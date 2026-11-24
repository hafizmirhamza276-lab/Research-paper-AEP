# Agent Execution Protocol (AEP) — Phase 1 High-Level Design

**Document Version:** 1.0.0 (Phase 1 HLD)
**Date:** 2026-05-22
**Target Audience:** Implementation team, orchestrator integrators, operational reviewers

---

## 1. Purpose & Scope

### 1.1 What AEP Is

AEP is a Python 3.13 + `redis.asyncio` persistence and concurrency layer for autonomous agents. It provides:

- **Atomicity at the storage layer:** state updates via compare-and-swap on monotonically increasing version integers, ensuring internal consistency against concurrent writes.
- **Detectability of contention and corruption:** distinct exception types allow the orchestrator to route failures (retry vs. fence vs. quarantine) based on root cause, not guessing.
- **Deterministic fail-closed behavior:** on ambiguity, corruption, or safety-cap hit, the system halts rather than speculates, escalating to the operator.

The honest guarantee is: **corruption and contention are detectable, and the system fails closed.** This is the only guarantee that holds on a single self-hosted Redis instance without cluster/replication.

### 1.2 What AEP Is NOT

- **Not exactly-once delivery:** external side-effects (API calls) remain susceptible to duplicate if the Redis lease expires during the call. Duplicate detection is the responsibility of the intent ledger (Phase 2) combined with the Timeout Invariant.
- **Not HA-safe:** this design targets a single Redis instance. Master-replica or Sentinel topologies would require replication lag handling and leadership consensus; those are Phase 2+ expansions, not covered here.
- **Not lock-based consensus:** the lock is a **lease**, not a consensus primitive. Multiple workers may overlap if the lease expires; that overlap is detectable (via version fencing) but not prevented.

### 1.3 Phase 1 Scope (This Deliverable)

- `src/core/exceptions.py` — exception hierarchy.
- `src/core/storage.py` — state schema, atomic CAS write, read + validation + migration + quarantine.
- `src/core/locks.py` — distributed lease lock, auto-renewing context manager with hard cap.
- `tests/` — adversarial async pytest suite covering all critical scenarios and concurrency races.

### 1.4 Phase 2 (Contract Only, NOT Implemented)

- Write-ahead intent ledger workflow and recovery resolver.
- Poison ownership split (orchestrator scheduling ejection; storage writes quarantine).
- Systemic circuit breaker (threshold-based freeze on high error rate).

These are described in §6 as interface contracts only to ensure Phase 1 primitives expose the right surfaces.

---

## 2. Topology Assumption

### 2.1 Redis Topology

- **Single self-hosted instance**, no master-replica, no Sentinel, no Cluster mode.
- **Durability config (mandatory):**
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
  - `appendfsync everysec` trades some durability (≈1–2s max loss on hard crash) for throughput; it does not block the asyncio event loop.
  - NVMe/fast SSD required; slow disk makes background fsync stall and inflates loss window.

### 2.2 Honest Guarantee

On a **single Redis instance**, concurrent workers and lease expiry introduce three hazards:

1. **Lease expiry overlap:** a worker A's lock expires while A is mid-call; worker B acquires and advances the state; worker A later writes stale data. **Mitigated by:** the Timeout Invariant (calls complete before lock expires) and CAS fencing (stale writes are rejected).
2. **Corruption hazard:** malformed JSON or schema mismatch on load. **Mitigated by:** unified corruption path + fail-closed quarantine (never auto-heal).
3. **Loss of work on Redis crash:** up to 1–2s of recent writes may be lost on hardware failure. **Mitigated by:** the orchestrator's Phase 2 recovery resolver, which detects ambiguous ABOUT_TO_FIRE intents and reconciles with external APIs.

**The honest guarantee is:**
> Corruption and contention are detectable, and the system fails closed.

Not "absolute atomicity," not "split-brain impossible," not "exactly-once external calls." Only detectability + fail-closed halt.

---

## 3. The Three Invariants

### Invariant 1: Timeout Invariant

**Verbatim statement:**
```
T_client  <=  T_lock - Buffer_Margin      (Buffer_Margin >= 15s)
```

