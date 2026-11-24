# Phase 40 — amendment 6: the same payment, and whose decision it is

**No live call.** Cumulative live spend unchanged at **USD 0.00228720**. The one
collection here is stub mode: 12 calls, **USD 0.00**.

---

## 1. Who decides, established from the code and the live run directory

Asked before anything was written, and answered from `runner.py`,
`contract.py` and the stage-10 collection — not from the docs.

### 1.1 The second dispatch in the live B0 run was the harness's

`experiments/harness/runner.py`, the resume branch:

```python
if config.effective_resume_policy is ResumePolicy.REEXECUTE_CRASHED:
    # The supervisor runs the crashed execution again. With no durable
    # pre-dispatch record there is no third option ... and this is the branch
    # that turns a crash into a duplicated external effect.
    from_index = last_started
```

In `phase40-live-10call-interactive-2026-09-21/b0_naive_retry-…-r0/`:

```
events-worker-0-attempt-1.jsonl   worker_started from_index=0
                                  execution_started ex0 amount=775463
                                  crash_injected
events-worker-0-attempt-2.jsonl   worker_started from_index=0
                                  execution_started ex0 amount=775463
                                  execution_resolved
planner-transcript.jsonl          ONE entry for step 0
```

Two dispatches, one decision. **The planner was never asked.** The supervisor
set `from_index` back and the driver replayed the recorded decision.

### 1.2 In the interactive loop as it stood, nobody asked the agent — on either arm

| | `resume_policy` | `redispatches_on_replay` | after a crash |
|---|---|---|---|
| `B0_NAIVE_RETRY` | `REEXECUTE_CRASHED` | `True` | the **supervisor** re-dispatches |
| `AEP_FULL` | `NEXT_EXECUTION` | `False` | the worker **never** re-dispatches |

The two arms differed in **who decides**, and on neither was it the agent.

### 1.3 Stated plainly

**Any undetected duplicate collected so far is harness-caused and says nothing
about the agent.** It is produced by `runner.py`'s re-entry together with
`redispatches_on_replay=True`, with no agent involvement; the code's own
comment says as much. No live collection has recorded one, so nothing already
reported is withdrawn — but had one been recorded it would have been evidence
about `ResumePolicy`, not about an LLM.

### 1.4 A consequence the arm-neutrality test could not see

Under `AEP_FULL` a respawn resumed at `last_started + 1`, so the driver's
`_pending = UNKNOWN_PROCESS_DIED if from_index > 0` fired. Under
`B0_NAIVE_RETRY` it resumed at `last_started`, the crashed payment was
re-dispatched from the replayed decision, and the agent was told
**`acknowledged`** — the fate of a dispatch it did not choose. Both are visible
in stage 10's two turn-2 prompts.

So `unknown_process_died` was reachable on AEP and effectively unreachable on
B0. `tests/test_last_outcome_is_arm_neutral.py` tests `classify_outcome`'s
vocabulary and mapping, which are neutral; reachability was decided by the loop
around it.

---

## 2. Amendment 6

`prompts/phase-40-amendment-6-same-payment-redecision-2026-09-21.md`, committed
before the code.

**The defect, named:** two individually correct amendments combine into a
design that cannot ask its own question. Amendment 3 made turns independent
payments; amendment 4 made `last_outcome` report the previous call; together
the agent re-decides about a *different* payment from the one whose outcome was
ambiguous. An instrument-validity finding from a stage that **passed**, not a
change made to reach a result.

**The semantics.** After `acknowledged`, the next payment. After `timed_out`,
`server_error` or `unknown_process_died`, **the same payment** — same account,
same harness-assigned amount. A new payment only after an acknowledgement, or
after the agent explicitly declines to send again. At most one re-decision per
execution, because the harness crashes each execution at most once and because
"how many times does it retry" is a rate §2 forbids.

**The crashed decision is not replayed.** Decided *and observed* replays with
no call; decided and **never observed** is the crashed one and earns a
re-decision. Observations live in `planner-observations.jsonl` — never
reconstructed from `events.jsonl`, amendment 4 §3 without exception.

**Agent-owned re-dispatch, both arms identically**, on the agent-interactive
branch only. No protocol implementation is touched: `aep_core`'s ledger,
barrier, fencing and recovery are untouched and `SystemDescriptor` is not
edited. What moves is who is asked.

**Pre-committed:** this is the **last structural amendment** to phase 40. If
agents never re-dispatch, that is F1 and is reported as one. Only an instrument
fault — a crash, a leak, or a malformed path — justifies a further amendment,
and it must name which.

---

## 3. The per-run cap, and a constraint it exposed

`(T × D + L) × A × W` = `(3 × 2 + 4) × 2 × 1` = **20**, down from 28.

**At two workers the same formula gives 40, above §3's pre-registered ceiling
of 36**, which `stage_caps` refuses. Amendment 6 does not amend that ceiling,
so **the interactive design is pinned to one worker** until it is. Recorded now
rather than discovered when a launch is refused. Every live stage has used
`--workers 1`, so nothing changes in practice.

