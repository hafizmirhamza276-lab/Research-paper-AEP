"""The configurable fault surface, and the echo that makes a run unambiguous.

PAPER_ROADMAP.md section 3.1(1) requires the mock API to be configurable in
five dimensions. A result collected against an unknown configuration is not a
result, so this module also pins the two properties that make a run
self-describing: the loaded configuration echoes in full, and the echo carries
a digest that changes whenever any knob does.
"""

from __future__ import annotations

import random

import pytest
import yaml

from aep_core.core.connector_contract import ReconciliationCapability
from experiments.mock_api.config import (
    ConfigError,
    DelayDistribution,
    MockApiConfig,
    load_config,
)

MINIMAL = {
    "config_version": "aep.mock-legacy-api.config/1",
    "seed": 20260805,
    "endpoints": {
        "payments": {
            "response_class": "AUTHORITATIVE_READBACK",
            "identity_fields": ["action", "amount_minor"],
        }
    },
}


def write(tmp_path, document) -> str:
    path = tmp_path / "mock-api.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return str(path)


def load(tmp_path, document) -> MockApiConfig:
    return load_config(write(tmp_path, document))


def with_faults(**faults) -> dict:
    document = {
        "config_version": MINIMAL["config_version"],
        "seed": MINIMAL["seed"],
        "endpoints": {
            "payments": {
                "response_class": "AUTHORITATIVE_READBACK",
                "identity_fields": ["action", "amount_minor"],
                "faults": faults,
            }
        },
    }
    return document


# ===========================================================================
# The response class comes from the production contract (amendment B1)
# ===========================================================================


def test_the_response_class_is_the_production_contract_enum(tmp_path):
    config = load(tmp_path, MINIMAL)
    capability = config.endpoints["payments"].response_class

    assert isinstance(capability, ReconciliationCapability)
    assert capability is ReconciliationCapability.AUTHORITATIVE_READBACK


@pytest.mark.parametrize("capability", list(ReconciliationCapability))
def test_every_declared_response_class_is_configurable(tmp_path, capability):
    document = {
        **MINIMAL,
        "endpoints": {
            "e": {
                "response_class": capability.value,
                "identity_fields": ["action"],
            }
        },
    }

    assert load(tmp_path, document).endpoints["e"].response_class is capability


def test_an_undeclared_response_class_is_refused(tmp_path):
    document = {
        **MINIMAL,
        "endpoints": {
            "e": {"response_class": "MAYBE_READBACK", "identity_fields": ["a"]}
        },
    }

    with pytest.raises(ConfigError, match="response_class"):
        load(tmp_path, document)


# ===========================================================================
# The five configurable dimensions
# ===========================================================================


def test_per_endpoint_response_classes_are_independent(tmp_path):
    document = {
        **MINIMAL,
        "endpoints": {
            "authoritative": {
                "response_class": ReconciliationCapability.AUTHORITATIVE_READBACK.value,
                "identity_fields": ["action"],
            },
            "positive_only": {
                "response_class": ReconciliationCapability.POSITIVE_ONLY_READBACK.value,
                "identity_fields": ["action"],
            },
            "silent": {
                "response_class": ReconciliationCapability.NO_READBACK.value,
                "identity_fields": ["action"],
            },
        },
    }

    config = load(tmp_path, document)
    assert len(config.endpoints) == 3
    assert {endpoint.response_class for endpoint in config.endpoints.values()} == set(
        ReconciliationCapability
    )


@pytest.mark.parametrize(
    "knob",
    [
        "timeout_probability",
        "server_error_probability",
        "duplicate_response_probability",
    ],
)
def test_each_probability_is_configurable(tmp_path, knob):
    config = load(tmp_path, with_faults(**{knob: 0.25}))

    assert getattr(config.endpoints["payments"].faults, knob) == 0.25


@pytest.mark.parametrize("knob", ["timeout_probability", "server_error_probability"])
@pytest.mark.parametrize("value", [-0.01, 1.01, "half", None])
def test_a_probability_outside_the_unit_interval_is_refused(tmp_path, knob, value):
    with pytest.raises(ConfigError):
        load(tmp_path, with_faults(**{knob: value}))


