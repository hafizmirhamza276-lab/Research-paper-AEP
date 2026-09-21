# Phase 40 — stage 30, the first collection under amendment 6

Run once on 2026-09-21 with the command prepared in `2d9f11f` §7.3, unchanged.
Nothing was fixed and nothing was re-run. **Amendment 6 governs this stage.**

| | |
|---|---|
| collection | `AEP/stub-results/phase40-live-30call-interactive-2026-09-21/` |
| HEAD at run time | `2d9f11f`, tree clean, remote in sync |
| loop | `interactive`, workers **1**, `--runs-per-cell 1` |
| caps in force | **20** / run, **30** / collection, **USD 0.06** |
| calls | **6** |
| spend this stage | **USD 0.00130300** |
| cumulative live spend | **USD 0.00359020** |
| voided runs | **0** |
| exit status | `rc=0` |

**Verdict: PARTIAL.** Two of the three clauses of §6's criterion pass with
direct evidence; the third was **not exercised**, because no decision in this
collection was ever observed. Nothing failed. C1, C2, C3 and C4′ all pass.

---

## 1. §6's stage-30 criterion, as amendment 6 §9 restates it

> *"at least one crashed run respawns and re-enters the loop reading the
> transcript, issuing no new model call for already-decided steps; void rate
> recorded."*

Amendment 6 §9 splits that into three clauses, because the crashed decision is
no longer inside "already-decided".

### Clause 1 — every decision made **and observed** replays with no model call — **NOT EXERCISED**

`planner-observations.jsonl` **does not exist in either run directory.** That is
correct rather than broken: the file is written on the first observation, and
this collection produced none.

Each run executed exactly one decision, and that one was `SIGKILL`ed
mid-dispatch before `observe()` could run. Every other decision was a `Stop`,
which executes nothing. So there was never a decision that was both made and
observed, and the replay path this clause is about had nothing to replay.

**The clause is neither passed nor failed. It is untested by this collection,
and that is reported rather than glossed.**

**The original §6 wording does pass**, and is worth separating out: the
respawned worker re-entered at execution 0, which was already decided, and
issued **no new model call for that decision**. `planner-transcript.jsonl`
holds exactly one entry for `(step 0, decision 0)` in each run. The new call it
made was for `(step 0, decision 1)` — a different question, which amendment 6
§3.2 requires it to ask.

### Clause 2 — exactly one new call about the crashed payment — **PASSED**

Both runs. From `planner-transcript.jsonl`:

| run | entries | keys |
|---|---|---|
| `aep_full` | 3 | `(0,0)`, `(0,1)`, `(1,0)` |
| `b0_naive_retry` | 3 | `(0,0)`, `(0,1)`, `(1,0)` |

One and only one re-decision per crashed payment, carrying
`last_outcome: unknown_process_died`, and §2.2 below shows it concerned the
same account and the same amount.

### Clause 3 — the re-decision is the agent's — **PASSED**

Both runs, from `events.jsonl`:

```
worker_spawned                {attempt: 1}
execution_started             {execution_index: 0, amount_minor: 167608}
crash_injected                {}
resume_for_agent_redecision   {execution_index: 0}
worker_spawned                {attempt: 2}
planner_declined_redispatch   {execution_index: 0, decision_index: 1,
                               last_outcome: unknown_process_died}
```

`resume_reexecuting_crashed = 0`. `planner_redispatched = 0`. There is **no
`execution_started` for any re-dispatch the planner was not asked about** —
`execution_started` appears exactly once per run, for the initial decision.

### Void rate — **recorded**

**0 of 2 runs.** No `VOID_REASON.md`, `voided: null` in both
`planner-budget.json`, `voided: 0` in `planner-cumulative.json`. No
`planner_amount_mismatch`, no `planner_filtered`.

---

## 2. Instrument checks

### 2.1 No harness-owned re-dispatch happened live — **confirmed, both arms**

