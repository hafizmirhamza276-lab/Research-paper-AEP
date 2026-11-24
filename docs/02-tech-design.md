# Agent Execution Protocol (AEP) — Phase 1 Technical Design

**Document Version:** 1.0.0
**Date:** 2026-05-22
**Status:** Implementation-Ready
**Supersedes:** (none; this is the first tech-design pass)
**Next Deliverable:** `src/core/exceptions.py`, `src/core/storage.py`, `src/core/locks.py`, `tests/`

---

## 1. Reference & Alignment

### 1.1 Governing Documents

| Document | Role |
|---|---|
| `docs/01-hld.md` | Approved Phase 1 High-Level Design (prior orchestrator deliverable). |
| `.claude/skills/aep-context/references/brief.md` v2.1.0 | Primary implementation brief; governs §§3–5, §8. |
| `.claude/skills/aep-context/SKILL.md` | Canonical invariants and honest-guarantee rule. |
| `.claude/skills/redis-async-patterns/SKILL.md` | Async client, Lua, and lease patterns. |

### 1.2 Brief Sections That Govern This Design

- **§2** — Global invariants (Timeout, CAS Fencing, Fail-Closed). All three are binding.
- **§3** — Exception hierarchy class names, inheritance, and docstrings.
- **§4** — `AEPExecutionState` schema, `_CAS_SCRIPT` Lua, adapter contracts, SCHEMA_MIGRATIONS, quarantine behavior.
- **§5** — Lua scripts for lock release/renew, `DistributedLockManager` contracts, lease policy hard contract.
- **§7** — Phase 2 interface surfaces that Phase 1 primitives must expose without modification.
- **§8** — Cross-cutting implementation requirements (single client, `register_script`, decode_responses, type hints).

### 1.3 HLD Correction: Quarantine Attribution on CAS `-2`

HLD §7 describes the corrupt-at-write row as follows: "Quarantine key already written by Lua path (pending Phase 2 cleanup)." This is incorrect and is corrected here.

**Correct behavior (per brief §4.3 and the Fail-Closed Invariant):** the Lua `_CAS_SCRIPT` returns `-2` and does NOT write a quarantine key. The `-2` return code is an observation code only. The **Python adapter** (`RedisStorageAdapter.save_state`) receives the `-2` return, calls `self._quarantine(execution_id, reason="corrupt-at-write")` as a best-effort operation, and then raises `StateCorruptionError`. Lua never performs quarantine writes; all quarantine I/O is in Python.

This distinction matters for the implementer: if `_quarantine` itself raises, the exception is swallowed (so as not to mask the original corruption signal), and `StateCorruptionError` is still raised to the caller.

---

## 2. Module: `src/core/exceptions.py`

### 2.1 Exception Hierarchy

The five classes below are the complete exception surface for AEP Phase 1. The orchestrator branches on exception type to determine reaction: retry vs. fence vs. quarantine vs. alert.

```python
class AEPException(Exception):
    """Baseline for all AEP core errors.

    Catch this to handle any AEP failure generically. Do not raise this
    directly — raise a specific subclass so the orchestrator can branch
    on root cause.
    """


class StorageOperationError(AEPException):
    """Transport/driver failure or an integrity violation that is NOT
    corruption and NOT a stale write.

    Examples:
        - Redis network fault or authentication failure.
        - execution_id key/payload mismatch (key is aep:state:X, payload
          claims execution_id Y).

    Retry semantics: retryable ONLY if the root cause is a transient
    transport error. The orchestrator must inspect the message to
    determine whether the cause is transient before scheduling a retry.
    An execution_id mismatch is not retryable; escalate to operator.
    """


class StaleWriteError(StorageOperationError):
    """The incoming state version is not strictly greater than the stored
    version.

    This is EXPECTED under contention (two workers race to save; the
    slower one is fenced). It is NOT a bug.

    Retry semantics: NOT retryable as-is. The worker must re-read current
    state, rebase its local changes onto the updated version, and retry
    the CAS with the new (incremented) version. Retrying with the same
    version will always fail again.

    Raised by: RedisStorageAdapter.save_state when _CAS_SCRIPT returns -1.
    """


class StateCorruptionError(StorageOperationError):
    """Stored payload is unparseable, fails Pydantic validation, has no
    usable version field, or the schema migration chain cannot reach the
    current schema version.

    Retry semantics: NOT retryable. This is a data integrity failure.
    The adapter's _quarantine() is called before this exception is raised;
    the orchestrator must then mark the execution FAILED and eject it from
    active scheduling (Phase 2 concern).

    Per the Fail-Closed Invariant: corrupt payloads are quarantined, not
    silently overwritten or healed. Never catch this to continue silently.

    Raised by:
        - RedisStorageAdapter.save_state when _CAS_SCRIPT returns -2
          (after _quarantine is called).
        - RedisStorageAdapter.get_state when JSON decode fails, Pydantic
          validation fails, or schema migration fails (after _quarantine
          is called).
        - RedisStorageAdapter._migrate_schema when no migration path exists
          or the migration chain does not converge within 50 steps.
    """


class LockAcquisitionError(AEPException):
    """Lock engine communication fault or an invalid lease operation.

    Note: the plain "lock not available" case is NOT this exception.
    acquire_lock() returns None (not an error) when the lock is held by
    another worker. This exception signals an inability to communicate
    with the lock engine, or a programming error such as calling release
    with an invalid token type.

    Raised by: DistributedLockManager.acquire_lock, release_lock,
    renew_lock on Redis transport failure.
    """
```

### 2.2 Inheritance Summary

```
Exception
└── AEPException
    ├── StorageOperationError
    │   ├── StaleWriteError
    │   └── StateCorruptionError
    └── LockAcquisitionError
```

### 2.3 Definition of Done — Exceptions

- All five classes exist with docstrings as above.
- `StaleWriteError` and `StateCorruptionError` are subclasses of `StorageOperationError`.
- `StorageOperationError` and `LockAcquisitionError` are subclasses of `AEPException`.
- Module is importable without side effects (no I/O, no network, no global state).
- No other exceptions are defined in this module.

---

## 3. Module: `src/core/storage.py`

### 3.1 Pydantic v2 Schema

