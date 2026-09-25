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

Measured **on battery, external monitor unplugged, battery profile active** (so the
dGPU clocks are locked to 0–400 MHz / memory 405 MHz):

| | value |
|---|---|
| whole-system draw | **~20 W** (stable over 12 s) |
| dGPU alone (`nvidia-smi power.draw`) | **~10–12 W** |
| dGPU `power/runtime_status` | `active` |
| dGPU clocks / temp | 210 / 405 MHz, 42–44 °C |

The dGPU is therefore **about half of the idle power draw**, and it is awake, not
throttled. (Caveat: `power.draw` is the GPU's own board estimate; the two figures
are consistent in that the non-GPU remainder ~9 W is a plausible 5800H idle +
panel + RAM. With the monitor still attached it read ~17 W.)

**What holds it, by elimination.** `nvidia-persistenced` and `nbfc` are **not**
the blockers: stopping both (12 s each, with no `nvidia-smi` call — which would
itself hold the GPU) left `runtime_status=active`. The holders are the desktop
itself:

| process | open `/dev/nvidia*` fds |
|---|---|
| `kwin_wayland` | ~34 |
| `plasmashell` | ~16 |
| `zed-editor` | ~14 |

KWin *renders* on the iGPU — `qdbus6 org.kde.KWin /KWin supportInformation`
reports `OpenGL renderer string: AMD Radeon Graphics (radeonsi, renoir)` — and
the panel is on the iGPU (`card1-eDP-1`). The NVIDIA is `card0` because it is the
**boot VGA** (`nvidia_drm modeset=Y`). KWin nonetheless opens *both* DRM nodes
(its support info lists `Atomic Mode Setting on GPU 0: true` **and** `GPU 1:
true`), which is the leading explanation for its nvidia handles; whether that is
DRM enumeration alone or includes a stale GL context is **not settled**.

**This corrects the battery profile's premise.** `apply_battery` locks the dGPU
to 0–400 MHz and its memory to 405 MHz, but the cost here is *awake vs
suspended*, not *high clock vs low clock*: releasing the clocks on AC left power
unchanged at ~17 W, and on battery the GPU is locked low and still draws ~11 W.
Those locks bound *load* power; they save nothing at idle.

