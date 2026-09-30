# Access surface inventory (HP OMEN 15-en1xxx)

What is reachable on this machine, and what refuses. Measured, not assumed —
every row was read on this hardware, on CachyOS (originally kernel
7.2.4-3-cachyos; the MSR/SMM/FCH rows re-checked on 7.2.6-1-cachyos).

This page exists so the same ground is not re-covered, and so a surface that is
*reachable but never used* is visible as such.

## Reachable and used

| Surface | Path | Notes |
|---|---|---|
| SMU power limits | `ryzen_smu` + `ryzenadj` | STAPM / PPT / Tctl, writes persist |
| **SMU PM table** | `/sys/kernel/ryzen_smu_drv/pm_table` | 2372 B of `float32`; 9 limits + 9 live values. See [`pm-table.md`](pm-table.md) |
| **Raw SMN / SMU mailbox** | `/sys/kernel/ryzen_smu_drv/{smn,mp1_smu_cmd,rsmu_cmd,smu_args}` | The layer under `ryzenadj`; read-only so far. SMN registers read, `GetSmuVersion` verified end to end. Writable, deliberately not used. See [`smu-raw.md`](smu-raw.md) |
| **Raw SMN, no module** | `setpci -s 00:00.0 b8.l=<addr>` then `bc.l` | The root complex's own SMN index/data window. 1021/1024 agree with the sysfs node over the mailbox page (3 are volatile). Reaches SMN with no kernel module. See [`smu-raw.md`](smu-raw.md) |
| **Raw MSRs** | `/dev/cpu/N/msr` | Valid AMD MSRs read directly (HWCR, EFER, SMM_BASE/ADDR/MASK). **No CHIPSEC needed** — the old `EIO` was an Intel-only MSR, not a block. See [`msr-and-smm.md`](msr-and-smm.md) |
| **FCH write-protect + SPI controller** | `.../0000:00:14.3/config`; `/dev/mem` @ `0xFEC10000` | `ROMPROTECT2=0x00326400` (`WriteProtect=1` but `Range=0`), `SPIBASEADDR=0xFEC10002`. The MMIO *is* host-visible, but `SpiHostAccessRomEn=0` (`SpiAccessMacRomEn=1`), so the host cannot read the flash at all — flashrom finds no chip, and only the legacy 0xE0000/0xF0000 window plus the **last 1 MiB** of the BIOS (`0xFFF00000`) are memory-mapped. Read-only. See [`msr-and-smm.md`](msr-and-smm.md) and [`evidence/spi-flash-host-access.txt`](evidence/spi-flash-host-access.txt) |
| **SMM state** | MSRs + `/dev/mem` | `SmmLock=1`, `SmmBaseLock=1`; TSEG 32 MB @ `0xBE000000`; SMRAM reads `0xFF` (hidden). Live (`\AOD`) but sealed. See [`msr-and-smm.md`](msr-and-smm.md) |
| EC registers | `ec_probe`, `/sys/kernel/debug/ec/ec0/io`, **and the ACPI bridge** | `write_support=Y`; fans, three temperatures |
| **ACPI EC/I-O bridge** | `acpi_call` → `M040`/`M041`/`M31A`/`M319` | Any EC byte, any I/O port. Verified 256/256 vs `ec_probe`. See [`acpi-bridge.md`](acpi-bridge.md) |
| **Memory-mapped fan tachos** | `/dev/mem` at `0xfe700000` (`H2RA`) | A third, independent path, **read-only**. Writes were tested and do nothing. See [`h2ra-region.md`](h2ra-region.md) |
| Fan control | `nbfc` (EC), `hp-wmi` `pwm1_enable` | `pwm1_enable=2` (auto) |
| Platform profile | `/sys/class/platform-profile/` | `cool` / `balanced` / `performance` |
| **Battery charge control** | EC bridge → `MBDC` (0xA6); `\WMID.GBCC` reads it | Setting a mode **stops charging** (no held threshold seen down to 55 %), `GBCC` confirms it, reversible. The cap that *holds* is **`Adaptive Battery Extender`** (`SHEN`, EC `0xC5` bit 7 — enabled), which lowers `BFCC`. See [`battery-charge-control.md`](battery-charge-control.md) |
| **AMD overclocking (`\AOD`)** | `acpi_call` → `\AOD.WMAA` | PPT/TDC/EDC/Scalar/Curve Optimizer via SMM. **Driven and inert**: a power-limit lever through it moves nothing, while `ryzenadj` moves the same value instantly. Handler `AodSmmSsp` located in the image, no SMU mailbox address of its own. See [`acpi-bridge.md`](acpi-bridge.md) §2 |
| **Performance mode** | EC `OCPC` (0xBA) / `OCPS` (0xBB) | Maps to dGPU power limits via `\DPTC`. `OCPC` is EC-owned (read-only); `OCPS` accepts a write but the effect is not established. See [`ec-map.md`](ec-map.md) |
| **Keyboard RGB (4 zones)** | Reported by the EC in `H2RA`, but there is **no Linux interface** and writes there do nothing | 🟡 **found, not controllable** |
| EFI setup answers | `/sys/firmware/efi/efivars/` | 137 vars, read-only. See [`efi-nvram.md`](efi-nvram.md) |
| DSDT / 16 SSDT | `/sys/firmware/acpi/tables/` | 95 KB DSDT, disassembles cleanly with `iasl` |
| **iGPU / SoC DPM level** | `/sys/class/drm/card*/device/power_dpm_force_performance_level` | `low` on battery drops mclk/fclk 1600→400 and the idle draw ~14.5→11.5 W; video decode and the 144 Hz mode are unaffected. Costs CPU memory bandwidth (~−43 %). Driven per profile by `power-profile`. See [`efficiency.md`](efficiency.md) |
| **dGPU clock lock** | `nvidia-smi --lock-gpu-clocks=min,max` (NVML, root) | The RTX 3070 Laptop. **Measured effective** — 80 W → 41 W under load at a 1000 MHz cap. Memory clock lock also accepted. See [`dgpu-control.md`](dgpu-control.md) |

