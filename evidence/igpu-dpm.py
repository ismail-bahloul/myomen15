#!/usr/bin/env python3
"""Measure the iGPU DPM levels against idle draw, heat and noise.

On Cezanne the Radeon shares the SoC rail with the CPU, so the iGPU's clocks are
a plausible idle-power lever nothing else in this repo has touched. amdgpu exposes
`pp_dpm_{sclk,socclk,fclk,mclk,dcefclk}` and `power_dpm_force_performance_level`.

This samples battery draw, Tctl, the iGPU edge temperature and both fans over a
window, once per requested force-level, and restores `auto` on exit -- including
on Ctrl-C. The only thing it writes is `power_dpm_force_performance_level`.

    sudo python3 evidence/igpu-dpm.py                 # auto / low / auto
    sudo python3 evidence/igpu-dpm.py auto low high    # explicit list
    sudo python3 evidence/igpu-dpm.py low --secs 40
    # hold the memory/fabric at full speed, pin the rest low:
    sudo python3 evidence/igpu-dpm.py auto manual:sclk=0,socclk=0,fclk=3,mclk=3,dcefclk=0 auto
"""
import glob
import os
import statistics
import sys
import time

# The iGPU is the amdgpu card that owns a `pp_dpm_fclk` (the dGPU has no DPM
# level files); pick it by that rather than by card number.
def igpu_device():
    for d in sorted(glob.glob("/sys/class/drm/card[0-9]*/device")):
        if os.path.exists(os.path.join(d, "pp_dpm_fclk")):
            return os.path.realpath(d)
    raise SystemExit("no amdgpu DPM device found")


DEV = igpu_device()
LEVEL = os.path.join(DEV, "power_dpm_force_performance_level")
DPM = ["sclk", "socclk", "fclk", "mclk", "dcefclk"]


def read(path):
    try:
        return open(path).read().strip()
    except OSError:
        return None


def hwmon_temp(name, label="temp1"):
    for h in glob.glob("/sys/class/hwmon/hwmon*"):
        if read(os.path.join(h, "name")) == name:
            v = read(os.path.join(h, label + "_input"))
            return int(v) / 1000.0 if v else None
    return None


def fans():
    out = {}
    for h in glob.glob("/sys/class/hwmon/hwmon*"):
        if read(os.path.join(h, "name")) != "hp":
            continue
        for f in sorted(glob.glob(os.path.join(h, "fan*_input"))):
            out[os.path.basename(f)] = int(read(f) or 0)
    return out


def battery_w():
    v = read("/sys/class/power_supply/BAT0/power_now")
    return round(int(v) / 1e6, 2) if v else None


def on_ac():
    v = read("/sys/class/power_supply/AC/online") or read("/sys/class/power_supply/ACAD/online")
    return v


def dpm_levels():
    out = {}
    for c in DPM:
        txt = read(os.path.join(DEV, "pp_dpm_" + c))
        if not txt:
            out[c] = "-"
            continue
        cur = [(ln.split(":", 1)[1].strip() if ":" in ln else ln.strip())
               for ln in txt.splitlines() if ln.strip().endswith("*")]
        out[c] = cur[0] if cur else ("%d levels" % len(txt.splitlines()))
    return out


def set_level(level):
    try:
        with open(LEVEL, "w") as f:
            f.write(level)
    except OSError as e:
        print("  ! could not write %s: %s" % (LEVEL, e), file=sys.stderr)
        return False
    got = read(LEVEL)
    if got != level:
        print("  ! level stayed %r (asked %r)" % (got, level), file=sys.stderr)
        return False
    return True


def set_phase(spec):
    """A phase is either a force-level (`auto`, `low`) or a manual spec
    (`manual:sclk=0,socclk=0,fclk=3,mclk=3,dcefclk=0`), so a single clock can be
    held high while the others are pinned low."""
    if not spec.startswith("manual:"):
        return set_level(spec)
    if not set_level("manual"):
        return False
    for kv in spec[len("manual:"):].split(","):
        clk, idx = kv.split("=", 1)
        path = os.path.join(DEV, "pp_dpm_" + clk)
        try:
            with open(path, "w") as f:
                f.write(idx)
        except OSError as e:
            print("  ! could not write %s: %s" % (path, e), file=sys.stderr)
            return False
    return True


def sample(secs):
    acc = {"power": [], "tctl": [], "edge": [], "f1": [], "f2": []}
    for _ in range(secs):
        p, t, e = battery_w(), hwmon_temp("k10temp"), hwmon_temp("amdgpu", "temp1")
        fs = fans()
        if p is not None:
            acc["power"].append(p)
        if t is not None:
            acc["tctl"].append(t)
        if e is not None:
            acc["edge"].append(e)
        if fs:
            acc["f1"].append(fs.get("fan1_input", 0))
            acc["f2"].append(fs.get("fan2_input", 0))
        time.sleep(1.0)
    return acc


def mean(xs):
    return statistics.mean(xs) if xs else float("nan")


def main():
    argv = sys.argv[1:]
    secs = 20
    if "--secs" in argv:
        i = argv.index("--secs")
        secs = int(argv[i + 1])
        del argv[i:i + 2]
    phases = argv or ["auto", "low", "auto"]

    print("iGPU: %s" % DEV)
    print("on AC: %s   battery: %s W" % (on_ac(), battery_w()))
    print("sampling %d s per phase\n" % secs)

    try:
        rows = []
        for ph in phases:
            ok = set_phase(ph)
            if not ok:
                print("  (phase %r skipped: level not accepted)" % ph)
                continue
            time.sleep(4.0)  # let the new levels settle
            acc = sample(secs)
            lv = dpm_levels()
            rows.append((ph, acc, lv))
            print("after %-6s  power=%.2f W  Tctl=%.1f  edge=%.1f  fan=%d/%d  |  %s" % (
                ph, mean(acc["power"]), mean(acc["tctl"]), mean(acc["edge"]),
                mean(acc["f1"]), mean(acc["f2"]),
                " ".join("%s=%s" % kv for kv in lv.items())))
    finally:
        if set_level("auto"):
            print("\nrestored power_dpm_force_performance_level=auto")
        else:
            print("\n!! FAILED to restore auto -- fix with: echo auto > %s" % LEVEL, file=sys.stderr)


if __name__ == "__main__":
    main()
