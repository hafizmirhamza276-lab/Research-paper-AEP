# P2-004/P2-010 request-binding closure review

**Review date:** 2026-07-31  
**Review mode:** independent, focused, defensive, read-only repository audit  
**Implementation baseline:** the 2026-07-30 P2-004/P2-010 addendum in `phase2_implementation_report.md`  
**Runtime:** Redis 7.2.5, database 15, AOF enabled, `appendfsync=everysec`

## 1. Executive result

The repository now has a substantial test-only immutable request-binding boundary. The normal runner path constructs a versioned canonical request envelope, derives a typed safe descriptor and keyed protected-value commitments, stores the exact bytes in an authenticated create-once test vault, durably creates a bound intent, performs an atomic preflight, authenticates and recomputes the binding, and passes a frozen `VerifiedDispatch` to the test connector. Existing regression suites confirm that this path remains after the required durability acknowledgement and that connector exceptions are not automatically retried.

The reported repository enforcement is nevertheless only **PARTIALLY VERIFIED**, not `VERIFIED`. Static inspection found material limits that the existing tests do not close:

1. Lua compares decoded binding tables recursively, not their complete canonical byte encodings. The comparison does not explicitly preserve the JSON array/object distinction for empty containers or numeric lexical distinctions. Existing tests do not cover those representations, so complete canonical binding equality is not independently established.
2. `VerifiedDispatch` construction is guarded by a module-level Python token, but ordinary Python code can reference module-private names, and the connector checks only the exact class. There is no connector-side provenance evidence that is cryptographically or capability-wise unavailable outside `RequestBindingService.verify`.
3. `SafeField.canonical_value` is a bounded string on persisted model load; it is not decoded and revalidated against the selected endpoint profile's `SafeValueRule`. The normal construction and dispatch-verification path revalidates it, but the general persisted-model boundary is not itself a complete typed safe-value boundary.
4. Vault associated data authenticates many important fields, but it does not contain execution ID, step ID, operation version, endpoint-profile ID/version, credential-binding ID/version, wire-codec version, or the intent-creation deadline. Some of those values are separately protected by encrypted request material, the Redis binding, or the attempt digest, but the requested all-fields AAD claim is not met.
5. No durable production vault/KMS backend or production connector profile exists. Consequently, exact provider-side request sufficiency, dynamic authentication separation, production key lifecycle, and endpoint-specific response/reference privacy cannot be verified.

The existing test results sustain the earlier P2-001, P2-002, and P2-003 closures for their repository-defined scope. No regression was observed in Phase 1 CAS, strict raw UTF-8/JSON handling, duplicate-member rejection, recovery non-replay, or same-connection CAS/WAITAOF ordering.

Final classifications are:

| Item | Result |
|---|---|
| Repository enforcement | **PARTIALLY VERIFIED** |
| P2-004 — immutable request binding | **PARTIALLY CLOSED** |
| P2-010 — safe-value/privacy boundary | **PARTIALLY CLOSED** |
| Production applicability | **NO-GO** |
| Production non-idempotent dispatch | **NO-GO** |

## 2. Scope, method, and evidence limits

The review inspected the requested production modules, all production Lua, all connector/provider interfaces, the changed Phase 1 and Phase 2 fixtures and tests listed in the implementation addendum, `tests/MATRIX.md`, `pyproject.toml`, the complete dated addendum, and `docs/12-raw-state-gate-closure-review.md`. Repository-wide searches covered request material, credentials, query/URL forms, payment and personal-value categories, flexible mappings, provider calls, connector signatures, `VerifiedDispatch`, JSON codecs, hashing, HMAC, AES-GCM, key IDs, Redis reads/writes, exceptions, logging, quarantine, representations, and test-only gates.

The user subsequently bounded executable verification to unchanged repository suites and static inspection. No standalone audit program, new adversarial tool, direct cryptographic manipulation, external system, or production service was used. Conditions not exercised by an existing test are therefore classified `NOT VERIFIED` or `COVERAGE LIMITATION`; they are not inferred as passing.

The workspace has a `.git` directory but is not recognized by Git (`git rev-parse --is-inside-work-tree` exited 1 with “not a git repository”). Historical deletion, weakening, or conditional bypass of tests therefore cannot be independently proved from version-control metadata. Direct manifests and protected-file SHA-256 hashes are used for this audit's before/after integrity check.

## 3. Static path and interface inventory

Exactly three production Lua bodies interpret execution state:

| Path | State behavior | Binding/raw-state enforcement |
|---|---|---|
| Phase 1 CAS, `src/core/storage.py:159-270` | Creates or updates Phase 1 state | Shared raw UTF-8/JSON gate; refuses marked or non-empty-ledger Phase 2 state |
| Phase 2 intent CAS, `src/core/intents.py:313-530` | Creates intents and performs every normal, runner-resolution, recovery-claim, and recovery-resolution transition | Shared raw gate; creation identity/retention checks; later decoded-table binding equality |
| Preflight, `src/core/intents.py:533-572` | Read-only lease/TTL/version/status/binding check | Shared raw gate; digest comparison and decoded-table binding comparison |

The two Lua scripts in `src/core/locks.py` operate only on lock tokens (`GET`, `DEL`, and `PEXPIRE`) and do not interpret execution state. No other production `aep:state:*` writer, TTL-only state mutation, alternate decoder, or production connector call path was found.

