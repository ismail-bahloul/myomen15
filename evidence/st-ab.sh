#!/bin/bash
# Single-thread A/B: does the 3.2 GHz cap cost latency on ONE busy core -- the
# shape of "open an app", where a single thread sits on the critical path?
#
# Throughput (Mi/s) is the ground truth here, not the clock: the SMU PM table's
# per-core effective clock (0x3e0) intermittently reads impossible values above
# the 4.465 GHz part limit, and cpufreq's scaling_cur_freq is a CPPC request, so
# neither is trustworthy as an instantaneous figure. See pm-table.md.
#
# Pinned to cpu0 (core 0) so the load cannot wander. Repeats alternate the two
# configs to average out whatever slow state the SMU carries between runs.
set -u
OUT=evidence/autonomous-pass
mkdir -p "$OUT"
CAP=3200000
NOCAP=4465000
REPS=${REPS:-3}

sudo systemctl stop power-profile-watch.service power-profile.timer

run() {   # $1 label  $2 reps-index
  local lab="$1" r="$2"
  sudo /usr/local/bin/power-profile ac >/dev/null 2>&1
  for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do
    echo "$MAXF" | sudo tee "$c" >/dev/null 2>&1
  done
  python3 evidence/powsample.py "$OUT/st-$lab-$r.csv" 26 1 &
  local samp=$!
  taskset -c 0 ./evidence/load 6 18 1 | tee "$OUT/st-$lab-$r-load.txt"
  wait "$samp"
  echo
}

for r in $(seq 1 "$REPS"); do
  echo "===== rep $r: capped 3.2 GHz (same 28 W) ====="
  MAXF=$CAP run cap "$r"
  echo "===== rep $r: NO cap (same 28 W) ====="
  MAXF=$NOCAP run nocap "$r"
done

sudo /usr/local/bin/power-profile ac >/dev/null 2>&1
sudo systemctl start power-profile.timer power-profile-watch.service
echo "### summary"
python3 - "$REPS" <<'PY'
import csv, glob, re, sys
reps = int(sys.argv[1])
def mean(rows, k):
    v = [float(r[k]) for r in rows if r.get(k) not in ("", None)]
    return sum(v) / len(v) if v else float("nan")
print("%-6s %4s %9s %8s %8s %7s %7s" %
      ("config", "rep", "Mi/s", "PPTslow", "freqGHz", "Tctl", "fan1"))
agg = {}
for lab in ("cap", "nocap"):
    for r in range(1, reps + 1):
        with open("evidence/autonomous-pass/st-%s-%d.csv" % (lab, r)) as fh:
            rows = list(csv.DictReader(fh))[6:24]        # drop ramp samples
        with open("evidence/autonomous-pass/st-%s-%d-load.txt" % (lab, r)) as fh:
            thr = float(re.search(r"throughput_Mi_s=([0-9.]+)", fh.read()).group(1))
        print("%-6s %4d %9.1f %8.2f %8.2f %7.1f %7.0f" %
              (lab, r, thr, mean(rows, "ppt_slow_value"),
               mean(rows, "cur_freq") / 1e6, mean(rows, "tctl") / 1000.0,
               mean(rows, "fan1")))
        agg.setdefault(lab, []).append(thr)
for lab in ("cap", "nocap"):
    print("%-6s mean Mi/s: %.1f" % (lab, sum(agg[lab]) / len(agg[lab])))
print("delta: %+.1f%%" % ((sum(agg["nocap"]) / len(agg["nocap"]))
                          / (sum(agg["cap"]) / len(agg["cap"])) * 100 - 100))
PY
