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

## The OS can reach the TEE — the driver is right there

```
$ lspci -nn | grep -i encryption
07:00.2 Encryption controller: AMD Cezanne Platform Security Processor [1022:15df]

$ dmesg | grep -i ccp
ccp 0000:07:00.2: ccp: unable to access the device: you might be running a broken BIOS.
ccp 0000:07:00.2: tee enabled
ccp 0000:07:00.2: psp enabled

$ modinfo amdtee   ->  .../drivers/tee/amdtee/amdtee.ko.zst   (installed)
$ lsmod | grep amdtee    -> not loaded
$ ls /dev/tee*           -> does not exist
```

The AMD-TEE driver is installed but unbound. Loading it would create `/dev/tee0`
and let the OS open sessions to the TAs — the world `DRIVER_ENTRIES` lives in.
There is also an ACPI node for it (dmesg shows `\TAAD.RTWT` / `\TAAD._GRT`). This
is the **one OS-reachable door into the PSP**, and it is closed today only
because nobody loaded the driver.

## What this changes for the project

- **The PSP is no longer a black box.** Its modules are named, their ISA is ARM,
  and the debug-unlock flow is readable. That is the starting point for the one
  purely-software route to changing firmware: a bug reachable from the host.
- **Two candidate surfaces are now concrete.** The AMD-TEE (`amdtee` →
  `/dev/tee0`) is reachable today; and `DEBUG_UNLOCK` is a small module that
  parses attacker-shaped input and already worried about an overflow.
- **It is still a map.** Nothing here is a vulnerability, and nothing here
  writes. The next step is to open one of the two surfaces and read what it
  validates — the same method used on the SMU.

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
