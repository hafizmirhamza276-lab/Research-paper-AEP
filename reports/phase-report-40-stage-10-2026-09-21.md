# Phase 40 — the 10-call stage, assessed against its pre-registered criteria

**Assesses** `prompts/phase-40-agent-reachability.md` §6, row **10 calls**,
against the two live collections that have been made. Written on 2026-09-21,
three days after the collections, because no report existed for either.

**No model call was made for this report.** It is a retrospective audit of
archived data. Cumulative live spend is unchanged at **USD 0.00154520**.

**This is a partial result and is reported as one.** Two of the four criteria
are clean passes, one passes literally while the run that satisfied it is void
under the harness as it now stands, and one cannot be assessed as written. The
reasons are below, one criterion at a time.

---

## 1. What is being assessed

Two collections, both outside the repository with the other agent-mode data:

| | stage | root |
|---|---|---|
| **N** | the null stage (amendment 2) | `AEP/stub-results/phase40-live-10call-2026-09-18/` |
| **R** | the retry stage (amendment 3) | `AEP/stub-results/phase40-live-10call-retry-2026-09-18/` |

Both ran the same cell list — `AEP_FULL` and `B0_NAIVE_RETRY`, `mid_dispatch`,
`notifications`, `CALLER_REFERENCE`, 1 run × 3 executions × 1 worker,
p(crash)=1.0 — recorded in each root's `collection.log` and `matrix-plan.json`.

### 1.1 What was actually spent

From `planner-cumulative.jsonl` in each root, which is the authoritative record;
`planner-cumulative.json` carries `"_authoritative": false` and is derived.

| | calls | USD | runs | voided |
|---|---|---|---|---|
| N | 2 | 0.00027500 | 2 | 0 |
| R | 5 | 0.00110400 | 2 | 0 |
| **both** | **7** | **0.00137900** | 4 | 0 |

Plus USD 0.00016620 of route and identity probes, giving the session total of
USD 0.00154520 the handoff records.

The journal holds 4 and 10 lines respectively — one reservation and one settle
per call. Reservation is written **before** dispatch at the full per-call
ceiling and the settle is a negative correction afterwards, so a crash between
the two over-counts and stops early. Every reservation in both roots has its
matching settle; there are no unsettled reservations.

---

## 2. The criteria, one at a time

§6's stage-10 row reads:

> every call has a transcript, token counts and a cost; zero content-filter
> blocks, or each logged as `PLANNER_FILTERED`; zero malformed tool calls;
> measured cost within 20% of §3's model

### C1 — every call has a transcript, token counts and a cost — **PASSED** (N and R)

| | journal reservations | transcript entries | match |
|---|---|---|---|
| N | 2 | 1 + 1 = 2 | yes |
| R | 5 | 3 + 2 = 5 | yes |

Counted from `planner-cumulative.jsonl` against
`<run>/planner-transcript.jsonl`.

**Token counts.** Every transcript entry carries
`usage.prompt_tokens`, `usage.completion_tokens` and `usage.reasoning_tokens`.
No entry in either collection is missing any of the three.

**Cost.** Per call from the journal (`reservation + settle`), and per run in
`<run>/planner-budget.json`. The two agree exactly with the transcript's own
token counts in all four runs:

| run | prompt | output = completion + reasoning | `planner-budget.json` usd |
|---|---|---|---|
| N `aep_full-…-r0` | 330 | 40 + 20 = 60 | 0.0001380 |
| N `b0_naive_retry-…-r0` | 331 | 39 + 20 = 59 | 0.0001370 |
| R `aep_full-…-r0` | 1058 | 434 | 0.0007324 |
| R `b0_naive_retry-…-r0` | 700 | 193 | 0.0003716 |

`330 × 0.20/10⁶ + 60 × 1.20/10⁶ = 0.000066 + 0.000072 = 0.000138` — exact, and
the same holds for the other three. Reasoning tokens are billed as output,
which is correct and is worth stating because it is the term most easily
dropped: on one call in R, reasoning tokens (196) were **four times** the
visible completion (53).

The criterion is met. §3's "per-run cost counter written into the run
directory" and "cumulative cost counter persisted to disk" are both present and
non-zero in both roots.

### C2 — zero content-filter blocks, or each logged as `PLANNER_FILTERED` — **PASSED** (N and R)

All 7 transcript entries carry `"outcome": "OK"`. No entry carries `FILTERED`.
No `planner_filtered` record appears in any `events.jsonl`. No run directory
contains a `VOID_REASON.md`. `voided` is `null` in all four
`planner-budget.json` files and `0` in both cumulative journals.

