# HP OMEN 15-en1xxx — power, firmware & undervolt report (Linux side)

> **Status:** §5 ("the EC periodically reverts the power limits") is **wrong** —
> see the addendum in §10. §1–§4 and §6–§9 stand as written.

This is the Linux half of the investigation; the Windows half is in
`02-curve-optimizer-verdict-windows.md`. Everything here was measured on this
exact machine, and the commands and their raw output are quoted so they can be
reproduced and verified independently.

The immediate question this document exists to answer:

> **Curve Optimizer (CO) works on Windows with UXTU, but every CO call is
> refused by the SMU on Linux. Why — and what is UXTU doing differently?**

---

## 1. Machine

| Item | Value |
|---|---|
| Laptop | HP OMEN Laptop 15-en1037nf (product 4J8B4EA) |
| Board | HP 88D2 |
| BIOS | AMI **F.30**, released **2025-10-21** |
| Firmware security | **HP Sure Start active** |
| CPU | AMD Ryzen 7 5800H — Cezanne, family `0x19`, model `0x50`, stepping `0x0`, 8C/16T |
| iGPU | Radeon Vega (RENOIR `0x1002:0x1638`), PCI `07:00.0`, subsystem `0x103C:0x88D2` |
| dGPU | NVIDIA RTX 3070 Mobile (GA104, 8 GB) |
| RAM | 2 × 16 GB DDR4-3200 |
| Storage | SK Hynix PC711 512 GB NVMe + Crucial T500 1 TB NVMe |
| OS (Linux) | CachyOS, kernel `7.2.4-3-cachyos`, Limine + snapper, KDE Plasma 6 / Wayland |
| OS (Windows) | Windows 11 (dual-boot, shared ESP) |

**TPM is currently disabled in the BIOS.**

---

## 2. Headline result

- **On Windows: CO works.** UXTU (Universal x86 Tuning Utility) successfully
  applies a Curve Optimizer offset to this 5800H.
- **On Linux: every CO call is refused by the SMU** (see §3), including the
  neutral value `0`.

That combination is the important datum: **the silicon and firmware accept a CO
offset.** The Linux-side refusal is therefore a property of the *interface /
command path*, not a hardware or silicon limitation. Two working hypotheses:

1. UXTU uses a **different SMU command path** than ryzenadj (e.g. through an AMD
   driver interface such as the Ryzen Master driver, or a different mailbox
   message / argument layout).
2. UXTU performs an **unlock step first** (some OC-enable equivalent) that
   ryzenadj attempts with `--enable-oc` but which the SMU also refuses here.

If we can find out *how* UXTU does it, there is a realistic chance of
replicating it on Linux (a `ryzen_smu`/`ryzenadj` change, or a different call
sequence).

---

## 3. Linux SMU interface and exact results

Stack: `ryzen_smu` kernel module **0.1.7**, `ryzenadj` **v0.19.0**.

Interface reported by `ryzenadj --info`:

```
CPU Family: Cezanne
SMU BIOS Interface Version: 20
PM Table Version: 400005
```

### Accepted (the write succeeds)

`--stapm-limit`, `--fast-limit`, `--slow-limit`, `--apu-slow-limit`,
`--tctl-temp`, `--power-saving`, `--max-performance`

### Refused — raw output (this is the block we are fighting)

```
$ ryzenadj --set-coall=0
set_coall is rejected by SMU

$ ryzenadj --set-coper=0
set_coper is rejected by SMU

$ ryzenadj --set-cogfx=0
set_cogfx is rejected by SMU

$ ryzenadj --enable-oc
set_enable_oc is rejected by SMU

$ ryzenadj --gfx-clk=1000
set_gfx_clk is rejected by SMU
```

Note that **even the neutral offset `0` is rejected**, so this is not an
out-of-range / argument-validation problem: the SMU refuses the message itself.

### The argument encoding was verified as correct

Checked against ryzenadj issues #302 / #296:

- all-core negative offset → `0x100000 - |value|`
- per-core offset → `(core << 20) | value`

So the values sent were well formed. It is a platform-level refusal.

---

## 4. BIOS / firmware findings

### SmokelessUMAF **does** work on this machine

The AMD CBS/PBS menus are reachable with SmokelessUMAF. Relevant menus:

- `AMD CBS > NBIO Common Options > SMU Common Options`
  - **System Configuration** — POR choices: `10W / 15W / 25W / 35W / 45W / 54W`
  - STAPM Control, CPPC, Fan Control, Stability Boost
- `XFR Enhancement` — FCLK, SOC OVERCLOCK VID
- `UMC` — memory timings

### There is no Curve Optimize menu

Only **`Custom Core Pstates`**, and that form contains **no questions at all in
the IFR** — there is genuinely nothing to configure in it.

### SREP did not help

Patching the `SuppressIf` guards with SREP (`SuppressIFPatcher.efi` /
`SetupBrowser.efi` on a USB key), then re-entering the menu with `Accept` +
`F10`, then rebooting: **`Custom Core Pstates` is still empty.**

### Behaviour to know about this firmware

A parent option left on `<Auto>` **hides its sub-options**. That is why some
options appear and disappear as you navigate.

### BIOS modding is blocked

- **HP Sure Start is active** (confirmed via `hp-bioscfg`), which verifies and
  restores the firmware on tamper.
- The SPI flash is shared with the EC (fan control), so a failed `flashrom`
  write would take the fans with it. We deliberately did **not** attempt it.
- `BIOS_Update.exe`'s payload is a proprietary AMI container (`@UAF@` / `@UII@`)
  that `uefiextract` does not recognise, so the image cannot be extracted for
  offline inspection either.

### "System Configuration = 35W POR" had **no** effect

This was measured directly (see §5). Selecting `35W POR` and rebooting still
produced the **stock 54 W** profile at POST. The HP EC appears to own those
values and override the AMD CBS setting. The setting has since been returned to
its default **`Auto`** with no observable difference — which is itself the
confirmation. Don't spend time on that menu if the goal is a firmware-level
power limit.

---

## 5. The EC rewrites the OS-written power limits (key for "persistence")

### What the firmware seeds at POST

`power-profile` logs the limits in force **before** the first write of each boot.
Result across two reboots (stock profile, unchanged by the BIOS setting above):

```
firmware/POST limits: STAPM LIMIT=54.000  PPT LIMIT FAST=65.000  PPT LIMIT SLOW=54.000  THM LIMIT CORE=100.000
```

This is the **stock 54 W profile**, with Tctl at 100 °C.

### The EC then re-asserts its own values over ours

Something (the EC) periodically rewrites the limits back to **`50 / 65 / 54`**,
clobbering what the OS wrote. Observed survival times of an OS-written
`35 / 42 / 35`:

| When | Written | Survived | Then became |
|---|---|---|---|
| 16:50 | `50 / 60 / 50` | < 55 s | `50 / 65 / 54` |
| 19:06 | `35 / 42 / 35` | ~60–90 s | `50 / 65 / 54` |
| 19:12 | `35 / 42 / 35` | ≥ 150 s (no revert seen) | — |
| 19:15 | `35 / 42 / 35` | ≥ 171 s (no revert seen) | — |

So the revert is **not on a fixed timer** — it is event-driven and
intermittent. Trigger **unidentified**.

**Suspect (not proven):** `nbfc` (a fan-control daemon) writes to the EC
continuously to set fan speed. The two clean runs above (19:12 and 19:15) were
at idle with the fans stable; the 19:15 run had `nbfc` *stopped*. This is
suggestive but not conclusive — a proper A/B test (10 min with/without `nbfc`)
still needs to be run.

### Consequence

The Linux setup re-applies the profile every **5 minutes**
(`power-profile.timer`), which is a **coarse safety net**: the machine can sit
at the EC's `50 / 65 / 54` for most of the interval before being corrected. If
the goal is that a 35 W cap actually holds, the re-apply interval needs to be
well under the revert time, or the revert trigger needs to be removed.

Note also the **discrepancy**: POST seeds `54 / 65 / 54` while the later EC
re-assert is `50 / 65 / 54`. Why STAPM differs (54 vs 50) is unexplained.

---

## 6. Other controls discovered on the Linux side

- **`/sys/class/platform-profile/platform-profile-0/`** (provided by `hp-wmi`):
  `choices = cool balanced performance`, currently `balanced`.
  Writing a profile **does not** change the SMU limits — tested `cool`,
  `performance` and `balanced`, all three left the limits at `54 / 65 / 54`.
  So it is not the mechanism, but it *is* a real EC-facing control.
