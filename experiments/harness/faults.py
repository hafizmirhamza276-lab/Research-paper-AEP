"""Infrastructure faults: Redis restart with AOF replay, and network partition.

PAPER_ROADMAP.md 3.1(2) and amendment C3. Two faults live here because neither
is delivered by killing a worker.

**Redis restart.** ``docker compose restart``, then *verified* AOF replay.
"Verified" means something specific and falsifiable: a probe key is written and
put through the same ``WAITAOF`` barrier the protocol uses, the container is
restarted, and the key is read back. If the appendonly file did not replay, the
key is gone and :func:`restart_redis_and_verify_aof` raises rather than letting
a run continue collecting numbers against a Redis that silently lost its
history. ``aof_enabled`` and ``loading`` from ``INFO persistence`` are checked
too, but the probe is the load-bearing one -- those two fields would both look
healthy on a server that came back empty.

**Worker-to-Redis partition.** A ``timeout`` toxic with ``timeout: 0`` on the
upstream stream, which is toxiproxy's black hole: data stops flowing and the
connection is *not* closed. That is the interesting partition. A closed
connection tells the client something happened; a black hole leaves it waiting
while its lease expires, which is the case where the protocol has to be right
without being told anything.

Neither fault is available to a worker. Both are the runner's, and both are
recorded in the run log with the evidence that they took effect.
"""

from __future__ import annotations

import asyncio
import secrets
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from aep_core.core.durability import RealWaitAofDurabilityBarrier

from experiments.harness.redis_kill import (
    CanaryOutcome,
    RedisKillRecord,
    start_redis,
)

#: The toxic the harness installs. Named so it can be removed precisely rather
#: than by resetting every toxic the proxy happens to have.
PARTITION_TOXIC_NAME = "aep-harness-partition"

_PROBE_PREFIX = "aep:harness:aof-probe:"


class FaultInjectionError(RuntimeError):
    """A fault could not be injected, or could not be shown to have landed."""


# ===========================================================================
# Redis restart
# ===========================================================================


@dataclass(frozen=True)
class RedisRestartRecord:
    """What one restart did, in a form the run log can carry verbatim."""

    probe_key: str
    probe_survived: bool
    aof_enabled: int
    loading: int
    redis_version: str
    restart_duration_ms: int
    readiness_duration_ms: int

    def echo(self) -> dict[str, Any]:
        return {
            "probe_key": self.probe_key,
            "probe_survived": self.probe_survived,
            "aof_enabled": self.aof_enabled,
            "loading": self.loading,
            "redis_version": self.redis_version,
            "restart_duration_ms": self.restart_duration_ms,
            "readiness_duration_ms": self.readiness_duration_ms,
        }


async def _wait_until_ready(redis_client, *, timeout: float) -> int:
    """PING until the server answers, and report how long that took."""
    started = time.monotonic()
    last_error: Exception | None = None
    while time.monotonic() - started < timeout:
        try:
            if await redis_client.ping():
                return int((time.monotonic() - started) * 1000)
        except Exception as error:  # noqa: BLE001 -- the server is restarting
            last_error = error
        await asyncio.sleep(0.05)
    raise FaultInjectionError(
        f"Redis did not answer within {timeout}s after restart: {last_error!r}"
    )


async def restart_redis_and_verify_aof(
    config, *, redis_client, timeout: float = 60.0
) -> RedisRestartRecord:
    """Restart Redis from compose and prove the AOF replayed.

    Raises rather than returning a negative result: a run that continued after
    an unverified restart would be collecting evidence about a system whose
    durability substrate had silently reset.
    """
    probe_key = f"{_PROBE_PREFIX}{config.run_id}:{secrets.token_hex(8)}"
    probe_value = secrets.token_hex(16)

    barrier = RealWaitAofDurabilityBarrier()
    await barrier.validate_startup(redis_client)
    async with redis_client.client() as connection:
        await connection.set(probe_key, probe_value, ex=3600)
        durable = await barrier.confirm_durable(
            connection, config.durability_timeout_ms
        )
    if not durable:
        raise FaultInjectionError(
            "the AOF probe was not acknowledged durable before the restart, so "
            "its absence afterwards would prove nothing"
        )

    started = time.monotonic()
    completed = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            config.compose_file,
            "restart",
            config.redis_service,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    restart_ms = int((time.monotonic() - started) * 1000)
    if completed.returncode != 0:
        raise FaultInjectionError(
            f"docker compose restart failed: {completed.stderr.strip()}"
        )

    readiness_ms = await _wait_until_ready(redis_client, timeout=timeout)

    persistence = await redis_client.info("persistence")
    server = await redis_client.info("server")
    survived = await redis_client.get(probe_key) == probe_value
    await redis_client.unlink(probe_key)

    record = RedisRestartRecord(
        probe_key=probe_key,
        probe_survived=bool(survived),
        aof_enabled=int(persistence.get("aof_enabled", 0)),
        loading=int(persistence.get("loading", 1)),
        redis_version=str(server.get("redis_version", "unknown")),
        restart_duration_ms=restart_ms,
        readiness_duration_ms=readiness_ms,
    )
    if not record.probe_survived:
        raise FaultInjectionError(
            f"the AOF did not replay: probe key {probe_key} is absent after the "
            "restart, so everything written before it is gone too"
        )
    if record.aof_enabled != 1:
        raise FaultInjectionError(
            "Redis came back with AOF disabled; every durability claim "
            "collected after this point would be worthless"
        )
    if record.loading != 0:
        raise FaultInjectionError("Redis is still loading its dataset")
    return record


