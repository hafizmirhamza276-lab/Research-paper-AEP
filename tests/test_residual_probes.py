"""Executable probes for the two reasoned hypotheses in phase-report-1A §F.

Phase 1A recorded two claims that were *derived by reading the code*, not
reproduced.  Phase 1B converts both into executable probes:

* **R1-3 — an AOF rewind can un-fence a lease.**  Confirmed here by a
  deterministic *simulated* rewind.  There is no local fix (the fix is
  consensus/HA, an explicit non-claim), so it stays a declared residual window
  in docs/22-formal-model.md with this probe as evidence.
* **R3-5 — escalated records expire.**  Confirmed.  Part of it had a local
  fix — the retention floor did not cover ``PERMANENTLY_AMBIGUOUS`` — which is
  applied; the remaining finite-retention behaviour stays a declared residual.
"""

from __future__ import annotations

import uuid

import pytest

from src.core.exceptions import LockAcquisitionError, StaleWriteError
from src.core.intents import (
    MINIMUM_UNRESOLVED_TTL_SECONDS,
    IntentAuditEntry,
    IntentInvariantError,
    IntentLedgerStore,
    IntentRecord,
    IntentStatus,
    Phase2ExecutionState,
    evidence_hash,
)
from src.core.storage import (
    PHASE2_MANAGED_MARKER,
    AEPExecutionState,
    AEPStatus,
)
from tests.recovery_helpers import seed_stale_about_to_fire


# ---------------------------------------------------------------------------
# R1-3 — AOF rewind un-fencing a lease
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_probe_simulated_aof_rewind_unfences_a_stale_writer(
    redis_client, storage_adapter, lock_manager
):
    """Both CAS conjuncts become satisfiable again after a state+lock rewind.

    This probe does not crash Redis.  It restores the exact bytes of the state
    key and the lock key to an earlier point, which is what an AOF replay that
    lost the intervening writes produces.  It therefore establishes the
    *protocol* consequence deterministically; the wall-clock probability of the
    loss itself is a separate question measured by
    ``tests/aof_rewind_probe.py``.
    """

    execution_id = str(uuid.uuid4())
    state_key = f"aep:state:{execution_id}"
    lock_key = f"aep:lock:{execution_id}"

    # Worker A takes the lease and establishes version 1.
    token_a = await lock_manager.acquire_lock(execution_id, ttl_seconds=60)
    assert token_a
    await storage_adapter.save_state(
        AEPExecutionState(execution_id=execution_id, status=AEPStatus.IDLE),
        expected_version=0,
        lock_token=token_a,
        ttl_seconds=3600,
    )

    # The exact bytes an AOF replay would restore if it lost what follows.
    rewind_state = await redis_client.get(state_key)
    rewind_lock = await redis_client.get(lock_key)
    assert rewind_lock == token_a

    # Worker A finishes; worker B takes over and advances to version 2.
    assert await lock_manager.release_lock(execution_id, token_a)
    token_b = await lock_manager.acquire_lock(execution_id, ttl_seconds=60)
    assert token_b and token_b != token_a
    await storage_adapter.save_state(
        AEPExecutionState(
            execution_id=execution_id, status=AEPStatus.PROCESSING, version=2
        ),
        expected_version=1,
        lock_token=token_b,
        ttl_seconds=3600,
    )

    # Worker A is now correctly fenced on BOTH conjuncts.
    with pytest.raises((StaleWriteError, LockAcquisitionError)):
        await storage_adapter.save_state(
            AEPExecutionState(
                execution_id=execution_id, status=AEPStatus.FAILED, version=2
            ),
            expected_version=1,
            lock_token=token_a,
            ttl_seconds=3600,
        )

    # --- simulate the AOF rewind: the two writes above are lost -------------
    await redis_client.set(state_key, rewind_state, ex=3600)
    await redis_client.set(lock_key, rewind_lock, ex=60)

    # Worker A's identical, previously-fenced write is now accepted.
    await storage_adapter.save_state(
        AEPExecutionState(
            execution_id=execution_id, status=AEPStatus.FAILED, version=2
        ),
        expected_version=1,
        lock_token=token_a,
        ttl_seconds=3600,
    )
    restored = await storage_adapter.get_state(execution_id)
    assert restored is not None
    assert restored.version == 2
    assert restored.status is AEPStatus.FAILED, (
        "R1-3 confirmed: a rewind of both the version and the lease makes a "
        "previously fenced writer valid again"
    )


