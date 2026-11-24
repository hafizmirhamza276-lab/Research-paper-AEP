# Independent rereview of the third production vault/KMS design revision

Date: 2026-08-01

## 1. Purpose and evidence boundary

This is an independent, read-only rereview of the third revision of `docs/15-production-vault-kms-design.md`. The controlling review evidence is `docs/16-production-vault-kms-design-review.md`, `docs/17-production-vault-kms-design-rereview.md`, and `docs/18-production-vault-kms-design-rereview.md`. The purpose is to determine whether the current design fully resolves `PVK-RR2-01` through `PVK-RR2-08`, whether `PVK-RR-02`, `PVK-RR-06`, `PVK-R-01`, and `PVK-R-10` remain resolved, and whether the four partially resolved parent findings can now be promoted.

Counts, traceability entries, hashes, parser output, acceptance tables, and the design's self-assessment were treated as claims to reproduce and then tested independently against the actual contracts. The review reconstructed the production state/lease/Lua behavior, binary and outer-record capacity, authenticated deletion inputs, delete authority, retention aggregation, process-local result wrappers, failure/reason mapping, all failure rows, all acceptance criteria, the trace tables, and the delivered Agent Execution Protocol (AEP) invariants. Syntactic success was not treated as semantic success.

The required entry classifications were retained at review entry:

| Classification | Entry value |
|---|---|
| Provider-neutral design | `REQUIRES INDEPENDENT REREVIEW` |
| Design completeness | `NOT VERIFIED` |
| AEP compatibility | `PARTIALLY VERIFIED` |
| Bounded Stage 2 implementation | `NO-GO — pending independent rereview` |
| Durable production vault/KMS implemented | `NO` |
| Provider-specific durability verified | `NO` |
| Production applicability | `NO-GO` |
| First production connector | `NO-GO` |
| Production non-idempotent dispatch | `NO-GO` |

No existing file was modified. No source, test, configuration, report, provider, SDK, resource, adapter, connector, activation surface, or production dispatch was created or changed. This report is the only created artifact. Stage 2 was not begun.

## 2. Repository and revision-integrity verification

### 2.1 Independent structural inventory

The current `docs/15` has exactly 22 numbered level-2 sections. The independently extracted sequence is `1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22`; every number occurs once and in order.

Section 10 contains 62 physical failure rows and 62 unique IDs. The six table groups contain `10, 9, 25, 2, 1, 15` data rows, respectively. The count was obtained from the rows present, not by filling to a target.

Section 15 contains 70 physical criteria and 70 unique IDs. Each has exactly one evidence-stage label. The independently recalculated distribution is:

| Evidence stage | Count |
|---|---:|
| `CONTRACT` | 53 |
| `PROVIDER` | 13 |
| `OPERATIONAL` | 1 |
| `INDEPENDENT_REVIEW` | 3 |
| Total | 70 |

There are 22 exact Section 10 imports in Section 15; all 22 referenced IDs exist. All 13 provider criteria name the Section 16.2 durable test authorization precondition. The 26 `DependencyFailure` values have 26 mapping rows, with no missing or extra key, and every matrix failure pair agrees with the total mapping.

Section 19 contains four traceability tables with `10, 6, 8, 9` data rows, for an independently reproduced total of 33. Across all 45 Markdown tables in `docs/15`, every header, separator, and data row has the declared number of columns. The malformed-row count is zero. The literal audit-mode pipes in Sections 19.2 and 19.3 are escaped, and all `PVK-RR2-01` through `PVK-RR2-08` rows have eight rendered columns.

These results establish existence, uniqueness, labels, imports, and table shape only. Sections 4 through 10 explain why several reconstructed contracts and oracles are still not semantically complete.

### 2.2 Byte hashes and line endings

| File | Expected SHA-256 | Observed SHA-256 | Bytes | CR | LF | Result |
|---|---|---|---:|---:|---:|---|
| `docs/15-production-vault-kms-design.md` | `caf16a895a4cf6e580a814e9db431b7aae2e71fb9726695ecab427cac8b26108` | Same | 287,686 | 0 | 1,401 | Match; LF-only |
| `docs/18-production-vault-kms-design-rereview.md` | `6cb052a336616b94817b4352840f20925cfd846a5a6309ef891df42ea99299ba` | Same | 68,380 | 0 | 645 | Match; LF-only |
| `docs/17-production-vault-kms-design-rereview.md` | `531d00f51c1826d4e59feb22dee1ef3c24a2511d11d85234e9f4d116985966e3` | Same | 60,494 | 0 | 547 | Match; LF-only |
| `docs/16-production-vault-kms-design-review.md` | `86ddecad00d0705bf5791f79eb4a3a01fa77a8663532285c4310bdb6f2c9853a` | Same | 52,315 | 0 | 457 | Match; LF-only |

For each protected manifest, the reconstruction emitted `repository-relative POSIX path<TAB>lowercase file SHA-256`, sorted the rows by relative path, joined them with LF and no final LF, UTF-8 encoded that manifest, and SHA-256 hashed the result.

| Manifest | Expected | Observed | Result |
|---|---|---|---|
| Source/tests | 88 files; `b3d60014240692936afdaf2b37be0ea51fe9e327a6c06a0a8013c40e96d5bb8a` | Same | Match |
| Configuration | 3 files; `eaef6ce9bbe12f4c8b766489d976886433ec43ff4d89a7923e32894189fd4e63` | Same | Match |
| All-other-files | 92 files; `d347849318e5999341de3a745feee5a436dba7fb12fd47bba15028f1402c7db4` | Same | Match |

The source/tests selection is every file under `src` and `tests`. Configuration is exactly `pyproject.toml`, `compose.phase2.yml`, and `redis/phase2.conf`. The all-other selection excludes `.git`, `.pytest_cache`, `__pycache__`, `docs/15`, `docs/17`, and `docs/18`; this output did not yet exist when the reported 92-file value was measured.

### 2.3 Exact arithmetic reconstruction

For an inner binding length `n=1,048,576`, canonical unpadded base64url has:

```text
4 * floor(n/3) + remainder contribution
= 4 * 349,525 + 2
= 1,398,102 bytes
```

The quoted JSON value is 1,398,104 bytes. The 28 exact record/2 field names total 507 bytes. Quotes and colons for the names, 27 commas, and two braces total another 113 bytes, so top-level structural overhead is 620 bytes. Independently summing all maximum encoded values gives 1,677,621 bytes. Therefore:

```text
record/2 cap = 620 + 1,677,621 = 1,678,241 bytes
non-binding reserve = 1,678,241 - 1,398,102 = 280,139 bytes
ledger cap = 2 + 256 * (39 + 1,678,241) + 255 = 429,639,937 bytes
state/2 cap = 429,639,937 + 250 = 429,640,187 bytes
```

The 250-byte state remainder was independently reconstructed as 120 bytes of six-member structural/name overhead plus 130 bytes of maximum non-ledger values. Parser and production-Lua contracts name the same binding, record, ledger, and state caps. This is an exact provider-neutral capacity proof; it is not evidence that a future Redis topology can accept or efficiently process a 429,640,187-byte state.

