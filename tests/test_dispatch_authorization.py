"""Phase 1B regression tests: the WAITAOF ack is a *checked* dispatch gate.

Before Phase 1B, the ordering "durable intent, then dispatch" held only because
``WriteAheadRunner.execute`` happened to call the barrier before the connector.
Nothing in Redis recorded that the barrier had run, so the pre-dispatch
preflight would authorise a dispatch that had never been made durable.
"""

from __future__ import annotations

import pathlib
import uuid

import pytest

from src.core.durability import (
    DurabilityAck,
    DurabilityBarrierError,
    FakeDurabilityBarrier,
    confirm_durable_ack,
    consume_durability_ack,
    dispatch_scope,
)
from src.core.intents import (
    DispatchAuthorizationError,
    IntentLedgerStore,
)
from tests.test_request_binding_intents import _create_bound, _seed


async def _ack(redis_client, scope: str) -> DurabilityAck:
    return await confirm_durable_ack(
        FakeDurabilityBarrier(), redis_client, 100, scope=scope
    )


# ---------------------------------------------------------------------------
# The ack object itself
# ---------------------------------------------------------------------------


def test_durability_ack_cannot_be_constructed_directly():
    with pytest.raises(DurabilityBarrierError):
        DurabilityAck()


def test_durability_ack_cannot_be_subclassed():
    with pytest.raises(TypeError):

        class _Forged(DurabilityAck):  # pragma: no cover - raises at class body
            pass


@pytest.mark.asyncio
async def test_durability_ack_is_single_use(redis_client):
    scope = dispatch_scope("exec", "intent", 2)
    ack = await _ack(redis_client, scope)
    consume_durability_ack(ack, scope=scope)
    with pytest.raises(DurabilityBarrierError):
        consume_durability_ack(ack, scope=scope)


@pytest.mark.asyncio
async def test_durability_ack_is_scope_bound(redis_client):
    ack = await _ack(redis_client, dispatch_scope("exec", "intent", 2))
    with pytest.raises(DurabilityBarrierError):
        consume_durability_ack(ack, scope=dispatch_scope("exec", "intent", 3))


@pytest.mark.asyncio
async def test_failed_barrier_mints_no_ack(redis_client):
    class _RefusingBarrier:
        test_only = True

        async def confirm_durable(self, connection, timeout_ms):
            return False

    with pytest.raises(DurabilityBarrierError):
        await confirm_durable_ack(
            _RefusingBarrier(), redis_client, 100, scope=dispatch_scope("e", "i", 1)
        )


# ---------------------------------------------------------------------------
# Redis-side authorization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preflight_without_authorization_is_rejected(
    redis_client, storage_adapter, lock_manager
):
    """The headline Phase 1B assertion: no ack recorded, no dispatch."""

    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)

    with pytest.raises(DispatchAuthorizationError):
        await store.preflight(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            prepared_state_version=intent.prepared_state_version,
            lock_token=token,
            required_ttl_ms=1,
            request_binding=intent.request_binding,
        )


@pytest.mark.asyncio
async def test_preflight_succeeds_after_an_authorized_barrier_ack(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)
    scope = dispatch_scope(
        execution_id, intent.intent_id, intent.prepared_state_version
    )

    authorization = await store.authorize_dispatch(
        execution_id=execution_id,
        intent_id=intent.intent_id,
        prepared_state_version=intent.prepared_state_version,
        lock_token=token,
        request_binding=intent.request_binding,
        ack=await _ack(redis_client, scope),
        authorization_ttl_ms=30_000,
    )
    assert authorization

    ttl = await store.preflight(
        execution_id=execution_id,
        intent_id=intent.intent_id,
        prepared_state_version=intent.prepared_state_version,
        lock_token=token,
        required_ttl_ms=1,
        request_binding=intent.request_binding,
        authorization=authorization,
    )
    assert ttl > 0

    stored = await redis_client.get(
        f"aep:dispatch-auth:{execution_id}:{intent.intent_id}"
    )
    assert stored == authorization


