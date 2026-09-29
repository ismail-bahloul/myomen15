#!/usr/bin/env bash
# Stage a pre-boot apply (or revert) for one setup varstore on the ESP.
# Writes only to the ESP; does not reboot and does not apply anything itself.
#
# Usage: arm.sh <VARSTORE> [apply|revert] [ESP mount]
#   VARSTORE: Setup | AMD_PBS_SETUP | AmdSetup
# Build the .dat first, e.g.:
#   BRIDGE_OUT=out python3 ../bridge.py build Setup "CDROM boot=0"
#
# Files are staged under 8.3 names on purpose: this firmware's EDK2 Shell
# cannot open long (LFN) names inside a subdirectory (see README.md).
set -euo pipefail

VAR="${1:?VARSTORE: Setup|AMD_PBS_SETUP|AmdSetup}"
MODE="${2:-apply}"
ESP="${3:-/boot}"
HERE="$(cd "$(dirname "$0")" && pwd)"

case "$VAR" in
  Setup)         GUID=ec87d643-eba4-4bb5-a1e5-3f3e36b20da9 ;;
  AMD_PBS_SETUP) GUID=a339d746-f678-49b3-9fc7-54ce0f9df226 ;;
  AmdSetup)      GUID=3a997502-647a-4c82-998e-52ef9486a247 ;;
  *) echo "unknown varstore: $VAR" >&2; exit 1 ;;
esac

mkdir -p "$ESP/dumps"
rm -f "$ESP/dumps/poke.dat" "$ESP/dumps/rev.dat"
case "$MODE" in
  apply)  cp "$HERE/out/poke-$VAR.dat"   "$ESP/dumps/poke.dat" ;;
  revert) cp "$HERE/out/revert-$VAR.dat" "$ESP/dumps/rev.dat"  ;;
  *) echo "mode must be apply|revert" >&2; exit 1 ;;
esac
sed -e "s/@VARNAME@/$VAR/g" -e "s/@GUID@/$GUID/g" \
    "$HERE/startup.nsh.in" > "$ESP/startup.nsh"
sync

echo "staged ($MODE) on $ESP/dumps:"
ls -l "$ESP/dumps"
echo
echo "NOT rebooting. Arm the one-shot boot to the Shell entry, then reboot:"
echo "  sudo efibootmgr            # find the 'UEFI Shell (bridge)' entry number N"
echo "  sudo efibootmgr -n N && sudo systemctl reboot"
