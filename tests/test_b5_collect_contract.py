"""The runner must satisfy `analyse_b5_agreement.py`, not the other way round.

That script is committed and predates any B5 data. If the two disagree on
format, the runner changes. Editing the verdict script now is the one edit the
pre-registration ordering exists to prevent, so these tests are written to fail
against the **runner**.

Also here: the attribution gate's two directions, as a pure function over a
reconciler report. A missing oracle must void naming attribution, because a
missing oracle otherwise looks exactly like a clean zero-duplicate result.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.baselines.b5_temporal import collect  # noqa: E402
from experiments.baselines.b5_temporal.gate import (  # noqa: E402
    AttributionStatus,
    RunVerdict,
    classify,
)
from experiments.baselines.contract import OutcomeClass, SystemId  # noqa: E402
from experiments.baselines.crash_points import (  # noqa: E402
    CrashPointNotApplicable,
    applicable_roadmap_points,
    resolve_for_system,
)

_spec = importlib.util.spec_from_file_location(
    "analyse_b5_agreement", REPO / "scripts" / "analyse_b5_agreement.py"
)
verdict_script = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = verdict_script
_spec.loader.exec_module(verdict_script)


class _Report:
    """Stands in for a ReconciliationReport's read fields."""

    def __init__(self, unattributed=0, duplicates=0, lost=0, ambiguous=0):
        self.oracle_unattributed_rows = unattributed
        self.undetected_duplicate_applications = duplicates
        self.lost_effect_executions = lost
        self.declared_ambiguous_executions = ambiguous


# ------------------------------------------------ the runner satisfies reader


def test_runner_record_has_every_field_the_verdict_script_reads(
    tmp_path: Path,
) -> None:
    """Every key `analyse_b5_agreement` touches must exist in a runner record."""
    record = {
        "run_id": "r0",
        "system": SystemId.B5_TEMPORAL.value,
        "crash_point": "after_barrier_before_dispatch",
        "response_class": "NO_READBACK",
        "verdict": "COMPLETED",
        "executions": 10,
        "undetected_duplicate_applications": 0,
        "lost_effect_executions": 0,
        "declared_ambiguous": 0,
    }
    session = tmp_path / "session"
    collect.append_session_record(session, record)

    runs = verdict_script.read_b5_runs(session)
    assert len(runs) == 1
    reading = verdict_script.classify_cell(
        hypothesis="H1",
        crash_point=runs[0]["crash_point"],
        response_class=runs[0]["response_class"],
        runs=runs,
        frozen=verdict_script.Interval(0.0, 0.0, 0.1),
        metric_field="undetected_duplicate_applications",
    )
    assert reading.reading is not verdict_script.Reading.NO_DATA_AFTER_VOIDS
    assert reading.b5 is not None, "the reader could not compute a rate"


def test_runner_system_names_match_the_verdict_script_constants() -> None:
    """The two must agree on the arm names or every cell silently misses."""
    assert verdict_script.B5 == SystemId.B5_TEMPORAL.value
    assert verdict_script.B5B == SystemId.B5B_TEMPORAL_AT_MOST_ONCE.value


def test_absent_point_constant_matches_the_registered_mapping() -> None:
    """The script's ABSENT_IN_B5 must be the point the harness refuses."""
    with __import__("pytest").raises(CrashPointNotApplicable):
        resolve_for_system(SystemId.B5_TEMPORAL, verdict_script.ABSENT_IN_B5)
    assert verdict_script.ABSENT_IN_B5 not in applicable_roadmap_points(
        SystemId.B5_TEMPORAL
    )
    assert len(applicable_roadmap_points(SystemId.B5_TEMPORAL)) == 5


def test_a_voided_runner_record_is_excluded_by_the_reader(tmp_path: Path) -> None:
    """A void the runner writes must be a void the reader drops."""
    session = tmp_path / "session"
    for _ in range(3):
        collect.append_session_record(session, {
            "run_id": "v", "system": SystemId.B5_TEMPORAL.value,
            "crash_point": "after_barrier_before_dispatch",
            "response_class": "NO_READBACK",
            "verdict": RunVerdict.VOID_ATTRIBUTION_UNAVAILABLE.value,
            "executions": 10,
            "undetected_duplicate_applications": None,
            "lost_effect_executions": None, "declared_ambiguous": None,
        })
    runs = verdict_script.read_b5_runs(session)
    reading = verdict_script.classify_cell(
        hypothesis="H1", crash_point="after_barrier_before_dispatch",
        response_class="NO_READBACK", runs=runs,
        frozen=verdict_script.Interval(0.0, 0.0, 0.1),
        metric_field="undetected_duplicate_applications",
    )
    assert reading.reading is verdict_script.Reading.NO_DATA_AFTER_VOIDS
    assert reading.runs_void == 3


