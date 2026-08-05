"""EVALUATION mode, end to end, against a real MockLegacyAPI process.

Amendment B4, closing F4 of ``reports/phase-report-1b-2026-08-05.md``:

    *"EVALUATION mode is enforced but never exercised end-to-end. [...] no
    test dispatches a real mutation in EVALUATION mode. [...] So the
    composition is proven admissible, not proven functional."*

What follows dispatches one real mutation through the real
``WriteAheadRunner`` -- real Redis 7.2 with AOF, the real WAITAOF durability
barrier, the real evaluation request vault, and **no** ``allow_test_dispatch``
or ``allow_test_barrier`` -- to a MockLegacyAPI in its own OS process, and
then asserts the ground-truth ledger recorded it.

Scope is deliberately one dispatch. Porting the 22-case crash-boundary matrix
to EVALUATION mode is Session 2/3 work; this retires "admissible, not
functional" at the smallest scope that actually retires it.
"""

from __future__ import annotations

import os
import uuid

import pytest

from aep_core.core.connector_contract import (
    ReadbackResult,
    ReconciliationCapability,
    declared_capability,
)
from aep_core.core.durability import RealWaitAofDurabilityBarrier
from aep_core.core.intent_workflow import (
    ConnectorPolicy,
    DispatchMode,
    WriteAheadRunner,
)
from aep_core.core.intents import IntentLedgerStore, IntentStatus
from aep_core.core.request_binding import ReconciliationContext
from aep_core.core.request_vault import EvaluationRedisRequestVault
from aep_core.core.storage import AEPExecutionState, AEPStatus
from experiments.mock_api.client import MockLegacyApiConnector
from experiments.mock_api.ledger import GroundTruthLedger
from experiments.mock_api.tests.server_harness import MockApiProcess, write_config
from tests.request_binding_helpers import (
    DEFAULT_CONNECTOR,
    test_binding_service as _binding_service,
    test_request as _request,
)

pytestmark = [
    pytest.mark.redis72_integration,
    pytest.mark.skipif(
        os.environ.get("AEP_PHASE2_REDIS_INTEGRATION") != "1",
        reason=(
            "set AEP_PHASE2_REDIS_INTEGRATION=1 and REDIS_URL to the "
            "dedicated Redis 7.2+ AOF DB 15"
        ),
    ),
]

ENDPOINT = "payments"


def _mock_api_config(tmp_path, *, capability: ReconciliationCapability) -> dict:
    return {
        "config_version": "aep.mock-legacy-api.config/1",
        "seed": 20260805,
        "ledger_path": str(tmp_path / "ground_truth.sqlite3"),
        "endpoints": {
            ENDPOINT: {
                "response_class": capability.value,
                "identity_fields": ["action", "amount_minor"],
            }
        },
    }


@pytest.fixture
def mock_api(tmp_path):
    config = write_config(
        tmp_path / "mock-api.yaml",
        _mock_api_config(
            tmp_path, capability=ReconciliationCapability.AUTHORITATIVE_READBACK
        ),
    )
    with MockApiProcess(config, log_directory=tmp_path) as server:
        yield server


@pytest.fixture
async def connector(mock_api):
    instance = MockLegacyApiConnector(
        base_url=mock_api.base_url,
        endpoint=ENDPOINT,
        reconciliation_capability=(
            ReconciliationCapability.AUTHORITATIVE_READBACK
        ),
        connector_identity="mock-connector",
        connector_operation=DEFAULT_CONNECTOR,
        endpoint_profile_id="mock-endpoint",
        endpoint_profile_version="1",
    )
    try:
        yield instance
    finally:
        await instance.aclose()


def _policy() -> ConnectorPolicy:
    return ConnectorPolicy(
        client_timeout_seconds=5.0,
        settlement_lag_seconds=0,
        buffer_margin_seconds=15,
        lock_ttl_seconds=30,
        durability_timeout_ms=2_000,
        lease_acquire_attempts=1,
    )


def _evaluation_runner(redis_client, lock_manager, connector) -> WriteAheadRunner:
    """The EVALUATION composition, with every test affordance withheld."""
    return WriteAheadRunner(
        store=IntentLedgerStore(redis_client),
        lock_manager=lock_manager,
        connector=connector,
        barrier=RealWaitAofDurabilityBarrier(),
        policy=_policy(),
        connector_name=DEFAULT_CONNECTOR,
        binding_service=_binding_service(
            vault=EvaluationRedisRequestVault(
                redis_client=redis_client,
                encryption_keys={"eval-vault-key-1": b"e" * 32},
                active_key_id="eval-vault-key-1",
            )
        ),
        mode=DispatchMode.EVALUATION,
    )


async def _seed(storage_adapter, lock_manager) -> str:
    execution_id = str(uuid.uuid4())
    token = await lock_manager.acquire_lock(execution_id, ttl_seconds=60)
    assert token
    await storage_adapter.save_state(
        AEPExecutionState(execution_id=execution_id, status=AEPStatus.IDLE),
        expected_version=0,
        lock_token=token,
        ttl_seconds=3600,
    )
    assert await lock_manager.release_lock(execution_id, token)
    return execution_id


def _ledger(mock_api: MockApiProcess) -> GroundTruthLedger:
    import yaml

    document = yaml.safe_load(mock_api.config_path.read_text(encoding="utf-8"))
    ledger = GroundTruthLedger(document["ledger_path"])
    ledger.initialise()
    return ledger


# ===========================================================================
# The composition really is production-shaped
# ===========================================================================


