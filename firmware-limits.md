# Firmware & hardware limits (HP OMEN 15-en1xxx)

Living reference for what this firmware does and does not allow, so the dead
ends are not explored again. Everything here was measured on this machine.

The point-in-time investigation record is in `record/` in this repository; this
file is the distilled, current conclusion.

## The setup is readable — the flash chip is not fully opaque

An earlier conclusion in this repo was that the firmware is a black box: the
update payload is a proprietary AMI container, and the flash is shared with the
EC. That is true of the *payload*. It is **not** true of the flash chip itself,
and it is not true of the running system.

**The BIOS setup answers are plain EFI variables**, readable from Linux with no
reboot and no `/dev/mem`:

```
/sys/firmware/efi/efivars/AMD_PBS_SETUP-a339d746-…   132 B    PBS menu answers
/sys/firmware/efi/efivars/AmdSetup-3a997502-…        1448 B    CBS menu answers
/sys/firmware/efi/efivars/Setup-ec87d643-…            322 B    the Setup table
/sys/firmware/efi/efivars/SetupDefault-0ee72c08-…     322 B    its factory defaults
/sys/firmware/efi/efivars/HPSetupData-206bc44a-…      116 B    HP's own setup data
```

The same bytes are also sitting in the **flash chip, in clear, twice** — outside
the encrypted volumes. The two `AMD_PBS_SETUP` copies (flash `0x7c0e17` and
`0x7e0e17`) differ in **exactly one byte**, at offset 22; the runtime variable
matches whichever the firmware is running from.

So the interesting detail is not that the flash is opaque — it is that it is
readable **twice**, and the one byte that differs between the copies is a free
correlation point for naming the rest of the table. Full detail, with the
reproduction steps, is in [`efi-nvram.md`](efi-nvram.md).

### What this corrects

- **"The payload cannot even be extracted"** was too strong. It cannot be
extracted *as an Aptio image*, but the live configuration is readable at
runtime, and the payload is sitting on the ESP at
`/boot/EFI/HP/BIOS/Current/088D1.bin` (16 MiB) to inspect.
- **"`Custom Core Pstates` is empty, therefore there is nothing to
configure"** needs a caveat: **more than a third of the 16 MiB image is at
entropy ≈ 8.0** — encrypted or compressed — and no `_FVH` signature survives
inside those volumes. A string's absence from the dump therefore only says it is
not *in the clear*. The empty-menu finding rests on the live setup browser under
SmokelessUMAF, which is the right instrument; the image neither confirms nor
refutes it.
- **The memory-tuning dead end was a QVL dead end, not a firmware one.** The
image carries whole SPD profiles keyed by part number, in signed `APCB` blocks
(each with its own GUID and MD5). One of them is a literal
`8ATF1G64HZ-2G3B1` — a Micron module this machine does not have. The installed
modules are `MT16ATF2G64HZ-3G2E1` (confirmed by `dmidecode`, both slots), which
have no profile of their own. The lever is `AMD CBS > UMC Common Options`.

### The write path is still the dead end

Nothing above changes the flashing conclusion. Every one of these variables
carries the `EFI_VARIABLE_RUNTIME_ACCESS` bit and **refuses `O_RDWR`** outright,
which is the firmware gating its own setup rather than a mount option. Sure Start
is active, `authentication/SPM` reports `is_enabled = 0` and
`key_mechanism = not provisioned` (so no BIOS admin password is set either), and
the BIOS payload is PSS/RSA-signed — a modified image cannot be re-signed.

## BIOS power limits are a POST-time seed, not a policy

`ryzenadj` writes the SMU limits directly; the BIOS *System Configuration*
setting (`AMD CBS > NBIO Common Options > SMU Common Options`) only chooses the
values the firmware seeds at POST. Those seeds are the **stock** profile,
measured as:

```
firmware/POST limits: STAPM LIMIT=54.000 PPT LIMIT FAST=65.000 PPT LIMIT SLOW=54.000 THM LIMIT CORE=100.000
```

`power-profile.service` replaces them ~12 s after boot, and
`power-profile.timer` re-applies every 5 min as a safety net (see "Power limits"
below for what that net actually protects against).

**The setting is inert.** Selecting `35W POR` there and rebooting produced the
same stock values above. The HP EC appears to own them and override the AMD
setting. The setting is now back on its default `Auto` with no observable
difference — which is itself the confirmation. Don't spend time on that menu; if
firmware-level limits are ever needed for Windows, the lever to look at is HP's
own thermal mode, not AMD CBS.

