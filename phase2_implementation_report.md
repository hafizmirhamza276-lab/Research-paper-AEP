# AEP Phase 2 implementation report

Date: 2026-07-28  
Design baseline: `docs/06-phase2-design.md`  
Test backend: `redis://127.0.0.1:6381/15`, Redis `7.2.5`, AOF enabled  
Final result: **218 passed**, including the Redis 7.2 AOF integration suite

## Scope and file changes

Implemented in new Phase 2 modules:

- `src/core/intents.py`
  - Exact persisted intent states and exhaustive transition table.
  - Frozen typed models for the intent, audit entries, observations, and
    reconciliation progress.
  - Strict `Phase2ExecutionState` view over the Phase 1-compatible execution
    envelope.
  - Atomic Redis Lua intent CAS and atomic read-only preflight.
  - Same-script enforcement of lock token, expected version, consecutive
    version increment, legal transition, immutable identity fields,
    append-only audit history, no deletion, no `intent_id` reuse, unique and
    increasing attempt numbers, minimum unresolved TTL, and at most one
    `ABOUT_TO_FIRE`/`FIRED_UNCONFIRMED` intent per `step_id`.
- `src/core/durability.py`
  - `DurabilityBarrier` protocol.
  - Immediate `FakeDurabilityBarrier`, explicitly marked test-only.
  - Production `RealWaitAofDurabilityBarrier` using exactly
    `WAITAOF 1 0 <timeout-ms>`.
  - Fail-closed startup validation for Redis 7.2+, active AOF, the selected
    durability mode, and advertised `WAITAOF` command support.
  - Strict response validation: only a well-formed response with at least one
    local AOF fsync acknowledgment returns `True`.
- `src/core/intent_workflow.py`
  - Lease acquisition with bounded full-jitter contention backoff.
  - Write-ahead intent CAS and same-pinned-connection durability call.
  - Production dispatch gate that performs durability startup validation
    before lease acquisition or intent creation and rejects test-only barriers
    unless the caller explicitly enables the test harness path.
  - Atomic lease-TTL/version/intent-status preflight.
  - Exactly one connector mutation call with explicit response-class
    declarations and ambiguity as the default.
  - Fenced resolution CAS and durability barrier.
  - Fail-closed no-dispatch handling when the initial durability barrier does
    not acknowledge.
  - Per-connector defaults of 8 reconciliation attempts, 24 hours, and
    full-jitter capped exponential backoff from 5 to 300 seconds; all are
    constructor-overridable.
- `src/core/intent_recovery.py`
  - Cursor-based `SCAN MATCH aep:state:* COUNT 500` discovery with bounded
    concurrency.
  - Continuous 30-second pass loop and five-minute recovery-lag alert hook.
  - Lease-fenced stale `ABOUT_TO_FIRE` claim.
  - Read-only handling of `AUTHORITATIVE_READBACK`,
    `POSITIVE_ONLY_READBACK`, and `NO_READBACK`.
  - Persisted attempt counts, timestamps, next-check times, bounded backoff,
    attempt/duration exhaustion, and permanent ambiguity.

Added tests:

- `tests/test_phase2_state_machine.py`
- `tests/test_phase2_durability.py`
- `tests/test_phase2_runner.py`
- `tests/test_phase2_recovery.py`
- `tests/test_phase2_waitaof_integration.py`

Added reproducible Redis test/development configuration:

- `compose.phase2.yml`
- `redis/phase2.conf`

`tests/mock_connector.py` was not modified. `src/core/storage.py` and
`src/core/locks.py` were not modified. Phase 2 calls the existing normal
validated/quarantine read path and uses the existing lock manager, but keeps
its transition CAS and workflow in new modules. No Phase 1 implementation or
test was changed.

## Atomicity and durability behavior implemented

The unresolved-intent check is authoritative inside the same Lua invocation
that performs `SET`; any Python-side typed validation is only an earlier
fast-fail. There is no separate check-then-write race.

The workflow obtains a pinned Redis client for each intent/resolution CAS and
passes that same connection to `DurabilityBarrier.confirm_durable`.
`RealWaitAofDurabilityBarrier` issues `WAITAOF 1 0 <timeout-ms>` on that client
and authorizes dispatch only when the local-fsync count is at least one. The
Redis 7.2 integration test records the server `CLIENT ID` after each CAS and at
the barrier and proves the IDs match and the order is CAS, barrier, provider.

The fake barrier remains useful for deterministic crash orchestration only and
is not disk-durability evidence. Production runner construction defaults to
rejecting it. The provider mutation remains outside Redis atomicity and is
never replayed by recovery.

## Test evidence by stage

The initial historical commands in the stage sections below used
`REDIS_URL=redis://127.0.0.1:6380/15`, set `PYTHONDONTWRITEBYTECODE=1`, and
disabled the pytest cache provider. The Redis 7.2 follow-up has its own exact
commands and results later in this report.

### Stage 1 — state model and state machine

The first Redis checkpoint was:

```text
collected 21 items
...
============================= 21 passed in 0.34s ==============================
```

After expanding the transition table into every legal and every illegal edge,
the Stage 1 plus Stage 2 checkpoint was:

```text
collected 54 items
...
tests/test_phase2_state_machine.py::test_second_unresolved_intent_for_step_rejected_by_same_lua_write PASSED [ 94%]
tests/test_phase2_durability.py::test_fake_durability_barrier_acknowledges_without_redis_command PASSED [ 96%]
tests/test_phase2_durability.py::test_fake_durability_barrier_rejects_nonpositive_timeout PASSED [ 98%]
tests/test_phase2_durability.py::test_real_waitaof_barrier_is_explicitly_deferred PASSED [100%]
============================= 54 passed in 0.55s ==============================
```

This includes all 10 legal persisted-target edges, all 20 illegal
persisted-target edges, direct `NONE -> FIRED_CONFIRMED` rejection, deletion
rejection, `intent_id` reuse rejection, and the Lua-local unresolved-intent
uniqueness check.

### Stage 2 — durability abstraction

The three durability contract cases are included in the 54-test output above.
The real implementation test requires—and observes—the explicit
`NotImplementedError`; no WAITAOF command is sent.

### Stage 3 — write-ahead runner

The runner checkpoint before the final audit was:

```text
collected 21 items
...
tests/test_phase2_runner.py::test_runner_classifies_connector_response_once[CONFLICTING_EVIDENCE-True-FIRED_UNCONFIRMED] PASSED [100%]
============================= 21 passed in 0.76s ==============================
```

The later full suite also includes the added policy-default, failed-first-
durability-barrier/no-dispatch, and applied mid-transmission connection-drop
regression tests.

#### Applied mid-transmission connection-drop regression

Coverage correction: the runner's existing parameterized matrix exercised
`CONNECTION_DROP_MID_TRANSMISSION` with hidden
`mutation_applied=False`, while `tests/test_mock_connector.py` exercised both
hidden outcomes only at the connector boundary. The dedicated integrated test
`test_runner_applied_mid_transmission_drop_stays_unconfirmed_without_replay`
now executes the missing `mutation_applied=True` outcome through
`WriteAheadRunner`; the existing `False` runner case remains unchanged.

The regression asserts all of the following against the connector oracle,
runner-visible result, and a fresh Redis read:

- the oracle contains exactly one mutation attempt with mode
  `CONNECTION_DROP_MID_TRANSMISSION`;
- hidden `mutation_applied` is `True`, but caller evidence is `AMBIGUOUS`;
- the connector exception has no `mutation_applied` attribute, and neither the
  returned nor persisted intent serializes hidden mutation truth;
- both the returned and Redis-persisted statuses are `FIRED_UNCONFIRMED`;
- neither the persisted transition history nor raw Redis state contains
  `FIRED_CONFIRMED` or `FAILED_CONFIRMED`; and
- the oracle call log remains unchanged after runner completion and the Redis
  verification read, proving that no replay or second mutation occurred in
  this execution.

The test was added before any production change and passed on its first
execution, so it revealed a coverage gap rather than a production defect.
No production code was modified.

Exact validation commands and results:

The first sandboxed invocation of the focused command exited 1 before test
collection because pytest could not create a temporary capture file
(`FileNotFoundError: No usable temporary directory found`). The identical
command was then run outside the read-only filesystem sandbox and produced the
test result below; Redis was available throughout.

```powershell
$env:REDIS_URL='redis://127.0.0.1:6380/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_runner.py::test_runner_applied_mid_transmission_drop_stays_unconfirmed_without_replay -p no:cacheprovider -vv
```

```text
collected 1 item
tests/test_phase2_runner.py::test_runner_applied_mid_transmission_drop_stays_unconfirmed_without_replay PASSED [100%]
============================== 1 passed in 0.30s ==============================
```

```powershell
$env:PYTHONPYCACHEPREFIX='C:\Users\DELL\AppData\Local\Temp\aep-phase2-pycompile'; py -3 -m py_compile src\core\intent_workflow.py src\core\intents.py tests\mock_connector.py tests\test_phase2_runner.py
```

Result: exit code 0 with no output.

```powershell
$env:REDIS_URL='redis://127.0.0.1:6380/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_runner.py tests/test_mock_connector.py -p no:cacheprovider -vv
```

```text
collected 68 items
...
tests/test_phase2_runner.py::test_runner_applied_mid_transmission_drop_stays_unconfirmed_without_replay PASSED [ 33%]
...
============================= 68 passed in 1.96s ==============================
```

### Stage 4 — recovery and reconciliation

```text
collected 17 items
tests/test_phase2_recovery.py::test_recovery_crash_boundary_preserves_required_state_and_evidence[DURING_RECOVERY_BEFORE_CLAIM_CAS] PASSED
tests/test_phase2_recovery.py::test_recovery_crash_boundary_preserves_required_state_and_evidence[AFTER_RECOVERY_CLAIM_BEFORE_READBACK] PASSED
tests/test_phase2_recovery.py::test_recovery_crash_boundary_preserves_required_state_and_evidence[AFTER_READBACK_BEFORE_RECOVERY_RESOLUTION_CAS] PASSED
tests/test_phase2_recovery.py::test_recovery_crash_boundary_preserves_required_state_and_evidence[DURING_RECOVERY_RESOLUTION_CAS] PASSED
tests/test_phase2_recovery.py::test_recovery_crash_boundary_preserves_required_state_and_evidence[AFTER_RECOVERY_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER] PASSED
tests/test_phase2_recovery.py::test_recovery_crash_boundary_preserves_required_state_and_evidence[DURING_RECOVERY_RESOLUTION_DURABILITY_BARRIER] PASSED
tests/test_phase2_recovery.py::test_reconciliation_capability_result_mapping[AUTHORITATIVE_READBACK-APPLIED-FIRED_CONFIRMED] PASSED
tests/test_phase2_recovery.py::test_reconciliation_capability_result_mapping[AUTHORITATIVE_READBACK-NOT_APPLIED-FAILED_CONFIRMED] PASSED
tests/test_phase2_recovery.py::test_reconciliation_capability_result_mapping[AUTHORITATIVE_READBACK-UNKNOWN-FIRED_UNCONFIRMED] PASSED
tests/test_phase2_recovery.py::test_reconciliation_capability_result_mapping[POSITIVE_ONLY_READBACK-APPLIED-FIRED_CONFIRMED] PASSED
tests/test_phase2_recovery.py::test_reconciliation_capability_result_mapping[POSITIVE_ONLY_READBACK-UNKNOWN-FIRED_UNCONFIRMED] PASSED
tests/test_phase2_recovery.py::test_reconciliation_capability_result_mapping[AUTHORITATIVE_READBACK-CONFLICT-PERMANENTLY_AMBIGUOUS] PASSED
tests/test_phase2_recovery.py::test_no_readback_becomes_permanently_ambiguous_without_query PASSED
tests/test_phase2_recovery.py::test_reconciliation_attempt_limit_is_configurable_and_enforced PASSED
tests/test_phase2_recovery.py::test_scanner_finds_only_eligible_ambiguous_execution PASSED
tests/test_phase2_recovery.py::test_late_original_worker_is_fenced_after_recovery_claim PASSED
tests/test_phase2_recovery.py::test_recovery_never_repeats_mutation_and_only_reads_back PASSED
============================= 17 passed in 0.56s ==============================
```

### Unified 22 crash boundaries

The exact verbose selection produced:

```text
collected 39 items / 17 deselected / 22 selected
test_runner_crash_boundary_preserves_required_state_and_evidence[BEFORE_LEASE_ACQUISITION] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[AFTER_LEASE_ACQUISITION_BEFORE_INTENT_CAS] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[DURING_INTENT_CAS] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[DURING_REQUEST_TRANSMISSION] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[WHILE_WAITING_WITHOUT_RESPONSE] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[AFTER_CONCLUSIVE_SUCCESS_BEFORE_RESOLUTION_CAS] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[AFTER_CONCLUSIVE_FAILURE_BEFORE_RESOLUTION_CAS] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[AFTER_AMBIGUOUS_RESPONSE_BEFORE_RESOLUTION_CAS] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[DURING_RESOLUTION_CAS] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[AFTER_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[DURING_RESOLUTION_DURABILITY_BARRIER] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[AFTER_DURABLE_CONFIRMED_RESOLUTION_BEFORE_LEASE_RELEASE] PASSED
test_runner_crash_boundary_preserves_required_state_and_evidence[AFTER_DURABLE_FIRED_UNCONFIRMED_BEFORE_LEASE_RELEASE] PASSED
test_recovery_crash_boundary_preserves_required_state_and_evidence[DURING_RECOVERY_BEFORE_CLAIM_CAS] PASSED
test_recovery_crash_boundary_preserves_required_state_and_evidence[AFTER_RECOVERY_CLAIM_BEFORE_READBACK] PASSED
test_recovery_crash_boundary_preserves_required_state_and_evidence[AFTER_READBACK_BEFORE_RECOVERY_RESOLUTION_CAS] PASSED
test_recovery_crash_boundary_preserves_required_state_and_evidence[DURING_RECOVERY_RESOLUTION_CAS] PASSED
test_recovery_crash_boundary_preserves_required_state_and_evidence[AFTER_RECOVERY_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER] PASSED
test_recovery_crash_boundary_preserves_required_state_and_evidence[DURING_RECOVERY_RESOLUTION_DURABILITY_BARRIER] PASSED
====================== 22 passed, 17 deselected in 0.71s ======================
```

Each crash-boundary test checks the stored state permitted by section 7.
Runner crash cases compare confirmed states against caller-visible evidence
from the hidden ground-truth log. The separate integrated connection-drop
regression additionally proves that hidden applied truth remains ambiguous and
unconfirmed through runner completion and Redis persistence, without replay.
Recovery cases assert that no mutation was invoked and that no confirmed state
exists before read-back evidence.

### Initial complete suite before real WAITAOF

```text
============================= test session starts =============================
platform win32 -- Python 3.13.1, pytest-8.3.3, pluggy-1.6.0
rootdir: C:\Users\DELL\Desktop\personal\Research-paper-20260727T182111Z-1-001\Research-paper
configfile: pyproject.toml
plugins: anyio-4.13.0, langsmith-0.7.9, asyncio-1.3.0, cov-7.0.0, mock-3.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 190 items

tests\test_cas_write.py ...........                                      [  5%]
tests\test_get_migration.py .........                                    [ 10%]
tests\test_lease.py ..........                                           [ 15%]
tests\test_locks.py .........                                            [ 20%]
tests\test_mock_connector.py ........................................... [ 43%]
.                                                                        [ 43%]
tests\test_phase2_durability.py ...                                      [ 45%]
tests\test_phase2_recovery.py .................                          [ 54%]
tests\test_phase2_runner.py ........................                     [ 66%]
tests\test_phase2_state_machine.py ..................................... [ 86%]
..............                                                           [ 93%]
tests\test_races.py ....                                                 [ 95%]
tests\test_uuid_validation.py ......                                     [ 98%]
tests\test_version_range.py ..                                           [100%]

============================ 190 passed in 17.24s =============================
```

