# Phase 13 Arm A — why the landing-latency model missed, in both directions

**2026-09-04. Written after all three Arm A sessions landed and before §VI-C2 is
drafted, so that the section is written from this rather than around it.**

The pre-registration
(`reports/phase-report-13-prediction-armA-2026-09-03.md`) predicted AEP-full's
unwanted-applied rate at **0.058**, bounded **[0.045, 0.081]**. Arm A observed
**0.0112** (3 applied effects in 269 AEP-full executions), below the bound in all
three capability classes. The same model applied to the uncontrolled mechanism
predicted **0.368** against an observed **0.417**.

> **Scope of the uncontrolled figure, stated where it is first used.** The
> **0.417** is *transcribed* from the pre-registration §1, as the median of
> **six** ext4 sessions spanning **10–18 of 30** — itself transcribed from
> `reports/phase-report-12-filesystem-hypothesis-2026-09-03.md` §4. It is not
> regenerated here and no test guards it. The measurements in this note cover
> **four** of those six sessions — the `b2-paired-v2` collections, the ones
> carrying both the `durability_ack_observed` events and the
> `redis_kill_latency_ms` column — over which AEP-full's NO_READBACK applied
> rate is **0.483** (58 of 120). Quote 0.417 as the pre-registered six-session
> median and 0.483 as this note's four-session measurement; they are different
> denominators and must not be swapped for each other.

Wrong low on one mechanism and wrong high on the other. A single mis-set constant
cannot do that, so this is not calibration and must not be fixed by moving one.

**Nothing here adjusts the model.** No floor is fitted, no window is re-estimated,
no replacement is proposed. This note establishes what is wrong with the model's
two premises and what the collected data cannot settle. The pre-registration is
not amended: its value is that it has not been touched since before the data
existed.

---

## 1. The finding

The model is one assumed window multiplied by one assumed distribution:

> AEP-full dispatches **iff** `WAITAOF` returns before the fault lands. Under
> `appendfsync everysec` a `WAITAOF` issued at a uniformly random phase returns
> in **U(0, 1000) ms**, so the probability it beats the fault is the landing
> latency as a fraction of 1000 ms.

Two premises, both testable, **both false, and false in opposite directions**:

| | premise | verdict |
|---|---|---|
| **(a)** | the exposure window equals the fault's landing latency | **false for `docker kill`** (window far wider than the bench landing); **true for `docker pause`** |
| **(b)** | the `WAITAOF` wait is uniform on U(0, 1000) | **false for both** — the wait is unimodal around 300–500 ms with almost no left tail |

Premise (b) makes the model over-predict everywhere. Premise (a) makes it
under-predict on the uncontrolled mechanism only. Which error dominates depends
on **where the window falls in the wait distribution**, and that is the whole
explanation for the sign flip.

---

## 2. Premise (b): the wait is not uniform

The uncontrolled sessions ack in ~60% of runs, so the wait distribution is only
lightly censored there and can be read off rather than inferred. Measured as
`redis_kill_armed` → `durability_ack_observed`, both from the worker's own
monotonic clock, over the four `b2-paired-v2` ext4 sessions (240 AEP-full runs,
143 acks):

```
  0-  99 ms  #                               (1)      min      29.3 ms
100- 199 ms  ###                             (3)      p25     362.4 ms
200- 299 ms  ###############                (15)      median  483.6 ms
300- 399 ms  #############################  (29)      p75     622.8 ms
400- 499 ms  ###########################    (27)      max    1111.8 ms
500- 599 ms  #########################      (25)
600- 699 ms  #################              (17)      B3, same checkpoint,
700- 799 ms  ##############                 (14)      no barrier (n=240):
800- 899 ms  ###                             (3)      median 4.6 ms,
900- 999 ms  #####                           (5)      max   16.4 ms
1000-1099 ms ###                             (3)
1100-1199 ms #                               (1)
```

A uniform wait would put equal mass in every bin. This one is unimodal with its
mass between 300 and 700 ms and **essentially nothing below 200 ms**. The B3
column is the same checkpoint reached without a barrier, which fixes the
non-barrier cost at ~5 ms and confirms the shape above is the barrier and not
harness overhead.

