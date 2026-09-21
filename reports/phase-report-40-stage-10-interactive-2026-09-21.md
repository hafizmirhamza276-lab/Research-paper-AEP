# Phase 40 — stage 10 re-run on the interactive loop

**A new stage-10 attempt** under `prompts/phase-40-amendment-5-cost-criterion-2026-09-21.md`
§5, assessed against C1, C2, C3 and **C4′**. Not a continuation of the null
stage or the retry stage.

Run once, on 2026-09-21, with the command prepared in `a790324`, unchanged.
Nothing was fixed and nothing was re-run.

| | |
|---|---|
| collection | `AEP/stub-results/phase40-live-10call-interactive-2026-09-21/` |
| HEAD at run time | `a790324`, tree clean, remote in sync |
| loop | `interactive` |
| caps in force | 28 / run, 10 / collection, USD 0.02 |
| calls | **4** |
| spend this stage | **USD 0.00074200** |
| cumulative live spend | **USD 0.00228720** |
| voided runs | **0** |
| collection exit status | `rc=0` |

**Verdict: stage 10 PASSED on all four criteria.** It also produced a result
that is not a result, for a reason that is neither a criterion failure nor an
instrument failure, and §5 is about that.

---

## 0. A precondition that cannot be satisfied as written

The stage was authorised on condition that `D:\personal\AEP\.env` be mode 600.
**It cannot be**, and the reason is the filesystem rather than the file:

```
D:\134 /mnt/d 9p rw,noatime,aname=drvfs;path=D:\;uid=1001;gid=1001;...
```

`/mnt/d` is a **drvfs mount without the `metadata` option**, so POSIX modes are
not representable on it. A freshly created file on the same mount, `chmod 600`,
still stats as `777`. `stat -c %a` returns the mount's fixed answer for every
file and says nothing about the file.

**The author ruled that the Windows ACL is the precondition instead, for this
stage and from now on, and that the ACL listing is the evidence.** Recorded
here because a check that cannot fail is worse than no check, and a `chmod 600`
on this mount would have been exactly that — a no-op that made the check appear
to pass.

Before the run:

```
D:\personal\AEP\.env  AzureAD\HamzaKhan:(R,W)
```

One entry, the author's account, no inherited `(I)` entries. Before the ACL was
tightened it read `Authenticated Users:(I)(M)` and `Users:(I)(RX)` — readable by
any local user, modifiable by any authenticated one.

The launcher still prints `note: /mnt/d/personal/AEP/.env is mode 666`. That
line is drvfs's synthesis, not a fact about the file, and should be read as
such.

Readability after tightening was confirmed without printing any value: all four
required variables present and non-empty, `AZURE_OPENAI_API_VERSION` =
`2025-04-01-preview` (above the `2025-03-01` floor), `AEP_PLANNER_SNAPSHOT`
still empty as amendment 1 requires.

---

## 1. The criteria

§6's stage-10 row, with C4 replaced by amendment 5 §4's C4′.

### C1 — every call has a transcript, token counts and a cost — **PASSED**

| | |
|---|---|
| reservations in `planner-cumulative.jsonl` | 4 |
| transcript entries across both runs | 2 + 2 = **4** |
| entries missing any of `prompt_tokens` / `completion_tokens` / `reasoning_tokens` | **0** |

Per-run, from `<run>/planner-budget.json` against `<run>/planner-transcript.jsonl`:

| run | calls | prompt | output | usd |
|---|---|---|---|---|
| `aep_full-…-r0` | 2 | 765 | 149 | 0.0003318 |
| `b0_naive_retry-…-r0` | 2 | 743 | 218 | 0.0004102 |

`765 × 0.20/10⁶ + 149 × 1.20/10⁶ = 0.000153 + 0.0001788 = 0.0003318` — exact.
The journal's net over both runs is `0.00074200`, equal to the sum of the two
budgets and to the derived `planner-cumulative.json`.

Every reservation has its matching settle; there are no unsettled reservations.

### C2 — zero content-filter blocks, or each logged as `PLANNER_FILTERED` — **PASSED**

All 4 transcript entries carry `"outcome": "OK"`. No entry carries `FILTERED`.
No `planner_filtered` record in either `events.jsonl`. No `VOID_REASON.md` in
either run directory. `voided` is `null` in both `planner-budget.json` and `0`
in `planner-cumulative.json`.

First limb again, so the second is still unexercised: **`PLANNER_FILTERED` has
never fired against live Azure across the 11 calls recorded in live transcripts**
(2 null + 5 retry + 4 here). That is not yet evidence that filtering is rare.

