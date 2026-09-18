#!/usr/bin/env python3
"""Find what resets the SMU power limits.

The repo recorded that writing `/sys/class/platform-profile/.../profile` makes the
EC re-apply its own limits. A quick check suggested that is not true any more, so
this watches both surfaces at once and lets the data decide:

  - writes to platform_profile, caught with inotify
  - the SMU limits, polled through the PM table

A distinctive limit is written first, so the resulting value identifies the
writer:

    37/44/37  -> only our own write, nothing has changed them
    35/42/35  -> power-profile.timer (its configured AC target)
    54/65/54  -> the EC / POST stock profile

Run as root. Read-only apart from the one initial limit write.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import select
import struct
import sys
import time

PM_TABLE = "/sys/kernel/ryzen_smu_drv/pm_table"
PROFILE = "/sys/class/platform-profile/platform-profile-0/profile"

IN_MODIFY, IN_CLOSE_WRITE, IN_NONBLOCK = 0x2, 0x8, 0o4000

# PM table offsets for the live values are limit+1
L_STAPM, L_FAST, L_SLOW, L_TCTL = 0x00, 0x08, 0x10, 0x40

WRITTEN = (37.0, 44.0, 37.0)


def limits() -> tuple[float, float, float, float]:
    with open(PM_TABLE, "rb") as fh:
        vals = struct.unpack("<593f", fh.read(2372))
    return (vals[L_STAPM // 4], vals[L_FAST // 4],
            vals[L_SLOW // 4], vals[L_TCTL // 4])


def label(lim: tuple[float, float, float, float]) -> str:
    s, f, w, t = lim
    if abs(s - WRITTEN[0]) < 0.6 and abs(f - WRITTEN[1]) < 0.6:
        return "OURS (37/44/37)"
    if abs(s - 35.0) < 0.6 and abs(f - 42.0) < 0.6:
        return "power-profile.timer (35/42/35)"
    if abs(s - 54.0) < 0.6 and abs(f - 65.0) < 0.6:
        return "EC / POST stock (54/65/54)"
    return "?"


def set_limits() -> None:
    import subprocess
    subprocess.run(["ryzenadj", "-a", str(int(WRITTEN[0] * 1000)),
                    "-b", str(int(WRITTEN[1] * 1000)),
                    "-c", str(int(WRITTEN[2] * 1000))], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ctx() -> str:
    """Thermal and fan context, for correlating a revert with a cause."""
    def rd(p):
        try:
            with open(p) as fh:
                return int(fh.read().strip())
        except OSError:
            return None
    tctl = rd("/sys/class/hwmon/hwmon6/temp1_input")
    f1 = rd("/sys/class/hwmon/hwmon7/fan1_input")
    f2 = rd("/sys/class/hwmon/hwmon7/fan2_input")
    ac = rd("/sys/class/power_supply/ACAD/online")
    parts = []
    if tctl is not None:
        parts.append(f"Tctl {tctl/1000:.0f}C")
    if f1 is not None and f2 is not None:
        parts.append(f"fans {f1}/{f2}")
    parts.append("AC" if ac == 1 else "batt")
    return "  ".join(parts)


def main() -> None:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 180

    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    fd = libc.inotify_init1(IN_NONBLOCK)
    if fd < 0:
        sys.exit("inotify_init1 failed")
    if libc.inotify_add_watch(fd, PROFILE.encode(), IN_MODIFY | IN_CLOSE_WRITE) < 0:
        sys.exit(f"cannot watch {PROFILE}")

    print(f"watching {PROFILE} and the SMU limits for {duration:.0f}s\n")

    set_limits()
    time.sleep(0.5)
    cur = limits()
    prev = cur
    print(f"[{time.strftime('%H:%M:%S')}] wrote {WRITTEN[0]:g}/{WRITTEN[1]:g}/{WRITTEN[2]:g}"
          f"  now: {cur[0]:g}/{cur[1]:g}/{cur[2]:g}  -> {label(cur)}")

    end = time.time() + duration
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 1.0)
        if r:
            data = os.read(fd, 4096)
            for i in range(0, len(data), 16):
                _, mask, _, _ = struct.unpack_from("iIII", data, i)
                kind = "CLOSE_WRITE" if mask & IN_CLOSE_WRITE else "MODIFY"
                try:
                    with open(PROFILE) as fh:
                        val = fh.read().strip()
                except OSError:
                    val = "?"
                print(f"[{time.strftime('%H:%M:%S')}] platform_profile {kind} -> {val!r}")

        cur = limits()
        if cur != prev:
            print(f"[{time.strftime('%H:%M:%S')}] LIMITS CHANGED: "
                  f"{prev[0]:g}/{prev[1]:g}/{prev[2]:g} -> {cur[0]:g}/{cur[1]:g}/{cur[2]:g}"
                  f"  -> {label(cur)}")
            print(f"             context: {ctx()}")
            prev = cur

    print(f"\n[{time.strftime('%H:%M:%S')}] done. final: "
          f"{prev[0]:g}/{prev[1]:g}/{prev[2]:g} ({label(prev)})")


if __name__ == "__main__":
    main()
