#!/usr/bin/env bash
# Read-only capture for the AMD CBS memory (UMC) A/B.
# Ground truth is the OS-visible "Configured Memory Speed" (SMBIOS) plus the
# SPD-rated speed, so a change shows even without a benchmark.
#
# Usage: ./probe.sh > before.txt      (run before and after the change)
set -euo pipefail

echo "# $(date -Is)"
echo "# dmidecode type 17: rated Speed vs Configured Memory Speed"
sudo -n dmidecode -t 17 2>/dev/null \
  | grep -iE "^\s*(Size|Speed|Configured Memory Speed):" | sed 's/^[[:space:]]*/  /'
echo "# lscpu (cpu-side only, for context)"
lscpu | grep -iE "Model name|MHz" | sed 's/^/  /'
