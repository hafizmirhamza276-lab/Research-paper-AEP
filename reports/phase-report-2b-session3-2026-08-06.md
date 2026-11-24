# Phase 2B Session 3 — baselines, the matrix, and the analysis

**Date:** 2026-08-06
**Roadmap section:** `PAPER_ROADMAP.md` §3.2, §3.3 (Phase 2B, Session 3), with
the session amendments D0–D5.
**Predecessor:** `reports/phase-report-2b-session2-2026-08-05.md`

---

## A. Phase attempted and roadmap section reference

Session 3 of Phase 2B: the baselines B0–B4, the `{system × crash-point ×
response-class × read-back-keying}` matrix, and the analysis that turns a
directory of run logs into the paper's Table 1.

The amendments governing this session, and where each is discharged:

| Amendment | Requirement | Outcome |
|---|---|---|
| **D0(i)** | Commit/push Session 2; obtain a green Linux CI run | **Done.** Run [31008255041](https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31008255041), all three jobs green on `ubuntu-24.04` (§C.1) |
| **D0(ii)** | Six crash points × 1 run on Linux, EVALUATION mode, reconciliation agrees for all six | **Done, after failing once.** The first attempt failed at two crash points; the cause was a defect in the harness's own experimental setup, not in the protocol (§C.2) |
| **D0(iii)** | Mock API sustains ≥ 10× the busiest planned configuration's request rate | **Done.** 468.8 req/s against a planned peak of 2.5 req/s = **187×** (§C.3) |
| **D1** | B0–B3 as thin variants sharing the connector and workload driver, each with failing-then-passing tests; B4 implemented if feasible | **Done, including B4 as a real implementation** rather than the permitted qualitative fallback (§C.4–§C.9) |
| **D2** | `run_matrix.py` over the four-dimensional matrix, 30 reps/cell, resumable, seeds recorded, EVALUATION mode on Linux; plan emitted before launch | **Done.** 216 cells, 198 applicable, 594 runs, plan in §C.10 |
| **D3** | `analyze.py`: all §3.2 metrics, bootstrap CIs, Fisher's exact tests, CSV + Table 1 + PDF figures, reading only `events.jsonl` + the oracle ledger | **Done**, with a source gate enforcing the reading restriction (§C.11–§C.12) |
| **D4** | Any undetected duplicate in AEP-full halts the matrix and becomes the primary result | **Armed, not triggered.** The halt is implemented; AEP-full recorded **0 undetected duplicates in 180 executions** across all six crash points (§C.13) |
| **D5** | If the matrix exceeds the session, deliver D0–D3 complete, launch resumably, report PARTIAL with the resume command | **This is the case.** 83 of 594 runs collected; §C.13 and §E1 |

**The headline honest statement of this session.** D0–D3 are complete and
evidenced. The matrix is **partial** — 83 of 594 runs, which is tier 1 complete
for five of six systems — and every number below is labelled with the slice it
came from.

The result that slice supports: **AEP-full recorded no undetected duplicate in
180 executions across all six crash points, against 0.81–0.82 for the three
baselines with no pre-dispatch record (p < 1e-62)**, with zero reconciliation
disagreements in all 83 runs.

Three results it explicitly does **not** support, each stated where it would
otherwise be assumed: the known-ambiguity claim (§F8), the B3 ablation (§F3),
and RQ3's overhead numbers (§E8). And one measurement defect found and closed
during the analysis rather than after publication (§F5).

---

## B. Files created/modified

### The systems under comparison — `experiments/baselines/` (new, 2 379 lines)

| File | What it is |
|---|---|
| `contract.py` | `SystemId`, `OutcomeClass`, `ResumePolicy`, and the `SystemDescriptor` table: one machine-readable row per system in the roadmap's §3.3 table. The two modelling decisions that change numbers — what a supervisor does with a crashed execution, and which systems send a client reference — are stated at the top of it. |
| `common.py` | Everything the six systems share so that only the differences differ: the wire format, the evidence policy, the checkpoint hook, the bounded lease wait, and the shape of a durable outcome record. |
| `b0_naive_retry.py` | B0. No lease, no CAS, no pre-dispatch record; retries whenever the answer was not definitive. |
| `b1_lease_only.py` | B1. Real distributed lock, raw `SET` state, no intent ledger. |
| `b2_cas_only.py` | B2. Fenced expected-version CAS state writes through `RedisStorageAdapter`, no write-ahead intent. |
| `b3_no_barrier.py` | B3. `NoBarrierDurabilityBarrier`: the full `WriteAheadRunner` with `WAITAOF` removed and nothing else removed. |
| `b4_durable_workflow.py` | B4. A minimal event-sourced durable-execution engine: append-only history, durably acknowledged, replayed after a crash, activities memoised — and it still duplicates. |
| `crash_points.py` | The roadmap's six crash points mapped into each baseline's own vocabulary, with the ones that **do not exist** in a given system marked not-applicable and never run. |
| `intent_classifier.py` | The one mapping from `IntentStatus` to the shared outcome vocabulary, used by B3 and AEP-full. |
| `tests/` | 60 tests: one file per baseline plus the descriptor anti-drift gates and the lease-waiting regression. |

### The harness — `experiments/harness/` (modified)

| File | Change |
|---|---|
| `orchestrate.py` | **New.** One provider, one ledger, one freshly seeded fault generator per run. This is the fix for the D0(ii) failure. |
| `config.py` | `RunConfig` now carries `system`, `resume_policy` and `max_dispatch_attempts`; the crash point is resolved *in the run's system's vocabulary*, so an inapplicable cell is refused at construction. |
| `composition.py` | `build_system` / `classify_execution` — the factory and the classifier for all six systems; `build_barrier` selects B3's ablated barrier from the descriptor; `seed_execution_state` is now idempotent and waits for the lease. |
| `worker.py` | Builds whichever system the run names, hands the injector that system's crash-point resolver, seeds state only for the systems that use the fenced write path, and records the outcome class. |
| `runner.py` | Resume policy (`REEXECUTE_CRASHED` vs `NEXT_EXECUTION`), recovery process started only for the systems that declare one, settling skipped where there is nothing to settle, final classification through the system's own classifier. |
| `reconcile.py` | Rewritten around the shared outcome vocabulary, with every rule gated on what the system under test actually promised. |
| `injector.py` | Accepts a crash-point resolver and deferred-point set, so it can speak either vocabulary without knowing which systems exist. |

### The mock API — `experiments/mock_api/` (modified)

