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
fail, and its ``DurabilityAck`` is never issued, so it refuses to dispatch. B3,
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


#: Which fault a run delivers at the Redis kill point. Read from the process
#: environment rather than from ``RunConfig``, because ``RunConfig._body()``
#: iterates every dataclass field into ``config_digest`` and adding one would
#: change the digest of every run ever collected -- 150 of the 432 frozen matrix
#: runs already fail that check for exactly this reason
#: (``docs/31-transmission-event.md`` §4). The mechanism is instead recorded in
#: the ``environment`` block, which ``echo()`` writes and ``config_digest``
#: excludes, which is the same route Phase 8.2 used for
#: ``results_root_filesystem`` and Phase 10 for ``docker_kill_latency``.
REDIS_FAULT_MECHANISM_VARIABLE = "AEP_HARNESS_REDIS_FAULT_MECHANISM"

#: The mechanism the frozen cells used, and the default. Named explicitly so a
#: run that selected nothing is distinguishable from one that selected this.
MECHANISM_KILL = "kill"
#: Phase 13 Arm A. Freeze first, then kill.
MECHANISM_PAUSE_THEN_KILL = "pause-then-kill"

#: WS-4 / backlog B1. Not a kill at all: the device stops accepting writes while
#: Redis keeps running and keeps serving reads. Registered here so the existing
#: arming, watchdog and event machinery is reused rather than duplicated -- the
#: fault point, the delay and the scoped executions all keep the meaning they
#: already have, and only what happens at the checkpoint differs.
MECHANISM_WRITE_LOSS = "write-loss"

#: Phase 54. The device FAILS writes visibly (``error_writes``) and then Redis
#: is killed and restarted, so recovery reads an AOF that never received the
#: record. **Deliberately NOT in** :data:`NON_KILLING_MECHANISMS`: the restart
#: is the experiment, and a version of this that skipped it would collect the
#: WS-4 cell again under a new name.
#:
#: It is a separate mechanism rather than a flag on the existing one because
#: ``write-loss`` must keep behaving exactly as it did -- WS-4's collected cell
#: has to stay reproducible from this code.
#: ``prompts/phase-54-record-loss-restart-2026-09-24.md``.
MECHANISM_WRITE_LOSS_RESTART = "write-loss-restart"

#: The dm-flakey device the write-loss mechanism arms. Read from the environment
#: for the same reason the mechanism is: it must not enter ``config_digest``
#: (``docs/31-transmission-event.md`` section 4).
WRITE_LOSS_DEVICE_VARIABLE = "AEP_HARNESS_WRITE_LOSS_DEVICE"


