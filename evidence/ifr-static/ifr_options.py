#!/usr/bin/env python3
"""Full option map: name -> offset, current value, factory default, choices.

Scope-aware IFR walk (needed to attach ONE_OF_OPTION children to their parent
question). Reads the live variables from efivarfs; where a default variable
exists (Setup -> SetupDefault) it is used as the reference.

Usage:
    ifr_options.py <dump-base> [varstore-name ...]
"""
from __future__ import annotations

import sys

from dump_setup_ifr import fmt_guid, parse_strings

I = int.from_bytes
OP_END = 0x10
OP_FORM = 0x01
OP_FORM_SET = 0x0E
OP_ONE_OF_OPTION = 0x09
Q = {0x05, 0x06, 0x07, 0x08, 0x0F, 0x0C, 0x0D, 0x16, 0x17, 0x18, 0x23}
VSIZE = {0: 1, 1: 2, 2: 4, 3: 8, 4: 1, 5: 3, 6: 3, 7: 0, 8: 0}
OPT_DEFAULT = 0x10

MODULES = {
    "Setup":          ("76 Setup/1 PE32 image section/body.bin", 0x1AB38, 0x618D),
    "CbsSetupDxeRN":  ("55 CbsSetupDxeRN/1 PE32 image section/body.bin", 0x13868, 0x4DCC),
    "AmdPbsSetupDxe": ("57 AmdPbsSetupDxe/2 PE32 image section/body.bin", 0xC638, 0x141B),
    "AodSetupDxe":    ("58 AodSetupDxe/2 PE32 image section/body.bin", 0xE4F8, 0x363D),
}

# live efivarfs name (GUID in varstore form -> filename GUID)
LIVE = {
    "Setup": "Setup-ec87d643-eba4-4bb5-a1e5-3f3e36b20da9",
    "AMD_PBS_SETUP": "AMD_PBS_SETUP-a339d746-f678-49b3-9fc7-54ce0f9df226",
    "AmdSetup": "AmdSetup-3a997502-647a-4c82-998e-52ef9486a247",
    "AOD_SETUP": "AOD_SETUP-5ed15dc0-edef-4161-9151-6014c4cc630c",
}
DEFAULT_VAR = {
    "Setup": "SetupDefault-0ee72c08-8185-427a-a58a-855b78b7ba0b",
}


def live(name):
    f = LIVE.get(name)
    if not f:
        return None
    try:
        return open("/sys/firmware/efi/efivars/" + f, "rb").read()[4:]
    except OSError:
        return None


def default(name):
    f = DEFAULT_VAR.get(name)
    if not f:
        return None
    try:
        return open("/sys/firmware/efi/efivars/" + f, "rb").read()[4:]
    except OSError:
        return None


def walk(data, start, length):
    """Yield (op, off, ln, scope, varstores, questions) with choices attached."""
    strings = parse_strings(data)
    sid = lambda i: (strings.get(i, "").strip() if i else "")
    o, end = start, start + length
    varstores, questions, stack = {}, [], []
    while o + 2 <= end:
        op = data[o]
        ln = data[o + 1] & 0x7F
        sc = data[o + 1] >> 7
        if ln < 2 or o + ln > end:
            break
        if op == OP_END:
            if stack:
                stack.pop()
        elif op == 0x24 or op == 0x26:
            vid = I(data[o + 18:o + 20], "little")
            name = (data[o + 22:o + ln].split(b"\x00")[0].decode("latin1", "ignore")
                    if op == 0x24 else
                    data[o + 22:o + ln].decode("utf-16-le", "ignore").rstrip("\x00"))
            varstores[vid] = (fmt_guid(data, o + 2), I(data[o + 20:o + 22], "little"), name)
        elif op in Q:
            q = dict(op=op, off=I(data[o + 10:o + 12], "little"),
                     vid=I(data[o + 8:o + 10], "little"),
                     qid=I(data[o + 6:o + 8], "little"),
                     prompt=sid(I(data[o + 2:o + 4], "little")), choices=[])
            questions.append(q)
            if sc:
                stack.append(("q", q))
        elif op == OP_ONE_OF_OPTION:
            parent = next((e[1] for e in reversed(stack) if e[0] == "q"), None)
            if parent is not None:
                topt = sid(I(data[o + 2:o + 4], "little"))
                flags = data[o + 4]
                typ = data[o + 5] & 0x0F
                vsz = VSIZE.get(typ, 0)
                val = (I(data[o + 6:o + 6 + vsz], "little") if vsz else None)
                parent["choices"].append((topt, val, bool(flags & OPT_DEFAULT)))
            if sc:
                stack.append(("o", parent))
        elif sc:
            stack.append(("x", None))
        o += ln
    return varstores, questions


def main():
    base = sys.argv[1]
    only = sys.argv[2:]
    for mod, (rel, off, ln) in MODULES.items():
        data = open(f"{base}/{rel}", "rb").read()
        varstores, questions = walk(data, off, ln)
        for vid, (guid, size, vname) in sorted(varstores.items()):
            if only and vname not in only:
                continue
            rows = [q for q in questions if q["vid"] == vid]
            if not rows:
                continue
            cur, dfl = live(vname), default(vname)
            print(f"\n===== {vname}  ({size} B, {guid})  module={mod}"
                  f"  live={'yes' if cur else 'NO'}  default={'yes' if dfl else 'no'} =====")
            for q in sorted(rows, key=lambda r: (r["off"], r["qid"])):
                if q["op"] not in (0x05, 0x06, 0x07):
                    continue
                sz = 1 if q["op"] == 0x06 else None
                c = d = None
                if cur is not None:
                    end = min(q["off"] + (sz or 1), len(cur))
                    c = " ".join(f"{b:02x}" for b in cur[q["off"]:end]) or "?"
                if dfl is not None:
                    end = min(q["off"] + (sz or 1), len(dfl))
                    d = " ".join(f"{b:02x}" for b in dfl[q["off"]:end]) or "?"
                nm = q["prompt"] or "(hidden)"
                print(f"  off={q['off']:4d} op=0x{q['op']:02x} cur={c} dfl={d}  {nm}")


if __name__ == "__main__":
    main()
