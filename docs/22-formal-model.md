# AEP System Model, Failure Model, and Protocol Properties

**Document:** `docs/22-formal-model.md`
**Phase:** written in Phase 1A of `PAPER_ROADMAP.md` (§1); revised in Phase 1B
(`PAPER_ROADMAP.md:55-71`) after the four correctness fixes landed; citation
paths re-pointed in Phase 2A when the package was renamed.
**Status:** Descriptive model of the code as committed. Not a specification of
intended future behaviour.
**Sources read to produce this document:** `docs/01-hld.md`,
`docs/02-tech-design.md`, `docs/06-phase2-design.md`, and every module in
`aep_core/core/`.

---

## 0. How to read this document

Three rules govern every statement below.

1. **Every claim about system behaviour cites the enforcing artifact as
   `file:line`.** A claim without a citation is a definition, an assumption, or
   an explicitly labelled non-claim.
2. **Where the code does not enforce a property, this document says so.** The
   repository's own audit history (`docs/07-phase2-gap-audit.md:17-42`)
   records that earlier internal reports asserted properties the code did not
   have. §5 is the list of things that are *designed* in
   `docs/06-phase2-design.md` but *not enforced* in `aep_core/core/`.
3. **"Enforced" means a code path rejects the violation**, not that a
   convention exists. Where a property holds only because one particular
   caller sequences operations correctly, this document labels it *path
   discipline*, not *invariant*.

Line numbers refer to the repository state in which this revision was written.
Every `file:line` citation in this document is machine-checked in CI by
`scripts/validate_citations.py`, which fails the build if a cited path stops
existing or a cited line falls outside the file. Range validity is all that
check proves; semantic correctness rests on the per-anchor evidence recorded
in the phase reports.

### 0.05 Phase 2A: package rename

Phase 2A renamed the top-level package `src` → `aep_core`
(`PAPER_ROADMAP.md:82`). Every citation below that previously read
`src/core/...` now reads `aep_core/core/...`. **Line numbers are unchanged:**
the rename moved files and rewrote import statements only, with no edit to
any statement inside a function. Historical reports
(`reports/phase-report-1A-2026-08-05.md`,
`reports/phase-report-1b-2026-08-05.md`, `docs/07`–`docs/21`) still cite the
old paths and are deliberately left alone — they are records of a tree that
existed, not live references.

### 0.1 What Phase 1B changed

| Phase 1A finding | Status now |
|---|---|
| Response classes were a test-only construct (§1.5) | **Closed.** The contract is `aep_core/core/connector_contract.py`; `tests/mock_connector.py:24-27` imports it. |
| Recovery had no fault isolation (§5.3, assumption A2) | **Closed.** `aep_core/core/intent_recovery.py:192-261`, `:263-319`. |
| The barrier-before-dispatch ordering was path discipline (§3.2 R2-7) | **Partly closed.** It is now a checked precondition; the irreducible part is declared as R2-7 below. |
| Dispatch was possible only in a test-only composition (§1.7) | **Changed in kind.** An explicit `DispatchMode` now exists; `EVALUATION` requires production-grade durability and vault. |
| R1-3 (AOF rewind un-fences a lease) was a reasoned hypothesis | **Confirmed by probe**, no local fix; still a declared residual. |
| R3-5 (escalated records expire) was a reasoned hypothesis | **Confirmed by probe**; retention floor fixed; finite retention remains a declared residual. |

---

## 1. System model

### 1.1 Principals

| Principal | Realisation in code | Notes |
|---|---|---|
| **Runner** (worker) | `WriteAheadRunner` — `aep_core/core/intent_workflow.py:139` | Performs at most one external mutation per invocation of `execute` (`aep_core/core/intent_workflow.py:363`). |
| **Recovery service** (resolver) | `IntentRecoveryService` — `aep_core/core/intent_recovery.py:96` | Read-only with respect to the external system; writes only Redis state. |
| **Connector** | `ExternalMutationConnector` — `aep_core/core/intent_workflow.py:54`; reconciliation side `ReconciliationConnector` — `aep_core/core/connector_contract.py:101` | The only component that touches the external API. |
| **Store** | Single Redis instance, via `IntentLedgerStore` (`aep_core/core/intents.py:706`) and `RedisStorageAdapter` (`aep_core/core/storage.py:393`) | |
| **Operator** | *Not implemented as a component.* | The only operator surface is `transition_intent` (`aep_core/core/intents.py:874`) with an `actor` string. See §5.3. |

There is still **no process supervisor, daemon entrypoint, or CLI in the
repository**: `src/` contains no `if __name__ == "__main__"` block and
`pyproject.toml` declares no console scripts. `IntentRecoveryService.run_forever`
(`aep_core/core/intent_recovery.py:263`) is a library coroutine that some external
deployment must schedule. This still conditions P2 and P3 (assumption A1).

### 1.2 The store: one Redis 7.2 instance with AOF

- **Topology:** a single self-hosted Redis instance. No replica, no Sentinel,
  no Cluster (`docs/01-hld.md:48`, restated for Phase 2 in
  `docs/06-phase2-design.md:5`).
- **Persistence:** append-only file with `appendfsync everysec`
  (`redis/phase2.conf:11-12`), RDB snapshots disabled (`redis/phase2.conf:9`).
  The pinned image is `redis:7.2.5-alpine` by digest (`compose.phase2.yml:5`),
  published only on loopback (`compose.phase2.yml:9`).
- **Access control:** `protected-mode no` and `bind 0.0.0.0`
  (`redis/phase2.conf:3-4`); the only confinement is the loopback port
  mapping. No Redis ACL restricts which clients may write `aep:state:*`.

**Keyspace.**

| Key | Written by | Citation |
|---|---|---|
| `aep:state:{execution_id}` | the two state Lua scripts only | `aep_core/core/intents.py:601`, `aep_core/core/storage.py:266` |
| `aep:lock:{execution_id}` | `SET NX EX` / token-checked Lua `DEL`/`PEXPIRE` | `aep_core/core/locks.py:149-152`, `:35-52`, `:54-70` |
| `aep:dispatch-auth:{execution_id}:{intent_id}` | the dispatch-authorization Lua only | `aep_core/core/intents.py:673`, key builder `:1076` |
| `aep:vault:{locator}` | the evaluation vault (EVALUATION mode only) | `aep_core/core/request_vault.py:372` |
| `aep:poison:{execution_id}:{epoch_ms}` | best-effort quarantine writer | `aep_core/core/storage.py:784-822` |

