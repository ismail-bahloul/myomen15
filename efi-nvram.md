# The EFI variable store (HP OMEN 15-en1xxx)

The firmware's *setup answers* are readable from Linux, as plain EFI variables —
and they are also stored, in clear, twice inside the SPI flash chip. This page
records what is in there, how it was read, and what it does (and does not) allow.

Everything below was measured on this machine. Nothing here was written.

## Why this matters

Until now the README said the flash chip was effectively opaque: the
`BIOS_Update.exe` payload is a proprietary container, and the big firmware
volumes are encrypted. That is true of the *reference* image. It is **not** true
of the flash chip itself: the parts that hold state — the UEFI variable store and
the AMD PBS/CBS answers — sit in clear, outside the encrypted volumes. They are
also exposed at runtime through `efivarfs`, with no `/dev/mem` needed.

## 1. The setup answers are readable at runtime

`/sys/firmware/efi/efivars/` carries the platform's own configuration variables.
The interesting ones on this machine:

| Variable | Size | What it holds |
|---|---|---|
| `AMD_PBS_SETUP-a339d746-…` | 132 B | The AMD **PBS** menu answers (one byte-ish per option) |
| `AmdSetup-3a997502-…` | 1448 B | AMD **CBS** answers (the menu the README called "inert") |
| `AMITSESetup-c811fa38-…` | 65 B | AMI setup state |
| `Setup-ec87d643-…` | 322 B | The main Setup table |
| `SetupDefault-0ee72c08-…` | 322 B | Factory defaults for the same table |
| `HPSetupData-206bc44a-…` | 116 B | HP's own setup data (also mirrored in the flash) |
| `NewHPSetupData-206bc44a-…` | 1024 B | HP's pending/side data |
| `HiiDB-1b838190-…` | 8 B | Pointer into the HII database used by the setup browser |
| `HideFanAlwaysOn-0ee72c08-…` | 1 B | HP fan-behaviour flag |

Two useful consequences:

- **`Setup` vs `SetupDefault` can be diffed.** They are the *same table at the
  same length* (322 B) — one holds the current answers, the other the factory
  defaults. Diffing them says exactly which options have been changed from
  default on this machine, without booting into the setup.
- **The whole store can be dumped offline.** Boot `edk2-shell` from the ESP and
  it will list every variable, including the runtime-only ones. An older dump is
  already sitting on the ESP at `/boot/nvram-dump.txt` (331 KB, UTF-16), and it
  is where the `NewHPSetupData` blob below came from.

## 2. The BIOS settings whose *names* are visible at runtime

The variable store is not the only place the setup lives. A dump of
`/boot/nvram-dump.txt` shows an **NVRAM store table** (the `NVAR` records,
signature `NVAR` + `0x1E`/`0x15`/`0x58` … lengths) listing the *names* of the
individual setting records, independent of the opaque `Setup` blob:

```
NVAR… PlatformLang      = en-US
NVAR… Timeout           = 0
NVAR… AMITSESetup
NVAR… PCI_COMMON
NVAR… UsbSupport        = 1
NVAR… NetworkStackVar
NVAR… SecureBootSetup
NVAR… TpmStateFlag
NVAR… ROM_CMN
```

This is the layer that makes the variable store legible: the `Setup` blob is an
opaque byte array, but the NVRAM records next to it name what those bytes mean.

## 3. The same data is in the flash chip, in clear, twice

Reading the SPI window at `0xff000000` (16 MiB) through `/dev/mem` shows each
region duplicated, and the copies are **almost** byte-identical. The
`AMD_PBS_SETUP` variable appears at two offsets:

```
0x7c0e17   copy A
0x7e0e17   copy B
```

The two copies differ at **exactly one byte**, offset 22:

```
A: … 01 01 01 01 01 02 00 00 01 01 …   (value 2)
B: … 01 01 01 01 01 02 01 00 01 01 …   (value 1)
```

One PBS option differs between the two images. The runtime variable matches
whichever of the two the firmware is currently running from.

This is the first *writable-looking* structure found in the flash, and it gives a
clean experiment for a later session: change that one option (the only one that
differs) in the setup via SmokelessUMAF, and see which of the two copies the
firmware updates. That identifies the **active image and the write path** without
touching anything that matters.

## 4. What is *not* in the clear

For contrast, and so this is not mistaken for a fully readable flash:

- The main firmware volumes (`0x1e4000`, `0xa00000`, `0xb00000`, `0xef0000`) are
  **encrypted or compressed** — entropy ≈ 8.0 bits/byte, and no `_FVH` signature
  is recoverable inside them. No FFS files can be listed.
