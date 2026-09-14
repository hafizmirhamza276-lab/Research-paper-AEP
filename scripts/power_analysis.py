#!/usr/bin/env python3
"""WS-5: what the frozen results can support, and how many runs would be needed.

Two jobs, and the first is the one that matters.

**Job 1 -- audit what is already published.** Several intervals in the
manuscript come from a cluster bootstrap over *three* runs per arm. This module
measures what those intervals can support, from the frozen per-execution data
the manuscript was built from.

The first hypothesis it was written to test -- that three clusters make the
interval degenerate to the range of the three cluster values -- is **false**,
and is recorded here because the measurement is what settled it. Three runs
against three give a ceiling of 100 distinct differences, not 10: the two arms
resample independently, so the ceiling is the product. The realised count is 42,
and the published endpoints are interior points of the support, not its
extremes. The intervals are coarse; they are not degenerate.

What the measurement found instead is a better explanation and a worse problem.
The B3 arm is a **mixture**: roughly a quarter of its crash-free executions land
near 5 030 ms and the rest near 2 034 ms. A median summarises a mixture badly,
and jumps discontinuously when the mixture proportion crosses one half -- which
is exactly what one of its three runs does, splitting 5/5 and yielding a "median"
of 3 534.8 ms that is the midpoint between two modes rather than any central
value. The width of the published interval is that mixture, correctly
propagated. See section A2 of the report.

**Job 2 -- size the collection that would fix it.** Sample sizes are reported
two ways, and the distinction is load-bearing:

* *Precision-based.* How many runs to get the half-width below a stated target.
  This needs a variance estimate, and the only one available comes from the same
  small sample whose inadequacy is the problem, so it is quoted with its own
  uncertainty and treated as an order-of-magnitude guide.
* *SESOI-based.* How many runs for a stated power against a smallest effect size
  of interest fixed **before** looking at the data, and justified from the
  mechanism rather than from the observed estimate. This is the primary number,
  because "n to detect the effect we happened to observe" is post-hoc power and
  is not a design.

Nothing here changes any result. It reads frozen data and prints an assessment.
``reports/phase-report-ws5-prediction-2026-09-10.md`` is the pre-registration
this module exists to support, and ``tests/test_power_analysis.py`` exercises
every branch against hand-checked answers (docs/25 R2).

Usage:
    python scripts/power_analysis.py                    # full assessment
    python scripts/power_analysis.py --json             # machine-readable
    python scripts/power_analysis.py --section degeneracy
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: The estimator the manuscript uses, reproduced exactly so that the audit is
#: an audit of the published numbers and not of a lookalike.
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260806
CRASH_FREE_REGIME = "p0"

#: Where the frozen timing data lives, per fsync policy.
EXECUTION_PATHS = {
    "everysec": ROOT / "experiments/results/matrix/analysis/per-execution.csv",
    "always": ROOT / "experiments/results/fsync-always/analysis/per-execution.csv",
}

#: docs/26 §4 WS-5 task 5.1.
TARGET_RUNS_PER_ARM = 15


# ---------------------------------------------------------------------------
# Pre-registered decision inputs.  Fixed here, before collection, so that the
# analysis cannot be tuned to the data it will judge (docs/26 §3 rule 5).
# ---------------------------------------------------------------------------

#: Smallest effect size of interest for the barrier's cost, in milliseconds.
#:
#: Justified from the mechanism, not from the observed 1 966.7 ms. Under
#: ``appendfsync everysec`` Redis fsyncs on a 1 000 ms schedule and the protocol
#: waits for two of them, so the quantity being estimated is bounded above by
#: about 2 000 ms. A deployment choosing between AEP-full and B3-mode is
#: choosing between "adds up to two fsync waits" and "adds none"; a difference
#: smaller than a tenth of one fsync interval would not change that choice.
SESOI_BARRIER_MS = 100.0

#: Smallest effect size of interest for the non-barrier protocol cost. The
#: decomposition claim in §VI-RQ3 is that this is *small* next to the barrier,
#: so what must be resolvable is the order of magnitude, not the value.
SESOI_PROTOCOL_MS = 25.0

#: Smallest effect size of interest for a rate difference, in percentage points.
#:
#: This replaces the post-hoc ±5 pp margin (WS-5 task 5.5). 5 pp is retained as
#: the number but is now a *pre-registered* margin with a stated basis: at the
#: measured ambiguity rates, 5 pp of 180 crashed executions per class is nine
#: executions, which is the smallest difference the design can resolve at one
#: run of ten per stratum without splitting a run.
SESOI_RATE_PP = 5.0

#: Two-sided alpha, and the power the design is sized for.
ALPHA = 0.05
TARGET_POWER = 0.80


# ---------------------------------------------------------------------------
# Small statistics helpers.  Written out rather than pulled from scipy because
# the repository's locked environment does not carry it, and because each of
# these is three lines whose behaviour a reviewer can check by eye.
# ---------------------------------------------------------------------------

#: Two-sided t critical values at alpha=0.05 by degrees of freedom. Table
#: rather than an incomplete-beta inversion: the values are checked in
#: tests/test_power_analysis.py against published quantiles.
_T_CRIT_95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
    15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056,
    27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042, 40: 2.021, 50: 2.009,
    60: 2.000, 80: 1.990, 100: 1.984,
}


def t_critical(df: int) -> float:
    """Two-sided 95% t critical value, conservative between table entries."""
    if df < 1:
        raise ValueError("degrees of freedom must be at least 1")
    if df in _T_CRIT_95:
        return _T_CRIT_95[df]
    smaller = max(k for k in _T_CRIT_95 if k < df)
    larger = [k for k in _T_CRIT_95 if k > df]
    if not larger:
        return 1.960
    # Interpolating downward would understate the critical value and so
    # understate the required n. Take the smaller df's (larger) value.
    return _T_CRIT_95[smaller]


def distinct_multisets(n: int) -> int:
    """Number of distinct resample multisets of size n drawn from n clusters.

    C(2n-1, n). With n=3 it is 10, and asking for 10 000 resamples does not
    create information that 3 clusters do not contain.
    """
    if n < 1:
        raise ValueError("cluster count must be at least 1")
    return math.comb(2 * n - 1, n)


def distinct_multisets_for_difference(n_treatment: int, n_control: int) -> int:
    """Ceiling on distinct values of a *difference* of two cluster bootstraps.

    The two arms are resampled independently, so the ceiling is the product,
    not either factor. For three runs against three it is 100, not 10 -- and
    the realised count is smaller again, because different multisets can share
    a median. Getting this wrong understates the ceiling by an order of
    magnitude and would have made the published intervals look degenerate when
    they are merely coarse.
    """
    return distinct_multisets(n_treatment) * distinct_multisets(n_control)


def largest_gap_split(values: list[float]) -> dict:
    """Split a sample at its largest gap and describe the two groups.

    A crude mode detector, and crude is what is wanted: the question is not
    where the modes are to three decimal places but whether the sample is a
    mixture at all, because a median summarises a mixture badly and jumps
    discontinuously when the mixture proportion crosses one half.
    """
    if len(values) < 2:
        return {}
    ordered = sorted(values)
    gaps = [(ordered[i + 1] - ordered[i], i) for i in range(len(ordered) - 1)]
    gap, index = max(gaps)
    lower, upper = ordered[: index + 1], ordered[index + 1:]
    spread = ordered[-1] - ordered[0]
    return {
        "gap": gap,
        "gap_share_of_range": gap / spread if spread else 0.0,
        "lower_n": len(lower),
        "upper_n": len(upper),
        "upper_fraction": len(upper) / len(ordered),
        "lower_median": statistics.median(lower),
        "upper_median": statistics.median(upper),
        # A single far point is an outlier, not a mixture, and calling it
        # one would have flagged B0 -- whose three run medians agree to within
        # 1.8 ms -- alongside B3, whose three disagree by 1 497 ms. Require the
        # smaller group to be a tenth of the sample before saying "mixture".
        "bimodal": (bool(spread) and gap / spread > 0.5
                    and len(upper) >= max(2, 0.1 * len(ordered))),
    }


def sign_test_floor(n: int) -> float:
    """Smallest achievable two-sided sign-test p-value with n paired sessions.

    2 / 2**n -- the probability of all n differences sharing a sign, doubled.
    If this exceeds alpha the test *cannot* reject however large the effect,
    which is a property of the design and not of the data.
    """
    if n < 1:
        raise ValueError("session count must be at least 1")
    return min(1.0, 2.0 / (2 ** n))


def runs_for_half_width(sd: float, target_half_width: float, *,
                        max_n: int = 400) -> int | None:
    """Smallest n whose two-sided 95% t half-width is within the target."""
    if sd <= 0 or target_half_width <= 0:
        return 1
    for n in range(2, max_n + 1):
        if t_critical(n - 1) * sd / math.sqrt(n) <= target_half_width:
            return n
    return None


def runs_for_power(sd: float, effect: float, *, power: float = TARGET_POWER,
                   max_n: int = 400) -> int | None:
    """Smallest n reaching ``power`` against ``effect`` for a one-sample t test.

    Normal approximation with the t critical value substituted for z, which is
    slightly conservative at small n -- the direction that costs runs rather
    than the direction that overstates the design.
    """
    if sd <= 0:
        return 2
    if effect <= 0:
        return None
    # z for the power quantile: 0.80 -> 0.8416, 0.90 -> 1.2816.
    z_power = {0.80: 0.8416, 0.90: 1.2816, 0.95: 1.6449}.get(power)
    if z_power is None:
        raise ValueError(f"no z quantile tabulated for power {power}")
    for n in range(2, max_n + 1):
        if (effect * math.sqrt(n)) / sd >= t_critical(n - 1) + z_power:
            return n
    return None


# ---------------------------------------------------------------------------
# Frozen-data readers.
# ---------------------------------------------------------------------------


def read_rows(path: Path) -> list[dict]:
    import csv
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def crash_free_latencies(path: Path, system: str) -> dict[str, list[float]]:
    """Per-run crash-free step latencies. Mirrors paper_tables.py exactly."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in read_rows(path):
        if row.get("regime") != CRASH_FREE_REGIME or row.get("system") != system:
            continue
        value = row.get("step_latency_ms")
        if value:
            grouped[row["run_id"]].append(float(value))
    return dict(grouped)


