"""Controlled duplicate-member closure regressions for P2-001/002/003."""

from __future__ import annotations

import copy
import json
import time

import pytest

from aep_core.core.durability import FakeDurabilityBarrier
from aep_core.core.exceptions import AmbiguousStateError
from aep_core.core.intents import IntentLedgerStore, IntentStatus
from aep_core.core.state_codec import encode_state
from aep_core.core.storage import AEPExecutionState, AEPStatus
from tests.mock_connector import MockConnectorHarness, ResponseMode
from tests.request_binding_helpers import test_request as _request
from tests.test_phase2_mutation_safety import (
    FINGERPRINT,
    _create,
    _runner,
    _seed,
    _state_with_intent_status,
)
from tests.test_phase2_recovery import _seed_stale_about, _service


class _CountingBarrier(FakeDurabilityBarrier):
    def __init__(self) -> None:
        self.calls = 0

    async def confirm_durable(self, connection, timeout_ms: int) -> bool:
        self.calls += 1
        return await super().confirm_durable(connection, timeout_ms)


def _raw_object(members: list[tuple[str, str]]) -> str:
    return "{" + ",".join(
        f"{encode_state(name)}:{raw_value}" for name, raw_value in members
    ) + "}"


def _state_with_hidden_blocker(
    state,
    intent_id: str,
    *,
    visible_status: str = "FAILED_CONFIRMED",
) -> str:
    """Serialize one ledger ID twice, with the blocking record first."""

    data = state.model_dump(mode="json")
    hidden = data["intent_ledger"][intent_id]
    visible = copy.deepcopy(hidden)
    visible["status"] = visible_status
    visible["transitions"][-1]["new_state"] = visible_status
    ledger_raw = _raw_object(
        [
            (intent_id, encode_state(hidden)),
            (intent_id, encode_state(visible)),
        ]
    )
    members: list[tuple[str, str]] = []
    for name, value in data.items():
        if name == "intent_ledger":
            members.append((name, ledger_raw))
            continue
        members.append((name, encode_state(value)))
        if name == "status" and value == AEPStatus.PAUSED.value:
            # The old lossy decoder must not get an independent PAUSED fence.
            members.append((name, encode_state(AEPStatus.PROCESSING.value)))
    return _raw_object(members)


def _state_with_hidden_phase2_envelope(state) -> str:
    """Put protected values first and lossy-decoder replacements last."""

    data = state.model_dump(mode="json")
    members: list[tuple[str, str]] = []
    for name, value in data.items():
        members.append((name, encode_state(value)))
        if name == "status":
            members.append((name, encode_state(AEPStatus.IDLE.value)))
        elif name == "intent_ledger":
            members.append((name, "{}"))
        elif name == "phase2_managed":
            members.append((name, "null"))
    return _raw_object(members)


def _state_with_duplicate_unknown_member(raw: str) -> str:
    assert raw.endswith("}")
    return raw[:-1] + ',"future_field":1,"future_field":1}'


def _state_with_duplicate_existing_member(raw: str, name: str) -> str:
    """Append an equal duplicate so a lossy decoder sees the original map."""

    assert raw.endswith("}")
    value = json.loads(raw)[name]
    return raw[:-1] + f",{encode_state(name)}:{encode_state(value)}}}"


async def _assert_ambiguous_rejection_preserves_state(
    redis_client, execution_id: str, operation
) -> None:
    key = f"aep:state:{execution_id}"
    raw_before = await redis_client.get(key)
    ttl_before = await redis_client.pttl(key)
    assert raw_before is not None
    assert ttl_before > 0
    started = time.monotonic()
    with pytest.raises(AmbiguousStateError, match="ambiguous serialized state"):
        await operation()
    elapsed_ms = (time.monotonic() - started) * 1000
    assert await redis_client.get(key) == raw_before
    ttl_after = await redis_client.pttl(key)
    assert ttl_after <= ttl_before
    assert ttl_after >= ttl_before - elapsed_ms - 1_000