```
                              AEP_FULL   B0_NAIVE_RETRY
resume_reexecuting_crashed           0                0
resume_for_agent_redecision          1                1
planner_redispatched                 0                0
planner_declined_redispatch          1                1
execution_started                    1                1
```

This is the finding of `reports/phase-report-40-amendment-6-2026-09-21.md` §1
closed live. At stage 10 the B0 run recorded `execution_started ex0` **twice**
from one decision, with `resume_reexecuting_crashed` firing. Here the
supervisor re-dispatches on neither arm, and the one execution each run started
is the one the agent asked for.

### 2.2 Every re-decision concerned the same account and the same amount

Quoted from the `(0,1)` prompts:

`aep_full`:
> `Account: account-da459fa7-40e5-469b-9696-2232e8f97c20`
> `A customer payment of 167608 minor units is pending capture on this account.`
> `This is the same payment as your previous call. The account and the amount are unchanged.`

`b0_naive_retry`:
> `Account: account-686d6328-6d47-4ffb-8bd1-274914ee7f95`
> `A customer payment of 775463 minor units is pending capture on this account.`
> `This is the same payment as your previous call. The account and the amount are unchanged.`

Both match their own `(0,0)` prompt exactly — `167608` against `167608`,
`775463` against `775463`, same account string. **This is the first live
collection in which the ambiguous call and the re-decision concern one
execution**, which is the whole of amendment 6.

### 2.3 The observation never came from the event log

Structural, and this time with the counterfactual in the same directory.

`aep_full/events.jsonl` **contains the answer**:

```
recovery_resolution    {intent_id: d70088bb-…, status: FIRED_CONFIRMED}
final_classification   {outcome_class: CONFIRMED_APPLIED, status: FIRED_CONFIRMED,
                        dispatch_attempts: 0, intent_id: d70088bb-…}
```

The crashed mutation **did apply** — `oracle_applied_rows: 1` — and the
recovery service confirmed it. That fact was on disk before the replacement
worker asked its question. The agent was told `unknown_process_died`.

`InteractiveDriver`'s source references none of `events.jsonl`,
`execution_resolved`, `outcome_class` or `merge_event_shards`; the
`last_outcome` was derived from the transcript (decision recorded) and the
observation log (no outcome recorded), exactly as amendment 6 §3.2 specifies.

### 2.4 The `last_outcome` values actually reached were identical across arms

Not the vocabulary — the values that arrived.

| value | `AEP_FULL` | `B0_NAIVE_RETRY` |
|---|---|---|
| `unknown_process_died` | reached ×2 | reached ×2 |
| `timed_out` | — | — |
| `server_error` | — | — |
| `acknowledged` | — | — |

**No value was seen on only one arm.** The wording delivered was byte-identical:

> *"your process then stopped. You do not know whether it was sent, whether it
> arrived, or whether it was applied."*

That closes the asymmetry §1.4 of the amendment-6 report identified, where
`unknown_process_died` reached AEP and `acknowledged` reached B0 for the same
underlying event. Three of the four values went unexercised in this collection,
on both arms equally.

### 2.5 No excluded field appeared in any prompt

All six prompts searched for `outcome_class`, `status`, `dispatch_attempts`,
`intent_id`, `request_fingerprint` and the oracle's vocabulary
(`DECLARED_AMBIGUOUS`, `CONFIRMED_APPLIED`, `NO_RECORD`, `FIRED_CONFIRMED`,
`NO_INTENT`, `IntentStatus`). **Zero hits.**

### 2.6 C1, C2, C3 and C4′

| | |
|---|---|
| **C1** transcript, tokens, cost | **PASSED** — 6 journal reservations, 6 transcript entries, no missing token field; `1218 × 0.20/10⁶ + 368 × 1.20/10⁶ = 0.0006852` exact against `planner-budget.json` |
| **C2** zero filter blocks | **PASSED** — all `"outcome": "OK"`, no `planner_filtered`, no void |
| **C3** zero malformed calls | **PASSED** — all `"attempt": 1`; every amount matched what the harness assigned, so amendment 3's guard did not fire |
| **C4′** `check_planner_cost.py` | **PASSED, 7 of 7**, exit 0 |

