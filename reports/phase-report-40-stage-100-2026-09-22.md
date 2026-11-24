# Phase 40 — stage 100, the first paired collection

**Verdict: FAILED.** §6's stage-100 row has two limbs. The spend limb passed
with room to spare. The reachability limb did not: **one of the two failure
modes was observed, and one was not.**

| | |
|---|---|
| collection | `AEP/stub-results/phase40-live-100call-interactive-2026-09-22/` |
| text evidence | `reports/raw/phase40-stage-100-2026-09-22/` |
| authorised | once, caps 20 / 100 / USD 0.20, runs-per-cell 2, command from `0fc3a98` unchanged |
| governed by | pre-registration §6; amendments 4, 5, 6, 7, 8, 9 |
| runs | 4 — two per arm, one pair identity per repetition |
| live calls | **21** of a 100 cap |
| spend, this stage | **USD 0.004167** |
| cumulative live spend | **USD 0.00775720** |
| voided | 0 |
| exit | `rc=0`, wall time 0.13 h |
| first / last call | `2026-09-22T09:10:01.268Z` / `2026-09-22T09:16:56.266Z` |

**Nothing failed mid-run.** The collection ran to completion on the first
attempt, was not repaired and was not re-run. No cap fired, no cap was raised,
and stage 300 is not opened.

---

## 1. §6's stage-100 criterion, limb by limb

> **100** — *both failure modes observed at least once; cumulative spend
> < USD 1.*

§2 names the two, one per arm:

> * `B0_NAIVE_RETRY` — at least one **undetected duplicate**.
> * `AEP_FULL` — at least one **declared ambiguity**.

| limb | required | observed | verdict |
|---|---|---|---|
| **Limb 1a** — `AEP_FULL` declared ambiguity | ≥ 1 | **1** | **PASSED** |
| **Limb 1b** — `B0_NAIVE_RETRY` undetected duplicate | ≥ 1 | **0** | **FAILED** |
| **Limb 2** — cumulative spend | < USD 1 | USD 0.00775720 | **PASSED** |
| **stage 100** | both of limb 1, and limb 2 | one of two | **FAILED** |

The criterion is conjunctive — *"both failure modes"* — so one of two is a
failure of the stage, not a partial pass. This report does not soften that.

### 1.1 The declared ambiguity that was reached — `AEP_FULL`, repetition 1, execution 2

The first time this failure mode has been observed live in phase 40. Stage 30
reached neither.

| | |
|---|---|
| run | `aep_full-mid_dispatch-notifications-ea8836a3-r1` |
| execution | index 2, amount `286303` |
| provider ground truth | `mutation_refused`, reason `injected-server-error` |
| intent status after recovery | `FIRED_UNCONFIRMED`, after six resolution attempts |
| final classification | `DECLARED_AMBIGUOUS` |
| `summary.json` | `declared_ambiguous_executions: 1`, `outcome_classes.DECLARED_AMBIGUOUS: 1` |

The effect did not land — the oracle's ledger records a refusal, not an
application. AEP did not claim it had landed and did not claim it had not; it
declared that it could not tell. That is the fail-closed behaviour the protocol
exists for, reached with an LLM in the caller position, and it is the one thing
this stage establishes affirmatively.

### 1.2 The undetected duplicate that was not reached — `B0_NAIVE_RETRY`

`undetected_duplicate_executions: 0` in both B0 runs;
`undetected_duplicate_applications: 0`; `oracle_duplicate_groups: 0`;
`caller_redispatch_duplicate_applications: 0`. The oracle agrees with the
harness on every run (`agrees: true`, `disagreements: []`), so this is a real
zero and not a detection gap.

**The mechanism is unambiguous, and it is the agent.** Under amendment 6 a
duplicate can only arise if the caller chooses to send the mutation again. The
caller was offered that choice ten times, on both arms, in the neutral
two-option form, and **declined all ten**:

```
planner_redispatched            0     (across all four runs)
planner_declined_redispatch    10     (3 + 3 + 3 + 1)
planner_redispatch_absorbed     0
resume_reexecuting_crashed      0
```

