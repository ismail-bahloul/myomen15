#!/bin/bash
# Thermal A/B: the OLD AC config (35 W + 3.2 GHz cap) vs the NEW one (28 W, no
# cap). The question: does dropping the frequency cap make the machine hotter
# and/or louder in practice?
#
# Three phases per config, sampled at 1 Hz (temperature, both fan rpm, package
# power, frequency):
#   idle 25 s  |  1-thread 60 s  |  cooldown 25 s  |  14-thread 50 s
# The 1-thread phase is where the two configs differ most: capped, a single core
# cannot pass 3.2 GHz; uncapped it boosts to ~4 GHz (see efficiency.md).
set -u
OUT=evidence/autonomous-pass
mkdir -p "$OUT"

sudo systemctl stop power-profile-watch.service power-profile.timer

apply_old() {
  sudo ryzenadj --stapm-limit=35000 --fast-limit=42000 --slow-limit=35000 \
    --apu-slow-limit=22000 --tctl-temp=85 >/dev/null 2>&1
  for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do
    echo 3200000 | sudo tee "$c" >/dev/null 2>&1
  done
}
apply_new() {
  sudo /usr/local/bin/power-profile ac >/dev/null 2>&1
}

run() {  # $1 label
  local lab="$1"
  python3 evidence/powsample.py "$OUT/thermal-$lab.csv" 175 1 &
  local s=$!
  sleep 2
  echo "  [$lab] idle 25 s..."
  sleep 25
  echo "  [$lab] 1 thread 60 s..."
  taskset -c 0 ./evidence/load 0 60 1 >/dev/null 2>&1
  echo "  [$lab] cooldown 25 s..."
  sleep 25
  echo "  [$lab] 14 threads 50 s..."
  ./evidence/load 0 50 14 >/dev/null 2>&1
  wait "$s"
}

# SUF names this pass; ORDER=rev runs new-then-old, to cancel the "warmer
# second" bias of a fixed order.
SUF="${SUF:-}"
if [ "${ORDER:-oldnew}" = "rev" ]; then SEQ="new old"; else SEQ="old new"; fi

for cfg in $SEQ; do
  case "$cfg" in
    old) echo "=== OLD: 35 W + 3.2 GHz cap ==="; apply_old ;;
    new) echo "=== NEW: 28 W, no cap ===";         apply_new ;;
  esac
  run "$cfg$SUF"
done

sudo /usr/local/bin/power-profile ac >/dev/null 2>&1
sudo systemctl start power-profile.timer power-profile-watch.service
echo "### done -- analyse with thermal-analyze.py"
