# The fan curve (HP OMEN 15-en1xxx)

The fans are EC-owned; `nbfc` drives the two duty setpoints (`0x2C`/`0x2D`,
[`ec-map.md`](ec-map.md)) from a temperature table. That table was tuned once, for
the *yoyo* problem — a 12 % floor on the first step, so the EC never fully stops
the fan and oscillates 0↔12 % around 48–50 °C. Nothing had measured what the
curve does **under load** until now.

## Method

[`evidence/fan-trace.sh`](evidence/fan-trace.sh) runs a fixed load and samples
Tctl, both tachos and the nbfc target every 5 s. Every run here: **12 threads,
180 s, on battery** (15 W STAPM, Tctl capped at 65 °C by the profile) — so the
fan's only job is to hold that cap, and there is no risk of the SMU limit being
crossed by a curve change.

## What the three curves do

| curve | steady Tctl | CPU duty | CPU rpm |
|---|---|---|---|
| stock (16 % at 60 °C) | **54 °C** | 16 % | ~900 |
| low thresholds raised +5 °C | **58 °C** | 16 % | ~900 |
| **low-band duties lowered (12/12/15/18 %)** | **60–61 °C** | **12 %** (15 % late) | **~680** |

## The finding: thresholds do not buy silence, duties do

Raising the four lowest thresholds by 5 °C bought **nothing** — the loop
re-equilibrated at the same 16 % duty, only 4 °C hotter. A temperature-driven fan
loop settles where the cooling matches the heat, so moving where a step *starts*
only moves the equilibrium temperature **within the same step**; the duty that
gets chosen is unchanged.

Lowering the **duty** is what changes the rpm: `12/16/20/24 → 12/12/15/18` takes
the same load from ~900 to ~680 rpm, for +6 °C. The steps from 74 °C up are
untouched, so the heavy-load envelope is unchanged, and on battery the SMU caps
Tctl at 65 °C regardless, so the extra degrees are bounded by the firmware rather
than by this curve.

The honest summary: **the curve can trade noise for heat, not remove either.**
The lever that removes the *heat* is the power cap
([`efficiency.md`](efficiency.md)) — and the SoC DPM level already cut the idle
draw. The fan curve only decides how loudly the machine holds whatever the SMU
allows.

## Reproducing

```bash
sudo systemctl stop power-profile-watch.service power-profile.timer   # optional
evidence/fan-trace.sh 180 12
```

Revert the curve with `git checkout HEAD -- my-nbfc.json` in the dotfiles, then
`sudo cp my-nbfc.json /usr/share/nbfc/configs/ && sudo systemctl restart nbfc_service`.