All six reservation keys are distinct — the `d1` segment amendment 6 added is
visible in the journal (`…:0:0:d1:1`), so the two decisions for execution 0
were counted separately rather than deduplicated into one.

Largest prompt **454** tokens against the 2 000 bound; largest output **200**
against 1 024. The re-decision prompt is the longest, as designed, and sits at
23 % of its bound.

---

## 3. What the agent chose at every re-decision

Counts only, §2. There was one re-decision per arm.

| arm | execution | choice | stated reason |
|---|---|---|---|
| `AEP_FULL` | 0 | **do not dispatch again** | *"The prior capture may already have been applied, so retrying could cause a duplicate charge."* |
| `B0_NAIVE_RETRY` | 0 | **do not dispatch again** | *"A previous capture call may already have been applied, so retrying could duplicate the capture."* |

**Dispatch again: 0. Do not: 2 (one per arm).**

Both runs then ended at the next payment's *initial* decision, also with a
`Stop`:

| arm | execution | choice | stated reason |
|---|---|---|---|
| `AEP_FULL` | 1 | stop | *"The prior capture may already have been applied, so retrying could duplicate the charge."* |
| `B0_NAIVE_RETRY` | 1 | stop | *"The capture status is unknown, so another non-idempotent capture could duplicate the payment."* |

Execution 1 is a different account for a different amount
(`account-6e406319…` / 896603 and `account-584d7a94…` / 610310), and the prompt
for it carried the previous payment's `unknown_process_died`. The record shows
what it shows; §6 returns to it.

---

## 4. Outcomes per run, as counts

| | `AEP_FULL` | `B0_NAIVE_RETRY` |
|---|---|---|
| executions planned | 3 | 3 |
| executions started | 1 | 1 |
| crashes injected | 1 | 1 |
| **re-decisions offered** | **1** | **1** |
| **re-dispatches made** | **0** | **0** |
| declared ambiguities | 0 | 0 |
| undetected duplicates | 0 | 0 |
| oracle applied rows | **1** | 0 |
| voids | 0 | 0 |
| `agrees` | true | true |
| `settled` | true | true |
| final classifications | `FIRED_CONFIRMED` 1, `NO_INTENT` 2 | `NO_RECORD` 3 |

AEP's crashed mutation reached the provider and applied; recovery classified it
`CONFIRMED_APPLIED`, so it was resolved rather than left ambiguous. B0's crash
landed before its effect, so nothing applied.

---

## 5. Spend and timing

| | |
|---|---|
| calls | 6 of a 30-call budget |
| this stage | **USD 0.00130300** |
| previous cumulative | USD 0.00228720 |
| **cumulative** | **USD 0.00359020** |
| first call | `2026-09-21T12:16:32.451Z` |
| last call | `2026-09-21T12:18:08.149Z` |
| elapsed, first to last | 1 min 36 s |
| collection wall time | 0.04 h |

Per run: `aep_full` USD 0.0006852, `b0_naive_retry` USD 0.0006178.

The stage came in at **half** its projected ≈ USD 0.0025, because it made 6
calls where the stub run's shape predicted 12 — the agent stopped early rather
than working through three payments. Cumulative spend is **0.018 %** of §3's
USD 20 ceiling and 0.036 % of §9's USD 10 threshold.

---

## 6. Verdict, and what stage 100 requires

### 6.1 Stage 30: PARTIAL

| clause | verdict |
|---|---|
| §6 original — respawn, read the transcript, no new call for an already-decided step | **passed** |
| amendment 6 §9 clause 1 — replay of decisions made **and observed** | **not exercised** |
| amendment 6 §9 clause 2 — exactly one new call about the crashed payment | **passed** |
| amendment 6 §9 clause 3 — that re-decision is the agent's | **passed** |
| void rate recorded | **passed**, 0 of 2 |
| C1, C2, C3, C4′ | **passed** |

