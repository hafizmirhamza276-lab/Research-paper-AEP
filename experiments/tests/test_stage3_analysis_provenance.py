"""Regression gates for Stage 3 statistical and raw-data provenance rules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments import analyze
from experiments.analyze import (
    AnalysisError,
    ExecutionRecord,
    RunRecord,
    build_executions_csv,
    build_table_one,
    compute_metric,
    load_runs,
    load_voided_attempts,
    validate_plan_manifest,
)
from experiments.statistics import Interval


def _run(run_id: str, seed: int, *, regime: str = "") -> RunRecord:
    execution = ExecutionRecord(
        run_id=run_id,
        system="AEP_FULL",
        crash_point="mid_dispatch" if regime == "" else "none",
        endpoint="payments",
        response_class="AUTHORITATIVE_READBACK",
        readback_keying="CALLER_REFERENCE",
        execution_id=f"{run_id}-e0",
        outcome_class="CONFIRMED_APPLIED",
        status="FIRED_CONFIRMED",
        applied_effects=1,
        crashed=regime == "",
        dispatch_attempts=1,
    )
    return RunRecord(
        run_id=run_id,
        system="AEP_FULL",
        crash_point=execution.crash_point,
        endpoint=execution.endpoint,
        response_class=execution.response_class,
        readback_keying=execution.readback_keying,
        seed=seed,
        config_digest="digest",
        has_sigkill=True,
        wall_seconds=1.0,
        dataset_version="stage3-test",
        experiment_plan_sha256="a" * 64,
        git_sha="b" * 40,
        redis_durability="everysec",
        redis_version="7.2.5",
        redis_image="redis@example",
        source_raw_directory_hash="c" * 64,
        regime=regime,
        crash_probability=1.0 if regime == "" else 0.0,
        executions=[execution],
    )


def test_cross_regime_summary_excludes_non_crashed_runs() -> None:
    rows = build_table_one(
        [_run("crashed", 1), _run("p0", 2, regime="p0")],
        resamples=20,
        seed=3,
    )
    assert rows
    assert {row["regime"] for row in rows} == {"crashed"}
    assert sum(int(row["executions"]) for row in rows) == 1


def test_rate_bootstrap_receives_runs_not_executions(monkeypatch) -> None:
    runs = [_run("r1", 1), _run("r2", 2)]
    for index, run in enumerate(runs):
        run.executions.extend(
            [
                ExecutionRecord(
                    **{
                        **run.executions[0].__dict__,
                        "execution_id": f"{run.run_id}-extra-{extra}",
                    }
                )
                for extra in range(9)
            ]
        )
    observed = {}

    def capture(clusters, **_kwargs):
        observed["clusters"] = list(clusters)
        return Interval(0.0, 0.0, 0.0, 1, 1, len(clusters), 20)

    monkeypatch.setattr(analyze, "cluster_bootstrap_proportion", capture)
    compute_metric("lost_effect_rate", runs, {}, resamples=10, seed=1)
    assert observed["clusters"] == [(0, 10), (0, 10)]


def test_duplicate_seeds_within_dataset_and_durability_are_refused(
    tmp_path: Path, monkeypatch
) -> None:
    for name in ("r1", "r2"):
        (tmp_path / name).mkdir()
    records = {"r1": _run("r1", 7), "r2": _run("r2", 7)}
    monkeypatch.setattr(analyze, "load_run", lambda path: records[path.name])
    with pytest.raises(AnalysisError, match="duplicate seeds"):
        load_runs(tmp_path)


def test_per_execution_rows_carry_complete_provenance() -> None:
    row = build_executions_csv([_run("r1", 7)])[0]
    required = {
        "dataset_version", "regime", "system", "endpoint", "crash_point",
        "response_class", "readback_keying", "redis_durability", "run_id",
        "run_seed", "run_execution_count", "inclusion_status",
        "source_raw_directory_hash", "git_sha", "experiment_plan_sha256",
    }
    assert required <= row.keys()
    assert all(row[name] not in (None, "") for name in required)


def test_voided_directory_without_reason_is_refused(tmp_path: Path) -> None:
    (tmp_path / "voided" / "run-attempt-001").mkdir(parents=True)
    with pytest.raises(AnalysisError, match="accounting mismatch"):
        load_voided_attempts(tmp_path)


def test_plan_and_included_run_count_must_agree(tmp_path: Path) -> None:
    plan = {
        "dataset_version": "stage3-test",
        "runs": [{"run_id": "r1"}, {"run_id": "r2"}],
    }
    (tmp_path / "matrix-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(AnalysisError, match="manifest/count disagreement"):
        validate_plan_manifest(tmp_path, [_run("r1", 1)], [])


def test_incomplete_infrastructure_directory_is_never_silently_included(
    tmp_path: Path,
) -> None:
    (tmp_path / "interrupted-run").mkdir()
    with pytest.raises(AnalysisError, match="results/voided"):
        load_runs(tmp_path)
