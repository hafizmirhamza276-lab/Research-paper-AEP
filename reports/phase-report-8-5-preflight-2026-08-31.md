# Phase 8.5 steps 2–3 — verification, reproduction, and per-session feasibility

**Nothing has been fitted.** This is the preflight the plan requires before any
model is estimated: verify the roots, reproduce a known answer through the
pipeline before trusting it on an unknown one (**R2**), and establish that the
per-session fit is possible at all.

---

## 1. Step 2 — all four roots verify

Each root checked against **its own** entry count, since the sessions are not
uniformly instrumented and a single expected number would be wrong for three of
them.

| session | entries in `SHA256SUMS` | OK | FAILED | exit |
|---|---|---|---|---|
| `b2-paired-v2-s1` | 15 | 15 | 0 | **0** |
| `b2-paired-v2-s2` | 17 | 17 | 0 | **0** |
| `b2-paired-v2-s3` | 18 | 18 | 0 | **0** |
| `b2-paired-v2-s4` | 18 | 18 | 0 | **0** |

## 2. Step 3 — the Δ median log values reproduce exactly

Recomputed from each frozen `analysis/per-execution.csv` with
`covariate_check.py`, against the values the plan was approved on:

| session | reproduced | expected | match |
|---|---|---|---|
| s1 | **+0.012398** | +0.0124 | ✅ |
| s2 | **−0.085097** | −0.0851 | ✅ |
| s3 | **+0.069105** | +0.0691 | ✅ |
| s4 | **+0.041653** | +0.0417 | ✅ |

All four agree to the precision stated. **The pipeline reproduces a known answer,
so it may be trusted on the unknown one.** The halt condition on non-reproduction
does not fire.

**Amendment 3 §2 adjudicated over the k = 4 set:** |Δ| < 0.02 in **1 of 4**
sessions. The registered rule is a *majority*. **No majority, so the covariate is
not degenerate**, and plan §3.1's covariate-adjusted model is the primary result.
§3.2 is a robustness check, not a fallback.

`n = 30/30` per session for the two AEP-full arms in every session, and the
covariate is present for **30/30 in all eight arm-sessions** — no missing-data
handling is needed and none is applied.

## 3. Per-session fit feasibility — no separation in the primary

Checked from the frozen data before fitting, as the plan requires.

**AEP_FULL — the primary estimand's system:**

| session | AUTH n | applied | NO_READBACK n | applied | separation |
|---|---|---|---|---|---|
| s1 | 30 | **18** | 30 | **18** | no |
| s2 | 30 | **15** | 30 | **18** | no |
| s3 | 30 | **17** | 30 | **10** | no |
| s4 | 30 | **23** | 30 | **12** | no |

**Every count is strictly between 0 and 30 in every arm of every session. No
separation. The per-session fit is feasible in all four.** The halt condition
does not fire.

The applied counts are exactly those the plan change quoted — **18/15/17/23** and
**18/18/10/12**.

**One correction to the denominator.** The change described "60 runs per arm per
session"; it is **30 runs per arm per session**. 60 is AEP-full's per-session
*total* across both arms. The quoted counts are out of 30, not 60, which makes
them proportionally twice as far from the boundaries as a reading of 60 would
suggest — so the feasibility conclusion is strengthened, not weakened.

**B3 — degenerate, as expected, and not in the primary:**

| session | AUTH | NO_READBACK |
|---|---|---|
| s1–s4, all four | **30/30** | **28/30** |

`AUTH = 30/30` is complete separation in all four sessions. **This does not block
anything**: B3 is not in the primary estimand. It is recorded because it is the
quantitative form of the plan's §4 finding — B3's arms are constant across 480
runs because `b3_no_barrier.py:88` returns `True` without issuing a command, so
B3's dispatch path contains no barrier wait and cannot respond to the quantity
being perturbed.

The `28/30` is worth its own line: **identical in all four sessions**, so those
two failures are not timing-driven.

## 4. What the per-session model is, exactly

Plan §3.1 registers session as a **fixed effect**. In a per-session fit that term
is absorbed — there is one session — so each session's model is

> logistic regression of `applied_effects` ∈ {0,1} on capability class, with
> `log(redis_kill_latency_ms)` as covariate

which is the registered model with its session term saturated, not a different
model. Four coefficients, then mean and a two-sided t(3) interval across them,
matching `paper_tables.py:1899-1901`'s construction for `[6.1, 28.4]`.

**Units.** The covariate is registered as `log(issue_to_return_ns)` and the frozen
analysis exposes it as `redis_kill_latency_ms`, derived from the same field
(`analyze.py:563`). A unit change is a constant shift in log space, so it moves
the intercept and leaves the class coefficient unchanged. Stated so the
substitution is visible rather than silent.

## 5. Halt conditions — none fired

| condition | status |
|---|---|
| any root fails verification | **no** — all four exit 0 |
| the Δ medians do not reproduce | **no** — all four match |
| a per-session fit separates or fails to converge | **no separation**; convergence is checked at fit time |
| the cell structure differs from §3.1's assumption | **no** — 2 systems × 2 response classes × 2 endpoints × 30 |

Disagreement between the t(3) and pooled Wald intervals was removed from the halt
list by instruction: it is a **dual result**, pre-committed to t(3), reported both
ways.
