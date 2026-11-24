"""AEP Phase 1 storage adapter.

Provides:
  - AEPStatus enum and AEPExecutionState Pydantic v2 model (schema).
  - _CAS_SCRIPT: the Phase 1 Lua write path for aep:state:* keys.
  - SCHEMA_MIGRATIONS registry (empty in Phase 1).
  - BaseStorageAdapter ABC.
  - RedisStorageAdapter with save_state, get_state, _migrate_schema, _quarantine.

Honest guarantee: corruption and contention are detectable, and the system
fails closed. This module does NOT claim absolute atomicity, split-brain
impossibility, or exactly-once delivery.

Import-side-effect-free: no I/O, no network, no logging config at import time.
"""

import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator
from redis.client import NEVER_DECODE
from redis.asyncio import Redis

from aep_core.core.exceptions import (
    AmbiguousStateError,
    LockAcquisitionError,
    Phase2StateProtectionError,
    StateCorruptionError,
    StaleWriteError,
    StorageOperationError,
)
from aep_core.core.state_codec import (
    build_lua_state_validation_script,
    decode_state,
    encode_state,
    lua_state_validation_failure,
)
from aep_core.core.validation import validate_execution_id

# Module-level logger used by RedisStorageAdapter._quarantine to emit a
# WARNING when the best-effort quarantine write itself fails. The warning
# does NOT re-raise — preserving the design rule that a quarantine failure
# must never mask the original StateCorruptionError — but provides operator
# observability that bandit B110 (try_except_pass) flagged as missing.
logger = logging.getLogger("aep.storage")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class AEPStatus(str, Enum):
    """Lifecycle status for an AEP execution.

    Values are lowercase-safe (stored as strings in JSON). The str mixin
    ensures serialization produces the string value, not the enum key.
    """

    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    AWAITING_TOOL = "AWAITING_TOOL"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


CURRENT_SCHEMA_VERSION: str = "1.0.0"
"""Current schema version. Must be updated whenever a new schema version is
introduced (along with a corresponding migrator in SCHEMA_MIGRATIONS)."""

# Redis Lua represents numbers as IEEE-754 doubles. Integer versions are exact
# only through 2^53 - 1, so larger values must never reach the Lua comparison.
MAX_SAFE_VERSION: int = (1 << 53) - 1

PHASE2_MANAGED_MARKER: str = "intent-ledger-v1"
"""Immutable marker for executions owned by the Phase 2 write path."""


class AEPExecutionState(BaseModel):
    """Pydantic v2 model representing the full state of an AEP execution.

    Serialization: use the central ``encode_state`` function over
    ``model_dump(mode="json")`` for Redis storage. Deserialization must pass
    through ``decode_state`` before model validation.

    Versioning: the `version` field is the monotonic fencing counter used
    by the CAS Lua script. It starts at 1 and must increase strictly on
    every save. The `schema_version` field tracks the data schema and is
    used by the migration chain.

    Invariant (CAS Fencing): `version` is the fencing token. The lock
    ownership token (a random secrets value in locks.py) is a separate
    concept and must NEVER be confused with this integer.
    """

    execution_id: str
    """UUIDv4 string identifying the execution. Validated on construction.
    Must match the Redis key suffix aep:state:{execution_id}."""

    status: AEPStatus
    """Current lifecycle status of the execution."""

    version: int = Field(
        default=1, ge=1, le=MAX_SAFE_VERSION, strict=True
    )
    """Monotonic fencing counter. Starts at 1. Must increase strictly on
    every mutation. Never decremented. The CAS Lua script requires the caller's
    expected version to match storage and the incoming value to equal it + 1.
    """

    schema_version: str = Field(default=CURRENT_SCHEMA_VERSION)
    """Data schema version string. Used by _migrate_schema to walk the
    SCHEMA_MIGRATIONS chain on read. Must be bumped when the model fields
    change in a backwards-incompatible way."""

    intent_ledger: Dict[str, Any] = Field(default_factory=dict)
    """Write-ahead intent log for Phase 2 external mutations. Phase 1 can
    read legacy values without interpreting them, but its writer rejects a
    non-empty ledger. Keys and values remain broadly typed here so the normal
    read/quarantine path can hand legacy data to the strict Phase 2 model.
    """

    phase2_managed: Literal["intent-ledger-v1"] | None = None
    """Immutable Phase 2 write-path marker.

    ``None`` identifies an unmarked Phase 1 record.  The base writer may not
    introduce the marker, and once the Phase 2 Lua path stores the literal
    value it is the only write path allowed to change the execution.
    """

    context_data: Dict[str, Any] = Field(default_factory=dict)
    """Arbitrary agent context data. Not interpreted by Phase 1. The
    orchestrator and agent code store execution-specific information here.
    """

    updated_at: float = Field(default_factory=lambda: time.time())
    """Unix timestamp (float) of the last mutation. MUST use default_factory
    so a newly constructed state gets a real timestamp. Callers that mutate
    state should refresh this explicitly before each save_state call."""

    @field_validator("execution_id")
    @classmethod
    def _must_be_uuid4(cls, v: str) -> str:
        """Validate that execution_id is a well-formed UUIDv4 string.

        Raises:
            ValueError: if v is not a valid UUIDv4 string.
        """
        return validate_execution_id(v)


