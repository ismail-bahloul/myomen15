# Energy per unit work, and whether the frequency cap earns anything

`record/03-open-questions.md` §3 left one measurement open, and §6 kept it open:
on this machine the AC profile caps **both** frequency (3.2 GHz) and power
(35 W). The question was whether the frequency cap earns anything, or whether
the power cap alone gives the same work per joule — in which case the cap would
be "doing nothing but hurting peak responsiveness".

Measured on AC under `amd-pstate-epp`, kernel `7.2.6-1-cachyos`. Each config: a
fixed all-core load (the loop from §3, `evidence/load.c`), a 20 s warmup, a 40 s
window, power + frequency sampled every second (`evidence/powsample.py`), the
re-apply units stopped so nothing clobbered a config.

## Correction first: the first run was ~2× low

The numbers originally on this page were **about half** the reproducible value —
`ac` measured 3079 Mi/s where the same config re-measures at ~6400. The machine
**rebooted between the two runs** (a Windows session), so they were different
boots, and the exact cause of the halving is **not established**. It is recorded
here, not papered over.

Three independent re-runs agree at ~6400 Mi/s for the same ~3.07 GHz config, so
the new numbers are the ones to trust:

```
eff-test.sh  'ac'        6391 Mi/s
governor     'balanced'  6461 Mi/s     (same CPU settings as 'ac')
direct       ./load      6426 Mi/s
```

A back-of-envelope cycle count agrees with ~6400, not 3079 (16 threads at
3.07 GHz needs ~16 cycles/iteration to give 3079 — implausible for this loop,
which fits ~8). **What the correction changes is the conclusion**, not just the
scale — see below.

## The result (reproduced)

| Config | Throughput | PPT VALUE SLOW | mean freq | Tctl | fan1 | mJ / Miter | Mi/s per W |
|---|---|---|---|---|---|---|---|
| **AC** — 35 W **+ 3.2 GHz cap** | 6391.2 Mi/s | 30.83 W | 3.07 GHz | 80.0 °C | 2276 | 4.824 | 207 |
| **35 W, no cap** | 6956.3 Mi/s | 34.18 W | 3.38 GHz | 82.6 °C | 2853 | 4.913 | 204 |
| **PERF** — 54 W, no cap | 7412.0 Mi/s | 45.92 W | 3.63 GHz | 90.0 °C | 3708 | 6.195 | 161 |
| governor `quiet` | 5682.2 Mi/s | 21.93 W | 2.71 GHz | 67.3 °C | 1367 | 3.859 | 259 |
| governor `balanced` | 6461.6 Mi/s | 29.06 W | 3.07 GHz | 75.1 °C | 2000 | 4.498 | 222 |
| governor `performance` | 7716.3 Mi/s | 50.54 W | 3.71 GHz | 89.8 °C | 3709 | 6.549 | 153 |
| governor `battery` | 4193.4 Mi/s | 12.80 W | 2.12 GHz | 65.2 °C | 1366 | 3.052 | 328 |

`mJ / Miter` = millijoules per million iterations (`PPT VALUE SLOW` ÷
throughput). `PPT VALUE SLOW`, a ~5 s average, is the package-power proxy for a
40 s run; `STAPM VALUE` has a 275 s constant and does not settle in 40 s, so it
is not used here. The three governor rows are the same harness with
[`governor.md`](governor.md) modes applied (`evidence/gov-modes-test.sh`).

## What it says now

1. **The 3.2 GHz cap is efficiency-neutral, not a win.** `ac` (capped) and
   `nocap` (35 W, uncapped) are within ~2 % on work per joule (207 vs
   204 Mi/s·W⁻¹) — and a *repeat of the same config* (`ac` 207 vs the governor's
   identical `balanced` 222) spreads ~7 %, so that 2 % is inside the noise.
   **This overturns the original conclusion**, which had the cap ~24 % ahead;
   that gap was an artefact of the low first run.
2. **The cap still costs throughput** — ~9 % (6391 vs 6956). So at 3.2 GHz its
   value is **thermals and noise, not energy**.
3. **54 W buys little and costs efficiency.** PERF is +6.6 % throughput over
   `nocap` for **+26 %** energy per unit work (161 vs 204 Mi/s·W⁻¹) — the
   original "54 W earns nothing" was too strong; it earns ~7 % of speed, at a
   real efficiency price.
4. **Deeper caps do earn their keep.** `quiet` (2.71 GHz) and `battery`
   (2.12 GHz) reach 259 and 328 Mi/s·W⁻¹ — 25 % and 60 % better than `ac`. So
   "capping helps" is true, but the *3.2 GHz* point is roughly flat; it is the
   **lower** caps that pay.

## The cap's cost depends on the workload

