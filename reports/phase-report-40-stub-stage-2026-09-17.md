# Phase 40 — the stub stage, measured against its pre-registered criteria

> **Superseded, not corrected.** The three counter defects §5 records
> were fixed on 2026-09-18 and the stage was re-run:
> `phase-report-40-stub-stage-2026-09-18.md`, with the counter work in
> `phase-report-40-counter-2026-09-18.md` — what was wrong with it turned
> out to be worth its own document. **Nothing below is edited.** It is
> what the stage found on the day it ran, including the false failure in
> §1 that was my probe's error and not the harness's, and that record is
> worth more intact than tidied.

**Six criteria were fixed in `prompts/phase-40-agent-reachability.md` §6 before
any of this code existed.** This report gives each one a verdict and its
evidence. Five pass. One fails, and it fails on three separate defects in the
budget counters. Nothing below was adjusted to make a criterion pass; the
failing criterion is reported failing and the live stage does not open.

Zero model calls. No `.env`, no key, no network. `AEP_PLANNER_MODE=stub`.

---

## 0. What was collected

Two collections of the same cell — the pre-registered one: `AEP_FULL` and
`B0_NAIVE_RETRY`, `mid_dispatch`, the `notifications` endpoint
(`POSITIVE_ONLY_READBACK`), `CALLER_REFERENCE` keying, the crashed regime
(`p(crash)=1.0`), three replicates per system, two workers, four executions.

| | path | runs | planner artifacts |
|---|---|---|---|
| `phase40-stub-2026-09-17` | `AEP_PLANNER_MODE=stub` | 6 | 13 |
| `phase40-scripted-2026-09-17` | unset | 6 | **0** |

Plus two cap probes, `cap-per-run` and `cap-collection`.

Both collections ran against the pinned Redis 7.2.5 from `compose.phase2.yml`
(`verify_redis_semantics.py`: `appendonly=yes`, `appendfsync=everysec`,
`waitaof=present`) with real `SIGKILL` fault injection.

The run directories are **not committed**. They are stub-mode plumbing output,
not results; §6 of the pre-registration calls this stage "0 calls", and a
collection with no model in it is not evidence about agents. They live outside
the repository at `AEP/stub-results/`.

---

## 1. Criterion 1 — exactly one mutation call per execution

**PASS.**

This cannot be read off a single event count, and the first attempt to do so
gave a false failure worth recording. `provider_request_transmitted` is emitted
by the AEP transmission observer only — `docs/31-transmission-event.md` says in
terms that "the five baseline runs at `mid_dispatch` carry **no** event, which
is correct" — so counting it for `B0_NAIVE_RETRY` counts nothing. And B0
re-dispatches on timeout by design: eight `execution_started` events for four
executions is the baseline behaving as the baseline, and its duplicate
applications are the paper's headline finding. A probe that called that a
violation would be measuring the experiment and calling it a bug.

The measurement that means something is the comparison. The same cell was
collected on both paths and the per-execution event structure compared:

```
                                      execution_started  transmitted  crash_injected  final_classification
aep_full        r0/r1/r2   agent            4                 4             4                  4
                           scripted         4                 4             4                  4
b0_naive_retry  r0/r1/r2   agent            8                 0             4                  4
                           scripted         8                 0             4                  4
```

Identical on all six runs. The agent loop does not cause an execution to issue
a second mutation call; where the count is two, it is two on both paths.

Oracle *outcomes* differ on two of the six runs
(`oracle_applied_rows` 0 vs 2 on one AEP replicate, 7 vs 8 on one B0
replicate). The counter-check is that replicates of the same cell differ among
themselves **on the scripted path too** — AEP `r2` recorded `applied_rows=2`
where `r0` and `r1` recorded 0, and B0 recorded 7, 8 and 6 across its three.
With `timeout_probability=0.15` and a real `SIGKILL`, that is ordinary
replicate variation, not something the agent loop introduced.

## 2. Criterion 2 — oracle ledger and event log agree on every run

**PASS.** `summary.json: agrees=true` on all six runs, on both paths.
`lost_effect_executions=0` everywhere. B0 recorded 3, 3 and 2 undetected
duplicate applications and AEP recorded 0, which is the expected direction.

## 3. Criterion 3 — transcript written; replay reproduces the identical plan

**PASS**, and this is the criterion the crashed regime tests hardest.

At `p(crash)=1.0` every worker dies and is respawned — two respawns per AEP
run, four per B0 run. In every one of the six runs:

* the transcript holds exactly `executions_planned` OK decisions;
* **every entry is `attempt=1`.**

A respawned worker that had re-called the planner would have written attempt-1
entries of its own for steps already decided, and the decision count would
exceed the plan. It never does. The respawn reads
`planner-transcript.jsonl`, reconstructs the decision and issues no call. That
is correctness — a respawn is not allowed to decide differently — and it is
cost, because the crashed regime is the whole experiment and a re-calling
respawn would double the bill of every run in it.