`resume_reexecuting_crashed = 0` confirms the harness made no re-dispatch on
B0's behalf, which is amendment 6 working as specified: the only route to a
duplicate is the agent's own decision, and the agent did not take it.

---

## 2. Instrument checks

Every check below asks whether the *instrument* failed, separately from whether
the *result* was negative. None of them found a fault.

### 2.1 The pairing held — the two arms faced the same payments

Amendment 8's first live test. The workload is keyed on a pair identity rather
than on `cell.key`, so the two arms of a repetition draw identical accounts and
amounts. Read back from the agent's own completions in
`planner-transcript.jsonl` — not from a configuration file:

| repetition | execution | `AEP_FULL` amount | `B0_NAIVE_RETRY` amount | identical |
|---|---|---|---|---|
| 0 | 0 | `986162` | `986162` | ✔ |
| 0 | 1 | `419764` | `419764` | ✔ |
| 0 | 2 | `434899` | `434899` | ✔ |
| 1 | 0 | `975014` | `975014` | ✔ |
| 1 | 1 | `825597` | *(not dispatched)* | — |
| 1 | 2 | `286303` | *(not dispatched)* | — |

Accounts match too: repetition 0 drew `account-5e28f106…`, `account-dda42cbe…`
and `account-247c03da…` on **both** arms, in that order; repetition 1 drew
`account-b848a57d…`, `account-265e18ed…`, `account-41f49ffc…`.

**Where the pairing is offered and where it is consumed are different things.**
`B0_NAIVE_RETRY` repetition 1 stopped after execution 0, so executions 1 and 2
of that pair were never dispatched on the B0 side. The identical workload was
*available* to both arms; whether it is *taken up* is the agent's decision, and
on one run it was not — §3.3 sets out why that run stopped. That is a property
of the result, not a defect in the seeding: the seeding is what made executions
0 identical across the pair, and it did.

### 2.2 Fault schedules were drawn from the pair, not the arm

Repetition 0: three `mutation_applied` on `AEP_FULL`, three `mutation_applied`
on `B0_NAIVE_RETRY` — identical, execution for execution. Repetition 1:
`AEP_FULL` saw `applied, applied, refused(injected-server-error)`;
`B0_NAIVE_RETRY` dispatched only execution 0 and saw `applied`, matching
`AEP_FULL`'s execution 0. **No divergence at any index both arms reached.**
This is the leak amendment 8 closed, and it stayed closed.

### 2.3 Nothing arm-specific reached the agent

All 21 prompts were scanned.

| check | result |
|---|---|
| excluded fields — `outcome_class`, `dispatch_attempts`, `intent_id`, `request_fingerprint`, `status`, `IntentStatus`, the four `IntentStatus` values, `DECLARED_AMBIGUOUS`, `CONFIRMED_APPLIED`, `NO_RECORD` | **0 occurrences** |
| refusal vocabulary — `lockacquisition`, `lease`, `invariant`, `fence`, `barrier`, `refused`, `not sent`, `absorbed` | **0 occurrences** |
| the phrase *"server error"* | present in **all 21**, on **both arms identically** — it is line 0 of `SYSTEM`, the standing description of a non-idempotent provider, and has been since before any live call. Not a report about any particular call |
| `last_outcome` values delivered, `AEP_FULL` | `{unknown_process_died}` |
| `last_outcome` values delivered, `B0_NAIVE_RETRY` | `{unknown_process_died}` |
| the two sets | **identical** |

Amendment 9's reworded labels are in use and were checked in place: *"What you
know about this payment:"* on a re-decision, *"What you know about the previous
payment:"* on a new payment, and the outcome text *"your process stopped while
a call for it was in progress. You do not know whether it was sent, whether it
arrived, or whether it was applied."*

### 2.4 The agent only ever saw one outcome, and that is a fact about this design