`evidence/st-ab.sh` closes the gap the 16-thread table leaves: the cap bounds the
*ceiling*, so its cost is small where the all-core ceiling is already low, and
large where a core would otherwise boost. It pins one thread to core 0, runs
3 alternating reps per config (to average out whatever slow state the SMU carries
between runs), and measures throughput plus power and temperature:

| Load | capped 3.2 GHz (28 W) | uncapped (28 W) | cost |
|---|---|---|---|
| 1 thread | 417.7 Mi/s @ 3.17 GHz, 10.4 W, 65.8 °C | 526.1 Mi/s @ 3.96 GHz, 13.7 W, 72.6 °C | **−20.6 %** |
| 16 threads | 6391 Mi/s | 6956 Mi/s | −8 % |

The 1-thread row is three reps per config, and the spread is tight (cap 417.4–
418.1, no-cap 525.8–526.3 Mi/s), so the −21 % is solid; it agrees with the older
`cap-single-thread.sh` run (−21 %, 418.8 vs 531.9).

So the cap taxes **light work ~21 %** — where the core is not hot and the cap
buys nothing — to keep *sustained* loads ~3.4 W cooler (30.8 vs 34.2 W, ~11 %).
It is a blunt instrument: the power cap already binds only under load and lets a
light thread boost to ~4 GHz; the **frequency** cap is what also neuters the
light case. If the goal is cool-and-quiet under load, the power cap and the fan
curve do that; the frequency cap's extra cost lands on responsiveness.

### A burst costs the same either way

The −21 % is a *sustained* single-thread figure. Real interactive work is bursty:
an app launch or a keystroke response occupies a core for well under a second.
`evidence/burst-peak.sh` runs that shape — six 1 s bursts on two cores, pinned,
sampled at 50 Hz from the PM table — capped vs uncapped:

| Burst (1 s, 2 threads) | peak PPT-fast | peak PPT-slow | peak Tctl |
|---|---|---|---|
| capped 3.2 GHz | 10.2 W | 8.1 W | 61.0 °C |
| no cap | 10.1 W | 8.1 W | 60.4 °C |

No difference: a burst peaks at ~10 W either way, ~3.7 W below the sustained
single-thread case, and Tctl is identical within noise. The extra power the cap
withholds is only spent when a core is held busy for many seconds — opening and
closing apps quickly does **not** reach it.

Beware the clock when measuring this: the PM table's per-core effective clock
(`0x3e0`) was seen to read **above the 4.465 GHz part limit** (6.35, 6.50 GHz)
on burst exit, so it must not be used as an instantaneous peak. Throughput and
power are the reliable instruments. See [`pm-table.md`](pm-table.md).

### What the cap removal actually costs thermally

The single-thread +26 % is not free, and the cost is **workload-shaped**. A
controlled A/B (`evidence/thermal-ab.sh`, sampled at 1 Hz, run in both orders to
cancel the "warmer second pass" bias) over idle → 1 thread → cooldown →
14 threads:

| Phase | OLD: 35 W **+ 3.2 GHz cap** | NEW: 28 W, **no cap** |
|---|---|---|
| idle | 57.5–60.8 °C, fan 1061–1143 | 59.4–59.7 °C, fan 1137–1143 |
| **1 thread, 60 s** | 59.9–64.5 °C, fan 1029–1139, 10.3 W | **73.2–73.3 °C**, fan 1606–1649, 15.0 W |
| **14 threads, 50 s** | 71.7–74.5 °C, fan 1526–1812, 27.9 W | 73.9–74.5 °C, fan 1879–1903, 27.1 W |
| cooldown | 57.0–61.0 °C | 62.3–62.6 °C |

So:

- **Idle and all-core are unchanged.** The 14-thread temp is the same (within
  ~2 °C) and the package power is the same or *lower* (27.1 vs 27.9 W) — the
  power cap, not the frequency cap, was doing the all-core work.
- **Only a sustained single thread gets hotter: +9…+13 °C and ~+500 rpm.** That
  is the 4.0 GHz boost spending 15 W in one core instead of 10 W at 3.2 GHz.
  Note it is very reproducible on the new side (73.2 / 73.3 °C across both
  orderings) and bounded: 73 °C is ~11 °C under the 85 °C AC limit, and the fan
  lands on a mid step (~1650 rpm, ~28 %), not at its ceiling.
