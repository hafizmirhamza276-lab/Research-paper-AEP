# Production vault/KMS design acceptance review

**Review date:** 2026-07-31  
**Review mode:** independent, repository-local, read-only except for this document  
**Reviewed design:** `docs/15-production-vault-kms-design.md`  
**Decision:** revision is required before provider-neutral interface implementation

## 1. Review purpose and evidence boundary

This review determines whether `docs/15-production-vault-kms-design.md` is a complete, provider-neutral, fail-closed design for the future durable request-vault/KMS boundary that supports the Agent Execution Protocol (AEP). It does not implement that boundary and does not select or evaluate a cloud provider.

The review used only repository files, read-only filesystem and Git commands, manifest hashing, architecture searches, the already-running local Redis 7.2 test service, and the unchanged existing test suite. It did not install an SDK, access a cloud account or external system, use credentials or protected data, create a provider/KMS/HSM/storage resource, create a connector, enable production composition, or send a production mutation.

The exact design and historical files inspected were:

- `docs/06-phase2-design.md`
- `docs/07-phase2-gap-audit.md`
- `docs/08-production-connector-design.md`
- `docs/09-post-waitaof-gate-review.md`
- `docs/10-p0-closure-review.md`
- `docs/11-json-closure-gate-review.md`
- `docs/12-raw-state-gate-closure-review.md`
- `docs/13-request-binding-closure-review.md`
- `docs/14-request-binding-final-closure-review.md`
- `docs/15-production-vault-kms-design.md`
- the `2026-07-31 addendum: canonical request-binding repository closure`, historical precedence material, and end-of-file `2026-07-31 final delivered-tree closure evidence and precedence` in `phase2_implementation_report.md`

The exact implementation/configuration files inspected or repository-wide inventory-searched were:

- `src/core/request_vault.py`, `request_binding.py`, `intents.py`, `intent_workflow.py`, `intent_recovery.py`, `durability.py`, `state_codec.py`, `storage.py`, `locks.py`, `exceptions.py`, and `validation.py`
- `pyproject.toml`, `compose.phase2.yml`, and `redis/phase2.conf`
- `tests/conftest.py`, `tests/mock_connector.py`, `tests/request_binding_helpers.py`, `tests/MATRIX.md`, and every `tests/test_*.py` file returned by `rg --files tests`

The test files examined most closely were the canonicalization, canonical-binding, request-vault, vault-AAD, request-binding-intent, raw-state-gate, endpoint-profile, verified-dispatch, provenance, privacy, durability, runner, recovery, mutation-safety, state-codec, and Redis `WAITAOF` modules. The complete suite execution additionally exercised all delivered test files.

Unavailable evidence:

- The `.git` directory is empty and Git does not recognize the workspace as a repository. Historical additions, deletions, test weakening, and the claim that only `docs/15` was added in the preceding stage cannot be proved from Git history.
- No provider documentation, account, SDK, object-store behavior, KMS/HSM behavior, IAM policy, audit sink, retention system, backup system, regional-failure evidence, or production build artifact exists in the evidence boundary.
- There is no production vault/KMS implementation or provider-neutral Stage 2 implementation to test. Design-only criteria were assessed for precision and future testability, not treated as passing.

## 2. Baseline and research-topic alignment

The current delivered-tree baseline is independently reconfirmed:

| Item | Classification | Basis |
|---|---|---|
| Repository enforcement | **VERIFIED** | Current source trace, unchanged manifest, and `611 passed` |
| P2-004 | **CLOSED within repository scope** | Exact canonical Redis binding, authenticated test-vault reconstruction, and one-use connector-consumed provenance |
| P2-010 | **CLOSED within repository-defined Phase 2 mutation scope** | Current typed safe-value, evidence, exception, quarantine, representation, and connector-test boundaries |
| Durable production vault/KMS implemented | **NO** | Only `TestOnlyInMemoryRequestVault` exists |
| Provider-specific durability verified | **NO** | No provider was selected or accessed |
| Production applicability | **NO-GO** | No production vault/KMS, connector/profile, operations, or activation evidence |
| First production connector implementation | **NO-GO** | Its prerequisite production vault/KMS gate has not passed |
| Production non-idempotent dispatch | **NO-GO** | Current startup permits only an explicit test-only composition |

The evidence precedence stated in `docs/15` is correct. The open or partial historical classifications in `docs/07`, `docs/09`, `docs/10`, `docs/11`, and `docs/13` are superseded for the current tree by `docs/12`, the final delivered-tree report note, and `docs/14`. The older `2026-07-30 final report precedence note` remains textually contradictory, but the later end-of-file `2026-07-31` note expressly supersedes it. This is an unresolved documentation-ordering hazard, not a current source contradiction.

The research topic remains “A Fail-Closed Agent Execution Protocol for Reliable and Privacy-Preserving Non-Idempotent API Mutations.” The primary contribution is the AEP sequence:

`Agent request -> durable intent -> exact request binding -> encrypted material -> verified one-use dispatch -> provider call -> safe recovery`

`docs/15` is a future production-grade encrypted-material support boundary. Redis, same-connection `WAITAOF`, canonical binding, the vault/KMS, and verified dispatch are protocol components; they do not turn the research into a cloud-storage or KMS paper. Provider-specific cloud evaluation remains future work. No exactly-once external-effect claim is made or supported.

## 3. Scope compliance and changed-file verification

This review complied with the requested scope. Before this document was created, no source, test, configuration, report, or earlier document was edited. Existing tests were run unchanged with bytecode and pytest cache writes disabled. The local test database contained zero keys after the suite.

Historical “only `docs/15` changed” verification is **PARTIALLY VERIFIED, not proved**:

- the source/test manifests exactly equal the hashes recorded by `docs/14`;
- the prior protected hashes for `docs/07` through `docs/13` and `phase2_implementation_report.md` exactly match `docs/14`;
- current-tree hashes exist for `docs/06`, `docs/14`, and `docs/15`, but `docs/14` did not provide earlier comparison values for those files; and
- unusable Git metadata prevents a complete historical diff or addition/deletion proof.

