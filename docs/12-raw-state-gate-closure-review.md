# Raw-state validation gate closure review

**Review date:** 2026-07-30  
**Review mode:** focused, read-only implementation and reliability audit  
**Implementation baseline:** changes reported after `docs/11-json-closure-gate-review.md`  
**Runtime:** Redis 7.2.5, database 15, AOF enabled, `appendfsync=everysec`

## 1. Executive result

The reported raw-state validation gate is independently sustained for every repository-defined execution-state read, creation, transition, preflight, recovery, resolution, and retention-changing path.

The prior review's two blockers are closed:

1. The shared Lua validator now performs a strict byte-level UTF-8 pass before duplicate-member scanning or `cjson.decode`.
2. Each state-interpreting Lua body now fetches and validates stored state before reading the lock value, lock TTL, version, status, ledger, marker, transition history, predecessor information, or retention data.

All requested executable matrices passed on Redis 7.2.5. The controlled `PAUSED` race retained the exact injected bytes and elapsed-time-only TTL, created no intent, did not advance the version, and recorded provider `0` and durability acknowledgement `0`. Late runner-resolution and recovery-resolution injections were also rejected; operations that necessarily occurred before those deliberately late injections are reported separately from the zero post-injection deltas.

| Reported claim | Independent result | Principal evidence |
|---|---|---|
| Strict byte-level Lua UTF-8 validation | **Sustained** | `state_codec.py:152-221`; 142-case codec/Lua matrix |
| Duplicate-member detection on raw JSON | **Sustained** | `state_codec.py:224-420`; duplicate and P0 matrices |
| Raw validation before lock/TTL/state interpretation | **Sustained** | `storage.py:191-203`; `intents.py:253-267,455-466`; precedence tests |
| Exact Redis bytes with `decode_responses=True` | **Sustained** | `storage.py:651-656`; decoded-client regression |
| Central typed result mapping | **Sustained** | `state_codec.py:20-64`; `storage.py:658-678` |
| Rejected `PAUSED` race has zero provider calls and acknowledgements | **Sustained** | `test_raw_state_validation_gate.py:360-410` |
| P2-001/P2-002/P2-003 closure for repository raw-state paths | **Sustained, bounded to this scope** | static path inventory plus all requested suites |

No claim is made for exactly-once external effects, absolute atomicity, split-brain prevention, or guaranteed duplicate prevention.

## 2. Scope and path inventory

The audit inspected the requested production modules, every production Lua body, all checked-in tests, the prior review documents, and the current implementation report. Repository-wide searches covered `json.loads`, `json.dumps`, `cjson.decode`, `cjson.encode`, `register_script`, `decode_state`, `encode_state`, `aep:state:*`, Redis `GET`/`SET`, state scanning, poison records, lease inspection, transitions, recovery, resolution, TTL changes, and WAITAOF.

The production execution-state inventory is:

| Path | Read/write behavior | Authoritative gate |
|---|---|---|
| `RedisStorageAdapter.get_state` | Exact-byte application read, strict decode, migration, model validation | `decode_state`; `storage.py:585-649` |
| Phase 1 `save_state` | Initial save, update, and state TTL change | `_CAS_SCRIPT`; `storage.py:160-271` |
| `IntentLedgerStore.get_execution` | Delegates to `get_state`, then applies the strict Phase 2 model | `intents.py:520-538` |
| Phase 2 normal creation | Read/build candidate, then atomic creation CAS | `_INTENT_CAS_SCRIPT`; `intents.py:540-631` |
| Every Phase 2 transition | Read/build candidate, then atomic transition CAS | same `_INTENT_CAS_SCRIPT`; `intents.py:633-815` |
| Pre-dispatch preflight | Read-only lease/TTL/version/intent-status check | `_PREFLIGHT_SCRIPT`; `intents.py:454-476,817-862` |
| Runner resolution | Calls `transition_intent` | shared Phase 2 CAS; `intent_workflow.py:348-369` |
| Recovery claim | Calls `transition_intent` for `ABOUT_TO_FIRE -> FIRED_UNCONFIRMED` | shared Phase 2 CAS; `intent_recovery.py:200-220` |
| Recovery resolution | Calls `transition_intent` | shared Phase 2 CAS; `intent_recovery.py:317-358` |
| Recovery discovery | Scans key names, then calls `get_execution` for values | central application read; `intent_recovery.py:97-122` |
| Quarantine | Writes a separate bounded `aep:poison:*` record; never changes the state key | `storage.py:735-805` |
| Lock acquire/release/renew | Operates only on `aep:lock:*`; does not read execution state | outside the raw-state gate; `locks.py:35-70,117-235` |

