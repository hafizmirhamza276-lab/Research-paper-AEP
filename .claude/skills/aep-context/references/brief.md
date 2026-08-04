# Agent Execution Protocol (AEP) — Implementation Brief

**Document Version:** 2.1.0 (Hardened / Implementation-Ready)
**Supersedes:** 2.0.0
**Target Runtime:** Python 3.13.1 + Redis 7.x (`redis.asyncio`)
**Intended Reader:** Claude Code (autonomous implementation agent)

---

## 0. How To Use This Document

You are implementing the **core persistence + concurrency primitives** of AEP. Build exactly what is specified. Where this document says **MUST**, it is a hard contract; where it says **SHOULD/MAY**, use judgment but document your choice in a code comment.

**Scope of this pass (Phase 1 — implement now):**
- `src/core/exceptions.py`
- `src/core/storage.py`
- `src/core/locks.py`
- `tests/` (adversarial async pytest suite)

**Out of scope this pass (Phase 2 — contract only, do NOT implement yet):**
- The orchestration runner that drives the intent-ledger workflow.
- The crash-recovery resolver.
- The systemic circuit breaker.

Phase 2 is described in §7 only as an **interface contract** so that your Phase 1 primitives expose the right surfaces. Do not build Phase 2 logic.

**Honest guarantee statement (read this before you write a single line):**
This design does **not** make concurrent overlap *impossible* on a single Redis instance. It makes overlap **detectable and fail-closed**. The real safety properties delivered are: (a) internal state cannot be silently clobbered by a stale writer (CAS fencing), and (b) ambiguous external side-effects become detectable rather than silent (intent ledger). Do not write comments or docstrings claiming "absolute atomicity," "split-brain is impossible," or "guaranteed exactly-once external calls" — those claims are false for this topology and will mislead future maintainers.

---

## 1. Architectural Context

LLM agents that hold execution state in process memory or flat files lose everything on a crash, timeout, or exception. Restarting from step zero burns tokens, causes race conditions, and risks duplicate external mutations (double-charge, duplicate records).

AEP is a backend-neutral, deterministic state-boundary layer. It uses Redis as a high-speed persistence store plus a distributed lease lock. The current deployment topology is a **single self-hosted Redis instance** (foundational phase). All design choices below assume that topology and explicitly note where they would change under master-replica/Sentinel/Cluster.

**Critical limitation, stated up front:** The external legacy APIs AEP integrates with do **not** support native idempotency keys. Therefore neither the lock nor the CAS check can prevent a duplicate *external* side-effect. They only prevent internal state corruption and reduce wasteful re-execution. Duplicate-side-effect safety is delivered exclusively by the **Write-Ahead Intent Ledger** (§7) combined with the **Timeout Invariant** (§2.1), and even then the guarantee is "detectable ambiguous state + fail-closed," not "exactly once."

---

## 2. Global Invariants (Hard Contract)

### 2.1 Timeout Invariant
The client-side timeout for any external API / sub-agent call (`T_client`) MUST be strictly smaller than the lock TTL (`T_lock`), with a safety buffer:

```
T_client  <=  T_lock - Buffer_Margin      (Buffer_Margin >= 15s)
```

Purpose: no worker remains "in-flight" on an external call after its lease has expired. If a call cannot finish inside `T_client`, it MUST be aborted deterministically (an aborted-mid-call becomes a *detectable* ambiguous state, not a silent double-fire).

**Operational note for the implementer:** `T_lock` must be sized to the *slowest* legacy API plus the buffer. The 60s default is a placeholder; if any integration legitimately needs 50s, `T_lock` must be raised to >= 65s. Make `T_lock` and `Buffer_Margin` configurable, not hard-coded.

### 2.2 Optimistic Versioning Invariant (CAS Fencing)
State updates MUST NOT use raw `SET` overwrite. Every update goes through an atomic Compare-And-Swap on a **monotonically increasing integer** `version`. Random tokens MUST NOT be used as the fencing variable — only `v1 < v2 < v3` integers establish chronological order. (The lock token remains a random `secrets` value; it is an *ownership* token, not a *fencing* token. These are two different things.)

### 2.3 Fail-Closed Invariant
On data corruption, schema mismatch, unknown schema version, or an ambiguous in-flight intent, the system MUST stop, fence the affected `execution_id`, and surface the condition to the caller via a distinct exception. Auto-recovery guessing is banned. "Fail closed" beats "heal silently" everywhere in this codebase.