The manifest algorithm sorts repository-relative POSIX paths, emits `path<TAB>sha256` rows joined with LF, UTF-8 encodes that text, and SHA-256 hashes it. Results before document creation and after the unchanged test run were:

```text
broad src/tests files=88
broad src/tests manifest SHA-256=cda91d328f2469acde42b755153a8872c20475a610802fec36910325a12556de
Python src/tests files=43
Python src/tests manifest SHA-256=c921de204b067ea79ce9703aada13caac298ce35c00efc4301739d8a2dc15ff9
review-protected files excluding .git, .pytest_cache, __pycache__, and docs/16=92
review-protected manifest SHA-256=3251cc7bebc296bf5dc821bac20d83d82515fce63d6e2ba56ca4307cdb97839b
```

Protected/current document hashes are:

| File | SHA-256 | Prior comparison |
|---|---|---|
| `docs/06-phase2-design.md` | `f926e02494ac9490dc93617214bd679082e35ba1d1969aa4b4183d64be4bd339` | Current value only |
| `docs/07-phase2-gap-audit.md` | `2f0333691dc00ea9ed632ce33009348113ebb7f37f32cfee5b1a8e3114dc48e8` | Matches `docs/14` |
| `docs/08-production-connector-design.md` | `c08d3fc545138f05275a100affcdd5631085c2751b4700047ca1aaa6b1e848bf` | Matches `docs/14` |
| `docs/09-post-waitaof-gate-review.md` | `65dbbc52647d9364bfcda6a0aa1d53287c1dcf5e3a9f1135164e95d6090694dd` | Matches `docs/14` |
| `docs/10-p0-closure-review.md` | `963a9c43476340bc9584b33306876c502b6a4c82715a9beb048d7dd2fff6935b` | Matches `docs/14` |
| `docs/11-json-closure-gate-review.md` | `9f2ffa41c7825fbe7fa742dabe64e2f8d38434120e3589594bd7197435a25d35` | Matches `docs/14` |
| `docs/12-raw-state-gate-closure-review.md` | `82a2172d454524f8ed544b8e28c571f42158f8771de5182281b6332a8dd51622` | Matches `docs/14` |
| `docs/13-request-binding-closure-review.md` | `2b4c0cf14d87ae60d071b934bc5eecfbad3b01df77eeff43b5b9baffcd14e6cf` | Matches `docs/14` |
| `docs/14-request-binding-final-closure-review.md` | `d520e275512435212d41d6729d4acd132d332a174216a58b9731cf6fb99e55f2` | Current value only |
| `docs/15-production-vault-kms-design.md` | `a21712504c16d9f10d7c7b7f08518ccd6a15298fdb00b6a6791cc20891be9bff` | Current reviewed value |
| `phase2_implementation_report.md` | `a686159febda37cb4d1a1a54304ee67639255ad13d4ec4dab044474aa33a974c` | Matches `docs/14` |

Configuration hashes were `pyproject.toml=8e7c11479e76749c68d65257772dc693e13850eb34a48223a6cedfd1a7cb2fc2`, `redis/phase2.conf=b7e15a7a169732c03c13ac76da0738ae5c3848d1e4b881ca9e75d9a28928ae36`, and `compose.phase2.yml=35d0ca05ee0a79ac03ec103c0d2e36e4f79912486b673a7b51fd3ffa7a951630`.

### Command and result record

The following records every command family used. Repeated line-range reads are grouped with their exact ranges; they did not mutate files.

| Command or exact command family | Exit | Observed result |
|---|---:|---|
| Initial tool-orchestrated parallel inspection batch | 1 | Wrapper returned no child output; every intended command was rerun individually |
| `rg --files -g AGENTS.md -g '!docs/16-production-vault-kms-design-review.md'` | 1 | No `AGENTS.md` found |
| `Get-ChildItem -Force \| Select-Object Mode,Length,LastWriteTime,Name` | 0 | Repository root inventory obtained |
| `git status --short --untracked-files=all` | 1 | `fatal: not a git repository` |
| `git rev-parse --show-toplevel; git rev-parse HEAD; git log -5 --oneline --decorate` | 1 | Each Git operation reported `not a git repository` |
| `rg --files` | 0 | Delivered file inventory obtained |
| First PowerShell document hash/line-count pipeline | 1 | PowerShell parser rejected an empty pipe element; no write occurred |
| Corrected document hash/line-count loop and final `Get-FileHash -Algorithm SHA256` loops | 0 | Exact sizes, line counts, and hashes obtained |
| `rg -n '^#{1,6} ' docs/15-production-vault-kms-design.md` | 0 | All design sections inventoried |
| Numbered `Get-Content` reads of `docs/15` ranges `1-180`, `181-360`, `361-540`, `541-720`, `721-900`, `901-1008` | 0 | Entire reviewed design read |
| `rg` heading/hash/classification/addendum searches over `docs/06`-`docs/14` and `phase2_implementation_report.md` | 0 | Historical conflicts and precedence located |
| Numbered `Get-Content` reads of `docs/14` ranges `1-120`, `420-610`, `611-701`; `phase2_implementation_report.md` ranges `918-1312`, `2430-2507`; and cited decision/design ranges in `docs/06`-`docs/13` | 0 | Latest closure and relevant historical design/gates inspected |
| Numbered `Get-Content` reads of all of `src/core/request_vault.py`, all of `src/core/intent_recovery.py`, and relevant canonicalization/binding/provenance/runner/intent ranges | 0 | Implementation ordering and boundaries traced |
| `Get-Content` of `pyproject.toml`, `redis/phase2.conf`, and `compose.phase2.yml` | 0 | Dependency, package, Redis, and composition baseline inspected |
| Repository-wide `rg -n` inventories for production/KMS/cloud SDKs, connector/mutation paths, canonical binding/Lua/raw-state/WAITAOF, privacy/evidence/quarantine, and configuration/backend selection | 0 | No production vault/KMS, cloud SDK/client, production connector, or production dispatch composition found |
| Exact Python source/test manifest command recorded in `docs/14` | 0 | `88/cda91d...` broad and `43/c921de...` Python manifests, unchanged |
| Review-protected manifest command excluding only review output and volatile metadata | 0 | `92/3251cc...`, unchanged before review output |
| `Get-ChildItem -LiteralPath '.git' -Force \| Select-Object Mode,Length,Name` | 0 | No entries; Git metadata empty |
| `docker ps --format "table {{.Names}}..."` | 0 | `aep-phase2-redis72`, `redis:7.2.5-alpine`, healthy on loopback port 6381 |
| `py -3 --version; py -3 -m pytest --version` | 0 | Python 3.13.1; pytest 8.3.3 |
| `$env:REDIS_URL='redis://127.0.0.1:6381/15'; $env:AEP_PHASE2_REDIS_INTEGRATION='1'; $env:AEP_PHASE2_REDIS_CONTAINER='aep-phase2-redis72'; $env:PYTHONDONTWRITEBYTECODE='1'; py -3 -m pytest tests -p no:cacheprovider -q` | 0 | `611 passed in 38.79s`; zero failures and zero skips |
| `docker exec aep-phase2-redis72 redis-cli -n 15 DBSIZE` | 0 | `0` |
| `docker exec aep-phase2-redis72 redis-cli -n 15 --scan --pattern aep:*` | 0 | No keys |
| `docker exec aep-phase2-redis72 redis-cli -n 15 INFO persistence` | 0 | `aof_enabled:1`, no pending AOF error |
| Final post-creation hash, manifest, and exact output-path verification described below | 0 | Required delivery check; only `docs/16` is the review output |

