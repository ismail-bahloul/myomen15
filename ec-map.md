# Embedded controller map (HP OMEN 15-en1xxx)

The EC on this machine is reachable, and partially mapped. This page records
what has been **verified**, how, and what is still guesswork.

## Method

`ec_probe` (built on the `ec_sys` module, `write_support=1`) reads and writes EC
registers directly. Every row below was established by correlating a dump with an
independent source — `hwmon`, `ryzenadj`, or nbfc's own config — at the same
instant, never by guessing.

```bash
# dump all 256 registers
sudo ec_probe dump
# read / write a single byte
sudo ec_probe read 0x57
sudo ec_probe write 0x2C 30
```

## Verified registers

| Register | Type | Meaning | How it was checked |
|---|---|---|---|
| `0x2C` | u8 | CPU fan duty **setpoint** (%) | nbfc's `WriteRegister` (44) for the CPU fan |
| `0x2D` | u8 | GPU fan duty **setpoint** (%) | nbfc's `WriteRegister` (45) for the GPU fan |
| `0x2E` | u8 | CPU fan speed **readback** (%) | nbfc's `ReadRegister` (46); tracks `0x2C` |
| `0x2F` | u8 | GPU fan speed **readback** (%) | nbfc's `ReadRegister` (47) |
| `0xB0` | u16 LE | CPU fan **tachometer** (RPM) | equals `hwmon7/fan1_input` exactly, 5/5 samples |
| `0xB2` | u16 LE | GPU fan **tachometer** (RPM) | tracks `hwmon7/fan2_input` |
| `0x57` | u8 | temperature (°C) | equals `k10temp` `Tctl`, matched 50↔50 and 51↔51 |
| `0x58` | u8 | second temperature (°C) | same value as `0x57` in every sample |

Fan tachometer correlation (simultaneous reads):

```
fan1=888  fan2=696  | B0 = 78 03 B8 02  -> 0x0378 = 888, 0x02B8 = 696
fan1=931  fan2=691  | B0 = A0 03 A3 02  -> 0x03A0 = 928, 0x02A3 = 675
fan1=885  fan2=685  | B0 = 7D 03 9A 02  -> 0x037D = 893, 0x029A = 666
```

## Negative result: the power limits are *not* in the EC

The obvious hypothesis — that the EC stores the STAPM / PPT / Tctl limits and
re-asserts them — was tested and **falsified**.

Procedure: dump the EC, write distinctive limits through `ryzenadj`
(STAPM 31 W / fast 43 W / slow 33 W), dump again, diff. Then repeat the two dumps
**without changing anything**, as a control for telemetry drift.

The control run changed the *same* registers as the write run:

```
control (nothing changed):  0x2E, 0x50-row, 0x80-row, 0xB0-row drift
write  (31/43/33 W):        0x2E, 0x50-row, 0x80-row, 0xB0-row drift
```

The two diffs are indistinguishable, and none of the changed bytes encodes
31/43/33. So the SMU limits live in the SMU and nowhere else on the EC side; the
volatile registers are telemetry (fans, temperatures). This rules out "the EC
owns the limits" as an explanation for the [platform profile
reset](firmware-limits.md#power-limits-they-stay-put-but-writing-platform_profile-resets-them).

## Not yet identified

These move, but have not been attributed yet:

| Register / range | Observation |
|---|---|
| `0x51`, `0x53`, `0x55` | stable during idle; `0x53` sits at `0x0F` (15) |
| `0x40`–`0x49` | `0x47`≈53, `0x48`≈41, `0x49`≈46 — plausible additional temperatures |
| `0x80`–`0x88` | volatile cluster, low byte of a fast counter at `0x83` |

Next step for these would be a controlled thermal ramp (idle → sustained load)
while logging both the EC and every `hwmon` temperature, and matching the curves.

## How to reach the EC

- `ec_probe` — register dump / read / write, plus `acpi_call`.
- `nbfc` — writes the fan setpoints through the same path, so it is a working
  reference implementation of the write half.
- `hp-wmi` exposes `/sys/class/platform-profile/platform-profile-0/` (`cool`,
  `balanced`, `performance`) and a hwmon with `fan1_input` / `fan2_input` /
  `pwm1_enable`.