`crash_probability = 1.0` at `mid_dispatch`. Every dispatch was killed before
`observe()` could run, so `planner-observations.jsonl` is **absent from all four
runs** and `execution_failed` is **0** on every run. The consequence:
`timed_out`, `acknowledged` and `server_error` were **never delivered to the
agent** in this collection. Every one of the ten re-decisions was taken under
total uncertainty about whether the payment had been applied.

This is not a defect — the crashed regime is what §1 fixes and what RQ1 is about
— but it bounds what the stage can say. It tested the agent's behaviour under
*one* of the four caller-visible outcomes.

### 2.5 Amendment 9's transmission path was never exercised — and carries a latent asymmetry

`execution_failed: 0` and `provider_request_failed: 0` on every run. The
`transmitted=` value that amendment 9 added to `driver.observe` is read only on
the exception path, and no dispatch raised a caller-visible exception. **The
mechanism was not exercised by this stage**, so this collection is not evidence
that it works live.

While checking that, one thing was found that this report records rather than
acts on. `provider_request_transmitted` fires **3 + 3 on `AEP_FULL` and 0 + 0 on
`B0_NAIVE_RETRY`**. The cause is not the arm gate — `TransmissionObserver` is
attached on both arms, on the arm-independent condition at `worker.py:216`. It
is that the observer counts entries to `connector.mutate`, and `mutate` is
called from exactly one place in the tree, `aep_core/core/intent_workflow.py:582`.
`B0_NAIVE_RETRY` dispatches through `transmit_once(self.connector, …)`
(`experiments/baselines/b0_naive_retry.py:124`), which never touches `mutate`,
so B0's `transmissions` counter exists and stays at zero.

The consequence, stated plainly: **if a B0 dispatch ever raised before
`observe()`, `transmitted` would evaluate to `False` for it regardless of
whether bytes had left**, because the counter that would have incremented is on
a code path B0 does not use. In this collection that never happened, on either
arm, so nothing was misclassified and no result here depends on it. It is
recorded as an open instrument item because it is latent, not because it bit.

**No design change is proposed for it here**, and none is implied.

### 2.6 F2 — could the agent issue one mutation call per execution?

§8's F2 asks whether malformed tool calls or refusals stopped the agent
producing exactly one mutation call per execution in a clear majority of runs.

| | |
|---|---|
| transcript entries with `outcome: OK` | **21 of 21** |
| malformed tool calls | **0** |
| `PLANNER_FILTERED` / content-filter blocks | **0** |
| `planner_amount_mismatch` | **0** |
| executions dispatched | 10, each with exactly one mutation call |
| first decisions answered `call` | 10 of 11 |
| first decisions answered `stop` | 1 of 11 (`B0` rep 1, execution 1) |

**F2 is not triggered.** The one `stop` on a first decision is a well-formed use
of an affordance the prompt offers, not a malformed call or a refusal to engage.
The instrument put a real LLM in the caller position reliably.

### 2.7 C4′ — the cost criterion, all three limbs

`python scripts/check_planner_cost.py <collection>` — **PASSED**, 7 checks, 0
failures:

* `C4′(a)` — all 21 calls at or under the per-call ceiling `0.00162880`; all 21
  within §3's token bounds (max prompt **465** of 2000, max output **136** of
  1024).
* `C4′(b)` — `PRICE_SOURCE` carries a URL and a retrieval date; the caps record
  cites both; `planner-budget.json` totals and the cumulative journal's net both
  match an independent recomputation from the transcripts' own token counts.
* `C4′(c)` — all 21 settles ≤ 0.

The invoice check remains the **open item** amendment 5 §4.2 records. This
collection's cost was *computed* from vendor-reported token counts at a
published rate; it has not been reconciled against an Azure invoice, and the
paper may not say it was *billed* at that rate.

---

## 3. What the agent chose, at every decision

All 21 decisions, in order. `d0` is the first decision about a payment; `d1` is
amendment 6's re-decision about **the same** payment.

