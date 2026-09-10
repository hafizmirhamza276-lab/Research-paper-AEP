# WS-5 pre-registration — amendment 1: how a mixture arm is reported

**Committed and pushed before any WS-5 run exists.** Amends
`reports/phase-report-ws5-prediction-2026-09-10.md` (commit `47d8a23`), which is
left unedited. Rule 5: corrections are recorded alongside a pre-registration,
never applied silently to it.

**Why an amendment rather than an edit.** §1.2 of the pre-registration
established that B3's crash-free arm is a two-mode mixture and that `docs/26`
5.1's remedy — more runs — narrows the interval without fixing the estimand. It
did not say what to report instead. Choosing that *after* seeing fifteen runs
would be a fitted choice: the shape of the new data would decide which summary
flatters it. So it is fixed here, before any new run exists.

---

## 1. The decision

**For any arm the mixture test flags, the timing analysis reports three
quantities and derives every difference from the first two.**

| # | quantity | why it does not jump |
|---|---|---|
| 1 | **Mode-conditional median** — the median *within* each mode, taken after the largest-gap split | The modes are separated by a gap that is 95% of the arm's range. Moving one execution across the boundary changes each mode's median by at most the within-mode spread, which is ~90 ms, not by half the gap. |
| 2 | **Upper-mode fraction**, with a run-clustered interval | A proportion. It moves by 1/*n* per execution and has no discontinuity anywhere. |
| 3 | Pooled median | Retained as a **descriptive** statistic only. Never the basis of a difference. |

**Differences — the barrier cost, and the protocol-minus-barrier figure — are
computed as differences of *lower-mode* medians**, with the upper-mode fraction
reported beside them. Read aloud, the claim becomes: *"the protocol costs X ms
when nothing anomalous happens, and this fraction of executions cost about three
seconds more"* — two statements, each estimable, instead of one number that is
neither.

### The failure this avoids, stated concretely

B3's run `r2` splits 5/5 across the modes, so its pooled median is 3 534.8 ms —
the midpoint of a gap in which **no execution lies**. One execution crossing the
boundary moves that median by 1 500 ms. The mode-conditional medians for the
same run are ~2 030 ms and ~5 033 ms, and the upper fraction is 0.5; a single
execution crossing moves those by ~10 ms and by 0.1 respectively.

### What was considered and rejected

* **A trimmed mean, or a Winsorised mean.** Rejected: it discards the upper mode
  by construction. The upper mode is 27% of executions under both fsync
  policies. That is behaviour, not contamination, and a summary whose merit is
  that it hides a quarter of the data is the wrong instrument for a paper whose
  argument is that unexplained residuals get declared rather than smoothed.
* **The mean instead of the median.** Rejected: it does not jump, but it is a
  weighted blend of two modes and equals a value no execution exhibits — the
  same defect as the mixture median, made continuous rather than removed.
* **A quantile other than the median (e.g. p25).** Rejected: it happens to sit
  inside the lower mode *at the currently observed 27%*, and would migrate into
  the gap if the fraction rose above 0.75. Choosing a quantile because the
  present mixture proportion makes it safe is exactly the fitted choice this
  amendment exists to prevent.
* **Reporting only the pooled median with a wider interval.** Rejected: this is
  `docs/26` 5.1 as written, and §1.2 of the pre-registration is the argument
  against it.

### The rule for when it applies

The mixture test is `largest_gap_split` in `scripts/power_analysis.py`, already
committed: an arm is a mixture when the largest gap exceeds half the sample's
range **and** the smaller group holds at least a tenth of the observations. Both
conditions are fixed now. The second exists because a single far point is an
outlier, not a mixture, and without it B0 — whose three run medians agree to
within 1.8 ms — would be flagged alongside B3.

**If no arm is flagged at fifteen runs, the mixture reporting is omitted and the
pooled median stands.** That outcome is H2 of the pre-registration being
refuted, and it is reported as such rather than quietly dropped.

---

## 2. The class sweep: six sessions, reported as a bound

Confirmed as the ruling. Two sessions are added to the existing four.

* **Six is the minimum at which the paired sign test can reject at all.** The
  floor is 2/2ⁿ; at n = 4 it is 0.125 and at n = 6 it is 0.03125.
* **The result is reported as a bound, not as a test.** Six sessions gives 80%
  power only against effects far larger than the ±5 pp margin; reaching that
  margin needs ~143 sessions, which §3 of the pre-registration prices at about
  nine days of continuous collection. The claim made will therefore be an
  interval and an explicit statement of what it could not have detected.
* **This is not in the launched collection.** Tier 1 and Tier 2 are matrix
  cells. The two additional sessions are a separate, later launch.

---

## 3. Open question, recorded and deliberately not investigated

**Why do 27% of B3's crash-free executions cost about three seconds more than
the rest?**

What is known, and nothing beyond it:

* The arm is bimodal: **2 034 ms** and **5 033 ms**, medians within each mode.
* The gap between them spans **95% of the arm's entire range**.
* The upper mode holds **27% of executions under both fsync policies** —
  `everysec` and `always` — which makes an fsync-scheduling explanation
  unlikely on its face, since `always` has no 1-second boundary to wait for.
* Per-run upper fractions are 10%, 20% and 50%; the arm has only three runs, so
  that spread is itself poorly determined.
* B3 is AEP-full with the `WAITAOF` barrier ablated and nothing else changed,
  so whatever this is, AEP-full does it too or is masked by its own ~2 000 ms
  barrier wait.

**Not investigated, by instruction, and not a precondition for this
collection.** Tier 1 collects fifteen runs per arm, which will determine whether
27% is a property of the arm or of those three runs — H2 of the pre-registration
— without anyone having to diagnose the mechanism first. Recorded here so that
the question survives the collection rather than being rediscovered from the
new data.
