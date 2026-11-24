"""B1: lease-only -- Redis lock, raw SET state, no intent ledger.

PAPER_ROADMAP.md section 3.3. B1 adds exactly one thing to B0: the execution
lease. It is the real :class:`DistributedLockManager` -- the same lock AEP-full
takes, with the same TTL policy -- so B1 genuinely serialises concurrent
workers, and the difference between B0 and B1 in the results is the value of
that serialisation and nothing else.

The lease is a *mutual exclusion* mechanism. It answers "is another live worker
doing this right now?" and it answers that correctly. It does not answer, and
cannot answer, "did the worker that just died already send the request?" --
because it is released, or expires, without leaving any trace of what its
holder was doing. The state B1 writes is a raw ``SET``: no fencing counter, no
expected version, and written only after the call has returned.
"""

from __future__ import annotations

from typing import Any

from aep_core.core.intent_workflow import ConnectorPolicy
from aep_core.core.locks import DistributedLockManager
from aep_core.core.request_binding import EndpointProfile, ExactMutationRequest

from experiments.baselines.common import (
    DEFAULT_RECORD_TTL_SECONDS,
    acquire_lease_or_wait,
    default_lease_wait_seconds,
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

SYSTEM = SystemId.B1_LEASE_ONLY

DEFAULT_MAX_ATTEMPTS = 3


def state_key(execution_id: str) -> str:
    """B1's own state key.

    Deliberately not ``aep:state:{id}``: that key is owned by the CAS write
    path, and a raw ``SET`` into it would be refused by the Lua script rather
    than demonstrating what an unfenced write does. B1's point is that its
    state is unfenced, so it keeps its state where an unfenced write is
    possible, and the results say so.
    """
    return f"aep:b1:state:{execution_id}"


class LeaseOnlyRunner(CheckpointMixin):
    """Take the lease, call, write the result, release the lease."""

    system = SYSTEM

    def __init__(
        self,
        *,
        redis_client,
        lock_manager: DistributedLockManager,
        connector: Transmitter,
        profile: EndpointProfile,
        policy: ConnectorPolicy,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        lease_wait_seconds: float | None = None,
        crash_injector: Any = None,
        crash_point_enum: type[Any] | None = None,
        record_ttl_seconds: int = DEFAULT_RECORD_TTL_SECONDS,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.redis = redis_client
        self.lock_manager = lock_manager
        self.connector = connector
        self.profile = profile
        self.policy = policy
        self.max_attempts = max_attempts
        self.lease_wait_seconds = (
            default_lease_wait_seconds(policy)
            if lease_wait_seconds is None
            else float(lease_wait_seconds)
        )
        self.crash_injector = crash_injector
        self.crash_point_enum = crash_point_enum
        self.record_ttl_seconds = record_ttl_seconds

    async def validate_startup(self) -> None:
        if bool(getattr(self.connector, "test_only", False)):
            raise RuntimeError("B1 refuses a test-only connector")

    async def execute(
        self,
        *,
        execution_id: str,
        step_id: str,
        request: ExactMutationRequest,
    ) -> ExecutionOutcome:
        # Waits for a lease a dead worker still holds. See
        # experiments/baselines/tests/test_lease_waiting.py: giving up here
        # would credit the lease with preventing a duplicate it only delays.
        token, lease_wait_seconds = await acquire_lease_or_wait(
            self.lock_manager,
            execution_id,
            ttl_seconds=self.policy.lock_ttl_seconds,
            wait_seconds=self.lease_wait_seconds,
        )
        try:
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
                    client_reference=None,
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
                state_key(execution_id),
                status=status,
                dispatch_attempts=attempts,
                ttl_seconds=self.record_ttl_seconds,
                extra={
                    "step_id": step_id,
                    # A measured quantity, not bookkeeping: this is what the
                    # lease cost this execution under a crash.
                    "lease_wait_seconds": round(lease_wait_seconds, 3),
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
    return await read_outcome_record(
        redis_client,
        state_key(execution_id),
        system=SYSTEM,
        execution_id=execution_id,
    )
