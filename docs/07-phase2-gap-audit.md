# AEP Phase 2 gap audit

**Date:** 2026-07-28  
**Review type:** Read-only adversarial audit  
**Design baseline:** `docs/06-phase2-design.md`, especially Section 11  
**Implementation baseline:** `src/core/intents.py`, `intent_workflow.py`,
`intent_recovery.py`, `durability.py`, `storage.py`, and `locks.py`  
**Test baseline:** all five Phase 2 test modules, `tests/mock_connector.py`, and
`tests/conftest.py`  
**Report reviewed:** `phase2_implementation_report.md`

No production source or test file was changed during this audit. This document
is the only intended repository change.

## Executive verdict

Phase 2 is a useful fail-closed prototype, but it does **not** satisfy the
Section 11 gate and must not be enabled for production non-idempotent dispatch.
The strongest implemented properties are the token/version CAS checks, the
pre-dispatch status/TTL preflight, ambiguity-by-default response handling, and
read-only recovery. Those properties do not close the following blockers:

- a normal runner invocation can create another attempt after
  `FIRED_CONFIRMED` or `PERMANENTLY_AMBIGUOUS`, with no policy authorization or
  authenticated `risk_acceptance_id`;
- creating an intent can move a `PAUSED` execution to `PROCESSING` while a
  permanently ambiguous intent remains elsewhere in the ledger;
- the Phase 1 `save_state` API can rewrite a Phase 2 ledger without the Phase 2
  transition, audit, retention, or status rules;
- no exact immutable mutation request is bound to the recorded fingerprint, and
  the generated correlation ID is never passed to the connector;
- the real local durability barrier and startup validation do not exist;
- recovery discovery is concurrency-bounded but not memory-bounded;
- connector declarations, operator authentication, alerts, redaction, payload
  limits, and lifecycle retention are incomplete; and
- the named crash-point tests do not establish every required combination of
  hidden truth, caller evidence, durable persisted state, restart behavior, and
  absence of replay.

The governing guarantee therefore remains only:

> Ambiguity, corruption, and contention are detectable; the system fails closed.

Even that guarantee is not yet consistently enforced at every public write and
scheduling boundary identified below. Nothing in this audit asserts exactly-once
external effects, absolute atomicity, split-brain prevention, or guaranteed
duplicate prevention.

## Method and severity

This was a static source-and-test audit plus non-mutating runtime probes. The
Redis endpoint used by the existing reports was queried read-only. It responded
with `redis_version:3.0.504`, `appendonly:no`, and no `WAITAOF` command metadata.
No Redis keys were written or deleted by the audit probes.

- **Critical:** can directly authorize an unsafe external duplicate or bypass a
  governing safety invariant.
- **High:** production gate failure, broad recovery failure, or serious
  security/durability exposure.
- **Medium:** bounded-scope correctness, liveness, auditability, or resource
  weakness that does not by itself authorize a mutation.
- **Low:** narrow hardening or documentation issue.
- **P0:** must be fixed before any production non-idempotent dispatch.
- **P1:** fix before a production recovery/operator rollout.
- **P2:** subsequent hardening; do not silently accept.

## Section 11 acceptance status

| Acceptance criterion | Audit status | Concrete evidence |
|---|---|---|
| Every connector declares response classification and reconciliation capability | **Unmet** | `ConnectorPolicy` has two arbitrary string sets, but no complete response table tied to a connector version. Recovery reads `reconciliation_capability` dynamically at `src/core/intent_recovery.py:224-228`. There is no production connector registry or startup audit. |
| Redis supports an approved local durability barrier | **Unmet** | `RealWaitAofDurabilityBarrier.confirm_durable` only raises `NotImplementedError` (`src/core/durability.py:29-39`). The inspected Redis is 3.0.504 with AOF disabled. |
| Same-connection CAS plus `WAITAOF` is guaranteed | **Unmet** | Pinned-client orchestration exists (`src/core/intents.py:446-451`), but no `WAITAOF` command is implemented or integration-tested. |
| Scheduler, runner, resolver, and operator paths enforce the transition table | **Unmet** | Runner and resolver use the Phase 2 CAS, but no scheduler/operator implementation exists; normal intent creation has unsafe terminal-state eligibility; Phase 1 `save_state` remains a bypass. |
| Scanner and retention satisfy the recovery SLO | **Unmet** | `scan_once` accumulates all candidates and all gather awaitables (`src/core/intent_recovery.py:100-122`). There is no load/SLO test, per-candidate fault isolation, deployed alert sink, archive, or incident retention workflow. |
| Every Section 7 crash point has adversarial tests | **Partially met, not accepted** | Twenty-two names are triggerable, but several `DURING_*_CAS` checkpoints execute before the CAS, all durability tests use a fake barrier, and the parameterized runner test does not assert the complete oracle/evidence/persistence/replay tuple. |
| Documentation and telemetry use detectable ambiguity plus fail-closed, never exactly once | **Partially met** | The principal design/source wording is appropriately bounded. Production telemetry does not exist, and the implementation report overstates scanner boundedness and crash-test completeness. |

