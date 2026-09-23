# Phase 46 — RQ4: what is posed, what is answered, and the options

**No live calls. No manuscript text changed for this investigation.** The only
manuscript edits in this session are the two §IV/§V rulings, committed
separately before this report.

| | |
|---|---|
| RQ4 posed | `06-evaluation.tex:11` |
| §6.5 | `06-evaluation.tex:763–771`, **nine lines, a pointer** |
| answered in the body | **no** |
| answered in the supplementary | **partly** — outcome distribution and one incident, no per-cell result |
| evidence collected | **yes, and more than the manuscript uses** |
| macros for it in `paper/generated/` | **none** |
| added to `claims-to-review.md` | **entry 2** |
| recommendation | **Option 1**, answer it from evidence already collected |

---

## 1. (a) What is posed, and what stands

### RQ4 as posed — `paper/sections/06-evaluation.tex:11`

> \item[\textbf{RQ4}] How does recovery behave?

It sits in the same `itemize` as the other three, at
`06-evaluation.tex:4–12`. For contrast, the other three are each a two-part
question naming a quantity:

> **RQ1** Under crashes, does AEP eliminate *undetected* duplicates, and what
> does its residual ambiguity depend on?
> **RQ2** Which of the protocol's two durability mechanisms produces which
> guarantee --- and against which faults is each one observable?
> **RQ3** What does the protocol cost, and how much of that cost is a choice?

**RQ4 is the only one that names no quantity**, which is part of why it is hard
to say whether it has been answered.

### §6.5 in full — `paper/sections/06-evaluation.tex:763–771`

```latex
\subsection{RQ4 --- recovery}
\label{sec:eval-rq4}

Recovery behaviour --- how many interrupted executions the recovery
service resolves, how it resolves them, and why absolute recovery
latencies are not reported --- is in the supplementary material under
\emph{RQ4: recovery}. The outcome classes it produces are the ones
\cref{tab:outcomes} already counts, so no claim in this section depends
on it.
```

That is the whole subsection, and it is the last thing in the file — the
evaluation section ends on it at line 771. **It contains no number, no table,
no figure and no result.** Every other RQ subsection carries at least one
generated macro.

---

## 2. (b) Is RQ4 answered anywhere?

### The supplementary — `paper/supplementary.tex:640–684`, *RQ4: recovery*

The longest treatment, about 420 words. It contains three things:

**A methodological argument for not reporting a success rate** (lines 643–652):

> ``recovery success'' means two different things either side of whether a
> recovery service was running. Where one ran, a crashed execution reaching a
> terminal classification was *recovered*. Where none ran --- B0, B1, B2, B4,
> B4b declare none --- the same execution reached its classification because a
> supervisor ran the step again, which is not recovery but the thing recovery
> exists to avoid.

**One aggregate sentence** (lines 654–660):

> Within that scope: every AEP-full and B3 execution in the crashed regime
> reached a terminal classification, and across `\RunsCollected{}` runs exactly
> one recorded a reconciliation disagreement.

**An incident report** (lines 663–681), on the single voided B4b run, and a
closing statement that recovery latency is not reported because the E5 timing
gate leaves too few gated crashed runs.

### How complete is that?

| the question RQ4 asks | answered? | where |
|---|---|---|
| *how many* interrupted executions recovery resolves | **partly** — one unquantified sentence, no per-cell figure, no interval | supplementary |
| *how* it resolves them | **by reference only** — §6.5 says the outcome classes are the ones `tab:outcomes` counts | §6.5 |
| recovery latency | **explicitly not answered**, with a stated reason | supplementary + `08-threats.tex:382–387` |

**The one aggregate sentence uses `\RunsCollected{}` (432) and no other
macro.** It is the only generated number in the whole RQ4 treatment, and it
counts runs, not recoveries.

**It is also inaccurate as written**, which is the subject of
`claims-to-review.md` entry 2: 180 crashed executions (90 AEP-full, 90 B3, all
at `before_intent_write`) carry `outcome_class = NO_RECORD`, which the
project's own `is_terminal` excludes.

### Nowhere else

