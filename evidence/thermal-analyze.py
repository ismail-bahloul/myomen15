#!/usr/bin/env python3
"""Summarise the thermal-<label>.csv samples from thermal-ab.sh, phase by phase.

Phases are taken by wall-clock offset from the first sample (the sampler and the
load schedule share a clock), and each phase's *middle* is used so the ramps at
the boundaries do not leak in:

    t+2   .. t+27    idle
    t+27  .. t+87    1 thread
    t+87  .. t+112   cooldown
    t+112 .. t+162   14 threads

  python3 thermal-analyze.py old new
"""
import csv
import sys

PHASES = [("idle", 8, 24), ("1-thread", 35, 82),
          ("cooldown", 95, 110), ("14-thread", 120, 158)]


def col(rows, k):
    return [float(r[k]) for r in rows if r.get(k) not in ("", None)]


def main():
    labels = sys.argv[1:] or ["old", "new"]
    for lab in labels:
        with open("evidence/autonomous-pass/thermal-%s.csv" % lab) as fh:
            rows = list(csv.DictReader(fh))
        t0 = int(rows[0]["epoch"])
        print("== %s ==" % lab)
        print("  %-10s %8s %8s %7s %7s %7s %8s" %
              ("phase", "Tctl avg", "Tctl max", "fan1", "fan2", "PPTslow", "GHz"))
        for name, a, b in PHASES:
            win = [r for r in rows
                   if a <= int(r["epoch"]) - t0 <= b]
            if not win:
                continue
            tctl = [x / 1000.0 for x in col(win, "tctl")]
            print("  %-10s %7.1fC %7.1fC %6.0f %6.0f %6.1fW %7.2f" %
                  (name, sum(tctl) / len(tctl), max(tctl),
                   sum(col(win, "fan1")) / len(win),
                   sum(col(win, "fan2")) / len(win),
                   sum(col(win, "ppt_slow_value")) / len(win),
                   sum(col(win, "cur_freq")) / len(win) / 1e6))
        print()


if __name__ == "__main__":
    main()
