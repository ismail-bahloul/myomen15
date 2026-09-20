# HP OMEN 15-en1xxx — machine exploration

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

How far can one laptop actually be controlled? This repository documents every
layer of this machine I managed to reach, every layer that refused — and how each
conclusion was measured. It is a running log, not a tutorial: the wrong turns are
kept, because the method is the point.

**Machine:** HP OMEN Laptop 15-en1037nf (product 4J8B4EA) · AMD Ryzen 7 5800H
(Cezanne) · BIOS AMI F.30 (2025-10-21) · NVIDIA RTX 3070 Mobile · dual-boot
CachyOS + Windows 11. The serial number is deliberately not recorded here.

## The control surface

Everything measured on this machine, by domain. `✅` doable · `🟡` partial or
read-only · `⚪` no effect · `🔴` refused. Each row links its evidence.

### CPU and SMU

| What | | Detail |
|---|---|---|
| Write power limits (STAPM / PPT / TDC / EDC / Tctl) | ✅ | via `ryzenadj`; they persist. A `platform_profile` write resets them — a watcher re-applies in 0.12 s |
| Read what the SMU is doing | ✅ | the PM table: 9 limits + 9 live values, in one `read()` → [`pm-table.md`](pm-table.md) |
| Per-core busy % and clock | ✅ | requested `0x3c0` / effective `0x3e0`, confirmed against `perf` to <0.3 % |
| Read raw SMN registers and the SMU mailbox | ✅ | `smn`, `mp1_smu_cmd`; `GetSmuVersion` round-trips → [`smu-raw.md`](smu-raw.md) |
| Write through the raw SMU layer | ✅ | two query commands sent and cross-checked, plus a real mutating write (`SetStapmLimit`, self-restoring) — the same command `ryzenadj` already sends, proven to be the same mailbox and the same effect; `smn` writes and unverified commands stay untouched → [`smu-raw.md`](smu-raw.md) |
| Undervolt / Curve Optimizer | 🔴 | the SMU refuses the whole OC/CO family on **both** OSes |
| MSR | 🟡 | `/dev/cpu/*/msr` → `EIO`, but that's Linux's own `msr` module allowlist — a raw `rdmsr` via CHIPSEC's kernel driver reads real values (`APIC_BASE`, `EFER`); does not reopen CO, which is SMU-gated → [`chipsec-recon.md`](chipsec-recon.md) |

### Embedded controller (EC)

| What | | Detail |
|---|---|---|
| Reach any EC byte | ✅ | **four** independent paths: `ec_sys`, `hp-wmi`, `H2RA`, and the firmware's `M040`/`M041` (verified 256/256) |
| Reach any I/O port | ✅ | `M31A`/`M319`, including SMM `0xB2` (untried) |
| Write EC registers | 🟡 | measured **per register**: `MBDC` holds, `SHEN`/`OCPC` revert in ~100–150 ms, `TAPM` never lands → [`ec-map.md`](ec-map.md) |
| Map the register file | ✅ | complete for behaviour — only **18 of 256** offsets ever change, and 16 are named |
| Performance mode (`OCPC` / `OCPS`) | 🟡 | readable; `OCPC` is EC-owned, `OCPS` takes a write with no observed effect |

### Firmware and BIOS

