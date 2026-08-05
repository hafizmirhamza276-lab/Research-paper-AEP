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
    Cleanup never calls FLUSHALL; it incrementally UNLINKs only keys in the
    ``aep:*`` namespace. On a real Redis two independent preconditions must
    both hold before any destructive operation:

    1. The selected database must be the dedicated test database 15, unless
       the developer explicitly opts in with AEP_TEST_ALLOW_NONSTANDARD_DB=1
       (the legacy name AEP_TEST_ALLOW_FLUSHALL=1 is still accepted).
    2. The instance must advertise the test marker key
       ``aep:test-instance-marker``. Namespace-scoped cleanup alone is NOT a
       sufficient guard, because ``aep:*`` is precisely the namespace AEP
       uses in production — a mis-pointed REDIS_URL would delete exactly the
       production keys the scoping was meant to protect. The marker is the
       instance's own assertion that it is disposable.

    The marker is auto-provisioned only when the instance is demonstrably not
    production: real Redis, DB in the allowed set, and DBSIZE == 0. In every
    other case (override in use, non-empty database) it must be set
    out-of-band, e.g.::

        redis-cli -n 15 SET aep:test-instance-marker 1

    The marker key is never deleted by cleanup.
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

#: The instance's own assertion that it is a disposable test instance.
#: Required on real Redis before any destructive operation. Never deleted
#: by cleanup (see ``_delete_aep_test_keys``).
TEST_INSTANCE_MARKER_KEY = "aep:test-instance-marker"

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


def _nonstandard_db_override_enabled() -> bool:
    """True iff the developer opted into a real Redis DB outside the allowed set.

    ``AEP_TEST_ALLOW_FLUSHALL`` is the legacy spelling, kept working so that
    existing developer environments and CI definitions do not silently change
    meaning. Nothing has called FLUSHALL since the cleanup rewrite; the
    accurate name is ``AEP_TEST_ALLOW_NONSTANDARD_DB``.
    """
    return (
        os.environ.get("AEP_TEST_ALLOW_NONSTANDARD_DB") == "1"
        or os.environ.get("AEP_TEST_ALLOW_FLUSHALL") == "1"
    )


async def _assert_test_instance_marker(client, db_index: int) -> None:
    """Require the instance to advertise that it is disposable.

    Namespace scoping is not self-sufficient: ``aep:*`` is the namespace AEP
    uses in production, so a mis-pointed REDIS_URL would delete exactly the
    keys the scoping was meant to protect. The marker closes that hole.

    Auto-provisioned only when the instance is demonstrably not production:
    an allowed DB that is completely empty. A non-empty database — or one
    reached through the override — must be marked out-of-band, which forces a
    human to look at the instance before it can be written to.
    """
    if await client.exists(TEST_INSTANCE_MARKER_KEY):
        return

    db_is_allowed = db_index in _ALLOWED_REAL_REDIS_DATABASES
    if db_is_allowed and await client.dbsize() == 0:
        await client.set(TEST_INSTANCE_MARKER_KEY, "1")
        return

    raise RuntimeError(
        f"Refusing Redis test cleanup: DB {db_index} at {REDIS_URL!r} does not "
        f"advertise the test marker key {TEST_INSTANCE_MARKER_KEY!r}. The "
        "marker is auto-created only on an allowed, completely empty database; "
        "this one is non-empty or outside the allowed set, so it cannot be "
        "assumed disposable. If this instance really is a throwaway test "
        f"instance, mark it explicitly:\n"
        f"    redis-cli -n {db_index} SET {TEST_INSTANCE_MARKER_KEY} 1"
    )


async def _assert_safe_cleanup_target(client) -> None:
    """Refuse destructive test setup unless BOTH safety preconditions hold."""
    if not USING_REAL_REDIS:
        return

    try:
        db_index = await _real_redis_db_index(client)
    except Exception as exc:
        raise RuntimeError(
            f"Unable to connect to the Redis test backend at {REDIS_URL!r}: "
            f"{exc}"
        ) from exc

    # Precondition 1 — dedicated database.
    if (
        db_index not in _ALLOWED_REAL_REDIS_DATABASES
        and not _nonstandard_db_override_enabled()
    ):
        allowed = ", ".join(map(str, sorted(_ALLOWED_REAL_REDIS_DATABASES)))
        raise RuntimeError(
            f"Refusing Redis test cleanup on DB {db_index}. Allowed dedicated "
            f"test DB(s): {allowed}. Point REDIS_URL at DB 15, or explicitly "
            "set AEP_TEST_ALLOW_NONSTANDARD_DB=1 to override. Even with the "
            "override, cleanup remains limited to aep:* keys AND the instance "
            f"must still advertise {TEST_INSTANCE_MARKER_KEY!r}."
        )

    # Precondition 2 — the instance asserts it is disposable. Not weakened by
    # the override above: that override widens which DB is acceptable, it does
    # not license writing to an unmarked instance.
    await _assert_test_instance_marker(client, db_index)


def _is_test_instance_marker(key) -> bool:
    """True for the marker key, whether the client decodes responses or not."""
    if isinstance(key, bytes):
        key = key.decode("utf-8", errors="replace")
    return key == TEST_INSTANCE_MARKER_KEY


async def _delete_aep_test_keys(client) -> None:
    """UNLINK only AEP-owned keys without blocking Redis with KEYS/FLUSHALL.

    UNLINK reclaims memory on a background thread, so a large test keyspace
    cannot stall the server the way DEL would. The marker key is preserved:
    deleting it would make the very next fixture re-derive the instance's
    disposability from DBSIZE instead of from the operator's assertion.
    """
    batch = []
    async for key in client.scan_iter(match="aep:*", count=500):
        if _is_test_instance_marker(key):
            continue
        batch.append(key)
        if len(batch) == 500:
            await client.unlink(*batch)
            batch.clear()
    if batch:
        await client.unlink(*batch)


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