**Authoritative object.** `aep:state:{execution_id}` holds one JSON document
validated as `Phase2ExecutionState` (`aep_core/core/intents.py:339`), extending
`AEPExecutionState` (`aep_core/core/storage.py:82`) with a typed
`intent_ledger: dict[str, IntentRecord]`. Serialisation is deterministic
(`aep_core/core/state_codec.py:118-138`); decoding rejects duplicate JSON member
names (`aep_core/core/state_codec.py:67-75`). A Lua re-implementation of the same
strict UTF-8 + duplicate-member check is prefixed to every authoritative script
(`aep_core/core/state_codec.py:151-421`, `:425-428`).

**Version.** `version: int` is the fencing counter, bounded to 2^53−1 because
Redis Lua numbers are IEEE-754 doubles (`aep_core/core/storage.py:74-76`). It is
deliberately distinct from the lock ownership token, a random
`secrets.token_urlsafe(32)` (`aep_core/core/locks.py:150`, documented `:126-129`).

**State-key lifetime.** Every authoritative write sets an expiry
(`aep_core/core/intents.py:601`; `aep_core/core/storage.py:266`). The Lua rejects a TTL
below 31 days whenever the resulting ledger contains an `ABOUT_TO_FIRE`,
`FIRED_UNCONFIRMED`, **or `PERMANENTLY_AMBIGUOUS`** record
(`aep_core/core/intents.py:592-599`, floor constant `:49`). The ledger is
bounded-retention, not permanent; see R3-5.

### 1.3 Network model

- TCP to Redis; `decode_responses=True` with a shared pool
  (`docs/02-tech-design.md:1150`; convention only).
- Redis executes a Lua script without interleaving, so a script is a single
  serialisation point (`docs/06-phase2-design.md:194-197`).
- **Connection pinning** is required for CAS-then-durability, because
  `WAITAOF` reports fsync progress for writes on the same connection
  (`docs/06-phase2-design.md:222-236`). Provided by
  `IntentLedgerStore.pinned_connection` (`aep_core/core/intents.py:729`), used at
  `aep_core/core/intent_workflow.py:424`, `:511`, `:619` and
  `aep_core/core/intent_recovery.py:379`, `:539`.
- Transport faults become typed, non-silent failures:
  `LockAcquisitionError` (`aep_core/core/locks.py:153-157`),
  `StorageOperationError` (`aep_core/core/storage.py:515-516`),
  `IntentStateError` (`aep_core/core/intents.py:1022-1025`),
  `WriteAheadWorkflowError` (`aep_core/core/intent_workflow.py:335-338`).
  No transport fault is interpreted as evidence about the external system.

### 1.4 Clock model

**No synchrony assumption beyond lease TTLs.**

| Time source | Used for | Citation |
|---|---|---|
| Redis server `TIME` | `prepared_at`, `reconcile_after`, `next_check_at`, audit times, recovery eligibility | `aep_core/core/intents.py:735`; recovery at `aep_core/core/intent_recovery.py:202`, `:367` |
| Redis key expiry / `PTTL` | lease liveness, pre-dispatch TTL floor, dispatch-authorization lifetime | `aep_core/core/locks.py:152`; `aep_core/core/intents.py:618`, `:673` |
| Process-local `monotonic` | heartbeat interval, deadline watchdog, dispatch-capability expiry, recovery pass SLO | `aep_core/core/locks.py:350-357`, `:406-420`; `aep_core/core/request_binding.py:1191`; `aep_core/core/intent_recovery.py:288` |
| Process-local `time.time()` | nothing that affects an authoritative decision | passed as `ARGV[7]` to the intent CAS but never referenced by that script |

- All ordering decisions between principals are taken against the Redis server
  clock. No cross-worker clock comparison occurs.
- `T_client <= T_lock − Buffer_Margin`, `Buffer_Margin >= 15s`
  (`docs/01-hld.md:84`) is enforced at configuration time in
  `ConnectorPolicy.__post_init__` (`aep_core/core/intent_workflow.py:97-104`) and in
  `DistributedLockManager.lease` (`aep_core/core/locks.py:292-321`). It is a timing
  budget, not a synchrony guarantee: `docs/06-phase2-design.md:249-252` states
  that a gap remains between a successful preflight and transmission.

### 1.5 The external legacy API

Non-idempotent and non-cooperative: it need not accept an idempotency key, and
its response may be absent, late, or self-contradictory.

**(a) Caller-visible evidence at mutation time.** The runner accepts only
policy-declared values: `ConnectorPolicy.definitive_success_evidence` /
`definitive_failure_evidence`, required non-empty and disjoint
(`aep_core/core/intent_workflow.py:84-90`, `:119-124`). Any other value, and any
exception, is coerced to ambiguity (`aep_core/core/intent_workflow.py:591-616`).
Ambiguity is the default, not a special case.

**(b) Reconciliation response classes — now production code.**

| Class | Permitted conclusions | Design | Code |
|---|---|---|---|
| `AUTHORITATIVE_READBACK` | `APPLIED`, `NOT_APPLIED`, `UNKNOWN`, `CONFLICT` | `docs/06-phase2-design.md:351` | `aep_core/core/connector_contract.py:36-45`, table `:78-99` |
| `POSITIVE_ONLY_READBACK` | `APPLIED`, `UNKNOWN`, `CONFLICT` — absence never proves failure | `docs/06-phase2-design.md:352` | same |
| `NO_READBACK` | no automated query | `docs/06-phase2-design.md:353` | same |

Phase 1A recorded that these lived only in `tests/mock_connector.py`. They are
now defined in `aep_core/core/connector_contract.py` and the test harness imports
them (`tests/mock_connector.py:24-27`). Three consequences:

- The capability is resolved by `declared_capability`
  (`aep_core/core/connector_contract.py:118-140`), which **fails closed** on a
  missing, `None`, or unrecognised declaration rather than defaulting.
- Classification is total and explicit per class in `classify_readback`
  (`aep_core/core/connector_contract.py:171-240`). `POSITIVE_ONLY_READBACK` +
  `NOT_APPLIED` is a *named* contract violation
  (`aep_core/core/connector_contract.py:220`), not a fall-through.
