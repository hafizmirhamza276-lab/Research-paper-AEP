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

        recorded = replay.get((worker_index, base.execution_index))
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


class InteractiveDriver:
    """Ask, execute, observe, ask again -- one turn at a time.

    Amendment 4. The planned loop asked for every turn before any of them ran,
    so no outcome existed at decision time and §1's "observe an outcome, and
    re-plan" was not what the code did.

    Iterating this object yields one item at a time. ``worker.py`` executes the
    item and calls :meth:`observe` with what happened; the next iteration uses
    it. The execution body in ``worker.py`` is otherwise unchanged, which is
    deliberate -- that body produces every number in the paper.
    """

    def __init__(self, config, worker_index, from_index, planner, wrapper,
                 *, emit=None, max_turns=None):
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
        # A respawned worker resumes at from_index > 0, which means an earlier
        # turn was issued by a process that then died. Its outcome is exactly
        # what amendment 4 §3 describes: not "no calls yet", but "a call was
        # made and you cannot know what became of it". Starting at None would
        # tell the replacement agent it had a clean slate, which is false and
        # is the more misleading of the two.
        self._pending = UNKNOWN_PROCESS_DIED if from_index > 0 else None

    def __len__(self) -> int:
        """How many turns are AVAILABLE, not how many will be taken.

        ``worker.py`` emits this as ``assigned`` on ``worker_started``.
        Under the interactive loop the number taken is not known until the
        run ends -- the planner may stop early -- so what is reported is
        the scaffold's length, which is the same quantity the planned
        branch reports.
        """
        return len(self.scaffold)

    # -- what worker.py calls ------------------------------------------
    def observe(self, resolved=None, error=None) -> None:
        """Record the caller-visible result of the item just executed."""
        self._pending = classify_outcome(resolved, error)

    def __iter__(self):
        for base in self.scaffold:
            observation = Observation(
                run_id=self.config.run_id,
                worker_index=self.worker_index,
                step_index=base.execution_index,
                prior_outcomes=tuple(self.observations),
            )
            recorded = self._replay.get((self.worker_index, base.execution_index))
            if recorded is not None:
                action = _action_from_completion(recorded["completion"], base)
            else:
                try:
                    action = _ask(self.planner, observation, self.wrapper, base,
                                  last_outcome=self._pending)
                except CapExceeded as capped:
                    raise AgentRunVoided(capped.reason, capped.detail) from capped
            if isinstance(action, Stop):
                return
            _refuse_amount_drift(action, base, self.wrapper, self.emit)

            # The observation for THIS turn is not known until worker.py has
            # run it. Cleared here so that a crash between yielding and
            # observing leaves `unknown_process_died` rather than the previous
            # turn's result.
            self._pending = UNKNOWN_PROCESS_DIED
            yield replace(base, action=action.action,
                          amount_minor=action.amount_minor)
            # worker.py has called observe() by now, unless it died -- in which
            # case this generator never resumes and nothing is recorded.
            self.observations.append(self._pending or UNKNOWN_PROCESS_DIED)


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
        caps=stage_caps(),
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
        return ToolCall(tool="send_notification", action=STUB_ACTION,
                        amount_minor=amount)


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
        caps=stage_caps(),
    )
    if mode == LIVE:
        from experiments.harness.live_planner import LivePlanner

        planner = LivePlanner(counter=counter)
    else:
        planner = StubPlanner(script=_stub_script(scaffold))
    return agent_worker_items(
        config, worker_index, from_index, planner, wrapper, emit=emit
    )