The only mutation interface is `ExternalMutationConnector.mutate(*, dispatch: VerifiedDispatch, client_timeout: float)` in `src/core/intent_workflow.py:31-34`. The only implementation is the test-only connector in `tests/mock_connector.py:375-504`. Production code has one mutation call, at `src/core/intent_workflow.py:398-402`. Recovery uses only `read_back(context=ReconciliationContext, ...)` and does not receive exact request material.

Direct connector calls found in tests use the existing verified-dispatch fixture to exercise the mock harness. No production connector, provider SDK, HTTP client, connector registry, scheduler, operator endpoint, or alternate mutation signature exists.

## 4. Exact request envelope

### 4.1 Verified properties

`build_exact_request_bytes` constructs `aep.mutation-request/1` through `aep.canonical-json/1`. The envelope contains:

- envelope, canonicalization, and descriptor versions;
- connector operation and operation version;
- endpoint-profile ID and version;
- credential-binding ID and version;
- wire-codec version;
- validated target;
- ordered field-entry arrays for exact public fields, protected fields, and mutation options;
- protected field name, classification, encoding, and exact encoded value.

The request input is defensively copied at `ExactMutationRequest` construction. Public fields and mutation options are immediately canonicalized to immutable byte tuples; protected strings/bytes are copied into tuples. `build_exact_request_bytes` returns immutable `bytes`. The existing caller-mutation test changes the original top-level containers after vault creation and confirms that connector bytes remain those originally authenticated by the vault.

The exact envelope is distinct from `SafeSemanticDescriptor`. Redis persists only `PersistedRequestBinding`, whose protected entries are HMAC commitments rather than raw values. Repository searches found no exact-envelope write to Redis, quarantine, evidence, or logging. Custom representations for request, vault-read, prepared-mutation, and verified-dispatch objects suppress exact material.

### 4.2 Unverified completeness

The envelope does not contain an explicit HTTP method, concrete transport path/template, or content type. Those could be deterministically implied by the connector operation, endpoint-profile version, and wire-codec version, but no production endpoint-profile implementation exists to define or verify such derivation. The test connector does not build a real provider request from the exact bytes; it models effect state by intent identity. Therefore the claim that the envelope is sufficient to reproduce a complete provider-side mutation is **NOT VERIFIED**.

Credential-binding ID/version and the safe descriptor's `authentication-profile-only/1` policy bind a safe dynamic-authentication selection. Because there is no production credential loader or connector, the review cannot prove that future dynamic credentials affect authentication only, or that no credential/transport policy can alter semantic request identity. This is a **COVERAGE LIMITATION**.

Targets reject schemes, authorities, URL user information, query strings, fragments, `@`, and backslashes. Public fields and mutation options are exact profile allowlists. Amount-like examples use bounded integer minor units and ordered arrays remain order-sensitive. Currency, quantity, destination, account, and equivalent values would require explicit production profile fields; none are implemented.

## 5. Canonicalization and semantic fingerprint

### 5.1 Verified properties

`canonical_json_bytes` uses UTF-8, `ensure_ascii=False`, `sort_keys=True`, fixed compact separators, and `allow_nan=False`. It distinguishes null, exact booleans, integers, strings, arrays, and objects; rejects floats, NaN, infinity, non-string keys, and unsupported object types; and restricts integers to the interoperable ±(2^53−1) range. Strings must already be NFC and valid strict UTF-8, so there is no undocumented lossy Unicode normalization.

Canonical decode is limited to 1,048,576 bytes, rejects duplicate members before constructing a mapping, rejects floats/constants, and requires byte-for-byte canonical re-encoding. Request material is also limited to 1,048,576 bytes. Safe strings and stored canonical field values are bounded to 8,192 bytes. Timestamps in the binding/vault contracts are strict non-negative UTC Unix epoch milliseconds.

The existing suite verifies insertion-order independence, scalar type distinctions, Unicode behavior, array-order sensitivity, rejection classes, and cross-process fingerprint stability. The semantic fingerprint is exactly:

```text
SHA-256(canonical_json_bytes(safe_descriptor.model_dump(mode="json")))
```

The descriptor contains `AEP_REQUEST_FINGERPRINT_V1` as its fixed fingerprint-domain field and contains no raw protected value. Protected changes alter their keyed commitments and therefore the fingerprint.

### 5.2 Limitations

The request canonicalizer has no explicit recursion/nesting counter. Excessive nesting eventually fails through Python recursion behavior rather than a documented deterministic canonicalization limit. This does not meet the requested explicit nesting-limit guarantee.

`_canonical_value` accepts both lists and tuples and serializes both as JSON arrays. The typed rule later sees the decoded list, so a caller tuple can be normalized to the same representation as a list. Existing tests do not document or exercise this input-type normalization.

The cross-process test uses the same interpreter, dependencies, and platform. Locale, alternate Python versions, alternate Unicode databases, and other operating systems were not exercised. The code has no locale or timezone dependency, but cross-platform equivalence remains a reasoned static conclusion rather than multi-platform evidence.

The mutation-difference test samples operation version, endpoint profile, target, public action, protected value, boolean option, and array order. It does not independently enumerate every descriptor field. Static inspection shows all descriptor fields enter the canonical hash, but exhaustive per-field behavioral coverage is incomplete.

## 6. Protected-value commitments

Protected commitments use `HMAC-SHA-256`, not unkeyed hashing. Keys must be explicitly provided and at least 32 bytes. There is no generated, environment-derived, development, or fallback commitment key. Missing historical keys raise the stable `commitment-key-unavailable` reason code.

