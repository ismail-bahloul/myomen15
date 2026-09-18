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
| Fan control | `nbfc` (EC), `hp-wmi` `pwm1_enable`, and a memory-mapped tacho at `0xfe700000` | ✅ **controlled** (three independent paths) |
| EFI setup answers | **Readable** at runtime as plain EFI variables; also stored in clear twice in the flash | ✅ **read** |
| Battery charge control | `GBCC` / `SBCC` reachable through `acpi_call`; decoded, **not** written | 🟡 **open** |
| Memory tuning (SPD profiles) | Firmware ships non-QVL SPD profiles by part number, reachable via `AMD CBS > UMC` | 🟡 **open** |
| BIOS power menu (AMD CBS) | Nothing — it only seeds POST values the HP EC overrides | ⚪ **inert** |
| BIOS hidden menus | Reachable with SmokelessUMAF / SREP (`SuppressIf` patch) | 🟡 **partial** — but `Custom Core Pstates` stays empty |
| CPU undervolt / Curve Optimizer | Nothing — the SMU refuses the whole OC/CO family on **both** OSes | 🔴 **locked** |
| BIOS modification / flashing | Nothing — HP Sure Start is active, the payload is PSS-signed | 🔴 **blocked** |
| Embedded controller (EC) | Reachable (`ec_probe`, `nbfc`); fans and three temperature registers mapped | 🟡 **partial** — see [`ec-map.md`](ec-map.md) |
| TPM | `Hidden` — disabled and not detected at POST | ⚪ **off** |

Legend: ✅ controlled · 🟡 partial or open · ⚪ no effect · 🔴 refused.

## The short version

| Question | Answer |
|---|---|
| Can I undervolt, or use Curve Optimizer? | **No.** The SMU refuses the whole OC/CO command family — on Linux *and* on Windows. |
| Can I read what the SMU is actually doing? | **Yes.** The PM table decodes to 9 limits + 9 live values in one `read()`. This is the instrument the Windows side lacked. |
| Can I read the BIOS settings from the running OS? | **Yes.** They are plain EFI variables (`AMD_PBS_SETUP`, `AmdSetup`, `Setup`) — and identical in the flash chip, twice. |
| Can I cap battery charging? | **Mechanism found and decoded** (`SBCC` writes `EC0.MBDC`), but the battery reports no cap mode available. Unverified. |
| Can I set a power limit in the BIOS? | That setting is **inert** on this machine; the HP EC owns those values. |
| Do power limits written by the OS stick? | **Yes** — with one exception: writing `platform_profile` makes the EC re-apply its own. |
| Can I modify the BIOS? | **No** — HP Sure Start is active, and the payload is PSS-signed. |

## What is actually interesting here

Not the answers — those are small. What is interesting is that they are
*measured*, and that the wrong turns are kept, because that is where the method
is visible.

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
- **The battery "dead end" was not one.** "Charge thresholds unsupported" was
  true of the kernel surface and false of the firmware: HP's `SBCC` method writes
  a named EC register, and `acpi_call` reaches it. Decoded in full — arguments,
  bit encodings, the guard, the completion flag, the return codes. Not written to,
  and why. → [`battery-charge-control.md`](battery-charge-control.md)
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

- **The battery write, first and only if you want it.** The mechanism is decoded
  and the revert is known (`MBDC &= 0xE0`), but the battery advertises **no** cap
  mode (`MBST = 0x00`), so a write may be accepted and ignored — the exact trap
  this repo was already caught by once. `evidence/batterycc.py status` shows the
  state; it stays read-only unless asked.
- **The SSDTs.** Only the DSDT was disassembled. Sixteen SSDTs remain, and they
  are where the WMI and thermal plumbing is likely to be.
- **The raw SMU/SMN interface.** `mp1_smu_cmd`, `rsmu_cmd`, `smn` expose the layer
  under `ryzenadj` — the same layer the Windows probe used from the other side.
  Never driven from Linux here.
- **Name the setup offsets — the right way.** The eleven off-default offsets are
  known, but naming them needs the two-leg method of
  [`efi-nvram.md`](efi-nvram.md) §7: two reboots per option.
- **`postcode`.** `hp-wmi` exposes a firmware POST code that reads a stable
  `0x70`. Unexplored and free.
- **The memory side.** The firmware's own SPD table names a module that is not
  installed; the lever is `AMD CBS > UMC Common Options`.
- **Closed, do not chase:** Curve Optimizer, BIOS flashing, MSR (`EIO`), EFI
  variable writes (`EPERM`).

## What is in this repository

| Path | What it is |
|---|---|
| [`firmware-limits.md`](firmware-limits.md) | The living reference — current conclusions only: BIOS power semantics, the Curve Optimizer gate, Sure Start, what resets an OS-written profile, and what is unsupported. |
| [`access-surface.md`](access-surface.md) | Everything reachable on this machine, everything measured as blocked, and what is reachable but not yet used. |
| [`pm-table.md`](pm-table.md) | The SMU PM table decoded: 9 limits + 9 live values as `float32`, and the "50 vs 54" question it settles. |
| [`ec-map.md`](ec-map.md) | The mapped embedded-controller registers (fans, three temperatures), how each was verified, and what is not in the EC. |
| [`h2ra-region.md`](h2ra-region.md) | The `H2RA` memory region at `0xfe700000` — a third, independent path to the fan tachometers. |
| [`battery-charge-control.md`](battery-charge-control.md) | `GBCC` / `SBCC` / `MBDC` decoded from the DSDT, and why it was not written to. |
| [`efi-nvram.md`](efi-nvram.md) | The EFI variable store: the BIOS answers as readable variables, the clear-text copies in the flash, and what the image does and does not expose. |
| [`BIOS_arborescence_OMEN.md`](BIOS_arborescence_OMEN.md) | The full SmokelessUMAF menu tree, transcribed from the 133 photos. |
| [`record/`](record/) | The point-in-time investigation, kept as written. Start with the Linux report, then the Windows verdict. |
| [`evidence/`](evidence/) | Tooling and raw data: `smu.cs`, `load.cs`, the 26 benchmark runs, the two A/B CSVs, `setupdiff.py`, `tpmstate.py`, `batterycc.py`. |
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
