#!/usr/bin/env python3
"""Dump the PM table's per-core float groups.

Five 8-float groups in the SMU PM table are indexed by *physical* core id
(0..7), not by logical CPU. Confirmed by pinning a busy loop to one thread at a
time: `taskset -c 0 yes` saturates index 0, `taskset -c 14 yes` saturates index
7 (core 7). See pm-table.md.

  byte offset   index base   meaning
  0x3a0         232          unattributed (~3.7-6.2, rises only slightly)
  0x3c0         240          per-core clock in GHz (operating point)
  0x3e0         248          per-core effective clock in GHz (= 0x3c0 under load,
                              ~0 when idle)
  0x400         256          core busy % -- exactly 100.0000 when saturated
  0x5c0         368          unattributed, scales with load and clock

Both clocks were confirmed against `perf stat -C N -e cycles` on a core pinned
under a known cap: within 0.3 % under sustained load.

Read-only: open the PM table and unpack float32, no SMU command involved.

  sudo python3 pmtable-cores.py [label]
"""

import struct
import sys

PM = "/sys/kernel/ryzen_smu_drv/pm_table"
# This machine: cpu 2*i and 2*i+1 are the two threads of core i.
CPU_OF_CORE = [2 * i for i in range(8)]
GROUPS = [(0x3a0, "0x3a0"), (0x3c0, "0x3c0"), (0x3e0, "0x3e0"),
          (0x400, "0x400"), (0x5c0, "0x5c0")]


def cur_freq(cpu):
    """Context only. With amd-pstate-epp in active mode this does NOT track the
    delivered clock -- it reads 2.535 GHz for a core pinned to min=max=2.0 GHz --
    so never use it as ground truth. See pm-table.md."""
    try:
        with open("/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq"
                  % cpu) as fh:
            return int(fh.read()) / 1e6
    except OSError:
        return float("nan")


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    with open(PM, "rb") as fh:
        raw = fh.read()
    v = struct.unpack("<%df" % (len(raw) // 4), raw)

    print("== %s == len=%d floats=%d" % (label, len(raw), len(v)))
    print("core cpu  curGHz " + "".join("%9s" % name for _, name in GROUPS))
    for i in range(8):
        row = " %d    %2d  %6.3f " % (i, CPU_OF_CORE[i], cur_freq(CPU_OF_CORE[i]))
        row += "".join("%9.4f" % v[(off // 4) + i] for off, _ in GROUPS)
        print(row)


if __name__ == "__main__":
    main()
