# Independent rereview of the second production vault/KMS design revision

Date: 2026-08-01

## 1. Rereview purpose and evidence boundary

This is an independent, read-only rereview of the second revision of `docs/15-production-vault-kms-design.md`. The controlling prior reviews are `docs/16-production-vault-kms-design-review.md` and `docs/17-production-vault-kms-design-rereview.md`. The purpose is to decide whether the second revision genuinely resolves `PVK-RR-01` through `PVK-RR-06`, and whether previously resolved `PVK-R-01` and `PVK-R-10` remain resolved.

The revised document's correction-trace table, counts, and self-classification were treated as claims to test, not as evidence. I reconstructed the delivered Agent Execution Protocol (AEP), production schemas, hash graph, interface shapes, failure rows, acceptance oracles, and privacy boundary directly from the current tree.

At entry, the required classifications were retained:

| Classification | Rereview-entry value |
|---|---|
| Provider-neutral design | `REQUIRES INDEPENDENT REREVIEW` |
| Design completeness | `NOT VERIFIED` |
| AEP compatibility | `PARTIALLY VERIFIED` |
| Ready for bounded provider-neutral implementation | `NO-GO — pending independent rereview` |
| Durable production vault/KMS implemented | `NO` |
| Provider-specific durability verified | `NO` |
| Production applicability | `NO-GO` |
| First production connector | `NO-GO` |
| Production non-idempotent dispatch | `NO-GO` |

Evidence inspected included all required documents from `docs/06-phase2-design.md` through `docs/17-production-vault-kms-design-rereview.md`, the relevant delivered-tree addenda in `phase2_implementation_report.md`, and relevant canonicalization, request-binding, intent, state-codec, vault, workflow, recovery, dispatch, durability, safe-value, configuration, and test files. In particular, the source trace covered `src/core/request_binding.py`, `src/core/intents.py`, `src/core/intent_workflow.py`, `src/core/intent_recovery.py`, the request-vault and connector boundaries, configuration composition, and the corresponding tests.

Historical findings in `docs/07`, `docs/09`, `docs/10`, `docs/11`, and `docs/13` that report repository gaps as open or partial are superseded, for the current delivered tree, by the verified closures in `docs/12`, `docs/14`, the final 2026-07-31 implementation-report addendum, and direct source inspection. That later evidence closes repository-scoped raw-state, binding, provenance, recovery, and mutation-scope findings. It does not establish a production vault, provider durability, or production dispatch. Repository closure is not production closure.

This rereview did not modify `docs/15`, `docs/16`, `docs/17`, source, tests, configuration, or reports. It did not select or access a provider, install an SDK, create a schema or adapter, create a connector or activation mechanism, or issue a provider mutation. This report is the only created artifact.

## 2. Repository and revision-integrity verification

### 2.1 Section, row, and criterion inventory

The second revision contains 84 Markdown headings and exactly 22 numbered level-2 sections. Sections 1 through 22 each occur once and are in numeric order. Their titles are:

1. Purpose and current baseline.
2. Scope and exclusions.
3. Existing repository invariants.
4. Threat and trust-boundary model.
5. Provider-neutral component architecture.
6. Interface contracts.
7. Envelope and authenticated-metadata schema.
8. Write, read, dispatch, rotation, rewrap, retention, and deletion flows.
9. Lifecycle state machine.
10. Crash and partial-failure matrix.
11. Key lifecycle and authorization model.
12. Configuration and startup gates.
13. Safe telemetry and audit evidence.
14. Orphan reconciliation and recovery.
15. Provider-neutral acceptance criteria.
16. Future provider-specific test plan.
17. Provider mapping table.
18. Research evaluation plan.
19. Traceability matrix from review findings and prior residual limitations.
20. Open decisions and residual risks.
21. Implementation sequencing.
22. Final GO/NO-GO classifications.

The Section 10 inventory has exactly 53 physical failure rows and 53 unique IDs. Every row has the three intended Markdown cells and four pipe delimiters. The IDs are:

`F01`, `F02a`, `F02a2`, `F03`, `F04`, `F05a`, `F05b`, `F06`, `F07`, `F08`, `F09`, `F10`, `F11`, `F12a`, `F12b`, `F13`, `F14a`, `F14b`, `F02b`, `F15a`, `F15b`, `F16a`, `F16b`, `F17a`, `F17b`, `F18`, `F19`, `F20a`, `F20b`, `F21`, `F22a`, `F22b`, `F22c`, `F22d`, `F23`, `F24a`, `F24b`, `F25`, `F26`, `F27`, `F28a`, `F28b`, `F29a`, `F29b`, `F30`, `F31`, `F32a-S`, `F32a-H`, `F32a-R`, `F32a-D`, `F32b`, `F32c`, and `F32d`.

That proves row existence, uniqueness, and table shape. It does not prove semantic completeness. Section 8 below identifies omitted current-invocation receipts, incorrect audit counts, and combined failure classes. Therefore the reported 53-row *uniqueness* result is correct, but the stronger semantic-completeness result is not.

Section 15 has exactly 62 physical criteria and 62 unique IDs. Each has exactly one evidence-stage label. The independently recalculated distribution is:

| Evidence stage | Count |
|---|---:|
| `CONTRACT` | 45 |
| `PROVIDER` | 13 |
| `OPERATIONAL` | 1 |
| `INDEPENDENT_REVIEW` | 3 |
| Total | 62 |

The oracle-form inventory is 36 counter-vector forms, 22 exact Section 10 row references, and four explicit non-runtime `N/A` forms. The 36 includes `PVK-STR-002`, whose `O=N` is exact only because `N` is fixed before the case. No prohibited vague phrase such as “exact counters asserted,” “phase counters asserted,” “exact path counters,” “exact failing counter from phase,” or “one KMS target only” occurs. As with the matrix, syntactic form does not establish oracle validity; Section 9 records invalid imports and incomplete observations.

Six physical second-correction trace rows, one for each `PVK-RR-01` through `PVK-RR-06`, exist. Five are valid eight-column Markdown rows. The `PVK-RR-04` row has 11 pipe delimiters rather than nine because the literal `GATING_DURABLE|MANDATORY_BEST_EFFORT|OMITTED_BY_DESIGN` is not escaped; it therefore renders as extra columns. This is a `DOCUMENTATION` defect in traceability, not proof against or for the underlying contract.

The production binding table independently contains 40 required fields.

### 2.2 Hashes, line endings, and manifests

For each manifest, the reconstruction emitted `repository-relative POSIX path<TAB>lowercase file SHA-256`, sorted rows by relative path, joined them with LF and no final LF, UTF-8 encoded that manifest, and SHA-256 hashed it.

| Evidence | Expected | Observed | Result |
|---|---|---|---|
| Final `docs/15` SHA-256 | `75f11142c61a8bfc7c907450be86cdccd8fe486606276610e5b46a56edea318d` | Same | Match |
| Unchanged `docs/17` SHA-256 | `531d00f51c1826d4e59feb22dee1ef3c24a2511d11d85234e9f4d116985966e3` | Same | Match |
| Source/tests manifest | `b3d60014240692936afdaf2b37be0ea51fe9e327a6c06a0a8013c40e96d5bb8a` | Same; 88 files | Match |
| Configuration manifest | `eaef6ce9bbe12f4c8b766489d976886433ec43ff4d89a7923e32894189fd4e63` | Same; 3 files | Match |
| All-other-files manifest | `d347849318e5999341de3a745feee5a436dba7fb12fd47bba15028f1402c7db4` | Same; 92 files | Match |

The source/tests selection includes all files under `src` and `tests`, including the existing bytecode files. Configuration is exactly `pyproject.toml`, `compose.phase2.yml`, and `redis/phase2.conf`. The all-other selection excludes `.git`, `.pytest_cache`, `__pycache__`, `docs/15`, `docs/17`, and this authorized `docs/18` output.

