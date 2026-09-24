#!/usr/bin/env python3
"""Read-only physical memory dump via /dev/mem.

Used for the regions the DSDT/firmware declare that are not behind a driver:
the H2RA fan-tacho window at 0xfe700000, and the FCH SPI controller MMIO at
0xFEC10000 (SPIBASEADDR's own base). Reads only; the file is opened O_RDONLY.

  sudo python3 memdump.py 0xFEC10000 0x100
  sudo python3 memdump.py 0xfe700000 0x40
"""

import mmap
import os
import sys


def dump(base, size):
    page = base & ~0xFFF
    off = base - page
    fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    try:
        m = mmap.mmap(fd, off + size, offset=page, access=mmap.ACCESS_READ)
        data = m[off:off + size]
        m.close()
    finally:
        os.close(fd)
    for i in range(0, size, 16):
        chunk = data[i:i + 16]
        hexs = " ".join("%02x" % b for b in chunk)
        txt = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print("%08x  %-47s  %s" % (base + i, hexs, txt))


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: memdump.py <base> <size>")
    dump(int(sys.argv[1], 0), int(sys.argv[2], 0))


if __name__ == "__main__":
    main()
