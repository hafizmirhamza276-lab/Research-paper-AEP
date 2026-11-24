# Phase 53 — `after_barrier_before_dispatch` with an immediate kill

**Collected once, as pre-registered.** 45 runs, 450 executions, 15 cells,
**2.42 h** wall time, 0 skipped, 0 voided, `agrees=True` and `settled=True` in
all 45 progress records.

**No manuscript section was rewritten.** §4 below lists what would have to
change; the wording is the author's to decide.

| | |
|---|---|
| pre-registration | `prompts/phase-53-abd-immediate-2026-09-24.md`, commit `ba1638c` |
| data | commit `800d37f` |
| `check_prereg_order.py` | **ok**, prediction before data by both date and ancestry |
| **the prediction** | **REFUTED** |

---

## 1. The result against the prediction

The pre-registration predicted, as a **point** prediction, that
`applied_effects`, `undetected_duplicate`, `lost_effect` and
`dispatch_attempts` would all be **exactly zero in all 450 executions**.

**Totals: 420, 55, 4 and 448.** The prediction is refuted.

| system | class | n | applied | dup | lost | dispatch |
|---|---|---|---|---|---|---|
| B0_NAIVE_RETRY | AUTH | 30 | 32 | 2 | 0 | 35 |
| B0_NAIVE_RETRY | POS-ONLY | 30 | 35 | 4 | 1 | 38 |
| B0_NAIVE_RETRY | NO-READBACK | 30 | 39 | 8 | 0 | 41 |
| B1_LEASE_ONLY | AUTH | 30 | 35 | 5 | 0 | 36 |
| B1_LEASE_ONLY | POS-ONLY | 30 | 35 | 4 | 1 | 38 |
| B1_LEASE_ONLY | NO-READBACK | 30 | 34 | 4 | 1 | 38 |
| B2_CAS_ONLY | AUTH | 30 | 33 | 3 | 0 | 35 |
| B2_CAS_ONLY | POS-ONLY | 30 | 33 | 3 | 0 | 35 |
| B2_CAS_ONLY | NO-READBACK | 30 | 36 | 6 | 0 | 40 |
| B4_DURABLE_WORKFLOW | AUTH | 30 | 35 | 4 | 0 | 37 |
| B4_DURABLE_WORKFLOW | POS-ONLY | 30 | 36 | 6 | 0 | 36 |
| B4_DURABLE_WORKFLOW | NO-READBACK | 30 | 37 | 6 | 1 | 39 |
| **B4B_…_AT_MOST_ONCE** | **AUTH** | 30 | **0** | **0** | **0** | **0** |
| **B4B_…_AT_MOST_ONCE** | **POS-ONLY** | 30 | **0** | **0** | **0** | **0** |
| **B4B_…_AT_MOST_ONCE** | **NO-READBACK** | 30 | **0** | **0** | **0** | **0** |

---

## 2. Does the immediate kill behave as Table 3 describes?

**Yes — at the position. The kill lands before transmission, and the data says
so three independent ways.**

### 2.1 No execution anywhere applies an effect without a dispatch attempt

This is the decisive number, and it is the one that changed:

| | deferred kill (matrix) | **immediate kill (this collection)** |
|---|---|---|
| executions with `dispatch_attempts = 0` **and** `applied_effects > 0` | **82 of 90** (B4b alone) | **0 of 450** |

Under the deferred kill, B4b recorded an applied effect with **zero** recorded
dispatch attempts 82 times — the signature of a worker dying after the bytes
left but before it could write down that it had tried. **That signature is now
completely absent.** The full cross-tabulation over all 450 executions:

| `dispatch_attempts` | `applied_effects` | count |
|---|---|---|
| 0 | 0 | 90 |
| 1 | 1 | 286 |
| 2 | 1 | 17 |
| 2 | 2 | 43 |
| 3 | 1 | 2 |
| 3 | 2 | 7 |
| 3 | 3 | 5 |

Every applied effect has at least one recorded dispatch attempt behind it.

### 2.2 B4b is the control, and it is exactly zero

B4b is B4's code at B4's checkpoints with one difference: Maximum Attempts = 1,
so it does not retry. Under the immediate kill it records
**`dispatch_attempts = 0` and `applied_effects = 0` in 90 of 90 executions**,
with `status = TIMED_OUT` and `outcome_class = UNVERIFIED_FAILURE` throughout.