The HMAC message is a sequence of 32-bit length-framed components:

1. `AEP_SENSITIVE_FIELD_V1`;
2. `aep.safe-request/1`;
3. canonical connector-operation, operation-version, endpoint-profile-ID, and endpoint-profile-version context;
4. protected field identity;
5. canonical protected encoding/value object.

The protected encoding is therefore commitment-bound. Classification is present in the safe descriptor and semantic fingerprint, while field identity and endpoint-profile context connect it to the code-owned classification. The commitment itself does not directly include the classification string.

The persisted descriptor includes algorithm and key ID. Verification selects the persisted historical commitment key ID, recomputes the descriptor, and does not rewrite it using the active key. The commitment keyring and vault keyring are separate objects and tests provision different keys. The code does not enforce that their underlying bytes differ, so key separation remains an operational requirement rather than a checked invariant.

Commitment equality has a privacy cost. With a fixed commitment key, field identity, operation context, and exact protected representation, equal inputs produce equal commitments. This enables equality correlation within that scope. HMAC output is a keyed commitment, not encryption, and must not be described as hiding equality.

## 7. Authenticated vault review

### 7.1 Verified test-backend properties

`RequestVault` exposes only create-once and exact-read methods. The concrete test backend has an `update` method solely to return `vault-update-forbidden`; the protocol has no update operation. Locators use a non-semantic `vault_` format and are generated with `secrets.token_urlsafe(24)`. Collision checks and encryption occur under one `asyncio.Lock`, and the concurrent test permits exactly one creation.

The backend uses `cryptography`'s `AESGCM` with a fresh `os.urandom(12)` nonce per object. AES key lengths are restricted to 16, 24, or 32 bytes. The backing representation contains nonce, combined ciphertext/tag, and safe metadata, not plaintext. There is no plaintext file/Redis fallback, auto-repair, automatic locator regeneration, or replacement after integrity failure.

Associated data currently includes:

- opaque locator;
- object version and encryption key ID;
- envelope schema;
- connector operation;
- descriptor version;
- intent and correlation IDs;
- creation, expiry, and retention times;
- exact material length.

Existing tests verify exact byte readback, collision/update rejection, missing and expired errors, altered ciphertext, one altered metadata identity, missing encryption key, concurrent creation, and absence of fixture plaintext from the backing representation. Runner tests verify zero provider calls with one historical creation acknowledgement when the vault is missing, expired, or unauthenticated after durable intent creation.

### 7.2 Gaps and non-production status

AAD omits execution ID, step ID, operation version, endpoint-profile ID/version, credential-binding ID/version, wire-codec version, and intent-creation deadline. These values are protected elsewhere to varying degrees, but the requested single authenticated-metadata coverage is not present.

The unchanged tests do not individually alter nonce, tag, locator, object version, envelope version, connector identity, correlation identity, every time field, or every key-ID condition. Only ciphertext and intent metadata are directly altered. Wrong-key bytes under an existing key ID, as distinct from a missing key, are not exercised. Per the revised audit scope, these cases are **NOT VERIFIED** rather than newly probed.

`VaultObjectMetadata` validates object version but accepts any bounded safe envelope/descriptor/connector identifier. `RequestBindingService.verify` supplies the fixed version checks, so the vault alone does not classify every unsupported envelope/descriptor version as `VaultVersionError`.

The backend is explicitly `TestOnlyInMemoryRequestVault`, requires `test_only_acknowledgement=True`, is process-local, and is non-durable. It has no KMS, access control, audit trail, secure deletion, rotation workflow, backup/restore, or operational retention enforcement. It is not a production-capable security boundary.

## 8. Fingerprint and attempt-binding separation

The semantic fingerprint and attempt digest have different domains and purposes. The digest manifest contains `AEP_ATTEMPT_REQUEST_BINDING_V1` and covers:

- semantic fingerprint;
- vault locator and material version;
- execution, step, intent, and correlation IDs;
- descriptor and endpoint-profile versions;
- vault-object version;
- creation time, intent-creation deadline, dispatch-material expiry, and retention deadline.

The code therefore covers every minimum field requested. Connector operation, operation version, endpoint-profile ID, credential-binding identity/version, wire-codec version, commitment information, and encryption-key ID are not direct digest fields. The semantic fingerprint indirectly covers the connector/profile/credential/wire fields through the descriptor; vault/key metadata are checked separately during verification and are immutable in Redis transitions.

Existing digest tests change every listed digest input except `step_id`; static inspection confirms `step_id` is present in the manifest. Creation/verification context checks and digest fields prevent execution, step, intent, correlation, locator, and retention transplant in the normal service path. Only cross-execution creation transplant is directly tested; a complete binding transplant between two already-persisted intents/connectors/retention contexts is not.

The 64-hex formatting of fingerprint and digest is identical, but the fixed manifest/descriptor domains and recomputation paths are separate. Existing tests do not explicitly substitute a semantic fingerprint as the binding digest or vice versa; acceptance would still require the recomputed digest comparison.

## 9. Authoritative Redis immutability and raw-state order

### 9.1 Sustained guarantees

The Phase 2 CAS validates exact stored and candidate bytes through the shared UTF-8, duplicate-member, JSON syntax, and depth-128 Lua scanner before lease, version, status, ledger, marker, history, or retention interpretation. Preflight performs the same stored-state validation before lock ownership and lock TTL. This preserves the raw-state-before-lock ordering closed in `docs/12-raw-state-gate-closure-review.md`.