Against `MAX_ATTEMPTS_PER_WORKER = 64`: 64 lifetimes × 2 attempts × 1 worker =
**128** calls in one run without a per-run cap. At 20 the cap stops it **6.4×**
sooner.

---

## 4. The stub-interactive run: both choices, both arms, USD 0.00

`AEP/stub-results/phase40-stub-interactive-a6-2026-09-21/`, end to end against
Docker and Redis under WSL2. 12 calls, 0 voided, `rc=0`.

### 4.1 Both choices were exercised on both arms

| system | "dispatch again" | "do not" |
|---|---|---|
| `AEP_FULL` | **2** | **1** |
| `B0_NAIVE_RETRY` | **2** | **1** |

Every re-decision carried `last_outcome=unknown_process_died`, and the wording
was **byte-identical across the two arms** — the §1.4 asymmetry is gone.

```
resume_for_agent_redecision = 3     (both arms)
resume_reexecuting_crashed  = 0     (both arms)
```

**The supervisor no longer decides on either arm.**

### 4.2 What each system did in each case

`AEP_FULL` — 6 decisions, 3 crashes:

| step | d0 | d1 | dispatches | amount |
|---|---|---|---|---|
| 0 | call | **call** (re-dispatch) | 2 | 167608 both |
| 1 | call | **stop** (declined) | 1 | 896603 |
| 2 | call | **call** (re-dispatch) | 2 | 41282 both |

Outcome: **3 declared ambiguities**, 0 undetected duplicates, 0 applied rows,
`agrees=true`, `settled=false`. The agent chose to send again twice and AEP
fail-closed both times: nothing applied, everything declared.

`B0_NAIVE_RETRY` — 6 decisions, 3 crashes, the **same three agent choices**:

| step | d0 | d1 | dispatches | amount |
|---|---|---|---|---|
| 0 | call | **call** (re-dispatch) | 2 | 775463 both |
| 1 | call | **stop** (declined) | 1 | 610310 |
| 2 | call | **call** (re-dispatch) | 2 | 473905 both |

Outcome: 0 declared ambiguities, **2 oracle applied rows**, 0 undetected
duplicates, `agrees=true`, `settled=true`.

**Same caller, same choices, two protocols, different records.** That is the
comparison §2 describes and the first time the instrument has produced it. The
re-dispatched amount equals the initial amount in every case, so amendment 3's
guard never fired.

### 4.3 What these numbers are not

Stub mode. §2 forbids reporting any of it as a rate, and this is not a result
in any direction — the planner is a canned script, not an agent. B0 recorded no
undetected duplicate here because `mid_dispatch` crashes before the effect
applies, so the re-dispatch applied once. Whether a real agent re-dispatches at
all is exactly the open question, and §8's F1 covers the answer if it does not.

---

## 5. Implementation

The scripted branch is **character-for-character unchanged**; the planned agent
branch keeps the descriptor's resume policy.

| file | change |
|---|---|
| `planner.py` | `decision_index` on `Observation`, `TranscriptEntry`, the reservation key and `replay_index`; schema `/3` → `/4` |
| `agent_loop.py` | `MAX_DECISIONS_PER_EXECUTION`, `NON_ACKNOWLEDGED`, `ObservationLog`, the rewritten `InteractiveDriver`, a decision-aware stub |
| `live_planner.py` | `REDECISION` and `build_redecision_prompt` |
| `runner.py` | `resume_from_index` and `_agent_owns_redispatch` |

**Why `decision_index` had to reach the reservation key.** Two decisions for
one execution would otherwise key to the same reservation; the journal's
first-write-wins would drop the second, and a paid call would go uncounted —
the exact failure the journal exists to prevent. The replay slot would also
have held the wrong decision.

### 5.1 Tests

| file | count |
|---|---|
| `tests/test_same_payment_redecision.py` (new) | 14 |
| `tests/test_redecision_prompt_is_neutral.py` (new) | 15 |
| `tests/test_agent_owns_redispatch.py` (new) | 15 |
| `tests/test_last_outcome_is_arm_neutral.py` (extended) | 12 |
| `tests/test_interactive_loop.py` | 14 |
| `tests/test_scripted_plan_is_frozen.py` | **59** |

Prompt neutrality is read off the text: both options in parallel form, the
negation costing exactly seven characters and nothing else, no steering
vocabulary, no default, the shared facts stated once above both. Known-positives
show each check can fail.

### 5.2 Five amendment-4 tests were rewritten, and why

They encoded behaviour amendment 6 deliberately changes. Each keeps the
property it protected:

- **`test_replay_reuses_the_decision_and_makes_no_new_call`** asserted that a
  replayed decision is *yielded again* — which is how the supervisor's
  re-dispatch happened. It now asserts no new call **and no re-dispatch**.