- Recovery consumes the typed contract, not string literals
  (`aep_core/core/intent_recovery.py:404`, `:424`, `:469`); a regression test
  asserts no capability/result string literal remains in that module
  (`tests/test_connector_contract.py:318-330`).

**(c) Read-back result alphabet.** `ReadbackResult`
(`aep_core/core/connector_contract.py:47-54`). Unparseable or absent evidence
degrades to `UNKNOWN` (`aep_core/core/connector_contract.py:142-169`) so it consumes
reconciliation budget instead of asserting a conclusion.

**(d) The read-back request carries no dispatch authority.** Recovery passes a
`ReconciliationContext` (`aep_core/core/request_binding.py:1065-1095`) built at
`aep_core/core/intent_recovery.py:441-453`: identifiers, a redacted target, and the
fingerprint — no request material, no capability object.

### 1.6 Dispatch authority

A mutation call requires a `VerifiedDispatch`
(`aep_core/core/request_binding.py:1109-1131`), which cannot be constructed
(`:1115-1116`), subclassed (`:1118-1119`), or copied (`:1121-1125`); is minted
only by the wrapper over `RequestBindingService.verify`
(`aep_core/core/request_binding.py:1489-1503`); and is single-use
(`:1195-1251`). Before minting it, the runner re-reads the *authoritative
persisted* state and requires the stored canonical binding to equal the
prepared one (`aep_core/core/intent_workflow.py:530-554`).

**Phase 1B adds a second, Redis-visible gate** (§3.2 B).

### 1.7 Composition modes

`DispatchMode` (`aep_core/core/intent_workflow.py:39-52`) is checked by
`validate_startup` (`aep_core/core/intent_workflow.py:226-309`). An unspecified mode
is `PRODUCTION`; a caller that passed `allow_test_dispatch` without naming a
mode is placed in `TEST` by that act (`aep_core/core/intent_workflow.py:162-166`).
No composition silently degrades.

| Mode | Vault | Barrier | Connector |
|---|---|---|---|
| `TEST` | must be `test_only` (`:262-265`) | test barrier allowed only with `allow_test_barrier` (`:271-278`) | must be `test_only` (`:266-269`) |
| `EVALUATION` | must **not** be `test_only` (`:284-287`) | must **not** be a test barrier (`:288-291`); real `validate_startup` runs (`:309`, `:212-224`) | must declare `evaluation_endpoint` (`:302-307`) and must not be `test_only` (`:292-295`) |
| `PRODUCTION` | as EVALUATION, and must not be the evaluation vault (`:297-301`) | as EVALUATION | must **not** be an evaluation endpoint (`:293-296`) |

`PRODUCTION` and `EVALUATION` share one block of requirements, so *"differs
only in the connector endpoint"* is a property of the code, not of prose.

The evaluation vault is `EvaluationRedisRequestVault`
(`aep_core/core/request_vault.py:321`): AES-GCM, create-once
(`:372-411`), authenticated metadata as AAD, exact-length verification, no
update path (`:451`), durable in Redis. It declares `test_only = False`,
`evaluation_only = True` (`:341-342`). Two properties are weaker than the
production vault/KMS design in `docs/15-production-vault-kms-design.md` and are
declared, not hidden: it shares the Redis trust domain, and its keys are
operator-supplied rather than KMS-wrapped
(`aep_core/core/request_vault.py:325-339`).

**`PRODUCTION` still cannot be satisfied by this repository**: there is no
production vault and no production connector. `validate_startup` fails closed
for it. An evaluation therefore runs in `EVALUATION` mode and must say so.

---

## 2. Failure model

Crash-and-delay, not Byzantine. Redis is trusted to execute scripts atomically
and honour expiry; the external provider is trusted only to the extent that its
declared evidence is truthful (§5.1).

### F1 — Worker crash at any instruction boundary

22 named crash points (`tests/mock_connector.py:59`), reached through
`_checkpoint` hooks that are inert when no injector is configured
(`aep_core/core/intent_workflow.py:204-210`, `aep_core/core/intent_recovery.py:136-143`).

**Honest limitation, unchanged by Phase 1B.** Crashes are modelled *in
process*: `CrashStyle` (`tests/mock_connector.py:124`) and
`SimulatedProcessCrash`, a `BaseException` subclass chosen so the pytest
process survives (`tests/mock_connector.py:159`). **No OS-level `SIGKILL` of a
separate worker process occurs anywhere in this repository.** The
`PAPER_ROADMAP.md:105` requirement for separate-process `SIGKILL` injection is
Phase 2B work.

### F2 — Network partition between a worker and Redis

Not simulated (no proxy, no `tc netem`, no toxiproxy; `PAPER_ROADMAP.md:130`
schedules it). Its modelled effect is that any Redis command may raise, and
every raise forbids progress rather than permitting a guess (§1.3). A partition
outlasting the lease is observationally equal to F5.

### F3 — Redis restart with AOF replay

On restart Redis replays the AOF. With `appendfsync everysec`
(`redis/phase2.conf:12`) up to roughly 1–2 s of acknowledged-but-unsynced
writes may be absent (`docs/02-tech-design.md:1214-1216`).

1. **Intent and resolution writes get an explicit fsync barrier.**
   `WAITAOF 1 0 <timeout-ms>` on the pinned connection, success only when at
   least one *local* fsync is reported (`aep_core/core/durability.py:318`, `:332`).
2. **Lock keys and the dispatch-authorization key are not barriered.**
   `aep_core/core/locks.py:119-240` and `aep_core/core/intents.py:673` are ordinary
   writes. This is the basis of R1-3.

A real-crash probe exists at `tests/aof_rewind_probe.py`; it is deliberately
not a pytest test because its outcome depends on where the `everysec` boundary
falls. Its observed behaviour is reported in
`reports/phase-report-1b-2026-08-05.md` §C.

### F4 — Delayed or duplicated external responses

- Delay / no response: `TIMEOUT_NO_RESPONSE`,
  `CONNECTION_DROP_MID_TRANSMISSION` (`tests/mock_connector.py:40`), both
  ambiguous at `aep_core/core/intent_workflow.py:607-616`.