- Searches for `Custom Core Pstates`, `Curve Optimize`, `PBO`, `SureStart`, and
  `OMEN` in the 16 MiB dump return **nothing**.
- **That is not evidence the menus are absent.** Because the bulk is encrypted,
  a string's absence only says it is not in the clear. The README's conclusion
  that `Custom Core Pstates` "contains no questions at all" is based on the
  *live setup browser* under SmokelessUMAF, which is the right instrument — but
  the flash dump neither confirms nor refutes it.

## 5. What *is* in the clear, and provably so

Two structures in the dump are not only readable, they are **signed**:

```
AMD_PBS_SETUP   (flash 0x7c0e17, 0x7e0e17)
AMD CBS answers (flash, mirrored)
APCB blocks     (flash 0x738000, 0x73c000, 0x874000, 0x878000, 0x87c000, …)
```

Each `APCB` header carries a `GUID` and an **MD5** over the block, so tampering
is detectable by inspection alone, before any flash is involved. The APCB data
itself is memory-tuning tables.

### The memory table names a module that is not installed

Inside the `APCB` block at `0x738000` (sub-tag `ECB2`, section `MEMG`, `BCBA`
inside) there is a literal SPD part-number table:

```
MT16ATF2G64HZ-3G2E1     <- the module actually installed (2 × 16 GB Micron)
8ATF1G64HZ-2G3B1        <- preserved profile for a module that is NOT here
```

`MT16ATF2G64HZ-3G2E1` is confirmed installed by `dmidecode` (both slots, DDR4
3200 MT/s, Micron). `8ATF1G64HZ-2G3B1` is a Micron 8 GB module that this machine
does not have.

**Interpretation:** the firmware ships *support for non-QVL memory* as concrete
data inside the image — whole SPD profiles, keyed by part number, including
modules that are not the ones installed. It is not active on this machine
because the installed part numbers have no entry of their own, which is why the
CBS memory options are unavailable. The lever to look at is therefore
`AMD CBS > UMC Common Options` (see `BIOS_arborescence_OMEN.md` §4.5.3), which
SmokelessUMAF already exposes.

## 6. The setup diff: exactly eleven options are off-default

`Setup` and `SetupDefault` are the same 322-byte table at the same layout, so a
byte-for-byte diff lists every option this machine has changed from the factory
state. There are **eleven**:

```
offset   9 : default=0x00 -> current=0x01
offset  21 : default=0x00 -> current=0x01
offset  22 : default=0x00 -> current=0x01
offset  23 : default=0x00 -> current=0x01
offset 174 : default=0x00 -> current=0x02
offset 244 : default=0x04 -> current=0x00
offset 276 : default=0x00 -> current=0x01
offset 278 : default=0x01 -> current=0x02
offset 280 : default=0x02 -> current=0x00
offset 284 : default=0x04 -> current=0x00
offset 316 : default=0x00 -> current=0x01
```

Unprivileged detail, and the reason the first attempt at this looked wrong: the
comparison only works once the two tables are **aligned**. A naive compare of
`StdDefaults` against `Setup` reports 99 differences, which reads like nonsense.
Aligning `StdDefaults` at **offset 17** makes it byte-identical to
`SetupDefault`, and the real count is eleven — 304 of 315 bytes match at shift
−1 versus 221 at shift 0, so the alignment is not a judgement call:

```
shift -1 : 304/315	shift  0 : 221/315	shift +1 : 212/315
```

### The reference table is confirmed by two independent sources

This is what makes the eleven trustworthy rather than a coincidence of one
variable. `StdDefaults` is a **firmware-provided** variable (1088 B) that embeds
the defaults table; `SetupDefault` is the runtime copy. They are byte-identical
at the right offset:

```
StdDefaults[17:17+322] == SetupDefault : True
```

So "off-default" is asserted against the firmware's own reference *and* the
variable store's, and a future firmware revision that breaks the assumption is
detectable rather than silently wrong. `evidence/setupdiff.py verify` re-checks
it, and every `snapshot` runs the check first.

### Tooling

`evidence/setupdiff.py` does the reading, so the experiment is one command:

```bash
sudo python3 evidence/setupdiff.py verify       # is the reference table still valid?
sudo python3 evidence/setupdiff.py offdefault   # the eleven, listed
sudo python3 evidence/setupdiff.py snapshot before
#   ... change ONE option in the BIOS, reboot ...
sudo python3 evidence/setupdiff.py snapshot after
python3 evidence/setupdiff.py diff before after  # which offsets moved, and which way
```

