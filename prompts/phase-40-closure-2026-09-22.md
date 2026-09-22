# Phase 40 — closure by author decision, at stage 100's first failure

**Closes `prompts/phase-40-agent-reachability.md` and amendments 1–9.** No
further live call will be made under this pre-registration. Committed with the
partial record, as §9's on-stop procedure requires.

**This is an author decision, not a triggered stop rule, and it is written that
way deliberately.** A workstream abandoned because a rule fired and one
abandoned because the author chose to stop are different facts about a project,
and a reader who finds phase 40 closed should be able to see which this was.

---

## 1. §9 did not fire. All three of its conditions are stated and none is met

> **Abandon this workstream and keep the Option A retitle if any of:**
>
> * **Spend.** Cumulative spend reaches **USD 10** — half the ceiling — without
>   stage 100 having passed.
> * **Stages.** Any stage fails its criterion **twice**. One failure is a bug;
>   two is the design.
> * **Date.** Stage 300 has not passed by **2026-10-15**.

| condition | threshold | actual at closure | fired |
|---|---|---|---|
| Spend | USD 10 cumulative | **USD 0.00775720** — 0.078 % of it | **no** |
| Stages | any criterion failed **twice** | stage-100 criterion failed **once** | **no** |
| Date | 2026-10-15 | 2026-09-22, **23 days** remaining | **no** |

**The workstream is closed with none of them met.** Nothing in the
pre-registration compels this, and nothing in it forbids it either: §9 states
when abandonment is *required*, not when it is *permitted*.

## 2. What was decided, by whom, and why

**The author decided, on 2026-09-22, to close phase 40 at stage 100's first
failure.** The reasoning, recorded as given.

### 2.1 The result is the agent's behaviour, and it did not vary

Across stage 30 and stage 100, on both arms, under the neutral two-option
re-decision amendment 6 installed: **the agent was offered the re-dispatch and
declined every time.**

| | stage 30 | stage 100 | total |
|---|---|---|---|
| re-decisions offered | 2 | 10 | **12** |
| answered *send again* | 0 | 0 | **0** |
| answered *do not send again* | 2 | 10 | **12** |

Stage 100's ten were 6 on `AEP_FULL` and 4 on `B0_NAIVE_RETRY` — **no
difference by arm** — every one taken under total uncertainty
(`unknown_process_died`, the only outcome the crashed regime ever delivered),
and every one giving a reason that names the duplicate risk in the agent's own
words, without the word "duplicate" appearing in any prompt.

### 2.2 Amendment 6 §8 forecloses redesigning around it

Committed before any of this data existed, precisely so it could not be decided
afterwards:

> **If agents under these semantics never re-dispatch, that is a result.** It
> falls under §8's **F1** … and it is reported as one. … **It is not a reason
> for a seventh amendment.** A seventh amendment would be a search for a
> configuration in which the result appears, which §8's F1 paragraph already
> forbids in terms.

And §8 itself:

> It does not retry with a different prompt, a different crash point, or a
> larger model until the result appears — that would make the experiment a
> search for a confirming instance rather than a test.

**So the one lever that would plausibly change the outcome is the one the
pre-registration bars.** That is not an obstacle the design failed to
anticipate; it is the design working as intended.

### 2.3 The gating deadlock leaves no pre-registered path that does not either arm §9 or require a further override

Set out in full in `reports/phase-report-40-stage-100-2026-09-22.md` §6.3, and
restated here because it is the operative reason:

1. **§6 gates stage 300 on stage 100 passing** — *"Nothing advances
   automatically"*, each row stating what *"must establish before the next is
   allowed"*.
2. **Stage 100 has failed that gate once**, on the `B0_NAIVE_RETRY` limb.
3. **§8's F1 — the finding that would make a negative result publishable as a
   refutation — is defined over the 20 runs only stage 300 collects.**
4. **A second stage-100 attempt that again observes no duplicate arms §9**, and
   §9's consequence is abandonment, not escalation.

