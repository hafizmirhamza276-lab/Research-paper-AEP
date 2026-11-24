"""Self-tests for the adversarial non-idempotent connector harness."""

from __future__ import annotations

import asyncio

import pytest

from tests.request_binding_helpers import (
    reconciliation_context,
    verified_dispatch,
)

from tests.mock_connector import (
    CallerEvidence,
    CallScenario,
    CrashPoint,
    CrashStyle,
    MockConflictingEvidence,
    MockConnectionDropped,
    MockConnectorHarness,
    MockExternalTimeout,
    MockReadbackUnavailable,
    ReadbackResult,
    ReconciliationCapability,
    ResponseMode,
    SimulatedProcessCrash,
)


async def _mutate(connector, intent_id: str, client_timeout: float):
    return await connector.mutate(
        dispatch=await verified_dispatch(intent_id),
        client_timeout=client_timeout,
    )


async def _read_back(connector, intent_id: str):
    return await connector.read_back(
        context=reconciliation_context(intent_id),
        readback_timeout=0.01,
    )


@pytest.mark.asyncio
async def test_definitive_modes_match_ground_truth() -> None:
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    harness.enqueue_call(ResponseMode.DEFINITIVE_FAILURE)

    success = await _mutate(harness.connector, "intent-success", 0.01)
    failure = await _mutate(harness.connector, "intent-failure", 0.01)

    assert success.evidence is CallerEvidence.DEFINITIVE_SUCCESS
    assert success.external_reference is not None
    assert failure.evidence is CallerEvidence.DEFINITIVE_FAILURE
    assert failure.external_reference is None

    success_truth, failure_truth = harness.oracle.calls
    assert success_truth.mutation_applied is True
    assert success_truth.caller_evidence is CallerEvidence.DEFINITIVE_SUCCESS
    assert failure_truth.mutation_applied is False
    assert failure_truth.caller_evidence is CallerEvidence.DEFINITIVE_FAILURE
    assert failure_truth.transmission_started is True


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation_applied", [False, True])
async def test_timeout_hides_both_possible_mutation_truths(
    mutation_applied: bool,
) -> None:
    harness = MockConnectorHarness()
    harness.enqueue_call(
        ResponseMode.TIMEOUT_NO_RESPONSE,
        mutation_applied=mutation_applied,
    )

    with pytest.raises(MockExternalTimeout) as exc_info:
        await _mutate(harness.connector, "intent-timeout", 0.001)

    truth = harness.oracle.calls[0]
    assert truth.mutation_applied is mutation_applied
    assert truth.caller_evidence is CallerEvidence.AMBIGUOUS
    assert truth.response_received is False
    assert truth.call_finished is True
    assert not hasattr(exc_info.value, "mutation_applied")


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation_applied", [False, True])
async def test_connection_drop_hides_both_possible_mutation_truths(
    mutation_applied: bool,
) -> None:
    harness = MockConnectorHarness()
    harness.enqueue_call(
        ResponseMode.CONNECTION_DROP_MID_TRANSMISSION,
        mutation_applied=mutation_applied,
    )

    with pytest.raises(MockConnectionDropped) as exc_info:
        await _mutate(harness.connector, "intent-drop", 0.01)

    truth = harness.oracle.calls[0]
    assert truth.request_may_have_reached_server is True
    assert truth.mutation_applied is mutation_applied
    assert truth.caller_evidence is CallerEvidence.AMBIGUOUS
    assert not hasattr(exc_info.value, "mutation_applied")


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation_applied", [False, True])
async def test_conflicting_evidence_is_ambiguous_regardless_of_truth(
    mutation_applied: bool,
) -> None:
    harness = MockConnectorHarness()
    harness.enqueue_call(
        ResponseMode.CONFLICTING_EVIDENCE,
        mutation_applied=mutation_applied,
    )

    with pytest.raises(MockConflictingEvidence):
        await _mutate(harness.connector, "intent-conflict", 0.01)

    truth = harness.oracle.calls[0]
    assert truth.mutation_applied is mutation_applied
    assert truth.response_received is True
    assert truth.caller_evidence is CallerEvidence.AMBIGUOUS


