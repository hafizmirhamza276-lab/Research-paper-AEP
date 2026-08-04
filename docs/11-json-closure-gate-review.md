# Duplicate-JSON-member closure gate acceptance review

**Review date:** 2026-07-29  
**Mode:** focused, read-only acceptance review of production code and existing tests  
**Redis scope:** `redis://127.0.0.1:6381/15`; only test-owned `aep:*` keys  
**Implementation under review:** the state-codec and raw-JSON validation changes reported in `phase2_implementation_report.md` section 13

## 1. Acceptance outcome

The checked duplicate-member cases now fail closed in the central Python codec and in the shared Lua validator. The regression suites for the previously demonstrated duplicate-ledger and duplicate-marker cases pass, preserve exact state bytes, and prevent additional provider and durability calls where those calls are instrumented.

The reported blanket `CLOSED` classifications are nevertheless **not accepted**. Two current implementation facts fail explicit requirements of this gate:

1. Raw stored state is not validated before lock information is read. Phase 1 CAS checks the lock first; Phase 2 CAS reads the lock before invoking the raw-state validator; preflight reads the lock value and lock TTL first. Controlled duplicate-state calls returned the lock/TTL codes rather than the ambiguous-state codes.
2. The Lua raw-state validator does not enforce UTF-8 validity. It returned `0` (valid) for a JSON string containing byte `0xff`. A controlled Phase 1 CAS replaced that invalid serialization and reset its TTL. More seriously, a controlled Phase 2 race injected invalid UTF-8 into `status` after valid Python reads of a `PAUSED` execution; creation succeeded, two test durability acknowledgements occurred, and the mock provider was called once.

These are acceptance failures, not evidence that the checked duplicate-member matrix is ineffective. No pre-change executable baseline or usable Git history was present, so this review does not label either behavior a newly introduced regression.

| Finding | Classification | Acceptance result |
|---|---|---|
| P2-001 — unsafe same-step retry eligibility | **PARTIALLY CLOSED** | The known duplicate-intent predecessor case is closed, but the required raw-before-lock ordering is absent, and ambiguity is not always the returned classification under contention. |
| P2-002 — execution-wide ambiguity fence | **PARTIALLY CLOSED** | The checked duplicate-ledger/status cases are closed. The atomic validator still accepts invalid UTF-8, and a controlled post-read injection allowed a `PAUSED` execution to reach one provider call. |
| P2-003 — Phase 1 replacement of protected state | **PARTIALLY CLOSED** | Duplicate marker/ledger replacement is closed for the checked encodings. Phase 1 still validates lock data first and can replace an invalid UTF-8 stored serialization, advancing version and refreshing TTL. |

**Immutable request-binding implementation: NO-GO.** The next feature stage should not bind requests to a raw-state gate that still accepts an invalid serialization and does not meet the mandated validation order.

**Production non-idempotent dispatch: NO-GO.** The controlled `PAUSED`-state case reached the mock provider once. This review makes no exactly-once, absolute-atomicity, split-brain-prevention, or guaranteed-duplicate-prevention claim.

## 2. Scope, inventory, and decoder search

The review inspected:

- `src/core/state_codec.py`
- `src/core/exceptions.py`
- `src/core/storage.py`
- `src/core/intents.py`
- `src/core/intent_workflow.py`
- `src/core/intent_recovery.py`
- `src/core/durability.py`
- `src/core/locks.py`
- `src/core/validation.py`
- every Python file under `tests`, with detailed review of `test_state_codec.py`, `test_phase2_duplicate_member_safety.py`, `test_phase2_mutation_safety.py`, the Phase 1 CAS/migration/race suites, the Phase 2 state-machine/runner/recovery suites, and the Redis 7.2 WAITAOF suite
- the three state-interpreting Lua bodies, plus the lock-only Lua bodies
- historical findings in `docs/07-phase2-gap-audit.md`, `docs/09-post-waitaof-gate-review.md`, and `docs/10-p0-closure-review.md`
- the reported implementation in `phase2_implementation_report.md`

Repository-wide searches covered `json.loads`, `json.dumps`, `cjson.decode`, `cjson.encode`, codec calls, Redis state keys, `register_script`, raw `SET`, state scans, recovery, resolution, retention, and WAITAOF.

The resulting production inventory is:

