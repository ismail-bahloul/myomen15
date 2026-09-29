#!/usr/bin/env python3
"""Apply-side of the static IFR work: turn a named option into the two files a
pre-boot `dmpstore` needs — the change and a fresh revert — **without writing
anything**. It only reads efivarfs and writes files into this directory.

Never touches the firmware. Loading a `.dat` is a separate, deliberate step from
the UEFI Shell (see `startup.nsh`).

    bridge.py options <VARSTORE>            list named options + offsets
    bridge.py plan <VARSTORE> NAME=VALUE... dry-run: resolve names, show the diff
    bridge.py build <VARSTORE> NAME=VALUE...  write <outdir>/poke.dat + revert.dat

VARSTORE is one of: Setup, AMD_PBS_SETUP, AmdSetup.
`NAME` is matched case-insensitively as a substring of the option prompt; if it
matches several, all are shown and none is applied unless exactly one matches.
"""
from __future__ import annotations

import os
import re
import struct
import sys
import zlib

from dump_setup_ifr import fmt_guid, parse_strings
from ifr_options import MODULES, Q, walk

EFIVARFS = "/sys/firmware/efi/efivars"

# varstore name -> (dmpstore variable name, GUID string, data size, efivar file)
VARS = {
    "Setup":         ("Setup", "ec87d643-eba4-4bb5-a1e5-3f3e36b20da9", 322,
                      "Setup-ec87d643-eba4-4bb5-a1e5-3f3e36b20da9"),
    "AMD_PBS_SETUP": ("AMD_PBS_SETUP", "a339d746-f678-49b3-9fc7-54ce0f9df226", 136,
                      "AMD_PBS_SETUP-a339d746-f678-49b3-9fc7-54ce0f9df226"),
    "AmdSetup":      ("AmdSetup", "3a997502-647a-4c82-998e-52ef9486a247", 1448,
                      "AmdSetup-3a997502-647a-4c82-998e-52ef9486a247"),
}


def guid_bytes(g):
    h = g.replace("-", "")
    return bytes.fromhex(h[6:8] + h[4:6] + h[2:4] + h[0:2] + h[10:12] + h[8:10]
                        + h[14:16] + h[12:14] + h[16:])


def build_dat(name, guid, data):
    nb = (name + "\x00").encode("utf-16-le")
    header = (struct.pack("<I", len(nb)) + struct.pack("<I", len(data)) + nb
              + guid_bytes(guid) + struct.pack("<I", 7))          # NV|BS|RT
    body = header + data
    return body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)


def read_var(varname):
    with open(os.path.join(EFIVARFS, varname), "rb") as fh:
        return fh.read()[4:]


def load_options(base, varstore):
    for mod, (rel, off, ln) in MODULES.items():
        data = open(f"{base}/{rel}", "rb").read()
        vs, qs = walk(data, off, ln)
        for vid, (guid, size, name) in vs.items():
            if name == varstore:
                return [q for q in qs if q["vid"] == vid and q["op"] in
                        (0x05, 0x06, 0x07)]
    sys.exit(f"varstore {varstore} not found")


def cmd_options(opts):
    for q in sorted(opts, key=lambda r: (r["off"], r["qid"])):
        print(f"  off={q['off']:4d} op=0x{q['op']:02x} qid={q['qid']:5d} | "
              f"{q['prompt'] or '(hidden)'}")


def resolve(opts, spec):
    if "=" not in spec:
        sys.exit(f"expected NAME=VALUE, got {spec!r}")
    name, val = spec.rsplit("=", 1)
    m = re.compile(re.escape(name), re.I)
    hits = [q for q in opts if m.search(q["prompt"])]
    if len(hits) != 1:
        print(f"  ! {spec!r} matches {len(hits)} options"
              + ("" if not hits else ": offset(s) "
                 + ", ".join(str(h["off"]) for h in hits)) + " — skipped")
        return None
    return hits[0], int(val, 0)


def cmd_plan(varname, opts, specs):
    _, guid, size, efivarname = VARS[varname]
    cur = read_var(efivarname)
    print(f"{varname}: {len(cur)} B live (declared {size}), "
          f"{len(specs)} requested change(s)")
    plan = []
    for s in specs:
        r = resolve(opts, s)
        if r:
            q, v = r
            plan.append((q, v))
    for q, v in plan:
        old = cur[q["off"]]
        flag = "" if old != v else "   (already this value)"
        print(f"  off={q['off']:4d}  {old:#04x} -> {v:#04x}{flag}  "
              f"{q['prompt']}")
    return plan


def cmd_build(varname, opts, specs, outdir):
    name, guid, size, efivarname = VARS[varname]
    cur = bytearray(read_var(efivarname))
    plan = cmd_plan(varname, opts, specs)
    os.makedirs(outdir, exist_ok=True)
    revert = build_dat(name, guid, bytes(cur))
    open(f"{outdir}/revert-{varname}.dat", "wb").write(revert)
    for q, v in plan:
        cur[q["off"]] = v
    poke = build_dat(name, guid, bytes(cur))
    open(f"{outdir}/poke-{varname}.dat", "wb").write(poke)
    print(f"\nwrote {outdir}/poke-{varname}.dat and revert-{varname}.dat")
    print("Nothing was applied. See startup.nsh to load them from the UEFI Shell.")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__.strip().splitlines()[-1])
    base = os.path.join(os.path.dirname(__file__), "088D1.bin.dump/1 4F1C52D3-"
                        "D824-4D2A-A2F0-EC40C23C5916/0 9E21FD93-9C72-4C15-8C4B-E77F1DB2D792/"
                        "0 EE4E5898-3914-4259-9D6E-DC7BD79403CF/1 Volume image section/"
                        "0 5C60F367-A505-419A-859E-2A4FF6CA6FE5")
    cmd, varstore = sys.argv[1], sys.argv[2]
    opts = load_options(base, varstore)
    if cmd == "options":
        cmd_options(opts)
    elif cmd == "plan":
        cmd_plan(varstore, opts, sys.argv[3:])
    elif cmd == "build":
        outdir = os.environ.get("BRIDGE_OUT", ".")
        cmd_build(varstore, opts, sys.argv[3:], outdir)
    else:
        sys.exit(__doc__.strip().splitlines()[-1])


if __name__ == "__main__":
    main()
