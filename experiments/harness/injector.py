"""Environment-variable-selected process crash injection.

PAPER_ROADMAP.md section 3.1(2): *"Workers are separate OS processes killed
with SIGKILL at the chosen point (env-var controlled)."*

Three properties, in the order they matter.

**The kill is a kill.** :func:`hard_kill_self` sends ``SIGKILL`` to the calling
process. No ``finally`` runs, no buffer is flushed, no lease is released, no
connection is closed -- which is the entire point, because everything the
protocol claims about crash recovery is a claim about what Redis contains when
a worker stops existing without cooperating. On Windows, where ``SIGKILL`` does
not exist, ``os.kill`` with any other signal calls ``TerminateProcess``, which
is equally uncatchable and equally unable to run cleanup. It is *not* the same
system call, and :data:`HAS_SIGKILL` records which path a run used so a report
can say so.

**Disabled means absent.** :meth:`ProcessCrashInjector.from_environment`
returns ``None`` when no crash point is selected, and ``None`` is what
``WriteAheadRunner`` receives. The disabled path through ``aep_core`` is
therefore ``if self.crash_injector is not None:`` -- one attribute load and one
identity comparison per checkpoint, no allocation, no I/O. There is no
"disabled injector" object that could grow behaviour later.

**A typo is a failure, not a quiet no-op.** An unrecognised crash-point name
raises at process start. The alternative -- treating it as "no crash" -- would
produce a full, slow, entirely uninformative run whose own log claimed a crash
point was selected.

**Deferred kills.** Five of the roadmap's six crash points are positions the
workflow executes, so the kill happens at the checkpoint. ``mid_dispatch``
names an instant inside a socket wait, which the workflow never executes; the
injector therefore *arms* a watchdog thread at the last pre-transmission
checkpoint and returns, so the request really is sent, and the watchdog
delivers the kill while the connector is blocked on the response. Whether the
provider had already applied the mutation is then read from the ground-truth
ledger rather than assumed.
"""

from __future__ import annotations

import os
import signal
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping

from experiments.harness.crash_points import (
    DEFERRED_CRASH_POINTS,
    ROADMAP_CRASH_POINTS,
    CrashPoint,
    resolve_crash_point,
    roadmap_name_for,
)

#: True where a real ``SIGKILL`` exists. Recorded into every run log: the
#: artifact's crash-fidelity claim rests on the POSIX path, and a run collected
#: on Windows used ``TerminateProcess`` instead.
HAS_SIGKILL = hasattr(signal, "SIGKILL")

#: Environment variables. Read once, at worker start.
CRASH_POINT_VARIABLE = "AEP_HARNESS_CRASH_POINT"
CRASH_STYLE_VARIABLE = "AEP_HARNESS_CRASH_STYLE"
CRASH_DELAY_VARIABLE = "AEP_HARNESS_CRASH_DELAY_MS"
CRASH_EXECUTIONS_VARIABLE = "AEP_HARNESS_CRASH_EXECUTIONS"

#: Exit status a SIGKILLed process is reported with, for logs on platforms
#: that cannot deliver the real signal.
KILL_EXIT_STATUS = 137


def hard_kill_self(point: CrashPoint) -> None:  # pragma: no cover - kills us
    """Stop this process now, with no opportunity to clean up.

    Not covered by the in-process suite by construction: a test that executed
    this line would have no test process left to record the result. It is
    covered instead by ``test_injector.py``'s child-process tests, which assert
    the corpse's exit status.
    """
    if HAS_SIGKILL:
        os.kill(os.getpid(), signal.SIGKILL)
    else:
        # Windows: os.kill with anything other than CTRL_C_EVENT /
        # CTRL_BREAK_EVENT calls TerminateProcess.
        os.kill(os.getpid(), signal.SIGTERM)
    # Unreachable on both paths; present so a platform that somehow returns
    # cannot continue executing protocol code after a "crash".
    os._exit(KILL_EXIT_STATUS)


class CrashStyle(str, Enum):
    """How the kill is delivered relative to the checkpoint."""

    #: Delivered at the checkpoint. The checkpoint never returns.
    SIGKILL_IMMEDIATE = "SIGKILL_IMMEDIATE"
    #: Armed at the checkpoint, delivered by a watchdog thread afterwards, so
    #: the death lands inside the operation the checkpoint precedes.
    SIGKILL_DEFERRED = "SIGKILL_DEFERRED"