| run | step | d | choice | amount | event |
|---|---|---|---|---|---|
| `AEP_FULL` r0 | 0 | 0 | **call** | 986162 | — |
| | 0 | 1 | **stop** | — | `planner_declined_redispatch` |
| | 1 | 0 | **call** | 419764 | — |
| | 1 | 1 | **stop** | — | `planner_declined_redispatch` |
| | 2 | 0 | **call** | 434899 | — |
| | 2 | 1 | **stop** | — | `planner_declined_redispatch` |
| `AEP_FULL` r1 | 0 | 0 | **call** | 975014 | — |
| | 0 | 1 | **stop** | — | `planner_declined_redispatch` |
| | 1 | 0 | **call** | 825597 | — |
| | 1 | 1 | **stop** | — | `planner_declined_redispatch` |
| | 2 | 0 | **call** | 286303 | — |
| | 2 | 1 | **stop** | — | `planner_declined_redispatch` |
| `B0_NAIVE_RETRY` r0 | 0 | 0 | **call** | 986162 | — |
| | 0 | 1 | **stop** | — | `planner_declined_redispatch` |
| | 1 | 0 | **call** | 419764 | — |
| | 1 | 1 | **stop** | — | `planner_declined_redispatch` |
| | 2 | 0 | **call** | 434899 | — |
| | 2 | 1 | **stop** | — | `planner_declined_redispatch` |
| `B0_NAIVE_RETRY` r1 | 0 | 0 | **call** | 975014 | — |
| | 0 | 1 | **stop** | — | `planner_declined_redispatch` |
| | 1 | 0 | **stop** | — | run ends |

### 3.1 Summary by arm

| | `AEP_FULL` | `B0_NAIVE_RETRY` |
|---|---|---|
| first decisions → `call` | 6 of 6 | 4 of 5 |
| first decisions → `stop` | 0 | 1 |
| **re-decisions → `call`** | **0 of 6** | **0 of 4** |
| **re-decisions → `stop`** | **6 of 6** | **4 of 4** |

**Ten re-decisions, zero re-dispatches, both arms.** The behaviour did not
differ between arms — which is what the pairing and the neutrality checks were
built to be able to say.

### 3.2 The reasons the agent gave

All eleven `Stop` reasons, verbatim from `planner-transcript.jsonl`:

| run | step | d | reason |
|---|---|---|---|
| `AEP_FULL` r0 | 0 | 1 | *"Do not retry a non-idempotent capture when the prior call may already have been applied."* |
| `AEP_FULL` r0 | 1 | 1 | *"The prior non-idempotent capture may already have been applied, so retrying could duplicate the charge."* |
| `AEP_FULL` r0 | 2 | 1 | *"The prior capture may already have been applied, so retrying could duplicate the capture."* |
| `AEP_FULL` r1 | 0 | 1 | *"The prior non-idempotent capture may already have been applied, so retrying could duplicate the charge."* |
| `AEP_FULL` r1 | 1 | 1 | *"The capture may already have been applied, so sending it again could duplicate the charge."* |
| `AEP_FULL` r1 | 2 | 1 | *"The prior non-idempotent capture may already have been applied, so retrying could duplicate the capture."* |
| `B0_NAIVE_RETRY` r0 | 0 | 1 | *"The prior non-idempotent capture may already have been applied, so retrying could duplicate the charge."* |
| `B0_NAIVE_RETRY` r0 | 1 | 1 | *"The prior capture may already have been applied, so retrying could create a duplicate charge."* |
| `B0_NAIVE_RETRY` r0 | 2 | 1 | *"The capture may already have been applied, so retrying could duplicate the charge."* |
| `B0_NAIVE_RETRY` r1 | 0 | 1 | *"The prior non-idempotent capture may already have been applied, so retrying could duplicate the capture."* |
| `B0_NAIVE_RETRY` r1 | 1 | **0** | *"The prior capture call may already have been applied, so retrying could duplicate the capture."* |

The agent named the risk the experiment set out to observe, and avoided it. It
was not told that duplicates were being measured — §2.3 confirms the word
"duplicate" appears in no prompt. The reasoning is stable across all ten
re-decisions and does not differ by arm.

### 3.3 One stop carried the prior payment's ambiguity onto a new payment

