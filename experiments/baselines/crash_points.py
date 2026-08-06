"""Where the roadmap's six crash points land in a system that lacks them.

The roadmap names positions *in AEP's protocol*: ``before_intent_write``,
``after_intent_before_barrier``, and so on. Four of the six systems in section
3.3 do not have an intent write or a durability barrier -- that absence is what
defines them -- so "crash B0 at ``after_intent_before_barrier``" is not a
harder version of the same experiment. It is a request to crash at a moment
that does not exist.

There are two ways to handle that and only one of them is honest. Aliasing the
missing point onto the nearest one that does exist would produce a full row of
numbers for a cell whose experiment was never performed, and nothing in the
output would say so. Instead, the mapping below is explicit and partial:
:data:`ROADMAP_TO_BASELINE` maps a roadmap name either to a real position in
that system or to ``None``, and ``None`` means *this system has no such
moment*. ``run_matrix.py`` records those cells as ``not_applicable`` with the
reason, and the paper's tables carry the gap rather than filling it.

The positions themselves are chosen so that a crash at a shared name interrupts
the *same physical event* in every system that has it:

``BEFORE_ANY_WRITE``
    The lease (where there is one) is held and nothing has been written
    anywhere. Corresponds to ``before_intent_write``.

``AFTER_PRE_DISPATCH_RECORD_BEFORE_BARRIER``
    A record of the intent to call exists and has not been acknowledged
    durable. Only B4 has one; B0, B1 and B2 do not, by definition.

``BEFORE_REQUEST_TRANSMISSION``
    The last instruction before any provider bytes can exist. Serves both
    ``after_barrier_before_dispatch`` (delivered immediately: the mutation
    provably was not sent) and ``mid_dispatch`` (delivered by the deferred
    watchdog, so the death lands inside the socket wait).

``AFTER_RESPONSE_BEFORE_RECORD``
    The provider's answer has been received and classified, and nothing about
    it has been written down. Corresponds to
    ``after_response_before_resolution``.

``AFTER_RECORD_BEFORE_BARRIER``
    The outcome has been written and not yet acknowledged durable.
    Corresponds to ``after_resolution_before_barrier``. B0, B1 and B2 write
    their outcome without any barrier at all, so the moment exists in them --
    it is simply never followed by an acknowledgement, which is the point.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Mapping

from experiments.baselines.contract import SystemId
from experiments.harness.crash_points import (
    ROADMAP_CRASH_POINTS,
    CrashPoint,
    resolve_crash_point,
)


class BaselineCrashPoint(str, Enum):
    """Instruction boundaries the baselines announce they can be cut at."""

    BEFORE_ANY_WRITE = "BEFORE_ANY_WRITE"
    AFTER_PRE_DISPATCH_RECORD_BEFORE_BARRIER = (
        "AFTER_PRE_DISPATCH_RECORD_BEFORE_BARRIER"
    )
    BEFORE_REQUEST_TRANSMISSION = "BEFORE_REQUEST_TRANSMISSION"
    AFTER_RESPONSE_BEFORE_RECORD = "AFTER_RESPONSE_BEFORE_RECORD"
    AFTER_RECORD_BEFORE_BARRIER = "AFTER_RECORD_BEFORE_BARRIER"


#: The one baseline point that must be delivered by the deferred watchdog,
#: because the instant it names is inside a socket wait the caller never
#: executes. Mirrors ``harness.crash_points.DEFERRED_CRASH_POINTS``.
DEFERRED_BASELINE_POINTS = frozenset(
    {BaselineCrashPoint.BEFORE_REQUEST_TRANSMISSION}
)

_WITHOUT_PRE_DISPATCH_RECORD: Mapping[str, BaselineCrashPoint | None] = (
    MappingProxyType(
        {
            "before_intent_write": BaselineCrashPoint.BEFORE_ANY_WRITE,
            # No record is written before the call, so there is no window
            # between writing one and acknowledging it durable.
            "after_intent_before_barrier": None,
            "after_barrier_before_dispatch": (
                BaselineCrashPoint.BEFORE_REQUEST_TRANSMISSION
            ),
            "mid_dispatch": BaselineCrashPoint.BEFORE_REQUEST_TRANSMISSION,
            "after_response_before_resolution": (
                BaselineCrashPoint.AFTER_RESPONSE_BEFORE_RECORD
            ),
            "after_resolution_before_barrier": (
                BaselineCrashPoint.AFTER_RECORD_BEFORE_BARRIER
            ),
        }
    )
)

_WITH_PRE_DISPATCH_RECORD: Mapping[str, BaselineCrashPoint | None] = (
    MappingProxyType(
        {
            "before_intent_write": BaselineCrashPoint.BEFORE_ANY_WRITE,
            "after_intent_before_barrier": (
                BaselineCrashPoint.AFTER_PRE_DISPATCH_RECORD_BEFORE_BARRIER
            ),
            "after_barrier_before_dispatch": (
                BaselineCrashPoint.BEFORE_REQUEST_TRANSMISSION
            ),
            "mid_dispatch": BaselineCrashPoint.BEFORE_REQUEST_TRANSMISSION,
            "after_response_before_resolution": (
                BaselineCrashPoint.AFTER_RESPONSE_BEFORE_RECORD
            ),
            "after_resolution_before_barrier": (
                BaselineCrashPoint.AFTER_RECORD_BEFORE_BARRIER
            ),
        }
    )
)

#: Per system, the roadmap name -> that system's own position, or ``None``
#: where the system has no such moment.
ROADMAP_TO_BASELINE: Mapping[SystemId, Mapping[str, BaselineCrashPoint | None]] = (
    MappingProxyType(
        {
            SystemId.B0_NAIVE_RETRY: _WITHOUT_PRE_DISPATCH_RECORD,
            SystemId.B1_LEASE_ONLY: _WITHOUT_PRE_DISPATCH_RECORD,
            SystemId.B2_CAS_ONLY: _WITHOUT_PRE_DISPATCH_RECORD,
            SystemId.B4_DURABLE_WORKFLOW: _WITH_PRE_DISPATCH_RECORD,
        }
    )
)

#: Why a cell is not applicable, in a form a table footnote can quote.
NOT_APPLICABLE_REASONS: Mapping[str, str] = MappingProxyType(
    {
        "after_intent_before_barrier": (
            "the system writes no record before dispatching, so there is no "
            "window between writing one and acknowledging it durable"
        ),
    }
)


class CrashPointNotApplicable(LookupError):
    """This system has no moment answering to that roadmap crash point."""


def uses_aep_crash_points(system: SystemId) -> bool:
    """True for the systems that execute ``aep_core``'s own workflow.

    B3 is the full ``WriteAheadRunner`` with the barrier ablated, so it reaches
    every ``_checkpoint`` AEP-full reaches and uses the same vocabulary.
    """
    return system not in ROADMAP_TO_BASELINE


def crash_point_enum_for(system: SystemId) -> type[Enum]:
    return CrashPoint if uses_aep_crash_points(system) else BaselineCrashPoint


def resolve_for_system(system: SystemId, name: str | None):
    """Resolve a crash point in the vocabulary of one system.

    Raises :class:`CrashPointNotApplicable` when the roadmap names a moment
    this system does not have -- never returns ``None`` for that case, because
    ``None`` already means "no crash injection" and the two must not be
    confused by a caller that forgot to check.
    """
    if not name:
        return None
    if uses_aep_crash_points(system):
        return resolve_crash_point(name)

    mapping = ROADMAP_TO_BASELINE[system]
    if name in mapping:
        resolved = mapping[name]
        if resolved is None:
            raise CrashPointNotApplicable(
                f"{system.value} has no position answering to {name!r}: "
                f"{NOT_APPLICABLE_REASONS.get(name, 'not applicable')}"
            )
        return resolved
    try:
        return BaselineCrashPoint[name]
    except KeyError:
        raise KeyError(
            f"unknown crash point {name!r} for {system.value}; roadmap names: "
            f"{sorted(ROADMAP_CRASH_POINTS)}; canonical names: "
            f"{sorted(member.name for member in BaselineCrashPoint)}"
        ) from None


def applicable_roadmap_points(system: SystemId) -> tuple[str, ...]:
    """The roadmap crash points this system can actually be cut at."""
    if uses_aep_crash_points(system):
        return tuple(ROADMAP_CRASH_POINTS)
    mapping = ROADMAP_TO_BASELINE[system]
    return tuple(name for name in ROADMAP_CRASH_POINTS if mapping.get(name) is not None)
