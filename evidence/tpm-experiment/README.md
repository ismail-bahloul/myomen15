# The TPM experiment: raw snapshots

Fourteen JSON files taken around a three-way TPM toggle. These are the **raw
data** behind [`../efi-nvram.md`](../efi-nvram.md) §7 — kept because that section
is a negative result about *method*, and a negative result is only worth
anything if the data behind it survives.

Reading them back:

```bash
python3 ../setupdiff.py diff baseline-hidden after-hidden
python3 ../tpmstate.py  diff baseline-hidden after-hidden
```

(The scripts write and read these files from the current directory, so run them
from here, or copy a pair out.)

## The sequence

| Order | Snapshot | BIOS state |
|---|---|---|
| 1 | `before-tpm` | TPM disabled (original) |
| 2 | `after-tpm` | TPM **enabled** |
| 3 | `before-disable-tpm` | TPM enabled (unchanged — a control) |
| 4 | `after-disable-tpm` | TPM disabled again |
| 5 | `before-hidden` | TPM disabled |
| 6 | `after-hidden` | TPM **Hidden** |
| 7 | `baseline-hidden` | TPM Hidden (settled state) |

Snapshot 3 is the useful control: it was taken with **no change at all**, and it
is identical to snapshot 2. So the reads are repeatable and the differences
between other pairs are real changes, not read jitter.

## What the data shows

**The TPM enable is a clean boolean** at `Setup` offsets 3–4:

```
before-tpm         0x01 0x01
after-tpm          0x00 0x00
after-disable-tpm  0x01 0x01
after-hidden       0x01 0x01
```

**`Hidden` is a different variable**, not a third value of that field:

```
off      TpmStateFlag=00  PostTpmDetect=01   /dev/tpm0 present
Hidden   TpmStateFlag=00  PostTpmDetect=00   /dev/tpm0 absent
```

**And the method itself does not survive the data.** Returning to "disabled"
did not return to the earlier state — nine offsets in `Setup` differ between
snapshot 1 and snapshot 4, while the TPM setting is the same in both. Saving the
setup moves bytes on its own, and `SetupDefault` / `StdDefaults` drift with it.

That is why naming an offset needs the two-leg method: change, snapshot, revert,
snapshot, and keep only what moves both ways.

## Note on the files

They were written by root (`snapshot` runs under `sudo`) and are mode 0644, so
they are readable without privilege. They contain no secrets — the TPM
variables are state flags, not keys.
