# Results manifest -- WS-5.1 always arm, 45 runs, phase 21

Run counts per cell, keyed the way the paper quotes them. A cell is `(regime, system, crash point, response class, read-back keying)`. The regime is part of the key because pooling regimes is what disqualified the summary table as a source: a crash-free run and a run in which every execution was killed are different experiments, not repetitions of one.

Produced by `scripts/freeze_results.py`, which loads each run through the same `experiments.analyze.load_run` the analysis uses, so these counts and the CSVs cannot disagree.

## Totals

- completed runs: **45**
- executions: **450**
- of which crashed: **0**
- cells: **3**
- directories with no parsing log (interrupted, not counted): **0**

## By regime

| regime | cells | runs |
|---|---|---|
| `p0` | 3 | 45 |

## Cells

| regime | system | crash point | response class | keying | runs |
|---|---|---|---|---|---|
| `p0` | AEP_FULL | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p0` | B0_NAIVE_RETRY | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p0` | B3_INTENT_NO_BARRIER | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
