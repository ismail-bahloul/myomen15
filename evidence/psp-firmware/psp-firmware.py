#!/usr/bin/env python3
"""Extract the plaintext SMU / PMU firmware from the PSP directory, and show the
one-line psptool bug that made it look unverifiable.

`firmware-limits.md` recorded, from `psptool -E -t`, that `SMU_OFFCHIP_FW`,
`SMU_OFF_CHIP_FW_2`, `PMU_CODE` and `PMU_DATA` were "compressed,
veri-failed(<keyid>), sha256_ok", and guessed that psptool "mis-slices the
decompressed body against a size_signed field meant for the compressed one".

Neither half of that is what is happening:

  * The **decompression is correct.** `sha256(get_decrypted_decompressed_body())`
    equals the checksum stored in the file header for every one of these
    entries -- so `sha256_ok` is real, and the plaintext is exactly what AMD
    hashed. The SMU firmware is 0x40000 (256 KiB) per image, version
    `0x00404A00` (64.74.0, the same version the SMU mailbox reports).

  * `veri-failed` is a **psptool bug, not an unsigned file.** psptool's
    `HeaderFile.get_signed_bytes()` signs `header + *decompressed* body`. For a
    compressed entry the RSA-PSS signature is over `header + *stored
    (compressed)* body`. With that one line corrected, every compressed entry
    in this image verifies: `verified(96A0)` for the two SMU images,
    `verified(4F75)` for PMU_CODE / PMU_DATA.

This script proves both by reading the image directly (psptool for the parsing),
checking the sha256, and verifying the RSA-PSS signature over *both* message
layouts so the difference is visible rather than asserted. It then dumps the
decompressed bodies to `<out>/`.

Dependency: psptool (`pip install psptool`). Everything else is stdlib.

  python3 psp-firmware.py <ROM image>              # e.g. 088D1.bin
  python3 psp-firmware.py <ROM image> --out DIR    # where the .bin dumps go
"""

import argparse
import hashlib
import os
import struct
import sys

# The one-line fix. Stock psptool uses get_decrypted_decompressed_body() here;
# the signed message is header + stored (compressed) body.
def _fixed_get_signed_bytes(self) -> bytes:
    file_bytes = self.header.get_bytes() + self.get_decrypted_body()
    return file_bytes[:len(self.header) + self.size_signed]


def header_fields(f):
    h = f.header.get_bytes()
    return {
        "magic": h[0x10:0x14],
        "size_signed": struct.unpack("<I", h[0x14:0x18])[0],
        "encrypted": struct.unpack("<I", h[0x18:0x1c])[0],
        "compressed": struct.unpack("<I", h[0x48:0x4c])[0],
        "size_uncompressed": struct.unpack("<I", h[0x50:0x54])[0],
        "zlib_size": struct.unpack("<I", h[0x54:0x58])[0],
        "load_addr": struct.unpack("<I", h[0x68:0x6c])[0],
        "rom_size": struct.unpack("<I", h[0x6c:0x70])[0],
    }


TARGETS = ("SMU_OFFCHIP_FW", "SMU_OFF_CHIP_FW_2", "PMU_CODE", "PMU_DATA")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", help="the flash image (088D1.bin / BIOS_00.bin)")
    ap.add_argument("--out", default=".", help="directory for the decompressed .bin dumps (default: .)")
    args = ap.parse_args()

    try:
        from psptool.psptool import PSPTool
        from psptool.header_file import HeaderFile
    except ImportError:
        sys.exit("psptool is required: pip install psptool")

    # Apply the fix in memory only; the installed copy is left untouched.
    stock_get_signed_bytes = HeaderFile.get_signed_bytes
    HeaderFile.get_signed_bytes = _fixed_get_signed_bytes

    os.makedirs(args.out, exist_ok=True)
    pt = PSPTool.from_file(args.rom, verbose=False)

    print(f"ROM: {args.rom}  ({os.path.getsize(args.rom)} bytes)")
    print()

    seen = 0
    for ri, rom in enumerate(pt.blob.roms):
        for di, directory in enumerate(rom.directories):
            for ei, f in enumerate(directory.files):
                if f is None or not isinstance(f, HeaderFile):
                    continue
                t = f.get_readable_type()
                if not any(t.startswith(x) for x in TARGETS):
                    continue
                seen += 1
                hf = header_fields(f)
                stored = f.get_decrypted_body()                 # body as stored in flash
                plain = f.get_decrypted_decompressed_body()     # after zlib
                stored_sha = hashlib.sha256(plain).hexdigest()
                chk = f._sha256_checksum.get_bytes().hex()
                keys = f.signed_entity.certifying_keys if f.signed_entity else set()

                # both candidate signed messages, verified against the certifying key
                msg_bad = (f.header.get_bytes() + plain)[:len(f.header.get_bytes()) + hf["size_signed"]]
                msg_ok = (f.header.get_bytes() + stored)[:len(f.header.get_bytes()) + hf["size_signed"]]
                sig = f.signed_entity.signature.get_bytes() if f.signed_entity else b""

                print(f"dir={di} entry={ei}  {t}  sub={f.entry.subprogram} inst={f.entry.instance}")
                print(f"  addr 0x{f.get_address():x}  entry_size 0x{len(f):x}  magic {hf['magic']!r}  "
                      f"version {f.get_readable_version()}")
                print(f"  size_signed 0x{hf['size_signed']:x}  size_uncompressed 0x{hf['size_uncompressed']:x}  "
                      f"zlib_size 0x{hf['zlib_size']:x}  load_addr 0x{hf['load_addr']:x}")
                print(f"  compressed={f.compressed} encrypted={f.encrypted}  "
                      f"stored=0x{len(stored):x}  plaintext=0x{len(plain):x}")
                print(f"  sha256(plaintext) == header checksum : {stored_sha == chk}")
                for k in keys:
                    pk = k.get_public_key()
                    bad = pk.verify_blob(msg_bad, sig)
                    good = pk.verify_blob(msg_ok, sig)
                    print(f"  RSA-PSS vs key {k.get_magic()}:  "
                          f"header+plaintext -> {bad}   header+stored -> {good}")

                name = t.split("~")[0]
                if f.entry.subprogram or f.entry.instance:
                    name += f"_sub{f.entry.subprogram}_ins{f.entry.instance}"
                if di in (2, 3):  # BHD / BL2 hold two copies of the PMU images
                    name += f"_d{di}"
                out = os.path.join(args.out, name + ".bin")
                with open(out, "wb") as o:
                    o.write(plain)
                print(f"  wrote {out}")
                print()

    HeaderFile.get_signed_bytes = stock_get_signed_bytes
    print(f"{seen} entries extracted. The .bin dumps are gitignored (*.bin); "
          f"their hashes are in fw-analysis.txt.")


if __name__ == "__main__":
    main()
