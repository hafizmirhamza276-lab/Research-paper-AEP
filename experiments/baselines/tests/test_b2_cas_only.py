"""B2: fenced state writes, and no write-ahead intent.

PAPER_ROADMAP.md section 3.3: *"B2: CAS-only -- Fenced writes, no write-ahead
intent."*

B2 is the ablation that separates the two things AEP protects. Its state writes
go through ``RedisStorageAdapter.save_state`` -- the same expected-version CAS
under a live lock token that AEP-full uses -- so its *state* enjoys the full
P1 guarantee, and the tests below prove that by watching a stale writer be
refused. Its *external effects* have no protection whatsoever, because nothing
is written down before the call.
"""

from __future__ import annotations

import pytest

from aep_core.core.exceptions import StaleWriteError
from aep_core.core.intent_workflow import ConnectorPolicy
from aep_core.core.storage import AEPExecutionState, AEPStatus

from experiments.baselines.b2_cas_only import CasOnlyRunner, classify
from experiments.baselines.contract import OutcomeClass, SystemId
from experiments.baselines.tests.conftest import (
    RecordingConnector,
    ambiguous,
    applied,
    refused,
)
from experiments.baselines.tests.helpers import EXECUTION_ID, item_for
from experiments.harness.workload import harness_profile, request_for

POLICY = ConnectorPolicy(client_timeout_seconds=1.0, lock_ttl_seconds=20)

pytestmark = pytest.mark.usefixtures("cjson_available")


def build(redis_client, lock_manager, storage_adapter, connector, **kwargs):
    return CasOnlyRunner(
        redis_client=redis_client,
        lock_manager=lock_manager,
        storage_adapter=storage_adapter,
        connector=connector,
        profile=harness_profile(),
        policy=POLICY,
        **kwargs,
    )


async def test_state_write_is_fenced_by_expected_version(
    redis_client, lock_manager, storage_adapter, cjson_available
) -> None:
    """The guarantee B2 keeps: a stale writer is refused, not merged."""
    if not cjson_available:
        pytest.skip("CAS fencing requires a Redis with cjson")
    item = item_for()
    token = await lock_manager.acquire_lock(item.execution_id, ttl_seconds=20)
    assert token is not None
    try:
        await storage_adapter.save_state(
            AEPExecutionState(execution_id=item.execution_id, status=AEPStatus.IDLE),
            expected_version=0,
            lock_token=token,
        )
        await storage_adapter.save_state(
            AEPExecutionState(
                execution_id=item.execution_id, status=AEPStatus.PROCESSING, version=2
            ),
            expected_version=1,
            lock_token=token,
        )
        with pytest.raises(StaleWriteError):
            await storage_adapter.save_state(
                AEPExecutionState(
                    execution_id=item.execution_id,
                    status=AEPStatus.COMPLETED,
                    version=2,
                ),
                expected_version=1,
                lock_token=token,
            )
    finally:
        await lock_manager.release_lock(item.execution_id, token)


async def test_records_the_outcome_through_the_fenced_path(
    redis_client, lock_manager, storage_adapter, cjson_available
) -> None:
    if not cjson_available:
        pytest.skip("CAS fencing requires a Redis with cjson")
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, lock_manager, storage_adapter, connector)
    item = item_for()

    # Seeded exactly as the harness seeds it, so the version this test reads
    # is the version a matrix run produces. Without the seed B2 creates the
    # record itself at version 1 and the assertion below would be checking a
    # different code path from the one the results come from.
    token = await lock_manager.acquire_lock(item.execution_id, ttl_seconds=20)
    assert token is not None
    await storage_adapter.save_state(
        AEPExecutionState(execution_id=item.execution_id, status=AEPStatus.IDLE),
        expected_version=0,
        lock_token=token,
    )
    await lock_manager.release_lock(item.execution_id, token)

    outcome = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    state = await storage_adapter.get_state(item.execution_id)
    assert state is not None
    assert state.status is AEPStatus.COMPLETED
    assert state.version == 2, "a fenced write increments the fencing counter by one"
    assert outcome.outcome_class is OutcomeClass.CONFIRMED_APPLIED


async def test_writes_no_intent_ledger(
    redis_client, lock_manager, storage_adapter, cjson_available
) -> None:
    """"no write-ahead intent": the state exists, the intent ledger is empty."""
    if not cjson_available:
        pytest.skip("CAS fencing requires a Redis with cjson")
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, lock_manager, storage_adapter, connector)
    item = item_for()

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    state = await storage_adapter.get_state(item.execution_id)
    assert state is not None
    assert state.intent_ledger == {}
    assert state.phase2_managed is None
    assert (
        await redis_client.exists(f"aep:dispatch-auth:{item.execution_id}") == 0
    )


async def test_retries_on_ambiguity_and_records_an_unverified_failure(
    redis_client, lock_manager, storage_adapter, cjson_available
) -> None:
    if not cjson_available:
        pytest.skip("CAS fencing requires a Redis with cjson")
    connector = RecordingConnector(script=[ambiguous()])
    runner = build(
        redis_client, lock_manager, storage_adapter, connector, max_attempts=3
    )
    item = item_for()

    outcome = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert len(connector.transmissions) == 3
    assert outcome.outcome_class is OutcomeClass.UNVERIFIED_FAILURE
    state = await storage_adapter.get_state(item.execution_id)
    assert state is not None and state.status is AEPStatus.FAILED


async def test_a_refusal_is_confirmed_not_applied(
    redis_client, lock_manager, storage_adapter, cjson_available
) -> None:
    """FAILED in the state; the finer word is in context_data, where the
    difference between "refused" and "gave up" survives."""
    if not cjson_available:
        pytest.skip("CAS fencing requires a Redis with cjson")
    connector = RecordingConnector(script=[refused()])
    runner = build(redis_client, lock_manager, storage_adapter, connector)
    item = item_for()

    outcome = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert outcome.outcome_class is OutcomeClass.CONFIRMED_NOT_APPLIED
    classified = await classify(redis_client, item.execution_id)
    assert classified.outcome_class is OutcomeClass.CONFIRMED_NOT_APPLIED
    assert classified.system is SystemId.B2_CAS_ONLY


async def test_re_execution_transmits_again(
    redis_client, lock_manager, storage_adapter, cjson_available
) -> None:
    """Fenced state does not make an external effect idempotent."""
    if not cjson_available:
        pytest.skip("CAS fencing requires a Redis with cjson")
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, lock_manager, storage_adapter, connector)
    item = item_for()

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )
    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert len(connector.transmissions) == 2


async def test_classify_absent(redis_client) -> None:
    outcome = await classify(redis_client, EXECUTION_ID)
    assert outcome.outcome_class is OutcomeClass.NO_RECORD
