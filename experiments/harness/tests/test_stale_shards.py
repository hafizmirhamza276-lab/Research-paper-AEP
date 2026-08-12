"""A resumed run must not merge its own abandoned predecessor's events.

Found by the matrix. ``--resume`` re-runs anything without a parsing
``summary.json``, and such a run's directory still holds whatever its
interrupted attempt wrote. Shard names that the new attempt reuses are
overwritten; shards from *extra* worker lifetimes the old attempt needed and
the new one does not are left behind, and ``merge_event_shards`` merges every
shard it finds.

It surfaced loudly -- a run config digest mismatch, because the stale
``run_started`` record came from an older harness. Between two runs of the
*same* harness version it would have been silent, and the run's counts would
have been inflated by executions that were not part of it.
"""

from __future__ import annotations

import json

import pytest

from experiments.harness.config import RunConfig
from experiments.harness.runner import RunAborted, discard_stale_shards


def _config(tmp_path, **overrides) -> RunConfig:
    fields = {
        "run_id": "run-1",
        "seed": 1,
        "workers": 1,
        "executions_per_worker": 1,
        "endpoint": "payments",
        "mock_api_config_path": str(tmp_path / "mock.yaml"),
        "mock_api_base_url": "http://127.0.0.1:8099",
        "redis_url": "redis://127.0.0.1:6381/15",
        "results_root": str(tmp_path),
    }
    fields.update(overrides)
    return RunConfig(**fields)


def test_stale_shards_are_refused_and_preserved(tmp_path) -> None:
    config = _config(tmp_path)
    config.results_dir.mkdir(parents=True, exist_ok=True)

    # What an interrupted attempt leaves behind.
    (config.results_dir / "events-runner.jsonl").write_text("{}\n", encoding="utf-8")
    (config.results_dir / "events-worker-0-attempt-1.jsonl").write_text(
        "{}\n", encoding="utf-8"
    )
    (config.results_dir / "events-worker-0-attempt-3.jsonl").write_text(
        "{}\n", encoding="utf-8"
    )
    (config.results_dir / "events.jsonl").write_text("{}\n", encoding="utf-8")

    before = {path.name: path.read_bytes() for path in config.results_dir.iterdir()}
    with pytest.raises(RunAborted, match="results/voided"):
        discard_stale_shards(config)
    assert {path.name: path.read_bytes() for path in config.results_dir.iterdir()} == before


def test_a_stale_summary_is_refused_and_preserved_too(tmp_path) -> None:
    config = _config(tmp_path)
    config.results_dir.mkdir(parents=True, exist_ok=True)
    (config.results_dir / "summary.json").write_text(
        json.dumps({"agrees": True}), encoding="utf-8"
    )

    original = (config.results_dir / "summary.json").read_bytes()
    with pytest.raises(RunAborted, match="summary.json"):
        discard_stale_shards(config)
    assert (config.results_dir / "summary.json").read_bytes() == original


def test_the_provider_ledger_and_config_are_not_touched(tmp_path) -> None:
    """Only the run's own event stream is stale; its inputs are not.

    The rendered provider config and the ground-truth ledger are written by
    ``orchestrate.run_once`` *before* ``execute_run`` is called, so deleting
    them here would delete the oracle the run is about to be judged against.
    """
    config = _config(tmp_path)
    config.results_dir.mkdir(parents=True, exist_ok=True)
    for name in ("mock-api.yaml", "ground_truth.sqlite3", "run-config.json"):
        (config.results_dir / name).write_text("keep", encoding="utf-8")
    (config.results_dir / "events.jsonl").write_text("{}\n", encoding="utf-8")

    with pytest.raises(RunAborted):
        discard_stale_shards(config)

    for name in ("mock-api.yaml", "ground_truth.sqlite3", "run-config.json"):
        assert (config.results_dir / name).read_text(encoding="utf-8") == "keep"


def test_a_clean_directory_discards_nothing(tmp_path) -> None:
    config = _config(tmp_path)
    config.results_dir.mkdir(parents=True, exist_ok=True)
    assert discard_stale_shards(config) == []
