# Firmware & hardware limits (HP OMEN 15-en1xxx)

Living reference for what this firmware does and does not allow, so the dead
ends are not explored again. Everything here was measured on this machine.

The point-in-time investigation record is in `record/` in this repository; this
file is the distilled, current conclusion.

## The setup is readable — the flash chip is not fully opaque

An earlier conclusion in this repo was that the firmware is a black box: the
update payload is a proprietary AMI container, and the flash is shared with the
EC. That is true of the *payload*. It is **not** true of the flash chip itself,
and it is not true of the running system.

**The BIOS setup answers are plain EFI variables**, readable from Linux with no
reboot and no `/dev/mem`:

```
/sys/firmware/efi/efivars/AMD_PBS_SETUP-a339d746-…   132 B    PBS menu answers
/sys/firmware/efi/efivars/AmdSetup-3a997502-…        1448 B    CBS menu answers
/sys/firmware/efi/efivars/Setup-ec87d643-…            322 B    the Setup table
/sys/firmware/efi/efivars/SetupDefault-0ee72c08-…     322 B    its factory defaults
/sys/firmware/efi/efivars/HPSetupData-206bc44a-…      116 B    HP's own setup data
```

The same bytes are also sitting in the **flash chip, in clear, twice** — outside
the encrypted volumes. The two `AMD_PBS_SETUP` copies (flash `0x7c0e17` and
`0x7e0e17`) differ in **exactly one byte**, at offset 22; the runtime variable
matches whichever the firmware is running from.

So the interesting detail is not that the flash is opaque — it is that it is
readable **twice**, and the one byte that differs between the copies is a free
correlation point for naming the rest of the table. Full detail, with the
reproduction steps, is in [`efi-nvram.md`](efi-nvram.md).

### What this corrects