#### 3.1.1 `AEPStatus` Enum

```python
import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator


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
```

#### 3.1.2 `CURRENT_SCHEMA_VERSION`

```python
CURRENT_SCHEMA_VERSION: str = "1.0.0"
```

This constant is referenced by both the schema default and `_migrate_schema`. It MUST be updated whenever a new schema version is introduced (and a corresponding migrator added to `SCHEMA_MIGRATIONS`).

#### 3.1.3 `AEPExecutionState` Model

```python
class AEPExecutionState(BaseModel):
    """Pydantic v2 model representing the full state of an AEP execution.

    Serialization: use model_dump_json() for Redis storage. Use
    model_validate(dict) or model_validate_json(str) for deserialization.

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

    version: int = Field(default=1, ge=1)
    """Monotonic fencing counter. Starts at 1. Must increase strictly on
    every mutation. Never decremented. The CAS Lua script rejects writes
    where the incoming version is not strictly greater than the stored one.
    """

    schema_version: str = Field(default=CURRENT_SCHEMA_VERSION)
    """Data schema version string. Used by _migrate_schema to walk the
    SCHEMA_MIGRATIONS chain on read. Must be bumped when the model fields
    change in a backwards-incompatible way."""

    intent_ledger: Dict[str, Any] = Field(default_factory=dict)
    """Write-ahead intent log for Phase 2 external mutations. Phase 1
    persists this field without interpreting it. Keys are step identifiers;
    values are dicts with at minimum a 'status' key. Arbitrary structure
    is permitted so Phase 2 can evolve the schema without modifying Phase 1.
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
        try:
            uuid.UUID(v, version=4)
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError(
                f"execution_id must be a UUIDv4 string, got: {v!r}"
            ) from exc
        return v
```

**Field summary:**

| Field | Type | Default | Constraint |
|---|---|---|---|
| `execution_id` | `str` | required | UUIDv4; validated by `_must_be_uuid4` |
| `status` | `AEPStatus` | required | one of the six enum values |
| `version` | `int` | `1` | `>= 1`; monotonically increasing across saves |
| `schema_version` | `str` | `CURRENT_SCHEMA_VERSION` | walked by migration chain |
| `intent_ledger` | `Dict[str, Any]` | `{}` | arbitrary; Phase 2 owned |
| `context_data` | `Dict[str, Any]` | `{}` | arbitrary; agent owned |
| `updated_at` | `float` | `time.time()` at construction | Unix epoch float; caller refreshes on mutation |

---

### 3.2 The Atomic CAS Write Script

#### 3.2.1 Module-Level Declaration

`_CAS_SCRIPT` is defined as a module-level string constant in `src/core/storage.py`. It is the **only** path by which a state key may be written. Raw `SET` against an `aep:state:*` key is forbidden throughout the codebase.

#### 3.2.2 Lua Script Source

```lua
-- _CAS_SCRIPT: Atomic Compare-And-Swap for AEP execution state.
--
-- KEYS[1]  = aep:state:{execution_id}   (the state key)
-- ARGV[1]  = serialized state JSON      (the new full payload)
-- ARGV[2]  = incoming monotonic version (integer, as a string)
-- ARGV[3]  = TTL in seconds             (integer, as a string; default 172800 = 48h)
--
-- Return codes:
--   1  => written successfully (new key or monotonic version increase accepted)
--  -1  => stale write: stored version >= incoming version; no write performed
--  -2  => stored payload is corrupt/unversioned: cjson.decode failed or the
--          decoded table has no 'version' field; no write performed (fail-closed)
--
-- Design decision: the -2 path refuses to overwrite a corrupt payload.
-- This is the Fail-Closed Invariant in action. The Python adapter is
-- responsible for quarantining the key after receiving -2. The Lua script
-- never writes a quarantine key.

local current = redis.call("GET", KEYS[1])
if current then
    local ok, decoded = pcall(cjson.decode, current)
    if (not ok) or type(decoded) ~= "table" or decoded.version == nil then
        return -2
    end
    if tonumber(decoded.version) >= tonumber(ARGV[2]) then
        return -1
    end
end
redis.call("SET", KEYS[1], ARGV[1], "EX", ARGV[3])
return 1
```

#### 3.2.3 Return Code Semantics

| Return Code | Meaning | Python Adapter Action |
|---|---|---|
| `1` | Written successfully. Either the key was absent (first write) or the incoming version strictly exceeded the stored version. | Return normally. |
| `-1` | Stale write. `tonumber(stored.version) >= tonumber(ARGV[2])`. No write was performed. | Raise `StaleWriteError`. No quarantine. |
| `-2` | Stored payload is corrupt or unversioned. `cjson.decode` failed, result is not a table, or the table has no `version` field. No write was performed. | Call `_quarantine(reason="corrupt-at-write")`, then raise `StateCorruptionError`. |

#### 3.2.4 Registration via `register_script`

In `RedisStorageAdapter.__init__`, the script is bound once:

```python
self._cas = self.redis.register_script(_CAS_SCRIPT)
```

`register_script` returns a callable that uses `EVALSHA` under the hood and falls back to `EVAL` on a cache miss. No manual script-hash management is required. The bound callable is invoked per brief §4.3:

```python
result = await self._cas(
    keys=[key],
    args=[payload, str(state.version), str(ttl_seconds)],
)
```

`cjson` is a standard Lua library bundled with Redis 7.x. It is available without any additional configuration. If running tests against `fakeredis`, verify `cjson` support before relying on it for CAS tests (per brief §9); use a real Redis container if the fake lacks `cjson`.

#### 3.2.5 Design Decision: Fail-Closed on `-2`

The `-2` path is an explicit design decision documented in the Lua source and restated here for maintainers: a corrupt stored payload halts the write rather than allowing an overwrite. The monotonic guarantee exists only because every stored payload has a parseable version. Silently overwriting a corrupt payload would skip the version check, violating the CAS Fencing Invariant. Any future operator who wants to change this behavior MUST explicitly change the `-2` branch to fall through to `SET` and MUST accept that the monotonic guarantee is abandoned for that write.

---

### 3.3 `BaseStorageAdapter` ABC

