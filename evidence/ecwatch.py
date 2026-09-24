#!/usr/bin/env python3
"""Watch selected EC registers (plus Tctl and fan) while a load runs.

Targets the two offsets ec-map.md leaves unresolved: 0x62/0x63 (a 16-bit BE
value seen at 0x0604 and 0x0000) and 0xB7 (57-58, +1 under sustained load).
Reads the EC through ec_sys (/sys/kernel/debug/ec/ec0/io), which needs root.

  sudo python3 ecwatch.py <seconds> [interval]
"""

import glob
import sys
import time

EC = "/sys/kernel/debug/ec/ec0/io"
OFFSETS = [0x49, 0x57, 0x58, 0x59, 0x62, 0x63, 0x87, 0x95,
           0xB0, 0xB1, 0xB2, 0xB3, 0xB7, 0xBA]


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


def main():
    dur = int(sys.argv[1])
    iv = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    k10 = hwmon_dir("k10temp")
    hp = hwmon_dir("hp")
    hdr = ["ts"] + ["0x%02X" % o for o in OFFSETS] + ["tctl", "fan1"]
    print(",".join(hdr))
    end = time.time() + dur
    while time.time() < end:
        with open(EC, "rb") as fh:
            ec = fh.read(256)
        vals = ["%d" % ec[o] for o in OFFSETS]
        tctl = read_int(k10 + "/temp1_input") if k10 else -1
        fan1 = read_int(hp + "/fan1_input") if hp else -1
        print(",".join([time.strftime("%H:%M:%S")] + vals + [str(tctl), str(fan1)]),
              flush=True)
        time.sleep(iv)


if __name__ == "__main__":
    main()
