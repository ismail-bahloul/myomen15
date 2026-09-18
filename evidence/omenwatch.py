#!/usr/bin/env python3
"""Watch the H2RA keyboard region while you press the backlight key.

Samples the EC-published keyboard bytes a few times a second and prints a line
only when something in the watched window changes. That turns "which byte
controls what" from guesswork into a diff.

Usage:
    omenwatch.py [seconds] [--window 0xEC0 0xF00]

Press the keyboard-backlight key (usually Fn + a function key) while it runs.
"""

from __future__ import annotations

import mmap
import os
import sys
import time

H2RA = 0xFE700000


def main() -> None:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else 20.0

    lo, hi = 0xEC0, 0xF00
    if "--window" in sys.argv:
        i = sys.argv.index("--window")
        lo, hi = int(sys.argv[i + 1], 0), int(sys.argv[i + 2], 0)

    fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    m = mmap.mmap(fd, 0x1000, offset=H2RA, access=mmap.ACCESS_READ)

    prev = bytes(m[lo:hi])
    print(f"watching H2RA 0x{lo:03x}-0x{hi:03x} for {duration:.0f}s")
    print("baseline:", prev.hex(" "))
    print("now press the keyboard-backlight key (Fn + ...)")
    print()

    end = time.time() + duration
    changes = 0
    while time.time() < end:
        cur = bytes(m[lo:hi])
        if cur != prev:
            changes += 1
            moved = [lo + i for i in range(len(cur)) if cur[i] != prev[i]]
            fields = ", ".join(f"0x{a:03x}: {prev[a-lo]:02x}->{cur[a-lo]:02x}" for a in moved)
            print(f"[{time.strftime('%H:%M:%S')}] {fields}")
            prev = cur
        time.sleep(0.15)

    print()
    if changes == 0:
        print("nothing changed in this window — the control byte is elsewhere.")
    else:
        print(f"{changes} change(s) observed.")
        print("final   :", bytes(m[lo:hi]).hex(" "))


if __name__ == "__main__":
    main()
