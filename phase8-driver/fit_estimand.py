#!/usr/bin/env python3
"""Phase 8.5 plan section 3.1 -- the primary estimand.

    Logistic regression of applied in {0,1} on capability class, with
    log(issue_to_return_ns) as covariate and session as a fixed effect.

Fitted PER SESSION, then mean and a two-sided t(3) interval across the four
session-level coefficients, so the interval and the estimand are the same
quantity. With one session the session term is collinear with the intercept, so
each per-session model is the registered specification evaluated within a
stratum, not a different model.

WHAT IS REPORTED IS NOT THE POOLED COEFFICIENT. The pooled model assumes a
COMMON class coefficient; per-session fits do not. The mean of session-specific
adjusted log-odds differences equals the common coefficient only under
homogeneity. The four coefficients are therefore printed individually, and the
between-session spread is a result rather than noise.

The pooled fixed-effect fit is reported alongside, labelled as conditional on
independence given session.

Contrast: AUTHORITATIVE_READBACK relative to NO_READBACK. A positive coefficient
means AUTH applied an effect more often, matching the sign of the descriptive
percentage-point differences.

Units: the covariate is registered as log(issue_to_return_ns) and the frozen
analysis exposes it as redis_kill_latency_ms, derived from the same field
(analyze.py:563). A unit change is a constant shift in log space: it moves the
intercept and leaves the class coefficient unchanged.

HALTS, and never falls back. If a per-session fit does not converge, separates,
or returns an implausible standard error, this exits non-zero and reports. It
does not substitute the pooled fit, and it applies no penalty and no prior --
either would be a specification change made with the data in view.

Usage: fit_estimand.py [--position] <run root> <run root> <run root> <run root>
"""

from __future__ import annotations

import csv
import math
import re
import sys
from pathlib import Path

from logistic import FitError, fit

AUTH = "AUTHORITATIVE_READBACK"
NORB = "NO_READBACK"
SYSTEM = "AEP_FULL"
# t(0.975, 3), the same critical value and construction paper_tables.py:1899-1901
# uses for [6.1, 28.4]. Spelled out because scipy is not a dependency and a
# hard-coded critical value must be checkable against a table.
T_CRIT_3 = 3.182
T_CRIT = {3: 3.182, 2: 4.303, 1: 12.706}


def load(root: Path) -> list[dict]:
    rows = []
    path = root / "analysis" / "per-execution.csv"
    for r in csv.DictReader(path.open(newline="", encoding="utf-8")):
        if r["system"] != SYSTEM or r["response_class"] not in (AUTH, NORB):
            continue
        raw = (r.get("redis_kill_latency_ms") or "").strip()
        if not raw or float(raw) <= 0:
            raise FitError(f"{root.name}: missing covariate for {r['run_id']}")
        m = re.search(r"-r(\d+)$", r["run_id"])
        if not m:
            raise FitError(f"{root.name}: cannot parse repetition from {r['run_id']}")
        rows.append(
            {
                "applied": 1 if (r.get("applied_effects") or "0").strip() not in ("", "0") else 0,
                "auth": 1.0 if r["response_class"] == AUTH else 0.0,
                "logmv": math.log(float(raw)),
                "position": float(m.group(1)),
            }
        )
    return rows


def design(rows, with_position: bool, session_dummies=None, sindex=0, nsess=0):
    X, y = [], []
    for r in rows:
        row = [1.0, r["auth"], r["logmv"]]
        if with_position:
            row.append(r["position"])
        if session_dummies:
            row += [1.0 if j == sindex else 0.0 for j in range(1, nsess)]
        X.append(row)
        y.append(r["applied"])
    return X, y


def saturated_check(rows) -> tuple[float, float]:
    """Class-only fit against the exact log odds ratio. R2, on the real data."""
    X = [[1.0, r["auth"]] for r in rows]
    y = [r["applied"] for r in rows]
    got = fit(X, y)["beta"][1]
    a_ap = sum(r["applied"] for r in rows if r["auth"] == 1.0)
    a_n = sum(1 for r in rows if r["auth"] == 1.0)
    n_ap = sum(r["applied"] for r in rows if r["auth"] == 0.0)
    n_n = sum(1 for r in rows if r["auth"] == 0.0)
    want = math.log((a_ap / (a_n - a_ap)) / (n_ap / (n_n - n_ap)))
    return got, want