## Undervolt / Curve Optimizer: locked on the SMU path (dead end *there*)

Not possible through the **SMU mailbox** on this machine — on **either** OS. Six
independent confirmations:

1. `ryzenadj --set-coall`, `--set-coper` and `--set-cogfx` all return
   **`rejected by SMU`**, including for the neutral value `0`. `--enable-oc`,
   `--disable-oc` and `--gfx-clk` are rejected too, while `--stapm-limit` /
   `--fast-limit` / `--slow-limit` / `--max-performance` are accepted.
2. The encoding was verified against ryzenadj issues #302 / #296 (a negative
   offset is `0x100000 - value`, a per-core offset is `(core << 20) | value`),
   so this is not an encoding mistake.
3. The BIOS has **no Curve Optimize menu**, only *Custom Core Pstates* — and its
   form contains **no questions at all** in the IFR.
4. Patching the `SuppressIf` guards with SREP (`SuppressIFPatcher.efi` /
   `SetupBrowser.efi` on a USB key) and re-entering the menu with `Accept` +
   `F10` + reboot still leaves *Custom Core Pstates* empty.
5. `amdgpu`'s `pp_od_clk_voltage` exposes clock offsets only — no voltage curve
   for the iGPU either.
6. **Windows cross-check — the decisive one.** UXTU (Universal x86 Tuning
   Utility) *looks* like it succeeds, but its own `uxtu_log*.txt` records
   **20 failures out of 20 `set-coall` writes**, including offset `0`, with
   `SMU command 'set-coall' failed with status FAILED`. UXTU catches the
   exception, logs it as a warning, and **still updates its UI**, so a failed
   write looks applied. A direct SMU probe through UXTU's own PawnIO driver
   confirms it: the mailbox works (`0x0D` PM-table version, `0x14` stapm-limit)
   while the whole OC/CO command family is refused (`0x55` set-coall, `0x54`
   set-coper, `0x64` set-cogfx, `0x2F` enable-oc, `0x30` disable-oc, `0x49`
   pbo-scalar, `0x65` PM-table transfer).

Point 6 also settles the obvious hypothesis: UXTU reaches the SMU by the **same
path as Linux** (PawnIO → `RyzenSMU.bin` → SMN indirect via PCI config
`0xB8`/`0xBC`), with the **same message IDs and the same argument encoding**.
`ryzenadj` already sends the correct command for Cezanne, so there is nothing to
patch or port — the firmware simply gates the OC/CO family off, consistent with
points 3–5 and with HP Sure Start.

**Do not** install ZenTune (ex-UXTU4Linux) hoping for CO, and **do not** patch
`ryzenadj` for it.

### But there is a second road, and it has not been tried

Every confirmation above goes through the **SMU mailbox** (`ryzenadj` on Linux,
PawnIO → `RyzenSMU.bin` on Windows). SSDT2 declares a second `PNP0C14` device,
`\AOD`, with a command table that says, in literal strings, `Set Curve
Optimizer`. Its handler does not use the mailbox at all:

```
Method (R308, 1, NotSerialized)          // ACMD 0x0005000A
{
    CreateDWordField (Arg0, 0x04, SVAL)
    MBVS = 0x05
    COPS = SVAL
    MBCB = 0x00100032
    ASMI (0xB9)                          // writes I/O port 0xB2 -> SMM -> BIOS
}
```

That is the path HP's own tuning software uses, and it asks the **BIOS**, not
the SMU. The same table exposes `Set PPT Limit`, `Set TDC/EDC Limit`, `Set
Scalar`, `Set IOD VDDG`, and `Set Soc TDC/EDC`.

**This is not a claim that it works.** The SMM handler may forward straight to
the SMU and get the same `FAILED`. What is now established is only that the
interface exists, that the firmware documents it down to the command ID, and
that it has never been exercised. The conclusion above stands for the mailbox;
it does not cover this.

The read path is not usable as a check — `\AOD.AM04` returns zeros — so any
test here would have to be judged by **effect**, not by return value. Given this
repo has already been caught once by a write that succeeded and did nothing,
that is worth stating plainly rather than discovering. Detail:
[`acpi-bridge.md`](acpi-bridge.md).