```python
from abc import ABC, abstractmethod
from typing import Optional


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
        ttl_seconds: int = 172800,
    ) -> None:
        """Persist state atomically iff incoming version > stored version.

        Uses the CAS Lua script (_CAS_SCRIPT) as the sole write path. Raw
        SET is forbidden.

        Args:
            state: The AEPExecutionState to persist. state.version must be
                strictly greater than the currently stored version (if any).
            ttl_seconds: Key expiry in seconds. Default 172800 (48 hours).
                Must be positive.

        Returns:
            None on success.

        Raises:
            StaleWriteError: incoming version is not strictly greater than
                the stored version. The caller must re-read, rebase, and
                retry with an incremented version.
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
```

---

### 3.4 `RedisStorageAdapter`

#### 3.4.1 `__init__`

```python
from redis.asyncio import Redis


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
```

#### 3.4.2 `save_state`

```python
    async def save_state(
        self,
        state: AEPExecutionState,
        ttl_seconds: int = 172800,
    ) -> None:
        """Atomic CAS write. See BaseStorageAdapter.save_state for contract.

        Implementation notes:
            1. Serialize state to JSON via model_dump_json().
            2. Invoke self._cas with keys=[state_key], args=[payload,
               str(state.version), str(ttl_seconds)].
            3. Branch on int(result):
                 1  => return (success).
                -1  => raise StaleWriteError.
                -2  => call _quarantine(reason="corrupt-at-write"),
                       then raise StateCorruptionError.
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
        key = f"aep:state:{state.execution_id}"
        payload = state.model_dump_json()
        try:
            result = await self._cas(
                keys=[key],
                args=[payload, str(state.version), str(ttl_seconds)],
            )
        except Exception as exc:
            raise StorageOperationError(
                f"Redis transport failure on save_state: {exc}"
            ) from exc

        result = int(result)
        if result == 1:
            return
        if result == -1:
            raise StaleWriteError(
                f"Stale write blocked for execution_id={state.execution_id}: "
                f"incoming version={state.version} is not strictly greater "
                f"than the stored version."
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
        raise StorageOperationError(
            f"Unexpected CAS return code {result} for "
            f"execution_id={state.execution_id}."
        )
```

#### 3.4.3 `get_state`

```python
    async def get_state(
        self,
        execution_id: str,
    ) -> Optional[AEPExecutionState]:
        """Load, migrate, validate. See BaseStorageAdapter.get_state for
        contract.

        Implementation steps:
            1. redis.get(key). On exception: raise StorageOperationError.
            2. If raw is None: return None (not an error).
            3. Attempt json.loads(raw). On JSONDecodeError: quarantine
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

        The quarantine call in steps 3–5 is best-effort: if _quarantine
        raises internally, the exception is swallowed and the original
        corruption exception is still raised.

        Post-conditions (on return of a non-None value):
            returned.execution_id == execution_id
            returned is a fully validated AEPExecutionState.
        """
        key = f"aep:state:{execution_id}"
        try:
            raw = await self.redis.get(key)
        except Exception as exc:
            raise StorageOperationError(
                f"Redis transport failure on get_state: {exc}"
            ) from exc

        if raw is None:
            return None

        try:
            state_dict = json.loads(raw)
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
        except (json.JSONDecodeError, ValueError, Exception) as exc:
            # ValidationError is a subclass of ValueError in Pydantic v2.
            # Any failure that prevents producing a valid model is corruption.
            await self._quarantine(
                execution_id, reason="parse-or-validation", raw=raw
            )
            raise StateCorruptionError(
                f"State for execution_id={execution_id} failed "
                f"parse/validation: {exc}"
            ) from exc

        if validated.execution_id != execution_id:
            raise StorageOperationError(
                f"Key/payload mismatch: key suffix is {execution_id!r}, "
                f"but payload claims execution_id={validated.execution_id!r}. "
                f"This indicates data corruption or an operator error."
            )
        return validated
```

#### 3.4.4 `_migrate_schema`

```python
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
                    f"No migration path from schema_version={from_version!r} "
                    f"to {CURRENT_SCHEMA_VERSION!r}. Register a migrator in "
                    f"SCHEMA_MIGRATIONS or this execution cannot be recovered "
                    f"(fail-closed per the Fail-Closed Invariant)."
                )
            raw_state = migrator(raw_state)
            from_version = raw_state.get("schema_version")
        return raw_state
```

#### 3.4.5 `_quarantine`

```python
    async def _quarantine(
        self,
        execution_id: str,
        reason: str,
        raw: Any = None,
    ) -> None:
        """Best-effort write of a poison/quarantine record to Redis.

        Writes to aep:poison:{execution_id}:{epoch_ms} with a 7-day TTL.
        If the raw bytes are not provided, attempts to read the current
        value of aep:state:{execution_id} to preserve forensic evidence.

        This method MUST swallow all exceptions. It is called immediately
        before raising StateCorruptionError in save_state and get_state.
        If quarantine itself fails (e.g., Redis is down), the original
        corruption error must still be raised. The quarantine failure MUST
        NOT replace or suppress the original exception.

        Args:
            execution_id: The UUIDv4 of the affected execution.
            reason: Short descriptor, e.g. "corrupt-at-write",
                "parse-or-validation", "migration-failed".
            raw: The raw bytes/string to preserve. If None, the adapter
                attempts to read aep:state:{execution_id} for forensic
                value.

        Post-condition (best-effort):
            aep:poison:{execution_id}:{epoch_ms} exists in Redis with a
            7-day TTL and a JSON body containing 'reason' and 'raw'.

        Orchestrator responsibility (Phase 2):
            Scanning aep:poison:* keys, marking executions FAILED on the
            dashboard, and ejecting them from active scheduling. Storage
            owns the WRITE; the orchestrator owns the SCHEDULING EJECTION.
        """
        import time as _time
        poison_key = f"aep:poison:{execution_id}:{int(_time.time() * 1000)}"
        try:
            if raw is None:
                raw = await self.redis.get(f"aep:state:{execution_id}")
            await self.redis.set(
                poison_key,
                json.dumps({"reason": reason, "raw": raw}),
                ex=self.POISON_TTL_SECONDS,
            )
        except Exception:
            # Quarantine is best-effort telemetry. Swallow all failures so
            # the original corruption signal is not masked. The absence of
            # a quarantine key does not change the safety outcome; the caller
            # will still raise StateCorruptionError.
            pass
```

