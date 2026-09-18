"""A run that started nothing must fail, however consistent it looks.

**This is the defect the first live collection exposed, and it is worth more
than the collection was.** Two runs completed with `rc=0`, `agrees=true`,
`settled=true` and `execution_started=0`. The planner stopped on its first turn,
so the workload was empty, so nothing was dispatched, crashed, applied or
reconciled — and every consistency check in the harness passed, because there
were no events to disagree with each other.

`agrees=true` on an empty run does not say the oracle and the event log agree
about what happened. It says neither has anything to say. The two claims are
indistinguishable in `summary.json`, which is exactly why emptiness has to be
checked separately from consistency rather than inferred from it.

At 300 runs this would have cost three hundred times what it did here, and the
collection would have reported a clean sweep containing no evidence.

`docs/25` R2: `test_a_run_that_did_work_is_accepted` is the known-positive. A
gate that rejected everything would satisfy every other test in this file.
"""

from __future__ import annotations

import pytest

from experiments.harness.runner import RunAborted, assert_run_is_not_empty


def _started(execution_id: str) -> dict:
    return {"event": "execution_started", "execution_id": execution_id}


def test_a_run_that_planned_work_and_started_none_is_refused():
    """The shape the live collection produced."""
    records = [
        {"event": "run_started"},
        {"event": "worker_spawned"},
        {"event": "worker_started"},
        {"event": "all_workers_finished"},
        {"event": "settled"},
        {"event": "run_finished"},
    ]
    with pytest.raises(RunAborted, match="no execution started"):
        assert_run_is_not_empty(records, planned=3)


def test_the_refusal_says_where_to_look():
    """A gate that fires without saying why costs another collection to read."""
    with pytest.raises(RunAborted) as raised:
        assert_run_is_not_empty([{"event": "run_started"}], planned=3)
    message = str(raised.value)
    assert "planned 3 and started 0" in message
    assert "not a result" in message
    assert "transcript" in message, "the planner's transcript is the evidence"


def test_a_run_that_did_work_is_accepted():
    """R2's known-positive. Without it every test here would pass vacuously."""
    records = [{"event": "run_started"}, _started("e1"), _started("e2"),
               _started("e3"), {"event": "run_finished"}]
    assert_run_is_not_empty(records, planned=3)


def test_one_execution_out_of_three_is_enough_to_pass():
    """The gate is about emptiness, not completeness.

    A crashed run legitimately starts fewer executions than it planned, and
    `tests/test_scripted_plan_is_frozen.py` already relies on that: recorded
    ids are a subset of planned ones. Rejecting partial runs would throw away
    the crashed regime, which is the whole experiment.
    """
    assert_run_is_not_empty(
        [{"event": "run_started"}, _started("e1")], planned=3
    )


def test_a_run_that_planned_nothing_is_not_judged():
    """Nothing planned, nothing started, nothing to complain about."""
    assert_run_is_not_empty([], planned=0)


def test_consistency_is_not_evidence_of_content():
    """The point, stated as a test.

    These records carry `agrees`-style success markers and no execution. The
    gate must fire anyway -- that it looks healthy is the problem.
    """
    records = [
        {"event": "run_started"},
        {"event": "settled"},
        {"event": "recovery_finished"},
        {"event": "run_finished"},
    ]
    with pytest.raises(RunAborted):
        assert_run_is_not_empty(records, planned=6)


def test_events_other_than_execution_started_do_not_count():
    """Only a started execution counts as work.

    A run can spawn workers, arm crashes and finish cleanly without ever
    dispatching anything, which is precisely what happened.
    """
    records = [
        {"event": "worker_spawned"}, {"event": "worker_spawned"},
        {"event": "crash_armed"}, {"event": "composition_validated"},
        {"event": "clock_reference"}, {"event": "worker_exited"},
    ]
    with pytest.raises(RunAborted):
        assert_run_is_not_empty(records, planned=2)


def test_the_gate_runs_before_the_summary_is_written():
    """Structural: an empty run must not leave a summary.json behind.

    `--resume` skips any run with a parsing `summary.json`, so writing one for
    an empty run would make the emptiness sticky -- the retry would skip it.
    Asserted against the source order rather than by running a collection.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "experiments" / "harness"
              / "runner.py").read_text(encoding="utf-8")
    body = source[source.index("async def execute_run"):]
    gate = body.index("assert_run_is_not_empty(records")
    summary = body.index("write_summary(")
    assert gate < summary, (
        "the emptiness gate must fire before summary.json is written, or a "
        "resume will skip the run it was supposed to retry"
    )
