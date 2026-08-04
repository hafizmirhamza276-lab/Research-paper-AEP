"""Lock adversarial tests (L-01..L-05).

Tests for the distributed lock manager: acquire, release, renew primitives.
Covers double-acquire, release with correct/wrong tokens, and TTL extension.
"""

import uuid

import pytest


class TestDoubleAcquire:
    """L-01: Double-acquire of a held lock returns None on second attempt."""

    @pytest.mark.asyncio
    async def test_lock_double_acquire_returns_none(self, lock_manager):
        """Second acquire while lock is held returns None."""
        eid = str(uuid.uuid4())

        # First acquire succeeds
        token1 = await lock_manager.acquire_lock(eid, ttl_seconds=60)
        assert token1 is not None

        # Second acquire returns None (not an error)
        token2 = await lock_manager.acquire_lock(eid, ttl_seconds=60)
        assert token2 is None

        # Clean up
        await lock_manager.release_lock(eid, token1)

    @pytest.mark.asyncio
    async def test_lock_tokens_are_unique(self, lock_manager):
        """Different acquire calls return different tokens."""
        eid1 = str(uuid.uuid4())
        eid2 = str(uuid.uuid4())

        token1 = await lock_manager.acquire_lock(eid1, ttl_seconds=60)
        token2 = await lock_manager.acquire_lock(eid2, ttl_seconds=60)

        assert token1 != token2
        assert len(token1) > 0
        assert len(token2) > 0

        await lock_manager.release_lock(eid1, token1)
        await lock_manager.release_lock(eid2, token2)


class TestReleaseCorrectToken:
    """L-02: Release with correct token succeeds and key is gone."""

    @pytest.mark.asyncio
    async def test_lock_release_correct_token_succeeds(self, lock_manager, redis_client):
        """Release with correct token returns True and deletes key."""
        eid = str(uuid.uuid4())

        token = await lock_manager.acquire_lock(eid, ttl_seconds=60)
        assert token is not None

        # Verify key exists
        lock_key = f"aep:lock:{eid}"
        stored_value = await redis_client.get(lock_key)
        assert stored_value == token

        # Release
        result = await lock_manager.release_lock(eid, token)
        assert result is True

        # Verify key is gone
        stored_value = await redis_client.get(lock_key)
        assert stored_value is None


class TestReleaseWrongToken:
    """L-03: Release with wrong token returns False and logs warning."""

    @pytest.mark.asyncio
    async def test_lock_release_wrong_token_returns_false(
        self, lock_manager, caplog
    ):
        """Release with wrong token returns False and logs warning."""
        eid = str(uuid.uuid4())

        token = await lock_manager.acquire_lock(eid, ttl_seconds=60)
        assert token is not None

        # Try to release with a different token
        wrong_token = "wrong-token-value"
        result = await lock_manager.release_lock(eid, wrong_token)
        assert result is False

        # Check that a warning was logged
        assert any(
            "lease expired or re-acquired" in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        )

    @pytest.mark.asyncio
    async def test_lock_release_expired_token_returns_false(
        self, lock_manager, redis_client, caplog
    ):
        """Release after lock expires returns False and logs warning."""
        eid = str(uuid.uuid4())

        token = await lock_manager.acquire_lock(eid, ttl_seconds=1)
        assert token is not None

        # Manually delete the lock to simulate expiry
        lock_key = f"aep:lock:{eid}"
        await redis_client.delete(lock_key)

        # Release now returns False
        result = await lock_manager.release_lock(eid, token)
        assert result is False

        # Check for warning
        assert any(
            "lease expired" in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        )


class TestRenewCorrectToken:
    """L-04: Renew with correct token extends TTL."""

    @pytest.mark.asyncio
    async def test_lock_renew_correct_token_extends_ttl(
        self, lock_manager, redis_client
    ):
        """Renew with correct token extends TTL (verified via PTTL)."""
        eid = str(uuid.uuid4())

        token = await lock_manager.acquire_lock(eid, ttl_seconds=60)
        assert token is not None

        lock_key = f"aep:lock:{eid}"

        # Get initial TTL in milliseconds
        pttl_before = await redis_client.pttl(lock_key)
        assert pttl_before > 0

        # Renew for 30 seconds (30000 ms)
        result = await lock_manager.renew_lock(eid, token, extend_ms=30000)
        assert result is True

        # Get new TTL
        pttl_after = await redis_client.pttl(lock_key)
        assert pttl_after > 0

        # The new TTL should be close to 30000 ms
        # (allow some jitter, but should be > 25000)
        assert pttl_after > 25000

        await lock_manager.release_lock(eid, token)

    @pytest.mark.asyncio
    async def test_lock_renew_multiple_times(self, lock_manager, redis_client):
        """Renewing multiple times keeps the lock alive."""
        eid = str(uuid.uuid4())

        token = await lock_manager.acquire_lock(eid, ttl_seconds=10)
        lock_key = f"aep:lock:{eid}"

        # Renew 3 times
        for _ in range(3):
            result = await lock_manager.renew_lock(eid, token, extend_ms=10000)
            assert result is True

            # Verify key still exists
            stored = await redis_client.get(lock_key)
            assert stored == token

        await lock_manager.release_lock(eid, token)


class TestRenewWrongToken:
    """L-05: Renew with wrong token returns False."""

    @pytest.mark.asyncio
    async def test_lock_renew_wrong_token_returns_false(self, lock_manager):
        """Renew with wrong token returns False."""
        eid = str(uuid.uuid4())

        token = await lock_manager.acquire_lock(eid, ttl_seconds=60)
        assert token is not None

        # Try to renew with wrong token
        wrong_token = "wrong-token-value"
        result = await lock_manager.renew_lock(eid, wrong_token, extend_ms=30000)
        assert result is False

        # The actual token should still work
        result = await lock_manager.renew_lock(eid, token, extend_ms=30000)
        assert result is True

        await lock_manager.release_lock(eid, token)

    @pytest.mark.asyncio
    async def test_lock_renew_expired_token_returns_false(
        self, lock_manager, redis_client
    ):
        """Renew after lock expires returns False."""
        eid = str(uuid.uuid4())

        token = await lock_manager.acquire_lock(eid, ttl_seconds=1)
        assert token is not None

        # Manually delete the lock
        lock_key = f"aep:lock:{eid}"
        await redis_client.delete(lock_key)

        # Renew now returns False
        result = await lock_manager.renew_lock(eid, token, extend_ms=30000)
        assert result is False