Because Section 11 says implementation must not begin until all seven conditions
are agreed, the gate as a whole is **not passed**.

## Confirmed defects and implementation gaps

### P2-001 - Retry eligibility permits unsafe new external attempts

- **Severity:** Critical
- **Design requirement:** Section 4 says `FIRED_CONFIRMED` is terminal; Section
  8.4 says only `FAILED_CONFIRMED` can make a normal new attempt eligible; Section
  4.1 requires an audited risk override with a new authenticated
  `risk_acceptance_id` after permanent ambiguity.
- **Exact evidence:** `UNRESOLVED_INTENT_STATUSES` contains only
  `ABOUT_TO_FIRE` and `FIRED_UNCONFIRMED` (`src/core/intents.py:42-44`).
  `create_intent` always computes `max(attempt)+1` (`:507-512`) and accepts an
  optional, unconstrained `risk_acceptance_id` (`:493-496`, `:541`). The Lua
  creation branch checks only record addition, max attempt, and prepared version
  (`:311-327`); it does not inspect the prior terminal status. The public runner
  has no retry-policy or risk-acceptance argument (`src/core/intent_workflow.py:178-186`).
- **Consequence:** Calling the runner again for the same stable `step_id` after a
  confirmed success dispatches another mutation. Calling it after permanent
  ambiguity also dispatches without authenticated duplicate-risk acceptance.
  This violates fail-closed behavior and can create a duplicate external effect.
- **Missing regression test:** For the same execution/step, assert that a new
  normal attempt is rejected after `FIRED_CONFIRMED`, is policy-gated after
  `FAILED_CONFIRMED`, is rejected after `PERMANENTLY_AMBIGUOUS` without a
  verified risk decision, rejects an empty/forged ID, and is allowed only through
  the audited override path. Assert zero connector mutation calls on rejection.
- **Recommended minimal fix:** Put attempt-eligibility checks in the same Lua
  creation CAS. Keep normal creation and a privileged risk-override creation
  path distinct. The override must receive a verifier-approved opaque decision
  object, persist its ID and authenticated actor/ticket, and never treat a raw
  caller-supplied string as authentication.
- **Implementation priority:** P0

### P2-002 - Intent creation can clear a global ambiguity fence

- **Severity:** Critical
- **Design requirement:** Section 8.4 requires any execution containing
  `ABOUT_TO_FIRE`, `FIRED_UNCONFIRMED`, or `PERMANENTLY_AMBIGUOUS` to be ejected
  from normal scheduling.
- **Exact evidence:** `Phase2ExecutionState` enforces at most one unresolved
  intent only per `step_id` (`src/core/intents.py:215-232`), and permanent
  ambiguity is not in the unresolved set. `create_intent` unconditionally writes
  top-level `status=PROCESSING` (`:545-551`) without checking for a blocking
  intent on the same or another step. The Lua script has no global scheduling
  fence check.
- **Consequence:** A runner invocation for step B can turn an execution from
  `PAUSED` to `PROCESSING` and dispatch while step A remains permanently
  ambiguous. This is a direct fail-closed violation independent of the same-step
  retry defect in P2-001.
- **Missing regression test:** Seed a paused execution with permanent ambiguity
  on step A; run step B and assert the create CAS fails, the top-level status
  remains `PAUSED`, the version and ledger remain unchanged, and the connector
  call count stays zero. Repeat for `FIRED_UNCONFIRMED` and stale
  `ABOUT_TO_FIRE`.
- **Recommended minimal fix:** Make the Lua creation branch reject normal intent
  creation when any blocking status exists anywhere in the ledger. Permit an
  override only through the authenticated path described in P2-001, without
  automatically changing the top-level status.
- **Implementation priority:** P0

### P2-003 - The Phase 1 state writer bypasses all Phase 2 ledger invariants

- **Severity:** Critical
- **Design requirement:** Sections 4.1 and 6.1 require every intent transition to
  use the lock-token/expected-version CAS that validates the legal transition,
  append-only audit, execution status, and retention.
- **Exact evidence:** The base schema intentionally accepts
  `intent_ledger: Dict[str, Any]` (`src/core/storage.py:107-111`).
  `RedisStorageAdapter.save_state` writes the same `aep:state:{execution_id}` key
  after checking only schema version, lock token, and consecutive execution
  version (`:347-465`). It does not detect that a ledger is a Phase 2 ledger and
  does not invoke `_INTENT_CAS_SCRIPT`. No schema/version marker separates the
  two write modes.
