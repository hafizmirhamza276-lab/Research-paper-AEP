"""The hard-Redis-kill injector, without killing anything.

Amendment E1. Everything here is about *arming*: which checkpoint fires the
kill, that it fires once, that it is scoped to the execution the runner chose,
and that it does not block the protocol while the ``docker`` CLI takes its
half-second. The kill itself is exercised by
``experiments/redis_durability_window.py`` against a real container, because a
test that killed a real Redis would take the suite's own Redis with it.
"""

from __future__ import annotations

import threading
import time

import pytest

from experiments.harness.crash_points import CrashPoint
from experiments.harness.injector import CompositeInjector, compose_injectors
from experiments.harness.redis_kill import (
    REDIS_KILL_CONTAINER_VARIABLE,
    REDIS_KILL_DELAY_VARIABLE,
    REDIS_KILL_EXECUTIONS_VARIABLE,
    REDIS_KILL_POINT_VARIABLE,
    RedisKillInjector,
    RedisKillPlan,
)


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []
        self.killed: list[str] = []
        self.canaries: list[str] = []
        self.lock = threading.Lock()

    def emit(self, event: str, **fields) -> None:
        with self.lock:
            self.events.append((event, fields))

    def kill(self, container: str) -> dict:
        with self.lock:
            self.killed.append(container)
        return {"issued": True, "returncode": 0, "command_ms": 1}

    async def canary(self, key: str) -> None:
        self.canaries.append(key)

    def named(self, event: str) -> list[dict]:
        return [fields for name, fields in self.events if name == event]


def _injector(recorder: Recorder, **overrides) -> RedisKillInjector:
    plan_fields = {
        "point": CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER,
        "container": "test-redis",
        "delay_seconds": 0.0,
        "executions": None,
        "roadmap_name": "after_intent_before_barrier",
    }
    plan_fields.update(overrides)
    return RedisKillInjector(
        plan=RedisKillPlan(**plan_fields),
        emit=recorder.emit,
        write_canary=recorder.canary,
        killer=recorder.kill,
        run_id="run-1",
    )


@pytest.mark.asyncio
async def test_it_fires_at_its_own_checkpoint_and_no_other() -> None:
    recorder = Recorder()
    injector = _injector(recorder)
    injector.enter_execution("e1")

    await injector.checkpoint(CrashPoint.BEFORE_LEASE_ACQUISITION)
    await injector.checkpoint(CrashPoint.DURING_INTENT_CAS)
    assert recorder.killed == []

    await injector.checkpoint(CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER)
    injector.join_watchdog(timeout=5)
    assert recorder.killed == ["test-redis"]


@pytest.mark.asyncio
async def test_it_fires_exactly_once() -> None:
    """A second kill would land on a Redis the first one is still restarting."""
    recorder = Recorder()
    injector = _injector(recorder)
    injector.enter_execution("e1")
    for _ in range(3):
        await injector.checkpoint(
            CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER
        )
    injector.join_watchdog(timeout=5)
    assert recorder.killed == ["test-redis"]


@pytest.mark.asyncio
async def test_it_is_scoped_to_the_runner_s_chosen_executions() -> None:
    recorder = Recorder()
    injector = _injector(recorder, executions=frozenset({"e2"}))

    injector.enter_execution("e1")
    await injector.checkpoint(CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER)
    assert recorder.killed == []

    injector.enter_execution("e2")
    await injector.checkpoint(CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER)
    injector.join_watchdog(timeout=5)
    assert recorder.killed == ["test-redis"]


