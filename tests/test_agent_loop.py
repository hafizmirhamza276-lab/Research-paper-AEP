"""The agent branch: what it decides, what it must not touch, when it voids.

Phase 40, piece 2. Two properties matter more than the rest.

*The scripted path never enters this code.* ``test_scripted_is_the_default``
and ``test_worker_keeps_the_scripted_expression_verbatim`` check that from both
ends -- the mode function's default, and the literal text still present in
``worker.py``. ``tests/test_scripted_plan_is_frozen.py`` checks the same thing
against 51 already-collected runs.

*The planner decides the action, never the identity.* The execution id, the
target and the crash selection stay harness-assigned, which is what leaves the
duplicate metric meaning what its name says
(``prompts/phase-40-agent-reachability.md`` §1.1). A planner that returned a
different target would be silently accepted by a loop that merged the two
branches; here it cannot, because the loop never reads a target from the
planner -- ``ToolCall`` has no such field, and
``test_the_planner_cannot_express_a_target`` pins that.

`docs/25` R13: the refusal paths -- caps, malformed replies, an unreadable
transcript -- are exercised here rather than first met live.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.harness import agent_loop
from experiments.harness.agent_loop import (
    AgentRunVoided,
    PLANNER_MODE_ENV,
    agent_worker_items,
    is_agent_mode,
    planner_mode,
)
from experiments.harness.planner import (
    CallWrapper,
    Caps,
    CumulativeCounter,
    PlannerOutcome,
    StubPlanner,
    Stop,
    ToolCall,
    TranscriptEntry,
    Usage,
    VoidReason,
)
from experiments.harness.workload import plan_workload, worker_items

ROOT = Path(__file__).resolve().parents[1]


class _Config:
    """The fields the workload planner and the loop read, and nothing else."""

    def __init__(self, **kw):
        self.run_id = kw.get("run_id", "agent-loop-test")
        self.seed = kw.get("seed", 20260917)
        self.workers = kw.get("workers", 2)
        self.executions_per_worker = kw.get("executions_per_worker", 3)
        self.crash_probability = kw.get("crash_probability", 0.0)
        self.results_root = kw.get("results_root", "")


def _wrapper(tmp_path: Path, caps: Caps | None = None) -> CallWrapper:
    return CallWrapper(
        run_id="agent-loop-test",
        run_dir=tmp_path / "run",
        cumulative=CumulativeCounter(tmp_path / "cumulative.json"),
        caps=caps or Caps(),
    )


def _ok(*actions):
    return [(PlannerOutcome.OK, a) for a in actions]


# ---------------------------------------------------------------------------
# The default, from both ends
# ---------------------------------------------------------------------------

def test_scripted_is_the_default(monkeypatch):
    """No environment variable means the path that has all the data."""
    monkeypatch.delenv(PLANNER_MODE_ENV, raising=False)
    assert planner_mode() == "scripted"
    assert is_agent_mode() is False


@pytest.mark.parametrize("value", ["", "scripted", "  SCRIPTED  ", "Scripted"])
def test_these_values_all_mean_scripted(monkeypatch, value):
    monkeypatch.setenv(PLANNER_MODE_ENV, value)
    assert is_agent_mode() is False


def test_stub_is_recognised_as_the_agent_branch(monkeypatch):
    """The counter-check: a mode function that always said False is vacuous."""
    monkeypatch.setenv(PLANNER_MODE_ENV, "stub")
    assert is_agent_mode() is True


def test_an_unknown_mode_refuses_rather_than_falling_back(monkeypatch, tmp_path):
    """A typo must not silently collect a scripted run labelled as agentic."""
    monkeypatch.setenv(PLANNER_MODE_ENV, "live")
    with pytest.raises(RuntimeError, match="does not exist"):
        agent_loop.agent_items_for_worker(
            _Config(results_root=str(tmp_path)), 0, 0
        )


def test_worker_keeps_the_scripted_expression_verbatim():
    """The scripted branch is the same characters it was before this existed.

    A textual check, deliberately. The behavioural check is
    ``tests/test_scripted_plan_is_frozen.py`` against collected runs; this one
    catches a refactor that preserves behaviour today and drifts tomorrow.
    """
    source = (ROOT / "experiments" / "harness" / "worker.py").read_text(
        encoding="utf-8"
    )
    assert "if not is_agent_mode():" in source
    assert (
        "for item in worker_items(plan_workload(config), worker_index)"
        in source
    )
    assert "if item.execution_index >= from_index" in source


def test_nothing_here_reads_a_planner_field_off_run_config():
    """``docs/31`` §4: a new RunConfig field rewrites every config_digest."""
    source = (ROOT / "experiments" / "harness" / "agent_loop.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("config.planner", "config.agent", "config.model"):
        assert forbidden not in source


# ---------------------------------------------------------------------------
# What the planner may and may not decide
# ---------------------------------------------------------------------------

def test_the_planner_cannot_express_a_target():
    """Structural, not conventional: the field does not exist to be set."""
    assert not hasattr(ToolCall(tool="t", action="a", amount_minor=1), "target")
    with pytest.raises(TypeError):
        ToolCall(tool="t", action="a", amount_minor=1, target="account-999")


def test_identity_fields_survive_the_planner(tmp_path):
    """Execution id, target, step id and crash selection stay harness-assigned."""
    config = _Config()
    scaffold = [
        i for i in worker_items(plan_workload(config), 0)
    ]
    planner = StubPlanner(script=_ok(*[
        ToolCall(tool="send_notification", action="capture", amount_minor=777)
        for _ in scaffold
    ]))
    decided = agent_worker_items(config, 0, 0, planner, _wrapper(tmp_path))

    assert len(decided) == len(scaffold)
    for got, base in zip(decided, scaffold):
        assert got.execution_id == base.execution_id
        assert got.target == base.target == f"account-{base.execution_id}"
        assert got.step_id == base.step_id
        assert got.crash_selected == base.crash_selected
        assert got.worker_index == base.worker_index
        assert got.execution_index == base.execution_index


def test_the_action_and_amount_do_come_from_the_planner(tmp_path):
    """The counter-check to the test above -- otherwise both pass vacuously."""
    config = _Config(executions_per_worker=2)
    scaffold = list(worker_items(plan_workload(config), 0))
    planner = StubPlanner(script=_ok(
        ToolCall(tool="send_notification", action="refund", amount_minor=11),
        ToolCall(tool="send_notification", action="refund", amount_minor=22),
    ))
    decided = agent_worker_items(config, 0, 0, planner, _wrapper(tmp_path))
    assert [i.amount_minor for i in decided] == [11, 22]
    assert {i.action for i in decided} == {"refund"}
    assert [i.amount_minor for i in scaffold] != [11, 22]


def test_stop_truncates_the_run(tmp_path):
    config = _Config(executions_per_worker=4)
    planner = StubPlanner(script=_ok(
        ToolCall(tool="send_notification", action="capture", amount_minor=1),
        Stop("done"),
        ToolCall(tool="send_notification", action="capture", amount_minor=2),
    ))
    decided = agent_worker_items(config, 0, 0, planner, _wrapper(tmp_path))
    assert len(decided) == 1


def test_max_turns_bounds_the_loop(tmp_path):
    config = _Config(executions_per_worker=6)
    planner = StubPlanner(script=_ok(*[
        ToolCall(tool="send_notification", action="capture", amount_minor=n)
        for n in range(6)
    ]))
    decided = agent_worker_items(
        config, 0, 0, planner, _wrapper(tmp_path), max_turns=3
    )
    assert len(decided) == 3


def test_from_index_skips_what_a_respawn_already_did(tmp_path):
    config = _Config(executions_per_worker=4)
    planner = StubPlanner(script=_ok(*[
        ToolCall(tool="send_notification", action="capture", amount_minor=9)
        for _ in range(4)
    ]))
    decided = agent_worker_items(config, 0, 2, planner, _wrapper(tmp_path))
    assert [i.execution_index for i in decided] == [2, 3]


def test_each_worker_gets_only_its_own_items(tmp_path):
    config = _Config(workers=3, executions_per_worker=2)
    script = _ok(*[
        ToolCall(tool="send_notification", action="capture", amount_minor=5)
        for _ in range(2)
    ])
    first = agent_worker_items(
        config, 0, 0, StubPlanner(script=script), _wrapper(tmp_path / "a")
    )
    second = agent_worker_items(
        config, 1, 0, StubPlanner(script=script), _wrapper(tmp_path / "b")
    )
    assert {i.worker_index for i in first} == {0}
    assert {i.worker_index for i in second} == {1}
    assert not {i.execution_id for i in first} & {
        i.execution_id for i in second
    }


# ---------------------------------------------------------------------------
# The refusal paths
# ---------------------------------------------------------------------------

def test_the_per_run_cap_voids_the_run(tmp_path):
    """Not "stop early with partial data" -- the run stops being a result."""
    config = _Config(executions_per_worker=10)
    planner = StubPlanner(script=_ok(*[
        ToolCall(tool="send_notification", action="capture", amount_minor=1)
        for _ in range(10)
    ]))
    wrapper = _wrapper(tmp_path, caps=Caps(per_run_calls=3))
    with pytest.raises(AgentRunVoided) as raised:
        agent_worker_items(config, 0, 0, planner, wrapper)
    assert raised.value.reason is VoidReason.PER_RUN_CALL_CAP
    assert (tmp_path / "run" / "VOID_REASON.md").is_file()


def test_the_collection_cap_voids_the_run(tmp_path):
    config = _Config(executions_per_worker=10)
    counter = CumulativeCounter(tmp_path / "cumulative.json")
    counter.write({"calls": 999, "usd": 0.0, "runs": 1, "voided": 0})
    wrapper = CallWrapper(
        run_id="agent-loop-test",
        run_dir=tmp_path / "run",
        cumulative=counter,
        caps=Caps(per_collection_calls=1000),
    )
    planner = StubPlanner(script=_ok(*[
        ToolCall(tool="send_notification", action="capture", amount_minor=1)
        for _ in range(10)
    ]))
    with pytest.raises(AgentRunVoided) as raised:
        agent_worker_items(config, 0, 0, planner, wrapper)
    assert raised.value.reason is VoidReason.COLLECTION_CALL_CAP


def test_a_filtered_response_voids_rather_than_retries(tmp_path):
    """A content filter is a datapoint about the provider, not a transient."""
    config = _Config(executions_per_worker=2)
    planner = StubPlanner(
        script=[(PlannerOutcome.FILTERED, "content_filter")]
    )
    wrapper = _wrapper(tmp_path)
    with pytest.raises(AgentRunVoided) as raised:
        agent_worker_items(config, 0, 0, planner, wrapper)
    assert raised.value.reason is VoidReason.PLANNER_FILTERED


def test_one_malformed_reply_is_retried(tmp_path):
    config = _Config(executions_per_worker=1)
    planner = StubPlanner(script=[
        (PlannerOutcome.MALFORMED, "not json"),
        (PlannerOutcome.OK,
         ToolCall(tool="send_notification", action="capture", amount_minor=4)),
    ])
    decided = agent_worker_items(config, 0, 0, planner, _wrapper(tmp_path))
    assert [i.amount_minor for i in decided] == [4]


def test_two_malformed_replies_stop_the_run(tmp_path):
    from experiments.harness.planner import PlannerAttemptFailed

    config = _Config(executions_per_worker=1)
    planner = StubPlanner(script=[
        (PlannerOutcome.MALFORMED, "not json"),
        (PlannerOutcome.MALFORMED, "still not json"),
    ])
    with pytest.raises(PlannerAttemptFailed):
        agent_worker_items(config, 0, 0, planner, _wrapper(tmp_path))


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

def test_a_respawn_replays_the_transcript_instead_of_calling_again(tmp_path):
    """Correctness and cost. A respawn that re-called would double the bill."""
    config = _Config(executions_per_worker=2)
    wrapper = _wrapper(tmp_path)
    planner = StubPlanner(script=_ok(
        ToolCall(tool="send_notification", action="capture", amount_minor=31),
        ToolCall(tool="send_notification", action="capture", amount_minor=32),
    ))
    first = agent_worker_items(config, 0, 0, planner, wrapper)
    calls_after_first = wrapper.budget.calls

    # A fresh wrapper over the same directory sees the same transcript; a
    # planner with an empty script would raise if it were consulted.
    second_wrapper = _wrapper(tmp_path)
    empty = StubPlanner(script=[])
    second = agent_worker_items(config, 0, 0, empty, second_wrapper)

    assert [i.amount_minor for i in second] == [i.amount_minor for i in first]
    assert calls_after_first == 2
    assert second_wrapper.budget.calls == 0, (
        "replay consulted the planner; every crashed run would bill twice"
    )


def test_an_unparseable_transcript_entry_voids(tmp_path):
    """It must not quietly become a fresh call with a different decision."""
    wrapper = _wrapper(tmp_path)
    wrapper.transcript.append(TranscriptEntry(
        run_id="agent-loop-test", worker_index=0, step_index=0, attempt=1,
        outcome=PlannerOutcome.OK, prompt="p", completion="{}",
        model="stub", snapshot="stub-0", deployment="stub",
        api_version="stub", reasoning_effort="low",
        sampling={"reasoning_effort": "low"}, usage=Usage(1, 1, 0),
    ))
    config = _Config(executions_per_worker=1)
    with pytest.raises(AgentRunVoided, match="UNPARSEABLE"):
        agent_worker_items(
            config, 0, 0, StubPlanner(script=[]), _wrapper(tmp_path)
        )


def test_the_transcript_records_every_attempt(tmp_path):
    config = _Config(executions_per_worker=2)
    wrapper = _wrapper(tmp_path)
    planner = StubPlanner(script=[
        (PlannerOutcome.MALFORMED, "bad"),
        (PlannerOutcome.OK,
         ToolCall(tool="send_notification", action="capture", amount_minor=1)),
        (PlannerOutcome.OK,
         ToolCall(tool="send_notification", action="capture", amount_minor=2)),
    ])
    agent_worker_items(config, 0, 0, planner, wrapper)
    entries = wrapper.transcript.entries()
    assert len(entries) == 3, "the failed attempt is recorded, not discarded"
    assert entries[0]["outcome"] == PlannerOutcome.MALFORMED.value


def test_the_prompt_does_not_contain_the_oracle(tmp_path):
    """The planner is not told what the ledger thinks happened."""
    config = _Config(executions_per_worker=2)
    wrapper = _wrapper(tmp_path)
    planner = StubPlanner(script=_ok(*[
        ToolCall(tool="send_notification", action="capture", amount_minor=1)
        for _ in range(2)
    ]))
    agent_worker_items(config, 0, 0, planner, wrapper)
    for entry in wrapper.transcript.entries():
        lowered = entry["prompt"].lower()
        for forbidden in ("oracle", "ledger", "duplicate", "ground truth"):
            assert forbidden not in lowered


def test_the_budget_file_is_written_even_with_zero_calls(tmp_path):
    """Stub mode must produce the same artifacts a live run would."""
    wrapper = _wrapper(tmp_path)
    data = json.loads(
        (tmp_path / "run" / "planner-budget.json").read_text(encoding="utf-8")
    )
    assert data["calls"] == 0
    assert data["usd"] == 0.0
    assert data["voided"] is None
