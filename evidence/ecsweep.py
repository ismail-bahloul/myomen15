#!/usr/bin/env python3
"""Dump the EC register file and diff two dumps, offset by offset.

`ecbridge.py ec-dump` prints a human-readable table, which is fine to look at and
useless to compare: a change in one byte shifts nothing, but eyeballing 256 values
across several runs is hopeless. This writes the whole 256-byte space as JSON so
two states can be diffed mechanically.

Used to answer "which EC registers actually change?", the question that decides
whether the map is complete:

  idle x2, load, platform_profile x3  ->  only 18 of 256 offsets ever move,
  and 238 are identical across all six. See ec-map.md.

  sudo python3 ecsweep.py dump /tmp/ec_before.json
  # ... change one reversible thing ...
  sudo python3 ecsweep.py dump /tmp/ec_after.json
  python3 ecsweep.py diff /tmp/ec_before.json /tmp/ec_after.json
"""

import json
import re
import sys

EC = r"\_SB.PCI0.SBRG.EC0"


def acall(expr):
    with open("/proc/acpi/call", "w") as fh:
        fh.write(expr)
    with open("/proc/acpi/call") as fh:
        return fh.read().strip()


def read(off):
    m = re.search(r"0x([0-9a-fA-F]+)", acall("%s.M040 %s" % (EC, hex(off))))
    return int(m.group(1), 16) if m else -1


def dump():
    return [read(o) for o in range(256)]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip().splitlines()[-3].strip())
    cmd = sys.argv[1]
    if cmd == "dump":
        with open(sys.argv[2], "w") as fh:
            json.dump(dump(), fh)
    elif cmd == "diff":
        a = json.load(open(sys.argv[2]))
        b = json.load(open(sys.argv[3]))
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                print("  0x%02x   %02x -> %02x" % (i, x, y))
    else:
        sys.exit("unknown command: " + cmd)


if __name__ == "__main__":
    main()
