# Pre-boot apply bridge

Applies one named option change to a setup varstore from a UEFI Shell, with an
automatic revert if the change stops the machine booting. Built on the static
map in [`../ifr-static`](..) (which names the options) and the `dmpstore` write
path proven in [`../../../firmware-limits.md`](../../../firmware-limits.md#correction-the-setup-lock-is-linuxs-not-the-firmwares).

**Nothing here has been applied to the real firmware.** `bridge.py` only builds
files; `arm.sh` only stages them on the ESP; the actual `SetVariable` happens
pre-boot, deliberately, from the real Shell.

## Flow

1. Linux: `bridge.py build <VARSTORE> "<option>=<value>"` → writes the change
   and a *fresh* revert (never a stale snapshot — the mistake `efi-nvram.md` §7
   records).
2. `arm.sh` stages them on the ESP **under 8.3 names** (`dumps/poke.dat` for the
   change; `dumps/rev.dat` for a revert), plus `startup.nsh`.
3. Arm the one-shot boot to the Shell (`efibootmgr -n N`), reboot.
4. The firmware boots the Shell. `startup.nsh` is **flat and unconditional**: it
   loads `rev.dat` if present, deletes it, loads `poke.dat` if present, deletes
   it, then `reset`s. `dmpstore` on an absent file is a harmless error.
5. It boots back into Linux. To revert, stage the revert as `dumps/rev.dat` and
   repeat; nothing else changes.

## EDK2 Shell gotchas (learned the hard way, 2026-09-29)

These cost a whole debugging session; the QEMU rehearsal reproduces all three.

- **Long file names are silently unopenable.** `dmpstore … -l <file>` and `del`
  fail with `Cannot open file` / `File not found` on a *long* (LFN) name, even
  though `mdir`/`if exist` list it fine. Use 8.3 names only: `poke.dat`,
  `rev.dat`, `pkres.txt`. This is the real reason the first attempts applied
  nothing.
- **A false `if exist … then` breaks the checks after it.** In this firmware's
  Shell, once an `if exist` evaluates false, later `if exist` blocks are
  mis-skipped. The script is therefore flat, with **no `if` at all**.
- `dmpstore`'s argument order is `dmpstore <name> -guid <guid> -l <file>` — the
  name and `-guid` first, `-l` last — and `-l` needs its own `-guid` (repeating
  the name). See `../../../evidence/uefi-shell-probe/README.md`.

## Rehearse first

`./rehearse-qemu.sh [VARSTORE]` boots the exact `.dat` files in QEMU + OVMF,
against OVMF's variable store, and shows what `dmpstore` reported. This is the
step that caught every protocol bug in `../../../evidence/uefi-shell-probe/`;
run it before any contact with the real firmware.

## Safety

- One option at a time; revert between. Never batch.
- The Shell entry on the ESP is the recovery path (boots with no OS). Confirm
  it loads *before* arming, and remove the ESP files + `Boot0008` when done.
- `Setup` is NVRAM configuration, not the signed flash — it cannot brick the
  firmware. It can still leave the machine misconfigured until reverted.

## A worked protocol

[`experiment-pbs-power/`](experiment-pbs-power/) — the first concrete use: is
`AMD_PBS_SETUP` 111–117 (*"power limit adjustment percent"*) a real lever or
inert like the AMD CBS power selector? Baseline probe + A/B + decision rule.

## Applied on this machine

`Setup` **off=218** (Onboard PCIE LAN PXE ROM) and **off=227** (CDROM boot) set
to `0` (2026-09-29), to skip two Option ROMs at POST. Boot config is the one
firmware surface this platform honours — unlike the AMD power/OC/memory levers,
which the experiments above found inert (and against which the rest of the repo
has the OS-side tools).
