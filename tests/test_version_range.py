"""Regression tests for Redis Lua's exact-integer version limit."""

import json
import uuid

import pytest
from pydantic import ValidationError

from aep_core.core.exceptions import StorageOperationError
from aep_core.core.storage import AEPExecutionState, AEPStatus, CURRENT_SCHEMA_VERSION


MAX_SAFE_VERSION = (1 << 53) - 1


def test_state_model_rejects_version_above_lua_safe_integer():
    with pytest.raises(ValidationError, match="less than or equal"):
        AEPExecutionState(
            execution_id=str(uuid.uuid4()),
            status=AEPStatus.IDLE,
            version=MAX_SAFE_VERSION + 1,
        )


@pytest.mark.asyncio
async def test_save_rejects_increment_beyond_lua_safe_integer(
    storage_adapter, lock_manager, redis_client
):
    eid = str(uuid.uuid4())
    state_key = f"aep:state:{eid}"
    stored = {
        "execution_id": eid,
        "status": "IDLE",
        "version": MAX_SAFE_VERSION,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "intent_ledger": {},
        "context_data": {},
        "updated_at": 1.0,
    }
    await redis_client.set(state_key, json.dumps(stored), ex=3600)
    token = await lock_manager.acquire_lock(eid, ttl_seconds=60)
    assert token is not None

    incoming = AEPExecutionState(
        execution_id=eid, status=AEPStatus.PROCESSING, version=1
    )
    # Assignment validation is intentionally not relied on by save_state.
    incoming.version = MAX_SAFE_VERSION + 1

    with pytest.raises(StorageOperationError, match="maximum|safe"):
        await storage_adapter.save_state(
            incoming,
            expected_version=MAX_SAFE_VERSION,
            lock_token=token,
            ttl_seconds=3600,
        )

    remaining = json.loads(await redis_client.get(state_key))
    assert remaining["version"] == MAX_SAFE_VERSION
    await lock_manager.release_lock(eid, token)
