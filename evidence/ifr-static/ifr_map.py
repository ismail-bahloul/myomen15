#!/usr/bin/env python3
"""Static IFR map: module -> (varstore GUID, option offset -> name).

The forms package layout in this AMI/Aptos image is:
    [ u24 Length ][ u8 Type ] [ IFR opcode stream ]
(not the standard u32/u16 header), which is why IFRExtractor-RS lists the
packages but extracts nothing.
"""
from __future__ import annotations

import sys

from dump_setup_ifr import Q, fmt_guid, parse_strings


def u16(b, o):
    return int.from_bytes(b[o:o + 2], "little")


def parse(data, forms_start, forms_len):
    """Return (varstores, questions) for one forms package."""
    strings = parse_strings(data)
    # StringId 0 means "no prompt" (the first block is the language name).
    sid = lambda i: (strings.get(i, "").strip() if i else "")
    o, end = forms_start, forms_start + forms_len
    varstores, questions = {}, []
    while o + 2 <= end:
        op = data[o]
        ln = data[o + 1] & 0x7F
        if ln < 2 or o + ln > end:
            break
        if op == 0x24:
            vid = u16(data, o + 18)
            varstores[vid] = (fmt_guid(data, o + 2), u16(data, o + 20),
                              data[o + 22:o + ln].split(b"\x00")[0].decode("latin1", "ignore"))
        elif op == 0x26:
            vid = u16(data, o + 18)
            varstores[vid] = (fmt_guid(data, o + 2), u16(data, o + 20),
                              data[o + 22:o + ln].decode("utf-16-le", "ignore").rstrip("\x00"))
        elif op in Q:
            questions.append(dict(op=op, vid=u16(data, o + 8),
                                  off=u16(data, o + 10), qid=u16(data, o + 6),
                                  prompt=sid(u16(data, o + 2))))
        o += ln
    return varstores, questions


MODULES = {
    "Setup":          ("76 Setup/1 PE32 image section/body.bin", 0x1AB38, 0x618D),
    "CbsSetupDxeRN":  ("55 CbsSetupDxeRN/1 PE32 image section/body.bin", 0x13868, 0x4DCC),
    "AmdPbsSetupDxe": ("57 AmdPbsSetupDxe/2 PE32 image section/body.bin", 0xC638, 0x141B),
    "AodSetupDxe":    ("58 AodSetupDxe/2 PE32 image section/body.bin", 0xE4F8, 0x363D),
}


def main():
    base = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) > 2 else ""
    for name, (rel, off, ln) in MODULES.items():
        data = open(f"{base}/{prefix}{rel}", "rb").read()
        vs, qs = parse(data, off, ln)
        print(f"\n===== {name} ({len(vs)} varstores, {len(qs)} questions) =====")
        for vid, (g, s, n) in sorted(vs.items()):
            print(f"  vid=0x{vid:04x} size={s:5d} name={n!r} {g}")
        by = {}
        for q in qs:
            if q["vid"] in vs:
                by.setdefault(vs[q["vid"]][2], []).append(q)
        for vname, rows in by.items():
            print(f"\n  --- options in varstore {vname!r} ({len(rows)}) ---")
            for q in sorted(rows, key=lambda r: (r["off"], r["qid"])):
                print(f"    off={q['off']:4d} op=0x{q['op']:02x} qid={q['qid']:5d} | {q['prompt']}")


if __name__ == "__main__":
    main()
