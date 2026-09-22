# Phase 40 — amendment 9 implemented: the transmission boundary

**No live call.** Cumulative live spend unchanged at **USD 0.00359020**. Two
stub collections, 24 and 12 calls, **USD 0.00** each.

The author's ruling — Option 3 **without** Option 1 — is implemented.
`AEP_FULL`'s lock-acquisition policy is unchanged, no protocol code is touched,
and the claim that AEP refuses a re-dispatch anyway after lease expiry is
**tested rather than asserted**.

---

## 1. The nine points, classified

Amendment 9 §3. The boundary is `docs/31`'s `provider_request_transmitted` —
*"the last observable point at which no provider byte can have left"* — which
is an instruction boundary rather than an approximation, and is exactly the
distinction the rule needs.

| # | point | pre / post | code path |
|---|---|---|---|
| 1 | the whole exception branch of `classify_outcome` | **both** — the subject of the rule | `agent_loop.classify_outcome` |
| 2 | lease acquisition, 3 attempts exhausted | **pre** | `intent_workflow._acquire_with_jitter`, before `create_intent` |
| 2b | lease failure via intent CAS `-3` / state write `-3` | **pre** on creation, **post** on resolution — §2 | `intents` CAS, `storage` write |
| 3 | intent-ledger invariants (uniqueness, attempt, append-only) | **pre**; the resolution transitions the *same* intent and cannot breach uniqueness | `intents._ledger_keys_and_uniqueness`, CAS `-5` |
| 4 | fenced-write refusals | **pre** on seeding, **post** on resolution — §2 | `storage.save_state` |
| 5 | durability-barrier failure | **pre** | `_confirm_barrier`, before `AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION` |
| 6 | request-binding / vault rejection | **pre** | `binding_service.prepare` |
| 7 | recovery resolving an unfinished execution | **neither** — reaches the oracle, not `last_outcome` | `intent_recovery` |
| 8 | resume policy | **neither** — closed by amendment 6 §4.3 | `runner.resume_from_index` |
| 9 | the provider's fault stream | **post**, and symmetric — closed by amendment 8 | `mock_api.service.draw_faults` |

**Everything that can refuse an AEP dispatch before any byte leaves is
pre-transmission**, and now produces no observation.

## 2. The post-transmission points: flagged, and not reachable

Points 2b and 4 have a post-transmission form — `mutate` returns and the
resolution write at `intent_workflow.py:628` then fails because the lease
expired underneath it. B0 has no such step.

**Flagged rather than mapped, as instructed. And not reachable**, with the
numbers:

| | |
|---|---|
| `lock_ttl_seconds` | 25 |
| `buffer_margin_seconds` | 15 |
| `client_timeout_seconds` | 5 |
| Timeout Invariant `T_client ≤ ttl − buffer` | `5 ≤ 10` ✓ |
| slack before the lease could expire mid-execution | **20 s** |

`locks.py` **enforces** this rather than documenting it — it raises if the
buffer is under 15, if the TTL is not greater than the buffer, or if the client
deadline exceeds `ttl − buffer`. **No mapping was invented**, and
`test_the_timeout_invariant_holds_for_the_phase_40_configuration` fails if
those numbers ever change, rather than the case silently opening.

## 3. The wording checks

**One clause was false and is fixed.** Before:

```
Your previous call: your process then stopped. You do not know whether it was
sent, whether it arrived, or whether it was applied.
```

After an absorbed re-dispatch the agent *has* made a more recent decision, and
that decision's process did **not** stop — it was refused before transmission.
So `Your previous call:` named the wrong event and `your process then stopped`
was false of it.

| | before | after |
|---|---|---|
| re-decision label | `Your previous call:` | `What you know about this payment:` |
| new-payment label | `Your previous call:` | `What you know about the previous payment:` |
| `unknown_process_died` | *"your process **then** stopped. …"* | *"your process stopped **while a call for it was in progress**. …"* |

Every clause is now true after an absorbed re-dispatch: the process did stop
while a call was in progress, and the three unknowns are still unknown, because
the absorbed attempt sent nothing and changed nothing. The other three wordings
were already true of the payment and are unchanged.

**Verified in the live text, not just in the constant.**
`test_no_wording_tells_the_agent_a_refusal_happened` asserts that no wording
contains *lease, lock, intent, invariant, fence, barrier, refused before, not
sent*; and §5's stub evidence shows **zero** refusal terms across every prompt
in both collections.

## 4. Implementation

Agent branch only. Scripted branch and matrix character-for-character
unchanged; `AEP_FULL`'s lock policy unchanged; no protocol code touched.