- Self-contradictory response: `CONFLICTING_EVIDENCE`, also ambiguous.
- A late effect cannot be recalled (`docs/06-phase2-design.md:266`); recovery
  waits until `reconcile_after` (`aep_core/core/intents.py:836-841`) before drawing
  any conclusion, and never re-dispatches.
- **Duplicate *responses* are still not modelled.** Duplicate *dispatch* is:
  the mock's derived read-back returns `CONFLICT` when more than one call
  exists for one `intent_id` (`tests/mock_connector.py:589-593`).

### F5 — Worker pause (GC / VM stall) past lease expiry

1. **Pre-dispatch preflight** atomically re-checks lock token
   (`aep_core/core/intents.py:617`), `PTTL >= T_client + Buffer_Margin`
   (`aep_core/core/intents.py:618-619`), version (`:624`), status (`:626`), binding
   (`:627-635`), and — Phase 1B — the dispatch authorization (`:639`).
2. **Cancellation of the protected task** by the heartbeat on ownership loss
   (`aep_core/core/locks.py:394-404`), the deadline watchdog (`:406-420`), and the
   hard total-lease cap (`:364-375`).
3. **CAS rejection of the late write** (§3.1).

Residual, stated in the design itself: `docs/06-phase2-design.md:249-252` — a
scheduling gap remains between a successful preflight and transmission.

### Out of model

Byzantine Redis; a provider whose declared evidence contradicts its own effects
(§5.1); catastrophic loss of the Redis host after fsync acknowledgement
(`docs/06-phase2-design.md:292-294`); adversarial writers with direct socket
access (§4 NC-4); compromise of commitment or vault keys.

---

## 3. Properties

### 3.0 Definitions

- **Committed write** — a state write for which the Lua CAS returned `1`
  (`aep_core/core/intents.py:602`, `aep_core/core/storage.py:267`).
- **Durable write** — a committed write for which `WAITAOF` reported at least
  one local AOF fsync on the *same connection* (`aep_core/core/durability.py:332`).
- **Dispatch** — invocation of `connector.mutate`
  (`aep_core/core/intent_workflow.py:574`).
- **Effect** — a mutation applied by the provider; not observable by AEP except
  through connector evidence or read-back.
- **Resolved** — status is `FIRED_CONFIRMED`, `FAILED_CONFIRMED`, or
  `PERMANENTLY_AMBIGUOUS`; `UNRESOLVED_INTENT_STATUSES` is exactly
  `{ABOUT_TO_FIRE, FIRED_UNCONFIRMED}` (`aep_core/core/intents.py:61-63`).
- **Roadmap vocabulary** (`PAPER_ROADMAP.md:36`): CONFIRMED =
  `FIRED_CONFIRMED`; REFUTED = `FAILED_CONFIRMED`; PERMANENTLY_AMBIGUOUS =
  `PERMANENTLY_AMBIGUOUS` (`aep_core/core/intents.py:53-59`). The same three plus
  `RETRY` appear as `ReconciliationOutcome`
  (`aep_core/core/connector_contract.py:56-68`), mapped to statuses at
  `aep_core/core/intent_recovery.py:43-51`.

---

### 3.1 P1 — Fenced state

> **P1.** No committed state write can be superseded and then resurrected by a
> stale writer. Every write to `aep:state:*` is admitted only if, in one atomic
> Lua invocation, (a) the caller's ownership token equals the live value of
> `aep:lock:{execution_id}`, and (b) the stored version equals the caller's
> `expected_version` and the candidate's version equals `expected_version + 1`.

**Enforcement map.**

| Conjunct | Phase 2 intent path | Phase 1 base path |
|---|---|---|
| Single atomic invocation | body `aep_core/core/intents.py:372-603`, assembled `:605`, registered `:722`, invoked from `commit_transition` `:972` | `aep_core/core/storage.py:159-268`, assembled `:270`, registered `:421`, invoked `:505-514` |
| (a) live-token check | `aep_core/core/intents.py:385` | `aep_core/core/storage.py:202` |
| (b) exact expected-version CAS | `aep_core/core/intents.py:399-400` | `aep_core/core/storage.py:244` (creation `:255-257`) |
| The write itself | `aep_core/core/intents.py:601` | `aep_core/core/storage.py:266` |
| Typed rejection | `aep_core/core/intents.py:1026-1073` | `aep_core/core/storage.py:518-556` |

Version-only CAS admits a writer that lost its lease but holds the current
version; token-only checking admits a writer rebasing on a stale read. Both are
checked, and check and `SET` cannot interleave
(`docs/06-phase2-design.md:194-197`).

The same script also freezes, inside the atomic region: `execution_id` and
`schema_version` (`aep_core/core/intents.py:402-403`); the Phase 2 marker
(`:409-414`); every envelope field outside the mutable set (`:428-439`); every
other ledger entry (`:520-524`); the intent's immutable field list (`:533-541`);
append-only transitions with a prefix check (`:542-549`); and the requirement
that the final audit entry names exactly the edge applied (`:566-571`). Ledger
entries can never be deleted (`:487-488`, `:518-519`).

The Phase 1 writer cannot touch Phase 2 state: `-4` when the stored record
carries the marker or a non-empty ledger, or when the candidate introduces
either (`aep_core/core/storage.py:250-252`, `:262-265`, mapped `:547-552`).

**Declared residual windows for P1.**

- **R1-1 — Bypass by any other writer.** P1 constrains two Lua scripts. A plain
  `SET`/`DEL` on `aep:state:*` from any client with socket access is
  unconstrained (`redis/phase2.conf:3-4`, `compose.phase2.yml:9`); the
  "no raw SET" rule is a convention (`docs/02-tech-design.md:1156`).
- **R1-2 — Expiry, not deletion, ends the guarantee.** Each write resets the
  key TTL (`aep_core/core/intents.py:601`). After expiry the record is gone and any
  writer may create version 1 again (`aep_core/core/storage.py:255-257`). Phase 1B
  extended the 31-day floor to cover `PERMANENTLY_AMBIGUOUS`
  (`aep_core/core/intents.py:592-599`), so an escalated record can no longer be
  given a short TTL — but the floor is a floor, not permanence (R3-5).
