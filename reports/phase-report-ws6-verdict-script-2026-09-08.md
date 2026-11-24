# WS-6's verdict script, written before any B5 data exists

**No data collected.** `scripts/analyse_b5_agreement.py` and its test are
committed with their thresholds, their AGREES/DISAGREES rule and their handling
of the flagged conditions **fixed in advance**, which is what
`1fecb1f` §5.1 registered and the only thing that will make a favourable
agreement result worth reporting. WS-4's REFUTED verdict was credible for exactly
this reason.

---

## Where the frozen rates are read from

`experiments/results/matrix/analysis/per-cell-metrics.csv` — the long-form file
keyed by `(metric, regime, system, crash_point, response_class, readback_keying)`
which **already carries** `rate`, `ci_low`, `ci_high`, `runs` and `clusters`.
The run-clustered intervals this comparison needs were computed there by the same
estimator, so nothing is recomputed and **no frozen rate is restated in the
script**. It has 228 B4/B4b rows across all six roadmap crash points and all
three response classes.

Metrics used: `undetected_duplicate_rate` (H1), `lost_effect_rate` (H2),
`known_ambiguity_rate` (H3). B5's own side uses
`experiments.statistics.cluster_bootstrap_proportion` — the same estimator, the
run as the cluster (`docs/26` rule 6). `analysis/table-1.csv` is a banned source
(Session 3B §F2) and the reader refuses it by name.

## Agreement **and** the reasons

`classify_cell` returns one of six readings, not two, and the order it evaluates
them in is the substance:

1. **`NOT_TESTABLE_ABSENT_IN_B5`** — decided *before any arithmetic*. B5 has no
   `after_intent_before_barrier` position; B4 and B4b have frozen cells there on
   all three response classes, so it is a hole in B5 where B4 has numbers, and
   the reason says so in those words. **No rate is computed for an absent
   point**, and the summary prints the count explicitly with *"ABSENT IN B5, not
   missing from the collection… the comparison is not complete"* — so the table
   cannot look complete by omission.
2. **Voids excluded and counted**, before any rate exists.
3. **`UNINFORMATIVE_PENDING`** — above the pre-registered 20%, evaluated *before*
   interval overlap, so a cell can never be reported as AGREES on a basis the
   pre-registration already said would not support one. The reason names the
   remedy the pre-registration allows: a timeout change, re-registered, **not** a
   re-reading of the runs in hand.
4. Only then the overlap test, and `DISAGREES` carries the consequence — B4 would
   be an artefact of our model rather than of event-sourced re-execution, and
   every B4 claim would need re-scoping.

A cell that agrees while carrying pending runs *within* the bound says so
(`"…within the 20% bound"`), which is this script's version of WS-4's *"held, but
for a reason the pre-registration flagged as complicating."*

**H3** is separate and absolute: predicted at exactly zero because it is
structural, so one declared ambiguity refutes it. There is no tolerance band —
inventing one after seeing data would be fitting the threshold to the result.
Voided runs cannot refute H3.

## Voids are instrument failures, not measurements

`VOID_INJECTOR_NEVER_REACHED`, `VOID_INJECTOR_DID_NOT_FIRE`,
`VOID_SUPERVISOR_NEVER_RESPAWNED` and `VOID_WORKER_NEVER_READY` are removed from
every rate and reported separately with per-verdict counts, at both cell and
session level.

This is the same failure `gate.py` exists to stop, one layer up: a void counted
as "no duplicate" would make B5 look better than B4 for an instrument reason. A
cell that is *entirely* voids reads `NO_DATA_AFTER_VOIDS` and computes no rate at
all, rather than agreeing with a zero-duplicate frozen cell by vacuity.

## Proved non-vacuously — 12 tests, all passing

`tests/test_b5_agreement.py`. The three required fixtures produce three
**different** readings, and that difference is asserted directly
(`len({agree, disagree, voided}) == 3`) rather than left implicit:

| fixture | reading |
|---|---|
| B5 interval overlapping frozen | `AGREES` |
| B5 rate far from frozen | `DISAGREES`, with the re-scoping consequence |
| 8 voided runs | `NO_DATA_AFTER_VOIDS` |

The load-bearing test is the mixed one: 9 voids + 1 real run must give a rate
over **the one surviving run, not over ten** (`b5.point == 1/10`), with the voids
itemised `{NEVER_REACHED: 4, NEVER_RESPAWNED: 3, WORKER_NEVER_READY: 2}`. Plus:
the absent point reads absent even when runs are present for it; pending above
the bound reads `UNINFORMATIVE_PENDING` on a cell that would otherwise agree; H3
is refuted by one ambiguity and not refuted by a voided one; and the frozen
comparator is asserted to actually contain a B4 cell, so the reader cannot pass
by finding nothing.

Promoted to `scripts/` with a test, per `docs/26` rule 14.

---

## The three recorded items, each decided

**1. `worker.err` — truncated per run.** It was appended across runs and never
truncated, so a stale `ConnectError` from a previous round was readable during a
later one and was only not attributed to it because provider liveness was checked
directly. A log that cannot say which run a line belongs to cannot report *"I
could not tell"* — `docs/25` R14. Now zeroed at the start of every run.

**2. The `deaths` counter — fixed, not removed.** It counted polls, not deaths:
`maintain()` incremented on every poll while the worker stayed dead, so the
respawn-disabled branch printed `deaths=232` for one worker dying once. No
verdict depended on it — the gate tests `deaths > 0` — but **a number that counts
nothing does not belong in a report**, and it would have been quoted eventually.
Now counted once per lifetime, reset when a new lifetime starts. Removing it was
the alternative and was rejected: the gate's distinction between *died and no
respawn* and *never died* needs the count to exist.

**3. Cold-start `VOID_WORKER_NEVER_READY` — retried once, not spent.** I raised
this as avoidable power loss and it is. A worker that never came up measured
nothing, so voiding the run costs a run for a reason having nothing to do with
the engine. **One retry only**: a second failure still voids, because an
unbounded retry would hide a genuinely broken worker behind a loop. That bound is
the whole decision — the alternatives were spending the run (loses power) or
retrying freely (hides defects).

---

## Status

| | |
|---|---|
| `scripts/analyse_b5_agreement.py` | **written, before any B5 data exists** |
| `tests/test_b5_agreement.py` | **12 tests, all passing**, three fixtures giving three readings |
| Frozen comparator | read from `per-cell-metrics.csv`, banned source refused by name |
| Absent cell | reported as ABSENT, never omitted |
| Uninformative cell | never reported as agreement |
| Voids | excluded from rates, counted separately |
| The three recorded items | all three decided and applied |

**WS-6 is ready to collect.** Every open question from `1fecb1f` is closed, the
instrument's gates are proven able to fail in both directions, and the verdict
script now predates the data it will judge. What remains before a run is the
Start-To-Close choice — a collection-design decision the measurements support but
which is not itself an open question about the engine.
