# Phase 10 — pre-registration: is the container runtime a confound?

**Committed and pushed before any Phase 10 run exists.** Rule 5 of
`docs/26-journal-readiness-direction.md` §3. Nothing in this file is changed
once data arrives; if it turns out to be wrong, it is wrong in the record.

**Status at the moment of writing:** the native engine is provisioned and
verified (`reports/raw/phase10-provision-native-docker.txt`), the stack is up on
it, `scripts/phase10_replication_analysis.py` is committed in this same commit,
and `experiments/results/` contains no Phase 10 directory.

---

## 1. The cell

| dimension | value | why |
|---|---|---|
| system | `aep_full` | the system every claim is about |
| endpoint | `ledger_postings` | = `NO_READBACK` (`run_matrix.py:93-97`) |
| response class | `NO_READBACK` | the capability class where nothing can rescue a dispatch |
| regime | `session-3` (`REGIME_CRASH_ALWAYS`) | the regime Table 1 is built from |
| crash points | all six | see §2 |
| keying | `CALLER_REFERENCE` | the frozen cell's keying |
| frozen source | `experiments/results/matrix/analysis/per-execution.csv` | tracked; the run directories for this cell are not in the clone, the per-execution rows are |

This is the cell the prompt proposed. It is kept.

### Why all six crash points and not one

Five of the six are **degenerate** in the frozen data and would agree trivially:

| crash point | frozen `known_ambiguity_rate` |
|---|---|
| `before_intent_write` | 0/30 |
| `after_intent_before_barrier` | 30/30 |
| `mid_dispatch` | 30/30 |
| `after_response_before_resolution` | 30/30 |
| `after_barrier_before_dispatch` | 30/30 |
| **`after_resolution_before_barrier`** | **10/30 = 0.3333** |

`after_resolution_before_barrier` is the **only** sub-cell with interior
variance, and it is therefore the only one whose agreement carries information.
The other five are kept because a runtime that turned a 0/30 into anything
non-zero, or a 30/30 into anything less, would be a far larger finding than a
moved ambiguity rate — but they are not the test.

---

## 2. Two arms, and what each isolates

`provenance.py`'s docstring records that the paper's cell "was collected in the
WSL-native tree on ext4" while the four Phase-8 replications "ran through
`/mnt/d` on drvfs, where an event-log append costs about forty times more". The
repo working tree is on drvfs. Collecting only there would confound the
filesystem with the runtime.

| arm | results root | isolates |
|---|---|---|
| **ext4** (primary) | `/root/aep-phase10/ext4-2026-09-02` | only the **container runtime** differs from the frozen cell |
| **drvfs** | `experiments/results/phase10-replication-drvfs-2026-09-02` | adds the **filesystem** difference on top |

`ext4` minus `drvfs` is therefore the filesystem effect, measured directly.

---

## 3. Run counts, and the power calculation that set them

### The matched collection — 18 runs per arm

3 runs × 10 executions at each of 6 crash points = **18 runs, 180 executions per
arm**, matching the frozen cell's shape exactly.

### The powered collection — 30 runs per arm, not 15

The plan said 15. **A power calculation done before collecting says 15 is not
enough, so it is 30.** The calculation, run against the frozen cell's own
per-run values so the null is true by construction (arm runs resampled from the
frozen per-run pairs, 40 replicates, 2 000 bootstrap resamples each):

| comparison | median half-width of the 95% difference interval |
|---|---|
| arm n=3 vs frozen (3 runs) | 0.333 |
| arm n=15 vs frozen (3 runs) | 0.300 |
| arm n=30 vs frozen (3 runs) | 0.287 |
| arm n=60 vs frozen (3 runs) | 0.292 |
| **15 vs 15, arm against arm** | **0.173** |
| **30 vs 30, arm against arm** | **0.127** |

Two things follow, and both are declared here rather than discovered later.