The `diff` prints, for each changed offset, the old value, the new value, the
**factory default**, and whether the option is now back on default or still off
it — which is what turns an offset number into a named option.

**Read §7 before using this to name an offset.** Saving the setup moves bytes on
its own, so a single before/after pair is not conclusive: any offset it reports
might have moved simply because the setup was written. Naming an option requires
the two-leg form described there.

### What it does *not* rule out

Eleven is low, and the temptation is to conclude the rest of the table is
untouched. That does not follow, and the alignment lesson above is the reason:
any offset where `Setup` and `SetupDefault` agree may still have been changed,
if the change was *written back to both*. What the diff proves is that these
eleven differ **now**; it cannot show that nothing was ever written elsewhere.

## 7. A controlled experiment: toggling the TPM three ways

This is the method put to the test, and the test says more about the method than
about the TPM.

### The setup

The idea was simple: change exactly one BIOS option, snapshot the EFI variables
before and after, and see which bytes the firmware rewrote. That would name the
offsets. `evidence/setupdiff.py` and `evidence/tpmstate.py` automate the reading;
four snapshots were taken around three changes:

| Snapshot | BIOS state |
|---|---|
| `before-tpm` | TPM disabled (the original state) |
| `after-tpm` | TPM enabled |
| `after-disable-tpm` | TPM disabled again |
| `after-hidden` | TPM `Hidden` |

### What it found about the TPM

The field at `Setup` offsets **3-4** is the TPM enable, and it is a clean
boolean:

```
before-tpm         0x01 0x01
after-tpm          0x00 0x00     <- enabled
after-disable-tpm  0x01 0x01     <- disabled
after-hidden       0x01 0x01     <- still disabled
```

`Hidden` does **not** touch it. What `Hidden` changes is `PostTpmDetect`:

```
off      TpmStateFlag=00  PostTpmDetect=01   /dev/tpm0 present
disabled TpmStateFlag=00  PostTpmDetect=01   /dev/tpm0 present
Hidden   TpmStateFlag=00  PostTpmDetect=00   /dev/tpm0 absent
```

So `Hidden` is "the firmware does not detect the TPM at POST", which is exactly
what the mode name promises, and it is the only one of the three that makes
`/dev/tpm0` disappear. The earlier guess that offsets 3-4 encoded *three* states
was wrong; the third state lives in a different variable.

### What it found about the method - and this is the important part

Saving the setup moves bytes elsewhere in the table, **whatever was changed**.
`Hidden` is a minimal edit (visibility only), yet it moved four offsets:

```
Setup        : 6, 7, 9, 221
SetupDefault : 1, 6, 221, 222
StdDefaults  : 18, 23, 238, 239
HPSetupData  : 97, 98, 100, 106
```

And `SetupDefault` and `StdDefaults` - the firmware's own *reference* tables -
moved too. They are not fixed points. **Every visit to the setup rewrites them.**

Consequences, stated plainly:

1. **"Factory default" is not a stable point on this machine.** Restoring
defaults today does not return to the state of two weeks ago; it returns to a
state that has absorbed every setup visit since.

2. **Returning to the same setting is not returning to the same state.** After
the on/off cycle, `Setup` at `before-tpm` and `Setup` at `after-disable-tpm`
are **not equal**. The TPM is off in both, but nine offsets (`1, 6, 7, 9, 13,
16, 17, 221, 222`) are not where they were.

3. **A single before/after diff cannot name an offset.** An offset that moves
during a test may have moved simply because the setup was saved. The method as
originally proposed is **invalid**, and this experiment is what invalidated it.

### The method that does work

Do every test **both ways** - change the option, snapshot, revert it, snapshot -
and keep only the offsets that move out **and back**. It costs two reboots per
option instead of one, and it is the only form of this experiment that means
anything.

**Correction.** This section previously said offsets 6, 7, 9 and 221 "move on
both legs, so they pass the filter" — backwards. `baseline-hidden` never
reverts `Hidden` back off, so the `Hidden` run has no revert leg at all; 6, 7,
9, 221 are exactly the offsets listed just above as moving on the single
`before-hidden` → `after-hidden` diff, which §7 itself says is not sufficient.
Running the filter for real, on the one triple in this data that *is* a true
out-and-back (`before-tpm` → `after-tpm` → `after-disable-tpm`, i.e.
off → on → off), with the tooling this correction added
(`setupdiff.py twoleg`):

