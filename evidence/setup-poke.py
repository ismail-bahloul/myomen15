#!/usr/bin/env python3
"""Build a `dmpstore`-loadable `Setup` file, optionally with offsets patched.

Why this is safe to hand to `dmpstore`: the format is fully understood from the
files `evidence/uefi-shell-probe/` already round-tripped on this machine —

    [ 40-byte header ][ 322-byte Setup table ][ CRC32 of the two ]

with the header = u32 name-length (12) | u32 data-size (322) | "Setup" in
UTF-16LE | the variable GUID | u32 attributes (7). The trailing CRC is a plain
zlib CRC32 over everything before it — verified byte-exact on all four probe
`.dat` files (`match_body=True`). The 322-byte table itself carries no internal
checksum (checked), so patching a byte in it needs only the trailing CRC fixed.

Nothing here touches the machine. It reads the *live* `Setup` variable with
`GetVariable` semantics (i.e. efivarfs, minus its 4-byte attribute header) and
writes a file. Loading that file into the firmware is a separate, manual step
from the UEFI Shell.

Usage:
    sudo python3 setup-poke.py dump <out.dat>              # fresh, unmodified
    sudo python3 setup-poke.py poke <out.dat> 21=0 22=0    # patch offsets
    sudo python3 setup-poke.py info <file.dat>             # decode a .dat
    python3 setup-poke.py repatch <src.dat> <out.dat> 21=0 # patch an existing .dat

`dump` before you `poke`: the fresh dump is the exact revert file (build the
revert from the *current* state, never from a stale snapshot — efi-nvram.md §7).
"""

from __future__ import annotations

import struct
import sys
import zlib

SETUP_VAR = ("/sys/firmware/efi/efivars/"
             "Setup-ec87d643-eba4-4bb5-a1e5-3f3e36b20da9")
SETUP_DEFAULT_VAR = ("/sys/firmware/efi/efivars/"
                     "SetupDefault-0ee72c08-8185-427a-a58a-855b78b7ba0b")
EFIVARFS_HEADER = 4
TABLE_LEN = 322
NAME = "Setup"
NAME_LEN = len(NAME.encode("utf-16-le")) + 2          # 12
GUID_BYTES = bytes.fromhex("43d687eca4ebb54ba1e53f3e36b20da9")
ATTRS = 7                                              # NV | BS | RT
DATA_OFFSET = 4 + 4 + NAME_LEN + 16 + 4                # 40

OFFDEFAULT_KNOWN = [3, 4, 9, 13, 21, 22, 23, 38, 174, 244,
                    276, 278, 280, 284, 316]


def read_live_setup() -> bytes:
    try:
        with open(SETUP_VAR, "rb") as fh:
            raw = fh.read()
    except PermissionError:
        sys.exit("permission denied reading Setup (try: sudo)")
    except FileNotFoundError:
        sys.exit("no Setup variable (not an EFI boot?)")
    data = raw[EFIVARFS_HEADER:]
    if len(data) != TABLE_LEN:
        sys.exit(f"unexpected Setup size {len(data)}, expected {TABLE_LEN}")
    return data


def build_dat(data: bytes) -> bytes:
    header = (struct.pack("<I", NAME_LEN) + struct.pack("<I", len(data))
              + NAME.encode("utf-16-le") + b"\x00\x00" + GUID_BYTES
              + struct.pack("<I", ATTRS))
    assert len(header) == DATA_OFFSET, len(header)
    body = header + data
    return body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)


def apply_patches(data: bytearray, patches: list[str]) -> None:
    for p in patches:
        off, val = p.split("=")
        i, v = int(off, 0), int(val, 0)
        if not (0 <= i < len(data)):
            sys.exit(f"offset {i} out of range")
        if not (0 <= v <= 0xFF):
            sys.exit(f"value {v} out of byte range")
        print("  offset %3d: 0x%02x -> 0x%02x%s"
              % (i, data[i], v, "   (known off-default)" if i in OFFDEFAULT_KNOWN else ""))
        data[i] = v


def cmd_dump(out: str) -> None:
    data = read_live_setup()
    with open(out, "wb") as fh:
        fh.write(build_dat(data))
    print(f"wrote {out} (fresh, unmodified)")


def cmd_poke(out: str, patches: list[str]) -> None:
    data = bytearray(read_live_setup())
    print("patching live Setup:")
    apply_patches(data, patches)
    with open(out, "wb") as fh:
        fh.write(build_dat(bytes(data)))
    print(f"wrote {out}")


def cmd_repatch(src: str, out: str, patches: list[str]) -> None:
    raw = open(src, "rb").read()
    data = bytearray(raw[DATA_OFFSET:-4])
    print(f"patching {src}:")
    apply_patches(data, patches)
    with open(out, "wb") as fh:
        fh.write(build_dat(bytes(data)))
    print(f"wrote {out}")


def cmd_info(path: str) -> None:
    raw = open(path, "rb").read()
    namelen, size = struct.unpack_from("<II", raw, 0)
    name = raw[8:8 + namelen].decode("utf-16-le").rstrip("\x00")
    attrs = struct.unpack_from("<I", raw, 8 + namelen + 16)[0]
    data = raw[DATA_OFFSET:-4]
    trailer = struct.unpack_from("<I", raw, len(raw) - 4)[0]
    ok = trailer == (zlib.crc32(raw[:-4]) & 0xFFFFFFFF)
    print(f"file {path}: {len(raw)} bytes")
    print(f"  name={name!r} namelen={namelen} size={size} attrs=0x{attrs:x}")
    print(f"  CRC32 trailer=0x{trailer:08x} valid={ok}")
    print(f"  data[0:16] = {' '.join('%02x' % b for b in data[:16])}")
    print(f"  off-default vs SetupDefault: ", end="")
    try:
        dflt = open(SETUP_DEFAULT_VAR, "rb").read()
    except FileNotFoundError:
        dflt = None
    if dflt:
        dflt = dflt[4:]
        diff = [i for i in range(min(len(data), len(dflt))) if data[i] != dflt[i]]
        print(" ".join(f"{i}:{data[i]:02x}/{dflt[i]:02x}" for i in diff))
    else:
        print("(SetupDefault unreadable)")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip().splitlines()[-1])
    cmd = sys.argv[1]
    if cmd == "dump" and len(sys.argv) == 3:
        cmd_dump(sys.argv[2])
    elif cmd == "poke" and len(sys.argv) >= 4:
        cmd_poke(sys.argv[2], sys.argv[3:])
    elif cmd == "repatch" and len(sys.argv) >= 5:
        cmd_repatch(sys.argv[2], sys.argv[3], sys.argv[4:])
    elif cmd == "info" and len(sys.argv) == 3:
        cmd_info(sys.argv[2])
    else:
        sys.exit(__doc__.strip().splitlines()[-1])


if __name__ == "__main__":
    main()
