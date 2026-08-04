"""P2-004 authoritative Redis request-binding immutability tests."""

from __future__ import annotations

import json
import time
import uuid

import pytest

from src.core.intents import (
    IntentBindingError,
    IntentInvariantError,
    IntentLedgerStore,
    IntentStatus,
    Phase2ExecutionState,
)
from src.core.storage import AEPExecutionState, AEPStatus
from src.core.request_binding import canonical_request_binding_bytes
from tests.request_binding_helpers import prepared_binding


async def _seed(storage_adapter, lock_manager):
    execution_id = str(uuid.uuid4())
    token = await lock_manager.acquire_lock(execution_id, ttl_seconds=60)
    assert token
    await storage_adapter.save_state(
        AEPExecutionState(execution_id=execution_id, status=AEPStatus.IDLE),
        expected_version=0,
        lock_token=token,
        ttl_seconds=3600,
    )
    return execution_id, token


async def _create_bound(store, execution_id, token, *, step_id="step-a"):
    now = int((await store.redis_time()) * 1000)
    binding, intent_id, correlation_id = await prepared_binding(
        execution_id=execution_id,
        step_id=step_id,
        created_at_ms=now,
    )
    intent = await store.create_intent(
        execution_id=execution_id,
        expected_version=1,
        lock_token=token,
        step_id=step_id,
        connector=binding.connector_operation,
        target=binding.safe_descriptor.redacted_target,
        request_fingerprint=binding.request_fingerprint,
        request_binding=binding,
        client_timeout_seconds=1,
        settlement_lag_seconds=0,
        buffer_margin_seconds=15,
        actor="runner:test",
        intent_id=intent_id,
        correlation_id=correlation_id,
    )
    return intent


async def _assert_exact_rejection(redis_client, execution_id, operation):
    key = f"aep:state:{execution_id}"
    raw_before = await redis_client.get(key)
    ttl_before = await redis_client.pttl(key)
    started = time.monotonic()
    with pytest.raises(IntentInvariantError):
        await operation()
    elapsed_ms = (time.monotonic() - started) * 1000
    raw_after = await redis_client.get(key)
    ttl_after = await redis_client.pttl(key)
    assert raw_after == raw_before
    assert ttl_after <= ttl_before
    assert ttl_after >= ttl_before - elapsed_ms - 1_000


@pytest.mark.asyncio
async def test_new_intent_requires_complete_binding(redis_client, storage_adapter, lock_manager):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    with pytest.raises(IntentBindingError):
        await store.create_intent(
            execution_id=execution_id,
            expected_version=1,
            lock_token=token,
            step_id="step-a",
            connector="mock.non-idempotent.v1/mutate",
            target="account-redacted-17",
            request_fingerprint="a" * 64,
            client_timeout_seconds=1,
            settlement_lag_seconds=0,
            buffer_margin_seconds=15,
            actor="runner:test",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "binding_update",
    [
        None,
        {"request_material_ref": "vault_zyxwvutsrqponmlkjihgfedc"},
        {"request_fingerprint": "b" * 64},
        {"request_binding_digest": "c" * 64},
        {"descriptor_version": "aep.safe-request/2"},
        {"commitment_key_id": "different-key"},
        {"execution_id": str(uuid.uuid4())},
        {"intent_id": str(uuid.uuid4())},
        {"correlation_id": str(uuid.uuid4())},
        {"retention_not_after_ms": 1_800_000_000_001},
    ],
)
async def test_lua_rejects_binding_removal_or_change(
    redis_client, storage_adapter, lock_manager, binding_update
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)
    current = await store.get_execution(execution_id)
    assert current
    if binding_update is None:
        changed_binding = None
    else:
        changed_binding = intent.request_binding.model_copy(update=binding_update)
    changed_intent = intent.model_copy(update={
        "status": IntentStatus.FIRED_CONFIRMED,
        "request_binding": changed_binding,
        "canonical_request_binding": (
            canonical_request_binding_bytes(changed_binding).decode("utf-8")
            if changed_binding is not None
            else None
        ),
        "transitions": (*intent.transitions, intent.transitions[-1].model_copy(update={
            "old_state": IntentStatus.ABOUT_TO_FIRE.value,
            "new_state": IntentStatus.FIRED_CONFIRMED,
        })),
    })
    candidate = Phase2ExecutionState.model_construct(**{
        **current.model_dump(),
        "version": 3,
        "intent_ledger": {intent.intent_id: changed_intent},
    })
    await _assert_exact_rejection(
        redis_client,
        execution_id,
        lambda: store.commit_transition(
            candidate,
            intent_id=intent.intent_id,
            old_status=IntentStatus.ABOUT_TO_FIRE.value,
            new_status=IntentStatus.FIRED_CONFIRMED,
            expected_version=2,
            lock_token=token,
        ),
    )


@pytest.mark.asyncio
async def test_unchanged_binding_survives_normal_transition_exactly(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)
    before = intent.request_binding.model_dump(mode="json")
    updated = await store.transition_intent(
        execution_id=execution_id,
        intent_id=intent.intent_id,
        expected_version=2,
        lock_token=token,
        new_status=IntentStatus.FIRED_CONFIRMED,
        actor="runner:test",
        reason="confirmed",
    )
    assert updated.request_binding.model_dump(mode="json") == before
    raw = json.loads(await redis_client.get(f"aep:state:{execution_id}"))
    assert raw["intent_ledger"][intent.intent_id][
        "canonical_request_binding"
    ] == canonical_request_binding_bytes(before).decode("utf-8")


