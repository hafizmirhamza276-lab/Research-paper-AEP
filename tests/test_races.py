"""Race/concurrency adversarial tests (R-01..R-02).

Tests for concurrent behavior: two workers racing to acquire locks and
the scenario where a stale writer is fenced by a newer writer advancing
the version.
"""

import asyncio
import uuid

import pytest

from src.core.exceptions import LockAcquisitionError, StaleWriteError
from src.core.storage import AEPExecutionState, AEPStatus


class TestRaceLockAcquire:
    """R-01: Two workers race to acquire the same lock; exactly one wins."""

    @pytest.mark.asyncio
    async def test_race_acquire_lock_one_wins(self, lock_manager):
        """Two concurrent acquire calls; exactly one gets the token."""
        eid = str(uuid.uuid4())

        # Race two acquisitions concurrently
        results = await asyncio.gather(
            lock_manager.acquire_lock(eid, ttl_seconds=60),
            lock_manager.acquire_lock(eid, ttl_seconds=60),
        )

        # Exactly one should be a token, the other None
        assert len([r for r in results if r is not None]) == 1
        assert len([r for r in results if r is None]) == 1

        # Clean up: release the lock that was acquired
        token = [r for r in results if r is not None][0]
        await lock_manager.release_lock(eid, token)

    @pytest.mark.asyncio
    async def test_race_acquire_lock_three_way(self, lock_manager):
        """Three concurrent acquire calls; exactly one succeeds."""
        eid = str(uuid.uuid4())

        results = await asyncio.gather(
            lock_manager.acquire_lock(eid, ttl_seconds=60),
            lock_manager.acquire_lock(eid, ttl_seconds=60),
            lock_manager.acquire_lock(eid, ttl_seconds=60),
        )

        # Exactly one token, two Nones
        tokens = [r for r in results if r is not None]
        nones = [r for r in results if r is None]
        assert len(tokens) == 1
        assert len(nones) == 2

        await lock_manager.release_lock(eid, tokens[0])


class TestRaceStaleFence:
    """R-02: Stale writer is fenced; newer writer's state intact.

    Worker A writes version N with lock held. Lock expires. Worker B
    acquires lock and advances state to version N+1. Worker A (stale,
    unaware the lock expired) tries to write at version N. The CAS
    fences A's write (StaleWriteError). B's state remains intact.
    """

    @pytest.mark.asyncio
    async def test_race_stale_write_fenced(
        self, lock_manager, storage_adapter, redis_client
    ):
        """Stale writer is fenced by a newer writer advancing the version."""
        eid = str(uuid.uuid4())

        # Worker A: Acquire lock and write v1
        token_a = await lock_manager.acquire_lock(eid, ttl_seconds=60)
        assert token_a is not None

        state_a = AEPExecutionState(
            execution_id=eid,
            status=AEPStatus.PROCESSING,
            version=1,
        )
        await storage_adapter.save_state(
            state_a,
            expected_version=0,
            lock_token=token_a,
            ttl_seconds=3600,
        )

        # Simulate lock expiry: delete the lock key
        lock_key = f"aep:lock:{eid}"
        await redis_client.delete(lock_key)

        # Worker B: Acquire lock (now available because A's expired)
        token_b = await lock_manager.acquire_lock(eid, ttl_seconds=60)
        assert token_b is not None

        # Worker B: Fetch current state, advance to v2
        state_b = await storage_adapter.get_state(eid)
        assert state_b is not None
        assert state_b.version == 1
        state_b.version = 2
        state_b.status = AEPStatus.COMPLETED
        await storage_adapter.save_state(
            state_b,
            expected_version=1,
            lock_token=token_b,
            ttl_seconds=3600,
        )

        # Worker A (still holding stale assumption): Try to write v2
        # (A incremented its local copy from v1)
        state_a.version = 2
        state_a.status = AEPStatus.FAILED

        with pytest.raises(LockAcquisitionError):
            await storage_adapter.save_state(
                state_a,
                expected_version=1,
                lock_token=token_a,
                ttl_seconds=3600,
            )

        # Verify B's state is intact: v2 with COMPLETED status
        final = await storage_adapter.get_state(eid)
        assert final.version == 2
        assert final.status == AEPStatus.COMPLETED

        # Clean up
        await lock_manager.release_lock(eid, token_b)

    @pytest.mark.asyncio
    async def test_race_concurrent_writers_one_fenced(
        self, storage_adapter, lock_manager
    ):
        """Two concurrent writers; one is fenced by the other."""
        eid = str(uuid.uuid4())

        # Initial state at v1
        state = AEPExecutionState(
            execution_id=eid,
            status=AEPStatus.IDLE,
            version=1,
        )
        token = await lock_manager.acquire_lock(eid, ttl_seconds=60)
        assert token is not None
        await storage_adapter.save_state(
            state,
            expected_version=0,
            lock_token=token,
            ttl_seconds=3600,
        )

        # Simulate two workers both reading v1 and trying to write v2
        # (without lock coordination, just CAS)
        state1 = await storage_adapter.get_state(eid)
        state2 = await storage_adapter.get_state(eid)

        # Both increment to v2
        state1.version = 2
        state1.status = AEPStatus.PROCESSING

        state2.version = 2
        state2.status = AEPStatus.AWAITING_TOOL

        # First write succeeds
        await storage_adapter.save_state(
            state1,
            expected_version=1,
            lock_token=token,
            ttl_seconds=3600,
        )

        # Second write is fenced
        with pytest.raises(StaleWriteError):
            await storage_adapter.save_state(
                state2,
                expected_version=1,
                lock_token=token,
                ttl_seconds=3600,
            )

        # Verify the first writer's state is intact
        final = await storage_adapter.get_state(eid)
        assert final.version == 2
        assert final.status == AEPStatus.PROCESSING
        await lock_manager.release_lock(eid, token)
