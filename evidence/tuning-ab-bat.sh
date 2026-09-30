#!/bin/bash
# Battery A/B for the levers AC could not judge. Unplugged, deployed battery
# profile, arms interleaved A/B x rounds. Restores ASPM=default and no scx on exit.
# NB aspm is NOT usable on this machine: the FADT declares ASPM unsupported, so the
# kernel refuses to change the policy (see runtime-levers.md). Kept for reference.
#   aspm : pcie_aspm policy  default vs powersupersave   -> idle system draw
#   scx  : scx_lavd loaded vs default scheduler          -> idle draw + wake latency under load
#   evidence/tuning-ab-bat.sh aspm|scx [rounds]
# Draw is BAT power_now (whole system, uW): the number STAPM cannot see.
set -u
cd "$(dirname "$0")/.."
OUT=evidence/tuning-ab; mkdir -p "$OUT"
LEVER=${1:?aspm|scx}; ROUNDS=${2:-3}
POL=/sys/module/pcie_aspm/parameters/policy
BAT=$(ls -d /sys/class/power_supply/BAT* | head -1)
[ "$(cat /sys/class/power_supply/ACAD/online)" = 0 ] || { echo "unplug first"; exit 1; }
SCXPID=""
cleanup() {
  [ "$LEVER" = aspm ] && echo default | sudo tee $POL >/dev/null
  [ -n "$SCXPID" ] && sudo kill "$SCXPID" 2>/dev/null
}
trap cleanup EXIT

idle_draw() {  # median W over 45 s, 1 sample / 1.5 s
  for i in $(seq 30); do cat $BAT/power_now; sleep 1.5; done | sort -n \
    | awk '{a[NR]=$1} END {printf "%.2f", a[int((NR+1)/2)]/1e6}'
}
arm() {
  case "$LEVER:$1" in
    aspm:A) echo default          | sudo tee $POL >/dev/null ;;
    aspm:B) echo powersupersave   | sudo tee $POL >/dev/null ;;
    scx:A)  [ -n "$SCXPID" ] && { sudo kill "$SCXPID"; SCXPID=""; sleep 2; } ;;
    scx:B)  sudo scx_lavd >"$OUT/scx-lavd-bat.log" 2>&1 & SCXPID=$!
            for i in $(seq 30); do [ "$(cat /sys/kernel/sched_ext/state)" = enabled ] && break; sleep 1; done
            [ "$(cat /sys/kernel/sched_ext/state)" = enabled ] || { echo "scx not enabled after 30 s"; exit 1; } ;;
  esac
}
links() { sudo lspci -vv 2>/dev/null | grep -c "LnkCtl:.*ASPM L[01s]*[ /A-Za-z0-9]* Enabled"; }

date +%T > "$OUT/$LEVER-bat.start"
for r in $(seq "$ROUNDS"); do
  for a in A B; do
    arm $a; sleep 25   # settle
    tag="$LEVER-$a-r$r"
    echo "$tag idle_W=$(idle_draw) policy=$(cat $POL | grep -o '\[[a-z]*\]') soc_cpu_W=$(sudo ryzenadj -i 2>/dev/null | awk -F'|' '/STAPM VALUE/ {gsub(/ /,"",$3); print $3}')" | tee -a "$OUT/$LEVER-bat.txt"
    [ "$LEVER" = aspm ] && echo "$tag aspm_links_enabled=$(links)" | tee -a "$OUT/$LEVER-bat.txt"
    if [ "$LEVER" = scx ]; then
      ./evidence/load 5 20 16 > "$OUT/$tag-load.txt" & L=$!
      sleep 6; echo "$tag $(./evidence/wakelat 15 4)" | tee -a "$OUT/$LEVER-bat.txt"
      wait $L
      echo "$tag load: $(grep -h throughput_Mi_s "$OUT/$tag-load.txt")" | tee -a "$OUT/$LEVER-bat.txt"
    fi
  done
done
echo "--- kernel messages since start (AER / nvme / iwlwifi errors)"
sudo journalctl -k --no-pager --since "$(cat $OUT/$LEVER-bat.start)" 2>/dev/null | grep -iE "aer|nvme.*(error|timeout|reset)|iwlwifi.*(error|fail)|pcieport.*error" | head -20
echo done