**A system that does not retry, killed at this point, sends nothing.** That is
Table 3's row, measured.

### 2.3 AEP-full and B3 already agreed

In the matrix, where their kill at this point was always immediate, both record
0 applied effects and 0 dispatch attempts over 90 executions, with outcomes
`DECLARED_AMBIGUOUS` 60 and `CONFIRMED_NOT_APPLIED` 30.

---

## 3. So why did four baselines still apply effects? — **and why that is a
defect in my prediction, not in the harness**

`dispatch_attempts` for B0, B1, B2 and B4 is **1, 2 or 3 — never 0**. The
killed attempt sent nothing. **The effects come from the re-execution that
follows the crash.**

In the crashed regime every execution is killed, a supervisor re-executes, and
a system with **no durable pre-dispatch record has no way to know an attempt
was already made**. So it calls again, and the call lands. B4b does not,
because it is configured never to retry. AEP-full and B3 do not, because the
intent record plus the no-re-entry transition forbids it.

**Both readings the pre-registration offered for a refutation are ruled out by
the data.** It said an applied effect would mean *"either the immediate kill is
not landing where the code says it does, or a baseline sends before the
checkpoint the injector fires at."*

* The first is refuted by §2.1 and §2.2: the kill lands before transmission,
  and a non-retrying system sends nothing.
* The second is refuted by the same: if a baseline sent before the checkpoint,
  B4b would have applied effects too. It applies none.

**The cause is a third mechanism the pre-registration did not anticipate:
post-crash re-execution.** That omission is a defect in the prediction. The
prediction reasoned about the killed attempt and silently generalised it to the
execution, and an execution in this regime outlives its first attempt.

**The prediction is recorded as refuted rather than reinterpreted.** What is
written above is what the numbers show; the prediction as registered is wrong
and stays wrong in the record. This phase was not re-run.

**What it means substantively:** at a crash point where nothing was
transmitted, the systems without a pre-dispatch record still produce duplicate
effects, and the systems with one produce none. That is the paper's own
detection claim, and this cell now demonstrates it **without** the confound of
a mis-timed kill. It is a cleaner result than the one it replaces, and it was
obtained by a refuted prediction.

---

## 4. What would have to change in the manuscript — **nothing rewritten yet**

### 4.1 Pooled baseline rates, computed the exclusion way

Per the author's decision, `after_barrier_before_dispatch` is **dropped from
the pooled baseline rates** and this collection is **not pooled** with the
matrix.

| macro | now | exclusion-computed |
|---|---|---|
| `\BaselineDupLow` | 0.77 | **0.74** |
| `\BaselineDupHigh` | 0.83 | **0.78** |
| `\BaselineDupLowPct` | 77 | **74** |
| `\BaselineDupHighPct` | 83 | **78** |
| `\BfourDupAuth` | 0.5278 | **0.4467** |
| `\BfourDupPosOnly` | 0.5889 | **0.5067** |
| `\BfourDupNoReadback` | 0.5611 | **0.4800** |
| `\BaselineDupMaxP` | 5.4×10⁻¹⁸² | recomputed over five crash points |
| `\ModelDispatchRate` | 0.596 | recomputed |

`\BfourAtBarrier` (0.9500 / 60) and `\BfourbAtBarrier` (0.9167 / 60) currently
come from the excluded cell. **Under this decision they are re-sourced from
this collection rather than withdrawn** — see §4.2.

### 4.2 New macros the separately-reported cell needs

Named so that no macro can be confused with a matrix-sourced one. Suggested
prefix `\Abd…`, with every provenance comment naming
`experiments/results/abd-immediate-2026-09-24/`.

| proposed macro | value | source |
|---|---|---|
| `\AbdRuns` | 45 | `coverage.json` |
| `\AbdExecutions` | 450 | `coverage.json` |
| `\AbdCells` | 15 | `coverage.json` |
| `\AbdDate` | 2026-09-24 | the root |
| `\AbdBfourbApplied` | 0 | B4b, all three classes |
| `\AbdBfourbDispatch` | 0 | the control that fixes the position |
| `\AbdBzeroDupNoReadback` | 0.2667 (8/30) | worst baseline cell |
| `\AbdBfourDupNoReadback` | 0.2000 (6/30) | |
| `\AbdDupRange` | 0.0667–0.2667 | across the twelve retrying cells |
| `\AbdZeroDispatchApplied` | 0 of 450 | **the headline**: no effect without a dispatch attempt |

