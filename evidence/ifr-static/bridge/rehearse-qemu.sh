#!/usr/bin/env bash
# Rehearse the pre-boot apply in QEMU + OVMF, against OVMF's own variable store,
# BEFORE the real firmware is ever touched. This is the step that caught every
# protocol bug the uefi-shell-probe pass made; do not skip it.
#
# Exercises the real .dat files produced by bridge.py: dmpstore must load them,
# and the watchdog branch must fire when armed.txt is present and confirmed.txt
# is not.
set -euo pipefail

SHELL_EFI=/usr/share/edk2-shell/x64/Shell_Full.efi
OVMF_CODE=/usr/share/edk2/x64/OVMF_CODE.4m.fd
OVMF_VARS=/usr/share/edk2/x64/OVMF_VARS.4m.fd
HERE="$(cd "$(dirname "$0")" && pwd)"
VAR="${1:-AMD_PBS_SETUP}"

case "$VAR" in
  Setup)         GUID=ec87d643-eba4-4bb5-a1e5-3f3e36b20da9 ;;
  AMD_PBS_SETUP) GUID=a339d746-f678-49b3-9fc7-54ce0f9df226 ;;
  AmdSetup)      GUID=3a997502-647a-4c82-998e-52ef9486a247 ;;
  *) echo "unknown varstore: $VAR" >&2; exit 1 ;;
esac

W="$(mktemp -d)"
trap 'echo "scratch kept at $W"' EXIT

# The rehearsal boots from the first volume (fs0), not fs1 as on the real key.
sed -e "s/@VARNAME@/$VAR/g" -e "s/@GUID@/$GUID/g" -e 's/fs1:/fs0:/g' \
    "$HERE/startup.nsh.in" > "$W/startup.nsh"

dd if=/dev/zero of="$W/usb.img" bs=1M count=8 status=none
mkfs.vfat -n REHEARSE "$W/usb.img" >/dev/null
mmd -i "$W/usb.img" ::/EFI ::/EFI/BOOT ::/dumps
mcopy -i "$W/usb.img" "$SHELL_EFI" ::/EFI/BOOT/BOOTX64.EFI
mcopy -i "$W/usb.img" "$W/startup.nsh" ::/startup.nsh
mcopy -i "$W/usb.img" "$HERE"/out/poke-"$VAR".dat "$HERE"/out/revert-"$VAR".dat ::/dumps/

cp "$OVMF_VARS" "$W/vars.fd"

# -no-reboot makes qemu exit when the script ends with `reset -c`.
timeout 120 qemu-system-x86_64 -machine q35 -m 256 -nographic -no-reboot -net none \
  -drive if=pflash,format=raw,unit=0,readonly=on,file="$OVMF_CODE" \
  -drive if=pflash,format=raw,unit=1,file="$W/vars.fd" \
  -drive file="$W/usb.img",format=raw,if=none,id=u0 \
  -device usb-ehci -device usb-storage,drive=u0 \
  > "$W/serial.log" 2>&1 || true

echo "=== shell output (tail) ==="
tail -25 "$W/serial.log"
echo
echo "=== result files the shell wrote ==="
for f in poke-result revert-result armed; do
  echo "--- $f ---"
  mtype -i "$W/usb.img" "::/dumps/$f.txt" 2>/dev/null | iconv -f UTF-16LE -t UTF-8 2>/dev/null || echo "(absent)"
done
