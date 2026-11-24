# Phase 40 — clause 1's reachability, the run-count derivation, and stage 100 prepared

**No live call.** Cumulative live spend unchanged at **USD 0.00359020**. The one
collection here is stub mode: 24 calls, **USD 0.00**.

---

## 1. Is amendment 6 §9 clause 1 reachable at all?

> **Clause 1:** *"every decision that was made and observed is replayed with no
> model call."*

**Answer: structurally unreachable in the pre-registered regime.** Not
"unreached so far" — it cannot happen, and the reason is a two-line
interaction between the resume rule and the scaffold filter.

### 1.1 What has to be true for a decision to be observed

`worker.py` calls `driver.observe(...)` only after `runner.execute(...)` returns
or raises. A `Stop` executes nothing, so it can never be observed. A dispatch
that is `SIGKILL`ed mid-flight never returns, so it can never be observed
either. **A decision is observed only if it was dispatched and the worker
survived it.**

### 1.2 The two lines that make it unreachable

```python
# runner.py, resume_from_index  -- where the replacement worker starts
if _agent_owns_redispatch():
    return last_started, "resume_for_agent_redecision"
```

```python
# agent_loop.py, InteractiveDriver.__init__  -- what that worker walks
if item.execution_index >= from_index
```

And the crash suppression, which un-arms **exactly** the resumed execution:

```python
resumed = {item.execution_id for item in items
           if item.execution_index == from_index}
remaining_crashes = [e for e in remaining_crashes if e not in resumed]
```

### 1.3 The argument

Let lifetime *n* start at `F_n` and die at `last_started_n = k_n`.

1. **The worker always dies strictly above where it started.** At `p(crash)=1.0`
   every execution in the slice is crash-armed except the resumed one, which is
   at index `F_n` exactly. The driver walks indices in increasing order, so the
   first armed execution it reaches is `F_n + 1`. Hence `k_n > F_n`.
   *(On lifetime 1 there is no suppression, so it dies at index 0 — its first
   execution — having observed nothing.)*
2. **No decision at index `k_n` can be observed.** That execution is armed, so
   its dispatch is killed before `observe()`.
3. **Therefore every observation in lifetime *n* lies at an index `j` with
   `F_n ≤ j < k_n`.**
4. **The next lifetime starts at `F_{n+1} = k_n > j`**, and `from_index` is
   non-decreasing thereafter.
5. **The scaffold filter is `execution_index >= from_index`**, so every
   observed decision is excluded from lifetime *n+1* and from every lifetime
   after it. ∎

No later lifetime ever *sees* a made-and-observed decision, so none can replay
one. Clause 1 has no reachable instance.

### 1.4 It is not the crash rate — it is the resume rule

Step 1 uses `p(crash)=1.0`, but the conclusion does not depend on it. At any
crash rate the worker dies at some index `k_n ≥ F_n`, everything it observed is
below `k_n`, and `F_{n+1} = k_n` excludes all of it. **Lowering the crash
probability would not make clause 1 reachable.** Nor would a different agent:
every branch — dispatch again, decline, stop — either ends the run or advances
`from_index` past what was observed.

### 1.5 Checked against the two collections that produced observations

Stage 30 produced no observations at all, so it is silent on this. The
amendment-6 stub run did produce them, across four lifetimes:

| run | lifetimes `(attempt, from_index)` | observations `(step, decision)` | a later lifetime whose scaffold contains one |
|---|---|---|---|
| `aep_full` | `(1,0) (2,0) (3,1) (4,2)` | `(0,1)`, `(2,1)` | **NONE** |
| `b0_naive_retry` | `(1,0) (2,0) (3,1) (4,2)` | `(0,1)`, `(2,1)` | **NONE** |

`(0,1)` was observed in lifetime 2; lifetimes 3 and 4 start at 1 and 2, both
above 0. `(2,1)` was observed in lifetime 4, which is the last. Both runs ended
`worker_finished`.

**A correction to my own first probe.** It compared every observation against
every `from_index`, including lifetimes that ran *before* the observation
existed, and reported four hits. Ordering-aware, there are none. The first
answer was wrong and is recorded here because it was wrong in the direction of
a false positive.

### 1.6 A note on what amendment 6 did

