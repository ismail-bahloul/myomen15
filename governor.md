# One governor, not three tools

[`dgpu-control.md`](dgpu-control.md) ends with the repo's own conclusion about
what to build next:

> The CPU side already has a governor (`power-profile-watch`) and a monitor
> (`omenmon`). The dGPU adds a real lever with **no owner**. The coherent thing
> to build is not "a GPU tool" but **one governor** over the levers that
> actually work — CPU power limits (`ryzenadj`), the GPU clock lock (NVML), the
> fans (EC), and the platform profile — instead of three that ignore each other.

This page is that design, and `evidence/omen-governor` is a reference
implementation. It is a **proposal**, not something installed: nothing here
changes the running system until you choose to adopt it.

## The four levers, and who owns each today

| Lever | Tool | Range | Measured behaviour | Source |
|---|---|---|---|---|
| CPU power limits | `ryzenadj` | STAPM / PPT-fast / PPT-slow / Tctl | writes take and hold; the SMU re-derives some fields a minute later (the drift) | [`firmware-limits.md`](firmware-limits.md), [`pm-table.md`](pm-table.md) |
| CPU frequency + EPP | `amd-pstate-epp` | governor, `scaling_max_freq`, `energy_performance_preference` | the 3.2 GHz cap is efficiency-neutral (~+2 %, within noise) for ~9 % less throughput; the *deeper* caps do improve work/joule | [`efficiency.md`](efficiency.md) |
| dGPU clocks | `nvidia-smi` | `--lock-gpu-clocks min,max`, `--lock-memory-clocks` | the clock lock works (1000 MHz holds 41 W); the power limit and the voltage do **not** exist on either OS | [`dgpu-control.md`](dgpu-control.md), [`dgpu-windows-undervolt.md`](dgpu-windows-undervolt.md) |
| Fans | EC setpoints, via `nbfc` | 0–100 % per fan | `nbfc set -s P` moves them (40 % → 2260/2213 RPM measured); the `my-nbfc` curve is tuned | [`ec-map.md`](ec-map.md) |

Plus the platform profile (`/sys/class/platform-profile/`: `cool` / `balanced`
/ `performance`), which the HP EC maps onto dGPU power limits via `\DPTC`.

**Today they have three owners**: `/usr/local/bin/power-profile` (+ its
`.service`, `.timer`), `power-profile-watch.service`, and `nbfc_service` — and
they do not know about each other. The one interaction that bites is already
documented: a write to `platform_profile` makes the EC re-apply its own limits,
and `power-profile-watch` exists solely to undo that. A "governor" that sets
the profile *and* the limits is therefore fighting its own side unless it is the
only writer.

## The modes

One name, one coherent tuple across all four levers. The CPU rows follow the
machine's already-tuned profiles (the 35 W / 85 °C AC setting and the 54 W perf
one); the `quiet` row is new, and the fan column is a *bias*, not a curve.

| Mode | CPU (`ryzenadj`) | cpufreq | dGPU (`nvidia-smi -lgc`) | profile | fans |
|---|---|---|---|---|---|
| `quiet` | 25 / 32 / 25 W, Tctl 80 | powersave, 2.8 GHz, `power` EPP | 0,1200 | cool | auto (nbfc) |
| `balanced` | 35 / 42 / 35 W, Tctl 85 | powersave, 3.2 GHz, `balance_power` | 500,1800 | balanced | auto (nbfc) |
| `performance` | 54 / 65 / 54 W, Tctl 90 | performance, 4.465 GHz | unlocked | performance | auto (nbfc) |
| `battery` | 15 / 18 / 15 W, Tctl 65 | powersave, 2.4 GHz, `power` | 0,400 | cool | auto (nbfc) |

`auto` is not a mode but a policy: pick `balanced`/`performance` on AC and
`battery` on battery, exactly as `power-profile` does today.

### The modes, measured

`evidence/gov-modes-test.sh` applies each mode and runs the fixed load from
[`efficiency.md`](efficiency.md)'s harness. Same load, four settings:

| Mode | mean clock | throughput | package power | work / joule |
|---|---|---|---|---|
| `battery` | 2.12 GHz | 4193 Mi/s | 12.80 W | **328** Mi/s·W⁻¹ |
| `quiet` | 2.71 GHz | 5682 Mi/s | 21.93 W | 259 |
| `balanced` | 3.07 GHz | 6462 Mi/s | 29.06 W | 222 |
| `performance` | 3.71 GHz | 7716 Mi/s | 50.54 W | 153 |

A clean monotone ladder: each step up buys throughput at a real, measured
efficiency cost — `battery` → `performance` is **+84 % throughput for −53 %
work per joule**. So the `quiet` and `battery` numbers are now measured points,
not guesses (though whether they are the *optimal* points on these curves is
still open).

## The coherence rules — the part that was missing

