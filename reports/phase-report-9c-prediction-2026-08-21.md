# Phase 9C · pre-registration — the SHAPE of the control failure

**Committed before collecting. Same discipline as P9-A.**

P9-B's control failed: the paper's prevention cell, re-collected on its own host
with the same seed and the same configuration, moved from **10/30** to **20/30**
applied for AEP-full while B3 reproduced exactly at **28/30**. That failure is
established. **What is not established is its shape**, and the shape determines
what the paper may say.

Two hypotheses fit the evidence, and they have different consequences:

- **(i) VARIABLE** — the quantity is highly variable across sessions. 10/30 and
  20/30 are two draws from one wide distribution and neither is "the" value.
  *Consequence: the paper reports a range and declares the magnitude unstable.*
- **(ii) STATE CHANGE** — something changed between 2026-08-07 and now. The
  quantity is stable within each state and different between them.
  *Consequence: the paper may keep a point estimate, conditioned on a state it
  can name.*

A third outcome is possible and is pre-registered so it cannot be discovered
conveniently later:

- **(iii) TODAY WAS THE OUTLIER** — the quantity is stable near 10/30 and
  P9-B's 20/30 was the unusual draw.

---

## 1. What is knowably different about this host — recorded BEFORE collecting

Checked today, cheaply, as instructed. **The answer is: almost nothing is
recorded as different, and the one thing that would matter most is not recorded
at all.**

| Property | 2026-08-07 collection | 2026-08-21 (P9-B) | Same? |
|---|---|---|---|
| Cell identity hash | `aep_full-none-ledger_postings-**8530cc0f**-r0` | `aep_full-none-ledger_postings-**8530cc0f**-r0` | ✅ **identical** |
| Per-run `seed` | `1325779346` | `1325779346` | ✅ identical |
| `platform` fingerprint | `Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.39` | identical string | ✅ identical |
| Redis image | `redis:7.2.5-alpine@sha256:6aaf3f5e…` | same digest, verified on the running container | ✅ identical |
| `redis_kill_point` / `redis_kill_delay_ms` | `after_intent_before_barrier` / `0` | same | ✅ identical |
| `durability_timeout_ms`, `crash_delay_ms`, `workers`, `executions_per_worker` | 2000 / 400 / 1 / 1 | same | ✅ identical |
| **run-config.json overall** | — | — | **40 of 44 keys identical** |
| `results_root`, `mock_api_config_path`, `config_digest` | matrix | b2-2026-08-21 | ⚠️ bookkeeping only (digest derives from the path) |
| `suspend_disabled_declared` | **True** | **False** | ⚠️ **differs** — E5 gate; governs whether *timing* is admitted, not counts |
| **Redis container created** | — | **2026-08-13T07:19:04Z** | ⚠️ **container recreated between the two collections** |
| **Docker version** | **not recorded** | 29.4.3 | ❌ **not comparable — the harness does not capture it** |

**Finding, recorded now: the run artifacts capture `platform` but not the Docker
version or daemon state.** `docker kill` latency is precisely the quantity the
audit's A3 says the effect size depends on, and it is the one property that
cannot be compared across the two collections because nothing wrote it down.
That is a provenance gap in the harness, independent of how this measurement
turns out.

**So there is no recorded evidence for (ii).** Two candidate state changes exist
and neither is a smoking gun: the Redis container was recreated on 2026-08-13,
and the E5 declaration differs (which does not gate counts).

---

## 2. What I expect — (i), for a specific and checkable reason

**I expect (i), and I expect it because the arithmetic already fits.**

| Candidate true rate | mean at n=30 | ±1.96 sd | contains 10? | contains 20? |
|---|---|---|---|---|
| p = 0.3333 | 10.0 | [4.9, 15.1] | yes | **no** |
| **p = 0.5000** | **15.0** | **[9.6, 20.4]** | **yes** | **yes** |
| p = 0.6667 | 20.0 | [14.9, 25.1] | **no** | yes |

**A single true rate near p ≈ 0.5 with ordinary binomial sampling at n=30
explains both observations without any state change.** Fisher on 10/30 vs 20/30
gives **p = 0.0194** — unlikely under one fixed rate, but 0.0194 is the kind of
value that turns up once in fifty comparisons, and this is a quantity nobody had
ever sampled twice.

**Point prediction:** the three new sessions scatter around **15**, sd ≈ 2.7,
with most or all falling in **[10, 20]**.

**I would not bet heavily on this.** It is the hypothesis that requires no new
mechanism, which makes it the right default and also the one I am most likely to
be biased toward.

---

## 3. Discrimination criteria — thresholds, fixed now

Let **S = {s₁, s₂, s₃}** be the three new AEP-full applied counts (n=30 each).
Prior observations: **10** (2026-08-07) and **20** (2026-08-21).

| Verdict | Criterion |
|---|---|
| **(i) VARIABLE** | `range(S) ≥ 8` **OR** (`min(S) ≤ 13` **AND** `max(S) ≥ 18`) |
| **(ii) STATE CHANGE** | `range(S) ≤ 5` **AND** `min(S) ≥ 17` |
| **(iii) TODAY WAS THE OUTLIER** | `range(S) ≤ 5` **AND** `max(S) ≤ 16` |
| **AMBIGUOUS** | anything else — **reported as ambiguous, not forced into a label** |

`range(S) = max(S) − min(S)`.

### 3.1 B3 is the stability reference, and can overturn the framing

B3 does not wait for the barrier, so it dispatches regardless of when Redis dies:
its count should be **timing-insensitive**. It was 28/30 in both collections.

| B3 outcome | Meaning |
|---|---|
| `range(B3 counts across all 5 observations) ≤ 4` | variance is **specific to the timing-sensitive arm**, as the mechanism predicts |
| `range ≥ 5` | ⚠️ **the framing is wrong.** Variance is not specific to the barrier-waiting arm, and the whole detection/prevention decomposition needs re-examining before any claim is made |

### 3.2 HALT conditions — unchanged from P9-A §6A.3

Any undetected duplicate, any lost effect, `executions ≠ runs × 1`, or a
duplicated `(system, response_class)` pair stops the phase.

### 3.3 The stopping rule carries over in full

n = 30 per arm per session, fixed. **Three sessions, not "three or more".** The
same seven replaceable causes plus cause 8 (host not quiescent). The denominator
is attempted runs. Three host readings per session — before, between arms, after.
**No session is added because the first three were inconclusive**; "AMBIGUOUS" is
a permitted outcome and is reported as one.

---

## 4. What this measurement cannot settle

- It cannot distinguish (ii) *caused by the container recreation* from (ii)
  *caused by anything else*, because Docker version and daemon state were never
  recorded on 2026-08-07.
- It cannot recover the original session's `docker kill` latency distribution.
  That data does not exist.
- Three sessions is a small sample for a variance question. If the verdict is
  **(i)**, the honest statement is "the magnitude is unstable", **not** an
  estimate of how unstable.

---

## 5. Signed state

| | |
|---|---|
| Committed against | `3d2c2a8` + P9-B's uncommitted results |
| AUTH `redis-kill-preack` rows | **0** — AUTH was never collected and is not collected by this phase |
| Sessions collected at time of writing | **1** (P9-B's control) |
| Sessions this pre-registration commits to | **exactly 3 more** |

*No paper text, no macro, and no analysis of P9-B beyond the control verdict has
been performed. This file is written before the three sessions exist.*