No standalone probe, prototype, compilation artifact, dependency installation, or external/provider command was used.

## 4. Repository-invariant compatibility

| Required invariant | `docs/15` treatment | Assessment |
|---|---|---|
| Exact authoritative canonical request-binding string | Declares the Redis `canonical_request_binding` string to be sole authority; copies are non-authoritative and exact-compared | Preserved in intent; **conditional** because the production binding schema is left open |
| Strict canonicalization, 1 MiB, depth 128 | Preserves `aep.canonical-json/1` and the request limits | Request path preserved; vault-envelope use is internally contradictory (Finding PVK-R-01) |
| Raw state before semantic interpretation | Explicit invariant and retained preflight/Lua ordering | Preserved |
| Immutable identities, versions, profiles, keys, deadlines | Bound through Redis/AAD/context and checked before provenance | Preserved in principle; field schemas are incomplete |
| Authenticated vault metadata | Full AAD and exact comparison required | Preserved in principle; unauthenticated orphan/selector routing needs correction |
| Exact endpoint-profile revalidation | Required immediately before provenance | Preserved |
| One-use connector-consumed `VerifiedDispatch` | Required without alternate raw mutation path | Preserved |
| Create-once vault behavior | Atomic conditional create; no read-then-write, overwrite, adoption, or plaintext fallback | Preserved |
| CAS then same-connection `WAITAOF` | Explicit V1/I1/P1 sequence retains current boundary | Preserved |
| Durable vault acknowledgement before intent durability | V1 precedes I1 | Preserved |
| Durable intent acknowledgement before provider transport | I1 and P1 precede transport | Preserved |
| At most one application-level mutation attempt | One connector call; automatic retry/redirect/failover disabled | Preserved |
| Read-only recovery | Recovery workers cannot mutate or obtain mutation credentials | Preserved |
| Typed privacy boundary | Sealed event/result types and prohibited raw values | Preserved as intent; exact type bounds remain incomplete |
| Production dispatch disabled by default | Separate gates and authenticated activation record required | Preserved as intent; activation record is not frozen |

The design does not deliberately weaken the delivered protocol. It correctly says that the vault is not a second canonical-binding authority and that durable storage is not provider execution. The lifecycle selector is intended to be authoritative only for the active wrapping revision. As currently specified, however, its absent/genesis and rollback behavior can make it an unsafe second control authority; this prevents full compatibility verification.

## 5. Trust-boundary assessment

The component table correctly separates workflow, vault facade, object store, KMS/HSM, canonical Redis binding, intent ledger, provenance issuer, connector, audit pipeline, and operator/deployment roles. It states realistic assumptions: the application host, an authorized malicious connector, and provider/KMS control-plane compromise are not solved by this boundary. It also separates confidentiality, integrity, authenticity, durability, availability, and external-effect ambiguity.

Strong properties are:

- plaintext request material never becomes an object-store, Redis, audit, or KMS input except where the specific cryptographic operation requires it;
- master keys do not enter the application boundary;
- raw SDK objects and provider exceptions do not cross adapter boundaries;
- connector credentials are separated from vault/KMS administration;
- audit evidence is complementary rather than a substitute for primary state; and
- dependency failure blocks dispatch instead of selecting an alternate backend or key.

The trust model is not yet implementable at the lifecycle and audit boundaries. “Separately authenticated” selector/control records, audit-outbox durable acceptance, activation authorization, and safe key/namespace identifiers have no exact verifier, issuer, trust-anchor, schema, or bounded receipt contract. These omissions require security semantics to be invented in Stage 2.

## 6. Interface-contract assessment