- **Two `_pending` tests** asserted an in-memory sentinel. The unknown is now
  the *absence* of a line in `planner-observations.jsonl`, which the next
  lifetime can actually read; the tests assert that instead.
- **Two fixture planners** were positional and handed a re-decision the *next*
  payment's amount, which amendment 3's guard correctly voided. The guard was
  right; the fixtures are now keyed by `(step, decision)`.

### 5.3 One check I got wrong

My own neutrality test initially banned `idempotent` everywhere. It fired on
`SYSTEM`'s *"a legacy provider that is not idempotent"* — which has been in the
prompt since amendment 2 and is a fact a real caller has. The test was wrong,
not the prompt: `duplicate` names the metric and stays banned; `idempotent`
describes the provider and is now explicitly exempt, with the reason in the
test.

---

## 6. Stage 30 under the new semantics

§6's criterion needs one word of precision. Stage 30 must show, in at least one
crashed run:

1. every decision **made and observed** replayed with no model call;
2. **exactly one new call** about the crashed payment — the re-decision, with
   `last_outcome: unknown_process_died`, same account, same amount;
3. **that re-decision is the agent's** — no `execution_started` for a
   re-dispatch the planner was not asked about.

A respawn that silently re-dispatches fails clause 3 while satisfying clause 1,
and that is the difference between what stage 10 recorded and what stage 30
must. Void rate recorded as before.

The stub run satisfies all three at zero cost.

---

## 7. The stage-30 command, prepared and NOT run

### 7.1 Caps

| | value | derivation |
|---|---|---|
| `AEP_PLANNER_PER_RUN_CALLS` | **20** | amendment 6 §7, `(3×2 + 4) × 2 × 1` |
| `AEP_PLANNER_PER_COLLECTION_CALLS` | **30** | the stage is its call budget |
| `AEP_PLANNER_PER_COLLECTION_USD` | **0.06** | above the `30 × 0.0016288 = 0.048864` the call cap permits, so the call cap binds first and the USD ceiling stays a backstop |

### 7.2 Expected and maximum spend

Measured: the initial prompt is 1 238 characters and the re-decision prompt
1 622 — a ratio of 1.31. Calibrating against stage 10's live counts (372–393
tokens for a prompt of this size) gives ≈ 390 tokens initial and ≈ 487
re-decision, against a 2 000-token bound. Outputs ran 65–130 tokens live.

The stub run took **6 decisions per run** — 3 initial, 3 re-decisions — so for
the launcher's two runs:

```
prompt   2 × (3×390 + 3×487)  =  5 262 tokens  × 0.20/10⁶ = 0.00105
output   12 × ~100            =  1 200 tokens  × 1.20/10⁶ = 0.00144
                                                 expected ≈ USD 0.0025
```

| | |
|---|---|
| **expected** | **≈ USD 0.0025** (about 12 of the 30 calls) |
| maximum at the current price | `30 × 0.0016288` = **USD 0.048864** |
| maximum at the stale price | `30 × 0.008144` = **USD 0.24432** |
| cumulative afterwards | ≈ **USD 0.0048** expected, ≤ **USD 0.0511** worst case |

Against §3's USD 20 ceiling and §9's USD 10 threshold.

### 7.3 The command

```bash
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -u root -e bash -c '
export PATH=/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cd /mnt/d/personal/AEP/Research-paper-AEP

export AEP_HARNESS_SUSPEND_DISABLED=1
export AEP_PLANNER_LOOP=interactive
export AEP_PLANNER_PER_RUN_CALLS=20
export AEP_PLANNER_PER_COLLECTION_CALLS=30
export AEP_PLANNER_PER_COLLECTION_USD=0.06

bash scripts/run_phase40_live.sh \
    /mnt/d/personal/AEP/stub-results/phase40-live-30call-interactive-<date>
'
```

Prerequisites, all verified today: both containers healthy under WSL2's native
Docker, `aep:test-instance-marker` set in DB 15, port 8099 free, `.env` ACL
restricted to one account.

**One thing the author should know before running it.** The launcher hardcodes
`--runs-per-cell 1`, so the stage collects **two runs and about twelve calls**
against a thirty-call budget. Collecting four runs would use ~24 and would need
a launcher change, which has **not** been made speculatively. Either is
defensible; it is a decision, not a defect.

**This command has not been run. No cap is raised by this report and stage 30
is not opened.**

---

## 8. Verification

| | |
|---|---|
| full suite | **2 438 passed, 34 skipped** |
| `tests/test_scripted_plan_is_frozen.py` | **59 passed** |
| `tests/test_last_outcome_is_arm_neutral.py` | **12 passed** |
| `tests/test_interactive_loop.py` | **14 passed** |
| `scripts/check_paper_numbers.py` | 43 passed, 0 failed |
| `scripts/check_line_endings.py` | clean |
| builds | all four, supplementaries first; main **24 pp**, main-anon 23 pp, supplementary 7 pp, supplementary-anon 7 pp; zero `??` |
| live calls | **none**; cumulative USD 0.00228720 |
