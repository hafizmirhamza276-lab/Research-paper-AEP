"""The percentile convention the run-clustered intervals use, pinned.

Stage 3 moved ``cluster_bootstrap_median_difference`` out of
``scripts/paper_tables.py`` and into ``experiments/statistics.py``. The move
was not a copy: the two implementations index the lower endpoint differently.

    Stage 2 (paper_tables)   low = draws[int(tail * B)]
    Stage 3 (statistics)     low = draws[int(tail * B) - 1]

One order statistic out of 10,000, and for the three-run-per-arm latency cells
the paper already publishes it makes no difference at all -- every macro in
``paper/generated/numbers.tex`` regenerates byte-identically across the move.
That is luck, not equivalence: with three clusters the bootstrap distribution
is coarse enough that adjacent order statistics collide. Sampling forty
realistic datasets, the two conventions disagree on nine of them, and the
disagreements include the nine-cluster shape -- which is exactly the shape
Stage 3's B3 timing collection uses. So the convention is settled here, in a
test, rather than left to be discovered when an interval endpoint moves.

The settled convention is the Stage 3 one, for two reasons. It is the standard
``ceil(p * B)``-th order statistic (1-indexed), which for p = 0.025 and
B = 10,000 is the 250th value, i.e. index 249. And it is the marginally wider,
therefore marginally more conservative, of the two.
"""

from __future__ import annotations

import random
import statistics as stats

import pytest

from experiments.statistics import (
    DEFAULT_BOOTSTRAP_SEED,
    DEFAULT_RESAMPLES,
    cluster_bootstrap_median_difference,
)


def _stage2_convention(
    treatment: dict[str, list[float]],
    control: dict[str, list[float]],
    *,
    resamples: int,
    seed: int,
) -> tuple[float, float]:
    """The Stage 2 ``paper_tables`` endpoints, reproduced for comparison."""
    rng = random.Random(seed)
    treatment_runs = sorted(treatment)
    control_runs = sorted(control)

    def draw(runs: list[str], data: dict[str, list[float]]) -> list[float]:
        picked = [runs[rng.randrange(len(runs))] for _ in range(len(runs))]
        return [value for run in picked for value in data[run]]

    draws = [
        stats.median(draw(treatment_runs, treatment))
        - stats.median(draw(control_runs, control))
        for _ in range(resamples)
    ]
    draws.sort()
    low = draws[int(0.025 * len(draws))]
    high = draws[min(len(draws) - 1, int(0.975 * len(draws)))]
    return low, high


def test_lower_endpoint_is_the_ceil_p_b_order_statistic() -> None:
    """Pin the index formula itself, on a distribution with no ties.

    Every cluster holds one distinct value, so the bootstrap replicates are
    spread widely enough that neighbouring order statistics differ and the
    formula is observable in the result.
    """
    treatment = {f"t{i}": [float(i)] for i in range(40)}
    control = {"c0": [0.0]}
    resamples = 1_000

    interval = cluster_bootstrap_median_difference(
        treatment, control, resamples=resamples, seed=7
    )

    # Recompute the replicate stream with the same seed and read off the
    # endpoints by the claimed rule.
    rng = random.Random(7)
    treatment_runs = sorted(treatment)
    control_runs = sorted(control)

    def draw(runs: list[str], data: dict[str, list[float]]) -> list[float]:
        picked = [runs[rng.randrange(len(runs))] for _ in range(len(runs))]
        return [value for run in picked for value in data[run]]

    draws = sorted(
        stats.median(draw(treatment_runs, treatment))
        - stats.median(draw(control_runs, control))
        for _ in range(resamples)
    )
    tail = 0.025
    assert interval.low == draws[max(0, int(tail * resamples) - 1)]
    assert interval.high == draws[min(resamples - 1, int((1.0 - tail) * resamples))]


def test_the_two_conventions_really_can_disagree() -> None:
    """If this ever stops failing to agree, the guard below is vacuous."""
    disagreements = 0
    for trial in range(40):
        rng = random.Random(trial)
        clusters = rng.choice([4, 6, 9])
        treatment = {
            f"t{i}": [rng.gauss(100, 20) for _ in range(rng.choice([5, 10]))]
            for i in range(clusters)
        }
        control = {
            f"c{i}": [rng.gauss(80, 20) for _ in range(rng.choice([5, 10]))]
            for i in range(clusters)
        }
        new = cluster_bootstrap_median_difference(treatment, control)
        old_low, old_high = _stage2_convention(
            treatment,
            control,
            resamples=DEFAULT_RESAMPLES,
            seed=DEFAULT_BOOTSTRAP_SEED,
        )
        if abs(new.low - old_low) > 1e-12 or abs(new.high - old_high) > 1e-12:
            disagreements += 1
    assert disagreements > 0, (
        "the two conventions agreed everywhere, which would mean this test "
        "can no longer detect a convention change"
    )


def test_three_cluster_latency_shape_is_unaffected_by_the_move() -> None:
    """The published latency intervals do not move, and this says why.

    Three run clusters per arm is the shape behind ``\\BarrierCostLow`` and
    friends. At that shape the two conventions land on the same replicate, so
    the Stage 3 move republishes the Stage 2 numbers unchanged -- which the
    regenerated ``numbers.tex`` confirms independently.
    """
    rng = random.Random(4242)
    treatment = {f"t{i}": [rng.gauss(4005, 60) for _ in range(10)] for i in range(3)}
    control = {f"c{i}": [rng.gauss(2038, 25) for _ in range(10)] for i in range(3)}

    new = cluster_bootstrap_median_difference(treatment, control)
    old_low, old_high = _stage2_convention(
        treatment,
        control,
        resamples=DEFAULT_RESAMPLES,
        seed=DEFAULT_BOOTSTRAP_SEED,
    )
    assert new.low == pytest.approx(old_low, abs=1e-12)
    assert new.high == pytest.approx(old_high, abs=1e-12)


def test_defaults_are_the_ones_the_published_numbers_used() -> None:
    assert DEFAULT_RESAMPLES == 10_000
    assert DEFAULT_BOOTSTRAP_SEED == 20260806
