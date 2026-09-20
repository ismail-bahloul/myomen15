#!/usr/bin/env bash
# bios-unwrap.sh -- unwrap the AMI update capsule and confirm the 16 MiB
# image inside is Tiano/EFI-*compressed*, not encrypted: it fully parses
# with standard, public EDK2 tooling once that tooling is present.
#
# What was missing before was never the format -- it was TianoCompress.
# `uefiextract` (LongSoft/UEFITool, "New Engine") shells out to it for every
# EFI-compressed section, and without it on PATH it fails silently. This
# builds the real thing from EDK2's own BaseTools source (a few seconds,
# no exotic dependencies) instead of guessing at the compression scheme.
#
# Prerequisites this script assumes are already present:
#   - `uefiextract` (UEFITool "New Engine" build, LongSoft/UEFITool on GitHub)
#   - python3, pip, git, gcc, make
#
# Usage:
#   ./bios-unwrap.sh /path/to/BIOS_Update.exe   # or an already-extracted
#                                                #  '[0]' PE resource / 088D1.bin
set -euo pipefail

IN="${1:?usage: bios-unwrap.sh <ami-capsule-or-088D1.bin>}"
WORK="$(mktemp -d)"
trap 'echo "(scratch dir kept at $WORK)"' EXIT

echo "== 1. TianoCompress + LzmaCompress, built from EDK2 BaseTools source =="
git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/tianocore/edk2.git "$WORK/edk2-src" >/dev/null 2>&1
git -C "$WORK/edk2-src" sparse-checkout set BaseTools/Source/C >/dev/null
git -C "$WORK/edk2-src" sparse-checkout add MdePkg/Include >/dev/null
export EDK2_PATH="$WORK/edk2-src"
make -C "$WORK/edk2-src/BaseTools/Source/C/Common" >/dev/null
make -C "$WORK/edk2-src/BaseTools/Source/C/TianoCompress" >/dev/null
make -C "$WORK/edk2-src/BaseTools/Source/C/LzmaCompress" >/dev/null
export PATH="$WORK/edk2-src/BaseTools/Source/C/bin:$PATH"
TianoCompress --help >/dev/null && echo "  TianoCompress: OK"

echo "== 2. biosutilities (platomav) + psptool (PSPReverseEngineering) =="
python3 -m venv "$WORK/venv" >/dev/null
"$WORK/venv/bin/pip" install -q biosutilities psptool >/dev/null

echo "== 3. Unwrap the AMI UCP container down to the raw 16 MiB image =="
cat > "$WORK/unwrap.py" <<'PYEOF'
import sys
from biosutilities.ami_ucp_extract import AmiUcpExtract

in_path, out_dir = sys.argv[1], sys.argv[2]
with open(in_path, "rb") as f:
    data = f.read()

extractor = AmiUcpExtract(input_object=data, extract_path=out_dir, padding=0)
if extractor.check_format():
    extractor.parse_format()
else:
    # Already an unwrapped 16 MiB image (e.g. 088D1.bin) -- nothing to unwrap.
    sys.exit("not an AMI @UAF@ container -- pass it straight to uefiextract instead")
PYEOF
"$WORK/venv/bin/python" "$WORK/unwrap.py" "$IN" "$WORK/extracted"

BIN="$(find "$WORK/extracted" -iname 'BIOS_*.bin' | head -1)"
echo "  unwrapped: $BIN ($(stat -c%s "$BIN") bytes)"

echo "== 4. Parse it as a standard PI/UEFI image =="
uefiextract "$BIN" report
echo "  report: ${BIN}.report.txt"

echo "== 5. Parse the AMD PSP firmware directory (separate from the UEFI volumes) =="
"$WORK/venv/bin/psptool" -E "$BIN"
