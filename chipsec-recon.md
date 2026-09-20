# CHIPSEC recon: what the hardware itself says, not just HP's software

Everything the rest of this repo says about MSRs and about Sure Start came from
software surfaces: `/dev/cpu/*/msr` and `hp-bioscfg`. Both are one layer removed
from the chip. [CHIPSEC](https://github.com/chipsec/chipsec) — the platform
security assessment framework Intel and AMD themselves use — talks to the chip
directly: raw PCI config space, raw MSRs via its own kernel driver, raw MMIO.
This page is what it said when pointed at this machine, and what it took to get
it running here at all.

Raw commands and their full output: [`evidence/chipsec-recon.log`](evidence/chipsec-recon.log).

## Getting it to run at all was the first result

`chipsec-dkms-git` (AUR) failed to build against `7.2.4-3-cachyos`:

```
chipsec_km.c:895:9: error: call to undeclared function 'rdmsr_on_cpu'
chipsec_km.c:898:9: error: call to undeclared function 'wrmsr_on_cpu'
```

Not a missing header — the functions themselves are gone. This kernel renamed
`rdmsr_on_cpu`/`wrmsr_on_cpu` to `rdmsrq_on_cpu`/`wrmsrq_on_cpu`, with a single
`u64*` out-param instead of two `u32*` (eax/edx) ones. `chipsec`'s driver, like
most out-of-tree kernel modules, has not caught up. Fix: two `static inline`
shims that call the new API and split the `u64` back into the old two-register
shape, so the six call sites in `chipsec_km.c` don't need touching. Patch:
[`evidence/chipsec-km-msr-api.patch`](evidence/chipsec-km-msr-api.patch).

With that, `dkms install` succeeds, the module loads (`lsmod` confirms it), and
it **does not trip Secure Boot / lockdown** on this machine — it loads clean,
just taints the kernel (`TAINT_OOT_MODULE` + `TAINT_UNSIGNED_MODULE`, purely
informational here). CHIPSEC's own `LinuxHelper` unloads it again after each
invocation, so nothing sits resident.

## MSR `EIO` was Linux, not the firmware

The README lists `MSR | 🔴 | /dev/cpu/*/msr exist, read() → EIO`. That is true
of the *kernel's* `msr` module — which keeps its own safe-register allowlist —
but it is not what happens when you `rdmsr` directly, in kernel, via CHIPSEC's
own driver:

```
CHIPSEC RDMSR( 0x1b )        = 00000000FEE00800   -- APIC_BASE, correct shape
CHIPSEC RDMSR( 0xc0000080 )  = 0000000000009D01   -- EFER, plausible flags
```

Both are real, correctly-shaped values, not `0` or an error. So this machine's
MSRs are **not** blocked at the CPU or firmware level — the block is a Linux
policy decision in `arch/x86/kernel/msr.c`, one layer above the hardware. This
does not reopen Curve Optimizer: CO is gated through the **SMU mailbox**, a
different and already-tested path (`smu-raw.md`, `record/02-*`), not through
MSR reads. What it does mean is the `🔴` on that README row overstates where
the block actually lives.

## A platform CHIPSEC doesn't know, and what it takes to teach it

CHIPSEC 2.0.8 (git HEAD) ships zero AMD platform definitions below Strix Point
(Zen5) — nothing for Cezanne (Zen3, this CPU: `CPUID 0x00A50F00` decodes to
Family 19h Model 50h, matching AMD's public Family 19h Models 50h–5Fh
"Cezanne" designation). Without a matching config, every module that needs
decoded registers refuses to run (`ERROR: Platform is not supported`), even
though raw `pci`/`mem`/`msr` access works fine underneath — those don't need a
platform file, only the higher-level HAL (`spi`, `bios_wp`, `tpm`, `cpu info`,
`reg`) does.

So: [`evidence/chipsec-cezanne.xml`](evidence/chipsec-cezanne.xml), a minimal
platform file that gets CHIPSEC to recognise `CEZANNE` and correctly resolve
`VID 1022 / DID 1630` (this machine's root complex, `00:00.0`) instead of
`FFFF/FFFF`. Its register definitions (`SPIBASEADDR`, `ROMPROTECT0-3`, `HWCR`,
`SMM_BASE/ADDR/MASK`) are copied verbatim from CHIPSEC's own upstream
`strix.xml` — justified, not guessed: this machine's `LPC` (`1022:790E`) and
`SMBUS` (`1022:790B`) PCI device IDs are **identical** to the ones `strix.xml`
already declares, which means the FCH block those registers describe is shared
silicon across AMD generations, not Strix-specific.

Two things this did *not* get working, worth recording rather than hiding:

- `common.bios_wp`, CHIPSEC's write-protect check module, still refuses —
  `SPI HAL is not initialized`. That module is architecturally Intel-only (it
  expects an Intel-style SPI/`BIOS_CNTL` HAL); adding a platform file doesn't
  change that. AMD's equivalent isn't a HAL module in this codebase.
- `chipsec_util reg read <name>` reports `No register found`, even for
  registers this file defines and even under `-p CEZANNE`. Root cause not
  chased down — plausibly a bug in this specific dev snapshot (dated
  `Jul 10 2026`, well ahead of any tagged release), since the same command
  fails identically for CHIPSEC's *own* `strix.xml` registers once you work
  around an unrelated `-p` argument-parsing bug (platform names get
  uppercased before matching against literal, non-uppercase `choices`, so
  `-p "Strix Point"` cannot be selected either — not something this repo
  introduced).

The register values below therefore come from `pci dump` (works with no
platform file at all) decoded by hand against `strix.xml`'s field layout, not
from the `reg` command.

## What the FCH's own write-protect registers say

`chipsec_util pci dump 0 0x14 3` (the LPC bridge) — identical across two
independent captures:

```
offset 0x50: 00 00 00 00   ROMPROTECT0 = 0x00000000  (unset)
offset 0x54: 00 00 00 00   ROMPROTECT1 = 0x00000000  (unset)
offset 0x58: 00 64 32 00   ROMPROTECT2 = 0x00326400
offset 0x5C: 00 00 00 00   ROMPROTECT3 = 0x00000000  (unset)
offset 0xA0: 02 00 C1 FE   SPIBASEADDR = 0xFEC10002
```

`SPIBASEADDR` decodes clean: base `0xFEC10000`, `SpiRomEnable=1`,
`PspSpiMmioSel=0` — the SPI controller MMIO is host-visible right now, not
locked to PSP-only access. That MMIO was read directly too (`mem read
0xFEC10000 0x40`) and is genuinely live hardware, not a stub: one byte in it
changed between the two capture runs (`0x18` → `0x89` at MMIO offset `0x0C`) —
a status/counter field, not yet identified, flagged here so it isn't mistaken
for a stable config bit later.

`ROMPROTECT2` is the one register with anything set: `WriteProtect=1`,
`ReadProtect=0`, `RangeUnit=4 KB`, `RomBase=0x326`, `Range=0`. Read plainly,
that asserts write-protection starting at ROM offset `0x326000`, sized `Range
<< 12` — which, with `Range=0`, is either a genuine zero-length range or an
edge case the public field description doesn't resolve. **This is a hypothesis
about a narrow, specific FCH-level protection, not a measurement of Sure
Start.** It does not explain full-image tamper detection by itself, and it is
a different, much weaker mechanism than the PSP-enforced signature check the
rest of this repo already established — it would take an actual write attempt
(not done, not planned without a fallback plan for the shared EC/fan flash) to
know whether `WriteProtect` here does anything enforceable at all.

## The honest scorecard

| Question | Before this page | After |
|---|---|---|
| Are MSRs blocked by hardware/firmware? | Assumed, from `EIO` | **No** — blocked by the Linux `msr` module's own allowlist; raw `rdmsr` via CHIPSEC works and returns correct values |
| Does that reopen Curve Optimizer? | — | **No** — CO is gated at the SMU mailbox, a separate path already tested and refused on both OSes |
| Can CHIPSEC's own BIOS-write-protect check run here? | Not tried | **No** — that module is Intel-only architecturally, unrelated to platform support |
| Is there a readable FCH-level write-protect register? | Not known to exist as a measured value | **Yes** — `ROMPROTECT2` has `WriteProtect=1` over a narrow, ambiguous range; not yet correlated to any actual write behaviour |
| Does any of this get past Sure Start? | — | **No** — no write was attempted; the PSP-signature conclusion in `firmware-limits.md` stands |
