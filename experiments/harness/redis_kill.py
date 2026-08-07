"""The hard Redis kill: ``docker kill -s KILL``, timed against the protocol.

Amendment E1. Session 3's ablation could not show the durability barrier's
*benefit*, only its cost, because the only infrastructure fault the matrix
scheduled was ``docker compose restart`` -- a SIGTERM, which Redis answers by
flushing its append-only buffer. This module is the fault that does not let it.

**What the kill is.** ``docker kill -s KILL <container>`` delivers SIGKILL to
the container's PID 1, which is ``redis-server``. No shutdown hook runs, no
buffer is flushed, no client is told. The container does *not* come back on its
own -- Docker's ``restart: unless-stopped`` policy deliberately does not apply
to a container an operator killed -- so :func:`start_redis` is explicit, and
:func:`kill_and_restart` is what a run calls.

**Why it is fired asynchronously.** Measured on this host, the ``docker`` CLI
costs 0.44-0.52 s before it does anything and 0.8-1.1 s round trip. Firing it
synchronously at a checkpoint would suspend the protocol for a second in the
middle of the step whose timing is under test, and -- much worse -- would
suspend it *equally for every system*, which would destroy the very difference
the ablation exists to measure. So the checkpoint arms a watchdog thread and
returns immediately. AEP-full then blocks in ``WAITAOF`` while the kill is in
flight and B3, which does not wait, does not. That asymmetry is the experiment.

**What this fault can and cannot show, measured rather than assumed.** A
premise worth stating because it was tested and came out the opposite way to
the naive expectation. ``appendfsync everysec`` defers the *fsync* by up to a
second; it does not defer the ``write(2)``, which Redis issues on every event
loop iteration. A SIGKILL therefore destroys the process and leaves the written
bytes in the *kernel's* page cache, where they survive to be flushed by the
kernel that is still running. In six phase-aligned trials on this host a write
made 0.5-0.8 s before a hard kill survived the kill **six times out of six**
(``reports/raw/e1-durability-window.txt``).

The consequence is precise and the paper must state it: **no process-level
fault can demonstrate what ``WAITAOF`` buys, because ``appendonly yes`` already
survives a process death without it.** ``WAITAOF`` defends against the loss of
the page cache -- host power loss, kernel panic, VM crash -- and only a fault of
that class can separate it from B3 on the *durability* of the record.

That leaves a second, independent mechanism by which the barrier changes
behaviour, and this fault does exercise it: AEP-full *waits* at a moment where
B3 does not. A Redis that dies inside that wait makes AEP-full's ``WAITAOF``
fail, and its ``DurabilityAck`` is never minted, so it refuses to dispatch. B3,
which never waits, has already dispatched. Both systems then hold the same
durable record; only one of them sent the mutation. Each run records which,
and :data:`RedisKillRecord.canary` records whether the tail was lost as well,
so the claim above is re-tested by every cell rather than assumed from a probe.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping

#: Environment variables, read once at worker start. Named like the crash
#: injector's, because they select the same kind of thing.
REDIS_KILL_POINT_VARIABLE = "AEP_HARNESS_REDIS_KILL_POINT"
REDIS_KILL_DELAY_VARIABLE = "AEP_HARNESS_REDIS_KILL_DELAY_MS"
REDIS_KILL_EXECUTIONS_VARIABLE = "AEP_HARNESS_REDIS_KILL_EXECUTIONS"
REDIS_KILL_CONTAINER_VARIABLE = "AEP_HARNESS_REDIS_KILL_CONTAINER"

#: Where the canary lives. One key per run: written by the worker immediately
#: before the kill is armed and *not* put through any barrier, so that whether
#: it survives is a direct measurement of whether the unfsynced tail was lost.
CANARY_PREFIX = "aep:harness:kill-canary:"


class CanaryOutcome(str, Enum):
    """What happened to the un-acknowledged write made just before the kill."""

    #: The tail was lost: the write did not survive. This is the outcome the
    #: naive durability model predicts and the one that has never been
    #: observed on this host.
    LOST = "LOST"
    #: The write survived the kill -- because ``write(2)`` had already put it in
    #: the kernel's page cache, which a process kill does not touch.
    SURVIVED = "SURVIVED"
    #: No canary was written, so nothing can be said.
    NOT_PROBED = "NOT_PROBED"


def kill_redis(container: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """SIGKILL the container's PID 1. Returns what happened, never raises.

    Never raises because this runs on a watchdog thread inside a worker that
    is executing protocol code: an exception here would be reported as a
    protocol failure. The record is returned and logged instead, and the
    runner's post-run verification is what fails a run whose kill did not land.
    """
    started = time.monotonic()
    try:
        completed = subprocess.run(
            ["docker", "kill", "-s", "KILL", container],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "issued": True,
            "returncode": completed.returncode,
            "stderr": completed.stderr.strip()[-500:],
            "command_ms": int((time.monotonic() - started) * 1000),
        }
    except Exception as error:  # noqa: BLE001 -- see docstring
        return {
            "issued": False,
            "error": f"{type(error).__name__}: {error}",
            "command_ms": int((time.monotonic() - started) * 1000),
        }


def start_redis(container: str, *, timeout: float = 60.0) -> dict[str, Any]:
    """Bring the container back. Explicit, because Docker will not.

    ``restart: unless-stopped`` does not restart a container that was killed
    through the API -- Docker treats that as an operator decision. Verified on
    this host: the container stayed down for the full 60 s the probe waited.
    """
    started = time.monotonic()
    completed = subprocess.run(
        ["docker", "start", container],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "returncode": completed.returncode,
        "stderr": completed.stderr.strip()[-500:],
        "start_ms": int((time.monotonic() - started) * 1000),
    }


@dataclass(frozen=True)
class RedisKillPlan:
    """What this process will do to Redis, decided before it does any work."""

    #: A member of the running system's crash-point vocabulary. Compared by
    #: identity, exactly as ``ProcessCrashInjector`` does, so the two
    #: vocabularies cannot be mixed.
    point: Enum
    container: str
    delay_seconds: float = 0.0
    #: ``None`` means every execution arms it; in practice the runner scopes it
    #: to one, because a second kill would land on a Redis that the first one
    #: is still restarting.
    executions: frozenset[str] | None = None
    roadmap_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.point, Enum):
            raise TypeError("a redis-kill plan requires a declared crash point")
        if self.delay_seconds < 0:
            raise ValueError("delay_seconds cannot be negative")
        if not self.container:
            raise ValueError("a redis-kill plan requires a container name")

    def echo(self) -> dict[str, Any]:
        return {
            "point": self.point.value,
            "roadmap_crash_point": self.roadmap_name,
            "container": self.container,
            "delay_seconds": self.delay_seconds,
            "scoped_executions": (
                sorted(self.executions) if self.executions is not None else None
            ),
        }


def _no_emit(event: str, **fields: Any) -> None:
    """Default sink. A fault with no record is a fault nobody can attribute."""


@dataclass
class RedisKillInjector:
    """Fires one hard Redis kill at a named checkpoint, asynchronously.

    Implements the same two-method surface ``aep_core`` calls on a crash
    injector, so it can be composed with :class:`ProcessCrashInjector` behind
    ``CompositeInjector`` and neither has to know the other exists.
    """

    plan: RedisKillPlan
    emit: Callable[..., None] = _no_emit
    #: Awaited with the canary key just before the kill is armed. Supplied by
    #: the worker, which is the only thing here holding a Redis connection.
    write_canary: Callable[[str], Any] | None = None
    killer: Callable[[str], dict[str, Any]] = kill_redis
    run_id: str = "unknown"
    _fired: bool = field(default=False, init=False)
    _execution_id: str | None = field(default=None, init=False)
    _watchdog: threading.Thread | None = field(default=None, init=False)

    @classmethod
    def from_environment(
        cls,
        *,
        environ: Mapping[str, str] | None = None,
        emit: Callable[..., None] = _no_emit,
        resolver: Callable[[str | None], Any],
        write_canary: Callable[[str], None] | None = None,
        run_id: str = "unknown",
        killer: Callable[[str], dict[str, Any]] = kill_redis,
    ) -> "RedisKillInjector | None":
        """Build an injector, or ``None`` when no Redis kill was selected."""
        source = os.environ if environ is None else environ
        declared = source.get(REDIS_KILL_POINT_VARIABLE)
        point = resolver(declared)
        if point is None:
            return None

        container = source.get(REDIS_KILL_CONTAINER_VARIABLE)
        if not container:
            raise ValueError(
                f"{REDIS_KILL_POINT_VARIABLE} is set but "
                f"{REDIS_KILL_CONTAINER_VARIABLE} is not; a kill with no target "
                "would be a silent no-op in a run whose log claimed a fault"
            )
        raw_delay = source.get(REDIS_KILL_DELAY_VARIABLE)
        delay = float(raw_delay) / 1000.0 if raw_delay else 0.0
        raw_executions = source.get(REDIS_KILL_EXECUTIONS_VARIABLE)
        executions = (
            frozenset(part for part in raw_executions.split(",") if part)
            if raw_executions
            else None
        )
        return cls(
            plan=RedisKillPlan(
                point=point,
                container=container,
                delay_seconds=delay,
                executions=executions,
                roadmap_name=declared,
            ),
            emit=emit,
            write_canary=write_canary,
            run_id=run_id,
            killer=killer,
        )

    # -- the protocol-facing surface ---------------------------------------

    def enter_execution(self, execution_id: str) -> None:
        self._execution_id = execution_id

    @property
    def armed_for_current_execution(self) -> bool:
        if self.plan.executions is None:
            return True
        return self._execution_id in self.plan.executions

    def canary_key(self) -> str:
        return f"{CANARY_PREFIX}{self.run_id}"

    async def checkpoint(self, point: Any) -> None:
        """Called by the protocol at every named instruction boundary."""
        if self._fired or point is not self.plan.point:
            return
        if not self.armed_for_current_execution:
            return
        self._fired = True

        canary = None
        if self.write_canary is not None:
            canary = self.canary_key()
            try:
                await self.write_canary(canary)
            except Exception as error:  # noqa: BLE001 -- evidence, not protocol
                self.emit(
                    "redis_kill_canary_failed",
                    error=f"{type(error).__name__}: {error}",
                )
                canary = None

        self.emit(
            "redis_kill_armed",
            execution_id=self._execution_id,
            canary_key=canary,
            **self.plan.echo(),
        )
        self._start_watchdog(self._execution_id)

    def _start_watchdog(self, execution_id: str | None) -> None:
        delay = self.plan.delay_seconds
        container = self.plan.container

        def deliver() -> None:
            # A plain sleep on a thread of its own: the event loop in this
            # process is the thing the kill is meant to interrupt, so the timer
            # must not live on it.
            if delay:
                threading.Event().wait(delay)
            armed_at = time.monotonic_ns()
            outcome = self.killer(container)
            self.emit(
                "redis_kill_issued",
                execution_id=execution_id,
                container=container,
                delay_seconds=delay,
                issue_to_return_ns=time.monotonic_ns() - armed_at,
                **outcome,
            )

        # Not a daemon: on the fake-killer path used by tests the process must
        # not exit while the watchdog is pending, or the test would observe
        # neither outcome.
        watchdog = threading.Thread(
            target=deliver, name="aep-harness-redis-kill", daemon=False
        )
        self._watchdog = watchdog
        watchdog.start()

    def join_watchdog(self, timeout: float | None = None) -> None:
        """Wait for the kill to have been issued. Tests, and worker teardown."""
        if self._watchdog is not None:
            self._watchdog.join(timeout)


@dataclass(frozen=True)
class RedisKillRecord:
    """What one kill-and-restart did, for the run log to carry verbatim."""

    container: str
    was_killed: bool
    #: ``uptime_in_seconds`` read after the restart. A small number is the
    #: evidence that the server really is a new process; a large one means the
    #: kill never landed and the run's fault did not happen.
    uptime_after_seconds: int
    start_ms: int
    readiness_ms: int
    aof_enabled: int
    loading: int
    redis_version: str
    canary: CanaryOutcome
    canary_key: str | None

    def echo(self) -> dict[str, Any]:
        return {
            "container": self.container,
            "was_killed": self.was_killed,
            "uptime_after_seconds": self.uptime_after_seconds,
            "start_ms": self.start_ms,
            "readiness_ms": self.readiness_ms,
            "aof_enabled": self.aof_enabled,
            "loading": self.loading,
            "redis_version": self.redis_version,
            "canary": self.canary.value,
            "canary_key": self.canary_key,
        }


def canary_payload(run_id: str) -> str:
    return json.dumps({"run_id": run_id, "purpose": "unfsynced-tail-probe"})