Against uniform, over the whole denominator of 240 runs (uncensored below
492.8 ms, the earliest abort):

| x | empirical F(x) | uniform x/1000 | uniform overstates by |
|---|---|---|---|
| 25 ms | 0.0000 | 0.025 | — (no observations at all) |
| 29 ms | 0.0000 | 0.029 | — |
| **58 ms** | **0.0042** | **0.058** | **13.9×** |
| 100 ms | 0.0042 | 0.100 | 24× |
| 200 ms | 0.0167 | 0.200 | 12× |
| 368 ms | 0.1542 | 0.368 | 2.4× |

**The error grows as the window narrows.** At the uncontrolled mechanism's scale
uniform is 2.4× too generous; at the controlled mechanism's scale it is 13.9× too
generous. Arm A narrowed the window by 6.3× and therefore walked directly into
the region where this premise is worst.

This is the single most consequential number in the phase: **the data needed to
refute the uniformity premise was already in hand before Arm A was collected.**
It is in the same four sessions the model was calibrated against. Reading the ack
timestamps rather than only the applied counts would have shown it.

---

## 3. Premise (a): the window is not the bench landing

### It fails for `docker kill`

The model-free form of the evidence, which depends on no interpretation of any
timing field: **106 of 240 uncontrolled AEP-full runs received a genuine
`WAITAOF` acknowledgement more than 368.4 ms after arming.** A `WAITAOF` ack
requires a live server, so each of those runs proves Redis was still answering
past the bench's landing estimate. Consistent across all four sessions:

| session | acked | acks after 368.4 ms | longest observed wait |
|---|---|---|---|
| `b2-paired-v2-s1` | 40/60 (0.667) | 24 (0.400 of runs) | 1111.8 ms |
| `b2-paired-v2-s2` | 36/60 (0.600) | 30 (0.500 of runs) | 1086.6 ms |
| `b2-paired-v2-s3` | 29/60 (0.483) | 23 (0.383 of runs) | 969.8 ms |
| `b2-paired-v2-s4` | 38/60 (0.633) | 29 (0.483 of runs) | 726.7 ms |

The in-situ timing agrees. `redis_kill_latency_ms` (`experiments/analyze.py:563`,
derived from `issue_to_return_ns`) is the same quantity the bench reported as
`command_ms`, measured during the collections themselves:

| | median | min | max |
|---|---|---|---|
| bench, `docker kill` (n=100) | 368.3 ms | 294.1 | 428.6 |
| **in situ, same call (n=480)** | **1038.5 ms** | **731.7** | 8229.4 |

**The ranges do not overlap**: the bench maximum (428.6 ms) is below the in-situ
minimum (731.7 ms). The bench measured the mechanism in isolation; a collection
runs it against a contended Docker daemon. The measurement did not transport, and
nothing in the bench protocol would have revealed that.

### It holds for `docker pause`

The controlled mechanism's bench number transports almost exactly, which is why
error (a) disappears in Arm A and leaves error (b) exposed:

| | bench | in situ (Arm A, n=539) |
|---|---|---|
| `docker pause` command | 37.9 ms median | **36.0 ms median** (min 21, max 242) |
| landing / observed abort | 58.3 ms | **58.2 ms median** abort (min 42.7, max 201.6) |

The bench landing of 58.3 ms is approximately its 37.9 ms command plus the
declared 20.0 ms `landing_measurement_floor_ms` — approximately, not exactly:
the bench's own landing-minus-command is **20.4 ms**, so the floor accounts for
the gap without closing it. Nothing here rests on the 0.4 ms. AEP-full's non-acking runs abort at a median of
58.2 ms. The window the pre-registration assumed for the controlled arm is, as
far as this data can show, the right one.

---

## 4. Why the sign flips

Everything above composes into one statement:

* **Uncontrolled.** Error (a) is large — the true window is at least ~2.8× the
  assumed 368 ms — and pushes the prediction *up*. Error (b) pushes it *down* by
  2.4× at that scale. They partly cancel, and the residual was then masked
  entirely (§5). The model looked calibrated.
