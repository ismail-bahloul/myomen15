#!/usr/bin/env python3
"""Where does the firmware define / reference the HP setup variables?"""
import os
import uuid

ROOT = "088D1.bin.dump"
GUID = uuid.UUID("206bc44a-c8a7-4000-896f-0da25fb37702").bytes_le
NAMES = [b"HPSetupData", b"NewHPSetupData", b"HPAmiTse",
         b"HideFanAlwaysOn", b"OEMDeviceStatus", b"HpBootOrder"]

hits = {}
for dp, _, fs in os.walk(ROOT):
    for f in fs:
        p = os.path.join(dp, f)
        try:
            d = open(p, "rb").read()
        except OSError:
            continue
        if GUID in d:
            hits.setdefault("GUID 206bc44a", []).append(p)
        for n in NAMES:
            if n in d or n.decode().encode("utf-16-le") in d:
                hits.setdefault(n.decode(), []).append(p)

for k, v in hits.items():
    print(f"\n== {k}: {len(v)} file(s)")
    for p in v[:6]:
        print("   ", p.replace(ROOT + "/", ""))
