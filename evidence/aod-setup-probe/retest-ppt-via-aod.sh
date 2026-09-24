#!/usr/bin/env bash
# Rerun the PPT-limit test through \AOD, automatically, after AOD_SETUP has
# been created via the real UEFI Shell (create-aod-setup-test.nsh).
#
# This is the *retest* half of evidence/aod-setup-probe/README.md: the exact
# same commands evidence/aod-power-limit-probe.txt already used, run
# end-to-end with the service stop/restore and the before/after comparison
# done for you, so the only manual step left is the reboot into the UEFI
# Shell to create AOD_SETUP itself (that part cannot be scripted from Linux --
# it has to happen pre-boot).
#
# Usage: sudo ./retest-ppt-via-aod.sh
set -uo pipefail

LOG="ppt-retest-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG") 2>&1

fail() { echo "FAIL: $*"; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "run as root (sudo $0)"
command -v ryzenadj >/dev/null || fail "ryzenadj not found"
[ -e /proc/acpi/call ] || fail "/proc/acpi/call missing -- is acpi_call loaded? (sudo modprobe acpi_call)"

WATCH_WAS_ACTIVE=0
systemctl is-active --quiet power-profile-watch && WATCH_WAS_ACTIVE=1

cleanup() {
  echo
  echo "--- restoring state ---"
  systemctl start power-profile.service 2>/dev/null
  if [ "$WATCH_WAS_ACTIVE" -eq 1 ]; then
    systemctl start power-profile-watch 2>/dev/null
    echo "power-profile-watch restarted"
  fi
  systemctl is-active power-profile-watch power-profile.service 2>&1 | sed 's/^/  /'
}
trap cleanup EXIT

echo "=== AOD_SETUP existence check (informational only) ==="
EFIVAR="/sys/firmware/efi/efivars/AOD_SETUP-5ed15dc0-edef-4161-9151-6014c4cc630c"
if [ -e "$EFIVAR" ]; then
  echo "found: $EFIVAR ($(stat -c%s "$EFIVAR") bytes incl. 4-byte attr header)"
else
  echo "not visible in efivarfs at $EFIVAR"
  echo "(not necessarily fatal -- AodSmmSsp reads it via SMM runtime services,"
  echo " not through efivarfs; but if you haven't run create-aod-setup-test.nsh"
  echo " yet, stop here and do that first from the real UEFI Shell.)"
  read -rp "Continue anyway? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || exit 1
fi

ppt_fast() { ryzenadj --info 2>/dev/null | awk -F'|' '/PPT LIMIT FAST/{gsub(/ /,"",$3); print $3}'; }
ppt_slow() { ryzenadj --info 2>/dev/null | awk -F'|' '/PPT LIMIT SLOW/{gsub(/ /,"",$3); print $3}'; }

echo
echo "=== stopping power-profile-watch (it reapplies the profile every 1s and"
echo "    would mask both the AOD write and the ryzenadj control) ==="
systemctl stop power-profile-watch

echo
echo "=== baseline ==="
BASE_FAST=$(ppt_fast); BASE_SLOW=$(ppt_slow)
echo "PPT LIMIT FAST = $BASE_FAST   PPT LIMIT SLOW = $BASE_SLOW"

echo
echo "=== \\AOD.AM05 { Set PPT Limit, 25000 mW } ==="
printf '%s' '\AOD.AM05 {0x01,0x00,0x05,0x00,0xA8,0x61,0x00,0x00}' > /proc/acpi/call
cat /proc/acpi/call
sleep 1.5
AOD_FAST=$(ppt_fast); AOD_SLOW=$(ppt_slow)
echo "after AOD write: PPT LIMIT FAST = $AOD_FAST   PPT LIMIT SLOW = $AOD_SLOW"

echo
echo "=== control: ryzenadj --fast-limit=22000 (proves the instrument is live) ==="
ryzenadj --fast-limit=22000 >/dev/null
sleep 1
CTRL_FAST=$(ppt_fast)
echo "after ryzenadj control: PPT LIMIT FAST = $CTRL_FAST"

echo
echo "=== verdict ==="
if [ -n "$AOD_FAST" ] && [ "$AOD_FAST" != "$BASE_FAST" ]; then
  echo "PPT MOVED via \\AOD (from $BASE_FAST to $AOD_FAST) -- the AOD_SETUP gate"
  echo "was the real blocker. The road can drive the SMU after all."
else
  echo "PPT UNCHANGED via \\AOD ($BASE_FAST -> $AOD_FAST), while ryzenadj moved it"
  echo "to $CTRL_FAST in the same run. The road is live (answers, buffer now"
  echo "correctly sized) but still does not reach the SMU for this command --"
  echo "the original 'inert' conclusion in firmware-limits.md stands, now on"
  echo "firmer ground (the command chain genuinely ran this time)."
fi

echo
echo "full log: $LOG"