### 2.4 Git metadata, commands, and exit codes

Git metadata is unusable. `.git` has zero entries. The native Git exit code was 128 for status, repository-root discovery, and log discovery, each reporting that the directory is not a repository. No Git-history, commit, or historical changed-file claim is made.

The exact hash/line-ending command was:

```powershell
$ErrorActionPreference='Stop'
foreach($p in @('docs/15-production-vault-kms-design.md','docs/18-production-vault-kms-design-rereview.md','docs/17-production-vault-kms-design-rereview.md','docs/16-production-vault-kms-design-review.md')){
  $bytes=[IO.File]::ReadAllBytes((Resolve-Path $p)); $cr=0; $lf=0
  foreach($b in $bytes){if($b -eq 13){$cr++};if($b -eq 10){$lf++}}
  $hash=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
  "$p|sha256=$hash|bytes=$($bytes.Length)|CR=$cr|LF=$lf"
}
```

It exited 0 and produced the four exact rows in Section 2.2.

The decisive manifest construction was:

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
$files=@(Get-ChildItem -Recurse -File -Force|Where-Object{
  $relative=$_.FullName.Substring($repo.Length+1)
  $parts=$relative -split '[\\/]'
  '.git' -notin $parts -and '.pytest_cache' -notin $parts -and '__pycache__' -notin $parts -and $_.FullName -notin $excluded
})
$allOther=Manifest $files
```

It exited 0 and produced all three expected counts and hashes.

The structural parser used strict UTF-8 reads, recognized tables by their header/separator pair, counted only unescaped pipes, bounded Section 10/15/19 by their numbered headings, extracted matrix and criterion IDs, extracted each exact matrix import, extracted provider-stage rows, and compared the interface `DependencyFailure` set, the Section 13.1 mapping, and every matrix pair. It exited 0 with:

```text
numbered_sections=22|sequence=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22
matrix_rows=62|unique=62|table_groups=10,9,25,2,1,15
criteria=70|unique=70|stages=CONTRACT=53,INDEPENDENT_REVIEW=3,OPERATIONAL=1,PROVIDER=13|table_groups=7,17,10,22,14
matrix_imports=22|missing=0
provider_rows=13|missing_authorization=0
dependency_failures=26|reason_rows=26|missing=0|extra=0|matrix_reason_mismatches=0
trace_table_groups=10,6,8,9|trace_total=33
markdown_tables=45|malformed_rows=0|malformed_lines=
```

Other exact commands and genuine results were:

| Command | Exit | Result |
|---|---:|---|
| `Get-ChildItem -Path . -Filter AGENTS.md -File -Recurse -Force` | 0 | No `AGENTS.md` found |
| `rg -n '^#{1,6} ' docs\15-production-vault-kms-design.md docs\16-production-vault-kms-design-review.md docs\17-production-vault-kms-design-rereview.md docs\18-production-vault-kms-design-rereview.md` | 0 | Heading inventories obtained |
| Outer-cap arithmetic command using the exact 28 names and maxima | 0 | `base64url=1398102`, `record_cap=1678241`, `state_cap=429640187` |
| `rg -n "aep\.production-vault-envelope-lf/1\|aep\.production-persisted-request-binding/2\|aep\.production-intent-record/2\|aep\.production-intent-state/2\|aep\.vault-lifecycle-genesis/1\|create_genesis_and_selector_once\|compare_and_advance_selector\|AuthorizeDispatchResult\|UnwrapDekResult" src tests pyproject.toml compose.phase2.yml redis\phase2.conf` | 1 | No production contract implementation; exit 1 means no match |
| `git status --short --branch` | 128 native | Not a Git repository |
| `git rev-parse --show-toplevel` | 128 native | Not a Git repository |
| `git log --oneline -n 1` | 128 native | Not a Git repository |
| `Get-ChildItem -LiteralPath .git -Force` | 0 | Zero entries |
| `rg -n "611 passed\|48\.08s\|38\.79s" phase2_implementation_report.md docs\16-production-vault-kms-design-review.md docs\18-production-vault-kms-design-rereview.md` | 0 | Recorded baselines located |
| Numbered UTF-8 reads of all relevant ranges in `docs/15` through `docs/18`, `src/core/intents.py`, `src/core/request_binding.py`, and relevant test inventories | 0 | Contract evidence inspected without mutation |

### 2.5 Tests

No test command was run during this rereview. The genuine latest recorded baseline remains exit 0, `611 passed in 48.08s`, zero failures and zero skips, in `phase2_implementation_report.md`. `docs/16` separately records `611 passed in 38.79s`. The protected source/tests manifest matches, but neither historical run implements or tests the proposed production schemas. This report does not claim that 611 tests were rerun.

## 3. Preserved AEP invariants

Direct source inspection and the matching source/tests manifest confirm that the third document revision did not change delivered version-1 code or tests. The production design also continues to state these delivered invariants:

| Invariant | Independent result |
|---|---|
| Canonical request-binding equality | Preserved. Redis remains the sole authority; production record/2 decodes one exact binding and uses length, digest, round trip, projections, and constant-time full-byte equality only as validation. |
| Raw state before semantics | Preserved in the production host/Lua order and unchanged in delivered raw-state validation. |
| Delivered version-1 encodings | Preserved. UUIDv4 execution/intent/correlation IDs, safe step IDs, lowercase-hex fingerprints, delivered keys, models, Lua, TTL behavior, and tests remain in the matched source/tests bytes. |
| V1 before L1/A1/I1/P1 | Preserved throughout Sections 5, 7.8, 8, 9, and 10. |
| CAS then same-connection `WAITAOF` | Preserved; CAS alone is not I1. |
| Durable intent before transport | Preserved; I1 and all preflight steps precede the connector. |
| Endpoint/profile/deadline revalidation | Preserved in dispatch steps 12 and 13. |
| New audit acknowledgement before provenance | Preserved. Only a direct `NEW` dispatch receipt in the current invocation can issue. |
| One-use connector-consumed provenance | Preserved. `VerifiedDispatch/2` is process-local, non-copyable/non-serializable, and atomically consumed before one connector call. |
| At most one provider mutation; no automatic retry | Preserved. Redirect replay, failover, original-worker replay, and recovery replay remain prohibited. |
| Read-only recovery | Preserved with respect to application/provider mutation; only exact Redis evidence/progress CAS plus `WAITAOF` is allowed. |
| Unknown outcomes fail closed | Preserved. Unknown store, KMS, lifecycle, audit, Redis, delete, and transport outcomes do not authorize another mutation. |
| No fallback | Preserved for selector, revision, key, envelope, endpoint/profile, Redis, and test backend. |
| Typed privacy boundary | Preserved. Raw request, cryptographic material, provider objects/tokens, exceptions, capabilities, and unbounded strings remain excluded from typed telemetry. |
| Structural exclusion of production activation | Preserved. Stage 2 has no connector mutation port or activation schema/parser/method/capability. |
| Research-contribution boundary | Preserved. AEP remains the primary contribution; the vault/KMS boundary is supporting infrastructure. |
| Exactly-once external effects | Still expressly not claimed. |

These preserved statements do not make the production design fully compatible. The recovery-count contradiction in Section 4 would require implementation judgment in a state machine that fences non-idempotent mutation.

## 4. `PVK-RR2-01` disposition

**Disposition: `PARTIALLY RESOLVED`**  
**Residual severity: `BLOCKING`**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/18` | Production creation/state/recovery omitted the execution-wide ambiguity fence, exact same-step predecessor/attempt rules, TTL/lease/version conditions, and complete repeated recovery-progress semantics. |
| Exact revised sections examined | 3; 5.3; 6.1/6.4; 7.2-7.3; 7.8; 8.1-8.3; 9; 10.2-10.5; 13.2; 14; 15.1/15.4; 19.3; 22. |
| Contracts reconstructed | state/2, record/2, production lease/1, transition/1 and evidence/1, recovery observation/progress/terminal evidence, creation CAS, transition CAS, dispatch preflight, persistent-state TTL, delivered state/Lua behavior. |
| Cross-section compatibility | Creation, fence, same-step attempt, lease, persistent TTL, state-version, CAS, preflight, and no-second-mutation rules now agree. The late permanent-ambiguity resolution count does not agree with the general progress rule. |
| Delivered AEP compatibility | The five delivered statuses and legal edges, execution-wide blockers, `attempt=max+1`, immutable ledger preservation, raw-first validation, and read-only recovery direction are preserved. |
| Stage 2 semantic invention | **Required.** Stage 2 must choose whether a late authoritative observation increments the existing count, jumps to sentinel 61, or changes the meaning of counts 1..60. |
| Provider-specific dependency | Redis durability/topology/capacity, readback truth, and operational lease/time values remain later evidence; they cannot resolve the internal count rule. |
| Acceptance evidence | `PVK-WFL-013a/b` are unexecuted future criteria. `WFL-013b` imports the contradictory Section 7.2 progress rule rather than resolving it. |
| Residual limitation | No production parser, Lua, or recovery implementation exists. Permanent ambiguity deliberately sacrifices availability, but its later resolution record is not mechanically unique. |

