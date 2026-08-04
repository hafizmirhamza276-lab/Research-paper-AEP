"""Focused closure tests for the authoritative canonical request binding."""

from __future__ import annotations

import json
import time
import uuid

import pytest

import src.core.request_binding as request_binding_module
from src.core.intents import (
    IntentBindingError,
    IntentInvariantError,
    IntentLedgerStore,
    IntentStatus,
    Phase2ExecutionState,
)
from src.core.request_binding import CanonicalizationError
from src.core.storage import AEPExecutionState, AEPStatus
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


async def _create_bound(store, execution_id, token):
    now = int((await store.redis_time()) * 1000)
    binding, intent_id, correlation_id = await prepared_binding(
        execution_id=execution_id,
        step_id="step-a",
        created_at_ms=now,
    )
    return await store.create_intent(
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


def _confirmed_candidate(current, intent):
    changed = intent.model_copy(
        update={
            "status": IntentStatus.FIRED_CONFIRMED,
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
    return Phase2ExecutionState.model_construct(
        **{
            **current.model_dump(),
            "version": current.version + 1,
            "intent_ledger": {intent.intent_id: changed},
        }
    )


def _alternate_number(binding_text: str) -> str:
    changed = binding_text.replace('"request_material_version":1', '"request_material_version":1.0')
    assert changed != binding_text
    return changed


def _empty_array_as_object(binding_text: str) -> str:
    changed = binding_text.replace('"protected_commitments":[]', '"protected_commitments":{}')
    assert changed != binding_text
    return changed


def _alternate_key_order(binding_text: str) -> str:
    value = json.loads(binding_text)
    value = dict(reversed(tuple(value.items())))
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def _remove_field(binding_text: str) -> str:
    value = json.loads(binding_text)
    del value["wire_codec_version"]
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _add_field(binding_text: str) -> str:
    value = json.loads(binding_text)
    value["unexpected_safe_metadata"] = None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _modify_field(binding_text: str) -> str:
    value = json.loads(binding_text)
    value["correlation_id"] = str(uuid.uuid4())
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


@pytest.mark.asyncio
async def test_identical_binding_semantics_have_identical_canonical_bytes():
    binding, _, _ = await prepared_binding(
        execution_id=str(uuid.uuid4()), step_id="step-a"
    )
    values = binding.model_dump(mode="json")
    reversed_values = dict(reversed(tuple(values.items())))
    canonicalize = request_binding_module.canonical_request_binding_bytes
    assert canonicalize(values) == canonicalize(reversed_values)


@pytest.mark.asyncio
async def test_every_immutable_binding_field_affects_canonical_bytes():
    binding, _, _ = await prepared_binding(
        execution_id=str(uuid.uuid4()), step_id="step-a"
    )
    canonicalize = request_binding_module.canonical_request_binding_bytes
    values = binding.model_dump(mode="json")
    baseline = canonicalize(values)
    for name, value in values.items():
        changed = dict(values)
        if isinstance(value, str):
            changed[name] = value + "-changed"
        elif isinstance(value, int):
            changed[name] = value + 1
        elif isinstance(value, dict):
            nested = dict(value)
            nested["wire_codec_version"] = "mock-wire/changed"
            changed[name] = nested
        else:  # pragma: no cover - the schema has only these immutable kinds
            raise AssertionError(name)
        assert canonicalize(changed) != baseline, name


@pytest.mark.asyncio
async def test_binding_contexts_and_missing_null_array_order_are_distinct():
    binding, _, _ = await prepared_binding(
        execution_id=str(uuid.uuid4()), step_id="step-a"
    )
    canonicalize = request_binding_module.canonical_request_binding_bytes
    values = binding.model_dump(mode="json")
    baseline = canonicalize(values)
    for field in ("execution_id", "step_id", "intent_id", "correlation_id"):
        changed = dict(values)
        changed[field] = str(uuid.uuid4()) if field != "step_id" else "step-b"
        assert canonicalize(changed) != baseline
    missing = dict(values)
    missing.pop("credential_binding_id")
    explicit_null = dict(values)
    explicit_null["credential_binding_id"] = None
    assert canonicalize(missing) != canonicalize(explicit_null)
    descriptor = dict(values["safe_descriptor"])
    fields = list(descriptor["public_fields"])
    descriptor["public_fields"] = list(reversed(fields))
    reordered = dict(values)
    reordered["safe_descriptor"] = descriptor
    assert canonicalize(reordered) != baseline


def test_canonical_binding_has_an_explicit_nesting_limit():
    value: object = None
    for _ in range(130):
        value = [value]
    with pytest.raises(CanonicalizationError):
        request_binding_module.canonical_json_bytes(value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "alter",
    [
        _alternate_number,
        _empty_array_as_object,
        _alternate_key_order,
        _remove_field,
        _add_field,
        _modify_field,
    ],
    ids=[
        "numeric-lexeme",
        "empty-array-object",
        "key-order",
        "missing-field",
        "additional-field",
        "modified-field",
    ],
)
async def test_lua_rejects_any_nonidentical_canonical_binding_and_preserves_raw_state(
    redis_client, storage_adapter, lock_manager, alter
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)
    current = await store.get_execution(execution_id)
    assert current
    candidate = _confirmed_candidate(current, intent)
    key = f"aep:state:{execution_id}"
    raw = json.loads(await redis_client.get(key))
    record = raw["intent_ledger"][intent.intent_id]
    binding_text = record["canonical_request_binding"]
    assert isinstance(binding_text, str)
    record["canonical_request_binding"] = alter(binding_text)
    injected = json.dumps(raw, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    await redis_client.set(key, injected, keepttl=True)
    ttl_before = await redis_client.pttl(key)
    before = json.loads(injected)
    started = time.monotonic()
    with pytest.raises((IntentBindingError, IntentInvariantError)):
        await store.commit_transition(
            candidate,
            intent_id=intent.intent_id,
            old_status=IntentStatus.ABOUT_TO_FIRE.value,
            new_status=IntentStatus.FIRED_CONFIRMED,
            expected_version=current.version,
            lock_token=token,
        )
    elapsed_ms = (time.monotonic() - started) * 1000
    raw_after = await redis_client.get(key)
    ttl_after = await redis_client.pttl(key)
    assert raw_after == injected
    after = json.loads(raw_after)
    assert after["version"] == before["version"]
    assert after["status"] == before["status"]
    assert after["intent_ledger"] == before["intent_ledger"]
    assert ttl_after <= ttl_before
    assert ttl_after >= ttl_before - elapsed_ms - 1_000


@pytest.mark.asyncio
async def test_legacy_unbound_record_is_readable_but_cannot_preflight(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create_bound(store, execution_id, token)
    key = f"aep:state:{execution_id}"
    raw = json.loads(await redis_client.get(key))
    record = raw["intent_ledger"][intent.intent_id]
    record.pop("canonical_request_binding")
    record["request_binding"] = None
    legacy_raw = json.dumps(raw, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    await redis_client.set(key, legacy_raw, keepttl=True)
    legacy = await store.get_execution(execution_id)
    assert legacy
    legacy_intent = legacy.intent_ledger[intent.intent_id]
    assert legacy_intent.request_binding is None
    with pytest.raises(IntentBindingError):
        await store.preflight(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            prepared_state_version=legacy.version,
            lock_token=token,
            required_ttl_ms=1,
            request_binding=intent.request_binding,
        )
    assert await redis_client.get(key) == legacy_raw
