# AEP P0 closure review: P2-001, P2-002, and P2-003

**Review date:** 2026-07-29  
**Review type:** Read-only controlled robustness closure audit  
**Audit target:** Redis 7.2.5, DB 15, AOF enabled, `appendfsync everysec`  
**Implementation claim tested:** all three P0 findings are closed  
**Result:** the claim is not sustained. P2-001, P2-002, and P2-003 are each **PARTIALLY CLOSED**.

## 1. Executive verdict

The new Lua branches correctly close the original defects for canonical, uniquely keyed JSON state produced by the repository APIs. Normal creation now rejects unsafe same-step predecessors, scans all decoded ledger entries for the execution-wide fence, refuses a raw `risk_acceptance_id`, preserves `PAUSED`, and makes the first Phase 2 marker write atomic. The Phase 1 CAS also checks the currently stored marker/non-empty ledger and rejects current-token/current-version replacement. The checked-in 35-test mutation-safety matrix passes, as do the Phase 1, focused Phase 2, complete integration, and standalone WAITAOF suites.

That is not full closure. Redis stores bytes, while both read/validation layers decode JSON into maps without rejecting duplicate object member names:

- Python uses `json.loads(raw)` in `RedisStorageAdapter.get_state` (`src/core/storage.py:570-574`).
- the authoritative creation/transition CAS uses `cjson.decode` (`src/core/intents.py:256-262`).
- the Phase 1 CAS separately uses `cjson.decode` for both candidate and current state (`src/core/storage.py:191-196,206-220`).

Both decoders retained the last duplicate member in the verified Redis 7.2.5 environment. An earlier member therefore disappears before any invariant is evaluated. Three independent safe probes demonstrated:

1. a hidden `FIRED_CONFIRMED` attempt 2 followed by a duplicate-key `FAILED_CONFIRMED` attempt 1 allowed another same-step attempt 2 and one provider call;
2. a hidden `ABOUT_TO_FIRE` entry followed by a duplicate-key `FAILED_CONFIRMED` entry allowed different-step creation and one provider call; and
3. top-level duplicate `phase2_managed` and `intent_ledger` members hid a real marker and non-empty ledger behind later `null`/empty values, allowing Phase 1 `save_state` to overwrite the record, clear its history, and shorten its TTL from about 31 days to 1 hour.

These are persisted-byte bypasses, not stale-token artifacts. The callers held current tokens and versions. The first two bypasses reached `WriteAheadRunner`'s provider call at `src/core/intent_workflow.py:314-318`. The third returned success from the Phase 1 CAS. No checked-in regression test supplies duplicate JSON object members; the test named “duplicate” at `tests/test_phase2_state_machine.py:328-372` uses two distinct intent IDs and therefore does not exercise this parser ambiguity.

Consequently, the required complete-ledger/ordering/marker proofs fail for duplicate persisted entries, raw bytes mutate on the unsafe accepted operations, and provider calls occur in the P2-001/P2-002 reproductions. The current implementation does not yet satisfy the bounded fail-closed guarantee for this class of corruption.

## 2. Scope and method

The audit inspected, without modifying, at least:

- `src/core/intents.py`
- `src/core/storage.py`
- `src/core/intent_workflow.py`
- `src/core/intent_recovery.py`
- `src/core/locks.py`
- `src/core/durability.py`
- `src/core/exceptions.py`
- `tests/test_phase2_mutation_safety.py`
- all Phase 1 storage/CAS, migration, race, UUID, version, lock, and lease tests
- all Phase 2 state-machine, runner, recovery, durability, mock-connector, and Redis integration tests
- `tests/conftest.py` and its DB-15 scoped cleanup
- `_CAS_SCRIPT`, `_INTENT_CAS_SCRIPT`, `_PREFLIGHT_SCRIPT`, `_RELEASE_SCRIPT`, and `_RENEW_SCRIPT`

The repository's `.git` directory is empty, so Git status/diff evidence was unavailable. File hashes, exact raw Redis bytes, structured fields, TTLs, provider-call counts, and a final filesystem/hash check were used instead.

The audit did not call `FLUSHALL`. Cleanup used `SCAN MATCH aep:*` plus scoped `DEL`, matching `tests/conftest.py:105-116`. DB 15 began and ended with zero `aep:*` keys and `DBSIZE 0`.

## 3. Enforcement map

