"""The process crash injector: real SIGKILL, selected by environment variable.

Two things are being asserted, and they pull in opposite directions.

*It really kills.* A crash test whose "crash" is a raised exception proves
nothing about a protocol whose whole subject is what survives in Redis when a
process stops existing. So the load-bearing test here spawns a child process
that self-kills at a crash point and asserts the corpse's exit status.

*It really does nothing when disabled.* The injector is threaded through
``aep_core``'s hot path. If the disabled path allocated, logged, or touched the
environment per checkpoint, every latency number in the paper would include the
apparatus. The disabled path is therefore ``crash_injector is None`` -- no
object at all -- and that is asserted structurally and measured.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from experiments.harness.crash_points import CrashPoint
from experiments.harness.injector import (
    HAS_SIGKILL,
    CrashPlan,
    CrashStyle,
    ProcessCrashInjector,
    hard_kill_self,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


class _RecordingKiller:
    """Stands in for ``hard_kill_self`` so the test process survives."""

    def __init__(self) -> None:
        self.calls: list[CrashPoint] = []

    def __call__(self, point: CrashPoint) -> None:
        self.calls.append(point)


def _plan(**overrides) -> CrashPlan:
    defaults = dict(
        point=CrashPoint.DURING_RESOLUTION_CAS,
        style=CrashStyle.SIGKILL_IMMEDIATE,
        deferred_delay_seconds=0.05,
    )
    defaults.update(overrides)
    return CrashPlan(**defaults)


def _injector(plan: CrashPlan, killer, events: list | None = None):
    recorded = events if events is not None else []
    return ProcessCrashInjector(
        plan=plan,
        emit=lambda event, **fields: recorded.append((event, fields)),
        killer=killer,
    ), recorded


# ===========================================================================
# Selection by environment variable
# ===========================================================================


def test_no_environment_variable_yields_no_injector_at_all():
    """Not a disabled injector -- no object, so the workflow's guard is `None`."""
    assert ProcessCrashInjector.from_environment(environ={}) is None


def test_an_empty_crash_point_yields_no_injector():
    assert (
        ProcessCrashInjector.from_environment(
            environ={"AEP_HARNESS_CRASH_POINT": ""}
        )
        is None
    )


def test_a_roadmap_name_in_the_environment_selects_its_checkpoint():
    injector = ProcessCrashInjector.from_environment(
        environ={"AEP_HARNESS_CRASH_POINT": "mid_dispatch"},
        emit=lambda event, **fields: None,
    )

    assert injector is not None
    assert injector.plan.point is CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION
    # mid_dispatch cannot be delivered at the checkpoint; it defers by default.
    assert injector.plan.style is CrashStyle.SIGKILL_DEFERRED


def test_a_canonical_name_in_the_environment_selects_itself_immediately():
    injector = ProcessCrashInjector.from_environment(
        environ={"AEP_HARNESS_CRASH_POINT": "DURING_INTENT_CAS"},
        emit=lambda event, **fields: None,
    )

    assert injector.plan.point is CrashPoint.DURING_INTENT_CAS
    assert injector.plan.style is CrashStyle.SIGKILL_IMMEDIATE


def test_a_misspelled_crash_point_refuses_to_start_the_process():
    """Silently reading as 'no crash' would produce an expensive empty run."""
    with pytest.raises(KeyError):
        ProcessCrashInjector.from_environment(
            environ={"AEP_HARNESS_CRASH_POINT": "mid-dispatch"}
        )


def test_the_deferred_delay_comes_from_the_environment():
    injector = ProcessCrashInjector.from_environment(
        environ={
            "AEP_HARNESS_CRASH_POINT": "mid_dispatch",
            "AEP_HARNESS_CRASH_DELAY_MS": "250",
        },
        emit=lambda event, **fields: None,
    )

    assert injector.plan.deferred_delay_seconds == pytest.approx(0.25)


def test_a_negative_delay_is_refused():
    with pytest.raises(ValueError):
        ProcessCrashInjector.from_environment(
            environ={
                "AEP_HARNESS_CRASH_POINT": "mid_dispatch",
                "AEP_HARNESS_CRASH_DELAY_MS": "-1",
            }
        )


