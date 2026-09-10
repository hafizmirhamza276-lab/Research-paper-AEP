# Option B feasibility probe — the binding problem and the reachability problem

**Design and read-only analysis, 2026-09-10.** No agent workload collected. No
code built. No paper touched.

**Why nothing was built.** The instruction was not to start until the WS-5
collection has finished and its data is committed. At the time of writing WS-5
is at **42 of 105 runs in step 1 of 4**, with no `COMPLETE` sentinel. Design and
read-only analysis cannot disturb a running collection, so they are done here;
**the instrument is specified in §5 and deliberately not built.** Nothing in this
pass ran Python against the harness, touched Docker, or ran the suite.

---

## 0. Two corrections to docs/34, both mine

docs/34 was committed yesterday and the probe's premise inherited two errors
from it. Both change the answer, so they come first.

### 0.1 `write-loss-preack` runs ten executions per run, not one

docs/34 §5.3 says *"`redis-kill-preack`, `redis-kill-inflight` and
`write-loss-preack` all set `executions_per_run=1`."* **The third is wrong.**
Read from `experiments/run_matrix.py` directly:

| regime | `executions_per_run` | `crash_probability` |
|---|---|---|
| `(session-3)` | 10 | 1.0 |
| `p0` | 10 | 0.0 |
| `p30` | 10 | 0.3 |
| `redis-kill-preack` | **1** | 0.0 |
| `redis-kill-inflight` | **1** | 0.0 |
| `write-loss-preack` | **10** | 0.0 |
| `redis-pause-kill-preack` | **1** | 0.0 |

The three single-execution regimes are the two Redis kills and
**`redis-pause-kill-preack`** (Phase 13 Arm A / WS-3), which docs/34 did not
mention at all.

*How the error was made, because it is a repeatable one.* docs/34 read a grep of
`executions_per_run=` and `redis_kill_executions=` together; `write-loss-preack`
sets `redis_kill_executions=1` on the line the grep surfaced, and the adjacent
`executions_per_run=10` was two lines away and not in the output. The regime
block was never read. That is inference from a grep window presented as a fact
about a file.

**Consequence: it inverts docs/34's conclusion.** docs/34 said the workload
"cannot reach the write-loss regime" and that drift "would be measured exactly
where the two arms are hardest to tell apart." Neither follows. See §4.

### 0.2 "AEP-full withholds and B3 proceeds" is a pre-registration, not a result

docs/34 §4 wrote *"under block-level write loss AEP-full withholds dispatch and
B3 proceeds"* as measured evidence. It is not. That sentence is docs/26 §4 task
**4.2's pre-registered prediction**.

What WS-4 actually established is a **storage-level probe**: `dm-flakey`
`drop_writes` under a Redis whose AOF is on the affected device, writing one key
through `WAITAOF` and one without, then reading both back — `\FlakeyAckSurvived`
= 90/90, `\FlakeyUnackLost` = 90/90 across `\FlakeyReplications` = 3
replications. That is a claim about the barrier's premise, not about what
AEP-full and B3 each do while running the workload.

Checked: `grep write-loss experiments/results/*/analysis/per-cell-metrics.csv`
returns nothing. **The `write-loss-preack` regime is implemented and has never
been collected.**

---

## 1. The binding problem: it has a solution, and it is smaller than docs/34 said

### 1.1 What the binding actually is

Two independent environment variables, set by
`experiments/harness/runner.py:worker_environment()`:

* `AEP_HARNESS_CRASH_POINT` — a **kind**: an instruction boundary in the
  protocol (`mid_dispatch`, `after_intent_before_barrier`, …).
* `AEP_HARNESS_CRASH_EXECUTIONS` — a comma-separated set of **execution ids**,
  computed before the run starts.

The injector (`experiments/harness/injector.py:259`) fires on the conjunction:

```python
async def checkpoint(self, point):
    if self._fired or point is not self.plan.point:   # kind must match
        return
    if not self.armed_for_current_execution:          # id must be in the set
        return
    self._fired = True
```

### 1.2 The gate docs/34 said this is in tension with is B5-only

