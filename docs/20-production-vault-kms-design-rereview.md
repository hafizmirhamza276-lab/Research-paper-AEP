# Independent rereview of the fifth-corrected production vault/KMS design

Date: 2026-08-01

## 1. Review identity, scope, and authorization boundary

This is an independent, read-only rereview of the exact fifth-corrected revision of `docs/15-production-vault-kms-design.md` whose raw and LF-normalized SHA-256 is `39a6145a1df956d427cc8ddad8dc8f257b3c09e371c683061c00fb27366cd36b`. The authoritative earlier rereview lineage is `docs/19-production-vault-kms-design-rereview.md`.

The review tested the submitted claims against the document bytes. It did not treat the completion summary, traceability tables, stated counts, or self-classifications as proof. It reviewed provider-neutral correctness, completeness, constructibility, internal consistency, traceability, preserved AEP invariants, and the four submitted fifth-correction subjects.

The authorization boundary was observed. No provider, account, region, KMS/HSM, lifecycle system, audit service, object store, Redis deployment, credential, SDK, connector, production resource, feature flag, activation mechanism, source file, test, configuration, manifest, dependency, lockfile, schema/codec implementation, or deployment was selected, accessed, installed, created, or changed. Stage 2 was not begun. This report is the only permitted artifact.

Independent outcome: the input-integrity gate passed, but two `BLOCKING` provider-neutral defects remain. The revision is not ready for bounded Stage 2.

## 2. Exact reviewed hashes and line-ending status

The mandatory gate was executed before this report existed.

| File | Raw SHA-256 | LF-normalized SHA-256 | Bytes | CRLF | Bare CR | Result |
|---|---|---|---:|---:|---:|---|
| `docs/15-production-vault-kms-design.md` | `39a6145a1df956d427cc8ddad8dc8f257b3c09e371c683061c00fb27366cd36b` | `39a6145a1df956d427cc8ddad8dc8f257b3c09e371c683061c00fb27366cd36b` | 367,952 | 0 | 0 | Exact match; LF-only |

The raw byte count corresponds to 1,544 LF terminators and 1,545 logical lines. UTF-8 decoding and LF normalization changed no byte. The gate command exited `0`. A mismatch would have stopped the review without creating this file.

Additional lineage hashes independently observed were:

| File | SHA-256 | Bytes | Line endings |
|---|---|---:|---|
| `docs/16-production-vault-kms-design-review.md` | `86ddecad00d0705bf5791f79eb4a3a01fa77a8663532285c4310bdb6f2c9853a` | 52,315 | LF-only |
| `docs/17-production-vault-kms-design-rereview.md` | `531d00f51c1826d4e59feb22dee1ef3c24a2511d11d85234e9f4d116985966e3` | 60,494 | LF-only |
| `docs/18-production-vault-kms-design-rereview.md` | `6cb052a336616b94817b4352840f20925cfd846a5a6309ef891df42ea99299ba` | 68,380 | LF-only |
| `docs/19-production-vault-kms-design-rereview.md` | `cf835608ca38322e907e68d27394a646da2e3b101fdf1357cc8a1c77e2c41af3` | 59,894 | LF-only |

## 3. Documents and evidence inspected

`docs/15` lines 1-1,545 and `docs/19` lines 1-577 were read completely. Relevant lineage and invariant evidence was inspected in `docs/16` through `docs/18`, including the original findings, preserved-AEP assessments, later residual-finding tables, test-baseline statements, and Stage 2 boundaries. Their hashes match the lineage recorded by `docs/19`.

The current `src` and `tests` file set was read only for manifest/invariant verification. The exact historical manifest algorithm reproduced 88 files and SHA-256 `b3d60014240692936afdaf2b37be0ea51fe9e327a6c06a0a8013c40e96d5bb8a`, matching `docs/19`. The three-file configuration manifest reproduced SHA-256 `eaef6ce9bbe12f4c8b766489d976886433ec43ff4d89a7923e32894189fd4e63`.

Git metadata remains unusable: `git status --short` exited `128` because this directory is not a Git repository. Accordingly, this report makes no Git-history claim. A full current-tree manifest excluding the not-yet-created `docs/20` was captured before the write: 146 files, SHA-256 `a7f8471f684ba99b8bd8b41d033c2620e3953237c85115bcbc758e85fc8ab5d0`, using repository-relative POSIX paths, lowercase file hashes, ordinal path sorting, TAB-separated rows, LF joining, and no final LF.

