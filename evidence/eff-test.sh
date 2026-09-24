#!/bin/bash
# Joules-per-iteration across three configs. Run as the normal user; it calls
# sudo internally for the privileged bits, so the output files stay yours.
# Restores the normal AC profile and the re-apply units on exit.
set -u
OUT=evidence/autonomous-pass
mkdir -p "$OUT"
MAXFREQ=4465000

run() {
  local label="$1"
  sleep 4
  python3 evidence/powsample.py "$OUT/eff-$label.csv" 66 1 &
  local samp=$!
  ./evidence/load 20 40 16 | tee "$OUT/eff-$label-load.txt"
  wait "$samp"
  echo
}

echo "### stop the re-apply units so nothing clobbers a test config"
sudo systemctl stop power-profile-watch.service power-profile.timer

echo "### CONFIG 1: 35 W + 3.2 GHz cap (the published 'ac' row)"
# Explicit, not via power-profile: the deployed AC profile is now 28 W with no
# frequency cap, so `power-profile ac` no longer reproduces this row.
sudo ryzenadj --stapm-limit=35000 --fast-limit=42000 --slow-limit=35000 \
  --apu-slow-limit=22000 --tctl-temp=85 >/dev/null 2>&1
for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do
  echo "3200000" | sudo tee "$c" >/dev/null 2>&1
done
echo "max_freq=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq) gov=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor)"
run ac

echo "### CONFIG 2: 35 W, NO frequency cap"
sudo ryzenadj --stapm-limit=35000 --fast-limit=42000 --slow-limit=35000 \
  --apu-slow-limit=22000 --tctl-temp=85 >/dev/null 2>&1
for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do
  echo "$MAXFREQ" | sudo tee "$c" >/dev/null 2>&1
done
echo "max_freq=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq) gov=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor)"
run nocap

echo "### CONFIG 3: PERF (54 W + 4.465 GHz)"
sudo /usr/local/bin/power-profile perf
echo "max_freq=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq) gov=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor)"
run perf

echo "### restore AC profile + re-apply units"
sudo /usr/local/bin/power-profile ac >/dev/null 2>&1
sudo systemctl start power-profile.timer power-profile-watch.service
echo "done"
