"""The planner seam, and the controls that bound what it can spend.

Phase 40's pre-registration (`prompts/phase-40-agent-reachability.md`) fixes the
design this implements. Nothing here talks to a network: `StubPlanner` answers
from a canned script, and the live Azure path is deliberately absent until the
stage criteria for stub mode pass.

**The caps are the point of this module.** They are what stands between an
operator and an unbounded bill, so they are enforced here rather than in the
caller: a planner cannot issue a call except through :class:`CallWrapper`, and
the wrapper counts, caps and prices every attempt before it returns.

**Counting happens at the transport layer, not the SDK method.** An SDK retries
429s and timeouts *inside* one `responses.create()`, so a counter wrapped around
that method sees one call where three were billed. :meth:`CallWrapper.attempt`
is therefore the unit, and a live transport will call it per HTTP attempt. Stub
mode has nothing to retry, but it runs through the same counting path, because
a control first exercised in live mode has not been tested.

**The cumulative counter is on disk.** In memory it would reset on a
crash-restart loop, which is precisely the failure the per-collection cap exists
to bound, and the bound would be worthless.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence

#: Written into every transcript entry. Bumping it says previously recorded
#: transcripts are not comparable to new ones.
TRANSCRIPT_SCHEMA_VERSION = "aep.agent.transcript/1"


class PlannerOutcome(str, Enum):
    """What a single planner attempt produced.

    ``FILTERED`` is its own outcome and is never folded into a protocol
    outcome. Azure filters requests and responses by default; a filter block
    counted as declared ambiguity would read as protocol behaviour in the data
    and would inflate exactly the metric this paper is most careful about.
    """

    OK = "OK"
    FILTERED = "PLANNER_FILTERED"
    MALFORMED = "PLANNER_MALFORMED"
    RETRY = "PLANNER_RETRY"


class VoidReason(str, Enum):
    """Why a run stopped being a result.

    A voided run is not a measurement. It is recorded, it is not analysed, and
    it is never counted toward a rate -- the precedent is
    ``results/voided/README.md`` and phase 22's ``ABORTED.md``.
    """

    PER_RUN_CALL_CAP = "VOID_PER_RUN_CALL_CAP"
    COLLECTION_CALL_CAP = "VOID_COLLECTION_CALL_CAP"
    PLANNER_FILTERED = "VOID_PLANNER_FILTERED"


class CapExceeded(RuntimeError):
    """Raised when a cap fires. Carries the reason the run is voided under."""

    def __init__(self, reason: VoidReason, detail: str):
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Price:
    """USD per one million tokens.

    Defaults are Azure Global Standard for GPT-5.6 Luna short context, read
    2026-09-17. Reasoning tokens bill as output, which is why ``effort`` is
    pinned low in the pre-registration and why :meth:`Usage.output` adds them.
    """

    input_per_million: float = 0.20
    output_per_million: float = 1.20

    def usd(self, prompt_tokens: int, output_tokens: int) -> float:
        return (
            prompt_tokens * self.input_per_million
            + output_tokens * self.output_per_million
        ) / 1_000_000


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def output(self) -> int:
        """Reasoning tokens bill as output. Counting them apart would understate."""
        return self.completion_tokens + self.reasoning_tokens


# ---------------------------------------------------------------------------
# Caps
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Caps:
    """The five controls, with the pre-registration's numbers as defaults."""

    per_run_calls: int = 36
    per_collection_calls: int = 1000
    max_output_tokens: int = 1024
    #: Not a cap on spend directly -- the call caps bound that -- but a
    #: belt-and-braces ceiling an operator can lower without touching code.
    per_collection_usd: float = 20.0


