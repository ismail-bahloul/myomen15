# Two runtime levers from the audit: THP `madvise` and `scx_lavd`

Both can be flipped live, so both were A/B-tested rather than argued. Method:
[`evidence/tuning-ab.sh`](evidence/tuning-ab.sh), on AC under the deployed profile
(28 W, re-apply units running), arms interleaved A/B/A/B/A/B with a 25 s cool-down
so thermal drift lands on both. Raw output in `evidence/tuning-ab/`. Kernel
`7.2.6-1-cachyos`, 16 threads, 30 GiB RAM.

## THP: `always` stays

| arm | random writes, 6 GiB x 4 (`stress-ng --vm rand-set`) | stream |
|---|---|---|
| `always` (current) | 108.6k / 100.2k / 87.5k bogo/s | 478 / 477 / 472 |
| `madvise` | 72.4k / 78.8k / 79.1k | 481 / 485 / 482 |

`madvise` costs **~25-30 %** on a TLB-heavy random-access workload and gains
nothing on streaming (+1 %, inside the noise). The `always` arm falls from round
to round (108 -> 87k) while `madvise` is flat, so the gap narrows; the sign is the
same in all three rounds. **Not measured**: the usual argument against `always`
(latency spikes from compaction, memory bloat) needs a long-running mixed
workload, not a 20 s benchmark. No change made.

## `scx_lavd`: worse for wake-up latency here, no gain in power

Wake-up lateness of 1 ms sleepers (`evidence/wakelat.c`) beside an all-core load:

| arm | p50 | p99 | p99.9 | max |
|---|---|---|---|---|
| default scheduler | 538 / 535 / 551 us | 1618 / 1624 / 1649 | 2584 / 2635 / 2938 | 4.9-5.9 ms |
| `scx_lavd` | 718 / 707 / 694 us | 2986 / 2985 / 2992 | 3614 / 3716 / 3352 | 4.0-4.4 ms |

p50 is ~30 % worse and p99 ~85 % worse, in every round. Only the worst case (max)
improved. Everything else is a tie: load throughput 6442-6490 vs 6448-6467 Mi/s,
package power under load 17.8-19.2 W vs 18.3-19.3 W (+0.3 W, inside the round to
round drift), Tctl the same. `stress-ng --switch` is 55 % higher under `lavd`, but
that measures context-switch throughput, not how late a task wakes.

Verdict on AC: not worth it, and it makes the metric it is meant for worse. It was
**not** tested on battery, where lavd's power-oriented claims would apply: that
needs the machine unplugged.

## What could not be tested from here

- **`pcie_aspm.policy=powersupersave`**: ASPM saves power on the NVMe and Wi-Fi
  links, which the package power (STAPM) does not see, and on AC the battery
  discharge rate that would show it does not exist. It needs a battery run with
  the battery's own discharge reading, unplugged.

## Reproducing

```bash
evidence/tuning-ab.sh thp 3
evidence/tuning-ab.sh scx 3
```
It restores THP=`always` and unloads scx on exit.