* **Controlled.** Error (a) vanishes: the 58 ms window is real. Error (b) is
  left alone, and at 58 ms it is at its worst. The model over-predicts:
  **0.058 predicted, 0.0149 dispatched, 0.0112 applied** — a factor of 3.9 on
  the quantity the model predicts, 5.2 on the estimand.

  **The two do not reconcile exactly, and the gap is not explained here.** The
  uncontrolled wait distribution puts F(58) at 0.0042, which would predict a
  13.9× over-statement, not 3.9×. Arm A's four acks came in *faster* than that
  distribution allows — three of them under 7.5 ms, against a minimum of 29.3 ms
  across all 143 uncontrolled acks. Either the controlled arm's wait
  distribution genuinely differs, or four observations are too few to say. §6
  records this as unsettled; it is not resolved by assuming either answer.

The cancellation was never a property of the model. It was a coincidence of
where the uncontrolled window happened to sit, and narrowing the window by 6.3×
destroyed it. **A model validated at exactly one operating point, by a check that
two opposed errors could satisfy, carries no warrant for extrapolation to a
different one** — which is precisely what the bound `[0.045, 0.081]` was.

---

## 5. The calibration agreed for the wrong reason

This is the part §VI-C2 must state plainly, because it is a defect in the
pre-registration's reasoning and not only in its arithmetic.

The pre-registration §1 wrote that the model *"predicts AEP-full's
unwanted-applied rate at 0.368"* and checked it against an observed 0.417 — the
six-session median transcribed from phase-12, not a figure regenerated here; the
four sessions measured below give a NO_READBACK applied rate of **0.483**. But
the model's derivation is about whether `WAITAOF` returns before the fault —
that is **dispatch**, not **applied**. Dispatch is necessary for an applied
effect and not sufficient: the fault can land after the acknowledgement and
before transmission, which is the window `after_barrier_before_dispatch` names.

Both quantities are measurable on the same runs:

| | uncontrolled (n=240) | controlled (n=269) |
|---|---|---|
| **dispatch** (`durability_ack_observed`) | 143 = **0.596** | 4 = 0.0149 |
| transmitted (`provider_request_transmitted`) | *event did not exist yet* | 4 |
| **applied** (the estimand) | 131 = 0.546 | 3 = 0.0112 |
| NO_READBACK dispatch / applied | 0.575 / 0.483 | — |

Against the quantity it actually predicts, the model read **0.368 against 0.575**
— already wrong by 1.6× on its own calibration data. The apparent agreement came
from comparing a dispatch model to an applied rate, with the dispatch→applied
step (~16% of dispatches never become effects in NO_READBACK) absorbing most of
the discrepancy.

The pre-registration's stated reason for trusting the bound was that stating it
in advance meant *"its agreement cannot be claimed afterwards as a post-hoc
fit."* That protected against fitting after the fact. It did not protect against
the model agreeing for the wrong reason, and no amount of pre-registration
would have. The check that was missing is the one this note performs: compare the
model to the quantity it predicts, on data that already existed.

Ack rate is flat across capability classes — 0.575 `ledger_postings`, 0.617
`payments` — which is consistent with the pre-registration's claim that the
barrier's behaviour does not depend on read-back.

---

## 6. What the data cannot settle

Recorded in full, because each of these is a place where a confident sentence in
§VI-C2 would outrun the evidence.

* **When Redis actually died, in situ.** `issue_to_return_ns` times the *call*,
  not the death. In Arm A that same field demonstrably spans pause + kill +
  restart (385 ms median against a 36 ms pause), so **1038.5 ms is an upper
  bound on the uncontrolled landing, not a measurement of it**. The 2026-08-28
  sessions carry no `pause_ms` / `command_ms` to decompose it. Only the
  model-free bound is solid: ≥106 runs had Redis alive past 368.4 ms.
* **What closes the window for non-acking uncontrolled runs.** They abort at a
  median of 668.1 ms (min 492.8, max 963.7) — *before* the kill call returns —
  and **every** run in both arms fails with `LockAcquisitionError`, so the
  failure class carries no discriminating signal. Lock lease expiry, a barrier
  timeout, and the fault landing cannot be separated from the recorded events.