| File | Change |
|---|---|
| `supervisor.py` | **New.** Renders a per-run configuration, starts a provider, and *verifies it is serving that configuration's digest* before returning. |
| `client.py` | `transmit()` split out of `mutate()` so the baselines share the connector without inheriting the request-binding machinery under ablation. |

### Experiment drivers and analysis — `experiments/` (new)

| File | What it is |
|---|---|
| `smoke_matrix.py` | D0(ii): the six crash points, one run each, refusing to run on a platform without `SIGKILL`. |
| `bench_mock_api.py` | D0(iii): sustained throughput against the planned peak, computed from `run_matrix.py`'s own constants. |
| `run_matrix.py` | D2: the matrix as code. Plan-first, tiered, resumable, seeds derived and recorded, D4's halt implemented. |
| `statistics.py` | Exact Fisher's exact test and a run-clustered percentile bootstrap. |
| `analyze.py` | D3: every §3.2 metric, CSV per metric, Table 1, PDF figures. |
| `configs/smoke.yaml`, `configs/matrix.yaml` | The provider templates each run is rendered from. |
| `tests/test_statistics.py` | The statistics checked against values worked out by hand. |
| `tests/test_analysis_isolation.py` | The source gate enforcing D3's reading restriction. |

### Infrastructure

| File | Change |
|---|---|
| `pyproject.toml` | New `analysis` extra (matplotlib only — the statistics are implemented here). |
| `.github/workflows/ci.yml` | Installs the `analysis` extra; `MINIMUM_TESTS` raised 1500 → 1590. |
| `scripts/wsl_*.sh` | The Windows→Linux bridge: sync, environment setup, command runner. Development is on Windows; **every number in this report was collected on Linux.** |

---

## C. Raw command outputs

### C.1 D0(i) — Session 2 committed, pushed, and green on Linux

Commit `2fefe5e` pushed to `origin/main`; workflow run `31008255041`.
GitHub's logs endpoint requires admin rights on this repository, so the
evidence below is the API's own per-step conclusions, taken verbatim:

```
$ curl -s ".../actions/runs/31008255041" | python -c "...print(status, conclusion)"
completed success

$ curl -s ".../actions/runs/31008255041/jobs" | python -c "..."
'Citation ranges (docs/22)': completed/success  runner=GitHub Actions 1000000102 labels=['ubuntu-24.04']
    -  1 Set up job: success
    -  2 Run actions/checkout@v4: success
    -  3 Install uv: success
    -  4 Sync locked environment: success
    -  5 Validate docs/22-formal-model.md citations: success
    -  9 Post Install uv: success
    - 10 Post Run actions/checkout@v4: success
    - 11 Complete job: success
'WAITAOF durability (compose, phase2.conf)': completed/success  runner=GitHub Actions 1000000103 labels=['ubuntu-24.04']
    -  1 Set up job: success
    ...
    -  7 Run the WAITAOF integration suite: success
    -  8 Gate -- zero skipped, zero xpassed: success
    -  9 Confirm AOF survived the restart test: success
    - 10 Tear down: success
    - 11 Upload WAITAOF reports: success
    - 23 Complete job: success
'Suite (py3.13, Redis from compose)': completed/success  runner=GitHub Actions 1000000104 labels=['ubuntu-24.04']
    -  1 Set up job: success
    ...
    -  8 Run the suite: success
    -  9 Gate -- zero skipped, zero xpassed, suite actually ran: success
    - 10 Confirm AOF survived the restart test: success
    - 11 Tear down: success
    - 12 Upload test and coverage reports: success
    - 25 Complete job: success
```

The gate steps are the load-bearing ones: step 9 of the main job is
`scripts/check_pytest_gates.py --minimum-tests 1500`, which fails on any
skipped test, any xpassed test, or a collection below the floor.

**Limitation, stated:** these are the API's step conclusions, not the log
text. A reviewer with repository admin rights can download the raw log; I
cannot, and I have not pretended otherwise.

### C.2 D0(ii) — the smoke matrix, which failed first and why that mattered

**First attempt — FAIL at two of six crash points.**

```
--------------------------------------------------------------
crash point: after_response_before_resolution
--------------------------------------------------------------
{
  "agrees": false,
  "classifications": { "FIRED_CONFIRMED": 6 },
  "disagreements": [],
  "executions_planned": 6,
  "oracle_applied_rows": 12,
  "oracle_effect_executions": 6,
  "oracle_unattributed_rows": 6,
  ...
}
exit status: 1

--------------------------------------------------------------
crash point: after_resolution_before_barrier
--------------------------------------------------------------
{
  "agrees": false,
  "disagreements": [],
  "oracle_applied_rows": 18,
  "oracle_effect_executions": 6,
  "oracle_unattributed_rows": 12,
  ...
}
exit status: 1

==============================================================
D0(ii) FAIL -- disagreement at: after_response_before_resolution after_resolution_before_barrier
Per D0, any disagreement stops the phase.
```

`disagreements` is empty in both. The only failing condition is
`oracle_unattributed_rows` — 6, then 12 — which is exactly the cumulative
effect count of the runs that preceded each. All six runs shared one ledger
file, so every run after the first was being asked to account for effects that
belonged to a different run.

That is a defect in the experimental setup, and it exposed a second one that
would have been far more damaging: `MockLegacyAPI` seeds **one**
`random.Random(config.seed)` per *process*, and every mutation draws three
fault decisions from it. Shared across runs, run *N*'s fault stream is a
function of how many requests runs *1..N−1* happened to make — so the seed
recorded in run *N*'s log does not determine run *N*'s faults. Nothing would
have failed. The numbers would simply not have meant what they said.

Both are fixed the same way: one provider process, one ledger, one freshly
seeded generator, **per run** (`experiments/mock_api/supervisor.py`,
`experiments/harness/orchestrate.py`).

**Second attempt — PASS at all six.**

```
======================================================================
D0(ii) smoke matrix -- 6 crash points x 1 run
  platform:      Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.39
  python:        3.13.0
  has_sigkill:   True
  kill:          SIGKILL
  redis:         redis://127.0.0.1:6381/15
  template:      experiments/configs/smoke.yaml
  results root:  experiments/results/smoke
======================================================================
...
======================================================================
  PASS  before_intent_write                settled=True      3.0s
  PASS  after_intent_before_barrier        settled=True     31.0s
  PASS  after_barrier_before_dispatch      settled=True     35.0s
  PASS  mid_dispatch                       settled=True     36.0s
  PASS  after_response_before_resolution   settled=True     40.0s
  PASS  after_resolution_before_barrier    settled=True     11.1s
======================================================================
D0(ii) PASS -- reconciliation agreed at all 6 crash points
manifest: experiments/results/smoke/smoke-matrix.json
```

