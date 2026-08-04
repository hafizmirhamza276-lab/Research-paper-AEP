# AEP Phase 2 post-WAITAOF acceptance-gate review

**Date:** 2026-07-29  
**Review type:** Read-only post-WAITAOF adversarial reconciliation  
**Design baseline:** `docs/06-phase2-design.md` and
`docs/08-production-connector-design.md`  
**Finding baseline:** P2-001 through P2-018 in
`docs/07-phase2-gap-audit.md`  
**Runtime baseline:** Redis 7.2.5, AOF enabled, dedicated DB 15

No production source or existing test was changed. This document is the only
intended repository change. The repository has no usable Git metadata at this
path, so preservation was checked with a SHA-256 manifest of all pre-existing
files; the pre-review tree hash, excluding this new document, was
`91DB123A98FFADF0C7849BD938CE243A458378F55FF83AA90C682A3672A89010`.

## 1. Executive decision

**NO-GO for production non-idempotent dispatch.**

The real local durability mechanism is implemented and the reported 218-test
result is reproducible. That closes most of the technical substance of the old
WAITAOF sub-gap, but it does not close the Phase 2 gate. Fifteen findings remain
`OPEN`; P2-005, P2-013, and P2-018 are `PARTIALLY CLOSED`; none of P2-001 through
P2-018 is fully `CLOSED`, `SUPERSEDED`, or a `DESIGN DECISION`.

The three most direct mutation-safety defects remain reproducible on the current
code with the real barrier:

- after `FIRED_CONFIRMED`, a second normal invocation created attempt 2 and made
  a second provider call;
- after `PERMANENTLY_AMBIGUOUS`, a normal invocation created attempt 2 with
  `risk_acceptance_id=None` and called the provider;
- while one step remained `PERMANENTLY_AMBIGUOUS`, another step dispatched and
  the top-level execution status became `PROCESSING`;
- a current lock owner used the Phase 1 `save_state` path to delete an
  `ABOUT_TO_FIRE` ledger and change the execution to `IDLE`.

The bounded governing guarantee remains:

> “Ambiguity, corruption, and contention are detectable; the system fails closed.”

The current public write and scheduling boundaries do not enforce that guarantee
consistently enough for production enablement. This review does not claim
exactly-once external effects, absolute atomicity, split-brain prevention, or
guaranteed duplicate prevention.

## 2. Classification summary

| Finding | Classification | Priority | Gate reason |
|---|---|---:|---|
| P2-001 | **OPEN** | P0 | Normal creation still permits attempts after confirmed success and permanent ambiguity. |
| P2-002 | **OPEN** | P0 | Intent creation can still clear an execution-wide ambiguity fence. |
| P2-003 | **OPEN** | P0 | Phase 1 `save_state` still rewrites Phase 2 ledgers. |
| P2-004 | **OPEN** | P0 | The approved connector request-binding design is not implemented. |
| P2-005 | **PARTIALLY CLOSED** | P0 | Real WAITAOF works; a global, non-bypassable production construction gate does not exist. |
| P2-006 | **OPEN** | P0 | No immutable connector registry or complete startup audit exists. |
| P2-007 | **OPEN** | P1 | Recovery is concurrency-bounded but still O(N) in candidate/task/result memory. |
| P2-008 | **OPEN** | P0 | One candidate exception can still terminate a pass or the continuous loop. |
| P2-009 | **OPEN** | P0 | Authenticated operator resolution and ambiguity incidents are absent. |
| P2-010 | **OPEN** | P0 | Redaction, safe value types, and quarantine sanitization are not enforced. |
| P2-011 | **OPEN** | P1 | Typed validation still accepts incomplete or illegal history relationships. |
| P2-012 | **OPEN** | P1 | Size, archive, retention, and terminal lifecycle limits remain undefined or unenforced. |
| P2-013 | **PARTIALLY CLOSED** | P0 | One hidden-mutation regression and real-AOF tests were added; the full crash oracle is still incomplete. |
| P2-014 | **OPEN** | P1 | Read-back still has no enforced timeout or readback-sized capped lease. |
| P2-015 | **OPEN** | P1 | Runner and resolver still release in `finally` after unconfirmed resolution durability. |
| P2-016 | **OPEN** | P1 | The non-DB-15 cleanup override remains. |
| P2-017 | **OPEN** | P0 | Implementation still lacks a recorded, passed Section 11 prerequisite gate. |
| P2-018 | **PARTIALLY CLOSED** | P1 | Durability reporting is corrected, but scanner and crash-coverage claims remain overstated. |

## 3. Finding-by-finding reconciliation

### P2-001 — retry eligibility permits unsafe new external attempts

- **Classification / priority:** **OPEN / P0**.
- **Design requirement:** `docs/06-phase2-design.md` Sections 4.1 and 8.4;
  `docs/08-production-connector-design.md` Section 16. Only confirmed
  non-application permits a normal future attempt; permanent ambiguity requires
  an authenticated, request-bound risk decision.
- **Exact source evidence:** `UNRESOLVED_INTENT_STATUSES` still excludes both
  confirmed states and `PERMANENTLY_AMBIGUOUS`
  (`src/core/intents.py:42-44`). The Lua creation branch checks record addition,
  attempt numbering, and prepared version, but not the prior status for the step
  (`src/core/intents.py:311-327`). `create_intent` still accepts an optional raw
  `risk_acceptance_id` and always computes `max(attempt)+1`
  (`src/core/intents.py:493-512`, `:541`). The public runner accepts no verified
  risk-decision object (`src/core/intent_workflow.py:202-210`).
- **Regression-test evidence:** **No.** The closest Lua test rejects a second
  simultaneously unresolved intent (`tests/test_phase2_state_machine.py:328-372`);
  it does not try creation after `FIRED_CONFIRMED`, `FAILED_CONFIRMED`, or
  `PERMANENTLY_AMBIGUOUS`. The live DB-15 probe reproduced two confirmed calls
  with attempts `[1, 2]`, and a post-permanent call with attempt 2 and
  `risk_acceptance_id=None`.
- **Atomicity:** The required eligibility rule is absent from both Python and the
  atomic Lua CAS. Existing token/version/attempt checks are atomic but do not
  express the rule.
- **Concurrent/stale callers:** Stale token and stale version callers are fenced,
  but a serialized caller that re-reads the latest terminal record is accepted.
  Two racing callers may cause one stale failure, yet a later retry can still
  create the unsafe attempt.
- **Remaining consequence:** A normal call can repeat a mutation after success or
  after unresolved duplicate risk, without authenticated risk acceptance.