# ------------------------------------------------- the attribution gate, both


def test_attribution_available_does_not_void() -> None:
    status = collect.attribution_status(_Report(unattributed=0))
    assert status.usable
    result = classify(
        armed_point="ACTIVITY_ENTERED_BEFORE_CALL", settled=True,
        worker_ready=True,
        events=["b5_point_reached", "b5_crash_firing"],
        worker_deaths=1, respawns=1, attribution=status,
    )
    assert not result.is_void
    assert result.verdict is RunVerdict.COMPLETED


def test_attribution_unavailable_voids_naming_attribution() -> None:
    """The direction that matters: a missing oracle must not read as clean."""
    status = collect.attribution_status(_Report(unattributed=4))
    assert not status.usable
    result = classify(
        armed_point="ACTIVITY_ENTERED_BEFORE_CALL", settled=True,
        worker_ready=True,
        events=["b5_point_reached", "b5_crash_firing"],
        worker_deaths=1, respawns=1, attribution=status,
    )
    assert result.verdict is RunVerdict.VOID_ATTRIBUTION_UNAVAILABLE
    assert result.is_void
    assert "attribute" in result.reason
    assert "zero here would be indistinguishable" in result.reason


def test_attribution_is_checked_before_the_runs_own_outcome() -> None:
    """Even a settled, fully successful run voids if it cannot be attributed.

    Order matters: attribution first, or a clean-looking run would be reported
    on a join that did not hold.
    """
    result = classify(
        armed_point=None, settled=True, worker_ready=True, events=[],
        attribution=AttributionStatus(False, "no ledger"),
    )
    assert result.verdict is RunVerdict.VOID_ATTRIBUTION_UNAVAILABLE


def test_outcome_mapping_never_produces_declared_ambiguous() -> None:
    """H3 is structural: B5 has no record that could carry it."""
    assert collect.outcome_of(True, {"status": 200}).outcome_class is (
        OutcomeClass.CONFIRMED_APPLIED
    )
    assert collect.outcome_of(True, "FAILED:ApplicationError").outcome_class is (
        OutcomeClass.UNVERIFIED_FAILURE
    ), "a failed activity is UNVERIFIED_FAILURE, not CONFIRMED_NOT_APPLIED"
    assert collect.outcome_of(False, None) is None


def test_start_to_close_is_the_committed_value() -> None:
    """The runner may not quietly use a value other than the committed one."""
    assert collect.START_TO_CLOSE_MS == 4000


# ------------------------------------------- the crash point comes from the cell
#
# The defect these pin: ``session.py`` armed one constant point for every cell
# while labelling the cells from the roadmap. Harmless while a single crash
# point was collected, and silently wrong on the secondary sweep, where four
# labelled points would all have taken the same fault. Nothing downstream reads
# the injected point, so nothing downstream could have caught it.


def test_the_five_applicable_points_arm_five_distinct_positions() -> None:
    """The property the constant destroyed: distinct cells, distinct faults.

    If two roadmap points armed the same B5 position, a sweep over them would
    report two cells from one experiment.
    """
    from experiments.baselines.b5_temporal.session import injected_point_for

    points = {
        name: injected_point_for(SystemId.B5_TEMPORAL, name)
        for name in applicable_roadmap_points(SystemId.B5_TEMPORAL)
    }
    assert len(points) == 5
    assert len(set(points.values())) == 5, (
        f"two cells arm the same position, so one experiment would be "
        f"reported as two: {points}"
    )
    # The specific collapse the shared resolver would have caused: it maps both
    # of these onto BEFORE_REQUEST_TRANSMISSION.
    assert points["after_barrier_before_dispatch"] != points["mid_dispatch"]


