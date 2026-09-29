#!/usr/bin/env bash
# Read-only capture for the AMD PBS "power limit adjustment percent" A/B.
# Prints the context and the SMU limits ryzenadj reports. Changes nothing.
#
# Usage: ./probe.sh > before.txt      (run before and after the change)
set -euo pipefail

PP=/sys/class/platform-profile/platform-profile-0/profile
AC=$(cat /sys/class/power_supply/AC*/online 2>/dev/null | head -1 || echo '?')

echo "# $(date -Is)"
echo "platform_profile: $(cat "$PP" 2>/dev/null || echo '?')"
echo "ac_online: ${AC}  (1=AC, 0=battery)"
echo "# ryzenadj --info (limits only)"
sudo -n ryzenadj --info 2>/dev/null \
  | grep -iE "STAPM LIMIT|PPT LIMIT|TDC LIMIT|EDC LIMIT|THM LIMIT"
