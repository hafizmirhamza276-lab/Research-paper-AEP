"""Seeding an execution twice must not fail the second time.

Found by the matrix smoke, and only visible there. ``seed_execution_state``
creates the ``IDLE`` record the fenced write path requires, with
``expected_version=0`` -- "this key must not exist". That is correct exactly
once. B2 is the only system that both uses the fenced write path *and*
re-executes a crashed execution, so it is the only one that reaches this
function twice for one execution id, and when it did, the second call raised
``StaleWriteError``, the execution was recorded as failed, and B2's cell came
out as four lost effects and no duplicates.

That number was wrong in the direction that flatters the baseline: B2 looked
like a system that quietly loses effects rather than one that duplicates them,
because its re-execution never got as far as transmitting.

Two properties are asserted here. Seeding is idempotent, and seeding waits for
a lease a dead worker still holds -- the same bounded wait the baselines use,
for the same reason.
"""

from __future__ import annotations

import asyncio

import pytest

from aep_core.core.exceptions import LockAcquisitionError
from aep_core.core.storage import AEPStatus

from experiments.harness.composition import seed_execution_state
from experiments.baselines.tests.helpers import item_for


async def test_seeding_is_idempotent(
    redis_client, lock_manager, storage_adapter, cjson_available
) -> None:
    if not cjson_available:
        pytest.skip("the fenced write path needs a Redis with cjson")
    item = item_for()

    await seed_execution_state(
        storage_adapter=storage_adapter,
        lock_manager=lock_manager,
        execution_id=item.execution_id,
    )
    first = await storage_adapter.get_state(item.execution_id)
    assert first is not None and first.status is AEPStatus.IDLE

    # The second call is what a supervisor's re-execution makes.
    await seed_execution_state(
        storage_adapter=storage_adapter,
        lock_manager=lock_manager,
        execution_id=item.execution_id,
    )
    second = await storage_adapter.get_state(item.execution_id)
    assert second is not None
    assert second.version == first.version, (
        "re-seeding must not write: an execution that has already run has a "
        "version and a history, and resetting either would erase the very "
        "record the re-execution is about to be compared against"
    )


async def test_seeding_does_not_overwrite_work_already_done(
    redis_client, lock_manager, storage_adapter, cjson_available
) -> None:
    """The stronger form: a completed execution is not reset to IDLE."""
    if not cjson_available:
        pytest.skip("the fenced write path needs a Redis with cjson")
    item = item_for()
    await seed_execution_state(
        storage_adapter=storage_adapter,
        lock_manager=lock_manager,
        execution_id=item.execution_id,
    )
    token = await lock_manager.acquire_lock(item.execution_id, ttl_seconds=20)
    assert token is not None
    state = await storage_adapter.get_state(item.execution_id)
    state.status = AEPStatus.COMPLETED
    state.version = state.version + 1
    await storage_adapter.save_state(
        state, expected_version=state.version - 1, lock_token=token
    )
    await lock_manager.release_lock(item.execution_id, token)

    await seed_execution_state(
        storage_adapter=storage_adapter,
        lock_manager=lock_manager,
        execution_id=item.execution_id,
    )
    after = await storage_adapter.get_state(item.execution_id)
    assert after is not None and after.status is AEPStatus.COMPLETED


async def test_seeding_waits_for_a_lease_a_dead_worker_holds(
    redis_client, lock_manager, storage_adapter, cjson_available
) -> None:
    if not cjson_available:
        pytest.skip("the fenced write path needs a Redis with cjson")
    item = item_for()
    corpse = await lock_manager.acquire_lock(item.execution_id, ttl_seconds=20)
    assert corpse is not None

    async def release_shortly() -> None:
        await asyncio.sleep(0.3)
        await lock_manager.release_lock(item.execution_id, corpse)

    releaser = asyncio.create_task(release_shortly())
    await seed_execution_state(
        storage_adapter=storage_adapter,
        lock_manager=lock_manager,
        execution_id=item.execution_id,
        lease_wait_seconds=5.0,
    )
    await releaser
    assert await storage_adapter.get_state(item.execution_id) is not None


async def test_the_wait_is_bounded(
    redis_client, lock_manager, storage_adapter, cjson_available
) -> None:
    if not cjson_available:
        pytest.skip("the fenced write path needs a Redis with cjson")
    item = item_for()
    corpse = await lock_manager.acquire_lock(item.execution_id, ttl_seconds=20)
    assert corpse is not None
    try:
        with pytest.raises(LockAcquisitionError):
            await seed_execution_state(
                storage_adapter=storage_adapter,
                lock_manager=lock_manager,
                execution_id=item.execution_id,
                lease_wait_seconds=0.3,
            )
    finally:
        await lock_manager.release_lock(item.execution_id, corpse)
