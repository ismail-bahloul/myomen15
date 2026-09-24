# The `H2RA` region: a second, independent path to the fans

The DSDT declares an operation region the EC driver does not touch, and it is
mapped, readable, and full of live hardware state:

```
OperationRegion (H2RA, SystemMemory, 0xFE700000, 0x1000)
```

4 KiB of memory-mapped hardware state at `0xfe700000`, readable through
`/dev/mem`. The DSDT names eighteen of its fields; several of them correlate
exactly with hardware this repo had only been able to reach through the EC.

Read-only investigation. Nothing was written to it.

## The named fields, as measured

Every field the DSDT declares, read live:

| Field | Offset | Value | Notes |
|---|---|---|---|
| `FSUS` | `0x1B7` | 60 | |
| `FMR1` | `0x527` | 42 | a duty value |
| `FMR2` | `0x52F` | 42 | a duty value |
| `FS1H` `FS1L` | `0x530` `0x531` | 5, 66 | **fan 1 tachometer** |
| `FS2H` `FS2L` | `0x532` `0x533` | 4, 178 | **fan 2 tachometer** |
| `FAS1` | `0x534` | 29 | |
| `FAS2` | `0x535` | 29 | |
| `SFS1` | `0x53F` | 0 | |
| `SFS2` | `0x8CC` | 0 | |
| `BKBB` | `0x8FF` | 0 | |
| `VER1` `VER2` | `0xDD0` `0xDD1` | 0, 1 | version |
| `RSV1` `RSV2` | `0xDD2` `0xDD3` | 0, 0 | reserved |
| `CCI0`… | `0xDD4` | 0 | |
| `CTL0`… | `0xDD8` | 0 | control |

## The fan tachometers, confirmed independently

`FS1H:FS1L` as a big-endian `u16` is **the CPU fan speed**, to the RPM, every
time — and `FS2H:FS2L` is the GPU fan. Five simultaneous samples, zero
disagreement:

```
FS1=1344  FS2=1205   |  hwmon fan1=1344  fan2=1205
FS1=1380  FS2=1234   |  hwmon fan1=1380  fan2=1234
FS1=1388  FS2=1212   |  hwmon fan1=1388  fan2=1212
FS1=1350  FS2=1180   |  hwmon fan1=1350  fan2=1180
FS1=1347  FS2=1197   |  hwmon fan1=1347  fan2=1197
```

### Why this matters

The repo already knew two ways to read fan speed: the EC's `0xB0`/`0xB2`
(through `ec_sys`) and `hp-wmi`'s `fan1_input`/`fan2_input` (through the hwmon).
This is a **third one, on a different mechanism entirely** — a plain memory
region, no ACPI transaction, no EC mailbox, no WMI call.

That makes it a genuinely independent cross-check. The EC path and the `hp-wmi`
path could in principle share a bug or a stale cache; a direct `ld` from
`0xfe700000` cannot. Worth knowing before trusting either of them in an
experiment.

**Read only, though — not write.** The region is writable, and a controlled test
(§"The region is a status mirror") shows that writes to it change nothing. The
tachometers are a publication, not a control surface.

## A duty-value pair, not yet attributed

`FMR1` and `FMR2` (`0x527`, `0x52F`) both read **42** (0x2A) at the same instant
the EC reports a fan setpoint of 24 % and 22 %:

```
EC 0x2C (CPU setpoint) = 24       H2RA FMR1 = 42
EC 0x2D (GPU setpoint) = 22       H2RA FMR2 = 42
```

They do not match, so `FMR1`/`FMR2` are not a plain copy of the EC setpoints.
**A controlled fan sweep has since settled what they are** — see "The curve
tables, decoded" below: `FMR1`/`FMR2` are the last byte of two identical static
8-byte curves, and nothing in that window moves with fan speed.

## The rest of the region

Beyond the named fields the region has two more clusters that look structured:

```
0x520: 18 18 1b 1d 1f 22 28 2a | 18 18 1b 1d 1f 22 28 2a | 05 42 04 b2 1d 1d 03 03
0x8C0: … 07 00 … 1a 1a … 1a 1b 1f 26 28 … 1a 1b 1f 26 28 …
```

The two identical 8-byte runs at `0x520`–`0x527` and `0x528`–`0x52F`, and the
two identical 5-byte runs at `0x8E3` and `0x8EB`, are the two fans' entries in
two separate tables. **Decoded below.**

## The curve tables, decoded — and they are static

Driving the fans through `nbfc set -s` (0 → 100 %) and reading the region at
each step (`evidence/h2ra-sweep.sh`) settles both clusters and the
`FMR1`/`FMR2` question at once:

- **Both clusters are static.** `0x520`–`0x52F` reads
  `18 18 1b 1d 1f 22 28 2a` twice at *every* setpoint, and `0x8E3`/`0x8EB`
  read `1a 1b 1f 26 28` twice at every setpoint. So these are the firmware's
  **declared** fan curves, published but never driven — the same shape as the
  `SFS1`/`SFS2` finding above.
