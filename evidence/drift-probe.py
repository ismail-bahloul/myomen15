#!/usr/bin/env python3
"""Sample the SMU limits and the mailbox registers together, fast, to catch the
drift and see whether anything *asks* for it.

`firmware-limits.md` established that OS-written limits drift back toward the
stock values a minute or two after an apply, with no writer, no inotify event,
and no EC register carrying the values -- "the mechanism is not established".
One angle not tried: if an external agent (the EC, the BIOS, a service) is
re-issuing an SMU command, the *mailbox* would show it; if the SMU re-derives
internally, the mailbox stays at whatever the last command was.

Reads only -- it never sends a command. Pair it with a separate `ryzenadj`
write so the write is not what is being measured.

  sudo python3 drift-probe.py 200 1 > drift.csv
"""

from __future__ import annotations

import struct
import sys
import time

DRV = "/sys/kernel/ryzen_smu_drv"
SMN = DRV + "/smn"
PM_TABLE = DRV + "/pm_table"
PM_LEN = 2372

PM_OFF = (0x00, 0x08, 0x10, 0x18, 0x40)          # STAPM, fast, slow, APU, Tctl
MAIL = (("mp1_cmd", 0x3B10528), ("mp1_rsp", 0x3B10564), ("mp1_arg0", 0x3B10998),
        ("rsmu_cmd", 0x3B10A20), ("rsmu_rsp", 0x3B10A80))


def smn_read(addr):
    with open(SMN, "wb", buffering=0) as fh:
        fh.write(struct.pack("<I", addr))
    with open(SMN, "rb") as fh:
        return struct.unpack("<I", fh.read(4))[0]


def pm_limits():
    data = open(PM_TABLE, "rb").read(PM_LEN)
    vals = struct.unpack("<%df" % (PM_LEN // 4), data)
    return [round(vals[o // 4]) for o in PM_OFF]


def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    iv = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    print("t,stapm,fast,slow,apu,tctl," + ",".join(n for n, _ in MAIL), flush=True)
    end = time.time() + dur
    while time.time() < end:
        lim = pm_limits()
        m = [smn_read(a) for _, a in MAIL]
        print("%.2f,%s" % (time.time(), ",".join(map(str, lim + m))), flush=True)
        time.sleep(iv)


if __name__ == "__main__":
    main()
