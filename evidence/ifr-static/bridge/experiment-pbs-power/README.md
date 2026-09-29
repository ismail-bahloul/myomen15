# Experiment: is the AMD PBS power-adjust knob real or inert?

## The question

`AMD_PBS_SETUP` offsets **111–117** are *"Power limit adjustment percent for
[profile] on AC/DC: 0 - 100"*, all currently `0`. The repo already proved the
**AMD CBS** power selector is inert (the HP EC overrides it — `firmware-limits.md`).
These PBS fields are a **different** mechanism, and were never tested. Do they
move the SMU limits, or are they inert too?

| off | field |
|---|---|
| 111 | Maximum Performance, AC |
| 112 | Better Performance, AC |
| 113 | Better Battery, AC |
| 114 | Maximum Performance, DC |
| 115 | Better Performance, DC |
| 116 | Better Battery, DC |
| 117 | Battery Saver, DC |

Hypothesis **H1**: setting one to `>0` raises the corresponding SMU limits.
Null **H0**: no movement — inert, like CBS.

## Method (measure first, one change, revert, watchdog)

Do **not** skip the baseline; the lesson of `firmware-limits.md` is that a value
read without first making it distinctive proves nothing.

1. On **AC**, profile `performance` (so the AC fields are the ones in play):
   ```
   ./probe.sh > before.txt
   ```
   Record `STAPM LIMIT` / `PPT LIMIT FAST`.
2. Build and stage the change (a deliberately large, unambiguous value — 30):
   ```
   cd .. && BRIDGE_OUT=out python3 ../bridge.py build AMD_PBS_SETUP \
       "Maximum Performance] on AC=30"
   ./arm.sh AMD_PBS_SETUP            # copies .dat + startup.nsh to the ESP
   ```
3. Arm the one-shot boot to the Shell, reboot (see [`../README.md`](../README.md)).
   The watchdog auto-reverts if the change stops the boot.
4. Back on AC, profile `performance`:
   ```
   ./probe.sh > after.txt
   ```
5. Compare `before.txt` / `after.txt`.

## Decision rule

- **Limits moved** (`PPT LIMIT FAST` 54 → ~70 for +30 %) → **H1**: a real,
  previously unknown power lever. Worth characterising (which profile maps to
  which field, and how it interacts with `ryzenadj`).
- **No movement** → **H0**: inert. One line added to the dossier, revert, done.

Either way: **revert**, and confirm the revert with another `probe.sh`.

## Notes and limits

- The mapping between the firmware's four AMD profiles and this machine's
  `platform_profile` (`cool`/`balanced`/`performance`) is **not** known; if the
  change is invisible, the fields may simply be bound to a profile the EC never
  selects. That is a result too, and it is why a *large* value is used.
- Baseline recorded on **battery** (`baseline-dc.txt`, profile `balanced`,
  15/18 W) — the AC baseline must be taken on AC.
- The 7 fields are `op=0x07` (numeric); a byte write is `percent`, domain 0–100.
- Reading the limits is unprivileged in effect but `ryzenadj --info` needs root;
  `probe.sh` uses `sudo -n`.

## Result (2026-09-29, battery, profile `balanced`)

Set `114–117 = 30` (the DC fields), rebooted. The Shell applied it —
`poke-result.txt`: `DataSize = 0x88`, and the live variable came back
`114–117 = 30` (`poke-*.dat` deleted, `armed.txt` written). The SMU limits
**did not move**:

```
STAPM 15.000 | PPT FAST 18.000 | PPT SLOW 15.000 | TDC 58/15 | EDC 110/20 | THM 65
```

Identical before/after (`baseline-dc.txt` vs `after.txt` — only the timestamp
differs). **H0 on DC/`balanced`.** Consistent with the AMD CBS power selector
being inert (`firmware-limits.md`): the AMD PBS adjustment is apparently not a
live lever either — at least not for the profile selected on battery.

Still untested: the AC fields (`111–113`), and the profile↔field mapping, so a
false negative from "wrong profile" cannot be fully excluded. But the size of
the value (+30) and the absence of *any* movement point at inert.

## Result, AC (2026-09-29, on AC, profile `balanced`)

Set `111–113 = 30` (the AC fields) and rebooted. Applied again
(`DataSize = 0x88`; live variable `111–117 = 30`). SMU limits **unchanged**:

```
STAPM 28.000 | PPT FAST 36.000 | PPT SLOW 28.000 | APU 22.000 | THM 85
```

Identical to `baseline-ac.txt`. **H0 on AC as well.**

**Conclusion:** the AMD PBS "power limit adjustment percent" is inert on both
DC and AC — the write lands, the firmware ignores it, exactly like the AMD CBS
power selector above. With this, no firmware-side power lever remains on this
machine; `ryzenadj` is the only thing that moves the SMU limits.

## What this does not test

Whether the knob, if real, beats `ryzenadj` (which writes the SMU directly and is
already the proven lever). This only asks whether the *firmware* field is live.
