"""Get/migration adversarial tests (G-01..G-07).

Tests for state retrieval, schema validation, and migration chain handling.
Covers missing keys, valid payloads, corruption scenarios, and migration.
"""

import json
import uuid

import pytest

from aep_core.core.exceptions import StateCorruptionError, StorageOperationError
from aep_core.core.storage import (
    AEPExecutionState,
    AEPStatus,
    CURRENT_SCHEMA_VERSION,
    SCHEMA_MIGRATIONS,
)


class TestGetMissing:
    """G-01: Missing key returns None."""

    @pytest.mark.asyncio
    async def test_get_missing_key_returns_none(self, storage_adapter):
        """Calling get_state on a non-existent key returns None."""
        eid = str(uuid.uuid4())
        result = await storage_adapter.get_state(eid)
        assert result is None


class TestGetValidRoundTrip:
    """G-02: Valid JSON, valid schema_version round-trips correctly."""

    @pytest.mark.asyncio
    async def test_get_valid_round_trip(self, redis_client, storage_adapter):
        """Load a legacy state payload and verify it round-trips exactly."""
        eid = str(uuid.uuid4())
        original = AEPExecutionState(
            execution_id=eid,
            status=AEPStatus.PROCESSING,
            version=1,
            context_data={"key": "value", "nested": {"x": 123}},
            intent_ledger={"step1": {"status": "COMPLETED_SUCCESSFULLY"}},
        )

        # This is a read-path compatibility fixture.  Inject it as an already
        # existing legacy payload because the Phase 1 writer must no longer be
        # capable of introducing a non-empty Phase 2 ledger.
        await redis_client.set(
            f"aep:state:{eid}", original.model_dump_json(), ex=3600
        )

        # Load
        loaded = await storage_adapter.get_state(eid)

        # Compare
        assert loaded is not None
        assert loaded.execution_id == original.execution_id
        assert loaded.status == original.status
        assert loaded.version == original.version
        assert loaded.context_data == original.context_data
        assert loaded.intent_ledger == original.intent_ledger
        # updated_at is a float and may have small differences; allow tolerance
        assert abs(loaded.updated_at - original.updated_at) < 1.0


class TestGetNonJSON:
    """G-03: Non-JSON bytes stored trigger quarantine and StateCorruptionError."""

    @pytest.mark.asyncio
    async def test_get_non_json_payload(self, redis_client, storage_adapter):
        """Non-JSON payload in Redis raises StateCorruptionError."""
        eid = str(uuid.uuid4())
        state_key = f"aep:state:{eid}"

        # Store non-JSON bytes
        await redis_client.set(state_key, "not json at all", ex=3600)

        with pytest.raises(StateCorruptionError) as exc_info:
            await storage_adapter.get_state(eid)

        assert "parse/validation" in str(exc_info.value)

        # Verify quarantine key was created (best-effort)
        poison_keys = await redis_client.keys(f"aep:poison:{eid}:*")
        if poison_keys:
            poison_data = await redis_client.get(poison_keys[0])
            data = json.loads(poison_data)
            assert data.get("reason") == "parse-or-validation"


class TestGetSchemaInvalid:
    """G-04: JSON that fails schema validation raises StateCorruptionError."""

    @pytest.mark.asyncio
    async def test_get_schema_invalid_json(self, redis_client, storage_adapter):
        """Valid JSON at CURRENT_SCHEMA_VERSION that fails Pydantic validation
        raises StateCorruptionError via the parse/validation branch.

        Note: the payload MUST carry schema_version=CURRENT_SCHEMA_VERSION so
        that get_state bypasses _migrate_schema and reaches
        AEPExecutionState.model_validate, where an invalid enum value
        ("BOGUS" is not in AEPStatus) raises ValidationError. That branch
        emits the "parse/validation" reason in the exception message.

        Why this matters: if schema_version is omitted, the code legitimately
        routes through _migrate_schema and raises "No migration path from
        schema_version=None ..." (a different, also-correct fail-closed
        signal), which is covered by G-05's
        test_get_unknown_schema_version_no_migrator.
        """
        eid = str(uuid.uuid4())
        state_key = f"aep:state:{eid}"

        # Valid JSON, at current schema_version, but invalid status enum.
        # This exercises the Pydantic validation branch (not the migration
        # branch), which is what G-04 is intended to verify.
        invalid = json.dumps(
            {
                "execution_id": eid,
                "status": "BOGUS",  # not a member of AEPStatus
                "version": 1,
                "schema_version": CURRENT_SCHEMA_VERSION,
            }
        )
        await redis_client.set(state_key, invalid, ex=3600)

        with pytest.raises(StateCorruptionError) as exc_info:
            await storage_adapter.get_state(eid)

        assert "parse/validation" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_invalid_status_enum(self, redis_client, storage_adapter):
        """Valid JSON with invalid status enum value raises error."""
        eid = str(uuid.uuid4())
        state_key = f"aep:state:{eid}"

        # Valid structure but invalid status
        invalid = json.dumps(
            {
                "execution_id": eid,
                "status": "INVALID_STATUS",
                "version": 1,
                "schema_version": CURRENT_SCHEMA_VERSION,
            }
        )
        await redis_client.set(state_key, invalid, ex=3600)

        with pytest.raises(StateCorruptionError):
            await storage_adapter.get_state(eid)

    @pytest.mark.asyncio
    async def test_get_invalid_execution_id_type(self, redis_client, storage_adapter):
        """Valid JSON with invalid execution_id type raises error."""
        eid = str(uuid.uuid4())
        state_key = f"aep:state:{eid}"

        # execution_id must be a string and a UUIDv4
        invalid = json.dumps(
            {
                "execution_id": 12345,  # int instead of string
                "status": "IDLE",
                "version": 1,
                "schema_version": CURRENT_SCHEMA_VERSION,
            }
        )
        await redis_client.set(state_key, invalid, ex=3600)

        with pytest.raises(StateCorruptionError):
            await storage_adapter.get_state(eid)


