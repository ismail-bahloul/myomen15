#!/bin/sh
# run.sh -- empirically exercise the AMD-TEE Trusted-Application signature gate.
#
# The amdtee driver loads a TA as firmware:
#   open("/dev/tee0") + TEE_IOC_OPEN_SESSION(uuid)
#     -> amdtee_open_session -> request_firmware("amdtee/<uuid>.bin")
#     -> copy_ta_binary -> TEE_CMD_LOAD_TA to the PSP -> the PSP verifies the blob.
# The ioctl's returned `ret` is the PSP's verdict on the blob.
#
# This installs one byte-flipped variant of the TA at a time under its real UUID
# (the kernel re-reads the firmware from disk on every open -- verified by removing
# the file and seeing "failed to load firmware"), records the PSP's ret, and
# restores the original. Must run as root, with `modprobe amdtee` done.
#
# Usage: sudo sh run.sh
set -eu

UUID=773bd96f-b83f-4d52-b12dc529b13d8543
FW="/lib/firmware/amdtee/$UUID.bin.zst"
DEV=/dev/tee0
HERE=$(cd "$(dirname "$0")" && pwd)
BIN="$HERE/teeopen"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

[ "$(id -u)" = 0 ] || { echo "run as root"; exit 1; }
[ -e "$DEV" ] || { echo "$DEV missing -- modprobe amdtee first"; exit 1; }
[ -x "$BIN" ] || gcc -O2 -Wall -o "$BIN" "$HERE/teeopen.c"

zstdcat "$FW" > "$TMP/orig.bin"
cp "$FW" "$TMP/orig.bin.zst"          # keep the vendor-compressed original

# flip_install <offset-hex, no 0x>  -- 0 means "no flip" (pristine)
flip_install() {
    off=$1
    if [ "$off" = 0 ]; then
        cp "$TMP/orig.bin.zst" "$FW"
        return
    fi
    python3 -c "p='$TMP/v.bin'; d=bytearray(open('$TMP/orig.bin','rb').read()); i=int('$off',16); d[i]^=0xff; open(p,'wb').write(d)"
    zstd -q -f "$TMP/v.bin" -o "$TMP/v.bin.zst"
    cp "$TMP/v.bin.zst" "$FW"
}

probe() { "$BIN" "$DEV" 2>&1 | grep -oE 'ret=0x[0-9a-f]+' | head -1; }

echo "TA blob: $UUID  ($(zstdcat "$FW" | wc -c) bytes decompressed)"
echo "layout : header [0x000..0x100]  signed body [0x100..0x3140]  signature [0x3140..0x3240]"
echo
printf '%-26s %s\n' "variant" "PSP ret"
for spec in "pristine:0" "prefix byte@0x00:00" "header byte@0x40:40" \
            "body byte@0x1000:1000" "body byte@0x3000:3000" "signature byte@0x3200:3200"; do
    name=${spec%%:*}
    off=${spec##*:}
    flip_install "$off"
    printf '%-26s %s\n' "$name" "$(probe)"
done

cp "$TMP/orig.bin.zst" "$FW"
echo
echo "restored original: $(md5sum "$FW" | cut -d' ' -f1)"
