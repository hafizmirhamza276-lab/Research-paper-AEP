"""Redis-backed tests for the Phase 2 typed intent state machine."""

from __future__ import annotations

import uuid

import pytest

from src.core.intents import (
    NONE_STATE,
    IllegalIntentTransitionError,
    IntentInvariantError,
    IntentLedgerStore,
    IntentStatus,
    LEGAL_INTENT_TRANSITIONS,
    Phase2ExecutionState,
    ReconciliationProgress,
    require_legal_intent_transition,
)
from src.core.storage import AEPExecutionState, AEPStatus
from tests.request_binding_helpers import prepared_binding
from src.core.request_binding import canonical_request_binding_bytes


FINGERPRINT = "a" * 64


ALL_CONCEPTUAL_STATES = [NONE_STATE, *(status.value for status in IntentStatus)]
ALL_PERSISTED_STATES = [status.value for status in IntentStatus]
ALL_ILLEGAL_EDGES = [
    (source, target)
    for source in ALL_CONCEPTUAL_STATES
    for target in ALL_PERSISTED_STATES
    if (source, target) not in LEGAL_INTENT_TRANSITIONS
]


@pytest.mark.parametrize(("source", "target"), sorted(LEGAL_INTENT_TRANSITIONS))
def test_transition_table_accepts_every_and_only_legal_edge(source, target):
    require_legal_intent_transition(source, target)


@pytest.mark.parametrize(("source", "target"), ALL_ILLEGAL_EDGES)
def test_transition_table_rejects_every_illegal_edge(source, target):
    with pytest.raises(IllegalIntentTransitionError):
        require_legal_intent_transition(source, target)


async def _seed(storage_adapter, lock_manager):
    execution_id = str(uuid.uuid4())
    token = await lock_manager.acquire_lock(execution_id, ttl_seconds=60)
    assert token is not None
    await storage_adapter.save_state(
        AEPExecutionState(execution_id=execution_id, status=AEPStatus.IDLE),
        expected_version=0,
        lock_token=token,
        ttl_seconds=3600,
    )
    return execution_id, token


async def _create(store, execution_id, token, *, step_id="charge-card"):
    now_ms = int((await store.redis_time()) * 1000)
    binding, intent_id, correlation_id = await prepared_binding(
        execution_id=execution_id,
        step_id=step_id,
        connector_operation="mock.payment.v1/create",
        target="customer-redacted-17",
        created_at_ms=now_ms,
    )
    return await store.create_intent(
        execution_id=execution_id,
        expected_version=1,
        lock_token=token,
        step_id=step_id,
        connector="mock.payment.v1/create",
        target="customer-redacted-17",
        request_fingerprint=binding.request_fingerprint,
        request_binding=binding,
        client_timeout_seconds=1,
        settlement_lag_seconds=0,
        buffer_margin_seconds=15,
        actor="runner:test",
        intent_id=intent_id,
        correlation_id=correlation_id,
    )


@pytest.mark.asyncio
async def test_none_to_about_to_fire(redis_client, storage_adapter, lock_manager):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create(store, execution_id, token)
    state = await store.get_execution(execution_id)
    assert state is not None
    assert state.version == 2
    assert state.intent_ledger[intent.intent_id].status is IntentStatus.ABOUT_TO_FIRE
    assert state.intent_ledger[intent.intent_id].transitions[-1].old_state == NONE_STATE