| Contract family | What is sufficiently stated | Missing security/consistency contract | Result |
|---|---|---|---|
| Object store | Exact locator/revision, atomic conditional create, exact-version read, CAS, stable classifications, unknown-write reconciliation, no latest/adoption | Exact frozen definitions for receipts, provider version tokens, operation IDs, lifecycle records, selector identity, cancellation-before/after-submit, and per-operation audit/dispatch effects | **Incomplete** |
| KMS/HSM | Exact immutable key identity/version, approved algorithm, exact context, no alias/default/alternate/plaintext fallback, bounded read retries | Frozen typed inputs/results/receipts; per-operation outcome certainty; exact cancellation behavior; context-mapping result; safe metadata bounds; audit evidence | **Incomplete** |
| Vault facade | Correct conceptual operations and one codec owner | `CompleteVaultBindingContext`, `ExpectedVaultRead`, `PreparedDurableVaultObject`, `AuthenticatedExactMaterial`, `ExactRewrapPlan`, receipts, lifecycle views, deadline/cancellation fields, and safe representations are names rather than schemas | **Incomplete** |
| Lifecycle operations | Immutable revisions, CAS selector, holds, exact deletion, tombstones, unknown reconciliation | Exact selector/hold/deletion/tombstone schemas, legal transition validator, genesis, monotonic anchor, CAS reconciliation receipt, and authenticated issuer | **Blocking incomplete** |
| Audit outbox | Durable acceptance gates create/read/rewrap/delete/dispatch eligibility | No interface, idempotency key, unknown-acknowledgement handling, conditional append semantics, receipt schema, deadline/cancellation, or recovery rule | **Blocking incomplete** |
| Activation/configuration | Multi-condition signed record and negative startup gates | No exact record schema, signature/trust-anchor rules, anti-replay/revocation semantics, safe issuer/approver types, or validation order | **Incomplete** |

The common failure envelope is a useful base and provider exceptions are correctly contained. It does not make every operation exact. In particular, combining `apply_retention_hold / release_retention_hold / delete_if_eligible` behind one result signature leaves different mutation, certainty, and retry semantics unspecified. `safe_status` and `lifecycle_inspect` cannot be implemented securely until the accepted absence, generation, and authenticated-control-record meanings are frozen.

The design correctly rejects all of the following: read-then-write create-once, compare-and-adopt on conflict, treating unknown writes as absence, latest-object reads, raw SDK authority, default/alias reads, alternate-key trial, plaintext fallback, and automatic test-backend downgrade.

## 7. Envelope, AAD and KMS-context assessment

The following are clear and compatible:

- `vault_envelope_schema`, `envelope_format_version`, `envelope_revision`, `material_object_version`, and `request_material_version` are distinct concepts;
- revision 1 has null predecessor fields; later immutable revisions link the prior envelope and may change only wrapper/context/linkage fields;
- creation key identity/version is immutable AAD, while current wrapping key identity/version is revision-specific;
- the exact immutable KMS key version is persisted and aliases are forbidden on read;
- data encryption is AES-256-GCM with a 32-byte DEK, 12-byte nonce, 16-byte tag, and no algorithm downgrade;
- nonce/ciphertext/tag/material AAD remain byte-identical during rewrap;
- binary fields are intended to be strict unpadded base64url; duplicates, unknown fields, noncanonical JSON, unsupported versions, and invalid encodings are rejected;
- AAD/context bytes and SHA-256 values are stored exactly; checksums are not misrepresented as AEAD authenticity;
- deadline ordering is `created_at <= intent_creation_not_after < dispatch_material_not_after <= retention_not_after`; and
- the Redis canonical binding remains authoritative for the request fingerprint and binding digest.

The envelope is not implementable as written. A decoded ciphertext may be 1,048,576 bytes. Its unpadded base64url representation alone is 1,398,102 bytes, before JSON member names, AAD, KMS context, wrapped DEK, or other metadata. Yet `docs/15` requires the stored envelope to use delivered `aep.canonical-json/1`, whose implementation rejects canonical documents over 1,048,576 bytes. The separate 1,500,000-byte envelope cap cannot override that delivered canonicalizer without changing its version/semantics. This is a direct blocking contradiction, not a provider choice.

The field lists also omit exact primitive types, literals, regex/byte bounds, and semantic definitions for most AAD/context fields. `SafeId`, `SafeVaultLocator`, `ApprovedWrapAlgorithm`, fingerprints, schema identifiers, key versions, and timestamp/integer maxima are not frozen in `docs/15`. `material_ciphertext_sha256` refers to a domain-separated framing but does not define the separator, length framing, integer encoding, or exact bytes. `previous_envelope_sha256` does not explicitly define whether it hashes the exact canonical envelope bytes, a domain-separated representation, or a provider payload. These choices are security semantics, not mechanical implementation details.

The design's safe checksum use, key separation, expiry/retention order, and no-guarantee language are accepted. The schema and encoding gaps are not.

## 8. Construction-order and circular-dependency analysis

No inherent cryptographic circle is required if the design is frozen in this order:

1. Strictly canonicalize the exact request under the delivered request limits.
2. Build the safe descriptor and historical protected commitments, then compute the semantic fingerprint.
3. Allocate immutable attempt identities, locator, profiles, versions, and ordered deadlines.
4. Resolve the configured new-write key once to an approved backend, immutable key identity, and immutable key version.
5. Compute the attempt binding digest under one frozen production binding schema.
6. Build the complete canonical request binding in memory; it is persisted only after V1.
7. Build canonical `aep.vault-aad/2` from immutable material/binding facts, including the fingerprint and binding digest, then hash those exact AAD bytes.
8. Build revision-1 `aep.vault-kms-context/1` from the AAD hash, exact wrapper key/version/algorithm, revision 1, and null predecessor.
9. Generate/wrap the DEK with that exact context, generate a fresh nonce, and encrypt exact material with the exact AAD.
10. Compute the specified material checksum, canonicalize the complete envelope, and conditionally create revision 1.
11. Only after the envelope bytes exist can their exact hash be computed for use as a future revision's predecessor hash.
12. Obtain the approved durable receipt, exact authenticated readback, and audit-outbox receipt; then persist the Redis canonical binding by CAS and same-connection `WAITAOF`.

For rewrap, hash the exact selected prior envelope, build the new revision/context with that predecessor hash and the new exact key version, rewrap the same DEK, create and verify the immutable candidate, then CAS the lifecycle selector. The wrapped DEK, wrapper key/version, KMS context, revision, and predecessor linkage change. Plaintext, nonce, ciphertext, tag, material AAD, material identity, semantic fingerprint, binding digest, and authoritative Redis binding do not.

This order resolves AAD -> AAD digest -> KMS context -> wrapped DEK -> envelope -> future predecessor hash. It does not resolve the design's missing production binding schema or exact hash/framing rules; those must be fixed before construction can be implemented.

