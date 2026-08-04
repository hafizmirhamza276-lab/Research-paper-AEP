# Revised production vault/KMS design independent rereview

**Rereview date:** 2026-08-01  
**Rereview mode:** independent, repository-local, read-only except for this document  
**Reviewed revision:** `docs/15-production-vault-kms-design.md` at SHA-256 `9dfe04d0ebced0b7a4dddadffc94a87c76348d331ac5286fb57ad217caaf8394`  
**Decision:** further revision is required; bounded provider-neutral interface implementation remains **NO-GO**

## 1. Rereview purpose and evidence boundary

This rereview determines whether the corrected `docs/15-production-vault-kms-design.md` genuinely resolves the ten independent findings in `docs/16-production-vault-kms-design-review.md`, preserves the delivered Agent Execution Protocol (AEP), and freezes enough security and consistency semantics for a bounded provider-neutral Stage 2 implementation. The revised document's own status and traceability table were treated as claims to test, not as acceptance evidence.

The rereview inspected:

- `docs/06-phase2-design.md` through `docs/16-production-vault-kms-design-review.md`, with particular attention to the historical gates and the final precedence decisions in `docs/12` and `docs/14`;
- the relevant delivered-tree addenda in `phase2_implementation_report.md`, including the `2026-07-31 addendum: canonical request-binding repository closure` and the final `2026-07-31 final delivered-tree closure evidence and precedence`;
- `src/core/request_binding.py`, `request_vault.py`, `intents.py`, `intent_workflow.py`, `intent_recovery.py`, `durability.py`, `state_codec.py`, `storage.py`, `locks.py`, `exceptions.py`, and `validation.py`;
- the canonicalization, vault, canonical-binding, binding-intent, AAD, endpoint-profile, verified-dispatch, provenance, privacy, runner, recovery, durability, `WAITAOF`, mutation-safety, raw-state, and state-codec tests, plus their fixtures and mock connector; and
- `pyproject.toml`, `compose.phase2.yml`, and `redis/phase2.conf`.

Latest verified delivered-tree evidence controls where historical documents conflict. The accepted repository baseline is therefore repository enforcement `VERIFIED`, P2-004 `CLOSED (repository scope)`, P2-010 `CLOSED (repository-defined Phase 2 mutation scope)`, and the recorded unchanged-suite result `611 passed`. Those classifications do not establish a production vault, provider durability, a connector, or production dispatch.

This rereview did not modify `docs/15`, `docs/16`, source, tests, configuration, reports, or any other existing file. It did not install anything, use credentials, access an external service, select a provider, implement a schema or adapter, create an activation surface, create a connector, or issue a provider mutation. No test was rerun because the revision is documentation-only and the user supplied the unchanged `611 passed` baseline. This document is the only created artifact.

Unavailable evidence remains material:

- `.git` is an empty directory, and Git cannot recognize the workspace as a repository. Historical additions, deletions, or test weakening cannot be proved from Git history.
- No provider documentation, account, SDK, IAM policy, object-store/KMS/lifecycle/audit resource, production build, operational policy package, or external fault evidence is present.
- None of the proposed production schemas or interfaces exists in `src` or `tests`; their implementability can be reviewed only from the design and its compatibility with the delivered tree.

## 2. Repository and changed-file verification

### 2.1 Required section inventory

All 22 required top-level sections remain present, exactly once and in numeric order:

| Section | Revised title | Present |
|---:|---|---|
| 1 | Purpose and current baseline | Yes |
| 2 | Scope and exclusions | Yes |
| 3 | Existing repository invariants | Yes |
| 4 | Threat and trust-boundary model | Yes |
| 5 | Provider-neutral component architecture | Yes |
| 6 | Interface contracts | Yes |
| 7 | Envelope and authenticated-metadata schema | Yes |
| 8 | Write, read, dispatch, rotation, rewrap, retention, and deletion flows | Yes |
| 9 | Lifecycle state machine | Yes |
| 10 | Crash and partial-failure matrix | Yes |
| 11 | Key lifecycle and authorization model | Yes |
| 12 | Configuration and startup gates | Yes |
| 13 | Safe telemetry and audit evidence | Yes |
| 14 | Orphan reconciliation and recovery | Yes |
| 15 | Provider-neutral acceptance criteria | Yes |
| 16 | Future provider-specific test plan | Yes |
| 17 | Provider mapping table | Yes |
| 18 | Research evaluation plan | Yes |
| 19 | Traceability matrix from review findings and prior residual limitations | Yes |
| 20 | Open decisions and residual risks | Yes |
| 21 | Implementation sequencing | Yes |
| 22 | Final GO/NO-GO classifications | Yes |

The file contains 83 Markdown headings in total and 22 numbered level-2 headings.

### 2.2 Hashes, manifests, and line endings

The manifest algorithm was independently reconstructed and matched all three reported manifest values. For each selected file it emits `repository-relative POSIX path<TAB>lowercase SHA-256`, sorts by relative path, joins rows with LF and no final LF, UTF-8 encodes that manifest, and SHA-256 hashes the result.

| Evidence | Expected | Observed | Result |
|---|---|---|---|
| Revised `docs/15` SHA-256 | `9dfe04d0ebced0b7a4dddadffc94a87c76348d331ac5286fb57ad217caaf8394` | Same | Match |
| Source/tests manifest | `b3d60014240692936afdaf2b37be0ea51fe9e327a6c06a0a8013c40e96d5bb8a` | Same, 88 files | Match |
| Configuration manifest | `eaef6ce9bbe12f4c8b766489d976886433ec43ff4d89a7923e32894189fd4e63` | Same, 3 files | Match |
| All files except `docs/15` and volatile metadata | `d347849318e5999341de3a745feee5a436dba7fb12fd47bba15028f1402c7db4` | Same, 92 files before this output existed | Match |

The source/tests selection deliberately includes the 44 existing `.pyc` files as well as 43 Python files and `tests/MATRIX.md`; that explains its 88-file count. The all-other manifest excludes `.git`, `.pytest_cache`, and `__pycache__`. The configuration selection is exactly `compose.phase2.yml`, `pyproject.toml`, and `redis/phase2.conf`.

After this output was created, the same all-other calculation excluding both `docs/15` and this authorized `docs/17` output again selected 92 files and returned `d347849318e5999341de3a745feee5a436dba7fb12fd47bba15028f1402c7db4`. The source/tests and configuration manifests also remained exact.

`docs/15` contains 1,032 LF line terminators, zero CRLF pairs, and zero lone CR characters. Its raw hash and LF-normalized hash are identical. Converting it to CRLF would change the hash to `d5dd8462b73f2e0ac387647c36b4f0c8769ca867479b22ea9ac85b82ada0cc02`. Line-ending normalization therefore does not affect the reported hash when normalization is to LF, but conversion to CRLF does.

The prior reviewed `docs/15` hash recorded in `docs/16` was `a21712504c16d9f10d7c7b7f08518ccd6a15298fdb00b6a6791cc20891be9bff`; the revised file is demonstrably different. The protected document hashes for `docs/06` through `docs/14` and `phase2_implementation_report.md` still match the values recorded by `docs/16`/`docs/14`, and the supplied all-other manifest matches exactly.