@pytest.mark.asyncio
async def test_authorize_dispatch_requires_a_real_ack(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)

    class _FakeAck:
        scope = "anything"

    with pytest.raises(DurabilityBarrierError):
        await store.authorize_dispatch(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            prepared_state_version=intent.prepared_state_version,
            lock_token=token,
            request_binding=intent.request_binding,
            ack=_FakeAck(),
            authorization_ttl_ms=30_000,
        )
    assert (
        await redis_client.get(
            f"aep:dispatch-auth:{execution_id}:{intent.intent_id}"
        )
        is None
    )


@pytest.mark.asyncio
async def test_authorization_is_bound_to_the_exact_attempt_version(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)
    wrong_version = intent.prepared_state_version + 1
    scope = dispatch_scope(execution_id, intent.intent_id, wrong_version)

    with pytest.raises(DispatchAuthorizationError):
        await store.authorize_dispatch(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            prepared_state_version=wrong_version,
            lock_token=token,
            request_binding=intent.request_binding,
            ack=await _ack(redis_client, scope),
            authorization_ttl_ms=30_000,
        )


@pytest.mark.asyncio
async def test_authorization_requires_the_current_lease(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)
    scope = dispatch_scope(
        execution_id, intent.intent_id, intent.prepared_state_version
    )

    with pytest.raises(DispatchAuthorizationError):
        await store.authorize_dispatch(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            prepared_state_version=intent.prepared_state_version,
            lock_token="not-the-owner",
            request_binding=intent.request_binding,
            ack=await _ack(redis_client, scope),
            authorization_ttl_ms=30_000,
        )


@pytest.mark.asyncio
async def test_authorization_does_not_transfer_between_intents(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)
    scope = dispatch_scope(
        execution_id, intent.intent_id, intent.prepared_state_version
    )
    authorization = await store.authorize_dispatch(
        execution_id=execution_id,
        intent_id=intent.intent_id,
        prepared_state_version=intent.prepared_state_version,
        lock_token=token,
        request_binding=intent.request_binding,
        ack=await _ack(redis_client, scope),
        authorization_ttl_ms=30_000,
    )

    # A different intent id has no authorization key of its own.
    other_intent_id = str(uuid.uuid4())
    with pytest.raises(Exception) as excinfo:
        await store.preflight(
            execution_id=execution_id,
            intent_id=other_intent_id,
            prepared_state_version=intent.prepared_state_version,
            lock_token=token,
            required_ttl_ms=1,
            request_binding=intent.request_binding,
            authorization=authorization,
        )
    assert excinfo.value is not None


@pytest.mark.asyncio
async def test_a_forged_authorization_value_is_rejected(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)
    scope = dispatch_scope(
        execution_id, intent.intent_id, intent.prepared_state_version
    )
    await store.authorize_dispatch(
        execution_id=execution_id,
        intent_id=intent.intent_id,
        prepared_state_version=intent.prepared_state_version,
        lock_token=token,
        request_binding=intent.request_binding,
        ack=await _ack(redis_client, scope),
        authorization_ttl_ms=30_000,
    )

    with pytest.raises(DispatchAuthorizationError):
        await store.preflight(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            prepared_state_version=intent.prepared_state_version,
            lock_token=token,
            required_ttl_ms=1,
            request_binding=intent.request_binding,
            authorization="guessed-authorization-value",
        )


# ---------------------------------------------------------------------------
# Source-level guard
# ---------------------------------------------------------------------------


def test_preflight_lua_consults_the_dispatch_authorization_key():
    source = pathlib.Path("src/core/intents.py").read_text(encoding="utf-8")
    assert "aep:dispatch-auth:" in source
    preflight_body = source.split("_PREFLIGHT_SCRIPT_BODY")[1].split(
        "_PREFLIGHT_SCRIPT ="
    )[0]
    assert "KEYS[3]" in preflight_body, (
        "the preflight Lua must read the dispatch-authorization key"
    )
