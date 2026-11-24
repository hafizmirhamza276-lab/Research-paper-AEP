"""How far through the current matrix invocation are we, and what remains.

Reads the emitted plan and the results directory. Nothing here writes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument(
        "--system", action="append", default=[], help="restrict to these systems"
    )
    parser.add_argument("--max-tier", type=int, default=None)
    arguments = parser.parse_args()

    plan_path = arguments.results_root / "matrix-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    runs = plan["runs"] if isinstance(plan, dict) else plan

    selected = []
    for run in runs:
        if arguments.system and run.get("system") not in arguments.system:
            continue
        if arguments.max_tier is not None and run.get("tier", 1) > arguments.max_tier:
            continue
        selected.append(run)

    done = 0
    pending: Counter[str] = Counter()
    for run in selected:
        run_id = run.get("run_id") or run.get("id")
        summary = arguments.results_root / str(run_id) / "summary.json"
        if summary.is_file():
            done += 1
        else:
            pending[f"{run.get('system')} / {run.get('response_class')}"] += 1

    print(f"plan file      {plan_path}")
    print(f"selected runs  {len(selected)}")
    print(f"collected      {done}")
    print(f"remaining      {len(selected) - done}")
    if pending:
        print("\nremaining by system / response class:")
        for key, count in sorted(pending.items()):
            print(f"  {key:<52} {count}")
    estimate = sum(
        float(r.get("estimated_seconds") or 0)
        for r in selected
        if not (arguments.results_root / str(r.get("run_id") or r.get("id")) / "summary.json").is_file()
    )
    if estimate:
        print(f"\nestimated remaining wall time  {estimate / 3600:.2f} h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
