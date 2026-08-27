"""Tests for the manuscript's number generator (scripts/paper_tables.py).

``scripts/check_paper_numbers.py`` is the gate that keeps the paper honest.
It runs in CI as of Phase P -- the analysis products it reads are tracked by
name (see the tail of ``.gitignore``) and the ``paper-numbers`` job builds the
manuscript and runs it. It checks the generator's *output* against the real
CSVs; *this* file checks the generator's arithmetic and formatting against
synthetic ones. Between them the failure mode "the generator was wrong and
every downstream check agreed with it" needs two independent mistakes.

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
import re
from pathlib import Path

import pytest

from scripts.paper_tables import (
    CRASHED_REGIME,
    ROOT,
    emit_deployment_choice,
    emit_numbers,
    emit_outcomes_table,
    flakey_macros,
    mann_whitney_two_tailed,
    tex_p_value,
    tex_sigfigs,
)


def _cell(
    metric: str,
    system: str,
    response: str,
    successes: int,
    total: int = 180,
    crash_point: str = "mid_dispatch",
) -> dict[str, str]:
    return {
        "metric": metric,
        "regime": CRASHED_REGIME,
        "system": system,
        "crash_point": crash_point,
        "response_class": response,
        "readback_keying": "CALLER_REFERENCE",
        "successes": str(successes),
        "total": str(total),
        "runs": "18",
    }


RESPONSES = (
    "AUTHORITATIVE_READBACK",
    "POSITIVE_ONLY_READBACK",
    "NO_READBACK",
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


def _kill_row(
    system: str, applied: int, response_class: str = "NO_READBACK"
) -> dict[str, str]:
    return {
        "regime": "redis-kill-preack",
        "system": system,
        "response_class": response_class,
        "runs": "30",
        "executions": "30",
        "executions_with_an_applied_effect": str(applied),
        "canary_survived": "30",
        "canary_lost": "0",
    }


def _numbers_from_kill(kill: list[dict[str, str]], out: Path) -> str:
    out.mkdir(parents=True, exist_ok=True)
    emit_numbers(
        per_cell=[],
        latency=EVERYSEC,
        kill=kill,
        comparisons=[],
        flakey=[],
        always=ALWAYS,
        coverage={"runs": 398, "executions": 3440, "cells": 115},
        execution_paths={},
        out=out,
    )
    return (out / "numbers.tex").read_text(encoding="utf-8")


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


# ------------------------ two capability classes must not collide (B2/C-2)
#
# `analyze.py` groups redis-kill evidence by ["regime", "system",
# "response_class"], so collecting a second capability class makes
# redis-kill-ablation.csv 2N rows. Keying the macros by system alone let the
# last row win: \AepKillApplied and friends silently re-bound to whichever
# class sorted last while section 6.2.2's prose named `no-readback`, and the
# numbers gate passed over it because the macros still regenerated
# byte-identically from the new CSV. These tests fail on that binding.


def _four_rows() -> list[dict[str, str]]:
    """Two systems x two capability classes, with deliberately distinct counts."""
    return [
        _kill_row("AEP_FULL", 10, "NO_READBACK"),
        _kill_row("B3_INTENT_NO_BARRIER", 28, "NO_READBACK"),
        _kill_row("AEP_FULL", 4, "AUTHORITATIVE_READBACK"),
        _kill_row("B3_INTENT_NO_BARRIER", 25, "AUTHORITATIVE_READBACK"),
    ]


def test_two_capability_classes_bind_to_distinct_macros(tmp_path: Path) -> None:
    text = _numbers_from_kill(_four_rows(), tmp_path)
    # headline stays the class the manuscript's prose describes
    assert "\\newcommand{\\AepKillApplied}{10}" in text
    assert "\\newcommand{\\BthreeKillApplied}{28}" in text
    # the second class gets its own names rather than overwriting them
    assert "\\newcommand{\\AepAuthKillApplied}{4}" in text
    assert "\\newcommand{\\BthreeAuthKillApplied}{25}" in text


def test_the_headline_kill_macros_are_independent_of_row_order(
    tmp_path: Path,
) -> None:
    """The exact silent-rebinding this fix exists to prevent.

    Both orderings are asserted deliberately. Reversal alone is not a test:
    it happens to place NO_READBACK last, which the broken binding also gets
    right by luck. The forward order is the one that discriminates.
    """
    for name, rows in (("forward", _four_rows()),
                       ("reversed", list(reversed(_four_rows())))):
        text = _numbers_from_kill(rows, tmp_path / name)
        # `in text` is not enough: the broken binding emitted the macro TWICE,
        # once per class, so a substring check matches the first emission and
        # passes while LaTeX would take the last. Assert the definition is
        # unique and then assert its value.
        defs = re.findall(r"\\newcommand\{\\AepKillApplied\}\{([^}]*)\}", text)
        assert defs == ["10"], (
            f"{name} order: \\AepKillApplied defined {len(defs)} time(s) as "
            f"{defs}; it must be defined once, from the no-readback row that "
            "the manuscript's prose describes"
        )
        b3 = re.findall(r"\\newcommand\{\\BthreeKillApplied\}\{([^}]*)\}", text)
        assert b3 == ["28"], f"{name} order: {b3}"


def test_the_cross_system_macros_come_from_the_headline_class_only(
    tmp_path: Path,
) -> None:
    """UnwantedPrevented is 28-10, never 25-4."""
    text = _numbers_from_kill(_four_rows(), tmp_path)
    assert "\\newcommand{\\UnwantedPrevented}{18}" in text
    assert "\\newcommand{\\UnwantedPrevented}{21}" not in text


def _kill_macro_names(text: str) -> list[str]:
    names = re.findall(r"\\newcommand\{\\(\w*Kill(?:Applied|Runs|Canary))\}", text)
    return names + re.findall(r"\\newcommand\{\\(\w*UnwantedRate)\}", text)


def test_the_kill_macro_count_is_exactly_what_the_rows_justify(
    tmp_path: Path,
) -> None:
    """An explicit count, and -- the part that discriminates -- no duplicates.

    The count alone does not catch the broken binding: it emitted one macro per
    row either way. What it emitted for four rows was
    ``\\newcommand{\\AepKillApplied}`` **twice**, which is a LaTeX redefinition
    error and a silently different number depending on which won.
    """
    two = _kill_macro_names(_numbers_from_kill(_four_rows()[:2], tmp_path / "two"))
    four = _kill_macro_names(_numbers_from_kill(_four_rows(), tmp_path / "four"))
    assert len(two) == 8, "2 rows x 4 per-arm macros"
    assert len(four) == 16, "4 rows x 4 per-arm macros"
    assert len(set(two)) == len(two), "duplicate macro names for 2 rows"
    assert len(set(four)) == len(four), (
        "duplicate macro names: %s"
        % sorted({n for n in four if four.count(n) > 1})
    )


def test_a_duplicate_system_and_class_pair_is_refused(tmp_path: Path) -> None:
    rows = _four_rows() + [_kill_row("AEP_FULL", 99, "NO_READBACK")]
    with pytest.raises(SystemExit, match="two rows"):
        _numbers_from_kill(rows, tmp_path)


def test_a_missing_headline_class_is_refused(tmp_path: Path) -> None:
    """Refuse to bind the prevention macros to a class the prose does not name."""
    rows = [
        _kill_row("AEP_FULL", 4, "AUTHORITATIVE_READBACK"),
        _kill_row("B3_INTENT_NO_BARRIER", 25, "AUTHORITATIVE_READBACK"),
    ]
    with pytest.raises(SystemExit, match="NO_READBACK"):
        _numbers_from_kill(rows, tmp_path)


def test_an_unknown_response_class_is_refused(tmp_path: Path) -> None:
    rows = _four_rows() + [_kill_row("AEP_FULL", 7, "SOMETHING_NEW")]
    with pytest.raises(SystemExit, match="no macro suffix"):
        _numbers_from_kill(rows, tmp_path)


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


# ------------------------------------------------- the capability classes


def test_the_engine_macros_cover_every_capability_class(
    tmp_path: Path,
) -> None:
    """The omission that cost the paper a wrong number.

    B4's and B4b's macro loop listed two of the three capability classes
    while the third was still being collected. When that cell landed, the
    prose that wanted to quote it had no macro to quote and quoted a
    hand-written 0.9500 instead -- which the completed cell then contradicted
    by a factor of 1.8 (phase report 5A, sections E.5 and G.1). A class
    missing here is a number the manuscript types by hand, so the coverage is
    pinned rather than trusted.
    """
    per_cell = []
    for response in RESPONSES:
        per_cell.append(
            _cell("undetected_duplicate_rate", "B4_DURABLE_WORKFLOW", response, 95)
        )
        per_cell.append(
            _cell(
                "lost_effect_rate",
                "B4B_DURABLE_WORKFLOW_AT_MOST_ONCE",
                response,
                98,
            )
        )
    emit_numbers(
        per_cell=per_cell,
        latency=EVERYSEC,
        kill=[],
        comparisons=[],
        flakey=[],
        always=ALWAYS,
        coverage={},
        execution_paths={},
        out=tmp_path,
    )
    text = (tmp_path / "numbers.tex").read_text(encoding="utf-8")
    for suffix in ("Auth", "PosOnly", "NoReadback"):
        assert f"\\newcommand{{\\BfourDup{suffix}}}" in text
        assert f"\\newcommand{{\\BfourExec{suffix}}}" in text
        assert f"\\newcommand{{\\BfourbLost{suffix}}}" in text
        assert f"\\newcommand{{\\BfourbExec{suffix}}}" in text


def test_the_engine_ambiguity_ceiling_is_a_max_not_a_pooled_rate(
    tmp_path: Path,
) -> None:
    """One nonzero cell must move the number the manuscript quotes.

    The claim built on this macro is "never above this", so a mean would let
    a single declaring cell hide behind thirty-five silent ones.
    """
    per_cell = [
        _cell("known_ambiguity_rate", "B4_DURABLE_WORKFLOW", r, 0)
        for r in RESPONSES
    ]
    per_cell.append(
        _cell(
            "known_ambiguity_rate",
            "B4B_DURABLE_WORKFLOW_AT_MOST_ONCE",
            "NO_READBACK",
            18,
        )
    )
    emit_numbers(
        per_cell=per_cell,
        latency=EVERYSEC,
        kill=[],
        comparisons=[],
        flakey=[],
        always=ALWAYS,
        coverage={},
        execution_paths={},
        out=tmp_path,
    )
    text = (tmp_path / "numbers.tex").read_text(encoding="utf-8")
    assert "\\newcommand{\\BfourFamilyAmbMax}{0.1000}" in text
    assert "\\newcommand{\\BfourFamilyAmbCells}{4}" in text


# ------------------------------------------------------------- the caption


def test_the_outcomes_caption_names_every_system_it_claims_is_unique(
    tmp_path: Path,
) -> None:
    """The caption must be derivable from the table underneath it.

    It read "AEP-full is the only system with a nonzero declared-ambiguity
    column, and the only one whose other two columns are zero everywhere"
    while the B3 row directly above the caption's own numbers falsified both
    halves. Rather than pin the replacement wording, this derives the set of
    systems the claim is about from the rows and requires the caption to name
    all of them.
    """
    per_cell = []
    for response in RESPONSES:
        # B3 and AEP-full: ambiguity only. B0: duplicates only.
        per_cell.append(
            _cell("known_ambiguity_rate", "B3_INTENT_NO_BARRIER", response, 66)
        )
        per_cell.append(_cell("known_ambiguity_rate", "AEP_FULL", response, 63))
        per_cell.append(_cell("known_ambiguity_rate", "B0_NAIVE_RETRY", response, 0))
        for metric in ("undetected_duplicate_rate", "lost_effect_rate"):
            per_cell.append(_cell(metric, "B3_INTENT_NO_BARRIER", response, 0))
            per_cell.append(_cell(metric, "AEP_FULL", response, 0))
        per_cell.append(
            _cell("undetected_duplicate_rate", "B0_NAIVE_RETRY", response, 147)
        )
        per_cell.append(_cell("lost_effect_rate", "B0_NAIVE_RETRY", response, 2))

    emit_outcomes_table(per_cell, tmp_path)
    caption = next(
        line
        for line in (tmp_path / "table-outcomes.tex")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.startswith("\\caption{")
    )
    # Every system that reaches the third corner has to appear in a caption
    # that says which systems reach it. Two systems do here, so a caption
    # attributing it to one -- "AEP-full is the only system ..." -- is the
    # defect, and the singular is what identifies it.
    assert "B3" in caption
    assert "AEP-full" in caption
    assert "is the only system " not in caption


def test_the_outcomes_caption_discloses_the_crash_point_asymmetry(
    tmp_path: Path,
) -> None:
    """D11. The caption pooled five points and six under one sentence.

    ``after_intent_before_barrier`` cannot occur in a system that never
    writes an intent, so B0--B2 have five crash-point cells where the
    intent-bearing systems have six. That is a semantic property of the
    baselines rather than a sampling defect, but a caption reading "one of the
    six crash points" and nothing more invites a reviewer to read the columns
    as equally sampled.

    The assertion is two-sided on purpose. It requires the caption to state
    the asymmetry *and* requires the emitted denominator census underneath to
    still show it -- so if the baselines ever gain the sixth point, the test
    fails on the census rather than leaving a caption that has quietly become
    false.
    """
    points_with_intent = (
        "before_intent_write",
        "after_intent_before_barrier",
        "after_barrier_before_dispatch",
        "mid_dispatch",
        "after_response_before_resolution",
        "after_resolution_before_barrier",
    )
    per_cell = []
    for response in RESPONSES:
        for point in points_with_intent:
            for metric in (
                "undetected_duplicate_rate",
                "lost_effect_rate",
                "known_ambiguity_rate",
            ):
                for system in ("AEP_FULL", "B3_INTENT_NO_BARRIER"):
                    per_cell.append(
                        _cell(metric, system, response, 0, 30, point)
                    )
                # The baseline never reaches the barrier point.
                if point != "after_intent_before_barrier":
                    per_cell.append(
                        _cell(metric, "B0_NAIVE_RETRY", response, 0, 30, point)
                    )

    emit_outcomes_table(per_cell, tmp_path)
    text = (tmp_path / "table-outcomes.tex").read_text(encoding="utf-8")
    caption = next(
        line for line in text.splitlines() if line.startswith("\\caption{")
    )
    # The claim.
    assert "five" in caption
    assert "after\\_intent\\_before\\_barrier" in caption
    assert "per-cell-metrics.csv" in caption
    # The data the claim is about, from the generator's own census.
    census = [line for line in text.splitlines() if line.startswith("%   ")]
    assert any(
        "B0_NAIVE_RETRY" in line and "crash_points=5" in line for line in census
    )
    assert any(
        "AEP_FULL" in line and "crash_points=6" in line for line in census
    )


# --------------------------------------------- the process-kill probe file


def test_the_process_kill_macros_come_from_the_tracked_probe_report(
    tmp_path: Path,
) -> None:
    """Three sections quoted this probe; nothing generated it.

    The values are asserted against the committed raw report rather than a
    fixture, because the point of the macros is that the report is the
    source. If the file moves or its format changes, this fails rather than
    silently dropping four numbers out of the manuscript -- which the
    "every generated number is used" gate would not catch, since a macro that
    is never emitted is never orphaned.
    """
    emit_numbers(
        per_cell=[],
        latency=EVERYSEC,
        kill=[],
        comparisons=[],
        flakey=[],
        always=ALWAYS,
        coverage={},
        execution_paths={},
        out=tmp_path,
    )
    text = (tmp_path / "numbers.tex").read_text(encoding="utf-8")
    assert "\\newcommand{\\ProcessKillUnackLost}{0/10}" in text
    assert "\\newcommand{\\ProcessKillTrials}{10}" in text
    assert "\\newcommand{\\ProcessKillWindowMin}{419}" in text
    assert "\\newcommand{\\ProcessKillWindowMax}{992}" in text


def test_the_third_barrier_cost_is_a_share_of_the_step_not_the_barrier_bill(
    tmp_path: Path,
) -> None:
    """The distinction the prose got wrong.

    One more barrier is 50% more *barrier*, and the section costed it that
    way -- "roughly a 50% latency increase". Against the step a reader is
    actually timing it is half that. 983.35 / 4004.9 = 24.6%.
    """
    emit_numbers(
        per_cell=[],
        latency=EVERYSEC,
        kill=[],
        comparisons=[],
        flakey=[],
        always=ALWAYS,
        coverage={},
        execution_paths={},
        out=tmp_path,
    )
    text = (tmp_path / "numbers.tex").read_text(encoding="utf-8")
    assert "\\newcommand{\\ThirdBarrierStepPct}{24.6}" in text


def test_the_barrier_to_protocol_ratio_is_the_two_macros_divided(
    tmp_path: Path,
) -> None:
    """D6. The threats section called this "two orders of magnitude".

    It is 70x, which is nearer one and a half. The macro exists so the phrase
    cannot drift from the measurement again, and the arithmetic is asserted
    here against the same fixture the two operand macros are asserted against:
    (4004.9 - 2038.2) / (2038.2 - 2010.2) = 1966.7 / 28.0 = 70.2, which is 70
    to two significant figures.
    """
    emit_numbers(
        per_cell=[],
        latency=EVERYSEC,
        kill=[],
        comparisons=[],
        flakey=[],
        always=ALWAYS,
        coverage={},
        execution_paths={},
        out=tmp_path,
    )
    text = (tmp_path / "numbers.tex").read_text(encoding="utf-8")
    # The operands, so a change to either is caught here and not only
    # downstream.
    assert "\\newcommand{\\BarrierCost}{1\\,966.7}" in text
    assert "\\newcommand{\\ProtocolMinusBarrier}{28.0}" in text
    assert "\\newcommand{\\BarrierToProtocolRatio}{70}" in text
    # Not a coincidence of this fixture: the quotient, recomputed.
    assert round((4004.9 - 2038.2) / (2038.2 - 2010.2)) == 70


def test_the_ratios_denominator_carries_its_own_interval(tmp_path: Path) -> None:
    """The other half of the decomposition, which had no interval until now.

    ``\\BarrierToProtocolRatio`` divides one median difference by another. The
    numerator has been reported with a cluster bootstrap since the hostile
    read asked for one; the denominator had a point estimate and nothing else,
    which is what let the ratio read as a measurement rather than an estimate.

    Asserted structurally rather than against fixed numbers: the bootstrap is
    seeded, but pinning percentiles of a resample to four significant figures
    would make this a test of the RNG. What must hold is that both macros are
    emitted for ``everysec``, that they bracket the point estimate, and --
    the property the sentence in Section VIII actually leans on -- that the
    interval is not degenerate.
    """
    rows = ["regime,system,run_id,step_latency_ms"]
    # Three runs per arm, ten executions each, B3 above B0 by ~28 ms with
    # enough per-run spread that the resample has something to move.
    for run in range(3):
        for execution in range(10):
            rows.append(
                f"p0,B0_NAIVE_RETRY,b0-run{run},{2010 + run * 4 + execution}"
            )
            rows.append(
                f"p0,B3_INTENT_NO_BARRIER,b3-run{run},"
                f"{2038 + run * 9 + execution}"
            )
    path = tmp_path / "per-execution.csv"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    emit_numbers(
        per_cell=[],
        latency=EVERYSEC,
        kill=[],
        comparisons=[],
        flakey=[],
        always=ALWAYS,
        coverage={},
        execution_paths={"everysec": path},
        out=tmp_path,
    )
    text = (tmp_path / "numbers.tex").read_text(encoding="utf-8")

    def value(name: str) -> float:
        match = re.search(
            r"\\newcommand\{\\" + name + r"\}\{([^}]*)\}", text
        )
        assert match, f"{name} was not emitted"
        return float(match.group(1).replace("\\,", ""))

    low = value("ProtocolMinusBarrierLow")
    high = value("ProtocolMinusBarrierHigh")
    assert low <= high
    assert low < high, "a degenerate interval would make the qualifier a lie"
    # And it is the everysec arm only: an `always` twin would be orphaned,
    # and the "every generated number is used" gate fails on orphans.
    assert "ProtocolMinusBarrierAlwaysLow" not in text


def test_a_ratio_is_rounded_to_significant_figures_without_an_exponent() -> None:
    """``%g`` would render 100 as ``1e+02``, mid-sentence.

    Two significant figures on a magnitude means the decimals move with the
    scale: 70.2 rounds to a whole number, 7.02 keeps one place. Both appear in
    prose, so neither may carry an exponent.
    """
    assert tex_sigfigs(70.2392857142857) == "70"
    assert tex_sigfigs(100.4) == "100"
    assert tex_sigfigs(7.0239) == "7.0"
    assert tex_sigfigs(1966.7) == "2\\,000"
    assert tex_sigfigs(0.0) == "0"


def test_mann_whitney_separates_shifted_samples_and_not_identical_ones() -> None:
    """The kill-latency test's engine, checked against cases with known answers.

    Phase 8.1 uses this to say that the runs which applied an effect waited
    longer for the kill than those which did not. That claim reaches the
    manuscript as a p-value, so the implementation gets the same treatment as
    the Fisher path: cases whose answers are known independently of the code.
    """
    # Complete separation of two samples of ten cannot arise by chance at
    # anything near 0.05; the exact two-tailed p is 2/C(20,10) = 1.08e-5.
    assert mann_whitney_two_tailed(list(range(10)), list(range(100, 110))) < 0.001
    # The same sample against itself is the null in its purest form.
    assert mann_whitney_two_tailed([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0
    # Symmetric in its arguments: the two-tailed answer cannot depend on which
    # group was passed first.
    left = mann_whitney_two_tailed([1.0, 4.0, 9.0, 16.0], [2.0, 3.0, 5.0, 8.0])
    right = mann_whitney_two_tailed([2.0, 3.0, 5.0, 8.0], [1.0, 4.0, 9.0, 16.0])
    assert left == right
    # All ties is a zero-variance case; it must return the null rather than
    # dividing by zero.
    assert mann_whitney_two_tailed([5.0] * 6, [5.0] * 6) == 1.0
    # An empty group has no location to compare, and must not raise.
    assert mann_whitney_two_tailed([], [1.0, 2.0]) == 1.0


def test_the_replication_macros_are_absent_when_the_roots_are(tmp_path) -> None:
    """No replication roots must mean no macros, not zero-valued ones.

    ``emit_numbers`` reads the four Phase 9 results roots by a fixed path. A
    clone that has them emits nine ``Replication`` macros; a tree that does not
    must emit none at all. Emitting them with placeholder values would put a
    number in the manuscript that no measurement stands behind, and the
    "every generated number is used" gate cannot tell the difference.
    """
    emit_numbers(
        per_cell=[],
        latency=EVERYSEC,
        kill=[],
        comparisons=[],
        flakey=[],
        always=ALWAYS,
        coverage={},
        execution_paths={},
        out=tmp_path,
    )
    text = (tmp_path / "numbers.tex").read_text(encoding="utf-8")
    if not (ROOT / "experiments" / "results" / "b2-2026-08-21").is_dir():
        assert "ReplicationSessions" not in text
    else:
        # Present in this clone: then every one of them must carry a value,
        # and the B3 range must be the flat 0 the finding rests on.
        assert "\\newcommand{\\ReplicationSessions}{4}" in text
        assert "\\newcommand{\\ReplicationBthreeRange}{0}" in text
