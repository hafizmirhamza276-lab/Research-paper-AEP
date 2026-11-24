"""The scripted plan must reproduce the plans of already-collected runs.

**This is a baseline, established before the agent workload touches
``worker.py``.** That loop produces every number in the paper, and the agent
integration changes it from *iterate a precomputed tuple* to *ask, execute,
observe, repeat*. A regression there does not announce itself; it quietly
changes the numbers.

So the check is not a snapshot of what ``plan_workload`` prints today — that
would only prove it still agrees with itself. It recomputes the plan from each
tracked run's own ``run-config.json`` and asserts it matches the execution ids
and targets that run actually recorded in ``events.jsonl``, months ago, on the
measurement host. If the agent branch perturbs plan generation in any way, this
fails against real collected data rather than against an expectation written by
the same pass that made the change.

`docs/25` R2: the probe is verified against a known positive before any negative
is trusted. ``test_the_corpus_is_not_empty`` is that check — a version of this
test that silently found no runs would pass by looking at nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.harness.workload import plan_workload

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "experiments" / "results"

#: Enough runs to cover every regime and system without walking 432 directories
#: on every suite run. Chosen by path, so the selection cannot drift with the
#: contents of the tree.
CORPUS_ROOTS = (
    "matrix",
    "ws5-2026-09-10/t2-p30",
    "ws5-2026-09-10/t2-keying",
    "fsync-always-2026-09-14",
    "phase13-armA-s1-2026-09-03",
    "phase13-inflight-s1-2026-09-04",
)

REQUIRED = ("run_id", "seed", "workers", "executions_per_worker",
            "crash_probability")


class _Config:
    """The five fields ``plan_workload`` reads, and nothing else."""

    def __init__(self, data: dict):
        for key in REQUIRED:
            setattr(self, key, data[key])


def _run_directories(limit_per_root: int = 12) -> list[Path]:
    found: list[Path] = []
    for name in CORPUS_ROOTS:
        root = RESULTS / name
        if not root.is_dir():
            continue
        taken = 0
        for entry in sorted(root.iterdir()):
            if taken >= limit_per_root:
                break
            if not entry.is_dir():
                continue
            if (entry / "run-config.json").is_file() and (
                entry / "events.jsonl"
            ).is_file():
                found.append(entry)
                taken += 1
    return found


def _recorded(run: Path) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    targets: set[str] = set()
    with (run / "events.jsonl").open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                if isinstance(event.get("execution_id"), str):
                    ids.add(event["execution_id"])
                if isinstance(event.get("target"), str):
                    targets.add(event["target"])
    return ids, targets


CORPUS = _run_directories()


def test_the_corpus_is_not_empty():
    """R2: a negative from an empty search is not evidence of agreement."""
    assert CORPUS, (
        "no tracked run directory carried both run-config.json and "
        "events.jsonl; this test would otherwise pass by checking nothing"
    )
    assert len(CORPUS) >= 20, f"corpus is only {len(CORPUS)} runs"


@pytest.mark.parametrize(
    "run", CORPUS, ids=lambda p: p.parent.name + "/" + p.name
)
def test_plan_workload_reproduces_the_recorded_plan(run: Path):
    data = json.loads((run / "run-config.json").read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        pytest.skip(f"run-config.json predates {missing}")

    plan = plan_workload(_Config(data))
    assert len(plan) == data["workers"] * data["executions_per_worker"]

    recorded_ids, recorded_targets = _recorded(run)
    if not recorded_ids:
        pytest.skip("this run's events.jsonl records no execution_id")

    planned_ids = {item.execution_id for item in plan}
    planned_targets = {item.target for item in plan}

    # Every id the run recorded must be one the plan generates. The converse
    # need not hold: a run killed early records fewer than it planned.
    assert recorded_ids <= planned_ids, (
        f"{run.name}: recorded execution ids the current plan does not "
        f"generate: {sorted(recorded_ids - planned_ids)[:3]}"
    )
    assert recorded_targets <= planned_targets, (
        f"{run.name}: recorded targets the current plan does not generate: "
        f"{sorted(recorded_targets - planned_targets)[:3]}"
    )


@pytest.mark.parametrize(
    "run", CORPUS[:8], ids=lambda p: p.parent.name + "/" + p.name
)
def test_the_target_is_derived_from_the_execution_id(run: Path):
    """The property the agent workload must not break.

    ``docs/33`` §1.3: the agent workload's pre-registration keeps the target
    harness-assigned precisely so that this stays true and the duplicate metric
    keeps meaning what its name says.
    """
    data = json.loads((run / "run-config.json").read_text(encoding="utf-8"))
    if any(k not in data for k in REQUIRED):
        pytest.skip("run-config.json predates the required fields")
    for item in plan_workload(_Config(data)):
        assert item.target == f"account-{item.execution_id}"


def test_plan_is_a_pure_function_of_the_five_fields():
    """Two calls with equal inputs give byte-identical plans."""
    data = {
        "run_id": "baseline-check", "seed": 20260806, "workers": 3,
        "executions_per_worker": 4, "crash_probability": 0.3,
    }
    first = [i.echo() for i in plan_workload(_Config(data))]
    second = [i.echo() for i in plan_workload(_Config(dict(data)))]
    assert first == second
    assert len(first) == 12


def test_changing_the_seed_changes_the_plan():
    """The counter-check: a test that passed on any input would be vacuous."""
    base = {
        "run_id": "baseline-check", "seed": 1, "workers": 2,
        "executions_per_worker": 2, "crash_probability": 0.5,
    }
    other = dict(base, seed=2)
    assert [i.echo() for i in plan_workload(_Config(base))] != [
        i.echo() for i in plan_workload(_Config(other))
    ]
