"""The workload is a pure function of the run's seed.

Two reasons this matters more here than in an ordinary load generator.

*Reproducibility.* Amendment C4 requires every seed in the run log. A seed is
only worth recording if replaying it reproduces the same executions, with the
same identifiers, in the same order, including which of them were selected to
crash.

*Read-back under ``ORACLE_FINGERPRINT``.* A caller reconciling after a crash
has only a ``ReconciliationContext`` -- no payload. It can still describe the
mutation it made, because the mutation was derived from the execution id in
the first place. That is realistic (a real system stores what it sent) and it
is what lets the sensitivity variant be measured at all.
"""

from __future__ import annotations

import uuid

import pytest

from aep_core.core.validation import validate_execution_id
from experiments.harness.config import RunConfig
from experiments.harness.workload import (
    harness_profile,
    identity_descriptor,
    plan_workload,
    request_for,
)


def config(**overrides) -> RunConfig:
    defaults = dict(
        run_id="run-test",
        seed=20260805,
        workers=3,
        executions_per_worker=4,
        endpoint="payments",
        mock_api_config_path="x.yaml",
        mock_api_base_url="http://127.0.0.1:8099",
        redis_url="redis://127.0.0.1:6381/15",
        results_root="experiments/results",
    )
    defaults.update(overrides)
    return RunConfig(**defaults)


# ===========================================================================
# Determinism
# ===========================================================================


def test_the_same_seed_produces_the_identical_plan():
    assert plan_workload(config()) == plan_workload(config())


def test_a_different_seed_produces_a_different_plan():
    assert plan_workload(config(seed=1)) != plan_workload(config(seed=2))


def test_a_different_run_id_produces_different_executions():
    """Two runs of one configuration must not collide in the Redis keyspace."""
    first = {item.execution_id for item in plan_workload(config(run_id="a"))}
    second = {item.execution_id for item in plan_workload(config(run_id="b"))}

    assert first.isdisjoint(second)


def test_the_plan_covers_every_worker_and_execution_exactly_once():
    plan = plan_workload(config(workers=3, executions_per_worker=4))

    assert len(plan) == 12
    assert len({item.execution_id for item in plan}) == 12
    assert sorted((item.worker_index, item.execution_index) for item in plan) == [
        (worker, index) for worker in range(3) for index in range(4)
    ]


# ===========================================================================
# The identifiers the protocol will accept
# ===========================================================================


def test_every_execution_id_is_a_canonical_uuid4():
    """``aep_core.core.validation`` rejects anything else at the boundary."""
    for item in plan_workload(config()):
        assert validate_execution_id(item.execution_id) == item.execution_id
        assert uuid.UUID(item.execution_id).version == 4


def test_every_execution_targets_a_distinct_resource():
    """So a duplicate group in the oracle means a duplicated *effect*.

    If two executions shared a target and identity content they would share a
    fingerprint, and the oracle would report a duplicate for two mutations the
    caller genuinely intended. Distinct targets keep the headline metric
    measuring what it claims to measure.
    """
    plan = plan_workload(config(workers=3, executions_per_worker=4))

    assert len({item.target for item in plan}) == len(plan)


# ===========================================================================
# Crash selection
# ===========================================================================


def test_crash_selection_is_reproducible():
    first = plan_workload(config(crash_probability=0.5))
    second = plan_workload(config(crash_probability=0.5))

    assert [item.crash_selected for item in first] == [
        item.crash_selected for item in second
    ]


def test_probability_one_selects_every_execution():
    assert all(item.crash_selected for item in plan_workload(config(crash_probability=1.0)))


def test_probability_zero_selects_none():
    assert not any(
        item.crash_selected for item in plan_workload(config(crash_probability=0.0))
    )


def test_an_intermediate_probability_selects_some_of_each():
    plan = plan_workload(config(workers=10, executions_per_worker=10, crash_probability=0.5))
    selected = [item.crash_selected for item in plan]

    assert any(selected) and not all(selected)


def test_crash_selection_does_not_shift_the_identifiers():
    """A run with and without crashes must exercise the same executions."""
    with_crashes = plan_workload(config(crash_probability=1.0))
    without = plan_workload(config(crash_probability=0.0))

    assert [item.execution_id for item in with_crashes] == [
        item.execution_id for item in without
    ]


# ===========================================================================
# The request, and its identity descriptor
# ===========================================================================


def test_the_request_is_accepted_by_the_endpoint_profile():
    from aep_core.core.request_binding import build_exact_request_bytes

    item = plan_workload(config())[0]

    envelope = build_exact_request_bytes(harness_profile(), request_for(item))

    assert item.target.encode() in envelope


def test_the_workload_carries_no_protected_material():
    """A read-back must never require re-transmitting a credential."""
    item = plan_workload(config())[0]

    descriptor = identity_descriptor(item)

    assert "protected_fields" not in descriptor
    assert set(descriptor) == {
        "connector_operation",
        "operation_version",
        "target",
        "public_fields",
    }


def test_the_identity_descriptor_fingerprints_as_the_mutation_did():
    """The descriptor must reach the oracle's Definition 1 identically.

    This is the property the ``ORACLE_FINGERPRINT`` read-back rests on: the
    caller describes what it sent, and the provider's own identity function
    lands on the same fingerprint it recorded when it applied the mutation.
    """
    import json

    from aep_core.core.request_binding import build_exact_request_bytes
    from experiments.mock_api.fingerprint import mutation_fingerprint

    item = plan_workload(config())[0]
    envelope = json.loads(build_exact_request_bytes(harness_profile(), request_for(item)))
    identity_fields = ("action", "amount_minor")

    as_sent = mutation_fingerprint(
        method="POST",
        endpoint="payments",
        envelope=envelope,
        identity_fields=identity_fields,
    )
    as_described = mutation_fingerprint(
        method="POST",
        endpoint="payments",
        envelope=identity_descriptor(item),
        identity_fields=identity_fields,
    )

    assert as_sent == as_described


def test_two_executions_do_not_share_a_fingerprint():
    import json

    from aep_core.core.request_binding import build_exact_request_bytes
    from experiments.mock_api.fingerprint import mutation_fingerprint

    fingerprints = {
        mutation_fingerprint(
            method="POST",
            endpoint="payments",
            envelope=json.loads(
                build_exact_request_bytes(harness_profile(), request_for(item))
            ),
            identity_fields=("action", "amount_minor"),
        )
        for item in plan_workload(config(workers=3, executions_per_worker=4))
    }

    assert len(fingerprints) == 12


def test_the_identity_fields_the_workload_uses_are_the_ones_it_declares():
    """A drift here would make every ORACLE_FINGERPRINT read-back miss."""
    from experiments.harness.workload import IDENTITY_FIELDS

    item = plan_workload(config())[0]
    names = {entry["name"] for entry in identity_descriptor(item)["public_fields"]}

    assert set(IDENTITY_FIELDS) <= names
