"""The matrix definition changed shape; these pin what may and may not move.

Between Stage 2 (``c2fffa6``) and the Stage 3 preparation the default matrix
went from 302 cells / 1,068 runs to 304 cells / 1,128 runs, because the
``redis-kill-preack`` regime gained the ``notifications``
(``POSITIVE_ONLY_READBACK``) endpoint that B2 needs. That change is wanted.
What was missing is any record that it happened: ``MATRIX_VERSION`` read
``aep.matrix/1`` on both sides, so a plan generated after the change was
indistinguishable from one generated before it.

The obvious fix -- bump ``MATRIX_VERSION`` -- is a trap, and the second test
below is what makes it a failing trap rather than a silent one. That string is
hashed into every cell seed, so bumping it re-seeds all 1,128 runs, including
the 252 session-3 cells a replication is meant to reproduce. The seeds are
therefore pinned against the values Stage 2 produced, and the *definition*
carries its own version.
"""

from __future__ import annotations

import argparse
import hashlib

from experiments.mock_api.config import ReadbackKeying
from experiments.run_matrix import (
    MATRIX_DEFINITION_SHAPES,
    MATRIX_DEFINITION_VERSION,
    MATRIX_SEED_NAMESPACE,
    MATRIX_VERSION,
    REGIME_REDIS_KILL_PREACK,
    build_cells,
    build_plan,
    cell_seed,
)

#: The seed digest over every cell at three repetitions, computed on this
#: definition. Its counterpart on ``c2fffa6`` -- over the 302 cells that
#: definition contains -- is
#: ``e9a50bf686229ba4b6d454c64b859850483ac24769211ccef6cc619daeb87651``.
#: The two differ only by the two added cells; every shared cell's seed is
#: identical, which is what ``test_added_cells_did_not_reseed_existing_ones``
#: checks directly.
GOLDEN_SEED_DIGEST = (
    "68543f9d8d68141a4e5d7c95dc74dbe0aaa10dc5dd49b9eb9aff18b27bb5f8c2"
)

#: Individual seeds, recomputed from ``c2fffa6`` during the Stage 3 audit.
#: Spelled out as well as digested because a digest tells you something moved
#: and these tell you what.
GOLDEN_CELL_SEEDS = {
    "AEP_FULL|after_barrier_before_dispatch|ledger_postings|CALLER_REFERENCE": 1960949317,
    "AEP_FULL|after_barrier_before_dispatch|ledger_postings|ORACLE_FINGERPRINT": 114242820,
    "AEP_FULL|after_barrier_before_dispatch|notifications|CALLER_REFERENCE": 487175073,
    "AEP_FULL|after_barrier_before_dispatch|notifications|ORACLE_FINGERPRINT": 1801171484,
    "AEP_FULL|after_barrier_before_dispatch|payments|CALLER_REFERENCE": 2109461321,
    "AEP_FULL|after_barrier_before_dispatch|payments|ORACLE_FINGERPRINT": 830607293,
}

MATRIX_SEED = 20260806


def _default_arguments() -> argparse.Namespace:
    """The CLI's defaults, which is what an unqualified run collects."""
    return argparse.Namespace(
        regimes=None,
        crash_probability=None,
        endpoints=None,
        systems=None,
        crash_points=None,
        keyings=None,
        runs_per_cell=3,
        executions_per_run=10,
        workers=2,
        matrix_seed=MATRIX_SEED,
        results_root="/tmp/unused-plan-only",
        template="experiments/configs/matrix.yaml",
        redis_url="redis://127.0.0.1:6381/15",
        dataset_version="unversioned",
        run_order="interleaved",
        expected_appendfsync="everysec",
        max_tier=5,
    )


def test_seed_namespace_is_frozen() -> None:
    """It is hashed into every seed, so it is not a place to record changes."""
    assert MATRIX_SEED_NAMESPACE == "aep.matrix/1"
    assert MATRIX_VERSION == MATRIX_SEED_NAMESPACE


def test_cell_seeds_match_the_values_stage_2_produced() -> None:
    by_key = {cell.key: cell for cell in build_cells()}
    for key, expected in GOLDEN_CELL_SEEDS.items():
        assert key in by_key, f"cell disappeared from the matrix: {key}"
        assert cell_seed(MATRIX_SEED, by_key[key], 0) == expected, (
            f"seed for {key} moved. If this was deliberate it is a new "
            f"dataset, not a new matrix definition."
        )


def test_added_cells_did_not_reseed_existing_ones() -> None:
    cells = sorted(build_cells(), key=lambda cell: cell.key)
    material = "".join(
        f"{cell.key}:{repetition}:{cell_seed(MATRIX_SEED, cell, repetition)};"
        for cell in cells
        for repetition in range(3)
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    assert digest == GOLDEN_SEED_DIGEST, (
        "the seed stream over the whole matrix changed. Adding cells must not "
        "move any other cell's seed; changing MATRIX_SEED_NAMESPACE moves all "
        "of them."
    )


def test_definition_version_matches_the_shape_it_claims() -> None:
    plan = build_plan(_default_arguments())
    expected = MATRIX_DEFINITION_SHAPES[MATRIX_DEFINITION_VERSION]
    assert len(plan.cells) == expected["cells"]
    assert len(plan.runs) == expected["runs"]


def test_definition_two_is_definition_one_plus_the_two_b2_cells() -> None:
    """The delta is additive and is exactly the POSITIVE_ONLY_READBACK pair."""
    one = MATRIX_DEFINITION_SHAPES["aep.matrix-definition/1"]
    two = MATRIX_DEFINITION_SHAPES["aep.matrix-definition/2"]
    assert two["cells"] - one["cells"] == 2
    assert two["runs"] - one["runs"] == 2 * REGIME_REDIS_KILL_PREACK.runs_per_cell

    preack = [
        cell
        for cell in build_cells()
        if cell.regime.name == REGIME_REDIS_KILL_PREACK.name
    ]
    added = [cell for cell in preack if cell.endpoint == "notifications"]
    assert len(added) == 2, "B2's POSITIVE_ONLY_READBACK cells are missing"
    assert {cell.system.value for cell in added} == {
        "AEP_FULL",
        "B3_INTENT_NO_BARRIER",
    }
    assert {cell.readback_keying for cell in added} == {
        ReadbackKeying.CALLER_REFERENCE
    }


def test_plan_records_the_definition_version() -> None:
    echo = build_plan(_default_arguments()).echo()
    assert echo["matrix_definition_version"] == MATRIX_DEFINITION_VERSION
    assert echo["matrix_version"] == MATRIX_SEED_NAMESPACE
