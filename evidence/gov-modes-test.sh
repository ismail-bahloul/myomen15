#!/bin/bash
# Measure each omen-governor mode under a fixed load, so the modes stop being
# design choices and become measured points. Uses the same load and sampler as
# the efficiency work (evidence/load, evidence/powsample.py).
#
#   ./evidence/gov-modes-test.sh          # ~5 min of load
#
# Stops the power-profile units so nothing clobbers a mode, restores them and
# the normal AC state on exit.
set -u
OUT=evidence/autonomous-pass
mkdir -p "$OUT"

run() {
  local mode="$1"
  sudo python3 evidence/omen-governor apply "$mode" --commit >/dev/null
  sleep 4
  python3 evidence/powsample.py "$OUT/eff-gov-$mode.csv" 66 1 &
  local samp=$!
  ./evidence/load 20 40 16 | tee "$OUT/eff-gov-$mode-load.txt"
  wait "$samp"
  echo
}

sudo systemctl stop power-profile-watch.service power-profile.timer

for mode in quiet balanced performance battery; do
  echo "### governor mode: $mode"
  run "$mode"
done

echo "### restore the normal AC state"
sudo /usr/local/bin/power-profile ac >/dev/null 2>&1
echo balanced | sudo tee /sys/class/platform-profile/platform-profile-0/profile >/dev/null
sudo systemctl start power-profile.timer power-profile-watch.service
echo "done"
