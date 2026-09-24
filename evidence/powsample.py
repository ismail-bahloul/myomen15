#!/usr/bin/env python3
"""Sample CPU package power and thermals once a second, as CSV.

For the joules-per-iteration measurement that record/03-open-questions.md left
open. STAPM VALUE is the CPU-package-power proxy ryzenadj already reports (the
number that section points at); PPT VALUE SLOW is kept beside it as a second
view. hwmon directories are resolved by name, not by index, since the indices
are not stable across boots.

  sudo python3 powsample.py <out.csv> <seconds> [interval]
"""

import glob
import subprocess
import sys
import time


def hwmon_dir(name):
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            with open(d + "/name") as fh:
                if fh.read().strip() == name:
                    return d
        except OSError:
            pass
    return None


def read_int(path):
    try:
        with open(path) as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return -1


def field(info, name):
    for line in info.splitlines():
        parts = line.split("|")
        if len(parts) >= 3 and parts[1].strip() == name:
            return parts[2].strip()
    return ""


def main():
    out, dur = sys.argv[1], int(sys.argv[2])
    iv = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    k10 = hwmon_dir("k10temp")
    hp = hwmon_dir("hp")
    FREQ = "/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq"
    end = time.time() + dur
    with open(out, "w") as fh:
        fh.write("ts,epoch,stapm_limit,stapm_value,ppt_fast_value,ppt_slow_value,"
                 "cur_freq,tctl,fan1,fan2\n")
        while time.time() < end:
            info = subprocess.run(["sudo", "ryzenadj", "--info"],
                                  capture_output=True, text=True).stdout
            tctl = read_int(k10 + "/temp1_input") if k10 else -1
            fan1 = read_int(hp + "/fan1_input") if hp else -1
            fan2 = read_int(hp + "/fan2_input") if hp else -1
            fh.write("%s,%d,%s,%s,%s,%s,%d,%d,%d,%d\n" % (
                time.strftime("%H:%M:%S"), int(time.time()),
                field(info, "STAPM LIMIT"), field(info, "STAPM VALUE"),
                field(info, "PPT VALUE FAST"), field(info, "PPT VALUE SLOW"),
                read_int(FREQ), tctl, fan1, fan2))
            fh.flush()
            time.sleep(iv)


if __name__ == "__main__":
    main()
