# Phase 8 · pre-registration, AMENDMENT 2 — the residual imbalance, predicted

**Committed and pushed before any session runs under the amended design.**
Amends `16abc99` as further amended by `5b601d0`. Everything not amended here
stands.

Amendment 1 removed the *collinear* imbalance. It does not remove all of it, and
the residue is predictable rather than unknown. **Registering it now is what
makes the balance-check result interpretable at all**: without this, a +12 ms
outcome could not be told apart from something new.

---

## 1. The residual, and why it exists

The new sort key is `(tier, repetition, cell_key)`. All four cells run inside
each repetition, ordered by `cell_key` — and `ledger_postings` sorts before
`payments`. So within every repetition:

| offset | cell |
|---|---|
| 0 | AEP-full · `ledger_postings` (NO_READBACK) |
| **1** | **AEP-full · `payments` (AUTH)** |
| 2 | B3 · `ledger_postings` (NO_READBACK) |
| **3** | **B3 · `payments` (AUTH)** |

**AUTH lands exactly one run after its paired NO_READBACK, in all 30
repetitions.** The imbalance is no longer collinear with arm — it is a constant
lag of one run, which is a bounded quantity rather than an unidentifiable one.

## 2. The size, from session 1's measured drift

Fitted on session 1's 120 runs (`redis_kill_latency_ms` against execution
position):

| estimator | slope | lag-1 residual | of the 100 ms threshold | of the 194 ms effect |
|---|---|---|---|---|
| Theil–Sen (robust) | **9.06 ms/run** | **+9.1 ms** | 9.1% | 4.7% |
| OLS | 14.16 ms/run | +14.2 ms | 14.2% | 7.3% |

Theil–Sen is the one to weight: OLS is pulled upward by the B3 AUTH block's jump
to ~2170 ms, which is a level shift rather than a slope.

## 3. Registered prediction

> **The balance check PASSES, with a small POSITIVE median difference in AUTH's
> direction — expected +9 to +14 ms, and registered as acceptable anywhere in
> 0–20 ms.**

Positive because AUTH is always the later run; small because it is one run of
lag rather than thirty.

**What departures mean, decided now:**

| observed |median difference| | verdict |
|---|---|
| **≈ 0 to +20 ms**, positive | **As predicted.** The residual is the lag-1 effect and nothing else. Report and continue. |
| **near zero or negative** | Fine, and mildly informative: the session's drift was flatter than session 1's, or absent. Report the session's own slope beside it. |
| **+20 to +100 ms** | **Passes the threshold but is NOT passed over silently.** It means the drift is steeper than session 1's — a residual of +50 ms implies ~50 ms/run, 5× session 1's robust slope. Report the session's fitted slope and say so explicitly in 8.6. |
| **> 100 ms** | **HALTS**, as originally registered. Unchanged. |

The per-session drift slope (Theil–Sen, on that session's own runs) is reported
for **every** session regardless of outcome, so the residual is always
interpretable against the drift that produced it rather than against session 1's.

## 4. Bounded, not eliminated — and that is a choice

Randomising cell order within each repetition would remove even the lag-1 effect,
and it is identity-safe for the same reason the interleaving was: `cell_seed`
digests `matrix_seed`, `MATRIX_VERSION`, `cell.key` and `repetition`, never
position.

**It is not being done.** At ~5% of the effect the residual is smaller than the
measurement noise on the quantity it would perturb, and a predicted-and-bounded
residual is better evidence than an engineered-away one: the prediction is
falsifiable and the engineering would not be. Introducing a randomisation seed
would also add a source of between-session variation to a design whose whole
purpose is to hold everything but the arm fixed.

**8.6 must say that this was a choice** — that the residual was bounded and
predicted rather than eliminated, with this section as the reason — rather than
presenting the design as though no residual existed.

## 5. Unchanged

Everything else in `16abc99` and `5b601d0`: k = 4, the no-extension commitment,
the primary and both secondaries, the tertiary ext4 replication and its
[6.1, 28.4] containment prediction, the boundary-region verdicts, the
missing-vs-false adjudication and both gates, the corrected wall-time threshold
(6426 s), the HALT set, and session 1's status as a superseded design whose
outcome numbers are published.
