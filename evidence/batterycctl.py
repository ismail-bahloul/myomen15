#!/usr/bin/env python3
"""Battery charge control on the HP OMEN 15-en1xxx -- verified working.

The repo once recorded charge thresholds as unsupported because the battery
advertises no modes (`MBST = 0x00`) and the kernel exposes no
`charge_control_*` attributes. The DSDT says otherwise, and a controlled test
agrees with the DSDT:

    MBDC     EC 0xA6, the charge-control register
    GBCC     \\_SB.WMID.GBCC, the firmware's own reader for it

Writing `MBDC` to a mode value makes the EC stop maintaining the battery on AC
(`BAT0/status` goes Full -> Discharging and stays), and clearing it restores
`Full`. `GBCC` reports mode 0x02 while set and 0x00 after clearing, so the mode
is real rather than an echo. The EC sets the completion bit `MBDC & 0x10` within
~200 ms of the write.

Two mode encodings are used by the firmware's `SBCC` method (DSDT):

    MBDC = 0x0A   ->  GBCC reports mode 2
    MBDC = 0x0C   ->  GBCC reports mode 3

This tool writes `MBDC` through the ACPI EC bridge (`M041`), which is the same
path `ecbridge.py` uses, and polls for the ack itself instead of calling `SBCC`
-- `SBCC` waits on that bit in an *unbounded* AML loop, so driving it directly
keeps the timeout on this side.

Read-only unless asked. Always reversible: `clear` writes MBDC = 0x00, the same
revert both of `SBCC`'s branches share.

  sudo python3 batterycctl.py status
  sudo python3 batterycctl.py set 0x0A --yes      # apply a mode
  sudo python3 batterycctl.py clear --yes         # back to no cap
"""

import re
import sys
import time

EC = r"\_SB.PCI0.SBRG.EC0"
MBDC = 0xA6
ACK = 0x10
MODES = {0x0A: 2, 0x0C: 3}   # written value -> what GBCC reports


def call(method, *args):
    expr = method + (" " + " ".join(args) if args else "")
    with open("/proc/acpi/call", "w") as fh:
        fh.write(expr)
    with open("/proc/acpi/call") as fh:
        return fh.read().strip()


def parse_int(out):
    m = re.search(r"0x([0-9a-fA-F]+)", out)
    return int(m.group(1), 16) if m else None


def ec_read(off):
    return parse_int(call(f"{EC}.M040", hex(off)))


def ec_write(off, val):
    call(f"{EC}.M041", hex(off), hex(val))


def bat(field):
    try:
        with open("/sys/class/power_supply/BAT0/" + field) as fh:
            return fh.read().strip()
    except OSError:
        return "?"


def gbcc():
    return call(r"\_SB.WMID.GBCC")


def status():
    v = ec_read(MBDC)
    print("MBDC       = 0x%02x" % (v if v is not None else 0xFF))
    if v is not None:
        print("  mode bits 0x18 %s   ack 0x10 %s"
              % ("set" if v & 0x18 == 0x18 else "clear",
                 "set" if v & ACK else "clear"))
    print("GBCC       = %s" % gbcc())
    print("AC present = %s" % call(f"{EC}.ADPP"))
    print("battery    = %s %s%%" % (bat("status"), bat("capacity")))


def set_mode(val):
    if val not in MODES:
        sys.exit("mode must be 0x0A (GBCC mode 2) or 0x0C (mode 3)")
    if "--yes" not in sys.argv:
        sys.exit("about to WRITE EC MBDC = 0x%02x. Re-run with --yes." % val)
    ec_write(MBDC, val)
    for _ in range(30):
        v = ec_read(MBDC)
        if v is not None and v & ACK:
            print("MBDC = 0x%02x, EC acked; GBCC = %s" % (v, gbcc()))
            print("battery = %s %s%%" % (bat("status"), bat("capacity")))
            return
        time.sleep(0.1)
    print("no ack within 3 s; MBDC = 0x%02x, GBCC = %s"
          % (ec_read(MBDC) or 0, gbcc()))


def clear():
    if "--yes" not in sys.argv:
        sys.exit("about to WRITE EC MBDC = 0x00. Re-run with --yes.")
    ec_write(MBDC, 0x00)
    time.sleep(0.5)
    print("MBDC = 0x%02x, GBCC = %s" % (ec_read(MBDC) or 0, gbcc()))
    print("battery = %s %s%%" % (bat("status"), bat("capacity")))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip().splitlines()[-3].strip())
    cmd = sys.argv[1]
    if cmd == "status":
        status()
    elif cmd == "set":
        set_mode(int(sys.argv[2], 0))
    elif cmd == "clear":
        clear()
    else:
        sys.exit("unknown command: " + cmd)


if __name__ == "__main__":
    main()
