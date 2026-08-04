"""Pytest configuration and fixtures for AEP adversarial tests.

Execution rule (per the aep-adversarial-testing skill):
    Areas C (CAS), R (races), G-03/G-04 (cjson-touching corruption), and LE
    (lease) MUST run against a real Redis whenever possible. fakeredis may
    lack cjson; if it does, those tests skip with a clear reason rather
    than producing misleading failures.

Selection policy:
    1. If env var REDIS_URL is set, use a real redis.asyncio.Redis bound to
       it. This is the preferred path for full coverage.
    2. Otherwise fall back to fakeredis[lua]. At fixture setup the conftest
       probes cjson via EVAL; tests that require cjson (CAS / race / lease)
       skip if the probe fails.

Safety policy:
    A real Redis must use the dedicated test database 15 unless the developer
    explicitly opts in with AEP_TEST_ALLOW_FLUSHALL=1. Cleanup never calls
    FLUSHALL; it incrementally deletes only keys in the ``aep:*`` namespace.
"""

from __future__ import annotations

import os
from typing import AsyncIterator

import pytest
import pytest_asyncio

from src.core.locks import DistributedLockManager
from src.core.storage import RedisStorageAdapter

# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

REDIS_URL = os.environ.get("REDIS_URL")  # e.g. "redis://localhost:6379/15"
USING_REAL_REDIS = bool(REDIS_URL)
_ALLOWED_REAL_REDIS_DATABASES = frozenset({15})

# Try to import a fakeredis async client only if we are not using real Redis.
_FAKEREDIS_AVAILABLE = False
if not USING_REAL_REDIS:
    try:
        from fakeredis import aioredis as _fake_aioredis  # noqa: F401
        _FAKEREDIS_AVAILABLE = True
    except ImportError:
        _FAKEREDIS_AVAILABLE = False


def pytest_configure(config) -> None:
    """Abort the session when no Redis test backend can be constructed."""
    if not USING_REAL_REDIS and not _FAKEREDIS_AVAILABLE:
        raise pytest.UsageError(
            "Redis test backend unavailable: set REDIS_URL to a dedicated "
            "test Redis database (DB 15 is allowed by default), or install "
            "fakeredis[lua]. Refusing to skip Redis-backed tests."
        )


async def _probe_cjson(client) -> bool:
    """Return True iff the connected Redis (real or fake) has cjson in EVAL.

    The CAS Lua script depends on cjson.decode. If the backend lacks it,
    CAS tests cannot run honestly and should skip rather than mis-fail.
    """
    try:
        # Trivial round-trip: encode + decode a tiny table. If cjson is
        # missing this raises a Lua error, which the client wraps.
        result = await client.eval(
            "return cjson.encode({1,2,3})", 0
        )
        return result is not None
    except Exception:
        return False


async def _build_client():
    """Construct a client per the selection policy. Caller closes it."""
    if USING_REAL_REDIS:
        from redis.asyncio import Redis as AsyncRedis
        return AsyncRedis.from_url(REDIS_URL, decode_responses=True)
    if not _FAKEREDIS_AVAILABLE:
        raise RuntimeError(
            "Redis test backend unavailable: set REDIS_URL or install "
            "fakeredis[lua]."
        )
    from fakeredis import aioredis as fake_aioredis
    return fake_aioredis.FakeRedis(decode_responses=True)


async def _real_redis_db_index(client) -> int:
    """Return the selected DB, preferring the server's client metadata."""
    await client.ping()
    try:
        client_info = await client.client_info()
        return int(client_info["db"])
    except Exception:  # noqa: BLE001 -- compatibility fallback after PING
        # Some older Redis-compatible servers do not implement CLIENT INFO,
        # or an ACL may permit test commands while denying client metadata.
        configured_db = client.connection_pool.connection_kwargs.get("db", 0)
        return int(configured_db)


