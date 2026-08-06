"""B4: a minimal durable-workflow engine, and the duplicate it cannot avoid.

PAPER_ROADMAP.md section 3.3: *"B4: Durable-workflow style -- A minimal
Temporal-like event-sourced re-execution baseline."* The roadmap allows a
qualitative comparison plus a logging micro-benchmark if a real one is too
costly. It was not too costly, and the real one is worth far more, because the
argument this baseline settles is the one a reviewer will raise first: *"isn't
this just durable execution?"*

**The model.** A workflow execution is an append-only history in Redis. Running
it means replaying the history from the beginning: an activity whose completion
is already recorded is not re-run, its recorded result is returned instead.
Anything not recorded is executed for real and appended. Every append is
acknowledged durable through the *same* ``WAITAOF`` barrier AEP-full uses -- B4
is not ablated on durability, and saying so matters, because the difference
this baseline exposes must not be confusable with a weaker ledger.

**Where the duplicate comes from.** Consider the history a crash between
transmission and response leaves: ``activity_scheduled`` is recorded,
``activity_completed`` is not. Replay reaches that point and has to decide what
a scheduled-but-uncompleted activity means. A durable-execution engine's
activity semantics are at-least-once, and its answer is to run the activity
again. It is a correct answer for an idempotent activity and a wrong one here,
and the engine has no way to tell the difference, because the thing it would
need -- whether the provider applied the effect -- is not in its history and
cannot be put there by any amount of logging.

This is precisely the fork AEP takes differently. The same record, in AEP, is
an ``ABOUT_TO_FIRE`` intent, and the protocol's answer is to *reconcile* if the
endpoint permits it and to declare ``PERMANENTLY_AMBIGUOUS`` if it does not --
never to re-run. B4 is therefore the sharpest statement of the contribution:
the write-ahead record is necessary and is not sufficient. What matters is the
policy applied to it.

**Scope, stated plainly.** This is a *minimal* engine: one activity, one
history, no timers, no signals, no queues, no workers pool, no versioning, no
determinism checking. It reproduces the one mechanism under comparison -- durable
history plus replay -- and nothing else. It is not Temporal, it is not
benchmarked as Temporal, and no claim about Temporal's performance is made
from it. What it supports is a claim about *event-sourced re-execution as a
strategy*, which is what the related-work section needs.
"""

from __future__ import annotations

import json
from typing import Any

from aep_core.core.intent_workflow import ConnectorPolicy
from aep_core.core.exceptions import LockAcquisitionError
from aep_core.core.locks import DistributedLockManager
from aep_core.core.request_binding import EndpointProfile, ExactMutationRequest

from experiments.baselines.common import (
    DEFAULT_RECORD_TTL_SECONDS,
    STATUS_APPLIED,
    STATUS_FAILED,
    STATUS_REFUSED,
    STATUS_SCHEDULED,
    STATUS_TO_CLASS,
    CheckpointMixin,
    Transmitter,
    Verdict,
    exact_bytes,
    transmit_once,
)
from experiments.baselines.contract import (
    ExecutionOutcome,
    OutcomeClass,
    SystemId,
)

SYSTEM = SystemId.B4_DURABLE_WORKFLOW

DEFAULT_MAX_ATTEMPTS = 3

#: History event names. Chosen to read like the ones a durable-execution
#: engine writes, because the comparison is with that class of system.
ACTIVITY_SCHEDULED = "activity_scheduled"
ACTIVITY_COMPLETED = "activity_completed"

#: The outcome word an engine records for a completed activity, keyed by the
#: verdict the activity returned.
_VERDICT_STATUS = {
    Verdict.APPLIED: STATUS_APPLIED,
    Verdict.REFUSED: STATUS_REFUSED,
    Verdict.AMBIGUOUS: STATUS_FAILED,
}


def history_key(execution_id: str) -> str:
    return f"aep:b4:history:{execution_id}"


async def read_history(redis_client, execution_id: str) -> list[dict[str, Any]]:
    """The whole history, oldest first. Unparseable entries are surfaced."""
    raw = await redis_client.lrange(history_key(execution_id), 0, -1)
    events: list[dict[str, Any]] = []
    for entry in raw:
        try:
            document = json.loads(entry)
        except (ValueError, TypeError):
            events.append({"event": "unreadable"})
            continue
        events.append(document if isinstance(document, dict) else {"event": "unreadable"})
    return events


