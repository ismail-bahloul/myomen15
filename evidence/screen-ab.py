#!/usr/bin/env python3
"""Measure the screen's cost on battery: brightness first, then refresh rate.

The panel is a first-order battery load and nothing else in this repo has touched
it. This samples the battery draw across a few (brightness, refresh) states, sets
them through the backlight sysfs and `kscreen-doctor`, and restores the original
state on exit -- including on Ctrl-C.

Run as the user (kscreen-doctor talks to the running compositor); the backlight
write goes through `sudo -n`.

    python3 evidence/screen-ab.py            # as-is / dim / dim+60Hz / bright+60Hz
    python3 evidence/screen-ab.py --secs 25
"""
import glob
import os
import re
import statistics
import subprocess
import sys
import time

POWER = "/sys/class/power_supply/BAT0/power_now"
BACKLIGHT = sorted(glob.glob("/sys/class/backlight/*"))
OUTPUT = "eDP-1"


def read(path):
    try:
        return open(path).read().strip()
    except OSError:
        return None


def battery_w():
    v = read(POWER)
    return round(int(v) / 1e6, 2) if v else None


def on_ac():
    return read("/sys/class/power_supply/AC/online") or read("/sys/class/power_supply/ACAD/online")


def backlight_read():
    """(current, max) raw backlight values, or (None, None)."""
    if not BACKLIGHT:
        return None, None
    cur = read(os.path.join(BACKLIGHT[0], "brightness"))
    mx = read(os.path.join(BACKLIGHT[0], "max_brightness"))
    return (int(cur), int(mx)) if cur and mx else (None, None)


def backlight_write_pct(pct):
    _, mx = backlight_read()
    if mx is None:
        print("  ! no backlight node", file=sys.stderr)
        return False
    r = subprocess.run(["sudo", "-n", "tee", os.path.join(BACKLIGHT[0], "brightness")],
                       input=str(round(mx * pct / 100)), text=True,
                       stdout=subprocess.DEVNULL)
    return r.returncode == 0


def modes():
    """[(id, res, refresh, current, preferred)] from kscreen-doctor -o."""
    try:
        txt = subprocess.run(["kscreen-doctor", "-o"], capture_output=True, text=True,
                             timeout=15).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    txt = re.sub(r"\x1b\[[0-9;]*m", "", txt)   # kscreen-doctor colours its output
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("Modes:"):
            return [(int(m.group(1)), m.group(2), float(m.group(3)),
                     m.group(4) == "*", m.group(5) == "!")
                    for m in re.finditer(r"(\d+):(\d+x\d+)@([\d.]+)(\*?)(!?)", s)]
    return []


def current_mode():
    return next((m for m in modes() if m[3]), None)


def set_mode(mid):
    return subprocess.run(["kscreen-doctor", "output.%s.mode.%d" % (OUTPUT, mid)],
                          capture_output=True, timeout=10).returncode == 0


def sample(secs):
    vals = []
    for _ in range(secs):
        w = battery_w()
        if w is not None:
            vals.append(w)
        time.sleep(1.0)
    return statistics.mean(vals) if vals else float("nan")


def main():
    secs = 20
    if "--secs" in sys.argv:
        secs = int(sys.argv[sys.argv.index("--secs") + 1])

    cur = current_mode()
    if not cur:
        raise SystemExit("could not read the output modes (is kscreen-doctor available?)")
    res = cur[1]
    at_res = [m for m in modes() if m[1] == res]
    pick = lambda hz: min(at_res, key=lambda m: abs(m[2] - hz))
    m60 = pick(60)

    b0, bmx = backlight_read()
    p0 = round(100 * b0 / bmx) if b0 and bmx else None

    print("output %s @ %s   brightness %s%%   on AC: %s   battery: %s W"
          % (OUTPUT, res, p0, on_ac(), battery_w()))
    print("modes at %s: %s" % (res, ", ".join("%d=%gHz" % (m[0], m[2]) for m in at_res)))
    print("sampling %d s per phase\n" % secs)

    #                        label                 brightness%  mode id
    phases = [("as-is", None, None),
              ("dim 50%", 50, None),
              ("dim 50% + 60Hz", 50, m60[0]),
              ("full 100% + 60Hz", 100, m60[0])]

    rows = []
    try:
        for label, pct, mid in phases:
            if pct is not None:
                backlight_write_pct(pct)
            if mid is not None:
                set_mode(mid)
            time.sleep(4)  # let the compositor and the panel settle
            rows.append((label, sample(secs), backlight_read(), current_mode()))
    finally:
        if b0 is not None:
            backlight_write_pct(p0)
        set_mode(cur[0])
        print("restored: brightness %s%%, mode %s @ %gHz" % (p0, res, cur[2]))

    print()
    print("%-18s %9s   %-11s %s" % ("state", "power", "brightness", "mode"))
    for label, p, bl, md in rows:
        btxt = "%d%%" % round(100 * bl[0] / bl[1]) if bl[0] else "-"
        mtxt = "%s@%gHz" % (md[1], md[2]) if md else "-"
        print("%-18s %7.2f W   %-11s %s" % (label, p, btxt, mtxt))


if __name__ == "__main__":
    main()