Pytest also emitted the pre-existing `pytest-asyncio` deprecation warning that
`asyncio_default_fixture_loop_scope` is unset. It did not affect test results.

## Section 11 acceptance checklist

| Acceptance criterion | Status | Evidence / remaining gap |
|---|---|---|
| Every connector declares response classification and reconciliation capability | **Partially met** | `ConnectorPolicy` requires disjoint definitive success/failure declarations and the mock connector declares one of the three recovery capabilities. Only the mock connector exists in this implementation; there is no production connector registry/startup audit yet. |
| Redis deployment supports an approved local durability barrier | **Met for the checked-in test/development deployment; production remains startup-gated** | The pinned Redis 7.2.5 Compose service enables AOF with `appendfsync everysec`; startup rejects older Redis, disabled AOF, unsupported modes, missing `WAITAOF`, or failed capability commands. Each production deployment must pass the same validation. |
| Same-connection CAS plus WAITAOF is guaranteed by the client design | **Met** | The runner passes the pinned CAS client directly to `WAITAOF 1 0 <timeout-ms>`. The Redis integration test proves matching `CLIENT ID` values for both the intent and resolution CAS/barrier pairs. |
| Scheduler, runner, resolver, and operator paths enforce the transition table | **Partially met** | The Lua CAS, runner, and resolver enforce it. Unresolved states are marked `PROCESSING`/`PAUSED`; no separate production scheduler integration or authenticated manual operator-resolution API exists yet. |
| Scanner and retention satisfy the recovery SLO | **Partially met** | COUNT 500 scanning, bounded concurrency, 30-second loop, five-minute alert hook, 31-day minimum TTL, and custom-window retention validation exist. No production load/SLO test or deployed alert sink has validated completion within five minutes. |
| Every section 7 crash point has adversarial tests | **Met** | All 22 independently armed boundaries passed against real Redis and the unchanged mock connector harness. |
| Documentation and telemetry say detectable ambiguity + fail-closed, never exactly once | **Partially met** | The design, module documentation, exceptions, and this report use the bounded claim. A production telemetry/dashboard integration does not yet exist. |

## Residual gaps and non-goals

- `WAITAOF` proves acknowledgment to one Redis instance's local AOF only. It
  does not provide replication, survive catastrophic host/storage loss, or
  make Redis and the provider one transaction.
- There is no exactly-once guarantee, distributed transaction, provider-side
  recall, HA/consensus, or protection from catastrophic loss of the Redis
  host/storage.
- No production connector, scheduler, operator dashboard/incident sink, or
  authenticated manual resolution endpoint was added.
- The scanner has the designed defaults and alert hook, but its five-minute
  SLO has not been load-tested in a deployment.
- `FakeDurabilityBarrier` proves control-flow ordering only. It must never be
  treated as production durability evidence.

## Production local durability barrier follow-up

### Reproducible Redis configuration

The test/development service is defined by `compose.phase2.yml` and
`redis/phase2.conf` with:

- image
  `redis:7.2.5-alpine@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44`;
- loopback-only host publication `127.0.0.1:6381:6379`;
- 16 logical databases, with tests restricted to DB 15;
- a named `/data` volume;
- `appendonly yes`;
- `appendfsync everysec`;
- `appenddirname appendonlydir`;
- RDB snapshots disabled with `save ""`; and
- a health check using `redis-cli -n 15 PING`.

Exact startup and capability commands:

```powershell
docker compose -f compose.phase2.yml up -d --wait
redis-cli -h 127.0.0.1 -p 6381 -n 15 PING
redis-cli -h 127.0.0.1 -p 6381 -n 15 INFO server
redis-cli -h 127.0.0.1 -p 6381 -n 15 CONFIG GET appendonly appendfsync dir databases
redis-cli -h 127.0.0.1 -p 6381 -n 15 COMMAND INFO WAITAOF
```

Observed configuration:

```text
PONG
redis_version:7.2.5
appendfsync everysec
appendonly yes
databases 16
dir /data
```

Tests never call `FLUSHALL`. The shared fixture scans and deletes only
`aep:*` keys after verifying the real client is connected to DB 15.

### Test-first evidence

The new regression tests were added before production implementation. The
first focused command was:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_durability.py tests/test_phase2_waitaof_integration.py -p no:cacheprovider -q
```

It failed during collection, as expected, before production changes:

```text
ImportError: cannot import name 'DurabilityBarrierError' from 'src.core.durability'
ERROR tests/test_phase2_durability.py
1 error in 0.51s
```

The scripted unit tests exercise acknowledged, zero-local-fsync, malformed,
timeout, connection-loss, command-failure, unsupported-version, disabled-AOF,
missing-command, unsupported-mode, and unvalidated-barrier cases. Exact focused
result:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_durability.py -p no:cacheprovider -q
```

```text
25 passed in 0.16s
```

The production dispatch-gate regressions prove a fake barrier and a rejected
startup capability check produce no intent and no provider call:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_runner.py -p no:cacheprovider -q
```

```text
26 passed in 1.08s
```

The first integration run against the checked-in Compose environment produced
`1 failed, 3 passed in 7.61s`: the cold first fsync exhausted the test's
approximately 990 ms lease headroom, and the unchanged production preflight
correctly prevented dispatch. Only the integration policy's lease TTL was
increased from 16 to 30 seconds. The rerun was:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_waitaof_integration.py -p no:cacheprovider -q
```

```text
4 passed in 7.09s
```

Those four tests prove:

1. intent CAS and its `WAITAOF`, and resolution CAS and its `WAITAOF`, use the
   same respective pinned connection and precede the provider call;
2. an acknowledged real barrier permits the one provider dispatch;
3. a real `WAITAOF` command failure after validation results in zero provider
   calls; and
4. the complete intent with its confirmed resolution survives a controlled
   restart of the Redis container and the provider mutation count remains one.

The complete suite with integration explicitly enabled was:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests -p no:cacheprovider -q
```

```text
218 passed in 22.27s
```

Every pytest run emitted the pre-existing `pytest-asyncio` warning that
`asyncio_default_fixture_loop_scope` is unset.

### Residual risks and operational limits

- A successful barrier acknowledges only the local AOF of the selected Redis
  instance. Storage-controller lies, catastrophic disk/host loss, and loss of
  the only Redis copy remain outside the guarantee.
- CAS and `WAITAOF` are sequential commands, not one atomic operation. Failure
  between them forbids dispatch but can leave conservative ambiguity.
- The provider mutation is not atomic with Redis. Crashes and transport
  uncertainty still require read-only reconciliation or permanent ambiguity.
- Startup validation is a capability/configuration check, not continuous proof
  of server health. A later AOF, connection, or command failure fails the
  barrier and prevents that dispatch.
- The explicit `allow_test_barrier=True` runner option exists only for the
  deterministic test harness. Production composition must leave its default
  `False`; the future connector registry/startup audit remains responsible for
  rejecting all test-only components globally.
- This implementation does not add replication, HA, consensus, split-brain
  prevention, provider-side idempotency, or guaranteed duplicate prevention.

The governing guarantee remains: "Ambiguity, corruption, and contention are
detectable; the system fails closed."

## 2026-07-29 P0 mutation-safety closure evidence

### Scope and decision

This section records the test-first implementation of only P2-001, P2-002,
and P2-003 from `docs/09-post-waitaof-gate-review.md`. Within the normal intent
creation and repository write paths defined by this task, all three findings
are **fully closed**. The overall Phase 2 production gate remains **NO-GO** and
production non-idempotent dispatch remains explicitly disabled.

No request vault, production connector registry, operator API, telemetry,
scanner change, authenticated resume operation, authenticated risk-acceptance
workflow, or unrelated audit finding was implemented. In particular, a raw
`risk_acceptance_id` is rejected by normal creation and there is no privileged
override path.

`docs/09-post-waitaof-gate-review.md` remains the unchanged historical gate
snapshot. Its SHA-256 before and after this work is
`65DBBC52647D9364BFCDA6A0AA1D53287C1DCF5E3A9F1135164E95D6090694DD`.

### Exact files changed

- `src/core/exceptions.py`
  - Added the stable `Phase2StateProtectionError` domain error.
- `src/core/storage.py`
  - Added the immutable `phase2_managed="intent-ledger-v1"` field/constant.
  - Made the Phase 1 Lua CAS inspect both the current stored JSON and incoming
    JSON, while preserving live-token and stale-version error precedence.
  - Mapped Phase 2 protection rejection to the typed domain error.
- `src/core/intents.py`
  - Added typed normal-creation eligibility and execution-fence errors.
  - Added atomic predecessor, full-ledger fence, `PAUSED`, raw-risk-ID, and
    marker invariants to the Phase 2 Lua creation transaction.
  - Made every Phase 2 write require the exact marker and made normal intent
    creation construct its candidate without using a Python-only eligibility
    validator as the authority.
- `tests/test_phase2_mutation_safety.py`
  - Added the 35-test P2-001/P2-002/P2-003 regression, concurrency, stale-caller,
    raw-byte, version, TTL, and provider-call matrix.
- `tests/test_get_migration.py`
  - Changed one legacy non-empty-ledger read fixture to raw fixture injection;
    all of its round-trip assertions remain present.
- `tests/test_phase2_recovery.py`
  - Changed stale legacy Phase 2 fixture creation to raw, unmarked fixture
    injection because the Phase 1 writer is now correctly forbidden from
    introducing ledger data; all recovery assertions remain present.
- `phase2_implementation_report.md`
  - Added this dated evidence section.

No production workflow, recovery, lock, durability, connector, Redis
configuration, or historical review file was changed.

### Atomic invariant and Lua design

Normal creation is decided by `_INTENT_CAS_SCRIPT` in the same Redis Lua
invocation that may execute `SET`:

1. The script rechecks the current lock token, stored JSON, exact expected
   version, consecutive incoming version, and exact Phase 2 marker.
2. For `NONE -> ABOUT_TO_FIRE`, it scans every currently stored ledger entry.
   `ABOUT_TO_FIRE`, `FIRED_UNCONFIRMED`, or `PERMANENTLY_AMBIGUOUS` anywhere in
   the execution returns the typed execution-fence rejection. A stored
   top-level `PAUSED` status returns the same rejection before any change.
3. During the same scan it finds the highest attempt for the requested
   `step_id`. No predecessor or a latest `FAILED_CONFIRMED` predecessor is
   eligible; every other latest status returns the typed eligibility
   rejection. A non-null raw `risk_acceptance_id` also returns that rejection.
4. Only after those checks does it validate exact attempt numbering,
   preservation of every old record, audit shape, uniqueness, retention, and
   the new record. A rejected script performs no `SET`, so status, version,
   ledger, audit bytes, and TTL policy remain untouched except for elapsed
   time.
5. The first successful Phase 2 intent creation writes
   `phase2_managed="intent-ledger-v1"` atomically with the intent, status, audit,
   and version. Every later Phase 2 transition requires the exact marker.
   A legacy unmarked Phase 2 record is not rewritten on read; its next explicit
   invariant-aware Phase 2 transition adds the marker atomically.

The Phase 1 `_CAS_SCRIPT` also makes its decision inside the one atomic write:

1. It checks the live lock first and the exact version next, preserving the
   existing stale-token and stale-version behavior.
2. It then inspects the currently stored value. Any non-null marker or any
   non-empty legacy ledger returns `Phase2StateProtectionError`, including for
   a caller with the current token and current version.
3. It separately rejects an incoming marker or non-empty ledger, including on
   first write, so the base writer cannot introduce Phase 2 state.
4. The rejection path performs no write and therefore cannot reset or shorten
   the TTL. Genuine unmarked, ledger-free Phase 1 writes continue normally.

These checks are not Python pre-checks. The Lua scripts are the authoritative
race-free enforcement points.

### Complete regression matrix

| Requirement | Executable evidence |
|---|---|
| First normal attempt and atomic marker | `test_p2001_first_attempt_is_allowed_and_sets_phase2_marker_atomically` |
| `FAILED_CONFIRMED` allows exactly one next attempt | `test_p2001_failed_confirmed_permits_exactly_one_next_normal_attempt` |
| Confirmed success, about-to-fire, unconfirmed, and permanent predecessors reject with unchanged raw bytes/version | Four parameter rows in `test_p2001_ineligible_predecessor_rejects_current_caller_unchanged` |
| Confirmed success causes zero additional provider calls | `test_p2001_confirmed_success_rejects_runner_before_second_provider_call` |
| Raw risk ID cannot bypass permanent ambiguity | `test_p2001_raw_risk_acceptance_id_cannot_bypass_permanent_ambiguity` |
| Two callers racing after confirmed failure create at most one attempt and make one provider call | `test_p2001_two_racing_callers_after_failed_create_at_most_one_attempt` |
| Every blocking step-A status fences step B with current token/version and unchanged bytes | Three parameter rows in `test_p2002_blocking_step_a_fences_step_b_in_same_atomic_creation` |
| Every blocking status produces zero provider calls through the runner | Three parameter rows in `test_p2002_global_fence_rejects_runner_with_zero_provider_calls` |
| `PAUSED` is not changed implicitly | `test_p2002_paused_execution_without_blocking_ledger_fails_closed` |
| Confirmed terminal states do not create a global fence for another step | Two parameter rows in `test_p2002_terminal_states_do_not_create_unintended_global_fence` |
| Current base writer cannot delete ledger, alter immutable fields/status/history, unpause, remove/change marker, replace with an empty ledger, or shorten retention | Nine parameter rows in `test_p2003_current_base_writer_cannot_modify_marked_phase2_state` |
| Base writer cannot introduce marker or ledger | Two parameter rows in `test_p2003_base_writer_cannot_introduce_phase2_state` |
| Unmarked legacy Phase 2 state is protected and read does not migrate it | `test_p2003_unmarked_legacy_phase2_ledger_is_protected` |
| Genuine Phase 1 writes remain functional | `test_p2003_unmarked_ledger_free_phase1_writes_still_pass` |
| Phase 2 transition remains functional and marker cannot change through Phase 2 CAS | `test_p2003_phase2_transition_remains_allowed_and_marker_is_immutable` |
| Base writer racing a Phase 2 transition always loses; the transition survives | `test_p2003_base_writer_racing_phase2_transition_always_loses` |
| Existing unmarked stale token/version errors remain unchanged | `test_stale_token_and_stale_version_precedence_remains_unchanged` |
| Marked-state stale token/version errors remain unchanged | `test_marked_phase2_state_preserves_stale_token_and_version_errors` |

Every P2-003 rejection helper asserts exact raw Redis byte equality, unchanged
serialized version, and no TTL reset or shortening beyond measured elapsed time
plus a 1-second scheduling tolerance. Runner tests assert provider mutation
counts from the test-only ground-truth oracle.

### Test-first evidence

The new regression module was added before production changes. Exact command:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_mutation_safety.py -p no:cacheprovider -q
```

The pre-fix terminal summary was:

```text
27 failed, 5 passed, 12 warnings in 6.13s
```

Failures reproduced the missing marker, confirmed/permanent retries, Python-only
same-step rejection, different-step global-fence bypass, implicit unpause,
base-writer ledger/status/history/marker/TTL rewrites, legacy-ledger bypass, and
the base-writer/Phase-2-transition race. After implementation and expansion of
the stale-caller/read-without-migration rows, the same module collected 35
passing tests as recorded below.

