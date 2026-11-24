# Stage 3 amendment — 2026-08-17 — replication collected; E5 declaration contradicted

Records the collection of the Stage 3 replication dataset, the failure of the
amendment E5 suspend declaration during it, and the decision not to recollect
the affected runs.

## 1. What was collected

| | |
|---|---|
| Dataset version | `stage3-2026-08-13-replication-1` |
| Cell selection | `reports/stage3-replication-plan-2026-08-13.json`, SHA-256 `ce36b784…5c92e7a0` |
| Bound Git SHA | `dc954af1a07d43470ddfdaf63206b96f18bfcd1e` |
| Locked matrix plan | SHA-256 `4750f3828bbe4e618fe999381252c90d01489946cb38a322f7720da4aef282e6` |
| Matrix seed | `20260806` (historical, deliberately) |
| Shape | **126 cells / 432 runs / 3,780 executions** |
| Collected | 432 of 432. 0 failed, 0 voided. |
| Reconciliation | all 432 runs agreed with the independent ground-truth ledger |
| Coordinator | `redis:7.2.5-alpine@sha256:6aaf3f5e…7b1f44`, `appendfsync=everysec`, on all 432 runs |
| Measured run time | 10.93 h |
| Raw runs | **not committed** — 262 MB at `/var/tmp/aep-stage3-2026-08-13/replication` |

Every one of the 432 run configs records the same `git_sha`,
`experiment_plan_sha256`, `dataset_version`, `redis_durability` and
`redis_version`. No planned run is absent, no unplanned run is present, and no
collected seed differs from the seed the plan declared.

### 1.1 The shape matches the historical matrix exactly

The plan names `experiments/results/matrix/MANIFEST.csv` (SHA-256
`f3f3d2e0…16877e`) as its collection source. Comparing that manifest with the
replication's own, cell by cell:

- historical: 126 cells, 432 runs
- replication: 126 cells, 432 runs
- symmetric difference after normalising one label: **0**
- cells with differing run counts: **0**

The one label needing normalisation is the crash regime, which the historical
manifest calls `(session-3)` and the current code calls `crashed`. It is a
rename in the labelling, not a difference in what was collected: the 9 cells
outside that regime (7 `p0`, 2 `redis-kill-preack`) match without any
normalisation at all. This is a stronger statement than "432 runs completed" —
it says the replication collected the same experiment.

## 2. Amendment E5: the declaration was contradicted

The operator declared before collection resumed that the host could not
suspend: High Performance scheme, standby, monitor and hibernate timeouts all
0 on AC, machine on AC throughout. That declaration was set as
`AEP_HARNESS_SUSPEND_DISABLED=1` and is recorded in all 432 run configs as
`suspend_disabled_declared=true`.

**The host suspended anyway.** The collection spanned 94 hours of wall clock
for 10.93 hours of work, and the Windows event log records repeated
`Microsoft-Windows-Kernel-Power` 506/507 pairs — connected standby enter and
exit — on 15, 16 and 17 August, during the collection.

`experiments/analyze.py` detected it independently, without reference to the
event log, by comparing each run's wall-clock span against its monotonic span:

```
runs_with_usable_timing            423
runs_dropped_for_clock_suspension    9
runs_dropped_for_undeclared_suspend_policy  0
worst_suspension_seconds     49646.414   (13.79 h)
```

Nine runs, four cells, all `B4_DURABLE_WORKFLOW`. All three repetitions of
`b4_durable_workflow-after_intent_before_barrier-ledger_postings-7cb1f1f7`
were suspended, so that cell contributes no usable timing at all. The full
list, with seeds and durations, is in
`experiments/results/stage3-replication-2026-08-13/operator-declaration-e5-correction.json`.

### 2.1 The declaration was not dishonest, and that is the point

`powercfg` independently confirmed `STANDBYIDLE`, `HIBERNATEIDLE` and
`VIDEOIDLE` are all 0 on AC under the High Performance scheme, and that the
machine was on AC. Those settings govern *idle* transitions only. This host
reports S0 Low Power Idle (Modern Standby), on which connected standby can be
entered by lid close, by user action, or by policy that none of those timeouts
govern. **On a Modern Standby host the three settings named in the declaration
are necessary but not sufficient**, and no combination of them makes the
declaration safe to assert.

This is exactly why E5 has two gates rather than one. The declaration alone
would have admitted all 432 runs to the timing aggregates. The detector alone
cannot distinguish a host that cannot suspend from one that merely did not.
Requiring both is what caught this.

