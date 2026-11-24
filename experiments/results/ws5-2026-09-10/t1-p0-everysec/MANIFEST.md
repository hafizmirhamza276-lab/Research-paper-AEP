# Results manifest -- WS-5 t1-p0-everysec

Run counts per cell, keyed the way the paper quotes them. A cell is `(regime, system, crash point, response class, read-back keying)`. The regime is part of the key because pooling regimes is what disqualified the summary table as a source: a crash-free run and a run in which every execution was killed are different experiments, not repetitions of one.

Produced by `scripts/freeze_results.py`, which loads each run through the same `experiments.analyze.load_run` the analysis uses, so these counts and the CSVs cannot disagree.

## Totals

- completed runs: **105**
- executions: **1050**
- of which crashed: **0**
- cells: **7**
- directories with no parsing log (interrupted, not counted): **0**

## By regime

| regime | cells | runs |
|---|---|---|
| `p0` | 7 | 105 |

## Cells

| regime | system | crash point | response class | keying | runs |
|---|---|---|---|---|---|
| `p0` | AEP_FULL | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p0` | B0_NAIVE_RETRY | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p0` | B1_LEASE_ONLY | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p0` | B2_CAS_ONLY | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p0` | B3_INTENT_NO_BARRIER | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p0` | B4B_DURABLE_WORKFLOW_AT_MOST_ONCE | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p0` | B4_DURABLE_WORKFLOW | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
