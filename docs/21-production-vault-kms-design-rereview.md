# Independent rereview of the sixth-corrected production vault/KMS design

## 1. Review identity, scope, and authorization boundary

This is the independent, read-only rereview of the exact sixth-corrected production vault/KMS design requested on 2026-08-01. The primary reviewed artifact is `docs/15-production-vault-kms-design.md`; `docs/20-production-vault-kms-design-rereview.md` is the authoritative prior independent rereview. This report determines whether the sixth correction mechanically closes `PVK-RR4-05` and `PVK-RR4-06` and independently reassesses the specified fifth-correction and inherited findings.

The review was limited to repository bytes and in-memory mechanical checkers. It did not select or access a provider, account, region, KMS/HSM, object store, lifecycle service, audit service, Redis deployment, production environment, credentials, deployment, feature flag, connector, or activation mechanism. It did not change the reviewed design, source, tests, configuration, manifests, dependencies, lockfiles, schemas, codecs, providers, adapters, SDKs, or production data. It did not begin Stage 2. The only repository write made for this review is this report.

Design acceptance and implementation or operational evidence are separate gates. Provider-specific behavior intentionally deferred by the design is not treated as a defect unless the provider-neutral contract is itself incomplete, contradictory, or nonconstructible.

## 2. Exact reviewed hashes and line-ending status

The input-integrity gate passed before this report was created.

| Artifact | Bytes | Raw SHA-256 | LF-normalized SHA-256 | CRLF sequences | Bare CR sequences | Gate |
|---|---:|---|---|---:|---:|---|
| `docs/15-production-vault-kms-design.md` | 423860 | `69e78ea6c3a703eec8c621c1d758ca9cd53f78f4b03297a1483e9f9d80a15f2d` | `69e78ea6c3a703eec8c621c1d758ca9cd53f78f4b03297a1483e9f9d80a15f2d` | 0 | 0 | PASS |
| `docs/20-production-vault-kms-design-rereview.md` | 22644 | `4a36ba04a610272bfe34c71161b090c061a9d631fd39c51de66fc0a3bc7ecb80` | `4a36ba04a610272bfe34c71161b090c061a9d631fd39c51de66fc0a3bc7ecb80` | 0 | 0 | PASS |

Thus the design revision reviewed is exactly `69e78ea6c3a703eec8c621c1d758ca9cd53f78f4b03297a1483e9f9d80a15f2d`, with LF-only bytes. No completion statement, printed digest, traceability claim, or supplied count was used as proof of those facts.

## 3. Documents and evidence inspected

`docs/15` and `docs/20` were read completely. `docs/16` through `docs/19` were inspected only where needed to establish finding lineage, prior dispositions, preserved invariants, and the historical test/manifests boundary.

The pre-review hashes of the lineage documents were:

| Artifact | Raw SHA-256 | Bytes | Use in this review |
|---|---|---:|---|
| `docs/16-production-vault-kms-design-review.md` | `86ddecad00d0705bf5791f79eb4a3a01fa77a8663532285c4310bdb6f2c9853a` | 52315 | Targeted lineage inspection |
| `docs/17-production-vault-kms-design-rereview.md` | `531d00f51c1826d4e59feb22dee1ef3c24a2511d11d85234e9f4d116985966e3` | 60494 | Targeted lineage inspection |
| `docs/18-production-vault-kms-design-rereview.md` | `6cb052a336616b94817b4352840f20925cfd846a5a6309ef891df42ea99299ba` | 68380 | Targeted lineage inspection |
| `docs/19-production-vault-kms-design-rereview.md` | `cf835608ca38322e907e68d27394a646da2e3b101fdf1357cc8a1c77e2c41af3` | 59894 | Finding definitions and regression baseline |

The delivered source and test tree was inspected read-only for the frozen V1 contracts named by the request. No application test was executed. The only test statement retained is the historical baseline recorded in `docs/19`: 611 passed, zero failed, zero skipped. That historical result is not evidence that this documentation revision is correct.

## 4. Independent methodology and mechanical checks

The review used byte-level SHA-256 and line-ending scans; numbered complete reads; parsers for schema member sets, constructor assignments, matrix rows, acceptance IDs, evidence stages, Section 10 imports, traceability rows, headings, and Markdown-table widths; canonical compact sorted-key JSON; LF32 domain construction; SHA-256; Ed25519 derivation/signing from the published fixture seeds; fixture projection and commitment recomputation; interval arithmetic for E1-E12; and targeted stale/contradiction searches.

Important command/check outcomes before report creation were:

| Check | Command family | Exit code | Result |
|---|---|---:|---|
| First hash attempt | PowerShell/.NET `SHA256.HashData` probe | 1 | Host API unavailable; no file written |
| Compatible integrity gate | PowerShell byte reads plus `SHA256.Create()` | 0 | Both required normalized hashes matched; `docs/15` raw also matched; zero CR sequences |
| Git diagnostic | `git status`/diff diagnostic | 129 | Git metadata unusable as a repository; deterministic manifests used instead |
| Pre-review byte manifest | PowerShell recursive file hashing, excluding `.git` | 0 | 147 files; manifest digest `0a62659f498211e123accaa60521a8c4f24fa328eb3343c051e271713ed125de` |
| Full/targeted document reads | PowerShell numbered `Get-Content` reads and `rg` | 0 | `docs/15` and `docs/20` read completely; lineage inspected as scoped |
| Schema/constructor/count parser | In-memory Python | 0 | Counts and assignment sets independently reproduced |
| Canonical/hash/signature fixture checker | In-memory Python with `cryptography 46.0.5` | 0 | Printed digests reproduced under the assumptions identified in `PVK-RR5-02` |
| E1-E12 arithmetic checker | In-memory Python | 0 | All printed intervals and predicate outcomes reproduced |
| Exact stale-pattern searches | `rg` exact-pattern suite | 1 for each zero-match query | Expected zero matches; exit 1 meant “no match” only |
| Broad claim/time searches | `rg` context searches | 0 | Matches were prohibitions, limitations, lineage text, or the required predicate; no contradictory active rule found |

The deterministic pre-review protected manifests were `b3d60014240692936afdaf2b37be0ea51fe9e327a6c06a0a8013c40e96d5bb8a` for 88 source/test files, `eaef6ce9bbe12f4c8b766489d976886433ec43ff4d89a7923e32894189fd4e63` for the three configuration/manifest files, and `8bbe5d14acd6ee04ea4fe92e26511f158c9fe8b793a659536aaeb59218c7c298` for the dependency/lock selection. Section 16 records the post-write comparisons.

## 5. Findings ordered by severity

### PVK-RR5-01 — BLOCKING — the complete provider fact constructor reads a field absent from its strict package schema

Affected text: `docs/15` Section 6.1, especially lines 206, 230, and 303; the PB1/PD1/PD2 fixtures at lines 1357-1359; and `PVK-WFL-015a` at line 1452.

`ProviderRetentionEvidencePackage/1` is a strict, complete schema, but it has no `material_identity_hash` member. Nevertheless the sole provider constructor assigns `RetentionFact/4.material_identity_hash=p.material_identity_hash` at line 230. The strict package instead contains an `exact_receipt_target`; a provider-retention target has a material hash, while an exact-envelope target does not. The receipt manifest/reference schemas carry related nullable projections, but the constructor does not select or define any of them as its source.

Concrete failure path: PB1 can be strict-decoded, signature-verified, and package-hash verified through the offline reconstruction sequence. At fact projection, `p.material_identity_hash` is undefined. An implementation must either reject PB1, derive the value from `PT0`, or silently invent a package property. PD1 and PD2 make the ambiguity sharper because their exact receipt target is an `ExactEnvelopeTarget`, while their manifest/reference material-identity projections are nullable. These choices do not yield the same complete fact and are not authorized by the normative constructor.

The exhaustive mapping table does not prevent or detect this defect: every accepted provider row delegates to `P`, and `PVK-WFL-015a` repeats the demand to compare the `P` tuple without defining the missing projection source. Syntactically, `P` names all 49 fact members once; semantically, one assignment is unconstructible. Consequently provider classifications, including the required backup-purged and deletion-requested rows, do not yet produce exactly one constructible `RetentionFact/4` tuple.

Minimum documentation correction: define one exact authenticated source for provider-fact `material_identity_hash`. Either add the member to the strict package and bind it with class-specific null/equality rules and package hashing, or project it explicitly from the verified target/manifest/receipt reference with exact target-class rules. Then update the ten-step verifier, all provider mappings, PB1/PD1/PD2 full tuples, commitments, and `PVK-WFL-015a` oracle as needed.

### PVK-RR5-02 — MAJOR — the golden fixtures do not close all required authenticated time/signature inputs or the ordered aggregate

Affected text: `docs/15` `SignatureEvidence` at line 200, the envelope verification constraint at line 220, `TrustedTimeEvidence` at line 404, Section 14.5 at lines 1339-1360, `RetentionState/4` at lines 259-268, and `PVK-WFL-015a` at line 1452.

