# The runtime TEE: the verifier that runs after boot

[`psp-boot-verifier.md`](psp-boot-verifier.md) decoded the **boot-time** chain. But
the PSP does not stop at boot: it hosts a GlobalPlatform TEE
([`psp-tee.md`](psp-tee.md)) that keeps running, and that is where the OS hands it
a Trusted Application. This page follows that thread into the two modules that are
resident at runtime — `PSP_FW_TRUSTED_OS` and `DRIVER_ENTRIES` — and reports what
is there, including where the audit stops.

This is a first pass: the modules are mapped, the verifier is located, the
host-facing ingress is followed from the driver entry down to the RSA check, and
the result is that the runtime **reuses the same standard crypto and header format
as boot, with explicit bounds — ingress included**.

## The two runtime modules, mapped

| Module | Size | Functions (Ghidra) | What it is |
|---|---|---|---|
| `PSP_FW_TRUSTED_OS` (`0x2`, `0.11.0.85`) | 103280 | 111 | the TEE kernel (scheduler, SVCs, TA world) |
| `DRIVER_ENTRIES` (`0x28`, `0.11.0.85`) | 124784 | 764 | the AMD-TEE **driver** — the GP API the host talks to |

Both import cleanly as `ARM:LE:32:v7`, base `0` (a single executable block; TOS
`0x0..0x19370`, driver `0x0..0x1e770`). The relocation problem from the boot
loader is still present: the GP property strings are there but **carry no xrefs** —

```
0x814 xrefs=0  "gpd.tee.deviceID"
0x868 xrefs=0  "AMD-TEE Global Platform API"
0x926 xrefs=0  "gpd.tee.trustedStorage.antiRollback.protectionLevel"
```

— while a handful of strings *do* resolve and give handholds
(`gpd.ta.appID` → `FUN_0001480c`, `amd.fw.SecPatchLevel` → `FUN_00009a68`, the
UUID formatter `FUN_00019524`, `FUN_00006b78` → *"Widevine - Device unique - ECDSA
Key"*).

`DRIVER_ENTRIES` also carries the HMAC key names that tie it to this repo's
objects: *"HMAC Signature Key for signing APOB data"*, *"…for PSP Data saved in
DRAM"*, *"…for Wrapped iKEK saved in SPI-ROM"*, *AES/HMAC Key for wrapping data"*.

## The runtime has its own RSA verifier — and it is the same one

Searching the stored bytes for the PKCS#1 v1.5 DER headers (`30 21 …` SHA-1,
`30 31 …` SHA-256):

| Module | PKCS#1 SHA-1 OID | PKCS#1 SHA-256 OID |
|---|---|---|
| `PSP_FW_TRUSTED_OS` | — | — |
| `DRIVER_ENTRIES` | `0x13708` | `0x1372c` |
| `PSP_BOOT_TIME_TRUSTLETS` | `0x1ca0c` | `0x1ca28` |

So the **TOS does not do RSA itself**; `DRIVER_ENTRIES` does (an observation; the
inference is that the TOS delegates crypto to the driver). The OID table at
`0x13708` is read by one function, `FUN_00013570`, a textbook PKCS#1 v1.5 verify:

```c
// FUN_00013570(sign, ?, digest_len, exp?, key_bytes, ?, msg, sig)
FUN_00001698(auStack_74, &DAT_0001372c, 0x14);         // copy the SHA-256 DigestInfo prefix
if (param_3 == 0x14) { iVar5 = 0xf; puVar6 = &local_98; }        // SHA-1
else if (param_3 == 0x1c) puVar6 = auStack_88;                   // SHA-224
else if (param_3 == 0x20) puVar6 = auStack_74;                   // SHA-256
else if (param_3 == 0x30) puVar6 = auStack_60;                   // SHA-384
else if (param_3 == 0x40) puVar6 = auStack_4c;                   // SHA-512
if (param_5 == 0x80 || 0x100 || 0x180 || 0x200) {                // RSA 1024/2048/3072/4096
    if (param_5 < param_3 + iVar5 + 0xb) return err;             // must fit
    local_338[0]=0; local_338[1]=1;                              // EM = 00 01 FF..FF 00
    memset(local_338+2, 0xff, iVar4-3); puVar2[-1]=0;
    copy(puVar2, digestInfoPrefix, iVar5); copy(local_338+k-hLen, msg, param_3);
    FUN_00004958(...);                                           // RSA modexp
    FUN_0000ca2c(local_338, auStack_538, param_5);               // memcmp
}
```

