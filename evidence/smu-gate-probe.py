#!/usr/bin/env python3
"""Ask the SMU whether it *knows* the Curve Optimizer commands, or doesn't.

This exists because of a correction to `smuraw.py` and `smu-raw.md`: the
`mp1_smu_cmd` / `rsmu_cmd` sysfs nodes **mask every non-OK response as OK**.
Read `smu_send_command()` in `/usr/src/ryzen_smu-*/smu.c`:

    do
      read rsp -> tmp
    while (tmp == 0 && retries--);

    if (tmp != SMU_Return_OK && !retries) { ... return tmp; }
    return SMU_Return_OK;

When the SMU answers quickly with a non-zero, non-OK code (e.g. 0xFF), the loop
exits with `retries` still non-zero, the `!retries` guard is false, and the
function falls through to `return SMU_Return_OK`.  So the node reports `0x01`
for a `Failed`.  The earlier cross-checks in `smu-raw.md` never saw this because
every command they sent *was* OK.

The truth is in the **rsp register itself**, read through `smn`
(MP1 0x3B10564, RSMU 0x3B10A80).  This script always reads it that way and
prints both, so the masking is visible.

What it probes, and why it discriminates
----------------------------------------
The SMU distinguishes "I don't know this command" (`0xFE UnknownCmd`) from
"I know it and refuse it" (`0xFF Failed`).  Sending deliberate garbage IDs gives
the `UnknownCmd` baseline; sending the CO family then says which of the two the
gate is.  Confirmed on this machine (BIOS F.30, SMU 64.74.0):

    invalid 0xEE / 0x7E / 0x99 / 0xAB (MP1) -> 0xFE UnknownCmd
    set-coall 0x55 / set-coper 0x54 / set-cogfx 0x64 -> 0xFF Failed

i.e. the firmware *recognises* CO and refuses it deliberately.  That is a
firmware policy, not a transport or tooling problem -- no correct encoding,
mailbox or client will change it.

Safety
------
`controls` sends only query-class commands and deliberately-invalid IDs: reads,
nothing else.  `gate` sends the three CO *set* commands, but **with argument 0**,
which `EncodeCurveOptimiserOffset(0) == 0` means "offset zero" -- no change is
requested whatever the SMU decides.  It asks the acceptance question and nothing
more.  No state moved (verified: `ryzenadj --info` unchanged, `GetSmuVersion`
still answers after).

  sudo python3 evidence/smu-gate-probe.py controls   # read-only
  sudo python3 evidence/smu-gate-probe.py gate       # CO set, zero offset
  sudo python3 evidence/smu-gate-probe.py all        # both (default)
"""

import struct
import sys

DRV = "/sys/kernel/ryzen_smu_drv"
SMN = DRV + "/smn"

# Cezanne (codename 14), MP1 interface v12 -- from the driver's own tables.
RSP_ADDR = {"mp1_smu_cmd": 0x3B10564, "rsmu_cmd": 0x3B10A80}

RSP = {0x01: "OK", 0xFF: "Failed", 0xFE: "UnknownCmd",
       0xFD: "CmdRejectedPrereq", 0xFC: "CmdRejectedBusy",
       0xFB: "CommandTimeout", 0xFA: "InvalidArgument",
       0xF9: "Unsupported", 0xF8: "InsufficientSize",
       0xF7: "MappedError", 0xF6: "PCIFailed"}

ZERO = (0, 0, 0, 0, 0, 0)


def smn_read(addr):
    with open(SMN, "wb", buffering=0) as fh:
        fh.write(struct.pack("<I", addr))
    with open(SMN, "rb") as fh:
        return struct.unpack("<I", fh.read(4))[0]


def send(node, op, args=ZERO):
    """Send one mailbox command; return (sysfs_code, true_rsp, args_back)."""
    with open(DRV + "/smu_args", "wb", buffering=0) as fh:
        fh.write(struct.pack("<6I", *args))
    with open(DRV + "/" + node, "wb", buffering=0) as fh:
        fh.write(struct.pack("<I", op))
    with open(DRV + "/" + node, "rb") as fh:
        masked = struct.unpack("<I", fh.read(4))[0]
    true_rsp = smn_read(RSP_ADDR[node])
    with open(DRV + "/smu_args", "rb") as fh:
        back = struct.unpack("<6I", fh.read(24))
    return masked, true_rsp, back


def show(label, node, op, args=ZERO):
    masked, true_rsp, back = send(node, op, args)
    flag = "  <-- MASKED (sysfs said OK, SMU said %s)" % RSP.get(true_rsp, "?") \
        if masked == 0x01 and true_rsp != 0x01 else ""
    print("  %-38s %-11s op=0x%02X  sysfs=0x%02X  TRUE=0x%02X (%-15s)%s"
          % (label, node, op, masked, true_rsp, RSP.get(true_rsp, "?"), flag))
    print("       args_back = %s" % " ".join("0x%08X" % x for x in back))
    return true_rsp


def cmd_controls():
    print("== sanity (known-good queries) ==")
    show("GetSmuVersion", "mp1_smu_cmd", 0x02, (1, 0, 0, 0, 0, 0))
    show("GetPmTableVersion (MP1)", "mp1_smu_cmd", 0x0D)
    show("GetPmTableVersion (RSMU)", "rsmu_cmd", 0x06)

    print("\n== negative controls (deliberately invalid IDs -> UnknownCmd) ==")
    for op in (0xEE, 0x7E, 0x99, 0xAB):
        show("invalid MP1 0x%02X" % op, "mp1_smu_cmd", op)
    for op in (0xEE, 0x7E):
        show("invalid RSMU 0x%02X" % op, "rsmu_cmd", op)


def cmd_gate():
    print("== CO set family, ZERO offset (no-op arg): known vs unknown ==")
    show("set-coall 0x55 arg=0", "mp1_smu_cmd", 0x55)
    show("set-coper 0x54 arg=0", "mp1_smu_cmd", 0x54)
    show("set-cogfx 0x64 arg=0", "mp1_smu_cmd", 0x64)
    print("\n  Interpretation: %s vs the %s of the invalid IDs above."
          % (RSP.get(0xFF), RSP.get(0xFE)))


def cmd_all():
    cmd_controls()
    print()
    cmd_gate()
    print()
    print("== read-back: nothing should have moved ==")
    show("GetSmuVersion again", "mp1_smu_cmd", 0x02, (1, 0, 0, 0, 0, 0))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "controls":
        cmd_controls()
    elif cmd == "gate":
        cmd_gate()
    elif cmd == "all":
        cmd_all()
    else:
        sys.exit("usage: smu-gate-probe.py [controls|gate|all]")


if __name__ == "__main__":
    main()
