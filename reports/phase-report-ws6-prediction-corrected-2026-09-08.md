# WS-6 — pre-registration for the CORRECTED B5 cell

**8 September 2026.** Supplements `reports/phase-report-ws6-prediction-2026-09-07.md`
(`1fecb1f`). Committed **before any attempt-3 run exists**.

This is a re-registration, not a revision. The 09-07 pre-registration was
applied honestly and its §4 was followed; what changed is the **instrument**,
and because the repair changes what the collection measures, the cell is
registered again rather than re-read.

**The 2026-09-08 session (`0c6bcf4`) stands, unamended.** It is a complete,
honest record of a harness that was too deterministic. It is not deleted, not
corrected, and not superseded — it is evidence, and
`reports/phase-report-ws6-determinism-2026-09-08.md` is its reading.

---

## 1. Hypotheses — UNCHANGED

Restated verbatim in substance from `1fecb1f` §1. No hypothesis, threshold or
direction has been touched, and none may be after this file is committed.

* **H1** — at the crash points B4 and B5 can *both* be cut at, B5 reproduces
  B4's undetected-duplicate rate, run-clustered intervals overlapping.
* **H2** — the same for B5b against B4b's lost-effect rate.
* **H3** — neither B5 nor B5b declares ambiguity in any run. Predicted at
  **exactly zero**, structural, and one declared ambiguity refutes it.

## 2. What changed in the instrument, and only that

### 2.1 Every run gets its own provider seed

`RunProvider.start` rewrote `ledger_path` and nothing else, so all 120 runs ran
a provider seeded `20260908`. `MockLegacyAPI` draws its three fault decisions
from one `random.Random(config.seed)` per process, so every run replayed one
fault stream. Three of four cells produced a **single distinct outcome across
thirty runs**; the effective sample size was one fault pattern, not thirty runs.

It now calls `mock_api.supervisor.render_config(..., seed=...)` — the facility
that already existed, whose docstring was written because Session 3's D0(ii)
gate caught this same hazard and fixed only the ledger half of it. The seed
passed is **the run's own `RunConfig.seed`** (`20260908 + repetition`), so a run
is reproducible from its own record.

The record now carries `seed` and `provider_seed`, the latter **read back from
the config the provider was actually given** rather than restated from what the
driver intended — a seed that varies in the driver but never reaches the
provider is, in the outcome, indistinguishable from the defect it replaces.

**Per-run fault streams now vary. This is proven, not asserted**, and proven on
the fault stream rather than on the outcome:
`experiments/baselines/b5_temporal/prove_provider_seeding.py`, exit 0.

```
branch A: different seeds must give different fault streams
  seed 20260908 -> dfc78e24b12a0858
  seed 20260909 -> cb2122c4ceebfe35
  seed 20260910 -> 2428ff668118635f
  seed 20260911 -> e6bee18f47e61d91
  seed 20260912 -> 270f2b8edb56e9ae
  5 distinct signature(s) from 5 seeds          BRANCH A: True

branch B: the same seed must reproduce its stream exactly
  seed 20260908 first  -> dfc78e24b12a0858
  seed 20260908 repeat -> dfc78e24b12a0858      BRANCH B: True
```

Branch B is the one that matters for reproducibility: a generator that merely
varies is not enough, because a run must be replayable from the seed in its own
record. A "fix" that seeded from the clock would pass branch A and fail here.

**This proof failed the first time it was run, and the defect was in the
proof.** Its signature digested the client-observed HTTP statuses alongside the
provider's records, and those depend on whether the test client's socket timeout
fires before the provider's simulated timeout returns 504 — a race against
wall-clock, not a function of any seed. Two runs at seed 20260908 differed at
exactly one request (`504` versus a client-side sentinel `0`) **while the
provider's own decisions were byte-identical**. The signature now reads only the
provider's record, which is what the module's docstring always claimed it read.

This is recorded rather than quietly corrected because it is the third time in
this session that checking code was held to a lower standard than the code it
checks, and because a proof that fails for its own reasons is indistinguishable,
to a later reader, from the repair not working.

### 2.2 H1's units

`analyse_b5_agreement.py` compared B5's `undetected_duplicate_applications`
against a frozen rate whose numerator is `int(execution.is_undetected_duplicate)`
— a per-execution 0/1 indicator. It now reads `undetected_duplicate_executions`,
which `collect.py` writes into the session record.

**H2 was already units-consistent and needed no change.** Both its sides count
executions (`lost_effect_executions` against `lost_effect_rate`), and its
mapping is untouched.

**This was an edit to the verdict script after data existed** — the one edit the
ordering exists to prevent. It is recorded in that file's header with what the
script said before, what changed, and why: the mismatch was found by reading
`analyze.py`'s numerator definitions while establishing why three of four
intervals were zero-width — a question about the estimator, not the verdict —
and the correction moves H1's B5 numerator **down**, widening the gap that
produced `DISAGREES` rather than narrowing it.