## 9. Validation and dispatch-order assessment

The nine-step dispatch-read order is fail-closed in intent: bounded envelope and receipt validation; canonical AAD/context validation; identity/binding validation; exact key-version selection; exact unwrap; AEAD authentication/decryption; descriptor/commitment/fingerprint/digest/binding reconstruction; exact profile/deadline revalidation; and only then one-use provenance.

Correctly ordered properties include:

- no envelope-supplied backend/key/version is accepted before structural and expected-binding checks;
- no alternate key, alias, namespace, region, object revision, or plaintext path is tried;
- plaintext is not available before KMS context and AEAD authentication succeed;
- exact profile revalidation and deadline checks occur before provenance; and
- every rejected store/KMS/vault/profile/configuration case is specified to cause zero external provider mutation calls.

Two routing gaps remain:

1. The lifecycle selector chooses an envelope revision before Section 7.4 validates the “authoritative lifecycle selector.” Because the selector schema/authenticator/genesis is absent, an untrusted or rolled-back selector value may influence storage routing before its required authority is established.
2. Ordinary orphan classification derives Redis execution/intent lookup keys from an AAD candidate that the design explicitly has not yet authenticated. Syntactic bounds can constrain the lookup, but `BOUND`, `CONFLICT`, and `INTEGRITY_FAILURE` cannot be authoritative until exact KMS/AEAD authentication or an independently authenticated index/receipt establishes those identities.

Early selection of a bounded safe endpoint-profile identifier only to route validation is acceptable because the design withholds a successful profile result and dispatch authority until step 8. No raw value is authorized for logging or provider dispatch. The selector and orphan cases require revision.

## 10. Lifecycle, rotation and rewrap assessment

The lifecycle table covers accepted material, encryption prepared, conditional create, durable create acknowledgement, durable intent acknowledgement, dispatch eligibility, expiry, retention hold, deletion eligibility, deletion/cryptographic inaccessibility, integrity failure, quarantine, and operationally unrecoverable state. It correctly distinguishes process memory, immutable object receipts, Redis intent state, and lifecycle-control state rather than claiming one cross-system transaction.

New-write rotation is soundly separated from historical reads. Rewrap uses an immutable candidate, verifies it before selector CAS, retains the old revision for rollback/retention, never overwrites the only readable revision, and does not issue dispatch provenance. Algorithm migration is correctly separated from rewrap.

The selector design is nevertheless blocking incomplete:

- “absence means revision 1” conflicts with “revision 1 if no selector has ever existed”; no durable fact distinguishes never-created selector state from deletion, loss, rollback, or an unavailable selector after rewrap;
- no exact selector record binds material identity, selected revision, selected envelope hash/provider version/checksum, lifecycle generation, predecessor, decision ID, or authenticated issuer;
- there is no monotonic anchor outside the selector from which a reader can detect a rollback to an older generation;
- acknowledgement-loss reconciliation says to strongly reread the selector but does not define which observed generation/value is acceptable when the initiating receipt was lost;
- selector CAS and hold/deletion changes share a generic lifecycle record without frozen legal-transition and merge rules; and
- automatic revision-1 fallback after selector loss could silently reactivate an older wrapping-key revision while the old key remains usable.

These defects can make the selector an unsafe second control authority even though it is not the canonical request authority. The design must define selector genesis (preferably a durable revision-1 control record or equivalent immutable anchor), exact authentication, monotonic generation/rollback evidence, absence semantics, exact candidate hash binding, and unknown-CAS reconciliation before Stage 2.

Expiry and holds are otherwise ordered correctly: expiry cannot move backward, a hold extends retention but never restores dispatch, deletion requires dispatch impossibility plus grace/retention/hold checks, and old keys are never tried automatically.

## 11. Crash and partial-failure assessment

| Case | Design result | Review |
|---|---|---|
| Store succeeds, acknowledgement lost | `CREATE_OUTCOME_UNKNOWN`, zero provider calls, V1 not yet known, exact same-target reconciliation, no create retry | Correct |
| Store succeeds, process crashes before intent | V1 yes, I1 no, retained orphan candidate, zero provider calls | Correct |
| Vault succeeds, Redis intent creation fails | V1 yes, I1 no, grace/reference checks, no immediate delete | Correct |
| Intent succeeds, vault/KMS temporarily unavailable | V1 and I1 already exist; zero now, at most one later by the original worker after full revalidation | Correct |
| KMS unavailable/denied/throttled/disabled/destroyed | Same exact key/context only where retryable; no fallback or mutation | Correct policy; historical V1/I1 counts are not consistently explicit |
| Wrong key version/context; ciphertext/AAD integrity failure | Zero mutation calls, no repair/alternate read, quarantine for integrity cases | Correct policy |
| Rotation between write/read | Persisted exact version only | Correct |
| Interrupted rewrap | Old selection stays active until verified candidate and known CAS | Correct intent; selector ambiguity remains |
| Unknown selector CAS | Strong exact reconciliation, no blind second CAS | Correct intent; accepted observed-state rule is missing |
| Delete while dispatch may remain possible | Reject and retain | Correct |
| Concurrent same-locator create | At most one accepted create; losers conflict/unknown and cannot adopt | Correct |
| Wrong environment/backend/region/namespace/key | Startup rejection, no cross-environment discovery/fallback | Correct |

The matrix avoids the historical-counter error in its clearest cases: vault success followed by Redis failure says V1 yes/I1 no, and intent success followed by read outage says V1/I1 already exist. It does not consistently state exact historical acknowledgement counts for unexpected-version, key-disabled/not-found, binding mismatch, integrity failure, expiry, or rotation rows, each of which can occur before or after I1. Those rows need phase-specific preconditions and explicit `historical V1/I1/audit acknowledgements`, `new acknowledgements`, and external-call counters.

The matrix also lacks an explicit security-critical audit-outbox success-with-lost-acknowledgement case, audit failure after immutable object creation, lifecycle-selector disappearance/rollback case, and exact cancellation-before-submit versus after-submit cases for each write-like operation. The narrative fails closed, but future tests cannot derive exact expected counters and reconciliation from it.