## 4. Criterion 4 — per-run and per-collection caps fire when forced

**PASS**, forced end-to-end with **no code change**, because a cap that only
fires when the source is edited is not the cap that will run the collection.

*Per-run (36).* One worker, forty executions. The 37th decision is refused
**before the call is made**; thirty-six transcript entries exist and the
thirty-seventh does not.

```
CapExceeded: VOID_PER_RUN_CALL_CAP: 37 > 36
VOID_REASON.md: run would make attempt 37, cap is 36
transcript: 36 entries
```

*Per-collection (1000).* `planner-cumulative.json` seeded to 1000 — which is
also how an operator meets this ceiling in practice. The first decision of the
next run is refused and the transcript is empty.

```
CapExceeded: VOID_COLLECTION_CALL_CAP: 1001 > 1000
VOID_REASON.md: collection would make attempt 1001, cap is 1000
transcript: 0 entries
```

In both cases the run aborts and is marked `VOID_*`. It does not finish with
partial data and it is not analysed.

## 5. Criterion 5 — cost counters present and zero

**FAIL.** `usd` is 0.0 everywhere, as it must be with no model behind the
stub. The counters are not correct, in three separate ways.

**A. The per-run file is clobbered by a respawn.** Every run's
`planner-budget.json` reads `calls: 0` while its transcript holds four
entries. `CallWrapper.__init__` calls `write_budget()`, so a respawned worker
— which replays and therefore makes no calls — writes a fresh
`RunBudget(calls=0)` over the file the first attempt had filled in. Last
writer wins, and the last writer is always the one with nothing to report.
Reproduced directly:

```
after the first attempt made 4 calls:               4
after a respawned worker constructs its wrapper:    0
```

**B. The cumulative counter loses increments under concurrency.**
`planner-cumulative.json` recorded 23 calls where the six transcripts hold 24.
`CumulativeCounter.add` is a read-modify-write and the workers are separate
processes. `os.replace` makes the *write* atomic; it does not make the
read-modify-write atomic. Four processes doing 200 increments each:

```
expected 800, counted 202 — 598 lost
```

This is the serious one. The per-collection call cap and the USD ceiling are
both enforced from this file, and §3 of the pre-registration treats USD 20 as a
hard ceiling. A ceiling read from a counter that silently undercounts by a
factor of four under two-worker concurrency is not a ceiling. The stub stage
caught it at zero cost, which is what the stub stage is for.

**C. `runs` is never incremented.** It is initialised, written and read, and
nothing ever adds to it: the collection recorded `"runs": 0` after six runs.
A field that is reported and not maintained is worse than an absent one.

None of this is fixed in this commit. The instruction for this stage was to
report a failure rather than adjust anything to pass it, and a counter defect
found by the stage it was designed to be found by belongs in the record before
it belongs in a patch.

## 6. Criterion 6 — `.env` absent and the harness still runs

**PASS.** No `.env` exists in the repository — `ls` reports no such file, and
nothing in `planner.py` or `agent_loop.py` reads the environment for anything
but the mode selector (`tests/test_planner_budget.py`
`test_nothing_in_this_module_reads_the_environment`). Twelve runs completed
across the two collections and two cap probes voided as designed.

---

## 7. Verdict

| # | criterion | verdict |
|---|---|---|
| 1 | exactly one mutation call per execution | pass |
| 2 | oracle ledger and event log agree | pass |
| 3 | transcript written; replay reproduces the plan | pass |
| 4 | per-run and per-collection caps fire when forced | pass |
| 5 | cost counters present and zero | **fail** |
| 6 | `.env` absent and the harness still runs | pass |

**The stub stage has not passed, so the 10-call stage does not open.**
§6 says nothing advances automatically, and this is the first thing that has
had to be held back by that rule rather than merely permitted by it.

What must be true before it does:

1. `RunBudget` is reconstructed from the transcript on respawn, not reset — the
   transcript is already the durable record and the budget file should be
   derived from it rather than kept in parallel.
2. `CumulativeCounter.add` becomes atomic across processes.
3. `runs` is either maintained or removed.
4. A test for each, and a concurrency test that fails against today's `add`.

## 8. Two things the collection tripped over that are not defects in this work

*The disposability marker.* Six runs aborted because Redis had not advertised
`aep:test-instance-marker`. That is rule 9 working — the harness kills
processes and deletes keys on that instance and refuses one that has not said
it is disposable.

*`/tmp` is not storage.* A first stub collection of five runs was lost when the
WSL distro restarted and cleared `/tmp`. Re-collected to the Windows disk.

*Port 8099.* One run of that first collection failed with
`MockApiStartupError` on an orphaned provider holding the port — the R12 hazard
`launch_ws5_collection.sh` already documents. The re-collection checks the port
is free before starting and all six runs completed.