class DurableWorkflowRunner(CheckpointMixin):
    """Replay the history; run what is not yet recorded; append what happens."""

    system = SYSTEM

    def __init__(
        self,
        *,
        redis_client,
        lock_manager: DistributedLockManager,
        connector: Transmitter,
        profile: EndpointProfile,
        policy: ConnectorPolicy,
        barrier: Any,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        crash_injector: Any = None,
        crash_point_enum: type[Any] | None = None,
        history_ttl_seconds: int = DEFAULT_RECORD_TTL_SECONDS,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.redis = redis_client
        self.lock_manager = lock_manager
        self.connector = connector
        self.profile = profile
        self.policy = policy
        self.barrier = barrier
        self.max_attempts = max_attempts
        self.crash_injector = crash_injector
        self.crash_point_enum = crash_point_enum
        self.history_ttl_seconds = history_ttl_seconds

    async def validate_startup(self) -> None:
        if bool(getattr(self.connector, "test_only", False)):
            raise RuntimeError("B4 refuses a test-only connector")
        validator = getattr(self.barrier, "validate_startup", None)
        if not callable(validator):
            raise RuntimeError(
                "B4's history must be durable; its barrier has no startup "
                "validation, which would make it a weaker baseline than the "
                "one being claimed"
            )
        await validator(self.redis)

    async def _append(self, execution_id: str, event: dict[str, Any]) -> None:
        """Append one history event and wait for it to be acknowledged durable.

        The append and the acknowledgement share one pinned connection, for
        the same reason ``aep_core`` pins one: ``WAITAOF`` reports on the
        writes of the connection that issues it.
        """
        key = history_key(execution_id)
        async with self.redis.client() as connection:
            await connection.rpush(key, json.dumps(event, sort_keys=True))
            await connection.expire(key, self.history_ttl_seconds)
            durable = await self.barrier.confirm_durable(
                connection, self.policy.durability_timeout_ms
            )
        if not durable:
            raise RuntimeError("B4's history append was not acknowledged durable")

    async def execute(
        self,
        *,
        execution_id: str,
        step_id: str,
        request: ExactMutationRequest,
    ) -> ExecutionOutcome:
        token = await self.lock_manager.acquire_lock(
            execution_id, ttl_seconds=self.policy.lock_ttl_seconds
        )
        if token is None:
            raise LockAcquisitionError(
                f"execution lease unavailable for {execution_id}"
            )
        try:
            await self._checkpoint("BEFORE_ANY_WRITE")
            history = await read_history(self.redis, execution_id)

            completed = [
                event for event in history if event.get("event") == ACTIVITY_COMPLETED
            ]
            if completed:
                # Memoised. This is what durable execution is for, and it
                # works: no bytes reach the provider on a replay past a
                # recorded completion.
                status = str(completed[-1].get("status", STATUS_FAILED))
                return ExecutionOutcome(
                    system=SYSTEM,
                    execution_id=execution_id,
                    status=status,
                    outcome_class=STATUS_TO_CLASS.get(
                        status, OutcomeClass.UNVERIFIED_FAILURE
                    ),
                    dispatch_attempts=0,
                )

            scheduled = [
                event for event in history if event.get("event") == ACTIVITY_SCHEDULED
            ]
            # The fork. A scheduled-but-uncompleted activity is re-run, because
            # at-least-once is the only semantics an engine with no visibility
            # into the provider can offer. See the module docstring.
            attempt_number = len(scheduled) + 1
            await self._append(
                execution_id,
                {
                    "event": ACTIVITY_SCHEDULED,
                    "step_id": step_id,
                    "attempt": attempt_number,
                },
            )
            await self._checkpoint("AFTER_PRE_DISPATCH_RECORD_BEFORE_BARRIER")

            payload = exact_bytes(self.profile, request)
            attempts = 0
            verdict = Verdict.AMBIGUOUS
            for _ in range(self.max_attempts):
                await self._checkpoint("BEFORE_REQUEST_TRANSMISSION")
                attempts += 1
                verdict = await transmit_once(
                    self.connector,
                    exact_request_bytes=payload,
                    client_reference=None,
                    client_timeout=self.policy.client_timeout_seconds,
                )
                await self._checkpoint("AFTER_RESPONSE_BEFORE_RECORD")
                if verdict is not Verdict.AMBIGUOUS:
                    break

            status = _VERDICT_STATUS[verdict]
            await self._append(
                execution_id,
                {
                    "event": ACTIVITY_COMPLETED,
                    "step_id": step_id,
                    "attempt": attempt_number,
                    "status": status,
                    "dispatch_attempts": attempts,
                },
            )
            await self._checkpoint("AFTER_RECORD_BEFORE_BARRIER")

            return ExecutionOutcome(
                system=SYSTEM,
                execution_id=execution_id,
                status=status,
                outcome_class=STATUS_TO_CLASS[status],
                dispatch_attempts=attempts,
            )
        finally:
            await self.lock_manager.release_lock(execution_id, token)


async def classify(redis_client, execution_id: str) -> ExecutionOutcome:
    """What B4's history says about one execution.

    A history that stops at ``activity_scheduled`` is reported as
    ``SCHEDULED`` -- an unverified failure, not a declared ambiguity. The
    distinction is the whole point of this baseline: B4 *has* the record, and
    its own semantics say the record means "run it again", so nothing in B4
    ever escalates it to an operator.
    """
    events = await read_history(redis_client, execution_id)
    if not events:
        return ExecutionOutcome(
            system=SYSTEM,
            execution_id=execution_id,
            status="NO_RECORD",
            outcome_class=OutcomeClass.NO_RECORD,
        )
    if any(event.get("event") == "unreadable" for event in events):
        return ExecutionOutcome(
            system=SYSTEM,
            execution_id=execution_id,
            status="UNREADABLE",
            outcome_class=OutcomeClass.UNREADABLE,
        )

    completed = [event for event in events if event.get("event") == ACTIVITY_COMPLETED]
    if completed:
        status = str(completed[-1].get("status", STATUS_FAILED))
        return ExecutionOutcome(
            system=SYSTEM,
            execution_id=execution_id,
            status=status,
            outcome_class=STATUS_TO_CLASS.get(
                status, OutcomeClass.UNVERIFIED_FAILURE
            ),
            dispatch_attempts=int(completed[-1].get("dispatch_attempts", 0)),
        )
    return ExecutionOutcome(
        system=SYSTEM,
        execution_id=execution_id,
        status=STATUS_SCHEDULED,
        outcome_class=STATUS_TO_CLASS[STATUS_SCHEDULED],
        dispatch_attempts=0,
    )
