# Pre-boot UEFI Shell probe — result, and how to reproduce it

Goal: use the real UEFI Shell (not the SmokelessUMAF setup browser) to reach
`dmpstore`, which calls `GetVariable`/`SetVariable` directly, outside
Linux's `efivarfs` and its `immutable` inode policy on the setup store.
This tests a question `firmware-limits.md` left open: is the refusal to
write `Setup`/`AmdSetup`/etc. a real firmware lock, or a Linux-side
convention layered on top of a firmware that would actually accept the
write?

## Result

**The firmware accepts it. The lock is Linux's.** Writing `Setup` back
with its own unchanged bytes, via `dmpstore` from the real Shell, succeeds:

```
Load and set variables from file: dumps\Setup-preloop.dat.
Variable NV+RT+BS 'EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9:Setup' DataSize = 0x142
```

No error, and `Setup-preloop.dat`/`Setup-postloop.dat` (kept in this
directory) are byte-identical — a clean no-op, not a silent partial write.
Full writeup: [`firmware-limits.md`](../../firmware-limits.md#correction-the-setup-lock-is-linuxs-not-the-firmwares).

**A genuinely different value was then tested too, and cross-validated three
independent ways.** `Setup` offsets 3-4 (the TPM enable bit, named via the
two-leg method in `efi-nvram.md`) were flipped from `01 01` (disabled) to
`00 00` (enabled) with a hand-patched, CRC-recomputed `dmpstore` file
(`Setup-tpm-ENABLE-test.dat`) — see
[`tpm-apply-result.txt`](tpm-apply-result.txt) and
[`Setup-after-apply.dat`](Setup-after-apply.dat). Then, independently:

1. **The value persisted across multiple real reboots** — into
   Smokeless_UMAF (a different tool entirely) and back into Linux — not
   just within the shell session that wrote it.
2. **The native BIOS menu was used to do the same thing the "normal" way**
   (take TPM out of `Hidden`, set `TPM Embedded Security Device` to
   `Enabled`, save) — and produced the exact same bytes, `00 00`, at the
   exact same offsets. The raw write and the menu's own save path agree.
3. **The OS saw a real effect**: `/dev/tpm0`/`/dev/tpmrm0` appeared, and
   `dmesg` showed the kernel binding `tpm_crb_acpi` to the ACPI TPM2 table.

Reverting used a lesson from `efi-nvram.md` §7 the hard way: the first
prepared revert file (`Setup-tpm-DISABLE-revert.dat`) was built by patching
the *original* pre-test snapshot — replaying it would have overwritten the
`Hidden`-state change made through the menu in between, not just the TPM
bit. The revert that was actually used
(`Setup-tpm-DISABLE-revert-fresh.dat`, loaded by `tpm-revert-fresh.nsh`) was
built from a **fresh** dump of the then-current `Setup`, patching only
offsets 3-4 back to `01 01` — confirmed by
[`tpm-revert-fresh-result.txt`](tpm-revert-fresh-result.txt) and
[`Setup-after-revert-fresh.dat`](Setup-after-revert-fresh.dat), and by a
fresh `efivarfs` read afterward. The stale file is kept, not deleted — it's
the mistake that mattered, and the fix is the point.

## What's here

- `startup.nsh` — phase 1, read-only, auto-runs on boot. Dumps `Setup`,
  `SetupDefault`, `StdDefaults`, `AmdSetup`, `AMD_PBS_SETUP`,
  `HPSetupData`, `NewHPSetupData`, `AMITSESetup` individually, plus one
  `dmpstore -all` catch-all, to files under `dumps\` on the USB key.
- `verify-writeback.nsh` — phase 2, automated. Does the no-op write-back
  on `Setup` and redirects `dmpstore`'s own status line to
  `dumps\writeback-result.txt`, so the answer is a file, not a memory of
  what flashed on screen.
- `phase2-writeback-test.txt` — the same test as `verify-writeback.nsh`,
  but as commands meant to be typed one at a time at the Shell prompt
  instead — kept for anyone who wants to watch each step live rather than
  run the script.
- `writeback-result.txt`, `Setup-preloop.dat`, `Setup-postloop.dat` — the
  actual output from the real machine, kept as evidence.

**All of it was rehearsed end to end in a local QEMU + OVMF test VM (this
machine already has `edk2-ovmf` and `qemu-base` installed) before touching
the real USB key or the real firmware.** That caught four real bugs, two
of them only after a first real-hardware run had already produced a
result that looked like an answer and wasn't:

1. `REM` is not a comment in EDK2 Shell scripts — it's just an unknown
   command. Comments were removed rather than guessed at again.
2. The Shell does **not** default to any current filesystem, even inside
   an autorun script — `mkdir dumps` and every relative path failed until
   an explicit `fs1:` was added at the top. `fs1:` matches *this
   machine's own mapping*, confirmed from its actual boot log (`FS1:` =
   the USB key, `FS0:` = the internal NVMe ESP) — if the USB port or
   attached devices change, check the mapping table printed at Shell
   startup and adjust the first line of the scripts accordingly.
3. `dmpstore`'s real argument order is `dmpstore <name> -guid <guid> -s
   <file>` (name and `-guid` first, `-s`/`-l` last) — the first draft had
   `-s`/`-guid` before the name, which parses as "too many arguments".
4. **The one that produced a fake answer on the first real run:** `-l
   <file>` needs its own `<name> -guid <guid>` repeated, exactly like
   `-s` does. Without it, `-l` silently filters on the default
   `EFI_GLOBAL_VARIABLE` GUID instead of whatever the file actually
   contains, reports "No matching variables found" for that wrong GUID,
   and never touches `Setup` at all. The first real-hardware run did
   exactly this: `Setup-preloop.dat`/`Setup-postloop.dat` came back
   byte-identical, which looked like a successful no-op but actually meant
   nothing had been attempted. This was caught by reproducing the same
   false-success shape in the QEMU VM against a variable with a
   similarly non-default GUID, then fixing it and confirming the fix
   there before re-running on the real machine.

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
sudo cp evidence/uefi-shell-probe/verify-writeback.nsh /mnt/usb/verify-writeback.nsh
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
3. At the `FS1:\>` prompt, type `verify-writeback.nsh` to run phase 2.
4. Reboot back into Linux and copy the dump files off the USB key.

## What to bring back

Everything under `\dumps\`, especially `writeback-result.txt` — it's
UTF-16 with a BOM (`dmpstore`'s own encoding for redirected output), so
decode it before reading, e.g. `python3 -c "print(open('writeback-result.txt','rb').read().decode('utf-16'))"`.
