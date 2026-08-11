"""Regression tests for regime-separated comparisons and revision statistics."""

from __future__ import annotations

import csv
from pathlib import Path
from statistics import NormalDist

import pytest

from experiments.analyze import (
    CONFIRMED_APPLIED,
    DECLARED_AMBIGUOUS,
    ExecutionRecord,
    RunRecord,
    build_comparisons,
)
from experiments.rebuild_comparisons import build_rows
from experiments.statistics import (
    stratified_cluster_bootstrap_difference,
    wilson_interval,
    wilson_upper_bound,
)


def _run(
    system: str,
    regime: str,
    *,
    applied_effects: tuple[int, ...] = (1,),
    outcomes: tuple[str, ...] | None = None,
    run_id: str | None = None,
) -> RunRecord:
    if outcomes is None:
        outcomes = (CONFIRMED_APPLIED,) * len(applied_effects)
    executions = [
        ExecutionRecord(
            run_id=run_id or f"{regime}-{system}",
            system=system,
            crash_point="mid_dispatch" if regime == "" else "none",
            endpoint="payments",
            response_class="AUTHORITATIVE_READBACK",
            readback_keying="CALLER_REFERENCE",
            execution_id=f"e{index}",
            outcome_class=outcome,
            status="COMPLETED",
            applied_effects=effects,
            crashed=regime == "",
            dispatch_attempts=1,
        )
        for index, (effects, outcome) in enumerate(zip(applied_effects, outcomes))
    ]
    return RunRecord(
        run_id=run_id or f"{regime}-{system}",
        system=system,
        crash_point="mid_dispatch" if regime == "" else "none",
        endpoint="payments",
        response_class="AUTHORITATIVE_READBACK",
        readback_keying="CALLER_REFERENCE",
        seed=1,
        config_digest="digest",
        has_sigkill=True,
        wall_seconds=1.0,
        had_recovery_service=True,
        regime=regime,
        crash_probability=1.0 if regime == "" else 0.0,
        redis_kill_point=(
            "after_intent_before_barrier"
            if regime == "redis-kill-preack"
            else None
        ),
        executions=executions,
    )


def test_analysis_comparisons_never_pool_fault_regimes() -> None:
    runs = []
    for regime in ("", "p0", "redis-kill-preack"):
        runs.append(_run("AEP_FULL", regime))
        runs.append(
            _run(
                "B0_NAIVE_RETRY",
                regime,
                applied_effects=(2,) if regime == "" else (1,),
            )
        )

    rows = build_comparisons(runs, resamples=100, seed=7)
    duplicate_rows = [
        row
        for row in rows
        if row["metric"] == "undetected_duplicate_rate"
        and row["system"] == "B0_NAIVE_RETRY"
    ]

    assert {row["regime"] for row in duplicate_rows} == {
        "crashed",
        "p0",
        "redis-kill-preack",
    }
    crashed = next(row for row in duplicate_rows if row["regime"] == "crashed")
    assert (crashed["system_successes"], crashed["system_total"]) == (1, 1)
    assert (crashed["reference_successes"], crashed["reference_total"]) == (0, 1)
    assert all(row["system_total"] == 1 for row in duplicate_rows)


def test_tracked_analysis_rebuilder_keeps_regimes_separate() -> None:
    per_cell = []
    per_execution = []
    for regime, successes in (
        ("(session-3)", 9),
        ("p0", 0),
        ("redis-kill-preack", 0),
    ):
        for system in ("AEP_FULL", "B0_NAIVE_RETRY"):
            per_cell.append(
                {
                    "regime": regime,
                    "system": system,
                    "metric": "undetected_duplicate_rate",
                    "successes": str(successes if system.startswith("B0") else 0),
                    "total": "10",
                    "runs": "1",
                }
            )
            for index in range(10):
                per_execution.append(
                    {
                        "regime": regime,
                        "system": system,
                        "crash_point": "mid_dispatch",
                        "response_class": "AUTHORITATIVE_READBACK",
                        "readback_keying": "CALLER_REFERENCE",
                        "run_id": f"{regime}-{system}",
                        "outcome_class": CONFIRMED_APPLIED,
                        "crashed": "1" if regime == "(session-3)" else "0",
                    }
                )

    rows = build_rows(per_cell, per_execution, resamples=100, seed=7)
    duplicate_rows = [row for row in rows if row["metric"] == "undetected_duplicate_rate"]
    assert len(duplicate_rows) == 3
    assert all(row["system_total"] == 10 for row in duplicate_rows)
    crashed = next(row for row in duplicate_rows if row["regime"] == "crashed")
    assert crashed["system_successes"] == 9


