# Phase 13 Arm A — known text defects in the raw session results files

Two things in `reports/raw/phase13-armA-s{1,2,3}-results.txt` read wrong to
someone who has not seen this note. Neither affects the estimand, the spread
criterion, or any verdict. Both are recorded here rather than quietly repaired,
and the phase report should carry them.

The pre-registration (`reports/phase-report-13-prediction-armA-2026-09-03.md`)
is deliberately **not** amended. Its evidential value is that it has not been
touched since before Arm A's data existed.

---

## 1. The interleaving section header says "first 12 runs" and prints 40

```
########## interleaving actually realised (first 12 runs, by start time) ##########
  A A A B B B A A A B B B A A A B B B A A A B B B A A A B B B A A A B B B A A A B
  adjacent same-arm pairs: 120 of 179
```

The header is wrong: the line carries **40** arm letters, not 12. The count on
the following line (`120 of 179`) is over the **whole** session, not over the
printed prefix, and is correct.

**Present in all three session files**, because sessions 1 and 2 were assembled
by hand with this header and session 3 reproduced it deliberately.

**Left verbatim on purpose.** The three files are only comparable if their
diagnostics are rendered identically; correcting the header in s3 alone would
make it differ from its predecessors for a reason with nothing to do with the
data. `scripts/render_session_results.py` carries the constant
`INTERLEAVING_LETTERS = 40` with the mislabel noted at the definition, and
`tests/test_session_results_rendering.py` pins all three files byte-for-byte —
so a fix means regenerating and re-committing all three together, as one change,
with the test updated in the same commit. That is the correct way to do it and
it was not done here.

## 2. Session 3's per-run cost `min 7.9 s` is an aborted run, not a mechanism cost

```
########## final per-run cost, full n ##########
  min        7.9 s
```

This is **not** a fast successful run and must not be quoted as a floor on what
the `docker pause` → `docker kill` mechanism costs.

`aep_full-none-notifications-0c955d71-r25` aborted after 7.88 s when the
harness's own guard refused it:

> `FaultInjectionError: the hard kill did not land: Redis reports
> uptime_in_seconds=35, so it is the same server process the run started with
> and no infrastructure fault was injected`

Because the intervals are consecutive run *start* stamps, a run that aborts
early shortens the interval that begins at it. The 7.9 s is that abort, not a
completed run.

**The mechanism's real per-run floor is the other two sessions'**: 36.0 s (s1)
and 35.3 s (s2). Session 3's median (36.0 s), mean (50.5 s) and p95 (128.0 s)
are not meaningfully disturbed by one short interval in 179.

The same run is why session 3 reads `runs with no kill event: 1`,
`kills with paused=true : 358` rather than 360, an E5 gate of `runs 179
executions 179`, and an `AEP_FULL,POSITIVE_ONLY_READBACK` cell of 29 runs
rather than 30. Those are all correct and all trace to this one refusal.

---

### Not a defect, recorded to prevent a re-investigation

`scripts/analyse_controlled_prevention.py` prints
`MECHANISM FAILURE SIGNATURES PRESENT` for that same run. That check —
"runs with no kill event" — is the **script's own**, not one of the four
mechanism-failure signatures fixed in §4 of the pre-registration. All four
pre-registered signatures are clean across all 540 runs. At 1 run in 540
(0.19%) it is also well inside the 5% tolerance §4 sets for the analogous
`paused: false` case.
