# Phase 8.5 step 5 — refit with run position: the class effect is unmoved

**Result: adding run position moves the primary estimate by +0.003 log-odds, a
0.5% change, and does not alter the verdict.** The covariate is not merely
carrying elapsed time, and B9's defect does not reappear in this data.

The test is worth more than that summary suggests, because **position visibly
does something** — it just does not do it to the class coefficient.

---

## 1. The class coefficient, with and without position

| session | without position | with position | change |
|---|---|---|---|
| s1 | −0.0477 | −0.0334 | +0.014 |
| s2 | −0.0268 | −0.1823 | −0.156 |
| s3 | +0.8698 | +0.8945 | +0.025 |
| s4 | +1.5382 | +1.6674 | +0.129 |
| **mean** | **+0.5834** | **+0.5865** | **+0.003** |

| | without | with |
|---|---|---|
| between-session sd | 0.7669 | 0.8638 |
| half-width, t(3) | 1.2201 | 1.3743 |
| **95% interval** | **[−0.6368, +1.8035]** | **[−0.7878, +1.9609]** |
| **contains 0** | **YES → CONFIRMS** | **YES → CONFIRMS** |
| pooled β class | +0.5732 | +0.5960 |
| pooled Wald interval | [+0.0173, +1.1291] | [+0.0325, +1.1595] |
| pooled contains 0 | NO | NO |

**Every conclusion is unchanged.** The verdict is CONFIRMS either way, the pooled
comparison disagrees either way, and the disagreement remains marginal at the
pooled lower bound.

The largest single movement is session 2, −0.027 → −0.182. Against that
session's standard error of 0.65 it is a quarter of one standard error, and
session 2 is the session whose balance figure is −97.7 ms. It is noted rather
than interpreted.

## 2. Position is not inert — it absorbs part of the latency term

This is the part that makes the test informative rather than decorative.

| session | log(latency) without position | log(latency) with position | position β | se | \|β/se\| |
|---|---|---|---|---|---|
| s1 | +2.489 | **+1.534** | −0.0456 | 0.0349 | 1.30 |
| s2 | +4.439 | **+2.968** | −0.0883 | 0.0436 | 2.02 |
| s3 | +6.694 | **+6.448** | −0.0319 | 0.0344 | 0.93 |
| s4 | +2.446 | **+1.126** | −0.0520 | 0.0430 | 1.21 |

**The latency coefficient falls in all four sessions, by as much as 54% in
session 4.** Position and latency are correlated — that is the within-session
drift — and position takes back part of what latency was carrying.

**So B9's mechanism is present in this data.** The covariate *is* partly a proxy
for elapsed time, exactly as B9 says it was in the frozen 8.1 set.

**And the class coefficient is unaffected anyway.** That is amendment 1 working
as designed: run-level interleaving makes arm orthogonal to position by
construction, so however much of the drift the covariate absorbs, none of it can
transfer to the arm contrast. Step 1 established all four sessions ran under the
interleaved sort key; this is the consequence of that being true.

The position terms themselves are individually weak — all four negative, only
session 2 exceeding |β/se| = 2 — so later runs are slightly *less* likely to
apply an effect. Consistent in sign across all four sessions, which is worth
recording, but not a result this phase can carry on n = 4.

## 3. What this settles, and what it does not

**Settles:** 8.5 does not repeat B9. The primary estimand is robust to
conditioning on run position, and the reason is structural rather than lucky —
interleaving, not a fortunate correlation.

**Does not settle:** B9 itself. B9 is a re-analysis obligation on the *frozen
8.1 replication set*, which is cell-major (`b2-paired-s1-2026-08-28`,
`16abc997`, sort key `(tier, cell_key, repetition)`) and cannot be protected
retroactively. Nothing here discharges it. If anything, §2 strengthens the case
for doing it: the drift-latency entanglement B9 predicts is directly visible in
the sessions that *were* protected.

**Does not settle:** the heterogeneity. Adding position made the between-session
sd larger, not smaller — 0.767 → 0.864. Position is not the explanation for the
sessions disagreeing with each other. That remains unexplained, and §6 of the
step-4 report records the one co-occurrence that exists without weighting it.

## 4. Reporting requirement carried forward

Both specifications go into 8.6, not just the one. Reporting only the
without-position fit would hide that the covariate carries time; reporting only
the with-position fit would look like a specification chosen after the fact.
**The pair is the result**, and the pair is what makes the robustness claim
checkable.

No macro, paper file or pre-registration has been modified.
