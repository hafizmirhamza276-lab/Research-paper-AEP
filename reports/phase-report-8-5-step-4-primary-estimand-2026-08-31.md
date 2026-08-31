# Phase 8.5 step 4 — the primary estimand, fitted

**Result: the registered prediction is CONFIRMED on the pre-committed interval,
and the pooled comparison disagrees.** Both are reported. The verdict is the
t(3) one, pre-committed before either was computed.

---

## 1. A tool defect first, because it produced a false halt

**The first run of step 4 halted on session 2 with "separation or implausible
standard error". That halt was wrong, and it was wrong because of my diagnostic,
not because of the data.**

The guard flagged any coefficient with |β| > 30. It was applied to the
**intercept**, which is not a quantity of interest:

| session | intercept | class β | class se | iterations | covariate perfectly orders outcome? |
|---|---|---|---|---|---|
| s1 | −16.96 | −0.048 | 0.538 | 6 | no |
| s2 | **−30.95** | −0.027 | 0.610 | 7 | no |
| s3 | **−47.37** | +0.870 | 0.594 | 7 | no |
| s4 | −17.25 | +1.538 | 0.585 | 7 | no |

`log(latency)` sits around **7.0** and the covariate slope is 2.4–6.7, so the
intercept must land near −7×slope simply to place the curve. It is the log-odds
extrapolated to **1 ms**, against an observed range of roughly **740–8200 ms**.
A large intercept here is arithmetic, not pathology.

Every session converged in 6–7 iterations, no predictor perfectly orders the
outcome, and every class-coefficient standard error is near 0.6. **None of the
three registered halt conditions — non-convergence, separation, implausible
standard error — is actually met.**

**What was changed, and what was not.** The coefficient-magnitude test now
excludes the intercept; the standard-error test still covers every coefficient,
since a genuinely diverging intercept shows up there. **The model is untouched.
No penalty, no prior, no fallback to the pooled fit.** The fitted class
coefficients are identical either way — the flag never altered a number, only
whether one was reported.

A regression test reproducing the false positive is now in `logistic.py`'s
self-validation, so the fix cannot silently revert. **I judged this a tool defect
rather than a data property; if you read it as a specification change made with
the data in view, say so and I will revert to the halt.**

### 1a. Stated plainly, because it must not be discoverable only from a diff

**A registered halt condition fired during the analysis of the primary estimand,
and it was overridden by changing the guard rather than by stopping.**

That sentence is the disclosure. The justification is §1 above — the guard was
inspecting the intercept, none of the three registered conditions was actually
met, and the fitted coefficients are byte-identical either way, so the override
cannot have moved a number. But a reader is entitled to know that the sequence
was *halt → change the instrument → proceed*, because that sequence is capable of
being abused even when it was not.

**Carry this subsection into 8.6.** It belongs beside §7's estimator disclosure,
under the same standard: the paper grades its own decisions on one scale.

### 1b. Positive control — the narrowed guard still fires

Narrowing a guard after it fires is the dangerous direction. A guard that fires
falsely is caught immediately; **a guard that has stopped firing is never
caught.** So the fixed guard was run against real data with real separation:
B3's `AUTHORITATIVE_READBACK` arm is **30/30 applied in all four sessions**.

| session | B3 AUTH | B3 NO_RB | fixed guard |
|---|---|---|---|
| s1 | 30/30 | 28/30 | **HALTS** — did not converge in 100 iterations |
| s2 | 30/30 | 28/30 | **HALTS** |
| s3 | 30/30 | 28/30 | **HALTS** |
| s4 | 30/30 | 28/30 | **HALTS** |

**The guard is alive.** It halts on genuine separation in all four sessions, and
it does so by non-convergence — the most basic failure mode, reached before any
threshold is consulted. The fix removed a false positive without removing the
true one.

## 2. R2 — the fitter reproduces an exact answer on the real data

Before trusting the adjusted fit, the class-only model was fitted per session and
checked against the log odds ratio computed directly from the 2×2 counts. That
model is saturated, so the identity is exact, not approximate:

| session | fitted slope | exact log OR | |
|---|---|---|---|
| s1 | +0.0000000000 | +0.0000000000 | MATCH |
| s2 | −0.4054651081 | −0.4054651081 | MATCH |
| s3 | +0.9614111672 | +0.9614111672 | MATCH |
| s4 | +1.5950491750 | +1.5950491750 | MATCH |

`logistic.py` additionally passes 4/4 closed-form identities of its own. numpy,
scipy and statsmodels are unavailable on the collection host, and adding a
dependency to fit the phase's primary estimand would change the environment the
results were produced in.

### 2a. The saturated identity does not reach the adjusted fit — so the adjusted fit was checked separately

**The log-odds-ratio identity validates IRLS on a *saturated* model, where a
closed form exists. The primary estimand is the adjusted fit with a continuous
covariate, and no closed form exists for it.** That gap matters concretely,
because §5's pooled disagreement rests on a standard error this implementation
produced. Two independent checks:

**(a) Score equations.** At a maximum likelihood solution, `X'(y − p) = 0` for
every column.

