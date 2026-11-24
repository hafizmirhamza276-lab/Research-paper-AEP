"""Regression tests for the destructive-cleanup guards in tests/conftest.py.

The fixture that every other test depends on is itself a destructive
operation against a live Redis. These tests pin its two safety preconditions
so a future edit cannot quietly widen the blast radius:

  1. cleanup touches only ``aep:*`` and never the test-instance marker;
  2. an unmarked, non-empty instance is refused outright.

Precondition 2 exists because namespace scoping is not self-sufficient:
``aep:*`` is the namespace AEP uses in production, so a mis-pointed REDIS_URL
would delete exactly the keys the scoping was meant to protect.
"""

from __future__ import annotations

import pytest

from tests.conftest import (
    TEST_INSTANCE_MARKER_KEY,
    _assert_test_instance_marker,
    _delete_aep_test_keys,
    _is_aep_test_key,
    _is_test_instance_marker,
    _nonstandard_db_override_enabled,
)


# ---------------------------------------------------------------------------
# A deterministic stand-in for the guard's view of an instance. Using a stub
# rather than the live database keeps these assertions independent of whatever
# keys a concurrent test happens to have written.
# ---------------------------------------------------------------------------


class _StubClient:
    def __init__(self, *, keys: dict[str, str] | None = None):
        self.keys = dict(keys or {})
        self.sets: list[tuple[str, str]] = []

    async def exists(self, key: str) -> int:
        return 1 if key in self.keys else 0

    async def dbsize(self) -> int:
        return len(self.keys)

    async def set(self, key: str, value: str) -> None:
        self.keys[key] = value
        self.sets.append((key, value))


_ALLOWED_DB = 15
_DISALLOWED_DB = 0


async def test_marker_absent_and_database_not_empty_is_refused():
    """The dangerous case: a populated instance that never claimed to be a test one."""
    client = _StubClient(keys={"aep:execution:live": "production payload"})

    with pytest.raises(RuntimeError) as excinfo:
        await _assert_test_instance_marker(client, _ALLOWED_DB)

    message = str(excinfo.value)
    assert TEST_INSTANCE_MARKER_KEY in message
    assert "Refusing Redis test cleanup" in message
    # It must tell the operator how to proceed deliberately.
    assert f"SET {TEST_INSTANCE_MARKER_KEY} 1" in message
    # And it must not have written anything on the way out.
    assert client.sets == []


async def test_marker_absent_on_disallowed_database_is_refused_even_when_empty():
    """The override widens which DB is acceptable; it never licenses an unmarked one."""
    client = _StubClient()

    with pytest.raises(RuntimeError):
        await _assert_test_instance_marker(client, _DISALLOWED_DB)

    assert client.sets == []


async def test_marker_is_auto_provisioned_only_on_an_empty_allowed_database():
    """Ergonomic path: a fresh throwaway container needs no manual setup."""
    client = _StubClient()

    await _assert_test_instance_marker(client, _ALLOWED_DB)

    assert client.sets == [(TEST_INSTANCE_MARKER_KEY, "1")]


async def test_existing_marker_is_accepted_without_rewriting_it():
    client = _StubClient(
        keys={TEST_INSTANCE_MARKER_KEY: "1", "aep:execution:leftover": "x"}
    )

    await _assert_test_instance_marker(client, _ALLOWED_DB)

    assert client.sets == []


async def test_existing_marker_admits_a_disallowed_database():
    """An explicitly marked instance is disposable regardless of its DB index."""
    client = _StubClient(keys={TEST_INSTANCE_MARKER_KEY: "1"})

    await _assert_test_instance_marker(client, _DISALLOWED_DB)

    assert client.sets == []


# ---------------------------------------------------------------------------
# Override plumbing
# ---------------------------------------------------------------------------


def test_override_is_off_by_default(monkeypatch):
    monkeypatch.delenv("AEP_TEST_ALLOW_NONSTANDARD_DB", raising=False)
    monkeypatch.delenv("AEP_TEST_ALLOW_FLUSHALL", raising=False)

    assert _nonstandard_db_override_enabled() is False


@pytest.mark.parametrize(
    "variable",
    ["AEP_TEST_ALLOW_NONSTANDARD_DB", "AEP_TEST_ALLOW_FLUSHALL"],
)
def test_override_honours_both_the_current_and_legacy_names(monkeypatch, variable):
    """The legacy spelling stays working so existing environments keep meaning."""
    monkeypatch.delenv("AEP_TEST_ALLOW_NONSTANDARD_DB", raising=False)
    monkeypatch.delenv("AEP_TEST_ALLOW_FLUSHALL", raising=False)
    monkeypatch.setenv(variable, "1")

    assert _nonstandard_db_override_enabled() is True


