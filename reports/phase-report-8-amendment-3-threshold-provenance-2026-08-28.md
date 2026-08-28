# Phase 8 · amendment 3 §2 — the provenance of the 0.02 threshold

**This changes nothing.** The threshold is not revised, the rule is not
reinterpreted, and the adjudication still happens at 8.5 over all four sessions.
What is fixed here is the *record of the threshold's own provenance*, which was
missing — the same class of defect this phase keeps catching: a condition set
honestly with no account of how it was arrived at.

**Committed while sessions 3 and 4 are still collecting**, so that what was
computable at the time the threshold was set is on the record before the data it
will judge exists.

---

## 1. What the threshold is, and what amendment 3 said about it

Amendment 3 §2 pre-declares that the covariate is degenerate when

> |Δ median log-latency| < 0.02 (≈ 2%, against the ~20% imbalance amendment 1
> removed) in a majority of sessions

and that in that case the adjusted model is not the primary result; the
unadjusted within-session paired difference becomes the answer, reported as
**non-estimability** and never as "coefficient not distinguishable from zero".

**The stated derivation is internal to the design, not to the data.** 0.02 is
roughly one tenth of the ~20% arm-correlated latency imbalance that amendment 1's
interleaving removed *by construction*. The reasoning is that if the confound the
covariate exists to adjust for has been reduced to a tenth of its former size,
the covariate has nothing material left to adjust on. In log space Δ = 0.02 is a
ratio of 1.0202, i.e. ~2.0% between the arms.

## 2. What was visible when it was set — exactly

From commit timestamps, which are the only account that cannot be reconstructed
favourably afterwards:

| commit | time | what |
|---|---|---|
| `75a9019` | 2026-08-28 **13:45:40** | Phase 8.4 session 1 (amended design) |
| `850f221` | 2026-08-28 **13:58:41** | amendment 3, fixing the 0.02 threshold |
| `4d1d309` | 2026-08-28 **16:41:51** | Phase 8.4 session 2 |

Session 2's *collection* did not begin until 14:45:56, 47 minutes after the
threshold was committed.

**So the threshold was fixed with one of the four sessions visible** — session 1,
plus the superseded cell-major session whose data amendment 1 published. Sessions
2, 3 and 4 did not exist in any form. It is therefore **not** a threshold chosen
with two sessions in hand, and it is **not** fully blind either.

## 3. The statistic, computed now for the sessions that then existed

Amendment 3 §2 step 1, run on the frozen analysis of sessions 1 and 2:

| session | n (AUTH/NO_RB) | Δ median log | \|Δ\| < 0.02 | between/within variance |
|---|---|---|---|---|
| `b2-paired-v2-s1` | 30/30 | **+0.012398** | **YES** | 0.005298 |
| `b2-paired-v2-s2` | 30/30 | **−0.085097** | no | 0.048743 |

**The disclosure that matters: session 1's value is 0.0124, which is below the
threshold, at 0.62× of it.** Session 1 was the only session visible when 0.02 was
set. A threshold set just above the single observed value, in a direction that
makes that observation qualify, is exactly the shape that would be criticised if
it were left unlabelled. It is labelled here.

**What can be said in its defence, and its limits.** The stated derivation (§1) is
arithmetic on the ~20% figure and does not reference session 1's latency spread.
**No artefact containing this statistic exists prior to this document** — the
computation above is the first time it has been produced, on either session. So
the threshold was not tuned against a computed value, because no computed value
existed. It remains true that the underlying data was on disk and the statistic
was computable in the 13 minutes between `75a9019` and `850f221`, and nothing in
the record excludes an informal impression of session 1's balance (+13.0 ms,
published in that commit) having influenced the choice.

**This is a weaker claim than "blind", and a stronger one than "post-hoc". It is
stated at its true strength and not above it.**

## 4. Why the threshold is not being changed

Changing it now — in either direction — would be strictly worse. The data that
would motivate a change is precisely the data the threshold exists to judge, and
sessions 3 and 4 are mid-collection. Amendment 3 says the threshold "is fixed
here and is not revisable after seeing the fits", and one session's statistic
now being visible is not grounds to reopen it.

## 5. What 8.5 must do with this

- Compute the statistic for **all four** sessions and report the four numbers
  **before any coefficient**, as amendment 3 §2 step 2 requires.
- Apply the majority rule over the k = 4 set. **Sessions 1 and 2 currently split
  1–1**, so the classification genuinely turns on sessions 3 and 4, which did not
  exist when the threshold was set. That is the strongest thing that can be said
  for the threshold's provenance, and it is a fact about the arithmetic rather
  than an argument.
- Carry §3's disclosure into 8.6 verbatim. A reader deciding how much to trust
  the degeneracy verdict needs to know the threshold was set with one session
  visible and that this session's value fell below it.