@pytest.mark.asyncio
async def test_p2001_duplicate_intent_member_cannot_permit_same_step_attempt(
    redis_client, storage_adapter, lock_manager
):
    execution_id, _ = await _seed(storage_adapter, lock_manager, keep_lock=False)
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    runner = _runner(redis_client, lock_manager, harness)
    first = await runner.execute(
        execution_id=execution_id,
        step_id="step-a",
        request=_request(target="redacted-step-a"),
    )
    assert first.status is IntentStatus.FIRED_CONFIRMED
    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    ambiguous = _state_with_hidden_blocker(state, first.intent_id)
    key = f"aep:state:{execution_id}"
    await redis_client.set(key, ambiguous, keepttl=True, xx=True)
    barrier = _CountingBarrier()
    runner.barrier = barrier

    await _assert_ambiguous_rejection_preserves_state(
        redis_client,
        execution_id,
        lambda: runner.execute(
            execution_id=execution_id,
            step_id="step-a",
            request=_request(target="redacted-step-a"),
        ),
    )
    assert len(harness.oracle.calls) == 1
    assert barrier.calls == 0
    assert ambiguous.count(first.intent_id) >= 2
    assert json.loads(ambiguous)["version"] == state.version


@pytest.mark.parametrize(
    "blocking_status",
    [
        IntentStatus.ABOUT_TO_FIRE,
        IntentStatus.FIRED_UNCONFIRMED,
        IntentStatus.PERMANENTLY_AMBIGUOUS,
    ],
)
@pytest.mark.asyncio
async def test_p2002_duplicate_member_cannot_hide_execution_wide_blocker(
    redis_client, storage_adapter, lock_manager, blocking_status
):
    execution_id, token, intent, _ = await _state_with_intent_status(
        redis_client, storage_adapter, lock_manager, blocking_status
    )
    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    ambiguous = _state_with_hidden_blocker(state, intent.intent_id)
    key = f"aep:state:{execution_id}"
    await redis_client.set(key, ambiguous, keepttl=True, xx=True)
    assert await lock_manager.release_lock(execution_id, token)
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    runner = _runner(redis_client, lock_manager, harness)
    barrier = _CountingBarrier()
    runner.barrier = barrier

    await _assert_ambiguous_rejection_preserves_state(
        redis_client,
        execution_id,
        lambda: runner.execute(
            execution_id=execution_id,
            step_id="step-b",
            request=_request(target="redacted-step-b"),
        ),
    )
    assert harness.oracle.calls == ()
    assert barrier.calls == 0
    assert blocking_status.value in ambiguous