---

## 3. Module: `src/core/exceptions.py`

Implement this hierarchy. The distinct subclasses exist so the orchestrator can branch on *why* something failed (retry vs. fence vs. quarantine).

```python
class AEPException(Exception):
    """Baseline for all AEP core errors."""


class StorageOperationError(AEPException):
    """Transport/driver failure or an integrity violation that is NOT corruption
    and NOT a stale write (e.g., execution_id key mismatch). Generally retryable
    only if the cause is transient transport."""


class StaleWriteError(StorageOperationError):
    """The incoming version is not strictly greater than the stored version.
    EXPECTED under contention. NOT retryable as-is: the worker must re-read
    state and rebase before retrying. Signals a stale/fenced writer."""


class StateCorruptionError(StorageOperationError):
    """Stored payload is unparseable, fails schema validation, or has no usable
    version. NOT retryable. Triggers poison-message quarantine + fail-closed."""


class LockAcquisitionError(AEPException):
    """Lock engine communication fault or an invalid lease operation. The plain
    'lock not available' case is NOT an error — acquire returns None for that."""
```

**Definition of Done (exceptions):** all five classes exist; `StaleWriteError` and `StateCorruptionError` subclass `StorageOperationError`; importable without side effects.

---

## 4. Module: `src/core/storage.py`

### 4.1 Schema (`AEPExecutionState`, Pydantic v2)

```python
import time
import uuid
from enum import Enum
from typing import Any, Dict
from pydantic import BaseModel, Field, field_validator


class AEPStatus(str, Enum):
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    AWAITING_TOOL = "AWAITING_TOOL"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


CURRENT_SCHEMA_VERSION = "1.0.0"


class AEPExecutionState(BaseModel):
    execution_id: str
    status: AEPStatus
    version: int = Field(default=1, ge=1)            # monotonic fencing counter
    schema_version: str = Field(default=CURRENT_SCHEMA_VERSION)
    intent_ledger: Dict[str, Any] = Field(default_factory=dict)
    context_data: Dict[str, Any] = Field(default_factory=dict)
    updated_at: float = Field(default_factory=lambda: time.time())  # MUST default

    @field_validator("execution_id")
    @classmethod
    def _must_be_uuid4(cls, v: str) -> str:
        try:
            uuid.UUID(v, version=4)
        except (ValueError, AttributeError, TypeError) as e:
            raise ValueError("execution_id must be a UUIDv4 string") from e
        return v
```

Notes:
- `updated_at` MUST have a `default_factory` so callers cannot accidentally construct an invalid state. Callers that mutate state should still refresh it explicitly before each save.
- `execution_id` is validated as UUIDv4 (the v2.0.0 spec claimed this but did not enforce it).

### 4.2 The Atomic CAS Write Script (Lua, runs on Redis)

This eliminates the read-modify-write TOCTOU race. Three outcomes:
- `1` → written.
- `-1` → **stale write** (stored version >= incoming). Map to `StaleWriteError`.
- `-2` → **stored payload is corrupt/unversioned** (cannot verify monotonicity). Per the Fail-Closed Invariant we refuse to overwrite. Map to `StateCorruptionError`.

```lua
-- KEYS[1] = aep:state:{execution_id}
-- ARGV[1] = serialized state JSON
-- ARGV[2] = incoming monotonic version (int)
-- ARGV[3] = TTL seconds (default 172800 = 48h)
local current = redis.call("GET", KEYS[1])
if current then
    local ok, decoded = pcall(cjson.decode, current)
    if (not ok) or type(decoded) ~= "table" or decoded.version == nil then
        return -2   -- STORED PAYLOAD CORRUPT: fail closed, do not overwrite
    end
    if tonumber(decoded.version) >= tonumber(ARGV[2]) then
        return -1   -- STALE WRITE: fence the writer
    end
end
redis.call("SET", KEYS[1], ARGV[1], "EX", ARGV[3])
return 1
```

> **Design decision (documented for future maintainers):** the `-2` path chooses *fail-closed* over *self-heal*. A corrupt state key halts the execution until the corruption is investigated, rather than being silently overwritten. If a future operator prefers self-heal, they may change `-2` to fall through to `SET`, but they MUST then accept that the monotonic guarantee is skipped for that write. Do not change this without an explicit decision.

### 4.3 Adapter Implementation

