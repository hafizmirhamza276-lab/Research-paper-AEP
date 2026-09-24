# Phase 53 — `after_barrier_before_dispatch` re-collected with an immediate kill

**Pre-registration. Committed before any data of this phase exists.**
Rule 5 (`docs/26` §3): a cell's prediction is committed before its first data
commit, checked by `scripts/check_prereg_order.py` on both commit date and
ancestry.

**Author decision, 2026-09-24:** re-collect. The cost is machine time only, and
the alternative (exclusion) would delete `\BfourAtBarrier`,
`\BfourbAtBarrier` and the paper's only third-party comparison.

---

## 1. Why this collection exists

`reports/audit-response-2026-09-23.md` §1 established, from code and data, that
for the five baseline systems the roadmap names `after_barrier_before_dispatch`
and `mid_dispatch` resolve to a single position
(`experiments/baselines/crash_points.py`), that this position is the whole of
`DEFERRED_BASELINE_POINTS`, and that `experiments/harness/injector.py` chooses
the kill style from the **resolved value** rather than the roadmap name. The
baselines were therefore killed by a watchdog **inside the socket wait** at a
cell the paper labels "before dispatch".

AEP-full and B3 are unaffected: `experiments/harness/crash_points.py` gives the
two names different values and defers only `mid_dispatch`.

**Measured consequence in the collected matrix**, crashed regime, at that cell:
AEP-full and B3 apply 0.000 effects with `dispatch_attempts = 0` in 90/90;
B0, B1, B2 and B4 apply 2.09–2.32; B4b records zero dispatch attempts **and**
an applied effect in 82 of 90 executions.

This collection measures what the cell was supposed to measure.

## 2. Scope

**Exactly the cells the defect touches, and no others.**

| | |
|---|---|
| systems | `B0_NAIVE_RETRY`, `B1_LEASE_ONLY`, `B2_CAS_ONLY`, `B4_DURABLE_WORKFLOW`, `B4B_DURABLE_WORKFLOW_AT_MOST_ONCE` |
| crash point | `after_barrier_before_dispatch` **only** |
| regime | `session-3` (crashed; p(crash) = 1.0) |
| capability classes | all three: `payments` → AUTHORITATIVE_READBACK, `notifications` → POSITIVE_ONLY_READBACK, `ledger_postings` → NO_READBACK |
| keying | `CALLER_REFERENCE` only, matching the original cells |
| tiers | ≤ 4, which excludes the tier-5 `ORACLE_FINGERPRINT` sensitivity |
| **crash style** | **`SIGKILL_IMMEDIATE`**, via `AEP_HARNESS_CRASH_STYLE` |
| cells | **15** |
| runs | **45** (3 per cell) |
| executions | **450** (10 per run) |
| workers | 2 |
| matrix seed | **20260806**, the same seed as the original cells |
| estimate | **1.74 h** of run time by the planner's own model |
| results root | `experiments/results/abd-immediate-2026-09-24/` |

**Out of scope, deliberately:** AEP-full and B3 (already immediate at this
point); B5/B5b (the Temporal worker reads the roadmap name directly and was
never affected); every other crash point; every other regime.

**No code change.** `AEP_HARNESS_CRASH_STYLE` is honoured ahead of the mapping
(`injector.py:208-209`), and the worker environment inherits the parent's
(`runner.py:184`). `tests/test_crash_point_mapping.py::test_the_environment_override_beats_the_mapping`
pins that the override works for all five systems.

## 3. The prediction

**An immediate kill at `after_barrier_before_dispatch` happens before any
provider byte is sent. Therefore, for every one of the 15 cells:**

1. **`applied_effects` is 0 in every execution.** Mean applied effect per cell
   is exactly 0.000.
2. **`undetected_duplicate` is 0 in every execution.** There is no effect to
   duplicate.
3. **`lost_effect` is 0 in every execution.** There is no effect to lose.
4. **`dispatch_attempts` is 0 in every execution.**

This is what AEP-full and B3 already record at this cell, and what
`\cref{tab:crashpoints}` (Table 3) says the position means: *record durable; no
effect*.