Recovery remains read-only with respect to the external provider. Store, KMS, Redis, audit, rewrap, retention, and recovery operations are not counted as external provider mutation calls.

## 12. Identity, configuration and activation-gate assessment

The seven roles are separated with useful positive and negative authority boundaries:

- the normal writer can wrap/create/read back but not decrypt later, list, overwrite, rewrap, delete, administer keys, or mutate a provider;
- the reader/dispatcher can exact-read and unwrap but not create/update/delete/list, resolve aliases, administer KMS, or use alternate backends;
- the rewrap worker can transform key slots and CAS selection but cannot mutate requests/providers or delete;
- the retention/deletion worker cannot unwrap plaintext, mutate provider/intent state, or administer keys;
- deployment/configuration cannot read material or perform destructive/key/provider operations;
- the audit reader cannot mutate vault/KMS/Redis/provider state; and
- emergency authority is time-bounded and cannot unilaterally decrypt, delete, or destroy keys.

Production/test trust domains, accounts/projects/subscriptions/partitions, namespaces, keys, audit sinks, identities, and artifacts are required to be separate. `docs/15` correctly says a boolean `test_only=False` is insufficient. The current `pyproject.toml` packages all `src*`, and `TestOnlyInMemoryRequestVault` currently shares `src/core/request_vault.py` with the protocol; therefore structural exclusion is a future required refactor, not a current property. The design does require the production artifact/factory to omit the class, fake barrier, mock connector, emulator, plaintext backend, arbitrary import, and fallback.

Startup correctly rejects an unchecked flag, implicit defaults, dynamic backend class, missing audit path, development credential fallback, unresolved new-write key, alias-based read, and unapproved namespace/account/region/profile. The activation record is appropriately separate from configuration and binds environment, artifact/config digests, both gate results, approvers, time, and rollout scope.

The activation record and signed configuration are not frozen schemas. Issuer trust, signature algorithm/key version, anti-replay, revocation, authorization-store consistency, safe approver identifiers, expiry/skew behavior, and runtime revalidation are unspecified. Stage 2 may safely keep production activation structurally absent, but it may not implement an activation-capable interface by inventing these semantics.

## 13. Privacy, telemetry and audit assessment

The design correctly makes typed construction, not post-hoc redaction, the primary control. It forbids request plaintext, ciphertext, nonce, tag, wrapped/plaintext keys, canonical AAD/context bytes, credentials, raw provider responses, exception objects, and raw request/binding/vault/dispatch objects from events, logs, traces, metrics, alerts, or generic dumps. Crypto-artifact hashes are protected operational metadata, not metric labels.

The event envelope uses sealed enums and typed values, metrics are low cardinality, and security-critical operations require durable outbox acceptance. The design does not claim guaranteed secret non-disclosure or guaranteed memory erasure.

Remaining issues are:

- `SafeId`, safe key/namespace IDs, audit correlation IDs, approval/ticket IDs, operation IDs, and tombstone fields have no exact byte/character limits or semantic allowlists in `docs/15`;
- a syntactically safe identifier can contain sensitive business meaning, which the design acknowledges but does not turn into a frozen construction rule;
- the audit-outbox interface and unknown-acknowledgement behavior are absent; and
- PVK criteria using “never” or “absent from every prohibited output” are only testable as bounded source/schema/marker evidence and must not be reported as universal non-disclosure.

These issues do not justify logging raw values. Any unknown or semantically unsafe identifier must be omitted or reduced to a fixed enum/pseudonym under the future exact schema.

## 14. Orphan, retention and deletion assessment

The design correctly treats object listing or inventory only as a candidate hint, never proof of existence or absence. It requires exact Redis/raw-state and authoritative-reference checks, a mandatory grace greater than all preparation/skew/dependency/restart windows, two checks separated by an observation interval, exact lifecycle CAS, retention authorization, and retention on every unknown/unavailable dependency. Deletion is blocked while dispatch remains possible.

Normal classification is intended not to decrypt. That is acceptable only if unauthenticated AAD fields are explicitly treated as bounded lookup hints and the result remains `CANDIDATE` or `UNKNOWN`. As written, the procedure may derive Redis keys from an unauthenticated AAD candidate and then classify `BOUND`, `CONFLICT`, or `INTEGRITY_FAILURE`; those classifications are not authoritative until exact KMS/AEAD verification or an independently authenticated receipt/index binds the identities. Deletion later requires KMS metadata authentication, which is fail-closed, but the earlier classification semantics still need correction.

The deletion vocabulary is otherwise strong and must be retained:

- logical deletion denies use but may leave bytes;
- ciphertext deletion concerns exact object versions, not replicas/backups;
- wrapped-key deletion concerns key slots, not a master key or all copies;
- master-key retirement prevents new use but may allow historical decrypt;
- cryptographic inaccessibility describes approved current paths, not guaranteed physical erasure; and
- provider backup retention is separate and provider-specific.

The combined lifecycle label `DELETED_OR_CRYPTOGRAPHICALLY_INACCESSIBLE` must not erase these distinctions. Exact tombstone state and achieved deletion class need separate enum values and receipts.

## 15. Acceptance-criteria testability assessment

All `PVK-*` identifiers are unique. The criteria are directionally observable, but they do not all provide precise preconditions, exact object/KMS/Redis/audit/provider call counters, historical versus new acknowledgements, or an evidence-stage label.