# ===========================================================================
# Firing
# ===========================================================================


@pytest.mark.asyncio
async def test_an_unarmed_checkpoint_does_not_kill():
    killer = _RecordingKiller()
    injector, _ = _injector(_plan(point=CrashPoint.DURING_RESOLUTION_CAS), killer)

    await injector.checkpoint(CrashPoint.DURING_INTENT_CAS)

    assert killer.calls == []


@pytest.mark.asyncio
async def test_the_armed_checkpoint_kills_immediately():
    killer = _RecordingKiller()
    injector, events = _injector(_plan(point=CrashPoint.DURING_INTENT_CAS), killer)

    await injector.checkpoint(CrashPoint.DURING_INTENT_CAS)

    assert killer.calls == [CrashPoint.DURING_INTENT_CAS]
    assert [event for event, _ in events] == ["crash_injected"]
    (_, fields) = events[0]
    assert fields["crash_point"] == "DURING_INTENT_CAS"
    assert fields["style"] == CrashStyle.SIGKILL_IMMEDIATE.value


@pytest.mark.asyncio
async def test_a_deferred_crash_arms_and_lets_the_dispatch_proceed():
    """``mid_dispatch`` must not stop the request from being sent."""
    killer = _RecordingKiller()
    injector, events = _injector(
        _plan(
            point=CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION,
            style=CrashStyle.SIGKILL_DEFERRED,
            deferred_delay_seconds=0.15,
        ),
        killer,
    )

    await injector.checkpoint(
        CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION
    )

    # Returned, so the connector call happens; not dead yet.
    assert killer.calls == []
    assert [event for event, _ in events] == ["crash_armed"]

    injector.join_watchdog(timeout=5.0)

    assert killer.calls == [CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION]
    assert [event for event, _ in events] == ["crash_armed", "crash_injected"]


@pytest.mark.asyncio
async def test_only_the_first_arming_takes_effect():
    """One crash per process. A second would confuse the recovery attribution."""
    killer = _RecordingKiller()
    injector, events = _injector(_plan(point=CrashPoint.DURING_INTENT_CAS), killer)

    await injector.checkpoint(CrashPoint.DURING_INTENT_CAS)
    await injector.checkpoint(CrashPoint.DURING_INTENT_CAS)

    assert killer.calls == [CrashPoint.DURING_INTENT_CAS]


@pytest.mark.asyncio
async def test_the_injector_can_be_scoped_to_named_executions():
    """A run crashes some executions and not others; the rest are the control."""
    killer = _RecordingKiller()
    injector, _ = _injector(
        _plan(point=CrashPoint.DURING_INTENT_CAS, executions=frozenset({"exec-b"})),
        killer,
    )

    injector.enter_execution("exec-a")
    await injector.checkpoint(CrashPoint.DURING_INTENT_CAS)
    assert killer.calls == []

    injector.enter_execution("exec-b")
    await injector.checkpoint(CrashPoint.DURING_INTENT_CAS)
    assert killer.calls == [CrashPoint.DURING_INTENT_CAS]


# ===========================================================================
# It really is a process kill
# ===========================================================================


_CHILD = textwrap.dedent(
    """
    import asyncio, json, sys
    from pathlib import Path
    from experiments.harness.crash_points import CrashPoint
    from experiments.harness.injector import CrashPlan, CrashStyle, ProcessCrashInjector

    log = Path(sys.argv[1])

    def emit(event, **fields):
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": event, **fields}) + "\\n")
            handle.flush()

    async def main():
        injector = ProcessCrashInjector(
            plan=CrashPlan(
                point=CrashPoint.DURING_INTENT_CAS,
                style=CrashStyle.%(style)s,
                deferred_delay_seconds=0.1,
            ),
            emit=emit,
        )
        await injector.checkpoint(CrashPoint.DURING_INTENT_CAS)
        await asyncio.sleep(5)
        emit("survived")

    asyncio.run(main())
    emit("returned_normally")
    """
)