The evidence F1 needs is reachable only through a gate the evidence itself keeps
shut, and the single attempt available before §9 fires is the same experiment at
the same scale, against a behaviour that has now been stable across 12 of 12
offers.

### 2.4 We chose not to make another override

**This is the part that decides it, and it is a choice, not a deduction.**

Two overrides are already on this record. Amendment 5 overrode §9 after C4
failed twice. Amendment 7 withdrew stage 30's clause 1 as structurally
unreachable and opened stage 100 by author override. Each was documented as an
override rather than a reinterpretation, for the reason amendment 5 §0 gives:

> a stop rule that is quietly reread is not a stop rule, and a reader who finds
> C4 replaced should be able to see that the condition fired, who overrode it,
> and on what reasoning.

Opening stage 300 now would be a **third** override, of a gate this time rather
than of a criterion, and made in order to collect more of a result that has not
varied in 12 offers. Amendment 5 §5 already wrote the principle down for its own
case — *"the author does not get this override twice"* — and while that sentence
is scoped to C4′, the disposition behind it applies here.

**A pre-registration whose gates are overridden whenever they bind is not a
pre-registration.** The author judged that the evidentiary value of a third
override is lower than the cost to the credibility of the whole instrument, and
chose to stop with the record honest rather than continue with the rules
loosened. **That judgement, and not any rule, is why phase 40 is closed.**

### 2.5 What this deliberately does not assert

The closure does **not** assert that a real LLM caller never re-dispatches, that
the experiment was badly designed, or that a larger collection would have shown
nothing. It asserts only that the pre-registration as written offers no path to
that answer that the author is willing to take.

---

## 3. What was established, as counts only

**§2 governs this section.** *"Never as a rate. Never in a table beside the
matrix."* Every figure below is a count over the runs named beside it.

### 3.1 The two failure modes

| failure mode, per §2 | arm | observed | in |
|---|---|---|---|
| **declared ambiguity** | `AEP_FULL` | **1** | stage 100, repetition 1, execution 2 (amount `286303`) |
| **undetected duplicate** | `B0_NAIVE_RETRY` | **0** | stage 100, 2 runs |

**One of the two was reached with a real LLM in the caller position.** The
provider refused with an injected server error, recovery left the intent
`FIRED_UNCONFIRMED` after six resolution attempts, and the final classification
was `DECLARED_AMBIGUOUS`. The effect did not land and the system did not claim
it had. The transcript, the event log and the oracle's ledger are archived.

**The other was not.** `undetected_duplicate_executions: 0`,
`undetected_duplicate_applications: 0`, `oracle_duplicate_groups: 0`,
`caller_redispatch_duplicate_applications: 0`, with `agrees: true` and no
disagreements on every run — a measured zero, not a detection gap.

### 3.2 Agent re-dispatches

| | count |
|---|---|
| re-decisions offered, stage 30 and stage 100 | **12** |
| **agent re-dispatches** | **0** |
| harness-owned re-dispatches (`resume_reexecuting_crashed`) | **0** |
| absorbed re-dispatches (`planner_redispatch_absorbed`) | **0** |

### 3.3 Stage verdicts

| stage | verdict | qualification |
|---|---|---|
| **stub** (0 calls) | passed | — |
| **10** | **passed** | **C4 as written failed twice** — see §3.4, which amendment 5 §3 requires any later summary to carry |
| **30** | **PARTIAL** | clause 1 withdrawn by amendment 7 as structurally unreachable; clauses 2 and 3 passed; void rate recorded |
| **100** | **FAILED** | one of two failure modes observed; spend limb passed |
| **300** | **not opened, not attempted** | — |

### 3.4 Stage 10's C4 history, carried forward as amendment 5 §3 requires

> Both earlier verdicts stand as `failed as written`. … They are not re-scored
> under the replacement criterion, and any later summary that describes stage 10
> must carry those two failures.

