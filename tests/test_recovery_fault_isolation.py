"""Phase 1B regression tests: one bad execution must not stop recovery.

Before Phase 1B, ``scan_once`` had no exception handling, ``asyncio.gather``
was called without ``return_exceptions=True``, and ``run_forever`` did not
guard its ``scan_once`` call.  A single corrupt execution, or a single intent
naming an unregistered connector, therefore terminated reconciliation for the
entire keyspace.
"""

from __future__ import annotations

import asyncio

import pytest

from aep_core.core.intent_recovery import RecoveryScanPhase
from aep_core.core.intents import IntentLedgerStore, IntentStatus
from tests.mock_connector import MockConnectorHarness, ReadbackResult
from aep_core.core.connector_contract import ReconciliationCapability
from tests.recovery_helpers import (
    CONNECTOR_NAME,
    connector_config,
    recovery_service,
    seed_corrupt_execution,
    seed_stale_about_to_fire,
)

HEALTHY_COUNT = 4


def _service(redis_client, lock_manager, harness, **kwargs):
    return recovery_service(
        redis_client,
        lock_manager,
        {CONNECTOR_NAME: connector_config(harness.connector)},
        **kwargs,
    )


@pytest.mark.asyncio
async def test_corrupt_execution_does_not_stop_the_scan(
    redis_client, storage_adapter, lock_manager
):
    """One poisoned key must not prevent the N healthy ones being processed."""

    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    corrupt_id = await seed_corrupt_execution(redis_client)
    healthy = []
    for _ in range(HEALTHY_COUNT):
        execution_id, intent_id, _ = await seed_stale_about_to_fire(
            redis_client, lock_manager
        )
        healthy.append((execution_id, intent_id))
        harness.enqueue_readback(ReadbackResult.APPLIED)

    service = _service(redis_client, lock_manager, harness)
    results = await service.scan_once()

    processed = {(item.execution_id, item.intent_id) for item in results}
    assert processed == set(healthy)
    for execution_id, intent_id in healthy:
        state = await IntentLedgerStore(redis_client).get_execution(execution_id)
        assert state is not None
        assert (
            state.intent_ledger[intent_id].status is IntentStatus.FIRED_CONFIRMED
        )

    failures = service.last_scan_failures
    assert len(failures) == 1
    assert failures[0].execution_id == corrupt_id
    assert failures[0].phase is RecoveryScanPhase.DISCOVERY
    assert failures[0].failure_class == "StateCorruptionError"


@pytest.mark.asyncio
async def test_corrupt_execution_is_quarantined_during_discovery(
    redis_client, storage_adapter, lock_manager
):
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    corrupt_id = await seed_corrupt_execution(redis_client)

    await _service(redis_client, lock_manager, harness).scan_once()

    poison = [
        key
        async for key in redis_client.scan_iter(
            match=f"aep:poison:{corrupt_id}:*", count=100
        )
    ]
    assert poison, "the corrupt execution should have been quarantined"


@pytest.mark.asyncio
async def test_unregistered_connector_does_not_stop_the_scan(
    redis_client, storage_adapter, lock_manager
):
    """A single failing recover_intent must be isolated by the gather."""

    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    orphan_execution, orphan_intent, _ = await seed_stale_about_to_fire(
        redis_client, lock_manager, connector="some.unregistered.connector/v1"
    )
    healthy = []
    for _ in range(HEALTHY_COUNT):
        execution_id, intent_id, _ = await seed_stale_about_to_fire(
            redis_client, lock_manager
        )
        healthy.append((execution_id, intent_id))
        harness.enqueue_readback(ReadbackResult.APPLIED)

    service = _service(redis_client, lock_manager, harness)
    results = await service.scan_once()

    assert {(item.execution_id, item.intent_id) for item in results} == set(healthy)
    failures = service.last_scan_failures
    assert len(failures) == 1
    assert failures[0].execution_id == orphan_execution
    assert failures[0].intent_id == orphan_intent
    assert failures[0].phase is RecoveryScanPhase.RECOVERY


@pytest.mark.asyncio
async def test_scan_failures_are_reported_to_the_alert_callback(
    redis_client, storage_adapter, lock_manager
):
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    await seed_corrupt_execution(redis_client)
    seen = []

    service = _service(
        redis_client,
        lock_manager,
        harness,
        scan_failure_alert=lambda failure: seen.append(failure),
    )
    await service.scan_once()

    assert len(seen) == 1
    assert seen[0].failure_class == "StateCorruptionError"


@pytest.mark.asyncio
async def test_run_forever_survives_a_scan_failure_and_backs_off(
    redis_client, lock_manager
):
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    service = _service(redis_client, lock_manager, harness)

    stop = asyncio.Event()
    calls: list[int] = []

    async def flaky_scan():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("scan exploded")
        stop.set()
        return []

    service.scan_once = flaky_scan  # type: ignore[method-assign]

    await asyncio.wait_for(
        service.run_forever(
            stop,
            pass_interval_seconds=0.01,
            failure_backoff_base_seconds=0.01,
            failure_backoff_cap_seconds=0.05,
        ),
        timeout=10,
    )

    assert len(calls) >= 2, "run_forever must keep scanning after a failure"


@pytest.mark.asyncio
async def test_run_forever_still_propagates_cancellation(
    redis_client, lock_manager
):
    """Fault isolation must not swallow task cancellation."""

    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    service = _service(redis_client, lock_manager, harness)
    stop = asyncio.Event()

    async def cancelling_scan():
        raise asyncio.CancelledError()

    service.scan_once = cancelling_scan  # type: ignore[method-assign]

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(
            service.run_forever(stop, pass_interval_seconds=0.01), timeout=10
        )


@pytest.mark.asyncio
async def test_scan_once_source_uses_return_exceptions(
    redis_client, lock_manager
):
    """PAPER_ROADMAP.md Phase 1B item 2 names this explicitly."""

    import pathlib

    source = pathlib.Path("aep_core/core/intent_recovery.py").read_text(encoding="utf-8")
    assert "return_exceptions=True" in source
