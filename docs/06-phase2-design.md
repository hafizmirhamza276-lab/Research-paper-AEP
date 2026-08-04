# AEP Phase 2 Design: Intent Ledger, Write-Ahead Dispatch, and Crash Recovery

**Status:** Proposed for review; no implementation exists yet  
**Scope:** One non-idempotent external mutation at one logical execution step  
**Topology:** One self-hosted Redis instance, as assumed by Phase 1  
**Normative terms:** MUST, MUST NOT, SHOULD, and MAY are requirements in the
RFC 2119 sense.

## 1. Purpose and governing guarantee

This document turns the Phase 2 interface sketches in
[`AEP_IMPLEMENTATION_BRIEF.md` §7](../AEP_IMPLEMENTATION_BRIEF.md#7-phase-2-interface-contract-do-not-implement--for-surface-design-only)
and [`02-tech-design.md` §8](02-tech-design.md#8-phase-2-interface-contract)
into an implementation-ready protocol. It does not contain implementation
code.

The mechanism records an intent durably before permitting a non-idempotent
external call, records the observed outcome afterward, and stops automatic
execution when the outcome cannot be proved. Its guarantee is:

> AEP makes a potentially executed external mutation detectable and fails
> closed when its outcome is ambiguous.

It does **not** make the Redis write and the external system's mutation one
atomic transaction, and it does **not** provide exactly-once delivery.

## 2. Terms and identifiers

- **Execution**: one `AEPExecutionState`, stored at
  `aep:state:{execution_id}`.
- **Step**: a stable logical workflow position, identified by `step_id`.
- **Intent**: one attempt to perform one external mutation. Every attempt has
  a new immutable UUIDv4 `intent_id`; an intent is never overwritten or reused
  for a retry.
- **Dispatch**: the single point at which the request may begin leaving the
  process. Automatic transport retries for the non-idempotent method MUST be
  disabled.
- **Definitive success**: connector-specific evidence that the requested
  external effect exists.
- **Definitive failure**: connector-specific evidence that no external effect
  was applied. A generic HTTP error is not automatically definitive.
- **Ambiguous outcome**: the request may or may not have taken effect and the
  available evidence cannot distinguish those cases.
- **Reconciliation**: read-only inspection of the external system to determine
  whether an ambiguous intent took effect. Reconciliation MUST NOT repeat the
  mutation.

## 3. Intent record contract

Phase 2 replaces the free-form interpretation of `intent_ledger` with a typed
logical schema. The persisted representation remains JSON-compatible. The
ledger is a map keyed by `intent_id`; it is not keyed only by `step_id`, because
that would overwrite prior attempts and destroy forensic history.

Each intent record MUST contain:

| Field | Contract |
|---|---|
| `intent_id` | UUIDv4 equal to the ledger map key; immutable. |
| `step_id` | Stable logical step identifier; immutable. |
| `attempt` | Positive integer, unique and increasing within `step_id`. |
| `connector` | Versioned connector/operation name that defines response and reconciliation semantics. |
| `target` | Redacted logical target identifier; MUST NOT contain credentials. |
| `request_fingerprint` | SHA-256 of the canonical, secret-free request representation; immutable. |
| `correlation_id` | AEP-generated identifier sent to the provider when the provider accepts metadata. It is evidence, not an idempotency guarantee. |
| `status` | Exactly one state from §4. |
| `prepared_at` | Redis-server Unix time sampled with `TIME` immediately before the `ABOUT_TO_FIRE` write. |
| `client_timeout_seconds` | Timeout used for the mutation. |
| `settlement_lag_seconds` | Connector-declared time after which read-back may be trusted. |
| `reconcile_after` | `prepared_at + client_timeout_seconds + buffer_margin_seconds + settlement_lag_seconds`. |
| `prepared_state_version` | Execution-state version created by the write-ahead transition. |
| `external_reference` | Provider object/transaction identifier when known; otherwise null. |
| `last_observation` | Redacted response class, transport condition, and timestamp; never raw secrets or unrestricted bodies. |
| `reconciliation` | Attempt count, first/last check times, next check time, and last evidence class. |
| `transitions` | Append-only audit entries containing old state, new state, Redis-server time, actor, reason, and an evidence hash. |

There MUST be at most one intent in `ABOUT_TO_FIRE` or `FIRED_UNCONFIRMED`
for a given `step_id`. `FIRED_CONFIRMED`, `FAILED_CONFIRMED`, and
`PERMANENTLY_AMBIGUOUS` records remain in the ledger; a retry creates a new
`intent_id` and increments `attempt`.

While any intent is unresolved, saves MUST use a state TTL of at least the
configured reconciliation maximum age plus operator-retention period. The
initial values are 24 hours plus 7 days, hence a minimum TTL of 31 days. A
terminal incident may also be copied to the operator incident system, but that
copy is not a substitute for the Redis transition.

## 4. State machine

`NONE` is the conceptual absence of an intent for the step; it is not stored as
a record. The exact persisted states are:

| State | Meaning | Automated mutation allowed? |
|---|---|---|
| `ABOUT_TO_FIRE` | The write-ahead record has been accepted by Redis. The mutation has not yet produced a durably recorded outcome. After loss of the worker, this state is ambiguous even if the worker may actually have crashed before dispatch. | Only the original worker may perform the one dispatch, after the durability and lease preflight in §6. |
| `FIRED_CONFIRMED` | Conclusive provider response or authoritative read-back proves the requested effect exists. | No. Terminal. |
| `FAILED_CONFIRMED` | Conclusive evidence proves the mutation was not applied, including a locally proven failure before any request bytes were sent. | No dispatch under this intent. A retry, if policy permits it, requires a new intent. |
| `FIRED_UNCONFIRMED` | Dispatch may have occurred, but success or non-application is not proved. Despite the name, this does not assert that the effect fired. | No mutation retry. Read-only reconciliation only. |
| `PERMANENTLY_AMBIGUOUS` | Automated reconciliation is unavailable or exhausted. The execution is fenced and requires an audited operator decision. | No automated action. |

`COMPLETED_SUCCESSFULLY` from the earlier Phase 2 sketch is superseded by the
more precise canonical name `FIRED_CONFIRMED`. No Phase 2 records currently
exist, so no stored-data migration is required at design time.

### 4.1 Legal transitions

Every transition MUST occur while holding the execution lease, MUST append one
audit entry, MUST increment the execution version by exactly one, and MUST use
the lock-token/expected-version CAS write. The legal transition set is
exhaustive:

| From | To | Trigger and actor |
|---|---|---|
| `NONE` | `ABOUT_TO_FIRE` | Runner prepares a new immutable intent before dispatch. The transition is not complete for dispatch purposes until the durability barrier succeeds. |
| `ABOUT_TO_FIRE` | `FIRED_CONFIRMED` | Original worker receives connector-defined conclusive success and durably records it. |
| `ABOUT_TO_FIRE` | `FAILED_CONFIRMED` | Original worker proves no bytes were sent, or receives a connector-allowlisted rejection that guarantees no mutation occurred, and durably records it. |
| `ABOUT_TO_FIRE` | `FIRED_UNCONFIRMED` | Original worker observes timeout, connection loss after possible transmission, malformed/contradictory response, non-allowlisted error, or any other ambiguous result. A recovery worker also uses this transition when it claims a stale `ABOUT_TO_FIRE`. |
| `FIRED_UNCONFIRMED` | `FIRED_UNCONFIRMED` | Recovery stores another `UNKNOWN` observation, increments reconciliation attempts, and schedules the next read-back. This is the only legal same-state transition. |
| `FIRED_UNCONFIRMED` | `FIRED_CONFIRMED` | Authoritative read-back proves the effect exists. |
| `FIRED_UNCONFIRMED` | `FAILED_CONFIRMED` | Authoritative read-back proves the effect does not exist after the connector's settlement horizon. |
| `FIRED_UNCONFIRMED` | `PERMANENTLY_AMBIGUOUS` | No safe read-back exists, evidence conflicts, or reconciliation reaches 8 attempts or 24 hours without proof. |
| `PERMANENTLY_AMBIGUOUS` | `FIRED_CONFIRMED` | Audited operator resolution or later conclusive evidence proves the effect exists. |
| `PERMANENTLY_AMBIGUOUS` | `FAILED_CONFIRMED` | Audited operator resolution or later authoritative evidence proves no effect exists. |

All other transitions are illegal. In particular:

- no state transitions back to `NONE` or `ABOUT_TO_FIRE`;
- terminal confirmed states are immutable in normal operation;
- an ambiguous intent is never changed to `FAILED_CONFIRMED` merely because a
  query returned no result unless that connector declares the negative result
  authoritative after its settlement horizon;
- neither the runner nor resolver dispatches the same `intent_id` twice; and
- deleting an intent record is not a state transition and is forbidden.

Every transition into `FIRED_UNCONFIRMED` initializes reconciliation with
`attempt_count = 0` and `next_check_at = max(reconcile_after, transition_time)`.
The recovery worker that claims a stale `ABOUT_TO_FIRE` may perform the first
eligible read-back immediately after that durable transition.

An audited operator who accepts duplicate risk MUST first resolve or retain the
old record as `PERMANENTLY_AMBIGUOUS`, then create a new intent with a new
`intent_id`, a new attempt number, and a recorded `risk_acceptance_id`. The old
intent is never reused.

## 5. Normal write-ahead workflow

1. The runner acquires the execution lease with jittered contention backoff.
   `T_client <= T_lock - Buffer_Margin`, with `Buffer_Margin >= 15s`, remains a
   hard invariant.
2. Under the lease, it reads the latest state and version. It refuses to run if
   the same step already has an unresolved intent.
3. It creates the immutable intent, transitions `NONE -> ABOUT_TO_FIRE`, sets
   the execution to a non-schedulable in-progress state, increments the version
   by one, and performs the durable write in §6. If any part of that durable
   write is unconfirmed, it MUST NOT call the provider.
4. Immediately before dispatch, it performs the lease/status preflight in
   §6.3. Failure means no dispatch and fail-closed handling.
5. It makes exactly one application-level dispatch. HTTP/client automatic
   retries for the non-idempotent operation MUST be disabled. The AEP
   `correlation_id` SHOULD be attached where supported.
6. The connector classifies the result:
   - allowlisted conclusive success -> `FIRED_CONFIRMED`;
   - allowlisted conclusive non-application -> `FAILED_CONFIRMED`;
   - timeout, disconnect after possible transmission, generic 5xx, unknown
     provider error, malformed response, or conflicting evidence ->
     `FIRED_UNCONFIRMED`.
7. The runner writes the resolution with a version increment and the same
   durability barrier. It may retry **only this Redis resolution write** while
   it still owns the lease; it MUST NOT repeat the external mutation.
8. It releases the lease after the resolution is durably acknowledged. If the
   resolution cannot be made durable or lease ownership is lost, the execution
   is alerted and left for recovery; the mutation is not repeated.

Each connector MUST publish an explicit response classification table. Status
code families alone are insufficient: for example, a provider may return 500
after committing a mutation. Unclassified responses default to ambiguity.

## 6. Atomicity and durability boundary

### 6.1 What is atomic

The write-ahead transition is one Redis Lua CAS operation invoked via
`EVALSHA` (with the normal `EVAL` fallback on cache miss). In one Redis command,
it MUST:

1. verify the current lock value equals the caller's ownership token;
2. read and validate the stored state/version;
3. require the caller's exact `expected_version` and an incoming version of
   `expected_version + 1`;
4. validate the requested intent transition;
5. append the audit transition and update the execution status; and
6. `SET` the complete state JSON with the required TTL.

Those checks and the state replacement are atomic with each other because a
Redis script runs without interleaving. The intent status, audit entry,
execution status, and execution version are therefore one atomic Redis-state
change.

There is deliberately no secondary pending-intent index in Phase 2 v1. The
state key is the sole source of truth and recovery uses `SCAN` (§8). This avoids
a cross-key consistency gap between a state write and an index write.

### 6.2 The local durability barrier

A successful Lua return means the write is visible in Redis memory; with
`appendfsync everysec` it does not by itself mean the intent is on disk. Phase 2
therefore tightens durability only for intent and intent-resolution writes:

1. The Lua CAS and subsequent durability command MUST use the same pinned Redis
   connection.
2. After a successful CAS, the runner issues `WAITAOF 1 0
   <durability-timeout-ms>` on that same connection.
3. The write is dispatch-authorizing only when `WAITAOF` reports at least one
   local AOF fsync before the timeout.
4. If the barrier times out or errors, no external call is allowed. The runner
   may retry the barrier while its lease and time budget remain valid; it may
   not rewrite or dispatch speculatively. If it still owns the lease and can
   make a durable state write, it transitions the intent to `FAILED_CONFIRMED`
   with reason `pre-dispatch-durability-failure`; otherwise it leaves the
   conservative `ABOUT_TO_FIRE` for recovery.

[`WAITAOF`](https://redis.io/docs/latest/commands/waitaof/) is available from
Redis Open Source 7.2 and applies to preceding writes from the same connection,
which is why a generic pooled follow-up command is insufficient. Phase 2
startup in `WAITAOF` mode MUST verify Redis 7.2+ and AOF capability. An approved
alternative for older Redis is a verified
`appendfsync always` deployment, where successful completion of the CAS command
is the local fsync barrier. `WAIT` is not a substitute in the single-instance
topology because it acknowledges replicas, not local AOF fsync
([Redis `WAIT` documentation](https://redis.io/docs/latest/commands/wait/)). If
neither approved durability mode is available, non-idempotent dispatch is
disabled.

“Durable” here means acknowledged to the one Redis instance's local AOF. It
does not mean replicated, immune to storage-controller loss, or durable across
loss of the Redis host.

### 6.3 Final pre-dispatch check

After the durability barrier and immediately before calling the provider, a
read-only Lua preflight MUST atomically verify:

- the execution lock still contains the same ownership token;
- its `PTTL` is at least `T_client + Buffer_Margin`;
- the execution version is still `prepared_state_version`; and
- the selected `intent_id` is still `ABOUT_TO_FIRE`.

If TTL is insufficient, the worker may perform one token-checked lease renewal
and repeat the preflight. Any other failure forbids dispatch. A scheduling gap
still exists between a successful preflight and network transmission; the
buffer reduces that risk but cannot make the two systems atomic.

When preflight fails before dispatch and the worker still owns the lease, it
durably records `FAILED_CONFIRMED` with the exact pre-dispatch reason. If lease
ownership was lost, it cannot write and leaves `ABOUT_TO_FIRE` for conservative
recovery.

### 6.4 What is not atomic

| Operations | Atomic? | Consequence |
|---|---|---|
| Lease acquisition and intent write | No; they are separate Redis commands. | The intent script rechecks the token. A lease acquired earlier is not proof of current ownership. |
| Intent CAS and AOF fsync | No; `EVALSHA` then `WAITAOF` are sequential on one connection. | Dispatch is forbidden until both succeed. |
| Intent write and external mutation | No; Redis and the provider share no transaction coordinator. | A crash between them leaves a conservative `ABOUT_TO_FIRE`. |
| External mutation and resolution write | No. | A successful mutation can remain recorded as `ABOUT_TO_FIRE` or `FIRED_UNCONFIRMED`. Recovery must reconcile; it must not replay. |
| Lease ownership and the whole external call | No continuous atomic guarantee. | Timeout, preflight, renewal, and CAS fencing reduce overlap but cannot recall a late provider-side effect. |
| Redis state and dashboard/alert delivery | No. | Alerts are retried independently; Redis state is authoritative for execution safety. |
| A recovery `SCAN` and concurrent state writes | No snapshot. | Every candidate is re-read after acquiring its execution lease. |

## 7. Crash-point behavior

The following table is exhaustive for one call. “Stored state” means the state
that survives Redis recovery; a pre-barrier write may or may not survive.

| Crash point | Possible stored intent | Was the effect possible? | Required restart behavior |
|---|---|---|---|
| Before acquiring the lease | `NONE` | No | Normal scheduling may start the step. |
| After lease acquisition but before intent CAS | `NONE` | No | Let the lease expire or reacquire it; normal scheduling may start the step. |
| During intent CAS, or after its reply but before the durability barrier | `NONE` or `ABOUT_TO_FIRE` | No, because dispatch was forbidden | If `NONE`, normal scheduling may create an intent. If `ABOUT_TO_FIRE`, treat it conservatively as ambiguous and reconcile; do not infer that the call was never made. |
| After durable `ABOUT_TO_FIRE` but before preflight | `ABOUT_TO_FIRE` | No | Recovery still treats it as ambiguous; false-positive ambiguity is the cost of write-ahead safety. |
| After successful preflight but before request transmission | `ABOUT_TO_FIRE` | No | Same conservative recovery; no automatic retry. |
| During transmission or while waiting with no response | `ABOUT_TO_FIRE` | Yes | After `reconcile_after`, claim and reconcile. Never replay. |
| After receiving conclusive success but before/during the resolution CAS or its durability barrier | `ABOUT_TO_FIRE` or `FIRED_CONFIRMED` | Yes | If confirmed state survived, finish without replay. Otherwise reconcile and prove the existing effect. |
| After receiving conclusive no-effect failure but before/during its resolution CAS or barrier | `ABOUT_TO_FIRE` or `FAILED_CONFIRMED` | No, based on evidence lost with the worker | If failure state survived, policy may create a new intent. If only `ABOUT_TO_FIRE` survived, recovery must remain conservative and reconcile. |
| After a timeout, disconnect, generic error, or ambiguous response but before/during its resolution CAS or barrier | `ABOUT_TO_FIRE` or `FIRED_UNCONFIRMED` | Yes | Reconcile read-only. Never replay. |
| After a durable confirmed resolution but before lease release | `FIRED_CONFIRMED` or `FAILED_CONFIRMED` | As recorded | Lease release or expiry is cleanup only. The terminal intent prevents replay. |
| After durable `FIRED_UNCONFIRMED` but before lease release | `FIRED_UNCONFIRMED` | Yes | Recovery continues read-only reconciliation when eligible. |
| During recovery before its CAS | Existing ambiguous state | Already possible | No state change; another resolver may later acquire the lease. |
| After recovery claims `ABOUT_TO_FIRE` as `FIRED_UNCONFIRMED` but before read-back | `FIRED_UNCONFIRMED` | Already possible | A later resolver resumes reconciliation; it does not mutate the provider. |
| After read-back result but before/during recovery resolution persistence | Previous ambiguous state or confirmed/permanent state | Already possible | Re-run the read-only query after backoff if the resolution did not survive. Never replay the mutation. |

If the Redis host loses an intent even after its local fsync acknowledgment due
to catastrophic disk/host loss, AEP may have no record of a dispatched effect.
That is outside the guarantee and is called out explicitly in §9.

## 8. Recovery and reconciliation

### 8.1 Discovery

The recovery service continuously performs cursor-based
`SCAN MATCH aep:state:* COUNT 500`. It processes a bounded number of keys
concurrently and starts a new pass 30 seconds after cursor zero. A full pass
SHOULD complete within five minutes; exceeding that SLO raises a recovery-lag
alert.

For each key, the service calls the normal validated `get_state`; it never
parses or rewrites raw JSON. Corruption follows the existing quarantine and
circuit-breaker path. A state is a candidate when:

- an intent is `ABOUT_TO_FIRE` and Redis server time is at least
  `reconcile_after`; or
- an intent is `FIRED_UNCONFIRMED` and server time is at least
  `reconciliation.next_check_at`.

`PERMANENTLY_AMBIGUOUS` records are surfaced to the operator dashboard but are
not automatically processed. Confirmed records are ignored.

### 8.2 Claiming without racing the original worker

For each candidate, the resolver:

1. attempts the same execution lease used by normal workers, with full-jitter
   backoff; if unavailable, it does nothing;
2. after acquisition, re-reads and validates the complete state;
3. confirms the same `intent_id`, status, version, and eligibility time still
   apply;
4. for stale `ABOUT_TO_FIRE`, performs a durable CAS transition to
   `FIRED_UNCONFIRMED` with reason `orphaned-about-to-fire`; and
5. performs only connector-declared read-only reconciliation while holding a
   capped lease sized to the read timeout plus the 15-second buffer.

The claim CAS gives the recovery worker a newer execution version and requires
its current lock token. A late original worker therefore cannot persist its
resolution: its token and version are stale. The external request itself
cannot be recalled, so the resolver never sends the mutation. It also waits
until `reconcile_after`, which is beyond the original client timeout, safety
buffer, and connector settlement lag.

If the original process violates its timeout and remains alive after lease
loss, the above still avoids a second mutation. A negative provider lookup may
be accepted only when the connector documents that it is authoritative after
the settlement horizon. For eventually consistent or positive-only lookups,
“not found” remains `UNKNOWN`.

### 8.3 Connector reconciliation contract

Every non-idempotent connector MUST declare one capability:

| Capability | Permitted conclusion |
|---|---|
| `AUTHORITATIVE_READBACK` | May return `APPLIED`, `NOT_APPLIED`, `UNKNOWN`, or `CONFLICT`. `NOT_APPLIED` is legal only after the declared settlement horizon. |
| `POSITIVE_ONLY_READBACK` | May return `APPLIED`, `UNKNOWN`, or `CONFLICT`. Absence never proves failure. |
| `NO_READBACK` | No automated query is made; the resolver proceeds to permanent ambiguity and operator review. |

Results map as follows:

- `APPLIED` -> `FIRED_CONFIRMED`, storing the external reference and evidence;
- authoritative `NOT_APPLIED` -> `FAILED_CONFIRMED`;
- `UNKNOWN` -> remain `FIRED_UNCONFIRMED`, append evidence, and retry;
- `CONFLICT` or multiple possible matches -> `PERMANENTLY_AMBIGUOUS`.

For `UNKNOWN`, the resolver makes at most 8 read-back attempts and stops no
later than 24 hours after the first eligible reconciliation. Backoff uses a
delay sampled uniformly from zero through
`min(5 * 2^(attempt-1), 300)` seconds; the chosen `next_check_at` is persisted.
Reaching either limit transitions to
`PERMANENTLY_AMBIGUOUS` and emits a critical operator alert. Loss of the
resolver lease, a stale CAS, or a systemic circuit-breaker trip aborts the
attempt without changing the external system.

### 8.4 Scheduling and operator behavior

- Any execution containing `ABOUT_TO_FIRE`, `FIRED_UNCONFIRMED`, or
  `PERMANENTLY_AMBIGUOUS` is ejected from normal scheduling. The execution's
  top-level status is `PAUSED` once recovery claims ambiguity.
- The first transition to `FIRED_UNCONFIRMED` raises an operator-visible
  warning. `PERMANENTLY_AMBIGUOUS` raises a critical incident containing the
  execution ID, intent ID, target, fingerprint, timestamps, and redacted
  evidence.
- Manual resolution requires acquiring the execution lease, re-reading the
  state, and performing the same durable expected-version CAS. The transition
  records the authenticated operator, ticket/evidence reference, and reason.
- The resolver never turns ambiguity into permission to retry. Only
  `FAILED_CONFIRMED` can make a new attempt eligible under normal scheduler
  policy.

## 9. Explicit non-goals and residual risks

This design does not guarantee:

1. **Exactly-once delivery or execution at the provider.** AEP cannot atomically
   commit Redis and a legacy API, and the provider may not support idempotency.
2. **Duplicate prevention after an operator risk override.** A forced new
   intent may duplicate an unresolved old effect; the audit record only makes
   that decision explicit.
3. **Recovery of an intent lost with the Redis host/storage.** `WAITAOF`
   narrows the loss window to the local durability boundary; it does not create
   another copy or survive catastrophic storage loss.
4. **HA, consensus, or split-brain prevention.** The topology remains one Redis
   instance and the lock remains a lease.
5. **Recall or cancellation of a provider-side operation.** Cancelling the
   client timeout does not prove the provider stopped processing.
6. **Authoritative reconciliation where the provider exposes no trustworthy
   read-back.** Such cases stop at `PERMANENTLY_AMBIGUOUS`.
7. **Correct negative inference from eventually consistent APIs.** Connectors
   that cannot prove absence may only return `UNKNOWN`.
8. **Atomic alert/dashboard delivery with Redis state.** Monitoring is
   operationally retried and may lag the authoritative execution record.
9. **Unlimited ledger retention.** Retention is bounded; unresolved state must
   be retained for at least the configured reconciliation and operator window.
10. **Compensation.** Reversing a confirmed external effect is a separate,
    connector-specific workflow and, if non-idempotent, requires its own new
    intent.

## 10. Comparison with related mechanisms

The repository's
[`research_analysis_report.md` literature section](../research_analysis_report.md#strong-overlap-with-established-techniques)
identifies the following mechanisms. The comparison deliberately does not claim
novelty beyond that evidence.

| System | Mechanism cited in the repository literature review | Relationship to AEP | Why |
|---|---|---|---|
| [Beldi](https://www.usenix.org/conference/osdi20/presentation/zhang-haoran) | Logs stateful serverless operations and uses an **intent collector** to restart stalled functions. | **Variant at the intent/collector level; different recovery rule.** | AEP likewise records durable intent and has a separate process find stalled work. Unlike the cited Beldi behavior, AEP must not restart an ambiguous non-idempotent mutation; it performs read-only reconciliation or halts. AEP is also a Redis/lease/CAS protocol for agent executions, not a transactional serverless runtime. |
| [ExoFlow](https://www.usenix.org/conference/osdi23/presentation/zhuang) | Uses write-ahead logging for exactly-once workflow recovery and explicitly treats external effects. | **Limited variant of the WAL pattern; different guarantee and scope.** | AEP writes intent before one external effect and records its resolution afterward, but it does not provide a general DAG recovery engine or claim exactly-once behavior. Legacy providers without idempotency keep the Redis/effect gap fundamentally ambiguous. |
| [ACRFence](https://arxiv.org/abs/2603.20625) | Records irreversible tool effects across agent checkpoint/restore to enforce recovery semantics and prevent replay after semantic rollback. | **Same problem family, different/variant mechanism.** | Both fence replay of agent-triggered irreversible effects using durable effect metadata. AEP records pre-dispatch intent plus post-dispatch evidence and combines it with a Redis lease and version CAS; its response to missing proof is reconciliation or a permanent fail-closed state, not a claim that checkpoint restore can make the provider action exactly once. |

## 11. Review acceptance criteria

Phase 2 implementation must not begin until reviewers agree that:

- every connector has response-classification and reconciliation-capability
  declarations;
- the Redis deployment supports one approved local durability barrier;
- same-connection CAS plus `WAITAOF` can be guaranteed by the client design;
- scheduler, runner, resolver, and operator paths enforce the transition table;
- the scanner and retention settings satisfy the recovery SLO;
- all crash points in §7 have adversarial tests; and
- documentation and telemetry use “detectable ambiguity + fail-closed,” never
  “exactly once.”
