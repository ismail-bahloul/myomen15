#!/usr/bin/env python3
"""Inspect (and optionally set) the battery charge-control register on HP OMEN.

The mechanism, from the DSDT of an HP OMEN 15-en1xxx:

    EC0.MBDC   charge-control register        (read/write)
    EC0.MBST   modes supported, bits 0-1      (read-only)
    EC0.MBTS   battery present/usable         (read-only guard)
    EC0.ADPP   AC adapter present             (read-only guard)
    WMID.GBCC  firmware method: read the current mode
    WMID.SBCC  firmware method: write a mode (4 args)

`SBCC`'s argument space, decoded from the disassembly:

    Arg0 = 0      use the generic path; guarded by MBTS, and by ADPP for Arg1=1
    Arg0 = 0x63   force path; guarded only by ADPP. The one to use.
    Arg1 = 0      clear the cap            -> MBDC &= 0xE0
    Arg1 = 1      cap mode 1
    Arg1 = 2      cap mode 2

Both paths, after writing, spin until `MBDC & 0x10`, which is the EC's
completion flag. Return codes: 0x34 = no branch matched, 0x35 = battery/AC
guard failed, 0x36 = mode was already active.

DEFAULT IS READ-ONLY. `--set` is the only mode that writes.

Usage:
    batterycc.py status
    batterycc.py gbcc
    batterycc.py set 1        # WRITES: cap mode 1 (requires AC power)
    batterycc.py clear        # WRITES: clear the cap (MBDC &= 0xE0)

Before writing anything, note that on the machine this was developed on
`MBST = 0x00` — the battery advertises **no** charge-cap mode as available.
A write there may be accepted and ignored. Always read back.
"""

from __future__ import annotations

import re
import subprocess
import sys

EC = r"\_SB.PCI0.SBRG.EC0"
WMID = r"\_SB.WMID"

READ_REGS = ["MBTS", "MBST", "MBDC", "ADPP", "ECON"]

# MBDC bit meanings, from GBCC/SBCC
MBDC_COMPLETE = 0x10  # set by the EC when a write has landed
MBDC_MODE_MASK = 0x07  # low 3 bits select the mode
MBDC_CAP_BITS = 0x18  # GBCC only recognises a mode when both are set
MBDC_CLEAR_MASK = 0xE0  # MBDC &= 0xE0 clears the cap (both code paths)


def call(method: str) -> str:
    """Invoke an ACPI method through acpi_call and return its raw reply."""
    try:
        with open("/proc/acpi/call", "w") as fh:
            fh.write(method)
        with open("/proc/acpi/call") as fh:
            return fh.read().strip()
    except PermissionError:
        sys.exit("permission denied on /proc/acpi/call — run with sudo")
    except FileNotFoundError:
        sys.exit("/proc/acpi/call missing — is the acpi_call module loaded?")


def reg(name: str) -> int | None:
    out = call(f"{EC}.{name}")
    m = re.search(r"0x([0-9a-fA-F]+)", out)
    return int(m.group(1), 16) if m else None


def gbcc() -> tuple[str, int | None]:
    """The firmware's own read of the current mode. Returns (raw, mode)."""
    raw = call(f"{WMID}.GBCC")
    # reply looks like: [0x0, 0x4, {0x00, 0xff, 0x00, 0x00}]
    m = re.search(r"\{\s*0x([0-9a-fA-F]+)", raw)
    mode = int(m.group(1), 16) if m else None
    return raw, mode


def status() -> None:
    print("Register state (read-only)")
    print("-" * 46)
    values = {}
    for name in READ_REGS:
        values[name] = reg(name)
        print(f"  {name:6s} = 0x{values[name]:02x}" if values[name] is not None
              else f"  {name:6s} = ?")

    raw, mode = gbcc()
    print(f"\n  GBCC() -> {raw}")
    print(f"           mode = {mode}  ({'no charge control' if mode == 0 else 'cap active'})")

    mbst = values.get("MBST")
    if mbst is not None:
        print(f"\n  MBST = 0x{mbst:02x}: mode1 {'YES' if mbst & 1 else 'no'}, "
              f"mode2 {'YES' if mbst & 2 else 'no'}")
        if mbst & 0x03 == 0:
            print("  -> the battery advertises NO charge-cap mode as available.")
            print("     A write may be accepted and ignored. Read back after any write.")

    mbdc = values.get("MBDC")
    if mbdc is not None:
        print(f"\n  MBDC bits: complete={'YES' if mbdc & MBDC_COMPLETE else 'no'}, "
              f"cap_bits=0x{mbdc & MBDC_CAP_BITS:02x}, mode={mbdc & MBDC_MODE_MASK}")


def write_mode(arg0: int, arg1: int, label: str) -> None:
    """Invoke SBCC. This is the only function that writes."""
    if arg0 < 0:
        sys.exit("refusing: invalid Arg0")

    before = reg("MBDC")
    adpp = reg("ADPP")
    print(f"before: MBDC=0x{before:02x}  ADPP={adpp}")

    if arg0 == 0x63 and adpp != 1:
        sys.exit("refusing: the 0x63 path requires AC power (ADPP == 1), and ADPP is not 1.")

    print(f"calling SBCC(0x{arg0:02x}, {arg1}, 0, 0)  [{label}]")
    out = call(f"{WMID}.SBCC 0x{arg0:02x} {arg1} 0 0")
    print(f"  SBCC reply: {out}")

    after = reg("MBDC")
    _, mode = gbcc()
    print(f"after : MBDC=0x{after:02x}  GBCC mode={mode}")

    if after == before:
        print("  MBDC unchanged — the write did not land.")
    elif mode and mode != 0:
        print("  Mode is now active.")
    else:
        print("  MBDC changed but GBCC still reports mode 0 — check manually.")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "status":
        status()
    elif cmd == "gbcc":
        raw, mode = gbcc()
        print(f"{raw}   mode={mode}")
    elif cmd == "set":
        if len(sys.argv) < 3 or sys.argv[2] not in ("1", "2"):
            sys.exit("usage: batterycc.py set <1|2>")
        want = int(sys.argv[2])
        write_mode(0x63, want, f"cap mode {want}")
    elif cmd == "clear":
        write_mode(0x63, 0, "clear the cap")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
