# Phase 40 — paired seeding implemented, and a second leak found

**No live call.** Cumulative live spend unchanged at **USD 0.00359020**. Two
stub collections here, 24 and 12 calls, **USD 0.00** each.

Amendment 8 is written, implemented and demonstrated. **Stage 100 is not run**,
because the end-to-end stub run surfaced a second arm-asymmetric path into
`last_outcome` that has nothing to do with seeding. §6 has it.

---

## 1. How the provider draws each fault

### 1.1 Sequential, three draws per mutation

`MockLegacyAPI.__init__` holds one generator, `random.Random(config.seed)`, and
`draw_faults` consumes from it three times per mutation, unconditionally and in
a fixed order:

```python
server_error = self._random.random() < faults.server_error_probability
timeout      = self._random.random() < faults.timeout_probability
duplicate    = self._random.random() < faults.duplicate_response_probability
```

`draw_delay` consumes **nothing** under the pre-registered `CONSTANT`
distribution, and the code says why: *"a run with delays disabled must produce
the same stream of fault decisions as one with delays enabled."*

**Read-backs consume nothing.** `draw_faults` and `draw_delay` are called from
exactly one place — `service.py`, inside the mutation route. The read-back
routes never touch the generator. Worth stating because read-backs are the
obvious suspect and are not the problem.

### 1.2 The two arms send different numbers of mutations

From the provider's own ledgers and run logs:

| collection | `AEP_FULL` | `B0_NAIVE_RETRY` |
|---|---|---|
| stage 30 | 1 | 1 |
| stub a6 | **0** | **4** |
| stub rpc2, rep 0 | **0** | **4** |
| stub rpc2, rep 1 | **0** | **3** |

And the harness's own code documents the mechanism, in `REGIME_NO_CRASH`'s
comment: *"At `crash_probability = 1.0` neither AEP-full nor B3 completes an
execution."* AEP transmits and is killed in flight; B0 completes.

### 1.3 So a shared seed alone would still desynchronise

At three draws per mutation, two arms sharing one seed stay aligned only while
they present **the same mutations in the same order**. After the first
divergence — one withheld dispatch, one extra retry, one crash landing on the
other side of the request — arm A's *n*-th mutation meets the fault drawn for
arm B's *m*-th, *m ≠ n*, and every mutation after it is misaligned too.

`test_an_extra_request_on_one_arm_cannot_shift_the_other` is that case, made
explicit.

### 1.4 Where arm identity entered

| # | site | how |
|---|---|---|
| 1 | `run_matrix.cell_seed` | hashes `cell.key`, whose first component is `system.value` |
| 2 | `Cell.slug` → `run_id` | `f"{system.value.lower()}-…"` |
| 3 | `workload._stream(run_id, seed, …)` | execution ids, targets, amounts, crash selection — arm-specific through **both** |
| 4 | `provider_seed=entry["seed"]` | the mock's sequential generator |
| 5 | `config_digest` | differs per arm because `system` is a `RunConfig` field — an output, feeding nothing |

---

## 2. Amendment 8

`prompts/phase-40-amendment-8-paired-seeding-2026-09-22.md`, committed before
the code. Names the fault as `55807d6` did, cites amendment 6 §8's leak
category, and records that **the matrix is not affected** — per-cell seeds are
correct there, where each cell is its own condition 30 repetitions deep.

Stages 10 and 30 stay in the record as **unpaired**; their instrument criteria
stand because C1–C3, C4′ and amendment 6 §9's clauses 2 and 3 are properties of
the instrument and none depends on which faults were injected. **Stage 30 does
not need re-running.** Stage 100 is the first paired stage.

---

## 3. Implementation

Agent branch only. The scripted branch and the matrix are untouched.

| file | change |
|---|---|
| `harness/workload.py` | `pairing_identity()` and `PAIR_ID_ENV` / `PAIR_SEED_ENV`; `plan_workload` keys its named streams on the pair identity when set |
| `mock_api/config.py` | `MockApiConfig.pair_seed`, in the digest **only when set**; the strict loader accepts and type-checks it |
| `mock_api/service.py` | `_paired_uniforms`, `dispatch_ordinal`, keyed `draw_faults`/`draw_delay`, a separate auxiliary generator |
| `mock_api/supervisor.py`, `harness/orchestrate.py` | `pair_seed` threaded through |
| `run_matrix.py` | `pair_key`, `pair_identity`, `_paired_for`; applied only when the agent-interactive branch is on |

**Nothing collected moves.** `pair_seed` is absent from `_body()` when unset, so
every configuration written before amendment 8 produces a byte-identical digest;
the pair identity travels in the environment, so `RunConfig` — and therefore
`config_digest` for all 432 runs — is untouched.
`tests/test_scripted_plan_is_frozen.py` is **59 passed**.

