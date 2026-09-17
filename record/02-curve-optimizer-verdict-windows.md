# Curve Optimizer on HP OMEN 15-en1xxx — Windows-side verdict

Companion to `01-linux-power-report.md`. That report asked (priority #1):
*"How does UXTU apply CO on this platform?"* This document answers it, and then
falsifies the premise the report was built on.

---

## 1. Verdict up front

> **Curve Optimizer does not work on this machine. Not on Windows, not on Linux.
> It is refused by the SMU, deterministically, with status `FAILED`.**

The report's headline — *"On Windows: CO works"* — is **wrong**. It was based on
my own measurement, and that measurement was an artifact.

- UXTU does **not** report the failure. It updates its UI, writes a warning to a
  log nobody reads, and looks like it succeeded. A **silent false positive**.
- 20 out of 20 `set-coall` writes failed. Including offset `0`.
- The refusal is `SMU_Failed` (0xFF), not "wrong command ID", not "wrong
  argument encoding", not a missing prerequisite.

Your Linux conclusion — *"I can't do CO on Linux"* — was **correct**. Your
framing — *"refused by the SMU"* — was **correct**. The only thing wrong was
attributing the Linux-only failure to the Linux write path.

---

## 2. The decisive evidence

### 2.1 UXTU's own diagnostic log

`C:\Program Files\JamesCJ60\Universal x86 Tuning Utility\logs\uxtu_log<date>.txt`

First line of the session, written **before** the first "successful" benchmark run:

```
2026-09-15 18:17:43.622 [WRN] [RyzenAdj_To_UXTU.TranslateCore]
  Failed to process command: --set-coall=1048566
System.InvalidOperationException: SMU command 'set-coall' failed with status FAILED.
   at RyzenSmu.SMUCommands.Execute(...)            RyzenSmu.cs:line 669
   at RyzenSmu.SMUCommands.applySettings(...)      RyzenSmu.cs:line 627
   at ...RyzenAdj_To_UXTU.TranslateCore(...)       RyzenAdj_To_UXTU.cs:line 165
```

Totals over the whole session:

```
20 x Failed to process command: --set-coall
20 x failed with status FAILED
 0 x SMU applied
```

`1048566` = `0x100000 - 10`. All values attempted are present: −10, −15, −20,
−25, −30, and `0` (`--set-coall=0`).

### 2.2 Direct SMU probing (independent of UXTU)

I wrote a small tool that loads UXTU's own PawnIO module and sends raw MP1
commands (see §5). Results:

| MP1 msg | Meaning | Result |
|---|---|---|
| `0x0D` | get PM table version | ✅ SUCCESS (`0xC8`) |
| `0x14` | `stapm-limit` (arg 35000 mW) | ✅ SUCCESS (echoed `0x3A98` = 15000) |
| `0x55` | **`set-coall`** | ❌ FAILED |
| `0x64` | `set-cogfx` (iGPU CO) | ❌ FAILED |
| `0x2F` | `enable-oc` | ❌ FAILED |
| `0x49` | `pbo-scalar` | ❌ FAILED |
| `0x5B` | `get-sustained-power-and-thm-limit` | ❌ FAILED |
| `0x19` | `tctl-temp` | ❌ FAILED |
| `0x30` | `disable-oc` | ❌ ERROR_INVALID_PARAMETER |

So the mailbox itself works (0x0D and 0x14 succeed), and the **OC/CO command
family is gated off by the firmware**. This matches the report's §4 findings
highly: no Curve Optimize menu, empty `Custom Core Pstates`, Sure Start active.

### 2.3 What this does to my earlier measurement

The measured "gain":

| run | offset | throughput |
|---|---|---|
| `D_uxtu_open_noco` | 0 | 7152 Mi/s |
| `E1_co_minus10` | −10 | 7508 Mi/s |
| `E2_co_minus20` | −20 | 7510 Mi/s |

…was measured with a CO that **was never applied** (the −10 apply failed at
18:17:43, 69 seconds before run `E1`). The difference was environmental: thermal
soak, background contention, and the EC's own power-limit re-assertions.

Corollaries that were also wrong:

- The "optimal plateau at −10…−20" is noise.
- The "clock stretching at −25/−30" is noise. There was no undervolt, so there
  was nothing to stretch. I fitted a physically plausible story onto drift.
- The single-thread "confirmation" (533.6/532.6 normal, 523.7 at −30) is noise.

The run-to-run spread of *identical* configurations in that session was
~±3 % — the same size as the "effect". The interleaved sweep already showed
this (offset 0 scored both 7087 and 7300; −15 scored both 6940 and 7320). That
was the signal, and I under-weighted it.

---

## 3. Answers to the report's Windows questions (§7)

1. **How does UXTU apply CO / which driver?**
   `UXTU → PawnIO driver → RyzenSMU.bin module → SMN indirect via PCI config`.
   - Driver: **PawnIO** (`namazso`), service `PawnIO`, demand start,
     `PawnIO.sys` in the DriverStore. **Not** WinRing0, **not** the AMD Ryzen
     Master driver. It is a *generic* kernel driver; UXTU loads a Pawn script
     into it as a "module".
   - Module: `Assets/AMD/PawnIO/RyzenSMU.bin`, compiled from the **open-source**
     `RyzenSMU.p` (LGPL-2.1) in `github.com/namazso/PawnIO.Modules`.
   - Access: PCI config **offset `0xB8` = SMN address, `0xBC` = SMN data**
     (`Smu.SMU_OFFSET_ADDR = 184`, `SMU_OFFSET_DATA = 188`). Mailbox for
     Cezanne at `cmd=0x3B10A20, rsp=0x3B10A80, args=0x3B10A88` — matching the
     module's `k_addrinfo` table index 2 (`Cezanne`).
   - **This is the same mechanism `ryzen_smu` uses on Linux.** The access path
     was never the difference.

2. **Does UXTU have to unlock anything first?**
   It tries `enable-oc` (MP1 `0x2F`) among its command table, but that also
   **fails** here. There is no successful unlock step.

3. **Does the CO offset survive?** Moot — it is never written.

4. **What does UXTU report / what is the range?**
   UI range for all-core CO: **−50 … +30** (`sdAllCO` slider). iGPU (`sdGfxCO`)
   same range. Per-core section exists (`sdAmdCCD1CO`). It reports the value you
   set, **not** the value actually applied — there is no read-back, and no error
   surface when the write fails.

5. **Can the offset be read back?** No.

6. **Does UXTU expose the power limits?** Yes — see §4.

7. **Platform profile (cool/balanced/performance)?** Not exposed. UXTU has
   "Windows Power Mode" and "Windows Processor Power" instead.

8. **Persistence without UXTU running?** Not reachable, since the write fails.

---

## 4. Power limits in UXTU (relevant to the report's §5)

All present in *Custom Presets → APU Power Tuning / Temperature Tuning*, values
in **watts** (not mW):

| Control | AutomationId | Range | UI default |
|---|---|---|---|
| STAPM Limit (W) | `sdSTAPMPow` | 5–300 | 28 |
| Slow Power Limit (W) | `sdSlowPow` | 5–300 | 28 |
| Slow Boost Duration (s) | `sdSlowTime` | 2–1024 | 128 |
| Fast Power Limit (W) | `sdFastPow` | 5–300 | 28 |
| Fast Boost Duration (s) | `sdFastTime` | 2–1024 | 64 |
| Temperature Limit (°C) | `sdAPUTemp` | 10–105 | 95 |
| Skin Temperature Limit (°C) | `sdAPUSkinTemp` | — | 45 |
| VRM current targets | `sdAmdApuVRM` | — | not expanded |

**The UI defaults are not a hardware read-back.** They are UXTU's own defaults —
the Linux POST seeds 54/65/54 W and Tctl 100 °C. Do not use UXTU's display as
evidence of what is in the SMU.

And the SMU's own responses are not a read-back either — see §9.

UXTU also exposes per-preset **AC / DC** variants (`acPreset`, `dcPreset`,
`acCommandString`, `dcCommandString`) plus `AutoReapply` / `AutoReapplyTime` —
i.e. a direct equivalent of the Linux `power-profile` AC/battery design and its
`guard` re-apply timer.

---

## 5. Tools left behind (reusable)

> **Post-session cleanup (Windows), done:** the PawnIO service, its DriverStore
> package and its folder, UXTU and its runtime leftovers, the .NET 10 SDK and
> Desktop Runtime, and `C:\Users\<user>\Desktop\perf-test\` have all been removed.
> Only sources and raw data were preserved, in `evidence/` on the shared
> partition. The compiled helpers (`smu.exe`, `load.exe`) must be rebuilt from
> `smu.cs` / `load.cs` if ever needed again — that requires PawnIO plus UXTU's
> `Assets/AMD/PawnIO/RyzenSMU.bin`.

Originally located in `C:\Users\<user>\Desktop\perf-test\`:

| File | What it does |
|---|---|
| `smu.exe` (`smu.cs`) | Sends raw SMU commands / reads registers / dumps the PM table, via PawnIO + `RyzenSMU.bin`. P/Invokes `PawnIOLib.dll` (`pawnio_open/load/execute`) |
| `load.exe` (`load.cs`) | Fixed-work all-core / N-thread load generator (throughput metric) |
| `sample.ps1` | Runs the load, samples effective clock + ACPI temp, appends to `results.jsonl` |
| `set_co.ps1`, `sweep.ps1` | Drive UXTU's UI over UI Automation (sliders, checkboxes, Apply) |
| `uia.ps1`, `uiact.ps1`, `uiact2.ps1` | UI Automation dump / click / expand helpers |
| `strings.ps1` | Extract printable strings from a binary |
| `ryzensmu_src.p`, `ryzenadj_api.c` | Vendored sources used for the analysis |
| `uxtu_src/` | Full ILSpy decompilation of UXTU 26.3.1 |

`smu.exe` usage:

```
smu.exe info                 # code_name, smu_version, pm table version/base
smu.exe co <offset>          # set-coall (0x55), UXTU's argument encoding
smu.exe send <msg> [a1..a6]  # raw MP1 command
smu.exe read <addr_hex>      # read an SMN register
smu.exe pm <outfile>         # resolve + dump the PM table
```

Confirmed working sanity values:

```
code_name   = 13 (Cezanne)
smu_version = 0x00404A00  (SMU 64.74.0)
pm_version  = 0x00400005  (matches the Linux report's "PM Table Version: 400005")
```

---

## 6. For the record: the CO command encoding (in case the gate is ever lifted)

From UXTU's `RyzenSmu.Addresses`, socket `FP6_AM4` (Renoir / Lucienne / Cezanne):

```
("set-coper", true,  84)   MP1 message 0x54
("set-coall", true,  85)   MP1 message 0x55
("set-cogfx", true, 100)   MP1 message 0x64
("get-coper-options", false, 195)   RSMU
("get-cogfx-options", false, 198)   RSMU
```

Argument encoding (`EncodeCurveOptimiserOffset`):

```csharp
if (offset >= 0) return (uint)offset;
return (uint)(1048576 - (-offset));    // 1048576 = 0x100000
```

Dispatch (`RyzenSmu.SMUCommands.Execute`) tries each candidate in order, moving on
only on `UNKNOWN_CMD`; any other status is thrown. **`ryzenadj` uses the same
message IDs and the same encoding** for Cezanne (`lib/api.c`: `set_coall →
_do_adjust(0x55)`, `set_coper → 0x54`, `set_enable_oc → 0x2F`), and its
`REP_MSG_CmdRejectedPrereq` / `REP_MSG_Failed` paths explain the "rejected by SMU"
message.

So there is nothing to port and nothing to fix: both implementations send the
same correct command, and the SMU refuses it with `FAILED`.

**`ZenTune` (ex-UXTU4Linux) will hit the same wall** for CO on this machine — it
drives the same SMU messages. It remains interesting for power limits,
automations and AC/battery switching, but not for Curve Optimizer.

---

## 7. What is still genuinely open

**The report's §5 question is unanswered and now answerable**: *does the EC
re-assert power limits on Windows the way it does on Linux?*

I have confirmed that `stapm-limit` (MP1 `0x14`) is **accepted** on Windows — but its
response argument is a **constant** (`0x3A98` = 15000) regardless of the value
written, so the effect cannot be confirmed (see §9). What is missing is a
*read-back* — `get-sustained-power-and-thm-limit` (`0x5B`) is
refused, and UXTU's display is not trustworthy. The path forward is to resolve
the PM table (`smu.exe pm`) and decode the Cezanne PM-table offsets to read
STAPM/PPT/Tctl and package power/voltage directly. That would give:

- a real answer to "do the limits stick for 5 minutes on Windows?";
- the same instrument the Linux side lacks for the EC-override trigger hunt;
- package power + SVI2 voltage, i.e. the efficiency metric (J per unit of work).

That is the next piece of work, and it does not depend on CO working.

---

## 9. Addendum — PM table and limit read-back are blocked on Windows

Attempted after the verdict above, with `smu.exe`:

| Operation | Command | Result |
|---|---|---|
| PM table version | `0x0D` | ✅ `0xC8` |
| resolve PM table | `ioctl_resolve_pm_table` | ✅ version `0x00400005`, base `0xB6AE6000` |
| **transfer PM table to DRAM** | `send_command2(0x65, 3)` | ❌ **SMU_Failed** |
| read PM table | `ioctl_read_pm_table` | ✅ SUCCESS but **all 8 KiB are zeros** |
| SVI2 voltage planes | `read 0x56000`…`0x5A008` | `0xFFFFFFFF` / `0` — dead |
| get sustained power/thm limit | `0x5B` (args 0…3) | ❌ FAILED |
| `stapm-limit` write | `0x14` | ✅ accepted, but echoes a **constant** `0x3A98` (15000) for every value written (15000/20000/35000/45000/54000) |

Two consequences:

1. **There is no usable read-back of the power limits on Windows.** The PM table
   is never populated (the refresh command `0x65` is refused), the register
   telemetry is dead, the dedicated getter is refused, UXTU's display shows its
   own defaults, and the write's response argument is a constant.
2. Therefore **the report's §5 cannot be answered from Windows**, and Windows
   cannot serve as the control experiment for the EC-override question. That
   question must be settled on Linux, where the instrument already works
   (`ryzenadj --info` reads real values, and OS-written limits were observed to
   survive then revert).

The write of `0x14` being accepted-but-echoing-a-constant is worth noting on the
Linux side: it suggests this firmware may accept the STAPM message without
acting on it, which would be a third behaviour (alongside "accepted and applied"
and "refused"). If `ryzenadj --info` ever reports a value that does not follow
what you wrote, suspect this.

---

## 10. Out-of-scope but worth reporting upstream

UXTU **silently swallows** failed SMU writes. `TranslateCore` catches the
exception, logs it at Warning, and then still calls
`LastAppliedSettingsService.Update(...)`, so the UI shows the setting as applied.
On any firmware that gates CO (HP, and likely other OEM laptops), users will
believe they have an undervolt that does not exist — and may draw invalid
efficiency conclusions from benchmarks, exactly as I did.
