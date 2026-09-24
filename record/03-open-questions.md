# Linux-side next steps — what to do, what NOT to do

> **Status: mostly closed — read §6 first.** §1 (the Curve Optimizer question) is
> settled, and §2 ("the EC re-asserts OS-written power limits") turned out to be
> **wrong**: the premise was false and the real trigger is a write to
> `platform_profile`. §§1–§5 are kept as the record of how that was established.

Companion to `01-linux-power-report.md` and
`02-curve-optimizer-verdict-windows.md`.

Read §1 first: **the Curve Optimizer question is closed. Do not spend more time
on it.** The remaining value is in §2 (your open §5) and §3 (efficiency).

---

## 1. Closed: Curve Optimizer. Do not chase it.

The Windows side answered the priority questions and then falsified the premise
of your §2. Summary of what is now established:

| Claim | Status |
|---|---|
| "On Windows: CO works" | ❌ **false.** UXTU fails silently; see the log below |
| "Linux refusal is a property of the interface/command path" | ❌ **false.** Both OSes send the same command and both get refused |
| "Silicon and firmware accept a CO offset" | ❌ **false.** The SMU refuses it |
| "The SMU refuses CO on this machine" | ✅ **true — you were right** |

Evidence: UXTU's own diagnostic log,
`C:\Program Files\JamesCJ60\Universal x86 Tuning Utility\logs\uxtu_log*.txt`,
contains **20 failure entries out of 20 attempts**, from the first apply onwards:

```
18:17:43 [WRN] Failed to process command: --set-coall=1048566
System.InvalidOperationException: SMU command 'set-coall' failed with status FAILED.
```

`1048566` = `0x100000 - 10`. Offset `0` is refused too. And UXTU surfaces nothing:
it catches the exception, logs a warning, and still updates the UI.

Direct SMU probing (independent of UXTU, via the PawnIO module) confirms the same
picture — the mailbox works, the OC/CO surface is gated:

| MP1 msg | Meaning | Result |
|---|---|---|
| `0x0D` | get PM table version | ✅ |
| `0x14` | `stapm-limit` | ✅ accepted (but echoes a constant, see §2.0) |
| `0x55` | `set-coall` | ❌ FAILED |
| `0x64` | `set-cogfx` | ❌ FAILED |
| `0x2F` | `enable-oc` | ❌ FAILED |
| `0x30` | `disable-oc` | ❌ FAILED |
| `0x49` | `pbo-scalar` | ❌ FAILED |
| `0x19` | `tctl-temp` | ❌ FAILED |
| `0x5B` | `get-sustained-power-and-thm-limit` | ❌ FAILED |
| `0x65` | transfer PM table to DRAM | ❌ FAILED |

Consequences for Linux:

- **Do not patch `ryzenadj` for CO.** `ryzenadj` already sends the correct command
  for Cezanne: `set_coall → _do_adjust(0x55)`, `set_coper → 0x54`,
  `set_enable_oc → 0x2F` — identical to UXTU's table, with identical argument
  encoding (`offset >= 0 ? offset : 0x100000 - |offset|`). There is nothing to fix.
- **Do not install ZenTune (ex-UXTU4Linux) expecting CO.** Its README advertises
  Curve Optimizer, but it drives the same SMU messages and will hit the same wall.
  (It is still worth a look for power limits, automations and AC/battery
  switching — just not for CO.)
- HP's firmware gates this, consistent with the rest of your §4: Sure Start
  active, no Curve Optimize menu, `Custom Core Pstates` empty.

---

## 2. Open: your §5 — the EC re-asserting OS-written limits

This is the real remaining question, and **it can only be answered on Linux**:
Windows has no usable read-back (PM table refresh refused, dediated getter
refused, UXTU display is its own defaults, `stapm-limit` echoes a constant).

You already have the instrument: `ryzenadj --info` prints both the **limits** and
the **live values**, e.g. `STAPM LIMIT` / `STAPM VALUE` / `PPT LIMIT FAST` /
`PPT VALUE FAST` / `THM LIMIT CORE`. The `VALUE` fields are measured power — that
is the same number Windows could not give us.

### 2.0 Do this first (5 seconds, and it may invalidate the rest)

The Windows side found that `0x14` (`stapm-limit`) **succeeds** and echoes a
constant `15000` regardless of the value written (tested 15000/20000/35000/
45000/54000). So this firmware may **accept a limit write without acting on it**.

Before measuring survival times, check that a write actually takes:

