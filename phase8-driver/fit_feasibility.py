#!/usr/bin/env python3
"""Can the registered model be fitted PER SESSION, or would it separate?

Plan change 1 fits plan section 3.1's model once per session and then takes the
mean and a t(3) interval across the four session-level coefficients, so that the
interval and the estimand are the same quantity. That only works if each session
fits. A per-session logistic regression fails when an arm's outcome is constant
-- complete separation -- and the coefficient runs to infinity.

This checks feasibility BEFORE any fitting, from the frozen data, and it does not
fit anything. It reports each session's per-arm n, applied count, and whether
either arm is degenerate.

The applied column is `applied_effects`, and the covariate is
`redis_kill_latency_ms` (analyze.py:563 derives it from issue_to_return_ns; a
unit change is a constant shift in log space, so a difference of log medians and
a ratio of variances are both invariant to it).

Read-only. No model is fitted.

Usage: fit_feasibility.py <run root> [<run root> ...]
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

AUTH = "AUTHORITATIVE_READBACK"
NORB = "NO_READBACK"


def session(root: Path) -> dict:
    rows = list(
        csv.DictReader(
            (root / "analysis" / "per-execution.csv").open(
                newline="", encoding="utf-8"
            )
        )
    )
    out = {"session": root.name, "rows": len(rows), "by": {}}
    for system in sorted({r["system"] for r in rows}):
        for cls in (AUTH, NORB):
            sel = [r for r in rows if r["system"] == system and r["response_class"] == cls]
            applied = sum(1 for r in sel if (r.get("applied_effects") or "0").strip() not in ("", "0"))
            cov = [
                r for r in sel
                if (r.get("redis_kill_latency_ms") or "").strip()
                and float(r["redis_kill_latency_ms"]) > 0
            ]
            out["by"][(system, cls)] = {
                "n": len(sel),
                "applied": applied,
                "covariate_present": len(cov),
            }
    return out


def main(argv: list[str]) -> int:
    stats = [session(Path(p)) for p in argv]

    for system in ("AEP_FULL", "B3_INTENT_NO_BARRIER"):
        print(f"\n=== {system} ===")
        print(f"{'session':<32}{'AUTH n':>8}{'applied':>9}{'NO_RB n':>9}"
              f"{'applied':>9}{'separation?':>14}")
        for s in stats:
            a = s["by"].get((system, AUTH), {"n": 0, "applied": 0})
            n = s["by"].get((system, NORB), {"n": 0, "applied": 0})
            deg = []
            for label, d in (("AUTH", a), ("NO_RB", n)):
                if d["n"] and d["applied"] in (0, d["n"]):
                    deg.append(f"{label}={d['applied']}/{d['n']}")
            flag = ", ".join(deg) if deg else "no"
            print(f"{s['session']:<32}{a['n']:>8}{a['applied']:>9}"
                  f"{n['n']:>9}{n['applied']:>9}{flag:>14}")

    print("\n=== covariate completeness (AEP_FULL, both arms) ===")
    for s in stats:
        a = s["by"][("AEP_FULL", AUTH)]
        n = s["by"][("AEP_FULL", NORB)]
        print(f"  {s['session']:<32} AUTH {a['covariate_present']}/{a['n']}"
              f"   NO_RB {n['covariate_present']}/{n['n']}")

    print("\nSeparation is the halt condition: a per-session fit whose arm is "
          "0/n or n/n\nhas no finite coefficient. B3's arms are expected to be "
          "degenerate and are NOT\nin the primary estimand; only AEP_FULL "
          "matters for feasibility.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
