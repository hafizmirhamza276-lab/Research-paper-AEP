"""B2: CAS-only -- fenced state writes, no write-ahead intent.

PAPER_ROADMAP.md section 3.3. B2 is the ablation that separates AEP's two
protections and shows they are not the same protection.

Its state writes go through ``RedisStorageAdapter.save_state``: the real
expected-version compare-and-swap under a live lock token, the same Lua script
AEP-full's state writes go through, with the same three refusals -- stale
version, corrupt stored payload, lost lock. B2's *state* therefore enjoys P1 in
full, and ``tests/test_b2_cas_only.py`` proves it by watching a stale writer be
refused rather than merged.

Its *external effects* have no protection at all. Nothing is written before the
call, so a crash between transmission and response leaves a fenced, versioned,
perfectly consistent state record that says the execution was ``PROCESSING`` --
and no way to find out whether money moved. Fenced state does not make a
non-idempotent call idempotent, and B2 exists to make that concrete rather than
arguable.

The finer outcome word lives in ``context_data``, which the model documents as
arbitrary agent context. ``AEPStatus`` has no vocabulary for "refused with
evidence" versus "gave up guessing", and collapsing the two would erase exactly
the distinction the metrics need.
"""

from __future__ import annotations

import time
from typing import Any

from aep_core.core.intent_workflow import ConnectorPolicy
from aep_core.core.locks import DistributedLockManager
from aep_core.core.request_binding import EndpointProfile, ExactMutationRequest
from aep_core.core.storage import (
    AEPExecutionState,
    AEPStatus,
    RedisStorageAdapter,
)

from experiments.baselines.common import (
    STATUS_APPLIED,
    acquire_lease_or_wait,
    default_lease_wait_seconds,
    STATUS_FAILED,
    STATUS_REFUSED,
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

SYSTEM = SystemId.B2_CAS_ONLY

DEFAULT_MAX_ATTEMPTS = 3

#: Where B2 keeps the word ``AEPStatus`` has no room for.
CONTEXT_KEY = "b2_outcome"


class CasOnlyRunner(CheckpointMixin):
    """Lease, call, then persist the outcome through the fenced write path."""

    system = SYSTEM

    def __init__(
        self,
        *,
        redis_client,
        lock_manager: DistributedLockManager,
        storage_adapter: RedisStorageAdapter,
        connector: Transmitter,
        profile: EndpointProfile,
        policy: ConnectorPolicy,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        lease_wait_seconds: float | None = None,
        crash_injector: Any = None,
        crash_point_enum: type[Any] | None = None,
        state_ttl_seconds: int = 7 * 24 * 60 * 60,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.redis = redis_client
        self.lock_manager = lock_manager
        self.storage = storage_adapter
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
        self.state_ttl_seconds = state_ttl_seconds

    async def validate_startup(self) -> None:
        if bool(getattr(self.connector, "test_only", False)):
            raise RuntimeError("B2 refuses a test-only connector")

    async def _save(
        self,
        *,
        execution_id: str,
        token: str,
        status: AEPStatus,
        outcome: str,
        attempts: int,
        step_id: str,
    ) -> None:
        current = await self.storage.get_state(execution_id)
        expected_version = current.version if current is not None else 0
        context = dict(current.context_data) if current is not None else {}
        context[CONTEXT_KEY] = {
            "status": outcome,
            "dispatch_attempts": attempts,
            "step_id": step_id,
        }
        await self.storage.save_state(
            AEPExecutionState(
                execution_id=execution_id,
                status=status,
                version=expected_version + 1,
                context_data=context,
                updated_at=time.time(),
            ),
            expected_version=expected_version,
            lock_token=token,
            ttl_seconds=self.state_ttl_seconds,
        )

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

            outcome_word, lifecycle = {
                Verdict.APPLIED: (STATUS_APPLIED, AEPStatus.COMPLETED),
                Verdict.REFUSED: (STATUS_REFUSED, AEPStatus.FAILED),
                Verdict.AMBIGUOUS: (STATUS_FAILED, AEPStatus.FAILED),
            }[verdict]

            await self._save(
                execution_id=execution_id,
                token=token,
                status=lifecycle,
                outcome=outcome_word,
                attempts=attempts,
                step_id=step_id,
            )
            await self._checkpoint("AFTER_RECORD_BEFORE_BARRIER")

            return ExecutionOutcome(
                system=SYSTEM,
                execution_id=execution_id,
                status=outcome_word,
                outcome_class=STATUS_TO_CLASS[outcome_word],
                dispatch_attempts=attempts,
            )
        finally:
            await self.lock_manager.release_lock(execution_id, token)


async def classify(redis_client, execution_id: str) -> ExecutionOutcome:
    """Read B2's fenced state and recover the outcome word from it."""
    storage = RedisStorageAdapter(redis_client)
    try:
        state = await storage.get_state(execution_id)
    except Exception as error:  # noqa: BLE001 -- a corrupt state is a result
        return ExecutionOutcome(
            system=SYSTEM,
            execution_id=execution_id,
            status=f"UNREADABLE:{type(error).__name__}",
            outcome_class=OutcomeClass.UNREADABLE,
        )
    if state is None:
        return ExecutionOutcome(
            system=SYSTEM,
            execution_id=execution_id,
            status="NO_RECORD",
            outcome_class=OutcomeClass.NO_RECORD,
        )

    recorded = state.context_data.get(CONTEXT_KEY)
    if not isinstance(recorded, dict) or recorded.get("status") not in STATUS_TO_CLASS:
        # The state exists but B2 never finished an execution against it --
        # the seeded IDLE record, or a worker that died before the save. Both
        # are "this system has no outcome to report", which is the honest
        # reading and is not the same as a corrupt payload.
        return ExecutionOutcome(
            system=SYSTEM,
            execution_id=execution_id,
            status="NO_RECORD",
            outcome_class=OutcomeClass.NO_RECORD,
        )

    status = str(recorded["status"])
    return ExecutionOutcome(
        system=SYSTEM,
        execution_id=execution_id,
        status=status,
        outcome_class=STATUS_TO_CLASS[status],
        dispatch_attempts=int(recorded.get("dispatch_attempts", 0)),
    )
