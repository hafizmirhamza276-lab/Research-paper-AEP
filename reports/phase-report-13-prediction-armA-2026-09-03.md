# Pre-registration — Phase 13 Arm A: the controlled crash fault

**Written and pushed before any Arm A data exists.** Rule 5 of
`docs/26-journal-readiness-direction.md` §3.

Arm A is the **crash-class** replication: the same failure class F3 and the same
instruction boundary as the frozen `redis-kill-preack` cell, with the injector's
own contribution to the race narrowed by measurement. It is comparable to the
frozen cell. Arm B, a separate regime and a separate pre-registration, is not,
and no sentence may blend them.

---

## 1. What changed, and the one number the whole prediction turns on

`scripts/measure_fault_landing.py`, 100 trials per mechanism on the native
runtime (`docs/30-controlled-fault-mechanism.md`):

| mechanism | landing median | landing spread | landing / WAITAOF window |
|---|---|---|---|
| `docker kill` — the frozen cells' mechanism | 368.4 ms | 134.6 ms | **0.368** |
| **`docker pause` → `docker kill` — Arm A** | **58.3 ms** | **36.0 ms** | **0.058** |

AEP-full dispatches **iff** `WAITAOF` returns before the fault lands. Under
`appendfsync everysec` Redis fsyncs once a second, so a `WAITAOF` issued at a
uniformly random phase of that cycle returns in **U(0, 1000) ms**. The
probability that it beats the fault is therefore the landing latency expressed
as a fraction of 1000 ms — the last column.

### The model is calibrated against data that already exists

The same model applied to the **uncontrolled** mechanism predicts AEP-full's
unwanted-applied rate at **0.368**, i.e. ~11/30. The six ext4 sessions
(`reports/phase-report-12-filesystem-hypothesis-2026-09-03.md`) observed
**10, 10, 12, 13, 18, 18 out of 30** — median 12.5/30 = **0.417**. The model
predicts 0.368 and the realised median is 0.417.

**This is stated before Arm A is collected so that its agreement cannot be
claimed afterwards as a post-hoc fit.** It is what licenses using the same model
to state Arm A's bound rather than guessing one.

---

## 2. The prediction — a bound, not zero

> **AEP-full's unwanted-applied rate under Arm A will approach 0.058, the bound
> the narrowed window permits. It will NOT reach 0/30, and this pre-registration
> does not predict that it will.**

| quantity | pre-registered value |
|---|---|
| **point prediction**, AEP-full | **0.058** (≈ **1.7 of 30** runs per cell) |
| **bound from the landing distribution** | **[0.045, 0.081]** — from the measured landing min 45.2 ms and max 81.2 ms |
| **B3** | at ceiling, **≥ 27/30 (0.90)**, unchanged from the frozen cell's 28/30 |
| **capability classes** | the same in all three; the barrier's behaviour does not depend on read-back |

**Why not zero.** No crash-class fault can drive it to zero. Freezing Redis
*synchronously at the checkpoint* would make `WAITAOF` unanswerable, but B3
reaches the same checkpoint and still needs `authorize_dispatch` and `preflight`
— both Redis calls — so the freeze would stop B3 dispatching too and the
contrast would vanish because the injector disabled both arms.
`docs/30-controlled-fault-mechanism.md` §4 establishes this. **The residual is
irreducible under this fault class**, and Arm B exists because of it.

**How the residual will be reported.** As a bound with its mechanism, in these
terms: *the injector's landing latency is 58.3 ms against a 1000 ms barrier
window, so at most ~5.8% of runs can dispatch, and the observed rate is X.* Not
as "AEP-full prevents the effect", which would overstate it.

---

## 3. Did the spread collapse — the criterion, stated in advance

This is the criterion Phase 9C lacked. The comparison is the **between-session
spread** in AEP-full's unwanted-applied count, per capability class, across the
3 sessions.

**Baseline to beat:** the six ext4 sessions under the uncontrolled fault spanned
**10–18/30 — a spread of 8 counts (26.7 pp)**.

| observed spread across the 3 sessions (max − min, counts out of 30) | verdict |
|---|---|
| **≤ 3** (≤ 10 pp) | **CONTROL SUCCEEDED.** Consistent with binomial noise alone: at p = 0.058, n = 30, sd = 1.28 counts, so a 3-count range across three sessions is ~2.3 sd. |
| **4–5** | **INCONCLUSIVE.** Reported in those words, not as success. |
| **≥ 6** (≥ 20 pp) | **CONTROL FAILED.** The injector is still dominating the outcome and the narrowed window did not remove it. |

Applied per capability class, and reported per class. A collapse in two classes
and not the third is reported as exactly that.

