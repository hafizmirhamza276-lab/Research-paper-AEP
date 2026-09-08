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
    #: The run's LABEL and the fault it actually took name different points.
    #: NOT a measurement, and the one void here that cannot be detected by
    #: looking at the run alone: every other verdict asks "did the instrument
    #: work?", this one asks "did it do what this cell claims it did?". A run
    #: labelled ``mid_dispatch`` that was cut at ``after_barrier_before_dispatch``
    #: is internally consistent, settles normally, and produces a full row of
    #: plausible numbers under the wrong heading.
    VOID_CRASH_POINT_MISMATCH = "VOID_CRASH_POINT_MISMATCH"
    #: The point was reached but the kill did not fire. NOT a measurement.
    VOID_INJECTOR_DID_NOT_FIRE = "VOID_INJECTOR_DID_NOT_FIRE"
    #: The worker never came up. NOT a measurement.
    VOID_WORKER_NEVER_READY = "VOID_WORKER_NEVER_READY"
    #: The injected kill worked, but no worker was brought back, so the engine's
    #: retry had nothing to poll. NOT a measurement --- and before this verdict
    #: existed it was indistinguishable from ``PENDING_AT_DEADLINE``, which is
    #: how three Start-To-Close values were all reported as deadline results
    #: when in fact none of them was ever exercised.
    VOID_SUPERVISOR_NEVER_RESPAWNED = "VOID_SUPERVISOR_NEVER_RESPAWNED"
    #: The run happened but its effects could not be attributed to executions:
    #: no ledger, an unreadable one, or rows the plan's targets do not account
    #: for. NOT a measurement, and the verdict that must exist because a missing
    #: oracle otherwise looks exactly like a clean zero-duplicate result --
    #: which would make B5 appear better than B4 for the one reason that has
    #: nothing to do with either engine.
    VOID_ATTRIBUTION_UNAVAILABLE = "VOID_ATTRIBUTION_UNAVAILABLE"


VOID_VERDICTS = frozenset(
    {
        RunVerdict.VOID_CRASH_POINT_MISMATCH,
        RunVerdict.VOID_INJECTOR_NEVER_REACHED,
        RunVerdict.VOID_INJECTOR_DID_NOT_FIRE,
        RunVerdict.VOID_WORKER_NEVER_READY,
        RunVerdict.VOID_SUPERVISOR_NEVER_RESPAWNED,
        RunVerdict.VOID_ATTRIBUTION_UNAVAILABLE,
    }
)


@dataclass(frozen=True)
class AttributionStatus:
    """Whether the shared reconciler could account for this run's effects."""

    usable: bool
    reason: str
    unattributed_rows: int = 0


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
    worker_deaths: int = 0,
    respawns: int = 0,
    attribution: "AttributionStatus | None" = None,
    expected_point: str | None = None,
    reached_points: list[str] | None = None,
) -> GateResult:
    """Decide what a run was. ``events`` is the trace's event names, in order.

    ``settled`` means the workflow returned a result before the deadline.

    ``expected_point`` is the point this run's **label** resolves to, and
    ``reached_points`` the points the worker recorded reaching. Both are
    optional so the existing callers that arm and label from a single value are
    unaffected; where they are supplied, the run must agree with its own label.
    """
    # Identity before instrument, and before outcome. Every other verdict below
    # asks whether the instrument worked. This one asks whether the run belongs
    # to the cell it will be filed under, and there is no reading of a run that
    # answers no: its attribution could be perfect and its numbers would still
    # be published beneath the wrong crash point.
    if (
        armed_point is not None
        and expected_point is not None
        and armed_point != expected_point
    ):
        return GateResult(
            RunVerdict.VOID_CRASH_POINT_MISMATCH,
            f"this run is labelled for {expected_point!r} but the injector was "
            f"armed at {armed_point!r}; the two name different moments, so "
            f"whatever it measured does not belong to this cell",
        )

    # Attribution is checked next, before the run's own outcome is consulted.
    # A rate computed over unattributable effects is worse than no rate: it
    # looks like data.
    if attribution is not None and not attribution.usable:
        return GateResult(
            RunVerdict.VOID_ATTRIBUTION_UNAVAILABLE,
            f"the oracle could not attribute this run's effects: "
            f"{attribution.reason}. No rate may be computed from it, and a "
            f"zero here would be indistinguishable from a clean result.",
        )

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

    # The worker only traces a point it was armed at, so a point in the trace
    # that is not the armed one means the process carried an arming this run did
    # not ask for -- a stale environment, a shared worker, a respawn that
    # re-armed. Checked before ``reached``, because otherwise a trace naming the
    # wrong point still contains the right event name and reads as success.
    if reached_points:
        wrong = sorted({p for p in reached_points if p != armed_point})
        if wrong:
            return GateResult(
                RunVerdict.VOID_CRASH_POINT_MISMATCH,
                f"the injector was armed at {armed_point!r} but the worker "
                f"recorded reaching {', '.join(repr(p) for p in wrong)}; the "
                f"fault delivered is not the fault this run names",
            )

    reached = (
        armed_point in reached_points
        if reached_points is not None
        else "b5_point_reached" in events
    )
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

    # The fault was delivered. Before the run may be called PENDING_AT_DEADLINE,
    # the engine's retry must have had somewhere to run. Temporal schedules the
    # retry onto a task queue; if the killed worker was never replaced there is
    # nothing polling that queue, and the run cannot settle for a reason that has
    # nothing to do with any timeout.
    if (not settled) and worker_deaths > 0 and respawns == 0:
        return GateResult(
            RunVerdict.VOID_SUPERVISOR_NEVER_RESPAWNED,
            f"the fault was delivered at {armed_point!r} and the worker died, "
            f"but no worker was respawned: the engine's retry had no worker to "
            f"poll, so this run measures the supervisor and not the engine. "
            f"NOT a deadline result.",
        )

    return GateResult(
        RunVerdict.COMPLETED if settled else RunVerdict.PENDING_AT_DEADLINE,
        f"fault delivered at {armed_point!r}; "
        f"worker deaths={worker_deaths}, respawns={respawns}",
    )
