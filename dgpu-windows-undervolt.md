# MSI Afterburner on the dGPU — what to capture, and what to expect back

[`dgpu-control.md`](dgpu-control.md) ends by naming the one lever it did not
test: a real GPU undervolt, which lives on **Windows**, through a V/F-curve
tool. The machine dual-boots Windows 11, so it is reachable — this page is the
protocol to capture what Afterburner actually offers on this *laptop* dGPU, and
what can be brought back to Linux.

**Ran on 2026-09-24 — → [Result](#result-measured-2026-09-24).** The trip is
done, and it did not go the way the page hoped: the power limit and the voltage
are refused on Windows exactly as they are on Linux, the core clock offset is a
control that reports success and does nothing, and the V/F curve editor is real
— but it is a **clock** lever, not a voltage one.

It is a **manual protocol**, like [`setup-offset-naming.md`](setup-offset-naming.md):
the Windows half needs your hands, the Linux half is tooling.

## What Linux already exposes (the target to compare against)

Measured on this machine (driver `615.71.09`, vBIOS `94.04.3D.00.C3`):

| Lever | Linux | Evidence |
|---|---|---|
| Lock the GPU clock | ✅ works | `nvidia-smi --lock-gpu-clocks`; 80 W → 41 W at a 1000 MHz cap |
| Lock the memory clock | ✅ accepted | `nvidia-smi --lock-memory-clocks` |
| **Power limit** | 🔴 not settable | `power.limit` queries `[N/A]`; `-q -d POWER` shows the limit *reported* (80 W default, 100 W max) but not user-enforced |
| Clock **offsets** (whole curve) | 🟡 X11 + Coolbits only | attributes exist and read (−1000…+1000 MHz); writes refused on Wayland |
| **Voltage / V/F curve** | 🔴 not exposed | `nvidia-smi -q -d VOLTAGE` prints no readings; `voltage.gpu` is not a valid field |

So the two questions the Windows trip can settle are exactly the two Linux
refuses: **can the power limit be set, and can the voltage?**

## Result (measured 2026-09-24)

Driver `610.88` on the Windows side (`615.71.09` on Linux, same vBIOS
`94.04.3d.00.c3`). Afterburner 4.6.6, load MSI Kombustor 4, on AC power. Raw
1 Hz logs are local in `evidence/dgpu-windows/` (36 MB, not versioned); the
extracted windows are versioned as `evidence/dgpu-windows/windows.txt`.

### Verdict per control

| Control | Verdict | Evidence |
|---|---|---|
| **Power Limit (%)** | 🔴 **greyed out** | not draggable — the same refusal `nvidia-smi -pl` gives on Linux |
| **Temp Limit (°C)** | 🔴 greyed out | same |
| **Core Clock (MHz)** offset | ⚪ **inert — the slider lies** | −300 MHz: 1267.75 → 1264.25 MHz mean, at the same 79.3 W |
| **Memory Clock (MHz)** offset | ✅ works | +500 MHz: 6001 → 6501 MHz, on **both** instruments |
| **Core Voltage (mV)** | 🔴 greyed out | in all four unlock modes; no monitoring column either |
| **V/F curve editor** (`Ctrl+F`) | ✅ applied **and enforced** | a ~700 MHz plateau pins the card at 660-705 MHz under a 100 % load |

The memory offset is what makes the core-offset result mean something: it proves
the write path reaches the driver on this machine. So the core offset is not a
tool that failed — it is a control that reports success and does nothing.

### The two questions, answered

**Can the power limit be set?** **No — and Linux is not the reason.** The slider
is greyed on Windows exactly where NVML refuses. Whatever withholds the power
target from `nvidia-smi -pl` withholds it from NVAPI too: this is the vBIOS, not
the OS. The wildcard is closed, negatively.

**Is the undervolt a voltage change or only a clock change?** **Only a clock
change — and not even a power-saving one.** The decisive measurement is a step
inside a *single continuous load*, plateau lifted at 17:16:51 while usage stayed
at 100 %:

| | `core clock` | `power` |
|---|---|---|
| curve plateau ~700 MHz (n=55) | **670 MHz** avg (660-705) | **69.34 W** |
| after `Reset`, same load (n=15) | **1221 MHz** avg (1155-1275) | **78.72 W** |

Giving up **45 %** of the clock buys **12 %** of the power. That is the shape of
a **frequency clamp**, not a voltage map: the card stays near its power ceiling
at half the clock, which is what you would see if the voltage were still being
picked by the stock algorithm. A real V/F edit would show the opposite — less
power for the same clock. There is no voltage lever on this card at all.

### The comparison that matters

Same machine, same GPU, two OSes:

| Path | Result |
|---|---|
| Linux `nvidia-smi --lock-gpu-clocks=0,1000` | **1000 MHz at 41 W** |
| Windows, V/F curve plateaued at ~700 MHz | **670 MHz at 69 W** |

Linux's clock lock makes the card *re-select a lower voltage* — 41 W to hold
1000 MHz. Afterburner's curve does not: 69 W to hold 670 MHz. They are not
equivalent levers, and for cutting power the Linux one is the better instrument.
The Windows half of this page has nothing Linux lacks.

## Capture protocol (Windows)

1. Install **MSI Afterburner** (and RivaTuner Statistics Server, which it
   bundles — the hardware-monitor log comes from it).
2. **Turn off "Apply at startup"** and never let the profile persist before you
   know what it does. In the same *General* tab, tick **Unlock voltage control**
   and **Unlock voltage monitoring** — both ship off (`UnlockVoltageControl`
   and `UnlockVoltageMonitoring` are `0` in the shipped `MSIAfterburner.cfg`),
   and with monitoring off there is no voltage column to read at all.
3. Settings → **Monitoring** → enable and tick "log to file" for at least:
   *GPU2 core clock, GPU2 memory clock, GPU2 power, GPU2 temperature, GPU2
   usage*, plus *GPU2 power limit* if the list offers it, and a *voltage*
   column if one exists at all.

   **Which GPU is which — measured, not assumed.** Afterburner numbers the
   hybrid pair with the iGPU first: `GPU1` is the **AMD Radeon(TM) Graphics**
   (Cezanne iGPU), `GPU2` is the **RTX 3070 Laptop GPU** — read off
   `HardwareMonitoring.hml`'s own device line, not guessed. Every column above
   must be `GPU2…`; logging `GPU1` measures the iGPU and answers nothing. (This
   page said `GPU1` before it was checked.)

4. A GPU load that saturates the card — Afterburner's own **Kombustor**, or any
   CUDA workload (the Linux side uses `evidence/gpuload.cu`). **On a hybrid
   machine this is where the session silently fails**: a windowed load can land
   on the iGPU and leave the dGPU at idle. Force it — Windows *Settings →
   System → Display → Graphics* → add `MSI-Kombustor-x64.exe` → *High
   performance* — and confirm with `nvidia-smi` that the 3070 is the one at
   ~99 % and ~80 W before trusting any log. *(The Windows Graphics preference
   binds at process start: close and relaunch Kombustor after setting it.)*
5. **Read the monitor's own log instead of clicking "log to file" per pass.**
   Afterburner already writes `HardwareMonitoring.hml` beside itself
   (`EnableLog=1`, `LogPath=%ABDir%\HardwareMonitoring.hml`): plain text, one row
   per second, the column names in its own header, and — verified — every
   property it can read, not just the ones ticked in the graph list (all
   `ShowInOSD` were `0`, and the log still carried `GPU2 power`). Copy that file
   per pass and parse it with [`evidence/hml-analyze.py`](evidence/hml-analyze.py):
   no RTSS CSV, no per-pass clicking, and no keyword-matching on the columns.
   Its `01, …` device line is also what settles GPU1/GPU2.

   The passes as they were actually run, one change each:
   - **P0 stock** — no offsets, load only. *1267.75 MHz @ 79.34 W.*
   - **P1 core offset** — core clock slider −300 MHz, apply, load.
   - **P1b memory offset** — memory clock slider +500 MHz, apply, load. *This is
     the control that proves the write path is alive; run it before concluding
     anything from a slider that did nothing.*
   - **P2 curve** — `Ctrl+F`, plateau the curve, apply, load.
   - **P3 power limit** — greyed out; nothing to run.
6. **Judge a cap by the ceiling, not the mean.** The Kombustor workload drifts
   by ±65 MHz on its own — measured inside one untouched load: 1295 MHz over its
   first 20 s, 1230 MHz over its last 20 s. Any effect smaller than that is
   invisible in a pass-to-pass mean, but a *cap* clips the top of the
distribution, and the maximum is robust to drift.
7. **For a small effect, toggle it while one load keeps running** and look for a
   step — and note the wall-clock time of the click, or the log cannot be split.
   (The pass that settled this page needed no timestamp: the step was a 550 MHz
   cliff inside a continuous load.)

## The decisive questions — and what they came back as

- **Is the voltage slider live?** **No.** Greyed in all four unlock modes and
  the monitor never gains a voltage column (89 properties; only `GPU2 voltage
  limit`, a 0/1 flag). Nothing to replicate on Linux, because there is nothing.
- **Is the undervolt a voltage change or only a clock change?** **Only a clock
  change**, and a costly one — 670 MHz at 69.34 W against 1221 MHz at 78.72 W in
  the same load. A real V/F edit would show the opposite. No voltage is being
  touched anywhere on this card.
- **Can it set the power limit?** **No.** Greyed on Windows exactly where
  `nvidia-smi -pl` refuses on Linux, so the `NvAPI_GPU_SetPowerTarget` path is
  closed to this vBIOS too. Not an OS difference.

## Linux-side reception

1. On an **X11** session with Coolbits (the NVIDIA-side test the repo could not
   do on Wayland) — **not run in this session**:
   ```
   # /etc/X11/xorg.conf.d/20-nvidia-cb.conf
   Section "Device"
       Identifier "nvidia"
       Driver     "nvidia"
       Option     "Coolbits" "8"
   EndSection
   ```
   Log into X11, then `./evidence/nv-surface.sh /tmp/nv-x11.txt`. If the
   `GPUGraphicsClockOffset…` attributes now *write*, the clock-offset half is
   replicable; if they still pull, that path is closed too.
2. Run `./evidence/hml-analyze.py <pass>.hml --windows` — one row per contiguous
   loaded window, with the memory clock acting as a fingerprint of which pass it
   was. (`ab-log-analyze.py` stays for RTSS CSV logs, if they are ever used.)
3. Compare against `nv-surface.sh`'s output: does anything Linux exposes move
   the same numbers? The honest expectation:

   - **Voltage will not be portable.** Linux has no V/F lever at all, so the
     best outcome is a measured curve — useful for knowing how much headroom an
     undervolt *would* give, not for applying it here.
   - **The clock-offset half may be**, on X11 + Coolbits — and it is an
     underclock, the same shape as `--lock-gpu-clocks`, only curve-wide.
   - **The power limit is the wildcard.** If Afterburner sets it and Linux's
     `-pl` still refuses, that is a genuine, named difference worth recording.

## Safety

- An undervolt on a laptop dGPU is generally **not** bricking — worst case is a
  driver reset or a black screen the reboot clears — but keep
  **Apply-at-startup off** so a bad profile cannot come back by itself.
- One change per pass, so the log attributes the effect.
- Nothing in the Windows half is expected to touch the firmware; it is NVAPI at
  runtime, the same class as `nvidia-smi` here.

## Tooling

| Tool | Side | What it does |
|---|---|---|
| `evidence/gpuload.cu` | Linux | the CUDA saturation kernel already used in `dgpu-control.md` |
| `evidence/nv-surface.sh` | Linux | captures the exposed NVIDIA surface, read-only, for diffing |
| `evidence/hml-analyze.py` | either | parses Afterburner's own `HardwareMonitoring.hml`: per-property stats, and `--windows` for one row per loaded window |
| `evidence/ab-log-analyze.py` | either | parses RTSS "log to file" CSVs; per-pass stats + the V/F curve |
| MSI Kombustor 4 | Windows | the load (`winget install MSI.Kombustor.4`); must be pointed at the dGPU |

## What came back, and the two wasted passes worth keeping

The slider verdicts, the `.hml` logs, and the per-GPU profile file — which is
where the start-up safety argument actually lives, and it is readable rather
than a checkbox. The file holds two sections and **only `[Startup]` is applied
at boot**:

```
Profiles\VEN_10DE&DEV_249D&…cfg
  [Startup]    CoreClkBoost=          VFCurve=          MemClkBoost=      <- empty
  [Profile1]   CoreClkBoost=0         MemClkBoost=0     VFCurve=<12 pairs>
```

Checked at 16:54, 16:59, 17:16 and 17:17: **`Apply` never writes this file** —
every offset in this session was runtime-only and none of it could have
survived a reboot. `[Profile1]` showed up only once a profile was explicitly
*saved*, and what it holds is the **stock** curve — the hex decodes to twelve
`(voltage, frequency)` pairs, 450 mV/210 MHz through 1200 mV/2025 MHz — so it is
a restore point, not a trap. (The trailing bytes are zero-padded, and the
8-byte header `00000200 7f000000` is only partly understood.) Safety here rests
on `[Startup]` staying empty, which can be *checked*, unlike a tick box.

Two passes were wasted, and both failures are the repo's recurring ones:

- **A change too small to see.** A plateau at 1300 MHz — then one clamped to
  1200 while a load was running — were both invisible: the workload's own drift
  (±65 MHz) is the same size as the effect. Only **700 MHz** produced an
  unmistakable signal. *Set a distinctive value, or you measure the noise.*
- **No timestamp on the action.** Without the wall-clock time of the click there
  is no way to say which samples are before and which are after, and the log
  cannot be split. The fix is one number from the operator: note `hh:mm:ss` at
  Apply. The pass that finally settled it needed no timestamp at all, because
the step was a 550 MHz cliff inside one continuous load.

The results are folded into [`dgpu-control.md`](dgpu-control.md).
