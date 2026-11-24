"""The run configuration, and the two things it is not allowed to permit.

Amendment C2: *"Every harness-driven run -- including every crash point --
executes the workflow in EVALUATION mode with no test flags."* A configuration
is the only place that could quietly reintroduce a TEST-mode measurement, so it
refuses to describe one at all.

Amendment C4: the configuration is echoed verbatim into every run's
``events.jsonl``, and carries a digest so two runs can be compared without
comparing prose.
"""

from __future__ import annotations

import json

import pytest

from aep_core.core.intent_workflow import DispatchMode
from experiments.mock_api.config import ReadbackKeying
from experiments.harness.config import (
    RunConfig,
    load_run_config,
    run_config_from_mapping,
)


def base(**overrides) -> RunConfig:
    defaults = dict(
        run_id="run-test",
        seed=20260805,
        workers=2,
        executions_per_worker=3,
        endpoint="payments",
        mock_api_config_path="experiments/results/mock-api.yaml",
        mock_api_base_url="http://127.0.0.1:8099",
        redis_url="redis://127.0.0.1:6381/15",
        results_root="experiments/results",
    )
    defaults.update(overrides)
    return RunConfig(**defaults)


# ===========================================================================
# EVALUATION mode is not negotiable
# ===========================================================================


def test_the_default_dispatch_mode_is_evaluation():
    assert base().dispatch_mode is DispatchMode.EVALUATION


@pytest.mark.parametrize("refused", [DispatchMode.TEST, DispatchMode.PRODUCTION])
def test_no_other_dispatch_mode_can_be_configured(refused):
    """TEST because C2 forbids it; PRODUCTION because this repo ships no
    production vault or connector, so it could only fail closed at run time."""
    with pytest.raises(ValueError) as rejected:
        base(dispatch_mode=refused)

    assert "EVALUATION" in str(rejected.value)


def test_the_configuration_names_no_test_flag_at_all():
    """A structural check on the dataclass, not on one instance."""
    fields = set(RunConfig.__dataclass_fields__)

    assert not [name for name in fields if "allow_test" in name or "test_only" in name]


# ===========================================================================
# Validation
# ===========================================================================


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workers", 0),
        ("executions_per_worker", 0),
        ("crash_probability", 1.5),
        ("crash_probability", -0.1),
        ("crash_delay_ms", -1),
        ("poisoned_executions", -1),
    ],
)
def test_an_impossible_run_is_refused_before_anything_is_spawned(field, value):
    with pytest.raises(ValueError):
        base(**{field: value})


def test_a_timing_policy_that_violates_the_timeout_invariant_is_refused():
    """T_client <= T_lock - Buffer, checked here rather than in a worker."""
    with pytest.raises(ValueError) as rejected:
        base(client_timeout_seconds=30.0, lock_ttl_seconds=30, buffer_margin_seconds=15)

    assert "T_client" in str(rejected.value)


def test_a_misspelled_crash_point_is_refused_by_the_configuration():
    with pytest.raises(KeyError):
        base(crash_point="mid-dispatch")


def test_the_six_roadmap_crash_points_are_all_accepted():
    for name in (
        "before_intent_write",
        "after_intent_before_barrier",
        "after_barrier_before_dispatch",
        "mid_dispatch",
        "after_response_before_resolution",
        "after_resolution_before_barrier",
    ):
        assert base(crash_point=name).resolved_crash_point is not None


def test_no_crash_point_is_a_valid_run():
    """The control arm of every comparison."""
    assert base(crash_point=None).resolved_crash_point is None


# ===========================================================================
# The echo, and the digest
# ===========================================================================


def test_the_echo_is_json_serialisable_and_carries_the_measurement_decisions():
    echo = base(crash_point="mid_dispatch").echo()

    json.dumps(echo)
    assert echo["dispatch_mode"] == "EVALUATION"
    assert echo["readback_keying"] == "CALLER_REFERENCE"
    assert echo["crash_point"] == "mid_dispatch"
    assert echo["resolved_crash_point"] == "AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION"
    assert echo["seed"] == 20260805
    assert "config_digest" in echo