- **`hp-wmi` hwmon**: `fan1_input`, `fan2_input`, `pwm1_enable` (an alternative
  path to the fans besides `nbfc`).
- **EC access exists**: `nbfc` drives the EC through `ec_sys`; `ec_probe`
  (register dump / read / write, plus `acpi_call`) is available. Mapping EC
  registers to the power-limit behaviour is unexplored and is the remaining
  lead for firmware-level persistence.
- **`hp-bioscfg` firmware-attributes** exposes only `Sure_Start` and
  `pending_reboot`.
- **Battery charge thresholds: not available.** `powerdevil` reports "not
  supported by kernel"; the `BCTC` / `BMNC` ACPI objects are read-only in the
  DSDT and their writes go to an opaque SMM handler.
- `amdgpu`'s `pp_od_clk_voltage` exposes clock offsets only — no voltage curve.

---

## 7. Questions for the Windows side

Priority order — the first three are the ones that actually unblock things.

1. **How does UXTU apply CO on this platform?** Which driver does it load
   (AMD Ryzen Master driver? WinRing0? something else?) and through which
   interface does it reach the SMU? Does it use SMU mailbox commands that
   differ from ryzenadj's, or the same ones with different arguments?
2. **Does UXTU have to unlock anything first?** i.e. is there an equivalent of
   `enable_oc` that it succeeds at? (ryzenadj's `--enable-oc` is refused by the
   SMU here.)
3. **Does the CO offset survive?** Reboot, shutdown, sleep/hibernate, AC
   unplug. If it only survives while UXTU runs, that is a strong hint the EC /
   firmware resets it — which would match the §5 behaviour.
4. **What does UXTU report as the applied offset, and what range does it
   allow?** Which value is currently stable on this chip (all-core and/or
   per-core, and iGPU `cogfx` if exposed)?
5. **Can the CO offset be read back** (from UXTU or any other tool) so we can
   compare it against the SMU state?
6. **Does UXTU expose the power limits too?** (STAPM / PPT fast / PPT slow /
   Tctl). If yes, do they **also** get clobbered after a while, or do they
   stick on Windows? That would tell us whether the §5 revert is an
   EC/hardware behaviour or something specific to the Linux write path.
7. **Does UXTU expose the HP thermal / platform profile** (`cool` / `balanced`
   / `performance`) or the `System Configuration` POR? If the Windows tool can
   change these, we learn whether they are the real lever for the POST values.
8. **Is there a way to make the CO offset persistent without UXTU running** —
   a service, a scheduled task, a registry/EFI variable, or an actual BIOS
   setting?

### What to bring back to Linux

Anything that identifies the **exact command path UXTU uses**. If UXTU can do
CO on this silicon, the SMU accepts it somehow; knowing which mailbox message
and arguments would let us reproduce it through `ryzenadj`/`ryzen_smu`.

Also useful: any indication that the Windows tool writes to the **EC** (not just
the SMU), which would tie into the §5 trigger.

---

## 8. Other work done in this session (context only, not Windows-actionable)

Recorded for completeness; none of it affects Windows.

- **Dotfiles repo** (`chezmoi`): all French content translated to English
  (README, comments, scripts); personal data stripped (desktop layout,
  geolocation, hardcoded paths) with the full git history rewritten
  (`git-filter-repo`); repository published.
- **Stale UEFI boot entries removed.** The `BootOrder` had two dead entries
  ahead of the real one (a `Limine` pointing at a GPT partition that no longer
  existed, and a "Windows Boot Manager" label pointing at a deleted
  `\EFI\cachyos\grubx64.efi`); both were removed, and Limine is kept early in
  `BootOrder`. Note: `systemd-analyze`'s *firmware* phase counts from power-on,
  so any figure captured after a BIOS visit is inflated and was not a valid
  before/after metric here.
- **Initramfs slimmed 248 MB → 55 MB** by dropping `nouveau` and its
  per-chipset NVIDIA GSP firmware (the `kms` hook pulls in ~140 MiB of it), and
  by keeping the NVIDIA modules out of the initramfs (~33 MiB, plus ~2.9 s of
  initrd load time).