The correction genuinely freezes all of the following:

- execution-wide blocking by `ABOUT_TO_FIRE`, `FIRED_UNCONFIRMED`, and `PERMANENTLY_AMBIGUOUS`;
- all five statuses and every legal transition;
- no later same-step attempt after `FIRED_CONFIRMED`, and a later same-step attempt only after latest `FAILED_CONFIRMED`;
- exact `attempt=max_attempt+1`, uniqueness, complete-ledger byte preservation, and state-version `expected+1`;
- a canonical lease record, ownership/epoch/policy validation, Redis-time expiry, positive PTTL, and exact operation coverage;
- persistent state (`PTTL=-1`) while any record exists, including unresolved and permanently ambiguous states;
- creation and transition CAS inputs, raw-first validation, exact candidate preservation, one `SET ... KEEPTTL XX`, and required same-connection `WAITAOF`;
- read-only atomic preflight requiring latest same-step `ABOUT_TO_FIRE`, initial progress, pre-reconcile time, exact binding/profile/deadline/lease, and no global blocker;
- a bounded recovery observation, terminal evidence, progress record, prior-progress hash, deterministic backoff, automatic terminal classification, and no provider mutation replay; and
- an explicit prohibition on preparing any second mutation while an earlier record is unresolved or permanently ambiguous.

The blocking contradiction is narrower but decisive. Section 7.2 says that after any observation CAS the observation ordinal equals the new count, that a caller cannot skip progress, and that each readback observation increments the count by one. It also says counts 1 through 60 are automatic-policy observations and count 61 is legal only for the single later authoritative observation that resolves `PERMANENTLY_AMBIGUOUS`.

Permanent ambiguity can occur at count 1: `NO_READBACK`, `CONFLICT`, unclassified evidence, or a positive-only `NOT_APPLIED` result makes it terminal immediately. If a later operator-triggered authoritative observation then resolves it, increment-by-one requires count 2, while the reserved rule requires count 61. Jumping from 1 to 61 violates the no-skip/increment rule; using 2 violates the “count 61 only” rule. The same conflict occurs whenever permanent ambiguity is reached before count 60. This governs append-only state/version evidence and the legal terminal-resolution CAS. Stage 2 cannot implement both rules and would have to invent the precedence. Because this state remains the fence against another non-idempotent mutation, the defect is `BLOCKING`.

## 5. `PVK-RR2-02` disposition

**Disposition: `RESOLVED`**  
**Residual severity: none; implementation and provider capacity evidence remain future work**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/18` | Escaping an inner 1,048,576-byte canonical JSON binding into a capped outer JSON string could exceed record/1, forcing a smaller domain, truncation, or cap invention. |
| Exact revised sections examined | 3; 6.4; 7.1-7.2; 7.8; 8.1; 10.1/10.3; 15.1; 19.3; 20. |
| Contracts reconstructed | binding/2, record/2, `BASE64URL_UNPADDED/1`, exact base64 length function, per-field maxima, record cap, ledger/state caps, strict decoder and equality sequence. |
| Cross-section compatibility | Binding cap, record field bound, parser allocation rule, creation CAS input, preflight equality, raw-state cap, and CAN-005/007 agree. |
| Delivered AEP compatibility | The 1,048,576-byte request/canonical binding limit is unchanged; decoded bytes remain the sole Redis authority. No delivered v1 encoding changes. |
| Stage 2 semantic invention | Not required for encoding, capacity, truncation, or request-domain behavior. |
| Provider-specific dependency | Whether a selected Redis deployment can store/process the maximum state, and its performance, remain provider/deployment gates. |
| Acceptance evidence | CAN-005/007 specify future exact boundary vectors; none has been run. Arithmetic was independently reproduced here. |
| Residual limitation | Design arithmetic is not a Redis capacity or production performance result. |

The selected outer encoding is exact, versioned, canonical unpadded base64url. Its worst-case expansion and all record/state arithmetic reproduce exactly. Base64url characters require no JSON escaping, the strict decoder rejects padding/alternate alphabets/noncanonical tails, and decoded length must equal the explicit length and lie within `1..1,048,576`. The decoded bytes, their strict canonical round trip, digest, outer projections, and host-supplied authoritative bytes must all agree. No truncation, implicit smaller domain, partial comparison, or alternate decoder is permitted. Every maximum-size valid binding fits.

## 6. `PVK-RR2-03` disposition

**Disposition: `PARTIALLY RESOLVED`**  
**Residual severity: `BLOCKING`**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/18` | `DeletionEvaluationInput` carried hashes/times rather than the complete canonical observation records, raw Redis evidence, lifecycle views, audit receipts, and exact authenticated lookups needed to verify deletion eligibility. |
| Exact revised sections examined | 6.1/6.3-6.4/6.6; 7.1/7.3/7.7; 8.7; 10.6; 13; 14.2; 15.4; 19.3. |
| Contracts reconstructed | `TrustedTimeEvidence`, `ReferenceObservationEvidence`, `DeletionEvaluationInput/2`, reference-observation/1, raw-Redis/lifecycle/audit/observation/aggregate hashes, audit event/receipt, eligibility decision. |
| Cross-section compatibility | Complete records and most hash/identity/independence checks align. Observation time is not explicitly bound to its authenticated time sample or durable audit event, and the audit event does not commit back to the observation facts. |
| Delivered AEP compatibility | Raw Redis is still validated before semantics, exact binding identity is retained, terminal/nonblocking statuses are conservative, and unknown evidence fails closed. |
| Stage 2 semantic invention | **Required.** Stage 2 must choose the equality/range relationship among observation time, signed sample time, audit-event time, and receipt acknowledgement time, and how the durable audit event authenticates the complete observation facts. |
| Provider-specific dependency | Redis/lifecycle/audit/time-source durability and authoritative absence remain provider evidence; provider truth cannot repair an absent provider-neutral byte relationship. |
| Acceptance evidence | WFL-014 is future-only and repeats “trusted-time sample/interval” without supplying the missing exact equality/commitment oracle. |
| Residual limitation | Complete canonical records are present, but self-consistent caller-supplied record times are not the same as authenticated interval evidence. |