A future collection needing complete timings should disable Modern Standby
(`HKLM\SYSTEM\CurrentControlSet\Control\Power\PlatformAoAcOverride = 0`,
reboot), verify an empty 506/507 window, and collect from scratch — not patch
this dataset.

## 3. The nine runs are not being recollected

Their **counts are valid**. An execution either duplicated or it did not, and
that observation does not depend on the clock. All 432 runs remain in every
rate metric; only durations are withheld.

Re-running them would discard nine observed results and draw again, on the
basis of a property uncorrelated with the outcome. That is re-sampling.
Amendment D4 forbids re-running or filtering to move a number, and the
principle does not stop applying because the number in question is a timing.
`analyze.py` already handles the case in the open — counts kept, timings
excluded, a warning printed on every invocation — which is a better scientific
record than a dataset quietly reconstructed to look unblemished.

The cost is stated rather than hidden: **`B4_DURABLE_WORKFLOW`'s timing sample
is 48 of 57 runs where every other system's is complete.** Any overhead or
latency comparison involving B4 has an asymmetric denominator and must say so.

## 4. Results

Quote `analysis/per-cell-metrics.csv`. `analysis/table-1.csv` pools three fault
regimes and `analyze.py` prints a warning saying it is a coverage summary and
not a result; that warning is correct.

Undetected duplicate applications, by regime:

| system | crashed | p0 (no faults) | redis-kill-preack |
|---|---|---|---|
| **AEP_FULL** | **0 / 540** | **0 / 30** | **0 / 30** |
| B0_NAIVE_RETRY | 354 / 450 | 3 / 30 | — |
| B1_LEASE_ONLY | 366 / 450 | 5 / 30 | — |
| B2_CAS_ONLY | 358 / 450 | 5 / 30 | — |
| B3_INTENT_NO_BARRIER | **0 / 540** | 0 / 30 | 0 / 30 |
| B4_DURABLE_WORKFLOW | 296 / 540 | 3 / 30 | — |
| B4B_…_AT_MOST_ONCE | 0 / 540 | 0 / 30 | — |

AEP-full records zero undetected duplicates in every regime, at a known
ambiguity rate of 0.357: it converts silent duplication into declared
ambiguity. B4B shows the opposite trade — zero duplicates, 282/540 lost
effects.

### 4.1 B3 is separated from AEP-full only by the E1 ablation

`B3_INTENT_NO_BARRIER` records zero undetected duplicates under worker
crashes, statistically indistinguishable from AEP-full (Fisher p = 1.00). The
barrier is not what separates them there. It separates them under durability
acknowledgement loss:

```
regime              system                 runs  applied  ambiguous
redis-kill-preack   AEP_FULL                 30        0         30
redis-kill-preack   B3_INTENT_NO_BARRIER     30       28         30
```

`applied` is the discriminator: B3 dispatched an effect in 28 of 30 runs in
which the durability acknowledgement never arrived. AEP-full dispatched none.
Any claim that the barrier prevents duplication under crashes is not supported
by this dataset; the claim it does support is narrower and about durability.

### 4.2 One result to confront before it is written up

The baselines produce undetected duplicates in the **`p0` regime, where no
fault is injected at all** — B0 3/30, B1 5/30, B2 5/30, B4 3/30. Duplication
without any injected fault is either a strong result or a harness artifact,
and three runs per cell is too thin to tell. A handful of those executions
should be read by hand before either reading is asserted.

## 5. What is committed, and what is not

Committed under `experiments/results/stage3-replication-2026-08-13/`:
`MANIFEST.md`, `MANIFEST.csv`, `SHA256SUMS`, the locked `matrix-plan.json`,
`matrix-progress.jsonl`, both operator declaration files, and all 20 analysis
outputs (3.3 MB).

Every file `SHA256SUMS` digests is committed, so the digest list can be
verified by a reader who has only this repository. That is deliberately more
than `experiments/results/matrix` tracks, where SHA256SUMS covers files the
repository does not contain and therefore cannot be checked from it.
`matrix-progress.jsonl` is the one committed file not covered by SHA256SUMS,
which digests the manifest and the analysis outputs only; it is included
because it is the only record of the coordinator snapshot taken either side of
each of the 432 runs.

**Not committed:** the 262 MB of raw run directories, at
`/var/tmp/aep-stage3-2026-08-13/replication`. Also on disk, and also not
committed, are two abandoned attempts retained as evidence:
`replication--superseded-20260813T1020Z-no-e5-declaration` (22 runs collected
before the E5 declaration existed) and
`replication--failed-20260813T1052Z-orphaned-provider` (0 runs collected; 432
attempts refused because a mock-api process orphaned by the previous stop
still held port 8099, which the harness correctly declined to collect
against).
