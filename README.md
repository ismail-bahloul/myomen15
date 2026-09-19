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

Where control sits, layer by layer. The detailed evidence for each row is in
[`firmware-limits.md`](firmware-limits.md).

| Layer | What we can do | State |
|---|---|---|
| CPU power limits (SMU) | Write STAPM / PPT / Tctl via `ryzenadj`; they persist | ✅ **controlled** (one caveat: a `platform_profile` write resets them) |
| SMU telemetry (PM table) | 2372 bytes of `float32` — 9 limits + 9 live values, one file read | ✅ **decoded** |
| Fan control | `nbfc` (EC), `hp-wmi`, memory-mapped tacho at `0xfe700000`, and the ACPI bridge | ✅ **controlled** (four independent paths) |
| EC registers | Four paths: `ec_sys`, `hp-wmi`, `H2RA`, and firmware `M040`/`M041` (verified 256/256) | ✅ **controlled** |
| I/O ports | Firmware `M31A`/`M319` reaches any port, including SMM `0xB2` | ✅ **accessible** |
| EFI setup answers | **Readable** at runtime as plain EFI variables; also stored in clear twice in the flash | ✅ **read** |
| Keyboard RGB | The EC publishes 4-zone RGB state in `H2RA`; **writes there don't control it** | 🟡 **found, not controllable** |
| Performance mode (`OCPC`) | In the EC; maps to dGPU power limits via `\DPTC` | 🟡 **open** |
| Curve Optimizer (SMM path) | `\AOD` command `0x0005000A` — a second road, never tried | 🟡 **open** |
| Battery charge control | EC bridge → `MBDC` **stops charging** (no held threshold seen, 100→55 %); `GBCC` confirms the mode; the cap that holds is the BIOS optimizer's `BFCC` | 🟡 **partial** |
| Memory tuning (SPD profiles) | Firmware ships non-QVL SPD profiles by part number, reachable via `AMD CBS > UMC` | 🟡 **open** |
| BIOS power menu (AMD CBS) | Nothing — it only seeds POST values the HP EC overrides | ⚪ **inert** |
| BIOS hidden menus | Reachable with SmokelessUMAF / SREP (`SuppressIf` patch) | 🟡 **partial** — but `Custom Core Pstates` stays empty |
| CPU undervolt / Curve Optimizer (**SMU path**) | The SMU refuses the whole OC/CO family on **both** OSes | 🔴 **locked** |
| BIOS modification / flashing | Nothing — HP Sure Start is active, the payload is PSS-signed | 🔴 **blocked** |
| Embedded controller (EC) registers | Fans, three temperatures, and the named control offsets mapped | 🟡 **partial** — see [`ec-map.md`](ec-map.md) |
| TPM | `Hidden` — disabled and not detected at POST | ⚪ **off** |

Legend: ✅ controlled · 🟡 partial or open · ⚪ no effect · 🔴 refused.

## The short version

| Question | Answer |
|---|---|
| Can I undervolt, or use Curve Optimizer? | **The SMU says no** — proven on both OSes. But an untested second road exists (`\AOD`, via SMM), which is what HP's own software uses. |
| Can I read what the SMU is actually doing? | **Yes.** The PM table decodes to 9 limits + 9 live values in one `read()`. |
| Can I read the BIOS settings from the running OS? | **Yes.** Plain EFI variables — and identical in the flash chip, twice. Writing them back is refused for the setup store, but the standard EFI globals *are* writable. |
| Can I talk to any EC register or I/O port? | **Yes.** The firmware ships a generic byte bridge (`M040`/`M041`/`M31A`/`M319`), verified 256/256 against `ec_probe`. |
| Can I cap battery charging? | **Partly.** The firmware's cap is the BIOS "battery optimizer": it lowers `BFCC`, the reported full capacity (85 % of the 70.9 Wh pack) — and the OS cannot see it. The `MBDC` register is a *different* lever: it stops charging, it does not hold a level. |
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
- **A method I proposed, and the experiment that killed it.** Toggle one BIOS
  option, diff the tables, name the offset — that was the plan. A three-way TPM
  toggle (`off` → `on` → `off` → `Hidden`) showed it does not work: saving the
  setup moves bytes *whatever* you changed, and `SetupDefault` itself drifts, so
  "factory default" is not a stable point. → [`efi-nvram.md`](efi-nvram.md) §7