- **R1-3 — AOF rewind can un-fence. CONFIRMED BY PROBE.** P1 is a statement
  about one monotonic Redis timeline. Under F3 a lost write rewinds `version`,
  and because lock keys are not barriered (§F3) a lease whose release was lost
  can reappear. A writer correctly fenced before the restart then satisfies
  **both** conjuncts.
  *Evidence:* `tests/test_residual_probes.py:46-121` performs a deterministic
  simulated rewind — restoring the exact prior bytes of the state and lock keys
  — and shows a previously-fenced write being accepted;
  `tests/test_residual_probes.py:125-145` pins the mechanism (no `WAITAOF` in
  `aep_core/core/locks.py`). **No local fix exists**: the fix is consensus/HA, an
  explicit non-claim (§4 NC-3). The real-crash probe
  (`tests/aof_rewind_probe.py`) did not observe an actual rewind in the runs
  recorded in the Phase 1B report, so the *frequency* is unmeasured; only the
  *consequence* is established.
- **R1-4 — P1 fences state, never effects** (`docs/02-tech-design.md:1287`).
- **R1-5 — The token is a bearer credential.** Nothing proves the caller
  obtained it from `acquire_lock` (`aep_core/core/intents.py:385`).
- **R1-6 — Raw-state classification precedes the token check**
  (`aep_core/core/intents.py:373-383` then `:385`). A caller without a valid token
  can learn whether stored state is corrupt and can cause a best-effort
  `aep:poison:*` write (`aep_core/core/storage.py:671-691`). No state write results.

---

### 3.2 P2 — Detectable ambiguity

> **P2.** If a *durable* `ABOUT_TO_FIRE` intent exists, then under F1–F5 the
> intent is eventually assigned exactly one of `FIRED_CONFIRMED`,
> `FAILED_CONFIRMED`, or `PERMANENTLY_AMBIGUOUS` — never silently re-dispatched
> and never silently dropped — provided assumptions A1–A3 below hold.

**A. The write-ahead ordering.** In `WriteAheadRunner.execute`
(`aep_core/core/intent_workflow.py:363`):

1. lease acquired with jittered retry (`:375`, `:311-326`);
2. existing state required (`:381-385`);
3. request prepared, vaulted and read back before any intent exists
   (`:397-421`);
4. `NONE → ABOUT_TO_FIRE` CAS **and** the barrier on the same pinned
   connection (`:424-477`);
5. the ack is converted into a Redis authorization (`:481-490`);
6. preflight, which re-checks that authorization (`:496-504`);
7. capability minting (`:530-554`);
8. only then `connector.mutate` (`:574`).

If the barrier fails, the runner makes one fenced attempt to record
`FAILED_CONFIRMED` with evidence `LOCAL_NO_DISPATCH` (`:454-476`), falling back
to leaving `ABOUT_TO_FIRE` for recovery. No bytes were sent, so
`FAILED_CONFIRMED` is sound there.

**B. The durability acknowledgement is now a checked precondition.** This is
the Phase 1B change to P2. The chain is:

1. `confirm_durable_ack` (`aep_core/core/durability.py:161-176`) runs the barrier
   and mints a `DurabilityAck` **only** when it returned `True`.
2. `DurabilityAck` (`aep_core/core/durability.py:75-102`) cannot be constructed
   (`:87-90`), subclassed (`:92-93`), or copied (`:95-99`); it is single-use
   and scope-bound via an HMAC provenance registry
   (`aep_core/core/durability.py:105-155`). The scope is
   `execution_id:intent_id:prepared_state_version`
   (`aep_core/core/durability.py:62-72`), so an ack for one attempt cannot authorise
   another.
3. `IntentLedgerStore.authorize_dispatch`
   (`aep_core/core/intents.py:1081-1162`) **consumes** the ack first (`:1110-1115`),
   then runs `_DISPATCH_AUTHORIZATION_SCRIPT`
   (`aep_core/core/intents.py:649-675`), which re-checks lease, version, status and
   binding digest and writes `aep:dispatch-auth:{exec}:{intent}` (`:673`).
4. The preflight Lua requires that exact value
   (`aep_core/core/intents.py:639`); an absent authorization defaults to a value
   that cannot match (`aep_core/core/intents.py:1186`), so it fails closed with
   `DispatchAuthorizationError` (`aep_core/core/intents.py:136-137`, raised
   `:1223-1226`).

Regression coverage: `tests/test_dispatch_authorization.py` — no authorization
means no dispatch (`:94-113`), a forged value is rejected (`:262-288`), an ack
is single-use (`:61-68`) and scope-bound (`:70-76`), and a barrier that returns
`False` mints nothing (`:78-90`).

**C. Classification at the runner.** Declared success →`FIRED_CONFIRMED`;
declared failure →`FAILED_CONFIRMED`; everything else, including every
exception, →`FIRED_UNCONFIRMED` (`aep_core/core/intent_workflow.py:578-616`). The
resolution is written by the same fenced CAS and barriered on a pinned
connection (`:618-639`).

**D. Classification at recovery.** For an eligible intent
(`aep_core/core/intent_recovery.py:145-151`), under a freshly acquired lease
(`:362-364`) and after re-validating status, version and eligibility
(`:366-377`):

| Observation | Target | Citation |
|---|---|---|
| capability undeclared / unrecognised | `PERMANENTLY_AMBIGUOUS`, **no query** | `aep_core/core/intent_recovery.py:403-422` |
| `NO_READBACK` | `PERMANENTLY_AMBIGUOUS`, no query | `:424-437` |
| `APPLIED` (either querying class) | `FIRED_CONFIRMED` | `aep_core/core/connector_contract.py:196-210` |
| `NOT_APPLIED` + `AUTHORITATIVE_READBACK` | `FAILED_CONFIRMED` | `:212-217` |
| `NOT_APPLIED` + `POSITIVE_ONLY_READBACK` | `PERMANENTLY_AMBIGUOUS` (named violation) | `:218-224` |
| `CONFLICT` | `PERMANENTLY_AMBIGUOUS` | `:226-231` |
| `UNKNOWN`, budget remaining | stay `FIRED_UNCONFIRMED`, backoff | `:233-238`; budget at `aep_core/core/intent_recovery.py:470-506` |
| `UNKNOWN`, budget exhausted | `PERMANENTLY_AMBIGUOUS` | `aep_core/core/intent_recovery.py:478-487` |