---

### 3.5 `SCHEMA_MIGRATIONS` Registry

```python
from typing import Callable, Dict, Any

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
```

The registry is empty in Phase 1 because `CURRENT_SCHEMA_VERSION` is the first version and no prior data exists to migrate. The registry is populated only when a new schema version is introduced in a future release.

---

### 3.6 Storage Definition of Done (per brief §4.4)

All of the following must pass before storage is considered complete:

- Valid round-trip: `save_state(state)` followed by `get_state(state.execution_id)` returns an equal model.
- First write (key absent) succeeds (CAS returns `1`).
- Strictly increasing version increments all succeed.
- Equal or lower version on write raises `StaleWriteError` (CAS returns `-1`).
- Corrupt stored payload at write time raises `StateCorruptionError` with no overwrite (CAS returns `-2`); quarantine key is written before the exception surfaces.
- `get_state` on a missing key returns `None`.
- Non-JSON payload in Redis triggers quarantine key creation and raises `StateCorruptionError`.
- Schema-invalid JSON payload (valid JSON but fails Pydantic validation) triggers quarantine and raises `StateCorruptionError`.
- Unknown `schema_version` with no entry in `SCHEMA_MIGRATIONS` raises `StateCorruptionError` (fail-closed).
- A registered migrator in `SCHEMA_MIGRATIONS` is walked and the result is validated and returned.
- `execution_id` key/payload mismatch raises `StorageOperationError` (no quarantine).
- `_quarantine` never raises its own error over the original corruption error.
- `_CAS_SCRIPT` is the only write path to `aep:state:*` keys throughout the codebase.

---

## 4. Module: `src/core/locks.py`

### 4.1 Lua Scripts

Both scripts are defined as module-level string constants. Both are registered via `register_script` in `DistributedLockManager.__init__`.

#### 4.1.1 `_RELEASE_SCRIPT`

```lua
-- _RELEASE_SCRIPT: Token-checked atomic lock release.
--
-- KEYS[1] = aep:lock:{execution_id}
-- ARGV[1] = ownership token (secrets value; not the fencing token)
--
-- Returns:
--   1  => lock was held by this token; deleted successfully.
--   0  => token mismatch or key does not exist (lock expired or
--          already held by another worker). The Python caller MUST
--          log a warning: this is a CRITICAL signal that the lease
--          may have expired and overlap may have occurred.
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
```

#### 4.1.2 `_RENEW_SCRIPT`

```lua
-- _RENEW_SCRIPT: Token-checked atomic TTL extension.
--
-- KEYS[1] = aep:lock:{execution_id}
-- ARGV[1] = ownership token
-- ARGV[2] = new TTL in milliseconds (PEXPIRE takes ms)
--
-- Returns:
--   1  => token matched; PEXPIRE applied (TTL extended).
--   0  => token mismatch or key expired. The caller MUST treat
--          itself as lock-less and fail-closed immediately.
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("PEXPIRE", KEYS[1], ARGV[2])
else
    return 0
end
```

---

### 4.2 `DistributedLockManager`

#### 4.2.1 Module-Level Logger

```python
import logging

logger = logging.getLogger("aep.locks")
```

All warning and error log calls in this module use this logger. The `aep.locks` name allows operators to configure lock-specific log levels independently.

#### 4.2.2 `__init__`

```python
import asyncio
import contextlib
import secrets
from typing import AsyncIterator, Optional

from redis.asyncio import Redis

from src.core.exceptions import LockAcquisitionError


class DistributedLockManager:
    """Distributed lease lock backed by a single Redis instance.

    Provides acquire/release/renew primitives and an auto-renewing lease
    context manager with a hard cap.

    The lock provides an OWNERSHIP signal (who holds the lease), not a
    FENCING guarantee. Concurrent overlap is still possible if the lease
    expires mid-operation. Overlap is made detectable by the monotonic
    version CAS in storage.py (the CAS Fencing Invariant), not by this
    lock alone.

    The honest guarantee: corruption and contention are detectable, and
    the system fails closed.
    """

    def __init__(self, redis_client: Redis) -> None:
        """Initialize the lock manager.

        Args:
            redis_client: A pre-built redis.asyncio.Redis instance
                constructed with decode_responses=True and a shared
                connection pool. Shared with RedisStorageAdapter — do not
                create a separate client.

        Post-condition:
            self._release and self._renew are bound to the compiled Lua
            script callables via register_script. No network I/O in __init__.
        """
        self.redis: Redis = redis_client
        self._release = self.redis.register_script(_RELEASE_SCRIPT)
        self._renew = self.redis.register_script(_RENEW_SCRIPT)
```

#### 4.2.3 `acquire_lock`

```python
    async def acquire_lock(
        self,
        execution_id: str,
        ttl_seconds: int = 60,
    ) -> Optional[str]:
        """Attempt to acquire the lock for the given execution_id.

        Uses SET NX EX for an atomic acquire. The returned token is a
        random ownership token (secrets.token_urlsafe(32)) — it is NOT the
        monotonic fencing token. Do not use it for CAS versioning.

        Args:
            execution_id: The UUIDv4 of the execution to lock.
            ttl_seconds: Lock TTL in seconds. Default 60. Must be sized
                so that T_client <= ttl_seconds - 15 (Timeout Invariant).

        Returns:
            A random token string on successful acquisition.
            None if the lock is already held by another worker. None is
            NOT an error; the orchestrator owns backoff/retry policy.

        Raises:
            LockAcquisitionError: on Redis transport failure (network,
                auth, timeout). Not raised for "lock unavailable."

        Post-condition (on return of a token):
            aep:lock:{execution_id} exists in Redis with TTL = ttl_seconds
            and value = token.
        """
        key = f"aep:lock:{execution_id}"
        token = secrets.token_urlsafe(32)
        try:
            acquired = await self.redis.set(key, token, nx=True, ex=ttl_seconds)
        except Exception as exc:
            raise LockAcquisitionError(
                f"Lock engine fault on acquire for execution_id={execution_id}: {exc}"
            ) from exc
        return token if acquired else None
```

#### 4.2.4 `release_lock`