| collection | calls | USD | per call | vs §3's model | verdict |
|---|---|---|---|---|---|
| null stage (amendment 2) | 2 | 0.000275 | 0.00013750 | 8.44 % | **failed as written** |
| retry stage (amendment 3) | 5 | 0.001104 | 0.00022080 | 13.56 % | **failed as written** |

C4 was replaced by C4′ (amendment 5 §4), which **passed** at every stage that
ran under it, including all seven checks at stage 100. **C4′'s own §9 counter
closes at zero.**

### 3.5 Collections made

| collection | calls | purpose |
|---|---|---|
| route and identity probes, 2026-09-18 | — | deployment identification (amendment 1) |
| stage-10 null | 2 | amendment 2 |
| stage-10 retry | 5 | amendment 3 |
| stage-10 interactive re-run | 4 | amendment 5 |
| stage 30 | 6 | amendment 6 |
| stage 100 | 21 | amendments 8, 9 — the first paired collection |
| **total live calls** | **38** | plus the probes |

---

## 4. What is NOT claimed

### 4.1 §8's F1 was not evaluated

> **F1 — neither failure mode is reached.** If **across 20 runs** no undetected
> duplicate occurs under `B0_NAIVE_RETRY` and no declared ambiguity occurs under
> `AEP_FULL`, the experiment has refuted its own premise …

**F1 is defined over 20 runs. Four were collected.** F1 is therefore **not
triggered, not evaluated, and not reported as having been evaluated.** The
negative result on `B0_NAIVE_RETRY` at n = 2 is not F1's negative result and
overstating it as one would inflate the evidence fivefold.

F1's strongest wording — *"the failure modes were not shown reachable with an
LLM caller"* — is also **not available**, in the other direction: one of them
was shown reachable (§3.1). Neither horn of F1 is claimed.

### 4.2 No rate, and no comparison against the matrix

§2, in force and not amended:

> **Never as a rate. Never in a table beside the matrix.** No value from this
> collection enters `paper/generated/`, `numbers.tex`, or any table that a
> reader could read as comparable to a matrix cell.

And `docs/33` §3.2, which the pre-registration's §0 quotes as already binding:

> **No number that reaches the manuscript may come from it.**

No count in §3 is a rate, none is comparable to a matrix cell, and none enters
the manuscript. See §6.

### 4.3 No generalisation beyond one point in the space

§7, in force:

> One vendor, one deployment, one pinned snapshot, one `api-version`, one
> `reasoning.effort`, one date. Results **not reproducible, only auditable**
> from archived transcripts. No claim about prompt sensitivity, model scale,
> planner quality, or any other model.

| axis | this collection | claimed beyond it |
|---|---|---|
| vendor | Azure OpenAI | **no** |
| deployment | `gpt-5.6-luna` | **no** |
| snapshot | `2026-07-09`, pinned | **no** |
| `api-version` | `2025-04-01-preview` | **no** |
| `reasoning.effort` | `low` | **no** |
| prompt | one, committed before any live call | **no** |
| date | 2026-09-18 to 2026-09-22 | **no** |

**And the deployment auto-upgrades.** Amendment 1 established that the Azure
deployment reports an **alias**, not a snapshot. The snapshot above is what the
transcripts recorded at the time of the calls; the deployment behind it is free
to move, and a later reader pointing the same configuration at the same endpoint
may not reach the same model. **This makes the collection auditable from its
transcripts and not reproducible**, exactly as §7 says, and it is why no claim
here is stated as a property of a model rather than of a recorded interaction.

### 4.4 No claim about why the agent declined

The collection records **that** it declined and **what reason it gave**. It
contains no manipulation that would distinguish a model's learned caution about
non-idempotent retries from a response to the wording of the two-option prompt.
`docs/33` §5.2's *"No causal claim about why a planner drifts"* applies in the
same form here.

---

## 5. The instrument findings — three, and they are findings about the harness