class TestGetUnknownSchema:
    """G-05: Unknown schema_version with no migrator raises StateCorruptionError."""

    @pytest.mark.asyncio
    async def test_get_unknown_schema_version_no_migrator(
        self, redis_client, storage_adapter
    ):
        """Unknown schema_version with no registered migrator raises error."""
        eid = str(uuid.uuid4())
        state_key = f"aep:state:{eid}"

        # Store valid JSON with an unknown schema version
        unknown_schema = json.dumps(
            {
                "execution_id": eid,
                "status": "IDLE",
                "version": 1,
                "schema_version": "99.99.99",  # Unknown version
            }
        )
        await redis_client.set(state_key, unknown_schema, ex=3600)

        with pytest.raises(StateCorruptionError) as exc_info:
            await storage_adapter.get_state(eid)

        assert "No migration path" in str(exc_info.value)


class TestGetKnownMigrator:
    """G-06: Known migrator registered and used."""

    @pytest.mark.asyncio
    async def test_get_schema_migrated_with_registered_migrator(
        self, redis_client, storage_adapter
    ):
        """Schema migration is applied when a migrator is registered."""
        eid = str(uuid.uuid4())
        state_key = f"aep:state:{eid}"

        # Define a test migrator inline
        def migrate_0_9_0_to_1_0_0(raw):
            # Transform old schema to new
            raw["intent_ledger"] = raw.pop("old_ledger", {})
            raw["schema_version"] = "1.0.0"
            return raw

        # Temporarily register the migrator
        original_migrations = SCHEMA_MIGRATIONS.copy()
        try:
            SCHEMA_MIGRATIONS["0.9.0"] = migrate_0_9_0_to_1_0_0

            # Store a state with old schema
            old_schema = json.dumps(
                {
                    "execution_id": eid,
                    "status": "IDLE",
                    "version": 1,
                    "schema_version": "0.9.0",
                    "old_ledger": {"step1": {"status": "COMPLETED"}},
                    "context_data": {},
                    "updated_at": 1234567.0,
                }
            )
            await redis_client.set(state_key, old_schema, ex=3600)

            # Get should migrate and return
            loaded = await storage_adapter.get_state(eid)

            assert loaded is not None
            assert loaded.schema_version == "1.0.0"
            assert loaded.intent_ledger == {"step1": {"status": "COMPLETED"}}

        finally:
            # Restore original migrations
            SCHEMA_MIGRATIONS.clear()
            SCHEMA_MIGRATIONS.update(original_migrations)


class TestGetKeyPayloadMismatch:
    """G-07: execution_id key/payload mismatch raises StorageOperationError."""

    @pytest.mark.asyncio
    async def test_get_key_payload_mismatch(self, redis_client, storage_adapter):
        """Key suffix does not match payload execution_id raises error."""
        key_eid = str(uuid.uuid4())
        payload_eid = str(uuid.uuid4())
        state_key = f"aep:state:{key_eid}"

        # Store a valid state but with a different execution_id in the payload
        mismatched = json.dumps(
            {
                "execution_id": payload_eid,  # Different from key
                "status": "IDLE",
                "version": 1,
                "schema_version": CURRENT_SCHEMA_VERSION,
            }
        )
        await redis_client.set(state_key, mismatched, ex=3600)

        # Try to get with the key's execution_id
        with pytest.raises(StorageOperationError) as exc_info:
            await storage_adapter.get_state(key_eid)

        assert "Key/payload mismatch" in str(exc_info.value)
        assert key_eid in str(exc_info.value)
        assert payload_eid in str(exc_info.value)