- **Consequence:** Any lock-owning scheduler or operator using the pre-existing
  public storage API can delete an intent, rewrite immutable fields or audit
  history, change `PAUSED` to a schedulable status, or use a shorter TTL while
  still passing the Phase 1 CAS. Phase 2's authoritative validation is therefore
  not authoritative across public repository write paths.
- **Missing regression test:** Create a typed Phase 2 state, then attempt through
  `RedisStorageAdapter.save_state` to delete/change an intent, unpause a blocked
  execution, and lower retention. Every write must fail and leave raw Redis
  bytes unchanged.
- **Recommended minimal fix:** Add an explicit Phase 2 state/write-mode marker
  and make the base CAS reject Phase 2 ledger changes, or consolidate all state
  writes behind one script that dispatches to the full Phase 2 invariants. Do
  not rely on callers to choose the correct adapter.
- **Implementation priority:** P0

### P2-004 - The mutation is not bound to an exact immutable request

- **Severity:** High
- **Design requirement:** Section 3 requires a fingerprint of the canonical,
  secret-free request; Section 5 requires the write-ahead record to describe the
  mutation actually dispatched and recommends sending the correlation ID.
- **Exact evidence:** `ExternalMutationConnector.mutate` receives only
  `intent_id` and `client_timeout` (`src/core/intent_workflow.py:23-26`).
  `execute` receives only caller-supplied `target` and `request_fingerprint`
  metadata (`:178-186`), then calls the connector with only the two protocol
  arguments (`:289-293`). The generated `correlation_id` is persisted but never
  passed to `mutate`. Recovery likewise calls `read_back(intent_id=...)` only
  (`src/core/intent_recovery.py:244-245`).
- **Consequence:** A production connector must obtain the request from mutable
  closure/global state or an undocumented side store. AEP cannot prove that the
  fingerprint and target describe the bytes sent, cannot attach its generated
  correlation ID, and may lack the provider identifiers needed for read-back.
- **Missing regression test:** Mutate the caller's original request after
  preparation and prove the dispatched request remains unchanged; prove AEP
  computes/verifies the canonical fingerprint; prove the stored correlation ID
  is the one sent; prove raw secrets/PII never appear in Redis, logs, exceptions,
  or quarantine.
- **Recommended minimal fix:** Introduce a frozen `PreparedMutation` produced by
  a versioned connector. It should contain an in-memory typed dispatch request,
  redacted target, secret-free canonical representation/fingerprint, and opaque
  secret references. Persist only redacted metadata and the computed hash. Pass
  the prepared object plus the persisted correlation ID to `mutate`. Resolve
  credentials just in time from a secret manager. If request material must
  survive process loss for non-mutation purposes, store only an opaque handle to
  an encrypted, access-controlled request vault with explicit retention; do not
  store the raw request in the intent ledger. Pass a redacted reconciliation
  context derived from `IntentRecord` to `read_back`.
- **Implementation priority:** P0

### P2-005 - Production durability and its startup gate are absent

- **Severity:** High
- **Design requirement:** Sections 6.2 and 11 require approved local AOF
  durability, same-connection CAS plus `WAITAOF`, and dispatch disablement when
  unavailable.
- **Exact evidence:** `RealWaitAofDurabilityBarrier` is only a fail-closed stub
  (`src/core/durability.py:29-39`). `FakeDurabilityBarrier` is shipped in the
  production package (`:18-26`), and `WriteAheadRunner` accepts any barrier with
  no production-mode guard (`src/core/intent_workflow.py:106-127`). The inspected
  endpoint reported Redis 3.0.504 and `appendonly=no`; `WAITAOF` is unavailable.
  `tests/test_phase2_durability.py:25-30` asserts the stub rather than real
  durability.
- **Consequence:** The current artifact cannot authorize production dispatch
  under the design. A caller can nevertheless instantiate the runner with the
  fake barrier and dispatch without a local fsync guarantee.
- **Missing regression test:** Against Redis 7.2+ with AOF enabled, verify
  same-connection ordering and `WAITAOF 1 0 timeout`; cover acknowledged,
  timeout, command error, AOF-disabled, too-old Redis, connection replacement,
  and startup refusal. Every unapproved case must show zero connector calls.
- **Recommended minimal fix:** Implement the real barrier and one mandatory
  startup capability check. Keep the fake in test-only code or require an
  explicit non-production construction mechanism that production bootstrap
  rejects.
- **Implementation priority:** P0

### P2-006 - Connector declarations are neither complete nor startup-validated

- **Severity:** High
- **Design requirement:** Sections 5 and 8.3 require an explicit response
  classification table and exactly one reconciliation capability for every
  non-idempotent connector; Section 11 makes that a startup gate.