| Operation | Execution-state behavior |
|---|---|
| `RedisStorageAdapter.get_state` | The sole application raw-state reader. It calls `decode_state(raw)` before migration or Pydantic model conversion (`storage.py:580-607`). |
| `IntentLedgerStore.get_execution` | Delegates to `RedisStorageAdapter.get_state`, then applies the strict Phase 2 model (`intents.py:511-529`). |
| `RedisStorageAdapter.save_state` | The only Phase 1 execution-state writer. It uses the codec for the candidate and `_CAS_SCRIPT` for the atomic write (`storage.py:405-536`). |
| `IntentLedgerStore.create_intent` | Strictly reads state, builds a candidate, then delegates to the shared Phase 2 CAS (`intents.py:531-622`). |
| `IntentLedgerStore.transition_intent` / `commit_transition` | The only Phase 2 execution-state writer (`intents.py:624-810`). |
| Runner resolution | Reuses `transition_intent` (`intent_workflow.py:348-369`). |
| Recovery claim and recovery resolution | Reuse `transition_intent` (`intent_recovery.py:200-220,317-358`). |
| Pre-dispatch preflight | Read-only with respect to execution state, but semantically reads the lock, lock TTL, version, ledger, and intent status (`intents.py:448-467,812-861`). |
| Recovery scan | Uses `get_execution`; there is no alternative state decoder (`intent_recovery.py:97-122`). |
| Quarantine | Writes a separate `aep:poison:*` envelope and never replaces the state key (`storage.py:689-748`). |
| Lock release/renew | Operate only on `aep:lock:*`; they do not read execution state (`locks.py:35-70`). |

No additional production execution-state decoder or writer was found. The remaining direct `json.dumps` in `intents.py:470-477` canonicalizes evidence solely for hashing; it is not execution-state serialization. Direct `json.loads`/`json.dumps` calls in tests inject or inspect fixtures and are not application paths.

## 3. Codec review

### 3.1 Accepted properties

`decode_state`:

- accepts `str`, `bytes`, or `bytearray` and performs strict UTF-8 validation (`state_codec.py:43-69`);
- supplies `object_pairs_hook`, so every Python-decoded object is checked for duplicate names before conversion to an ordinary mapping;
- compares decoded names, which closes literal-versus-escaped spellings such as `status` and `statu\u0073`;
- rejects duplicates at every recursively decoded object, including objects inside arrays;
- rejects `NaN`, `Infinity`, and non-finite parsed floats;
- preserves a stable distinction: duplicates raise `AmbiguousStateError`; malformed or invalid serialization raises `StateCorruptionError`.

`encode_state`:

- uses `allow_nan=False`;
- uses `ensure_ascii=False` and verifies strict UTF-8 encodability;
- uses `sort_keys=True`;
- uses compact separators `(',', ':')`;
- converts serialization failures to the stable `StateSerializationError` type (`state_codec.py:72-92`).

The state writers pass `model_dump(mode="json")` only through `encode_state` (`storage.py:481`; `intents.py:738`). An ambiguous existing state is checked before semantic `cjson.decode` in the current-value portions of both CAS scripts, so the tested duplicate cases are not normalized before those semantic checks.

`AmbiguousStateError` is a stable subtype of `StateCorruptionError`, and its contract explicitly states that it never makes an external provider retry safe (`exceptions.py:76-83`). Caller-visible ambiguous-state messages do not include the complete raw state. The complete raw value is retained only in the bounded poison record; the warning path logs identifiers, reason, and the quarantine exception, not the state body (`storage.py:724-748`).

### 3.2 Compatibility implications

- Valid duplicate-free historical Phase 1 and Phase 2 envelopes remain accepted by both Python and Lua matrix tests.
- Valid historical whitespace, key order, and escaped Unicode spellings are accepted on read. A later successful application write emits the new sorted, compact, literal-Unicode representation, so exact bytes may change as part of an authorized versioned mutation.
- Unmarked legacy non-empty ledgers remain readable by the strict Phase 2 view and protected from Phase 1 replacement.
- Duplicate members that older last-wins decoders accepted are now rejected and may create a poison record. This is an intentional compatibility break for ambiguous state.
- Lua has a nesting cap of 128. A syntactically valid historical record deeper than that can be read by Python but is rejected by an atomic Lua path as invalid state.
- The intended UTF-8 contract is inconsistent: Python is strict, but the Lua validator accepted invalid byte `0xff`. When invalid bytes are read through a `decode_responses=True` Redis client before Lua, redis-py decoding fails and `get_state` wraps that as `StorageOperationError` before `decode_state` or quarantine. When a race injects those bytes after the Python read, Lua can accept and replace them.

