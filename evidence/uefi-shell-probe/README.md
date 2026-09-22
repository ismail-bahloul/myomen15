# Pre-boot UEFI Shell probe — preparing and running it

Goal: use the real UEFI Shell (not the SmokelessUMAF setup browser) to reach
`dmpstore`, which calls `GetVariable`/`SetVariable` directly, outside
Linux's `efivarfs` and its `immutable` inode policy on the setup store.
This tests a question `firmware-limits.md` left open: is the refusal to
write `Setup`/`AmdSetup`/etc. a real firmware lock, or a Linux-side
convention layered on top of a firmware that would actually accept the
write?

Two phases, deliberately kept separate: a read-only recon that is
automated and safe to run unattended, and a single write test that is
**not** automated — run it interactively, one command at a time, so a
bad result is caught before doing anything else.

## What's here

- `startup.nsh` — phase 1, read-only. Dumps `Setup`, `SetupDefault`,
  `StdDefaults`, `AmdSetup`, `AMD_PBS_SETUP`, `HPSetupData`,
  `NewHPSetupData`, `AMITSESetup` individually, plus one `dmpstore -all`
  catch-all, to files under `dumps\` on the USB key. Safe to auto-run
  (EDK2 Shell runs `startup.nsh` automatically if present at the root of
  the boot volume).
- `phase2-writeback-test.txt` — the exact commands for the write-back
  test, meant to be typed one at a time at the Shell prompt, not run as a
  script.

**Both were rehearsed end to end in a local QEMU + OVMF test VM (this
machine already has `edk2-ovmf` and `qemu-base` installed) before being
put on the real USB key.** Three real bugs were caught this way and would
otherwise have needed a real reboot per fix:

1. `REM` is not a comment in EDK2 Shell scripts — it's just an unknown
   command. Comments were removed rather than guessed at again.
2. The Shell does **not** default to any current filesystem, even inside
   an autorun script — `mkdir dumps` and every relative path failed until
   an explicit `fs1:` was added at the top. `fs1:` was picked to match
   *this machine's own mapping*, confirmed from the real boot log
   (`FS1:` = the USB key, `FS0:` = the internal NVMe ESP) — if the USB
   port or attached devices change, check the mapping table printed at
   Shell startup and adjust the first line of `startup.nsh` accordingly.
3. `dmpstore`'s real argument order is `dmpstore <name> -guid <guid> -s
   <file>` (name and `-guid` first, `-s`/`-l` last) — the first draft had
   `-s`/`-guid` before the name, which parses as "too many arguments".
   `-l <file>` was separately confirmed to restore whatever the file
   contains without needing `-guid`/name repeated, and to report a clear
   `Write Protected` (not a silent no-op) for a genuinely protected
   variable, tested against real read-only OVMF variables.

## Preparing the USB key

The machine already boots signed `.efi` binaries from a USB key via
**Boot Maintenance Manager → Boot From File** (this is exactly how
`SuppressIFPatcher.efi`/`SetupBrowser.efi` were run for SREP, per
`firmware-limits.md`), so no Secure Boot enrollment or special signing is
needed here — Secure Boot is already `Disabled` on this machine
(`efi-nvram.md`).

From Linux, with the USB key plugged in (replace `sdX1` with the actual
FAT32 partition):

```bash
sudo mkdir -p /mnt/usb
sudo mount /dev/sdX1 /mnt/usb
sudo mkdir -p /mnt/usb/EFI/BOOT
sudo cp /usr/share/edk2-shell/x64/Shell_Full.efi /mnt/usb/EFI/BOOT/BOOTX64.EFI
sudo cp evidence/uefi-shell-probe/startup.nsh /mnt/usb/startup.nsh
sync
sudo umount /mnt/usb
```

`Shell_Full.efi` (not the trimmed `Shell.efi`) is used specifically
because it has `dmpstore` built in rather than as a separate loadable
command.

## Running it

1. Reboot, enter the firmware's Boot Manager, pick the USB key.
2. `startup.nsh` runs automatically (phase 1) and writes its output files
   to the same USB key. Let it finish, then it prints `phase 1 done`.
3. For phase 2, **do not run a script** — read
   `phase2-writeback-test.txt` and type each command by hand at the
   `Shell>` prompt, checking the result of each before continuing.
4. Boot back into Linux and copy the dump files off the USB key —
   they're the input for the next analysis pass.

## What to bring back

Everything the USB key now has under `\dumps\`, plus whatever the Shell
printed for the phase 2 `dmpstore -l` write-back attempt (a screenshot or
a transcript is fine — that status line is the actual answer to the open
question).
