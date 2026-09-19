# Access surface inventory (HP OMEN 15-en1xxx)

What is reachable on this machine, and what refuses. Measured, not assumed —
every row was read on this hardware, on CachyOS with kernel 7.2.4-3-cachyos.

This page exists so the same ground is not re-covered, and so a surface that is
*reachable but never used* is visible as such.

## Reachable and used

| Surface | Path | Notes |
|---|---|---|
| SMU power limits | `ryzen_smu` + `ryzenadj` | STAPM / PPT / Tctl, writes persist |
| **SMU PM table** | `/sys/kernel/ryzen_smu_drv/pm_table` | 2372 B of `float32`; 9 limits + 9 live values. See [`pm-table.md`](pm-table.md) |
| **Raw SMN / SMU mailbox** | `/sys/kernel/ryzen_smu_drv/{smn,mp1_smu_cmd,rsmu_cmd,smu_args}` | The layer under `ryzenadj`; read-only so far. SMN registers read, `GetSmuVersion` verified end to end. Writable, deliberately not used. See [`smu-raw.md`](smu-raw.md) |
| EC registers | `ec_probe`, `/sys/kernel/debug/ec/ec0/io`, **and the ACPI bridge** | `write_support=Y`; fans, three temperatures |
| **ACPI EC/I-O bridge** | `acpi_call` → `M040`/`M041`/`M31A`/`M319` | Any EC byte, any I/O port. Verified 256/256 vs `ec_probe`. See [`acpi-bridge.md`](acpi-bridge.md) |
| **Memory-mapped fan tachos** | `/dev/mem` at `0xfe700000` (`H2RA`) | A third, independent path, **read-only**. Writes were tested and do nothing. See [`h2ra-region.md`](h2ra-region.md) |
| Fan control | `nbfc` (EC), `hp-wmi` `pwm1_enable` | `pwm1_enable=2` (auto) |
| Platform profile | `/sys/class/platform-profile/` | `cool` / `balanced` / `performance` |
| **Battery charge control** | EC bridge → `MBDC` (0xA6); `\WMID.GBCC` reads it | Setting a mode **stops charging** (no held threshold seen down to 55 %), `GBCC` confirms it, reversible. The cap that *holds* is **`Adaptive Battery Extender`** (`SHEN`, EC `0xC5` bit 7 — enabled), which lowers `BFCC`. See [`battery-charge-control.md`](battery-charge-control.md) |
| **AMD overclocking (`\AOD`)** | `acpi_call` → `\AOD.WMAA` | PPT/TDC/EDC/Scalar/Curve Optimizer via SMM. Never tried. See [`acpi-bridge.md`](acpi-bridge.md) |
| **Performance mode** | EC `OCPC` (0xBA) / `OCPS` (0xBB) | Maps to dGPU power limits via `\DPTC`. `OCPC` is EC-owned (read-only); `OCPS` accepts a write but the effect is not established. See [`ec-map.md`](ec-map.md) |
| **Keyboard RGB (4 zones)** | Reported by the EC in `H2RA`, but there is **no Linux interface** and writes there do nothing | 🟡 **found, not controllable** |
| EFI setup answers | `/sys/firmware/efi/efivars/` | 137 vars, read-only. See [`efi-nvram.md`](efi-nvram.md) |
| DSDT / 16 SSDT | `/sys/firmware/acpi/tables/` | 95 KB DSDT, disassembles cleanly with `iasl` |

## Reachable, NOT yet used

These are open, and none of them has been explored. Listed so the choice is
visible rather than forgotten.

| Surface | How | Why it might matter |
|---|---|---|
| `hp-wmi` `postcode` | `cat /sys/devices/platform/hp-wmi/postcode` | Reads a stable `0x70`. A firmware observation channel that costs nothing. |
| esrt / capsules | `/sys/firmware/efi/esrt/` | Firmware update entries; `fwupd` sees the system as updatable. |
| PCI config, root complex | `setpci` / `lspci -xxx -s 00:00.0` | Zone `0x40`–`0x100` is non-zero and uninterpreted. |
| IOMMU + vfio | 24 groups, `vfio-pci` registered | No device bound; unused. Relevant to the VFIO passthrough setup. |
| SMBus / i2c | `i2c-3`, `i2c-4`, `i2c-5`, `i2c-6`, `i2c-7` | `i2cdetect`, `i2cget` available. SPD is on this bus; nothing scanned yet. |
| `hp-wmi` `display`, `dock` | `cat` | Both read `0`. |
| `hp_accel` | module exists, not loaded | The accelerometer driver is shipped but idle. |

## Measured as blocked — do not retry

| Surface | Result | Detail |
|---|---|---|
| **MSR** | `EIO` | `/dev/cpu/*/msr` exist (16 nodes), but `read()` at `0x1a0` returns `Input/output error`. No `rdmsr`/`wrmsr` installed. |
| **EFI variable writes** | mixed | 137 variables: **22 are writable** (the EFI globals — `Boot####`, `BootOrder`, `BootCurrent`, `Timeout`, `PlatformLang`, `OsIndications`, …); **115 are immutable** (`EPERM`), and that set is exactly the BIOS/HP/AMD setup store plus the Secure Boot keys and TPM state. The attribute dword (`0x7`) is the same in both groups. |
| **HP Sure Start audit log** | `ENOTSUP` | `hp-bioscfg` exposes `audit_log_entries`, but reading it fails. |
| **SPM auth token** | `ENOTSUP` / `EPERM` | `enhanced-bios-auth`, `is_enabled=0`, `key_mechanism = not provisioned`. No BIOS admin password set. |
| **BIOS flashing** | blocked by design | Payload is PSS/RSA-signed; Sure Start restores on tamper. Not attempted, deliberately. |
| **`hp-wmi` `als`, `hddtemp`, `tablet`** | `EINVAL` / `ENODEV` | Nodes exist, hardware does not answer. |
| **Curve Optimizer** | refused | SMU rejects the whole OC/CO family on both OSes. Dead end, do not chase. |

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
