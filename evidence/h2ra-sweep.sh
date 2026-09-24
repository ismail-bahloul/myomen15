#!/bin/bash
# Sweep the nbfc fan setpoint and read H2RA's curve-table window at each step.
# That separates the bytes that are a *static declared curve* (unchanged by fan
# speed) from the ones that track the fans (the tachometers).
#
#   sudo ./evidence/h2ra-sweep.sh
#
# memdump.py needs root; nbfc's CLI does not. Restores nbfc to auto on exit.
set -u
for sp in 0 20 40 60 80 100; do
  if [ "$sp" = 0 ]; then nbfc set -a >/dev/null 2>&1; else nbfc set -s "$sp" >/dev/null 2>&1; fi
  sleep 7
  printf '### setpoint %s%%  ' "$sp"
  sudo python3 evidence/memdump.py 0xfe700520 0x20 | tr '\n' '|'
  echo
  printf '###             0x8E0  '
  sudo python3 evidence/memdump.py 0xfe7008e0 0x10 | tr '\n' '|'
  echo
done
nbfc set -a >/dev/null 2>&1
echo "nbfc restored to auto"
