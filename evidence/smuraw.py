#!/usr/bin/env python3
"""The raw SMU/SMN layer under ryzenadj.

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

Command IDs below (0x02, 0x06, 0x66) are not guessed: they are Cezanne's own
case in `/usr/src/ryzen_smu-*/smu.c` (smu_get_version, smu_get_pm_table_version,
smu_get_dram_base_address), the exact driver already running on this machine.
All three are query-class commands -- they read SMU/PM-table state, they do not
change it -- which is why they were sent first, and cross-checked before
anything else was tried.

`stapmtest` is the one command below that *does* change state: MP1 cmd 0x14,
Cezanne's `set_stapm_limit` in RyzenAdj's own `lib/api.c` (the same command
`ryzenadj --stapm-limit=N` already sends on this machine, routinely, watched
and re-applied by `evidence/power-profile-watch`). It is used here only to
prove the raw sysfs path can mutate real SMU state and not just query it -- the
script reads the current limit first, writes a distinguishable test value, and
writes the original value straight back itself, so it is safe to run whether or
not the watcher service happens to be active. `smn` writes, and any command
outside this known set, are still not offered: the SMU is a live
microcontroller, and the repo's position is that a newly-opened control path is
read, its queries cross-checked, and only a command whose exact effect is
already independently known is ever used to change something.

  sudo python3 smuraw.py mailbox            # the live mailbox registers
  sudo python3 smuraw.py smn 0x3B10564      # one SMN register
  sudo python3 smuraw.py version            # GetSmuVersion, MP1 cmd 0x02
  sudo python3 smuraw.py pmver              # GetPmTableVersion, RSMU cmd 0x06
  sudo python3 smuraw.py drambase           # GetDramBaseAddress, RSMU cmd 0x66
  sudo python3 smuraw.py stapmtest          # SetStapmLimit, MP1 cmd 0x14 -- writes, reads back, restores
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
# itself sends at init to read the SMU version. 0x06/0x66 are Cezanne's own
# case in ryzen_smu's smu.c (smu_get_pm_table_version, smu_get_dram_base_address).
SAFE_MP1 = {0x02: "GetSmuVersion"}
SAFE_RSMU = {0x06: "GetPmTableVersion", 0x66: "GetDramBaseAddress"}


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


def mp1_send(op, args6):
    with open(DRV + "/smu_args", "wb", buffering=0) as fh:
        fh.write(struct.pack("<6I", *args6))
    with open(DRV + "/mp1_smu_cmd", "wb", buffering=0) as fh:
        fh.write(struct.pack("<I", op))
    with open(DRV + "/mp1_smu_cmd", "rb") as fh:
        return struct.unpack("<I", fh.read(4))[0]


def stapm_mw():
    import subprocess
    out = subprocess.run(["ryzenadj", "--info"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "STAPM LIMIT" in line:
            return round(float(line.split("|")[2].strip()) * 1000)
    sys.exit("could not read STAPM LIMIT from `ryzenadj --info`")


def cmd_stapmtest():
    import time
    op = 0x14  # SetStapmLimit, Cezanne -- RyzenAdj lib/api.c set_stapm_limit()
    baseline = stapm_mw()
    test_val = baseline + 5000
    print("baseline STAPM limit : %d mW" % baseline)
    print("writing MP1 cmd 0x%02X (SetStapmLimit) arg0=%d ..." % (op, test_val))
    rsp = mp1_send(op, (test_val, 0, 0, 0, 0, 0))
    print("  rsp = 0x%02X (%s)" % (rsp, RSP.get(rsp, "?")))
    time.sleep(0.05)
    after = stapm_mw()
    print("  STAPM limit immediately after : %d mW" % after)
    print("  MATCH" if after == test_val else "  MISMATCH (or something else already reverted it)")
    print("restoring baseline MP1 cmd 0x%02X arg0=%d ..." % (op, baseline))
    rsp2 = mp1_send(op, (baseline, 0, 0, 0, 0, 0))
    print("  rsp = 0x%02X (%s)" % (rsp2, RSP.get(rsp2, "?")))
    time.sleep(0.05)
    restored = stapm_mw()
    print("  STAPM limit after restore : %d mW" % restored)
    print("  RESTORED" if restored == baseline else "  WARNING: did not restore cleanly, check `ryzenadj --info`")


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


def rsmu_send(op, args6):
    with open(DRV + "/smu_args", "wb", buffering=0) as fh:
        fh.write(struct.pack("<6I", *args6))
    with open(DRV + "/rsmu_cmd", "wb", buffering=0) as fh:
        fh.write(struct.pack("<I", op))
    with open(DRV + "/rsmu_cmd", "rb") as fh:
        rsp = struct.unpack("<I", fh.read(4))[0]
    with open(DRV + "/smu_args", "rb") as fh:
        back = struct.unpack("<6I", fh.read(24))
    return rsp, back


def cmd_pmver():
    op = 0x06
    rsp, back = rsmu_send(op, (0, 0, 0, 0, 0, 0))
    print("RSMU cmd 0x%02X (%s): rsp 0x%02X (%s)"
          % (op, SAFE_RSMU[op], rsp, RSP.get(rsp, "?")))
    print("  args back : " + " ".join("0x%08X" % x for x in back))
    with open(DRV + "/pm_table_version", "rb") as fh:
        sysfs_ver = struct.unpack("<I", fh.read(4))[0]
    print("  sysfs pm_table_version : 0x%08X" % sysfs_ver)
    print("  MATCH" if (rsp == 0x01 and back[0] == sysfs_ver) else "  MISMATCH")


def cmd_drambase():
    op = 0x66
    rsp, back = rsmu_send(op, (1, 1, 0, 0, 0, 0))
    print("RSMU cmd 0x%02X (%s): rsp 0x%02X (%s)"
          % (op, SAFE_RSMU[op], rsp, RSP.get(rsp, "?")))
    print("  args back : " + " ".join("0x%08X" % x for x in back))
    if rsp == 0x01:
        addr = back[0] | (back[1] << 32)
        print("  DRAM base address : 0x%016X" % addr)
        print("  cross-check against /proc/iomem for a Reserved region there")


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
    elif cmd == "pmver":
        cmd_pmver()
    elif cmd == "drambase":
        cmd_drambase()
    elif cmd == "stapmtest":
        cmd_stapmtest()
    else:
        sys.exit("unknown command: %s" % cmd)


if __name__ == "__main__":
    main()
