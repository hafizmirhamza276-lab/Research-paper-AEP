"""The crash-point vocabulary, and the gate that stops it drifting.

The harness names crash points; ``aep_core`` names checkpoints. Nothing in the
type system connects the two -- ``WriteAheadRunner`` takes ``crash_point_enum``
as a parameter and looks members up by string
(``aep_core/core/intent_workflow.py`` ``_checkpoint``). A checkpoint renamed in
``aep_core`` would therefore raise ``KeyError`` deep inside a worker process,
mid-run, and only for the crash point that happened to be selected.

So the agreement is asserted here, by parsing the checkpoint names out of the
``aep_core`` sources and comparing them with the enum.
"""

from __future__ import annotations

import pytest

from experiments.harness.crash_points import (
    ROADMAP_CRASH_POINTS,
    CrashPoint,
    aep_core_checkpoint_names,
    resolve_crash_point,
)


# ===========================================================================
# The anti-drift gate
# ===========================================================================


def test_the_enum_is_exactly_the_set_of_checkpoints_aep_core_reaches():
    """Neither direction may drift.

    A missing member is a ``KeyError`` in a worker at crash time. An extra
    member is a crash point the harness offers and the protocol never
    reaches, which would silently produce a run with no crash in it.
    """
    assert aep_core_checkpoint_names() == {member.name for member in CrashPoint}


def test_every_member_name_equals_its_value():
    """The value is what is written to ``events.jsonl`` and read back."""
    for member in CrashPoint:
        assert member.name == member.value


# ===========================================================================
# The roadmap's six names
# ===========================================================================


ROADMAP_NAMES = (
    "before_intent_write",
    "after_intent_before_barrier",
    "after_barrier_before_dispatch",
    "mid_dispatch",
    "after_response_before_resolution",
    "after_resolution_before_barrier",
)


def test_the_roadmap_names_are_exactly_the_six_the_roadmap_lists():
    """PAPER_ROADMAP.md 3.1(2)."""
    assert tuple(ROADMAP_CRASH_POINTS) == ROADMAP_NAMES


@pytest.mark.parametrize("name", ROADMAP_NAMES)
def test_every_roadmap_name_resolves_to_a_checkpoint_aep_core_reaches(name):
    assert ROADMAP_CRASH_POINTS[name].name in aep_core_checkpoint_names()


def test_the_six_roadmap_names_map_to_six_distinct_points():
    """An alias collision would silently halve the crash matrix."""
    assert len(set(ROADMAP_CRASH_POINTS.values())) == len(ROADMAP_CRASH_POINTS)


@pytest.mark.parametrize(
    ("roadmap_name", "canonical"),
    [
        ("before_intent_write", "AFTER_LEASE_ACQUISITION_BEFORE_INTENT_CAS"),
        ("after_intent_before_barrier", "AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER"),
        (
            "after_barrier_before_dispatch",
            "AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT",
        ),
        ("mid_dispatch", "AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION"),
        ("after_response_before_resolution", "DURING_RESOLUTION_CAS"),
        (
            "after_resolution_before_barrier",
            "AFTER_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER",
        ),
    ],
)
def test_each_roadmap_name_maps_to_the_documented_checkpoint(roadmap_name, canonical):
    """Pinned, because the mapping is a claim the paper will make in prose."""
    assert ROADMAP_CRASH_POINTS[roadmap_name].name == canonical


# ===========================================================================
# Resolution accepts both vocabularies and refuses everything else
# ===========================================================================


def test_a_roadmap_name_resolves():
    assert resolve_crash_point("mid_dispatch") is (
        CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION
    )


def test_a_canonical_name_resolves():
    assert resolve_crash_point("DURING_RESOLUTION_CAS") is (
        CrashPoint.DURING_RESOLUTION_CAS
    )


def test_none_resolves_to_no_crash_point():
    assert resolve_crash_point(None) is None
    assert resolve_crash_point("") is None


def test_an_unknown_name_is_refused_rather_than_ignored():
    """A typo must not read as 'no crash', which would be a silent no-op run."""
    with pytest.raises(KeyError) as refused:
        resolve_crash_point("mid-dispatch")

    assert "mid_dispatch" in str(refused.value)


def test_resolution_is_case_sensitive_for_canonical_names():
    with pytest.raises(KeyError):
        resolve_crash_point("during_resolution_cas")
