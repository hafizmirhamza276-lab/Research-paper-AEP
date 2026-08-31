#!/usr/bin/env python3
"""Phase 8.5 plan sections 3.2 and 3.3.

3.2 SECONDARY -- the unadjusted paired difference.

    d_i = applied_AUTH(i) - applied_NO_READBACK(i) for AEP-full, session as the
    unit, mean with a two-sided 95% t-interval on k-1 df. A robustness check on
    3.1. The naive Wilson interval on pooled runs is FORBIDDEN -- 9C section 3
    shows it four times too narrow.

    Same construction as paper_tables.py:1899-1901 and as the primary's
    interval, so the paper carries one inferential standard rather than two.

3.3 INTEGRITY CHECK (not an estimand) -- the fail-closed invariant.

    For every AEP-full execution with an applied effect, the run must show
    traversal of AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT for that
    execution. Predicted: zero exceptions. ANY exception HALTS the phase.

    The column is durability_ack_observed. That it is the right column is
    checked rather than assumed: injector.py:373-381 emits that event only when
    the traversed checkpoint's name equals AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_
    PREFLIGHT, so the field is exactly the traversal record and nothing else.

    One-directional by construction: ack => applied is NOT claimed, because the
    kill can land after the acknowledgement and before transmission, which is
    the window after_barrier_before_dispatch names.

Neither section touches B3, so B3's 30/30 separation cannot bite here. Both are
AEP-full only, as registered.

Read-only. Usage: fit_secondary.py <run root> ...
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

AUTH = "AUTHORITATIVE_READBACK"
NORB = "NO_READBACK"
T_CRIT = {3: 3.182, 2: 4.303, 1: 12.706}


def rows_of(root: Path) -> list[dict]:
    path = root / "analysis" / "per-execution.csv"
    return list(csv.DictReader(path.open(newline="", encoding="utf-8")))


def truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes")


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv]

    print("\n" + "=" * 72)
    print("3.2 SECONDARY -- unadjusted paired difference, session as the unit")
    print("=" * 72)
    print(f"{'session':<32}{'AUTH':>7}{'NO_RB':>7}{'d (count)':>11}{'d (pp)':>10}")
    diffs, pps = [], []
    for root in roots:
        rows = [r for r in rows_of(root) if r["system"] == "AEP_FULL"]
        a = [r for r in rows if r["response_class"] == AUTH]
        n = [r for r in rows if r["response_class"] == NORB]
        a_ap = sum(1 for r in a if truthy(r["applied_effects"]))
        n_ap = sum(1 for r in n if truthy(r["applied_effects"]))
        d = a_ap - n_ap
        pp = 100.0 * (a_ap / len(a) - n_ap / len(n))
        diffs.append(d)
        pps.append(pp)
        print(f"{root.name:<32}{a_ap:>4}/{len(a):<2}{n_ap:>4}/{len(n):<2}"
              f"{d:>+11}{pp:>+10.1f}")

    for label, vals, unit in (("count", diffs, ""), ("percentage points", pps, " pp")):
        k = len(vals)
        mean = sum(vals) / k
        sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (k - 1))
        tc = T_CRIT[k - 1]
        half = tc * sd / math.sqrt(k)
        print(f"\n  --- in {label} ---")
        print(f"    values                : {[round(v, 1) for v in vals]}")
        print(f"    mean                  : {mean:+.4f}{unit}")
        print(f"    sd across sessions    : {sd:.4f}")
        print(f"    t({k-1}, 0.975)           : {tc}")
        print(f"    half-width t*sd/sqrt(k): {half:.4f}")
        print(f"    95% interval          : [{mean-half:+.4f}, {mean+half:+.4f}]{unit}")
        print(f"    contains 0            : "
              f"{'YES' if (mean-half) <= 0 <= (mean+half) else 'NO'}")

    print("\n  The naive Wilson interval on pooled runs is FORBIDDEN by the plan")
    print("  (9C section 3: four times too narrow) and is not computed here.")

    print("\n" + "=" * 72)
    print("3.3 INTEGRITY CHECK -- applied implies durability ack observed")
    print("=" * 72)
    print(f"{'session':<32}{'applied':>9}{'of which ack':>14}{'EXCEPTIONS':>12}")
    total_applied = total_exc = 0
    exceptions: list[tuple[str, str]] = []
    for root in roots:
        rows = [r for r in rows_of(root) if r["system"] == "AEP_FULL"]
        applied = [r for r in rows if truthy(r["applied_effects"])]
        acked = [r for r in applied if truthy(r["durability_ack_observed"])]
        bad = [r for r in applied if not truthy(r["durability_ack_observed"])]
        total_applied += len(applied)
        total_exc += len(bad)
        exceptions += [(root.name, r["run_id"]) for r in bad]
        print(f"{root.name:<32}{len(applied):>9}{len(acked):>14}{len(bad):>12}")
    print(f"{'TOTAL':<32}{total_applied:>9}{total_applied-total_exc:>14}{total_exc:>12}")

    if exceptions:
        print("\n  HALT: the fail-closed invariant is violated.")
        for name, run in exceptions[:20]:
            print(f"    {name}  {run}")
        print("\n  This means a dispatch without authorization, which")
        print("  DispatchAuthorizationError is supposed to make impossible.")
        print("  Reported and minimised, not re-run away.")
        return 2

    print("\n  Zero exceptions, as predicted.")
    print("  CONFIRMATORY OF CODE-ENFORCED BEHAVIOUR ALONG A SINGLE CODE PATH.")
    print("  Not a discovered property: _checkpoint is awaited on the protocol")
    print("  path, so dispatched implies traversed holds by construction, and")
    print("  DispatchAuthorizationError already enforces it in code. This mostly")
    print("  exercises the observer's own fidelity, and any report using it has")
    print("  to say so (injector.py:351-356).")
    print("  One-directional: ack => applied is NOT claimed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
