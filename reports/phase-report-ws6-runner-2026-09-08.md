# WS-6: the B5 collection runner, built but not yet proven

**No data collected.** The runner exists, four of the five components `1df2b16`
named are in place, and **the gate is not proven**, so it must not be used to
collect.

---

## Built

**1. `SystemId.B5_TEMPORAL` and `B5B_TEMPORAL_AT_MOST_ONCE`** in
`experiments/baselines/contract.py`, following B4's shape. Every declared fact
matches B4's, and a test asserts it field by field — B4 and B5 are the same row
of the roadmap's table run two ways, and a descriptor that differed would make
any measured difference a difference in *what was measured*.

**2. The crash-point mapping** in `experiments/baselines/crash_points.py`. B5
needed a third mapping: it *does* write a durable pre-dispatch record, so
`_WITHOUT_PRE_DISPATCH_RECORD` is wrong, but the server writes it inside one RPC,
so `_WITH_PRE_DISPATCH_RECORD` is wrong too. `after_intent_before_barrier` maps
to `None`, `resolve_for_system` raises `CrashPointNotApplicable`, and five points
remain applicable — verified, not assumed.

**3. `REGIME_B5_TEMPORAL`** in `run_matrix.py`, 30 × 10, both arms, two
endpoints. The six frozen regimes are untouched.

**4. The runner**, `experiments/baselines/b5_temporal/collect.py`.

### Oracle attribution: the constraint the design is built around

**The runner does not compute any outcome number.** It calls
`experiments.harness.reconcile.reconcile(events_path, ledger_path)` — read from
`experiments/harness/reconcile.py:236`, the same function `run_matrix` calls for
every other arm, unchanged. The counts come from `ReconciliationReport`
(`reconcile.py:90`), built from the provider's own
`GroundTruthLedger.applied_mutations()` and `duplicate_groups()`, joined to
executions through `plan_workload(config)`'s targets.

So the runner's job is to **produce an event log of the shape the reconciler
already reads**, not to produce numbers:

* one `run_started` with `run_config` and `mock_api_config`
  (`reconcile.py:169`, `:180`);
* one `final_classification` per execution with `execution_id`, `status` and
  `outcome_class` (`:187`, `:195`) — the last is mandatory and a log without it
  is refused rather than silently counted.

The consequence that made this work: **the workflow mutates the plan's targets**,
because `execution_by_target` is how an applied row becomes an execution's
effect. A target invented in the runner would make every row unattributed.

There is no B5-specific reconciler and no B5-specific counting anywhere.

## Proven

**The runner satisfies the already-committed verdict script**, not the reverse —
`tests/test_b5_collect_contract.py`, 10 tests. A record the runner writes is read
back by `analyse_b5_agreement.read_b5_runs` and produces a rate; the arm-name
constants agree; the script's `ABSENT_IN_B5` is the point the harness actually
refuses; and a void the runner writes is a void the reader drops.
`analyse_b5_agreement.py` was **not edited**.

**22 tests pass** across the two B5 test files; the full suite is green.

## Not proven — the gate

Rule 13 requires both directions. Only one was observed:

```
branch B  (ledger this run's plan cannot explain)
    verdict=VOID_ATTRIBUTION_UNAVAILABLE   attribution_usable=False
    1 applied ledger row(s) could not be attributed to any execution
    branch B voided naming attribution : True

branch A  (expected: gate silent)
    verdict=VOID_ATTRIBUTION_UNAVAILABLE   attribution_usable=False
    129 applied ledger row(s) could not be attributed
    branch A did not void on attribution : False

BOTH BRANCHES OBSERVED: False
```

**Branch B works.** A run whose effects cannot be attributed voids naming
attribution rather than reporting a zero rate — the defect the verdict exists for.

**Branch A failed, and the cause is a defect in my proof harness, not in the
gate.** I pointed it at `/var/tmp/b5-probe/ground_truth.sqlite3`, the ledger the
probe passes had been accumulating in for days. It held **129 rows** from
previous runs, none of which this run's plan contains — so the gate voided it,
correctly.

**That is a real design requirement, surfaced by the gate doing its job:
every run needs its own ledger.** WS-4's runs each had their own
`ground_truth.sqlite3` inside the run directory; B5's must too, and the proof
harness must start a provider configured with a per-run ledger rather than
reusing a shared one. Until that is done and branch A is observed silent, **the
gate is unproven and the runner must not collect** — a session started now would
have nothing for a void decision to rest on, which is the reason the
pre-registered stopping rule exists.

## Two regressions I introduced, both caught by running the suite

**1. `test_at_most_once_dispatch_is_not_what_distinguishes_aep`.** Adding B5b
enlarged the set of at-most-once systems. The test is an inventory assertion
doing exactly its job — adding a system must force someone to say which side of
the line it falls on. B5b is at-most-once for the same reason B4b is, and is now
listed.

**2. `test_the_unit_of_analysis_is_the_run`, and this one is worse.** It broke in
**`856d78a`**, when I changed `analyse_write_loss.py` to read per-run counts from
`summary.json` instead of a key that does not exist in `matrix-progress.jsonl`.
The fixture still described the old shape. **I did not notice because that pass
ran `check_paper_numbers.py` and not the suite** — a fix verified by the wrong
gate. The fixture now writes per-run `summary.json`, matching where the data
actually lives.

**A third thing the suite caught:** the CI full-suite job did not install the
`b5` extra, which `tests/test_artifact_reproducibility.py` asserts against the
imports the suite makes. Fixed by adding `--extra b5` rather than by letting the
tests skip, since rule 7 forbids skipping.

## R14 — the fifth instance, and whether the rule should widen

`1df2b16` asked me to decide this rather than carry it.

The fifth instance was a **readiness claim in prose**: "WS-6 is ready to collect",
written without running the `grep` that would have refuted it. R14 as written
covers *instruments* that cannot report "I looked in the wrong place" — a scanner,
a checker, a probe.

**My judgement: widen R14, do not add a rule.** The defect is identical in
structure — an assertion about the world made without the check that would
falsify it — and the only difference is that the output was a sentence rather
than an exit code. A separate rule would split one failure mode across two
entries and make both easier to forget. The widening is one clause: *a report's
claim about the state of the tree is an instrument reading, and needs the same
third outcome — verified, refuted, or not checked.* Every prior instance already
satisfies the widened form.

Not applied in this pass: `docs/25` is a documentation change and rule 12 keeps
it out of a build pass. Recorded here as the decision, for its own prompt.

## Teardown

R8a evidence first, then verified from a script file: **0 ws6 containers, ports
7233 / 8233 / 8099 all free, `redis-data` intact**, `compose down` without `-v`.
R1 throughout — provider and observers killed by PID recorded at start. R12a
observers ran from before bring-up.

## Status

| Component (`1df2b16`) | State |
|---|---|
| 1. `SystemId` + crash-point mapping | **done**, verified |
| 2. B5 regime in `run_matrix` | **done** |
| 3. Run driver | **done** |
| 4. Oracle attribution via the shared reconciler | **done**, no B5-specific path |
| 5. Gate proven both directions | **NOT DONE** — branch A unproven |

**Next pass is bounded:** give each run its own ledger, re-run
`prove_attribution_gate.py`, and observe branch A silent. Nothing else is
outstanding, and nothing may be collected until it is.
