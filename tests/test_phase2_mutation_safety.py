"""P2-001/P2-002/P2-003 atomic mutation-safety regressions.

These tests deliberately exercise current-token/current-version callers.  A
stale caller being fenced is not evidence that the requested invariant holds.
Every rejection assertion also compares the serialized Redis value so a
failed operation cannot hide a status, version, ledger, or audit mutation.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid

import pytest

from src.core.durability import FakeDurabilityBarrier
from src.core.exceptions import (
    LockAcquisitionError,
    Phase2StateProtectionError,
    StaleWriteError,
)
from src.core.intent_workflow import ConnectorPolicy, WriteAheadRunner
from src.core.intents import (
    ExecutionIntentFenceError,
    IntentCreationEligibilityError,
    IntentInvariantError,
    IntentLedgerStore,
    IntentStatus,
    Phase2ExecutionState,
)
from src.core.storage import AEPExecutionState, AEPStatus
from tests.mock_connector import MockConnectorHarness, ResponseMode
from tests.request_binding_helpers import (
    prepared_binding,
    test_binding_service as _binding_service,
    test_request as _request,
)


CONNECTOR = "mock.non-idempotent.v1/mutate"
FINGERPRINT = "f" * 64
PHASE2_TTL_SECONDS = 31 * 24 * 60 * 60
MARKER_FIELD = "phase2_managed"
MARKER_VALUE = "intent-ledger-v1"


def _eligibility_error():
    return IntentCreationEligibilityError


def _fence_error():
    return ExecutionIntentFenceError


def _phase2_protection_error():
    return Phase2StateProtectionError


async def _seed(
    storage_adapter,
    lock_manager,
    *,
    status: AEPStatus = AEPStatus.IDLE,
    keep_lock: bool = True,
):
    execution_id = str(uuid.uuid4())
    token = await lock_manager.acquire_lock(execution_id, ttl_seconds=60)
    assert token is not None
    await storage_adapter.save_state(
        AEPExecutionState(execution_id=execution_id, status=status),
        expected_version=0,
        lock_token=token,
        ttl_seconds=3600,
    )
    if not keep_lock:
        assert await lock_manager.release_lock(execution_id, token)
    return execution_id, token


async def _create(
    store: IntentLedgerStore,
    execution_id: str,
    token: str,
    *,
    expected_version: int,
    step_id: str = "step-a",
    risk_acceptance_id: str | None = None,
):
    now_ms = int((await store.redis_time()) * 1000)
    binding, intent_id, correlation_id = await prepared_binding(
        execution_id=execution_id,
        step_id=step_id,
        connector_operation=CONNECTOR,
        target=f"redacted-{step_id}",
        created_at_ms=now_ms,
    )
    return await store.create_intent(
        execution_id=execution_id,
        expected_version=expected_version,
        lock_token=token,
        step_id=step_id,
        connector=CONNECTOR,
        target=binding.safe_descriptor.redacted_target,
        request_fingerprint=binding.request_fingerprint,
        request_binding=binding,
        client_timeout_seconds=0.01,
        settlement_lag_seconds=0,
        buffer_margin_seconds=15,
        actor="regression:test",
        risk_acceptance_id=risk_acceptance_id,
        intent_id=intent_id,
        correlation_id=correlation_id,
    )


async def _state_with_intent_status(
    redis_client,
    storage_adapter,
    lock_manager,
    status: IntentStatus,
    *,
    step_id: str = "step-a",
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create(
        store,
        execution_id,
        token,
        expected_version=1,
        step_id=step_id,
    )
    version = 2
    if status is IntentStatus.ABOUT_TO_FIRE:
        return execution_id, token, intent, version
    if status is IntentStatus.PERMANENTLY_AMBIGUOUS:
        await store.transition_intent(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            expected_version=version,
            lock_token=token,
            new_status=IntentStatus.FIRED_UNCONFIRMED,
            actor="regression:test",
            reason="ambiguous",
        )
        version += 1
    await store.transition_intent(
        execution_id=execution_id,
        intent_id=intent.intent_id,
        expected_version=version,
        lock_token=token,
        new_status=status,
        actor="regression:test",
        reason=f"setup-{status.value.lower()}",
    )
    return execution_id, token, intent, version + 1


async def _raw_and_ttl(redis_client, execution_id: str):
    key = f"aep:state:{execution_id}"
    return await redis_client.get(key), await redis_client.pttl(key)


async def _assert_rejected_without_redis_change(
    redis_client,
    execution_id: str,
    error_type,
    operation,
):
    raw_before, ttl_before = await _raw_and_ttl(redis_client, execution_id)
    assert raw_before is not None
    assert ttl_before > 0
    started = time.monotonic()
    with pytest.raises(error_type):
        await operation()
    elapsed_ms = (time.monotonic() - started) * 1000
    raw_after, ttl_after = await _raw_and_ttl(redis_client, execution_id)
    assert raw_after == raw_before
    assert json.loads(raw_after)["version"] == json.loads(raw_before)["version"]
    assert ttl_after <= ttl_before
    assert ttl_after >= ttl_before - elapsed_ms - 1_000


def _runner(redis_client, lock_manager, harness, *, lock_manager_override=None):
    return WriteAheadRunner(
        store=IntentLedgerStore(redis_client),
        lock_manager=lock_manager_override or lock_manager,
        connector=harness.connector,
        barrier=FakeDurabilityBarrier(),
        policy=ConnectorPolicy(
            client_timeout_seconds=0.01,
            settlement_lag_seconds=0,
            buffer_margin_seconds=15,
            lock_ttl_seconds=30,
            durability_timeout_ms=100,
            lease_acquire_attempts=1,
        ),
        connector_name=CONNECTOR,
        binding_service=_binding_service(CONNECTOR),
        allow_test_barrier=True,
        allow_test_dispatch=True,
    )


# ---------------------------------------------------------------------------
# P2-001: normal attempt eligibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p2001_first_attempt_is_allowed_and_sets_phase2_marker_atomically(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    intent = await _create(
        IntentLedgerStore(redis_client),
        execution_id,
        token,
        expected_version=1,
    )

    raw = json.loads(await redis_client.get(f"aep:state:{execution_id}"))
    assert intent.attempt == 1
    assert raw[MARKER_FIELD] == MARKER_VALUE
    assert raw["version"] == 2
    assert list(raw["intent_ledger"]) == [intent.intent_id]


@pytest.mark.asyncio
async def test_p2001_failed_confirmed_permits_exactly_one_next_normal_attempt(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token, first, version = await _state_with_intent_status(
        redis_client,
        storage_adapter,
        lock_manager,
        IntentStatus.FAILED_CONFIRMED,
    )
    store = IntentLedgerStore(redis_client)
    second = await _create(
        store,
        execution_id,
        token,
        expected_version=version,
    )
    assert second.attempt == 2

    current = await store.get_execution(execution_id)
    assert current is not None
    assert sorted(item.attempt for item in current.intent_ledger.values()) == [1, 2]
    await _assert_rejected_without_redis_change(
        redis_client,
        execution_id,
        _fence_error(),
        lambda: _create(
            store,
            execution_id,
            token,
            expected_version=current.version,
        ),
    )
    assert first.intent_id in current.intent_ledger


@pytest.mark.parametrize(
    ("status", "error_factory"),
    [
        (IntentStatus.FIRED_CONFIRMED, _eligibility_error),
        (IntentStatus.ABOUT_TO_FIRE, _fence_error),
        (IntentStatus.FIRED_UNCONFIRMED, _fence_error),
        (IntentStatus.PERMANENTLY_AMBIGUOUS, _fence_error),
    ],
)
@pytest.mark.asyncio
async def test_p2001_ineligible_predecessor_rejects_current_caller_unchanged(
    redis_client,
    storage_adapter,
    lock_manager,
    status,
    error_factory,
):
    execution_id, token, _, version = await _state_with_intent_status(
        redis_client, storage_adapter, lock_manager, status
    )
    store = IntentLedgerStore(redis_client)
    await _assert_rejected_without_redis_change(
        redis_client,
        execution_id,
        error_factory(),
        lambda: _create(
            store,
            execution_id,
            token,
            expected_version=version,
        ),
    )


@pytest.mark.asyncio
async def test_p2001_raw_risk_acceptance_id_cannot_bypass_permanent_ambiguity(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token, _, version = await _state_with_intent_status(
        redis_client,
        storage_adapter,
        lock_manager,
        IntentStatus.PERMANENTLY_AMBIGUOUS,
    )
    store = IntentLedgerStore(redis_client)
    await _assert_rejected_without_redis_change(
        redis_client,
        execution_id,
        _fence_error(),
        lambda: _create(
            store,
            execution_id,
            token,
            expected_version=version,
            risk_acceptance_id="forged-raw-risk-id",
        ),
    )


@pytest.mark.asyncio
async def test_p2001_confirmed_success_rejects_runner_before_second_provider_call(
    redis_client, storage_adapter, lock_manager
):
    execution_id, _ = await _seed(
        storage_adapter, lock_manager, keep_lock=False
    )
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
    raw_before = await redis_client.get(f"aep:state:{execution_id}")

    with pytest.raises(_eligibility_error()):
        await runner.execute(
            execution_id=execution_id,
            step_id="step-a",
            request=_request(target="redacted-step-a"),
        )

    assert len(harness.oracle.calls) == 1
    assert await redis_client.get(f"aep:state:{execution_id}") == raw_before


class _SharedCurrentTokenLockManager:
    """Adversarial harness that lets two callers reach the creation CAS."""

    def __init__(self, token: str):
        self.token = token

    async def acquire_lock(self, execution_id, ttl_seconds=60):
        return self.token

    async def release_lock(self, execution_id, lock_token):
        return True


@pytest.mark.asyncio
async def test_p2001_two_racing_callers_after_failed_create_at_most_one_attempt(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token, _, version = await _state_with_intent_status(
        redis_client,
        storage_adapter,
        lock_manager,
        IntentStatus.FAILED_CONFIRMED,
    )
    assert version == 3
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    shared = _SharedCurrentTokenLockManager(token)
    runners = [
        _runner(
            redis_client,
            lock_manager,
            harness,
            lock_manager_override=shared,
        )
        for _ in range(2)
    ]

    outcomes = await asyncio.gather(
        *(
            runner.execute(
                execution_id=execution_id,
                step_id="step-a",
                request=_request(target="redacted-step-a"),
            )
            for runner in runners
        ),
        return_exceptions=True,
    )

    assert sum(not isinstance(item, BaseException) for item in outcomes) == 1
    rejected = [item for item in outcomes if isinstance(item, BaseException)]
    assert len(rejected) == 1
    assert isinstance(
        rejected[0],
        (StaleWriteError, _eligibility_error(), _fence_error()),
    )
    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    assert sorted(item.attempt for item in state.intent_ledger.values()) == [1, 2]
    assert len(harness.oracle.calls) == 1


# ---------------------------------------------------------------------------
# P2-002: execution-wide blocking fence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "blocking_status",
    [
        IntentStatus.ABOUT_TO_FIRE,
        IntentStatus.FIRED_UNCONFIRMED,
        IntentStatus.PERMANENTLY_AMBIGUOUS,
    ],
)
@pytest.mark.asyncio
async def test_p2002_blocking_step_a_fences_step_b_in_same_atomic_creation(
    redis_client,
    storage_adapter,
    lock_manager,
    blocking_status,
):
    execution_id, token, old, version = await _state_with_intent_status(
        redis_client, storage_adapter, lock_manager, blocking_status
    )
    store = IntentLedgerStore(redis_client)
    await _assert_rejected_without_redis_change(
        redis_client,
        execution_id,
        _fence_error(),
        lambda: _create(
            store,
            execution_id,
            token,
            expected_version=version,
            step_id="step-b",
        ),
    )
    state = await store.get_execution(execution_id)
    assert state is not None
    assert set(state.intent_ledger) == {old.intent_id}
    assert state.intent_ledger[old.intent_id].status is blocking_status


@pytest.mark.asyncio
async def test_p2002_paused_execution_without_blocking_ledger_fails_closed(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(
        storage_adapter, lock_manager, status=AEPStatus.PAUSED
    )
    await _assert_rejected_without_redis_change(
        redis_client,
        execution_id,
        _fence_error(),
        lambda: _create(
            IntentLedgerStore(redis_client),
            execution_id,
            token,
            expected_version=1,
            step_id="step-b",
        ),
    )
    state = await storage_adapter.get_state(execution_id)
    assert state is not None
    assert state.status is AEPStatus.PAUSED
    assert state.intent_ledger == {}


@pytest.mark.parametrize(
    "blocking_status",
    [
        IntentStatus.ABOUT_TO_FIRE,
        IntentStatus.FIRED_UNCONFIRMED,
        IntentStatus.PERMANENTLY_AMBIGUOUS,
    ],
)
@pytest.mark.asyncio
async def test_p2002_global_fence_rejects_runner_with_zero_provider_calls(
    redis_client, storage_adapter, lock_manager, blocking_status
):
    execution_id, token, old, _ = await _state_with_intent_status(
        redis_client,
        storage_adapter,
        lock_manager,
        blocking_status,
    )
    assert await lock_manager.release_lock(execution_id, token)
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    raw_before = await redis_client.get(f"aep:state:{execution_id}")

    with pytest.raises(_fence_error()):
        await _runner(redis_client, lock_manager, harness).execute(
            execution_id=execution_id,
            step_id="step-b",
            request=_request(target="redacted-step-b"),
        )

    assert harness.oracle.calls == ()
    assert await redis_client.get(f"aep:state:{execution_id}") == raw_before
    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    if blocking_status is not IntentStatus.ABOUT_TO_FIRE:
        assert state.status is AEPStatus.PAUSED
    assert set(state.intent_ledger) == {old.intent_id}


@pytest.mark.parametrize(
    "terminal_status",
    [IntentStatus.FIRED_CONFIRMED, IntentStatus.FAILED_CONFIRMED],
)
@pytest.mark.asyncio
async def test_p2002_terminal_states_do_not_create_unintended_global_fence(
    redis_client,
    storage_adapter,
    lock_manager,
    terminal_status,
):
    execution_id, token, first, version = await _state_with_intent_status(
        redis_client, storage_adapter, lock_manager, terminal_status
    )
    second = await _create(
        IntentLedgerStore(redis_client),
        execution_id,
        token,
        expected_version=version,
        step_id="step-b",
    )
    assert first.step_id == "step-a"
    assert second.step_id == "step-b"
    assert second.attempt == 1


# ---------------------------------------------------------------------------
# P2-003: Phase 1 writer cannot mutate Phase 2 state
# ---------------------------------------------------------------------------


def _delete_ledger(data, intent_id):
    data["intent_ledger"] = {}


def _change_immutable(data, intent_id):
    data["intent_ledger"][intent_id]["target"] = "changed-target"


def _change_intent_status(data, intent_id):
    data["intent_ledger"][intent_id]["status"] = "FAILED_CONFIRMED"


def _change_transition_history(data, intent_id):
    data["intent_ledger"][intent_id]["transitions"][0]["reason"] = "rewritten"


def _unpause_to_idle(data, intent_id):
    data["status"] = AEPStatus.IDLE


def _unpause_to_processing(data, intent_id):
    data["status"] = AEPStatus.PROCESSING


def _remove_marker(data, intent_id):
    data.pop(MARKER_FIELD, None)


def _change_marker(data, intent_id):
    data[MARKER_FIELD] = "forged-phase2-mode"


def _no_payload_change(data, intent_id):
    pass


@pytest.mark.parametrize(
    ("mutation", "ttl_seconds"),
    [
        (_delete_ledger, PHASE2_TTL_SECONDS),
        (_change_immutable, PHASE2_TTL_SECONDS),
        (_change_intent_status, PHASE2_TTL_SECONDS),
        (_change_transition_history, PHASE2_TTL_SECONDS),
        (_unpause_to_idle, PHASE2_TTL_SECONDS),
        (_unpause_to_processing, PHASE2_TTL_SECONDS),
        (_remove_marker, PHASE2_TTL_SECONDS),
        (_change_marker, PHASE2_TTL_SECONDS),
        (_no_payload_change, 60),
    ],
    ids=[
        "delete-ledger",
        "immutable-field",
        "intent-status",
        "transition-history",
        "paused-to-idle",
        "paused-to-processing",
        "remove-marker",
        "change-marker",
        "shorten-retention",
    ],
)
@pytest.mark.asyncio
async def test_p2003_current_base_writer_cannot_modify_marked_phase2_state(
    redis_client,
    storage_adapter,
    lock_manager,
    mutation,
    ttl_seconds,
):
    execution_id, token, intent, version = await _state_with_intent_status(
        redis_client,
        storage_adapter,
        lock_manager,
        IntentStatus.FIRED_UNCONFIRMED,
    )
    current = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert current is not None
    assert current.version == version
    assert current.status is AEPStatus.PAUSED
    data = current.model_dump()
    mutation(data, intent.intent_id)
    data["version"] = current.version + 1
    candidate = AEPExecutionState.model_construct(**data)

    await _assert_rejected_without_redis_change(
        redis_client,
        execution_id,
        _phase2_protection_error(),
        lambda: storage_adapter.save_state(
            candidate,
            expected_version=current.version,
            lock_token=token,
            ttl_seconds=ttl_seconds,
        ),
    )


def _legacy_intent(intent_id: str):
    correlation_id = str(uuid.uuid4())
    return {
        "intent_id": intent_id,
        "step_id": "legacy-step",
        "attempt": 1,
        "connector": CONNECTOR,
        "target": "redacted-legacy-step",
        "request_fingerprint": FINGERPRINT,
        "correlation_id": correlation_id,
        "status": "ABOUT_TO_FIRE",
        "prepared_at": 1.0,
        "client_timeout_seconds": 1.0,
        "settlement_lag_seconds": 0.0,
        "reconcile_after": 17.0,
        "prepared_state_version": 1,
        "external_reference": None,
        "last_observation": None,
        "reconciliation": None,
        "transitions": [
            {
                "old_state": "NONE",
                "new_state": "ABOUT_TO_FIRE",
                "redis_time": 1.0,
                "actor": "legacy:test",
                "reason": "legacy-fixture",
                "evidence_hash": "a" * 64,
            }
        ],
        "risk_acceptance_id": None,
    }


@pytest.mark.parametrize("introduction", ["ledger", "marker"])
@pytest.mark.asyncio
async def test_p2003_base_writer_cannot_introduce_phase2_state(
    redis_client,
    storage_adapter,
    lock_manager,
    introduction,
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    current = await storage_adapter.get_state(execution_id)
    assert current is not None
    data = current.model_dump()
    data["version"] = 2
    if introduction == "ledger":
        intent_id = str(uuid.uuid4())
        data["intent_ledger"] = {intent_id: _legacy_intent(intent_id)}
    else:
        data[MARKER_FIELD] = MARKER_VALUE
    candidate = AEPExecutionState.model_construct(**data)

    await _assert_rejected_without_redis_change(
        redis_client,
        execution_id,
        _phase2_protection_error(),
        lambda: storage_adapter.save_state(
            candidate,
            expected_version=1,
            lock_token=token,
            ttl_seconds=PHASE2_TTL_SECONDS,
        ),
    )


@pytest.mark.asyncio
async def test_p2003_unmarked_legacy_phase2_ledger_is_protected(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    key = f"aep:state:{execution_id}"
    legacy = json.loads(await redis_client.get(key))
    legacy.pop(MARKER_FIELD, None)
    intent_id = str(uuid.uuid4())
    legacy["intent_ledger"] = {intent_id: _legacy_intent(intent_id)}
    await redis_client.set(key, json.dumps(legacy), keepttl=True, xx=True)

    raw_before_read = await redis_client.get(key)
    loaded = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert loaded is not None
    assert loaded.phase2_managed is None
    assert await redis_client.get(key) == raw_before_read

    replacement = AEPExecutionState(
        execution_id=execution_id,
        status=AEPStatus.IDLE,
        version=2,
    )
    await _assert_rejected_without_redis_change(
        redis_client,
        execution_id,
        _phase2_protection_error(),
        lambda: storage_adapter.save_state(
            replacement,
            expected_version=1,
            lock_token=token,
            ttl_seconds=3600,
        ),
    )


@pytest.mark.asyncio
async def test_p2003_unmarked_ledger_free_phase1_writes_still_pass(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    current = await storage_adapter.get_state(execution_id)
    assert current is not None
    current.version = 2
    current.status = AEPStatus.PROCESSING
    current.context_data = {"phase": 1}
    await storage_adapter.save_state(
        current,
        expected_version=1,
        lock_token=token,
        ttl_seconds=3600,
    )
    persisted = await storage_adapter.get_state(execution_id)
    assert persisted is not None
    assert persisted.version == 2
    assert persisted.status is AEPStatus.PROCESSING
    assert persisted.intent_ledger == {}
    assert getattr(persisted, MARKER_FIELD, None) is None


@pytest.mark.asyncio
async def test_p2003_phase2_transition_remains_allowed_and_marker_is_immutable(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    store = IntentLedgerStore(redis_client)
    intent = await _create(store, execution_id, token, expected_version=1)
    updated = await store.transition_intent(
        execution_id=execution_id,
        intent_id=intent.intent_id,
        expected_version=2,
        lock_token=token,
        new_status=IntentStatus.FIRED_CONFIRMED,
        actor="regression:test",
        reason="confirmed",
    )
    assert updated.status is IntentStatus.FIRED_CONFIRMED
    raw = json.loads(await redis_client.get(f"aep:state:{execution_id}"))
    assert raw[MARKER_FIELD] == MARKER_VALUE
    assert raw["version"] == 3

    current = await store.get_execution(execution_id)
    assert current is not None
    candidate = current.model_copy(deep=True)
    candidate.version = 4
    candidate.phase2_managed = "changed-mode"
    await _assert_rejected_without_redis_change(
        redis_client,
        execution_id,
        IntentInvariantError,
        lambda: store.commit_transition(
            candidate,
            intent_id=intent.intent_id,
            old_status=IntentStatus.FIRED_CONFIRMED.value,
            new_status=IntentStatus.FIRED_CONFIRMED,
            expected_version=3,
            lock_token=token,
        ),
    )


@pytest.mark.asyncio
async def test_p2003_base_writer_racing_phase2_transition_always_loses(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token, intent, version = await _state_with_intent_status(
        redis_client,
        storage_adapter,
        lock_manager,
        IntentStatus.ABOUT_TO_FIRE,
    )
    current = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert current is not None
    replacement_data = current.model_dump()
    replacement_data["version"] = version + 1
    replacement_data["status"] = AEPStatus.IDLE
    replacement_data["intent_ledger"] = {}
    replacement = AEPExecutionState.model_construct(**replacement_data)
    store = IntentLedgerStore(redis_client)

    base_result, phase2_result = await asyncio.gather(
        storage_adapter.save_state(
            replacement,
            expected_version=version,
            lock_token=token,
            ttl_seconds=60,
        ),
        store.transition_intent(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            expected_version=version,
            lock_token=token,
            new_status=IntentStatus.FIRED_CONFIRMED,
            actor="regression:test",
            reason="race-confirmed",
        ),
        return_exceptions=True,
    )

    # If the base CAS runs first it sees current marked state and returns the
    # protection error.  If the Phase 2 CAS wins first, the base caller is
    # stale.  Neither legal serialization can overwrite the transition.
    assert isinstance(
        base_result, (Phase2StateProtectionError, StaleWriteError)
    )
    assert not isinstance(phase2_result, BaseException)
    final = await store.get_execution(execution_id)
    assert final is not None
    assert final.version == version + 1
    assert final.intent_ledger[intent.intent_id].status is IntentStatus.FIRED_CONFIRMED


@pytest.mark.asyncio
async def test_stale_token_and_stale_version_precedence_remains_unchanged(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token = await _seed(storage_adapter, lock_manager)
    current = await storage_adapter.get_state(execution_id)
    assert current is not None
    candidate = current.model_copy(deep=True)
    candidate.version = 2

    with pytest.raises(LockAcquisitionError):
        await storage_adapter.save_state(
            candidate,
            expected_version=1,
            lock_token="stale-token",
            ttl_seconds=3600,
        )
    with pytest.raises(StaleWriteError):
        await storage_adapter.save_state(
            candidate,
            expected_version=0,
            lock_token=token,
            ttl_seconds=3600,
        )

    raw = json.loads(await redis_client.get(f"aep:state:{execution_id}"))
    assert raw["version"] == 1
    assert raw["intent_ledger"] == {}


@pytest.mark.asyncio
async def test_marked_phase2_state_preserves_stale_token_and_version_errors(
    redis_client, storage_adapter, lock_manager
):
    execution_id, token, _, version = await _state_with_intent_status(
        redis_client,
        storage_adapter,
        lock_manager,
        IntentStatus.ABOUT_TO_FIRE,
    )
    current = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert current is not None
    assert current.version == version
    candidate = AEPExecutionState.model_validate(current.model_dump())

    with pytest.raises(LockAcquisitionError):
        await storage_adapter.save_state(
            candidate,
            expected_version=version - 1,
            lock_token="stale-token",
            ttl_seconds=60,
        )
    with pytest.raises(StaleWriteError):
        await storage_adapter.save_state(
            candidate,
            expected_version=version - 1,
            lock_token=token,
            ttl_seconds=60,
        )

    persisted = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert persisted is not None
    assert persisted.version == version
    assert persisted.intent_ledger == current.intent_ledger
