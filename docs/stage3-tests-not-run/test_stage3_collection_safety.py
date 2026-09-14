"""Stage 3 experiment-shape, resumption, and preservation gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.baselines.contract import SystemId
from experiments.mock_api.config import ReadbackKeying
from experiments.run_matrix import (
    MatrixPlan,
    REGIME_REDIS_KILL_PREACK,
    archive_voided_attempt,
    build_cells,
    inspect_run_attempt,
    persist_plan,
)


def _entry(run_id: str = "stage3-r0") -> dict[str, object]:
    return {
        "run_id": run_id,
        "dataset_version": "stage3-test",
        "seed": 1234,
        "system": "AEP_FULL",
        "endpoint": "payments",
        "readback_keying": "CALLER_REFERENCE",
        "crash_probability": 0.0,
        "redis_kill_point": None,
        "redis_kill_delay_ms": 0,
        "redis_kill_executions": 0,
        "executions_per_run": 10,
    }


def _plan(*, runs_per_cell: int = 9) -> MatrixPlan:
    return MatrixPlan(
        cells=(),
        runs_per_cell=runs_per_cell,
        executions_per_run=10,
        workers=2,
        matrix_seed=20260812,
        results_root="unused",
        template="experiments/configs/matrix.yaml",
        redis_url="redis://127.0.0.1:6381/15",
        dataset_version="stage3-test",
        run_order="interleaved",
        expected_appendfsync="everysec",
    )


def test_b2_preack_design_exposes_both_missing_capability_classes() -> None:
    cells = build_cells(
        systems=(SystemId.AEP_FULL, SystemId.B3_INTENT_NO_BARRIER),
        endpoints=(
            ("payments", "AUTHORITATIVE_READBACK"),
            ("notifications", "POSITIVE_ONLY_READBACK"),
        ),
        keyings=(ReadbackKeying.CALLER_REFERENCE,),
        regimes=(REGIME_REDIS_KILL_PREACK,),
    )
    assert len(cells) == 4
    assert {cell.response_class for cell in cells} == {
        "AUTHORITATIVE_READBACK",
        "POSITIVE_ONLY_READBACK",
    }
    assert REGIME_REDIS_KILL_PREACK.runs_per_cell == 30
    assert REGIME_REDIS_KILL_PREACK.executions_per_run == 1
    assert REGIME_REDIS_KILL_PREACK.workers == 1


def test_finalized_result_root_plan_cannot_be_overwritten(tmp_path: Path) -> None:
    root = tmp_path / "results"
    plan = _plan()
    persist_plan(root, plan, "plan nine")

    with pytest.raises(SystemExit, match="differs"):
        persist_plan(root, _plan(runs_per_cell=8), "plan eight")

    assert json.loads((root / "matrix-plan.json").read_text())["runs_per_cell"] == 9
    assert (root / "matrix-plan.txt").read_text() == "plan nine\n"


def test_resume_archives_original_bytes_and_machine_reason(tmp_path: Path) -> None:
    entry = _entry()
    run = tmp_path / str(entry["run_id"])
    run.mkdir()
    originals = {
        "events-runner.jsonl": b'{"event":"run_started"}\n',
        "provider.log": b"original provider bytes\n",
    }
    for name, payload in originals.items():
        (run / name).write_bytes(payload)

    state, details = inspect_run_attempt(str(tmp_path), entry)
    assert state == "incomplete"
    destination = archive_voided_attempt(
        str(tmp_path),
        entry,
        reason_code="resume-incomplete",
        reason="interrupted infrastructure attempt",
        details=details,
    )

    assert destination is not None
    assert not run.exists()
    assert {path.name: path.read_bytes() for path in destination.iterdir()} == originals
    reason = json.loads((destination.parent / f"{destination.name}.void.json").read_text())
    assert reason["reason_code"] == "resume-incomplete"
    assert reason["status"] == "void"
    assert len(reason["source_raw_directory_hash"]) == 64
    assert len((destination.parent / "MANIFEST.jsonl").read_text().splitlines()) == 1


def test_resume_rejects_a_completed_run_with_different_seed(tmp_path: Path) -> None:
    entry = _entry()
    run = tmp_path / str(entry["run_id"])
    run.mkdir()
    (run / "summary.json").write_text("{}", encoding="utf-8")
    config = {
        **entry,
        "seed": 9999,
        "workers": 2,
        "executions_per_worker": 5,
    }
    (run / "run-config.json").write_text(json.dumps(config), encoding="utf-8")

    state, details = inspect_run_attempt(str(tmp_path), entry)
    assert state == "configuration-mismatch"
    assert details["mismatches"]["seed"] == {
        "expected": 1234,
        "observed": 9999,
    }