@pytest.mark.parametrize(
    "target",
    [
        IntentStatus.FIRED_CONFIRMED,
        IntentStatus.FAILED_CONFIRMED,
        IntentStatus.FIRED_UNCONFIRMED,
    ],
)
@pytest.mark.asyncio
async def test_every_about_to_fire_transition_succeeds(
    redis_client, storage_adapter, lock_manager, target
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create(store, execution_id, token)
    updated = await store.transition_intent(
        execution_id=execution_id,
        intent_id=intent.intent_id,
        expected_version=2,
        lock_token=token,
        new_status=target,
        actor="runner:test",
        reason=f"test-{target.value.lower()}",
    )
    assert updated.status is target
    assert len(updated.transitions) == 2


async def _advance_to_unconfirmed(store, execution_id, token):
    intent = await _create(store, execution_id, token)
    await store.transition_intent(
        execution_id=execution_id,
        intent_id=intent.intent_id,
        expected_version=2,
        lock_token=token,
        new_status=IntentStatus.FIRED_UNCONFIRMED,
        actor="runner:test",
        reason="ambiguous",
    )
    return intent


@pytest.mark.parametrize(
    "target",
    [
        IntentStatus.FIRED_UNCONFIRMED,
        IntentStatus.FIRED_CONFIRMED,
        IntentStatus.FAILED_CONFIRMED,
        IntentStatus.PERMANENTLY_AMBIGUOUS,
    ],
)
@pytest.mark.asyncio
async def test_every_fired_unconfirmed_transition_succeeds(
    redis_client, storage_adapter, lock_manager, target
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _advance_to_unconfirmed(store, execution_id, token)
    kwargs = {}
    if target is IntentStatus.FIRED_UNCONFIRMED:
        kwargs["reconciliation"] = ReconciliationProgress(
            attempt_count=1,
            first_check_at=1,
            last_check_at=1,
            next_check_at=2,
            last_evidence_class="UNKNOWN",
        )
    updated = await store.transition_intent(
        execution_id=execution_id,
        intent_id=intent.intent_id,
        expected_version=3,
        lock_token=token,
        new_status=target,
        actor="recovery:test",
        reason=f"test-{target.value.lower()}",
        **kwargs,
    )
    assert updated.status is target


@pytest.mark.parametrize(
    "target",
    [IntentStatus.FIRED_CONFIRMED, IntentStatus.FAILED_CONFIRMED],
)
@pytest.mark.asyncio
async def test_every_permanently_ambiguous_transition_succeeds(
    redis_client, storage_adapter, lock_manager, target
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _advance_to_unconfirmed(store, execution_id, token)
    await store.transition_intent(
        execution_id=execution_id,
        intent_id=intent.intent_id,
        expected_version=3,
        lock_token=token,
        new_status=IntentStatus.PERMANENTLY_AMBIGUOUS,
        actor="recovery:test",
        reason="limits-exhausted",
    )
    updated = await store.transition_intent(
        execution_id=execution_id,
        intent_id=intent.intent_id,
        expected_version=4,
        lock_token=token,
        new_status=target,
        actor="operator:alice",
        reason="ticket-123-conclusive-evidence",
    )
    assert updated.status is target


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (IntentStatus.ABOUT_TO_FIRE, IntentStatus.ABOUT_TO_FIRE),
        (IntentStatus.FIRED_CONFIRMED, IntentStatus.FAILED_CONFIRMED),
        (IntentStatus.FIRED_CONFIRMED, IntentStatus.FIRED_UNCONFIRMED),
        (IntentStatus.FAILED_CONFIRMED, IntentStatus.FIRED_CONFIRMED),
        (IntentStatus.FAILED_CONFIRMED, IntentStatus.PERMANENTLY_AMBIGUOUS),
        (IntentStatus.PERMANENTLY_AMBIGUOUS, IntentStatus.FIRED_UNCONFIRMED),
        (IntentStatus.PERMANENTLY_AMBIGUOUS, IntentStatus.ABOUT_TO_FIRE),
    ],
)
@pytest.mark.asyncio
async def test_representative_illegal_transitions_are_rejected(
    redis_client, storage_adapter, lock_manager, source, target
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create(store, execution_id, token)
    version = 2
    if source is IntentStatus.FIRED_UNCONFIRMED:
        await store.transition_intent(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            expected_version=version,
            lock_token=token,
            new_status=source,
            actor="runner:test",
            reason="setup",
        )
        version += 1
    elif source is not IntentStatus.ABOUT_TO_FIRE:
        if source is IntentStatus.PERMANENTLY_AMBIGUOUS:
            await store.transition_intent(
                execution_id=execution_id,
                intent_id=intent.intent_id,
                expected_version=version,
                lock_token=token,
                new_status=IntentStatus.FIRED_UNCONFIRMED,
                actor="runner:test",
                reason="setup",
            )
            version += 1
        await store.transition_intent(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            expected_version=version,
            lock_token=token,
            new_status=source,
            actor="recovery:test",
            reason="setup",
        )
        version += 1
    with pytest.raises(IllegalIntentTransitionError):
        await store.transition_intent(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            expected_version=version,
            lock_token=token,
            new_status=target,
            actor="test",
            reason="must-fail",
        )


@pytest.mark.asyncio
async def test_none_cannot_jump_directly_to_confirmed(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    with pytest.raises(IllegalIntentTransitionError, match="absent intent"):
        await store.transition_intent(
            execution_id=execution_id,
            intent_id=str(uuid.uuid4()),
            expected_version=1,
            lock_token=token,
            new_status=IntentStatus.FIRED_CONFIRMED,
            actor="test",
            reason="must-fail",
        )


@pytest.mark.asyncio
async def test_deleting_an_intent_is_rejected_inside_atomic_script(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create(store, execution_id, token)
    current = await store.get_execution(execution_id)
    assert current is not None
    candidate = Phase2ExecutionState.model_validate(
        {**current.model_dump(), "intent_ledger": {}, "version": 3}
    )
    with pytest.raises(IntentInvariantError, match="deletion"):
        await store.commit_transition(
            candidate,
            intent_id=intent.intent_id,
            old_status=IntentStatus.ABOUT_TO_FIRE.value,
            new_status=IntentStatus.FIRED_CONFIRMED,
            expected_version=2,
            lock_token=token,
        )


@pytest.mark.asyncio
async def test_reusing_intent_id_is_rejected_inside_atomic_script(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create(store, execution_id, token)
    current = await store.get_execution(execution_id)
    assert current is not None
    candidate = current.model_copy(update={"version": 3})
    with pytest.raises(IntentInvariantError):
        await store.commit_transition(
            candidate,
            intent_id=intent.intent_id,
            old_status=NONE_STATE,
            new_status=IntentStatus.ABOUT_TO_FIRE,
            expected_version=2,
            lock_token=token,
        )


@pytest.mark.asyncio
async def test_second_unresolved_intent_for_step_rejected_by_same_lua_write(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    first = await _create(store, execution_id, token)
    current = await store.get_execution(execution_id)
    assert current is not None
    now_ms = int((await store.redis_time()) * 1000)
    second_binding, second_intent_id, second_correlation_id = await prepared_binding(
        execution_id=execution_id,
        step_id=first.step_id,
        connector_operation=first.connector,
        target=first.target,
        created_at_ms=now_ms,
    )
    duplicate = first.model_copy(
        update={
            "intent_id": second_intent_id,
            "correlation_id": second_correlation_id,
            "attempt": 2,
                "prepared_state_version": 3,
                "request_binding": second_binding,
                "canonical_request_binding": canonical_request_binding_bytes(
                    second_binding
                ).decode("utf-8"),
                "request_fingerprint": second_binding.request_fingerprint,
        }
    )
    duplicate = duplicate.model_copy(
        update={
            "transitions": tuple(
                entry.model_copy(update={"redis_time": entry.redis_time + 0.001})
                for entry in duplicate.transitions
            )
        }
    )
    duplicate = type(first).model_validate(duplicate.model_dump())
    ledger = dict(current.intent_ledger)
    ledger[duplicate.intent_id] = duplicate
    # Construct without Phase2ExecutionState validation so Lua, not a Python
    # pre-check, is the authority for this race-sensitive invariant.
    candidate = Phase2ExecutionState.model_construct(
        **{
            **current.model_dump(),
            "intent_ledger": ledger,
            "version": 3,
        }
    )
    with pytest.raises(IntentInvariantError, match="uniqueness"):
        await store.commit_transition(
            candidate,
            intent_id=duplicate.intent_id,
            old_status=NONE_STATE,
            new_status=IntentStatus.ABOUT_TO_FIRE,
            expected_version=2,
            lock_token=token,
        )
