# The PSP firmware verifier, decoded

[`psp-tee.md`](psp-tee.md) named the secure-boot chain from `PSP_FW_BOOT_LOADER`'s
own strings but stopped at the code: the module is **relocated at load**, so no
string is an absolute literal and a flat disassembly cannot resolve it. That was
the honest wall. This session got past it with Ghidra and the module's own
control flow, and the result is not a string list any more — it is the
**verification logic itself**, function by function, down to the RSA modexp.

The short version: firmware is checked with **RSA-2048 / SHA-256, PKCS#1 v1.5,
over the *stored* (compressed) body**, with the key material sourced from
firmware and a **keyed hash** layered on top, plus an **anti-rollback** counter.
That is the gate, and now it is read rather than inferred.

Method: `PSP_FW_BOOT_LOADER` (`0.11.0.85`, 67776 bytes) imported into Ghidra as
`ARM:LE:32:v7`, base `0`, auto-analysed (260 functions). Scripts and raw output:
[`evidence/psp-boot-verifier/`](evidence/psp-boot-verifier/). All addresses below
are module-relative.

## The call chain, top to bottom

```
FUN_000073e8   PSP command dispatcher (no resolved callers -> relocated entry)
  case 0x52:   FUN_00003624(&mode);  FUN_000048c4(mode)
FUN_00003624   boot mode from ASF_STATUS + the ACPI PM1 control block
FUN_000048c4   "load firmware" phase (once-only guard), mode 0/3/4/5:
                 FUN_00005194(...)                      load image into DRAM -> base
                 FUN_0000aa48(0, 0x08,  base,        0x40000, 2,0,0)  # SMU_OFFCHIP_FW
                 FUN_0000aa48(0, 0x12, base+0x40000, 0x40000, 2,0,0)  # SMU_OFF_CHIP_FW_2
                 FUN_00007e84 / FUN_00006f68(3)
FUN_0000aa48   per-entry load: GetPspFwHeader, then validate
  FUN_00003eb8  "GetPspFwHeader": FUN_0000539c = PSPDirectorySearch(2, EntryType)
                                   FUN_0000e108 = spiPspRead (0x100-byte header)
                                   FUN_00008788  header entry-type byte check
  FUN_0000b8ac  validate, THEN decompress
FUN_0000bad8   signature core
  FUN_0000ca04  mapSpiRomAperture: map the stored body out of SPI
  FUN_00002b2c  keyed comparison of body vs. signature (key table, op selector 9)
FUN_0000ef6c   generic verify (mode 1)
  FUN_0000302c  hash context, keyed with key #0 (FUN_00003e50)
  FUN_00002bac  PKCS#1 v1.5: FUN_000029f8 = RSA modexp, FUN_00002d3c = algo table,
                FUN_00003234 = digest compare
FUN_0000317c   zlib decompress           (runs AFTER verification)
FUN_0000a61c   anti-rollback SVN table    (header+0x4c < min  ->  status 0x96)
```

There is a second, independent entry: `FUN_000083b0` (also called from
`FUN_000073e8`) verifies a **signed blob already in DRAM** (mode `2`) instead of
reading one out of SPI — see *The in-DRAM path* below.

## Verify first, decompress second

`FUN_0000b8ac` is the decision. Its shape is the finding: it checks the
signature, and only afterwards inflates the body.

```c
// FUN_0000b8ac(header, body, size, key_ctx, mode)
if (*(int *)(header + 0x48) == 1) {          // 0x48 = compressed flag
    log("Comp Image Found CompImageSize ...", *(u32 *)(header + 0x54));
    uVar3 = (*(int *)(header + 0x54) + 0x1f) & ~0x1f;   // align(zlib_size, 32)
    if (size < uVar3)                       return 3;
    if (size < *(u32 *)(header + 0x50))     return 3;   // size_uncompressed
    body = body + (size - uVar3);           // signature sits at the END
}
...
iVar2 = FUN_0000bad8(header, body, uVar3, key_ctx, mode);   // <-- RSA verify
if (iVar2 != 0) return iVar2;
log("starting validation step...");
...
log("Checking if need to decompress...");
if (*(int *)(header + 0x48) == 1 && /* not wrapped */) {
    log("Decompressing verified image...");
    FUN_0000317c(body, dest, *(u32 *)(header + 0x54), size, &out_len);  // zlib
    if (*(int *)(header + 0x50) != out_len) return 0x47;   // size mismatch
}
return FUN_0000a61c(rollback_table, header);   // anti-rollback
```

