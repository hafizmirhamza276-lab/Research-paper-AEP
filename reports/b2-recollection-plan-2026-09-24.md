# B2 — the re-collection plan, and the alternative

**Nothing was collected. No live calls.** This document establishes what each
option would cost and what it would change. The recommendation is at §7 and is
a recommendation, not a decision.

**The defect, in one line.** For B0, B1, B2, B4 and B4b the roadmap names
`after_barrier_before_dispatch` and `mid_dispatch` resolve to one position, and
the harness delivers it with a watchdog that fires inside the socket wait — so
the cell named "before dispatch" measures a kill *during* transmission.
AEP-full and B3 are unaffected. Verified in
`reports/audit-response-2026-09-23.md` §1.

**Part 1 is done and is in the tree:** the docstring is corrected, twenty tests
pin both mappings and the delivered kill style, and §6.1 discloses what was
delivered. **No number has been changed.** This document is about whether to
change them, and how.

---

## 1. Exactly which cells

**15 cells, 450 executions, 45 runs, 10 executions per run.**

| system | capability class | executions | runs |
|---|---|---|---|
| B0_NAIVE_RETRY | AUTHORITATIVE_READBACK | 30 | 3 |
| B0_NAIVE_RETRY | POSITIVE_ONLY_READBACK | 30 | 3 |
| B0_NAIVE_RETRY | NO_READBACK | 30 | 3 |
| B1_LEASE_ONLY | AUTHORITATIVE_READBACK | 30 | 3 |
| B1_LEASE_ONLY | POSITIVE_ONLY_READBACK | 30 | 3 |
| B1_LEASE_ONLY | NO_READBACK | 30 | 3 |
| B2_CAS_ONLY | AUTHORITATIVE_READBACK | 30 | 3 |
| B2_CAS_ONLY | POSITIVE_ONLY_READBACK | 30 | 3 |
| B2_CAS_ONLY | NO_READBACK | 30 | 3 |
| B4_DURABLE_WORKFLOW | AUTHORITATIVE_READBACK | 30 | 3 |
| B4_DURABLE_WORKFLOW | POSITIVE_ONLY_READBACK | 30 | 3 |
| B4_DURABLE_WORKFLOW | NO_READBACK | 30 | 3 |
| B4B_…_AT_MOST_ONCE | AUTHORITATIVE_READBACK | 30 | 3 |
| B4B_…_AT_MOST_ONCE | POSITIVE_ONLY_READBACK | 30 | 3 |
| B4B_…_AT_MOST_ONCE | NO_READBACK | 30 | 3 |
| **total** | | **450** | **45** |

**One crash point only:** `after_barrier_before_dispatch`, crashed regime.
`mid_dispatch` is already what it says it is and is not re-collected.

**Not in scope:** AEP-full and B3, whose kill at that point is already
immediate; B5/B5b, whose Temporal worker reads the roadmap name directly and
was never affected; every other crash point and every other regime.

**How it would be run.** No code change is needed.
`AEP_HARNESS_CRASH_STYLE=SIGKILL_IMMEDIATE` is honoured ahead of the mapping
(`RunConfig.crash_style` → `runner.py:206-207` → `injector.py:208-209`), and
`tests/test_crash_point_mapping.py::test_the_environment_override_beats_the_mapping`
pins that it works for all five systems.

---

## 2. How long, on this host

From `experiments/results/matrix/matrix-progress.jsonl`, which records
`wall_seconds` per run:

| | |
|---|---|
| median over all 101 records | **59.4 s** |
| median over the 47 baseline records | **143.9 s** |
| median over the 11 baseline records at this crash point | **144.2 s** |
| min / max, all records | 3.0 s / 176.3 s |

Baseline runs at this crash point are the slow end, because a deferred kill
runs the full 0.4 s watchdog delay and the provider's two-second call.

**45 runs × 144 s ≈ 1.8 hours of run time.**

Adding the observed inter-run overhead (median 48 s between consecutive
`summary.json` writes in the tracked subset, which includes Redis provisioning
and per-run teardown) gives **≈ 2.4 hours**. With pre-flight verification,
analysis and the manifest/digest work the project does after every collection,
budget **3 to 4 hours end to end**, one uninterrupted session on the one host.

**Cross-check against the paper's own figure.** §IX states the full plan is
1 068 runs at an estimated 25 h, or ≈ 84 s per run averaged over all systems.
45 runs at the baseline median of 144 s is the same order and is the
appropriate rate for these particular cells.

**The host must be quiet.** `docs/25` and the supplementary's incident record
require it: the project has already discarded a batch because its own
integration suite ran against the same Redis.

---

## 3. Cost — **no API cost. Confirmed.**

* The matrix calls the **mock provider** in `experiments/mock_api/`, in-process
  and local. `experiments/run_matrix.py` imports only
  `experiments.mock_api.config`; grep for `AZURE`, `api.openai`,
  `cognitiveservices` and `AEP_PLANNER_MODE` across `run_matrix.py` and
  `harness/runner.py` returns **nothing**.
