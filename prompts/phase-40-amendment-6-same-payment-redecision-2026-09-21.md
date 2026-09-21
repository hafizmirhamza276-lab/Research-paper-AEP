# Amendment 6 — the re-decision concerns the same payment, and the agent owns it

**Amends `prompts/phase-40-agent-reachability.md`** §1 (the turn structure) and
§3 (the per-run cap), and supersedes amendment 3's turn semantics in the one
respect §2 below names. The pre-registration is not edited. Committed **before
any further live call**.

**This is an instrument-validity finding from stage 10, not a change made to
reach a result.** Stage 10 passed all four of its criteria
(`reports/phase-report-40-stage-10-interactive-2026-09-21.md`). What it
established is that the instrument, working exactly as specified, **cannot ask
the question §1 says the experiment is about**. Nothing here is adjusted
because a number came out wrong; no number has come out at all.

---

## 1. The defect, named exactly

**Two individually correct amendments combine into a design that cannot ask its
own question.**

* **Amendment 3** made each turn an *independent payment*. Correct: the
  scaffold has always given every execution its own `amount_minor` from its own
  named random stream, and the accumulating-obligation reading produced
  arithmetic that terminated two runs early.
* **Amendment 4** made `last_outcome` report the previous call. Correct:
  without it there was no observation at all, and §1's "observe an outcome, and
  re-plan" described something the code did not do.

**Together, the agent re-decides about a different payment from the one whose
outcome was ambiguous.** §1's claim is *"an LLM re-planning after an ambiguous
outcome"*. For that claim, the ambiguous call and the re-decision must concern
**the same execution**. They do not.

Stage 10 showed both possible agent responses, one per arm, and neither is the
measurement:

> `aep_full` — *"A prior capture may already have been applied, so retrying could duplicate the payment."*

> `b0_naive_retry` — *"The previous notification was acknowledged, so no further call is warranted."*

Both treated `last_outcome` as bearing on the payment in front of them. It bore
on a different account for a different amount. An agent that instead reads the
prompt correctly would have to ignore `last_outcome` entirely — in which case
the interactive loop measures exactly what the planned loop measured, and
amendment 4 bought nothing.

## 2. What §1 and amendment 3 keep, and the one thing that changes

**Amendment 3 stands in full except for one sentence.** Payments remain
independent: each execution keeps its own harness-assigned account and amount,
and nothing an agent did about payment *n* bears on the amount owed on payment
*n+1*. Amendment 3's reasoning — that the alternative adds a second reasoning
task on top of the one under test, and that the amount must stay where the
oracle's fingerprint can see it — is untouched, and `PLANNER_AMOUNT_MISMATCH`
is untouched.

**What changes is what happens when a payment's outcome is not an
acknowledgement.** Amendment 3 assumed every turn advances to a new payment.
That is now false in one case, and only one.

---

## 3. The turn semantics, fixed now

A **decision** concerns one execution. `decision_index` counts decisions for
that execution: `0` is the initial one, `1` is a re-decision.

**After a decision is executed and its outcome observed:**

| observed outcome | what the next decision concerns |
|---|---|
| `acknowledged` | the **next** payment: new account, new harness-assigned amount |
| `timed_out` | **the same payment**: same account, same harness-assigned amount |
| `server_error` | **the same payment** |
| `unknown_process_died` | **the same payment** |

**A new payment is presented only after the previous one is acknowledged, or
after the agent has explicitly chosen not to dispatch it again.**

### 3.1 At most one re-decision per execution

`MAX_DECISIONS_PER_EXECUTION = 2`. If the re-dispatch also returns a
non-acknowledged outcome, the run moves to the next payment and records that it
did.

Two reasons, and neither is cost:

1. **One is enough to answer the question.** The harness crashes each execution
   at most once — `runner.py` removes the resumed execution from
   `remaining_crashes` precisely so a crashed system can make progress — so a
   single re-decision is sufficient to reach an acknowledged outcome in the
   regime the experiment runs in.
2. **More would be a rate.** "How many times does an agent retry" is a
   distribution, and §2 forbids this collection from reporting one. A bounded
   single re-decision answers *whether* it retries, which is the binary
   reachability claim §2 does allow.

### 3.2 The re-decision is not a replay