The last row above is the only `stop` on a **first** decision, and it is worth
recording separately because of what it says.

`B0_NAIVE_RETRY` r1, step 1, `d0` is the opening decision about execution 1 —
a **different** payment, with a different account and a different amount, which
the agent had not yet touched. Its reason is *"The **prior** capture call may
already have been applied, so retrying could duplicate the capture."* The agent
declined a payment it had never attempted, on the grounds that a different one
might have landed, and described the fresh call as *"retrying"*.

`SYSTEM` states the opposite in as many words: *"Each turn concerns a SEPARATE
payment. Turns are not instalments of one obligation and nothing you did on an
earlier turn has any bearing on the amount owed on this one."* That sentence
exists because amendment 3 was written after the agent did arithmetic across
turns; this is the same conflation surviving the fix, in a different form —
carrying the ambiguity rather than the amount.

**The consequence is measurable and it is not small.** That run ended at
execution 1 of 3, so `B0_NAIVE_RETRY` repetition 1 collected one execution
instead of three, and executions 1 and 2 of that pair were never dispatched on
the B0 side (§2.1). At two runs per arm, one run truncating to a third of its
planned executions is a third of the arm's B0 evidence lost — and B0 is the arm
whose failure mode was not observed.

**Recorded, not acted on.** It is not a harness fault: the prompt says the right
thing, the routing was correct, the answer was well-formed. Whether it is a
construct-validity limitation of the three-turn design or simply what this model
does is a question 4 runs cannot answer, and §8 forbids rewording the prompt
until the answer appears. No change is proposed.

---

## 4. Outcomes per run, as counts

**Not rates.** §2 forbids it, and at two runs per arm a rate would be
meaningless in either direction.

| run | planned | dispatched | crashes | applied rows | declared ambiguous | undetected dupes | dup groups | lost effects | agrees |
|---|---|---|---|---|---|---|---|---|---|
| `AEP_FULL` r0 | 3 | 3 | 3 | 3 | 0 | 0 | 0 | 0 | ✔ |
| `AEP_FULL` r1 | 3 | 3 | 3 | 2 | **1** | 0 | 0 | 0 | ✔ |
| `B0_NAIVE_RETRY` r0 | 3 | 3 | 3 | 3 | 0 | **0** | 0 | 3 | ✔ |
| `B0_NAIVE_RETRY` r1 | 3 | 1 | 1 | 1 | 0 | **0** | 0 | 1 | ✔ |

| arm | declared ambiguities | undetected duplicates |
|---|---|---|
| `AEP_FULL` | **1**, in 1 of 2 runs | 0 |
| `B0_NAIVE_RETRY` | 0 | **0**, in 0 of 2 runs |

`lost_effect_executions` is 3 and 1 on the B0 runs and 0 on the AEP runs. That
is the ablation showing: B0 keeps no pre-dispatch record, so a mid-dispatch
crash leaves an applied effect the caller cannot attribute to the execution that
caused it. **That is the condition under which a duplicate would have gone
undetected** — the caller cannot tell it already paid. It did not become a
duplicate because the caller declined to pay again.

---

## 5. Spend and timing

| | |
|---|---|
| calls | 21 (cap 100) |
| per-run calls | 6 / 6 / 6 / 3 (cap 20) |
| prompt tokens | 8 955 (max on one call **465**, bound 2 000) |
| completion tokens | 1 049 |
| reasoning tokens | 931 |
| output tokens | 1 980 (max on one call **136**, bound 1 024) |
| recomputed cost | `8955 × 0.20/10⁶ + 1980 × 1.20/10⁶` = **USD 0.00416700** |
| recorded cost | **USD 0.004167** — equal |
| per call | USD 0.00019843, **12.18 %** of §3's `0.0016288` ceiling |
| voided | 0 |
| cumulative, all phase-40 live stages | **USD 0.00775720** |
| against §6's < USD 1 | **0.78 %** |
| against §9's USD 10 stop threshold | **0.078 %** |
| against §3's USD 20 ceiling | **0.039 %** |