## 4. Duplicate-member and valid-JSON matrix

The 63-case codec/Lua suite passed in full. The common Python/Lua matrix covers:

| Required class | Evidence |
|---|---|
| Root members | conflicting duplicate `status`, duplicate `version`, duplicate marker, and duplicate complete ledger |
| Ledger | duplicate intent ID with conflicting records |
| Intent | duplicate status, step ID, attempt, and retention-related `reconcile_after` |
| Transition history | identical duplicate `transitions` member |
| Nested metadata | duplicate member in `context_data.metadata` |
| Objects in arrays | duplicate member inside an object contained by an array |
| Equal and conflicting values | identical complete ledger/transition/unknown members and conflicting status/intent members |
| Equivalent escaped names | `status` and `statu\u0073`; an additional read-only probe also returned ambiguous for escaped solidus and an explicit UTF-8 supplementary character versus its surrogate-pair escape |
| Unknown names | identical duplicate root unknown member plus nested unknown metadata/array members |
| False-positive controls | strings containing braces, commas, colons, escaped quotes and backslashes; repeated array values; similar names; empty containers; and Urdu/Chinese Unicode text |

The shared recursive scanner correctly distinguishes punctuation inside strings from JSON structure and calls `cjson.decode` only after the raw duplicate scan. For valid UTF-8 inputs in this matrix, no duplicate bypass or false positive was observed.

The matrix is incomplete as a strict serialization matrix because it lacks invalid UTF-8. The additional controlled probe returned:

```text
lua_result=0
```

for `{"x":"<byte ff>"}`. A strict JSON gate must reject that input.

## 5. Atomic-path review

### 5.1 Phase 1 save and retention replacement

1. **Python entry point:** `RedisStorageAdapter.save_state` (`storage.py:405`).
2. **Lua/storage operation:** `_CAS_SCRIPT`, ending in `SET ... EX` (`storage.py:157-260`).
3. **Raw validator:** `aep_json_member_check`, prefixed by `build_lua_state_validation_script`.
4. **Order before semantic decoding:** candidate and current valid-UTF-8 duplicate checks precede their respective `cjson.decode` calls (`storage.py:198-205,216-232`). **Acceptance exception:** lock `GET` occurs first at `storage.py:183`.
5. **Typed error:** duplicate return `-5` maps to quarantined `AmbiguousStateError` (`storage.py:526-532`). Invalid current state normally maps through `-2` to `StateCorruptionError`, but invalid UTF-8 was accepted by Lua.
6. **Regression evidence:** P2-003 duplicate-envelope test; current-writer retention matrix; Phase 1 CAS/malformed tests; controlled invalid-UTF-8 probe.
7. **Raw bytes/version unchanged on checked duplicate rejection:** yes. Exact raw equality is asserted; therefore serialized version, status, ledger, and history are also unchanged.
8. **TTL on checked duplicate rejection:** elapsed-time-only decay within a 1,000 ms scheduling tolerance. Invalid UTF-8 was not rejected: the probe advanced version `1 -> 2` and refreshed TTL.
9. **Provider/durability counts:** the direct storage path has no provider or durability component. The P2-003 duplicate test does not instrument counters, so a numeric zero is structural rather than directly asserted.

### 5.2 Phase 2 normal creation

1. **Python entry point:** `IntentLedgerStore.create_intent` (`intents.py:531`).
2. **Lua/storage operation:** `commit_transition` -> `_INTENT_CAS_SCRIPT` -> `SET ... EX` (`intents.py:722-758,253-445`).
3. **Raw validator:** the same `aep_json_member_check` on both current and candidate.
4. **Order before semantic decoding:** valid-UTF-8 duplicate checks occur before both `cjson.decode` calls (`intents.py:258-268`). **Acceptance exception:** the state is fetched and the lock is read first (`intents.py:254-255`).
5. **Typed error:** duplicate return `-9` maps to quarantined `AmbiguousStateError` (`intents.py:803-809`).
6. **Regression evidence:** P2-001 duplicate predecessor; P2-002 three-status parameterization; post-Python-read duplicate-version injection.
7. **Raw bytes/version unchanged on checked duplicate rejection:** yes.
8. **TTL on checked duplicate rejection:** elapsed-time-only decay.
9. **Provider/durability counts:** same-step duplicate rejection observed zero additional provider calls and zero barrier calls; each execution-wide duplicate rejection observed zero provider calls and zero barrier calls. The invalid-UTF-8 race did not reject and observed one provider call and two successful fake-barrier acknowledgements.

