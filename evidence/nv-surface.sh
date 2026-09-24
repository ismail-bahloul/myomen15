#!/bin/bash
# Capture the Linux-exposed NVIDIA surface, read-only, for diffing against a
# Windows / MSI Afterburner session.
#
#   ./evidence/nv-surface.sh /tmp/nv-surface.txt
#
# Run it inside an X11 session that has Coolbits set (see dgpu-windows-undervolt.md)
# to also capture the clock-offset attributes; without X the nvidia-settings
# section just fails into the file, which is itself informative. Reads only.
set -u
out="${1:-/tmp/nv-surface.txt}"
{
  echo "### date";            date -Is
  echo "### gpu";             nvidia-smi --query-gpu=name,driver_version,vbios_version,power.limit,power.default_limit,power.min_limit,power.max_limit --format=csv
  echo "### clocks";          nvidia-smi -q -d CLOCK
  echo "### power";           nvidia-smi -q -d POWER
  echo "### supported clocks";nvidia-smi -q -d SUPPORTED_CLOCKS
  echo "### voltage";         nvidia-smi -q -d VOLTAGE
  echo "### temperature";     nvidia-smi -q -d TEMPERATURE
  echo "### nvidia-settings clock/voltage/power attributes"
  nvidia-settings -q all 2>&1 | grep -iE 'clock|voltage|power|offset|perfmode|perflevel' | head -120
} > "$out" 2>&1
echo "wrote $out"
