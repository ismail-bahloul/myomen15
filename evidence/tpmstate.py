#!/usr/bin/env python3
"""Dump the TPM-related EFI variables, before and after a BIOS change.

Companion to `setupdiff.py`, which only covers the setup *tables*. The TPM state
lives in its own set of variables, and one of them (`TpmStateFlag`) is present in
the NVRAM name table even though it is not part of the 322-byte `Setup` table —
so `setupdiff.py` alone would miss it.

Usage:
    tpmstate.py before
    # ... toggle the TPM in the BIOS, reboot ...
    tpmstate.py after
    tpmstate.py diff before after

Writes tpmstate-<tag>.json next to the current directory. Reads only.
"""

from __future__ import annotations

import json
import os
import sys

EFIVARS = "/sys/firmware/efi/efivars/"

# Every variable observed to carry TPM state on this machine, plus the two
# user-visible ones that should follow if the TPM is really switched on.
VARS = [
    "TpmStateFlag-0ee72c08-8185-427a-a58a-855b78b7ba0b",
    "TpmOldvar-135902e7-9709-4b41-8fd2-4069daf0546a",
    "PreviousTpmDevice-0ee72c08-8185-427a-a58a-855b78b7ba0b",
    "PostTpmDetect-0ee72c08-8185-427a-a58a-855b78b7ba0b",
    "InternalDisallowTpmFlag-70fff0ff-a543-45b9-8be3-1bdb90412080",
    "TPMPERBIOSFLAGS-7d3dceee-cbce-4ea7-8709-6e552f1edbde",
    "TpmServFlags-7d3dceee-cbce-4ea7-8709-6e552f1edbde",
    "DisplayTpmMsg-0ee72c08-8185-427a-a58a-855b78b7ba0b",
    "SecureBootSetup-7b59104a-c00d-4158-87ff-f04d6396a915",
]

# The setup table, so a TPM toggle can also be located in the 322-byte layout.
TABLES = {
    "Setup": "Setup-ec87d643-eba4-4bb5-a1e5-3f3e36b20da9",
    "AMD_PBS_SETUP": "AMD_PBS_SETUP-a339d746-f678-49b3-9fc7-54ce0f9df226",
    "AmdSetup": "AmdSetup-3a997502-647a-4c82-998e-52ef9486a247",
}


def read(name: str) -> bytes | None:
    try:
        with open(os.path.join(EFIVARS, name), "rb") as fh:
            return fh.read()[4:]
    except FileNotFoundError:
        return None
    except PermissionError:
        sys.exit(f"permission denied reading {name}\n(try: sudo)")


def visible_state() -> dict:
    """What the running OS can see of the TPM, independent of the variables."""
    state = {
        "dev_tpm_exists": os.path.exists("/dev/tpm0"),
        "dev_tpmrm0_exists": os.path.exists("/dev/tpmrm0"),
        "sys_class_tpm_exists": os.path.exists("/sys/class/tpm"),
    }
    try:
        state["dev_tpm_listing"] = sorted(x for x in os.listdir("/dev") if x.startswith("tpm"))
    except OSError:
        state["dev_tpm_listing"] = []
    return state


def snapshot(tag: str) -> None:
    out = {"vars": {}, "tables": {}, "visible": visible_state()}
    for name in VARS:
        data = read(name)
        out["vars"][name] = list(data) if data is not None else None
    for name, var in TABLES.items():
        data = read(var)
        out["tables"][name] = list(data[:322]) if data else None
    path = f"tpmstate-{tag}.json"
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {path}")
    print(f"  /dev/tpm0 present : {out['visible']['dev_tpm_exists']}")
    print(f"  /dev tpm nodes    : {out['visible']['dev_tpm_listing']}")


def pretty(data: list[int] | None) -> str:
    if data is None:
        return "(absent)"
    return " ".join(f"{b:02x}" for b in data[:16]) + (" …" if len(data) > 16 else "")


def diff(before: str, after: str) -> None:
    with open(f"tpmstate-{before}.json") as fh:
        a = json.load(fh)
    with open(f"tpmstate-{after}.json") as fh:
        b = json.load(fh)

    print("=== TPM variables ===")
    for name in VARS:
        x, y = a["vars"].get(name), b["vars"].get(name)
        if x == y:
            print(f"  {name[:52]:<52} unchanged  ({pretty(x)})")
        else:
            print(f"  {name[:52]:<52} CHANGED")
            print(f"      before: {pretty(x)}")
            print(f"      after : {pretty(y)}")

    print("\n=== setup tables ===")
    for name in TABLES:
        x, y = a["tables"].get(name), b["tables"].get(name)
        if x is None or y is None:
            print(f"  {name}: (absent on one side)")
            continue
        moved = [i for i in range(min(len(x), len(y))) if x[i] != y[i]]
        if not moved:
            print(f"  {name}: no change")
        else:
            print(f"  {name}: {len(moved)} offset(s) changed")
            for i in moved:
                print(f"      offset {i:3d}: 0x{x[i]:02x} -> 0x{y[i]:02x}")

    print("\n=== what the OS sees ===")
    for k in ("dev_tpm_exists", "dev_tpm_listing", "sys_class_tpm_exists"):
        x, y = a["visible"].get(k), b["visible"].get(k)
        mark = "  <-- CHANGED" if x != y else ""
        print(f"  {k}: {x} -> {y}{mark}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "snapshot" and len(sys.argv) > 2:
        snapshot(sys.argv[2])
    elif cmd == "diff" and len(sys.argv) > 3:
        diff(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