The historical statement “only `docs/15` changed during the correction stage” is **PARTIALLY VERIFIED, not historically proved**. The matching recorded all-other manifest and protected hashes strongly corroborate it, and current-tree inspection found no production implementation. They do not replace a before/after version-control history. Git cannot supply that history because `.git` has zero children and all tested Git discovery/status commands return 128. No stronger historical claim is made.

### 2.3 Exact command and exit record

The definitive integrity command was:

```powershell
$ErrorActionPreference='Stop'
$repo=(Get-Location).Path
$utf8=[Text.UTF8Encoding]::new($false)
$sha=[Security.Cryptography.SHA256]::Create()
$tab=[char]9; $lf=[char]10; $bs=[char]92
function Hash-Text([string]$value){([BitConverter]::ToString($sha.ComputeHash($utf8.GetBytes($value)))).Replace('-','').ToLowerInvariant()}
function File-Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Manifest([object[]]$files){
  $rows=@()
  foreach($file in $files){
    $relative=$file.FullName.Substring($repo.Length+1).Replace($bs,'/')
    $rows += [pscustomobject]@{Relative=$relative;Hash=(File-Hash $file.FullName)}
  }
  $rows=@($rows|Sort-Object Relative)
  [pscustomobject]@{Count=$rows.Count;Hash=(Hash-Text (($rows|ForEach-Object{$_.Relative+$tab+$_.Hash})-join $lf))}
}
$sourceTests=Manifest @(Get-ChildItem -LiteralPath src,tests -Recurse -File -Force)
$config=Manifest @(Get-Item -LiteralPath pyproject.toml,compose.phase2.yml,redis\phase2.conf)
$allOther=Manifest @(Get-ChildItem -Recurse -File -Force|Where-Object{$_.FullName -notmatch '\\.git\\|\\.pytest_cache\\|\\__pycache__\\' -and $_.FullName -ne (Join-Path $repo 'docs\15-production-vault-kms-design.md')})
```

It exited `0` and produced the four matching values above. Other definitive commands were:

| Exact command or command family | Exit | Genuine result |
|---|---:|---|
| `Get-ChildItem -Path . -Filter AGENTS.md -Recurse -Force \| Select-Object -ExpandProperty FullName` | 0 | No `AGENTS.md` found |
| `rg --files` | 0 | Repository inventory obtained |
| `rg -n '^#{1,6} ' docs/15-production-vault-kms-design.md` | 0 | All headings inventoried |
| `(rg -n '^## [0-9]+\. ' docs/15-production-vault-kms-design.md \| Measure-Object).Count` | 0 | `22` |
| `Get-FileHash -LiteralPath docs\15-production-vault-kms-design.md -Algorithm SHA256` | 0 | Reported hash matched |
| UTF-8 read plus LF/CRLF normalization/hash script | 0 | raw = LF hash; CRLF hash differs as recorded |
| `Get-FileHash -Algorithm SHA256` over `docs/06`-`docs/16` and `phase2_implementation_report.md` | 0 | Current protected hashes obtained; prior recorded values matched where available |
| `git status --short --branch` | 128 | `fatal: not a git repository` |
| `git log --oneline -n 8` | 128 | `fatal: not a git repository` |
| `git rev-parse --show-toplevel` | 128 | `fatal: not a git repository` |
| `git --git-dir=.git --work-tree=. status --short --branch` | 128 | `fatal: not a git repository: '.git'` |
| `Get-ChildItem -LiteralPath .git -Force` | 0 | Zero entries |
| Numbered `Get-Content` reads covering all of `docs/15`, the findings and assessments in `docs/16`, relevant ranges in `docs/06`-`docs/14`, and the delivered-tree report addenda | 0 | Required document evidence inspected |
| Numbered `Get-Content` reads of the relevant source files and `rg` inventories of tests/symbols/paths | 0 | Delivered invariants and test coverage traced |
| `rg -n "aep\.production-vault-envelope-lf/1\|aep\.production-persisted-request-binding/2\|aep\.vault-lifecycle-genesis/1\|AuditOutbox\|create_genesis_and_selector_once\|compare_and_advance_selector" src tests pyproject.toml compose.phase2.yml redis/phase2.conf` | 1 | No production schema/interface implementation found; exit 1 means no match |
| Acceptance-row parser over Section 15 | 0 | 47 criteria, 47 unique IDs; 38 `CONTRACT`, 5 `PROVIDER`, 1 `OPERATIONAL`, 3 `INDEPENDENT_REVIEW`; no invalid/multiple label |

### 2.4 Tests

No test command was run in this rereview. The genuine latest delivered-tree record is the unchanged integration-enabled suite at exit `0`, `611 passed in 48.08s`, zero failures and zero skips, recorded at the end of `phase2_implementation_report.md` and independently accepted by `docs/14`/`docs/16`. The matching source/tests manifest confirms the inspected source/test tree corresponds to the supplied correction-stage baseline. It does not prove that the new design contracts pass, because those contracts are not implemented.

## 3. Research-topic alignment

The revised Section 18 contains, byte-for-byte with Unicode U+2019, the required sentence:

> The Agent Execution Protocol is the paper’s primary research contribution. The production vault/KMS boundary is supporting infrastructure for confidential, durable and exactly bound request-material handling.

The revision preserves the AEP sequence—durable intent, exact request binding, protected material, verified one-use dispatch, one provider attempt, and read-only recovery—as the research subject. It expressly says the work does not claim novelty in cloud storage, KMS, or HSM design. Provider experiments remain future, separately authorized work using synthetic non-sensitive material. The measurements in Section 18 are proposed metrics, not reported results; no latency, failure-rate, availability, RPO/RTO, or provider measurement is fabricated. No exactly-once external-effect claim is introduced.

**Research alignment: VERIFIED.**

## 4. Preserved Agent Execution Protocol invariants

| Delivered invariant | Revised design treatment | Rereview result |
|---|---|---|
| Redis `canonical_request_binding` is the sole binding authority | Sections 3, 4.2, 7.2, 7.4, and 7.8 repeatedly require exact full-string equality and make every AAD/envelope/audit copy non-authoritative | Preserved in intent |
| `aep.canonical-json/1` retains 1,048,576-byte and depth-128 limits | Sections 3 and 7.1 preserve them; LF/1 is explicitly a separate binary envelope | Preserved |
| Raw Redis bytes precede semantic interpretation | Sections 3 and 7.8 put raw validation before binding/preflight semantics | Preserved |
| Exact immutable identities, profiles, credentials, versions, locator, key, and deadlines | Binding/AAD/context intend to bind them | Preserved in principle; v2-to-delivered-schema bridge is incomplete |
| Authenticated material and complete reconstruction precede authority | Section 7.8 orders selector, envelope, KMS, AEAD, reconstruction, Redis equality, and revalidation before provenance | Preserved in principle; facade/provenance contract contradicts this order |
| V1 precedes I1; I1 is CAS plus same-connection `WAITAOF` | Sections 5.3, 8.1, 9, and 10 retain the ordering | Preserved |
| L1 and A1 are additional pre-I1 gates, not substitutes for V1 or I1 | Sections 5.3 and 8.1 make the order `V1 -> L1 -> A1 -> I1 -> P1` | Preserved |
| At most one non-idempotent connector attempt; no retry/redirect/failover | Sections 3, 8.3, 9, 10.5, and 14.3 retain it | Preserved |
| Recovery never issues or replays the mutation | Sections 3, 10, and 14.3 retain read-only provider recovery | Preserved |
| Typed safe-value boundary | Sections 6.1, 7.1, and 13 prohibit raw request/crypto/provider/exception objects | Preserved in intent; some safe schemas remain incomplete |
| Test-only composition is not production composition | Sections 1, 12.2, 15.5, and 21 require structural exclusion and no activation surface | Preserved; not implemented |