```python
    async def release_lock(
        self,
        execution_id: str,
        lock_token: str,
    ) -> bool:
        """Release the lock only if the token still matches.

        Uses _RELEASE_SCRIPT for an atomic token check + DEL.

        Args:
            execution_id: The UUIDv4 of the execution to unlock.
            lock_token: The ownership token returned by acquire_lock.

        Returns:
            True if the lock was held by this token and was deleted.
            False if the token did not match (lock expired or re-acquired
            by another worker). False is a CRITICAL signal: potential
            overlap has occurred. A warning is logged via logger.warning.

        Raises:
            LockAcquisitionError: on Redis transport failure.

        Post-condition (on return True):
            aep:lock:{execution_id} does not exist in Redis.
        """
        key = f"aep:lock:{execution_id}"
        try:
            result = await self._release(keys=[key], args=[lock_token])
        except Exception as exc:
            raise LockAcquisitionError(
                f"Lock release fault for execution_id={execution_id}: {exc}"
            ) from exc
        if int(result) == 0:
            logger.warning(
                "AEP lock release returned 0 for execution_id=%s: lease "
                "expired or re-acquired by another worker. Possible overlap "
                "occurred. Review logs for concurrent activity.",
                execution_id,
            )
            return False
        return True
```

#### 4.2.5 `renew_lock`

```python
    async def renew_lock(
        self,
        execution_id: str,
        lock_token: str,
        extend_ms: int = 30000,
    ) -> bool:
        """Extend the lock TTL atomically only if the token still matches.

        Uses _RENEW_SCRIPT for an atomic token check + PEXPIRE. PEXPIRE
        takes milliseconds; use extend_ms for sub-second precision.

        Args:
            execution_id: The UUIDv4 of the execution whose lock to extend.
            lock_token: The ownership token from acquire_lock.
            extend_ms: New TTL in milliseconds. Default 30000 (30s).

        Returns:
            True if the token matched and TTL was extended.
            False if the token no longer matches (lock expired or
            re-acquired). The caller MUST stop all work immediately on
            False — it no longer owns the lock (Fail-Closed Invariant).

        Raises:
            LockAcquisitionError: on Redis transport failure.
        """
        key = f"aep:lock:{execution_id}"
        try:
            result = await self._renew(
                keys=[key], args=[lock_token, str(extend_ms)]
            )
        except Exception as exc:
            raise LockAcquisitionError(
                f"Lock renew fault for execution_id={execution_id}: {exc}"
            ) from exc
        return int(result) == 1
```

#### 4.2.6 `lease` — Auto-Renewing Context Manager

```python
    @contextlib.asynccontextmanager
    async def lease(
        self,
        execution_id: str,
        ttl_seconds: int = 60,
        max_total_lease_seconds: int = 600,
    ) -> AsyncIterator[Optional[str]]:
        """Acquire a lock and auto-renew it in the background up to a hard cap.

        Heartbeat interval is ttl_seconds / 3 (minimum 1s). Each heartbeat
        calls renew_lock with extend_ms = ttl_seconds * 1000.

        Hard cap behavior (Fail-Closed Invariant):
            When elapsed renewal time reaches max_total_lease_seconds, the
            heartbeat task stops renewing. The lock TTL is allowed to expire
            naturally. The lock is NOT explicitly released after cap; the
            caller's finally block still calls release_lock, but by then the
            lock may already be expired (release returns False, warning logged).

        Heartbeat False behavior:
            If renew_lock returns False during a heartbeat, the task stops
            renewing and logs a warning. The caller's code continues executing
            (yield has already happened), but the lock is effectively lost.
            Operators MUST monitor these log warnings and cease the caller's
            work on detection.

        Args:
            execution_id: The UUIDv4 of the execution to lock.
            ttl_seconds: Per-renewal TTL in seconds. Default 60.
                Must satisfy Timeout Invariant: T_client <= ttl_seconds - 15.
            max_total_lease_seconds: Hard ceiling on total auto-renewal
                duration. Default 600 (10 minutes). Once elapsed, renewal
                stops and the lock expires (fail-closed). No exceptions.

        Yields:
            The ownership token (str) on successful acquisition.
            None if the lock could not be acquired. The caller MUST check
            for None — if None, no heartbeat task is started.

        Note: this method never claims "exactly-once" or "split-brain
        impossible." The honest guarantee is: corruption and contention are
        detectable, and the system fails closed.
        """
        token = await self.acquire_lock(execution_id, ttl_seconds)
        if token is None:
            yield None
            return

        stop = asyncio.Event()

        async def _heartbeat() -> None:
            elapsed = 0.0
            interval = max(ttl_seconds / 3.0, 1.0)
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=interval)
                    return  # Normal exit: stop was set by the finally block.
                except asyncio.TimeoutError:
                    elapsed += interval
                    if elapsed >= max_total_lease_seconds:
                        logger.warning(
                            "AEP lease hard cap (%ss) hit for "
                            "execution_id=%s; stopping renewal. Lock will "
                            "expire (fail-closed per Fail-Closed Invariant).",
                            max_total_lease_seconds,
                            execution_id,
                        )
                        return
                    renewed = await self.renew_lock(
                        execution_id,
                        token,
                        extend_ms=ttl_seconds * 1000,
                    )
                    if not renewed:
                        logger.warning(
                            "AEP lease renewal returned False for "
                            "execution_id=%s; lock no longer owned. "
                            "Stopping heartbeat. Worker should cease work.",
                            execution_id,
                        )
                        return

        hb = asyncio.create_task(_heartbeat())
        try:
            yield token
        finally:
            stop.set()
            with contextlib.suppress(Exception):
                await hb
            await self.release_lock(execution_id, token)
```

---

### 4.3 Lease Policy Hard Contract (per brief §5.1)

The following rules are binding and must not be overridden without an explicit design decision:

1. The lock TTL (`ttl_seconds`) is **per critical section**, not per whole workflow. A workflow that spans multiple critical sections uses multiple acquire/release cycles, not one long TTL.

2. If a critical section may legitimately exceed `ttl_seconds`, the caller MUST use `lease(...)` (auto-renew) rather than relying on a single TTL. A single-TTL lock that expires mid-section produces an expired lock, which is logged as a warning on release and may signal overlap.

