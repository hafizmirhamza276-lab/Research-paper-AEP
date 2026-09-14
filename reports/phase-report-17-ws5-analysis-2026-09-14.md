# Phase 17 — WS-5 analysis of the 612 collected runs

**Status at the time this section was committed: no outcome has been computed.**
The `settled=false` ruling below is committed *before* the analysis runs, so the
git history establishes the ordering rather than the report asserting it.

---

## 1. Integrity: what could be proved, and what could not

### 1.1 The committed digests verify

```
t1-p0-everysec     MANIFEST.md: OK MANIFEST.csv: OK
t1-incomplete      MANIFEST.md: OK MANIFEST.csv: OK
t2-p30             MANIFEST.md: OK MANIFEST.csv: OK
t2-keying          MANIFEST.md: OK MANIFEST.csv: OK
```

8 of 8 OK.

### 1.2 They do not cover the raw tree, and the prompt's step 2 assumed they did

Each `SHA256SUMS` contains **two lines** — `MANIFEST.md` and `MANIFEST.csv`.
`scripts/freeze_results.py` documents exactly this (*"over the manifest and every
analysis output"*), and at freeze time there were no analysis outputs. **The
over-claim is in commit `729fbfa`, which is mine:** *"SHA256SUMS is what lets the
later pass prove it analysed what was collected."* It lets a later pass prove the
manifests are unchanged. That is strictly weaker and does not cover 331 MB of run
directories.

### 1.3 What was done instead

The manifests were regenerated from the present raw tree and compared
byte-for-byte:

```
t1-p0-everysec     MANIFEST.md=same  MANIFEST.csv=same
t1-incomplete      MANIFEST.md=same  MANIFEST.csv=same
t2-p30             MANIFEST.md=same  MANIFEST.csv=same
t2-keying          MANIFEST.md=same  MANIFEST.csv=same
```

and the digests still verify afterwards (8/8 OK). Because `freeze_results.py`
reads runs through `experiments.analyze.load_run` — the same loader the analysis
uses — this establishes that the tree still yields the same **612 runs, 44 cells
and per-cell execution counts**.

**What it does not establish:** a change to a run's *contents* that left every
count identical would pass this check. It is not a full-tree digest and is not
presented as one.

---

## 2. Ruling on the `settled=false` runs

**Committed before any outcome was computed.** 19 of 315 in `t2-p30` and 53 of
180 in `t2-keying` carry `settled=false`.

### 2.1 What the flag means

`runner.wait_until_settled` returns `False` when at least one execution is still
in a `PENDING_STATUS` after `recovery_deadline_seconds`. It is a statement about
how long recovery took relative to a deadline, not about whether the run
produced a measurement.

### 2.2 The ruling

> **An unsettled run is a measurement and is included, unweighted, exactly as a
> settled one.**

### 2.3 Where the rule comes from — four independent grounds, none of them new

1. **The pre-registration fixes it.** §2.3: rates are *"unchanged from the frozen
   analysis, so old and new cells are comparable."* Any exclusion rule invented
   now would not be unchanged from the frozen analysis.
2. **`experiments/analyze.py` has no run-level `settled` filter at all.** The
   only occurrences are `settled_at`, an execution-level timing field. The
   absence of a filter is the frozen analysis's treatment; including these runs
   *is* leaving the analysis unchanged.
3. **The harness treats it as a warning, not a void.** `runner.py:747` prints
   `WARNING: the run did not settle within the recovery deadline` and returns
   `0 if report.agrees else 1` — validity is `agrees`, not `settled`. The harness
   has a separate, explicit void vocabulary (`RunVerdict.VOID_*`), and it voided
   nothing: all 612 runs carry `status=collected`.
4. **§2.4's stopping rule forbids it.** Fixed *n*, no outcome-dependent
   decisions. `settled` correlates with crash regimes by construction — the
   crash-free step has 0 unsettled and the all-crash step has the most — so
   excluding on it would preferentially drop crashed runs, which is an
   outcome-adjacent exclusion made after collection.

### 2.4 The honest limitation of ground 1

The frozen `matrix-progress.jsonl` available in this clone holds 83 entries, all
`settled=true`, so the frozen analysis was **never actually confronted with an
unsettled run**. The precedent is therefore untested rather than established,
and ground 1 rests on the absence of a filter (ground 2) rather than on an
observed decision. Recorded because the difference matters: grounds 2–4 carry
the ruling on their own, and ground 1 alone would not.

### 2.5 What would have changed the ruling

A run whose recovery process *died* during settling is a different case:
`wait_until_settled` raises `RunAborted` and states that *"No recovery
measurement from this run is usable."* That did not happen in any of the 612 —
every run reached `status=collected`. Had it happened, those runs would be
excluded, and the rule for doing so is the harness's own, not a new one.

---

*Sections 1 and 2 above were committed at `2b78452`, before any outcome was
computed. Sections 3 onward were appended after that commit; the git history,
not this sentence, is the evidence for the ordering.*

---

## 3. The analysis as run

`experiments/analyze.py --results-root <step>` on each of the four steps, with
its defaults, which **are** the pre-registered values: `DEFAULT_RESAMPLES =
10_000` and `DEFAULT_BOOTSTRAP_SEED = 20260806`
(`experiments/statistics.py:43,46`). Nothing was passed that could change the
estimator. The mixture instrument is `power_analysis.py --section degeneracy`,
pointed at the new tree with a new `--everysec` argument that changes which
`per-execution.csv` is read and nothing else.

## 4. H1–H5

### H1 — REFUTED (on its second clause)

> *At ≥ 15 crash-free runs per arm, the barrier's cost under `everysec` excludes
> zero, and the protocol-minus-barrier figure's interval half-width falls below
> 100 ms.*

| quantity | 3 runs (published) | 15 runs (this pass) |
|---|---|---|
| barrier cost, AEP-full − B3 | 1 966.7 [477.9, 1 978.8] | **1 939.7 [1 855.8, 1 962.4]** |
| protocol − barrier, B3 − B0 | 30.5 [27.1, 1 524.6] | **33.9 [−122.6, +120.1]** |

First clause **holds**: the barrier's cost excludes zero and is now pinned to
about ±53 ms instead of a factor of four.

Second clause **fails**: the half-width is **121.4 ms** against a target of
100 ms, and the interval **spans zero**.

### H2 — SUPPORTED on its stated criterion, with the flag disagreeing

> *B3's upper-mode fraction lies in [0.15, 0.40] at 15 runs.*

Measured: **0.20** (30 of 150 executions), lower mode 2 055.8 ms (n = 120), upper
mode 5 048.3 ms (n = 30). In band.

**The `bimodal` flag did not fire**, and that is an instrument limitation rather
than evidence against the mixture. The flag requires the largest gap to exceed
half the sample's *range*; at 3 runs that was 95%, at 15 runs it is 40%, because
the wider sample contains far points that inflate the denominator while the gap
itself stays near 3 000 ms. Amendment 1 §1 ties "flagged" to that threshold and
therefore, read literally, would call H2 refuted. H2's own text is about the
fraction, and the fraction is in band.

**Both readings are reported because they disagree and it would be trivial to
quote whichever is convenient.** The pre-registered procedure for an unflagged
arm is that the pooled median stands; for completeness the lower-mode difference
is 2 055.8 − 2 039.4 = **16.4 ms** against the pooled 33.9 ms. Both are far below
the barrier's ≈ 1 940 ms, so the *ordering* survives either way.

### H3 — REFUTED as stated, on two cells that are one event each

19 of 21 (system × metric) comparisons lie between the crash-free and all-crash
rates. Two do not, both `lost_effect_rate`:

| system | p0 | p30 | crashed |
|---|---|---|---|
| B0_NAIVE_RETRY | 0.0333 | 0.0044 | 0.0111 |
| B4_DURABLE_WORKFLOW | 0.0333 | 0.0044 | 0.0074 |

Both violations sit in the **frozen p0 arm**, where 0.0333 is 1 event in 30
executions. The literal criterion fails; the cause is a single event in a
30-execution denominator, not a regime interaction. Reported as refuted rather
than reinterpreted.

### H4 — REFUTED, and this is the substantive finding of the pass

> *The alternative read-back keying leaves every headline rate inside ±5 pp.*

| metric | class | ORACLE_FINGERPRINT | CALLER_REFERENCE | delta |
|---|---|---|---|---|
| undetected duplicate | AUTH / POS-ONLY | 0.0000 | 0.0000 | +0.00 pp |
| lost effect | AUTH / POS-ONLY | 0.0000 | 0.0000 | +0.00 pp |
| declared ambiguity | AUTH | 0.0000 | 0.0000 | +0.00 pp |
| **declared ambiguity** | **POS-ONLY** | **0.4433** | **0.3500** | **+9.33 pp** |

The sensitivity variant is **not** null. The two silent columns stay at zero
under both keyings — the safety claim is unaffected — but declared ambiguity on
`POSITIVE_ONLY_READBACK` moves by 9.33 pp, nearly twice the pre-registered
margin.

### H5 — REFUTED, by 0.11 pp

> *The B3-versus-AEP-full ambiguity difference is equivalent within ±5 pp by
> TOST at α = 0.05.*

p30 regime, 45 run clusters per arm: B3 0.2089, AEP-full 0.1956, difference
**+1.33 pp**, stratified run-cluster 90% interval **[−2.67, +5.11] pp**.

TOST requires the 90% interval to lie inside ±5 pp. The upper bound is **5.11**.
Equivalence is **not** established — by 0.11 pp. Bonferroni across the three
capability classes was not reached: a joint test cannot pass where the pooled one
does not.

## 5. What this means for §VI-RQ3 and §VIII — stated, not applied

**No `.tex` file was touched in this pass.** What follows is what the numbers
imply, for a later pass to act on.

1. **§VI-RQ3's decomposition claim does not survive at 15 runs.** The sentence
   *"Everything the write-ahead protocol does apart from waiting for `fsync` …
   costs 28.0 ms"* rests on a quantity whose interval is now
   [−122.6, +120.1] ms. At this sample size the non-barrier protocol cost is
   **not resolvable from zero**. What survives is the *ordering* — the barrier
   dominates, 1 939.7 [1 855.8, 1 962.4] ms, against a non-barrier term that
   cannot be shown to be non-zero.
2. **More data did not confirm the figure, it dissolved it.** At 3 runs the
   interval excluded zero, [27.1, 1 524.6]; at 15 it includes zero and is twelve
   times narrower. That is the opposite of the usual direction and is the
   strongest available evidence that the 3-run interval was not informative.
3. **§VIII gains a finding it does not have**: the read-back keying sensitivity
   variant moves declared ambiguity by 9.33 pp on `POSITIVE_ONLY`. The
   supplementary currently lists the alternative keying as an *uncollected* gap.
   It is now collected, and it is not null.
4. **The B3-versus-AEP equivalence claim needs its regime named.** The frozen
   crashed-regime interval was [−1.11, +2.04] pp and passes; the p30 interval is
   [−2.67, +5.11] pp and fails. Any equivalence sentence must say which regime it
   holds in.

## 6. Not done, and why

- **The `always` arm of task 5.1** — out of scope by the prompt, still
  outstanding, needs `scripts/fsync_always_benchmark.sh`.
- **The two extra class-sweep sessions (4 → 6)** — out of scope, amendment 1 §2.
- **No macro regenerated, no paper number changed, zero `.tex` files touched.**
- **Bonferroni across the three classes for H5** — not computed, because the
  pooled TOST already fails and a joint test cannot pass where the pooled one
  does not.

## 7. Findings outside scope

1. **`SHA256SUMS` does not cover the raw tree** (§1.2). A `RAW-SHA256SUMS` per
   step would close it. Not added: the prompt confines writes to `**/analysis/`
   plus named scripts and reports.
2. **Regime-label drift between analysis trees.** The frozen analysis labels the
   all-crash regime `(session-3)`; the new one labels the same regime `crashed`.
   Both are `crash_probability = 1.0`. Any script joining the two trees on
   `regime` silently matches nothing — which happened twice while writing this
   report and produced an empty table that read as a clean result.
3. **R14, an eighth instance, in `power_analysis.py`, and mine.**
   `--section degeneracy` rebuilt the report without the `mixtures` key, so §A2
   printed a heading with nothing under it — indistinguishable from "no arm was
   flagged", which is H2 refuted. Caught only because the 15-run B3 arm visibly
   has two modes. Fixed twice: the key now travels with degeneracy, and **every**
   empty section now prints which kind of empty it is. Two tests pin it.

4. **`make reproduce-figures` does not pass on this clone, and it is right not
   to.** The six generated `.tex` files are **IDENTICAL** and the state-machine
   figure matches the implementation. The two analysis PDFs differ, and the
   cause is not this pass: `ARCHIVE = experiments/results/matrix`, which this
   clone holds as the **84-run incomplete snapshot** that
   `reports/phase-report-11-rescue` already records as *"An older, incomplete
   snapshot. Excluded."* The committed `MANIFEST.md` for that tree says **432
   runs / 3 780 executions**. The target regenerates the figures from 84 runs
   and compares them against figures built from 432, so they cannot match.

   *Verified not to be mine:* `git status` is clean for
   `experiments/results/matrix/` and `paper/figures/`, and every analysis write
   this pass made went to `experiments/results/ws5-2026-09-10/`.

   *The defect underneath it.* The Makefile guards this branch on the
   **presence** of raw run directories — *"regenerated only when ARCHIVE holds
   the raw run directories"* — not on their **completeness**. 84 directories is
   enough to enter the branch and not enough to reproduce, so the target reports
   *"a plotted value moved"* when the truth is *"I had 84 of 432 runs."* That is
   the R14 shape again: it can distinguish "same" from "different" but not
   "I could not have looked properly." Left alone, out of scope.

## 8. Environment

`uv run --frozen --extra experiments --extra analysis`, CPython 3.13.0,
Redis 7.2.5-alpine by digest, WSL2 6.6.114.1. Analysis run against the
measurement-host tree at `experiments/results/ws5-2026-09-10/`, 612 runs, 331 MB.