* Workers take the **scripted** planner branch unless `AEP_PLANNER_MODE` opts
  in, and the matrix never sets it. The scripted branch executes a plan fixed
  before the run and issues no model call.
* The only hosted-API spend this project has ever incurred is phase 40, which
  is **closed** (`prompts/phase-40-closure-2026-09-22.md`), total
  USD 0.00775720.

**Cost is machine time and the author's attention. Nothing is billed.**

---

## 4. Pre-registration — **a new collection needs one, and this one is not exempt**

`scripts/check_prereg_order.py` enforces **rule 5** (`docs/26` §3): *"a cell's
prediction is committed before its first data commit"*, checked both by commit
date and by ancestry.

**The original matrix is exempt, and the exemption does not transfer.** Its
`EXPECTED` entry (`check_prereg_order.py:68-73`) reads:

> `predates_rule=True` — *"The 432-run evaluation, collected across early
> August before rule 5 existed. Its design is recorded in the phase 2B and
> session-3 reports, not in a pre-registration."*

Rule 5 was adopted in the phase 8 pre-registration on **2026-08-27**. A
collection run now is governed by it. The gate enumerates **from the data**, so
a new tracked root with no `EXPECTED` entry is a **failure**, not a silent
skip.

### What would have to exist, before any data is written

1. **A pre-registration**, committed first —
   `prompts/phase-NN-abd-immediate-<date>.md`. It would have to state:
   * the defect, and that the cell is being re-collected because the delivered
     position differed from the named one;
   * the exact cells (§1), the crash style, the seeds and the run count;
   * **the prediction.** This is the load-bearing part: an immediate kill
     before transmission should produce **no applied effect and no duplicate**
     for every baseline at this cell, as it already does for AEP-full and B3.
     A baseline that still duplicates would mean the mapping is not the only
     thing wrong;
   * the analysis, fixed in advance: which macros are recomputed, and that the
     old cell is **superseded rather than pooled with** the new one;
   * the stop rule, and what would void a run.
2. **An `EXPECTED` entry** in `check_prereg_order.py` naming that file.
3. **A new collection root** — `experiments/results/abd-immediate-<date>/`,
   not an edit of `experiments/results/matrix/`. The matrix's files are under
   SHA-256 manifests in the published archive and their bytes must not move.

### The constraint that makes this more than bookkeeping

The paper's own rule is that **regimes and sessions are never pooled**: a rate
computed across collections is a property of how many runs of each kind were
collected. A cell re-collected in late September on a different day is a
**different session** from the early-August matrix.

So the re-collected cell cannot simply be dropped into the pooled baseline
rates. Either the pooled rates are recomputed with the new cell **and the
session difference is disclosed**, or the affected rates are reported per
session. This is the same between-session variance the project has already
been bitten by: `docs/33` records the `redis-kill-preack` cell recording 10,
20, 12, 4 and 7 applied effects across five identical sessions, over-dispersion
**5.37** against binomial.

**A re-collection therefore buys a correct cell and a new confound.** That is
not an argument against doing it, but it is an argument against expecting the
result to be a clean substitution.

---

## 5. What would have to be regenerated afterwards

### Macros (`paper/generated/numbers.tex`, via `scripts/paper_tables.py`)

| macro | as collected | excluding the cell | after re-collection |
|---|---|---|---|
| `\BaselineDupLow` | 0.77 | **0.74** | unknown; predicted lower still |
| `\BaselineDupHigh` | 0.83 | **0.78** | unknown |
| `\BaselineDupLowPct` / `\BaselineDupHighPct` | 77 / 83 | **74 / 78** | unknown |
| `\BaselineDupMaxP` | 5.4×10⁻¹⁸² | recomputed | recomputed |
| `\BfourDupAuth` | 0.5278 | **0.4467** | unknown |
| `\BfourDupPosOnly` | 0.5889 | **0.5067** | unknown |
| `\BfourDupNoReadback` | 0.5611 | **0.4800** | unknown |
| `\BfourAtBarrier` / `\BfourAtBarrierExec` | 0.9500 / 60 | **withdrawn** | recomputed |
| `\BfourbAtBarrier` / `\BfourbAtBarrierExec` | 0.9167 / 60 | **withdrawn** | recomputed |
| `\ModelDispatchRate` | 0.596 | recomputed | recomputed |

### Tables and figures

* **Table 7** (`generated/table-outcomes.tex`) — every baseline cell, and its
  caption, which currently says *"Every execution in every cell was killed at
  one of the six crash points of Table 3"*.
* **Figure 2** — the per-system duplicate/ambiguity picture.
* **Supplementary Table 1** (`table-ambiguity-by-crashpoint.tex`) — the
  by-crash-point decomposition, where this cell is a column.
* `table-ablation.tex` if any pooled baseline rate feeds it.

### Prose that carries a number or a claim about the cell