### 5.3 Phase 2 transitions, runner resolution, and recovery mutations

1. **Python entry points:** `transition_intent` and `commit_transition`; runner resolution at `intent_workflow.py:348-369`; recovery claim at `intent_recovery.py:200-220`; recovery resolution at `intent_recovery.py:317-358`.
2. **Lua/storage operation:** all use `_INTENT_CAS_SCRIPT` and the same `SET ... EX`.
3. **Raw validator:** the same validator on current and candidate raw JSON.
4. **Order before semantic decoding:** yes for the duplicate scan; no for the required raw-before-lock ordering.
5. **Typed error:** duplicate return `-9` -> `AmbiguousStateError`.
6. **Regression evidence:** post-Python-read transition injection; recovery read rejection before readback; normal runner/recovery suites.
7. **Raw bytes/version unchanged:** exact equality is asserted for the transition injection and recovery initial-read rejection.
8. **TTL:** elapsed-time-only in the shared rejection helper.
9. **Provider/durability counts:** recovery initial-read rejection asserts zero readbacks; it does not attach a durability counter. The direct transition injection has no attached provider or barrier. Resolution and recovery-resolution do not have dedicated post-read injection tests asserting all counters. This is a coverage limitation even though they reuse the same CAS.

### 5.4 Pre-dispatch preflight

1. **Python entry point:** `IntentLedgerStore.preflight` (`intents.py:812`).
2. **Lua operation:** `_PREFLIGHT_SCRIPT`; it does not mutate execution state.
3. **Raw validator:** the shared validator on stored raw JSON.
4. **Order:** **fails the required order.** Lock `GET` and `PTTL` are at `intents.py:449-451`; raw state is fetched and validated only at `:452-456`; semantic `cjson.decode` follows at `:457`.
5. **Typed error:** duplicate return `-6` -> quarantined `AmbiguousStateError` (`intents.py:852-858`). A stale token or short lock TTL masks the ambiguity with the pre-existing preflight result.
6. **Regression evidence:** direct duplicate-unknown-member preflight rejection; runner provider-order tests; controlled lock/TTL precedence probe.
7. **Raw bytes/version unchanged:** yes for the checked duplicate test.
8. **TTL:** state TTL decays only with elapsed time; preflight reads but does not refresh it.
9. **Provider/durability counts:** the direct preflight duplicate test does not attach counters. The runner duplicate creation cases reject before preflight and observe zero provider/barrier calls.

## 6. Controlled validation cases

All checked-in controlled cases were rerun against Redis DB 15 through the 45-test P0 matrix and 73-test integrated ambiguous-state matrix.

