# WS-5 pre-registration — amendment 3: the lower-mode threshold, pinned before the `always` arm

**Amends** `reports/phase-report-ws5-prediction-2026-09-10.md` (`47d8a23`),
amendment 1 (`684c5fb`) and amendment 2 (`05458ea`). **All three stay unedited**
(rule 5).

**Committed and pushed before any `always`-arm run directory exists.** The 45
runs of WS-5 task 5.1's `always` arm go through the same lower-mode code that
phase 18 got wrong, so the rule that governs it is fixed here rather than after.

---

## 1. What went wrong, and how narrowly it was caught

Amendment 1 §1 prescribes that, for a flagged arm, differences be taken between
**lower-mode medians**. It did not say where the lower mode ends.

Phase 18 implemented the boundary as a **midpoint**,
`lower_median + gap / 2`, and computed:

> protocol − barrier = **+16.3 ms [+7.1, +46.6]** — excluding zero.

The boundary should be the **top of the splitter's own lower group**, which
gives:

> protocol − barrier = **+16.3 ms [−54.1, +47.5]** — spanning zero.

**Opposite signs on the same data, under two defensible-sounding readings of the
same sentence.** The midpoint rule sits below the top of a skewed lower group,
so it dropped **8 of B3's 120** lower-mode executions — quietly, because
dropping executions narrows an interval rather than breaking anything.

It was caught because the kept counts (149 / 112 / 145) did not match the
splitter's group sizes (149 / 120 / 145), and someone read both. That is not a
control.

## 2. The rule that governs

> **The lower-mode boundary is the largest value still inside the splitter's
> lower group** — `largest_gap_split(pooled)["lower_max"]` — computed once per
> arm from that arm's pooled sample, and then applied to every run.

Two properties, both deliberate:

* **One threshold per arm, not per run.** A per-run split would move under the
  bootstrap, making the estimator depend on which runs a resample drew. That is
  not an estimator, it is a search.
* **The boundary comes from the same function that produced the split.** Any
  separately-derived threshold — a midpoint, a quantile, a fixed multiple of the
  within-mode spread — can disagree with the split it is supposed to implement,
  and phase 18 is the demonstration.

## 3. The invariant, asserted in code rather than checked by eye

`scripts/power_analysis.py:lower_mode_difference` now raises before producing
any interval:

```
for each arm:
    kept = |{executions <= threshold}|
    expected = largest_gap_split(pooled)["lower_n"]
    kept == expected, or AssertionError
```

**This is the check that would have stopped phase 18's midpoint rule
immediately** — it keeps 112 where the splitter holds 120 — instead of letting
it return a sign-flipped interval that a human had to notice.

The assertion refuses rather than corrects. A threshold that disagrees with its
own split is a defect in the code, not a number to be repaired at runtime.

## 4. Scope

This governs every lower-mode difference computed from here on, including the
`always` arm's, if that arm is flagged as a mixture. It does **not** re-open
phase 17 or 18: their reported numbers already use the correct boundary, and
amendment 2's table is unaffected.

## 5. What this does not fix

`gap / range > 0.5` — amendment 1's *flag* predicate — is still range-sensitive,
and amendment 2 §4 records why it is not being changed mid-workstream. This
amendment fixes where the lower mode **ends**, not when an arm is **called** a
mixture. The two are independent, and only the first was implicated in phase 18.
