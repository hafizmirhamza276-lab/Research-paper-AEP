"""The planner chooses the action. It does not choose what is measured.

`fingerprint.py`'s identity function includes `amount_minor`. An agent free to
invent amounts is therefore choosing a term of the oracle's own identity
function — the system under test deciding part of its measurement. Two
executions the harness meant to be distinct could collapse into one
fingerprint, or a genuine duplicate pair could split into two apparently
separate effects. Either direction breaks the duplicate metric.

**Found live, not reasoned about.** On the first corrected 10-call stage the
planner was offered 896603 on turn 2 and answered 728995 — which is
`896603 - 167608`, the amount it had captured on turn 1. The prompt had invited
the arithmetic (amendment 3), and the executed mutation would have carried an
amount no plan contained.

Treated exactly as a content filter is: its own void class, the run stops being
a result, recorded in the event log, and never counted as a normal mutation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.harness.agent_loop import AgentRunVoided, agent_worker_items
from experiments.harness.planner import (
    CallWrapper,
    CumulativeCounter,
    PlannerOutcome,
    Stop,
    StubPlanner,
    ToolCall,
    VoidReason,
)
from experiments.harness.workload import plan_workload, worker_items


class _Config:
    def __init__(self, **kw):
        self.run_id = kw.get("run_id", "amount-test")
        self.seed = kw.get("seed", 20260918)
        self.workers = kw.get("workers", 1)
        self.executions_per_worker = kw.get("executions_per_worker", 3)
        self.crash_probability = kw.get("crash_probability", 0.0)
        self.results_root = kw.get("results_root", "")


def _wrapper(tmp_path):
    return CallWrapper(
        run_id="amount-test", run_dir=tmp_path / "run",
        cumulative=CumulativeCounter(tmp_path / "cumulative.json"),
    )


def _scaffold(config):
    return list(worker_items(plan_workload(config), 0))


def _ok(*actions):
    return [(PlannerOutcome.OK, a) for a in actions]


def test_an_invented_amount_voids_the_run(tmp_path):
    """The injected mismatch. This is the test the guard exists for."""
    config = _Config()
    base = _scaffold(config)
    planner = StubPlanner(script=_ok(
        ToolCall(tool="send_notification", action="capture",
                 amount_minor=base[0].amount_minor + 1),   # off by one
    ))
    with pytest.raises(AgentRunVoided) as raised:
        agent_worker_items(config, 0, 0, planner, _wrapper(tmp_path))
    assert raised.value.reason is VoidReason.PLANNER_AMOUNT_MISMATCH


def test_the_arithmetic_the_live_stage_actually_did(tmp_path):
    """The real shape: offered X, answered X minus an earlier capture."""
    config = _Config()
    base = _scaffold(config)
    planner = StubPlanner(script=_ok(
        ToolCall(tool="send_notification", action="capture",
                 amount_minor=base[0].amount_minor),          # turn 1 ok
        ToolCall(tool="send_notification", action="capture",
                 amount_minor=base[1].amount_minor - base[0].amount_minor),
    ))
    with pytest.raises(AgentRunVoided) as raised:
        agent_worker_items(config, 0, 0, planner, _wrapper(tmp_path))
    assert raised.value.reason is VoidReason.PLANNER_AMOUNT_MISMATCH
    assert str(base[1].amount_minor) in raised.value.detail


def test_the_matching_amount_is_accepted(tmp_path):
    """R2's known-positive. A guard that voided everything would also pass."""
    config = _Config()
    base = _scaffold(config)
    planner = StubPlanner(script=_ok(*[
        ToolCall(tool="send_notification", action="capture",
                 amount_minor=item.amount_minor)
        for item in base
    ]))
    decided = agent_worker_items(config, 0, 0, planner, _wrapper(tmp_path))
    assert len(decided) == len(base)
    assert [i.amount_minor for i in decided] == [i.amount_minor for i in base]


