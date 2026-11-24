r"""Can a collection's own event logs say which filesystem they were written to?

Phase 8.1 §E.3 measured `EventLog.emit`'s cost -- `json.dumps` + `write` +
`flush()`, a real syscall -- on both filesystems of this host:

    ext4  (WSL native)      median   5.4 us   p95    11.3 us   max    212.5 us
    drvfs (/mnt/..., 9p)    median 229.7 us   p95   371.9 us   max  2 276.8 us

**About 40x, and it is paid once per record inside the runs themselves.** If two
records are emitted back to back, the gap between their `monotonic_ns` stamps is
the second emit's cost plus whatever little work separates them. Over tens of
thousands of pairs the *low quantiles* of that gap are dominated by the emit, so
the low tail of the inter-record gap distribution should carry a 40x signature of
the filesystem the log was written to.

That matters because `docs/28-storage-backing-recovery.md` leaves four
collections -- the `b2-*-2026-08-21` prevention sessions, 240 runs, which carry
`\ReplicationPrevented*` -- **UNDETERMINED**: they record no `environment` block,
no artifact of theirs records an absolute path, and an inode event on 2026-09-01
removed the ctime evidence. If the fingerprint works, it is a measurement made by
the collection, at collection time, which is precisely the class of evidence that
document says is the only kind able to DETERMINE anything.

**It is calibrated before it is used, and the calibration is unusually good.**
Phase 10 collected the same cell twice on the same day on the same host with the
same harness, once on ext4 and once on drvfs, and both arms record their
filesystem in every run config. They are the positive and negative control. If
the fingerprint does not separate *them*, it cannot classify anything, and this
script says so rather than reporting a number.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

#: Phase 8.1 §E.3, the direct microbenchmark this fingerprint is derived from.
PHASE_81_EXT4_MEDIAN_US = 5.4
PHASE_81_DRVFS_MEDIAN_US = 229.7

#: The two Phase 10 arms, whose filesystem every run config records.
CALIBRATION = {
    "ext4": (
        "/root/aep-phase10/ext4-2026-09-02",
        "/root/aep-phase10/ext4-2026-09-02-arbb30",
    ),
    "drvfs": (
        "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
        "phase10-replication-drvfs-2026-09-02",
        "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
        "phase10-replication-drvfs-arbb30-2026-09-02",
    ),
}


def gaps_microseconds(run: Path, limit_files: int | None = None) -> list[float]:
    """Consecutive `monotonic_ns` gaps, per event-log file, in microseconds.

    Grouped per file rather than pooled across the run: two files are written by
    different processes and interleaving them would manufacture gaps that no
    single emit ever paid.
    """
    out: list[float] = []
    files = sorted(run.glob("events*.jsonl"))
    if limit_files:
        files = files[:limit_files]
    for log in files:
        previous: int | None = None
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                record = json.loads(line)
            except Exception:
                previous = None
                continue
            stamp = record.get("monotonic_ns")
            if stamp is None:
                continue
            stamp = int(stamp)
            if previous is not None and stamp >= previous:
                out.append((stamp - previous) / 1000.0)
            previous = stamp
    return out


def quantile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(q * (len(ordered) - 1))))
    return ordered[index]


def fingerprint(root: Path, max_runs: int | None = None) -> dict:
    runs = sorted(d for d in root.iterdir() if d.is_dir() and d.name != "analysis")
    if max_runs:
        runs = runs[:max_runs]
    pooled: list[float] = []
    per_run_p05: list[float] = []
    for run in runs:
        gaps = gaps_microseconds(run)
        if not gaps:
            continue
        pooled.extend(gaps)
        per_run_p05.append(quantile(gaps, 0.05))
    if not pooled:
        return {"runs": 0}
    return {
        "runs": len(per_run_p05),
        "gaps": len(pooled),
        "p01_us": round(quantile(pooled, 0.01), 1),
        "p05_us": round(quantile(pooled, 0.05), 1),
        "p10_us": round(quantile(pooled, 0.10), 1),
        "p25_us": round(quantile(pooled, 0.25), 1),
        "median_us": round(statistics.median(pooled), 1),
        "min_us": round(min(pooled), 1),
        # The per-run p05 is the classifier: one number per run, so a root can
        # be summarised by how many of its runs sit on each side of a threshold
        # rather than by a pooled statistic that a few long runs could dominate.
        "per_run_p05_median_us": round(statistics.median(per_run_p05), 1),
        "per_run_p05_min_us": round(min(per_run_p05), 1),
        "per_run_p05_max_us": round(max(per_run_p05), 1),
        "per_run_p05_values": [round(v, 1) for v in per_run_p05],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="a collection to fingerprint; repeat",
    )
    parser.add_argument("--max-runs", type=int, default=None)
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    report: dict = {
        "phase_8_1_microbenchmark_us": {
            "ext4_median": PHASE_81_EXT4_MEDIAN_US,
            "drvfs_median": PHASE_81_DRVFS_MEDIAN_US,
        },
        "calibration": {},
        "roots": {},
    }

    print("=== calibration: the two Phase 10 arms, whose filesystem is recorded ===")
    print(
        f"{'arm':28s} {'runs':>5s} {'gaps':>8s} {'p01':>9s} {'p05':>9s} "
        f"{'p10':>9s} {'median':>9s}  per-run p05 (min..max)"
    )
    for label, paths in CALIBRATION.items():
        for path in paths:
            base = Path(path)
            if not base.is_dir():
                continue
            result = fingerprint(base, arguments.max_runs)
            report["calibration"][f"{label}:{base.name}"] = result
            print(
                f"{label + ' ' + base.name[:20]:28s} {result['runs']:5d} "
                f"{result['gaps']:8d} {result['p01_us']:9.1f} {result['p05_us']:9.1f} "
                f"{result['p10_us']:9.1f} {result['median_us']:9.1f}  "
                f"{result['per_run_p05_min_us']:.1f}..{result['per_run_p05_max_us']:.1f}"
            )

    # The unit of the question is the COLLECTION -- "which filesystem was this
    # root written to" -- so the classifier is one number per root, the pooled
    # 5th-percentile gap. Reported at run level too, below, because the run-level
    # distributions OVERLAP and that limit belongs in the open where a reader can
    # see it rather than in a footnote.
    ext4_root_p05 = [
        r["p05_us"] for k, r in report["calibration"].items() if k.startswith("ext4:")
    ]
    drvfs_root_p05 = [
        r["p05_us"] for k, r in report["calibration"].items() if k.startswith("drvfs:")
    ]
    ext4_run_p05 = [
        v
        for key, r in report["calibration"].items()
        if key.startswith("ext4:")
        for v in r.get("per_run_p05_values", [])
    ]
    drvfs_run_p05 = [
        v
        for key, r in report["calibration"].items()
        if key.startswith("drvfs:")
        for v in r.get("per_run_p05_values", [])
    ]
    separated = (
        bool(ext4_root_p05)
        and bool(drvfs_root_p05)
        and max(ext4_root_p05) < min(drvfs_root_p05)
    )
    threshold = (
        (max(ext4_root_p05) + min(drvfs_root_p05)) / 2.0
        if separated
        else float("nan")
    )
    run_level_separated = (
        bool(ext4_run_p05)
        and bool(drvfs_run_p05)
        and max(ext4_run_p05) < min(drvfs_run_p05)
    )
    report["separation"] = {
        "unit": "collection root, pooled p05 of inter-record gaps",
        "ext4_root_p05_max": max(ext4_root_p05) if ext4_root_p05 else None,
        "drvfs_root_p05_min": min(drvfs_root_p05) if drvfs_root_p05 else None,
        "cleanly_separated_at_root_level": separated,
        "threshold_us": round(threshold, 1) if separated else None,
        "cleanly_separated_at_run_level": run_level_separated,
        "ext4_run_p05_max": max(ext4_run_p05) if ext4_run_p05 else None,
        "drvfs_run_p05_min": min(drvfs_run_p05) if drvfs_run_p05 else None,
    }
    print()
    if separated:
        print(
            f"SEPARATED AT ROOT LEVEL: every ext4 root's pooled p05 is below "
            f"{max(ext4_root_p05):.1f} us and every drvfs root's is above "
            f"{min(drvfs_root_p05):.1f} us. Threshold {threshold:.1f} us."
        )
    else:
        print(
            "NOT SEPARATED even at root level. The fingerprint cannot classify "
            "anything and no verdict is printed below."
        )
    if not run_level_separated and ext4_run_p05 and drvfs_run_p05:
        print(
            f"  Run level does NOT separate: ext4 runs reach "
            f"{max(ext4_run_p05):.1f} us and drvfs runs start at "
            f"{min(drvfs_run_p05):.1f} us. So this classifies a COLLECTION, "
            f"never a run."
        )

    if not arguments.root:
        if arguments.json:
            Path(arguments.json).write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        return 0

    print()
    print("=== classification ===")
    print(
        f"{'root':40s} {'runs':>5s} {'p01':>8s} {'p05':>8s}  {'verdict':>9s}  "
        f"{'known':>10s}  agrees?"
    )
    for spec in arguments.root:
        label, _, rest = spec.partition("=")
        known, _, path = rest.partition("@") if "@" in rest else ("", "", rest)
        base = Path(path)
        if not base.is_dir():
            print(f"{label:40s} MISSING {path}")
            continue
        result = fingerprint(base, arguments.max_runs)
        verdict = "n/a"
        if separated and result.get("p05_us") == result.get("p05_us"):
            verdict = "ext4" if result["p05_us"] < threshold else "drvfs"
        result["verdict"] = verdict
        result["recorded_filesystem"] = known or None
        agrees = ""
        if known:
            agrees = "YES" if known == verdict else "** NO **"
        result["agrees_with_record"] = agrees or None
        report["roots"][label] = result
        print(
            f"{label:40s} {result['runs']:5d} {result['p01_us']:8.1f} "
            f"{result['p05_us']:8.1f}  {verdict:>9s}  {known or '-':>10s}  {agrees}"
        )
    validated = [
        r
        for r in report["roots"].values()
        if r.get("recorded_filesystem") and r.get("agrees_with_record")
    ]
    if validated:
        ok = sum(1 for r in validated if r["agrees_with_record"] == "YES")
        print()
        print(
            f"Held-out validation: {ok}/{len(validated)} roots whose filesystem "
            f"IS recorded are classified correctly by a threshold calibrated "
            f"only on the Phase 10 pair."
        )
        report["separation"]["held_out_correct"] = ok
        report["separation"]["held_out_total"] = len(validated)

    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