@pytest.mark.parametrize("value", ["0", "", "true", "yes"])
def test_override_requires_exactly_one(monkeypatch, value):
    monkeypatch.delenv("AEP_TEST_ALLOW_NONSTANDARD_DB", raising=False)
    monkeypatch.setenv("AEP_TEST_ALLOW_FLUSHALL", value)

    assert _nonstandard_db_override_enabled() is False


# ---------------------------------------------------------------------------
# Marker identification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [TEST_INSTANCE_MARKER_KEY, TEST_INSTANCE_MARKER_KEY.encode()],
)
def test_marker_is_recognised_whether_or_not_responses_are_decoded(key):
    assert _is_test_instance_marker(key) is True


@pytest.mark.parametrize(
    "key",
    ["aep:execution:abc", "aep:test-instance-marker:extra", b"aep:lock:abc", ""],
)
def test_non_marker_keys_are_not_mistaken_for_the_marker(key):
    assert _is_test_instance_marker(key) is False


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("aep:execution:abc", True),
        (b"aep:lock:abc", True),
        ("not-aep:execution:abc", False),
        (b"not-aep:lock:abc", False),
        (object(), False),
    ],
)
def test_aep_namespace_is_recognised_for_byte_and_decoded_responses(key, expected):
    assert _is_aep_test_key(key) is expected


class _RecordingScanClient:
    """SCAN/UNLINK recorder that can return bytes or decoded strings."""

    def __init__(self, keys):
        self.keys = list(keys)
        self.scan_calls = []
        self.unlink_calls = []

    async def scan_iter(self, *, match, count):
        self.scan_calls.append((match, count))
        for key in self.keys:
            yield key

    async def unlink(self, *keys):
        self.unlink_calls.append(keys)


@pytest.mark.parametrize("decoded", [True, False])
async def test_cleanup_scans_first_then_unlinks_in_bounded_batches(decoded):
    def response(value):
        return value if decoded else value.encode()

    matching = [response(f"aep:execution:recording-{index}") for index in range(1203)]
    marker = response(TEST_INSTANCE_MARKER_KEY)
    foreign = response("not-aep:recording-probe")
    client = _RecordingScanClient([*matching, marker, foreign])

    await _delete_aep_test_keys(client)

    assert client.scan_calls == [("aep:*", 500)]
    assert [len(batch) for batch in client.unlink_calls] == [500, 500, 203]
    assert [key for batch in client.unlink_calls for key in batch] == matching
    assert marker not in {key for batch in client.unlink_calls for key in batch}
    assert foreign not in {key for batch in client.unlink_calls for key in batch}


# ---------------------------------------------------------------------------
# Cleanup blast radius, against the live backend
# ---------------------------------------------------------------------------


async def test_cleanup_removes_aep_keys_but_preserves_the_marker(redis_client):
    await redis_client.set(TEST_INSTANCE_MARKER_KEY, "1")
    await redis_client.set("aep:execution:cleanup-probe", "delete me")

    await _delete_aep_test_keys(redis_client)

    assert await redis_client.exists("aep:execution:cleanup-probe") == 0
    assert await redis_client.exists(TEST_INSTANCE_MARKER_KEY) == 1


async def test_cleanup_does_not_touch_keys_outside_the_aep_namespace(redis_client):
    foreign_key = "not-aep:conftest-safety-probe"
    await redis_client.set(foreign_key, "keep me")
    await redis_client.set("aep:execution:cleanup-probe", "delete me")
    try:
        await _delete_aep_test_keys(redis_client)

        assert await redis_client.exists("aep:execution:cleanup-probe") == 0
        assert await redis_client.get(foreign_key) == "keep me"
    finally:
        # Namespace-scoped cleanup will not reclaim this one; do it here.
        await redis_client.unlink(foreign_key)


async def test_cleanup_spans_more_keys_than_one_scan_batch(redis_client):
    """The batching path (count=500) must not drop the tail of the keyspace."""
    written = [f"aep:execution:batch-probe-{index}" for index in range(600)]
    for key in written:
        await redis_client.set(key, "x")

    await _delete_aep_test_keys(redis_client)

    remaining = [key async for key in redis_client.scan_iter(match="aep:execution:batch-probe-*")]
    assert remaining == []