Amendment 6 created clause 1 and made it unreachable in the same change. Before
it, a crashed decision was replayed, and §6's *"no new model call for
already-decided steps"* was satisfied by exactly that replay. Amendment 6 §3.2
stopped replaying the crashed decision — correctly, because replaying it
re-dispatched without asking the agent — which left "made and observed" as the
only replayable category, and the resume rule excludes it.

**§6's original wording still passes**, and did at stage 30: the respawned
worker made no new call for `(step 0, decision 0)`. Only amendment 6's
restatement of it is unreachable.

---

## 2. Draft author ruling — NOT COMMITTED

Offered for the author's decision. It is **not** committed, and clause 1
remains recorded as *not exercised* until the author rules.

### 2.1 Is it a criterion correction or a structural amendment?

**A criterion correction, in the same class as amendment 5.** It is not a
structural amendment under amendment 6 §8, and it does not need to be:

* Amendment 6 §8 reserves further **structural** amendments for an instrument
  fault — a crash, a leak, or a malformed path. This is none of those, and the
  harness behaved exactly as amendment 6 specifies.
* Nothing in the instrument changes. No turn semantics, no prompt, no loop, no
  cap, no metric, no system descriptor. What changes is a **stage criterion's
  wording**, which is what amendment 5 changed when it replaced C4.
* The precedent is exact: C4 asked for a measurement no healthy stage could
  produce; clause 1 asks for an event no regime can produce. Both are
  arithmetic-or-logic errors inside a criterion rather than defects in what is
  being measured.

> ### DRAFT — Amendment 7: clause 1 cannot be met, and is withdrawn rather than passed
>
> **Amends `prompts/phase-40-amendment-6-same-payment-redecision-2026-09-21.md`
> §9.** A criterion correction, not a structural amendment: amendment 6 §8's
> closure of structural amendments is untouched, and nothing in the instrument
> changes.
>
> #### 1. What was asked
>
> Amendment 6 §9 clause 1 requires stage 30 to show that *"every decision that
> was made and observed is replayed with no model call."*
>
> #### 2. It cannot be met in the pre-registered regime
>
> A decision is observed only if it was dispatched and the worker survived it.
> `runner.resume_from_index` starts the replacement worker at
> `from_index = last_started`, and `InteractiveDriver` walks only executions
> with `execution_index >= from_index`. The crash suppression un-arms exactly
> the execution at `from_index`, so the worker always dies strictly above where
> it started, and every decision it observed lies strictly below where the next
> lifetime begins.
>
> **No later lifetime ever sees a made-and-observed decision, so none can
> replay one.** The conclusion does not depend on `p(crash)=1.0`; it follows
> from the resume rule at any crash rate, and no agent behaviour reaches it.
>
> Amendment 6 created the clause and made it unreachable in the same change:
> §3.2 stopped replaying the crashed decision, which left "made and observed"
> as the only replayable category, and the resume rule excludes it.
>
> #### 3. Clause 1 is NOT recorded as passed
>
> **Stage 30's record stands as PARTIAL.** Clause 1 was not met, is not met,
> and is not retroactively satisfied by this ruling. A criterion withdrawn
> because it cannot be met is not a criterion passed, and any later summary of
> stage 30 carries it as *not exercised, subsequently withdrawn as
> unreachable*.
>
> #### 4. What replaces it
>
> Clause 1 is **withdrawn**, not rewritten. The property it was reaching for —
> that a respawn costs no model call for work already decided — is already
> carried by §6's original wording, which stage 30 satisfied and which remains
> in force:
>
> > *"re-enters the loop reading the transcript, issuing no new model call for
> > already-decided steps."*
>
> Clauses 2 and 3 of amendment 6 §9 are unchanged and both passed at stage 30.
>
> **No replacement clause is invented.** A clause written now, after seeing
> which events this regime produces, would be a criterion fitted to the data —
> which is what §9's whole discipline exists to prevent.
>
> #### 5. §9's counter
>
> Clause 1 never failed; it was never reachable. **§9's "fails its criterion
> twice" counter is not incremented by it**, and this ruling does not reset any
> other counter. Amendment 5's ruling on C4 stands, and C4′'s counter remains
> at zero.
>
> #### 6. What is unchanged
>
> Everything. §1's design, §1.1, §2's metric and its prohibition on rates, §3's
> controls, §4, §5, §6's C1–C3 and C4′, §8's failure definitions, §9's spend and
> date limbs, and amendments 1–6 in full — including amendment 6 §8's closure of
> structural amendments, which this ruling does not reopen.