- **Required next task:** Add distinct normal and privileged creation operations.
  Put predecessor eligibility and one-time request-bound risk-grant validation in
  the creation Lua transaction; add zero-provider-call regressions for every
  predecessor state, forgery, expiry, reuse, and stale versions.

### P2-002 — intent creation can clear a global ambiguity fence

- **Classification / priority:** **OPEN / P0**.
- **Design requirement:** `docs/06-phase2-design.md` Section 8.4 and
  `docs/08-production-connector-design.md` Sections 7 and 16 require an
  execution-wide fence while any blocking intent remains.
- **Exact source evidence:** The typed model enforces at most one unresolved
  intent only per `step_id` (`src/core/intents.py:215-232`). The Lua scan likewise
  tracks unresolved status by step and does not treat permanent ambiguity as a
  global blocker (`src/core/intents.py:377-393`). New intent creation always sets
  top-level status to `PROCESSING` (`src/core/intents.py:545-551`).
- **Regression-test evidence:** **No.** No test seeds a paused permanent ambiguity
  on step A and attempts step B. The live probe produced
  `P2-002_REPRO PROCESSING PERMANENTLY_AMBIGUOUS 1`.
- **Atomicity:** No Python pre-check or Lua invariant enforces the global fence.
  The unsafe status change and new intent are themselves committed atomically.
- **Concurrent/stale callers:** Token/version CAS rejects a stale candidate, but a
  current or retried caller remains authorized. Different-step concurrency is
  serialized by version; serialization does not make the resulting action safe.
- **Remaining consequence:** Normal scheduling and provider dispatch can resume
  while an unrelated permanently ambiguous effect remains unresolved.
- **Required next task:** In the same creation CAS, reject normal creation when any
  ledger entry is `ABOUT_TO_FIRE`, `FIRED_UNCONFIRMED`, or
  `PERMANENTLY_AMBIGUOUS`; never change `PAUSED` implicitly. Keep explicit resume
  semantics as the separate P2-D01 design decision.

### P2-003 — the Phase 1 writer bypasses Phase 2 ledger invariants

- **Classification / priority:** **OPEN / P0**.
- **Design requirement:** `docs/06-phase2-design.md` Sections 4.1 and 6.1 require
  every intent change to use the Phase 2 transition/audit/retention CAS.
- **Exact source evidence:** Phase 1 still models `intent_ledger` as
  `Dict[str, Any]` (`src/core/storage.py:107-112`). Its Lua script checks only a
  live token and consecutive version before replacing the whole state
  (`src/core/storage.py:162-201`), and `save_state` invokes that script with a
  default 48-hour TTL (`src/core/storage.py:347-465`). No Phase 2 marker is
  inspected.
- **Regression-test evidence:** **No.** Phase 1 CAS tests cover token/version and
  corruption behavior, not protection of an already typed Phase 2 ledger. The
  live probe successfully changed an `ABOUT_TO_FIRE` execution to version 3,
  status `IDLE`, and `{}` ledger through `save_state`.
- **Atomicity:** The bypass is an atomic whole-state write, but it atomically
  enforces only Phase 1 rules. No Python pre-check detects a Phase 2 record.
- **Concurrent/stale callers:** Stale versions/tokens are safe. A current lock
  owner, including a scheduler or operator using the public base adapter, can
  erase history. A race merely decides which current-version write wins.
- **Remaining consequence:** Intent deletion, immutable-field changes, unpause,
  audit replacement, and shorter retention remain possible through a public
  repository write path.
- **Required next task:** Introduce an explicit Phase 2 state/write-mode marker
  and make the base Lua CAS reject any creation or modification of marked Phase 2
  state, or consolidate both paths into one invariant-aware script. Add raw-byte
  unchanged regressions for deletion, mutation, unpause, and TTL reduction.

### P2-004 — the mutation is not bound to an exact immutable request

- **Classification / priority:** **OPEN / P0**. The recommended design is now
  approved in `docs/08-production-connector-design.md`; the implementation gap
  is not superseded by that document.
- **Design requirement:** The immutable envelope, vault-backed safe binding,
  canonical JCS serialization, SHA-256/HMAC commitments, substitution checks,
  and typed dispatch/read-back contexts in connector-design Sections 4-8.
- **Exact source evidence:** `ExternalMutationConnector.mutate` still receives
  only `intent_id` and `client_timeout` (`src/core/intent_workflow.py:23-26`). The
  runner still accepts caller-provided `target` and `request_fingerprint`
  (`src/core/intent_workflow.py:202-210`) and passes neither request material nor
  correlation ID at dispatch (`src/core/intent_workflow.py:315-318`).
  `IntentRecord` has none of the approved locator/binding/version fields
  (`src/core/intents.py:152-174`), and recovery passes only `intent_id` to
  `read_back` (`src/core/intent_recovery.py:244-250`).
- **Regression-test evidence:** **No.** The mock connector implements the same
  ID-only interface (`tests/mock_connector.py:392-417`, `:501-517`). No test
  mutates caller input after preparation, recomputes canonical bytes, verifies
  a vault binding, or rejects request substitution.
- **Atomicity:** Request binding is absent from both the Python model and Lua
  immutable-field list. The existing preflight atomically checks token, TTL,
  state version, and status only (`src/core/intents.py:400-413`).
- **Concurrent/stale callers:** State staleness is detected, but mutable or
  reconstructed request material can drift independently of the state version.
- **Remaining consequence:** A production connector cannot prove that the exact
  intended request described by the ledger is the request it sends, and secure
  recovery context is undefined.
- **Required next task:** Implement `docs/08-production-connector-design.md`
  test-first, using the recommended create-once encrypted request vault and
  persisted safe binding. Do not put raw or merely encrypted regulated payloads
  in Redis.

### P2-005 — production durability and its startup gate

- **Classification / priority:** **PARTIALLY CLOSED / P0**.
- **Design requirement:** `docs/06-phase2-design.md` Section 6.2 requires Redis
  7.2+, AOF, same-connection `WAITAOF 1 0 <timeout-ms>`, local acknowledgment,
  and dispatch disablement on failure.
- **Exact source evidence:** `RealWaitAofDurabilityBarrier.validate_startup`
  checks Redis version, AOF configuration/runtime state, selected mode, and
  command metadata (`src/core/durability.py:103-179`). `confirm_durable` issues
  the exact command and returns true only for a valid response with local count
  at least one (`src/core/durability.py:181-206`). The runner validates before
  lease acquisition (`src/core/intent_workflow.py:147-167`, `:213`) and uses one
  pinned client for CAS then barrier (`src/core/intent_workflow.py:228-247`,
  `:349-369`; `src/core/intents.py:446-451`). Compose pins Redis 7.2.5 and
  `redis/phase2.conf` enables AOF with `appendfsync everysec`.
