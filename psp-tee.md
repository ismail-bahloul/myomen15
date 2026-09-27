# The PSP is a GlobalPlatform TEE (HP OMEN 15-en1xxx)

[`psp-firmware.md`](psp-firmware.md) opened the SMU. This opens the *other*
processor on the same image: the **Platform Security Processor**, whose directory
`psptool` already lists — and it turns out to be a GlobalPlatform TEE on an ARM
Cortex-A5, with named Trusted Applications, one of which is the secure-debug
unlock. This is the map, not a finding: no bug is claimed here.

## The module map

`psptool -X -d 1` extracts the PL2 directory; the modules are (raw stored form,
PSP header included):

| Module | Size | ISA | What it is |
|---|---|---|---|
| `PSP_FW_BOOT_LOADER` | 67776 | ARM | the PSP boot loader (`0.11.0.85`) |
| `PSP_FW_TRUSTED_OS` | 103280 | ARM | the TEE OS (`0.11.0.85`) |
| `PSP_BOOT_TIME_TRUSTLETS` | 131328 | ARM | TAs loaded at boot |
| `DRIVER_ENTRIES` | 124784 | ARM | the **AMD-TEE** interface |
| `DRTM_TA` | 24832 | ARM | a **DRTM** Trusted App |
| `DEBUG_UNLOCK` | 8448 | ARM | the **secure-debug unlock** module |
| `SEC_GASKET` | 11904 | ARM | a service gasket |
| `TOS_SECURITY_POLICY` | 7056 | data | policy blob (no strings) |
| `TOKEN_UNLOCK` | 4096 | — | **4096 zero bytes** |
| `SEC_DBG_PUBLIC_KEY` | 1088 | — | the secure-debug signing key |

The GlobalPlatform nature is in the strings. `DRIVER_ENTRIES` carries
`gpd.tee.deviceID`, `gpd.tee.apiversion`, `AMD-TEE Global Platform API`,
`gpd.tee.trustedStorage.antiRollback.protectionLevel`, `gpd.tee.cryptography.ecc`;
`DRTM_TA` carries `amd.dr.driverID`, `gpd.ta.appID`, `amd.ta.fwtype`,
`amd.fw.SecPatchLevel`. So the PSP is a TOS plus TAs — the same world the fTPM
lives in.

## The boot verifier is named, in plain text

The module whose job is to decide what firmware may run is `PSP_FW_BOOT_LOADER`,
and it says so itself. Its own strings are the secure-boot chain, in order:

```
Bootloader C entry start...
GetPspFwHeader() start...EntryType=0x%X
PSPDirectorySearch()::Enter-EntryType =0x%04X
load_bios_l1_directory failed Status = 0x%x
load_psp_l2_directory failed Status = 0x%x
set_spirom_aperture_ex failed Status = 0x%x
load_validate_bios_l2_directory failed Status = 0x%x
Detected 2nd level entry for HVB validation on BIOS signature
ReadAndCopyRTMSignature::Signature Not Found
Loading SMU FW to SRAM Start... / Loading MP2 FW start...
RpmcDeriveRootKey: CryptoSHAOTP 256 returned %X
Soc is secured ! / Soc is nonsecured !
system cannot recover from this point, brick it
```

So the chain parses the PSP directories, loads the BIOS L1 / PSP L2 directories,
and then **"loads and validates the BIOS L2 directory" with HVB (Hardware
Validated Boot) signature validation** — the exact gate behind "you cannot
modify the firmware on this machine", named and placed. `ReadAndCopyRTMSignature`
handles the reset-image signature; `CryptoModExp` is RSA modexp;
`DeriveKeyUsingPRF` + `CcpHmacSha256` is the key derivation; RPMC keys and the
monotonic counter are the replay protection.