- **Limine snapshot entries capped at 8** — the 4 GiB ESP had reached 85 % and
  kernel updates were at risk of failing.
- **Fixed `power-profile`:** a `RemainAfterExit=yes` made the periodic timer
  resolve to `infinity` after one run (the re-apply was silently dead); the AC
  udev rule called `auto` instead of `guard`, so plugging/unplugging the
  charger clobbered a manually selected PERF mode; and the service now logs the
  firmware/POST limits once per boot (which is how §5 was measured).
- **Fixed `nbfc` handling:** the install check looked for a binary path that
  does not exist, so `nbfc-linux` was being rebuilt from source on *every*
  apply; and `nbfc restart` started the daemon *outside* systemd, leaving the
  unit "inactive" while the fans were in fact being controlled.

---

## 9. Appendix — how to reproduce the key measurements

```bash
# What the firmware seeded at POST (logged once per boot, before the first write)
journalctl -t power-profile -b | grep POST

# Current SMU limits
sudo ryzenadj --info

# The CO refusals
sudo ryzenadj --set-coall=0     # set_coall is rejected by SMU
sudo ryzenadj --set-coper=0     # set_coper is rejected by SMU
sudo ryzenadj --set-cogfx=0     # set_cogfx is rejected by SMU
sudo ryzenadj --enable-oc       # set_enable_oc is rejected by SMU

# The EC-facing platform profile
cat /sys/class/platform-profile/platform-profile-0/choices   # cool balanced performance
cat /sys/class/platform-profile/platform-profile-0/profile   # balanced
# (writing a profile does not move the SMU limits)

# Measure how long an OS-written limit survives against the EC
sudo ryzenadj --stapm-limit=35000 --fast-limit=42000 --slow-limit=35000
# then poll:  sudo ryzenadj --info | grep -E 'STAPM LIMIT|PPT LIMIT FAST|PPT LIMIT SLOW'
```

The BIOS menu tree was transcribed (in French) to
`~/Desktop/img_smokelessUMAF/BIOS_arborescence_OMEN.md`, alongside 133 photos of
the SmokelessUMAF menus.

---

## 10. Addendum — §5 is resolved, and §5 was **wrong**

Written after the Windows verdict (`02-curve-optimizer-verdict-windows.md`) came back and
the Linux-side A/B test below was run.

### What §5 claimed

That the EC periodically rewrites the OS-written limits back to `50/65/54`, in
under ~90 s, which is why `power-profile.timer` re-applies every 5 minutes.

### What was actually measured

A controlled A/B with the guard **disabled** for the whole run:

| Phase | Condition | Duration | Result |
|---|---|---|---|
| A | `nbfc` running | 10 min (287 samples) | `35/42/35` — **no reversion** |
| B | `nbfc` stopped | 10 min (287 samples) | `35/42/35` — **no reversion** |

Raw data: `evidence/nbfc_on.csv`, `evidence/nbfc_off.csv`. Script:
`evidence/ec-revert-ab-test.sh`.

### The real trigger

Writing the EC-facing platform profile forces the EC to re-apply its own limits
— **even when writing back the value that is already set**:

```
write 35/42/35                  -> 35.000 42.000 35.000
5 s later                       -> 35.000 42.000 35.000
write platform_profile=cool     -> 54.000 65.000 54.000    # clobbered
write platform_profile=balanced -> 54.000 65.000 54.000
```

So the revert is real but **event-driven by that sysfs write**, not periodic, and
`nbfc` was never the cause. Every "reversion" in the §5 table coincides with a
`platform_profile` write performed by hand during the investigation.

### Corrected conclusions

1. **OS-written power limits are persistent in normal use.** The 35 W / 85 °C
   profile is genuinely in effect; it is not being fought by the EC.
2. `power-profile.timer` is therefore not fixing a periodic EC revert. It still
   protects against anything that writes `platform_profile` on a power-state
   change — whether any daemon does so here remains unverified.
3. **`nbfc` is exonerated**, both as the limit-revert trigger and (from the
   same run) as a fan-side interference.
4. Do not shorten the re-apply interval; if this is revisited, watch for writes
   to `/sys/class/platform-profile/platform-profile-0/profile` instead.