- **"The payload cannot even be extracted"** was too strong. It cannot be
extracted *as an Aptio image*, but the live configuration is readable at
runtime, and the payload is sitting on the ESP at
`/boot/EFI/HP/BIOS/Current/088D1.bin` (16 MiB) to inspect.
- **"`Custom Core Pstates` is empty, therefore there is nothing to
configure"** still needs a caveat, but a narrower one than before — see
["Three of the four \"encrypted\" regions are now identified"](#three-of-the-four-encrypted-regions-are-now-identified)
below. The empty-menu finding rests on the live setup browser under
SmokelessUMAF, which is the right instrument regardless; the image neither
confirms nor refutes it.
- **The memory-tuning dead end was a QVL dead end, not a firmware one.** The
image carries whole SPD profiles keyed by part number, in signed `APCB` blocks
(each with its own GUID and MD5). One of them is a literal
`8ATF1G64HZ-2G3B1` — a Micron module this machine does not have. The installed
modules are `MT16ATF2G64HZ-3G2E1` (confirmed by `dmidecode`, both slots), which
have no profile of their own. The lever is `AMD CBS > UMC Common Options`.

### The write path: writable for the globals, not for the setup

Nothing above changes the flashing conclusion, but the earlier blanket "every
variable refuses `O_RDWR`" was wrong. Of the 137 variables, **22 open `O_RDWR`
and can be written** — the standard EFI globals (`Boot####`, `BootOrder`,
`BootCurrent`, `ConIn`/`ConOut`, `ErrOut`, `Timeout`, `PlatformLang`,
`OsIndications`, systemd's `LoaderSystemToken`); a no-op rewrite of `Timeout`
with its own bytes succeeds. The other **115 are `immutable`** — efivarfs sets
the inode flag `i` (visible with `lsattr`), so `O_RDWR` returns `EPERM` before any
write — and that set is exactly the BIOS/HP/AMD **setup** store (`Setup`,
`SetupDefault`, `AMITSESetup`, `AmdSetup`, `AMD_PBS_SETUP`, `HPSetupData`,
`NewHPSetupData`, `StdDefaults`), the Secure Boot keys, and the TPM/firmware
state. The attribute dword is the same (`0x7`, `NV|BS|RT`) in both groups, so the
refusal is not attribute-driven.

So the **setup variables** are readable and not writable, which is the part that
matters. Sure Start is active, `authentication/SPM` reports `is_enabled = 0` and
`key_mechanism = not provisioned` (so no BIOS admin password is set either), and
the BIOS payload is PSS/RSA-signed — a modified image cannot be re-signed.

One writable variable worth knowing: **`OsIndications`** — the standard bit a
bootloader sets to ask the firmware to process a capsule update.

## BIOS power limits are a POST-time seed, not a policy

`ryzenadj` writes the SMU limits directly; the BIOS *System Configuration*
setting (`AMD CBS > NBIO Common Options > SMU Common Options`) only chooses the
values the firmware seeds at POST. Those seeds are the **stock** profile,
measured as:

```
firmware/POST limits: STAPM LIMIT=54.000 PPT LIMIT FAST=65.000 PPT LIMIT SLOW=54.000 THM LIMIT CORE=100.000
```

`power-profile.service` replaces them ~12 s after boot, and
`power-profile.timer` re-applies every 5 min as a safety net (see "Power limits"
below for what that net actually protects against).

**The setting is inert.** Selecting `35W POR` there and rebooting produced the
same stock values above. The HP EC appears to own them and override the AMD
setting. The setting is now back on its default `Auto` with no observable
difference — which is itself the confirmation. Don't spend time on that menu; if
firmware-level limits are ever needed for Windows, the lever to look at is HP's
own thermal mode, not AMD CBS.

## Undervolt / Curve Optimizer: locked on the SMU path (dead end *there*)

Not possible through the **SMU mailbox** on this machine — on **either** OS. Seven
independent confirmations:

1. `ryzenadj --set-coall`, `--set-coper` and `--set-cogfx` all return
   **`rejected by SMU`**, including for the neutral value `0`. `--enable-oc`,
   `--disable-oc` and `--gfx-clk` are rejected too, while `--stapm-limit` /
   `--fast-limit` / `--slow-limit` / `--max-performance` are accepted.
2. The encoding was verified against ryzenadj issues #302 / #296 (a negative
   offset is `0x100000 - value`, a per-core offset is `(core << 20) | value`),
   so this is not an encoding mistake.
3. The BIOS has **no Curve Optimize menu**, only *Custom Core Pstates* — and its
   form contains **no questions at all** in the IFR.
4. Patching the `SuppressIf` guards with SREP (`SuppressIFPatcher.efi` /
   `SetupBrowser.efi` on a USB key) and re-entering the menu with `Accept` +
   `F10` + reboot still leaves *Custom Core Pstates* empty.
5. `amdgpu`'s `pp_od_clk_voltage` exposes clock offsets only — no voltage curve
   for the iGPU either.
6. **Windows cross-check — the decisive one.** UXTU (Universal x86 Tuning
   Utility) *looks* like it succeeds, but its own `uxtu_log*.txt` records
   **20 failures out of 20 `set-coall` writes**, including offset `0`, with
   `SMU command 'set-coall' failed with status FAILED`. UXTU catches the
   exception, logs it as a warning, and **still updates its UI**, so a failed
   write looks applied. A direct SMU probe through UXTU's own PawnIO driver
   confirms it: the mailbox works (`0x0D` PM-table version, `0x14` stapm-limit)
   while the whole OC/CO command family is refused (`0x55` set-coall, `0x54`
   set-coper, `0x64` set-cogfx, `0x2F` enable-oc, `0x30` disable-oc, `0x49`
   pbo-scalar, `0x65` PM-table transfer).
7. **The raw mailbox, with the driver's masking of failures lifted.** The
   `mp1_smu_cmd` sysfs node reports `0x01` even for a `Failed` — a driver bug,
   see [`smu-raw.md`](smu-raw.md#the-response-node-masks-failures). Read from
   the rsp register over SMN instead, the SMU answers `0xFE UnknownCmd` for a
   deliberately-invalid ID but `0xFF Failed` for `set-coall` / `set-coper` /
   `set-cogfx`: it *recognises* the CO family and refuses it deliberately. →
   [`smu-raw.md`](smu-raw.md#is-the-curve-optimizer-gate-a-transport-problem-measured-no)

Point 6 also settles the obvious hypothesis: UXTU reaches the SMU by the **same
path as Linux** (PawnIO → `RyzenSMU.bin` → SMN indirect via PCI config
`0xB8`/`0xBC`), with the **same message IDs and the same argument encoding**.
`ryzenadj` already sends the correct command for Cezanne, so there is nothing to
patch or port — the firmware simply gates the OC/CO family off, consistent with
points 3–5 and with HP Sure Start.

**Do not** install ZenTune (ex-UXTU4Linux) hoping for CO, and **do not** patch
`ryzenadj` for it.

### The second road, measured: it is inert

Every confirmation above goes through the **SMU mailbox** (`ryzenadj` on Linux,
PawnIO → `RyzenSMU.bin` on Windows). SSDT2 declares a second `PNP0C14` device,
`\AOD`, with a command table that says, in literal strings, `Set Curve
Optimizer`. Its handler does not use the mailbox at all:

```
Method (R308, 1, NotSerialized)          // ACMD 0x0005000A
{
    CreateDWordField (Arg0, 0x04, SVAL)
    MBVS = 0x05
    COPS = SVAL
    MBCB = 0x00100032
    ASMI (0xB9)                          // writes I/O port 0xB2 -> SMM -> BIOS
}
```

That is the path HP's own tuning software uses, and it asks the **BIOS**, not
the SMU. The same table exposes `Set PPT Limit`, `Set TDC/EDC Limit`, `Set
Scalar`, `Set IOD VDDG`, and `Set Soc TDC/EDC`.

**This road was untested when the rest of this section was written. It has now
been driven, with a lever whose effect is independently known and readable — a
power limit.** `Set PPT Limit` is ACMD `0x00050001` → `R23B`; called through
`\AOD.AM05` at 25000 and 12000 mW, and `Set TDC Limit` (`0x00050002`) at 45000,
**none of them moved the SMU's PPT or TDC limits**, while the same values set
through `ryzenadj` moved them immediately. The `power-profile-watch` service had
to be stopped for the test: it polls the PM table every second and re-applies
the profile, which reverted **both** the AOD write and a control write before
the read. So the road is live but **inert** for this class of control — the same
shape of result [`h2ra-region.md`](h2ra-region.md) found. A Curve Optimizer
write here would plausibly be equally inert, and cannot be read back to tell.
Detail: [`evidence/aod-power-limit-probe.txt`](evidence/aod-power-limit-probe.txt).

The handler itself is located in the image — `AodSmmSsp` — and, measured, it
carries no SMU mailbox address and depends on no SMU protocol; see
[`acpi-bridge.md`](acpi-bridge.md) §2 and
[`evidence/aod-smm-handler.txt`](evidence/aod-smm-handler.txt).

`\AOD.AM04` returns zeros, so the road can only be judged by **effect** — which
is exactly what the test above did, on a lever already known to work. `\AOD.AM01`
answers `0x5` and `\AOD.AM03` returns the command table, so the interface is
live; it simply does not drive the SMU. Detail:
[`acpi-bridge.md`](acpi-bridge.md).

## BIOS modding: not possible (HP Sure Start)

`hp-bioscfg` reports **HP Sure Start** active, which verifies and restores the
firmware on tamper. On top of that the flash chip is shared with the EC (fan
control), and `flashrom` is deliberately not used here: a failed write would
risk the fans. **Reading is a different question from writing, and this section
used to conflate them** — see below: the payload turned out not to resist
reading at all, only writing.

The image itself is not opaque — see
["The setup is readable"](#the-setup-is-readable--the-flash-chip-is-not-fully-opaque)
above. The payload on the ESP is a 16 MiB AMI firmware image with two complete
copies of the flash, and the parts that hold *state* are in clear.

## Three of the four "encrypted" regions are now identified

This corrects a claim made twice in this repo — that `uefixtract` does not
recognise the `BIOS_Update.exe` payload, and that the firmware volumes at
`0x1e4000, 0xa00000, 0xb00000, 0xef0000` "are encrypted or compressed" —
**mostly**. `0xb00000`/`0xef0000` were a missing external tool, not an
unreadable image, and fully parse as UEFI volumes. `0xa00000` is AMD's own
PSP firmware directory — a different, signed (not encrypted) format that
`uefiextract` was never going to parse regardless of tooling. Only
`0x1e4000` is unresolved, exactly where it started.

**The container is a documented, public AMI format, not proprietary.** `@UAF@`
/ `@UII@` is "AMI UCP" (Utility Configuration Program) — `platomav/biosutilities`
(`pip install biosutilities`) parses it directly: `Tag`, `Size`, `Checksum`,
`Compress Size`, `Original Size`, `Filename`, one module per tag. Unwrapping it
extracts `BIOS_00.bin` — **16,777,216 bytes, byte-for-byte identical to
`/boot/EFI/HP/BIOS/Current/088D1.bin`**, the exact file the entropy scan
above was run against.

**What made `uefiextract` fail on it silently was one missing binary.**
EFI-compressed sections (`GUID defined | EE4E5898-3914-4259-9D6E-DC7BD79403CF`
— the standard Tiano/EFI compression GUID) need `TianoCompress` on `PATH`, and
without it `uefiextract` reports nothing and exits non-zero, with no error
message pointing at what's missing. `TianoCompress` is not exotic — it is
EDK2's own BaseTools, buildable from the public `tianocore/edk2` source in
about ten seconds (`evidence/bios-unwrap.sh`). With it present, `uefiextract`
parses `088D1.bin`/`BIOS_00.bin` into 6 firmware volumes and 684 files, real
`_FVH` headers throughout — but only **two** of those six volumes are at the
addresses this repo had already flagged: `0xb00000` and `0xef0000`. Full
structural report: [`evidence/bios-image-report.txt`](evidence/bios-image-report.txt).

**`0x1e4000` and `0xa00000` are not in that report.** A byte-level re-scan of
`BIOS_00.bin` confirms genuinely high entropy (7.4–8.0 bits/byte) across
`0x0–~0x1e0000` and `~0x820000–~0x9e0000` — real regions, not an artifact of
where the two literal addresses happened to land (both sit just past the edge
of their block, in ordinary `0xFF` padding). `uefiextract` reports both as
top-level `Padding`: no FFS/FV structure, a different failure mode from the
one `TianoCompress` fixed — this was never going to be a UEFI volume, because
it isn't one.

**One of the two is now explained; the other genuinely isn't.** The
`~0x820000–~0x9e0000` region is AMD's own PSP firmware directory — confirmed,
not guessed: `psptool` (`PSPReverseEngineering/psptool`) finds a complete,
valid `$PSP` directory header at `0x863000`, with `$BHD`/`$PL2`/`$BL2`
siblings nearby, the same structure it parses in full at `0xc53000`. The
offset between the two — `0x3F0000` — is **exactly** the offset between the
two Sure Start UEFI volumes (`0xef0000 − 0xb00000`). Both firmware layers use
the same A/B redundancy scheme, at the same relative distance; the two
directory headers differ in a few bytes (unaudited — not a byte-identical
copy) but are unmistakably the same format. `evidence/psp-directory-report.txt`
is the full parse of the `0xc53000` copy — real signed PSP modules, by name,
with per-file verification status: `PSP_FW_BOOT_LOADER`, `PSP_FW_TRUSTED_OS`,
`SMU_OFFCHIP_FW` (the actual SMU firmware image this repo has been probing
all session via the mailbox), `AMD_PUBLIC_KEY`, and others — most
`verified(<keyid>), sha256_ok`, a few (`SMU_OFFCHIP_FW`, `PMU_CODE`/`PMU_DATA`)
`compressed, veri-failed(<keyid>), sha256_ok`.

**Checked, not a firmware flaw.** `psptool -E -t` shows a real RSA check was
attempted — the certifying key (`96A0` for `SMU_OFFCHIP_FW`, `4F75` for
`PMU_CODE`/`PMU_DATA`) is present in this image's own key tree and was tried,
not missing (that has its own distinct `key_missing(...)` label in `psptool`,
never seen here). Every other key in the tree verifies `True` for all of its
files; only these two, and only for `compressed` entries, fail — 100%
consistent, not one success among them. The obvious next suspect, an AMD
generation-specific decryption key (`psptool`'s own source has a `TODO: Find
out how to identify the correct IKEK` and hardcodes the Zen+ one regardless of
platform), is **ruled out by direct measurement**: both files' own headers
read `encrypted=0` — decryption is never attempted, only decompression, which
completes with no warning. Likely `psptool` itself mis-slices the decompressed
body against a `size_signed` field meant for the compressed one, for this
specific PSP entry type — but that is not confirmed, and it is a `psptool`
question, not a question about this machine's firmware.

`0x0–~0x1e0000` remains completely unaccounted for: no `$PSP`/`$BHD`/`$BL2`/
`$PL2`/`_FVH` magic anywhere in it. Still genuinely opaque, still a
hypothesis-free dead end.

**This maps "Sure Start" onto actual named modules, for the first time.** Two
identical-size volumes (`61C0F511-A691-4F54-974F-B9A42172CE53`, 0x110000 bytes
each) sit at `0xB00000` and `0xEF0000` — the "two complete copies" already
known from the flash-level read, now with an exact address and a manifest:

```
AmdPspPeiV2, AmdPspFtpmPei, AmdCpmABRecoveryPeim, RecoveryControl,
NvmeRecovery, PcdRecoveryPei, AmiPspFtpmPei, AmiPspPlatform, AhciRecovery,
Recovery, FsRecovery, IdeRecovery, HPCrisisRecovery          (PEI modules)

AmdPspDxeV2Rn, AmdPspFtpmDxe, PspPlatformDriver, PspDxe, AmiPspNvramDxe,
PspResource, OememSecureBootDxe, SecureBootDXE, PspSetPcdForRecovery  (DXE)

AmdPspP2CmboxV2, AmdPspP2CmboxV2SmmBuffer, AmdPspSmmV2, AmiPspNvramSmm,
PspS3Smm, PspResumeServicesSmm                                (SMM)
```

`HPCrisisRecovery` and the A/B recovery PEIMs are, by name, almost certainly
what `hp-bioscfg`'s `Sure_Start` audit flag refers to as one opaque word. The
NVAR store is in the same volume family, at `0x7C0000` (0x20000 bytes),
containing the exact GUIDs `efi-nvram.md` already names from the runtime side
(`Setup`, `StdDefaults`, `SecureBootSetup`, …) — one exception logged, not
resolved: `uefiextract`'s own name table labels GUID
`0EE72C08-8185-427A-A58A-855B78B7BA0B` **`TpmStateFlag`**, where this repo's
own `efivarfs` reading calls the same GUID **`SetupDefault`**. Worth checking
before relying on either name for that specific GUID.

**What this is not.** It is read access, and read access to a plaintext image
was never the blocked operation — writing was, and still is: the PSS/RSA
signature requirement is over the payload as a whole and does not care whether
the payload is human-readable. Nothing here writes anything, and nothing here
makes Sure Start's signature check any easier to pass. What it does do is turn
"Sure Start is active" (a config-audit assertion) into a list of the actual PEI
and DXE/SMM modules that implement it, at known offsets — the necessary
starting point for anyone who wanted to go further (disassembling those PE32
images), not a shortcut past it.

Reproducing: `evidence/bios-unwrap.sh <path to BIOS_Update.exe or 088D1.bin>`.

## Power limits: what resets them is **not** established

This section has now been wrong in three different ways, so it is written as
the current state of the evidence rather than as a conclusion.

### What is solid

`ryzenadj` writes take and hold. Writing `37/44/37` reads back `37/44/37`, and
the two 10-minute A/B runs (`evidence/nbfc_{on,off}.csv`) showed no reversion.

### The three claims, in order

| # | Claim | Status |
|---|---|---|
| 1 | "The EC periodically reverts the limits, hence the 5-minute timer" | **confirmed, finally** — see the timestamped journal below |
| 2 | "A `platform_profile` write makes the EC re-apply its own limits" | **measured once, then contradicted** — not supported |
| 3 | "Claim 2 is wrong" (an earlier over-correction in this file) | itself wrong: the test that produced it never set a distinctive value first |

The one measurement that looked decisive:

```
[18:48:08] platform_profile MODIFY -> 'balanced'
[18:48:09] LIMITS CHANGED: 35/42/35 -> 54/65/54
```

### What contradicts it

With every power-profile unit **stopped** and no other writer present, writing
`platform_profile` was measured over 5 seconds of 100 ms polling, for all three
profiles (`cool`, `balanced`, `performance`), and **the limits did not move**:

```
depart  : (37, 44, 37)
write platform_profile = 'performance'
final   : (37, 44, 37)      after 5 s
```

So the write alone does not reset them, and claim 2 is not supported.

### But the drift is real, regular, and now timestamped

The watcher was finally instrumented well enough to catch it, and it caught
**two** events within 45 seconds of each other, right after its own startup
apply. From its journal:

```
19:10:34  baseline after startup apply: 35/42/35
19:11:21  limits moved 35/42/35 -> 50/42/35      STAPM 35 -> 50
19:11:21  re-applied after silent limit change in 0.12s
19:12:06  limits moved 35/42/54 -> 35/42/35      PPT slow 35 -> 54
19:12:06  re-applied after silent limit change in 0.12s
```

Then it stopped — no further events. So it is not a fight in a loop, but it is
neither rare nor periodic: it happens in the minute or two **following an
apply**, and then settles.

This is the original §5 observation, finally measured with timestamps rather
than inferred: the limits **are** rewritten, and the code that was blamed
(`platform_profile`) was not the writer.

### And it explains `50/65/54`

`50` is `STAPM`, and `54` is `PPT slow`. Both were seen leaving the profile
values and heading back toward the stock ones:

| Field | Profile sets | Drifts to |
|---|---|---|
| `STAPM` | 35 | **50** |
| `PPT fast` | 42 | (65, seen in the earlier readings) |
| `PPT slow` | 35 | **54** |

So `50/65/54` was never a single "EC profile" — it is the three fields
drifting back to their stock values, not necessarily at the same moment. The
`50/65/54` reading in §5 and the one in the TUI were two of these, captured
mid-drift.

### `54/65/54` is still this machine's own PERF profile

Independently of the above:

```
/usr/local/bin/power-profile:53
    ryzenadj --stapm-limit=54000 --fast-limit=65000 --slow-limit=54000 \
             --apu-slow-limit=42000 --tctl-temp=90
```

`apply_perf()` writes exactly `54/65/54`, chosen to match the stock values. So
a `54/65/54` reading is ambiguous: it can be PERF being applied, or the drift
landing on all three fields at once. The number alone does not say which.

### Still not known: the mechanism

What is established is **that** the fields drift back, that it follows an apply
within a minute or two, and which fields (`STAPM` -> 50, `PPT slow` -> 54). What
is not established is **why** — no writer has been identified, no EC register
carries those values, and the drift is invisible to inotify.

`STAPM` is a *sustained* limit with a 275 s time constant, so the SMU
re-deriving it would be a natural explanation; `PPT slow` heading to its stock
54 at the same time is harder to fit to that. Recorded as an open question.

### The practical position

Whatever the mechanism, the fix does not depend on identifying it:

| Mechanism | Signature | Detection |
|---|---|---|
| `platform_profile` write | limits reset, inotify event | inotify on the attribute |
| the drift | field(s) leaving the profile values | read the PM table once a second |

Reading the limits is nearly free (one `read()` of 2372 bytes, no SMU command,
no ACPI call), so the profile is applied **only when the values move**, plus
once at startup so a watcher beginning from a wrong state still corrects it.
Measured: 0.12 s per correction, against a 5-minute timer before.

Two events in the observed window means the machine would otherwise have spent
up to five minutes at `50/42/35` or `35/42/54` — the timer alone was not enough,
and this is the first time that has been demonstrated rather than assumed.

The pieces are `evidence/power-profile-watch` and
`evidence/power-profile-watch.service`; they delegate the apply to
`systemctl start power-profile.service`, so there is one implementation of the
profile. `power-profile.timer` stays as a third backstop.

### The lesson, kept

This question was answered wrongly three times before it was answered right, and
the three failures had two shapes:

1. **A value read without establishing what it was first.** The 10-minute A/B
   that "disproved" the drift ran while the guard was disabled and caught a quiet
   period; the re-test that "disproved" the `platform_profile` cause started with
   the limits *already* at `54/65/54`, so "no change" proved nothing.
2. **A number attributed without checking who wrote it.** `54/65/54` was blamed
   on the EC for two sessions. It is written by `apply_perf()` in
   `/usr/local/bin/power-profile`, in this machine's own configuration.

What finally worked was instrumenting the watcher well enough to log the drift
with timestamps, and reading the PM table fast enough to catch fields leaving one
at a time. Both are cheap; neither was the first thing tried.

Two rules kept from it:

- **Set a distinctive value before measuring whether something resets it.**
- **Before attributing a value to firmware, `grep` your own configuration.**

The investigation scripts are `evidence/limitwatch.py` and
`evidence/limitrace.py`; the original A/B is `evidence/ec-revert-ab-test.sh`.

## Battery charge thresholds: reachable, not exposed

The kernel surface really is empty — `powerdevil` reports "not supported by
kernel", `/sys/class/power_supply/BAT0/` has no `charge_control_*` attributes,
and `hp-bioscfg` exposes nothing. That part of the earlier conclusion stands.

What does **not** stand is calling the mechanism opaque. The DSDT shows HP's own
WMI methods doing exactly this, on a named EC register:

```
Method (GBCC, 0, Serialized)   // "HP WMI Command 0x1F (BIOS Read)"
Method (SBCC, 4, Serialized)   // "HP WMI Command 0x1F (BIOS Write)"

\_SB.PCI0.SBRG.EC0.MBDC    charge-control register, written by SBCC
\_SB.PCI0.SBRG.EC0.MBTS    battery-usable guard
\_SB.PCI0.SBRG.EC0.MBST    modes supported, bits 0-1
\_SB.PCI0.SBRG.EC0.ADPP    AC-present guard
```

And `acpi_call` reaches them right now:

```
\_SB.PCI0.SBRG.EC0.MBTS  -> 0x1     battery usable
\_SB.PCI0.SBRG.EC0.MBST  -> 0x0     ** no cap mode advertised **
\_SB.PCI0.SBRG.EC0.MBDC  -> 0x0     nothing set
\_SB.WMID.GBCC            -> [0x0, 0x4, {0x00, 0xff, 0x00, 0x00}]   mode 0
```

The `BCTC` / `BMNC` read-only finding is about the ACPI *battery* objects, a
different mechanism. Both statements are true; the earlier page conflated them.

**Written to, and measured — the answer was not what this page expected.** The
argument encoding is decoded and the revert (`MBDC &= 0xE0`) is shared by both
code paths. Writing it did not produce a cap: the EC acknowledges and stops
charging, and the pack then discharges with no threshold (measured 100 % → 55 %).
`MBST = 0x00` was right that no cap mode is advertised. The cap that **does**
hold is a different lever — `Adaptive Battery Extender`, one EC bit (`SHEN`),
which the BIOS sets, which explains the 84.8 % `BFCC`/`BADC` ratio, and which is
**readable but not writable** from Linux. Full detail:
[`battery-charge-control.md`](battery-charge-control.md).
Tooling: `evidence/batterycctl.py`.

## The PM table: what the SMU is actually doing

`/sys/kernel/ryzen_smu_drv/pm_table` is a plain read-only file of 2372 bytes, and
it decodes as `float32` — nine limits, each followed by its live value:

```
STAPM      limit=50.000   live=8.941      TDC_VDD   limit=58.000   live=9.965
PPT_FAST   limit=65.000   live=18.872     TDC_SOC   limit=15.000   live=4.347
PPT_SLOW   limit=54.000   live=19.148     EDC_VDD   limit=110.000  live=79.132
PPT_APU    limit=22.000   live=19.148     EDC_SOC   limit=20.000   live=0.000
THM_CORE   limit=85.000   live=65.364
```

This is the instrument the Windows half of this repo concluded it could not have
(there, the PM table never populated — the refresh command `0x65` was refused and
the read returned zeros). On Linux it is populated and needs no SMU command at
all. Any "did this write take, and does it survive?" question is now one file
read instead of parsing `ryzenadj --info`.

It also closes an old loose end: the "`50/65/54` vs `54/65/54` discrepancy" was
never a discrepancy. `0x00` is STAPM and `0x10` is PPT-slow; reading a triple as
"STAPM / fast / slow" and expecting 54 in the first slot was the error. Details in
[`pm-table.md`](pm-table.md).

## Not supported by the kernel / firmware

- **Battery charge thresholds**: not exposed by the kernel, but two firmware
  levers exist — see "Battery charge thresholds" above.
- **Serial port**: `8250.nr_uarts=0` was measured to save ~0 — the `ttyS*`
  devices are not on the critical path — so `limine.conf` was left untouched (it
  carries the VFIO entry).
- **MSR**: `/dev/cpu/*/msr` exist but `read()` returns `EIO`.
- **EFI variable writes**: refused with `EPERM` for the BIOS/HP/AMD **setup**
  store and the Secure Boot keys (efivarfs marks those inodes `immutable`); the
  standard EFI globals — `Boot####`, `BootOrder`, `Timeout`, `OsIndications`, … —
  *are* writable.
- **TPM**: currently set to `Hidden` — disabled and not detected at POST.

## The firmware ships a generic EC / I-O bridge

SSDT12 declares byte-level access to **any** EC register and **any** I/O port:

```
\_SB.PCI0.SBRG.EC0.M040 <offset>         read  any EC byte
\_SB.PCI0.SBRG.EC0.M041 <offset> <val>   write any EC byte
\_SB.PCI0.SBRG.EC0.M31A <port>           read  any I/O port byte
\_SB.PCI0.SBRG.EC0.M319 <port> <val>     write any I/O port byte
```

Verified exhaustively against `ec_probe`: **256 of 256 registers agree**. Two
consequences worth noting:

- It is a **fourth independent path to the EC** (after `ec_sys`, `hp-wmi` and the
  `H2RA` memory region), so a disagreement between paths is detectable.
- `M319` reaches **any I/O port, including `0xB2`**, the AMD SMM command channel
  — the same one `\AOD` uses. Nothing in the kernel exposes that.

Tooling: `evidence/ecbridge.py`, read-only unless `--yes`. Detail:
[`acpi-bridge.md`](acpi-bridge.md).

## HP's performance mode, located (in the EC)

The earlier note here said HP's thermal mode "has not been located on the Linux
side". It is at two adjacent EC registers:

| Register | Offset | Meaning |
|---|---|---|
| `OCPC` | `0xBA` | current performance profile (0–6) |
| `OCPS` | `0xBB` | highest selectable profile |

Currently `OCPC = 0x01`, `OCPS = 0x07`. Note that `OCPC` is EC-owned: it read `0x00`
later in the same session and a write is reverted in ~100 ms, so the "current"
value is whatever the EC decided. `PWLC` (DSDT 17344) maps the profile to
dGPU power limits in mW through `\DPTC` — profile 0 gives 54/65/54 W, profile 6
gives 15 W. It is switched by EC query events (`_Q8C` applies, `_Q8E` cycles up),
not by a WMI command.

So this is a **live, writable mode selector in the EC**, and `\DPTC` is callable
directly. It drives the dGPU rather than the CPU, so it is not the CPU thermal
mode the earlier note was chasing — but it is the same family of control, and it
was previously recorded as not found.

## EC access (mapped further)

The EC is reachable through `ec_probe` (based on `ec_sys`), and its fan and
temperature registers are identified and verified — see
[`ec-map.md`](ec-map.md). `nbfc` already drives the fan setpoints through the same
path, so the write half has a working reference.

Two corrections to the earlier map, both from a controlled thermal ramp:

- **`0x57` and `0x58` are CPU temperatures**, tracking `k10temp`'s `Tctl` within
a degree across a 72 → 85 °C ramp. `0x48` is a third, slower-moving sensor.
- **The rest of the `0x40`–`0x49` row is not.** `0x40`, `0x42`, `0x44`, `0x46`
and `0x49` never moved under load. The earlier "plausible additional
temperatures" was too generous.

What was tested and **ruled out**: the EC does not hold the SMU power limits.
Dumping the EC before and after a `ryzenadj` write, with a no-op control run to
account for telemetry drift, produces indistinguishable diffs — the limits live
in the SMU only. So the [platform profile
reset](#power-limits-what-resets-them-is-not-established) is not
the EC re-asserting a stored limit.

### The EFI variables that carry the setup

```bash
# the AMD PBS answers (skip the 4-byte NVRAM counter)
sudo dd if=/sys/firmware/efi/efivars/AMD_PBS_SETUP-a339d746-f678-49b3-9fc7-54ce0f9df226 \
        bs=1 skip=4 count=132 status=none | xxd

# the same structure, in the flash chip, in clear, twice
sudo python3 -c "
import mmap,os
fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
d=mmap.mmap(fd,0x1000000,offset=0xff000000,access=mmap.ACCESS_READ)
for off in (0x7c0e17,0x7e0e17): print(hex(off), bytes(d[off:off+15]))"
# -> 0x7c0e17 b'AMD_PBS_SETUP'   /   0x7e0e17 b'AMD_PBS_SETUP'  (differ at byte 22)
```

Details, and the rest of the store, in [`efi-nvram.md`](efi-nvram.md).

---

See also [Boot tuning](https://github.com/ismail-bahloul/dotfiles/blob/main/docs/boot-tuning.md)
in the dotfiles repository, for the boot-time work and what is still on the table
there.