def bootstrap_difference_support(
    treatment: dict[str, list[float]],
    control: dict[str, list[float]],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    """Run the manuscript's estimator and report its *support*, not just its ends.

    The published number is the pair (2.5th, 97.5th percentile). What this adds
    is how many distinct values the resample distribution actually takes and
    whether those percentiles are interior points or the extremes -- which is
    the difference between an interval and a range.
    """
    rng = random.Random(seed)
    treatment_runs = sorted(treatment)
    control_runs = sorted(control)
    if not treatment_runs or not control_runs:
        return {}

    def draw(runs: list[str], data: dict[str, list[float]]) -> list[float]:
        picked: list[float] = []
        for _ in runs:
            picked.extend(data[rng.choice(runs)])
        return picked

    point = statistics.median(
        [v for run in treatment_runs for v in treatment[run]]
    ) - statistics.median([v for run in control_runs for v in control[run]])

    differences = []
    for _ in range(resamples):
        differences.append(
            statistics.median(draw(treatment_runs, treatment))
            - statistics.median(draw(control_runs, control))
        )
    differences.sort()
    low = differences[int(0.025 * len(differences))]
    high = differences[int(0.975 * len(differences))]
    realised = sorted(set(round(d, 6) for d in differences))
    return {
        "treatment_clusters": len(treatment_runs),
        "control_clusters": len(control_runs),
        "point": point,
        "ci_low": low,
        "ci_high": high,
        "ceiling_multisets_per_arm": distinct_multisets(len(treatment_runs)),
        "ceiling_for_difference": distinct_multisets_for_difference(
            len(treatment_runs), len(control_runs)),
        "realised_distinct_values": len(realised),
        "support_min": realised[0],
        "support_max": realised[-1],
        "low_is_support_min": math.isclose(low, realised[0], rel_tol=1e-9,
                                           abs_tol=1e-6),
        "high_is_support_max": math.isclose(high, realised[-1], rel_tol=1e-9,
                                            abs_tol=1e-6),
        "half_width": (high - low) / 2.0,
        "half_width_over_point": ((high - low) / 2.0 / abs(point))
        if point else float("inf"),
        "spans_zero": low <= 0.0 <= high,
    }


# ---------------------------------------------------------------------------
# Section A -- what the frozen intervals can support.
# ---------------------------------------------------------------------------


def jackknife_runs(per_run: dict[str, list[float]]) -> list[dict]:
    """Leave-one-run-out pooled medians.

    With three clusters, "is this interval wide because the quantity is
    uncertain, or because one run is unlike the other two?" is the whole
    question, and a jackknife answers it in three lines where a bootstrap
    percentile does not.
    """
    runs = sorted(per_run)
    everything = [v for r in runs for v in per_run[r]]
    full = statistics.median(everything)
    out = []
    for dropped in runs:
        kept = [v for r in runs if r != dropped for v in per_run[r]]
        if not kept:
            continue
        out.append({
            "dropped": dropped,
            "median_without": statistics.median(kept),
            "shift_from_full": statistics.median(kept) - full,
        })
    return out


def assess_mixtures() -> list[dict]:
    """Per-arm mixture diagnostics, and the per-run instability they cause."""
    out = []
    for policy, path in EXECUTION_PATHS.items():
        for system in ("B0_NAIVE_RETRY", "B3_INTENT_NO_BARRIER", "AEP_FULL"):
            per_run = crash_free_latencies(path, system)
            if not per_run:
                continue
            pooled = [v for vals in per_run.values() for v in vals]
            split = largest_gap_split(pooled)
            per_run_medians = {r: statistics.median(v) for r, v in per_run.items()}
            out.append({
                "policy": policy,
                "system": system,
                "clusters": len(per_run),
                "pooled_median": statistics.median(pooled),
                "per_run_medians": per_run_medians,
                "per_run_median_range": (max(per_run_medians.values())
                                         - min(per_run_medians.values())),
                "mixture": split,
                "per_run_upper_fraction": {
                    r: (sum(1 for v in vals
                            if split and v > split["lower_median"]
                            + split["gap"] / 2) / len(vals))
                    for r, vals in per_run.items()
                } if split else {},
                "jackknife": jackknife_runs(per_run),
            })
    return out


def assess_degeneracy() -> list[dict]:
    findings = []
    for policy, path in EXECUTION_PATHS.items():
        treated = crash_free_latencies(path, "AEP_FULL")
        ablated = crash_free_latencies(path, "B3_INTENT_NO_BARRIER")
        base = crash_free_latencies(path, "B0_NAIVE_RETRY")
        if treated and ablated:
            row = bootstrap_difference_support(treated, ablated)
            row.update(policy=policy, quantity="barrier cost (AEP-full - B3)")
            findings.append(row)
        if ablated and base:
            row = bootstrap_difference_support(ablated, base)
            row.update(policy=policy, quantity="protocol minus barrier (B3 - B0)")
            findings.append(row)
    return findings


# ---------------------------------------------------------------------------
# Section B -- session-level comparisons that failed to reject.
# ---------------------------------------------------------------------------

#: The two comparisons §VIII's conclusion-validity paragraph calls precision
#: failures rather than null results. Values are the per-session differences
#: already published in numbers.tex, restated here so this module can be run
#: without re-deriving them, and checked against numbers.tex by the test suite.
SESSION_COMPARISONS = {
    "kill_latency_ms": {
        "label": "kill-latency attribution (ms)",
        "per_session": [70.0, -4.0, 282.0, 74.0],
        "sesoi": 50.0,
        "sesoi_basis": (
            "half the smallest inter-arm gap the harness can schedule; below "
            "this the attribution cannot change a deployment decision"
        ),
    },
    "class_sweep_pp": {
        "label": "capability-class sweep (pp)",
        "per_session": [0.0, -10.0, 23.3, 36.7],
        "sesoi": SESOI_RATE_PP,
        "sesoi_basis": "the pre-registered rate margin, §5.5",
    },
}


def assess_session_comparison(name: str, spec: dict) -> dict:
    values = spec["per_session"]
    n = len(values)
    mean = statistics.mean(values)
    sd = statistics.stdev(values)
    se = sd / math.sqrt(n)
    half = t_critical(n - 1) * se
    return {
        "name": name,
        "label": spec["label"],
        "sessions": n,
        "mean": mean,
        "sd": sd,
        "half_width": half,
        "ci_low": mean - half,
        "ci_high": mean + half,
        "spans_zero": (mean - half) <= 0 <= (mean + half),
        "half_width_over_mean": half / abs(mean) if mean else float("inf"),
        "sign_test_floor": sign_test_floor(n),
        "sign_test_can_ever_reject": sign_test_floor(n) <= ALPHA,
        "sessions_for_sign_test": next(
            (k for k in range(1, 40) if sign_test_floor(k) <= ALPHA), None
        ),
        "sessions_for_power_at_observed": runs_for_power(sd, abs(mean)),
        "sessions_for_power_at_sesoi": runs_for_power(sd, spec["sesoi"]),
        "sesoi": spec["sesoi"],
        "sesoi_basis": spec["sesoi_basis"],
    }


# ---------------------------------------------------------------------------
# Section C -- sizing the timing collection (task 5.1).
# ---------------------------------------------------------------------------


def assess_timing_sizing() -> list[dict]:
    out = []
    for policy, path in EXECUTION_PATHS.items():
        for system in ("AEP_FULL", "B3_INTENT_NO_BARRIER", "B0_NAIVE_RETRY"):
            per_run = crash_free_latencies(path, system)
            if len(per_run) < 2:
                continue
            medians = [statistics.median(v) for v in per_run.values()]
            sd = statistics.stdev(medians)
            out.append({
                "policy": policy,
                "system": system,
                "clusters": len(per_run),
                "between_run_sd_ms": sd,
                "runs_for_sesoi_barrier": runs_for_half_width(sd, SESOI_BARRIER_MS),
                "runs_for_sesoi_protocol": runs_for_half_width(sd, SESOI_PROTOCOL_MS),
                "half_width_at_target": (
                    t_critical(TARGET_RUNS_PER_ARM - 1) * sd
                    / math.sqrt(TARGET_RUNS_PER_ARM)
                ),
            })
    return out


# ---------------------------------------------------------------------------
# Reporting.
# ---------------------------------------------------------------------------


def build_report() -> dict:
    return {
        "degeneracy": assess_degeneracy(),
        "mixtures": assess_mixtures(),
        "session_comparisons": [
            assess_session_comparison(k, v) for k, v in SESSION_COMPARISONS.items()
        ],
        "timing_sizing": assess_timing_sizing(),
        "preregistered": {
            "alpha": ALPHA,
            "target_power": TARGET_POWER,
            "sesoi_barrier_ms": SESOI_BARRIER_MS,
            "sesoi_protocol_ms": SESOI_PROTOCOL_MS,
            "sesoi_rate_pp": SESOI_RATE_PP,
            "target_runs_per_arm": TARGET_RUNS_PER_ARM,
        },
    }


def _empty(section: str) -> None:
    """Say which of the two empty-looking outcomes this is.

    A heading with nothing under it is ambiguous between "this view did not
    compute the section" and "the section was computed and found nothing".
    The first is routine; the second would, for section A2, mean no arm was
    flagged as a mixture -- which is H2 of the WS-5 pre-registration being
    refuted. Those must never render alike.
    """
    print(f"  ({section})")
    print()


def print_report(report: dict) -> None:
    print("=" * 74)
    print("WS-5 power assessment -- frozen data, no collection")
    print("=" * 74)

    print("\n-- A. What the three-run bootstrap intervals can support --\n")
    print("A cluster bootstrap over n runs can take at most C(2n-1, n) distinct")
    print("values. Ten thousand resamples do not change that.\n")
    if not report.get("degeneracy"):
        _empty("not computed in this view")
    for row in report["degeneracy"]:
        print(f"  {row['quantity']}  [appendfsync={row['policy']}]")
        print(f"    clusters per arm      : {row['treatment_clusters']} vs "
              f"{row['control_clusters']}")
        print(f"    ceiling on distinct   : "
              f"{row['ceiling_multisets_per_arm']} multisets per arm, "
              f"{row['ceiling_for_difference']} for the difference")
        print(f"    realised distinct     : {row['realised_distinct_values']} "
              f"values over {BOOTSTRAP_RESAMPLES} resamples")
        print(f"    point estimate        : {row['point']:.1f}")
        print(f"    published interval    : [{row['ci_low']:.1f}, "
              f"{row['ci_high']:.1f}]")
        print(f"    realised support      : [{row['support_min']:.1f}, "
              f"{row['support_max']:.1f}]")
        print(f"    endpoints are extremal: low={row['low_is_support_min']}  "
              f"high={row['high_is_support_max']}")
        print(f"    half-width / |point|  : {row['half_width_over_point']:.2f}"
              f"{'   SPANS ZERO' if row['spans_zero'] else ''}")
        print()

    print("-- A2. Why those intervals are wide: the arms are mixtures --\n")
    if "mixtures" not in report:
        _empty("not computed in this view")
    elif not report["mixtures"]:
        _empty("computed: no arm has a splittable sample")
    for row in report.get("mixtures", []):
        mix = row["mixture"]
        if not mix:
            continue
        flag = ("  <-- MIXTURE" if mix["bimodal"]
                else "  (single outlier, not a mixture)")
        print(f"  {row['system']:<22} [appendfsync={row['policy']}]{flag}")
        print(f"    pooled median         : {row['pooled_median']:.1f} ms")
        print(f"    per-run medians       : "
              + ", ".join(f"{v:.1f}" for v in row['per_run_medians'].values())
              + f"   (range {row['per_run_median_range']:.1f} ms)")
        print(f"    largest gap           : {mix['gap']:.1f} ms "
              f"= {mix['gap_share_of_range'] * 100:.0f}% of the range")
        print(f"    lower / upper mode    : {mix['lower_median']:.1f} ms "
              f"(n={mix['lower_n']})  /  {mix['upper_median']:.1f} ms "
              f"(n={mix['upper_n']})")
        print(f"    upper-mode fraction   : {mix['upper_fraction'] * 100:.0f}% "
              f"pooled; per run "
              + ", ".join(f"{v * 100:.0f}%"
                          for v in row['per_run_upper_fraction'].values()))
        for jk in row["jackknife"]:
            if abs(jk["shift_from_full"]) >= 1.0:
                print(f"    drop {jk['dropped'][-2:]:>3}            : median "
                      f"{jk['median_without']:.1f} ms "
                      f"({jk['shift_from_full']:+.1f})")
        print()

    print("-- B. The two comparisons §VIII calls precision failures --\n")
    if not report.get("session_comparisons"):
        _empty("not computed in this view")
    for row in report["session_comparisons"]:
        print(f"  {row['label']}")
        print(f"    sessions              : {row['sessions']}")
        print(f"    mean, sd              : {row['mean']:+.1f}, {row['sd']:.1f}")
        print(f"    95% interval          : [{row['ci_low']:+.1f}, "
              f"{row['ci_high']:+.1f}]  half-width {row['half_width']:.1f}")
        print(f"    half-width / |mean|   : {row['half_width_over_mean']:.2f}")
        print(f"    sign-test floor       : p >= {row['sign_test_floor']:.3f}"
              f"  -> can ever reject at 0.05: "
              f"{row['sign_test_can_ever_reject']}")
        print(f"    sessions for sign test: {row['sessions_for_sign_test']}")
        print(f"    sessions for 80% power at SESOI "
              f"{row['sesoi']:g}: {row['sessions_for_power_at_sesoi']}")
        print(f"      (SESOI basis: {row['sesoi_basis']})")
        print(f"    sessions for 80% power at the OBSERVED effect: "
              f"{row['sessions_for_power_at_observed']}  "
              f"[post-hoc, not a design target]")
        print()

    print("-- C. Sizing the timing arms (task 5.1) --\n")
    if not report.get("timing_sizing"):
        _empty("not computed in this view")
    for row in report["timing_sizing"]:
        print(f"  {row['system']:<22} [appendfsync={row['policy']}]  "
              f"clusters={row['clusters']}")
        print(f"    between-run sd        : {row['between_run_sd_ms']:.1f} ms "
              f"(from {row['clusters']} runs -- itself imprecise)")
        print(f"    runs for +/-{SESOI_BARRIER_MS:g} ms  : "
              f"{row['runs_for_sesoi_barrier']}")
        print(f"    runs for +/-{SESOI_PROTOCOL_MS:g} ms   : "
              f"{row['runs_for_sesoi_protocol']}")
        print(f"    half-width at n={TARGET_RUNS_PER_ARM}   : "
              f"{row['half_width_at_target']:.1f} ms")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="emit the assessment as JSON")
    parser.add_argument("--section",
                        choices=("degeneracy", "session", "timing"),
                        help="print one section only")
    # The instrument is fixed; the tree it reads is not. Pre-registration
    # section 2.3 names this module as the mixture instrument, and the arms it
    # has to judge are the fifteen-run ones collected later, not the three-run
    # ones that motivated the workstream. Overriding the path changes which
    # data is read and nothing else: estimator, resamples and seed are
    # module constants and stay where they are.
    parser.add_argument("--everysec", type=Path, default=None,
                        help="per-execution.csv for the appendfsync=everysec arm")
    parser.add_argument("--always", type=Path, default=None,
                        help="per-execution.csv for the appendfsync=always arm")
    args = parser.parse_args()

    if args.everysec or args.always:
        chosen = {}
        if args.everysec:
            chosen["everysec"] = args.everysec
        if args.always:
            chosen["always"] = args.always
        for label, path in chosen.items():
            if not path.is_file():
                raise SystemExit(f"FAIL: no per-execution.csv at {path}")
        EXECUTION_PATHS.clear()
        EXECUTION_PATHS.update(chosen)
        print("# reading:", ", ".join(f"{k}={v}" for k, v in chosen.items()))

    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if args.section == "degeneracy":
        # "mixtures" travels WITH degeneracy and is not optional: section A2
        # is the explanation for section A, and dropping it made the report
        # print an empty A2 that reads exactly like "no arm was flagged".
        # An instrument that renders "not computed" and "nothing found"
        # identically is the R14 shape, inside the instrument written to
        # judge the mixture. Caught on the first fifteen-run run.
        report = {"degeneracy": report["degeneracy"],
                  "mixtures": report["mixtures"],
                  "session_comparisons": [], "timing_sizing": []}
    elif args.section == "session":
        report = {"degeneracy": [], "mixtures": [], "session_comparisons":
                  report["session_comparisons"], "timing_sizing": []}
    elif args.section == "timing":
        report = {"degeneracy": [], "mixtures": [], "session_comparisons": [],
                  "timing_sizing": report["timing_sizing"]}
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
