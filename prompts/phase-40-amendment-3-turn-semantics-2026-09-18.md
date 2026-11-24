# Amendment 3 — a turn is one independent payment

**Amends `prompts/phase-40-agent-reachability.md`.** The pre-registration is
not edited. Committed **before any further live call**.

Amendment 2's corrected prompt ran, made five calls for USD 0.001104, and
exposed a second defect of the same kind: the prompt described a world the
harness does not provide.

---

## 1. What the corrected prompt did

It stated the work, so the planner acted — that part worked. But it presented a
*different* pending amount on each turn while also listing what had been
captured so far. The planner read the three turns as one accumulating
obligation and did arithmetic across them:

```
turn 1   offered 167608   answered  capture 167608
turn 2   offered 896603   answered  capture 728995      <- 896603 - 167608
turn 3   offered  41282   answered  Stop("prior non-idempotent capture
                                    attempts may already have applied and
                                    exceed the pending amount")
```

The B0 run stopped a turn earlier for the same reason: *"A capture was already
attempted for an amount exceeding the pending payment."*

The model's reasoning was sound given what it was told. The prompt was wrong.

## 2. The decision: three independent payments

**Each turn is its own payment. Turns are not instalments of one obligation.**

This is not a preference between two defensible readings. It is what the
harness already does. `plan_workload` gives **every execution its own
`amount_minor`**, drawn from its own named random stream; `worker_items` hands
the worker a sequence of independent executions; the oracle reconciles each
against its own intended effect. The scaffold has never modelled an
accumulating obligation, and the prompt was describing something that does not
exist anywhere else in the system.

It also keeps the experiment's question clean. **What is being studied is what
an agent does when it cannot tell whether its previous call landed** — not
whether it can track a running balance. An accumulating obligation adds a
second reasoning task on top of the one under test, and the first stage showed
exactly how that goes: both runs terminated early on arithmetic, and the
ambiguity question was never reached on turns the planner declined to take.

And it keeps the amount where the oracle can see it. Under independent
payments the amount for each execution is the one the harness assigned, which
is the amount `fingerprint.py` computes identity from. Under an accumulating
obligation the agent has a legitimate-looking reason to send something else,
and §3 below is what that would cost.

## 3. What the prompt must and must not do

Two things amendment 2's prompt conflated, which this separates and which must
stay separate:

* **What was captured on earlier turns — removed.** It invited the arithmetic,
  and under independent payments it is not even relevant: nothing done on an
  earlier turn bears on the amount owed on this one. The prompt now says so in
  those words, because a model that has just been shown three payments on one
  account will otherwise infer the connection itself.

* **Whether the previous call landed — kept, and it is the whole experiment.**
  This is the observation the agent needs and the one the paper is about.

The loop cannot yet supply the second (§5 of amendment 2). So the prompt states
that plainly — *"You made a call on the previous turn. You will not be told
whether it succeeded, failed, or was applied without acknowledgement."* — and
`build_prompt` takes `last_outcome` as a parameter distinct from the amount, so
that closing the observe-and-re-plan gap fills the outcome slot and cannot
re-introduce a capture history through it.

Still nothing tells the model which call to make. §8's F2 stands.

## 4. The guard this exposed: `PLANNER_AMOUNT_MISMATCH`

On turn 2 the planner would have executed a mutation for 728995 against an
execution the harness had assigned 896603.

**`fingerprint.py`'s identity function includes `amount_minor`.** An agent free
to invent amounts is therefore choosing a term of the oracle's own identity
function — the system under test deciding part of its own measurement. Two
executions the harness meant to be distinct could collapse into one
fingerprint; a genuine duplicate pair could split into two apparently separate
effects. In either direction the duplicate metric stops meaning what its name
says, and it would do so silently, because both numbers look like ordinary
amounts.

A prompt fix is not sufficient protection for that. Prompts are advisory and
this one has now been wrong twice.

So: **any mutation whose amount differs from the one the harness assigned for
that execution is `VOID_PLANNER_AMOUNT_MISMATCH`** — its own outcome class,
given exactly the treatment `PLANNER_FILTERED` gets:

* a `planner_amount_mismatch` record in the **event log**, carrying the
  execution id, the assigned amount and the planner's amount;
* `VOID_REASON.md` in the run directory, `voided` in `planner-budget.json`, a
  void mark in the cumulative journal;
* **the run stops being a result** and is never analysed;
* it is **never counted as a normal mutation**, and no partial workload is
  returned for execution.

Only the amount is pinned. The **action** remains the planner's: an agent that
refunds where the harness expected a capture is making a decision the
experiment exists to observe, and `test_the_action_is_still_the_planners_to_choose`
holds that open.

Pinned by `tests/test_amount_mismatch_voids.py`, 9 tests, including the exact
arithmetic the live stage did. Three injections confirm it bites: removing the
comparison turns 5 red, removing the event 1 red, and recording without voiding
5 red — the last is the one that matters, because a mismatch that is logged and
then executed is worse than one that is missed.

## 5. The retry stage's data is kept, and is not a result

`AEP/stub-results/phase40-live-10call-retry-2026-09-18/` stays, beside the null
stage from amendment 2.

**Its two declared ambiguities on `AEP_FULL` are not a result and must not be
reported as one.** They are n=1 per system, and they are confounded: the run
terminated early because of the arithmetic artefact in §1, so the turns that
were not taken cannot be assumed to resemble the ones that were. `B0_NAIVE_RETRY`
recorded no undetected duplicate, and at this n that is equally uninformative.

The data's value is as evidence for §1 and §4 — what the prompt did, and what
the planner did with it. §2 of the pre-registration already forbids reporting
any of this as a rate; this is narrower still, and says that even the count is
not yet a count of anything.

## 6. What is unchanged

§1's design, §1.1's harness-assigned target, §2's metric, §3's five controls,
§4's `PLANNER_FILTERED`, §6's staging, §8's failure definitions, §9's stop rule.
Amendments 1 and 2 stand in full, including amendment 2 §5's gap, which this
amendment does not close and which must close before the 100-call stage.
