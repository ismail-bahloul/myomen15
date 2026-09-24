#!/bin/bash
# power-profile - CPU/GPU power profiles for Ryzen 5800H
set -uo pipefail

log() { logger -t "power-profile" "$@"; }

# Write a value to all CPU sysfs files (e.g., scaling_governor, scaling_max_freq)
# Reports errors via log instead of silencing them
write_cpu_sysfs() {
  local file="$1" val="$2"
  for cpu in /sys/devices/system/cpu/cpu*/cpufreq/"$file"; do
    if [ -f "$cpu" ]; then
      echo "$val" > "$cpu" 2>/dev/null || log "WARN: $cpu write failed ($val)"
    fi
  done
}

# Log the SMU limits currently in effect. Called once per boot, before the first
# apply, so the journal records what the firmware seeded at POST. That is how you
# tell whether a BIOS "System Configuration" change actually took effect: the
# BIOS values are a POST-time seed only, and this service overwrites them ~12 s later.
log_current_limits() {
    local limits
    limits=$(/usr/bin/ryzenadj --info 2>/dev/null | awk -F'|' '
        /STAPM LIMIT|PPT LIMIT FAST|PPT LIMIT SLOW|THM LIMIT CORE/ {
            name=$2; val=$3
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", name)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
            printf "%s=%s ", name, val
        }')
    [ -n "$limits" ] && log "firmware/POST limits: ${limits% }"
}

# ------ Settings ------
GPU_AC=1800
GPU_AC_MIN=500   # AC frequency floor: avoids deep P8 sleep (cause of mini-freezes when launching an app)
GPU_BAT=400
TDP_AC=35000
TDP_BAT=15000
TEMP_AC=85
TEMP_BAT=65
FAST_AC=42000
FAST_BAT=18000
FREQ_AC=3200000
FREQ_BAT=2400000

# ------ Performance (unlocked) ------
apply_perf() {
    log "PERF profile: 4.4 GHz / 54W / GPU unlocked"
    write_cpu_sysfs scaling_governor performance
    write_cpu_sysfs scaling_max_freq 4465000
    write_cpu_sysfs energy_performance_preference performance
    /usr/bin/ryzenadj --stapm-limit=54000 --fast-limit=65000 --slow-limit=54000 \
             --apu-slow-limit=42000 --tctl-temp=90 || log "WARN: ryzenadj perf failed"
    nvidia-smi -rgc > /dev/null 2>&1 || true
    nvidia-smi -rmc > /dev/null 2>&1 || true
    echo ">>> PERF mode: CPU 4.4 GHz / 54W / GPU unlocked"
    log "OK: CPU 4.4 GHz / 54W, GPU unlocked"
}

apply_ac() {
    log "AC profile: 3.2 GHz / $((TDP_AC / 1000))W / GPU ${GPU_AC} MHz"
    write_cpu_sysfs scaling_governor powersave
    write_cpu_sysfs scaling_max_freq "${FREQ_AC}"
    write_cpu_sysfs energy_performance_preference balance_power
    /usr/bin/ryzenadj --stapm-limit=${TDP_AC} --fast-limit=${FAST_AC} --slow-limit=${TDP_AC} \
             --apu-slow-limit=22000 --tctl-temp=${TEMP_AC} 2>&1 || log "WARN: ryzenadj AC failed"
    nvidia-smi -lgc ${GPU_AC_MIN},${GPU_AC} > /dev/null 2>&1 || true
    iw dev wlan0 set power_save off 2>/dev/null || true
    echo ">>> AC mode: CPU 3.2 GHz / $((TDP_AC / 1000))W / GPU ${GPU_AC_MIN}–${GPU_AC} MHz (mem: dynamic)"
    log "OK: CPU 3.2 GHz / $((TDP_AC / 1000))W, GPU ${GPU_AC_MIN}-${GPU_AC} MHz (mem: auto)"
}

apply_battery() {
    log "Battery profile: $((FREQ_BAT / 1000000)).$(( (FREQ_BAT / 100000) % 10 )) GHz / $((TDP_BAT / 1000))W / GPU ${GPU_BAT} MHz"
    write_cpu_sysfs scaling_governor powersave
    write_cpu_sysfs scaling_max_freq "${FREQ_BAT}"
    write_cpu_sysfs energy_performance_preference power
    /usr/bin/ryzenadj --stapm-limit=${TDP_BAT} --fast-limit=${FAST_BAT} --slow-limit=${TDP_BAT} \
             --apu-slow-limit=15000 --tctl-temp=${TEMP_BAT} --power-saving 2>&1 || log "WARN: ryzenadj battery failed"
    nvidia-smi -lgc 0,${GPU_BAT} > /dev/null 2>&1 || true
    nvidia-smi -lmc 405 > /dev/null 2>&1 || true
    iw dev wlan0 set power_save on 2>/dev/null || true
    echo ">>> BATTERY mode: CPU $((FREQ_BAT / 1000000)).$(( (FREQ_BAT / 100000) % 10 )) GHz / $((TDP_BAT / 1000))W / GPU ${GPU_BAT} MHz"
    log "OK: CPU $((FREQ_BAT / 1000000)).$(( (FREQ_BAT / 100000) % 10 )) GHz / $((TDP_BAT / 1000))W, GPU ${GPU_BAT} MHz"
}

# ------ Main ------
case "${1:-balanced}" in
    perf|performance)
        apply_perf  ;;
    ac|plugged)
        apply_ac  ;;
    battery|onbattery)
        apply_battery  ;;
    auto|balanced|guard)
        # Record the firmware-seeded limits once per boot (see log_current_limits).
        if [ ! -e /run/power-profile.boot-seen ]; then
            log_current_limits
            : > /run/power-profile.boot-seen 2>/dev/null || true
        fi
        # guard: periodic re-apply (EC/firmware override workaround) - never clobber manual perf mode
        if [ "${1:-}" = "guard" ] && [ "$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)" = "performance" ]; then
            log "guard: PERF mode active, re-apply ignored"
            exit 0
        fi
        online=$(cat /sys/class/power_supply/ACAD/online 2>/dev/null || echo 0)
        if [ "$online" = "1" ]; then
            apply_ac
        else
            apply_battery
        fi
        ;;
    info)
        gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)
        freq_khz=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null)
        freq_ghz=$(awk "BEGIN { printf \"%.2f\", $freq_khz / 1000000 }" 2>/dev/null)

        temp_cpu=$(sensors 2>/dev/null | grep -E "^Tctl" | awk '{print $2}' | tr -d '+')
        temp_igpu=$(sensors 2>/dev/null | grep -E "^edge" | awk '{print $2}' | tr -d '+')