```
$ python3 setupdiff.py twoleg before-tpm after-tpm after-disable-tpm

=== Setup ===
  2 offset(s) moved out AND back (real signal):
    offset   3: before-tpm=0x01 -> after-tpm=0x00 -> after-disable-tpm=0x01  default=0x01
    offset   4: before-tpm=0x01 -> after-tpm=0x00 -> after-disable-tpm=0x01  default=0x01
  5 offset(s) moved out but did NOT return (save-noise, discard): [6, 7, 9, 13, 221]

=== HPSetupData ===
  2 offset(s) moved out AND back (real signal):
    offset  94: before-tpm=0x01 -> after-tpm=0x00 -> after-disable-tpm=0x01  default=0xff
    offset  95: before-tpm=0x01 -> after-tpm=0x00 -> after-disable-tpm=0x01  default=0xff
  5 offset(s) moved out but did NOT return (save-noise, discard): [97, 98, 100, 104, 106]
```

Two results, not one: `Setup` offsets 3-4 pass the filter exactly as already
concluded — now on a rigorous basis rather than a mislabelled one — and
`HPSetupData` offsets 94-95 track them in perfect lockstep (`1 → 0 → 1`,
same steps, same snapshots), a second, independent variable confirming the
same TPM-enable bit. Neither was known to pass a real two-leg test before this.
Six, seven, nine and 221 remain unnamed noise, in `Setup` and `SetupDefault`
and `StdDefaults` and `HPSetupData` alike — the correction does not change
that part.

### Hypothesis check, for the record

Two explanations were on the table before the `Hidden` run:

- **A:** the TPM leaves state behind when toggled.
- **B:** saving the setup moves bytes regardless of what was changed.

`Hidden` decided it: **B.** One more reason to distrust any single-leg diff.

## 8. The `StdDefaults` name table

`StdDefaults-4599d26f-…` (1088 B) begins with an `NVARS` header followed by a
322-byte copy of the `Setup` table and then a list of `NVAR` records. Those
records name the individual settings records that make up the store, and they are
plain ASCII:

```
NVAR   PlatformLang      = "en-US"
NVAR   Timeout           = 0
NVARX  AMITSESetup
NVAR   PCI_COMMON
NVARG  UsbSupport        = 1
NVAR   NetworkStackVar
NVAR   SecureBootSetup
NVAR   TpmStateFlag
NVAR   ROM_CMN
```

The names are what make the opaque `Setup` blob legible: they are the *record*
names, not the question names, but they bound the search when mapping offsets to
questions.

## 9. The flash copies and the live variable are *not* byte-comparable

This is a negative result worth recording, because the obvious next step was to
use the one-byte difference between the two flash copies to index the table.

First, some structure. The flash entry is
`name (15) + NUL + attributes (4)` then 132 bytes of data. The runtime variable
is **140 bytes** and starts with `07 00 00 00` — and that is not a simple
"counter + attributes" prefix, because the following bytes do not line up with
either flash copy at *any* offset:

```
start=0  differ vs A: 77   vs B: 78
start=1  differ vs A: 73   vs B: 72
start=2  differ vs A: 71   vs B: 70
start=3  differ vs A: 75   vs B: 74
start=4  differ vs A: 66   vs B: 65     <- best, still 66 of 132
start=5  differ vs A: 67   vs B: 66
...
```

A best case of 66 mismatched bytes out of 132, with no offset reaching zero (or
anything close), means the two are **encoded differently** — the runtime form is
not the flash form with a prefix. Notably the runtime variable's last four bytes
are `00 5e 00 00` where both flash copies end `00 5e 00 00 4e 56 41 52` (the
`NVAR` signature of the next record), so the flash copy is cut short relative to
the runtime one.

**Consequence:** the "one differing byte between the two copies" is real and
reproducible, but it cannot be read as *an offset into the same table* without
first understanding the two encodings. Mapping question names to offsets needs
the IFR, and the IFR is in the encrypted volume.

## 10. How this was read (reproducible)

```bash
# 1. The setup answers, at runtime — no privilege beyond reading efivarfs
sudo dd if=/sys/firmware/efi/efivars/AMD_PBS_SETUP-a339d746-f678-49b3-9fc7-54ce0f9df226 \
        bs=1 skip=4 count=132 status=none | xxd

# 2. The flash window, read-only
sudo python3 -c "
import mmap,os
fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
print(mmap.mmap(fd,0x1000000,offset=0xff000000,access=mmap.ACCESS_READ)[0x7c0e17:0x7c0e30].hex())"
# -> 41 4d 44 5f 50 42 53 5f 53 45 54 55 50   "AMD_PBS_SETUP"

# 3. The NVRAM name table (needs an EFI-shell dump; an old one is on the ESP)
sudo iconv -f UTF-16LE -t UTF-8 /boot/nvram-dump.txt | less
```