def test_the_delay_distribution_is_configurable(tmp_path):
    config = load(
        tmp_path,
        with_faults(delay={"distribution": "uniform", "low": 0.1, "high": 0.4}),
    )
    delay = config.endpoints["payments"].faults.delay

    assert delay.distribution is DelayDistribution.UNIFORM
    assert (delay.low, delay.high) == (0.1, 0.4)


@pytest.mark.parametrize(
    ("document", "match"),
    [
        ({"distribution": "poisson", "seconds": 1}, "distribution"),
        ({"distribution": "uniform", "low": 0.5, "high": 0.1}, "low"),
        ({"distribution": "constant", "seconds": -1}, "negative"),
        ({"distribution": "exponential", "mean": 0}, "positive"),
    ],
)
def test_an_unusable_delay_distribution_is_refused(tmp_path, document, match):
    with pytest.raises(ConfigError, match=match):
        load(tmp_path, with_faults(delay=document))


# ===========================================================================
# Sampling is seeded, so a run is reproducible
# ===========================================================================


def test_a_constant_delay_does_not_consume_randomness(tmp_path):
    config = load(tmp_path, with_faults(delay={"distribution": "constant", "seconds": 0.5}))
    delay = config.endpoints["payments"].faults.delay
    generator = random.Random(1)

    assert delay.sample(generator) == 0.5
    assert generator.getstate() == random.Random(1).getstate()


@pytest.mark.parametrize(
    "document",
    [
        {"distribution": "uniform", "low": 0.1, "high": 0.4},
        {"distribution": "exponential", "mean": 0.2},
    ],
)
def test_sampling_is_reproducible_under_a_seed(tmp_path, document):
    delay = load(tmp_path, with_faults(delay=document)).endpoints["payments"].faults.delay

    first = [delay.sample(random.Random(7)) for _ in range(3)]
    second = [delay.sample(random.Random(7)) for _ in range(3)]

    assert first == second
    assert all(value >= 0 for value in first)


def test_a_uniform_delay_stays_inside_its_bounds(tmp_path):
    delay = (
        load(tmp_path, with_faults(delay={"distribution": "uniform", "low": 0.1, "high": 0.4}))
        .endpoints["payments"]
        .faults.delay
    )
    generator = random.Random(11)

    assert all(0.1 <= delay.sample(generator) <= 0.4 for _ in range(200))


def test_the_seed_is_part_of_the_configuration(tmp_path):
    assert load(tmp_path, MINIMAL).seed == 20260805


# ===========================================================================
# Defaults and overrides
# ===========================================================================


def test_endpoints_inherit_the_declared_defaults(tmp_path):
    document = {
        **MINIMAL,
        "defaults": {"faults": {"server_error_probability": 0.3}},
    }

    assert load(tmp_path, document).endpoints["payments"].faults.server_error_probability == 0.3


def test_an_endpoint_overrides_only_what_it_names(tmp_path):
    document = {
        **MINIMAL,
        "defaults": {
            "faults": {"server_error_probability": 0.3, "timeout_probability": 0.2}
        },
        "endpoints": {
            "payments": {
                "response_class": ReconciliationCapability.NO_READBACK.value,
                "identity_fields": ["action"],
                "faults": {"timeout_probability": 0.9},
            }
        },
    }

    faults = load(tmp_path, document).endpoints["payments"].faults
    assert faults.timeout_probability == 0.9
    assert faults.server_error_probability == 0.3


def test_the_default_configuration_injects_no_faults(tmp_path):
    faults = load(tmp_path, MINIMAL).endpoints["payments"].faults

    assert faults.timeout_probability == 0
    assert faults.server_error_probability == 0
    assert faults.duplicate_response_probability == 0
    assert faults.delay.sample(random.Random(3)) == 0


# ===========================================================================
# Fail closed on anything unrecognised
# ===========================================================================