**Nothing else in the script changed.** The stage ordering, the 20% pending
bound, the absent-point constant, the void prefix rule and H3's threshold are as
committed before any B5 data existed.

## 3. What is collected

Identical to `1fecb1f` §3.1. Nothing here is widened because the instrument was
repaired.

| | |
|---|---|
| stage | primary |
| crash point | `after_barrier_before_dispatch`, both endpoints |
| arms | `B5_TEMPORAL` (unlimited attempts), `B5B_TEMPORAL_AT_MOST_ONCE` (1) |
| runs | **120** — 4 cells × 30 |
| executions per run | 10 |
| Start-To-Close | **4000 ms**, the value fixed in `06d51b0` and unchanged |

The provider's fault configuration is unchanged: constant 2.0 s delay, 5% server
errors, 15% timeouts, 0% duplicate responses, `CALLER_REFERENCE` keying. **Only
the seed varies now, and it varies per run.**

## 4. Unit of analysis

**The run**, per `docs/26` §3 rule 6, unchanged. The run-clustered bootstrap
resamples runs, not executions.

**What the repair changes is whether that unit means anything.** In the
2026-09-08 session the thirty runs of a cell were thirty replays of one fault
pattern, so clustering on the run described nothing and the interval collapsed
to zero width. With per-run seeds the runs are distinct draws and the cluster is
the right unit again. **If a cell again returns a zero-width interval, that is a
signal the repair did not take, not a result** — and it must be reported as
such rather than published.

## 5. Stopping rule

Unchanged from `1fecb1f` §4, restated because this file must stand alone:

- **Fixed n.** 120 runs primary. **No inspect-and-extend.**
- **A session is void** if the engine or the provider restarts mid-collection,
  or the run count is short — **decided on the run count alone, before any
  outcome is read.**
- **No knob is tuned after seeing an outcome.** The Start-To-Close timeout is
  fixed and changing it voids the session.
- **`PENDING_AT_DEADLINE` above 20% of a cell's non-void runs** makes that cell
  uninformative; the fix is a re-registered timeout change, not a re-reading.
- **New, and specific to this repair:** a cell whose non-void runs are all
  identical is reported as **instrument-constrained, not as a result**. The
  2026-09-08 session is what that looks like, and it must not be published as a
  rate a second time.

## 6. The exact analysis to be run

Unchanged command; the mapping inside it is the correction in §2.2.

```
uv run --frozen --extra experiments python -m experiments.analyze \
    --results-root <session root>
uv run --frozen --extra experiments python scripts/analyse_b5_agreement.py \
    --session <session root>
```

**It has not been run against any data since the correction.** Re-reading the
2026-09-08 session with it would answer nothing: that session's fault stream was
fixed, so its H1 numerator is a different quantity computed over a degenerate
sample.

### 6.1 The prohibition above has teeth, and here is what breaks if it is ignored

**Recorded 8 September, after the corrected cell was read. Deliberately not
fixed.**

`cell_interval` reads `int(run.get(metric_field, 0))`. The 2026-09-08 session's
records **do not contain `undetected_duplicate_executions` at all** — the field
is absent in all 30 and all 28 runs of its two `B5_TEMPORAL` cells, because
`collect.py` only began writing it at `4f31c42`, after that session was
collected.

So running the **corrected** script against the **2026-09-08** session does not
fail, and does not warn. It silently computes **H1 = 0.0000** from a missing
field, and reports it beside a frozen B4 rate of 0.9333 as a `DISAGREES` with a
zero-width interval. Every part of that output would be an artefact of a field
that was never written.

This is why §6's prohibition is not a matter of taste. It is also why the
defect is recorded here, next to the prohibition, rather than in a bug list:
the two only make sense together.

**Not fixed**, for the reason the whole ordering exists — the script has now
read data, and a `KeyError`-on-missing-field change made afterwards would be an
edit to a verdict script after seeing results. If it is ever changed, it belongs
in its own pass with its own record, and the change would be to *refuse* a
missing metric field rather than to default it to zero.

## 7. The attempt budget — does the repair reset it?

`1fecb1f` §4 set **three attempts**, and defined an attempt as a session that
collects run data. Under it, attempt 1 (39 runs, voided) and attempt 2 (120
runs, complete) both count. **One would remain.**

**Decision: the corrected cell gets a fresh budget of three, and attempt 2 does
not count against it.** The reasoning, including what is uncomfortable about it:

**Why a reset is defensible here.** The budget bounds attempts *at a
measurement*. Attempt 2 did not measure this cell: its fault stream was fixed,
so it measured one draw thirty times. The corrected cell has never been
attempted. Spending a budget on attempts against a different instrument would
mean the corrected cell gets **one** attempt, and a single transient host
failure would end WS-6 as *"not collected on this host"* for a reason with
nothing to do with the science — a worse outcome, and one the budget was never
meant to produce.

**Why that is a loophole, and what closes it.** "Declare a repair, get three
more attempts" would let the budget be evaded indefinitely. Three things close
it here, and a future reset must satisfy the same three:

1. **The repair's effect is proven independently of any outcome.** The
   fault-stream proof shows the streams now differ and are reproducible, without
   reference to a duplicate rate or an agreement reading.
2. **The defect was identified from the code, not from the result.** The units
   mismatch came from reading `analyze.py`'s numerators; the seed defect came
   from asking why a bootstrap returned zero width. Neither began with the
   verdict being unwelcome, and the units correction makes the gap *wider*.
3. **This file is committed before any attempt-3 run exists**, and the stopping
   rule above is unchanged — so the reset buys attempts, not freedom to stop on
   a favourable reading.

**What does not reset.** The host-reliability evidence carries forward: attempt
1's failure mode (a non-detached launch) is closed and proven closed, and
attempt 2 demonstrated this host can hold a complete 2h 05m collection. If three
attempts at the corrected cell fail to produce a complete session, WS-6 is
reported as **not collected on this host**, with the defects found — the same
explicit cut `1fecb1f` §4 defined, and it is not resettable again by this
argument.

**Attempt 2 was not wasted, and it also did not measure the cell.** Both are
true, and the second is why this file exists.

## 7a. The secondary sweep: DEFERRED, with the trigger stated

**Decided 8 September, after the primary was read. Recorded here so the
registration and its disposition sit together, and so no registered cell is left
in an undecided state.**

`1fecb1f` §3.1 registers a **secondary sweep — 240 runs**, the remaining four
reachable crash points (`before_intent_write`, `mid_dispatch`,
`after_response_before_resolution`, `after_resolution_before_barrier`),
`NO_READBACK` only, both arms, 30 × 10. Its own condition was *"collected only
if the primary completes"* — **and the primary has completed**, so the
registration's trigger has fired and the cell cannot be left silent.

**Decision: deferred, not cancelled.** Arm B in Phase 13 was *cancelled* because
its mechanism would have changed the question and was designed but never built.
This is the opposite case: the instrument exists, `session.py` arms all five
points from the cell through the resolvers, and the binding is proven in both
directions (`prove_crash_point_binding.py`). Cancelling would discard working,
proven capability for a reason that is only cost.

### What it would add, and what it would not

**It would broaden, not strengthen.** §VIII's paragraph rests on the primary
cell alone and says so in its own text — *"at the one crash point both the
engine and our model can be cut at."* No claim in the manuscript depends on the
other four points:

* **H3** is argued structurally — the fact required is not in the engine's
  history and cannot be put there — and the empirical support the paper cites is
  the 118 non-void runs already collected. Four more points would add
  opportunities to falsify it, which is worth something, but the claim does not
  rest on breadth.
* **The corner assignment** is currently observed at one point. Broadening it
  would license a stronger statement than the paper makes.
* **The frozen comparators exist** at all four points, so the sweep is testable —
  this is a choice not to collect, not an inability.

**The one thing it would genuinely settle**, and this is the honest argument
*for* collecting it: a single crash point cannot distinguish *"the model's rates
are systematically higher than the product's"* from *"the model and the product
diverge at this particular point."* Four more points would. **The paper claims
neither**, so nothing currently written is weaker for the gap — but a reader may
reasonably want to know, which is why this is deferred rather than closed.

### Cost, and what must be settled first

≈240 runs at the 55–60 s/run observed in attempt 3, so **roughly four hours**
plus analysis. Three things would have to be handled before collecting, none of
which is a blocker and none of which has been done:

1. **`before_intent_write` has never attributed at 10 executions.** The
   crash-point binding proof saw `VOID_ATTRIBUTION_UNAVAILABLE` there under a
   2-execution configuration. That was probably an artefact of the proof's
   configuration — `after_barrier_before_dispatch` attributed cleanly at 10 in
   both attempts — but it is untested at collection width.
2. **`mid_dispatch` uses deferred delivery** (`DURING_PROVIDER_CALL`, armed by a
   watchdog thread) and has never been exercised in a collection, only in the
   binding proof.
3. **`VOID_WORKER_NEVER_READY` is an open question** (handoff §7), at 2 in 120
   in each of the last two sessions.

### The trigger

Collect the secondary sweep if **any** of these occurs:

* **A reviewer asks** whether the primary result holds at other crash points.
* **The manuscript comes to claim anything about B5 beyond the primary cell** —
  §VIII's paragraph being broadened, a B5 row added to a table, or the corner
  assignment stated generally rather than at one point.
* **H3 is challenged on breadth** — that one crash point is too narrow a basis
  for the non-escalation claim.

If triggered, it needs its **own re-registration** before any run: fixed n 240,
the stopping rule restated, and the three items above settled. **The attempt
budget does not transfer.** §7's three attempts belong to the primary corrected
cell, of which one was used; the secondary sweep would declare its own.

## 8. What this does not claim

The `DISAGREES` reading at `3e633d7` **stands as a description of what was
collected** and **does not support a claim about B4**. This pre-registration
does not withdraw it, does not predict that a corrected collection will reverse
it, and does not predict that it will confirm it. The prediction is the one in
§1, unchanged, and it was made before any B5 data existed.
