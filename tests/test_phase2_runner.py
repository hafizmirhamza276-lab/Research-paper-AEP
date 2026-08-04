"""Write-ahead runner and its 16 normal-worker crash boundaries."""

from __future__ import annotations

import uuid

import pytest

from src.core.durability import DurabilityCapabilityError, FakeDurabilityBarrier
from src.core.intent_workflow import (
    ConnectorPolicy,
    WriteAheadRunner,
    WriteAheadWorkflowError,
)
from src.core.intents import IntentLedgerStore, IntentStatus
from src.core.storage import AEPExecutionState, AEPStatus
from tests.mock_connector import (
    CallerEvidence,
    CrashPoint,
    CrashStyle,
    MockConnectorHarness,
    ResponseMode,
    SimulatedProcessCrash,
)
from tests.request_binding_helpers import (
    test_binding_service as _binding_service,
    test_request as _request,
)


FINGERPRINT = "b" * 64
RUNNER_POINTS = list(CrashPoint)[:16]


def test_connector_policy_defaults_match_design_limits():
    policy = ConnectorPolicy(client_timeout_seconds=1, lock_ttl_seconds=16)
    assert policy.max_reconciliation_attempts == 8
    assert policy.max_reconciliation_duration_seconds == 24 * 60 * 60
    assert policy.backoff_base_seconds == 5
    assert policy.backoff_cap_seconds == 300
    assert policy.backoff_ceiling(1) == 5
    assert policy.backoff_ceiling(20) == 300
    assert policy.definitive_success_evidence == {"DEFINITIVE_SUCCESS"}
    assert policy.definitive_failure_evidence == {"DEFINITIVE_FAILURE"}


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
    assert await lock_manager.release_lock(execution_id, token)
    return execution_id


def _scenario_for(point):
    if point in {
        CrashPoint.WHILE_WAITING_WITHOUT_RESPONSE,
        CrashPoint.AFTER_AMBIGUOUS_RESPONSE_BEFORE_RESOLUTION_CAS,
        CrashPoint.AFTER_DURABLE_FIRED_UNCONFIRMED_BEFORE_LEASE_RELEASE,
    }:
        return ResponseMode.TIMEOUT_NO_RESPONSE, True
    if point is CrashPoint.AFTER_CONCLUSIVE_FAILURE_BEFORE_RESOLUTION_CAS:
        return ResponseMode.DEFINITIVE_FAILURE, None
    return ResponseMode.DEFINITIVE_SUCCESS, None


def _expected_status(point):
    if point in {
        CrashPoint.BEFORE_LEASE_ACQUISITION,
        CrashPoint.AFTER_LEASE_ACQUISITION_BEFORE_INTENT_CAS,
        CrashPoint.DURING_INTENT_CAS,
    }:
        return None
    if point in {
        CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER,
        CrashPoint.AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT,
        CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION,
        CrashPoint.DURING_REQUEST_TRANSMISSION,
        CrashPoint.WHILE_WAITING_WITHOUT_RESPONSE,
        CrashPoint.AFTER_CONCLUSIVE_SUCCESS_BEFORE_RESOLUTION_CAS,
        CrashPoint.AFTER_CONCLUSIVE_FAILURE_BEFORE_RESOLUTION_CAS,
        CrashPoint.AFTER_AMBIGUOUS_RESPONSE_BEFORE_RESOLUTION_CAS,
        CrashPoint.DURING_RESOLUTION_CAS,
    }:
        return IntentStatus.ABOUT_TO_FIRE
    if point is CrashPoint.AFTER_DURABLE_FIRED_UNCONFIRMED_BEFORE_LEASE_RELEASE:
        return IntentStatus.FIRED_UNCONFIRMED
    if point in {
        CrashPoint.AFTER_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER,
        CrashPoint.DURING_RESOLUTION_DURABILITY_BARRIER,
        CrashPoint.AFTER_DURABLE_CONFIRMED_RESOLUTION_BEFORE_LEASE_RELEASE,
    }:
        return IntentStatus.FIRED_CONFIRMED
    raise AssertionError(point)