@pytest.mark.parametrize(
    ("document", "match"),
    [
        ({**MINIMAL, "endpoints": {}}, "at least one endpoint"),
        ({**MINIMAL, "typo_key": 1}, "unknown"),
        ({**MINIMAL, "config_version": "aep.mock-legacy-api.config/99"}, "version"),
        ({"seed": 1, "endpoints": MINIMAL["endpoints"]}, "config_version"),
    ],
)
def test_a_malformed_document_is_refused(tmp_path, document, match):
    with pytest.raises(ConfigError, match=match):
        load(tmp_path, document)


def test_an_unknown_endpoint_key_is_refused(tmp_path):
    document = {
        **MINIMAL,
        "endpoints": {
            "e": {
                "response_class": ReconciliationCapability.NO_READBACK.value,
                "identity_fields": ["a"],
                "resposne_class": "typo",
            }
        },
    }

    with pytest.raises(ConfigError, match="unknown"):
        load(tmp_path, document)


def test_an_unknown_fault_key_is_refused(tmp_path):
    with pytest.raises(ConfigError, match="unknown"):
        load(tmp_path, with_faults(tiemout_probability=0.5))


def test_an_endpoint_without_identity_fields_is_refused(tmp_path):
    document = {
        **MINIMAL,
        "endpoints": {
            "e": {
                "response_class": ReconciliationCapability.NO_READBACK.value,
                "identity_fields": [],
            }
        },
    }

    with pytest.raises(ConfigError, match="identity_fields"):
        load(tmp_path, document)


def test_duplicate_identity_fields_are_refused(tmp_path):
    document = {
        **MINIMAL,
        "endpoints": {
            "e": {
                "response_class": ReconciliationCapability.NO_READBACK.value,
                "identity_fields": ["action", "action"],
            }
        },
    }

    with pytest.raises(ConfigError, match="identity_fields"):
        load(tmp_path, document)


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(str(tmp_path / "absent.yaml"))


def test_a_document_that_is_not_a_mapping_is_refused(tmp_path):
    path = tmp_path / "mock-api.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="mapping"):
        load_config(str(path))


# ===========================================================================
# The echo: no run can be ambiguous about what the API was doing
# ===========================================================================


def test_the_echo_reports_every_knob(tmp_path):
    config = load(
        tmp_path,
        with_faults(
            timeout_probability=0.1,
            server_error_probability=0.2,
            duplicate_response_probability=0.3,
            delay={"distribution": "uniform", "low": 0.05, "high": 0.15},
        ),
    )
    echo = config.echo()
    endpoint = echo["endpoints"]["payments"]

    assert echo["seed"] == 20260805
    assert echo["config_version"] == "aep.mock-legacy-api.config/1"
    assert endpoint["response_class"] == "AUTHORITATIVE_READBACK"
    assert endpoint["identity_fields"] == ["action", "amount_minor"]
    assert endpoint["faults"]["timeout_probability"] == 0.1
    assert endpoint["faults"]["server_error_probability"] == 0.2
    assert endpoint["faults"]["duplicate_response_probability"] == 0.3
    assert endpoint["faults"]["delay"] == {
        "distribution": "uniform",
        "low": 0.05,
        "high": 0.15,
    }


def test_the_echo_is_json_serialisable(tmp_path):
    import json

    json.dumps(load(tmp_path, MINIMAL).echo())


def test_the_echo_carries_a_digest_of_itself(tmp_path):
    config = load(tmp_path, MINIMAL)

    assert len(config.config_digest) == 64
    assert config.echo()["config_digest"] == config.config_digest


def test_changing_any_knob_changes_the_digest(tmp_path):
    baseline = load(tmp_path, MINIMAL).config_digest

    assert load(tmp_path, with_faults(timeout_probability=0.01)).config_digest != baseline
    assert load(tmp_path, {**MINIMAL, "seed": 1}).config_digest != baseline


def test_the_same_document_always_produces_the_same_digest(tmp_path):
    assert load(tmp_path, MINIMAL).config_digest == load(tmp_path, MINIMAL).config_digest


def test_the_echo_records_where_the_configuration_came_from(tmp_path):
    path = write(tmp_path, MINIMAL)

    assert load_config(path).echo()["source_path"].endswith("mock-api.yaml")