Crash fidelity, from the `mid_dispatch` run's own log:

```
{
  "event": "crash_injected",
  "crash_point": "AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION",
  "roadmap_crash_point": "mid_dispatch",
  "style": "SIGKILL_DEFERRED",
  "has_sigkill": true
}
--- worker exit statuses ---
      6 "exit_status": -9
      1 "exit_status": 0
```

`-9` is a real `SIGKILL`. **Session 2's §F4 caveat is retired for every run in
this report.**

Full output: `reports/raw/d0ii-smoke-matrix.txt`.

### C.3 D0(iii) — the provider's throughput ceiling

Carried over unresolved from Session 1 §F8 and Session 2 §F9/§G3.

```
{
  "achieved_requests_per_second": 468.79,
  "concurrency": 16,
  "duration_seconds": 20.02,
  "headroom_multiple": 187.52,
  "latency_ms": { "max": ..., "mean": ..., "median": ..., "p95": ..., "p99": ... },
  "ledger_applied_rows": 9385,
  "non_200_responses": 0,
  "passes": true,
  "planned_peak_model": {
    "max_dispatch_attempts": 3,
    "note": "upper bound: every worker assumed to issue its maximum attempts plus one read-back, back to back, never idle",
    "per_execution_seconds": 3.2,
    "requests_per_execution": 4,
    "workers": 2
  },
  "planned_peak_requests_per_second": 2.5,
  "platform": "Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.39",
  "python": "3.13.0",
  "requests_sent": 9384,
  "required_headroom_multiple": 10.0,
  "warmup_requests": 1
}

D0(iii) PASS -- 468.79 req/s sustained is 187.52x the busiest planned configuration's 2.5 req/s (bar: 10.0x).
```

The planned peak is computed from `run_matrix.py`'s own constants rather than
estimated, so the two cannot drift, and it is a deliberate *upper* bound: it
assumes every worker issues its maximum attempts plus a read-back, back to
back, never idle.

**What this licenses and what it does not.** It licenses the claim that the
provider is not the bottleneck in the fault-injection matrix. It does **not**
license a claim about AEP's absolute throughput: the mock API's ~36 ms mean
service latency under load is still inside every end-to-end number, and §3.2's
overhead comparison is a comparison *between systems sharing that provider*,
not an absolute measurement. That is stated again in §F.

Full output: `reports/raw/d0iii-throughput.txt`.

### C.4 D1 — B0, red then green

Red, before `experiments/baselines/b0_naive_retry.py` existed:

```
$ python -m pytest experiments/baselines/tests/test_b0_naive_retry.py -q
=================================== ERRORS ====================================
_____ ERROR collecting experiments/baselines/tests/test_b0_naive_retry.py _____
ImportError while importing test module '...test_b0_naive_retry.py'.
Traceback:
experiments\baselines\tests\test_b0_naive_retry.py:22: in <module>
    from experiments.baselines.b0_naive_retry import NaiveRetryRunner, classify
E   ModuleNotFoundError: No module named 'experiments.baselines.b0_naive_retry'
=========================== short test summary info ===========================
ERROR experiments/baselines/tests/test_b0_naive_retry.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.46s
```

Green:

```
$ python -m pytest experiments/baselines/tests/test_b0_naive_retry.py -q
...........                                                              [100%]
11 passed in 0.15s
```

The eleven tests are all about what is observable outside the runner — what
reached the wire and what is in Redis afterwards — because a baseline that
merely *reported* retrying would not generate the duplicate the evaluation
counts. The amendment's own wording (*"B0 demonstrably retries on timeout
without any intent record"*) is two of them:
`test_retries_on_timeout` asserts three transmissions for two ambiguous
answers, and `test_writes_no_intent_record` asserts against Redis directly.

### C.5 D1 — B1, B2, B3, B4, red then green

Red, before any of the four modules existed:

```
$ python -m pytest experiments/baselines/tests/ -q
...
E   ModuleNotFoundError: No module named 'experiments.baselines.b3_no_barrier'
E   ModuleNotFoundError: No module named 'experiments.baselines.b4_durable_workflow'
=========================== short test summary info ===========================
ERROR experiments/baselines/tests/test_b1_lease_only.py
ERROR experiments/baselines/tests/test_b2_cas_only.py
ERROR experiments/baselines/tests/test_b3_no_barrier.py
ERROR experiments/baselines/tests/test_b4_durable_workflow.py
!!!!!!!!!!!!!!!!!!! Interrupted: 4 errors during collection !!!!!!!!!!!!!!!!!!!
4 errors in 0.24s
```

Green (against real Redis 7.2 with AOF, which B2's CAS and B3's barrier both
require):

```
$ REDIS_URL=redis://127.0.0.1:6381/15 python -m pytest experiments/baselines/tests/ -q -ra
........................................                                 [100%]
40 passed in 0.67s
```

and after the contract anti-drift gates were added:

```
$ REDIS_URL=redis://127.0.0.1:6381/15 python -m pytest experiments/baselines/tests/ -q -ra
......................................................                   [100%]
54 passed in 0.75s
```

### C.6 B3 — the ablation, observed on the wire

The single most important assertion about B3 is that the ablation is real and
is *only* the ablation:

```python
async def test_confirm_durable_issues_no_waitaof(redis_client) -> None:
    barrier = await _validated_barrier(redis_client)
    connection = RecordingConnection(redis_client)
    durable = await barrier.confirm_durable(connection, 2000)
    assert durable is True
    assert connection.commands == []
```

with a control in the same file proving the *real* barrier does issue it
(`("WAITAOF",) in connection.commands`) — without which the first assertion
proves nothing. `validate_startup` is deliberately **not** ablated, so B3 still
refuses a server without AOF or `WAITAOF` support; what is removed is one round
trip per dispatch and nothing else.

### C.7 B4 — implemented, not argued

The roadmap permits *"a carefully argued qualitative comparison + micro-benchmark
of its logging overhead"* if a real implementation is too costly. It was not too
costly, and the real one is worth much more, because B4 settles the objection a
reviewer raises first: *isn't this just durable execution?*

The defining test:

```python
async def test_replay_of_a_scheduled_but_uncompleted_activity_re_runs_it(...):
    # the history is left exactly as a crash between transmission and
    # response leaves it: scheduled, not completed
    await runner._append(item.execution_id, {"event": ACTIVITY_SCHEDULED, ...})
    outcome = await runner.execute(...)
    assert len(connector.transmissions) == 1
    assert outcome.outcome_class is not OutcomeClass.DECLARED_AMBIGUOUS
```