The fixture table supplies signed-time sample centers, error, environment, source, sample IDs, and key seed, but not a complete `TrustedTimeEvidence` wrapper, its exact receipt-reference digest, its nested `SignatureEvidence`, or an exact `verified_at_ms`. More importantly, the accepted schema only constrains `SignatureEvidence.verified_at_ms >= observed_at_ms`; it does not make equality a fixture rule. The fact commitment includes `signature_evidence_hash`, so multiple schema-valid fixtures follow from the published values.

Concrete counterexample: for RH1, choosing the natural but unstated `verified_at_ms=800` reproduces the printed signature-evidence hash `VF2XpYjEPIALd2_vw9adpLV0ZLMs65MK4x7-60bT-ts`. Choosing the equally schema-valid value `verified_at_ms=801` produces `Ss_wtGG6iOEi7vz29vu2iDtUfji6YFx7tdMCyiqozz8`, and therefore a different fact commitment, while all values actually stated by the fixture still hold. The same freedom exists for the other positive fixtures.

Section 14.5 also prints individual fact commitments but does not give a complete positive `RetentionState/4` fixture: the exact aggregate binding values and derived members are not all fixed, and no expected `retention_aggregate_evidence_hash` is supplied. Thus the requested ordered aggregate commitment cannot be independently reconstructed from the normative fixtures alone.

`PVK-WFL-015a` does not detect the gap because it says to compare every signature/fact hash and complete tuple against Section 14.5, which is the incomplete oracle itself. Minimum documentation correction: publish the complete canonical trusted-time wrappers and nested signature evidence for every fixture, fix each verification time and receipt-reference digest explicitly, and add a complete positive `RetentionState/4` fixture with every binding/derived field, ordered commitment list, and expected aggregate hash. Recompute affected printed values if the chosen completion differs from the implicit values used by the existing hashes.

No additional `MINOR` finding was found. The two defects above are substantive and actionable; provider-specific implementation evidence intentionally deferred by the design was not promoted into a documentation finding.

## 6. `PVK-RR4-05` disposition

**PARTIALLY RESOLVED.**

The sixth correction independently closes several distinct parts of the prior finding:

- Lines 212-222 define complete strict V2 unsigned/signed forms rather than “adds fields” deltas: hold unsigned has 27 members, release unsigned 31, lifecycle-control unsigned 28, and each signed envelope 8. Required members, explicit nulls, prohibited members, bounds/enums, authority/key resolution, hash/signature domains, exact signed bytes, canonical round-trip, ordering, equality checks, and failure mappings are explicit.
- `RetentionFact/4` at line 210 has exactly 49 fields, including its schema and final commitment. Mechanical parsing found that `H`, `R`, `C`, `P`, and `TS` each name all 49 fields exactly once with no duplicate, missing, or extra assignment.
- Lines 232-255 provide an exhaustive syntactic classification dispatch, including backup-purged, deletion-requested acknowledged/unknown, deletion achieved, signed tombstone, conflicts, unknowns, duplicates, order, generation/token incompatibility, and scope failures.
- Lines 253, 771, 780, and 818 leave only `raw_evidence_hash=tombstone_hash`, recomputed under `AEP-TOMBSTONE-HASH-V2`; no alternate active retention-tombstone raw domain was found.

However, `PVK-RR5-01` prevents every accepted provider row from constructing its promised complete fact, and `PVK-RR5-02` prevents the golden fixture/aggregate oracle from being uniquely reproduced from normative inputs. The exact requirement of `PVK-RR4-05`—one complete valid fact or one exact rejection for every accepted mapping, plus constructible golden fixtures—is therefore not fully closed.

## 7. `PVK-RR4-06` disposition

**RESOLVED.**

Lines 417, 419, 421, and 442-443 make the destructive-boundary predicate exact: `fresh_trusted_now.upper_ms < authority_context.eligibility_expires_at_ms`, separately combined with `fresh_trusted_now.lower_ms >= authority_context.grace_not_before_ms`. Equality at expiry fails closed. Lower-endpoint, center, wall-clock, caller, provider, database, reused initial-evaluation, and unspecified time alternatives are expressly prohibited.

Line 419 enumerates and requires equality across the signed decision, authority context, eligibility decision, authorized input, decision receipt, current inspection, revalidation input/result, adapter authorization, pre-delete audit, provider-delete result/receipt, and tombstone. Lines 421 and 443 bind distinct authenticated samples at the initial, decision, authorization, post-inspection facade, local revalidation, audit, isolated-adapter, dispatch, result, and tombstone boundaries without hidden lookups. The adapter receives the signed source inspection, exact fresh-time bytes/hash, context, expiry, pre-delete event, and durable receipt in explicit input and reauthenticates locally.

