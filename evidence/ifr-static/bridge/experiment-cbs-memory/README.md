# Experiment: is the AMD CBS memory (UMC) lever real or inert?

## The question

`AmdSetup` (the AMD CBS answers, 1448 B) holds the full UMC memory menu — clock
frequency, CAS, tRFC, turnaround timings, interleaving, ECC, power-down. The
machine's `README` open front said: *"The memory side — the firmware's own SPD
table names a module that is not installed; the lever is `AMD CBS > UMC Common
Options`."*

The **power** knob is inert (`firmware-limits.md`, and the PBS knob in
[`../experiment-pbs-power/`](../experiment-pbs-power/)). But power is owned by
the HP EC; the **DRAM timings are AGESA/PSMC**, a subsystem the EC does not
touch — so this was the best remaining candidate for a lever that *works*.

Hypothesis **H1**: a UMC change takes effect. Null **H0**: inert too.

## Method

The cleanest OS-visible signal is SMBIOS `Configured Memory Speed` (the actual
configured rate, not the SPD rated one) — so no benchmark and no noise.

1. Baseline: `./probe.sh` → both modules `Speed: 3200 / Configured: 3200`.
2. Change `off=75` (*"Specifies the memory clock frequency"*, `0xFF` = Auto) to
   `0x4C` = value **76 = 2600 MHz** — a deliberate **under**clock, so it cannot
   fail training upward:
   ```
   cd .. && BRIDGE_OUT=out python3 ../bridge.py build AmdSetup "memory clock frequency=76"
   ```
   `poke-AmdSetup.dat` / `revert-AmdSetup.dat` (CRC ok).
3. Reboot via the Shell; the watchdog applies it (`DataSize = 0x5A8`).

## Result (2026-09-29)

The write landed — the live variable came back `off=75 = 0x4C` — but the memory
did **not** change:

```
Speed: 3200 MT/s / Configured Memory Speed: 3200 MT/s   (before)
Speed: 3200 MT/s / Configured Memory Speed: 3200 MT/s   (after)
```

**H0.** The CBS memory lever is inert as well. Consistent with the reason: the
memory controller is programmed from the **signed `APCB`** blocks in the flash
(the SPD/part-number tuning tables), not from the `AmdSetup` variable — which is
also why these options are greyed out in the menu to begin with. Storing a
different answer in NVRAM changes nothing.

## Consequence

With this, **the whole AMD CBS/PBS family is inert** on this machine — power
(PBS + CBS), and now memory. The only firmware-adjacent levers that do anything
are the OS-side ones (`ryzenadj`, `nvidia-smi --lock-gpu-clocks`, the EC bridge).
