#!/usr/bin/env python3
"""Summarise MSI Afterburner's *own* hardware-monitor log (HardwareMonitoring.hml).

Why this exists next to ab-log-analyze.py: the `.hml` is the monitor's native
log, it is plain text, it carries every enabled property at the 1 s poll
period, and — unlike an RTSS "log to file" CSV — it needs no per-pass clicking.
More importantly, the column names are read from the log's **own header**, not
matched by keyword, so a property appearing or disappearing between passes
(dGPU voltage, say) cannot silently shift every column by one.

Verified on this machine: the column order the header declares lines up
exactly with `nvidia-smi` (GPU2 core clock 495 MHz, GPU2 power 18.8 W at idle),
which is what makes GPU1/GPU2 attribution trustworthy.

    python hml-analyze.py pass.hml                # every property
    python hml-analyze.py pass.hml --grep GPU2    # one GPU's columns
    python hml-analyze.py pass.hml --last 60      # last 60 samples (~60 s) only
    python hml-analyze.py pass.hml --list         # header only, no stats

Nothing here touches a GPU; it reads a file only.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

TS_FORMAT = "%d-%m-%Y %H:%M:%S"


def load(path: str):
    """Return (devices, properties, rows) for the *last* session in the file."""
    text = open(path, "rb").read().decode("latin-1")
    devices: list[str] = []
    props: list[str] = []
    rows: list[tuple[str, list[str]]] = []

    for line in text.split("\r\n"):
        if not line.strip():
            continue
        kind = line.split(",", 1)[0].strip()
        if kind == "01":                      # device list
            devices = [c.strip() for c in line.split(",")[2:] if c.strip()]
        elif kind == "02":                    # property list -> new session
            props = [c.strip() for c in line.split(",")[2:]]
            rows = []
        elif kind == "80":                    # one sample
            cells = line.split(",")
            if len(cells) > 2:
                rows.append((cells[1].strip(), [c.strip() for c in cells[2:]]))
    return devices, props, rows


def parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, TS_FORMAT)
    except ValueError:
        return None


def value(cell: str) -> float | None:
    try:
        return float(cell)
    except ValueError:
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="a HardwareMonitoring.hml file")
    ap.add_argument("--grep", help="only properties whose name contains this")
    ap.add_argument("--last", type=int, metavar="N",
                    help="analyse only the last N samples (~seconds)")
    ap.add_argument("--list", action="store_true", help="print the header only")
    ap.add_argument("--windows", action="store_true",
                    help="print one row per contiguous loaded window (~100 %% usage), "
                         "which is how these passes are actually compared")
    ap.add_argument("--usage-prop", default="GPU2 usage",
                    help="the property that decides whether the card is loaded "
                         "(--windows only, default: GPU2 usage)")
    args = ap.parse_args()

    devices, props, rows = load(args.path)
    if not props or not rows:
        sys.exit(f"{args.path}: no property header or no samples found "
                 "(is this an .hml from the hardware monitor?)")

    if args.windows:
        for i, d in enumerate(devices):
            print(f"GPU{i + 1} = {d}")
        if args.usage_prop not in props:
            sys.exit(f"no {args.usage_prop!r} property in this log")
        segs, cur = [], []
        for r in rows:
            if (value(r[1][props.index(args.usage_prop)]) or 0.0) >= 95.0:
                cur.append(r)
            else:
                if len(cur) >= 20:
                    segs.append(cur)
                cur = []
        if len(cur) >= 20:
            segs.append(cur)
        print(f"{'window':19s} {'n':>4s}  {'memclk':10s} {'core mean':>9s} "
              f"{'core min-max':>12s} {'power mean':>10s}")
        for s in segs:
            def col(name, seg=s):
                return [value(r[1][props.index(name)]) or 0.0 for r in seg]
            core, power = col("GPU2 core clock"), col("GPU2 power")
            mem = sorted({round(x) for x in col("GPU2 memory clock")})
            print(f"{s[0][0][-8:]}-{s[-1][0][-8:]} {len(s):4d}  "
                  f"{'/'.join(str(x) for x in mem):10s} "
                  f"{sum(core) / len(core):9.0f} "
                  f"{min(core):6.0f}-{max(core):5.0f} "
                  f"{sum(power) / len(power):10.2f}")
        return

    if args.list:
        print(f"{args.path}")
        for i, d in enumerate(devices):
            print(f"  GPU{i + 1}: {d}")
        print(f"  {len(props)} properties, {len(rows)} samples")
        for p in props:
            print(f"    {p}")
        return

    if args.last:
        rows = rows[-args.last:]

    print(f"=== {args.path} ===")
    for i, d in enumerate(devices):
        print(f"  GPU{i + 1} = {d}")
    t0, t1 = parse_ts(rows[0][0]), parse_ts(rows[-1][0])
    span = f"{(t1 - t0).total_seconds():.0f} s" if t0 and t1 else "?"
    print(f"  {len(rows)} samples over {span}   ({rows[0][0]} -> {rows[-1][0]})")
    print()

    series: dict[str, list[float]] = {}
    for _, cells in rows:
        for i, p in enumerate(props):
            if i < len(cells):
                v = value(cells[i])
                if v is not None:
                    series.setdefault(p, []).append(v)

    # read the dGPU voltage/V-F shape straight off the log when it is there
    volt = [p for p in props if "voltage" in p.lower() and "limit" not in p.lower()]

    print(f"  {'property':22s} {'n':>4s} {'min':>9s} {'mean':>9s} {'max':>9s}")
    for p in props:
        if args.grep and args.grep.lower() not in p.lower():
            continue
        xs = series.get(p)
        if not xs:
            print(f"  {p:22s} {'n/a':>4s}")
            continue
        print(f"  {p:22s} {len(xs):4d} {min(xs):9.2f} "
              f"{sum(xs) / len(xs):9.2f} {max(xs):9.2f}")

    if volt and not args.grep:
        core = [p for p in props if "core clock" in p.lower()]
        if core:
            print(f"\n  dGPU voltage column present: {volt[0]}")
            print(f"  (cross it with '{core[-1]}' for the V/F curve)")


if __name__ == "__main__":
    main()