Only three Lua bodies interpret execution state: Phase 1 CAS, the shared Phase 2 CAS, and preflight. Lock release and renewal are lock-only scripts. No other production state decoder, state writer, `EXPIRE` path, or direct `SET` to `aep:state:*` was found. The direct `json.dumps` in `intents.py:483-485` canonicalizes evidence for hashing and is not state persistence. Direct JSON and raw Redis operations elsewhere are test fixture construction or inspection.

## 3. Strict codec and Lua byte validator

### 3.1 Python boundary

`decode_state` accepts `bytes`, `bytearray`, or `str`, performs strict UTF-8 validation, and uses `object_pairs_hook` before constructing ordinary mappings (`state_codec.py:89-115`). Decoded member names are compared, so literal and JSON-escaped equivalent names collide. Duplicate members raise `AmbiguousStateError`; malformed JSON, invalid UTF-8, nonstandard numeric constants, non-finite parsed floats, recursion failure, and invalid input types raise `StateCorruptionError`.

`encode_state` uses `allow_nan=False`, `ensure_ascii=False`, sorted keys, compact separators, and a strict UTF-8 encodability check (`state_codec.py:118-138`). Serialization failures remain `StateSerializationError`.

### 3.2 Lua UTF-8 acceptance matrix

`aep_utf8_check` walks every raw byte (`state_codec.py:152-221`). Its allowed multibyte ranges are the shortest valid UTF-8 encodings only: `C2-DF`, constrained `E0`/`ED`, ordinary `E1-EC`/`EE-EF`, constrained `F0`/`F4`, and ordinary `F1-F3`, each with the required continuation bytes.

The passing 142-case codec/Lua matrix directly covers:

| Required class | Passing cases |
|---|---|
| Isolated continuation bytes | `80`, `BF` |
| Truncation | incomplete two-, three-, and four-byte sequences |
| Invalid leading bytes | `C0`, `C1`, every `F5` through `FF`, including `FE`/`FF` |
| Overlong forms | two-, three-, and four-byte minimum/maximum examples |
| Surrogate code points | UTF-8 encodings of U+D800 and U+DFFF rejected |
| Above U+10FFFF | U+110000 encoding rejected |
| Invalid byte locations | root object name/value, nested object name/value, and object-in-array name/value |
| Valid ASCII | ordinary ASCII and the one-byte upper boundary `7F` |
| Valid two-byte boundaries | `C2 80`, `DF BF` |
| Valid three-byte boundaries | `E0 A0 80`, pre-/post-surrogate boundaries, `EF BF BF` |
| Valid four-byte boundaries | `F0 90 80 80`, `F4 8F BF BF` |
| Valid multilingual text | Urdu, Chinese, accented text, emoji |
| JSON Unicode escapes | valid `\u00e9`, `\u4e2d`, and surrogate-pair escape for emoji |

The UTF-8 pass covers the complete document, not only JSON string values. `aep_json_member_check` invokes it first at `state_codec.py:224-227`. Only then does the recursive scanner locate and decode member names, detect duplicates within each object, and validate JSON structure. The final `pcall(cjson.decode, raw)` is at `state_codec.py:418-419`.

Strict UTF-8 validation did not weaken duplicate-member detection: all valid-UTF-8 duplicate cases still returned the ambiguous result in the shared validator, including root, ledger, intent, transition-history, retention-related, nested-object, object-in-array, equal-value, conflicting-value, unknown-member, and escaped-equivalent-name cases. The 45-case combined P0 suite also retained the integrated duplicate-state protections.

