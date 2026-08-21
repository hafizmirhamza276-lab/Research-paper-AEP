# Phase 9C · result — the shape of the control failure

**Verdict, by the criteria pre-registered in `phase-report-9c-prediction-2026-08-21.md`
(commit `079d092`) before these sessions existed:**

# **(i) VARIABLE**

The quantity is not stable. It is not a point estimate with sampling noise
around it — **the underlying rate itself moves between sessions.**

*No paper text and no macro has been touched. This file reports the distribution
and stops.*

---

## 1. The distribution

**AEP-full, `executions_with_an_applied_effect` out of 30, `redis-kill-preack`
× `after_intent_before_barrier` × `NO_READBACK`, identical seed and
configuration in every case:**

| Session | Date | AEP-full | rate | B3 | rate |
|---|---|---|---|---|---|
| original (the paper's cell) | 2026-08-07 | **10**/30 | 0.3333 | 28/30 | 0.9333 |
| P9-B control | 2026-08-21 20:12 | **20**/30 | 0.6667 | 28/30 | 0.9333 |
| session 1 | 2026-08-21 21:53 | **12**/30 | 0.4000 | 28/30 | 0.9333 |
| session 2 | 2026-08-21 22:31 | **4**/30 | 0.1333 | 28/30 | 0.9333 |
| session 3 | 2026-08-21 23:08 | **7**/30 | 0.2333 | 28/30 | 0.9333 |

```
AEP-full applied /30, five observations:

  0    5    10   15   20   25   30
  |....|....|....|....|....|....|
       4      = session 2
          7   = session 3
            10 = 2026-08-07  <- the value the paper prints
              12 = session 1
                     20 = P9-B control
```

**Rate range 0.1333 – 0.6667. A five-fold spread on an identical cell.**

## 2. The criteria, applied

`S = {12, 4, 7}` — the three sessions the pre-registration committed to.

| Verdict | Criterion | Result |
|---|---|---|
| **(i) VARIABLE** | `range(S) ≥ 8` OR (`min ≤ 13` AND `max ≥ 18`) | **range(S) = 12 − 4 = 8 → TRUE** |
| (ii) STATE CHANGE | `range(S) ≤ 5` AND `min(S) ≥ 17` | false |
| (iii) TODAY WAS THE OUTLIER | `range(S) ≤ 5` AND `max(S) ≤ 16` | false |

**(i) fires on the threshold exactly** — range 8 against a threshold of ≥ 8. It
is not a comfortable margin and it is reported as it is. The supporting evidence
below is what makes the verdict robust rather than marginal.

## 3. It is not binomial noise — the rate itself moves

| | |
|---|---|
| pooled | 53/150 = 0.3533 |
| session mean ± sd | 10.60/30, sd **6.07** |
| binomial sd expected at p = 0.3533, n = 30 | **2.62** |
| **over-dispersion factor** (observed variance ÷ binomial variance) | **5.37** |

A factor of 1.0 would mean pure binomial sampling around one fixed rate.
**5.37 means the rate is not fixed.**

This also **refutes the specific mechanism I predicted.** P9C §2 argued that a
single true rate near p ≈ 0.5 would explain both 10 and 20 with ordinary
sampling. It would have — but it cannot explain 4 and 20 in the same set, and
the over-dispersion rules it out.

**Two intervals, and the difference between them matters:**

| Method | 95% interval on the AEP-full rate |
|---|---|
| naive Wilson on pooled 53/150 — **wrong here** | [0.281, 0.433] |
| session-level mean ± t·SE, session as the unit — **the honest one** | **[0.102, 0.604]** → counts **[3.1, 18.1]/30** |

Pooling the 150 executions treats them as independent draws and produces an
interval **four times too narrow**, because executions within a session share a
host-timing state. This is the same clustering error the paper already avoids
elsewhere with its run-cluster bootstrap.

## 4. B3 is flat, and that is the load-bearing control

**B3 recorded 28/30 in every one of the five sessions. Range 0.**

The pre-registered overturn condition was `range(B3) ≥ 5`, which would have meant
the variance was not specific to the barrier-waiting arm and the whole
detection/prevention framing needed re-examining. **It did not fire. The framing
holds.**

This is the strongest evidence in the whole phase, and it is worth stating
plainly: **the variance is confined entirely to the arm whose behaviour depends
on kill timing.** B3 never waits for the barrier, so it dispatches regardless of
when Redis dies — timing-insensitive, and it did not move by a single execution
across five sessions and 150 runs. AEP-full dispatches only if `WAITAOF`
completed before the kill landed — timing-sensitive, and it moved 4 → 20.

**The mechanism the paper describes is intact. The magnitude it reports is not
a stable quantity.**

## 5. What this does to the number the paper prints

`\UnwantedPrevented{}` = B3 applied − AEP-full applied:

| session | 2026-08-07 | P9-B | s1 | s2 | s3 |
|---|---|---|---|---|---|
| **UnwantedPrevented** | **18** | 8 | 16 | 24 | 21 |

Mean **17.4**, range **8 – 24**. **The paper prints 18.**

Two things are true at once and both belong in any decision:

- **The paper's number is not biased.** 18 sits essentially on the mean of five
  independent observations (17.4). Nothing was cherry-picked.
- **The paper presents as a point estimate a quantity that ranges 8 to 24 across
  sessions**, and the direction — B3 commits effects AEP-full withholds — held in
  all five.

## 6. Was anything knowably different about the host? No.

Recorded before collecting (P9C §1) and unchanged by the result:

- **Cell identity hash identical** in both trees: `…-8530cc0f-r0`
- **Per-run seed identical**: `1325779346`
- **`platform` fingerprint identical**: `Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.39`
- **Redis image identical**: pinned `sha256:6aaf3f5e…`, verified on the running container
- **40 of 44 `run-config.json` keys identical**; three differences are bookkeeping, the fourth is `suspend_disabled_declared` (the E5 timing gate, which does not gate counts)

**Finding carried forward: the harness records `platform` but not the Docker
version or daemon state.** `docker kill` latency is precisely the quantity the
audit's A3 identifies as driving this effect, and it is the one property that
could not be compared across collections because nothing wrote it down. That is
a provenance gap independent of this result — and given verdict (i), it is now
the gap that matters most.

## 7. My prediction, scored honestly

| Claim | Outcome |
|---|---|
| Verdict would be **(i) VARIABLE** | ✅ **right** |
| Centre near **15** | ❌ **wrong** — new-session mean 7.7 |
| "most or all in [10, 20]" | ❌ **wrong** — 1 of 3 (12); 4 and 7 fell below |
| Mechanism: a single fixed rate ≈ 0.5 | ❌ **wrong** — over-dispersion 5.37 refutes it |

I got the shape right and the location wrong, and the reason I gave for the
shape was itself incorrect. Recorded because P9C §2 said I would not bet heavily
on it and named the bias — "it is the hypothesis requiring no new mechanism,
which makes it both the right default and the one I am most likely biased
toward." That caveat was warranted.

## 8. Run accounting — the denominator is attempted runs

| Collection | attempted | completed | discarded |
|---|---|---|---|
| P9-B control | 60 | 60 | 0 |
| session 1 | 60 | 60 | 0 |
| session 2 | 60 | 60 | 0 |
| session 3 | 60 | 60 | 0 |
| **total** | **240** | **240** | **0** |

**Zero replacements used of the 12 permitted.** No HALT condition fired: zero
undetected duplicates, zero lost effects, `executions = runs × 1` in every cell,
canaries 30/30 in all ten arm-sessions, no duplicated `(system, response_class)`
pair.

## 9. Host readings — three per session, as committed

| Session | before | after |
|---|---|---|
| P9-B | 20:10:48 · 1.84 1.37 1.08 | 20:56:00 · 2.49 1.32 1.02 (between: 20:52:51 · 0.72) |
| 1 | 21:16:55 · 0.10 0.17 0.39 | 21:53:08 · 0.50 0.51 0.55 |
| 2 | 21:55:45 · 0.22 0.47 0.54 | 22:31:25 · 0.36 0.43 0.45 |
| 3 | 22:32:56 · 0.17 0.37 0.43 | 23:08:39 · 0.63 0.71 0.66 |

Two containers throughout (`aep-phase2-redis72`, `aep-phase2-toxiproxy`).

**Load does not explain the result.** Session 2 produced the *lowest* AEP-full
count (4/30) on a **quiet** host (0.22 → 0.36), and P9-B produced the *highest*
(20/30) on the **busiest** (1.84 → 2.49). If anything the association runs
opposite to the naive expectation, and with five points it is not worth
modelling. Cause 8 (host not quiescent) never fired.

---

## 10. Scope — what this phase did not do

- **AUTH was never collected.** P9-A §3 forbade a cross-class claim once the
  control failed, and that still holds.
- **No macro, no generated file, no manuscript text was touched.**
- **Nothing was re-run to see if it would go away.** Every session collected is
  reported.
- **B2's original question — prevention beyond one capability class — remains
  unanswered**, and is now secondary to what this measured instead.

**The paper decision comes next, and is not taken here.**
