"""Every refusal in the write-ahead composition's own configuration.

Coverage headroom for ``aep_core/core/intent_workflow.py``, which
``reports/phase-report-2b-session1-2026-08-05.md`` H.1 asked for before Session
2 added code to it. These are not filler: each branch below is a fail-closed
refusal that exists because the corresponding misconfiguration would silently
weaken a safety property rather than break loudly.

``ConnectorPolicy`` is where AEP's Timeout Invariant lives --
``T_client <= T_lock - Buffer``, ``Buffer >= 15s`` -- and where the bounded
reconciliation budget that makes P3 terminate is declared. A policy that
accepted a negative backoff, or overlapping success and failure evidence, would
produce a runner that looked configured and was not.
"""

from __future__ import annotations

import pytest

from aep_core.core.durability import FakeDurabilityBarrier
from aep_core.core.intent_workflow import (
    ConnectorPolicy,
    WriteAheadRunner,
    WriteAheadWorkflowError,
)
from aep_core.core.intents import IntentLedgerStore
from tests.mock_connector import CrashPoint, MockConnectorHarness
from tests.request_binding_helpers import (
    DEFAULT_CONNECTOR,
    # Aliased: pytest collects any module-level ``test_*`` name as a test, and
    # a helper that returns a service would be reported as a returning test.
    test_binding_service as _binding_service,
)


def policy(**overrides) -> ConnectorPolicy:
    values = {
        "client_timeout_seconds": 1.0,
        "settlement_lag_seconds": 0.0,
        "buffer_margin_seconds": 15.0,
        "lock_ttl_seconds": 30,
        "durability_timeout_ms": 100,
    }
    values.update(overrides)
    return ConnectorPolicy(**values)


# ===========================================================================
# The timing invariant
# ===========================================================================


@pytest.mark.parametrize("value", [0, -1, -0.5])
def test_a_non_positive_client_timeout_is_refused(value):
    with pytest.raises(ValueError, match="client_timeout_seconds"):
        policy(client_timeout_seconds=value)


def test_a_negative_settlement_lag_is_refused():
    with pytest.raises(ValueError, match="settlement_lag_seconds"):
        policy(settlement_lag_seconds=-0.1)


def test_a_buffer_below_fifteen_seconds_is_refused():
    """The buffer covers clock skew, jitter and renewal latency."""
    with pytest.raises(ValueError, match="buffer_margin_seconds"):
        policy(buffer_margin_seconds=14.999)


def test_a_client_timeout_that_can_outlive_the_lease_is_refused():
    """``T_client <= T_lock - Buffer``: the whole Timeout Invariant."""
    with pytest.raises(ValueError, match="T_client"):
        policy(client_timeout_seconds=16.0, lock_ttl_seconds=30)


def test_the_boundary_of_the_timeout_invariant_is_admissible():
    """Exactly at the limit is legal; one step past it is not."""
    assert policy(client_timeout_seconds=15.0, lock_ttl_seconds=30)


# ===========================================================================
# The bounded reconciliation budget (P3)
# ===========================================================================


@pytest.mark.parametrize("value", [0, -1])
def test_a_non_positive_durability_timeout_is_refused(value):
    with pytest.raises(ValueError, match="durability_timeout_ms"):
        policy(durability_timeout_ms=value)


@pytest.mark.parametrize("value", [0, -3])
def test_a_non_positive_reconciliation_attempt_cap_is_refused(value):
    with pytest.raises(ValueError, match="max_reconciliation_attempts"):
        policy(max_reconciliation_attempts=value)


@pytest.mark.parametrize("value", [0, -1.0])
def test_a_non_positive_reconciliation_duration_cap_is_refused(value):
    with pytest.raises(ValueError, match="max_reconciliation_duration"):
        policy(max_reconciliation_duration_seconds=value)


@pytest.mark.parametrize(
    ("field", "value"),
    [("backoff_base_seconds", -1.0), ("backoff_cap_seconds", -1.0)],
)
def test_a_negative_backoff_is_refused(field, value):
    with pytest.raises(ValueError, match="backoff"):
        policy(**{field: value})


@pytest.mark.parametrize("value", [0, -2])
def test_a_non_positive_lease_attempt_count_is_refused(value):
    with pytest.raises(ValueError, match="lease_acquire_attempts"):
        policy(lease_acquire_attempts=value)