| What | | Detail |
|---|---|---|
| Read the BIOS settings | ✅ | plain EFI variables at runtime → [`efi-nvram.md`](efi-nvram.md) |
| Write the standard EFI globals | ✅ | `Boot####`, `BootOrder`, `Timeout`, `OsIndications`, … |
| Write the BIOS setup store | 🔴 | `EPERM` — efivarfs marks those inodes immutable |
| Unlock the hidden menus | 🟡 | `SmokelessUMAF` / `SREP`, **pre-boot only**; `Custom Core Pstates` stays empty |
| Modify or flash the firmware | 🔴 | HP Sure Start + a PSS/RSA signature. Definitive — but Sure Start is no longer just a name: the actual recovery volumes are unwrapped and their modules named → [`firmware-limits.md`](firmware-limits.md#two-of-the-four-encrypted-regions-were-compressed-not-encrypted) |
| The AMD CBS power menu | ⚪ | inert — it only seeds POST values the HP EC then overrides |
| TPM | ⚪ | `Hidden` — disabled, not detected at POST |

### Battery and power

| What | | Detail |
|---|---|---|
| Read the true design capacity | ✅ | EC `BADC` (70.9 Wh) vs `BFCC` (60.2 Wh); the OS only ever sees `BFCC` → [`battery-charge-control.md`](battery-charge-control.md) |
| Read the BIOS charge option | ✅ | `Adaptive Battery Extender`, one bit: `SHEN` (EC `0xC5` bit 7) — enabled here |
| Change it | 🔴 | EC-owned — a write is reverted in ~150 ms |
| Stop charging (`MBDC`) | 🟡 | writable and reversible, but **not a held cap** (100 % → 55 %, no plateau) |
| Kernel charge API (`charge_control_*`) | 🔴 | absent on this model |

### Thermal and fans

| What | | Detail |
|---|---|---|
| Read fan speed | ✅ | four independent paths, cross-checked to the RPM → [`h2ra-region.md`](h2ra-region.md) |
| Control the fans | ✅ | `nbfc` (EC setpoints), `hp-wmi` |
| Drive them through `H2RA` | ⚪ | a one-way publication — writes read back and do nothing |
| Read temperatures | ✅ | EC `0x57`/`0x58` track `Tctl`; `k10temp` |

### Keyboard and lighting

| What | | Detail |
|---|---|---|
| Keyboard RGB (4 zones) | 🔴 | the EC publishes the state in `H2RA`, but writes there — including the firmware's own `LM05` — change nothing |

### Memory and platform

| What | | Detail |
|---|---|---|
| Memory tuning (SPD profiles) | 🟡 | the firmware ships non-QVL profiles by part number, behind `AMD CBS > UMC` — BIOS-only |
| IOMMU / vfio | 🟡 | 24 groups, registered, nothing bound |
| SMBus / i2c busses | 🟡 | reachable, not scanned |

## The short version

| Question | Answer |
|---|---|
| Can I undervolt, or use Curve Optimizer? | **The SMU says no** — proven on both OSes. But an untested second road exists (`\AOD`, via SMM), which is what HP's own software uses. |
| Can I read what the SMU is actually doing? | **Yes.** The PM table decodes to 9 limits + 9 live values in one `read()`. |
| Can I read the BIOS settings from the running OS? | **Yes.** Plain EFI variables — and identical in the flash chip, twice. Writing them back is refused for the setup store, but the standard EFI globals *are* writable. |
| Can I talk to any EC register or I/O port? | **Yes.** The firmware ships a generic byte bridge (`M040`/`M041`/`M31A`/`M319`), verified 256/256 against `ec_probe`. |
| Can I cap battery charging? | **Yes — and it is already on.** The BIOS option is **`Adaptive Battery Extender`**: one EC bit, `SHEN` (`0xC5` bit 7), currently `1`. It works by lowering `BFCC`, the reported full capacity (85 % of the 70.9 Wh pack), so the OS cannot see it. Read it with the EC bridge or `\_SB.WMID.ABES`. The `MBDC` register is a *different* lever: it stops charging, it does not hold a level. |
| Can I control the keyboard lighting? | **No** — the EC publishes the state in `H2RA`, but writes there (including the firmware's own `LM05`) change nothing. |
| Can I set a power limit in the BIOS? | That setting is **inert**; the HP EC owns those values. |
| Do power limits written by the OS stick? | **Yes** — except a `platform_profile` write makes the EC re-apply its own. |
| Can I modify the BIOS? | **No** — HP Sure Start is active, and the payload is PSS-signed. |

## What is actually interesting here

Not the answers — those are small. What is interesting is that they are
*measured*, and that the wrong turns are kept, because that is where the method
is visible.

- **The same question went wrong twice, the same way.** Whether the EC reverts
  OS-written power limits was first answered "yes, periodically", then
  "no, only via `platform_profile`". Re-measuring it produced a *third* answer —
  the second one was itself an over-correction, and the mistake both times was
  reading a value without first setting a distinctive one. →
  [`firmware-limits.md`](firmware-limits.md)
- **A 5-minute blind spot, and a 0.1-second fix.** The profile could be clobbered
  and stay clobbered for minutes. inotify turned out to work on the sysfs
  attribute, so the machine now reacts to the write rather than polling for it.
  → [`evidence/power-profile-watch`](evidence/power-profile-watch)
- **A kernel panic this repo caused.** Chasing a read-back for the Curve
  Optimizer meant editing the `acpi_call` DKMS module; resizing its buffer
  panicked the machine (screen dead, Caps Lock blinking). It rolled back and
  nothing persisted, but it happened. → [`acpi-bridge.md`](acpi-bridge.md)
- **The Curve Optimizer gate is firmware-side, and proving it took more than
  trusting a tool.** UXTU on Windows *appears* to apply a CO offset — it updates
  its UI and looks like it worked. Its own diagnostic log records **20 failures
  out of 20** writes. The verdict came from probing the SMU directly, over the
  same access path and with the same message IDs the Linux side uses.
  → [`record/02-curve-optimizer-verdict-windows.md`](record/02-curve-optimizer-verdict-windows.md)
- **A benchmark "gain" that was never real.** The efficiency improvement
  originally measured was noise from thermal soak: the offset it was attributed
  to had never been applied. The run-to-run spread of *identical* configurations
  was ±3 % — the same size as the "effect".
- **A conclusion of mine was wrong, and an experiment said so.** I had concluded
  that the EC periodically rewrites OS-written power limits. A controlled A/B —
  ten minutes with the fan daemon running against ten minutes with it stopped —
  showed **zero** reverts in either condition, and pointed at a different trigger
  entirely. → [`firmware-limits.md`](firmware-limits.md)
- **What the firmware seeds at POST is observable**, by logging the limits in
  force *before* the OS writes anything. That is what proved the BIOS power
  setting does nothing.
- **The setup answers are readable while the machine runs.** They are ordinary EFI
  variables, and the same bytes are also sitting in the flash chip *in clear,
  twice* — outside the encrypted volumes. Diffing `Setup` against `SetupDefault`
  says this machine has **eleven** options off-default. → [`efi-nvram.md`](efi-nvram.md)
- **The PM table was readable the whole time.** `ryzen_smu` had been exposing 2372
  bytes of raw SMU state as a plain read-only file. It decodes to `float32` — nine
  limits and nine live values — and it settles a discrepancy this repo had left
  open: the "50 vs 54" puzzle was a misread of which field held which number.
  → [`pm-table.md`](pm-table.md)
- **A third way to read the fans, on a different mechanism entirely.** The DSDT
  declares a 4 KiB memory region at `0xfe700000`; `FS1H:FS1L` there is the CPU fan
  tacho, to the RPM, 5/5 samples. The EC and `hp-wmi` could in principle share a
  bug — a direct load cannot. → [`h2ra-region.md`](h2ra-region.md)
- **The battery "dead end" was not one — and the real cap turned out to be
  invisible.** "Charge thresholds unsupported" was true of the kernel surface and
  false of the firmware, but not in the way the DSDT first suggested. Writing
  `MBDC` stops charging and the pack then discharges (measured down to 55 %); it
  is reversible, but it holds no threshold. The cap that *does* hold is the BIOS
  "battery optimizer", which works by lowering `BFCC` — the reported full
  capacity, 85 % of the 70.9 Wh pack here. The DSDT feeds `BFCC` into both design
  and last-full, so no userspace tool can see it.
  → [`battery-charge-control.md`](battery-charge-control.md)
- **The firmware ships a generic EC/I-O bridge, and nothing uses it.** SSDT12
  declares `M040`/`M041` (read/write any EC byte) and `M31A`/`M319` (read/write
  any I/O port). Verified against `ec_probe`: **256 of 256 registers agree**.
  `M319` reaches I/O port `0xB2`, the AMD SMM channel. → [`acpi-bridge.md`](acpi-bridge.md)
- **The Curve Optimizer gate has an untested second road, with a catch.** The
  repo's central negative result — CO refused — was measured through the **SMU
  mailbox**, on both OSes. SSDT2 declares `\AOD` with a literal `Set Curve
  Optimizer` command that does **not** use the mailbox: it pokes SMM via I/O
  `0xB2`, the way HP's own software does. It may well be refused by the same SMU,
  but it has never been tried. → [`acpi-bridge.md`](acpi-bridge.md) §2
- **A crash that this repo caused, and kept.** Chasing a read-back for the above
  meant reading `\AOD`'s full state, which `acpi_call` truncates at 42 values.
  Enlarging that buffer means editing the `acpi_call` DKMS module — and doing so
  **panicked the machine** (screen dead, Caps Lock blinking). It rolled back on
  reboot and `pacman -Qkk` confirms nothing persisted, but it happened. The
  truncation stands, and the curve optimizer has no read-back here. →
  [`acpi-bridge.md`](acpi-bridge.md) §4
- **HP's performance mode, located.** The README listed it as "not found on the
  Linux side". It is in the EC: `OCPC` (0xBA) is the current profile, `OCPS`
  (0xBB) the maximum, and the DSDT maps 0–6 to dGPU power limits in mW. →
  [`acpi-bridge.md`](acpi-bridge.md) §3
- **The keyboard is 4-zone RGB and Linux exposes none of it.** `\_SB.WMID.LM03`
  writes the data (`H2RA` 0xEE3 / 0xEF0, 12 bytes each) and commits it. The
  control itself is inside the EC, and **writing `H2RA` has no effect on it**.
- **A control surface that looked open, and was not.** `H2RA` at `0xfe700000` is
  writable, and the firmware declares fan setpoints there (`SFS1`/`SFS2`) that it
  never writes — which looked like an unwired control. A controlled test on the
  keyboard backlight says otherwise: **writes there are ignored**, including via
  the firmware's own `LM05` method. `H2RA` is a one-way publication. That closes
  the hope of driving the fans through it. → [`h2ra-region.md`](h2ra-region.md)
- **The `EIO` on MSR reads was Linux, not this machine.** Getting CHIPSEC
  running at all meant patching its kernel driver for a renamed kernel API
  first — and once it ran, a raw `rdmsr` through it returned correct values
  (`APIC_BASE`, `EFER`) where `/dev/cpu/*/msr` had refused. The block was the
  Linux `msr` module's own allowlist, one layer above the chip. It does not
  reopen Curve Optimizer, which is gated somewhere else entirely (the SMU
  mailbox). → [`chipsec-recon.md`](chipsec-recon.md)
- **The raw SMU layer went from read to written, on purpose and in order.**
  Two query commands first (`GetPmTableVersion`, `GetDramBaseAddress`), each
  cross-checked against a value independent of the command itself, before a
  real mutating write: `SetStapmLimit`, sent from this repo's own script
  instead of `ryzenadj`, over the exact mailbox command `ryzenadj` already
  uses. Self-restoring, and separately confirmed reverted by the running
  `power-profile-watch` service on its own — the raw path and `ryzenadj`'s are
  provably the same mailbox. → [`smu-raw.md`](smu-raw.md)
- **"Encrypted" was half right, and the half that was wrong had a one-word
  cause.** Two of the four firmware regions flagged at entropy ≈ 8.0 turned out
  to be EFI/Tiano-*compressed*, not encrypted — `uefiextract` was failing
  silently for want of `TianoCompress` on `PATH`, a real EDK2 tool, not an
  exotic one. Built from public source in about ten seconds
  (`evidence/bios-unwrap.sh`), it unwraps the exact 16 MiB file this machine
  already had cached at `/boot/EFI/HP/BIOS/Current/088D1.bin` into 684 named
  modules — including, for the first time, actual named PEI/DXE/SMM code for
  Sure Start's A/B recovery scheme (`HPCrisisRecovery`, `AmdCpmABRecoveryPeim`,
  `AmdPspSmmV2`, …). The other two regions are still genuinely high-entropy and
  still unread — this didn't open the whole image, and it didn't touch the
  PSS/RSA signature that still blocks writing. →
  [`firmware-limits.md`](firmware-limits.md#two-of-the-four-encrypted-regions-were-compressed-not-encrypted)
- **A method I proposed, and the experiment that killed it — then the same
  data, read correctly, is what made it work.** Toggle one BIOS option, diff
  the tables, name the offset — that was the plan. A three-way TPM toggle
  (`off` → `on` → `off` → `Hidden`) showed the naive form does not work: saving
  the setup moves bytes *whatever* you changed, and `SetupDefault` itself
  drifts. This page also said 6/7/9/221 "passed" a two-leg filter — backwards;
  they never had a revert leg to pass. Actually running the filter, on the one
  triple that *is* a real out-and-back (`before-tpm → after-tpm →
  after-disable-tpm`), names two things at once: `Setup` offsets 3-4, and —
  new — `HPSetupData` offsets 94-95 tracking them in lockstep, a second
  variable confirming the same bit. → [`efi-nvram.md`](efi-nvram.md) §7
- **A hidden memory-tuning table names a module this machine does not have.** The
  firmware carries whole SPD profiles keyed by part number; one of them is for a
  Micron `8ATF1G64HZ-2G3B1`, which is not in either slot. So the "no memory
  tuning" dead end was a *QVL* dead end, not a firmware one.
- **Two EC temperatures, and a slow third.** A controlled thermal ramp
  (idle → 16 threads → idle) confirmed `0x57` and `0x58` track `k10temp`'s
  `Tctl`, and killed the guess that the whole `0x40`-`0x49` row was a bank of
  sensors: only `0x48` moves there. A later, *longer* load showed `0x49` moves
  too (`0x38` -> `0x3A`) — a slow channel, not a constant. → [`ec-map.md`](ec-map.md)

## Open fronts

What has not been tried yet, ordered by how much it would unlock:

- **Raw `smn` writes.** A direct address-value poke into the SoC's internal
  fabric, with no per-command validation the way a mailbox message gets — the
  one part of the raw SMU layer still genuinely untouched, now that the
  mailbox itself has been both read and (carefully) written. →
  [`smu-raw.md`](smu-raw.md)
- **Name the remaining setup offsets.** Two of the eleven are settled (offset 9
  is TPM-adjacent noise, not TPM itself; offsets 276-284 are confirmed
  untouched by the TPM toggle). Nine remain (`21, 22, 23, 174, 244, 276, 278,
  280, 284, 316`), and naming them needs the two-leg method of
  [`efi-nvram.md`](efi-nvram.md) §7 — now with tooling for it,
  `setupdiff.py twoleg`: two reboots per option.
- **`postcode`.** `hp-wmi` exposes a firmware POST code that reads a stable
  `0x70`. Read, but not decoded any further.
- **The memory side.** The firmware's own SPD table names a module that is not
  installed; the lever is `AMD CBS > UMC Common Options`.
- **What `ROMPROTECT2` actually does.** CHIPSEC reads one FCH write-protect
  register as set (`WriteProtect=1`, a narrow, ambiguous range) — a real,
  measured data point, but not yet correlated to any actual write behaviour,
  and not the same mechanism as the PSP-enforced Sure Start signature check.
  → [`chipsec-recon.md`](chipsec-recon.md)
- **Closed, do not chase:** Curve Optimizer, BIOS flashing, EFI setup-variable
  writes (`EPERM`). MSR reads are open (raw `rdmsr` works via CHIPSEC) but lead
  nowhere new — CO stays SMU-gated regardless.

## What is in this repository

| Path | What it is |
|---|---|
| [`firmware-limits.md`](firmware-limits.md) | The living reference — current conclusions only: BIOS power semantics, the Curve Optimizer gate, Sure Start, what resets an OS-written profile, and what is unsupported. |
| [`acpi-bridge.md`](acpi-bridge.md) | The SSDTs decoded: the firmware's generic EC/I-O bridge, the `\AOD` overclocking interface, and HP's performance-mode selector. |
| [`access-surface.md`](access-surface.md) | Everything reachable on this machine, everything measured as blocked, and what is reachable but not yet used. |
| [`pm-table.md`](pm-table.md) | The SMU PM table decoded: 9 limits + 9 live values as `float32`, the "50 vs 54" question it settles, and the per-core groups (busy %, and the clocks `0x3c0`/`0x3e0` confirmed against `perf`). |
| [`smu-raw.md`](smu-raw.md) | The raw SMU/SMN layer under `ryzenadj`: the nodes, Cezanne's mailbox addresses, an end-to-end `GetSmuVersion` from userspace, and why the write path is left untouched so far. |
| [`ec-map.md`](ec-map.md) | The mapped embedded-controller registers (fans, three temperatures), how each was verified, and what is not in the EC. |
| [`h2ra-region.md`](h2ra-region.md) | The `H2RA` memory region at `0xfe700000` — a third, independent path to the fan tachometers. |
| [`battery-charge-control.md`](battery-charge-control.md) | `GBCC` / `SBCC` / `MBDC` decoded from the DSDT, the measured proof the charge cap works and is reversible, and the EC capacity registers (`BADC`/`BFCC`) that explain why the OS cannot see the design capacity. |
| [`efi-nvram.md`](efi-nvram.md) | The EFI variable store: the BIOS answers as readable variables, the clear-text copies in the flash, and what the image does and does not expose. |
| [`chipsec-recon.md`](chipsec-recon.md) | Talking to the chip directly instead of through HP's software: fixing CHIPSEC's kernel driver for a newer kernel, what that shows about the MSR block, and a from-scratch AMD platform file that reads the FCH's own write-protect registers. |
| [`BIOS_arborescence_OMEN.md`](BIOS_arborescence_OMEN.md) | The full SmokelessUMAF menu tree, transcribed from the 133 photos. |
| [`record/`](record/) | The point-in-time investigation, kept as written. Start with the Linux report, then the Windows verdict. |
| [`evidence/`](evidence/) | Tooling and raw data: `smu.cs`, `load.cs`, the 26 benchmark runs, the two A/B CSVs, `setupdiff.py`, `tpmstate.py`, `batterycc.py`, `ecbridge.py`, `omenkbd.py`, `omenwatch.py`, `aodread.py`, plus `omenmon.py` (live power/thermal TUI), `limitwatch.py` (what resets the SMU limits), `pmtable-cores.py` (the per-core PM table groups), `smuraw.py` (SMN reads, query-class SMU mailbox commands, and one self-restoring mutating write), `batterycctl.py` (battery charge control), `ecsweep.py` (EC dump/diff), `chipsec-km-msr-api.patch` (the driver fix for newer kernels), `chipsec-cezanne.xml` (the AMD platform file), `chipsec-recon.log` (raw command output), `bios-unwrap.sh` (unwraps the AMI update capsule and parses the result), and `bios-image-report.txt` (the full 684-file structural report it produces). |
| [`evidence/power-profile-watch`](evidence/power-profile-watch) | Re-applies the power profile the instant `platform_profile` is written — the 5-minute re-apply window, closed. |
| [`img_smokelessUMAF/`](img_smokelessUMAF/) | The 133 photographs of the SmokelessUMAF menus, kept as primary evidence. |

## Caveats

- **One machine.** This is the behaviour of one 15-en1xxx on BIOS F.30. Other
  revisions, or a BIOS update, can differ.
- **The OC/CO gate is HP's, not AMD's.** That is consistent with the missing BIOS
  menu, the empty `Custom Core Pstates` form and Sure Start — but the mechanism
  behind the refusal is not known. Only the refusal is.
- **A string missing from the flash image proves nothing — for the part that's
  still opaque.** Two of the four regions once called "encrypted" were
  compressed, not encrypted — a missing tool (`TianoCompress`), not an
  unreadable image; fixed, and now fully parsed by name →
  [`firmware-limits.md`](firmware-limits.md#two-of-the-four-encrypted-regions-were-compressed-not-encrypted).
  Two others (`0x1e4000`, `0xa00000`) really are still high-entropy and
  unparsed. For those, absence of a name still only means it is not *in the
  clear*, and any claim drawn from searching that part of the image carries
  that limit.
- **"It was written" is not "it took effect".** One finding in here is a write
  that succeeds and echoes a constant back, which is why every claim about a
  write is backed by a read-back.

## Resources

- HP product support for this SKU (product `4J8B4EA`, model id `2100371391`):
  drivers, BIOS updates, and the maintenance and service guide —
  <https://support.hp.com/my-en/product/troubleshooting/omen-15.6-inch-gaming-laptop-pc-15-en1000/model/2100371391>

## Related

The configuration all of this was measured on — the CachyOS setup, VFIO GPU
passthrough, pro-audio chain, and the boot tuning — lives in
[ismail-bahloul/dotfiles](https://github.com/ismail-bahloul/dotfiles).