3. Heartbeat interval = `ttl_seconds / 3`. This is the empirical tradeoff between renewal responsiveness and unnecessary Redis traffic.

4. The **hard `max_total_lease_seconds` ceiling** MUST always be set. On reaching it, renewal stops unconditionally and the lock is allowed to expire (fail-closed). There is no mechanism to extend the ceiling at runtime. This prevents zombie processes from starving all other workers indefinitely.

5. On any heartbeat or `renew_lock` call returning `False`, the worker MUST cease all work immediately. It no longer owns the lock. Any state mutations made after this point will be fenced by the CAS versioning, but the external side-effects cannot be recalled.

6. `T_client <= T_lock - Buffer`, with `Buffer >= 15s`. Any external API or sub-agent call made under a lock must complete strictly before the lock TTL minus the safety buffer. If it cannot, it MUST be aborted deterministically. Aborted-mid-call becomes a detectable ambiguous state (per the intent ledger, Phase 2), not a silent double-fire.

---

### 4.4 Locks Definition of Done (per brief §5.2)

- `acquire_lock` returns a token string on success.
- A second `acquire_lock` call while the lock is held returns `None`.
- `release_lock` with the correct token returns `True` and removes the key from Redis.
- `release_lock` with a wrong or already-expired token returns `False` AND emits a `logger.warning` log entry.
- `renew_lock` with the correct token extends the TTL (verifiable via `PTTL`); returns `True`.
- `renew_lock` with a wrong or expired token returns `False`.
- `lease` context manager: acquires the lock, renews across at least one heartbeat interval, releases on exit.
- `lease` yields `None` when the lock is unavailable; no heartbeat task is started in that case.
- `lease` stops renewing when `max_total_lease_seconds` is reached; lock is allowed to expire (fail-closed); a warning is logged.
- Module-level `logger = logging.getLogger("aep.locks")` is used for all log output.

---

## 5. Cross-Cutting Requirements (per brief §8)

These requirements apply to all three modules and to the test suite. Violations are defects.

| Requirement | Detail |
|---|---|
| **Single client** | One `redis.asyncio.Redis` instance, constructed once at startup with `decode_responses=True` and a shared connection pool. Passed into both `RedisStorageAdapter` and `DistributedLockManager`. No per-call client creation. |
| **No `decode_responses` toggling** | The client is configured once. No code path may override `decode_responses` for individual calls. |
| **All Lua via `register_script`** | `_CAS_SCRIPT`, `_RELEASE_SCRIPT`, and `_RENEW_SCRIPT` are each registered once in `__init__` via `client.register_script(SRC)`. The returned callable uses `EVALSHA` with automatic `EVAL` fallback on cache miss. No raw `EVAL` per call. No manual SHA management. |
| **No per-call connections** | Connection pool is managed by the `redis.asyncio` client. No `connect()`, `disconnect()`, or context-manager connection creation per request. |
| **Type hints everywhere** | Every function signature must include full type hints. Target Python 3.13. `from __future__ import annotations` may be used. |
| **Import-side-effect-free modules** | No I/O, network calls, logging config, or global state mutations at module import time. All I/O is deferred to runtime calls. |
| **No raw `SET` on `aep:state:*`** | Raw `SET` against any `aep:state:*` key is forbidden. Only `_CAS_SCRIPT` may write these keys. Quarantine keys (`aep:poison:*`) and lock keys (`aep:lock:*`) use `redis.set(...)` directly, which is permitted. |

---

## 6. Failure Modes & Exception Mapping

This table maps every observable failure to the exact exception class, the code path that raises it, and the orchestrator's expected reaction. It extends HLD §7 with precise code-path bindings.