`docs/15` is 231,871 bytes, contains 1,265 LF bytes, and contains zero CR bytes. The reported LF-only result is correct. `docs/17` is 60,494 bytes, contains 547 LF bytes, and contains zero CR bytes.

### 2.3 Git metadata and exact command record

Git metadata is not usable. `.git` exists but has zero entries. The native Git exit code was independently captured as `128` for status, repository-root discovery, and log discovery; Git reported that the directory is not a repository. No Git history or historical changed-file state is claimed.

The decisive manifest command was:

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
$excluded=@((Join-Path $repo 'docs\15-production-vault-kms-design.md'),(Join-Path $repo 'docs\17-production-vault-kms-design-rereview.md'),(Join-Path $repo 'docs\18-production-vault-kms-design-rereview.md'))
$allOther=Manifest @(Get-ChildItem -Recurse -File -Force|Where-Object{$_.FullName -notmatch '[\\/](?:\.git|\.pytest_cache|__pycache__)[\\/]' -and $_.FullName -notin $excluded})
```

It exited `0` and produced the three counts and hashes above. The exact hash/line-ending command was:

```powershell
$ErrorActionPreference='Stop'
foreach($p in @('docs/15-production-vault-kms-design.md','docs/17-production-vault-kms-design-rereview.md')){
  $bytes=[IO.File]::ReadAllBytes((Resolve-Path $p)); $cr=0; $lf=0
  foreach($b in $bytes){if($b -eq 13){$cr++};if($b -eq 10){$lf++}}
  $hash=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
  "$p|sha256=$hash|bytes=$($bytes.Length)|CR=$cr|LF=$lf"
}
```

It exited `0` and produced the byte, CR, LF, and hash values above.

Other decisive commands and exit codes were:

| Exact command or command family | Exit | Genuine result |
|---|---:|---|
| `Get-ChildItem -Recurse -Force -Filter AGENTS.md` | 0 | No `AGENTS.md` found |
| `rg -n '^#{1,6} ' docs/15-production-vault-kms-design.md` plus the UTF-8 heading parser | 0 | 84 headings; 22 numbered sections; order 1 through 22 |
| UTF-8 Section 10 physical-row parser matching `^\| F...` | 0 | 53 rows; 53 unique; four pipe delimiters per row |
| UTF-8 Section 15 physical-row/stage/oracle parser | 0 | 62 rows; 62 unique; stage and form counts above |
| `rg -n "exact counters asserted|phase counters asserted|exact path counters|exact failing counter from phase|one KMS target only" docs/15-production-vault-kms-design.md` | 1 | No prohibited phrase; exit 1 means no match |
| `rg -n "aep\.production-vault-envelope-lf/1|aep\.production-persisted-request-binding/2|aep\.production-intent-record/1|aep\.vault-lifecycle-genesis/1|create_genesis_and_selector_once|compare_and_advance_selector" src tests pyproject.toml compose.phase2.yml redis/phase2.conf` | 1 | No production schema/interface implementation; exit 1 means no match |
| `git status --short --branch` | 128 | Not a Git repository |
| `git rev-parse --show-toplevel` | 128 | Not a Git repository |
| `git log --oneline -n 1` | 128 | Not a Git repository |
| `Get-ChildItem -Force -LiteralPath .git` | 0 | Zero entries |
| Numbered UTF-8 reads of required documents, report ranges, source, configuration, and relevant tests | 0 | Evidence inspected without mutation |

### 2.4 Tests

No test command was run during this rereview. The genuine recorded baseline remains the integration-enabled suite at exit `0`, `611 passed in 48.08s`, with zero failures and zero skips, at the end of `phase2_implementation_report.md`. `docs/16` also records a separate earlier `611 passed in 38.79s` run. Neither result tests the new production contracts because those contracts are not implemented. This report does not claim that `611 passed` was rerun.

## 3. Research-topic alignment

Section 18 contains the required sentence exactly once, including Unicode U+2019 in “paper’s”:

> The Agent Execution Protocol is the paper’s primary research contribution. The production vault/KMS boundary is supporting infrastructure for confidential, durable and exactly bound request-material handling.

The design expressly disclaims novelty in cloud storage, KMS, and HSM design and disclaims exactly-once external effects. Its proposed latency, failure, reconciliation, rollback, retention, privacy, cost, and availability measurements are future experiments rather than reported measurements. It retains production applicability as `NO-GO`. No paper reframing, fabricated provider behavior, or current production-readiness claim was found.

## 4. Preserved AEP invariants

The revision continues to state the following AEP invariants without weakening them:

| Preserved invariant | Reconstructed evidence and qualification |
|---|---|
| 1,048,576-byte request limit | Binding/2 and LF/1 keep the exact request/ciphertext cap. The separate outer-record capacity issue found below does not silently reduce the stated request cap; it instead makes the schemas mutually unsatisfiable for part of the stated domain. |
| Exact canonical request-binding equality | Redis `canonical_request_binding` is named the sole authoritative value; host and Lua compare the whole reconstructed string. |
| Raw state before semantic interpretation | Production host and Lua gates require strict raw UTF-8/JSON/shape/version validation before lease, status, ledger, binding, or transition semantics. |
| Immutable execution/intent/step/connector/operation/profile binding | Binding/2 freezes these values, and the outer projections must equal them exactly. |
| Authenticated complete vault metadata | Selector, anchor, exact receipt, LF/1 metadata, AAD, context, KMS result, AEAD, fingerprint, digest, and binding are all required. |
| Endpoint-profile and deadline revalidation | Dispatch steps 12 and 13 reload authority and revalidate exact profile/credential/codec/deadline facts. |
| V1 before L1/A1/I1 | Creation order is V1, L1, A1, then production intent CAS and I1. |
| CAS then same-connection `WAITAOF` | Section 8.1 and the state machine retain this order. |
| Durable intent before transport | Connector consumption follows I1 and a new dispatch acknowledgement. |
| One-use, connector-consumed provenance | `VerifiedDispatch/2` is process-local and moves atomically from issued to consumed before one connector call. |
| At most one application mutation attempt; no automatic retry | Dispatch and connector rules prohibit redirect replay, failover, original-worker replay, and recovery replay. |
| Read-only recovery | Recovery purposes can inspect exact object, lifecycle, Redis, tombstone, and audit state but cannot perform or replay a provider mutation or mint provenance. |
| Unknown outcomes fail closed | Unknown store/KMS/lifecycle/audit/Redis/delete/transport outcomes remain ineligible and require exact-target inspection or operator action. |
| No selector fallback | Missing, corrupt, conflicting, rolled-back, or unavailable selector state never selects revision 1 or an older revision. |
| No older key/envelope/endpoint fallback | Exact persisted KMS version, selected envelope, and endpoint/profile version are mandatory. |
| Typed privacy boundaries | Raw requests, cryptographic values, provider objects/tokens, exceptions, and unbounded strings are excluded from typed telemetry. |
| Structural exclusion of activation | No activation schema, parser, method, port, capability, or dispatch-enabling result is authorized for Stage 2. |
| Production dispatch disabled by default | Current source contains only test composition and no production vault/KMS schemas or production connector activation. |

These preserved statements are necessary but not sufficient for compatibility. `PVK-RR-01` remains blocking because the new production creation/state contract does not specify all consistency conditions needed to implement those statements without choosing semantics.

## 5. `PVK-RR-01` disposition

**Disposition: `PARTIALLY RESOLVED`**  
**Residual severity: `BLOCKING` (plus one `MAJOR` size contradiction)**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/17` | Production v2 used ID/fingerprint representations incompatible with delivered `IntentRecord` and binding/1, and did not freeze how v2 fit authoritative raw Redis state, parsers, Lua, preflight, or v1 compatibility. |
| Exact revised sections examined | 3; 5.3; 6.4; 7.1; 7.2; 7.4-7.8; 8.1-8.3; 9; 10.1/10.3; 14; 15.1/15.4; 19.2; 22. |
| Schemas/contracts reconstructed | `aep.production-persisted-request-binding/2`; `aep.production-intent-record/1`; `aep.production-intent-state/1`; `aep.production-intent-transition/1`; transition evidence/1; production key/lock namespaces; host/raw/Lua version gates; creation CAS; later mutation; dispatch preflight; delivered binding/1 and `IntentRecord`. |
| Delivered-AEP compatibility | Representational separation is compatible: execution, intent, and correlation IDs are canonical lowercase UUIDv4; `step_id` uses the delivered exact safe-ID profile; fingerprint is exactly 64 lowercase hex; v1 keys/parser/Lua remain separate and unchanged in the matching source/tests manifest. Semantic compatibility is incomplete for production creation and recovery. |
| Stage 2 semantic invention | **Required.** Stage 2 would have to choose the complete production creation fence, attempt rule, TTL rule, and recovery-progress representation, and would have to resolve the outer-record capacity contradiction. |
| Remaining provider dependency | Redis topology/durability, lease deployment, provider material/storage durability, and operational time/TTL values remain later evidence. They do not cure the missing provider-neutral state semantics. |
| Acceptance evidence | `PVK-CAN-005/006` and `PVK-WFL-002` are future criteria only. No production parser, Lua, codec, or test exists. The unchanged manifest proves non-implementation, not correctness. |
| Residual limitation | Exact version rejection and byte equality are frozen, but not the full legal creation/state/recovery behavior or a size-safe embedding for every valid binding. |