@pytest.mark.asyncio
async def test_lua_rejects_shortened_retention_deadline_exactly(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)
    current = await store.get_execution(execution_id)
    assert current and intent.request_binding
    shortened = intent.request_binding.model_copy(
        update={
            "retention_not_after_ms": (
                intent.request_binding.retention_not_after_ms - 1
            )
        }
    )
    changed_intent = intent.model_copy(
        update={
            "status": IntentStatus.FIRED_CONFIRMED,
            "request_binding": shortened,
            "canonical_request_binding": canonical_request_binding_bytes(
                shortened
            ).decode("utf-8"),
            "transitions": (
                *intent.transitions,
                intent.transitions[-1].model_copy(
                    update={
                        "old_state": IntentStatus.ABOUT_TO_FIRE.value,
                        "new_state": IntentStatus.FIRED_CONFIRMED,
                    }
                ),
            ),
        }
    )
    candidate = Phase2ExecutionState.model_construct(
        **{
            **current.model_dump(),
            "version": 3,
            "intent_ledger": {intent.intent_id: changed_intent},
        }
    )
    await _assert_exact_rejection(
        redis_client,
        execution_id,
        lambda: store.commit_transition(
            candidate,
            intent_id=intent.intent_id,
            old_status=IntentStatus.ABOUT_TO_FIRE.value,
            new_status=IntentStatus.FIRED_CONFIRMED,
            expected_version=2,
            lock_token=token,
        ),
    )


@pytest.mark.asyncio
async def test_lua_rejects_adding_binding_to_readable_legacy_intent(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    bound_intent = await _create_bound(store, execution_id, token)
    key = f"aep:state:{execution_id}"
    raw = json.loads(await redis_client.get(key))
    raw["intent_ledger"][bound_intent.intent_id].pop(
        "canonical_request_binding"
    )
    raw["intent_ledger"][bound_intent.intent_id]["request_binding"] = None
    await redis_client.set(
        key,
        json.dumps(raw, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        keepttl=True,
    )
    legacy = await store.get_execution(execution_id)
    assert legacy and legacy.intent_ledger[bound_intent.intent_id].request_binding is None
    old = legacy.intent_ledger[bound_intent.intent_id]
    changed = old.model_copy(
        update={
            "status": IntentStatus.FIRED_CONFIRMED,
            "request_binding": bound_intent.request_binding,
            "canonical_request_binding": canonical_request_binding_bytes(
                bound_intent.request_binding
            ).decode("utf-8"),
            "transitions": (
                *old.transitions,
                old.transitions[-1].model_copy(
                    update={
                        "old_state": IntentStatus.ABOUT_TO_FIRE.value,
                        "new_state": IntentStatus.FIRED_CONFIRMED,
                    }
                ),
            ),
        }
    )
    candidate = Phase2ExecutionState.model_construct(
        **{
            **legacy.model_dump(),
            "version": 3,
            "intent_ledger": {old.intent_id: changed},
        }
    )
    await _assert_exact_rejection(
        redis_client,
        execution_id,
        lambda: store.commit_transition(
            candidate,
            intent_id=old.intent_id,
            old_status=IntentStatus.ABOUT_TO_FIRE.value,
            new_status=IntentStatus.FIRED_CONFIRMED,
            expected_version=2,
            lock_token=token,
        ),
    )


@pytest.mark.asyncio
async def test_transplanted_binding_is_rejected_before_intent_creation(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    other_execution_id = str(uuid.uuid4())
    now = int((await IntentLedgerStore(redis_client).redis_time()) * 1000)
    binding, intent_id, correlation_id = await prepared_binding(
        execution_id=other_execution_id,
        step_id="step-a",
        created_at_ms=now,
    )
    key = f"aep:state:{execution_id}"
    raw_before = await redis_client.get(key)
    ttl_before = await redis_client.pttl(key)
    with pytest.raises(IntentBindingError):
        await IntentLedgerStore(redis_client).create_intent(
            execution_id=execution_id,
            expected_version=1,
            lock_token=token,
            step_id="step-a",
            connector=binding.connector_operation,
            target=binding.safe_descriptor.redacted_target,
            request_fingerprint=binding.request_fingerprint,
            request_binding=binding,
            client_timeout_seconds=1,
            settlement_lag_seconds=0,
            buffer_margin_seconds=15,
            actor="runner:test",
            intent_id=intent_id,
            correlation_id=correlation_id,
        )
    assert await redis_client.get(key) == raw_before
    assert await redis_client.pttl(key) <= ttl_before


@pytest.mark.asyncio
async def test_preflight_requires_matching_binding_digest(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)
    with pytest.raises(IntentBindingError):
        await store.preflight(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            prepared_state_version=2,
            lock_token=token,
            required_ttl_ms=1,
            request_binding=intent.request_binding.model_copy(
                update={"request_binding_digest": "f" * 64}
            ),
        )
