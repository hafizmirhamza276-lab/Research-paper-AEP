"""Named crash points, and the mapping from the roadmap's names to the code.

PAPER_ROADMAP.md section 3.1(2) names six crash points:

    ``before_intent_write``, ``after_intent_before_barrier``,
    ``after_barrier_before_dispatch``, ``mid_dispatch``,
    ``after_response_before_resolution``, ``after_resolution_before_barrier``

Those are *descriptions of positions in the protocol*, not identifiers in the
code. ``aep_core`` already carries its own, finer vocabulary of instruction
boundaries -- the ``_checkpoint("...")`` calls in
``aep_core/core/intent_workflow.py`` and ``aep_core/core/intent_recovery.py``,
which are the boundaries ``docs/06-phase2-design.md`` section 7 enumerates.
This module holds both vocabularies and the mapping between them, so the paper
can say "we crashed at ``mid_dispatch``" and a reader can follow it to a line.

**Why the enum is not imported from ``aep_core``.** ``WriteAheadRunner`` takes
``crash_point_enum`` as a constructor parameter and looks members up by name.
That is deliberate: the protocol declares *where* it can be interrupted without
depending on any particular injector's vocabulary. The cost is that nothing in
the type system keeps the two sets in agreement, so
``tests/test_crash_points.py`` asserts the agreement by parsing the checkpoint
names straight out of the ``aep_core`` sources
(:func:`aep_core_checkpoint_names`). A rename in ``aep_core`` fails that test
rather than raising ``KeyError`` inside a worker, mid-run, for one crash point.

**On ``mid_dispatch``.** The other five points are positions the workflow
itself reaches, so a crash there is delivered synchronously at the checkpoint.
``mid_dispatch`` is not: it means *the worker died while the request was in
flight*, and that instant is inside the connector's socket wait, not at any
instruction the workflow executes. It is therefore implemented as a deferred
kill armed at the last checkpoint before transmission
(``AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION``) and delivered by a watchdog
thread while ``connector.mutate`` is blocked. Whether the provider had already
applied the mutation when the worker died is then *read from the ground-truth
ledger* rather than assumed -- see ``experiments/harness/reconcile.py``.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

#: The ``aep_core`` modules that reach checkpoints. Parsed, not imported: the
#: point of the gate is to read what the source actually says.
_CHECKPOINT_SOURCES = (
    "intent_workflow.py",
    "intent_recovery.py",
)

_CHECKPOINT_CALL = re.compile(r"_checkpoint\(\s*\n?\s*\"([A-Z0-9_]+)\"")

_AEP_CORE = Path(__file__).resolve().parents[2] / "aep_core" / "core"


class CrashPoint(str, Enum):
    """Every instruction boundary ``aep_core`` announces it can be cut at.

    Exactly the set of names passed to ``_checkpoint`` in the two modules
    above -- asserted, not assumed (``test_crash_points.py``).
    """

    # -- the write-ahead workflow ------------------------------------------
    BEFORE_LEASE_ACQUISITION = "BEFORE_LEASE_ACQUISITION"
    AFTER_LEASE_ACQUISITION_BEFORE_INTENT_CAS = (
        "AFTER_LEASE_ACQUISITION_BEFORE_INTENT_CAS"
    )
    DURING_INTENT_CAS = "DURING_INTENT_CAS"
    AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER = (
        "AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER"
    )
    AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT = (
        "AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT"
    )
    AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION = (
        "AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION"
    )
    DURING_RESOLUTION_CAS = "DURING_RESOLUTION_CAS"
    AFTER_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER = (
        "AFTER_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER"
    )
    DURING_RESOLUTION_DURABILITY_BARRIER = "DURING_RESOLUTION_DURABILITY_BARRIER"
    AFTER_DURABLE_FIRED_UNCONFIRMED_BEFORE_LEASE_RELEASE = (
        "AFTER_DURABLE_FIRED_UNCONFIRMED_BEFORE_LEASE_RELEASE"
    )
    AFTER_DURABLE_CONFIRMED_RESOLUTION_BEFORE_LEASE_RELEASE = (
        "AFTER_DURABLE_CONFIRMED_RESOLUTION_BEFORE_LEASE_RELEASE"
    )

    # -- the recovery service ----------------------------------------------
    DURING_RECOVERY_BEFORE_CLAIM_CAS = "DURING_RECOVERY_BEFORE_CLAIM_CAS"
    DURING_RECOVERY_RESOLUTION_CAS = "DURING_RECOVERY_RESOLUTION_CAS"
    AFTER_RECOVERY_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER = (
        "AFTER_RECOVERY_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER"
    )
    DURING_RECOVERY_RESOLUTION_DURABILITY_BARRIER = (
        "DURING_RECOVERY_RESOLUTION_DURABILITY_BARRIER"
    )


#: The roadmap's six names, in the roadmap's order, mapped to the checkpoint
#: each one denotes. Insertion order is asserted by test: the paper's tables
#: are laid out in it.
ROADMAP_CRASH_POINTS: Mapping[str, CrashPoint] = MappingProxyType(
    {
        # The lease is held and the state has been read; nothing is written.
        "before_intent_write": CrashPoint.AFTER_LEASE_ACQUISITION_BEFORE_INTENT_CAS,
        # ABOUT_TO_FIRE is in Redis but not yet acknowledged durable. This is
        # the residual pre-ack window docs/22-formal-model.md declares for P2.
        "after_intent_before_barrier": (
            CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER
        ),
        # WAITAOF has acknowledged; no provider bytes have been sent.
        "after_barrier_before_dispatch": (
            CrashPoint.AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT
        ),
        # Armed here; delivered while the socket is waiting. See the module
        # docstring.
        "mid_dispatch": CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION,
        # The provider answered and the answer was classified; nothing about
        # it has been written down.
        "after_response_before_resolution": CrashPoint.DURING_RESOLUTION_CAS,
        # The resolution is in Redis but not yet acknowledged durable.
        "after_resolution_before_barrier": (
            CrashPoint.AFTER_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER
        ),
    }
)

#: The one crash point that cannot be delivered synchronously at its
#: checkpoint, because the instant it names is inside a socket wait.
DEFERRED_CRASH_POINTS = frozenset({CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION})


def aep_core_checkpoint_names(source_directory: Path | None = None) -> set[str]:
    """Every name passed to ``_checkpoint`` in the ``aep_core`` sources.

    Read from disk on purpose. Importing the modules and inspecting them would
    only tell us what the enum already says; parsing the source tells us what
    the protocol will actually ask for by name at run time.
    """
    directory = source_directory or _AEP_CORE
    names: set[str] = set()
    for filename in _CHECKPOINT_SOURCES:
        text = (directory / filename).read_text(encoding="utf-8")
        names.update(_CHECKPOINT_CALL.findall(text))
    return names


def resolve_crash_point(name: str | None) -> CrashPoint | None:
    """Accept a roadmap name or a canonical name; refuse anything else.

    ``None`` and the empty string mean "no crash injection". Every other
    unrecognised value raises: a mistyped crash point that silently read as
    "no crash" would produce a full, expensive, entirely uninformative run
    whose log claimed a crash point was selected.
    """
    if not name:
        return None
    if name in ROADMAP_CRASH_POINTS:
        return ROADMAP_CRASH_POINTS[name]
    try:
        return CrashPoint[name]
    except KeyError:
        raise KeyError(
            f"unknown crash point {name!r}; roadmap names: "
            f"{sorted(ROADMAP_CRASH_POINTS)}; canonical names: "
            f"{sorted(member.name for member in CrashPoint)}"
        ) from None


def roadmap_name_for(point: CrashPoint) -> str | None:
    """The roadmap's name for a checkpoint, if the roadmap names it."""
    for name, mapped in ROADMAP_CRASH_POINTS.items():
        if mapped is point:
            return name
    return None
