"""Stage 3's provenance fields, the run-config version boundary, and the
host snapshot -- the three preparation changes that had no direct coverage.

The Stage 3 preparation bumped ``RUN_CONFIG_VERSION`` to
``aep.harness.run-config/2`` and added six provenance fields. It also made the
configuration digest skip those fields when they are absent, which is the
compatibility seam that lets a Stage 1 run-config/1 record keep the digest it
was collected under. A seam like that is only safe while something checks both
of its sides, and nothing did.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.harness.config import (
    RUN_CONFIG_VERSION,
    RunConfig,
    load_run_config,
)
from experiments.harness.runner import (
    _available_memory_bytes,
    _filesystem_type,
    host_environment_snapshot,
)

STAGE3_PROVENANCE_FIELDS = (
    "dataset_version",
    "experiment_plan_sha256",
    "git_sha",
    "redis_durability",
    "redis_version",
    "redis_image",
)


def _config(**overrides: object) -> RunConfig:
    base: dict[str, object] = {
        "run_id": "stage3-provenance",
        "seed": 4242,
        "workers": 2,
        "executions_per_worker": 3,
        "endpoint": "payments",
        "mock_api_config_path": "experiments/results/mock-api.yaml",
        "mock_api_base_url": "http://127.0.0.1:8099",
        "redis_url": "redis://127.0.0.1:6381/15",
        "results_root": "experiments/results",
    }
    base.update(overrides)
    return RunConfig(**base)  # type: ignore[arg-type]


# --- item 1: the run-config version boundary ---------------------------------


def test_the_version_states_the_stage_three_boundary() -> None:
    assert RUN_CONFIG_VERSION == "aep.harness.run-config/2"


def test_provenance_fields_default_to_absent() -> None:
    """Absent, not empty-string: a run-config/1 record simply lacks them."""
    config = _config()
    for field in STAGE3_PROVENANCE_FIELDS:
        assert getattr(config, field) is None, field


def test_absent_provenance_leaves_the_run_config_one_digest_intact() -> None:
    """The compatibility seam, from the side that must not move.

    A configuration carrying none of the new fields must digest to exactly
    what it digested before they existed, or every Stage 1 run in the raw
    archive fails its own configuration check on re-analysis.
    """
    without = _config().config_digest
    explicit_nones = _config(
        **{field: None for field in STAGE3_PROVENANCE_FIELDS}
    ).config_digest
    assert without == explicit_nones


@pytest.mark.parametrize("field", STAGE3_PROVENANCE_FIELDS)
def test_each_provenance_field_binds_into_the_digest(field: str) -> None:
    """The seam from the other side: a supplied field is bound, not ignored.

    Data collected under a different frozen plan, Git tree, or Redis image is
    not the same experimental configuration, and the digest is what says so.
    """
    baseline = _config().config_digest
    bound = _config(**{field: "stage3-value"}).config_digest
    assert bound != baseline, f"{field} is not bound into the digest"


def test_two_different_plans_do_not_share_a_digest() -> None:
    first = _config(experiment_plan_sha256="a" * 64).config_digest
    second = _config(experiment_plan_sha256="b" * 64).config_digest
    assert first != second


def test_provenance_survives_a_json_round_trip(tmp_path: Path) -> None:
    original = _config(
        dataset_version="stage3-replication-1",
        experiment_plan_sha256="c" * 64,
        git_sha="0123456789abcdef",
        redis_durability="everysec",
        redis_version="7.2.5",
        redis_image="redis:7.2.5-alpine@sha256:6aaf3f5e",
    )
    path = tmp_path / "run-config.json"
    path.write_text(json.dumps(original.echo()), encoding="utf-8")
    restored = load_run_config(path)
    assert restored.config_digest == original.config_digest
    for field in STAGE3_PROVENANCE_FIELDS:
        assert getattr(restored, field) == getattr(original, field)


# --- item 3: the host snapshot and its platform fallbacks --------------------


def test_host_snapshot_records_what_a_replication_needs(tmp_path: Path) -> None:
    snapshot = host_environment_snapshot(tmp_path)
    for key in (
        "captured_at_utc",
        "platform",
        "python",
        "cpu_count",
        "load_average_1m_5m_15m",
        "results_disk_free_bytes",
        "results_disk_total_bytes",
        "has_sigkill",
        "kill_mechanism",
    ):
        assert key in snapshot, key
    assert snapshot["results_disk_total_bytes"] > 0
    assert snapshot["kill_mechanism"] in {"SIGKILL", "TerminateProcess"}


def test_host_snapshot_is_json_serialisable(tmp_path: Path) -> None:
    """It is written into a run record, so it has to survive being one."""
    json.dumps(host_environment_snapshot(tmp_path))


def test_memory_probe_falls_back_rather_than_raising(monkeypatch) -> None:
    """No /proc/meminfo is a missing reading, not a failed run."""
    def explode(*_args: object, **_kwargs: object) -> str:
        raise OSError("no /proc on this platform")

    monkeypatch.setattr(Path, "read_text", explode)
    assert _available_memory_bytes() is None


def test_filesystem_probe_falls_back_rather_than_raising(
    monkeypatch, tmp_path: Path
) -> None:
    def explode(*_args: object, **_kwargs: object) -> str:
        raise OSError("no /proc on this platform")

    monkeypatch.setattr(Path, "read_text", explode)
    assert _filesystem_type(tmp_path) is None


def test_filesystem_probe_prefers_the_longest_matching_mount(
    monkeypatch, tmp_path: Path
) -> None:
    """A results root under /mnt/d must not be reported as ``/``.

    The distinction is the one Stage 3's host gate turns on: a native Linux
    filesystem and a Windows mount are both mounts, and only the longest match
    identifies which one the evidence is actually landing on.
    """
    resolved = tmp_path.resolve().as_posix()
    fake_mounts = (
        "/dev/sdf / ext4 rw,relatime 0 0\n"
        f"drvfs {resolved} 9p rw,relatime 0 0\n"
    )
    monkeypatch.setattr(
        Path, "read_text", lambda self, **_kwargs: fake_mounts
    )
    assert _filesystem_type(tmp_path) == "9p"
