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
| Write the BIOS setup store | 🟡 | `EPERM` under Linux (`efivarfs` marks those inodes immutable), but a direct `SetVariable` from the real UEFI Shell **succeeds** — the lock is Linux's, not the firmware's → [`firmware-limits.md`](firmware-limits.md#correction-the-setup-lock-is-linuxs-not-the-firmwares) |
| Unlock the hidden menus | 🟡 | `SmokelessUMAF` / `SREP`, **pre-boot only**; `Custom Core Pstates` stays empty |
| Modify or flash the firmware | 🔴 | HP Sure Start + a PSS/RSA signature. Definitive — but Sure Start is no longer just a name: the actual recovery volumes are unwrapped and their modules named → [`firmware-limits.md`](firmware-limits.md#three-of-the-four-encrypted-regions-are-now-identified) |
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

### Discrete GPU (NVIDIA)

| What | | Detail |
|---|---|---|
| **Lock the GPU clock** | ✅ | `nvidia-smi --lock-gpu-clocks=min,max`; **measured** — 80 W → 41 W under load at a 1000 MHz cap → [`dgpu-control.md`](dgpu-control.md) |
| Lock the memory clock | ✅ | `nvidia-smi --lock-memory-clocks` |
| Set the power limit | 🔴 | `nvidia-smi -pl` → *not supported*; on Windows Afterburner's Power Limit slider is **greyed out** too, so the refusal is the vBIOS's, not the OS's |
| Clock offsets (the curve) | 🟡 | Linux: attributes read (−1000…+1000 MHz / −2000…+6000), writes refused (no `Coolbits`, Wayland). Windows: the memory offset works, the **core offset silently does nothing** → [`dgpu-windows-undervolt.md`](dgpu-windows-undervolt.md#result-measured-2026-09-24) |
| Voltage / V/F curve | 🔴 | not exposed — this is an **underclock**, not an undervolt. Neither OS has a voltage lever: Linux exposes no field, and Afterburner's is greyed out in all four unlock modes. Its V/F curve editor *does* bind, but as a clock clamp: 670 MHz still costs 69 W → [`dgpu-windows-undervolt.md`](dgpu-windows-undervolt.md) |

## The short version

| Question | Answer |
|---|---|
| Can I undervolt, or use Curve Optimizer? | **The SMU says no** — proven on both OSes. The second road (`\AOD`, via SMM) was then tested with a power-limit lever and is inert. |
| Can I read what the SMU is actually doing? | **Yes.** The PM table decodes to 9 limits + 9 live values in one `read()`. |
| Can I read the BIOS settings from the running OS? | **Yes.** Plain EFI variables — and identical in the flash chip, twice. Linux refuses to write the setup store back (`efivarfs` marks it immutable), but a direct `SetVariable` from the real UEFI Shell accepts it — the lock is Linux's, not the firmware's. |
| Can I talk to any EC register or I/O port? | **Yes.** The firmware ships a generic byte bridge (`M040`/`M041`/`M31A`/`M319`), verified 256/256 against `ec_probe`. |
| Can I cap battery charging? | **Yes — and it is already on.** The BIOS option is **`Adaptive Battery Extender`**: one EC bit, `SHEN` (`0xC5` bit 7), currently `1`. It works by lowering `BFCC`, the reported full capacity (85 % of the 70.9 Wh pack), so the OS cannot see it. Read it with the EC bridge or `\_SB.WMID.ABES`. The `MBDC` register is a *different* lever: it stops charging, it does not hold a level. |
| Can I control the keyboard lighting? | **No** — the EC publishes the state in `H2RA`, but writes there (including the firmware's own `LM05`) change nothing. |
| Can I set a power limit in the BIOS? | That setting is **inert**; the HP EC owns those values. |
| Do power limits written by the OS stick? | **Yes** — except a `platform_profile` write makes the EC re-apply its own. |
| Can I modify the BIOS? | **No** — HP Sure Start is active, and the payload is PSS-signed. |
| How far below the OS can I read? | **All the way down** — MSRs, the SMN bus and the FCH write-protect registers all read with stock tools, no CHIPSEC. But **SMM is locked** (`SmmLock=1`) and its RAM is hidden. → [`msr-and-smm.md`](msr-and-smm.md) |
| Can I undervolt the GPU? | **No — on either OS.** Linux exposes no voltage field at all, and the Windows trip closed the last hope: Afterburner's Core Voltage is greyed out in all four unlock modes, and its V/F curve editor acts as a **clock clamp, not a voltage map** (670 MHz still costs 69 W, against 1000 MHz at 41 W through Linux's clock lock). → [`dgpu-control.md`](dgpu-control.md) |

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
- **An SMRAM heap overflow that was caught before it ran, not after.** Closing
  the `AOD_SETUP` question (a variable gating the whole `\AOD` SMI dispatcher)
  meant creating that variable for real. The first draft sized it at 1 byte;
  tracing what the handler does with it further showed it allocates its
  config buffer to that exact size, then writes into it at offsets up to
  `0x234` regardless — a 1-byte variable would have overflowed a live SMRAM
  pool allocation the first time any `\AOD` command ran afterward. Sized
  correctly (1020 zero bytes, bounded on the other side by the gate's own
  read buffer), the real test ran clean. →
  [`evidence/aod-setup-probe/README.md`](evidence/aod-setup-probe/README.md)
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
- **The setup store's lock is Linux's, not the firmware's — and a real
  value change, not just a no-op, checks out three independent ways.**
  `efivarfs` marking `Setup` immutable had been read as the machine
  refusing the write. It doesn't: a direct `SetVariable` from the real
  UEFI Shell writes `Setup` back with its own bytes and succeeds. Pushed
  further — flipping the TPM enable bit (`Setup` offsets 3-4) to a
  genuinely different value — the change survived multiple reboots into
  different environments, the native BIOS menu's own "Enable" action
  produced the identical bytes at the identical offsets, and Linux saw a
  real effect (`/dev/tpm0` appeared, `tpm_crb_acpi` bound). Reverting it
  cleanly took a second attempt too: the first revert file replayed a
  stale snapshot and would have overwritten an unrelated menu change made
  in between. →
  [`firmware-limits.md`](firmware-limits.md#correction-the-setup-lock-is-linuxs-not-the-firmwares)
- **A second named offset, and a cleaner two-leg result than the TPM's.**
  Toggling `AMD PBS > USB Camera Enable` names `AMD_PBS_SETUP` offset 82 —
  `01 -> 00 -> 01`, zero noise offsets on either leg, unlike the TPM
  experiment's five. The bit is real and clean; what it disables in
  hardware isn't confirmed — the built-in webcam still enumerates in
  `lsusb` after setting it to `Disabled`. → [`efi-nvram.md`](efi-nvram.md) §8
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
- **The Curve Optimizer gate's "second road" was tested, and it is inert.** The
  repo's central negative result — CO refused — was measured through the **SMU
  mailbox**, on both OSes. SSDT2 declares `\AOD` with a literal `Set Curve
  Optimizer` command that does **not** use the mailbox: it pokes SMM via I/O
  `0xB2`, the way HP's own software does. Driving that same road with a lever
  whose effect is independently known — a power limit — moved nothing, while
  `ryzenadj` moved the same value instantly (and the `power-profile-watch`
  service had to be stopped, or it reverted both writes before the read). →
  [`acpi-bridge.md`](acpi-bridge.md) §2
- **The Curve Optimizer branch inside `AodSmmSsp` was disassembled, and a real
  candidate bug turned out not to be one.** Tracing the SMI handler's own
  command dispatcher (no decompiler — `r2ghidra` doesn't build against this
  `radare2` version, so this is raw `radare2` disassembly) found the `Set
  Curve Optimizer` branch decoding a caller-controlled value with one masked
  field (the core index) and one **unmasked** field used as an array index —
  a real asymmetry. Tracing where that index's target buffer (`AODT`) actually
  comes from, in the companion `AodDxe` module, found a genuine
  `AllocatePool(EfiACPIMemoryNVS, 0x220C, ...)` matching the DSDT's declared
  region exactly — which means the worst case for the unmasked index still
  lands inside the allocated buffer. Found, traced, closed: not an
  out-of-bounds write. → [`acpi-bridge.md`](acpi-bridge.md#the-curve-optimizer-branch-itself-traced--and-the-aodt-allocation-confirmed)
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
- **`H2RA`'s "fan curve table" is static, and `FMR1`/`FMR2` are not duties.** A
  fan-setpoint sweep showed the two `18 18 1b 1d 1f 22 28 2a` runs and the two
  `1a 1b 1f 26 28` runs never move with fan speed — they are the firmware's
  **declared** curves (`24 24 27 29 31 34 40 42` % and `26 27 31 38 40`), so
  `FMR1`/`FMR2` are the top of the curve, not live registers. Only the
  tachometers track the fans. → [`h2ra-region.md`](h2ra-region.md)
- **The `EIO` on MSR reads was Linux, not this machine.** Getting CHIPSEC
  running at all meant patching its kernel driver for a renamed kernel API
  first — and once it ran, a raw `rdmsr` through it returned correct values
  (`APIC_BASE`, `EFER`) where `/dev/cpu/*/msr` had refused. The block was the
  Linux `msr` module's own allowlist, one layer above the chip. It does not
  reopen Curve Optimizer, which is gated somewhere else entirely (the SMU
  mailbox). → [`chipsec-recon.md`](chipsec-recon.md)
- **...and then the "allowlist" was wrong too — MSR reads were never blocked.**
  `0x1a0` is `IA32_MISC_ENABLE`, an **Intel** MSR this AMD part does not have,
  so the read faulted and returned `EIO` — the same reason a nonsense MSR does.
  Every valid AMD MSR reads straight through the stock `/dev/cpu/N/msr`, no
  CHIPSEC. With that, the deepest layer answers for the first time: `HWCR`
  says **`SmmLock=1`** (ring −2 is sealed), `SMM_ADDR` places TSEG at
  `0xBE000000` (32 MB, confirmed by `/proc/iomem`), and the SMRAM pages read
  `0xFF` — visible in the map, unreadable in content. →
  [`msr-and-smm.md`](msr-and-smm.md)
- **The SMN bus was reachable without the driver all along.** The AMD SMN
  indirect window is just PCI config `0xB8`/`0xBC` on the root complex, so
  `setpci` reads SMN with no `ryzen_smu` — cross-checked 1021/1024 against the
  sysfs node over the mailbox page (the 3 that differ are volatile, i.e. an
  SMN read is not always idempotent). → [`smu-raw.md`](smu-raw.md)
- **The two RAM modules are confirmed from their own SPD.** `ee1004` exposes
  both; they read `MT16ATF2G64HZ-3G2E1` (Micron, 16 GB, DDR4-3200, ×2), so the
  firmware's APCB table naming a Micron `8ATF1G64HZ-2G3B1` really is a profile
  for a module this machine does not have — the QVL dead end, at the source.
- **The AC frequency cap is *not* the efficiency win it first looked like.** A
  controlled joules-per-iteration run answered `record/03-open-questions.md` §3,
  then a re-run corrected it (the first was ~2× low): the 3.2 GHz cap is
  **efficiency-neutral** within noise (~+2 %) and costs ~9 % throughput, so its
  value is thermals and noise, not energy. 54 W buys ~7 % speed for **+26 %**
  energy per unit work. It is the *deeper* caps (2.1–2.7 GHz) where
  work-per-joule really rises. And the cap's cost is workload-shaped: **−21 %**
  on a single thread (three reps each, 417.7 vs 526.1 Mi/s), where it buys
  nothing, versus −8 % all-core. The fix is a **lower power cap, not a frequency
  cap** — 28 W with no cap matches the capped config's all-core heat and gives
  back the single-thread speed. A short burst (an app launch) costs the same
  either way (~10 W peak, ~60.5 °C), so the cap cannot be defended as "quieter
  bursts". The only thing the cap removal heats is a *sustained single thread*:
  **+9–13 °C and ~+500 rpm** on one busy core, while idle and all-core are
  unchanged. → [`efficiency.md`](efficiency.md)
- **The raw SMU layer went from read to written, on purpose and in order.**
  Two query commands first (`GetPmTableVersion`, `GetDramBaseAddress`), each
  cross-checked against a value independent of the command itself, before a
  real mutating write: `SetStapmLimit`, sent from this repo's own script
  instead of `ryzenadj`, over the exact mailbox command `ryzenadj` already
  uses. Self-restoring, and separately confirmed reverted by the running
  `power-profile-watch` service on its own — the raw path and `ryzenadj`'s are
  provably the same mailbox. → [`smu-raw.md`](smu-raw.md)
- **A response node that lies, and what lifting it showed.** The `ryzen_smu`
  sysfs node reports `0x01 OK` for a `Failed` — a driver bug: a non-OK code
  that arrives before the retry counter runs out falls through to `return OK`.
  Read from the rsp register over SMN instead, the Curve Optimizer gate gets a
  shape: the SMU answers `0xFE UnknownCmd` for deliberate garbage but `0xFF
  Failed` for `set-coall` / `set-coper` / `set-cogfx` — it *knows* the commands
  and refuses them on purpose. A firmware policy, not a missing command and not
  a transport. → [`smu-raw.md`](smu-raw.md)
- **"Encrypted" was mostly wrong, in two different ways.** Of the four firmware
  regions flagged at entropy ≈ 8.0: two (`0xb00000`, `0xef0000`) were
  EFI/Tiano-*compressed*, not encrypted — `uefiextract` was failing silently
  for want of `TianoCompress` on `PATH`, a real EDK2 tool, not an exotic one.
  Built from public source in about ten seconds (`evidence/bios-unwrap.sh`),
  it unwraps the exact 16 MiB file this machine already had cached at
  `/boot/EFI/HP/BIOS/Current/088D1.bin` into 684 named modules — including,
  for the first time, actual named PEI/DXE/SMM code for Sure Start's A/B
  recovery scheme (`HPCrisisRecovery`, `AmdCpmABRecoveryPeim`, `AmdPspSmmV2`,
  …). A third (`0xa00000`) is AMD's own PSP firmware directory — signed, not
  encrypted, a different format `uefiextract` was never going to parse; found
  by its `$PSP` magic bytes exactly `0x3F0000` before the *other* copy of that
  same directory, the identical offset that separates the two Sure Start
  volumes — the same A/B scheme, at both firmware layers. Only one region
  (`0x1e4000`) remains genuinely unread, and none of this touched the PSS/RSA
  signature that still blocks writing. →
  [`firmware-limits.md`](firmware-limits.md#three-of-the-four-encrypted-regions-are-now-identified)
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
- **The one lever beyond the CPU's gates is on the other GPU.** Everything
  CPU-side that could have been unlocked turned out gated in signed firmware.
  The dGPU is a different vendor and a different gate: its clock **is** lockable
  (`nvidia-smi --lock-gpu-clocks`), and — measured under a full load — a
  1000 MHz cap cut power from **80 W to 41 W**. It is an underclock, not an
  undervolt (Linux never exposes the voltage), but it is a real lever with no
  owner. → [`dgpu-control.md`](dgpu-control.md)

## Open fronts

A later read-only, autonomous pass closed several items this page had listed as
open: the MSR / SMM / FCH / SMN layers ([`msr-and-smm.md`](msr-and-smm.md)), the
i²c/SPD, IOMMU and ESRT surfaces (now "Done" in
[`access-surface.md`](access-surface.md)), and the joules-per-iteration question
([`efficiency.md`](efficiency.md)). What remains genuinely open is below — and
the rest is either a manual step (reboots, BIOS menus, a USB key) or a write
with no known-effect read-back to de-risk it.

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
  `setupdiff.py twoleg`: two reboots per option. A direct `SetVariable` on
  `Setup` from the UEFI Shell is now confirmed to work for a genuinely
  different value, not just a no-op (`firmware-limits.md`), so this could
  move to poking one offset at a time from a script instead of hunting for
  the right menu item to toggle — untried on an *unnamed* offset
  specifically, where (unlike the already-understood TPM bit) the effect
  of a given value isn't known ahead of time. → ready to run:
  [`setup-offset-naming.md`](setup-offset-naming.md) and
  `evidence/setup-poke.py` (builds the CRC-correct `.dat`)
- **`postcode`.** `hp-wmi` exposes a firmware POST code that reads a stable
  `0x70`. Read, but not decoded any further.
- **The memory side.** The firmware's own SPD table names a module that is not
  installed; the lever is `AMD CBS > UMC Common Options`.
- **What `ROMPROTECT2` actually does.** CHIPSEC reads one FCH write-protect
  register as set (`WriteProtect=1`, a narrow, ambiguous range) — a real,
  measured data point, but not yet correlated to any actual write behaviour,
  and not the same mechanism as the PSP-enforced Sure Start signature check.
  → [`chipsec-recon.md`](chipsec-recon.md)
- **A governor for the lever that has no owner.** The dGPU clock lock is real
  (`nvidia-smi --lock-gpu-clocks`) and the CPU side already has a governor
  (`power-profile-watch`) — the coherent move is **one** governor over the CPU
  power limits, the GPU clock, the fans and the profile, not three tools that
  ignore each other. → designed and implemented: [`governor.md`](governor.md)
  and `evidence/omen-governor`
- **`AOD_SETUP`.** An EFI variable name found hard-coded in `AodSmmSsp` (two
  `GetVariable` calls, both with correctly-checked `EFI_STATUS`), absent from
  `/sys/firmware/efi/efivars/` on this machine and not in `efi-nvram.md`'s
  catalogue. Not chased past finding it. → [`acpi-bridge.md`](acpi-bridge.md)
- **Closed, do not chase:** Curve Optimizer, BIOS flashing, EFI setup-variable
  writes (`EPERM`), the `\AOD`/SMM road (driven and inert above), and the
  Curve Optimizer branch's unmasked array index inside `AodSmmSsp` (traced to
  the confirmed `AODT` allocation size — stays in-bounds). MSR reads turned
  out never to have been blocked at all (the old `EIO` was an Intel-only MSR);
  they now read through the stock node, and what they show — `SmmLock=1`,
  TSEG/SMRAM sealed — is in [`msr-and-smm.md`](msr-and-smm.md). They still
  lead nowhere new for CO, which stays SMU-gated regardless.

## What is in this repository

| Path | What it is |
|---|---|
| [`firmware-limits.md`](firmware-limits.md) | The living reference — current conclusions only: BIOS power semantics, the Curve Optimizer gate, Sure Start, what resets an OS-written profile, and what is unsupported. |
| [`acpi-bridge.md`](acpi-bridge.md) | The SSDTs decoded: the firmware's generic EC/I-O bridge, the `\AOD` overclocking interface, and HP's performance-mode selector. |
| [`access-surface.md`](access-surface.md) | Everything reachable on this machine, everything measured as blocked, and what is reachable but not yet used. |
| [`msr-and-smm.md`](msr-and-smm.md) | The layers below the OS: MSR reads without CHIPSEC (and a correction to `chipsec-recon.md`), the SMM lock / TSEG / hidden-SMRAM state, the FCH write-protect registers, and the SMN-over-PCI path. |
| [`efficiency.md`](efficiency.md) | Energy per unit work under several configs — and the correction that matters: the AC profile's 3.2 GHz cap is **efficiency-neutral** (~+2 %, within noise), not the ~24 % win a first, ~2×-low run suggested; it is the *deeper* caps that pay. |
| [`power-config-audit.md`](power-config-audit.md) | The config that actually runs (`power-profile`, `nbfc`, the GPU locks), audited against its own intent: what each mode sets, what was verified (the dGPU memory-lock fix, `platform_profile` as a trigger only, the WiFi lever, no `CCLK` asymmetry), and the nuances left as-is. |
| [`setup-offset-naming.md`](setup-offset-naming.md) | The manual protocol for naming the remaining `Setup` offsets: the two-leg menu method, and the one-reboot poke method (with the `.dat` format and `setup-poke.py`). |
| [`pm-table.md`](pm-table.md) | The SMU PM table decoded: 9 limits + 9 live values as `float32`, the "50 vs 54" question it settles, and the per-core groups (busy %, and the clocks `0x3c0`/`0x3e0` confirmed against `perf`). |
| [`smu-raw.md`](smu-raw.md) | The raw SMU/SMN layer under `ryzenadj`: the nodes, Cezanne's mailbox addresses, an end-to-end `GetSmuVersion` from userspace, and why the write path is left untouched so far. |
| [`ec-map.md`](ec-map.md) | The mapped embedded-controller registers (fans, three temperatures), how each was verified, and what is not in the EC. |
| [`h2ra-region.md`](h2ra-region.md) | The `H2RA` memory region at `0xfe700000` — a third, independent path to the fan tachometers. |
| [`dgpu-control.md`](dgpu-control.md) | The other end of the machine: the RTX 3070 Laptop GPU. A different gate from the CPU's — a clock lock that works, a power limit that does not, no voltage exposed. An underclock, not an undervolt. |
| [`dgpu-windows-undervolt.md`](dgpu-windows-undervolt.md) | The Windows trip for the one dGPU lever Linux lacks — a real V/F undervolt via MSI Afterburner — **run on 2026-09-24, and it came back empty**: no voltage, no power limit, a core-clock offset that reports success and does nothing, and a curve editor that binds as a clock clamp rather than a voltage map. Tooling to read what came back: `hml-analyze.py`. |
| [`governor.md`](governor.md) | The design for **one** governor over the four levers the machine actually has — CPU power limits, CPU frequency/EPP, the dGPU clock lock, the profile — instead of the three tools that ignore each other today. Plus `evidence/omen-governor`, its reference implementation. |
| [`battery-charge-control.md`](battery-charge-control.md) | `GBCC` / `SBCC` / `MBDC` decoded from the DSDT, the measured proof the charge cap works and is reversible, and the EC capacity registers (`BADC`/`BFCC`) that explain why the OS cannot see the design capacity. |
| [`efi-nvram.md`](efi-nvram.md) | The EFI variable store: the BIOS answers as readable variables, the clear-text copies in the flash, and what the image does and does not expose. |
| [`psp-tee.md`](psp-tee.md) | The other processor on the same image: the PSP is a GlobalPlatform TEE (ARM Cortex-A5) — the module map, the **named secure-boot chain** (`PSP_FW_BOOT_LOADER`'s own `load_validate_bios_l2_directory` / HVB signature check), `DEBUG_UNLOCK`, and the AMD-TEE door the OS can open (`amdtee` → `/dev/tee0`, which loads TAs as `$PS1`-signed firmware files). |
| [`psp-boot-verifier.md`](psp-boot-verifier.md) | That chain, decoded in Ghidra: the firmware gate is **RSA-2048 / SHA-256, PKCS#1 v1.5, over the *stored* (compressed) body**, verified before decompression (`FUN_0000b8ac`), with the key read from SPI (`FUN_00003e50`), a keyed hash behind it, and an **anti-rollback** counter (`FUN_0000a61c`, error `0x96`); plus the three entry points (SPI directory, in-DRAM blob, wrapped-key) and the `0x52` boot command that validates the SMU/MP2 images this repo reverses — and a reachability audit showing the verifier **is** fed caller-shaped headers (command `0x2d`/`0x32` → mode 2) but the parse is **bounded** (region-table resolution, constant-bounded lengths; no memory-safety violation found). |
| [`chipsec-recon.md`](chipsec-recon.md) | Talking to the chip directly instead of through HP's software: fixing CHIPSEC's kernel driver for a newer kernel, what that shows about the MSR block, and a from-scratch AMD platform file that reads the FCH's own write-protect registers. |
| [`psp-firmware.md`](psp-firmware.md) | The SMU/PMU firmware extracted in the clear — and the correction that it was readable all along: the `veri-failed` was a one-line `psptool` bug (it signs the *decompressed* body; the signature is over the *compressed* one). The 256 KiB images are **Xtensa** cores; the MP1 message queue and the Curve Optimizer handler are located, and the gate is decoded to instructions — the CO handler is a real ±30 per-core implementation that refuses with 0xFF because the OC-enable state is off, a state the unguarded path cannot reach (`enable-oc` is guard-rejected with 0xFD). |
| [`BIOS_arborescence_OMEN.md`](BIOS_arborescence_OMEN.md) | The full SmokelessUMAF menu tree, transcribed from the 133 photos. |
| [`record/`](record/) | The point-in-time investigation, kept as written. Start with the Linux report, then the Windows verdict. |
| [`img_smokelessUMAF/`](img_smokelessUMAF/) | The 133 photographs of the SmokelessUMAF menus, kept as primary evidence. |

### Tooling and raw data, in [`evidence/`](evidence/)

Grouped by what they act on — this is the working surface of the repo:

- **SMU, power limits and the CPU load** — `smuraw.py` (SMN reads, query-class SMU mailbox commands, and one self-restoring mutating write), `smu-gate-probe.py` + `.log` (the true SMU response read from the rsp register — it exposes the sysfs node's masking, and shows the CO gate is a recognised-and-refused command), `pmtable-cores.py` (the per-core PM table groups), `omenmon.py` (live power/thermal TUI), `limitwatch.py` / `limitrace.py` / `ec-revert-ab-test.sh` / `nbfc_on.csv` / `nbfc_off.csv` (what resets the SMU limits — the A/B), `load.c` (the Linux CPU load; the Windows twin is `load.cs`), `powsample.py` / `eff-test.sh` / `eff-analyze.py` (the joules-per-iteration harness), and `power-profile-watch` + `.service` (the re-apply governor), and `omen-governor` (the proposed unified governor over all four levers — see [`governor.md`](governor.md)), plus `gov-modes-test.sh` (measures each governor mode under load), `cap-single-thread.sh` and `st-ab.sh` (the cap's cost on a light load — the latter is the 3-rep A/B used in `efficiency.md`), `burst-peak.sh` (peak power/heat of a short burst, cap vs no-cap), and `drift-probe.py` (limits and the SMU mailbox sampled together, to catch what resets them).
- **Embedded controller** — `ecbridge.py` (the ACPI EC/I-O bridge), `ecsweep.py` (EC dump/diff), `ecwatch.py` (registers under load), `omenkbd.py` / `omenwatch.py` (keyboard backlight, the `H2RA` watch), and `batterycctl.py` / `batterycc.py` (battery charge control).
- **Firmware, EFI and the setup store** — `setupdiff.py` (the setup tables, `twoleg`), `tpmstate.py` (the TPM variables), `setup-poke.py` (a CRC-correct `dmpstore` `.dat`, built or inspected), `chipsec-cezanne.xml` / `chipsec-km-msr-api.patch` / `chipsec-recon.log`, `bios-unwrap.sh` / `bios-image-report.txt` / `psp-directory-report.txt` (unwrapping the AMI capsule and parsing it as UEFI and as an AMD PSP directory), `psp-firmware/` (`psp-firmware.py`, its captured output, the SMU/PMU hashes, the Xtensa ISA identification, the located `queue_dispatch`, and the decoded Curve Optimizer handler — the readable SMU firmware, the `psptool` signature-layout bug it exposes, and the instruction-level CO gate; see [`psp-firmware.md`](psp-firmware.md)), `psp-tee-modules.txt` (the PSP module characterisation), `psp-boot-verifier.txt` (the PSP secure-boot chain, by name) and `psp-boot-verifier/` (the same chain decoded: `decompiled.txt` plus the `ghidra/` scripts `Dec5–Dec11.java` — the verifier, the RSA modexp, the key table, the anti-rollback table, and the reachability audit; see [`psp-boot-verifier.md`](psp-boot-verifier.md)), `spi-flash-host-access.txt` (why the OS cannot read the flash), `aodread.py` / `aod-smm-handler.txt` / `aod-smm-curve-optimizer-trace.txt` / `aod-power-limit-probe.txt` (the `\AOD` SMI handler, located and disassembled), and the rehearsed probes `uefi-shell-probe/`, `tpm-experiment/`, `usbcam-experiment/`, `aod-setup-probe/`.
- **The lowest layers** — `smnscan.py` (SMN reads cross-checked between the sysfs node and the raw PCI config window), `msrread.py` (raw MSR reads with the validity discriminators), `memdump.py` (read-only `/dev/mem` hexdump), `h2ra-sweep.sh` (which `H2RA` bytes are a static curve vs the fans), and `deep-recon/` (the raw PCI-config, SMN, SPI-MMIO and MSR captures).
- **The dGPU, and the Windows side** — `dgpu-probe.txt` (the Linux probe), `gpuload.cu` (the CUDA GPU load), `gpu-lock-e2e.sh` (the battery→AC clock-lock interaction test), `ab-log-analyze.py` (RTSS CSV logs), `hml-analyze.py` (Afterburner's own `HardwareMonitoring.hml`; `--windows` is how the passes are compared), `nv-surface.sh` (the exposed NVIDIA surface), and `dgpu-windows/` (the extracted windows; the 36 MB raw `.hml` are local, not versioned).
- **Benchmarks and captures** — `results.jsonl` (the 26 Windows benchmark runs), `ab-test.log`, `smu.cs` (the Windows SMU prober), and `autonomous-pass/` (the IOMMU, ESRT, i²c, efficiency and EC-under-load captures).

## Caveats

- **One machine.** This is the behaviour of one 15-en1xxx on BIOS F.30. Other
  revisions, or a BIOS update, can differ.
- **The OC/CO gate is HP's, not AMD's.** That is consistent with the missing BIOS
  menu, the empty `Custom Core Pstates` form and Sure Start — but the mechanism
  behind the refusal is not known. Only the refusal is.
- **A string missing from the flash image proves nothing — for the part that's
  still opaque.** Three of the four regions once called "encrypted" are now
  identified — two were compressed (a missing tool, `TianoCompress`, not an
  unreadable image), one is AMD's signed PSP directory (a different, known
  format) →
  [`firmware-limits.md`](firmware-limits.md#three-of-the-four-encrypted-regions-are-now-identified).
  Only `0x1e4000` is still genuinely high-entropy and unparsed. For that one
  region, absence of a name still only means it is not *in the clear*, and any
  claim drawn from searching that part of the image carries that limit.
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