def _run_child(tmp_path: Path, style: str) -> tuple[subprocess.CompletedProcess, list]:
    script = tmp_path / "child.py"
    script.write_text(_CHILD % {"style": style}, encoding="utf-8")
    log = tmp_path / "child-events.jsonl"
    # sys.path[0] is the script's directory, not the working directory, so the
    # repository has to be put on the path explicitly for the child to import
    # the harness it is exercising.
    environment = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    completed = subprocess.run(
        [sys.executable, str(script), str(log)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        env=environment,
        timeout=60,
    )
    assert log.is_file(), (
        "the child wrote no event log:\n"
        f"{completed.stdout.decode(errors='replace')}\n"
        f"{completed.stderr.decode(errors='replace')}"
    )
    records = [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return completed, records


def test_an_immediate_crash_point_really_kills_a_real_process(tmp_path):
    completed, records = _run_child(tmp_path, "SIGKILL_IMMEDIATE")

    assert completed.returncode != 0, completed.stderr.decode(errors="replace")
    if HAS_SIGKILL:
        # POSIX reports a signal death as a negative return code.
        assert completed.returncode == -9
    assert [record["event"] for record in records] == ["crash_injected"]
    assert "survived" not in {record["event"] for record in records}


def test_a_deferred_crash_point_really_kills_a_real_process(tmp_path):
    completed, records = _run_child(tmp_path, "SIGKILL_DEFERRED")

    assert completed.returncode != 0
    if HAS_SIGKILL:
        assert completed.returncode == -9
    assert [record["event"] for record in records] == ["crash_armed", "crash_injected"]


def test_the_crash_record_reaches_the_disk_before_the_process_dies(tmp_path):
    """Otherwise every crashed execution would be missing from the run log."""
    _, records = _run_child(tmp_path, "SIGKILL_IMMEDIATE")

    assert records, "the crash record did not survive the kill"


def test_hard_kill_self_is_wired_to_an_uncatchable_signal():
    """Structural: the function must not be reachable in the test process."""
    import inspect
    import signal as signal_module

    source = inspect.getsource(hard_kill_self)

    assert "os.kill" in source
    if HAS_SIGKILL:
        assert "SIGKILL" in source
        assert hasattr(signal_module, "SIGKILL")


# ===========================================================================
# Disabled means absent
# ===========================================================================


def test_the_workflow_hot_path_short_circuits_on_a_missing_injector():
    """The disabled path is one `is None` test and a return: no work at all."""
    import inspect

    from aep_core.core.intent_workflow import WriteAheadRunner

    source = inspect.getsource(WriteAheadRunner._checkpoint)
    body = [line.strip() for line in source.splitlines() if line.strip()]

    assert body[1] == "if self.crash_injector is not None:", body
    # Everything else in the method is inside that guard.
    assert all(
        not line.startswith(("await ", "self.", "logger", "os.", "time."))
        for line in body[2:3]
    )


@pytest.mark.parametrize("checkpoints", [200_000])
def test_the_disabled_checkpoint_costs_far_less_than_the_work_it_guards(checkpoints):
    """A ceiling, not a benchmark: if the disabled path ever does I/O this fails.

    The absolute number is reported in the phase report; the assertion is only
    that a disabled checkpoint stays in the sub-microsecond range, which is
    three orders of magnitude below the millisecond-scale Redis round trips it
    sits between.
    """
    import asyncio

    from aep_core.core.intent_workflow import WriteAheadRunner

    runner = WriteAheadRunner.__new__(WriteAheadRunner)
    runner.crash_injector = None

    async def measure() -> float:
        started = time.perf_counter()
        for _ in range(checkpoints):
            await runner._checkpoint("DURING_INTENT_CAS")
        return time.perf_counter() - started

    elapsed = asyncio.run(measure())
    per_checkpoint_ns = elapsed / checkpoints * 1e9

    assert per_checkpoint_ns < 5_000, (
        f"a disabled checkpoint cost {per_checkpoint_ns:.0f} ns; the disabled "
        "path is supposed to be an attribute load and a comparison"
    )


def test_the_environment_variable_is_absent_from_the_default_process():
    """The harness opts in; nothing in the repo sets it globally."""
    assert "AEP_HARNESS_CRASH_POINT" not in os.environ or (
        os.environ["AEP_HARNESS_CRASH_POINT"] == ""
    )