# ---------------------------------------------------------------------------
# CAS Lua script — the Phase 1 write path for aep:state:* keys
# ---------------------------------------------------------------------------

_CAS_SCRIPT_BODY: str = """\
-- _CAS_SCRIPT: Atomic Compare-And-Swap for AEP execution state.
--
-- KEYS[1]  = aep:state:{execution_id}   (the state key)
-- KEYS[2]  = aep:lock:{execution_id}    (the ownership lock)
-- ARGV[1]  = serialized state JSON      (the new full payload)
-- ARGV[2]  = incoming monotonic version (integer, as a string)
-- ARGV[3]  = expected stored version    (0 means the key must not exist)
-- ARGV[4]  = lock ownership token
-- ARGV[5]  = TTL in seconds             (integer, as a string; default 172800 = 48h)
--
-- Return codes:
--   1  => written successfully (new key or monotonic version increase accepted)
--  -1  => stale write: expected version mismatch or non-consecutive increment
--  -2  => stored payload is corrupt/unversioned: cjson.decode failed or the
--          decoded table has no 'version' field; no write performed (fail-closed)
--  -3  => lock missing, expired, or owned by a different token
--  -4  => Phase 2 state is present or the candidate tries to introduce it;
--          the invariant-aware Phase 2 write path is required
-- -10  => stored state is invalid UTF-8 or malformed JSON
-- -11  => stored state contains duplicate object member names
-- -12  => candidate is invalid UTF-8 or malformed/invalid state JSON
-- -13  => candidate contains duplicate object member names
--
-- Design decision: the -2 path refuses to overwrite a corrupt payload.
-- This is the Fail-Closed Invariant in action. The Python adapter is
-- responsible for quarantining the key after receiving -2. The Lua script
-- never writes a quarantine key.

-- Stored raw state is authoritative. Validate all of its bytes and JSON
-- structure before lock, version, marker, ledger, status, or retention data.
local current = redis.call("GET", KEYS[1])
if current then
    local current_check = aep_json_member_check(current)
    if current_check == 1 then return -11 end
    if current_check ~= 0 then return -10 end
end

-- The candidate crosses the same strict raw boundary before it is trusted.
local candidate_check = aep_json_member_check(ARGV[1])
if candidate_check == 1 then return -13 end
if candidate_check ~= 0 then return -12 end

if redis.call("GET", KEYS[2]) ~= ARGV[4] then return -3 end

local incoming_version = tonumber(ARGV[2])
local expected_version = tonumber(ARGV[3])
if incoming_version == nil or expected_version == nil then
    return -1
end
if incoming_version < 1 or incoming_version > 9007199254740991 or
   incoming_version % 1 ~= 0 or expected_version < 0 or
   expected_version >= 9007199254740991 or expected_version % 1 ~= 0 then
    return -1
end

local ok_candidate, candidate = pcall(cjson.decode, ARGV[1])
if (not ok_candidate) or type(candidate) ~= "table" or
   type(candidate.version) ~= "number" or
   candidate.version ~= incoming_version then
    return -12
end

local function has_marker(value)
    return value ~= nil and value ~= cjson.null
end

local function has_ledger_entries(value)
    return type(value) == "table" and next(value) ~= nil
end

if current then
    local ok, decoded = pcall(cjson.decode, current)
    -- A payload is corrupt if it failed to decode, is not a table, or its
    -- 'version' is missing OR not numeric. The "type(...) ~= 'number'" check
    -- subsumes the nil case and additionally catches a present-but-non-numeric
    -- version (e.g. a string), which must NOT be allowed to reach the
    -- subsequent tonumber(...) comparison (that crashes with "attempt to
    -- compare number with nil" under Lua). Fail-closed: return -2 and let
    -- the Python adapter quarantine + raise StateCorruptionError.
    if (not ok) or type(decoded) ~= "table" or
       type(decoded.version) ~= "number" or decoded.version < 1 or
       decoded.version > 9007199254740991 or decoded.version % 1 ~= 0 then
        return -2
    end
    if decoded.version ~= expected_version or incoming_version ~= expected_version + 1 then
        return -1
    end
    -- Authoritative Phase 2 protection is evaluated against the currently
    -- stored value after token/version fencing.  A caller with the current
    -- token and version still cannot replace marked or legacy-ledger state.
    if has_marker(decoded.phase2_managed) or
       has_ledger_entries(decoded.intent_ledger) then
        return -4
    end
else
    if expected_version ~= 0 or incoming_version ~= 1 then
        return -1
    end
end
-- The base writer cannot create Phase 2 state either.  Treat every non-empty
-- ledger as protected because the Phase 1 schema deliberately does not know
-- enough to authenticate or safely interpret Phase 2 records.
if has_marker(candidate.phase2_managed) or
   has_ledger_entries(candidate.intent_ledger) then
    return -4
end
redis.call("SET", KEYS[1], ARGV[1], "EX", ARGV[5])
return 1
"""