def pause_then_kill(container: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """Freeze the container, then SIGKILL it. Same end state, narrower race.

    Phase 13 Arm A. ``docker kill`` alone lands 368.4 ms after it is issued
    (median, n=100, spread 134.6 ms), against a ``WAITAOF`` round trip of
    U(0, 1000) ms under ``appendfsync everysec`` -- so whether AEP-full's
    barrier returns before the fault arrives is a coin weighted by the
    injector, which is what ``08-threats.tex`` §A(e) concedes. ``docker pause``
    lands in **58.3 ms, spread 36.0 ms** (`docs/30-controlled-fault-mechanism.md`),
    cutting the residual race from 37% of that window to 5.8%.

    **The fault class does not change**, and that is why this mechanism was
    chosen over the faster ones. ``docker pause`` uses the cgroup-v2 freezer;
    the kill that follows delivers SIGKILL to PID 1 exactly as before, and the
    container ends in the same state -- verified: ``docker kill`` on a paused
    container exits 137 and auto-unpauses. An ``iptables`` drop lands in ~2 ms
    but is an F2 partition, and would answer a different question.

    **The race is narrowed, not closed, and it cannot be closed.** Freezing
    *synchronously at the checkpoint* would make ``WAITAOF`` unanswerable -- but
    B3 reaches the same checkpoint and still needs ``authorize_dispatch`` and
    ``preflight``, both Redis calls, so it would stop dispatching too and the
    contrast would vanish because the injector disabled both arms. The
    asymmetry this experiment measures *is* a timing difference.

    Returns the same shape as :func:`kill_redis`, with the pause's own timing
    added, so a run records what the fault cost as well as that it happened.
    """
    started = time.monotonic()
    paused: dict[str, Any]
    try:
        completed = subprocess.run(
            ["docker", "pause", container],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        paused = {
            "paused": completed.returncode == 0,
            "pause_returncode": completed.returncode,
            "pause_stderr": completed.stderr.strip()[-200:],
            "pause_ms": int((time.monotonic() - started) * 1000),
        }
    except Exception as error:  # noqa: BLE001 -- see kill_redis's docstring
        paused = {
            "paused": False,
            "pause_error": f"{type(error).__name__}: {error}",
            "pause_ms": int((time.monotonic() - started) * 1000),
        }

    # The kill is issued whether or not the pause succeeded. A run whose pause
    # failed is still a valid crash-fault run -- it is just the uncontrolled
    # one -- and `paused` records which it was, so the analysis can separate
    # them instead of the injector silently deciding not to inject.
    killed = kill_redis(container, timeout=timeout)
    return {
        **killed,
        **paused,
        "mechanism": MECHANISM_PAUSE_THEN_KILL,
        "total_ms": int((time.monotonic() - started) * 1000),
    }


#: The mechanisms that kill the Redis *server*.
#:
#: ``restart_after_hard_kill`` restarts the container and then verifies the
#: server actually died, via ``uptime_in_seconds``. That verification is only
#: meaningful for a fault that kills: under ``write-loss`` Redis keeps running
#: by design -- the device stops accepting writes while the server keeps serving
#: reads -- so the check can never pass and would refuse every run.
SERVER_KILLING_MECHANISMS = frozenset({MECHANISM_KILL, MECHANISM_PAUSE_THEN_KILL})

#: The mechanisms that do NOT kill the server. Membership of this set, rather
#: than absence from the set above, is what skips the restart -- so an unknown or
#: misspelled mechanism is treated as killing and the guard fires, instead of
#: silently skipping a verification that should have run.
NON_KILLING_MECHANISMS = frozenset({MECHANISM_WRITE_LOSS})


def mechanism_kills_server(mechanism: str | None = None) -> bool:
    """Does the configured fault kill the server?

    Read from the environment exactly as :func:`killer_for` reads it, and for
    the same reason: the mechanism lives in the environment so that no collected
    run's ``config_digest`` moves. A ``RunConfig`` field would change the digest
    of all 432 frozen matrix runs against ``docs/32``'s generation-aware check.

    Unknown mechanisms are treated as killing, which is the conservative
    direction: the guard fires, the run is refused, and the operator is told --
    rather than silently skipping a verification that should have run.
    """
    if mechanism is None:
        mechanism = os.environ.get(REDIS_FAULT_MECHANISM_VARIABLE)
    if mechanism in (None, ""):
        return True  # the default mechanism is MECHANISM_KILL
    return mechanism not in NON_KILLING_MECHANISMS


def killer_for(mechanism: str | None) -> Callable[[str], dict[str, Any]]:
    """Resolve the named mechanism, refusing anything unrecognised.

    Refusing rather than defaulting: a typo in the variable would otherwise
    deliver the uncontrolled fault into a root whose name says it is the
    controlled one, and the run log would not contradict it.
    """
    if mechanism in (None, "", MECHANISM_KILL):
        return kill_redis
    if mechanism == MECHANISM_PAUSE_THEN_KILL:
        return pause_then_kill
    if mechanism == MECHANISM_WRITE_LOSS:
        return drop_writes_on_device
    if mechanism == MECHANISM_WRITE_LOSS_RESTART:
        return error_writes_on_device
    raise ValueError(
        f"unknown {REDIS_FAULT_MECHANISM_VARIABLE}={mechanism!r}; expected "
        f"{MECHANISM_KILL!r}, {MECHANISM_PAUSE_THEN_KILL!r}, "
        f"{MECHANISM_WRITE_LOSS!r} or {MECHANISM_WRITE_LOSS_RESTART!r}"
    )


def drop_writes_on_device(container: str) -> dict[str, Any]:
    """WS-4's fault: stop the device accepting writes.

    The container is deliberately not touched -- that is the whole difference
    from the two kill mechanisms, and it is why B1 can separate "the record was
    destroyed" from "the server died".

    ``container`` is accepted and ignored so this matches the callable shape
    :func:`killer_for` returns. The device comes from the environment, because a
    run cannot know which dm-flakey mapping the session provisioned and because a
    ``RunConfig`` field would change every collected run's ``config_digest``.

    Returns the ``issued``/``command_ms`` shape the kill mechanisms return, plus
    both table lines, so the run log records what the device was before and after
    without a second code path. ``issued`` follows the table read back rather
    than the exit codes, so it is a delivery signal and not a hopeful one.
    """
    from experiments.harness import write_loss

    device = os.environ.get(WRITE_LOSS_DEVICE_VARIABLE, "").strip()
    if not device:
        return {
            "issued": False,
            "mechanism": MECHANISM_WRITE_LOSS,
            "error": f"{WRITE_LOSS_DEVICE_VARIABLE} is not set",
            "command_ms": 0,
        }

    # A run whose device is ALREADY dropping did not have its fault delivered
    # late -- its pre-fault portion ran under write loss too, which is a
    # different experiment from the one this regime declares. Refuse it rather
    # than arm an already-armed device and produce a run that completes and
    # looks like data.
    existing = write_loss.read_table(device)
    if write_loss.table_declares_drop(existing):
        return {
            "issued": False,
            "mechanism": MECHANISM_WRITE_LOSS,
            "device": device,
            "table_before": existing,
            "table_after": existing,
            "armed": True,
            "error": (
                "the device was already in drop_writes when this run reached the "
                "fault point, so the run's pre-fault portion also ran under write "
                "loss. Restore the device to pass mode between runs; a run that "
                "begins armed is not the experiment this regime declares."
            ),
            "command_ms": 0,
        }

    record = write_loss.arm_drop_writes(device)
    return {
        "issued": record.armed,
        "mechanism": MECHANISM_WRITE_LOSS,
        "device": record.device,
        "table_before": record.table_before,
        "table_after": record.table_after,
        "armed": record.armed,
        "error": record.error,
        "command_ms": record.arm_ms,
    }


def error_writes_on_device(container: str) -> dict[str, Any]:
    """Phase 54's fault: make the device FAIL writes, visibly.

    The same shape as :func:`drop_writes_on_device` and the same refusals, with
    one difference that is the entire point of the phase: ``error_writes``
    rather than ``drop_writes``, so the write fails with an I/O error instead
    of being discarded silently.

    Why that matters, from
    ``prompts/phase-54-record-loss-restart-2026-09-24.md`` §2: under
    ``drop_writes`` the barrier's ``WAITAOF`` *succeeds* on a lie, AEP-full
    dispatches, and the restart loses the record for both arms -- the cell
    separates nothing. Under ``error_writes`` the ``WAITAOF`` fails, AEP-full
    withholds dispatch, and B3 does not. That is the contrast between
    ``b3-no-barrier-restart.cfg`` and ``aof-rewind.cfg``.

    **The container is killed and restarted afterwards**, because this
    mechanism is not in :data:`NON_KILLING_MECHANISMS`. The device fault alone
    would leave the record in memory and reproduce WS-4.
    """
    from experiments.harness import write_loss

    device = os.environ.get(WRITE_LOSS_DEVICE_VARIABLE, "").strip()
    if not device:
        return {
            "issued": False,
            "mechanism": MECHANISM_WRITE_LOSS_RESTART,
            "error": f"{WRITE_LOSS_DEVICE_VARIABLE} is not set",
            "command_ms": 0,
        }

    # Same refusal as the WS-4 path: a run that begins already armed ran its
    # pre-fault portion under the fault too, which is a different experiment.
    existing = write_loss.read_table(device)
    if write_loss.table_declares_feature(existing, write_loss.ERROR_FEATURE) or (
        write_loss.table_declares_drop(existing)
    ):
        return {
            "issued": False,
            "mechanism": MECHANISM_WRITE_LOSS_RESTART,
            "device": device,
            "table_before": existing,
            "table_after": existing,
            "armed": True,
            "error": (
                "the device was already failing or dropping writes when this "
                "run reached the fault point, so the run's pre-fault portion "
                "also ran under the fault. Restore the device to pass mode "
                "between runs; a run that begins armed is not the experiment "
                "this regime declares."
            ),
            "command_ms": 0,
        }

    record = write_loss.arm_error_writes(device)
    return {
        "issued": record.armed,
        "mechanism": MECHANISM_WRITE_LOSS_RESTART,
        "device": record.device,
        "table_before": record.table_before,
        "table_after": record.table_after,
        "armed": record.armed,
        "error": record.error,
        "command_ms": record.arm_ms,
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
        # The mechanism, unless the caller supplied its own killer (tests do).
        if killer is kill_redis:
            killer = killer_for(source.get(REDIS_FAULT_MECHANISM_VARIABLE))
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