## Reachable, NOT yet used

These are open, listed so the choice is visible rather than forgotten. Where a
later pass has covered one, the row says so.

| Surface | How | Why it might matter |
|---|---|---|
| `hp-wmi` `postcode` | `cat /sys/devices/platform/hp-wmi/postcode` | Reads a stable `0x70`. A firmware observation channel that costs nothing. |
| **PCIe ASPM policy** | **not runtime-writable** (`EPERM` on `/sys/module/pcie_aspm/parameters/policy`) — kernel cmdline `pcie_aspm.policy=powersave` + reboot | The live policy is `default`, and 7 links sit at `ASPM Disabled`. Untested: needs a reboot, and ASPM-on-everything carries a stability risk. |
| Screen | brightness is at 80 % (52428/65535); the panel also advertises adaptive backlight modulation (`kscreen-doctor`: set to 2) | The panel is a first-order battery load; brightness and refresh (144 → 60 Hz) are the classic levers, both user-facing. Unmeasured here. |
| Fan curve | `nbfc` (`my-nbfc.json`) | Runs, but the curve itself has not been tuned against temps — the lever for **silence**, not draw. |
| esrt / capsules | `/sys/firmware/efi/esrt/` | **Read:** one entry, `fw_class 8278833a-…`, type 1 (system firmware), fw_version `0x0F300000` (= F.30). `OsIndications` = `0x7`, `BootCurrent` = `0006`. No capsule applied. |
| PCI config, root complex | `setpci` / `lspci -xxx -s 00:00.0` | **Done:** the `0x40`–`0x100` zone captured (`evidence/deep-recon/pci-sysfs-256.txt`); it also carries the SMN index/data window at `0xB8`/`0xBC`. On the FCH (`00:14.3`), `0x50`–`0x5C` (`ROMPROTECT`) and `0xA0` (`SPIBASEADDR`) are interpreted; the rest is still raw. |
| IOMMU + vfio | 24 groups, `vfio-pci` registered | **Enumerated:** booted `iommu=pt`; the 24 groups are the PCI functions, nothing bound to `vfio-pci` yet. Relevant to the VFIO passthrough setup. |
| SMBus / i2c | `i2c-0`…`i2c-9` | **Scanned.** SPD EEPROMs on `i2c-7` (`7-0050`/`7-0051`, `MT16ATF2G64HZ-3G2E1` ×2). `i2c-0` = touchpad at `0x2d`; `i2c-6` = dGPU devices at `0x30`/`0x37`/`0x50`; `i2c-1`…`i2c-5` empty (`i2c-2` is a DP AUX channel — its "hits" are false positives). |
| `hp-wmi` `display`, `dock` | `cat` | Both read `0`. |
| `hp_accel` | `modprobe hp_accel` | **Tested:** loads clean (pulls in `lis3lv02d`) but binds to **no hardware** — no `/dev/freefall`, no sysfs device, no kernel message. The accelerometer is not exposed on this SKU. Unloaded clean. |
| dGPU clock offsets | `nvidia-settings` with `Coolbits` set (needs an X restart) | The offset attributes already read (−1000…+1000 MHz / −2000…+6000); only the permission is missing. Would shift the whole curve — a wider underclock, still not a voltage. |