B4 has a durable, `WAITAOF`-acknowledged write-ahead record — the same barrier
AEP-full uses — and it still duplicates, because its semantics for a
scheduled-but-uncompleted activity are at-least-once: run it again. **The
write-ahead record is necessary and is not sufficient; what matters is the
policy applied to it.** That sentence is the paper's contribution, and B4 is
what makes it a measurement instead of an assertion.

### C.8 Two defects the matrix found that the unit suite had not

The first end-to-end matrix run across all six systems produced this:

```
AEP_FULL               agrees=True  dup_undet=0   lost=0   rows=4  classes={'CONFIRMED_APPLIED': 4}
B0_NAIVE_RETRY         agrees=True  dup_undet=3   lost=0   rows=7  classes={'CONFIRMED_APPLIED': 4}
B1_LEASE_ONLY          agrees=True  dup_undet=0   lost=4   rows=4  classes={'NO_RECORD': 4}
B2_CAS_ONLY            agrees=True  dup_undet=0   lost=4   rows=4  classes={'NO_RECORD': 4}
B3_INTENT_NO_BARRIER   agrees=True  dup_undet=0   lost=0   rows=4  classes={'CONFIRMED_APPLIED': 4}
B4_DURABLE_WORKFLOW    agrees=True  dup_undet=0   lost=3   rows=3  classes={'UNVERIFIED_FAILURE': 4}
```

B0 duplicated as designed; B1, B2 and B4 produced four `NO_RECORD` executions
and four lost effects apiece. Both causes made a baseline look **better** than
it is, which is the direction that matters.

**(1) A re-executing supervisor gave up on the lease instead of waiting for
it.** A worker killed mid-dispatch leaves its lease held until the TTL expires;
the supervisor respawns within a second; `acquire_lock` returned `None` and the
baseline raised. That credited the lease with *preventing* a duplicate that it
only ever delays. The trace:

```
{"event": "resume_reexecuting_crashed", "execution_index": 0, "worker_index": 1}
{"attempt": 2, "crash_armed_for": 1, "event": "worker_spawned", "from_index": 0}
{"event": "execution_started", "execution_index": 0, "source": "worker-1#2"}
{"event": "execution_failed",  "execution_index": 0, "source": "worker-1#2"}
```

Fixed by a bounded wait (`acquire_lease_or_wait`), which also **measures** the
wait — that delay is the throughput cost a lease imposes under crashes and is
itself a result.

**(2) `seed_execution_state` was not idempotent.** It creates the `IDLE` record
the fenced write path requires with `expected_version=0` — correct exactly
once. B2 is the only system that both uses that path *and* re-executes, so it
was the only one to reach it twice, and the second call raised
`StaleWriteError` before anything was transmitted.

Both fixed with failing-then-passing regressions
(`experiments/baselines/tests/test_lease_waiting.py`,
`experiments/harness/tests/test_seed_idempotence.py`):

```
$ REDIS_URL=... python -m pytest experiments/harness/tests/test_seed_idempotence.py -q
E   TypeError: seed_execution_state() got an unexpected keyword argument 'lease_wait_seconds'
FAILED ... ::test_seeding_is_idempotent
FAILED ... ::test_seeding_does_not_overwrite_work_already_done
FAILED ... ::test_seeding_waits_for_a_lease_a_dead_worker_holds
FAILED ... ::test_the_wait_is_bounded
4 failed in 0.68s

$ REDIS_URL=... python -m pytest experiments/harness/tests/test_seed_idempotence.py -q
....                                                                     [100%]
4 passed in 2.21s
```

### C.9 The same smoke, after both fixes

```
AEP_FULL               agrees=True  dup_undet=0   lost=0  rows=4  classes={'CONFIRMED_APPLIED': 4}
B0_NAIVE_RETRY         agrees=True  dup_undet=3   lost=0  rows=7  classes={'CONFIRMED_APPLIED': 4}
B1_LEASE_ONLY          agrees=True  dup_undet=4   lost=0  rows=8  classes={'CONFIRMED_APPLIED': 4}
B2_CAS_ONLY            agrees=True  dup_undet=5   lost=0  rows=9  classes={'CONFIRMED_APPLIED': 4}
B3_INTENT_NO_BARRIER   agrees=True  dup_undet=0   lost=0  rows=4  classes={'CONFIRMED_APPLIED': 4}
B4_DURABLE_WORKFLOW    agrees=True  dup_undet=3   lost=0  rows=7  classes={'CONFIRMED_APPLIED': 4}
```

Four executions per system at one crash point. Not a statistical result — it is
the shape check that says the apparatus is measuring the thing it was built to
measure, and it is the reason the matrix was launched rather than debugged
further.

### C.10 D2 — the matrix plan, emitted before anything ran

```
==============================================================================
AEP evaluation matrix plan (aep.matrix/1)
==============================================================================
  platform             Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.39
  python               3.13.0
  real SIGKILL         True
  matrix seed          20260806
  repetitions/cell     30 (3 runs x 10 executions)
  workers per run      2
  cells (total)        216
  cells (applicable)   198
  cells (not applic.)  18
  runs planned         594
  estimated wall time  5.86 h (21087.0 s)

  by tier:
    tier 1:   99 runs,  0.98 h   Table 1: all systems x all crash points, AUTHORITATIVE_READBACK, CALLER_REFERENCE
    tier 2:  198 runs,  1.95 h   other response classes, CALLER_REFERENCE
    tier 3:  297 runs,  2.93 h   ORACLE_FINGERPRINT sensitivity variant

  not applicable (recorded, never run):
    B0_NAIVE_RETRY         after_intent_before_barrier        the system writes no record before dispatching, so there is no window between writing one and acknowledging it durable
    B1_LEASE_ONLY          after_intent_before_barrier        the system writes no record before dispatching, so there is no window between writing one and acknowledging it durable
    B2_CAS_ONLY            after_intent_before_barrier        the system writes no record before dispatching, so there is no window between writing one and acknowledging it durable
    (18 cells in total, over 3 system/crash-point pairs)
```

Written to `experiments/results/matrix/matrix-plan.json` and `matrix-plan.txt`
before the first run.

