# Pre-registration — Phase 13 Step 4: the in-flight Redis kill

**Written and committed before any `redis-kill-inflight` data exists.** Rule 5 of
`docs/26-journal-readiness-direction.md` §3. This closes **M9** — the
uncollected-but-implemented cells named in §VIII-C(f) — per task 3.4: *"Also
collect the in-flight Redis-kill variant (predicted tie)."*

The regime has been fully defined since Phase 2b (`experiments/run_matrix.py:259`)
and has **zero runs**. Nothing about it is being changed to collect it.

---

## 1. What the variant is, and why a tie is predicted

`redis-kill-inflight` arms the hard Redis kill at the last instruction before
transmission (`mid_dispatch` → `AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION`) and
delivers it **200 ms later**, so the kill lands while the provider request is in
flight — *after* both arms have already dispatched.

The prediction is a **tie**, and it rests on two things that are already
established rather than on any model:

**(i) Both arms have dispatched before the fault arrives.** The kill point is
after preflight, and AEP-full's barrier is upstream of it. Whatever `WAITAOF`
did, it has already returned by the time the kill is armed. The fault cannot
reach the decision the two arms make differently.

**(ii) A process kill cannot lose the record.**
`reports/phase-report-2b-session3b-2026-08-07.md` §C.2 tested exactly this
before six hours were spent on it: `appendfsync everysec` defers the `fsync(2)`,
**not** the `write(2)`. Redis writes the AOF buffer to the OS on every event-loop
iteration, and a `SIGKILL` destroys the process while leaving the kernel and its
page cache intact. Ten trials, every kill landing inside the 1 000 ms window
(`write→death` 419–992 ms), and **not one unfsynced write lost**. `WAITAOF`
defends against loss of the *page cache* — host power failure, kernel panic, VM
destruction — which `appendonly yes` does not cover. It does not defend against
process death, which `appendonly yes` already survives.

So no process-level fault delivered *after* dispatch can separate B3 from
AEP-full, and this one is delivered after dispatch by construction.

### This prediction does not use the landing-latency model

**Stated explicitly because that model has just been refuted.**
`reports/raw/phase13-armA-model-gap.md` shows it failed on two independent
premises — the exposure window is not the bench landing latency, and the
`WAITAOF` wait is not uniform on U(0, 1000). Nothing above depends on either.
The prediction here is **structural**: the fault lands after the branch point, so
there is no race to model. Landing latency is irrelevant to this cell for the
same reason, which is also why the mechanism choice below is free.

---

## 2. The prediction

> **AEP-full and B3 will be indistinguishable under the in-flight kill, in both
> capability classes: both at ceiling on applied effects, and no arm showing
> duplicates or lost effects the other does not.**

| quantity | pre-registered value |
|---|---|
| **AEP-full applied** | at ceiling, **≥ 27/30** per class per session |
| **B3 applied** | at ceiling, **≥ 27/30** per class per session |
| **arm difference** | **≈ 0** — the criterion is in §3 |
| `lost_effect_executions` | **0 in both arms** (§C.2: the record survives) |
| `undetected_duplicate_applications` | **0 in both arms** |