### 3.1 Intent creation and Phase 2 transitions

`IntentLedgerStore.create_intent` reads typed state and calculates a candidate attempt (`src/core/intents.py:518-584`), but deliberately uses `Phase2ExecutionState.model_construct` so the Python unresolved-step validator is not authoritative (`:585-599`). It sends the candidate to `commit_transition` (`:600-608`). The single `_INTENT_CAS_SCRIPT` is the authoritative atomic write path for both creation and later transitions (`:248-251,483-484,727-745`).

The Lua creation branch:

- checks lock ownership before any write (`:252-254`);
- decodes current and candidate, then checks exact expected/current/successor versions (`:256-269`);
- requires the candidate marker and refuses marker modification (`:273-282`);
- preserves non-ledger top-level fields (`:284-307`);
- admits only the enumerated state-machine edge (`:317-329`);
- rejects `PAUSED` and requires the candidate top-level status to be `PROCESSING` (`:337-342`);
- scans every **decoded** current ledger entry, rejects malformed required fields, and applies the execution-wide fence for `ABOUT_TO_FIRE`, `FIRED_UNCONFIRMED`, and `PERMANENTLY_AMBIGUOUS` (`:343-359`);
- rejects every non-null raw `risk_acceptance_id` (`:360`);
- requires the maximum-attempt same-step predecessor to be `FAILED_CONFIRMED` (`:354-365`);
- enforces append-only preservation and candidate-wide intent-ID/attempt uniqueness (`:341-353,417-432`);
- enforces unresolved retention before the sole final `SET` (`:433-436`).

For canonical JSON, no rejection branch writes the state key. The single write is after every check at `src/core/intents.py:435`.

### 3.2 Phase 1 `save_state`

The Phase 1 writer serializes the Pydantic candidate and invokes `_CAS_SCRIPT` (`src/core/storage.py:390-477`). The Lua script:

- checks the live lock token (`:176-178`);
- validates integer version bounds (`:180-195`);
- decodes and validates the currently persisted version before comparing it (`:206-223`);
- checks the **persisted decoded value**, not merely the candidate, for any marker or non-empty table ledger (`:224-230`);
- also prevents a candidate from introducing a marker or non-empty table ledger (`:236-241`);
- performs its only state write at `:243`.

Return `-4` is mapped to `Phase2StateProtectionError` (`src/core/storage.py:507-512`). This is the correct current-value, current-token/current-version design for canonical JSON.

### 3.3 Marker preservation by Phase 2 paths

The first creation candidate always carries `PHASE2_MANAGED_MARKER` (`src/core/intents.py:590-598`). Every transition candidate does the same (`:688-696`). Lua requires the candidate marker on every Phase 2 CAS and rejects changing a stored marker (`:277-282`). All production Phase 2 mutation call sites route through these methods:

- runner creation and resolution: `src/core/intent_workflow.py:227-242,254-265,296-308,348-369`;
- recovery claim and resolution: `src/core/intent_recovery.py:200-219,317-358`.

`preflight` and recovery scanning are read-only with respect to the execution state. Lock release/renew scripts touch only `aep:lock:*` (`src/core/locks.py:35-70`). No second production state-write path was found.

## 4. P2-001 — unsafe retry eligibility

### Classification: PARTIALLY CLOSED

### What is closed

For canonical persisted state, normal creation is atomically allowed only with no same-step predecessor or with the maximum-attempt predecessor in `FAILED_CONFIRMED`. The decisive checks are inside the Lua CAS, not the Python attempt calculation:

- maximum attempt and status selection: `src/core/intents.py:343-359`;
- predecessor decision: `:361-363`;
- exact next attempt/prepared version: `:364-365`;
- raw risk ID rejection: `:360`;
- sole write after all checks: `:435`.

The max-attempt comparison is independent of JSON member order. The dynamic canonical-order probe stored attempt 2 before attempt 1 and still received `IntentCreationEligibilityError`; raw bytes, version, status, ledger, history, and TTL were unchanged.

The checked-in regression evidence is substantive:

- first attempt and atomic marker: `tests/test_phase2_mutation_safety.py:194-210`;
- exactly one next attempt after `FAILED_CONFIRMED`: `:213-246`;
- rejection after `FIRED_CONFIRMED`, `ABOUT_TO_FIRE`, `FIRED_UNCONFIRMED`, and `PERMANENTLY_AMBIGUOUS`: `:249-280`;
- forged `risk_acceptance_id`: `:283-305`;
- runner rejection before a second provider call: `:308-337`;
- two current-token creators racing after failure, at most one new attempt and one provider call: `:340-401`.