- **Exact evidence:** `ConnectorPolicy` validates only that two arbitrary string
  sets are non-empty and disjoint (`src/core/intent_workflow.py:48-88`). The
  policy is not declared by or cryptographically/configurationally bound to the
  versioned connector name. Recovery discovers capability with nested `getattr`
  at execution time (`src/core/intent_recovery.py:224-228`), and missing connector
  configuration is found only when an intent is recovered (`:173-181`). There is
  no registry/bootstrap module in the repository.
- **Consequence:** A typo, capability/method mismatch, name/version drift, or
  unsafe allowlist can reach live work. An incorrectly allowlisted value can be
  persisted as definitive; a missing `read_back` can terminate recovery.
- **Missing regression test:** Startup must reject unknown capabilities, missing
  or extra methods, incomplete/overlapping tables, illegal result classes for a
  capability, duplicate connector names, unversioned names, and production use
  of a fake barrier.
- **Recommended minimal fix:** Define a typed immutable connector descriptor
  containing versioned operation name, complete mutation response table,
  reconciliation capability/result table, timeouts, settlement semantics,
  redactor/canonicalizer, and durability mode. Validate the entire registry
  before accepting scheduling traffic.
- **Implementation priority:** P0

### P2-007 - `scan_once` is not memory-bounded

- **Severity:** High
- **Design requirement:** Sections 8.1 and 11 require cursor scanning with a
  bounded amount of concurrent processing sufficient for the recovery SLO.
- **Exact evidence:** `scan_once` appends every eligible pair to one
  `candidates` list (`src/core/intent_recovery.py:100-112`), creates one bounded
  coroutine/awaitable per candidate for `asyncio.gather` (`:113-121`), and
  returns a list containing every result (`:122`). The semaphore limits active
  bodies, not candidate, task, or result allocation.
- **Consequence:** Memory is O(total eligible intents), so the recovery worker
  can exhaust memory precisely during a large ambiguity backlog. `SCAN COUNT`
  is a server hint and does not bound the Python pass.
- **Missing regression test:** Feed a large synthetic async scan iterator and
  instrument outstanding tasks and retained candidate/result objects; assert
  they never exceed a configured bound while every candidate is processed.
- **Recommended minimal fix:** Process each scan page through a fixed worker
  pool or bounded task set and stream results/metrics instead of returning the
  entire pass as a list. If callers require detailed results, use a bounded sink
  or async iterator.
- **Implementation priority:** P1

### P2-008 - One bad candidate can terminate continuous recovery

- **Severity:** High
- **Design requirement:** Section 8 requires a continuous service, normal
  validated corruption handling, recovery-lag alerting, and circuit-breaker
  behavior for systemic faults.
- **Exact evidence:** `scan_once` does not isolate exceptions from
  `get_execution` (`src/core/intent_recovery.py:102-111`) or `gather`
  (`:119-121`). `run_forever` calls `scan_once` without a top-level exception
  route (`:135-146`). A missing connector raises (`:177-181`), and every
  read-back exception, including ordinary connector exceptions, is re-raised
  (`:244-248`). The only alert hook is for a successfully completed but slow
  pass (`:57`, `:139-142`). No systemic circuit breaker exists.
- **Consequence:** One corrupt record, connector outage, malformed registration,
  or read-back exception can end recovery for all executions without a lag or
  critical ambiguity alert. Other gathered tasks may also continue after the
  caller has already unwound, complicating shutdown and observability.
- **Missing regression test:** Place one corrupt/failing candidate beside a valid
  ambiguous candidate; assert the valid candidate is still processed, the fault
  is quarantined/classified, the loop remains alive or deliberately trips a
  tested breaker, and the proper alert fires. Test cancellation/shutdown with
  in-flight workers.
- **Recommended minimal fix:** Add per-candidate exception isolation with typed
  outcomes, a top-level pass guard, structured alerts, and the specified systemic
  circuit breaker. Preserve fail-closed semantics: connector/query failure must
  never be converted to `NOT_APPLIED`.
- **Implementation priority:** P0

### P2-009 - Operator resolution, authentication, and ambiguity alerts are absent

- **Severity:** High
- **Design requirement:** Section 8.4 requires a warning on first ambiguity, a
  critical incident on permanent ambiguity, and manual resolution with lease,
  re-read, durable CAS, authenticated operator, ticket/evidence reference, and
  reason.
- **Exact evidence:** The recovery service exposes only `recovery_lag_alert`
  (`src/core/intent_recovery.py:57`, `:139-142`). No ambiguity/critical incident
  hook or operator API exists. `transition_intent` accepts arbitrary non-empty
  `actor` and `reason`, optional evidence, and allows permanent ambiguity to a
  confirmed state (`src/core/intents.py:565-660`) without authentication or a
  required ticket/evidence reference.
