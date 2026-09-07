# WS-4's two recorded findings, closed

Both were recorded at `1d13868` and deliberately left unfixed there, because
editing a verdict script after seeing its data is what the pre-registration
ordering exists to prevent. They are fixed here, in a pass that reads no new
data and moves no result.

---

# 1. `analyse_write_loss.py:200` — the per-run column

## What was wrong

`per_run_applied()` read `applied_effects_total` from `matrix-progress.jsonl`.
That key is not in a progress row: `summary` there is a **path string**, and the
column of that name lives in `analysis/redis-kill-ablation.csv`. `dict.get(…, 0)`
turned every miss into a zero, so the display printed thirty zeros immediately
beneath a total of 285.

## Fixed, not removed — and why

Removing the display was the cheaper option and would have been wrong. The
per-run counts **exist**, in each run's `summary.json`, and they are what makes
the unit-of-analysis claim (rule 6) true rather than decorative. Deleting the
column would have resolved the contradiction by discarding the evidence for the
claim the script makes about itself.

The field is `oracle_effect_executions`. It was **identified rather than
assumed**: summed over each arm it reproduces the ablation CSV's
`executions_with_an_applied_effect` exactly — 285 and 287.

Two further changes came with it:

* **No silent zero.** A run whose count cannot be read now raises rather than
  defaulting. Reporting "this run applied nothing" and "I could not read this
  run" as the same number is the entire defect, and a repair that left the
  default in place would have left the mechanism in place.
* **Reconciliation.** The per-run sum is compared against the arm total read
  from the ablation CSV — a different file — and the result printed. Two
  independent sources for one quantity that are never compared is precisely how
  thirty zeros sat under a total of 285 without anyone noticing.

## The docstring claim about spread

> *"Per-run counts are reported and the run is what the spread is taken over."*

No spread was taken over anything. **Computed rather than deleted**, for the same
reason as above: the data was there. The display now reports min, median, max,
spread and standard deviation per arm.

| arm | per-run | min | median | max | spread | sd | reconciles |
|---|---|---|---|---|---|---|---|
| `AEP_FULL` | n=30 | 7 | 10 | 10 | 3 | 0.682 | 285 = 285 ✓ |
| `B3_INTENT_NO_BARRIER` | n=30 | 8 | 10 | 10 | 2 | 0.679 | 287 = 287 ✓ |

## The result did not move

The verdict path never touched `per_run_applied`: `classify_numbers()` reads the
ablation CSV, `classify_reading()` takes the verdict and the behaviour. Verified
rather than asserted — the script was re-run against the same session root and
diffed against the verdict committed at `1d13868`. **The only lines that differ
are the per-run lines themselves.** The estimand, the behaviour block, the
verdict and the READING are byte-identical:

```
numbers : REFUTED
  - AEP-full applied 285/300 = 0.9500, above the refutation threshold 0.2
  - B3 applied 287/300 = 0.9567: at ceiling
READING : REFUTED, and the third Redis behaviour was observed …
SILENT_APPEND_FAILURE  acks_after_the_fault: 300  post_fault_failures: 0
```

---

# 2. The `redis-kill-preack` label drift

## Where the label comes from

`experiments/analyze.py:601`, `_regime_of(crash_probability, redis_kill_point)`.
It is **derived at analysis time**, not baked into the collected data — the
collected `matrix-progress.jsonl` rows carry `regime = "write-loss-preack"`
correctly for all 60 runs. So this is an analysis-time path and is fixable
without touching any frozen byte.

The cause is structural rather than careless. WS-4's write-loss cell shares
`redis_kill_point = "after_intent_before_barrier"` with the hard-kill cell —
deliberately, the fault is delivered at the same instruction boundary — and
differs only in *mechanism*. The mechanism is chosen by the **environment**
rather than by `RunConfig`, precisely so that no collected run's `config_digest`
changes. The consequence is that the kill point alone cannot distinguish them,
and 60 write-loss runs were labelled with a fault class naming a fault that never
occurred.

## Fixed

The mechanism *is* in the collected data: the run's own `redis_kill_issued` event
carries `"mechanism": "write-loss"`. `_regime_of` now takes it as a third
argument, read from the run's events — the same "derive from what the run did,
do not trust a field the matrix wrote" discipline the surrounding function
already follows.

**Frozen results cannot move, by construction rather than by promise.** Runs
collected before the write-loss injector existed have no `mechanism` key; the
argument is `None` for them and they take exactly the branch they took before.
Confirmed empirically: `check_paper_numbers.py` reports all five generated tables
byte-identical after the change.

```
PASS  table-ablation.tex matches the CSVs
PASS  table-ambiguity-by-crashpoint.tex matches the CSVs
PASS  table-deployment-choice.tex matches the CSVs
PASS  table-latency.tex matches the CSVs
PASS  table-outcomes.tex matches the CSVs
```

The WS-4 ablation CSV now reads:

```
write-loss-preack,AEP_FULL,NO_READBACK,30,300,285,285,49,0,0,0,0,0
write-loss-preack,B3_INTENT_NO_BARRIER,NO_READBACK,30,300,287,287,61,0,0,0,0,0
```

## The verdict after both fixes

Re-run on the re-analysed root: **byte-identical** to the run before the relabel,
including the per-run lines. The relabel changed nothing in the verdict output at
all.

Re-run from the **committed** root (`reports/raw/ws4-writeloss-s1-2026-09-07/`)
rather than the host one: identical but for the session-name line, which is the
directory name. The committed data reproduces the verdict.

---

# 3. The pattern: three times, a rule broken inside the fix for that rule

Recorded because it is now a pattern rather than an incident, and because each
instance was caught by something other than care.

1. **The anonymity scan.** `C=$(grep -c … || echo 0)` made every clean needle
   render as a hit — a leak scanner that could not tell zero from one. The fix
   for it, a DocInfo regex, then used `(.+?)` with `re.S` and reported every
   empty key as populated. **A defect of the "cannot distinguish absence" class,
   inside the repair for a defect of the same class.**
2. **The rule-13 proof.** `prove_anonymous_gate.sh` asserted by re-running the
   checker rather than on the output it had just printed — asserting about a run
   it had not shown. **The R13 shape, inside the proof written to justify R13.**
3. **This pass.** `per_run_applied()` was repaired for defaulting a missing key
   to zero; the docstring above it asserted a spread the code did not compute.
   The verification script written to check that nothing moved compared two
   greps with **different patterns** and reported a difference that did not
   exist — a comparison that could produce a false alarm, inside the check that
   the fix produced no false result.

**What the three have in common** is not carelessness in the fix; it is that in
each case the *checking* code was held to a lower standard than the code it
checked. The instrument gets written quickly because it is "just" a check, and
then it is the thing everything else is believed on.

The practical consequence, and the reason this is worth a section rather than a
footnote: **the verification of a fix needs the same failing-branch proof the
fix's own gate does** (R3, R13, and now this). In all three cases the defect
surfaced only because a result looked wrong against something already known by
hand — a PDF verified clean ten minutes earlier, a diff of two greps against a
file that had just been read. None was caught by the instrument itself.
