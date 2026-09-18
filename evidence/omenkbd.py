#!/usr/bin/env python3
"""Read and (optionally) set the HP OMEN keyboard backlight / RGB.

The keyboard state lives in the `H2RA` memory region, which the EC exposes at
`0xfe700000`. The DSDT declares the fields:

    Offset (0xEE0)
        ,   5               // 5 reserved bits
        LCMC,   1           // bit 5 = commit. The EC applies on this.
    Offset (0xEE3)
        LRGB,   96          // 12 bytes: 4 zones x 3 (RGB)
    Offset (0xEF0)
        BRGB,   96          // 12 bytes: a second copy of the same
    LBRT,   8               // brightness

The firmware's own methods (`\\_SB.WMID.LM03`, `LM05`) write these, but they
read their data from a shared `WBUF` name rather than taking arguments, so
calling them through acpi_call means populating that buffer first. This script
writes the region directly instead, which is what those methods do anyway.

`LM03` writes LRGB, stalls, writes BRGB, stalls, then sets LCMC. That order is
reproduced here.

PROTOCOL: save before changing anything. `restore` puts the exact bytes back.
"""

from __future__ import annotations

import json
import mmap
import os
import sys

H2RA = 0xFE700000
LCMC_OFF = 0xEE0
LCMC_BIT = 0x20  # bit 5
LRGB_OFF = 0xEE3
BRGB_OFF = 0xEF0
LBRT_OFF = 0xEFC
N = 12

STATE = "kbd-state.json"


def open_region(write: bool = False):
    flags = os.O_RDWR if write else os.O_RDONLY
    fd = os.open("/dev/mem", flags | os.O_SYNC)
    access = mmap.ACCESS_WRITE if write else mmap.ACCESS_READ
    return mmap.mmap(fd, 0x1000, offset=H2RA, access=access)


def read_state() -> dict:
    m = open_region()
    return {
        "lcmc": m[LCMC_OFF],
        "lrgb": list(m[LRGB_OFF:LRGB_OFF + N]),
        "brgb": list(m[BRGB_OFF:BRGB_OFF + N]),
        "lbrt": m[LBRT_OFF],
    }


def show(state: dict) -> None:
    print(f"  LCMC (0xEE0 bit5) : 0x{state['lcmc']:02x}  "
          f"({'commit set' if state['lcmc'] & LCMC_BIT else 'clear'})")
    print(f"  LRGB (0xEE3)      : {' '.join(f'{b:02x}' for b in state['lrgb'])}")
    print(f"  BRGB (0xEF0)      : {' '.join(f'{b:02x}' for b in state['brgb'])}")
    print(f"  LBRT (0xEFC)      : 0x{state['lbrt']:02x}")


def cmd_read() -> None:
    print("keyboard state, read from H2RA 0xfe700000")
    show(read_state())


def cmd_save() -> None:
    state = read_state()
    with open(STATE, "w") as fh:
        json.dump(state, fh, indent=1)
    print(f"saved to {STATE}:")
    show(state)


def cmd_restore() -> None:
    if not os.path.exists(STATE):
        sys.exit(f"no {STATE} — run `save` first")
    with open(STATE) as fh:
        state = json.load(fh)
    write(state)
    print("restored:")
    show(read_state())


def write(state: dict) -> None:
    """Apply the state exactly as LM03 does: LRGB, BRGB, then commit."""
    m = open_region(write=True)
    for i, b in enumerate(state["lrgb"]):
        m[LRGB_OFF + i] = b
    for i, b in enumerate(state["brgb"]):
        m[BRGB_OFF + i] = b
    m[LBRT_OFF] = state["lbrt"]
    m[LCMC_OFF] = state["lcmc"] | LCMC_BIT
    try:
        m.flush()
    except OSError:
        # /dev/mem mappings do not support flush(); writes are already through.
        pass


def cmd_brightness(level: int) -> None:
    """Set only the brightness, keeping the RGB bytes as they are."""
    state = read_state()
    old = state["lbrt"]
    state["lbrt"] = level
    write(state)
    after = read_state()
    print(f"LBRT 0x{old:02x} -> 0x{after['lbrt']:02x}   (commit bit now "
          f"{'set' if after['lcmc'] & LCMC_BIT else 'clear'})")
    if after["lbrt"] == old and level != old:
        print("  the value did not change — the write was ignored")


def cmd_rgb(spec: str) -> None:
    """Set the 12 RGB bytes. `spec` is 12 hex bytes, eg `ff0000ff0000ff0000ff0000`."""
    cleaned = spec.replace(" ", "").replace(",", "")
    if len(cleaned) != N * 2:
        sys.exit(f"expected {N} hex bytes ({N*2} chars), got {len(cleaned)//2}")
    state = read_state()
    state["lrgb"] = [int(cleaned[i:i+2], 16) for i in range(0, N * 2, 2)]
    state["brgb"] = list(state["lrgb"])  # LM03 writes the same data to both
    old = read_state()
    write(state)
    after = read_state()
    print("before:", " ".join(f"{b:02x}" for b in old["lrgb"]))
    print("after :", " ".join(f"{b:02x}" for b in after["lrgb"]))
    if old["lrgb"] == after["lrgb"]:
        print("  unchanged — the write was ignored")


def usage() -> None:
    print(__doc__)
    print("Commands:")
    print("  read                       show the current keyboard state")
    print("  save                       save the state to kbd-state.json")
    print("  restore                    put the saved state back")
    print("  brightness <0-255>         set brightness only")
    print("  rgb <24 hex chars>         set the 12 RGB bytes")


def main() -> None:
    if len(sys.argv) < 2:
        usage()
        return
    cmd = sys.argv[1]
    if cmd == "read":
        cmd_read()
    elif cmd == "save":
        cmd_save()
    elif cmd == "restore":
        cmd_restore()
    elif cmd == "brightness":
        cmd_brightness(int(sys.argv[2], 0))
    elif cmd == "rgb":
        cmd_rgb(sys.argv[2])
    else:
        usage()


if __name__ == "__main__":
    main()