## 4. Mandatory validation order

The three state-interpreting Lua paths satisfy the required order:

| Lua path | Raw fetch/missing handling | UTF-8, duplicate, syntax validation | First lock/TTL read | First semantic state use | Mutation |
|---|---|---|---|---|---|
| Phase 1 save/CAS | `storage.py:191-196`; missing is allowed only for expected first write | stored `:193-195`; candidate `:199-201` | lock `:203` | candidate decode `:216`; current decode/version/marker/ledger `:232-265` | `SET ... EX` `:267` |
| Shared Phase 2 creation/transition CAS | `intents.py:253-254`; missing returns rejection | stored `:256-258`; candidate `:259-261` | lock `:265` | decodes `:267-275`, then version/status/ledger/marker/history/retention checks | `SET ... EX` `:447` |
| Preflight | `intents.py:455-456`; missing returns rejection | stored `:457-459` | lock `:463`, `PTTL` `:464` | decode `:466`, version `:470`, ledger/status `:471-472` | none; read-only |

Within `aep_json_member_check`, raw UTF-8 precedes recursive duplicate detection, the recursive scan proves JSON grammar, and the final `cjson.decode` syntax check occurs before the function returns valid. Therefore the calls shown above do not reach their lock lines until all stored bytes have crossed the complete raw gate.

Candidate serialized state crosses the same gate inside both mutating scripts before it is decoded or trusted. The candidate regressions forced invalid UTF-8 and duplicate-member payloads at the Lua boundary; both Phase 1 and Phase 2 rejected without changing the stored state, and the central mapper returned `StateSerializationError`.

All higher-level operations named in the review reduce to these bodies:

- Phase 1 initial/update/TTL save uses Phase 1 CAS.
- Phase 2 creation, every transition, runner resolution, recovery claim, recovery resolution, and every Phase 2 retention reset use the shared Phase 2 CAS.
- Pre-dispatch inspection uses preflight.
- Recovery scanning reads through the central application codec before eligibility interpretation.

### 4.1 Error precedence

For invalid or ambiguous stored state, the executable precedence matrix proves that the raw classification wins over:

- missing or stale lock token;
- insufficient lock TTL;
- stale version;
- a `PAUSED` state race;
- predecessor and execution-wide ledger decisions;
- marker, transition, and retention interpretation.

The Phase 1 matrix crosses invalid/ambiguous serialization with stale token, missing lock, and stale version. The Phase 2 CAS matrix crosses both raw failure classes with stale or missing locks while also supplying a stale expected version. The preflight matrix crosses both raw classes with stale token or insufficient TTL while also supplying a stale version. The `PAUSED` runner race injects invalid bytes after the second application read and rejects at the creation CAS.

For valid state, the established concurrency precedence remains compatible: a stale token returns `LockAcquisitionError`; with a valid token, a stale version returns `StaleWriteError`; marked valid Phase 2 state preserves those results before the later Phase 2-protection decision (`test_phase2_mutation_safety.py:858-920`).

## 5. Application reads and stable errors

`RedisStorageAdapter._read_raw_state` issues `GET` using redis-py's `NEVER_DECODE` option (`storage.py:651-656`). This returns exact Redis bytes even though the shared fixture and production contract use `decode_responses=True`. Those bytes enter `decode_state` before migration, Pydantic validation, or Phase 2 ledger interpretation.

The decoded-client invalid-byte regression passed and returned `StateCorruptionError`, not `UnicodeDecodeError`, generic `StorageOperationError`, or a raw Redis/Lua error. Duplicate members remain `AmbiguousStateError`. Neither error indicates that an external provider mutation is safe to retry.

The shared Lua codes and their only domain mapping are:

| Lua result | Typed result |
|---|---|
| `-10` stored invalid UTF-8/malformed JSON | `StateCorruptionError` plus best-effort quarantine |
| `-11` stored duplicate member | `AmbiguousStateError` plus best-effort quarantine |
| `-12` candidate invalid UTF-8/malformed JSON | `StateSerializationError` |
| `-13` candidate duplicate member | `StateSerializationError` |

