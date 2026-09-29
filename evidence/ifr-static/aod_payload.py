#!/usr/bin/env python3
"""Build the dmpstore .dat that CREATES AOD_SETUP, with a real AMD-Overclocking
payload instead of all zeros.

AOD_SETUP (5ED15DC0-EDEF-4161-9151-6014C4CC630C, 1020 B) is the AMD Overclocking
menu, read at POST by AodPei. aod-setup-probe created it all-zero (to open the
SMM gate); this fills the menu fields, to test whether AodPei applies them.

Payload (offset -> value), all within the IFR domains:
  142 = 1        Precision Boost Overdrive = Enabled
  143 = 2        PBO limits = Manual
  144,145 = 0xC8 0xAF   PPT limit = 45000 mW (u16 LE)
  368 = 2        Curve Optimizer = All Core
  370 = 10       Curve Optimizer magnitude = 10 (domain 0..30)
"""
from __future__ import annotations

import argparse
import binascii
import struct
import uuid

GUID = "5ED15DC0-EDEF-4161-9151-6014C4CC630C"
SIZE = 0x3FC  # 1020, pinned by aod-setup-probe/README.md
PATCHES = {142: 1, 143: 2, 144: 0xC8, 145: 0xAF, 368: 2, 370: 10}


def build_record(name, guid, attrs, data):
    nb = (name + "\0").encode("utf-16-le")
    body = struct.pack("<II", len(nb), len(data)) + nb + uuid.UUID(guid).bytes_le \
        + struct.pack("<I", attrs) + data
    return body + struct.pack("<I", binascii.crc32(body) & 0xFFFFFFFF)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--output", default="aod-create.dat")
    args = ap.parse_args()

    data = bytearray(SIZE)
    for off, val in PATCHES.items():
        data[off] = val
    rec = build_record("AOD_SETUP", GUID, 0x7, bytes(data))
    open(args.output, "wb").write(rec)
    print(f"wrote {args.output}: {len(rec)} bytes, data {SIZE} B")
    for off, val in sorted(PATCHES.items()):
        print(f"  off={off:4d} = 0x{val:02x}")


if __name__ == "__main__":
    main()