**Stated as results of the workstream, not as excuses for its outcome.** Each
was found by the harness's own checks before it could contaminate a live
comparison, and each is a way that putting an LLM in the caller position leaked
arm identity into what was supposed to be a paired comparison.

### 5.1 Amendment 6 — the harness, not the agent, owned the re-dispatch

**Found at stage 10.** After a crash, `B0_NAIVE_RETRY`'s `ResumePolicy` issued
`REEXECUTE_CRASHED` and `AEP_FULL`'s did not. The second dispatch was therefore
the *supervisor's*, on one arm only. Any duplicate it produced would have been
evidence about `ResumePolicy` — a component both arms were always going to
differ on — and not about an LLM.

**Compounding it, the agent's "re-decision" concerned a *different* payment**,
so the ambiguous call and the decision that followed it were about different
executions, and §1's claim of *"re-planning after an ambiguous outcome"* had no
referent.

**Closed by** making the re-decision concern the same payment, and making
re-dispatch the agent's decision on both arms identically.

### 5.2 Amendment 8 — the fault seed was keyed on the arm

**Found by a symmetry check run before stage 100, as an explicit precondition.**
`cell_seed(matrix_seed, cell.key, repetition)` derives from `cell.key`, which
begins with `system.value`. **The two arms therefore drew different workloads
and different fault schedules**, so any behavioural difference between them
would have been confounded with a difference in what they were asked to do.

**Closed by** paired seeding: the workload is keyed on a pair identity, and
faults on `(pair_seed, endpoint, fingerprint, per-fingerprint dispatch
ordinal)`. Stage 100 is the first collection under it, and §3's evidence shows
it held at every index both arms reached.

### 5.3 Amendment 9 — a pre-transmission refusal was reported to the agent as a server error

**Found while analysing stage 30.** `AEP_FULL` can refuse *locally*, before any
byte leaves, when the lease has expired — a path `B0_NAIVE_RETRY` structurally
lacks, having no lease. The harness classified the resulting exception as
`server_error`, so **the agent was told the provider had failed when no provider
had been contacted**, and only on one arm.

Two defects in one: a **false statement to the caller**, and an **arm-identity
leak** — a value one arm could produce through a path the other did not have.

**Closed by** deriving the caller-visible outcome from whether transmission
occurred, at the boundary `docs/31` already defines as *"the last observable
point at which no provider byte can have left"*. The author ruled against the
alternative of changing AEP's lock-acquisition policy for phase 40, on the
ground that the system under test would then no longer be the matrix's
`AEP_FULL`.

### 5.4 What the three have in common

All three were **invisible to the protocol's own tests and visible only under a
paired live comparison with a real caller.** None would have been found by the
scripted workload, because the scripted workload does not ask the two arms to be
comparable at the level of what the caller is told. That observation is listed in
§7 as one that may stand on its own.

---

## 6. The manuscript

**Settled by §9 and §10 and recorded here so it is not reopened by inference.**

§9's on-stop procedure:

> On stop: the partial record is committed, `docs/33`'s status lines are updated
> again to say so, and **no manuscript text depends on it — §VI-F does not exist
> and is not created until stage 300 passes.**

§10:

> * The manuscript prose. **No §VI-F, no §I change, until stage 300 passes and
>   the result is known.**

**Stage 300 did not pass and will not be attempted, so the condition on which
every manuscript permission depends is never satisfied.** §VI-F does not exist
and is not created. §I is unchanged: agents remain the motivating deployment
context, which is the Option A position `docs/33` §0's 2026-09-04 banner
records and which this closure leaves exactly where it found it.

The detailed reading — the four candidate forms of mention, the rule that
governs each, and the audit of every existing agent mention in `main.tex` and
`supplementary.tex` — is in
`reports/phase-report-40-closure-2026-09-22.md` §3. **No manuscript file is
edited by this closure.**

---

## 7. Open items, recorded and not fixed