### 5.1 Reconstructed compatibility model

The representational correction is genuine:

- Binding/2 is strict canonical JSON under `aep.canonical-json/1`, depth 128, with 40 exact fields and a maximum of 1,048,576 UTF-8 bytes.
- `execution_id`, `intent_id`, and `correlation_id` use canonical lowercase UUIDv4, including the exact version/variant positions.
- `step_id` uses `[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}` with a 128-byte ASCII limit and case-sensitive equality.
- `request_fingerprint` is a decoded-and-constant-time-compared 32-byte digest represented externally as exactly 64 lowercase hexadecimal characters.
- `request_binding_digest` is `SHA-256(LF32("AEP-PRODUCTION-BINDING-DIGEST-V2", canonical_manifest_bytes))`, serialized as `Digest32`.
- Redis `canonical_request_binding` remains the sole authoritative request-binding value. Projections do not replace it.
- Delivered `aep:state:*`, binding/1, `IntentRecord`, raw validator, Lua, and preflight are structurally separate from production `aep:production:state:*`, record/1, state/1, binding/2, and the proposed production Lua family.
- Unsupported, absent, and mixed versions reject before semantic mutation. Migration, dual-read, upgrade, downgrade, reinterpretation, and fallback are prohibited.
- Full binding strings and all outer projections must match exactly, and raw-state validation precedes semantic interpretation.

The delivered code remains byte-for-byte represented by the matching source/tests manifest. Delivered creation Lua independently confirms stronger rules: it blocks creation if *any* current ledger record in the execution is `ABOUT_TO_FIRE`, `FIRED_UNCONFIRMED`, or `PERMANENTLY_AMBIGUOUS`; for the same step it permits the next attempt only after the latest attempt is `FAILED_CONFIRMED`; and it requires `attempt=max_attempt+1`, `prepared_state_version=expected+1`, immutable prior ledger entries, a processing candidate state, lease/TTL conditions, and exact binding equality.

### 5.2 Blocking semantic gap

The production state contract freezes only `(step_id, attempt)` uniqueness and “at most one unresolved delivered status per `step_id`.” The production Lua text requires a new `ABOUT_TO_FIRE` record and projection/binding/version equality, but it does not freeze:

- the delivered execution-wide ambiguity fence;
- whether `FIRED_CONFIRMED`, `PERMANENTLY_AMBIGUOUS`, or other terminal same-step states permit another attempt;
- the exact same-step predecessor/latest-attempt rule;
- the `attempt=max+1` and complete-ledger preservation rule;
- exact execution-status eligibility and state-version increment conditions;
- the minimum lock/TTL coverage for unresolved intent retention;
- the production representation and mutation rules for repeated read-only recovery observations, attempt counts, next-check times, and terminal ambiguity evidence.

The production record deliberately removes delivered `last_observation`, `reconciliation`, `external_reference`, and `risk_acceptance_id` while retaining statuses such as `FIRED_UNCONFIRMED` and `PERMANENTLY_AMBIGUOUS`. No other frozen production schema carries the read-only recovery progress required to reach those statuses deterministically. Stage 2 would therefore have to import some delivered rules, weaken them, or invent replacements. Because those choices govern whether another non-idempotent application mutation may be prepared while an earlier intent is ambiguous, this is `BLOCKING`.

### 5.3 Outer-record capacity contradiction

The inner canonical binding may be 1,048,576 bytes. The outer production record stores those bytes as the JSON string `canonical_request_binding` but caps the entire outer record at 1,114,112 bytes. JSON-string embedding must escape every inner quote and backslash. A valid near-cap binding can contain many escaped quotes/backslashes through bounded `safe_descriptor` canonical values; the added escaping can exceed the 65,536-byte difference before any other outer fields or transitions are counted. No smaller admissible inner cap or proven worst-case outer bound is specified.

An implementation would have to reject part of the stated valid binding domain, silently raise the outer cap, or choose a different encoding. That is a cross-schema `MAJOR` contradiction and means the 1 MiB request/binding domain is not mechanically implementable as written.

## 6. `PVK-RR-02` disposition