def test_the_action_is_still_the_planners_to_choose(tmp_path):
    """Only the amount is pinned. Refunding what was meant as a capture is a
    decision the experiment is trying to observe, not a fault."""
    config = _Config(executions_per_worker=2)
    base = _scaffold(config)
    planner = StubPlanner(script=_ok(*[
        ToolCall(tool="send_notification", action="refund",
                 amount_minor=item.amount_minor)
        for item in base
    ]))
    decided = agent_worker_items(config, 0, 0, planner, _wrapper(tmp_path))
    assert {i.action for i in decided} == {"refund"}


def test_a_stop_is_not_an_amount_mismatch(tmp_path):
    """Stop carries no amount and must not trip the guard."""
    config = _Config()
    base = _scaffold(config)
    planner = StubPlanner(script=_ok(
        ToolCall(tool="send_notification", action="capture",
                 amount_minor=base[0].amount_minor),
        Stop("nothing further warranted"),
    ))
    decided = agent_worker_items(config, 0, 0, planner, _wrapper(tmp_path))
    assert len(decided) == 1


def test_the_void_is_recorded_the_way_a_content_filter_is(tmp_path):
    """Same treatment as PLANNER_FILTERED: file, budget, journal."""
    config = _Config()
    base = _scaffold(config)
    wrapper = _wrapper(tmp_path)
    planner = StubPlanner(script=_ok(
        ToolCall(tool="send_notification", action="capture",
                 amount_minor=base[0].amount_minor + 500),
    ))
    with pytest.raises(AgentRunVoided):
        agent_worker_items(config, 0, 0, planner, wrapper)

    marker = tmp_path / "run" / "VOID_REASON.md"
    assert marker.is_file()
    assert "VOID_PLANNER_AMOUNT_MISMATCH" in marker.read_text(encoding="utf-8")

    budget = json.loads(
        (tmp_path / "run" / "planner-budget.json").read_text(encoding="utf-8")
    )
    assert budget["voided"] == VoidReason.PLANNER_AMOUNT_MISMATCH.value

    journal = [
        json.loads(line)
        for line in (tmp_path / "cumulative.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert any(entry.get("voided") for entry in journal)


def test_the_mismatch_reaches_the_event_log(tmp_path):
    """Recorded where the run's other evidence is, not only beside it."""
    config = _Config()
    base = _scaffold(config)
    emitted = []
    planner = StubPlanner(script=_ok(
        ToolCall(tool="send_notification", action="capture",
                 amount_minor=base[0].amount_minor - 7),
    ))
    with pytest.raises(AgentRunVoided):
        agent_worker_items(
            config, 0, 0, planner, _wrapper(tmp_path),
            emit=lambda event, **fields: emitted.append((event, fields)),
        )
    assert len(emitted) == 1
    event, fields = emitted[0]
    assert event == "planner_amount_mismatch"
    assert fields["assigned_amount_minor"] == base[0].amount_minor
    assert fields["planner_amount_minor"] == base[0].amount_minor - 7
    assert fields["void_reason"] == "VOID_PLANNER_AMOUNT_MISMATCH"
    assert fields["execution_id"] == base[0].execution_id


def test_no_item_is_returned_when_the_amount_drifts(tmp_path):
    """The run stops being a result; it does not continue with the bad item."""
    config = _Config()
    base = _scaffold(config)
    planner = StubPlanner(script=_ok(
        ToolCall(tool="send_notification", action="capture",
                 amount_minor=base[0].amount_minor),
        ToolCall(tool="send_notification", action="capture", amount_minor=1),
        ToolCall(tool="send_notification", action="capture",
                 amount_minor=base[2].amount_minor),
    ))
    with pytest.raises(AgentRunVoided):
        agent_worker_items(config, 0, 0, planner, _wrapper(tmp_path))
    # Nothing partial is written back; the caller gets the exception, not a
    # workload it might execute anyway.


def test_the_void_reason_is_its_own_class():
    """Not folded into the filter class or a cap."""
    assert VoidReason.PLANNER_AMOUNT_MISMATCH.value == (
        "VOID_PLANNER_AMOUNT_MISMATCH"
    )
    assert VoidReason.PLANNER_AMOUNT_MISMATCH is not VoidReason.PLANNER_FILTERED
