# WS-5 — pre-registration: statistical power and the remaining cells

**Committed and pushed before any WS-5 run exists.** Rule 5 of
`docs/26-journal-readiness-direction.md` §3. Nothing in this file is changed
once data arrives; if it turns out to be wrong, it is wrong in the record.

**Status at the moment of writing.** `scripts/power_analysis.py` and
`tests/test_power_analysis.py` are committed in this same commit.
`experiments/results/` contains no WS-5 directory. No collection has been
launched. Every number in §1 comes from the **frozen** results the manuscript
was already built from.

---

## 0. Summary

WS-5 was scoped as a sample-size problem: run more, tighten the intervals. The
power analysis says that is not quite what is wrong, and §1 is the finding
about the paper's existing results that the analysis produced before any new
data was collected. §2 is what is pre-registered. §3 is the collection and what
it costs. §4 states which of the tasks in `docs/26` §4 WS-5 are affected.

---

## 1. What the frozen results can support

### 1.1 A hypothesis this analysis was written to confirm, and refuted

The prompt for this workstream, and an earlier draft of `power_analysis.py`,
carried the claim that a cluster bootstrap over three runs is *degenerate* — that
with only ten distinct resample multisets, a "95% percentile interval" is really
the range of the three cluster values dressed as an interval.

**That is false, and the measurement is what settled it.** Two arms resample
independently, so the ceiling on distinct differences is the *product*,
`C(5,2)² = 100`, not 10. The realised count is 42 over 10 000 resamples, and the
published endpoints are interior points of the support, not its extremes:

| quantity | published interval | realised support | endpoints extremal? |
|---|---|---|---|
| barrier cost, `everysec` | [477.9, 1978.8] | [460.5, 1981.0] | no |
| protocol − barrier, `everysec` | [27.1, 1524.6] | [26.9, 1525.7] | no |
| barrier cost, `always` | [−1474.6, 22.7] | [−1483.2, 22.7] | low no, high yes |

The intervals are coarse. They are not degenerate, and no published number has
to be withdrawn on that ground. This is recorded because it was the expected
finding and it did not survive contact with the data.

### 1.2 The real problem: the B3 arm is a mixture, and a median summarises it badly

B3's crash-free step latencies are **bimodal**. Twenty-two of thirty executions
sit near 2 034 ms; the other eight sit near 5 033 ms, across a gap of 2 913 ms
that is 95% of the arm's whole range. The upper mode holds 27% of executions
under **both** fsync policies — 10%, 20% and 50% in the three runs respectively.

The consequence is not a wide interval, it is an unstable estimand:

| run | executions in the upper mode | run median |
|---|---|---|
| `…85b7630d-r0` | 1 of 10 | 2 037.8 ms |
| `…85b7630d-r1` | 2 of 10 | 2 050.4 ms |
| `…85b7630d-r2` | **5 of 10** | **3 534.8 ms** |

`r2`'s median of 3 534.8 ms is the midpoint of the gap between the two modes.
**No execution in that run is anywhere near 3 534.8 ms.** With ten executions and
a two-mode mixture, the median jumps by half the gap when a single execution
crosses the 5/5 boundary — which is the entirety of that arm's 860.7 ms
between-run standard deviation, against 12.5 ms for AEP-full and 1.0 ms for B0.

The published [27.1, 1524.6] interval on the protocol-minus-barrier figure is
therefore **correct** and correctly derived: the bootstrap is faithfully
reporting that if all three runs resembled `r2`, the pooled median would be near
3 535 ms. Three runs cannot rule that out.

### 1.3 What that means for §VI's decomposition claim

§VI-RQ3 states that everything the write-ahead protocol does apart from waiting
for `fsync` costs **28.0 ms**, and reads the decomposition as saying "something
stronger than *AEP costs two seconds*". The interval on that 28.0 ms figure is
[27.1, 1524.6] — a factor of 56 — and it is quoted **only in §VIII**, five
sections later, where it correctly describes the barrier-to-protocol ratio as
"an estimate of an order of magnitude rather than of a figure".

The claim is not contradicted by its own data. But the sentence that carries it
appears without the interval that qualifies it, and at three runs per arm the
decomposition is not separable from the mixture: if B3's upper mode is more
common than 27%, the "protocol minus barrier" term is not small.

**Pre-registered position:** this is a reporting defect in §VI, not a withdrawn
result, and it is repaired by (a) quoting the interval where the claim is made
and (b) reporting the mixture rather than only the median. Both are done after
collection, in the same pass that adds the runs.

### 1.4 The two "failures to reject" are precision failures — provably

§VIII's conclusion-validity paragraph says two comparisons "fail to exclude zero
for reasons of precision rather than of effect". **WS-5 substantiates that
sentence, in the strongest form available: for the paired sign test the claim is
not an interpretation but a theorem about the design.**

