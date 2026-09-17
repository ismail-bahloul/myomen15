# Firmware & hardware limits (HP OMEN 15-en1xxx)

Living reference for what this firmware does and does not allow, so the dead
ends are not explored again. Everything here was measured on this machine.

The point-in-time investigation record is in `record/` in this repository; this
file is the distilled, current conclusion.

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

## Undervolt / Curve Optimizer: locked by HP (dead end)

Not possible on this machine — on **either** OS. Six independent confirmations:

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

## BIOS modding: not possible (HP Sure Start)

`hp-bioscfg` reports **HP Sure Start** active, which verifies and restores the
firmware on tamper. On top of that the flash chip is shared with the EC (fan
control), and `flashrom` is deliberately not used here: a failed write would
risk the fans. The `BIOS_Update.exe` payload is a proprietary AMI container
(`@UAF@` / `@UII@`) that `uefixtract` does not recognise, so the image cannot
even be extracted for offline inspection.

## Power limits: they stay put, but writing `platform_profile` resets them

`ryzenadj` writes **do** take (writing `37/44/37` reads back `37/44/37`
immediately and still after 27 s), and a controlled A/B run with the guard
disabled shows they **stay put**: an OS-written `35/42/35` held unchanged for
**10 minutes with `nbfc` running and 10 minutes with `nbfc` stopped**, with no
reversion at all (`evidence/nbfc_{on,off}.csv`, 287 samples each).

The one thing that *does* clobber them is a **write to the EC-facing platform
profile**:

```
write 35/42/35                  -> 35.000 42.000 35.000
write platform_profile=cool     -> 54.000 65.000 54.000    # clobbered
write platform_profile=balanced -> 54.000 65.000 54.000
```

So the HP EC re-applies its own limits (`54/65/54` here, seen as `50/65/54` in
one earlier sample) whenever
`/sys/class/platform-profile/platform-profile-0/profile` is written — **even
when writing back the value it already has**.

An earlier conclusion in this repo — *"the EC periodically reverts the limits,
hence the 5-minute re-apply timer"* — was **wrong**. Those reverts were the
platform-profile writes performed by hand during the investigation, and `nbfc`
was never the cause. What `power-profile.timer` still protects against is
anything that writes `platform_profile` on a power-state change; whether any
daemon actually does here is unverified. The investigation script is kept at
`evidence/ec-revert-ab-test.sh`.

## Not supported by the kernel / firmware

- **Battery charge thresholds**: `powerdevil` reports "not supported by kernel".
  `hp-bioscfg` exposes only `Sure_Start` and `pending_reboot`; the `BCTC` /
  `BMNC` ACPI objects are read-only in the DSDT and their writes go to an opaque
  SMM handler.
- **Serial port**: `8250.nr_uarts=0` was measured to save ~0 — the `ttyS*`
  devices are not on the critical path — so `limine.conf` was left untouched (it
  carries the VFIO entry).
- **TPM** is disabled in the BIOS.

## EC access (mapped, partially)

The EC is reachable through `ec_probe` (based on `ec_sys`), and its fan and
temperature registers are now identified and verified — see
[`ec-map.md`](ec-map.md). `nbfc` already drives the fan setpoints through the same
path, so the write half has a working reference.

What was tested and **ruled out**: the EC does not hold the SMU power limits.
Dumping the EC before and after a `ryzenadj` write, with a no-op control run to
account for telemetry drift, produces indistinguishable diffs — the limits live
in the SMU only. So the [platform profile
reset](#power-limits-they-stay-put-but-writing-platform_profile-resets-them) is not
the EC re-asserting a stored limit.

---

See also [Boot tuning](https://github.com/ismail-bahloul/dotfiles/blob/main/docs/boot-tuning.md)
in the dotfiles repository, for the boot-time work and what is still on the table
there.
