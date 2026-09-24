#!/bin/bash
# Does removing the frequency cap make SHORT bursts heat more?  A burst here is
# 1 s on 2 cores, the shape of "open an app and let it settle" -- far shorter
# than the sustained single-thread load st-ab.sh measured (which cost +3.4 W and
# +7 C for +26 % throughput).
#
# Sampled from the SMU PM table at 50 Hz: PPT VALUE FAST is at 0x0C, so the peak
# is caught without shelling out to ryzenadj. The per-core effective clock
# (0x3e0) is also read but is reported only as a rough figure -- it was seen to
# glitch above the 4.465 GHz part limit, so it is not a trustable peak.
set -u
PM=/sys/kernel/ryzen_smu_drv/pm_table

sudo systemctl stop power-profile-watch.service power-profile.timer
sudo /usr/local/bin/power-profile ac >/dev/null 2>&1

for mf in 3200000 4465000; do
  for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do
    echo "$mf" | sudo tee "$c" >/dev/null 2>&1
  done

  sudo python3 - "$mf" <<'PY' &
import glob, struct, sys, time
mf = int(sys.argv[1])
PM = "/sys/kernel/ryzen_smu_drv/pm_table"
FAST, SLOW, EFF = 0x0C // 4, 0x14 // 4, 0x3E0 // 4

def hwmon(name, fn):
    for d in glob.glob('/sys/class/hwmon/hwmon*'):
        try:
            if open(d + '/name').read().strip() == name:
                return float(open(d + '/' + fn).read())
        except OSError:
            pass
    return float('nan')

t0 = time.time()
pfast = pslow = tctl = 0.0
while time.time() - t0 < 12:
    with open(PM, 'rb') as fh:
        raw = fh.read()
    v = struct.unpack('<%df' % (len(raw) // 4), raw)
    pfast = max(pfast, v[FAST]); pslow = max(pslow, v[SLOW])
    t = hwmon('k10temp', 'temp1_input')
    if t == t:
        tctl = max(tctl, t / 1000.0)
    time.sleep(0.02)
print("  cap=%-8d burst: peak PPT-fast %.1f W  peak PPT-slow %.1f W  "
      "peak Tctl %.1f C" % (mf, pfast, pslow, tctl))
PY
  spid=$!
  sleep 3
  for i in 1 2 3 4 5 6; do taskset -c 0,2 ./evidence/load 0 1 2 >/dev/null 2>&1; sleep 0.5; done
  wait "$spid"
done

sudo /usr/local/bin/power-profile ac >/dev/null 2>&1
sudo systemctl start power-profile.timer power-profile-watch.service
echo "restored"