The revision does not intentionally weaken the delivered protocol. Full compatibility cannot be verified because the proposed v2 binding changes identifier and digest encodings without freezing the production intent-record/version bridge, and because the facade/audit/provenance contracts still conflict. Repository closure remains distinct from production closure.

## 5. `PVK-R-01` disposition

**Disposition: RESOLVED.**

| Required item | Independent result |
|---|---|
| Exact revised sections | 2, 3, 6.2, 7.1, 7.6, 15.1, 19.1 |
| Original defect | A JSON envelope could not contain a 1,048,576-byte ciphertext while also conforming to the delivered 1,048,576-byte canonical-JSON document cap; prior totals and migration behavior were not implementable |
| Revised decision | A separate versioned binary codec, `aep.production-vault-envelope-lf/1`, carries bounded canonical JSON subdocuments and raw crypto fields; the request codec and its cap remain unchanged |
| Schemas/contracts examined | 40-byte LF/1 header, seven ordered segments, metadata/1, AAD/2, KMS-context/1, object-store `envelope_bytes[1..1_118_276]`, decoder order, and `PVK-CAN-001` |
| Repository invariants | Compatible with the delivered 1 MiB request and canonical-JSON limits; no JSON-root cap is bypassed or redefined |
| Semantic invention still required | No security/consistency semantic for framing or size; implementation still must faithfully code and test the frozen codec |
| Provider-specific dependency | The selected store must accept and preserve an exact 1,118,276-byte object and later prove its receipt/durability semantics |
| Acceptance evidence | `PVK-CAN-001 / CONTRACT` now specifies minimum/maximum requests, all maximum segments, each +1 boundary, truncation, overflow patterns, trailing bytes, preallocation rejection, exact counters, and the provider exclusion |
| Residual limitation | Provider capacity/durability and implementation correctness remain unverified; this is not a design defect |

Independent arithmetic:

```text
Header: final length word starts at offset 36 and occupies 4 bytes -> body starts at 40.
Maximum body:
  16,384 metadata
+ 32,768 AAD
+  4,096 KMS context
+     12 nonce
+1,048,576 ciphertext
+     16 tag
+ 16,384 wrapped DEK
=1,118,236 bytes

Maximum object = 40 + 1,118,236 = 1,118,276 bytes.
Declared framing minimum = 40 + 1 + 1 + 1 + 12 + 1 + 16 + 1 = 73 bytes;
semantic JSON validation may impose a higher valid-object minimum.
```

Every maximum segment fits `U32`; total calculation is explicitly checked in unsigned 64-bit space before allocation. The body order and header offsets are mutually consistent. Exact total length forbids truncation and trailing bytes; fixed framing prevents missing/duplicate/unknown outer fields, while the three canonical JSON parsers reject those conditions internally. Magic, version, flags, individual bounds, fixed nonce/tag lengths, total, provider length, and stream length are checked before segment allocation or KMS. Unsupported versions fail closed; future codecs require new magic/version, retained immutable source, non-dispatching migration, and independent review. The binary envelope makes no canonical-JSON-root conformance claim.

## 6. `PVK-R-02` disposition

**Disposition: PARTIALLY RESOLVED — BLOCKING residual.**

| Required item | Independent result |
|---|---|
| Exact revised sections | 3, 7.1, 7.2, 7.4, 7.8, 8.1, 15.1, 19.1 |
| Original defect | No frozen production binding schema, digest input, version compatibility, Lua equality behavior, or one-authority rule |
| Revised decision | Define strict `aep.production-persisted-request-binding/2`, a 40-field full binding, a manifest excluding only the computed digest, LF32-framed digest construction, exact full-string Redis equality, raw-first Lua handling, production rejection of v1, and no automatic migration/downgrade |
| Schemas/contracts examined | Binding/2 field table, safe descriptor, commitment construction, `Digest32`, binding manifest/digest, AAD copies, production/test compatibility text, current `PersistedRequestBinding`, `IntentRecord`, Lua CAS/preflight, and canonical binding tests |
| Repository invariants | Sole Redis authority and exact equality are preserved; identifier/digest representation compatibility is not frozen |
| Semantic invention still required | **Yes.** Stage 2 would have to decide how a production v2 binding coexists with the delivered intent model and Lua path without reinterpreting or weakening v1 |
| Provider-specific dependency | None for canonical binding semantics; registry mappings for provider keys remain later dependencies |
| Acceptance evidence | `PVK-CAN-005`/`006` cover version rejection and reconstruction directionally, but cannot cure the missing outer-intent compatibility contract |
| Residual limitation | Production migration remains correctly prohibited, but even new production intent creation lacks a compatible frozen outer record/version |

The v2 binding field set, canonical construction, digest framing, deadline order, exact parse/re-encode, constant-time digest comparison, production rejection of v1, and no-downgrade policy are substantially corrected. Redis is consistently the sole binding authority; AAD, selector, receipt, and envelope copies are authenticated evidence only.

The blocking compatibility defect is independent of provider choice:

1. Revised `CorrelationId` is `cor_` plus a 43-character base64url suffix, while delivered `IntentRecord` validates both `intent_id` and `correlation_id` as canonical UUIDv4 strings.
2. Revised `request_fingerprint` is `Digest32`, whose JSON representation is 43-character base64url. Delivered `IntentRecord.request_fingerprint`, `PersistedRequestBinding.request_fingerprint`, and the Lua creation equality use a 64-character lowercase hexadecimal digest.
3. Revised `execution_id`, `step_id`, and `intent_id` are described only as “registry opaque ID, 1..128 bytes.” `execution_id` and `intent_id` are canonical UUIDv4 values in the delivered tree; `step_id` uses the delivered bounded safe-ID alphabet. “Registry opaque ID” is not among the exact identifier profiles in Section 7.1.
4. Section 7.2 says production Lua requires the v2 literal, but it does not freeze a new versioned production intent-record schema, a structural production/test Lua split, or exact version-aware outer-field validation that preserves v1 unchanged.

As written, a literal implementation cannot insert the specified v2 correlation ID or fingerprint into the delivered `IntentRecord`, and changing the existing record/Lua semantics would affect the accepted v1 test composition. The correction must either preserve the delivered UUIDv4/hex outer encodings in v2 or define a separately versioned production intent record and exact structural/Lua dispatch with no v1 reinterpretation. Stage 2 may not choose that security/compatibility semantic itself.

## 7. `PVK-R-03` disposition

**Disposition: PARTIALLY RESOLVED — BLOCKING residual.**