**The prediction is registered as a point prediction, not a bound.** All four
quantities are predicted to be exactly zero across all 450 executions.

## 4. What would count as failure, and what each failure would mean

| observation | reading |
|---|---|
| all four quantities zero in all 450 executions | **The prediction holds.** The mapping was the whole defect, and the cell now measures the position Table 3 names |
| **any** execution with `applied_effects > 0` | **The prediction is refuted, and the mapping was not the only problem.** An effect reached the provider despite a kill placed before transmission, which means either the immediate kill is not landing where the code says it does, or a baseline sends before the checkpoint the injector fires at. Either is a defect in the harness or in that baseline, and it is a **larger** finding than the mapping |
| any `undetected_duplicate = 1` | as above, and it would also mean the duplicate rates at this cell are not an artefact of deferral alone |
| any `dispatch_attempts > 0` with `applied_effects = 0` | the request was attempted and did not land; the kill is close to the boundary rather than before it. Reportable, weaker than the row above |
| a run voids, or the reconciliation disagrees | the run is reported as voided with its reason; the cell is reported with the reduced n rather than re-run |

**On refutation.** A refuted prediction is reported as refuted. It is not a
reason to adjust the collection, and this phase will not be re-run to obtain a
different answer. `prompts/phase-40-amendment-2` and the write-loss refutation
in §6.3.4 are the precedent.

## 5. The result is NOT pooled with the matrix

**This is the load-bearing constraint of this pre-registration.**

The matrix was collected in early August. This cell is collected on
2026-09-24. They are **different sessions**, and this project does not pool
across sessions: `docs/33` records the `redis-kill-preack` cell producing 10,
20, 12, 4 and 7 applied effects across five identical sessions,
over-dispersion **5.37** against binomial.

Therefore:

1. **The pooled baseline rates in the manuscript are computed the exclusion
   way** — over the five crash points that were delivered where they are
   named, with `after_barrier_before_dispatch` dropped from the pooled
   baseline figures.
2. **This cell is reported separately, as its own session**, with its own
   macros, its own n, and its date.
3. **No macro mixes the two.** No rate is computed over the union of this
   collection and the matrix.
4. The manuscript states that the cell was re-collected, why, and that the two
   are not pooled.

**Neither number claims more than it has:** the pooled rates describe data
collected as described, and the re-collected cell describes the intended
position measured once, in one session.

## 6. Analysis, fixed in advance

**Reported, per cell and pooled within this collection only:**
`applied_effects` mean and total; `undetected_duplicate` count and rate;
`lost_effect` count and rate; `dispatch_attempts` distribution; the count of
executions and runs; and any voided run with its reason.

**Not reported from this collection:** timing. The host is not declared
suspend-disabled for this run (`suspend_disabled_declared: false` in the plan),
so the E5 gate contributes no timing, and no latency macro may take a value
from here.

**Comparison against the original cell** is reported as a difference between
two sessions and labelled as such. It is not a paired statistical test: n = 1
session per condition, and the project's own rule about four-session designs
(§9.4) applies with more force at one.

## 7. Stop rule

* **Stop and report** on any harness error, any refusal by the runner, or any
  void condition, preserving the results directory as it stands.
* **Do not fix and re-run** inside this phase. A defect found mid-collection is
  a finding of this phase, and closing it is a different phase with its own
  pre-registration.
* AEP-full is not in this collection, so the D4 halt-on-undetected-duplicate
  rule has nothing to fire on; the runner's default halt behaviour is left on
  regardless.

## 8. Provenance

* **Results root:** `experiments/results/abd-immediate-2026-09-24/`
* **Command:** `experiments/run_matrix.py` with `--regime session-3`,
  `--crash-point after_barrier_before_dispatch`, `--keying CALLER_REFERENCE`,
  `--max-tier 4`, the five systems above, and
  `AEP_HARNESS_CRASH_STYLE=SIGKILL_IMMEDIATE` exported.
* **Gate entry:** `scripts/check_prereg_order.py` `EXPECTED` gains
  `experiments/results/abd-immediate-2026-09-24` naming this file.
* **Report:** `reports/phase-report-53-abd-immediate-2026-09-24.md`.
