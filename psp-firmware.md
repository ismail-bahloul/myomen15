# The SMU firmware, in the clear (HP OMEN 15-en1xxx)

[`firmware-limits.md`](firmware-limits.md#three-of-the-four-encrypted-regions-are-now-identified)
ended its PSP-directory section with a `psptool` line it could not explain:

> `SMU_OFFCHIP_FW`, `PMU_CODE`/`PMU_DATA` ... `compressed, veri-failed(<keyid>),
> sha256_ok`. Likely `psptool` itself mis-slices the decompressed body against a
> `size_signed` field meant for the compressed one ... a `psptool` question, not
> a question about this machine's firmware.

It was half right and half wrong, and the wrong half was the interesting one.
This page settles it: **the SMU firmware was readable all along**, the
decompression was never broken, and `veri-failed` is a **one-line `psptool`
bug** — now identified exactly. The two SMU images and the PMU code/data are
extracted, with their hashes.

## The correction, in two parts

**1. The decompression is correct.** For every one of these entries,
`sha256(get_decrypted_decompressed_body())` equals the checksum stored in the
file header. So `sha256_ok` is real, and the plaintext is byte-exact what AMD
hashed. The guess that psptool "mis-slices the decompressed body" is not what
is happening; the decompression `psptool` performs returns the right bytes.

**2. `veri-failed` is `psptool`, not the file.** The RSA signature on a
compressed PSP entry is over `header + stored (compressed) body`. `psptool`'s
`HeaderFile.get_signed_bytes()` instead signs `header + decompressed body`. For
uncompressed entries those are the same bytes, which is why only the compressed
ones failed. One character-level change in
`psptool/header_file.py`:

```python
def get_signed_bytes(self) -> bytes:
    file_bytes = self.header.get_bytes() + self.get_decrypted_body()   # was get_decrypted_decompressed_body()
    return file_bytes[:len(self.header) + self.size_signed]
```

and every previously `veri-failed` entry verifies:

| Entry | stock psptool | with the one-line fix |
|---|---|---|
| `SMU_OFFCHIP_FW` | `compressed, veri-failed(96A0), sha256_ok` | `compressed, verified(96A0), sha256_ok` |
| `SMU_OFF_CHIP_FW_2` | `compressed, veri-failed(96A0), sha256_ok` | `compressed, verified(96A0), sha256_ok` |
| `PMU_CODE` / `PMU_DATA` | `compressed, veri-failed(4F75), sha256_ok` | `compressed, verified(4F75), sha256_ok` |

The fix is proven the same two ways the rest of this repo proves things: the
RSA-PSS check is run directly over *both* message layouts against the entry's
own certifying key (only `header + stored` passes — see `psp-firmware.py`), and
`psptool -E` is re-run with the patch and reverted, every entry flipping
`veri-failed` -> `verified`. Nothing else in the image changes.

So the firmware was never "verification-failed". It was **`psptool` verifying
the wrong bytes** — the same shape as the MSR `EIO` story in
[`msr-and-smm.md`](msr-and-smm.md), one layer up: a tool-side mistake read as a
hardware limit.

## What is now in hand

The plaintext, decompressed and hash-verified (`evidence/psp-firmware/fw-analysis.txt`):

| Component | Size | Version | sha256 |
|---|---|---|---|
| `SMU_OFFCHIP_FW` | `0x40000` (256 KiB) | `0.40.4A.0` | `fb1687f6…976d9ce0` |
| `SMU_OFF_CHIP_FW_2` | `0x40000` (256 KiB) | `0.40.4A.0` | `32339071…17f6e158` |
| `PMU_CODE` (inst 1 / 4) | `0x8020` (32 KiB) | `0.0.10.1` | `e4c15162…119a862a2` / `f996468a…a085d5ce` |
| `PMU_DATA` (inst 1 / 4) | `0x4020` (16 KiB) | `0.0.10.1` | `70a58cac…c4f1cf65` / `f15de9eb…c7e2f739` |

The two `$BHD`/`$BL2` copies are byte-identical. The `.bin` dumps are gitignored
(the repo's `*.bin` rule); the script regenerates them from the image in one
command.

`SMU_OFFCHIP_FW` starts with the SMU version the mailbox already reports on this
machine — `0x00404A00`, i.e. 64.74.0, exactly the `GetSmuVersion` reply in
[`smu-raw.md`](smu-raw.md). The firmware image and the live SMU agree, from two
independent sources.

## What the image looks like

`SMU_OFFCHIP_FW` is 256 KiB, and it is not uniform. Its 4 KiB-block entropy, and
what falls out of it:

- a small header (version, a few fixed fields);
- two high-entropy blocks early (`0x1000`–`0x4000`);
- a long **structured-data** stretch (`0x6000`–`0x1C000`) — at `0x12000`, a run
  of small ascending integers, the shape of a table, not code;
- a large homogeneous ~7.0 region from `0x1D000` to the end.

Entropy ~7.0 is code or packed data. It is **not** ciphertext (that would be
~7.99) and not a nested container: no zlib/gzip/lzma/zstd/lz4/bzip2 magic
appears anywhere in either SMU image.

## The architecture: no *Capstone* ISA — because the core is Xtensa

Disassembling the ~7.0 regions with every architecture Capstone models (ARM,
Thumb, ARM64, MIPS, PPC, RISC-V, x86, SuperH, M68K, ...) leaves them undecoded;
the best coverage any architecture reaches on the code-like windows averages
~1 %, and every 100 % hit is on the all-zero padding — a false positive.

The control is what makes that meaningful: this same image's own
`PSP_FW_BOOT_LOADER` and `PSP_FW_TRUSTED_OS` **are** ARM (Cortex-A5) and light
up unmistakably. Counting the Thumb-2 `push.w` prologue (`2d e9`) against a
byte-shuffled random baseline:

```
file                  observed   random-expected   ratio
psp_bl  (ARM control)      149            1.02     146x
psp_tos (ARM control)      124            1.57      79x
SMU_OFFCHIP_FW               1            4.00     0.2x
SMU_OFF_CHIP_FW_2            0            4.00     0.0x
PMU_CODE                     0            0.50     0.0x
PMU_DATA                     0            0.25     0.0x
```

No ARM64, x86-64 or MIPS prologue signature either. So the SMU/PMU images carry
**no signature of any instruction set Capstone knows** — which is exactly true,
and the reason is now known: the core is **Xtensa**, which Capstone does not
model. The evidence is below, and it is not statistical.

## The core is Xtensa

radare2's Xtensa plugin decodes the same regions cleanly, and the decoded
instructions are self-evidently Xtensa by their operands — the Xtensa-only
control-register and synchronisation instructions, in a coherent stream at the
boot region:

```
0x1e0  movi.n a2, 0       0x1e6  isync              ; Xtensa instruction-fetch sync
0x1e2  wsr.itlbcfg a2     0x1e8  l32r a2, <literal>
0x1eb  wsr.dtlbcfg a2     0x1f0  dsync              ; Xtensa load/store sync
0x1d1  dii a3, 0          0x1c7  bltu a3, a2, <loop> ; Xtensa disable-interrupt
```

`wsr.itlbcfg` / `wsr.dtlbcfg` / `isync` / `dsync` / `dii` have no equivalent in
any other ISA; their presence is decisive, not a fit statistic.

Two independent sources agree it is Xtensa, and neither is this repo:

- AMD's own firmware repository (`github.com/amd/firmware_binaries`) ships the
  Cezanne SMU firmware directly (`cezanne/PSP/TypeId0x08_SmuFirmware_CZN.csbin`).
  It is a `$PS1` entry, `compressed=1 encrypted=0 size_signed=0x40000`, and it
  decompresses to a 0x40000 body beginning `00404800 00404800` (version 64.72.0,
  twice) — the identical header shape to the 64.74.0 this machine's F.30 ships.
  That validates the extraction against an official artifact, not just psptool.
- The `bc250-collective/amd_smu_reverse_engineering` project describes the SMU of
  a related SoC as booting an Xtensa core. What matters more is that section
  below **re-derives the same dispatch structure by hand from this image**.

## `queue_dispatch`, located by hand

With Xtensa decoding, the message dispatcher falls out around `0xff8`. It is
recognisable by the status codes this repo already measured from the live SMU:

```
0x1026  extui a14, a10, 0, 8     ; message id = low 8 bits
0x103d  l16ui a9, a9, 252        ; per-queue message-count bound
0x1043  bltu a10, a9, <lookup>   ; id < bound -> has a handler
0x1048  movi a11, 254            ; 0xFE  (unknown command)
0x1058  addx8 a3, a10, a3        ; entry = handler_table + id * 8
0x105b  l32i.n a13, a3, 0        ; <- handler FUNCTION POINTER
0x1060  l8ui a5, a3, 5           ; <- config/guard byte at entry+5
0x10b4  callx8 a8                ; <- call the handler
0x109c  movi a11, 253            ; 0xFD  (guard reject)
0x1115  movi a11, 252            ; 0xFC  (busy)
```

0xFE / 0xFD / 0xFC are the same three codes `smu-raw.md` observed the live SMU
emit. So the Curve Optimizer question has a precise home now: the CO messages
`0x55` / `0x54` / `0x64` returning **0xFF (Failed), not 0xFE (UnknownCmd)** means
their table entries are non-null and their handlers run and then refuse — the
refusal is a branch inside a handler this image contains.

Several handler tables were found by structure (arrays of 8-byte entries whose
pointer column is an Xtensa prologue, `36 4x 00` / `36 6x 00`) — `@0x13b90`
(48 entries, default handler `0x2bd88`), `@0x7ff0` (64 entries), `@0x6f94`,
`@0x70c4`, `@0x6b6c`, with per-entry config dwords like `0x00000006` /
`0x00000201`. Full disassembly and the table list:
[`evidence/psp-firmware/queue-dispatch.txt`](evidence/psp-firmware/queue-dispatch.txt).

**What is not yet pinned down.** Which of those is the MP1 queue, and the exact
handler for id `0x55`. The dispatch's queue index is set up in RAM at boot, and
the handler arrays visible in the image top out around 18–64 entries, so the
id→handler array for the MP1 queue (which must reach `0x55`) is either built in
RAM or indexed differently from the 8-byte model above. That resolution wants a
real Xtensa disassembler with a RAM map — Ghidra 11.1+ ships Xtensa — not
`rasm2` by hand.

## What this does and does not change

- **It reopens nothing by itself.** The Curve Optimizer gate is still the SMU
  refusing a recognised command (`smu-raw.md`), and the flash is still
  signature-verified end to end. Reading the SMU firmware does not unlock it.
- **It closes the ISA question and moves the CO question one level in.** The
  core is Xtensa and the dispatcher's structure (id → per-queue handler table,
  8-byte entries, guard byte, 0xFE/0xFD/0xFC) is now known from this image. The
  remaining step is narrower and concrete: resolve the MP1 queue's handler table
  and read entry `0x55`.
- **It corrects two things.** `firmware-limits.md`'s "psptool mis-slices" guess
  (replaced by the exact layout bug), and any reading of `veri-failed` as
  "this machine's firmware is not properly signed" — it is signed, and verifies.
- **It states two limits honestly.** Capstone cannot disassemble the image
  because it does not model Xtensa (a tool limit, now worked around with rasm2);
  and the specific CO handler is not yet extracted (a work limit, stated as
  such).

## Reproducing

```bash
pip install psptool

# extract the plaintext, prove the sha256, and verify over both layouts
python3 evidence/psp-firmware/psp-firmware.py \
    /home/iswad/DATA/bios_extract/work/smmre/088D1.bin --out /tmp/psp-firmware

# the same correction seen from psptool itself:
#   in psptool/header_file.py, change get_decrypted_decompressed_body() to
#   get_decrypted_body() in get_signed_bytes(); re-run
psptool -E 088D1.bin | grep -E 'SMU|PMU'

# the ISA and the dispatcher: rasm2 (radare2) speaks Xtensa, capstone does not
rasm2 -a xtensa -b 32 -d "$(xxd -s 0x1e0 -l 0x18 -p SMU_OFFCHIP_FW.bin)"
```

Captured output: [`evidence/psp-firmware/psp-firmware.txt`](evidence/psp-firmware/psp-firmware.txt)
(extraction + both RSA layouts), [`evidence/psp-firmware/fw-analysis.txt`](evidence/psp-firmware/fw-analysis.txt)
(hashes, structure, the architecture probe),
[`evidence/psp-firmware/xtensa-isa.txt`](evidence/psp-firmware/xtensa-isa.txt)
(the ISA identification and its corroboration), and
[`evidence/psp-firmware/queue-dispatch.txt`](evidence/psp-firmware/queue-dispatch.txt)
(`queue_dispatch` and the handler tables).

## Related

- [`firmware-limits.md`](firmware-limits.md) — the PSP directory, Sure Start,
  and the "three of four encrypted regions" section this page corrects.
- [`smu-raw.md`](smu-raw.md) — the live SMU the extracted firmware's version
  matches, and the CO gate (0xFF, not 0xFE) this firmware's dispatcher implements.
- [`msr-and-smm.md`](msr-and-smm.md) — the same pattern, one layer down: a
  tool-side mistake (`EIO`) read as a hardware block.
