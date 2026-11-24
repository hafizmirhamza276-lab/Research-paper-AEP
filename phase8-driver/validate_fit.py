#!/usr/bin/env python3
"""Two checks the earlier validation did not reach.

1. POSITIVE CONTROL for the separation guard.

   The guard was NARROWED after it fired falsely on the intercept. A guard that
   fires falsely gets caught immediately; a guard that has stopped firing never
   does. So it is exercised here on real data with real separation:
   B3_INTENT_NO_BARRIER's AUTHORITATIVE_READBACK arm is 30/30 applied in all four
   sessions, which is complete separation on the class term.

   The fixed guard MUST halt on it. If it does not, the fix blinded the guard and
   that is a defect to report before any further fitting.

2. NUMERICAL VALIDATION of the ADJUSTED fit.

   Reproducing the exact log odds ratio validates IRLS on a SATURATED model,
   where a closed form exists. The primary estimand is the adjusted fit with a
   continuous covariate, and no closed form exists for it. Two independent
   checks:

     (a) Score equations. At a maximum likelihood solution X'(y - p) = 0 for
         every column. The largest absolute residual is reported.
     (b) Standard errors against a numerically differentiated Hessian. The
         IRLS covariance is (X'WX)^-1, computed analytically; a central-
         difference second derivative of the log-likelihood is an independent
         route to the same quantity.

   This matters concretely. The pooled dual result's interval is
   [+0.0173, +1.1291] from se = 0.283622. For the lower bound to reach zero the
   se would need to be beta/1.96 = 0.292446, a 3.1% difference. "The pooled fit
   disagrees" therefore rests on the third significant figure of a standard error
   from a hand-written implementation. The t(3) verdict does not rest on it,
   because that interval is built from the between-session sd of four
   coefficients rather than from any model standard error.

Read-only. Fits only; writes nothing.

Usage: validate_fit.py <run root> <run root> <run root> <run root>
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import fit_estimand as F
from logistic import FitError, _invert, fit

AUTH = "AUTHORITATIVE_READBACK"
NORB = "NO_READBACK"


def load_system(root: Path, system: str) -> list[dict]:
    saved = F.SYSTEM
    F.SYSTEM = system
    try:
        return F.load(root)
    finally:
        F.SYSTEM = saved


def loglik(X, y, beta) -> float:
    total = 0.0
    for row, yi in zip(X, y):
        eta = max(-500.0, min(500.0, sum(b * x for b, x in zip(beta, row))))
        p = 1.0 / (1.0 + math.exp(-eta))
        total += yi * math.log(max(p, 1e-300)) + (1 - yi) * math.log(max(1.0 - p, 1e-300))
    return total


def numeric_se(X, y, beta, h: float = 1e-4) -> list[float]:
    """Central-difference Hessian of the log-likelihood, then invert its negative."""
    k = len(beta)
    H = [[0.0] * k for _ in range(k)]
    for a in range(k):
        for b in range(a, k):
            bp = list(beta)
            if a == b:
                bp[a] = beta[a] + h
                f_plus = loglik(X, y, bp)
                bp[a] = beta[a] - h
                f_minus = loglik(X, y, bp)
                H[a][a] = (f_plus - 2 * loglik(X, y, beta) + f_minus) / (h * h)
            else:
                def at(da, db):
                    q = list(beta)
                    q[a] += da
                    q[b] += db
                    return loglik(X, y, q)
                H[a][b] = H[b][a] = (
                    at(h, h) - at(h, -h) - at(-h, h) + at(-h, -h)
                ) / (4 * h * h)
    neg = [[-v for v in row] for row in H]
    cov = _invert(neg)
    return [math.sqrt(cov[a][a]) for a in range(k)]


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv]
    failures = 0

    print("=" * 74)
    print("1. POSITIVE CONTROL -- the guard must halt on B3's 30/30 AUTH arm")
    print("=" * 74)
    for root in roots:
        rows = load_system(root, "B3_INTENT_NO_BARRIER")
        a_ap = sum(r["applied"] for r in rows if r["auth"] == 1.0)
        a_n = sum(1 for r in rows if r["auth"] == 1.0)
        n_ap = sum(r["applied"] for r in rows if r["auth"] == 0.0)
        n_n = sum(1 for r in rows if r["auth"] == 0.0)
        X, y = F.design(rows, False)
        try:
            out = fit(X, y)
            halted = out["separated"]
            detail = (f"beta_class={out['beta'][1]:+.3f} se={out['se'][1]:.3g} "
                      f"iters={out['iterations']}")
        except FitError as exc:
            halted = True
            detail = f"FitError: {exc}"
        status = "HALTS (guard alive)" if halted else "DID NOT HALT -- GUARD BLINDED"
        if not halted:
            failures += 1
        print(f"  {root.name:<32} AUTH {a_ap}/{a_n}  NO_RB {n_ap}/{n_n}  -> {status}")
        print(f"      {detail}")

    print()
    print("=" * 74)
    print("2. ADJUSTED FIT -- score equations and a numerically differentiated se")
    print("=" * 74)
    names = ["intercept", "class", "log(latency)"]
    for root in roots:
        rows = load_system(root, "AEP_FULL")
        X, y = F.design(rows, False)
        out = fit(X, y)
        beta = out["beta"]

        p = []
        for row in X:
            eta = max(-500.0, min(500.0, sum(b * x for b, x in zip(beta, row))))
            p.append(1.0 / (1.0 + math.exp(-eta)))
        score = [sum(X[i][a] * (y[i] - p[i]) for i in range(len(y))) for a in range(len(beta))]
        worst = max(abs(s) for s in score)

        nse = numeric_se(X, y, beta)
        print(f"\n  {root.name}")
        print(f"    largest |score| residual X'(y-p) : {worst:.3e}")
        print(f"    {'term':<14}{'IRLS se':>12}{'numeric se':>13}{'rel diff':>11}")
        for name, s_irls, s_num in zip(names, out["se"], nse):
            rel = abs(s_irls - s_num) / s_num if s_num else float("inf")
            print(f"    {name:<14}{s_irls:>12.6f}{s_num:>13.6f}{rel:>10.2e}")
        if worst > 1e-6:
            print("    !! score residual is large; the solution is not at a maximum")
            failures += 1

    print()
    print("=" * 74)
    print("3. SENSITIVITY -- how thin is the pooled disagreement?")
    print("=" * 74)
    X, y = [], []
    for i, root in enumerate(roots):
        for r in load_system(root, "AEP_FULL"):
            X.append([1.0, r["auth"], r["logmv"]]
                     + [1.0 if j == i else 0.0 for j in range(1, len(roots))])
            y.append(r["applied"])
    out = fit(X, y)
    beta, se = out["beta"][1], out["se"][1]
    lower = beta - 1.96 * se
    se_flip = beta / 1.96
    print(f"  pooled beta_class            : {beta:+.6f}")
    print(f"  pooled se                    : {se:.6f}")
    print(f"  95% Wald lower bound         : {lower:+.6f}")
    print(f"  se that would put it at zero : {se_flip:.6f}")
    print(f"  required change in se        : {100*(se_flip-se)/se:+.2f}%")
    print("\n  So the pooled verdict turns on the third significant figure of a")
    print("  standard error. The t(3) verdict does NOT: it is built from the")
    print("  between-session sd of four coefficients, not from a model se.")

    print()
    if failures:
        print(f"VALIDATION FAILED: {failures} problem(s)")
        return 2
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