@pytest.mark.asyncio
async def test_the_checkpoint_returns_before_the_kill_is_issued() -> None:
    """The load-bearing property of the whole ablation.

    The ``docker`` CLI costs half a second before it does anything. A
    synchronous kill would suspend the protocol for that half-second *equally
    for every system*, which would erase the difference the ablation exists to
    measure: that AEP-full waits in ``WAITAOF`` at this checkpoint and B3 does
    not. So the checkpoint must return immediately and the kill must land on
    whichever system is still standing there.
    """
    started = threading.Event()
    release = threading.Event()

    def slow_kill(container: str) -> dict:
        started.set()
        release.wait(5)
        return {"issued": True, "returncode": 0, "command_ms": 500}

    recorder = Recorder()
    injector = _injector(recorder)
    injector.killer = slow_kill
    injector.enter_execution("e1")

    at = time.monotonic()
    await injector.checkpoint(CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER)
    returned_in = time.monotonic() - at

    assert started.wait(5), "the kill was never started"
    assert returned_in < 0.5, (
        f"checkpoint blocked for {returned_in:.3f}s; a synchronous kill would "
        "delay every system equally and destroy the ablation"
    )
    release.set()
    injector.join_watchdog(timeout=5)


@pytest.mark.asyncio
async def test_the_canary_is_written_before_the_kill_is_armed() -> None:
    """The evidence for what the kill did to the un-acknowledged tail."""
    recorder = Recorder()
    injector = _injector(recorder)
    injector.enter_execution("e1")
    await injector.checkpoint(CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER)
    injector.join_watchdog(timeout=5)

    assert recorder.canaries == ["aep:harness:kill-canary:run-1"]
    armed = recorder.named("redis_kill_armed")
    assert len(armed) == 1
    assert armed[0]["canary_key"] == "aep:harness:kill-canary:run-1"


def test_absent_means_absent() -> None:
    """No environment selection builds no injector, not a disabled one."""
    assert (
        RedisKillInjector.from_environment(environ={}, resolver=lambda name: None)
        is None
    )


def test_a_kill_with_no_target_is_refused() -> None:
    """A fault the log claims and never injects is worse than no fault."""
    with pytest.raises(ValueError, match=REDIS_KILL_CONTAINER_VARIABLE):
        RedisKillInjector.from_environment(
            environ={
                REDIS_KILL_POINT_VARIABLE: "after_intent_before_barrier",
                REDIS_KILL_EXECUTIONS_VARIABLE: "e1",
            },
            resolver=lambda name: (
                CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER
                if name
                else None
            ),
        )


def test_it_reads_its_whole_plan_from_the_environment() -> None:
    injector = RedisKillInjector.from_environment(
        environ={
            REDIS_KILL_POINT_VARIABLE: "mid_dispatch",
            REDIS_KILL_DELAY_VARIABLE: "200",
            REDIS_KILL_EXECUTIONS_VARIABLE: "e1,e2",
            REDIS_KILL_CONTAINER_VARIABLE: "aep-phase2-redis72",
        },
        resolver=lambda name: CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION,
    )
    assert injector is not None
    assert injector.plan.delay_seconds == pytest.approx(0.2)
    assert injector.plan.executions == frozenset({"e1", "e2"})
    assert injector.plan.container == "aep-phase2-redis72"
    assert injector.plan.roadmap_name == "mid_dispatch"


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


class Spy:
    def __init__(self) -> None:
        self.entered: list[str] = []
        self.points: list[object] = []
        self.plan = type("P", (), {"echo": staticmethod(lambda: {"spy": True})})()

    def enter_execution(self, execution_id: str) -> None:
        self.entered.append(execution_id)

    async def checkpoint(self, point) -> None:
        self.points.append(point)


def test_composing_nothing_gives_the_disabled_path() -> None:
    """``None`` is the disabled path the protocol tests for; keep it reachable."""
    assert compose_injectors(None, None) is None


def test_composing_one_does_not_wrap_it() -> None:
    spy = Spy()
    assert compose_injectors(None, spy) is spy


@pytest.mark.asyncio
async def test_composing_two_fans_out_in_order() -> None:
    first, second = Spy(), Spy()
    composite = compose_injectors(first, second)
    assert isinstance(composite, CompositeInjector)

    composite.enter_execution("e1")
    await composite.checkpoint(CrashPoint.DURING_INTENT_CAS)

    assert first.entered == second.entered == ["e1"]
    assert first.points == second.points == [CrashPoint.DURING_INTENT_CAS]


def test_a_composite_of_none_is_refused() -> None:
    with pytest.raises(ValueError, match="disabled path"):
        CompositeInjector(())