def _runner(redis_client, lock_manager, harness):
    return WriteAheadRunner(
        store=IntentLedgerStore(redis_client),
        lock_manager=lock_manager,
        connector=harness.connector,
        barrier=FakeDurabilityBarrier(),
        policy=ConnectorPolicy(
            client_timeout_seconds=0.01,
            settlement_lag_seconds=0,
            buffer_margin_seconds=15,
            lock_ttl_seconds=16,
            durability_timeout_ms=100,
            lease_acquire_attempts=1,
            max_reconciliation_attempts=8,
            max_reconciliation_duration_seconds=24 * 60 * 60,
            backoff_base_seconds=5,
            backoff_cap_seconds=300,
        ),
        connector_name="mock.non-idempotent.v1/mutate",
        binding_service=_binding_service(),
        crash_injector=harness.crashes,
        crash_point_enum=CrashPoint,
        allow_test_barrier=True,
        allow_test_dispatch=True,
    )


@pytest.mark.parametrize("point", RUNNER_POINTS, ids=lambda point: point.value)
@pytest.mark.asyncio
async def test_runner_crash_boundary_preserves_required_state_and_evidence(
    redis_client, storage_adapter, lock_manager, point
):
    execution_id = await _seed(storage_adapter, lock_manager)
    harness = MockConnectorHarness()
    mode, truth = _scenario_for(point)
    harness.enqueue_call(mode, mutation_applied=truth)
    harness.crashes.arm(point, style=CrashStyle.PROCESS_EXIT)

    with pytest.raises(SimulatedProcessCrash) as crashed:
        await _runner(redis_client, lock_manager, harness).execute(
            execution_id=execution_id,
            step_id="charge-card",
            request=_request(target="customer-redacted-17"),
        )
    assert crashed.value.point is point

    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    expected = _expected_status(point)
    if expected is None:
        assert state.intent_ledger == {}
    else:
        assert len(state.intent_ledger) == 1
        assert next(iter(state.intent_ledger.values())).status is expected

    for call in harness.oracle.calls:
        caller_could_not_prove = (
            call.caller_evidence in {CallerEvidence.NONE, CallerEvidence.AMBIGUOUS}
            or not call.call_finished
        )
        if caller_could_not_prove and state.intent_ledger:
            assert next(iter(state.intent_ledger.values())).status not in {
                IntentStatus.FIRED_CONFIRMED,
                IntentStatus.FAILED_CONFIRMED,
            }


@pytest.mark.parametrize(
    ("mode", "applied", "expected"),
    [
        (ResponseMode.DEFINITIVE_SUCCESS, None, IntentStatus.FIRED_CONFIRMED),
        (ResponseMode.DEFINITIVE_FAILURE, None, IntentStatus.FAILED_CONFIRMED),
        (ResponseMode.TIMEOUT_NO_RESPONSE, True, IntentStatus.FIRED_UNCONFIRMED),
        (
            ResponseMode.CONNECTION_DROP_MID_TRANSMISSION,
            False,
            IntentStatus.FIRED_UNCONFIRMED,
        ),
        (ResponseMode.CONFLICTING_EVIDENCE, True, IntentStatus.FIRED_UNCONFIRMED),
    ],
)
@pytest.mark.asyncio
async def test_runner_classifies_connector_response_once(
    redis_client, storage_adapter, lock_manager, mode, applied, expected
):
    execution_id = await _seed(storage_adapter, lock_manager)
    harness = MockConnectorHarness()
    harness.enqueue_call(mode, mutation_applied=applied)
    result = await _runner(redis_client, lock_manager, harness).execute(
        execution_id=execution_id,
        step_id="charge-card",
        request=_request(target="customer-redacted-17"),
    )
    assert result.status is expected
    assert len(harness.oracle.calls) == 1


