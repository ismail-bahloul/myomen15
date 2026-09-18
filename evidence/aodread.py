#!/usr/bin/env python3
"""Read the AMD overclocking state through the firmware's \\AOD interface.

SSDT2 declares a PNP0C14 device `\\AOD` whose `AM05` method fills a 0xC8-byte
`OBUF` with the *current* settings and returns it. Those fields include the
power limits and the curve-optimizer values, which is the read-back this repo
could not get through the SMU mailbox.

**It only half works.** `acpi_call` copies the ACPI result into a fixed 256-byte
kernel buffer, so a reply is truncated to about 42 buffer values — offsets
0x00-0x29. Every field below 0x2A is reachable; `BCOS` (0x57) and `BPCS`
(0xA1), the curve-optimizer fields, are **not**. See `../acpi-bridge.md` for why
enlarging that buffer is not a thing to do casually: it was tried, and it
panicked the machine.

Read-only. The buffer sent selects a *read* handler only.
"""

from __future__ import annotations

import re
import sys

AOD = r"\AOD"

# The *input* buffer only needs the 4-byte command id. The reply is the full
# 0xB4-byte OBUF regardless. Keeping the input short matters: /proc/acpi/call
# rejects an expression beyond roughly 256 characters.
BUF_LEN = 4

# (offset, width, name, unit hint)
FIELDS = [
    (0x46, 4, "BOCV", "OC mode value"),
    (0x4A, 4, "BOCF", "OC mode flags"),
    (0x57, 1, "BCOS", "curve optimizer scalar"),
    (0x6C, 4, "BPPL", "PPT limit"),
    (0x70, 4, "BTDL", "TDC limit"),
    (0x74, 4, "BEDL", "EDC limit"),
    (0x7A, 2, "BFCK", "FCLK"),
    (0x82, 2, "BVDG", "IOD VDDG"),
    (0x8C, 4, "BPPT", "PPT set"),
    (0x90, 4, "BTDC", "TDC set"),
    (0x94, 4, "BEDM", "EDC set"),
    (0x98, 4, "BSCA", "scalar set"),
    (0x9C, 1, "BDMI", "DRAM map inversion"),
    (0x9F, 1, "BNPS", "NPSS"),
    (0xA1, 4, "BPCS", "curve optimizer (COPS)"),
    (0xA5, 2, "BIOD", "IOD VDDG (IVDG)"),
    (0xAB, 4, "BSTD", "SoC TDC (OTDC)"),
    (0xAF, 4, "BSED", "SoC EDC (OEDC)"),
    (0xB3, 1, "BSLC", "DRAM latency enh (DMLC)"),
]


def call_buffer(buf: bytes) -> bytes:
    """Invoke \\AOD.AM05 with a buffer whose first dword is a lookup id.

    The id only selects a *read* handler; 0x00010001 is `R101`.
    """
    payload = ",".join(f"0x{b:02x}" for b in buf)
    expr = f"{AOD}.AM05 {{{payload}}}"
    try:
        with open("/proc/acpi/call", "w") as fh:
            fh.write(expr)
        out = open("/proc/acpi/call").read().strip()
    except PermissionError:
        sys.exit("permission denied on /proc/acpi/call — run with sudo")
    except FileNotFoundError:
        sys.exit("/proc/acpi/call missing — is acpi_call loaded?")

    if out.startswith("Error"):
        sys.exit(f"acpi_call returned: {out}")
    hexes = re.findall(r"0x([0-9a-fA-F]{2})", out)
    if not hexes:
        sys.exit(f"could not parse the reply: {out[:120]}")
    return bytes(int(h, 16) for h in hexes)


def le(data: bytes, off: int, width: int) -> int:
    return int.from_bytes(data[off:off + width], "little")


def main() -> None:
    buf = bytearray(BUF_LEN)
    buf[0:4] = (0x00010001).to_bytes(4, "little")  # selects R101 (a read)
    reply = call_buffer(bytes(buf))

    print(f"\\AOD.AM05 returned {len(reply)} bytes\n")
    print("current overclocking state, as the firmware reports it")
    print("-" * 52)
    for off, width, name, hint in FIELDS:
        if off + width > len(reply):
            continue
        val = le(reply, off, width)
        print(f"  {name} @0x{off:02x}  {val:>10}  {hint}")

    print()
    print("raw 0x40-0xB4:")
    for base in range(0x40, min(0xB4, len(reply)), 16):
        chunk = reply[base:base + 16]
        print(f"  {base:02x} | {' '.join(f'{b:02x}' for b in chunk)}")


if __name__ == "__main__":
    main()
