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


def _driver(tmp_path, config, script=None):
    return InteractiveDriver(
        config, 0, 0, StubPlanner(script=script or _assigned(config)),
        _wrapper(tmp_path),
    )


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
    """What the loop observed is what the planner is told next turn."""
    config = _Config()
    driver = _driver(tmp_path, config)
    results = ["timeout", "503 server_error", "ok"]
    for index, item in enumerate(driver):
        driver.observe(resolved=_Resolved(results[index]))

    assert driver.observations == [TIMED_OUT, SERVER_ERROR, ACKNOWLEDGED]
    prompts = [e["prompt"] for e in driver.wrapper.transcript.entries()]
    assert "timed out" in prompts[1], prompts[1]
    assert "server error" in prompts[2], prompts[2]
    assert "previous-call=none" in prompts[0], (
        "turn 1 must not be told about a call it has not made"
    )


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
    script = _assigned(config)
    script[1] = (PlannerOutcome.OK, Stop("nothing further warranted"))
    driver = _driver(tmp_path, config, script)
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
    """
    config = _Config()
    driver = _driver(tmp_path, config)
    iterator = iter(driver)
    next(iterator)          # turn 1 yielded, never observed
    assert driver.observations == []
    assert driver._pending == UNKNOWN_PROCESS_DIED


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
    assert driver._pending == UNKNOWN_PROCESS_DIED, (
        "turn 2 is carrying turn 1's outcome; a crash here would misreport it"
    )


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


def test_replay_reuses_the_decision_and_makes_no_new_call(tmp_path):
    """A respawn re-walks decided turns from the transcript, as before."""
    config = _Config(executions_per_worker=2)
    first = _driver(tmp_path, config)
    for item in first:
        first.observe(resolved=_Resolved("ok"))
    decided = [e["completion"] for e in first.wrapper.transcript.entries()]
    assert len(decided) == 2

    class _Exploding:
        def next_action(self, observation):
            raise AssertionError("the planner was consulted during replay")

    second = InteractiveDriver(config, 0, 0, _Exploding(), _wrapper(tmp_path))
    replayed = []
    for item in second:
        replayed.append(item.amount_minor)
        second.observe(resolved=_Resolved("ok"))
    assert replayed == [i.amount_minor for i in _scaffold(config)[:2]]
    assert len(second.wrapper.transcript.entries()) == 2, "a new call was made"


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