`paper/generated/` contains **no recovery macro**. Grepping the tracked
`numbers.tex` for `recover`, `reconcil` and `resolve` returns nothing. §6
elsewhere, §8 and the abstract contain no recovery result.

---

## 3. (c) What evidence was actually collected?

**More than the manuscript uses, and it is of the same kind and quality as
RQ1's.**

### The metric exists and is computed

`experiments/analyze.py` defines `recovery_success_rate` at lines 47–60,
674–675 and 680–684:

* **numerator** `execution.crashed and execution.is_terminal`
* **denominator** `execution.crashed`
* `is_terminal` (lines 266–273) is `outcome_class ∈ {CONFIRMED_APPLIED,
  CONFIRMED_NOT_APPLIED, DECLARED_AMBIGUOUS}`
* runs without a recovery service are **excluded**, not scored zero
  (`had_recovery_service`, line 583, from the `recovery_spawned` event)

### The collected result

`experiments/results/matrix/analysis/metric-recovery-success-rate.csv`, crashed
regime, the two systems that declare a recovery service:

| system | crash point | successes / total | rate | CI | runs | clusters |
|---|---|---|---|---|---|---|
| `AEP_FULL` | `after_intent_before_barrier` | 30 / 30 | 1.0 | [1.0, 1.0] | 3 | 3 |
| `AEP_FULL` | `after_barrier_before_dispatch` | 30 / 30 | 1.0 | [1.0, 1.0] | 3 | 3 |
| `AEP_FULL` | `mid_dispatch` | 30 / 30 | 1.0 | [1.0, 1.0] | 3 | 3 |
| `AEP_FULL` | `after_response_before_resolution` | 30 / 30 | 1.0 | [1.0, 1.0] | 3 | 3 |
| `AEP_FULL` | `after_resolution_before_barrier` | 30 / 30 | 1.0 | [1.0, 1.0] | 3 | 3 |
| `AEP_FULL` | `before_intent_write` | **0 / 30** | 0.0 | [0.0, 0.0] | 3 | 3 |

Each row above is **per response class**, and all three classes
(`AUTHORITATIVE`, `POSITIVE_ONLY`, `NO_READBACK`) carry identical values.
`B3_INTENT_NO_BARRIER` reproduces the table exactly. The five baselines carry
`0 / 0` rows, correctly excluded for having no recovery service.

Aggregated from `analysis/per-execution.csv`:

| system | where an intent existed | `before_intent_write` |
|---|---|---|
| `AEP_FULL` | **450 / 450 terminal** | 0 / 90, all `NO_RECORD` |
| `B3_INTENT_NO_BARRIER` | **450 / 450 terminal** | 0 / 90, all `NO_RECORD` |

540 crashed executions per arm, which is the same `\BthreeVsAepN{}` the
detection ablation uses.

### Is it enough, at the standard the other RQs are held to?

**For the outcome question, yes.** It is the same collection, the same regime,
the same 15 cells per system, the same seeded run-cluster bootstrap with the
same resample count and seed, and the same exclusion discipline. RQ1's headline
is a zero-event rate with a Wilson bound over 540 executions; RQ4's would be a
unit-event rate with a bootstrap interval over 450. Structurally they are the
same kind of claim.

**Two honest qualifications.** The interval is `[1.0, 1.0]` because the
bootstrap resamples 3 run clusters per cell that are all identical, so it
carries no information about between-run variation — the same criticism the
`ReplicationSessions` work made of the prevention cell. And a 100 % result over
three runs per cell is a weaker statement than the same result over thirty.

**For the latency question, no, and the paper already says so.** 176 of 432
runs have usable timing after the E5 gate (`analysis/coverage.json`), with 249
dropped for an undeclared suspend policy and 7 for clock suspension. §8 records
this as a cost of the gate. Nothing in this session changes that.

---

## 4. (d) Every dependency on RQ4

**Five locations. None is a contribution claim.**