**No timing macro may be sourced here.** `coverage.json` records
`runs_with_usable_timing: 0` and
`runs_dropped_for_undeclared_suspend_policy: 45`, as pre-registered.

### 4.3 Every manuscript place that would have to change, and what it would say

| location | what it would have to say |
|---|---|
| `03-model.tex` Table 3 caption | The qualifier added in `18f44ac` can be **narrowed**: the position is now measured as described. It should still record that the *matrix* cells were delivered later, because those are the cells the pooled rates came from |
| `06-evaluation.tex` §6.1, the paragraph added in `18f44ac` | Rewrite from "we state this rather than adjust it" to: the cell was re-collected at the intended position on 2026-09-24, it is reported separately as its own session, and the pooled rates below exclude the original cell. It must say both halves |
| `06-evaluation.tex:112-113` and `:378` | the 0.77–0.83 range becomes 0.74–0.78, and the "weakest of the three comparisons" sentence is recomputed over five crash points |
| `02-motivating.tex:29` | the same range |
| `06-evaluation.tex:245-246` | *"that is the crash point at which no effect can possibly exist"* — **now demonstrably false for four of five baselines**, and true only of systems that do not re-dispatch. The audit already flagged this sentence; this collection settles it |
| `06-evaluation.tex:159-162` | the B4-vs-Temporal sentence, §4.4 |
| `07-related.tex:208` | *"B4's rates are our model's, not the product's"*, which leans on the same comparison |
| Table 7 caption | *"Every execution in every cell was killed at one of the six crash points of Table 3"* — must be scoped to five for the baselines, or point at the new cell |
| a new §6 paragraph, or a supplementary subsection | the re-collected cell itself: what it measures, that it is one session, that it is not pooled, and the refuted prediction |
| §VIII | the refuted prediction belongs with the other disclosed refutations |

### 4.4 What happens to the Temporal comparison (S1)

**The audit's S1 is now partly answerable, and the answer changes the
sentence.**

S1 was that *"at that same crash point"* compared B4/B4b under a **deferred**
kill against B5/B5b under an **immediate** one. A correctly positioned B4/B4b
cell now exists.

| | at `after_barrier_before_dispatch`, immediate kill |
|---|---|
| **B4b** (our model, no retry) | lost 0/90, applied **0** |
| **B5b** (the engine, no retry) | `\BfivebLost` 0.1424 (84/590) |
| **B4** (our model, retries) | dup 0.1333–0.2000 per class |
| **B5** (the engine, retries) | `\BfiveDup` 0.1576 (93/590) |

**Two things follow, and they point in opposite directions.**

1. **The "roughly six times" claim does not survive.** It compared B4b's 0.9167
   against B5b's 0.1424. At the intended position B4b loses **nothing at all**,
   so the ratio is not six — it is zero against 0.1424, in the *other*
   direction. The sentence as written is not recoverable.
2. **B4-versus-B5 on duplicates is now close.** 0.1333–0.2000 against 0.1576.
   With matched kill placement, our model of a durable-execution engine and the
   engine itself land in the same range, which is a **stronger** statement about
   the model's fidelity than the paper currently makes.

**Still not like-for-like, and this must be said.** B5 kills **once per
10-execution run**; this collection kills **every execution**. Exposure still
differs even though placement no longer does. Any revived comparison has to
state that, and a fully matched comparison would need a B5 cell at one kill per
execution — which is **not** in this collection and would be another phase.

---

## 5. Verification

| | |
|---|---|
| leakage scan on the new collection | **no blocking category**; 0 credentials, 0 emails, 0 hostnames, 0 account names, 0 MACs, 0 github identities, 0 env dumps |
| non-blocking findings | a drvfs path to the measurement-host file, a `D:\` fragment, and the WSL kernel version `6.6.114.1` matched as an IP — the same profile as the existing archive |
| `check_prereg_order.py` | **cells 36, ok 31, exempt 5, failing 0** |
| tracked files | 14, by explicit `.gitignore` allow-list; the 1 052 raw run files stay out |
| voided runs | **0** |
| `all_runs_used_real_sigkill` | true |
