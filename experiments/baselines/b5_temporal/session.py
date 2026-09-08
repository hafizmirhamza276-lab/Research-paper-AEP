"""Drive one B5 session: cells x runs, each with its own provider and ledger.

Sequencing only. Every measurement decision lives elsewhere --- the crash points
in ``crash_points.py``, the outcome counts in the shared reconciler, the
verdicts in ``gate.py``, the Start-To-Close in ``collect.py`` --- and this module
is deliberately unable to change any of them.

**Per-run ledger.** Each run gets its own provider and its own
``ground_truth.sqlite3`` inside its run directory, exactly as every WS-4 run had.
That is not a convenience: a shared ledger makes every run's effects
unattributable to that run's workload plan, which is what the attribution gate
voided on and how the requirement was found.

**The stopping rule is the pre-registration's** (`1fecb1f` section 4) and is not
adjustable from here: fixed n, no inspect-and-extend.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.baselines.b5_temporal import collect  # noqa: E402
from experiments.baselines.b5_temporal.worker import (  # noqa: E402
    B5CrashPointNotApplicable,
    resolve_b5_point,
)
from experiments.baselines.contract import SystemId  # noqa: E402
from experiments.baselines.crash_points import (  # noqa: E402
    CrashPointNotApplicable,
    resolve_for_system,
)
from experiments.harness.config import RunConfig  # noqa: E402
from experiments.mock_api.config import load_config  # noqa: E402

ARMS = (SystemId.B5_TEMPORAL, SystemId.B5B_TEMPORAL_AT_MOST_ONCE)

#: `1fecb1f` section 3.1. Primary is one crash point on both endpoints; the
#: secondary sweep is the remaining reachable points on NO_READBACK only, and
#: runs ONLY if the primary completes.
PRIMARY_CRASH_POINT = "after_barrier_before_dispatch"
PRIMARY_ENDPOINTS = ("ledger_postings", "payments")
SECONDARY_CRASH_POINTS = (
    "before_intent_write",
    "mid_dispatch",
    "after_response_before_resolution",
    "after_resolution_before_barrier",
)
SECONDARY_ENDPOINTS = ("ledger_postings",)
RUNS_PER_CELL = 30
EXECUTIONS_PER_RUN = 10


def cells(stage: str):
    if stage == "primary":
        for endpoint in PRIMARY_ENDPOINTS:
            for arm in ARMS:
                yield arm, PRIMARY_CRASH_POINT, endpoint
    else:
        for crash_point in SECONDARY_CRASH_POINTS:
            for endpoint in SECONDARY_ENDPOINTS:
                for arm in ARMS:
                    yield arm, crash_point, endpoint


def injected_point_for(arm: SystemId, crash_point: str) -> str:
    """The point the injector is armed at, for a cell named by the roadmap.

    **Two resolvers, and both must be consulted.**
    ``resolve_for_system`` is the cross-system contract every baseline shares,
    and it is what ``RunConfig`` itself validates against, so it decides whether
    the cell exists at all. But it is *lossy for B5*: it maps both
    ``after_barrier_before_dispatch`` and ``mid_dispatch`` onto the single
    ``BEFORE_REQUEST_TRANSMISSION``, distinguishing them only by deferred
    delivery. B5 has two separately named positions for those moments, so the
    armed point comes from ``resolve_b5_point``, B5's own registered mapping.

    Driving the injector from the lossy resolver would collapse two of the four
    secondary crash points into one -- the same defect this function exists to
    remove, one level further down.
    """
    shared = resolve_for_system(arm, crash_point)     # raises if not applicable
    point = resolve_b5_point(crash_point)             # raises if not applicable
    if shared is None or point is None:
        # Neither resolver returns None for an absent moment; they raise. A None
        # here would mean "no crash injection" for a cell that named one.
        raise ValueError(
            f"{arm.value} cell {crash_point!r} resolved to no crash injection; "
            f"an unarmed run cannot stand in for an armed one"
        )
    return point


def run_config(
    *, run_id, arm, endpoint, seed, results_root, template, crash_point
) -> RunConfig:
    return RunConfig(
        run_id=run_id,
        seed=seed,
        workers=1,
        executions_per_worker=EXECUTIONS_PER_RUN,
        endpoint=endpoint,
        mock_api_config_path=str(template),
        mock_api_base_url="http://127.0.0.1:8099",
        redis_url="redis://127.0.0.1:6381/15",
        results_root=str(results_root),
        system=arm,
        # The CELL's point, in the roadmap vocabulary the frozen B4 comparison
        # is keyed on. Previously a constant, which was invisible while one
        # crash point was collected and silently wrong the moment a second was.
        crash_point=crash_point,
        crash_probability=1.0,
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-root", required=True)
    parser.add_argument("--template", default="/var/tmp/b5-probe/mock-api.yaml")
    parser.add_argument("--stage", choices=("primary", "secondary"), default="primary")
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--deadline-s", type=float, default=120.0)
    arguments = parser.parse_args()

    root = Path(arguments.session_root)
    # R12-in-spirit for the results root. This driver replans from index 0 and
    # APPENDS to b5-runs.jsonl, so a second launch into a used root produces one
    # file holding two sessions with no marker between them -- and the run count
    # is the number every void decision in this workstream is made on. Refusing
    # is the only safe reading of an existing root: resuming is not available
    # (fixed n, no inspect-and-extend) and overwriting destroys the evidence a
    # void is recorded from.
    existing = root / "b5-runs.jsonl"
    if existing.exists():
        print(
            f"REFUSING: {existing} already exists with "
            f"{sum(1 for _ in existing.open(encoding='utf-8'))} run(s). A "
            f"session root is used once. Choose a fresh --session-root; the "
            f"prior attempt is voided and kept, never appended to.",
            file=sys.stderr, flush=True,
        )
        return 2
    root.mkdir(parents=True, exist_ok=True)
    template = Path(arguments.template)
    plan_path = root / f"plan-{arguments.stage}.json"

    planned = []
    for arm, crash_point, endpoint in cells(arguments.stage):
        try:
            point = injected_point_for(arm, crash_point)
        except (CrashPointNotApplicable, B5CrashPointNotApplicable) as exc:
            # Recorded, never aliased onto a neighbour.
            planned.append({"system": arm.value, "crash_point": crash_point,
                            "endpoint": endpoint, "status": "not_applicable",
                            "reason": str(exc)})
            continue
        for index in range(RUNS_PER_CELL):
            planned.append({"system": arm.value, "crash_point": crash_point,
                            "endpoint": endpoint, "repetition": index,
                            # Written into the plan BEFORE the run, so the point
                            # a run was meant to take is recorded independently
                            # of what it reports having taken.
                            "injected_point": point,
                            "status": "planned"})
    plan_path.write_text(json.dumps(planned, indent=2), encoding="utf-8")
    runnable = [p for p in planned if p["status"] == "planned"]
    print(f"stage={arguments.stage} runs planned={len(runnable)} "
          f"not_applicable={len(planned) - len(runnable)}", flush=True)

    done = 0
    for entry in runnable:
        arm = SystemId(entry["system"])
        run_id = (
            f"{arm.value.lower()}-{entry['crash_point']}-{entry['endpoint']}"
            f"-r{entry['repetition']}"
        )
        config = run_config(
            run_id=run_id, arm=arm, endpoint=entry["endpoint"],
            seed=arguments.seed + entry["repetition"],
            results_root=root, template=template,
            crash_point=entry["crash_point"],
        )
        results_dir = config.results_dir
        # The provider is seeded from THIS run's seed, so its fault stream is a
        # function of the run's own record and nothing else. The 2026-09-08
        # session left the template's fixed seed in place for all 120 runs, so
        # every run replayed one fault stream and three of four cells produced a
        # single distinct outcome across thirty runs.
        provider = collect.RunProvider(results_dir, template=template, port=8099,
                                       seed=config.seed)
        if not provider.start():
            record = {"run_id": run_id, "system": arm.value,
                      "crash_point": entry["crash_point"],
                      "response_class": "", "verdict": "VOID_PROVIDER_NEVER_READY",
                      "executions": EXECUTIONS_PER_RUN,
                      "provider_seed": config.seed,
                      "undetected_duplicate_applications": None,
                      "undetected_duplicate_executions": None,
                      "lost_effect_executions": None, "declared_ambiguous": None}
            collect.append_session_record(root, record)
            provider.stop()
            done += 1
            continue
        try:
            record = await collect.run_once(
                config=config,
                mock_api_config=load_config(provider.config_path),
                results_dir=results_dir,
                # From the cell, through the resolvers, recorded in the plan.
                # ``run_once`` independently re-resolves the label and refuses
                # the run if the two disagree.
                crash_point=entry["injected_point"],
                provider_url=provider.url,
                deadline_s=arguments.deadline_s,
                ledger_path=provider.ledger_path,
            )
        finally:
            provider.stop()
        collect.append_session_record(root, record)
        done += 1
        if done % 5 == 0:
            print(f"  {done}/{len(runnable)}", flush=True)

    (root / f"stage-{arguments.stage}-finished.json").write_text(
        json.dumps({"runs": done,
                    "finished_at": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )
    print(f"stage {arguments.stage} finished: {done} runs", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