The generic RSA primitive (PKCS#1 v1.5 DER headers + SHA-1/256/384 OIDs) lives in
`PSP_BOOT_TIME_TRUSTLETS` and `DRIVER_ENTRIES`, next to the HMAC keys —
`DRIVER_ENTRIES` ties them to this repo's own objects: *"HMAC Signature Key for
Wrapped iKEK saved in SPI-ROM"*, *"for signing APOB data"*, *"for PSP Data saved
in DRAM"*.

Full string map: [`evidence/psp-boot-verifier.txt`](evidence/psp-boot-verifier.txt).

**Reaching the verifier's code is the next session.** Both attempts to jump from
those strings to the instructions failed, and for a reason worth stating: the
module is **relocated** at load (its strings are never absolute literals, and no
shared base emerges), so a flat disassembly cannot resolve its data references.
That needs Ghidra plus the module's relocation data — the same wall `DEBUG_UNLOCK`
hit. The map is solid; the code is not faked.

> **Correction (later).** The wall was not relocation. The two labels left
> un-mapped here (`load_validate_bios_l2_directory`, `HVB validation`) were
> referenced by Thumb `ADR` all along — PC-relative, which relocation does not
> touch. Ghidra had simply not disassembled ~48% of the mixed ARM/Thumb module.
> They are resolved to `FUN_00001554`/`FUN_00002538` in
> [`psp-boot-verifier.md`](psp-boot-verifier.md).

## `DEBUG_UNLOCK` — the secure-debug path, named

It is a standalone ARM module (a real boot stub at `0x100`: `ldr sp` → `blx`
init → `blx` main → `b .`), and its own strings spell out the flow:

```
DBG_UNLOCK_MODULE::FAIL - Svc_GetDebugUnlockInfo Status =
DBG_UNLOCK_MODULE::Received UnlockMode =
DBG_UNLOCK_MODULE::FAIL - UnlockNegotiation with HdtError =
DBG_UNLOCK_MODULE::FAIL - SecureUnlock with HdtError =
DBG_UNLOCK_MODULE::Securely UNLOCKED
DBG_UNLOCK_MODULE::FAIL - Failed to Lock ASIC
DBG_UNLOCK::FAIL - Stack Buffer Overflow
```

Two things matter. The flow is legible end to end — a service, a negotiation,
then a secure unlock — which is AMD's secure-debug mechanism made readable. And
**AMD's own code checks for a stack buffer overflow there**: a hand-written guard
means the input was known to be attacker-influenced, which is where a bug hunt
would start.

`TOKEN_UNLOCK` is 4096 zero bytes — **no secure-debug token is provisioned** on
this machine — and `SEC_DBG_PUBLIC_KEY` (`key_usage = unknown_key_usage(3)`) has
nothing paired with it in the image.

## The OS can reach the TEE — and does

```
$ lspci -nn | grep -i encryption
07:00.2 Encryption controller: AMD Cezanne Platform Security Processor [1022:15df]

$ dmesg | grep -i ccp
ccp 0000:07:00.2: ccp: unable to access the device: you might be running a broken BIOS.
ccp 0000:07:00.2: tee enabled
ccp 0000:07:00.2: psp enabled

$ sudo modprobe amdtee        # rc=0
$ lsmod | grep amdtee ; ls -l /dev/tee0
amdtee 32768 0
crw------- 1 root root 510, 0 ... /dev/tee0
$ cat /sys/class/tee/tee0/implementation_id
2                            # TEE_IMPL_ID_AMD = 2
```

So it is not theoretical: loading the driver binds, `ccp` takes a dependency, and
the OS ends up with an **AMD-TEE** handle. (Fully reversible: `rmmod amdtee`
removes `/dev/tee0`.) There is also an ACPI node for the TEE world (dmesg shows
`\TAAD.RTWT` / `\TAAD._GRT`).

## The TAs are firmware files the OS hands to the PSP

The driver's own strings (`copy_ta_binary`, "failed to load firmware %s") and the
firmware directory say what happens next:

```
$ ls /lib/firmware/amdtee/
773bd96f-b83f-4d52-b12dc529b13d8543.bin.zst   -> amd_pmf_v3.bin.zst
f29bb3d9-bd66-5441-afb88acc2b2b60d6.bin.zst   -> amd_pmf_v3_1.bin.zst
```

The file *name* is the TA UUID (the driver formats
`%08x-%04x-%04x-%02x%02x%02x%02x%02x%02x%02x%02x.bin`), and the *content* is a
**PSP module** — the very same `$PS1` header and trailing signature as every
module in the PSP directory:

```
$ zstdcat /lib/firmware/amdtee/773bd96f-….bin.zst | xxd | head -2
00000000: 00 00 00 00 ...                (16 bytes)
00000010: 24 50 53 31  40 30 00 00       "$PS1", size_signed = 0x3040
… and it ends in ~0x200 bytes of high-entropy signature
$ strings -> "AMD PMF Application", gpd.ta.appID, gpd.ta.stackSize, gpd.ta.heapSize, …
```

So the flow is: **the OS supplies a code blob, the PSP loads it.** The only thing
between an attacker-controlled file and code in the PSP is the **signature check
on that blob** — the same verifier as everything else, now fed bytes the host
chose. That is a sharper surface than `DEBUG_UNLOCK`: a parser of attacker-shaped
input that must get the signature check right *before* it executes anything.

## What this changes for the project

- **The PSP is reachable, for real.** The OS has a TEE handle, and the TEE
exchange with the PSP is a **module-loading path**: the host writes a file, the
PSP validates and runs it. That is the software route toward code in the PSP.
- **`DEBUG_UNLOCK` was tried and needs reloc-aware tooling.** The module is
relocated at load (no absolute string references, unresolved outside calls), so a
linear disassembly is not trustworthy; it wants Ghidra plus the relocation info
— a session of its own, noted rather than faked.
- **It is still a map.** No vulnerability is claimed. What is new is that the
host→PSP door is identified, opened, and shown to be a *verifier*.

## Reproducing

```bash
pip install psptool capstone
psptool -X -d 1 -o /tmp/pspmods 088D1.bin      # extract the PSP directory
strings /tmp/pspmods/*DRIVER_ENTRIES* | head
strings /tmp/pspmods/*DEBUG_UNLOCK* | grep -i unlock
```

Raw characterisation output: [`evidence/psp-tee-modules.txt`](evidence/psp-tee-modules.txt).

## Related

- [`psp-firmware.md`](psp-firmware.md) — the SMU, the other processor on this image.
- [`chipsec-recon.md`](chipsec-recon.md) — the FCH / SPI / Sure Start layer above.
- [`firmware-limits.md`](firmware-limits.md) — what is signed, and by what.
