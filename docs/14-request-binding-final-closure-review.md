# Final P2-004/P2-010 request-binding repository closure review

**Review date:** 2026-07-31  
**Review mode:** independent, defensive, repository-local, read-only except for this review  
**Runtime:** Redis 7.2.5, database 15, AOF enabled, `appendfsync=everysec`

## 1. Executive result

The bounded patch resolves the four repository defects recorded in
`docs/13-request-binding-closure-review.md`:

1. every authoritative Phase 2 state mutation and preflight now compares the
   complete persisted canonical request-binding string exactly;
2. every repository connector consumes a process-local, HMAC-authenticated,
   object-identity-bound, one-use `VerifiedDispatch` capability before its
   modeled provider transmission;
3. the dispatch verification boundary reloads the authoritative binding,
   authenticates the exact vault material, revalidates persisted safe values
   against the selected versioned endpoint profile, rebuilds commitments and
   the descriptor, recomputes both fingerprint and attempt digest, and issues
   provenance only after all checks succeed; and
4. the versioned vault AAD schema covers the required object, material,
   cryptographic, connector, operation, profile, credential, codec, commitment,
   attempt-identity, and deadline fields.

The repository-defined Phase 2 state, evidence, exception, logging,
quarantine, representation, and dispatch-metadata paths use bounded typed
values or fixed reductions. The existing runtime-generated marker tests pass
with zero prohibited occurrences. No alternate mutation connector signature,
real provider client, plaintext vault fallback, production connector, or
production vault/KMS path exists.

The independent classifications are:

| Item | Classification |
|---|---|
| Repository enforcement | **VERIFIED** |
| P2-004 — immutable request binding | **CLOSED (repository scope)** |
| P2-010 — safe-value/privacy boundary | **CLOSED (repository-defined Phase 2 mutation scope)** |
| Production applicability | **NO-GO** |
| Production non-idempotent dispatch | **NO-GO** |

Repository closure is not production closure. The only vault is an explicitly
test-only, process-local, non-durable AES-GCM backend, and the only mutation
connectors are test harnesses. There is no durable production vault/KMS,
operational key lifecycle, production endpoint profile, real provider
transport, or separately reviewed production connector composition.

## 2. Scope, evidence, and integrity method

The review independently read:

- `docs/13-request-binding-closure-review.md`;
- the `2026-07-31 addendum: canonical request-binding repository closure` in
  `phase2_implementation_report.md`;
- the end-of-file `2026-07-31 final delivered-tree closure evidence and
  precedence` note;
- all four changed production files;
- all eight changed existing test/fixture/matrix files; and
- all five new focused test modules listed by the addendum.

Changed production files inspected:

- `src/core/request_binding.py`
- `src/core/request_vault.py`
- `src/core/intents.py`
- `src/core/intent_workflow.py`

Changed existing tests, fixtures, and matrix inspected:

- `tests/request_binding_helpers.py`
- `tests/test_request_canonicalization.py`
- `tests/test_request_vault.py`
- `tests/test_request_binding_intents.py`
- `tests/test_phase2_state_machine.py`
- `tests/test_verified_dispatch.py`
- `tests/mock_connector.py`
- `tests/MATRIX.md`

New focused tests inspected:

- `tests/test_canonical_request_binding_closure.py`
- `tests/test_verified_dispatch_provenance.py`
- `tests/test_endpoint_profile_revalidation.py`
- `tests/test_vault_aad_closure.py`
- `tests/test_privacy_boundary_closure.py`

Repository-wide searches independently inventoried every Lua definition,
`register_script` call, `aep:state:*` access, connector protocol and
implementation, `.mutate` call, vault implementation, request-binding use,
logger call, evidence path, quarantine write, representation override,
production/test-only gate, and network-client import. No external or production
system was accessed.

The workspace contains a `.git` directory but `git status --short` failed with
exit 128 because the directory is not recognized as a Git repository. Therefore
historical deletion or weakening of tests cannot be independently proved from
version-control history. Current-tree inspection found the expected files and
assertions, the integration run collected and passed 611 tests with no skips,
and the source/test manifests remained byte-identical across this audit.

## 3. Independent resolution of the four `docs/13` findings

| `docs/13` finding | Current source evidence | Result |
|---|---|---|
| Lua compared decoded binding tables rather than exact canonical encodings | The persisted `canonical_request_binding` string is compared directly at creation, every later CAS transition, and preflight; other records remain byte-for-byte strings inside outer state equality | **RESOLVED** |
| Connector checked only class and construction used a module token | No usable public constructor or legacy token exists; connector-side consumption checks a closure-held HMAC record, object identity, material hash, canonical binding, context, and monotonic expiry, then atomically consumes it | **RESOLVED for cooperative repository code** |
| Persisted `SafeField.canonical_value` lacked canonical/profile revalidation | `SafeField` requires strict canonical JSON and hides its value; the selected exact profile recursively revalidates persisted values and commitment slots before provenance issuance | **RESOLVED at the mutation boundary** |
| Vault AAD omitted required identities, versions, profiles, keys, and deadlines | `aep.vault-aad/1` authenticates every required field, and existing tests alter each field individually | **RESOLVED in the test-only vault** |