**On "30 repetitions".** The unit of every §3.2 metric is one agent execution —
one intended non-idempotent effect — so a repetition is one execution, and a
cell is 3 runs × 10 executions. Collecting all 30 in a single run would make
them share one provider, one lease namespace and one respawn history;
collecting 30 runs of one execution would cost 30 provider starts and 30
settling periods per cell. Splitting it samples run-level effects too, which is
what lets the analysis report a **cluster bootstrap** interval instead of
pretending 30 correlated observations are 30 independent draws.

**On the 18 inapplicable cells.** `after_intent_before_barrier` does not exist
in B0, B1 or B2 — they write nothing before dispatching, so there is no window
between writing a record and acknowledging it. Those cells are carried in the
plan with `applicable: false` and a reason, and nothing is run for them.
Aliasing them onto a neighbouring crash point would have produced a full row of
numbers for an experiment that was never performed.

### C.11 D3 — the analysis, and the gate on what it may read

```
$ python -m pytest experiments/tests/ -q
..........................                                               [100%]
26 passed in 0.47s
```

`experiments/tests/test_analysis_isolation.py` parses `analyze.py` and
`statistics.py` and fails the suite if either imports `redis`, `fakeredis`,
anything under `aep_core`, or any harness module that opens Redis. It also
asserts the ledger is opened `mode=ro`, that only `events.jsonl` and
`ground_truth.sqlite3` are named, and — deliberately — that `summary.json` is
**not**, because reading the harness's own reconciliation would make the
paper's numbers a restatement rather than a recomputation.

The statistics are checked against values computed by hand rather than against
another library: Fisher's tea-tasting table (34/70), the perfectly separated
table (2/70), and a bootstrap whose answer is forced by construction
(identical clusters ⇒ degenerate interval; a single cluster ⇒ a point, reported
as a point rather than disguised as a range).

### C.12 D3 — the pipeline, end to end on the six-system smoke

```
Table 1 -- per system, pooled over every cell collected
==============================================================================================
system                  runs   exec  undet.dup           95% CI  known amb.    lost   Fisher p
----------------------------------------------------------------------------------------------
AEP_FULL                   1      4     0.0000   [0.000, 0.000]      0.0000  0.0000         --
B0_NAIVE_RETRY             1      4     0.7500   [0.750, 0.750]      0.0000  0.0000   1.43e-01
B1_LEASE_ONLY              1      4     1.0000   [1.000, 1.000]      0.0000  0.0000   2.86e-02
B2_CAS_ONLY                1      4     1.0000   [1.000, 1.000]      0.0000  0.0000   2.86e-02
B3_INTENT_NO_BARRIER       1      4     0.0000   [0.000, 0.000]      0.0000  0.0000   1.00e+00
B4_DURABLE_WORKFLOW        1      4     0.5000   [0.500, 0.500]      0.0000  0.0000   4.29e-01
==============================================================================================

written:
  .../analysis/table-1.csv
  .../analysis/per-cell-metrics.csv
  .../analysis/comparisons-vs-aep-full.csv
  .../analysis/latency-and-throughput.csv
  .../analysis/per-execution.csv
  .../analysis/metric-undetected-duplicate-rate.csv
  .../analysis/metric-known-ambiguity-rate.csv
  .../analysis/metric-lost-effect-rate.csv
  .../analysis/metric-unverified-failure-rate.csv
  .../analysis/metric-state-corruption-rate.csv
  .../analysis/metric-recovery-success-rate.csv
  .../analysis/figure-1-undetected-vs-ambiguity.pdf
  .../analysis/figure-2-duplicates-by-crash-point.pdf
  .../analysis/coverage.json
```

**This table is from the four-execution smoke and is not a result.** The
degenerate intervals are the single-cluster case reporting itself honestly, and
the p-values are large because n = 4. It is here to evidence that the pipeline
produces what D3 asks for, nothing more. The real table is §C.13.

### C.13 The matrix — **PARTIAL**

**83 of 594 planned runs; 830 executions; 28 of 198 applicable cells.** The
collected slice is **exactly tier 1 for five of the six systems**: every crash
point, the `AUTHORITATIVE_READBACK` endpoint, `CALLER_REFERENCE` keying, 30
executions per cell. B4 is 2 of its 15 tier-1 runs.

```
$ python -m experiments.analyze --results-root experiments/results/matrix
{
  "all_runs_used_real_sigkill": true,
  "bootstrap_resamples": 10000,
  "bootstrap_seed": 20260806,
  "cells": 28,
  "crash_points": [
    "after_barrier_before_dispatch",
    "after_intent_before_barrier",
    "after_resolution_before_barrier",
    "after_response_before_resolution",
    "before_intent_write",
    "mid_dispatch"
  ],
  "executions": 830,
  "readback_keyings": [ "CALLER_REFERENCE" ],
  "response_classes": [ "AUTHORITATIVE_READBACK" ],
  "runs": 83,
  "runs_dropped_for_clock_suspension": 5,
  "runs_with_usable_timing": 78,
  "worst_suspension_seconds": 1028.787,
  "systems": [ "AEP_FULL", "B0_NAIVE_RETRY", "B1_LEASE_ONLY",
               "B2_CAS_ONLY", "B3_INTENT_NO_BARRIER", "B4_DURABLE_WORKFLOW" ]
}

Table 1 -- per system, pooled over every cell collected
==============================================================================================
system                  runs   exec  undet.dup           95% CI  known amb.    lost   Fisher p
----------------------------------------------------------------------------------------------
AEP_FULL                  18    180     0.0000   [0.000, 0.000]      0.0000  0.0000         --
B0_NAIVE_RETRY            15    150     0.8200   [0.640, 0.973]      0.0000  0.0133   2.15e-64
B1_LEASE_ONLY             15    150     0.8133   [0.640, 0.953]      0.0000  0.0000   1.60e-63
B2_CAS_ONLY               15    150     0.8067   [0.620, 0.953]      0.0000  0.0067   1.15e-62
B3_INTENT_NO_BARRIER      18    180     0.0000   [0.000, 0.000]      0.0000  0.0000   1.00e+00
B4_DURABLE_WORKFLOW        2     20     0.9500   [0.900, 1.000]      0.0000  0.0000   1.12e-25
==============================================================================================

WARNING: 5 of 83 run(s) show a wall-versus-monotonic divergence above 2.0s
(worst: 1028.787s). The host suspended during them, so every wall-clock
duration they contain includes the suspension. Their COUNTS are unaffected and
are still in the rate metrics; their TIMINGS are excluded from the latency and
throughput aggregates.
```

**Zero disagreements and zero failed runs across all 83.** Every run's log and
its own ground-truth ledger agreed.

