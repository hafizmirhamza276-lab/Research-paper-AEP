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
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence

#: Written into every transcript entry. Bumping it says previously recorded
#: transcripts are not comparable to new ones.
#:
#: /2 -> /3 adds ``timestamp``. Section 5 of the pre-registration always
#: required a wall-clock timestamp and no entry carried one, which
#: ``reports/phase-report-40-stage-10-2026-09-21.md`` §5.1 found. The two
#: archived live collections are ``/2`` and stay that way; they cannot be
#: stamped after the fact, and inventing a time for them would be worse than
#: the gap.
TRANSCRIPT_SCHEMA_VERSION = "aep.agent.transcript/3"


def utc_now() -> str:
    """UTC, ISO-8601, millisecond resolution, explicit ``Z``.

    Millisecond rather than second resolution because two attempts on the same
    step can land inside one second on a retry, and a timestamp that cannot
    order them is not much better than none.
    """
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


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
    #: The planner returned an amount other than the one the harness assigned
    #: for that execution. ``fingerprint.py``'s identity function includes
    #: ``amount_minor``, so an agent free to invent amounts is deciding a term
    #: the measurement is computed from: two executions the harness meant to be
    #: distinct could be made identical, or one duplicate pair made to look
    #: like two separate effects. Treated exactly as a content filter is --
    #: a distinct void class, never folded into a normal mutation.
    PLANNER_AMOUNT_MISMATCH = "VOID_PLANNER_AMOUNT_MISMATCH"


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
    #: The input bound section 3's ceiling is already calculated from
    #: ("1 000 attempts x (<=2 000 input + <=1 024 output)"). Named here
    #: because the reservation below has to price a call it has not made yet,
    #: and the only safe price is the largest one the pre-registration allows.
    max_prompt_tokens: int = 2000
    #: Not a cap on spend directly -- the call caps bound that -- but a
    #: belt-and-braces ceiling an operator can lower without touching code.
    per_collection_usd: float = 20.0


