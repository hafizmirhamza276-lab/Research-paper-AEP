"""`scripts/analyse_b5_agreement.py` must give three different readings.

Rule 13 applied to a verdict script: one that has only ever been run on data it
approves of has been shown to be quiet, not correct. The three fixtures below are
agreement, disagreement, and a run set dominated by voids, and the test asserts
they produce **different** readings -- not merely that each runs.

The void fixture is the one that matters most. A void silently counted as "no
duplicate" would make B5 look better than B4 for an instrument reason, which is
the failure `experiments/baselines/b5_temporal/gate.py` exists to stop one layer
down. If this test ever passes with voids folded into the rate, the gate below it
has been made pointless.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "analyse_b5_agreement", REPO / "scripts" / "analyse_b5_agreement.py"
)
b5 = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
# Registered before exec: @dataclass resolves annotations through
# sys.modules[cls.__module__], which is None for a spec-loaded module that was
# never registered, and the class body then fails with an AttributeError that
# says nothing about the real cause.
sys.modules[_spec.name] = b5
_spec.loader.exec_module(b5)


def _run(**overrides) -> dict:
    run = {
        "system": b5.B5,
        "crash_point": "after_barrier_before_dispatch",
        "response_class": "NO_READBACK",
        "verdict": "COMPLETED",
        "executions": 10,
        "undetected_duplicate_applications": 0,
        "lost_effect_executions": 0,
        "declared_ambiguous": 0,
    }
    run.update(overrides)
    return run


def _session(tmp_path: Path, runs: list[dict]) -> Path:
    session = tmp_path / "session"
    session.mkdir(exist_ok=True)
    (session / "b5-runs.jsonl").write_text(
        "\n".join(json.dumps(r) for r in runs) + "\n", encoding="utf-8"
    )
    return session


def _cell(report: dict, hypothesis: str, crash_point: str) -> dict:
    return next(
        c for c in report["cells"]
        if c["hypothesis"] == hypothesis and c["crash_point"] == crash_point
    )


# ---------------------------------------------------------------- the three


def test_agreement_reads_as_agrees(tmp_path: Path) -> None:
    """B5's interval overlapping the frozen one reads AGREES."""
    frozen = b5.Interval(0.10, 0.00, 0.20)
    reading = b5.classify_cell(
        hypothesis="H1",
        crash_point="after_barrier_before_dispatch",
        response_class="NO_READBACK",
        runs=[_run(undetected_duplicate_applications=1) for _ in range(10)],
        frozen=frozen,
        metric_field="undetected_duplicate_applications",
    )
    assert reading.reading is b5.Reading.AGREES
    assert reading.runs_void == 0
    assert "overlaps frozen" in " ".join(reading.reasons)


def test_disagreement_reads_as_disagrees(tmp_path: Path) -> None:
    """A B5 rate far from the frozen one reads DISAGREES, and says what it costs."""
    frozen = b5.Interval(0.95, 0.90, 1.00)
    reading = b5.classify_cell(
        hypothesis="H1",
        crash_point="after_barrier_before_dispatch",
        response_class="NO_READBACK",
        runs=[_run(undetected_duplicate_applications=0) for _ in range(10)],
        frozen=frozen,
        metric_field="undetected_duplicate_applications",
    )
    assert reading.reading is b5.Reading.DISAGREES
    assert "re-scoped" in " ".join(reading.reasons)


def test_voids_are_excluded_and_counted_not_folded_into_the_rate(
    tmp_path: Path,
) -> None:
    """The load-bearing one.

    Nine voided runs and one real run must NOT read as a clean zero-duplicate
    cell agreeing with a zero-duplicate frozen cell. The voids are excluded from
    the rate and reported with counts.
    """
    runs = [
        _run(verdict="VOID_INJECTOR_NEVER_REACHED") for _ in range(4)
    ] + [
        _run(verdict="VOID_SUPERVISOR_NEVER_RESPAWNED") for _ in range(3)
    ] + [
        _run(verdict="VOID_WORKER_NEVER_READY") for _ in range(2)
    ] + [
        _run(undetected_duplicate_applications=1)
    ]
    reading = b5.classify_cell(
        hypothesis="H1",
        crash_point="after_barrier_before_dispatch",
        response_class="NO_READBACK",
        runs=runs,
        frozen=b5.Interval(0.10, 0.00, 0.20),
        metric_field="undetected_duplicate_applications",
    )
    assert reading.runs_void == 9
    assert reading.voids_by_verdict == {
        "VOID_INJECTOR_NEVER_REACHED": 4,
        "VOID_SUPERVISOR_NEVER_RESPAWNED": 3,
        "VOID_WORKER_NEVER_READY": 2,
    }
    # The rate is over the one surviving run, not over ten.
    assert reading.b5 is not None
    assert reading.b5.point == 1 / 10
    assert "voided as instrument failures" in " ".join(reading.reasons)


def test_all_voids_reads_as_no_data_not_as_agreement(tmp_path: Path) -> None:
    """A cell that is entirely voids must not agree with anything."""
    reading = b5.classify_cell(
        hypothesis="H1",
        crash_point="after_barrier_before_dispatch",
        response_class="NO_READBACK",
        runs=[_run(verdict="VOID_INJECTOR_DID_NOT_FIRE") for _ in range(6)],
        frozen=b5.Interval(0.0, 0.0, 0.0),
        metric_field="undetected_duplicate_applications",
    )
    assert reading.reading is b5.Reading.NO_DATA_AFTER_VOIDS
    assert reading.b5 is None


