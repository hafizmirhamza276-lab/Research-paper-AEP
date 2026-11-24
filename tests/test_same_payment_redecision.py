"""Amendment 6: the re-decision is about the same payment, and it is the agent's.

Stage 10 established that neither of those was true. The agent re-decided about
a *different* payment, and after a crash the *supervisor* decided whether to
send again -- `REEXECUTE_CRASHED` on B0, never on AEP. So the comparison was
between two supervisors, and any duplicate it produced would have been evidence
about `ResumePolicy` rather than about an LLM.
"""
from __future__ import annotations

import json
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from experiments.harness.agent_loop import (
    ACKNOWLEDGED,
    MAX_DECISIONS_PER_EXECUTION,
    NON_ACKNOWLEDGED,
    OUTCOME_VALUES,
    SERVER_ERROR,
    TIMED_OUT,
    UNKNOWN_PROCESS_DIED,
    InteractiveDriver,
    ObservationLog,
)
from experiments.harness.planner import (
    CallWrapper,
    CumulativeCounter,
    Observation,
    Stop,
    ToolCall,
    Usage,
)
from experiments.harness.workload import plan_workload, worker_items


class Resolved:
    """What worker.py hands to observe(): a caller-visible transport result."""

    def __init__(self, transport_result="ok", provider_status="200"):
        self.transport_result = transport_result
        self.provider_status = provider_status
        # Present, and deliberately never read -- amendment 4 §2.3.
        self.outcome_class = "CONFIRMED_APPLIED"
        self.status = "APPLIED"
        self.dispatch_attempts = 1
        self.intent_id = "i-1"
        self.request_fingerprint = "fp"


ACK = Resolved()
TIMEOUT = Resolved(transport_result="timeout")
ERROR = Resolved(transport_result="", provider_status="503")


class ScriptedPlanner:
    """Answers from a per-(step, decision) script, and records what it saw."""

    model = snapshot = deployment = api_version = "stub"
    reasoning_effort = "low"

    def __init__(self, answers):
        self.answers = answers
        self.seen: list[Observation] = []

    def next_action(self, observation: Observation):
        self.seen.append(observation)
        answer = self.answers.get(
            (observation.step_index, observation.decision_index), "call"
        )
        if answer == "stop":
            return Stop("declined")
        return ToolCall(tool="send_notification", action="capture",
                        amount_minor=_amount_for(observation.step_index))


_AMOUNTS: dict[int, int] = {}


def _amount_for(step_index: int) -> int:
    return _AMOUNTS[step_index]


class _Config:
    """The fields plan_workload and the driver read. Same shape the
    interactive-loop tests already use -- a full RunConfig needs a Redis URL
    and a mock-API path that nothing here touches."""

    def __init__(self, results_root, **kw):
        self.run_id = kw.get("run_id", "r0")
        self.seed = kw.get("seed", 20260921)
        self.workers = kw.get("workers", 1)
        self.executions_per_worker = kw.get("executions_per_worker", 3)
        self.crash_probability = kw.get("crash_probability", 0.0)
        self.results_root = str(results_root)


@pytest.fixture
def config(tmp_path):
    cfg = _Config(tmp_path)
    _AMOUNTS.clear()
    for item in worker_items(plan_workload(cfg), 0):
        _AMOUNTS[item.execution_index] = item.amount_minor
    return cfg


def build(config, tmp_path, answers, from_index=0):
    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    wrapper = CallWrapper(run_id=config.run_id, run_dir=tmp_path / "r0",
                          cumulative=counter)
    planner = ScriptedPlanner(answers)
    events: list[tuple] = []
    driver = InteractiveDriver(
        config, 0, from_index, planner, wrapper,
        emit=lambda name, **kw: events.append((name, kw)),
    )
    return driver, planner, events, wrapper


def drive(driver, outcomes):
    """Iterate, feeding each yielded item the next outcome."""
    got = []
    iterator = iter(driver)
    for item in iterator:
        got.append(item)
        driver.observe(resolved=outcomes[len(got) - 1])
    return got