At creation, Lua atomically requires a binding table and checks execution, step, intent, correlation, connector, request fingerprint, and the absolute retention floor. Python additionally checks target, creation deadline, and binding/model consistency before invoking the script.

Later transitions include `request_binding` in the immutable field set, reject addition/removal, and use recursive equality over the complete decoded binding. Other ledger records must remain equal. This one transition path is reused by ordinary transitions, runner resolution, recovery claim, and recovery resolution. There is no separate retention mutation path.

Preflight checks lease ownership, lease TTL, prepared version, `ABOUT_TO_FIRE` status, binding presence, digest equality, and recursive equality with the caller's complete binding. Existing tests show exact Redis string equality and elapsed-time-only TTL for sampled binding removal/replacement cases, including locator, fingerprint, digest, descriptor version, commitment key ID, execution/intent/correlation identity, and retention. Legacy binding addition is rejected. A valid-looking safe-descriptor replacement after the first durability acknowledgement is preserved exactly and produces zero provider calls and zero additional acknowledgements.

Legacy unbound records remain model-readable because `request_binding` is optional. Transition Lua rejects adding a binding. Preflight rejects absent bindings. Recovery receives only safe `ReconciliationContext` and never replays the mutation.

### 9.2 Partial verification of complete equality

`deep_equal` operates on Lua values after `cjson.decode`. It compares types, scalar values, keys, and recursive members, but it does not compare canonical binding bytes. Lua tables represent both JSON arrays and objects; empty-container type preservation is not explicitly checked by the function. JSON numeric lexical forms also collapse to Lua numbers. The shared raw gate proves valid unambiguous JSON, not canonical request-binding serialization.

No existing test replaces an empty binding array with an empty object, changes a numeric lexical form while preserving the decoded value, or otherwise proves that every noncanonical serialized binding change is rejected. Therefore the claim “complete canonical binding equality” is **NOT VERIFIED**. This is a static boundary concern, not an executed bypass claim in this review.

Creation does not perform a full schema/digest recomputation in Lua. It relies on the typed Python candidate for fields beyond the atomic identity/retention subset. Python equality is not the sole protection for later immutability, but the creation-time completeness claim is partly split between Python and Lua.

## 10. Verified-dispatch boundary

The normal test-only runner sequence is verified as:

1. production/test composition validation;
2. lease acquisition and current-state read;
3. strict request validation and exact immutable envelope construction;
4. safe descriptor and keyed protected commitments;
5. semantic fingerprint;
6. create-once AES-GCM vault write and authenticated exact readback;
7. attempt digest and complete persisted binding;
8. atomic intent creation;
9. same-connection durability acknowledgement;
10. raw-state/lease/TTL/version/status/digest/full-binding preflight;
11. second authenticated vault retrieval;
12. profile, metadata, descriptor, commitments, fingerprint, and digest recomputation using persisted key IDs/versions;
13. frozen `VerifiedDispatch` construction;
14. one `mutate(dispatch=..., client_timeout=...)` connector call;
15. existing resolution CAS followed by its durability acknowledgement.

The connector signature cannot receive replacement target, headers, body, request dictionary, options, credential object, or arbitrary provider metadata. No production alternate call was found. Existing tests prove one call/two acknowledgements for success, one call/two acknowledgements and `FIRED_UNCONFIRMED` for connector exception, and no automatic provider retry.

`VerifiedDispatch` is a frozen dataclass with `init=False` and a custom constructor requiring `_VERIFIED_DISPATCH_TOKEN`. That token is a module-level object. Python underscore names are conventional rather than access-controlled, and the mock connector checks `type(dispatch) is VerifiedDispatch` only. There is no service-issued signature, sealed capability, or connector-side check that the object passed through successful verification. Consequently, non-forgeable verified-dispatch provenance is **NOT VERIFIED** by static design or existing tests. No construction attempt was made under the bounded review scope.

The existing mutation test changes original top-level caller containers. Nested values are canonicalized during `ExactMutationRequest` construction, which statically prevents later nested-container changes from affecting exact bytes, but no existing test mutates every nested container shape.

## 11. P2-010 safe-value and privacy boundary

### 11.1 Verified normal-path protections

`SafeValueRule` is frozen and recursively code-owned. It supports exact null/boolean/integer/string/array/object/one-of variants. Strings require explicit enumeration, integers enforce optional bounds, arrays enforce item schema and a maximum count, objects require an exact field set, and unions require exactly one matching variant. Endpoint profiles make their public/options/protected maps immutable through mapping proxies.

The field-name scanner rejects sensitive-name tokens as supplementary protection. It is not the principal control: explicit allowlists validate values and exact shapes. Targets reject URL authority/user information/query/fragment forms. Protected values occupy explicit root protected-field entries and cannot be supplied under undeclared or case-varied names.

Intent actor, reason, observation, evidence class, external reference, and risk-acceptance values use bounded safe identifiers. Evidence hashing accepts only a small exact key set and safe identifiers. Unknown mutation responses become `AMBIGUOUS`; provider call IDs and external references are not persisted. Recovery maps unknown result values to `UNKNOWN` and drops provider identifiers.

Request/vault/binding errors use fixed reason codes. Workflow wrappers include only safe reason codes or exception class names and suppress causes. Connector exceptions are reduced to fixed ambiguous evidence. Quarantine persists only reason, presence, byte length, and encoding class; it does not preserve raw state through Base64, hex, compression, or escaping. Logger calls contain validated execution/reason values and exception class names, not request/vault/dispatch/provider objects.