**What this shows, stated no more strongly than it is.**

*AEP-full recorded no undetected duplicate in 180 executions across all six
crash points* — 0/180, with the three no-record baselines at 0.81–0.82 and
p < 1e-62 against it. That is the paper's RQ1 result **for one response class
and one keying**, which is what was collected.

*B4 is the sharpest row and the thinnest.* 0.95 at n = 20 — a system with a
durable, `WAITAOF`-acknowledged write-ahead record duplicating on nearly every
crashed execution, because its policy on a scheduled-but-uncompleted activity
is to run it again. It is also **2 runs**, so the point estimate is reported
with its interval and not leant on.

**Three things this table does *not* show, and a reader must not take from it.**

1. **The known-ambiguity rate is 0.0000 for AEP-full, and that is an artifact
   of the slice, not a result.** Tier 1 uses the `AUTHORITATIVE_READBACK`
   endpoint, which can prove both presence *and* absence, so recovery resolved
   every crashed execution definitively and nothing was left ambiguous. The
   roadmap's claim of a *bounded known-ambiguity rate* can only appear under
   `POSITIVE_ONLY_READBACK` and `NO_READBACK` — tiers 2 and 3, **not
   collected**. The paper cannot make that claim from this data.
2. **B3 is identical to AEP-full (0.0000, p = 1.00), and this was predicted
   rather than discovered.** `appendfsync everysec` plus a graceful
   `docker compose restart` does not lose a buffered write, and the matrix as
   launched schedules no Redis fault at all. The ablation currently measures
   the barrier's *cost* and cannot show its *benefit*. See §F3; this is the
   first prerequisite in §H.
3. **RQ3 — overhead — cannot be computed from this slice at all.** With
   `crash_probability = 1.0` every AEP-full and B3 execution is killed before
   it can resolve, so neither emits a single `execution_resolved` record and
   neither has a step-latency sample:

```
latency / throughput (runs with usable clocks only)
--------------------------------------------------------------------------------------------
system                 runs timed dropped  step_ms med   step_ms p95   recov_s med  p95   exec/s
AEP_FULL                 18    16       2            -             -        30.271 39.216 0.2992
B0_NAIVE_RETRY           15    14       1      2048.297      7064.603             -      - 0.3616
B1_LEASE_ONLY            15    15       0     26446.945     31965.017             -      - 0.0692
B2_CAS_ONLY              15    13       2     26448.363     31463.553             -      - 0.0695
B3_INTENT_NO_BARRIER     18    18       0            -             -        30.101 34.465 0.3239
B4_DURABLE_WORKFLOW       2     2       0     27445.532     33297.900             -      - 0.0632
```

   The step latencies that *are* present are the baselines', and B1/B2/B4's
   ≈ 26 s median is almost entirely the **lease wait** — the delay a lease
   imposes on a re-execution while a dead worker's lock expires. That is a
   real and reportable finding (a lease buys a delay, not a prevention), and it
   is not an overhead measurement of AEP. Overhead needs cells with
   `crash_probability = 0`, which the matrix does not currently contain.

**Recovery**, from the collected cells:

```
recovery success rate (denominator = executions that crashed)
  AEP_FULL               after_barrier_before_dispatch       30/30   1.0000
  AEP_FULL               after_intent_before_barrier         30/30   1.0000
  AEP_FULL               after_resolution_before_barrier     30/30   1.0000
  AEP_FULL               after_response_before_resolution    30/30   1.0000
  AEP_FULL               mid_dispatch                        30/30   1.0000
  AEP_FULL               before_intent_write                  0/30   0.0000
  B3_INTENT_NO_BARRIER   (identical at all six)
  B0/B1/B2/B4            0/0 -- no recovery service ran; excluded, not scored
```

150 of 180 crashed AEP-full executions were recovered to a terminal
classification. **The 0/30 at `before_intent_write` is the metric's denominator
misbehaving, not a failure**: a worker killed there never wrote an intent, so
there is nothing to recover, the correct outcome is `NO_RECORD`, and the
execution applied nothing. It is reported as it came out rather than being
redefined after the fact; §G5 is the decision it needs.

Recovery latency is 30.3 s median / 39.2 s p95 for AEP-full and 30.1 s / 34.5 s
for B3, and is dominated by policy: lease TTL (25 s) plus `reconcile_after`
(client timeout 5 s + buffer 15 s). §F4.

**Resume command** — the matrix is resumable and was stopped, not finished:

```
python -m experiments.run_matrix --resume --results-root experiments/results/matrix
```

A run counts as collected only when its `summary.json` exists *and* parses, so
the interrupted run is re-run rather than treated as an empty result. The plan,
including every seed, is in `experiments/results/matrix/matrix-plan.json`.

### C.14 The full suite — Linux, real Redis, zero skips

```
$ bash scripts/wsl_suite.sh
...
aep_core/core/validation.py              11      0   100%
-------------------------------------------------------------------
TOTAL                                  2528    223    91%
Required test coverage of 90% reached. Total coverage: 91.18%
1655 passed, 3 warnings in 72.69s (0:01:12)
```

**1655 passed, 0 failed, 0 skipped**, `aep_core` coverage 91.18 % against the
90 % gate. Run with `AEP_PHASE2_REDIS_INTEGRATION=1` against the compose Redis
7.2 with AOF, so the 31 environment-gated tests that skip on a bare developer
machine — WAITAOF durability, the EVALUATION composition, and the
infrastructure faults — actually executed.

**One honest note about getting here.** The first Linux run of this suite had
three failures, all `The command 'docker' could not be found`: Docker Desktop's
WSL integration was not enabled for this distro, so the Redis-restart tests
could not restart Redis. That is an environment gap and not a code defect —
the same suite is green in CI, which has a real `docker` — and it was closed by
`scripts/wsl_docker_shim.sh` rather than by deselecting the tests. The count
differs from the Windows figure quoted elsewhere (1624 passed + 31 skipped)
for exactly that reason: 1624 + 31 = 1655.

---

## D. Requirement checklist