### Final verification commands and unedited result summaries

All Redis-backed commands used `redis://127.0.0.1:6381/15`. Pytest emitted the
same pre-existing `pytest-asyncio` deprecation warning after every invocation:

```text
PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
```

It did not affect any result.

#### 1. Compile every source and test module

```powershell
$env:PYTHONPYCACHEPREFIX='C:\Users\DELL\AppData\Local\Temp\aep-p0-mutation-safety-pycompile'; $compileFiles = @(rg --files src tests -g '*.py'); py -3 -m py_compile $compileFiles
```

```text
exit 0; no output
```

#### 2. Focused Phase 1 storage/CAS tests

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_cas_write.py tests/test_get_migration.py tests/test_races.py tests/test_uuid_validation.py tests/test_version_range.py -p no:cacheprovider -q
```

```text
................................                                         [100%]
32 passed in 1.37s
```

#### 3. Focused Phase 2 state-machine and runner/recovery tests

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_mock_connector.py tests/test_phase2_durability.py tests/test_phase2_state_machine.py tests/test_phase2_runner.py tests/test_phase2_recovery.py -p no:cacheprovider -q
```

```text
........................................................................ [ 44%]
........................................................................ [ 88%]
...................                                                      [100%]
163 passed in 5.79s
```

#### 4. New P2-001/P2-002/P2-003 suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_mutation_safety.py -p no:cacheprovider -q
```

```text
...................................                                      [100%]
35 passed in 3.10s
```

#### 5. Complete suite with integration enabled

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests -p no:cacheprovider -q
```

```text
........................................................................ [ 28%]
........................................................................ [ 56%]
........................................................................ [ 85%]
.....................................                                    [100%]
253 passed in 31.40s
```

#### 6. Standalone Redis 7.2 WAITAOF integration suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_waitaof_integration.py -p no:cacheprovider -q
```

```text
....                                                                     [100%]
4 passed in 6.92s
```

The integration tier continued to prove same-connection CAS then
`WAITAOF 1 0 <timeout-ms>`, fail-closed barrier behavior, one permitted
provider call, and controlled Redis restart survival. No fake durability
fallback was introduced.

#### 7. Safe DB-15 dynamic reproductions

The dynamic probe used current library objects, real WAITAOF for every
dispatch-capable runner, a DB-15 assertion, and `SCAN MATCH aep:*` plus `DEL`
cleanup before the cases and in `finally`. Exact command:

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $code = @'
import asyncio
import json
import time
import uuid
from redis.asyncio import Redis
from src.core.durability import RealWaitAofDurabilityBarrier
from src.core.exceptions import Phase2StateProtectionError
from src.core.intent_workflow import ConnectorPolicy, WriteAheadRunner
from src.core.intents import ExecutionIntentFenceError, IntentCreationEligibilityError, IntentLedgerStore, IntentStatus
from src.core.locks import DistributedLockManager
from src.core.storage import AEPExecutionState, AEPStatus, RedisStorageAdapter
from tests.mock_connector import MockConnectorHarness, ResponseMode

URL = 'redis://127.0.0.1:6381/15'
POLICY = ConnectorPolicy(client_timeout_seconds=0.01, settlement_lag_seconds=0, buffer_margin_seconds=15, lock_ttl_seconds=30, durability_timeout_ms=2000, lease_acquire_attempts=1)

async def cleanup(redis):
    batch = []
    async for key in redis.scan_iter(match='aep:*', count=500):
        batch.append(key)
        if len(batch) == 500:
            await redis.delete(*batch)
            batch.clear()
    if batch:
        await redis.delete(*batch)

async def seed(redis):
    eid = str(uuid.uuid4())
    locks = DistributedLockManager(redis)
    token = await locks.acquire_lock(eid, ttl_seconds=60)
    assert token
    await RedisStorageAdapter(redis).save_state(AEPExecutionState(execution_id=eid, status=AEPStatus.IDLE), expected_version=0, lock_token=token, ttl_seconds=3600)
    assert await locks.release_lock(eid, token)
    return eid

async def make_permanent(redis, eid, step='step-a'):
    store = IntentLedgerStore(redis)
    locks = DistributedLockManager(redis)
    token = await locks.acquire_lock(eid, ttl_seconds=60)
    assert token
    intent = await store.create_intent(execution_id=eid, expected_version=1, lock_token=token, step_id=step, connector='mock.non-idempotent.v1/mutate', target='redacted-target', request_fingerprint='e'*64, client_timeout_seconds=0.01, settlement_lag_seconds=0, buffer_margin_seconds=15, actor='probe')
    await store.transition_intent(execution_id=eid, intent_id=intent.intent_id, expected_version=2, lock_token=token, new_status=IntentStatus.FIRED_UNCONFIRMED, actor='probe', reason='ambiguous')
    await store.transition_intent(execution_id=eid, intent_id=intent.intent_id, expected_version=3, lock_token=token, new_status=IntentStatus.PERMANENTLY_AMBIGUOUS, actor='probe', reason='exhausted')
    assert await locks.release_lock(eid, token)
    return intent.intent_id

async def runner(redis, harness):
    return WriteAheadRunner(store=IntentLedgerStore(redis), lock_manager=DistributedLockManager(redis), connector=harness.connector, barrier=RealWaitAofDurabilityBarrier(), policy=POLICY, connector_name='mock.non-idempotent.v1/mutate')

async def main():
    redis = Redis.from_url(URL, decode_responses=True)
    try:
        assert int((await redis.client_info())['db']) == 15
        await cleanup(redis)

        eid = await seed(redis)
        harness = MockConnectorHarness()
        harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
        harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
        first = await (await runner(redis, harness)).execute(execution_id=eid, step_id='step-a', target='redacted-target', request_fingerprint='a'*64)
        raw_before = await redis.get(f'aep:state:{eid}')
        try:
            await (await runner(redis, harness)).execute(execution_id=eid, step_id='step-a', target='redacted-target', request_fingerprint='a'*64)
            raise AssertionError('confirmed retry unexpectedly succeeded')
        except IntentCreationEligibilityError:
            pass
        state = await IntentLedgerStore(redis).get_execution(eid)
        print('P2-001_CONFIRMED_CLOSED', first.status.value, len(harness.oracle.calls), sorted(i.attempt for i in state.intent_ledger.values()), await redis.get(f'aep:state:{eid}') == raw_before)

        eid = await seed(redis)
        old = await make_permanent(redis, eid)
        harness = MockConnectorHarness()
        harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
        raw_before = await redis.get(f'aep:state:{eid}')
        try:
            await (await runner(redis, harness)).execute(execution_id=eid, step_id='step-a', target='redacted-target', request_fingerprint='b'*64)
            raise AssertionError('permanent retry unexpectedly succeeded')
        except ExecutionIntentFenceError:
            pass
        state = await IntentLedgerStore(redis).get_execution(eid)
        print('P2-001_PERMANENT_CLOSED', state.status.value, state.intent_ledger[old].status.value, len(harness.oracle.calls), len(state.intent_ledger), await redis.get(f'aep:state:{eid}') == raw_before)

        eid = await seed(redis)
        old = await make_permanent(redis, eid)
        harness = MockConnectorHarness()
        harness.enqueue_call(ResponseMode.DEFINITIVE_SUCCESS)
        raw_before = await redis.get(f'aep:state:{eid}')
        try:
            await (await runner(redis, harness)).execute(execution_id=eid, step_id='step-b', target='redacted-target', request_fingerprint='c'*64)
            raise AssertionError('global fence bypass unexpectedly succeeded')
        except ExecutionIntentFenceError:
            pass
        state = await IntentLedgerStore(redis).get_execution(eid)
        print('P2-002_GLOBAL_FENCE_CLOSED', state.status.value, state.intent_ledger[old].status.value, len(harness.oracle.calls), len(state.intent_ledger), await redis.get(f'aep:state:{eid}') == raw_before)

        eid = await seed(redis)
        store = IntentLedgerStore(redis)
        locks = DistributedLockManager(redis)
        storage = RedisStorageAdapter(redis)
        token = await locks.acquire_lock(eid, ttl_seconds=60)
        assert token
        intent = await store.create_intent(execution_id=eid, expected_version=1, lock_token=token, step_id='step-a', connector='mock.non-idempotent.v1/mutate', target='redacted-target', request_fingerprint='d'*64, client_timeout_seconds=0.01, settlement_lag_seconds=0, buffer_margin_seconds=15, actor='probe')
        current = await store.get_execution(eid)
        raw_before = await redis.get(f'aep:state:{eid}')
        ttl_before = await redis.pttl(f'aep:state:{eid}')
        bypass = AEPExecutionState.model_validate({**current.model_dump(), 'version': current.version + 1, 'status': AEPStatus.IDLE, 'intent_ledger': {}})
        started = time.monotonic()
        try:
            await storage.save_state(bypass, expected_version=current.version, lock_token=token, ttl_seconds=60)
            raise AssertionError('base writer bypass unexpectedly succeeded')
        except Phase2StateProtectionError:
            pass
        elapsed_ms = (time.monotonic() - started) * 1000
        raw_after = await redis.get(f'aep:state:{eid}')
        ttl_after = await redis.pttl(f'aep:state:{eid}')
        state = await store.get_execution(eid)
        ttl_unchanged = ttl_after <= ttl_before and ttl_after >= ttl_before - elapsed_ms - 1000
        print('P2-003_BASE_WRITER_CLOSED', state.status.value, state.version, state.intent_ledger[intent.intent_id].status.value, raw_after == raw_before, ttl_unchanged)
        assert await locks.release_lock(eid, token)
    finally:
        await cleanup(redis)
        assert await redis.dbsize() == 0
        await redis.aclose()

asyncio.run(main())
'@; py -3 -c $code
~~~

Its four verbatim output lines were:

```text
P2-001_CONFIRMED_CLOSED FIRED_CONFIRMED 1 [1] True
P2-001_PERMANENT_CLOSED PAUSED PERMANENTLY_AMBIGUOUS 0 1 True
P2-002_GLOBAL_FENCE_CLOSED PAUSED PERMANENTLY_AMBIGUOUS 0 1 True
P2-003_BASE_WRITER_CLOSED PROCESSING 2 ABOUT_TO_FIRE True True
```

The final boolean on every line proves raw serialized state equality; the final
P2-003 boolean additionally proves TTL changed only by elapsed time. Provider
counts are `1` total after one confirmed first call and `0` in both ambiguity
fence probes. Attempts remained `[1]`; no new intent was created.

### Redis configuration and cleanup confirmation

Exact command:

```powershell
docker compose -f compose.phase2.yml config --quiet; redis-cli -h 127.0.0.1 -p 6381 -n 15 PING; redis-cli -h 127.0.0.1 -p 6381 -n 15 INFO server | Select-String '^redis_version:'; redis-cli -h 127.0.0.1 -p 6381 -n 15 CONFIG GET appendonly appendfsync; redis-cli -h 127.0.0.1 -p 6381 -n 15 COMMAND INFO WAITAOF | Select-Object -First 4; $aepKeys = @(redis-cli -h 127.0.0.1 -p 6381 -n 15 --scan --pattern 'aep:*'); "aep_key_count=$($aepKeys.Count)"; redis-cli -h 127.0.0.1 -p 6381 -n 15 DBSIZE; $flushStat = redis-cli -h 127.0.0.1 -p 6381 -n 15 INFO commandstats | Select-String '^cmdstat_flushall:'; if ($flushStat) { $flushStat } else { 'flushall_commandstat=absent' }; Get-FileHash docs/09-post-waitaof-gate-review.md -Algorithm SHA256 | Select-Object -ExpandProperty Hash
```

Unedited output:

```text
PONG

redis_version:7.2.5
appendonly
yes
appendfsync
everysec
waitaof
4
noscript
0
aep_key_count=0
0
flushall_commandstat=absent
65DBBC52647D9364BFCDA6A0AA1D53287C1DCF5E3A9F1135164E95D6090694DD

WARNING: Error loading config file: open C:\Users\DELL\.docker\config.json: Access is denied.
WARNING: Error loading config file: open C:\Users\DELL\.docker\config.json: Access is denied.
```

The Compose configuration command still exited 0; the two Docker CLI warnings
concerned only the user's Docker client config file. Redis itself returned
`PONG`, version `7.2.5`, AOF enabled, `appendfsync everysec`, and WAITAOF command
metadata. DB 15 contained zero `aep:*` keys and `DBSIZE` was `0` after testing.
No test, probe, fixture, or verification command invoked `FLUSHALL`; cleanup
deleted only scanned `aep:*` keys. The final command-stat output contained no
`cmdstat_flushall` entry.

### Closure status and remaining limitations

- **P2-001 fully closed for normal creation.** Only no predecessor or latest
  `FAILED_CONFIRMED` is eligible. Confirmed success and all ambiguous/in-flight
  statuses reject. Raw risk strings never authorize a retry.
- **P2-002 fully closed for normal creation.** The complete stored ledger and
  top-level `PAUSED` status are fenced atomically, including different steps.
- **P2-003 fully closed for the repository write APIs.** Marked and legacy-ledger
  states cannot be modified through `save_state`, and that writer cannot
  introduce Phase 2 data.

This closure does not provide exactly-once execution or guaranteed duplicate
prevention. Redis and the provider remain separate systems. The request vault,
production connector contract/registry, authenticated operator resolution and
risk acceptance, explicit authenticated resume from `PAUSED`, telemetry,
scanner hardening, remaining crash-oracle work, and other findings in the gate
review remain open. Therefore production dispatch remains disabled and the
bounded guarantee remains:

> Ambiguity, corruption, and contention are detectable; the system fails closed.

## 2026-07-31 addendum: canonical request-binding repository closure

### Scope and independently confirmed findings

This bounded patch addresses the four repository defects independently confirmed
from `docs/13-request-binding-closure-review.md`; it does not modify that review.
The confirmed defects were:

1. authoritative Lua paths compared decoded binding tables rather than exact
   canonical binding bytes, leaving empty-array/object and numeric-lexeme
   equivalence unproved;
2. `VerifiedDispatch` used a module-level construction token and the connector
   checked only the exact class, so successful verification had no
   connector-verifiable provenance;
3. persisted `SafeField.canonical_value` strings lacked a dedicated exact
   endpoint-profile revalidation boundary and safe direct representation; and
4. vault AAD omitted execution/step and several operation, profile, material,
   credential, codec, key, and deadline fields.

The absence of a durable production vault/KMS and a production connector remains
outside this patch. No connector registry, scheduler/operator API, deployment
automation, production credential flow, real provider call, or unrelated Phase 2
finding was implemented. Production non-idempotent dispatch remains disabled.

### Files changed

Production:

- `src/core/request_binding.py`
- `src/core/request_vault.py`
- `src/core/intents.py`
- `src/core/intent_workflow.py`

Existing tests/fixtures and matrix:

- `tests/request_binding_helpers.py`
- `tests/test_request_canonicalization.py`
- `tests/test_request_vault.py`
- `tests/test_request_binding_intents.py`
- `tests/test_phase2_state_machine.py`
- `tests/test_verified_dispatch.py`
- `tests/mock_connector.py`
- `tests/MATRIX.md`

New focused tests:

- `tests/test_canonical_request_binding_closure.py`
- `tests/test_verified_dispatch_provenance.py`
- `tests/test_endpoint_profile_revalidation.py`
- `tests/test_vault_aad_closure.py`
- `tests/test_privacy_boundary_closure.py`

No protected review document was edited, and `docs/14` was not created.

### Tests-first evidence

Before any production edit, the five new focused modules were run together:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_canonical_request_binding_closure.py tests/test_verified_dispatch_provenance.py tests/test_endpoint_profile_revalidation.py tests/test_vault_aad_closure.py tests/test_privacy_boundary_closure.py -p no:cacheprovider -q
```

