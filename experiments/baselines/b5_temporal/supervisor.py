"""Keep a live B5 worker on the task queue across the injected kill.

**Why this is needed, and why it was missed for four rounds.** Temporal schedules
the activity retry onto a task queue; a retry needs a *worker polling that queue*
to run on. WS-6's probe started one worker, the injector killed it, and nothing
brought one back -- so across Start-To-Close timeouts of 2.5 s, 4 s and 8 s every
run sat at the deadline with **zero provider calls**, and none of the three
timeouts was ever exercised. **No B5 cell can measure a duplicate without this**,
because a duplicate is by definition what the second attempt does.

**The shape is B4's, deliberately.** Read from
``experiments/harness/runner.py:201`` ``run_worker_slot`` -- *"Run one worker slot
to completion, respawning it after each crash."* Its properties, and which are
carried over:

* **A bounded attempt loop.** B4 uses ``MAX_ATTEMPTS_PER_WORKER = 64``
  (``runner.py:97``) and raises ``RunAborted`` on exhaustion rather than looping
  forever. Carried: :data:`MAX_LIFETIMES`, and exhaustion is a void, not a
  result.
* **The fault is armed on attempt 1 only.** ``runner.py:244`` -- *"The kill fires
  once per run. A respawned worker must not carry it, or a system whose
  supervisor re-executes would kill Redis once per lifetime while a system that
  does not would kill it once."* **Carried, and it is the reason to copy the
  shape rather than invent one**: a B5 that re-armed on every lifetime would
  produce duplicates by a different mechanism than B4, which is precisely the
  confound this baseline exists to avoid.
* **Each lifetime is recorded**, spawn and exit, with its attempt number
  (``worker_spawned`` / ``worker_exited``). Carried, as
  ``b5_worker_spawned`` / ``b5_worker_exited`` on the same trace the gate reads.

**What is deliberately NOT carried.** B4's supervisor computes ``from_index`` and
tells the respawned worker where to resume, because B4's harness owns the resume
policy. **B5 must not**: deciding what to re-execute is the engine's job, and
that decision is the thing under measurement. The B5 supervisor only guarantees
that a worker exists; Temporal decides what it runs.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent

#: Bound on worker lifetimes per run, mirroring ``MAX_ATTEMPTS_PER_WORKER``.
#: Small here because a B5 run injects one fault: attempt 1 dies, attempt 2
#: carries the retry, and anything beyond that is a worker dying for a reason
#: nobody asked for -- which must end the run rather than be absorbed.
MAX_LIFETIMES = 6


@dataclass
class SupervisorState:
    spawns: int = 0
    deaths: int = 0
    respawns: int = 0
    exhausted: bool = False
    lifetimes: list[dict] = field(default_factory=list)


class WorkerSupervisor:
    """Spawn a worker; when it dies, bring another one back.

    ``respawn_enabled=False`` reproduces the pre-supervisor behaviour exactly,
    and exists so the gate's failing branch can be exercised on the real stack
    (rule 13). It is not a configuration anyone should collect under.
    """

    def __init__(
        self,
        *,
        out: Path,
        crash_point: str | None,
        provider_url: str,
        respawn_enabled: bool = True,
        injector_disabled: bool = False,
    ) -> None:
        self.out = out
        self.crash_point = crash_point
        self.provider_url = provider_url
        self.respawn_enabled = respawn_enabled
        self.injector_disabled = injector_disabled
        self.state = SupervisorState()
        self._process: subprocess.Popen | None = None
        self._death_counted = False

    # -- lifetimes ---------------------------------------------------------

    def _environment(self, attempt: int) -> dict:
        env = dict(os.environ)
        env["B5_TRACE"] = str(self.out / "trace.jsonl")
        env["B5_PROVIDER_URL"] = self.provider_url
        env.pop("B5_CRASH_POINT", None)
        env.pop("B5_INJECTOR_DISABLED", None)
        # B4's runner.py:244 rule. Attempt 1 carries the fault; no later
        # lifetime does, or a respawning system would take more faults than a
        # non-respawning one and the arms would not be comparable.
        if self.crash_point and attempt == 1:
            env["B5_CRASH_POINT"] = self.crash_point
            if self.injector_disabled:
                env["B5_INJECTOR_DISABLED"] = "1"
        return env

    def spawn(self, attempt: int) -> bool:
        """Start one worker lifetime. True once it signals ready."""
        ready = self.out / "ready"
        ready.unlink(missing_ok=True)
        with open(self.out / "worker.err", "ab") as errlog:
            self._process = subprocess.Popen(
                [sys.executable, str(HERE / "worker.py"),
                 "--ready-file", str(ready)],
                env=self._environment(attempt),
                stdout=subprocess.DEVNULL, stderr=errlog,
            )
        self.state.spawns += 1
        self._death_counted = False
        if attempt > 1:
            self.state.respawns += 1
        for _ in range(400):
            if ready.exists():
                self.state.lifetimes.append(
                    {"attempt": attempt, "pid": self._process.pid, "ready": True,
                     "armed": bool(self.crash_point and attempt == 1)}
                )
                return True
            if self._process.poll() is not None:
                break
            time.sleep(0.05)
        self.state.lifetimes.append(
            {"attempt": attempt, "pid": self._process.pid, "ready": False,
             "armed": bool(self.crash_point and attempt == 1)}
        )
        return False

    def alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def note_death(self) -> None:
        self.state.deaths += 1

    def maintain(self) -> None:
        """Called on the poll loop: if the worker is gone, bring one back.

        When ``respawn_enabled`` is False the death is still *recorded* -- the
        gate needs ``deaths > 0, respawns == 0`` to tell a missing supervisor
        apart from a legitimate deadline result.
        """
        if self.alive():
            return
        # Count DEATHS, not polls. The first version incremented on every poll
        # while the worker stayed dead, so a respawn-disabled branch reported
        # deaths=232 when one worker had died once. No verdict depended on it --
        # the gate tests deaths > 0 -- but the number as printed counted nothing,
        # and a number that counts nothing does not belong in a report.
        if not self._death_counted:
            self.note_death()
            self._death_counted = True
        if not self.respawn_enabled:
            return
        if self.state.spawns >= MAX_LIFETIMES:
            self.state.exhausted = True
            return
        self.spawn(self.state.spawns + 1)

    def stop(self) -> None:
        """Kill the current lifetime by PID (R1: never by pattern)."""
        if self._process is not None and self._process.poll() is None:
            self._process.kill()
            try:
                self._process.wait(timeout=10)
            except Exception:                                  # noqa: BLE001
                pass
