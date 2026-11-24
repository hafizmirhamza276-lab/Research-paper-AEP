#!/usr/bin/env python3
"""Slice the continuous foreign-load sample into one session's window.

Observation only. No registered gate reads this, and nothing in the analysis
depends on it. It exists because session 2 demonstrated that a start-of-session
container snapshot cannot see load that arrives mid-session: session 2's own
precondition recorded `foreign_running_before: []` correctly, two foreign
postgres containers appeared during the run, and they were removed within four
minutes of finally being noticed 43 minutes after the session ended.

Honesty requirements this file enforces by recording them in its own output:

  * `coverage_note` states when sampling began relative to the session, so a
    reader can see that session 3's series starts partway in and that session 2
    has no series at all.
  * The absence of foreign load in a sampled window is only as strong as the
    sampling interval. A container that lived for less than the interval can be
    missed entirely, and both containers seen in Phase 8.4 were ephemeral. The
    output says so rather than letting an empty list read as proof of quiet.

Usage: slice_load.py <run root> <session log> <samples jsonl>
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path


def parse_window(log: Path) -> tuple[str | None, str | None]:
    start = end = None
    text = log.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"collection starting at (\S+)", text)
    if m:
        start = m.group(1).rstrip("=").strip()
    m = re.search(r"(\S+) complete at (\S+)", text)
    if m:
        end = m.group(2).rstrip("=").strip()
    if end is None:
        m = re.search(r"session .* complete at (\S+)", text)
        if m:
            end = m.group(1).rstrip("=").strip()
    return start, end


def main(argv: list[str]) -> int:
    root = Path(argv[0]).resolve()
    log = Path(argv[1])
    samples = Path(argv[2])

    if not samples.is_file():
        print(f"no sample file at {samples}")
        return 1

    start, end = parse_window(log)
    if not start:
        print("could not determine the session's collection window from the log")
        return 1

    t0 = datetime.fromisoformat(start)
    t1 = datetime.fromisoformat(end) if end else None

    kept = []
    first_sample = None
    for line in samples.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            t = datetime.fromisoformat(rec["t"])
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        if first_sample is None or t < first_sample:
            first_sample = t
        if t < t0:
            continue
        if t1 and t > t1:
            continue
        kept.append(rec)

    foreign_names: dict[str, int] = {}
    for rec in kept:
        for name in rec.get("foreign_running", []):
            foreign_names[name] = foreign_names.get(name, 0) + 1

    gap = None
    if first_sample and first_sample > t0:
        gap = round((first_sample - t0).total_seconds())

    out = {
        "session": root.name,
        "window_start": start,
        "window_end": end,
        "samples": len(kept),
        "interval_seconds": 60,
        "foreign_running_seen": foreign_names,
        "foreign_free_samples": sum(
            1 for r in kept if not r.get("foreign_running")
        ),
        "coverage_note": (
            f"sampling began {gap} s after this session's collection started; "
            f"the first {gap} s are unsampled"
            if gap
            else "sampling covered the whole window"
        ),
        "interpretation_limit": (
            "An empty or sparse foreign list bounds only what was visible at "
            "60 s resolution. A container living less than one interval can be "
            "missed entirely, and both foreign containers observed in Phase 8.4 "
            "were removed within four minutes. Absence here is weak evidence of "
            "quiet, not proof of it."
        ),
        "session_2_has_no_series": (
            "Sampling was added mid-collection, after session 2. Session 2 has "
            "no series; sessions 3 and 4 are not uniformly instrumented with it."
        ),
        "records": kept,
    }

    for target in (root / "foreign-load-sample.json",
                   root / "analysis" / "foreign-load-sample.json"):
        if target.parent.is_dir():
            target.write_text(json.dumps(out, indent=2) + "\n", newline="\n")
            print(f"wrote {target}")

    print(f"  samples in window     : {len(kept)}")
    print(f"  foreign running seen  : {foreign_names or 'none'}")
    print(f"  coverage              : {out['coverage_note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
