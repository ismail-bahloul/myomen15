#!/bin/bash
# The dGPU clock locks are independent (graphics vs memory), so a profile
# transition can leave one behind. This reads clocks.mem under the CUDA load at
# every relevant lock state, and shows the battery -> AC bug and its fix.
#
#   nvcc -O2 -o /tmp/gpuload evidence/gpuload.cu
#   sudo ./evidence/gpu-lock-e2e.sh
set -u
sample() {
  /tmp/gpuload & local pid=$!
  sleep 4
  local mem=""
  for i in 1 2 3 4 5 6; do
    mem="$mem $(nvidia-smi --query-gpu=clocks.mem --format=csv,noheader,nounits)"
    sleep 1
  done
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  echo "$1: mem under load =$mem"
}
reset_all() { sudo nvidia-smi -rmc >/dev/null 2>&1; sudo nvidia-smi -rgc >/dev/null 2>&1; }

reset_all;                         sample "clean, no lock       "
sudo nvidia-smi -lgc 500,1800;     sample "-lgc alone (ac step)  "
reset_all
sudo nvidia-smi -lmc 405;          sample "-lmc 405 alone        "
sudo nvidia-smi -lgc 500,1800;     sample "-lmc 405 then -lgc    "
reset_all

# The profile part needs the re-apply units stopped: power-profile-watch reverts
# any SMU-limit drift within ~1 s, which silently undoes a `battery` apply.
sudo systemctl stop power-profile-watch.service power-profile.timer
sudo /usr/local/bin/power-profile battery >/dev/null 2>&1; sleep 2
sample "power-profile battery "
sudo /usr/local/bin/power-profile ac >/dev/null 2>&1; sleep 2
sample "  ... then -> AC      "
sudo systemctl start power-profile.timer power-profile-watch.service

sudo /usr/local/bin/power-profile ac >/dev/null 2>&1
sudo nvidia-smi -rmc >/dev/null 2>&1
sample "restored to AC (fixed)"
echo "done"
