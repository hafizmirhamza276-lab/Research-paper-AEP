"""The matrix's cell identity is a compatibility contract, so it is a test.

A cell's key digests into its slug, the slug names its results directory, and
``--resume`` decides what to re-run by looking for that directory. So the key
is not an implementation detail: it is the thing that decides whether adding a
dimension costs nothing or costs four hours of recollection.

Session 3 collected 83 runs under a key of four fields. Amendments E1 and E2
add a fifth -- the regime -- and this module pins the seam that keeps those 83
runs identified: the regime contributes to the key only when it has a name, and
Session 3's regime is the one with the empty name.
"""

from __future__ import annotations

import pytest

from experiments.baselines.contract import SystemId
from experiments.mock_api.config import ReadbackKeying
from experiments.run_matrix import (
    REGIME_CRASH_ALWAYS,
    REGIME_NO_CRASH,
    REGIME_REDIS_KILL_INFLIGHT,
    REGIME_REDIS_KILL_PREACK,
    Cell,
    build_cells,
)

#: Run identifiers that exist on disk from Session 3 and the current session.
#: Hard-coded rather than read from a results directory: the point of the test
#: is to fail on a *source* change, on any machine, including one that has
#: never collected anything.
COLLECTED_RUN_IDS = (
    "aep_full-after_barrier_before_dispatch-payments-59673812-r0",
    "b0_naive_retry-after_barrier_before_dispatch-payments-3e961d07-r0",
    "b1_lease_only-after_barrier_before_dispatch-payments-a73d77a9-r0",
    "b2_cas_only-after_barrier_before_dispatch-payments-0e996445-r0",
    "b3_intent_no_barrier-after_barrier_before_dispatch-payments-d46fb584-r0",
    "b4_durable_workflow-after_barrier_before_dispatch-payments-11d6b7e1-r0",
)


def _cell(regime, **overrides) -> Cell:
    fields = {
        "system": SystemId.AEP_FULL,
        "crash_point": "mid_dispatch",
        "endpoint": "payments",
        "response_class": "AUTHORITATIVE_READBACK",
        "readback_keying": ReadbackKeying.CALLER_REFERENCE,
        "tier": 1,
        "applicable": True,
        "regime": regime,
    }
    fields.update(overrides)
    return Cell(**fields)


def test_the_session_three_regime_contributes_nothing_to_the_key() -> None:
    """The seam. Break this and 83 collected runs are re-run in silence."""
    cell = _cell(REGIME_CRASH_ALWAYS)
    assert cell.key == "AEP_FULL|mid_dispatch|payments|CALLER_REFERENCE"
    assert REGIME_CRASH_ALWAYS.name == ""


def test_every_other_regime_is_named_in_the_key() -> None:
    for regime in (
        REGIME_NO_CRASH,
        REGIME_REDIS_KILL_PREACK,
        REGIME_REDIS_KILL_INFLIGHT,
    ):
        assert regime.name, "a regime other than Session 3's must have a name"
        assert _cell(regime).key.endswith(f"|{regime.name}")


def test_regimes_cannot_collide_on_a_results_directory() -> None:
    slugs = [
        _cell(regime).slug
        for regime in (
            REGIME_CRASH_ALWAYS,
            REGIME_NO_CRASH,
            REGIME_REDIS_KILL_PREACK,
            REGIME_REDIS_KILL_INFLIGHT,
        )
    ]
    assert len(set(slugs)) == len(slugs)


@pytest.mark.parametrize("run_id", COLLECTED_RUN_IDS)
def test_already_collected_runs_are_still_identified(run_id: str) -> None:
    """Every run on disk must still be named by some cell of the new plan.

    A failure here does not mean the plan is wrong -- it means the plan will
    re-collect data it already has, which is a decision to take deliberately
    and record, not to discover six hours in.
    """
    planned = {f"{cell.slug}-r{repetition}" for cell in build_cells() for repetition in range(30)}
    assert run_id in planned


def test_the_whole_plan_has_no_duplicate_cell_keys() -> None:
    cells = build_cells()
    keys = [cell.key for cell in cells]
    assert len(set(keys)) == len(keys)
