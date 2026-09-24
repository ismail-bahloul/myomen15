#!/usr/bin/env python3
"""Build a dmpstore .dat file that creates the (currently missing) AOD_SETUP
EFI variable, so it can be loaded with `dmpstore AOD_SETUP -guid <guid> -l
aod-setup-create.dat` from a real UEFI Shell.

The dmpstore binary record format was reverse-engineered from
evidence/uefi-shell-probe/Setup-preloop.dat (a known-good record dmpstore
itself produced for the `Setup` variable):

    NameSize   u32 LE   -- bytes of the UTF-16LE name, incl. null terminator
    DataSize   u32 LE
    Name       NameSize bytes, UTF-16LE, null-terminated
    Guid       16 bytes (Data1 LE4, Data2 LE2, Data3 LE2, Data4 8 bytes as-is)
    Attributes u32 LE
    Data       DataSize bytes
    Crc32      u32 LE, binascii.crc32 over every byte before it

Verified against Setup-preloop.dat: header+name+guid+attr = 40 bytes,
data = 0x142 bytes, +4 bytes trailing CRC32 = 366 bytes total, and the
stored CRC32 matches a recompute over data[:-4].

The GUID below was extracted directly from AodSmmSsp.pe32's disassembly
(radare2, section .data @ 0x15000, referenced as arg2 to the SmmGetVariable
call at 0x12f93/0x146a0, right before `lea rcx, str.AOD_SETUP`):

    5ED15DC0-EDEF-4161-9151-6014C4CC630C

See ../aod-smm-curve-optimizer-trace.txt and acpi-bridge.md for how that
GetVariable call gates the *entire* SMI command dispatcher in
fcn.00012f18 -- if it fails (which it does today, since AOD_SETUP does not
exist), the handler bails out before ever reaching the `Set PPT Limit` /
`Set Curve Optimizer` command chain. Creating this variable is the test for
whether that's the real reason the `\\AOD` road measured "inert" in
firmware-limits.md.
"""
import argparse
import binascii
import struct
import uuid

AOD_SETUP_GUID = "5ED15DC0-EDEF-4161-9151-6014C4CC630C"


def guid_bytes(guid_str: str) -> bytes:
    u = uuid.UUID(guid_str)
    # Microsoft/EFI_GUID layout: Data1/2/3 little-endian, Data4 as-is.
    return u.bytes_le


def build_record(name: str, guid_str: str, attributes: int, data: bytes) -> bytes:
    name_utf16 = (name + "\0").encode("utf-16-le")
    header = struct.pack("<II", len(name_utf16), len(data))
    body = header + name_utf16 + guid_bytes(guid_str) + struct.pack("<I", attributes) + data
    crc = binascii.crc32(body) & 0xFFFFFFFF
    return body + struct.pack("<I", crc)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--output", default="aod-setup-create.dat")
    ap.add_argument("--name", default="AOD_SETUP")
    ap.add_argument("--guid", default=AOD_SETUP_GUID)
    ap.add_argument("--attributes", type=lambda s: int(s, 0), default=0x7,
                     help="default 0x7 = NV|BS|RT, same class as every other setup-family variable")
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x3FC,
                     help="zero-filled data size in bytes (default: 0x3fc = 1020). "
                          "Two constraints pin this, both measured: (1) AodSmmSsp allocates its "
                          "persistent config buffer with AllocatePool(EfiRuntimeServicesData, "
                          "DataSize, &ptr) using AOD_SETUP's *own* DataSize, then writes into it "
                          "at ~60 fixed offsets scattered across the command dispatcher -- the "
                          "highest confirmed by static analysis is a byte write at +0x234, so the "
                          "buffer must be noticeably larger than that or later commands overflow "
                          "the SMRAM pool allocation the first time they run. (2) The *initial* "
                          "GetVariable call that gates the whole dispatcher reads into a fixed "
                          "0x3fc-byte stack buffer -- a DataSize above that returns "
                          "EFI_BUFFER_TOO_SMALL, which fails the same sign-bit check as "
                          "EFI_NOT_FOUND and defeats the whole point. 0x3fc is the largest value "
                          "satisfying both: comfortably past every offset seen (0x234) and exactly "
                          "at the read cap.")
    args = ap.parse_args()

    data = b"\x00" * args.size
    record = build_record(args.name, args.guid, args.attributes, data)

    with open(args.output, "wb") as f:
        f.write(record)

    print(f"wrote {args.output}: {len(record)} bytes")
    print(f"  name       = {args.name!r} ({len((args.name + chr(0)).encode('utf-16-le'))} bytes)")
    print(f"  guid       = {args.guid}")
    print(f"  attributes = 0x{args.attributes:x}")
    print(f"  data       = {len(data)} zero bytes")
    print()
    print("Load it from the real UEFI Shell with:")
    print(f"  dmpstore {args.name} -guid {args.guid} -l {args.output}")
    print("Then confirm it stuck with:")
    print(f"  dmpstore {args.name} -guid {args.guid} -s dumps\\{args.name}-after-create.dat")


if __name__ == "__main__":
    main()