| # | location | what it does | depends on RQ4 being *answered*? |
|---|---|---|---|
| 1 | `06-evaluation.tex:11` | poses RQ4 in the RQ list | **yes** — an unanswered RQ in the list is the whole problem |
| 2 | `06-evaluation.tex:763–771` | §6.5, the pointer subsection | **yes** — this is the place that would carry the answer |
| 3 | `supplementary.tex:640–684` | *RQ4: recovery*, the fullest treatment | **yes** — it is where the current partial answer lives |
| 4 | `08-threats.tex:382–387` | *Timing hygiene, and what it cost us*, citing *"the supplementary material, \emph{RQ4: recovery}"* for why recovery-latency distributions are not reported | **partly** — it needs the supplementary section to exist, but not the outcome question to be answered |
| 5 | `supplementary.tex:641` | `\label{supp:rq4}`, **defined and never referenced** | no |

### What does **not** depend on it

Checked and clear:

* **The abstract** (`main.tex:262–288`) — no recovery claim. It is about
  detection, prevention and cost.
* **C1–C4** (`01-introduction.tex:72–129`) — no contribution mentions recovery.
  C3 names crash points, capabilities, regimes and baselines; C4 is the
  detection/prevention decomposition.
* **`paper/cover-letter-tse.md`** — the word *recovery* does not appear.
* **`paper/arxiv-metadata.md`** — likewise.
* **There is no conclusion section.** `main.tex:301–309` inputs sections 01–09
  and stops at *Artifact Availability*.