@pytest.mark.asyncio
async def test_p2003_duplicate_members_cannot_hide_phase2_state_from_save_state(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token, intent, version = await _state_with_intent_status(
        redis_client,
        storage_adapter,
        lock_manager,
        IntentStatus.FIRED_UNCONFIRMED,
    )
    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    assert state.status is AEPStatus.PAUSED
    ambiguous = _state_with_hidden_phase2_envelope(state)
    key = f"aep:state:{execution_id}"
    await redis_client.set(key, ambiguous, keepttl=True, xx=True)
    replacement = AEPExecutionState(
        execution_id=execution_id,
        status=AEPStatus.IDLE,
        version=version + 1,
    )

    await _assert_ambiguous_rejection_preserves_state(
        redis_client,
        execution_id,
        lambda: storage_adapter.save_state(
            replacement,
            expected_version=version,
            lock_token=token,
            ttl_seconds=60,
        ),
    )
    assert intent.intent_id in ambiguous
    assert '"phase2_managed":"intent-ledger-v1"' in ambiguous
    assert '"status":"PAUSED"' in ambiguous
    assert await redis_client.ttl(key) > 60


@pytest.mark.asyncio
async def test_phase2_creation_cas_rejects_duplicate_injected_after_python_read(
    redis_client, storage_adapter, lock_manager, monkeypatch
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    original_get = store.get_execution
    key = f"aep:state:{execution_id}"
    injected: dict[str, str] = {}

    async def read_then_inject(*args, **kwargs):
        current = await original_get(*args, **kwargs)
        raw = await redis_client.get(key)
        injected["raw"] = _state_with_duplicate_existing_member(raw, "version")
        await redis_client.set(key, injected["raw"], keepttl=True, xx=True)
        return current

    monkeypatch.setattr(store, "get_execution", read_then_inject)
    ttl_before = await redis_client.pttl(key)
    with pytest.raises(AmbiguousStateError, match="ambiguous serialized state"):
        await _create(store, execution_id, token, expected_version=1)
    assert await redis_client.get(key) == injected["raw"]
    assert await redis_client.pttl(key) <= ttl_before


@pytest.mark.asyncio
async def test_phase2_transition_cas_rejects_duplicate_injected_after_python_read(
    redis_client, storage_adapter, lock_manager, monkeypatch
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create(store, execution_id, token, expected_version=1)
    original_get = store.get_execution
    key = f"aep:state:{execution_id}"
    injected: dict[str, str] = {}

    async def read_then_inject(*args, **kwargs):
        current = await original_get(*args, **kwargs)
        raw = await redis_client.get(key)
        injected["raw"] = _state_with_duplicate_existing_member(raw, "version")
        await redis_client.set(key, injected["raw"], keepttl=True, xx=True)
        return current

    monkeypatch.setattr(store, "get_execution", read_then_inject)
    ttl_before = await redis_client.pttl(key)
    with pytest.raises(AmbiguousStateError, match="ambiguous serialized state"):
        await store.transition_intent(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            expected_version=2,
            lock_token=token,
            new_status=IntentStatus.FIRED_CONFIRMED,
            actor="regression:test",
            reason="must-not-commit",
        )
    assert await redis_client.get(key) == injected["raw"]
    assert await redis_client.pttl(key) <= ttl_before


@pytest.mark.asyncio
async def test_preflight_rejects_duplicate_state_before_provider_dispatch(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create(store, execution_id, token, expected_version=1)
    key = f"aep:state:{execution_id}"
    raw = await redis_client.get(key)
    await redis_client.set(
        key, _state_with_duplicate_unknown_member(raw), keepttl=True, xx=True
    )
    await _assert_ambiguous_rejection_preserves_state(
        redis_client,
        execution_id,
        lambda: store.preflight(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            prepared_state_version=intent.prepared_state_version,
            lock_token=token,
            required_ttl_ms=1,
            request_binding=intent.request_binding,
        ),
    )


@pytest.mark.asyncio
async def test_ambiguous_read_is_quarantined_without_rewriting_state(
    redis_client, storage_adapter, lock_manager
):
    execution_id, _ = await _seed(storage_adapter, lock_manager)
    key = f"aep:state:{execution_id}"
    raw = _state_with_duplicate_unknown_member(await redis_client.get(key))
    await redis_client.set(key, raw, keepttl=True, xx=True)

    await _assert_ambiguous_rejection_preserves_state(
        redis_client,
        execution_id,
        lambda: storage_adapter.get_state(execution_id),
    )
    poison_keys = [
        item
        async for item in redis_client.scan_iter(
            match=f"aep:poison:{execution_id}:*", count=100
        )
    ]
    assert poison_keys
    record = json.loads(await redis_client.get(poison_keys[-1]))
    assert record["reason"] == "ambiguous-serialization"


@pytest.mark.asyncio
async def test_recovery_rejects_ambiguous_state_before_any_readback(
    redis_client, storage_adapter, lock_manager
):
    execution_id, _, _ = await _seed_stale_about(
        storage_adapter, lock_manager, redis_client
    )
    key = f"aep:state:{execution_id}"
    ambiguous = _state_with_duplicate_unknown_member(await redis_client.get(key))
    await redis_client.set(key, ambiguous, keepttl=True, xx=True)
    harness = MockConnectorHarness()

    await _assert_ambiguous_rejection_preserves_state(
        redis_client,
        execution_id,
        lambda: _service(redis_client, lock_manager, harness).recover_intent(
            execution_id, "00000000-0000-4000-8000-000000000000"
        ),
    )
    assert harness.oracle.readbacks == ()
