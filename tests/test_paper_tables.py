"""Tests for the manuscript's number generator (scripts/paper_tables.py).

``scripts/check_paper_numbers.py`` is the gate that keeps the paper honest,
and it cannot run in CI: it needs the frozen results tree, which is published
as an archive rather than committed. So the gate is exercised locally against
real CSVs, and *this* file exercises the arithmetic and the formatting in CI
against synthetic ones. Between them the failure mode "the generator was wrong
and every downstream check agreed with it" needs two independent mistakes.

Four things are pinned here, each because getting it wrong produces a
plausible-looking number rather than an error:

* **p-value rendering.** ``p = 1.0`` is a real and load-bearing value in this
  paper -- it is what an ablation that changes nothing looks like -- and a
  formatter that rounds small p-values to ``0.0000`` or renders 1.0 as
  ``1.0e0`` would either destroy the finding or make it unreadable.
* **The barrier cost is an ablation difference within one fsync policy.**
  Subtracting across policies is the mistake amendment G1 caught, and it
  changes the headline ratio by a factor of five.
* **Void trials do not enter the write-loss rate.** A trial whose acknowledged
  write vanished says nothing about the unacknowledged one.
* **The unwanted-applied-effect rate is a rate over executions**, not a count
  and not a rate over runs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.paper_tables import (
    emit_deployment_choice,
    emit_numbers,
    flakey_macros,
    tex_p_value,
)


def _latency(system: str, median: float, crash_free: int = 3) -> dict[str, str]:
    return {
        "system": system,
        "step_latency_ms_median": str(median),
        "overhead_runs_crash_free": str(crash_free),
    }


EVERYSEC = [
    _latency("AEP_FULL", 4004.9),
    _latency("B3_INTENT_NO_BARRIER", 2038.2),
    _latency("B0_NAIVE_RETRY", 2010.2),
]
ALWAYS = [
    _latency("AEP_FULL", 2063.4),
    _latency("B3_INTENT_NO_BARRIER", 2048.4),
]


# --------------------------------------------------------------- p-values


def test_a_p_value_of_one_renders_as_one() -> None:
    """The ablation's null result is quoted as p = 1.00 in the abstract."""
    assert tex_p_value(1.0) == "1.00"


def test_a_borderline_p_value_stays_decimal() -> None:
    assert tex_p_value(0.9524131997365775) == "0.95"
    assert tex_p_value(0.05) == "0.05"


def test_a_small_p_value_keeps_its_exponent() -> None:
    """Rounding 1.9e-06 to four places would print 0.0000."""
    assert tex_p_value(1.9e-06) == "1.9\\times10^{-6}"
    assert tex_p_value(2.070073888186964e-35) == "2.1\\times10^{-35}"


def test_the_exponent_is_the_real_one_not_a_fixed_string() -> None:
    assert tex_p_value(2.5207678232969033e-12) == "2.5\\times10^{-12}"


# ------------------------------------------------- the deployment choice


def test_the_barrier_cost_subtracts_within_one_fsync_policy(
    tmp_path: Path,
) -> None:
    """Across policies the number is wrong by a factor of five.

    always: 2063.4 - 2048.4 = 15.0  (both arms under `always`)
    across: 2063.4 - 2038.2 = 25.2  (B3 measured under `everysec`)
    """
    emit_deployment_choice(EVERYSEC, ALWAYS, tmp_path)
    table = (tmp_path / "table-deployment-choice.tex").read_text(encoding="utf-8")
    assert "15.0" in table
    assert "25.2" not in table
    # And the everysec row is its own within-policy difference.
    assert "1\\,966.7" in table


def test_the_deployment_table_carries_the_barrier_less_row(
    tmp_path: Path,
) -> None:
    """The B3-mode row is what makes the other two a choice rather than a cost."""
    emit_deployment_choice(EVERYSEC, ALWAYS, tmp_path)
    table = (tmp_path / "table-deployment-choice.tex").read_text(encoding="utf-8")
    assert "B3-mode" in table
    assert "detection only" in table
    assert table.count("detection + prevention") == 2


def test_no_deployment_table_without_the_ablated_arm(tmp_path: Path) -> None:
    """Rather than fall back to a cross-policy subtraction, emit nothing."""
    emit_deployment_choice(EVERYSEC, [_latency("AEP_FULL", 2063.4)], tmp_path)
    assert not (tmp_path / "table-deployment-choice.tex").exists()


# ------------------------------------------------------- the write-loss probe


def _payload(counted: int, ack: int, lost: int, trials: list[dict]) -> dict:
    return {
        "summary": {
            "counted": counted,
            "acknowledged_survived": ack,
            "unacknowledged_lost": lost,
        },
        "trials": trials,
    }


def _trial(
    *, ack: bool = True, window: float = 20.0, barrier: float = 600.0, error=None
) -> dict:
    return {
        "acknowledged_survived": ack,
        "write_to_drop_ms": window,
        "barrier_ms": barrier,
        "error": error,
    }


