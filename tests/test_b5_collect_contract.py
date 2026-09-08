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