**If the half-width of the session-clustered interval on the rate exceeds
10 pp**, the comparison is reported as **INCONCLUSIVE — UNDERPOWERED**, in those
words, regardless of the point estimates. Phase 9C's failure was this shape and
Phase 10's was avoided by declaring the rule first.

---

## 4. What would mean the *mechanism* failed, as distinct from the protocol

Declared in advance so the two cannot be confused afterwards.

**The control mechanism failed if any of these hold:**

| signature | what it means |
|---|---|
| **B3 below ceiling (< 27/30)** in any class | the freeze is blocking B3's post-checkpoint `authorize_dispatch`/`preflight`. The injector disabled both arms; the contrast is an artifact. **This is the primary failure signature.** |
| `paused: false` in > 5% of runs | `docker pause` did not fire; those runs carry the uncontrolled fault and the root is mixed. |
| AEP-full ≈ 0.37 **and** spread ≥ 6 | the pause is not landing before the barrier at all; the run is an expensive replication of the uncontrolled cell. |
| `redis_fault_mechanism` ≠ `pause-then-kill` in any run's environment block | the regime did not select its own mechanism. |

**The protocol behaved unexpectedly — a different and more interesting finding —
if the mechanism checks all pass and:** AEP-full's rate is materially **above**
0.081 (the landing-distribution bound) or materially **below** 0.045, or B3 is at
ceiling while AEP-full's *spread* is large despite a tight landing distribution.

---

## 5. Design

* **Regime:** `redis-pause-kill-preack` (`experiments/run_matrix.py`), fault at
  `after_intent_before_barrier`, `redis_kill_delay_ms=0`, one execution per run,
  one worker.
* **Systems:** `AEP_FULL` and `B3_INTENT_NO_BARRIER`, the ablation pair.
* **Capability classes:** all three — `payments` (AUTHORITATIVE_READBACK),
  `notifications` (POSITIVE_ONLY_READBACK), `ledger_postings` (NO_READBACK).
* **Shape:** 30 runs per arm per class per session × 2 arms × 3 classes = **180
  runs per session**; **3 sessions** = **540 runs**. Fitted estimate 1.79 h per
  session.
* **Sessions are separate collections in separate dated roots**, not one long
  run, so between-session variance is measurable — which is the estimand.
* **Interleaving:** run-level, between AEP-full and B3, by the matrix's own sort
  key. Phase 8.5 amendment 1 established that this makes arm orthogonal to
  within-session position by construction. **The realised ordering will be
  reported from the collected runs rather than assumed**, since Phase 8.4's
  `b2-paired-s1` was cell-major and B9 exists because of it.
* **Host:** ext4 (`/root/aep-phase13/...`), native Docker runtime, the pinned
  Redis digest.
* **Unit of analysis: the run.** Session-clustered intervals, cluster bootstrap
  over sessions, 10 000 resamples, seed 20260806 — the project's parameters.
* **Stopping rule:** fixed at 3 sessions × 180 runs. No interim look. No run
  dropped except by the harness's existing void criteria, which are reported as
  counts.

### Preconditions, checked not assumed

Before the first run: `scripts/verify_measurement_host.py` exits 0;
`AEP_HARNESS_SUSPEND_DISABLED` declared; the E5 clock check within tolerance.
Phase 11 established the clock divergence is **episodic, not a state** — one
2.5-hour window on 2026-09-02 in 1 458 runs — so it is measured per session and
the E5 drop rate is reported as a first-class number.

### Exact analysis command

```sh
uv run --frozen --extra experiments --extra analysis python -m experiments.analyze \
  --results-root /root/aep-phase13/armA-s<N>-2026-09-03 \
  --bootstrap-seed 20260806 --resamples 10000

uv run --frozen --extra experiments --extra analysis python \
  scripts/prevention_session_crosstab.py \
  --json reports/raw/phase13-armA-crosstab.json
```

`redis-kill-ablation.csv`'s `executions_with_an_applied_effect` is the estimand,
read exactly as `\UnwantedPrevented` reads it.

**Analysis filters by results root, not by regime label.** Arm A and the frozen
cell derive the same `regime_label` from their configs, because the mechanism is
recorded in the environment block rather than in the digested body. Pooling them
would be the error this note exists to prevent.

---

## 6. Both outcomes are acceptable

If the spread collapses, §VI-C2 leads with a bounded controlled result and the
frozen cell becomes the uncontrolled replication that agrees in direction. If it
does not, the concession in §VIII-A(e) stays, and the phase reports that the
narrowed window was not enough — **which is itself the finding that the residual
is irreducible under crash faults, and is the argument for Arm B.**

Nothing will be tuned to make an arm agree.
