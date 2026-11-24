"""Lease cap adversarial tests (LE-01..LE-02).

Tests for the auto-renewing lease context manager with a hard cap.
Covers long-running tasks that stay within TTL and tasks that hit the cap.
"""

import asyncio
import inspect
import uuid

import pytest

from aep_core.core.exceptions import LockAcquisitionError


def _lease_with_timeout_contract(
    lock_manager,
    execution_id,
    *,
    ttl_seconds,
    max_total_lease_seconds,
    client_deadline_seconds,
    buffer_margin_seconds,
):
    """Call the pre-fix or post-fix API so regressions span both versions."""
    parameters = inspect.signature(lock_manager.lease).parameters
    kwargs = {
        "ttl_seconds": ttl_seconds,
        "max_total_lease_seconds": max_total_lease_seconds,
    }
    if "client_deadline_seconds" in parameters:
        kwargs.update(
            client_deadline_seconds=client_deadline_seconds,
            buffer_margin_seconds=buffer_margin_seconds,
        )
    return lock_manager.lease(execution_id, **kwargs)


class TestTimeoutInvariantEnforcement:
    """Regression coverage for the executable client/lock timeout bound."""

    @pytest.mark.asyncio
    async def test_lease_cancels_block_at_configured_client_deadline(
        self, lock_manager
    ):
        eid = str(uuid.uuid4())

        async def protected_worker():
            async with _lease_with_timeout_contract(
                lock_manager,
                eid,
                ttl_seconds=20,
                max_total_lease_seconds=10,
                client_deadline_seconds=0.2,
                buffer_margin_seconds=15,
            ) as token:
                assert token is not None
                await asyncio.sleep(0.5)
                return "continued-after-client-deadline"

        result = (
            await asyncio.gather(protected_worker(), return_exceptions=True)
        )[0]
        assert isinstance(result, asyncio.CancelledError)

    @pytest.mark.asyncio
    async def test_lease_rejects_invalid_timeout_invariant(self, lock_manager):
        eid = str(uuid.uuid4())

        with pytest.raises(LockAcquisitionError, match="Buffer|buffer"):
            async with _lease_with_timeout_contract(
                lock_manager,
                eid,
                ttl_seconds=20,
                max_total_lease_seconds=10,
                client_deadline_seconds=1,
                buffer_margin_seconds=14,
            ):
                pass

        with pytest.raises(LockAcquisitionError, match="deadline|T_client"):
            async with _lease_with_timeout_contract(
                lock_manager,
                eid,
                ttl_seconds=20,
                max_total_lease_seconds=10,
                client_deadline_seconds=6,
                buffer_margin_seconds=15,
            ):
                pass


class TestLeaseAutoRenewal:
    """LE-01: Long-running task with auto-renew under TTL stays locked."""

    @pytest.mark.asyncio
    async def test_lease_auto_renew_stays_locked(self, lock_manager, redis_client):
        """Lease auto-renews and keeps the lock held during the task."""
        eid = str(uuid.uuid4())
        lock_key = f"aep:lock:{eid}"

        # TTL leaves the mandatory 15-second safety buffer; the explicit
        # deadline keeps the test fast and drives a shorter heartbeat interval.
        async with lock_manager.lease(
            eid,
            ttl_seconds=20,
            max_total_lease_seconds=10,
            client_deadline_seconds=5,
            buffer_margin_seconds=15,
        ) as token:
            assert token is not None

            # Task runs and checks that lock is held
            for i in range(3):
                # Check lock exists
                stored = await redis_client.get(lock_key)
                assert stored == token

                # Sleep to let heartbeat run
                await asyncio.sleep(1.5)

                # Check lock still held after sleep
                stored = await redis_client.get(lock_key)
                assert stored == token

        # After exit, lock should be gone
        stored = await redis_client.get(lock_key)
        assert stored is None

    @pytest.mark.asyncio
    async def test_lease_yields_none_when_unavailable(self, lock_manager):
        """Lease yields None when the lock is already held."""
        eid = str(uuid.uuid4())

        # Acquire the lock manually
        token1 = await lock_manager.acquire_lock(eid, ttl_seconds=60)
        assert token1 is not None

        # Try to get a lease; should yield None
        async with lock_manager.lease(eid, ttl_seconds=60) as token:
            assert token is None

        # Release the manual lock
        await lock_manager.release_lock(eid, token1)

    @pytest.mark.asyncio
    async def test_lease_cleanup_on_exception(self, lock_manager, redis_client):
        """Lease cleanup happens even if task raises an exception."""
        eid = str(uuid.uuid4())
        lock_key = f"aep:lock:{eid}"

        with pytest.raises(ValueError):
            async with lock_manager.lease(
                eid,
                ttl_seconds=20,
                client_deadline_seconds=5,
                buffer_margin_seconds=15,
            ) as token:
                assert token is not None
                raise ValueError("Test error")

        # Lock should still be cleaned up
        stored = await redis_client.get(lock_key)
        assert stored is None


