"""The agent branch of the worker loop. The scripted path never enters it.

Phase 40, piece 2. ``worker.py`` builds its execution list from
``plan_workload(config)`` — a tuple fixed before the run starts and
recomputable after a ``SIGKILL``. An agent run is a *sequence* of decisions
instead (``docs/33`` §1.4), so the two cannot be the same expression.

**They are therefore two branches, not one generalised path.** The scripted
branch in ``worker.py`` is character-for-character what it was before this
module existed, and it is taken whenever the planner mode is absent or
``scripted`` — which is every frozen run, every existing config, and every
invocation that does not deliberately opt in. A regression in the scripted
path would have to survive
``tests/test_scripted_plan_is_frozen.py``, which recomputes 51 already-collected
runs' plans and compares them against what those runs recorded.

**The mode is read from the environment, never from ``RunConfig``.**
``docs/31-transmission-event.md`` §4: ``RunConfig._body()`` iterates every
dataclass field into ``config_digest``, so adding a field changes the digest of
every run ever collected — 150 of the 432 frozen matrix runs already fail that
check for exactly this reason. Phases 8.2, 10 and 13 all used the environment
block instead, and so does this.

**The target stays harness-assigned.** The planner chooses the tool, the action
and the amount. The execution id, the target and the crash selection come from
``plan_workload`` exactly as they do on the scripted path, which is what leaves
the duplicate metric sound and removes the WS-1a prerequisite
(``prompts/phase-40-agent-reachability.md`` §1.1).
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from experiments.harness.planner import (
    CallWrapper,
    CapExceeded,
    VoidReason,
    Observation,
    Planner,
    PlannerAttemptFailed,
    Stop,
    ToolCall,
)
from experiments.harness.workload import (
    WorkloadItem,
    plan_workload,
    worker_items,
)

#: The environment variable that selects the branch. Absent means scripted,
#: which is the only value any collected run has ever had.
PLANNER_MODE_ENV = "AEP_PLANNER_MODE"

SCRIPTED = "scripted"
STUB = "stub"
LIVE = "live"

#: Which loop shape. Orthogonal to the mode, so the interactive
#: loop can be exercised in stub mode at zero cost before it is
#: ever run live. Amendment 4 §5.
PLANNER_LOOP_ENV = "AEP_PLANNER_LOOP"
PLANNED = "planned"
INTERACTIVE = "interactive"


def planner_mode() -> str:
    """Which branch the worker takes. Defaults to the path that has data."""
    return (os.environ.get(PLANNER_MODE_ENV) or SCRIPTED).strip().lower()


def is_agent_mode() -> bool:
    return planner_mode() not in ("", SCRIPTED)


def loop_mode() -> str:
    """Which loop shape. Defaults to the one the stub stage validated."""
    return (os.environ.get(PLANNER_LOOP_ENV) or PLANNED).strip().lower()


def is_interactive() -> bool:
    return loop_mode() == INTERACTIVE


#: Everything ``last_outcome`` may carry, and nothing else. Amendment 4 §2.
#:
#: Derived from the transport alone, so the vocabulary is identical on both
#: arms. `rejected` (4xx) was approved and then withdrawn: there is no injected
#: 4xx fault -- the injected refusal is a 503, which in this harness already
#: means "refused before applying" -- and the only 4xx reachable in normal
#: operation are on the read-back routes, which B0_NAIVE_RETRY never calls.
#:
#: **The standing constraint on this set: an agent that can tell which arm it is
#: in is a second uncontrolled variable, and the comparison stops meaning
#: anything.** Anything added here must be visible to a real caller AND
#: identical in range across both systems.
#: tests/test_last_outcome_is_arm_neutral.py holds the second half.
TIMED_OUT = "timed_out"
SERVER_ERROR = "server_error"
ACKNOWLEDGED = "acknowledged"
UNKNOWN_PROCESS_DIED = "unknown_process_died"

OUTCOME_VALUES = (TIMED_OUT, SERVER_ERROR, ACKNOWLEDGED, UNKNOWN_PROCESS_DIED)

#: Everything that is not an acknowledgement. Amendment 6 §3: after one of
#: these the NEXT decision concerns the SAME payment -- same account, same
#: harness-assigned amount -- because §1's claim is "re-planning after an
#: ambiguous outcome" and that requires the ambiguous call and the re-decision
#: to be about the same execution.
NON_ACKNOWLEDGED = (TIMED_OUT, SERVER_ERROR, UNKNOWN_PROCESS_DIED)

#: One initial decision and at most one re-decision, per execution.
#:
#: Not a cost limit. The harness crashes each execution at most once --
#: ``runner.py`` drops the resumed execution from ``remaining_crashes`` so a
#: crashed system can make progress -- so one re-decision is enough to reach an
#: acknowledged outcome in the regime this runs in. And "how many times does an
#: agent retry" is a distribution, which §2 forbids this collection from
#: reporting; whether it retries at all is the binary claim §2 allows.
MAX_DECISIONS_PER_EXECUTION = 2

#: What the planner is shown for each. Deliberately in a caller's words, with
#: no reference to intents, dispatch counts, or anything the oracle computes.
OUTCOME_WORDING = {
    TIMED_OUT: (
        "it timed out. You received no response, and you do not know whether "
        "it was applied."
    ),
    SERVER_ERROR: (
        "the provider returned a server error before applying it."
    ),
    ACKNOWLEDGED: (
        "it was acknowledged."
    ),
    UNKNOWN_PROCESS_DIED: (
        "your process then stopped. You do not know whether it was sent, "
        "whether it arrived, or whether it was applied."
    ),
}


def classify_outcome(resolved, error) -> str:
    """The caller-visible result of one execution.

    Reads only what a caller could see. ``outcome_class``, ``status``,
    ``dispatch_attempts``, ``intent_id`` and ``request_fingerprint`` are all
    deliberately untouched -- the first two leak the oracle's verdict, the last
    three leak which arm the agent is in (amendment 4 §2.3).
    """
    if error is not None:
        name = type(error).__name__.lower()
        if "timeout" in name:
            return TIMED_OUT
        return SERVER_ERROR
    text = " ".join(
        str(getattr(resolved, field, "") or "")
        for field in ("transport_result", "provider_status")
    ).lower()
    if "timeout" in text or "timed out" in text:
        return TIMED_OUT
    if "503" in text or "server_error" in text or "5xx" in text:
        return SERVER_ERROR
    return ACKNOWLEDGED


class AgentRunVoided(RuntimeError):
    """The run stopped being a result. Carries the void reason."""

    def __init__(self, reason, detail: str):
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


def agent_worker_items(
    config,
    worker_index: int,
    from_index: int,
    planner: Planner,
    wrapper: CallWrapper,
    *,
    max_turns: int | None = None,
    emit=None,
) -> tuple[WorkloadItem, ...]:
    """Ask the planner for each step; keep the harness's identity fields.

    Returns items in the same shape the scripted branch returns, so everything
    downstream of the loop — the connector, the vault, the barrier, recovery,
    the oracle, the metrics — is untouched. The system under test is unchanged;
    only the caller above it is.
    """
    scaffold = [
        item
        for item in worker_items(plan_workload(config), worker_index)
        if item.execution_index >= from_index
    ]
    limit = len(scaffold) if max_turns is None else min(max_turns, len(scaffold))

    replay = wrapper.transcript.replay_index()
    decided: list[WorkloadItem] = []
    outcomes: list[str] = []

    for step, base in enumerate(scaffold[:limit]):
        observation = Observation(
            run_id=config.run_id,
            worker_index=worker_index,
            step_index=base.execution_index,
            prior_outcomes=tuple(outcomes),
        )

        # The planned branch has exactly one decision per execution, so it
        # always reads decision 0. Amendment 6's re-decision is the
        # interactive branch's, and this one is unchanged by it.
        recorded = replay.get((worker_index, base.execution_index, 0))
        if recorded is not None:
            # Replay: a respawned worker reads the transcript rather than
            # calling the model. Correctness and cost both -- a respawn that
            # re-called would double the bill of every crashed run.
            action = _action_from_completion(recorded["completion"], base)
        else:
            try:
                action = _ask(planner, observation, wrapper, base)
            except CapExceeded as capped:
                raise AgentRunVoided(capped.reason, capped.detail) from capped

        if isinstance(action, Stop):
            break

        _refuse_amount_drift(action, base, wrapper, emit)
        decided.append(
            replace(base, action=action.action, amount_minor=action.amount_minor)
        )
        # Retained only so the count of prior turns is known. It is NOT
        # shown to the planner as a capture history any more -- amendment 3 --
        # and it is not an outcome either, because the loop plans every turn
        # before executing any of them (amendment 2 §5).
        outcomes.append(f"{action.action} {action.amount_minor}")

    return tuple(decided)


class ObservationLog:
    """What the agent was told happened, append-only, in the run directory.

    **Why this file exists at all.** Amendment 6 §3.2 needs to distinguish a
    decision that was made and *observed* -- replayable, no model call -- from
    one that was made and never observed, which is the decision the crash
    landed inside and which earns a re-decision. The transcript records
    decisions; nothing recorded outcomes.

    **Why not the event log.** Amendment 4 §3, without exception: the replayed
    observation is derived from the agent's own record, never from
    ``events.jsonl``. The event log holds the oracle's ``execution_resolved``
    entry for the very turn the death was supposed to leave unknown, and
    reading it would hand the replacement agent the answer.

    What is written is only ``classify_outcome``'s output -- one of
    ``OUTCOME_VALUES`` -- which is caller-visible and arm-neutral by
    construction. Nothing else goes in here.
    """

    FILENAME = "planner-observations.jsonl"

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, worker_index: int, execution_index: int,
               decision_index: int, result: str) -> None:
        # One O_APPEND write per line, the same discipline the cumulative
        # journal uses and for the same reason: several worker lifetimes write
        # here and a read-modify-write would lose entries under a SIGKILL.
        line = json.dumps(
            {
                "worker_index": worker_index,
                "step_index": execution_index,
                "decision_index": decision_index,
                "result": result,
            },
            sort_keys=True,
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def index(self) -> dict[tuple[int, int, int], str]:
        """Last write wins per key: a re-executed decision observed twice."""
        out: dict[tuple[int, int, int], str] = {}
        if not self.path.is_file():
            return out
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            out[(entry["worker_index"], entry["step_index"],
                 int(entry.get("decision_index", 0)))] = entry["result"]
        return out


class InteractiveDriver:
    """Ask, execute, observe, ask again -- one decision at a time.

    Amendment 4 built the loop. Amendment 6 fixed what a turn means: after a
    non-acknowledged outcome the next decision concerns the SAME payment, so
    that the ambiguous call and the re-decision are about the same execution,
    which is what §1's claim requires.

    Iterating this object yields one item at a time. ``worker.py`` executes the
    item and calls :meth:`observe` with what happened; the next iteration uses
    it. The execution body in ``worker.py`` is otherwise unchanged, which is
    deliberate -- that body produces every number in the paper.
    """

    def __init__(self, config, worker_index, from_index, planner, wrapper,
                 *, emit=None, max_turns=None, observations=None):
        self.config = config
        self.worker_index = worker_index
        self.planner = planner
        self.wrapper = wrapper
        self.emit = emit
        self.scaffold = [
            item
            for item in worker_items(plan_workload(config), worker_index)
            if item.execution_index >= from_index
        ]
        if max_turns is not None:
            self.scaffold = self.scaffold[:max_turns]
        self.observations: list[str] = []
        self._replay = wrapper.transcript.replay_index()
        self._log = observations or ObservationLog(
            Path(wrapper.run_dir) / ObservationLog.FILENAME
        )
        self._observed = self._log.index()
        # No `from_index > 0` heuristic any more. Amendment 6 §4.3 makes BOTH
        # arms re-enter at the crashed execution, so from_index is 0 on a
        # respawn as often as not, and the old test would have read a respawn
        # as a clean start. What identifies the crashed decision is that it was
        # recorded and never observed -- which is a fact in the run directory
        # rather than an inference from an index, and is the same on both arms.
        self._pending = None

    def __len__(self) -> int:
        """How many turns are AVAILABLE, not how many will be taken.

        ``worker.py`` emits this as ``assigned`` on ``worker_started``.
        Under the interactive loop the number taken is not known until the
        run ends -- the planner may stop early, or may spend two decisions on
        one payment -- so what is reported is the scaffold's length, which is
        the same quantity the planned branch reports.
        """
        return len(self.scaffold)

    # -- what worker.py calls ------------------------------------------
    def observe(self, resolved=None, error=None) -> None:
        """Record the caller-visible result of the item just executed."""
        self._pending = classify_outcome(resolved, error)

    # -- the loop ------------------------------------------------------
    def __iter__(self):
        for base in self.scaffold:
            for decision_index in range(MAX_DECISIONS_PER_EXECUTION):
                key = (self.worker_index, base.execution_index, decision_index)
                decided = self._replay.get(key)
                observed = self._observed.get(key)

                if decided is not None and observed is not None:
                    # Made in an earlier lifetime AND its outcome recorded. It
                    # has already happened: replaying costs no model call and
                    # must not dispatch again. §5 of the pre-registration.
                    self._pending = observed
                    self.observations.append(observed)
                    if observed in NON_ACKNOWLEDGED:
                        continue
                    break

                if decided is not None and observed is None:
                    # Recorded and never observed: this is where the kill
                    # landed. NOT replayed -- amendment 6 §3.2. Re-dispatching
                    # on the strength of a decision the agent made before it
                    # knew anything had gone wrong is the harness deciding
                    # while appearing not to.
                    self._pending = UNKNOWN_PROCESS_DIED
                    continue

                try:
                    action = _ask(
                        self.planner,
                        Observation(
                            run_id=self.config.run_id,
                            worker_index=self.worker_index,
                            step_index=base.execution_index,
                            prior_outcomes=tuple(self.observations),
                            decision_index=decision_index,
                        ),
                        self.wrapper,
                        base,
                        last_outcome=self._pending,
                    )
                except CapExceeded as capped:
                    raise AgentRunVoided(capped.reason, capped.detail) from capped

                if isinstance(action, Stop):
                    if decision_index == 0:
                        # "No further call is warranted" about a payment not
                        # yet attempted ends the run, as it always has.
                        return
                    # A re-decision declined. Amendment 6 §3: a new payment is
                    # presented after an acknowledgement OR after the agent
                    # explicitly chooses not to dispatch this one again.
                    # Emitted so the archive shows the choice was offered and
                    # which way it went -- "the agent declined" and "the agent
                    # was never asked" must not look alike in the record.
                    self._emit("planner_declined_redispatch", base,
                               decision_index)
                    break

                _refuse_amount_drift(action, base, self.wrapper, self.emit)

                if decision_index > 0:
                    self._emit("planner_redispatched", base, decision_index)

                # The observation for THIS decision is not known until
                # worker.py has run it. Cleared so a crash between yielding
                # and observing records nothing -- which is exactly how the
                # next lifetime recognises the crashed decision.
                self._pending = None
                yield replace(base, action=action.action,
                              amount_minor=action.amount_minor)
                # worker.py has called observe() by now, unless it died -- in
                # which case this generator never resumes and nothing is
                # written, leaving the decision recorded and unobserved.
                result = self._pending or UNKNOWN_PROCESS_DIED
                self._log.record(self.worker_index, base.execution_index,
                                 decision_index, result)
                self._observed[key] = result
                self.observations.append(result)
                if result in NON_ACKNOWLEDGED:
                    continue
                break

    def _emit(self, event: str, base, decision_index: int) -> None:
        if self.emit is None:
            return
        self.emit(
            event,
            execution_id=base.execution_id,
            execution_index=base.execution_index,
            decision_index=decision_index,
            last_outcome=self._pending,
        )


def interactive_driver(config, worker_index: int, from_index: int, *,
                       emit=None):
    """Build the driver from the environment, like agent_items_for_worker."""
    from experiments.harness.planner import Caps, CumulativeCounter, StubPlanner

    mode = planner_mode()
    if mode not in (STUB, LIVE):
        raise RuntimeError(
            f"{PLANNER_MODE_ENV}={mode!r} selects a planner that does not exist."
        )
    run_dir = Path(config.results_root) / config.run_id
    counter = CumulativeCounter(
        Path(config.results_root) / "planner-cumulative.json"
    )
    wrapper = CallWrapper(
        run_id=config.run_id, run_dir=run_dir, cumulative=counter,
        caps=stage_caps(), planner=planner_record(),
    )
    scaffold = [
        item
        for item in worker_items(plan_workload(config), worker_index)
        if item.execution_index >= from_index
    ]
    if mode == LIVE:
        from experiments.harness.live_planner import LivePlanner

        planner = LivePlanner(counter=counter)
    else:
        planner = _ScaffoldStub(scaffold)
    return InteractiveDriver(config, worker_index, from_index, planner,
                             wrapper, emit=emit)


def _refuse_amount_drift(action, base, wrapper, emit) -> None:
    """The planner chooses the action. It does not choose what is measured.

    ``fingerprint.py``'s identity function includes ``amount_minor``, so an
    amount the harness did not assign is a term of the oracle's own identity
    function chosen by the system under test. Two executions meant to be
    distinct could be collapsed into one fingerprint, or a genuine duplicate
    pair split into two apparently separate effects -- in either direction the
    duplicate metric stops meaning what its name says.

    Found by the first corrected live stage: offered 896603 on turn 2, the
    planner answered 728995, which is 896603 minus the 167608 it had captured
    on turn 1. It was doing arithmetic the prompt invited, and the executed
    mutation would have carried an amount no plan contained.

    Treated exactly as a content filter is: a distinct void class, the run
    stops being a result, and it is never counted as a normal mutation.
    """
    if action.amount_minor == base.amount_minor:
        return
    detail = (
        f"planner returned amount_minor={action.amount_minor} for execution "
        f"{base.execution_id}, which the harness assigned "
        f"{base.amount_minor}. The oracle's identity function includes the "
        f"amount, so this is the system under test choosing a term of its own "
        f"measurement."
    )
    if emit is not None:
        emit(
            "planner_amount_mismatch",
            execution_id=base.execution_id,
            assigned_amount_minor=base.amount_minor,
            planner_amount_minor=action.amount_minor,
            void_reason=VoidReason.PLANNER_AMOUNT_MISMATCH.value,
        )
    wrapper.void(VoidReason.PLANNER_AMOUNT_MISMATCH, detail)
    raise AgentRunVoided(VoidReason.PLANNER_AMOUNT_MISMATCH, detail)


def _ask(
    planner: Planner,
    observation: Observation,
    wrapper: CallWrapper,
    base: WorkloadItem,
    last_outcome: str | None = None,
) -> ToolCall | Stop:
    """One decision, through the wrapper, with one retry on a malformed reply."""
    prompt = _prompt_for(observation, base, last_outcome)
    for attempt in (1, 2):
        # A fresh call object per attempt: the wrapper reads usage and identity
        # back off it afterwards, and a reused one would report the previous
        # attempt's tokens.
        call = _call_object(planner, observation, prompt)
        try:
            return wrapper.attempt(
                worker_index=observation.worker_index,
                step_index=observation.step_index,
                decision_index=observation.decision_index,
                attempt=attempt,
                prompt=prompt,
                call=call,
            )
        except PlannerAttemptFailed:
            if attempt == 2:
                raise
    raise AssertionError("unreachable")


def _call_object(planner: Planner, observation: Observation, prompt: str):
    """What the wrapper invokes.

    A planner that can build its own call object -- the live one -- supplies it,
    because the wrapper has to hold that object to read its token counts and
    model identity back. A planner that cannot is wrapped in a closure, which
    is what the stub has always been and costs nothing to keep.
    """
    maker = getattr(planner, "call_for", None)
    if maker is not None:
        return maker(observation, prompt)

    def make_call(*, max_output_tokens: int):
        make_call.max_output_tokens = max_output_tokens  # type: ignore[attr-defined]
        return planner.next_action(observation)

    return make_call


def _prompt_for(observation: Observation, base: WorkloadItem,
                last_outcome: str | None = None) -> str:
    """What the planner is shown. The oracle is not in it, by construction."""
    if planner_mode() == LIVE:
        from experiments.harness.live_planner import build_prompt

        # The amount is the work the harness assigned for THIS execution;
        # the planner still chooses the action and whether to act at all.
        # No capture history is passed: amendment 3 makes each turn its own
        # payment, and the history is what invited the arithmetic.
        wording = OUTCOME_WORDING.get(last_outcome) if last_outcome else None
        if observation.decision_index > 0:
            from experiments.harness.live_planner import build_redecision_prompt

            # Amendment 6: the SAME payment, and both choices put
            # symmetrically. This is the one place a prompt could decide the
            # result, so tests/test_redecision_prompt_is_neutral.py reads the
            # text rather than trusting this comment.
            return build_redecision_prompt(
                observation, base.target, base.amount_minor, wording
            )
        return build_prompt(observation, base.target, base.amount_minor,
                            wording)
    # The stub prompt carries the outcome too. Without it, stub mode would
    # exercise a different prompt from live mode and the interactive loop's
    # only zero-cost test would not be testing the thing that runs.
    previous = OUTCOME_WORDING.get(last_outcome, "none") if last_outcome \
        else "none"
    return (
        f"run={observation.run_id} worker={observation.worker_index} "
        f"step={observation.step_index} "
        f"decision={observation.decision_index} "
        f"prior={','.join(observation.prior_outcomes) or 'none'} "
        f"previous-call={previous} "
        f"target={base.target}"
    )


def _action_from_completion(completion: str, base: WorkloadItem) -> ToolCall | Stop:
    """Reconstruct the decision a transcript recorded.

    ``repr`` of the dataclass is what the wrapper stored, so this parses that
    shape. It is deliberately strict: a transcript that cannot be parsed must
    not silently become a fresh model call.
    """
    if "Stop(" in completion:
        return Stop("replayed stop")
    if "ToolCall(" not in completion:
        raise AgentRunVoided(
            _ReplayFailure.UNPARSEABLE,
            f"transcript entry for step {base.execution_index} is neither a "
            f"ToolCall nor a Stop: {completion[:80]!r}",
        )
    body = completion.split("ToolCall(", 1)[1].rsplit(")", 1)[0]
    fields: dict[str, str] = {}
    for part in body.split(","):
        if "=" in part:
            key, _, value = part.partition("=")
            fields[key.strip()] = value.strip().strip("'\"")
    return ToolCall(
        tool=fields.get("tool", ""),
        action=fields.get("action", base.action),
        amount_minor=int(fields.get("amount_minor", base.amount_minor)),
    )


class _ReplayFailure:
    class UNPARSEABLE:
        value = "VOID_TRANSCRIPT_UNPARSEABLE"

# ---------------------------------------------------------------------------
# What worker.py calls
# ---------------------------------------------------------------------------

#: Stub mode's canned decision. Deterministic, so a stub run replays; and
#: distinguishable from the scripted plan, so the data shows the planner chose
#: rather than that the scaffold passed through unchanged.
STUB_ACTION = "capture"


class _ScaffoldStub:
    """A stub planner keyed by step, not by position.

    ``StubPlanner`` walks its script with a cursor, and replay consumes no
    script entry -- so after a respawn replayed turn 0 from the transcript, the
    cursor was one behind and the stub answered turn 0's amount for turn 1. The
    amount guard voided the run, correctly; the stub was what was wrong.

    Keying on ``step_index`` makes it right by construction, whatever order the
    turns are asked for and however many lifetimes it takes.
    """

    model = "stub"
    snapshot = "stub-0"
    deployment = "stub"
    api_version = "stub"
    reasoning_effort = "low"

    def __init__(self, scaffold: Sequence[WorkloadItem]):
        self._by_step = {
            item.execution_index: item.amount_minor for item in scaffold
        }

    def next_action(self, observation: Observation):
        amount = self._by_step.get(observation.step_index)
        if amount is None:
            return Stop("no assignment for this step")
        if observation.decision_index > 0 and not self.redispatches(
            observation.step_index
        ):
            return Stop("stub declines to send this payment again")
        return ToolCall(tool="send_notification", action=STUB_ACTION,
                        amount_minor=amount)

    @staticmethod
    def redispatches(step_index: int) -> bool:
        """Which way the stub answers a re-decision, by execution.

        **Both choices must be exercised, on both arms**, or the zero-cost run
        tests half the branch it exists to test. Alternating on the execution
        index gives both within a single 3-execution run -- dispatch again on
        0 and 2, decline on 1 -- and does it deterministically, so a stub run
        still replays exactly and a respawn reproduces the same answer.

        It is the same rule on both systems: the stub is the fixed caller, and
        a stub that answered differently per arm would build the arm asymmetry
        amendment 6 §4 exists to remove straight back into the test.
        """
        return step_index % 2 == 0


def _stub_script(scaffold: Sequence[WorkloadItem]):
    from experiments.harness.planner import PlannerOutcome

    script = []
    for item in scaffold:
        script.append(
            (PlannerOutcome.OK,
             ToolCall(tool="send_notification", action=STUB_ACTION,
                      amount_minor=item.amount_minor))
        )
    script.append((PlannerOutcome.OK, Stop("plan exhausted")))
    return script


#: Stage caps, read from the environment. Each may only be LOWERED.
#:
#: The staging table in prompts/phase-40-agent-reachability.md §6 runs 10, 30,
#: 100 then 300 calls, and says the author raises each cap by hand -- so the
#: collection-wide numbers in §3 are the *maximum*, not the setting for any
#: given stage. A stage that could raise them by exporting a variable would
#: make the ceiling advisory, so this refuses upward and says so.
CAP_ENV = {
    "per_run_calls": "AEP_PLANNER_PER_RUN_CALLS",
    "per_collection_calls": "AEP_PLANNER_PER_COLLECTION_CALLS",
    "per_collection_usd": "AEP_PLANNER_PER_COLLECTION_USD",
}


def planner_record() -> dict[str, str]:
    """Which branch is running, resolved here because this is where env lives.

    ``planner.py`` must not read the environment -- pinned by
    ``test_nothing_in_this_module_reads_the_environment``, and the reason is
    that the next thing it would pick up implicitly is a key. So the mode and
    the loop are resolved here, where they already are, and passed down to be
    recorded.
    """
    return {"mode": planner_mode(), "loop": loop_mode()}


def stage_caps():
    """The pre-registered ceilings, optionally tightened for this stage."""
    from experiments.harness.planner import Caps

    ceiling = Caps()
    values = {}
    for field, name in CAP_ENV.items():
        raw = (os.environ.get(name) or "").strip()
        if not raw:
            continue
        limit = getattr(ceiling, field)
        try:
            value = type(limit)(raw)
        except ValueError:
            raise RuntimeError(f"{name}={raw!r} is not a {type(limit).__name__}")
        if value > limit:
            raise RuntimeError(
                f"{name}={value} is above the pre-registered ceiling {limit} "
                f"(prompts/phase-40-agent-reachability.md §3). These may be "
                f"lowered for a stage and never raised; raising one is an "
                f"amendment to the pre-registration, not an environment "
                f"variable."
            )
        if value <= 0:
            raise RuntimeError(f"{name}={value} must be positive")
        values[field] = value
    # max_output_tokens is deliberately absent: §3 calls it "what makes the
    # ceiling finite", so it is not a knob.
    return replace(ceiling, **values)


def agent_items_for_worker(config, worker_index: int, from_index: int,
                           emit=None):
    """The agent branch, assembled from the environment.

    Only reached when AEP_PLANNER_MODE selects it. Stub mode builds a
    StubPlanner and a CallWrapper whose run directory is the run's own, so the
    budget file and the transcript land beside the run's other artifacts.
    """
    from experiments.harness.planner import (
        Caps,
        CumulativeCounter,
        StubPlanner,
    )

    mode = planner_mode()
    scaffold = [
        item
        for item in worker_items(plan_workload(config), worker_index)
        if item.execution_index >= from_index
    ]
    if mode not in (STUB, LIVE):
        raise RuntimeError(
            f"{PLANNER_MODE_ENV}={mode!r} selects a planner that does not "
            f"exist. The implemented branches are {STUB!r} and {LIVE!r}."
        )

    run_dir = Path(config.results_root) / config.run_id
    counter = CumulativeCounter(
        Path(config.results_root) / "planner-cumulative.json"
    )
    wrapper = CallWrapper(
        run_id=config.run_id, run_dir=run_dir, cumulative=counter,
        caps=stage_caps(), planner=planner_record(),
    )
    if mode == LIVE:
        from experiments.harness.live_planner import LivePlanner

        planner = LivePlanner(counter=counter)
    else:
        planner = StubPlanner(script=_stub_script(scaffold))
    return agent_worker_items(
        config, worker_index, from_index, planner, wrapper, emit=emit
    )