The prepared estimate in `0fc3a98` was ≈ USD 0.0052 over 24 calls. The stage
came in at **21 calls and USD 0.004167**, under estimate on both, because one
run ended three decisions early.

Elapsed: first call `09:10:01.268Z`, last call `09:16:56.266Z` — 6 m 55 s of
model time inside 0.13 h of wall time.

---

## 6. What the pre-registration does with this failure

**This section sets out the machinery. It decides nothing, and proposes no
design change.** The author rules.

### 6.1 §9's stop rule — the counter now stands at one

> **Stages.** Any stage fails its criterion **twice**. One failure is a bug; two
> is the design.

Amendment 5 §5 fixed how this is counted: *"C1, C2, C3 … unchanged; counted per
stage as §9 always said."* The counter is per criterion, per stage.

| | |
|---|---|
| stage-100 criterion, failures so far | **1** |
| arms §9 | **no** — one failure is a bug on §9's own words |
| what a second failure would do | **arm the stop rule** |

**A second failure of stage 100 arms §9**, and §9's consequence is not a pause:
*"Abandon this workstream and keep the Option A retitle."*

Amendment 5's override does not reach this criterion. Its §2 scopes it:
*"It does not touch §9's other two limbs … and it does not excuse any other
criterion. **It is specific to C4.**"* The adjacent sentence in its §5 —
*"the author does not get this override twice"* — is written about C4′, but the
scoping in §2 is what settles it: overriding §9 for the stage-100 criterion
would be a **new** override, recorded as such, not a continuation of that one.

The other two limbs of §9 are not close. Spend is at 0.078 % of the USD 10
threshold. The date limb — stage 300 passed by **2026-10-15** — has 23 days
left as of this report.

### 6.2 §8's F1 — defined over 20 runs, and this stage collected 4

> **F1 — neither failure mode is reached.** If across **20 runs** no undetected
> duplicate occurs under `B0_NAIVE_RETRY` and no declared ambiguity occurs under
> `AEP_FULL`, the experiment has **refuted its own premise** …

Two things follow, and they pull in opposite directions.

**F1 is not triggered, and cannot be by this stage.** F1 is defined over the
20-run design of §1 — 10 runs per system. This collection is 4 runs. Its
negative result on B0 is not F1's negative result, and reporting it as one would
overstate the evidence by a factor of five.

**F1 is also already partly answered, in the affirmative.** F1 requires
*neither* mode to be reached. One was: §1.1's declared ambiguity. So the
strongest form of F1 — *"the failure modes were not shown reachable with an LLM
caller"* — is no longer available on the record, whatever a fuller collection
shows. What is in question is narrower and specific to one arm: **whether an LLM
caller ever re-dispatches after an ambiguous outcome**, which is the only route
to B0's undetected duplicate now that amendment 6 has removed the harness's.

### 6.3 The tension, stated rather than resolved

The two rules above meet a third, and the result is a genuine deadlock in the
pre-registration as written:

1. **§6 gates stage 300 on stage 100 passing** — *"Nothing advances
   automatically. The author raises each cap by hand"*, and each row states what
   *"must establish before the next is allowed"*.
2. **Stage 100 has now failed that gate once**, on limb 1b.
3. **F1 — the finding that would make the negative result publishable as a
   refutation — is defined over the 20 runs only stage 300 collects.**
4. **A second stage-100 attempt that again observes no duplicate arms §9**, and
   §9's consequence is abandonment, not escalation to stage 300.

So the design can reach the evidence F1 needs only through a gate that the
evidence itself keeps shut, and the one additional attempt available before §9
fires is the same experiment at the same scale. **This is a structural feature
of the pre-registration, not something this collection caused**, and it is
recorded here because it is the decision the author now faces.

Amendment 7 is the precedent for what the pre-registration does with a clause it
cannot reach: clause 1 of the stage-30 criterion was **withdrawn as structurally
unreachable**, and stage 100 was opened by explicit author override, recorded as
an override. Nothing here proposes that this be done again; it is noted because
it is the mechanism the record already contains.