# ===========================================================================
# Hard kill (amendment E1)
# ===========================================================================


async def restart_after_hard_kill(
    config, *, redis_client, canary_key: str | None, timeout: float = 90.0
) -> RedisKillRecord:
    """Bring Redis back after a worker hard-killed it, and record what is true.

    Unlike :func:`restart_redis_and_verify_aof` this does **not** raise when
    something was lost. Losing the un-acknowledged tail is the outcome under
    measurement, not a harness failure, and a function that raised on it would
    turn the finding into an exception. What it does refuse is a run in which
    the kill never landed: ``uptime_in_seconds`` after the restart is read, and
    a server that has been up for longer than this run has existed is one that
    was never killed, which means the cell's fault did not happen and its
    numbers describe a different experiment.
    """
    started = time.monotonic()
    start_outcome = start_redis(config.redis_container, timeout=timeout)
    if start_outcome["returncode"] != 0:
        raise FaultInjectionError(
            f"docker start failed after the hard kill: {start_outcome['stderr']}"
        )
    readiness_ms = await _wait_until_ready(redis_client, timeout=timeout)

    persistence = await redis_client.info("persistence")
    server = await redis_client.info("server")
    uptime = int(server.get("uptime_in_seconds", 10**9))

    canary_outcome = CanaryOutcome.NOT_PROBED
    if canary_key:
        survived = await redis_client.get(canary_key)
        canary_outcome = (
            CanaryOutcome.SURVIVED if survived is not None else CanaryOutcome.LOST
        )
        await redis_client.unlink(canary_key)

    record = RedisKillRecord(
        container=config.redis_container,
        # A server that has been up longer than the whole restart took cannot
        # be the one this run killed.
        was_killed=uptime <= max(30, int(time.monotonic() - started) + 10),
        uptime_after_seconds=uptime,
        start_ms=int(start_outcome["start_ms"]),
        readiness_ms=readiness_ms,
        aof_enabled=int(persistence.get("aof_enabled", 0)),
        loading=int(persistence.get("loading", 1)),
        redis_version=str(server.get("redis_version", "unknown")),
        canary=canary_outcome,
        canary_key=canary_key,
    )
    if not record.was_killed:
        raise FaultInjectionError(
            "the hard kill did not land: Redis reports "
            f"uptime_in_seconds={uptime}, so it is the same server process the "
            "run started with and no infrastructure fault was injected"
        )
    if record.aof_enabled != 1:
        raise FaultInjectionError(
            "Redis came back with AOF disabled; every durability claim "
            "collected after this point would be worthless"
        )
    return record


# ===========================================================================
# Worker-to-Redis partition
# ===========================================================================


@dataclass
class ToxiproxyControl:
    """The toxiproxy HTTP control API, scoped to one declared proxy."""

    api_url: str
    proxy_name: str
    timeout: float = 5.0
    _client: httpx.Client | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.api_url = self.api_url.rstrip("/")

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "ToxiproxyControl":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # -- reading -----------------------------------------------------------

    def describe(self) -> dict[str, Any]:
        """The declared proxy. Raises if compose never created it."""
        response = self.client.get(f"{self.api_url}/proxies/{self.proxy_name}")
        if response.status_code == 404:
            raise FaultInjectionError(
                f"toxiproxy has no proxy named {self.proxy_name!r}; it is "
                "declared in redis/toxiproxy.json and created at container "
                "start, so this means the container is not the one compose "
                "defines"
            )
        response.raise_for_status()
        return response.json()

    def is_reachable(self) -> bool:
        try:
            self.client.get(f"{self.api_url}/version")
        except httpx.HTTPError:
            return False
        return True

    def toxics(self) -> list[dict[str, Any]]:
        response = self.client.get(
            f"{self.api_url}/proxies/{self.proxy_name}/toxics"
        )
        response.raise_for_status()
        return response.json()

    # -- faulting ----------------------------------------------------------

    def partition(self) -> dict[str, Any]:
        """Black-hole everything a worker sends to Redis.

        ``timeout: 0`` is toxiproxy's "stop the data and hold the connection
        open" -- the client is not told anything, which is the case the lease
        exists for.
        """
        response = self.client.post(
            f"{self.api_url}/proxies/{self.proxy_name}/toxics",
            json={
                "name": PARTITION_TOXIC_NAME,
                "type": "timeout",
                "stream": "upstream",
                "toxicity": 1.0,
                "attributes": {"timeout": 0},
            },
        )
        if response.status_code >= 400:
            raise FaultInjectionError(
                f"could not install the partition toxic: {response.text}"
            )
        return response.json()

    def heal(self) -> bool:
        """Remove the partition. Returns whether one was installed."""
        response = self.client.delete(
            f"{self.api_url}/proxies/{self.proxy_name}/toxics/"
            f"{PARTITION_TOXIC_NAME}"
        )
        if response.status_code == 404:
            return False
        if response.status_code >= 400:
            raise FaultInjectionError(
                f"could not remove the partition toxic: {response.text}"
            )
        return True