@pytest.mark.asyncio
async def test_runner_applied_mid_transmission_drop_stays_unconfirmed_without_replay(
    redis_client, storage_adapter, lock_manager, monkeypatch
):
    execution_id = await _seed(storage_adapter, lock_manager)
    harness = MockConnectorHarness()
    harness.enqueue_call(
        ResponseMode.CONNECTION_DROP_MID_TRANSMISSION,
        mutation_applied=True,
    )
    connector_exceptions = []
    mutate = harness.connector.mutate

    async def observe_connector_exception(*, dispatch, client_timeout):
        try:
            return await mutate(
                dispatch=dispatch,
                client_timeout=client_timeout,
            )
        except Exception as exc:
            connector_exceptions.append(exc)
            raise

    monkeypatch.setattr(harness.connector, "mutate", observe_connector_exception)

    result = await _runner(redis_client, lock_manager, harness).execute(
        execution_id=execution_id,
        step_id="charge-card",
        request=_request(target="customer-redacted-17"),
    )

    calls_after_runner = harness.oracle.calls
    assert len(calls_after_runner) == 1
    truth = calls_after_runner[0]
    assert truth.mode is ResponseMode.CONNECTION_DROP_MID_TRANSMISSION
    assert truth.mutation_applied is True
    assert truth.caller_evidence is CallerEvidence.AMBIGUOUS

    assert len(connector_exceptions) == 1
    assert not hasattr(connector_exceptions[0], "mutation_applied")
    assert result.status is IntentStatus.FIRED_UNCONFIRMED
    assert result.external_reference is None
    assert result.last_observation is not None
    assert result.last_observation.evidence_class == "AMBIGUOUS"
    assert "mutation_applied" not in result.model_dump_json()

    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    persisted = state.intent_ledger[result.intent_id]
    assert persisted.status is IntentStatus.FIRED_UNCONFIRMED
    persisted_statuses = {transition.new_state for transition in persisted.transitions}
    assert IntentStatus.FIRED_CONFIRMED not in persisted_statuses
    assert IntentStatus.FAILED_CONFIRMED not in persisted_statuses
    assert "mutation_applied" not in persisted.model_dump_json()

    raw_state = await redis_client.get(f"aep:state:{execution_id}")
    assert raw_state is not None
    assert IntentStatus.FIRED_CONFIRMED.value not in raw_state
    assert IntentStatus.FAILED_CONFIRMED.value not in raw_state
    assert harness.oracle.calls == calls_after_runner


class _FailThenSucceedBarrier:
    test_only = True

    def __init__(self):
        self.calls = 0

    async def confirm_durable(self, connection, timeout_ms):
        self.calls += 1
        return self.calls > 1


@pytest.mark.asyncio
async def test_intent_durability_failure_records_no_dispatch_failure(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    barrier = _FailThenSucceedBarrier()
    runner = _runner(redis_client, lock_manager, harness)
    runner.barrier = barrier
    with pytest.raises(Exception, match="durability barrier"):
        await runner.execute(
            execution_id=execution_id,
            step_id="charge-card",
            request=_request(target="customer-redacted-17"),
        )
    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    assert next(iter(state.intent_ledger.values())).status is IntentStatus.FAILED_CONFIRMED
    assert harness.oracle.calls == ()
    assert barrier.calls == 2


@pytest.mark.asyncio
async def test_production_dispatch_rejects_test_only_fake_barrier(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    runner = _runner(redis_client, lock_manager, harness)
    runner.allow_test_barrier = False

    with pytest.raises(WriteAheadWorkflowError, match="test-only"):
        await runner.execute(
            execution_id=execution_id,
            step_id="charge-card",
            request=_request(target="customer-redacted-17"),
        )

    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    assert state.intent_ledger == {}
    assert harness.oracle.calls == ()


class _RejectingStartupBarrier:
    test_only = False

    async def validate_startup(self, redis_client):
        raise DurabilityCapabilityError("scripted capability rejection")

    async def confirm_durable(self, connection, timeout_ms):
        raise AssertionError("barrier command must not run after rejected startup")


@pytest.mark.asyncio
async def test_startup_capability_failure_disables_non_idempotent_dispatch(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    runner = _runner(redis_client, lock_manager, harness)
    runner.allow_test_barrier = False
    runner.barrier = _RejectingStartupBarrier()

    with pytest.raises(
        WriteAheadWorkflowError, match="durability startup validation failed"
    ):
        await runner.execute(
            execution_id=execution_id,
            step_id="charge-card",
            request=_request(target="customer-redacted-17"),
        )

    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    assert state.intent_ledger == {}
    assert harness.oracle.calls == ()