**A tie here is not evidence the barrier is useless**, and §VI-C2 must not read
that way. It is evidence that *this fault class, delivered at this point, cannot
separate the arms* — which is precisely why the `redis-kill-preack` variant
exists and why it is the one the prevention result rests on. Recording a
predicted tie as a measurement rather than an inference is the whole value of
this collection (`phase-report-2b-session3b` §H.5: *"a predicted tie that is
collected is evidence; a predicted tie that is inferred is an assumption"*).

---

## 3. The tie criterion, stated in advance

Per **capability class**, per **session**, on
`executions_with_an_applied_effect` from `redis-kill-ablation.csv` — the same
estimand, read the same way, as `\UnwantedPrevented` reads it:

| \|AEP-full − B3\|, counts out of 30 | verdict |
|---|---|
| **≤ 2** | **TIE.** Consistent with binomial noise at ceiling. |
| **3–5** | **INCONCLUSIVE.** Reported in those words, not as a tie. |
| **≥ 6** | **NOT A TIE.** The arms differ under a fault that should not distinguish them. |

Applied per class and reported per class. A tie in one class and not the other
is reported as exactly that.

### The k = 2 interval will be reported as uninformative

Arm A used a session-clustered bootstrap over 3 sessions. **At k = 2 that
interval is not informative and will not be presented as though it were**: a
cluster bootstrap resampling two sessions can only ever draw {s1,s1}, {s1,s2} or
{s2,s2}, so its width is an artifact of having two clusters rather than a
measure of precision. The criterion above is therefore the **per-session count
difference**, not an interval, and any interval reported alongside will carry
that caveat in the same sentence.

This is declared now because Phase 9C's failure was reporting an underpowered
comparison without saying so, and declaring the rule first is what Phase 10 did
instead.

---

## 4. What would mean the *mechanism* failed, as distinct from the protocol

Declared in advance so the two cannot be confused afterwards.

| signature | what it means |
|---|---|
| **either arm below ceiling (< 27/30)** | the kill is landing *before* transmission completes, so the cell is not the in-flight variant it claims to be. **This is the primary failure signature**, and it is the one that would invalidate the tie regardless of how equal the arms look — two arms equally broken by a mis-timed injector is not a tie. |
| `redis_fault_mechanism` ≠ `kill` in any run's environment block | the collection did not use the mechanism this pre-registration fixes. |
| `redis_kill_point` ≠ `mid_dispatch`, or `redis_kill_delay_ms` ≠ 200, in any run | the regime did not deliver its own fault. |
| runs with no kill event in > 5% of runs | the injector did not fire; those runs carry no fault at all. |

**A result that is more interesting than the tie**, and must be reported as its
own finding rather than folded into this one:

* **`lost_effect_executions` > 0 in either arm.** §C.2 establishes that a process
  kill cannot lose the record. A lost effect here would contradict a result the
  paper already rests on, and would be a larger finding than anything this cell
  was collected to show.
* **The arms differ (≥ 6) with both at ceiling.** Both dispatched, so a
  difference could only arise downstream in recovery or read-back — a claim about
  reconciliation, not about the barrier, and it would need its own investigation
  rather than a sentence in §VI-C2.

---

## 5. Design

* **Regime:** `redis-kill-inflight` (`experiments/run_matrix.py:259`), unmodified.
* **Fault:** `mid_dispatch`, `redis_kill_delay_ms=200`, one kill, one execution
  per run, one worker.
* **Systems:** `AEP_FULL` and `B3_INTENT_NO_BARRIER` — the ablation pair.
* **Capability classes: two**, `payments` (AUTHORITATIVE_READBACK) and
  `ledger_postings` (NO_READBACK), because that is what the regime defines.
  Arm A used all three; this cell does not, and **the difference is deliberate**:
  M9 asks for the cell *as implemented*, and widening `endpoints` would modify a
  regime that has been frozen since Phase 2b.
* **Mechanism: `kill`** — the default, `MECHANISM_KILL` in
  `experiments/harness/redis_kill.py`, selected by leaving
  `AEP_HARNESS_REDIS_FAULT_MECHANISM` at its default and recorded in the
  environment block.

  **Why the default and not Arm A's `pause-then-kill`.** This cell exists to
  close M9, and §VIII-C(f) names it as implemented with the default mechanism;
  collecting it under a different mechanism would close a different gap than the
  one the direction asks for. And the choice is free here in a way it was not for
  Arm A: landing latency is irrelevant when the kill lands after both arms have
  dispatched, so the narrower injector buys nothing this cell can use.

* **Shape:** 30 runs per arm per class per session × 2 arms × 2 classes = **120
  runs per session**; **2 sessions** = **240 runs**.
* **Why 2 sessions and not 3.** The estimand here is a *within-session, paired*
  contrast between interleaved arms, not the between-session spread Arm A
  measured, so it is far less exposed to the over-dispersion that forced Arm A to
  3. Two sessions still make a session effect visible; one would not, and a
  single-session claim is exactly what Phase 9C was criticised for.
* **Sessions are separate collections in separate dated roots.**
* **Interleaving:** run-level, between AEP-full and B3, by the matrix's own sort
  key. **The realised ordering will be reported from the collected runs rather
  than assumed**, since Phase 8.4's `b2-paired-s1` was cell-major and B9 exists
  because of it.
* **Host:** ext4 (`/root/aep-phase13/...`), native Docker runtime, the pinned
  Redis digest — the same host as Arm A.
* **Unit of analysis: the run.**
* **Stopping rule:** fixed at 2 sessions × 120 runs. No interim look. No run
  dropped except by the harness's existing void criteria, which are reported as
  counts.

### Preconditions, checked not assumed

Before the first run: `scripts/verify_measurement_host.py` exits 0;
`AEP_HARNESS_SUSPEND_DISABLED` declared; the E5 clock check within tolerance.
Phase 11 established the clock divergence is **episodic, not a state**, so it is
measured per session and the E5 drop rate is reported as a first-class number.

### Exact analysis command

```sh
uv run --frozen --extra experiments --extra analysis python -m experiments.analyze \
  --results-root /root/aep-phase13/inflight-s<N>-2026-09-04 \
  --bootstrap-seed 20260806 --resamples 10000
```

Session diagnostics are rendered with `scripts/render_session_results.py`, which
reproduces the Arm A session files byte-for-byte and is pinned by
`tests/test_session_results_rendering.py`.

**Analysis filters by results root.** `redis-kill-inflight` derives its own
`regime_label`, so it does not collide with the preack cells — but the roots are
kept separate regardless, for the same reason Arm A's were.

---

## 6. Both outcomes are acceptable

If the arms tie, M9 closes: a cell that was "implemented but not collected"
becomes a measured, reported result, and §VI-C2 can say that the fault class is
separable only at the pre-ack boundary because that is where it was measured, not
where it was argued.

If they do not tie, the tie was an assumption the paper has been carrying since
Phase 2b §C.2, and finding that out is worth more than confirming it. Either way
the concession in §VIII-C(f) about uncollected cells is removed.

Nothing will be tuned to make the arms agree.