Levers, none of which are testable from here (a re-login, or the user's hands):

1. **`KWIN_DRM_DEVICES=/dev/dri/card1`** so KWin never opens the nvidia node.
2. Keep **Zed** (and other Vulkan/GL apps) off the discrete GPU — Vulkan picks the
   3070 by default because it is `card0`.
3. **Stop `nvidia-persistenced`** — no effect alone, but part of the set.
4. Point **`nbfc`'s GPU sensor** at the EC temperature instead of NVML.

**Not verified:** that the four together actually let the dGPU suspend (and drop
to a few watts). That needs a re-login with (1) applied and a re-measure of the
battery draw. It is the single highest-value autonomy experiment left: at ~20 W
with ~11 W of it asleep-able, the upside is on the order of **2× battery life**.

## The other boot entry already does it (measured)

The Limine config has an entry that binds the dGPU to `vfio-pci`
(`vfio-pci.ids=10de:249d,10de:228b`). It is the strongest autonomy lever on this
machine — stronger than anything `power-profile` can do. Measured on battery,
both boots, stable over 16 s:

| | normal boot (nvidia driver) | **VFIO boot** |
|---|---|---|
| dGPU | `active`, ~10–12 W | `runtime_status=suspended` |
| whole-system draw | ~20 W | **~13.3 W** |
| idle Tctl / fan1 | ~48 °C / ~660 rpm | 47.8 °C / 672 rpm |
| external DP monitor | works | **dead** (DP is wired to the dGPU) |
| dGPU usable (games / CUDA / VM passthrough) | yes | no |

So the VFIO entry removes **~6.7 W — 33 % of the battery draw**, about **1.5× the
runtime**. That is more than the whole CPU-profile story is worth, and it needs no
policy: it is just "the dGPU is not there".

**It is D3hot, not D3cold.** The GPU's ACPI node exposes **no `_PR3` power
resource** (`firmware_node/power_resources` is empty), so the platform cannot cut
its power; `vfio-pci` runtime-suspends it, which is D3hot / `suspended`. The win
is real regardless — the mechanism is that the nvidia stack is gone and *nothing
holds the device*, not that the silicon is unpowered.

Consequences: on this boot `nvidia-smi` does not exist, so `apply_battery`'s
`-lgc` / `-lmc` lines are no-ops (the `|| true` keeps that safe), and
`power-profile info` already has a `VFIO (off)` branch. The rest — 15 W, 2.4 GHz,
EPP `power`, WiFi power-save — applies normally (verified: STAPM 15 W, Tctl 65,
watcher/timer/nbfc active). This also makes the `KWIN_DRM_DEVICES` route *above*
the second-best option, for sessions that need the dGPU present.

## The two tradeoffs the config assumes

These are the only places the config makes a real bet. Both are decisions to
*keep*, not bugs.

**1. `TDP_AC=28 W` — a cooling/efficiency bet, not just "cooler".** The 5800H
ships configurable 35–54 W and HP seeds it at 45 W, so 28 W is well below stock.
The measured cost and gain (same harness as [`efficiency.md`](efficiency.md)):

| AC config | all-core | PPT-slow | Mi/s per W |
|---|---|---|---|
| 35 W, no cap | 6956 Mi/s | 34.18 W | 204 |
| 28–30 W, no cap | 6676 Mi/s | 28.88 W | **231** |

So 28 W costs **~4 %** sustained all-core throughput and buys **~13 %** better
work per joule. That is the right side of the trade for the stated priority
(silence, coolness, overall efficiency) — the "fast" burst limit of 36 W keeps
short tasks off the cap. The one thing not yet cross-checked is the *workload*:
these are FP-spin numbers, and a branchy/integer load (Cinebench-class) could
shift them. Worth one cross-check before treating the 4 % as universal, not
before keeping the setting.

**2. The dGPU power limit is not a choice — it is locked.** `nvidia-smi` reports
`power.default_limit 80 W`, `power.min 1 W`, `power.max 100 W`, which invites
"raise it to 100 W for PERF". It cannot be raised:

```
sudo nvidia-smi -pl 100
Changing power management limit is not supported for GPU: 00000000:01:00.0.
```

The same vBIOS lock is why Windows Afterburner offered no power slider
([`dgpu-windows-undervolt.md`](dgpu-windows-undervolt.md)). There is nothing to
decide here; the GPU always runs at its 80 W default.

## Known fragility: `guard` keys off the governor

`power-profile guard` (what the watcher and the timer invoke) refuses to apply
when `scaling_governor == performance`:

```bash
if [ "${1:-}" = "guard" ] && [ "$(cat .../scaling_governor)" = "performance" ]; then
    log "guard: PERF mode active, re-apply ignored"; exit 0
fi
```

That signature is *"the governor is performance"*, which `gamemode`, `cpupower`,
or any game launcher can also set. During such a window `guard` stops applying,
so: (a) the drift is no longer corrected, and (b) an AC→battery switch in that
window would not get the battery limits. The window is usually a game (where the
28 W cap is not wanted anyway), so the practical exposure is small — but a mode
marker (`/run/power-profile.mode`) written by the profile itself would be more
robust than sniffing a global the rest of the system also writes. Left as-is
because the fix adds state that must be cleared on boot/shutdown.

## Verdict against the goals

- **Silence / cool (AC):** consistent. 28 W cap + no frequency cap (so light work
  still boosts — see [`efficiency.md`](efficiency.md)) + a silence-first fan
  curve + a 1800 MHz dGPU ceiling.
- **Autonomy (battery):** every *policy* lever is pointed the right way (15 W,
  2.4 GHz, EPP `power`, dGPU 0–400 MHz, memory 405 MHz, WiFi power-save on) —
  but the largest single draw is **not** one of them: the dGPU stays awake at
  ~10–12 W of the ~20 W total in the normal boot. The real solution is not a
  profile at all but the **VFIO boot entry**, which removes the dGPU from the
  system entirely: ~20 W → **~13.3 W** (−33 %). See the two sections above.
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
- **`iw dev wlan0` is hard-coded** in all three modes. It works here (`wlan0`
  exists, `iw dev wlan0 get power_save` reads `off` on AC), and the `|| true`
  means a rename would fail *silently* rather than crash. Harmless today; noted
  so a future interface rename is not mistaken for "power save is handled".
- **`--power-saving` (battery) is an opaque SMU hint.** `ryzenadj` reports
  `Successfully enable power_saving`, but a full `ryzenadj --info` diff before/after
  shows **no** change to any limit or to `CCLK Boost SETPOINT`. Its own `--help`
  calls it a "hidden option ... behavior depends on CPU generation, Device and
  Manufacture", so it is a hint to the SMU, not a register this surface can read
  back. It is harmless and semantically right for battery; it just cannot be
  credited with a visible effect here.