Custom representations redact exact request, vault material, keyrings, prepared mutation, and verified dispatch. Existing privacy tests cover the repository's synthetic authorization, cookie, token, credential, payment, personal-identifier, provider-result, invalid-state, log, exception, quarantine, descriptor, fingerprint, Redis, and backing-storage paths. Those unchanged tests passed.

### 11.2 Persisted-model and broad-repository limits

`SafeField.canonical_value` is only a length-bounded string in the Pydantic model. During normal descriptor construction it is produced from a value that has passed the endpoint rule, but on persisted model load it is not decoded, checked for canonical JSON, or revalidated against the profile. A directly supplied/tampered but structurally valid string can therefore pass the model boundary. Dispatch verification reconstructs the descriptor from authenticated vault bytes and rejects inequality, but model inspection and default Pydantic representation occur earlier in other callers. The claimed authoritative typed allowlist for every persisted safe value is therefore only partially implemented.

Pydantic validation errors can include rejected input values when models are constructed directly. Normal workflow/storage entry points wrap or replace the relevant failures with safe messages and suppressed causes, but a general guarantee for all direct model-construction errors is not established.

The Phase 1 `AEPExecutionState` intentionally retains `context_data: Dict[str, Any]` and a broad base `intent_ledger: Dict[str, Any]`. Phase 2 reparses the ledger through strict models before use, and the request-binding path does not write request material to `context_data`. Nonetheless, the repository as a whole does contain unrestricted persisted mappings outside the bounded request-binding descriptor. They must not be represented as a universal privacy-safe storage model.

No fresh independent privacy values were generated because the revised audit scope permits only existing fixtures and forbids standalone probes. The existing seeded privacy tests passed, but fresh privacy-canary verification, pytest-output/cache scanning for fresh values, and generated-report scanning against fresh values are **NOT VERIFIED**. Absence of the repository's known fixtures from selected prohibited surfaces is not proof that arbitrary protected values can never leak.

Python objects, temporary canonical buffers, AES-GCM inputs/outputs, and connector arguments cannot be reliably erased from managed memory. No memory-erasure guarantee is made.

## 12. Controlled altered-state and counter matrix

The following table distinguishes direct existing evidence from missing coverage. “Historical acknowledgement” means the durable `ABOUT_TO_FIRE` creation acknowledgement already occurred; it is not counted as zero.

| # | Required case | Existing evidence and counters | Audit status |
|---:|---|---|---|
| 1 | Unsafe request before intent creation | `test_unsafe_request_rejection...`: provider 0, acknowledgements 0, empty ledger | **VERIFIED** |
| 2 | Production composition rejected before intent creation | `test_test_vault_cannot_authorize_production_configuration`: provider 0, acknowledgements 0 | **VERIFIED** |
| 3 | Missing vault object after durable creation | provider 0; 1 historical creation acknowledgement; 0 additional; `ABOUT_TO_FIRE` remains | **VERIFIED** |
| 4 | Expired vault object after durable creation | provider 0; 1 historical creation acknowledgement; 0 additional | **VERIFIED** with synthetic second-read fixture |
| 5 | Altered ciphertext | provider 0; 1 historical creation acknowledgement; 0 additional | **VERIFIED** |
| 6 | Altered authenticated metadata | Direct vault read rejects one altered identity; no runner counter assertion | **PARTIALLY VERIFIED** |
| 7 | Wrong or missing encryption-key version | Missing key is a typed direct-vault rejection; wrong-key and post-durable counters absent | **PARTIALLY VERIFIED** |
| 8 | Wrong or missing commitment-key version | Missing/short key before preparation is covered; post-durable historical-key loss is absent | **PARTIALLY VERIFIED** |
| 9 | Fingerprint mismatch | Transition Lua sample preserves exact raw state/TTL; no runner counter case | **PARTIALLY VERIFIED** |
| 10 | Binding-digest mismatch | Transition and direct preflight samples reject; no altered-authoritative-runner counter case | **PARTIALLY VERIFIED** |
| 11 | Locator replacement | Transition Lua sample preserves exact raw state/TTL; no runner counter case | **PARTIALLY VERIFIED** |
| 12 | Execution, step, intent, or correlation mismatch | Execution/intent/correlation samples exist; `step_id` is not independently altered | **PARTIALLY VERIFIED** |
| 13 | Endpoint-profile or operation-version mismatch | Endpoint-profile service change yields provider 0 and 1 historical acknowledgement; operation-version post-creation case absent | **PARTIALLY VERIFIED** |
| 14 | Vault-object or descriptor-version mismatch | Descriptor transition sample exists; vault-object-version alteration absent | **PARTIALLY VERIFIED** |
| 15 | Creation, expiry, or retention deadline mismatch | Digest unit coverage and one retention transition sample; no complete post-durable matrix | **PARTIALLY VERIFIED** |
| 16 | Valid-looking safe-descriptor replacement in Redis | Exact injected string preserved; provider 0; 1 historical acknowledgement; 0 additional | **VERIFIED** |
| 17 | Complete binding transplant from another intent | Cross-execution creation transplant is rejected; persisted intent-to-intent transplant absent | **PARTIALLY VERIFIED** |
| 18 | Binding removal | Transition Lua rejects with exact raw state/TTL; legacy dispatch presentation not directly tested | **PARTIALLY VERIFIED** |
| 19 | Binding addition to a legacy intent | Exact raw state and elapsed-time TTL preserved | **VERIFIED** |
| 20 | Shortened vault or binding retention | Binding retention shortening rejected with exact raw state/TTL; vault retention alteration absent | **PARTIALLY VERIFIED** |
| 21 | Mutation of original caller containers | Transmitted bytes retain original authenticated material | **VERIFIED** for existing top-level fixture |
| 22 | Legacy unbound intent presented for dispatch | Static preflight returns absent-binding rejection; no dedicated unchanged test presents it to the runner | **NOT VERIFIED** behaviorally |
| 23 | Connector exception after one transport attempt | provider 1; acknowledgements 2; `FIRED_UNCONFIRMED`; no retry | **VERIFIED** |
| 24 | Valid verified dispatch and confirmed resolution | provider 1; acknowledgements 2; `FIRED_CONFIRMED` | **VERIFIED** |