@pytest.mark.asyncio
async def test_the_runner_carries_no_test_authorisation(
    redis_client, lock_manager, connector
):
    runner = _evaluation_runner(redis_client, lock_manager, connector)

    assert runner.mode is DispatchMode.EVALUATION
    assert runner.allow_test_dispatch is False
    assert runner.allow_test_barrier is False
    assert getattr(connector, "test_only") is False
    assert getattr(runner.binding_service.vault, "test_only") is False
    assert getattr(runner.barrier, "test_only", False) is False
    await runner.validate_startup()


def test_the_connector_declares_a_contract_capability(connector):
    """``declared_capability`` is the production gate a connector must pass."""
    assert (
        declared_capability(connector)
        is ReconciliationCapability.AUTHORITATIVE_READBACK
    )


# ===========================================================================
# The dispatch itself
# ===========================================================================


@pytest.mark.asyncio
async def test_evaluation_mode_dispatches_a_real_mutation_to_the_mock_api(
    redis_client, storage_adapter, lock_manager, connector, mock_api
):
    """F4, retired: the composition is functional, not merely admissible."""
    execution_id = await _seed(storage_adapter, lock_manager)
    runner = _evaluation_runner(redis_client, lock_manager, connector)

    resolved = await runner.execute(
        execution_id=execution_id,
        step_id="charge-card",
        request=_request(target="account-redacted-17"),
    )

    assert resolved.status is IntentStatus.FIRED_CONFIRMED
    assert [entry.new_state for entry in resolved.transitions] == [
        IntentStatus.ABOUT_TO_FIRE,
        IntentStatus.FIRED_CONFIRMED,
    ]

    ledger = _ledger(mock_api)
    try:
        (applied,) = ledger.applied_mutations()
        assert applied.endpoint == ENDPOINT
        assert applied.target == "account-redacted-17"
        assert applied.delivery_index == 1
        # The protocol's own fingerprint travelled as an opaque reference.
        assert applied.client_reference == resolved.request_fingerprint
        # And the oracle's fingerprint is its own, computed from the wire.
        assert applied.fingerprint != applied.client_reference

        assert ledger.duplicate_groups() == ()
        assert ledger.consistency_report().is_consistent
        assert ledger.simulated_state()[0].effect_count == 1
    finally:
        ledger.close()


@pytest.mark.asyncio
async def test_one_execution_produces_exactly_one_applied_mutation(
    redis_client, storage_adapter, lock_manager, connector, mock_api
):
    """The baseline every duplicate rate is measured against."""
    for _ in range(3):
        execution_id = await _seed(storage_adapter, lock_manager)
        await _evaluation_runner(redis_client, lock_manager, connector).execute(
            execution_id=execution_id,
            step_id="charge-card",
            request=_request(target="account-redacted-17"),
        )

    ledger = _ledger(mock_api)
    try:
        # Three separate executions of the same request content are three
        # applications of one mutation: the oracle reports two duplicates,
        # which is correct -- they are genuinely three effects on the
        # external world, and only the protocol's own ledger knows they were
        # three intended executions rather than one retried.
        assert len(ledger.applied_mutations()) == 3
        (group,) = ledger.duplicate_groups()
        assert group.applications == 3
        assert ledger.consistency_report().is_consistent
    finally:
        ledger.close()


@pytest.mark.asyncio
async def test_the_applied_mutation_reads_back_as_applied(
    redis_client, storage_adapter, lock_manager, connector, mock_api
):
    """Recovery's evidence path, over the same real socket."""
    execution_id = await _seed(storage_adapter, lock_manager)
    resolved = await _evaluation_runner(
        redis_client, lock_manager, connector
    ).execute(
        execution_id=execution_id,
        step_id="charge-card",
        request=_request(target="account-redacted-17"),
    )

    observation = await connector.read_back(
        context=ReconciliationContext(
            execution_id=execution_id,
            step_id="charge-card",
            intent_id=resolved.intent_id,
            correlation_id=resolved.correlation_id,
            connector_operation=DEFAULT_CONNECTOR,
            redacted_target="account-redacted-17",
            request_fingerprint=resolved.request_fingerprint,
            attempt_count=0,
        ),
        readback_timeout=5.0,
    )

    assert observation.result is ReadbackResult.APPLIED


@pytest.mark.asyncio
async def test_a_mutation_that_was_never_dispatched_reads_back_as_not_applied(
    redis_client, lock_manager, connector
):
    observation = await connector.read_back(
        context=ReconciliationContext(
            execution_id=str(uuid.uuid4()),
            step_id="charge-card",
            intent_id=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            connector_operation=DEFAULT_CONNECTOR,
            redacted_target="account-redacted-17",
            request_fingerprint="f" * 64,
            attempt_count=0,
        ),
        readback_timeout=5.0,
    )

    assert observation.result is ReadbackResult.NOT_APPLIED


@pytest.mark.asyncio
async def test_the_mock_api_never_saw_protected_material_it_should_not_have(
    redis_client, storage_adapter, lock_manager, connector, mock_api
):
    """The vault boundary holds across a real network hop.

    The request carries a secret; the ledger and run log must contain its
    digest and nothing more.
    """
    execution_id = await _seed(storage_adapter, lock_manager)
    await _evaluation_runner(redis_client, lock_manager, connector).execute(
        execution_id=execution_id,
        step_id="charge-card",
        request=_request(
            target="account-redacted-17",
            protected_fields={"authorization": "Bearer super-secret-value"},
        ),
    )

    import yaml

    document = yaml.safe_load(mock_api.config_path.read_text(encoding="utf-8"))
    ledger_path = document["ledger_path"]
    run_log = ledger_path.replace(".sqlite3", ".run.jsonl")

    assert b"super-secret-value" not in open(ledger_path, "rb").read()
    assert "super-secret-value" not in open(run_log, encoding="utf-8").read()
