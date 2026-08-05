"""Strict raw-state UTF-8, validation-order, and controlled-race gates."""

from __future__ import annotations

import json
import time

import pytest
from redis.client import NEVER_DECODE

from aep_core.core.durability import FakeDurabilityBarrier
from aep_core.core.exceptions import (
    AmbiguousStateError,
    StateCorruptionError,
    StateSerializationError,
)
from aep_core.core.intent_recovery import RecoveryConnectorConfig
from aep_core.core.intents import IntentLedgerStore, IntentStatus
from aep_core.core.storage import AEPExecutionState, AEPStatus
from tests.mock_connector import (
    MockConnectorHarness,
    ReadbackResult,
    ReconciliationCapability,
    ResponseMode,
)
from tests.request_binding_helpers import test_request as _request
from tests.test_phase2_mutation_safety import (
    FINGERPRINT,
    _create,
    _runner,
    _seed,
)
from tests.test_phase2_recovery import (
    CONNECTOR_NAME,
    _seed_stale_about,
    _service,
)


class _CountingBarrier(FakeDurabilityBarrier):
    def __init__(self) -> None:
        self.calls = 0

    async def confirm_durable(self, connection, timeout_ms: int) -> bool:
        self.calls += 1
        return await super().confirm_durable(connection, timeout_ms)


async def _raw_get(redis_client, key: str) -> bytes | None:
    return await redis_client.execute_command(
        "GET", key, **{NEVER_DECODE: True}
    )


def _invalid_value(raw: bytes, field: bytes | None = None) -> bytes:
    if field is not None:
        for old_value in (b'"IDLE"', b'"PAUSED"', b'"PROCESSING"'):
            needle = b'"' + field + b'":' + old_value
            if needle in raw:
                return raw.replace(
                    needle, b'"' + field + b'":"\xff"', 1
                )
        raise AssertionError(f"field {field!r} was not found in state")
    assert raw.endswith(b"}")
    return raw[:-1] + b',"invalid_utf8":"\xff"}'


def _duplicate_member(raw: bytes) -> bytes:
    assert raw.endswith(b"}")
    return raw[:-1] + b',"future_field":1,"future_field":1}'


async def _inject(redis_client, key: str, raw: bytes) -> None:
    assert await redis_client.set(key, raw, keepttl=True, xx=True)


async def _assert_rejection_preserves_raw_state(
    redis_client,
    key: str,
    error_type: type[BaseException],
    operation,
    *,
    expected_raw=None,
    expected_ttl=None,
) -> None:
    raw_before = await _raw_get(redis_client, key)
    ttl_before = await redis_client.pttl(key)
    assert raw_before is not None
    assert ttl_before > 0
    started = time.monotonic()
    with pytest.raises(error_type):
        await operation()
    elapsed_ms = (time.monotonic() - started) * 1000
    expected = expected_raw() if expected_raw is not None else raw_before
    assert await _raw_get(redis_client, key) == expected
    ttl_after = await redis_client.pttl(key)
    ttl_reference = expected_ttl() if expected_ttl is not None else ttl_before
    assert ttl_after <= ttl_reference
    assert ttl_after >= ttl_reference - elapsed_ms - 1_000


@pytest.mark.asyncio
async def test_decode_responses_client_maps_invalid_utf8_read_to_corruption(
    redis_client, storage_adapter
):
    execution_id = "00000000-0000-4000-8000-000000000101"
    key = f"aep:state:{execution_id}"
    invalid = b'{"execution_id":"' + execution_id.encode() + b'","x":"\xff"}'
    await redis_client.set(key, invalid, ex=3600)

    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        StateCorruptionError,
        lambda: storage_adapter.get_state(execution_id),
    )
    assert await _raw_get(redis_client, key) == invalid
    poison_keys = [
        item
        async for item in redis_client.scan_iter(
            match=f"aep:poison:{execution_id}:*", count=100
        )
    ]
    assert poison_keys
    poison = json.loads(await redis_client.get(poison_keys[-1]))
    assert poison["reason"] == "parse-or-validation"
    assert "raw" not in poison
    assert poison["raw_encoding"] == "binary"
    assert poison["raw_length"] == len(invalid)