The correction is substantial. Each observation bundle now directly carries the exact canonical observation record, exact raw Redis key and bytes, raw-state hash, complete authenticated lifecycle view and view hash, complete audit event and event hash, durable audit receipt and receipt-reference digest, and exact signed trusted-time evidence. The evaluator recomputes both raw-state, lifecycle, audit, observation, and aggregate hashes; checks immutable target/execution/intent/binding identity; requires ordinals 1 and 2, distinct operation IDs/time samples/audit keys/outbox sequences, ordering after the first durable acknowledgement, constant-time digest comparison, and fail-closed missing/malformed/stale/replayed/conflicting/unknown handling. Hashes no longer substitute for the canonical observation records.

The interval proof is nevertheless not closed. `TrustedTimeEvidence` authenticates `unix_time_ms` and `maximum_error_ms`, while `reference-observation/1` separately carries `observed_at_ms` and only the trusted-time evidence hash. No rule requires:

```text
observation.observed_at_ms == trusted_time_evidence.unix_time_ms
```

or defines a conservative interval relationship between them. The minimum-interval calculation uses `first.observed_at_ms` and `second.observed_at_ms`, not the authenticated `unix_time_ms` values. A pair of complete records can therefore satisfy the displayed interval by choosing record times far apart while carrying authentic signed samples from a shorter interval. The document also does not equate observation time to the associated audit event's `observed_at_ms` or receipt acknowledgement time.

The durable audit link is one-way: the observation contains `audit_event_hash`, but the closed audit-event schema contains no observation hash, raw-Redis evidence hash, lifecycle-view hash, exact binding digest, or exact target. Recomputing an old valid event/receipt and placing its hash in a newly constructed observation proves event acceptance, not that the durable event committed to that observation's deletion facts. Section 7.3's prose that times/audit slots “satisfy” independence does not choose the missing byte equalities. These gaps affect the proof that the two no-reference observations were genuinely separated and durably witnessed; they are `BLOCKING` deletion-authority semantics.

## 7. `PVK-RR2-04` disposition

**Disposition: `PARTIALLY RESOLVED`**  
**Residual severity: `BLOCKING`**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/18` | The exact delete method omitted requested class/signed authority, and one discriminator could not represent concurrent legal hold, provider lock, backup pending, lifecycle hold, deadlines, release, and deletion state. |
| Exact revised sections examined | 6.1-6.4/6.6; 7.3/7.7; 8.7; 10.6; 11.3; 13; 15.4; 16.2; 19.3. |
| Contracts reconstructed | `RequestedDeletionClass`, `DeletionTarget`, `EnvelopeDeleteAuthorization`, delete method/receipt/result verification, `RetentionFact`, `RetentionState/2`, evidence classes, provider receipt/reference schema, aggregate rules. |
| Cross-section compatibility | Delete authority is compatible. Concurrent aggregation rules are conservative, but provider retention/backup evidence cannot be represented by the closed receipt/method contracts and its source-to-evidence authentication is not total. |
| Delivered AEP compatibility | Exact immutable target/version/checksum/hash and no second unknown delete preserve fail-closed/no-replay behavior. Retention can only reduce authority. |
| Stage 2 semantic invention | **Required.** Stage 2 must add or select receipt classes, methods/results, target fields, generation binding, and per-class evidence-hash meanings for provider retention and backup evidence. |
| Provider-specific dependency | Actual lock, backup, delete, delayed purge, and receipt truth remain provider gates. Provider selection cannot decide the missing provider-neutral interface semantics. |
| Acceptance evidence | WFL-015a/b are future criteria; WFL-015a cannot construct all named authenticated facts from the current closed receipt set. |
| Residual limitation | Physical erasure and backup purge remain correctly unclaimed; the blocker is earlier—the provider-neutral authority/evidence type is incomplete. |

The delete-authority correction itself is complete. `EnvelopeDeleteAuthorization` carries the exact `DeletionTarget`, signed decision bytes, decision hash and ID, verified signature evidence, idempotency key, and authorization-audit receipt reference. The adapter re-parses and verifies the signed bytes, exact target membership, expiry, version, checksum, envelope hash, class, decision, idempotency, and audit tuple. Only `DELETE_CIPHERTEXT_VERSION` reaches the adapter. The two no-call classes are exact, achieved-only classes cannot be requested, and a known result must echo and verify the authorized tuple. Unknown delete outcome remains unreplayed.

`RetentionState/2` also replaces the invalid discriminator with an ordered array of concurrent facts and conservative aggregation. It retains legal/lifecycle holds, provider locks, backup pending, releases, maximum finite deadlines, deletion requested/achieved state, and unknown/conflicting facts without a precedence shortcut.

The evidence model needed to make those facts authoritative is incomplete:

- `RetentionEvidenceClass` names `PROVIDER_RETENTION_RECEIPT` and `PROVIDER_BACKUP_RECEIPT`, but the closed `ReceiptClass` enum has no retention-lock or backup-retention class.
- The closed Sections 6.2-6.6 method set has no exact provider retention/backup read, status, or release method/result from which those receipts are obtained.
- The backup rule requires evidence for the same target and “retention generation,” but neither `RetentionFact` nor `aep.provider-receipt-evidence/1` freezes a retention-generation projection for comparison.
- `RetentionFact.evidence_hash` is said to be recomputed over decoded bytes, but the allowed `RetentionSource` to `RetentionEvidenceClass` combinations and the exact named Section 7.3 hash/digest selected for every combination are not exhaustive. `SIGNED_LIFECYCLE_CONTROL` in particular can denote more than one signed record family.

An implementation must therefore invent a new receipt class/method/schema, overload an existing lifecycle/object receipt, or trust an unstated mapping. These facts decide whether deletion is allowed in the presence of legal/backup/provider retention authority, so the gap is `BLOCKING`.

## 8. `PVK-RR2-05` disposition

**Disposition: `RESOLVED`**  
**Residual severity: none; runtime type enforcement remains future evidence**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/18` | Universal result meta conflicted with `PlaintextDekScope` and `VerifiedDispatch/2`, and `DependencyFailure` lacked a total deterministic `ReasonCode` mapping. |
| Exact revised sections examined | 5.3; 6.1/6.4-6.6; 7.1/7.3/7.8; 8.2-8.3; 10; 13.1; 15.3/15.5; 19.3. |
| Contracts reconstructed | `OperationResultMeta`, `PlaintextDekScope`, `UnwrapDekResult`, `VerifiedDispatch/2`, `AuthorizeDispatchResult`, 26-value dependency set, 26-row reason map, event/safe-evidence/matrix uses. |
| Cross-section compatibility | The wrapper, interface, dispatch, audit, matrix, and acceptance descriptions agree on one top-level meta and one non-serializable payload. Every matrix pair matches the total map. |
| Delivered AEP compatibility | Plaintext never becomes connector authority; one-use provenance remains process-local and non-replayable. |
| Stage 2 semantic invention | Not required for wrapper shape or failure/reason choice. |
| Provider-specific dependency | Provider errors must be reduced into the frozen classes; runtime typing and safe representations remain implementation evidence. |
| Acceptance evidence | KMS-004/010 and OPS-011 are complete future contract oracles; none has been run. |
| Residual limitation | Process-local typing is not hostile-host isolation, guaranteed erasure, or proof of runtime enforcement. |