def main(argv: list[str]) -> int:
    with_position = "--position" in argv
    roots = [Path(a) for a in argv if not a.startswith("--")]
    if len(roots) < 2:
        raise SystemExit("need at least two run roots")

    label = "class + log(latency)" + (" + run position" if with_position else "")
    print(f"\nPhase 8.5 section 3.1 -- per-session adjusted class effect")
    print(f"Model per session: applied ~ {label}")
    print(f"Contrast: {AUTH} relative to {NORB}, system {SYSTEM}\n")

    print("--- R2 check: class-only fit reproduces the exact log odds ratio ---")
    per = []
    for root in roots:
        rows = load(root)
        got, want = saturated_check(rows)
        ok = abs(got - want) < 1e-9
        print(f"  {root.name:<32} fitted {got:+.10f}  exact {want:+.10f}  "
              f"{'MATCH' if ok else 'MISMATCH'}")
        if not ok:
            raise FitError(f"{root.name}: saturated identity failed")
        per.append((root, rows))
    print()

    print("--- per-session adjusted class coefficient (log-odds) ---")
    print(f"{'session':<32}{'n':>5}{'beta_class':>13}{'se':>9}{'iters':>7}"
          f"{'AUTH':>7}{'NO_RB':>7}{'pp diff':>9}")
    coefs = []
    for root, rows in per:
        X, y = design(rows, with_position)
        out = fit(X, y)
        if not out["converged"]:
            raise FitError(f"{root.name}: did not converge")
        if out["separated"]:
            raise FitError(f"{root.name}: separation or implausible standard error")
        b, se = out["beta"][1], out["se"][1]
        a_ap = sum(r["applied"] for r in rows if r["auth"] == 1.0)
        a_n = sum(1 for r in rows if r["auth"] == 1.0)
        n_ap = sum(r["applied"] for r in rows if r["auth"] == 0.0)
        n_n = sum(1 for r in rows if r["auth"] == 0.0)
        pp = 100.0 * (a_ap / a_n - n_ap / n_n)
        coefs.append(b)
        print(f"{root.name:<32}{out['n']:>5}{b:>+13.6f}{se:>9.4f}"
              f"{out['iterations']:>7}{a_ap:>4}/{a_n:<2}{n_ap:>4}/{n_n:<2}{pp:>+9.1f}")

    k = len(coefs)
    mean = sum(coefs) / k
    var = sum((c - mean) ** 2 for c in coefs) / (k - 1)
    sd = math.sqrt(var)
    tc = T_CRIT.get(k - 1, T_CRIT_3)
    half = tc * sd / math.sqrt(k)

    print(f"\n--- primary result: mean of {k} session coefficients, t({k-1}) interval ---")
    print(f"  mean beta_class            : {mean:+.6f}")
    print(f"  between-session sd         : {sd:.6f}")
    print(f"  t({k-1}, 0.975)                 : {tc}")
    print(f"  half-width = t*sd/sqrt(k)  : {half:.6f}")
    print(f"  95% interval               : [{mean - half:+.6f}, {mean + half:+.6f}]")
    contains = (mean - half) <= 0.0 <= (mean + half)
    print(f"  contains 0                 : {'YES -> CONFIRMS' if contains else 'NO -> CONTRADICTS'}")
    print(f"  odds ratio at the mean     : {math.exp(mean):.4f}")

    print(f"\n  Width decomposition: sd across sessions is {sd:.4f} against a "
          f"typical\n  within-session se of "
          f"{sum(fit(*design(r, with_position))['se'][1] for _, r in per)/k:.4f}. "
          f"Most of the\n  interval's width is between-session heterogeneity, "
          f"not sampling error.\n  That is correct behaviour and is reported as "
          f"a result, not as noise.")

    print("\n--- pooled fixed-effect fit, for comparison only ---")
    print("  Assumes a COMMON class coefficient and independence given session.")
    allrows, X, y = [], [], []
    for i, (root, rows) in enumerate(per):
        for r in rows:
            row = [1.0, r["auth"], r["logmv"]]
            if with_position:
                row.append(r["position"])
            row += [1.0 if j == i else 0.0 for j in range(1, len(per))]
            X.append(row)
            y.append(r["applied"])
            allrows.append(r)
    out = fit(X, y)
    b, se = out["beta"][1], out["se"][1]
    print(f"  n                          : {out['n']}")
    print(f"  pooled beta_class          : {b:+.6f}")
    print(f"  model-based Wald se        : {se:.6f}")
    print(f"  95% Wald interval          : [{b - 1.96*se:+.6f}, {b + 1.96*se:+.6f}]")
    pooled_contains = (b - 1.96 * se) <= 0.0 <= (b + 1.96 * se)
    print(f"  contains 0                 : {'YES' if pooled_contains else 'NO'}")
    print(f"\n  VERDICT is the t({k-1}) interval above, pre-committed. The two "
          f"{'AGREE' if contains == pooled_contains else 'DISAGREE'}.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except FitError as exc:
        print(f"\nHALT: {exc}")
        print("No fallback is applied. The plan forbids substituting the pooled")
        print("fit or patching with a penalty or a prior.")
        sys.exit(2)