@pytest.mark.asyncio
async def test_phase1_save_rejects_invalid_utf8_without_replacement_or_ttl_refresh(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    current = await storage_adapter.get_state(execution_id)
    assert current is not None
    key = f"aep:state:{execution_id}"
    invalid = _invalid_value(await _raw_get(redis_client, key), b"status")
    await _inject(redis_client, key, invalid)
    candidate = current.model_copy(
        update={"version": 2, "status": AEPStatus.PROCESSING}
    )

    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        StateCorruptionError,
        lambda: storage_adapter.save_state(
            candidate,
            expected_version=1,
            lock_token=token,
            ttl_seconds=7200,
        ),
    )
    assert b'"version":1' in invalid


@pytest.mark.parametrize("content", ["invalid", "ambiguous"])
@pytest.mark.parametrize("contention", ["stale-token", "missing-lock", "stale-version"])
@pytest.mark.asyncio
async def test_phase1_raw_failure_precedes_lock_and_version_rejection(
    redis_client, storage_adapter, lock_manager, content, contention
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    current = await storage_adapter.get_state(execution_id)
    assert current is not None
    key = f"aep:state:{execution_id}"
    raw = await _raw_get(redis_client, key)
    injected = _invalid_value(raw) if content == "invalid" else _duplicate_member(raw)
    await _inject(redis_client, key, injected)
    if contention == "missing-lock":
        await redis_client.delete(f"aep:lock:{execution_id}")
    candidate = current.model_copy(update={"version": 2})
    expected_error = StateCorruptionError if content == "invalid" else AmbiguousStateError

    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        expected_error,
        lambda: storage_adapter.save_state(
            candidate,
            expected_version=0 if contention == "stale-version" else 1,
            lock_token="stale-token" if contention == "stale-token" else token,
            ttl_seconds=7200,
        ),
    )


@pytest.mark.asyncio
async def test_phase1_candidate_invalid_utf8_is_serialization_error(
    redis_client, storage_adapter, lock_manager, monkeypatch
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    current = await storage_adapter.get_state(execution_id)
    assert current is not None
    candidate = current.model_copy(update={"version": 2})
    key = f"aep:state:{execution_id}"
    monkeypatch.setattr(
        "aep_core.core.storage.encode_state",
        lambda value: b'{"version":2,"invalid":"\xff"}',
    )

    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        StateSerializationError,
        lambda: storage_adapter.save_state(
            candidate,
            expected_version=1,
            lock_token=token,
            ttl_seconds=7200,
        ),
    )


@pytest.mark.parametrize(
    "candidate_raw",
    [
        pytest.param(b'{"invalid":"\xff"}', id="invalid-utf8"),
        pytest.param(b'{"x":1,"x":2}', id="duplicate-member"),
    ],
)
@pytest.mark.asyncio
async def test_phase2_candidate_serialization_failure_is_typed_and_nonmutating(
    redis_client,
    storage_adapter,
    lock_manager,
    monkeypatch,
    candidate_raw,
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create(store, execution_id, token, expected_version=1)
    key = f"aep:state:{execution_id}"
    monkeypatch.setattr("aep_core.core.intents.encode_state", lambda value: candidate_raw)

    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        StateSerializationError,
        lambda: store.transition_intent(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            expected_version=2,
            lock_token=token,
            new_status=IntentStatus.FIRED_CONFIRMED,
            actor="regression:test",
            reason="must-not-commit",
        ),
    )

