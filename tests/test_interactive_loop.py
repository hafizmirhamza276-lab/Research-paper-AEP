"""The interactive branch: ask, execute, observe, ask again.

Amendment 4. The planned branch asked for every turn before any of them ran, so
no outcome existed at decision time and §1's "observe an outcome, and re-plan"
was not what the code did.

The two properties that matter most here:

* the observation the planner receives is the one the *executing* loop handed
  back, not a prediction made before the run;
* a turn whose process died carries `unknown_process_died` and **not** what the
  event log later recorded. A respawned agent must not be given the answer that
  arrived after the death that was supposed to deny it.
"""

from __future__ import annotations

import pytest

from experiments.harness.agent_loop import (
    ACKNOWLEDGED,
    INTERACTIVE,
    PLANNED,
    PLANNER_LOOP_ENV,
    SERVER_ERROR,
    TIMED_OUT,
    UNKNOWN_PROCESS_DIED,
    InteractiveDriver,
    is_interactive,
    loop_mode,
)
from experiments.harness.planner import (
    CallWrapper,
    CumulativeCounter,
    PlannerOutcome,
    Stop,
    StubPlanner,
    ToolCall,
)
from experiments.harness.workload import plan_workload, worker_items


class _Config:
    def __init__(self, **kw):
        self.run_id = kw.get("run_id", "interactive-test")
        self.seed = kw.get("seed", 20260918)
        self.workers = kw.get("workers", 1)
        self.executions_per_worker = kw.get("executions_per_worker", 3)
        self.crash_probability = kw.get("crash_probability", 0.0)
        self.results_root = kw.get("results_root", "")


class _Resolved:
    def __init__(self, transport_result=""):
        self.transport_result = transport_result
        self.provider_status = ""
        self.status = "x"
        self.outcome_class = "CONFIRMED_APPLIED"
        self.dispatch_attempts = 1
        self.intent_id = None
        self.request_fingerprint = None


def _wrapper(tmp_path):
    return CallWrapper(
        run_id="interactive-test", run_dir=tmp_path / "run",
        cumulative=CumulativeCounter(tmp_path / "cumulative.json"),
    )


def _scaffold(config):
    return list(worker_items(plan_workload(config), 0))


def _assigned(config):
    return [
        (PlannerOutcome.OK,
         ToolCall(tool="send_notification", action="capture",
                  amount_minor=item.amount_minor))
        for item in _scaffold(config)
    ]


class _ByStep:
    """A planner keyed by (step, decision), not by position.

    Amendment 6 lets one execution carry two decisions, so a positional script
    hands the re-decision the NEXT payment's amount and amendment 3's guard
    voids the run -- correctly. The guard is right; a positional fixture is
    what would be wrong. Keying makes it right by construction.
    """

    model = snapshot = deployment = api_version = "stub"
    reasoning_effort = "low"

    def __init__(self, config, stops=()):
        self._amounts = {
            item.execution_index: item.amount_minor
            for item in _scaffold(config)
        }
        self._stops = set(stops)

    def next_action(self, observation):
        key = (observation.step_index, observation.decision_index)
        if key in self._stops:
            return Stop("declined")
        amount = self._amounts.get(observation.step_index)
        if amount is None:
            return Stop("no assignment")
        return ToolCall(tool="send_notification", action="capture",
                        amount_minor=amount)


def _driver(tmp_path, config, script=None, stops=()):
    planner = (StubPlanner(script=script) if script is not None
               else _ByStep(config, stops))
    return InteractiveDriver(config, 0, 0, planner, _wrapper(tmp_path))


# ---------------------------------------------------------------------------
# The mode selector
# ---------------------------------------------------------------------------

def test_the_planned_loop_is_the_default(monkeypatch):
    """The shape the stub stage validated stays the default."""
    monkeypatch.delenv(PLANNER_LOOP_ENV, raising=False)
    assert loop_mode() == PLANNED
    assert is_interactive() is False


def test_interactive_is_opt_in(monkeypatch):
    monkeypatch.setenv(PLANNER_LOOP_ENV, INTERACTIVE)
    assert is_interactive() is True


def test_the_loop_selector_is_orthogonal_to_the_mode(monkeypatch):
    """So the interactive loop can be exercised in stub mode at zero cost."""
    from experiments.harness.agent_loop import PLANNER_MODE_ENV, planner_mode

    monkeypatch.setenv(PLANNER_MODE_ENV, "stub")
    monkeypatch.setenv(PLANNER_LOOP_ENV, INTERACTIVE)
    assert planner_mode() == "stub"
    assert is_interactive() is True