Exit `1`: `71 failed, 5 passed, 2 warnings in 6.71s`. The failures were the
expected missing closure behavior: no canonical-binding API/persisted canonical
field or nesting limit, absent provenance consumer/connector identity, absent
persisted-profile validator, incomplete AAD model, and canonical safe values in
model representations. Two warnings were caused by pytest collecting imported
helpers whose names began with `test_`; aliases removed that collection artifact.
One privacy rejection initially occurred during request construction rather than
inside the assertion context; the assertion was widened around the same full
construction-and-prepare boundary without weakening the rejection or privacy
checks.

The first post-implementation run of those modules exited `0` with `74 passed in
1.67s`. After adding the exhaustive stale/all-field provenance cases, nested
caller mutation, and final report/cache marker scan, the delivered focused run is
recorded in the final verification table below.

Two compatibility discovery runs are retained rather than erased:

- Existing canonical/vault/binding/dispatch selection: exit `1`, `14 failed,
  52 passed in 5.12s`. Cause: old binding-mutation fixtures changed the excluded
  typed view but not the new authoritative canonical string, and one raw fixture
  still indexed the retired nested representation. After mandatory fixture
  adaptation, the identical command exited `0`, `66 passed in 3.40s`.
- Broad Phase 2/P0/raw/recovery selection: exit `1`, `18 failed, 216 passed in
  8.72s`. Cause: a duplicate-intent fixture did not supply its second canonical
  binding and Lua initially treated absent versus explicit-null canonical fields
  differently for intentionally unbound legacy recovery records. The focused
  correction rerun exited `0`, `19 passed in 1.83s`; the identical broad command
  then exited `0`, `234 passed in 7.97s`.

No existing test was removed, skipped, weakened, conditionally bypassed, or
broadly rewritten.

### Canonical binding representation and authoritative Lua enforcement

`aep.canonical-json/1` remains the single strict request/binding canonicalizer.
It now has explicit limits of 1,048,576 canonical bytes and 128 nested container
levels. It preserves order-sensitive arrays and distinguishes missing members,
explicit null, arrays, and objects. It accepts only strict NFC UTF-8 strings,
exact booleans, null, interoperable-range integers, arrays, and string-keyed
objects; it rejects duplicate members on decode, malformed UTF-8, floats, NaN,
Infinity, unsupported values, noncanonical encodings, and excessive material or
nesting.

`canonical_request_binding_bytes()` canonicalizes every field of
`aep.persisted-request-binding/1`, including execution, step, intent,
correlation, connector identity/operation, endpoint and credential profiles,
wire/material/vault/descriptor/canonicalization versions, key identifiers,
fingerprint, attempt digest, all deadlines, public safe values, mutation options,
and protected commitments. It contains no raw protected request material.

New bound intent records persist only this canonical UTF-8 JSON as
`canonical_request_binding`; the typed `request_binding` view is excluded from
Redis serialization and is reconstructed only by strict canonical decode for an
already-present canonical value. A bound object without the canonical field is
rejected; an unbound legacy record is not backfilled. This is not a silent binding
reconstruction path.

The shared intent CAS now requires exact string equality with the caller's
canonical binding at creation and every later bound mutation. The same CAS body is
used by ordinary transitions, runner resolution, recovery claim, recovery
resolution, and retention-affecting state transitions. Preflight compares the
complete canonical string exactly before interpreting its digest. The existing
raw UTF-8/duplicate/member/depth gate remains before lease, version, status, or
binding interpretation. Tests alter numeric lexical form, empty array/object
type, key order, members, values, array order, identities, versions, and deadlines;
all rejections preserve the exact raw Redis string, version, status, ledger,
history, and elapsed-time-only TTL.

Legacy unbound intents remain inspectable and usable by the existing read-only
reconciliation handling, but cannot acquire a binding or pass mutation preflight.

### Connector-verifiable `VerifiedDispatch` provenance

`VerifiedDispatch` remains frozen and redacted but no longer has a caller-usable
constructor or module-level token. Successful `RequestBindingService.verify`
returns through an installed closure-held issuer. Issuance creates a random,
HMAC-authenticated, process-local record keyed to object identity, the SHA-256 of
the exact authenticated vault bytes, and the complete canonical safe binding.
The provenance token contains no request plaintext, credential, or protected
value. The issuer callable is removed from module globals after installation.

`consume_verified_dispatch()` is the connector-side boundary. It atomically
consumes the capability once, requires the exact class and object identity,
checks monotonic capability expiry, verifies the HMAC record, exact-material hash,
canonical binding, connector identity/operation, endpoint profile/version, and
execution/step/intent/correlation context, then returns an immutable copy of the
authenticated exact bytes. Failed checks consume no provider call authority.
Direct construction, the former token path, `object.__new__` forgery, copies,
subclasses, look-alikes, reuse/staleness, context transplant, and replacement of
material, target/body semantics, binding, profile, descriptor/material/vault
versions, keys, fingerprints/digests, or deadlines are rejected. Both repository
test connectors call this consumer before modeling transmission.

Caller-owned top-level and nested input mutations cannot alter transmitted bytes.
A valid dispatch yields exactly one connector call. A connector exception records
that one call and is never automatically retried.

### Endpoint-profile revalidation

Immediately before capability issuance, verification now:

1. uses the canonical binding reloaded from authoritative Redis after preflight;
2. retrieves and authenticates the exact vault object;
3. checks all authenticated metadata against the binding and invocation context;
4. revalidates the persisted descriptor against the exact selected versioned
   endpoint profile;
5. rebuilds the safe descriptor and protected commitments from exact vault bytes;
6. recomputes the semantic fingerprint and attempt binding digest; and
7. compares every result before issuing provenance.

The explicit `SafeValueRule` allowlists remain authoritative. Persisted canonical
values are strictly decoded and recursively checked. Public fields and mutation
options require exact name sets; objects require exact members; arrays require
the declared item schema and bounds; protected commitment names, classifications,
algorithms, and key IDs must match the profile/binding. Unknown, missing,
additional, wrongly typed/classified, wrong-operation/version, noncanonical,
nested-object/array, and extra-metadata cases fail with stable request-binding
reason codes before transport. The name scanner remains supplementary.

### Complete versioned vault AAD

Vault AAD is now the strict canonical `aep.vault-aad/1` document. It authenticates:

- opaque locator, vault-object version, request-material version, material length;
- `AES-GCM` algorithm and encryption key ID;
- request envelope, canonicalization, and descriptor versions;
- connector identity, connector operation and operation version;
- endpoint-profile ID/version, credential-binding ID/version, and wire codec;
- commitment algorithm and historical commitment key ID;
- execution ID, step ID, intent ID, and correlation ID; and
- creation time, intent-creation deadline, dispatch-material expiry, and retention
  deadline.

AAD generation and AES-GCM verification call the same strict canonicalizer.
Individual alteration of every field produces a typed vault/request-binding
rejection before provider transport. There is no alternate-key trial, repair,
metadata replacement, locator regeneration, plaintext fallback, or overwrite.
Create-once/concurrent-create behavior and exact authenticated readback remain.
The backing representation contains nonce, ciphertext/tag, and safe AAD only.

`TestOnlyInMemoryRequestVault` remains explicitly acknowledged, process-local,
non-durable, and test-only. Production dispatch validation still refuses it unless
the complete explicit test-only composition is enabled; there is no production
configuration path that selects it.

### Safe-value and privacy boundary

`SafeField` now validates that its stored text is strict canonical JSON, suppresses
the canonical value from `repr`/`str`, and hides rejected input from Pydantic
errors. Binding/descriptor/intent/vault models use safe fixed failures and hidden
validation inputs at the protected boundaries. The exact endpoint-profile
revalidation is required before dispatch capability issuance.

Existing fixed allowlists remain for intent identities, actor/reason/observation,
external reference, evidence, quarantine metadata, and logs. Unknown connector or
provider evidence is reduced to bounded `AMBIGUOUS`/`UNKNOWN` classification;
provider identifiers and arbitrary payloads are dropped. Quarantine stores only
safe reason/presence/length/encoding metadata. Workflow wrappers retain fixed
reason codes or exception class names and suppress unsafe cause chains. No raw
request/vault material is stored in Redis, history, quarantine, evidence, logs,
snapshots, or representations.

Six fresh runtime-generated non-secret markers are created only inside the new
privacy tests. The tests cover nested/case-varied request placement, safe model
representations and errors, exception/cause behavior, evidence, request
representations, captured test output, review/report files, and pytest-cache
artifacts. The final scan result is zero prohibited occurrences. The existing
typed-schema tests remain authoritative; scanner checks are supplementary. No
runtime marker literal is reproduced here.

Python cannot guarantee erasure of immutable managed-memory objects, canonical
buffers, AES-GCM inputs/outputs, or connector arguments. No memory-zeroization or
guaranteed secret-nondisclosure claim is made.

### Mandatory fixture changes and preserved assertions

| Fixture | Binding-contract reason | Original assertion preserved |
|---|---|---|
| `test_profile` and canonicalization `_profile` | endpoint profiles now require a separate connector identity | Same canonicalization, profile-change, and request-validation behavior |
| Vault `_metadata` fixture | every AAD field is now mandatory/authenticated | Same exact readback, expiry, collision/update, integrity, missing-key, concurrency, and no-plaintext assertions |
| Request-binding mutation fixtures | the authoritative persisted binding is now the canonical string, not a decoded Redis object | Same removal/replacement/transplant/retention rejection, exact raw state, history, version, status, and TTL assertions |
| Legacy intent fixture | an unbound legacy record must omit canonical binding and may retain explicit `request_binding: null` | Same readability and binding-addition/preflight rejection |
| Duplicate-intent fixture | a second typed binding requires its own canonical representation | Same same-Lua global uniqueness/fence rejection |
| Runner altered-binding barrier | controlled replacement must edit the canonical descriptor inside the authoritative string | Same zero-provider, one-historical-ack, zero-post-rejection-write assertion |
| Mock and recording connectors | connector acceptance now requires provenance consumption | Same scripted call/crash/evidence/count behavior, with stronger pre-transport validation |

### Verification commands and results

Every pytest command selected `redis://127.0.0.1:6381/15`, set
`PYTHONDONTWRITEBYTECODE=1`, and disabled the pytest cache provider.

The first sandboxed all-file compile command exited `1` before directory creation
because `C:\tmp\aep-request-binding-closure-pyc` was denied. The identical approved
rerun was:

```powershell
$ErrorActionPreference='Stop'; $compileDir='C:\tmp\aep-request-binding-closure-pyc'; $resolved=[IO.Path]::GetFullPath($compileDir); $allowed=[IO.Path]::GetFullPath('C:\tmp\'); if(-not $resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'unsafe compile path'}; if(Test-Path -LiteralPath $resolved){throw 'compile path already exists'}; New-Item -ItemType Directory -Path $resolved | Out-Null; try { $env:PYTHONPYCACHEPREFIX=$resolved; $pyFiles=@(Get-ChildItem -LiteralPath 'src','tests' -Recurse -Filter '*.py' | Select-Object -ExpandProperty FullName); py -3 -m py_compile @pyFiles; $compileExit=$LASTEXITCODE; $artifactCount=(Get-ChildItem -LiteralPath $resolved -Recurse -File | Measure-Object).Count; Write-Output "py_files=$($pyFiles.Count)"; Write-Output "py_compile_exit_code=$compileExit"; Write-Output "compiled_artifacts=$artifactCount" } finally { if(Test-Path -LiteralPath $resolved){ Remove-Item -LiteralPath $resolved -Recurse -Force }; Write-Output "temp_removed=$(-not (Test-Path -LiteralPath $resolved))" }; exit $compileExit
```

Exit `0`: `py_files=43`, `compiled_artifacts=80`, `temp_removed=True`. A final
identical delivered-tree rerun is recorded below.

| Required selection | Exact pytest files | Exit | Result |
|---|---|---:|---|
| Post-implementation closure | five new `test_*_closure.py`/provenance/profile modules listed in the tests-first command | 0 | `92 passed in 1.36s` before the final report-scan case; final rerun below |
| Phase 1 storage/CAS | `test_cas_write.py test_get_migration.py test_races.py test_uuid_validation.py test_version_range.py` | 0 | `32 passed in 1.25s` |
| Focused Phase 2 | `test_mock_connector.py test_phase2_durability.py test_phase2_state_machine.py test_phase2_runner.py test_phase2_recovery.py` | 0 | `163 passed in 5.66s` |
| Combined P0 | `test_phase2_mutation_safety.py test_phase2_duplicate_member_safety.py` | 0 | `45 passed in 4.04s` |
| State codec/Lua | `test_state_codec.py test_phase2_duplicate_member_safety.py` | 0 | `152 passed in 3.46s` |
| Raw-state gate | `test_raw_state_validation_gate.py` | 0 | `26 passed in 1.64s` |
| Canonical binding | `test_request_canonicalization.py test_canonical_request_binding_closure.py test_request_binding_intents.py` | 0 | `57 passed in 2.44s` |
| Vault/safe value | `test_request_vault.py test_vault_aad_closure.py test_endpoint_profile_revalidation.py test_privacy_boundary_closure.py` | 0 | `58 passed in 0.61s` before final report-scan case; final rerun below |
| Verified dispatch | `test_verified_dispatch.py test_verified_dispatch_provenance.py` | 0 | `64 passed in 2.24s` |
| Recovery/resolution | `test_phase2_recovery.py test_phase2_runner.py` | 0 | `43 passed in 2.48s` |
| Preliminary complete integration-enabled | `tests` with `AEP_PHASE2_REDIS_INTEGRATION=1` and container `aep-phase2-redis72` | 0 | `610 passed in 36.75s`; final delivered-tree rerun below |
| Redis 7.2 WAITAOF | `test_phase2_waitaof_integration.py` with integration variables | 0 | `4 passed in 8.42s` |
| Explicit accepted/rejected dispatch | `test_verified_dispatch.py` | 0 | `34 passed in 2.42s` |
| Counter-focused dispatch | six named accepted/unsafe/missing/AAD/canonical/exception tests in `test_verified_dispatch.py` | 0 | `25 passed in 2.02s` |

The earlier complete non-integration run, before the last expanded cases, exited
`0`: `567 passed, 4 skipped in 38.49s`. No successful final required run has a
failure or skip unless explicitly stated above.

### Controlled counter results

| Case | Intent/state result | Provider calls | Durability acknowledgements |
|---|---|---:|---:|
| Unsafe request or disabled production composition before creation | no new intent | 0 | 0 |
| Valid verified dispatch and confirmed resolution | bound `FIRED_CONFIRMED` | 1 | 2 |
| Missing/expired/unauthenticated vault after durable creation | original bound `ABOUT_TO_FIRE` | 0 | 1 historical creation acknowledgement; 0 additional |
| Any individually altered authenticated AAD field | original bound `ABOUT_TO_FIRE` | 0 | 1 historical creation acknowledgement; 0 additional |
| Profile mismatch or persisted safe-value replacement | original binding retained/rejected before transport | 0 | 1 historical creation acknowledgement; 0 additional |
| Noncanonical numeric or empty-container binding replacement | exact injected raw value/version/status/history retained | 0 | 1 historical creation acknowledgement; 0 additional |
| Direct rejected Lua transition | exact raw value/version/status/ledger/history retained; elapsed-time-only TTL | no provider interface in path | no durability interface in path |
| Connector exception after real transport attempt | `FIRED_UNCONFIRMED` | 1 | 2; 0 retries and 0 later provider calls |