A read-back that raises is swallowed to `observation = None`
(`aep_core/core/intent_recovery.py:459-460`), which becomes `UNKNOWN` and therefore
*consumes* budget. `BaseException` is re-raised (`:461-463`).

A stale `ABOUT_TO_FIRE` is first claimed by a durable CAS to
`FIRED_UNCONFIRMED` with reason `orphaned-about-to-fire`
(`aep_core/core/intent_recovery.py:379-396`), which advances the version and
consumes the lease — this is what prevents a late original worker from
persisting its own resolution (`docs/06-phase2-design.md:333-337`).

**E. "Never silently re-dispatched."** Recovery has no reference to
`connector.mutate`; it calls only `read_back`
(`aep_core/core/intent_recovery.py:455-458`). The transition table has no edge back
to `ABOUT_TO_FIRE` — Python set `aep_core/core/intents.py:65-96`, re-checked inside
the atomic script `:449-461`, guard `:99-105`. New attempts are fenced while
the execution is `PAUSED` (`:485`) or any intent is `ABOUT_TO_FIRE`,
`FIRED_UNCONFIRMED`, or `PERMANENTLY_AMBIGUOUS` (`:495-497`), and require the
step's latest attempt to be `FAILED_CONFIRMED` (`:507-509`). Transitions to
`FIRED_UNCONFIRMED` or `PERMANENTLY_AMBIGUOUS` force the execution to `PAUSED`
(`:945-950`).

**F. "Never silently dropped."** At most one unresolved intent per `step_id`
and unique `(step_id, attempt)` pairs, checked over the whole candidate ledger
inside the script (`aep_core/core/intents.py:573-599`), mirrored in Python
(`:345-367`). Deletion is impossible (§3.1). Transitions are append-only
(`:542-549`).

**Assumptions.**

- **A1 — the recovery loop runs.** `run_forever`
  (`aep_core/core/intent_recovery.py:263`) is a library coroutine; the repository
  ships no supervisor (§1.1).
- **A2 — the loop survives its own pass. NOW ENFORCED.** Phase 1A recorded that
  a single corrupt execution aborted the whole pass. `scan_once` now isolates
  per-execution discovery failures (`aep_core/core/intent_recovery.py:213-221`),
  gathers with `return_exceptions=True` (`:241`), and records each isolated
  failure as a `RecoveryScanFailure` (`:68-79`, recorded `:153-190`, bounded by
  `MAX_RETAINED_SCAN_FAILURES` `:57`). `run_forever` survives a wholesale pass
  failure with exponential backoff (`:291-311`) and still propagates
  cancellation (`:289-290`). Regression coverage:
  `tests/test_recovery_fault_isolation.py:41-79` (one corrupt key, N healthy
  ones all processed), `:104-131` (unregistered connector isolated),
  `:157-185` (`run_forever` survives), `:188-206` (cancellation still
  propagates).
- **A3 — the lease is eventually obtainable.** `_acquire` returns `None` after
  the configured attempts (`aep_core/core/intent_recovery.py:321-333`); progress
  depends on a later pass.

*(Phase 1A's assumption A4 — "a connector config is registered, else the pass
dies" — is retired: a missing config now raises inside one gathered task and is
isolated by A2.)*

**Declared residual windows for P2.**

- **R2-1 — the pre-acknowledgement window.** Between the CAS reply and the
  `WAITAOF` acknowledgement the intent exists in memory but may not be on disk.
  Because dispatch is gated on the barrier *and* on the authorization it mints
  (§3.2 B), losing this write implies no dispatch occurred; the window costs a
  lost record of a non-event, not an undetected effect.
- **R2-2 — loss after fsync acknowledgement.** Catastrophic host or storage
  loss can destroy an acknowledged intent (`docs/06-phase2-design.md:292-294`).
- **R2-3 — false-positive ambiguity is the price.** A crash after a durable
  `ABOUT_TO_FIRE` but before transmission yields an intent recovery must treat
  as ambiguous even though no effect exists
  (`docs/06-phase2-design.md:280-281`). This inflates the *known-ambiguity*
  rate; it never inflates the undetected-duplicate rate.
- **R2-4 — classification inherits connector truthfulness.** `FIRED_CONFIRMED`
  and `FAILED_CONFIRMED` at the runner come from declared evidence
  (`aep_core/core/intent_workflow.py:591-597`) with no independent verification.
- **R2-5 — the capability declaration is self-asserted.** The contract is now
  typed and validated for *shape* (`aep_core/core/connector_contract.py:118-140`),
  but nothing verifies that a connector claiming `AUTHORITATIVE_READBACK`
  really can prove absence.
- **R2-6 — `PERMANENTLY_AMBIGUOUS` is a state, not a notification** (§5.2).
- **R2-7 — the authorization proves *a barrier ran in this process*, not that
  Redis fsynced.** Redis exposes no way for a Lua script to verify that a
  previous `WAITAOF` succeeded, so a complete proof is impossible. What is
  enforced is: the authorization key is written by exactly one script
  (`aep_core/core/intents.py:649-675`), that script is reachable only through
  `authorize_dispatch`, and `authorize_dispatch` first consumes an
  unforgeable, single-use, scope-bound `DurabilityAck`
  (`aep_core/core/intents.py:1110-1115`). Two gaps remain and are declared:
  1. a principal with direct Redis access can write the authorization key
     itself (the same trust-domain gap as R1-1);
  2. a caller inside this process could compose `RequestBindingService.verify`
     with a connector directly, bypassing the runner entirely — the capability
     object is derived from the persisted binding, not from the fsync ack
     (`aep_core/core/request_binding.py:1489-1503`).
  The authorization key is also **not itself barriered** (`aep_core/core/intents.py:673`
  is an ordinary `SET`), so an AOF rewind can lose it; the effect is
  conservative (a later preflight then refuses to dispatch).
- **R2-8 — single-use is by attempt, not by consumption.** The preflight
  *verifies* the authorization but does not delete it
  (`aep_core/core/intents.py:639`); it expires by TTL (`:673`). Replay is
  nevertheless fenced because the preflight also requires status
  `ABOUT_TO_FIRE` and version `== prepared_state_version` (`:624-626`), both of
  which change once the attempt resolves. The conservative alternative —
  consuming the key inside the preflight — was rejected in Phase 1B because it
  would make the documented read-only preflight
  (`docs/06-phase2-design.md:240-247`) a writer.

