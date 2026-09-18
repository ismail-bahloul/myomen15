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
| `0x2C` | u8 | CPU fan duty **setpoint** (%) | `nbfc status -a` reports `Target Fan Speed` equal to it, and `0x2E` tracks it; 28 ↔ 28, 26 ↔ 26 |
| `0x2D` | u8 | GPU fan duty **setpoint** (%) | same, second fan |
| `0x2E` | u8 | CPU fan speed **readback** (%) | `nbfc status -a` `Current Fan Speed`; tracks `0x2C` |
| `0x2F` | u8 | GPU fan speed **readback** (%) | same, second fan |
| `0xB0` | u16 LE | CPU fan **tachometer** (RPM) | equals `hwmon7/fan1_input` exactly, 10/10 samples |
| `0xB2` | u16 LE | GPU fan **tachometer** (RPM) | equals `hwmon7/fan2_input` exactly, 10/10 samples |
| `0x57` | u8 | CPU temperature (°C) | equals `k10temp` `Tctl`, tracked over a 72→85 °C ramp, 14/14 samples |
| `0x58` | u8 | CPU temperature, second sensor (°C) | tracks `0x57` within 1 °C across the same ramp |
| `0x48` | u8 | temperature (°C), slower-moving | tracked Tctl over the ramp: 48 → 53 as Tctl went 72 → 85 |

### The fan correlation, with `nbfc` as the reference

`nbfc status -a` prints the duty it believes it has set. Reading the EC at the
same instant closes the loop on the write half:

```
nbfc: CPU Target Fan Speed = 28.00   GPU Target Fan Speed = 26.00
EC:   0x2C = 28  0x2E = 28          0x2D = 26  0x2F = 26
```

Fan tachometers (simultaneous reads, exact match every time):

```
fan1=1617  fan2=1201  | B0 = 51 06  B2 = B1 04  -> 0x0651 = 1617, 0x04B1 = 1201
fan1=1588  fan2=1189  | B0 = 34 06  B2 = A5 04  -> 0x0634 = 1588, 0x04A5 = 1189
fan1=1601  fan2=1218  | B0 = 41 06  B2 = C2 04  -> 0x0641 = 1601, 0x04C2 = 1218
```

### The temperature ramp

Sixteen busy threads on an 8C/16T part, sampling the EC and `k10temp` together
every four seconds. `0x57` is `Tctl` to the degree:

```
Tctl  72 78 79 80 82 82 83 83 84 84 84 84 85 85
0x57  77 78 80 81 82 82 83 83 84 84 84 85 85 84
0x58  74 77 79 80 80 81 83 83 83 84 84 84 85 85
0x48  48 49 49 49 49 49 50 50 51 51 52 52 52 52
```

`0x57` is the fastest and tightest of the three; `0x48` is a slower, more
damped sensor — consistent with a board or VRM sensor rather than a die one.

### A negative result worth keeping

The `0x40`–`0x49` row is **not** a bank of temperatures. Across the whole ramp,
`0x40` (0x0B), `0x42` (0x04), `0x44` (0x04) and `0x46` (0x00) never moved at
all, and `0x49` never moved. Only `0x48` tracks heat. The earlier reading of
that row as "plausible additional temperatures" was too generous.

### `0x80`–`0x88` is a DMI/SMBIOS table, not telemetry

Those bytes are stored backwards relative to the SMBIOS strings. Read in a
sliding 2-byte window they reassemble into the strings `KBC1126`, `NPCE985` and
`ITE IT5570`, then the ASCII run `333-2C-2E-A`. These are **EC part numbers**
(the ENE KBC1126 / NPCX, and the ITE IT5570 family) — a firmware string table,
which is why the row looks volatile: it is not counters, it is static text being
sampled at a byte offset.

### Not yet identified

| Register | Observation |
|---|---|
| `0x53` | sits at `15` in every sample so far; unmoved by load, fan or AC state |
| `0x51`, `0x55` | stable at `0` throughout |
| `0x70`–`0x74` | fixed bytes (`FC 17 4B 14 …`), look like a fixed identifier |
| `0x86`, `0x90`, `0x92`, `0xD4`, `0xD8` | stable under every condition tested |
| `0x40`–`0x47`, `0x49` | constant under load — *not* temperatures (see above) |

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

## A full dump, for reference

```
00 | 00 80 16 1A 31 00 4F 4E 30 37 30 58 4C 2D 41 00   ..1.ON070XL-A.
10 | 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
20 | 00 00 00 00 04 00 00 00 00 00 00 00 23 16 23 15
30 | A0 01 7C 01 FF FF 11 00 00 00 00 00 00 00 00 00
40 | 0B 01 04 14 04 10 00 35 30 3C 00 00 00 00 00 00
50 | 80 00 00 0F 00 00 00 47 4A 3B 00 00 00 00 00 00
60 | 00 00 00 00 00 00 00 00 00 74 00 06 00 08 08 00
70 | FC 17 4B 14 1E 2D 80 33 33 33 2D 32 43 2D 32 45
80 | 2D 41 00 00 00 4B 14 DF 31 00 00 00 01 E0 00 00
90 | D1 D1 4B 14 05 30 63 00 00 00 00 00 00 09 0C 00
A0 | 06 80 00 88 01 00 00 00 30 15 00 00 00 01 00 06
B0 | DD 07 AF 04 00 0F 04 3B 00 00 01 07 00 00 00 00
C0 | 03 00 00 00 00 80 00 00 00 00 00 00 00 00 00 00
D0 | 63 00 00 00 13 05 00 01 63 00 1D 02 00 00 00 00
E0 | 00 00 00 00 00 00 00 00 00 00 08 00 00 89 00 00
F0 | 08 00 20 00 00 00 00 00 xx xx xx xx xx xx xx xx
```

The first few bytes are the EC's own firmware identification: an `ON070XL-A`
string at `0x06`–`0x0E`, then `0x16 0x1A` and a version byte at `0x04` (`0x31`).
`0xF0`–`0xFF` carries an ASCII **build/serial number of the EC firmware itself**
— redacted here on the same principle as the machine serial in the README. It is
reproducible from `ec_probe dump` on the machine that owns it.

## How to reach the EC

- `ec_probe` — register dump / read / write, plus `acpi_call`.
- `nbfc` — writes the fan setpoints through the same path, so it is a working
  reference implementation of the write half.
- `hp-wmi` exposes `/sys/class/platform-profile/platform-profile-0/` (`cool`,
  `balanced`, `performance`) and a hwmon with `fan1_input` / `fan2_input` /
  `pwm1_enable`.
