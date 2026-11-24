"""CAS write adversarial tests (C-01..C-04).

Tests for the atomic Compare-And-Swap Lua script that is the only write path
for state keys. Covers success paths, stale writes, and corruption scenarios.
"""

import json
import inspect
import uuid

import pytest

from aep_core.core.exceptions import (
    LockAcquisitionError,
    StateCorruptionError,
    StaleWriteError,
    StorageOperationError,
)
from aep_core.core.storage import AEPExecutionState, AEPStatus


async def _save_with_fencing_contract(
    storage_adapter, state, *, expected_version, lock_token, ttl_seconds=3600
):
    """Call the pre-fix or post-fix API so one regression test spans both."""
    parameters = inspect.signature(storage_adapter.save_state).parameters
    if "expected_version" in parameters:
        return await storage_adapter.save_state(
            state,
            expected_version=expected_version,
            lock_token=lock_token,
            ttl_seconds=ttl_seconds,
        )
    return await storage_adapter.save_state(state, ttl_seconds=ttl_seconds)


class TestExpectedVersionAndLockFencing:
    """Regression coverage for true CAS and lock-token ownership."""

    @pytest.mark.asyncio
    async def test_stale_writer_cannot_jump_version(
        self, storage_adapter, lock_manager
    ):
        eid = str(uuid.uuid4())
        token = await lock_manager.acquire_lock(eid, ttl_seconds=60)
        assert token is not None

        initial = AEPExecutionState(
            execution_id=eid, status=AEPStatus.IDLE, version=1
        )
        await _save_with_fencing_contract(
            storage_adapter,
            initial,
            expected_version=0,
            lock_token=token,
        )
        stale = initial.model_copy(deep=True)

        newer = initial.model_copy(deep=True)
        newer.version = 2
        newer.status = AEPStatus.COMPLETED
        await _save_with_fencing_contract(
            storage_adapter,
            newer,
            expected_version=1,
            lock_token=token,
        )

        stale.version = 999
        stale.status = AEPStatus.FAILED
        with pytest.raises(StaleWriteError, match="expected version"):
            await _save_with_fencing_contract(
                storage_adapter,
                stale,
                expected_version=1,
                lock_token=token,
            )

        final = await storage_adapter.get_state(eid)
        assert final is not None
        assert final.version == 2
        assert final.status == AEPStatus.COMPLETED
        await lock_manager.release_lock(eid, token)

    @pytest.mark.asyncio
    async def test_save_requires_matching_live_lock_token(
        self, storage_adapter
    ):
        state = AEPExecutionState(
            execution_id=str(uuid.uuid4()),
            status=AEPStatus.IDLE,
            version=1,
        )

        with pytest.raises(LockAcquisitionError, match="lock"):
            await _save_with_fencing_contract(
                storage_adapter,
                state,
                expected_version=0,
                lock_token="not-the-owner",
            )


class TestSchemaVersionWriteGuard:
    """Regression coverage for rejecting unreadable state on write."""

    @pytest.mark.asyncio
    async def test_save_rejects_unsupported_schema_version_before_write(
        self, storage_adapter, lock_manager, redis_client
    ):
        eid = str(uuid.uuid4())
        token = await lock_manager.acquire_lock(eid, ttl_seconds=60)
        assert token is not None
        state = AEPExecutionState(
            execution_id=eid,
            status=AEPStatus.IDLE,
            version=1,
            schema_version="99.0.0",
        )

        with pytest.raises(StorageOperationError, match="schema_version"):
            await storage_adapter.save_state(
                state,
                expected_version=0,
                lock_token=token,
                ttl_seconds=3600,
            )

        assert await redis_client.get(f"aep:state:{eid}") is None
        await lock_manager.release_lock(eid, token)


class TestCASFirstWrite:
    """C-01: First write to a fresh key succeeds."""

    @pytest.mark.asyncio
    async def test_cas_first_write_no_key(self, storage_adapter, locked_save):
        """Writing to a non-existent key succeeds (CAS returns 1)."""
        eid = str(uuid.uuid4())
        state = AEPExecutionState(
            execution_id=eid,
            status=AEPStatus.IDLE,
            version=1,
        )

        # Should not raise
        await locked_save(state, ttl_seconds=3600)

        # Verify it was written
        loaded = await storage_adapter.get_state(eid)
        assert loaded is not None
        assert loaded.execution_id == eid
        assert loaded.version == 1


class TestCASMonotonicIncrements:
    """C-02: Strictly increasing versions all succeed."""

    @pytest.mark.asyncio
    async def test_cas_strictly_increasing_versions(
        self, storage_adapter, locked_save
    ):
        """Multiple increments from v1 to v5 all succeed."""
        eid = str(uuid.uuid4())
        state = AEPExecutionState(
            execution_id=eid,
            status=AEPStatus.IDLE,
            version=1,
        )

        # Write v1
        await locked_save(state, ttl_seconds=3600)

        # Increment and write v2..v5
        for next_version in range(2, 6):
            state.version = next_version
            state.status = AEPStatus.PROCESSING  # mutate to verify update
            await locked_save(state, ttl_seconds=3600)

        # Verify final state
        loaded = await storage_adapter.get_state(eid)
        assert loaded.version == 5
        assert loaded.status == AEPStatus.PROCESSING