`VOID_CRASH_POINT_MISMATCH` exists in exactly one place:
`experiments/baselines/b5_temporal/gate.py:49`. Its docstring says why it is
special — *"the one void here that cannot be detected by looking at the run
alone: every other verdict asks 'did the instrument work?', this one asks 'did
it do what this cell claims it did?'"* — and it exists because Temporal's
activity lifecycle does not map onto the roadmap's six points, so a run **can**
be cut somewhere other than its label claims.

**In the main harness that cannot happen.** The injector fires only when
`point is self.plan.point`. The delivered point equals the planned point by
construction; there is nothing for a mismatch gate to catch, and there is no
such gate (`grep -n "void" experiments/run_matrix.py` returns nothing; the
runner counts `crash_injected` events and nothing compares points).

And B5 cannot host drift at all — `can_declare_ambiguity=False`, docs/34 §3. So
**the gate and the agent workload never meet.** docs/34 generalised a B5 gate
into a harness property and built a tension on it.

### 1.3 What the cell should name under a planner

**A step kind and a step index, which is what it already names, and neither
needs redesign.**

* *The kind is planner-independent.* `mid_dispatch` is "inside the socket wait"
  no matter which tool the planner selected. The protocol traverses the same
  named boundaries for any tool call, because the boundaries are in
  `aep_core`, not in the workload.
* *The index survives too, for a reason that is easy to miss.* Execution ids come
  from `workload._execution_id(run_id, seed, worker, index)` — **a function of
  position, not of content**. Step 3 of worker 1 has the same id whatever the
  planner decides to do at step 3. So "crash the 3rd execution of worker 1"
  remains computable before the run, exactly as today, and
  `crash_execution_ids` can be built unchanged.

A *trajectory-relative* binding — "crash at the first step after an ambiguous
one" — was considered and is rejected: it makes the fault's position an outcome
of the run, so two runs in the same cell would be cut at different places and
the cell would no longer name one experiment. That is precisely the defect
`VOID_CRASH_POINT_MISMATCH` exists to prevent, reintroduced by design.

### 1.4 What it costs: the planner may not stop early

There is one real incompatibility, and it is with docs/33 §1.4, not with the
gate. docs/33 specifies a run as a sequence *"until STOP or budget"* — a
**variable-length** run. The crash-execution set is fixed before the run. If the
planner stops at step 2 and the cell armed step 3, the armed point is never
reached and the run is void.

Two ways out, and the choice is a real trade:

| option | what it preserves | what it costs |
|---|---|---|
| **(a) Fixed-length runs.** The planner must emit exactly `executions_per_run` steps; STOP is not in its action space. | The existing binding, the existing void semantics, comparability with every frozen cell. | A degree of freedom docs/33 wanted. A planner that cannot stop is less agent-like, and §5.2's honesty paragraph gets one more line. |
| **(b) Variable-length runs.** Arm "step *k* if it exists, else void." | docs/33's STOP. | A new void class whose **rate depends on the planner** — an instrument whose failure rate is itself an experimental outcome. Void rates would differ between AEP-full and B3 if their observations differ, which is the thing being measured. |

**(b) is the one that would break the gate's purpose**, so if Option B proceeds
the binding should be (a), and the restriction should be stated in §5.2 rather
than discovered later.

**Answer: the binding problem is solvable, at the cost of fixed-length runs.**
No change to the injector, the crash-point mapping, or the void semantics.

---

## 2. The reachability problem

### 2.1 Is `executions_per_run=1` hard, or configured?

**Configured, but load-bearing — and it does not need changing.**

It is not physically forced: `redis_kill.kill_and_restart()` does bring the
container back, so a second execution *could* run afterwards. What makes it
load-bearing is what raising it would do:

1. Rates in those cells are over **executions**. Adding nine unfaulted
   executions to a run containing one faulted execution changes every
   denominator, so the new cells would not be comparable with the 30-run frozen
   ones without re-collecting them.
2. `redis_kill_executions=1` targets one execution; the rest would be
   post-fault control executions sharing a run with a faulted one — a different
   experiment, not a longer version of the same one.

So it is a decision that could be reversed at the price of re-collecting three
regimes. **It does not have to be, because a drift-reachable regime with ten
executions already exists.**

### 2.2 Where drift is reachable

Drift needs three things at once: more than one execution per run; a system that
can declare ambiguity (AEP-full and B3 only, docs/34 §3); and at least one
ambiguous step with a later planner decision.