**Disposition: `RESOLVED`**  
**Residual severity: none; provider and implementation evidence remain future dependencies**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/17` | Required anchor, hold/release, deletion, receipt, event, and reconciliation hashes were absent or incomplete; selector predecessor fields were ambiguous; one construction used a nonexistent revision update time; creation/rewrap order was not demonstrably acyclic. |
| Exact revised sections examined | 6.2-6.3; 7.1; 7.3; 7.5-7.8; 8.1; 8.5; 9; 10.3/10.6; 13; 15.1-15.4; 19.2. |
| Schemas/contracts reconstructed | LF32; every required digest/hash row; signed genesis/selector/anchor/hold/release/deletion/tombstone/reconciliation records; provider receipt and primary-result manifests; receipt references; audit event/receipt; creation and rewrap dependency order. |
| Delivered-AEP compatibility | The graph authenticates exact binding, AAD, KMS context, selected immutable envelope, lifecycle state, and receipt evidence without altering the delivered fingerprint or authoritative Redis-binding rules. |
| Stage 2 semantic invention | Not required for the reviewed hash constructions. The exact labels, field order, primitive encodings, bounds, exclusions, algorithm, output, and comparison rules are stated. |
| Remaining provider dependency | Provider receipt/token truth, lifecycle CAS durability, pinned-key operation, KMS context enforcement, and actual deletion/tombstone behavior remain provider-stage facts. |
| Acceptance evidence | Future contract criteria name byte vectors and failure paths; no code, vector results, or provider result exists yet. Resolution here is design-contract resolution only. |
| Residual limitation | Cryptographic correctness, provider enforcement, and operational key custody are unverified. That limitation is expressly retained and does not leave the provider-neutral byte graph ambiguous. |

### 6.1 Independently reconstructed required graph

All SHA-256 constructions use `LF32` with the displayed ASCII label as part 1. Identifiers use validated exact UTF-8/ASCII bytes, integers use `U64BE` unless expressly `U32BE`, digests use raw decoded 32-byte values, signatures use raw 64-byte values, and canonical record bytes use their named strict codec and cap. Digest outputs are raw 32 bytes serialized only as 43-character unpadded base64url `Digest32`. Hash, HMAC, AEAD-tag, and signature comparisons use constant-time library operations after public type/length checks where applicable.

| Required relationship | Reconstructed exact definition |
|---|---|
| Lifecycle monotonic-anchor hash | `SHA-256(LF32("AEP-MONOTONIC-ANCHOR-HASH-V1", canonical_signed_anchor_bytes))`; the signed record includes generation, selector hash, and predecessor anchor hash. |
| Predecessor anchor hash | Null only at generation 1; otherwise the raw decoded anchor hash for generation `g-1`, authenticated inside the signed current anchor. |
| Envelope predecessor link | `SHA-256(LF32("AEP-PREDECESSOR-LINK-V1", vault_locator, material_id, U64BE(previous_revision), previous_envelope_hash_raw))`; absent for revision 1. |
| Retention-hold hash | Label `AEP-RETENTION-HOLD-HASH-V1` plus the entire canonical signed hold record. |
| Hold-release linkage/hash | Label `AEP-HOLD-RELEASE-HASH-V1` plus the entire signed release; record includes exact released hold hash and optional predecessor release hash. |
| Deletion-decision hash | Label `AEP-DELETION-DECISION-HASH-V1` plus the entire signed ordered decision record. |
| Deletion receipt digest | Label `AEP-DELETION-RECEIPT-DIGEST-V1` plus the exact canonical delete-receipt manifest; self/outer receipt digests and meta are excluded. |
| Tombstone receipt digest | Label `AEP-TOMBSTONE-RECEIPT-DIGEST-V1` plus the exact canonical tombstone-receipt manifest; self/provider/reference digests and meta are excluded. |
| Audit-event hash | Label `AEP-AUDIT-EVENT-HASH-V1` plus the canonical audit event excluding only `event_hash`. |
| Audit receipt-reference digest | Label `AEP-AUDIT-RECEIPT-REFERENCE-DIGEST-V1` plus the exact receipt manifest; reference digest and meta are excluded. |
| Lifecycle reconciliation evidence hash | Label `AEP-LIFECYCLE-RECONCILIATION-EVIDENCE-HASH-V1` plus the entire signed reconciliation record. |
| Safe-operation pseudonym | HMAC-SHA-256 over `LF32("AEP-SAFE-OPERATION-PSEUDONYM-V1", environment, pseudonym-key ID, key version, method, operation ID)`; prefix `sop_` plus the first 22 characters of the full canonical base64url digest. |
| Provider-receipt pseudonym | HMAC-SHA-256 over the corresponding common prefix fields plus label `AEP-PROVIDER-RECEIPT-PSEUDONYM-V1`, receipt class, and raw provider-receipt digest; prefix `prc_` plus first 22 characters. |

The broader table also freezes AAD, KMS-context, wrapped-DEK, envelope, genesis, selector, lifecycle-view, eligibility-decision, provider-receipt, receipt-reference, aggregate-receipt, primary-result, raw-Redis reference, reference-observation, aggregate-reference, and production-transition hashes.

`selected_envelope_predecessor_link` has one meaning: it equals the selected envelope metadata and KMS-context `predecessor_link`. It is derived from the previous revision number and previous envelope hash, but is never that previous envelope hash itself. `updated_at_ms` is used only where it actually exists—the selector—and no undefined revision update time participates in the graph.

Creation is acyclic: binding → AAD/context → wrap/encrypt → envelope → provider receipt → genesis → selector → anchor → audit → Redis intent. Rewrap is also acyclic: authenticate current state → read/unwrap source → derive predecessor link → rewrap → build/write/read/verify candidate → candidate audit → selector/anchor proposal → authorization audit → CAS → result audit.

Rewrap's allowlist is exact. It cannot change plaintext, material length, nonce, ciphertext, tag, AAD bytes/hash, material checksum, material identity, creation key identity/version, semantic fingerprint, binding digest, deadlines, `created_at_ms`, or the authoritative Redis binding. Only the named wrapper, context, candidate receipt, revision, selector/anchor, and audit fields may change.

## 7. `PVK-RR-03` disposition

**Disposition: `PARTIALLY RESOLVED`**  
**Residual severity: `BLOCKING`**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/17` | Lifecycle/deletion/facade/audit types were placeholders; selector inspection lacked an immutable target; enums were incomplete; facade/plaintext/provenance ownership contradicted itself; historical audit evidence could recreate dispatch authority. |
| Exact revised sections examined | 5.3; 6.1-6.6; 7.1; 7.3; 7.7-7.8; 8.2-8.3; 8.7; 9-10; 13-14; 15.2-15.5; 19.2. |
| Schemas/contracts reconstructed | `CancellationToken`; `OperationResultMeta`; object/KMS/lifecycle/audit results; deletion inputs and receipts; `AuthenticatedLifecycleView`; `RetentionState`; `SignatureEvidence`; selector inspection; facade inputs/results; audit event/status/receipt; `VerifiedDispatch/2`. |
| Delivered-AEP compatibility | The dispatch facade and one-use provenance rule now match the delivered closure model. The deletion evidence and result-type contradictions are not implementably frozen and could weaken deletion security or interface invariants. |
| Stage 2 semantic invention | **Required.** It would have to invent how deletion observations are supplied/authenticated, how requested deletion class reaches the object adapter, how simultaneous retention states are folded, whether scope/capability results carry meta, and how unmapped failures select audit reason codes. |
| Remaining provider dependency | Provider receipt semantics, audit durability/delivery, lifecycle authority behavior, KMS custody, provider deletion/retention, and operational identity governance remain later evidence. |
| Acceptance evidence | No implementation exists. Future criteria cover portions of the types and provenance rule but do not expose the deletion-input mismatch and import invalid matrix rows for some lifecycle cases. |
| Residual limitation | The authority transition is well frozen, but deletion authorization and the universal result contract are internally incomplete. |

### 7.1 Corrections that are genuine

`CancellationToken` has a bounded process-local identity, one-way state, no serialization, and exact cancellation phases. Object, KMS, lifecycle, selector inspection, audit, facade, hold/release/deletion/tombstone, and dispatch types now generally name every primitive field, target, acknowledgement state, outcome certainty, retry/reconciliation directive, audit requirement, and dispatch effect through `OperationResultMeta`.

`inspect_selector_cas_exact` takes `SelectorInspectionInput`, which includes the complete immutable `LifecycleTarget`, expected/proposed generations and hashes, anchor token, and decision ID. It cannot infer a global target from a decision ID.

The dispatch authority correction is exact and conservative:

1. `authorize_dispatch` owns authenticated material reconstruction, raw Redis binding/preflight, and endpoint/deadline revalidation.
2. It obtains one direct `NEW` durable `dispatch.eligible` acknowledgement in the current invocation.
3. It then issues exactly one process-local `VerifiedDispatch/2`.
4. `HISTORICAL`, inspected, caller-supplied, reconciled, conflicting, or `UNKNOWN` audit evidence issues no authority.
5. A crash after audit acceptance consumes the deterministic audit slot; neither restart nor recovery can recreate authority.
6. Repeated facade invocation sees historical/conflict and cannot issue a replacement.
7. Recovery is read-only and has a distinct `RECOVERY_READ_ONLY` purpose; normal metadata/lifecycle reads use their separately enumerated audited purposes.

`VerifiedDispatch/2` explicitly freezes IDs, exact request scope, canonical production binding, binding digest, endpoint/profile/credential/codec versions, dispatch event hash, receipt-reference digest, monotonic deadline, and one-way capability state. Plaintext material is never returned as a separate dispatch authority.

### 7.2 Blocking deletion-evidence mismatch

`aep.reference-observation/1` includes target, ordinal, execution/intent IDs, production state version, request-binding digest, raw-Redis evidence hash, lifecycle-view hash, exact reference state, audit receipt-reference digest, and observation time. Section 7.3 requires the evaluator to accept two independently read complete records, recompute both observation hashes, confirm both durable audit receipts, compare all same-target/binding facts, and compute the aggregate reference-evidence hash.

`DeletionEvaluationInput`, however, contains only:

- one `raw_redis_reference_evidence_hash`;
- first and second observation hashes;
- first and second times;
- the interval and trusted-time fields;
- the lifecycle view and control token.