- **Consequence:** Ambiguity is stored but may never be surfaced, while a direct
  caller with a lock can impersonate an operator and resolve a permanent
  incident. This is detectable only by inspecting whatever actor string the
  caller chose.
- **Missing regression test:** Verify warning/critical hooks fire only after the
  corresponding Redis transition is durable; verify retries do not duplicate an
  incident; reject unauthenticated actors and missing ticket/evidence; test stale
  token/version fencing on the operator path.
- **Recommended minimal fix:** Add an authenticated operator service/facade and
  durable outbox or retryable incident hook keyed by transition identity. Keep
  Redis authoritative and document that alert delivery is not atomic with it.
- **Implementation priority:** P0

### P2-010 - Secret/PII redaction is contractual prose, not an enforced boundary

- **Severity:** High
- **Design requirement:** Section 3 forbids credentials in `target`, requires a
  secret-free request fingerprint, and permits only redacted observations.
- **Exact evidence:** `target`, `connector`, observation `detail`, audit `actor`
  and `reason`, `external_reference`, and `risk_acceptance_id` are plain strings
  with no redaction type or allowlist (`src/core/intents.py:105-174`). A runtime
  schema probe showed only `min_length=1` on `target`/`actor` and no constraints
  on `risk_acceptance_id`. Connector-provided `external_reference` is persisted
  directly (`src/core/intent_workflow.py:304-335`). On corruption, the complete
  raw state is copied into a poison record (`src/core/storage.py:605-649`).
- **Consequence:** A caller or connector can persist credentials, request PII,
  response content, or an oversized identifier in both the state and its
  quarantine copy. Seven-day poison retention increases exposure; future alerts
  may repeat it.
- **Missing regression test:** Use secret and PII canaries in every input and
  connector output; assert raw Redis state, poison records, logs, exceptions,
  alerts, and model dumps contain only approved redacted/hashed values. Include
  redactor failure and malicious oversized values.
- **Recommended minimal fix:** Introduce validated redacted value objects and
  connector-owned canonicalizer/redactor functions; allowlist characters and
  lengths; accept opaque secret references only; sanitize or encrypt quarantine
  payloads under a separately reviewed forensic-access policy.
- **Implementation priority:** P0

### P2-011 - Typed validation accepts corrupt audit/history relationships

- **Severity:** High
- **Design requirement:** Sections 3 and 4 require immutable records, legal
  append-only transition history, exact reconciliation bookkeeping, and
  detectable corruption through the normal validated read path.
- **Exact evidence:** `IntentRecord` checks only that `reconcile_after` is not
  before `prepared_at`, the last transition ends at current status, and
  `FIRED_UNCONFIRMED` has reconciliation data (`src/core/intents.py:197-207`).
  It does not validate the first edge, every edge's legality/continuity, timestamp
  order, initial prepared version, the reconcile-after formula, or reconciliation
  time/count consistency. A non-mutating probe successfully validated an intent
  whose sole transition was illegal `NONE -> FIRED_CONFIRMED`.
- **Consequence:** Corrupted or manually injected history can pass
  `get_execution` as valid, avoiding quarantine and allowing recovery/operator
  decisions based on internally contradictory evidence. That narrows the honest
  corruption-detectability claim.
- **Missing regression test:** Inject raw records with every broken relationship
  above and assert `get_execution` raises `StateCorruptionError`, writes a
  sanitized quarantine record, and performs no connector operation.
- **Recommended minimal fix:** Add full cross-field/history validation to the
  frozen models and mirror all race-sensitive invariants in Lua. Validate a
  contiguous legal transition chain and coherent server times/progress without
  attempting to repair corrupt history.
- **Implementation priority:** P1

### P2-012 - Payload growth and retention lifecycle are not bounded operationally

- **Severity:** Medium
- **Design requirement:** Sections 3, 8.1, and 9 state that retention is bounded
  while unresolved evidence remains available for the reconciliation plus
  operator window.
- **Exact evidence:** There are no maximum lengths for persisted strings, no cap
  on ledger entries or transition history, and no maximum serialized state size
  (`src/core/intents.py:105-232`). Intent deletion is forbidden, while every
  transition rewrites the entire JSON and resets the default 31-day TTL
  (`:662-695`). There is no archive/incident store or terminal-execution cleanup
  workflow. The Phase 1 writer bypass in P2-003 can also apply its 48-hour
  default to a Phase 2 state.
- **Consequence:** Long-lived/retried executions can make CAS, reads, quarantine,
  and recovery scans increasingly expensive. Conversely, a permanently
  ambiguous record eventually expires with the whole state if it is not copied
  to an operator system, leaving no repository-defined tombstone or closure
  procedure.
- **Missing regression test:** Enforce and test maximum field/state/ledger sizes,
  TTL at every unresolved and permanent transition, archive handoff, expiry, and
  behavior when the archive/incident sink is unavailable.