`UnwrapDekResult` has exactly one `OperationResultMeta` and one bounded `PlaintextDekScope`; the scope has no meta, serialization, copy, persistence, safe material representation, or dispatch authority. `AuthorizeDispatchResult` has exactly one meta and one bounded `VerifiedDispatch`; the capability has no meta, wire/persistence/copy form, or replay construction. Metadata cannot widen either payload.

All 26 `DependencyFailure` values map to exactly one `ReasonCode`; there are no missing, extra, or duplicate keys. Interfaces require the mapping, safe evidence duplicates the exact pair, event hashing uses the mapped reason, all 62 matrix rows use the same pair, and OPS-011 rejects alternatives before event hashing. More-specific policy classifications do not replace failure metadata's mapped pair.

## 9. `PVK-RR2-06` disposition

**Disposition: `PARTIALLY RESOLVED`**  
**Residual severity: `MAJOR`**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/18` | Matrix rows undercounted lifecycle result audits, contradicted F24 gating, omitted obtained receipts, and combined distinct F01/F17b/F18/F22a failures. |
| Exact revised sections examined | 6.1-6.6; 7.2-7.3/7.8; all 62 Section 10 rows; 13.2; 14; every Section 15 import. |
| Contracts reconstructed | Closed Method set, result wrappers, counter legend, VAIP history, acknowledgements, selector/control reconciliation, audit policy, retry/quarantine/dispatch/operator outcomes. |
| Cross-section compatibility | Splits, F24, F27/F28 audit totals, and most receipt lists now agree. Selector/control reconciliation rows do not agree with the closed method/result interfaces. |
| Delivered AEP compatibility | Rows keep V1/L1/A1/I1/P1, one connector mutation, no automatic mutation retry, no recovery mutation replay, and fail-closed unknown outcomes. |
| Stage 2 semantic invention | Required to decide whether reconciliation is one typed inspection or multiple reads/results, and to invent the missing hold/release control-inspection method/result. |
| Provider-specific dependency | Actual fault placement, conditional semantics, acknowledgement truth, and durability remain future provider evidence. They do not choose application call/result shapes. |
| Acceptance evidence | Count/uniqueness/shape and reason pairs are verified; no row has been executed. Several criteria import the incompatible rows. |
| Residual limitation | The matrix is much stronger but is not yet an operation-by-operation executable oracle. |

The following corrections are genuine:

- F01 is split into segment-cap F01a and total-cap F01b.
- F17b is split into version, checksum, and envelope-hash outcomes with the correct three failure/reason pairs.
- F18 is split into syntax, segment bound, total bound, AAD hash, KMS-context hash, and cross-field outcomes.
- F22a is split into malformed structure and unsupported version.
- F27, F28a, and F28b each use A2 and include the post-reconciliation result/failure audit.
- F24a/F24b remain `GATING_DURABLE`; neither permits audit-slot or capability recreation.
- F26 enumerates source/candidate object and KMS receipts rather than only aggregate receipts.
- Historical V1/L1/A1/I1/P1 evidence is retained, all rows prohibit recovery mutation replay, and every physical row has one phase, injected failure, result pair, retry/reconciliation, quarantine, dispatch effect, and operator action.

The remaining method/result contradiction is material. Section 6.3 freezes one exact `inspect_selector_cas_exact(SelectorInspectionInput)` method returning one `SelectorCasStatus`. F27 instead counts `L3(CAS+selector+anchor)` and lists three separate acknowledgements (`L.selector-cas`, `L.selector-read`, `L.anchor-read`). The design does not say that one typed inspection result expands into two Method calls and two separately returned metas/receipts, nor how that agrees with the one `SelectorCasStatus` wrapper.

F28a/F28b are worse: each counts `L2(CAS+inspect)` and names `L.control-inspect`, but the closed Section 6.3 method/result set has no exact hold/release control-inspection input, status schema, or method literal. F30 similarly names `L.decision-control` without identifying a closed method/result. F29a/b count four lifecycle reads inside a high-level deletion evaluation even though `evaluate_deletion` receives a populated `DeletionEvaluationInput`; the re-read/revalidation boundary is not frozen.

These are not provider call-placement details. `Method`, result meta, receipt acknowledgements, audit hashes, and acceptance counters depend on the chosen interface call. Stage 2 would have to invent the call/result decomposition. The defect is `MAJOR`.

## 10. `PVK-RR2-07` disposition

**Disposition: `PARTIALLY RESOLVED`**  
**Residual severity: `MAJOR`**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/18` | Criteria imported invalid rows, omitted receipt/dispatch observations, and permitted lifecycle CAS without exact durable authorization preconditions. |
| Exact revised sections examined | All 70 Section 15 criteria; all 22 imports; Sections 6, 7.2-7.3, 10, 13, and 16. |
| Contracts reconstructed | Evidence-stage grammar, runtime oracle grammar, provider authorization receipt, lifecycle authorization precondition, counter/history/new-ack vectors, matrix imports, mocks/emulator claim boundary. |
| Cross-section compatibility | Stage labels, provider authorization, and most vectors agree. WFL-013b/014/015a/015b and imports of F27/F28 inherit unresolved or contradictory contracts. |
| Delivered AEP compatibility | No criterion permits fallback, mutation replay, second capability use, or production activation. |
| Stage 2 semantic invention | Required to choose recovery count semantics, deletion time/audit binding, retention receipt classes, reconciliation call decomposition, and facade-versus-adapter delete counters. |
| Provider-specific dependency | The 13 provider, one operational, and three independent criteria remain future evidence. Mocks/emulators correctly prove application contracts only. |
| Acceptance evidence | Counts/distribution/import existence are verified. No production criterion has passed. |
| Residual limitation | A syntactically complete vector that depends on an internally contradictory contract is not a complete oracle. |

