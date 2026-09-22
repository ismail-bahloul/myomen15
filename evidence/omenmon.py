#!/usr/bin/env python3
"""Live power, thermal and fan monitor for the HP OMEN 15-en1xxx (CachyOS).

Everything shown comes from surfaces this repo mapped, and none of it is
available from a standard tool:

  - the SMU PM table, decoded as float32 -- 9 limits, each with its live value
    (see ../pm-table.md)
  - fan tachometers from the hp-wmi hwmon
  - die / GPU / NVMe / wifi temperatures from hwmon
  - the EC-facing platform profile, plus a check that the SMU limits still match
    a target (a platform_profile write resets them -- see ../firmware-limits.md)

Read-only. It never writes to the machine.

Usage:
    omenmon.py                 watch, target auto-picked from AC/battery state
                                (35/42/35 W, 85 C on AC; 15/18/15 W, 65 C on
                                battery -- matching /usr/local/bin/power-profile)
    omenmon.py --target 54 65 54 --temp 100   override, e.g. for PERF mode
    omenmon.py --interval 0.5

Keys: q quit, r force redraw.
"""

from __future__ import annotations

import argparse
import curses
import glob
import os
import struct
import time

PM_TABLE = "/sys/kernel/ryzen_smu_drv/pm_table"
PM_LEN = 2372

# PM table field order: each limit is followed by its live value.
PM_FIELDS = [
    ("STAPM", 0x00, "W"),
    ("PPT fast", 0x08, "W"),
    ("PPT slow", 0x10, "W"),
    ("PPT APU", 0x18, "W"),
    ("TDC VDD", 0x20, "A"),
    ("TDC SOC", 0x28, "A"),
    ("EDC VDD", 0x30, "A"),
    ("EDC SOC", 0x38, "A"),
    ("Tctl", 0x40, "C"),
]

HWMON_TEMPS = [
    ("Tctl", "k10temp", 1),
    ("iGPU", "amdgpu", 1),
    ("NVMe 1", "nvme", 1),
    ("Wifi", "iwlwifi_1", 1),
    ("acpitz", "acpitz", 1),
]


def hwmon_path(chip: str, filename: str = None) -> str | None:
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            with open(os.path.join(d, "name")) as fh:
                if fh.read().strip() != chip:
                    continue
        except OSError:
            continue
        return os.path.join(d, filename) if filename else d
    return None


def read_int(path: str | None) -> int | None:
    if not path:
        return None
    try:
        with open(path) as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return None


