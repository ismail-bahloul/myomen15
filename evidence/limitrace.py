#!/usr/bin/env python3
"""Race the EC registers against the SMU limits, to find what moves first.

`50/65/54` has been seen twice on this machine with no `platform_profile` write
and no known writer. This watches both surfaces at high frequency and logs any
EC register that moves *outside the set already known to be telemetry*, together
with any change in the SMU limits, so the ordering can be read off.

Known-volatile EC registers (excluded, they change continuously and are already
mapped in ec-map.md):

    0x2E 0x2F       fan duty readback
    0xB0-0xB3       fan tachometers
    0x42 0x48 0x49 0x57 0x58 0x59   temperatures
    0x83 0x87 0x63  counters

Anything else that moves is logged. Read-only.

Usage: limitrace.py [seconds]
"""

from __future__ import annotations

import struct
import sys
import time

PM_TABLE = "/sys/kernel/ryzen_smu_drv/pm_table"
EC_IO = "/sys/kernel/debug/ec/ec0/io"
PM_LEN = 2372

L_STAPM, L_FAST, L_SLOW, L_TCTL = 0x00, 0x08, 0x10, 0x40

TELEMETRY = {
    0x2C, 0x2D, 0x2E, 0x2F,          # fan duty setpoint and readback
    0xB0, 0xB1, 0xB2, 0xB3,          # fan tachometers
    0x42, 0x48, 0x49, 0x57, 0x58, 0x59,   # temperatures
    0x83, 0x87, 0x63, 0x9D,          # counters
}


def limits():
    with open(PM_TABLE, "rb") as fh:
        raw = fh.read(PM_LEN)
    v = struct.unpack("<%df" % (PM_LEN // 4), raw)
    return (round(v[L_STAPM // 4], 1), round(v[L_FAST // 4], 1),
            round(v[L_SLOW // 4], 1), round(v[L_TCTL // 4], 1))


def ec():
    with open(EC_IO, "rb") as fh:
        return fh.read(256)


def show(lim):
    return "%-14s Tctl lim %g" % ("/".join("%g" % x for x in lim[:3]), lim[3])


def main():
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 1800

    prev_lim = limits()
    prev_ec = ec()
    print("%s  start   %s" % (time.strftime("%H:%M:%S"), show(prev_lim)), flush=True)

    end = time.time() + duration
    last_heartbeat = time.time()

    while time.time() < end:
        cur_lim = limits()
        if cur_lim != prev_lim:
            print("%s  LIMITS  %s -> %s"
                  % (time.strftime("%H:%M:%S"),
                     "/".join("%g" % x for x in prev_lim[:3]),
                     "/".join("%g" % x for x in cur_lim[:3])), flush=True)
            prev_lim = cur_lim

        cur_ec = ec()
        moved = [i for i in range(256)
                 if cur_ec[i] != prev_ec[i] and i not in TELEMETRY]
        if moved:
            print("%s  EC      %s"
                  % (time.strftime("%H:%M:%S"),
                     ", ".join("0x%02X: %02x->%02x" % (i, prev_ec[i], cur_ec[i])
                               for i in moved)), flush=True)
        prev_ec = cur_ec

        # a heartbeat, so a silent run is distinguishable from a dead one
        if time.time() - last_heartbeat >= 300:
            print("%s  alive   %s" % (time.strftime("%H:%M:%S"), show(cur_lim)),
                  flush=True)
            last_heartbeat = time.time()

        time.sleep(0.25)


if __name__ == "__main__":
    main()