# -- the same payment -------------------------------------------------------

def test_a_non_acknowledged_outcome_re_decides_the_same_payment(config, tmp_path):
    driver, planner, _, _ = build(config, tmp_path, {})
    got = drive(driver, [TIMEOUT, ACK, ACK, ACK])

    first_two = [(o.step_index, o.decision_index) for o in planner.seen][:2]
    assert first_two == [(0, 0), (0, 1)], planner.seen

    # Same account and same harness-assigned amount, both times.
    assert got[0].execution_index == got[1].execution_index == 0
    assert got[0].target == got[1].target
    assert got[0].amount_minor == got[1].amount_minor == _AMOUNTS[0]


@pytest.mark.parametrize("outcome", [TIMEOUT, ERROR])
def test_every_non_acknowledged_outcome_re_decides(config, tmp_path, outcome):
    driver, planner, _, _ = build(config, tmp_path, {})
    drive(driver, [outcome, ACK, ACK, ACK])
    assert (0, 1) in {(o.step_index, o.decision_index) for o in planner.seen}


def test_an_acknowledgement_moves_to_the_next_payment(config, tmp_path):
    driver, planner, _, _ = build(config, tmp_path, {})
    got = drive(driver, [ACK, ACK, ACK])
    assert [(o.step_index, o.decision_index) for o in planner.seen] == [
        (0, 0), (1, 0), (2, 0)
    ]
    assert [i.execution_index for i in got] == [0, 1, 2]
    assert len({i.target for i in got}) == 3


def test_declining_a_re_decision_moves_to_the_next_payment(config, tmp_path):
    driver, planner, events, _ = build(config, tmp_path, {(0, 1): "stop"})
    got = drive(driver, [TIMEOUT, ACK, ACK])
    assert [i.execution_index for i in got] == [0, 1, 2]
    assert ("planner_declined_redispatch", ) not in events  # name check below
    assert any(name == "planner_declined_redispatch" for name, _ in events)


def test_a_stop_on_the_first_decision_still_ends_the_run(config, tmp_path):
    driver, _, _, _ = build(config, tmp_path, {(0, 0): "stop"})
    assert drive(driver, []) == []


def test_at_most_one_re_decision_per_payment(config, tmp_path):
    """MAX_DECISIONS_PER_EXECUTION is a bound, not an aspiration."""
    driver, planner, _, _ = build(config, tmp_path, {})
    drive(driver, [TIMEOUT, TIMEOUT, TIMEOUT, TIMEOUT, TIMEOUT, TIMEOUT])
    per_step: dict[int, set] = {}
    for o in planner.seen:
        per_step.setdefault(o.step_index, set()).add(o.decision_index)
    for step, decisions in per_step.items():
        assert len(decisions) <= MAX_DECISIONS_PER_EXECUTION, (step, decisions)


def test_a_redispatch_is_announced_in_the_event_log(config, tmp_path):
    driver, _, events, _ = build(config, tmp_path, {})
    drive(driver, [TIMEOUT, ACK, ACK, ACK])
    names = [name for name, _ in events]
    assert "planner_redispatched" in names
    payload = dict(next(kw for name, kw in events
                        if name == "planner_redispatched"))
    assert payload["decision_index"] == 1
    assert payload["execution_index"] == 0


# -- the crashed decision is not replayed -----------------------------------

def test_a_decision_made_and_observed_is_replayed_without_a_call(config, tmp_path):
    driver, planner, _, wrapper = build(config, tmp_path, {})
    drive(driver, [ACK, ACK, ACK])
    calls_before = wrapper.budget.calls

    driver2, planner2, _, wrapper2 = build(config, tmp_path, {})
    drive(driver2, [])
    assert planner2.seen == [], "a replayed run asked the planner something"
    assert wrapper2.budget.calls == calls_before


