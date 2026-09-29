# Static IFR extraction — the setup menus, read from the image, no reboots

This directory corrects a conclusion in [`../../efi-nvram.md`](../../efi-nvram.md) §10:

> *Mapping question names to offsets needs the IFR, and the IFR is in the
> encrypted volume.*

**The IFR is not encrypted.** It is in the clear in the image that has been
sitting on the ESP all along (`/boot/EFI/HP/BIOS/Current/088D1.bin`), and it
parses completely. The earlier search that concluded otherwise looked for menu
strings in **ASCII**; UEFI/IFR strings are **UTF-16LE**, so that search could
never have found them.

Consequence: `Setup` / `AMD_PBS_SETUP` / `AmdSetup` / `AOD_SETUP` option names
can be mapped to varstore offsets **offline, with no reboots and no pokes** —
which is what [`../../setup-offset-naming.md`](../../setup-offset-naming.md)
otherwise needs two reboots per option to do.

## What was found

Four HII form packages were extracted and parsed. The varstore GUIDs match the
live EFI variables exactly:

| Module | varstore | size | GUID | questions |
|---|---|---|---|---|
| `Setup` | `Setup` | 322 | `ec87d643-…` | 187 |
| `CbsSetupDxeRN` | `AmdSetup` | 1448 | `3a997502-…` | 525 |
| `AmdPbsSetupDxe` | `AMD_PBS_SETUP` | 136 | `a339d746-…` | 125 |
| `AodSetupDxe` | `AOD_SETUP` | 1020 | `5ed15dc0-…` | 525 |

Two independent checks say the mapping is right:

- **`AMD_PBS_SETUP` offset 82** resolves to *"Enable or disable the power of USB
  CAMERA"* — the option named by hand (two-leg method) in
  [`../../efi-nvram.md`](../../efi-nvram.md) §8. Exact match, no shift.
- **`AOD_SETUP`, 1020 bytes** — the variable [`../../acpi-bridge.md`](../../acpi-bridge.md)
  reported as *non-existent*, and later created by hand as **1020 zero bytes**
  for the `AOD_SETUP` SMI probe. The firmware's own definition of it is 1020
  bytes. Same size, independently.

## Why the off-default offsets were hard to name

`setup-offdefault-named.txt` crosses the eleven off-default `Setup` bytes against
the IFR. Most of them land on entries that **have no menu prompt at all** (hidden
or derived), or on AMI questions with an empty prompt string (StringId `0`):

```
off=3    00/01  no IFR question at this offset
off=4    00/01  hidden numeric question
off=21   01/00  hidden numeric question
...
off=316  01/00  "reporting of battery remaining time from the BIOS to the OS"
```

That is the real explanation for why toggling menu items barely named any of
them: several are not menu items. The IFR says so directly, instead of it being
inferred from a failed experiment.

## Method

The AMI/Aptos packages here do **not** use the standard HII package header
(`u32 Length` + `u16 Type`); theirs is `u24 Length + u8 Type`, which is why
`IFRExtractor-RS` v1.6.1 lists the packages but extracts nothing from them. The
string blocks are `0x14` (UCS2, `\0\0`-terminated) rather than the spec's `0x20`.

- `scan.py` — first test: varstore GUIDs + menu strings in ASCII *vs* UTF-16.
- `dump_setup_ifr.py` — the HII parser (string blocks + IFR questions).
- `ifr_map.py` — maps every module above to `offset -> option name`.
- `ifr-map-all.txt`, `setup-offdefault-named.txt` — the output.

Tooling (downloaded, not versioned): `tools/uefiextract` (LongSoft/UEFITool
A75), `tools/ifrextractor` (kept for reference). Reproduction:

```bash
sudo cp /boot/EFI/HP/BIOS/Current/088D1.bin evidence/ifr-static/088D1.bin
cd evidence/ifr-static && ./tools/uefiextract 088D1.bin
python3 ifr_map.py "088D1.bin.dump/1 4F1C52D3-…/0 9E21FD93-…/0 EE4E5898-…/1 Volume image section/0 5C60F367-…"
```

## Applying a change

`bridge.py` resolves an option name to its offset and writes the two `.dat`
files `dmpstore` needs (the change and a fresh revert) — it never applies them:

```bash
BRIDGE_OUT=out python3 bridge.py build AMD_PBS_SETUP "USB CAMERA=0"
```

The pre-boot apply (with an automatic revert if the change stops the machine
booting) lives in [`bridge/`](bridge/) — scripts + watchdog design + a QEMU/OVMF
rehearsal that exercises the real `.dat` files against OVMF's variable store.
Validated there: apply-then-arm, and revert-on-unconfirmed-armed.

## The HP NVRAM layer

Two more GUIDs hold HP's own state, separate from the setup store: `0ee72c08`
(42 variables — UI hiding, TPM/security flags, boot, and command channels) and
`206bc44a` (`HPSetupData`/`NewHPSetupData`/`HPAmiTse`/…). All 47 are immutable
from Linux. Full inventory: [`hp-nvram-layer.md`](hp-nvram-layer.md).

## AOD_SETUP is the AMD Overclocking menu

One of the four mapped varstores, `AOD_SETUP` (1020 B), turns out to be the
**AMD Overclocking menu** — PBO, PPT/TDC/EDC, custom CPU/GFX frequency/voltage,
and Curve Optimizer — and it is read **at POST** by `AodPei`, not only by the
`\AOD` SMM handler. → [`aod-setup.md`](aod-setup.md).

## What this does not change

Reading the IFR names options; it does not unlock them. The Curve Optimizer is
still refused by the SMU, the AMD CBS power menu is still inert, and the flash
is still PSS-signed and Sure Start-guarded. This is leverage on *knowing what
each `Setup` byte means*, not on *what the machine will let you set*.
