"""Redis-backed Phase 2 recovery, reconciliation, and crash tests."""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest

from src.core.durability import FakeDurabilityBarrier
from src.core.exceptions import LockAcquisitionError
from src.core.intent_recovery import (
    IntentRecoveryService,
    RecoveryConnectorConfig,
)
from src.core.intent_workflow import ConnectorPolicy
from src.core.intents import (
    IntentAuditEntry,
    IntentLedgerStore,
    IntentStatus,
    Phase2ExecutionState,
)
from src.core.storage import AEPExecutionState, AEPStatus
from tests.mock_connector import (
    CrashPoint,
    CrashStyle,
    MockConnectorHarness,
    ReadbackResult,
    ReconciliationCapability,
    ResponseMode,
    SimulatedProcessCrash,
)
from tests.request_binding_helpers import verified_dispatch


CONNECTOR_NAME = "mock.non-idempotent.v1/mutate"
RECOVERY_POINTS = list(CrashPoint)[16:]


def _policy(**overrides):
    values = {
        "client_timeout_seconds": 0.01,
        "settlement_lag_seconds": 0,
        "buffer_margin_seconds": 15,
        "lock_ttl_seconds": 16,
        "durability_timeout_ms": 100,
        "lease_acquire_attempts": 1,
        "max_reconciliation_attempts": 8,
        "max_reconciliation_duration_seconds": 24 * 60 * 60,
        "backoff_base_seconds": 5,
        "backoff_cap_seconds": 300,
    }
    values.update(overrides)
    return ConnectorPolicy(**values)


async def _seed_stale_about(
    storage_adapter,
    lock_manager,
    redis_client,
    *,
    intent_id=None,
):
    execution_id = str(uuid.uuid4())
    intent_id = intent_id or str(uuid.uuid4())
    now = await IntentLedgerStore(redis_client).redis_time()
    prepared_at = now - 100
    transition = IntentAuditEntry(
        old_state="NONE",
        new_state=IntentStatus.ABOUT_TO_FIRE,
        redis_time=prepared_at,
        actor="runner:test-fixture",
        reason="write-ahead-before-dispatch",
        evidence_hash=hashlib.sha256(b"fixture").hexdigest(),
    )
    raw_intent = {
        "intent_id": intent_id,
        "step_id": "charge-card",
        "attempt": 1,
        "connector": CONNECTOR_NAME,
        "target": "customer-redacted-17",
        "request_fingerprint": "c" * 64,
        "correlation_id": str(uuid.uuid4()),
        "status": IntentStatus.ABOUT_TO_FIRE,
        "prepared_at": prepared_at,
        "client_timeout_seconds": 1,
        "settlement_lag_seconds": 0,
        "reconcile_after": prepared_at + 16,
        "prepared_state_version": 1,
        "external_reference": None,
        "last_observation": None,
        "reconciliation": None,
        "transitions": [transition.model_dump()],
        "risk_acceptance_id": None,
    }
    state = AEPExecutionState(
        execution_id=execution_id,
        status=AEPStatus.PROCESSING,
        version=1,
        intent_ledger={intent_id: raw_intent},
    )
    token = await lock_manager.acquire_lock(execution_id, ttl_seconds=60)
    assert token
    # Recovery needs a deliberately stale, pre-existing legacy Phase 2
    # record.  Inject it without the new marker; the Phase 1 writer is now
    # correctly forbidden from creating such ledger data.
    payload = state.model_dump(mode="json")
    payload.pop("phase2_managed", None)
    await redis_client.set(
        f"aep:state:{execution_id}",
        json.dumps(payload),
        ex=31 * 24 * 60 * 60,
    )
    assert await lock_manager.release_lock(execution_id, token)
    return execution_id, intent_id, token


def _service(redis_client, lock_manager, harness, *, policy=None):
    config = RecoveryConnectorConfig(
        connector=harness.connector,
        barrier=FakeDurabilityBarrier(),
        policy=policy or _policy(),
    )
    return IntentRecoveryService(
        store=IntentLedgerStore(redis_client),
        lock_manager=lock_manager,
        connectors={CONNECTOR_NAME: config},
        crash_injector=harness.crashes,
        crash_point_enum=CrashPoint,
    )


@pytest.mark.parametrize("point", RECOVERY_POINTS, ids=lambda point: point.value)
@pytest.mark.asyncio
async def test_recovery_crash_boundary_preserves_required_state_and_evidence(
    redis_client, storage_adapter, lock_manager, point
):
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    execution_id, intent_id, _ = await _seed_stale_about(
        storage_adapter, lock_manager, redis_client
    )
    harness.crashes.arm(point, style=CrashStyle.PROCESS_EXIT)
    with pytest.raises(SimulatedProcessCrash) as crashed:
        await _service(redis_client, lock_manager, harness).recover_intent(
            execution_id, intent_id
        )
    assert crashed.value.point is point

    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    status = state.intent_ledger[intent_id].status
    if point is CrashPoint.DURING_RECOVERY_BEFORE_CLAIM_CAS:
        assert status is IntentStatus.ABOUT_TO_FIRE
    elif point in {
        CrashPoint.AFTER_RECOVERY_CLAIM_BEFORE_READBACK,
        CrashPoint.AFTER_READBACK_BEFORE_RECOVERY_RESOLUTION_CAS,
        CrashPoint.DURING_RECOVERY_RESOLUTION_CAS,
    }:
        assert status is IntentStatus.FIRED_UNCONFIRMED
    else:
        # No external call exists and authoritative readback proves absence.
        assert status is IntentStatus.FAILED_CONFIRMED
    assert harness.oracle.calls == ()
    if not harness.oracle.readbacks:
        assert status not in {
            IntentStatus.FIRED_CONFIRMED,
            IntentStatus.FAILED_CONFIRMED,
        }


