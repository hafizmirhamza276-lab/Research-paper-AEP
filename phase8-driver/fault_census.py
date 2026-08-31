#!/usr/bin/env python3
"""Per-session census of kills that did not land.

Reads ``matrix-progress.jsonl``, the harness's own structured record, rather
than the collection log.

The first version of this census grepped the log, and got two things wrong at
once. It counted 4 errors where there were 2, because the census itself echoes
the matching lines into the same log it then greps -- a counter that inflates by
reading its own output. And it recorded positions as [3, 120, 26, 120], because
``grep -oE '[0-9]+'`` over ``[3/120]`` yields both the position and the total.
Both are the B11 class: a number that looks live, is never checked against a
known answer, and is wrong.

The count that matters is not the log position but the REPETITION index. The
design is interleaved at run level, so repetition is the session's time axis:
rep0 through rep29, with all four cells visited within each repetition. "rep0
and rep6, then none through rep29" is a statement about clustering. "runs 3 and
26 of 120" is the same fact in units that obscure it.

Usage: fault_census.py <run root> [--write]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FAULT = "FaultInjectionError"


def repetition_of(run_id: str) -> int | None:
    m = re.search(r"-r(\d+)$", run_id or "")
    return int(m.group(1)) if m else None


def census(root: Path) -> dict:
    progress = root / "matrix-progress.jsonl"
    if not progress.is_file():
        raise SystemExit(f"no matrix-progress.jsonl at {progress}")

    # A run can appear more than once: the failed attempt, then the refill.
    # Keyed by (run_id, error) so a refill of the same run does not erase the
    # record of why it needed one.
    faults: list[dict] = []
    other: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for line in progress.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("status") != "failed":
            continue
        run_id = row.get("run_id") or ""
        error = str(row.get("error") or "")
        key = (run_id, error)
        if key in seen:
            continue
        seen.add(key)
        rec = {
            "run_id": run_id,
            "repetition": repetition_of(run_id),
            "error": error,
        }
        m = re.search(r"uptime_in_seconds=(\d+)", error)
        if m:
            rec["uptime_in_seconds"] = int(m.group(1))
        (faults if FAULT in error else other).append(rec)

    faults.sort(key=lambda r: (r["repetition"] is None, r["repetition"]))
    reps = [f["repetition"] for f in faults if f["repetition"] is not None]

    record = {
        "session": root.name,
        "fault_injection_errors": len(faults),
        "other_failures": len(other),
        "failures": faults,
        "other": other,
        "repetitions_with_a_non_landing_kill": reps,
        "repetitions_total": 30,
    }

    if reps:
        record["clustering"] = (
            f"non-landing kills at repetition(s) {', '.join(map(str, reps))} "
            f"of 0-29; last occurrence at rep{max(reps)}, "
            f"none through rep29"
        )
    else:
        record["clustering"] = "no non-landing kills in this session"

    return record


def main(argv: list[str]) -> int:
    root = Path(argv[0]).resolve()
    record = census(root)

    print(f"\n--- FaultInjectionError census: {record['session']} ---")
    print(f"kills that did not land : {record['fault_injection_errors']} of 120")
    print(f"other failures          : {record['other_failures']}")
    for f in record["failures"]:
        up = f.get("uptime_in_seconds")
        print(
            f"  rep{f['repetition']:<3} {f['run_id']}"
            + (f"   uptime_in_seconds={up}" if up is not None else "")
        )
    for o in record["other"]:
        print(f"  OTHER  rep{o['repetition']}  {o['run_id']}: {o['error'][:80]}")
    print(f"clustering: {record['clustering']}")

    if "--write" in argv:
        for target in (root / "fault-injection-census.json",
                       root / "analysis" / "fault-injection-census.json"):
            if target.parent.is_dir():
                target.write_text(json.dumps(record, indent=2) + "\n", newline="\n")
                print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
