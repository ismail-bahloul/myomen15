#!/usr/bin/env python3
"""Summarise the eff-<label>.csv samples produced by eff-test.sh.

Throughput comes from eff-<label>-load.txt; power from the CSV. The measurement
window is taken as sample rows 22..61 (the load's 20 s warmup plus a couple of
seconds of settle), so the warmup is excluded.

Power caveat: STAPM VALUE has a 275 s time constant and does not settle in a
40 s window, so it *understates* package power here. PPT VALUE SLOW (a ~5 s
average) is the honest proxy for a 40 s run and is used for the J/Mi figure;
STAPM is printed beside it for continuity with record/03-open-questions.md.
"""

import csv
import glob
import re
import sys


def mean(rows, key):
    vals = [float(r[key]) for r in rows if r.get(key) not in ("", None)]
    return sum(vals) / len(vals) if vals else float("nan")


def throughput(path):
    with open(path) as fh:
        m = re.search(r"throughput_Mi_s=([0-9.]+)", fh.read())
    return float(m.group(1))


def main():
    labels = sys.argv[1:] or ["ac", "nocap", "perf"]
    print("%-6s %10s %8s %9s %8s %7s %7s %9s" %
          ("label", "Mi/s", "STAPM", "PPTslow", "freq GHz", "Tctl", "fan1", "mJ/Mi"))
    for lab in labels:
        with open("evidence/autonomous-pass/eff-%s.csv" % lab) as fh:
            rows = list(csv.DictReader(fh))
        win = rows[22:62]
        thr = throughput("evidence/autonomous-pass/eff-%s-load.txt" % lab)
        stapm = mean(win, "stapm_value")
        pptslow = mean(win, "ppt_slow_value")
        freq = mean(win, "cur_freq") / 1e6
        tctl = mean(win, "tctl") / 1000.0
        fan1 = mean(win, "fan1")
        mj_per_mi = pptslow / thr * 1e3    # W/(Mi/s) -> mJ/Mi
        print("%-6s %10.1f %8.2f %9.2f %8.2f %7.1f %7.0f %9.3f" %
              (lab, thr, stapm, pptslow, freq, tctl, fan1, mj_per_mi))


if __name__ == "__main__":
    main()