async def _assert_safe_cleanup_target(client) -> None:
    """Refuse destructive test setup on a non-dedicated real Redis DB."""
    if not USING_REAL_REDIS:
        return

    try:
        db_index = await _real_redis_db_index(client)
    except Exception as exc:
        raise RuntimeError(
            f"Unable to connect to the Redis test backend at {REDIS_URL!r}: "
            f"{exc}"
        ) from exc

    explicitly_allowed = os.environ.get("AEP_TEST_ALLOW_FLUSHALL") == "1"
    if db_index not in _ALLOWED_REAL_REDIS_DATABASES and not explicitly_allowed:
        allowed = ", ".join(map(str, sorted(_ALLOWED_REAL_REDIS_DATABASES)))
        raise RuntimeError(
            f"Refusing Redis test cleanup on DB {db_index}. Allowed dedicated "
            f"test DB(s): {allowed}. Point REDIS_URL at DB 15, or explicitly "
            "set AEP_TEST_ALLOW_FLUSHALL=1 to override. Even with the override, "
            "cleanup remains limited to aep:* keys."
        )


async def _delete_aep_test_keys(client) -> None:
    """Delete only AEP-owned keys without blocking Redis with KEYS/FLUSHALL."""
    batch = []
    async for key in client.scan_iter(match="aep:*", count=500):
        batch.append(key)
        if len(batch) == 500:
            await client.delete(*batch)
            batch.clear()
    if batch:
        await client.delete(*batch)


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator:
    """Per-test client with guarded, namespace-scoped cleanup."""
    client = await _build_client()
    cleanup_is_safe = False
    try:
        await _assert_safe_cleanup_target(client)
        cleanup_is_safe = True
        await _delete_aep_test_keys(client)
        yield client
    finally:
        try:
            if cleanup_is_safe:
                await _delete_aep_test_keys(client)
        finally:
            try:
                await client.aclose()
            except AttributeError:
                # Older clients expose .close() instead of .aclose().
                await client.close()


@pytest_asyncio.fixture
async def cjson_available(redis_client) -> bool:
    """True iff the current backend supports cjson in EVAL.

    Tests that exercise the CAS Lua script (areas C and R-02) MUST depend
    on this fixture and skip if it is False.
    """
    ok = await _probe_cjson(redis_client)
    return ok


@pytest_asyncio.fixture
async def storage_adapter(redis_client, cjson_available):
    """RedisStorageAdapter bound to the per-test client.

    save_state and get_state both touch the CAS Lua, which requires cjson.
    If the backend lacks cjson, skip — running these tests against a
    cjson-less backend produces misleading failures (wrapped Lua errors
    instead of the typed exceptions the test asserts).
    """
    if not cjson_available:
        pytest.skip(
            "cjson is not available in this Redis backend. "
            "Set REDIS_URL to a real Redis (Docker: `docker run --rm -p "
            "6379:6379 redis:7`) or install a fakeredis build that ships "
            "lupa with cjson."
        )
    return RedisStorageAdapter(redis_client)


@pytest_asyncio.fixture
async def lock_manager(redis_client):
    """DistributedLockManager. Lock Lua scripts do not require cjson, so this
    fixture does not gate on cjson_available."""
    return DistributedLockManager(redis_client)


@pytest_asyncio.fixture
async def locked_save(storage_adapter, lock_manager):
    """Save helper that owns one live lock per execution for the test."""
    tokens = {}

    async def _save(state, *, expected_version=None, ttl_seconds=172800):
        token = tokens.get(state.execution_id)
        if token is None:
            token = await lock_manager.acquire_lock(
                state.execution_id, ttl_seconds=60
            )
            assert token is not None
            tokens[state.execution_id] = token
        if expected_version is None:
            expected_version = state.version - 1
        return await storage_adapter.save_state(
            state,
            expected_version=expected_version,
            lock_token=token,
            ttl_seconds=ttl_seconds,
        )

    try:
        yield _save
    finally:
        for execution_id, token in tokens.items():
            await lock_manager.release_lock(execution_id, token)


def _xfail_if_no_cjson(request) -> None:
    """Helper for tests that read fixtures other than storage_adapter but
    still need cjson (e.g. the lease test that calls save_state directly)."""
    if "cjson_available" in request.fixturenames:
        if not request.getfixturevalue("cjson_available"):
            pytest.skip("cjson required and not available in this backend.")