def test_legacy_crashed_label_is_validated_from_execution_schema() -> None:
    per_cell = [
        {
            "regime": "(session-3)",
            "system": "AEP_FULL",
            "metric": "undetected_duplicate_rate",
            "successes": "0",
            "total": "1",
            "runs": "1",
        }
    ]
    per_execution = [
        {
            "regime": "(session-3)",
            "system": "AEP_FULL",
            "crash_point": "mid_dispatch",
            "response_class": "AUTHORITATIVE_READBACK",
            "readback_keying": "CALLER_REFERENCE",
            "run_id": "bad-label",
            "outcome_class": CONFIRMED_APPLIED,
            "crashed": "0",
        }
    ]

    with pytest.raises(ValueError, match="non-crashed execution"):
        build_rows(per_cell, per_execution, resamples=10, seed=7)


def test_one_sided_95_wilson_bound_uses_the_one_sided_quantile_and_540() -> None:
    z = NormalDist().inv_cdf(0.95)
    expected = z * z / (540 + z * z)
    upper = wilson_upper_bound(0, 540, confidence=0.95)

    assert upper == pytest.approx(expected, rel=1e-12)
    assert upper == pytest.approx(0.0049852880, rel=1e-8)
    assert upper < wilson_interval(0, 540, confidence=0.95)[1]


def test_stratified_run_cluster_interval_supports_revision_margin() -> None:
    # Three runs per stratum, with the fixed stratum mix preserved. These
    # values exercise run-level resampling rather than execution-level Wald
    # arithmetic and produce a non-degenerate interval around the difference.
    system = {
        "s1": [(4, 10), (3, 10), (4, 10)],
        "s2": [(2, 10), (3, 10), (2, 10)],
    }
    reference = {
        "s1": [(3, 10), (3, 10), (4, 10)],
        "s2": [(2, 10), (2, 10), (3, 10)],
    }
    interval = stratified_cluster_bootstrap_difference(
        system, reference, resamples=2_000, seed=11, confidence=0.90
    )

    assert interval.system_clusters == 6
    assert interval.reference_clusters == 6
    assert interval.strata == 2
    assert interval.low < interval.point < interval.high
    assert interval.within(0.20)


def test_committed_crashed_comparison_has_aep_b3_counts_and_cluster_interval() -> None:
    path = Path("experiments/results/matrix/analysis/comparisons-vs-aep-full.csv")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ambiguity = next(
        row
        for row in rows
        if row["regime"] == "crashed"
        and row["system"] == "B3_INTENT_NO_BARRIER"
        and row["metric"] == "known_ambiguity_rate"
    )

    assert (int(ambiguity["system_successes"]), int(ambiguity["system_total"])) == (
        195,
        540,
    )
    assert (
        int(ambiguity["reference_successes"]),
        int(ambiguity["reference_total"]),
    ) == (193, 540)
    assert float(ambiguity["difference_ci_low"]) > -0.05
    assert float(ambiguity["difference_ci_high"]) < 0.05
    assert ambiguity["equivalence_margin_preregistered"] == "False"

    duplicate = next(
        row
        for row in rows
        if row["regime"] == "crashed"
        and row["system"] == "B0_NAIVE_RETRY"
        and row["metric"] == "undetected_duplicate_rate"
    )
    assert (int(duplicate["system_successes"]), int(duplicate["system_total"])) == (
        359,
        450,
    )
    assert (
        int(duplicate["reference_successes"]),
        int(duplicate["reference_total"]),
    ) == (0, 540)
    assert float(duplicate["fisher_p_value"]) == pytest.approx(
        1.152215442865763e-183, rel=1e-12
    )
