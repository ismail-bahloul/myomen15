# AOD_SETUP — the variable that gates the whole `\AOD` SMM dispatcher

`acpi-bridge.md` left one thread open: `AodSmmSsp` references an EFI variable
named `AOD_SETUP` twice, which does not exist on this machine, and was "not
chased further" in that session. This closes that thread and turns it into a
concrete, reversible experiment.

**Follow-up (static IFR):** `AOD_SETUP` is not an opaque buffer — it is the
**AMD Overclocking menu** (207 options: PBO, PPT/TDC/EDC, custom CPU/GFX
freq/voltage, Curve Optimizer, memory timings), and it is read **at POST** by
`AodPei`, not only by the SMM handler. That reframes this experiment: it opened
the *gate* with an all-zero buffer and tested the *runtime command path*, but
never the *POST-time application of the menu's values*. →
[`../ifr-static/aod-setup.md`](../ifr-static/aod-setup.md).

## Result

**The gate was not the blocker.** `AOD_SETUP` was created for real (1020
zero bytes, `NV+RT+BS`, confirmed both by `dmpstore -s`'s readback --
`DataSize = 0x3FC` -- and from Linux at
`/sys/firmware/efi/efivars/AOD_SETUP-5ed15dc0-edef-4161-9151-6014c4cc630c`,
1024 bytes = 4-byte efivarfs attribute header + 1020), then
`retest-ppt-via-aod.sh` reran the exact `Set PPT Limit` test from
`aod-power-limit-probe.txt`:

```
baseline:              PPT LIMIT FAST = 42.000   PPT LIMIT SLOW = 35.000
\AOD.AM05 (25000 mW):  PPT LIMIT FAST = 42.000   (unchanged)
ryzenadj control:      PPT LIMIT FAST = 22.000   (moved -- instrument is live)
```

No hang, no crash, clean restore. This settles the question the gate had left
open: with the buffer correctly sized this time, the command chain almost
certainly ran for real (rather than bailing at the top like every earlier
attempt did) -- and the SMU still didn't move. `firmware-limits.md`'s
"live but inert" conclusion for the `\AOD` road now stands on firmer ground:
it was never the missing variable, the road itself just doesn't reach the
SMU for this class of command. `AOD_SETUP` should be reverted with
`revert-aod-setup.nsh` (`dmpstore -d`) to restore the pre-experiment state --
nothing further is gained by leaving it in place.

## What was found (the investigation that led to the test above)

## What was found

Re-disassembling `AodSmmSsp.pe32` (still on disk at
`/home/iswad/DATA/bios_extract/work/smmre/`, radare2 6.2.0, `-A`) located both
`GetVariable("AOD_SETUP", ...)` call sites precisely:

- The GUID, read directly out of `.data @ 0x15000` (the literal `lea rdx,
  section..data` argument at both call sites): **`5ED15DC0-EDEF-4161-9151-6014C4CC630C`**.
- The **first** call site, at `0x12f93`/`0x12f9a`, is not buried inside the
  command chain — it is the first thing `fcn.00012f18` does after locating the
  SMM variable protocol, *before* the `cmp ecx, 0x100030/0x100031/0x100032...`
  chain (`Set PPT Limit`, `Set Curve Optimizer`, ...) that `acpi-bridge.md`
  already mapped. If the call fails (`js 0x146da` — sign bit set, which is
  true for both `EFI_NOT_FOUND` and `EFI_BUFFER_TOO_SMALL`), execution jumps
  straight to the function epilogue. **No command is ever dispatched.**

```
0x00012f93   lea rdx, section..data          ; &guid, 0x15000
0x00012f9a   lea rcx, str.AOD_SETUP          ; "AOD_SETUP"
0x00012fa1   call qword [rax]                ; SmmVariable->SmmGetVariable
0x00012fa3   mov rdi, rax
0x00012fa6   test rax, rax
0x00012fa9   js 0x146da                      ; <-- bails out of the ENTIRE handler
```