- **Recommended minimal fix:** Define explicit byte/entry limits and a terminal
  execution archival policy. Retain the immutable active ledger until durable
  archive/incident acknowledgement, then expire the whole terminal execution
  under a documented policy rather than deleting individual intents.
- **Implementation priority:** P1

### P2-013 - Crash-boundary acceptance evidence is incomplete

- **Severity:** High (acceptance-test gap)
- **Design requirement:** Section 11 requires adversarial tests for every Section
  7 crash point. The requested audit standard requires hidden ground truth,
  caller evidence, persisted state, and no mutation replay at every boundary.
- **Exact evidence:** The runner's `DURING_INTENT_CAS` checkpoint runs before
  entering the CAS (`src/core/intent_workflow.py:202-204`), and
  `DURING_RESOLUTION_CAS` runs before the resolution CAS (`:323-325`); the tests
  therefore cover only the pre-command outcome, not the design's either-state
  uncertainty. Every workflow uses `FakeDurabilityBarrier`
  (`tests/test_phase2_runner.py:95-116`,
  `tests/test_phase2_recovery.py:113-125`). The general runner crash test asserts
  expected intent status and only a one-way rule for caller-unproven calls
  (`tests/test_phase2_runner.py:119-157`); it does not assert exact call count,
  every hidden truth, raw persisted evidence, restart reconciliation, or replay
  absence. One dedicated applied connection-drop test does those checks for one
  case (`:191-251`), and one separate recovery test checks a pre-seeded call
  (`tests/test_phase2_recovery.py:317-341`).
- **Consequence:** The suite cannot support the report's Section 11 **Met**
  verdict. Reply loss, process restart, Redis restart/AOF survival, and combined
  runner-to-recovery behavior remain unproved.
- **Missing regression test:** For every crash boundary and every permitted
  hidden truth, assert exact mutation-call count, oracle truth, caller-visible
  evidence, returned exception/result, typed and raw persisted state/history,
  restart behavior, read-back count, and unchanged mutation count after recovery.
  Add real Redis 7.2+ process/AOF tests for the durability boundaries.
- **Recommended minimal fix:** Strengthen the existing matrix without removing
  assertions. Place hooks on both sides of commands; use controlled connection
  loss/reply loss for uncertain CAS outcomes; add end-to-end restart scenarios
  and a separate real-AOF integration tier.
- **Implementation priority:** P0 as an acceptance gate

### P2-014 - Read-back has no enforced timeout or correctly sized capped lease

- **Severity:** Medium
- **Design requirement:** Section 8.2 requires read-only reconciliation while
  holding a capped lease sized to read timeout plus the 15-second buffer.
- **Exact evidence:** Recovery acquires the mutation policy's fixed
  `lock_ttl_seconds` (`src/core/intent_recovery.py:148-160`) and invokes
  `read_back(intent_id=...)` with no timeout (`:244-245`). There is no read-back
  timeout field, `asyncio.timeout`, lease renewal, or hard-cap integration.
- **Consequence:** A hung connector can stall the whole pass, exceed the lease,
  permit overlapping read-backs, and later fail its CAS as stale. The stale
  token/version checks preserve state safety, but recovery liveness and the
  five-minute SLO do not hold.
- **Missing regression test:** Hang read-back beyond its deadline and lock TTL;
  assert it is cancelled/fenced before unsafe persistence, mutation count stays
  unchanged, the pass remains observable, and the next resolver can recover.
- **Recommended minimal fix:** Add a declared read-back timeout, size a capped
  token-checked lease to timeout plus buffer, and wrap the query in an enforced
  timeout. Treat timeout as unknown/operational failure according to the
  connector contract, never as authoritative absence.
- **Implementation priority:** P1

### P2-015 - Locks are released even when resolution durability is unconfirmed

- **Severity:** Medium
- **Design requirement:** Section 5 says release occurs after the resolution is
  durably acknowledged; if durability cannot be confirmed, alert and leave the
  execution for recovery.
- **Exact evidence:** Both runner and resolver release in unconditional `finally`
  blocks (`src/core/intent_workflow.py:355-356`,
  `src/core/intent_recovery.py:314-315`). A failed resolution barrier therefore
  deliberately unlocks the visible but not durability-confirmed state. A release
  exception can also replace an earlier workflow exception.
- **Consequence:** Another worker can act on a resolution that was not confirmed
  to local AOF, and the primary durability failure may be obscured by cleanup
  failure. CAS/recovery remain conservative after loss, but the documented
  durability/lease ordering and auditability are not implemented.
- **Missing regression test:** Fail/raise the post-resolution barrier and assert
  no mutation replay, primary error preservation, a critical alert, and the
  specified lock-expiry/recovery behavior. Separately fail lock release while a
  primary workflow error is active and assert both failures remain observable.
