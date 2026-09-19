# Battery charge control: found, and reachable

This repo recorded battery charge thresholds as **unsupported** — `powerdevil`
says "not supported by kernel", `hp-bioscfg` exposes nothing, and the `BCTC` /
`BMNC` objects are read-only in the DSDT with writes going to an opaque SMM
handler.

That conclusion was about the *kernel interfaces*. Reading the DSDT shows the
mechanism is not opaque at all: HP's WMI methods `GBCC` and `SBCC` read and
**write** a named EC register, and `acpi_call` can invoke them right now.

Nothing has been written yet. This page records what exists and what it would
take, not an attempt to set a threshold.

## The find

`DSDT.dsl`, in device `\_SB.WMID` (`_HID = PNP0C14`, HP's WMI device):

```
Method (GBCC, 0, Serialized)      // "HP WMI Command 0x1F (BIOS Read)"
Method (SBCC, 4, Serialized)      // "HP WMI Command 0x1F (BIOS Write)"
```

The firmware's own debug strings name them. `GBCC` reads, `SBCC` writes, and both
operate on:

```
\_SB.PCI0.SBRG.EC0.MBDC     the charge-control register
\_SB.PCI0.SBRG.EC0.MBTS     the "main battery present/state" guard
\_SB.PCI0.SBRG.EC0.ADPP     the AC-adapter-present guard
```

`SBCC` masks and rewrites `MBDC` in several places, including one branch that
does nothing but clear bits:

```
If ((Arg1 == Zero))
{
    Local1 &= 0xE0
    ^^PCI0.SBRG.EC0.MBDC = Local1      // write
    Return (Local0)
}
```

So there **is** a writable charge-control register, and a firmware method to
write it. The earlier "opaque SMM handler" conclusion was about a different path
(the ACPI battery objects), not this one.

## It answers, right now

Via `acpi_call`, with no extra tooling and no reboot:

```
$ printf '%s' '\\_SB.PCI0.SBRG.EC0.MBTS' > /proc/acpi/call ; cat /proc/acpi/call
0x1                                     <- battery present/guard OK
$ printf '%s' '\\_SB.PCI0.SBRG.EC0.MBDC' > /proc/acpi/call ; cat /proc/acpi/call
0x0                                     <- charge control: nothing set
$ printf '%s' '\\_SB.WMID.GBCC' > /proc/acpi/call ; cat /proc/acpi/call
[0x0, 0x4, {0x00, 0xff, 0x00, 0x00}]    <- GBCC returns, consistently, 5/5 runs
```

`GBCC` returning `0x00` at byte 0 means "no charge control active". The trailing
`0x00 0xff` are the `Else` branch of the method — an explicit "not applicable"
pair. The method is live and callable; it simply reports that no threshold is
set, which is correct for the current state.

## Decoding `GBCC`'s return

From the method body, when `MBTS == 1`:

```
Local2 = MBDC
If ((Local2 & 0x18) == 0x18)          // bits 3 and 4 both set
{
    Switch (Local2 & 0x07)            // low 3 bits select a mode
    {
        Case (0) { Local1 = 0 }       // no control
        Case (1) { Local1 = 1 }
        Case (2) { Local1 = 2 }
        Case (4) { Local1 = 3 }       // -> reported as 3
        Default  { Local1 = 0 }
    }
}
Else { Local1 = 0 }
```

So the ACPI-side value is a **4-state enum**: none (0), 1, 2, 3 (which is
`MBDC & 7 == 4`). The mode is only recognised when `MBDC` has bits `0x18` set —
`MBDC = 0x00` therefore reads back as "no charge control", which is what we see.

## What implementing a threshold would actually require

### The argument space, decoded

`SBCC` branches on `Arg0`, and there are exactly two modes. `Arg0 = 0` and
`Arg0 = 0x63` both write `MBDC`, with **different bit encodings for the same
intent**:

| | `Arg0 = 0` | `Arg0 = 0x63` |
|---|---|---|
| clear the cap | `MBDC &= 0xE0` | `MBDC &= 0xE0` |
| cap mode 1 | `MBDC = (MBDC & 0xF9) \| 0x09` | `MBDC = (MBDC & 0xFA) \| 0x0A` |
| cap mode 2 | `MBDC = (MBDC & 0xFA) \| 0x0A` | `MBDC = (MBDC & 0xFC) \| 0x0C` |
| any other `Arg1` | writes anyway | returns `0x35` ("invalid") |

The `Arg0 = 0` path also has an early-out that never touches `MBDC`: if the
battery is *not* on AC (`ADPP == 0`) and `Arg1 == 1`, it returns `0x35` instead
of writing. Only the `0x63` path is guard-free.

After a successful write, both paths **wait for the EC to acknowledge**:

```
Sleep (0x64)                    // 100 ms
While ((MBDC & 0x10) != 0x10) { Sleep (0x64) }
```

So bit `0x10` of `MBDC` is a **completion flag**, and the method spins on it.
That is the read-back — no guessing required, the firmware itself confirms the
write landed.

### Return codes

| Value | Meaning |
|---|---|
| `0x34` | no branch matched (`Arg0` was neither `0` nor `0x63`) |
| `0x35` | battery not in a usable state, or AC absent for a mode that needs it |
| `0x36` | the mode is **already active** — the `MBST` bit test succeeded |

`0x36` is the one to watch for: it is not an error, it means the requested mode
was already set, so the method skipped the write.

### The problem: this battery advertises no modes

Read live:

```
MBTS = 0x1     battery present and usable          (guard passed)
MBST = 0x0     ** modes supported: bits 0-1 are both clear **
MBDC = 0x0     no charge control active
ADPP = 0x1     on AC power
ECON = 0x1     EC reachable
```

`SBCC` gates the `Arg0 = 0` path on `MBST`, and the code explains what the bits
mean:

```
Local1 = MBST
Local1 &= 0x03
If ((Local1 & 0x02) & (Arg1 << 1)) { return 0x36 }   // bit 1 = mode 2 supported
ElseIf ((Local1 & 0x01) & (Arg1 >> 1)) { return 0x36 }  // bit 0 = mode 1 supported
```

With `MBST = 0x00`, **neither bit is set**, so no charge-cap mode is advertised
as available. On the `Arg0 = 0` path that means every request falls through to
the `Else` branch and writes `MBDC` anyway — but the write would be setting a
mode the EC does not claim to implement.

The `Arg0 = 0x63` path is different: it does **not** check `MBST` at all, only
`ADPP`. It is the path the firmware uses when it wants to force the setting
regardless of what the battery advertises.

### What that means practically

This is the honest state of it:

- The **mechanism is reachable** and I have decoded it completely: which
  arguments, which bits, which guard, which completion flag, which return codes.
- The **write is not a blind guess any more** — the firmware waits for `MBDC &
  0x10`, so a failed write is observable, and `MBDC &= 0xE0` is a clean revert
  to "no cap" that both code paths share.
- But `MBST = 0` says the EC reports **no charge-cap mode available**, and this
  machine's battery is an HP-branded pack with no `charge_control_*` sysfs
  attributes. A write may well be accepted and ignored.

That last point is exactly the failure mode this repo has already been burned by
once — the UXTU write that succeeded and echoed a constant back. So the rule
applies: **a write is not evidence, a read-back is.**

### The order I would do it in

1. Record `MBDC` (now `0x0`) and `GBCC` (now mode `0`).
2. On AC (`ADPP = 1`, already true), call `SBCC(0x63, 1, 0, 0)` once.
3. Read `MBDC` back and wait for bit `0x10`; call `GBCC` again and see whether it
   reports mode `1`.
4. If `GBCC` still reports `0`, the write did not take — record that and stop.
5. Revert with `SBCC(0x63, 0, 0, 0)` regardless of the outcome.

**This writes to a live EC register on the battery.** The revert argument is
known and shared by both paths. It has since been done — see
[below](#the-write-was-done--it-works) — and it is reversible. What it does turns
out to be "stop charging", not "hold a threshold".

## The write was done — it works

The order above was followed, but through the EC bridge (`M041`) rather than
`SBCC`, so the timeout stays on this side. `SBCC` waits on the completion bit in
an **unbounded** AML loop:

```
While ((Local1 & 0x10) != 0x10) { Sleep (0x64); Local1 = EC0.MBDC }
```

If the EC did not acknowledge, that loop would spin forever inside the ACPI
interpreter, holding the EC lock. That risk is now measured away: the EC **does**
acknowledge, in about 200 ms.

The A/B, sampled once a second:

```
no cap    MBDC=0x00  status=Full         (6/6)
cap set   MBDC=0x1a  status=Discharging  (10/10)
reverted  MBDC=0x00  status=Full         (6/6)
```

Writing `MBDC = 0x0A` sets the mode (the EC raises `MBDC & 0x10` within ~200 ms),
and the EC **stops maintaining the battery on AC** — the pack discharges while
plugged in. Clearing it (`MBDC = 0x00`) restores `Full`.

The mode is not an echo: the firmware's own `GBCC` reports it.

```
MBDC = 0x00   GBCC = {0x00, ...}   no charge control
MBDC = 0x1a   GBCC = {0x02, ...}   mode 2
MBDC = 0x00   GBCC = {0x00, ...}   no charge control
```

### What the mode actually does — a longer test

The A/B above only shows that charging *stops*. Whether the mode **holds** a
level was then tested by leaving it set on AC and watching:

```
12:05:54  80%  Discharging 0x1a
12:13:06  70%  Discharging 0x1a
12:20:08  60%  Discharging 0x1a
12:26:23  55%  Discharging 0x1a   (test stopped here)
```

The pack discharged continuously from 100 % to 55 % — it **never plateaued and
charging never resumed**. So mode 2, as exercised here, is *"stop charging"*, not
"hold at a threshold". The test was cut off at 55 % deliberately; a threshold at
50 % or below cannot be excluded from this run.

That is a **different mechanism** from the firmware's own battery cap. The BIOS
"battery optimizer" discharges nothing — it lowers `BFCC`, the reported
full-charge capacity (see
[above](#capacity-registers-and-the-design-the-os-cannot-see)). The two are not
the same lever.

### What is settled, and what is not

- **Settled:** the register takes the mode, the EC acknowledges (bit `0x10`,
  ~200 ms), the firmware's own `GBCC` reports it back, charging stops, and
  clearing it restores charging immediately. Fully reversible.
- **Not settled:** what the modes *mean*. Mode 2 stops charging with no hold
  observed down to 55 %; whether it eventually resumes at some lower level is
  open, and mode 3 (`0x0C`) was not exercised at all.
- **Not persistent:** `MBDC` lives in EC RAM and is not written on boot, and the
  EC clears it on an AC transition (observed: it read `0x1a` on battery and was
  back to `0x00` once the charger was plugged), so a mode lasts until the EC
  resets or the charger moves. Persisting it is deliberately **not** done — see
  [below](#why-this-is-not-wired-to-run-at-boot).

Note that the sysfs `capacity` percentage is relative to `BFCC`, which the BIOS
optimizer already lowers. So the 55 % above is 55 % of 60.15 Wh, i.e. about 33 Wh
— roughly 47 % of the true 70.9 Wh pack.

Tooling: `evidence/batterycctl.py` — `status` / `capacity` / `set <0x0A|0x0C>` /
`clear` / `watch [min]`. Read-only unless `--yes`; always reversible with
`clear`.

### Why this is *not* wired to run at boot

Nothing here is made automatic, on purpose. Two measured reasons: `MBDC` is EC
RAM cleared on a cold boot, *and* the EC clears it on an AC transition — so a
boot unit alone would not even keep it. And more to the point, the effect is
"stop charging": re-applying that at every boot would leave a laptop that never
charges from the adapter. Until the modes are understood better — in particular
whether mode 3 (`0x0C`) behaves differently — this stays a manual tool.

To observe a mode across a discharge:

```bash
sudo python3 evidence/batterycctl.py set 0x0A --yes
sudo python3 evidence/batterycctl.py watch 60
```

## Capacity registers, and the design the OS cannot see

The DSDT's battery methods read three EC registers:

| EC | Field | u16 LE | Meaning |
|---|---|---|---|
| `0x70` | `BADC` | 6140 | design capacity (mAh) |
| `0x72` | `BFCC` | 5208 | full-charge capacity, as reported |
| `0x74` | `BADV` | 11550 | design voltage (mV) |

At 11.55 V that is **70.92 Wh** design and **60.15 Wh** full — the pack is a
70.9 Wh one, and the OS only ever sees the second number.

The reason is in the firmware. `UPBI` and `UPBX` fill *both* design and
last-full from the same register:

```
Local5  = EC.BFCC
PBIF[1] = Local5   // DesignCapacity
PBIF[2] = Local5   // LastFullChargeCapacity
```

So `energy_full == energy_full_design` in sysfs is not "no wear" — it is the
firmware copying one value into both fields. **The true design capacity is
declared (`BADC`) and then never exported**, which is why no userspace tool can
see a BIOS charge cap: it only ever sees 100 % of an already-capped number.

`full / design` reads **84.8 %** here. Whether that is the "battery optimizer"
setting exactly, or a cap plus some wear, needs the option toggled in the BIOS
and the register read again.

```bash
sudo python3 evidence/batterycctl.py capacity
```

## What this changes in the repo

- **"Battery charge thresholds: unsupported"** was true of the *kernel surface*
  and false of the *firmware*. The correct statement is: not exposed by
  `acpi_platform_profile`-style interfaces, but reachable through HP's WMI
  method, which is present and callable.
- The `BCTC` / `BMNC` read-only finding stands — those are the ACPI *battery*
  objects, a different mechanism from `EC0.MBDC`. Both are true.
- `/sys/class/power_supply/BAT0/` has no `charge_control_*` attributes, which is
  consistent: nothing in the kernel bridge wires HP's WMI method to the power
  supply class on this model.

## Useful context, measured

```
/sys/class/power_supply/BAT0/
  cycle_count        124
  energy_full        60060000   (60.06 Wh)
  energy_full_design 60060000   (no wear recorded yet)
  capacity           100
  status             Full
  voltage_now        12765000
```

## Reproducing the read-only part

```bash
call() { printf '%s' "$1" > /proc/acpi/call; cat /proc/acpi/call; }
sudo sh -c "$(declare -f call); call '\\_SB.PCI0.SBRG.EC0.MBTS'"
sudo sh -c "$(declare -f call); call '\\_SB.PCI0.SBRG.EC0.MBDC'"
sudo sh -c "$(declare -f call); call '\\_SB.WMID.GBCC'"
```

Note that the `DSDT` must be disassembled to read `SBCC`'s argument mapping —
`/tmp/acpi/DSDT.dsl` in the session that produced this page:

```bash
cp /sys/firmware/acpi/tables/DSDT /tmp/DSDT.aml && iasl -d /tmp/DSDT.aml
grep -n 'Method (SBCC' -A 110 /tmp/DSDT.dsl
```
