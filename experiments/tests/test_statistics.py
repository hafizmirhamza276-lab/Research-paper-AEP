"""The statistics are checked against values computed by hand.

A test that compares one implementation against another implementation of the
same formula proves only that they agree. The Fisher p-values below are worked
out from the hypergeometric definition on small tables where the arithmetic can
be written out, and the bootstrap is checked on inputs whose answer is forced
by construction rather than by a reference library.
"""

from __future__ import annotations

from fractions import Fraction
from math import comb

import pytest

from experiments.statistics import (
    Interval,
    cluster_bootstrap_median_difference,
    cluster_bootstrap_proportion,
    compare_rates,
    fisher_exact_two_tailed,
    proportion,
    quantile,
    summarise,
)


# ---------------------------------------------------------------------------
# Fisher's exact test
# ---------------------------------------------------------------------------


def test_the_tea_tasting_table() -> None:
    """Fisher's own example. 3/4 correct out of 4 and 4, two-tailed p = 0.4857.

    Table [[3,1],[1,3]]: the possible values of cell a are 0..4 with
    probabilities C(4,a)C(4,4-a)/C(8,4) = 1/70, 16/70, 36/70, 16/70, 1/70.
    The observed weight is 16; tables with weight <= 16 are a in {0,1,3,4},
    totalling (1+16+16+1)/70 = 34/70 = 0.4857142857...
    """
    p = fisher_exact_two_tailed(3, 1, 1, 3)
    assert p == pytest.approx(34 / 70, rel=1e-12)


def test_a_perfectly_separated_table() -> None:
    """[[4,0],[0,4]]: only the two extreme tables are as improbable. 2/70."""
    p = fisher_exact_two_tailed(4, 0, 0, 4)
    assert p == pytest.approx(2 / 70, rel=1e-12)


def test_the_shape_the_paper_reports() -> None:
    """AEP-full at zero against a baseline that duplicates often.

    [[0, 30], [12, 18]]: the reference row has no events at all, so the
    p-value is the probability of seeing a split this lopsided or worse.
    Computed here from the definition, independently of the implementation.
    """
    a, b, c, d = 0, 30, 12, 18
    row1, row2, column1, total = a + b, c + d, a + c, a + b + c + d
    observed = comb(row1, a) * comb(row2, column1 - a)
    expected = Fraction(
        sum(
            comb(row1, i) * comb(row2, column1 - i)
            for i in range(max(0, column1 - row2), min(row1, column1) + 1)
            if comb(row1, i) * comb(row2, column1 - i) <= observed
        ),
        comb(total, column1),
    )
    assert fisher_exact_two_tailed(a, b, c, d) == pytest.approx(
        float(expected), rel=1e-12
    )
    assert float(expected) < 0.001


def test_identical_rows_are_not_significant() -> None:
    assert fisher_exact_two_tailed(5, 5, 5, 5) == pytest.approx(1.0)


def test_a_zero_margin_has_nothing_to_reject() -> None:
    """No events anywhere: one table is possible, so p = 1."""
    assert fisher_exact_two_tailed(0, 10, 0, 10) == 1.0
    assert fisher_exact_two_tailed(10, 0, 10, 0) == 1.0
    assert fisher_exact_two_tailed(0, 0, 0, 0) == 1.0


def test_the_test_is_symmetric_under_swapping_rows() -> None:
    assert fisher_exact_two_tailed(2, 8, 7, 3) == pytest.approx(
        fisher_exact_two_tailed(7, 3, 2, 8)
    )


def test_negative_counts_are_refused() -> None:
    with pytest.raises(ValueError):
        fisher_exact_two_tailed(-1, 2, 3, 4)


def test_p_never_exceeds_one() -> None:
    for table in ((1, 1, 1, 1), (0, 1, 1, 0), (3, 7, 4, 6), (30, 0, 0, 30)):
        assert 0.0 <= fisher_exact_two_tailed(*table) <= 1.0


# ---------------------------------------------------------------------------
# The cluster bootstrap
# ---------------------------------------------------------------------------


def test_identical_clusters_give_a_degenerate_interval() -> None:
    """Every resample is the same rate, so the interval collapses onto it.

    Forced by construction: with three identical clusters, any draw with
    replacement pools the same proportion.
    """
    interval = cluster_bootstrap_proportion([(3, 10), (3, 10), (3, 10)], resamples=500)
    assert interval.point == pytest.approx(0.3)
    assert interval.low == pytest.approx(0.3)
    assert interval.high == pytest.approx(0.3)


def test_a_single_cluster_reports_a_point_not_a_range() -> None:
    """One run is one run. The interval must not pretend otherwise."""
    interval = cluster_bootstrap_proportion([(2, 10)], resamples=500)
    assert (interval.point, interval.low, interval.high) == (0.2, 0.2, 0.2)
    assert interval.clusters == 1


