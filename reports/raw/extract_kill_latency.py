"""Extract the measured `docker kill` latency of every redis-kill run.

Phase 8.1. The harness has always recorded this quantity and nothing has ever
surfaced it: :func:`experiments.harness.redis_kill.kill_redis` returns
``command_ms`` (redis_kill.py:108) and the kill watchdog emits
``issue_to_return_ns`` (redis_kill.py:305) into every run's ``events.jsonl``.
Neither reaches ``RedisKillRecord.echo()`` or any analysis CSV, so the only way
to read it is to walk the raw run directories -- which are not committed.

This script is the committed, re-runnable bridge between those raw runs and the
one small file the manuscript's generator is allowed to read, exactly as
``probe_kill.py`` is for ``e1-durability-window.txt``. Output:
``reports/raw/e1-kill-latency-by-run.csv``.

**Why the latency matters.** In the ``redis-kill-preack`` regime AEP-full
dispatches only if ``WAITAOF`` returns before Redis dies, so the kill latency is
the width of that race. B3 never waits, so it cannot be affected -- which makes
B3 a negative control for the whole mechanism rather than merely a baseline.

**Why `filesystem` is a column.** The paper's cell (2026-08-07) was collected in
the WSL-native tree ``/root/aep`` on ext4; all four replication sessions were
collected through ``/mnt/d`` on drvfs, where an event-log append costs ~40x more
(5.4 us vs 229.7 us median, measured). No ``run-config.json`` key records this,
so a comparison that pools the two strata inherits a confound that the recorded
configuration cannot reveal. The column exists so the analysis can stratify.

Invocations used to produce the committed file (Phase 8.1):

    python reports/raw/extract_kill_latency.py \
        --cell 2026-08-07:ext4:/root/aep/experiments/results/matrix \
        --cell P9-B:drvfs:experiments/results/b2-2026-08-21 \
        --cell s1:drvfs:experiments/results/b2-s1-2026-08-21 \
        --cell s2:drvfs:experiments/results/b2-s2-2026-08-21 \
        --cell s3:drvfs:experiments/results/b2-s3-2026-08-21 \
        --out reports/raw/e1-kill-latency-by-run.csv

The first root lives only in the root-owned measurement tree and is reachable
from the published raw archive; the other four are the tracked results roots.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

#: The event the kill watchdog emits once the `docker kill` call returns.
KILL_EVENT = "redis_kill_issued"


def applied_by_run(root: Path) -> dict[str, tuple[str, int]]:
    """``run_id -> (system, applied_effects)`` from the root's own analysis.

    Read from ``analysis/per-execution.csv`` rather than re-derived, so this
    file and the analysis can never disagree -- the same reason
    ``freeze_results.py`` loads runs through ``experiments.analyze.load_run``.
    """
    path = root / "analysis" / "per-execution.csv"
    if not path.is_file():
        raise SystemExit(f"no analysis at {path}; run experiments/analyze.py first")
    out: dict[str, tuple[str, int]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("regime") not in (None, "", "redis-kill-preack"):
                continue
            out[row["run_id"]] = (row["system"], int(row["applied_effects"]))
    return out


def kill_latency_ns(run_directory: Path) -> int | None:
    """The first ``redis_kill_issued`` record's arm-to-return time, in ns.

    One kill per run by construction: the regime sets
    ``redis_kill_executions=1`` and ``executions_per_run=1``, and the injector
    fires once (``self._fired``, redis_kill.py:262). The first match is
    therefore the only one, and reading only the first keeps this linear.
    """
    events = run_directory / "events.jsonl"
    if not events.is_file():
        return None
    with events.open(encoding="utf-8") as handle:
        for line in handle:
            if KILL_EVENT not in line:
                continue
            record = json.loads(line)
            if record.get("event") != KILL_EVENT:
                continue
            value = record.get("issue_to_return_ns")
            return int(value) if value is not None else None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cell",
        action="append",
        required=True,
        metavar="LABEL:FILESYSTEM:PATH",
        help="a results root, its session label and the filesystem it was "
        "collected on; repeatable",
    )
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()

    rows: list[dict[str, object]] = []
    missing: list[str] = []
    for spec in arguments.cell:
        label, filesystem, raw_path = spec.split(":", 2)
        root = Path(raw_path)
        applied = applied_by_run(root)
        for directory in sorted(p for p in root.iterdir() if p.is_dir()):
            if directory.name == "analysis" or directory.name not in applied:
                continue
            latency = kill_latency_ns(directory)
            if latency is None:
                missing.append(f"{label}/{directory.name}")
                continue
            system, effects = applied[directory.name]
            rows.append(
                {
                    "session": label,
                    "filesystem": filesystem,
                    "run_id": directory.name,
                    "system": system,
                    "applied": 1 if effects > 0 else 0,
                    "issue_to_return_ns": latency,
                }
            )

    if missing:
        # A run with no kill event is not a run with a fast kill: it is a run
        # whose fault may not have landed, and averaging over it would hide
        # that. Refuse rather than emit a quietly shorter file.
        raise SystemExit(
            f"{len(missing)} run(s) have no {KILL_EVENT} event: "
            f"{', '.join(missing[:5])}"
        )

    rows.sort(key=lambda row: (row["session"], row["system"], row["run_id"]))
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    # LF explicitly, on every platform. The other committed files under
    # reports/raw/ are LF and .gitattributes does not cover this directory, so a
    # csv writer left at its default "\r\n" would make the committed bytes depend
    # on which machine ran the extraction. That is the same portability defect
    # this phase found in freeze_results.py; it is not reproduced here.
    with arguments.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {arguments.out}  ({len(rows)} runs)")
    for filesystem in sorted({str(row["filesystem"]) for row in rows}):
        subset = [row for row in rows if row["filesystem"] == filesystem]
        print(f"  {filesystem:6} {len(subset)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