| regime | ≥2 exec | ambiguity possible | drift reachable | data today |
|---|---|---|---|---|
| `(session-3)` | ✓ 10 | ✓ crash 1.0 | **yes** | collected |
| `p30` | ✓ 10 | ✓ crash 0.3 | **yes** | **being collected now by WS-5** |
| `write-loss-preack` | ✓ 10 | ✓ | **yes** | **never collected** |
| `p0` | ✓ 10 | ✗ crash 0.0 | no — no ambiguous step | collected |
| `redis-kill-preack` | ✗ 1 | ✓ | **no** — no "after" | collected |
| `redis-kill-inflight` | ✗ 1 | ✓ | **no** | collected |
| `redis-pause-kill-preack` | ✗ 1 | ✓ | **no** | collected |

**Drift is reachable in three regimes, not zero.** Within them, the cells are
AEP-full and B3 only, across the three capability classes.

### 2.3 Are those the cells where the arms already differ by 0.37 pp?

**Partly, and the part that matters is unmeasured.**

The +0.37 pp figure is the pooled declared-ambiguity difference in the
**crashed (session-3)** regime, 90% run-clustered interval
**[−1.11, +2.04] pp**, with per-class rates 0.7222 (AEP-full) against 0.7167
(B3) under NO_READBACK. So:

* **`session-3` — the only drift-reachable regime with data — is exactly where
  the two arms are indistinguishable.** docs/33 §4.4's uncomfortable prediction
  applies here at full force: same observation in, same planner, so the expected
  drift difference is zero, and a zero result would be uninformative about the
  protocol rather than informative about the caller.
* **`p30` is unmeasured** on this axis; WS-5 is collecting it as this is written,
  so the ambiguity differential there will be known shortly and is not knowable
  now.
* **`write-loss-preack` is the regime where the arms are *predicted* to differ**
  — docs/26 task 4.2's prediction, still unfired — **and it has ten executions
  per run.** It is the one cell where drift could show a difference rather than
  a tie, and collecting it is a prerequisite for the drift experiment being
  worth running at all.

**So the honest statement is the reverse of docs/34's.** Drift is observable;
what is not yet established is whether there is anything for it to observe, and
the experiment that would establish that is a regime nobody has collected.

---

## 3. What restoring `74ea31f` would now touch

Not restored, per instruction. Scope established.

docs/34 warned that the fallback-to-`target` reader is load-bearing for more
data than when the revert was justified. That is right, and there is a sharper
problem underneath it.

**The check that justified the revert cannot be re-run from this clone.**
`74ea31f` asserts *"1364 collected ledgers checked, ZERO carry the column."*
This clone holds **473** `ground_truth.sqlite3` files, of which only **84** are
under `experiments/results/matrix` — and `reports/phase-report-11-rescue` already
records that the clone's matrix is *"an older, incomplete snapshot. Excluded."*
The 1364 figure is from the measurement host's tree (`/root/aep`), not from here.

So re-verifying "nothing is stranded" before a restore requires the measurement
host, and the corpus has grown three ways since: WS-6's B5 sessions, WS-5's
in-flight ~600 runs (46 present at the time of writing), and everything the
matrix holds on the host but not here.

**What a restore touches, in order:**

1. `git revert 74ea31f` for the code — clean; 6 of 8 files untouched since, the
   7th has an empty diff for that path (docs/34 §2.1).
2. Re-run the stranded-ledger check **on the measurement host**, against a corpus
   now well over 1364 and still growing. This is the gate, and it is the step
   that cannot be done from a laptop clone.
3. The `ledger/2` bump, and the fallback reader for every `ledger/1` ledger —
   which is now *all* of them, so the fallback is the normal path rather than a
   legacy path, and needs a test that exercises it as such.
4. Re-author the §VIII construct-validity paragraph into WS-9's
   construct/internal/external/conclusion structure. Not restorable.

---

## 4. The instrument, specified and not built

Per instruction: the scripted planner only, seeded, distinct-targets broken, and
just enough seam to run one reachable cell. Specified here so the build is
mechanical when WS-5's data is committed.

* **`experiments/harness/planner.py`** — `Planner` protocol with
  `next_action(observation) -> ToolCall`, and `ScriptedPlanner` seeded from
  `(run_id, seed, worker_index, step_index)` exactly as `workload.py` seeds
  today. **No STOP**, per §1.4(a).
