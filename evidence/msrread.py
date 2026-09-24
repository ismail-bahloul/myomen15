#!/usr/bin/env python3
"""Raw MSR reads via /dev/cpu/N/msr, with no extra tooling.

The Linux `msr` driver maps the file offset directly to the MSR number, so a
pread(fd, 8, msr) reads exactly that MSR. The repo's earlier note read MSR
0x1a0 and got EIO, and attributed that to "the msr module's own allowlist".
0x1a0 is an Intel MSR -- on this AMD part it simply does not exist, so a #GP
(and therefore EIO) is what a *valid* MSR must *not* produce. This script
tests that reading: it reads known-good AMD MSRs (EFER, APIC_BASE, HWCR, the
SMM MSRs), which is what actually distinguishes "filtered" from "invalid".

Reads only. Nothing is written to any MSR.

  sudo python3 msrread.py
"""

import os
import struct

CPU = 0
PATH = "/dev/cpu/%d/msr" % CPU

# (msr, name, note)
MSRS = [
    (0x00000010, "TSC",            "live timestamp counter"),
    (0x0000001B, "APIC_BASE",      "known-good per chipsec-recon.md"),
    (0x0000008B, "PATCH_LEVEL",    "loaded microcode revision"),
    (0xC0000080, "EFER",           "known-good per chipsec-recon.md"),
    (0xC0010015, "HWCR",           "SmmLock bit0 / SmmBaseLock bit31 / SmmPgCfgLock bit33"),
    (0xC0010111, "SMM_BASE",       "SMM base address"),
    (0xC0010112, "SMM_ADDR",       "TSEG base"),
    (0xC0010113, "SMM_MASK",       "TSEG mask / AVALID / TVALID"),
    (0xC0010114, "VM_CR",          "SVM control"),
    (0xC0010010, "SYSCFG",         "MtrrFixDramModEn etc."),
    # discriminators: if reads were allowlisted (as chipsec-recon.md claimed),
    # a valid AMD MSR would fail too. Intel-only and nonsense MSRs must fail.
    (0x000001A0, "IA32_MISC_ENABLE", "Intel-only; #GP on AMD -- the one read that DID EIO"),
    (0xDEADBEEF, "invalid",        "nonsense MSR, must EIO if reads are unfiltered"),
]


def main():
    fd = os.open(PATH, os.O_RDONLY)
    try:
        for msr, name, note in MSRS:
            try:
                data = os.pread(fd, 8, msr)
                val = struct.unpack("<Q", data)[0]
                print("0x%08X %-12s = 0x%016X   %s" % (msr, name, val, note))
            except OSError as e:
                print("0x%08X %-12s = ERROR %s   %s" % (msr, name, e.strerror, note))
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