```bash
sudo ryzenadj --stapm-limit=35000 --fast-limit=42000 --slow-limit=35000
# immediately, twice:
sudo ryzenadj --info | grep -E 'STAPM LIMIT|PPT LIMIT FAST|PPT LIMIT SLOW'
sleep 2
sudo ryzenadj --info | grep -E 'STAPM LIMIT|PPT LIMIT FAST|PPT LIMIT SLOW'
```

Interpretation:

- If the LIMIT fields read back **35 / 42 / 35** → writes take. Continue to §2.1.
- If they read **50 / 65 / 54** (the EC values) or the POST values → the write is
  **ignored**, and your whole §5 observation may actually be "writes never took",
  not "the EC reverts them". That distinction changes the fix entirely.

### 2.1 The revert measurement

Ah, and a protocol detail that matters: **stop your 5-minute timer during the
test**, otherwise it will mask the revert and you will measure your own script.

```bash
sudo systemctl stop power-profile.timer
sudo systemctl stop power-profile.service   # judge whether to re-enable after
```

Poller (adapt the labels if your `ryzenadj --info` differs):

```bash
#!/usr/bin/env bash
# poll-limits.sh <out.csv> <seconds> [interval]
# NB: ryzenadj --info is a pipe-delimited table (| Name | Value | Parameter |)
#     so the value is field 3, not the last field.
out="${1:-limits.csv}"; dur="${2:-600}"; iv="${3:-2}"
echo "ts,epoch,stapm_limit,stapm_value,ppt_fast_limit,ppt_fast_value,tctl_limit,ac,fan1,fan2" > "$out"
end=$(( $(date +%s) + dur ))
while [ "$(date +%s)" -lt "$end" ]; do
  info=$(ryzenadj --info 2>/dev/null)
  get() { printf '%s\n' "$info" | awk -F'|' -v p="$1" 'index($2,p){gsub(/[ \t\r]/,"",$3); print $3; exit}'; }
  ac=$(cat /sys/class/power_supply/ACAD/online 2>/dev/null || echo '?')
  f1=$(cat /sys/class/hwmon/hwmon*/fan1_input 2>/dev/null | head -1)
  f2=$(cat /sys/class/hwmon/hwmon*/fan2_input 2>/dev/null | head -1)
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "$(date -Is)" "$(date +%s)" \
    "$(get 'STAPM LIMIT')" "$(get 'STAPM VALUE')" \
    "$(get 'PPT LIMIT FAST')" "$(get 'PPT VALUE FAST')" \
    "$(get 'THM LIMIT CORE')" "$ac" "$f1" "$f2" >> "$out"
  sleep "$iv"
done
```

Run it in one terminal, write the limits in another, and let it run 10 minutes:

```bash
./poll-limits.sh nbfc_on.csv 600 &
sudo ryzenadj --stapm-limit=35000 --fast-limit=42000 --slow-limit=35000
```

Then the A/B that actually answers the question — the report already suspected
`nbfc` as the trigger, and the suspicion is testable:

```bash
# condition B: fans controlled by the EC only
sudo systemctl stop nbfc          # (or whatever unit your nbfc-linux uses)
sleep 30
./poll-limits.sh nbfc_off.csv 600 &
sudo ryzenadj --stapm-limit=35000 --fast-limit=42000 --slow-limit=35000
```

Deliverable: for each condition, the **time-to-revert** for every event, from the
`LIMIT` columns. Your existing observations as the starting point:

| When | Written | Survived | Then |
|---|---|---|---|
| 16:50 | 50/60/50 | < 55 s | 50/65/54 |
| 19:06 | 35/42/35 | ~60–90 s | 50/65/54 |
| 19:12 | 35/42/35 | ≥ 150 s | — |
| 19:15 | 35/42/35 (nbfc stopped) | ≥ 171 s | — |

If `nbfc_off.csv` shows zero reverts over 10 minutes and `nbfc_on.csv` shows
them, the trigger is nbfc, and the fix is to stop nbfc from writing to the EC
(or to move fan control to `hp-wmi`'s `pwm1_enable` path, which the report
already identified) — **not** to shorten the re-apply interval.

Do **not** shorten the re-apply interval first. It treats the symptom and hides
the trigger.

---

## 3. Efficiency: the measurement you actually want

Windows could not do this. Linux can, with what you already have, and it needs no
new tooling.

Metric: **joules per unit of work** (or work per watt). On a laptop this is the
only number that answers "is this profile worth it".