@pytest.mark.parametrize(
    ("capability", "readback", "expected"),
    [
        (
            ReconciliationCapability.AUTHORITATIVE_READBACK,
            ReadbackResult.APPLIED,
            IntentStatus.FIRED_CONFIRMED,
        ),
        (
            ReconciliationCapability.AUTHORITATIVE_READBACK,
            ReadbackResult.NOT_APPLIED,
            IntentStatus.FAILED_CONFIRMED,
        ),
        (
            ReconciliationCapability.AUTHORITATIVE_READBACK,
            ReadbackResult.UNKNOWN,
            IntentStatus.FIRED_UNCONFIRMED,
        ),
        (
            ReconciliationCapability.POSITIVE_ONLY_READBACK,
            ReadbackResult.APPLIED,
            IntentStatus.FIRED_CONFIRMED,
        ),
        (
            ReconciliationCapability.POSITIVE_ONLY_READBACK,
            ReadbackResult.UNKNOWN,
            IntentStatus.FIRED_UNCONFIRMED,
        ),
        (
            ReconciliationCapability.AUTHORITATIVE_READBACK,
            ReadbackResult.CONFLICT,
            IntentStatus.PERMANENTLY_AMBIGUOUS,
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconciliation_capability_result_mapping(
    redis_client,
    storage_adapter,
    lock_manager,
    capability,
    readback,
    expected,
):
    harness = MockConnectorHarness(capability=capability)
    harness.enqueue_readback(readback)
    execution_id, intent_id, _ = await _seed_stale_about(
        storage_adapter, lock_manager, redis_client
    )
    result = await _service(redis_client, lock_manager, harness).recover_intent(
        execution_id, intent_id
    )
    assert result is not None
    assert result.status is expected
    assert len(harness.oracle.readbacks) == 1
    assert len(harness.oracle.calls) == 0


@pytest.mark.asyncio
async def test_no_readback_becomes_permanently_ambiguous_without_query(
    redis_client, storage_adapter, lock_manager
):
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.NO_READBACK
    )
    execution_id, intent_id, _ = await _seed_stale_about(
        storage_adapter, lock_manager, redis_client
    )
    result = await _service(redis_client, lock_manager, harness).recover_intent(
        execution_id, intent_id
    )
    assert result is not None
    assert result.status is IntentStatus.PERMANENTLY_AMBIGUOUS
    assert harness.oracle.readbacks == ()
    assert harness.oracle.calls == ()


@pytest.mark.asyncio
async def test_reconciliation_attempt_limit_is_configurable_and_enforced(
    redis_client, storage_adapter, lock_manager
):
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.POSITIVE_ONLY_READBACK
    )
    harness.enqueue_readback(ReadbackResult.UNKNOWN)
    execution_id, intent_id, _ = await _seed_stale_about(
        storage_adapter, lock_manager, redis_client
    )
    result = await _service(
        redis_client,
        lock_manager,
        harness,
        policy=_policy(max_reconciliation_attempts=1),
    ).recover_intent(execution_id, intent_id)
    assert result is not None
    assert result.status is IntentStatus.PERMANENTLY_AMBIGUOUS


@pytest.mark.asyncio
async def test_scanner_finds_only_eligible_ambiguous_execution(
    redis_client, storage_adapter, lock_manager
):
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    execution_id, intent_id, _ = await _seed_stale_about(
        storage_adapter, lock_manager, redis_client
    )
    results = await _service(redis_client, lock_manager, harness).scan_once()
    assert [(item.execution_id, item.intent_id) for item in results] == [
        (execution_id, intent_id)
    ]


@pytest.mark.asyncio
async def test_late_original_worker_is_fenced_after_recovery_claim(
    redis_client, storage_adapter, lock_manager
):
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    execution_id, intent_id, original_token = await _seed_stale_about(
        storage_adapter, lock_manager, redis_client
    )
    harness.crashes.arm(
        CrashPoint.AFTER_RECOVERY_CLAIM_BEFORE_READBACK,
        style=CrashStyle.PROCESS_EXIT,
    )
    with pytest.raises(SimulatedProcessCrash):
        await _service(redis_client, lock_manager, harness).recover_intent(
            execution_id, intent_id
        )

    with pytest.raises(LockAcquisitionError, match="lease token"):
        await IntentLedgerStore(redis_client).transition_intent(
            execution_id=execution_id,
            intent_id=intent_id,
            expected_version=1,
            lock_token=original_token,
            new_status=IntentStatus.FIRED_CONFIRMED,
            actor="late-original",
            reason="late-response",
        )
    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    assert state.version == 2
    assert state.intent_ledger[intent_id].status is IntentStatus.FIRED_UNCONFIRMED


@pytest.mark.asyncio
async def test_recovery_never_repeats_mutation_and_only_reads_back(
    redis_client, storage_adapter, lock_manager
):
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    intent_id = str(uuid.uuid4())
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    await harness.connector.mutate(
        dispatch=await verified_dispatch(intent_id), client_timeout=0.01
    )
    assert len(harness.oracle.calls) == 1
    execution_id, _, _ = await _seed_stale_about(
        storage_adapter,
        lock_manager,
        redis_client,
        intent_id=intent_id,
    )

    result = await _service(redis_client, lock_manager, harness).recover_intent(
        execution_id, intent_id
    )
    assert result is not None
    assert result.status is IntentStatus.FIRED_CONFIRMED
    assert len(harness.oracle.calls) == 1
    assert len(harness.oracle.readbacks) == 1
