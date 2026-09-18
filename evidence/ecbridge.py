#!/usr/bin/env python3
"""EC and I/O access through the firmware's own ACPI bridge.

The DSDT/SSDT set on this machine declares a *generic* byte-level bridge, which
the firmware itself provides and which nothing on Linux uses:

    \\_SB.PCI0.SBRG.EC0.M040 <offset>        read  any EC byte (0x00-0xFF)
    \\_SB.PCI0.SBRG.EC0.M041 <offset> <val>  write any EC byte
    \\_SB.PCI0.SBRG.EC0.M31A <port>          read  any I/O port byte
    \\_SB.PCI0.SBRG.EC0.M319 <port> <val>    write any I/O port byte

These are declared in SSDT12. `M040` was verified against `ec_probe` and agrees
exactly, so this is a fourth independent path to the EC (after `ec_sys`,
`hp-wmi`, and the `H2RA` memory region).

`M319` is the more interesting one: it can write **any** I/O port, including
`0xB2` — the AMD SMM command port that the firmware's own `\\AOD` interface uses
to reach the BIOS. Nothing on Linux exposes that.

DEFAULT IS READ-ONLY. The `write` subcommands require an explicit `--yes`.
"""

from __future__ import annotations

import re
import sys

EC = r"\_SB.PCI0.SBRG.EC0"


def call(method: str, *args: str) -> str:
    expr = method + (" " + " ".join(args) if args else "")
    try:
        with open("/proc/acpi/call", "w") as fh:
            fh.write(expr)
        with open("/proc/acpi/call") as fh:
            return fh.read().strip()
    except PermissionError:
        sys.exit("permission denied on /proc/acpi/call — run with sudo")
    except FileNotFoundError:
        sys.exit("/proc/acpi/call missing — is acpi_call loaded?")


def parse_int(out: str) -> int | None:
    m = re.search(r"0x([0-9a-fA-F]+)", out)
    if m:
        return int(m.group(1), 16)
    m = re.search(r"\b(\d+)\b", out)
    return int(m.group(1)) if m else None


def ec_read(offset: int) -> int | None:
    return parse_int(call(f"{EC}.M040", hex(offset)))


def io_read(port: int) -> int | None:
    return parse_int(call(f"{EC}.M31A", hex(port)))


def confirm(prompt: str) -> None:
    if "--yes" not in sys.argv:
        sys.exit(f"{prompt}\nThis is a WRITE. Re-run with --yes if that is intended.")


# Named offsets worth checking, from the DSDT field declarations.
EC_NAMES = {
    0x40: "TAPM  (thermal policy bit 4)",
    0x43: "GFXT  (graphics type)",
    0x57: "RTTP  (temp)",
    0x58: "RTMP  (temp)",
    0x62: "OMCC  (bit 0)",
    0x90: "NVDO  (dGPU power)",
    0x95: "HPCM  (dGPU mode)",
    0xA6: "MBDC  (battery charge control)",
    0xAD: "SARS  (thermal level)",
    0xAF: "GPUT  (GPU type)",
    0xBA: "OCPC  (OC profile current)",
    0xBB: "OCPS  (OC profile set)",
    0xE2: "KBT0  (keyboard type)",
    0xE6: "SFHK  (hotkey set)",
}

# I/O ports worth knowing about on this platform.
IO_NOTES = {
    0x62: "EC command",
    0x66: "EC data",
    0x72: "EC index (ECMC region)",
    0xB2: "AMD SMM / APMC — how \\AOD reaches the BIOS",
}


def do_ec_read(offset: int) -> None:
    v = ec_read(offset)
    note = f"   {EC_NAMES[offset]}" if offset in EC_NAMES else ""
    val = f"0x{v:02x}" if v is not None else "?"
    print(f"EC 0x{offset:02x} = {val}{note}")


def do_io_read(port: int) -> None:
    v = io_read(port)
    note = f"   {IO_NOTES[port]}" if port in IO_NOTES else ""
    val = f"0x{v:02x}" if v is not None else "?"
    print(f"IO 0x{port:02x} = {val}{note}")


def usage() -> None:
    print(__doc__)
    print("Commands:")
    print("  ec-read <offset>        read an EC register (hex ok)")
    print("  io-read <port>          read an I/O port")
    print("  named                   read the named EC offsets above")
    print("  ec-dump                 dump all 256 EC registers via M040")
    print("  ec-write <off> <val>    WRITE an EC register   (needs --yes)")
    print("  io-write <port> <val>   WRITE an I/O port      (needs --yes)")


def main() -> None:
    if len(sys.argv) < 2:
        usage()
        return
    cmd = sys.argv[1]

    def num(s: str) -> int:
        return int(s, 0)

    if cmd == "ec-read":
        do_ec_read(num(sys.argv[2]))
    elif cmd == "io-read":
        do_io_read(num(sys.argv[2]))
    elif cmd == "named":
        for off in sorted(EC_NAMES):
            do_ec_read(off)
    elif cmd == "ec-dump":
        for base in range(0, 256, 16):
            row = [ec_read(base + i) for i in range(16)]
            hexs = " ".join(f"{v:02x}" if v is not None else "??" for v in row)
            print(f"{base:02x} | {hexs}")
    elif cmd == "ec-write":
        confirm(f"about to write EC 0x{num(sys.argv[2]):02x} = 0x{num(sys.argv[3]):02x}")
        call(f"{EC}.M041", hex(num(sys.argv[2])), hex(num(sys.argv[3])))
        do_ec_read(num(sys.argv[2]))
    elif cmd == "io-write":
        confirm(f"about to write IO port 0x{num(sys.argv[2]):02x} = 0x{num(sys.argv[3]):02x}")
        call(f"{EC}.M319", hex(num(sys.argv[2])), hex(num(sys.argv[3])))
        do_io_read(num(sys.argv[2]))
    else:
        usage()


if __name__ == "__main__":
    main()
