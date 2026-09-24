#!/bin/bash
# Does removing the frequency cap make short BURSTS (app launch/close) heat more?
# Runs the same burst pattern (15 x ~1 s on 2 threads) with the frequency capped
# vs uncapped, same 28 W power cap, and records the Tctl / power swings.
set -u
bursts() { for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do ./evidence/load 0 1 2 >/dev/null 2>&1; sleep 0.4; done; }

sudo systemctl stop power-profile-watch.service power-profile.timer
sudo /usr/local/bin/power-profile ac >/dev/null 2>&1

for mf in 3200000 4465000; do
  for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do echo "$mf" | sudo tee "$c" >/dev/null 2>&1; done
  label="mf$mf"
  python3 evidence/powsample.py "/tmp/burst-$label.csv" 30 0.5 &
  local_s=$!
  sleep 2
  bursts
  wait "$local_s"
done

sudo /usr/local/bin/power-profile ac >/dev/null 2>&1
sudo systemctl start power-profile.timer power-profile-watch.service

python3 - <<'PYEOF'
import csv
def stat(p):
    rows=list(csv.DictReader(open(p)))
    def col(k):
        xs=[float(r[k]) for r in rows if r[k] not in ('',None)]
        return (max(xs), sum(xs)/len(xs)) if xs else (0,0)
    tmax,_=col('tctl'); pmax,pavg=col('ppt_slow_value'); fmax,_=col('cur_freq')
    print("%-14s Tctl max=%.1f C   power max=%.1f avg=%.1f W   freq max=%.2f GHz"
          % (p.split('/')[-1], tmax/1000, pmax, pavg, fmax/1e6))
for lbl in ('mf3200000','mf4465000'):
    stat('/tmp/burst-%s.csv' % lbl)
PYEOF
echo "(Tctl de départ ~66-68 C ; une variation de quelques degrés = bruit thermique)"