Header fields, as read by the code: `+0x14` size_signed, `+0x18` a flag,
`+0x48` compressed, `+0x50` size_uncompressed, `+0x54` zlib_size, `+0x60`
version (printed), `+0x6c` wrapped-image total size, `+0x78` bit0 wrapped,
`+0x7c` entry-type byte, `+0x4c` the security/revision number compared by the
anti-rollback step.

This is the same fact [`psp-firmware.md`](psp-firmware.md) reached from the other
side: the signature is over the **compressed stored body**, which is exactly why
`psptool`'s default (it signs the *decompressed* body) reported `veri-failed`.

## The signature core, `FUN_0000bad8`

`FUN_0000bad8(header, sig, size, ctx, mode)` maps the body out of SPI and verifies
it:

```c
iVar2 = FUN_0000ca04(*DAT_0000bc68 + ctx + 0x100, uVar4);   // map body
if (iVar2 == 0) return 10;
log("FW type:0x%02X version:0x%08X", *(u8 *)(header+0x7c), *(u32 *)(header+0x60));
if (((sig + 0x1f) & ~0x1f) != sig || ((size + 0x1f) & ~0x1f) != size) return 6; // 32B align
if (size < uVar4) return 3;
// ... else-branch, the boot case:
iVar3 = FUN_00002b2c(iVar2, sig, (uVar4 + 0x1f) & ~0x1f);   // verify stored body
```

Two things to note.

- **`FUN_0000ca04` is `set_spirom_aperture_ex`.** It programs a block of registers
  and issues `DataSynchronizationBarrier` / `InstructionSynchronizationBarrier`
  before returning the mapped address — the loader mapping SPI ROM into its
  address space. The body it hashes is the bytes **as stored in the flash**, not a
  re-encoded copy.
- **`FUN_00002b2c` is the boot-time comparator.** It calls `FUN_00003e50(0, …)` to
  fetch **key #0** from a three-entry key table, runs a crypto op (selector `9`),
  feeds the body and the expected value into a hash context
  (`FUN_00002018(0,1,body,…)`, `FUN_00002018(2,1,sig,…)`) and finalises
  (`FUN_00003158`); failure returns `0x1a`. So the body hash is **keyed by a
  symmetric key baked into the firmware**, not just a plain digest — a second lock
  behind the RSA one. (The precise CCP op behind selector `9` is not resolved here;
  it is recorded as unresolved, not guessed.)

## The RSA primitive, `FUN_00002bac`

The generic verifier `FUN_0000ef6c` (mode 1) reaches the full PKCS#1 v1.5 path.
`FUN_00002bac` is textbook, and reading it explains every constant:

```c
if (param_4 != 0x100 && param_4 != 0x200) return 5;   // 2048- or 4096-bit key
FUN_00002d3c(param_8, auStack_3c, &local_44);          // algo table -> digest length
if (local_44 != param_2) return 4;                     // expected digest length
for (uVar2 = 0; uVar2 < param_4; uVar2++)              // byte-reverse the signature
    *(iVar4 + uVar2) = *(sig + (param_4 - uVar2) - 1);
FUN_000029f8(param_5, param_6, local_2c, param_4, iVar4, iVar1, 0);   // RSA modexp
for (...) pbVar5[uVar2] = <reverse back>(iVar1);       // byte-reverse the result
if (pbVar5[0] < 0x80 && pbVar5[param_4-1] == 0xbc) {   // PKCS#1 v1.5 marker
    FUN_00003234(pbVar5 + ..., local_44, iVar1, ..., param_8);   // compare digest
    ... xor-unmask, extract data, FUN_00003122 (final hash), FUN_0000cdc4 (copy out)
}
```

- `FUN_000029f8` = **`CryptoModExp`** (the string names it): the RSA public
  operation `s^e mod n`.