| Required item | Independent result |
|---|---|
| Exact revised sections | 7.1-7.7, 7.8, 8.5-8.6, 15.1, 15.3, 19.1 |
| Original defect | AAD, context, envelope, digests, links, key/version identities, encodings, comparisons, and construction order lacked exact primitive and domain definitions |
| Revised decision | Freeze AES-256-GCM parameters, LF32, canonical base64url, timestamp/integer bounds, binding/AAD/context/metadata schemas, domain-separated hashes, lifecycle signatures, construction order, and a rewrap change allowlist |
| Schemas/contracts examined | Binding/2, AAD/2, KMS-context/1, metadata/1, LF/1, genesis/selector/anchor/reconciliation/hold/deletion/tombstone records, audit idempotency/event hash inputs, and Section 8.5 rewrap |
| Repository invariants | Creation-key and request facts remain immutable; wrapper revision is separate; exact Redis binding remains authoritative |
| Semantic invention still required | **Yes.** Several security-relevant lifecycle/audit hash values and one predecessor field do not have an exact construction |
| Provider-specific dependency | Concrete provider-native DEK-wrap algorithm, deterministic context mapping, immutable key-version behavior, and actual KMS enforcement |
| Acceptance evidence | CAN-002-004 and KMS-002/007/009 are now bounded correctly, but no vector can implement an undefined anchor/hold/receipt hash |
| Residual limitation | Application-contract tests cannot prove provider cryptography; additionally, the remaining hash omissions are design defects rather than provider dependencies |

The AEAD parameters are exact: 32-byte DEK, 12-byte nonce, 16-byte untruncated tag, ciphertext length equal to plaintext, one CSPRNG nonce for one DEK/encryption, and no universal uniqueness claim. Material checksum, AAD hash, context hash, wrapped-DEK hash, envelope hash, predecessor link, selector hash, genesis hash, and tombstone hash are domain separated and LF32 framed. Base64url, integer, timestamp, canonical-field, and constant-time-comparison rules are substantially exact. Confidentiality classifications are conservative.

The complete normal creation order has no cryptographic circle:

`request -> descriptor/fingerprint -> IDs/key resolution -> binding manifest/digest/full binding -> AAD/hash -> revision-1 context/hash -> DEK wrap + nonce + AEAD -> material/wrapper hashes + metadata -> LF/1 envelope/hash -> V1 -> genesis/selector/anchor L1 -> audit A1 -> Redis I1`.

Rewrap likewise can be acyclic: authenticate the selected revision, compute the prior envelope hash/link, build the new context, rewrap the same DEK, construct and verify a candidate, hash it, audit it, then CAS the selector. Section 8.5 correctly forbids changes to plaintext, material length, nonce, ciphertext, tag, AAD, material checksum, identity, creation key, fingerprint, binding digest, deadlines, and authoritative Redis binding.

Blocking omissions remain:

- `aep.vault-monotonic-anchor/1` carries a predecessor anchor hash, but no `AEP-...` domain or exact anchor-hash construction is defined. The anchor chain therefore cannot be implemented or independently vector-tested.
- Hold release binds a hold hash, yet no hold-hash construction is defined. Tombstones carry per-target receipt digests, and audit methods accept `event_hash`, but their exact domain/framing/hash inputs are not defined.
- The selector field is named `selected_envelope_predecessor_hash`, while the envelope and KMS context define `predecessor_link`. The text says the selector copies the selected envelope predecessor identity but never says whether that field is the prior envelope hash or the derived predecessor link. Those values are not interchangeable.
- Section 8.5 permits a “revision update time” to change, but the envelope metadata schema has no such field. The only defined update time is in the selector. The allowlist and schema must use one exact field name/location.

These are cryptographic and authenticated-lifecycle semantics. Stage 2 cannot invent labels or select between a predecessor hash and link.

## 8. `PVK-R-04` disposition

**Disposition: PARTIALLY RESOLVED — BLOCKING residual.**

| Required item | Independent result |
|---|---|
| Exact revised sections | 5.2-5.3, 6.3, 7.7-7.8, 8.2, 8.5, 9, 10.2-10.6, 14, 15.2-15.3, 19.1 |
| Original defect | Selector absence could mean revision 1; genesis, authentication, rollback anchor, CAS-loss acceptance, and historical-revision eligibility were undefined |
| Revised decision | Signed immutable genesis and selectors, pinned Ed25519 verification key, separate monotonic anchor, no absence default, distinct missing/rollback/conflict/unknown states, exact +1 CAS, deterministic lost-ack reconciliation, and non-dispatching historical reads |
| Schemas/contracts examined | Genesis/1, selector/1, anchor/1, selector reconciliation/1, lifecycle methods, selector state table, F08/F09/F15/F16/F27, STR-009/010, KMS-006/008 |
| Repository invariants | Lifecycle chooses an envelope only; it never replaces Redis binding authority or permits fallback |
| Semantic invention still required | **Yes.** The undefined anchor hash/chain and incomplete lifecycle receipt/result types prevent the frozen authority from being implemented exactly |
| Provider-specific dependency | Atomic/durable genesis+selector+anchor creation, monotonic CAS, isolation, retained generation reads, and rollback resistance for the selected lifecycle authority |
| Acceptance evidence | Contract and provider criteria are correctly separated; provider-neutral vectors still need the missing hash and exact result schemas |
| Residual limitation | A malicious lifecycle control plane remains outside the claim, correctly; ordinary rollback detection must nevertheless have a complete local contract |

The revision correctly states that selector absence never selects revision 1. `UNSUBMITTED_NEW`, genesis missing after creation evidence, selector missing, rollback, conflict, corruption, and unknown are distinct observations; each blocks dispatch and automatic older-revision selection. Selector authentication and anchor comparison occur before envelope routing. The pinned Ed25519 public key/digest, not a selector field, is the non-circular local trust anchor. L1 is an explicit durable boundary after V1. Lost selector-CAS acknowledgement accepts only exact proposed selector+anchor, exact old state with authoritative non-commit, or conflict/unknown. Old revisions remain exact-read recoverable only for explicit non-dispatch purposes and cannot regain eligibility by availability fallback.

The proposed authority is still a provider-neutral contract, not evidence of real atomicity, monotonic durability, or rollback resistance. The document correctly leaves those proofs to the provider stage. That dependency is acceptable. The blocking issue is that the contract itself references an undefined anchor hash and several undefined lifecycle result/receipt structures, so Stage 2 cannot implement the chain and reconciliation evidence without choosing authenticated bytes and semantics. This overlaps `PVK-R-03` and `PVK-R-05` but directly prevents full resolution of lifecycle authority.

## 9. `PVK-R-05` disposition

**Disposition: PARTIALLY RESOLVED — BLOCKING residual.**

