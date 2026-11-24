# Results manifest -- WS-5 t2-p30

Run counts per cell, keyed the way the paper quotes them. A cell is `(regime, system, crash point, response class, read-back keying)`. The regime is part of the key because pooling regimes is what disqualified the summary table as a source: a crash-free run and a run in which every execution was killed are different experiments, not repetitions of one.

Produced by `scripts/freeze_results.py`, which loads each run through the same `experiments.analyze.load_run` the analysis uses, so these counts and the CSVs cannot disagree.

## Totals

- completed runs: **315**
- executions: **3150**
- of which crashed: **952**
- cells: **21**
- directories with no parsing log (interrupted, not counted): **0**

## By regime

| regime | cells | runs |
|---|---|---|
| `p30` | 21 | 315 |

## Cells

| regime | system | crash point | response class | keying | runs |
|---|---|---|---|---|---|
| `p30` | AEP_FULL | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p30` | AEP_FULL | `mid_dispatch` | NO_READBACK | CALLER_REFERENCE | 15 |
| `p30` | AEP_FULL | `mid_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B0_NAIVE_RETRY | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B0_NAIVE_RETRY | `mid_dispatch` | NO_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B0_NAIVE_RETRY | `mid_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B1_LEASE_ONLY | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B1_LEASE_ONLY | `mid_dispatch` | NO_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B1_LEASE_ONLY | `mid_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B2_CAS_ONLY | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B2_CAS_ONLY | `mid_dispatch` | NO_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B2_CAS_ONLY | `mid_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B3_INTENT_NO_BARRIER | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B3_INTENT_NO_BARRIER | `mid_dispatch` | NO_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B3_INTENT_NO_BARRIER | `mid_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B4B_DURABLE_WORKFLOW_AT_MOST_ONCE | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B4B_DURABLE_WORKFLOW_AT_MOST_ONCE | `mid_dispatch` | NO_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B4B_DURABLE_WORKFLOW_AT_MOST_ONCE | `mid_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B4_DURABLE_WORKFLOW | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B4_DURABLE_WORKFLOW | `mid_dispatch` | NO_READBACK | CALLER_REFERENCE | 15 |
| `p30` | B4_DURABLE_WORKFLOW | `mid_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 15 |