The failure reasons and placement are distinct for decision expiry, policy expiry, grace, missing time, stale/reused time, invalid interval, overflow, authority-context mismatch, and signed-decision mismatch. E1-E12 mechanically agree with those rules and call counts. No substantive counterexample to the corrected expiry closure was reproduced.

## 8. Four fifth-correction subject dispositions

| Fifth-correction subject | Disposition | Independently verified basis |
|---|---|---|
| Authenticated deletion timing policy | **RESOLVED** | Complete signed immutable policy/evidence mapping, authenticated interval arithmetic, exact policy tuple propagation, checked grace/expiry derivation, and dedicated failures remain in Sections 5-8 and 13-15. |
| Complete cryptographic retention semantics | **PARTIALLY RESOLVED** | V4 fact/commitment and exhaustive mapping are materially completed, but `PVK-RR5-01` makes provider facts unconstructible and `PVK-RR5-02` leaves fixture/aggregate authority underdetermined. |
| Constructible deletion revalidation | **RESOLVED** | The exact current read-only inspection, explicit revalidation input/result, equality chain, fresh time, audit receipt, adapter input, reasons, and pre-provider counters are complete; the sixth correction closes the former expiry ambiguity. |
| Offline provider-evidence reconstruction | **PARTIALLY RESOLVED** | Raw/manifest/receipt/reference/package hashes and the ten-step offline verifier are explicit and reproduced, but the final provider-fact projection reads the nonexistent package member identified by `PVK-RR5-01`. |

These dispositions were derived from the sixth-correction bytes, not copied from the author's traceability or `docs/20` conclusions.

## 9. `PVK-RR3-01` through `PVK-RR3-05` dispositions

| Finding | Disposition | Independently verified evidence |
|---|---|---|
| `PVK-RR3-01` | **RESOLVED** | Recovery count/ordinal progression, limits, sole `k+1` operator resolution, version/prior-hash/CAS/barrier behavior, and no skipped/reused count remain explicit in Sections 6, 7, 9, 14, and 15. |
| `PVK-RR3-02` | **RESOLVED** | Signed trusted time, checked intervals, pre-audit observations, immutable timing policy, grace/expiry projection, audit receipt, and failure placement remain fully bound. |
| `PVK-RR3-03` | **PARTIALLY RESOLVED** | Strict provider target/status/receipt/package forms and exhaustive semantic rows exist, but `P.material_identity_hash` has no package source; provider semantics also remain separately unverified as intended. |
| `PVK-RR3-04` | **RESOLVED** | Named read-only selector/control/current inspections, explicit revalidation method/input/result, closed method set, and facade/adapter counter placement are complete and internally consistent. |
| `PVK-RR3-05` | **PARTIALLY RESOLVED** | The 65 matrix rows and 71 criteria are structurally closed and E1-E12 have exact oracles, but `PVK-WFL-015a` cannot uniquely execute the incomplete provider constructor and fixture/aggregate inputs. |

No inherited finding was promoted merely because the sixth-correction traceability table claimed completion.

## 10. Golden-fixture and mapping verification

### 10.1 V2 schemas, constructors, and mapping

The three complete V2 evidence schemas have final member sets and do not depend on an undefined base record, implicit default, unstated inheritance, or accepted older V2 alternative. Strict decoding precedes signature verification and projection. Unsigned hashes use their three V2 domains; Ed25519 signatures cover the exact canonical unsigned bytes under their three signature domains; the environment-pinned authority/key and public-key digest are checked before `SignatureEvidence` construction; all target/environment/execution/intent/request/material/envelope/policy/generation/time equalities and null/prohibited rules precede fact construction.

The 49-field count and syntactic assignment coverage of all five constructors reproduced exactly. `H`, `R`, `C`, and `TS` source every assignment from authenticated bytes, deterministic derivation, exact constant, or explicit null. `P` fails semantic assignment closure only at the nonexistent `p.material_identity_hash` source in `PVK-RR5-01`. Consequently the mapping table is syntactically exhaustive but not constructively total.

The required `BACKUP_PURGED_EXACT/PURGED` row has the sole stated tuple `P(BACKUP_PENDING,INACTIVE,RELEASED_EXACT,PURGED,ack,ref,p,m,r)`, with generation/token/times/result/receipt/package/signature fields inherited from the verified provider bytes and all deletion fields null. The prose correctly limits it to a selected-provider report and does not claim universal purge, physical erasure, or future irrecoverability. The deletion-requested acknowledged tuple remains active/pending and the unknown tuple remains unknown/deletion-denying with null acknowledgement, achieved class, effective deadline, and provider request/delete token. Neither is treated as achieved deletion or erasure.

