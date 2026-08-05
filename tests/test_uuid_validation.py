"""Regression tests for strict UUIDv4 validation on every public API."""

import uuid

import pytest
from pydantic import ValidationError

from aep_core.core.exceptions import LockAcquisitionError, StorageOperationError
from aep_core.core.storage import AEPExecutionState, AEPStatus


@pytest.mark.parametrize(
    "invalid_id",
    [
        str(uuid.uuid1()),
        str(uuid.uuid4()).upper(),
        uuid.uuid4().hex,
    ],
)
def test_state_model_rejects_non_v4_or_noncanonical_uuid(invalid_id):
    with pytest.raises(ValidationError, match="canonical UUIDv4"):
        AEPExecutionState(execution_id=invalid_id, status=AEPStatus.IDLE)


@pytest.mark.asyncio
async def test_get_state_rejects_invalid_execution_id(storage_adapter):
    with pytest.raises(StorageOperationError, match="canonical UUIDv4"):
        await storage_adapter.get_state(str(uuid.uuid1()))


@pytest.mark.asyncio
async def test_save_state_revalidates_mutated_execution_id(
    storage_adapter, redis_client
):
    state = AEPExecutionState(
        execution_id=str(uuid.uuid4()), status=AEPStatus.IDLE, version=1
    )
    state.execution_id = str(uuid.uuid1())
    token = "test-token"
    await redis_client.set(f"aep:lock:{state.execution_id}", token, ex=60)

    with pytest.raises(StorageOperationError, match="canonical UUIDv4"):
        await storage_adapter.save_state(
            state,
            expected_version=0,
            lock_token=token,
            ttl_seconds=3600,
        )


@pytest.mark.asyncio
async def test_all_lock_entry_points_reject_invalid_execution_id(lock_manager):
    invalid_id = str(uuid.uuid4()).upper()

    with pytest.raises(LockAcquisitionError, match="canonical UUIDv4"):
        await lock_manager.acquire_lock(invalid_id)
    with pytest.raises(LockAcquisitionError, match="canonical UUIDv4"):
        await lock_manager.release_lock(invalid_id, "token")
    with pytest.raises(LockAcquisitionError, match="canonical UUIDv4"):
        await lock_manager.renew_lock(invalid_id, "token")
    with pytest.raises(LockAcquisitionError, match="canonical UUIDv4"):
        async with lock_manager.lease(
            invalid_id,
            ttl_seconds=20,
            client_deadline_seconds=1,
            buffer_margin_seconds=15,
        ):
            pass
