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
    ``after_barrier_before_dispatch`` and ``mid_dispatch``, and **both are
    delivered by the deferred watchdog**, so in a baseline the death lands
    inside the socket wait for either name. See "Two mappings, and they are
    not the same" below: this is the one place where a baseline's delivered
    position differs from the roadmap position it is named for.

``AFTER_RESPONSE_BEFORE_RECORD``
    The provider's answer has been received and classified, and nothing about
    it has been written down. Corresponds to
    ``after_response_before_resolution``.

``AFTER_RECORD_BEFORE_BARRIER``
    The outcome has been written and not yet acknowledged durable.
    Corresponds to ``after_resolution_before_barrier``. B0, B1 and B2 write
    their outcome without any barrier at all, so the moment exists in them --
    it is simply never followed by an acknowledgement, which is the point.

Two mappings, and they are not the same
---------------------------------------

There are **two** roadmap-name resolutions in this project, and at one crash
point they disagree. Anything that reasons about a cell has to know which one
produced it.

======================================  ==========================  ==========
roadmap name                            systems on ``aep_core``      baselines
                                        (AEP-full, B3)               (B0-B2,
                                                                     B4, B4b)
======================================  ==========================  ==========
``after_barrier_before_dispatch``       ``AFTER_DURABLE_ABOUT_TO_``  ``BEFORE_``
                                        ``FIRE_BEFORE_PREFLIGHT``    ``REQUEST_``
                                        -> **SIGKILL_IMMEDIATE**     ``TRANS...``
                                                                     -> **DEFERRED**
``mid_dispatch``                        ``AFTER_PREFLIGHT_BEFORE_``  same value
                                        ``REQUEST_TRANSMISSION``     -> **DEFERRED**
                                        -> **SIGKILL_DEFERRED**
======================================  ==========================  ==========

``harness/crash_points.py`` gives the two names **different** ``CrashPoint``
values and defers only the second, so for AEP-full and B3 the two cells really
are different positions: the kill at ``after_barrier_before_dispatch`` lands
before any byte is sent, and no effect can exist.

This module gives the two names the **same** ``BaselineCrashPoint`` value, and
:data:`DEFERRED_BASELINE_POINTS` contains exactly that value. Deferral is
chosen on the *resolved value*, not on the roadmap name
(``harness/injector.py``: ``elif point in deferred_points``), so a baseline is
killed inside the socket wait under **both** names, and an effect can have
reached the provider.

**Consequence, measured.** In the collected matrix, at
``after_barrier_before_dispatch``: AEP-full and B3 apply 0.000 effects with
``dispatch_attempts == 0`` in 90/90; B0, B1, B2 and B4 apply 2.09-2.32; and
B4b records zero dispatch attempts *and* an applied effect in 82 of 90
executions. ``tests/test_crash_point_mapping.py`` pins all of this.

**B5/B5b are not affected.** They appear in :data:`ROADMAP_TO_BASELINE`, but
``b5_temporal/worker.py`` reads the roadmap name directly and has its own
immediate and deferred paths, so its ``after_barrier_before_dispatch`` really
is immediate. That asymmetry is why a B4-vs-B5 comparison at this crash point
is not like-for-like.

**Overriding it.** ``AEP_HARNESS_CRASH_STYLE`` forces a style and is honoured
ahead of this table (``RunConfig.crash_style`` -> ``runner.py``). The matrix
never sets it: all 84 tracked ``run-config.json`` files carry
``crash_style: null``.
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

#: B5/B5b. A shape neither existing mapping has: the engine *does* write a
#: durable pre-dispatch record, so ``_WITHOUT_PRE_DISPATCH_RECORD`` is wrong,
#: but the record is written by the SERVER inside one RPC, so there is no
#: worker-side instant between writing it and its acknowledgement and
#: ``_WITH_PRE_DISPATCH_RECORD`` is wrong too. ``after_intent_before_barrier``
#: is therefore ``None`` -- *this system has no such moment* -- and
#: ``run_matrix`` records the cell ``not_applicable`` with the reason rather
#: than aliasing it onto a neighbour. See ``b5_temporal/B5_SEMANTICS.md`` 2.3.
_TEMPORAL_SERVER_SIDE_BARRIER: Mapping[str, BaselineCrashPoint | None] = (
    MappingProxyType(
        {
            "before_intent_write": BaselineCrashPoint.BEFORE_ANY_WRITE,
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

#: Per system, the roadmap name -> that system's own position, or ``None``
#: where the system has no such moment.
ROADMAP_TO_BASELINE: Mapping[SystemId, Mapping[str, BaselineCrashPoint | None]] = (
    MappingProxyType(
        {
            SystemId.B0_NAIVE_RETRY: _WITHOUT_PRE_DISPATCH_RECORD,
            SystemId.B1_LEASE_ONLY: _WITHOUT_PRE_DISPATCH_RECORD,
            SystemId.B2_CAS_ONLY: _WITHOUT_PRE_DISPATCH_RECORD,
            SystemId.B4_DURABLE_WORKFLOW: _WITH_PRE_DISPATCH_RECORD,
            # B4b runs the same code at the same checkpoints; only its retry
            # policy differs, so it has exactly B4's positions.
            SystemId.B4B_DURABLE_WORKFLOW_AT_MOST_ONCE: _WITH_PRE_DISPATCH_RECORD,
            SystemId.B5_TEMPORAL: _TEMPORAL_SERVER_SIDE_BARRIER,
            SystemId.B5B_TEMPORAL_AT_MOST_ONCE: _TEMPORAL_SERVER_SIDE_BARRIER,
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
        # B5's absence has a different cause and must not be reported with
        # B0-B2's reason: the record IS written, by the server, transactionally.
        "after_intent_before_barrier:B5": (
            "the worker issues an RPC and the server persists the record "
            "transactionally before replying, so no worker-side window exists "
            "between the write and its acknowledgement"
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