1. **One writer.** The governor must be the only thing that writes the CPU
   limits and the platform profile. Adopting it means retiring
   `power-profile.service`, `power-profile.timer` and
   `power-profile-watch.service`; the governor's own `watch` subcommand subsumes
   the watcher (same drift detection, generalised to re-apply the *active
   mode* instead of only AC).
2. **Profile first, then the limits.** Writing `platform_profile` makes the EC
   re-apply its own limits within ~1 s, so CPU limits written *before* it are
   clobbered. The profile goes first and the limits after — and this is not a
   guess: the first version of this governor wrote the limits first and the
   profile last, and one `apply quiet` went `25/32/25` → **`54/65/54`** three
   seconds later. The test caught the ordering; the code now encodes it.
3. **Fans are delegated, not rebuilt.** `nbfc`'s `my-nbfc` curve is tuned
   (hysteresis, a 12 % floor to stop the yoyo at 48–50 °C). The governor does
   not replace it, and the reference implementation leaves every mode on
   `auto`. Rebuilding a validated thermal loop on top of a working one would be
   a net loss.
4. **Read before write, every time.** The mode is applied only if the current
   state differs, so the governor is idempotent and cheap to run on a timer.
5. **Measure the effect, don't assume it.** `--status` reads the state back
   through the same instruments the rest of this repo uses (the PM table, NVML,
   hwmon, the profile attribute), so "applied" is never confused with "took".

## Reference implementation — `evidence/omen-governor`

```
sudo evidence/omen-governor status          # read every lever + temps, guess the mode
sudo evidence/omen-governor apply balanced  # dry-run: print the delta only
sudo evidence/omen-governor apply balanced --commit
sudo evidence/omen-governor auto --commit   # balanced/perf on AC, battery off it
sudo evidence/omen-governor watch           # the drift watcher (subsumes power-profile-watch)
```

It is `--commit`-gated: without it, nothing is written. It reads the PM table
directly (the `ryzen_smu` node is world-readable) and shells out only to
`ryzenadj`, `nvidia-smi`, `nbfc` and `systemctl`. Its mode table is one dict at
the top of the file.

It was exercised on this machine: `status` reads every lever and identifies the
active mode; `apply quiet --commit` moves all four and the limits **stay**
(`active mode: quiet`); restoring returned the machine to `35/42/35` at
3.2 GHz. Two things the test itself decided: the profile-before-limits ordering
above, and that a mode change writes the profile *persistently* — a mode is not
just a power setting, it owns the profile (`systemctl`-level ownership, rule 1).

## What is measured, and what is a design choice

- **Measured:** every lever's *existence and direction* (the tables above), the
  drift and the `platform_profile` interaction, the fan response to `nbfc set`,
  and now the **effect of each mode under load** (the ladder above).
- **Design choice, not measured optimum:** the exact per-mode *target* values.
  They sit on measured curves and behave as measured, but nothing here claims
  `quiet`'s 2.8 GHz or `battery`'s 2.4 GHz is the best point on its curve.

## Failure modes worth designing for

- **The drift.** The SMU re-derives STAPM/PPT-slow a minute or two after an
  apply, with no writer and no inotify event — so the only detector is reading
  the limits. The `watch` subcommand does exactly that, ~1 Hz, one `read()` of
  2.4 KiB.
- **The `platform_profile` clobber.** Any profile write makes the EC re-apply
  its own limits; with the governor as the only writer, its own writes are
  followed by its own re-apply, which is why rule 2 orders them.
- **A stale mode.** If someone sets the profile by hand, the governor's next
  tick sees a profile that does not match the active mode and re-applies — the
  same "adopt only what we set" rule `power-profile-watch` already uses.
- **Fans left manual.** If a mode biases the fans and is interrupted, `nbfc set
  -a` on the next `watch` start (or mode change) restores the curve.

## Adopting it

The reference implementation is deliberately a single script so it can be read
before it is trusted. To adopt it: install it beside `/usr/local/bin`, point one
`systemd` unit at `watch`, and retire the three `power-profile*` units.

## Tried, then reverted (2026-09-29)

Adopted briefly as the single writer (installed `omen-governor.service`, retiring
the three `power-profile*` units), verified live — `apply balanced` held at
`35/42/35 W`, 3.2 GHz, dGPU locked — and then **rolled back** to the three-process
stack.

Why: the consolidation is real (three units → one, the profile-before-limits
ordering encoded in code instead of worked around by a watcher, a readable
`status`), but it is a **refactor, not a gain** — `power-profile` already owned
all four levers, including the dGPU clock lock. And the mode *values* are design
choices: `auto` on AC picks `balanced` = **35/42 W**, hotter than the tuned AC
profile the old script applies (**28/36 W** — the one `efficiency.md` credits
with doing the cooling). So as-is it raised AC power.

Net: worth adopting only after aligning `MODES` with the tuned numbers. Until
then `power-profile` + `.timer` + `power-profile-watch` remain the writers;
`omen-governor` and `omen-governor.service` are kept here as the (working,
rehearsed) reference implementation. That
migration is left to you on purpose — this is the design and the tool, not a
change to a working setup.
