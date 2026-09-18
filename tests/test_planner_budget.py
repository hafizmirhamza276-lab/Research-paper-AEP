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
    # Seeded through the journal, which is the authority. `write` now only
    # refreshes the human-readable snapshot and nothing reads it back.
    counter.add(1, 20.0, key="already-spent")
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
    counter = CumulativeCounter(tmp_path / "counter.json")
    counter.add(1, 0.5, key="real")
    counter.journal.write_text("{not json", encoding="utf-8")
    with pytest.raises(CapExceeded):
        counter.read()


def test_a_corrupt_snapshot_is_harmless_because_nothing_reads_it(tmp_path):
    """The counterpart, and a real change in what is protected.

    ``planner-cumulative.json`` used to be the authority, so corrupting it had
    to be refused. It is now derived from the journal and is not an input to
    any decision, so corrupting it can be ignored -- there is nothing left to
    protect. Asserted rather than left implied, because "we stopped checking
    that file" and "that file stopped mattering" look identical in a diff.
    """
    counter = CumulativeCounter(tmp_path / "counter.json")
    counter.add(1, 0.5, key="real")
    counter.path.write_text("{ not json at all", encoding="utf-8")
    assert counter.read()["calls"] == 1


def test_the_counter_write_is_atomic(tmp_path):
    """os.replace, so a crash mid-write leaves old or new, never truncated."""
    path = tmp_path / "counter.json"
    counter = CumulativeCounter(path)
    counter.add(1, 0.5, key="a")
    counter.add(1, 0.5, key="b")
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


# --------------------------------------------------------------------------
# The three defects the stub stage found, each pinned separately.
# reports/phase-report-40-stub-stage-2026-09-17.md §5 and §7.
# --------------------------------------------------------------------------


def test_a_respawn_resumes_the_run_budget_instead_of_zeroing_it(tmp_path):
    """Defect A. The per-run counter was clobbered by the worker that replayed.

    ``CallWrapper.__init__`` wrote ``RunBudget(calls=0)`` over the file the
    first attempt had filled in, so every run's ``planner-budget.json`` read
    ``calls: 0`` beside a transcript holding four entries. Last writer wins,
    and the last writer always had nothing to report.
    """
    counter = CumulativeCounter(tmp_path / "counter.json")
    first = CallWrapper("r0", tmp_path / "run", counter)
    for step in range(3):
        fire(first, FakeCall(), step=step)
    assert first.budget.calls == 3

    respawn = CallWrapper("r0", tmp_path / "run", counter)
    assert respawn.budget.calls == 3, (
        "the respawned worker reset the run's budget to zero"
    )
    assert respawn.budget.usd == pytest.approx(first.budget.usd)
    assert respawn.budget.prompt_tokens == first.budget.prompt_tokens

    recorded = json.loads(
        (tmp_path / "run" / "planner-budget.json").read_text(encoding="utf-8")
    )
    assert recorded["calls"] == 3


def test_the_per_run_cap_is_not_reset_by_a_respawn(tmp_path):
    """Defect A's consequence, which is worse than the wrong number in a file.

    The per-run cap is checked against the same counter. A run that respawned
    got a fresh 36 calls per attempt, so at ``p(crash)=1.0`` -- the regime the
    whole experiment runs in -- the per-run cap bounded nothing.
    """
    counter = CumulativeCounter(tmp_path / "counter.json")
    caps = Caps(per_run_calls=4, per_collection_calls=10_000)
    first = CallWrapper("r0", tmp_path / "run", counter, caps)
    for step in range(4):
        fire(first, FakeCall(), step=step)

    respawn = CallWrapper("r0", tmp_path / "run", counter, caps)
    with pytest.raises(CapExceeded) as raised:
        fire(respawn, FakeCall(), step=99)
    assert raised.value.reason is VoidReason.PER_RUN_CALL_CAP


def test_the_collection_counts_runs_and_voids_rather_than_reporting_zero(
    tmp_path,
):
    """Defect C. ``runs`` was initialised, written, read, and never incremented.

    It read 0 after six runs. Both fields are now derived from the journal --
    distinct run ids that made at least one call, and of those the ones that
    voided -- so neither can drift from what happened.
    """
    counter = CumulativeCounter(tmp_path / "counter.json")
    for index in range(3):
        wrapper = CallWrapper(
            f"run-{index}", tmp_path / f"run-{index}", counter
        )
        fire(wrapper, FakeCall())

    state = counter.read()
    assert state["runs"] == 3, f"three runs made calls, counted {state['runs']}"
    assert state["voided"] == 0

    doomed = CallWrapper("run-3", tmp_path / "run-3", counter)
    fire(doomed, FakeCall())
    doomed.void(VoidReason.PLANNER_FILTERED, "content filter")

    after = counter.read()
    assert after["runs"] == 4
    assert after["voided"] == 1


def test_the_call_is_counted_before_it_is_dispatched(tmp_path):
    """The ordering defect, which is why SIGKILL could hide a paid call.

    ``attempt``'s docstring always said "Count, cap, invoke". The code counted
    in the ``finally``, *after* the call returned, so a worker killed between
    the request and the increment had spent money nothing recorded. The harness
    injects SIGKILL by design, so this was not a corner case.

    The call itself observes the counter to prove the ordering.
    """
    counter = CumulativeCounter(tmp_path / "counter.json")
    wrapper = CallWrapper("r0", tmp_path / "run", counter)
    seen = {}

    def observing_call(*, max_output_tokens):
        seen["calls_during_the_call"] = counter.read()["calls"]
        return Stop("done")

    observing_call.usage = Usage(1000, 50, 0)
    wrapper.attempt(worker_index=0, step_index=0, attempt=1,
                    prompt="p", call=observing_call)

    assert seen["calls_during_the_call"] == 1, (
        "the call was already in flight and the collection counter still read "
        "zero; a SIGKILL here would have lost a paid call"
    )


def test_the_reservation_is_priced_at_the_ceiling_then_settled(tmp_path):
    """Dying mid-call over-counts, which stops a collection early.

    The real cost is not known until the call returns, so the reservation is
    priced at the most §3 permits one call to cost. The difference is settled
    afterwards. The error direction is deliberate: over-counting ends a
    collection sooner than needed, under-counting spends money nobody counted.
    """
    counter = CumulativeCounter(tmp_path / "counter.json")
    caps = Caps()
    price = Price()
    wrapper = CallWrapper("r0", tmp_path / "run", counter, caps)

    during = {}

    def observing_call(*, max_output_tokens):
        during["usd"] = counter.read()["usd"]
        return Stop("done")

    observing_call.usage = Usage(10, 1, 0)
    wrapper.attempt(worker_index=0, step_index=0, attempt=1,
                    prompt="p", call=observing_call)

    reserved = price.usd(caps.max_prompt_tokens, caps.max_output_tokens)
    assert during["usd"] == pytest.approx(reserved)
    assert counter.read()["usd"] == pytest.approx(price.usd(10, 1))
    assert counter.read()["usd"] < during["usd"]


def test_a_settled_reservation_is_not_double_counted_on_replay(tmp_path):
    """The same attempt appended twice must still count once."""
    counter = CumulativeCounter(tmp_path / "counter.json")
    wrapper = CallWrapper("r0", tmp_path / "run", counter)
    fire(wrapper, FakeCall(), step=0)
    once = counter.read()

    twin = CallWrapper("r0", tmp_path / "run", counter)
    fire(twin, FakeCall(), step=0)
    assert counter.read()["calls"] == once["calls"]