| Requested case | Result | Before/after and call evidence |
|---|---|---|
| 1. Duplicate status allowing same-step retry | **Rejected as `AmbiguousStateError`.** | Exact raw bytes unchanged; therefore version, execution status, ledger, and transition history unchanged. TTL elapsed only. Provider count stayed at its one-call baseline, so zero additional calls; barrier count `0`. |
| 2. Duplicate ledger status hiding execution-wide blocking state | **Rejected for `ABOUT_TO_FIRE`, `FIRED_UNCONFIRMED`, and `PERMANENTLY_AMBIGUOUS`.** | Exact bytes unchanged; semantic fields unchanged; TTL elapsed only; provider `0`; barrier `0`. |
| 3. Duplicate Phase 2 marker or ledger allowing Phase 1 replacement | **Rejected as `AmbiguousStateError`.** | Exact bytes/version/status/ledger/history unchanged; roughly 31-day retention was not shortened to 60 seconds. No provider/barrier exists on this direct path. |
| 4. Duplicate retention data allowing shortening | **Component validation passes; integrated mutation coverage is incomplete.** | Duplicate `reconcile_after` is rejected by both Python and Lua matrix tests. The P2-003 mutation suite separately proves retention shortening is rejected, but no checked-in case combines duplicate `reconcile_after` with a retention-changing CAS and all requested counters. |
| 5. Duplicate fields during a Phase 2 transition | **Rejected atomically after a valid Python read.** | Equal duplicate `version` injected after read; exact injected bytes remain; TTL does not increase. Direct test has no provider/barrier counter objects. |
| 6. Duplicate fields during recovery or resolution | **Recovery initial read rejected before readback. Shared CAS evidence passes; dedicated race coverage is incomplete.** | Exact bytes unchanged; TTL elapsed only; readbacks `0`. There is no dedicated post-read injection in recovery claim, runner resolution, or recovery resolution that instruments both durability and provider counters. |
| 7. Equivalent escaped member names | **Rejected by Python and Lua for the checked spellings.** | `status`/`statu\u0073` passes the matrix; additional read-only escaped-solidus and supplementary-code-point probes also returned ambiguous. No integrated state-mutation snapshot exists for this exact spelling class. |
| 8. Duplicate unknown nested members | **Rejected by Python and Lua.** | Nested metadata and array-contained object cases pass; preflight rejects a duplicate unknown root member with exact-state preservation. No integrated mutating CAS test uses the nested unknown form. |
| 9. Valid historical Phase 1 and Phase 2 states | **Accepted.** | Both codec implementations accept the historical envelopes; normal Phase 1 and Phase 2 suites pass; legacy non-empty ledger protection passes. |

For rejected cases using `_assert_ambiguous_rejection_preserves_state`, exact raw equality is stronger than separate semantic comparisons: the serialized version, execution status, complete intent ledger, transition arrays, and all unknown fields remain byte-for-byte identical. The helper also checks that `PTTL` neither increases nor falls by more than measured elapsed time plus 1,000 ms.

The requested provider and durability zero-count evidence is not uniformly present for every direct CAS case. It is directly instrumented for the P2-001/P2-002 runner cases, structurally absent from Phase 1 storage, and uninstrumented for several direct transition/preflight/recovery cases. This prevents treating the regression matrix alone as complete evidence for the closure rule.

## 7. Additional robustness validation

### 7.1 Required validation order is not implemented

With exact stored duplicate `version` members and a stale token, the scripts returned:

```text
phase1_duplicate_with_stale_token=-3
phase2_duplicate_with_stale_token=-3
preflight_duplicate_with_stale_token=-1
preflight_duplicate_with_short_ttl=-2
raw_unchanged=True
```

The duplicate codes would have been Phase 1 `-5`, Phase 2 `-9`, and preflight `-6`. The state remained unchanged, so this is not an accepted mutation. It does prove that raw-state validation does not precede lock/version information as required and that ambiguous state is not the stable returned classification for those calls.

### 7.2 Lua accepts invalid UTF-8

The validator returned valid for a JSON string containing byte `0xff`. A controlled current-token/current-version Phase 1 CAS then produced:

```text
selected_db=15
cas_result=1
raw_unchanged=False
stored_version=2
ttl_before_ms=3599983
ttl_after_ms=3599992
probe_keys_remaining=0
```

This is an accepted replacement of invalid serialization. It silently removes the invalid bytes and refreshes retention rather than failing closed.

That Phase 1 probe used an unmarked, ledger-free envelope. It does not demonstrate removal of a currently recognizable Phase 2 marker or ledger: those checked fields remain protected. It does demonstrate that the authoritative Phase 1 path is not the strict raw-JSON gate required by this acceptance review.

A separate Phase 2 controlled race started from a valid `PAUSED` execution. Both application reads completed successfully; immediately after the second read, the test replaced the stored `"status":"PAUSED"` value with a JSON string containing byte `0xff`, preserving the key TTL. The Phase 2 Lua validator accepted it, did not see `current.status == 'PAUSED'`, and accepted creation. The resulting output was:

```text
selected_db=15
injected_invalid_utf8=True
runner_result=FIRED_CONFIRMED
provider_calls=1
durability_ack_calls=2
final_status=PROCESSING
final_version=3
intent_count=1
probe_keys_remaining=0
```

This fails the P2-002 closure rule: invalid serialization was not detected, the persisted state changed, durability acknowledgements were issued, and the provider was called.

These probes used unique UUID state/lock keys, selected DB 15 explicitly, deleted exactly their two keys in `finally`, and left zero probe keys. They did not use `FLUSHALL`.