| Required item | Independent result |
|---|---|
| Exact revised sections | 6.1-6.6, 7.1, 7.7, 8, 11.4, 12.2, 13, 15.2-15.5, 19.1 |
| Original defect | Named placeholder inputs/results, vague shared outcomes, absent audit-outbox contract, and unfrozen cancellation/idempotency/reconciliation semantics |
| Revised decision | Add common certainty/retry/ack/cancellation/quarantine/dispatch enums, method tables for store/lifecycle/facade/KMS/audit, exact-target reads/writes, idempotency/CAS rules, safe evidence, audit acceptance, and no Stage 2 activation port |
| Schemas/contracts examined | Every method in Sections 6.2-6.6, common result/error envelope, audit-event/1, audit idempotency and receipts, lifecycle and deletion methods, facade inputs/results, and no-activation rule |
| Repository invariants | No latest/adoption/fallback, unknown writes are not absence, provider exceptions stay inside adapters, audit unknown fails closed, activation remains absent |
| Semantic invention still required | **Yes.** Several inputs/results and audit/lifecycle values remain names without frozen field sets or authority effects, and the dispatch-read facade contradicts provenance issuance |
| Provider-specific dependency | Actual receipt meanings, durability classes, absence, conditional operations, provider version tokens, and KMS/store/audit behavior |
| Acceptance evidence | STR-004/005, WFL-011/012, and OPS-002/004 improve testability, but cannot instantiate undefined types |
| Residual limitation | Interface types alone will not prove provider behavior even after correction |

The revised common envelope is materially better. It distinguishes definite no change, conflict, commit, historical commit, unknown, and not-applicable; closes retry/cancellation classes; names acknowledgement and dispatch effects; prohibits raw SDK/exception leakage; forbids conflict adoption, blind repeat writes, latest-object reads, alias/default/alternate keys, and test fallback; and gives unknown audit acknowledgement fail-closed reconciliation. Stage 2 is expressly prohibited from exposing activation or connector mutation ports.

However, the facade's statement that its types are “fully structural, not placeholders” is not true:

- `DeletionEvaluationInput`, `AuthorizedDeletionInput`, `AuthenticatedLifecycleView`, `HoldApplyReceipt`, `HoldReleaseReceipt`, `DeletionDecisionReceipt`, `TombstoneReceipt`, `retention_state`, `durability_class`, `signature_evidence`, `provider_delete_token`, and several aggregate receipts have no exact field schemas.
- `inspect_selector_cas_exact` has decision/generation/hash inputs but no explicit locator/material target. A globally random decision ID is not a frozen immutable target contract.
- Hold/deletion records are described together in prose, but their exact schemas, reason enums, legal transitions, idempotency-key fields, and result receipts are not enumerated per operation.
- `aep.audit-event/1` names `event_type`, `operation_class`, `reason_code`, `duration bucket`, call-count vector, and receipt-reference pseudonyms without closing their enum/value schemas. `event_hash`, `outbox_version_token`, and the durability-class enum are also undefined.
- `read_authenticate_material` is said to execute the full 14-step order, whose step 14 issues `VerifiedDispatch`, but it returns `AuthenticatedMaterial` and says that value may “later feed provenance.” Those are different authority boundaries. The design must decide whether the facade atomically returns provenance after audit or returns protected material to a separate issuer, and must freeze the no-repeat rule for a historical `dispatch.eligible` audit after a crash.

The last point is security-significant. F24 says a post-P1/pre-connector crash can never recreate provenance, but no interface or persisted/audit acknowledgement rule states whether a historical dispatch-audit receipt may authorize another issuance. Stage 2 must not invent that one-use semantic.

## 10. `PVK-R-06` disposition

**Disposition: PARTIALLY RESOLVED — MAJOR residual.**

| Required item | Independent result |
|---|---|
| Exact revised sections | 6.3-6.4, 7.7-7.8, 8.2-8.3, 14.1, 15.1-15.4, 19.1 |
| Original defect | Unauthenticated selector data could route an envelope and unauthenticated orphan AAD could derive Redis identity/classification |
| Revised decision | Freeze a 14-step order: bounded hints; genesis; selector structure; selector signature+anchor; exact selected identity; immutable read; envelope validation; AAD/context; exact unwrap; AEAD; reconstruction; raw Redis/equality; endpoint/deadline; audit then provenance |
| Schemas/contracts examined | Section 7.8 order, active selector reads, ExpectedMaterialRead, read/authenticate facade, orphan classification, F15-F23/F31, CAN-006/STR-009/WFL-008 |
| Repository invariants | Raw Redis precedes Redis semantics; cryptographic reconstruction and exact equality precede authority; all rejects produce `C0` |
| Semantic invention still required | Not for selector/orphan routing itself; **yes** for the conflicting facade/provenance boundary and exact treatment of a historical dispatch audit |
| Provider-specific dependency | Exact authenticated lifecycle reads, immutable object reads, KMS enforcement, and optional authenticated orphan index/receipt |
| Acceptance evidence | WFL-008 correctly distinguishes unauthenticated candidate hints from authenticated classifications; call-spy evidence can prove the contract only |
| Residual limitation | Dependency loss intentionally reduces availability and deletion progress |

The original routing defects are corrected in the normative order: an unauthenticated selector cannot authorize an envelope read, and unauthenticated inventory/header/AAD data remains only `CANDIDATE` or `UNKNOWN`. It cannot derive a Redis key, classify binding/conflict/integrity, authorize quarantine/deletion, or dispatch. Exact genesis/selector/anchor authentication precedes selected-envelope identity and the immutable read. Exact key-version unwrap, AEAD, binding reconstruction, raw Redis validation, authoritative equality, profile/deadline revalidation, and one-use issuance are ordered correctly. Every rejection/unknown produces zero connector mutation calls.

The disposition is not fully resolved because Section 6.4 says the facade executes all 14 steps but returns material for later provenance, whereas step 14 already includes issuance. That cross-section contradiction requires implementation judgment about where authority is created and whether a repeat invocation after a crash is allowed. The order must be made implementable by one exact typed boundary. Genesis is signed and selector-bound, but the ordered list should also explicitly say where the genesis signature/schema/hash is verified rather than relying on the surrounding lifecycle section.

## 11. `PVK-R-07` disposition

**Disposition: PARTIALLY RESOLVED — MAJOR residual.**

| Required item | Independent result |
|---|---|
| Exact revised sections | 5.3, 6.1, 6.6, 8-10, 13, 14.3, 15.4, 19.1 |
| Original defect | Failure rows lacked phase placement, historical/new acknowledgements, exact dependency counters, audit loss, selector cases, and complete crash/reconciliation behavior |
| Revised decision | Split pre-V1, V1/pre-I1, I1/pre-transport, post-provenance, transport-unknown, and lifecycle phases; define O/K/L/R/W/A/C and V/L/A/I/P; add F01-F32 |
| Schemas/contracts examined | Every F01-F32 row, common outcome mapping, audit operation table, lifecycle state machine, WFL-001/003/011, KMS-006, and delivered runner/recovery ordering |
| Repository invariants | No pre-transport connector call, no automatic replay, and provider recovery remains read-only are preserved |
| Semantic invention still required | Matrix contradictions can mostly be corrected from Sections 6/8, but the historical dispatch-audit/provenance rule remains a blocking interface issue recorded under `PVK-R-05` |
| Provider-specific dependency | Real fault injection, receipt truth, authoritative absence, KMS and lifecycle outcomes, audit durability, retention/deletion behavior |
| Acceptance evidence | The matrix is much more observable, but its current counter vectors cannot be accepted as golden evidence |
| Residual limitation | External transport outcome remains deliberately ambiguous and unreplayable |