**A half-applied pairing is refused.** One environment variable without the
other raises, and the agent branch resuming a plan that predates amendment 8
exits rather than collecting something that would be recorded as paired without
being paired.

### 3.1 Tests — `tests/test_paired_seeding.py`, 29 passed

Including the known-positives:

| known-positive | what it shows |
|---|---|
| `test_putting_the_system_name_back_into_the_pairing_breaks_it` | give the arms arm-specific pair ids and the workloads diverge again — so the pairing tests are not vacuous |
| `test_an_arm_specific_pair_seed_also_breaks_it` | the same through the seed rather than the id |
| `test_unpaired_the_two_arms_get_different_workloads` | the archives' state, pinned |
| `test_the_arm_name_is_what_made_the_seeds_differ` | the finding itself |

and the case a shared seed could not have handled:

> **`test_an_extra_request_on_one_arm_cannot_shift_the_other`** — arm B sends
> two extra mutations between two that both arms share. Under the sequential
> draw that shifts every later fault by three. Keyed to the request, the shared
> second mutation meets the identical fault.

Plus: the ordinal is per-fingerprint not global; the keyed draw ignores the
sequential generator entirely; the unpaired path is still sequential; different
repetitions still get different schedules; and the marginal probabilities are
unchanged (20 000 draws, server error 0.04–0.06, timeout 0.14–0.16).

---

## 4. The stub runs — side by side

### 4.1 `phase40-stub-paired-2026-09-22`, p(crash)=1.0, 4 runs, 24 calls, USD 0.00

**The workload is paired, exactly.**

| rep | ex | AEP amount | B0 amount | amounts | targets |
|---|---|---|---|---|---|
| 0 | 0 | 986162 | 986162 | ✓ | ✓ |
| 0 | 1 | 419764 | 419764 | ✓ | ✓ |
| 0 | 2 | 434899 | 434899 | ✓ | ✓ |
| 1 | 0 | 975014 | 975014 | ✓ | ✓ |
| 1 | 1 | 825597 | 825597 | ✓ | ✓ |
| 1 | 2 | 286303 | 286303 | ✓ | ✓ |

`pair_seed` matches across arms in both repetitions (1108363607 and
1555905736), while the per-arm `seed` still differs — which is the matrix's
rule, left alone.

The full dispatch sequence is identical too:
`[(0, 986162), (0, 986162), (1, 419764), (2, 434899), (2, 434899)]` on **both**
arms.

**But the faults cannot be compared in this regime**, because AEP delivers
nothing to the provider: its ledger is empty in both runs while B0's holds 3
and 5 records. That is the regime, not the pairing — see §1.2.

### 4.2 `phase40-stub-paired-nocrash-2026-09-22`, no crash armed, 4 runs, 12 calls, USD 0.00

Run because §4.1 cannot show the faults match. With no crash point armed both
arms complete every dispatch, so every mutation reaches the fault draw.

**Workload paired** — 226215 / 52744 / 991224 in rep 0 and 666377 / 330968 /
739158 in rep 1, identical on both arms, same targets.

**And the faults match, per execution:**

| rep | ex | dec | amount | `AEP_FULL` | `B0_NAIVE_RETRY` | match |
|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 226215 | acknowledged | acknowledged | **yes** |
| 0 | 1 | 0 | 52744 | acknowledged | acknowledged | **yes** |
| 0 | 2 | 0 | 991224 | acknowledged | acknowledged | **yes** |
| 1 | 0 | 0 | 666377 | acknowledged | acknowledged | **yes** |
| 1 | 1 | 0 | 330968 | acknowledged | acknowledged | **yes** |
| 1 | 2 | 0 | 739158 | acknowledged | acknowledged | **yes** |

**6 of 6 comparable slots agree.** The provider's own logs show the same:
rep 1 records `[applied, refused(503), applied]` on **AEP** and
`[applied, refused(503), applied, applied]` on B0 — the injected 503 landed on
**both** arms, where in every unpaired collection every 503 landed on B0 and
none on AEP.

**Stated honestly:** all six comparable observations are `acknowledged`, so
this table shows agreement rather than agreement *under an injected fault*. The
per-request keying under divergent traffic is shown by
`test_an_extra_request_on_one_arm_cannot_shift_the_other` instead, and the 503
reaching both arms is shown by the provider logs above rather than by the
observation table.

---

## 5. Where this leaves the two collections

| | paired workload | paired faults | comparable |
|---|---|---|---|
| p(crash)=1.0 | **yes** | not demonstrable — AEP delivers nothing | no |
| no crash armed | **yes** | **yes**, 6 of 6 | yes |

---

## 6. A second leak, found by the end-to-end run — **stage 100 is not run**

§4.1's observation table did not agree, and the reason is not seeding.