**Rationale:** any operation held under a lock—especially an external API call—must complete strictly before the lease expires. The buffer (≥15s) covers clock skew, network jitter, and renewal latency. If a call cannot finish in `T_client`, it MUST abort deterministically (an aborted call becomes a detectable ambiguous state, not a silent double-fire). The orchestrator MUST size `T_lock` to the slowest legitimate API plus the buffer, and make both configurable, not hard-coded.

### Invariant 2: CAS Fencing Invariant

**Verbatim statement:**
```
State updates happen ONLY via an atomic monotonic-integer compare-and-swap, NEVER via raw SET.
Random tokens (e.g., the lock-ownership token from `secrets`) are OWNERSHIP tokens —
they prove who holds the lock. They are NOT fencing tokens. The fencing token is the monotonic integer.
```

**Rationale:** on a single Redis instance, `SET` overwrites are not atomic against reads + external calls. The monotonic-integer CAS ensures: (a) stale writes (non-increasing version) are rejected immediately (detectable), and (b) the version order remains consistent even under contention. The lock token (`secrets` value) proves ownership of the lease; the version integer proves chronological order of state mutations. These are distinct concepts.

### Invariant 3: Fail-Closed Invariant

**Verbatim statement:**
```
On corruption, ambiguity, or a hit on a safety cap (e.g., the lease-cap ceiling):
STOP, FENCE, ESCALATE. Never guess.
A corrupt payload is quarantined, not silently rewritten.
An ABOUT_TO_FIRE intent is never auto-retried.
A capped lease that hits its ceiling stops renewing and the lock is allowed to expire.
```

**Rationale:** ambiguous states are the hardest to debug and the most dangerous to silent-heal. A corrupt state key halts execution until the corruption is investigated (not overwritten). A capped lease that has renewed beyond its safe lifetime stops renewing and fails closed (preventing zombie processes from starving others). The system prefers detectability + operator action over guessing and risking silent data loss.

---

## 4. Component Map

### 4.1 `src/core/exceptions.py`

**Purpose:** Exception hierarchy to let the orchestrator route failures by root cause.

**Module structure:**
- `AEPException(Exception)` — baseline for all AEP core errors.
- `StorageOperationError(AEPException)` — transport fault or integrity violation (not corruption, not stale write). May be transient; retryable if cause is transient.
- `StaleWriteError(StorageOperationError)` — incoming version ≤ stored version. Expected under contention. NOT directly retryable; requires re-read + rebase.
- `StateCorruptionError(StorageOperationError)` — payload unparse-able, fails validation, or has no version. NOT retryable. Triggers poison quarantine + fail-closed.
- `LockAcquisitionError(AEPException)` — lock engine communication fault or invalid lease operation. Plain "lock unavailable" is NOT an error (acquire_lock returns None).

**Responsibilities:**
- Signal the **category** of failure so the orchestrator can decide: retry/backoff, fence the execution_id, quarantine and alert.

