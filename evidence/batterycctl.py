#!/usr/bin/env python3
"""The HP battery charge-control register on the 15-en1xxx -- decoded, and
what writing it actually does.

    MBDC   EC 0xA6                  the charge-control register
    GBCC   \\_SB.WMID.GBCC          the firmware's own reader for it

Writing `MBDC` to a mode value does **not** hold a charge threshold. Measured on
AC from 100 %: the EC stops charging and the pack discharges continuously --
80 % at 12:05, 70 at 12:13, 60 at 12:20, 55 at 12:26 -- with no plateau and no
resumption. Clearing it restores charging immediately. So the mode is "stop
charging", not "cap at X". (A threshold at 50 % or below was not excluded; the
test was stopped at 55 %.)

The cap that *does* hold is the BIOS "battery optimizer", and it works
differently: it lowers `BFCC`, the reported full-charge capacity, so the pack
simply charges to a smaller "Full". See `capacity`.

The EC acknowledges a write by setting `MBDC & 0x10` within ~200 ms, and `GBCC`
reports the mode back (`0x0A` -> mode 2, `0x0C` -> mode 3), so a write here is
verifiable rather than an echo.

Writes go through the ACPI EC bridge (`M041`) and the ack is polled here rather
than by `SBCC`: `SBCC` waits on that bit in an *unbounded* AML loop, so the
timeout stays on this side.

  sudo python3 batterycctl.py status
  sudo python3 batterycctl.py capacity        # design (BADC) vs reported full (BFCC)
  sudo python3 batterycctl.py set 0x0A --yes  # mode 2: stop charging
  sudo python3 batterycctl.py clear --yes     # resume charging
  sudo python3 batterycctl.py watch 20        # log capacity and status

Not persisted, on purpose: `MBDC` is EC RAM, cleared on a cold boot and on an AC
transition, and wiring "stop charging" to run at every boot is not something to
do by default.
"""

import re
import sys
import time

EC = r"\_SB.PCI0.SBRG.EC0"
MBDC = 0xA6
ACK = 0x10
MODES = {0x0A: 2, 0x0C: 3}   # written value -> what GBCC reports

# Capacity registers (u16 little-endian), from the DSDT field block:
BADC = 0x70   # design capacity, mAh
BFCC = 0x72   # reported full-charge capacity, mAh
BADV = 0x74   # design voltage, mV


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


def do_set(val, require_yes):
    if val not in MODES:
        sys.exit("mode must be 0x0A (GBCC mode 2) or 0x0C (mode 3)")
    if require_yes and "--yes" not in sys.argv:
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


def rd16(off):
    lo = ec_read(off)
    hi = ec_read(off + 1)
    return None if lo is None or hi is None else lo | (hi << 8)


def capacity():
    """Design vs reported full, and the ratio between them.

    The DSDT feeds BFCC into *both* _BIF's DesignCapacity and its
    LastFullChargeCapacity, so the kernel shows energy_full ==
    energy_full_design and the true design (BADC) is invisible to the OS. Read
    it here instead: on this machine BADC = 6140 mAh = 70.9 Wh (the pack), BFCC
    = 5208 mAh = 60.2 Wh, i.e. the full the OS sees is 84.8 % of the pack."""
    badc, bfcc, badv = rd16(BADC), rd16(BFCC), rd16(BADV)
    if None in (badc, bfcc, badv):
        sys.exit("could not read the capacity registers")
    print("BADC design capacity = %5d mAh  (%.2f Wh)" % (badc, badc * badv / 1e6))
    print("BFCC reported full   = %5d mAh  (%.2f Wh)" % (bfcc, bfcc * badv / 1e6))
    print("BADV design voltage  = %5d mV" % badv)
    print("full / design        = %.1f %%" % (100.0 * bfcc / badc))


def watch(minutes):
    """Log capacity and status at a steady interval."""
    end = time.monotonic() + minutes * 60
    last = None
    while time.monotonic() < end:
        cap = bat("capacity")
        print("%s  MBDC=0x%02x  %-11s %s%%"
              % (time.strftime("%H:%M:%S"), ec_read(MBDC) or 0,
                 bat("status"), cap), flush=True)
        last = cap
        time.sleep(10)
    print("last capacity: %s%%" % last)


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: batterycctl.py status|capacity|set <0x0A|0x0C>|clear|watch [min]")
    cmd = sys.argv[1]
    if cmd == "status":
        status()
    elif cmd == "set":
        do_set(int(sys.argv[2], 0), require_yes=True)
    elif cmd == "clear":
        clear()
    elif cmd == "capacity":
        capacity()
    elif cmd == "watch":
        watch(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    else:
        sys.exit("unknown command: " + cmd)


if __name__ == "__main__":
    main()