`lua_state_validation_failure` defines the mapping (`state_codec.py:29-64`), and `RedisStorageAdapter._raise_lua_state_validation` applies it (`storage.py:658-678`). Phase 1 CAS, Phase 2 CAS, and preflight all call that same mapper.

Rejected state keys are not logged, normalized, rewritten, deleted, or automatically repaired. Error and warning messages contain identifiers and bounded reasons, not the raw state. Best-effort quarantine may copy the exact value to a separate poison record; invalid bytes are base64 encoded (`storage.py:773-790`). This forensic copy does not alter the original state key.

## 6. Controlled race and ordering results

All state snapshots use exact byte reads with `NEVER_DECODE`. The common rejection helper captures raw bytes and `PTTL` immediately before the operation, times the operation, then requires exact byte equality and TTL decay bounded by elapsed time plus 1,000 ms. Exact byte equality also preserves the serialized version, execution status, ledger, transition history, marker, and retention representation. Where injection happens after an application read, the expected post-operation value is the exact injected byte string.

| Controlled case | Classification and persistence result | Provider/durability evidence |
|---|---|---|
| 1. Phase 1 save against invalid UTF-8 | `StateCorruptionError`; injected bytes/version 1 remain; requested 7,200-second TTL is not applied | Direct storage path has no provider or barrier call site |
| 2. Intent creation after post-read injection | `StateCorruptionError`; injected bytes, empty ledger, version 1, status, and history remain | Direct store call has no provider or barrier call site |
| 3. `PAUSED` changed to invalid UTF-8 after application reads | `StateCorruptionError`; exact injected envelope remains; no intent, version 1, empty ledger, elapsed-time-only TTL | Direct counters: provider `0`; durability acknowledgements `0` |
| 4. Phase 2 transition after post-read injection | `StateCorruptionError`; exact injected ledger and transition history remain | Rejected before any caller-owned post-CAS acknowledgement; direct transition has no provider call |
| 5. Preflight with invalid state and stale token | raw corruption/ambiguity wins; state bytes and TTL preserved | Preflight is read-only and has no provider/barrier call site |
| 6. Preflight with invalid state and short lock TTL | raw corruption/ambiguity wins; state bytes and TTL preserved | Preflight is read-only and has no provider/barrier call site |
| 7. Recovery claim after post-read injection | `StateCorruptionError`; exact injected state remains | Direct counters: provider mutation `0`, readback `0`, acknowledgement `0` |
| 8. Runner resolution after post-read injection | resolution CAS rejects and exact injected state remains | One provider call and one creation acknowledgement occurred before the deliberately late injection; rejection added provider `0` and resolution acknowledgement `0` |
| 9. Recovery resolution after post-read injection | resolution CAS rejects and exact injected state remains | Provider mutation `0`; one readback occurred before the deliberately late injection; rejection added acknowledgement `0` |
| 10. Valid Phase 1 and Phase 2 operations | Unicode Phase 1 update and normal Phase 2 creation succeed; final version 3, one `ABOUT_TO_FIRE` intent | Authorized control path |

The explicit race selection produced `12 passed`: the preflight test expands to four combinations, and the remaining eight selected tests cover the other numbered operations. Rejected pre-dispatch runner paths have zero total provider calls and zero total durability acknowledgements. The runner-resolution case is intentionally post-provider and establishes a zero increment after invalid-state insertion, not a claim that no provider call had historically occurred.

## 7. Compatibility and regression findings

