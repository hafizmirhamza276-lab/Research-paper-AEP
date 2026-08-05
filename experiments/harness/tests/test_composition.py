"""Amendment C2: the harness composition carries no test authorisation.

``reports/phase-report-1b-2026-08-05.md`` F4 said the 22 crash-boundary runner
tests "all still run in TEST mode", and Session 1's F4 repeated it: EVALUATION
mode had been shown to work for exactly one happy-path dispatch. C2 closes
that for the harness by making EVALUATION the only mode the harness can be
configured for, and by asserting here -- against real Redis, a real WAITAOF
barrier, a real vault and a real HTTP connector -- that the composition a
worker builds validates with every test affordance withheld.

The structural test at the end is the one that keeps it closed: it fails if the
string ``allow_test`` appears anywhere under ``experiments/harness/``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from aep_core.core.connector_contract import (
    ReconciliationCapability,
    declared_capability,
)
from aep_core.core.intent_workflow import DispatchMode
from aep_core.core.intents import IntentLedgerStore, IntentStatus
from experiments.harness.composition import (
    build_connector,
    build_recovery_service,
    build_runner,
    delete_run_keys,
    seed_execution_state,
)
from experiments.harness.config import RunConfig
from experiments.harness.workload import (
    index_by_execution_id,
    plan_workload,
    request_for,
)
from experiments.mock_api.ledger import GroundTruthLedger
from experiments.mock_api.tests.server_harness import MockApiProcess, write_config

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

HARNESS_ROOT = Path(__file__).resolve().parent.parent


def mock_api_document(tmp_path) -> dict:
    return {
        "config_version": "aep.mock-legacy-api.config/1",
        "seed": 20260805,
        "ledger_path": str(tmp_path / "ground_truth.sqlite3"),
        "readback_keying": "CALLER_REFERENCE",
        "endpoints": {
            "payments": {
                "response_class": (
                    ReconciliationCapability.AUTHORITATIVE_READBACK.value
                ),
                "identity_fields": ["action", "amount_minor"],
            }
        },
    }


@pytest.fixture
def mock_api(tmp_path):
    config_path = write_config(tmp_path / "mock-api.yaml", mock_api_document(tmp_path))
    with MockApiProcess(config_path, log_directory=tmp_path) as server:
        yield server


@pytest.fixture
def run_config(tmp_path, mock_api) -> RunConfig:
    return RunConfig(
        run_id="run-composition-test",
        seed=20260805,
        workers=1,
        executions_per_worker=2,
        endpoint="payments",
        mock_api_config_path=str(mock_api.config_path),
        mock_api_base_url=mock_api.base_url,
        redis_url=os.environ["REDIS_URL"],
        results_root=str(tmp_path / "results"),
    )


def ledger_for(mock_api: MockApiProcess) -> GroundTruthLedger:
    document = yaml.safe_load(mock_api.config_path.read_text(encoding="utf-8"))
    ledger = GroundTruthLedger(document["ledger_path"])
    ledger.initialise()
    return ledger


# ===========================================================================
# The composition is production-shaped
# ===========================================================================


@pytest.mark.asyncio
async def test_the_runner_validates_with_no_test_authorisation(
    run_config, redis_client, lock_manager
):
    connector = build_connector(run_config)
    try:
        runner = build_runner(
            run_config,
            redis_client=redis_client,
            lock_manager=lock_manager,
            connector=connector,
        )

        assert runner.mode is DispatchMode.EVALUATION
        assert runner.allow_test_dispatch is False
        assert runner.allow_test_barrier is False
        assert getattr(runner.binding_service.vault, "test_only") is False
        assert getattr(runner.binding_service.vault, "evaluation_only") is True
        assert getattr(runner.barrier, "test_only", False) is False
        assert getattr(connector, "test_only") is False
        assert getattr(connector, "evaluation_endpoint") is True

        # The real check: WAITAOF capability against the live server.
        await runner.validate_startup()
    finally:
        await connector.aclose()


@pytest.mark.asyncio
async def test_the_connector_declares_a_contract_capability(run_config):
    connector = build_connector(run_config)
    try:
        assert (
            declared_capability(connector)
            is ReconciliationCapability.AUTHORITATIVE_READBACK
        )
    finally:
        await connector.aclose()


@pytest.mark.asyncio
async def test_a_crash_injector_does_not_change_the_mode(
    run_config, redis_client, lock_manager
):
    """Crash injection is orthogonal to dispatch authority, and must stay so."""

    class _Injector:
        async def checkpoint(self, point):
            return None

    connector = build_connector(run_config)
    try:
        runner = build_runner(
            run_config,
            redis_client=redis_client,
            lock_manager=lock_manager,
            connector=connector,
            crash_injector=_Injector(),
        )

        assert runner.mode is DispatchMode.EVALUATION
        assert runner.allow_test_dispatch is False
        await runner.validate_startup()
    finally:
        await connector.aclose()


# ===========================================================================
# And it really dispatches
# ===========================================================================


@pytest.mark.asyncio
async def test_the_composition_dispatches_a_real_mutation(
    run_config, redis_client, storage_adapter, lock_manager, mock_api
):
    item = plan_workload(run_config)[0]
    connector = build_connector(
        run_config, items=index_by_execution_id(plan_workload(run_config))
    )
    try:
        await seed_execution_state(
            storage_adapter=storage_adapter,
            lock_manager=lock_manager,
            execution_id=item.execution_id,
        )
        runner = build_runner(
            run_config,
            redis_client=redis_client,
            lock_manager=lock_manager,
            connector=connector,
        )
        resolved = await runner.execute(
            execution_id=item.execution_id,
            step_id=item.step_id,
            request=request_for(item),
        )
    finally:
        await connector.aclose()

    assert resolved.status is IntentStatus.FIRED_CONFIRMED

    ledger = ledger_for(mock_api)
    try:
        (applied,) = ledger.applied_mutations()
        assert applied.target == item.target
        assert applied.client_reference == resolved.request_fingerprint
        assert ledger.duplicate_groups() == ()
        assert ledger.consistency_report().is_consistent
    finally:
        ledger.close()


@pytest.mark.asyncio
async def test_the_recovery_service_is_built_for_the_same_connector_name(
    run_config, redis_client, lock_manager
):
    connector = build_connector(run_config)
    try:
        service = build_recovery_service(
            run_config,
            redis_client=redis_client,
            lock_manager=lock_manager,
            connector=connector,
        )

        # A mismatch here is the failure mode where recovery finds an intent
        # and has no declaration for the connector that wrote it.
        runner = build_runner(
            run_config,
            redis_client=redis_client,
            lock_manager=lock_manager,
            connector=connector,
        )
        assert set(service.connectors) == {runner.connector_name}
    finally:
        await connector.aclose()


@pytest.mark.asyncio
async def test_cleanup_removes_only_the_keys_this_run_created(
    run_config, redis_client, storage_adapter, lock_manager
):
    item = plan_workload(run_config)[0]
    await seed_execution_state(
        storage_adapter=storage_adapter,
        lock_manager=lock_manager,
        execution_id=item.execution_id,
    )
    await redis_client.set("aep:state:not-this-run", "keep me")

    await delete_run_keys(redis_client, [item.execution_id])

    assert await redis_client.get(f"aep:state:{item.execution_id}") is None
    assert await redis_client.get("aep:state:not-this-run") == "keep me"
    await redis_client.unlink("aep:state:not-this-run")


# ===========================================================================
# The structural gate
# ===========================================================================


def test_no_harness_module_names_a_test_authorisation():
    """C2, made impossible to regress by discipline alone."""
    offenders = []
    for source in HARNESS_ROOT.rglob("*.py"):
        if "tests" in source.parts:
            continue
        text = source.read_text(encoding="utf-8")
        for needle in ("allow_test_dispatch", "allow_test_barrier"):
            if needle in text:
                offenders.append(f"{source.name}:{needle}")

    assert offenders == [], (
        f"harness modules reference test authorisation: {offenders}. Every "
        "harness-driven run executes in EVALUATION mode (amendment C2)."
    )


def test_no_harness_module_reaches_the_oracle_routes():
    """The protocol under measurement must not be able to read its own score."""
    offenders = []
    for source in HARNESS_ROOT.rglob("*.py"):
        if "tests" in source.parts or source.name == "reconcile.py":
            continue
        if "/v1/oracle" in source.read_text(encoding="utf-8"):
            offenders.append(source.name)

    assert offenders == [], (
        f"{offenders} reach the mock API's oracle routes. Only reconcile.py, "
        "which runs after a run has finished, may read the ground truth."
    )