With *n* paired sessions the smallest attainable two-sided sign-test p-value is
`2/2ⁿ`. Both comparisons have **four** sessions, so the floor is **p = 0.125**.
No effect size, however large, could have produced a rejection at α = 0.05. Six
sessions is the minimum at which the test becomes *capable* of rejecting.

| comparison | sessions | mean | half-width | half-width ÷ \|mean\| | sign-test floor |
|---|---|---|---|---|---|
| kill-latency attribution | 4 | +105.5 ms | 195.7 ms | 1.86 | 0.125 |
| capability-class sweep | 4 | +12.5 pp | 33.9 pp | 2.71 | 0.125 |

The sentence in §VIII stands and can be strengthened: it is not that the study
failed to find an effect, it is that this design **could not have found one**.

---

## 2. Pre-registered design

### 2.1 Decision inputs, fixed now

Set in `scripts/power_analysis.py` as module constants so the analysis cannot be
tuned to the data it will judge.

| input | value | basis (independent of any observed effect) |
|---|---|---|
| α | 0.05, two-sided | convention |
| power | 0.80 | convention |
| SESOI, barrier cost | 100 ms | a tenth of one `everysec` fsync interval; below this the AEP-full-versus-B3-mode choice does not change |
| SESOI, protocol cost | 25 ms | the decomposition claim is about order of magnitude, not value |
| SESOI, rate difference | 5 pp | 5 pp of 180 crashed executions per class is 9 executions — the smallest difference resolvable at one run of ten per stratum without splitting a run |
| unit of analysis | the **run** for matrix cells; the **session** for interleaved comparisons | rule 6; sessions disagree with one another and that variance is real |

### 2.2 Hypotheses

* **H1 (timing, task 5.1).** At ≥ 15 crash-free runs per arm, the barrier's cost
  under `everysec` excludes zero, and the protocol-minus-barrier figure's
  interval half-width falls below 100 ms. *Directional prediction:* the barrier
  cost stays near 2 000 ms; the protocol cost stays below 100 ms.
* **H2 (mixture).** B3's upper-mode fraction is a stable property of the arm, not
  of those three runs: at 15 runs it lies in [0.15, 0.40]. **If it does not, the
  mixture is a per-run artifact and H1's estimand must be reconsidered before
  any timing number is quoted.**
* **H3 (30% regime, task 5.2).** Rates in the 30%-crash regime lie between the
  crash-free and all-crash regimes for every system and metric. A rate outside
  that envelope is a finding about regime interaction, not a precision problem.
* **H4 (keying, task 5.3).** The alternative read-back keying leaves every
  headline rate inside the pre-registered ±5 pp margin. This is a sensitivity
  check and is predicted to be null.
* **H5 (equivalence, task 5.5).** The B3-versus-AEP-full ambiguity difference is
  equivalent within ±5 pp by TOST at α = 0.05.

### 2.3 The exact analysis, fixed before collection

* **Rates.** Cluster bootstrap over runs, 10 000 resamples, seed 20260806 —
  unchanged from the frozen analysis, so old and new cells are comparable.
* **Timing.** The same cluster bootstrap, **plus** a mandatory mixture report per
  arm: the largest-gap split, both mode locations, and the per-run upper-mode
  fraction. A median is not quoted for an arm flagged as a mixture without the
  fraction beside it. `power_analysis.py --section degeneracy` is the instrument.
* **Equivalence (task 5.5).** TOST at α = 0.05 against the ±5 pp margin above,
  which is **operationally identical** to requiring the 90% run-clustered
  interval to lie inside ±5 pp — the interval the analysis already computes.
  Two one-sided nulls: H0₁ Δ ≤ −5 pp, H0₂ Δ ≥ +5 pp; equivalence is claimed only
  if both are rejected.
* **Multiplicity.** Where several capability classes are tested together,
  Bonferroni across the three, as §VI already does for the zero-event bounds.

**An honesty constraint on 5.5 that survives this pre-registration.** The ±5 pp
margin was chosen post hoc in an earlier revision, and pre-registering it now
does not retrospectively make it pre-registered *for the frozen data*. The
margin is pre-registered for the **new** cells only. §VI's existing sentence
labelling it a post-hoc stipulation stays as it is for the existing result.

### 2.4 Stopping rule

Fixed *n*, decided in §3, with **no interim peeking at any outcome**. One
interim look is permitted and is specified here: after the first 5 runs of each
timing arm, the between-run variance and the upper-mode fraction may be
re-estimated **for the sole purpose of deciding whether the pre-registered *n* is
adequate**, and any increase to *n* is recorded as an amendment to this file
before collection continues. Outcome measures are not examined at that point.
This exists because every sample size in §3 is derived from a variance estimated
on three or four clusters and is therefore uncertain by roughly a factor of two
in each direction; a design that cannot adjust to that is a design that pretends
the variance is known.