def test_the_shared_resolver_alone_would_collapse_two_cells() -> None:
    """Non-vacuity for the test above: the collapse is real, not hypothetical.

    ``resolve_for_system`` is the cross-system contract and is the natural thing
    to reach for, but it is lossy for B5. This records why the injected point is
    not taken from it.
    """
    shared = {
        name: resolve_for_system(SystemId.B5_TEMPORAL, name)
        for name in applicable_roadmap_points(SystemId.B5_TEMPORAL)
    }
    assert len(set(shared.values())) == 4, (
        "the shared resolver is expected to be lossy here; if it stopped being "
        "lossy this test should be deleted, not the guard it justifies"
    )
    assert (
        shared["after_barrier_before_dispatch"] == shared["mid_dispatch"]
    ), "the two points this collapses are the reason B5 resolves separately"


def test_the_session_plan_records_the_point_each_cell_will_arm() -> None:
    """Every planned secondary run carries the point its own label resolves to."""
    from experiments.baselines.b5_temporal import session

    seen: dict[str, set[str]] = {}
    for arm, crash_point, _endpoint in session.cells("secondary"):
        point = session.injected_point_for(arm, crash_point)
        assert point == session.resolve_b5_point(crash_point)
        seen.setdefault(crash_point, set()).add(point)

    assert set(seen) == set(session.SECONDARY_CRASH_POINTS)
    armed = {next(iter(v)) for v in seen.values()}
    assert len(armed) == len(session.SECONDARY_CRASH_POINTS), (
        f"the secondary sweep must arm one distinct position per crash point, "
        f"not {armed}"
    )
    # And none of them is the primary's, which is what a constant would give.
    assert session.injected_point_for(
        SystemId.B5_TEMPORAL, session.PRIMARY_CRASH_POINT
    ) not in armed


def test_the_recorded_crash_point_is_the_vocabulary_frozen_cells_use() -> None:
    """The label written to the run record must key the frozen B4 comparison.

    ``analyse_b5_agreement`` looks a cell up in the frozen per-cell file by
    ``crash_point``. That file is keyed on roadmap names, so a record carrying
    B5's own vocabulary matches nothing and every cell reads NO_FROZEN_CELL.
    """
    import csv

    from experiments.baselines.b5_temporal.session import injected_point_for

    frozen_path = REPO / verdict_script.FROZEN_PER_CELL
    with frozen_path.open(newline="", encoding="utf-8") as handle:
        frozen_keys = {row["crash_point"] for row in csv.DictReader(handle)}

    for name in applicable_roadmap_points(SystemId.B5_TEMPORAL):
        assert name in frozen_keys, (
            f"{name!r} is a cell B5 collects but the frozen file is not keyed "
            f"on it, so the comparison could never be made"
        )
        # The injected point is deliberately NOT a roadmap name. This is what
        # makes writing the wrong one detectable: the two vocabularies are
        # disjoint, so a record carrying B5's own name matches no frozen cell.
        point = injected_point_for(SystemId.B5_TEMPORAL, name)
        assert point != name
        assert point not in frozen_keys, (
            f"{point!r} is B5's vocabulary and must not key a frozen cell; if "
            f"it did, a mislabelled record would silently find a match"
        )


# ------------------------------------------------ the mismatch gate, both ways


def test_label_and_fault_agreeing_does_not_void() -> None:
    """The branch that must stay silent, or the gate is not a gate."""
    result = classify(
        armed_point="ACTIVITY_ENTERED_BEFORE_CALL",
        expected_point="ACTIVITY_ENTERED_BEFORE_CALL",
        settled=True, worker_ready=True,
        events=["b5_point_reached", "b5_crash_firing"],
        reached_points=["ACTIVITY_ENTERED_BEFORE_CALL"],
        worker_deaths=1, respawns=1,
        attribution=AttributionStatus(True, "attributed"),
    )
    assert not result.is_void
    assert result.verdict is RunVerdict.COMPLETED


def test_label_and_fault_disagreeing_voids() -> None:
    """A run labelled for one point and cut at another is not a measurement."""
    result = classify(
        armed_point="ACTIVITY_ENTERED_BEFORE_CALL",   # what the constant armed
        expected_point="DURING_PROVIDER_CALL",        # what the cell is labelled
        settled=True, worker_ready=True,
        events=["b5_point_reached", "b5_crash_firing"],
        reached_points=["ACTIVITY_ENTERED_BEFORE_CALL"],
        worker_deaths=1, respawns=1,
        attribution=AttributionStatus(True, "attributed"),
    )
    assert result.verdict is RunVerdict.VOID_CRASH_POINT_MISMATCH
    assert result.is_void
    assert "DURING_PROVIDER_CALL" in result.reason
    assert "ACTIVITY_ENTERED_BEFORE_CALL" in result.reason