class TestLeaseHardCap:
    """LE-02: Task exceeds max_total_lease; renewal stops; lock expires."""

    @pytest.mark.asyncio
    async def test_lease_hard_cap_stops_renewal(
        self, lock_manager, redis_client, caplog, monkeypatch
    ):
        """Lease renewal stops when max_total_lease_seconds is reached."""
        eid = str(uuid.uuid4())
        lock_key = f"aep:lock:{eid}"
        original_renew = lock_manager.renew_lock
        renewal_count = 0

        async def counted_renew(*args, **kwargs):
            nonlocal renewal_count
            renewal_count += 1
            return await original_renew(*args, **kwargs)

        async def leave_lock_to_expire(*args, **kwargs):
            return True

        monkeypatch.setattr(lock_manager, "renew_lock", counted_renew)
        monkeypatch.setattr(lock_manager, "release_lock", leave_lock_to_expire)

        # Keep the lock after context cleanup so its TTL reveals whether a
        # zombie heartbeat is still extending it after the short hard cap.
        with pytest.raises(asyncio.CancelledError):
            async with lock_manager.lease(
                eid,
                ttl_seconds=20,
                max_total_lease_seconds=0.6,
                client_deadline_seconds=5,
                buffer_margin_seconds=15,
            ) as token:
                assert token is not None

                # The hard cap cancels this sleep.
                await asyncio.sleep(1)

        assert renewal_count > 0
        renewals_at_cap = renewal_count
        ttl_at_cap = await redis_client.pttl(lock_key)
        assert ttl_at_cap > 0
        await asyncio.sleep(0.3)
        ttl_after_wait = await redis_client.pttl(lock_key)
        assert renewal_count == renewals_at_cap
        assert 0 < ttl_after_wait < ttl_at_cap - 150

        # Check for the cap warning in logs
        cap_warning_found = any(
            "lease hard cap" in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        )
        assert cap_warning_found, "Expected cap warning in logs"

    @pytest.mark.asyncio
    async def test_lease_cap_prevents_zombie_renewal(
        self, lock_manager, redis_client, monkeypatch
    ):
        """Lease cap ensures lock expires even if task is hung."""
        eid = str(uuid.uuid4())
        lock_key = f"aep:lock:{eid}"
        short_ttl_ms = 500
        original_acquire = lock_manager.acquire_lock
        original_renew = lock_manager.renew_lock
        renewal_count = 0

        async def acquire_with_short_redis_ttl(*args, **kwargs):
            token = await original_acquire(*args, **kwargs)
            if token is not None:
                await redis_client.pexpire(lock_key, short_ttl_ms)
            return token

        async def renew_with_short_redis_ttl(
            execution_id, lock_token, extend_ms=30000
        ):
            nonlocal renewal_count
            renewal_count += 1
            return await original_renew(
                execution_id, lock_token, extend_ms=short_ttl_ms
            )

        async def leave_lock_to_expire(*args, **kwargs):
            return True

        monkeypatch.setattr(
            lock_manager, "acquire_lock", acquire_with_short_redis_ttl
        )
        monkeypatch.setattr(
            lock_manager, "renew_lock", renew_with_short_redis_ttl
        )
        monkeypatch.setattr(lock_manager, "release_lock", leave_lock_to_expire)

        # The wrappers preserve lease logic while using a sub-second Redis
        # TTL, making real expiry observable without a 20-second wait.
        with pytest.raises(asyncio.CancelledError):
            async with lock_manager.lease(
                eid,
                ttl_seconds=20,
                max_total_lease_seconds=0.6,
                client_deadline_seconds=5,
                buffer_margin_seconds=15,
            ) as token:
                assert token is not None
                await asyncio.sleep(1)

        assert await redis_client.get(lock_key) == token
        renewals_at_cap = renewal_count
        await asyncio.sleep(0.65)
        assert await redis_client.get(lock_key) is None
        await asyncio.sleep(0.25)
        assert renewal_count == renewals_at_cap
        assert await redis_client.get(lock_key) is None

    @pytest.mark.asyncio
    async def test_lease_no_cap_allows_indefinite_renewal(
        self, lock_manager, redis_client
    ):
        """Without a cap (very high value), renewal continues."""
        eid = str(uuid.uuid4())
        lock_key = f"aep:lock:{eid}"

        # TTL 1 second, cap 100 seconds (very high)
        async with lock_manager.lease(
            eid,
            ttl_seconds=20,
            max_total_lease_seconds=100,
            client_deadline_seconds=5,
            buffer_margin_seconds=15,
        ) as token:
            assert token is not None

            # Do multiple checks; lock should still be held
            for _ in range(5):
                stored = await redis_client.get(lock_key)
                assert stored == token
                await asyncio.sleep(0.5)

        # After normal exit, lock gone
        stored = await redis_client.get(lock_key)
        assert stored is None


