#!/bin/bash
# Is a LOWER POWER cap better than the frequency cap for the same cooling?
#   cfgAC : the current AC profile -- 35 W + 3.2 GHz cap
#   cfg30 : 30 W (lower STAPM/slow), NO frequency cap
# If cfg30 matches cfgAC on all-core power but keeps single-thread boost, the
# power cap is the better instrument.
set -u
OUT=evidence/autonomous-pass
mkdir -p "$OUT"
allcore() {
  python3 evidence/powsample.py "$OUT/eff-$1.csv" 66 1 &
  local s=$!
  ./evidence/load 20 40 16 | tee "$OUT/eff-$1-load.txt" >/dev/null
  wait "$s"
}
single() { ./evidence/load 8 15 1 | grep throughput; }

sudo systemctl stop power-profile-watch.service power-profile.timer

echo "### cfgAC  (35 W + 3.2 GHz cap)"
sudo /usr/local/bin/power-profile ac >/dev/null 2>&1
allcore cfgAC
echo -n "  1-thread: "; single

echo "### cfg30  (30 W, no cap)"
sudo ryzenadj --stapm-limit=30000 --fast-limit=36000 --slow-limit=30000 \
  --apu-slow-limit=22000 --tctl-temp=85 >/dev/null 2>&1
for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do echo 4465000 | sudo tee "$c" >/dev/null 2>&1; done
allcore cfg30
echo -n "  1-thread: "; single

sudo /usr/local/bin/power-profile ac >/dev/null 2>&1
sudo systemctl start power-profile.timer power-profile-watch.service
echo "restored"
