"""The order runs are executed in, which Phase 8.4 discovered is load-bearing.

The matrix collects each cell as a block of consecutive repetitions, and the
harness's ``docker kill`` latency drifts monotonically upward within a session
(Phase 8.4 session 1: Spearman 0.703 over 120 runs, block medians rising from
829 to 2176 ms). Those two facts together make one arm of any paired comparison
always the earlier block and the other always the later one -- so the treatment
and the drift are *perfectly collinear*, and no amount of covariate adjustment
or extra sessions can separate them.

Interleaving at run level is the fix, and the property that makes it safe is
that ordering contributes to nothing else: a run's identity and its seed are
derived from the cell and the repetition, never from position. These tests pin
both halves -- that the interleaving happens, and that it changed nothing else.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from experiments.run_matrix import DEFAULT_TEMPLATE, build_plan


def arguments(**overrides) -> SimpleNamespace:
    defaults = dict(
        regimes=["redis-kill-preack"],
        crash_probability=None,
        endpoints=None,
        keyings=None,
        systems=None,
        crash_points=None,
        matrix_seed=20260806,
        results_root="experiments/results/ordering-test",
        template=DEFAULT_TEMPLATE,
        redis_url="redis://127.0.0.1:6381/15",
        runs_per_cell=3,
        executions_per_run=10,
        workers=2,
        max_tier=4,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_the_paired_arms_alternate_run_by_run() -> None:
    """The property session 1 needed and did not have.

    With the cell-major order this regime produced 30 consecutive
    ``ledger_postings`` runs followed by 30 consecutive ``payments`` runs, so
    the second arm was collected roughly 18 minutes later than the first under
    a monotonically drifting fault. Alternating draws both arms from the same
    part of the drift, whatever shape the drift has -- which is why this is
    preferable to counterbalancing whole cells across sessions.
    """
    runs = build_plan(arguments()).runs
    assert runs, "the regime must plan some runs"

    # Within one system, consecutive runs must not repeat the same endpoint.
    aep = [r for r in runs if r["system"] == "AEP_FULL"]
    endpoints = [r["endpoint"] for r in aep]
    repeats = [
        (i, endpoints[i])
        for i in range(1, len(endpoints))
        if endpoints[i] == endpoints[i - 1]
    ]
    assert not repeats, f"arms did not alternate at positions {repeats}"


def test_every_cell_finishes_a_repetition_before_any_cell_starts_the_next() -> None:
    """Run-major, not cell-major: the ordering invariant stated directly."""
    runs = build_plan(arguments()).runs
    repetitions = [r["repetition"] for r in runs]
    assert repetitions == sorted(repetitions), (
        "repetition must be the outer sort key, or an arm can still be "
        "collected as one consecutive block"
    )


def test_interleaving_changes_no_run_identity_and_no_seed() -> None:
    """The whole safety argument for fixing this with a sort key.

    ``run_id`` is ``cell.slug``-``repetition`` and ``cell_seed`` digests
    ``matrix_seed``, ``MATRIX_VERSION``, ``cell.key`` and ``repetition``.
    Neither reads position, so re-ordering must be a pure permutation: the same
    runs, the same seeds, in a different sequence. If this ever fails, the
    ordering change has become a re-collection.
    """
    runs = build_plan(arguments()).runs
    identity = {(r["run_id"], r["seed"], r["cell_key"]) for r in runs}

    # The order the matrix used before Phase 8.4, reconstructed by sorting.
    cell_major = sorted(
        runs, key=lambda e: (e["tier"], e["cell_key"], e["repetition"])
    )
    assert {(r["run_id"], r["seed"], r["cell_key"]) for r in cell_major} == identity
    assert len(cell_major) == len(runs)


def test_the_run_set_is_unchanged_for_the_frozen_session_three_regime() -> None:
    """The 432-run matrix must not be re-identified by this change.

    Phase 8.4 changes execution order for every regime, including the one the
    frozen corpus was collected under. That is intended -- drift protection is
    not specific to the paired design -- but it must remain *only* order.
    """
    runs = build_plan(arguments(regimes=["session-3"], runs_per_cell=3)).runs
    assert runs
    assert len({r["run_id"] for r in runs}) == len(runs)
    for run in runs:
        assert run["run_id"].endswith(f"-r{run['repetition']}")