| Compatibility requirement | Result |
|---|---|
| Valid historical Phase 1 state readable and writable | **Pass.** Historical envelope matrix and Phase 1 32/32 suite pass; multilingual update passes. |
| Valid historical Phase 2 state readable | **Pass.** Historical envelope, focused Phase 2, and full integration suites pass. |
| Normal intent creation and transitions | **Pass.** First creation, legal transition table, runner, recovery, and valid raw-gate control pass. |
| Legacy unmarked non-empty ledger protection | **Pass.** It remains readable and Phase 1 replacement is rejected unchanged. |
| Duplicate-member rejection | **Pass.** Python, Lua, post-read creation/transition, preflight, recovery, and P2-001/002/003 regressions pass. |
| Malformed JSON, NaN, Infinity | **Pass.** Rejected by the central codec/Lua matrix. |
| Valid Unicode | **Pass.** ASCII, UTF-8 boundaries, Urdu, Chinese, accents, emoji, and Unicode escapes pass. |
| Valid-state stale token/version behavior | **Pass.** Existing typed precedence remains unchanged. |
| Same-connection CAS/WAITAOF ordering | **Pass.** The 4/4 Redis 7.2 suite asserts `CAS, WAITAOF, provider, CAS, WAITAOF` and matching client IDs for each CAS/barrier pair. |
| Alternative repository state path | **None found.** All production state values use the codec and one of the three raw-gated Lua bodies. |

## 8. Verification commands and unedited summaries

All pytest commands used real Redis database 15 and disabled bytecode and pytest cache writes.

### 8.1 `py_compile` for all source and test files

```powershell
$ErrorActionPreference='Stop'; $compileDir=Join-Path ([IO.Path]::GetTempPath()) ('aep-closure-'+[guid]::NewGuid().ToString('N')); $tempRoot=[IO.Path]::GetFullPath(([IO.Path]::GetTempPath())+[IO.Path]::DirectorySeparatorChar); $resolved=[IO.Path]::GetFullPath($compileDir); if(-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'unsafe compile path'}; New-Item -ItemType Directory -Path $resolved | Out-Null; try { $env:PYTHONPYCACHEPREFIX=$resolved; $pyFiles=@(Get-ChildItem -LiteralPath src,tests -Recurse -Filter '*.py' | Select-Object -ExpandProperty FullName); py -3 -m py_compile @pyFiles; $compileExit=$LASTEXITCODE; Write-Output "py_files=$($pyFiles.Count)"; Write-Output "py_compile_exit_code=$compileExit"; Write-Output "compiled_artifacts=$((Get-ChildItem -LiteralPath $resolved -Recurse -File | Measure-Object).Count)" } finally { Remove-Item -LiteralPath $resolved -Recurse -Force; Write-Output "temp_removed=$(-not (Test-Path -LiteralPath $resolved))" }; exit $compileExit
```

Exit `0`:

```text
py_files=31
py_compile_exit_code=0
compiled_artifacts=68
temp_removed=True
```

### 8.2 Phase 1 storage/CAS suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_cas_write.py tests/test_get_migration.py tests/test_races.py tests/test_uuid_validation.py tests/test_version_range.py -p no:cacheprovider -q
```

Exit `0`; unedited summary: `32 passed in 1.39s`.

### 8.3 Focused Phase 2 suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_mock_connector.py tests/test_phase2_durability.py tests/test_phase2_state_machine.py tests/test_phase2_runner.py tests/test_phase2_recovery.py -p no:cacheprovider -q
```

Exit `0`; unedited summary: `163 passed in 5.81s`.

### 8.4 Combined P0 regression suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_mutation_safety.py tests/test_phase2_duplicate_member_safety.py -p no:cacheprovider -q
```

Exit `0`; unedited summary: `45 passed in 3.97s`.

### 8.5 State-codec and Lua UTF-8 matrix

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_state_codec.py -p no:cacheprovider -q
```

Exit `0`; unedited summary: `142 passed in 2.84s`.

### 8.6 Raw-state validation gate matrix

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_raw_state_validation_gate.py -p no:cacheprovider -q
```

Exit `0`; unedited summary: `26 passed in 1.90s`.

### 8.7 Complete integration-enabled suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests -p no:cacheprovider -q
```

Exit `0`; unedited summary: `431 passed in 34.84s`.