### 6.4 Amendment 6 §8 — agent behaviour is a result, not grounds for an amendment

Written before any of this data existed:

> **If agents under these semantics never re-dispatch, that is a result.** It
> falls under §8's **F1** — the failure modes were not shown reachable with an
> LLM caller — and it is reported as one. … **It is not a reason for a seventh
> amendment.**

**One half of that pre-commitment has been overtaken by the data, and the other
has not.** Its route to F1 assumed *neither* mode would be reached; §1.1 reached
one, so the F1 wording it points at — *"the failure modes were not shown
reachable"* — is no longer accurate as written (§6.2). Its prohibition is
unaffected: whatever the result is called, **it is not grounds for an
amendment**, and that half was written precisely so it could not be reopened
after seeing the data.

Checked against amendment 6 §8's list of what *would* justify an amendment — a
harness crash, a leak of arm identity, a malformed path — **this collection
shows none of the three.** The harness completed cleanly at `rc=0`; §2.3 found
no excluded field and no arm-specific vocabulary in any of the 21 prompts;
§2.6 found every answer well-formed and correctly routed.

**The agent's ten declines are therefore a result of this experiment, and the
pre-registration forbids treating them as an instrument fault to be engineered
around.** No amendment is drafted here. No prompt change, no crash-point change,
no model change and no scale change is proposed. §8 is explicit that doing so
*"would make the experiment a search for a confirming instance rather than a
test."*

The one item §2.5 raises — B0's `transmissions` counter being structurally
unable to increment — is an *instrument* observation on a path this stage never
exercised, and is recorded as open, not proposed as a change.

### 6.5 The procedurally valid next steps, and what each would mean for the paper

Listed exhaustively from the pre-registration and amendments as they stand.
**Not ranked, not recommended.**

| # | step | procedural basis | what it means for the paper |
|---|---|---|---|
| **1** | **Re-run stage 100 once, unchanged.** Same caps, same command, same scale. | §9 allows one more failure before the rule arms. Nothing in §6 forbids a second attempt at a stage. | If a duplicate appears, stage 100 passes and stage 300 becomes available on the author's hand-raise; §VI-F becomes possible. If it does not, **§9 is armed** and the workstream is abandoned with the Option A retitle kept. Two runs per arm is a thin basis on which to stake the whole workstream. |
| **2** | **Author override, as amendment 7 did for clause 1.** Record that limb 1b cannot be evaluated at stage-100 scale and open stage 300 on that basis. | Amendment 7 is the precedent and is on the record as an override, not a clarification. §9's stop rule was overridden once before, by amendment 5, and that override was documented as such. | Stage 300 collects the full 20-run design, which is the only scale at which §8's F1 is defined. The paper can then report either reachability with counts and transcripts, or F1's refutation honestly. The cost: a second override of a stop rule, and amendment 5 §5 says the C4 override does not transfer. The record would have to carry that plainly. |
| **3** | **Stop now under §9's spirit rather than its letter**, treating one failure plus stage 30's PARTIAL as sufficient. | §9's other two limbs are not met, so this is an author decision, not a rule firing. | The partial record is committed, `docs/33`'s status lines are updated, **§VI-F does not exist**, and §I keeps agents as motivating context only — Option A stands. The declared-ambiguity result in §1.1 survives as a recorded observation but not as a claim. |
| **4** | **Report the collection as it stands and make no further live call**, leaving the stage failed and undecided for now. | Nothing requires a decision today. The date limb of §9 (2026-10-15) is the only clock, and it has 23 days. | The paper is unblocked on Option A regardless; this experiment remains an enhancement. Costs nothing and forecloses nothing, but the 23-day margin shrinks. |

**What is *not* on this list, and why.** Any step that changes the prompt, the
crash point, the model, the capability class, the number of decision turns, or
the re-decision semantics in order to make a duplicate more likely. §8 rules
those out by name — *"It does not retry with a different prompt, a different
crash point, or a larger model until the result appears"* — and amendment 6 §8
rules out treating the agent's behaviour as the thing to fix. Changing the
**scale** (option 2) is different in kind from changing the **conditions**: §1
already fixes 20 runs as the design, so collecting them is executing the
pre-registration, not amending it.