The provenance result is deliberately process-local. Python does not provide a
hardware or privilege boundary inside one interpreter; arbitrary code with
full same-process introspection or memory-tampering authority is outside this
repository capability claim.

## 4. Canonical request-binding review

### 4.1 One strict authoritative representation

`src/core/request_binding.py` defines one request/binding canonicalizer,
`aep.canonical-json/1`, and one persisted binding schema,
`aep.persisted-request-binding/1`. `canonical_request_binding_bytes()` dumps
the frozen typed binding and passes it through that canonicalizer.
`parse_canonical_request_binding()` accepts only bytes that decode and
round-trip to the identical canonical bytes.

The canonicalizer has explicit limits of 1,048,576 bytes and 128 nested
container levels. It:

- uses strict UTF-8 and NFC strings;
- rejects duplicate members through `object_pairs_hook`;
- rejects all floats, including NaN and Infinity;
- rejects unsupported types and non-string object keys;
- permits only null, exact booleans, interoperable-range integers, strings,
  arrays, and string-keyed objects;
- sorts object keys deterministically while preserving array order; and
- distinguishes missing members from explicit null and arrays from objects.

`PersistedRequestBinding` contains the binding schema version; execution,
step, intent, and correlation identities; connector identity and operation;
operation, descriptor, and canonicalization versions; endpoint-profile and
credential-binding identities and versions; wire codec; opaque vault locator;
request-material and vault-object versions; vault encryption key ID;
commitment algorithm and historical key ID; semantic fingerprint; attempt
digest; creation and all three deadlines; and the complete safe descriptor.
The descriptor contains its own request-envelope/profile/codec context,
redacted target, typed public safe values, ordered mutation values, and keyed
protected commitments. No raw protected request value is present.

### 4.2 Authoritative persistence and Lua coverage

`IntentRecord.request_binding` is excluded from Redis serialization.
`canonical_request_binding` is the persisted authoritative value. A bound
record lacking it is rejected; an existing canonical value is strictly parsed
to produce the typed read view; and an unbound legacy record is not backfilled.

The complete Lua inventory is:

| Lua body | State effect | Binding result |
|---|---|---|
| Phase 1 CAS in `src/core/storage.py` | Creates/updates Phase 1 state | Refuses a Phase 2 marker or any non-empty intent ledger, so it cannot mutate or replace a bound intent |
| Phase 2 intent CAS in `src/core/intents.py` | Creates intents and performs ordinary transitions, runner resolution, recovery claim, recovery resolution, and retention-affecting state writes | Creation requires the new canonical string to equal `ARGV[12]`; later mutations require old string = new string = `ARGV[12]`; unbound legacy records require an empty argument and cannot acquire a binding |
| Phase 2 preflight in `src/core/intents.py` | Read-only lease/TTL/version/status/binding check | Requires the persisted canonical string to equal `ARGV[6]`, then checks its digest |
| Release/renew scripts in `src/core/locks.py` | Mutate only lock token/TTL keys | Do not read or mutate intent state |

The decoded Lua `deep_equal` helper remains for non-binding state invariants.
It is not the authoritative request-binding control. Canonical bindings are
strings at that layer and are compared with exact Lua string equality.
Existing ledger records not targeted by a transition also remain equal as
complete outer-record values, including their canonical strings.

Both state-writing CAS bodies and preflight run the shared exact raw UTF-8,
JSON, duplicate-member, and depth scanner before lease, version, status,
marker, ledger, or binding interpretation. The Phase 1 writer cannot bypass
the Phase 2 CAS. Repository searches found no other `aep:state:*` writer or
intent TTL-only mutation.

### 4.3 Rejection behavior and legacy records

Existing tests cover alternate numeric lexemes, empty array/object
substitution, key reordering, missing/additional/modified fields, array order,
identity transplantation, binding removal, retention change, and legacy
binding addition. For direct Lua rejection they assert the exact raw Redis
string is unchanged, which transitively preserves the version, status, entire
ledger, and transition history. TTL assertions permit only elapsed time. The
runner altered-state cases additionally prove zero provider calls and exactly
one historical creation acknowledgement with no post-rejection durability
increment.

Legacy unbound intents remain readable. Preflight rejects their missing
canonical binding, and the CAS refuses adding one. They cannot reach mutation
transport.

## 5. Verified-dispatch boundary

`VerifiedDispatch` is frozen, has `init=False`, has a constructor that always
raises, rejects subclassing, rejects shallow/deep copying, and has a protected
representation. The old predictable/module-level marker does not exist.

At module initialization `_build_dispatch_boundary()` creates a random
32-byte secret and a closure-private identity-record map. Its issuer:

- copies the authenticated exact material to immutable `bytes`;
- canonicalizes the complete binding;
- hashes the exact material;
- creates a random nonce and HMAC provenance over a domain, nonce, material
  digest, and canonical-binding digest;
- binds the record to a weak reference and exact object identity; and
- sets a monotonic expiry no later than the authenticated material deadline.

The issuer function is installed around the successful internal
`RequestBindingService.verify` path and removed from module globals.
Provenance contains no plaintext request, credential, or protected value.

`consume_verified_dispatch()` atomically removes the identity record before
validation. It requires the exact class and same object, validates monotonic
expiry, checks the caller-supplied connector/operation/profile and
execution/step/intent/correlation context against the binding, recomputes the
exact material hash and canonical binding, and compares both plus the HMAC
provenance. The canonical binding transitively ties all material, descriptor,
profile, credential, codec, key, fingerprint, digest, and deadline fields.
Successful consumption returns a new immutable copy of the authenticated exact
bytes. Reuse is impossible because the record has already been consumed.

Every repository mutation connector—the mock connector and the recording
connectors in existing tests—calls this consumer before recording or modeling
provider transmission. `WriteAheadRunner` has one connector mutation call and
one signature, `mutate(*, dispatch: VerifiedDispatch, client_timeout: float)`.
Repository search found no alternate connector signature, provider SDK, HTTP
client, or direct transport path. Recovery calls read-back only and never calls
mutation.

Existing provenance tests reject direct construction, `object.__new__`
forgery, the retired token form, copies, subclasses, look-alikes, reuse, stale
capabilities, every connector/profile/context transplant, exact-material
replacement, binding replacement, and material/descriptor/version/key/digest/
deadline replacement. Caller-owned top-level and nested containers are copied
before vault creation; later mutation does not change the verified bytes. A
valid runner dispatch records exactly one connector call. A connector exception
records that one call and transitions to `FIRED_UNCONFIRMED`; no automatic retry
exists.

This proves repository process-local enforcement, not a production connector
guarantee. The mock connector models an external effect and does not construct
or send a real provider request. Provider-side method/path/query/header/body/
credential sufficiency remains unverified until a production connector profile
exists and is independently reviewed.

## 6. Endpoint-profile revalidation immediately before provenance

The actual source order is:

1. Phase 2 preflight checks the exact prepared canonical binding.
2. The runner reloads the current execution from Redis.
3. It obtains the typed binding only by parsing the persisted canonical string
   and compares that string again with the prepared canonical bytes.
4. `RequestBindingService.verify` checks invocation identity, dispatch expiry,
   minimum retention, and the binding against the service's one exact
   operation/profile/credential/codec tuple.
5. It retrieves the specified locator and the vault authenticates ciphertext
   with the exact versioned AAD.
6. It compares every authenticated metadata field with the invocation and
   authoritative binding.
7. It recursively revalidates persisted public safe fields, mutation options,
   and protected commitment classifications/algorithms/key IDs against the
   selected exact profile.
8. It rebuilds the descriptor and protected commitments from the authenticated
   exact material using the bound historical commitment key.
9. It recomputes and compares the semantic fingerprint and complete descriptor.
10. It recomputes and compares the attempt-specific binding digest.
11. Only the installed wrapper then issues `VerifiedDispatch` provenance.

The requested security dependency is satisfied: authoritative reload, vault
authentication, metadata validation, exact profile checking, typed recursive
safe-value validation, descriptor/commitment reconstruction, fingerprint and
attempt-digest comparison all precede provenance. The literal checklist order
places profile resolution after vault authentication; this implementation
performs the safe context/profile mismatch rejection earlier because one
`RequestBindingService` already owns exactly one profile. No authority is
issued by that early rejection, and vault authentication still precedes all
reconstruction and provenance.

`SafeValueRule` is the authoritative recursive allowlist. Public fields and
mutation options require exact field sets. Object rules require exact members;
array rules require an explicit item rule and maximum length; one-of rules must
match exactly one variant. Protected entries require known names, exact
classifications, the bound commitment algorithm, and the bound historical key.
Name scanning only supplements these typed rules.

Existing tests reject unknown, missing, additional, wrong-type,
wrong-classification, wrong-profile-version, wrong-operation, noncanonical,
unexpected-array/object, invalid nested array/object, extra member, missing
nested member, and extra top-level metadata cases. A descriptor accepted by one
profile is rejected under another operation or profile version. Replacing a
persisted public safe value after durable intent creation produces zero provider
calls and no additional acknowledgement.

## 7. Vault AAD review

`VaultObjectMetadata.authenticated_bytes()` uses the same
`canonical_json_bytes()` function and therefore the same strict UTF-8,
duplicate, type, float, size, depth, NFC, and deterministic ordering rules as
the request binding. The explicit `aep.vault-aad/1` document authenticates:

- AAD schema, opaque locator, vault-object version, request-material version,
  and exact material length;