def read_pm() -> dict | None:
    """Return {'limits': {...}, 'live': {...}} or None if unavailable."""
    try:
        with open(PM_TABLE, "rb") as fh:
            raw = fh.read(PM_LEN)
    except OSError:
        return None
    if len(raw) < PM_LEN:
        return None
    vals = struct.unpack("<%df" % (PM_LEN // 4), raw)

    limits, live = {}, {}
    for name, off, _ in PM_FIELDS:
        idx = off // 4
        limits[name] = vals[idx]
        live[name] = vals[idx + 1]
    return {"limits": limits, "live": live}


def read_fans() -> tuple[int | None, int | None]:
    d = hwmon_path("hp")
    return read_int(os.path.join(d, "fan1_input") if d else None), \
           read_int(os.path.join(d, "fan2_input") if d else None)


def read_temps() -> dict:
    out = {}
    for label, chip, ch in HWMON_TEMPS:
        d = hwmon_path(chip)
        v = read_int(os.path.join(d, f"temp{ch}_input") if d else None)
        if v is not None:
            out[label] = v / 1000.0
    return out


def read_profile() -> str:
    try:
        with open("/sys/class/platform-profile/platform-profile-0/profile") as fh:
            return fh.read().strip()
    except OSError:
        return "?"


def read_power_supply() -> tuple[str, int | None]:
    ac = read_int("/sys/class/power_supply/ACAD/online")
    cap = read_int("/sys/class/power_supply/BAT0/capacity")
    return ("AC" if ac == 1 else "battery" if ac == 0 else "?"), cap


def bar(fraction: float, width: int) -> str:
    fraction = max(0.0, min(1.0, fraction))
    filled = int(round(fraction * width))
    return "#" * filled + "." * (width - filled)


def draw(stdscr, args) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(int(args.interval * 1000))
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # nominal
        curses.init_pair(2, curses.COLOR_YELLOW, -1)  # warm
        curses.init_pair(3, curses.COLOR_RED, -1)     # at the limit
        curses.init_pair(4, curses.COLOR_CYAN, -1)    # headings

    while True:
        ch = stdscr.getch()
        if ch in (ord("q"), ord("Q")):
            return

        stdscr.erase()
        h, w = stdscr.getmaxyx()
        if w < 62 or h < 16:
            stdscr.addstr(0, 0, "terminal too small (need 62x16)")
            stdscr.refresh()
            continue

        def head(row: int, text: str) -> None:
            attr = curses.color_pair(4) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
            stdscr.addstr(row, 2, text, attr)

        def line(row: int, label: str, value: str, frac: float | None,
                 barw: int = 20, note: str = "") -> None:
            attr = 0
            if frac is not None and curses.has_colors():
                if frac >= 0.95:
                    attr = curses.color_pair(3)
                elif frac >= 0.75:
                    attr = curses.color_pair(2)
                else:
                    attr = curses.color_pair(1)
            stdscr.addstr(row, 2, f"{label:<10}", curses.A_BOLD)
            stdscr.addstr(row, 13, value)
            if frac is not None:
                stdscr.addstr(row, 34, bar(frac, barw), attr)
            if note:
                stdscr.addstr(row, 34 + barw + 2, note, curses.A_DIM)

        stdscr.addstr(0, 2, "HP OMEN 15-en1xxx  |  live power, thermal & fan", curses.A_BOLD)
        profile, cap = read_power_supply()
        stdscr.addstr(1, 2, f"platform profile: {read_profile():<12}  power: {profile}"
                            + (f"  battery {cap}%" if cap is not None else ""),
                      curses.A_DIM)

        row = 3
        head(row, "SMU PM table  (live / limit)")
        row += 1
        pm = read_pm()
        warn = []
        if pm is None:
            stdscr.addstr(row, 4, "pm_table unavailable (ryzen_smu not loaded?)")
            row += 1
        else:
            on_battery = profile == "battery"
            tgt = args.target if args.target is not None else (
                [15.0, 18.0, 15.0] if on_battery else [35.0, 42.0, 35.0])
            temp_tgt = args.temp if args.temp is not None else (
                65.0 if on_battery else 85.0)
            targets = {"STAPM": tgt[0], "PPT fast": tgt[1],
                       "PPT slow": tgt[2], "Tctl": temp_tgt}
            for name, _off, unit in PM_FIELDS:
                lim = pm["limits"][name]
                live = pm["live"][name]
                frac = live / lim if lim else 0.0
                if unit == "C":
                    txt = f"{live:7.1f} / {lim:5.1f} {unit}"
                else:
                    txt = f"{live:7.2f} / {lim:5.1f} {unit}"
                note = ""
                if name in targets:
                    ok = abs(lim - targets[name]) < 0.6
                    note = "target ok" if ok else f"target {targets[name]:g}"
                    if not ok:
                        warn.append(f"{name} is {lim:g}, expected {targets[name]:g}")
                line(row, name, txt, frac, note=note)
                row += 1

        row += 1
        head(row, "Fans")
        row += 1
        f1, f2 = read_fans()
        stdscr.addstr(row, 2, f"{'CPU':<10}")
        stdscr.addstr(row, 13, f"{f1 if f1 is not None else '?':>7} rpm")
        stdscr.addstr(row, 30, f"{'GPU':<8}")
        stdscr.addstr(row, 39, f"{f2 if f2 is not None else '?':>7} rpm")
        row += 2

        head(row, "Temperatures")
        row += 1
        temps = read_temps()
        for label, val in temps.items():
            frac = val / 100.0
            line(row, label, f"{val:7.1f} C", frac, barw=20)
            row += 1

        if warn:
            row += 1
            attr = curses.color_pair(3) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
            stdscr.addstr(row, 2, "! SMU limits drifted from target:", attr)
            row += 1
            for msg in warn[:3]:
                stdscr.addstr(row, 4, msg, attr)
                row += 1
            stdscr.addstr(row, 4, "a platform_profile write resets them; "
                                  "power-profile.timer re-applies every 5 min", curses.A_DIM)

        stdscr.addstr(h - 1, 2, f"q quit   every {args.interval:g}s", curses.A_DIM)
        stdscr.refresh()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", nargs=3, type=float, metavar=("STAPM", "FAST", "SLOW"),
                   default=None,
                   help="expected SMU limits in W (default: auto, from AC/battery state)")
    p.add_argument("--temp", type=float, default=None,
                   help="expected Tctl limit in C (default: auto, from AC/battery state)")
    p.add_argument("--interval", type=float, default=1.0, help="refresh seconds")
    args = p.parse_args()
    try:
        curses.wrapper(draw, args)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