| location | what changes |
|---|---|
| `02-motivating.tex:29` | the 0.77–0.83 range |
| `06-evaluation.tex:112-113` | the same range, and the "weakest of the three comparisons" sentence |
| `06-evaluation.tex:378` | `\BaselineDupLowPct`–`\BaselineDupHighPct`\% |
| `06-evaluation.tex:159-162` | *"at that same crash point … roughly six times the engine's rates"* — **withdrawn under exclusion**, recomputed under re-collection |
| `06-evaluation.tex:245-246` | *"that is the crash point at which no effect can possibly exist"* — already flagged by the audit as overstated |
| `03-model.tex` Table 3 caption | reverts to unqualified **only if** re-collection makes the delivered position match the named one |
| `06-evaluation.tex` §6.1 | the disclosure added in Part 1 changes meaning: under re-collection it becomes a historical note, under exclusion it stays |
| `07-related.tex:208` | *"B4's rates are our model's, not the product's"*, which leans on the same comparison |

### Counts

Under **exclusion**, the crashed regime loses **450 executions and 45 runs**.
`\RunsCollected` (432), `\ExecutionsCollected` (3 780) and `\CellsCollected`
(126) describe the whole collection including other regimes, so they do not
change under exclusion — but §6.1 would have to say that 15 cells are reported
from five crash points rather than six.

Under **re-collection** the counts are restored, from a different session.

---

## 6. The alternative: exclude the cell

**What it is.** Drop `after_barrier_before_dispatch` from the pooled baseline
rates, keep it for AEP-full and B3 where it is correct, and say why.

**What changes:** every macro, table, figure and prose site in §5, with the
"excluding the cell" column as the new value. No collection, no
pre-registration, no new session confound. **Class (b): re-analysis of data
already collected.** Hours, not a session.

**What the paper loses.**

1. **A crash point, asymmetrically.** AEP-full and B3 would be reported over
   six crash points and the baselines over five. Table 7's rows stop being
   like-for-like in a second, different way — which is the thing the exclusion
   is meant to fix. §6.1 would have to state it plainly.
2. **The B4-versus-Temporal comparison.** `\BfourAtBarrier` and
   `\BfourbAtBarrier` **are** the excluded cell. They have no other source, so
   the *"roughly six times the engine's rates"* sentence and the paragraph
   around it are withdrawn, not adjusted. That is the paper's only comparison
   against a third-party engine, and the audit's S1 already says it is not
   like-for-like — so exclusion resolves S1 by deleting it.
3. **The strongest baseline cell.** This is where B0/B1/B2 duplicate most
   (0.92–0.97) and where B4b's loss rate is 0.911. Removing it lowers every
   baseline rate and makes AEP-full's advantage look *smaller*. Exclusion is
   the conservative direction, which is worth stating — the paper would be
   giving up its most favourable cell.
4. **Coverage against the roadmap.** §IX and the coverage record describe six
   crash points. The manifest would carry a documented gap.

**What it does not lose:** the headline separation. AEP-full and B3 record zero
undetected duplicates and zero lost effects with or without the cell, on every
capability class. Every comparison keeps its direction.

---

## 7. Recommendation — **exclude now, re-collect only if the schedule allows**

**Reasoning, in the order that decided it.**

1. **Exclusion is correct on its own terms, and available immediately.** Every
   number it produces is computed from data that was collected as described. A
   rate over five crash points that says so is a true statement; a rate over
   six that includes a mislabelled one is not.

2. **Re-collection does not fully restore what it appears to restore.** The
   new cell would be a different session, and this project has measured
   over-dispersion of 5.37 across identical sessions in a comparable cell.
   Pooling it with early-August runs violates the paper's own no-pooling rule;
   reporting it separately leaves Table 7 with one cell from a different date.
   **Re-collection trades a known, disclosable defect for an unknown
   between-session one.**

3. **Exclusion moves the numbers against the paper's own case.** Baseline
   duplicate rates fall from 0.77–0.83 to 0.74–0.78 and B4's from ~0.56 to
   ~0.48. A reviewer reading a correction that weakens the author's own
   comparison reads it as a correction, not as a repair.

4. **The cost asymmetry is real but not decisive.** Three to four hours is
   affordable. What is not obviously affordable is the pre-registration, the
   new root, the manifest work, and the analysis of a cross-session
   comparison — and the deposit is already a submission blocker.

**Against my own recommendation, and it is the strongest point:** exclusion
deletes the only third-party comparison in the paper. If the Temporal
comparison is judged load-bearing for the related-work claim, then it has to be
re-collected rather than excluded, because there is no version of it that
survives exclusion. **That is the question to decide first**, and it is a
judgement about the paper's argument rather than about the data.

**If both are wanted:** exclude now so the manuscript is correct, and record
the re-collection as a named item. The excluded cell is not destroyed — it
stays in the archive and in the manifest, and a later session can add the
immediate-kill cell under a proper pre-registration and restore the
comparison with the session difference disclosed.

**Neither option was started.**
