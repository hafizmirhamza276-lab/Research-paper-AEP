"""Amendment 6 §4: the agent decides whether to send again, on both arms.

**What stage 10 established, from the code and the live run directory.** In the
live `B0_NAIVE_RETRY` run, execution 0 was dispatched twice at 775463 and the
second dispatch was the *harness's*: `runner.py` sets `from_index` back under
`REEXECUTE_CRASHED`, the driver replayed the old decision, and the planner was
never asked. Under `AEP_FULL` the crashed payment was never re-dispatched at
all.

So the two arms differed in **who decides**, and on neither was it the agent.
While that held, any undetected duplicate was evidence about `ResumePolicy`
rather than about an LLM, and the comparison was between two supervisors rather
than two protocols.
"""
from __future__ import annotations

import pytest

from experiments.baselines.contract import ResumePolicy, SYSTEMS, descriptor_for
from experiments.harness import runner as runner_module
from experiments.harness.agent_loop import (
    INTERACTIVE,
    PLANNED,
    PLANNER_LOOP_ENV,
    PLANNER_MODE_ENV,
)

ARMS = ("AEP_FULL", "B0_NAIVE_RETRY")


class _Config:
    def __init__(self, system):
        self.descriptor = descriptor_for(system)
        self.resume_policy = None

    @property
    def effective_resume_policy(self):
        return self.resume_policy or self.descriptor.resume_policy


@pytest.fixture
def agent_interactive(monkeypatch):
    monkeypatch.setenv(PLANNER_MODE_ENV, "stub")
    monkeypatch.setenv(PLANNER_LOOP_ENV, INTERACTIVE)


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.delenv(PLANNER_MODE_ENV, raising=False)
    monkeypatch.delenv(PLANNER_LOOP_ENV, raising=False)


# -- the asymmetry this closes ---------------------------------------------

def test_the_two_arms_disagree_about_resume_off_the_agent_branch(scripted):
    """The finding itself, pinned so it cannot be forgotten.

    This is the state the scripted and planned branches are still in, and
    correctly so -- the descriptors describe real systems.
    """
    aep = _Config("AEP_FULL")
    b0 = _Config("B0_NAIVE_RETRY")
    assert aep.effective_resume_policy is ResumePolicy.NEXT_EXECUTION
    assert b0.effective_resume_policy is ResumePolicy.REEXECUTE_CRASHED

    assert runner_module.resume_from_index(aep, 0) == (1, None)
    assert runner_module.resume_from_index(b0, 0) == (
        0, "resume_reexecuting_crashed"
    )


def test_the_supervisor_redispatches_on_b0_off_the_agent_branch(scripted):
    """And the code says what that is for, in its own comment."""
    source = runner_module.__file__
    text = open(source, encoding="utf-8").read()
    assert "turns a crash into a duplicated external effect" in text


# -- what amendment 6 changes ----------------------------------------------

@pytest.mark.parametrize("system", ARMS)
def test_both_arms_re_enter_at_the_crashed_execution(agent_interactive, system):
    """Identically. That is the point: same caller, two protocols."""
    config = _Config(system)
    assert runner_module.resume_from_index(config, 0) == (
        0, "resume_for_agent_redecision"
    )
    assert runner_module.resume_from_index(config, 2) == (
        2, "resume_for_agent_redecision"
    )


def test_the_two_arms_now_resume_identically(agent_interactive):
    """The property stated as one assertion, over both systems."""
    results = {
        system: runner_module.resume_from_index(_Config(system), 1)
        for system in ARMS
    }
    assert len(set(results.values())) == 1, results


def test_the_descriptors_are_not_edited():
    """No protocol implementation changes. Only who is asked.

    `resume_policy` and `redispatches_on_replay` keep their values and keep
    governing the scripted and planned branches; `aep_core`'s ledger, barrier,
    fencing and recovery are untouched.
    """
    assert SYSTEMS["AEP_FULL"].resume_policy is ResumePolicy.NEXT_EXECUTION
    assert SYSTEMS["AEP_FULL"].redispatches_on_replay is False
    assert SYSTEMS["B0_NAIVE_RETRY"].resume_policy is ResumePolicy.REEXECUTE_CRASHED
    assert SYSTEMS["B0_NAIVE_RETRY"].redispatches_on_replay is True


# -- the branch is opt-in, and narrow --------------------------------------