def test_the_mismatch_voids_even_when_everything_else_is_perfect() -> None:
    """Ordering: identity is decided before attribution and before outcome.

    A mismatched run can be perfectly attributed and settle cleanly. If
    attribution were checked first the run would be filed under the wrong cell
    with a full set of plausible numbers.
    """
    result = classify(
        armed_point="ACTIVITY_ENTERED_BEFORE_CALL",
        expected_point="AFTER_RESPONSE_BEFORE_RETURN",
        settled=True, worker_ready=True,
        events=["b5_point_reached", "b5_crash_firing"],
        reached_points=["ACTIVITY_ENTERED_BEFORE_CALL"],
        worker_deaths=1, respawns=1,
        attribution=collect.attribution_status(_Report(unattributed=0)),
    )
    assert result.verdict is RunVerdict.VOID_CRASH_POINT_MISMATCH


def test_a_trace_naming_a_point_the_run_did_not_arm_voids() -> None:
    """Delivery landing elsewhere voids, and does not read as a clean reach.

    Before the gate read the point rather than the event name, this trace
    contained ``b5_point_reached`` and passed.
    """
    result = classify(
        armed_point="DURING_COMPLETE_RPC",
        expected_point="DURING_COMPLETE_RPC",
        settled=True, worker_ready=True,
        events=["b5_point_reached", "b5_crash_firing"],
        reached_points=["BEFORE_SCHEDULE_ACTIVITY"],   # a stale arming
        worker_deaths=1, respawns=1,
        attribution=AttributionStatus(True, "attributed"),
    )
    assert result.verdict is RunVerdict.VOID_CRASH_POINT_MISMATCH
    assert "BEFORE_SCHEDULE_ACTIVITY" in result.reason


def test_the_old_event_name_only_reading_would_have_passed_that_trace() -> None:
    """Non-vacuity: the previous gate could not tell those two apart."""
    old_reading_reached = "b5_point_reached" in [
        "b5_point_reached", "b5_crash_firing"
    ]
    assert old_reading_reached, (
        "the trace that must now void contains the event name the old gate "
        "checked, which is why reading the name was not enough"
    )


def test_a_void_for_mismatch_is_excluded_by_the_reader(tmp_path: Path) -> None:
    """The new verdict must be dropped from rates, not averaged in as a zero."""
    session = tmp_path / "session"
    collect.append_session_record(session, {
        "run_id": "m", "system": SystemId.B5_TEMPORAL.value,
        "crash_point": "mid_dispatch", "response_class": "NO_READBACK",
        "verdict": RunVerdict.VOID_CRASH_POINT_MISMATCH.value,
        "executions": 10, "undetected_duplicate_applications": None,
        "lost_effect_executions": None, "declared_ambiguous": None,
    })
    runs = verdict_script.read_b5_runs(session)
    reading = verdict_script.classify_cell(
        hypothesis="H1", crash_point="mid_dispatch",
        response_class="NO_READBACK", runs=runs,
        frozen=verdict_script.Interval(0.0, 0.0, 0.1),
        metric_field="undetected_duplicate_applications",
    )
    assert reading.reading is verdict_script.Reading.NO_DATA_AFTER_VOIDS
    assert reading.runs_void == 1
    assert reading.voids_by_verdict == {
        RunVerdict.VOID_CRASH_POINT_MISMATCH.value: 1
    }


def test_b5_descriptor_facts_match_b4s() -> None:
    """B5 and B4 must be the same row of the table run two ways.

    A descriptor that differed would make any measured difference a difference
    in what was measured.
    """
    from experiments.baselines.contract import descriptor_for

    b4 = descriptor_for(SystemId.B4_DURABLE_WORKFLOW)
    b5 = descriptor_for(SystemId.B5_TEMPORAL)
    for field in (
        "uses_lease", "uses_fenced_state_writes", "writes_pre_dispatch_record",
        "uses_durability_barrier", "has_recovery_service",
        "retries_on_ambiguity", "can_declare_ambiguity",
        "sends_client_reference", "redispatches_on_replay",
    ):
        assert getattr(b4, field) == getattr(b5, field), field
