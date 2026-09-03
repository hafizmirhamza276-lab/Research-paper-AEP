"""When was this host's wall clock diverging from its monotonic clock, and when
was it not?

Phase 10 reported the E5 gate excluding 18/18 and 29/30 of its own runs for
clock suspension against 7/432 in the frozen matrix, and concluded that "no
timing number can be collected on this host in its current state". Phase 11
measured both clocks directly -- 180 s idle and 330 s under the full test suite
against real Redis -- and found them agreeing to 51 ms, forty times inside the
E5 tolerance.

Those two observations are not contradictory, but only one of them can be a
description of a *state*. This script settles which by measuring the divergence
per run, from the runs' own event logs, across every collection this host holds.

The quantity is the one `analyze.py:484-493` gates on, computed the same way,
plus a second one it does not compute: the spread of `wall_ms - monotonic_ns`
over the individual records. The span difference can only grow; the per-record
spread shows whether the divergence accumulated smoothly or arrived as a step.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
from pathlib import Path

#: analyze.py's threshold, repeated rather than imported so this script can run
#: against a tree where the analysis extras are not installed.
TOLERANCE_SECONDS = 2.0


def iso(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000.0, dt.UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def run_divergence(run: Path) -> dict | None:
    walls: list[int] = []
    monos: list[int] = []
    for log in sorted(run.glob("events*.jsonl")):
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                record = json.loads(line)
            except Exception:
                continue
            if (
                record.get("source") == "runner"
                and "monotonic_ns" in record
                and "wall_ms" in record
            ):
                walls.append(int(record["wall_ms"]))
                monos.append(int(record["monotonic_ns"]))
    if len(walls) < 2:
        return None
    wall_span = (max(walls) - min(walls)) / 1000.0
    mono_span = (max(monos) - min(monos)) / 1e9
    offsets = [w / 1000.0 - m / 1e9 for w, m in zip(walls, monos)]
    return {
        "run": run.name,
        "started_utc": iso(min(walls)),
        "wall_span_seconds": round(wall_span, 3),
        "monotonic_span_seconds": round(mono_span, 3),
        # analyze.py clamps at zero: a wall clock that ran SLOW is not a
        # suspension. Kept unclamped here as well, because the sign is
        # informative about the mechanism and the clamp hides it.
        "suspension_seconds": round(max(0.0, wall_span - mono_span), 3),
        "signed_divergence_seconds": round(wall_span - mono_span, 3),
        "per_record_offset_spread_seconds": round(max(offsets) - min(offsets), 3),
        "records": len(walls),
        "e5_would_drop": (wall_span - mono_span) > TOLERANCE_SECONDS,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--metadata",
        default="/root/aep-raw-archive/ARCHIVE-METADATA.json",
        help="the Phase 11 archive metadata, which enumerates the roots",
    )
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    metadata = json.loads(Path(arguments.metadata).read_text(encoding="utf-8"))
    report: dict = {"tolerance_seconds": TOLERANCE_SECONDS, "roots": {}}

    print(
        f"{'root':44s} {'dropped':>9s} {'median':>9s} "
        f"{'worst':>9s}  collection window (UTC)"
    )
    print("-" * 118)

    for entry in metadata["roots"]:
        base = Path(entry["source_path"])
        if not base.is_dir():
            continue
        rows = []
        for run in sorted(d for d in base.iterdir() if d.is_dir()):
            if run.name == "analysis":
                continue
            row = run_divergence(run)
            if row:
                rows.append(row)
        if not rows:
            continue
        signed = [r["signed_divergence_seconds"] for r in rows]
        dropped = sum(1 for r in rows if r["e5_would_drop"])
        starts = sorted(r["started_utc"] for r in rows)
        report["roots"][entry["label"]] = {
            "runs": len(rows),
            "dropped_by_e5": dropped,
            "median_signed_divergence_seconds": round(statistics.median(signed), 3),
            "worst_signed_divergence_seconds": round(max(signed, key=abs), 3),
            "window_start_utc": starts[0],
            "window_end_utc": starts[-1],
            "runs_detail": rows,
        }
        print(
            f"{entry['label']:44s} "
            f"{dropped:4d}/{len(rows):<4d} "
            f"{statistics.median(signed):+9.3f} {max(signed, key=abs):+9.3f}  "
            f"{starts[0]} .. {starts[-1]}"
        )

    print()
    print("Read the median column, not the worst: a single outlier is an event,")
    print("a median above the tolerance is a state.")

    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