- **Regression-test evidence:** **Yes for the barrier and default runner path.**
  Scripted unit tests cover accepted/zero/malformed/error/unsupported responses
  (`tests/test_phase2_durability.py:82-201`). Runner tests prove default fake and
  rejected startup validation cause no intent/call
  (`tests/test_phase2_runner.py:292-350`). Real integration proves CAS/barrier
  client IDs and order, permitted dispatch, failed-barrier no-call, and restart
  survival (`tests/test_phase2_waitaof_integration.py:104-277`).
- **Atomicity:** CAS and WAITAOF are intentionally sequential, not one atomic
  command; ordering is enforced by the pinned connection. Capability validation
  is a Python pre-check. The later barrier is the fail-closed runtime check.
- **Concurrent/stale callers:** The post-barrier Lua preflight atomically fences
  stale token/version/status callers. A server configuration change after startup
  is not continuously prevented, but an actual WAITAOF error/zero acknowledgment
  blocks that dispatch. The Redis/provider scheduling gap remains.
- **Remaining consequence:** The runner has a public
  `allow_test_barrier=True` option whose first branch skips all durability
  validation (`src/core/intent_workflow.py:118-129`, `:147-151`), and tests use it
  (`tests/test_phase2_runner.py:99-121`). Repository-wide construction search
  found no production bootstrap or registry—only test constructors—so the claim
  that *all* production construction paths reject fake durability is not proved.
  A caller can deliberately select the bypass; no environment, factory, or
  service identity distinguishes a test process.
- **Required next task:** Put the test bypass behind test-only composition that
  cannot be imported or selected by production bootstrap. Add an all-or-nothing
  global startup gate, integrated with the connector registry, and validate real
  barriers used by recovery as well as dispatch. Preserve the existing
  same-connection implementation and tests.

### P2-006 — connector declarations are incomplete and not startup-validated

- **Classification / priority:** **OPEN / P0**.
- **Design requirement:** `docs/06-phase2-design.md` Sections 5, 8.3, and 11;
  `docs/08-production-connector-design.md` Section 13.
- **Exact source evidence:** `ConnectorPolicy` contains two arbitrary non-empty,
  disjoint string sets (`src/core/intent_workflow.py:33-88`) that are independent
  of `connector_name`. Recovery accepts a mutable mapping
  (`src/core/intent_recovery.py:46-70`), discovers capability with nested
  `getattr` during live work (`src/core/intent_recovery.py:224-228`), and detects
  a missing connector only after an intent is selected (`:173-181`). No
  production registry/bootstrap module exists.
- **Regression-test evidence:** **No.** Tests exercise valid mock enums and the
  two default response strings, but do not reject duplicate/unversioned names,
  method/capability mismatch, incomplete tables, illegal evidence, schema drift,
  fake barriers, or historical-version loss at global startup.
- **Atomicity:** Registry validation and descriptor binding are absent. Response
  classification is a Python string membership check after the provider call;
  no descriptor digest is persisted atomically with the intent.
- **Concurrent/stale callers:** Redis token/version CAS protects the state write,
  but connector configuration can drift independently, so stale configuration
  is not detected.
- **Remaining consequence:** Misconfiguration or an unsafe allowlist can reach
  live dispatch/recovery and can persist a wrong definitive classification.
- **Required next task:** Implement the immutable, versioned, all-or-nothing
  registry and every startup check in connector-design Section 13; persist and
  preflight its descriptor digest.

### P2-007 — `scan_once` is not memory-bounded

- **Classification / priority:** **OPEN / P1**.
- **Design requirement:** `docs/06-phase2-design.md` Sections 8.1 and 11 require
  bounded candidate processing that can meet the recovery SLO.
- **Exact source evidence:** `scan_once` appends every eligible pair to
  `candidates`, creates one awaitable per candidate for `asyncio.gather`, and
  retains all results (`src/core/intent_recovery.py:97-122`). The semaphore limits
  active bodies only.
- **Regression-test evidence:** **No.** The only scanner test has one eligible
  execution (`tests/test_phase2_recovery.py:266-279`); no large iterator measures
  outstanding or retained objects.
- **Atomicity:** Not an atomicity issue; allocation is entirely in Python.
- **Concurrent/stale callers:** `recover_intent` correctly re-reads after lease
  acquisition (`src/core/intent_recovery.py:183-198`), so stale discovery is
  fenced. That does not bound discovery memory under a large backlog.
- **Remaining consequence:** Memory remains O(total eligible intents) and can be
  exhausted during the incident in which recovery is most needed.
- **Required next task:** Stream scan pages into a fixed worker pool/bounded task
  set and a bounded result/metric sink. Add a large synthetic scan regression.

### P2-008 — one bad candidate can terminate continuous recovery

- **Classification / priority:** **OPEN / P0**.
- **Design requirement:** `docs/06-phase2-design.md` Section 8 requires continuous
  recovery, corruption handling, alerting, and systemic circuit breaking.
- **Exact source evidence:** Candidate `get_execution` calls have no isolation,
  `asyncio.gather` uses default exception propagation, and `run_forever` has no
  pass guard (`src/core/intent_recovery.py:100-146`). Missing configuration raises
  (`:173-181`), and `read_back` re-raises every `BaseException` (`:244-248`). The
  only hook is for a successfully completed slow pass (`:57`, `:139-142`).
- **Regression-test evidence:** **No.** No corrupt/failing candidate is placed
  beside a recoverable candidate, and no loop-survival, breaker, or in-flight
  shutdown test exists.
- **Atomicity:** Per-intent CAS is atomic if reached; fault isolation and breaker
  state are absent Python service controls.
- **Concurrent/stale callers:** Claim/re-read fencing is safe, but an unrelated
  candidate fault prevents other candidates from reaching it.
- **Remaining consequence:** One corruption, outage, or malformed connector can
  halt recovery globally without the required alert path.
- **Required next task:** Add typed per-candidate outcomes, exception isolation,
  a top-level pass guard, structured alerts, and a tested systemic circuit
  breaker. Operational failure must remain unknown, never `NOT_APPLIED`.

### P2-009 — operator resolution, authentication, and ambiguity alerts are absent

- **Classification / priority:** **OPEN / P0**.
- **Design requirement:** `docs/06-phase2-design.md` Section 8.4 and
  connector-design Section 16 require durable incidents and authenticated,
  ticket/evidence-bound operator actions.
