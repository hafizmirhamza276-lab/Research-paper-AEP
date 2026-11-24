# Phase 8 · pre-registration, AMENDMENT 3 — the covariate may be degenerate

**Committed and pushed before sessions 2–4 exist.** Amends `16abc99` as further
amended by `5b601d0` and `f29f3ae`. Everything not amended here stands.

Two items. The first is a finding to be carried into the manuscript; the second
is an **analysis rule that is worth nothing unless it is registered now**,
because it decides how to read a result that has not been collected yet.

---

## 1. The drift reverses sign between sessions — recorded as a finding

Measured, two sessions, same host, same day, same configuration:

| session | design | Spearman(run position, kill latency) | Theil–Sen slope |
|---|---|---|---|
| `b2-paired-s1` (superseded) | cell-major | **+0.703** | +9.06 ms/run |
| `b2-paired-v2-s1` | interleaved | **−0.478** | −1.81 ms/run |

**The host's timing behaviour changes direction, not merely level.** This is a
result about the instrument and is to be reported in 8.6 as its own finding, and
carried into `paper/sections/08-threats.tex`. Three places it bears on:

- **The ext4/drvfs reading.** A between-stratum latency difference measured on
  single sessions (ext4 858.9 ms against drvfs 1000.8 ms) sits inside a quantity
  whose *within*-session trend can point either way. F.2a's narrowing stands,
  but "one host" is a weaker constant than it looked.
- **The 859–1216 ms envelope** used by the §7 stop conditions. It was derived
  from five session medians and is a level envelope; it says nothing about
  trend, and a session can sit inside it while drifting steeply in either
  direction. The envelope is retained unchanged for this phase — changing a stop
  condition mid-collection is not on offer — but 8.6 must record that it is a
  weaker check than it appears.
- **What "one host" limits.** The paper's threats section treats the single host
  as fixing a distribution. It does not fix even the sign of the within-session
  trend. That is a sharper and more falsifiable statement of the limitation than
  the one currently written.

**It is also the strongest argument for interleaving over counterbalancing**, and
8.6 should say so: any counterbalancing scheme needs the sign of the drift known
in advance, and it is not knowable in advance because it is not stable.

## 2. The covariate may be degenerate — registered before the data

**The risk.** The primary is a logistic fit of applied on capability class with
`log(issue_to_return_ns)` as covariate and session as a fixed effect. That
covariate exists to adjust for the arm-correlated latency imbalance. Amendment 1
removed that imbalance *by design*. If the remaining sessions also come in with
near-zero class difference and flat drift, **the covariate may carry no
arm-discriminating variation left to adjust on.**

**Why this must be decided now.** A degenerate covariate and a true null produce
the same-looking output — a class coefficient with a confidence interval
containing zero. Reporting that as "class coefficient not distinguishable from
zero" reads as *evidence for the prediction*. If the covariate is degenerate it
is not evidence; it is **non-estimability**, and the two must not be conflated
after the fact.

**Pre-declared procedure, executed BEFORE the model is fitted:**

1. For each session, compute the **within-session between-arm** difference in
   median `log(issue_to_return_ns)` for AEP-full, and the **ratio** of
   between-arm variance to within-arm variance of the covariate.
2. Report those four numbers **before** any coefficient.
3. Then classify:

| condition | verdict | what is reported |
|---|---|---|
| The covariate retains material between-arm variation | **Estimable** | Fit as registered. A class CI containing zero is evidence for the prediction, as originally pre-registered. |
| Between-arm variation is negligible — pre-declared as **\|Δ median log-latency\| < 0.02** (≈ 2%, against the ~20% imbalance amendment 1 removed) in a majority of sessions | **NON-ESTIMABLE, and said so** | The adjusted model is **not** reported as the primary result. The **unadjusted within-session paired difference (§3.2) becomes the answer**, and 8.6 states plainly that the covariate adjustment had nothing to adjust because the design removed the confound it existed for. |

4. **Either way, this is not a failure of the phase.** The second case means
   interleaving worked: the confound the adjustment was built to handle is
   absent, and a clean paired difference is a better answer than an adjusted one.
   What is forbidden is presenting non-estimability as though it were evidence.

**The threshold is fixed here and is not revisable after seeing the fits.**

## 3. The tertiary scheme is closed

Two observations so far — prevented 15 (superseded design) and 10 (amended) —
range 5. The registered verdicts (≥ 10 DISPERSED, 6–9 BOUNDARY reported as
"cannot distinguish", ≤ 5 TIGHT) stand exactly as written in `16abc99` §6.2 and
**are not reconsidered once the remaining numbers are in**, whichever region
they fall in. Recorded here so that the closure is on the record before the data
that would tempt it open.

## 4. Unchanged

k = 4 and the no-extension commitment; the primary, both secondaries and the
integrity check; the balance check and amendment 2's residual prediction and its
per-session Theil–Sen reporting requirement; the missing-vs-false adjudication
and both gates; the corrected wall-time threshold (6426 s); the HALT set;
session 1's status as a superseded design with its outcome numbers published.