| file | change |
|---|---|
| `agent_loop.py` | `NOT_TRANSMITTED` sentinel; `classify_outcome(..., transmitted)`; `observe(..., transmitted)`; the loop absorbs and restores; `_emit_absorbed`; the reworded `OUTCOME_WORDING` |
| `live_planner.py` | the two prompt labels |
| `worker.py` | **+16 / −1** — reads the transmission counter around the dispatch |
| `injector.py` | `TransmissionObserver.transmissions`, a counter on the existing passthrough |

**Why a counter and not the event log.** Amendment 4 §3 keeps the oracle's
record on the oracle's side of the wall, so the driver must not read
`events.jsonl`. The counter is in-process state on the passthrough that already
emits `docs/31`'s event, incremented **before** the event and before the call,
so it marks the same instruction boundary. `docs/31` §2's six properties are
untouched: delegation, return value and exception re-raising are unchanged.

**`NOT_TRANSMITTED` is a sentinel, not a fifth value.** A fifth value would be
reachable on AEP and never on B0 — the one-bit arm label amendment 6 §6 forbids
and the reason the author rejected Option 2. `OUTCOME_VALUES` is still exactly
four.

**Undetermined counts as transmitted.** `transmitted=None` reports the
transport result. Absorbing an undetermined case would hide a real failure; the
safe direction at worst repeats what the code did before.

### 4.1 Tests — `tests/test_transmission_boundary.py`, 30 passed

**The reachability test that replaces the synthetic-only check.**
`test_last_outcome_is_arm_neutral.py` tests `classify_outcome`'s mapping over
synthetic inputs and cannot see which inputs each arm can produce — which is
how this leak survived it. The new check drives the seven `aep_core` failure
classes and the transport results each arm can actually raise, and compares the
sets produced:

```
test_the_values_actually_produced_are_identical_across_arms   PASSED
```

**The known-positive**, `test_the_old_mapping_would_fail_the_reachability_check`:
the old rule is reproduced exactly and shown to map `LockAcquisitionError` to
`server_error` where the new rule absorbs it — so the test above is not
vacuous. Both the old vocabulary test and the new reachability test are kept.

**The post-expiry claim, tested:** `test_a_refusal_before_transmission_is_not_a_dispatch`
covers every pre-transmission class including `IntentInvariantError`, which is
the uniqueness invariant that refuses a same-payment re-dispatch after the
lease has expired. §6 of the amendment records the intent; the harness-level
form is what is pinned here, and the end-to-end form is what §5's crashed-regime
collection shows.

**Absorption behaviour:**
`test_an_absorbed_redispatch_reaches_the_oracle_and_not_the_planner` asserts the
event carries the cause and that no prompt contains it;
`test_the_knowledge_state_is_restored_after_an_absorbed_redispatch` asserts the
next prompt still says *timed out* and never *server error*;
`test_a_transmitted_failure_is_still_observed` is the known-negative.

One existing test asserted the old wording as a literal and now asserts against
`OUTCOME_WORDING` instead, so a future rewording cannot drift past it.

## 5. The stub collections, side by side

### 5.1 Crashed regime — `phase40-stub-a9-crashed-2026-09-22`, 4 runs, 24 calls, USD 0.00

| | rep 0 | rep 1 |
|---|---|---|
| workload paired | **yes** — 986162 / 419764 / 434899 | **yes** — 975014 / 825597 / 286303 |
| dispatch sequence | `[0,0,1,2,2]` on **both** arms | `[0,0,1,2,2]` on **both** arms |
| `provider_request_transmitted` | AEP 3, B0 0 (emitted on the `mutate` path only) | AEP 3, B0 0 |
| absorbed re-dispatches (oracle) | AEP `(0, 1, LockAcquisitionError)`, B0 none | AEP `(0, 1, LockAcquisitionError)`, B0 none |
| **refusal terms in any prompt** | **NONE** | **NONE** |
| decisions seeing identical text | **5 of 6** | **5 of 6** |

**The `server_error` lie is gone.** Where stage 30 and the amendment-8 stub
recorded `server_error` on AEP's re-dispatch four times out of four, the
absorbed attempt now produces no observation at all and the agent's knowledge
state is restored.

**The one remaining difference is two true statements, and it is the
measurement.** At `step1 d0`:

| | text delivered |
|---|---|
| `AEP_FULL` | *"your process stopped while a call for it was in progress. You do not know whether it was sent…"* |
| `B0_NAIVE_RETRY` | *"it was acknowledged."* |

AEP's re-dispatch of payment 0 was refused before transmission, so nothing
changed and the crash's unknown still stands. B0's re-dispatch transmitted and
was acknowledged. **Both are true of what happened on that arm**, and the
difference is the protocols behaving differently — which is what the experiment
exists to observe.