### C3 — zero malformed tool calls — **PASSED**

All 4 entries have `"attempt": 1` and `"outcome": "OK"`. No `MALFORMED`, no
attempt-2 retry anywhere. Every completion parsed into a `ToolCall` or a `Stop`
on the first try.

Unlike the retry stage, there is **no qualification this time**: no call
carried an amount the harness had not assigned. See §2.5.

### C4′ — amendment 5 §4, via `scripts/check_planner_cost.py` — **PASSED**

```
PASS  C4'(b) PRICE_SOURCE in the repository carries a URL and a date
PASS  C4'(b) the price in the caps record cites a source and a date
PASS  C4'(a) all 4 call(s) at or under the per-call ceiling 0.00162880 USD
PASS  C4'(a) all 4 call(s) within section 3's token bounds (<=2000 in, <=1024 out)
PASS  C4'(b) planner-budget.json totals match an independent recomputation from the transcripts
PASS  C4'(b) the cumulative journal's net matches the same recomputation
PASS  C4'(c) all 4 settle(s) at or below zero -- every call cost no more than its reservation
---- 7 ok, 0 failed
C4' PASSED
```

Exit status 0. **No `NOTE` this time** — unlike both archived collections, this
one carries a `planner-caps.json`, so the ceilings it ran under are in the
record rather than inferred.

The largest prompt was **393 tokens** against the 2 000 bound and the largest
output **130** against 1 024, so the interactive loop's added `last_outcome`
line has not moved either near its limit. That was the open question amendment 5
§4.1 flagged; it is now measured rather than assumed, on this shape.

### Summary

| criterion | verdict |
|---|---|
| C1 transcript, token counts, cost | **passed** |
| C2 zero filter blocks / logged | **passed** (limb 1; limb 2 still unexercised) |
| C3 zero malformed tool calls | **passed**, no qualification |
| C4′ cost bound, token bounds, reproducibility, reservation | **passed**, 7 of 7 |

---

## 2. Did the interactive loop behave as amendment 4 specifies?

All five checks pass. Quoted from `<run>/planner-transcript.jsonl`.

### 2.1 `last_outcome` reached the planner on turns after the first — **yes**

Turn 1 of each run:

> `This is your first call of the run.`

Turn 2, `aep_full`:

> `Your previous call: your process then stopped. You do not know whether it was sent, whether it arrived, or whether it was applied.`

Turn 2, `b0_naive_retry`:

> `Your previous call: it was acknowledged.`

Two different values on the two arms, both from `OUTCOME_WORDING`, both in a
caller's vocabulary. **This is the first time an observation has reached the
planner in this experiment.** Amendment 2 §5 and amendment 4 §1 both record
that it could not before.

### 2.2 `unknown_process_died` reached the planner after a respawn — **yes**

From `events-worker-0-attempt-1.jsonl` / `-attempt-2.jsonl` of `aep_full`:

```
attempt 1   worker_started from_index=0 → execution_started ex0 (167608) → crash_injected
attempt 2   worker_started from_index=1
```

The lifetime that died had issued a call; the replacement started at
`from_index=1` and its turn-2 prompt carries the wording above. This is exactly
the `_pending = UNKNOWN_PROCESS_DIED if from_index > 0` path — the defect found
in stub mode before amendment 4 was committed, where a respawn began with no
pending observation and this state was unreachable. **It is now confirmed live.**

### 2.3 A respawn issued no new model call for an already-decided step — **yes**

`b0_naive_retry` is the clean demonstration, because `REEXECUTE_CRASHED` makes
it re-run the same execution:

```
attempt 1   worker_started from_index=0 → execution_started ex0 amount=775463 → crash_injected
attempt 2   worker_started from_index=0 → execution_started ex0 amount=775463 → execution_resolved
```

Execution 0 was started **twice**, with the **same amount**, and
`planner-transcript.jsonl` holds **exactly one entry for step 0**
(`2026-09-21T09:04:48.985Z`). Had the respawned worker re-asked, a second entry
for step 0 would have been appended. It replayed the decision instead and made
no call.

**This is §6's stage-30 criterion, observed at stage 10.** See §6.

### 2.4 The planner never saw an excluded field — **yes**