The criterion is met on its first limb — there were no blocks — so its second
limb was never exercised. **`PLANNER_FILTERED` has therefore still never fired
against live Azure.** §4 of the pre-registration is unexercised, and the void
rate it says must be reported is zero out of seven calls, which is not yet
evidence that filtering is rare.

### C3 — zero malformed tool calls — **PASSED as written**, with a material qualification

All 7 entries have `"attempt": 1` and `"outcome": "OK"`. No entry has outcome
`MALFORMED`. No attempt-2 retry was needed anywhere. Every completion parsed
into a `ToolCall` or a `Stop` on the first try. On the pre-registration's terms
the criterion is met in both collections.

**The qualification.** In R, `AEP_FULL` step 1 answered
`ToolCall(tool='send_notification', action='capture', amount_minor=728995)`
while the prompt for that same step
(`planner-transcript.jsonl`, step 1) offered *"A customer payment of **896603**
minor units is pending capture"*. `events.jsonl` confirms the harness then
dispatched it: `execution_started` with `amount_minor=728995`.

That call was **well-formed**, so C3 is not the criterion it violates — but
under the harness at HEAD it violates a different one. Amendment 3 added
`PLANNER_AMOUNT_MISMATCH`, and a mutation whose amount differs from the
assigned one now voids the run. **Re-run today, R's `AEP_FULL` run would be
`VOID_PLANNER_AMOUNT_MISMATCH` and would never reach `analyze.py`.**

So C3 passes, and the run that passed it is not a run the current harness would
keep. That is not a contradiction — the guard was written *because* of this
call — but it is the reason §4 below matters.

### C4 — measured cost within 20% of §3's model — **FAILED as written; the check it was for is NOT ASSESSABLE**

#### The model, reconstructed from §3

§3's only cost arithmetic: 1 000 attempts × (≤2 000 input + ≤1 024 output) at
Azure Global Standard $0.20/$1.20 per 1M, read 2026-09-17. Both constants are
in code at `experiments/harness/planner.py:98-99`
(`input_per_million = 0.20`, `output_per_million = 1.20`) and the token caps at
`:130,:135` (`max_output_tokens = 1024`, `max_prompt_tokens = 2000`).

```
per call   2000 × 0.20/10⁶  +  1024 × 1.20/10⁶
         =    0.0004        +    0.0012288      =  0.0016288
1000 calls                                      =  1.6288   -> §3's "≈ USD 1.64"  ✓
at the stale $1.00/$6.00                        =  8.144    -> §3's "≈ USD 8.14"  ✓
```

Both of §3's published figures reproduce exactly, so the model is correctly
reconstructed and `0.0016288` is its per-call figure. It is also the exact
amount the journal reserves per call, in both roots.

#### The measurement

```
N     2 calls   USD 0.000275   ->  0.00013750 / call
R     5 calls   USD 0.001104   ->  0.00022080 / call
both  7 calls   USD 0.001379   ->  0.00019700 / call
```

| | measured / model | deviation |
|---|---|---|
| N | 0.00013750 / 0.0016288 = **8.44 %** | **−91.6 %** |
| R | 0.00022080 / 0.0016288 = **13.56 %** | **−86.4 %** |
| both | 0.00019700 / 0.0016288 = **12.09 %** | **−87.9 %** |

A ±20 % band requires the measured figure to land between 0.00130 and 0.00196
per call. It landed at 0.00020. **The criterion fails, in both collections, by
a factor of about eight.**

#### Why it fails, which is the part that matters

§3's model is a **maximum**, written with `≤` signs, under the heading *"Ceiling
if something goes wrong"*. The measurement is actual usage. The gap is entirely
token utilisation:

| | prompt tokens used / capped | output tokens used / capped |
|---|---|---|
| N | 661 / 4 000 = 16.5 % | 119 / 2 048 = 5.8 % |
| R | 1 758 / 10 000 = 17.6 % | 627 / 5 120 = 12.2 % |

A prompt of ~350 tokens against a 2 000-token cap cannot produce a cost within
20 % of that cap's price. **The ±20 % band was unreachable the moment the model
was written as a ceiling**, and it would have been unreachable for any
successful stage. A stage could only satisfy C4 by very nearly exhausting the
token caps on every call — that is, by behaving pathologically.

#### And the check it was presumably for cannot be run