> **(a) The comparison against the frozen cell cannot be made conclusive at
> ±15 pp by collecting more.** Its half-width plateaus at ≈ 0.29 whatever the
> arm size, because the frozen side has **three** run-clusters and their per-run
> rates are **6/10, 4/10 and 0/10** — the reference's own between-run variance
> floors the interval. This is a property of the frozen cell, not of this phase,
> and no amount of new collection removes it.
>
> **(b) 15 vs 15 would have been underpowered too** (0.173 > 0.15), which is why
> the powered cell is **30 runs per arm**. At 30 vs 30 the half-width is 0.127,
> inside the margin, so the ext4-versus-drvfs comparison *can* return a verdict
> other than "inconclusive".

**Total per arm: 18 matched + 30 powered = 48 runs, 480 executions.** At the
fitted 40 s/run for AEP-full (`run_matrix.py`'s wall-time model) that is ≈ 32
minutes per arm.

---

## 4. Unit of analysis, and the exact analysis

**Unit of analysis: the run.** Never the execution.

Cluster bootstrap over runs, stratified by crash point so a resample cannot
reweight the cells: `experiments/statistics.py::stratified_cluster_bootstrap_difference`,
**10 000 resamples, seed 20260806** — the frozen cell's own parameters.

The analysis is `scripts/phase10_replication_analysis.py`, committed in the same
commit as this file. The exact invocation:

```
uv run --frozen python scripts/phase10_replication_analysis.py \
  --frozen experiments/results/matrix/analysis/per-execution.csv \
  --arm ext4=<ext4 root>/analysis/per-execution.csv \
  --arm drvfs=<drvfs root>/analysis/per-execution.csv \
  --output reports/raw/phase10-replication-analysis.json
```

Collection, per arm:

```
AEP_HARNESS_SUSPEND_DISABLED=1 uv run --frozen python -m experiments.run_matrix \
  --redis-url redis://127.0.0.1:6381/15 --results-root <ROOT> \
  --regime session-3 --system aep_full --endpoint ledger_postings \
  --keying CALLER_REFERENCE --runs-per-cell 3  --executions-per-run 10
AEP_HARNESS_SUSPEND_DISABLED=1 uv run --frozen python -m experiments.run_matrix \
  --redis-url redis://127.0.0.1:6381/15 --results-root <ROOT>-arbb30 \
  --regime session-3 --system aep_full --endpoint ledger_postings \
  --keying CALLER_REFERENCE --crash-point after_resolution_before_barrier \
  --runs-per-cell 30 --executions-per-run 10
```

**Primary metric:** `known_ambiguity_rate` on `after_resolution_before_barrier`.
**Secondary, reported for every cell:** `undetected_duplicate_rate`,
`lost_effect_rate`, `unverified_failure_rate`, `recovery_success_rate`.

---

## 5. The criterion, stated as a difference and declared in advance

**Stipulated confound margin: ±15 percentage points.**

> **This is a stipulation, not a derivation**, and it is labelled as one — the
> same discipline §VI-C1 applies to its equivalence margin. The reasoning: the
> frozen cell's point estimate is 33.3 pp and its own 95% interval spans 60 pp,
> so a margin tighter than the frozen cell's resolution would be a margin the
> design cannot support. ±15 pp is a little under half the point estimate and is
> the smallest round margin that 30 clusters per arm can address (§3).

Verdict rule, applied by `verdict_for()` in the analysis script:

| interval, relative to ±15 pp | verdict |
|---|---|
| half-width **> 0.15** | **INCONCLUSIVE — UNDERPOWERED** (never "agrees") |
| entirely inside | NOT A CONFOUND at this margin |
| entirely outside on either side | **CONFOUND** |
| straddles a bound | INCONCLUSIVE — INTERVAL STRADDLES THE MARGIN |

The half-width rule is checked **first**, deliberately: Phase 9C's failure was
to read a wide interval as agreement, and an interval that cannot exclude
anything must not be allowed to pass as a pass.

---

## 6. The predictions

**P1 — ext4 arm vs frozen, matched cells.** The five degenerate cells reproduce
exactly: 0/180 undetected duplicates, 0/180 lost effects, 0/180 unverified
failures; `before_intent_write` 0/30 ambiguous; the four saturated cells 30/30.

**P2 — ext4 arm vs frozen, primary metric.** The point difference in
`known_ambiguity_rate` on `after_resolution_before_barrier` is **within ±15 pp**
of the frozen 0.3333. **Its interval is predicted to be INCONCLUSIVE —
UNDERPOWERED**, for the structural reason in §3(a). *This prediction is made in
advance so that an inconclusive result is not later presented as agreement.*
What the comparison **can** do is detect a gross shift: |difference| > ≈ 0.29
would fall outside even this interval, and would be reported as a CONFOUND.

**P3 — drvfs arm vs frozen.** Same as P2.

**P4 — ext4 vs drvfs, primary metric, 30 vs 30.** **Within ±15 pp, and
conclusively so** (predicted half-width ≈ 0.127). This is the one comparison in
this phase with real resolving power. A CONFOUND verdict here is attributable to
the **filesystem**, not to the runtime, because both arms share the runtime.

**P5 — no undetected duplicate and no lost effect appears in either arm.** If
one does, `run_matrix` halts on it (amendment D4) and that is a far more
important finding than anything else in this phase.

---

## 7. Stopping rule

Fixed: **18 matched + 30 powered runs per arm.** No interim look at the rates,
no extension, no early stop. No run is dropped except by the harness's own
existing void criteria (amendment 4 exclusions, `FaultInjectionError`), and
those are **reported as counts** in the phase report whether they are zero or
not.

---

## 8. Conditions present before collection that could bear on the result

Recorded now so that they cannot be introduced afterwards as explanations.

1. **`docker kill` latency differs by a factor of 1.89 between the runtimes**
   (`reports/raw/phase10-kill-latency.json`): median 423 ms through the Docker
   Desktop shim, 223 ms through the native daemon, difference +199.5 ms
   95% CI [192.0, 209.0], interleaved, n=100 each. Against the *real* compose
   container the native engine gives median 317 ms
   (`reports/raw/phase10-kill-latency-compose-native.json`) where the collected
   runs recorded 961.8 ms (`reports/raw/e1-kill-latency-by-run.csv`, n=300).
   **The `session-3` regime performs no `docker kill`** — its fault is a worker
   `SIGKILL` the process sends to itself (`injector.py:81-82`) — so this should
   not reach the replication. It is recorded because it will reach WS-3.

2. **`tests/test_recovery_durability_barrier.py::test_the_barrier_is_validated_once_not_per_resolution`
   is flaky on both runtimes**: 5/20 native (Wilson 95% [0.112, 0.469]), 2/20
   Docker Desktop ([0.028, 0.301]), Fisher exact two-tailed **p = 0.41** — not
   distinguishable at n = 20. It is a `WAITAOF` acknowledgement exceeding a
   2 000 ms timeout across three consecutive recoveries under
   `appendfsync everysec`. AEP-full uses the same barrier, so if the runtime had
   moved barrier latency this is where it would show; at n = 20 per runtime it
   does not show. Raw: `reports/raw/phase10-barrier-flake-{native,desktop}.txt`.

3. **Two gates fail before collection, and neither is caused by this phase.**
   `tests/test_paper_tables.py::test_the_cross_fault_comparison_is_against_the_process_kill_probe`
   asserts a macro deliberately withdrawn on 2026-08-31 (`9545ccb`); the two
   analysis-figure PDFs differ from what is committed on a pristine tree. Both
   are recorded as findings outside scope in the phase report.

4. **`redis_storage_backing` has changed and it is stated, not assumed
   comparable** (the Phase-8.2 requirement). Frozen runs: a named Docker volume
   at `/var/lib/docker/volumes/aep-phase2_redis-data/_data` **inside Docker
   Desktop's VM**, whose filesystem was *not observable from the distro at all*.
   Phase 10 runs: the same logical mount, now at the same path **inside
   `Ubuntu-24.04`**, on `/dev/sdd` **ext4**,
   `rw,relatime,discard,errors=remount-ro,data=ordered`. The mount *type* is
   unchanged (`volume`); what changed is which kernel owns it.

---

## 9. What would make this phase's replication uninformative, said now

If both arms return INCONCLUSIVE — UNDERPOWERED against the frozen cell **and**
the ext4-versus-drvfs comparison also returns inconclusive, then this phase has
established that the runtime is not *grossly* a confound and nothing finer. That
is a weaker result than the phase set out to obtain, and it will be reported in
those words rather than as agreement.