- `FUN_00002d3c` = the **algorithm table**: case 3 → `0x20` (SHA-256), case 4 →
  `0x30` (SHA-384), and SHA-1/224/512 alongside. `FUN_0000ef6c` picks key length
  `0x100` → SHA-256, `0x200` → SHA-384.
- `FUN_00003234` = the **digest comparison**; `FUN_00003122` finalises the payload
  hash.

So the machine's firmware gate is a stock, correctly-implemented RSA-2048
SHA-256 PKCS#1 v1.5 verify. There is no shortcut in the algorithm.

## Where the keys come from

`FUN_00003e50(index, &out)` is a **key table** of three entries:

```c
iVar1 = DAT_00003e78 + param_1 * 0x1c;
*param_2 = *(int *)(iVar1 + 8) + *(int *)(iVar1 + 0xc) * 0x20;
```

In the mode-1 path, `FUN_0000b8ac` reads the **RSA public key material out of SPI**
before verifying (`FUN_0000e108(DAT_0000ba88, ctx + size + 0x100, len, 0x200, 0)`
— a 0x200-byte `spiPspRead`). The key is not derived from the host and not
supplied by the OS; it is read from the flash region beside the entry. That is
what "the root of trust is in ROM, not on the disk" means at the instruction
level.

## Anti-rollback, `FUN_0000a61c`

The last step of `FUN_0000b8ac` walks a table at `DAT_0000bad4` (entries of `0x20`
bytes, count at `+0x100`), matches the entry's type byte against `header+0x7c`, and:

```c
if ((iVar1 == 0) && (*(uint *)(param_2 + 0x4c) < uVar3)) iVar1 = 0x96;
```

`header+0x4c` must be **at least** the recorded minimum for that entry type, and a
"forbidden type" list (`DAT_0000a6a0`, 0xf ids) is checked too. Error `0x96` is
**anti-rollback**: an older-but-signed image is refused. This is the software half
of what the RPMC monotonic counter enforces in hardware.

## The in-DRAM path, `FUN_000083b0`

Not everything is read from SPI. `FUN_000083b0(type, flags, buf, &size)` verifies a
blob the previous stage already placed in DRAM:

```c
if (*param_4 < 0x100) return 3;                     // need header + body
FUN_0000148c(param_1, param_2, &local_28, 0, &puStack_24, 0);
FUN_0000dea0(param_3, local_28, 0x100, 0x100, 0);   // copy 0x100-byte header
if (*(byte *)(param_3 + 0x7c) == (param_1 & 0xff)) {
    uVar2 = FUN_0000b8ac(param_3, param_3 + 0x100, *param_4 - 0x100, local_28, 2);
    ...
    *param_4 = (header+0x48 == 1) ? *(u32*)(header+0x50) : *(u32*)(header+0x14);
}
```

Mode `2` is the branch in `FUN_0000b8ac` that asks **`FUN_0000b760`** for the
expected digest. `FUN_0000b760` searches a bundled list for the entry whose
16-byte id at `header+0x38` matches, and returns a descriptor — i.e. the
**expected hash lives in the loader's own tables**, keyed by the entry's identity
field, and the RSA key is read from SPI (`0x200` bytes) as in the SPI path. Same
cryptography, different body source.

## The dispatcher, and the one non-verifier branch

`FUN_000073e8` is the PSP **command handler**: `param_1` selects a command
(`0x2e`, `0x2f…0x36`, `0x4e`, `0x50`, `0x51`, `0x52`, `0x59`, `0x5a`, `0x5d`,
`0x60`…). Most are memory/aperture services — `0x50` maps SMN
(`"MAP_SMN_access_blocked Addr %08x"`), `0x51` unmaps, `0x35`/`0x69` read/write
registers, and so on. Command `0x52` is the one that enters the firmware load:

```c
if (param_1 == 0x52) {
    uVar11 = FUN_00003624(&local_40);
    if (uVar11 == 0) FUN_000048c4(local_40);
}
```

