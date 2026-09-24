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

**This does not mean it works — and it has now been tried, with a known-working
lever.** Driving the same road with a power limit (`Set PPT Limit`, ACMD
`0x00050001` → `R23B`) moved the SMU's limits not at all, while `ryzenadj` moved
the identical value instantly. The road is live but inert for that class of
control; a CO write here would plausibly be equally inert. Detail:
[`firmware-limits.md`](firmware-limits.md#the-second-road-measured-it-is-inert).

The interface answers today:

```
\_AOD.AM01                     -> 0x5
\_AOD.AM03                     -> [0x40, 0x10001, 0x10002, 0x20001, ...]   the command table
\_AOD.AM04 0x0005000A          -> [0x0, 0x0, ...]   the read path returns zeros
```

The read path returning zeros means there is no usable read-back — which is
exactly the trap this repo was caught by once before (a write that succeeds and
echoes a constant). The power-limit test above therefore judged the road by
**effect**, not by return value.

### The SMM handler behind `ASMI(0xB9)`, located in the image

The SSDT shows what `ASMI(0xB9)` actually is: `Method (ASMI, 1)` is just
`APMC = Arg0; Sleep (0x0A)` over `OperationRegion (PSMI, SystemIO, 0xB2, 2)` —
it writes the APMC port and raises an SMI, carrying nothing. The payload sits in
a shared region the SSDT declares as `OperationRegion (AODT, SystemMemory,
0xB6EA5018, 0x220C)`, whose first fields are the mailbox (`MBSN`, `MBVS`,
`MBCB`, `MBMC`) followed by the whole tuning block (`PPTL`, `TDCL`, `EDCL`,
`SCAS`, `COPS`, …). `R308` fills `AODT` and rings the doorbell; the SMM handler
reads `AODT` and acts.

That handler is identifiable in the flash image: it is **`AodSmmSsp`** (SMM
module GUID `5EA93CAF-A8DD-4400-9FF6-FE343BCAF308`, PE32, `0x4A04` bytes),
alongside `AodPei`, `AodDxe` and `AodSetupDxe`. It was unwrapped with the same
`TianoCompress` path [`firmware-limits.md`](firmware-limits.md) documents.

Two of its properties were measured, and they bear directly on whether the SMM
road could bypass the SMU gate:

- **It contains no SMU mailbox address.** A scan of the PE32 for Cezanne's SMN
  mailbox constants (`0x3B10528`, `0x3B10564`, `0x3B10998`, `0x3B10A20`,
  `0x3B10A80`, `0x3B10A88` — the addresses [`smu-raw.md`](smu-raw.md) reads and
  writes) finds **none**, and no hardcoded MMIO base either. `AodSmmSsp` does
  not poke the SMN mailbox the way `ryzenadj` does.
- **It depends on protocols, not addresses.** Resolving its decoded dependency
  expression against the image gives only generic UEFI protocols — MmBase
  (`F4CCBFB7-…`), MmAccess (`C2702B74-…`), PCD (`13A3F0F6-…`), the Metronome
  arch protocol (`26BACCB2-…`) — plus four *vendor* GUIDs absent from EDK2. One
  of those is AOD-private: `AB776607-6169-44E8-B8F1-50129D4A25DB` is referenced
  **only** by `AmdCpmOemSmm`, `AodDxe` and `AodSmmSsp`. **No SMU protocol
  appears.**

So the SMM handler reaches the SMU (if at all) through a lower AMD module
(fabric/SoC or `AmdCpmOemSmm`), not a private SMU handle of its own. **That
narrows the open question but does not settle it** — the same note stands under
[`firmware-limits.md`](firmware-limits.md#the-second-road-measured-it-is-inert):
the SMU mailbox is source-agnostic (both the OS and SMM submit the same SMN
write), so a gate that is a *policy in the SMU firmware on a recognised
command* would refuse an SMM-submitted copy too. The residual opening is that
`\AOD` raises an SMI and might reach a channel the MP1 mailbox is not — which is
why the write remains the only decisive test. Evidence:
[`evidence/aod-smm-handler.txt`](evidence/aod-smm-handler.txt).

### The Curve Optimizer branch itself, traced — and the AODT allocation confirmed

`AodSmmSsp`'s own command dispatcher (`fcn.00012f18`, ~6 KB, reached from the
software SMI `0xB9` registered in the module's entry point — matching
`ASMI(0xB9)` exactly) is a linear `cmp ecx, <MBCB literal>` chain, not a jump
table. `cmp ecx, 0x100032` is the `Set Curve Optimizer` case — confirming the
ASL's literal `MBCB = 0x00100032` write is exactly what the handler tests for,
and that `\AOD.AM03`'s `0x0005000A` is a UI-side descriptor id, unrelated to
the value actually placed in the mailbox.

On that branch, the handler decodes the caller-supplied 32-bit CO value: the
top nibble (core index) is correctly masked to 0–15, but a middle byte of the
same value is used **unmasked** as an array index into `AODT` (`base+0x174+idx`
and `base+0x1B4+idx·2`) — a real asymmetry against its masked neighbour two
instructions above, and the reason this looked like a candidate memory-safety
bug worth chasing.

It isn't one, and tracing why closes the question cleanly rather than leaving
it open. `AodSmmSsp` caches its `AODT` pointer in a global that is zero in the
static image and never written in that module — it has to come from a
companion driver. `AodDxe`'s `fcn.000116b0` settles it with a real
`gBS->AllocatePool(EfiACPIMemoryNVS, 0x220C, &Buffer)` — the exact size the
DSDT declares for `OperationRegion (AODT, SystemMemory, 0xB6EA5018, 0x220C)`,
in a memory type (ACPI NVS) stable enough across boots on a fixed platform for
the DSDT to hardcode that address as a literal. With the real allocation size
confirmed, the worst case for the unmasked index (`idx` up to 255) lands at
`base+0x273` and `base+0x3B2` — both comfortably inside the 8716-byte pool.
**Found, traced, not exploitable as an out-of-bounds write** — the missing
mask could still misdirect a value to the wrong internal `AODT` field if
triggered with an out-of-range index, but it does not escape the buffer.

One thread from this pass was left open, not chased further at the time:
`AodSmmSsp` references an EFI variable named `AOD_SETUP` twice (a
`GetVariable` call with correctly-checked `EFI_STATUS`), which did **not**
exist in `/sys/firmware/efi/efivars/` on this machine and is not among the
variables `efi-nvram.md` catalogues. Full trace, exact addresses, and the
extraction method (UEFITool's default full dump was needed — targeted GUID
extraction misbehaves on this image because `AodPei`/`AodDxe` each have
duplicate hits across the two Sure Start volumes): →
[`evidence/aod-smm-curve-optimizer-trace.txt`](evidence/aod-smm-curve-optimizer-trace.txt).

**That thread is now closed.** The `GetVariable("AOD_SETUP", ...)` call turned
out to gate the *entire* SMI command dispatcher, not just some side path — a
failed lookup (which it always was, since the variable never existed) bails
out before the dispatcher ever reaches the `Set PPT Limit`/`Set Curve
Optimizer` chain. Creating the variable for real (with a size correctly
computed to avoid an SMRAM heap overflow the dispatcher's own writes would
otherwise cause — see the write-up for why 1 byte very nearly became a real
bug) and rerunning the already-established PPT test showed the command chain
now runs, and the SMU still doesn't move. So the "second road, measured: it
is inert" conclusion in `firmware-limits.md` was correct, but had been
resting on an unverified assumption; it now rests on a decisive one. Full
account: [`evidence/aod-setup-probe/README.md`](evidence/aod-setup-probe/README.md).

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
EC 0xBA (OCPC) = 0x01     (0x00 later the same session -- EC-owned, see ec-map.md)
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

## 4. The `\AOD` read path, and the crash it led to

The write conclusion in §2 was reached without ever reading what `\AOD`
currently holds. There *is* a read path, and finding it cost a kernel panic —
which is the part worth recording.

### The read path exists

`AM05` fills a 200-byte output structure (`OBUF`) with the current state and
returns it. The fields are declared explicitly in the ASL, including the ones
this repo could not read through the SMU:

```
BCOS 0x57   curve optimizer scalar      BPPL 0x6C   PPT limit
BPPT 0x8C   PPT                          BTDL 0x70   TDC limit
BTDC 0x90   TDC                          BEDL 0x74   EDC limit
BEDM 0x94   EDC                          BPCS 0xA1   curve optimizer (COPS)
BSCA 0x98   scalar
```

The method is callable, and `acpi_call` accepts a buffer argument:

```
printf '%s' '\AOD.AM05 {0x01,0x00,0x01,0x00}' > /proc/acpi/call
cat /proc/acpi/call
-> {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, ... }
```

`AM01` answers `0x5` and `AM03` returns the command table, so the device is live.

### Why it cannot be read, yet

`acpi_call` copies the result into a fixed **256-byte** kernel buffer, so the
reply is cut off at roughly **42 buffer values — offsets `0x00`–`0x29`**. Every
field above `0x2A` is unreachable, and that includes both curve-optimizer
fields. The power limits at `0x6C`–`0x94` are also cut off — but those are
already available from the [PM table](pm-table.md), so the real loss is the
curve optimizer, which nothing else exposes.

The region those fields actually live in, `AODT` at `0xB6EA5018`, cannot be read
directly either: `/dev/mem` refuses it with `EPERM`, as it does all ACPI-resident
storage on this kernel.

### The attempt that panicked the machine

Enlarging that 256-byte buffer looks like a one-line fix. It is a DKMS module, the
source is right there, and the constant is unmissable:

```
/usr/src/acpi_call-1.2.2/acpi_call.c:27:#define BUFFER_SIZE 256
```

It was raised to 8192, the module rebuilt and reloaded, and the first call
returned normally — still truncated at 253 characters, so the module had not
taken the change. It was rebuilt again with `dkms build --force`.

**The machine then panicked: the screen died and the Caps Lock LED blinked.**
That blink is the kernel-panic indicator on this platform.

After the reboot the system had **rolled itself back**: `acpi_call.c` was back to
`BUFFER_SIZE 256`, the installed module was the original, and `pacman -Qkk
acpi_call-dkms` reported `0 altered files`. So the damage did not persist — but
it did happen, and the machine had to restart.

### What to take from it

1. **`acpi_call` is not a safe module to modify here.** Its buffers are passed
   into ACPI evaluation; changing their size changes what the kernel tells the
   firmware to write into. Bumping one constant is not a local change.
2. **A panic can look like success first.** The reloaded module answered a call
   correctly before the machine died. "It responded" was not evidence it was
   sane.
3. **The truncation stands.** There is no read-back for the curve optimizer on
   this machine through this tool, and the obvious workaround is the one that
   just crashed it.

### Where that leaves the curve-optimizer question

The SMU path (§2) is refused, proven on both OSes. The `\AOD`/SMM write path is
reachable and **still untested** — but it now has no read-back, and the reason is
not a firmware gate but a tooling limit that is dangerous to lift. Testing a
write there would mean judging it by effect alone, with no way to verify, on a
mechanism that already knocked the machine over once.

That is the honest state: not "impossible", and not "worth it either".

## 5. Also found

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

## 6. What is untested, and why

A `\AOD` write is opaque by construction: `R308` hands a value to the BIOS and
gets nothing back, so what the handler did can only be judged by effect. The one
write done here — a power limit, chosen because its effect is independently
known and readable — showed the road is inert for that class of control, and
was reversed cleanly. That is why a **Curve Optimizer** write is still not the
move, three reasons in order:

1. **The road does not drive the SMU.** A known-working lever through it moved
   nothing (see §2 and [`firmware-limits.md`](firmware-limits.md#the-second-road-measured-it-is-inert));
   a CO write would plausibly be equally inert.
2. **The read-back is unusable.** `\AOD.AM04` returns zeros, so even if CO did
   apply, it could not be read back — and the UXTU failure already showed a
   silent no-op looks applied.
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