- **Exact source evidence:** Recovery exposes only `recovery_lag_alert`
  (`src/core/intent_recovery.py:46-70`, `:139-142`). `transition_intent` accepts
  arbitrary non-empty actor/reason strings and optional evidence
  (`src/core/intents.py:565-607`) and permits permanent ambiguity to confirmed
  states through the normal CAS.
- **Regression-test evidence:** **No.** The state-machine test passes the literal
  string `operator:alice` and embeds a ticket in a reason, with no authentication
  assertion (`tests/test_phase2_state_machine.py:168-197`). No warning/critical
  delivery or deduplication test exists.
- **Atomicity:** Token/version/legal-edge checks are atomic, but authentication,
  ticket binding, authorization, and incident delivery are absent. Any current
  lock owner can supply an operator-looking string.
- **Concurrent/stale callers:** Stale token/version callers are fenced. A current
  unauthorized caller is not, because authorization is not part of the CAS or a
  verified grant.
- **Remaining consequence:** Ambiguity may remain invisible, and a current lock
  holder can impersonate an operator and resolve it.
- **Required next task:** Build an authenticated operator facade and one-time
  decision grant, then a durable/retryable incident outbox keyed by transition
  identity. Alert delivery remains non-atomic with Redis and must be documented
  as such.

### P2-010 — secret and PII redaction is not an enforced boundary

- **Classification / priority:** **OPEN / P0**.
- **Design requirement:** `docs/06-phase2-design.md` Section 3 and
  connector-design Section 12.
- **Exact source evidence:** Persisted strings have mostly only `min_length=1`
  and no redacted types or maximums (`src/core/intents.py:105-174`). Runner
  persists connector-supplied external reference, evidence values, exception
  type, call ID, actor, and reason (`src/core/intent_workflow.py:329-360`).
  Quarantine copies the complete raw state into another Redis key
  (`src/core/storage.py:605-649`).
- **Regression-test evidence:** **No.** The integrated hidden-mutation test proves
  only that the test oracle's `mutation_applied` flag is absent from one result
  and Redis record (`tests/test_phase2_runner.py:197-256`). It is not a
  secret/PII canary test and does not cover poison records, logs, exceptions,
  metrics, traces, alerts, or oversized values.
- **Atomicity:** Unsafe values can be accepted in Python and committed atomically;
  Lua validates neither redaction nor bounded size.
- **Concurrent/stale callers:** Fencing does not mitigate data disclosure. Any
  accepted current caller/connector can persist unsafe content.
- **Remaining consequence:** Credentials, payment data, PII, or oversized fields
  can enter state, AOF, backups, quarantine, and future telemetry.
- **Required next task:** Implement connector-design safe value objects,
  allowlist-based field classification/redaction, strict byte limits, safe
  exceptions/telemetry, and sanitized or separately encrypted quarantine; add
  cross-sink canary tests.

### P2-011 — typed validation accepts corrupt audit/history relationships

- **Classification / priority:** **OPEN / P1**.
- **Design requirement:** `docs/06-phase2-design.md` Sections 3 and 4 require a
  contiguous legal immutable history and coherent reconciliation bookkeeping.
- **Exact source evidence:** Model validation checks only
  `reconcile_after >= prepared_at`, the last transition's target, and the
  presence of reconciliation for `FIRED_UNCONFIRMED`
  (`src/core/intents.py:197-207`). Lua validates the newly appended edge but does
  not revalidate the complete prior transition chain or timing relationships
  (`src/core/intents.py:328-375`).
- **Regression-test evidence:** **No.** State-machine tests exercise legal API
  calls and representative rejected edges; no raw record injects a broken first
  edge, discontinuity, illegal middle edge, time reversal, formula mismatch, or
  reconciliation inconsistency and then asserts quarantine/no connector call.
- **Atomicity:** Append-only preservation and the new edge are atomic. Full
  history integrity is only partially checked in Python and not mirrored in Lua.
- **Concurrent/stale callers:** Token/version checks prevent stale mutation but do
  not detect an already corrupt record that passes the weak typed validator.
- **Remaining consequence:** Contradictory forensic history can pass the normal
  read path and influence recovery/operator decisions.
- **Required next task:** Add full frozen-model cross-field/history validators and
  mirror race-sensitive invariants in Lua; reject and sanitize/quarantine rather
  than repair.

### P2-012 — payload growth and retention lifecycle are not bounded

- **Classification / priority:** **OPEN / P1**.
- **Design requirement:** `docs/06-phase2-design.md` Sections 3, 8.1, and 9;
  connector-design Sections 4, 6, and 12 define bounded fields, material
  retention, archive, and tombstones.
- **Exact source evidence:** No maximum ledger, transition, persisted-string, or
  serialized-state sizes exist (`src/core/intents.py:105-232`). Every transition
  serializes and rewrites the full state (`src/core/intents.py:676-697`). Lua
  applies the 31-day minimum only when `ABOUT_TO_FIRE` or `FIRED_UNCONFIRMED`
  exists (`src/core/intents.py:377-395`), not solely for
  `PERMANENTLY_AMBIGUOUS`. The Phase 1 bypass retains a 48-hour default. No
  archive/incident lifecycle exists.
- **Regression-test evidence:** **No.** Phase 2 tests do not assert field/state
  size caps, TTL throughout all blocking states, durable archive handoff, expiry,
  tombstones, or sink-unavailable behavior.
- **Atomicity:** The configured TTL and whole payload are set atomically, but the
  lifecycle policy and limits are absent. Some minimum retention is Lua-enforced
  only for the two unresolved statuses.
- **Concurrent/stale callers:** Version fencing prevents competing rewrites but
  does not prevent unbounded growth or a current base-writer TTL reduction.
- **Remaining consequence:** Large histories increase CAS/scan/quarantine cost;
  permanent incidents can expire without a repository-defined durable closure.
- **Required next task:** Enforce byte/entry limits and all blocking-state TTL
  rules in the atomic write path, then implement durable archive/incident
  acknowledgement, tombstones, and documented terminal expiry.

### P2-013 — crash-boundary acceptance evidence is incomplete

- **Classification / priority:** **PARTIALLY CLOSED / P0 acceptance gate**.
- **Design requirement:** `docs/06-phase2-design.md` Sections 7 and 11 and
  connector-design Section 19 require every permitted hidden truth, caller
  evidence, persisted state, restart/read-back behavior, and unchanged mutation
  count.
