"""Recovery must validate its durability barrier before it uses it.

Found by the Phase 2B Session 2 harness, not by the unit suite, and the reason
is instructive: every existing recovery test supplies ``FakeDurabilityBarrier``,
which has no startup contract. The *production* barrier does --
``RealWaitAofDurabilityBarrier.confirm_durable`` refuses to issue ``WAITAOF``
until ``validate_startup`` has succeeded -- and ``IntentRecoveryService`` never
called it.

The failure was quiet in the worst way. ``_persist_recovery_resolution``
performs the transition CAS *first* and confirms durability *second*, so with an
unvalidated barrier:

* the intent's status really did advance in Redis, and looked correct to
  anything that read it afterwards;
* the durability confirmation then raised, so the resolution was discarded as
  an isolated single-execution failure and ``scan_once`` reported zero
  recoveries;
* every recovered transition was therefore unacknowledged -- precisely the
  guarantee P2 rests on -- and any recovery-success or recovery-latency metric
  computed from the service's return value would have read zero while the
  system was, in fact, recovering.

The fix mirrors ``WriteAheadRunner._validate_real_barrier``: validate once,
before first use, and fail closed if validation fails.
"""

from __future__ import annotations

import os

import pytest

from aep_core.core.connector_contract import ReadbackResult, ReconciliationCapability
from aep_core.core.durability import (
    DurabilityCapabilityError,
    RealWaitAofDurabilityBarrier,
)
from aep_core.core.intent_recovery import RecoveryConnectorConfig
from aep_core.core.intents import IntentLedgerStore, IntentStatus
from tests.mock_connector import MockConnectorHarness
from tests.recovery_helpers import (
    CONNECTOR_NAME,
    policy,
    recovery_service,
    seed_stale_about_to_fire,
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


def real_barrier_config(connector, **overrides):
    """A recovery connector declaration using the production barrier."""
    return RecoveryConnectorConfig(
        connector=connector,
        barrier=RealWaitAofDurabilityBarrier(),
        policy=policy(durability_timeout_ms=2_000, **overrides),
    )


@pytest.mark.asyncio
async def test_recovery_resolves_an_orphan_with_the_production_barrier(
    redis_client, lock_manager
):
    """The regression: with the real barrier this returned nothing at all."""
    execution_id, intent_id, _ = await seed_stale_about_to_fire(
        redis_client, lock_manager
    )
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    harness.enqueue_readback(ReadbackResult.APPLIED)
    service = recovery_service(
        redis_client,
        lock_manager,
        {CONNECTOR_NAME: real_barrier_config(harness.connector)},
    )

    results = await service.scan_once()

    mine = [result for result in results if result.execution_id == execution_id]
    assert mine, (
        "recovery reported no resolution; before the fix the transition CAS "
        "landed in Redis and the durability confirmation then raised, so the "
        "result was discarded as an isolated failure"
    )
    (result,) = mine
    assert result.status is IntentStatus.FIRED_CONFIRMED
    assert result.readback_performed is True
    assert service.last_scan_failures == ()

    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state.intent_ledger[intent_id].status is IntentStatus.FIRED_CONFIRMED


@pytest.mark.asyncio
async def test_the_barrier_is_validated_once_not_per_resolution(
    redis_client, lock_manager
):
    """Startup validation is four Redis round trips; it is not per intent."""
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    barrier = RealWaitAofDurabilityBarrier()
    validations = []
    original = barrier.validate_startup

    async def counting_validate(redis_client_argument):
        validations.append(redis_client_argument)
        return await original(redis_client_argument)

    barrier.validate_startup = counting_validate
    service = recovery_service(
        redis_client,
        lock_manager,
        {
            CONNECTOR_NAME: RecoveryConnectorConfig(
                connector=harness.connector,
                barrier=barrier,
                policy=policy(durability_timeout_ms=2_000),
            )
        },
    )

    for _ in range(3):
        execution_id, _, _ = await seed_stale_about_to_fire(
            redis_client, lock_manager
        )
        harness.enqueue_readback(ReadbackResult.APPLIED)
        await service.recover_intent(
            execution_id,
            next(
                iter(
                    (
                        await IntentLedgerStore(redis_client).get_execution(
                            execution_id
                        )
                    ).intent_ledger
                )
            ),
        )

    assert len(validations) == 1


@pytest.mark.asyncio
async def test_a_barrier_that_fails_validation_stops_the_resolution(
    redis_client, lock_manager
):
    """Fail closed: an unvalidatable barrier must not silently be skipped."""

    class _RejectingBarrier:
        test_only = False

        def __init__(self) -> None:
            self.confirmations = 0

        async def validate_startup(self, redis_client_argument):
            raise DurabilityCapabilityError("scripted capability rejection")

        async def confirm_durable(self, connection, timeout_ms):
            self.confirmations += 1
            return True

    execution_id, intent_id, _ = await seed_stale_about_to_fire(
        redis_client, lock_manager
    )
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    harness.enqueue_readback(ReadbackResult.APPLIED)
    barrier = _RejectingBarrier()
    service = recovery_service(
        redis_client,
        lock_manager,
        {
            CONNECTOR_NAME: RecoveryConnectorConfig(
                connector=harness.connector,
                barrier=barrier,
                policy=policy(),
            )
        },
    )

    results = await service.scan_once()

    assert [result.execution_id for result in results] == []
    assert barrier.confirmations == 0
    assert [failure.execution_id for failure in service.last_scan_failures] == [
        execution_id
    ]


@pytest.mark.asyncio
async def test_a_barrier_without_a_startup_contract_still_works(
    redis_client, lock_manager
):
    """The existing test barrier must keep working; nothing is required of it.

    ``IntentRecoveryService`` has no dispatch-mode concept, so it cannot tell a
    test barrier from a production one. It validates what can be validated and
    leaves the rest to the composition -- which is where the mode check lives.
    """
    from tests.recovery_helpers import connector_config

    execution_id, intent_id, _ = await seed_stale_about_to_fire(
        redis_client, lock_manager
    )
    harness = MockConnectorHarness(
        capability=ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    harness.enqueue_readback(ReadbackResult.APPLIED)
    service = recovery_service(
        redis_client,
        lock_manager,
        {CONNECTOR_NAME: connector_config(harness.connector)},
    )

    results = await service.scan_once()

    assert [
        result.status
        for result in results
        if result.execution_id == execution_id
    ] == [IntentStatus.FIRED_CONFIRMED]
