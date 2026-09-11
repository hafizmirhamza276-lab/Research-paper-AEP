# Results manifest -- WS-5 t2-keying

Run counts per cell, keyed the way the paper quotes them. A cell is `(regime, system, crash point, response class, read-back keying)`. The regime is part of the key because pooling regimes is what disqualified the summary table as a source: a crash-free run and a run in which every execution was killed are different experiments, not repetitions of one.

Produced by `scripts/freeze_results.py`, which loads each run through the same `experiments.analyze.load_run` the analysis uses, so these counts and the CSVs cannot disagree.

## Totals

- completed runs: **180**
- executions: **1800**
- of which crashed: **1788**
- cells: **12**
- directories with no parsing log (interrupted, not counted): **0**

## By regime

| regime | cells | runs |
|---|---|---|
| `crashed` | 12 | 180 |

## Cells

| regime | system | crash point | response class | keying | runs |
|---|---|---|---|---|---|
| `crashed` | AEP_FULL | `after_barrier_before_dispatch` | AUTHORITATIVE_READBACK | ORACLE_FINGERPRINT | 15 |
| `crashed` | AEP_FULL | `after_barrier_before_dispatch` | POSITIVE_ONLY_READBACK | ORACLE_FINGERPRINT | 15 |
| `crashed` | AEP_FULL | `after_intent_before_barrier` | AUTHORITATIVE_READBACK | ORACLE_FINGERPRINT | 15 |
| `crashed` | AEP_FULL | `after_intent_before_barrier` | POSITIVE_ONLY_READBACK | ORACLE_FINGERPRINT | 15 |
| `crashed` | AEP_FULL | `after_resolution_before_barrier` | AUTHORITATIVE_READBACK | ORACLE_FINGERPRINT | 15 |
| `crashed` | AEP_FULL | `after_resolution_before_barrier` | POSITIVE_ONLY_READBACK | ORACLE_FINGERPRINT | 15 |
| `crashed` | AEP_FULL | `after_response_before_resolution` | AUTHORITATIVE_READBACK | ORACLE_FINGERPRINT | 15 |
| `crashed` | AEP_FULL | `after_response_before_resolution` | POSITIVE_ONLY_READBACK | ORACLE_FINGERPRINT | 15 |
| `crashed` | AEP_FULL | `before_intent_write` | AUTHORITATIVE_READBACK | ORACLE_FINGERPRINT | 15 |
| `crashed` | AEP_FULL | `before_intent_write` | POSITIVE_ONLY_READBACK | ORACLE_FINGERPRINT | 15 |
| `crashed` | AEP_FULL | `mid_dispatch` | AUTHORITATIVE_READBACK | ORACLE_FINGERPRINT | 15 |
| `crashed` | AEP_FULL | `mid_dispatch` | POSITIVE_ONLY_READBACK | ORACLE_FINGERPRINT | 15 |