_CAS_SCRIPT: str = build_lua_state_validation_script(_CAS_SCRIPT_BODY)


# ---------------------------------------------------------------------------
# Schema migration registry
# ---------------------------------------------------------------------------

# Schema migration registry (per brief §4.3).
#
# Maps source schema_version (str) to a migration function. Each migrator
# receives a raw dict at the source version and must:
#   1. Transform the dict to the next version's shape.
#   2. Set raw["schema_version"] to the next version string.
#   3. Return the transformed dict.
#
# Migrators are chained automatically by _migrate_schema until
# CURRENT_SCHEMA_VERSION is reached. A missing entry for any version in
# the chain raises StateCorruptionError (fail-closed).
#
# Example migrator (commented — implement real ones as schemas evolve):
#
#   def _migrate_0_9_0_to_1_0_0(raw: Dict[str, Any]) -> Dict[str, Any]:
#       """Migrate from schema 0.9.0 to 1.0.0.
#
#       Changes:
#           - Renamed 'ledger' field to 'intent_ledger'.
#       """
#       raw["intent_ledger"] = raw.pop("ledger", {})
#       raw["schema_version"] = "1.0.0"
#       return raw
#
SCHEMA_MIGRATIONS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    # "0.9.0": _migrate_0_9_0_to_1_0_0,
}


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseStorageAdapter(ABC):
    """Abstract base for AEP state persistence adapters.

    Implementers must provide save_state and get_state. Both methods must
    honor the CAS Fencing Invariant and the Fail-Closed Invariant. No raw
    SET against state keys is permitted in any concrete implementation.
    """

    @abstractmethod
    async def save_state(
        self,
        state: "AEPExecutionState",
        *,
        expected_version: int,
        lock_token: str,
        ttl_seconds: int = 172800,
    ) -> None:
        """Persist state iff the lock is owned and expected version matches.

        Uses the base CAS Lua script (_CAS_SCRIPT). Raw SET is forbidden;
        Phase 2 mutations use their separate invariant-aware Lua path.

        Args:
            state: The AEPExecutionState to persist. state.version must equal
                expected_version + 1.
            ttl_seconds: Key expiry in seconds. Default 172800 (48 hours).
                Must be positive.

        Returns:
            None on success.

        Raises:
            StaleWriteError: expected_version does not match storage or the
                incoming version is not its exact successor. The caller must
                re-read, rebase, and retry.
            StateCorruptionError: stored payload exists but is corrupt or
                unversioned. _quarantine is called before this is raised.
                Do not retry; escalate to operator.
            StorageOperationError: Redis transport failure (network, auth,
                timeout). May be transient; orchestrator owns retry policy.
        """

    @abstractmethod
    async def get_state(
        self,
        execution_id: str,
    ) -> Optional["AEPExecutionState"]:
        """Load, migrate, and validate state for the given execution_id.

        Args:
            execution_id: The UUIDv4 string identifying the execution.

        Returns:
            AEPExecutionState if the key exists and is valid.
            None if the key does not exist (normal for new executions).

        Raises:
            StateCorruptionError: payload is unparseable, fails Pydantic
                validation, or schema migration cannot reach the current
                version. _quarantine is called before this is raised.
            StorageOperationError: execution_id key/payload mismatch, or
                Redis transport failure.
        """


