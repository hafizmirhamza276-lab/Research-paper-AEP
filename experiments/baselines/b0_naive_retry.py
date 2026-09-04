"""B0: naive retry -- what most agent frameworks do today.

PAPER_ROADMAP.md section 3.3: *"No lease, no CAS, retry-on-timeout."*

The whole system is: build the request, send it, and if the answer was not
definitive, send it again. When the attempts run out, write down "failed" and
move on. There is no lease, no version, no record of the intent to call, and no
reconciliation -- there is nothing to reconcile *with*, because nothing was
written before the call.

Three properties of this code are load-bearing for the evaluation and each is
asserted by a test rather than promised here.

**The retries are the same mutation.** Every attempt transmits the identical
bytes, so the oracle's Definition 1 gives them one fingerprint and counts the
extra applications as duplicates. A baseline that varied an identity field per
attempt would report a duplicate rate of zero while duplicating every time.

**No client reference is sent.** A stable identifier that would let the
provider recognise the resend is exactly what a pre-dispatch record is for, and
B0 has none: an identifier held only in this process's memory does not survive
the process. Sending none is the honest model, and it is why B0 could not
reconcile even if it wanted to.

**Giving up is not the same as declaring ambiguity.** After the last attempt
B0 writes ``FAILED``. Every one of those attempts may have applied. The record
is a guess, and it is indistinguishable -- to an operator reading B0's own
state -- from a genuine refusal. The metrics call it ``UNVERIFIED_FAILURE`` and
never ``DECLARED_AMBIGUOUS``, which is the distinction the paper turns on.
"""

from __future__ import annotations

from typing import Any

from aep_core.core.request_binding import EndpointProfile, ExactMutationRequest
from aep_core.core.intent_workflow import ConnectorPolicy

from experiments.baselines.common import (
    DEFAULT_RECORD_TTL_SECONDS,
    STATUS_APPLIED,
    STATUS_FAILED,
    STATUS_REFUSED,
    STATUS_TO_CLASS,
    CheckpointMixin,
    Transmitter,
    Verdict,
    exact_bytes,
    read_outcome_record,
    transmit_once,
    write_outcome_record,
)
from experiments.baselines.contract import ExecutionOutcome, SystemId

SYSTEM = SystemId.B0_NAIVE_RETRY

#: How many times a naive caller sends the same mutation before giving up.
#: Three is the common default in HTTP client libraries and agent frameworks
#: (one attempt plus two retries), and it is recorded in the run config so a
#: reader never has to guess which number produced a duplicate count.
DEFAULT_MAX_ATTEMPTS = 3


def result_key(execution_id: str) -> str:
    return f"aep:b0:result:{execution_id}"


class NaiveRetryRunner(CheckpointMixin):
    """Send; if the answer was not definitive, send again."""

    system = SYSTEM

    def __init__(
        self,
        *,
        redis_client,
        connector: Transmitter,
        profile: EndpointProfile,
        policy: ConnectorPolicy,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        crash_injector: Any = None,
        crash_point_enum: type[Any] | None = None,
        record_ttl_seconds: int = DEFAULT_RECORD_TTL_SECONDS,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.redis = redis_client
        self.connector = connector
        self.profile = profile
        self.policy = policy
        self.max_attempts = max_attempts
        self.crash_injector = crash_injector
        self.crash_point_enum = crash_point_enum
        self.record_ttl_seconds = record_ttl_seconds

    async def validate_startup(self) -> None:
        """The one composition check a baseline can honestly make.

        It refuses a test-only connector for the same reason ``EVALUATION``
        mode does: a number collected against an in-process double is not a
        number about a system that talks to a provider. It cannot check a
        vault, a barrier or a mode, because it has none of them -- that is
        what makes it B0.
        """
        if bool(getattr(self.connector, "test_only", False)):
            raise RuntimeError("B0 refuses a test-only connector")

    async def execute(
        self,
        *,
        execution_id: str,
        step_id: str,
        request: ExactMutationRequest,
    ) -> ExecutionOutcome:
        await self._checkpoint("BEFORE_ANY_WRITE")
        payload = exact_bytes(self.profile, request)

        attempts = 0
        verdict = Verdict.AMBIGUOUS
        for _ in range(self.max_attempts):
            await self._checkpoint("BEFORE_REQUEST_TRANSMISSION")
            attempts += 1
            verdict = await transmit_once(
                self.connector,
                exact_request_bytes=payload,
                # No stable identifier exists to send: see the module
                # docstring. This is the ablation, not an oversight.
                client_reference=None,
# WS-1a instrumentation, sent by every system. It is not a
# client_reference and gives this baseline no capability:
# the provider records it, never returns it, and never uses
# it to decide whether two applications are the same.
                execution_id=execution_id,
                client_timeout=self.policy.client_timeout_seconds,
            )
            await self._checkpoint("AFTER_RESPONSE_BEFORE_RECORD")
            if verdict is not Verdict.AMBIGUOUS:
                break

        status = {
            Verdict.APPLIED: STATUS_APPLIED,
            Verdict.REFUSED: STATUS_REFUSED,
            Verdict.AMBIGUOUS: STATUS_FAILED,
        }[verdict]

        await write_outcome_record(
            self.redis,
            result_key(execution_id),
            status=status,
            dispatch_attempts=attempts,
            ttl_seconds=self.record_ttl_seconds,
            extra={"step_id": step_id},
        )
        await self._checkpoint("AFTER_RECORD_BEFORE_BARRIER")

        return ExecutionOutcome(
            system=SYSTEM,
            execution_id=execution_id,
            status=status,
            outcome_class=STATUS_TO_CLASS[status],
            dispatch_attempts=attempts,
        )


async def classify(redis_client, execution_id: str) -> ExecutionOutcome:
    """What B0's own durable record says about one execution."""
    return await read_outcome_record(
        redis_client,
        result_key(execution_id),
        system=SYSTEM,
        execution_id=execution_id,
    )
