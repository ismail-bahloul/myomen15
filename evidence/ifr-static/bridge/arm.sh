#!/usr/bin/env bash
# Stage a pre-boot apply for one setup varstore. Reads nothing privileged,
# writes only to the ESP. Does NOT reboot and does NOT apply anything itself.
#
# Usage: arm.sh <VARSTORE> [ESP mount]
#   VARSTORE: Setup | AMD_PBS_SETUP | AmdSetup
# Build the .dat first:  BRIDGE_OUT=out python3 ../bridge.py build <VARSTORE> NAME=VALUE
set -euo pipefail

VAR="${1:?VARSTORE: Setup|AMD_PBS_SETUP|AmdSetup}"
ESP="${2:-/boot}"
HERE="$(cd "$(dirname "$0")" && pwd)"

case "$VAR" in
  Setup)         GUID=ec87d643-eba4-4bb5-a1e5-3f3e36b20da9 ;;
  AMD_PBS_SETUP) GUID=a339d746-f678-49b3-9fc7-54ce0f9df226 ;;
  AmdSetup)      GUID=3a997502-647a-4c82-998e-52ef9486a247 ;;
  *) echo "unknown varstore: $VAR" >&2; exit 1 ;;
esac

test -f "$HERE/out/poke-$VAR.dat"   || { echo "missing out/poke-$VAR.dat" >&2; exit 1; }
test -f "$HERE/out/revert-$VAR.dat" || { echo "missing out/revert-$VAR.dat" >&2; exit 1; }

mkdir -p "$ESP/dumps"
cp "$HERE/out/poke-$VAR.dat" "$HERE/out/revert-$VAR.dat" "$ESP/dumps/"
sed -e "s/@VARNAME@/$VAR/g" -e "s/@GUID@/$GUID/g" \
    "$HERE/startup.nsh.in" > "$ESP/startup.nsh"
rm -f "$ESP/dumps/confirmed.txt" "$ESP/dumps/armed.txt"
sync

echo "staged on $ESP:"
echo "  startup.nsh  -> $ESP/startup.nsh"
echo "  dumps/       -> poke-$VAR.dat, revert-$VAR.dat"
echo
echo "NOT rebooting. Arm the one-shot boot to the UEFI Shell entry, then reboot:"
echo "  efibootmgr                       # find the USB Shell entry number N"
echo "  sudo efibootmgr -n N             # next boot = Shell"
echo "  systemctl reboot"
echo "(or use Boot Maintenance Manager -> Boot From File)"