## Measured as blocked — do not retry

| Surface | Result | Detail |
|---|---|---|
| **EFI variable writes** | mixed | 137 variables: **22 are writable** (the EFI globals — `Boot####`, `BootOrder`, `BootCurrent`, `Timeout`, `PlatformLang`, `OsIndications`, …); **115 are immutable** (`EPERM`), and that set is exactly the BIOS/HP/AMD setup store plus the Secure Boot keys and TPM state. The attribute dword (`0x7`) is the same in both groups. |
| **HP Sure Start audit log** | `ENOTSUP` | `hp-bioscfg` exposes `audit_log_entries`, but reading it fails. |
| **SPM auth token** | `ENOTSUP` / `EPERM` | `enhanced-bios-auth`, `is_enabled=0`, `key_mechanism = not provisioned`. No BIOS admin password set. |
| **BIOS flashing** | blocked by design | Payload is PSS/RSA-signed; Sure Start restores on tamper. Not attempted, deliberately. |
| **`hp-wmi` `als`, `hddtemp`, `tablet`** | `EINVAL` / `ENODEV` | Nodes exist, hardware does not answer. |
| **Curve Optimizer** | refused | SMU rejects the whole OC/CO family on both OSes. The raw mailbox shows *why it is a real gate*: `0xFF Failed` for a recognised command, not `0xFE UnknownCmd` (and the sysfs response node was masking that — read the rsp over SMN). → [`smu-raw.md`](smu-raw.md#is-the-curve-optimizer-gate-a-transport-problem-measured-no) |
| **dGPU power limit** | not supported | `nvidia-smi -pl` → *"Changing power management limit is not supported for GPU"*. A 1–100 W range is reported but not user-enforced. |
| **dGPU voltage / V/F curve** | not exposed | Nothing via NVML, nothing via `nvidia-settings`. There is no Linux undervolt for this GPU. → [`dgpu-control.md`](dgpu-control.md) |

The **MSR** row that used to sit here — "`EIO`, the block is the Linux `msr`
module's allowlist" — has been removed: the block was never a block. `0x1a0`
is an Intel-only MSR, invalid on this AMD part; valid AMD MSRs read fine via
the stock node. See [`msr-and-smm.md`](msr-and-smm.md).

## A note on two `hp-wmi` quirks

`hp-bioscfg` creates an attribute directory whose name is a bare control
character (`\x0e`), holding `display_name`, `possible_values` and `current_value`
— all empty. It is a driver bug in how the attribute is registered, and it is
harmless to read, but it means shell globbing over
`/sys/class/firmware-attributes/hp-bioscfg/attributes/*` misbehaves. Address
`Sure_Start` and `pending_reboot` by name.

`hp-wmi`'s `pwm1_enable` reports `2` (automatic), and there is no `pwm1` node —
so the hwmon can be read but not driven directly. Fan control goes through
`nbfc` or the EC.