- **Exact source evidence:** Runner `DURING_INTENT_CAS` is immediately before the
  CAS (`src/core/intent_workflow.py:227-229`) and `DURING_RESOLUTION_CAS` is
  immediately before that CAS (`:348-350`). The durability “during” checkpoint
  is also before `_confirm_barrier` (`:363-369`). Recovery uses the same
  pre-command placement (`src/core/intent_recovery.py:200-203`, `:332-357`). Thus
  those names do not create uncertain reply-loss outcomes.
- **Regression-test evidence:** **Partial.** The 16-case runner matrix asserts a
  permitted typed status and only a one-way caller-evidence condition
  (`tests/test_phase2_runner.py:124-162`); it does not assert the full oracle for
  every row. General runner/recovery crash tests use
  `FakeDurabilityBarrier` (`tests/test_phase2_runner.py:99-121`;
  `tests/test_phase2_recovery.py:113-125`). `SimulatedProcessCrash` is a
  `BaseException` in the same process, so Python `finally` still runs; it is not
  an actual process exit. The new
  `test_runner_applied_mid_transmission_drop_stays_unconfirmed_without_replay`
  does prove hidden applied truth, caller ambiguity, typed/raw persistence, and
  one unchanged call for that one case (`tests/test_phase2_runner.py:197-256`).
  The real-AOF restart test proves a normally confirmed intent survives restart
  with one call (`tests/test_phase2_waitaof_integration.py:220-277`), not all
  crash outcomes or runner-to-recovery restart behavior.
- **Atomicity:** This is an evidence gap, not a new atomicity mechanism. The
  existing Lua CAS and preflight remain atomic; test hooks do not exercise reply
  loss on both sides of those commands.
- **Concurrent/stale callers:** The dedicated late-worker test proves one stale
  token/version case (`tests/test_phase2_recovery.py:282-314`). It does not cover
  every concurrent/crash combination.
- **Remaining consequence:** The report's “all 22” names demonstrate checkpoint
  reachability and selected states, not the exhaustive Section 7 oracle. Redis
  reply loss, uncertain CAS outcome, cancellation/finally differences, ambiguous
  restart reconciliation, and every hidden true/false branch remain incomplete.
- **Required next task:** Build the full crash matrix without weakening existing
  assertions: before/after/reply-loss hooks for each CAS/barrier, genuine child
  process and controlled connection loss, every allowed provider truth, raw and
  typed state, caller evidence, restart/recovery, read-back count, and unchanged
  mutation count.

### P2-014 — read-back has no enforced timeout or correctly sized capped lease

- **Classification / priority:** **OPEN / P1**.
- **Design requirement:** `docs/06-phase2-design.md` Section 8.2 and
  connector-design Sections 8.1 and 11.
- **Exact source evidence:** Recovery acquires the mutation policy's fixed
  `lock_ttl_seconds` (`src/core/intent_recovery.py:148-160`) and directly awaits
  `read_back(intent_id=...)` with no timeout (`:244-248`). `ConnectorPolicy` has
  no read-back timeout or recovery lease-cap field
  (`src/core/intent_workflow.py:33-53`).
- **Regression-test evidence:** **No.** No test hangs or cancels read-back beyond
  its deadline/lease and proves the next resolver can continue.
- **Atomicity:** The timeout/lease sizing would be Python service control; it is
  absent. A late persistence CAS is still atomically token/version fenced.
- **Concurrent/stale callers:** A hung read-back may outlive its lease and overlap
  another read-only query. Its later write should be fenced, preserving state
  safety, but liveness and the five-minute SLO are not safe.
- **Remaining consequence:** A connector hang can stall a pass, cause overlapping
  queries, and defer every other recovery candidate.
- **Required next task:** Add a registry-validated finite read-back timeout,
  timeout-plus-buffer capped lease, enforced `asyncio.timeout`, cancellation
  handling, and operationally unknown—not negative—classification.

### P2-015 — locks are released when resolution durability is unconfirmed

- **Classification / priority:** **OPEN / P1**.
- **Design requirement:** `docs/06-phase2-design.md` Section 5 requires release
  after durable resolution; failure should alert and leave bounded expiry or a
  specifically designed handoff.
- **Exact source evidence:** Runner and recovery release unconditionally in
  `finally` (`src/core/intent_workflow.py:380-381`;
  `src/core/intent_recovery.py:314-315`). A resolution CAS may therefore succeed
  in Redis memory, its real barrier may fail, and cleanup still unlocks it. A
  release exception can replace the primary exception.
- **Regression-test evidence:** **No.** Existing barrier-failure tests cover the
  initial pre-dispatch barrier (`tests/test_phase2_runner.py:258-289` and
  `tests/test_phase2_waitaof_integration.py:175-217`), not a post-provider
  resolution barrier or a simultaneous release failure.
- **Atomicity:** Release is token-checked atomically, but the decision to release
  is an unconditional Python `finally`. CAS and WAITAOF remain sequential.
- **Concurrent/stale callers:** Token checking prevents deletion of a successor's
  lock. When the original token is current, early release lets another worker
  observe a resolution that was not confirmed to local AOF.
- **Remaining consequence:** Recovery can race sooner against unconfirmed durable
  state, and cleanup can obscure the primary durability failure. Conservative
  recovery limits harm after loss but does not implement the documented order.
- **Required next task:** Track resolution-barrier success, implement the explicit
  expiry/alert policy for failure, and preserve primary plus cleanup exceptions.
  Add no-replay and recovery regressions.

### P2-016 — test cleanup can target a non-dedicated Redis database

- **Classification / priority:** **OPEN / P1**.
- **Design requirement:** Tests may delete only `aep:*` in dedicated DB 15 and
  must never call `FLUSHALL`.
- **Exact source evidence:** Namespace-scoped scanning/deletion is correct
  (`tests/conftest.py:129-138`), and no executable `FLUSHALL` call exists.
  However, `AEP_TEST_ALLOW_FLUSHALL=1` still permits any real DB
  (`tests/conftest.py:105-126`), despite the misleading name.
- **Regression-test evidence:** **No.** No test proves a non-15 URL is rejected
  even with the override or that unrelated DB-15 keys survive.
- **Atomicity:** Not a state-CAS issue. Cleanup deletes batches in Python after a
  startup DB check.
- **Concurrent/stale callers:** A shared non-15 database remains unsafe against
  concurrent production-like `aep:*` keys when the override is set.
- **Remaining consequence:** An opted-in test can delete scoped but real AEP keys
  outside the dedicated database.
- **Required next task:** Remove the override and unconditionally require DB 15;
  rename/remove the variable and add cleanup-scope regressions.