| Testability class | Criteria | Assessment |
|---|---|---|
| Provider-neutral contract/source tests after a corrected Stage 2 | `PVK-CAN-002`-`006`; `PVK-STR-001`-`005`, `007`; application-contract portions of `PVK-KMS-001`-`003`, `005`-`008`; `PVK-WFL-001`-`007`, `009`-`010`; `PVK-OPS-002`-`004`, `006`-`008` | Testable with frozen types, deterministic fault adapters, crash injection, and counters; proves application contract only |
| Provider-specific evidence required | `PVK-STR-006`; real atomic/durable parts of `PVK-STR-002`-`005`; real key-version/context/IAM portions of `PVK-KMS-001`-`003`; actual cross-environment denial in `PVK-OPS-001`; provider audit delivery/retention | Cannot pass from mocks/emulators/product names |
| Operational-policy checks | Key retirement/destruction, RPO/RTO/SLO budgets, retention/hold/tombstone/backup rules, separation of duties, signed config/activation, incident and rollback approval | Requires selected environment and reviewed policy/evidence |
| Independent-review checks | Accepted durability class, production artifact exclusion, provider documentation/config match, IAM negatives, backup/deletion claim boundaries, separate connector and activation gates | Cannot be self-certified by unit tests |
| Not sufficiently testable as written | `PVK-CAN-001`, `CAN-004`, `STR-008`, `KMS-004`, `KMS-006`, `WFL-003`, `WFL-008`, `OPS-001`, `OPS-005` | Conflicting size rule, unverifiable universal wording, missing selector/orphan semantics, or missing phase-specific counters/preconditions |

Specific corrections are required:

- `PVK-CAN-001` must resolve which canonical byte cap applies to the 1.5 MB envelope.
- `PVK-CAN-004` can verify nonce length, one encryption per DEK, fresh generation path, and no reuse under injected restarts; it cannot prove universal random uniqueness.
- `PVK-STR-008`, `PVK-KMS-004`, and `PVK-OPS-005` must be scoped to typed interfaces, inspected source/builds, simulated backing stores, authorized process boundaries, and generated marker corpora rather than absolute “never/every” claims.
- `PVK-KMS-006` needs exact selector genesis, acceptable observed states, and per-crash store/KMS/CAS/audit counters.
- `PVK-WFL-003` needs a row per failure phase with external mutation calls, store/KMS calls, Redis CAS/`WAITAOF`, audit acceptance, historical V1/I1, and new acknowledgements.
- `PVK-WFL-008` must distinguish unauthenticated candidate discovery from authenticated classification/deletion eligibility.
- `PVK-OPS-001` must split provider-neutral role/interface tests from later real IAM denial tests.

A mock or emulator may prove only application contract behavior. It cannot prove conditional-create linearization, durable acknowledgement, provider read consistency, key-version immutability, context enforcement, IAM, audit delivery, retention/legal hold, backup/deletion, or regional failure semantics.

## 16. Provider-neutrality assessment

The AWS, Microsoft Azure, Google Cloud, and other-provider rows are explicitly non-binding. They use product names only as possible mappings and correctly require later evidence for every material semantic. No SDK, service, key type, storage class, account, region, or provider is selected.

The following cannot honestly be standardized as verified provider behavior at this stage:

- the linearization point and response-loss semantics of conditional create;
- the fault domain represented by a durable acknowledgement;
- strongly consistent absence and exact immutable-version reads;
- lifecycle-selector CAS, generation, and rollback behavior;
- read-after-create and retention/legal-hold behavior;
- immutable KMS key-version addressing and lifecycle state;
- encryption-context mapping/enforcement and size limits;
- application/provider audit acceptance, ordering, delivery, and retention;
- object versions, delete markers, purge, replicas, snapshots, backups, and key backups; and
- regional outage, failover, split-brain, and control-plane behavior.

`docs/15` correctly reserves these matters for later primary documentation and exact-environment tests. Provider neutrality of its claims is **verified**. Completeness of the provider-neutral application contract is **not verified** because the blocking schema/selector issues precede provider selection.

## 17. Research evaluation assessment

The proposed experiments are explicitly future work and generally measurable. They name latency percentiles, classification accuracy, false retry/fallback, provider-call counts, false absence/success, concurrent winners, selected revisions, recovery actions, early/late dispatch/deletion, marker occurrences, RPO/RTO observations, cost, throttling, and availability. They correctly label in-memory and non-bound variants as weaker non-production baselines.

Required framing conditions are:

- the AEP, not the vault/KMS service, remains the primary research contribution;
- experiments evaluate how the encrypted-material boundary supports the AEP's durable-intent/exact-binding/verified-dispatch protocol;
- real provider work remains future, separately authorized work with synthetic non-sensitive material;
- “expected zero” is an experimental acceptance target, not an already verified absolute claim; and
- no experiment may infer provider durability or production security from a mock/emulator.

`docs/15` does not explicitly restate the paper's primary-contribution boundary in its research section. That is a documentation limitation, not a reason to convert this work into a KMS paper.

## 18. Findings and required corrections