Historical creation acknowledgement is deliberately reported separately; no
post-durable rejection is misreported as having zero historical acknowledgements.

### Redis and integrity evidence

The local test container was
`aep-phase2-redis72|redis:7.2.5-alpine|healthy|127.0.0.1:6381->6379/tcp`.
Final namespace-only cleanup/inspection reported:

```text
selected_db=15
redis_version=7.2.5
aof_enabled=1
appendonly=yes
appendfsync=everysec
aep_keys_before_cleanup=0
aep_keys_deleted=0
aep_keys_after_cleanup=0
dbsize=0
flushall_commandstat_present=false
```

Only `SCAN ... MATCH aep:*` plus `DELETE` of returned keys was permitted; no
command or fixture invoked `FLUSHALL`.

The broad `src`/`tests` filesystem manifest changed from 83 files and SHA-256
`7a73c957546868cf4a888a14419213c8bf781dd7278da8cf8f45310fb15851a9`
to 88 files and SHA-256
`78224c455e54037e6d1b793a3e21818000995c220ef68443c1f2c03313d1bd85`.
The final 43-file Python-only manifest is
`c7331debe727cdc3632a520d4a13585036b00f49da86baef2277c85fef23e530`.
The five-file increase is exactly the five new focused Python test modules.

Protected review hashes were identical before and after:

| Protected file | SHA-256 |
|---|---|
| `docs/07-phase2-gap-audit.md` | `2f0333691dc00ea9ed632ce33009348113ebb7f37f32cfee5b1a8e3114dc48e8` |
| `docs/09-post-waitaof-gate-review.md` | `65dbbc52647d9364bfcda6a0aa1d53287c1dcf5e3a9f1135164E95D6090694DD` |
| `docs/10-p0-closure-review.md` | `963a9c43476340bc9584b33306876c502b6a4c82715a9beb048d7dd2fff6935b` |
| `docs/11-json-closure-gate-review.md` | `9f2ffa41c7825fbe7fa742dabe64e2f8d38434120e3589594bd7197435a25d35` |
| `docs/12-raw-state-gate-closure-review.md` | `82a2172d454524f8ed544b8e28c571f42158f8771de5182281b6332a8dd51622` |
| `docs/13-request-binding-closure-review.md` | `2b4c0cf14d87ae60d071b934bc5eecfbad3b01df77eeff43b5b9baffcd14e6cf` |

The implementation report's pre-change SHA-256 was
`8afa31741e6f73b173f927ffd9fbf1d6b8fe953a601385eabdc5721127201db1`;
its post-change hash is recorded after the final reruns.

### Compatibility and residual limitations

P2-001/P2-002/P2-003 behavior remains unchanged. Strict UTF-8, duplicate member,
malformed JSON, NaN, and Infinity rejection pass. The raw-state-before-lock order
is unchanged. Valid Phase 1 and bound Phase 2 behavior passes. Legacy unbound
records remain readable but cannot dispatch. Phase 1 CAS protection, same-pinned-
connection CAS/WAITAOF order, transport-after-creation-durability order, and
readback-only recovery remain. Recovery never replays a non-idempotent mutation.

The preserved limitations are:

- one local Redis 7.2.5 AOF node and DB 15 only; no multi-node coordination or
  split-brain prevention;
- WAITAOF means local-AOF acknowledgement and remains sequential after CAS on a
  pinned connection, not Redis/provider atomicity;
- the Lua raw JSON nesting limit remains 128;
- quarantine remains best effort;
- an unavoidable external ambiguity window remains after a real provider call;
- HMAC commitments reveal equality within their scoped key/domain context;
- no exactly-once effect, guaranteed duplicate prevention, absolute atomicity,
  guaranteed secret non-disclosure, or Python memory erasure; and
- no durable production vault/KMS, production key lifecycle, production endpoint
  profile/connector, credential loader, or production response/reference schema.

The Phase 1 base model retains generic `context_data` and legacy ledger mappings
for compatibility, but no repository request/vault/binding/dispatch/connector
path writes protected mutation material to them. This closure is not a claim that
arbitrary future uses of those general Phase 1 fields are privacy-safe.

### Final classification

| Item | Classification | Evidence boundary |
|---|---|---|
| Repository enforcement | **VERIFIED** | Every repository-defined mutation path uses exact canonical Redis equality; dispatch requires authenticated vault recomputation, exact profile revalidation, and one-use connector-verified provenance |
| P2-004 immutable request binding | **CLOSED (repository scope)** | The only repository provider mutation is derived exclusively from authenticated exact vault bytes and accepted only through provenance tied to the immutable authoritative binding |
| P2-010 safe-value/privacy boundary | **CLOSED (repository-defined Phase 2 mutation scope)** | Typed rules cover the repository mutation state, descriptor/profile, vault/AAD, connector result, evidence, exception, log, quarantine, representation, and dispatch-metadata paths; fresh and existing privacy suites pass |
| Production applicability | **NO-GO** | Durable production vault/KMS and a reviewed production connector/profile remain absent |
| Production non-idempotent dispatch | **NO-GO** | Startup continues to reject production dispatch; only explicit test-only composition can reach transport |

These repository-scoped classifications do not convert the test-only AES-GCM
vault into production-grade security and do not authorize deployment. The next
step is the separately requested independent read-only review; this implementation
does not create `docs/14`.

The bounded guarantee remains:

> Ambiguity, corruption, and contention are detectable; the system fails closed.

## 2026-07-30 addendum: bounded P2-004/P2-010 immutable request-binding stage

This addendum supersedes only earlier statements that P2-004 and P2-010 were
unimplemented. It implements the repository-owned enforcement boundary
authorized by `docs/12-raw-state-gate-closure-review.md`. It does not add a
connector registry, scheduler, operator API, telemetry platform, deployment
automation, multi-node coordination, or any unrelated Phase 2 finding.

Production non-idempotent dispatch remains disabled and is still **NO-GO**.
Only an explicitly acknowledged test-only connector plus the explicitly
acknowledged test-only in-memory vault can exercise the transport boundary.

### Files changed

Production and configuration:

- `pyproject.toml`
- `src/core/request_binding.py` (new)
- `src/core/request_vault.py` (new)
- `src/core/intents.py`
- `src/core/intent_workflow.py`
- `src/core/intent_recovery.py`
- `src/core/storage.py`
- `src/core/durability.py`
- `src/core/locks.py`
- `src/core/state_codec.py`
- `src/core/validation.py`

Tests and fixtures:

- `tests/MATRIX.md`
- `tests/mock_connector.py`
- `tests/request_binding_helpers.py` (new)
- `tests/test_cas_write.py`
- `tests/test_mock_connector.py`
- `tests/test_phase2_duplicate_member_safety.py`
- `tests/test_phase2_mutation_safety.py`
- `tests/test_phase2_recovery.py`
- `tests/test_phase2_runner.py`
- `tests/test_phase2_state_machine.py`
- `tests/test_phase2_waitaof_integration.py`
- `tests/test_raw_state_validation_gate.py`
- `tests/test_request_canonicalization.py` (new)
- `tests/test_request_vault.py` (new)
- `tests/test_request_binding_intents.py` (new)
- `tests/test_verified_dispatch.py` (new)

The five protected historical review documents were not edited.

### Request envelope and safe persisted binding

`aep.mutation-request/1` is the exact immutable request envelope. Its
canonical object contains:

- envelope, canonicalization, and descriptor versions;
- versioned connector operation;
- endpoint-profile ID and version;
- credential-binding ID and version;
- wire-codec version;
- one profile-validated redacted target;
- exact typed public-field entries;
- exact protected-field entries with field classification and encoding;
- every profile-declared mutation option.

Protected values remain in cleartext only within the exact envelope before
vault encryption and after an explicitly authorized vault read/verified
dispatch. Redis receives only `aep.persisted-request-binding/1`, including the
safe descriptor, separate semantic fingerprint and binding digest, opaque
locator, safe connector/profile/key identifiers, object versions, IDs, and
UTC Unix-epoch-millisecond deadlines.

The safe descriptor uses recursive code-owned `SafeValueRule` schemas. String
values require explicit enumerations, integers require explicit bounds,
objects require an exact member schema, arrays require an item schema and
length bound, and unions require exactly one matching alternative. Top-level
field-name allowlists and protected-field classifications are exact. The
name-based sensitive-token scan is supplementary; it is not the authoritative
boundary. URL schemes/authorities, user information, query strings,
fragments, `@`, and backslashes are rejected from persisted targets.

No unrestricted request dictionary, request body, header collection, raw
query, caller diagnostic metadata, provider reference, or provider call ID is
persisted. Provider-returned evidence is reduced to an exact declared enum;
unknown evidence becomes `AMBIGUOUS`. Provider identifiers are not persisted
because this bounded repository has no endpoint-profile-specific safe schema
for them.

### Canonicalization and fingerprints

`aep.canonical-json/1` is the only request canonicalizer. It emits strict UTF-8
JSON with sorted object keys, compact fixed separators, and no insertion-order,
locale, platform, timezone, or process dependency. It accepts only null,
exact booleans, integers within the documented interoperable safe range, NFC
UTF-8 strings, arrays, and string-keyed objects. Floats, NaN, infinities,
non-string object keys, non-NFC text, duplicate members on decode, unsupported
objects, non-canonical encodings, and excessive material are rejected. Times
are explicit UTC Unix epoch milliseconds; monetary examples use integer minor
units. No undocumented lossy numeric or textual normalization is applied.

The semantic request fingerprint is:

```text
SHA-256(canonical_utf8(aep.safe-request/1 descriptor))
```

The descriptor covers its schema/canonicalization/domain versions, operation
and operation version, endpoint profile and version, credential profile and
version, wire codec, redactor and dynamic-transport policies, redacted target,
typed public fields, typed mutation options, and protected commitments. Array
order remains significant.

The attempt-specific request-binding digest is a separate SHA-256 over a
canonical manifest under `AEP_ATTEMPT_REQUEST_BINDING_V1`. It covers the
semantic fingerprint, opaque material locator and material version, execution
ID, step ID, intent ID, correlation ID, descriptor version, endpoint-profile
version, vault-object version, creation time, intent-creation deadline,
dispatch-material expiry, and retention deadline. Tests prove that changing
any field changes the digest and that a binding cannot be transplanted to
another execution or intent.

### Protected commitments and key assumptions

Protected identity uses `HMAC-SHA-256`, never an unkeyed hash. The input is an
explicit 32-bit-length-framed sequence containing:

```text
AEP_SENSITIVE_FIELD_V1
aep.safe-request/1
canonical operation context
field identity
canonical protected encoding/value object
```

The operation context contains the versioned connector operation and endpoint
profile. The safe descriptor identifies the commitment algorithm and key ID.
The keyring accepts only explicitly provisioned keys of at least 32 bytes,
has no generated or development default, is separate from the vault encryption
keyring, and fails closed when the selected historical key is unavailable.
Verification uses the persisted commitment key ID; it does not recompute a
historical commitment with the current active key or rewrite it during
dispatch.

### Vault interface and implemented backend

`RequestVault` defines create-once and exact-read operations returning stable
typed failures. `VaultObjectMetadata` authenticates the opaque locator, object
and envelope versions, encryption key ID, connector, descriptor version,
intent/correlation IDs, UTC creation/expiry/retention deadlines, and material
length.

The only backend is `TestOnlyInMemoryRequestVault`. It requires an explicit
`test_only_acknowledgement=True`, uses `cryptography` AES-GCM with a fresh
96-bit nonce per object, and authenticates the safe metadata as associated
data. It has no update path; locator collisions, missing objects, expiry,
authentication failures, unsupported versions, and missing/wrong keys are
typed failures. Concurrent creation permits at most one success. Its backing
representation contains nonce, ciphertext, and safe authenticated metadata,
not plaintext request material.

This backend is not durable, not a production key-management solution, and is
not represented as production-secure. No plaintext file, Redis body, default
environment key, automatically generated production key, or fallback backend
exists. A separately reviewed durable encrypted vault and KMS integration is
still required.

### Atomic intent immutability and migration

New intent creation requires a complete binding whose execution, step, intent,
correlation, connector, target, fingerprint, creation deadline, and minimum
retention match the candidate intent. The authoritative Lua CAS rechecks those
creation identities and the absolute retention floor in the same invocation
that writes the intent.

For every later normal, runner-resolution, recovery-claim, and
recovery-resolution transition, Lua performs deep equality on the complete
binding and rejects addition, removal, or any change. This includes locator,
fingerprint, digest, versions, key IDs, correlation, execution/intent
identity, and all deadlines. The final Lua preflight now compares both the
digest and the complete canonical candidate binding with the authoritative
Redis binding. A controlled valid-looking safe-descriptor replacement is
therefore rejected before provider transport.

Legacy records without a binding remain readable and may undergo the existing
read-only reconciliation/state-machine handling, but preflight rejects them
for mutation transport. Lua rejects adding a reconstructed binding to a
legacy intent. There is no automatic backfill, locator regeneration, log-based
reconstruction, or silent historical commitment rewrite.

### Verified dispatch sequence

The test-only write-ahead runner now:

1. validates the strict request and the single endpoint profile;
2. constructs exact canonical immutable bytes;
3. constructs typed safe semantics and protected commitments;
4. computes the semantic fingerprint;
5. creates the vault object once and performs exact authenticated readback;
6. computes the attempt binding and atomically creates the intent;
7. obtains the existing same-connection durability acknowledgement;
8. runs the existing raw-state/lease/version/status/TTL preflight plus full
   binding comparison;
9. retrieves and authenticates the vault object and recomputes descriptor,
   commitments, fingerprint, and binding digest using persisted versions;
10. constructs `VerifiedDispatch`, whose exact bytes and binding are frozen;
11. calls the connector only as `mutate(dispatch=VerifiedDispatch, ...)`;
12. follows the existing resolution CAS and durability sequence.

The connector no longer accepts a target, headers, body, request dictionary,
or replacement request at the final transport boundary. The caller-mutation
test changes every original mutable container immediately after vault creation
and proves the transmitted bytes remain the original vault bytes. Connector
exceptions remain ambiguous and result in one provider call, never an
automatic transport retry.

Production startup always rejects dispatch. Setting the explicit test gate is
insufficient by itself: both vault and connector must also identify themselves
as test-only. A real durability barrier is still required unless the separate
test-barrier acknowledgement is explicit.

### P2-010 safe-value enforcement

The following repository-defined paths now use typed allowlists or fixed reason
codes:

- recursively typed request fields/options and exact protected classes;
- redacted target validation;
- intent actor, reason, observation, external-reference, and evidence models;
- provider evidence reduction to declared enum values;
- quarantine reason classes and bounded length/encoding metadata only;
- safe exception wrapping with no unrestricted message or cause chain;
- logger arguments containing safe execution/reason/failure-class values only;
- safe `repr`/string output for request, keyring, vault, vault-read,
  prepared-mutation, and verified-dispatch objects.

Quarantine no longer duplicates raw state in Base64 or any other encoding.
Controlled invalid-state tests prove raw protected material is absent from the
raised exception, exception cause, logs, and quarantine record. Provider
result canaries are dropped rather than entering evidence or state. Happy-path
privacy tests cover credentials/authorization, cookies, tokens, payment data,
and personal identifiers; their values are absent from exact Redis bytes,
transition history, safe descriptors, fingerprints, binding documents, logs,
object representations, and the encrypted vault backing representation. They
appear only in an explicitly authorized decrypted exact-vault read.

### Compatibility and fixture changes

No test was removed, skipped, weakened, or conditionally bypassed. Existing
fixtures changed only where the newly mandatory contract required it:

- runner fixtures now supply a test binding service and `ExactMutationRequest`;
- intent fixtures prepare a valid vault-backed binding before creation;
- direct preflight fixtures supply the complete candidate binding;
- the mock connector accepts only `VerifiedDispatch`, while readback accepts
  only `ReconciliationContext`;
- quarantine assertions now check safe presence/length/encoding metadata and
  the absence of a raw payload.

The original transition, crash, race, provider-count, durability-ordering,
strict UTF-8, duplicate-member, Phase 1 CAS, recovery, and WAITAOF assertions
remain. Valid Phase 1 operations, valid Phase 2 state, all existing legal
transitions, legacy inspection, Phase 1 replacement protection, same-connection
CAS/WAITAOF ordering, and provider-after-durability ordering all pass.

### Verification commands and exact results

All commands selected dedicated Redis DB 15 and test cleanup deleted only
scanned `aep:*` keys.

Final all-file compilation used a validated short path beneath `C:\tmp`, then
removed only that directory:

```powershell
$compileDir='C:\tmp\aep-p2-binding-pyc-final2'; $resolved=[IO.Path]::GetFullPath($compileDir); $allowed=[IO.Path]::GetFullPath('C:\tmp\'); if(-not $resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'unsafe compile path'}; if(Test-Path -LiteralPath $resolved){throw 'compile path already exists'}; New-Item -ItemType Directory -Path $resolved | Out-Null; $env:PYTHONPYCACHEPREFIX=$resolved; $pyFiles=@(Get-ChildItem -LiteralPath 'src','tests' -Recurse -Filter '*.py' | Select-Object -ExpandProperty FullName); py -3 -m py_compile @pyFiles; $compileExit=$LASTEXITCODE; $artifactCount=(Get-ChildItem -LiteralPath $resolved -Recurse -File | Measure-Object).Count; "py_files=$($pyFiles.Count)"; "py_compile_exit_code=$compileExit"; "compiled_artifacts=$artifactCount"; Remove-Item -LiteralPath $resolved -Recurse -Force; "temp_removed=$(-not (Test-Path -LiteralPath $resolved))"; exit $compileExit
```

Exit `0`: `py_files=38`, `py_compile_exit_code=0`,
`compiled_artifacts=75`, `temp_removed=True`.

Two preliminary compile-wrapper attempts were not used as evidence: the first
short-path attempt was denied by the sandbox (`exit 1`, zero artifacts), and a
workspace-local cache prefix exceeded the effective Windows path limit partway
through (`exit 1`, 58 artifacts, temporary directory removed). The identical
all-file compile succeeded after the authorized short-path rerun above.

Phase 1 storage/CAS:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_cas_write.py tests/test_get_migration.py tests/test_races.py tests/test_uuid_validation.py tests/test_version_range.py -p no:cacheprovider -q
```

Exit `0`: `32 passed in 0.96s`.

Focused Phase 2:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_mock_connector.py tests/test_phase2_durability.py tests/test_phase2_state_machine.py tests/test_phase2_runner.py tests/test_phase2_recovery.py -p no:cacheprovider -q
```

Exit `0`: `163 passed in 4.75s`.

Combined P0 regression matrix:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_mutation_safety.py tests/test_phase2_duplicate_member_safety.py -p no:cacheprovider -q
```

Exit `0`: `45 passed in 2.92s`.

State-codec and authoritative Lua validation matrix:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_state_codec.py tests/test_phase2_duplicate_member_safety.py -p no:cacheprovider -q
```

Exit `0`: `152 passed in 2.49s`.

Raw-state gate matrix:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_raw_state_validation_gate.py -p no:cacheprovider -q
```

Exit `0`: `26 passed in 1.63s`.

Canonicalization, fingerprint, commitment, and binding-digest suite:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_request_canonicalization.py -p no:cacheprovider -q
```

Exit `0`: `30 passed in 1.13s`.

Vault and safe-value/verified-dispatch suite:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_request_vault.py tests/test_verified_dispatch.py -p no:cacheprovider -q
```

Exit `0`: `20 passed in 0.98s`.

Binding immutability and controlled-race suite:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_request_binding_intents.py tests/test_races.py tests/test_phase2_mutation_safety.py -p no:cacheprovider -q
```

Exit `0`: `55 passed in 3.42s`.

Complete integration-enabled suite:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests -p no:cacheprovider -q
```

Exit `0`: `497 passed in 34.69s`; no failures or skips.

Standalone Redis 7.2 WAITAOF suite:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_waitaof_integration.py -p no:cacheprovider -q
```

Exit `0`: `4 passed in 6.19s`.

Explicit accepted and rejected end-to-end dispatch cases:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_verified_dispatch.py -p no:cacheprovider -q
```

Final rerun exit `0`: `13 passed in 0.89s`.

### Controlled altered-state and counter results

| Case | Intent state | Provider calls | Durability acknowledgements |
|---|---:|---:|---:|
| unsafe request or disabled production composition | no new intent | 0 | 0 |
| valid verified dispatch and confirmed resolution | confirmed bound intent | 1 | 2 |
| missing/expired/unauthenticated vault after durable creation | original `ABOUT_TO_FIRE` binding unchanged | 0 | 1 historical creation acknowledgement; 0 additional |
| endpoint-profile mismatch after durable creation | original `ABOUT_TO_FIRE` binding unchanged | 0 | 1 historical creation acknowledgement; 0 additional |
| controlled valid-looking Redis binding replacement | injected bytes preserved after rejection | 0 | 1 historical creation acknowledgement; 0 additional |
| connector raises after the one transport attempt | `FIRED_UNCONFIRMED` | 1 | 2; no second provider attempt |

Vault collisions/overwrite, wrong key, expiry, altered ciphertext/AAD,
transplant, locator/fingerprint/digest/key/deadline changes, binding removal,
legacy binding addition, shortened retention, strict JSON/UTF-8 failures, lock
loss, stale version/status, and ambiguous raw state all fail closed. Late
resolution tests continue to count calls that occurred before controlled state
replacement separately from zero post-rejection increments.

### Redis and protected-document verification

Final read-only checks reported:

```text
selected_db=15
redis_version=7.2.5
aof_enabled=1
appendonly=yes
appendfsync=everysec
aep_key_count=0
dbsize=0
flushall_commandstat=absent
```

No verification command or fixture invoked `FLUSHALL`.

The protected review hashes remained identical to the pre-change inventory:

```text
2F0333691DC00EA9ED632CE33009348113EBB7F37F32CFEE5B1A8E3114DC48E8  docs/07-phase2-gap-audit.md
65DBBC52647D9364BFCDA6A0AA1D53287C1DCF5E3A9F1135164E95D6090694DD  docs/09-post-waitaof-gate-review.md
963A9C43476340BC9584B33306876C502B6A4C82715A9BEB048D7DD2FFF6935B  docs/10-p0-closure-review.md
9F2FFA41C7825FBE7FA742DABE64E2F8D38434120E3589594BD7197435A25D35  docs/11-json-closure-gate-review.md
82A2172D454524F8ED544B8E28C571F42158F8771DE5182281B6332A8DD51622  docs/12-raw-state-gate-closure-review.md
```

The privacy tests assert that every seeded protected-category canary is absent
from prohibited Redis, history, quarantine, log, exception, fingerprint,
binding, descriptor, evidence, object-representation, snapshot, and generated
report outputs. No seeded canary literal is included in this report.

### Classification and residual limitations

| Finding | Classification | Repository evidence | Production applicability |
|---|---|---|---|
| P2-004 immutable request binding | **PARTIALLY CLOSED** | Every repository test mutation is derived only from authenticated vault bytes reverified against one immutable Redis binding; atomic Lua transition/preflight checks and zero-call altered-state tests pass | **NO-GO / OPEN production integration:** only a test-only in-memory vault and mock connector exist; no durable production vault/KMS/backend |
| P2-010 redaction and safe-value enforcement | **PARTIALLY CLOSED** | Recursive typed allowlists, protected commitments, safe exceptions/logging/quarantine/evidence, and privacy-canary tests cover all repository-defined paths | **NO-GO / OPEN production integration:** production connectors and their endpoint-specific response/reference schemas, production vault backend, and operational key management are absent |

Neither finding is classified `CLOSED` because the repository cannot provide a
production-capable encrypted vault/key-management backend or production
connector composition without inventing unsafe key management. No regression
was introduced in the verified P2-001/P2-002/P2-003 or Phase 1 gates.

Python immutable objects and third-party cryptographic implementations do not
provide a reliable application-level memory-erasure guarantee. This work does
not claim memory zeroization. It also does not claim exactly-once external
effects, Redis/provider atomicity, split-brain prevention, guaranteed duplicate
prevention, or multi-node coordination. Redis CAS and WAITAOF remain sequential
commands on one pinned connection, and WAITAOF proves only the tested local AOF
acknowledgement.

The bounded guarantee remains:

> Ambiguity, corruption, and contention are detectable; the system fails closed.

## 2026-07-30 addendum: raw-state validation gate closure

### Scope and files changed

This addendum supersedes only the raw-state acceptance claims in section 13.
It implements the two remaining defects identified by
`docs/11-json-closure-gate-review.md`. No immutable request binding, request
vault, connector registry, scheduler, operator API, telemetry, or unrelated P2
finding was implemented.

Exact implementation and regression files changed:

- `src/core/state_codec.py`
- `src/core/storage.py`
- `src/core/intents.py`
- `tests/test_state_codec.py`
- `tests/test_raw_state_validation_gate.py` (new)
- `phase2_implementation_report.md`

The workflow, recovery, durability, and lock modules were inspected but did not
require production edits because creation, runner resolution, recovery claim,
and recovery resolution all reuse the shared Phase 2 CAS, while lock
release/renew never read execution state. The four historical review documents
remained unchanged.

### Test-first evidence

The strict UTF-8, validation-order, typed-result, raw-read, and controlled-race
tests were added before production code changed. This command compiled the two
new/expanded test files and then ran them against Redis DB 15:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m py_compile tests\test_state_codec.py tests\test_raw_state_validation_gate.py; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; py -3 -m pytest tests\test_state_codec.py tests\test_raw_state_validation_gate.py -p no:cacheprovider -q
```

Exit `1`, unedited summary: `51 failed, 111 passed in 9.38s`. The failures
covered all invalid-byte Lua cases, decoded-client invalid UTF-8 reads, typed
candidate failures, validation precedence, and post-read mutation races. This
was the expected failing baseline.

### Lua UTF-8 validator design

`aep_utf8_check` walks the exact Redis/Lua string one byte at a time before any
JSON parsing. It accepts ASCII directly and permits only these multibyte ranges:

- `C2-DF` followed by one continuation byte;
- `E0 A0-BF`, `E1-EC 80-BF`, `ED 80-9F`, or `EE-EF 80-BF`, each with the
  required final continuation byte;
- `F0 90-BF`, `F1-F3 80-BF`, or `F4 80-8F`, each with two final continuation
  bytes.

Every other leading byte, missing continuation, isolated continuation,
overlong form, UTF-8 encoded surrogate, and value above U+10FFFF returns the
shared invalid result. The scan covers the complete raw document, so member
names, values, nested objects/arrays, and objects inside arrays receive the same
validation. Only after this byte pass does the existing recursive JSON scanner
perform duplicate-member detection; only after that scan does `cjson.decode`
prove final JSON syntax. Escaped JSON Unicode remains ASCII at the byte gate and
continues through the existing JSON decoder. The duplicate-member behavior and
the existing 128-level Lua nesting cap were retained.

### Raw-before-lock validation order

All three repository-defined state-interpreting scripts now follow one order:

1. fetch the stored raw execution state;
2. handle absence (allowed only for a Phase 1 first write; rejected by Phase 2
   CAS and preflight);
3. validate strict UTF-8;
4. detect duplicate members;
5. validate JSON syntax;
6. validate the candidate raw serialization where the operation has one;
7. only then inspect lock value/TTL, version, status, ledger, marker,
   transition, predecessor, or retention data;
8. perform an eligible mutation.

Phase 1 CAS, shared Phase 2 CAS, and read-only preflight therefore classify
invalid or ambiguous stored serialization before stale/missing tokens, short
lease TTL, stale versions, or status/ledger decisions. Candidate validation is
also inside each authoritative mutating Lua call. Valid-state stale-token and
stale-version ordering is unchanged.

### Typed result and application-read behavior

The three scripts share centrally translated raw-boundary codes:

| Code | Stable classification |
|---|---|
| `-10` | invalid UTF-8 or malformed stored JSON -> `StateCorruptionError` |
| `-11` | duplicate stored object member -> `AmbiguousStateError` |
| `-12` | invalid/malformed candidate -> `StateSerializationError` |
| `-13` | duplicate-member candidate -> `StateSerializationError` |

`lua_state_validation_failure` is the sole code-to-domain mapping, and
`RedisStorageAdapter._raise_lua_state_validation` applies the associated
best-effort quarantine policy. Normal callers never receive these numeric
codes or raw Lua strings. Errors contain no raw persisted bytes.

`RedisStorageAdapter.get_state` now issues `GET` with redis-py's
`NEVER_DECODE`, then passes exact bytes through the central `decode_state`
codec before migration or model construction. A client-side Unicode decoding
failure is independently translated to `StateCorruptionError`. Quarantine
remains best effort and does not modify the state key; invalid bytes are placed
in the bounded poison record as base64 rather than emitted in exceptions or
logs. Invalid state is never normalized, rewritten, deleted, or classified as
proof that provider retry is safe.

### Regression matrix

The shared codec/Lua matrix now includes:

- byte `FF`, isolated `80`/`BF`, `C0`/`C1`, overlong two-, three-, and
  four-byte forms, truncated two-/three-/four-byte sequences, both surrogate
  boundaries, U+110000, every illegal lead byte `F5-FF`, and invalid bytes in
  root/nested/array-object keys and values;
- ASCII plus lower/upper boundaries for two-, three-, and four-byte UTF-8,
  pre/post-surrogate boundaries, U+10FFFF, Urdu, Chinese, accented text,
  emoji, and escaped Unicode JSON;
- all existing duplicate-member locations and escaped-equivalent names;
- valid historical Phase 1/Phase 2 envelopes and false-positive controls;
- malformed JSON, NaN, and Infinity rejection.

The new integrated matrix covers Phase 1 and Phase 2 candidate failures,
decoded-client invalid bytes, corruption/ambiguity precedence for all three
scripts, exact raw-byte and elapsed-time-only TTL preservation, and direct
provider/durability/readback counters.

### Controlled race results

| Controlled case | Result and direct counter evidence |
|---|---|
| Phase 1 `save_state` after invalid UTF-8 injection | `StateCorruptionError`; exact injected bytes and version 1 remain; TTL does not refresh. |
| Phase 2 creation after post-read injection | `StateCorruptionError`; empty ledger/version 1 remain byte-for-byte. |
| PAUSED status replaced by invalid UTF-8 after both application reads | `StateCorruptionError`; injected PAUSED envelope, empty ledger, and version 1 remain; provider `0`; durability acknowledgements `0`; no TTL refresh. |
| Phase 2 transition after post-read injection | `StateCorruptionError`; injected bytes, ledger, transition history, and version remain unchanged. |
| Preflight with stale token | corruption/ambiguity wins before token, version, or status interpretation; read-only state/TTL preservation passes. |
| Preflight with insufficient lock TTL | corruption/ambiguity wins before TTL, stale version, or status interpretation; read-only state/TTL preservation passes. |
| Recovery claim after post-read injection | provider mutations `0`; readbacks `0`; durability acknowledgements `0`; exact injected state remains. |
| Runner resolution after post-read injection | the one provider call and one creation durability acknowledgement occur before the deliberately late injection; the rejection adds `0` provider calls and `0` resolution acknowledgements; injected state remains exact. |
| Recovery resolution after post-read injection | provider mutations `0`; one readback occurs before the deliberately late injection; durability acknowledgements `0`; injected state remains exact. |
| Valid Phase 1 update and Phase 2 creation | passes with Urdu, Chinese, accented, and emoji context; final version 3 and intent `ABOUT_TO_FIRE`. |