### P2-017 — implementation began before design prerequisites were met

- **Classification / priority:** **OPEN / P0 release gate**.
- **Design requirement:** `docs/06-phase2-design.md` Section 11 says implementation
  must not begin before reviewer agreement on all seven prerequisites.
- **Exact source evidence:** The design still says “Proposed for review; no
  implementation exists yet” (`docs/06-phase2-design.md:3`), while the report
  lists implemented modules (`phase2_implementation_report.md:8-75`). Its current
  checklist still admits missing connector registry, scheduler/operator path,
  SLO/load proof, and telemetry (`phase2_implementation_report.md:311-336`). No
  signed or recorded Section 11 approval artifact or executable release gate
  exists.
- **Regression-test evidence:** **No.** Passing tests do not prove governance
  approval or prevent production composition when a checklist is incomplete.
- **Atomicity:** Not an atomicity issue.
- **Concurrent/stale callers:** Not a caller-race issue; it is a release/governance
  gate.
- **Remaining consequence:** Prototype completeness and a green suite can be
  mistaken for an approved production design.
- **Required next task:** Keep production dispatch explicitly disabled, complete
  all P0 work, record reviewer approval and deployment evidence, and make CI or
  release composition require the signed Section 11 checklist.

### P2-018 — implementation-report coverage claims remain too strong

- **Classification / priority:** **PARTIALLY CLOSED / P1**.
- **Design requirement:** Evidence-backed Section 11 wording must preserve the
  bounded guarantee.
- **Exact source evidence:** The report now accurately describes real WAITAOF,
  same-connection integration, and residual local-only durability
  (`phase2_implementation_report.md:338-478`). It still describes scanner
  discovery as bounded without disclosing O(N) retained candidates/tasks/results
  (`phase2_implementation_report.md:48-56`, `:319`) and marks every crash point
  **Met** (`:320`) despite P2-013. Its “explicit response-class declarations”
  summary (`:40-41`) is only the two unbound string sets, not the approved
  connector contract.
- **Regression-test evidence:** **No documentation gate.** The 218 tests pass but
  do not link every “Met” claim to the required dimensions or fail release on an
  incomplete acceptance row.
- **Atomicity:** Not an atomicity issue.
- **Concurrent/stale callers:** Not directly applicable; the risk is reviewer
  interpretation of evidence.
- **Remaining consequence:** A reader may infer memory-bounded recovery and
  exhaustive crash proof from correct test counts.
- **Required next task:** Correct the implementation report to say
  concurrency-bounded/O(N) memory and crash coverage partial; distinguish mock
  allowlists from the connector registry, and link each gate row to executable
  tests/deployment probes and this current gap register.

## 4. Reconciliation of the reported contradictions

### 4.1 “All 22 crash boundaries passed” versus incomplete evidence

Both statements describe different things. Twenty-two parameter values do pass
and every named checkpoint can be armed. The acceptance criterion is stronger:
the checkpoint must model the actual uncertain boundary and assert all permitted
hidden truth, caller evidence, durable state, restart behavior, and no replay.
Several “during” hooks execute before their command, general durability is fake,
and same-process `BaseException` still runs `finally`. The integrated applied
connection-drop regression materially improves one case, while the real Redis
restart test proves normal confirmed-state AOF survival. Neither makes the
entire Section 7 matrix complete. The report's row must therefore be partial,
not **Met**.

### 4.2 “Bounded recovery” versus unbounded memory

`asyncio.Semaphore(max_concurrency)` genuinely bounds concurrent recovery bodies.
It does not bound the `candidates` list, generated awaitables, or result list.
`SCAN COUNT 500` is a Redis iteration hint, not a Python pass-memory limit.
Recovery is concurrency-bounded and O(N)-memory; the five-minute SLO and backlog
survivability remain unproved.

### 4.3 P2-005 after real WAITAOF

The old stub, unsupported Redis, disabled AOF, missing command, malformed reply,
zero acknowledgment, same-connection, and restart-survival portions are now
implemented and tested. P2-005 is therefore not `OPEN` in its original entirety.
It is not fully closed because `allow_test_barrier=True` bypasses validation and
the repository has no production registry/bootstrap through which every
construction is forced. This is a composition/global-gate residual, not a defect
in the exact WAITAOF command implementation.

### 4.4 Redis durability versus connector/global startup

The checked-in Redis deployment and runner-level real barrier can be correct
while the production service gate remains absent. `docs/08-production-connector-design.md`
requires one immutable registry that validates request schemas, classification,
read-back capability, settlements, redaction, vault/KMS, old descriptor support,
and the real barrier before scheduling traffic. None of that registry exists.

### 4.5 Default fake rejection versus every production construction path

The default runner path rejects `test_only=True`, and its regression proves zero
intent/call. There is no repository production constructor to audit, however,
and the same public class accepts a boolean that skips all checks. Consequently,
the default is proven; universal production enforcement is not.

### 4.6 Current reproducibility of P2-001, P2-002, and P2-003

All three remain dynamically reproducible against Redis 7.2.5/AOF/DB 15. The
probe used the real barrier for runner dispatches and cleaned only `aep:*` in a
`finally` block. Exact output:

```text
P2-001_CONFIRMED_REPRO FIRED_CONFIRMED FIRED_CONFIRMED 2 [1, 2]
P2-001_PERMANENT_REPRO FIRED_CONFIRMED 1 2 None
P2-002_REPRO PROCESSING PERMANENTLY_AMBIGUOUS 1
P2-003_REPRO ABOUT_TO_FIRE IDLE 3 {}
```

## 5. Design decisions and non-goals

No P2-001 through P2-018 finding is reclassified as a design decision or
non-goal.

- **P2-D01 remains a design decision:** resolving the last ambiguous intent does
  not automatically unpause the execution. `transition_intent` preserves the
  current top-level status for a confirmed target (`src/core/intents.py:636-649`),
  so a previously paused execution stays paused. This is safe but lacks a defined
  authenticated resume CAS.
- **P2-D02 is resolved at design level only:** connector-design Section 6 selects
  an AEP-owned create-once encrypted request vault with an opaque Redis reference.
  Raw request material must not be added to the ledger. Implementation remains
  P2-004/P2-010 work.

Accepted non-goals remain: no exactly-once provider effects, no atomic Redis/
provider transaction, no HA/consensus or split-brain prevention, no guaranteed
duplicate prevention after an authenticated risk override, no provider recall,
no authoritative negative inference for positive-only APIs, no atomic alert
delivery, no recovery from catastrophic loss of the only Redis storage, and no
secondary recovery index.

