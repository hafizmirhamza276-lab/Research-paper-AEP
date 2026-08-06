"""Anti-drift gates over the system descriptors and the crash-point mapping.

Every claim in ``contract.py``'s table is a claim the paper will repeat, and a
table that has drifted from the code it describes is worse than no table. The
tests here check the descriptors against the implementations by *executing*
them, not by reading them: "B0 takes no lease" is asserted by running B0 and
looking at Redis, and "B4 has a pre-dispatch record" by running B4 and looking
at its history.
"""

from __future__ import annotations

import pytest

from aep_core.core.intent_workflow import ConnectorPolicy

from experiments.baselines import (
    b0_naive_retry,
    b1_lease_only,
    b2_cas_only,
    b4_durable_workflow,
)
from experiments.baselines.contract import (
    FLAGGED_CLASSES,
    SYSTEMS,
    OutcomeClass,
    ResumePolicy,
    SystemId,
    descriptor_for,
    resolve_system,
)
from experiments.baselines.crash_points import (
    ROADMAP_TO_BASELINE,
    BaselineCrashPoint,
    CrashPointNotApplicable,
    applicable_roadmap_points,
    crash_point_enum_for,
    resolve_for_system,
    uses_aep_crash_points,
)
from experiments.baselines.tests.conftest import RecordingConnector, applied
from experiments.baselines.tests.helpers import item_for
from experiments.harness.crash_points import (
    ROADMAP_CRASH_POINTS,
    CrashPoint,
)
from experiments.harness.workload import harness_profile, request_for

POLICY = ConnectorPolicy(client_timeout_seconds=1.0, lock_ttl_seconds=20)


def test_every_system_has_a_descriptor() -> None:
    assert set(SYSTEMS) == set(SystemId)


def test_only_declared_ambiguity_counts_as_flagged() -> None:
    """The headline metric's definition, pinned.

    If ``UNVERIFIED_FAILURE`` ever joined this set, every baseline's undetected
    duplicate rate would collapse to zero and the comparison would evaporate.
    """
    assert FLAGGED_CLASSES == frozenset({OutcomeClass.DECLARED_AMBIGUOUS})


def test_only_the_intent_systems_can_declare_ambiguity() -> None:
    """The property the whole comparison rests on."""
    can = {
        system
        for system, descriptor in SYSTEMS.items()
        if descriptor.can_declare_ambiguity
    }
    assert can == {SystemId.B3_INTENT_NO_BARRIER, SystemId.AEP_FULL}


def test_only_the_intent_systems_dispatch_at_most_once() -> None:
    at_most_once = {
        system
        for system, descriptor in SYSTEMS.items()
        if descriptor.dispatches_at_most_once
    }
    assert at_most_once == {SystemId.B3_INTENT_NO_BARRIER, SystemId.AEP_FULL}


def test_the_ablation_ladder_is_monotone() -> None:
    """B0 < B1 < B2 in protections, and B3 differs from AEP in one bit only.

    Stated as a test because the value of an ablation study is entirely in the
    ladder being a ladder: if B2 lost a protection B1 had, no difference
    between them could be attributed to the protection that was added.
    """
    b0, b1, b2 = (
        descriptor_for(SystemId.B0_NAIVE_RETRY),
        descriptor_for(SystemId.B1_LEASE_ONLY),
        descriptor_for(SystemId.B2_CAS_ONLY),
    )
    assert (b0.uses_lease, b1.uses_lease, b2.uses_lease) == (False, True, True)
    assert (
        b0.uses_fenced_state_writes,
        b1.uses_fenced_state_writes,
        b2.uses_fenced_state_writes,
    ) == (False, False, True)
    assert not any(
        item.writes_pre_dispatch_record for item in (b0, b1, b2)
    )

    b3 = descriptor_for(SystemId.B3_INTENT_NO_BARRIER)
    aep = descriptor_for(SystemId.AEP_FULL)
    differences = {
        field
        for field in vars(b3)
        if getattr(b3, field) != getattr(aep, field)
    }
    assert differences == {"system", "label", "description", "uses_durability_barrier"}


def test_systems_without_a_pre_dispatch_record_reexecute() -> None:
    """The modelling decision, asserted rather than buried in prose."""
    for descriptor in SYSTEMS.values():
        if descriptor.writes_pre_dispatch_record and descriptor.has_recovery_service:
            assert descriptor.resume_policy is ResumePolicy.NEXT_EXECUTION
        else:
            assert descriptor.resume_policy is ResumePolicy.REEXECUTE_CRASHED


def test_resolve_system_refuses_silence() -> None:
    with pytest.raises(KeyError):
        resolve_system(None)
    with pytest.raises(KeyError):
        resolve_system("B9_WISHFUL_THINKING")
    assert resolve_system("AEP_FULL") is SystemId.AEP_FULL


# ---------------------------------------------------------------------------
# The crash-point mapping
# ---------------------------------------------------------------------------


def test_the_aep_systems_use_the_aep_vocabulary() -> None:
    for system in (SystemId.B3_INTENT_NO_BARRIER, SystemId.AEP_FULL):
        assert uses_aep_crash_points(system)
        assert crash_point_enum_for(system) is CrashPoint
    for system in ROADMAP_TO_BASELINE:
        assert not uses_aep_crash_points(system)
        assert crash_point_enum_for(system) is BaselineCrashPoint