* **The controlled arm's own wait distribution.** n = 4 acks, at 3.6, ~4.5, ~7.5
  and 102.7 ms. Three of them sit below the 29.3 ms minimum of all 143
  uncontrolled acks. Whether the two mechanisms genuinely differ in wait
  distribution, or this is chance at n = 4, is not decidable from this data.
* **Cross-epoch comparability.** The two groups are six days and at least one
  code change apart — `provider_request_transmitted` landed between them
  (`docs/31-transmission-event.md`). The wait distribution may have moved for
  reasons unrelated to the mechanism, and nothing collected isolates that.
* **Scope.** The four `b2-paired-v2` sessions were used because they carry both
  the ack events and the kill-latency column. The other two ext4 sessions
  (`matrix`, `b2-paired-s1-2026-08-28`) are **not** in any figure here, so these
  are four of the six sessions the pre-registration's 0.417 median came from.
* **The uncontrolled target was never a point.** Six ext4 sessions span 10–18 of
  30 (0.333–0.60), and the model's 0.368 sits inside that range. "The model
  under-predicted 0.417" was always a weak claim about an unstable point
  estimate. The firm claim is the dispatch-level one: **0.368 against 0.575.**

---

## 7. Provenance

Every number above is derived from runs already collected; nothing was
re-collected and no run was re-analysed by a modified analyzer.

| number | source |
|---|---|
| wait distribution, ack rates, abort times | `events-worker-*.jsonl`, `redis_kill_armed` → `durability_ack_observed` / `execution_failed`, one process clock |
| in-situ `docker kill` latency | `redis_kill_latency_ms` in each session's `analysis/per-execution.csv` |
| in-situ `docker pause` latency | `redis_kill_issued.pause_ms`, Arm A only |
| bench landing | `reports/raw/phase13-fault-landing.json` |
| applied counts | `analysis/redis-kill-ablation.csv`, `executions_with_an_applied_effect`, read as `\UnwantedPrevented` reads it |

**Every number above is regenerable by a committed script.** The probes that
first computed them were promoted to `scripts/analyse_model_gap.py`, and
`tests/test_model_gap_analysis.py` pins the results as literals transcribed from
*this note* rather than as a snapshot of the script's own output — a snapshot
would pass if the analysis and the snapshot drifted together. The analysis run
from the session roots and from the committed fixture produce byte-identical
output, so `tests/fixtures/model-gap/runs.json` is a faithful stand-in for roots
CI cannot reach.

### Known limitation: the prose is not machine-checked

The test pins what the *script computes*. Nothing checks that what this
*document says* still matches it — the figures were transcribed here by hand,
and an earlier revision carried `14×` in three places where the computed value
is `13.9×` while every test passed.

**This is accepted, not overlooked.** The note is an intermediate document. The
gate that matters is `scripts/check_paper_numbers.py`, which checks the
manuscript's numbers against the real analysis products and runs in CI, and
§VI-C2 will be covered by it. Adding a second, weaker gate here would duplicate
that one and imply this document carries an authority it does not have.

**The consequence to carry forward:** a figure quoted from this note into §VI-C2
is quoted from prose, not from a checked artifact. Re-derive it from
`scripts/analyse_model_gap.py` at the point it enters the manuscript, so that
`check_paper_numbers.py` is checking the analysis rather than this
transcription.

---

## 8. What this note does not do

* **It does not adjust the model.** No floor is fitted to the left tail, no
  window is re-estimated, no corrected predictor is offered. Doing so against the
  same data that refuted it would produce exactly the post-hoc fit the
  pre-registration was designed to prevent. A replacement model needs its own
  pre-registration and its own data.
* **It does not write §VI-C2.**
* **It does not amend the pre-registration**, which stands unmodified as the
  record of what was predicted before the data existed. Its bound was wrong; that
  it was stated in advance, and can now be shown wrong against measurements it
  did not anticipate, is the pre-registration working as designed.
