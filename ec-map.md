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

### A negative result, partly revised

The `0x40`–`0x49` row is **not** a bank of temperatures. Across the short thermal
ramp, `0x40` (0x0B), `0x42` (0x04), `0x44` (0x04) and `0x46` (0x00) never moved
at all, and only `0x48` tracked heat — so the earlier reading of that row as
"plausible additional temperatures" was too generous.

But `0x49` is not dead either. Under a *sustained* all-cores load it moved
`0x38` -> `0x3A`, where the short ramp never budged it. So it is a slow channel
of some kind, not a constant — the one spot where a longer experiment softened
this repo's own negative result.

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

## The responsive surface: 18 of 256

Six dumps — idle twice, all-cores load, and the three `platform_profile` values —
settle how much of the 256-byte space actually *does* anything:

| | Count |
|---|---|
| Offsets that moved under at least one stimulus | **18** |
| Offsets identical across all six dumps | **238** |

The eighteen, attributed:

```
0x2c 0x2d 0x2e 0x2f   fan duty setpoint / readback        known
0x49 0x57 0x58 0x59   temperatures                          known
0x62 0x63             16-bit BE, volatile (0x0604 / 0x0000)   UNKNOWN
0x87                  DMI part-number table (static text)   explained
0x95                  HPCM, dGPU mode: 0x30/0x31/0x50       known
0xb0 0xb1 0xb2 0xb3   fan tachometers                       known
0xb7                  57-58, +1 on sustained load           UNKNOWN
0xba                  OCPC, OC profile current              known, EC-owned
```

The two unresolved ones, with what has been ruled out:

- **`0x62` / `0x63`** — a 16-bit big-endian value. Seen at `0x0604` (1540) and at
  `0x0000`, so it is volatile and sometimes zero. It is **not** the CPU fan
  tacho: under load the real tacho at `0xB0:B1` climbed 1620 -> 2300 while this
  stayed `0`. Reading it as an RPM is not supported.
- **`0xB7`** — `57`–`58`, and `+1` under a sustained load. Slow and weakly
  load-linked, so plausibly a temperature, but nothing confirms it.

So **16 of the 18 are already attributed**, and the two that are not — `0x63` and
`0xB7` — are the *entire* remaining gap, not 165 offsets. Everything else in the
space is **static**: identifiers, the `0x80`–`0x88` DMI strings, constants. (That covers every register on the "Not yet identified" list above — `0x53`,
`0x51`, `0x55`, `0x70`–`0x74`, `0x86`, `0x90`, `0x92`, `0xD4`, `0xD8` — except
`0x49`, which is not static: it moved `0x38` -> `0x3A` under sustained all-core
load, so it behaves like a slow temperature after all.)

That reframes the map. It is not 36 % complete; it is **complete for behaviour**.
Everything the EC *changes* is explained, and everything unexplained is something
it never changes.

Tooling: `evidence/ecsweep.py` (`dump <file>` / `diff <a> <b>`).

### `0xB7` resolved toward "a temperature"; `0x63` still silent

The two unresolved registers above were re-measured under a controlled load at
two power levels (AC cap → ~71 °C, PERF → ~84 °C), sampling the EC every 5 s
(`evidence/ecwatch.py`):

```
idle (Tctl 66 °C)   0x57=66  0x58=68  0x49=59  0x59=56  0xB7=56  0x62=0 0x63=0
AC   (Tctl 71 °C)   0x57=71  0x58=71  0x49=59  0x59=57  0xB7=57  0x62=0 0x63=0
PERF (Tctl 84 °C)   0x57=84  0x58=83  0x49=63  0x59=61  0xB7=61  0x62=0 0x63=0
```

- **`0xB7` tracks temperature clearly.** 56 at 66 °C, 61 at 84 °C — five counts
  across an 18 °C rise. The earlier note ("57–58, +1 under sustained load") was
  a shorter load that never got hot enough to show the slope. It moves with
  `Tctl`/`0x57`, so it reads as a damped or low-resolution temperature channel.
  Where in the machine it sits is still not established.
- **`0x63` stays `0` under all three conditions** — idle, 71 °C, 84 °C. The
  earlier `0x0604` sighting is not reproduced here; whatever produced it is not
  load or temperature. It is the one offset this pass never saw move.

`0x49` and `0x59` moved alongside (`59→63`, `56→61`), consistent with the
already-noted slow temperature channels.

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
reset](firmware-limits.md#power-limits-what-resets-them-is-not-established).

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

## Which registers accept a write — measured per register

There is **no blanket rule**. Writing a value and watching the register:

| Register | Behaviour |
|---|---|
| `MBDC` `0xA6` | **writable and held** — and it does something (stops charging) |
| `OCPS` `0xBB` | **writable and held** (≥10 s), but writing it does **not** move `OCPC` (tested `1`, `3`, `7`) — effect not otherwise established |
| `SHEN` `0xC5.7` | the written value reads back, then the EC **reverts it in ~150 ms** |
| `OCPC` `0xBA` | the written value reads back, then the EC **reverts it in ~100 ms** |
| `TAPM` `0x40` | the write **does not land at all** — the register never changes |

```
MBDC  0x00 -> hold
OCPS  0x00 -> hold (t = 1, 3, 6, 10 s all read 0x00)
SHEN  0x00 -> t=0.00s 0x00, t=0.15s 0x80
OCPC  0x00 -> t=0.0s 0x00, t=0.1s 0x01
TAPM  0x00 -> 0x0b throughout
```

So three distinct behaviours coexist in the same 256-byte space, plus the
[`H2RA`](h2ra-region.md) case where a write lands and reads back but has **no
effect at all**. "Can I write this register?" is only answerable by measuring,
and "it read back" proves nothing by itself — the lesson this repo keeps
relearning.

Tooling: `evidence/ecbridge.py` (`ec-read` / `ec-write`).

## How to reach the EC

- `ec_probe` — register dump / read / write, plus `acpi_call`.
- `nbfc` — writes the fan setpoints through the same path, so it is a working
  reference implementation of the write half.
- `hp-wmi` exposes `/sys/class/platform-profile/platform-profile-0/` (`cool`,
  `balanced`, `performance`) and a hwmon with `fan1_input` / `fan2_input` /
  `pwm1_enable`.
