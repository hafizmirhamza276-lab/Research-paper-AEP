"""Redis 7.2+ AOF integration tests for the Phase 2 durability barrier."""

from __future__ import annotations

import asyncio
import os
import subprocess
import uuid

import pytest
from redis.asyncio import Redis

from src.core.durability import RealWaitAofDurabilityBarrier
from src.core.intent_workflow import ConnectorPolicy, WriteAheadRunner
from src.core.intents import IntentLedgerStore, IntentStatus
from src.core.storage import AEPExecutionState, AEPStatus
from tests.mock_connector import MockConnectorHarness, ResponseMode
from tests.request_binding_helpers import (
    test_binding_service as _binding_service,
    test_request as _request,
)


pytestmark = [
    pytest.mark.redis72_integration,
    pytest.mark.skipif(
        os.environ.get("AEP_PHASE2_REDIS_INTEGRATION") != "1",
        reason=(
            "set AEP_PHASE2_REDIS_INTEGRATION=1 and REDIS_URL to the "
            "dedicated Redis 7.2+ AOF DB 15"
        ),
    ),
]

FINGERPRINT = "d" * 64


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


def _policy():
    return ConnectorPolicy(
        client_timeout_seconds=0.01,
        settlement_lag_seconds=0,
        buffer_margin_seconds=15,
        lock_ttl_seconds=30,
        durability_timeout_ms=2_000,
        lease_acquire_attempts=1,
    )


def _runner(store, lock_manager, harness, barrier):
    return WriteAheadRunner(
        store=store,
        lock_manager=lock_manager,
        connector=harness.connector,
        barrier=barrier,
        policy=_policy(),
        connector_name="mock.non-idempotent.v1/mutate",
        binding_service=_binding_service(),
        allow_test_dispatch=True,
    )


@pytest.fixture(autouse=True)
async def _require_redis_72_aof(redis_client):
    capabilities = await RealWaitAofDurabilityBarrier().validate_startup(
        redis_client
    )
    assert capabilities.redis_version_tuple >= (7, 2, 0)
    assert capabilities.aof_enabled is True


class _TracingStore(IntentLedgerStore):
    def __init__(self, redis_client, events):
        super().__init__(redis_client)
        self.events = events

    async def commit_transition(self, *args, connection=None, **kwargs):
        result = await super().commit_transition(
            *args, connection=connection, **kwargs
        )
        self.events.append(("cas", await connection.client_id()))
        return result


class _TracingWaitAofBarrier(RealWaitAofDurabilityBarrier):
    def __init__(self, events):
        super().__init__()
        self.events = events

    async def confirm_durable(self, connection, timeout_ms):
        client_id = await connection.client_id()
        result = await super().confirm_durable(connection, timeout_ms)
        self.events.append(("waitaof", client_id, result))
        return result


@pytest.mark.asyncio
async def test_cas_and_waitaof_are_ordered_on_the_same_pinned_connection(
    redis_client, storage_adapter, lock_manager, monkeypatch
):
    execution_id = await _seed(storage_adapter, lock_manager)
    events = []
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    mutate = harness.connector.mutate

    async def traced_mutate(*, dispatch, client_timeout):
        events.append(("provider",))
        return await mutate(
            dispatch=dispatch,
            client_timeout=client_timeout,
        )

    monkeypatch.setattr(harness.connector, "mutate", traced_mutate)
    store = _TracingStore(redis_client, events)

    result = await _runner(
        store,
        lock_manager,
        harness,
        _TracingWaitAofBarrier(events),
    ).execute(
        execution_id=execution_id,
        step_id="charge-card",
        request=_request(target="customer-redacted-17"),
    )

    assert result.status is IntentStatus.FIRED_CONFIRMED
    assert [event[0] for event in events] == [
        "cas",
        "waitaof",
        "provider",
        "cas",
        "waitaof",
    ]
    assert events[0][1] == events[1][1]
    assert events[3][1] == events[4][1]
    assert events[1][2] is True
    assert events[4][2] is True
    assert len(harness.oracle.calls) == 1


@pytest.mark.asyncio
async def test_acknowledged_real_waitaof_barrier_permits_dispatch(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)

    result = await _runner(
        IntentLedgerStore(redis_client),
        lock_manager,
        harness,
        RealWaitAofDurabilityBarrier(),
    ).execute(
        execution_id=execution_id,
        step_id="charge-card",
        request=_request(target="customer-redacted-17"),
    )

    assert result.status is IntentStatus.FIRED_CONFIRMED
    assert len(harness.oracle.calls) == 1


class _DisableAofAfterStartupBarrier(RealWaitAofDurabilityBarrier):
    async def validate_startup(self, redis_client):
        capabilities = await super().validate_startup(redis_client)
        assert await redis_client.config_set("appendonly", "no") is True
        return capabilities


async def _restore_aof(redis_client):
    assert await redis_client.config_set("appendonly", "yes") is True
    for _ in range(100):
        persistence = await redis_client.info("persistence")
        if int(persistence.get("aof_enabled", 0)) == 1:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("Redis AOF did not become enabled after test restoration")


@pytest.mark.asyncio
async def test_waitaof_command_failure_prevents_all_provider_calls(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    runner = _runner(
        IntentLedgerStore(redis_client),
        lock_manager,
        harness,
        _DisableAofAfterStartupBarrier(),
    )

    try:
        with pytest.raises(Exception, match="durability barrier"):
            await runner.execute(
                execution_id=execution_id,
                step_id="charge-card",
                request=_request(target="customer-redacted-17"),
            )
    finally:
        await _restore_aof(redis_client)

    assert harness.oracle.calls == ()


@pytest.mark.asyncio
async def test_intent_and_resolution_survive_controlled_redis_restart(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    harness = MockConnectorHarness()
    harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
    result = await _runner(
        IntentLedgerStore(redis_client),
        lock_manager,
        harness,
        RealWaitAofDurabilityBarrier(),
    ).execute(
        execution_id=execution_id,
        step_id="charge-card",
        request=_request(target="customer-redacted-17"),
    )
    assert result.status is IntentStatus.FIRED_CONFIRMED
    assert len(result.transitions) == 2

    await redis_client.connection_pool.disconnect()
    container = os.environ.get(
        "AEP_PHASE2_REDIS_CONTAINER", "aep-phase2-redis72"
    )
    restarted = subprocess.run(
        ["docker", "restart", container],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert restarted.returncode == 0, restarted.stderr

    redis_url = os.environ["REDIS_URL"]
    fresh = Redis.from_url(redis_url, decode_responses=True)
    try:
        for _ in range(100):
            try:
                if await fresh.ping():
                    break
            except Exception:
                pass
            await asyncio.sleep(0.05)
        else:
            raise AssertionError("Redis did not return after controlled restart")

        persisted = await IntentLedgerStore(fresh).get_execution(execution_id)
        assert persisted is not None
        surviving = persisted.intent_ledger[result.intent_id]
        assert surviving.status is IntentStatus.FIRED_CONFIRMED
        assert [entry.new_state for entry in surviving.transitions] == [
            IntentStatus.ABOUT_TO_FIRE,
            IntentStatus.FIRED_CONFIRMED,
        ]
        assert len(harness.oracle.calls) == 1
    finally:
        await fresh.aclose()