The matrix now covers lost create acknowledgement, audit acknowledgement loss, genesis/selector loss, rollback/replay, unknown selector CAS, envelope limits/codecs, crashes at named durable boundaries, post-provenance failure, unknown transport outcome, rewrap, holds, and deletion. Historical acknowledgements are usually retained rather than incorrectly reset. Recovery never invokes the connector or replays a mutation.

Material inconsistencies remain:

| Rows/sections | Independent inconsistency |
|---|---|
| F02 versus F18 | F02 combines local pre-crypto caller input with malformed “persisted evidence” while retaining `O0/L0`; a persisted envelope cannot be examined without lifecycle/object reads. F18 separately covers that persisted phase. The cases must be split. |
| F05 | One injected “definite reject” yields either `DEFINITE_NO_CHANGE` or `DEFINITE_CONFLICT`; the precondition does not identify which. Golden evidence needs separate rows. |
| F15 | Genesis missing and selector missing are combined with `L2`, even though exact ordered reads stop at different call counts. The row also maps selector loss to `SELECTOR_CONFLICT` despite defining a distinct `SELECTOR_MISSING` observation. |
| F18-F22 versus Sections 6.6/13 | These rows use `A0`, while Section 13 requires exact read, KMS, integrity/quarantine, and dispatch-boundary events and says security-critical boundaries require durable acceptance. The design must state whether failure events are mandatory/gating/best-effort and count them consistently. |
| F26 versus Section 8.5 | `O2(create+read) K1` omits the selected source-envelope read/authentication and candidate KMS/AEAD verification required by the flow. A full rewrap path needs explicitly counted source read/unwrap, rewrap, candidate create/read, and candidate unwrap/verification calls or an exact precondition that makes them historical. |
| F28 and F32a | Hold/release/selector/deletion-decision CAS rows use `A0`, but Section 6.6 requires a durable `.authorized` audit before each CAS. |
| F32b | A crash after exact delete submission uses `A0`, although the pre-delete authorization audit is required before submission; that acknowledgement must be stated as historical or newly obtained. |
| F24 and Section 7.8 | F24 forbids provenance recreation, but the audit/idempotency and facade contracts do not specify how restart distinguishes “audit accepted before issuance” from “issuance occurred.” |

These are material specification contradictions, not provider measurements. They prevent the matrix from serving as exact contract-test or crash-oracle evidence.

## 12. `PVK-R-08` disposition

**Disposition: PARTIALLY RESOLVED — MAJOR residual.**

| Required item | Independent result |
|---|---|
| Exact revised sections | 15-16 and 19.1 |
| Original defect | Criteria mixed contract/provider/operational/review evidence, used universal language, and lacked precise fault/counter/acknowledgement boundaries |
| Revised decision | Assign one of four stages to each criterion, add precondition/action, observations, counters/acknowledgements/dispatch, permitted evidence, and excluded claims |
| Schemas/contracts examined | All 47 `PVK-*` rows and the Section 15 default/import rules |
| Repository invariants | Mocks/emulators are correctly limited to application-contract claims; provider and production claims stay separate |
| Semantic invention still required | Criteria do not define production semantics, but incomplete vectors would force test authors to choose expected calls/acknowledgements |
| Provider-specific dependency | The five `PROVIDER` criteria and later operational/independent evidence remain open by design |
| Acceptance evidence | Parser confirmed 47 unique IDs and exactly one valid stage label each |
| Residual limitation | Criteria are future specifications, not passing evidence |

The stage-label correction is genuine: 38 criteria are `CONTRACT`, 5 are `PROVIDER`, 1 is `OPERATIONAL`, and 3 are `INDEPENDENT_REVIEW`; no criterion has an invalid or duplicate label. Universal nonce uniqueness, universal non-disclosure, provider truth from mocks, and exactly-once claims are excluded correctly.

The content requirement is not fully met. The Section 15 blanket default is useful only for genuinely local pre-durability cases. Several nonlocal rows still use phrases such as “exact failing counter from phase,” “phase counters asserted,” “exact path counters,” “one KMS target only,” or only `C0`, without a complete O/K/L/R/W/A/C vector and historical/new V/L/A/I/P state. Examples include PVK-CAN-005, STR-002, STR-004, STR-008, KMS-001, KMS-003-005, KMS-007-008, WFL-004-006, and OPS-005-008. Some refer to matrix rows whose counters are themselves inconsistent, particularly KMS-006/WFL-003/WFL-011.

Every criterion must either state a complete vector and acknowledgement history, state `N/A` with a reason for a non-runtime review/policy check, or import one exact corrected matrix row. “Exact counters asserted” is not an expected result. Until corrected, the criteria cannot be an objective acceptance oracle even though their evidence-stage boundaries are substantially improved.

## 13. `PVK-R-09` disposition

**Disposition: PARTIALLY RESOLVED — MINOR residual, plus the blocking AEP identifier conflict recorded under `PVK-R-02`.**

| Required item | Independent result |
|---|---|
| Exact revised sections | 6.1, 7.1-7.2, 7.7, 13, 15.5, 19.1 |
| Original defect | Safe identifiers lacked exact alphabets, byte bounds, provenance, pseudonymization, business-meaning rules, and cardinality controls |
| Revised decision | Define random/registry/HMAC identifier profiles, exact prefixes and lengths, business-meaning prohibition, omitted/rejected unsafe values, no metric labels, and typed event prohibitions |
| Schemas/contracts examined | Entire Section 7.1 identifier table, HMAC labels, binding identifiers, lifecycle/audit IDs, SafeOperationEvidence, audit-event/1, and OPS-005/006 |
| Repository invariants | Typed reductions and no raw provider/request/exception output remain compatible |
| Semantic invention still required | Bounded clarification remains for a few HMAC inputs and receipt-reference/event pseudonyms; the v2 correlation/intent conflict is separately blocking |
| Provider-specific dependency | Registry mapping, pseudonymization-key operation/lifecycle, and safe reduction of provider IDs |
| Acceptance evidence | OPS-005/006 correctly scope marker and metric evidence to bounded reviewed outputs |
| Residual limitation | Syntactic safety is correctly not equated with semantic non-sensitivity |

The revision now explicitly defines UTF-8/ASCII alphabets, prefix/length rules, CSPRNG provenance, registry aliases, business-meaning prohibitions, collection cardinalities, omission/rejection of unsafe/unknown values, and metric-label exclusions. Provider version tokens and artifact hashes cannot become labels. Typed events cannot contain raw request, crypto, provider, Redis, dispatch, exception, or trace objects. These are strong corrections.

Remaining bounded clarifications are:

- the raw external approval/ticket ID input to HMAC has no byte/string encoding, normalization, or maximum input bound;
- the provider-request pseudonym and locator-audit pseudonym name domain labels but do not freeze the complete LF32 input tuple and raw-provider-ID encoding;
- receipt-reference pseudonyms, safe operation pseudonyms, `operation_class`, `reason_code`, and duration-bucket values used by events are not separately defined; and
- `execution_id`, `step_id`, and `intent_id` use the undefined “registry opaque ID” description, while the delivered AEP has exact UUIDv4/safe-ID rules.