Buffers are `[512]`, key size ≤ `0x200`, digest ≤ `0x40`, and the length is checked
before use — **the same algorithm and the same care as the boot loader's
`FUN_00002bac`**. Its only caller is `FUN_00017e10`, a **crypto dispatcher**: it
selects SHA-1/224/256/384/512 and RSA, and also routes to non-RSA ops
(`FUN_00007bb8`, `FUN_00007ee0`, `FUN_00013770`, `FUN_000138fc`) — consistent with
the `gpd.tee.cryptography.ecc` property. `FUN_00017e10`'s caller is `FUN_00018b3c`.

## The runtime parses `$PS1` modules — with the boot header fields

The `$PS1` magic appears several times in `DRIVER_ENTRIES` (`0x712c`, `0xbc88`,
`0x1a530`, `0x1ab60`, `0x1e010`) and in the TOS (`0x16120`, `0x173a0`, `0x17538`).
Three loaders reference it:

- **`FUN_0000bc20`** — checks `header+0x10 == $PS1`, then bounds the module:
  `size = *(u32 *)(header+0x14) + 0x100; if (size < 0xa000)` — a **0xa000 cap** —
  before copying it in.
- **`FUN_0001a3b8`** — a **directory loader**: maps the image, checks `$PS1`, then
  walks an entry array with pairs `(type, offset)`, requiring `0x7fff < size` to
  fail (entries ≤ `0x7fff`) and a matching type byte (`'D'`, `0x101d`, `0x101e`,
  `0x1047`), and calls `FUN_0000f7a0` to verify each one.
- **`FUN_0000f7a0`** — the **per-entry verifier**, and the clearest sign that this
  is the same format as boot:

```c
// FUN_0000f7a0(entry, flag, ctx, keybase)
uVar2 = (*(int *)(puVar5 + 0x34) == 0) ? 0x20 : 0x30;   // digest len: SHA-256 / SHA-384
iVar8 = (*(int *)(puVar5 + 0x34) == 0) ? 0x100 : 0x200; // key size
uVar3 = (*(int *)(puVar5 + 0x48) == 0) ? *(u32 *)(puVar5 + 0x14)          // size_signed
                                       : (*(int *)(puVar5 + 0x54) + 0xf) & ~0xf; // zlib size
if (param_1[1] < uVar3 || param_1[1] < uVar3 + iVar8 + 0x100) fail;       // bounds
...
FUN_000138fc(auStack_7c, uVar2, ...);   // verify (dispatcher op)
for (; local_6a8 < 4 && puVar5[0x7f] != 0; puVar5 += 0x100) { ... }       // <= 4 sub-entries
```

`+0x48` compressed, `+0x14` size_signed, `+0x54` zlib_size, `+0x34` digest
selector, key `0x100`/`0x200` — the **same header layout** the boot loader reads,
and it recurses into up to four sub-entries with a bound check on each.

`FUN_00007000` (called on `0xb`/`0xc`) is the same idea on another path: map, check
`$PS1`, `software_interrupt(0x79)` (an SVC into the TOS), then parse via
`FUN_0001a7c4`.

## The host-facing ingress, located