def test_the_digest_changes_when_a_measurement_decision_changes():
    caller = base(readback_keying=ReadbackKeying.CALLER_REFERENCE)
    oracle = base(readback_keying=ReadbackKeying.ORACLE_FINGERPRINT)

    assert caller.config_digest != oracle.config_digest


def test_the_digest_ignores_where_the_results_happen_to_be_written():
    """Two runs of one configuration in two directories are one configuration."""
    assert (
        base(results_root="/tmp/a").config_digest
        == base(results_root="/tmp/b").config_digest
    )


def test_the_digest_is_stable_across_processes():
    """Recomputed from the echo, so a worker and the runner agree."""
    assert base().config_digest == base().config_digest


# ===========================================================================
# Round-tripping through disk, which is how workers receive it
# ===========================================================================


def test_a_configuration_round_trips_through_json(tmp_path):
    original = base(crash_point="mid_dispatch", crash_probability=0.5)
    path = tmp_path / "run-config.json"
    path.write_text(json.dumps(original.echo()), encoding="utf-8")

    restored = load_run_config(path)

    assert restored.config_digest == original.config_digest
    assert restored.resolved_crash_point is original.resolved_crash_point


def test_an_unknown_key_in_a_saved_configuration_is_refused(tmp_path):
    """A stale field silently ignored would misdescribe the run it produced."""
    document = base().echo()
    document["experimental_knob"] = True
    path = tmp_path / "run-config.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError) as refused:
        load_run_config(path)

    assert "experimental_knob" in str(refused.value)


# ===========================================================================
# Derived values the runner and workers both depend on
# ===========================================================================


def test_the_connector_policy_comes_from_the_configuration():
    policy = base(client_timeout_seconds=4.0, lock_ttl_seconds=25).policy()

    assert policy.client_timeout_seconds == 4.0
    assert policy.lock_ttl_seconds == 25


def test_the_results_directory_is_per_run():
    assert base(run_id="run-a").results_dir != base(run_id="run-b").results_dir


def test_the_total_execution_count_is_workers_times_executions():
    assert base(workers=3, executions_per_worker=10).total_executions == 30


# ===========================================================================
# Phase 8.2: detected environment, and why it must stay out of the digest
# ===========================================================================


def test_the_environment_is_echoed_but_not_digested() -> None:
    """The frozen corpus depends on this, and it is not a stylistic choice.

    ``run_config_from_mapping`` re-verifies the digest whenever a saved
    configuration is parsed. If the detected environment entered the digested
    body, then every one of the 432 already-frozen runs -- written before the
    field existed -- would compute a different digest on the next read and
    raise. The field would have made the historical record unreadable in the
    act of describing it better.

    It is also the right answer on the merits: two runs that differ only in
    where Docker happened to place a volume are the same configuration
    observed twice, not two configurations.
    """
    config = base()
    echoed = config.echo()
    assert "environment" in echoed
    assert "results_root_filesystem" in echoed["environment"]
    assert "redis_storage_backing" in echoed["environment"]

    body_without = {
        key: value for key, value in echoed.items()
        if key not in {"config_digest", "environment"}
    }
    stripped = dict(body_without)
    stripped["config_digest"] = config.config_digest
    # The digest is over the body alone: re-deriving it from a mapping that
    # never carried an environment must give the same answer.
    assert run_config_from_mapping(stripped).config_digest == config.config_digest


def test_a_configuration_saved_before_the_field_existed_still_parses() -> None:
    """Forward compatibility in the direction that actually happened."""
    echoed = base().echo()
    legacy = {key: value for key, value in echoed.items() if key != "environment"}
    restored = run_config_from_mapping(legacy)
    assert restored.config_digest == echoed["config_digest"]


def test_an_unknown_key_is_still_refused() -> None:
    """Widening `derived` must not have widened it into a hole."""
    echoed = base().echo()
    echoed["some_field_nobody_declared"] = 1
    with pytest.raises(ValueError, match="unknown key"):
        run_config_from_mapping(echoed)