| ID | Severity | Finding | Required correction before implementation |
|---|---|---|---|
| PVK-R-01 | **BLOCKING** | The 1,500,000-byte canonical envelope and 1,048,576-byte ciphertext cannot use the delivered `aep.canonical-json/1` 1,048,576-byte document cap; ciphertext base64 alone can be 1,398,102 bytes. | Freeze a non-conflicting versioned envelope encoding/cap or reduce material support without weakening the authoritative request limit; define migration/compatibility and update PVK-CAN-001. |
| PVK-R-02 | **BLOCKING** | The authoritative production persisted-binding schema is an open decision even though AAD and construction depend on creation-key identity/version and Stage 2 is supposed to freeze schemas. | Name and fully define the production binding schema, all fields/bounds, exact digest inputs, compatibility with `aep.persisted-request-binding/1`, Lua equality/preflight behavior, and one-authority rule. |
| PVK-R-03 | **BLOCKING** | AAD/context/envelope fields and cryptographic checksums/link hashes lack exact primitive types, bounded encodings, domain separators, framing, and hash-input definitions. | Freeze exact schemas and canonical bytes for every field, material checksum, envelope hash, predecessor link, base64url decoder, algorithms, and constant-time comparisons. |
| PVK-R-04 | **BLOCKING** | Lifecycle selector absence/genesis, authentication, generation, rollback detection, exact envelope binding, and unknown-CAS acceptance are undefined; selector loss can silently select revision 1. | Define an authenticated, bounded selector/control schema, durable genesis/anchor, monotonic generation and rollback evidence, exact selected envelope hash/version/checksum, legal transitions, and unknown-outcome reconciliation. |
| PVK-R-05 | **BLOCKING** | Object/KMS/facade/lifecycle/audit contracts use named placeholder types instead of frozen inputs/results/receipts; the audit outbox has no contract despite gating dispatch. | Define exact typed signatures, deadlines/cancellation, certainty/retry enums per operation, safe representations, audit receipts, idempotency/conditional semantics, unknown handling, and dispatch-eligibility effects. Keep activation structurally absent until its schema is separately frozen. |
| PVK-R-06 | **MAJOR** | The validation order uses the not-yet-validated selector for envelope routing and unauthenticated orphan AAD identities for Redis routing/classification. | Validate/authenticate selector authority before selection; treat orphan metadata only as bounded hints until authenticated, or provide an independently authenticated index/receipt. |
| PVK-R-07 | **MAJOR** | The failure matrix is phase-ambiguous for several KMS/integrity/expiry cases and omits audit acknowledgement loss, selector disappearance/rollback, and exact per-boundary counters. | Split cases by pre-V1, V1/pre-I1, post-I1/pre-transport, and lifecycle phase; state historical/new acknowledgements and all relevant call counters. |
| PVK-R-08 | **MAJOR** | Several PVK criteria conflate contract, provider, operational, and independent-review evidence or use unverifiable universal wording. | Add evidence-stage labels, precise preconditions, exact counters, bounded observation claims, and provider-only/operational prerequisites. |
| PVK-R-09 | **MINOR** | Safe IDs, operation IDs, approval/ticket IDs, key/namespace IDs, audit correlations, and tombstone fields are not fully bounded or semantically constrained in the design. | Freeze character, byte, cardinality, provenance, and semantic-construction rules; omit/reduce unknown values. |
| PVK-R-10 | **DOCUMENTATION** | The research section does not expressly state that AEP is the paper's primary contribution and this boundary is supporting infrastructure. | Add that scope sentence and preserve future-work labels; do not add a cloud/KMS novelty claim. |

Because BLOCKING and MAJOR findings exist, a separate revision stage for `docs/15` is required. This review does not silently repair the design, and Stage 2 implementation is not authorized.

## 19. Verified and unverified guarantees

| Guarantee | Status | Boundary |
|---|---|---|
| Current repository exact canonical binding and raw-state gate | **VERIFIED** | Delivered source and unchanged tests |
| Current one-use connector-consumed provenance | **VERIFIED** | Cooperative repository Python process/test connectors |
| Current CAS then same-connection `WAITAOF`, one mutation attempt, no automatic mutation retry | **VERIFIED** | One local Redis 7.2.5 AOF test environment |
| Current recovery never replays a mutation | **VERIFIED** | Delivered read-back-only recovery path |
| `docs/15` preserves V1 -> I1 -> P1 and production-disabled intent | **VERIFIED** | Design statement only |
| Provider-neutral create-once/exact-key/no-fallback policy | **PARTIALLY VERIFIED** | Direction is precise; full interface schemas are not |
| Envelope/AAD/context implementation semantics | **NOT VERIFIED** | Blocking size/schema/hash conflicts |
| Lifecycle selector rollback/acknowledgement safety | **NOT VERIFIED** | Missing genesis/authentication/anchor/reconciliation semantics |
| Durable production object or audit acknowledgement | **NOT VERIFIED** | No implementation/provider evidence |
| Provider KMS/HSM key-version/context behavior | **NOT VERIFIED** | No provider evidence |
| Production IAM, audit, retention, backup, deletion, or regional behavior | **NOT VERIFIED** | No operational/provider evidence |
| Production build excludes test vault structurally | **NOT VERIFIED / NOT IMPLEMENTED** | Current package still includes test vault class |
| Production connector/profile/credentials/response safety | **NOT VERIFIED / ABSENT** | Separate later gate |
| Exactly-once effects, absolute Redis/provider atomicity, split-brain prevention, guaranteed duplicate prevention | **NOT VERIFIED / NOT CLAIMED** | Separate systems and single-node boundary |
| Guaranteed secret non-disclosure or in-memory erasure | **NOT VERIFIED / NOT CLAIMED** | Bounded typed controls only |
| Historical proof that only `docs/15` changed or tests were never weakened | **NOT VERIFIED** | Git metadata unusable |

Repository closure and design prose are not production closure. Passing the unchanged repository suite confirms the delivered baseline; it does not pass any future PVK criterion or establish provider behavior.

## 20. Final classifications and recommendation

| Classification | Decision | Reason |
|---|---|---|
| Provider-neutral design | **REQUIRES REVISION** | Provider claims are neutral, but blocking application-contract semantics remain open/contradictory |
| Design completeness | **NOT VERIFIED** | Stage 2 would have to invent binding, envelope/hash, interface, audit, and selector semantics |
| Compatibility with Agent Execution Protocol | **PARTIALLY VERIFIED** | Governing order/invariants are retained, but canonical-size and selector-authority gaps prevent full verification; no source regression was introduced |
| Ready to begin provider-neutral interface implementation | **NO-GO** | Separate `docs/15` revision and independent rereview required first |
| Durable production vault/KMS implemented | **NO** | Design only |
| Provider-specific durability verified | **NO** | No provider evidence |
| Production applicability | **NO-GO** | Vault/KMS, operations, connector, and activation gates absent |
| First production connector implementation | **NO-GO** | Durable vault/KMS production gate has not passed |
| Production non-idempotent dispatch | **NO-GO** | Must remain disabled |

Recommendation: revise `docs/15` only in a separate bounded design stage, resolve PVK-R-01 through PVK-R-08, and submit the revised document to another independent read-only review. A future `GO`, if earned, may authorize only provider-neutral interfaces, frozen schemas/codecs, typed results/errors, production/test composition separation, and later provider-neutral contract tests. It must not authorize a provider, SDK, cloud/HSM resource, connector, deployment, credential, production activation, or provider mutation.

Ambiguity, corruption, and contention are detectable; the system fails closed.