For the direct transition cases, `tests/test_request_binding_intents.py` captures raw Redis strings before and after rejection and asserts exact equality. That byte equality transitively preserves version, execution status, complete ledger, and transition history. It also asserts TTL is no greater than the original and no lower than elapsed time plus a one-second tolerance. Those tests do not instantiate provider/durability counters, so the report does not claim zero total calls/acknowledgements for those direct unit paths.

The existing matrix is materially narrower than the requested all-field matrix. No new matrix was created after the scope was narrowed. Uncovered cases remain coverage limitations and contribute to `PARTIALLY VERIFIED`.

## 13. Regression and compatibility assessment

| Requirement | Result |
|---|---|
| P2-001 normal retry eligibility/fencing | **Sustained** for repository scope; combined P0 and full suites pass |
| P2-002 execution-wide ambiguity fence | **Sustained**; blocking status/race/raw-state suites pass |
| P2-003 Phase 1 replacement protection | **Sustained**; Phase 1/P0 suites pass |
| Strict Lua UTF-8 | **Sustained**; shared validator and 152-case codec/Lua suite pass |
| Duplicate members | **Sustained** in Python/Lua/read/preflight/recovery paths |
| Malformed JSON, NaN, infinity | **Sustained** |
| Raw-state-before-lock order | **Sustained** in all three state-interpreting Lua bodies |
| Valid Phase 1 operations | **Sustained**; Phase 1 suite passes |
| Valid bound Phase 2 operations | **Sustained**; focused/full suites pass |
| Legacy Phase 2 records readable | **Sustained** by existing fixtures |
| Legacy unbound mutation dispatch | Statically rejected by preflight; dedicated runner case absent |
| Same-connection CAS/WAITAOF | **Sustained** after successful rerun; full integration also passed |
| Provider after creation durability | **Sustained** by ordering and dispatch suites |
| Recovery never replays mutation | **Sustained**; recovery uses readback only |
| No production mutation enabled | **Sustained**; startup defaults reject dispatch |
| No test removed/skipped/weakened | Full suite collected/passed 497 with 0 skips, but historical comparison is **NOT VERIFIED** without usable Git metadata |

The shared Lua scanner retains its depth limit of 128. Application reads may accept a deeper valid document that authoritative Lua later rejects. Redis evidence is single-node only. WAITAOF confirms local AOF fsync for preceding writes on the pinned connection; it does not provide multi-node coordination or Redis/provider atomicity. Quarantine remains best-effort. Python memory erasure cannot be guaranteed.

## 14. Verification commands and observed results

All pytest runs used `redis://127.0.0.1:6381/15`, disabled Python bytecode writes, and disabled pytest's cache provider. Repository fixtures scan and delete only `aep:*` keys. No command invoked `FLUSHALL`.

### 14.1 Compilation

```powershell
$ErrorActionPreference='Stop'; $compileDir='C:\tmp\aep-p2-closure-audit-pyc'; $resolved=[IO.Path]::GetFullPath($compileDir); $allowed=[IO.Path]::GetFullPath('C:\tmp\'); if(-not $resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'unsafe compile path'}; if(Test-Path -LiteralPath $resolved){throw 'compile path already exists'}; New-Item -ItemType Directory -Path $resolved | Out-Null; try { $env:PYTHONPYCACHEPREFIX=$resolved; $pyFiles=@(Get-ChildItem -LiteralPath 'src','tests' -Recurse -Filter '*.py' | Select-Object -ExpandProperty FullName); py -3 -m py_compile @pyFiles; $compileExit=$LASTEXITCODE; $artifactCount=(Get-ChildItem -LiteralPath $resolved -Recurse -File | Measure-Object).Count; Write-Output "py_files=$($pyFiles.Count)"; Write-Output "py_compile_exit_code=$compileExit"; Write-Output "compiled_artifacts=$artifactCount" } finally { Remove-Item -LiteralPath $resolved -Recurse -Force; Write-Output "temp_removed=$(-not (Test-Path -LiteralPath $resolved))" }; exit $compileExit
```

The first sandboxed attempt exited 1 before directory creation with access denied. The identical approved temporary-directory run exited 0: `py_files=38`, `py_compile_exit_code=0`, `compiled_artifacts=75`, `temp_removed=True`.

### 14.2 Existing repository suites