No application test was run. The retained historical baseline is `611 passed` with zero recorded failures and skips; it is not a result of this rereview and does not test these unimplemented production contracts.

## 4. Independent review methodology

The review used the following independent checks:

1. Byte-level raw/LF-normalized hash and CRLF/bare-CR gate before any write.
2. Complete numbered reads of `docs/15` and `docs/19`, with targeted lineage reads from `docs/16` through `docs/18`.
3. Reconstruction of the policy, observation, retention, deletion-decision, authorization, current-inspection, local-revalidation, audit, adapter, result, and tombstone byte graph.
4. Enumeration of every allowed `RetentionSource` plus `RetentionEvidenceClass` row and every provider-package reconstruction step.
5. Counterexample analysis for caller control, expiration boundaries, missing canonical bytes, ambiguous projections, duplicate/order changes, stale evidence, and pre-provider zero-call behavior.
6. Mechanical parsing of numbered sections, matrix IDs, acceptance IDs/stages/imports, trace rows, and Markdown tables.
7. Targeted stale-contract searches. References to older versions were accepted only where the text explicitly supersedes, rejects, or preserves them outside the current retention/deletion boundary.
8. Pre/post manifests rather than Git history, because `.git` supplies no usable repository metadata.

Representative verification results were:

| Command/check | Exit | Independently observed result |
|---|---:|---|
| Raw/LF-normalized SHA-256 and CRLF/bare-CR gate | 0 | Both hashes exact; CRLF 0; bare CR 0 |
| Structural parser for Sections 10, 15, and 19 plus all Markdown tables | 0 | All submitted counts reproduced; zero malformed rows |
| `rg` for active old fact/state/package/evaluation/authorization schema literals | 1 | Zero matches; exit 1 is the expected no-match result |
| `rg` for V1-V3 fact/aggregate commitment domains at the current boundary | 1 | Zero matches; exit 1 is the expected no-match result |
| `rg` for unsupported positive production/provider/connector/dispatch gate claims | 1 | Zero matches; exit 1 is the expected no-match result |
| `git status --short` | 128 | Not a Git repository; no Git claim made |

## 5. Findings, ordered by severity

### `PVK-RR4-05` — `BLOCKING` — `RetentionFact/4` source/evidence normalization is not mechanically total

Precise evidence: Section 6.1, especially `docs/15:210-228`; provider backup result vocabulary at `docs/15:275` and `docs/15:300`; hash definitions at `docs/15:727-735`; tombstone hash/signature contracts at `docs/15:718`, `docs/15:892`, and `docs/15:925`; and `PVK-WFL-015a` at `docs/15:1346`.

The correction materially separates raw evidence, primary-result hash, receipt reference, semantic fact commitment, and ordered aggregate. It nevertheless leaves three implementation choices:

- `docs/15:212` names `aep.signed-retention-hold-evidence/2`, `aep.signed-hold-release-evidence/2`, and `aep.signed-lifecycle-retention-control/2`, but does not enumerate their complete strict unsigned/signed field sets. Saying that they “add” listed fields does not identify a complete base record, exact required/null fields, or constructible canonical fixture.
- The exhaustive row at `docs/15:223` does not map `ProviderBackupStatus/2.classification=BACKUP_PURGED_EXACT` and receipt/3 `provider_backup_state=PURGED` to exact `RetentionFact/4.state`, `classification`, and `backup_condition` values. The deletion-requested row at `docs/15:224` similarly names only the resulting classification and does not freeze the corresponding fact state, backup condition, and all class-dependent null/value projections.
- The `SIGNED_TOMBSTONE` row at `docs/15:226` requires a “Tombstone/2 raw hash,” but the retention raw-evidence rule at `docs/15:727` and the exact V2 raw domains at `docs/15:733-735` define no tombstone raw-evidence domain and do not explicitly equate `raw_evidence_hash` with the separately defined `AEP-TOMBSTONE-HASH-V2` value.

Concrete counterexample: a package with class `PROVIDER_BACKUP`, method `inspect_provider_backup_retention_exact`, classification `BACKUP_PURGED_EXACT`, receipt state `PURGED`, exact target/identity/generation/token, valid policy/time/signature evidence, and recomputable manifest/receipt/reference hashes completes offline steps 1-7. At step 8, one implementation can emit `INACTIVE/RELEASED_EXACT/PURGED`, another can reject the known classification, and the current text supplies no exact normalized tuple. They therefore compute different or absent fact commitments. Independently, two tombstone implementations can use `AEP-TOMBSTONE-HASH-V2` or invent a new retention-raw domain, again producing different commitments from the same signed bytes.