| Failure Mode | Exception | Trigger Condition | Code Path | Orchestrator Reaction |
|---|---|---|---|---|
| **First write, no key** | (none — success) | `_CAS_SCRIPT` returns `1`; key was absent. | `save_state` → Lua returns `1` → `return`. | Not a failure. Continue. |
| **Stale write (version ≤ stored)** | `StaleWriteError` | `_CAS_SCRIPT` returns `-1`: `stored.version >= incoming.version`. | `save_state` → Lua returns `-1` → `raise StaleWriteError`. | Re-read state with `get_state`, rebase local changes, increment version, retry `save_state`. Do NOT retry with the same version. |
| **Corrupt stored payload at write** | `StateCorruptionError` | `_CAS_SCRIPT` returns `-2`: stored JSON is not decodable or has no `version` field. | `save_state` → Lua returns `-2` → `_quarantine(reason="corrupt-at-write")` → `raise StateCorruptionError`. No overwrite. | Fail-closed. Mark execution FAILED. Do not retry. Operator must investigate quarantine key. |
| **Unexpected Lua return code** | `StorageOperationError` | `_CAS_SCRIPT` returns a value other than `1`, `-1`, `-2`. | `save_state` → `raise StorageOperationError(f"Unexpected CAS return code {result}")`. | Escalate to operator. Indicates a bug or Redis data type mismatch. |
| **Redis transport failure on write** | `StorageOperationError` | Exception raised from `self._cas(...)` call (network, auth, timeout). | `save_state` → `except Exception as exc` → `raise StorageOperationError` from exc. | Retry with backoff if transient. Sustained failure: escalate. |
| **Missing key on read** | `None` (no exception) | `redis.get(key)` returns `None`. | `get_state` → `raw is None` → `return None`. | Not a failure. New execution; caller constructs initial state. |
| **Non-JSON payload on read** | `StateCorruptionError` | `json.loads(raw)` raises `JSONDecodeError`. | `get_state` → `_quarantine(reason="parse-or-validation", raw=raw)` → `raise StateCorruptionError`. | Fail-closed. Quarantine key written. Escalate to operator. |
| **Schema-invalid payload on read** | `StateCorruptionError` | `AEPExecutionState.model_validate(state_dict)` raises `ValidationError` (a `ValueError` subclass in Pydantic v2). | `get_state` → `_quarantine(reason="parse-or-validation", raw=raw)` → `raise StateCorruptionError`. | Fail-closed. Quarantine key written. Escalate. |
| **Unknown schema_version, no migrator** | `StateCorruptionError` | `SCHEMA_MIGRATIONS.get(from_version)` returns `None` in `_migrate_schema`. | `get_state` → `_migrate_schema` raises `StateCorruptionError` → `get_state` catches, calls `_quarantine(reason="migration-failed")`, re-raises. | Fail-closed. Indicates a deploy mismatch (old data, new code without migrator). Operator must register a migrator or manually recover. |
| **Migrator cycle (> 50 iterations)** | `StateCorruptionError` | Loop guard in `_migrate_schema` exceeds 50 iterations without converging. | `_migrate_schema` → `raise StateCorruptionError("chain did not converge")` → `get_state` quarantines and re-raises. | Fail-closed. Indicates a bug in the migration chain. Operator must fix the migrators. |
| **execution_id key/payload mismatch** | `StorageOperationError` | `validated.execution_id != execution_id` after successful Pydantic validation. | `get_state` → `raise StorageOperationError("key/payload mismatch")`. No quarantine. | Fail-closed. Escalate. Indicates data corruption or manual Redis edit. Not retryable. |
| **Redis transport failure on read** | `StorageOperationError` | Exception raised from `redis.get(key)`. | `get_state` → `except Exception as exc` → `raise StorageOperationError`. | Retry with backoff if transient. |
| **Quarantine write failure** | (swallowed — original exception surfaces) | Any exception inside `_quarantine`. | `_quarantine` → `except Exception: pass`. | Quarantine failure is not separately signaled. The original `StateCorruptionError` is still raised. Operator may find no quarantine key; original error message is sufficient. |
| **Lock unavailable** | `None` (no exception) | `redis.set(key, token, nx=True, ex=ttl)` returns `None` (key exists). | `acquire_lock` → `return None`. | Not an error. Orchestrator applies backoff/jitter and retries or defers. |
| **Lock release with expired/wrong token** | `bool False` + `logger.warning` | `_RELEASE_SCRIPT` returns `0` (token mismatch or key gone). | `release_lock` → `int(result) == 0` → `logger.warning(...)` → `return False`. | CRITICAL: potential overlap. Orchestrator must review logs. CAS versioning in storage will have fenced any stale writes. |
| **Lock renew returns False** | `bool False` from `renew_lock`; heartbeat logs warning and exits | `_RENEW_SCRIPT` returns `0`. | `renew_lock` → `return False`; `_heartbeat` → `logger.warning(...)` → `return`. | Worker MUST cease all in-flight work immediately. Fail-closed. |
| **Lease hard cap hit** | Heartbeat stops; lock expires naturally; `logger.warning` | `elapsed >= max_total_lease_seconds` in `_heartbeat`. | `_heartbeat` → `logger.warning(...)` → `return`. | Fail-closed. Lock expires. Work halts. No exception raised to caller; warning in logs is the signal. Prevents zombie process starvation. |
| **Redis transport failure on acquire** | `LockAcquisitionError` | Exception from `redis.set(key, token, nx=True, ex=ttl)`. | `acquire_lock` → `raise LockAcquisitionError`. | Retry with backoff if transient. |
| **Redis transport failure on release** | `LockAcquisitionError` | Exception from `self._release(...)`. | `release_lock` → `raise LockAcquisitionError`. | Retry with backoff if transient. Lock TTL will eventually expire. |
| **Redis transport failure on renew** | `LockAcquisitionError` | Exception from `self._renew(...)`. | `renew_lock` → `raise LockAcquisitionError`. | Treat as loss-of-lock (fail-closed). |

---

## 7. TTL & Versioning Rules

### 7.1 State Key TTL

| Parameter | Value | Source |
|---|---|---|
| Default state TTL | `172800` seconds (48 hours) | Brief §4.3, configurable on `save_state(ttl_seconds=...)`. |
| Poison/quarantine TTL | `604800` seconds (7 days) | `RedisStorageAdapter.POISON_TTL_SECONDS`; not configurable per-call. |
| Lock TTL default | `60` seconds | `acquire_lock(ttl_seconds=60)`; configurable per acquisition. |
| Max total lease default | `600` seconds (10 minutes) | `lease(max_total_lease_seconds=600)`; configurable per lease. |

The 48h state TTL is configurable on each `save_state` call to allow orchestrators to tune retention per execution type. It MUST be positive. A value of `0` or negative is a programming error and will be rejected by Redis.

### 7.2 Versioning Rules

| Rule | Detail |
|---|---|
| **Starting version** | `version = 1` (the `Field(default=1, ge=1)` constraint). |
| **Monotonic increment** | Each mutation increments `version` by exactly `1` before calling `save_state`. The caller owns the increment; the adapter does not auto-increment. |
| **Fencing semantics** | `_CAS_SCRIPT` rejects writes where `stored.version >= incoming.version`. Strictly greater is required. |
| **Fencing token vs. ownership token** | `version` (monotonic int) is the fencing token. The lock token (from `secrets.token_urlsafe`) is the ownership token. These are distinct concepts and must never be conflated. |
| **Schema version** | `schema_version` starts at `"1.0.0"`. It is bumped only when the model fields change in a backwards-incompatible way. A new `schema_version` MUST have a corresponding migrator registered in `SCHEMA_MIGRATIONS` before deployment to Redis instances that hold data at the prior version. |
| **Migration path rule** | `_migrate_schema` is fail-closed: an unknown `schema_version` raises `StateCorruptionError`. There is no auto-heal for unknown schema versions. A missing migrator requires operator intervention. |
| **Loop guard** | `_migrate_schema` enforces a maximum of 50 migration steps per call. Exceeding this raises `StateCorruptionError` (detects cyclic migrator chains). |

### 7.3 Durability Bound

On the AOF `appendfsync everysec` configuration (per brief §6 and HLD §2.1), the maximum data loss window on a hard Redis crash is approximately **1–2 seconds** of writes. This is not zero. Reports, docstrings, and operator documentation MUST use this honest bound. Do not claim "zero loss" or "durable to the millisecond."

---

## 8. Phase 2 Interface Contract

The following surfaces must be exposed by Phase 1 primitives WITHOUT modification when Phase 2 is built. This section documents the contract only; do NOT implement Phase 2 logic.

### 8.1 Intent Ledger Workflow Surface