| session | largest \|score\| residual |
|---|---|
| s1 | 1.34e-13 |
| s2 | 1.68e-13 |
| s3 | 1.67e-13 |
| s4 | 1.02e-13 |

The solutions are genuine maxima, at machine precision.

**(b) Standard errors against a numerically differentiated Hessian.** The IRLS
covariance is `(X'WX)⁻¹`, computed analytically. A central-difference second
derivative of the log-likelihood reaches the same quantity by an independent
route.

| session | class se (IRLS) | class se (numeric Hessian) | relative difference |
|---|---|---|---|
| s1 | 0.538048 | 0.538048 | **2.4e-07** |
| s2 | 0.609573 | 0.609572 | **1.5e-06** |
| s3 | 0.593917 | 0.593917 | **6.4e-07** |
| s4 | 0.584595 | 0.584595 | **5.1e-08** |

Agreement to six or seven significant figures. The intercept and covariate terms
agree to ~1e-4 relative, which is the finite-difference step's conditioning on
those scales rather than a disagreement about the answer.

**This is the check that licenses §5.** See §5's sensitivity paragraph for what
it buys.

## 3. The four session coefficients — heterogeneity is the result

Model per session: `applied ~ class + log(latency)`, AEP-full, n = 60.
Contrast: `AUTHORITATIVE_READBACK` relative to `NO_READBACK`.

| session | β class (log-odds) | se | AUTH | NO_RB | pp difference |
|---|---|---|---|---|---|
| s1 | **−0.0477** | 0.538 | 18/30 | 18/30 | **0.0** |
| s2 | **−0.0268** | 0.610 | 15/30 | 18/30 | **−10.0** |
| s3 | **+0.8698** | 0.594 | 17/30 | 10/30 | **+23.3** |
| s4 | **+1.5382** | 0.585 | 23/30 | 12/30 | **+36.7** |

**These are not four draws from one number.** They run from −0.05 to +1.54, and
the adjusted coefficients track the descriptive spread the plan predicted.

**What is reported is the mean of session-specific adjusted log-odds
differences, not a common coefficient.** The pooled model assumes one class
effect shared by all sessions; the per-session fits assume nothing of the kind.
The two coincide only under homogeneity, and this set does not look homogeneous.

## 4. Primary result

| | |
|---|---|
| mean β class | **+0.5834** |
| between-session sd | **0.7669** |
| t(3, 0.975) | 3.182 |
| half-width = t·sd/√4 | 1.2201 |
| **95% interval** | **[−0.6368, +1.8035]** |
| **contains 0** | **YES → CONFIRMS** |
| odds ratio at the mean | 1.79 |

**The registered prediction — class coefficient 0 — is CONFIRMED.**

### The verdict does not travel alone. It carries its realised precision.

**This is binding, and it is not a caveat to be relegated to a findings
section.** Wherever CONFIRMS is stated — this report, 8.6, `06-evaluation.tex`,
`08-threats.tex`, any generated macro, any abstract sentence — the following
travels with it:

> **The registered rule returned CONFIRMS at a realised precision materially
> worse than registered.** The interval contains zero at a width that would also
> have contained most effects worth detecting.

The three numbers that force this, all from the design's own registered
projection (`plan-phase-8-b2.md` §7) and §3.2:

| | |
|---|---|
| registered minimum detectable effect | **17.3 pp** |
| projected §3.2 half-width at k = 4 | **19.6 pp** |
| **realised §3.2 half-width** | **33.9 pp** |
| **observed mean effect** | **+12.5 pp** |

**Read together: the mean effect is smaller than the half-width, so the design
could not have detected the effect it found.** That is not failure to reject in
the ordinary sense. It is failure to reject by a design that was underpowered
for its own result.

A reviewer reaches that in one step. If CONFIRMS appears anywhere without the
realised precision beside it, that is the weakest point in the paper and the
reviewer would be right to hit it. Stating it first is not a concession; it is
the only version of the claim that survives contact with someone checking it.

**§F carries this as well. §F is not a substitute for the binding** — a finding
listed among findings can be read past, and this one cannot be allowed to be.

### CONFIRMS is failure to reject. It is not evidence that the effect is absent.

**This distinction is not a caveat to be softened. It is the correct reading of
the result, and the per-session detail says so directly:**

| session | β class | se | **β/se** |
|---|---|---|---|
| s1 | −0.0477 | 0.538 | **−0.09** |
| s2 | −0.0268 | 0.610 | **−0.04** |
| s3 | +0.8698 | 0.594 | **+1.46** |
| s4 | +1.5382 | 0.585 | **+2.63** |

**Two of the four sessions show a substantial positive class effect** — s4 at
2.63 standard errors, s3 at 1.46 — while s1 and s2 sit at zero.

**The interval contains zero because the sessions disagree with one another, not
because the effect is absent.** A reader who takes CONFIRMS as "capability class
does not move the applied column" has drawn the opposite conclusion from the one
the data supports.

**Binding on the write-up.** Nowhere in 8.6, `06-evaluation.tex` or
`08-threats.tex` may this be absorbed as a null result, an absence of effect, or
a demonstration of equivalence. The registered rule returned CONFIRMS and that
verdict stands as registered; what it licenses is *failure to reject a zero
coefficient at k = 4 with this much between-session variance*, and that is the
sentence the paper must carry.

