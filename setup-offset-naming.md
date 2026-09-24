# Naming the remaining `Setup` offsets — protocol

`efi-nvram.md` §6 lists the offsets this machine has off the factory default.
The TPM bit (`Setup` offsets 3-4) and `AMD_PBS_SETUP` offset 82 are named; the
rest are not. This is the protocol to name them, and it is **a manual job** —
every step needs a reboot, most of them a BIOS menu or a UEFI Shell session.
The tooling here removes the guesswork, not the reboots.

Read this with [`efi-nvram.md`](efi-nvram.md) §7 open: it is why a plain
before/after diff cannot name an offset, and why every method below is a
two-leg (or effect-observed) test.

## What is actually unnamed right now

`sudo python3 evidence/setupdiff.py offdefault` on this machine, today:

```
offset   3: default=0x01 -> current=0x00      <- TPM enable (known)
offset   4: default=0x01 -> current=0x00      <- TPM enable (known)
offset   9: default=0x00 -> current=0x01      <- save-noise (settled in §7)
offset  13: default=0x00 -> current=0x01      <- save-noise
offset  21: default=0x00 -> current=0x01      <- ?
offset  22: default=0x00 -> current=0x01      <- ?
offset  23: default=0x00 -> current=0x01      <- ?
offset  38: default=0x02 -> current=0x00      <- ?
offset 174: default=0x00 -> current=0x02      <- ?
offset 244: default=0x04 -> current=0x00      <- ?
offset 276: default=0x00 -> current=0x01      <- ?
offset 278: default=0x01 -> current=0x02      <- ?
offset 280: default=0x02 -> current=0x00      <- ?
offset 284: default=0x04 -> current=0x00      <- ?
offset 316: default=0x00 -> current=0x01      <- ?
```