- **Recommended minimal fix:** Track whether the required barrier succeeded.
  Follow the design's explicit release policy; on unconfirmed durability, alert
  and let the bounded lease expire or execute a separately designed safe handoff.
  Preserve the primary exception and attach/log cleanup failure without masking.
- **Implementation priority:** P1

### P2-016 - Test cleanup can be opted into a non-dedicated Redis database

- **Severity:** Medium (test-infrastructure safety)
- **Design requirement:** Audit hard rule: tests may delete only `aep:*` keys in
  dedicated Redis DB 15 and must never use `FLUSHALL`.
- **Exact evidence:** Cleanup correctly scans/deletes only `aep:*`
  (`tests/conftest.py:129-138`) and never calls `FLUSHALL`, but
  `AEP_TEST_ALLOW_FLUSHALL=1` permits a real Redis database other than 15
  (`:105-125`). The variable name is also misleading because cleanup never uses
  `FLUSHALL`.
- **Consequence:** An opted-in test run can delete production-like `aep:*` keys
  outside the dedicated test DB, contrary to the hard rule.
- **Missing regression test:** Set a non-15 Redis URL with the override present
  and assert fixture setup still refuses cleanup; verify unrelated and non-`aep`
  keys remain untouched in DB 15.
- **Recommended minimal fix:** Remove the override path and require DB 15
  unconditionally for real-Redis cleanup. Rename/remove the misleading variable.
- **Implementation priority:** P1

### P2-017 - Phase 2 implementation began before its prerequisites were met

- **Severity:** High (process and acceptance gate)
- **Design requirement:** Section 11: “Phase 2 implementation must not begin
  until reviewers agree” to all listed conditions.
- **Exact evidence:** The design still says “Proposed for review; no
  implementation exists yet” (`docs/06-phase2-design.md:3`), while
  `phase2_implementation_report.md:10-49` records implemented modules. The same
  report explicitly marks the durability deployment **Unmet** and four other
  criteria **Partially met** (`phase2_implementation_report.md:293-303`). The
  inspected Redis objectively lacks the required version and AOF mode. No Phase
  2 approval record exists in the repository.
- **Consequence:** Implementation and its reported 190-test result may be
  mistaken for an accepted production design even though the design's own
  precondition was false. This is a governance defect, not proof that every
  implemented prototype path is unsafe.
- **Missing regression test:** Not solely a unit-test concern. CI/release policy
  must require a signed Section 11 checklist plus executable startup/integration
  evidence before production dispatch artifacts can be enabled.
- **Recommended minimal fix:** Mark the implementation explicitly
  experimental/dispatch-disabled, obtain review after P0 fixes, and record the
  approved checklist with environment evidence. Update the design status only
  after the gate is actually met.
- **Implementation priority:** P0 release gate

### P2-018 - The implementation report overstates completed coverage

- **Severity:** Medium (documentation accuracy)
- **Design requirement:** Section 11 requires honest, evidence-backed claims;
  the governing guarantee must not be broadened by implication.
- **Exact evidence:** The report describes scanner discovery as having “bounded
  concurrency” (`phase2_implementation_report.md:41-44`) and its acceptance row
  cites that as partial SLO evidence (`:301`), without disclosing that all
  candidates/tasks/results are retained. It marks every Section 7 crash point
  **Met** (`:302`) despite P2-013. Its implementation summary calls response
  declarations explicit (`:33-34`) although the full per-connector table/startup
  contract is absent. The report does honestly disclose the fake barrier,
  missing production connectors, scheduler, operator API, and telemetry
  (`:297-318`); those disclosures should be preserved.
- **Consequence:** Reviewers may infer memory-bounded recovery or complete crash
  evidence from a green test count and enable Phase 2 prematurely.
- **Missing regression test:** Add documentation/acceptance checks that link each
  “Met” row to executable tests and deployment probes; fail the gate when any
  required dimension is simulated only or lacks assertions.
- **Recommended minimal fix:** Change the crash criterion to partial/unmet,
  explicitly say concurrency-bounded but O(N) memory, distinguish declared
  string allowlists from a complete response table, and link this audit as the
  current gap register.
- **Implementation priority:** P1

## Design decisions and open questions (not confirmed bugs)

### P2-D01 - Safe exit from `PAUSED` is intentionally undefined

- **Severity:** Design decision / liveness gap, not a confirmed safety defect
- **Design requirement:** Section 8.4 defines entry into `PAUSED` and manual
  intent resolution but does not define the execution status to restore after
  the last ambiguous intent is resolved.
- **Exact evidence:** `transition_intent` sets `PAUSED` on ambiguity and otherwise
  retains the current top-level status (`src/core/intents.py:636-649`). Thus a
  permanent ambiguity resolved to `FIRED_CONFIRMED` or `FAILED_CONFIRMED` remains
  `PAUSED`. There is no scheduler/operator resume API. Using Phase 1
  `save_state` could change the status, but that is unsafe due to P2-003.