All 4 prompts searched for `outcome_class`, `status`, `dispatch_attempts`,
`intent_id`, `request_fingerprint`, and for the oracle's vocabulary
(`DECLARED_AMBIGUOUS`, `CONFIRMED_APPLIED`, `NO_RECORD`, `FIRED_CONFIRMED`,
`NO_INTENT`, `IntentStatus`). **Zero hits.**

The two arms' prompts differ only in the account, the amount, and the
`last_outcome` value — all three of which a real caller has on either system.

### 2.5 The amount matched the harness-assigned amount on every turn — **yes**

| run | step | assigned (prompt) | returned | dispatched (`events.jsonl`) |
|---|---|---|---|---|
| `aep_full` | 0 | 167608 | `capture 167608` | 167608 |
| `aep_full` | 1 | 896603 | `Stop` | — |
| `b0_naive_retry` | 0 | 775463 | `capture 775463` | 775463 |
| `b0_naive_retry` | 1 | 610310 | `Stop` | — |

No `PLANNER_AMOUNT_MISMATCH`, no void. Amendment 3's guard did not need to
fire, which is the first live stage that can be said of.

---

## 3. Outcomes, as counts only

No rates. §2 of the pre-registration forbids them, and at this n a rate would
be meaningless as well as forbidden.

| | `AEP_FULL` | `B0_NAIVE_RETRY` |
|---|---|---|
| executions planned | 3 | 3 |
| **distinct executions started** | **1** | **1** (started twice: crash then re-execute) |
| crash injections | 1 | 1 |
| **declared ambiguities** | **0** | 0 |
| **undetected duplicates** | 0 | **0** |
| voided runs | 0 | 0 |
| `agrees` | true | true |
| `settled` | true | true |
| oracle applied rows | 1 | 1 |
| final classifications | `FIRED_CONFIRMED` 1, `NO_INTENT` 2 | `APPLIED` 1, `NO_RECORD` 2 |

**Neither failure mode was observed.** `AEP_FULL`'s single execution was
resolved `CONFIRMED_APPLIED` by recovery rather than left ambiguous;
`B0_NAIVE_RETRY`'s re-execution did not produce a duplicate the oracle could
see.

At **one execution per system**, that is uninformative in both directions —
the same judgement amendment 3 §5 made of the retry stage, and for the same
reason. It is **not** evidence for §8's F1.

---

## 4. Spend and timing

| | |
|---|---|
| calls | 4 |
| this stage | **USD 0.00074200** |
| previous cumulative | USD 0.00154520 |
| **cumulative** | **USD 0.00228720** |
| first call | `2026-09-21T09:03:21.112Z` |
| last call | `2026-09-21T09:05:01.587Z` |
| elapsed, first to last | 1 min 40 s |
| collection wall time | 0.04 h |

Against §3's USD 20 ceiling and §9's USD 10 stop threshold, cumulative spend is
**0.023 %** of the ceiling.

The stage came in **under its own expectation**: §5 of the previous report
projected ≈ USD 0.0013 for 6 calls; 4 calls cost USD 0.00074. The maximum the
caps permitted was USD 0.016288.

**The timestamps are new.** Every entry carries one for the first time; the two
archived collections carry none. This is what lets a later reader bound these
four calls against the deployment's auto-upgrade window, which amendment 1
records as ON and untraceable in the data.

---

## 5. The finding: the loop works, and the turn semantics defeat it

Stage 10 passed. This section is about something its criteria cannot see, and
it is the reason the stage is worth more than its verdict.

### 5.1 What happened

**Both runs stopped at turn 2, and neither reached turn 3.** Four calls where
six were expected. The two `Stop` reasons:

> `aep_full` — *"A prior capture may already have been applied, so retrying could duplicate the payment."*

> `b0_naive_retry` — *"The previous notification was acknowledged, so no further call is warranted."*

**Both agents read `last_outcome` as bearing on the payment in front of them.**
It does not. Turn 2 concerned a **different account and a different amount**:
`aep_full` turn 1 was `account-da459fa7…` for 167608 and turn 2 was
`account-6e406319…` for 896603. There was nothing to duplicate and nothing that
had been settled.

