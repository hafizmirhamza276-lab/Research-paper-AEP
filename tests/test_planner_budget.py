"""Exercise the controls that bound what a planner can spend.

``docs/26`` §3 rule 13, and the operator's own instruction: *"the caps and the
void classes are the controls that stand between me and an unbounded bill, and
they must be pinned before a live call, not after."* Every assertion here is on
a **refusal**, and each is watched firing.

Nothing in this file opens a socket or reads an environment variable. The
planner under test answers from a canned script, which is the whole point of
stub mode: every path the live client will take is exercised first at zero cost.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.harness.planner import (
    CallWrapper,
    CapExceeded,
    Caps,
    CumulativeCounter,
    Observation,
    Planner,
    PlannerAttemptFailed,
    PlannerOutcome,
    Price,
    Stop,
    StubPlanner,
    TRANSCRIPT_FIELDS,
    ToolCall,
    Transcript,
    TranscriptEntry,
    Usage,
    VoidReason,
)


class FakeCall:
    """Stands in for one HTTP attempt, carrying what a transport would report."""

    def __init__(self, result=None, usage: Usage | None = None,
                 fail: PlannerOutcome | None = None, detail: str = "x"):
        self.result = result if result is not None else ToolCall(
            "send_notification", "capture", 100
        )
        self.usage = usage or Usage(1200, 60, 740)
        self.fail = fail
        self.detail = detail
        self.model = "gpt-5.6-luna"
        self.snapshot = "gpt-5.6-luna-2026-07-09"
        self.deployment = "dep"
        self.api_version = "2026-08-01-preview"
        self.reasoning_effort = "low"
        self.sampling = {"temperature": 1.0, "top_p": 1.0}
        self.max_output_tokens_seen: list[int] = []

    def __call__(self, *, max_output_tokens: int):
        self.max_output_tokens_seen.append(max_output_tokens)
        if self.fail is not None:
            raise PlannerAttemptFailed(self.fail, self.detail)
        return self.result


@pytest.fixture()
def wrapper(tmp_path: Path) -> CallWrapper:
    return CallWrapper(
        run_id="r0",
        run_dir=tmp_path / "run",
        cumulative=CumulativeCounter(tmp_path / "collection" / "counter.json"),
        caps=Caps(per_run_calls=3, per_collection_calls=5,
                  max_output_tokens=1024, per_collection_usd=20.0),
    )


def fire(w: CallWrapper, call, step: int = 0, attempt: int = 1):
    return w.attempt(worker_index=0, step_index=step, attempt=attempt,
                     prompt="p", call=call)


# --------------------------------------------------------------------------
# Each cap fires at its boundary.
# --------------------------------------------------------------------------


def test_the_per_run_cap_fires_at_its_boundary_not_after(wrapper):
    for i in range(3):
        fire(wrapper, FakeCall(), step=i)
    assert wrapper.budget.calls == 3
    with pytest.raises(CapExceeded) as excinfo:
        fire(wrapper, FakeCall(), step=3)
    assert excinfo.value.reason is VoidReason.PER_RUN_CALL_CAP
    # The refused attempt was not made and was not billed.
    assert wrapper.budget.calls == 3


def test_a_run_that_breaches_its_cap_is_voided_not_counted(wrapper):
    for i in range(3):
        fire(wrapper, FakeCall(), step=i)
    with pytest.raises(CapExceeded):
        fire(wrapper, FakeCall(), step=3)
    assert wrapper.budget.voided is VoidReason.PER_RUN_CALL_CAP
    written = json.loads((wrapper.run_dir / "planner-budget.json").read_text())
    assert written["voided"] == "VOID_PER_RUN_CALL_CAP"
    assert (wrapper.run_dir / "VOID_REASON.md").is_file()
    assert "not a result" in (wrapper.run_dir / "VOID_REASON.md").read_text()


def test_the_collection_cap_stops_the_collection(tmp_path):
    counter = CumulativeCounter(tmp_path / "counter.json")
    caps = Caps(per_run_calls=100, per_collection_calls=4)
    made = 0
    with pytest.raises(CapExceeded) as excinfo:
        for run in range(3):
            w = CallWrapper(f"r{run}", tmp_path / f"run{run}", counter, caps)
            for step in range(3):
                fire(w, FakeCall(), step=step)
                made += 1
    assert excinfo.value.reason is VoidReason.COLLECTION_CALL_CAP
    assert made == 4, "the collection stopped at its cap, not after it"
    assert counter.read()["calls"] == 4


def test_max_output_tokens_is_applied_to_every_call(wrapper):
    calls = [FakeCall() for _ in range(3)]
    for i, c in enumerate(calls):
        fire(wrapper, c, step=i)
    for c in calls:
        assert c.max_output_tokens_seen == [1024]


def test_the_usd_ceiling_refuses_once_reached(tmp_path):
    counter = CumulativeCounter(tmp_path / "counter.json")
    counter.write({"calls": 1, "usd": 20.0, "runs": 0, "voided": 0})
    w = CallWrapper("r0", tmp_path / "run", counter,
                    Caps(per_run_calls=100, per_collection_calls=100,
                         per_collection_usd=20.0))
    with pytest.raises(CapExceeded) as excinfo:
        fire(w, FakeCall())
    assert excinfo.value.reason is VoidReason.COLLECTION_CALL_CAP


# --------------------------------------------------------------------------
# The counter survives a crash-restart.
# --------------------------------------------------------------------------


def test_the_cumulative_counter_survives_a_simulated_crash_restart(tmp_path):
    """In memory this would reset, and the ceiling would be worthless."""
    path = tmp_path / "counter.json"
    caps = Caps(per_run_calls=2, per_collection_calls=3)

    first = CallWrapper("r0", tmp_path / "r0", CumulativeCounter(path), caps)
    fire(first, FakeCall())
    fire(first, FakeCall(), step=1)
    del first  # the process dies here

    # A wholly new process, new wrapper, new counter object, same file.
    second = CallWrapper("r1", tmp_path / "r1", CumulativeCounter(path), caps)
    fire(second, FakeCall())
    with pytest.raises(CapExceeded) as excinfo:
        fire(second, FakeCall(), step=1)
    assert excinfo.value.reason is VoidReason.COLLECTION_CALL_CAP
    assert CumulativeCounter(path).read()["calls"] == 3


def test_an_unreadable_counter_is_not_treated_as_zero(tmp_path):
    """The safe direction: refuse rather than read corruption as no spend."""
    path = tmp_path / "counter.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(CapExceeded):
        CumulativeCounter(path).read()


def test_the_counter_write_is_atomic(tmp_path):
    """os.replace, so a crash mid-write leaves old or new, never truncated."""
    path = tmp_path / "counter.json"
    counter = CumulativeCounter(path)
    counter.add(1, 0.5)
    counter.add(1, 0.5)
    assert counter.read() == {"calls": 2, "usd": 1.0, "runs": 0, "voided": 0}
    assert not list(path.parent.glob(".counter-*")), "temp file left behind"


# --------------------------------------------------------------------------
# SDK-level retries count.
# --------------------------------------------------------------------------


def test_every_attempt_counts_including_retries(wrapper):
    """Three attempts at one logical step is three billed calls, not one.

    An SDK retries 429s and timeouts inside one responses.create(). A counter
    around that method would see one call where three were billed, and the cap
    would be three times looser than it reads.
    """
    for attempt in (1, 2, 3):
        fire(wrapper, FakeCall(), step=0, attempt=attempt)
    assert wrapper.budget.calls == 3
    entries = wrapper.transcript.entries()
    assert [e["attempt"] for e in entries] == [1, 2, 3]
    assert {e["step_index"] for e in entries} == {0}


def test_a_failed_attempt_is_still_counted_and_priced(wrapper):
    """A malformed completion consumed tokens. Not counting it understates."""
    with pytest.raises(PlannerAttemptFailed):
        fire(wrapper, FakeCall(fail=PlannerOutcome.MALFORMED))
    assert wrapper.budget.calls == 1
    assert wrapper.budget.usd > 0


# --------------------------------------------------------------------------
# PLANNER_FILTERED.
# --------------------------------------------------------------------------


def test_a_filtered_call_voids_the_run_under_its_own_class(wrapper):
    with pytest.raises(CapExceeded) as excinfo:
        fire(wrapper, FakeCall(fail=PlannerOutcome.FILTERED, detail="blocked"))
    assert excinfo.value.reason is VoidReason.PLANNER_FILTERED
    assert wrapper.budget.voided is VoidReason.PLANNER_FILTERED


def test_a_filter_block_is_never_a_protocol_outcome(wrapper):
    """It must not be expressible as declared ambiguity anywhere."""
    with pytest.raises(CapExceeded):
        fire(wrapper, FakeCall(fail=PlannerOutcome.FILTERED))
    text = (wrapper.run_dir / "VOID_REASON.md").read_text()
    assert "never folded into declared ambiguity" in text
    assert PlannerOutcome.FILTERED.value == "PLANNER_FILTERED"
    assert VoidReason.PLANNER_FILTERED.value == "VOID_PLANNER_FILTERED"


# --------------------------------------------------------------------------
# Cost counters.
# --------------------------------------------------------------------------


def test_cost_counters_are_written_into_the_run_directory(wrapper):
    path = wrapper.run_dir / "planner-budget.json"
    assert path.is_file(), "written at construction, before any call"
    assert json.loads(path.read_text())["calls"] == 0
    fire(wrapper, FakeCall())
    written = json.loads(path.read_text())
    assert written["calls"] == 1
    assert written["prompt_tokens"] == 1200
    assert written["output_tokens"] == 800, "reasoning tokens bill as output"


def test_price_counts_reasoning_tokens_as_output():
    usage = Usage(prompt_tokens=1_000_000, completion_tokens=0,
                  reasoning_tokens=1_000_000)
    assert usage.output == 1_000_000
    assert Price().usd(usage.prompt_tokens, usage.output) == pytest.approx(1.40)


# --------------------------------------------------------------------------
# Transcript and replay.
# --------------------------------------------------------------------------


def test_the_transcript_records_all_fourteen_fields(wrapper):
    fire(wrapper, FakeCall())
    entry = wrapper.transcript.entries()[0]
    for field in TRANSCRIPT_FIELDS:
        assert field in entry, f"transcript is missing {field}"
    assert entry["schema_version"] == "aep.agent.transcript/1"
    assert entry["usage"]["reasoning_tokens"] == 740


def test_replay_returns_the_completion_that_was_acted_on(wrapper):
    """A step whose first attempt was malformed replays the second, not the first."""
    with pytest.raises(PlannerAttemptFailed):
        fire(wrapper, FakeCall(fail=PlannerOutcome.MALFORMED, detail="bad"),
             step=0, attempt=1)
    fire(wrapper, FakeCall(result=ToolCall("charge_card", "capture", 7)),
         step=0, attempt=2)
    index = wrapper.transcript.replay_index()
    assert list(index) == [(0, 0)]
    assert index[(0, 0)]["attempt"] == 2
    assert "charge_card" in index[(0, 0)]["completion"]


def test_replay_index_holds_one_entry_per_step(wrapper):
    for step in range(3):
        fire(wrapper, FakeCall(), step=step)
    assert sorted(wrapper.transcript.replay_index()) == [(0, 0), (0, 1), (0, 2)]


# --------------------------------------------------------------------------
# The planner seam.
# --------------------------------------------------------------------------


def test_the_stub_planner_answers_from_its_script():
    planner: Planner = StubPlanner(script=[
        (PlannerOutcome.OK, ToolCall("charge_card", "capture", 1)),
        (PlannerOutcome.OK, Stop("done")),
    ])
    obs = Observation(run_id="r", worker_index=0, step_index=0)
    assert isinstance(planner.next_action(obs), ToolCall)
    assert isinstance(planner.next_action(obs), Stop)


def test_the_stub_can_produce_a_filtered_response():
    """So the PLANNER_FILTERED path is exercised at zero cost, not first in live mode."""
    planner = StubPlanner(script=[(PlannerOutcome.FILTERED, "blocked")])
    with pytest.raises(PlannerAttemptFailed) as excinfo:
        planner.next_action(Observation("r", 0, 0))
    assert excinfo.value.outcome is PlannerOutcome.FILTERED


def test_a_tool_call_cannot_carry_a_target():
    """Phase 40 keeps the target harness-assigned. A planner must not name one."""
    assert not hasattr(ToolCall("charge_card", "capture", 1), "target")
    with pytest.raises(TypeError):
        ToolCall("charge_card", "capture", 1, target="account-x")  # type: ignore[call-arg]


def test_nothing_in_this_module_reads_the_environment():
    """No key can be picked up implicitly; stub mode needs no .env."""
    source = Path(__file__).resolve().parents[1] / "experiments" / "harness" / "planner.py"
    text = source.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
