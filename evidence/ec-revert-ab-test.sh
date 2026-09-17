#!/usr/bin/env bash
# ec-revert-ab-test.sh — is the HP EC reverting OS-written SMU limits, and is
# `nbfc` the trigger?
#
# Phase A: nbfc running.   Phase B: nbfc stopped.   ~21 min total.
#
# The power-profile guard MUST be stopped for the duration, otherwise it
# re-applies every 5 min and we would be measuring our own script.
#
# Outputs (next to this script): nbfc_on.csv, nbfc_off.csv, ab-test.log
#
# Result to read: in each CSV, the `stapm_limit` / `ppt_fast_limit` columns.
# A revert shows up as 35/42/35 -> 50/65/54 without anyone writing.
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$DIR"
echo $$ > ab-test.pid

log() { printf '%s %s\n' "$(date -Is)" "$*" | tee -a ab-test.log; }

STAPM=35000
FAST=42000
SLOW=35000

write_limits() {
  sudo -n ryzenadj --stapm-limit="$STAPM" --fast-limit="$FAST" --slow-limit="$SLOW" >/dev/null 2>&1
}

# ryzenadj --info is a pipe-delimited table (| Name | Value | Parameter |),
# so the value is field 3, not the last field.
poll() {
  local out="$1" dur="$2" end info ac f1 f2
  echo "ts,epoch,stapm_limit,stapm_value,ppt_fast_limit,ppt_fast_value,tctl_limit,ac,fan1,fan2" > "$out"
  end=$(( $(date +%s) + dur ))
  while [ "$(date +%s)" -lt "$end" ]; do
    info=$(sudo -n ryzenadj --info 2>/dev/null)
    get() { printf '%s\n' "$info" | awk -F'|' -v p="$1" 'index($2,p){gsub(/[ \t\r]/,"",$3); print $3; exit}'; }
    ac=$(cat /sys/class/power_supply/ACAD/online 2>/dev/null || echo '?')
    f1=$(cat /sys/class/hwmon/hwmon*/fan1_input 2>/dev/null | head -1)
    f2=$(cat /sys/class/hwmon/hwmon*/fan2_input 2>/dev/null | head -1)
    printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
      "$(date -Is)" "$(date +%s)" \
      "$(get 'STAPM LIMIT')" "$(get 'STAPM VALUE')" \
      "$(get 'PPT LIMIT FAST')" "$(get 'PPT VALUE FAST')" \
      "$(get 'THM LIMIT CORE')" "$ac" "$f1" "$f2" >> "$out"
    sleep 2
  done
}

log "=== stopping the power-profile guard (it would mask the revert) ==="
sudo -n systemctl stop power-profile.timer
sudo -n systemctl stop power-profile.service

log "=== PHASE A: nbfc RUNNING ==="
sudo -n systemctl start nbfc_service.service
sleep 10
write_limits
log "phase A: wrote $STAPM/$FAST/$SLOW"
poll nbfc_on.csv 600
log "phase A: done"

log "=== PHASE B: nbfc STOPPED (EC controls the fans) ==="
sudo -n systemctl stop nbfc_service.service
sleep 30
write_limits
log "phase B: wrote $STAPM/$FAST/$SLOW"
poll nbfc_off.csv 600
log "phase B: done"

log "=== restoring normal operation ==="
sudo -n systemctl start nbfc_service.service
sudo -n systemctl start power-profile.timer
sleep 2
sudo -n systemctl start power-profile.service
log "restored. DONE"