| # | Requirement | Status | Evidence |
|---|---|---|---|
| D0(i) | Commit and push Session 2 | ✅ | commit `2fefe5e` on `origin/main` |
| D0(i) | Green Linux CI run | ✅ | run 31008255041, three jobs, all `ubuntu-24.04`, all green (§C.1) |
| D0(ii) | Six crash points × 1 run on Linux | ✅ | §C.2; `has_sigkill: True`, worker exit `-9` |
| D0(ii) | EVALUATION mode | ✅ | `RunConfig` cannot represent another mode; every run log carries it |
| D0(ii) | Reconciliation agrees for all six | ✅ | **after failing on the first attempt**, which is reported in full (§C.2) |
| D0(iii) | ≥ 10× the busiest configuration's request rate | ✅ | 187× (§C.3) |
| D1 | B0 naive retry | ✅ | 11 tests, red→green (§C.4) |
| D1 | B1 lease-only | ✅ | red→green (§C.5) |
| D1 | B2 CAS-only | ✅ | red→green (§C.5) |
| D1 | B3 intent without durability barrier | ✅ | red→green (§C.5, §C.6) |
| D1 | Thin variants sharing the connector interface | ✅ | all six use `MockLegacyApiConnector.transmit` and identical wire bytes |
| D1 | …and the same workload driver | ✅ | `workload.py` unchanged; the baselines' tests use it |
| D1 | Failing-then-passing tests proving each label | ✅ | §C.4–§C.8 |
| D1 | B4 durable-workflow style | ✅ | **implemented**, not the permitted fallback (§C.7) |
| D2 | Matrix over the four dimensions | ✅ | 216 cells (§C.10) |
| D2 | 30 repetitions per cell | ✅ | 3 runs × 10 executions; both recorded |
| D2 | Resumable | ✅ | §C.13 carries the resume command; a run counts only with a parseable summary |
| D2 | Seeds recorded | ✅ | derived and printed in the plan *before* the run, echoed in every log |
| D2 | EVALUATION mode on Linux | ✅ | `run_matrix.py` refuses a platform without `SIGKILL` |
| D2 | Plan emitted before launching | ✅ | §C.10; `matrix-plan.json` + `.txt` |
| D3 | All §3.2 metrics | ✅ | §C.13 |
| D3 | Bootstrap 95% CIs | ✅ | run-clustered percentile bootstrap, seed printed |
| D3 | Fisher's exact tests | ✅ | exact integer arithmetic, checked against hand-computed tables |
| D3 | CSV per metric | ✅ | six `metric-*.csv` plus four more |
| D3 | Table 1 | ✅ | §C.13 |
| D3 | PDF figures | ✅ | two |
| D3 | Reads only `events.jsonl` + the oracle ledger | ✅ | source gate, §C.11 |
| D4 | Halt on any AEP-full undetected duplicate | ✅ implemented, **not triggered** | 0/180 (§C.13) |
| D5 | D0–D3 complete, matrix launched resumably, PARTIAL reported | ✅ | §C.13, §E1 |
| Standing | Raw output, not prose | ✅ | §C, `reports/raw/*.txt` |
| Standing | Failing-then-passing for every baseline test | ✅ | §C.4, §C.5, §C.8 |
| Standing | Sections A–H | ✅ | this document |

---

## E. Deviations from the roadmap

**E1. The matrix is partial — 83 of 594 runs — and this is D5's path, not a
shortfall against D2.** The collected slice is not arbitrary: it is tier 1, the
paper's Table 1, complete for five of six systems. D5 requires D0–D3 complete,
a resumable launch and clear PARTIAL labelling; all three are delivered, and
§C.13 states three specific things the slice cannot support.

**E2. "30 repetitions per cell" is 3 runs × 10 executions.** Reasoning in
§C.10; the consequence is that the bootstrap must be, and is, clustered by run.

**E3. Eighteen cells of the cross-product do not exist and are recorded rather
than filled.** §C.10.

**E4. The fault surface is fixed, not a fifth dimension.**
`timeout_probability = 0.15`, `server_error_probability = 0.05`,
`duplicate_response_probability = 0.0`, 2 s delay. The third is zero on purpose
so every ledger duplicate is caller-caused, which keeps the attribution exact
and the at-most-once prediction checkable.

**E5. The supervisor's resume policy is a per-system modelling decision, and it
is the most consequential choice in this session.** With no durable
pre-dispatch record a framework can only re-execute or drop; it cannot
reconcile. B0, B1, B2 and B4 re-execute; B3 and AEP-full do not. Declared in
`SystemDescriptor.resume_policy`, echoed into every run log, asserted by test,
and overridable per run. §F1.

**E6. The baselines send no client reference**, because a pre-dispatch record
is the only thing that could hold a stable identifier across a process death.
Consequence: the keying dimension (tier 3) should move only B3 and AEP-full.

**E7. Development is on Windows; every number is collected on Linux.** Enforced
— both drivers refuse to run without a real `SIGKILL`.

**E8. `crash_probability = 1.0` was chosen to maximise crash signal per run,
and it makes RQ3 uncomputable.** Every AEP-full and B3 execution dies before
resolving, so neither has a step-latency sample (§C.13). Overhead needs cells
with no crash injection; the matrix does not currently contain any. This was
not foreseen when the plan was written, and it is a design error in the matrix
rather than a limitation of the harness.

---

## F. Known weaknesses, shortcuts, and what a hostile reviewer would attack

**F1. The baselines re-execute because I decided they should, and that decision
produces most of their duplicates.** This is the first thing to attack. The
defence: the choice is a printed data structure rather than a buried branch; it
is overridable per run; the roadmap defines B0 as "retry-on-timeout (what most
agent frameworks do today)", and once processes can die "retry" must say
something about crashed steps; and the alternative does not make a baseline
*safe* — it converts duplicates into lost effects, which the harness also
measures. **The honest weakness is that the alternative is implemented and
unmeasured.** §G1.

**F2. B4 is a minimal engine and is not a claim about Temporal.** One activity,
one history, no timers, signals, queues, worker pool, versioning or determinism
checking. And in this report it is **2 runs, 20 executions** — the thinnest row
in Table 1 and the one carrying the most rhetorical weight. Its interval is
reported; it should not be quoted without one.

**F3. B3's ablation cannot show the barrier's benefit under the faults the
matrix injects, and B3 = AEP-full in Table 1 is that, not a null result.**
`appendfsync everysec` means an unbarriered intent may sit in Redis's AOF
buffer for up to a second; `docker compose restart` sends `SIGTERM` and Redis
flushes on shutdown; and the matrix as launched schedules no Redis fault at
all. Losing the buffered write requires `docker kill`. **The harness has no
such fault.** This is the single most important gap in the evaluation.

**F4. The recovery-latency numbers are dominated by policy.** 30.3 s median is
lease TTL (25 s) plus `reconcile_after` (20 s). The paper must report what
dominates the number beside the number.

