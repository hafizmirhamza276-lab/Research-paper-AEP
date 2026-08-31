#!/usr/bin/env python3
"""Why did a per-session fit trip the separation guard?

A halt is only worth reporting if it is a property of the data rather than of the
detector. fit_estimand.py flags separation when ANY coefficient exceeds a
magnitude threshold or ANY standard error exceeds a size threshold -- including
the intercept, which is not a quantity of interest and which absorbs the
covariate's scale. log(latency) is around 6-8 here, so a large covariate slope
forces a large intercept mechanically, with no separation anywhere.

This prints every coefficient so the flag can be attributed to the right term
before anything is concluded from it. Read-only, fits only.

Usage: diagnose_halt.py <run root> [<run root> ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import fit_estimand as F
from logistic import fit

NAMES = ["intercept", "class(AUTH)", "log(latency)"]


def main(argv: list[str]) -> int:
    for arg in argv:
        root = Path(arg)
        rows = F.load(root)
        X, y = F.design(rows, False)
        out = fit(X, y)
        lv = [r["logmv"] for r in rows]
        print(f"{root.name}")
        print(f"  n={out['n']}  iterations={out['iterations']}  "
              f"converged={out['converged']}  FLAGGED={out['separated']}")
        for name, b, se in zip(NAMES, out["beta"], out["se"]):
            mark = ""
            if abs(b) > 30.0:
                mark += "  <-- |beta| > 30"
            if se > 1e3:
                mark += "  <-- se > 1e3"
            print(f"    {name:<14} beta={b:+16.6f}   se={se:16.6f}{mark}")
        print(f"    log(latency) range {min(lv):.4f} .. {max(lv):.4f}   "
              f"mean {sum(lv)/len(lv):.4f}")
        # Does the covariate perfectly order the outcome? That is the only
        # genuine separation route left once class is ruled out by its counts.
        pairs = sorted((r["logmv"], r["applied"]) for r in rows)
        ones = [i for i, (_, a) in enumerate(pairs) if a == 1]
        zeros = [i for i, (_, a) in enumerate(pairs) if a == 0]
        overlap = not (max(zeros, default=-1) < min(ones, default=10**9)
                       or max(ones, default=-1) < min(zeros, default=10**9))
        print(f"    covariate separates outcome perfectly: {'NO' if overlap else 'YES'}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
