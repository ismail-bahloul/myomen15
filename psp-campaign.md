# The PSP campaign: what was established

This is the hub for the firmware-security work in this repo — four pages deep —
and its verdict. It answers one question: **on this machine (HP OMEN 15-en1xxx,
Cezanne, BIOS F.30), can the firmware be modified?** The answer, shown rather than
asserted, is **not through the verifier, by software.**

The pages it draws together:

- [`psp-tee.md`](psp-tee.md) — the map: the PSP is a GlobalPlatform TEE, and the modules.
- [`psp-boot-verifier.md`](psp-boot-verifier.md) — the boot-time verifier, decoded to instructions.
- [`psp-tee-runtime.md`](psp-tee-runtime.md) — the runtime TEE: the second verifier, the host ingress, the TA loader.
- [`psp-tee-empirical.md`](psp-tee-empirical.md) — the gate, observed on hardware.
- [`psp-firmware.md`](psp-firmware.md) — the SMU/MP1 image the gate protects, and the `psptool` bug it explains.

## The three modules, and the gate

The PSP runs three reachable modules (imported into Ghidra, `ARM:LE:32:v7`, base 0):

| module | size | functions | role |
|---|---|---|---|
| `PSP_FW_BOOT_LOADER` | 67776 | ~260 | the boot verifier + a command handler |
| `DRIVER_ENTRIES` | 124784 | 764 | the AMD-TEE driver: the host-facing GP API |
| `PSP_FW_TRUSTED_OS` | 103280 | 111 | the TEE kernel: TA loader, `svc 0xf2` syscalls |

The gate itself, decoded to instructions, is:

- **verify first, decompress second** — `FUN_0000b8ac` runs the signature check
  *before* it inflates the body;
- the signature is **RSA-2048 / SHA-256, PKCS#1 v1.5, over the stored
  (compressed) body** — `FUN_0000bad8` → `FUN_00002b2c`, and
  `FUN_0000ef6c` → `FUN_00002bac` (`FUN_000029f8` = `CryptoModExp`);
- the key comes from **SPI** via a three-entry table (`FUN_00003e50`), with a
  **keyed hash** layered behind it;
- an **anti-rollback** counter at `header+0x4c` refuses older-but-signed images
  (`FUN_0000a61c`, error `0x96`).

This is a stock, correct PKCS#1 v1.5 verify. There is no shortcut in the algorithm,
and the same design (signature over the **stored** bytes) is what makes `psptool`'s
default `veri-failed` a one-line bug rather than a mystery
([`psp-firmware.md`](psp-firmware.md)).

## Reachable, and bounded

The verifier is not unreachable — the question was followed to the bytes:

- **Boot command `0x2d`/`0x32`** routes a caller-supplied blob (mode 2) into
  `FUN_0000b8ac`. The buffer, however, is resolved from the PSP's own **region
  table** (`FUN_0000148c`) and range-checked (`FUN_0000738c`).
- **Runtime**: driver entry `FUN_000077e0` → command dispatcher `FUN_0000dbe0` →
  load command `0x3130` → `FUN_000106dc` → `FUN_0000f7a0` → RSA. The
  `(address,size)` pairs are validated by `FUN_00011604` (page-aligned, 16-byte
  integrity tag) and `FUN_00007730` (page-range, traps into the TOS) first.
- **Sweeps**: all 57 boot-loader commands and all 181 runtime handlers were
  classified. Every handler that maps host memory verifies it; every
  address-taking command is confined to a blacklist / fixed aperture / checked
  range.
- **The TOS TA loader** (`FUN_00016748`) caps the input at 1 MiB, keys on the
  header type (`"TA"`/`"DR"`), requires `driverID ∈ {2,3,4}`, and bounds the memory
  plan (each region `< 0x401` pages, total below the aperture).

No unbounded length or offset was found on any of these paths.

## Observed, not just inferred

The one verifier the OS can drive is the AMD-TEE TA path
(`/dev/tee0` → `TEE_IOC_OPEN_SESSION` → the PSP validates the blob). Flipping a
single byte **anywhere** in the vendor TA — the prefix, the header, the body, or
the signature itself — moves the PSP's verdict from `0x33` to `0x34`
([`psp-tee-empirical.md`](psp-tee-empirical.md)). The `0x34` is a distinct code
from the pristine `0x33`, so the whole-module integrity check provably runs
**before** the load. The static model holds on silicon.

## Verdict

**Software cannot modify the firmware on this machine.** The firmware gate is a
correct, standard signature check; the two host-reachable entry points into it
(boot and runtime) and the TA loader are all bounded; and the one OS-reachable path
was exercised and rejects a one-byte change. There is no bypass in the logic to
find, and the parse surfaces a bug would need are not there to our reading.

An important qualifier, stated because it changes what "reachable" means: the
command interfaces are the **PSP mailbox**, and no Linux driver exposes those
service ids to userspace. The actor who could issue them is **pre-boot / SMM
level** (AGESA, or a DXE/SMM module), not an unprivileged process. The OS's own
door (`/dev/tee0`) is the TA path — and even the pristine vendor TA does not load
from it here (`0x33`), consistent with the TEE ACPI `\TAAD` not being provisioned.

What remains is **hardware**: fault injection (glitch/EMFI) on the PSP's SPI read
or on the modexp comparison. That is failure *of* the code, not a flaw *in* it —
a different experiment, with a real cost and brick risk on a single machine, and
**not attempted or claimed here**.

## The honest limits of this conclusion

- It rests on **static reading** of three modules plus **one empirical
  differential**. The differential had no *accept* baseline (the pristine TA is
  refused `0x33` for a platform reason), so it demonstrates "tampering changes the
  verdict", not "good is accepted".
- A few items are **recorded and not resolved**: the CCP primitive behind the
  keyed-hash selector `9`; the two relocator-hidden labels
  (`load_validate_bios_l2_directory`, `HVB validation`) in the boot loader; the
  non-RSA (ECC) dispatcher ops.
- "Exhausted" means *by this method*. It is not a proof that no bug exists — it is
  a claim that the paths checked are bounded, and the paths not yet read are
  enumerated.

## Related

- [`firmware-limits.md`](firmware-limits.md) — the wider firmware/hardware reference this belongs to.
- [`access-surface.md`](access-surface.md) — the machine-wide reachable-surface inventory.
- [`chipsec-recon.md`](chipsec-recon.md) — the FCH / SPI / Sure Start layer above the PSP.
