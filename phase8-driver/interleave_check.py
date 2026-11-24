#!/usr/bin/env python3
"""Was a session collected cell-major or run-level interleaved?

Amendment 1 changed build_plan's sort key from (tier, cell_key, repetition) to
(tier, repetition, cell_key), so that both arms are drawn from the same part of
a session's latency drift. Which sessions actually ran under it decides whether
they can be pooled, and therefore decides k.

Determined from each session's OWN recorded execution order in
matrix-progress.jsonl -- not from a commit hash, and not from what a report says.
The file is written in execution order, so the ordering is directly observable:

  cell-major   -> cell_key is constant for a long stretch while repetition climbs
  interleaved  -> repetition is constant for a short stretch while cell_key cycles

The diagnostic is the number of cell_key CHANGES between consecutive runs. With
c cells and r repetitions, interleaved gives roughly r*(c-1) changes and
cell-major gives about c-1. They differ by orders of magnitude, so this does not
depend on a threshold being tuned.

Read-only.

Usage: interleave_check.py <run root> [<run root> ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    for arg in argv:
        root = Path(arg)
        path = root / "matrix-progress.jsonl"
        if not path.is_file():
            print(f"{root.name}: no matrix-progress.jsonl")
            continue

        recs = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        cells = [r.get("cell_key") for r in recs]
        reps = [r.get("repetition") for r in recs]
        n_cells = len(set(cells))
        n_reps = len(set(reps))

        cell_changes = sum(1 for a, b in zip(cells, cells[1:]) if a != b)
        rep_changes = sum(1 for a, b in zip(reps, reps[1:]) if a != b)

        # Longest run of a single cell_key: ~repetitions if cell-major, ~1 if
        # interleaved.
        longest = cur = 1
        for a, b in zip(cells, cells[1:]):
            cur = cur + 1 if a == b else 1
            longest = max(longest, cur)

        expect_interleaved = n_reps * (n_cells - 1)
        expect_cellmajor = n_cells - 1
        verdict = (
            "INTERLEAVED"
            if abs(cell_changes - expect_interleaved)
            < abs(cell_changes - expect_cellmajor)
            else "CELL-MAJOR"
        )

        print(f"{root.name}")
        print(f"  runs {len(recs)}   cells {n_cells}   repetitions {n_reps}")
        print(f"  cell_key changes between consecutive runs : {cell_changes}")
        print(f"    expected if interleaved                 : ~{expect_interleaved}")
        print(f"    expected if cell-major                  : ~{expect_cellmajor}")
        print(f"  repetition changes                        : {rep_changes}")
        print(f"  longest consecutive run of one cell_key   : {longest}")
        print(f"  first 8 (repetition, cell_key)            : "
              f"{[(r, (c or '')[:22]) for r, c in list(zip(reps, cells))[:8]]}")
        print(f"  VERDICT: {verdict}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
