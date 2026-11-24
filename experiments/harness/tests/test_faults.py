"""Infrastructure faults, exercised against the real containers.

These tests are the evidence for amendment C3's two non-worker faults. Both
are written so that the *absence* of the fault fails them: a partition test
that only asserted "the toxic was created" would pass against a proxy that
forwarded every byte, and a restart test that only asserted "the container came
back" would pass against a Redis that came back empty.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest
from redis.asyncio import Redis

from experiments.harness.config import RunConfig
from experiments.harness.faults import (
    PARTITION_TOXIC_NAME,
    FaultInjectionError,
    ToxiproxyControl,
    restart_redis_and_verify_aof,
)

pytestmark = [
    pytest.mark.redis72_integration,
    pytest.mark.skipif(
        os.environ.get("AEP_PHASE2_REDIS_INTEGRATION") != "1",
        reason=(
            "set AEP_PHASE2_REDIS_INTEGRATION=1 and REDIS_URL to the "
            "dedicated Redis 7.2+ AOF DB 15, with compose.phase2.yml up"
        ),
    ),
]

PROXY_URL = "redis://127.0.0.1:6382/15"


def config(tmp_path, **overrides) -> RunConfig:
    defaults = dict(
        run_id="run-faults-test",
        seed=1,
        workers=1,
        executions_per_worker=1,
        endpoint="payments",
        mock_api_config_path="unused.yaml",
        mock_api_base_url="http://127.0.0.1:8099",
        redis_url=os.environ["REDIS_URL"],
        results_root=str(tmp_path),
    )
    defaults.update(overrides)
    return RunConfig(**defaults)


@pytest.fixture
def toxiproxy():
    control = ToxiproxyControl(
        api_url="http://127.0.0.1:8474", proxy_name="aep-redis"
    )
    try:
        control.heal()
        yield control
    finally:
        try:
            control.heal()
        finally:
            control.close()


# ===========================================================================
# The proxy compose declares
# ===========================================================================


def test_the_declared_proxy_exists_and_points_at_redis(toxiproxy):
    proxy = toxiproxy.describe()

    assert proxy["enabled"] is True
    assert proxy["upstream"].endswith(":6379")
    assert proxy["listen"].endswith(":6382")


@pytest.mark.asyncio
async def test_redis_is_reachable_through_the_proxy(toxiproxy):
    """Otherwise a partition run would be measuring a broken proxy."""
    client = Redis.from_url(PROXY_URL, decode_responses=True)
    try:
        assert await client.ping()
    finally:
        await client.aclose()


# ===========================================================================
# The partition
# ===========================================================================


@pytest.mark.asyncio
async def test_a_partition_black_holes_traffic_and_healing_restores_it(toxiproxy):
    """The whole cycle, because a partition that cannot be healed ends a run."""
    client = Redis.from_url(
        PROXY_URL, decode_responses=True, socket_timeout=2.0, socket_connect_timeout=2.0
    )
    try:
        assert await client.ping()

        toxiproxy.partition()
        assert [toxic["name"] for toxic in toxiproxy.toxics()] == [
            PARTITION_TOXIC_NAME
        ]

        # A black hole: the client is not told anything, it simply waits.
        started = time.monotonic()
        with pytest.raises(Exception):
            await asyncio.wait_for(client.ping(), timeout=4.0)
        assert time.monotonic() - started >= 1.0, (
            "the command failed immediately, so the connection was refused "
            "rather than black-holed; that is a different fault"
        )

        assert toxiproxy.heal() is True
        assert toxiproxy.toxics() == []

        # A fresh connection, because the old one is holding a dead request.
        await client.aclose()
        client = Redis.from_url(PROXY_URL, decode_responses=True, socket_timeout=5.0)
        assert await client.ping()
    finally:
        await client.aclose()


def test_healing_an_unpartitioned_proxy_is_not_an_error(toxiproxy):
    assert toxiproxy.heal() is False


def test_an_undeclared_proxy_is_refused_rather_than_created(toxiproxy):
    """A run must not silently proceed against a proxy nobody declared."""
    control = ToxiproxyControl(
        api_url="http://127.0.0.1:8474", proxy_name="no-such-proxy"
    )
    try:
        with pytest.raises(FaultInjectionError) as refused:
            control.describe()
    finally:
        control.close()

    assert "redis/toxiproxy.json" in str(refused.value)


# ===========================================================================
# The restart
# ===========================================================================


@pytest.mark.asyncio
async def test_a_restart_replays_the_appendonly_file(tmp_path, redis_client):
    """C3: AOF replay verified after each restart, by a probe not by INFO."""
    marker = "aep:harness:restart-witness"
    await redis_client.set(marker, "written before the restart", ex=3600)

    record = await restart_redis_and_verify_aof(
        config(tmp_path), redis_client=redis_client
    )

    assert record.probe_survived is True
    assert record.aof_enabled == 1
    assert record.loading == 0
    assert record.redis_version.startswith("7.2")
    # Independent of the probe: data written before the restart is still here.
    assert await redis_client.get(marker) == "written before the restart"
    await redis_client.unlink(marker)


@pytest.mark.asyncio
async def test_the_restart_record_is_json_ready_for_the_run_log(
    tmp_path, redis_client
):
    import json

    record = await restart_redis_and_verify_aof(
        config(tmp_path), redis_client=redis_client
    )

    json.dumps(record.echo())
    assert set(record.echo()) == {
        "probe_key",
        "probe_survived",
        "aof_enabled",
        "loading",
        "redis_version",
        "restart_duration_ms",
        "readiness_duration_ms",
    }