Why existing acceptance criteria do not prevent this: `PVK-WFL-015a` says to validate every mapping, but supplies no canonical field-by-field expected fact or golden hash for `BACKUP_PURGED_EXACT`, deletion-requested unknown/acknowledged, or `SIGNED_TOMBSTONE`. It also cannot construct golden bytes for the three partially specified V2 non-provider schemas. An oracle cannot resolve an ambiguity in its normative source.

Minimum documentation correction: freeze the complete strict unsigned and signed field sets, order, null rules, bounds, and exact domains for all three V2 non-provider evidence schemas; define the tombstone `raw_evidence_hash` domain or exact equality to the existing tombstone hash; enumerate every `RetentionFact/4` field/value/null projection for every admissible raw classification, including backup purged and both deletion-requested outcomes; then add exact canonical/golden commitment vectors for those cases to `PVK-WFL-015a`.

### `PVK-RR4-06` — `BLOCKING` — deletion-decision expiry has no exact conservative immediate-revalidation predicate

Precise evidence: the exact trusted-time interval at `docs/15:374`; policy activation/expiration rule at `docs/15:378`; initial eligibility expiry rule at `docs/15:387-390`; immediate revalidation at `docs/15:335`; adapter reauthentication at `docs/15:291`; signed decision expiry equality at `docs/15:924`; and criteria `PVK-WFL-015b/c` at `docs/15:1347-1348`.

Initial eligibility is exact: it requires `trusted_now.upper_ms < eligibility_expires_at_ms`. The immediate revalidation contract later requires only that the “decision [is] unexpired,” while separately spelling out `trusted_now.lower_ms >= grace_not_before_ms`. Neither that rule nor the adapter rule states whether decision expiration is checked against the fresh interval's lower endpoint, center, or upper endpoint.

Concrete counterexample: let signed decision/context expiry be `E`, let the fresh trusted-time center be `E-50`, and let `maximum_error_ms=100`; grace is already satisfied and the timing policy itself expires later. The fresh interval is `[E-150,E+50]`. A center- or lower-bound interpretation treats the decision as unexpired and can reach the pre-delete audit and provider call. The conservative upper-bound interpretation returns `STALE` before both. All authenticated bytes and equality checks can otherwise match, so Stage 2 must choose a destructive-authority semantic.

Why existing acceptance criteria do not prevent this: `PVK-WFL-015b` names an “expired decision” but freezes no straddling-interval boundary vector or endpoint predicate. `PVK-WFL-015c` tests altered/mismatched authority bytes, not a valid signed decision whose fresh uncertainty interval overlaps expiry. Both implementations can therefore claim conformance.

Minimum documentation correction: require, in both local `VALID_EXACT` revalidation and isolated adapter verification, checked exact equality of the context and signed-decision expiries plus `trusted_now.upper_ms < authority_context.eligibility_expires_at_ms`; equality must fail closed. Add lower/center/upper boundary vectors to `PVK-WFL-015b/c`, with the facade overlap case fixed at `O0/L1/A0/C0` and the isolated adapter overlap case at all-zero dependency calls.

No `MAJOR` or `MINOR` finding was identified. The two blocking findings are independently sufficient to keep Stage 2 closed.

## 6. Fifth-correction finding dispositions

| Submitted correction subject | Disposition | Independent evidence |
|---|---|---|
| Authenticated deletion timing policy (`PVK-RR4-01`) | `RESOLVED` | `docs/15:374-387` freezes policy/1 canonical bytes, signature/digest domains, immutable environment/namespace/configuration mapping, predecessor replay rules, numeric/error/age bounds, checked arithmetic, conservative activation/policy-expiration intervals, caller exclusion, observation interval, and deterministic grace/eligibility expiry. The same tuple is carried through observations, retention aggregate, authority context, signed decision, authorization, inspection, audits, adapter input, results, and tombstone. `PVK-RR4-06` concerns the separate signed decision expiry predicate during immediate revalidation, not policy/1 expiration. |
| Complete cryptographic retention semantics (`PVK-RR4-02`) | `PARTIALLY RESOLVED` | Fact/4 and state/4 commit far more complete semantics, explicit nulls, ordering, raw/result/reference separation, and derived state. `PVK-RR4-05` shows that several accepted raw schemas/projections and one raw-hash domain remain unconstructible or non-total. |
| Constructible deletion revalidation (`PVK-RR4-03`) | `PARTIALLY RESOLVED` | `docs/15:327-335` and `docs/15:390-409` make the input constructible from authorization/receipt, one named read-only inspection, immutable target, and trusted time; context, generations, hashes, evidence bytes, counters, and zero-call failure placement are explicit. `PVK-RR4-06` leaves the decision-expiry acceptance predicate open. |
| Offline provider retention evidence reconstruction (`PVK-RR4-04`) | `PARTIALLY RESOLVED` | `docs/15:273-290` and `docs/15:739-769` retain canonical manifest/receipt bytes and mechanically reconstruct hashes/reference through step 7 without a provider call. `PVK-RR4-05` prevents deterministic steps 8-10 for at least the backup-purged path, so the full ten-step claim is not closed. |