The structural claims are correct: 70 unique criteria, exactly one label each, distribution `53/13/1/3`, 22 existing imports, explicit `N/A` only for non-runtime review, and 13 provider rows covered by the exact signed/durable `ProviderTestAuthorizationReceipt`. `PVK-STR-006d` now also requires the operation-specific durable selector authorization receipt. Counter, history, acknowledgement, dispatch, and mock/emulator claim boundaries are markedly improved.

The set is not semantically complete:

- `PVK-WFL-013b` says exact status/progress/version follows Section 7.2, but Section 7.2 gives contradictory increment-versus-61 behavior for early permanent ambiguity. It also names `Connector.readback=NEW` without an exact closed Method/result wrapper or a call-count member for that read-only provider interaction.
- `PVK-WFL-014` cannot test a trusted minimum interval because the observation time is not bound to the signed time sample or durable audit event.
- `PVK-WFL-015a` requires authenticated provider-lock and backup facts for which no closed receipt class/method/result exists.
- `PVK-STR-004d`, `PVK-STR-005`, `PVK-KMS-006`, `PVK-WFL-006b`, and `PVK-WFL-006c` import F27/F28 call/result decompositions that conflict with or are absent from Section 6.3.
- `PVK-WFL-015b` says it exercises `delete_material_exact` “/object adapter” with `L0/A0`. The facade contract must reauthenticate/revalidate and obtains the pre-delete audit inside the same high-level invocation; callers cannot supply it. If the case is instead an isolated `request_envelope_delete_exact` adapter test, `NO_PROVIDER_CALL` and `POLICY_DENIAL` are invalid adapter inputs and cannot exercise the three-class facade behavior. The criterion leaves Stage 2 to choose which operation its counters describe.

These gaps affect executable acceptance of state, deletion, retention, and lifecycle mutation boundaries. They are `MAJOR`, independently of the blocking underlying contracts.

## 11. `PVK-RR2-08` disposition

**Disposition: `RESOLVED`**  
**Residual severity: none; traceability remains non-probative**

| Required disposition evidence | Independent result |
|---|---|
| Original defect from `docs/18` | A literal audit-mode pipe made the `PVK-RR-04` trace row render with extra columns. |
| Exact revised sections examined | 19.1-19.4 and every referenced correction row/section. |
| Contracts reconstructed | Four declared trace-table shapes, unescaped-pipe parser, row inventory, all eight RR2 mappings. |
| Cross-section compatibility | All rows render with their declared columns. Each RR2 row identifies sections, correction, contract, matrix rows, acceptance criteria, provider dependency, and a residual-limitation cell. |
| Delivered AEP compatibility | Traceability changes no AEP behavior. |
| Stage 2 semantic invention | Not required for table parsing or finding-to-section linkage. |
| Provider-specific dependency | None for formatting; provider dependencies remain as stated in the substantive rows. |
| Acceptance evidence | 33 rows reproduced as `10+6+8+9`; zero malformed rows across all 45 Markdown tables. |
| Residual limitation | Traceability records claims; it does not validate the substantive corrections, several of which remain incomplete above. |

The audit-mode literal is escaped in both the parent and RR2 trace rows. All `PVK-RR2-01` through `PVK-RR2-08` rows render as eight columns, and the reported 33-row total is independently reproducible.

## 12. Parent-finding reassessment

| Parent finding | Reassessment | Basis |
|---|---|---|
| `PVK-RR-01` | **`PARTIALLY RESOLVED`** | Production representation, version separation, capacity, creation fence, lease, TTL, CAS, and preflight are repaired; late permanent-ambiguity recovery progress remains `BLOCKING`. |
| `PVK-RR-02` | **`RESOLVED`** | The previously accepted authenticated envelope/lifecycle/receipt hash graph and acyclic construction remain intact. The new retention-evidence interface gap is classified under RR2-04; no prior hash construction was weakened. |
| `PVK-RR-03` | **`PARTIALLY RESOLVED`** | Wrappers, dispatch authority, and delete target/class authority are repaired; deletion time/audit authentication, retention provider evidence, and control-inspection interfaces remain `BLOCKING` or `MAJOR`. |
| `PVK-RR-04` | **`PARTIALLY RESOLVED`** | 62 split rows and corrected audits exist, but lifecycle reconciliation methods/results/counters are not cross-sectionally exact. |
| `PVK-RR-05` | **`PARTIALLY RESOLVED`** | 70 one-stage criteria exist, but several inherit blocking contracts or describe ambiguous operations/counters. |
| `PVK-RR-06` | **`RESOLVED`** | Safe identifiers, raw provider input reduction, pseudonym construction/key lifecycle, typed event payloads, and metric restrictions remain frozen. |

Because RR2-01, RR2-03, and RR2-04 are not resolved, the corresponding parents cannot be promoted. Because RR2-06 and RR2-07 are not resolved, their matrix and acceptance parents cannot be promoted. The condition that all six parents be `RESOLVED` is not met.

## 13. Previously resolved finding regression check

### `PVK-RR-02`

**Disposition: `RESOLVED` (preserved).** The prior domain-separated LF32 hash graph, selector/predecessor semantics, signed anchor/hold/release/deletion/tombstone records, receipt and audit hashes, exact construction order, and rewrap allowlist remain present and unchanged in meaning. No circular dependency or previous-envelope-hash/predecessor-link substitution was introduced. The new provider-retention evidence type is incomplete, but it does not alter the previously accepted hash bytes; it is recorded as a new RR2-04 cross-section gap.

### `PVK-RR-06`

**Disposition: `RESOLVED` (preserved).** UUID/safe-ID bounds, external text normalization/rejection, raw provider-byte bounds, every HMAC/LF32 pseudonym construction, pseudonym-key identity/lifecycle, typed-event exclusions, and low-cardinality metric restrictions remain intact. No production implementation or operational DLP evidence exists, as before.

### `PVK-R-01`

**Disposition: `RESOLVED` (preserved).** LF/1 remains a 40-byte header plus bounded raw segments. The independent maximum remains 1,118,276 bytes, with a 1,048,576-byte ciphertext/request domain, checked preallocation arithmetic, exact stream length, and no JSON-envelope fallback. Record/2 base64url capacity is a separate corrected embedding and does not regress LF/1.

### `PVK-R-10`

**Disposition: `RESOLVED` (preserved).** Section 18 retains the exact required sentence that AEP is the paper's primary research contribution and the vault/KMS boundary is supporting infrastructure. Provider experiments remain future work; cloud/KMS novelty and exactly-once external effects are not claimed.

## 14. Cross-section consistency assessment

Sections 5 through 16 were compared operation by operation across method/input, immutable target, result wrapper, counters, receipts/acknowledgements, error/reason, retry, audit mode, dispatch effect, and recovery behavior.