* **§1's three mentions of "recovery process"** (`01-introduction.tex:30, 35,
  41`) are the trilemma's recovery process, not RQ4.

**So RQ4 can be answered, withdrawn or explicitly deferred without touching a
single contribution claim, the abstract, or either submission document.** That
is the most useful fact in this report.

---

## 5. The three options

### Option 1 — answer RQ4 in §6.5 from evidence already collected

**What the answer would be**, stated exactly:

> Across the crashed regime, every interrupted execution that had written an
> intent was resolved to a terminal classification by the recovery service:
> 450 of 450 for AEP-full and 450 of 450 for B3, over five crash points and
> three endpoint capabilities, with a run-cluster bootstrap interval of
> [1.0, 1.0] in every cell. At `before_intent_write` no intent exists, so there
> is nothing to resolve; those 90 executions per system are recorded
> `NO_RECORD` and are outside the metric rather than failures of it. The
> baselines declare no recovery service and are excluded rather than scored.
> Absolute recovery latency is not reported: the E5 timing gate leaves 176 of
> 432 runs with usable timing, too few gated crashed runs for a distribution.

**Macros it would use.** None exist; `scripts/paper_tables.py` would have to
emit them from `metric-recovery-success-rate.csv`, which it already reads for
nothing. Minimum set:

| macro | value | source |
|---|---|---|
| `\RecoveryResolvedAep` | 450 | `metric-recovery-success-rate.csv`, crashed, AEP-full, five crash points |
| `\RecoveryExecAep` | 450 | same, denominator |
| `\RecoveryResolvedBthree` | 450 | same, B3 |
| `\RecoveryExecBthree` | 450 | same |
| `\RecoveryNoRecordPerArm` | 90 | `per-execution.csv`, `before_intent_write` |
| `\RecoveryCrashPoints` | 5 | count of crash points where an intent exists |
| `\RunsWithUsableTiming` | 176 | `coverage.json` |

**Is the evidence at the same standard as the other RQs?** For the outcome
question, yes, with the two qualifications in §3 — the `[1.0, 1.0]` interval
carries no between-run information, and three runs per cell is thin. **Those
qualifications must be stated in the answer**, exactly as the prevention cell
states its own. For latency, no, and the answer says so rather than filling it.

**Files that would change:**

| file | change |
|---|---|
| `paper/sections/06-evaluation.tex` | §6.5 rewritten, roughly 9 lines to 25 |
| `scripts/paper_tables.py` | emit 7 new macros |
| `paper/generated/numbers.tex` | regenerated |
| `paper/supplementary.tex` | the aggregate sentence corrected (`claims-to-review.md` entry 2) |
| `tests/test_paper_tables.py` | a test per new macro, as every other macro has |

**Contribution claims changed: none.**

### Option 2 — withdraw RQ4

Remove it from the RQ list and from every dependency in §4.

**Files that would change:**

| file | change |
|---|---|
| `paper/sections/06-evaluation.tex:11` | delete the RQ4 item |
| `paper/sections/06-evaluation.tex:763–771` | delete §6.5 |
| `paper/sections/08-threats.tex:382–387` | rewrite the pointer; the timing-gate disclosure must survive |
| `paper/supplementary.tex:640–684` | retitle, since it can no longer be *RQ4: recovery* |

**What the paper loses.** The reconciliation evidence is the strongest thing in
that supplementary section and it is not really about recovery: *across 432
runs exactly one recorded a reconciliation disagreement between the event log
and an independently written oracle ledger*. That is the oracle-independence
argument, which §8 leans on, and it would need a home. The voided-run incident
likewise. Withdrawing the question does not withdraw the evidence, so this
option is mostly a relabelling exercise with a real risk of orphaning material.

**Contribution claims changed: none**, but §8's *The oracle is independent, not
infallible* would need re-pointing.

### Option 3 — keep RQ4 posed, state in §6.5 that it is not answered

**Files that would change:** `paper/sections/06-evaluation.tex:763–771` only.

**Is it defensible for TSE?** For a question the paper *cannot* answer, yes —
the manuscript already does exactly this twice, for recovery latency and for
the provably-empty cell, and does it well. **For this question, no.** The
evidence is collected, analysed, committed and shipping in the artifact. A
reviewer who opens `metric-recovery-success-rate.csv` finds a complete per-cell
result with intervals and then reads a subsection saying the question is not
answered here. That is a worse position than either answering it or removing
it, and it is the one thing in this report I would advise against.

**Contribution claims changed: none.**

### Summary

| | files touched | contribution claims | new evidence needed | net effect |
|---|---|---|---|---|
| **1 answer** | 5 | **none** | **none** | §6.5 becomes a result; one supplementary sentence corrected |
| **2 withdraw** | 4 | none | none | a question disappears; evidence needs rehoming |
| **3 defer** | 1 | none | none | the cheapest edit and the weakest position |

---

## 6. Recommendation

**Option 1.** The reasoning, in order of weight:

1. **The evidence is already collected and already analysed.** Answering costs
   no new runs and no new spend. `metric-recovery-success-rate.csv` is a
   tracked analysis product that ships in the artifact and that nothing in the
   manuscript currently reads.
2. **It touches no contribution claim, no abstract sentence and neither
   submission document.** §4's dependency list is the evidence for that. This
   is an unusually cheap thing to get right.
3. **Option 3 is the weakest position available**, for the reason given above:
   the evidence exists and a reviewer can find it.
4. **Option 2 orphans material the paper uses elsewhere** — the
   one-disagreement-in-432-runs reconciliation result supports §8's
   oracle-independence argument.
5. **Answering forces the supplementary's inaccurate sentence to be fixed**,
   which `claims-to-review.md` entry 2 has now recorded. Under options 2 and 3
   that sentence either survives or is deleted without the error being
   acknowledged.

**The one thing that would change my recommendation.** If you judge that three
runs per cell and a degenerate `[1.0, 1.0]` interval are too thin to state as a
result in the body at the standard RQ1 and RQ2 are held to, then Option 1
becomes Option 1-with-a-caveat, and the honest form is to give the counts
(450/450, 450/450) and explicitly decline to give them as a rate — the same
move §2 makes for the motivating traces. I would still prefer that to Option 3.

**I am not proposing an edit.** No manuscript text was changed for this report.

---

## 7. Verification

| | |
|---|---|
| live calls | **none** |
| manuscript changed for step 2 | **none** |
| `origin/main == HEAD` before starting | confirmed at `b7ec9eb` |
| step-1 rulings | committed separately, `8663645` |
| `check_paper_numbers.py` | **43 passed, 0 failed** |
| `check_no_repo_paths.py` | **4 builds clean, 0 failed** |
| builds, supplementaries first | **7 / 7 / 24 / 24**, all clean |
| `prove_anonymous_gate.sh` | green |
| `claims-to-review.md` | **entry 2 added** |
