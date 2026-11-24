# Phase 40 — the stub stage, re-run. All six criteria pass.

The stub stage was held back on 2026-09-17: five criteria passed and criterion
5 failed on three defects in the budget counters
(`phase-report-40-stub-stage-2026-09-17.md`). Those are fixed — the counter
work is reported separately in `phase-report-40-counter-2026-09-18.md`, because
what was wrong with it turned out to be worth its own document — and the stage
was re-run in full.

Zero model calls. No `.env`, no key, no network. `AEP_PLANNER_MODE=stub`.

**The stub stage passes. The 10-call stage may open.**

---

## 0. What was collected

The same pre-registered cell as before: `AEP_FULL` and `B0_NAIVE_RETRY`,
`mid_dispatch`, the `notifications` endpoint (`POSITIVE_ONLY_READBACK`),
`CALLER_REFERENCE`, the crashed regime (`p(crash)=1.0`), three replicates per
system, two workers, four executions.

| | path | runs | planner artifacts |
|---|---|---|---|
| `phase40-stub-2026-09-18` | `AEP_PLANNER_MODE=stub` | 6 | 14 |
| `phase40-scripted-2026-09-18` | unset | 6 | **0** |

Plus the two cap probes. Against the pinned Redis 7.2.5 from
`compose.phase2.yml` with real `SIGKILL` injection. Run directories are not
committed: a collection with no model in it is plumbing output, not evidence
about agents.

---

## 1. Criterion 1 — exactly one mutation call per execution

**PASS.** Measured as the comparison, for the reason
`phase-report-40-stub-stage-2026-09-17.md` §1 sets out: a single event count
cannot express this, because `provider_request_transmitted` is emitted by the
AEP transmission observer only and `B0_NAIVE_RETRY` re-dispatches by design.

Per-execution event structure, agent path against scripted path:

```
  aep_full        x3   execution_started 4  transmitted 4  crash 4  classified 4
  b0_naive_retry  x3   execution_started 8  transmitted 0  crash 4  classified 4
```

**Identical on all six runs**, and the scripted collection contains zero
`planner-*` artifacts — the scripted path does not enter the agent branch.

## 2. Criterion 2 — oracle ledger and event log agree on every run

**PASS.** `agrees=true` on all six. `lost_effect_executions=0` everywhere. B0
recorded 3, 3 and 2 undetected duplicate applications; AEP recorded 0.

## 3. Criterion 3 — transcript written; replay reproduces the identical plan

**PASS.** At `p(crash)=1.0` there are two respawns per AEP run and four per B0
run. In every one of the six:

* the transcript holds exactly `executions_planned` OK decisions — 4 of 4;
* **every entry is `attempt=1`.**

A respawned worker that had re-called would have written its own attempt-1
entries for steps already decided. None did.

This is also now checked in a way that cannot go stale. The old test used
`budget.calls == 0` as its probe for "the planner was not consulted"; the
budget is now rebuilt from the transcript and correctly reports what the first
attempt spent, so that proxy would have started failing for the right behaviour.
It was replaced with a planner that raises if it is called at all, plus an
assertion that the transcript did not grow.

## 4. Criterion 4 — per-run and per-collection caps fire when forced

**PASS**, forced end-to-end with no code change.

*Per-run (36).* One worker, forty executions:

```
  VOID_PER_RUN_CALL_CAP: 37 > 36
  VOID_REASON.md: run would make attempt 37, cap is 36
  transcript: 36 entries
  journal:    73 lines = 36 reservations + 36 settles + 1 void mark
```

*Per-collection (1 000).* The journal seeded to 1 000 — and note the seeding
mechanism had to change with the fix. The old probe wrote
`planner-cumulative.json` directly; that file is now derived and nothing reads
it, so seeding it would have forced nothing at all. A probe that quietly stops
forcing the thing it claims to force is precisely the failure this stage
exists to catch, so it now seeds the journal.

```
  VOID_COLLECTION_CALL_CAP: 1001 > 1000
  VOID_REASON.md: collection would make attempt 1001, cap is 1000
  transcript files: 0    -- refused before the first call
```

## 5. Criterion 5 — cost counters present and zero

**PASS**, and on the stronger reading the brief set: not "the tests are green"
but the counter demonstrably holding under concurrency, crashes and `SIGKILL`.

Per-run, all six runs:

```
  calls=4  (transcript=4)  usd=0.0        previously calls=0 against 4
```

Collection-wide:

```
  journal   48 lines = 24 reservations + 24 settles, 48 distinct keys
  snapshot  calls=24  usd=0.0  runs=6  voided=0  _authoritative=false
  transcripts across all runs: 24
```

24 counted against 24 recorded, exactly. `runs` reads 6 where it previously
read 0 after six runs.

**The reserve/settle path really ran** — it did not net to zero by never
executing. Each reservation is priced at the ceiling and each settle returns
the difference:

```
  reservation  +0.0016288 USD   (2 000 x $0.20/M + 1 024 x $1.20/M)
  settle       -0.0016288 USD
  sum                0.0 USD
```

Zero because the stub has no model behind it, arrived at through the same
arithmetic a priced call will use.

The properties themselves are pinned in `tests/test_cumulative_counter.py`
against 2, 4 and 8 concurrent writers, `os._exit`, `SIGKILL` with other writers
live, and the cap at its boundary under load. Every defect was injected back
with its signature intact and went red; see
`phase-report-40-counter-2026-09-18.md` §3.

## 6. Criterion 6 — `.env` absent and the harness still runs

**PASS.** No `.env` in the repository. Nothing in `planner.py` or
`agent_loop.py` reads the environment for anything but the mode selector, which
`test_nothing_in_this_module_reads_the_environment` asserts. Twelve runs
completed across the two collections; the two cap probes voided as designed.

---

## 7. Verdict

| # | criterion | 2026-09-17 | 2026-09-18 |
|---|---|---|---|
| 1 | exactly one mutation call per execution | pass | pass |
| 2 | oracle ledger and event log agree | pass | pass |
| 3 | transcript written; replay reproduces the plan | pass | pass |
| 4 | per-run and per-collection caps fire when forced | pass | pass |
| 5 | cost counters present and zero | **fail** | **pass** |
| 6 | `.env` absent and the harness still runs | pass | pass |

`prompts/phase-40-agent-reachability.md` §6 says nothing advances
automatically and the author raises each cap by hand. The stub stage has now
established what it was asked to establish; the next stage is a decision, not a
consequence.

---

## 8. One thing worth recording from the probes

Probe B's journal holds 1 002 lines and 1 001 distinct keys. The repeat is a
void mark: both workers voided the same run, each appending
`{run_id}:void`. The journal's keying counts it once, so `voided` reports one
run rather than two.

That is the idempotency property doing its job on a case nobody designed for
it — which is the argument for keying every line rather than only the ones
where a duplicate seemed likely.
