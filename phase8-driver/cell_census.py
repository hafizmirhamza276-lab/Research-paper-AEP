#!/usr/bin/env python3
"""Per-cell run and execution counts, taken directly from the run directories.

Why this exists. Plan §3.4's HALT set includes `executions != runs x 1` in any
cell, and that condition was written specifically to catch what `--resume` can
do: collect a run a second time and double-count its executions. Amendment 4
now uses `--resume` deliberately, to refill runs the harness refused to record.

Those two things point at the same signature. If the check ever fires later,
disentangling an amendment-4 refill from a genuine resume double-count after the
fact would be hard. So the census is taken BEFORE and AFTER every refill and the
comparison is reported explicitly, while the two are still separable.

This reads the run directories rather than `analysis/`, so it can be taken
before `analyze.py` has ever run on the root.

Usage: cell_census.py <run root> [label]
       cell_census.py --compare <before.json> <after.json>
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def census(root: Path) -> dict:
    cells: dict[str, dict] = defaultdict(lambda: {"runs": 0, "executions": 0})
    for d in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "analysis"):
        summary = d / "summary.json"
        if not summary.is_file():
            continue
        try:
            data = json.loads(summary.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        # The cell is the run directory name minus its -rN repetition suffix.
        cell = d.name.rsplit("-r", 1)[0]
        # `executions_planned` is the run's own count of executions. NB
        # `oracle_effect_executions` is NOT it -- that is an int count of
        # executions that applied an effect, and reading it here would silently
        # report the applied column as the execution column.
        classifications = data.get("classifications")
        if isinstance(data.get("executions_planned"), int):
            n = data["executions_planned"]
        elif isinstance(classifications, list):
            n = len(classifications)
        else:
            raise KeyError(f"no execution count in {summary}")
        cells[cell]["runs"] += 1
        cells[cell]["executions"] += n

    return {
        "root": root.name,
        "cells": {k: dict(v) for k, v in sorted(cells.items())},
        "total_runs": sum(v["runs"] for v in cells.values()),
        "total_executions": sum(v["executions"] for v in cells.values()),
    }


def show(record: dict, label: str) -> None:
    print(f"\n--- cell census: {label} ({record['root']}) ---")
    print(f"{'cell':<52} {'runs':>6} {'execs':>7}  exec==runs")
    for cell, v in record["cells"].items():
        ok = "OK" if v["executions"] == v["runs"] else "** MISMATCH **"
        print(f"{cell:<52} {v['runs']:>6} {v['executions']:>7}  {ok}")
    print(f"{'TOTAL':<52} {record['total_runs']:>6} {record['total_executions']:>7}")


def compare(before: dict, after: dict) -> int:
    print("\n--- refill comparison: the resume double-count check ---")
    print(f"{'cell':<52} {'runs':>11} {'execs':>13}")
    bad = 0
    for cell in sorted(set(before["cells"]) | set(after["cells"])):
        b = before["cells"].get(cell, {"runs": 0, "executions": 0})
        a = after["cells"].get(cell, {"runs": 0, "executions": 0})
        dr = a["runs"] - b["runs"]
        de = a["executions"] - b["executions"]
        note = ""
        if a["executions"] != a["runs"]:
            note = "  ** executions != runs x 1 -- HALT **"
            bad += 1
        elif dr != de:
            note = f"  ** {dr} new run(s) but {de} new execution(s) **"
            bad += 1
        elif dr > 0:
            note = f"  refilled +{dr}"
        print(
            f"{cell:<52} {b['runs']:>4} -> {a['runs']:<4} "
            f"{b['executions']:>5} -> {a['executions']:<5}{note}"
        )
    print(
        f"\ntotals: runs {before['total_runs']} -> {after['total_runs']}, "
        f"executions {before['total_executions']} -> {after['total_executions']}"
    )
    if bad:
        print(f"\n*** {bad} cell(s) fail the double-count check -- HALT ***")
        return 1
    print(
        "\nevery cell holds executions == runs x 1 after the refill, and each "
        "cell's run and execution deltas agree: no resume double-count"
    )
    return 0


def main(argv: list[str]) -> int:
    if argv[0] == "--compare":
        before = json.loads(Path(argv[1]).read_text())
        after = json.loads(Path(argv[2]).read_text())
        show(before, "BEFORE refill")
        show(after, "AFTER refill")
        return compare(before, after)

    root = Path(argv[0]).resolve()
    label = argv[1] if len(argv) > 1 else "census"
    record = census(root)
    show(record, label)
    out = root / f"cell-census-{label}.json"
    out.write_text(json.dumps(record, indent=2) + "\n", newline="\n")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