### 3.1 Workload (fixed work, identical loop to the Windows side)

```c
/* load.c — fixed-duration all-core load; usage: ./load <warmup_s> <measure_s> <threads> */
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>
#include <time.h>

static volatile int stop = 0;
static unsigned long long total = 0;
static pthread_mutex_t lk = PTHREAD_MUTEX_INITIALIZER;

static void *worker(void *arg) {
    double x = 1.0001; long acc = 0;
    while (!stop) {
        for (long i = 0; i < 2000000; i++) {
            x = x * 1.0000001 + 0.9999999;
            if (x > 3.0) x *= 0.5;
            acc += i ^ (long)x;
        }
        pthread_mutex_lock(&lk); total += 2000000ULL; pthread_mutex_unlock(&lk);
    }
    __asm__ volatile("" :: "r"(acc) : "memory");
    return NULL;
}

int main(int argc, char **argv) {
    int warmup = argc > 1 ? atoi(argv[1]) : 20;
    int measure = argc > 2 ? atoi(argv[2]) : 40;
    int threads = argc > 3 ? atoi(argv[3]) : (int)sysconf(_SC_NPROCESSORS_ONLN);
    pthread_t th[512];
    for (int i = 0; i < threads && i < 512; i++) pthread_create(&th[i], NULL, worker, NULL);
    sleep(warmup);
    unsigned long long before = total;
    struct timespec t0, t1; clock_gettime(CLOCK_MONOTONIC, &t0);
    sleep(measure);
    clock_gettime(CLOCK_MONOTONIC, &t1);
    unsigned long long done = total - before;
    double secs = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;
    stop = 1;
    for (int i = 0; i < threads && i < 512; i++) pthread_join(th[i], NULL);
    printf("threads=%d\niterations=%llu\nmeasure_s=%.2f\nthroughput_Mi_s=%.1f\n",
           threads, done, secs, done / 1e6 / secs);
    return 0;
}
```

```bash
gcc -O2 -pthread -o load load.c
```

Same loop as the Windows harness, so `throughput_Mi_s` is roughly comparable
across the two (compiler differences aside).

### 3.2 Energy per iteration

```bash
# pendant le run: puissance CPU (STAPM VALUE / PPT VALUE) toutes les secondes
./poll-limits.sh eff.csv 90 1 &
nice -n -5 ./load 20 60 16
```

Then, over the 60-second measurement window:

```
avg_watts = mean(STAPM VALUE over the window)
J_per_Miter = avg_watts * 60 / (iterations / 1e6)
```

And for autonomy — the number that actually matters — repeat **on battery** and
read whole-system power in parallel:

```bash
# puissance systeme entiere, en microwatts
watch -n1 'cat /sys/class/power_supply/BAT*/power_now'
```

Caveats that matter here:

- **Park the dGPU** (your VFIO setup already does this) — otherwise you are
  measuring the 3070, not the CPU.
- Whole-system power includes the panel, NVMe and the VRM losses; that is a
  feature for autonomy questions, a nuisance for CPU-only comparisons. Report both.
- Fix the ambient/fan conditions between runs, and interleave configurations
  (A/B/A/B) — the Windows session showed a ~2.5 % drift from heat soak alone,
  which is larger than the effects you are chasing.

### 3.3 What to compare

| Config | Expected purpose |
|---|---|
| AC profile (3.2 GHz cap, 35 W) | your daily quiet AC setting |
| Battery profile (2.4 GHz, 15 W) | autonomy |
| `perf` (4.4 GHz, 54 W) | ceiling / thermal headroom |
| AC without the frequency cap, 35 W | is the `scaling_max_freq` cap winning anything over the power cap? |

That last row is the interesting one: you cap both frequency **and** power on AC.
If the power cap alone gives the same work per joule, the frequency cap is doing
nothing but hurting peak responsiveness.

---

## 4. Reference: the Cezanne SMU map (from UXTU's decompiled tables)

Useful if you ever get an unlocked machine, or want to sanity-check `ryzenadj`.