class CumulativeCounter:
    """The collection-wide call and cost counter. **This is the budget control.**

    The per-collection call cap and the USD ceiling
    (``prompts/phase-40-agent-reachability.md`` §3) are both enforced from this
    number, so an undercount is not a reporting error -- it is a ceiling that
    does not exist.

    **What the first implementation got wrong.** It kept one JSON file and did
    ``read`` then ``write``. ``os.replace`` made each *write* atomic, so the
    file was always well-formed; nothing made the *read-modify-write* atomic,
    and nothing anywhere took a lock. Measured on this host, the loss is not a
    narrow race that a bigger machine would hide: concurrent writers advance
    the counter by roughly one per round, so the loss is systematically
    ``(writers - 1) / writers``. At the two workers the harness actually runs,
    two writers x 60 increments counted 69 of 120.

    **What this one does instead.** One append-only journal line per increment.
    A single ``os.write`` to a file opened ``O_APPEND`` is atomic on both
    filesystems the harness can land on -- verified on this host at 800
    concurrent 201-byte appends, all intact, on DrvFs and on ext4 -- so two
    writers cannot interleave within a line and neither can overwrite the
    other's. The total is the sum of the journal.

    Why not a lock. ``fcntl.flock`` does work here, across processes, on both
    filesystems. It was not chosen because it only moves the problem: a writer
    holding the lock and then killed between its read and its write still loses
    its increment, and the harness injects ``SIGKILL`` by design. An append has
    no window to be killed in. It is also the idiom the rest of this repository
    already uses for exactly this reason -- every event log here is a jsonl
    append.

    **Idempotency.** Each line carries a ``key``. The total counts a key once
    however many times it is appended, which is what makes "none
    double-counted" mechanical rather than a promise about call sites.

    **A partial line is refused, not dropped.** It can only come from a process
    killed mid-append. Dropping it would undercount and counting it would
    invent a number, so ``read`` raises -- the same stance the first
    implementation already took for an unreadable file, and for the same
    reason.

    ``planner-cumulative.json`` is still written, and is now **derived**: a
    snapshot for a human watching a collection. It is re-derived in full on
    every append, so a clobbered one self-heals and none of the caps ever read
    it.
    """

    #: An append is atomic up to a limit; past it the guarantee lapses. Refuse
    #: rather than trust that a key can never grow. PIPE_BUF is 4096 on Linux;
    #: this leaves an order of magnitude of headroom.
    MAX_LINE = 512

    def __init__(self, path: Path):
        self.path = Path(path)
        self.journal = self.path.with_suffix(".jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # -- reading -----------------------------------------------------------
    def _lines(self) -> list[dict[str, Any]]:
        if not self.journal.is_file():
            return []
        try:
            raw = self.journal.read_text(encoding="utf-8")
        except OSError as exc:
            raise CapExceeded(
                VoidReason.COLLECTION_CALL_CAP,
                f"cumulative journal at {self.journal} is unreadable "
                f"({exc}); refusing to treat that as zero spend",
            ) from exc
        entries: list[dict[str, Any]] = []
        for number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CapExceeded(
                    VoidReason.COLLECTION_CALL_CAP,
                    f"cumulative journal at {self.journal} line {number} is "
                    f"malformed ({exc}); a partial line means a writer was "
                    f"killed mid-append. Refusing: dropping it would "
                    f"undercount and counting it would invent a number. "
                    f"Reconcile against the run transcripts.",
                ) from exc
            if not isinstance(entry, dict) or "key" not in entry:
                raise CapExceeded(
                    VoidReason.COLLECTION_CALL_CAP,
                    f"cumulative journal at {self.journal} line {number} is "
                    f"not a keyed entry; refusing to guess what it counted",
                )
            entries.append(entry)
        return entries

    def has_key(self, key: str) -> bool:
        """Is this reservation already durably on disk?

        Read from the file, not from memory. The live client calls this
        immediately before dispatching, so that "counted before it is made" is
        a property the request cannot get around rather than an ordering a
        later edit could quietly invert.
        """
        return any(entry["key"] == key for entry in self._lines())

    def read(self) -> dict[str, Any]:
        """Aggregate the journal. Absent is the only thing that reads as zero."""
        seen: dict[str, dict[str, Any]] = {}
        for entry in self._lines():
            # First write wins. A later line with the same key is the same
            # call reported again, not a second call.
            seen.setdefault(entry["key"], entry)
        calls = sum(int(e.get("calls", 0)) for e in seen.values())
        usd = sum(float(e.get("usd", 0.0)) for e in seen.values())
        runs = {e["run_id"] for e in seen.values() if e.get("run_id")}
        voided = {e["run_id"] for e in seen.values()
                  if e.get("run_id") and e.get("voided")}
        return {
            "calls": calls,
            "usd": usd,
            # Derived, so it cannot drift: runs that made at least one call,
            # and of those the ones that stopped being results.
            "runs": len(runs),
            "voided": len(voided),
        }

    # -- writing -----------------------------------------------------------
    def write(self, state: dict[str, Any]) -> None:
        """Write the derived snapshot. Never the authority; never read back."""
        payload = dict(state)
        payload["_derived_from"] = self.journal.name
        payload["_authoritative"] = False
        handle, tmp = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".counter-", suffix=".json"
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def add(
        self,
        calls: int,
        usd: float,
        *,
        key: str,
        run_id: str | None = None,
        voided: bool = False,
    ) -> dict[str, Any]:
        """Append one increment, durably, before returning.

        ``fsync`` before returning is the whole contract: a caller that reserves
        a call and is then killed must find that reservation on disk. The
        reservation is made *before* the call is dispatched, so the direction of
        any error is over-counting -- stopping a collection early -- and never
        the direction that spends money nobody counted.
        """
        entry = {
            "key": key,
            "calls": int(calls),
            "usd": float(usd),
        }
        if run_id is not None:
            entry["run_id"] = run_id
        if voided:
            entry["voided"] = True
        line = json.dumps(entry, sort_keys=True) + "\n"
        encoded = line.encode("utf-8")
        if len(encoded) > self.MAX_LINE:
            raise ValueError(
                f"journal line is {len(encoded)} bytes, too long to append "
                f"atomically (limit {self.MAX_LINE}); shorten the key"
            )
        descriptor = os.open(
            self.journal, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644
        )
        try:
            written = os.write(descriptor, encoded)
            if written != len(encoded):
                raise OSError(
                    f"short append: {written} of {len(encoded)} bytes"
                )
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

        state = self.read()
        try:
            self.write(state)
        except OSError:
            # The snapshot is a convenience. Failing to refresh it must not
            # fail a call that is already durably counted.
            pass
        return state


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------

#: The fields the pre-registration requires of every entry, in the order they
#: are written. Named as a constant so a test can assert the set rather than a
#: reader trusting the writer.
TRANSCRIPT_FIELDS = (
    "run_id",
    "worker_index",
    "step_index",
    "attempt",
    "timestamp",
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
    "served_model",
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
    #: What the response reported as its model, which on an AI
    #: Foundry deployment is the alias rather than a version.
    #: Recorded because it cannot be checked -- amendment 1 §5.
    served_model: str | None = None
    #: When this attempt was recorded. Section 5 requires it and no entry
    #: carried one until amendment 5's companion commit.
    #:
    #: It is a default_factory rather than a parameter every caller must pass
    #: because a field that can be forgotten will be: the entry is built in a
    #: ``finally`` block on four different paths. Stamping at construction is
    #: also the most accurate moment available -- the call has just returned.
    #:
    #: Why it matters beyond bookkeeping: amendment 1 records that
    #: auto-upgrade is ON and that "the pinned version can change with no
    #: trace in the data". This is what lets a later reader bound a given call
    #: against a version change, which is the one question amendment 1 says
    #: the paper must be honest about.
    timestamp: str = field(default_factory=utc_now)

    def echo(self) -> dict[str, Any]:
        return {
            "schema_version": TRANSCRIPT_SCHEMA_VERSION,
            "run_id": self.run_id,
            "worker_index": self.worker_index,
            "step_index": self.step_index,
            "attempt": self.attempt,
            "timestamp": self.timestamp,
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
            "served_model": self.served_model,
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

    @classmethod
    def from_transcript(
        cls, run_id: str, transcript: "Transcript", price: "Price"
    ) -> "RunBudget":
        """Rebuild from what was actually recorded, not from zero.

        A respawned worker used to construct a fresh ``RunBudget(calls=0)``,
        and ``CallWrapper.__init__`` wrote it straight over the file the first
        attempt had filled in. Last writer wins and the last writer -- which
        replays and therefore calls nothing -- always had nothing to report, so
        every run's ``planner-budget.json`` read ``calls: 0`` beside a
        transcript holding four entries.

        Worse than the wrong number in a file: the per-run cap was checked
        against that same counter, so a run that respawned got a fresh 36 calls
        per attempt. The transcript is the durable record of what was spent, so
        the budget is derived from it rather than kept in parallel with it.
        """
        budget = cls(run_id=run_id)
        for entry in transcript.entries():
            usage = entry.get("usage") or {}
            prompt_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = int(
                usage.get("completion_tokens", 0)
            ) + int(usage.get("reasoning_tokens", 0))
            if not output_tokens:
                output_tokens = int(usage.get("output_tokens", 0))
            budget.calls += 1
            budget.prompt_tokens += prompt_tokens
            budget.output_tokens += output_tokens
            budget.usd += price.usd(prompt_tokens, output_tokens)
        return budget

    def echo(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "calls": self.calls,
            "usd": round(self.usd, 8),
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "voided": self.voided.value if self.voided else None,
        }


def reservation_key(
    run_id: str, worker_index: int, step_index: int, attempt: int
) -> str:
    """The identity of one counted attempt.

    Named in one place because ``CallWrapper.attempt`` writes it and the live
    client checks for it; two spellings of the same thing would turn the
    dispatch guard into a guard that always refuses, or never does.
    """
    return f"{run_id}:{worker_index}:{step_index}:{attempt}"


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
        self.transcript = Transcript(self.run_dir / "planner-transcript.jsonl")
        # Derived from the transcript, so a respawn resumes the run's budget
        # instead of zeroing it. See RunBudget.from_transcript.
        self.budget = RunBudget.from_transcript(
            run_id, self.transcript, self.price
        )
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
        # Recorded in the journal too, so the collection-level `voided` count
        # is derived from what happened rather than initialised and forgotten.
        try:
            self.cumulative.add(
                0, 0.0, key=f"{self.run_id}:void", run_id=self.run_id,
                voided=True,
            )
        except (OSError, ValueError):
            pass
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

        # Reserve BEFORE dispatching. The docstring above always said "Count,
        # cap, invoke"; the code counted in the `finally`, after the call had
        # returned, so a worker SIGKILLed between the call and the count had
        # made a paid call that nothing recorded. The harness injects SIGKILL
        # by design, so that was not a corner case -- it was the crashed
        # regime, which is the entire experiment.
        #
        # The reservation is priced at the most section 3 allows a single call
        # to cost, because the real cost is not known until the call returns.
        # It is settled below with the difference. Dying in between over-counts
        # the collection, which stops it early; the other order spends money
        # nobody counted.
        reservation = reservation_key(
            self.run_id, worker_index, step_index, attempt
        )
        # The live client re-reads this key from disk and refuses to dispatch
        # without it, so the two sides must agree on the spelling. Named once.
        setattr(call, "reservation_key", reservation)
        self.cumulative.add(
            1,
            self.price.usd(
                self.caps.max_prompt_tokens, self.caps.max_output_tokens
            ),
            key=reservation,
            run_id=self.run_id,
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
            # Settle the reservation: the difference between what was set aside
            # and what the call actually cost. A separate key, so the
            # reservation itself stays idempotent and a replayed settle cannot
            # double-count.
            self.cumulative.add(
                0,
                usd - self.price.usd(
                    self.caps.max_prompt_tokens, self.caps.max_output_tokens
                ),
                key=f"{reservation}:settle",
                run_id=self.run_id,
            )
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
                    served_model=getattr(call, "served_model", None),
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
        if outcome in (PlannerOutcome.MALFORMED, PlannerOutcome.RETRY):
            # RETRY has to raise for the same reason MALFORMED does: the call
            # produced no decision, and `return result` would hand the loop a
            # None to treat as one. _ask retries on PlannerAttemptFailed, so a
            # throttled attempt gets its one retry and then stops the run --
            # both attempts counted, neither uncapped.
            raise PlannerAttemptFailed(outcome, completion)
        return result