---

## 3. How many runs should stage 100 collect?

Derived, not chosen.

### 3.1 The constraints

| | source | says |
|---|---|---|
| **A** design | §1 | 10 runs per system, 20 total — the *full* design, which §6 assigns to **stage 300**, not 100 |
| **B** budget | §6 | the stage *is* its call budget: **100 calls** |
| **C** per-run cap | amendment 6 §7 | **20** calls per run, at **W = 1** |
| **D** integrity | §3 | a run that breaches the collection cap is **voided**, and a voided run is not a result |
| **E** symmetry | §1 | two systems, equal runs each → the total is **even** |

### 3.2 The binding one is D, not B

A collection of *N* runs has a worst case of `20N` calls. If `20N > 100`, a
legal-but-unlucky collection can hit the cap part-way through and **void the
run it fires on** — and stage 100's criterion needs observations, so a shape
whose worst case breaches its own budget risks destroying the evidence it is
there to collect.

```
N = 2   worst case  40  ≤ 100   ✓
N = 4   worst case  80  ≤ 100   ✓   <- largest even N that fits
N = 6   worst case 120  > 100   ✗
```

**N = 4, i.e. `runs-per-cell 2`: two runs per system.**

### 3.3 Against the observed rate

| source | calls per run |
|---|---|
| stage 10, live interactive | 2 |
| stage 30, live | 3 |
| amendment-6 stub | 6 |
| stub at `runs-per-cell 2` (§4) | **6, in all four runs** |

Expected for 4 runs: **12 calls** at the live rate, **24** at the stub rate.
Against a 100-call budget that is 12–24 % utilisation, and the cap is a genuine
backstop rather than a target. The gap between 6 and the 20-call per-run cap is
the headroom amendment 6 §7 derived for malformed retries and extra lifetimes.

### 3.4 What it is not

It is **not** the full design. Four runs is 2 of 10 per system; §1's 20 runs
belong to stage 300, and reaching them needs a per-run cap and a collection
budget that this derivation does not attempt. Noted, not solved: at stage 300
the same arithmetic gives `20N ≤ 300 → N ≤ 15`, short of 20, which is a tension
in §6's own staging that stage 300 will have to face. **No change is proposed
here.**

---

## 4. The launcher, and the stub run at the derived count

### 4.1 `runs-per-cell` is now an argument, defaulting to 1

`scripts/run_phase40_live.sh <results-root> [runs-per-cell]`.

**The default is the load-bearing half.** Stages 10 and 30 were launched
without the argument and their reports quote the shape it produced, so the
argument extends what the launcher can do and must not change what an earlier
command meant.

It uses `"${2-1}"`, **not** `"${2:-1}"`: an absent argument defaults, an
argument that is present but empty is refused. That distinction was found by
the parametrised refusal test — `run_phase40_live.sh "$ROOT" "$RUNS"` with
`RUNS` unset is the shape an operator actually writes, and silently collecting
one run per cell there is a collection they did not ask for.

Refused, all before the env file is read and before any network access:

```
runs-per-cell=0     -> REFUSING: runs-per-cell must be at least 1
runs-per-cell=abc   -> REFUSING: runs-per-cell must be a whole number, got 'abc'
runs-per-cell=-1    -> REFUSING: runs-per-cell must be a whole number, got '-1'
runs-per-cell=2.5   -> REFUSING: runs-per-cell must be a whole number, got '2.5'
runs-per-cell=''    -> REFUSING: runs-per-cell must be a whole number, got ''
```

`tests/test_live_launcher_runs_per_cell.py`, **18 tests**, including that the
rest of the collection shape — `--executions-per-run 3`, `--workers 1`, both
systems, the crash point, the endpoint, the keying — is untouched.

### 4.2 The stub run: `AEP/stub-results/phase40-stub-rpc2-2026-09-21/`

End to end against Docker and Redis under WSL2. **4 runs, 24 calls, 0 voided,
USD 0.00**, `rc=0`.

**Per-run directories** — 4, two per system, four distinct `run_id`s:

```
aep_full-…-r0        aep_full-…-r1
b0_naive_retry-…-r0  b0_naive_retry-…-r1
```

**The caps record** — one record at the collection root, one in each run
directory, every run's `in_force` identical to the collection's, and
`collection_caps_differ: false` on **all four**. That is the `O_EXCL`
first-writer rule working across more than two runs: one process created it and
the other three read it and agreed.