@pytest.mark.parametrize("content", ["invalid", "ambiguous"])
@pytest.mark.parametrize("lock_state", ["stale", "missing"])
@pytest.mark.asyncio
async def test_phase2_cas_raw_failure_precedes_lock_and_stale_version(
    redis_client,
    storage_adapter,
    lock_manager,
    monkeypatch,
    content,
    lock_state,
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    original_get = store.get_execution
    key = f"aep:state:{execution_id}"
    expected_error = StateCorruptionError if content == "invalid" else AmbiguousStateError
    injected: dict[str, bytes] = {}

    async def read_then_inject(*args, **kwargs):
        current = await original_get(*args, **kwargs)
        raw = await _raw_get(redis_client, key)
        injected["raw"] = (
            _invalid_value(raw) if content == "invalid" else _duplicate_member(raw)
        )
        await _inject(redis_client, key, injected["raw"])
        if lock_state == "missing":
            await redis_client.delete(f"aep:lock:{execution_id}")
        return current

    monkeypatch.setattr(store, "get_execution", read_then_inject)
    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        expected_error,
        lambda: _create(
            store,
            execution_id,
            "stale-token" if lock_state == "stale" else token,
            expected_version=0,
        ),
        expected_raw=lambda: injected["raw"],
    )
    assert await _raw_get(redis_client, key) == injected["raw"]


@pytest.mark.parametrize("content", ["invalid", "ambiguous"])
@pytest.mark.parametrize("lock_state", ["stale", "short-ttl"])
@pytest.mark.asyncio
async def test_preflight_raw_failure_precedes_token_ttl_version_and_status(
    redis_client,
    storage_adapter,
    lock_manager,
    content,
    lock_state,
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create(store, execution_id, token, expected_version=1)
    key = f"aep:state:{execution_id}"
    raw = await _raw_get(redis_client, key)
    injected = _invalid_value(raw) if content == "invalid" else _duplicate_member(raw)
    await _inject(redis_client, key, injected)
    if lock_state == "short-ttl":
        assert await redis_client.pexpire(f"aep:lock:{execution_id}", 5_000)
    expected_error = StateCorruptionError if content == "invalid" else AmbiguousStateError

    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        expected_error,
        lambda: store.preflight(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            prepared_state_version=intent.prepared_state_version - 1,
            lock_token="stale-token" if lock_state == "stale" else token,
            required_ttl_ms=10_000,
            request_binding=intent.request_binding,
        ),
    )


@pytest.mark.asyncio
async def test_phase2_creation_rejects_post_read_invalid_utf8_injection(
    redis_client, storage_adapter, lock_manager, monkeypatch
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    original_get = store.get_execution
    key = f"aep:state:{execution_id}"
    injected: dict[str, bytes] = {}

    async def read_then_inject(*args, **kwargs):
        current = await original_get(*args, **kwargs)
        injected["raw"] = _invalid_value(await _raw_get(redis_client, key))
        await _inject(redis_client, key, injected["raw"])
        return current

    monkeypatch.setattr(store, "get_execution", read_then_inject)
    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        StateCorruptionError,
        lambda: _create(store, execution_id, token, expected_version=1),
        expected_raw=lambda: injected["raw"],
    )
    assert b'"intent_ledger":{}' in injected["raw"]
    assert b'"version":1' in injected["raw"]