@pytest.mark.parametrize(
    "mode",
    [
        ResponseMode.TIMEOUT_NO_RESPONSE,
        ResponseMode.CONNECTION_DROP_MID_TRANSMISSION,
        ResponseMode.CONFLICTING_EVIDENCE,
    ],
)
def test_ambiguous_scenarios_require_explicit_hidden_truth(
    mode: ResponseMode,
) -> None:
    with pytest.raises(ValueError, match="explicit mutation_applied"):
        CallScenario(mode)


def test_definitive_scenarios_reject_impossible_ground_truth() -> None:
    with pytest.raises(ValueError, match="must apply"):
        CallScenario(ResponseMode.DEFINITIVE_SUCCESS, mutation_applied=False)
    with pytest.raises(ValueError, match="reject before mutation"):
        CallScenario(ResponseMode.DEFINITIVE_FAILURE, mutation_applied=True)


@pytest.mark.asyncio
async def test_caller_surface_has_no_ground_truth_inspection_api() -> None:
    harness = MockConnectorHarness()
    connector = harness.connector
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)

    response = await _mutate(connector, "intent-separated-oracle", 0.01)

    assert not hasattr(connector, "oracle")
    assert not hasattr(connector, "ground_truth")
    assert not hasattr(response, "mutation_applied")
    assert harness.oracle.calls[0].mutation_applied is True


@pytest.mark.asyncio
async def test_authoritative_readback_proves_presence_and_absence() -> None:
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    harness.enqueue_calls(
        [
            CallScenario(
                ResponseMode.TIMEOUT_NO_RESPONSE,
                mutation_applied=True,
            ),
            CallScenario(
                ResponseMode.TIMEOUT_NO_RESPONSE,
                mutation_applied=False,
            ),
        ]
    )

    for intent_id in ("intent-applied", "intent-not-applied"):
        with pytest.raises(MockExternalTimeout):
            await _mutate(harness.connector, intent_id, 0.001)

    applied = await _read_back(harness.connector, "intent-applied")
    not_applied = await _read_back(harness.connector, "intent-not-applied")

    assert applied.result is ReadbackResult.APPLIED
    assert applied.external_reference is not None
    assert not_applied.result is ReadbackResult.NOT_APPLIED
    assert not_applied.external_reference is None


@pytest.mark.asyncio
async def test_positive_only_readback_never_proves_absence() -> None:
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.POSITIVE_ONLY_READBACK
    )
    harness.enqueue_calls(
        [
            CallScenario(
                ResponseMode.CONNECTION_DROP_MID_TRANSMISSION,
                mutation_applied=True,
            ),
            CallScenario(
                ResponseMode.CONNECTION_DROP_MID_TRANSMISSION,
                mutation_applied=False,
            ),
        ]
    )

    for intent_id in ("intent-present", "intent-absent"):
        with pytest.raises(MockConnectionDropped):
            await _mutate(harness.connector, intent_id, 0.01)

    present = await _read_back(harness.connector, "intent-present")
    absent = await _read_back(harness.connector, "intent-absent")

    assert present.result is ReadbackResult.APPLIED
    assert absent.result is ReadbackResult.UNKNOWN
    assert all(
        observation.result is not ReadbackResult.NOT_APPLIED
        for observation in harness.oracle.readbacks
    )


@pytest.mark.asyncio
async def test_no_readback_refuses_query_and_records_no_query() -> None:
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.NO_READBACK
    )

    with pytest.raises(MockReadbackUnavailable, match="operator review"):
        await _read_back(harness.connector, "intent-no-readback")

    assert harness.oracle.readbacks == ()
    with pytest.raises(ValueError, match="NO_READBACK"):
        harness.enqueue_readback(ReadbackResult.UNKNOWN)


@pytest.mark.asyncio
async def test_readback_evidence_can_be_scripted_deterministically() -> None:
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    harness.enqueue_readback(ReadbackResult.UNKNOWN)
    harness.enqueue_readback(ReadbackResult.CONFLICT)

    first = await _read_back(harness.connector, "intent-scripted")
    second = await _read_back(harness.connector, "intent-scripted")

    assert first.result is ReadbackResult.UNKNOWN
    assert second.result is ReadbackResult.CONFLICT
    assert [item.scripted for item in harness.oracle.readbacks] == [True, True]