For the record, the flash entry is laid out as
`name (15) + NUL + attributes (4)` followed by 132 bytes of data, and the
runtime variable is 140 bytes starting `07 00 00 00`. As §8 shows, those two
forms do **not** line up at any offset — do not assume a fixed prefix.

## 11. The write path, and why it is not the way in

Reading is not a dead end; writing to the **setup** store is.

- `efivarfs` is mounted `rw`. Of the 137 variables, **22 open `O_RDWR`** — the
  standard EFI globals (`Boot####`, `BootOrder`, `Timeout`, `PlatformLang`,
  `OsIndications`, …); rewriting `Timeout` with its own bytes succeeds. The other
  **115 refuse `O_RDWR`** with `Operation not permitted` *before* any write: they
  are marked `immutable` (efivarfs sets the inode flag `i`, visible with
  `lsattr`), and that set is exactly the BIOS/HP/AMD **setup** store, the Secure
  Boot keys and the TPM state. The attribute dword is the same in both groups
  (`0x7`), so this is not attribute-driven.
- `HP Sure Start` is **active**. `hp-bioscfg` exposes only `Sure_Start` (audit
  log: `Operation not supported`) and `pending_reboot` (= `0`). Its
  `authentication/SPM` node reports `role = enhanced-bios-auth`,
  `is_enabled = 0`, `key_mechanism = not provisioned` — i.e. **no BIOS admin
  password is set**, and no auth token is provisioned to change settings.
- `fwupd` sees the system as updatable, but there is a **PSS/RSA signature over
  the BIOS payload** (`/boot/EFI/HP/BIOS/Current/088D1.sig`, 256 bytes; the
  payload's PSS blocks are still visible in the clear inside `088D1.bin`). A
  modified image cannot be re-signed.

So the correct conclusion is not "the setup is locked" — it is **"the setup is
readable, and it is readable *twice*"**. Reading is what gives leverage here;
writing is guarded by Sure Start and a signature that cannot be reproduced.

## 12. What this changes in the rest of the repo

- The claim *"the BIOS update payload cannot even be extracted"* is too strong:
  the container cannot be extracted **as an Aptio image**, but the flash chip
  itself holds the live, unencrypted configuration, and the payload is right
  there on the ESP to inspect.
- The claim *"`Custom Core Pstates` is empty, therefore there is nothing to
  configure"* should carry the caveat from §4: the flash is encrypted, so that
  conclusion rests on the live browser, not on the image.
- The AMD CBS power menu being "inert" is consistent with §1: its answers are
  stored (`AmdSetup`, 1448 B) and readable, so the setting *is* recorded. That
  it has no effect on the SMU limits is a separate, already-measured fact.

## 13. Next steps, in order of value

1. **Name the offsets.** Two of the eleven are now named: **offset 9** was
   ruled out as a TPM effect (§7 — it moves during the TPM cycle, but as
   noise, not signal), and offsets 276-284 are confirmed **untouched** by the
   TPM toggle at all (checked directly against the `twoleg` triple, zero
   movement). Nine remain (`21, 22, 23, 174, 244, 276, 278, 280, 284, 316` —
   note offset 9 is settled, not named to a TPM cause). One at a time:
   snapshot, change a single option in the BIOS, reboot, snapshot, revert the
   same option, reboot, snapshot again, `setupdiff.py twoleg`. Tooling is
   written and tested — `evidence/setupdiff.py`.
2. ~~Correlate one of the eleven with a known-changed setting: the TPM~~ —
   done, and it named a *different* offset than expected. The TPM toggle (§7)
   turned out to explain `Setup` offsets 3-4 and, newly, `HPSetupData`
   offsets 94-95 — neither of which is one of the eleven off-default offsets,
   because this machine's TPM setting is already at its factory default
   (`disabled`). It does not touch offsets 276-284 at all, which was the
   original guess for "the cheapest candidate": that guess is now closed,
   not open.
3. **Decide the encoding question of §8.** Either locate the IFR in the
   encrypted volume (hard), or find a second variable whose live and flash forms
   are both known, so the transformation between them can be inferred (cheap).
4. **The memory side** — the firmware's own SPD table names a module that is not
   installed; the lever is `AMD CBS > UMC Common Options`.