So **eleven** candidates: `21, 22, 23, 38, 174, 244, 276, 278, 280, 284, 316`.
(Two more than `efi-nvram.md`'s list — offset 38 newly shows off-default, and
the list drifts as the setup is saved, which is itself §7's point.)

## Prerequisites

- A FAT32 USB key carrying `Shell_Full.efi` as `EFI/BOOT/BOOTX64.EFI` plus the
  `dumps\` folder — the setup is in
  [`evidence/uefi-shell-probe/README.md`](evidence/uefi-shell-probe/README.md).
  Boot it via **Boot Maintenance Manager → Boot From File**.
- **Rehearse in QEMU + OVMF before the real firmware.** This machine has
  `qemu-system-x86_64` and `edk2-shell`; the probe README documents that the
  rehearsal is what caught every protocol bug last time. Do the same with any
  new `.dat` you generate here.
- The USB Shell is also the **recovery path**: it boots without the OS, so a
  bad `Setup` value (even one that stops the OS booting) is always revertible
  from it. Put the revert file on the key *before* every poke.

## Method A — menu-driven two-leg (safe, names by *meaning*)

This is the method `efi-nvram.md` §7 validated. It is slow — two reboots per
option — but it names an offset by the option you toggled, not by inferring
what an unknown poke did.

Per option:

1. Linux: `sudo python3 evidence/setupdiff.py snapshot <opt>-a`
2. Reboot → BIOS → change **one** option → save → reboot.
3. Linux: `sudo python3 evidence/setupdiff.py snapshot <opt>-b`
4. Reboot → BIOS → set that option **back** → save → reboot.
5. Linux: `sudo python3 evidence/setupdiff.py snapshot <opt>-c`
6. `sudo python3 evidence/setupdiff.py twoleg <opt>-a <opt>-b <opt>-c`

Keep only offsets that appear under *"moved out AND back (real signal)"*. If
`HPSetupData`/`SetupDefault` also flag the same bit, that is a second,
independent witness — good (see the TPM result). Use `evidence/tpmstate.py`
alongside when the option is TPM-adjacent.

Good options to toggle, because their effect is observable: TPM (done),
**USB Camera Enable** (done, `AMD_PBS_SETUP` 82), Secure Boot, XHCI/legacy USB,
the dGPU (hybrid vs UMA), and anything under `AMD CBS`.

## Method B — poke one offset (one reboot each, names by *effect*)

`firmware-limits.md` established that a direct `SetVariable` on `Setup` from
the real UEFI Shell works for a genuinely different value, not just a no-op.
That reopens poking one offset at a time — faster than A, and the only way to
ask "what does offset N actually *do*?" for an offset no menu item obviously
maps to. `efi-nvram.md` flags this as untried on an *unnamed* offset, which is
exactly what makes it worth doing carefully.

The `.dat` format is now fully known (verified byte-exact against the four
probe files): **40-byte header + 322-byte table + zlib CRC32 of the two**, and
the 322-byte table has **no internal checksum**. `evidence/setup-poke.py`
builds the file and fixes the CRC.

Per offset `<N>`:

1. Linux, with the key mounted at `/mnt/usb`:
   ```
   sudo python3 evidence/setup-poke.py dump  /mnt/usb/dumps/Setup-revert.dat
   sudo python3 evidence/setup-poke.py poke  /mnt/usb/dumps/Setup-poke-<N>.dat <N>=<newvalue>
   sync
   ```
   (choose `<newvalue>` = the *default* from the table above, so the poke moves
   the offset to its factory value — an unambiguous, reversible change.)
2. Reboot → UEFI Shell. Load it:
   ```
   dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -l fs1:\dumps\Setup-poke-<N>.dat > fs1:\dumps\poke-<N>-result.txt
   dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -s fs1:\dumps\Setup-after-poke-<N>.dat
   ```
   Check `poke-<N>-result.txt` says it loaded (not "no matching variables" —
   that is the `-l`-needs-its-own-`-guid` bug the probe README documents).
3. Reboot → Linux. `sudo python3 evidence/setupdiff.py snapshot poke-<N>` then
   `diff before poker snapshot` — the target offset should be the only *real*
   signal once you apply the two-leg check.
4. **Observe the effect.** This is where the naming comes from: did a device
   appear/disappear (`lsusb`, `lspci`, `dmesg`), a controller change mode, a
   thermal limit move? A small script that diffs the observable surface before
   and after (`lspci -nn`, `lsusb`, `ls /sys/class/*`, `dmesg`) captures it.
5. **Revert** before the next offset: reboot → Shell →
   `dmpstore Setup -guid EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9 -l fs1:\dumps\Setup-revert.dat`,
   then Linux → snapshot → `twoleg` to confirm the offset returned.

### Why "build the revert from a fresh dump"

`efi-nvram.md` §7, learned the hard way: the setup table moves bytes on *every*
save, so a revert built from an old snapshot would clobber whatever changed in
between, not just your poke. `setup-poke.py dump` reads the **live** variable,
so the revert is always current.

## Safety, stated plainly

- **A poke changes an unknown setting.** The value could disable a controller
  the OS boots from, flip a memory/PCIe option, or change a thermal limit.
  Reversible via the Shell (which needs no OS), but if you cannot reach the key
  you have a problem — so confirm "Boot From File" works *before* the first poke.
- **One offset at a time, default-value target, revert between.** Never batch
  pokes; you will not be able to attribute the effect.
- **Method A before Method B** where an option exists: A names by meaning and
  is what the repo has already trusted. Use B only for offsets no menu maps to.
- Nothing here is a firmware write in the Sure Start sense — `Setup` is NVRAM
  configuration, not the signed flash payload. It cannot brick the firmware,
  but it can make the machine misconfigured until reverted.

## What to bring back

For each `<N>`: `dumps\poke-<N>-result.txt`, `dumps\Setup-after-poke-<N>.dat`,
the `setupdiff` snapshots, and the before/after of the observable surface. Drop
them in `evidence/setup-offsets/` and I can fold the names into
[`efi-nvram.md`](efi-nvram.md) §6.

## Tooling

| Tool | What it does |
|---|---|
| `evidence/setupdiff.py` | `verify` / `offdefault` / `snapshot` / `diff` / `twoleg` — the tables |
| `evidence/tpmstate.py` | the TPM variables and the setup tables together |
| `evidence/setup-poke.py` | build / inspect a `dmpstore` `.dat`; patch one offset, CRC fixed |
| `evidence/uefi-shell-probe/` | the USB key scripts and the probe's own `.dat` files |
