# Results manifest

Run counts per cell, keyed the way the paper quotes them. A cell is `(regime, system, crash point, response class, read-back keying)`. The regime is part of the key because pooling regimes is what disqualified the summary table as a source: a crash-free run and a run in which every execution was killed are different experiments, not repetitions of one.

Produced by `scripts/freeze_results.py`, which loads each run through the same `experiments.analyze.load_run` the analysis uses, so these counts and the CSVs cannot disagree.

## Totals

- completed runs: **120**
- executions: **120**
- of which crashed: **0**
- cells: **4**
- directories with no parsing log (interrupted, not counted): **0**

## By regime

| regime | cells | runs |
|---|---|---|
| `redis-kill-preack` | 4 | 120 |

## Cells

| regime | system | crash point | response class | keying | runs |
|---|---|---|---|---|---|
| `redis-kill-preack` | AEP_FULL | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 30 |
| `redis-kill-preack` | AEP_FULL | `none` | NO_READBACK | CALLER_REFERENCE | 30 |
| `redis-kill-preack` | B3_INTENT_NO_BARRIER | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 30 |
| `redis-kill-preack` | B3_INTENT_NO_BARRIER | `none` | NO_READBACK | CALLER_REFERENCE | 30 |
