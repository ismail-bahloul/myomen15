# Pre-boot apply bridge — watchdog design

Applies one named option change to a setup varstore from a UEFI Shell, with an
automatic revert if the change stops the machine booting. Built on the static
map in [`../ifr-static`](..) (which names the options) and the `dmpstore` write
path proven in [`../../../firmware-limits.md`](../../../firmware-limits.md#correction-the-setup-lock-is-linuxs-not-the-firmwares).

**Nothing here has been applied to the real firmware.** `bridge.py` only builds
files; `arm.sh` only stages them on the ESP; the actual `SetVariable` happens
pre-boot, deliberately, from the real Shell.

## Flow

1. Linux:
   `BRIDGE_OUT=out python3 ../bridge.py build AMD_PBS_SETUP "USB CAMERA=0"`
   → writes `out/poke-AMD_PBS_SETUP.dat` and `out/revert-AMD_PBS_SETUP.dat`
   (the revert is read *fresh*, never a stale snapshot — the mistake
   `efi-nvram.md` §7 records).
2. `./arm.sh AMD_PBS_SETUP` → copies both `.dat` + `startup.nsh` to the ESP.
3. Arm the one-shot boot to the Shell entry (`efibootmgr -n N`), reboot.
4. Firmware boots the **Shell** (the default during the operation). `startup.nsh`:
   - if `armed.txt` exists and `confirmed.txt` does not → the previous change was
     never confirmed → load `revert`, clear armed;
   - then load `poke` if present, write `armed.txt`, and `reset`.
5. Boot back into Linux (via `BootNext`). If the boot is healthy, a service
   deletes `armed.txt`. If it is not, the next boot falls back to the Shell and
   the change is reverted automatically.

The reversal does not depend on Linux reaching a "good" state, only on it not
reaching the OS — that is the point of the marker.

## Why the shell is the default boot

`BootNext` is consumed once. If the changed firmware fails to reach Linux, the
next boot returns to the default — which must be the Shell, or nothing would
recover the machine. Setting the Shell entry first in `BootOrder` for the
duration is what makes the watchdog real.

## Rehearse first

`./rehearse-qemu.sh [VARSTORE]` boots the exact `.dat` files in QEMU + OVMF,
against OVMF's variable store, and shows what `dmpstore` reported. This is the
step that caught every protocol bug in `../../../evidence/uefi-shell-probe/`;
run it before any contact with the real firmware.

## Safety

- One option at a time; revert between. Never batch.
- The USB key with the Shell is the recovery path (boots with no OS). Confirm
  `Boot Maintenance Manager → Boot From File` works *before* arming.
- `Setup` is NVRAM configuration, not the signed flash — it cannot brick the
  firmware. It can still leave the machine misconfigured until reverted.

## A worked protocol

[`experiment-pbs-power/`](experiment-pbs-power/) — the first concrete use: is
`AMD_PBS_SETUP` 111–117 (*"power limit adjustment percent"*) a real lever or
inert like the AMD CBS power selector? Baseline probe + A/B + decision rule,
all prepared and rehearsed, nothing applied.