**Left open deliberately.** Closing a workstream by fixing its loose ends first
would make the closure a milestone rather than a stop.

| # | item | where |
|---|---|---|
| 1 | **`B0_NAIVE_RETRY` never passes the transmission counter.** `TransmissionObserver` counts entries to `connector.mutate`, called only from `intent_workflow.py:582`; B0 dispatches through `transmit_once` (`b0_naive_retry.py:124`) and never touches it. Its counter exists and stays at zero, so a B0 dispatch that raised before `observe()` would be classified as not transmitted regardless of whether bytes had left. **Latent** — `execution_failed` is 0 on every run of stage 100, so the path was never exercised and no recorded result depends on it | stage-100 report §2.5 |
| 2 | **One agent decision declined a payment it had never attempted.** `B0_NAIVE_RETRY` repetition 1, step 1, first decision: *"The prior capture call may already have been applied, so retrying could duplicate the capture."* — against `SYSTEM`'s explicit *"Each turn concerns a SEPARATE payment … nothing you did on an earlier turn has any bearing"*. That run ended at execution 1 of 3 | stage-100 report §3.3 |
| 3 | **The invoice check.** C4′(b) verifies the repository is internally consistent and its price citable. It does **not** verify that Azure charged that price; the cost-analysis blade has not been read. The record may say the cost was *computed* from vendor-reported token counts at a published rate, and **may not say it was billed at that rate** | amendment 5 §4.2 |
| 4 | **§5's `temperature` and `top_p` are absent from the transcript**, almost certainly because the Responses API does not accept them for a reasoning deployment. §5 says they are recorded; the record should say *not settable on this deployment* rather than omit them silently | amendment 5 §6 |
| 5 | **Stage 300's shortfall.** `N ≤ 15` reachable against §1's 20, noted when stage 100 was opened | amendment 7 |

Items 1 and 2 are the two the author named at closure. Items 3–5 predate it and
are carried so that the closed record is complete rather than tidy.

---

## 8. Spend, and the ceilings that were in force

| | |
|---|---|
| route and identity probes, 2026-09-18 | USD 0.00016620 |
| stage-10 null | USD 0.00027500 |
| stage-10 retry | USD 0.00110400 |
| stage-10 interactive re-run | USD 0.00074200 |
| stage 30 | USD 0.00130300 |
| stage 100 | USD 0.00416700 |
| **total, entire workstream** | **USD 0.00775720** |
| live calls | **38** |
| voided | **0** |

| ceiling | value | consumed |
|---|---|---|
| §3's hard budget ceiling for the whole experiment | USD 20 | **0.039 %** |
| §9's stop threshold | USD 10 | **0.078 %** |
| §6's stage-100 spend limb | USD 1 | **0.78 %** |
| stage-100 per-collection cap | USD 0.20 | 2.08 % |
| stage-100 per-collection calls | 100 | 21 |
| stage-100 per-run calls | 20 | max 6 |

**No cap was ever raised except by the author, by hand, before the stage it
governed**, as §6 requires. No cap fired. **The workstream closes having spent
0.039 % of what it was authorised to spend** — which is worth recording, because
it establishes that the closure was not forced by cost.

---

## 9. What is preserved, and where

| | |
|---|---|
| pre-registration | `prompts/phase-40-agent-reachability.md` |
| amendments 1–9 | `prompts/phase-40-amendment-*.md` |
| this closure | `prompts/phase-40-closure-2026-09-22.md` |
| stage reports | `reports/phase-report-40-*.md` |
| committed text evidence | `reports/raw/phase40-*/` |
| full live collections | `AEP/stub-results/phase40-*/`, outside the repository, unedited |
| status | `docs/33-agent-workload.md` §0 |

§8's disposition, honoured:

> **Both failures are reportable results.** Neither is a reason to leave the
> experiment out of the record. `reports/` carries the outcome either way.

`reports/` carries it. The manuscript does not, for the reason §6 gives.