The common rejection helper captures exact raw bytes and TTL before the operation, then checks raw equality, version equality, and elapsed-time TTL tolerance (`tests/test_phase2_mutation_safety.py:145-168`). Full raw equality also covers top-level status, ledger contents, and audit history.

The safe dynamic probes independently reproduced:

- after `FAILED_CONFIRMED`, two creators produced one success and one `StaleWriteError`, attempts `[1,2]`, and a single version increment;
- after `FIRED_CONFIRMED`, the runner raised `IntentCreationEligibilityError`, made zero provider calls, and preserved exact bytes and every compared field;
- canonical reordering could not make the older failure authoritative.

### What remains open

The “latest predecessor” proof is performed over the decoded Lua table, not the exact persisted JSON member stream. A raw ledger object can contain the same intent key twice. The verified bypass stored, under one duplicate intent key:

1. `FIRED_CONFIRMED`, attempt 2; then
2. `FAILED_CONFIRMED`, attempt 1.

Python `json.loads` and Redis `cjson.decode` both retained only item 2. `create_intent` therefore calculated attempt 2 and Lua also treated the old failure as latest. The runner accepted and resolved the new attempt as `FIRED_CONFIRMED`, made one provider call, and changed the raw state. This was a current-token/current-version controlled invalid-state case.

This fails required closure conditions 1, 3, 4, 5, and 6 for duplicate persisted entries. It also lacks a required checked-in regression. The code is materially safer for canonical state, so **PARTIALLY CLOSED** is more precise than `OPEN`, but it is not eligible for `CLOSED`.

## 5. P2-002 — execution-wide ambiguity fence bypass

### Classification: PARTIALLY CLOSED

### What is closed

For canonical state, the creation Lua CAS scans every decoded execution-ledger record, regardless of `step_id`, and returns `-7` for any `ABOUT_TO_FIRE`, `FIRED_UNCONFIRMED`, or `PERMANENTLY_AMBIGUOUS` status (`src/core/intents.py:345-353`). It separately rejects `current.status == 'PAUSED'` (`:339`) before requiring candidate `PROCESSING` (`:340`). A current token and current version do not bypass either check.

Terminal `FIRED_CONFIRMED` and `FAILED_CONFIRMED` entries do not create a global fence. Same-step predecessor enforcement remains independent at `:354-365`. Malformed required fields and duplicate step/attempt combinations in the decoded table return `-5` before `SET` (`:346-348,417-432`). The dynamic malformed-entry probe reached Lua directly, returned the stable `IntentInvariantError`, and preserved exact bytes and TTL.

Checked-in tests cover:

- cross-step blocking for all three statuses with exact raw/TTL preservation: `tests/test_phase2_mutation_safety.py:409-443`;
- `PAUSED` with no blocking ledger: `:446-468`;
- runner ordering and zero provider calls: `:471-508`;
- terminal nonblocking behavior: `:511-534`;
- same-step restrictions through the P2-001 matrix at `:249-305`.

Dynamic probes 3, 4, and 5 independently confirmed current-token/current-version rejection for cross-step `FIRED_UNCONFIRMED`, cross-step `PERMANENTLY_AMBIGUOUS`, and `PAUSED`. Each raised `ExecutionIntentFenceError`, made zero provider calls, preserved exact raw bytes/version/status/ledger/history, and changed TTL only by 19–27 ms of elapsed time.

### What remains open

The scan is complete only after JSON duplicate members have already been collapsed. A raw ledger object with the same intent key twice was stored with:

1. hidden first value `ABOUT_TO_FIRE`; then
2. visible last value `FAILED_CONFIRMED`.

Both decoders exposed only the terminal value. Different-step creation passed the Lua scan, the provider was called once, the result became `FIRED_CONFIRMED`, and the accepted write normalized away the hidden blocking entry.

The checked-in “duplicate” state-machine test uses two distinct JSON keys (`tests/test_phase2_state_machine.py:336-354`); it proves decoded attempt uniqueness but not duplicate-member detection. No mutation-safety test covers raw duplicate members, legacy duplicate serialization, or strict/canonical JSON parsing.

