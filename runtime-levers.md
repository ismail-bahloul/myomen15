# Runtime levers from the audit: THP `madvise`, `scx_lavd`, ASPM

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

Verdict on AC: not worth it, and it makes the metric it is meant for worse.

### On battery (unplugged, deployed battery profile: 15 W, 2.4 GHz cap)

Same test, whole-system draw from the battery (`power_now`, median of 30 samples
after a 25 s settle), 3 interleaved rounds ([`evidence/tuning-ab-bat.sh`](evidence/tuning-ab-bat.sh)):

| | idle draw | wake p50 | wake p99 | wake max | load throughput |
|---|---|---|---|---|---|
| default | 10.76 / 10.75 / 10.74 W | 515 / 514 / 518 us | ~1.6 ms | 4.1 / 7.5 / **30.0** ms | 4548 / 4542 / 4556 Mi/s |
| `scx_lavd` | 10.61 / 10.67 / 10.72 W | 727 / 777 / 758 us | ~3.0 ms | 5.3 / 5.0 / 4.4 ms | 4592 / 4545 / 4544 Mi/s |

- **Power: no gain.** -0.15 / -0.08 / -0.02 W: the difference shrinks each round,
  which is drift, not an effect. ~-0.1 W of 10.7 W is 1 %.
- **Latency: same verdict as on AC**, p50 +45 %, p99 +90 %, every round.
- **The one thing it does buy is the tail**: the default scheduler had a 7.5 ms and
  a 30 ms worst wake-up; lavd never exceeded 5.3 ms. Whether a single 30 ms outlier
  in three 15 s runs matters is a judgement, not a measurement; median and p99
  are what a user feels.
- Throughput is identical. No change made, on AC or battery.

The first battery attempt failed because the harness waited 4 s for lavd to
register and on battery it takes ~6 s; the loop now waits up to 30 s.

## ASPM: not switchable on this machine

The kernel does not own PCIe ASPM here:

```
ACPI FADT declares the system doesn't support PCIe ASPM, so disable it
acpi PNP0A08:00: FADT indicates ASPM is unsupported, using BIOS configuration
r8169 0000:02:00.0: can't disable ASPM; OS doesn't have ASPM control
```

so `/sys/module/pcie_aspm/parameters/policy` refuses writes (`Operation not
permitted`) and links run on whatever the BIOS configured. This closes what
`access-surface.md` calls a cmdline-only lever more precisely: `pcie_aspm.policy=`
alone would not do it either; only `pcie_aspm=force` overrides the FADT, against
the firmware's own declaration, on a platform where the vendor never validated OS
control (NVMe and the Wi-Fi/Ethernet links are the exposed ones). **Not tested**,
and not worth doing blind: the reward is unmeasured and the failure mode is a
link that drops. If ever tried, do it from a Limine snapshot entry so the
rollback is a reboot, and watch `journalctl -k` for AER/`nvme` errors.

## Reproducing

```bash
evidence/tuning-ab.sh thp 3
evidence/tuning-ab.sh scx 3          # AC
evidence/tuning-ab-bat.sh scx 3      # unplugged
```
It restores THP=`always` and unloads scx on exit.
