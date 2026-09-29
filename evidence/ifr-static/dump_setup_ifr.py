#!/usr/bin/env python3
"""Parse the AMI `Setup` module's HII form + string packages and map every
question to its varstore offset and option name.

Discovered empirically (IFRExtractor-RS v1.6.1 lists these packages but
extracts nothing):
  - string blocks: 0x00=END, 0x14=UCS2 string (\0\0 terminated), increments id
  - the language string ("en-US") is ASCII, right after LanguageName (u16)
  - questions carry the standard IFR question header at +2:
        Prompt(u16) Help(u16) QuestionId(u16) VarStoreId(u16)
        VarOffset(u16) VarSize(u16) Flags(u8)
"""
from __future__ import annotations

import sys

FORMS_START = 0x1AB38
FORMS_LEN = 0x618D

OP_FORM_SET = 0x0E
OP_FORM = 0x01
OP_ONE_OF = 0x05
OP_CHECKBOX = 0x06
OP_NUMERIC = 0x07
OP_ONE_OF_OPTION = 0x09
OP_VARSTORE = 0x24
OP_VARSTORE_EFI = 0x26
Q = {0x05, 0x06, 0x07, 0x08, 0x0F, 0x0C, 0x0D, 0x16, 0x17, 0x18, 0x23}


def u16(b, o):
    return int.from_bytes(b[o:o + 2], "little")


def fmt_guid(b, o):
    d = b[o:o + 16]
    return (f"{d[3]:02x}{d[2]:02x}{d[1]:02x}{d[0]:02x}-{d[5]:02x}{d[4]:02x}-"
            f"{d[7]:02x}{d[6]:02x}-{d[8]:02x}{d[9]:02x}-"
            + "".join(f"{x:02x}" for x in d[10:16]))


def parse_strings(data):
    marker = b"\x01\x00en-US\x00"
    i = data.find(marker)
    if i < 0:
        sys.exit("language marker not found")
    o = i + len(marker)
    out = {}
    sid = 0
    while o < len(data):
        t = data[o]
        if t == 0x00:
            break
        if t == 0x14:                       # UCS2 string
            j = o + 1
            while data[j:j + 2] != b"\x00\x00":
                j += 2
            out[sid] = data[o + 1:j].decode("utf-16-le", "ignore")
            o = j + 2
            sid += 1
        elif t == 0x10:                     # SCSU (ascii-ish)
            j = data.index(b"\x00", o + 1)
            out[sid] = data[o + 1:j].decode("latin-1", "ignore")
            o = j + 1
            sid += 1
        elif t == 0x11:                     # SCSU + font
            j = data.index(b"\x00", o + 2)
            out[sid] = data[o + 2:j].decode("latin-1", "ignore")
            o = j + 1
            sid += 1
        elif t == 0x21:                     # UCS2 + font
            j = o + 2
            while data[j:j + 2] != b"\x00\x00":
                j += 2
            out[sid] = data[o + 2:j].decode("utf-16-le", "ignore")
            o = j + 2
            sid += 1
        elif t == 0x30:                     # duplicate
            dup = u16(data, o + 1)
            out[sid] = out.get(dup, "")
            o += 3
            sid += 1
        elif t == 0x31:                     # skip2
            sid += u16(data, o + 1); o += 3
        elif t == 0x32:                     # skip1
            sid += data[o + 1]; o += 2
        else:
            break
    return out


def main():
    path = sys.argv[1]
    data = open(path, "rb").read()
    strings = parse_strings(data)
    # StringId 0 means "no prompt"; the first string block is the language name.
    sid = lambda i: (strings.get(i, f"<str {i}>").strip() if i else "")

    varstores = {}
    forms = []          # (name) stack-ish
    questions = []
    o = FORMS_START
    end = FORMS_START + FORMS_LEN
    cur_formset = None
    cur_form = None
    while o + 2 <= end:
        op = data[o]
        ln = data[o + 1] & 0x7F
        if ln < 2 or o + ln > end:
            break
        if op == OP_FORM_SET:
            cur_formset = sid(u16(data, o + 18))
        elif op == OP_FORM:
            cur_form = sid(u16(data, o + 4))
        elif op == OP_VARSTORE:
            guid = fmt_guid(data, o + 2)
            vid = u16(data, o + 18)
            size = u16(data, o + 20)
            name = data[o + 22:o + ln].split(b"\x00")[0].decode("latin-1", "ignore")
            varstores[vid] = (guid, size, name)
        elif op == OP_VARSTORE_EFI:
            guid = fmt_guid(data, o + 2)
            vid = u16(data, o + 18)
            size = u16(data, o + 20)
            name = data[o + 22:o + ln].decode("utf-16-le", "ignore").rstrip("\x00")
            varstores[vid] = (guid, size, name)
        elif op in Q:
            questions.append(dict(
                op=op, prompt=sid(u16(data, o + 2)),
                qid=u16(data, o + 6), vid=u16(data, o + 8),
                off=u16(data, o + 10), size=u16(data, o + 12),
                formset=cur_formset, form=cur_form))
        o += ln

    print("== varstores ==")
    for vid, (g, s, n) in sorted(varstores.items()):
        print(f"  vid=0x{vid:04x} size={s:5d} name={n!r} guid={g}")
    print(f"\n== {len(questions)} questions ==")
    for q in questions:
        if q["vid"] == 0:
            continue
        g, s, n = varstores.get(q["vid"], ("?", 0, "?"))
        print(f"  off={q['off']:4d} size={q['size']:2d} op=0x{q['op']:02x} "
              f"var={n}[{q['vid']}] | {q['prompt']}")


if __name__ == "__main__":
    main()