and `FUN_00003624` derives that mode from the **ACPI PM1 control block** and
`ASF_STATUS` (`"AcpiPm1CntBlkX00: 0x%x"`), i.e. the boot/resume S-state decides
which entries get validated and brought up. `FUN_000048c4`'s cases `0/3/4/5` load
**`SMU_OFFCHIP_FW` (EntryType `0x08`)** and **`SMU_OFF_CHIP_FW_2` (EntryType
`0x12`)** at `base` and `base+0x40000` — the very 256 KiB images
[`psp-firmware.md`](psp-firmware.md) reversed. The firmware-verification chain is,
concretely, the chain that gates the SMU/MP1 image this repo has been reading.

## The wrapped/encrypted path, `FUN_00003a20`

When `header+0x78 & 1` is set, `FUN_0000b8ac` takes a different branch,
`FUN_00003a20`, which reads a **wrapped key blob** from SPI (a length between the
key-aperture bound and `0x841`), verifies *that* blob with `FUN_0000ef6c`, derives a
key (`FUN_0000aea0`, `FUN_0000d7d4`), then verifies the image against the derived
key. This is the confidential-image path: the signature is checked with a key that
itself arrived signed. It is a second, longer chain with more parser surface — and
it is entered by a header flag, i.e. by attacker-influenced data **before** the
signature is checked.

## What this settles, and what it does not

Settled, at instruction level:

- The BIOS/SMU firmware gate is **RSA-2048 / SHA-256, PKCS#1 v1.5, over the stored
  body**, verified before decompression, with the key read from SPI and a keyed
  hash and an anti-rollback counter layered behind it. There is no bypass in the
  logic; the algorithm and its constants are correct.
- The verifier is fed from **three** sources: the SPI directory (mode 1), an
  in-DRAM signed blob (mode 2), and a wrapped-key path (`header+0x78 & 1`). The
  last two are the ones a host or a previous stage can shape.

Not settled (recorded, not guessed):

- The exact CCP operation behind selector `9` in `FUN_00002b2c` is not resolved;
  it is a keyed hash with key #0, but the primitive name is not pinned.
- After **load-time relocation** the loader's strings have no absolute references,
  so a few names (`load_validate_bios_l2_directory`, `HVB validation`) still have
  no xref. The chain above is followed from `FUN_0000b8ac`/`FUN_000029f8`/
  `FUN_00003234`, which *do* resolve; the string-to-code mapping for those two
  remaining labels is the next session.

For the project's standing question — *can the firmware be modified?* — this is the
answer from the code: **not through the verifier.** The only software route left is
a **bug in the parsers that run before the check** (the wrapped-image reader, the
header/`GetPspFwHeader` path, the in-DRAM blob reader) or the secure-debug unlock
(named in [`psp-tee.md`](psp-tee.md); no token is provisioned here). Everything
else is the hardware route: fault injection (glitch/EMFI) on the PSP's SPI read or
on the modexp comparison, which is failure *of* this code, not a flaw *in* it.
That is a different experiment, and it is not claimed here.

## Reproducing

```bash
# 1. extract the PL2 modules (raw stored form, header included)
pip install psptool
psptool -X -d 1 -o /tmp/pspmods 088D1.bin

# 2. import the boot loader into Ghidra as ARM:LE:32:v7, base 0, and let it analyse
analyzeHeadless <proj> PSPBL -import /tmp/pspmods/d00_e00_PSP_FW_BOOT_LOADER~0x1_0.11.0.85 \
    -processor ARM:LE:32:v7 -loader BinaryLoader -loader-baseAddr 0

# 3. run the decompilation scripts (addresses are module-relative)
analyzeHeadless <proj> PSPBL -process '…PSP_FW_BOOT_LOADER…' -noanalysis \
    -scriptPath evidence/psp-boot-verifier/ghidra -postScript Dec8.java
```

Decompiled chain: [`evidence/psp-boot-verifier/decompiled.txt`](evidence/psp-boot-verifier/decompiled.txt).
Scripts: [`evidence/psp-boot-verifier/ghidra/`](evidence/psp-boot-verifier/ghidra/).

## Related

- [`psp-tee.md`](psp-tee.md) — the PSP module map and the string-level chain this decodes.
- [`psp-firmware.md`](psp-firmware.md) — the SMU/MP1 image this chain validates, and the `psptool` layout bug it explains.
- [`firmware-limits.md`](firmware-limits.md) — what is signed, and by what.