A decision that was *made* and whose outcome was *observed* is replayed on
respawn, unchanged, with no model call — amendment 4 §3 and §5 of the
pre-registration both stand.

A decision that was made and whose outcome was **never observed** is the
crashed one. It is **not** replayed: the agent is asked again, about the same
payment, with `last_outcome: unknown_process_died`. Replaying it would
re-dispatch on the strength of a decision the agent made before it knew
anything had gone wrong, which is the harness deciding while appearing not to.

This requires observations to be durable and on the agent's side of the wall.
They are written to **`planner-observations.jsonl`** in the run directory,
keyed `(worker_index, execution_index, decision_index)`, carrying only the
`result` value. **Amendment 4 §3's rule stands without exception: the replayed
observation is never reconstructed from `events.jsonl`.** The event log holds
the oracle's `execution_resolved` record for the very turn the death was
supposed to leave unknown; reading it would hand the replacement agent the
answer. `planner-observations.jsonl` holds only what `classify_outcome`
produced, which is arm-neutral by construction (§6).

---

## 4. The re-dispatch decision is the agent's, on both arms, identically

### 4.1 What stage 10 established about who decides now

Established from the code and the live run directory, not from the docs.

**In the live `B0_NAIVE_RETRY` run, execution 0 was dispatched twice at 775463.
The second dispatch was decided by the harness.** `runner.py:293-303`:

```python
if config.effective_resume_policy is ResumePolicy.REEXECUTE_CRASHED:
    # The supervisor runs the crashed execution again. With no durable
    # pre-dispatch record there is no third option ... and this is the branch
    # that turns a crash into a duplicated external effect.
    from_index = last_started
```

`events-worker-0-attempt-2.jsonl` records `worker_started from_index=0` then
`execution_started ex0 amount=775463`, and `planner-transcript.jsonl` holds
**one** entry for step 0. The planner was never asked. The supervisor set
`from_index` back and the driver replayed the old decision.

**The two arms do not merely differ in outcome; they differ in who decides, and
on neither arm is it the agent:**

| | `resume_policy` | `redispatches_on_replay` | after a crash |
|---|---|---|---|
| `B0_NAIVE_RETRY` | `REEXECUTE_CRASHED` | `True` | the **supervisor** re-dispatches |
| `AEP_FULL` | `NEXT_EXECUTION` | `False` | the worker **never** re-dispatches |

**So, stated plainly: any undetected duplicate collected so far is
harness-caused and says nothing about the agent.** It is produced by
`runner.py:293` together with `redispatches_on_replay=True`, with no agent
involvement whatsoever. The comment in the code says so itself — *"this is the
branch that turns a crash into a duplicated external effect."* No live
collection has yet recorded an undetected duplicate, so nothing already
reported has to be withdrawn; but had one been recorded, it would have been
evidence about `ResumePolicy`, not about an LLM.

### 4.2 A second consequence: `unknown_process_died` is currently AEP-only

Following from the same asymmetry, and checked in the live transcripts:

* Under `AEP_FULL`, `from_index = last_started + 1`, so the driver's
  `_pending = UNKNOWN_PROCESS_DIED if from_index > 0` fires and the agent is
  told its previous call's fate is unknown.
* Under `B0_NAIVE_RETRY`, `from_index = last_started` (0 here), so `_pending`
  starts `None`, the crashed execution is re-dispatched from the replayed
  decision, its outcome is observed, and the agent is told **`acknowledged`** —
  the fate of a dispatch it did not choose, not of its own call.

That is precisely what stage 10's two turn-2 prompts show.

**`unknown_process_died` is therefore reachable on AEP and effectively
unreachable on B0**, which is the leak class amendment 4 §2.3 excludes
`dispatch_attempts` for. `tests/test_last_outcome_is_arm_neutral.py` did not
catch it because it tests `classify_outcome`'s *vocabulary and mapping*, which
are neutral, and not the *reachability of each value per arm*, which is decided
by the loop around it. That gap is closed in §6.

### 4.3 The change

**On the agent–interactive branch only**, and on **both arms identically**:

1. `run_worker_slot` re-enters at the crashed execution —
   `from_index = last_started` — **regardless of the descriptor's
   `resume_policy`**.
2. The crash injector's existing suppression of a second crash on a resumed
   execution applies on both arms, so the agent's re-dispatch is allowed to
   complete rather than being crashed again into a lifetime loop.