- The extra heat is therefore a **noise** cost on the light path, not a
  throttling or durability one. It shows up on long single-threaded work — a
  build, a JS-heavy page, an emulator — not on app-launch bursts, which [cost the
  same either way](#a-burst-costs-the-same-either-way).

### The better instrument: a lower power cap, not a frequency cap

The frequency cap's cooling is really just "less all-core power", and a **power**
cap delivers that without touching the light case. Measured
(`evidence/cap-vs-power-test.sh`):

| Config | all-core | PPT-slow | Tctl | 1-thread |
|---|---|---|---|---|
| AC: 35 W **+ 3.2 GHz cap** | 6440 Mi/s | 28.25 W | 74.1 °C | **418.9 Mi/s** |
| **30 W, no cap** | 6676 Mi/s | 28.88 W | 76.5 °C | **529.1 Mi/s** |

Same all-core power and heat (within ~0.6 W and ~2 °C), and **+26 % on a single
thread**. So dropping the frequency cap and lowering the power cap to ~30 W keeps
the cooling and gives back the responsiveness. The cap was the wrong instrument:
the power cap binds only under load, the frequency cap binds always. The profile
now deployed as AC applies exactly this: **28 W, no frequency cap**
(`TDP_AC=28000`, `FREQ_AC=4465000`).

## The iGPU / SoC DPM level: a ~3 W idle lever (measured)

Everything above moves the **CPU** package. The SoC rail is shared with the
Radeon, and `amdgpu` exposes the iGPU's DPM levels — a lever no other page here
had touched. `power_dpm_force_performance_level` alone moves the idle draw:

| level | battery draw | Tctl | edge | fan1/fan2 | clocks |
|---|---|---|---|---|---|
| `auto` | **14.3–14.4 W** | 44–45 °C | 44 °C | 684/658 | sclk 400–716, socclk 400–975, fclk 1600, mclk 1600, dcefclk 847 |
| `low` | **11.4–11.5 W** | 44.5 °C | 43.5 °C | 650–700 | everything at its floor: 200 / 400 / 400 / 400 / 400 |

**−2.9 W, −20 % of the idle draw**, reproduced across four `auto`/`low`/`auto`
runs ([`evidence/igpu-dpm.py`](evidence/igpu-dpm.py)). That is a large fraction of
the whole VFIO dGPU win and needs no reboot — but it is not free:

- **The memory/fabric clocks go with it.** `low` takes `mclk`/`fclk` from 1600 to
  400 MHz, and a 128 MiB `memcpy` drops **10.9 → 6.2 GiB/s**. So this is a
  *quiet/eco* mode, not a default: fine for reading and writing, wrong under a
  browser or anything moving pixels.
- **It cannot be made selective, and the win is the memory, not the GPU.** Asking
  `manual` mode to hold `pp_dpm_mclk` / `pp_dpm_fclk` at their top level does not
  take (read back after the phase, both sit at 400). And `profile_min_sclk` — the
  GPU core pinned at the floor with the memory left at 1600 — saves **nothing**
  (14.54 W vs 14.62 W for `auto`). So the whole ~3 W is the memory/fabric/display
  clocks (`mclk`/`fclk` 1600→400, `dcefclk` 847→400); there is no cheap half of
  this lever to take.
- **No measurable noise change in the window.** The fan is EC-controlled and slow;
  fan1/fan2 stayed within their spread (650–720). The win is draw, not dB, over
  a 20 s sample.
- **It is not persistent.** The level resets to `auto` on reboot, so it is safe to
  try, and `auto` undoes it.

Not adopted by default — recorded as the lever it is.

## Caveats

- **One workload.** A branchy FP loop. Efficiency ordering is workload-dependent.
- **Run-to-run spread is ~7 %**, measured directly (the same 3.07 GHz / 35 W
  config gave 207 and 222 Mi/s·W⁻¹ in two runs). Differences under ~10 % are not
  resolved by one run each; A/B/A would be needed to tighten them.
- **The first-run anomaly (~2×) is unexplained.** The reboot between runs is the
  only known difference; a power-source or thermal-state difference is possible
  but was not captured.
- The iGPU/dGPU were not loaded — this is a CPU-package comparison only.

## Reproducing

```bash
gcc -O2 -pthread -o evidence/load evidence/load.c
./evidence/eff-test.sh          # ac / no-cap / perf
./evidence/gov-modes-test.sh    # the governor modes
python3 evidence/eff-analyze.py ac nocap perf gov-quiet gov-balanced gov-performance gov-battery
./evidence/st-ab.sh             # single-thread capped vs uncapped (3 reps each)
./evidence/burst-peak.sh        # burst peak power/heat, capped vs uncapped
./evidence/thermal-ab.sh        # thermal A/B across idle / 1 thread / 14 threads
python3 evidence/thermal-analyze.py old new
sudo python3 evidence/igpu-dpm.py auto low auto   # the iGPU DPM idle A/B
```

Tooling: `evidence/load.c`, `evidence/powsample.py`, `evidence/eff-test.sh`,
`evidence/gov-modes-test.sh`, `evidence/eff-analyze.py`, `evidence/st-ab.sh`,
`evidence/burst-peak.sh`, `evidence/thermal-ab.sh` + `evidence/thermal-analyze.py`,
raw samples in `evidence/autonomous-pass/eff-*.csv`,
`evidence/autonomous-pass/st-*.csv` and `evidence/autonomous-pass/thermal-*.csv`.