def test_every_baseline_maps_every_roadmap_name() -> None:
    """No roadmap crash point may be silently absent from a mapping."""
    for system, mapping in ROADMAP_TO_BASELINE.items():
        assert set(mapping) == set(ROADMAP_CRASH_POINTS), system


def test_a_missing_moment_is_refused_not_aliased() -> None:
    """The honesty gate: an inapplicable cell raises rather than substituting."""
    with pytest.raises(CrashPointNotApplicable):
        resolve_for_system(SystemId.B0_NAIVE_RETRY, "after_intent_before_barrier")
    assert "after_intent_before_barrier" not in applicable_roadmap_points(
        SystemId.B0_NAIVE_RETRY
    )
    assert "after_intent_before_barrier" in applicable_roadmap_points(
        SystemId.B4_DURABLE_WORKFLOW
    )
    assert "after_intent_before_barrier" in applicable_roadmap_points(
        SystemId.AEP_FULL
    )


def test_no_crash_point_selected_is_not_an_error() -> None:
    for system in SystemId:
        assert resolve_for_system(system, None) is None
        assert resolve_for_system(system, "") is None


def test_a_typo_is_a_failure_for_every_system() -> None:
    for system in SystemId:
        with pytest.raises(KeyError):
            resolve_for_system(system, "mid_dispach")


def test_the_checkpoint_names_the_baselines_reach_are_the_declared_ones() -> None:
    """Parsed from the baseline sources, in the spirit of the harness's own gate.

    ``experiments/harness/tests/test_crash_points.py`` parses ``aep_core`` for
    its ``_checkpoint`` calls so that a rename fails a test rather than raising
    ``KeyError`` inside a worker mid-run. The same hazard exists here, so the
    same gate does.
    """
    import re
    from pathlib import Path

    pattern = re.compile(r'_checkpoint\(\s*"([A-Z0-9_]+)"')
    root = Path(__file__).resolve().parents[1]
    reached: set[str] = set()
    for module in ("b0_naive_retry.py", "b1_lease_only.py", "b2_cas_only.py", "b4_durable_workflow.py"):
        reached.update(pattern.findall((root / module).read_text(encoding="utf-8")))

    declared = {member.name for member in BaselineCrashPoint}
    assert reached <= declared, sorted(reached - declared)
    # Every declared point must be reachable by at least one baseline, or it
    # is a crash point the matrix could select and no system would ever hit.
    assert declared == reached


# ---------------------------------------------------------------------------
# Descriptors versus behaviour
# ---------------------------------------------------------------------------


async def test_declared_lease_use_matches_observed_lease_use(
    redis_client, lock_manager, storage_adapter, cjson_available
) -> None:
    """Run each baseline and watch Redis, rather than trusting the table."""
    if not cjson_available:
        pytest.skip("B2 needs a Redis with cjson")

    observations: dict[SystemId, bool] = {}

    for system in (
        SystemId.B0_NAIVE_RETRY,
        SystemId.B1_LEASE_ONLY,
        SystemId.B2_CAS_ONLY,
        SystemId.B4_DURABLE_WORKFLOW,
    ):
        item = item_for()
        connector = RecordingConnector(script=[applied()])
        seen: list[bool] = []

        async def probe() -> None:
            seen.append(
                bool(await redis_client.exists(f"aep:lock:{item.execution_id}"))
            )

        runner = _build(
            system,
            redis_client=redis_client,
            lock_manager=lock_manager,
            storage_adapter=storage_adapter,
            connector=connector,
        )
        # The lease, if any, is held while the request is on the wire. That is
        # the only instant at which its presence means anything.
        connector.on_transmit = lambda index: None
        holder: list[bool] = []
        original = connector.transmit

        async def transmit(**kwargs):
            holder.append(
                bool(await redis_client.exists(f"aep:lock:{item.execution_id}"))
            )
            return await original(**kwargs)

        connector.transmit = transmit  # type: ignore[method-assign]
        await runner.execute(
            execution_id=item.execution_id,
            step_id=item.step_id,
            request=request_for(item),
        )
        observations[system] = any(holder)

    for system, held in observations.items():
        assert held is descriptor_for(system).uses_lease, system


def _build(system, *, redis_client, lock_manager, storage_adapter, connector):
    common = {
        "redis_client": redis_client,
        "connector": connector,
        "profile": harness_profile(),
        "policy": POLICY,
    }
    if system is SystemId.B0_NAIVE_RETRY:
        return b0_naive_retry.NaiveRetryRunner(**common)
    if system is SystemId.B1_LEASE_ONLY:
        return b1_lease_only.LeaseOnlyRunner(lock_manager=lock_manager, **common)
    if system is SystemId.B2_CAS_ONLY:
        return b2_cas_only.CasOnlyRunner(
            lock_manager=lock_manager, storage_adapter=storage_adapter, **common
        )
    if system is SystemId.B4_DURABLE_WORKFLOW:
        return b4_durable_workflow.DurableWorkflowRunner(
            lock_manager=lock_manager, barrier=_PassthroughBarrier(), **common
        )
    raise AssertionError(f"no local builder for {system}")


class _PassthroughBarrier:
    test_only = False

    async def validate_startup(self, redis_client):
        return None

    async def confirm_durable(self, connection, timeout_ms: int) -> bool:
        return True