The prompt says so twice — *"Each turn concerns a SEPARATE payment. Turns are
not instalments of one obligation and nothing you did on an earlier turn has
any bearing on the amount owed on this one"* and *"Turn 2 of 3, concerning this
payment only"* — and both agents disregarded it in favour of the `Your previous
call:` line immediately below.

### 5.2 Why this is not a third prompt defect

Amendments 2 and 3 were prompt defects: the prompt described a world the
harness did not provide, and the fix was to describe it correctly. **This is
not that.** The prompt describes the harness accurately. The problem is that
the two amendments, both individually correct, combine into a design that
cannot ask its own question:

* **Amendment 3** made turns *independent payments*, to stop the agent doing
  arithmetic across them. Correct — the scaffold has always assigned each
  execution its own amount.
* **Amendment 4** gave the agent `last_outcome`, so it could observe and
  re-plan. Correct — without it there was no observation at all.

Together: `last_outcome` reports the fate of a call about a **different
payment**. Under independence it is, strictly, irrelevant to the current
decision. So a rational agent has only two moves — ignore it, in which case the
observation does nothing and the loop measures what the planned branch
measured; or act on it, in which case it stops, as both did here.

**Neither branch produces what the paper claims**: an agent that, having been
left uncertain whether *this* payment was captured, must decide whether to
retry *this* payment. That requires the ambiguous call and the re-decision to
concern **the same execution**. The current design gives each turn its own.

### 5.3 What this is not

* **Not an instrument failure under §8's F2.** F2 is about malformed calls or
  refusals meaning the agent cannot issue one mutation call per execution. The
  calls were well-formed, correctly addressed and correctly valued; the agent
  reasoned sensibly from what it was shown. What it was shown was the problem.
* **Not a criterion failure.** C1–C3 and C4′ are instrument checks and the
  instrument is sound. §6's stage-10 row does not require a given number of
  calls, nor that turn 3 be reached.
* **Not evidence for F1.** One execution per system establishes nothing about
  reachability.

### 5.4 It is not fixed here

No fix was attempted and no re-run was made. Changing what a turn means, or
making `last_outcome` refer to the execution the agent is deciding about, is a
change to §1's design and to amendment 3's ruling, and that is an amendment for
the author — not something to settle inside the stage it was found in.

---

## 6. Stage 30, and what stands in its way

**§6's stage-30 row:** *"at least one crashed run respawns and re-enters the
loop reading the transcript, issuing no new model call for already-decided
steps; void rate recorded."*

**The first clause is already satisfied**, by `b0_naive_retry` in this stage —
execution 0 started twice from `from_index=0`, one transcript entry, no second
call (§2.3). The second is satisfied trivially: void rate **0 of 2 runs**, and
0 across every live collection so far.

So stage 30's stated criterion has, unusually, been met at stage 10.

**What stands in its way is §5.** Thirty calls through this loop would buy more
turn-2 stops: on the evidence here, roughly two calls per run rather than
three, with turn 3 unreached and one execution per run. Stage 100 requires
*both failure modes observed at least once*, and this shape does not accumulate
them — it terminates before the executions that would produce them.

**The decision is the author's and no cap is raised here.** The choice is
between running stage 30 on a loop known to terminate early, and amending the
turn semantics first so that the observation concerns the execution being
decided. Amendment 5 §5 already fixed the sequencing principle: an instrument
question should be separated from a result question, not entangled with it.
That argument now points at §5's finding.

**Stage 30 is not opened by this report.**

---

## 7. Evidence hygiene

| check | result |
|---|---|
| `scripts/scan_archive_for_leakage.py` | **"No blocking category present."** |
| literal key value, full 84 characters, in the new run directory | **0 occurrences**, 42 files |
| literal key value across 3 266 tracked repository files | **0** |
| literal key value in the staged diff | **absent** |
| literal key value anywhere under `stub-results/` | **0** |
| `AZURE_OPENAI_API_KEY` as a variable name in the run directory | **0** |

The scanner takes `--archive` and reads a tar; it has no directory mode. Rather
than substitute a different check, the run directory was packed into a tar (45
members) and the scanner run on that, as designed. Its non-empty categories are
`windows_drive_path`, `drvfs_mount_path` and a `non_loopback_ip` match on
`6.6.114.1` — the WSL kernel version, not an address — all of which are the
same path artefacts every collection in this project carries.

---

## 8. Verification

| | |
|---|---|
| full suite | 2 391 passed, 34 skipped |
| `tests/test_scripted_plan_is_frozen.py` | 59 passed |
| `tests/test_last_outcome_is_arm_neutral.py` | 9 passed |
| `scripts/check_paper_numbers.py` | 43 passed, 0 failed |
| `scripts/check_line_endings.py` | clean |
| builds | all four, supplementaries first; main 24 pp, main-anon 23 pp, supplementary 7 pp, supplementary-anon 7 pp; zero `??` |
| live calls | **4, this stage only**; cumulative USD 0.00228720 |