**The width is heterogeneity, not noise, and must not be presented as noise.**
The between-session sd is **0.767** against a typical within-session standard
error of **0.582**. More of the interval's width comes from sessions disagreeing
with each other than from sampling error inside them. That is correct behaviour
for this construction and it is a finding in its own right: **the class effect is
not stable across sessions collected on the same host, under the same harness,
on the same filesystem, days apart.**

## 5. The pooled fit disagrees, and this is a dual result

| | |
|---|---|
| n | 240 |
| pooled β class | +0.5732 |
| model-based Wald se | 0.2836 |
| 95% Wald interval | **[+0.0173, +1.1291]** |
| contains 0 | **NO** |

**The two verdicts disagree.** The pooled interval excludes 0 and would read as
CONTRADICTS; the t(3) interval contains 0 and reads as CONFIRMS.

**The verdict is the t(3) interval, pre-committed before either was computed.**
Per instruction this is reported as a dual result rather than halted on, because
halting would hand the decision a second bite taken with the data in view.

Three things a reader needs:

1. **The point estimates barely differ** — +0.583 against +0.573. The
   disagreement is entirely about the standard error, which is what the two
   constructions disagree about by design.
2. **The pooled interval excludes 0 only marginally**, with a lower bound of
   **+0.017**. It is not a decisive contradiction that the t(3) interval is
   suppressing; it is a boundary case.
3. **The pooled se is 0.284 against the t(3) half-width's implied 0.383.** The
   pooled fit treats 240 runs as independent given session and latency. The
   between-session spread in §3 is direct evidence that they are not, which is
   the reason the pre-registration's own §3.2 uses session as the unit and the
   reason `paper_tables.py` does the same for `[6.1, 28.4]`.

### How thin the pooled disagreement is, stated numerically

| | |
|---|---|
| pooled β class | +0.573194 |
| pooled se | 0.283622 |
| 95% Wald lower bound | **+0.017294** |
| se that would place the lower bound at zero | 0.292446 |
| **required change in se** | **+3.11%** |

**A 3.1% error in one standard error flips the pooled verdict.** That is the
third significant figure, and it is produced by a hand-written IRLS
implementation, so the claim "the pooled fit disagrees" would be worth nothing
without §2a.

**§2a is what makes it reportable.** The class standard error agrees with an
independently computed numerical Hessian to between 5e-08 and 1.5e-06 relative —
roughly four orders of magnitude tighter than the 3.1% that would matter. The
disagreement is a property of the two constructions, not an artefact of the
arithmetic.

**The t(3) verdict is not exposed to this at all.** Its half-width is built from
the between-session standard deviation of four coefficients, not from any model
standard error. A 3% error in a model se would leave it unchanged. That
asymmetry is worth stating: the pre-committed verdict happens also to be the one
that does not turn on the implementation's third digit.

## 6. Foreign load — co-occurrence, stated and stopped there

**The two sessions with confirmed foreign container load are s3 and s4 — the
+23.3 pp and +36.7 pp sessions**, which are also the two largest adjusted
coefficients.

**No causal claim. No adjustment. No exclusion.** Foreign load is measured for
2 of 4 sessions and adjusting on it would make the four non-comparable. The
comparison available is not "load versus no load" but **"load observed versus
load not looked for"** — s1 and s2 have no series at all because sampling did not
exist then, so their load is **unmeasured, not absent**. Two sessions against two
unmeasured ones is consistent with load mattering and equally consistent with
coincidence.

Recorded because it is real, timestamped and hashed; not weighted, because it
cannot bear weight.

## 7. Disclosure — the estimator choice, at its true strength

The estimator was chosen before fitting and **it determined the verdict**. That
raises the standard of disclosure rather than lowering it.

**Weaker than blind, stronger than post-hoc** — Amendment 3's own label, applied
to this decision so the paper grades its own choices on one scale.

**And weaker than Amendment 3's original position**, which must be said plainly.
When the 0.02 threshold was set, sessions 3 and 4 **did not exist in any form**.
When this estimator was chosen, **all four sessions were collected and their
outcome counts were visible to me**: 18/18, 15/18, 17/10 and 23/12. Those counts
give the direction and the approximate magnitude of the result. What the fitted
coefficient added was adjustment and precision — it is not the fact that was
withheld, and claiming "no fitted coefficient was seen" would imply more
protection than exists.

**What protects the choice is not blindness. It is the absence of any free
parameter.** The construction — session as the unit, mean, t(k−1), half-width
t·sd/√k — predates collection: it is `paper_tables.py:1899-1901`, which produced
`[6.1, 28.4]`, and plan §3.2 already registers it for the secondary estimand.
There was no knob to turn toward a preferred answer, and the alternative was
adopting a second inferential standard in the same paper.

**Carry this section into 8.6 verbatim.**

## 8. Not done here

Step 5 — the refit with run position — follows. §3.2 and §3.3 are not touched.
No macro, no paper file and no pre-registration has been modified.