@dataclass(frozen=True)
class CrashPlan:
    """What this process will do, decided before it does any protocol work."""

    #: A member of *some* declared crash-point vocabulary. ``aep_core``'s for
    #: AEP-full and B3; ``experiments.baselines.crash_points``' for the four
    #: baselines, which have their own instruction boundaries because they do
    #: not have AEP's. The injector compares members by identity and never by
    #: name, so mixing the two vocabularies is impossible rather than merely
    #: discouraged.
    point: Enum
    style: CrashStyle = CrashStyle.SIGKILL_IMMEDIATE
    #: Only meaningful for ``SIGKILL_DEFERRED``.
    deferred_delay_seconds: float = 0.4
    #: ``None`` means every execution is eligible. A set scopes the crash to
    #: named executions, so one run can contain crashed and control executions.
    executions: frozenset[str] | None = None
    #: The roadmap's name for this position, when the caller selected one. A
    #: baseline's vocabulary has no reverse lookup into the roadmap -- several
    #: roadmap names can share one baseline position -- so the name is carried
    #: rather than derived, and every record says which cell it belongs to.
    roadmap_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.point, Enum):
            raise TypeError("crash plan requires a declared crash-point member")
        if self.deferred_delay_seconds < 0:
            raise ValueError("deferred_delay_seconds cannot be negative")
        if (
            self.style is CrashStyle.SIGKILL_IMMEDIATE
            and self.point in DEFERRED_CRASH_POINTS
        ):
            # Allowed, but it is a different experiment: an immediate kill at
            # the pre-transmission checkpoint proves the mutation was *not*
            # dispatched, which is `after_barrier_before_dispatch`, not
            # `mid_dispatch`. Callers must say so explicitly.
            pass

    @property
    def roadmap_crash_point(self) -> str | None:
        if self.roadmap_name is not None:
            return self.roadmap_name
        return roadmap_name_for(self.point) if isinstance(self.point, CrashPoint) else None

    def echo(self) -> dict[str, Any]:
        return {
            "crash_point": self.point.value,
            "roadmap_crash_point": self.roadmap_crash_point,
            "style": self.style.value,
            "deferred_delay_seconds": self.deferred_delay_seconds,
            "scoped_executions": (
                sorted(self.executions) if self.executions is not None else None
            ),
            "has_sigkill": HAS_SIGKILL,
        }


def _no_emit(event: str, **fields: Any) -> None:
    """Default sink. A crash with no record is a crash nobody can count."""