It does not contain either canonical observation record, either audit receipt/reference object, both per-observation raw Redis evidence hashes, or an exact lookup key/port by which the evaluator retrieves them. Hashes alone do not let the evaluator reconstruct and authenticate the claimed record fields. An implementation must trust caller assertions or invent fields/reads. Because this is the proof that no authoritative intent/reference still binds the material before deletion, the gap is `BLOCKING`.

### 7.3 Blocking delete-target and retention gaps

The signed `DeletionTarget` freezes `requested_deletion_class`, and `EnvelopeDeleteReceipt` reports it. The method `request_envelope_delete_exact(...)` does not accept `requested_deletion_class`, the signed decision bytes, or a `DeletionTarget`; it accepts only the exact envelope target, provider version/checksum, decision ID, and idempotency key. A decision ID is expressly not a global target. The object adapter therefore cannot know which exact deletion class it is authorized to request or verify. Stage 2 would have to add an input or infer authority through an unstated lookup. That is `BLOCKING`.

`DeletionClass` also includes `NONE` and `LOGICAL_DENIAL`, but the decision schema does not say which values are legal as a requested class. Whether those values create no provider call, a policy denial, or an invalid authorization is left open.

`RetentionState` has one `class` discriminator while separately carrying active holds and an optional provider lock token. Its rules allow a null end only for `LEGAL_HOLD` and a provider lock token only for `PROVIDER_LOCK`. It cannot losslessly encode an indefinite legal hold concurrent with a provider lock or backup-pending state. No precedence/aggregation rule freezes the conservative effective state. Deletion code would have to invent how overlapping retention authorities combine, which is also a security-semantic blocker.

### 7.4 Result and audit-enum contradictions

Section 6.1 says every typed result contains `OperationResultMeta`. `unwrap_dek_exact` returns `PlaintextDekScope`, whose complete frozen shape has no `meta`. `authorize_dispatch` returns `VerifiedDispatch/2`, whose complete frozen shape also has no `meta`. Both are named method results. An implementation must either widen those supposedly exact shapes, wrap them in an unstated result, or violate the universal result rule. This is `MAJOR` independent of the deletion blockers.

The audit enums are closed, but the mapping is not complete. `DependencyFailure` includes, among others, `CONFIGURATION`, `UNEXPECTED_VERSION`, and `REPLAY`; `ReasonCode` has no exact same-named values for those classes and no exhaustive mapping table selects the required alternative. “Operation-specific but closed” does not tell an implementer whether to report, for example, configuration/precondition or replay/integrity. Because event hash bytes and operator evidence depend on the chosen enum, this is a `MAJOR` audit-contract omission.

## 8. `PVK-RR-04` disposition

**Disposition: `PARTIALLY RESOLVED`**  
**Residual severity: `MAJOR`**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/17` | Failure rows conflated malformed/conflict/missing cases, had incorrect audit/read/KMS counts, omitted required authorization/result audits, mishandled post-audit provenance crashes, and failed to preserve historical acknowledgements consistently. |
| Exact revised sections examined | All 53 rows in Section 10; Sections 6.1, 6.6, 7.8, 8.5, 9, 13.2, 14; every Section 15 row import. |
| Schemas/contracts reconstructed | Counter meanings; V1/L1/A1/I1/P1 history; result meta; audit policy; object/KMS/lifecycle method calls and receipts; dispatch authority; recovery directives. |
| Delivered-AEP compatibility | The matrix preserves fail-closed dispatch, one provider mutation, no replay, exact-target reconciliation, and historical VAIP points. Audit-result counters and acknowledgement accounting conflict with the frozen interfaces. |
| Stage 2 semantic invention | Required for whether result audits run, which receipts count as newly acknowledged, and which error/certainty applies to combined faults. |
| Remaining provider dependency | Actual fault placement, provider acknowledgement truth, conditional-write semantics, and durability remain provider evidence. |
| Acceptance evidence | Row count/shape is mechanically verified; no row has been executed. Several criteria import rows that are invalid under Sections 6.6 and 13. |
| Residual limitation | The matrix is substantially more precise but is not a complete executable oracle. |

### 8.1 Corrected properties confirmed

- Local unsupported version (`F02a`), local malformed canonical input (`F02a2`), and persisted unsupported version (`F02b`) are separate physical rows.
- Definite provider no-change (`F05a`) and an existing different object (`F05b`) are separate.
- Genesis absence (`F15a`) and selector absence (`F15b`) are separate.
- Most non-crash authenticated dependency failures use one mandatory-best-effort audit after the primary result is fixed.
- `F24a` and `F24b` correctly preserve the no-provenance-recreation rule: a direct new dispatch audit is not reusable after a crash, and a delivered process-local capability cannot be recreated.
- `F26` counts all three object operations and all three KMS operations: source read, candidate create, candidate read, source unwrap, rewrap, and candidate unwrap/verification.
- `F28a/b` and every `F32a-*` row place an authorization audit before a lifecycle/deletion-decision CAS.
- `F32b` retains the new pre-delete audit after the delete submission crash.
- Historical V1/L1/A1/I1/P1 states are never reset merely because a current invocation has zero corresponding calls.
- No recovery row issues or replays an object/KMS/lifecycle/audit/connector mutation. A later write is expressly a new authorized normal invocation.

### 8.2 Audit counter contradictions

Sections 6.6 and 13 require `vault.selector.advance.result` after or after reconciliation of selector CAS, and the corresponding `.result` event after or after reconciliation of hold apply/release. Every non-crash lifecycle failure after submission is also subject to mandatory-best-effort audit.

- `F27` performs selector CAS plus selector and anchor inspection and returns an unresolved result, but reports only `A1`, the pre-CAS authorization audit. The required selector-result/failure audit makes the enclosing invocation `A2`.
- `F28a` and `F28b` perform CAS plus exact control inspection and return unresolved hold/release results, but each reports only `A1`, the authorization audit. The required result/failure audit likewise makes each enclosing invocation `A2`.
- The crash-only `F32a-*` rows may omit the post-CAS result audit because the process crashed before that boundary; this does not justify omission in the non-crash `F27/F28` rows.

Section 13.2 also lists `F24` among cases using `OMITTED_BY_DESIGN` for a crash before an audit boundary. `F24a/b` occur after a direct `NEW` `dispatch.eligible` acknowledgement and correctly state `GATING_DURABLE`. The generic Section 13 rule directly contradicts those rows and the facade rule.

### 8.3 Incomplete acknowledgement accounting

The Section 10 legend says “new acknowledgements” names every receipt obtained by the current invocation, including non-VAIP receipts. `F26` names only a candidate object receipt and candidate audit even though its counted calls return source-read, candidate-create, candidate-read, source-unwrap, rewrap, and candidate-unwrap result/receipt evidence under the Section 6 interfaces. The same pattern affects dispatch rows that count exact lifecycle/object/KMS reads but name only the later audit receipt.

This is not merely a shorter narrative: receipt-reference digests are folded into authenticated audit and aggregate receipts, so an executable oracle must say which results were obtained and in what acknowledgement state. The current cells do not meet their own legend.

### 8.4 Rows combining distinct injected failures or outcomes

The following rows still combine mutually exclusive injected classes under one ID:

- `F01`: one declared segment over cap **or** total over cap.
- `F17b`: provider version mismatch, checksum mismatch, or envelope-hash mismatch, while assigning `CHECKSUM` to the combined result.
- `F18`: syntax, bounds, hash, or cross-field validation across dispatch steps 7 and 8, while assigning one `INTEGRITY` result.
- `F22a`: malformed raw structure **or** unsupported version, while assigning only `MALFORMED_ENCODING`; Section 7.2 requires unsupported version to be `UNSUPPORTED_VERSION`.

Those cases can share the same no-dispatch outcome, but they cannot be one precise injected failure with one exact error/reason oracle. The matrix therefore does not satisfy the required semantic completeness result.

## 9. `PVK-RR-05` disposition

**Disposition: `PARTIALLY RESOLVED`**  
**Residual severity: `MAJOR`**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/17` | The prior criteria used vague counter phrases, incomplete acknowledgement/history vectors, and insufficient evidence-stage separation. |
| Exact revised sections examined | All 62 criteria in Section 15; all imported Section 10 rows; Sections 6.2-6.6, 13, 16, and 19.2. Particular attention was given to every criterion named in the rereview instructions. |
| Schemas/contracts reconstructed | Criterion ID/stage grammar; counter/history/new-ack/uncertainty/dispatch oracle; matrix import semantics; non-runtime N/A; contract/provider/operational claim boundaries. |
| Delivered-AEP compatibility | Stage labeling and evidence boundaries are compatible. Some criteria authorize behavior inconsistent with the lifecycle audit contract or import incorrect failure rows. |
| Stage 2 semantic invention | Required to repair imported audit counts, decide omitted dispatch states/acknowledgements, and decide whether an unaudited lifecycle CAS is a valid provider criterion. |
| Remaining provider dependency | All 13 provider cases, one operational review, and three independent reviews remain unexecuted. Real durability, linearization, IAM, KMS immutability/context, retention/deletion, audit delivery, backup, and regional behavior remain unverified. |
| Acceptance evidence | Counts and syntax were independently verified. No criterion has passed, and no production contract test exists. |
| Residual limitation | A formally shaped oracle that imports a contradictory row is not a complete oracle. |

