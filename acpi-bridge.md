# The ACPI bridge: what the firmware exposes and Linux ignores

Reading the 16 SSDTs — never done before in this repo — turned up three things
the DSDT alone did not show: a **generic EC and I/O byte bridge** the firmware
provides for free, an **AMD overclocking interface** with a Curve Optimizer path
that this repo had declared dead, and the **HP performance-mode selector** the
README listed as "not located on the Linux side".

Everything below is read-only unless stated. The bridge was verified against
`ec_probe` and agrees exactly.

## 1. A generic EC / I/O bridge (SSDT12) — verified

SSDT12 declares byte-level read/write methods for **any** EC register and **any**
I/O port:

```
\_SB.PCI0.SBRG.EC0.M040 <offset>         read  any EC byte (0x00–0xFF)
\_SB.PCI0.SBRG.EC0.M041 <offset> <val>   write any EC byte
\_SB.PCI0.SBRG.EC0.M31A <port>           read  any I/O port byte
\_SB.PCI0.SBRG.EC0.M319 <port> <val>     write any I/O port byte
```

They build a one-byte `OperationRegion` at the requested address, under the EC
mutex, and read or write it. The firmware ships this; no kernel driver uses it.

**Verified against `ec_probe`**, six registers, exact agreement:

```
              M040    ec_probe
0x57           0x45    69       temperature
0x58           0x45    69       temperature
0x40           0x0b    11       TAPM
0xB0/0xB1      0x28 06 1576 RPM (fan 1 tachometer)
0xA6           0x00    0        MBDC (battery charge control)
```

This is a **fourth independent path to the EC**, after `ec_sys`, `hp-wmi` and
the `H2RA` memory region.

`M31A` reads I/O ports directly. Port `0x62`/`0x66` (the EC's own command/data
ports) return 0, but `0xB2` — the **AMD SMM command port** — reads `0xe4`:

```
IO 0x62 = 0x00   EC command
IO 0x66 = 0x00   EC data
IO 0xb2 = 0xe4   AMD SMM / APMC
```

`M319` writes any I/O port, which means the SMM channel is reachable from Linux
through a firmware-provided method. Nothing in the kernel exposes that.

Tooling: `evidence/ecbridge.py` (read-only by default).

## 2. The `\AOD` interface: the Curve Optimizer path this repo missed

SSDT2 declares a second `PNP0C14` device, `\AOD` (`_UID = "AOD"`), whose methods
`AM01`–`AM08` dispatch through `WMAA`. Its command table is readable, and it
speaks in literal strings:

```
Set PPT Limit              Set TDC Limit           Set EDC Limit
Set Scalar                 Set DRAM Map Inversion
Set Curve Optimizer        Set IOD VDDG
Set Soc TDC Limit          Set Soc EDC Limit       Set Dram Latency Enhance
Set EDC Throttler Control
```

`Set Curve Optimizer` is command `0x0005000A`:

```
Method (R308, 1, NotSerialized)
{
    CreateDWordField (Arg0, 0x04, SVAL)
    MBVS = 0x05
    COPS = SVAL
    MBCB = 0x00100032
    ASMI (0xB9)          // -> writes I/O port 0xB2
}
```

### Why this matters

The repo's central negative result is that **Curve Optimizer is refused by the
SMU** — proven on Linux with `ryzenadj`, and cross-checked on Windows through
UXTU's own PawnIO path. Both of those go through the **SMU mailbox**.

`R308` does not. It writes `MBCB` and pokes **SMM through I/O port `0xB2`**, the
AMD APMC channel, i.e. it asks the BIOS, not the SMU. That is a genuinely
different road, and it is the one HP's own software uses.

**This does not mean it works.** The SMM handler may simply forward to the same
SMU and get the same refusal. But the honest statement is: the interface exists,
it is documented by the firmware itself down to the command ID, and **it has
never been tried**. The repo's "do not chase CO" conclusion was about the SMU
path, and it stands for that path. It does not cover this one.

The interface answers today:

```
\_AOD.AM01                     -> 0x5
\_AOD.AM03                     -> [0x40, 0x10001, 0x10002, 0x20001, ...]   the command table
\_AOD.AM04 0x0005000A          -> [0x0, 0x0, ...]   the read path returns zeros
```

The read path returning zeros means there is no usable read-back — which is
exactly the trap this repo was caught by once before (a write that succeeds and
echoes a constant). Anything done here must be verified by **effect**, not by
return value.

## 3. The HP performance-mode selector (`OCPC` / `OCPS`)

The README said HP's own thermal mode "has not been located on the Linux side".
It is in the EC, at two adjacent registers, and the DSDT shows the whole
mechanism:

| Register | Offset | Meaning |
|---|---|---|
| `OCPC` | EC `0xBA` | current performance profile (0–6) |
| `OCPS` | EC `0xBB` | highest selectable profile |

Reading them today:

```
EC 0xBA (OCPC) = 0x01
EC 0xBB (OCPS) = 0x07
```

And `PWLC` (DSDT 17344) maps the profile index to **dGPU power limits in mW**,
via `\DPTC`:

| `OCPC` | `DPTC(0x05)` | `DPTC(0x06)` | `DPTC(0x07)` |
|---|---|---|---|
| 0 | 54000 | 65000 | 54000 |
| 1 | 50000 | 65000 | 54000 |
| 2 | 45000 | 45000 | 45000 |
| 3 | 35000 | 35000 | 35000 |
| 4 | 25000 | 25000 | 25000 |
| 5 | 25000 | 25000 | 25000 |
| 6 | 15000 | 15000 | 15000 |

The profile is switched by EC query events, not by a WMI command:

```
_Q8C:  OCPC = OCPS          // apply the set profile
_Q8E:  if (OCPC < OCPS) OCPC++   // cycle up
```

So `OCPC` is a **mode selector that already exists in the EC**, and `\DPTC` is
callable directly. On this platform it drives the dGPU's power limit rather than
the CPU's — so it is not the CPU "thermal mode" the README was looking for, but
it is the same family of control, and it is a live, writable register.

## 4. Also found

| Path | What it does | R/W |
|---|---|---|
| `\_SB.WMID.LM02` | read keyboard RGB (`H2RA` `0xEE3`, 12 bytes) | R |
| `\_SB.WMID.LM03` / `LM05` | **write** keyboard RGB and brightness, then commit via `LCMC` | W |
| `\_SB.WMID.GM2D` | fan RPM from EC `0xB0`–`0xB3` | R |
| `\_SB.WMID.GM11` | fan tacho from `H2RA` `FMR*`/`FS*` | R |
| `\_SB.WMID.GM1A` / `GM22` | **write** dGPU power state (`HPCM`, `NVDO`, `NPCF`) | W |
| `\_SB.WMID.SFCS` | BIOS/SMM command 0x29 — candidate for fan/thermal policy | W |
| `\_TZ.THRM._SCP <0\|1>` | ACPI thermal policy, writes EC `TAPM` bit 4 | W |
| `\_DPTC <fn> <mW>` | dGPU power limit through the SMU | W |
| `\_SB.PCI0.SBRG.EC0.SMRD` / `SMWR` | SMBus mediated by the EC | R/W |

The RGB one is notable: the keyboard is 4-zone RGB, the data lives in `H2RA` at
`0xEE3` and `0xEF0` (two 12-byte copies) with a commit bit at `0xEE0` bit 5, and
`hp-wmi` on Linux exposes none of it.

## 5. What is untested, and why

Everything in sections 2–4 that writes has been left alone. Three reasons, in
order:

1. **The read-back is unusable.** `\AOD.AM04` returns zeros, so a CO write here
   cannot be verified the way the repo now verifies everything else. The lesson
   from the UXTU failure applies directly.
2. **SMM is opaque by construction.** `R308` hands a value to the BIOS and gets
   nothing back. There is no way to know what the handler did with it.
3. **The risk is asymmetric.** The repo's value is that it documents a machine
   that still works. A rejected SMU command is harmless; a mis-used SMM command
   on a firmware-owned register is not obviously so.

What *can* be done without writing:

- Dump all 256 EC registers through `M040` and diff against `ec_probe` — a
  cross-check of two independent paths, free.
- Read `OCPC`/`OCPS`, `TAPM`, `SARS`, `GPUT` and the rest of the named offsets
  while changing *reversible* things (AC state, `platform_profile`, fan load)
  to see which move.
- Read the remaining SSDTs' declared regions for anything else new.

## Reproducing

```bash
# the bridge, read-only
sudo python3 evidence/ecbridge.py named
sudo python3 evidence/ecbridge.py io-read 0xb2

# the AOD command table
printf '%s' '\AOD.AM03' > /proc/acpi/call ; cat /proc/acpi/call

# the performance profile, in the EC
sudo python3 evidence/ecbridge.py ec-read 0xba
sudo python3 evidence/ecbridge.py ec-read 0xbb
```

The SSDTs must be disassembled first:

```bash
for i in $(seq 1 16); do cp /sys/firmware/acpi/tables/SSDT$i /tmp/; done
for f in /tmp/SSDT*.aml; do iasl -d -p /tmp/$(basename $f .aml) $f; done
grep -n 'Method (R308' /tmp/SSDT2.dsl
grep -n 'Method (M040' /tmp/SSDT12.dsl
```