| rep | ex | dec | `AEP_FULL` | `B0_NAIVE_RETRY` |
|---|---|---|---|---|
| 0 | 0 | 1 | **server_error** | acknowledged |
| 0 | 2 | 1 | **server_error** | acknowledged |
| 1 | 0 | 1 | **server_error** | acknowledged |
| 1 | 2 | 1 | **server_error** | acknowledged |

Four of four, on the agent's re-dispatch after a crash. **AEP's provider ledger
is empty**, so no 503 was ever injected for it. The event log says what
happened:

```
planner_redispatched   {execution_index: 0, decision_index: 1,
                        last_outcome: unknown_process_died}
execution_started      {execution_index: 0, amount_minor: 986162}
execution_failed       {execution_index: 0, failure_class: LockAcquisitionError}
```

**`LockAcquisitionError`.** The re-dispatch never reached the provider: AEP
could not take the execution lease, because the dead worker's lease had not yet
expired or recovery held it. `classify_outcome` maps any non-timeout exception
to `server_error`, so the agent was told

> *"the provider returned a server error before applying it."*

which is **false** — the provider never saw the request.

### 6.1 Why this is a leak under amendment 6 §8

`SYSTEMS["AEP_FULL"].uses_lease` is `True`; `SYSTEMS["B0_NAIVE_RETRY"].uses_lease`
is **`False`**. B0 takes no lease, so `LockAcquisitionError` is **structurally
impossible** on it.

Amendment 6 §6's standing constraint is not merely that the vocabulary match:

> *"Every value must be reachable on both arms, by the same path."*

`server_error` is reachable on B0 only via a provider 503. On AEP it is
reachable by that path **and** by a local lease failure that B0 has no analogue
for — and in the crashed regime, which is the regime the experiment runs in,
the local path is the one that fires. That is an arm-asymmetric path into
`last_outcome`, which is the leak category amendment 6 §8 lists.

It also tells the agent something untrue about the provider, which is a second
problem of its own: the agent's re-decision is being made on a false premise.

### 6.2 What follows

**Stage 100 is not run.** Running it now would collect a cross-arm comparison
in which one arm's re-dispatch is systematically reported as a provider error
that never happened.

This is a **named leak**, which is what amendment 6 §8 requires of any further
amendment. **No remedy is proposed here** — the same discipline
`reports/phase-report-40-fault-symmetry-2026-09-22.md` §5 applied: naming the
fault is what a report does, choosing the remedy is the author's, and proposing
one here would be the shortcut the report is about.

**It does not invalidate amendment 8 or its implementation.** The seeding leak
was real, is fixed, and is demonstrated fixed. This is a different leak in a
different place, and it was found *because* pairing removed the noise that hid
it: with the workloads identical, the remaining difference had nowhere else to
come from.

---

## 7. The stage-100 command — prepared, NOT run, and NOT clear to run

Unchanged from `6ec7c53` §7 except for the trailing run count:

| | value |
|---|---|
| `AEP_PLANNER_PER_RUN_CALLS` | 20 |
| `AEP_PLANNER_PER_COLLECTION_CALLS` | 100 |
| `AEP_PLANNER_PER_COLLECTION_USD` | 0.20 |
| runs-per-cell | 2 (4 runs) |

```bash
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -u root -e bash -c '
export PATH=/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cd /mnt/d/personal/AEP/Research-paper-AEP

export AEP_HARNESS_SUSPEND_DISABLED=1
export AEP_PLANNER_LOOP=interactive
export AEP_PLANNER_PER_RUN_CALLS=20
export AEP_PLANNER_PER_COLLECTION_CALLS=100
export AEP_PLANNER_PER_COLLECTION_USD=0.20

bash scripts/run_phase40_live.sh \
    /mnt/d/personal/AEP/stub-results/phase40-live-100call-interactive-<date> 2
'
```

**Cost**, on stage 30's measured 405.8 prompt and 113.3 output tokens per call
at 0.00021712 per call:

| | |
|---|---|
| expected, 24 calls | ≈ **USD 0.0052** |
| maximum, 100 calls at the current price | **USD 0.16288** |
| maximum at the stale price | USD 0.81440 |
| cumulative afterwards | ≈ 0.0088 expected, ≤ 0.1665 worst case |

**Do not run it until §6 is ruled on.** The command is correct and the caps are
right; the instrument is not yet clear.

---

## 8. Verification

| | |
|---|---|
| full suite | **2 485 passed, 34 skipped** |
| `tests/test_paired_seeding.py` | **29 passed** |
| `tests/test_scripted_plan_is_frozen.py` | **59 passed** |
| `tests/test_last_outcome_is_arm_neutral.py` | **12 passed** |
| `scripts/check_paper_numbers.py` | 43 passed, 0 failed |
| `scripts/check_line_endings.py` | clean |
| builds | all four, supplementaries first; main **24 pp**, main-anon 23 pp, supplementary 7 pp, supplementary-anon 7 pp; zero `??` |
| live calls | **none**; cumulative USD 0.00359020 |