```python
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from redis.asyncio import Redis

from src.core.exceptions import (
    StorageOperationError,
    StaleWriteError,
    StateCorruptionError,
)


# --- Schema migration registry (real chain, fail-closed on unknown) ---------
# Each migrator takes a raw dict at version K and returns a raw dict at the
# next version, and MUST bump raw_state["schema_version"]. Register them here.
# Example stub (commented; implement real ones as schemas evolve):
#
# def _migrate_0_9_0_to_1_0_0(raw: Dict[str, Any]) -> Dict[str, Any]:
#     raw["intent_ledger"] = raw.pop("ledger", {})
#     raw["schema_version"] = "1.0.0"
#     return raw
#
SCHEMA_MIGRATIONS: Dict[str, Any] = {
    # "0.9.0": _migrate_0_9_0_to_1_0_0,
}


class BaseStorageAdapter(ABC):
    @abstractmethod
    async def save_state(self, state: "AEPExecutionState", ttl_seconds: int = 172800) -> None:
        """Persist iff incoming version > stored version (atomic CAS)."""

    @abstractmethod
    async def get_state(self, execution_id: str) -> Optional["AEPExecutionState"]:
        """Load, migrate if needed, validate. Quarantine + raise on corruption."""


class RedisStorageAdapter(BaseStorageAdapter):
    POISON_TTL_SECONDS = 7 * 24 * 3600  # 7-day forensic window

    def __init__(self, redis_client: Redis):
        # The client SHOULD be created with decode_responses=True and a shared
        # connection pool. See §8.
        self.redis = redis_client
        # register_script uses EVALSHA with automatic EVAL fallback (no manual
        # script-shipping each call).
        self._cas = self.redis.register_script(_CAS_SCRIPT)

    # ---- write path -------------------------------------------------------
    async def save_state(self, state: "AEPExecutionState", ttl_seconds: int = 172800) -> None:
        key = f"aep:state:{state.execution_id}"
        payload = state.model_dump_json()
        try:
            result = await self._cas(
                keys=[key],
                args=[payload, str(state.version), str(ttl_seconds)],
            )
        except Exception as e:
            raise StorageOperationError(f"Redis transport failure on save: {e}") from e

        result = int(result)
        if result == 1:
            return
        if result == -1:
            raise StaleWriteError(
                f"Stale write blocked: incoming version {state.version} "
                f"is not greater than the stored version."
            )
        if result == -2:
            await self._quarantine(state.execution_id, reason="corrupt-at-write")
            raise StateCorruptionError(
                f"Stored state for {state.execution_id} is corrupt/unversioned; "
                f"refused overwrite (fail-closed)."
            )
        raise StorageOperationError(f"Unexpected CAS return code: {result}")

    # ---- read path --------------------------------------------------------
    async def get_state(self, execution_id: str) -> Optional["AEPExecutionState"]:
        key = f"aep:state:{execution_id}"
        try:
            raw = await self.redis.get(key)
        except Exception as e:
            raise StorageOperationError(f"Redis transport failure on get: {e}") from e

        if raw is None:
            return None

        # UNIFIED corruption path: both unparseable JSON and schema-invalid
        # data route to quarantine + StateCorruptionError. (v2.0.0 split these
        # across two exception types — that gap is closed here.)
        try:
            state_dict = json.loads(raw)
            if state_dict.get("schema_version") != CURRENT_SCHEMA_VERSION:
                state_dict = await self._migrate_schema(state_dict)
            validated = AEPExecutionState.model_validate(state_dict)
        except StateCorruptionError:
            # already classified by _migrate_schema; quarantine then re-raise
            await self._quarantine(execution_id, reason="migration-failed", raw=raw)
            raise
        except (json.JSONDecodeError, ValueError, Exception) as e:
            # ValidationError is a subclass of ValueError in pydantic v2.
            # Anything that prevents producing a valid model = corruption.
            await self._quarantine(execution_id, reason="parse-or-validation", raw=raw)
            raise StateCorruptionError(
                f"State for {execution_id} failed parse/validation: {e}"
            ) from e

        if validated.execution_id != execution_id:
            raise StorageOperationError(
                f"Key/payload mismatch: requested {execution_id}, "
                f"payload claims {validated.execution_id}."
            )
        return validated

    # ---- migration (fail-closed on unknown version) -----------------------
    async def _migrate_schema(self, raw_state: Dict[str, Any]) -> Dict[str, Any]:
        from_version = raw_state.get("schema_version")
        # Walk the chain until we reach the current version.
        guard = 0
        while from_version != CURRENT_SCHEMA_VERSION:
            guard += 1
            if guard > 50:
                raise StateCorruptionError("Migration chain did not converge.")
            migrator = SCHEMA_MIGRATIONS.get(from_version)
            if migrator is None:
                raise StateCorruptionError(
                    f"No migration path from schema_version={from_version!r} "
                    f"to {CURRENT_SCHEMA_VERSION}."
                )
            raw_state = migrator(raw_state)
            from_version = raw_state.get("schema_version")
        return raw_state

    # ---- poison-message quarantine (storage owns the WRITE; orchestrator
    #      owns scheduling ejection + dashboard — see §7) --------------------
    async def _quarantine(self, execution_id: str, reason: str, raw: Any = None) -> None:
        import time as _t
        poison_key = f"aep:poison:{execution_id}:{int(_t.time() * 1000)}"
        try:
            if raw is None:
                raw = await self.redis.get(f"aep:state:{execution_id}")
            await self.redis.set(
                poison_key,
                json.dumps({"reason": reason, "raw": raw}),
                ex=self.POISON_TTL_SECONDS,
            )
        except Exception:
            # Quarantine is best-effort telemetry; never let it mask the
            # original corruption error. Swallow and let the caller raise.
            pass
```

