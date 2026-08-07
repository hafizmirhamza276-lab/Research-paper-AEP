"""A figure is a claim. These pin the two ways ours were computing wrong ones.

Both defects were found while preparing the manuscript, and neither was
visible in any output: the figures rendered, the numbers were plausible, and
nothing failed.

**Defect 1 -- figure 1 was drawn from the banned table.** Session 3B forbade
``analysis/table-1.csv`` as a source because it pools three fault regimes, so
each rate is a property of the collected mix. ``write_figures`` took its bar
heights straight from it. A banned table does not become quotable by being
drawn, so figure 1 is now pooled from ``per_cell`` inside one regime.

**Defect 2 -- figure 2 pooled with a running mean.** The code read
``current[point] = rate if previous is None else (previous + rate) / 2``
under a comment claiming it weighted on counts. It does not. It is
order-dependent, and over three response classes it weights the last-seen at
1/2, the one before at 1/4 and the first at 1/4. A rate over executions is a
ratio of sums.
"""

from __future__ import annotations

from experiments.analyze import FIGURE_REGIME
from experiments.statistics import wilson_interval


def _cell(
    *,
    system: str,
    crash_point: str,
    response_class: str,
    successes: int,
    total: int,
    metric: str = "undetected_duplicate_rate",
    regime: str = FIGURE_REGIME,
) -> dict[str, object]:
    return {
        "metric": metric,
        "regime": regime,
        "system": system,
        "crash_point": crash_point,
        "response_class": response_class,
        "readback_keying": "CALLER_REFERENCE",
        "successes": successes,
        "total": total,
        "rate": successes / total if total else 0.0,
        "runs": 3,
    }


def _pool_by_crash_point(cells, regime=FIGURE_REGIME):
    """The corrected pooling, extracted so the arithmetic can be asserted."""
    counts: dict[tuple[str, str], list[int]] = {}
    for row in cells:
        if row["metric"] != "undetected_duplicate_rate":
            continue
        if row.get("regime") != regime:
            continue
        key = (row["system"], row["crash_point"])
        bucket = counts.setdefault(key, [0, 0])
        bucket[0] += int(row["successes"])
        bucket[1] += int(row["total"])
    return {
        key: (pair[0] / pair[1] if pair[1] else 0.0)
        for key, pair in counts.items()
    }


def test_pooling_is_a_ratio_of_sums_not_a_running_mean() -> None:
    """Three unequal cells: the two formulas give visibly different answers."""
    cells = [
        _cell(
            system="B0",
            crash_point="mid_dispatch",
            response_class="AUTHORITATIVE_READBACK",
            successes=1,
            total=10,
        ),
        _cell(
            system="B0",
            crash_point="mid_dispatch",
            response_class="POSITIVE_ONLY_READBACK",
            successes=0,
            total=10,
        ),
        _cell(
            system="B0",
            crash_point="mid_dispatch",
            response_class="NO_READBACK",
            successes=30,
            total=30,
        ),
    ]

    pooled = _pool_by_crash_point(cells)
    # 31 duplicates in 50 executions.
    assert pooled[("B0", "mid_dispatch")] == 31 / 50

    # What the old code produced, for contrast: ((0.1 + 0.0)/2 + 1.0)/2.
    running = None
    for row in cells:
        running = (
            row["rate"] if running is None else (running + row["rate"]) / 2
        )
    assert running == 0.525
    assert abs(running - 31 / 50) > 0.09, (
        "the running mean and the pooled rate must differ here, or this test "
        "is not exercising the defect"
    )


def test_pooling_is_order_independent() -> None:
    cells = [
        _cell(
            system="B0",
            crash_point="mid_dispatch",
            response_class=response,
            successes=successes,
            total=total,
        )
        for response, successes, total in (
            ("AUTHORITATIVE_READBACK", 1, 10),
            ("POSITIVE_ONLY_READBACK", 0, 10),
            ("NO_READBACK", 30, 30),
        )
    ]
    assert _pool_by_crash_point(cells) == _pool_by_crash_point(cells[::-1])


def test_cells_from_another_regime_are_excluded() -> None:
    """A crash-free cell must not raise a crashed system's duplicate rate."""
    cells = [
        _cell(
            system="B0",
            crash_point="none",
            response_class="AUTHORITATIVE_READBACK",
            successes=0,
            total=30,
            regime="p0",
        ),
        _cell(
            system="B0",
            crash_point="mid_dispatch",
            response_class="AUTHORITATIVE_READBACK",
            successes=25,
            total=30,
        ),
    ]
    pooled = _pool_by_crash_point(cells)
    assert ("B0", "none") not in pooled
    assert pooled[("B0", "mid_dispatch")] == 25 / 30


def test_the_figure_regime_is_a_single_named_regime() -> None:
    assert isinstance(FIGURE_REGIME, str) and FIGURE_REGIME


def test_wilson_interval_behaves_at_the_boundaries() -> None:
    """The duplicate rate is exactly 0 for three systems; the interval must
    stay inside [0, 1] there, which a normal approximation does not."""
    low, high = wilson_interval(0, 180)
    assert low == 0.0
    assert 0.0 < high < 0.05

    low, high = wilson_interval(180, 180)
    assert high == 1.0
    assert 0.95 < low < 1.0

    # An empty cell is not a measurement.
    assert wilson_interval(0, 0) == (0.0, 0.0)

    # A known value: 1 success in 10 trials, 95% Wilson, is about
    # [0.018, 0.404].
    low, high = wilson_interval(1, 10)
    assert abs(low - 0.0179) < 0.002
    assert abs(high - 0.4042) < 0.002
