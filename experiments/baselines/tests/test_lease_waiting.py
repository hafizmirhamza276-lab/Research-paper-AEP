"""A re-executing supervisor waits for the lease; it does not give up on it.

Found by running the matrix, not by reasoning about it. The first end-to-end
matrix smoke showed B1, B2 and B4 producing four ``NO_RECORD`` executions and
four lost effects apiece, where B0 produced the expected duplicates. The trace
said why: a worker killed mid-dispatch leaves its lease held until the TTL
expires, the supervisor respawns within a second, and the re-execution called
``acquire_lock`` once, got ``None``, and raised.

That is not a model of anything. A framework that abandoned a step forever
because a lock was briefly held would be a worse baseline than the naive one,
and -- worse for the evaluation -- it would credit the lease with *preventing*
a duplicate that it only ever delays. The lease's real contribution is exactly
that delay, and measuring it requires waiting for it.

So the systems that take a lease wait for it, up to a bound derived from the
lock TTL, and record how long they waited. The wait is a result: it is the
throughput cost a lease imposes under crashes, and it is the reason B1 and B2
are slower than B0 while duplicating just as much.
"""

from __future__ import annotations

import asyncio

import pytest

from aep_core.core.exceptions import LockAcquisitionError
from aep_core.core.intent_workflow import ConnectorPolicy

from experiments.baselines.b1_lease_only import LeaseOnlyRunner
from experiments.baselines.b4_durable_workflow import DurableWorkflowRunner
from experiments.baselines.common import acquire_lease_or_wait
from experiments.baselines.tests.conftest import RecordingConnector, applied
from experiments.baselines.tests.helpers import item_for
from experiments.harness.workload import harness_profile, request_for

POLICY = ConnectorPolicy(client_timeout_seconds=1.0, lock_ttl_seconds=20)


class _PassthroughBarrier:
    test_only = False

    async def validate_startup(self, redis_client):
        return None

    async def confirm_durable(self, connection, timeout_ms: int) -> bool:
        return True


async def test_a_held_lease_is_waited_for_not_abandoned(
    redis_client, lock_manager
) -> None:
    """The exact situation the matrix produced: someone else holds it, briefly."""
    item = item_for()
    held = await lock_manager.acquire_lock(item.execution_id, ttl_seconds=20)
    assert held is not None

    async def release_shortly() -> None:
        await asyncio.sleep(0.3)
        await lock_manager.release_lock(item.execution_id, held)

    releaser = asyncio.create_task(release_shortly())
    token, waited = await acquire_lease_or_wait(
        lock_manager,
        item.execution_id,
        ttl_seconds=20,
        wait_seconds=5.0,
        poll_seconds=0.05,
    )
    await releaser

    assert token is not None
    assert waited > 0.0, "the wait must be measured; it is the lease's real cost"
    await lock_manager.release_lock(item.execution_id, token)


async def test_the_wait_is_bounded_and_then_it_raises(
    redis_client, lock_manager
) -> None:
    """Fail-closed still applies: an unbounded wait is not patience, it is a hang."""
    item = item_for()
    held = await lock_manager.acquire_lock(item.execution_id, ttl_seconds=20)
    assert held is not None
    try:
        with pytest.raises(LockAcquisitionError):
            await acquire_lease_or_wait(
                lock_manager,
                item.execution_id,
                ttl_seconds=20,
                wait_seconds=0.3,
                poll_seconds=0.05,
            )
    finally:
        await lock_manager.release_lock(item.execution_id, held)


async def test_an_uncontended_lease_is_not_waited_for(
    redis_client, lock_manager
) -> None:
    item = item_for()
    token, waited = await acquire_lease_or_wait(
        lock_manager, item.execution_id, ttl_seconds=20, wait_seconds=5.0
    )
    assert token is not None
    # "No waiting" means no polling interval was ever slept, not that the
    # round trip to Redis was instantaneous. The poll interval is 0.25 s, so
    # anything below it proves the loop ran exactly once.
    assert waited < 0.25
    await lock_manager.release_lock(item.execution_id, token)


async def test_b1_waits_for_a_lease_a_dead_worker_still_holds(
    redis_client, lock_manager
) -> None:
    """End to end through the baseline, because that is where it went wrong."""
    item = item_for()
    corpse_token = await lock_manager.acquire_lock(item.execution_id, ttl_seconds=20)
    assert corpse_token is not None

    async def expire_shortly() -> None:
        await asyncio.sleep(0.3)
        await lock_manager.release_lock(item.execution_id, corpse_token)

    releaser = asyncio.create_task(expire_shortly())
    connector = RecordingConnector(script=[applied()])
    runner = LeaseOnlyRunner(
        redis_client=redis_client,
        lock_manager=lock_manager,
        connector=connector,
        profile=harness_profile(),
        policy=POLICY,
        lease_wait_seconds=5.0,
    )
    outcome = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )
    await releaser

    assert len(connector.transmissions) == 1, (
        "the re-execution must eventually transmit -- the lease delays the "
        "duplicate, it does not prevent it, and an evaluation that reported "
        "otherwise would be crediting the lease with a guarantee it lacks"
    )
    assert outcome.status == "APPLIED"


async def test_b4_waits_too(redis_client, lock_manager) -> None:
    item = item_for()
    corpse_token = await lock_manager.acquire_lock(item.execution_id, ttl_seconds=20)
    assert corpse_token is not None

    async def expire_shortly() -> None:
        await asyncio.sleep(0.3)
        await lock_manager.release_lock(item.execution_id, corpse_token)

    releaser = asyncio.create_task(expire_shortly())
    connector = RecordingConnector(script=[applied()])
    runner = DurableWorkflowRunner(
        redis_client=redis_client,
        lock_manager=lock_manager,
        connector=connector,
        profile=harness_profile(),
        policy=POLICY,
        barrier=_PassthroughBarrier(),
        lease_wait_seconds=5.0,
    )
    outcome = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )
    await releaser

    assert len(connector.transmissions) == 1
    assert outcome.status == "APPLIED"


def test_the_default_wait_outlives_the_lock_ttl() -> None:
    """Waiting for less than the TTL would abandon every crashed execution.

    The number that matters: a lease held by a process that no longer exists
    goes away when Redis expires it and not before, so a supervisor that waits
    for less than the TTL is a supervisor that never retries anything.
    """
    from experiments.baselines.common import default_lease_wait_seconds

    assert default_lease_wait_seconds(POLICY) > POLICY.lock_ttl_seconds