**F5. The host suspended during 5 of 83 runs, and the timings would have been
silently wrong.** A run recorded 40 s of `time.monotonic()` against a 792 s
span of `time.time()`, with a 774-second gap between two settling polls two
seconds apart: WSL2 stopped `CLOCK_MONOTONIC` while the VM idled and
resynchronised `CLOCK_REALTIME` on resume. It surfaced as a recovery p95 of
780 s against a 30 s median — impossible inside a 52 s run, which is how it was
caught. The analysis now computes wall-span minus monotonic-span per run from
the runner's own records, drops contaminated runs from the timing aggregates
and reports how many it dropped (5, worst 1028.8 s). **Counts are unaffected**
— an execution either duplicated or it did not — so every rate in Table 1
stands. A 20-second probe of the two clocks showed a ratio of 1.004 and would
never have found this; only a run long enough to be suspended did.

**F6. Every run is WSL2, not bare metal.** `SIGKILL` is real and the exit
status is `-9`, so crash fidelity holds. Absolute latency and throughput do
not: the filesystem, the network stack and Docker Desktop's port forwarding are
all in the path, and — per §F5 — the host suspends. **No absolute timing number
from this session should reach the paper.**

**F7. The mock API's own latency is inside every end-to-end number.** D0(iii)
retires the throughput concern (187× headroom); the ≈ 36 ms service latency
under load and the configured 2 s delay are still there. §3.2's overhead
comparison is between systems sharing a provider, not an absolute measurement.

**F8. The known-ambiguity rate is 0.0000 everywhere in Table 1, and the
roadmap's headline claim about it is therefore unevidenced.** Tier 1's endpoint
can prove absence, so recovery resolved everything and nothing was left
ambiguous. AEP's claim to convert silent failures into *declared* ones needs
`POSITIVE_ONLY_READBACK` and `NO_READBACK`, which are tiers 2 and 3 and were
not collected. A reviewer reading only Table 1 would see a protocol that never
declares ambiguity — which is true of this slice and false of the protocol.

**F9. `analyze.py` duplicates the outcome vocabulary rather than importing it.**
Deliberate — it pins the analysis to the log format — but it is a duplication
held in step by exactly one test.

**F10. Reconciliation is system-aware, which weakens it on baseline runs.** A
no-record-with-an-effect is a P2 violation for AEP-full and B3 and a measured
lost effect for B0/B1/B2. Correct, but it means a harness defect that only
manifested on a baseline run has fewer ways to be caught.

**F11. `recovery_success_rate` is 0.0000 at `before_intent_write` for both
recovering systems, and the metric is at fault, not the protocol.** A worker
killed there wrote no intent, so there is nothing to recover and the correct
outcome is `NO_RECORD`; the denominator counts it as a crashed execution
anyway. It is reported as it came out rather than redefined after seeing it.
§G5.

**F12. The 18 inapplicable cells rest on my reading of what "the same moment"
means across two protocols.** Stated and tested, but still a judgement.

**F13. The lease wait is a modelling choice with a measured cost and no
sensitivity analysis.** Bounded at `lock_ttl + 5 s`; recorded per execution;
never varied. It is most of B1/B2/B4's ≈ 26 s step latency.

**F14. B0's 0.0133 and B2's 0.0067 lost-effect rates are two and one executions
respectively.** Real, and far too small to characterise.

---

## G. Open questions needing a human/architect decision

1. **Collect the drop-on-crash variant of B0/B1/B2?** (§F1.) It converts their
   duplicates into lost effects and pre-empts the likeliest objection to the
   whole comparison. Recommendation: tier 1 only, as a robustness column.

2. **Add a hard Redis kill before any B3-versus-AEP claim?** (§F3.) Without it
   the barrier's benefit is unobservable and only its cost is measured.
   Recommendation: yes, and it should block RQ2 rather than the matrix — it is
   a new fault, not a new dimension.

3. **Add crash-free cells so RQ3 becomes computable?** (§E8.) At
   `crash_probability = 1.0` neither AEP-full nor B3 completes an execution, so
   there is no step-latency sample for either. Recommendation: one
   `crash_probability = 0.0` cell per system per response class — 18 cells,
   cheap, and it is the only way the overhead column gets numbers.

4. **Session 2's G1 and G2 are still open.** `IntentRecoveryService` still
   validates a barrier only if it offers `validate_startup`; the partition and
   restart still run after all workers finish, and the matrix uses neither.

5. **Should `recovery_success_rate`'s denominator be "crashed" or "crashed with
   a durable intent"?** (§F11.) The second is the quantity the paper means. The
   first is what is implemented, and changing it after seeing the numbers is a
   decision that should be made deliberately and recorded, not slipped in.

6. **Is the headline duplicate rate per execution or per application?** Both
   are computed; Table 1 uses per execution because it is a rate over the
   sampling unit and the CI and Fisher test apply to it cleanly.

---

## H. Recommended next phase and its prerequisites

**Next: close the three gaps that change what a cell means, then resume the
matrix.** Finishing the remaining 511 runs needs wall time, not work — but
resuming *before* the following would spend six hours collecting cells with the
same blind spots:

1. **Add the hard-Redis-kill fault** (§F3, §G2). Until it exists B3 is an
   ablation whose benefit cannot appear, and Table 1's B3 row invites exactly
   the wrong conclusion.
2. **Add crash-free cells** (§E8, §G3). Without them the paper has no overhead
   column at all.
3. **Decide §G1** before tier 2, because interleaving is cheaper than bolting
   on.
4. **Collect tiers 2 and 3**, which is where the known-ambiguity claim lives
   (§F8). `NO_READBACK` is the configuration AEP exists for, and it has not
   been run once.
5. **Move the collection off WSL2, or disable host suspension** (§F5, §F6). The
   counts survived; the timings did not, and 5 runs in 83 were affected.

**What the next session can rely on from this one:**

- Six systems behind one interface, one workload and one oracle, each system's
  claims readable from a table that tests check against the implementations.
- A matrix that states its plan, seeds and cost before running, refuses hosts
  where crashes would not be real crashes, records inapplicable cells instead
  of filling them, halts on a D4 finding, and resumes.
- An analysis that cannot reach the system under test, and that now detects a
  suspended host rather than reporting its suspension as latency.
- Statistics implemented against their definitions and checked against
  hand-computed values.
- Four defects fixed that the unit suite had not found — two provider-isolation
  defects that would have made every recorded seed a fiction, and two that made
  baselines look better than they are.
- **0 undetected duplicates in 180 AEP-full executions across all six crash
  points**, against 0.81–0.82 for the three no-record baselines, p < 1e-62.