Phase 1 must expose `intent_ledger: Dict[str, Any]` on `AEPExecutionState` as a round-trippable, uninterpreted dict field. Phase 2 will:
1. Call `get_state` to read the current version.
2. Write `intent_ledger[step] = {"target": ..., "status": "ABOUT_TO_FIRE"}`, increment `version`, refresh `updated_at`, call `save_state` (CAS ensures monotonic record of intent).
3. Execute the external call under a timeout satisfying `T_client <= T_lock - 15s`.
4. Write `intent_ledger[step]["status"] = "COMPLETED_SUCCESSFULLY"` (or failure detail), increment `version`, call `save_state`.

Phase 1 requirement: `save_state` and `get_state` must faithfully round-trip `intent_ledger` with arbitrary nested values. No schema enforcement on its contents.

### 8.2 Recovery Resolver Surface

Phase 2 will call `get_state(execution_id)` on restart to detect `ABOUT_TO_FIRE` intents. Phase 1 must:
- Preserve `intent_ledger` exactly as written (no cleanup, no normalization).
- Raise `StateCorruptionError` on corruption so the resolver can detect unrecoverable state.
- Return `None` for unknown executions so the resolver can distinguish new vs. crashed executions.

The resolver MUST NOT auto-retry `ABOUT_TO_FIRE` intents. This rule is enforced at the Phase 2 design level; Phase 1 has no mechanism to enforce it but must not clear or mutate the ledger.

### 8.3 Poison Ownership Split Surface

Phase 1 exposes:
- `_quarantine(execution_id, reason, raw)` — writes `aep:poison:{execution_id}:{epoch_ms}` with 7-day TTL. Best-effort. Body: `{"reason": str, "raw": str|None}`.
- `StateCorruptionError` — raised after quarantine. The orchestrator catches this, marks the execution FAILED on the dashboard, and ejects it from active scheduling.

Phase 2 requirement: the orchestrator periodically scans `aep:poison:*` keys and manages scheduling ejection. Phase 1 does NOT scan, schedule, or eject — it only writes quarantine records. Duplicate quarantine logic in the orchestrator is prohibited.

### 8.4 Systemic Circuit Breaker Surface

Phase 2 will implement a threshold-based circuit breaker. Phase 1 exposes:
- `StateCorruptionError` — countable corruption signal. Distinct from `StaleWriteError`.
- `StorageOperationError` — countable transport/integrity signal. Distinct from corruption.
- `LockAcquisitionError` — countable lock-engine signal.

Phase 1 requirement: all three exception types must remain distinct (no merging, no aliasing) so Phase 2 can count them independently in a moving window. The circuit breaker will freeze scheduling read-only if the combined error rate exceeds a threshold (e.g., >5% of threads in a 60s window).

### 8.5 Acquire Lock Non-Blocking Surface

`acquire_lock` returns `None` (not an exception) when the lock is already held. This design is mandatory so Phase 2 can apply jitter-backed retry logic on lock contention without catching exceptions. The orchestrator owns the backoff policy; Phase 1 must not make any retry or sleep decision internally.

---

## 9. Honest Guarantee & Residual Risks

### 9.1 The Honest Guarantee

> **Corruption and contention are detectable, and the system fails closed.**

This is the only guarantee this design delivers on a single self-hosted Redis instance. It is the correct and complete statement. Do not expand it. The following claims are explicitly false for this topology and MUST NOT appear in code, docstrings, comments, or documentation:

- "Absolute atomicity"
- "Split-brain is impossible"
- "Exactly-once external calls"
- "Zero data loss on crash"
- "Lock prevents all overlap"

### 9.2 Residual Risks the Implementation Cannot Eliminate

| Risk | Description | Mitigation (honest) |
|---|---|---|
| **Lease expiry during external call** | If an external API call takes longer than the remaining lock TTL (even with the Timeout Invariant as a guide), the lock may expire mid-call. Another worker may acquire and advance the state. | The Timeout Invariant (`T_client <= T_lock - 15s`) reduces this risk but does not eliminate it (clock skew, jitter). CAS versioning ensures the stale write is detected and fenced. The external side-effect may still have fired. The intent ledger (Phase 2) makes the ambiguity detectable. |
| **1–2 second write loss on Redis crash** | AOF `appendfsync everysec` buffers up to 1 second of writes. A hard crash (kernel panic, power loss) may lose up to approximately 2 seconds of the most recent writes. | This is the chosen tradeoff (throughput vs. durability). `appendfsync always` reduces the window at the cost of write latency. Neither setting eliminates all loss. Use NVMe SSD to minimize background fsync stall. The Phase 2 recovery resolver detects `ABOUT_TO_FIRE` intents and reconciles; it cannot recover if the intent write itself was lost. |
| **No consensus on a single instance** | `SET NX EX` on a single Redis instance is not safe across Redis failover. If Redis restarts and a new primary is elected with stale state, two workers may both believe they hold the lock. | This design does not support HA/Sentinel/Cluster. For HA requirements, the locking strategy would need to be replaced (e.g., Redlock across multiple instances, though Redlock has its own documented hazards). The honest claim for Phase 1 is "detectable + fail-closed," not "safe across failover." |
| **CAS fencing does not prevent external side-effects** | The monotonic version CAS fences internal state corruption but cannot recall or deduplicate an external API call that has already been dispatched. | The intent ledger (Phase 2) + the Timeout Invariant together make the ambiguity detectable. Operators must investigate `ABOUT_TO_FIRE` intents after a crash or overlap event. Do not claim prevention; only claim detectability. |
| **Clock skew across workers** | The Timeout Invariant buffer (≥15s) assumes bounded clock skew. If two workers have clock skew exceeding several seconds, the effective buffer may be insufficient. | The buffer SHOULD be sized larger than the expected maximum clock skew. NTP synchronization is strongly recommended. The current 15s default assumes skew < a few seconds. |
| **Quarantine best-effort only** | `_quarantine` swallows its own exceptions. If Redis is down at the moment quarantine is attempted, no quarantine key is written. | The `StateCorruptionError` is still raised; the original error message is preserved. Operators may find no quarantine key for some corruption events. Logging should capture enough context. A future enhancement could write quarantine to a secondary store. |
