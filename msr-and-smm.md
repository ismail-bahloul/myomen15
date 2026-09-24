# The layers below the OS: MSR, SMM, and the FCH write-protect registers

Companion to [`chipsec-recon.md`](chipsec-recon.md). That page got CHIPSEC —
Intel's and AMD's own platform-security tool — running on this machine to talk
to the chip directly, and used it for three things: raw MSRs, the FCH
write-protect registers, and the SMM MSRs.

This page records what happened when the same questions were asked **without
CHIPSEC**, through interfaces the running kernel already exposes. All three
turned out to need no external tool at all, and one of `chipsec-recon.md`'s
conclusions is wrong.

Everything below was read on this machine, on CachyOS kernel `7.2.6-1-cachyos`.
Reads only — no MSR, PCI config or MMIO write was made.

## Correction: MSR reads were never blocked

`chipsec-recon.md` closed with this, and so does [`access-surface.md`](access-surface.md):

> `MSR` | `EIO` | `/dev/cpu/*/msr` exist but `read()` at `0x1a0` returns
> `Input/output error` … the block is a Linux policy decision in
> `arch/x86/kernel/msr.c`, one layer above the hardware.

**Half of that is right and half is wrong.** There is no block for a *valid*
MSR: the stock `msr` driver reads AMD MSRs directly, no CHIPSEC, no module
build. What the `0x1a0` read actually hit is that `0x1a0` is
`IA32_MISC_ENABLE` — an **Intel** MSR, which does not exist on this AMD part,
so the read takes a `#GP` and the driver reports `EIO`. The repo read an
Intel-only register on an AMD CPU and concluded the kernel was filtering.

Measured, read via `os.pread(fd, 8, msr)` on `/dev/cpu/0/msr`
(`evidence/msrread.py`):

| MSR | Name | Value | Note |
|---|---|---|---|
| `0x00000010` | `TSC` | live | a plain timestamp counter, changing every read |
| `0x0000001B` | `APIC_BASE` | `0x00000000FEE00900` | matches CHIPSEC's `0xFEE00800` (bit 8 = BSP) |
| `0x0000008B` | `PATCH_LEVEL` | `0x000000000A500014` | the loaded microcode revision |
| `0xC0000080` | `EFER` | `0x0000000000009D01` | **identical** to CHIPSEC's value |
| `0x000001A0` | `IA32_MISC_ENABLE` | **`EIO`** | Intel-only; #GP on AMD |
| `0xDEADBEEF` | invalid | **`EIO`** | nonsense MSR |

The two `EIO` rows are the discriminator. A nonsense MSR and the Intel-only
MSR both fail; every AMD MSR succeeds. That is *validity*, not policy — if
`msr.c` were allowlisting by policy, a nonsense address and a legitimate
out-of-tree AMD address would not be distinguished this way, and `0xC0010015`
above would not have returned at all.

**Consequence for the repo:** the "MSR" rows in `access-surface.md` and the
`chipsec-recon.md` scorecard should read "not blocked" — but with the reason
corrected. CHIPSEC's driver was never needed to read an MSR here; it was
needed only because the probe that started this was pointing at an Intel
register. (CHIPSEC remains the tool for CHIPSEC's *higher-level* modules —
`spi`, `bios_wp`, decoded register dumps — which the stock interfaces do not
reproduce.)

## What the MSRs say: SMM is locked, and where SMRAM is

With the MSRs readable, the SMM control registers answer directly:

| MSR | Name | Value | Meaning |
|---|---|---|---|
| `0xC0010015` | `HWCR` | `0x00000001C9000011` | see decode below |
| `0xC0010111` | `SMM_BASE` | `0x00000000BEF62000` | SMBASE |
| `0xC0010112` | `SMM_ADDR` | `0x00000000BE000000` | **TSEG base** |
| `0xC0010113` | `SMM_MASK` | `0x0000FFFFFF006603` | low bits `0x3` → `AVALID`=`TVALID`=1 |
| `0xC0010114` | `VM_CR` | `0x0000000000000008` | `SVMDIS`=1 (SVM off), `LOCK` clear |
| `0xC0010010` | `SYSCFG` | `0x0000000000740000` | MTRR/DRAM config |

Decoding `HWCR = 0x1C9000011`, bits set are `0, 4, 24, 27, 30, 31, 32`:

- **bit 0 — `SmmLock` = 1.** SMM code in the ASeg/TSeg ranges and the SMM
  registers are read-only, and SMI is not intercepted under SVM.
- **bit 31 — `SmmBaseLock` = 1.** `SMM_BASE` is not saved to / restored from
  the SMM save-state area.
- bit 32 is also set. The repo's own `chipsec-cezanne.xml` (copied from
  CHIPSEC's `strix.xml`) labels `SmmPgCfgLock` at **bit 33**, not 32 — a
  one-bit discrepancy between that field description and what this part
  reports. Flagged, not resolved; the AMD field is not guessed here.

So the deepest privilege level on the machine, **ring −2, is locked**. This is
the CPU bit that makes the SMI handler un-redirectable even for code running
in it, and it is set.

**TSEG is 32 MB at `0xBE000000`, confirmed twice.** `SMM_ADDR` says the TSEG
base is `0xBE000000`; `/proc/iomem` independently marks exactly
`be000000-bfffffff` (32 MB, sitting right below the `0xC0000000` MMIO hole) as
`Reserved`. The MSR and the memory map agree.

