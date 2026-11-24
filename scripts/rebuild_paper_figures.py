"""Redraw the two manuscript analysis figures from tracked per-cell counts.

This is a typesetting reproduction path, not a substitute for the absent raw
archive: it verifies the committed plots against ``per-cell-metrics.csv`` but
does not re-derive that CSV from the 432 raw run directories.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.analyze import FIGURE_REGIME, write_figures


SYSTEM_ORDER = (
    "AEP_FULL",
    "B0_NAIVE_RETRY",
    "B1_LEASE_ONLY",
    "B2_CAS_ONLY",
    "B3_INTENT_NO_BARRIER",
    "B4B_DURABLE_WORKFLOW_AT_MOST_ONCE",
    "B4_DURABLE_WORKFLOW",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--per-cell",
        type=Path,
        default=Path("experiments/results/matrix/analysis/per-cell-metrics.csv"),
    )
    parser.add_argument(
        "--per-execution",
        type=Path,
        default=Path("experiments/results/matrix/analysis/per-execution.csv"),
        help="execution-level evidence used to validate the legacy regime label",
    )
    parser.add_argument("--out", type=Path, default=Path("paper/figures"))
    arguments = parser.parse_args()

    with arguments.per_cell.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with arguments.per_execution.open(newline="", encoding="utf-8") as handle:
        executions = list(csv.DictReader(handle))

    legacy = "(session-3)"
    legacy_executions = [row for row in executions if row.get("regime") == legacy]
    if any(row.get("regime") == legacy for row in rows):
        if not legacy_executions:
            raise SystemExit("legacy per-cell regime lacks execution-level evidence")
        if any(row.get("crashed") != "1" for row in legacy_executions):
            raise SystemExit("legacy per-cell regime contains a non-crashed execution")
        for row in rows:
            if row.get("regime") == legacy:
                row["regime"] = FIGURE_REGIME
    present = {
        row["system"] for row in rows if row.get("regime") == FIGURE_REGIME
    }
    if not present:
        raise SystemExit(
            f"{arguments.per_cell} contains no rows for regime {FIGURE_REGIME!r}"
        )

    ordering = [{"system": system} for system in SYSTEM_ORDER if system in present]
    paths = write_figures(ordering, rows, arguments.out)
    expected = {
        "figure-1-undetected-vs-ambiguity.pdf",
        "figure-2-duplicates-by-crash-point.pdf",
    }
    written = {path.name for path in paths}
    if written != expected:
        raise SystemExit(f"expected {sorted(expected)}, wrote {sorted(written)}")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