class CumulativeCounter:
    """The collection-wide call and cost counter, persisted to disk.

    Written with a temp file and ``os.replace`` so a crash between writes
    leaves either the old state or the new one, never a truncated file. A
    counter that could be read back as zero after a crash would let a
    restart loop spend without bound.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"calls": 0, "usd": 0.0, "runs": 0, "voided": 0}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Unreadable is not zero. Refusing here is the safe direction: the
            # alternative is a corrupt file reading as "nothing spent yet".
            raise CapExceeded(
                VoidReason.COLLECTION_CALL_CAP,
                f"cumulative counter at {self.path} is unreadable; refusing to "
                "treat that as zero spend",
            )
        for key, default in (("calls", 0), ("usd", 0.0), ("runs", 0),
                             ("voided", 0)):
            data.setdefault(key, default)
        return data

    def write(self, state: dict[str, Any]) -> None:
        handle, tmp = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".counter-", suffix=".json"
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2, sort_keys=True)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def add(self, calls: int, usd: float) -> dict[str, Any]:
        state = self.read()
        state["calls"] += calls
        state["usd"] += usd
        self.write(state)
        return state


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------

#: The fourteen fields the pre-registration requires of every entry, in the
#: order they are written. Named as a constant so a test can assert the set
#: rather than a reader trusting the writer.
TRANSCRIPT_FIELDS = (
    "run_id",
    "worker_index",
    "step_index",
    "attempt",
    "prompt",
    "completion",
    "model",
    "snapshot",
    "deployment",
    "api_version",
    "reasoning_effort",
    "sampling",
    "usage",
    "outcome",
)


@dataclass(frozen=True)
class TranscriptEntry:
    run_id: str
    worker_index: int
    step_index: int
    attempt: int
    prompt: str
    completion: str
    model: str
    snapshot: str
    deployment: str
    api_version: str
    reasoning_effort: str
    sampling: dict[str, Any]
    usage: Usage
    outcome: PlannerOutcome

    def echo(self) -> dict[str, Any]:
        return {
            "schema_version": TRANSCRIPT_SCHEMA_VERSION,
            "run_id": self.run_id,
            "worker_index": self.worker_index,
            "step_index": self.step_index,
            "attempt": self.attempt,
            "prompt": self.prompt,
            "completion": self.completion,
            "model": self.model,
            "snapshot": self.snapshot,
            "deployment": self.deployment,
            "api_version": self.api_version,
            "reasoning_effort": self.reasoning_effort,
            "sampling": dict(self.sampling),
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "reasoning_tokens": self.usage.reasoning_tokens,
            },
            "outcome": self.outcome.value,
        }


class Transcript:
    """Append-only record of every attempt, and the only replay mechanism.

    ``docs/33`` §3.3: a model call cannot be recomputed from a seed, so a
    respawned worker reads this rather than calling the model again. That is
    correctness *and* cost -- a respawn that re-called would double the bill of
    every crashed run.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: TranscriptEntry) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.echo(), sort_keys=True) + "\n")

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def replay_index(self) -> dict[tuple[int, int], dict[str, Any]]:
        """The last OK attempt per (worker, step) -- what a respawn reads.

        Last rather than first: a step whose first attempt was malformed and
        whose second succeeded must replay the completion that was acted on.
        """
        index: dict[tuple[int, int], dict[str, Any]] = {}
        for entry in self.entries():
            if entry.get("outcome") == PlannerOutcome.OK.value:
                index[(entry["worker_index"], entry["step_index"])] = entry
        return index


# ---------------------------------------------------------------------------
# The planner seam
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Observation:
    """What a real caller would have: the protocol's own declared results.

    ``docs/33`` §1.4: the planner never sees the oracle. If it could, what is
    measured would be the oracle rather than the protocol.
    """

    run_id: str
    worker_index: int
    step_index: int
    prior_outcomes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolCall:
    """The planner's whole action space.

    ``target`` is absent on purpose. Phase 40 keeps it harness-assigned, which
    is what leaves the duplicate metric sound and removes the WS-1a
    prerequisite. A planner that could choose a target could collide two
    executions onto one resource.
    """

    tool: str
    action: str
    amount_minor: int


@dataclass(frozen=True)
class Stop:
    reason: str = "planner stopped"


class Planner(Protocol):
    def next_action(self, observation: Observation) -> ToolCall | Stop: ...


@dataclass
class StubPlanner:
    """A canned-response planner. Zero cost, no network, no key.

    The script is a sequence of responses per step. ``FILTERED`` and
    ``MALFORMED`` are expressible so those paths are exercised in stub mode
    rather than first met in live mode.
    """

    script: Sequence[tuple[PlannerOutcome, Any]]
    model: str = "stub"
    snapshot: str = "stub-0"
    deployment: str = "stub"
    api_version: str = "stub"
    reasoning_effort: str = "low"
    usage: Usage = field(default_factory=lambda: Usage(1200, 60, 740))
    _cursor: int = 0

    def _next(self) -> tuple[PlannerOutcome, Any]:
        if self._cursor >= len(self.script):
            return PlannerOutcome.OK, Stop("script exhausted")
        item = self.script[self._cursor]
        self._cursor += 1
        return item

    def next_action(self, observation: Observation) -> ToolCall | Stop:
        outcome, payload = self._next()
        if outcome is PlannerOutcome.OK:
            return payload
        raise PlannerAttemptFailed(outcome, str(payload))


class PlannerAttemptFailed(RuntimeError):
    def __init__(self, outcome: PlannerOutcome, detail: str):
        super().__init__(f"{outcome.value}: {detail}")
        self.outcome = outcome
        self.detail = detail


# ---------------------------------------------------------------------------
# The wrapper
# ---------------------------------------------------------------------------

@dataclass
class RunBudget:
    """Per-run counters, written into the run directory."""

    run_id: str
    calls: int = 0
    usd: float = 0.0
    prompt_tokens: int = 0
    output_tokens: int = 0
    voided: VoidReason | None = None

    def echo(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "calls": self.calls,
            "usd": round(self.usd, 8),
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "voided": self.voided.value if self.voided else None,
        }