```
socket FP6_AM4 (Renoir / Lucienne / Cezanne), MP1 unless noted:
  stapm-limit       20      fast-limit        21      slow-limit     22
  slow-time         23      stapm-time        24      tctl-temp      25
  apu-slow-limit    33      skin-temp-limit   83      enable-oc      47
  disable-oc        48      pbo-scalar        73      gfx-clk       137 (RSMU)
  set-coper         84      set-coall         85      set-cogfx     100
  get-coper-options 195 (RSMU)                get-cogfx-options 198 (RSMU)
  get-sustained-power-and-thm-limit 91
  enable-feature     5      disable-feature    7

Command encoding, if ever needed:
  offset >= 0  ->  (uint)offset
  offset <  0  ->  (uint)(0x100000 - |offset|)

Access path (same on both OSes):
  PCI config 0xB8 = SMN address, 0xBC = SMN data
  Cezanne mailbox: cmd 0x3B10A20, rsp 0x3B10A80, args 0x3B10A88
  SMU 64.74.0, PM table version 0x400005
```

---

## 5. Where the Windows-side evidence lives

In this repo: `02-curve-optimizer-verdict-windows.md` (verdict, evidence,
tooling, and the UXTU bug write-up).

Preserved in `evidence/`: `results.jsonl` (all
26 benchmark runs), `smu.cs` and `load.cs` (the raw SMU prober and the load
generator), `ryzensmu_src.p` and `ryzenadj_api.c` (vendored sources), and
`uxtu_src/` (a full ILSpy decompilation of UXTU 26.3.1 — contains
`RyzenSmu.Addresses`, `SMUCommands` and `EncodeCurveOptimiserOffset`, all cited
above).

The Windows install has been cleaned up: the PawnIO driver (service, DriverStore
package and folder), UXTU and its runtime leftovers, the .NET 10 SDK and Desktop
Runtime, and `C:\Users\<user>\Desktop\perf-test\` are all removed. The compiled
helpers (`smu.exe`, `load.exe`) are gone with them — rebuild from `smu.cs` /
`load.cs` if a machine ever needs them, which requires PawnIO plus UXTU's
`Assets/AMD/PawnIO/RyzenSMU.bin` module.

Nothing else is pending on the Windows side.

---

## 6. Both open items are now closed (added later)

This document was written before the §2 work was carried out. It has been done,
and it changed the answer — read this before acting on §2.

### §2.0 (do writes actually take?)

Yes. Writing `37/44/37` read back `37/44/37` immediately, and still 27 s later.
The Linux instrument is sound, and the caveat imported from the Windows side
(the `0x14` echoing a constant) does not apply here: that was an artifact of the
Windows probe path, where the PM table is not populated at all.

### §2 — the EC-revert question

**The premise was wrong: the EC does not revert the limits.** A controlled A/B
with the guard disabled for the whole run:

| Phase | Condition | Duration | Result |
|---|---|---|---|
| A | `nbfc` running | 10 min (287 samples) | `35/42/35` — no reversion |
| B | `nbfc` stopped | 10 min (287 samples) | `35/42/35` — no reversion |

So the recommendation in this document — *"if `nbfc_off.csv` shows zero reverts
and `nbfc_on.csv` shows them, the trigger is nbfc"* — resolved the other way:
**neither** condition shows reverts, so `nbfc` is not the trigger.

The actual trigger is a **write to the EC-facing platform profile**, which makes
the EC re-apply its own limits, even when the value written is the one already
set:

```
write 35/42/35                  -> 35.000 42.000 35.000
write platform_profile=cool     -> 54.000 65.000 54.000    # clobbered
write platform_profile=balanced -> 54.000 65.000 54.000
```

Every "reversion" in the §2 table coincides with such a write performed by hand
during the investigation.

### Consequences

- **Nothing to fix.** The 35 W / 85 °C profile persists in normal use; there is
  no EC fight to win. `power-profile.timer` is a safety net against
  `platform_profile` writes, not a workaround for a periodic revert.
- **Do not** shorten the re-apply interval — there is no revert to outrun.
- If this is ever revisited, watch
  `/sys/class/platform-profile/platform-profile-0/profile` for writers rather
  than polling the limits.
- §3 (efficiency: joules per iteration, and whether the `scaling_max_freq` cap
  earns anything over the power cap alone) is still open and still worth doing.

---

## 7. §3 is done too (added later)

The joules-per-iteration measurement, and the "does the frequency cap earn
anything" question, have been carried out. Short version: the 3.2 GHz cap is a
real efficiency win (~24 % better work-per-joule), **not** the no-op §3.3
suspected, at a cost of ~19 % peak throughput; and raising the power limit to
54 W earns nothing on a load that tops out at ~34 W. Full method, table and
caveats: [`../efficiency.md`](../efficiency.md).