* **The distinct-targets break** — the planner draws `target` from a bounded pool
  smaller than the step count, so two steps in a run can collide by construction.
  This is the deliberate violation docs/33 §1.3 requires, and it is the whole
  reason §2 (attribution) is a prerequisite.
* **The seam** — `workload.py` currently returns a fixed list. The smallest change
  is a second constructor that yields steps from a planner while keeping
  `_execution_id(run_id, seed, worker, index)` unchanged, so §1.3's binding
  argument holds and `crash_execution_ids` needs no change.
* **The reachable cell** — `session-3`, AEP-full, NO_READBACK: the highest
  ambiguity rate in the paper (0.7222), so the ambiguous steps drift needs are
  most abundant there.
* **What it answers** — whether a seeded planner that re-plans under ambiguity
  produces `F(s') = F(s)` with `c(s') ≠ c(s)` at a measurable rate. That is the
  feasibility question; it is not a paper number and must not become one, because
  attribution (§2) is not restored and without it the duplicate metric is
  unsound under colliding targets.

**Order matters and is not negotiable:** the distinct-targets break makes
`undetected_duplicate_applications` unsound (docs/33 §2.2), so this instrument
may run only in a scratch results root and **may not write into any tree the
analysis reads** until `74ea31f` is restored.

---

## 5. What Option B would cost, accounting for both problems

docs/33 said 2–3 weeks. docs/34 said that predated two problems. Both problems
are now settled, and they are **cheaper than docs/34 implied** — one dissolves,
the other costs a design restriction rather than an engineering effort. The
increase over docs/33 comes from somewhere else.

| item | verdict | cost |
|---|---|---|
| Crash-point binding under a planner | **Solved.** No code change; fixed-length runs (§1.4a) | 0, plus one sentence in §5.2 |
| Reachability | **Solved.** Three regimes, no regime reconfiguration needed | 0 |
| **Collect `write-loss-preack`** | **New, and now the critical path** | ~30 runs × 2 systems × classes; the regime exists and is unrun |
| WS-1a code restore | Clean revert | ~1 day |
| Stranded-ledger re-check **on the measurement host** | New; cannot be done from this clone | ~0.5 day + host access |
| Fallback reader now the normal path, with a test | New | ~0.5 day |
| §VIII paragraph re-authored into WS-9's structure | Rewrite | ~0.5 day |
| Planner interface + scripted planner | As docs/33 costed | ~3 days |
| Distinct-targets break + seam | As docs/33 costed | ~2 days |
| Planner seam for B5/B5b | **Still new and undesigned** (docs/34 §5.1) | ~1 week, or a justified exclusion |
| Provider-seed replay ordering | Model-backed arm only | ~1 day |
| Pre-registration (§4.4) | Rule 5 | ~1 day |
| Agent-cell collection | 3 regimes × 3 classes × 2 systems | ~2 days machine, mostly unattended |
| Local open-weights arm | Optional | ~1 week |

**The honest number: 4–5 weeks** for the scripted-planner path including the
write-loss collection, the WS-1a restore and its host-side re-check, and a
justified exclusion of B5/B5b rather than a second planner implementation. **6–7
weeks** if B5/B5b get a real seam. **Add 1 week** for the local-model arm.

docs/33's 2–3 weeks was for the planner, the metric and the collection, and that
part of the estimate survives. What it did not carry is the restore-and-reverify
work (WS-1a was in the tree when docs/33 was written), the write-loss collection
(the regime existed but its relevance to drift was not seen), and B5/B5b (which
did not exist).

**One thing that is not a cost but should decide the question.** The only
drift-reachable regime with data is the one where AEP-full and B3 are
statistically indistinguishable at +0.37 pp [−1.11, +2.04]. If
`write-loss-preack` is not collected first, Option B's most likely outcome is a
tie that docs/33 §4.4 already predicted in writing — a result that costs four
weeks and says nothing the paper does not already say.

---

## 6. Status

Read-only. No build, no collection, no paper edit, no suite run — the WS-5
collection was left alone throughout and was at 42/105 runs of step 1 when this
was written. R15's obligation is discharged by there being no code change to
cover; the two documents this pass produced are `docs/35` and the corrections in
§0, which change no number in the manuscript.
