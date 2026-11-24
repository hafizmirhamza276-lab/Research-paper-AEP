# Results manifest -- WS-5 t1-incomplete

Run counts per cell, keyed the way the paper quotes them. A cell is `(regime, system, crash point, response class, read-back keying)`. The regime is part of the key because pooling regimes is what disqualified the summary table as a source: a crash-free run and a run in which every execution was killed are different experiments, not repetitions of one.

Produced by `scripts/freeze_results.py`, which loads each run through the same `experiments.analyze.load_run` the analysis uses, so these counts and the CSVs cannot disagree.

## Totals

- completed runs: **12**
- executions: **120**
- of which crashed: **69**
- cells: **4**
- directories with no parsing log (interrupted, not counted): **0**

## By regime

| regime | cells | runs |
|---|---|---|
| `crashed` | 2 | 6 |
| `p0` | 1 | 3 |
| `p30` | 1 | 3 |

## Cells

| regime | system | crash point | response class | keying | runs |
|---|---|---|---|---|---|
| `crashed` | B4_DURABLE_WORKFLOW | `after_barrier_before_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `crashed` | B4_DURABLE_WORKFLOW | `after_barrier_before_dispatch` | AUTHORITATIVE_READBACK | ORACLE_FINGERPRINT | 3 |
| `p0` | B4_DURABLE_WORKFLOW | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `p30` | B4_DURABLE_WORKFLOW | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
