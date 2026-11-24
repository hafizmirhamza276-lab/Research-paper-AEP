"""The replication set is 126 cells that no filter selects; this pins the flag.

Stage 3 collects a dataset defined as exactly 126 cells / 432 runs / 3,780
executions, matching the repository's historical collected matrix. The pilot
established that this set is unreachable with the CLI's own filters: it is a
subset at every tier (78 of 84, 2 of 10, 7 of 42, 39 of 42) and within every
regime, and the tightest filter its own value-sets imply admits 153 cells --
27 too many. Approximating it and hoping was the alternative.

``--cells-from`` reads the cell set out of the immutable plan whose SHA-256 is
already recorded in the replication amendment, so the shape collected and the
shape declared cannot drift apart. The tests below exist because every one of
these failure modes silently produces a *plausible* dataset of the wrong
shape, and a wrong denominator is not visible in any single run.

The seed test is the load-bearing one. Restricting the cell set must not
perturb the seed of any surviving cell -- ``cell_seed`` hashes
``(matrix_seed, cell.key, repetition)`` and nothing positional -- because the
84 surviving original runs are kept as corroboration precisely so the
replication can be compared against them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from experiments.run_matrix import (
    build_plan,
    cell_seed,
    load_cell_selection,
    resume_command_line,
)

#: The shape the 2026-08-13 replication plan declares. Frozen here rather than
#: read from the plan file, so that a corrupted plan fails these tests instead
#: of redefining what they check.
REPLICATION_CELLS = 126
REPLICATION_RUNS = 432
REPLICATION_EXECUTIONS = 3780

#: The tightest filter the 126 cells' own value-sets imply, measured during the
#: Prompt 3 pilot. It is recorded because it is the reason this flag exists: a
#: filter cannot express the set, so 27 surplus cells would be collected.
FILTER_ADMITS = 153

PLAN_PATH = Path("reports/stage3-replication-plan-2026-08-13.json")


def _default_arguments(**overrides) -> argparse.Namespace:
    """The CLI's defaults, which is what an unqualified run collects."""
    fields = {
        "regimes": None,
        "crash_probability": None,
        "endpoints": None,
        "systems": None,
        "crash_points": None,
        "keyings": None,
        "runs_per_cell": 3,
        "executions_per_run": 10,
        "workers": 2,
        "matrix_seed": 20260806,
        "results_root": "/tmp/unused-plan-only",
        "template": "experiments/configs/matrix.yaml",
        "redis_url": "redis://127.0.0.1:6381/15",
        "dataset_version": "unversioned",
        "run_order": "interleaved",
        "expected_appendfsync": "everysec",
        "max_tier": 5,
        "cells_from": None,
    }
    fields.update(overrides)
    return argparse.Namespace(**fields)


def _write_plan(tmp_path: Path, cells, **top) -> Path:
    document = {"cells": cells}
    document.update(top)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _selected_keys(count: int = REPLICATION_CELLS) -> list[str]:
    document = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    return [entry["cell_key"] for entry in document["cells"]][:count]


# --------------------------------------------- the shape the flag must produce


def test_selection_produces_exactly_the_declared_shape() -> None:
    """126 / 432 / 3,780. Any other triple is a different experiment."""
    plan = build_plan(_default_arguments(cells_from=str(PLAN_PATH)))

    assert len(plan.cells) == REPLICATION_CELLS
    assert len(plan.runs) == REPLICATION_RUNS
    assert sum(int(r["executions_per_run"]) for r in plan.runs) == (
        REPLICATION_EXECUTIONS
    )


def test_no_filter_combination_can_express_the_same_set() -> None:
    """If this ever stops being true, the flag has become unnecessary."""
    document = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    wanted = {entry["cell_key"] for entry in document["cells"]}

    every = build_plan(_default_arguments()).cells
    chosen = [cell for cell in every if cell.key in wanted]

    dimensions = [
        {cell.system.value for cell in chosen},
        {cell.regime.name or "(session-3)" for cell in chosen},
        {cell.crash_point for cell in chosen},
        {cell.response_class for cell in chosen},
        {cell.readback_keying.value for cell in chosen},
        {cell.endpoint for cell in chosen},
    ]
    admitted = [
        cell
        for cell in every
        if cell.system.value in dimensions[0]
        and (cell.regime.name or "(session-3)") in dimensions[1]
        and cell.crash_point in dimensions[2]
        and cell.response_class in dimensions[3]
        and cell.readback_keying.value in dimensions[4]
        and cell.endpoint in dimensions[5]
    ]

    assert len(admitted) == FILTER_ADMITS, (
        "the surplus a filter would collect changed. --cells-from exists "
        "because this number is not 126; if it is now 126, the historical "
        "matrix or the cell definitions moved."
    )
    assert len(admitted) > REPLICATION_CELLS


# ----------------------------------------------------------- the seed property


def test_restricting_the_cell_set_moves_no_surviving_seed() -> None:
    """Selection must be a filter, not a re-seed.

    A failure here does not mean the selection is wrong -- it means the 84
    surviving original runs can no longer be compared against the
    replication, which is the entire reason they were kept.
    """
    full = build_plan(_default_arguments())
    restricted = build_plan(_default_arguments(cells_from=str(PLAN_PATH)))

    full_seeds = {(r["cell_key"], r["repetition"]): r["seed"] for r in full.runs}
    for run in restricted.runs:
        key = (run["cell_key"], run["repetition"])
        assert run["seed"] == full_seeds[key], (
            f"seed for {key} moved when the cell set was restricted. Seeds "
            f"must depend only on (matrix_seed, cell.key, repetition)."
        )