**Timestamps** — 24 of 24 entries carry an ISO-8601 UTC millisecond stamp,
schema `aep.agent.transcript/4`, non-decreasing within every run. First
`13:14:13.309Z`, last `13:24:31.682Z`.

**The collection-wide counter** — the property more runs actually stress:

| | |
|---|---|
| journal lines | 48 (24 reservations + 24 settles) |
| **distinct keys** | **48 of 48** — no collision across runs |
| distinct `run_id`s in the journal | 4 |
| reservations == transcript entries | 24 == 24 |
| derived snapshot | `calls=24 runs=4 voided=0` |
| sum of the four `planner-budget.json` | **24**, six per run |
| counter == sum of runs == reservations | **true** |

**Outcomes, counts only** (§2 — stub mode, not a result):

| run | crashes | re-dispatched | declined | `resume_reexecuting_crashed` | declared amb. | undetected dupes | applied |
|---|---|---|---|---|---|---|---|
| `AEP_FULL` r0 | 3 | 2 | 1 | **0** | 3 | 0 | 0 |
| `AEP_FULL` r1 | 3 | 2 | 1 | **0** | 3 | 0 | 0 |
| `B0_NAIVE_RETRY` r0 | 3 | 2 | 1 | **0** | 0 | 0 | 2 |
| `B0_NAIVE_RETRY` r1 | 3 | 2 | 1 | **0** | 0 | 0 | **3** |

`agrees=true` on all four. The two B0 runs differ (2 applied vs 3), which is
the per-repetition seed doing its job rather than four copies of one run.

---

## 5. The stage-100 command, prepared and NOT run

### 5.1 Caps

| | value | derivation |
|---|---|---|
| `AEP_PLANNER_PER_RUN_CALLS` | **20** | amendment 6 §7, `(3×2 + 4) × 2 × 1` |
| `AEP_PLANNER_PER_COLLECTION_CALLS` | **100** | the stage is its call budget |
| `AEP_PLANNER_PER_COLLECTION_USD` | **0.20** | above the `100 × 0.0016288 = 0.16288` the call cap permits, so the call cap binds first and the USD ceiling stays a backstop |
| runs-per-cell | **2** | §3.2 — largest even *N* with `20N ≤ 100` |

### 5.2 Expected and maximum spend

Stage 30's live tokens: 2 435 prompt and 680 output over 6 calls — 405.8 and
113.3 per call.

```
per call   405.8 × 0.20/10⁶ + 113.3 × 1.20/10⁶ = 0.00021712
```

| | |
|---|---|
| **expected**, 24 calls (stub rate) | **≈ USD 0.0052** |
| expected, 12 calls (live rate) | ≈ USD 0.0026 |
| **maximum**, 100 calls at the current price | **USD 0.16288** |
| maximum at the stale price | USD 0.81440 |
| cumulative afterwards | ≈ **USD 0.0088** expected, ≤ **USD 0.1665** worst case |

§6's stage-100 criterion requires cumulative spend **< USD 1**; the worst case
is 17 % of that. §9's USD 10 threshold and §3's USD 20 ceiling are untouched.

### 5.3 The command

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
    /mnt/d/personal/AEP/stub-results/phase40-live-100call-interactive-2026-09-22 2
'
```

The trailing `2` is the new argument. Prerequisites are the same as stage 30's
and were all green when the stub run above was made: both containers healthy
under WSL2's native Docker, `aep:test-instance-marker` set in DB 15, port 8099
free, `.env` ACL restricted to one account.

**This command has not been run. No cap is raised by this report and stage 100
is not opened.**

---

## 6. Verification

| | |
|---|---|
| full suite | **2 456 passed, 34 skipped** |
| `tests/test_live_launcher_runs_per_cell.py` | **18 passed** |
| `tests/test_scripted_plan_is_frozen.py` | **59 passed** |
| `tests/test_last_outcome_is_arm_neutral.py` | **12 passed** |
| `scripts/check_paper_numbers.py` | 43 passed, 0 failed |
| `scripts/check_line_endings.py` | clean |
| builds | all four, supplementaries first; main **24 pp**, main-anon 23 pp, supplementary 7 pp, supplementary-anon 7 pp; zero `??` |
| live calls | **none**; cumulative USD 0.00359020 |