- **They decode to a fan curve in percent.** The 8-byte run is
  `24 24 27 29 31 34 40 42` (%), an ascending 8-step curve; the 5-byte run is
  `26 27 31 38 40`, a shorter one. Two copies each = the two fans.
- **`FMR1`/`FMR2` are part of the table, not live.** `0x527` and `0x52F` are the
  last byte of each 8-byte run (`0x2a` = 42) — constant, which is why they read
  42 while the EC setpoint was 24 %. The "second duty register" hypothesis is
  **falsified**: they are the top of the declared curve.
- **The live fan state is elsewhere.** The only fields that track the setpoint
  are the tachometers `FS1H:FS1L` (`0x530`–`0x531`) and `FS2H:FS2L`
  (`0x532`–`0x533`), big-endian `u16`: 20 % → 1166 RPM, 40 % → 2267,
  60 % → 3428, 80 % → 4549, 100 % → 5674 — a clean monotone map.

One field did drift with the setpoint without being a tachometer: `0x538`–
`0x539`, big-endian, `0x453b` → `0x4234` from 0 % to 100 %. Slow and fan-linked,
but not reduced to a unit. Recorded, not explained.

## The region is a status mirror, not a control channel — measured

This is the part that matters, and it is a **negative result**. The region is
writable (`/dev/mem` opens it `O_RDWR`, writes land and read back), so the
obvious hope was that writing to it would drive the hardware — in particular the
fan setpoints `SFS1`/`SFS2`, which the firmware itself declares but never writes.

**It does not work.** Tested on the keyboard backlight, which is the safest
field to experiment with because the failure mode is cosmetic.

### What was done

The keyboard backlight state is published at `0xEFC` (`LBRT`) and `0xEFD`.
Watching the region while the backlight key is pressed shows the EC writing it:

```
[18:03:58] 0xefd: 80->00
[18:04:04] 0xefc: 00->80, 0xefd: 00->80
[18:04:07] 0xefc: 80->00, 0xefd: 80->00
[18:04:09] 0xefc: 00->80, 0xefd: 00->80
```

So the EC **does** write this region. Two attempts were then made to write it
back, with the keyboard verified lit:

| Attempt | What it wrote | Read back? | Effect on the keyboard? |
|---|---|---|---|
| Direct `/dev/mem` write | `0xEFC = 0x80/0x00`, `0xEFD` likewise, `LCMC` bit 5 | **yes** | **no** |
| `\_SB.WMID.LM05` | the firmware's own method, `LBRT = WBUF[0]`, then commit | **yes** (`0x80 -> 0x00`) | **no** |

The second row is the decisive one: it is not a homemade write, it is the
**firmware's own method**, taken straight from the DSDT, invoked through
`acpi_call`. It changed the register exactly as its code says it would, and the
keyboard did not react.

### What that means

`H2RA` is a **one-way publication**: the EC writes its state there for the OS to
read, and does not act on what the OS writes back. The `LCMC` "commit" bit is
not a trigger the EC waits on from this side — or at least not from a write made
while the machine is running normally.

Consequences, stated plainly:

- **The fan setpoints `SFS1`/`SFS2` cannot be driven this way.** They are in the
  same region, and the region behaves the same way. The hope recorded earlier in
  this page — that `H2RA` was a control surface the firmware left unwired — is
  **falsified**.
- **The read side is still valuable.** The fan tachometers at `0x530`–`0x533`
  remain an independent cross-check of the EC and `hp-wmi` paths.
- **`H2RA` writes should not be attempted for fans.** Writing a fan setpoint that
  the EC may or may not honour is a risk with no demonstrated upside.

### Where the keyboard control actually is, still unknown

A 30-second sweep of all 256 EC registers while the backlight key was pressed
found no candidate: the changes were entirely the usual telemetry — `0xB0`/`0xB2`
tachometers, `0x2E`/`0x2F` fan duty, `0x57`/`0x58`/`0x48`/`0x49` temperatures,
`0x87` and `0x9D` counters. Nothing in the "user just pressed a key" category.

So the backlight is handled inside the EC, and not exposed as a register this
sweep could see. That may need the `_Q` query path or the SMM channel rather
than a register hunt.

## Reproducing

```bash
# what the EC publishes, and that it publishes it only when it wants
sudo python3 evidence/omenwatch.py 30      # press the backlight key during this

# the write test: the register changes, the hardware does not
sudo python3 evidence/omenkbd.py read
sudo python3 evidence/omenkbd.py brightness 100

# the firmware's own method, for comparison
printf '%s' '\_SB.WMID.LM05' > /proc/acpi/call ; cat /proc/acpi/call

# which H2RA bytes are a static declared curve, and which track the fans
sudo ./evidence/h2ra-sweep.sh
```

**Restore after experimenting.** `omenkbd.py save` before touching anything,
`omenkbd.py restore` after.