| Purpose | Exact pytest selection | Exit | Unedited summary |
|---|---|---:|---|
| Phase 1 storage/CAS | `py -3 -m pytest tests/test_cas_write.py tests/test_get_migration.py tests/test_races.py tests/test_uuid_validation.py tests/test_version_range.py -p no:cacheprovider -q` | 0 | `32 passed in 2.00s` |
| Focused Phase 2 | `py -3 -m pytest tests/test_mock_connector.py tests/test_phase2_durability.py tests/test_phase2_state_machine.py tests/test_phase2_runner.py tests/test_phase2_recovery.py -p no:cacheprovider -q` | 0 | `163 passed in 12.23s` |
| Combined P0 | `py -3 -m pytest tests/test_phase2_mutation_safety.py tests/test_phase2_duplicate_member_safety.py -p no:cacheprovider -q` | 0 | `45 passed in 8.48s` |
| State codec and Lua | `py -3 -m pytest tests/test_state_codec.py tests/test_phase2_duplicate_member_safety.py -p no:cacheprovider -q` | 0 | `152 passed in 6.03s` |
| Raw-state gate | `py -3 -m pytest tests/test_raw_state_validation_gate.py -p no:cacheprovider -q` | 0 | `26 passed in 3.63s` |
| Canonicalization/commitment/digest | `py -3 -m pytest tests/test_request_canonicalization.py -p no:cacheprovider -q` | 0 | `30 passed in 16.13s` |
| Vault/dispatch | `py -3 -m pytest tests/test_request_vault.py tests/test_verified_dispatch.py -p no:cacheprovider -q` | 0 | `20 passed in 3.31s` |
| Binding immutability/races | `py -3 -m pytest tests/test_request_binding_intents.py tests/test_races.py tests/test_phase2_mutation_safety.py -p no:cacheprovider -q` | 0 | `55 passed in 9.70s` |
| Complete integration-enabled suite | `py -3 -m pytest tests -p no:cacheprovider -q` with integration variables | 0 | `497 passed in 63.76s (0:01:03)` |
| Explicit accepted/rejected dispatch | `py -3 -m pytest tests/test_verified_dispatch.py -p no:cacheprovider -q` | 0 | `13 passed in 1.66s` |

The complete integration command was:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests -p no:cacheprovider -q
```

It had 497 passes, 0 failures, and 0 skips.

### 14.3 WAITAOF infrastructure failure and rerun

The standalone command was:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests/test_phase2_waitaof_integration.py -p no:cacheprovider -q
```

The first run exited 1: `1 failed, 3 passed in 16.23s`. The failing ordering test received no local-fsync acknowledgement from its first barrier and failed closed before provider transport. Immediate read-only Redis inspection reported Redis 7.2.5, `aof_enabled=1`, no rewrite in progress, last AOF write/rewrite status `ok`, `appendonly=yes`, and `appendfsync=everysec`. The identical rerun exited 0: `4 passed in 11.21s`. The complete 497-test integration run immediately before the standalone run had also passed all four tests.

This is recorded as a transient infrastructure/acknowledgement failure, not erased by the rerun. It demonstrates fail-closed behavior when WAITAOF does not acknowledge; it does not establish that every deployment will acknowledge within the configured timeout.

### 14.4 Redis and integrity results

The dedicated container inspection reported:

```text
aep-phase2-redis72 | redis:7.2.5-alpine | healthy | 127.0.0.1:6381->6379/tcp
selected_db=15
redis_version=7.2.5
aof_enabled=1
appendonly=yes
appendfsync=everysec
```

The final database check found zero `aep:*` keys and `DBSIZE 0`. Repository search found `FLUSHALL` only in explanatory test comments/configuration strings, not an executable call.

The 38-file Python source/test manifest was unchanged before and after execution:

```text
3e618bf71b750fd5d863a741a97856bb615ca3bc86b72ca5acea9e8e4f7b3a99
```

The broader 83-file `src`/`tests` filesystem manifest, including pre-existing cache artifacts, was also unchanged:

```text
7a73c957546868cf4a888a14419213c8bf781dd7278da8cf8f45310fb15851a9
```

Protected-file SHA-256 values were identical before and after:

| Protected file | SHA-256 |
|---|---|
| `docs/07-phase2-gap-audit.md` | `2f0333691dc00ea9ed632ce33009348113ebb7f37f32cfee5b1a8e3114dc48e8` |
| `docs/09-post-waitaof-gate-review.md` | `65dbbc52647d9364bfcda6a0aa1d53287c1dcf5e3a9f1135164e95d6090694dd` |
| `docs/10-p0-closure-review.md` | `963a9c43476340bc9584b33306876c502b6a4c82715a9beb048d7dd2fff6935b` |
| `docs/11-json-closure-gate-review.md` | `9f2ffa41c7825fbe7fa742dabe64e2f8d38434120e3589594bd7197435a25d35` |
| `docs/12-raw-state-gate-closure-review.md` | `82a2172d454524f8ed544b8e28c571f42158f8771de5182281b6332a8dd51622` |
| `phase2_implementation_report.md` | `8afa31741e6f73b173f927ffd9fbf1d6b8fe953a601385eabdc5721127201db1` |

No production source, existing test, configuration, or implementation report was modified. This review is the only repository file created.

## 15. Repository-enforcement verdict

**PARTIALLY VERIFIED.** The ordinary test-only runner path, immutable-field samples, raw-state gate, durability order, safe response reduction, and no-retry behavior are directly verified. Full canonical Lua equality, verified-dispatch provenance, persisted safe-value revalidation, exhaustive altered-state coverage, and production endpoint behavior are not.

## 16. P2-004 classification