The first three are bounded corrections and are `MINOR` on their own. The last participates in the blocking v2/delivered-intent compatibility defect and must be corrected there.

## 14. `PVK-R-10` disposition

**Disposition: RESOLVED.**

| Required item | Independent result |
|---|---|
| Exact revised sections | 1, 2, 16, 18, 19.1, 20-22 |
| Original defect | The design did not expressly preserve AEP as the primary research contribution and could be read as reframing the paper around cloud/KMS infrastructure |
| Revised decision | Include the required sentence verbatim; label the boundary supporting infrastructure; reserve provider experiments as future work; reject cloud/KMS novelty and exactly-once claims |
| Schemas/contracts examined | Research/evidence claim boundary rather than a runtime schema |
| Repository invariants | Matches the delivered AEP guarantee and historical non-goals |
| Semantic invention still required | No |
| Provider-specific dependency | Future experiments only |
| Acceptance evidence | Exact UTF-8 sentence presence was programmatically confirmed; Sections 16/18 contain the required exclusions |
| Residual limitation | No research result has yet been measured, which is correctly stated |

No paper reframing, fabricated measurement, or exactly-once external-effect claim was found.

## 15. Cross-section consistency and regression assessment

| Cross-section subject | Consistent decisions | Contradiction or residual |
|---|---|---|
| V1/L1/A1/I1/P1 | Sections 5.3, 8.1, 8.3, and 9 consistently order `V1 -> L1 -> A1 -> I1 -> P1 -> at most one connector call` | Failure rows omit required audit calls/acks at several lifecycle boundaries |
| Authoritative binding | Sections 3, 4.2, 7.2, 7.4, and 7.8 consistently make Redis the sole authority | V2 identifier/fingerprint encodings do not fit the delivered outer intent record; bridge/version split absent |
| Selector/anchor authority | No absence default, pinned key, selector+anchor before envelope, no automatic older revision | Anchor hash is undefined; selector predecessor “hash” conflicts with envelope predecessor “link” |
| Acknowledgement meanings | Common enums distinguish none/new/historical/unknown; V/L/A/I/P are separately named | Matrix A counters contradict audit gating; F24 historical audit/provenance treatment is not frozen |
| Retry rules | Unknown writes reconcile exact target; no blind create/CAS/delete or provider mutation replay | F05 and several criteria do not name one exact result/vector; facade repeat/provenance rule remains open |
| Dispatch eligibility | Missing/corrupt/rollback/unknown/expired/hold/deletion are ineligible; no historical fallback | `read_authenticate_material` both executes issuance and returns material to feed later issuance |
| Expiry and holds | Expiry is monotonic; hold only extends retention and never restores dispatch | Hold schemas/results and audit counters remain incomplete |
| Deletion eligibility | Exact reference checks, two observations, grace, no hold, signed decision, audit, exact deletes, tombstone | Deletion input/receipt/reason schemas and some crash/audit histories are placeholders/inconsistent |
| Rewrap | Candidate is immutable/unselected until verified audit+CAS; plaintext/nonce/ciphertext/tag/AAD/binding stay fixed | Rewrap counters omit required calls; predecessor field and “revision update time” are inconsistent |
| Audit gating | Unknown acknowledgement fails closed; audit never replaces primary authority | Exact event/reason/hash/durability schemas are incomplete; failure matrix often says `A0` where audit is required |
| Provider-neutral claims | Provider behavior is consistently reserved for future exact-environment evidence | No provider claim regression found |
| Test-backend exclusion | Future production artifact must structurally exclude test backends and activation | Correctly remains unimplemented; current `pyproject.toml` still packages all `src*` |

No source regression was introduced because the correction changed design text only. The revised design also does not deliberately authorize a second provider call, fallback, or alternate binding authority. Compatibility is nevertheless only partial: implementing the v2 identifier/digest choices literally would conflict with the delivered intent model, and the audit/facade/lifecycle contradictions require implementation judgment. That is not enough evidence to classify `REGRESSION DETECTED`, because no implementation change occurred and a compatible correction remains possible; it is enough to withhold `VERIFIED`.

## 16. Remaining provider and operational dependencies

Even after the document defects are corrected, the following remain outside provider-neutral Stage 2 and cannot be passed by mocks or emulators:

- conditional-create and lifecycle-CAS linearization, exact immutable-version reads, checksums/version tokens, authoritative absence, response-loss reconciliation, and the fault domain represented by a durable receipt;
- lifecycle genesis/selector/anchor atomicity, isolation, retained generation evidence, monotonicity, rollback resistance, backup/restore behavior, and control-plane compromise assumptions;
- a concrete immutable KMS/HSM key-version and provider-native wrap algorithm compatible with the frozen enum, deterministic full-context mapping, context limits/enforcement, key lifecycle, rewrap, IAM, throttling, outage, and receipt semantics;
- audit-outbox conditional append, authoritative inspection, durability, downstream delivery, ordering, retention, backup, and operational alert behavior;
- exact account/project/subscription, namespace, region, identity, registry, key, audit, and pseudonymization-key configuration;
- retention, legal hold, deletion, tombstones, replica/snapshot/backup purge, key retirement/destruction, and precise deletion-claim evidence;
- time/skew/deadline/grace/retry/circuit parameters, RPO/RTO/SLO measurement, incident response, dual control, owner/runbook evidence, and change/rollback procedures;
- a structurally separated production artifact and independently reviewed provider adapters; and
- later, separate connector/profile/credential/response schemas and a separately designed activation authorization boundary.

These dependencies do not justify weakening a frozen interface. A provider or operational design that cannot meet the corrected contract must be rejected.

## 17. Findings and required corrections

| ID | Severity | Finding | Required correction before Stage 2 |
|---|---|---|---|
| PVK-RR-01 | **BLOCKING** | Production binding v2 uses correlation/intent/fingerprint representations that cannot be stored by the delivered UUIDv4/hex `IntentRecord` and Lua equality path; several IDs are only “registry opaque.” | Preserve delivered outer encodings or freeze a separately versioned production intent schema, exact production/test structural split, version-aware raw/Lua validation, and no-v1-reinterpretation bridge. Define exact execution/step/intent types. |
| PVK-RR-02 | **BLOCKING** | Anchor, hold, receipt/audit hashes and selector predecessor linkage are not completely defined; rewrap names an absent revision-update field. | Define every domain label, LF32 input, canonical bytes, comparison, and field name. Define anchor/hold/receipt/event hashes and make selector predecessor linkage exactly equal to one named envelope field. Align the rewrap allowlist with actual schemas. |
| PVK-RR-03 | **BLOCKING** | Lifecycle/deletion/facade/audit contracts still contain placeholder result/input types, and dispatch material/provenance issuance plus historical dispatch-audit behavior is contradictory. | Expand every named type to exact fields/bounds/immutable target/idempotency/result semantics; close audit enums/hashes/durability tokens; define one typed audit-to-provenance boundary and an exact no-repeat/crash rule. |
| PVK-RR-04 | **MAJOR** | Failure matrix rows conflate phases or contradict audit/rewrap requirements and exact counters. | Split F02, F05, and F15; correct F18-F22, F26, F28, and F32 acknowledgement/counter histories; make F24 follow the corrected provenance contract; recheck every row against Sections 6-9. |
| PVK-RR-05 | **MAJOR** | Although every PVK criterion has one evidence-stage label, many criteria still lack exact vectors and historical/new acknowledgement outcomes or import inconsistent matrix rows. | Give each criterion a complete vector/history/dispatch result, a corrected exact matrix reference, or explicit `N/A` for non-runtime evidence. Remove “exact counters asserted/from phase” placeholders. |
| PVK-RR-06 | **MINOR** | Some pseudonym inputs and event-safe identifiers remain underdefined. | Freeze raw external/provider ID byte encoding and bounds, full LF32 tuples, receipt-reference/operation pseudonyms, and all event enums/buckets. Keep unsafe/unknown values omitted or rejected. |

