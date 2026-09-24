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
```

Tooling: `evidence/load.c`, `evidence/powsample.py`, `evidence/eff-test.sh`,
`evidence/gov-modes-test.sh`, `evidence/eff-analyze.py`, raw samples in
`evidence/autonomous-pass/eff-*.csv`.