@pytest.mark.asyncio
async def test_probe_lock_keys_are_not_covered_by_the_durability_barrier(
    redis_client, lock_manager
):
    """The mechanism behind R1-3: lease writes are ordinary, unbarriered SETs."""

    import pathlib

    source = pathlib.Path("src/core/locks.py").read_text(encoding="utf-8")
    assert "WAITAOF" not in source
    assert "confirm_durable" not in source

    execution_id = str(uuid.uuid4())
    token = await lock_manager.acquire_lock(execution_id, ttl_seconds=60)
    assert token
    # Nothing about the lease write is fsync-acknowledged before it is used.
    assert await redis_client.get(f"aep:lock:{execution_id}") == token


# ---------------------------------------------------------------------------
# R3-5 — escalated records expiring at TTL
# ---------------------------------------------------------------------------


async def _escalate_to_permanently_ambiguous(
    redis_client, lock_manager, *, ttl_seconds: int
):
    """Drive one seeded intent FIRED_UNCONFIRMED -> PERMANENTLY_AMBIGUOUS."""

    execution_id, intent_id, _ = await seed_stale_about_to_fire(
        redis_client,
        lock_manager,
        status=IntentStatus.FIRED_UNCONFIRMED,
        reconciliation={"attempt_count": 0, "next_check_at": 0.0},
    )
    store = IntentLedgerStore(redis_client)
    token = await lock_manager.acquire_lock(execution_id, ttl_seconds=60)
    assert token
    current = await store.get_execution(execution_id)
    assert current is not None
    old = current.intent_ledger[intent_id]
    now = await store.redis_time()
    audit = IntentAuditEntry(
        old_state=old.status.value,
        new_state=IntentStatus.PERMANENTLY_AMBIGUOUS,
        redis_time=now,
        actor="probe",
        reason="probe-escalation",
        evidence_hash=evidence_hash({"class": "UNKNOWN"}),
    )
    updated = IntentRecord.model_validate(
        {
            **old.model_dump(),
            "status": IntentStatus.PERMANENTLY_AMBIGUOUS,
            "transitions": [
                *[item.model_dump() for item in old.transitions],
                audit.model_dump(),
            ],
        }
    )
    candidate = Phase2ExecutionState.model_validate(
        {
            **current.model_dump(),
            "intent_ledger": {intent_id: updated.model_dump()},
            "phase2_managed": PHASE2_MANAGED_MARKER,
            "version": current.version + 1,
            "status": AEPStatus.PAUSED,
            "updated_at": now,
        }
    )
    await store.commit_transition(
        candidate,
        intent_id=intent_id,
        old_status=old.status.value,
        new_status=IntentStatus.PERMANENTLY_AMBIGUOUS,
        expected_version=current.version,
        lock_token=token,
        ttl_seconds=ttl_seconds,
    )
    return execution_id, intent_id


@pytest.mark.asyncio
async def test_probe_escalated_record_retention_is_finite(
    redis_client, storage_adapter, lock_manager
):
    """R3-5 confirmed: escalation sets a finite TTL, it does not pin the record."""

    execution_id, intent_id = await _escalate_to_permanently_ambiguous(
        redis_client, lock_manager, ttl_seconds=MINIMUM_UNRESOLVED_TTL_SECONDS
    )
    store = IntentLedgerStore(redis_client)
    state = await store.get_execution(execution_id)
    assert state is not None
    assert (
        state.intent_ledger[intent_id].status
        is IntentStatus.PERMANENTLY_AMBIGUOUS
    )

    ttl = await redis_client.ttl(f"aep:state:{execution_id}")
    # A positive, bounded TTL: the escalated record is retained, then evicted.
    assert 0 < ttl <= MINIMUM_UNRESOLVED_TTL_SECONDS, (
        "R3-5 confirmed: an escalated record is retained for a bounded window "
        "and is then deleted by Redis rather than kept until an operator acts"
    )


@pytest.mark.asyncio
async def test_sub_retention_ttl_is_refused_for_an_escalated_record(
    redis_client, storage_adapter, lock_manager
):
    """Local fix for R3-5: the retention floor must cover PERMANENTLY_AMBIGUOUS.

    Before Phase 1B the Lua applied its 31-day floor only while an intent was
    ABOUT_TO_FIRE or FIRED_UNCONFIRMED, so the very write that escalated an
    intent could also shorten its retention to one second.
    """

    with pytest.raises(IntentInvariantError):
        await _escalate_to_permanently_ambiguous(
            redis_client, lock_manager, ttl_seconds=1
        )