> Place `_CAS_SCRIPT` (the Lua from §4.2) as a module-level string. `AEPExecutionState`, `AEPStatus`, `CURRENT_SCHEMA_VERSION` live in this same module (per the original §3.1).

### 4.4 Storage — Definition of Done
- Valid round-trip: `save_state` then `get_state` returns an equal model.
- First write (no key) succeeds; monotonic increments succeed; equal/lower version → `StaleWriteError`.
- Corrupt stored payload at write → `StateCorruptionError` (no overwrite happened).
- `get_state` on missing key → `None`.
- Non-JSON payload → quarantine key created + `StateCorruptionError`.
- Schema-invalid payload → quarantine + `StateCorruptionError`.
- Unknown `schema_version` with no migrator → `StateCorruptionError`; registered migrator → upgraded then validated.
- `execution_id` key/payload mismatch → `StorageOperationError`.
- Quarantine never raises its own error over the original corruption error.

---

## 5. Module: `src/core/locks.py`

Distributed lease lock. Ownership token is a random `secrets` value (NOT a fencing token — fencing is the integer `version` in storage).

```python
import asyncio
import contextlib
import logging
import random
import secrets
from typing import AsyncIterator, Optional

from redis.asyncio import Redis

from src.core.exceptions import LockAcquisitionError

logger = logging.getLogger("aep.locks")

_RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

_RENEW_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("PEXPIRE", KEYS[1], ARGV[2])
else
    return 0
end
"""


class DistributedLockManager:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self._release = self.redis.register_script(_RELEASE_SCRIPT)
        self._renew = self.redis.register_script(_RENEW_SCRIPT)

    async def acquire_lock(self, execution_id: str, ttl_seconds: int = 60) -> Optional[str]:
        """Returns an ownership token on success, or None if already held.
        None is NOT an error — the orchestrator owns any backoff/retry policy."""
        key = f"aep:lock:{execution_id}"
        token = secrets.token_urlsafe(32)
        try:
            acquired = await self.redis.set(key, token, nx=True, ex=ttl_seconds)
        except Exception as e:
            raise LockAcquisitionError(f"Lock engine fault on acquire: {e}") from e
        return token if acquired else None

    async def release_lock(self, execution_id: str, lock_token: str) -> bool:
        """True if we still owned the lock and released it. False is a CRITICAL
        signal: the lease already expired and possibly another worker owns it —
        i.e. an overlap may have already occurred. We LOG it loudly."""
        key = f"aep:lock:{execution_id}"
        try:
            result = await self._release(keys=[key], args=[lock_token])
        except Exception as e:
            raise LockAcquisitionError(f"Lock release rejected: {e}") from e
        if int(result) == 0:
            logger.warning(
                "AEP lock release returned 0 for execution_id=%s: lease expired "
                "or re-acquired by another worker. Possible overlap occurred.",
                execution_id,
            )
            return False
        return True

    async def renew_lock(self, execution_id: str, lock_token: str,
                         extend_ms: int = 30000) -> bool:
        """Atomic, token-checked TTL extension (PEXPIRE). Returns False if we no
        longer own the lock — caller MUST stop work immediately on False."""
        key = f"aep:lock:{execution_id}"
        try:
            result = await self._renew(keys=[key], args=[lock_token, str(extend_ms)])
        except Exception as e:
            raise LockAcquisitionError(f"Lock renew failed: {e}") from e
        return int(result) == 1

    # ---- OPTIONAL helper: capped auto-renewing lease ----------------------
    @contextlib.asynccontextmanager
    async def lease(self, execution_id: str, ttl_seconds: int = 60,
                    max_total_lease_seconds: int = 600) -> AsyncIterator[Optional[str]]:
        """Acquire a lock and auto-renew it in the background up to a HARD CAP.

        Why the cap (resolves the zombie-renewal hazard): a hung-but-alive worker
        whose heartbeat task keeps running would otherwise hold the lock forever
        and starve every other worker. Once max_total_lease is reached we STOP
        renewing, let the lock expire, and the work fails closed.

        Yields the token on success, or None if the lock could not be acquired
        (caller must check)."""
        token = await self.acquire_lock(execution_id, ttl_seconds)
        if token is None:
            yield None
            return

        stop = asyncio.Event()

        async def _heartbeat():
            elapsed = 0.0
            interval = max(ttl_seconds / 3.0, 1.0)
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=interval)
                    return  # released normally
                except asyncio.TimeoutError:
                    elapsed += interval
                    if elapsed >= max_total_lease_seconds:
                        logger.warning(
                            "AEP lease cap (%ss) hit for execution_id=%s; "
                            "stopping renewal, lock will expire (fail-closed).",
                            max_total_lease_seconds, execution_id,
                        )
                        return
                    if not await self.renew_lock(execution_id, token,
                                                 extend_ms=ttl_seconds * 1000):
                        logger.warning(
                            "AEP lease lost for execution_id=%s during renewal.",
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

### 5.1 Lease Policy (Hard Contract — resolves the "when do we renew?" ambiguity)
- The lock TTL is **per critical section**, not per whole workflow.
- If a locked critical section can exceed `T_lock`, the orchestrator MUST use `lease(...)` (auto-renew) rather than relying on a single TTL.
- Heartbeat interval = `T_lock / 3`.
- A **hard `max_total_lease` ceiling** MUST exist. On reaching it, renewal stops, the lock expires, and the worker fails closed. No exceptions.
- On any `renew_lock`/heartbeat returning False, the worker MUST cease all work immediately (it no longer owns the lock).

### 5.2 Locks — Definition of Done
- `acquire_lock` returns a token; a second acquire while held returns `None`.
- `release_lock` with the correct token returns `True` and removes the key.
- `release_lock` with a wrong/expired token returns `False` AND emits a `warning` log.
- `renew_lock` with the correct token extends TTL (verify via `PTTL`); wrong token → `False`.
- `lease` context manager: acquires, renews across at least one interval, releases on exit; yields `None` when the lock is unavailable; stops renewing at the cap.

---

## 6. Production Redis Configuration

Single instance, balanced durability (max ~1–2s loss window on a hard crash):

```
appendonly yes
appendfsync everysec
aof-use-rdb-preamble yes
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
save 900 1
save 300 10
```

Notes the implementer MUST keep in mind:
- `appendfsync everysec` is a **server-side** durability policy. It does not block the Python asyncio event loop; `always` would only increase per-write *server* latency. The choice here is throughput-vs-durability, correctly biased to `everysec`.
- The `<500ms` target is **state-fetch-and-resume from a live Redis** (sub-ms network round trip), NOT necessarily Redis process restart + AOF replay. AOF replay time scales with dataset size and must be benchmarked separately; do not assume <500ms cold-start without measuring.
- Use NVMe/fast SSD: a slow disk makes `everysec` background fsync stall the main thread and inflates the loss window.

---

## 7. Phase 2 Interface Contract (DO NOT IMPLEMENT — for surface design only)

Your Phase 1 primitives must support the following without modification. This is documentation, not a build target.

**Write-Ahead Intent Ledger workflow (per external mutation):**
1. `acquire_lock` (or `lease` if the section may exceed TTL).
2. `get_state`, read `version`.
3. Record intent: `intent_ledger[step] = {"target": ..., "status": "ABOUT_TO_FIRE"}`, `version += 1`, refresh `updated_at`, `save_state`.
4. Execute external call wrapped in a timeout satisfying §2.1 (`T_client <= T_lock - 15s`); abort deterministically on timeout.
5. Record resolution: `status = "COMPLETED_SUCCESSFULLY"` (or failure detail), `version += 1`, `save_state`.
6. Release / exit lease.

**Recovery resolver:** on restart, if `get_state` shows an intent at `ABOUT_TO_FIRE`, the call's outcome is ambiguous. MUST NOT auto-retry. MUST either reconcile via an external read-back (if the API supports it) or halt and raise a systemic alert.

**Poison handling ownership split:** the storage adapter performs the quarantine *write* and raises `StateCorruptionError`. The orchestrator catches it, marks the execution `FAILED` on the dashboard, and ejects it from active scheduling. Do not duplicate quarantine logic in the orchestrator.

**Systemic circuit breaker:** if `StateCorruptionError`/`StorageOperationError` exceed a threshold (e.g. >5% of threads in a moving 60s window), trip a breaker: stop all background recovery, freeze scheduling read-only, alert. (Distinct from per-record poison handling: poison = one bad record; breaker = systemic failure, e.g. a bad deploy.)

---

## 8. Cross-Cutting Implementation Requirements
- Construct the client once: `Redis(host=..., port=..., decode_responses=True)` with a shared connection pool. Pass that single client into both adapters. Do not open a connection per call.
- All Lua runs via `register_script` (EVALSHA with EVAL fallback). No raw `EVAL` per call.
- On crash-recovery storms, the orchestrator (Phase 2) should add jitter to re-acquire backoff to avoid a thundering herd; expose `acquire_lock` such that this is possible (it already returns `None` rather than blocking — good).
- Type-hint everything; target Python 3.13. Keep modules import-side-effect free.

---

## 9. Build Order (sequential)
1. **`src/core/exceptions.py`** — §3 hierarchy. Verify imports.
2. **`src/core/storage.py`** — schema (§4.1), `_CAS_SCRIPT` (§4.2), adapter (§4.3).
3. **`src/core/locks.py`** — §5 manager + `lease` helper.
4. **`tests/`** — adversarial async pytest suite covering every Definition-of-Done bullet in §4.4 and §5.2, plus the matrix below.

### 9.1 Adversarial Test Matrix (acceptance criteria)

| Area | Scenario | Expected |
|---|---|---|
| CAS | first write, no key | success (`1`) |
| CAS | strictly increasing versions | each succeeds |
| CAS | equal version | `StaleWriteError` |
| CAS | lower version | `StaleWriteError` |
| CAS | stored payload corrupt at write | `StateCorruptionError`, no overwrite |
| Get | missing key | `None` |
| Get | valid round-trip | equal model |
| Get | non-JSON payload | quarantine key + `StateCorruptionError` |
| Get | schema-invalid payload | quarantine + `StateCorruptionError` |
| Get | unknown schema_version, no migrator | `StateCorruptionError` |
| Get | known migrator registered | upgraded + validated |
| Get | execution_id key/payload mismatch | `StorageOperationError` |
| Lock | acquire then acquire again | second returns `None` |
| Lock | release with correct token | `True`, key gone |
| Lock | release with wrong/expired token | `False` + warning logged |
| Lock | renew with correct token | TTL extended (`PTTL` grows) |
| Lock | renew with wrong token | `False` |
| Concurrency | two workers race acquire | exactly one wins |
| Concurrency | stale worker writes after expiry while new worker advanced version | stale write fenced (`StaleWriteError`); newer state intact |
| Lease | section exceeds TTL with `lease()` | lock stays held via renewal |
| Lease | reach `max_total_lease` | renewal stops, lock expires (fail-closed) |

Use `pytest-asyncio` and a real Redis (Docker container or `fakeredis` that supports Lua + `cjson`; verify `cjson` support before relying on it — if the fake lacks `cjson`, use a real Redis container for the CAS tests).

---

## 10. What Success Looks Like
All four files exist, every Definition-of-Done bullet and every matrix row passes, no docstring overclaims atomicity guarantees, and the three resolved hazards are demonstrably handled in tests: (1) unified poison path, (2) fail-closed schema migration, (3) capped heartbeat lease. Phase 2 logic is intentionally absent.