The tombstone verifier has one rule and one sequence: strict canonical `Tombstone/2` decode; unknown/missing/noncanonical rejection; V2 tombstone-hash recomputation; signed-tombstone verification; retained raw-hash equality; complete `TS` projection; fact-commitment recomputation; ordered aggregate inclusion. Searches found no active alternative raw domain.

### 10.2 Independently recomputed positive values

Canonical JSON, LF32 inputs, SHA-256, public-seed Ed25519 signatures, raw domains, manifests, receipts, references, packages, `SignatureEvidence`, and fact commitments were recomputed independently. The printed values below all match when the checker applies the constructor's apparent intended material projection and the unstated choice `verified_at_ms=observed_at_ms`. That conditional match does not cure `PVK-RR5-01` or `PVK-RR5-02`.

| Fixture | Independently recomputed values |
|---|---|
| RH1 | unsigned SHA `86c797c3dcef08b64f0d469a5d43ca726ca4892b5f7efbdf378da1f44cb59054`; envelope SHA `9c149054c5678bc8ed6311528a517283ad3916a7d7d2aa1e9a876247ef5fe1b1`; raw `Y71_XIgj-Wn5alJRf0ndW1IlqjNZCiWa_N67CJAssC4`; signature evidence `VF2XpYjEPIALd2_vw9adpLV0ZLMs65MK4x7-60bT-ts`; fact `5W99imnKrGNKAKUWkXZT5PbjD8naMkmGla0cZZgkqpA`. |
| RR1 | unsigned SHA `bc347ceb4b81eceeac5be37391235e05af1f7c3fc9f036ce52f4c6c1f46f5d25`; envelope SHA `f30fed0b66f191743179d3573a8adf79a55fe46d341012f666c84f436a63e51b`; raw `UPRbZvPt-KJGr6yMxF-mxC1NLsJ0xT3BRvTVHo4wD3w`; signature evidence `SIk3Y94tf7dbGDaBa5L3mGCD7WA6QLPsUmCIdWdz_CE`; fact `GzIbc87jEht2sHSxo5qQXwMk_Y_tHvd_10njysZTgs0`. |
| RC1 | unsigned SHA `65d384310a56d25a6ec46428b3840ff38701768a9bda38e1fd364e11a57d0545`; envelope SHA `c75f209430229300fe722e59a62148dbb61be382137fe33435e3f01389892040`; raw `jDe2UvwTvVLggEiazIrkdLq7kSoTR2G4jNZ-lA0CJGE`; signature evidence `DTPrg2uoGDcnhW0cSpHf2H2tFXzUr4q9gW3KxpZjIVw`; fact `jlgGEVu6a6srwpjiXxqlVB1dcF2Cwi10J_hJLcysOSU`. |
| PB1 | material identity `xhTJtejwyIa-8U87MtmhHN939Co6Pw_XHtrjFKgGjOA`; manifest `eJT478GtWHzBnVstZehwKPwM7dpWAXbPcrYq8hgEgDs`; receipt `uiRO7yuAydwXGOF936HlJ18ALap8q75PFOMTJoKySOg`; raw `ee3L_XoHQLuTX0LYlT_VaDzO58z6R9NEWpdJgXCy2JM`; reference `cREahKo0nqaSnlsvJMXLomQirXLb_yxSF48Bznuh_pg`; package `MsdB40k_sUABQoT4EovrYvQs5bTjPM5SakoRuwdPT_A`; signature evidence `LTruNx6aEnoJu8mkSTqUgAiW0OfZ5j2dwdbRz-4MBlw`; fact `pRYA33lTA3QX_9XtoLAO1mv7kFuTmU4dMHYHQrLWNPQ`. |
| PD1 | manifest `2AyvC3jC8v68G5gGbOYJ5P4kMnRjBslb2OqpOc8vcIw`; receipt `VdMc0ELOJ-vU0KMK2oruuR_-aVzeFYgD55GnztpLMW4`; raw `brTS5j9B8rcXtBFIbISBQ8QamxCe0UWzItuo1e5mwLc`; reference `of9isktRhC8-pBBz4tZn9BAxCbLrlj2K87Y-jl2KMEU`; package `_-I9QspuVouNUiEg0mm2lGhN4r73tFFBgLTKIvpUzEk`; signature evidence `K1TIR2m7KnnbpaaP6yjpiBMwiQ79wuEHJcPyaNZuXok`; fact `F-XOGFwbeeCJU5IQZUc3L72Yv_o49qr1XxUIHG5AWRs`. |
| PD2 | manifest `zg8eK1leV79Oez2H_yMGSDoCn_8HMxV05OtRBwiz2Yk`; receipt `FRfpFkpf0WxFoTQxSLvxQpL_9CnxS-sXjkKBQ1UEcb0`; raw `ZwBJZzs7Wo6bG5svN_TSgjJDMJ9m__i9cV-U8euL1Ek`; reference `hHywpa-eFlL4egGsrZvqLc5YGqXnK8QH9Rraqw63H4I`; package `NwNF3ahqvkSrlAgfolmbeugwi-6Gkne-Fy5VVzaS4Yk`; signature evidence `dbJoQTNeu2OC8lN3kxaTlhThe8BR58GwrWD7OTs_bwE`; fact `9Md8camaYOA8ju66sUeZNxMo6D6VQsxXo-QpCgp6Mr4`. |
| TS1 | context `fGILlQr833M7viSmXqAj6nLYSxcHGtXUNfsu_ftb9Ts`; signed tombstone plain SHA `c3fadf3cd99ce68226215743a3e215799feeaf69261e3870b73464efbdbe39d2`; tombstone/raw `dqWJ1WQm-RrSsZ74L3OQ3xHy5Sxr5jcnTKUhffZscKo`; receipt set `Wsh6mJ-wOuJjdoKgWsVxsMvUfqsGT9_awsRSipKR_Uc`; signature evidence `c1oUX3qlmInD7HqmF-C6nljd1JCm-y4SX_h9lod2jwg`; fact `DI57mNUpYU7qSuB3kHpAz6yMS7jHUsBOJvFIAz5UMZ4`. |