- **Consequence:** The current supported Phase 2 path cannot safely resume the
  execution after all ambiguity is resolved. Remaining paused is the safer
  behavior, so it should not be “fixed” by automatic unpause without a policy.
- **Missing regression test:** Resolve one of multiple ambiguous intents and
  prove status remains paused; resolve the last one and exercise an explicit,
  authenticated resume decision; reject resume if any blocking intent or other
  pause reason remains.
- **Recommended minimal fix:** Decide and document resume semantics. Prefer a
  dedicated authenticated CAS that re-reads the full ledger, verifies no
  blocking intent and no independent pause reason, records the decision, and
  moves to an explicitly chosen allowed status. Do not infer a pre-pause state.
- **Implementation priority:** P1 design decision

### P2-D02 - Do not persist the raw mutation request merely to fill P2-004

- **Severity:** Security design decision
- **Design requirement:** Section 3 intentionally stores a secret-free hash and
  redacted target, not unrestricted request content.
- **Exact evidence:** The ledger schema has no raw-request field
  (`src/core/intents.py:152-174`). This absence is correct; the connector call
  interface is what is incomplete.
- **Consequence:** Adding a raw request field would expose secrets/PII through
  normal state, quarantine, backups, and operator tooling.
- **Missing regression test:** The P2-004/P2-010 canary tests should explicitly
  reject raw request serialization.
- **Recommended minimal fix:** Keep the exact request in a frozen ephemeral
  dispatch object or separately governed secure vault, and persist only safe
  binding metadata.
- **Implementation priority:** P0 design constraint

## Confirmed correct controls in the inspected paths

These observations narrow the findings; they are not broader guarantees:

- `_INTENT_CAS_SCRIPT` rechecks the live ownership token and exact consecutive
  version in the same Lua invocation (`src/core/intents.py:238-258`).
- The preflight atomically checks token, lease TTL, prepared version, and
  `ABOUT_TO_FIRE` status (`src/core/intents.py:400-413`).
- Unknown mutation responses and ordinary mutation exceptions become
  `FIRED_UNCONFIRMED`, not confirmed failure (`src/core/intent_workflow.py:294-321`).
- Recovery calls `read_back` and contains no call to `mutate`
  (`src/core/intent_recovery.py:168-364`).
- The intended Phase 2 CAS rejects deletion, immutable-field changes, stale
  tokens/versions, and illegal per-intent edges. The bypass in P2-003 is a
  separate public write path, not a flaw in those individual checks.
- The late-original-worker test exercises stale token/version fencing
  (`tests/test_phase2_recovery.py:282-314`). No stale-token or stale-version
  defect was found in the intended runner/resolver CAS paths.
- `asyncio.CancelledError` is not swallowed by the runner's `except Exception`
  block on Python 3.13. Integrated cancellation coverage is still incomplete as
  described in P2-013 and P2-015.

## Explicit non-goals and accepted residual risks

The following are design non-goals, not defects found by this audit:

- exactly-once provider execution or delivery;
- absolute atomicity between Redis and an external provider;
- split-brain prevention or HA/consensus on the single-Redis topology;
- guaranteed duplicate prevention after an authenticated operator accepts risk;
- recovery after catastrophic loss of the Redis host/storage;
- provider-side recall when client cancellation/timeout occurs;
- authoritative negative inference from positive-only/eventually consistent APIs;
- atomic alert delivery with Redis state;
- compensation of an already confirmed external effect; and
- a secondary recovery index. The Section 8 `SCAN` choice is deliberate, though
  its Python processing must still be memory-bounded.

## Recommended implementation order

1. **P0 safety gate:** P2-001 through P2-006, P2-008 through P2-010, P2-013,
   and P2-017. Keep production dispatch disabled throughout.
2. **P1 recovery/operator hardening:** P2-007, P2-011 through P2-016, P2-018,
   and the explicit `PAUSED` resume decision P2-D01.
3. Re-run startup probes, `py_compile`, focused regressions, the complete suite,
   large-backlog recovery tests, and real Redis 7.2+ AOF crash tests before
   reconsidering Section 11.

## Audit limitations

- This repository has no `.git` metadata at the inspected path, so historical
  author/reviewer identity and uncommitted-change attribution cannot be verified.
- Static inspection cannot prove external connector semantics, provider
  settlement behavior, secret-manager policy, alert delivery, disk-controller
  durability, or production load/SLO performance.
- The local Redis query characterizes only `127.0.0.1:6380/15` at audit time; it
  is not evidence about another deployment.
- Passing fake-barrier tests demonstrate control flow, not disk durability.