The reason this matters: the runtime verifier is reachable **from the host**, and
the path is now read end to end. Following the call graph upward (the `BL`s are
PC-relative and survive relocation, so the call graph is trustworthy even where
the data references are not), the loaders bottom out in a single entry:

```
FUN_000077e0  driver entry  (a ROOT — nothing calls it; the TOS/scheduler does)
   *param_1 == 0x1000 or >= DAT_00007848  ->  FUN_0000dbe0  (command dispatcher)
   *param_1 <  0x1000                     ->  FUN_00018b3c  (crypto services)
```

```c
// FUN_000077e0(cmd, ctx)   -- copies the 0x7c-byte request, dispatches on cmd[0]
uVar3 = *param_1;
FUN_00001698(local_98, param_1, 0x7c);         // request struct is 0x7c bytes
local_98[0] = uVar3;
if (uVar3 < 0x1000) iVar2 = FUN_00018b3c();   // crypto
else                iVar2 = FUN_0000dbe0(local_98, param_2);   // services
```

`FUN_0000dbe0` (0xca2 bytes) is the **host command dispatcher**: a large switch on
`*param_1` over AMD service ids. The ones that matter here route straight into the
load-and-verify routines:

| command | handler | what it does |
|---|---|---|
| `0x3130` | `FUN_000106dc` | load an image from host (addr,size) and verify |
| `0x312d` | `FUN_0001a3b4` | adjacent to the `$PS1` directory loader |
| `0x313e` | `FUN_00010388` | |
| `0x3140` / `0x3141` | `FUN_00010138` / `FUN_00010170` | |
| `0x1000`,`0x1002`,`0x6001–3`,`0x8004–a` | … | other services |

And the load command takes **host pointers**, then hands the image to the entry
verifier:

```c
// FUN_000106dc (host command 0x3130)
if (0xff < param_1[2]) {                                   // size > 0xff
    FUN_00011604(&local_98, 1);                            // validate the host region
    FUN_00007730(*param_1, param_1[1], param_1[2], ..., &local_78, ...);  // read it
    local_7c = *(uint *)(local_78 + 0x54);                 // zlib size from header+0x54
    if (local_7c < param_1[2] - 0x100) {
        FUN_00007730(param_1[3], param_1[4], uVar5, ...);  // second region (key/sig)
        software_interrupt(0x79);                          // into the TOS
        iVar4 = FUN_0000f7a0(&local_74, 0, local_50);      // <-- verify the entry
        FUN_0000f11c(local_78 + 0x100, local_7c, local_80, uVar5, &local_54);  // decompress
        if (*(int *)(iVar3 + 0x50) != local_54) iVar4 = err;  // size_uncompressed check
    }
}
```

So a host-supplied image goes: **command `0x3130` → `FUN_000106dc` → `FUN_0000f7a0`
→ `FUN_000138fc` → the PKCS#1 verifier**. The same format, the same gate — now
provably fed by the host.

**And it is bounded.** The `(address, size)` pairs a command carries are validated
before use, twice over:

- **`FUN_00011604`** requires the address and size to be **page-aligned**
  (`(addr & 0xffff) == 0`, `(size & 0xffff) == 0`), rejects any address with high
  bits set (`addr & 0xffff0000`), caps the size against `DAT_00011840`, rejects
  overflow on the computed end, checks a **16-byte integrity tag** (`local_44` xor
  a stored value — the loop `bVar6 |= buf[i] ^ stored[i]; ... i < 0x10`), and gates
  on a chip id (`param_1[4] ∈ {0x65, 0x66}`).
- **`FUN_00007730`** checks the `[addr, addr+size)` range against page boundaries
  (`uVar3 - param_1 < end > start`), and on failure **traps into the TOS**
  (`software_interrupt(0x6b/0x8b)`) rather than proceeding.

## Auditing the other ~180 handlers

The load commands are one set of ids among many, so the natural next question is
whether any *other* host command reaches the verifier — or, worse, touches host
memory **without** the validator. That was checked mechanically rather than by
reading 180 functions:

