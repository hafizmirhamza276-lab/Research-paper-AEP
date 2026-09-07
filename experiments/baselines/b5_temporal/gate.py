"""The reach gate: did the injector actually get to the armed crash point?

**Why this exists.** Before it, a run whose injector never fired and a run whose
retry had not yet fired looked *identical to the caller*: both simply did not
finish. The pre-registration
(`reports/phase-report-ws6-prediction-2026-09-07.md` §3.3) treats one of those as
a legitimate measurement outcome --- ``PENDING_AT_DEADLINE``, counted and
reported --- and the other is an instrument failure that must void the run. A
session run without this gate would have recorded instrument failures as data,
and the 20% uninformative-cell rule would have blamed the Start-To-Close timeout
rather than the injector.

That is not hypothetical: it is what WS-6's first probe did. The workflow-side
point raised ``RestrictedWorkflowAccessError`` inside Temporal's sandbox, the
workflow task was retried indefinitely, and every run looked like
``PENDING_AT_DEADLINE``.

**The rule.** An armed run must carry positive evidence that the named point was
reached. Absence of that evidence voids the run, with a reason naming the
injector --- never the deadline.

Deliberately a pure function over the trace: it can be tested on fixtures, and
the failing branch can be exercised without a Temporal server.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RunVerdict(str, Enum):
    """What a B5 run is, once the injector's own behaviour is accounted for."""

    #: The workflow finished. A measurement.
    COMPLETED = "COMPLETED"
    #: Armed, the point was reached, the worker died, and the run did not settle
    #: inside the deadline. A measurement --- the pre-registered third outcome.
    PENDING_AT_DEADLINE = "PENDING_AT_DEADLINE"
    #: The injector never reached the armed point. NOT a measurement.
    VOID_INJECTOR_NEVER_REACHED = "VOID_INJECTOR_NEVER_REACHED"
    #: The point was reached but the kill did not fire. NOT a measurement.
    VOID_INJECTOR_DID_NOT_FIRE = "VOID_INJECTOR_DID_NOT_FIRE"
    #: The worker never came up. NOT a measurement.
    VOID_WORKER_NEVER_READY = "VOID_WORKER_NEVER_READY"


VOID_VERDICTS = frozenset(
    {
        RunVerdict.VOID_INJECTOR_NEVER_REACHED,
        RunVerdict.VOID_INJECTOR_DID_NOT_FIRE,
        RunVerdict.VOID_WORKER_NEVER_READY,
    }
)


@dataclass(frozen=True)
class GateResult:
    verdict: RunVerdict
    reason: str

    @property
    def is_void(self) -> bool:
        return self.verdict in VOID_VERDICTS


def classify(
    *,
    armed_point: str | None,
    settled: bool,
    worker_ready: bool,
    events: list[str],
) -> GateResult:
    """Decide what a run was. ``events`` is the trace's event names, in order.

    ``settled`` means the workflow returned a result before the deadline.
    """
    if not worker_ready:
        return GateResult(
            RunVerdict.VOID_WORKER_NEVER_READY,
            "the worker never signalled ready; nothing was injected and nothing "
            "was measured",
        )

    if armed_point is None:
        # No fault was requested. Only the workflow's own outcome matters.
        return GateResult(
            RunVerdict.COMPLETED if settled else RunVerdict.PENDING_AT_DEADLINE,
            "no crash point armed",
        )

    reached = "b5_point_reached" in events
    fired = "b5_crash_firing" in events

    if not reached:
        # The decisive case, and the reason this module exists. Note what is NOT
        # said: nothing about the deadline. A run that never reached its crash
        # point tells us nothing about timing, and reporting it as
        # PENDING_AT_DEADLINE would be reporting an instrument failure as data.
        return GateResult(
            RunVerdict.VOID_INJECTOR_NEVER_REACHED,
            f"injector armed at {armed_point!r} but the worker never recorded "
            f"reaching it: the fault was not delivered, so this run is not a "
            f"measurement of anything. NOT a deadline result.",
        )

    if not fired:
        return GateResult(
            RunVerdict.VOID_INJECTOR_DID_NOT_FIRE,
            f"the worker reached {armed_point!r} but no kill was recorded: the "
            f"injector was disabled or failed to fire",
        )

    return GateResult(
        RunVerdict.COMPLETED if settled else RunVerdict.PENDING_AT_DEADLINE,
        f"fault delivered at {armed_point!r}",
    )
