# The deployed power config — audited against its own intent

This is a read-only audit of the config that actually runs on this machine:
`/usr/local/bin/power-profile` (+ `power-profile-watch`, `power-profile.{service,timer}`),
`nbfc`, and the GPU locks. It records what each lever was *measured* to do, not
what the script's comments claim, and it is checked against the three goals the
config is meant to serve:

- **default / AC**: silence, coolness, overall efficiency;
- **battery**: minimum power draw (autonomy);
- **PERF**: unlock the machine.

Method: stop `power-profile-watch.service` and `power-profile.timer`, apply each
mode with `power-profile <mode>`, and read the result back — from the SMU PM
table (one 2372-byte read), `ryzenadj --info`, `nvidia-smi`, `iw`, and the `hp`
hwmon. Runtime only; nothing is written to flash.

## What each mode actually sets

Diffed from `ryzenadj --info`, `ryzenadj --info | diff` between modes. Only the
limit fields move; the live values move on their own. The firmware seeds
`54 / 65 / 54` at POST, and `power-profile` overwrites it within ~12 s.

| Field | battery | AC | PERF |
|---|---|---|---|
| STAPM LIMIT | 15 W | 28 W | 54 W |
| PPT LIMIT FAST | 18 W | 36 W | 65 W |
| PPT LIMIT SLOW | 15 W | 28 W | 54 W |
| PPT LIMIT APU | 15 W | 22 W | 42 W |
| THM LIMIT CORE | 65 °C | 85 °C | 90 °C |
| `scaling_governor` | powersave | powersave | performance |
| `scaling_max_freq` | 2.4 GHz | 4.465 GHz (no cap) | 4.465 GHz |
| EPP | `power` | `balance_power` | `performance` |
| dGPU clock lock | `-lgc 0,400` | `-lgc 500,1800` | `-lgc 500,2100` |
| dGPU memory | `-lmc 405` | released (`-rmc`) | released (`-rmc`) |
| WiFi power save | on | off | (untouched) |

TDC and EDC limits (58 / 15 / 110 / 20) are **never written** — they stay at the
POST values in every mode. That is deliberate-looking (they are not the binding
constraint at these power caps) but is not stated anywhere; noted here so it is
not mistaken for a policy.

## Findings (each verified)

1. **The dGPU memory-lock fix is real.** Under GPU load on AC, `clocks.mem`
   reaches **6001 MHz** — the lock `battery` sets (`-lmc 405`) is released by
   `apply_ac`'s `-rmc`. Before the fix the memory stayed at 810 MHz (~13 % loss)
   for the whole AC session. See [`dgpu-control.md`](dgpu-control.md).
   Repro: `/tmp/gpuload & nvidia-smi --query-gpu=clocks.mem --format=csv`.
2. **`platform_profile` is a trigger, not a power lever.** Writing
   `/sys/firmware/acpi/platform_profile` (`cool` / `balanced` / `performance`)
   does **not** move the SMU limits (28/36/28 held across all three) and does not
   measurably move fan rpm. It is watched by `power-profile-watch` so that a
   profile write re-applies the config, and that is its only observed effect.
   (An earlier read of `54/65/54` right after a write was a transient artefact,
   not the write: it did not reproduce with the watcher stopped and a clean
   apply first.)
3. **The WiFi power-save lever works.** `wlan0` exists, and
   `iw dev wlan0 get power_save` reads `off` on AC — matching `apply_ac`.
   So the battery side's `power_save on` is not a silent no-op.
4. **No `CCLK` asymmetry.** `/usr/bin/ryzenadj --power-saving` (battery) does
   **not** change `CCLK Boost SETPOINT` (stayed 95 across battery → AC → PERF),
   so the "sticky `--power-saving` that AC never undoes" that the pattern invites
   does **not** exist here.
5. **Fans are `nbfc`'s alone.** `nbfc` runs the custom `my-nbfc` curve
   (silence-first: 12 % at 50 °C, ~40 % at 83 °C, 100 % at 100 °C), auto control
   on both fans, critical temp 100 °C. `power-profile` never touches fans, so
   there is no lever conflict.

## The dGPU cannot sleep — and why (autonomy)

