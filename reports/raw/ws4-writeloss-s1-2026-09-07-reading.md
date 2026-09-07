# WS-4 write-loss cell, session 1: the reading

`scripts/analyse_write_loss.py` run unmodified against the session collected in
`252e2d3`. Raw output: `ws4-writeloss-s1-2026-09-07-verdict.txt`.

## The estimand

| arm | executions | applied | rate | lost effects | undetected duplicates | declared ambiguous |
|---|---|---|---|---|---|---|
| `AEP_FULL` | 300 | 285 | **0.9500** | 0 | 0 | 49 |
| `B3_INTENT_NO_BARRIER` | 300 | 287 | **0.9567** | 0 | 0 | 61 |

## Verdict and behaviour, both

> **numbers: REFUTED** — AEP-full applied 285/300 = 0.9500, above the refutation
> threshold 0.2. B3 applied 287/300 = 0.9567: at ceiling.
>
> **READING: REFUTED, and the third Redis behaviour was observed:** WAITAOF
> acknowledged after the device stopped accepting writes. *Whatever the numbers
> say, they were not produced by the mechanism the prediction describes.*

Behaviour: **`SILENT_APPEND_FAILURE`**, on 30/30 AEP-full runs —
`durability_acks_after_the_fault: 300`, `post_fault_failures: 0`.

**The verdict and the behaviour say different things and both are needed.** The
numbers alone would read as "the barrier does not withhold under write loss".
That is not what happened. The barrier withholds on a *failed or absent*
durability acknowledgement, and it never got one: Redis returned `WAITAOF`
success 300 times out of 300 after the device had stopped accepting writes. The
protocol behaved correctly given the answer it was given; the answer was false.

This is exactly the third of the three behaviours `d8b2ca5` enumerated in
advance, and the one it flagged as *"would complicate the reading"*. The
pre-registration anticipated the result it got, which is the only reason this can
be reported as a finding rather than a surprise.

**Two pre-registered exact quantities held**, and are worth stating because they
are not weakened by the above: `lost_effect_executions = 0` for AEP-full, and
`undetected_duplicate_applications = 0` for **both** arms.

**What this does not support.** It is not evidence that the barrier fails to
withhold under write loss — that condition was never reached, because the store
never reported a durability failure. Nor is it evidence the barrier works. It is
evidence about **Redis**: with `appendfsync everysec`, `WAITAOF` acknowledged
durability that block-level write loss had already made impossible. Any claim
drawn from this cell has to be about the acknowledgement, not about the protocol.

## Finding: the per-run column is zero by construction, and was not fixed

`analyse_write_loss.py:200` `per_run_applied()` reads
`record.get("applied_effects_total", 0)` from **`matrix-progress.jsonl`**. That
key does not exist in a progress row. Its `summary` field is a **path string**,
not a nested object, and the real per-run counts sit in each run's
`summary.json`. The column named `applied_effects_total` does exist — in
`analysis/redis-kill-ablation.csv`, which is a different file.

So every run prints `0`, and the printed line

```
AEP_FULL   n= 30 [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] ...
```

is a default, not a measurement. It contradicts the 285/300 directly above it.

**Scope: display only. The verdict is unaffected.** `classify_numbers()` takes
`ArmCounts` read from the ablation CSV; `classify_reading()` takes the verdict and
the behaviour; the behaviour classifier reads worker event logs. `statistics` is
used only on post-arm wait times. Nothing in the verdict path touches
`per_run_applied`. Re-reading the estimand straight from the ablation CSV
reproduces 285/300 and 287/300.

**It was not fixed, deliberately.** The script's whole value is that it was
written before any data existed; editing it after seeing the result is the one
thing that ordering exists to prevent, even for a defect this clearly cosmetic.
The fix is a separate prompt.

**It is not purely cosmetic in one respect**, and that is the part worth
flagging: the module docstring says *"Unit of analysis: the run — per-run counts
are reported and the run is what the spread is taken over."* No spread is taken
over anything, and a column that is constant-zero regardless of input cannot show
one. By `docs/26` §3 rule 13 — a gate that cannot fail is decoration — this is
decoration. It should be either made real or removed.

## Provenance note

`scripts/analyse_write_loss.py` reads `analysis/redis-kill-ablation.csv`, which
the collection does not produce; `python -m experiments.analyze` does. That step
had not been run at `252e2d3`, so the committed root could not drive the verdict.
`experiments.analyze` also needs per-run files that were not in the committed
subset, so it was run against the complete host root and its `analysis/` output
committed alongside the data. The committed root now reproduces the verdict.

The analysis output labels the regime `redis-kill-preack` rather than
`write-loss-preack`. That is the **known regime-label drift**, already recorded
and deliberately not fixed.
