# Phase 8.5 §3.2 and §3.3 — the robustness check corroborates, the invariant holds

**§3.2 agrees with §3.1: the interval contains zero, for the same reason —
the sessions disagree with each other.**
**§3.3 passes with zero exceptions in 131 applied executions, and is
confirmatory of code-enforced behaviour rather than a discovered property.**

**B3's separation did not bite.** Both sections are AEP-full only, as registered.
The 30/30 arms are never fitted here, so the flag raised in advance did not need
to be acted on.

---

## 1. §3.2 — the unadjusted paired difference

`d_i = applied_AUTH(i) − applied_NO_READBACK(i)`, session as the unit, mean with
a two-sided 95% t-interval on k−1 df. Same construction as the primary's interval
and as `paper_tables.py:1899-1901`, so the paper carries one inferential standard.

| session | AUTH | NO_READBACK | d (count) | d (pp) |
|---|---|---|---|---|
| s1 | 18/30 | 18/30 | **0** | 0.0 |
| s2 | 15/30 | 18/30 | **−3** | −10.0 |
| s3 | 17/30 | 10/30 | **+7** | +23.3 |
| s4 | 23/30 | 12/30 | **+11** | +36.7 |

| | counts | percentage points |
|---|---|---|
| mean | **+3.750** | **+12.50 pp** |
| sd across sessions | 6.397 | 21.32 |
| t(3, 0.975) | 3.182 | 3.182 |
| half-width | 10.177 | 33.92 |
| **95% interval** | **[−6.43, +13.93]** | **[−21.42, +46.42] pp** |
| **contains 0** | **YES** | **YES** |

**The robustness check corroborates the primary.** §3.1 returned CONFIRMS on
+0.583 log-odds; §3.2 returns an interval containing zero on +12.5 pp. Two
different quantities, one adjusted and one not, reaching the same verdict.

The naive Wilson interval on pooled runs is **forbidden** by the plan — 9C §3
shows it four times too narrow — and was not computed.

### And here too, containing zero is not an absence of effect

The mean is **+12.5 pp**. That is not a small number: it is roughly a fifth of
the barrier's own measured effect of 58.0 pp. The interval contains zero because
the **sd across sessions is 21.3 pp**, larger than the mean itself — not because
the sessions agree on nothing happening. The same sentence as §3.1's: **the
heterogeneity is the result.**

## 2. The phase did not achieve its registered precision, and that must be said

The plan projected §3.2's half-width at k = 4 as **19.6 pp**, and made a specific
argument from it:

> **k = 4 is also the point where the two analyses become commensurable** —
> 3.1's MDE (17.3 pp) and 3.2's half-width (19.6 pp) agree, so the robustness
> check can actually corroborate the primary. At k = 3 they diverge badly
> (20.0 vs 30.6), which would make 3.2 decorative.

**The realised half-width is 33.92 pp — 1.73× the projection.**

| | registered | realised |
|---|---|---|
| §3.2 half-width at k = 4 | 19.6 pp | **33.9 pp** |
| implied between-session sd | 12.3 pp | **21.3 pp** |

**The between-session standard deviation is about 73% larger than the projection
assumed.** k was not wrong; the variance was.

**Consequences, stated rather than absorbed:**

1. **The registered MDE of 17.3 pp was not achieved.** An effect of exactly the
   minimum detectable size would not have been detected by §3.2, whose interval
   is nearly twice that wide.
2. **The commensurability argument for k = 4 does not survive contact with the
   data.** The realised half-width of 33.9 pp is worse than the projection for
   k = 3 (30.6 pp). On the plan's own criterion, the realised precision is the
   one it called "decorative".
3. **This does not change the verdict, and must not be used to reopen it.** The
   registered rule was applied exactly as written to the k = 4 set, and the
   pre-registration forbids extending k after seeing results. What it changes is
   what CONFIRMS *means*: it is failure to reject at a precision materially worse
   than the one the design promised.
4. **It is a finding about the design, and it goes in 8.6 §F** beside the two
   contradicted predictions. The projection assumed a between-session variance
   the host did not deliver — which is the same instability visible in the
   balance figures (+13.0, −97.7, +73.6, +41.3) and in §3.1's coefficient spread.

### But §F is not where this primarily lives — it is bound to the verdict

**Filing this only as a finding would be the wrong placement, and the reason is
arithmetic.** Set the three registered numbers beside the observed one:

| | |
|---|---|
| registered MDE | 17.3 pp |
| projected half-width | 19.6 pp |
| **realised half-width** | **33.9 pp** |
| **observed mean effect** | **+12.5 pp** |

**The mean is smaller than the half-width. The design could not have detected the
effect it found.**

So the verdict is not "no effect was detected"; it is "an effect of +12.5 pp was
observed by an instrument too blunt to resolve it, and by the registered rule
that counts as failure to reject". Those are very different sentences, and only
the second is true.

**Therefore, wherever CONFIRMS is stated — 8.6, `06-evaluation.tex`,
`08-threats.tex`, any macro or abstract sentence — the realised precision travels
with it.** The §F entry stays, and is not a substitute: a finding among findings
can be read past, and a reviewer who reaches this unaided will reasonably treat
its absence as the paper's weakest point.

## 3. §3.3 — the fail-closed invariant

For every AEP-full execution with an applied effect, the run must show traversal
of `AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT`. Predicted: zero exceptions.
Any exception HALTS the phase.

**The column was verified to be the right one rather than assumed.**
`injector.py:373-381` emits `durability_ack_observed` **only** when the traversed
checkpoint's name equals `AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT` — it
returns early for every other point — so the field is exactly the traversal
record the plan names.

| session | applied executions | of which ack observed | exceptions |
|---|---|---|---|
| s1 | 36 | 36 | **0** |
| s2 | 33 | 33 | **0** |
| s3 | 27 | 27 | **0** |
| s4 | 35 | 35 | **0** |
| **total** | **131** | **131** | **0** |

**Zero exceptions. No halt.**

### Stated at the strength the plan requires, and no higher

**This is confirmatory of code-enforced behaviour along a single code path. It is
not a discovered property.** `injector.py:351-356` says so in the source:
`_checkpoint` is awaited on the protocol path, so *dispatched ⇒ traversed* holds
by construction, and `DispatchAuthorizationError` already enforces the invariant
in code. Zero exceptions was near-certain in advance, and what the check mostly
exercises is **the observer's own fidelity**.

Its value is that the claim now rests on 131 recorded executions rather than on
reading the source. That is worth having, and it is all it is worth.

**One-directional.** `ack ⇒ applied` is **not** claimed and is not testable from
this record: the kill can land after the acknowledgement and before transmission,
which is precisely the window `after_barrier_before_dispatch` names. Only
`applied ⇒ acknowledged` is established.

## 4. Status

§3.1, §3.2 and §3.3 are complete. No halt condition fired in any of them.
8.6 §F has not been written. No macro, paper file or pre-registration has been
modified.