### 9.1 Corrected properties confirmed

All 62 IDs are unique and have exactly one valid evidence-stage label. All four non-runtime criteria use explicit justified `N/A`. Every other row has exactly one syntactic counter-vector form or one exact Section 10 row reference. The prior vague phrases are gone.

`PVK-CAN-005` now expressly covers v1, unsupported, mixed, noncanonical v2, and one-byte outer/inner mismatch before semantic CAS. `PVK-STR-002`, `PVK-STR-004`, `PVK-STR-008`, `PVK-KMS-001`, `PVK-KMS-003` through `PVK-KMS-005`, `PVK-KMS-007/008`, `PVK-WFL-004` through `PVK-WFL-006`, and `PVK-OPS-005` through `PVK-OPS-008` all contain explicit counters rather than the prohibited phrases.

Section 16 correctly limits deterministic backends, mocks, and emulators to application-contract evidence. It explicitly denies that they prove provider conditional-write linearization, durable acknowledgement, consistency, key immutability/context enforcement, IAM, audit delivery, retention, legal hold, deletion, backups, or regional behavior.

### 9.2 Oracle defects

The following criteria are not complete executable oracles:

- `PVK-STR-004d`, `PVK-STR-005`, and `PVK-KMS-006` import `F27`, whose post-reconciliation selector-result audit is omitted.
- `PVK-WFL-006b` and `PVK-WFL-006c` import `F28a/b`, whose post-reconciliation hold/release result audits are omitted.
- `PVK-WFL-003` imports `F24a`; that row has the correct new gating audit, but Section 13.2 simultaneously classifies `F24` as omitted-by-design. The imported oracle is therefore cross-sectionally ambiguous.
- `PVK-STR-006d` claims an accepted lifecycle CAS with `A0`, no historical audit point, and no stated pre-existing authorized audit receipt. The lifecycle method contract requires the exact authorization receipt-reference digest before CAS. An isolated provider test may exclude the audit call from its local counter only if that durable receipt is an explicit precondition; it is not.
- `PVK-KMS-007` repeats `F26`'s acknowledgement omission: its counters cover three object and three KMS calls, but its “new” list names only candidate object/audit and selector audit/CAS/result components, not every object/KMS result receipt required by the legend. `PVK-KMS-001` and `PVK-KMS-005` similarly name enclosing audits without fully enumerating the read/KMS receipt results they fold in.
- `PVK-STR-010` says only “quarantined and `C0`”; it does not provide the exact `DispatchEffect/DispatchEligibility` pair required by the oracle column.
- `PVK-WFL-004b` says “authority consumed and second use rejects” but omits the exact `AUTHORITY_CONSUMED/INELIGIBLE` pair.

Criteria importing `PVK-KMS-006`, `PVK-WFL-003`, or `PVK-WFL-011` were traced through their named matrix rows rather than treated as self-proving. `PVK-WFL-011` → `F23` is consistent with fail-closed unknown audit acknowledgement. `PVK-KMS-006` and `PVK-WFL-003` retain the defects stated above.

Because invalid imports and incomplete acknowledgement/dispatch observations are material to lifecycle mutation and authority issuance, this is `MAJOR`, not a formatting-only defect.

## 10. `PVK-RR-06` disposition