There is a second reading — that C4 exists to confirm the project is being
billed what it thinks. That reading cannot be satisfied either, for a different
reason: **the "measured" cost is not a measurement.** It is Azure's token
counts multiplied by a price constant this repository hardcodes. The identity
`tokens × price = recorded USD` holds exactly in all four runs, as C1 shows. The
only unverified term is the price constant itself, and verifying it requires the
Azure invoice or the cost-analysis blade, neither of which is in the record and
neither of which was read.

So: **failed as written, and not assessable as a billing check.** Both halves
are reported rather than picking whichever gives a cleaner verdict.

### Summary table

| criterion | N (null) | R (retry) |
|---|---|---|
| C1 transcript, token counts, cost | **passed** | **passed** |
| C2 zero filter blocks / logged | **passed** (limb 1; limb 2 unexercised) | **passed** (as N) |
| C3 zero malformed tool calls | **passed** | **passed**, but the run is void at HEAD |
| C4 measured cost within 20 % of §3's model | **failed as written** / not assessable | **failed as written** / not assessable |

---

## 3. Does the null stage count as a stage failure under §9?

§9: *"**Stages.** Any stage fails its criterion **twice**. One failure is a bug;
two is the design."*

Argued from the text, not from what is convenient.

### 3.1 The null stage did not fail any §6 stage-10 criterion

Run C1–C3 against N, which is done above: it passes all three. Two calls, two
transcripts, full token counts, a cost, no filter block, no malformed call.

What N actually did wrong — `executions_planned=3`, `execution_started=0` in
both runs (`summary.json`, `events.jsonl`) — **is not among stage 10's
criteria.** The requirement that executions happen at all lives in §6's row
above: the **stub** stage's *"exactly one mutation call per execution"*. Stage
10's row asks only about calls, transcripts, filters, malformed calls and cost.

That is precisely amendment 2 §7's finding, restated from the criteria's side:
an empty run is internally consistent, so every check that existed passed it.
**Stage 10's criteria were among the checks it passed.** The remedy taken was
a harness gate (`runner.py`'s empty-run refusal, pinned by
`tests/test_empty_run_is_not_a_result.py`), not a new §6 criterion — which is
the right place for it, but it means §6 as written still cannot fail an empty
stage-10 collection.

### 3.2 §8's F2 does not catch it either

F2 is the nearest clause: *"If malformed tool calls or refusals mean the agent
does not produce exactly one mutation call per execution in a clear majority of
runs…"*. N's runs **were** refusals, in 2 of 2 runs — a clear majority.

But F2 defines an **instrument failure** — *"the harness could not put a real
LLM in the caller position reliably enough"* — and amendment 2 §3 establishes
that this is not what happened: *"This is not a model failure and it is not a
harness failure. It is a defect in the prompt."* The prompt never stated there
was a payment to make. Both refusals named the missing thing precisely. F2
describes an agent that cannot do a stated task; N had no stated task.

Reading N as an F2 failure would record the model as unreliable for correctly
declining to act on nothing. The record should not say that.

### 3.3 So: not a stage failure — but C4 has failed twice

**The null stage does not increment §9's counter.** It failed no stage-10
criterion, and the one clause that could have caught it, F2, is about an agent
failing a task it was given.

**C4 is a different matter, and it is uncomfortable.** C4 failed in N and
failed again in R. On §9's plain words — *"any stage fails its criterion
twice"* — **the stop-rule condition is armed.**

The case against reading it that way, also from §9's own words: *"One failure
is a bug; two is the design."* The sentence explains what the rule is *for* —
two failures mean the design is wrong, not the run. C4's two failures have a
single cause, and it is neither the run nor the experiment's design. It is an
arithmetic error inside the criterion: it compares a mean against a ceiling. It
would have fired on every stage, including a perfect one.

**This is the author's ruling to make, and the mechanism is an amendment, not a
reinterpretation.** §9 is a stop rule and the project's practice is that stop
rules are not quietly reread. If C4 is to be restated — as a bound (`measured ≤
§3's model`, which both collections satisfy comfortably) plus a separate,
explicit price-verification step against the Azure invoice — that is amendment
5, committed before the next stage, in the form the other four use. What must
not happen is C4 being treated as passed because the spend was small.

---

## 4. Must stage 10 be re-run on the interactive loop before stage 30?

**Recommendation: yes, re-run it.** The reasoning, and the case against.

### 4.1 Neither collection was produced by the instrument stage 30 would run

Both changed since:

- **The prompt changed** (amendment 3 §3). The capture history was removed, the
  turns were restated as three independent payments, and `build_prompt` gained
  a `last_outcome` parameter. R's prompts are not the prompts that would be
  sent.