def test_a_decision_made_and_never_observed_earns_a_re_decision(config, tmp_path):
    """The crash landed inside it. Replaying it would re-dispatch silently."""
    driver, planner, _, wrapper = build(config, tmp_path, {})
    iterator = iter(driver)
    next(iterator)          # decision (0, 0) made and yielded
    del iterator            # the process dies here: no observe() call

    observations = ObservationLog(tmp_path / "r0" / ObservationLog.FILENAME)
    assert observations.index() == {}, "an unobserved decision was recorded"

    driver2, planner2, _, _ = build(config, tmp_path, {})
    drive(driver2, [ACK, ACK, ACK])
    asked = [(o.step_index, o.decision_index) for o in planner2.seen]
    assert asked[0] == (0, 1), asked
    assert (0, 0) not in asked, "the crashed decision was re-asked, not re-decided"


def test_the_replacement_is_told_the_outcome_is_unknown(config, tmp_path):
    driver, _, _, _ = build(config, tmp_path, {})
    iterator = iter(driver)
    next(iterator)
    del iterator

    class Recorder(ScriptedPlanner):
        pass

    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    wrapper = CallWrapper(run_id=config.run_id, run_dir=tmp_path / "r0",
                          cumulative=counter)
    planner = Recorder({})
    driver2 = InteractiveDriver(config, 0, 0, planner, wrapper)
    drive(driver2, [ACK, ACK, ACK])
    entries = wrapper.transcript.entries()
    redecision = [e for e in entries
                  if e["step_index"] == 0 and e["decision_index"] == 1]
    assert redecision, entries
    # Against OUTCOME_WORDING rather than a literal, so amendment 9's rewording
    # -- "your process THEN stopped" named the most recent decision and was
    # false after an absorbed re-dispatch -- cannot silently drift past this.
    from experiments.harness.agent_loop import OUTCOME_WORDING

    prompt = redecision[0]["prompt"]
    assert (UNKNOWN_PROCESS_DIED in prompt
            or OUTCOME_WORDING[UNKNOWN_PROCESS_DIED] in prompt), prompt


def test_the_observation_log_is_the_source_not_the_event_log(config, tmp_path):
    """Amendment 4 §3, without exception.

    The event log holds the oracle's execution_resolved record for the very
    turn the death was supposed to leave unknown. Reading it would hand the
    replacement agent the answer.
    """
    source = Path("experiments/harness/agent_loop.py").read_text(
        encoding="utf-8"
    )
    driver_src = source[source.index("class InteractiveDriver"):
                        source.index("def interactive_driver(")]
    assert "events.jsonl" not in driver_src
    assert "execution_resolved" not in driver_src
    assert "outcome_class" not in driver_src


def test_the_observation_log_records_only_caller_visible_values(config, tmp_path):
    driver, _, _, _ = build(config, tmp_path, {})
    drive(driver, [TIMEOUT, ACK, ACK, ACK])
    lines = [
        json.loads(line)
        for line in (tmp_path / "r0" / ObservationLog.FILENAME)
        .read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines
    for entry in lines:
        assert set(entry) == {"worker_index", "step_index", "decision_index",
                              "result"}
        assert entry["result"] in OUTCOME_VALUES


# -- two decisions for one execution must not collide -----------------------

def test_both_decisions_for_one_payment_are_counted_and_recorded(config, tmp_path):
    """Without decision_index in the key, the second would be deduplicated.

    The journal's first-write-wins would drop the second reservation -- a paid
    call that nothing counted, which is exactly what the journal exists to
    prevent -- and the replay slot would hold the wrong decision.
    """
    driver, _, _, wrapper = build(config, tmp_path, {})
    drive(driver, [TIMEOUT, ACK, ACK, ACK])

    entries = wrapper.transcript.entries()
    keys = [(e["step_index"], e["decision_index"]) for e in entries]
    assert (0, 0) in keys and (0, 1) in keys

    journal = [
        json.loads(line)
        for line in (tmp_path / "planner-cumulative.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    reservations = [e for e in journal if not e["key"].endswith(":settle")]
    assert len({e["key"] for e in reservations}) == len(reservations)
    assert sum(e["calls"] for e in reservations) == len(entries)