Because an in-scope duplicate persisted entry bypasses the fence across step IDs and reaches the provider, P2-002 is **PARTIALLY CLOSED**, not `CLOSED`.

## 6. P2-003 — Phase 1 `save_state` bypass of Phase 2 invariants

### Classification: PARTIALLY CLOSED

### What is closed

For canonical JSON, the Phase 2 marker is atomically set by the same first-creation CAS that appends the first intent (`src/core/intents.py:590-608,727-745`). The Phase 2 Lua CAS requires and preserves it (`:277-282`) and writes only after validating ledger immutability, history append-only rules, uniqueness, transition legality, and retention (`:296-435`).

The Phase 1 CAS checks the currently stored decoded marker and non-empty ledger after lock/version validation (`src/core/storage.py:206-230`), then checks the candidate separately (`:236-241`). Thus canonical current-token/current-version `save_state` cannot:

- delete or replace the ledger;
- modify intent status, immutable fields, or transition history;
- remove/change the marker;
- change `PAUSED` to `IDLE` or `PROCESSING`;
- shorten retention;
- replace a marked record with an empty ledger;
- introduce a marker/non-empty ledger; or
- overwrite a legacy non-empty ledger without a marker.

`Phase2StateProtectionError` is a stable, explicit non-retry-through-`save_state` domain error (`src/core/exceptions.py:76-83`; mapping at `src/core/storage.py:507-512`). Genuine unmarked, ledger-free Phase 1 records remain writable.

The checked-in matrix covers all listed canonical mutations in `tests/test_phase2_mutation_safety.py:542-636`, introduction of marker/ledger at `:672-702`, unmarked legacy ledger protection at `:705-738`, the valid Phase 1 path at `:741-762`, Phase 2 marker preservation at `:765-803`, and a concurrent Phase 1/Phase 2 race at `:806-854`. Stale-token/version precedence remains covered at `:857-920`.

The dynamic probes independently confirmed:

- the base writer lost a race with a Phase 2 transition; the transition alone advanced the record to version 3, retained one intent and the marker, and made no provider call;
- a legacy non-empty ledger without a marker produced `Phase2StateProtectionError` with exact byte/field/history preservation and only 18 ms TTL decay;
- caller introduction of a ledger or marker produced the same typed error with exact preservation;
- a genuine Phase 1 update succeeded from version 1 to 2 with `PROCESSING`, no marker, and an empty ledger.

### What remains open

The stored-value check is still a check of the decoded map rather than the exact persisted bytes. A marked Phase 2 state was rewritten as raw JSON containing duplicate top-level members:

- first `intent_ledger` contained the real `ABOUT_TO_FIRE` record, then a second `intent_ledger` was `{}`;
- first `phase2_managed` was `"intent-ledger-v1"`, then a second `phase2_managed` was `null`.

The raw bytes demonstrably contained both the marker literal and `ABOUT_TO_FIRE`. Python and Lua nevertheless saw only the later empty/unmarked values. With the live token and expected version 2, Phase 1 `save_state` returned success, replaced the record with version 3/`IDLE`/empty ledger/no marker, and reduced retention from about 31 days to 1 hour. Raw before/after bytes were unequal; no provider call was involved.

This directly defeats the persisted-current-value marker/ledger fence for duplicate raw state and violates deletion, marker immutability, history, status, empty-ledger replacement, and retention requirements. There is no checked-in duplicate-member regression. P2-003 is therefore **PARTIALLY CLOSED**.

## 7. Typed-error audit

The intended rejection return codes are mapped to stable domain types:

- `-6` → `IntentCreationEligibilityError` (`src/core/intents.py:772-777`);
- `-7` → `ExecutionIntentFenceError` (`:778-784`);
- `-8` → `IntentInvariantError` for marker removal/modification (`:785-789`);
- Phase 1 `-4` → `Phase2StateProtectionError` (`src/core/storage.py:507-512`).

The canonical dynamic rejections exposed only these types (plus the expected contention `StaleWriteError` in the creator race), never raw Lua return strings. Eligibility and global-fence errors do not classify provider mutation as safe to repeat. `Phase2StateProtectionError` explicitly says not to retry through `save_state` (`src/core/exceptions.py:79-82`).

Two typed-error gaps remain:

1. The duplicate-member bypasses are accepted, so no rejection/error is produced at all.
2. A Redis/Lua execution exception is wrapped as generic `IntentStateError(f"intent CAS Redis failure: {exc}")` (`src/core/intents.py:746-749`), and Phase 1 storage similarly embeds `exc` in `StorageOperationError` (`src/core/storage.py:478-481,562-565`). Those strings can expose Redis/Lua implementation details. Unexpected return codes also become generic `IntentStateError` at `src/core/intents.py:790`. These are not the normal new `-6/-7/-8/-4` branches, but they do not meet the broader requirement that callers never receive raw internal details or ambiguous generic errors.

## 8. Race and persistence probe record

All probes used `redis://127.0.0.1:6381/15`, current library objects, exact raw byte reads with `decode_responses=False`, and scoped `aep:*` cleanup. Rejection snapshots compared exact raw bytes, version, top-level status, ledger, transition history, TTL with elapsed-time tolerance, and provider-call count.

The PowerShell/stdin invocation form was:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; @'
# Inline asyncio probe source; it used Redis.from_url(.../15), SCAN MATCH aep:*,
# RedisStorageAdapter, IntentLedgerStore, WriteAheadRunner, and MockConnectorHarness.
# No source/test file was created and no FLUSHALL command was present.
'@ | py -3 -
```

The executed inline source implemented the nine required cases plus canonical-order, malformed-entry, and duplicate-member controlled robustness cases. It was supplied directly on stdin and was not written into the repository. Both invocations exited `0`.

| Case | Typed result | Raw/field result | TTL result | Provider calls |
|---|---|---|---|---:|
| 1. Two creators after `FAILED_CONFIRMED` | one success, one `StaleWriteError` | attempts `[1,2]`; one version increment | successful write reset retention as designed | 0 in direct creator probe; checked-in runner race recorded 1 winner call |
| 2. Creation after `FIRED_CONFIRMED` | `IntentCreationEligibilityError` | exact raw/version/status/ledger/history unchanged | 21 ms elapsed decay, within tolerance | 0 |
| 3. Other step while `FIRED_UNCONFIRMED` | `ExecutionIntentFenceError` | exact raw/version/status/ledger/history unchanged | 25 ms elapsed decay, within tolerance | 0 |
| 4. Other step while `PERMANENTLY_AMBIGUOUS` | `ExecutionIntentFenceError` | exact raw/version/status/ledger/history unchanged | 27 ms elapsed decay, within tolerance | 0 |
| 5. `PAUSED`, current token/version | `ExecutionIntentFenceError` | exact raw/version/status/ledger/history unchanged | 19 ms elapsed decay, within tolerance | 0 |
| 6. Phase 1 save races Phase 2 transition | Phase 1 `Phase2StateProtectionError`; Phase 2 success | final version 3, marker present, one `FIRED_CONFIRMED` intent | Phase 2 retention preserved | 0 |
| 7. Save legacy ledger without marker | `Phase2StateProtectionError` | exact raw/version/status/ledger/history unchanged | 18 ms elapsed decay, within tolerance | 0 |
| 8a. Introduce ledger through Phase 1 | `Phase2StateProtectionError` | exact raw/version/status/ledger/history unchanged | 10 ms elapsed decay, within tolerance | 0 |
| 8b. Introduce marker through Phase 1 | `Phase2StateProtectionError` | exact raw/version/status/ledger/history unchanged | 8 ms elapsed decay, within tolerance | 0 |
| 9. Valid unmarked Phase 1 save | success | version 2, `PROCESSING`, empty ledger, no marker | requested Phase 1 TTL stored | 0 |
| Canonical ledger reordering | `IntentCreationEligibilityError` | exact raw/fields unchanged | 15 ms elapsed decay, within tolerance | 0 |
| Malformed decoded entry at Lua CAS | `IntentInvariantError` | exact raw/fields unchanged | 7 ms elapsed decay, within tolerance | 0 |
| Duplicate member hides P2-002 blocker | accepted, `FIRED_CONFIRMED` | raw state changed | normal accepted-path retention | 1 |
| Duplicate member hides P2-001 predecessor | accepted, `FIRED_CONFIRMED` | raw state changed | normal accepted-path retention | 1 |
| Duplicate top-level marker/ledger | Phase 1 save accepted | version 3, `IDLE`, empty ledger, no marker | shortened from about 31 days to 1 hour | 0 |
| Final cleanup | exit `0` | zero `aep:*` keys; `DBSIZE 0` | not applicable | not applicable |

## 9. Verification commands and results

### 9.1 Python compilation

The exact PowerShell command compiled every `src` and `tests` Python file into a verified temporary directory, reported the count, and removed only that directory:

```powershell
$auditCompileDir = Join-Path $env:TEMP 'aep-p0-closure-pyc-20260729'; $resolvedTempRoot = [IO.Path]::GetFullPath($env:TEMP); $resolvedCompileDir = [IO.Path]::GetFullPath($auditCompileDir); if (-not $resolvedCompileDir.StartsWith($resolvedTempRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe compile temp path' }; if (Test-Path -LiteralPath $resolvedCompileDir) { Remove-Item -LiteralPath $resolvedCompileDir -Recurse -Force }; New-Item -ItemType Directory -Path $resolvedCompileDir | Out-Null; $env:PYTHONPYCACHEPREFIX=$resolvedCompileDir; $pyFiles = @(Get-ChildItem -LiteralPath 'src','tests' -Recurse -Filter '*.py' | Select-Object -ExpandProperty FullName); py -3 -m py_compile @pyFiles; $compileExit=$LASTEXITCODE; "py_files=$($pyFiles.Count)"; "py_compile_exit_code=$compileExit"; "compiled_artifacts=$((Get-ChildItem -LiteralPath $resolvedCompileDir -Recurse -File | Measure-Object).Count)"; Remove-Item -LiteralPath $resolvedCompileDir -Recurse -Force; "temp_removed=$(-not (Test-Path -LiteralPath $resolvedCompileDir))"; exit $compileExit
```

Exit `0`. Unedited summary:

```text
py_files=27
py_compile_exit_code=0
compiled_artifacts=64
temp_removed=True
```

### 9.2 Phase 1 storage/CAS suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest -s tests/test_cas_write.py tests/test_get_migration.py tests/test_races.py tests/test_uuid_validation.py tests/test_version_range.py -p no:cacheprovider -q
```

Exit `0`. Unedited summary: `32 passed in 0.96s`.

### 9.3 Focused Phase 2 suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest -s tests/test_mock_connector.py tests/test_phase2_durability.py tests/test_phase2_state_machine.py tests/test_phase2_runner.py tests/test_phase2_recovery.py -p no:cacheprovider -q
```

Exit `0`. Unedited summary: `163 passed in 3.04s`.

### 9.4 P2-001/P2-002/P2-003 regression matrix

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest -s tests/test_phase2_mutation_safety.py -p no:cacheprovider -q
```

Exit `0`. Unedited summary: `35 passed in 1.69s`.

### 9.5 Complete integration-enabled suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest -s tests -p no:cacheprovider -q
```

The first sandboxed invocation exited `1` with the unedited summary `1 failed, 252 passed in 29.97s`; the sole failure was `test_intent_and_resolution_survive_controlled_redis_restart`, where Docker returned Windows pipe `Access is denied`. No code assertion before the Docker permission boundary failed. The exact command was rerun with approved Docker-pipe access and exited `0`. Unedited rerun summary: `253 passed in 23.78s`.

### 9.6 Standalone Redis 7.2 WAITAOF suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest -s tests/test_phase2_waitaof_integration.py -p no:cacheprovider -q
```

Exit `0`. Unedited summary: `4 passed in 7.46s`.

Every pytest invocation also emitted the existing `pytest-asyncio` deprecation warning that `asyncio_default_fixture_loop_scope` is unset. No test was skipped.

## 10. Redis and preservation checks

Final environment output:

```text
redis_version:7.2.5
aof_enabled:1
appendfsync
everysec
appendonly
yes
aep_key_count=0
0
```

The last `0` is `DBSIZE`. `INFO commandstats` contained no `cmdstat_flushall` entry both when first checked and after the final run. Because the WAITAOF suite intentionally restarts Redis, final commandstats alone cannot prove commands issued before the restart; source inspection of `tests/conftest.py:101-116` and the audit command transcript confirm namespace-scoped `DEL` only. No audit command contained or issued `FLUSHALL`.

Historical file SHA-256 values were identical before and after all tests/probes:

```text
2F0333691DC00EA9ED632CE33009348113EBB7F37F32CFEE5B1A8E3114DC48E8  docs/07-phase2-gap-audit.md
65DBBC52647D9364BFCDA6A0AA1D53287C1DCF5E3A9F1135164E95D6090694DD  docs/09-post-waitaof-gate-review.md
30F917B04B0165F6B7A0477FF4FB3428056F0DFDCA5FB4C7CFCDEAD1EF568BE4  phase2_implementation_report.md
```

The specifically requested historical review file, `docs/09-post-waitaof-gate-review.md`, remained at SHA-256 `65DBBC52647D9364BFCDA6A0AA1D53287C1DCF5E3A9F1135164E95D6090694DD`.

## 11. Required closing decisions

### 11.1 Closure table

| Finding | Classification | Canonical-state result | Closure blocker |
|---|---|---|---|
| P2-001 unsafe retry eligibility | **PARTIALLY CLOSED** | Atomic max-attempt predecessor check, risk-ID rejection, race fencing, exact rejection preservation, and pre-provider ordering pass | Duplicate intent JSON members can hide a newer `FIRED_CONFIRMED` behind an older `FAILED_CONFIRMED`; one new same-step provider call was reproduced |
| P2-002 execution-wide ambiguity fence | **PARTIALLY CLOSED** | Atomic cross-step scan, `PAUSED` fence, terminal nonblocking behavior, and exact rejection preservation pass | Duplicate intent JSON members can hide `ABOUT_TO_FIRE` behind `FAILED_CONFIRMED`; one different-step provider call was reproduced |
| P2-003 Phase 1 `save_state` bypass | **PARTIALLY CLOSED** | Canonical stored marker/ledger checks, candidate checks, marker-preserving Phase 2 paths, race behavior, legacy ledger protection, and valid Phase 1 writes pass | Duplicate top-level marker/ledger members hide marked state from both decoders; Phase 1 overwrite and major TTL shortening were reproduced |

### 11.2 Residual risks and coverage gaps

- Exact persisted JSON is not rejected when an object contains duplicate member names. The normalized map can disagree with the byte-level history an operator or another parser observes.
- The 35-test P0 matrix has no duplicate-member/canonical-JSON regression and no assertion that raw duplicate input is quarantined before any CAS/provider call.
- Generic Redis/Lua exception wrappers can expose implementation text and do not provide a stable retry classification.
- The canonical creator race is safe, but its losing `StaleWriteError` instructs generic callers to re-read/rebase. Safety currently relies on the next attempt reaching the global fence; caller guidance should explicitly state that no provider dispatch occurred and that the operation must re-enter eligibility evaluation.
- WAITAOF proves local AOF acknowledgment on the verified Redis instance only. CAS and WAITAOF remain sequential commands, and this review makes no stronger durability or external-effect claim.

Required remediation is strict duplicate-member detection/canonical-state validation before typed model use and inside, or cryptographically bound to, each authoritative Lua mutation decision. The fix needs persisted-raw regression tests for duplicate keys at the ledger and top levels, current-token/current-version calls, exact raw/TTL comparisons, zero provider calls, quarantine/ejection behavior, concurrency, and legacy state.

### 11.3 May immutable request binding work safely begin?

**No, not as the next gated feature stage.** The duplicate-byte P0 bypasses must be closed first because immutable request binding would otherwise be evaluated over the same lossy decoded representation. Work whose sole purpose is to remediate and test these P0 parser/persistence defects may begin immediately; feature progression should not.

### 11.4 Next development stage

**NO-GO.** All three required findings fail at least one mandatory `CLOSED` condition, and each has a reproduced persisted-state bypass. Re-run this closure audit after strict duplicate-member handling and checked-in regressions are added.

### 11.5 Production non-idempotent dispatch

**NO-GO for production non-idempotent dispatch.** Two duplicate-ledger probes reached the provider, and the duplicate top-level probe erased the Phase 2 marker/ledger through Phase 1 `save_state`. This review does not claim exactly-once external effects, absolute atomicity, split-brain prevention, or guaranteed duplicate prevention.

The bounded guarantee to preserve is:

> “Ambiguity, corruption, and contention are detectable; the system fails closed.”

The canonical paths now approximate that guarantee substantially better, but the demonstrated duplicate-member corruption is not detected and does not fail closed; therefore the guarantee is a remediation target, not a current unconditional claim.