## 7. Inherited `PVK-RR3-01` through `PVK-RR3-05` dispositions

| Finding | Disposition | Independent evidence |
|---|---|---|
| `PVK-RR3-01` | `RESOLVED` | `docs/15:644-656`, `docs/15:1035`, and `PVK-WFL-013b` freeze sequential `previous+1` count/ordinal/version progress, natural operator `k+1`, no sentinel jump, exact readback result/counter, and a maximum of 63 transitions under the 64-entry cap. |
| `PVK-RR3-02` | `RESOLVED` | `docs/15:379-387`, `docs/15:723-752`, and `docs/15:773-777` freeze the acyclic commitment -> event -> receipt -> final-observation chain, authenticate observation/acknowledgement times, and enforce conservative ordered intervals with checked arithmetic. |
| `PVK-RR3-03` | `PARTIALLY RESOLVED` | Provider retention/backup targets, read-only methods/results, provider receipt/manifest/reference bytes, and complete fact/aggregate structures now exist, but `PVK-RR4-05` leaves allowed fact construction and projection non-total. |
| `PVK-RR3-04` | `RESOLVED` | `docs/15:321-357` gives one exact selector inspection, one control-mutation inspection, and one current-deletion-control inspection; F27/F28/F30 and their criteria consistently count the corresponding calls/results without hidden methods. |
| `PVK-RR3-05` | `PARTIALLY RESOLVED` | The facade/adapter criteria are separated and the criteria/matrix inventories are structurally exact, but `PVK-WFL-015a-c` do not resolve or detect the two blocking normative ambiguities above. |

## 8. Structural/count verification

The structural claims were recalculated from physical rows and parsed table shape, not copied from Section 19.5.

| Item | Independently recalculated result |
|---|---:|
| Numbered level-2 sections | 22, exactly `1` through `22` |
| Section 10 matrix rows | 64 physical, 64 unique |
| Section 15 criteria | 71 physical, 71 unique |
| `CONTRACT` criteria | 54 |
| `PROVIDER` criteria | 13 |
| `OPERATIONAL` criteria | 1 |
| `INDEPENDENT_REVIEW` criteria | 3 |
| Exact Section 10 import occurrences | 25 |
| Unresolved imports | 0 |
| Duplicate criterion/import pairs | 0 |
| Section 19 trace rows | 42 = `10+6+8+5+4+9` |
| Markdown tables | 48 |
| Rows with inconsistent Markdown column count | 0 |
| Duplicate matrix IDs | 0 |
| Duplicate acceptance IDs | 0 |

The 25 import occurrences are owned by 25 distinct criteria and resolve to 21 matrix target IDs; intentional reuse of F27 and F30 by different criteria is not a duplicate criterion/import pair. Every imported target exists.

The stale-schema searches found no active old fact/state/package/evaluation/authorization schema literal, no V1-V3 fact/aggregate commitment domain at the current boundary, and no positive provider/production/connector/dispatch gate claim. Older names occur only in explicit supersession, rejection, lineage, negative tests, or non-retention compatibility text. No active caller-selected deletion interval/grace, raw-evidence-only aggregate, naked primary-result hash acceptance, unstated deletion lookup, or self-acceptance claim was found.

## 9. Preserved-invariant assessment

The fifth revision does not weaken the protected AEP invariants:

- exact decoded Redis request-binding bytes remain the sole authority;
- raw state validation precedes semantic interpretation;
- delivered version-1 encodings and production version separation remain explicit;
- V1 precedes L1/A1/I1, and I1 remains CAS plus same-connection `WAITAOF`;
- complete I1/P1 preflight precedes transport;
- endpoint/profile/deadline revalidation and a direct `NEW` dispatch audit precede one-use provenance;
- one process-local capability permits at most one connector mutation, with no automatic retry, redirect replay, or failover;
- recovery remains read-only with respect to application/provider mutation and uses sequential evidence CAS only;
- unknown outcomes fail closed, no fallback path is introduced, and pre-provider failures keep connector count zero;
- typed telemetry exclusions, structural Stage 2 activation exclusion, the AEP research-contribution boundary, and the no-exactly-once claim remain intact.

These preserved invariants support `AEP compatibility` at the provider-neutral design level. They do not cure the two deletion/retention completeness defects and do not constitute implementation or production evidence.

## 10. Residual provider and operational dependencies

Even after the two documentation defects are corrected and independently accepted, separate evidence remains required for exact provider/account/region/tier/topology; conditional create/CAS/read/absence and response-loss truth; Redis capacity, persistence, lease, and `WAITAOF`; KMS/HSM immutable version/context/HA/DR behavior; lifecycle snapshot/signature/anchor/CAS durability; provider retention/backup/delete tokens and receipts; provider-evidence, policy, and trusted-time signer custody; audit append/delivery/retention; IAM and cross-environment negatives; backup/restore, legal hold, purge, key lifecycle, incident, RPO/RTO/SLO, performance, and cost; and later connector/deployment/activation reviews.

The reconstructed provider package proves internal canonical consistency only. It does not prove provider durability, lock truth, backup purge, physical deletion, future irrecoverability, key zeroization, or exactly-once effects.

## 11. Gate classifications

| Gate | Independent classification | Basis |
|---|---|---|
| Provider-neutral design | `REQUIRES REVISION` | `PVK-RR4-05` and `PVK-RR4-06` are blocking provider-neutral defects. |
| Design completeness | `NOT VERIFIED` | Stage 2 would have to choose fact bytes/projections and a destructive decision-expiry predicate. |
| AEP compatibility | `VERIFIED AT PROVIDER-NEUTRAL DESIGN LEVEL` | Protected AEP invariants are preserved; no implementation evidence is implied. |
| Readiness for bounded provider-neutral Stage 2 | `NO-GO` | Blocking documentation semantics remain; mechanical implementation is not yet possible. |
| Durable production vault/KMS implementation | `NO` | No implementation exists or was authorized. |
| Provider-specific durability verification | `NO` | No provider/environment evidence exists or was accessed. |
| Production applicability | `NO-GO` | Implementation, provider, operational, deployment, connector, and activation gates remain open. |
| First production connector | `NO-GO` | Its prerequisite vault/KMS and separate connector gates have not passed. |
| Production non-idempotent dispatch | `NO-GO` | It remains structurally disabled and unauthorized. |

## 12. Final recommendation

Bounded provider-neutral Stage 2 remains `NO-GO`. Correct only the provider-neutral documentation defects in `PVK-RR4-05` and `PVK-RR4-06`, then perform another independent read-only rereview. Do not begin implementation, provider selection, provider tests, connector work, deployment, activation design, or production dispatch from this revision.

The final verification sequence recomputed the protected design hash, compared the full pre/post manifest excluding this report, checked the protected document/source/test/configuration/dependency manifests, confirmed this report is the only new file, and validated this report's required headings, finding IDs, dispositions, Markdown tables, and line endings. Final observed values and exit codes are recorded below after the completed write:

| Final verification | Exit | Result |
|---|---:|---|
| Recompute `docs/15` raw/LF hash and line endings | 0 | Both hashes remain `39a6145a…cd36b`; CRLF 0; bare CR 0 |
| Compare 146-file pre/post manifest excluding `docs/20` | 0 | Count remains 146 and manifest remains `a7f8471f…8ab5d0` |
| Verify protected docs/source/tests/config/dependency hashes | 0 | `docs/15`-`docs/19`, 88-file source/tests, three-file configuration, and dependency/lock selection all match their pre-write hashes |
| Confirm only `docs/20-production-vault-kms-design-rereview.md` is new | 0 | Total file count changed from 146 to 147; exactly one path is `docs/20` |
| Validate report headings, IDs, dispositions, tables, and LF-only bytes | 0 | 12 required numbered headings; 2 unique finding definitions; allowed dispositions only; 8 valid tables; zero malformed rows/CRLF/bare CR |

Tests were not rerun. The historical 611-test baseline is retained without being represented as current execution evidence.
