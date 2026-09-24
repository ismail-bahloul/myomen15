#!/usr/bin/env python3
"""Read-only SMN sweep, via the PCI config window instead of ryzen_smu.

Two ways to read one SMN register were used on this machine, and this script
exists to prove they are the same thing:

  ryzen_smu:  write the address (u32) to /sys/kernel/ryzen_smu_drv/smn,
              read the value (u32) back from the same node.

  raw PCI:    on the root complex 00:00.0, offset 0xB8 is the SMN index and
              0xBC is the SMN data. Write the address to 0xB8, read 0xBC.
              This is the exact mechanism ryzen_smu itself uses internally
              (pci_write_config_dword(0xB8, addr); pci_read_config_dword(0xBC,
              &val)) -- the window simply stays readable afterwards, so no
              kernel module is needed at all to talk to SMN.

Both were cross-checked against each other and agree (`sed -i`-free, this file
only ever reads).

The sweep targets the SMU mailbox block the repo already documents
(0x3B10000-0x3B10FFF): MP1 cmd/rsp/args and RSMU cmd/rsp/args all live there.
Reads only. No SMN write is offered here, on purpose -- a write has no
"read a known register first" to de-risk it, unlike a decoded EC byte or a
documented mailbox command.

  sudo python3 smnscan.py pci 0x3B10564        # one register, PCI window
  sudo python3 smnscan.py smn 0x3B10564        # one register, ryzen_smu node
  sudo python3 smnscan.py diff                  # both paths over the mailbox page
  sudo python3 smnscan.py sweep 0x3B10000 0x3B10FFF   # non-zero registers in a range
"""

import struct
import subprocess
import sys

DRV = "/sys/kernel/ryzen_smu_drv"
SMN_NODE = DRV + "/smn"
BDF = "00:00.0"
IDX = "b8.l"
DAT = "bc.l"


def smn_node_read(addr):
    with open(SMN_NODE, "wb", buffering=0) as fh:
        fh.write(struct.pack("<I", addr))
    with open(SMN_NODE, "rb") as fh:
        return struct.unpack("<I", fh.read(4))[0]


def pci_smn_read(addr):
    subprocess.run(["setpci", "-s", BDF, "%s=%08X" % (IDX, addr)], check=True)
    out = subprocess.run(["setpci", "-s", BDF, DAT], check=True,
                         capture_output=True, text=True).stdout.strip()
    return int(out, 16)


def one(path, addr):
    val = smn_node_read(addr) if path == "smn" else pci_smn_read(addr)
    print("SMN 0x%08X = 0x%08X  (%s)" % (addr, val, path))


def diff():
    """Every register in the mailbox page, read both ways, compared."""
    bad = 0
    total = 0
    for addr in range(0x3B10000, 0x3B11000, 4):
        total += 1
        a = smn_node_read(addr)
        b = pci_smn_read(addr)
        if a != b:
            bad += 1
            print("MISMATCH 0x%08X  node=0x%08X  pci=0x%08X" % (addr, a, b))
    print("compared %d registers, %d mismatches" % (total, bad))
    print("the two paths are the same SMN, or they are not -- this says which")


def sweep(lo, hi):
    """Non-zero SMN registers in [lo, hi] (inclusive), values read via the PCI
    window (no module needed) so the sweep is self-contained."""
    step = 4
    for addr in range(lo, hi + 1, step):
        val = pci_smn_read(addr)
        if val not in (0x00000000, 0xFFFFFFFF):
            print("0x%08X = 0x%08X" % (addr, val))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip().splitlines()[-4].strip())
    cmd = sys.argv[1]
    if cmd == "pci":
        one("pci", int(sys.argv[2], 0))
    elif cmd == "smn":
        one("smn", int(sys.argv[2], 0))
    elif cmd == "diff":
        diff()
    elif cmd == "sweep":
        sweep(int(sys.argv[2], 0), int(sys.argv[3], 0))
    else:
        sys.exit("unknown command: %s" % cmd)


if __name__ == "__main__":
    main()