def test_three_fixtures_produce_three_different_readings(tmp_path: Path) -> None:
    """Non-vacuity, stated as such: the readings must actually differ."""
    frozen_low = b5.Interval(0.10, 0.00, 0.20)
    agree = b5.classify_cell(
        hypothesis="H1", crash_point="after_barrier_before_dispatch",
        response_class="NO_READBACK",
        runs=[_run(undetected_duplicate_applications=1) for _ in range(10)],
        frozen=frozen_low, metric_field="undetected_duplicate_applications",
    ).reading
    disagree = b5.classify_cell(
        hypothesis="H1", crash_point="after_barrier_before_dispatch",
        response_class="NO_READBACK",
        runs=[_run(undetected_duplicate_applications=0) for _ in range(10)],
        frozen=b5.Interval(0.95, 0.90, 1.00),
        metric_field="undetected_duplicate_applications",
    ).reading
    voided = b5.classify_cell(
        hypothesis="H1", crash_point="after_barrier_before_dispatch",
        response_class="NO_READBACK",
        runs=[_run(verdict="VOID_INJECTOR_NEVER_REACHED") for _ in range(8)],
        frozen=frozen_low, metric_field="undetected_duplicate_applications",
    ).reading
    assert len({agree, disagree, voided}) == 3


# ------------------------------------------------- the flagged conditions


def test_absent_point_is_absent_not_missing(tmp_path: Path) -> None:
    """`after_intent_before_barrier` reads ABSENT even with runs present."""
    reading = b5.classify_cell(
        hypothesis="H1",
        crash_point=b5.ABSENT_IN_B5,
        response_class="NO_READBACK",
        runs=[_run(crash_point=b5.ABSENT_IN_B5) for _ in range(10)],
        frozen=b5.Interval(0.10, 0.00, 0.20),
        metric_field="undetected_duplicate_applications",
    )
    assert reading.reading is b5.Reading.NOT_TESTABLE_ABSENT_IN_B5
    assert reading.b5 is None, "no rate may be computed for an absent point"
    assert "hole in B5 where B4 has numbers" in " ".join(reading.reasons)


def test_pending_above_the_bound_is_uninformative_not_agreement(
    tmp_path: Path,
) -> None:
    """A cell that would 'agree' but is mostly pending must not read AGREES."""
    runs = [_run(verdict=b5.PENDING) for _ in range(5)] + [_run() for _ in range(5)]
    reading = b5.classify_cell(
        hypothesis="H1", crash_point="after_barrier_before_dispatch",
        response_class="NO_READBACK", runs=runs,
        frozen=b5.Interval(0.0, 0.0, 0.10),
        metric_field="undetected_duplicate_applications",
    )
    assert reading.reading is b5.Reading.UNINFORMATIVE_PENDING
    assert "re-registered" in " ".join(reading.reasons)


def test_pending_within_the_bound_still_agrees_but_says_so(tmp_path: Path) -> None:
    runs = [_run(verdict=b5.PENDING)] + [_run() for _ in range(9)]
    reading = b5.classify_cell(
        hypothesis="H1", crash_point="after_barrier_before_dispatch",
        response_class="NO_READBACK", runs=runs,
        frozen=b5.Interval(0.0, 0.0, 0.10),
        metric_field="undetected_duplicate_applications",
    )
    assert reading.reading is b5.Reading.AGREES
    assert "within the 20% bound" in " ".join(reading.reasons)


def test_h3_refuted_by_a_single_declared_ambiguity() -> None:
    verdict, reasons = b5.classify_h3(
        [_run(), _run(declared_ambiguous=1)]
    )
    assert verdict == "REFUTED"
    assert "most important finding" in " ".join(reasons)


def test_h3_held_ignores_voided_runs() -> None:
    verdict, _ = b5.classify_h3(
        [_run(), _run(verdict="VOID_INJECTOR_NEVER_REACHED", declared_ambiguous=3)]
    )
    assert verdict == "HELD", "a voided run must not refute H3"


def test_frozen_rates_are_read_from_the_per_cell_file() -> None:
    """The comparator is the frozen file, and it really has B4 cells in it."""
    frozen = b5.read_frozen(REPO)
    key = ("undetected_duplicate_rate", b5.B4, "after_intent_before_barrier",
           "NO_READBACK")
    assert key in frozen, "frozen B4 cell missing; comparator would be empty"
    assert b5.BANNED_SOURCE not in str(b5.FROZEN_PER_CELL)


def test_end_to_end_report_marks_the_absent_cell(tmp_path: Path) -> None:
    session = _session(tmp_path, [_run() for _ in range(4)])
    report = b5.build_report(session, REPO)
    absent = _cell(report, "H1", b5.ABSENT_IN_B5)
    assert absent["reading"] == b5.Reading.NOT_TESTABLE_ABSENT_IN_B5.value
    text = b5.render(report)
    assert "ABSENT IN B5, not missing from the" in text
    assert "voided as instrument failures" in text