# ---------------------------------------------------------------------------
# Ask, execute, observe, ask again
# ---------------------------------------------------------------------------

def test_the_planner_is_asked_one_turn_at_a_time(tmp_path):
    """The defect amendment 4 closes: decisions used to precede all execution."""
    config = _Config()
    driver = _driver(tmp_path, config)
    asked_before_first_execution = len(driver.wrapper.transcript.entries())

    seen = []
    for item in driver:
        # Exactly one decision has been made per item executed so far.
        seen.append(len(driver.wrapper.transcript.entries()))
        driver.observe(resolved=_Resolved("ok"))

    assert asked_before_first_execution == 0
    assert seen == [1, 2, 3], (
        "the planner was asked for more than one turn before the first "
        "execution, which is the planned loop, not the interactive one"
    )


def test_the_observation_reaches_the_next_prompt(tmp_path):
    """What the loop observed is what the planner is told next turn.

    The run is longer than three turns since amendment 6: a non-acknowledged
    outcome earns a re-decision about the same payment, so the first timeout
    buys a fourth decision rather than advancing. The property under test is
    unchanged -- each prompt carries the outcome of the call before it.
    """
    config = _Config()
    driver = _driver(tmp_path, config)
    results = ["timeout", "503 server_error", "ok", "ok", "ok", "ok"]
    for index, item in enumerate(driver):
        driver.observe(resolved=_Resolved(results[index]))

    assert driver.observations[:3] == [TIMED_OUT, SERVER_ERROR, ACKNOWLEDGED]
    prompts = [e["prompt"] for e in driver.wrapper.transcript.entries()]
    assert "timed out" in prompts[1], prompts[1]
    assert "server error" in prompts[2], prompts[2]
    assert "previous-call=none" in prompts[0], (
        "turn 1 must not be told about a call it has not made"
    )
    # The timeout was re-decided about the SAME payment, not the next one.
    entries = driver.wrapper.transcript.entries()
    assert (entries[0]["step_index"], entries[0]["decision_index"]) == (0, 0)
    assert (entries[1]["step_index"], entries[1]["decision_index"]) == (0, 1)


def test_the_first_turn_has_no_previous_call(tmp_path):
    config = _Config()
    driver = _driver(tmp_path, config)
    for item in driver:
        driver.observe(resolved=_Resolved("ok"))
    first = driver.wrapper.transcript.entries()[0]["prompt"]
    assert "previous-call=none" in first
    assert "timed out" not in first


def test_a_stop_ends_the_run_mid_stream(tmp_path):
    config = _Config()
    driver = _driver(tmp_path, config, stops={(1, 0)})
    executed = []
    for item in driver:
        executed.append(item)
        driver.observe(resolved=_Resolved("ok"))
    assert len(executed) == 1


def test_a_failed_execution_is_observed_too(tmp_path):
    """The error path feeds back as well as the success path."""
    import httpx

    config = _Config()
    driver = _driver(tmp_path, config)
    for index, item in enumerate(driver):
        if index == 0:
            driver.observe(error=httpx.ReadTimeout("no answer"))
        else:
            driver.observe(resolved=_Resolved("ok"))
    assert driver.observations[0] == TIMED_OUT


# ---------------------------------------------------------------------------
# The crash: what a respawned agent may be told
# ---------------------------------------------------------------------------

def test_a_turn_that_was_never_observed_is_unknown(tmp_path):
    """The worker died between yielding the item and observing it.

    The generator never resumes, so nothing is appended -- and the next
    lifetime must not invent an outcome for it.

    Amendment 6 moved where that fact lives. It used to be an in-memory
    sentinel on the dying object, which the next lifetime could not read. It is
    now the ABSENCE of a line in ``planner-observations.jsonl``, which is a
    fact on disk the replacement can act on -- and does, by asking a
    re-decision about the same payment instead of replaying the decision.
    """
    from experiments.harness.agent_loop import ObservationLog

    config = _Config()
    driver = _driver(tmp_path, config)
    iterator = iter(driver)
    next(iterator)          # turn 1 yielded, never observed
    assert driver.observations == []
    log = ObservationLog(driver.wrapper.run_dir / ObservationLog.FILENAME)
    assert log.index() == {}, "an unobserved decision was recorded anyway"
    # And the decision itself IS recorded, which is what makes the pair
    # "decided, never observed" recognisable as the crashed one.
    assert len(driver.wrapper.transcript.entries()) == 1