class CallWrapper:
    """The single seam every model call passes through.

    One wrapper, counted per *attempt*. A live transport calls
    :meth:`attempt` once per HTTP request, including the SDK's automatic
    retries on 429 and timeout, because a retry that is not counted is a retry
    that is not capped.
    """

    def __init__(
        self,
        run_id: str,
        run_dir: Path,
        cumulative: CumulativeCounter,
        caps: Caps | None = None,
        price: Price | None = None,
    ):
        self.run_id = run_id
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.cumulative = cumulative
        self.caps = caps or Caps()
        self.price = price or Price()
        self.budget = RunBudget(run_id=run_id)
        self.transcript = Transcript(self.run_dir / "planner-transcript.jsonl")
        self._budget_path = self.run_dir / "planner-budget.json"
        self.write_budget()

    # -- counters ----------------------------------------------------------
    def write_budget(self) -> None:
        self._budget_path.write_text(
            json.dumps(self.budget.echo(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def void(self, reason: VoidReason, detail: str) -> None:
        self.budget.voided = reason
        self.write_budget()
        (self.run_dir / "VOID_REASON.md").write_text(
            f"# {reason.value}\n\n{detail}\n\n"
            "This run is not a result. It is recorded and not analysed.\n",
            encoding="utf-8",
        )

    # -- the seam ----------------------------------------------------------
    def attempt(
        self,
        *,
        worker_index: int,
        step_index: int,
        attempt: int,
        prompt: str,
        call,
    ) -> Any:
        """Count, cap, invoke, price, record. In that order.

        Capping *before* invoking is what makes the ceiling real: a cap checked
        afterwards has already paid for the call it refuses.
        """
        if self.budget.calls + 1 > self.caps.per_run_calls:
            self.void(
                VoidReason.PER_RUN_CALL_CAP,
                f"run would make attempt {self.budget.calls + 1}, cap is "
                f"{self.caps.per_run_calls}",
            )
            raise CapExceeded(
                VoidReason.PER_RUN_CALL_CAP,
                f"{self.budget.calls + 1} > {self.caps.per_run_calls}",
            )

        state = self.cumulative.read()
        if state["calls"] + 1 > self.caps.per_collection_calls:
            self.void(
                VoidReason.COLLECTION_CALL_CAP,
                f"collection would make attempt {state['calls'] + 1}, cap is "
                f"{self.caps.per_collection_calls}",
            )
            raise CapExceeded(
                VoidReason.COLLECTION_CALL_CAP,
                f"{state['calls'] + 1} > {self.caps.per_collection_calls}",
            )
        if state["usd"] >= self.caps.per_collection_usd:
            self.void(
                VoidReason.COLLECTION_CALL_CAP,
                f"collection has spent {state['usd']:.4f} USD, ceiling is "
                f"{self.caps.per_collection_usd}",
            )
            raise CapExceeded(
                VoidReason.COLLECTION_CALL_CAP,
                f"{state['usd']:.4f} >= {self.caps.per_collection_usd}",
            )

        outcome = PlannerOutcome.OK
        completion = ""
        result: Any = None
        try:
            result = call(max_output_tokens=self.caps.max_output_tokens)
            completion = repr(result)
        except PlannerAttemptFailed as failure:
            outcome = failure.outcome
            completion = failure.detail
        finally:
            usage = getattr(call, "usage", None) or Usage()
            usd = self.price.usd(usage.prompt_tokens, usage.output)
            self.budget.calls += 1
            self.budget.usd += usd
            self.budget.prompt_tokens += usage.prompt_tokens
            self.budget.output_tokens += usage.output
            self.write_budget()
            self.cumulative.add(1, usd)
            self.transcript.append(
                TranscriptEntry(
                    run_id=self.run_id,
                    worker_index=worker_index,
                    step_index=step_index,
                    attempt=attempt,
                    prompt=prompt,
                    completion=completion,
                    model=getattr(call, "model", "stub"),
                    snapshot=getattr(call, "snapshot", "stub-0"),
                    deployment=getattr(call, "deployment", "stub"),
                    api_version=getattr(call, "api_version", "stub"),
                    reasoning_effort=getattr(call, "reasoning_effort", "low"),
                    sampling=getattr(call, "sampling", {}),
                    usage=usage,
                    outcome=outcome,
                )
            )

        if outcome is PlannerOutcome.FILTERED:
            self.void(
                VoidReason.PLANNER_FILTERED,
                "the provider filtered this request or response. A filter "
                "block is a vendor policy decision, not a protocol outcome, "
                "and is never folded into declared ambiguity.",
            )
            raise CapExceeded(VoidReason.PLANNER_FILTERED, completion)
        if outcome is PlannerOutcome.MALFORMED:
            raise PlannerAttemptFailed(outcome, completion)
        return result