**PARTIALLY CLOSED.** The repository has a meaningful immutable request-binding design and passing test-only enforcement, but the closure is incomplete because canonical decoded-Lua equality and dispatch provenance are not fully established, AAD coverage is incomplete, exact production mutation sufficiency is unverified, and no durable production vault/KMS or production connector exists.

## 17. P2-010 classification

**PARTIALLY CLOSED.** Normal request construction uses strong recursive allowlists and safe fixed evidence/error/quarantine paths, but persisted safe canonical values are not revalidated against endpoint rules on model load, direct model-validation representations are not universally safe, broad Phase 1 mappings remain outside the boundary, fresh independent privacy verification was not permitted, and no production connector-specific safe schemas exist.

## 18. Verified and unverified guarantees

| Guarantee | Status | Boundary |
|---|---|---|
| Strict versioned canonical test request envelope | **VERIFIED** | Repository construction path |
| Exact bytes encrypted once and authenticated on read | **VERIFIED** | Test-only in-memory vault |
| Raw protected values absent from Redis binding | **VERIFIED** | Inspected schema and existing privacy tests |
| HMAC-SHA-256 protected commitments with explicit key IDs | **VERIFIED** | Repository construction/verification path |
| Separate semantic fingerprint and attempt digest | **VERIFIED** | Code and existing tests |
| All requested attempt-digest fields covered in code | **VERIFIED** | Static inspection; `step_id` lacks a change test |
| Authoritative immutability for sampled binding changes | **VERIFIED** | Existing Redis Lua tests |
| Canonical byte equality for every binding serialization | **NOT VERIFIED** | Lua compares decoded tables |
| Non-forgeable `VerifiedDispatch` provenance | **NOT VERIFIED** | Module-level token and connector type check |
| Full safe-value validation on persisted-model load | **NOT VERIFIED** | Canonical values are bounded strings on load |
| Provider call occurs after durability acknowledgement | **VERIFIED** | Test-only runner and Redis 7.2 integration |
| Automatic retry absent after ambiguous mutation exception | **VERIFIED** | One-call runner tests |
| Recovery never replays a mutation | **VERIFIED** | Readback-only recovery path |
| Production-capable encrypted durable vault/KMS | **UNVERIFIED / ABSENT** | No implementation |
| Production credential lifecycle and key rotation | **UNVERIFIED / ABSENT** | No implementation |
| Complete provider-side request derivation | **UNVERIFIED / ABSENT** | No production connector profile |
| Production connector response/reference privacy schema | **UNVERIFIED / ABSENT** | No production connector profile |
| Exactly-once external effects | **NOT CLAIMED** | Redis/provider remain separate systems |
| Guaranteed protected-value non-disclosure | **NOT CLAIMED** | Bounded tests are not universal proof |
| Guaranteed Python memory erasure | **NOT CLAIMED** | Managed runtime limitation |

## 19. Residual security, compatibility, and coverage limitations

- The only vault is non-durable and test-only; it is not production-grade security.
- Vault AAD does not cover every requested identity/profile/deadline field.
- Commitment equality reveals scoped equality correlation and is not encryption.
- Lua's 128-level raw JSON limit differs from the Python application read boundary.
- Decoded-Lua deep equality is not proven equivalent to complete canonical byte equality.
- The Python `VerifiedDispatch` construction guard is conventional module privacy, not a sealed capability.
- Persisted safe-field strings are not endpoint-rule revalidated during model loading.
- Existing altered-state tests sample rather than exhaust every binding/vault field.
- Fresh independent privacy values and generated-output scanning were not performed under the revised scope.
- There is no usable Git history for independent proof that earlier tests were not removed or weakened.
- Redis verification covers one local Redis 7.2.5 AOF node and DB 15 only.
- WAITAOF is a local AOF acknowledgement; CAS and WAITAOF are sequential commands on a pinned connection.
- No multi-node coordination, split-brain prevention, or Redis/provider transaction exists.
- Quarantine is best-effort and can fail while the original corruption result remains fail-closed.
- Python and cryptographic library objects cannot guarantee memory zeroization.

Within the verified repository paths and evidence scope, the bounded conclusion remains:

> “Ambiguity, corruption, and contention are detectable; the system fails closed.”

## 20. Implementation GO/NO-GO recommendations

| Next stage | Recommendation | Conditions |
|---|---|---|
| Durable production vault/KMS boundary | **GO to implement; NO-GO to activate** | Define full authenticated metadata, durable create-once semantics, KMS/key separation and lifecycle, access control, retention, recovery, rotation, audit, and exhaustive altered-state tests; close the canonical-equality and provenance gaps before relying on it for production dispatch |
| First production connector profile | **GO to implement in isolation; NO-GO to activate** | Specify every effect-changing transport field, deterministic method/path/query/codec/content-type derivation, credential semantics, response/reference safe schemas, and connector-side verified-dispatch provenance; independently review it with the durable vault boundary |

These recommendations authorize implementation and review work only. They do not authorize a production connector call, production credential use, or deployment.

## 21. Production non-idempotent dispatch decision

**NO-GO.** Production non-idempotent dispatch must remain disabled. A passing test-only vault/mock-connector suite cannot close the missing durable vault/KMS, production key lifecycle, endpoint-specific safe schema, complete transport binding, or connector integration. This review does not establish exactly-once effects, absolute Redis/provider atomicity, split-brain prevention, guaranteed duplicate prevention, guaranteed protected-value non-disclosure, or guaranteed in-memory erasure.