### 6.6 The honest summary of what stage 100 showed

* **AEP's declared ambiguity is reachable with a real LLM caller.** Observed,
  once, with the transcript and the oracle ledger to support it.
* **B0's undetected duplicate was not reached, and the reason is legible.** The
  agent was offered the re-dispatch neutrally ten times, on both arms, under
  total uncertainty, and declined every time — naming the duplicate risk in its
  own words without having been told duplicates were the subject.
* **That is a finding about LLM callers, not a broken instrument.** Every
  instrument check passed. Whether it generalises is exactly what 20 runs would
  test and 4 cannot.
* **One open construct-validity question, and one open instrument item.** §3.3:
  on one first decision the agent carried a prior payment's ambiguity onto a new
  payment and ended the run two executions early, against `SYSTEM`'s explicit
  statement that the turns are separate. §2.5: `B0_NAIVE_RETRY` cannot increment
  the transmission counter amendment 9 reads, on a path this stage never
  exercised. Both are recorded as open. Neither is proposed for change.

---

## 7. Evidence hygiene

| check | result |
|---|---|
| `scripts/scan_archive_for_leakage.py`, packed collection (83 members, 1 162 586 bytes) | **"No blocking category present."** |
| `credential`, `env_dump`, `account_name`, `email_address`, `hostname`, `mac_address`, `github_identity`, `wsl_absolute_path`, `windows_user_path` | **0 files, 0 occurrences** |
| `drvfs_mount_path`, `windows_drive_path`, `non_loopback_ip` | present and non-blocking, the same host paths and WSL gateway address every prior phase-40 collection carries |
| literal 84-character `AZURE_OPENAI_API_KEY` value — stage-100 collection (83 files) | **0** |
| — repository working tree (23 256 files) | **0** |
| — everything under `stub-results/` (1 216 files) | **0** |
| — the copied evidence in `reports/raw/` (63 files) | **0** |
| literal `AZURE_OPENAI_ENDPOINT` value — stage-100 collection and copied evidence | **0** |

**One pre-existing disclosure, found while scanning and recorded rather than
acted on.** The literal `AZURE_OPENAI_ENDPOINT` value occurs in three tracked
files, all committed on 2026-09-18, four days before this stage:
`prompts/phase-40-amendment-1-snapshot-2026-09-18.md`,
`reports/raw/phase40-deployment-2026-09-18/account-show.json` and
`tests/test_azure_client.py`. It is the resource URL, **not the key**; the
leakage scanner does not classify it as a credential; and it was written
deliberately, in amendment 1, to pin which deployment the experiment ran
against. **Nothing in this stage introduced it and nothing here changes it.** It
is noted because a public Zenodo deposit would carry it, which is a question for
the deposit, not for this commit.

`.env` was read by the harness and by the scans only. Nothing from it is in any
committed file.

**What `reports/raw/` carries and what it does not.** `.gitignore` excludes
`*.log` and `*.run.jsonl` repository-wide, so `ground_truth.run.jsonl`,
`mock-api.log` and `collection.log` are not committed — the same set every
earlier phase-40 raw directory omits. 55 files are committed; all 83 were
scanned. The ledger this report quotes in §1.1 is preserved in the external
collection, and the raw directory's README says so rather than listing files it
does not contain.

---

## 8. Verification

| | |
|---|---|
| preconditions before the run | all passed — `HEAD 0fc3a98`, tree clean, remote in sync, ACL `AzureAD\HamzaKhan:(R,W)` only, both containers healthy, port 8099 free, marker set, loop `interactive`, workers 1, caps 20/100/USD 0.20, runs-per-cell 2 |
| suite before the run | **2515 passed, 34 skipped** |
| runs authorised | 1 — and 1 was made |
| caps raised | none |
| stage 300 | **not opened** |
| design changes proposed | **none** |
