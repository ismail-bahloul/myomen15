# The discrete GPU (HP OMEN 15-en1xxx)

The rest of this repository is the CPU (Cezanne), its SMU, and the HP embedded
controller. This page is the other end of the machine: the **NVIDIA RTX 3070
Laptop GPU** — a different vendor, a different driver, and a *different gate*.
It was checked because every CPU-side lever that could have been unlocked turned
out to be gated in signed firmware; the dGPU is the one place where the gate is
not that one.

**Machine:** RTX 3070 Laptop GPU · driver `615.71.09` · vBIOS `94.04.3D.00.C3`
· board part `249D-750-A1` · 80 W TGP. Measured on CachyOS (kernel 7.2.4), a
**Wayland** session with the iGPU (`amdgpu`) driving the display. `✅` doable ·
`🟡` partial · `🔴` refused.

## The control surface

| What | | Detail |
|---|---|---|
| **Lock the GPU clock** | ✅ | `nvidia-smi --lock-gpu-clocks=<min>,<max>`. **Measured effective** (below). Needs root, needs no X |
| **Lock the memory clock** | ✅ | `nvidia-smi --lock-memory-clocks=<MHz>`; accepted |
| Set the power limit | 🔴 | `nvidia-smi -pl` → *"Changing power management limit is not supported for GPU"*. A 1–100 W range is *reported*, but it is not user-enforced |
| Clock offsets (the over/underclock curve) | 🟡 | The attributes exist and read — `GPUGraphicsClockOffsetAllPerformanceLevels` (−1000…+1000 MHz), `GPUMemoryTransferRateOffsetAllPerformanceLevels` (−2000…+6000) — but **writes are refused**: no `Coolbits`, and a Wayland session |
| Voltage / V/F curve | 🔴 | **not exposed** — nothing via NVML, nothing via `nvidia-settings` |

## The one lever that works, measured

A CUDA spin kernel (`evidence/gpuload.cu`) held the GPU at 100 % utilisation
while the clocks were read back. The lock is not just accepted, it moves the
numbers:

| State | Graphics clock | Util | Power |
|---|---|---|---|
| under load, **no lock** | 1560 MHz | 100 % | **79.8 W** (against the 80 W cap) |
| **locked to ≤ 1000 MHz** | 990 MHz | 100 % | **41.2 W** |
| after `--reset-gpu-clocks` | 1545 MHz | 100 % | 79.3 W |

Roughly **half the power for ~36 % fewer MHz** — the curve is not linear, which
is the whole point of capping it.

## What this is, and is not

- It is **clock control — an underclock, not an undervolt.** Linux does not
  expose the GPU voltage, so the V/F curve a Windows tool edits has **no Linux
  equivalent**. The practical gains overlap (heat, noise, sustained clock); the
  mechanism does not. There is no undervolt to build here.
- A static lock is a **blunt instrument**. The driver already manages clocks and
  power dynamically and usually does better; the lock earns its place for
  sustained, thermally-constrained work and for a quiet mode — not as a default.
- It is **not a way past the CPU's gate**, and shares no mechanism with the SMU
  story — only the machine.

## Where a real undervolt lives: the Windows trip was made, and it is a dead end

On **Windows**, through a V/F-curve tool. That was [tested on
2026-09-24](dgpu-windows-undervolt.md#result-measured-2026-09-24) — MSI
Afterburner 4.6.6, driver `610.88`, the same card — and the answer is that the
tool has nothing this page's Linux side lacks:

- **No voltage, at all.** The Core Voltage slider is greyed out in all four
  unlock modes, and the monitor never gains a voltage column (89 properties;
  only `GPU2 voltage limit`, a 0/1 flag).
- **No power limit either.** The Power Limit slider is greyed out, exactly where
  `nvidia-smi -pl` refuses here. The refusal is the vBIOS's, not the OS's — so
  the `NvAPI_GPU_SetPowerTarget` path this page hoped for is closed too.
- **The core clock offset slider lies.** Afterburner's write *does* reach the
  driver (proven by a +500 MHz memory offset landing exactly, 6001 → 6501 MHz),
  and the core offset changes nothing: −300 MHz left the card at 1264.25 MHz
  against 1267.75 MHz stock, at the same 79.3 W.
- **The V/F curve editor is real, but it is a clock clamp, not a voltage map.**
  Plateauing the curve at ~700 MHz pins the card at 670 MHz under a 100 % load —
  and it still draws **69.34 W**; release it, in the same continuous load, and
  the card returns to 1221 MHz at **78.72 W**. A 45 % clock reduction buys 12 %
  of the power.

The contrast is the point. On Linux, `--lock-gpu-clocks=0,1000` holds 1000 MHz
at **41 W**, because the driver re-selects a lower voltage to go with the lower
clock. Afterburner's curve does not touch the voltage, so it buys almost nothing
while giving up the clock. **The lever that cuts power on this GPU is the Linux
one, and this page's original guess — that the real undervolt lived on Windows
— was wrong.**

## D3Cold Support: tested, and it breaks boot

`AMD PBS > D3Cold Support` is one of the few non-`Auto` values in that menu
(`Disabled`), and a plausible lever for letting the dGPU power all the way
down when idle on the iGPU. **Tested, and it doesn't work on this
machine**: setting it to `Enabled` leaves Limine reachable, but selecting
either Linux or Windows from it hangs — neither OS actually boots. Setting
it back to `Disabled` restores normal boot immediately. This is the risk
this page already flagged before testing it ("NVIDIA + Linux + D3Cold is
known-troublesome territory") — now measured, not just anticipated.
**Closed: leave `D3Cold Support` on `Disabled`.**

## If anything is built, build it coherent

The CPU side already has a governor (`power-profile-watch`) and a monitor
(`omenmon`). The dGPU adds a real lever with **no owner**. The coherent thing to
build is not "a GPU tool" but **one governor** over the levers that actually
work — CPU power limits (`ryzenadj`), the GPU clock lock (NVML), the fans (EC),
and the platform profile — instead of three that ignore each other.

## Reproducing

```bash
nvidia-smi -q -d POWER,CLOCK            # the ranges; the power limit is informational
sudo nvidia-smi --lock-gpu-clocks=300,1000
sudo nvidia-smi --reset-gpu-clocks
```

Load harness and the raw log: [`evidence/gpuload.cu`](evidence/gpuload.cu),
[`evidence/dgpu-probe.txt`](evidence/dgpu-probe.txt).
