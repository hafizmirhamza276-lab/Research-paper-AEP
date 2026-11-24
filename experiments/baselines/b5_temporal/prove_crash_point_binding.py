"""Rule 13 for the crash-point binding, on the real stack, in both directions.

**What was wrong.** ``session.py`` armed one constant point --- literally the
string ``"ACTIVITY_ENTERED_BEFORE_CALL"`` --- for every run, while labelling
cells from the roadmap. On the primary stage, where one crash point is
collected, the constant happened to be right. On the secondary sweep, where
``cells()`` yields four different points, all 240 runs would have taken the same
fault under four different headings, and every downstream reader would have
believed the headings: the injected point is not in the run record, not in the
per-cell metrics, and not in any gate.

**What this proves.**

* **Branch A, once per applicable crash point.** A run labelled with a roadmap
  name records reaching the position *that name resolves to*, and the five
  applicable names resolve to five distinct positions. A constant would fail
  four of the five.
* **Branch B, the mismatch.** A run whose label and armed point disagree is
  refused --- before a worker is spawned and before a provider is called --- and
  reads ``VOID_CRASH_POINT_MISMATCH``. It is not collectable, not merely
  flagged.

Branch B is the one that matters, and it is checked *without a provider*: if the
refusal happened after the run, the absence of one would produce some other
failure and the branch would pass for the wrong reason.

Exit 0 means every branch was observed. Any other exit means the binding is
unproven and the runner must not be used to collect.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.baselines.b5_temporal import collect  # noqa: E402
from experiments.baselines.b5_temporal.gate import RunVerdict  # noqa: E402
from experiments.baselines.b5_temporal.session import (  # noqa: E402
    injected_point_for,
)
from experiments.baselines.contract import SystemId  # noqa: E402
from experiments.baselines.crash_points import (  # noqa: E402
    applicable_roadmap_points,
)
from experiments.harness.config import RunConfig  # noqa: E402
from experiments.mock_api.config import load_config  # noqa: E402

OUT = Path("/var/tmp/b5-point-proof")
TEMPLATE = Path("/var/tmp/b5-probe/mock-api.yaml")
ARM = SystemId.B5_TEMPORAL


def _config(run_id: str, results_root: Path, crash_point: str) -> RunConfig:
    return RunConfig(
        run_id=run_id,
        seed=20260908,
        workers=1,
        executions_per_worker=2,
        endpoint="ledger_postings",
        mock_api_config_path=str(TEMPLATE),
        mock_api_base_url="http://127.0.0.1:8099",
        redis_url="redis://127.0.0.1:6381/15",
        results_root=str(results_root),
        system=ARM,
        crash_point=crash_point,
        crash_probability=1.0,
    )


def _points_in_trace(results_dir: Path) -> list[str]:
    """Every position the worker recorded reaching, in order."""
    trace = results_dir / "trace.jsonl"
    if not trace.exists():
        return []
    points = []
    for line in trace.read_text(errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and entry.get("event") == "b5_point_reached":
            points.append(entry.get("point"))
    return points


async def branch_a() -> tuple[bool, list[dict]]:
    """One real trial per applicable crash point."""
    names = applicable_roadmap_points(ARM)
    print(f"=== branch A: {len(names)} crash points, one real trial each ===",
          flush=True)
    rows = []
    for name in names:
        expected = injected_point_for(ARM, name)
        config = _config(f"pt-{name}-{uuid.uuid4().hex[:6]}", OUT / name, name)
        results_dir = config.results_dir
        results_dir.mkdir(parents=True, exist_ok=True)
        provider = collect.RunProvider(results_dir, template=TEMPLATE, port=8099)
        if not provider.start():
            print(f"  {name}: provider never became healthy", flush=True)
            rows.append({"crash_point": name, "expected": expected,
                         "reached": [], "ok": False, "verdict": "NO_PROVIDER"})
            continue
        try:
            record = await collect.run_once(
                config=config,
                mock_api_config=load_config(provider.config_path),
                results_dir=results_dir,
                crash_point=expected,
                provider_url=provider.url,
                deadline_s=60,
                ledger_path=provider.ledger_path,
            )
        finally:
            provider.stop()

        reached = _points_in_trace(results_dir)
        # The assertion: the position recorded is the one the LABEL resolves to.
        ok = bool(reached) and set(reached) == {expected}
        rows.append({"crash_point": name, "expected": expected,
                     "reached": reached, "ok": ok,
                     "verdict": record["verdict"]})
        print(f"  {name}", flush=True)
        print(f"      label resolves to : {expected}", flush=True)
        print(f"      trace recorded    : {reached or '(nothing)'}", flush=True)
        print(f"      verdict           : {record['verdict']}", flush=True)
        print(f"      records its point : {ok}", flush=True)

    distinct = {r["expected"] for r in rows}
    print(f"\n  distinct positions armed across {len(rows)} cells: "
          f"{len(distinct)}", flush=True)
    all_ok = all(r["ok"] for r in rows) and len(distinct) == len(rows)
    return all_ok, rows


async def branch_b() -> bool:
    """A label and a fault that disagree must not be collectable."""
    print("\n=== branch B: label and fault disagree ===", flush=True)
    label = "mid_dispatch"
    expected = injected_point_for(ARM, label)
    # The constant the defect armed for every cell. For this label it is wrong.
    wrong = injected_point_for(ARM, "after_barrier_before_dispatch")
    assert wrong != expected, "the two points must differ or this proves nothing"

    config = _config(f"pt-mismatch-{uuid.uuid4().hex[:6]}", OUT / "mismatch",
                     label)
    results_dir = config.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)

    # Deliberately NO provider and NO Temporal work: the refusal must come
    # before either is needed. If it came afterwards, this call would fail for a
    # different reason and the branch would pass without proving anything.
    record = await collect.run_once(
        config=config,
        mock_api_config=load_config(TEMPLATE),
        results_dir=results_dir,
        crash_point=wrong,
        provider_url="http://127.0.0.1:9",     # nothing listens here
        deadline_s=5,
        ledger_path=results_dir / "unused.sqlite3",
    )
    voided = record["verdict"] == RunVerdict.VOID_CRASH_POINT_MISMATCH.value
    not_run = not (results_dir / "trace.jsonl").exists()
    print(f"  labelled          : {label} -> {expected}", flush=True)
    print(f"  armed             : {wrong}", flush=True)
    print(f"  verdict           : {record['verdict']}", flush=True)
    print(f"  voided on mismatch: {voided}", flush=True)
    print(f"  nothing was run   : {not_run}", flush=True)
    print(f"  reason            : {record['reason'][:150]}", flush=True)
    return voided and not_run


async def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    a_ok, rows = await branch_a()
    b_ok = await branch_b()

    print("\n=== rule 13 ===", flush=True)
    print(f"  A: every cell recorded the point its label names : {a_ok}",
          flush=True)
    print(f"  B: a disagreeing run voided and did not run      : {b_ok}",
          flush=True)
    (OUT / "summary.json").write_text(
        json.dumps({"branch_a": rows, "branch_a_ok": a_ok, "branch_b_ok": b_ok},
                   indent=2, sort_keys=True),
        encoding="utf-8",
    )
    satisfied = a_ok and b_ok
    print(f"  BOTH BRANCHES OBSERVED: {satisfied}", flush=True)
    return 0 if satisfied else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
