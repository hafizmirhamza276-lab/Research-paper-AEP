#!/usr/bin/env python3
"""Amendment 3 §2 step 1, computed per session.

    For each session, compute the within-session between-arm difference in
    median log(issue_to_return_ns) for AEP-full, and the ratio of between-arm
    variance to within-arm variance of the covariate.

Run here on sessions 1 and 2 BEFORE sessions 3 and 4 finish, so the record
shows exactly what was knowable when amendment 3's 0.02 threshold was fixed.
This is not the 8.5 adjudication: amendment 3 requires the classification to be
made over the k = 4 set, and the verdict column below is printed per session for
provenance only.

UNITS. The covariate is `log(issue_to_return_ns)`; the frozen analysis exposes
it as `redis_kill_latency_ms`, derived from the same field
(`analyze.py:563` reads `issue_to_return_ns`). A change of unit is a constant
shift in log space, so a DIFFERENCE of log medians and a RATIO of variances are
both invariant to it. The numbers below are therefore exactly the registered
statistic despite being computed from the ms column.

Usage: covariate_check.py <run root> [<run root> ...]
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
from statistics import median, pvariance

THRESHOLD = 0.02
AUTH = "AUTHORITATIVE_READBACK"
NORB = "NO_READBACK"


def session_stat(root: Path) -> dict:
    path = root / "analysis" / "per-execution.csv"
    arms: dict[str, list[float]] = {AUTH: [], NORB: []}

    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("system") != "AEP_FULL":
                continue
            cls = row.get("response_class")
            if cls not in arms:
                continue
            raw = (row.get("redis_kill_latency_ms") or "").strip()
            if not raw:
                continue
            try:
                v = float(raw)
            except ValueError:
                continue
            if v > 0:
                arms[cls].append(math.log(v))

    a, n = arms[AUTH], arms[NORB]
    if not a or not n:
        raise SystemExit(f"{root.name}: no covariate values")

    delta = median(a) - median(n)

    # Between-arm variance against within-arm variance, both on the log scale.
    # Between: the spread of the two arm means about the grand mean, weighted by
    # arm size. Within: the pooled variance inside the arms.
    grand = (sum(a) + sum(n)) / (len(a) + len(n))
    mean_a, mean_n = sum(a) / len(a), sum(n) / len(n)
    between = (len(a) * (mean_a - grand) ** 2 + len(n) * (mean_n - grand) ** 2) / (
        len(a) + len(n)
    )
    within = (len(a) * pvariance(a) + len(n) * pvariance(n)) / (len(a) + len(n))
    ratio = between / within if within else float("inf")

    return {
        "session": root.name,
        "n_auth": len(a),
        "n_no_readback": len(n),
        "median_log_auth": round(median(a), 6),
        "median_log_no_readback": round(median(n), 6),
        "delta_median_log": round(delta, 6),
        "abs_delta_median_log": round(abs(delta), 6),
        "below_registered_threshold": abs(delta) < THRESHOLD,
        "between_arm_variance": round(between, 8),
        "within_arm_variance": round(within, 8),
        "variance_ratio": round(ratio, 8),
    }


def main(argv: list[str]) -> int:
    stats = [session_stat(Path(p).resolve()) for p in argv]

    print("\nAmendment 3 §2 step 1 — the covariate's between-arm variation")
    print("(AEP-full only; log scale; threshold |Δ median| < 0.02)\n")
    print(
        f"{'session':<34}{'n':>7}{'Δ median log':>15}"
        f"{'|Δ| < 0.02':>13}{'var ratio':>13}"
    )
    for s in stats:
        print(
            f"{s['session']:<34}{s['n_auth']:>3}/{s['n_no_readback']:<3}"
            f"{s['delta_median_log']:>15.6f}"
            f"{('YES' if s['below_registered_threshold'] else 'no'):>13}"
            f"{s['variance_ratio']:>13.6f}"
        )

    below = sum(1 for s in stats if s["below_registered_threshold"])
    print(
        f"\n{below} of {len(stats)} session(s) below the threshold. "
        "The registered rule is a MAJORITY of the k = 4 sessions, so this is "
        "provenance, not the adjudication -- that happens at 8.5 over all four."
    )
    print(
        "\nFor scale: amendment 3 set 0.02 as approximately 2%, against the ~20% "
        "arm-correlated latency imbalance that amendment 1's interleaving removed "
        "by design. A Δ of 0.02 in log space is a ratio of about "
        f"{math.exp(0.02):.4f}, i.e. ~2.0% between the arms."
    )
    return 0


if __name__ == "__main__":
    out = main(sys.argv[1:])
    sys.exit(out)