def test_the_interval_brackets_the_point_and_widens_with_disagreement() -> None:
    agreeing = cluster_bootstrap_proportion([(5, 10), (5, 10), (5, 10)], resamples=2000)
    disagreeing = cluster_bootstrap_proportion(
        [(0, 10), (5, 10), (10, 10)], resamples=2000
    )
    assert agreeing.point == disagreeing.point == pytest.approx(0.5)
    assert agreeing.high - agreeing.low < disagreeing.high - disagreeing.low


def test_the_bootstrap_is_reproducible_from_its_seed() -> None:
    """Every interval in the paper must be recomputable from what is printed.

    Only reproducibility is asserted, not seed *sensitivity*. With three
    clusters the resampling distribution has ten distinct multisets, so two
    different seeds routinely land on the same percentile bounds -- which is a
    property of a small discrete support, not evidence that the seed is
    ignored. The seed's effect is asserted below, on a sample large enough for
    it to have one.
    """
    clusters = [(1, 10), (4, 10), (7, 10)]
    first = cluster_bootstrap_proportion(clusters, resamples=1000, seed=99)
    second = cluster_bootstrap_proportion(clusters, resamples=1000, seed=99)
    assert (first.point, first.low, first.high) == (
        second.point,
        second.low,
        second.high,
    )


def test_different_seeds_draw_different_resamples() -> None:
    """With enough clusters for the support to be rich, the seed shows."""
    clusters = [(index % 7, 10) for index in range(40)]
    first = cluster_bootstrap_proportion(clusters, resamples=2000, seed=1)
    other = cluster_bootstrap_proportion(clusters, resamples=2000, seed=2)
    assert first.point == other.point
    assert (first.low, first.high) != (other.low, other.high)


def test_an_all_zero_rate_stays_at_zero() -> None:
    """AEP-full's expected row. A bootstrap of zeros cannot manufacture a tail."""
    interval = cluster_bootstrap_proportion([(0, 10), (0, 10), (0, 10)], resamples=2000)
    assert (interval.point, interval.low, interval.high) == (0.0, 0.0, 0.0)


def test_median_difference_resamples_run_clusters_not_executions() -> None:
    treatment = {"t1": [10.0] * 10, "t2": [30.0] * 10}
    control = {"c1": [5.0] * 10, "c2": [15.0] * 10}
    interval = cluster_bootstrap_median_difference(
        treatment, control, resamples=2_000, seed=9
    )
    assert interval.treatment_clusters == 2
    assert interval.control_clusters == 2
    assert interval.treatment_observations == 20
    assert interval.control_observations == 20
    assert interval.low <= interval.point <= interval.high


def test_an_empty_cell_is_zero_and_says_so() -> None:
    interval = cluster_bootstrap_proportion([], resamples=100)
    assert interval.observations == 0
    assert interval.point == 0.0
    assert interval.resamples == 0


def test_the_echo_carries_the_seed_and_the_counts() -> None:
    echo = cluster_bootstrap_proportion([(1, 10), (2, 10)], resamples=100, seed=7).echo()
    assert echo["bootstrap_seed"] == 7
    assert echo["clusters"] == 2
    assert echo["observations"] == 20


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def test_an_empty_denominator_is_zero_not_nan() -> None:
    assert proportion(0, 0) == 0.0


def test_quantiles_are_observed_values() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert quantile(values, 0.5) in values
    assert quantile(values, 0.95) == 10.0
    assert quantile(values, 0.0) == 1.0
    assert quantile([], 0.5) is None


def test_summarise_reports_nothing_rather_than_zero_for_an_empty_sample() -> None:
    empty = summarise([])
    assert empty["count"] == 0
    assert empty["mean"] is None
    assert empty["p99"] is None


def test_compare_rates_builds_the_table_the_right_way_round() -> None:
    comparison = compare_rates(
        "undetected_duplicate_rate",
        system="B0_NAIVE_RETRY",
        reference="AEP_FULL",
        system_successes=12,
        system_total=30,
        reference_successes=0,
        reference_total=30,
    )
    assert comparison.system_rate == pytest.approx(0.4)
    assert comparison.reference_rate == 0.0
    assert comparison.p_value == pytest.approx(
        fisher_exact_two_tailed(12, 18, 0, 30), rel=1e-12
    )
    assert comparison.p_value < 0.001


def test_interval_is_immutable() -> None:
    interval = Interval(0.1, 0.0, 0.2, 100, 1, 3, 30)
    with pytest.raises(Exception):
        interval.point = 0.5  # type: ignore[misc]
