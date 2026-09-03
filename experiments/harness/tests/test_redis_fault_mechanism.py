"""Arm A's mechanism selection, and the guarantee that Arm A did not touch Arm 0.

Two things are pinned here and the second matters more than the first: the new
regime must reach all three capability classes and deliver the freeze, and the
frozen regime it is compared against must be **byte-for-byte the experiment it
always was**. If `REGIME_REDIS_KILL_PREACK` drifts, the uncontrolled
replication stops being a replication of anything.
"""

from __future__ import annotations

import pytest

from experiments.harness import redis_kill
from experiments.run_matrix import (
    REGIME_REDIS_KILL_PREACK,
    REGIME_REDIS_PAUSE_KILL_PREACK,
    REGIMES,
)


def test_the_frozen_regime_is_unchanged_field_by_field() -> None:
    """The uncontrolled cell's definition, pinned literally.

    Written out rather than compared to a copy, so that changing the regime
    requires changing this test and saying why in the diff.
    """
    regime = REGIME_REDIS_KILL_PREACK
    assert regime.name == "redis-kill-preack"
    assert regime.crash_probability == 0.0
    assert regime.iterates_crash_points is False
    assert regime.redis_kill_point == "after_intent_before_barrier"
    assert regime.redis_kill_delay_ms == 0
    assert regime.redis_kill_executions == 1
    assert regime.runs_per_cell == 30
    assert regime.executions_per_run == 1
    assert regime.workers == 1
    # The restriction WS-3 exists to lift -- lifted in the NEW regime only.
    assert regime.endpoints == ("payments", "ledger_postings")


def test_the_new_regime_reaches_all_three_capability_classes() -> None:
    assert REGIME_REDIS_PAUSE_KILL_PREACK.endpoints == (
        "payments",
        "notifications",
        "ledger_postings",
    )


def test_the_two_regimes_share_the_fault_point_and_differ_in_name() -> None:
    """Same instruction boundary, same class of fault; different experiment."""
    assert (
        REGIME_REDIS_PAUSE_KILL_PREACK.redis_kill_point
        == REGIME_REDIS_KILL_PREACK.redis_kill_point
    )
    assert REGIME_REDIS_PAUSE_KILL_PREACK.name != REGIME_REDIS_KILL_PREACK.name
    names = [regime.name for regime in REGIMES]
    assert len(names) == len(set(names)), "regime names key the results cells"


def test_the_mechanism_resolves_from_its_name_and_refuses_anything_else() -> None:
    assert redis_kill.killer_for(None) is redis_kill.kill_redis
    assert redis_kill.killer_for("") is redis_kill.kill_redis
    assert redis_kill.killer_for(redis_kill.MECHANISM_KILL) is redis_kill.kill_redis
    assert (
        redis_kill.killer_for(redis_kill.MECHANISM_PAUSE_THEN_KILL)
        is redis_kill.pause_then_kill
    )


def test_an_unknown_mechanism_raises_rather_than_falling_back() -> None:
    """A typo must not deliver the uncontrolled fault into a controlled root.

    Defaulting here is the fail-open direction: the results directory would say
    the fault was controlled, the run log would not contradict it, and the
    number would be wrong in the direction that flatters the result.
    """
    with pytest.raises(ValueError) as caught:
        redis_kill.killer_for("pause_then_kill")  # underscores, not hyphens
    assert "pause_then_kill" in str(caught.value)


def test_the_injector_selects_the_mechanism_from_the_environment() -> None:
    from experiments.harness.crash_points import CrashPoint, resolve_crash_point

    injector = redis_kill.RedisKillInjector.from_environment(
        environ={
            redis_kill.REDIS_KILL_POINT_VARIABLE: "after_intent_before_barrier",
            redis_kill.REDIS_KILL_CONTAINER_VARIABLE: "aep-phase2-redis72",
            redis_kill.REDIS_FAULT_MECHANISM_VARIABLE: (
                redis_kill.MECHANISM_PAUSE_THEN_KILL
            ),
        },
        resolver=resolve_crash_point,
    )
    assert injector is not None
    assert injector.killer is redis_kill.pause_then_kill
    assert injector.plan.point is CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER


def test_an_explicitly_supplied_killer_is_not_overridden() -> None:
    """Tests inject a fake killer; the environment must not replace it."""
    from experiments.harness.crash_points import resolve_crash_point

    def fake(container: str) -> dict:
        return {"issued": True, "returncode": 0, "command_ms": 0}

    injector = redis_kill.RedisKillInjector.from_environment(
        environ={
            redis_kill.REDIS_KILL_POINT_VARIABLE: "after_intent_before_barrier",
            redis_kill.REDIS_KILL_CONTAINER_VARIABLE: "c",
            redis_kill.REDIS_FAULT_MECHANISM_VARIABLE: (
                redis_kill.MECHANISM_PAUSE_THEN_KILL
            ),
        },
        resolver=resolve_crash_point,
        killer=fake,
    )
    assert injector is not None
    assert injector.killer is fake


def test_pause_then_kill_issues_the_kill_even_if_the_pause_fails(monkeypatch) -> None:
    """A failed freeze is the uncontrolled fault, not the absence of one.

    The alternative -- skipping the kill when the pause failed -- would let the
    injector silently decide not to inject, and the run would be counted as a
    fault-bearing run that carried no fault.
    """
    calls: list[list[str]] = []

    class _Result:
        def __init__(self, code: int) -> None:
            self.returncode = code
            self.stderr = "boom" if code else ""

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return _Result(1 if argv[1] == "pause" else 0)

    monkeypatch.setattr(redis_kill.subprocess, "run", fake_run)
    record = redis_kill.pause_then_kill("aep-phase2-redis72")

    assert [argv[1] for argv in calls] == ["pause", "kill"]
    assert record["paused"] is False
    assert record["issued"] is True
    assert record["mechanism"] == redis_kill.MECHANISM_PAUSE_THEN_KILL
    assert "pause_ms" in record and "total_ms" in record
