"""The two statistical procedures PAPER_ROADMAP.md section 3.2 asks for.

    *"report mean + 95% CI (bootstrap), and for rate comparisons use Fisher's
    exact test; state seeds and repetition counts."*

Both are implemented here rather than imported, for reasons that are about the
paper rather than about dependencies.

**Fisher's exact test is computed exactly.** The two-tailed p-value is the sum
of the hypergeometric probabilities of every 2x2 table with the observed
margins whose probability does not exceed the observed table's. Implemented in
integer arithmetic -- every probability shares the denominator ``C(n, k)``, so
the comparison "is this table at least as extreme" is a comparison of exact
integers, with no floating-point tolerance deciding which tables are counted.
This matters here more than usual: the headline comparison is against a rate
that is expected to be zero, where the tables at the boundary are exactly the
ones a tolerance would include or exclude.

**The bootstrap is clustered by run.** Executions inside one run share a
provider, a Redis keyspace, a worker-respawn history and a seed. Resampling
executions independently would treat 30 correlated observations as 30
independent ones and report an interval narrower than the evidence supports.
The resampling unit is therefore the *run*: draw runs with replacement, pool
their executions, recompute the rate. That is the standard cluster bootstrap,
and it is the honest one for a design that collects 30 repetitions as three
runs of ten.

**The seed is an argument, never a global.** Every interval in the paper must
be reproducible from the numbers printed beside it.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from math import comb
from statistics import NormalDist
from typing import Any, Mapping, Sequence

#: Bootstrap resamples. 10 000 is the usual floor for a percentile interval
#: reported to two decimal places.
DEFAULT_RESAMPLES = 10_000

#: The seed every interval in the paper is computed with, unless one is passed.
DEFAULT_BOOTSTRAP_SEED = 20260806


@dataclass(frozen=True)
class Interval:
    """A point estimate and a percentile bootstrap interval around it."""

    point: float
    low: float
    high: float
    resamples: int
    seed: int
    clusters: int
    observations: int

    def echo(self) -> dict[str, Any]:
        return {
            "point": self.point,
            "ci_low": self.low,
            "ci_high": self.high,
            "resamples": self.resamples,
            "bootstrap_seed": self.seed,
            "clusters": self.clusters,
            "observations": self.observations,
        }


def proportion(successes: int, total: int) -> float:
    """A rate, with an empty denominator reported as ``0.0`` and not as NaN.

    A cell with no observations is a cell that was not collected; the caller
    is expected to say so from the counts, and a NaN propagating into a CSV
    would be read as a measurement.
    """
    return successes / total if total else 0.0


def wilson_interval(
    successes: int, total: int, *, confidence: float = 0.95
) -> tuple[float, float]:
    """A two-sided Wilson score interval on a pooled proportion.

    This exists for the *figures* and nowhere else. Every interval in the CSVs
    is a cluster bootstrap over runs, because executions within one run are
    not independent -- one crash produces ten correlated outcomes -- and an
    interval that ignored that would be too narrow.

    A figure that pools across cells has no cluster structure left to
    resample: the pooled counts are all that remain. Wilson is the right
    interval for that shape (it does not misbehave at 0 or 1, where a normal
    approximation produces bounds outside [0, 1], and the duplicate rates in
    this paper sit at exactly 0 for three systems).

    **These bounds are not the ones in the CSV and are not interchangeable
    with them.** The CSV's are cluster-aware and wider; quote those.
    """
    if total <= 0:
        return (0.0, 0.0)
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be strictly between zero and one")
    if successes < 0 or successes > total:
        raise ValueError("successes must be between zero and total")
    z = NormalDist().inv_cdf((1.0 + confidence) / 2.0)
    phat = successes / total
    denominator = 1.0 + z * z / total
    centre = (phat + z * z / (2 * total)) / denominator
    spread = (
        z
        * math.sqrt(phat * (1.0 - phat) / total + z * z / (4 * total * total))
        / denominator
    )
    # Avoid exposing floating-point cancellation as a nonzero lower endpoint
    # at exactly zero (and symmetrically below one at exactly total). These are
    # mathematical boundary values, not numerical approximations.
    low = 0.0 if successes == 0 else max(0.0, centre - spread)
    high = 1.0 if successes == total else min(1.0, centre + spread)
    return (low, high)


def wilson_upper_bound(
    successes: int, total: int, *, confidence: float = 0.95
) -> float:
    """A genuinely one-sided Wilson upper confidence bound.

    A one-sided 95% bound uses ``Phi^-1(0.95)``, not the 1.96 quantile used
    by the upper endpoint of a two-sided 95% interval. Keeping this as a
    separate function makes that distinction explicit at every call site.
    """
    if total <= 0:
        return 0.0
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be strictly between zero and one")
    if successes < 0 or successes > total:
        raise ValueError("successes must be between zero and total")
    z = NormalDist().inv_cdf(confidence)
    phat = successes / total
    denominator = 1.0 + z * z / total
    centre = (phat + z * z / (2 * total)) / denominator
    spread = (
        z
        * math.sqrt(phat * (1.0 - phat) / total + z * z / (4 * total * total))
        / denominator
    )
    return min(1.0, centre + spread)


@dataclass(frozen=True)
class DifferenceInterval:
    """A confidence interval for ``system rate - reference rate``."""

    point: float
    low: float
    high: float
    confidence: float
    resamples: int
    seed: int
    system_clusters: int
    reference_clusters: int
    strata: int

    def within(self, margin: float) -> bool:
        """Whether the complete interval lies strictly inside ``+/-margin``."""
        if margin <= 0.0:
            raise ValueError("equivalence margin must be positive")
        return self.low > -margin and self.high < margin


def stratified_cluster_bootstrap_difference(
    system: Mapping[str, Sequence[tuple[int, int]]],
    reference: Mapping[str, Sequence[tuple[int, int]]],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    confidence: float = 0.90,
) -> DifferenceInterval:
    """Bootstrap a rate difference by resampling runs within matched strata.

    Each mapping value contains one ``(successes, total)`` pair per run. The
    same stratum set must exist in both arms. Resampling within each stratum
    preserves the experiment's fixed crash-point, endpoint-capability and
    keying mix while treating a run, rather than an execution, as the
    independent unit.
    """
    if set(system) != set(reference) or not system:
        raise ValueError("system and reference must have the same non-empty strata")
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be strictly between zero and one")

    def validate(arm: Mapping[str, Sequence[tuple[int, int]]]) -> None:
        for stratum, clusters in arm.items():
            if not clusters:
                raise ValueError(f"stratum {stratum!r} has no run clusters")
            for successes, total in clusters:
                if total <= 0 or successes < 0 or successes > total:
                    raise ValueError("each run cluster must have 0 <= successes <= total")

    validate(system)
    validate(reference)

    def pooled_rate(arm: Mapping[str, Sequence[tuple[int, int]]]) -> float:
        successes = sum(pair[0] for clusters in arm.values() for pair in clusters)
        total = sum(pair[1] for clusters in arm.values() for pair in clusters)
        return proportion(successes, total)

    point = pooled_rate(system) - pooled_rate(reference)
    generator = random.Random(seed)
    draws: list[float] = []
    ordered_strata = sorted(system)
    for _ in range(resamples):
        arm_rates: list[float] = []
        for arm in (system, reference):
            successes = total = 0
            for stratum in ordered_strata:
                clusters = arm[stratum]
                for _ in range(len(clusters)):
                    chosen_successes, chosen_total = clusters[
                        generator.randrange(len(clusters))
                    ]
                    successes += chosen_successes
                    total += chosen_total
            arm_rates.append(proportion(successes, total))
        draws.append(arm_rates[0] - arm_rates[1])

    draws.sort()
    tail = (1.0 - confidence) / 2.0
    low = draws[max(0, int(tail * resamples) - 1)]
    high = draws[min(resamples - 1, int((1.0 - tail) * resamples))]
    return DifferenceInterval(
        point=point,
        low=low,
        high=high,
        confidence=confidence,
        resamples=resamples,
        seed=seed,
        system_clusters=sum(len(clusters) for clusters in system.values()),
        reference_clusters=sum(
            len(clusters) for clusters in reference.values()
        ),
        strata=len(system),
    )


def cluster_bootstrap_proportion(
    clusters: Sequence[tuple[int, int]],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    confidence: float = 0.95,
) -> Interval:
    """Percentile bootstrap for a rate, resampling whole runs.

    ``clusters`` is one ``(successes, total)`` pair per run. The point estimate
    is the pooled rate over every run; each resample draws ``len(clusters)``
    runs with replacement and pools those.

    A single cluster produces a degenerate interval -- every resample is the
    same run -- and that is reported honestly as ``[point, point]`` rather than
    disguised. It is a signal that the cell has one run, not that its rate is
    known exactly.
    """
    successes = sum(pair[0] for pair in clusters)
    total = sum(pair[1] for pair in clusters)
    point = proportion(successes, total)
    if not clusters or total == 0:
        return Interval(
            point=point,
            low=point,
            high=point,
            resamples=0,
            seed=seed,
            clusters=len(clusters),
            observations=total,
        )

    generator = random.Random(seed)
    count = len(clusters)
    draws: list[float] = []
    for _ in range(resamples):
        drawn_successes = 0
        drawn_total = 0
        for _ in range(count):
            chosen = clusters[generator.randrange(count)]
            drawn_successes += chosen[0]
            drawn_total += chosen[1]
        draws.append(proportion(drawn_successes, drawn_total))

    draws.sort()
    tail = (1.0 - confidence) / 2.0
    low = draws[max(0, int(tail * resamples) - 1)]
    high = draws[min(resamples - 1, int((1.0 - tail) * resamples))]
    return Interval(
        point=point,
        low=low,
        high=high,
        resamples=resamples,
        seed=seed,
        clusters=count,
        observations=total,
    )


def fisher_exact_two_tailed(a: int, b: int, c: int, d: int) -> float:
    """Two-tailed Fisher's exact test for the table ``[[a, b], [c, d]]``.

    Rows are the two systems, columns are (event, no event). Conditioning on
    both margins, the count in cell ``a`` is hypergeometric, and the p-value is
    the total probability of every table at least as extreme as the observed
    one -- "at least as extreme" meaning "no more probable".

    Exact integer arithmetic: every table with these margins has probability
    ``C(r1, i) * C(r2, k - i) / C(n, k)``, so the shared denominator cancels
    out of the comparison and both the selection and the sum are done on
    integers. Nothing here depends on a floating-point tolerance.
    """
    for value in (a, b, c, d):
        if value < 0:
            raise ValueError("counts cannot be negative")
    row1, row2 = a + b, c + d
    column1 = a + c
    total = row1 + row2
    if total == 0 or row1 == 0 or row2 == 0 or column1 == 0 or column1 == total:
        # A margin of zero leaves exactly one possible table, so the observed
        # one is certain and there is nothing to reject.
        return 1.0

    denominator = comb(total, column1)
    observed = comb(row1, a) * comb(row2, column1 - a)

    numerator = 0
    low = max(0, column1 - row2)
    high = min(row1, column1)
    for i in range(low, high + 1):
        weight = comb(row1, i) * comb(row2, column1 - i)
        if weight <= observed:
            numerator += weight

    # Clamped: the sum can exceed the denominator only by floating-point
    # conversion, and a p-value above 1 in a table would be read as a bug in
    # the experiment rather than in the printer.
    return min(1.0, numerator / denominator)


@dataclass(frozen=True)
class RateComparison:
    """One baseline against the reference system, on one rate."""

    metric: str
    system: str
    reference: str
    system_successes: int
    system_total: int
    reference_successes: int
    reference_total: int
    p_value: float

    @property
    def system_rate(self) -> float:
        return proportion(self.system_successes, self.system_total)

    @property
    def reference_rate(self) -> float:
        return proportion(self.reference_successes, self.reference_total)

    def echo(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "system": self.system,
            "reference": self.reference,
            "system_successes": self.system_successes,
            "system_total": self.system_total,
            "system_rate": self.system_rate,
            "reference_successes": self.reference_successes,
            "reference_total": self.reference_total,
            "reference_rate": self.reference_rate,
            "fisher_p_value": self.p_value,
        }


def compare_rates(
    metric: str,
    *,
    system: str,
    reference: str,
    system_successes: int,
    system_total: int,
    reference_successes: int,
    reference_total: int,
) -> RateComparison:
    return RateComparison(
        metric=metric,
        system=system,
        reference=reference,
        system_successes=system_successes,
        system_total=system_total,
        reference_successes=reference_successes,
        reference_total=reference_total,
        p_value=fisher_exact_two_tailed(
            system_successes,
            system_total - system_successes,
            reference_successes,
            reference_total - reference_successes,
        ),
    )


def quantile(values: Sequence[float], fraction: float) -> float | None:
    """Nearest-rank quantile. ``None`` for an empty sample.

    Nearest-rank rather than interpolated: every latency reported in the paper
    is then a latency that was actually observed, which is what a reader of a
    p99 expects it to be.
    """
    if not values:
        return None
    ordered = sorted(values)
    if fraction <= 0:
        return ordered[0]
    if fraction >= 1:
        return ordered[-1]
    rank = max(1, min(len(ordered), int(fraction * len(ordered) + 0.9999999)))
    return ordered[rank - 1]


def summarise(values: Sequence[float]) -> dict[str, float | None]:
    """Count, mean and the three quantiles section 3.2 asks for."""
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p95": None,
            "p99": None,
            "min": None,
            "max": None,
        }
    return {
        "count": len(values),
        "mean": sum(values) / len(values),
        "median": quantile(values, 0.5),
        "p95": quantile(values, 0.95),
        "p99": quantile(values, 0.99),
        "min": min(values),
        "max": max(values),
    }
