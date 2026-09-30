#!/usr/bin/env python3
"""Attribute the unattributed Cezanne PM-table floats by state, not by guessing.

`pm-table.md` decodes the first 18 floats (nine limits + nine live values) and
leaves everything from 0x48 on unattributed. Four of those (0x68-0x74) look like
clocks or voltage planes. This script identifies each field by *what it tracks*:
it reads the table under controlled CPU load and under a fixed clock cap, so a
field that rises with load is power-ish, one that follows the clock is a clock,
and one that moves with the operating point but stays in the ~0.5-1.5 range is a
voltage plane.

Read-only: it only reads /sys/kernel/ryzen_smu_drv/pm_table. The load it applies
is ordinary user processes, killed before it returns. The optional clock cap is
written to cpufreq and restored on exit.

Run as root (the pm_table node is root-only):

    sudo python3 evidence/pmtable-attr.py            # idle / 1 core / all cores
    sudo python3 evidence/pmtable-attr.py 1000000    # the same, capped to 1 GHz
"""
import glob
import os
import signal
import struct
import subprocess
import sys
import time

NODE = "/sys/kernel/ryzen_smu_drv/pm_table"
POLICIES = sorted(glob.glob("/sys/devices/system/cpu/cpufreq/policy*"))
# Everything from the second thermal triplet to the tail.
OFFS = list(range(0x48, 0xA0, 4))
# Logical CPUs, from the cpufreq policies' affected_cpus (8 cores / 16 threads
# on the 5800H; booting with fewer cores still works).
def policy_cpus():
    cpus = []
    for p in POLICIES:
        try:
            cpus += [int(c) for c in open(os.path.join(p, "affected_cpus")).read().split()]
        except OSError:
            pass
    return sorted(set(cpus))


CPUS = policy_cpus()


def snap():
    d = open(NODE, "rb").read()
    return struct.unpack("<%df" % (len(d) // 4), d)


def read_freqs():
    out = {}
    for p in POLICIES:
        name = os.path.basename(p)
        try:
            out[name] = open(os.path.join(p, "scaling_max_freq")).read().strip()
        except OSError:
            pass
    return out


def write_freq(hz):
    for p in POLICIES:
        try:
            with open(os.path.join(p, "scaling_max_freq"), "w") as f:
                f.write(str(hz))
        except OSError as e:
            print("  ! could not set %s: %s" % (p, e), file=sys.stderr)


def measure(label, secs, cores):
    """Hold `cores` busy for `secs`, then read the table while they run."""
    procs = []
    for c in cores:
        procs.append(subprocess.Popen(
            ["taskset", "-c", str(c), "yes"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True))
    time.sleep(secs)
    v = snap()
    for p in procs:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for p in procs:
        p.wait()
    # Guarantee no stray load survives into the next state (a leaked `yes` here
    # silently turns the next "idle" into an all-core measurement).
    subprocess.run(["pkill", "-9", "-x", "yes"], stderr=subprocess.DEVNULL)
    time.sleep(2.0)  # let the operating point settle before the next state
    return v, label


def main():
    cap = None
    if len(sys.argv) > 1:
        cap = int(sys.argv[1])
    saved = read_freqs()

    print("PM table: %s  (%d bytes)" % (NODE, os.path.getsize(NODE)))
    print("policies: %s" % ", ".join("%s=%s" % kv for kv in sorted(saved.items())))

    # A clock cap applied *before* every state, so a capped run can be diffed
    # against an uncapped one state-for-state: a field that tracks the cap is a
    # clock, one that tracks the operating point but stays in ~0.5-1.5 is volts.
    if cap is not None:
        print("capping every policy to %d kHz for the whole run" % cap)
        write_freq(cap)
        time.sleep(1.0)
    print()

    results = []
    results.append(measure("idle", 4, []))
    results.append(measure("1 core", 6, [CPUS[0]]))
    results.append(measure("all cores", 8, CPUS))

    if cap is not None:
        for name, hz in saved.items():
            try:
                with open("/sys/devices/system/cpu/cpufreq/%s/scaling_max_freq" % name, "w") as f:
                    f.write(hz)
            except OSError:
                pass
        print("  (freq caps restored)")

    labels = ["%-14s" % lab for _, lab in results]
    print()
    print("%-6s" % "off" + "".join(labels))
    for off in OFFS:
        row = "0x%02x  " % off
        for v, _ in results:
            row += "%-14.4f" % v[off // 4]
        print(row)


if __name__ == "__main__":
    main()
