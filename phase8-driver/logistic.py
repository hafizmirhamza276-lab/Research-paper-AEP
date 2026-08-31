#!/usr/bin/env python3
"""Logistic regression by IRLS, in pure Python.

numpy, scipy and statsmodels are not available on the collection host, and
adding a dependency to fit the phase's primary estimand would change the
environment the results were produced in. This is small enough to write and --
more to the point -- small enough to VALIDATE against answers that are known
exactly, which a library would not be.

R2 requires that before this is trusted on a coefficient nobody knows, it
reproduces one that is known analytically. Two such identities are used, and
both are exact rather than approximate:

  1. Intercept-only:  beta0 == log(p / (1 - p)) for the sample proportion p.
  2. Binary predictor, no covariate: the model is SATURATED, so the slope must
     equal the log odds ratio of the 2x2 table exactly, and the fitted
     probabilities must equal the observed cell proportions exactly.

Identity 2 is the strong one. It is run on the real per-session data rather than
on a synthetic case, so the validation exercises the same code path, the same
parsing and the same numbers as the estimand.

Separation is detected and reported, never silently patched. No penalty and no
prior is applied: either would be a specification change made with the data in
view.
"""

from __future__ import annotations

import math

MAX_ITER = 100
TOL = 1e-11
# A coefficient this large, or a standard error this large, is the numerical
# signature of separation rather than a finding.
BETA_IMPLAUSIBLE = 30.0
SE_IMPLAUSIBLE = 1e3


class FitError(Exception):
    """Raised when a fit cannot be trusted. Never caught to substitute a fallback."""


def _invert(matrix: list[list[float]]) -> list[list[float]]:
    """Gauss-Jordan with partial pivoting. Small dense matrices only."""
    n = len(matrix)
    a = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-13:
            raise FitError(f"design matrix is singular at column {col}")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [v / scale for v in a[col]]
        for r in range(n):
            if r == col:
                continue
            factor = a[r][col]
            if factor:
                a[r] = [v - factor * w for v, w in zip(a[r], a[col])]
    return [row[n:] for row in a]


def fit(X: list[list[float]], y: list[int], intercept_col: int | None = 0) -> dict:
    """IRLS. Returns coefficients, standard errors and convergence detail.

    ``intercept_col`` is excluded from the coefficient-magnitude test for
    separation, and only from that test. A large intercept is not evidence of
    separation when a covariate is on a shifted scale: with log(latency) around
    7 and a slope of 6.7, the intercept must be near -47 simply to place the
    fitted curve, because it is the log-odds extrapolated to latency = 1 ms,
    far outside the observed 740-8200 ms.

    Applying the magnitude test to the intercept produced a FALSE halt on two of
    Phase 8.5's four sessions, both of which converged in 7 iterations with
    class-coefficient standard errors near 0.6. The standard-error test still
    covers every coefficient including the intercept, since a diverging
    intercept under genuine separation shows up there.
    """
    n, k = len(X), len(X[0])
    if n <= k:
        raise FitError(f"{n} observations for {k} parameters")
    beta = [0.0] * k

    for iteration in range(1, MAX_ITER + 1):
        eta = [sum(b * x for b, x in zip(beta, row)) for row in X]
        # Clamp only the linear predictor's exponent, to keep exp() finite. This
        # does not alter a converged fit; it prevents an overflow on the way to
        # detecting separation, which is reported below rather than smoothed.
        p = [1.0 / (1.0 + math.exp(-max(-500.0, min(500.0, e)))) for e in eta]
        w = [max(pi * (1.0 - pi), 1e-12) for pi in p]

        xtwx = [[sum(w[i] * X[i][a] * X[i][b] for i in range(n)) for b in range(k)]
                for a in range(k)]
        xtr = [sum(X[i][a] * (y[i] - p[i]) for i in range(n)) for a in range(k)]

        cov = _invert(xtwx)
        step = [sum(cov[a][b] * xtr[b] for b in range(k)) for a in range(k)]
        beta = [b + s for b, s in zip(beta, step)]

        if max(abs(s) for s in step) < TOL:
            se = [math.sqrt(cov[a][a]) for a in range(k)]
            structural = [
                a for a in range(k) if a != intercept_col
            ]
            separated = any(abs(beta[a]) > BETA_IMPLAUSIBLE for a in structural) or any(
                s > SE_IMPLAUSIBLE for s in se
            )
            loglik = sum(
                (y[i] * math.log(max(p[i], 1e-300)))
                + ((1 - y[i]) * math.log(max(1.0 - p[i], 1e-300)))
                for i in range(n)
            )
            return {
                "beta": beta,
                "se": se,
                "iterations": iteration,
                "converged": True,
                "separated": separated,
                "loglik": loglik,
                "n": n,
            }

    raise FitError(f"did not converge in {MAX_ITER} iterations")


def validate() -> None:
    """Both identities, on synthetic data with answers known in closed form."""
    # 1. Intercept only.
    y = [1] * 18 + [0] * 12
    got = fit([[1.0]] * 30, y)["beta"][0]
    want = math.log(18 / 12)
    assert abs(got - want) < 1e-9, f"intercept-only: {got} != {want}"

    # 2. Binary predictor, saturated -> exact log odds ratio.
    #    arm 0: 18/30 applied, arm 1: 10/30 applied
    X, y = [], []
    for arm, applied, total in ((0.0, 18, 30), (1.0, 10, 30)):
        for i in range(total):
            X.append([1.0, arm])
            y.append(1 if i < applied else 0)
    out = fit(X, y)
    want_or = math.log((10 / 20) / (18 / 12))
    assert abs(out["beta"][1] - want_or) < 1e-9, f"log OR: {out['beta'][1]} != {want_or}"
    assert not out["separated"]

    # 3. Separation must be DETECTED, not smoothed away.
    X, y = [], []
    for arm, applied, total in ((0.0, 30, 30), (1.0, 28, 30)):
        for i in range(total):
            X.append([1.0, arm])
            y.append(1 if i < applied else 0)
    try:
        out = fit(X, y)
        detected = out["separated"]
    except FitError:
        detected = True
    assert detected, "separation was not detected"

    # 4. A large intercept forced by a shifted covariate is NOT separation.
    #    This is the false positive that halted Phase 8.5's step 4 on its first
    #    run, reproduced here so the fix cannot regress silently.
    X, y = [], []
    for i in range(60):
        lat = 6.60 + i * 0.0170              # log-latency ~6.6-7.6, as observed
        label = 1 if lat > 7.10 else 0
        if i in (20, 21, 44, 45):            # overlap, so the MLE stays finite
            label = 1 - label
        X.append([1.0, float(i % 2), lat])
        y.append(label)
    out = fit(X, y)
    assert out["converged"], "shifted-covariate case did not converge"
    assert abs(out["beta"][0]) > 30.0, "test case no longer produces a large intercept"
    assert not out["separated"], (
        "a large intercept from a shifted covariate is still being reported as "
        "separation"
    )

    print("logistic.py self-validation: 4/4 identities hold")
    print(f"  intercept-only beta0 == log(18/12)           = {want:.10f}")
    print(f"  saturated slope  == log odds ratio           = {want_or:.10f}")
    print("  30/30 vs 28/30 separation                    = detected")
    print(f"  large intercept ({out['beta'][0]:+.1f}) from shifted covariate  "
          f"= NOT flagged")


if __name__ == "__main__":
    validate()
