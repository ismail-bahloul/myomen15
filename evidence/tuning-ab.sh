#!/bin/bash
# A/B/A/B/A/B of the two runtime-switchable levers from the audit, on AC under
# the deployed profile (re-apply units left running, so the config is the real one).
#   thp : transparent_hugepage/enabled  always vs madvise
#   scx : sched_ext scx_lavd loaded vs the default scheduler
# Interleaved, with a cool-down, so thermal drift lands on both arms equally.
# Run as the normal user (sudo for the switches). Restores THP=always, no scx.
#   evidence/tuning-ab.sh thp|scx [rounds]
set -u
cd "$(dirname "$0")/.."
OUT=evidence/tuning-ab; mkdir -p "$OUT"
LEVER=${1:?thp|scx}; ROUNDS=${2:-3}
THP=/sys/kernel/mm/transparent_hugepage/enabled
[ "$(cat /sys/class/power_supply/ACAD/online)" = 1 ] || { echo "run on AC"; exit 1; }
SCXPID=""
cleanup() {
  echo always | sudo tee $THP >/dev/null
  [ -n "$SCXPID" ] && sudo kill "$SCXPID" 2>/dev/null
}
trap cleanup EXIT

arm() {  # arm <A|B>
  case "$LEVER:$1" in
    thp:A) echo always   | sudo tee $THP >/dev/null ;;
    thp:B) echo madvise  | sudo tee $THP >/dev/null ;;
    scx:A) [ -n "$SCXPID" ] && { sudo kill "$SCXPID"; SCXPID=""; sleep 2; } ;;
    scx:B) sudo scx_lavd >"$OUT/scx-lavd.log" 2>&1 & SCXPID=$!; sleep 4
           [ "$(cat /sys/kernel/sched_ext/state)" = enabled ] || { echo "scx not enabled"; exit 1; } ;;
  esac
}

for r in $(seq "$ROUNDS"); do
  for a in A B; do
    arm $a; sleep 25   # cool-down
    tag="$LEVER-$a-r$r"
    if [ "$LEVER" = thp ]; then
      # TLB-heavy: random writes over 6 GiB x 4 workers
      stress-ng --vm 4 --vm-bytes 6G --vm-method rand-set --timeout 20s --metrics-brief 2>&1 \
        | awk '/vm +[0-9]/ {print "'"$tag"' vm_bogo/s(real)=" $(NF-1)}' | tee -a "$OUT/thp.txt"
      stress-ng --stream 4 --stream-l3-size 32M --timeout 15s --metrics-brief 2>&1 \
        | awk '/stream +[0-9]/ {print "'"$tag"' stream_bogo/s(real)=" $(NF-1)}' | tee -a "$OUT/thp.txt"
    else
      ./evidence/load 5 20 16 > "$OUT/$tag-load.txt" &  L=$!
      python3 evidence/powsample.py "$OUT/$tag.csv" 25 1 & P=$!
      sleep 6; echo "$tag $(./evidence/wakelat 15 4)" | tee -a "$OUT/scx.txt"
      wait $L $P
      echo "$tag load: $(grep -h throughput_Mi_s "$OUT/$tag-load.txt" | tail -1)" | tee -a "$OUT/scx.txt"
      stress-ng --switch 8 --timeout 15s --metrics-brief 2>&1 \
        | awk '/switch +[0-9]/ {print "'"$tag"' switch_bogo/s(real)=" $(NF-1)}' | tee -a "$OUT/scx.txt"
    fi
  done
done
echo done
