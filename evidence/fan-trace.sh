#!/bin/bash
# Trace the fan's response to a sustained load.
#
# Tuning the curve for silence needs two numbers that cannot be guessed: how hot
# the machine actually settles, and what duty cycle (hence rpm) it takes to hold
# that. This runs a fixed load and prints Tctl, both tachos and the nbfc target
# every 5 s, so a curve change can be judged by the *steady state*, not a guess.
#
#   evidence/fan-trace.sh [seconds] [threads]      (default 180 s, 12 threads)
#
# Run it once as-is, then again after a curve change, and compare the last rows.
set -u

SECS="${1:-180}"
THREADS="${2:-12}"
STEP=5

TCTL=""; HP=""
for h in /sys/class/hwmon/hwmon*; do
  case "$(cat "$h/name" 2>/dev/null)" in
    k10temp) TCTL="$h/temp1_input" ;;
    hp)      HP="$h" ;;
  esac
done
[ -n "$TCTL" ] || { echo "no k10temp hwmon"; exit 1; }

rw() { awk -v v="$(cat "$1" 2>/dev/null)" 'BEGIN{printf "%.0f", v/1000}'; }
fan() { cat "$HP/fan$1_input" 2>/dev/null || echo 0; }

echo "load: ${THREADS} threads for ${SECS}s   (Tctl limit $(cat /sys/class/hwmon/*/../hwmon*/temp1_max 2>/dev/null | head -1) not read here)"
echo
printf "%-6s %-8s %-8s %-8s %-8s\n" "t(s)" "Tctl" "fan1" "fan2" "target%"
echo "---------------------------------------------------"

./evidence/load 0 "$SECS" "$THREADS" >/dev/null 2>&1 &
LPID=$!

start=$(date +%s)
while kill -0 "$LPID" 2>/dev/null; do
  now=$(( $(date +%s) - start ))
  tgt=$(nbfc status 2>/dev/null | awk -F': ' '/Target Fan Speed/{printf "%.0f/", $2} END{print ""}')
  printf "%-6s %-8s %-8s %-8s %-8s\n" "$now" "$(rw "$TCTL")" "$(fan 1)" "$(fan 2)" "${tgt%/}"
  sleep "$STEP"
done
wait "$LPID" 2>/dev/null

echo
echo "after load:"
sleep 5
printf "%-6s %-8s %-8s %-8s\n" "t(s)" "Tctl" "fan1" "fan2"
printf "%-6s %-8s %-8s %-8s\n" "+5" "$(rw "$TCTL")" "$(fan 1)" "$(fan 2)"