**Does NOT:**
- Handle recovery logic (that's orchestrator work).
- Make any guarantees about the state of Redis after an error (caller must re-check).

---

### 4.2 `src/core/storage.py`

**Purpose:** Atomic state persistence, corruption detection, and schema migration.

**Module structure:**

**Schema:**
- `AEPStatus` enum: IDLE, PROCESSING, AWAITING_TOOL, PAUSED, COMPLETED, FAILED.
- `AEPExecutionState(BaseModel)` — Pydantic v2 model with fields:
  - `execution_id` (UUIDv4, validated).
  - `status` (AEPStatus).
  - `version` (int, ≥1, monotonic fencing counter).
  - `schema_version` (str, default "1.0.0").
  - `intent_ledger` (dict, for Phase 2).
  - `context_data` (dict, arbitrary agent data).
  - `updated_at` (float, Unix timestamp, must default-factory so it cannot be None).
- `CURRENT_SCHEMA_VERSION` = "1.0.0".

**Lua script (`_CAS_SCRIPT`):**
- Atomically compares stored version against incoming version, rejects if stored ≥ incoming (return -1 → StaleWriteError).
- Detects corrupt/unversioned stored payload (return -2 → StateCorruptionError, no overwrite).
- On success, SET with TTL and return 1.

**Adapter interface:**
- `BaseStorageAdapter` (abstract):
  - `async save_state(state: AEPExecutionState, ttl_seconds: int) -> None` — persist iff version > stored.
  - `async get_state(execution_id: str) -> Optional[AEPExecutionState]` — load, migrate, validate, quarantine-on-corruption.

- `RedisStorageAdapter(BaseStorageAdapter)`:
  - **Write path:** serialize state to JSON, invoke Lua CAS script, map return codes to exceptions (1 → success, -1 → StaleWriteError, -2 → StateCorruptionError + quarantine).
  - **Read path:** fetch from Redis, parse JSON, migrate schema if needed (walking the `SCHEMA_MIGRATIONS` registry), validate against `AEPExecutionState`, quarantine on corruption, check execution_id key/payload match.
  - **Migration:** walk migration chain from stored `schema_version` to `CURRENT_SCHEMA_VERSION`; raise `StateCorruptionError` on unknown version (fail-closed).
  - **Quarantine:** write to `aep:poison:{execution_id}:{timestamp}` with 7-day TTL, best-effort (failures swallowed so as not to mask original corruption).

**Schema migration registry:**
- `SCHEMA_MIGRATIONS: Dict[str, Callable]` — maps from_version → migration function. Each migrator takes raw dict, bumps `schema_version`, returns upgraded dict. Empty in Phase 1; populated as schemas evolve.

**Responsibilities:**
- Ensure monotonic version consistency on write (fail-closed on stale/corrupt).
- Detect and quarantine corrupted payloads without overwrite.
- Migrate schemas atomically on read, failing closed on unknown versions.
- Enforce execution_id consistency (key ↔ payload).

**Does NOT:**
- Implement the intent ledger workflow (Phase 2).
- Implement recovery/reconciliation logic (Phase 2).
- Decide retry/backoff policy (orchestrator owns that).
- Handle lock operations (that's locks.py).

---

### 4.3 `src/core/locks.py`

**Purpose:** Distributed lease lock with auto-renewing context manager and hard cap.

**Module structure:**

**Lua scripts:**
- `_RELEASE_SCRIPT` — atomic token check + DEL. Return count (0 = not held, 1 = deleted).
- `_RENEW_SCRIPT` — atomic token check + PEXPIRE. Return 1 if extended, 0 if token mismatch.

**`DistributedLockManager` class:**
- `__init__(redis_client: Redis)` — store client, register Lua scripts via `register_script`.
- `async acquire_lock(execution_id: str, ttl_seconds: int = 60) -> Optional[str]` — SET with NX (atomic acquire). Return token on success, None if already held. None is NOT an error; orchestrator owns backoff policy.
- `async release_lock(execution_id: str, lock_token: str) -> bool` — Lua script: delete only if token matches. Return True if we still owned it, False if lease expired (emit warning log — this is a CRITICAL signal that overlap may have occurred).
- `async renew_lock(execution_id: str, lock_token: str, extend_ms: int = 30000) -> bool` — Lua script: extend TTL only if token matches. Return True on success, False if we no longer own lock (caller MUST stop work immediately).
- `async lease(execution_id: str, ttl_seconds: int = 60, max_total_lease_seconds: int = 600) -> AsyncIterator[Optional[str]]` — context manager:
  - Acquire lock, yield token (or None if unavailable).
  - Spawn background heartbeat task: renew every `ttl_seconds / 3` until cap is reached.
  - On cap hit: stop renewing (lock expires, fail-closed).
  - On heartbeat returning False (loss of ownership): stop renewing, log warning.
  - On exit: signal heartbeat, await cleanup, release lock.

**Lease policy (hard contract):**
- Lock TTL is **per critical section**, not per whole workflow.
- If a critical section may exceed `T_lock`, use `lease(...)` for auto-renewal.
- Heartbeat interval = `T_lock / 3` (empirical tradeoff between responsiveness and chatter).
- **Hard `max_total_lease` ceiling:** once hit, renewal stops, lock expires (fail-closed zombie prevention).
- On `renew_lock` or heartbeat returning False: worker MUST cease work immediately.

**Responsibilities:**
- Provide non-blocking lock acquire (return None if unavailable; orchestrator owns retry).
- Atomic token-checked release and renewal (Lua scripts prevent ABA problem).
- Log loss-of-ownership as a CRITICAL signal for operator review.
- Enforce lease cap to prevent zombie processes.

**Does NOT:**
- Implement consensus or leader election (just a lease).
- Guarantee no overlap (overlap is detectable via version fencing in storage).
- Decide orchestrator-level retry backoff (orchestrator owns that).
- Manage the intent ledger (Phase 2).

---

### 4.4 `tests/`

**Purpose:** Adversarial async pytest suite covering all critical paths and concurrency races.

**Test structure:** pytest-asyncio with a real Redis instance (Docker or equivalent) or `fakeredis` that supports Lua + `cjson` module.

**Coverage areas:**
- **CAS write path:** first write, strictly increasing versions, stale writes, corrupt payload at write.
- **Get/read path:** missing key, valid round-trip, non-JSON, schema-invalid, unknown migrator, mismatch on execution_id.
- **Lock acquire/release/renew:** single worker, concurrent winners, token expiry, wrong token.
- **Concurrency races:** stale write after lease expiry, two workers racing CAS, version advancement across workers.
- **Lease cap:** renewal across multiple intervals, cap hit detection, fail-closed at ceiling.

**Responsibilities:**
- Verify every Definition-of-Done bullet (§4.4, §5.2 in brief).
- Exercise the three resolved hazards: (1) unified poison path, (2) fail-closed migration, (3) capped heartbeat.

---

## 5. Data Flow

### 5.1 Write Path (State Mutation)

1. **Caller obtains state lock:**
   ```
   token = await lock_mgr.acquire_lock(execution_id, ttl_seconds=60)
   if token is None:
       # cannot acquire; orchestrator backoff/retry
       return
   ```

2. **Caller reads current state:**
   ```
   state = await storage.get_state(execution_id)
   # May raise StateCorruptionError (quarantine + fail-closed)
   # May return None if execution_id is new
   ```

3. **Caller mutates state (increment version):**
   ```
   if state is None:
       state = AEPExecutionState(execution_id=..., status=IDLE, version=1, ...)
   else:
       state.version += 1
       state.updated_at = time.time()
   state.context_data["key"] = value  # or intent_ledger in Phase 2
   ```

4. **Caller persists via CAS:**
   ```
   try:
       await storage.save_state(state)
       # Success: version incremented, data written
   except StaleWriteError:
       # Another worker advanced the version; must re-read and rebase
   except StateCorruptionError:
       # Stored state is corrupt; fail-closed; propagate to orchestrator
   ```

5. **Caller releases lock:**
   ```
   success = await lock_mgr.release_lock(execution_id, token)
   if not success:
       logger.critical("Lock loss detected; overlap may have occurred.")
   ```

**CAS Lua return codes:**
- **`1`** → written successfully.
- **`-1`** → stale write (incoming version ≤ stored); raise `StaleWriteError`; caller must re-read and rebase.
- **`-2`** → stored payload corrupt/unversioned; quarantine + raise `StateCorruptionError`; fail-closed.

### 5.2 Read Path (State Fetch)

1. **Caller retrieves key from Redis:**
   ```
   raw = await redis.get(f"aep:state:{execution_id}")
   if raw is None:
       return None
   ```

2. **Parse JSON:**
   ```
   state_dict = json.loads(raw)
   # On JSONDecodeError: quarantine + StateCorruptionError
   ```

3. **Migrate schema if needed:**
   ```
   if state_dict["schema_version"] != CURRENT_SCHEMA_VERSION:
       state_dict = await _migrate_schema(state_dict)
       # On unknown version: quarantine + StateCorruptionError
   ```

4. **Validate against Pydantic model:**
   ```
   validated = AEPExecutionState.model_validate(state_dict)
   # On ValidationError: quarantine + StateCorruptionError
   ```

5. **Check key/payload consistency:**
   ```
   if validated.execution_id != execution_id:
       raise StorageOperationError("key/payload mismatch")
   ```

6. **Quarantine on any failure:**
   - Write to `aep:poison:{execution_id}:{timestamp}` (7-day TTL).
   - Log the corruption reason.
   - Raise the appropriate exception (StateCorruptionError preferred if corruption involved).

### 5.3 Lock Lifecycle

**Normal acquire-release flow:**
```
token = await acquire_lock(id, 60s)
# critical section (must complete in < 45s per Timeout Invariant)
await release_lock(id, token)  # returns True if still held
```

**Auto-renewing lease (for sections that may exceed TTL):**
```
async with await lease(id, ttl_seconds=60, max_total_lease=600) as token:
    if token is None:
        # lock unavailable
        return
    # critical section
    # heartbeat task renews every 20s (60/3)
    # if work exceeds 600s total, renewal stops (fail-closed)
    # on exit: signal stop, release
```

**Heartbeat renewal loop:**
- Wait `ttl / 3` (20s for 60s TTL).
- Check if `elapsed >= max_total_lease` (600s). If yes, log and stop renewing; let lock expire.
- Call `renew_lock(...)`, which extends TTL atomically (Lua script).
- If `renew_lock` returns False, log loss-of-ownership and stop (worker must cease work immediately).

---

## 6. Phase 2 Surfaces (Contract Only, NOT Implemented)

### 6.1 Write-Ahead Intent Ledger Workflow

The Phase 1 storage layer persists `intent_ledger` (a dict field in `AEPExecutionState`) but does NOT implement the workflow. Phase 2 will:

1. Before external API call: record `intent_ledger[step] = {"target": url, "status": "ABOUT_TO_FIRE"}`, increment version, save.
2. Execute external call (wrapped in timeout ≤ T_lock - 15s).
3. On completion: record `status: "COMPLETED_SUCCESSFULLY"` or failure detail, increment version, save.

**Phase 1 interface:** the storage layer must support round-trip of `intent_ledger` as a dict with arbitrary keys and values; no schema enforcement.

### 6.2 Recovery Resolver

On restart, if `get_state` returns an execution with intent at `ABOUT_TO_FIRE`, the external call is ambiguous (may have fired, may have timed out). Phase 2 will:

- NEVER auto-retry.
- Attempt external read-back if the API supports it.
- If ambiguous after read-back: escalate to operator (cannot proceed safely).

**Phase 1 interface:** the storage layer must preserve intent_ledger exactly; no mutations or cleanup.

### 6.3 Poison Ownership Split

- **Storage (Phase 1):** quarantine writes happen in `_quarantine()` (called by `get_state` on corruption). Best-effort; failures swallowed so as not to mask the original error.
- **Orchestrator (Phase 2):** periodically scans `aep:poison:*` keys, marks the execution FAILED on the dashboard, ejects from active scheduling. Does NOT re-implement quarantine logic.

**Phase 1 interface:** quarantine keys are written with reason and raw payload in JSON; 7-day TTL.

### 6.4 Systemic Circuit Breaker

If `StateCorruptionError` or `StorageOperationError` exceed a threshold (e.g., >5% of threads in a moving 60s window), the orchestrator trips a breaker: freeze scheduling read-only, alert ops.

**Phase 1 interface:** the exceptions are distinct so the orchestrator can count them separately from application logic errors.

---

## 7. Failure-Mode Catalogue

For each failure type: the exception raised, the condition, and the orchestrator's expected reaction.

| Failure Mode | Exception | Condition | Orchestrator Action |
|---|---|---|---|
| **Stale write** | `StaleWriteError` | Incoming version ≤ stored version. Expected under contention. | Re-read state, rebase local changes, retry CAS with incremented version. Do not immediately retry with same version. |
| **Corrupt write (stored payload unversioned)** | `StateCorruptionError` | Lua script finds stored JSON with no `version` field or unparseable. | Fail-closed: escalate to operator. Do not overwrite. Quarantine key already written by Lua path (pending Phase 2 cleanup). |
| **Missing key on get** | None (returns `None`) | `execution_id` has no state yet. | Not an error; normal for new executions. Caller constructs initial state. |
| **Unknown schema version, no migrator** | `StateCorruptionError` | Stored `schema_version` not in `SCHEMA_MIGRATIONS` chain. | Fail-closed: escalate to operator. Quarantine key written. This signals a code deployment mismatch (old Redis data, new code without migrator). |
| **Execution_id key/payload mismatch** | `StorageOperationError` | Redis key is `aep:state:X`, but payload claims `execution_id: Y`. | Fail-closed: escalate. Indicates corruption or operator error (manual Redis edit). Not retryable. |
| **Lock unavailable** | None (returns `None`) | Another worker holds the lease. | NOT an error. Orchestrator owns backoff/jitter policy. Caller may retry after delay or defer the work. |
| **Lock release with wrong/expired token** | bool `False` + warning log | `release_lock` called but lease already expired or held by another worker. | CRITICAL signal: log already emitted. Orchestrator MUST review logs for potential overlap. May not have affected state (CAS would have blocked stale writes), but overlap is possible. |
| **Lease renewal returns False** | bool `False` from `renew_lock`; heartbeat logs and stops | Worker no longer owns lease during renewal. Another worker may have acquired and advanced. | Worker MUST cease all in-flight work immediately (not just database work; abort external API calls, return control). Fail-closed: let the new worker take over. |
| **Lease cap hit** | Heartbeat stops; lock TTL expires; no exception raised | Auto-renewal elapsed ≥ `max_total_lease_seconds`. | Fail-closed: lock expires, work halts. Prevents zombie processes. Operator can detect by monitoring lease cap warnings in logs. |
| **Corrupt payload on read (JSON parse error)** | `StateCorruptionError` | JSON in Redis is malformed (not valid JSON). | Fail-closed: quarantine written, exception raised. Escalate to operator. |
| **Corrupt payload on read (schema validation fails)** | `StateCorruptionError` | JSON parses but fails Pydantic `AEPExecutionState` validation. | Fail-closed: quarantine written, exception raised. Escalate to operator. |
| **Redis transport/connection error** | `StorageOperationError` or `LockAcquisitionError` | Network fault, Redis down, auth failure. | Transient: orchestrator may retry with backoff if temporary. Sustained: escalate. Depends on root cause (operational issue vs. code bug). |

---

## 8. Open Questions & Explicit Non-Goals

### 8.1 Open Questions

1. **Schema migration at scale:** if the schema change requires a major data transformation (e.g., refactoring `intent_ledger` structure), how should very large states (>10MB) be handled? The current design assumes migrators are lightweight; if not, a separate migration service may be needed (Phase 2+ concern).

2. **Quarantine cleanup cadence:** the quarantine writes are best-effort and 7-day TTL is a placeholder. Should there be an explicit SLA for how often the orchestrator (Phase 2) must scan and eject poison keys, or is "as part of normal maintenance" acceptable?

3. **Clock skew across distributed agents:** the Timeout Invariant assumes `T_client <= T_lock - 15s`, but if multiple agents have clock skew >5s, the buffer may not suffice. Should the orchestrator enforce NTP sync, or should the buffer be larger?

4. **Redis persistence trade-off:** `appendfsync everysec` risks 1–2s of loss on crash. Is this acceptable for the target use case (autonomous agents), or should the brief recommend `always` for critical integrations, accepting the latency hit?

### 8.2 Explicit Non-Goals

- **This is NOT HA-safe.** Single Redis instance only. Master-replica failover would require handling replication lag and consensus; out of scope.
- **This is NOT exactly-once.** External side-effects (API calls) can duplicate if the lease expires during the call. Only the intent ledger (Phase 2) + Timeout Invariant can make duplicate detection possible; the system offers "detectable ambiguity + fail-closed," not prevention.
- **This is NOT a consensus primitive.** The lock is a lease; concurrent overlap is possible if the lease expires. Overlap is detectable via CAS versioning, but not prevented.
- **This is NOT a message queue.** The intent ledger is stored in the execution state, not a separate durable queue. Loss of recent intents on Redis crash is possible (mitigated by `appendfsync everysec` and operator recovery, Phase 2).
- **This does NOT provide automatic recovery.** On corruption, schema mismatch, or ambiguous intent, the system fails closed and escalates. Operator (or Phase 2 resolver) must diagnose and fix.

---

## Definition of Done Checklist

- [x] **All three invariants restated verbatim** in §3 with rationale.
- [x] **Honest-guarantee phrasing** used throughout (e.g., "Corruption and contention are detectable," not "absolute atomicity").
- [x] **No overclaims:** no "split-brain impossible," "exactly-once," "HA-safe" on single Redis.
- [x] **Every Phase 1 module** (`exceptions.py`, `storage.py`, `locks.py`, `tests/`) described with responsibilities and interfaces.
- [x] **No TODOs or placeholders** in the design (open questions are explicitly listed in §8.1).
- [x] **Phase 2 surfaces** (§6) described as contract only; no implementation logic included.
- [x] **Failure-mode catalogue** (§7) maps every error case to exception type, condition, and orchestrator action.
- [x] **Data flows** (§5) trace write path (CAS Lua codes), read path (parse → migrate → validate → quarantine), and lock lifecycle.

