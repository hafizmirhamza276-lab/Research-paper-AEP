"""Cross-tabulate the prevention sessions: filesystem, counts, kill latency.

Phase 9C recorded the 4-20/30 spread in AEP-full's unwanted-applied count across
sessions as over-dispersion 5.37 and left it unexplained. Phase 8.1 §F.2 named a
candidate: the sessions were collected on different filesystems, whose event-log
append cost differs ~40x, and AEP-full dispatches only if `WAITAOF` returns
before the kill lands -- so a systematic per-session difference in append cost
would move each session along that race.

This script assembles the table that question needs, from analysis products that
already exist. It collects nothing and re-analyses nothing: every count is read
out of the tracked (or archived) `redis-kill-ablation.csv` exactly as the
manuscript reads it, and the filesystem column is whatever
`scripts/filesystem_fingerprint.py` and `docs/28-storage-backing-recovery.md`
have established, with its confidence carried along.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

#: label -> (analysis dir, raw root or None, filesystem, confidence)
#: The filesystem column is NOT derived here; it is transcribed from
#: docs/28-storage-backing-recovery.md and reports/raw/phase12-filesystem-
#: fingerprint.json so that one document owns the determination.
SESSIONS: tuple[tuple[str, str, str | None, str, str], ...] = (
    (
        "matrix (the paper's kill cell)",
        "/root/aep/experiments/results/matrix/analysis",
        "/root/aep/experiments/results/matrix",
        "ext4",
        "INFERRED (traceback + ctime + fingerprint 38.8us)",
    ),
    (
        "b2-2026-08-21 (P9C s0)",
        "experiments/results/b2-2026-08-21/analysis",
        "experiments/results/b2-2026-08-21",
        "drvfs",
        "INFERRED (fingerprint 472.7us)",
    ),
    (
        "b2-s1-2026-08-21 (P9C s1)",
        "experiments/results/b2-s1-2026-08-21/analysis",
        "experiments/results/b2-s1-2026-08-21",
        "drvfs",
        "INFERRED (fingerprint 397.2us)",
    ),
    (
        "b2-s2-2026-08-21 (P9C s2)",
        "experiments/results/b2-s2-2026-08-21/analysis",
        "experiments/results/b2-s2-2026-08-21",
        "drvfs",
        "INFERRED (fingerprint 392.2us)",
    ),
    (
        "b2-s3-2026-08-21 (P9C s3)",
        "experiments/results/b2-s3-2026-08-21/analysis",
        "experiments/results/b2-s3-2026-08-21",
        "drvfs",
        "INFERRED (fingerprint 386.5us)",
    ),
    (
        "b2-paired-s1-2026-08-28 (P8.4 v1)",
        "experiments/results/b2-paired-s1-2026-08-28/analysis",
        "/root/aep-phase8/experiments/results/b2-paired-s1-2026-08-28",
        "ext4",
        "DETERMINED (recorded environment block)",
    ),
    (
        "b2-paired-v2-s1-2026-08-28 (P8.4)",
        "experiments/results/b2-paired-v2-s1-2026-08-28/analysis",
        "/root/aep-phase8/experiments/results/b2-paired-v2-s1-2026-08-28",
        "ext4",
        "DETERMINED (recorded environment block)",
    ),
    (
        "b2-paired-v2-s2-2026-08-28 (P8.4)",
        "experiments/results/b2-paired-v2-s2-2026-08-28/analysis",
        "/root/aep-phase8/experiments/results/b2-paired-v2-s2-2026-08-28",
        "ext4",
        "DETERMINED (recorded environment block)",
    ),
    (
        "b2-paired-v2-s3-2026-08-28 (P8.4)",
        "experiments/results/b2-paired-v2-s3-2026-08-28/analysis",
        "/root/aep-phase8/experiments/results/b2-paired-v2-s3-2026-08-28",
        "ext4",
        "DETERMINED (recorded environment block)",
    ),
    (
        "b2-paired-v2-s4-2026-08-28 (P8.4)",
        "experiments/results/b2-paired-v2-s4-2026-08-28/analysis",
        "/root/aep-phase8/experiments/results/b2-paired-v2-s4-2026-08-28",
        "ext4",
        "DETERMINED (recorded environment block)",
    ),
)

#: The cell the prevention result is about, keyed the way the manuscript keys it.
REGIME = "redis-kill-preack"
RESPONSE_CLASS = "NO_READBACK"


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def applied_counts(analysis: Path) -> dict[str, dict[str, str]]:
    """`executions_with_an_applied_effect` per system, from the ablation CSV.

    This is exactly the column `\\UnwantedPrevented` is computed from
    (`ARTIFACT.md` §3, spot-check 2), read rather than recomputed.
    """
    out: dict[str, dict[str, str]] = {}
    for row in read_rows(analysis / "redis-kill-ablation.csv"):
        if row.get("regime") not in (REGIME, "", None):
            continue
        if row.get("response_class") not in (RESPONSE_CLASS, "", None):
            continue
        out[row["system"]] = row
    return out


def kill_latency(analysis: Path) -> dict | None:
    """Kill-landing latency per execution, if the CSV carries the column.

    `redis_kill_latency_ms` was added to `per-execution.csv` after the earliest
    collections were frozen, so its absence is "not recorded", never "zero".
    """
    values: list[float] = []
    for row in read_rows(analysis / "per-execution.csv"):
        raw = row.get("redis_kill_latency_ms")
        if raw in (None, ""):
            continue
        try:
            values.append(float(raw))
        except ValueError:
            continue
    if not values:
        return None
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "min": round(ordered[0], 1),
        "median": round(statistics.median(ordered), 1),
        "p95": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 1),
        "max": round(ordered[-1], 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".")
    parser.add_argument("--fingerprint", default=None)
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)
    repo = Path(arguments.repo).resolve()

    fingerprints: dict[str, float] = {}
    if arguments.fingerprint and Path(arguments.fingerprint).is_file():
        data = json.loads(Path(arguments.fingerprint).read_text(encoding="utf-8"))
        for label, entry in data.get("roots", {}).items():
            fingerprints[label.split(" (")[0].split(" ")[0]] = entry.get("p05_us")

    rows = []
    print(
        f"{'session':36s} {'fs':>6s} {'AEP':>8s} {'B3':>8s} {'diff':>5s} "
        f"{'kill latency ms (n/med)':>24s}  append p05 us"
    )
    print("-" * 118)
    for label, analysis_rel, raw, filesystem, confidence in SESSIONS:
        analysis = Path(analysis_rel)
        if not analysis.is_absolute():
            analysis = repo / analysis
        counts = applied_counts(analysis)
        aep = counts.get("AEP_FULL")
        b3 = counts.get("B3_INTENT_NO_BARRIER")
        latency = kill_latency(analysis)
        key = label.split(" (")[0]
        row = {
            "session": label,
            "filesystem": filesystem,
            "confidence": confidence,
            "aep_applied": (
                f"{aep['executions_with_an_applied_effect']}/{aep['executions']}"
                if aep
                else None
            ),
            "b3_applied": (
                f"{b3['executions_with_an_applied_effect']}/{b3['executions']}"
                if b3
                else None
            ),
            "aep_runs": aep.get("runs") if aep else None,
            "kill_latency_ms": latency,
            "append_p05_us": fingerprints.get(key),
        }
        rows.append(row)
        diff = ""
        if aep and b3:
            diff = str(
                int(b3["executions_with_an_applied_effect"])
                - int(aep["executions_with_an_applied_effect"])
            )
        lat = (
            f"{latency['n']}/{latency['median']}" if latency else "not recorded"
        )
        print(
            f"{label:36s} {filesystem:>6s} {row['aep_applied'] or '-':>8s} "
            f"{row['b3_applied'] or '-':>8s} {diff:>5s} {lat:>24s}  "
            f"{row['append_p05_us'] if row['append_p05_us'] is not None else '-'}"
        )

    by_fs: dict[str, list[int]] = {}
    for row in rows:
        if not row["aep_applied"]:
            continue
        by_fs.setdefault(row["filesystem"], []).append(
            int(row["aep_applied"].split("/")[0])
        )
    print()
    print("=== AEP-full unwanted-applied counts, grouped by filesystem ===")
    for filesystem, values in sorted(by_fs.items()):
        print(
            f"  {filesystem:6s} n={len(values)}  values {sorted(values)}  "
            f"range {min(values)}-{max(values)}  median {statistics.median(values)}"
        )
    if len(by_fs) < 2:
        print("  ONE GROUP ONLY -- the filesystems do not vary across these sessions.")
    else:
        groups = sorted(by_fs.items())
        (fa, va), (fb, vb) = groups[0], groups[1]
        overlap = not (max(va) < min(vb) or max(vb) < min(va))
        print()
        print(
            f"  ranges {'OVERLAP' if overlap else 'DO NOT OVERLAP'}: "
            f"{fa} {min(va)}-{max(va)} against {fb} {min(vb)}-{max(vb)}"
        )

    report = {"sessions": rows, "by_filesystem": by_fs}
    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