The mechanically derived fact order is RH1, PB1, RR1, RC1, PD1, PD2, TS1, with the commitments printed above. A complete aggregate digest is not reproducible because Section 14.5 does not close the full aggregate inputs identified in `PVK-RR5-02`.

### 10.3 Negative fixtures

N1-N8 were mechanically/semantically evaluated. N1 rejects at tombstone step 5 as `INTEGRITY/INTEGRITY_FAILURE`; N2 at projection equality/commitment with the same pair; N3 and N4 as `MALFORMED_ENCODING/MALFORMED_ENCODING`; N5 as `CONFLICT/CONFLICT` or `REPLAY/REPLAY_DETECTED` according to its branch; N6 as `WRONG_SCOPE/WRONG_SCOPE`; N7 as malformed; and N8 as conflict. Every case inserts no invalid fact, returns an unknown/indefinite aggregate, remains deletion-ineligible, emits no audit, has `O0/K0/L0/R0/W0/A0/C0`, and makes zero provider mutation/delete calls. Those negative oracles are constructible without provider access. Their correctness does not supply the missing positive provider projection or full aggregate oracle.

## 11. Expiry-boundary and E1-E12 verification

The interval for each numeric vector was independently recomputed as center minus/plus error with checked arithmetic.

| Vector | Recomputed interval or mismatch | Independently reproduced result | Facade placement | Adapter/provider placement |
|---|---|---|---|---|
| E1 | `[910,990]`, expiry 1000 | Grace and strict expiry pass; may proceed only if all other checks pass | Valid delete `O1/K0/L1/R0/W0/A2/C0` | `O1/K0/L0/R0/W0/A0/C0` |
| E2 | `[920,1000]` | `DECISION_EXPIRED`; equality fails | Post-inspection `O0/K0/L1/R0/W0/A0/C0` | All zero; no provider call |
| E3 | `[950,1050]` | `DECISION_EXPIRED`; interval overlaps expiry | Same | Same |
| E4 | `[970,1010]` | `DECISION_EXPIRED`; center-before does not help | Same | Same |
| E5 | `[1000,1040]` | `DECISION_EXPIRED`; lower equality does not help | Same | Same |
| E6 | `[1010,1050]` | `DECISION_EXPIRED`; wholly after expiry | Same | Same |
| E7 | `[950,1050]`, grace 900 | `DECISION_EXPIRED`; satisfied grace does not override expiry | Same | Same |
| E8 | `[850,890]`, grace 900 | `GRACE_NOT_REACHED`; expiry remains future | Same | Same |
| E9 | signed expiry 1000, context 1001 | `SIGNED_DECISION_MISMATCH` | Pre-inspection all zero | All zero |
| E10 | context 1000, input/adapter 999 | `AUTHORITY_CONTEXT_MISMATCH` | Pre-provider all zero | All zero |
| E11 | absent or reused sample | Absent malformed; reused/stale `TRUSTED_TIME_STALE` | Absent all zero; stale after inspection has L1 only | All zero |
| E12 | 8640000000000000 plus 1; or `[1001,999]` | `ARITHMETIC_OVERFLOW`; `INVALID_TIME_INTERVAL` | L1 only when detected after inspection | All zero |