- **The loop changed** (amendment 4 §5). N and R ran the plan-then-execute
  branch: every turn decided before anything executed. Stage 30 would run the
  interactive branch, which executes, observes, and asks again.

Stage 10's criteria are *instrument* checks — transcripts, tokens, costs,
filter blocks, malformed calls. An instrument check carried out on a different
instrument certifies nothing about this one.

### 4.2 The surviving evidence is thinner than "two collections" suggests

- N produced **no executions at all** (amendment 2 §3).
- R's `AEP_FULL` run is **void at HEAD** (§2, C3 above) — amendment 3's amount
  guard would refuse it.
- R's `B0_NAIVE_RETRY` run stopped at turn 2 for the same arithmetic reason and
  amendment 3 §5 already rules that its data *"is not a result"*.

So the total live evidence that the instrument works is **7 calls, of which 2
did nothing and 3 came from a run the harness would now void.** That is not a
basis for skipping a check.

### 4.3 The interactive loop has never made a live call

Everything in amendment 4 is derived or stub-verified, not measured live:

- **Prompt length is now larger and unmeasured.** Every turn carries
  `last_outcome`. The per-call cost scales with it and the only live prompt
  sizes on record — 330 to 356 tokens — are from the old shape.
- **The per-run cap of 28** was derived as `(3 + 4) × 2 × 2` (amendment 4 §4),
  with `L = 4` justified from *"observed 3 and 2 in the live retry"* — on the
  loop that no longer runs. It has not been checked against the loop that will.
- **Replay has never run live.** Amendment 4 §3 turns on a respawned worker
  reading the transcript and issuing no new call. In stub mode this cost $0.00;
  live it is the difference between 28 calls and an unbounded respawn loop that
  `MAX_ATTEMPTS_PER_WORKER = 64` permits to reach 256.

### 4.4 The case against, stated fairly

Stage 30 would exercise all of C1–C3 on three times the sample, and §6 does not
oblige a repeat after an amendment — *"Nothing advances automatically. The
author raises each cap by hand"* obliges a decision, not a re-run. Ten calls to
re-certify what thirty calls will certify anyway is arguably ritual.

### 4.5 Why the recommendation is still yes

Because stage 30 carries a criterion the earlier stages do not: *"at least one
crashed run respawns and re-enters the loop reading the transcript, issuing no
new model call for already-decided steps."* That is a **result**, not an
instrument check. If the instrument is broken in a new way — a `last_outcome`
that misaligns after a respawn, a prompt that pushes past a cap, a malformed
completion from the new shape — the failure arrives entangled with the replay
result, and neither can be read cleanly. Stage 10 exists to separate those two
questions, and it is worth ten calls to keep them separate.

The stub-interactive run already demonstrated the shape of this risk at zero
cost: two bugs survived the unit tests and were caught only end to end — a
respawn that started with no pending observation, so `unknown_process_died`
never reached the planner at p(crash)=1.0; and a positional stub that
misaligned after replay. Both were in exactly the machinery stage 30 depends on.

**Cost of the re-run:** at R's worst observed per-call figure (0.00037 USD,
`aep_full` step 1), ten calls is **≈ USD 0.004**. Cumulative spend would remain
near USD 0.006 against a USD 20 ceiling and a USD 10 stop threshold. Against
§9's date — stage 300 by 2026-10-15, i.e. 24 days from this report — a stage
that takes minutes of wall time is not a schedule risk.

**No cap is raised by this report and no call is authorised by it.** The
decision, and the `AEP_PLANNER_PER_COLLECTION_CALLS` value that would carry it,
remain the author's.

---

## 5. Three findings outside the criteria

Found while auditing, none of them a §6 criterion, all of them cheap now and
expensive later.

### 5.1 The transcript has no timestamp, and §5 requires one

§5 lists what each transcript entry records, including *"wall-clock
timestamp"*. It is **absent**. `TranscriptEntry` at
`experiments/harness/planner.py:369-387` has no time field, and no entry in
either collection carries one.

This is not bookkeeping. §5 makes the transcript *"the only replay mechanism"*
and concedes it only lets a reader *check* a run rather than recompute it.
Amendment 1 records that auto-upgrade is **ON** and that *"the pinned version
can change with no trace in the data"*. A timestamp is exactly what would let a
later reader bound a given call against a version change. Without it, the
archive cannot answer "which side of the upgrade was this call on?" — the one
question amendment 1 says the paper must be honest about.