| Operation/boundary | Consistent reconstruction | Residual contradiction |
|---|---|---|
| Material creation | Binding/AAD/context, V1/L1/A1, state creation, persistent TTL, lease, CAS, and I1 order agree. | None in capacity/creation; later recovery progress remains inconsistent. |
| Production intent creation | Global blockers, same-step predecessor, max attempt, version +1, ledger preservation, and no second mutation agree. | Early permanent ambiguity cannot use both increment-by-one and reserved count 61 on later resolution. |
| Dispatch authorization | 14-step read, exact target/binding/profile/deadline, direct new audit, wrapper, one-use consumption, and no recreation agree. | None found in the authority path itself. |
| Authenticated read | Exact lifecycle/envelope/KMS/AEAD/binding path and standalone audit agree; no provenance is returned. | None material to this rereview. |
| Rewrap | Source/candidate reads, unwrap/rewrap/verification, immutable field allowlist, candidate audit, authorization, selector CAS, and result audit agree. | F27's reconciliation call/result decomposition conflicts with the single typed inspection method. |
| Hold/release | Durable authorization before CAS, conservative unknown hold, and A2 non-crash result auditing agree. | No exact control-inspection method/input/status exists for F28 reconciliation. |
| Deletion evaluation | Complete records/hashes/identities are present and unknown evidence fails closed. | Observation time is not tied to signed time/audit evidence; F29 call boundary is not exact. |
| Exact delete | Signed target/class/decision/idempotency/audit tuple and exact result verification agree. | Provider retention/backup receipt types are absent; WFL-015b conflates facade and adapter counters. |
| Recovery | No provider mutation replay, deterministic backoff, bounded observations, and continued fence agree. | Count/ordinal rule for late resolution is contradictory; readback Method/result is not frozen. |
| Audit/reason mapping | One total 26-row map is used by meta, event, matrix, and criteria. F24 remains gating. | Reconciliation Method/result ambiguity changes receipt/meta/audit inputs in affected rows. |
| Privacy/configuration/activation | Safe types, no fallback, structural test/production separation, and no activation surface agree. | Implementation/provider/operational evidence remains absent, not contradictory. |

The revision does not weaken canonical request-binding equality, raw-before-semantic validation, LF/1 framing, the previously accepted authenticated hash graph, safe identifiers/pseudonyms, delivered v1 behavior, V1-before-L1/A1/I1, same-connection `WAITAOF`, durable intent before transport, endpoint/profile/deadline revalidation, direct-new audit before provenance, one-use `VerifiedDispatch`, at-most-one provider mutation, no automatic retry, read-only recovery, fail-closed unknown outcomes, no selector/revision/key/envelope/endpoint fallback, typed privacy boundaries, structural exclusion of activation, the AEP research boundary, or the no-exactly-once claim.

## 15. New or residual findings

| ID | Severity | Finding | Required correction boundary |
|---|---|---|---|
| `PVK-RR3-01` | `BLOCKING` | Recovery requires increment-by-one/no-skip progress but reserves count 61 for a late authoritative resolution even when permanent ambiguity occurred before count 60. | Freeze one legal count/ordinal/version rule for every early and limit-reached terminal path; update transition-cap arithmetic and WFL-013b. |
| `PVK-RR3-02` | `BLOCKING` | Deletion observation `observed_at_ms` is not equated to signed trusted time or audit time, and the durable audit event does not commit to the complete observation facts. | Bind exact observation time to authenticated time evidence, define conservative error arithmetic, and make the durable audit evidence authenticate the observation/raw/lifecycle/binding tuple without a hash cycle. |
| `PVK-RR3-03` | `BLOCKING` | Concurrent retention names provider lock/backup receipt evidence absent from the closed ReceiptClass/Method/result schemas; retention generation and source-to-evidence hash mapping are incomplete. | Freeze exact provider-neutral receipt classes, methods/results, targets/generation, evidence hashes, and all allowed source/evidence combinations. |
| `PVK-RR3-04` | `MAJOR` | F27/F28/F30 reconciliation counters and acknowledgements do not map to the closed lifecycle methods/results. | Define one exact Method/input/result per reconciliation operation and then recalculate calls, returned metas/receipts, audit hashes, and imported rows. |
| `PVK-RR3-05` | `MAJOR` | Several criteria import those rows or conflate facade and adapter operations; state/deletion/retention oracles are therefore not deterministic. | Correct WFL-013b/014/015a/015b and every F27/F28 import after the underlying contracts are frozen; revalidate all 70 criteria. |

No `MINOR` or `DOCUMENTATION` defect independently changes the gate. The three blocking findings and two major findings are sufficient to retain Stage 2 `NO-GO`.

## 16. Verified and unverified guarantees

| Guarantee or claim | Status | Boundary |
|---|---|---|
| 22 numbered sections | `VERIFIED` | Current `docs/15` bytes |
| Four supplied document hashes and LF-only status | `VERIFIED` | Exact current bytes |
| Three protected manifests | `VERIFIED` | Current selected files; no Git-history proof |
| 62 unique matrix IDs | `VERIFIED` | Existence/uniqueness/table shape |
| Matrix semantic completeness | `NOT VERIFIED` | Lifecycle reconciliation method/result contradictions remain |
| 70 unique criteria and `53/13/1/3` stages | `VERIFIED` | Syntax/count/label distribution |
| Acceptance-oracle completeness | `NOT VERIFIED` | State, deletion, retention, reconciliation, and facade/adapter gaps remain |
| 33 trace rows and zero malformed table rows | `VERIFIED` | Markdown shape only |
| Missing matrix imports/provider authorizations/reason mappings | `VERIFIED AS ZERO` | Structural and mapping reconstruction |
| LF/1 framing and record/2 capacity arithmetic | `VERIFIED AS DESIGN` | No codec/Redis/provider capacity result |
| Production creation fence/lease/TTL/CAS/preflight | `VERIFIED AS DESIGN EXCEPT RECOVERY COUNT` | No implementation; blocking late-resolution contradiction |
| Authenticated deletion evidence | `PARTIALLY VERIFIED` | Complete records present; trusted interval/audit commitment incomplete |
| Exact delete authority | `VERIFIED AS DESIGN` | Provider deletion truth absent |
| Conservative concurrent retention | `PARTIALLY VERIFIED` | Aggregation rules present; provider receipt/method evidence incomplete |
| Process-local wrappers and total reason map | `VERIFIED AS DESIGN` | Runtime enforcement unimplemented |
| Delivered v1 current-tree bytes | `VERIFIED AGAINST SUPPLIED MANIFEST` | Git history unavailable; tests not rerun here |
| Durable V1/L1/A1/I1/P1 in production | `UNVERIFIED` | No production implementation/provider |
| Provider durability/CAS/KMS/audit/retention/deletion | `UNVERIFIED` | No provider evidence |
| Operational IAM/key custody/backup/incident/RPO/RTO/DLP | `UNVERIFIED` | No operational evidence |
| Production connector/activation | `ABSENT / NO-GO` | Structurally excluded and unauthorized |
| Exactly-once external effects | `NOT CLAIMED AND NOT GUARANTEED` | Unknown transport outcomes remain unreplayed |
| Universal non-disclosure/zeroization/physical erasure | `NOT CLAIMED AND NOT GUARANTEED` | Explicit boundary |