def test_a_negative_lease_backoff_cap_is_refused():
    with pytest.raises(ValueError, match="lease_backoff_cap_seconds"):
        policy(lease_backoff_cap_seconds=-0.1)


def test_the_backoff_ceiling_requires_a_positive_attempt_number():
    with pytest.raises(ValueError, match="attempt_number"):
        policy().backoff_ceiling(0)


# ===========================================================================
# The evidence vocabulary
# ===========================================================================


def test_a_connector_that_declares_no_success_evidence_is_refused():
    with pytest.raises(ValueError, match="definitive success evidence"):
        policy(definitive_success_evidence=frozenset())


def test_a_connector_that_declares_no_failure_evidence_is_refused():
    with pytest.raises(ValueError, match="definitive failure evidence"):
        policy(definitive_failure_evidence=frozenset())


def test_overlapping_success_and_failure_evidence_is_refused():
    """One string meaning both would make every classification a coin toss."""
    with pytest.raises(ValueError, match="overlap"):
        policy(
            definitive_success_evidence=frozenset({"DONE", "BOTH"}),
            definitive_failure_evidence=frozenset({"NOPE", "BOTH"}),
        )


# ===========================================================================
# The runner's own composition checks
# ===========================================================================


def _runner(redis_client, lock_manager, harness, **overrides):
    arguments = {
        "store": IntentLedgerStore(redis_client),
        "lock_manager": lock_manager,
        "connector": harness.connector,
        "barrier": FakeDurabilityBarrier(),
        "policy": policy(),
        "connector_name": DEFAULT_CONNECTOR,
        "binding_service": _binding_service(),
        "allow_test_barrier": True,
        "allow_test_dispatch": True,
    }
    arguments.update(overrides)
    return WriteAheadRunner(**arguments)


@pytest.mark.asyncio
async def test_a_runner_whose_profile_names_another_operation_is_refused(
    redis_client, lock_manager
):
    harness = MockConnectorHarness()

    with pytest.raises(ValueError, match="connector operation"):
        _runner(redis_client, lock_manager, harness, connector_name="something.else")


@pytest.mark.asyncio
async def test_a_connector_whose_identity_differs_from_the_profile_is_refused(
    redis_client, lock_manager
):
    """The connector and the binding must describe the same endpoint."""
    harness = MockConnectorHarness()
    harness.connector.endpoint_profile_version = "99"

    with pytest.raises(ValueError, match="connector identity/profile"):
        _runner(redis_client, lock_manager, harness)


@pytest.mark.asyncio
async def test_an_intent_ttl_that_cannot_outlive_reconciliation_is_refused(
    redis_client, lock_manager
):
    """Escalations must survive the budget that produced them, plus retention."""
    harness = MockConnectorHarness()

    with pytest.raises(ValueError, match="intent TTL"):
        _runner(
            redis_client,
            lock_manager,
            harness,
            policy=policy(max_reconciliation_duration_seconds=40 * 24 * 60 * 60),
        )


@pytest.mark.asyncio
async def test_a_crash_injector_without_its_vocabulary_is_a_hard_error(
    redis_client, lock_manager
):
    """Silently skipping the checkpoint would produce a crash-free crash run."""
    harness = MockConnectorHarness()
    runner = _runner(
        redis_client,
        lock_manager,
        harness,
        crash_injector=harness.crashes,
        crash_point_enum=None,
    )

    with pytest.raises(RuntimeError, match="crash_point_enum"):
        await runner._checkpoint(CrashPoint.DURING_INTENT_CAS.value)


@pytest.mark.asyncio
async def test_a_barrier_without_startup_validation_cannot_be_used_untested(
    redis_client, lock_manager
):
    """A production-mode barrier must offer the check the mode depends on."""

    class _NoStartupBarrier:
        test_only = False

        async def confirm_durable(self, connection, timeout_ms):
            return True

    harness = MockConnectorHarness()
    runner = _runner(
        redis_client,
        lock_manager,
        harness,
        barrier=_NoStartupBarrier(),
        allow_test_barrier=False,
    )

    with pytest.raises(WriteAheadWorkflowError, match="startup validation"):
        await runner.validate_startup()