For E2-E8 and stale E11, the facade makes exactly the one named current read-only inspection and no authorized audit or provider delete. E9, E10, and missing E11 reject at the earlier schema/equality boundary with all counters zero. Every rejected adapter vector has all counters zero, no object/provider call, no result audit, and no tombstone claiming authorized mutation. Timing-policy expiry remains a separate `TIMING_POLICY_EXPIRED` reason. “Authority valid at dispatch” is carried into result/tombstone evidence only as the exact dispatch sample/hash/expiry and is not converted into proof of later validity, physical completion, durability, erasure, purge, or irrecoverability.

## 12. Structural/count verification

All submitted totals in this category were independently reproduced; none was accepted from the prose.

| Quantity | Independently reproduced value | Discrepancy |
|---|---:|---|
| Unique Section 10 matrix rows | 65 | None |
| Unique acceptance criteria | 71 | None |
| `CONTRACT` criteria | 54 | None |
| `PROVIDER` criteria | 13 | None |
| `OPERATIONAL` criteria | 1 | None |
| `INDEPENDENT_REVIEW` criteria | 3 | None |
| Traceability data rows | 44 | None |
| Markdown tables | 53 | None |
| Exact Section 10 import occurrences | 26 | None |
| Unique imported matrix rows | 22 | None |
| Unresolved imported rows | 0 | None |
| Duplicate criterion/import pairs | 0 | None |
| Markdown tables with inconsistent column counts | 0 | None |
| `RetentionFact/4` fields | 49 | None |

The 22 imported rows are `F06`, `F14b`, `F15b`, `F17b-H`, `F18-A`, `F19`, `F20a`, `F20b`, `F21`, `F22a-M`, `F22c`, `F23`, `F24a`, `F27`, `F28a`, `F28b`, `F29a`, `F29c`, `F30`, `F30a`, `F30b`, and `F31`. The affected F29/F30/F32 rows and `PVK-WFL-007`, `009`, `014`, `015a`, `015b`, `015c`, `STR-004e`, and `OPS-011` exist and have fixed row imports/counters. Their structure is consistent; the substantive `PVK-WFL-015a` oracle gap remains as `PVK-RR5-01` and `PVK-RR5-02`.

No criterion contains the vague active oracle “validate all fields.” Invalid facts are rejected rather than silently inserted or deduplicated; excess facts deny rather than drop; pre-provider rejection cases retain their exact zero-call behavior; and provider inspections remain read-only.

## 13. Preserved-invariant assessment

The sixth correction did not weaken the previously frozen AEP contracts examined in source/design bytes:

- canonical request-binding equality remains exact, with no selector/revision/key/envelope/endpoint/profile/backend fallback;
- raw Redis bytes are validated before semantic interpretation;
- delivered V1 codecs, keys, models, Lua, TTL rules, and their historical test boundary remain unchanged;
- V1 precedes L1/A1/I1/P1; CAS is followed on the same connection by `WAITAOF`;
- durable intent precedes provider transport;
- endpoint/profile/deadline and exact dispatch context are revalidated;
- direct `NEW` audit acknowledgement precedes provenance/authority issuance;
- `VerifiedDispatch` remains process-local, one-use, non-copyable, and consumed at most once;
- at most one provider mutation is attempted, with no automatic mutation retry, redirect replay, failover, or recovery replay;
- recovery is read-only and unknown outcomes fail closed;
- typed privacy boundaries and structural absence of production activation remain intact;
- AEP remains the primary research contribution;
- the design makes no exactly-once external-effect, provider-durability, guaranteed physical-erasure, universal backup-purge, future-irrecoverability, or guaranteed-zeroization claim.

Targeted stale searches found no accepted old V2 evidence schema, undefined “adds fields” base, alternate tombstone raw domain, lower/center expiry acceptance, expiry-equality acceptance, reused initial-time fallback, hidden adapter time/state lookup, self-resolution of `PVK-RR4-05`/`06`, positive Stage 2 GO, or forbidden positive durability/erasure claim. Broad matches were conservative denials, limitations, or lineage statements.

## 14. Residual provider and operational dependencies

The following remain separately controlled and unverified: provider-specific retention, generation/token, backup, release/purge, deletion, receipt, native authentication-chain, and recovery-readback semantics; signer and trusted-time custody/accuracy/availability; lifecycle, Redis, and audit durability; IAM and key governance; environment configuration; endpoint/profile/provider selection; RPO/RTO; operational approval and incident procedures; production connector implementation; deployment; activation; and production non-idempotent dispatch.