3. The driver asks the agent whether to dispatch that payment again. The item
   is executed only if the agent says so.

**What this does not change.** No protocol implementation is touched:
`aep_core`'s intent ledger, `WAITAOF` barrier, fencing and recovery are exactly
as they are, and B0's absence of them is exactly as it is. `SystemDescriptor`
is not edited — `resume_policy` and `redispatches_on_replay` keep their values
and keep governing the scripted branch and the planned-agent branch. What moves
is **who is asked**, which is a property of the supervisor and, in the world the
paper describes, of the caller.

**Why this strengthens validity rather than weakening it.** The experiment runs
one fixed caller against two protocols and attributes the difference to the
protocols. While the supervisor re-dispatches on one arm and not the other, the
difference being measured is between *supervisors*. Making the decision the
agent's on both arms removes that confound and is the only configuration in
which the comparison means what §2 says it means.

**Comparability.** The agent-branch collection is not comparable with the
scripted matrix. That was already true — §2 forbids any of it appearing beside
a matrix cell — and this amendment does not widen it. The scripted branch
remains character-for-character unchanged and
`tests/test_scripted_plan_is_frozen.py` still recomputes the 51 collected runs.

---

## 5. Prompt neutrality, and a test on the text

The re-decision prompt must present **dispatch again** and **do not dispatch
again** symmetrically. This is the one place in the experiment where the prompt
could decide the result, and §8's F2 already names a prompt that scripts the
call as an instrument failure.

The constraints, pinned by `tests/test_redecision_prompt_is_neutral.py`:

* **Both options are stated, in parallel grammatical form**, and neither is
  listed with a qualifier the other lacks.
* **No evaluative or steering vocabulary** anywhere in the re-decision text:
  no *safe*, *risk*, *risky*, *careful*, *cautious*, *avoid*, *danger*,
  *should*, *ought*, *better*, *prefer*, *recommend*, *advise*, *warn*,
  *duplicate*, *idempotent*.
  `duplicate` is on the list because it names the outcome being measured;
  a prompt that says the word has told the agent what the experiment is about.
* **No default.** The text must not say what happens if the agent does not
  choose, because there is no such case — it is asked and must answer.
* **The two options' descriptions are within a small length ratio of each
  other**, so neither is argued for at greater length than the other.
* The facts either option needs — that the provider is not idempotent, and what
  was observed — are stated **once, before** the options, not attached to one.

## 6. Amendment 4's rules are kept in full, and one is strengthened

`last_outcome` keeps exactly the four values `timed_out`, `server_error`,
`acknowledged`, `unknown_process_died`, and the exclusions of `outcome_class`,
`request_fingerprint`, `status`, `dispatch_attempts` and `intent_id` stand
unchanged. **The re-decision prompt must pass the same test**: it is built from
the same `OUTCOME_WORDING` and carries nothing else about what happened.

**The standing constraint is restated and extended**, because §4.2 found a way
around it:

> **An agent that can tell which arm it is in is a second uncontrolled
> variable, and the comparison stops meaning anything.** It is not enough that
> the *vocabulary* of `last_outcome` be identical across arms. **Every value
> must be reachable on both arms, by the same path.**

`tests/test_last_outcome_is_arm_neutral.py` gains a case for the second
sentence: after a crash, both arms must reach `unknown_process_died` at the
same point in the loop.

---

## 7. The per-run cap, re-derived: 28 → 20

Amendment 4 derived `(T + L) × A × W`. The new turn structure changes `T`,
because an execution may now cost two decisions instead of one:

`(T × D + L) × A × W`

| term | value | source |
|---|---|---|
| `T` executions per worker | 3 | §1 |
| `D` decisions per execution | 2 | §3.1: one initial, at most one re-decision |
| `L` lifetimes | 4 | `REEXECUTE_CRASHED`-style re-entry without re-crashing, so lifetimes ≈ executions + 1. Observed 2 and 3 live |
| `A` attempts per decision | 2 | one call, one malformed retry — what `_ask` does |
| `W` workers | **1** | what every live stage has run with |

**(3 × 2 + 4) × 2 × 1 = 20.**