def test_selected_seeds_match_the_plan_file_that_selected_them() -> None:
    """The plan's own seed list and the harness must agree, cell by cell."""
    document = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    plan = build_plan(_default_arguments(cells_from=str(PLAN_PATH)))
    by_key = {cell.key: cell for cell in plan.cells}

    for entry in document["cells"]:
        cell = by_key[entry["cell_key"]]
        for repetition, declared in enumerate(entry["seeds"]):
            assert cell_seed(document["matrix_seed"], cell, repetition) == declared


# ------------------------------------------------------------- the refusals


def test_a_cell_the_matrix_does_not_have_is_refused(tmp_path: Path) -> None:
    """Naming a cell that cannot be built is fatal, not a silent 125."""
    path = _write_plan(tmp_path, [{"cell_key": "NO_SUCH|cell|key|CALLER_REFERENCE"}])

    with pytest.raises(SystemExit, match="not available"):
        build_plan(_default_arguments(cells_from=str(path)))


def test_a_repeated_cell_key_is_refused(tmp_path: Path) -> None:
    """A duplicate would collapse into one cell and understate the total."""
    key = _selected_keys(1)[0]
    path = _write_plan(tmp_path, [{"cell_key": key}, {"cell_key": key}])

    with pytest.raises(SystemExit, match="repeats cell key"):
        build_plan(_default_arguments(cells_from=str(path)))


def test_a_plan_that_contradicts_its_own_totals_is_refused(tmp_path: Path) -> None:
    """Per-cell runs and planned_totals are two statements of one fact."""
    keys = _selected_keys(2)
    path = _write_plan(
        tmp_path,
        [{"cell_key": k, "runs": 3} for k in keys],
        planned_totals={"cells": 2, "runs": 99},
    )

    with pytest.raises(SystemExit, match="cells sum to"):
        build_plan(_default_arguments(cells_from=str(path)))


def test_a_declared_cell_count_that_disagrees_is_refused(tmp_path: Path) -> None:
    keys = _selected_keys(2)
    path = _write_plan(
        tmp_path,
        [{"cell_key": k} for k in keys],
        planned_totals={"cells": 7, "runs": 6},
    )

    with pytest.raises(SystemExit, match="declares 7 cells but lists 2"):
        build_plan(_default_arguments(cells_from=str(path)))


def test_a_cell_dropped_after_selection_is_refused(tmp_path: Path) -> None:
    """--max-tier can silently remove a selected cell. It must not."""
    with pytest.raises(SystemExit, match="planned .* runs but"):
        build_plan(
            _default_arguments(cells_from=str(PLAN_PATH), max_tier=1)
        )


def test_an_absent_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="cannot read"):
        build_plan(_default_arguments(cells_from=str(tmp_path / "nope.json")))


def test_a_file_that_is_not_json_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    path.write_text("this is not json", encoding="utf-8")

    with pytest.raises(SystemExit, match="not valid JSON"):
        build_plan(_default_arguments(cells_from=str(path)))


def test_a_plan_with_no_cells_array_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"planned_totals": {"cells": 0}}), encoding="utf-8")

    with pytest.raises(SystemExit, match="no non-empty 'cells' array"):
        build_plan(_default_arguments(cells_from=str(path)))


def test_a_cell_entry_without_a_key_is_refused(tmp_path: Path) -> None:
    path = _write_plan(tmp_path, [{"cell_slug": "readable-but-not-a-key"}])

    with pytest.raises(SystemExit, match="has no 'cell_key'"):
        build_plan(_default_arguments(cells_from=str(path)))


# ------------------------------------------------------------- the provenance


def test_the_plan_records_which_file_selected_its_cells() -> None:
    """A dataset that cannot say what selected it cannot be reproduced."""
    selection = load_cell_selection(PLAN_PATH)
    echo = build_plan(_default_arguments(cells_from=str(PLAN_PATH))).echo()

    assert echo["cells_from"]["sha256"] == selection.sha256
    assert len(echo["cells_from"]["sha256"]) == 64
    assert echo["cells_from"]["declared_cells"] == REPLICATION_CELLS
    assert echo["cells_from"]["declared_runs"] == REPLICATION_RUNS


def test_an_unselected_plan_records_no_selection() -> None:
    """The field is absent-as-None, so old plans stay legible."""
    assert build_plan(_default_arguments()).echo()["cells_from"] is None


# ------------------------------------------------------- the resume command


def test_the_printed_resume_command_carries_what_collection_requires() -> None:
    """It failed as printed: the parser rejects a resume with no --git-sha."""
    arguments = _default_arguments(
        cells_from=str(PLAN_PATH),
        dataset_version="stage3-2026-08-13-replication-1",
    )
    arguments.git_sha = "a" * 40
    arguments.experiment_plan_sha256 = "b" * 64

    line = resume_command_line("/var/tmp/root", arguments)

    assert "--resume" in line
    assert "--results-root /var/tmp/root" in line
    assert f"--git-sha {'a' * 40}" in line
    assert f"--experiment-plan-sha256 {'b' * 64}" in line
    assert f"--cells-from {PLAN_PATH}" in line
    assert "--dataset-version stage3-2026-08-13-replication-1" in line


def test_the_resume_command_omits_the_selection_when_there_is_none() -> None:
    """Resuming a full-matrix run must not invent a cell selection."""
    arguments = _default_arguments()
    arguments.git_sha = "a" * 40
    arguments.experiment_plan_sha256 = "b" * 64

    assert "--cells-from" not in resume_command_line("/var/tmp/root", arguments)