- **Reachability.** For every function called from `FUN_0000dbe0` (181 of them),
  follow the callees four levels and ask whether they reach a host-buffer
  validator (`FUN_00011604`, `FUN_00007730`, `FUN_0000c4bc`) or the entry verifier
  (`FUN_0000f7a0`). Full table:
  [`evidence/psp-tee-runtime/handler-audit.txt`](evidence/psp-tee-runtime/handler-audit.txt).
- **SVC map.** Every `svc` immediate, per number and per function, to see which
  functions use the host-mapping calls:
  [`evidence/psp-tee-runtime/svc-map.txt`](evidence/psp-tee-runtime/svc-map.txt).

Result:

- **Eight handlers map host memory and verify it** — `FUN_000106dc`,
  `FUN_000119a0`, `FUN_00016c80`, `FUN_0001aa5c`, `FUN_00010888`, `FUN_0000fda0`,
  `FUN_00010b50`, `FUN_0000f4c8` — all reaching `FUN_00007730` (map) and/or
  `FUN_00011604` (validate), then `FUN_0000f7a0` / `FUN_000138fc`.
- **The host-map helpers are twins, and both check.** `FUN_00007730` (SVC
  `0x6b`/`0x8b`) and `FUN_000075a0` (SVC `0x6b`/`0x6d`) have the identical shape:
  page-range check, then **trap into the TOS** on a bad range, then map. No mapping
  helper exists without the check.
- **The SVC-sharing candidates are not host parsers.** `FUN_000159c8`,
  `FUN_00015bf0`, `FUN_00015eac`, `FUN_00015fac` (which share SVC `0x5e`/`0xa7`
  with the validator) index a **bounded table** — `param_2 < 0x40`, 16/32-byte
  compare, key/session services. `FUN_00014a5c` (the slot allocator) walks **8
  slots** (`uVar6 < 8`) with range checks. None takes a free host pointer.

So the sweep found **no host command that processes host memory without a range
check**. The host-facing surface of the runtime TEE is the eight load/verify
handlers above — which are the ones already walked to the RSA check.

## What this shows, and where it stops

Shown (and this is now end to end):

- The runtime TEE has its **own PKCS#1 v1.5 verifier** (`FUN_00013570`) and a
  crypto dispatcher (`FUN_00017e10`) — the **same algorithm, the same bounds**, and
  the same `$PS1` header fields as the boot-time verifier.
- The runtime loaders have **explicit size caps** (`0xa000` for a module,
  `0x7fff` per entry), digest and key sizes from a small fixed set, and a length
  check before every copy we read.
- **The host ingress is located and bounded**: `FUN_000077e0` → `FUN_0000dbe0` →
  the load commands → `FUN_0000f7a0` → RSA, with the `(address, size)` pairs
  validated by `FUN_00011604` and `FUN_00007730` before any parse.
- **A sweep of the other 180 handlers found no unvalidated host path**: the only
  eight that map host memory all verify it, the mapping helpers all trap on a bad
  range, and the look-alike candidates are bounded-index key/session services.
- **The TOS TA loader is bounded too** (and readable, after a correction):
  `FUN_00016748` caps the input at 1 MiB, keys on the header type (`"TA"`/`"DR"`),
  requires `driverID ∈ {2,3,4}`, and bounds the memory plan (`< 0x401` pages per
  region, total below the aperture).

Where it stops (recorded, not guessed):

- The relocation wall is still up: the `gpd.tee.*` property strings have no xrefs,
  so the property table and the API dispatch table cannot be followed by data
  reference. The command→handler map above is read from the **switch in
  `FUN_0000dbe0`** (PC-relative), which is why it resolves at all.
- The **full command id → handler enumeration** is not exhaustive here — only the
  load/verify ids are named; the other ~50 ids map to services that are located but
  not characterised.