## 8. Regression and compatibility conclusions

| Requirement | Result |
|---|---|
| Normal Phase 1 `save_state` remains functional | **Pass.** Phase 1 suite 32/32; unmarked ledger-free update passes. |
| Normal Phase 2 creation and transitions remain functional | **Pass.** Focused Phase 2 163/163; full suite 326/326. |
| Legacy ledger records remain protected | **Pass for duplicate-free valid UTF-8 legacy fixtures.** Unmarked non-empty ledger cannot be replaced by Phase 1. |
| Malformed JSON remains rejected | **Partial/fail.** Checked syntax errors, NaN, and Infinity reject. Invalid UTF-8 is accepted by Lua and can be replaced. |
| Stale-token and stale-version behavior unchanged | **Pass for valid stored state.** Existing tests pass. Under duplicate state, stale token/TTL masks ambiguous-state classification, as source order specifies. |
| Same-connection CAS and WAITAOF ordering unchanged | **Pass.** Redis 7.2 suite 4/4; the existing event order remains CAS, WAITAOF, provider, CAS, WAITAOF with matching pinned connection IDs for each write/barrier pair. |
| No relevant state mutation uses an unprotected decoder | **Fail as a strict statement.** No alternative decoder exists, but the shared Lua decoder boundary itself accepts invalid UTF-8. |
| Duplicate members at all checked locations fail closed | **Pass for the checked valid-UTF-8 matrix.** |
| Every rejected mutation has exact state/TTL plus zero provider and durability assertions | **Partial.** Exact state/TTL is strong; counters are not instrumented on every direct transition/preflight/recovery case. |

## 9. Verification record

All required commands selected Redis DB 15. All exited `0`. Pytest emitted only the existing `pytest-asyncio` fixture-loop-scope deprecation warning.

### 9.1 `py_compile` for `src` and `tests`

```powershell
$compileDir=Join-Path $env:TEMP 'aep-json-closure-review-pyc-20260729'; $tempRoot=[IO.Path]::GetFullPath($env:TEMP); $resolved=[IO.Path]::GetFullPath($compileDir); if(-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'unsafe compile path'}; if(Test-Path -LiteralPath $resolved){throw 'compile temp path already exists'}; New-Item -ItemType Directory -Path $resolved | Out-Null; $env:PYTHONPYCACHEPREFIX=$resolved; $pyFiles=@(Get-ChildItem -LiteralPath 'src','tests' -Recurse -Filter '*.py' | Select-Object -ExpandProperty FullName); py -3 -m py_compile @pyFiles; $exitCode=$LASTEXITCODE; "py_files=$($pyFiles.Count)"; "py_compile_exit_code=$exitCode"; "compiled_artifacts=$((Get-ChildItem -LiteralPath $resolved -Recurse -File | Measure-Object).Count)"; Remove-Item -LiteralPath $resolved -Recurse -Force; "temp_removed=$(-not (Test-Path -LiteralPath $resolved))"; exit $exitCode
```

Exit `0`: `py_files=30`, `compiled_artifacts=67`, `temp_removed=True`.

### 9.2 Phase 1 storage/CAS suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_cas_write.py tests/test_get_migration.py tests/test_races.py tests/test_uuid_validation.py tests/test_version_range.py -p no:cacheprovider -q
```

Exit `0`: `32 passed in 1.64s`.

### 9.3 Focused Phase 2 suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_mock_connector.py tests/test_phase2_durability.py tests/test_phase2_state_machine.py tests/test_phase2_runner.py tests/test_phase2_recovery.py -p no:cacheprovider -q
```

Exit `0`: `163 passed in 6.52s`.

### 9.4 Combined P0 regression matrix

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_mutation_safety.py tests/test_phase2_duplicate_member_safety.py -p no:cacheprovider -q
```

Exit `0`: `45 passed in 4.59s`.

### 9.5 Codec and Lua validation matrix

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_state_codec.py -p no:cacheprovider -q
```

Exit `0`: `63 passed in 1.19s`.

### 9.6 Complete integration-enabled suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests -p no:cacheprovider -q
```

Exit `0`: `326 passed in 32.76s`; no failures or skips.

### 9.7 Redis 7.2 WAITAOF suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_waitaof_integration.py -p no:cacheprovider -q
```