---

### 3.3 P3 — Fail-closed liveness bound

> **P3.** Automated reconciliation of one intent terminates within a
> configurable attempt budget and a configurable duration budget, after which
> the intent is placed in a terminal automated state and the execution is
> withdrawn from normal scheduling.

**Budgets.** `max_reconciliation_attempts` (default 8) and
`max_reconciliation_duration_seconds` (default 24 h)
(`aep_core/core/intent_workflow.py:78-79`), both required positive (`:106-112`).
Backoff is full-jitter over `min(base·2^(n−1), cap)` with base 5 s and cap
300 s (`:80-81`, `:126-133`), sampled at
`aep_core/core/intent_recovery.py:492-495`.

**Termination test.** `aep_core/core/intent_recovery.py:478-483`; on exhaustion the
target becomes `PERMANENTLY_AMBIGUOUS` with reason
`reconciliation-attempt-or-duration-limit` (`:484-487`). Attempt counting is
monotone and re-checked inside the atomic script: a
`FIRED_UNCONFIRMED → FIRED_UNCONFIRMED` edge must increment `attempt_count` by
exactly one (`aep_core/core/intents.py:561-563`), and the first entry must start at
zero with `next_check_at >= reconcile_after` (`:556-560`). The duration budget
is measured from `reconcile_after`, so a long recovery outage does not extend
it.

**Ejection.** On `PERMANENTLY_AMBIGUOUS`: no longer eligible
(`aep_core/core/intent_recovery.py:145-151`); execution status becomes `PAUSED`
(`aep_core/core/intents.py:945-950`); no new intent may be created
(`aep_core/core/intents.py:485`, `:495-497`); operator resolution is possible only
via `PERMANENTLY_AMBIGUOUS → FIRED_CONFIRMED`/`FAILED_CONFIRMED`
(`aep_core/core/intents.py:87-94`; Lua `:458-459`), requiring the lease and exact
version like any other transition.

**Retention floor.** A ledger containing an `ABOUT_TO_FIRE`,
`FIRED_UNCONFIRMED`, or `PERMANENTLY_AMBIGUOUS` record forces a ≥ 31-day state
TTL (`aep_core/core/intents.py:592-599`, constant `:49`). Runner and recovery refuse
to start unless the store TTL covers the maximum reconciliation duration plus a
7-day operator window (`aep_core/core/intent_workflow.py:195-203`;
`aep_core/core/intent_recovery.py:127-134`).

**Declared residual windows for P3.**

- **R3-1 — conditional on the loop running.** A1 still applies. A2 no longer
  does: one bad execution no longer stops the others.
- **R3-2 — the budget is consulted only on the `UNKNOWN` branch.** Every other
  observation resolves immediately, so this is not a gap in practice, but the
  bound is not a global watchdog over the intent's lifetime.
- **R3-3 — lease contention does not consume budget**
  (`aep_core/core/intent_recovery.py:321-333`, `:363-364`).
- **R3-4 — "escalation" is not implemented** (§5.2).
- **R3-5 — escalated records still expire. CONFIRMED BY PROBE.** Phase 1B
  closed the sharper half: the retention floor now covers
  `PERMANENTLY_AMBIGUOUS`, so the escalating write can no longer shorten
  retention to seconds (`aep_core/core/intents.py:592-599`; regression
  `tests/test_residual_probes.py:232-245`). What remains is inherent to
  TTL-based retention: after the floor elapses, Redis deletes the record and
  the escalation evidence is gone without an operator having acted. *Evidence:*
  `tests/test_residual_probes.py:207-228` asserts the TTL is positive and
  bounded.
- **R3-6 — recovery discovery is not memory-bounded.** `scan_once` still
  accumulates every eligible `(execution_id, intent_id)` pair before acting
  (`aep_core/core/intent_recovery.py:202-236`); raised in
  `docs/07-phase2-gap-audit.md:33` and still true. The isolated-failure list is
  bounded (`aep_core/core/intent_recovery.py:57`), the candidate list is not.

---

### 3.4 Summary

| Property | Enforced by | Enforcement kind | Principal residual |
|---|---|---|---|
| P1 Fenced state | `aep_core/core/intents.py:372-603` (`:385`, `:399-400`, `:601`); `aep_core/core/storage.py:159-268` | Atomic, in-Redis | Bypass by any direct writer (R1-1); AOF rewind (R1-3, probe-confirmed) |
| P2 Detectable ambiguity | ordering `aep_core/core/intent_workflow.py:424-574`; ack chain `aep_core/core/durability.py:161-176` → `aep_core/core/intents.py:1081-1162` → `:649-675` → `:639`; recovery `aep_core/core/intent_recovery.py:403-521`; table `aep_core/core/intents.py:449-461` | Atomic for the state machine and for the authorization check; **in-process** for the ack itself | Cannot prove fsync to Lua (R2-7); connector truthfulness (R2-4) |
| P3 Fail-closed bound | `aep_core/core/intent_recovery.py:478-487`; budgets `aep_core/core/intent_workflow.py:78-79` | Per-intent, conditional on progress | No escalation mechanism (R3-4); escalated records expire (R3-5, probe-confirmed) |

---

## 4. Non-claims