- AES-GCM algorithm and encryption key ID;
- request envelope, canonicalization, and descriptor versions;
- connector identity, operation, and operation version;
- endpoint-profile identity/version;
- credential-binding identity/version;
- wire codec;
- commitment algorithm and historical commitment key ID;
- execution, step, intent, and correlation identities; and
- creation time, intent-creation deadline, dispatch-material expiry, and
  retention deadline.

The create path authenticates the canonical AAD during AES-GCM encryption. The
read path selects the one metadata key ID, authenticates the same canonical AAD
during decryption, validates material length, and returns exact bytes. Existing
tests compare the AAD model's exact field set, compare AAD bytes with the common
canonicalizer, and individually change all 29 fields. Every alteration raises a
typed vault rejection. Since `read_exact` completes before connector
consumption, these failures occur before modeled provider transport; the runner
suite separately demonstrates zero connector calls for the relevant identity,
profile, version, key, and deadline alterations.

There is no alternate-key loop, metadata repair, locator regeneration,
replacement, overwrite, update, plaintext fallback, or retry after
authentication failure. Create-once and concurrent-create tests remain
unchanged and pass. The backing representation contains nonce, AES-GCM
ciphertext/tag, and safe canonical AAD; existing tests find no exact plaintext
material there.

`TestOnlyInMemoryRequestVault` requires an explicit test-only acknowledgement,
advertises `test_only=True`, is process-local, and is non-durable. Runner startup
defaults to disabled production dispatch and additionally requires an explicit
test-dispatch composition, a test-only vault, and a test-only connector. This
vault is not a durable security boundary and does not provide production-grade
key management.

## 8. P2-010 safe-value and privacy review

Repository searches and source tracing found the following controls:

- exact request material exists only in the request object, authenticated vault
  plaintext during authorized processing, and verified dispatch;
- Redis persists only typed safe descriptor values, HMAC commitments, safe
  identities, hashes, fixed classifications, and audit metadata;
- endpoint profiles use recursive typed allowlists; target validation rejects
  schemes, authorities, user information, query strings, fragments, and other
  unsafe target forms;
- `SafeField` strictly decodes canonical JSON, hides the canonical value from
  `repr`/`str`, forbids extras, freezes instances, and hides rejected inputs;
- enclosing descriptor, binding, intent, and vault models forbid unexpected
  metadata and hide protected binding inputs at their persisted boundaries;
- request, keyring, vault-read, prepared-mutation, verified-dispatch, and
  test-only vault representations redact exact material or keys;
- request/vault/binding errors use stable reason codes; workflow wrappers retain
  only those codes or exception class names and suppress causes;
- mutation exceptions and unknown provider responses become bounded
  `AMBIGUOUS`; recovery unknowns become `UNKNOWN`;
- provider call IDs, opaque provider references, and arbitrary response payloads
  are not persisted by the runner or recovery path;
- evidence accepts only a small exact key set and bounded safe values, then
  persists only its SHA-256 digest;
- quarantine writes only an allowlisted reason, presence bit, byte length, and
  encoding class; raw content is never copied there; and
- logger arguments contain validated execution IDs, bounded reasons, numeric
  timing values, or exception class names—not request, vault, binding,
  dispatch, response, provider, or raw-state objects.