Also absent: `temperature` and `top_p`, which §5 lists. `sampling` carries only
`{"reasoning_effort": "low"}`. That is probably right — the Responses API does
not accept them for a reasoning deployment — but §5 says they are recorded, so
the record should say *not settable on this deployment* rather than omit them.

**Recommendation:** fix before stage 30, since every transcript written after
that is evidence. It is a schema change (`aep.agent.transcript/2` → `/3`) and a
one-line amendment to §5, and it is not made in this report.

### 5.2 The caps in force are not recorded in the collection

`run-config.json` holds 45 fields and **none of them is a planner cap**. The
caps are environment-only —
`AEP_PLANNER_PER_COLLECTION_CALLS`, `AEP_PLANNER_PER_RUN_CALLS`,
`AEP_PLANNER_PER_COLLECTION_USD`, all `:?`-required by
`scripts/run_phase40_live.sh:94-96` — and the launcher echoes them to the
terminal, not into `collection.log`.

This is a consequence of a deliberate decision, not an oversight:
`docs/31` §4 keeps the planner configuration out of `RunConfig` because
`RunConfig._body()` folds every field into `config_digest`. The consequence was
not followed through. **Auditing this stage, I could not verify from the
archive what ceiling was actually in force** — only that the observed spend
(7 calls) is under the intended one. If a stage ever runs with the wrong cap,
the run directories will not show it.

**Recommendation:** write the resolved caps into the collection root as their
own file — not into `run-config.json`, which would move the digest.

### 5.3 `\HarnessLoc` was stale, and the gate was red at 733e1ff

Not part of this stage, found while running the gates this report required.
`check_paper_numbers.py` failed on *"numbers.tex matches the CSVs"*: 106 files
/ 28 166 lines against an actual 108 / 29 229. The drift began at `e8faab9`,
not at 733e1ff, and accumulated across seven commits. Regenerated in `4ab2a53`;
gates now 43 passed / 0 failed. **This is the third occurrence of this exact
staleness class** in this workstream, which is the point rather than the fix.

---

## 6. What this report does not conclude

- **Not that stage 10 passed.** Two criteria passed cleanly, one passed on a
  run the harness would now void, and one is unassessable as written.
- **Not that stage 10 failed.** Nothing in C1–C3 went wrong on its own terms.
- **Not that §9's stop rule has fired.** C4 has failed twice on its plain words
  and the condition is armed; whether that counts is a ruling this report puts
  to the author rather than takes.
- **Not anything about reachability.** §2's metric is untouched here. Amendment
  3 §5 already rules R's two declared ambiguities out as a result, and this
  report does not revive them.
- **Not that the cost model is validated.** No invoice was read.

---

## 7. Verification for this report

| | |
|---|---|
| HEAD assessed | `733e1ff`, tree clean |
| full suite | **2 350 passed, 34 skipped** on the final run (17 m 35 s). An earlier run in the same session returned 2 349 / 1 — `tests/test_lease.py::TestLeaseHardCap::test_lease_cap_prevents_zombie_renewal`, which asserts a sub-second Redis TTL is still alive after a 1 s sleep and so fails when the event loop is delayed under load. It passed **5 / 5** in isolation, passed in the run before, and passed in the final run. Recorded because a suite that is green only sometimes should be in the record as such. |
| `tests/test_scripted_plan_is_frozen.py` | 59 passed |
| `tests/test_interactive_loop.py` | 14 passed |
| `tests/test_last_outcome_is_arm_neutral.py` | 9 passed |
| `scripts/check_paper_numbers.py` | 42 / 1 at `733e1ff`; **43 passed, 0 failed** after `4ab2a53` |
| `scripts/check_line_endings.py` | clean, no file changed its dominant line ending |
| builds | all four rebuilt, supplementaries first; main **24 pp**, main-anon 23 pp, supplementary 7 pp, supplementary-anon 7 pp; zero `??` in all four |
| `.env` | `D:\personal\AEP\.env`, outside every git work tree (`git rev-parse` fails from that directory), untracked, **mode 777** — still world-writable, and it holds an 84-character key |
| live calls this session | **none**; spend unchanged at USD 0.00154520 |

`AEP_PLANNER_SNAPSHOT` is present in `.env` but **empty**, so it is unset in
effect and amendment 1 stands: the snapshot recorded in every transcript
(`2026-07-09`) is read from the archived ARM JSON by
`scripts/run_phase40_live.sh:80-88`, which also asserts it differs from the
deployment alias before running.
