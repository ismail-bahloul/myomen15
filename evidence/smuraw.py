#!/usr/bin/env python3
"""The raw SMU/SMN layer under ryzenadj -- read-only.

`ryzen_smu` exposes four nodes that reach below any client (ryzenadj, UXTU):

  smn                  rb: one u32 = the last SMN read result
                       wb: 1 u32 (address)      -> read that SMN register
                           2 u32 (address,val)  -> write it   (NOT used here)
  smu_args             rw: 6 u32 command arguments
  mp1_smu_cmd          w: one u32 = send an MP1 command
                       r: one u32 = the last response code
  rsmu_cmd             same, for the RSMU mailbox

Protocol for a command: write the 6 u32 args to `smu_args`, write the command to
`mp1_smu_cmd` (or `rsmu_cmd`), then read the response from the same node (0x01 =
OK, 0xFF = failed, 0xFE = unknown command, ...). The reply lands in `smu_args`
and in the mailbox registers, which are themselves readable through SMN.

This machine is Cezanne, MP1 interface v12:

  MP1   cmd 0x3B10528   rsp 0x3B10564   args 0x3B10998
  RSMU  cmd 0x3B10A20   rsp 0x3B10A80   args 0x3B10A88

Only reads are performed here. `smn` writes and arbitrary MP1 commands are not
offered: the SMU is a live microcontroller, and the repo's position is that a
newly-opened control path is not used to write before it has been read.

  sudo python3 smuraw.py mailbox            # the live mailbox registers
  sudo python3 smuraw.py smn 0x3B10564      # one SMN register
  sudo python3 smuraw.py version            # GetSmuVersion via MP1 (cmd 0x02)
"""

import struct
import sys

DRV = "/sys/kernel/ryzen_smu_drv"
SMN = DRV + "/smn"

# Cezanne (codename 14), MP1 interface v12 -- see ryzen_smu smu.c.
MAILBOX = [
    ("MP1 cmd  ", 0x3B10528),
    ("MP1 rsp  ", 0x3B10564),
    ("MP1 args0", 0x3B10998),
    ("RSMU cmd ", 0x3B10A20),
    ("RSMU rsp ", 0x3B10A80),
    ("RSMU arg0", 0x3B10A88),
]

# Response codes from ryzen_smu smu.h.
RSP = {0x01: "OK", 0xFF: "Failed", 0xFE: "UnknownCmd",
       0xFD: "CmdRejectedPrereq", 0xFC: "CmdRejectedBusy",
       0xFB: "CommandTimeout", 0xFA: "InvalidArgument",
       0xF9: "Unsupported", 0xF8: "InsufficientSize",
       0xF7: "MappedError", 0xF6: "PCIFailed"}

# Only commands known to be pure queries are sent. 0x02 is the one the driver
# itself sends at init to read the SMU version.
SAFE_MP1 = {0x02: "GetSmuVersion"}


def smn_read(addr):
    with open(SMN, "wb", buffering=0) as fh:
        fh.write(struct.pack("<I", addr))
    with open(SMN, "rb") as fh:
        return struct.unpack("<I", fh.read(4))[0]


def cmd_mailbox():
    print("live SMU mailbox registers (Cezanne addresses)")
    for name, addr in MAILBOX:
        val = smn_read(addr)
        extra = "  (%s)" % RSP.get(val, "") if val in RSP else ""
        print("  %s 0x%08X = 0x%08X%s" % (name, addr, val, extra))


def cmd_smn(argv):
    if len(argv) != 1:
        sys.exit("usage: smuraw.py smn <hex-address>")
    addr = int(argv[0], 0)
    val = smn_read(addr)
    extra = "  (%s)" % RSP[val] if val in RSP else ""
    print("SMN 0x%08X = 0x%08X%s" % (addr, val, extra))


def cmd_version():
    op = 0x02
    args = struct.pack("<6I", 1, 0, 0, 0, 0, 0)
    with open(DRV + "/smu_args", "wb", buffering=0) as fh:
        fh.write(args)
    with open(DRV + "/mp1_smu_cmd", "wb", buffering=0) as fh:
        fh.write(struct.pack("<I", op))
    with open(DRV + "/mp1_smu_cmd", "rb") as fh:
        rsp = struct.unpack("<I", fh.read(4))[0]
    print("MP1 cmd 0x%02X (%s): rsp 0x%02X (%s)"
          % (op, SAFE_MP1[op], rsp, RSP.get(rsp, "?")))
    print("  reply in smu_args[0] : 0x%08X" % smn_read(0x3B10998))
    with open(DRV + "/smu_args", "rb") as fh:
        back = struct.unpack("<6I", fh.read(24))
    print("  reply in smu_args    : " + " ".join("0x%08X" % x for x in back))
    with open(DRV + "/version") as fh:
        print("  sysfs version        : %s" % fh.read().strip())


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip().splitlines()[-3].strip())
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "mailbox":
        cmd_mailbox()
    elif cmd == "smn":
        cmd_smn(rest)
    elif cmd == "version":
        cmd_version()
    else:
        sys.exit("unknown command: %s" % cmd)


if __name__ == "__main__":
    main()