@pytest.mark.asyncio
async def test_paused_runner_race_preserves_injected_state_with_zero_side_effects(
    redis_client, storage_adapter, lock_manager, monkeypatch
):
    execution_id, _ = await _seed(
        storage_adapter,
        lock_manager,
        status=AEPStatus.PAUSED,
        keep_lock=False,
    )
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    barrier = _CountingBarrier()
    runner = _runner(redis_client, lock_manager, harness)
    runner.barrier = barrier
    store = IntentLedgerStore(redis_client)
    runner.store = store
    original_get = store.get_execution
    key = f"aep:state:{execution_id}"
    reads = 0
    injected: dict[str, bytes] = {}

    async def inject_after_second_application_read(*args, **kwargs):
        nonlocal reads
        current = await original_get(*args, **kwargs)
        reads += 1
        if reads == 2:
            injected["raw"] = _invalid_value(
                await _raw_get(redis_client, key), b"status"
            )
            await _inject(redis_client, key, injected["raw"])
        return current

    monkeypatch.setattr(store, "get_execution", inject_after_second_application_read)
    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        StateCorruptionError,
        lambda: runner.execute(
            execution_id=execution_id,
            step_id="step-a",
            request=_request(target="redacted-step-a"),
        ),
        expected_raw=lambda: injected["raw"],
    )
    assert reads == 2
    assert await _raw_get(redis_client, key) == injected["raw"]
    assert b'"version":1' in injected["raw"]
    assert b'"intent_ledger":{}' in injected["raw"]
    assert harness.oracle.calls == ()
    assert barrier.calls == 0


@pytest.mark.asyncio
async def test_phase2_transition_rejects_post_read_invalid_utf8_injection(
    redis_client, storage_adapter, lock_manager, monkeypatch
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create(store, execution_id, token, expected_version=1)
    original_get = store.get_execution
    key = f"aep:state:{execution_id}"
    injected: dict[str, bytes] = {}

    async def read_then_inject(*args, **kwargs):
        current = await original_get(*args, **kwargs)
        injected["raw"] = _invalid_value(await _raw_get(redis_client, key))
        await _inject(
            redis_client,
            key,
            injected["raw"],
        )
        return current

    monkeypatch.setattr(store, "get_execution", read_then_inject)
    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        StateCorruptionError,
        lambda: store.transition_intent(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            expected_version=2,
            lock_token=token,
            new_status=IntentStatus.FIRED_CONFIRMED,
            actor="regression:test",
            reason="must-not-commit",
        ),
        expected_raw=lambda: injected["raw"],
    )


@pytest.mark.asyncio
async def test_runner_resolution_rejects_post_read_invalid_state_before_ack(
    redis_client, storage_adapter, lock_manager, monkeypatch
):
    execution_id, _ = await _seed(
        storage_adapter, lock_manager, keep_lock=False
    )
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    barrier = _CountingBarrier()
    runner = _runner(redis_client, lock_manager, harness)
    runner.barrier = barrier
    store = IntentLedgerStore(redis_client)
    runner.store = store
    original_get = store.get_execution
    key = f"aep:state:{execution_id}"
    reads = 0
    injected: dict[str, bytes] = {}
    injected_ttl: list[int] = []

    async def inject_during_resolution_transition(*args, **kwargs):
        nonlocal reads
        current = await original_get(*args, **kwargs)
        reads += 1
        if reads == 3:
            injected["raw"] = _invalid_value(await _raw_get(redis_client, key))
            await _inject(
                redis_client,
                key,
                injected["raw"],
            )
            injected_ttl.append(await redis_client.pttl(key))
        return current

    monkeypatch.setattr(store, "get_execution", inject_during_resolution_transition)
    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        StateCorruptionError,
        lambda: runner.execute(
            execution_id=execution_id,
            step_id="step-a",
            request=_request(target="redacted-step-a"),
        ),
        expected_raw=lambda: injected["raw"],
        expected_ttl=lambda: injected_ttl[0],
    )
    assert reads == 3
    assert len(harness.oracle.calls) == 1
    assert barrier.calls == 1


def _count_recovery_barrier(service, barrier: _CountingBarrier) -> None:
    config = service.connectors[CONNECTOR_NAME]
    service.connectors[CONNECTOR_NAME] = RecoveryConnectorConfig(
        connector=config.connector,
        barrier=barrier,
        policy=config.policy,
    )