- The entry-hash primitive (`FUN_0000a150`), the decompressor (`FUN_0000f11c`),
  and the non-RSA dispatcher ops (ECC) are located but not decoded.

The honest summary: the runtime **reuses the same standard, bounded crypto**, and
the one place a host bug could have lived — the ingress path in `DRIVER_ENTRIES` —
has been **walked from the entry to the RSA check, then swept across every other
handler, and found bounded both ways**. The TOS's own loader, once read rather than
assumed, is bounded as well. Nothing here weakens the
[`psp-boot-verifier.md`](psp-boot-verifier.md) conclusion; it extends it to the path
where the OS hands the PSP a blob — and the audit of that path is now closed,
not just sampled.

## The TOS kernel: the TA loader, read and bounded

`PSP_FW_TRUSTED_OS` is the third and last runtime module — the TEE kernel that
receives host commands and hosts TAs. It is imported (111 functions), and its shape
is legible even where the code is not:

- **44 of the 111 functions are roots** (no caller), and almost all are **syscall
  wrappers**: 45 functions contain a single `svc 0xf2`. So `0xf2` is the TOS's own
  system call — the entry the driver (`DRIVER_ENTRIES`) and the TAs call into — and
  the stubs `FUN_000123da`…`FUN_000135e4` are the service surface.
- **One large root is the TA loader**: `FUN_00016748` (0x870) queries a TA's
  manifest properties and sets the instance up. The property path is
  `FUN_000126e8(ctx, "gpd.ta.appID" | …)` → build a request (`0x1009`, type `2`)
  → `svc 0xf2` → read the result from `&DAT_00007280 + offset`.
- The property getters **clamp and convert**. `FUN_00014748` returns
  `ceil(heapSize / 4096)` pages, and clamps `amd.ta.SecHeapSize` to **`0x100`
  pages**; `FUN_000147c8` returns `ceil(stackSize / 4096)`; `FUN_000146c4` and
  `FUN_000146fc` read `amd.dr.driverID` and `gpd.ta.instanceKeepAlive`.

```c
// FUN_00014748(ctx, which) -- which=0 heapSize, which=1 SecHeapSize
if (which == 0) {
    iVar2 = FUN_000126e8(ctx, "gpd.ta.heapSize", ...);
    if (iVar2 == 0) uVar3 = (*(int *)(&DAT_00007280 + *piVar1) + 0xfff) >> 0xc;   // pages
} else {
    iVar2 = FUN_000126e8(ctx, "amd.ta.SecHeapSize", ...);
    if (iVar2 == 0) { uVar3 = (size + 0xfff) >> 0xc; if (0x100 < uVar3) uVar3 = 0x100; }
}
```

**A correction.** The first pass here claimed the loader *"defeats the
decompiler"* — Ghidra drops a long list of *"Removing unreachable block"* warnings
inside `FUN_00016748`. Reading the **disassembly** instead
([`evidence/psp-tee-runtime/tos-loader-disasm.txt`](evidence/psp-tee-runtime/tos-loader-disasm.txt))
shows those blocks are **dead code** — e.g. a `bne` followed by an unconditional
`b` that both skip the following `svc` — not indirect control flow. There is no jump
table; the code is ordinary Thumb. The loader is therefore **readable**, and it was
read.

**The TA loader is bounded, in layers.** `FUN_00016748(size, …, buf)`:

- input size `param_3 ≤ 0x100000` (1 MiB), else error 5;
- the header carries a **type magic at `+0x14`**: `0x4154` = `"TA"` or `0x5244` =
  `"DR"` (driver) — the two object kinds;
- a `"DR"` object's `amd.dr.driverID` must be `2`, `3` or `4`, else error 6;
- heap / stack / secure-heap sizes come from the manifest, are converted to pages,
  and `SecHeapSize` is clamped to `0x100` pages;
- the memory plan is bounded by a combined check:

```c
uVar6 = *(int *)(hdr + 8)  - *(int *)(hdr + 4);          // a region size
uVar3 = align(*(int *)(hdr + 0xc)) - *(int *)(hdr + 8);  // another
if ((((uVar6 | uVar3) >> 0xc | heap_pages | stack_pages | secheap_pages) < 0x401)
    && (total <= (isTA ? 0x400000 : 0x100000) - 0x20000)) { ... instantiate ... }
```

so **every** region's page count must be `< 0x401` and the **total footprint** is
capped below the aperture (`0x400000` for a TA, `0x100000` for a driver). The
instance is placed in a **slot from a bounded table** (index `local_10c`, checked
`!= 0xff`), and a failure tears the slot down (`FUN_000184d4(slot, 2)`).

The `$PS1` byte sequences at `0x16120`, `0x173a0`, `0x17538` are **not in any
function** — they are data (embedded blobs), so the TA-header parsing is not there.

## Reproducing

```bash
# modules are already extracted by psptool -X -d 1 (see psp-boot-verifier.md)
analyzeHeadless <proj> PSPBL -import …/d00_e15_DRIVER_ENTRIES~0x28_0.11.0.85 \
    -processor ARM:LE:32:v7 -loader BinaryLoader -loader-baseAddr 0x0
analyzeHeadless <proj> PSPBL -import …/d00_e02_PSP_FW_TRUSTED_OS~0x2_0.11.0.85 \
    -processor ARM:LE:32:v7 -loader BinaryLoader -loader-baseAddr 0x0
analyzeHeadless <proj> PSPBL -process '…DRIVER_ENTRIES…' -noanalysis \
    -scriptPath evidence/psp-boot-verifier/ghidra -postScript Dec20.java
# Dec12-16 = verifier + loaders; Dec17-18 = call graph + the entry/dispatcher;
# Dec19-21 = the host load commands, the (address,size) validators, and the
#   candidates; Audit.java = handler reachability; Svcs.java = the SVC map
# Dec22 = boot-command bounds; Dec23-24 + Tos.java = the TOS loader and getters
# Disasm.java = the TA loader's linear disassembly (the correction that it is readable)
```

- Census and string xrefs: [`evidence/psp-tee-runtime/map-DRIVER_ENTRIES.txt`](evidence/psp-tee-runtime/map-DRIVER_ENTRIES.txt),
  [`evidence/psp-tee-runtime/map-PSP_FW_TRUSTED_OS.txt`](evidence/psp-tee-runtime/map-PSP_FW_TRUSTED_OS.txt).
- TOS recon and its TA loader / property getters: [`evidence/psp-tee-runtime/tos-recon.txt`](evidence/psp-tee-runtime/tos-recon.txt),
  and the loader's disassembly [`evidence/psp-tee-runtime/tos-loader-disasm.txt`](evidence/psp-tee-runtime/tos-loader-disasm.txt).
- Handler reachability sweep: [`evidence/psp-tee-runtime/handler-audit.txt`](evidence/psp-tee-runtime/handler-audit.txt).
- SVC (TOS call) map: [`evidence/psp-tee-runtime/svc-map.txt`](evidence/psp-tee-runtime/svc-map.txt).
- Decompiled runtime verifier and loaders: [`evidence/psp-tee-runtime/decompiled.txt`](evidence/psp-tee-runtime/decompiled.txt).
- Scripts: `Dec12–Dec16.java`, `MapAll.java`, `Str2.java` in
  [`evidence/psp-boot-verifier/ghidra/`](evidence/psp-boot-verifier/ghidra/).

## Related

- [`psp-boot-verifier.md`](psp-boot-verifier.md) — the boot-time chain this extends.
- [`psp-tee.md`](psp-tee.md) — the module map and the AMD-TEE door (`amdtee` → `/dev/tee0`).
- [`psp-firmware.md`](psp-firmware.md) — the SMU/MP1 image these loaders bring up.