def test_the_pending_outcome_is_cleared_before_each_yield(tmp_path):
    """A crash must not leave the PREVIOUS turn's result standing.

    Without this, an agent whose process died on turn 2 would be told turn 1's
    outcome as though it were turn 2's -- strictly worse than being told
    nothing, because it is wrong rather than absent.
    """
    config = _Config()
    driver = _driver(tmp_path, config)
    iterator = iter(driver)
    next(iterator)
    driver.observe(resolved=_Resolved("ok"))
    assert driver._pending == ACKNOWLEDGED
    next(iterator)          # turn 2 yielded
    assert driver._pending is None, (
        "turn 2 is carrying turn 1's outcome; a crash here would misreport it"
    )
    # Cleared to None rather than to the sentinel, because amendment 6 records
    # the unknown on disk instead of holding it in memory. The property is the
    # same and is asserted here: whatever a crash at this point leaves behind,
    # it is not turn 1's result.
    assert driver._pending != ACKNOWLEDGED


def test_the_observation_never_comes_from_the_event_log(tmp_path):
    """Structural. The event log holds the answer the dead agent never saw.

    `execution_resolved` is written by worker.py after the execution completes.
    A respawned worker can read it. Reconstructing the observation from it
    would hand the replacement agent the outcome that arrived after the death
    which was supposed to deny it, and every decision afterwards would be
    worthless as evidence.
    """
    from pathlib import Path as _P

    source = (_P(__file__).resolve().parents[1] / "experiments" / "harness"
              / "agent_loop.py").read_text(encoding="utf-8")
    start = source.index("class InteractiveDriver")
    body = source[start:source.index("\ndef interactive_driver", start)]
    for forbidden in ("events.jsonl", "read_events", "execution_resolved",
                      "merge_event_shards"):
        assert forbidden not in body, (
            f"InteractiveDriver reads {forbidden!r}; the observation must come "
            f"from the transcript, which holds only what the agent received"
        )


def test_replay_makes_no_new_call_and_does_not_dispatch_again(tmp_path):
    """A respawn costs no model call for work already done -- and no dispatch.

    **Amendment 6 changed the second half, deliberately.** Under amendment 4 a
    replayed decision was yielded again, so ``worker.py`` executed it again.
    That is how B0's duplicate was produced at stage 10: the supervisor set
    ``from_index`` back, the driver replayed, and the mutation went out a
    second time with the planner never asked. It was evidence about
    ``ResumePolicy``, not about an agent.

    A decision that was made AND observed has already happened. Replaying it
    now re-reads the outcome and moves on. Re-dispatching, if it happens at
    all, is a fresh decision the agent is asked for (§3.2), and
    tests/test_same_payment_redecision.py holds that half.
    """
    config = _Config(executions_per_worker=2)
    first = _driver(tmp_path, config)
    executed = []
    for item in first:
        executed.append(item.amount_minor)
        first.observe(resolved=_Resolved("ok"))
    assert executed == [i.amount_minor for i in _scaffold(config)[:2]]
    assert len(first.wrapper.transcript.entries()) == 2

    class _Exploding:
        def next_action(self, observation):
            raise AssertionError("the planner was consulted during replay")

    second = InteractiveDriver(config, 0, 0, _Exploding(), _wrapper(tmp_path))
    re_executed = [item.amount_minor for item in second]

    assert re_executed == [], "a replayed decision was dispatched again"
    assert len(second.wrapper.transcript.entries()) == 2, "a new call was made"
    # The outcomes were re-read from the agent's own record, not re-derived.
    assert second.observations == [ACKNOWLEDGED, ACKNOWLEDGED]


# ---------------------------------------------------------------------------
# The guards still apply on this branch
# ---------------------------------------------------------------------------

def test_the_amount_guard_applies_to_the_interactive_branch(tmp_path):
    """Amendment 3's guard is not bypassed by the new loop."""
    from experiments.harness.agent_loop import AgentRunVoided
    from experiments.harness.planner import VoidReason

    config = _Config()
    base = _scaffold(config)
    script = [(PlannerOutcome.OK,
               ToolCall(tool="send_notification", action="capture",
                        amount_minor=base[0].amount_minor + 13))]
    driver = _driver(tmp_path, config, script)
    with pytest.raises(AgentRunVoided) as raised:
        for item in driver:
            driver.observe(resolved=_Resolved("ok"))
    assert raised.value.reason is VoidReason.PLANNER_AMOUNT_MISMATCH


def test_identity_fields_still_survive_the_planner(tmp_path):
    config = _Config()
    base = _scaffold(config)
    driver = _driver(tmp_path, config)
    got = []
    for item in driver:
        got.append(item)
        driver.observe(resolved=_Resolved("ok"))
    for item, expected in zip(got, base):
        assert item.execution_id == expected.execution_id
        assert item.target == expected.target
        assert item.crash_selected == expected.crash_selected