def test_the_scripted_branch_is_untouched(scripted):
    for system in ARMS:
        config = _Config(system)
        expected = (
            (0, "resume_reexecuting_crashed")
            if config.effective_resume_policy is ResumePolicy.REEXECUTE_CRASHED
            else (1, None)
        )
        assert runner_module.resume_from_index(config, 0) == expected


def test_the_planned_agent_branch_is_untouched(monkeypatch):
    """Amendment 4's loop keeps the descriptor's policy. It is what the stub
    stage validated and it collects nothing new."""
    monkeypatch.setenv(PLANNER_MODE_ENV, "stub")
    monkeypatch.setenv(PLANNER_LOOP_ENV, PLANNED)
    assert runner_module.resume_from_index(_Config("AEP_FULL"), 0) == (1, None)


def test_the_selector_reads_the_environment_not_the_config(agent_interactive):
    """docs/31 §4: a RunConfig field would move every config_digest."""
    from dataclasses import fields

    from experiments.harness.config import RunConfig

    names = {f.name for f in fields(RunConfig)}
    assert "planner_mode" not in names
    assert "planner_loop" not in names
    assert runner_module._agent_owns_redispatch() is True


def test_a_crash_is_not_injected_twice_into_a_resumed_execution():
    """Both arms, on the agent branch.

    Without this the agent's re-dispatch would be crashed again and the worker
    would burn lifetimes instead of producing an answer -- and the one outcome
    the re-decision exists to reach, an acknowledgement, would be unreachable.
    """
    text = open(runner_module.__file__, encoding="utf-8").read()
    guard = text[text.index("remaining_crashes = ["):]
    guard = guard[:guard.index("if (")] + guard[guard.index("if ("):][:400]
    assert "_agent_owns_redispatch()" in guard, (
        "the no-second-crash suppression does not cover the agent branch"
    )


# -- the per-run cap, re-derived --------------------------------------------

def test_the_per_run_cap_is_derived_from_the_new_turn_structure():
    """Amendment 6 §7: (T x D + L) x A x W = (3 x 2 + 4) x 2 x 1 = 20.

    Written out rather than asserted as a literal, so a term that changes has
    to change here too.
    """
    from experiments.harness.agent_loop import MAX_DECISIONS_PER_EXECUTION

    T = 3                                   # executions per worker, §1
    D = MAX_DECISIONS_PER_EXECUTION         # initial + at most one re-decision
    L = 4                                   # lifetimes; executions + 1
    A = 2                                   # one call, one malformed retry
    W = 1                                   # what every live stage has run

    assert D == 2
    assert (T * D + L) * A * W == 20


def test_two_workers_would_breach_the_preregistered_ceiling():
    """§7.1, and the reason the design is pinned to one worker.

    At W=2 the same formula gives 40 against §3's per-run ceiling of 36, and
    ``stage_caps`` refuses anything above the pre-registered number. Amendment
    6 does not amend that ceiling, so this is a real constraint rather than a
    note -- recorded here so it is not rediscovered when a launch is refused.
    """
    from experiments.harness.agent_loop import MAX_DECISIONS_PER_EXECUTION
    from experiments.harness.planner import Caps

    at_two_workers = (3 * MAX_DECISIONS_PER_EXECUTION + 4) * 2 * 2
    assert at_two_workers == 40
    assert at_two_workers > Caps().per_run_calls == 36


def test_stage_caps_still_refuses_to_raise_the_per_run_cap(monkeypatch):
    """The refusal amendment 6 relies on, exercised rather than assumed."""
    from experiments.harness.agent_loop import stage_caps

    monkeypatch.setenv("AEP_PLANNER_PER_RUN_CALLS", "40")
    with pytest.raises(RuntimeError, match="above the pre-registered ceiling"):
        stage_caps()


def test_the_derived_cap_is_settable(monkeypatch):
    from experiments.harness.agent_loop import stage_caps

    monkeypatch.setenv("AEP_PLANNER_PER_RUN_CALLS", "20")
    assert stage_caps().per_run_calls == 20


def test_the_cap_stands_in_front_of_the_lifetime_ceiling():
    """§7.2. MAX_ATTEMPTS_PER_WORKER = 64 lifetimes, 2 attempts each.

    Without a per-run cap one run could reach 128 calls at one worker. The cap
    is the only thing in front of that number, and at 20 it stops 6.4x sooner.
    """
    from experiments.harness.runner import MAX_ATTEMPTS_PER_WORKER

    assert MAX_ATTEMPTS_PER_WORKER == 64
    pathological = MAX_ATTEMPTS_PER_WORKER * 2 * 1
    assert pathological == 128
    assert pathological / 20 == 6.4
