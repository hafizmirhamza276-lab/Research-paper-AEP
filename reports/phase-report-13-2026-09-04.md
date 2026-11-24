# Phase 13 — the controlled fault, and what it cost the model

**Closing report. 2026-09-04.** Covers Arm A (the controlled crash fault), Step 4
(the in-flight variant), the landing-latency model's failure, and the decision
**not** to run Arm B.

Workstream WS-3 of `docs/26-journal-readiness-direction.md`: *"Replace 'one draw
from a docker-kill latency distribution' with a controlled fault."* That goal is
met in the weakened form `docs/30-controlled-fault-mechanism.md` §4 established
in advance was the only achievable one — the race is narrowed and its boundary
measured, not removed.

---

## 1. What the phase produced

| | result | where |
|---|---|---|
| **Arm A**, controlled crash fault, 3 sessions × 180 runs | AEP-full **0.0112** (3/269) against B3 **0.9778** (264/270); between-session spread **0–1** count per class against a baseline of 8 | `reports/raw/phase13-armA-s{1,2,3}-results.txt` |
| **Step 4**, in-flight kill, 2 sessions × 120 runs | **TIE** in all four class-sessions, ≤1 count apart, both arms at ceiling | `reports/raw/phase13-inflight-verdict.md` |
| **The model gap** | the pre-registered bound was wrong, on two independent premises | `reports/raw/phase13-model-gap.json` |
| **Arm B** | **cancelled**, §4 below | this report |
| §VI-C2 | rewritten to lead with the controlled result | commit `c25dfd0` |
| §VIII | limitation restated as bounded and measured; Arm B scope recorded | commits `624f3bb`, this one |

**780 runs collected across five sessions**, no voids beyond one harness-refused
run, zero E5 clock drops.

---

## 2. Arm A: the spread collapsed, and the prediction did not survive

Pre-registered in `reports/phase-report-13-prediction-armA-2026-09-03.md`,
pushed before any data existed.

**The criterion was met.** Between-session spread in AEP-full's unwanted-applied
count, per capability class: **0, 1, 1** against a pre-registered *"CONTROL
SUCCEEDED"* threshold of ≤3 and an uncontrolled baseline of 8. B3 held at
ceiling in all nine class-sessions (29/29/29, 30/30/30, 29/29/29), so the
primary mechanism-failure signature — two arms equally disabled by the injector
— did not fire. All four pre-registered mechanism checks were clean.

**The prediction was not met, and that is the phase's most important result.**
The registered point prediction was 0.058, bounded [0.045, 0.081]. Observed:
**0.0112, below the bound.** §4 of the pre-registration fixed in advance what
that would mean — *the protocol behaving unexpectedly*, not the mechanism
succeeding — and this report honours that rather than presenting a
lower-than-predicted number as a better outcome.

**One run was refused by the harness** (`aep_full-none-notifications-…-r25`,
session 3): its own guard detected that the kill had not landed and aborted
rather than scoring a trial with no fault in it. Session 3's first attempt was
also killed at 152/180 by the environment and **voided rather than resumed** —
resuming would have made it structurally different from sessions 1 and 2 in
exactly the quantity being measured. No outcome was inspected before that
decision.

---

## 3. The model gap: not calibration, and the calibration was never a calibration

Full analysis in `reports/raw/phase13-model-gap.md`, regenerable via
`scripts/analyse_model_gap.py`.

The bound came from one model: AEP-full dispatches iff `WAITAOF` returns before
the fault lands, and under `appendfsync everysec` that wait is `U(0, 1000)` ms,
so the probability is the landing latency over 1000. **Both premises are false,
and they fail in opposite directions**, which is why a single corrected constant
cannot fix it.

* **The window is not the bench landing.** 106 of 240 uncontrolled runs received
  a genuine `WAITAOF` acknowledgement *after* the bench landing had supposedly
  passed — and an ack requires a live server. The same injector call timed
  in situ is **1038.5 ms against the bench's 368.3**, ranges disjoint. This
  premise *holds* for `docker pause` (36.0 in situ against 37.9 bench), which is
  why the error vanishes in Arm A and leaves the second one exposed.
* **The wait is not uniform.** Measured over 143 acks it is unimodal around
  300–500 ms with almost no left tail: **F(58 ms) = 0.0042 against uniform's
  0.058**, 13.9× too generous, and worse the narrower the window.

**The calibration that licensed the bound compared the wrong quantities.** The
model predicts *dispatch*; the estimand is an *applied effect*. On the same runs
dispatch is 0.596 and applied is 0.546. Against the quantity it actually
predicts, the model was already wrong by 1.6× on its own calibration data — and
the evidence was in hand before Arm A ran.

**The model is not adjusted.** No floor is fitted, no window re-estimated. Doing
so against the data that refuted it would produce exactly the post-hoc fit the
pre-registration existed to prevent. A replacement needs its own pre-registration
and its own data.

---

## 4. Arm B: cancelled

**Arm B is cancelled. It is not deferred, and this section exists so the absence
is a recorded decision rather than a gap a reader has to notice.**

### What it would have tested

`docs/30-controlled-fault-mechanism.md` §4 established that no crash-class fault
can separate the arms deterministically. The asymmetry being measured *is* a
timing difference: AEP-full has one extra Redis-dependent step, and any fault
that guarantees `WAITAOF` cannot return also blocks the `authorize_dispatch` and
`preflight` calls B3 makes after the same checkpoint. Both arms would stop
dispatching, and the contrast would vanish because the injector disabled them.

