#!/usr/bin/env python3
"""Scan the raw 16 MiB firmware image for the setup HII varstore GUIDs and for
menu strings in *both* encodings.

Why: efi-nvram.md §10 concluded "the IFR is in the encrypted volume" from an
ASCII-only string search. UEFI/IFR strings are UTF-16LE, so an ASCII search
always misses menu names. This tests the same thing in UTF-16 before that
conclusion is trusted.
"""
from __future__ import annotations

import re
import sys
import uuid

IMG = sys.argv[1] if len(sys.argv) > 1 else "evidence/ifr-static/088D1.bin"
data = open(IMG, "rb").read()
print(f"image {IMG}: {len(data)} bytes ({len(data)/1024/1024:.1f} MiB)\n")

# --- 1. varstore GUIDs, as raw little-endian bytes (how they sit in the flash) -
GUIDS = {
    "Setup (main)": "ec87d643-eba4-4bb5-a1e5-3f3e36b20da9",
    "SetupDefault": "0ee72c08-8185-427a-a58a-855b78b7ba0b",
    "AmdSetup (CBS)": "3a997502-647a-4c82-998e-52ef9486a247",
    "AMD_PBS_SETUP": "a339d746-f678-49b3-9fc7-54ce0f9df226",
    "HPSetupData": "206bc44a-c8a7-4000-896f-0da25fb37702",
    "StdDefaults": "4599d26f-1a11-49b8-b91f-858745cff824",
    "HiiDB": "1b838190-4625-4ead-abc9-cd5e6af18fe0",
}
# The HiiDatabase / ExportHiiDb DXE drivers seen in the parsed module report.
MODULE_GUIDS = {
    "HiiDatabase driver": "348c4d62-bfbd-4882-9ece-c80bb1c4783b",
    "ExportHiiDb driver": "271b424e-a4cc-4e0e-90a2-7ea4841f12f3",
}

print("== varstore GUIDs (little-endian, as stored) ==")
for name, g in {**GUIDS, **MODULE_GUIDS}.items():
    b = uuid.UUID(g).bytes_le
    offs = [m.start() for m in re.finditer(re.escape(b), data)]
    where = ", ".join(f"0x{o:08x}" for o in offs[:6]) or "NOT FOUND"
    more = f" (+{len(offs)-6} more)" if len(offs) > 6 else ""
    print(f"  {name:22s} {len(offs):3d}x  {where}{more}")

# --- 2. the same menu strings, ASCII vs UTF-16LE ------------------------------
STRINGS = [
    "Custom Core Pstates", "Curve Optimize", "Curve Optimizer", "PBO",
    "System Configuration", "STAPM", "Precision Boost", "OMEN",
    "Adaptive Battery Extender", "USB Camera", "TPM Embedded Security Device",
    "AMD PBS", "AMD CBS", "Sure Start", "Secure Boot", "Legacy USB",
]

print("\n== menu strings, ASCII vs UTF-16LE ==")
print(f"  {'string':32s} {'ASCII':>6s} {'UTF-16':>7s}")
for s in STRINGS:
    a = len(re.findall(re.escape(s.encode("ascii", "ignore")), data))
    u = len(re.findall(re.escape(s.encode("utf-16-le")), data))
    flag = "  <-- UTF-16 ONLY" if u and not a else ""
    print(f"  {s:32s} {a:6d} {u:7d}{flag}")

# --- 3. where the formset/package header would sit near the Setup GUID --------
setup_guid = uuid.UUID(GUIDS["Setup (main)"]).bytes_le
print("\n== context around each Setup-GUID hit ==")
for m in re.finditer(re.escape(setup_guid), data):
    o = m.start()
    ctx = data[max(0, o - 32):o + 32]
    print(f"  @0x{o:08x}: {ctx.hex(' ')}")