**Disposition: `RESOLVED`**  
**Residual severity: none; provider/operational privacy evidence remains future work**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/17` | Safe identifier alphabets/bounds, raw provider input handling, pseudonym LF32/HMAC inputs, key lifecycle, typed events, and metric controls were incomplete. |
| Exact revised sections examined | 6.1; 7.1-7.3; 7.8; 13; 15.2/15.5; 16; 19.2. |
| Schemas/contracts reconstructed | UUID and safe-persisted ID profiles; all named random/registry IDs; `TextExternalId`; all identifier and provider pseudonyms; common HMAC tuple; pseudonym key lifecycle; safe evidence/event shapes; metric labels. |
| Delivered-AEP compatibility | Delivered UUIDv4, step-ID, lowercase-hex fingerprint, canonicalization, safe descriptor, and typed privacy rules are retained. |
| Stage 2 semantic invention | Not required for identifier and pseudonym bytes. Required-vs-optional unsafe handling, exact encodings, lengths, labels, inputs, and key identity/lifecycle are stated. |
| Remaining provider dependency | Registry governance, production pseudonym-key custody/rotation/retention, provider raw-value reduction, log controls, telemetry retention, and operational DLP evidence remain future gates. |
| Acceptance evidence | Future contract marker/metric tests are specified; no production implementation or operational/provider evidence exists. |
| Residual limitation | The design makes bounded interface claims, not universal non-disclosure, memory-zeroization, provider-log, or crash-dump guarantees. |

Execution, intent, and correlation IDs are canonical lowercase UUIDv4. Step IDs use the exact delivered safe alphabet and 128-byte bound. Production step/registry aliases may carry no business meaning. Audit correlation IDs are 32 CSPRNG bytes encoded as `aud_` plus 43 canonical base64url characters and cannot be caller supplied. Approval/ticket external inputs use exact NFC `TextExternalId` validation, control-character and edge-whitespace rejection, a 512-byte UTF-8 cap, and no trimming/case-folding.

Raw provider request IDs and version tokens are opaque `bytes[1..512]`, without Unicode normalization. Provider receipt inputs are protected 32-byte digests. All named pseudonyms use HMAC-SHA-256 over the common LF32 tuple:

`label, environment_id, pseudonym_key_identity, pseudonym_key_version, exact type-specific parts`.

Approval and ticket IDs use the full 43-character base64url HMAC; locator, receipt-reference, safe-operation, provider request/version/receipt, issuer, and approver pseudonyms use the exact first 22 characters of the full 43-character encoding and a type prefix. Omission is allowed only for unsafe optional telemetry values, with the closed omission reason; a required unsafe value rejects the authoritative operation.

The pseudonymization key is environment-scoped, at least 32 CSPRNG bytes, has immutable `KeyId` and `KeyVersionId`, is separate from encryption/commitment/signing keys, rotates only for new pseudonyms, retains old versions through the audit/incident period, and never falls back on missing/disabled/destroyed/cross-environment/ambiguous identity.

`EventType`, `OperationClass`, `ReasonCode`, `DurationBucket`, `CallCountVector`, `DurabilityClass`, `AcknowledgementState`, and `DispatchEffect` are closed enums/types. The missing exhaustive failure-to-reason mapping noted under `PVK-RR-03` affects interface/audit completeness, but does not leave the identifier or pseudonym byte construction open.

No raw provider value, identifier, pseudonym, token, digest, or material value is permitted as a metric label. Metrics are restricted to bounded low-cardinality classes, counts, buckets, and circuit state. Typed events cannot contain raw requests, Redis state, canonical binding, ciphertext, nonce/tag, AAD/context, keys, provider requests/responses/tokens, credentials, exceptions, trace locals, or capabilities.

## 11. Preserved `PVK-R-01` and `PVK-R-10` regression check

### 11.1 `PVK-R-01`

**Disposition: `RESOLVED` (preserved)**

The original `PVK-R-01` defect was the impossible use of the delivered 1,048,576-byte canonical-JSON document cap for a JSON/base64 envelope that also promised a 1,048,576-byte ciphertext. The LF/1 binary envelope remains the exact non-conflicting solution.

The maximum segment sum is independently recalculated as:

```text
metadata       16,384
AAD            32,768
KMS context     4,096
nonce              12
ciphertext  1,048,576
tag                 16
wrapped DEK     16,384
----------------------
segments     1,118,236
header             40
maximum      1,118,276 bytes
```

The minimum is `40 + 1 + 1 + 1 + 12 + 1 + 16 + 1 = 73` bytes. The decoder first reads the 40-byte header, validates magic/version/flags and fixed nonce/tag sizes, checks every `U32` length and per-segment cap, computes the total with checked unsigned 64-bit arithmetic, compares it with the 1,118,276 cap and exact stream/provider length, and only then allocates. Truncation, trailing data, integer wrap, unknown flags, unsupported version, and fallback are rejected. The 1,048,576-byte request/ciphertext limit is unchanged.

The new outer production-record size contradiction in `PVK-RR-01` is a different schema-embedding defect. It does not regress LF/1 framing itself. Provider object-size and durability support remain future evidence.

### 11.2 `PVK-R-10`

**Disposition: `RESOLVED` (preserved)**

The exact required research sentence remains present once. The revision explicitly makes provider experiments future work, disclaims cloud-storage/KMS/HSM novelty, reports no provider measurements, disclaims exactly-once external effects, and retains production applicability as `NO-GO`. No regression was found.

## 12. Cross-section consistency assessment

Sections 5 through 16 were compared operation-by-operation across architecture, interface, schema, construction order, flows, lifecycle state, matrix, telemetry, recovery, acceptance criteria, and provider evidence boundaries.

The following relationships are consistent:

- Binding/2 field encodings, the outer production projections, and Redis whole-string equality agree.
- Delivered v1 and production v2 namespaces/parsers are structurally separated.
- Selector predecessor link equals envelope metadata and KMS context, while prior envelope hash is only an input to that link.
- V1/L1/A1/I1/P1 ordering is consistent in creation, lifecycle state, dispatch, and the matrix.
- Facade authority is one direct new audit acknowledgement to one one-use capability.
- Recovery uses read-only purposes and cannot replay a provider or connector mutation.
- Rewrap's immutable and mutable field lists agree with its construction order.
- Holds never restore dispatch; unknown release remains conservatively active; unknown deletion never becomes an achieved class.
- Safe identifiers/pseudonyms and telemetry/metric exclusions agree.
- Mocks/emulators are limited to application-contract evidence.

The following contradictions require implementation judgment and are therefore at least `MAJOR`:

| Cross-section conflict | Consequence |
|---|---|
| Production state/creation text versus delivered Lua creation and recovery invariants | Stage 2 must select an ambiguity fence, attempt/TTL rules, and recovery state. This is `BLOCKING`. |
| Binding/2 1 MiB domain versus JSON-string embedding in the capped outer record | Some valid bindings cannot fit; implementation must change a cap/domain/encoding. |
| Reference-observation schema/verification versus `DeletionEvaluationInput` hashes-only shape | Deletion eligibility cannot authenticate the facts it is required to verify. This is `BLOCKING`. |
| Signed deletion target/receipt versus delete method missing requested class/decision bytes | Adapter cannot know the authorized deletion semantic. This is `BLOCKING`. |
| Overlapping hold/lock/backup facts versus single `RetentionState.class` | Conservative effective retention cannot be represented without an invented precedence rule. This is `BLOCKING`. |
| Universal `OperationResultMeta` rule versus `PlaintextDekScope` and `VerifiedDispatch/2` exact shapes | Result API cannot satisfy both contracts. |
| Lifecycle `.result` audit policy versus `F27/F28` `A1` totals | Matrix and imported criteria undercount required audits. |
| Section 13 `F24` omitted-by-design text versus `F24a/b` new gating audit | Crash/audit policy contradicts the exact provenance row. |
| Matrix legend versus rows that omit non-VAIP result receipts | “New acknowledgements” cannot be asserted exactly. |
| Exact single-failure requirement versus combined `F01`, `F17b`, `F18`, and `F22a` cases | Error/reason/certainty oracle is not unique. |
| Acceptance criteria versus invalid matrix imports/omitted dispatch pairs/unaudited CAS case | Section 15 is not a complete acceptance oracle. |

No contradiction was silently resolved in this review.

## 13. Remaining provider and operational dependencies

Even after provider-neutral design repair and later implementation, the following remain separate gates:

- selection of one provider, exact service tier, account, region/fault domain, and topology;
- conditional create, exact immutable read, authoritative absence, CAS/linearization, response-loss inspection, receipt, checksum, version-token, consistency, and durability semantics;
- exact immutable KMS key version, provider-native wrap/rewrap algorithm, context mapping/enforcement, key state, HA/DR, destruction, and backup behavior;
- lifecycle authority isolation, pinned signing-key custody, monotonic-anchor rollback/replay resistance, CAS durability, history retention, and restore behavior;
- audit outbox atomic append, status inspection, durability, downstream delivery, retention, and operational alerting;
- IAM and cross-environment negative evidence for object, KMS, lifecycle, and audit resources;
- retention locks, legal holds, deletion semantics, cryptographic inaccessibility, backup purge, tombstones, and delayed physical erasure;
- pseudonymization/commitment/signing key governance and historical-key retention;
- approved timeout, skew, deadline, grace, retention, backup, RPO/RTO, incident, dual-control, approval, and ticket policies;
- exact-environment failure injection, outage/restart, regional, performance, capacity, cost, and operational evidence;
- independent provider, operational, connector, deployment, and activation gates.

No provider documentation, SDK, account, resource, IAM policy, deployment artifact, production build, operational policy package, or external test evidence was used or found. These dependencies remain wholly unverified.

## 14. New or residual findings with severity

| ID | Severity | Finding | Required correction boundary |
|---|---|---|---|
| `PVK-RR2-01` | `BLOCKING` | Production state/creation/recovery does not freeze the delivered execution-wide ambiguity fence, exact attempt and ledger rules, TTL conditions, or recovery-progress representation. | Freeze exact provider-neutral state and Lua behavior for creation, every status/version, later transitions, preflight, TTL, and recovery; demonstrate no second mutation can be prepared across an unresolved execution. |
| `PVK-RR2-02` | `MAJOR` | A valid 1,048,576-byte binding can exceed the 1,114,112-byte outer-record cap after JSON-string escaping and outer fields. | Prove a worst-case bound or freeze a compatible smaller inner domain/larger outer bound/versioned non-ambiguous encoding without weakening the 1 MiB request invariant. |
| `PVK-RR2-03` | `BLOCKING` | `DeletionEvaluationInput` supplies hashes/times rather than the complete authenticated reference-observation records/evidence the evaluator must verify. | Freeze exact canonical records or exact authenticated lookup inputs/results, two independent raw-evidence/audit links, and recomputation steps in the input/interface. |
| `PVK-RR2-04` | `BLOCKING` | The exact delete method omits requested deletion class/decision authority, and `RetentionState` cannot represent/fold concurrent indefinite hold, provider lock, and backup-pending facts. | Carry the exact signed target/class to the adapter, restrict legal requested classes, and freeze conservative multi-source retention aggregation/precedence. |
| `PVK-RR2-05` | `MAJOR` | Universal result meta conflicts with `PlaintextDekScope` and `VerifiedDispatch/2`; audit failure classes lack an exhaustive exact `ReasonCode` mapping. | Freeze wrappers or explicit exceptions without widening exact authority shapes, and publish a total failure-to-reason mapping. |
| `PVK-RR2-06` | `MAJOR` | Failure matrix undercounts selector/hold result audits, contradicts F24 audit policy, omits obtained receipts, and combines distinct failures/outcomes. | Split rows and make counters, all current acknowledgements, audit mode, error/reason, certainty, retry, reconciliation, quarantine, dispatch, and operator action exact and cross-sectionally consistent. |
| `PVK-RR2-07` | `MAJOR` | Acceptance criteria import invalid rows, omit exact dispatch pairs/receipt observations, or permit a lifecycle CAS without an explicit durable authorization precondition. | Correct every affected oracle and revalidate all 62 against the corrected matrix and interfaces. |
| `PVK-RR2-08` | `DOCUMENTATION` | The `PVK-RR-04` correction-trace row contains unescaped enum pipes and is not a valid eight-column Markdown row. | Escape or code-format the embedded pipe literals in a later authorized document revision. |

Under the required severity definitions, `PVK-RR2-01`, `PVK-RR2-03`, and `PVK-RR2-04` are blocking because implementation would have to invent or weaken consistency/security/deletion semantics. `PVK-RR2-02`, `PVK-RR2-05`, `PVK-RR2-06`, and `PVK-RR2-07` are major cross-section or oracle defects. Any one of those results is sufficient to retain Stage 2 `NO-GO`.

## 15. Verified and unverified guarantees

| Guarantee or claim | Rereview status | Boundary |
|---|---|---|
| Required 22-section inventory | `VERIFIED` | Current `docs/15` bytes |
| Supplied file hashes and manifests | `VERIFIED` | Current tree; no historical Git proof |
| 53 unique matrix IDs | `VERIFIED` | Existence/uniqueness/table shape only |
| Matrix semantic completeness | `NOT VERIFIED` | Major counter, acknowledgement, audit, and single-fault defects remain |
| 62 unique criteria and one stage label each | `VERIFIED` | Syntax/count only |
| Acceptance oracle completeness | `NOT VERIFIED` | Major invalid imports and incomplete observations remain |
| LF/1 framing and size arithmetic | `VERIFIED AS DESIGN` | No codec implementation/provider capacity evidence |
| Required hash graph | `VERIFIED AS DESIGN` | No code, vectors, provider receipts, or key-custody evidence |
| Safe identifier/pseudonym bytes | `VERIFIED AS DESIGN` | No production implementation/operational privacy evidence |
| Direct-new-audit to one-use dispatch rule | `VERIFIED AS DESIGN` | No production facade/audit implementation |
| Delivered v1 source/test tree unchanged under supplied manifest | `VERIFIED FOR CURRENT TREE` | Git history unavailable; suite not rerun here |
| Production v2 state/Lua compatibility | `PARTIALLY VERIFIED` | Representations frozen; consistency/recovery semantics incomplete |
| Complete lifecycle/deletion interface | `NOT VERIFIED` | Blocking deletion evidence/retention gaps |
| Deterministic provider-neutral contract behavior | `UNVERIFIED` | No Stage 2 code/tests exist |
| Durable V1/L1/A1/I1/P1 in a production environment | `UNVERIFIED` | No provider or production implementation |
| Provider conditional-write/CAS/KMS/audit/retention/deletion behavior | `UNVERIFIED` | No provider evidence |
| Operational IAM, key custody, backup, incident, RPO/RTO, and DLP controls | `UNVERIFIED` | No operational evidence |
| Production connector or activation | `ABSENT / NO-GO` | Structurally excluded and not authorized |
| Exactly-once external effects | `NOT CLAIMED AND NOT GUARANTEED` | Unknown external outcomes remain ambiguous and unreplayed |
| Universal non-disclosure, zeroization, nonce uniqueness, or physical erasure | `NOT CLAIMED AND NOT GUARANTEED` | Explicit design limitation |

## 16. Stage 2 authorization boundary

The bounded Stage 2 `GO` conditions are not met:

- only `PVK-RR-02` and `PVK-RR-06` are fully resolved;
- `PVK-RR-01` and `PVK-RR-03` retain `BLOCKING` findings;
- `PVK-RR-04` and `PVK-RR-05` retain `MAJOR` findings;
- implementation would have to invent state/consistency, deletion-authentication, retention, result/audit, failure, and acceptance semantics;
- AEP invariants are stated but cannot all be mechanically enforced from the frozen production contracts as written.

Accordingly, this rereview authorizes no Stage 2 work. It does not authorize provider-neutral interfaces, schemas/codecs, typed results/errors, contract backends, or production/test composition changes at this time. It also does not authorize a provider or SDK, provider-specific adapters/resources, connector, deployment, activation mechanism, or production dispatch.

A future rereview could grant only a bounded provider-neutral `GO` after an authorized document revision resolves every blocking and major finding, preserves `PVK-R-01` and `PVK-R-10`, and demonstrates that no implementation choice remains for encoding, security, authentication, consistency, audit, retry, or provenance semantics. Such a later `GO` would still authorize only provider-neutral interfaces, exact schemas/codecs, typed results/errors, structural production/test separation, and continued absence of activation. It would not establish production readiness.

## 17. Final classifications and recommendation

| Classification | Final result | Basis |
|---|---|---|
| `PVK-RR-01` | **`PARTIALLY RESOLVED`** | Representation/version separation is repaired; production state/Lua/recovery semantics remain `BLOCKING`, and outer capacity is `MAJOR`. |
| `PVK-RR-02` | **`RESOLVED`** | Required authenticated hash graph and acyclic construction are fully frozen at design level. |
| `PVK-RR-03` | **`PARTIALLY RESOLVED`** | Dispatch authority is repaired; deletion evidence/class/retention semantics remain `BLOCKING`; result/audit types remain `MAJOR`. |
| `PVK-RR-04` | **`PARTIALLY RESOLVED`** | 53 unique shaped rows exist, but audit counters, acknowledgements, cross-section policy, and single-fault exactness remain `MAJOR`. |
| `PVK-RR-05` | **`PARTIALLY RESOLVED`** | 62 unique one-stage criteria exist, but invalid imports and incomplete oracles remain `MAJOR`. |
| `PVK-RR-06` | **`RESOLVED`** | Safe identifier, pseudonym, typed-event, and metric rules are fully frozen at design level. |
| Preserved `PVK-R-01` | **`RESOLVED`** | LF/1 framing and exact size arithmetic remain valid. |
| Preserved `PVK-R-10` | **`RESOLVED`** | Exact research-contribution statement and non-claims remain intact. |
| Provider-neutral design | **`REQUIRES REVISION`** | Blocking and major provider-neutral defects remain. |
| Design completeness | **`NOT VERIFIED`** | Production state, deletion, result, matrix, and acceptance contracts are incomplete or contradictory. |
| Compatibility with AEP | **`PARTIALLY VERIFIED`** | Core representations/order/fail-closed rules are preserved, but production enforcement semantics are not fully frozen. |
| Ready to begin bounded provider-neutral Stage 2 implementation | **`NO-GO`** | The mandatory all-six-resolved/no-blocking-or-major conditions fail. |
| Durable production vault/KMS implemented | **`NO`** | No implementation exists. |
| Provider-specific durability verified | **`NO`** | No provider evidence exists. |
| Production applicability | **`NO-GO`** | Implementation, provider, operational, connector, deployment, and activation gates are absent. |
| First production connector | **`NO-GO`** | Prerequisite production vault/KMS acceptance has not occurred. |
| Production non-idempotent dispatch | **`NO-GO`** | Must remain disabled; no activation or connector authority exists. |

Recommendation: revise the provider-neutral design in a separately authorized documentation-only correction stage, then perform another independent read-only rereview. Do not begin Stage 2, choose a provider, implement an adapter or connector, or enable production dispatch on the basis of this revision.

Ambiguity, corruption, and contention are detectable; the system fails closed.
