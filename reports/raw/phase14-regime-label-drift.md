# The `(session-3)` regime label in the frozen matrix CSVs — expected, not drift

**2026-09-04. Recorded during WS-1a stage 1 so the next person who runs this
comparison does not spend time on it. Nothing here is a defect and nothing is
being fixed.**

---

## What was observed

Re-running `experiments.analyze` over the frozen 432-run matrix with the WS-1a
attribution change, and diffing the output against the tracked analysis products
in `experiments/results/matrix/analysis/`:

| file | result |
|---|---|
| `redis-kill-ablation.csv` | **byte-identical** |
| `per-cell-metrics.csv` | 702 of 757 rows differ |
| `per-execution.csv` | differs |
| `comparisons-vs-aep-full.csv` | differs |

The difference is confined to **one column**. Tracked rows carry regime
`(session-3)`; freshly generated rows carry `crashed`. Every other field is
equal:

```
< known_ambiguity_rate,crashed,     AEP_FULL,after_barrier_before_dispatch,...,30,30,1.0,3,1.0,1.0,10000,20260806,3,30
> known_ambiguity_rate,(session-3), AEP_FULL,after_barrier_before_dispatch,...,30,30,1.0,3,1.0,1.0,10000,20260806,3,30
```

Verified by removing column 2 and diffing the sorted files: **zero differing
lines.** No value moved.

## What it is

**A known legacy label with a shim that already handles it.**
`scripts/paper_tables.py:120-126` says so at the point of use:

> The frozen Session-3 derivative predates explicit regime names. Normalize its
> legacy label in memory; the frozen source is never rewritten. Fresh analysis
> output already uses `crashed`.

`analyze._regime_of()` derives the label from the run's own config and returns
`crashed` for a crashed cell. The tracked CSVs predate that naming. The
generator normalises `(session-3)` → `CRASHED_REGIME` on read, so both spellings
select the same rows and **no macro is affected by which one is on disk**.

## What it is not

* **Not caused by the WS-1a change.** That diff adds `_has_execution_id`,
  `oracle_effects_by_execution` and `applied_effects_for`, and touches two call
  sites in `run_one`. It does not go near `_regime_of` or any labelling code.
* **Not an unexplained inconsistency between the CSVs and the code.** An earlier
  reading of this — recorded here because it was reported before the shim was
  found — treated it as artifact drift needing explanation. It is explained, in
  a comment at the exact place that consumes it.
* **Not a reason to regenerate.** The frozen source is deliberately not
  rewritten. Regenerating in place would replace the legacy label with `crashed`
  — which the shim also accepts, so the numbers would be unchanged — but it
  would make the committed CSVs differ from the form they were published in, for
  no gain.

## Why this note exists

The comparison in the table above is the natural way to check that an analysis
change moved nothing, and it will be run again — WS-1a's Proof 1 requires
exactly it. Anyone running it sees 702 differing rows before they see the
one-column explanation. This note is so that observation resolves in a minute
rather than an hour, and so nobody "fixes" a label the generator is already
normalising.

## Incidental

The re-run wrote fresh analysis products into
`/root/aep/experiments/results/matrix/analysis/` on the measurement host — a
separate checkout used as a data root, not this repository. The tracked copy
under `experiments/results/matrix/` was not touched, and `git status` confirmed
it. Those host-side products are regenerable from the run directories beside
them.