**And SMRAM is not readable from the host.** Reading `/dev/mem` at the TSEG
base and at `SMM_BASE` returns `0xFF` for every byte:

```
be000000  ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff
bef62000  ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff
```

That is meaningful, not an artifact: a control read of ordinary System RAM
(`0x100000`) is refused outright with `EPERM` by `STRICT_DEVMEM`, so the
`0xFF` here is the hardware hiding the SMRAM pages, not `/dev/mem` failing.
Combined with `SmmLock=1`, the read side of the deepest layer is closed too.

This closes the loop on the SMM story the repo already half-told. `\AOD`'s
handler `AodSmmSsp` is *live* (the repo pokes it via I/O `0xB2`), the MSRs say
SMM is *active* (`AVALID`/`TVALID`=1), and `SmmLock=1` says it cannot be
*modified* or *read*. The interface is reachable; the ring is sealed.

## The FCH write-protect registers, read without CHIPSEC

`chipsec-recon.md` gets the FCH registers through `chipsec_util pci dump`.
They are also in plain `/sys/bus/pci/devices/0000:00:14.3/config`, which needs
no tool at all. The values match CHIPSEC's capture exactly — an independent
reproduction, on a different kernel:

```
00:14.3  offset 0x50: 00 00 00 00   ROMPROTECT0 = 0x00000000
         offset 0x54: 00 00 00 00   ROMPROTECT1 = 0x00000000
         offset 0x58: 00 64 32 00   ROMPROTECT2 = 0x00326400
         offset 0x5C: 00 00 00 00   ROMPROTECT3 = 0x00000000
         offset 0xA0: 02 00 c1 fe   SPIBASEADDR = 0xFEC10002
```

`ROMPROTECT2`, the only one set, decodes against the field layout in
`chipsec-cezanne.xml`:

```
WriteProtect = 1     bit 10
ReadProtect  = 0     bit 9
RangeUnit    = 0     bit 8   -> 4 KB units
RomBase      = 0x326 bits 12+   -> 0x326000
Range        = 0     bits 0-7
```

So `ROMPROTECT2` **asserts write-protection over a zero-length range**: the
`WriteProtect` bit is armed, but `Range = 0` means the protected window is
`0 << 12` bytes. Read plainly, it protects nothing — the same ambiguity
`chipsec-recon.md` flagged, now with an explicit reading. It is a
`Read,Write-once` register, so this is the firmware's own choice, not a state
a running OS could have produced.

`SPIBASEADDR = 0xFEC10002` decodes `base 0xFEC10000`, `SpiRomEnable=1`,
`PspSpiMmioSel=0` — the SPI controller is host-visible right now, not
PSP-only. Two successive 256-byte reads of this config space are
**byte-identical**, so these protection values are stable state, not a
transient. The full `0x40`–`0x100` zone (the part `access-surface.md` calls
"non-zero and uninterpreted") is now captured in
`evidence/deep-recon/pci-sysfs-256.txt`. Two entries correlate with things the
repo already knows, as **hypotheses, not measurements**:

- LPC `0x60` = `0xfe70fe70` — two `0xFE70` fields, and the `H2RA` region the
  DSDT declares lives at `0xFE700000`. Looks like the bridge's own declaration
  of that memory range.
- LPC `0x68` = `0x000f0000` — the `0xF0000` legacy BIOS-ROM window in the
  F-segment.

Neither is decoded further here; they are recorded so the next person has the
raw bytes and a lead, not a claim.

The SPI controller's own MMIO (`0xFEC10000`, `SPIBASEADDR`'s base) was read
too, read-only — `evidence/deep-recon/spi-mmio.txt`. It is live hardware: two
bytes differ between two successive captures (`0x0C` and `0x4E`), one of them
the same status/counter field `chipsec-recon.md` saw move at `0x0C`. Not
decoded further.

## Reproducing

```bash
# MSR reads: valid AMD MSRs succeed, Intel-only and nonsense ones EIO
sudo python3 evidence/msrread.py

# the FCH config registers, straight from sysfs
sudo dd if=/sys/bus/pci/devices/0000:00:14.3/config bs=1 count=256 status=none | xxd

# SMRAM is hidden from the host
sudo python3 evidence/memdump.py 0xBE000000 0x40
```

Tooling: `evidence/msrread.py` (MSR reads + the validity discriminators),
`evidence/memdump.py` (`/dev/mem` hexdump, read-only), plus the raw captures in
`evidence/deep-recon/`.

## What this does and does not change

- **It reopens nothing that was actually closed.** Curve Optimizer is still
  SMU-gated; the setup store is still Sure-Start/signature-guarded. This is
  about *where* a block lives, and here the block was never where the repo
  said it was.
- **It makes one layer cheaper to inspect.** MSRs, the FCH protection
  registers and the SMN bus now need, at most, a stock device node or a
  `setpci` — no DKMS build, no tool install. For anyone reading this repo on a
  fresh system, the MSR/FCH/SMN layer is a `cat` away.
- **It states a hard ceiling.** `SmmLock=1`, SMRAM hidden, and PSP signature
  verification over the flash are three independent reasons the deepest
  layers of this machine are inspectable but not modifiable. See
  [`firmware-limits.md`](firmware-limits.md) for the flash side.
