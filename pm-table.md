# The PM table, decoded (HP OMEN 15-en1xxx)

`ryzen_smu` exposes the SMU's **PM table** as a raw 2372-byte binary. Nothing had
parsed it. It turns out to be straight `float32` telemetry — limits and live
values, both, in the clear — and it answers a question this repo had left
open for a while.

Everything below was read, not written. The table is read-only.

## Where it is

```bash
/sys/kernel/ryzen_smu_drv/pm_table         2372 bytes, root-readable
/sys/kernel/ryzen_smu_drv/pm_table_version @D  (0x400005)
/sys/kernel/ryzen_smu_drv/pm_table_size
/sys/kernel/ryzen_smu_drv/version          64.74.0
/sys/kernel/ryzen_smu_drv/codename         14 (Cezanne)
```

Two things worth noting about the interface itself: the node is **read-only**
(`-r--r--r--`), and unlike the EFI variables it does *not* refuse access. There
is nothing to unlock — it was simply never read.

## The layout: limits and live values interleave

Every limit is followed immediately by its live reading, in pairs:

| Offset | Field | Live twin |
|---|---|---|
| `0x00` | STAPM LIMIT | `0x04` STAPM VALUE |
| `0x08` | PPT LIMIT FAST | `0x0C` PPT VALUE FAST |
| `0x10` | PPT LIMIT SLOW | `0x14` PPT VALUE SLOW |
| `0x18` | PPT LIMIT APU | `0x1C` PPT VALUE APU |
| `0x20` | TDC LIMIT VDD | `0x24` TDC VALUE VDD |
| `0x28` | TDC LIMIT SOC | `0x2C` TDC VALUE SOC |
| `0x30` | EDC LIMIT VDD | `0x34` EDC VALUE VDD |
| `0x38` | EDC LIMIT SOC | `0x3C` EDC VALUE SOC |
| `0x40` | THM LIMIT CORE | `0x44` THM VALUE CORE |

Decoding is a `struct.unpack('<%df', ...)` over the whole file. Nine limits and
nine live values, matching `ryzenadj --info` field for field:

```
PM table                     ryzenadj --info
[0x00] = 50.000              STAPM LIMIT        50.000
[0x08] = 65.000              PPT LIMIT FAST     65.000
[0x10] = 54.000              PPT LIMIT SLOW     54.000
[0x18] = 22.000              PPT LIMIT APU      22.000
[0x20] = 58.000              TDC LIMIT VDD      58.000
[0x28] = 15.000              TDC LIMIT SOC      15.000
[0x30] = 110.000             EDC LIMIT VDD      110.000
[0x38] = 20.000              EDC LIMIT SOC      20.000
[0x40] = 85.000              THM LIMIT CORE     85.000
```

## What it settles: the "50 vs 54" question

An old note in this repo flagged an unexplained discrepancy — POST seeded
`54 / 65 / 54`, but something later re-asserted `50 / 65 / 54`, and
**why STAPM differed (54 vs 50) was never explained**.

The PM table shows they are two different fields:

- `0x10` = **PPT LIMIT SLOW** = 54
- `0x00` = **STAPM LIMIT** = 50

Reading a three-number profile as "STAPM / fast / slow" and expecting the first
value to be 54 was the error. The `50 / 65 / 54` triple is
`STAPM / PPT-fast / PPT-slow` — consistent all along. There was never a
discrepancy to explain; there was a misread of which field held which value.

## Also readable, not yet interpreted

```
[0x68] 1919.879     (a clock? ~1.92 GHz)
[0x6c] 0.543
[0x70] 1.447
[0x74] 1.079
[0x78] 18.000
[0x7c] 0.016
[0x84] 100.000
```

`0x84` at 100.000 may be a second thermal limit. The four floats at
`0x68`–`0x74` are probably clocks or voltage planes. Not attributed yet.

## The per-core groups, decoded

Five 8-float groups are indexed by **physical core id** (0..7), not by logical
CPU. Confirmed by pinning a busy loop to one thread at a time:

```
taskset -c 0  yes  ->  0x400 index 0 = 100.0000   (cpu0  = core 0)
taskset -c 14 yes  ->  0x400 index 7 = 100.0000   (cpu14 = core 7)
```

`evidence/pmtable-cores.py` dumps them.

| Offset | Index base | Meaning |
|---|---|---|
| `0x3a0` | 232 | scales only slightly with load (~3.7–6.2) — unattributed |
| `0x3c0` | 240 | per-core clock in GHz: the operating point the core is set to |
| `0x3e0` | 248 | per-core **effective** clock in GHz: equals `0x3c0` under load, falls to ~0 when idle |
| `0x400` | 256 | **core busy %** — exactly 100.0000 when saturated |
| `0x5c0` | 368 | scales with load and clock — unattributed |

### How the clocks were confirmed

`cpufreq` could not serve as the reference (see below), so the reference was
`perf`, counting real core cycles while one core ran pinned under a known cap:

| Core 0 capped at | `perf stat -C 0 -e cycles` | `0x3c0[0]` | `0x3e0[0]` |
|---|---|---|---|
| 2.0 GHz | 2.394 GHz | 2.393 | 2.388 |
| 3.2 GHz | 3.169 GHz | 3.175 | 3.175 |

Both fields match the measured frequency to under 0.3 % under sustained load.
They differ only once the core stops working:

```
sustained load :  0x3c0 = 0x3e0 = 3.175
load ends      :  0x3c0 = 2.40   0x3e0 = 0.07
```

So `0x3c0` is the clock the core is *set to* and `0x3e0` the clock it actually
delivers. (Whether `0x3c0` is best named "requested" or "last decided P-state"
is not settled; what is settled is that it is not an average — it held its value
across the whole idle sample instead of decaying.)

### Caveat: `0x3e0` glitches above the part limit

`0x3e0` is fine for a *window mean*, but as an *instantaneous peak* it lies:
on burst exit it was read at **6.35 and 6.50 GHz** — above the 4.465 GHz limit of
this 5800H. The value is real in the table; it is just not a frequency. So a
"peak clock" claim built on `max(0x3e0)` is not trustworthy, and throughput or
PPT is the right instrument for anything about a transient. (Found while
measuring burst heat; see [`efficiency.md`](efficiency.md).)

### Why `cpufreq` could not be the reference

```
scaling_driver = amd-pstate-epp      (status: active)
write min=max=2000000 to core 0
scaling_cur_freq reads 2.535 GHz     (not 2.0)
```

Under `amd-pstate-epp` in `active` mode `scaling_cur_freq` does not track the
delivered clock, so a correlation against it can only ever look "close but never
equal" — which is exactly what the earlier reading found. `perf` (or
`turbostat`) gives the real number; installing `perf` is the step that unlocked
the attribution above.

## Why it matters

This is the **instrument the Windows side lacked**. The Windows investigation
concluded it could not verify power limits, because the PM table there never
populated (the refresh command `0x65` was refused, and the table read back all
zeros). On Linux the table is not only populated, it is directly readable as
floats, with no SMU command required.

Practical consequence: any experiment asking "did this write take effect, and
does it survive?" can now be answered by reading nine limits and nine live
values in one file read — instead of shelling out to `ryzenadj --info` and
parsing a pipe-delimited table.

## Reproducing

```bash
# limits and live values, in one shot
sudo python3 -c "
import struct
v = struct.unpack('<%df' % (2372 // 4), open('/sys/kernel/ryzen_smu_drv/pm_table','rb').read())
names = ['STAPM','PPT_FAST','PPT_SLOW','PPT_APU','TDC_VDD','TDC_SOC','EDC_VDD','EDC_SOC','THM']
for n, i in zip(names, range(0, 18, 2)):
    print(f'{n:9s} limit={v[i]:8.3f}   live={v[i+1]:8.3f}')"
```