## 6. Verification commands and exact results

All Redis-backed commands used `redis://127.0.0.1:6381/15`. No command invoked
`FLUSHALL`; cleanup scanned and deleted only `aep:*`. DB 15 contained zero keys
after verification.

### 6.1 Environment and configuration

```powershell
docker compose -f compose.phase2.yml config --quiet
redis-cli -h 127.0.0.1 -p 6381 -n 15 PING
redis-cli -h 127.0.0.1 -p 6381 -n 15 INFO server | Select-String '^redis_version:'
redis-cli -h 127.0.0.1 -p 6381 -n 15 CONFIG GET appendonly appendfsync
redis-cli -h 127.0.0.1 -p 6381 -n 15 COMMAND INFO WAITAOF | Select-Object -First 4
redis-cli -h 127.0.0.1 -p 6381 -n 15 --scan --pattern 'aep:*'
redis-cli -h 127.0.0.1 -p 6381 -n 15 DBSIZE
```

Result: exit 0; `PONG`; `redis_version:7.2.5`; `appendonly yes`;
`appendfsync everysec`; WAITAOF metadata returned; no `aep:*` output; `DBSIZE` was
`0`.

### 6.2 `py_compile`

```powershell
$env:PYTHONPYCACHEPREFIX='C:\Users\DELL\AppData\Local\Temp\aep-post-waitaof-gate-pycompile'; $compileFiles = @(rg --files src tests -g '*.py'); py -3 -m py_compile $compileFiles
```

Result: exit 0 with no output.

### 6.3 Focused Phase 2 suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_mock_connector.py tests/test_phase2_durability.py tests/test_phase2_state_machine.py tests/test_phase2_runner.py tests/test_phase2_recovery.py -p no:cacheprovider -q
```

Result: `163 passed in 2.96s`.

### 6.4 Complete suite with Redis integration enabled

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests -p no:cacheprovider -q
```

Result: `218 passed in 22.78s`.

