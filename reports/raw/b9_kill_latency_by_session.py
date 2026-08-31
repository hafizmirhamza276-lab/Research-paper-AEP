#!/usr/bin/env python3
"""B9: the kill-latency contrast at the session level rather than pooled.

`paper_tables.py::_median_split` filters on filesystem and system only, so the
drvfs arm pools 120 runs across four replication sessions with no session term.
Those sessions have applied rates of 20, 12, 4 and 7 out of 30 -- 9C's
over-dispersion -- so pooling mixes between-session level differences into a
contrast that is supposed to be within-session.

This script recomputes the same quantity with the session as the stratum, which
is the unit the paper already uses for `\\ReplicationPrevented*` and `\\ClassPp*`
on these same four sessions.  Read-only over the tracked CSV.
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

CSV = Path(__file__).resolve().parent / "e1-kill-latency-by-run.csv"
T_975_3 = 3.182  # t(0.975, 3), the paper's own session-clustered constant


def load() -> list[dict]:
    with CSV.open(newline="") as fh:
        return list(csv.DictReader(fh))


def median_diff(rows: list[dict]) -> tuple[float, int, int]:
    """Median latency of applied runs minus that of non-applied runs, ms."""
    applied = [int(r["issue_to_return_ns"]) / 1e6 for r in rows if r["applied"] == "1"]
    missed = [int(r["issue_to_return_ns"]) / 1e6 for r in rows if r["applied"] != "1"]
    if not applied or not missed:
        return float("nan"), len(applied), len(missed)
    return statistics.median(applied) - statistics.median(missed), len(applied), len(missed)


def clustered(diffs: list[float]) -> tuple[float, float, float, float, float]:
    mean = statistics.mean(diffs)
    sd = statistics.stdev(diffs)
    half = T_975_3 * sd / len(diffs) ** 0.5
    return mean, sd, half, mean - half, mean + half


def main() -> None:
    rows = load()
    sessions = ["P9-B", "s1", "s2", "s3"]

    for system, label in (("AEP_FULL", "AEP-full"), ("B3_INTENT_NO_BARRIER", "B3")):
        print(f"\n=== drvfs, {label} ===")
        diffs = []
        for sess in sessions:
            sub = [r for r in rows
                   if r["session"] == sess and r["filesystem"] == "drvfs"
                   and r["system"] == system]
            d, na, nm = median_diff(sub)
            print(f"  {sess:5s} n={len(sub):3d} applied={na:2d} not={nm:2d}  diff={d:+8.1f} ms")
            diffs.append(d)

        pooled_rows = [r for r in rows
                       if r["filesystem"] == "drvfs" and r["system"] == system]
        pooled, pa, pm = median_diff(pooled_rows)
        print(f"  POOLED (what the macro reports) n={len(pooled_rows)} "
              f"applied={pa} not={pm}  diff={pooled:+.1f} ms")

        mean, sd, half, lo, hi = clustered(diffs)
        print(f"  session-clustered: mean={mean:+.1f} sd={sd:.1f} "
              f"t(3)*sd/sqrt(4)={half:.1f}")
        print(f"  95% interval [{lo:+.1f}, {hi:+.1f}]  "
              f"half-width / |mean| = {half / abs(mean):.2f}x")

    print("\n=== ext4, the paper's original cell: ONE session, not pooled ===")
    for system, label in (("AEP_FULL", "AEP-full"), ("B3_INTENT_NO_BARRIER", "B3")):
        sub = [r for r in rows if r["filesystem"] == "ext4" and r["system"] == system]
        d, na, nm = median_diff(sub)
        sess = sorted({r["session"] for r in sub})
        print(f"  {label:8s} sessions={sess} n={len(sub)} applied={na} "
              f"not={nm}  diff={d:+.1f} ms")


if __name__ == "__main__":
    main()
