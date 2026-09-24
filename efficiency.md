# Energy per unit work, and whether the frequency cap earns anything

`record/03-open-questions.md` §3 left one measurement open, and §6 kept it open:
on this machine the AC profile caps **both** frequency (3.2 GHz) and power
(35 W). The question was whether the frequency cap earns anything, or whether
the power cap alone gives the same work per joule — in which case the cap would
be "doing nothing but hurting peak responsiveness".

Measured, on AC, under `amd-pstate-epp`, kernel `7.2.6-1-cachyos`. Three
configs, each: a fixed all-core load (the same loop as the Windows harness in
§3, `evidence/load.c`), a 20 s warmup, a 40 s measurement window, and power +
frequency sampled every second (`evidence/powsample.py`). The re-apply units
(`power-profile-watch`, `power-profile.timer`) were stopped for the run so
nothing clobbered a test config, and restored after.

## The result

| Config | Throughput | STAPM VALUE | PPT VALUE SLOW | mean freq | Tctl | fan1 | **nJ / iteration** |
|---|---|---|---|---|---|---|---|
| **AC** — 35 W **+ 3.2 GHz cap** | 3079.6 Mi/s | 12.86 W | 20.77 W | 3.07 GHz | 71.2 °C | 1594 | **6.74** |
| **35 W, no cap** | 3787.5 Mi/s | 16.45 W | 33.45 W | 3.72 GHz | 81.8 °C | 2277 | **8.83** |
| **PERF** — 54 W, no cap | 3739.4 Mi/s | 20.06 W | 34.66 W | 3.75 GHz | 83.0 °C | 2806 | **9.27** |

Power caveat, stated up front: `STAPM VALUE` has a 275 s time constant and does
**not** settle inside a 40 s window, so it understates package power here —
badly for the capped config. `PPT VALUE SLOW` (a ~5 s average) is the honest
proxy for a 40 s run, and is what the nJ/iteration column uses. STAPM is kept
beside it only for continuity with §3, which named it.

## What it says

Two things fall out, and the second overturns the §3 guess.

1. **Raising the power limit to 54 W earns nothing on this workload.** PERF
   (3739 Mi/s) is the same as 35 W-no-cap (3788 Mi/s) — a 1.3 % difference,
   inside the ±2.5 % run-to-run soak noise this repo already measured. The load
   simply never needs 54 W: the 35 W-no-cap run drew 33.45 W (just under its
   cap) and PERF drew 34.66 W, both far below 54. So `apply_perf`'s power
   headroom is unused by a sustained all-core load; its only real effect there
   is the `performance` governor.

2. **The frequency cap is the most efficient config, not a no-op.** 6.74
   nJ/iteration against 8.83 (no cap, same 35 W) and 9.27 (PERF). So the power
   cap *alone* does **not** give the same work per joule — it is ~24 % worse.
   The cap earns its keep: at 3.2 GHz the parts sit further down the voltage /
   frequency curve, and the same work costs less energy.

   The price is throughput: 3079 vs 3788 Mi/s, **-19 %**. So the AC cap is a
   real trade-off — **-19 % speed for ~+24 % efficiency** — not the free
   responsiveness win §3 hoped the cap might be wasting, and not the no-op it
   feared either.

Stated the other way, work per watt:

```
AC      3079.6 / 20.77 = 148.3  Mi/s per W
nocap   3787.5 / 33.45 = 113.2  Mi/s per W
PERF    3739.4 / 34.66 = 107.9  Mi/s per W
```

## Caveats

- **One workload.** A branchy, cache-bound floating loop. Efficiency ordering
  is workload-dependent: a memory-bound load that does not saturate the cores'
  power would flatten these differences, and a load that can use 54 W would
  change outcome (1). The *shape* — capped = most efficient, 54 W = no gain on
  a load that tops out at ~34 W — is what this measures, not a universal law.
- **Thermal soak.** Configs ran in sequence (AC → no-cap → PERF), so the later
  ones started warmer (fan1 1594 → 2277 → 2806). The ±2.5 % soak noise is
  smaller than the 19 % / 24 % effects here, so the ordering holds, but an
  interleaved A/B/A would tighten it.
- The `iGPU`/`dGPU` were not loaded, so whole-system power is not measured —
  this is a CPU-package comparison only.

## Reproducing

```bash
gcc -O2 -pthread -o evidence/load evidence/load.c
./evidence/eff-test.sh            # stops/restores the re-apply units itself
python3 evidence/eff-analyze.py   # the table above
```

Tooling: `evidence/load.c` (the load), `evidence/powsample.py` (the sampler),
`evidence/eff-test.sh` (the three-config harness), `evidence/eff-analyze.py`
(the summary), and the raw per-second samples in
`evidence/autonomous-pass/eff-*.csv`.