class TestLeaseLossCancellation:
    """Regression coverage: lease loss must cancel the protected task."""

    @pytest.mark.asyncio
    async def test_hard_cap_cancels_owner_before_rival_can_overlap(
        self, lock_manager
    ):
        eid = str(uuid.uuid4())
        active = asyncio.Event()

        async def original_worker():
            async with lock_manager.lease(
                eid,
                ttl_seconds=20,
                max_total_lease_seconds=0.4,
                client_deadline_seconds=5,
                buffer_margin_seconds=15,
            ) as token:
                assert token is not None
                active.set()
                try:
                    await asyncio.sleep(1.6)
                    return "continued-after-cap"
                finally:
                    active.clear()

        async def rival_worker():
            await active.wait()
            deadline = asyncio.get_running_loop().time() + 2.0
            while asyncio.get_running_loop().time() < deadline:
                token = await lock_manager.acquire_lock(eid, ttl_seconds=5)
                if token is not None:
                    overlapped = active.is_set()
                    await lock_manager.release_lock(eid, token)
                    return overlapped
                await asyncio.sleep(0.05)
            pytest.fail("Rival never acquired the lock after lease termination")

        owner_result, rival_overlapped = await asyncio.gather(
            original_worker(), rival_worker(), return_exceptions=True
        )

        assert isinstance(owner_result, asyncio.CancelledError)
        assert rival_overlapped is False

    @pytest.mark.asyncio
    async def test_failed_renewal_cancels_protected_task(
        self, lock_manager, redis_client
    ):
        eid = str(uuid.uuid4())
        lock_key = f"aep:lock:{eid}"
        started = asyncio.Event()

        async def protected_worker():
            async with lock_manager.lease(
                eid,
                ttl_seconds=20,
                max_total_lease_seconds=10,
                client_deadline_seconds=2,
                buffer_margin_seconds=15,
            ) as token:
                assert token is not None
                started.set()
                await asyncio.sleep(1.0)
                return "continued-after-renewal-loss"

        task = asyncio.create_task(protected_worker())
        await started.wait()
        await redis_client.delete(lock_key)
        result = (await asyncio.gather(task, return_exceptions=True))[0]

        assert isinstance(result, asyncio.CancelledError)