## 17. Remaining provider and operational dependencies

Even after the provider-neutral blockers are corrected and a later implementation is accepted, separate evidence is still required for:

- exact provider/account/region/tier/topology and fault domain;
- conditional create, immutable read, authoritative absence, CAS/linearization, response-loss status, version/checksum, consistency, and durability;
- Redis capacity/performance for the frozen record/state domain, lease behavior, persistence, and `WAITAOF` topology;
- immutable KMS/HSM key versions, concrete compatible wrap/rewrap algorithm, full context mapping/enforcement, HA/DR, key lifecycle, and receipt semantics;
- lifecycle authority isolation, pinned signing-key custody, anchor monotonicity/rollback resistance, history, CAS durability, and restore behavior;
- audit conditional append, authoritative inspection, durability, delivery, retention, backup, and alerting;
- provider retention locks, legal holds, backup pending/release, deletion/tombstones, delayed purge, and physical-erasure non-claims;
- IAM/cross-environment negatives and registry/pseudonym/commitment/signing-key governance;
- trusted-time, deadline, skew, observation interval, grace, retention, backup, incident, dual-control, approval, RPO/RTO, and SLO policy;
- exact-environment failure injection, outage/restart, regional, performance, capacity, cost, and operational review; and
- later independent provider, operations, connector, deployment, and activation gates.

No provider documentation, account, SDK, resource, IAM policy, deployment, operational policy package, or provider test result was used. These are unverified dependencies, not reasons to weaken or invent Stage 2 semantics.

## 18. Stage 2 authorization boundary

The bounded Stage 2 `GO` conditions are not met:

- only `PVK-RR2-02`, `PVK-RR2-05`, and `PVK-RR2-08` are fully resolved;
- `PVK-RR2-01`, `PVK-RR2-03`, and `PVK-RR2-04` retain `BLOCKING` defects;
- `PVK-RR2-06` and `PVK-RR2-07` retain `MAJOR` defects;
- parent `PVK-RR-01`, `PVK-RR-03`, `PVK-RR-04`, and `PVK-RR-05` cannot be promoted;
- Stage 2 would have to invent recovery state/version semantics, deletion time/audit authentication, retention evidence/method semantics, lifecycle reconciliation results, and acceptance counters; and
- AEP invariants remain stated, but the production state and deletion gates cannot be implemented mechanically from the current text.

Therefore bounded provider-neutral Stage 2 remains `NO-GO`. This rereview authorizes no interface/schema/codec implementation, deterministic backend/test work, production/test composition change, provider/SDK/resource/adapter, connector, deployment, activation mechanism, credential path, or production mutation.

A future documentation-only correction and independent rereview are required. Even a later bounded Stage 2 `GO` would still leave durable production vault/KMS implementation `NO`, provider-specific durability `NO`, production applicability `NO-GO`, first connector `NO-GO`, and production non-idempotent dispatch `NO-GO` until their separate evidence gates pass.

## 19. Final classifications and recommendation

### 19.1 Finding classifications

| Finding | Final classification | Severity/basis |
|---|---|---|
| `PVK-RR2-01` | **`PARTIALLY RESOLVED`** | `BLOCKING`: late permanent-ambiguity resolution count/ordinal/version is contradictory. |
| `PVK-RR2-02` | **`RESOLVED`** | Exact versioned base64url expansion and record/state bounds preserve the full 1 MiB domain. |
| `PVK-RR2-03` | **`PARTIALLY RESOLVED`** | `BLOCKING`: complete records exist, but observation time and durable audit do not authenticate the interval facts. |
| `PVK-RR2-04` | **`PARTIALLY RESOLVED`** | `BLOCKING`: delete authority is exact; provider retention/backup evidence contracts are incomplete. |
| `PVK-RR2-05` | **`RESOLVED`** | Exact two wrappers and total 26-row failure/reason mapping are frozen. |
| `PVK-RR2-06` | **`PARTIALLY RESOLVED`** | `MAJOR`: lifecycle reconciliation rows do not map to closed methods/results. |
| `PVK-RR2-07` | **`PARTIALLY RESOLVED`** | `MAJOR`: several runtime oracles inherit contradictions or conflate operations. |
| `PVK-RR2-08` | **`RESOLVED`** | 33 rows reproduce, every table renders, and all RR2 trace rows are structurally complete. |
| `PVK-RR-01` | **`PARTIALLY RESOLVED`** | Recovery progress remains blocking. |
| `PVK-RR-02` | **`RESOLVED`** | Previously accepted hash graph remains resolved. |
| `PVK-RR-03` | **`PARTIALLY RESOLVED`** | Deletion/retention/control interface semantics remain blocking or major. |
| `PVK-RR-04` | **`PARTIALLY RESOLVED`** | Matrix method/result consistency remains major. |
| `PVK-RR-05` | **`PARTIALLY RESOLVED`** | Acceptance completeness remains major. |
| `PVK-RR-06` | **`RESOLVED`** | Privacy/identifier/pseudonym contract remains resolved. |
| `PVK-R-01` | **`RESOLVED`** | LF/1 framing and size arithmetic remain valid. |
| `PVK-R-10` | **`RESOLVED`** | Research boundary and non-claims remain intact. |

### 19.2 Gate classifications

| Classification | Final result | Basis |
|---|---|---|
| Provider-neutral design | **`REQUIRES REVISION`** | Blocking state, deletion-time, and retention-evidence semantics remain. |
| Design completeness | **`NOT VERIFIED`** | Stage 2 cannot implement every security/state/interface contract without choosing semantics. |
| AEP compatibility | **`PARTIALLY VERIFIED`** | Core delivered invariants are preserved, but production recovery/deletion enforcement is not fully frozen. |
| Readiness for bounded provider-neutral Stage 2 | **`NO-GO`** | Not all RR2/parent findings are resolved; blocking and major issues remain. |
| Durable production vault/KMS implementation | **`NO`** | No implementation exists. |
| Provider-specific durability verification | **`NO`** | No provider evidence exists. |
| Production applicability | **`NO-GO`** | Implementation, provider, operational, connector, deployment, and activation gates are absent. |
| First production connector | **`NO-GO`** | The prerequisite production vault/KMS gate has not passed. |
| Production non-idempotent dispatch | **`NO-GO`** | Must remain disabled; no connector or activation authority exists. |

Recommendation: revise only the provider-neutral design in a separately authorized documentation stage, resolve `PVK-RR3-01` through `PVK-RR3-05`, and perform another independent read-only rereview. Do not begin Stage 2, choose a provider, install an SDK, create an adapter/resource/connector, design activation, or enable production dispatch on the basis of this revision.

Ambiguity, corruption, and contention are detectable; the system fails closed.
