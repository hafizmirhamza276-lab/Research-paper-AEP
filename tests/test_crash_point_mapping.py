r"""The two roadmap-name mappings are not the same, and one crash point proves it.

`experiments/harness/crash_points.py` resolves roadmap names for systems that
run ``aep_core``'s workflow (AEP-full, B3). `experiments/baselines/crash_points.py`
resolves them for the baselines. **At ``after_barrier_before_dispatch`` the two
disagree, and the disagreement changes what the fault is.**

* For AEP-full and B3 the name resolves to
  ``AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT``, which is *not* in
  ``DEFERRED_CRASH_POINTS``, so the kill is **immediate** and lands before any
  byte is sent.
* For the baselines it resolves to ``BEFORE_REQUEST_TRANSMISSION``, which is
  the whole of ``DEFERRED_BASELINE_POINTS``, so the kill is **deferred** into
  the socket wait and the provider may already have applied the mutation.

The style is chosen on the **resolved value**, not on the roadmap name
(``injector.py``: ``elif point in deferred_points``), which is why the two
mappings produce different faults under one name.

**Why this file exists.** The baseline module's docstring claimed for months
that ``after_barrier_before_dispatch`` was "delivered immediately: the mutation
provably was not sent". The code had never done that. Nothing failed, because
nothing compared the two mappings. These tests compare them.

**They do not assert that the mappings *should* agree.** Making them agree is a
collection decision, not a refactor. What they assert is that the difference is
**deliberate and known**: if someone changes either side, a test fails and
names the consequence.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import pytest

from experiments.baselines.contract import SystemId
from experiments.baselines.crash_points import (
    DEFERRED_BASELINE_POINTS,
    BaselineCrashPoint,
    resolve_for_system,
    uses_aep_crash_points,
)
from experiments.harness.crash_points import (
    DEFERRED_CRASH_POINTS,
    CrashPoint,
    resolve_crash_point,
)
from experiments.harness.injector import (
    CRASH_POINT_VARIABLE,
    CRASH_STYLE_VARIABLE,
    CrashStyle,
    ProcessCrashInjector,
)

ABD = "after_barrier_before_dispatch"
MID = "mid_dispatch"

#: Exactly the pair ``experiments/harness/worker.py`` builds per system.
def _resolver_and_deferred(system: SystemId | None):
    if system is None or uses_aep_crash_points(system):
        return resolve_crash_point, DEFERRED_CRASH_POINTS

    def resolver(name, _system=system):
        return resolve_for_system(_system, name)

    return resolver, DEFERRED_BASELINE_POINTS


def _style_for(system: SystemId | None, roadmap_name: str,
               environ: dict | None = None) -> CrashStyle:
    """The style the worker would really get, through the real code path."""
    resolver, deferred = _resolver_and_deferred(system)
    env = {CRASH_POINT_VARIABLE: roadmap_name}
    env.update(environ or {})
    injector = ProcessCrashInjector.from_environment(
        environ=env, resolver=resolver, deferred_points=deferred,
        killer=lambda point: None,
    )
    assert injector is not None
    return injector.plan.style


AEP_SYSTEMS = [None]  # None => aep_core's own vocabulary (AEP-full, B3)
BASELINES = [
    SystemId.B0_NAIVE_RETRY,
    SystemId.B1_LEASE_ONLY,
    SystemId.B2_CAS_ONLY,
    SystemId.B4_DURABLE_WORKFLOW,
    SystemId.B4B_DURABLE_WORKFLOW_AT_MOST_ONCE,
]


# -- 1. the two mappings must not be assumed identical ----------------------

def test_the_two_mappings_disagree_at_after_barrier_before_dispatch():
    """The guard. If this fails, the mappings converged -- find out which way.

    Converging is not forbidden. It is forbidden to converge *silently*: the
    collected matrix was produced under the disagreement, so every baseline
    rate at this crash point depends on it.
    """
    aep_abd = resolve_crash_point(ABD)
    aep_mid = resolve_crash_point(MID)
    base_abd = resolve_for_system(SystemId.B0_NAIVE_RETRY, ABD)
    base_mid = resolve_for_system(SystemId.B0_NAIVE_RETRY, MID)

    assert aep_abd is not aep_mid, (
        "aep_core used to give the two names different CrashPoints; they are "
        "now the same, so AEP-full's after_barrier_before_dispatch cell has "
        "become a second mid_dispatch cell"
    )
    assert base_abd is base_mid, (
        "the baselines used to collapse the two names onto one "
        "BaselineCrashPoint; they no longer do, so the collected baseline "
        "cells no longer describe what this code produces"
    )
    assert (aep_abd in DEFERRED_CRASH_POINTS) is False
    assert (base_abd in DEFERRED_BASELINE_POINTS) is True


def test_the_deferred_sets_are_not_interchangeable():
    """Neither set's members belong to the other's enum."""
    assert all(isinstance(p, CrashPoint) for p in DEFERRED_CRASH_POINTS)
    assert all(isinstance(p, BaselineCrashPoint)
               for p in DEFERRED_BASELINE_POINTS)
    assert not (set(DEFERRED_CRASH_POINTS) & set(DEFERRED_BASELINE_POINTS))


# -- 2. which system gets which style, at that crash point ------------------

@pytest.mark.parametrize("system", AEP_SYSTEMS)
def test_aep_core_systems_are_killed_immediately_before_dispatch(system):
    """AEP-full and B3: the kill lands before any byte is sent."""
    assert _style_for(system, ABD) is CrashStyle.SIGKILL_IMMEDIATE


@pytest.mark.parametrize("system", AEP_SYSTEMS)
def test_aep_core_systems_are_deferred_at_mid_dispatch(system):
    assert _style_for(system, MID) is CrashStyle.SIGKILL_DEFERRED


@pytest.mark.parametrize("system", BASELINES)
def test_every_baseline_is_deferred_at_both_names(system):
    """The finding. Both names put a baseline inside the socket wait."""
    assert _style_for(system, ABD) is CrashStyle.SIGKILL_DEFERRED
    assert _style_for(system, MID) is CrashStyle.SIGKILL_DEFERRED


def test_the_style_differs_between_the_two_families_at_one_name():
    """Stated as the contrast, so a reader of a failure sees the point."""
    aep = _style_for(None, ABD)
    base = _style_for(SystemId.B0_NAIVE_RETRY, ABD)
    assert aep is CrashStyle.SIGKILL_IMMEDIATE
    assert base is CrashStyle.SIGKILL_DEFERRED
    assert aep is not base


# -- 3. the override, which exists and was never used -----------------------

@pytest.mark.parametrize("system", BASELINES)
def test_the_environment_override_beats_the_mapping(system):
    """``AEP_HARNESS_CRASH_STYLE`` is what a re-collection would set."""
    style = _style_for(
        system, ABD,
        environ={CRASH_STYLE_VARIABLE: CrashStyle.SIGKILL_IMMEDIATE.value},
    )
    assert style is CrashStyle.SIGKILL_IMMEDIATE


# -- 4. known-positives: prove each guard can fail --------------------------

def test_known_positive_a_collapsed_aep_mapping_changes_the_delivered_style():
    """Drive the real path with a collapsed resolver and watch the style move.

    This is the regression the guard above exists for: if ``aep_core`` ever
    resolved ``after_barrier_before_dispatch`` to the deferred point, AEP-full
    would start being killed inside the socket wait -- silently, because
    nothing else in the suite compares the two families.
    """
    def collapsed(name):
        if name == ABD:
            return CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION
        return resolve_crash_point(name)

    injector = ProcessCrashInjector.from_environment(
        environ={CRASH_POINT_VARIABLE: ABD},
        resolver=collapsed, deferred_points=DEFERRED_CRASH_POINTS,
        killer=lambda point: None,
    )
    assert injector.plan.style is CrashStyle.SIGKILL_DEFERRED
    # ... whereas the real resolver gives the opposite, which is the contrast
    # the production assertions pin.
    assert _style_for(None, ABD) is CrashStyle.SIGKILL_IMMEDIATE


def test_known_positive_a_split_baseline_mapping_changes_the_delivered_style():
    """The same, the other way: split the baselines and the style flips."""
    def split(name):
        if name == ABD:
            return BaselineCrashPoint.BEFORE_ANY_WRITE
        return resolve_for_system(SystemId.B0_NAIVE_RETRY, name)

    injector = ProcessCrashInjector.from_environment(
        environ={CRASH_POINT_VARIABLE: ABD},
        resolver=split, deferred_points=DEFERRED_BASELINE_POINTS,
        killer=lambda point: None,
    )
    assert injector.plan.style is CrashStyle.SIGKILL_IMMEDIATE
    assert _style_for(SystemId.B0_NAIVE_RETRY, ABD) is CrashStyle.SIGKILL_DEFERRED


def test_known_positive_the_style_helper_reports_a_real_difference():
    """The helper must not return the same style for everything."""
    styles = {_style_for(None, ABD), _style_for(SystemId.B0_NAIVE_RETRY, ABD)}
    assert len(styles) == 2, (
        "the helper collapsed two different code paths onto one style, so "
        "every assertion above would pass vacuously"
    )


# -- 5. what the collected data shows, which is the reason any of this matters

MATRIX = (Path(__file__).resolve().parent.parent
          / "experiments/results/matrix/analysis/per-execution.csv")

#: Measured at 3b55fc5, crashed regime, ``after_barrier_before_dispatch``.
#: ``None`` for the two systems whose kill is immediate: no effect can exist.
EXPECTED_MEAN_APPLIED = {
    "AEP_FULL": 0.0,
    "B3_INTENT_NO_BARRIER": 0.0,
}


@pytest.mark.skipif(not MATRIX.is_file(), reason="matrix analysis not present")
def test_the_immediate_kill_applies_no_effect_and_the_deferred_kill_does():
    """The consequence, in the collected data rather than in the code."""
    rows = [r for r in csv.DictReader(MATRIX.open(encoding="utf-8"))
            if r["regime"] == "(session-3)" and r["crash_point"] == ABD]
    assert rows, "no rows at that crash point"

    applied = defaultdict(list)
    zero_dispatch = defaultdict(int)
    for r in rows:
        applied[r["system"]].append(int(r["applied_effects"]))
        if r["dispatch_attempts"] == "0":
            zero_dispatch[r["system"]] += 1

    for system, expected in EXPECTED_MEAN_APPLIED.items():
        mean = sum(applied[system]) / len(applied[system])
        assert mean == expected, (
            f"{system} is killed immediately at {ABD} and must apply no "
            f"effect; mean is {mean}"
        )
        assert zero_dispatch[system] == len(applied[system])

    for system in ("B0_NAIVE_RETRY", "B1_LEASE_ONLY", "B2_CAS_ONLY",
                   "B4_DURABLE_WORKFLOW"):
        mean = sum(applied[system]) / len(applied[system])
        assert mean > 1.0, (
            f"{system} is killed inside the socket wait at {ABD}, so effects "
            f"reach the provider; mean is {mean}"
        )


@pytest.mark.skipif(not MATRIX.is_file(), reason="matrix analysis not present")
def test_b4b_records_no_dispatch_attempt_yet_applies_an_effect():
    """The single clearest sign that the kill lands after transmission."""
    rows = [r for r in csv.DictReader(MATRIX.open(encoding="utf-8"))
            if r["regime"] == "(session-3)" and r["crash_point"] == ABD
            and r["system"] == "B4B_DURABLE_WORKFLOW_AT_MOST_ONCE"]
    both = [r for r in rows
            if r["dispatch_attempts"] == "0" and int(r["applied_effects"]) > 0]
    assert len(rows) == 90
    assert len(both) == 82, (
        "82 of 90 B4b executions recorded zero dispatch attempts and an "
        f"applied effect at {ABD}; got {len(both)}"
    )