@dataclass
class ProcessCrashInjector:
    """Implements ``aep_core``'s ``CrashInjectorProtocol`` by dying.

    ``emit`` is called *before* the kill and must have flushed to disk by the
    time it returns; ``experiments/harness/events.py`` flushes every record for
    exactly this reason. A SIGKILL loses process buffers, not the kernel's, so
    a flushed write survives -- see the report's discussion of why ``fsync`` is
    not required for this failure model.
    """

    plan: CrashPlan
    emit: Callable[..., None] = _no_emit
    killer: Callable[[CrashPoint], None] = hard_kill_self
    _fired: bool = field(default=False, init=False)
    _execution_id: str | None = field(default=None, init=False)
    _watchdog: threading.Thread | None = field(default=None, init=False)

    # -- selection ---------------------------------------------------------

    @classmethod
    def from_environment(
        cls,
        *,
        environ: Mapping[str, str] | None = None,
        emit: Callable[..., None] = _no_emit,
        killer: Callable[[CrashPoint], None] = hard_kill_self,
        resolver: Callable[[str | None], Any] = resolve_crash_point,
        deferred_points: frozenset = DEFERRED_CRASH_POINTS,
    ) -> "ProcessCrashInjector | None":
        """Build an injector, or return ``None`` if none was selected.

        ``resolver`` and ``deferred_points`` default to ``aep_core``'s
        vocabulary and are overridden by a worker running one of the section
        3.3 baselines, whose instruction boundaries are its own. Passing them
        in rather than reading a system name here keeps this module ignorant
        of which systems exist, which is what stops the injector from becoming
        the place new systems have to be registered.
        """
        source = os.environ if environ is None else environ
        point = resolver(source.get(CRASH_POINT_VARIABLE))
        if point is None:
            return None

        declared_style = source.get(CRASH_STYLE_VARIABLE)
        if declared_style:
            style = CrashStyle(declared_style)
        elif point in deferred_points:
            style = CrashStyle.SIGKILL_DEFERRED
        else:
            style = CrashStyle.SIGKILL_IMMEDIATE

        raw_delay = source.get(CRASH_DELAY_VARIABLE)
        delay = float(raw_delay) / 1000.0 if raw_delay else 0.4
        if delay < 0:
            raise ValueError(
                f"{CRASH_DELAY_VARIABLE} must not be negative, got {raw_delay!r}"
            )

        raw_executions = source.get(CRASH_EXECUTIONS_VARIABLE)
        executions = (
            frozenset(part for part in raw_executions.split(",") if part)
            if raw_executions
            else None
        )

        declared_name = source.get(CRASH_POINT_VARIABLE)
        return cls(
            plan=CrashPlan(
                point=point,
                style=style,
                deferred_delay_seconds=delay,
                executions=executions,
                roadmap_name=(
                    declared_name
                    if declared_name in ROADMAP_CRASH_POINTS
                    else None
                ),
            ),
            emit=emit,
            killer=killer,
        )

    # -- the protocol-facing surface --------------------------------------

    def enter_execution(self, execution_id: str) -> None:
        """Tell the injector which execution the next checkpoints belong to."""
        self._execution_id = execution_id

    @property
    def armed_for_current_execution(self) -> bool:
        if self.plan.executions is None:
            return True
        return self._execution_id in self.plan.executions

    async def checkpoint(self, point: Any) -> None:
        """Called by ``aep_core`` at every named instruction boundary."""
        if self._fired or point is not self.plan.point:
            return
        if not self.armed_for_current_execution:
            return

        self._fired = True
        if self.plan.style is CrashStyle.SIGKILL_IMMEDIATE:
            self.emit(
                "crash_injected",
                crash_point=self.plan.point.value,
                roadmap_crash_point=self.plan.roadmap_crash_point,
                style=self.plan.style.value,
                execution_id=self._execution_id,
                has_sigkill=HAS_SIGKILL,
            )
            self.killer(self.plan.point)
            return

        self.emit(
            "crash_armed",
            crash_point=self.plan.point.value,
            roadmap_crash_point=self.plan.roadmap_crash_point,
            style=self.plan.style.value,
            deferred_delay_seconds=self.plan.deferred_delay_seconds,
            execution_id=self._execution_id,
            has_sigkill=HAS_SIGKILL,
        )
        self._start_watchdog()

    # -- deferred delivery -------------------------------------------------

    def _start_watchdog(self) -> None:
        execution_id = self._execution_id
        delay = self.plan.deferred_delay_seconds

        def deliver() -> None:
            # A plain sleep, in a thread of its own: the event loop this
            # process is running is the thing being interrupted, so the timer
            # must not live on it.
            threading.Event().wait(delay)
            self.emit(
                "crash_injected",
                crash_point=self.plan.point.value,
                roadmap_crash_point=self.plan.roadmap_crash_point,
                style=self.plan.style.value,
                execution_id=execution_id,
                deferred_delay_seconds=delay,
                has_sigkill=HAS_SIGKILL,
            )
            self.killer(self.plan.point)

        # Not a daemon: on the fake-killer path used by tests the process must
        # not exit while the watchdog is still pending, or the test would
        # observe neither outcome.
        watchdog = threading.Thread(
            target=deliver, name="aep-harness-crash-watchdog", daemon=False
        )
        self._watchdog = watchdog
        watchdog.start()

    def join_watchdog(self, timeout: float | None = None) -> None:
        """Wait for a deferred kill to be delivered. Tests only."""
        if self._watchdog is not None:
            self._watchdog.join(timeout)


@dataclass
class CompositeInjector:
    """Fan one protocol's checkpoints out to several independent injectors.

    Amendment E1 introduces a second thing that can happen at a named
    instruction boundary -- a hard Redis kill -- and a run may want it beside a
    worker crash or instead of one. ``WriteAheadRunner`` takes exactly one
    injector, so the composition happens here rather than by teaching either
    injector about the other.

    Order is the order given, and it is load-bearing: a synchronous worker kill
    never returns, so an injector that must act at the same checkpoint has to
    be listed before it. The runner lists the Redis kill first for that reason.
    """

    injectors: tuple[Any, ...]

    def __post_init__(self) -> None:
        if not self.injectors:
            raise ValueError(
                "a composite of no injectors is not the same thing as no "
                "injector; the disabled path is `crash_injector is None`"
            )

    def enter_execution(self, execution_id: str) -> None:
        for injector in self.injectors:
            injector.enter_execution(execution_id)

    async def checkpoint(self, point: Any) -> None:
        for injector in self.injectors:
            await injector.checkpoint(point)

    @property
    def plan(self):
        """The plans, so ``worker_started`` can echo whichever exist."""
        return [injector.plan.echo() for injector in self.injectors]


def compose_injectors(*injectors: Any) -> Any:
    """The one injector a runner should pass, given zero or more of them."""
    present = tuple(injector for injector in injectors if injector is not None)
    if not present:
        return None
    if len(present) == 1:
        return present[0]
    return CompositeInjector(present)