class TestCASStaleWrite:
    """C-03: Equal or lower version raises StaleWriteError."""

    @pytest.mark.asyncio
    async def test_cas_equal_version_rejected(self, storage_adapter, locked_save):
        """Writing with version == stored version raises StaleWriteError."""
        eid = str(uuid.uuid4())
        state = AEPExecutionState(
            execution_id=eid,
            status=AEPStatus.IDLE,
            version=1,
        )

        # First write succeeds
        await locked_save(state, ttl_seconds=3600)

        # Try to write the same version again
        with pytest.raises(StaleWriteError) as exc_info:
            await locked_save(state, expected_version=0, ttl_seconds=3600)

        assert "expected version" in str(exc_info.value)

        # Verify original state is unchanged
        loaded = await storage_adapter.get_state(eid)
        assert loaded.version == 1

    @pytest.mark.asyncio
    async def test_cas_lower_version_rejected(self, storage_adapter, locked_save):
        """Writing with version < stored version raises StaleWriteError."""
        eid = str(uuid.uuid4())
        state = AEPExecutionState(
            execution_id=eid,
            status=AEPStatus.IDLE,
            version=1,
        )

        # Write v1, then advance normally to v2.
        await locked_save(state, ttl_seconds=3600)
        state.version = 2
        await locked_save(state, ttl_seconds=3600)

        # Try to write a lower version while claiming v2 was read.
        state.version = 1
        with pytest.raises(StaleWriteError):
            await locked_save(state, expected_version=2, ttl_seconds=3600)

        # Verify original state is unchanged
        loaded = await storage_adapter.get_state(eid)
        assert loaded.version == 2


class TestCASCorruptPayload:
    """C-04: Corrupt stored payload at write time raises StateCorruptionError."""

    @pytest.mark.asyncio
    async def test_cas_corrupt_at_write_no_overwrite(
        self, redis_client, storage_adapter, locked_save
    ):
        """Writing when stored payload is corrupt raises StateCorruptionError.

        The Lua script returns -2 and does NOT overwrite. The adapter calls
        _quarantine and raises StateCorruptionError.
        """
        eid = str(uuid.uuid4())
        state_key = f"aep:state:{eid}"

        # Manually store a corrupt (non-JSON) payload
        await redis_client.set(state_key, "not valid json at all }{", ex=3600)

        # Try to write a valid state
        state = AEPExecutionState(
            execution_id=eid,
            status=AEPStatus.IDLE,
            version=1,
        )

        with pytest.raises(StateCorruptionError) as exc_info:
            await locked_save(state, ttl_seconds=3600)

        assert "corrupt or unversioned" in str(exc_info.value)

        # Verify the corrupt payload was NOT overwritten
        raw = await redis_client.get(state_key)
        assert raw == "not valid json at all }{"

        # Verify a quarantine key was created (best-effort)
        poison_keys = await redis_client.keys("aep:poison:*")
        # Note: poison write is best-effort, so we don't assert it exists,
        # but if it does, it should contain the execution_id
        if poison_keys:
            assert any(eid in key for key in poison_keys)

    @pytest.mark.asyncio
    async def test_cas_corrupt_unversioned_payload(
        self, redis_client, storage_adapter, locked_save
    ):
        """Writing when stored payload has no 'version' field raises error."""
        eid = str(uuid.uuid4())
        state_key = f"aep:state:{eid}"

        # Store a valid JSON object but without a 'version' field
        corrupt_payload = json.dumps({"execution_id": eid, "status": "IDLE"})
        await redis_client.set(state_key, corrupt_payload, ex=3600)

        # Try to write a valid state
        state = AEPExecutionState(
            execution_id=eid,
            status=AEPStatus.IDLE,
            version=1,
        )

        with pytest.raises(StateCorruptionError):
            await locked_save(state, ttl_seconds=3600)

        # Verify no overwrite occurred
        raw = await redis_client.get(state_key)
        assert raw == corrupt_payload

    @pytest.mark.asyncio
    async def test_cas_corrupted_json_field_in_table(
        self, redis_client, storage_adapter, locked_save
    ):
        """Writing when stored version field is not a number."""
        eid = str(uuid.uuid4())
        state_key = f"aep:state:{eid}"

        # Store valid JSON with a string version (should be numeric)
        bad_payload = json.dumps(
            {"execution_id": eid, "status": "IDLE", "version": "not-a-number"}
        )
        await redis_client.set(state_key, bad_payload, ex=3600)

        state = AEPExecutionState(
            execution_id=eid,
            status=AEPStatus.IDLE,
            version=1,
        )

        # A malformed stored version must never be accepted as a successful
        # CAS write. Both typed failures are compatible with older backends.
        with pytest.raises((StateCorruptionError, StaleWriteError)):
            await locked_save(state, ttl_seconds=3600)

        assert await redis_client.get(state_key) == bad_payload

    @pytest.mark.asyncio
    async def test_cas_quarantine_called_on_corrupt(
        self, redis_client, storage_adapter, locked_save
    ):
        """Quarantine key is written before StateCorruptionError is raised."""
        eid = str(uuid.uuid4())
        state_key = f"aep:state:{eid}"

        # Store a corrupt payload
        await redis_client.set(state_key, "{invalid json", ex=3600)

        state = AEPExecutionState(
            execution_id=eid,
            status=AEPStatus.IDLE,
            version=1,
        )

        with pytest.raises(StateCorruptionError):
            await locked_save(state, ttl_seconds=3600)

        # This path has a healthy Redis connection, so quarantine is required.
        poison_keys = await redis_client.keys(f"aep:poison:{eid}:*")
        assert poison_keys, "Expected a poison key for the corrupt state"
        for poison_key in poison_keys:
            poison_data = await redis_client.get(poison_key)
            assert poison_data is not None
            data = json.loads(poison_data)
            assert data.get("reason") == "corrupt-at-write"
            assert "raw" not in data
            assert data.get("raw_length") == len("{invalid json")
            assert data.get("raw_encoding") == "utf8"