All pre-dispatch rejected runner paths, including the PAUSED controlled race,
produce zero provider calls and zero durability acknowledgements. The
resolution test separately records the operations that necessarily preceded
its post-provider injection and proves that rejection adds none.

### Exact verification record

Two isolated-cache wrappers failed before the successful compile check. They
are recorded to avoid omitting unavailable results:

1. The `C:\tmp\aep-raw-state-gate-pyc-20260730` wrapper exited `1` because
   `New-Item` was denied; summary:
   `py_files=31`, `py_compile_exit_code=1`, `compiled_artifacts=0`,
   `temp_removed=True`.
2. The workspace-local `.aep-raw-state-gate-pyc-20260730` wrapper exited `1`
   after Windows generated an overlong cache path; summary:
   `py_files=31`, `py_compile_exit_code=1`, `compiled_artifacts=55`,
   `temp_removed=True`.

The successful compilation command was:

```powershell
$compileDir=Join-Path $env:TEMP 'aep-pyc-0730'; $resolved=[IO.Path]::GetFullPath($compileDir); $allowed=[IO.Path]::GetFullPath($env:TEMP + [IO.Path]::DirectorySeparatorChar); if(-not $resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'unsafe compile path'}; if(Test-Path -LiteralPath $resolved){throw 'compile temp path already exists'}; New-Item -ItemType Directory -Path $resolved | Out-Null; $env:PYTHONPYCACHEPREFIX=$resolved; $pyFiles=@(Get-ChildItem -LiteralPath 'src','tests' -Recurse -Filter '*.py' | Select-Object -ExpandProperty FullName); py -3 -m py_compile @pyFiles; $exitCode=$LASTEXITCODE; "py_files=$($pyFiles.Count)"; "py_compile_exit_code=$exitCode"; "compiled_artifacts=$((Get-ChildItem -LiteralPath $resolved -Recurse -File | Measure-Object).Count)"; Remove-Item -LiteralPath $resolved -Recurse -Force; "temp_removed=$(-not (Test-Path -LiteralPath $resolved))"; exit $exitCode
```

Exit `0`: `py_files=31`, `py_compile_exit_code=0`,
`compiled_artifacts=68`, `temp_removed=True`.

Phase 1 storage/CAS:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests\test_cas_write.py tests\test_get_migration.py tests\test_races.py tests\test_uuid_validation.py tests\test_version_range.py -p no:cacheprovider -q
```

Exit `0`: `32 passed in 1.52s`.

Focused Phase 2:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests\test_mock_connector.py tests\test_phase2_durability.py tests\test_phase2_state_machine.py tests\test_phase2_runner.py tests\test_phase2_recovery.py -p no:cacheprovider -q
```

Exit `0`: `163 passed in 6.27s`.

Combined P0 regression matrix:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests\test_phase2_mutation_safety.py tests\test_phase2_duplicate_member_safety.py -p no:cacheprovider -q
```

Exit `0`: `45 passed in 3.96s`.

State-codec and Lua validation matrix:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests\test_state_codec.py -p no:cacheprovider -q
```

Exit `0`: `142 passed in 3.07s`.

New UTF-8, validation-order, and controlled-race matrix:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests\test_raw_state_validation_gate.py -p no:cacheprovider -q
```

Exit `0`: `26 passed in 2.42s`.

Complete integration-enabled suite:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests -p no:cacheprovider -q
```

Exit `0`: `431 passed in 42.55s`; no failures or skips.

Standalone Redis 7.2 WAITAOF suite:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests\test_phase2_waitaof_integration.py -p no:cacheprovider -q
```

The sandboxed attempt exited `1` with `3 passed, 1 failed in 6.95s`; the sole
failure was Docker daemon `Access is denied` during the controlled restart.
The approved rerun of the identical command exited `0` with
`4 passed in 8.43s`.

Explicit controlled-race selection:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests\test_raw_state_validation_gate.py::test_phase1_save_rejects_invalid_utf8_without_replacement_or_ttl_refresh tests\test_raw_state_validation_gate.py::test_phase2_creation_rejects_post_read_invalid_utf8_injection tests\test_raw_state_validation_gate.py::test_paused_runner_race_preserves_injected_state_with_zero_side_effects tests\test_raw_state_validation_gate.py::test_phase2_transition_rejects_post_read_invalid_utf8_injection tests\test_raw_state_validation_gate.py::test_preflight_raw_failure_precedes_token_ttl_version_and_status tests\test_raw_state_validation_gate.py::test_recovery_claim_rejects_post_read_invalid_state_before_readback_or_ack tests\test_raw_state_validation_gate.py::test_runner_resolution_rejects_post_read_invalid_state_before_ack tests\test_raw_state_validation_gate.py::test_recovery_resolution_rejects_post_read_invalid_state_before_ack tests\test_raw_state_validation_gate.py::test_valid_phase1_and_phase2_operations_pass_after_raw_gate -p no:cacheprovider -q
```

Exit `0`: `12 passed in 1.42s`.

All successful pytest commands emitted only the existing `pytest-asyncio`
fixture-loop-scope deprecation warning.

Final Redis verification and namespace-only cleanup:

```powershell
py -3 -c "import redis; r=redis.Redis.from_url('redis://127.0.0.1:6381/15',decode_responses=True); keys=list(r.scan_iter(match='aep:*',count=500)); deleted=r.delete(*keys) if keys else 0; server=r.info('server'); persistence=r.info('persistence'); config=r.config_get('append*'); stats=r.info('commandstats'); remaining=list(r.scan_iter(match='aep:*',count=500)); print('selected_db=15'); print('redis_version='+server['redis_version']); print('aof_enabled='+str(persistence['aof_enabled'])); print('appendonly='+config.get('appendonly','')); print('appendfsync='+config.get('appendfsync','')); print('aep_keys_before_cleanup='+str(len(keys))); print('aep_keys_deleted='+str(deleted)); print('aep_keys_after_cleanup='+str(len(remaining))); print('dbsize='+str(r.dbsize())); print('flushall_commandstat_present='+str('cmdstat_flushall' in stats).lower()); r.close()"
```

Exit `0`:

```text
selected_db=15
redis_version=7.2.5
aof_enabled=1
appendonly=yes
appendfsync=everysec
aep_keys_before_cleanup=0
aep_keys_deleted=0
aep_keys_after_cleanup=0
dbsize=0
flushall_commandstat_present=false
```

No implementation, fixture, or verification command used `FLUSHALL`.

### Compatibility and decoder inventory evidence

- Valid historical Phase 1 state remains readable and writable; Phase 1 is
  `32/32` and the new multilingual Phase 1 update passes.
- Valid historical Phase 2 envelopes remain readable; normal creation, every
  legal transition, runner, recovery, and the focused `163/163` suite pass.
- Legacy unmarked non-empty ledgers remain protected from Phase 1 replacement.
- Duplicate-member rejection remains effective at every previously covered
  location and now retains precedence under stale/missing leases.
- Malformed JSON, NaN, Infinity, invalid UTF-8, and schema-invalid state all
  fail closed; valid Unicode boundaries and multilingual values pass.
- Existing valid-state stale-token/stale-version semantics pass unchanged.
- Same-connection CAS -> WAITAOF -> provider -> CAS -> WAITAOF ordering and
  controlled restart persistence pass unchanged.
- Repository-wide searches for `json.loads`, `decode_state`, `cjson.decode`,
  `register_script`, and `aep:state:` find no alternative production state
  decoder or writer. Recovery discovery delegates to `get_execution`; lock
  scripts do not interpret state.

### Residual limitations, classifications, and dispatch status

- The pre-existing Lua nesting limit remains 128. This is a residual
  compatibility limit for otherwise valid historical JSON deeper than 128.
- Quarantine remains best effort and scheduling ejection remains outside this
  repository.
- Redis CAS and WAITAOF remain sequential commands on one pinned connection;
  the tests establish only the reported local AOF acknowledgement behavior.
- Redis state and external providers remain separate systems. No exactly-once
  external-effect, absolute-atomicity, split-brain-prevention, or guaranteed-
  duplicate-prevention claim is made.

| Finding | 2026-07-30 classification | Bounded closure evidence |
|---|---|---|
| P2-001 unsafe retry eligibility | **CLOSED for the repository-defined raw-state gate scope** | strict UTF-8 and duplicate validation precede lease/version/predecessor decisions in every authoritative path; post-read injections cannot create a retry-eligible mutation; rejected pre-dispatch paths have zero provider/durability calls |
| P2-002 execution-wide ambiguity fence | **CLOSED for the repository-defined raw-state gate scope** | the PAUSED invalid-status race preserves exact injected state, version, ledger, and retention with provider `0` and durability `0`; no conflicting state interpreter remains |
| P2-003 Phase 1 replacement protection | **CLOSED for the repository-defined raw-state gate scope** | Phase 1 validates stored raw state before lease/version/marker/ledger/retention and rejects invalid UTF-8 without replacement, version advancement, or TTL refresh |

These classifications do not close any unrelated P2 finding. Production
non-idempotent dispatch remains disabled.

The bounded guarantee remains:

> “Ambiguity, corruption, and contention are detectable; the system fails closed.”

### Protected review hashes

The protected documents retained their initial SHA-256 values:

```text
2F0333691DC00EA9ED632CE33009348113EBB7F37F32CFEE5B1A8E3114DC48E8  docs/07-phase2-gap-audit.md
65DBBC52647D9364BFCDA6A0AA1D53287C1DCF5E3A9F1135164E95D6090694DD  docs/09-post-waitaof-gate-review.md
963A9C43476340BC9584B33306876C502B6A4C82715A9BEB048D7DD2FFF6935B  docs/10-p0-closure-review.md
9F2FFA41C7825FBE7FA742DABE64E2F8D38434120E3589594BD7197435A25D35  docs/11-json-closure-gate-review.md
```

---

## 13. Duplicate-JSON-member P0 closure (2026-07-29)

This section supersedes only the duplicate-member limitation recorded by
`docs/10-p0-closure-review.md`. It does not revise that historical review and
does not implement the request vault, connector registry, scheduler, operator
API, telemetry, or any other P2 finding.

### Exact files changed

- `src/core/exceptions.py`
- `src/core/state_codec.py` (new)
- `src/core/storage.py`
- `src/core/intents.py`
- `tests/test_state_codec.py` (new)
- `tests/test_phase2_duplicate_member_safety.py` (new)
- `phase2_implementation_report.md`

The three protected review documents were not edited.

### Investigation result

The source and test inventory found one application read path and three Lua
consumers of persisted execution JSON:

1. `RedisStorageAdapter.get_state` read raw Redis text with `json.loads`.
   `IntentLedgerStore.get_execution`, runner creation, recovery scanning,
   recovery claiming, and existing internal/manual resolution all pass through
   this adapter before typed model interpretation.
2. The Phase 1 `save_state` CAS decoded the stored value and candidate with
   `cjson.decode`.
3. The Phase 2 intent CAS decoded the stored value and candidate with
   `cjson.decode`. This one CAS is shared by normal creation, every intent
   transition, runner resolution, recovery claim, recovery resolution, and the
   existing internal/manual resolution surface. It is also the retention-
   changing Phase 2 writer.
4. The Phase 2 pre-dispatch preflight decoded the stored value with
   `cjson.decode` before checking version and `ABOUT_TO_FIRE`.

No other `src` execution-state decoder or Lua state decoder was found. Lock Lua
scripts do not read execution JSON. The only remaining direct `json.dumps` in
`src/core/intents.py` canonicalizes evidence solely for a SHA-256 input; it does
not serialize execution state. Test-only historical fixture injection remains
explicitly outside application serialization.

Before this change, each of the four paths converted raw Redis JSON into a map
only after duplicate names had been discarded. Recovery and resolution did not
have separate scripts; they inherited the lossy Phase 2 read/CAS behavior.

### State-codec design

`src/core/state_codec.py` is now the central codec.

- `decode_state` accepts strict UTF-8 text/bytes and supplies an
  `object_pairs_hook`, so decoded member names are compared before that object
  becomes an ordinary dictionary. JSON escape processing therefore makes a
  literal name and a Unicode-escaped equivalent collide. Equal and conflicting
  duplicates raise the stable `AmbiguousStateError`, a subtype of
  `StateCorruptionError`. Malformed JSON, invalid UTF-8, nonstandard
  `NaN`/`Infinity` tokens, and non-finite parsed floats remain typed corruption.
- `encode_state` is the single application execution-state serializer. It uses
  `ensure_ascii=False`, `allow_nan=False`, sorted keys, compact `(',', ':')`
  separators, and a strict UTF-8 encodability check. It raises
  `StateSerializationError` rather than emitting NaN, Infinity, invalid
  Unicode, or a nondeterministically serializable value.
- Phase 1 and Phase 2 writes serialize `model_dump(mode="json")` only through
  `encode_state`. Quarantine envelopes also use it. Deterministic serialization
  is not treated as evidence that previously stored bytes were unambiguous.

Read-path duplicate rejection writes a best-effort poison record with reason
`ambiguous-serialization`, preserves the original state key, and raises
`AmbiguousStateError`. Neither the state nor raw Redis/Lua exception text is put
in the caller-visible error. Full persisted state is not logged. The existing
forensic quarantine value remains stored under the bounded poison-key policy.
The exception documentation explicitly says that it never authorizes repeating
an external provider mutation.

### Shared atomic Lua validation

`build_lua_state_validation_script` prefixes each state script with the same
recursive-descent raw JSON validator. Redis 7.2's embedded `cjson` does not
preserve duplicate member pairs, so the validator scans exact bytes before any
semantic `cjson.decode`:

- it distinguishes object/array structure from quotes, braces, commas, colons,
  backslashes, and escapes inside strings;
- it keeps a separate decoded-name set for every object at every depth;
- it locates a complete member-name string token, decodes that token with
  `cjson`, and compares the decoded bytes, closing escaped-equivalent bypasses;
- it recurses through objects inside arrays and through arbitrary metadata;
- it lexes JSON numbers/literals and rejects malformed/non-finite input;
- it caps nesting at 128 and returns invalid state rather than risking an
  unbounded Lua stack;
- after the raw scan, it requires a successful full `cjson.decode` before
  returning valid.

The shared return contract is `0` valid, `1` ambiguous duplicate, and `-1`
invalid JSON. Phase 1 CAS maps ambiguity to `-5`, the Phase 2 CAS to `-9`, and
preflight to `-6`; Python maps each to the same quarantined
`AmbiguousStateError`. The validator runs on both stored and candidate JSON in
each write CAS and on stored JSON in preflight. No script semantically reads the
state before this check. Lock ownership and lease TTL checks retain their prior
precedence because they do not interpret execution JSON.

This provides atomic enforcement for:

| Path | Atomic duplicate check | Regression evidence |
|---|---|---|
| Phase 1 `save_state` CAS and retention change | stored and candidate raw JSON | P2-003 integrated reproduction |
| Phase 2 creation CAS | stored and candidate raw JSON | post-Python-read injection test |
| Every Phase 2 transition CAS | stored and candidate raw JSON | post-Python-read transition injection test |
| Runner/internal resolution | shared transition CAS | transition injection plus existing runner suite |
| Recovery claim and resolution | shared transition CAS | recovery read rejection plus existing recovery suite |
| Final pre-dispatch preflight | stored raw JSON | direct preflight ambiguous-state test |