- **A hidden memory-tuning table names a module this machine does not have.** The
  firmware carries whole SPD profiles keyed by part number; one of them is for a
  Micron `8ATF1G64HZ-2G3B1`, which is not in either slot. So the "no memory
  tuning" dead end was a *QVL* dead end, not a firmware one.
- **Two EC temperatures, and three that were not.** A controlled thermal ramp
  (idle → 16 threads → idle) confirmed `0x57` and `0x58` track `k10temp`'s
  `Tctl`, and killed the earlier guess that the whole `0x40`-`0x49` row was a
  bank of sensors: only `0x48` moves with heat. → [`ec-map.md`](ec-map.md)

## Open fronts

What has not been tried yet, ordered by how much it would unlock:

- **Writing through the raw SMU layer.** The layer under `ryzenadj` (`smn`,
  `mp1_smu_cmd`, `rsmu_cmd`, `smu_args`) is now *read* — SMN registers, and an
  end-to-end `GetSmuVersion` — but every node is also writable and none has been
  written. That is the largest remaining unlock, and the honest reason it waits
  is that a control path should be read before it is used to write. →
  [`smu-raw.md`](smu-raw.md)
- **Name the setup offsets — the right way.** The eleven off-default offsets are
  known, but naming them needs the two-leg method of
  [`efi-nvram.md`](efi-nvram.md) §7: two reboots per option.
- **`postcode`.** `hp-wmi` exposes a firmware POST code that reads a stable
  `0x70`. Unexplored and free.
- **The memory side.** The firmware's own SPD table names a module that is not
  installed; the lever is `AMD CBS > UMC Common Options`.
- **Closed, do not chase:** Curve Optimizer, BIOS flashing, MSR (`EIO`), EFI
  setup-variable writes (`EPERM`).

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
| [`BIOS_arborescence_OMEN.md`](BIOS_arborescence_OMEN.md) | The full SmokelessUMAF menu tree, transcribed from the 133 photos. |
| [`record/`](record/) | The point-in-time investigation, kept as written. Start with the Linux report, then the Windows verdict. |
| [`evidence/`](evidence/) | Tooling and raw data: `smu.cs`, `load.cs`, the 26 benchmark runs, the two A/B CSVs, `setupdiff.py`, `tpmstate.py`, `batterycc.py`, `ecbridge.py`, `omenkbd.py`, `omenwatch.py`, `aodread.py`, plus `omenmon.py` (live power/thermal TUI), `limitwatch.py` (what resets the SMU limits), `pmtable-cores.py` (the per-core PM table groups), `smuraw.py` (read-only SMN/MP1 access), and `batterycctl.py` (battery charge control). |
| [`evidence/power-profile-watch`](evidence/power-profile-watch) | Re-applies the power profile the instant `platform_profile` is written — the 5-minute re-apply window, closed. |
| [`img_smokelessUMAF/`](img_smokelessUMAF/) | The 133 photographs of the SmokelessUMAF menus, kept as primary evidence. |

## Caveats

- **One machine.** This is the behaviour of one 15-en1xxx on BIOS F.30. Other
  revisions, or a BIOS update, can differ.
- **The OC/CO gate is HP's, not AMD's.** That is consistent with the missing BIOS
  menu, the empty `Custom Core Pstates` form and Sure Start — but the mechanism
  behind the refusal is not known. Only the refusal is.
- **A string missing from the flash image proves nothing.** More than a third of
  the 16 MiB image is at entropy ≈ 8.0 (encrypted or compressed), and no `_FVH`
  signature survives inside those volumes. Absence of a name only means it is not
  *in the clear*. Any claim drawn from searching the image carries that limit.
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