| # | Non-claim | Why out of scope |
|---|---|---|
| NC-1 | **Exactly-once external execution.** | Redis and a legacy provider share no transaction coordinator (`docs/06-phase2-design.md:264`). The protocol converts this into declared ambiguity. |
| NC-2 | **Duplicate prevention.** AEP prevents *automatic* duplicates; it cannot prevent an effect the provider applied from a request it already received. | A dispatched request cannot be recalled (`docs/06-phase2-design.md:266`). |
| NC-3 | **HA, consensus, or split-brain immunity.** | Single instance; the lock is a lease (`docs/01-hld.md:24-25`, `aep_core/core/locks.py:9-13`). This is also why R1-3 has no local fix. |
| NC-4 | **A hardened trust domain.** | `protected-mode no`, no ACL (`redis/phase2.conf:3-4`); "no raw SET" is convention (`docs/02-tech-design.md:1156`). Any principal reaching the socket can violate P1 (R1-1) and can forge a dispatch authorization (R2-7). |
| NC-5 | **Durability beyond one local AOF fsync.** | `WAITAOF 1 0` requires one *local* fsync (`aep_core/core/durability.py:318`, `:332`); `WAIT` is explicitly not a substitute (`docs/06-phase2-design.md:228-231`). |
| NC-6 | **Recovery of an effect whose intent was lost with the host.** | `docs/06-phase2-design.md:292-294`. |
| NC-7 | **Authoritative negative inference from eventually consistent APIs.** | `NOT_APPLIED` is honoured only from `AUTHORITATIVE_READBACK` (`aep_core/core/connector_contract.py:212-217`); positive-only absence is a named violation (`:218-224`). |
| NC-8 | **Compensation / rollback of a confirmed effect.** | Not implemented; routed to a separate workflow (`docs/06-phase2-design.md:411-413`). |
| NC-9 | **Operator alerting or incident delivery.** | Not implemented (§5.2). Recovery now records isolated scan failures and can call a `scan_failure_alert` (`aep_core/core/intent_recovery.py:153-190`), but nothing alerts on `PERMANENTLY_AMBIGUOUS`. |
| NC-10 | **Unbounded ledger retention.** | TTL-based (R1-2, R3-5); `docs/06-phase2-design.md:409-410`. |
| NC-11 | **Production readiness.** | `PRODUCTION` mode fails closed: no production vault or connector exists (`aep_core/core/intent_workflow.py:284-301`, `aep_core/core/request_vault.py:1-6`). Measurement runs in `EVALUATION` mode, whose weaker properties are declared in §1.7. |
| NC-12 | **Machine-checked proofs.** | Argued from code paths, not model-checked. `PAPER_ROADMAP.md:141` schedules TLA+/Hypothesis work as Phase 3A. |

---

## 5. Enforcement gaps: designed but not enforced in `aep_core/core/`

*(Phase 1A's §5.1 "capability contract unvalidated" and §5.3 "recovery loop not
fault-isolated" are closed; see §1.5(b) and assumption A2.)*

**5.1 Provider evidence is trusted without corroboration.** A connector
returning `DEFINITIVE_SUCCESS` yields `FIRED_CONFIRMED` and one returning
`DEFINITIVE_FAILURE` yields `FAILED_CONFIRMED`
(`aep_core/core/intent_workflow.py:591-597`) with no read-back cross-check. The
design's requirement for a published per-connector response-classification
table (`docs/06-phase2-design.md:174-176`) is expressed only as the two policy
frozensets (`aep_core/core/intent_workflow.py:84-90`).

**5.2 There is no escalation mechanism.** `docs/06-phase2-design.md:376-379`
requires a critical incident on `PERMANENTLY_AMBIGUOUS` and a warning on the
first `FIRED_UNCONFIRMED`. `aep_core/core/` emits neither. Phase 1B added
`scan_failure_alert` for *isolated scan failures* only
(`aep_core/core/intent_recovery.py:124`, `:180-190`) and `recovery_lag_alert`
for pass-duration SLO (`:123`, `:312-316`). Neither fires on an intent outcome.
"Ejects to operator escalation" in P3 therefore means "reaches a terminal
automated state and pauses the execution", nothing more.

**5.3 The operator is unauthenticated.** `actor` is validated only as a bounded
safe identifier (`aep_core/core/intents.py:177-180`). Any caller holding the lease
and current version can drive `PERMANENTLY_AMBIGUOUS → FAILED_CONFIRMED` and
re-enable new attempts (`aep_core/core/intents.py:507-509`). The design's audited
duplicate-risk override (`docs/06-phase2-design.md:140-143`) is **not
implemented**: the script rejects creation of any intent carrying a
`risk_acceptance_id` (`aep_core/core/intents.py:506`).

**5.4 Crash injection is in-process only.** §F1. No separate-process `SIGKILL`
in the suite, no partition test. Phase 1B added a real-crash *probe*
(`tests/aof_rewind_probe.py`) but it is a manual experiment, not coverage.

**5.5 No production vault or connector exists.** §1.7, NC-11.

---

## 6. Evidence index

| Artifact | Role |
|---|---|
| `aep_core/core/intents.py:372-603` | Intent CAS script — enforcement point for P1 and the state machine |
| `aep_core/core/intents.py:608-641` | Pre-dispatch preflight, including the Phase 1B authorization check (`:639`) |
| `aep_core/core/intents.py:649-675` | Dispatch-authorization script (Phase 1B) |
| `aep_core/core/intents.py:1081-1162` | `authorize_dispatch`: consumes the ack, then writes the authorization |
| `aep_core/core/intents.py:65-96`, `:449-461` | Exhaustive transition table, Python and Lua copies |
| `aep_core/core/durability.py:62-176` | `dispatch_scope`, `DurabilityAck`, the provenance boundary, and the sole mint point |
| `aep_core/core/durability.py:229-332` | WAITAOF capability validation and the fsync barrier |
| `aep_core/core/connector_contract.py` | The production response-class contract and total classification |
| `aep_core/core/intent_recovery.py:192-319` | Fault-isolated scan pass and surviving `run_forever` |
| `aep_core/core/intent_recovery.py:347-521` | Claim-and-reconcile, typed-contract classification |
| `aep_core/core/intent_workflow.py:39-52`, `:226-309` | `DispatchMode` and the composition gate |
| `aep_core/core/request_vault.py:321-451` | The evaluation vault |
| `aep_core/core/storage.py:159-268` | Phase 1 base CAS, including Phase 2 state protection |
| `aep_core/core/locks.py:35-70`, `:119-240`, `:244-432` | Lease primitives and the capped auto-renewing lease |
| `tests/test_residual_probes.py` | Executable probes for R1-3 and R3-5 |
| `tests/aof_rewind_probe.py` | Real-crash AOF probe (manual experiment) |
| `redis/phase2.conf`, `compose.phase2.yml` | AOF configuration, image digest, loopback publication |
| `docs/06-phase2-design.md:178-294`, `:345-413` | Atomicity/durability boundary, crash table, capability contract, non-goals |
| `docs/07-phase2-gap-audit.md` | Prior adversarial audit; §5 records which findings remain open |