# ---------------------------------------------------------------------------
# Redis implementation
# ---------------------------------------------------------------------------

#: TTL in seconds for quarantine (poison) keys. 7-day forensic window.
POISON_TTL_SECONDS: int = 7 * 24 * 3600
_SAFE_QUARANTINE_REASONS = frozenset(
    {
        "ambiguous-serialization",
        "corrupt-at-write",
        "invalid-serialization",
        "migration-failed",
        "parse-or-validation",
        "phase2-intent-validation",
    }
)


class RedisStorageAdapter(BaseStorageAdapter):
    """Redis-backed implementation of BaseStorageAdapter.

    The redis_client MUST be constructed with decode_responses=True and
    backed by a shared connection pool. Do not pass a per-call client.
    The CAS Lua script is registered once at construction time via
    register_script (EVALSHA semantics with EVAL fallback).

    Attributes:
        POISON_TTL_SECONDS: TTL for quarantine keys. 7 days by default.
    """

    POISON_TTL_SECONDS: int = 7 * 24 * 3600  # 604800 seconds = 7 days

    def __init__(self, redis_client: Redis) -> None:
        """Initialize the adapter.

        Args:
            redis_client: A pre-built redis.asyncio.Redis instance
                constructed with decode_responses=True and a shared
                connection pool. This adapter does not create its own
                connection; it reuses the provided client for all I/O.

        Post-condition:
            self._cas is bound to the compiled _CAS_SCRIPT callable.
            No network I/O is performed in __init__.
        """
        self.redis: Redis = redis_client
        self._cas = self.redis.register_script(_CAS_SCRIPT)

    # ---- write path -------------------------------------------------------

    async def save_state(
        self,
        state: AEPExecutionState,
        *,
        expected_version: int,
        lock_token: str,
        ttl_seconds: int = 172800,
    ) -> None:
        """Atomic CAS write. See BaseStorageAdapter.save_state for contract.

        Implementation notes:
            1. Serialize state through the deterministic strict state codec.
            2. Invoke self._cas with the state and lock keys plus payload,
               version, expected version, ownership token, and TTL arguments.
            3. Branch on int(result):
                 1  => return (success).
                -1  => raise StaleWriteError.
                -2  => call _quarantine(reason="corrupt-at-write"),
                       then raise StateCorruptionError.
                -3  => raise LockAcquisitionError.
                -4  => raise Phase2StateProtectionError.
               other => raise StorageOperationError (unexpected code).
            4. Any exception from the redis/Lua call itself (not a return
               code) is wrapped in StorageOperationError.

        The quarantine call on -2 is best-effort: if _quarantine raises,
        the exception is swallowed and StateCorruptionError is still raised.
        The _quarantine failure MUST NOT mask the original corruption signal.

        Pre-conditions:
            state.version >= 1 (enforced by Pydantic model field `ge=1`).
            state.execution_id is a valid UUIDv4 (enforced by validator).

        Post-conditions (on return without exception):
            aep:state:{execution_id} in Redis holds the serialized state.
            Key TTL is set to ttl_seconds.
            Stored version equals state.version.
        """
        try:
            validate_execution_id(state.execution_id)
        except ValueError:
            raise StorageOperationError(
                "execution_id must be a canonical UUIDv4 string"
            ) from None
        if state.schema_version != CURRENT_SCHEMA_VERSION:
            raise StorageOperationError(
                f"Cannot save schema_version={state.schema_version!r}; "
                f"new writes must use CURRENT_SCHEMA_VERSION="
                f"{CURRENT_SCHEMA_VERSION!r}."
            )
        if (
            isinstance(state.version, bool)
            or not isinstance(state.version, int)
            or state.version < 1
            or state.version > MAX_SAFE_VERSION
        ):
            raise StorageOperationError(
                f"version must be an integer between 1 and the Redis Lua "
                f"safe maximum {MAX_SAFE_VERSION}."
            )
        if (
            isinstance(expected_version, bool)
            or not isinstance(expected_version, int)
            or expected_version < 0
            or expected_version >= MAX_SAFE_VERSION
        ):
            raise StorageOperationError(
                f"expected_version must be an integer between 0 and "
                f"{MAX_SAFE_VERSION - 1}; the safe maximum version cannot "
                "be incremented."
            )
        if not isinstance(lock_token, str) or not lock_token:
            raise LockAcquisitionError(
                "A non-empty lock token is required to save state."
            )

        key = f"aep:state:{state.execution_id}"
        lock_key = f"aep:lock:{state.execution_id}"
        payload = encode_state(state.model_dump(mode="json"))
        try:
            result = await self._cas(
                keys=[key, lock_key],
                args=[
                    payload,
                    str(state.version),
                    str(expected_version),
                    lock_token,
                    str(ttl_seconds),
                ],
            )
        except Exception:
            raise StorageOperationError("Redis state CAS operation failed") from None

        result = int(result)
        await self._raise_lua_state_validation(
            state.execution_id,
            result,
            invalid_state_reason="corrupt-at-write",
        )
        if result == 1:
            return
        if result == -1:
            raise StaleWriteError(
                f"Stale write blocked for execution_id={state.execution_id}: "
                f"expected version {expected_version} did not match the stored "
                f"version, or incoming version {state.version} was not exactly "
                f"expected version + 1."
            )
        if result == -2:
            await self._quarantine(
                state.execution_id, reason="corrupt-at-write"
            )
            raise StateCorruptionError(
                f"Stored state for execution_id={state.execution_id} is "
                f"corrupt or unversioned; refused overwrite (fail-closed). "
                f"Quarantine key written."
            )
        if result == -3:
            raise LockAcquisitionError(
                f"State write rejected for execution_id={state.execution_id}: "
                "lock token is missing, expired, or not the current owner."
            )
        if result == -4:
            raise Phase2StateProtectionError(
                f"Base state write rejected for execution_id="
                f"{state.execution_id}: Phase 2 state can be created or "
                "modified only by the invariant-aware intent ledger path."
            )
        raise StorageOperationError(
            f"Unexpected CAS return code {result} for "
            f"execution_id={state.execution_id}."
        )

    # ---- read path --------------------------------------------------------

    async def get_state(
        self,
        execution_id: str,
    ) -> Optional[AEPExecutionState]:
        """Load, migrate, validate. See BaseStorageAdapter.get_state for
        contract.

        Implementation steps:
            1. redis.get(key). On exception: raise StorageOperationError.
            2. If raw is None: return None (not an error).
            3. Decode through the strict state codec. On invalid or ambiguous
               JSON: quarantine
               (reason="parse-or-validation", raw=raw) + raise
               StateCorruptionError.
            4. If state_dict["schema_version"] != CURRENT_SCHEMA_VERSION:
               call _migrate_schema(state_dict). _migrate_schema may raise
               StateCorruptionError (unknown version or convergence failure);
               if it does, quarantine then re-raise.
            5. AEPExecutionState.model_validate(state_dict). On
               ValidationError or any ValueError: quarantine
               (reason="parse-or-validation", raw=raw) + raise
               StateCorruptionError.
            6. If validated.execution_id != execution_id: raise
               StorageOperationError (key/payload mismatch). No quarantine
               for this case — the data itself may be valid, just stored
               under the wrong key.
            7. Return validated.

        The quarantine call in steps 3-5 is best-effort: if _quarantine
        raises internally, the exception is swallowed and the original
        corruption exception is still raised.

        Post-conditions (on return of a non-None value):
            returned.execution_id == execution_id
            returned is a fully validated AEPExecutionState.
        """
        try:
            validate_execution_id(execution_id)
        except ValueError:
            raise StorageOperationError(
                "execution_id must be a canonical UUIDv4 string"
            ) from None
        key = f"aep:state:{execution_id}"
        try:
            raw = await self._read_raw_state(key)
        except UnicodeError:
            await self._quarantine(
                execution_id, reason="invalid-serialization"
            )
            raise StateCorruptionError(
                f"State for execution_id={execution_id} failed strict "
                "serialization validation"
            ) from None
        except Exception:
            raise StorageOperationError("Redis state read operation failed") from None

        if raw is None:
            return None

        try:
            state_dict = decode_state(raw)
        except AmbiguousStateError:
            await self._quarantine(
                execution_id, reason="ambiguous-serialization", raw=raw
            )
            raise
        except StateCorruptionError:
            await self._quarantine(
                execution_id, reason="parse-or-validation", raw=raw
            )
            raise StateCorruptionError(
                f"State for execution_id={execution_id} failed parse/validation"
            ) from None

        try:
            if state_dict.get("schema_version") != CURRENT_SCHEMA_VERSION:
                state_dict = await self._migrate_schema(state_dict)
            validated = AEPExecutionState.model_validate(state_dict)
        except StateCorruptionError:
            # _migrate_schema already classified this. Quarantine with the
            # raw bytes, then re-raise so the original message is preserved.
            await self._quarantine(
                execution_id, reason="migration-failed", raw=raw
            )
            raise
        except Exception:
            # ValidationError is a subclass of ValueError in Pydantic v2.
            # Any failure that prevents producing a valid model is corruption.
            await self._quarantine(
                execution_id, reason="parse-or-validation", raw=raw
            )
            raise StateCorruptionError(
                f"State for execution_id={execution_id} failed "
                "parse/validation"
            ) from None

        if validated.execution_id != execution_id:
            raise StorageOperationError(
                f"Key/payload mismatch: key suffix is {execution_id!r}, "
                f"but payload claims execution_id={validated.execution_id!r}. "
                f"This indicates data corruption or an operator error."
            )
        return validated

    async def _read_raw_state(self, key: str) -> bytes | None:
        """Read exact Redis bytes even when the shared client decodes text."""

        return await self.redis.execute_command(
            "GET", key, **{NEVER_DECODE: True}
        )

    async def _raise_lua_state_validation(
        self,
        execution_id: str,
        code: int,
        *,
        invalid_state_reason: str | None = None,
    ) -> None:
        """Apply the central raw-state result mapping and quarantine policy."""

        failure = lua_state_validation_failure(code)
        if failure is None:
            return
        error, quarantine_reason = failure
        if (
            quarantine_reason == "invalid-serialization"
            and invalid_state_reason is not None
        ):
            quarantine_reason = invalid_state_reason
        if quarantine_reason is not None:
            await self._quarantine(execution_id, reason=quarantine_reason)
        raise error

    # ---- migration (fail-closed on unknown version) -----------------------

    async def _migrate_schema(
        self,
        raw_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Walk the SCHEMA_MIGRATIONS chain from the stored schema_version
        to CURRENT_SCHEMA_VERSION.

        Each migrator in SCHEMA_MIGRATIONS is keyed by its source version.
        It must return a dict with an updated 'schema_version' field pointing
        to the next version in the chain.

        Args:
            raw_state: The decoded JSON dict from Redis. Must contain a
                'schema_version' key (may be None or missing if corrupt).

        Returns:
            The migrated raw dict at CURRENT_SCHEMA_VERSION.

        Raises:
            StateCorruptionError: if any of the following occur:
                - SCHEMA_MIGRATIONS has no entry for the current from_version
                  (unknown version, no migration path — fail-closed per the
                  Fail-Closed Invariant).
                - The migration chain does not converge within 50 iterations
                  (cyclic migrator bug — loop guard is a safety cap).

        Note: this method does NOT call _quarantine itself. The caller
        (get_state) is responsible for quarantining after catching
        StateCorruptionError from here.
        """
        from_version = raw_state.get("schema_version")
        guard = 0
        while from_version != CURRENT_SCHEMA_VERSION:
            guard += 1
            if guard > 50:
                raise StateCorruptionError(
                    "Schema migration chain did not converge within 50 "
                    "iterations. Possible cyclic migrator in SCHEMA_MIGRATIONS."
                )
            migrator = SCHEMA_MIGRATIONS.get(from_version)
            if migrator is None:
                raise StateCorruptionError(
                    "No migration path exists for the stored schema version; "
                    "the execution cannot be recovered (fail-closed)."
                )
            raw_state = migrator(raw_state)
            from_version = raw_state.get("schema_version")
        return raw_state

    # ---- poison-message quarantine ----------------------------------------

    async def _quarantine(
        self,
        execution_id: str,
        reason: str,
        raw: Any = None,
    ) -> None:
        """Best-effort write of a poison/quarantine record to Redis.

        Writes to aep:poison:{execution_id}:{epoch_ms} with a 7-day TTL.
        If the raw bytes are not provided, attempts to read the current
        value of aep:state:{execution_id} only to derive bounded safe metadata.

        This method MUST swallow all exceptions. It is called immediately
        before raising StateCorruptionError in save_state and get_state.
        If quarantine itself fails (e.g., Redis is down), the original
        corruption error must still be raised. The quarantine failure MUST
        NOT replace or suppress the original exception.

        Args:
            execution_id: The UUIDv4 of the affected execution.
            reason: Short descriptor, e.g. "corrupt-at-write",
                "parse-or-validation", "migration-failed".
            raw: The raw bytes/string to classify. If None, the adapter
                attempts to read aep:state:{execution_id} for forensic
                value.

        Post-condition (best-effort):
            aep:poison:{execution_id}:{epoch_ms} exists in Redis with a
            7-day TTL and a JSON body containing only a bounded reason,
            presence flag, byte length, and encoding class. Raw state is never
            duplicated into quarantine.

        Orchestrator responsibility (Phase 2):
            Scanning aep:poison:* keys, marking executions FAILED on the
            dashboard, and ejecting them from active scheduling. Storage
            owns the WRITE; the orchestrator owns the SCHEDULING EJECTION.
        """
        import time as _time
        poison_key = f"aep:poison:{execution_id}:{int(_time.time() * 1000)}"
        safe_reason = (
            reason
            if isinstance(reason, str) and reason in _SAFE_QUARANTINE_REASONS
            else "parse-or-validation"
        )
        try:
            if raw is None:
                raw = await self._read_raw_state(
                    f"aep:state:{execution_id}"
                )
            raw_present = raw is not None
            raw_encoding = "none"
            raw_length = 0
            if isinstance(raw, (bytes, bytearray)):
                raw_bytes = bytes(raw)
                raw_length = len(raw_bytes)
                try:
                    raw_bytes.decode("utf-8", errors="strict")
                    raw_encoding = "utf8"
                except UnicodeDecodeError:
                    raw_encoding = "binary"
            elif isinstance(raw, str):
                raw_length = len(raw.encode("utf-8", errors="replace"))
                raw_encoding = "utf8"
            elif raw is not None:
                raw_encoding = "unsupported"
            await self.redis.set(
                poison_key,
                encode_state(
                    {
                        "reason": safe_reason,
                        "raw_present": raw_present,
                        "raw_length": raw_length,
                        "raw_encoding": raw_encoding,
                    }
                ),
                ex=self.POISON_TTL_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001 -- intentional broad catch
            # Quarantine is best-effort telemetry. Swallow all failures so
            # the original corruption signal is not masked (the caller will
            # still raise StateCorruptionError). Emit a WARNING so an
            # operator debugging a corruption event sees that the quarantine
            # write itself failed — previously this branch was a silent
            # pass and bandit flagged it as B110 (try_except_pass) with
            # zero observability. The warning does NOT re-raise.
            logger.warning(
                "AEP _quarantine best-effort write failed for "
                "execution_id=%s reason=%s failure_class=%s",
                execution_id,
                safe_reason,
                type(exc).__name__,
            )
