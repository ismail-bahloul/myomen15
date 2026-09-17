# HP OMEN 15-en1xxx — firmware, power and undervolt notes

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

What the firmware on this laptop actually allows, how each conclusion was
established — and what it refused.

**Machine:** HP OMEN Laptop 15-en1xxx · AMD Ryzen 7 5800H (Cezanne) · BIOS AMI
F.30 (2025-10-21) · NVIDIA RTX 3070 Mobile · dual-boot CachyOS + Windows 11.

## The short version

| Question | Answer |
|---|---|
| Can I undervolt, or use Curve Optimizer? | **No.** The SMU refuses the whole OC/CO command family — on Linux *and* on Windows. |
| Can I set a power limit in the BIOS? | That setting is **inert** on this machine; the HP EC owns those values. |
| Do power limits written by the OS stick? | **Yes** — with one exception: writing `platform_profile` makes the EC re-apply its own. |
| Can I modify the BIOS? | **No** — HP Sure Start is active, and the update payload cannot even be extracted. |
| Can I cap battery charging? | **No.** The ACPI objects are read-only and the writes go to an opaque SMM handler. |

## What is actually interesting here

Not the answers — those are small. What is interesting is that they are
*measured*, and that the wrong turns are kept, because that is where the method
is visible.

- **The Curve Optimizer gate is firmware-side, and proving it took more than
  trusting a tool.** UXTU on Windows *appears* to apply a CO offset — it updates
  its UI and looks like it worked. Its own diagnostic log records **20 failures
  out of 20** writes. The verdict came from probing the SMU directly, over the
  same access path and with the same message IDs the Linux side uses.
  → [`record/02-curve-optimizer-verdict-windows.md`](record/02-curve-optimizer-verdict-windows.md)
- **A benchmark "gain" that was never real.** The efficiency improvement
  originally measured was noise from thermal soak: the offset it was attributed
  to had never been applied. The run-to-run spread of *identical* configurations
  was ±3 % — the same size as the "effect".
- **A conclusion of mine was wrong, and an experiment said so.** I had concluded
  that the EC periodically rewrites OS-written power limits. A controlled A/B —
  ten minutes with the fan daemon running against ten minutes with it stopped —
  showed **zero** reverts in either condition, and pointed at a different trigger
  entirely. → [`firmware-limits.md`](firmware-limits.md)
- **What the firmware seeds at POST is observable**, by logging the limits in
  force *before* the OS writes anything. That is what proved the BIOS power
  setting does nothing.

## What is in this repository

| Path | What it is |
|---|---|
| [`firmware-limits.md`](firmware-limits.md) | The living reference — current conclusions only: BIOS power semantics, the Curve Optimizer gate, Sure Start, what resets an OS-written profile, and what is unsupported. |
| [`record/`](record/) | The point-in-time investigation, kept as written. Start with the Linux report, then the Windows verdict. |
| [`evidence/`](evidence/) | Tooling and raw data: the SMU prober (`smu.cs`), the load generator (`load.cs`), all 26 benchmark runs, and the two A/B CSVs. |

## Caveats

- **One machine.** This is the behaviour of one 15-en1xxx on BIOS F.30. Other
  revisions, or a BIOS update, can differ.
- **The OC/CO gate is HP's, not AMD's.** That is consistent with the missing BIOS
  menu, the empty `Custom Core Pstates` form and Sure Start — but the mechanism
  behind the refusal is not known. Only the refusal is.
- **"It was written" is not "it took effect".** One finding in here is a write
  that succeeds and echoes a constant back, which is why every claim about a
  write is backed by a read-back.

## Related

The configuration all of this was measured on — the CachyOS setup, VFIO GPU
passthrough, pro-audio chain, and the boot-time work — lives in
[ismail-bahloul/dotfiles](https://github.com/ismail-bahloul/dotfiles).