Exit `0`: `4 passed in 8.46s`.

### 9.8 Integrated ambiguous-state validation suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_state_codec.py tests/test_phase2_duplicate_member_safety.py -p no:cacheprovider -q
```

Exit `0`: `73 passed in 2.03s`.

### 9.9 Redis configuration and final cleanup

The exact final command was:

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

No review command used `FLUSHALL`.

## 10. Integrity of protected documents

The workspace's `.git` directory is empty, so Git status/diff evidence is unavailable. SHA-256 hashes were captured before this review and recomputed after creating this document. Each protected hash remained identical:

| File | SHA-256 |
|---|---|
| `docs/07-phase2-gap-audit.md` | `2F0333691DC00EA9ED632CE33009348113EBB7F37F32CFEE5B1A8E3114DC48E8` |
| `docs/09-post-waitaof-gate-review.md` | `65DBBC52647D9364BFCDA6A0AA1D53287C1DCF5E3A9F1135164E95D6090694DD` |
| `docs/10-p0-closure-review.md` | `963A9C43476340BC9584B33306876C502B6A4C82715A9BEB048D7DD2FFF6935B` |
| `phase2_implementation_report.md` | `BD006AAB571252FF81E0D3F0B56ABF42C2290EB1B610B508024D43CECC21BA3D` |

Production code and existing tests were inspected and executed but not edited.

## 11. Final closure and gate decision

### 11.1 Closure table

| Finding | Final classification | Closed evidence | Remaining blocker |
|---|---|---|---|
| P2-001 unsafe retry eligibility | **PARTIALLY CLOSED** | Duplicate intent ID/status cannot make `FAILED_CONFIRMED` authoritative; same-step runner rejection preserves exact state with zero additional provider calls and zero barrier calls. | Atomic scripts do not validate raw state before lock information, so ambiguity is not consistently classified first; several shared-path counter assertions remain indirect. |
| P2-002 execution-wide ambiguity fence | **PARTIALLY CLOSED** | All three checked blocking statuses remain protected under valid-UTF-8 duplicate serialization, with exact state preservation and zero provider/barrier calls. | Lua accepts invalid UTF-8. A controlled post-read `PAUSED`-status injection reached two durability acknowledgements and one provider call. |
| P2-003 Phase 1 replacement protection | **PARTIALLY CLOSED** | Checked duplicate marker/ledger/status state cannot be overwritten or retention-shortened; legacy ledgers remain protected. | Phase 1 checks the lock first and accepts invalid UTF-8 as valid raw JSON; a current caller replaced such state, advanced version, and refreshed TTL. |

### 11.2 Residual compatibility and coverage limitations

- Strict Python and non-strict Lua UTF-8 behavior are inconsistent.
- Raw-before-lock/TTL ordering is absent from all three state-interpreting scripts.
- Valid nesting beyond 128 is incompatible with atomic Lua mutation.
- Counter assertions are not attached to every direct transition, preflight, recovery-claim, runner-resolution, and recovery-resolution injection case.
- Duplicate retention, equivalent escaped names, and unknown nested members have component-level Python/Lua coverage, but not a dedicated end-to-end mutation snapshot for every spelling/location.
- Quarantine is best-effort and scheduling ejection remains outside this repository.
- Redis CAS and WAITAOF are sequential commands on one pinned connection. The passing suite establishes only the tested local AOF acknowledgement behavior.

### 11.3 Immutable request-binding gate

**NO-GO for immutable request-binding implementation.** First make Lua validate strict UTF-8 and move raw-state validation ahead of lock value, lock TTL, version, ledger, status, marker, predecessor, ambiguity-fence, transition, retention, and replacement decisions. Then add controlled regressions for the uncovered resolution/recovery races and all requested counters.

### 11.4 Production dispatch gate

**NO-GO for production non-idempotent dispatch.** The present implementation has a controlled invalid-serialization path from a `PAUSED` execution to a provider call. Separate open work around request storage, connector governance, authenticated resolution, scheduling, and telemetry also remains outside this closure.

The bounded guarantee remains the required standard:

> “Ambiguity, corruption, and contention are detectable; the system fails closed.”

The checked valid-UTF-8 duplicate-member cases now satisfy that standard. The invalid-UTF-8 and validation-order results prevent treating it as an unconditional property of the current implementation.