### 8.8 Redis 7.2 WAITAOF suite

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_waitaof_integration.py -p no:cacheprovider -q
```

Exit `0`; unedited summary: `4 passed in 7.03s`.

### 8.9 Explicit controlled race selection

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_raw_state_validation_gate.py::test_phase1_save_rejects_invalid_utf8_without_replacement_or_ttl_refresh tests/test_raw_state_validation_gate.py::test_phase2_creation_rejects_post_read_invalid_utf8_injection tests/test_raw_state_validation_gate.py::test_paused_runner_race_preserves_injected_state_with_zero_side_effects tests/test_raw_state_validation_gate.py::test_phase2_transition_rejects_post_read_invalid_utf8_injection tests/test_raw_state_validation_gate.py::test_preflight_raw_failure_precedes_token_ttl_version_and_status tests/test_raw_state_validation_gate.py::test_recovery_claim_rejects_post_read_invalid_state_before_readback_or_ack tests/test_raw_state_validation_gate.py::test_runner_resolution_rejects_post_read_invalid_state_before_ack tests/test_raw_state_validation_gate.py::test_recovery_resolution_rejects_post_read_invalid_state_before_ack tests/test_raw_state_validation_gate.py::test_valid_phase1_and_phase2_operations_pass_after_raw_gate -p no:cacheprovider -q
```

Exit `0`; unedited summary: `12 passed in 1.12s`.

Every successful pytest command emitted the existing `pytest-asyncio` warning that `asyncio_default_fixture_loop_scope` is unset. There were no test failures or skips in the reported successful runs.

## 9. Redis and workspace integrity

The Docker metadata was `aep-phase2-redis72|redis:7.2.5-alpine|healthy|127.0.0.1:6381->6379/tcp`. Direct Redis inspection before the suites found database 15, Redis 7.2.5, AOF enabled, `appendonly=yes`, `appendfsync=everysec`, zero `aep:*` keys, and `DBSIZE 0`.

The exact final namespace-only cleanup and environment command was:

```powershell
py -3 -c "import redis; r=redis.Redis.from_url('redis://127.0.0.1:6381/15',decode_responses=True); keys=list(r.scan_iter(match='aep:*',count=500)); deleted=r.delete(*keys) if keys else 0; server=r.info('server'); persistence=r.info('persistence'); config=r.config_get('appendonly','appendfsync'); stats=r.info('commandstats'); remaining=list(r.scan_iter(match='aep:*',count=500)); print('selected_db='+str(r.client_info().get('db'))); print('redis_version='+server['redis_version']); print('aof_enabled='+str(persistence['aof_enabled'])); print('appendonly='+config.get('appendonly','')); print('appendfsync='+config.get('appendfsync','')); print('aep_keys_before_cleanup='+str(len(keys))); print('aep_keys_deleted='+str(deleted)); print('aep_keys_after_cleanup='+str(len(remaining))); print('dbsize='+str(r.dbsize())); print('flushall_commandstat_present='+str('cmdstat_flushall' in stats).lower()); r.close()"
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

The database began empty, fixtures create only `aep:*` test keys, fixture cleanup scans and deletes only that namespace, and the final cleanup found nothing to delete. No audit command used `FLUSHALL`; source inspection found no executable `flushall()` call. Because the restart test restarts Redis and resets server command statistics, the no-`FLUSHALL` conclusion also relies on the inspected cleanup implementation and the audit command record, not only the final command-statistic value.

The workspace has no usable Git repository metadata, so integrity was checked with hashes. Before the audit, the source/test manifest covered 70 existing files and had SHA-256 `C61ACC6BCA7CF772957732E550F68F10F3262605D32F66FD25F32E7F9C1BF7FF`. Final verification is recorded below. The protected-file baseline hashes were:

| Protected file | SHA-256 |
|---|---|
| `docs/07-phase2-gap-audit.md` | `2F0333691DC00EA9ED632CE33009348113EBB7F37F32CFEE5B1A8E3114DC48E8` |
| `docs/09-post-waitaof-gate-review.md` | `65DBBC52647D9364BFCDA6A0AA1D53287C1DCF5E3A9F1135164E95D6090694DD` |
| `docs/10-p0-closure-review.md` | `963A9C43476340BC9584B33306876C502B6A4C82715A9BEB048D7DD2FFF6935B` |
| `docs/11-json-closure-gate-review.md` | `9F2FFA41C7825FBE7FA742DABE64E2F8D38434120E3589594BD7197435A25D35` |
| `phase2_implementation_report.md` | `C422A0EF4125D42BC14305E48036569D45EDD47F1A3F37F9DC2E060419D8EBDE` |

The final rehash reproduced every protected hash above. The final 70-file source/test manifest also remained `C61ACC6BCA7CF772957732E550F68F10F3262605D32F66FD25F32E7F9C1BF7FF`. Production code and existing tests were inspected and executed but not edited; this review document is the only repository artifact created by the audit.

## 10. Closure table

| Finding | Classification | Closure basis |
|---|---|---|
| P2-001 — normal retry eligibility and raw-state ambiguity | **CLOSED** | Every repository-defined read and authoritative CAS rejects invalid UTF-8 and duplicates before lease/version/predecessor decisions. Post-read replacement cannot authorize a same-step attempt. Pre-dispatch rejections preserve exact state/retention and have zero provider and durability calls. |
| P2-002 — execution-wide ambiguity fence | **CLOSED** | Raw validation precedes `PAUSED` and complete-ledger interpretation. All blocking-status/duplicate regressions pass, and the `PAUSED` invalid-byte race preserves version 1, empty ledger, exact bytes, and elapsed-time-only TTL with provider `0` and acknowledgement `0`. |
| P2-003 — Phase 1 replacement of Phase 2 state | **CLOSED** | Phase 1 validates stored bytes before token/version/marker/ledger/retention, validates the candidate, and rejects invalid or ambiguous serialization without overwrite, version advancement, history loss, or TTL refresh. Marked and legacy unmarked ledgers remain protected. |

These classifications apply to P2-001/P2-002/P2-003 and all repository-defined raw-state gate paths. They do not close unrelated Phase 2 findings.

## 11. Residual limitations and coverage gaps

- The shared Lua recursive JSON scanner retains its existing nesting limit of 128. An otherwise valid historical document deeper than that can be accepted by an application read but rejected by an authoritative Lua operation.
- Quarantine is best effort, and scheduling ejection/incident handling remains outside this repository. A quarantine failure does not weaken the typed state rejection.
- `NEVER_DECODE` behavior is verified with the installed redis-py client and the checked Redis 7.2.5 endpoint; alternative clients/backends require their own exact-byte compatibility check.
- The Redis evidence is for one local Redis 7.2.5 AOF instance with `appendfsync=everysec`. It is not a proof about an untested deployment or multi-node failure model.
- CAS and WAITAOF remain sequential commands on a pinned connection. The passing integration suite proves the tested local ordering and acknowledgement behavior, not absolute atomicity.
- Direct storage, transition, and preflight methods do not own connector or durability objects; zero external-call evidence for those methods follows both their call graph and unchanged state. Direct counters are attached to the end-to-end runner and recovery cases where those operations exist.
- The deliberately late runner-resolution case has one provider call and one intent durability acknowledgement before injection; the test proves zero additional provider calls and zero resolution acknowledgements after rejection. The recovery-resolution case similarly has one prior readback and zero post-injection acknowledgements.
- P2-004 immutable request binding and P2-010 enforced redaction/safe-value boundaries remain unimplemented and are not changed by this audit.

## 12. P2-004/P2-010 immutable request-binding decision

**GO to begin the bounded P2-004/P2-010 implementation work.** The raw-state gate that would protect the binding metadata now meets the P2-001/P2-002/P2-003 closure conditions. This GO authorizes the next implementation and test stage only; it does not classify P2-004 or P2-010 as closed. The work must bind dispatch to the exact immutable, secret-free request representation and enforce redaction/safe-value rules without persisting unrestricted raw requests.

## 13. Production non-idempotent dispatch decision

**NO-GO for production non-idempotent dispatch.** P2-004/P2-010 and other production-gate findings remain outside this closure and unresolved. Redis state and an external provider remain separate systems, and the verified CAS/WAITAOF sequence does not establish exactly-once effects, absolute atomicity, split-brain prevention, or guaranteed duplicate prevention.

The bounded guarantee remains:

> “Ambiguity, corruption, and contention are detectable; the system fails closed.”
