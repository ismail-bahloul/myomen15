# `AOD_SETUP` is the AMD Overclocking menu

The `aod-setup-probe` experiment treated `AOD_SETUP` as an opaque buffer: a
variable the `\AOD` SMM dispatcher gates on, created as **1020 zero bytes** just
to open that gate. The static IFR shows it is something else entirely — the
**AMD Overclocking ("AOD") setup menu**, and it is read **at POST**, not only by
the SMM handler.

## What the variable actually is

`AodSetupDxe` declares varstore `AOD_SETUP` (`5ed15dc0-edef-4161-9151-6014c4cc630c`,
**1020 B**) with **207 options** — the whole AMD Overclocking menu:

| off | option |
|---|---|
| 38 / 42 | Custom CPU core frequency / voltage (mV) |
| 48 | Disable SMT |
| 72–135 | the memory-timing menu (duplicates the CBS one) |
| 135 | FCLK |
| 142 / 143 | **Precision Boost Overdrive** and its limit mode |
| 144 | **PPT limit** (socket power) |
| 148 / 152 | **TDC limit** (CPU / SoC) |
| 156 / 160 | **EDC limit** (CPU / SoC) |
| 165–182 | silicon-health override, max CPU/GPU boost, max temp |
| 184–199 | VDDP / VDDG / VDDIO voltages |
| 327 / 331 | Custom GFX core frequency / voltage |
| 335 | SoC/uncore voltage (VDD_SOC) |
| 339 | ECO Mode |
| **368 / 369 / 370** | **Curve Optimizer** (enable / direction / magnitude) |
| 221–327, 564, 566 | mostly *hidden* numerics — plausibly the per-core CO table, DRAM latency enhance |

## Who reads it — and why this matters

The `AOD_SETUP` GUID appears in **`AodPei`** (a **PEI** module, i.e. POST), plus
`AodDxe`, `AmdCpmOemSmm` and `AodSmmSsp`. `AodPei`'s own strings contain
`AOD_SETUP`. So the menu's values are read **at boot**, not only when an OS sends
an `\AOD` SW-SMI.

## Result (2026-09-29) — the POST path is inert too

`AOD_SETUP` was created **populated**, not all-zero, and the machine rebooted:

| off | value | meaning |
|---|---|---|
| 142 | 1 | Precision Boost Overdrive = Enabled |
| 143 | 2 | PBO limits = Manual |
| 144/145 | 45000 | PPT limit = 45 W (u16) |
| 368 / 370 | 2 / 10 | Curve Optimizer = All Core, magnitude 10 |

All within the IFR domains (CO ≤ 30; PPT ≤ 65535). The write landed — `DataSize
= 0x3FC`, visible in efivars — but the SMU did **not** move:

```
STAPM 28 | PPT FAST 36 | THM 85 | CPU max MHz 4465   (before)
STAPM 28 | PPT FAST 36 | THM 85 | CPU max MHz 4465   (after)
```

**`AodPei` does not apply the AMD Overclocking menu at POST** — or if it does,
the EC overrides the result. Either way the populated menu is inert: the last
firmware-side lever is closed, exactly like CBS/PBS (power) and CBS (memory).

Caveat, kept honest: this tests PPT/limits (readable) decisively. Curve Optimizer
has no read-back, so "CO was applied" cannot be ruled out by this probe alone —
but nothing else moved, which is the shape of "nothing was applied".

## What that changes about `aod-setup-probe`

That experiment created `AOD_SETUP` as **1020 zeros** (deliberately, to size the
SMRAM pool past every write offset) and then sent the runtime SMM command
`Set PPT Limit`. It answered *"is the gate the blocker?"* — no — and *"does the
runtime command path move the SMU?"* — no. Both stand.

But it never tested the **POST-time application of the menu's values**: with an
all-zero `AOD_SETUP`, `AodPei` had nothing configured to apply. Two things were
conflated and are now separable:

1. the **gate** (does the variable exist) — closed experimentally, not the blocker;
2. the **contents** (does AodPei apply a populated OC menu at POST) — **untested**.

Whether all-zeros is even a faithful "factory" state is unknown: the menu is
hidden (greyed), so `AOD_SETUP` was never saved, and there is no default variable
to compare against.

## The experiment this suggests (not run)

Populate `AOD_SETUP` as the menu would — e.g. a Curve Optimizer offset
(`off=369/370`) or a PPT value (`off=144`) — reboot, and read the PM table. If
`AodPei` drives the SMU at POST, this is a working lever (and specifically the
Curve Optimizer the rest of the repo found refused everywhere else). If it does
not, the OC menu is inert like the rest of the firmware surface.

Same discipline as before: rehearse in QEMU/OVMF, one change, revert via
`dmpstore -d`, and note that unlike `Setup` the SMM handler also reads this
buffer, so a malformed one touches SMRAM — size it correctly (1020 B).