---

## 3. What would be collected, and what it costs

Per-run wall clock from the frozen manifest: 50.8 s (B0) to 104.2 s (B3), mean
≈ 72 s for ten executions.

### Tier 1 — cheap, and repairs a published claim

| task | cells | runs | estimated wall clock |
|---|---|---|---|
| 5.4 re-collect the one incomplete run | 1 | 1 | ~2 min |
| 5.1 timing, `everysec`, all 7 systems at 15 crash-free runs | 7 | 105 | ~2.1 h |
| 5.1 timing, `always`, AEP-full/B3/B0 at 15 | 3 | 45 | ~0.9 h |
| **Tier 1 total** | | **151** | **~3 h** |

### Tier 2 — closes two of the three remaining named gaps

| task | cells | runs | estimated wall clock |
|---|---|---|---|
| 5.2 30%-crash regime, 7 systems × 3 classes × 15 runs | 21 | 315 | ~6.3 h |
| 5.3 alternative keying, AEP-full × 2 querying classes × 6 crash points × 15 | 12 | 180 | ~3.6 h |
| **Tier 2 total** | | **495** | **~10 h** |

**Tier 1 + Tier 2 ≈ 13 hours**, which is inside `docs/26`'s "2–3 days of mostly
unattended collection" for the matrix tasks.

### Tier 3 — the session-level comparisons, where the estimate breaks

One session of the class sweep is 4 sessions × 30 runs per arm × 2 arms ≈ 1.5 h.

| target | sessions | additional | wall clock | verdict |
|---|---|---|---|---|
| sign test becomes *capable* of rejecting | 6 | +2 | ~3 h | **worth doing** |
| 80% power at the *observed* class-sweep effect | 25 | +21 | ~32 h | post-hoc; not a design target |
| 80% power at the pre-registered 5 pp SESOI | **143** | +139 | **~9 days continuous** | **not recommended** |
| 80% power at the observed kill-latency effect | 13 | +9 | ~14 h | marginal |
| 80% power at the 50 ms kill-latency SESOI | 50 | +46 | ~3 days | not recommended |

**`docs/26`'s effort estimate of "2–3 days" does not cover the session-level
comparisons, and no feasible amount of collection fixes the class sweep at its
pre-registered margin.** The between-session standard deviation is 21.3 pp on a
+12.5 pp mean; sessions disagree with each other more than the arms disagree.
Adding sessions attacks that at √n, and 5 pp is out of reach.

**Recommended position, to be ruled on before launching:** take the class sweep
to **6 sessions** so the sign test is no longer at its floor, report it as a
bound rather than a test, and leave §VIII's conclusion-validity paragraph
standing — because it is correct, and §1.4 makes it stronger rather than
weaker. Chasing 143 sessions would buy one interval at the cost of a week of
machine time and would still be a session-level result from one host.

---

## 4. Effect on the tasks as written in `docs/26` §4

| task | status after this analysis |
|---|---|
| 5.1 ≥ 15 crash-free runs per arm | **Kept, and amended.** 15 runs fixes the interval width for AEP-full and B0. It does **not** fix B3, whose estimand is a mixture median; the analysis must report the mixture. The acceptance criterion "intervals must exclude zero where the point estimate is > 0" is achievable for the barrier cost and is **not** a sensible target for the `always` policy, where the true effect may be near zero. |
| 5.2 30%-crash regime | Kept as written. |
| 5.3 alternative keying | Kept as written. |
| 5.4 one incomplete run | Kept as written. |
| 5.5 replace the ±5 pp margin with a pre-registered TOST | **Kept, with a caveat.** The TOST is specified in §2.3 and, on the frozen data, already passes: the published 90% interval [−1.11, +2.04] lies inside ±5 pp. What changes for the new cells is that the margin is registered in advance. For the frozen cells it remains post hoc and stays labelled so. |
| **Acceptance:** "every interval quoted in Tables X–XI has ≥ 15 clusters" | Achievable in Tier 1. |
| **Acceptance:** "§VIII-C(f) gap list shrinks" | Tier 2 closes the 30%-regime and keying gaps; the incomplete run closes in Tier 1. |

---

## 5. What is *not* pre-registered here

* No new host. Every collection remains on the one measurement host, so nothing
  here addresses the cross-host external-validity gap §VIII already declares.
* No change to the metrics, the crash points, or the outcome classifier.
* No re-analysis of frozen cells. §1's findings are about what the frozen
  numbers support; the numbers themselves are immutable (rule 2).
* B3's mixture is *reported*, not *explained*. Why 27% of B3's crash-free
  executions cost three seconds more than the rest is a question this
  pre-registration raises and does not answer, and answering it is not a
  precondition for the collection above.