@pytest.mark.asyncio
async def test_conflicting_call_derives_conflicting_readback() -> None:
    harness = MockConnectorHarness()
    harness.enqueue_call(
        ResponseMode.CONFLICTING_EVIDENCE,
        mutation_applied=True,
    )
    with pytest.raises(MockConflictingEvidence):
        await _mutate(harness.connector, "intent-conflict-readback", 0.01)

    observation = await _read_back(harness.connector, "intent-conflict-readback")
    assert observation.result is ReadbackResult.CONFLICT


@pytest.mark.asyncio
@pytest.mark.parametrize("point", list(CrashPoint))
async def test_every_design_crash_point_is_individually_triggerable(
    point: CrashPoint,
) -> None:
    harness = MockConnectorHarness()
    harness.crashes.arm(point, style=CrashStyle.PROCESS_EXIT)

    with pytest.raises(SimulatedProcessCrash) as exc_info:
        await harness.crashes.checkpoint(point)

    assert exc_info.value.point is point
    assert harness.crashes.triggered_points == (point,)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation_applied", [False, True])
async def test_mid_transmission_crash_cancels_task_and_preserves_truth(
    mutation_applied: bool,
) -> None:
    harness = MockConnectorHarness()
    harness.enqueue_call(
        ResponseMode.CONNECTION_DROP_MID_TRANSMISSION,
        mutation_applied=mutation_applied,
    )
    harness.crashes.arm(
        CrashPoint.DURING_REQUEST_TRANSMISSION,
        style=CrashStyle.CANCEL_COROUTINE,
    )

    task = asyncio.create_task(
        _mutate(harness.connector, "intent-crash-mid-transmission", 0.01)
    )
    with pytest.raises(asyncio.CancelledError):
        await task

    truth = harness.oracle.calls[0]
    assert task.cancelled()
    assert truth.transmission_started is True
    assert truth.mutation_applied is mutation_applied
    assert truth.caller_evidence is CallerEvidence.NONE
    assert truth.call_finished is False
    assert truth.crashed_at is CrashPoint.DURING_REQUEST_TRANSMISSION


@pytest.mark.asyncio
async def test_crash_before_transmission_records_no_external_mutation() -> None:
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    harness.crashes.arm(
        CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION,
        style=CrashStyle.PROCESS_EXIT,
    )

    with pytest.raises(SimulatedProcessCrash):
        await _mutate(harness.connector, "intent-crash-before-send", 0.01)

    truth = harness.oracle.calls[0]
    assert truth.transmission_started is False
    assert truth.request_may_have_reached_server is False
    assert truth.mutation_applied is False
    assert truth.crashed_at is (
        CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION
    )


@pytest.mark.asyncio
async def test_crash_after_success_keeps_applied_truth_without_response_return() -> None:
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    harness.crashes.arm(
        CrashPoint.AFTER_CONCLUSIVE_SUCCESS_BEFORE_RESOLUTION_CAS,
        style=CrashStyle.PROCESS_EXIT,
    )

    with pytest.raises(SimulatedProcessCrash):
        await _mutate(harness.connector, "intent-crash-after-success", 0.01)

    truth = harness.oracle.calls[0]
    assert truth.mutation_applied is True
    assert truth.caller_evidence is CallerEvidence.DEFINITIVE_SUCCESS
    assert truth.call_finished is True
    assert truth.crashed_at is (
        CrashPoint.AFTER_CONCLUSIVE_SUCCESS_BEFORE_RESOLUTION_CAS
    )


@pytest.mark.asyncio
async def test_crash_after_readback_retains_test_only_observation() -> None:
    harness = MockConnectorHarness()
    harness.enqueue_readback(ReadbackResult.UNKNOWN)
    harness.crashes.arm(
        CrashPoint.AFTER_READBACK_BEFORE_RECOVERY_RESOLUTION_CAS,
        style=CrashStyle.PROCESS_EXIT,
    )

    with pytest.raises(SimulatedProcessCrash):
        await _read_back(harness.connector, "intent-readback-crash")

    assert harness.oracle.readbacks[0].result is ReadbackResult.UNKNOWN
    assert harness.oracle.readbacks[0].crashed_at is (
        CrashPoint.AFTER_READBACK_BEFORE_RECOVERY_RESOLUTION_CAS
    )