### 5.2 No crash armed — `phase40-stub-a9-nocrash-2026-09-22`, 4 runs, 12 calls, USD 0.00

Run because §5.1 cannot compare faults: AEP delivers nothing to the provider
when killed mid-dispatch.

| | rep 0 | rep 1 |
|---|---|---|
| workload paired | **yes** | **yes** |
| dispatch sequence | `[0,1,2]` both arms | `[0,1,2]` both arms |
| provider saw | AEP 3 applied; B0 4 applied | AEP `[applied, **refused 503**, applied]`; B0 `[applied, **refused 503**, applied, applied]` |
| decisions seeing identical text | **3 of 3** | **3 of 3** |
| refusal terms in any prompt | **NONE** | **NONE** |

The injected 503 landed on **both** arms — amendment 8's pairing still holding —
and every decision saw identical text.

### 5.3 Arm-neutrality, stated precisely

The values **delivered** in each collection:

| collection | `AEP_FULL` | `B0_NAIVE_RETRY` | identical |
|---|---|---|---|
| crashed | `unknown_process_died` | `acknowledged`, `unknown_process_died` | **no** |
| no crash | `acknowledged` | `acknowledged` | yes |

**This is not a leak, and the distinction matters.** Amendment 6 §6 requires
every value to be *reachable* on both arms **by the same path**, not that the
same values *occur* in every regime. `acknowledged` is reachable on AEP — §5.2
shows AEP delivering it, by the same path B0 does, a transmitted call that was
acknowledged. In the crashed regime AEP does not reach it because its protocol
refuses to re-dispatch, and that refusal is the measurement rather than a leak.

What *was* a leak — a value AEP could produce through a path B0 structurally
lacks — is closed: the seven `aep_core` refusal classes now produce no
observation at all.

## 6. The stage-100 command — prepared, NOT run

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
at 0.00021712 per call. The re-decision prompt is slightly longer since
amendment 9 reworded the labels, which moves the estimate by under 1 %:

| | |
|---|---|
| expected, 24 calls | ≈ **USD 0.0052** |
| maximum, 100 calls at the current price | **USD 0.16288** |
| maximum at the stale price | USD 0.81440 |
| cumulative afterwards | ≈ 0.0088 expected, ≤ 0.1665 worst case |

§6's stage-100 criterion requires cumulative spend **< USD 1**; the worst case
is 17 % of that.

### Is it clear to run?

**On the instrument, yes.** The leak `55807d6` named is closed by amendment 8
and verified; the leak `4525646` named is closed by amendment 9 and verified;
no prompt in either stub collection contains a refusal term; the values
produced are arm-neutral in reachability and every statement made to the agent
is true.

**Two things the author should weigh before authorising it**, neither a defect:

1. **In the crashed regime AEP never completes a re-dispatch**, so stage 100
   will collect AEP declining or being absorbed, and B0 re-dispatching. That is
   the protocols' real difference, and it is what §2's binary reachability
   claim is about — but it means an *undetected duplicate* under B0 requires the
   **agent** to choose to re-dispatch, and at stage 30 it declined both times.
2. **The stage-100 criterion needs both failure modes observed.** Nothing in
   the instrument now prevents either; whether an agent produces them is the
   open question, and §8's F1 governs the answer if it does not.

**The command has not been run and no cap is raised by this report.**

## 7. One correction to the record

While setting up §5.1 I ran a stub script whose `ROOT` still pointed at
`phase40-stub-rpc2-2026-09-21`, and **overwrote that collection**. It was a
zero-cost stub, superseded by `phase40-stub-paired-2026-09-22` (which is
intact), and its numbers are quoted in
`reports/phase-report-40-clause1-and-stage-100-prep-2026-09-22.md` §4.2, which
still reads correctly. The directory was renamed to
`phase40-stub-a9-crashed-2026-09-22`, which is what it now contains. Recorded
because overwriting a directory a committed report cites should not pass
without a note.

## 8. Verification

| | |
|---|---|
| full suite | **2 515 passed, 34 skipped** |
| `tests/test_transmission_boundary.py` | **30 passed** |
| `tests/test_scripted_plan_is_frozen.py` | **59 passed** |
| `tests/test_last_outcome_is_arm_neutral.py` | **12 passed** |
| `tests/test_paired_seeding.py` | 29 passed |
| `tests/test_same_payment_redecision.py` | 14 passed |
| `scripts/check_paper_numbers.py` | 43 passed, 0 failed |
| `scripts/check_line_endings.py` | clean |
| builds | all four, supplementaries first; main **24 pp**, main-anon 23 pp, supplementary 7 pp, supplementary-anon 7 pp; zero `??` |
| live calls | **none**; cumulative USD 0.00359020 |