Canonical package consistency would not prove provider truth or durability even after the two documentation findings are corrected. A provider-reported purge classification remains narrower than universal backup destruction. Dispatch-time authority does not prove later physical completion. No provider-neutral design result can silently pass any provider, operational, connector, deployment, activation, or production-dispatch gate.

## 15. Gate classifications

| Gate | Independent decision | Basis |
|---|---|---|
| Provider-neutral design | **REQUIRES REVISION** | One blocking constructor defect and one major fixture-oracle defect remain. |
| Design completeness | **NOT VERIFIED** | Provider fact construction and positive aggregate fixtures are not closed. |
| AEP compatibility | **VERIFIED AT PROVIDER-NEUTRAL DESIGN LEVEL** | Frozen ordering, authority, audit, one-attempt/no-replay, fail-closed, privacy, and nonactivation contracts remain compatible; this is not implementation evidence. |
| Readiness for bounded provider-neutral Stage 2 | **NO-GO** | `PVK-RR5-01` blocks a constructible provider-neutral retention-fact contract; `PVK-RR5-02` prevents the required exact golden aggregate oracle. |
| Durable production vault/KMS implementation | **NO** | No such implementation was created or verified. |
| Provider-specific durability verification | **NO** | No provider was selected or accessed and no provider evidence was supplied. |
| Production applicability | **NO-GO** | Implementation, provider, operational, deployment, activation, and durability gates remain open. |
| First production connector | **NO-GO** | Its prerequisite production vault/KMS gates have not passed. |
| Production non-idempotent dispatch | **NO-GO** | It remains structurally disabled and separately controlled. |

## 16. Final recommendation and final verification

The exact sixth correction resolves `PVK-RR4-06` but only partially resolves `PVK-RR4-05`. Correct `PVK-RR5-01` and `PVK-RR5-02` in a separately authorized documentation revision, then obtain another independent byte-pinned rereview. Bounded provider-neutral Stage 2 remains **NO-GO**; this report does not authorize it.

After creating this report, the integrity hashes of `docs/15` and `docs/20`, the byte identity of `docs/15` through `docs/20`, the protected source/test/configuration/dependency manifests, the workspace file census, and this report's headings/tables/IDs/line endings were rechecked.

| Final verification check | Exit code | Exact result |
|---|---:|---|
| Rehash `docs/15` through `docs/20`; normalize `docs/15` and `docs/20`; rescan CR | 0 | All six raw hashes equal their pre-review values; `docs/15` raw/normalized remains `69e78ea6…15f2d`; `docs/20` raw/normalized remains `4a36ba04…cb80`; both have CRLF 0 and bare CR 0. |
| Historical source/test manifest replay | 0 | 88 files; `b3d60014240692936afdaf2b37be0ea51fe9e327a6c06a0a8013c40e96d5bb8a`; exact pre-review match. |
| Configuration/manifest replay | 0 | 3 files; `eaef6ce9bbe12f4c8b766489d976886433ec43ff4d89a7923e32894189fd4e63`; exact pre-review match. |
| Dependency/lock selection replay | 0 | 1 file; `8bbe5d14acd6ee04ea4fe92e26511f158c9fe8b793a659536aaeb59218c7c298`; exact pre-review match. |
| Workspace census excluding `.git` | 0 | Pre-review 147 files with `docs/21` absent; post-review 148 files with `docs/21` present; excluding this report remains 147. The only issued write targeted this report. |
| Report structure, IDs, tables, and line endings | 0 | 16 required H2 sections in order; one definition each for `PVK-RR5-01` and `PVK-RR5-02`; 10 Markdown tables, 0 width errors; CRLF 0; bare CR 0. |
| Final Git diagnostic, `git status --short` | 1 | `fatal: not a git repository`; no Git-history claim is made. |

The initial full-tree byte snapshot was 147 files with digest `0a62659f498211e123accaa60521a8c4f24fa328eb3343c051e271713ed125de`. Git was therefore not used as the protection oracle. The exact protected pre/post manifests above, the unchanged six reviewed-document hashes, the one-path file-count increase, and the write-command boundary confirm that design and implementation files were not modified and that this report is the sole created repository artifact.

Three discarded final-checker invocations were read-only and produced no artifact: one combined command was denied before process creation by the sandbox; one legacy-API checker timed out with exit 124; and one quoted one-liner had exit 1. They were replaced by the successful checks above. The first integrity-check attempt likewise exited 1 only because the host lacked the probed static .NET hash API; the compatible byte checker then exited 0. Exact stale-search `rg` exit 1 values meant zero matches, as stated in Section 4.

No application tests were rerun. Only the historical 611-test baseline is retained. All provider, operational, connector, deployment, activation, and production-dispatch gates remain separately controlled.