PVK-RR-01 through PVK-RR-03 require Stage 2 to invent or choose security/consistency semantics and are therefore `BLOCKING`. PVK-RR-04 and PVK-RR-05 are material internal contradictions/incompleteness and are `MAJOR`. Another revision of `docs/15` and another independent rereview are required.

## 18. Verified and unverified guarantees

| Guarantee | Status | Exact boundary |
|---|---|---|
| All 22 revised sections and reported `docs/15` hash | **VERIFIED** | Current file bytes |
| Reported source/tests, configuration, and all-other manifests | **VERIFIED** | Current selections and recorded algorithm |
| Historical proof that only `docs/15` changed | **PARTIALLY VERIFIED** | Matching current/recorded manifests and protected hashes; no usable Git history |
| Delivered canonical binding/raw-state/provenance/recovery baseline | **VERIFIED from latest delivered-tree evidence; not rerun here** | Repository-defined test-only mutation composition, recorded `611 passed` |
| LF/1 framing and size model | **VERIFIED as a design contract** | `PVK-R-01`; no implementation/provider evidence |
| Research-primary-contribution boundary | **VERIFIED** | `PVK-R-10` |
| Production v2 binding compatibility with delivered intent state | **NOT VERIFIED** | Blocking encoding/version bridge defect |
| Complete AAD/context/envelope/lifecycle hash graph | **NOT VERIFIED** | Missing anchor/hold/receipt/event constructions and predecessor mismatch |
| Complete store/lifecycle/KMS/facade/audit interfaces | **NOT VERIFIED** | Placeholder types and provenance/audit contradictions |
| Exact failure matrix and acceptance oracle | **NOT VERIFIED** | Major counter/acknowledgement gaps |
| Real object-store/lifecycle/KMS/audit durability or consistency | **NOT VERIFIED** | No provider evidence |
| Production IAM, retention, deletion, backup, incident, RPO/RTO/SLO | **NOT VERIFIED** | No operational evidence |
| Production build structurally excludes test vault/fake/mock | **NOT IMPLEMENTED / NOT VERIFIED** | Current package includes all `src*` and the test vault class |
| Durable production vault/KMS | **NOT IMPLEMENTED** | Design only |
| Production connector/profile/credentials/response safety | **ABSENT / NOT VERIFIED** | Separate later gate |
| Exactly-once external effects, cross-system atomicity, split-brain prevention, guaranteed duplicate prevention | **NOT CLAIMED / NOT VERIFIED** | Explicit non-goals |
| Universal secret non-disclosure, physical deletion, or managed-memory erasure | **NOT CLAIMED / NOT VERIFIED** | Bounded typed/source/schema evidence only |

## 19. Stage 2 authorization boundary

**Ready to begin bounded provider-neutral interface implementation: NO-GO.**

The authorization conditions are not met: only `PVK-R-01` and `PVK-R-10` are fully resolved; blocking and major findings remain; an implementation would have to choose v2/delivered-intent compatibility, lifecycle/audit hash bytes, interface fields, and provenance/audit crash semantics. That would be silent design work, not mechanical implementation of frozen contracts.

Accordingly, this rereview authorizes none of the following:

- provider-neutral interfaces, schema/codecs, typed result/error implementation, or composition refactoring;
- deterministic contract backends or new contract tests;
- a provider, SDK, account, object store, KMS/HSM, lifecycle authority, audit outbox, retention system, or provider adapter;
- a production connector, endpoint profile, credential loader, deployment, or external mutation;
- an activation schema, parser, method, capability, feature flag, or production dispatch path.

A future `GO`, if earned after correction and independent rereview, may authorize only provider-neutral interfaces, exact schemas/canonical codecs, typed results/errors, structural production/test separation, and continued structural absence of activation and connector mutation ports. It would not establish provider or production readiness.

## 20. Final classifications and recommendation

### 20.1 Finding dispositions

| Finding | Disposition | Remaining severity |
|---|---|---|
| `PVK-R-01` | **RESOLVED** | None |
| `PVK-R-02` | **PARTIALLY RESOLVED** | **BLOCKING** |
| `PVK-R-03` | **PARTIALLY RESOLVED** | **BLOCKING** |
| `PVK-R-04` | **PARTIALLY RESOLVED** | **BLOCKING** |
| `PVK-R-05` | **PARTIALLY RESOLVED** | **BLOCKING** |
| `PVK-R-06` | **PARTIALLY RESOLVED** | **MAJOR** |
| `PVK-R-07` | **PARTIALLY RESOLVED** | **MAJOR** |
| `PVK-R-08` | **PARTIALLY RESOLVED** | **MAJOR** |
| `PVK-R-09` | **PARTIALLY RESOLVED** | **MINOR**, with identifier compatibility also covered by blocking `PVK-RR-01` |
| `PVK-R-10` | **RESOLVED** | None |

### 20.2 Gate classifications

| Classification | Decision | Reason |
|---|---|---|
| Provider-neutral design | **REQUIRES REVISION** | Blocking binding, hash/lifecycle, interface/audit, and provenance semantics remain |
| Design completeness | **NOT VERIFIED** | Stage 2 could not implement the document without making security and consistency decisions |
| Compatibility with Agent Execution Protocol | **PARTIALLY VERIFIED** | Core order, authority, no-replay, and fail-closed intent remain; v2 outer-state compatibility and facade/audit semantics are unresolved; no source regression occurred |
| Ready to begin bounded provider-neutral interface implementation | **NO-GO** | Stage 2 entry conditions are not satisfied |
| Durable production vault/KMS implemented | **NO** | Design only |
| Provider-specific durability verified | **NO** | No provider evidence |
| Production applicability | **NO-GO** | Implementation, provider, operational, connector, and activation gates remain absent |
| First production connector implementation | **NO-GO** | Production vault/KMS prerequisite has not passed |
| Production non-idempotent dispatch | **NO-GO** | Must remain disabled |

Recommendation: revise only `docs/15` in a separately authorized correction stage, address PVK-RR-01 through PVK-RR-06, and submit the resulting document to another independent read-only rereview. Do not begin Stage 2, provider selection, connector work, activation design, deployment, or production dispatch on the basis of this revision.

“Ambiguity, corruption, and contention are detectable; the system fails closed.”
