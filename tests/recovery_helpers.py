"""Shared seeding helpers for Phase 1B recovery tests.

Kept separate from ``tests/test_phase2_recovery.py`` so the pre-existing suite
is not disturbed by Phase 1B additions.
"""

from __future__ import annotations

import hashlib
import json
import uuid

from aep_core.core.durability import FakeDurabilityBarrier
from aep_core.core.intent_recovery import IntentRecoveryService, RecoveryConnectorConfig
from aep_core.core.intent_workflow import ConnectorPolicy
from aep_core.core.intents import (
    IntentAuditEntry,
    IntentLedgerStore,
    IntentStatus,
    MINIMUM_UNRESOLVED_TTL_SECONDS,
)
from aep_core.core.storage import AEPExecutionState, AEPStatus

CONNECTOR_NAME = "mock.non-idempotent.v1/mutate"


def policy(**overrides) -> ConnectorPolicy:
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


async def seed_stale_about_to_fire(
    redis_client,
    lock_manager,
    *,
    connector: str = CONNECTOR_NAME,
    intent_id: str | None = None,
    status: IntentStatus = IntentStatus.ABOUT_TO_FIRE,
    ttl_seconds: int = MINIMUM_UNRESOLVED_TTL_SECONDS,
    reconciliation: dict | None = None,
) -> tuple[str, str, str]:
    """Write a deliberately stale legacy Phase 2 record directly to Redis."""

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
    transitions = [transition.model_dump()]
    if status is not IntentStatus.ABOUT_TO_FIRE:
        transitions.append(
            IntentAuditEntry(
                old_state=IntentStatus.ABOUT_TO_FIRE.value,
                new_state=status,
                redis_time=prepared_at + 1,
                actor="recovery",
                reason="orphaned-about-to-fire",
                evidence_hash=hashlib.sha256(b"fixture2").hexdigest(),
            ).model_dump()
        )
    raw_intent = {
        "intent_id": intent_id,
        "step_id": "charge-card",
        "attempt": 1,
        "connector": connector,
        "target": "customer-redacted-17",
        "request_fingerprint": "c" * 64,
        "correlation_id": str(uuid.uuid4()),
        "status": status,
        "prepared_at": prepared_at,
        "client_timeout_seconds": 1,
        "settlement_lag_seconds": 0,
        "reconcile_after": prepared_at + 16,
        "prepared_state_version": 1,
        "external_reference": None,
        "last_observation": None,
        "reconciliation": reconciliation,
        "transitions": transitions,
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
    payload = state.model_dump(mode="json")
    payload.pop("phase2_managed", None)
    await redis_client.set(
        f"aep:state:{execution_id}",
        json.dumps(payload),
        ex=ttl_seconds,
    )
    assert await lock_manager.release_lock(execution_id, token)
    return execution_id, intent_id, token


async def seed_corrupt_execution(redis_client) -> str:
    """Write a state key that passes Phase 1 validation but fails Phase 2.

    ``RedisStorageAdapter.get_state`` accepts it because ``intent_ledger`` is
    ``Dict[str, Any]`` at Phase 1; ``IntentLedgerStore.get_execution`` then
    fails the strict ``IntentRecord`` validation and raises
    ``StateCorruptionError`` after quarantining the key.
    """

    execution_id = str(uuid.uuid4())
    payload = {
        "execution_id": execution_id,
        "status": AEPStatus.PROCESSING.value,
        "version": 1,
        "schema_version": "1.0.0",
        "intent_ledger": {"not-a-real-intent": {"garbage": True}},
        "context_data": {},
        "updated_at": 0.0,
    }
    await redis_client.set(
        f"aep:state:{execution_id}",
        json.dumps(payload),
        ex=MINIMUM_UNRESOLVED_TTL_SECONDS,
    )
    return execution_id


def recovery_service(
    redis_client,
    lock_manager,
    connectors: dict,
    **kwargs,
) -> IntentRecoveryService:
    return IntentRecoveryService(
        store=IntentLedgerStore(redis_client),
        lock_manager=lock_manager,
        connectors=connectors,
        **kwargs,
    )


def connector_config(connector, *, pol: ConnectorPolicy | None = None):
    return RecoveryConnectorConfig(
        connector=connector,
        barrier=FakeDurabilityBarrier(),
        policy=pol or policy(),
    )