@pytest.mark.asyncio
async def test_recovery_claim_rejects_post_read_invalid_state_before_readback_or_ack(
    redis_client, storage_adapter, lock_manager, monkeypatch
):
    execution_id, intent_id, _ = await _seed_stale_about(
        storage_adapter, lock_manager, redis_client
    )
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    barrier = _CountingBarrier()
    service = _service(redis_client, lock_manager, harness)
    _count_recovery_barrier(service, barrier)
    original_get = service.store.get_execution
    key = f"aep:state:{execution_id}"
    reads = 0
    injected: dict[str, bytes] = {}

    async def inject_during_claim_transition(*args, **kwargs):
        nonlocal reads
        current = await original_get(*args, **kwargs)
        reads += 1
        if reads == 3:
            injected["raw"] = _invalid_value(await _raw_get(redis_client, key))
            await _inject(
                redis_client,
                key,
                injected["raw"],
            )
        return current

    monkeypatch.setattr(service.store, "get_execution", inject_during_claim_transition)
    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        StateCorruptionError,
        lambda: service.recover_intent(execution_id, intent_id),
        expected_raw=lambda: injected["raw"],
    )
    assert reads == 3
    assert harness.oracle.calls == ()
    assert harness.oracle.readbacks == ()
    assert barrier.calls == 0


@pytest.mark.asyncio
async def test_recovery_resolution_rejects_post_read_invalid_state_before_ack(
    redis_client, storage_adapter, lock_manager, monkeypatch
):
    execution_id, intent_id, _ = await _seed_stale_about(
        storage_adapter, lock_manager, redis_client
    )
    token = await lock_manager.acquire_lock(execution_id, ttl_seconds=60)
    assert token is not None
    store = IntentLedgerStore(redis_client)
    await store.transition_intent(
        execution_id=execution_id,
        intent_id=intent_id,
        expected_version=1,
        lock_token=token,
        new_status=IntentStatus.FIRED_UNCONFIRMED,
        actor="regression:setup",
        reason="setup-unconfirmed",
    )
    assert await lock_manager.release_lock(execution_id, token)

    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    harness.enqueue_readback(ReadbackResult.APPLIED)
    barrier = _CountingBarrier()
    service = _service(redis_client, lock_manager, harness)
    _count_recovery_barrier(service, barrier)
    original_get = service.store.get_execution
    key = f"aep:state:{execution_id}"
    reads = 0
    injected: dict[str, bytes] = {}

    async def inject_during_resolution_transition(*args, **kwargs):
        nonlocal reads
        current = await original_get(*args, **kwargs)
        reads += 1
        if reads == 3:
            injected["raw"] = _invalid_value(await _raw_get(redis_client, key))
            await _inject(
                redis_client,
                key,
                injected["raw"],
            )
        return current

    monkeypatch.setattr(service.store, "get_execution", inject_during_resolution_transition)
    await _assert_rejection_preserves_raw_state(
        redis_client,
        key,
        StateCorruptionError,
        lambda: service.recover_intent(execution_id, intent_id),
        expected_raw=lambda: injected["raw"],
    )
    assert reads == 3
    assert harness.oracle.calls == ()
    assert len(harness.oracle.readbacks) == 1
    assert barrier.calls == 0


@pytest.mark.asyncio
async def test_valid_phase1_and_phase2_operations_pass_after_raw_gate(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    current = await storage_adapter.get_state(execution_id)
    assert current is not None
    current.version = 2
    current.context_data = {
        "urdu": "\u0633\u0644\u0627\u0645",
        "chinese": "\u4e2d\u6587",
        "accented": "caf\u00e9",
        "emoji": "\U0001f600",
    }
    await storage_adapter.save_state(
        current,
        expected_version=1,
        lock_token=token,
        ttl_seconds=3600,
    )
    intent = await _create(
        IntentLedgerStore(redis_client),
        execution_id,
        token,
        expected_version=2,
    )
    assert intent.status is IntentStatus.ABOUT_TO_FIRE
    persisted = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert persisted is not None
    assert persisted.version == 3
    assert persisted.context_data == current.context_data