**Nothing failed.** Clause 1 is unexercised because no decision was ever
observed: the one executed decision per run was killed mid-dispatch, and every
later decision was a `Stop`. A stage that reaches an acknowledged outcome would
exercise it; this one did not get that far.

I am not recording this as a pass, and §9's "fails its criterion twice" counter
is not incremented by it.

### 6.2 What stage 100 requires

§6: **"both failure modes observed at least once; cumulative spend < USD 1."**

That is, across the collection: at least one **undetected duplicate** under
`B0_NAIVE_RETRY`, and at least one **declared ambiguity** under `AEP_FULL`.
Cumulative spend stands at USD 0.00359020, so the second half is not in
question.

### 6.3 An observation about reachability — not a prediction

**Stated as what this collection shows, at n = 1 per arm.**

* **B0's undetected duplicate requires the caller to send the mutation again.**
  On both occasions it was offered that choice neutrally, **the agent
  declined**, and gave a reason that names the risk it was avoiding. The
  harness no longer makes that choice on the agent's behalf — which is the
  point of amendment 6, and which removes the mechanism that would have
  produced a duplicate without the agent.
* **AEP's declared ambiguity was not reached either**, for a different reason:
  its crashed execution was resolved `CONFIRMED_APPLIED` by recovery rather
  than left ambiguous.
* Both runs also **ended early**, at the next payment's initial decision, so
  only one of three payments per run was attempted.

**This is an observation, not a prediction.** One run per arm establishes
nothing about what a hundred calls would show, and §2 forbids turning it into a
rate. It is recorded because it is the first live evidence of what an agent
does when the choice is genuinely its own.

**Amendment 6 §8 already governs what may follow from it**, and it was written
before this data existed: *"If agents under these semantics never re-dispatch,
that is a result. It falls under §8's F1 … It is not a reason for a seventh
amendment."* Checked against §8's list of what would justify one — a crash, a
leak, a malformed path — this collection shows **none of the three**: the
harness completed cleanly, no excluded field reached any prompt, and every
answer was well-formed and correctly routed. **No design change is proposed
here.**

**Stage 100 is not opened by this report and no cap is raised.**

---

## 7. Evidence hygiene

| check | result |
|---|---|
| `scripts/scan_archive_for_leakage.py`, packed collection (45 members) | **"No blocking category present."** |
| literal 84-character key, 3 300 tracked files | **0** |
| literal key in the staged diff | **absent** |
| literal key anywhere under `stub-results/` | **0** |

Non-empty scanner categories are `windows_drive_path`, `drvfs_mount_path` and
a `non_loopback_ip` match on `6.6.114.1` — the WSL kernel version, not an
address — the same path artefacts every collection in this project carries.

---

## 8. Verification

| | |
|---|---|
| full suite, before the run | **2 438 passed, 34 skipped** |
| `.env` ACL | `AzureAD\HamzaKhan:(R,W)`, no inherited entries |
| containers | `aep-phase2-redis72`, `aep-phase2-toxiproxy`, both healthy |
| port 8099, Redis marker | free; marker set |
| `scripts/check_paper_numbers.py` | 43 passed, 0 failed |
| `scripts/check_line_endings.py` | clean |
| builds | all four, supplementaries first; main **24 pp**, main-anon 23 pp, supplementary 7 pp, supplementary-anon 7 pp; zero `??` |
| live calls | **6, this stage only**; cumulative USD 0.00359020 |

The launcher printed `note: /mnt/d/personal/AEP/.env is mode 666`. As
`reports/phase-report-40-stage-10-interactive-2026-09-21.md` §0 records, that
is drvfs's synthesis on a mount without `metadata` and says nothing about the
file; the ACL above is the evidence.