One mechanism escapes that. **Disabling the fsync rather than the server** —
`CONFIG SET appendfsync no` at the checkpoint — makes `WAITAOF` unsatisfiable
while every other Redis call keeps working. B3 is untouched; AEP-full times out
deterministically. It separates the arms *by construction* rather than by a
latency comparison, and it is the only candidate that does.

That was Arm B: **durability made unavailable, rather than raced for and lost.**

### Why it is cancelled

1. **It would add a failure class the paper's model does not contain.** It is not
   a crash and arguably not a fault — it is a configuration change that makes a
   guarantee unattainable. `docs/30` §4 already recorded that it *"could not be
   described as a Redis-kill result"* and that the comparison to the frozen cell
   would be to a different experiment. Introducing a new class in the last phase
   means every claim scoped to F3 needs re-scoping, and §III's failure model
   needs a member it was not designed around.

2. **The gain is marginal, because Arm A already did the work.** Arm B's
   argument in the Arm A pre-registration was explicitly conditional: *"the
   residual is irreducible under this fault class, and Arm B exists because of
   it."* That was written when the expected outcome was a residual near the
   registered 0.058 with a spread that might not collapse. What actually
   happened is a spread of **0–1 count per class against a baseline of 8**, and
   a rate of 0.0112. §VI-C2 now rests on measured, bounded evidence. Arm B would
   move a residual that is already small and already characterised, and would
   buy a cleaner *number* rather than a better-supported *claim*.

3. **It answers a different question.** `docs/30` §4 warned that adopting it
   silently *"would answer a different question from the one §VI-C2 asks."*
   §VI-C2 asks what the barrier does when durability is contended and lost. Arm B
   asks what it does when durability is unavailable. Both are legitimate; only
   the first is the paper's.

**The decision is a judgement, not a measurement**, and it is reversible: the
mechanism is designed and documented, and a future phase that wants the second
question can run it under its own pre-registration.

### What the paper therefore does not claim

Recorded in §VIII as a scoped limitation, and repeated here so the two cannot
drift apart:

> The barrier's prevention guarantee is evaluated where durability is **raced
> for and lost to a crash**. It is **not** evaluated where durability is simply
> **unavailable** — a degraded or misconfigured store that answers every other
> call while never acknowledging an fsync. The paper makes no claim about that
> regime, and the residual reported in §VI-C2 is a property of the crash class
> rather than a bound that carries over to it.

**The Arm A pre-registration's forward references to Arm B stand as written and
are not edited.** It was pushed before the data existed and its value is that it
has not been touched since; this report is where the decision it anticipated is
recorded.

---

## 5. Step 4: the in-flight tie, and what its determinism shows

Pre-registered in `reports/phase-report-13-prediction-inflight-2026-09-04.md`,
committed as `77afd9a` before any data. Closes **M9**.

**TIE in all four class-sessions**, every difference 1 against a pre-registered
band of ≤2, both arms at ceiling, zero lost effects and zero undetected
duplicates. No mechanism-failure signature fired across 240 runs.

Two qualifications that belong with the number, both in
`reports/raw/phase13-inflight-verdict.md`:

* **Session 2 is a deterministic replay, not an independent replication.** All
  120 seeds are shared and all 120 per-run outcome tuples identical, so the
  effective run count is **120, not 240**. The k=2 justification in that
  pre-registration **does not hold as written**: it assumed a second session is
  a second draw, and under this harness it is not unless something in the run is
  non-deterministic.
* **The absence of variation is itself evidence.** Arm A ran the same
  shared-seed design — 180 seeds shared across three sessions — and varied
  anyway (1/0/1 and 0/0/1). What moved it is the race. The in-flight cell has no
  race and did not move at all, which is a stronger form of the structural
  prediction than the tie counts.

**B3's floor is 27/30 in both sessions — exactly the pre-registered threshold,
one run from tripping the primary mechanism-failure signature. It is the
boundary, not headroom.**

---

## 6. What is unexplained, and stays that way

* **The controlled arm's four acks are faster than anything seen uncontrolled** —
  3.6, 4.5, 7.5 and 102.7 ms, three of them below the 29.3 ms minimum of all 143
  uncontrolled acks. Whether the mechanisms differ in wait distribution or four
  observations are too few is not decidable from this data.
* **2–3 runs per NO_READBACK cell did not apply an effect in the in-flight
  cell, in both arms.** Not a difference between the arms, so it does not touch
  the tie, but why is unexamined.
* **One host.** Every collection is from one machine. The effect size's
  dependence on host timing is now measured *on* that host, not established
  *across* hosts.
* **`issue_to_return_ns` times the call, not the death**, so the in-situ
  landing figure is an upper bound rather than a measurement. Only the
  106-runs-alive-past-368 ms bound is model-free.

---

## 7. Artifacts

| | |
|---|---|
| pre-registrations (before data) | `phase-report-13-prediction-armA-2026-09-03.md`, `phase-report-13-prediction-inflight-2026-09-04.md` (`77afd9a`) |
| session diagnostics | `reports/raw/phase13-{armA-s1,armA-s2,armA-s3,inflight-s1,inflight-s2}-results.txt` |
| analyses | `scripts/analyse_controlled_prevention.py`, `analyse_model_gap.py`, `analyse_inflight_tie.py`, `render_session_results.py`, `distil_session_fixture.py` |
| their tests | `tests/test_session_results_rendering.py`, `test_model_gap_analysis.py`, `test_inflight_tie_analysis.py` |
| tracked results | `experiments/results/phase13-*/analysis/` |
| known text defects | `reports/raw/phase13-armA-known-text-defects.md` |

Every number in §VI-C2 and §VIII is a generated macro; `paper/generated/**` is
never hand-edited. `scripts/check_paper_numbers.py`: **19 passed, 0 failed.**

**Phase 13 is closed.**