def test_the_write_loss_macros_pool_across_replications() -> None:
    macros = dict(
        (name, value) for name, value, *_ in flakey_macros(
            [
                _payload(30, 30, 30, [_trial(window=12.4)] * 30),
                _payload(30, 30, 30, [_trial(window=42.6)] * 30),
            ]
        )
    )
    assert macros["FlakeyN"] == "60"
    assert macros["FlakeyAckSurvived"] == "60/60"
    assert macros["FlakeyUnackLost"] == "60/60"
    assert macros["FlakeyWindowMin"] == "12.4"
    assert macros["FlakeyWindowMax"] == "42.6"


def test_a_void_trial_does_not_widen_the_reported_window() -> None:
    """A trial that says nothing must not contribute its timings either."""
    macros = dict(
        (name, value)
        for name, value, *_ in flakey_macros(
            [
                _payload(
                    1,
                    1,
                    1,
                    [_trial(window=20.0), _trial(ack=False, window=9999.0)],
                )
            ]
        )
    )
    assert macros["FlakeyWindowMax"] == "20.0"


def test_an_errored_trial_is_excluded_from_the_windows() -> None:
    macros = dict(
        (name, value)
        for name, value, *_ in flakey_macros(
            [
                _payload(
                    1,
                    1,
                    1,
                    [_trial(window=20.0), _trial(window=9999.0, error="boom")],
                )
            ]
        )
    )
    assert macros["FlakeyWindowMax"] == "20.0"


def test_no_countable_trial_emits_no_macros_rather_than_zeroes() -> None:
    assert flakey_macros([_payload(0, 0, 0, [])]) == []


def test_the_cross_fault_comparison_is_against_the_process_kill_probe() -> None:
    macros = dict(
        (name, value)
        for name, value, *_ in flakey_macros(
            [_payload(60, 60, 60, [_trial()] * 60)]
        )
    )
    # 0/10 lost under a process kill vs 60/60 under write loss.
    assert macros["FlakeyVsProcessKillP"] == "2.5\\times10^{-12}"


# ------------------------------------------- the barrier's own metric


def _kill_row(system: str, applied: int) -> dict[str, str]:
    return {
        "regime": "redis-kill-preack",
        "system": system,
        "response_class": "NO_READBACK",
        "runs": "30",
        "executions": "30",
        "executions_with_an_applied_effect": str(applied),
        "canary_survived": "30",
        "canary_lost": "0",
    }


def test_the_unwanted_applied_effect_rate_is_over_executions(
    tmp_path: Path,
) -> None:
    emit_numbers(
        per_cell=[],
        latency=EVERYSEC,
        kill=[_kill_row("AEP_FULL", 10), _kill_row("B3_INTENT_NO_BARRIER", 28)],
        comparisons=[],
        flakey=[],
        always=ALWAYS,
        coverage={"runs": 398, "executions": 3440, "cells": 115},
        execution_paths={},
        out=tmp_path,
    )
    text = (tmp_path / "numbers.tex").read_text(encoding="utf-8")
    assert "\\newcommand{\\AepUnwantedRate}{0.3333}" in text
    assert "\\newcommand{\\BthreeUnwantedRate}{0.9333}" in text
    assert "\\newcommand{\\UnwantedPrevented}{18}" in text
    assert "\\newcommand{\\UnwantedP}{1.9\\times10^{-6}}" in text


def test_the_barrier_costs_are_within_policy_and_no_ratio_is_emitted(
    tmp_path: Path,
) -> None:
    emit_numbers(
        per_cell=[],
        latency=EVERYSEC,
        kill=[],
        comparisons=[],
        flakey=[],
        always=ALWAYS,
        coverage={"runs": 398, "executions": 3440, "cells": 115},
        execution_paths={},
        out=tmp_path,
    )
    text = (tmp_path / "numbers.tex").read_text(encoding="utf-8")
    assert "\\newcommand{\\BarrierCost}{1\\,966.7}" in text
    assert "\\newcommand{\\BarrierCostAlways}{15.0}" in text
    # No ratio macro. The obvious one -- 1966.7 / 15.0 = 131 -- was emitted
    # and quoted until a cluster bootstrap showed the denominator's 95%
    # interval spans zero. A ratio whose denominator is not distinguishable
    # from zero is not a measurement, and generating it is what let it back
    # into the prose the first time.
    assert "BarrierCostRatio" not in text


def test_every_emitted_macro_carries_a_provenance_comment(
    tmp_path: Path,
) -> None:
    """Amendment F3's rule, checked mechanically rather than by reading."""
    emit_numbers(
        per_cell=[],
        latency=EVERYSEC,
        kill=[_kill_row("AEP_FULL", 10)],
        comparisons=[],
        flakey=[_payload(60, 60, 60, [_trial()] * 60)],
        always=ALWAYS,
        coverage={"runs": 398, "executions": 3440, "cells": 115},
        execution_paths={},
        out=tmp_path,
    )
    lines = (tmp_path / "numbers.tex").read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("\\newcommand"):
            assert index > 0 and lines[index - 1].startswith("%"), (
                f"{line} has no provenance comment above it"
            )
