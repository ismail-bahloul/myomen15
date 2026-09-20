#!/usr/bin/env python3
"""Snapshot / diff the BIOS setup tables exposed as EFI variables.

The point: `Setup` holds the *current* BIOS answers, `SetupDefault` (whose bytes
also appear verbatim inside the firmware's `StdDefaults` variable) holds the
factory ones. Same 322-byte table, same layout, so a byte diff lists exactly
which options are off-default — no reboot, no setup visit.

Usage:
    setupdiff.py snapshot before
    # ... change ONE option in the BIOS, reboot ...
    setupdiff.py snapshot after
    setupdiff.py diff before after

A plain before/after diff cannot name an offset by itself: saving the setup
moves bytes on its own, whatever was changed (see efi-nvram.md §7). The form
that means something reverts the option and snapshots a third time:

    # ... revert the same option, reboot ...
    setupdiff.py snapshot revert
    setupdiff.py twoleg before after revert

`twoleg` keeps only the offsets that moved out and came back; everything else
that moved is save-noise from the two setup visits, not the option.

Two independent sources back the reference table, which is why the diff is
trustworthy: `StdDefaults` (1088 B, firmware-provided) embeds the same table at
offset 17, byte-identical to `SetupDefault`. `setupdiff.py verify` re-checks
that, so a firmware update that invalidates the assumption is caught rather
than silently producing a wrong answer.

Reads only. Nothing here writes to the machine.
"""

from __future__ import annotations

import json
import os
import sys

EFIVARS = "/sys/firmware/efi/efivars/"

VARS = {
    "Setup": "Setup-ec87d643-eba4-4bb5-a1e5-3f3e36b20da9",
    "SetupDefault": "SetupDefault-0ee72c08-8185-427a-a58a-855b78b7ba0b",
    "StdDefaults": "StdDefaults-4599d26f-1a11-49b8-b91f-858745cff824",
    "AMD_PBS_SETUP": "AMD_PBS_SETUP-a339d746-f678-49b3-9fc7-54ce0f9df226",
    "AmdSetup": "AmdSetup-3a997502-647a-4c82-998e-52ef9486a247",
    "HPSetupData": "HPSetupData-206bc44a-c8a7-4000-896f-0da25fb37702",
}

# The 4-byte header efivarfs prepends to every variable's data.
HEADER = 4
# Where the embedded Setup table starts inside StdDefaults.
STD_DEFAULTS_OFFSET = 17
TABLE_LEN = 322


def read_var(name: str) -> bytes:
    """Read a variable, stripping efivarfs' 4-byte per-variable header."""
    path = os.path.join(EFIVARS, VARS[name])
    try:
        with open(path, "rb") as fh:
            return fh.read()[HEADER:]
    except FileNotFoundError:
        sys.exit(f"missing variable: {path}\n(not an EFI boot, or the firmware changed)")
    except PermissionError:
        sys.exit(f"permission denied reading {path}\n(try: sudo)")


def verify() -> bool:
    """Confirm SetupDefault really is the firmware's reference table."""
    std = read_var("StdDefaults")
    table = std[STD_DEFAULTS_OFFSET:STD_DEFAULTS_OFFSET + TABLE_LEN]
    default = read_var("SetupDefault")
    ok = table == default
    print(f"StdDefaults[+{STD_DEFAULTS_OFFSET}:+{TABLE_LEN}] == SetupDefault : {ok}")
    if not ok:
        n = sum(1 for i in range(min(len(table), len(default))) if table[i] != default[i])
        print(f"  {n} bytes differ — the reference table assumption is BROKEN.")
        print("  Do not trust `diff` until this is understood.")
    return ok


def snapshot(tag: str) -> None:
    """Write every table's raw bytes to setupdiff-<tag>.json."""
    out = {"verify": verify(), "tables": {}}
    for name in VARS:
        data = read_var(name)
        out["tables"][name] = list(data[:TABLE_LEN]) if name != "StdDefaults" else list(data)
    path = f"setupdiff-{tag}.json"
    with open(path, "w") as fh:
        json.dump(out, fh)
    print(f"wrote {path}")


def diff(before: str, after: str) -> None:
    """Report which offsets changed, against the defaults as a third column."""
    with open(f"setupdiff-{before}.json") as fh:
        a = json.load(fh)
    with open(f"setupdiff-{after}.json") as fh:
        b = json.load(fh)

    default = read_var("SetupDefault")

    for name in VARS:
        old, new = a["tables"][name], b["tables"][name]
        n = min(len(old), len(new))
        changed = [i for i in range(n) if old[i] != new[i]]

        print(f"\n=== {name} ===")
        if not changed:
            print("  no change")
            continue
        print(f"  {len(changed)} offset(s) changed:")
        for i in changed:
            d = default[i] if name != "StdDefaults" and i < len(default) else None
            dflt = f"  default=0x{d:02x}" if d is not None else ""
            tag = ""
            if d is not None:
                tag = "  -> back to DEFAULT" if new[i] == d else "  -> still off-default"
            print(f"    offset {i:3d}: 0x{old[i]:02x} -> 0x{new[i]:02x}{dflt}{tag}")


def twoleg(before: str, after: str, revert: str) -> None:
    """The method from efi-nvram.md §7: change, snapshot, revert, snapshot --
    keep only offsets that moved out AND came back. A plain before/after diff
    cannot name an offset, because saving the setup moves bytes on its own,
    whatever was changed; this is the filter that removes that noise."""
    with open(f"setupdiff-{before}.json") as fh:
        a = json.load(fh)
    with open(f"setupdiff-{after}.json") as fh:
        b = json.load(fh)
    with open(f"setupdiff-{revert}.json") as fh:
        c = json.load(fh)

    default = read_var("SetupDefault")

    for name in VARS:
        old, mid, back = a["tables"][name], b["tables"][name], c["tables"][name]
        n = min(len(old), len(mid), len(back))
        moved_out = [i for i in range(n) if old[i] != mid[i]]
        signal = [i for i in moved_out if back[i] == old[i]]
        noise = [i for i in moved_out if back[i] != old[i]]

        print(f"\n=== {name} ===")
        if not moved_out:
            print("  no change")
            continue
        if signal:
            print(f"  {len(signal)} offset(s) moved out AND back (real signal):")
            for i in signal:
                d = default[i] if name != "StdDefaults" and i < len(default) else None
                dflt = f"  default=0x{d:02x}" if d is not None else ""
                print(f"    offset {i:3d}: {before}=0x{old[i]:02x} -> {after}=0x{mid[i]:02x} -> {revert}=0x{back[i]:02x}{dflt}")
        if noise:
            print(f"  {len(noise)} offset(s) moved out but did NOT return (save-noise, discard): {noise}")


def offdefault() -> None:
    """List every option currently off-default, using both references."""
    setup = read_var("Setup")
    default = read_var("SetupDefault")
    n = sum(1 for i in range(TABLE_LEN) if setup[i] != default[i])
    print(f"{n} offset(s) off-default on this machine:\n")
    for i in range(TABLE_LEN):
        if setup[i] != default[i]:
            print(f"  offset {i:3d}: default=0x{default[i]:02x} -> current=0x{setup[i]:02x}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "verify":
        verify()
    elif cmd == "offdefault":
        offdefault()
    elif cmd == "snapshot" and len(sys.argv) > 2:
        snapshot(sys.argv[2])
    elif cmd == "diff" and len(sys.argv) > 3:
        diff(sys.argv[2], sys.argv[3])
    elif cmd == "twoleg" and len(sys.argv) > 4:
        twoleg(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