On AC the dGPU sits at **~17 W idle** (`clocks.gr` 510 MHz, `clocks.mem`
810 MHz) and `power/runtime_status` is `active`. Three separate things hold it
awake, and only one of them is the current session's fault:

1. **An external monitor is attached.** `card0-DP-2` (the dGPU's output) reads
   `connected`; the internal panel (`card1-eDP-1`) is on the *iGPU*. So while the
   external display is plugged in, the dGPU must stay powered — expected, not a
   misconfiguration.
2. **`nvidia-persistenced.service` is enabled and active.** Keeping the NVIDIA
   driver initialised is exactly what that daemon does, and it prevents the GPU
   from powering down. It is the first thing to stop for a no-monitor battery
   session.
3. **`nbfc` holds `/dev/nvidia0` open.** The `my-nbfc` GPU fan curve reads the
   `@GPU` sensor (NVML), and `lsof` shows `nbfc_service` with the device open — so
   the GPU cannot suspend while the fan curve polls it. The EC exposes GPU
   temperature directly ([`ec-map.md`](ec-map.md)), so a curve built on that
   would not hold the GPU awake.

Releasing the clock locks does **not** change this: after `nvidia-smi -rgc -rmc`
the graphics clock fell to 405–450 MHz but power stayed ~17 W and
`runtime_status` stayed `active`. So the AC floor (`-lgc 500,…`) is not what
keeps the GPU on; the display load dominates its idle draw.

**Not verified:** whether the dGPU actually suspends (and drops to a few watts)
once the monitor is unplugged *and* both holders above are removed. It cannot be
tested with the external display attached, and unplugging is a manual step. The
levers are recorded here so that a battery-autonomy pass can test them.

## Verdict against the goals

- **Silence / cool (AC):** consistent. 28 W cap + no frequency cap (so light work
  still boosts — see [`efficiency.md`](efficiency.md)) + a silence-first fan
  curve + a 1800 MHz dGPU ceiling.
- **Autonomy (battery):** the levers are all pointed the right way (15 W, 2.4 GHz,
  EPP `power`, dGPU 400 MHz, memory 405 MHz, WiFi power-save on).
- **PERF:** raises every CPU limit and unlocks both GPU clock families, with the
  `-lgc 500,…` floor kept because deep P8 sleep is the real cause of app-launch
  micro-freezes — not the CPU clock.

No bug was found in this pass (the memory-lock bug had already been fixed and is
re-verified above).

## Nuances left as-is

- **The AC 1800 MHz dGPU cap does little under load.** With memory at 6001 MHz a
  compute load already hits the GPU's **80 W** vBIOS default (`power.limit` is
  `N/A` — not settable below the vBIOS, which is why Windows Afterburner showed
  no power slider either; see [`dgpu-windows-undervolt.md`](dgpu-windows-undervolt.md)).
  So capping graphics to 1800 mostly trims idle/near-idle draw, not the loaded
  ceiling. Left as-is: it is a silence lever, and lowering it further would trade
  real GPU throughput for little heat.
- **`PPT LIMIT APU` on battery is 15 W** — the same as STAPM. The iGPU is unused
  on battery (the dGPU is locked to 400 MHz, not powered off), so this cap only
  bounds the SoC under load. It is a limit, not a floor, so idle draw is
  unaffected; not tightened, because a tight APU cap can slow SoC work
  (memory controllers, display) for no measurable idle gain.
- **`platform_profile` is left at `balanced`.** It is the only one of the three
  choices that is not "more cooling" (`cool`) or "more power" (`performance`);
  since it has no power effect here and fans are `nbfc`'s, `balanced` is the
  right neutral resting value.
- **`--power-saving` (battery) is an opaque SMU hint.** `ryzenadj` reports
  `Successfully enable power_saving`, but a full `ryzenadj --info` diff before/after
  shows **no** change to any limit or to `CCLK Boost SETPOINT`. Its own `--help`
  calls it a "hidden option ... behavior depends on CPU generation, Device and
  Manufacture", so it is a hint to the SMU, not a register this surface can read
  back. It is harmless and semantically right for battery; it just cannot be
  credited with a visible effect here.