### 6.5 Standalone Redis 7.2 AOF integration suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_waitaof_integration.py -p no:cacheprovider -q
```

Result: `4 passed in 7.78s`.

Every pytest invocation emitted the existing `pytest-asyncio` deprecation
warning that `asyncio_default_fixture_loop_scope` is unset. It did not alter the
results.

### 6.6 DB-15-only reproduction probe

The probe constructed current library objects directly, verified `CLIENT INFO`
reported DB 15, used `RealWaitAofDurabilityBarrier` for all runner dispatches,
and performed namespace-only cleanup before and in `finally`. Its exact logical
sequence was:

1. seed a Phase 1 execution under a live lock;
2. run the same step twice to confirmed success;
3. create and transition a separate step through `ABOUT_TO_FIRE` →
   `FIRED_UNCONFIRMED` → `PERMANENTLY_AMBIGUOUS`, then invoke the same step through
   the normal real-barrier runner;
4. repeat permanent ambiguity and invoke a different step;
5. create an `ABOUT_TO_FIRE` intent, then use `RedisStorageAdapter.save_state`
   with the current token/version to submit an empty ledger and `IDLE` status;
6. scan/delete only `aep:*` and close the DB-15 client.

Exact command:

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $code = @'
import asyncio
import uuid
from redis.asyncio import Redis
from src.core.durability import RealWaitAofDurabilityBarrier
from src.core.intent_workflow import ConnectorPolicy, WriteAheadRunner
from src.core.intents import IntentLedgerStore, IntentStatus
from src.core.locks import DistributedLockManager
from src.core.storage import AEPExecutionState, AEPStatus, RedisStorageAdapter
from tests.mock_connector import MockConnectorHarness, ResponseMode

URL = 'redis://127.0.0.1:6381/15'
POLICY = ConnectorPolicy(client_timeout_seconds=0.01, settlement_lag_seconds=0, buffer_margin_seconds=15, lock_ttl_seconds=30, durability_timeout_ms=2000, lease_acquire_attempts=1)

async def cleanup(redis):
    batch=[]
    async for key in redis.scan_iter(match='aep:*', count=500):
        batch.append(key)
        if len(batch) == 500:
            await redis.delete(*batch); batch.clear()
    if batch:
        await redis.delete(*batch)

async def seed(redis):
    eid=str(uuid.uuid4()); locks=DistributedLockManager(redis); storage=RedisStorageAdapter(redis)
    token=await locks.acquire_lock(eid, ttl_seconds=60); assert token
    await storage.save_state(AEPExecutionState(execution_id=eid, status=AEPStatus.IDLE), expected_version=0, lock_token=token, ttl_seconds=3600)
    assert await locks.release_lock(eid, token)
    return eid

async def make_permanent(redis, eid, step='step-a'):
    store=IntentLedgerStore(redis); locks=DistributedLockManager(redis)
    token=await locks.acquire_lock(eid, ttl_seconds=60); assert token
    async with store.pinned_connection() as conn:
        intent=await store.create_intent(execution_id=eid, expected_version=1, lock_token=token, step_id=step, connector='mock.non-idempotent.v1/mutate', target='redacted-target', request_fingerprint='e'*64, client_timeout_seconds=0.01, settlement_lag_seconds=0, buffer_margin_seconds=15, actor='probe', connection=conn)
        unconfirmed=await store.transition_intent(execution_id=eid, intent_id=intent.intent_id, expected_version=2, lock_token=token, new_status=IntentStatus.FIRED_UNCONFIRMED, actor='probe', reason='ambiguous', connection=conn)
        await store.transition_intent(execution_id=eid, intent_id=intent.intent_id, expected_version=3, lock_token=token, new_status=IntentStatus.PERMANENTLY_AMBIGUOUS, actor='probe', reason='exhausted', connection=conn)
    assert await locks.release_lock(eid, token)
    return intent.intent_id

async def runner(redis, harness):
    return WriteAheadRunner(store=IntentLedgerStore(redis), lock_manager=DistributedLockManager(redis), connector=harness.connector, barrier=RealWaitAofDurabilityBarrier(), policy=POLICY, connector_name='mock.non-idempotent.v1/mutate')

async def main():
    redis=Redis.from_url(URL, decode_responses=True)
    try:
        assert int((await redis.client_info())['db']) == 15
        await cleanup(redis)

        eid=await seed(redis)
        h=MockConnectorHarness(); h.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS); h.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
        r=await runner(redis,h)
        first=await r.execute(execution_id=eid, step_id='step-a', target='redacted-target', request_fingerprint='a'*64)
        second=await r.execute(execution_id=eid, step_id='step-a', target='redacted-target', request_fingerprint='a'*64)
        s=await IntentLedgerStore(redis).get_execution(eid)
        print('P2-001_CONFIRMED_REPRO', first.status.value, second.status.value, len(h.oracle.calls), sorted(i.attempt for i in s.intent_ledger.values()))

        eid=await seed(redis); old=await make_permanent(redis,eid)
        h=MockConnectorHarness(); h.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
        result=await (await runner(redis,h)).execute(execution_id=eid, step_id='step-a', target='redacted-target', request_fingerprint='b'*64)
        s=await IntentLedgerStore(redis).get_execution(eid)
        new=[i for i in s.intent_ledger.values() if i.intent_id != old][0]
        print('P2-001_PERMANENT_REPRO', result.status.value, len(h.oracle.calls), new.attempt, new.risk_acceptance_id)

        eid=await seed(redis); old=await make_permanent(redis,eid)
        h=MockConnectorHarness(); h.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
        await (await runner(redis,h)).execute(execution_id=eid, step_id='step-b', target='redacted-target', request_fingerprint='c'*64)
        s=await IntentLedgerStore(redis).get_execution(eid)
        print('P2-002_REPRO', s.status.value, s.intent_ledger[old].status.value, len(h.oracle.calls))

        eid=await seed(redis); store=IntentLedgerStore(redis); locks=DistributedLockManager(redis); storage=RedisStorageAdapter(redis)
        token=await locks.acquire_lock(eid, ttl_seconds=60); assert token
        intent=await store.create_intent(execution_id=eid, expected_version=1, lock_token=token, step_id='step-a', connector='mock.non-idempotent.v1/mutate', target='redacted-target', request_fingerprint='d'*64, client_timeout_seconds=0.01, settlement_lag_seconds=0, buffer_margin_seconds=15, actor='probe')
        current=await store.get_execution(eid)
        bypass=AEPExecutionState.model_validate({**current.model_dump(), 'version': current.version+1, 'status': AEPStatus.IDLE, 'intent_ledger': {}})
        await storage.save_state(bypass, expected_version=current.version, lock_token=token, ttl_seconds=172800)
        raw=await storage.get_state(eid)
        print('P2-003_REPRO', intent.status.value, raw.status.value, raw.version, raw.intent_ledger)
        assert await locks.release_lock(eid, token)
    finally:
        await cleanup(redis)
        await redis.aclose()

asyncio.run(main())
'@; py -3 -c $code
~~~

The four exact output lines are recorded in Section 4.6. The probe created no
repository file and left DB 15 empty.

## 7. Current Section 11 acceptance table

| Section 11 criterion | Current status | Reconciled evidence |
|---|---|---|
| Every connector has response-classification and reconciliation-capability declarations | **UNMET** | Mock string sets/capability exist; the approved production descriptor, full tables, registry, and startup audit do not. P2-004/P2-006. |
| Redis deployment supports an approved local durability barrier | **MET for the verified checked-in DB-15 environment; production deployment remains conditional** | Redis 7.2.5, AOF, WAITAOF capability, exact command behavior, failure handling, and restart survival are verified. A production deployment must pass the same probe. |
| Same-connection CAS plus WAITAOF is guaranteed by client design | **MET** | Pinned client is passed to CAS then exact WAITAOF; matching server client IDs are asserted for intent and resolution. |
| Scheduler, runner, resolver, and operator paths enforce the transition table | **UNMET** | Intended Phase 2 CAS edges are strong, but P2-001/P2-002/P2-003 are reproducible; no production scheduler or authenticated operator workflow exists. |
| Scanner and retention satisfy the recovery SLO | **UNMET** | Concurrency is bounded, memory is O(N); candidate isolation, load/SLO proof, full retention/archive lifecycle, and deployed alerting are absent. P2-007/P2-008/P2-012/P2-014. |
| Every Section 7 crash point has adversarial tests | **PARTIALLY MET, NOT ACCEPTED** | Twenty-two names pass; one hidden applied regression and four real-AOF tests are strong. The exhaustive oracle and uncertain command/reply-loss boundaries remain incomplete. P2-013. |
| Documentation and telemetry use detectable ambiguity plus fail-closed, never exactly once | **PARTIALLY MET** | Governing wording is bounded and durability limitations are honest. The report still overstates scanner/crash coverage, and production telemetry does not exist. P2-018. |

The Section 11 gate as a whole is **not passed**.

## 8. Ordered implementation plan

1. **P0 mutation authorization:** fix P2-001, P2-002, and P2-003 in atomic Lua
   write paths with test-first regressions. Keep dispatch disabled.
2. **P0 connector boundary:** implement the immutable request envelope, safe vault
   binding, canonical fingerprint, substitution checks, evidence unions, and
   version compatibility from `docs/08-production-connector-design.md` (P2-004,
   P2-010).
3. **P0 global startup:** implement the immutable connector registry and
   all-or-nothing production bootstrap; make fake/test-barrier selection
   unreachable from production composition (P2-005 residual, P2-006).
4. **P0 ambiguity operations:** add authenticated risk acceptance, manual
   resolution, warning/critical incidents, durable retry/deduplication, and
   systemic recovery fault isolation (P2-008, P2-009).
5. **P0 acceptance proof:** expand the crash matrix across real CAS/WAITAOF reply
   loss, child-process termination, hidden truths, restart/reconciliation, and no
   replay (P2-013).
6. **P1 recovery and lifecycle:** stream bounded scanner work, enforce read-back
   timeout/capped lease, validate full history, add size/retention/archive policy,
   and correct durability-failure lock release (P2-007, P2-011, P2-012, P2-014,
   P2-015).
7. **P1 infrastructure and liveness:** require DB 15 unconditionally, decide and
   implement authenticated execution resume after the last ambiguity, and add
   deployment load/SLO testing (P2-016 and P2-D01).
8. **Release governance:** correct the implementation report, link every
   acceptance row to executable evidence, obtain and record Section 11 review,
   then rerun compile, focused, complete, real-AOF, large-backlog, redaction,
   crash/restart, and production-startup suites (P2-017/P2-018).

## 9. Final GO/NO-GO

**NO-GO. Production non-idempotent dispatch must remain disabled.**

Real same-connection WAITAOF materially strengthens local intent durability, but
it does not compensate for reproducible retry/fence/write-path bypasses, the
unimplemented production connector contract and registry, incomplete crash
evidence, or missing operator/recovery controls. Reconsideration is appropriate
only after the ordered P0 tasks and the complete Section 11 gate pass without
weakening the bounded guarantee.