`+L` rather than `×L` still holds: a respawn replays every decided-and-observed
step, so a new lifetime costs new calls only for the at-most-one decision a kill
can land inside, plus the re-decision that death now earns.

### 7.1 Two workers would breach §3, and the design is therefore pinned to one

At `W = 2` the same formula gives **40**, and §3's pre-registered per-run
ceiling is **36**. `agent_loop.stage_caps` refuses any value above the
pre-registered number, so 40 could not be set even deliberately without
amending §3's ceiling — which this amendment does **not** do.

**So the interactive design is pinned to one worker until and unless §3's
per-run ceiling is amended.** That is recorded here rather than discovered when
a two-worker run is refused at launch. Every live stage so far has used
`--workers 1`, so nothing changes in practice.

### 7.2 Against `MAX_ATTEMPTS_PER_WORKER = 64`

A worker slot may burn **64 lifetimes** before the runner gives up. Each
lifetime replays what is decided and observed, and can add at most one new
decision the kill landed inside, at `A = 2` attempts:

`64 × 2 × W` = **128** calls in one run at `W = 1`, **256** at `W = 2`.

**The per-run cap is the only thing standing in front of that number.** At 20 it
stops **6.4×** sooner than the pathological case, and 1.8× sooner than
amendment 4's 28.

### 7.3 The collection-wide numbers do not move

Worst case 20 runs × 20 = 400, under §3's 1 000. Expected is far lower: 20 runs
× 1 worker × 3 payments, plus a re-decision on each crashed one, ≈ 120 calls for
the entire design. The USD ceiling is untouched at 1 000 × $0.0016288 ≈ $1.63.

---

## 8. Pre-commitment: this is the last structural amendment to phase 40

Committed here, before the data, so it cannot be decided after seeing it.

**If agents under these semantics never re-dispatch, that is a result.** It
falls under §8's **F1** — the failure modes were not shown reachable with an
LLM caller — and it is reported as one. The paper then says that a real agent
offered a neutral choice to re-send a call whose fate it could not determine
declined to, and the reachability claim is dropped as §8 already specifies.

**It is not a reason for a seventh amendment.** A seventh amendment would be a
search for a configuration in which the result appears, which §8's F1 paragraph
already forbids in terms: *"It does not retry with a different prompt, a
different crash point, or a larger model until the result appears — that would
make the experiment a search for a confirming instance rather than a test."*

**Only an instrument fault justifies a further amendment**, and such an
amendment must name which of these it is:

* a **crash** — the harness aborts, a run cannot complete, a cap fires
  spuriously;
* a **leak** — the agent can see the oracle's verdict, or can tell which arm it
  is in;
* a **malformed path** — the agent cannot express one of the two choices, or
  the harness misroutes a well-formed answer.

A prompt the agent reads differently from how it was intended is **not** on that
list. That judgement has now been made three times, and the third time it was
the design rather than the wording.

---

## 9. What §6's stage-30 criterion means under these semantics

§6 stage 30: *"at least one crashed run respawns and **re-enters the loop
reading the transcript, issuing no new model call for already-decided steps**;
void rate recorded."*

"Already-decided" now needs one word of precision, because §3.2 splits the
crashed decision out of it. Under amendment 6, stage 30 must show, in at least
one crashed run:

1. **every decision that was made and observed is replayed with no model
   call** — the cost and correctness property §5 of the pre-registration is
   about, unchanged; **and**
2. **exactly one new call is made about the crashed payment** — the
   re-decision, with `last_outcome: unknown_process_died`, concerning the same
   account and the same harness-assigned amount; **and**
3. **that re-decision is the agent's**, on whichever arm the run is — no
   `execution_started` for a re-dispatch that the planner was not asked about.

A respawn that silently re-dispatches the crashed payment **fails** clause 3
even though it satisfies clause 1, and that is the difference between what
stage 10 recorded and what stage 30 must record.

Void rate is recorded as before.

---

## 10. What is unchanged

§1's design and its two systems, §1.1's harness-assigned target, §2's metric
and its prohibition on rates, §3's five controls and both USD figures, §4's
`PLANNER_FILTERED`, §5's transcript requirements, §6's C1–C3 and its staging,
§8's failure definitions, and §9's stop rule as amended by amendment 5.
Amendments 1, 2, 4 and 5 stand in full; amendment 3 stands except for the one
sentence §2 names.
