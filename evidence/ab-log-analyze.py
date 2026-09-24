#!/usr/bin/env python3
"""Summarise MSI Afterburner / RTSS hardware-monitor logs, per pass.

Afterburner's log is a CSV-shaped file, usually UTF-16LE with a BOM, with a
name row and a unit row above the data. The column set depends on what is
enabled in Monitoring, so columns are matched by keyword, not position. Run
one log per pass (stock / clock-offset / curve-undervolt) and pass the files
here; the point is to see, per pass, the effective core clock, voltage, power
and temperature — i.e. whether the lever did anything and what the V/F curve
looks like.

  python3 ab-log-analyze.py stock.csv offset.csv curve.csv

Nothing here touches a GPU; it reads files only.
"""

from __future__ import annotations

import re
import sys

# keyword -> canonical field
FIELDS = [
    ("core clock", "core_mhz"),
    ("gpu clock", "core_mhz"),
    ("memory clock", "mem_mhz"),
    ("mem clock", "mem_mhz"),
    ("voltage", "voltage"),
    # "power limit" must be tested before "power", or the limit column
    # would shadow the real power draw (Afterburner lists both).
    ("power limit", "power_limit"),
    ("power", "power"),
    ("temperature", "temp"),
    ("temp", "temp"),
    ("gpu usage", "usage"),
    ("usage", "usage"),
    ("fan", "fan"),
]


def read_text(path: str) -> str:
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in raw[:200]:
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")


def classify(header: str) -> str | None:
    h = header.lower()
    for key, field in FIELDS:
        if key in h:
            return field
    return None


def num(s: str):
    m = re.search(r"-?\d+(?:[.,]\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def analyze(path: str) -> None:
    lines = [ln for ln in read_text(path).splitlines() if ln.strip()]
    if not lines:
        print(f"{path}: empty")
        return
    # header row = the first line containing a recognisable sensor name
    hidx = 0
    for i, ln in enumerate(lines):
        if any(k in ln.lower() for k in ("clock", "power", "temperature", "voltage")):
            hidx = i
            break
    headers = [c.strip().strip('"') for c in lines[hidx].split(",")]
    cols: dict[str, int] = {}
    for j, c in enumerate(headers):
        field = classify(c)
        # First column wins: two headers can classify to the same field
        # ("GPU1 usage" vs "GPU1 memory usage"), and the more specific one
        # is listed first by Afterburner.
        if field and field not in cols:
            cols[field] = j
    data = lines[hidx + 2:]  # skip the unit row

    series: dict[str, list[float]] = {f: [] for f in cols}
    vf: dict[float, float] = {}          # voltage -> max core clock seen there
    for ln in data:
        cells = [c.strip().strip('"') for c in ln.split(",")]
        row = {}
        for field, j in cols.items():
            if j < len(cells):
                v = num(cells[j])
                if v is not None:
                    series[field].append(v)
                    row[field] = v
        if "voltage" in row and "core_mhz" in row:
            vf[row["voltage"]] = max(vf.get(row["voltage"], 0), row["core_mhz"])

    def stat(field):
        xs = series.get(field, [])
        if not xs:
            return "   n/a"
        return "%5.1f / %5.1f (mean/max)" % (sum(xs) / len(xs), max(xs))

    print(f"=== {path} ===  {len(data)} samples")
    for field in ("core_mhz", "mem_mhz", "voltage", "power", "power_limit",
                  "temp", "usage", "fan"):
        if field in series:
            print(f"  {field:10s}: {stat(field)}")
    if vf:
        print("  V/F (voltage -> max core MHz):")
        for v in sorted(vf):
            print(f"      {v:6.0f} mV  ->  {vf[v]:5.0f} MHz")
    else:
        print("  no voltage column — Afterburner logged no GPU voltage "
              "(common on laptop vBIOSes; that is itself the answer)")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip().splitlines()[-1])
    for path in sys.argv[1:]:
        analyze(path)


if __name__ == "__main__":
    main()
