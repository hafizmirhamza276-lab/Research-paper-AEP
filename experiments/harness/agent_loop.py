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


def planner_mode() -> str:
    """Which branch the worker takes. Defaults to the path that has data."""
    return (os.environ.get(PLANNER_MODE_ENV) or SCRIPTED).strip().lower()


def is_agent_mode() -> bool:
    return planner_mode() not in ("", SCRIPTED)


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

        decided.append(
            replace(base, action=action.action, amount_minor=action.amount_minor)
        )
        # What this planner decided, not what happened to it: the loop
        # plans before it executes. Amendment 2 §5.
        outcomes.append(f"{action.action} {action.amount_minor}")

    return tuple(decided)


def _ask(
    planner: Planner,
    observation: Observation,
    wrapper: CallWrapper,
    base: WorkloadItem,
) -> ToolCall | Stop:
    """One decision, through the wrapper, with one retry on a malformed reply."""
    prompt = _prompt_for(observation, base)
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


def _prompt_for(observation: Observation, base: WorkloadItem) -> str:
    """What the planner is shown. The oracle is not in it, by construction."""
    if planner_mode() == LIVE:
        from experiments.harness.live_planner import build_prompt

        # The amount is the work the harness assigned; the planner still
        # chooses the action and whether to act at all.
        return build_prompt(observation, base.target, base.amount_minor)
    return (
        f"run={observation.run_id} worker={observation.worker_index} "
        f"step={observation.step_index} "
        f"prior={','.join(observation.prior_outcomes) or 'none'} "
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


def agent_items_for_worker(config, worker_index: int, from_index: int):
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
        config, worker_index, from_index, planner, wrapper
    )