`\AOD.AM01` answers `0x5` and `\AOD.AM03` returns the command table today, so
the interface is live.

## BIOS modding: not possible (HP Sure Start)

`hp-bioscfg` reports **HP Sure Start** active, which verifies and restores the
firmware on tamper. On top of that the flash chip is shared with the EC (fan
control), and `flashrom` is deliberately not used here: a failed write would
risk the fans. The `BIOS_Update.exe` payload is a proprietary AMI container
(`@UAF@` / `@UII@`) that `uefixtract` does not recognise.

The image itself, though, is not opaque — see
["The setup is readable"](#the-setup-is-readable--the-flash-chip-is-not-fully-opaque)
above. The payload on the ESP is a 16 MiB AMI firmware image with two complete
copies of the flash, and the parts that hold *state* are in clear.

## Power limits: what resets them is **not** established

This section has now been wrong in three different ways, so it is written as
the current state of the evidence rather than as a conclusion.

### What is solid

`ryzenadj` writes take and hold. Writing `37/44/37` reads back `37/44/37`, and
the two 10-minute A/B runs (`evidence/nbfc_{on,off}.csv`) showed no reversion.

### The three claims, in order

| # | Claim | Status |
|---|---|---|
| 1 | "The EC periodically reverts the limits, hence the 5-minute timer" | **not reproduced** in the A/B run |
| 2 | "A `platform_profile` write makes the EC re-apply its own limits" | **measured once, then contradicted** |
| 3 | "Claim 2 is wrong" (an earlier over-correction in this file) | itself wrong: the test that produced it never set a distinctive value first |

The one measurement that looked decisive:

```
[18:48:08] platform_profile MODIFY -> 'balanced'
[18:48:09] LIMITS CHANGED: 35/42/35 -> 54/65/54
```

### What contradicts it

With every power-profile unit **stopped** and no other writer present, writing
`platform_profile` was measured over 5 seconds of 100 ms polling, for all three
profiles (`cool`, `balanced`, `performance`), and **the limits did not move**:

```
depart  : (37, 44, 37)
write platform_profile = 'performance'
final   : (37, 44, 37)      after 5 s
```

So the write alone does not reset them. Something else in the earlier test did,
and the most likely candidate is now visible in the configuration:

### `54/65/54` is this machine's own PERF profile

```
/usr/local/bin/power-profile:53
    ryzenadj --stapm-limit=54000 --fast-limit=65000 --slow-limit=54000 \
             --apu-slow-limit=42000 --tctl-temp=90
```

`54/65/54` is not an EC value at all — it is what `apply_perf()` writes, chosen
to match the stock/POST values. So a `54/65/54` reading means **PERF was applied
by the script**, not that firmware clobbered anything.

That does not by itself explain the 18:48 event (no caller of `power-profile
perf` exists in `/etc`, and the governor was `powersave`, so `apply_perf` should
not have run). It does mean the number was misattributed.

### Still unexplained

`50/65/54` was seen twice, with no `platform_profile` write logged. It is:

- **not** in `/usr/local/bin/power-profile` (which only writes 54/65/54, 35/42/35
  and 15/18/15),
- **not** in any platform-profile attribute,
- **not** in any of the 256 addressable EC registers (the `50`s found there are
  the fan setpoint at `0x2C` and two unrelated bytes).

`STAPM` is a *sustained* limit with a 275 s time constant, so a smaller value
under load is at least plausible as SMU behaviour rather than an override — but
that is a hypothesis, not a measurement.

### The practical position

Whatever the mechanism, the fix does not depend on identifying it:

| Mechanism | Signature | Detection |
|---|---|---|
| `platform_profile` write | `54/65/54` | inotify on the attribute |
| anything else | any other drift | read the PM table once a second |

Reading the limits is nearly free (one `read()` of 2372 bytes, no SMU command,
no ACPI call), so the profile is applied **only when the values move**, plus
once at startup so a watcher beginning from a wrong state still corrects it.
Measured: 0.12 s for a `platform_profile` write, 1 s for a silent drift, against
a 5-minute timer before.

The pieces are `evidence/power-profile-watch` and
`evidence/power-profile-watch.service`; they delegate the apply to
`systemctl start power-profile.service`, so there is one implementation of the
profile. `power-profile.timer` stays as a third backstop.

### The lesson, kept

Three claims, three retractions, and both errors had the same shape: a value was
read without first establishing what it was. The original "EC reverts" theory
and the "platform_profile is innocent" correction failed the same way. The
`54/65/54` attribution then failed a third way — by not checking whether the
number was written by *our own script*.

Before attributing a value to firmware, set a distinctive one and check who else
writes it.

The investigation script is `evidence/limitwatch.py`; the original A/B is
`evidence/ec-revert-ab-test.sh`.

## Battery charge thresholds: reachable, not exposed

The kernel surface really is empty — `powerdevil` reports "not supported by
kernel", `/sys/class/power_supply/BAT0/` has no `charge_control_*` attributes,
and `hp-bioscfg` exposes nothing. That part of the earlier conclusion stands.

What does **not** stand is calling the mechanism opaque. The DSDT shows HP's own
WMI methods doing exactly this, on a named EC register:

```
Method (GBCC, 0, Serialized)   // "HP WMI Command 0x1F (BIOS Read)"
Method (SBCC, 4, Serialized)   // "HP WMI Command 0x1F (BIOS Write)"

\_SB.PCI0.SBRG.EC0.MBDC    charge-control register, written by SBCC
\_SB.PCI0.SBRG.EC0.MBTS    battery-usable guard
\_SB.PCI0.SBRG.EC0.MBST    modes supported, bits 0-1
\_SB.PCI0.SBRG.EC0.ADPP    AC-present guard
```

And `acpi_call` reaches them right now:

```
\_SB.PCI0.SBRG.EC0.MBTS  -> 0x1     battery usable
\_SB.PCI0.SBRG.EC0.MBST  -> 0x0     ** no cap mode advertised **
\_SB.PCI0.SBRG.EC0.MBDC  -> 0x0     nothing set
\_SB.WMID.GBCC            -> [0x0, 0x4, {0x00, 0xff, 0x00, 0x00}]   mode 0
```

The `BCTC` / `BMNC` read-only finding is about the ACPI *battery* objects, a
different mechanism. Both statements are true; the earlier page conflated them.

**Not written to, deliberately.** The argument encoding is decoded and the revert
(`MBDC &= 0xE0`) is shared by both code paths — but `MBST = 0x00` says the
battery implements no cap mode, so a write may be accepted and ignored. Given
this repo has already been burned once by a write that succeeded and changed
nothing (the UXTU case), that is a warning, not a formality. Full detail:
[`battery-charge-control.md`](battery-charge-control.md).
Tooling: `evidence/batterycc.py` (read-only by default).

## The PM table: what the SMU is actually doing

`/sys/kernel/ryzen_smu_drv/pm_table` is a plain read-only file of 2372 bytes, and
it decodes as `float32` — nine limits, each followed by its live value:

```
STAPM      limit=50.000   live=8.941      TDC_VDD   limit=58.000   live=9.965
PPT_FAST   limit=65.000   live=18.872     TDC_SOC   limit=15.000   live=4.347
PPT_SLOW   limit=54.000   live=19.148     EDC_VDD   limit=110.000  live=79.132
PPT_APU    limit=22.000   live=19.148     EDC_SOC   limit=20.000   live=0.000
THM_CORE   limit=85.000   live=65.364
```

This is the instrument the Windows half of this repo concluded it could not have
(there, the PM table never populated — the refresh command `0x65` was refused and
the read returned zeros). On Linux it is populated and needs no SMU command at
all. Any "did this write take, and does it survive?" question is now one file
read instead of parsing `ryzenadj --info`.

It also closes an old loose end: the "`50/65/54` vs `54/65/54` discrepancy" was
never a discrepancy. `0x00` is STAPM and `0x10` is PPT-slow; reading a triple as
"STAPM / fast / slow" and expecting 54 in the first slot was the error. Details in
[`pm-table.md`](pm-table.md).

## Not supported by the kernel / firmware

- **Battery charge thresholds**: not exposed by the kernel — but *not* a
  firmware dead end either. See "Battery charge thresholds" above.
- **Serial port**: `8250.nr_uarts=0` was measured to save ~0 — the `ttyS*`
  devices are not on the critical path — so `limine.conf` was left untouched (it
  carries the VFIO entry).
- **MSR**: `/dev/cpu/*/msr` exist but `read()` returns `EIO`.
- **EFI variable writes**: every variable carries `EFI_VARIABLE_RUNTIME_ACCESS`
  and refuses `O_RDWR` with `EPERM`.
- **TPM**: currently set to `Hidden` — disabled and not detected at POST.

## The firmware ships a generic EC / I-O bridge

SSDT12 declares byte-level access to **any** EC register and **any** I/O port:

```
\_SB.PCI0.SBRG.EC0.M040 <offset>         read  any EC byte
\_SB.PCI0.SBRG.EC0.M041 <offset> <val>   write any EC byte
\_SB.PCI0.SBRG.EC0.M31A <port>           read  any I/O port byte
\_SB.PCI0.SBRG.EC0.M319 <port> <val>     write any I/O port byte
```

Verified exhaustively against `ec_probe`: **256 of 256 registers agree**. Two
consequences worth noting:

- It is a **fourth independent path to the EC** (after `ec_sys`, `hp-wmi` and the
  `H2RA` memory region), so a disagreement between paths is detectable.
- `M319` reaches **any I/O port, including `0xB2`**, the AMD SMM command channel
  — the same one `\AOD` uses. Nothing in the kernel exposes that.

Tooling: `evidence/ecbridge.py`, read-only unless `--yes`. Detail:
[`acpi-bridge.md`](acpi-bridge.md).

## HP's performance mode, located (in the EC)

The earlier note here said HP's thermal mode "has not been located on the Linux
side". It is at two adjacent EC registers:

| Register | Offset | Meaning |
|---|---|---|
| `OCPC` | `0xBA` | current performance profile (0–6) |
| `OCPS` | `0xBB` | highest selectable profile |

Currently `OCPC = 0x01`, `OCPS = 0x07`. `PWLC` (DSDT 17344) maps the profile to
dGPU power limits in mW through `\DPTC` — profile 0 gives 54/65/54 W, profile 6
gives 15 W. It is switched by EC query events (`_Q8C` applies, `_Q8E` cycles up),
not by a WMI command.

So this is a **live, writable mode selector in the EC**, and `\DPTC` is callable
directly. It drives the dGPU rather than the CPU, so it is not the CPU thermal
mode the earlier note was chasing — but it is the same family of control, and it
was previously recorded as not found.

## EC access (mapped further)

The EC is reachable through `ec_probe` (based on `ec_sys`), and its fan and
temperature registers are identified and verified — see
[`ec-map.md`](ec-map.md). `nbfc` already drives the fan setpoints through the same
path, so the write half has a working reference.

Two corrections to the earlier map, both from a controlled thermal ramp:

- **`0x57` and `0x58` are CPU temperatures**, tracking `k10temp`'s `Tctl` within
a degree across a 72 → 85 °C ramp. `0x48` is a third, slower-moving sensor.
- **The rest of the `0x40`–`0x49` row is not.** `0x40`, `0x42`, `0x44`, `0x46`
and `0x49` never moved under load. The earlier "plausible additional
temperatures" was too generous.

What was tested and **ruled out**: the EC does not hold the SMU power limits.
Dumping the EC before and after a `ryzenadj` write, with a no-op control run to
account for telemetry drift, produces indistinguishable diffs — the limits live
in the SMU only. So the [platform profile
reset](#power-limits-what-resets-them-is-not-established) is not
the EC re-asserting a stored limit.

### The EFI variables that carry the setup

```bash
# the AMD PBS answers (skip the 4-byte NVRAM counter)
sudo dd if=/sys/firmware/efi/efivars/AMD_PBS_SETUP-a339d746-f678-49b3-9fc7-54ce0f9df226 \
        bs=1 skip=4 count=132 status=none | xxd

# the same structure, in the flash chip, in clear, twice
sudo python3 -c "
import mmap,os
fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
d=mmap.mmap(fd,0x1000000,offset=0xff000000,access=mmap.ACCESS_READ)
for off in (0x7c0e17,0x7e0e17): print(hex(off), bytes(d[off:off+15]))"
# -> 0x7c0e17 b'AMD_PBS_SETUP'   /   0x7e0e17 b'AMD_PBS_SETUP'  (differ at byte 22)
```

Details, and the rest of the store, in [`efi-nvram.md`](efi-nvram.md).

---

See also [Boot tuning](https://github.com/ismail-bahloul/dotfiles/blob/main/docs/boot-tuning.md)
in the dotfiles repository, for the boot-time work and what is still on the table
there.