The existing privacy suites exercise nested and case-varied placements, unsafe
targets, safe-field representations, model validation errors, exception causes,
unknown evidence, connector result reduction, logs, quarantine, Redis state,
descriptor/fingerprint output, vault backing bytes, captured pytest output,
cache artifacts, reports, and review Markdown. Typed schemas are authoritative;
the marker scans are supplementary. After this review file was created, the
unchanged privacy module was run again:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_privacy_boundary_closure.py -p no:cacheprovider -q
```

Exit 0: `6 passed in 0.54s`. The module generated one fresh runtime marker per
test case. Its report/docs/cache/captured-output scan asserted
`prohibited_occurrences=0`; pytest intentionally printed no marker value.

Bounded identifiers are syntactic contract values, not a general data-loss-
prevention classifier. A caller violating the contract could choose a
semantically sensitive string that happens to match an identifier grammar.
The review therefore does not claim guaranteed secret non-disclosure. Python
also cannot guarantee erasure of immutable managed-memory objects.

## 9. Regression and compatibility review

| Requirement | Independent result |
|---|---|
| P2-001 unsafe retry eligibility | **Sustained for repository scope**; P0 and full suites pass |
| P2-002 execution-wide ambiguity fence | **Sustained for repository scope**; duplicate/race/fence suites pass |
| P2-003 Phase 1 writer bypass | **Sustained for repository scope**; Phase 1 CAS rejects marked/non-empty-ledger states |
| Strict UTF-8 and duplicate members | **Sustained** in Python and all state-interpreting Lua paths |
| Malformed JSON, NaN, Infinity | **Sustained**; focused codec/Lua and full suites pass |
| Raw-state-before-lock/version/status | **Sustained** in Phase 1 CAS, Phase 2 CAS, and preflight |
| Valid Phase 1 behavior | **Sustained**; 32 focused tests and full suite pass |
| Valid bound Phase 2 behavior | **Sustained**; state-machine/runner/recovery/full suites pass |
| Legacy inspection/no dispatch | **Sustained**; legacy read and failed preflight/binding-addition tests pass |
| Same-connection CAS then WAITAOF | **Sustained**; full integration and standalone Redis 7.2 suite pass |
| Transport after creation acknowledgement | **Sustained** by ordering and exact counter tests |
| Recovery mutation replay | **Absent**; source has read-back only and recovery suites pass |
| Existing tests removed/weakened/bypassed | Current tree contains the documented assertions and 611 tests pass with zero skips; historical proof is **NOT VERIFIED** because Git metadata is unusable |
| Production dispatch | **Disabled** by default and absent as a real composition |

The addendum documents mandatory fixture changes for the new canonical binding,
profile identity, AAD, legacy, duplicate-intent, barrier, and connector contracts.
Inspection confirms that their original behavioral assertions remain present.
Without usable version history, the exact pre-change text cannot be
independently reconstructed.

## 10. Historical-report consistency

The end-of-file `2026-07-31 final delivered-tree closure evidence and
precedence` note explicitly says it supersedes the older P2-004/P2-010
classifications that follow the detailed closure addendum in historical
2026-07-30 material. It then states `VERIFIED`, `CLOSED (repository scope)`,
`CLOSED (repository-defined Phase 2 mutation scope)`, and both production
`NO-GO` decisions. That precedence is clear when the report is read to its end.

There is nevertheless a documentation limitation: an older end-positioned
`2026-07-30 final report precedence note` still says P2-004 and P2-010 are
partially closed, while the later delivered-tree note supersedes it. The report
also contains older statements that the vault/request-binding stage was absent.
These are labeled historical but can confuse readers who stop before the final
note. This audit did not edit the implementation report.

## 11. Verification commands and observed results

Every pytest command used Redis DB 15, disabled Python bytecode writes, and
disabled pytest's cache provider. Integration runs explicitly selected the
Redis 7.2 container. No test command invoked `FLUSHALL`.

### 11.1 Compilation

Exact command:

```powershell
$ErrorActionPreference='Stop'; $compileDir='C:\tmp\aep-final-closure-review-pyc'; $resolved=[IO.Path]::GetFullPath($compileDir); $allowed=[IO.Path]::GetFullPath('C:\tmp\'); if(-not $resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'unsafe compile path'}; if(Test-Path -LiteralPath $resolved){throw 'compile path already exists'}; New-Item -ItemType Directory -Path $resolved | Out-Null; try { $env:PYTHONPYCACHEPREFIX=$resolved; $pyFiles=@(Get-ChildItem -LiteralPath 'src','tests' -Recurse -Filter '*.py' | Select-Object -ExpandProperty FullName); py -3 -m py_compile @pyFiles; $compileExit=$LASTEXITCODE; $artifactCount=(Get-ChildItem -LiteralPath $resolved -Recurse -File | Measure-Object).Count; Write-Output "py_files=$($pyFiles.Count)"; Write-Output "py_compile_exit_code=$compileExit"; Write-Output "compiled_artifacts=$artifactCount" } finally { if(Test-Path -LiteralPath $resolved){ Remove-Item -LiteralPath $resolved -Recurse -Force }; Write-Output "temp_removed=$(-not (Test-Path -LiteralPath $resolved))" }; exit $compileExit
```

The first sandboxed attempt exited 1 before directory creation with
`UnauthorizedAccessException` for the dedicated `C:\tmp` directory. It created
no repository file. The identical approved rerun exited 0:
`py_files=43`, `py_compile_exit_code=0`, `compiled_artifacts=80`,
`temp_removed=True`.

### 11.2 Existing unchanged test suites

| Selection | Exact command after the common environment prefix | Exit | Result |
|---|---|---:|---|
| Five focused closure/provenance/profile modules | `py -3 -m pytest tests/test_canonical_request_binding_closure.py tests/test_verified_dispatch_provenance.py tests/test_endpoint_profile_revalidation.py tests/test_vault_aad_closure.py tests/test_privacy_boundary_closure.py -p no:cacheprovider -q` | 0 | `93 passed in 2.95s` |
| Canonicalization and request binding | `py -3 -m pytest tests/test_request_canonicalization.py tests/test_canonical_request_binding_closure.py tests/test_request_binding_intents.py -p no:cacheprovider -q` | 0 | `57 passed in 5.86s` |
| Vault, AAD, endpoint profile, privacy | `py -3 -m pytest tests/test_request_vault.py tests/test_vault_aad_closure.py tests/test_endpoint_profile_revalidation.py tests/test_privacy_boundary_closure.py -p no:cacheprovider -q` | 0 | `59 passed in 1.33s` |
| Verified dispatch and provenance | `py -3 -m pytest tests/test_verified_dispatch.py tests/test_verified_dispatch_provenance.py -p no:cacheprovider -q` | 0 | `64 passed in 5.33s` |
| Phase 1 storage/CAS | `py -3 -m pytest tests/test_cas_write.py tests/test_get_migration.py tests/test_races.py tests/test_uuid_validation.py tests/test_version_range.py -p no:cacheprovider -q` | 0 | `32 passed in 2.05s` |
| Focused Phase 2 | `py -3 -m pytest tests/test_mock_connector.py tests/test_phase2_durability.py tests/test_phase2_state_machine.py tests/test_phase2_runner.py tests/test_phase2_recovery.py -p no:cacheprovider -q` | 0 | `163 passed in 10.88s` |
| P0 mutation/duplicate regression | `py -3 -m pytest tests/test_phase2_mutation_safety.py tests/test_phase2_duplicate_member_safety.py -p no:cacheprovider -q` | 0 | `45 passed in 7.05s` |
| State-codec/Lua validation | `py -3 -m pytest tests/test_state_codec.py tests/test_phase2_duplicate_member_safety.py -p no:cacheprovider -q` | 0 | `152 passed in 6.75s` |
| Raw-state gate | `py -3 -m pytest tests/test_raw_state_validation_gate.py -p no:cacheprovider -q` | 0 | `26 passed in 3.92s` |
| Explicit accepted/rejected dispatch | `py -3 -m pytest tests/test_verified_dispatch.py -p no:cacheprovider -q` | 0 | `34 passed in 7.13s` |

The common environment prefix for those rows was exactly:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1';
```

Complete integration-enabled command:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests -p no:cacheprovider -q
```

Exit 0: `611 passed in 57.34s`; zero failures and zero skips.

Standalone Redis 7.2 WAITAOF command:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_waitaof_integration.py -p no:cacheprovider -q
```

Exit 0: `4 passed in 9.43s`; no infrastructure failure or rerun was required.

Counter-focused command:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_verified_dispatch.py -p no:cacheprovider -q -k "test_valid_binding_dispatches_exactly_once_as_verified_object or test_unsafe_request_rejection_has_no_intent_call_ack_or_canary_output or test_missing_vault_after_durable_intent_has_zero_calls_and_no_extra_ack or test_altered_authenticated_metadata_has_zero_calls_and_one_historical_ack or test_noncanonical_binding_encoding_after_durable_creation_preserves_exact_state or test_connector_exception_is_single_call_and_safe_evidence"
```

Exit 0: `25 passed, 9 deselected in 3.87s`.

No pytest run in this audit failed or required a rerun. The compilation
temporary-directory denial above was the only prescribed-command
infrastructure failure. An initial read-only PowerShell manifest formulation
was also discarded because this PowerShell/.NET runtime lacked
`Path.GetRelativePath`, `SHA256.HashData`, and `Convert.ToHexString`; the
successful Python one-liner below was used instead and made no file changes.

## 12. Counter evidence

| Controlled case | Intent/state | Provider calls | Durability acknowledgements |
|---|---|---:|---:|
| Unsafe request or default-disabled production composition before creation | No new intent | 0 | 0 |
| Valid verified dispatch and confirmed resolution | Bound `FIRED_CONFIRMED` | 1 | 2 |
| Missing, expired, or unauthenticated vault after creation | Original bound `ABOUT_TO_FIRE` | 0 | 1 historical creation acknowledgement; 0 additional |
| Individually altered authenticated metadata in runner cases | Original bound `ABOUT_TO_FIRE` | 0 | 1 historical creation acknowledgement; 0 additional |
| Persisted safe-value or profile replacement | Binding retained/rejected before transport | 0 | 1 historical creation acknowledgement; 0 additional |
| Noncanonical numeric or empty-container binding replacement | Exact injected raw value/version/status/history retained | 0 | 1 historical creation acknowledgement; 0 additional |
| Direct rejected Lua transition | Exact raw value/version/status/ledger/history retained; elapsed-time-only TTL | No provider interface in this path | No durability interface in this path |
| Connector exception after real modeled call | `FIRED_UNCONFIRMED` | 1 | 2; no automatic retry or later call |

These are assertions in unchanged existing tests, not inferred totals. In
particular, post-creation rejection is not misreported as zero historical
acknowledgements.

## 13. Redis and manifest evidence

Container/configuration inspection reported:

```text
aep-phase2-redis72|redis:7.2.5-alpine|healthy|127.0.0.1:6381->6379/tcp
selected_db=15
redis_version=7.2.5
aof_enabled=1
appendonly=yes
appendfsync=everysec
```

Final namespace-only cleanup/inspection used `SCAN` with pattern `aep:*` and
deleted only returned keys:

```text
aep_keys_before_cleanup=0
aep_keys_deleted=0
aep_keys_after_cleanup=0
dbsize=0
flushall_commandstat_present=false
```

No command invoked `FLUSHALL`.

The manifest algorithm sorted repository-relative POSIX paths, paired each
with its SHA-256 as `path<TAB>hash`, joined rows with LF, and SHA-256 hashed the
UTF-8 result. Before and after all compilation/test execution:

```text
broad src/tests files=88
broad src/tests manifest SHA-256=cda91d328f2469acde42b755153a8872c20475a610802fec36910325a12556de
Python src/tests files=43
Python src/tests manifest SHA-256=c921de204b067ea79ce9703aada13caac298ce35c00efc4301739d8a2dc15ff9
```

Successful exact manifest command:

```powershell
py -3 -c "import hashlib,pathlib; root=pathlib.Path('.').resolve(); fs=sorted((p for d in ('src','tests') for p in (root/d).rglob('*') if p.is_file()),key=lambda p:p.as_posix()); rows='\n'.join(f'{p.relative_to(root).as_posix()}\t{hashlib.sha256(p.read_bytes()).hexdigest()}' for p in fs).encode(); py=sorted((p for d in ('src','tests') for p in (root/d).rglob('*.py') if p.is_file()),key=lambda p:p.as_posix()); prows='\n'.join(f'{p.relative_to(root).as_posix()}\t{hashlib.sha256(p.read_bytes()).hexdigest()}' for p in py).encode(); print(f'broad_files={len(fs)}'); print('broad_manifest_sha256='+hashlib.sha256(rows).hexdigest()); print(f'python_files={len(py)}'); print('python_manifest_sha256='+hashlib.sha256(prows).hexdigest())"
```

Protected-document SHA-256 values remained unchanged where an initial and
final value was captured; `docs/08` was additionally hashed during the final
protected set check:

| Protected file | SHA-256 |
|---|---|
| `docs/07-phase2-gap-audit.md` | `2f0333691dc00ea9ed632ce33009348113ebb7f37f32cfee5b1a8e3114dc48e8` |
| `docs/08-production-connector-design.md` | `c08d3fc545138f05275a100affcdd5631085c2751b4700047ca1aaa6b1e848bf` |
| `docs/09-post-waitaof-gate-review.md` | `65dbbc52647d9364bfcda6a0aa1d53287c1dcf5e3a9f1135164e95d6090694dd` |
| `docs/10-p0-closure-review.md` | `963a9c43476340bc9584b33306876c502b6a4c82715a9beb048d7dd2fff6935b` |
| `docs/11-json-closure-gate-review.md` | `9f2ffa41c7825fbe7fa742dabe64e2f8d38434120e3589594bd7197435a25d35` |
| `docs/12-raw-state-gate-closure-review.md` | `82a2172d454524f8ed544b8e28c571f42158f8771de5182281b6332a8dd51622` |
| `docs/13-request-binding-closure-review.md` | `2b4c0cf14d87ae60d071b934bc5eecfbad3b01df77eeff43b5b9baffcd14e6cf` |
| `phase2_implementation_report.md` | `a686159febda37cb4d1a1a54304ee67639255ad13d4ec4dab044474aa33a974c` |

## 14. Repository-enforcement verdict

**VERIFIED.** Within the repository-defined Phase 2 mutation boundary, the
complete strict canonical binding is authoritative in Redis and compared
exactly in every relevant Lua mutation and preflight; raw-state validation
retains precedence; vault material and complete metadata are authenticated;
persisted values are revalidated against the exact endpoint profile; all
recomputed descriptor/fingerprint/digest values must match; and connector
transport authority is a one-use process-local capability consumed before the
only modeled provider mutation path.

## 15. P2-004 classification

**CLOSED (repository scope).** Every repository-defined provider mutation is
reachable only through successful authentication of exact vault bytes,
comparison against the immutable authoritative canonical binding, and
connector-side consumption of verified provenance. The repository has no
alternate provider mutation path. This does not close production P2-004:
durable vault/KMS, operational keys, credentials, provider-specific exact
transport derivation, and a production connector are absent.

## 16. P2-010 classification

**CLOSED (repository-defined Phase 2 mutation scope).** Typed profile rules,
strict canonical safe values, fixed evidence/exception reductions, safe
quarantine/logging, protected representations, and dispatch metadata cover all
repository-defined Phase 2 mutation paths found by the audit. This does not
assert universal data-loss prevention, guaranteed secret non-disclosure, or
production connector response/reference safety.

## 17. Verified and unverified guarantees

| Guarantee | Status | Boundary |
|---|---|---|
| Exact authoritative canonical binding equality in all repository intent mutations and preflight | **VERIFIED** | Redis DB 15, current Lua/call sites |
| Strict 1 MiB/128-depth canonical format and rejection rules | **VERIFIED** | Source plus focused/full tests |
| Rejected binding mutations preserve raw state and elapsed-time-only TTL | **VERIFIED** | Existing altered-state tests |
| Legacy unbound records are inspectable but cannot bind or dispatch | **VERIFIED** | Source and existing tests |
| Connector-verifiable, process-local, one-use provenance | **VERIFIED** | Cooperative current Python process and repository connectors |
| Caller-container mutation cannot change verified bytes | **VERIFIED** | Top-level and nested existing tests |
| Exact profile revalidation/reconstruction before provenance | **VERIFIED** | Current single-profile service boundary |
| Complete canonical AAD field coverage and altered-field rejection | **VERIFIED** | Test-only in-memory AES-GCM vault |
| Provider call after creation durability; no automatic retry | **VERIFIED** | Test runner and counter suites |
| Recovery never replays a mutation | **VERIFIED** | Read-back-only source and recovery tests |
| P2-010 repository Phase 2 mutation-path reductions | **VERIFIED** | Current state/workflow/connector/evidence/log/quarantine/representation paths |
| Historical proof that no test text was removed or weakened | **NOT VERIFIED** | Git metadata is unusable; current tree only |
| Resistance to arbitrary malicious same-process Python introspection/memory tampering | **NOT VERIFIED / NOT A PROCESS BOUNDARY** | Python runtime limitation |
| Durable production vault/KMS and operational key lifecycle | **ABSENT** | Outside this stage |
| Production connector/profile and exact provider request derivation | **ABSENT** | Outside this stage |
| Production credential lifecycle and connector response/reference privacy | **ABSENT** | Outside this stage |
| Multi-node coordination or split-brain prevention | **NOT VERIFIED / NOT CLAIMED** | Single Redis node only |
| Exactly-once effects, absolute Redis/provider atomicity, guaranteed duplicate prevention | **NOT VERIFIED / NOT CLAIMED** | Redis and provider remain separate systems |
| Guaranteed secret non-disclosure or Python memory erasure | **NOT VERIFIED / NOT CLAIMED** | Bounded controls and managed-runtime limitation |

## 18. Residual security, reliability, compatibility, and coverage limitations

- The AES-GCM vault is test-only, process-local, and non-durable. It is not a
  production security boundary.
- No production KMS, access control, audit integration, rotation, key
  destruction, backup/recovery, retention enforcement, or operational key
  lifecycle exists.
- No real provider request is built or sent. Method/path/query/header/body/
  credential derivation and provider response/reference schemas are unverified.
- A closure-held Python capability is strong against ordinary construction and
  substitution but is not isolation from arbitrary hostile code already
  executing with full interpreter introspection or memory access.
- Commitment equality permits scoped equality correlation. HMAC commitments are
  not encryption.
- Syntactically safe identifiers do not prove that a caller has not placed
  semantically sensitive content in an identifier slot.
- The Lua state validator has a fixed 128-level nesting limit. Application
  behavior outside that boundary is not generalized to deeper documents.
- Redis evidence covers one local Redis 7.2.5 node and database 15. There is no
  multi-node coordination, consensus, or split-brain prevention.
- CAS and WAITAOF are sequential commands on one pinned connection. WAITAOF
  proves only the tested local AOF acknowledgement, not Redis/provider
  atomicity.
- External ambiguity remains unavoidable after a provider may have received a
  mutation and before a conclusive response is durably recorded.
- Quarantine is best-effort; its failure does not replace the original
  fail-closed corruption result.
- The runtime-marker and schema tests are bounded evidence, not a universal
  guarantee of protected-value non-disclosure.
- Python and the cryptographic library cannot guarantee zeroization of
  immutable in-memory objects.
- Historical test deletion/weakening is not independently provable without a
  usable repository history, although the current expected assertions and
  complete suite pass.

## 19. Recommendation for beginning durable production vault/KMS implementation

**GO to begin the separately bounded implementation stage; production
applicability remains NO-GO.** The repository request-binding boundary is
sufficiently closed to start designing and implementing the durable
production vault/KMS, operational key lifecycle, create-once durability,
access controls, retention, recovery, rotation, and audit behavior. That new
stage must pass its own independent review before any production use. This
recommendation does not authorize deployment, real credentials, or provider
calls.

## 20. Separate first-production-connector recommendation

**NO-GO to enable the first production connector until the durable vault/KMS
stage passes its own review.** After that stage, a concrete connector profile
must separately define and prove every effect-changing transport field,
method/path/query/header/body/codec/content-type rule, authentication boundary,
response/reference safe schema, timeout behavior, and connector-side
provenance consumption.

## 21. Production non-idempotent dispatch

**NO-GO.** Production applicability is **NO-GO**, and production
non-idempotent dispatch must remain disabled. Repository-scope closure does not
establish exactly-once external effects, absolute Redis/provider atomicity,
split-brain prevention, guaranteed duplicate prevention, guaranteed secret
non-disclosure, guaranteed in-memory erasure, or production-grade security from
the test-only vault.

“Ambiguity, corruption, and contention are detectable; the system fails closed.”
