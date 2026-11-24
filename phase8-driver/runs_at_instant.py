#!/usr/bin/env python3
"""How many runs of a session had completed at a given instant.

Used to state exactly, rather than estimate, how far into session 3's collection
commit 38ad8cd landed. Reads matrix-progress.jsonl, which R2 names as the
authoritative structured record -- not the session log, whose FAILED count is
corrupted by tee (B14).

Read-only.

Usage: runs_at_instant.py <run root> <iso instant>
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


def main(argv: list[str]) -> int:
    root = Path(argv[0])
    cut = datetime.fromisoformat(argv[1])
    path = root / "matrix-progress.jsonl"

    stamps = []
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        keys |= set(rec.keys())
        # matrix-progress.jsonl records when a run STARTED and how long it took.
        # A run's completion is started_at + wall_seconds; both are needed,
        # because "how many runs had finished" and "how many had begun" are
        # different questions and the second overstates progress by one.
        if "started_at" not in rec:
            continue
        try:
            begin = datetime.fromisoformat(str(rec["started_at"]))
        except ValueError:
            continue
        wall = rec.get("wall_seconds")
        stamps.append((begin, begin + timedelta(seconds=float(wall)) if wall else begin))

    if not stamps:
        print(f"no parsable timestamps; keys seen: {sorted(keys)}")
        return 1

    stamps.sort()
    started = [b for b, _ in stamps if b <= cut]
    finished = [e for _, e in stamps if e <= cut]
    print(f"root             : {root.name}")
    print(f"progress records : {len(stamps)}")
    print(f"first run started: {stamps[0][0].isoformat()}")
    print(f"last run ended   : {max(e for _, e in stamps).isoformat()}")
    print(f"instant          : {cut.isoformat()}")
    print(f"runs STARTED at or before the instant : {len(started)}")
    print(f"runs FINISHED at or before the instant: {len(finished)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