Since `AOD_SETUP` does not exist in `/sys/firmware/efi/efivars/` (confirmed:
it is not in `efi-nvram.md`'s catalogue), this call fails today, every time.

## Why this matters

`firmware-limits.md#the-second-road-measured-it-is-inert` concluded the
`\AOD` road is "live but inert" for `Set PPT Limit` — the command reached the
firmware (`\AOD.AM01`/`AM03` answer) but never moved the SMU's live PPT limit,
unlike the same value through `ryzenadj`. That conclusion was reached without
knowing about this gate. Two different explanations were previously
indistinguishable and are now separable:

1. **The road reaches the firmware but the firmware's write to the SMU is
   itself refused or misrouted** (the original reading).
2. **The command chain never runs at all**, because the handler exits at the
   top on the missing `AOD_SETUP` check — in which case "inert" so far means
   nothing more than "gate closed," and the PPT/CO command logic downstream
   has never actually been exercised.

Creating `AOD_SETUP` and rerunning the *exact same, already-instrumented* PPT
test is the one experiment that tells these apart.

## The variable's binary format

`dmpstore`'s `.dat` container format was reverse-engineered from
`evidence/uefi-shell-probe/Setup-preloop.dat` (a known-good dump) and
confirmed by rebuilding that exact 366-byte file byte-for-byte from its own
fields — see `build_aod_setup_dat.py`'s self-check. Layout:

```
NameSize   u32 LE   -- bytes of the UTF-16LE name, incl. null terminator
DataSize   u32 LE
Name       NameSize bytes, UTF-16LE, null-terminated
Guid       16 bytes (Data1 LE4, Data2 LE2, Data3 LE2, Data4 8 bytes as-is)
Attributes u32 LE
Data       DataSize bytes
Crc32      u32 LE, binascii.crc32 over every byte before it
```

`build_aod_setup_dat.py` writes a fresh record for `AOD_SETUP` — attributes
`0x7` (`NV|BS|RT`, the same class every other setup-family variable already
uses), **1020 zero bytes**.

### Why 1020 bytes, and not something smaller (this was wrong on the first pass)

The first version of this script used a single `0x01` byte, on the reasoning
that `GetVariable` only needs to succeed and the content shouldn't matter for
the gate check. That reasoning stopped one step too early. Continuing the
trace past the gate (`0x12faf` onward) found:

- On a successful read, the handler does
  `SmmAllocatePool(EfiRuntimeServicesData, DataSize, &ptr)` — sizing its
  **persistent config buffer to `AOD_SETUP`'s own `DataSize`** — then
  `CopyMem(ptr, GetVariable's temp buffer, DataSize)`, caching `ptr` in a
  global (`0x15788`).
- That cached pointer is then reloaded and **written into at fixed offsets in
  nearly every command branch** of the dispatcher — a static scan of the
  whole 6 KB function (`/tmp/aod_full.asm` via `r2 -A -c 'pD 6109 @
  0x12f18'`, then grepped for every `[reg + 0x..]` access on a register last
  loaded from `0x15788`) found writes as high as **`+0x234`**
  (`mov byte [rax + 0x234], cl` at `0x1466b`, confirmed by hand).

So a **1-byte `AOD_SETUP` would allocate a 1-byte SMRAM pool buffer, and the
very first `\AOD` command run afterward would write past the end of it** —
an SMM heap overflow, categorically worse than the already-traced
Curve-Optimizer index bug (which stayed inside an 8716-byte pool). This is
exactly the risk that motivated tracing further before touching real
hardware.

The fix is bounded on *both* sides, and both bounds are measured, not
guessed:

- **Lower bound:** must clear every offset found, `0x234` being the highest
  — so anything meaningfully above `0x235` is safe from that angle.
- **Upper bound:** the *initial* `GetVariable` call (the gate itself) reads
  into a fixed **0x3fc (1020)**-byte stack buffer. A `DataSize` larger than
  that returns `EFI_BUFFER_TOO_SMALL`, which fails the exact same sign-bit
  check as `EFI_NOT_FOUND` (`js 0x146da`) — an oversized `AOD_SETUP` would
  fail the gate it's meant to open, right back to square one.

1020 zero bytes sits at the top of that window: far past every offset seen
(more than 700 bytes of margin over `0x234`, in case the static scan missed
something), and exactly at the read cap. Zero-filled rather than patterned,
so any command that reads a field from this buffer before writing it sees a
consistent, inert `0`.

**Caveat kept explicit:** the offset scan was a heuristic register-tracking
pass over one disassembly listing, not a full data-flow proof — it can miss
an offset if a compiler-introduced code path moves the cached pointer
through a register the script didn't track from the right instruction. 1020
bytes is a comfortable margin over everything actually observed, not a
mathematical guarantee.

## Plan (mirrors `uefi-shell-probe`'s method — rehearse before touching real firmware)

1. **QEMU + OVMF first.** Build a throwaway OVMF vars store, boot
   `Shell_Full.efi`, create an arbitrary variable with a non-default GUID via
   a hand-built `.dat`, confirm `-l`/`-s`/`-d` all behave as expected
   (`uefi-shell-probe/README.md` §4 already lists the four mistakes made
   doing this the first time — repeat that discipline here, not from memory).
2. **Build the real file:**
   ```
   python3 build_aod_setup_dat.py -o aod-setup-create.dat
   ```
3. **Copy to the USB key** (same key/layout as `uefi-shell-probe`):
   ```
   sudo cp aod-setup-create.dat /mnt/usb/aod-setup-create.dat
   sudo cp create-aod-setup-test.nsh /mnt/usb/create-aod-setup-test.nsh
   sudo cp revert-aod-setup.nsh /mnt/usb/revert-aod-setup.nsh
   ```
4. **Boot the USB key**, at the `FS1:\>` prompt run `create-aod-setup-test.nsh`.
   Bring back `dumps\aod-setup-create-result.txt` and
   `dumps\AOD_SETUP-after-create.dat`.
5. **Reboot into Linux** and run:
   ```
   sudo ./retest-ppt-via-aod.sh
   ```
   This automates the *already-documented* PPT test verbatim
   (`evidence/aod-power-limit-probe.txt`'s "Reproducing" section): checks
   `AOD_SETUP` is visible in efivarfs, stops `power-profile-watch` (it
   reapplies the profile every 1 s and would mask both writes), records the
   baseline PPT, sends `\AOD.AM05 {Set PPT Limit, 25000 mW}`, records PPT
   again, runs the `ryzenadj --fast-limit=22000` control to prove the
   instrument is live, prints a verdict, and restores
   `power-profile.service`/`power-profile-watch` in a trap so it runs even if
   something above it fails. Full transcript saved to
   `ppt-retest-<timestamp>.log`.
   - **PPT moves this time** -> the gate was the real blocker; the road can
     drive the SMU after all, and a Curve Optimizer write down this path
     becomes a meaningfully different experiment than before (still with no
     read-back, still worth thinking hard about before trying).
   - **PPT still doesn't move** -> the original "inert" conclusion stands on
     firmer ground: the command chain does run now, and still doesn't reach
     the SMU.
6. **Revert either way**, from the USB key: run `revert-aod-setup.nsh`, which
   deletes `AOD_SETUP` (`dmpstore -d`) and confirms with `dmpstore -all`.

## Risk, honestly

Creating `AOD_SETUP` itself (step 4) is low-risk: it's the same `SetVariable`
mechanism already proven to work and revert cleanly on `Setup`'s TPM bit, on
a variable nothing reads at POST — only `AodSmmSsp`'s SW SMI 0xB9 handler
touches it, and only when something calls `\AOD` from a running OS. Sizing
it at 1020 zero bytes (see above) specifically closes the SMRAM heap-overflow
risk the first draft of this experiment had: every write offset found by
static analysis (`+0x234` max) lands well inside that buffer now.

The residual, un-eliminated risk is entirely in **step 5** — the PPT-limit
retest is the first time this dispatcher has ever run its real command logic
on this machine (every earlier attempt bailed at the gate). The buffer-size
question is closed, but the *arithmetic and control flow* of the individual
command handlers (bounds checks, whether any of them dereference a field of
this buffer as if it always holds a prior valid value, etc.) was not fully
audited this session — only the Curve Optimizer branch got that treatment
previously (`acpi-bridge.md`, found safe), and the PPT branch (`R23B`,
`MBCB=0x0010000B`) wasn't. Worst case if something in that class of code is
wrong: a hard hang requiring a forced power-cycle (SMM runs above the OS, so
a bad access there can't be caught by anything above it) — not a flash write,
since nothing traced so far touches the flash chip or the boot-critical
volumes, only ACPI NVS-backed memory and this new SMRAM pool allocation, both
of which are reinitialized on the next boot regardless of what happens to
them mid-session. Sensible precautions for step 5: on AC power, nothing
unsaved open, and treat a hang as "power-cycle and move on," not as something
to debug live.
