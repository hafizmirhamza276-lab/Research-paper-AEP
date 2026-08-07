# Results manifest -- Phase 4 Session 1

Run counts per cell, keyed the way the paper quotes them. A cell is `(regime, system, crash point, response class, read-back keying)`. The regime is part of the key because pooling regimes is what disqualified the summary table as a source: a crash-free run and a run in which every execution was killed are different experiments, not repetitions of one.

Produced by `scripts/freeze_results.py`, which loads each run through the same `experiments.analyze.load_run` the analysis uses, so these counts and the CSVs cannot disagree.

## Totals

- completed runs: **326**
- executions: **2720**
- of which crashed: **2450**
- cells: **91**
- directories with no parsing log (interrupted, not counted): **2**

## By regime

| regime | cells | runs |
|---|---|---|
| `(session-3)` | 82 | 245 |
| `p0` | 7 | 21 |
| `redis-kill-preack` | 2 | 60 |

## Cells

| regime | system | crash point | response class | keying | runs |
|---|---|---|---|---|---|
| `(session-3)` | AEP_FULL | `after_barrier_before_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `after_barrier_before_dispatch` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `after_barrier_before_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `after_intent_before_barrier` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `after_intent_before_barrier` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `after_intent_before_barrier` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `after_resolution_before_barrier` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `after_resolution_before_barrier` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `after_resolution_before_barrier` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `after_response_before_resolution` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `after_response_before_resolution` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `after_response_before_resolution` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `before_intent_write` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `before_intent_write` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `before_intent_write` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `mid_dispatch` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | AEP_FULL | `mid_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `after_barrier_before_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `after_barrier_before_dispatch` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `after_barrier_before_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `after_resolution_before_barrier` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `after_resolution_before_barrier` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `after_resolution_before_barrier` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `after_response_before_resolution` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `after_response_before_resolution` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `after_response_before_resolution` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `before_intent_write` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `before_intent_write` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `before_intent_write` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `mid_dispatch` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B0_NAIVE_RETRY | `mid_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `after_barrier_before_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `after_barrier_before_dispatch` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `after_barrier_before_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `after_resolution_before_barrier` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `after_resolution_before_barrier` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `after_resolution_before_barrier` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `after_response_before_resolution` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `after_response_before_resolution` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `after_response_before_resolution` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `before_intent_write` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `before_intent_write` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `before_intent_write` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `mid_dispatch` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B1_LEASE_ONLY | `mid_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `after_barrier_before_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `after_barrier_before_dispatch` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `after_barrier_before_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `after_resolution_before_barrier` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `after_resolution_before_barrier` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `after_resolution_before_barrier` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `after_response_before_resolution` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `after_response_before_resolution` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `after_response_before_resolution` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `before_intent_write` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `before_intent_write` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `before_intent_write` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `mid_dispatch` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B2_CAS_ONLY | `mid_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `after_barrier_before_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `after_barrier_before_dispatch` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `after_barrier_before_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `after_intent_before_barrier` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `after_intent_before_barrier` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `after_intent_before_barrier` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `after_resolution_before_barrier` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `after_resolution_before_barrier` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `after_resolution_before_barrier` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `after_response_before_resolution` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `after_response_before_resolution` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `after_response_before_resolution` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `before_intent_write` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `before_intent_write` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `before_intent_write` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `mid_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `mid_dispatch` | NO_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B3_INTENT_NO_BARRIER | `mid_dispatch` | POSITIVE_ONLY_READBACK | CALLER_REFERENCE | 3 |
| `(session-3)` | B4_DURABLE_WORKFLOW | `after_barrier_before_dispatch` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 2 |
| `p0` | AEP_FULL | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `p0` | B0_NAIVE_RETRY | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `p0` | B1_LEASE_ONLY | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `p0` | B2_CAS_ONLY | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `p0` | B3_INTENT_NO_BARRIER | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `p0` | B4B_DURABLE_WORKFLOW_AT_MOST_ONCE | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `p0` | B4_DURABLE_WORKFLOW | `none` | AUTHORITATIVE_READBACK | CALLER_REFERENCE | 3 |
| `redis-kill-preack` | AEP_FULL | `none` | NO_READBACK | CALLER_REFERENCE | 30 |
| `redis-kill-preack` | B3_INTENT_NO_BARRIER | `none` | NO_READBACK | CALLER_REFERENCE | 30 |

## Directories without a parsing run log

Interrupted attempts. They contribute nothing to any number in the paper, and are listed so the difference between the directory count and the run count is accounted for rather than noticed.

- `analysis-interim`
- `b4_durable_workflow-after_barrier_before_dispatch-payments-11d6b7e1-r2`
