#!/bin/bash
# How much does the 3.2 GHz cap cost on a LIGHT load (1 thread), where the core
# would otherwise boost to ~4.4 GHz -- versus the all-core case efficiency.md
# already measured? Re-apply units stopped so they cannot revert the test.
set -u
MAXF="4465000"
peakfreq() { cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq | sort -n | tail -1; }

sudo systemctl stop power-profile-watch.service power-profile.timer

sudo /usr/local/bin/power-profile ac
echo "== capped 3.2 GHz =="
./evidence/load 8 15 1 | grep throughput
echo "peak core clock during: $(peakfreq) kHz"

for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do echo "$MAXF" | sudo tee "$c" >/dev/null 2>&1; done
echo "== uncapped (same 35 W) =="
./evidence/load 8 15 1 | grep throughput
echo "peak core clock during: $(peakfreq) kHz"

sudo /usr/local/bin/power-profile ac
sudo systemctl start power-profile.timer power-profile-watch.service
echo "restored"