The post-read injection tests are controlled TOCTOU regressions: Python first
receives valid typed state, the Redis bytes are then replaced with an equal
duplicate `version` member (so a lossy decoder would see the identical original
map), and the authoritative Lua invocation rejects without writing. Thus a
Python-only pre-check cannot satisfy these tests.

### TDD record

The two new test modules were added before the exception/codec implementation.
The initial command was:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_state_codec.py tests/test_phase2_duplicate_member_safety.py -p no:cacheprovider -q
```

It exited `1` during collection with exactly two errors: both modules could not
import the then-nonexistent `AmbiguousStateError`. After production changes, the
expanded combined codec/Lua/integration matrix passed `73 passed in 3.11s`.

### Complete duplicate-member regression matrix

Python and the exact Redis Lua component are each tested against the same raw
matrix:

| Required case | Checked serialization |
|---|---|
| Top-level execution status | duplicate `status`, conflicting values |
| Version | duplicate `version` |
| Phase 2 marker | duplicate `phase2_managed` with marker/null |
| Complete ledger | duplicate `intent_ledger`, identical empty values |
| Duplicate intent ID | same ledger member name with conflicting records |
| Intent status | blocking `ABOUT_TO_FIRE` plus nonblocking `FAILED_CONFIRMED` |
| Step and attempt | duplicate `step_id`; duplicate `attempt` |
| Transition history | duplicate `transitions`, identical values |
| Retention field | duplicate `reconcile_after` |
| Unknown member | duplicate unknown name with identical values |
| Escaped equivalence | `status` plus `statu\u0073` |
| Nested metadata | duplicate member in a nested metadata object |
| Object in array | duplicate member inside an array-contained object |

False-positive controls cover repeated array values, similar-but-distinct names,
quotes/braces/commas/colons inside strings, escaped quotes and backslashes,
empty objects and arrays, ordinary Unicode string values, and valid historical
Phase 1 and Phase 2 envelopes. A separate malformed matrix covers unterminated
objects/strings, missing delimiters, NaN, and Infinity and proves malformed
input remains distinct from duplicate-member ambiguity.

Serialization controls prove sorted compact Unicode output and rejection of
NaN, positive Infinity, and negative Infinity.

### Controlled closure reproductions

Exact command:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_duplicate_member_safety.py -k "p2001_duplicate or p2002_duplicate or p2003_duplicate" -p no:cacheprovider -q
```

Result: `5 passed, 5 deselected in 1.12s`. The complete integrated module,
including atomic injection, preflight, quarantine, and recovery controls, later
passed `10 passed in 1.87s` after strengthening both TOCTOU cases to equal
duplicates whose lossy decoded mappings match the original state.

- **P2-001:** a genuine first provider call reaches `FIRED_CONFIRMED`; the raw
  ledger is then replaced with duplicate serialization exposing a later
  `FAILED_CONFIRMED` view to a lossy decoder. The second same-step runner call
  raises `AmbiguousStateError`. Total provider calls stay at one, so there are
  zero additional calls. Durability-barrier calls for the rejected attempt are
  zero. Exact state bytes, version, intent count, and transition history are
  unchanged; TTL decreases only within elapsed-time tolerance.
- **P2-002:** separate cases hide `ABOUT_TO_FIRE`, `FIRED_UNCONFIRMED`, and
  `PERMANENTLY_AMBIGUOUS` behind duplicate nonblocking serialization; PAUSED
  cases also contain a duplicate top-level status so neither old fence remains
  visible to a lossy last-wins decoder. Different-step runner creation raises
  `AmbiguousStateError`, with zero provider calls, zero durability-barrier
  calls, exact byte/version/ledger/history preservation, and elapsed-time-only
  TTL change.
- **P2-003:** raw top-level duplicates put the real PAUSED status, Phase 2
  marker, and complete ledger first and IDLE/null/empty replacements last.
  Current-token/current-version Phase 1 `save_state` raises
  `AmbiguousStateError`. It cannot delete/replace the ledger, remove/change the
  marker, unpause the execution, install a ledger-free object, advance version,
  rewrite audit history, or reduce the roughly 31-day retention to 60 seconds.

Every ambiguity rejection occurs before the relevant CAS write returns success.
Runner creation rejection therefore occurs before WAITAOF confirmation and
before provider dispatch. Preflight also rejects ambiguous bytes before provider
dispatch. Quarantine may add a poison key but never rewrites or refreshes the
state key.

### Verification commands and exact results

Python compilation used a validated task-specific directory beneath `%TEMP%`
as `PYTHONPYCACHEPREFIX`, compiled every Python file under `src` and `tests`,
and then removed only that directory. Result:

```powershell
$compileDir=Join-Path $env:TEMP 'aep-duplicate-json-pyc-20260729'; $tempRoot=[IO.Path]::GetFullPath($env:TEMP); $resolved=[IO.Path]::GetFullPath($compileDir); if(-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'unsafe compile path'}; if(Test-Path -LiteralPath $resolved){Remove-Item -LiteralPath $resolved -Recurse -Force}; New-Item -ItemType Directory -Path $resolved | Out-Null; $env:PYTHONPYCACHEPREFIX=$resolved; $pyFiles=@(Get-ChildItem -LiteralPath 'src','tests' -Recurse -Filter '*.py' | Select-Object -ExpandProperty FullName); py -3 -m py_compile @pyFiles; $exitCode=$LASTEXITCODE; "py_files=$($pyFiles.Count)"; "py_compile_exit_code=$exitCode"; "compiled_artifacts=$((Get-ChildItem -LiteralPath $resolved -Recurse -File | Measure-Object).Count)"; Remove-Item -LiteralPath $resolved -Recurse -Force; "temp_removed=$(-not (Test-Path -LiteralPath $resolved))"; exit $exitCode
```

```text
py_files=30
py_compile_exit_code=0
compiled_artifacts=67
temp_removed=True
```

Phase 1 storage/CAS:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_cas_write.py tests/test_get_migration.py tests/test_races.py tests/test_uuid_validation.py tests/test_version_range.py -p no:cacheprovider -q
```

Result: `32 passed in 1.76s`.

Focused Phase 2:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_mock_connector.py tests/test_phase2_durability.py tests/test_phase2_state_machine.py tests/test_phase2_runner.py tests/test_phase2_recovery.py -p no:cacheprovider -q
```

Result: `163 passed in 7.12s`.

Combined P0 regression matrix:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_mutation_safety.py tests/test_phase2_duplicate_member_safety.py -p no:cacheprovider -q
```

Result: `44 passed in 4.38s`.

Standalone duplicate codec and Lua validation matrix:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_state_codec.py -p no:cacheprovider -q
```

Result: `63 passed in 1.20s`.

Complete integration-enabled suite:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests -p no:cacheprovider -q
```

Final rerun result: `326 passed in 35.57s`.

Standalone Redis 7.2 WAITAOF suite:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_waitaof_integration.py -p no:cacheprovider -q
```

Result: `4 passed in 9.53s`.

All pytest commands emitted only the existing `pytest-asyncio` fixture-loop
scope deprecation warning. The integration-enabled run had no failures or
skips. The same-connection CAS then WAITAOF ordering tests remain unchanged and
pass.

Final Redis verification and namespace-only cleanup used a synchronous Redis
client fixed to `redis://127.0.0.1:6381/15`, scanned only `aep:*`, and would
delete only those scanned keys. It found nothing to delete:

```powershell
py -3 -c "import redis; r=redis.Redis.from_url('redis://127.0.0.1:6381/15',decode_responses=True); keys=list(r.scan_iter(match='aep:*',count=500)); deleted=r.delete(*keys) if keys else 0; server=r.info('server'); persistence=r.info('persistence'); config=r.config_get('append*'); stats=r.info('commandstats'); remaining=list(r.scan_iter(match='aep:*',count=500)); print('selected_db=15'); print('redis_version='+server['redis_version']); print('aof_enabled='+str(persistence['aof_enabled'])); print('appendonly='+config.get('appendonly','')); print('appendfsync='+config.get('appendfsync','')); print('aep_keys_before_cleanup='+str(len(keys))); print('aep_keys_deleted='+str(deleted)); print('aep_keys_after_cleanup='+str(len(remaining))); print('dbsize='+str(r.dbsize())); print('flushall_commandstat_present='+str('cmdstat_flushall' in stats).lower()); r.close()"
```

```text
selected_db=15
redis_version=7.2.5
aof_enabled=1
appendonly=yes
appendfsync=everysec
aep_keys_before_cleanup=0
aep_keys_deleted=0
aep_keys_after_cleanup=0
dbsize=0
flushall_commandstat_present=false
```

No verification command or fixture used `FLUSHALL`.

SHA-256 was recorded before changes and recomputed after the final suite/report
update. All historical-review hashes were identical:

```text
2F0333691DC00EA9ED632CE33009348113EBB7F37F32CFEE5B1A8E3114DC48E8  docs/07-phase2-gap-audit.md
65DBBC52647D9364BFCDA6A0AA1D53287C1DCF5E3A9F1135164E95D6090694DD  docs/09-post-waitaof-gate-review.md
963A9C43476340BC9584B33306876C502B6A4C82715A9BEB048D7DD2FFF6935B  docs/10-p0-closure-review.md
```

### Compatibility evidence

- Valid Phase 1 create/read/update remains writable and the full Phase 1 suite
  passes.
- Valid Phase 2 creation, every legal state transition, runner resolution, and
  recovery continue to pass.
- Legacy non-empty Phase 2 ledgers without the marker remain protected by the
  Phase 1 writer and readable by the strict Phase 2 view when unambiguous.
- Malformed JSON remains quarantined and rejected; duplicate JSON gains the
  narrower `AmbiguousStateError` subtype.
- Existing stale-token and stale-version precedence tests pass unchanged.
- Same-connection CAS plus WAITAOF ordering and restart persistence pass.
- Rejected runner attempts perform neither durability acknowledgement nor
  provider dispatch. Direct CAS/preflight rejection preserves exact raw bytes
  and changes TTL only through normal elapsed time.

### Closure classifications

| Finding | Classification | Evidence |
|---|---|---|
| P2-001 unsafe retry eligibility | **CLOSED for all repository-defined read, creation, transition, preflight, and recovery paths** | duplicate intent IDs/statuses fail in Python and atomic Lua; controlled same-step attempt produces zero additional provider calls |
| P2-002 execution-wide ambiguity fence | **CLOSED for all repository-defined read, creation, transition, preflight, and recovery paths** | all three blocking statuses remain protected under duplicate serialization; different-step attempts produce zero provider calls |
| P2-003 Phase 1 `save_state` bypass | **CLOSED for all repository-defined state write paths** | atomic Phase 1 CAS rejects hidden marker/ledger/status before semantic interpretation or retention-changing SET |

These classifications close the duplicate-JSON-member acceptance gap only.
They do not classify unrelated P2 findings as closed.

### Residual limitations and production status

- The Lua validator deliberately rejects nesting beyond 128 as invalid state.
- Atomic Redis CAS and WAITAOF remain sequential commands on one connection;
  WAITAOF establishes only the tested local AOF acknowledgement.
- Redis and external providers remain separate systems. This work does not
  claim exactly-once external effects, absolute atomicity, split-brain
  prevention, or guaranteed duplicate prevention.
- Quarantine remains best-effort, and operator scheduling ejection remains an
  out-of-scope orchestration responsibility.
- The request vault, connector registry, scheduler, operator API, telemetry,
  authenticated resolution/risk acceptance, and other P2 findings remain
  unimplemented.

Production non-idempotent dispatch remains disabled. The bounded guarantee is:

> Ambiguity, corruption, and contention are detectable; the system fails closed.

## 2026-07-30 final report precedence note

The bounded P2-004/P2-010 addendum above was written after the implementation
and current verification. It supersedes legacy phrases anywhere in the older
raw-state addendum that say the request vault or P2-004/P2-010 repository
boundary is wholly unimplemented. It does not alter that addendum's P2-001,
P2-002, or P2-003 classifications.

The current final classifications are **P2-004: PARTIALLY CLOSED** and
**P2-010: PARTIALLY CLOSED**. Production non-idempotent dispatch remains
**NO-GO** because the only vault is test-only and no production vault/KMS or
production connector composition exists.

After the report update, an exact case-sensitive scan extracted 16 distinct
seeded canary tokens from test source and checked the generated implementation
report, review Markdown files, and pytest cache artifacts. Result:

```text
seeded_canary_tokens=16
prohibited_artifact_hits=0
```

The final bounded guarantee remains:

> Ambiguity, corruption, and contention are detectable; the system fails closed.

## 2026-07-31 final delivered-tree closure evidence and precedence

This end-of-file note records the final delivered tree for the detailed
`2026-07-31 addendum: canonical request-binding repository closure` above and
supersedes the older P2-004/P2-010 classifications that follow that detailed
section in historical 2026-07-30 material.

Final reruns after the implementation report and final runtime-marker scan were
present were:

```powershell
$ErrorActionPreference='Stop'; $compileDir='C:\tmp\aep-request-binding-closure-pyc'; $resolved=[IO.Path]::GetFullPath($compileDir); $allowed=[IO.Path]::GetFullPath('C:\tmp\'); if(-not $resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'unsafe compile path'}; if(Test-Path -LiteralPath $resolved){throw 'compile path already exists'}; New-Item -ItemType Directory -Path $resolved | Out-Null; try { $env:PYTHONPYCACHEPREFIX=$resolved; $pyFiles=@(Get-ChildItem -LiteralPath 'src','tests' -Recurse -Filter '*.py' | Select-Object -ExpandProperty FullName); py -3 -m py_compile @pyFiles; $compileExit=$LASTEXITCODE; $artifactCount=(Get-ChildItem -LiteralPath $resolved -Recurse -File | Measure-Object).Count; Write-Output "py_files=$($pyFiles.Count)"; Write-Output "py_compile_exit_code=$compileExit"; Write-Output "compiled_artifacts=$artifactCount" } finally { if(Test-Path -LiteralPath $resolved){ Remove-Item -LiteralPath $resolved -Recurse -Force }; Write-Output "temp_removed=$(-not (Test-Path -LiteralPath $resolved))" }; exit $compileExit
```

Exit `0`: `py_files=43`, `py_compile_exit_code=0`,
`compiled_artifacts=80`, `temp_removed=True`.

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_canonical_request_binding_closure.py tests/test_verified_dispatch_provenance.py tests/test_endpoint_profile_revalidation.py tests/test_vault_aad_closure.py tests/test_privacy_boundary_closure.py -p no:cacheprovider -q
```

Exit `0`: `93 passed in 1.43s`.

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_request_vault.py tests/test_vault_aad_closure.py tests/test_endpoint_profile_revalidation.py tests/test_privacy_boundary_closure.py -p no:cacheprovider -q
```

Exit `0`: `59 passed in 0.84s`.

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests -p no:cacheprovider -q
```

Exit `0`: `611 passed in 48.08s`, with zero failures and zero skips.

The final classifications are:

- repository enforcement: **VERIFIED**;
- P2-004: **CLOSED (repository scope)**;
- P2-010: **CLOSED (repository-defined Phase 2 mutation scope)**;
- production applicability: **NO-GO**; and
- production non-idempotent dispatch: **NO-GO**.

The production decisions remain `NO-GO` because a durable production vault/KMS
and reviewed production connector profile are absent. No exactly-once,
Redis/provider atomicity, split-brain prevention, guaranteed duplicate
prevention, guaranteed secret non-disclosure, or managed-memory erasure claim is
made.

The bounded guarantee is:

> Ambiguity, corruption, and contention are detectable; the system fails closed.
