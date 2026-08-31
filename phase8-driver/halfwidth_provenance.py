#!/usr/bin/env python3
"""Where did the plan's section 3.2 half-width column come from?

The plan tabulates a "3.2 half-width (pp)" for k = 2..6 and argues from it that
k = 4 is the point where the primary's MDE and the robustness check become
commensurable. The MDE column has a full derivation and a sensitivity table. The
half-width column has NONE -- it appears in the table and in that argument, and
nowhere else in the document.

A session-as-unit t-interval half-width is t(k-1) * sd / sqrt(k), so the column
implies some assumed sd. This recovers it by reproducing all five rows, which
identifies the assumption uniquely: five independent matches cannot be a
coincidence of rounding.

Read-only, arithmetic only.
"""

from __future__ import annotations

import math

# The plan's own registered inputs.
P0 = 53 / 150          # baseline AEP-full NO_READBACK applied fraction
N_PER_ARM = 30         # runs per arm per session
T_CRIT = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571}   # keyed by k
PLAN_HALFWIDTH = {2: 110.8, 3: 30.6, 4: 19.6, 5: 15.3, 6: 12.9}

# Observed, from the four v2 sessions.
OBSERVED_D_PP = [0.0, -10.0, 23.333333, 36.666667]


def main() -> int:
    # Hypothesis: the sd used is the BINOMIAL sampling sd of one session's
    # paired difference, with the two arms treated as independent -- i.e. no
    # between-session variance component at all.
    var = 2.0 * P0 * (1.0 - P0) / N_PER_ARM
    sd_binomial = 100.0 * math.sqrt(var)

    print("Hypothesis: sd = binomial sampling sd of ONE session's paired")
    print("difference, two arms independent, no between-session component.\n")
    print(f"  p0 = 53/150            = {P0:.6f}")
    print(f"  Var(p1 - p2) = 2p(1-p)/n = {var:.8f}")
    print(f"  sd                     = {sd_binomial:.4f} pp\n")

    print(f"{'k':>3}{'t(k-1)':>9}{'reproduced':>13}{'plan':>9}{'diff':>9}")
    ok = 0
    for k in sorted(PLAN_HALFWIDTH):
        half = T_CRIT[k] * sd_binomial / math.sqrt(k)
        diff = half - PLAN_HALFWIDTH[k]
        if abs(diff) < 0.1:
            ok += 1
        print(f"{k:>3}{T_CRIT[k]:>9}{half:>13.2f}{PLAN_HALFWIDTH[k]:>9}{diff:>+9.2f}")
    print(f"\n  {ok} of {len(PLAN_HALFWIDTH)} rows reproduced to within 0.1 pp.")

    # What actually happened.
    k = len(OBSERVED_D_PP)
    mean = sum(OBSERVED_D_PP) / k
    sd_obs = math.sqrt(sum((v - mean) ** 2 for v in OBSERVED_D_PP) / (k - 1))
    print(f"\n  observed sd across the four sessions : {sd_obs:.4f} pp")
    print(f"  assumed sd                           : {sd_binomial:.4f} pp")
    print(f"  ratio                                : {sd_obs / sd_binomial:.3f}")
    print(f"  implied over-dispersion (ratio^2)    : "
          f"{(sd_obs / sd_binomial) ** 2:.3f}")
    print("\n  9C measured over-dispersion 5.37 for UNBLOCKED pooling. The")
    print("  blocking the design added moved it from 5.37 toward 1.0 and")
    print("  reached about 3.0 -- it helped, and it did not reach the 1.0 the")
    print("  half-width column assumed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
