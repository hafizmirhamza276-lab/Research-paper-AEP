"""Read-back keying: the measurement decision of amendment C1.

Session 1 closed with open question G1 (report section F5): read-back is keyed
on ``X-AEP-Client-Reference``, which is AEP's own request fingerprint. That is
realistic -- legacy APIs do echo client references -- but it means read-back
only works for a caller with the discipline to reuse one reference across
attempts. A naive-retry baseline mints a fresh reference per attempt and would
read back ``NOT_APPLIED`` for a mutation it *had* applied, and the resulting
number would be a property of the apparatus rather than of the baseline.

C1 resolves it by making the key a per-run configuration with two values, both
implemented, both echoed into every run log:

``CALLER_REFERENCE``
    The provider can find a past mutation only by the identifier the caller
    gave it. Primary model; every headline number is collected under it.

``ORACLE_FINGERPRINT``
    The provider can find a past mutation by its *content*, using the oracle's
    own identity function (Definition 1). Sensitivity variant. It is strictly
    more generous than any real legacy endpoint: it hands every system under
    test, including the ones with no idempotency discipline at all, a working
    read-back. Its hazard is asserted below rather than described -- two
    genuinely distinct executions of identical content share one fingerprint,
    so the second reads ``CONFLICT`` off the first's effect.

Both directions of ignoring are tested, because "the keying is a property of
the run, not of the caller" is only true if the service really disregards the
input its configured keying does not name.
"""

from __future__ import annotations

import json

import pytest
import yaml
from fastapi.testclient import TestClient

from aep_core.core.connector_contract import ReadbackResult, ReconciliationCapability
from experiments.mock_api.config import ConfigError, ReadbackKeying, load_config
from experiments.mock_api.service import MockLegacyAPI, create_app

from experiments.mock_api.tests.test_service import config_document, envelope

ENDPOINT = "payments"


def identity_of(**overrides) -> dict:
    """The identity descriptor a caller sends to describe a past mutation.

    Deliberately *not* the whole envelope: only the keys Definition 1 reads.
    A read-back must not require the caller to re-transmit credentials.
    """
    body = envelope(**overrides)
    return {
        "connector_operation": body["connector_operation"],
        "operation_version": body["operation_version"],
        "target": body["target"],
        "public_fields": body["public_fields"],
    }


def build(tmp_path, *, keying=None, capability=None, document=None) -> MockLegacyAPI:
    document = document or config_document(
        tmp_path,
        endpoints={
            ENDPOINT: {
                "response_class": (
                    capability or ReconciliationCapability.AUTHORITATIVE_READBACK
                ).value,
                "identity_fields": ["action", "amount_minor"],
            }
        },
    )
    if keying is not None:
        document = {**document, "readback_keying": keying.value}
    path = tmp_path / "mock-api.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return MockLegacyAPI.from_config_path(path)


@pytest.fixture
def caller_reference_client(tmp_path):
    api = build(tmp_path, keying=ReadbackKeying.CALLER_REFERENCE)
    api.start()
    try:
        with TestClient(create_app(api)) as client:
            yield client
    finally:
        api.stop()


@pytest.fixture
def oracle_fingerprint_client(tmp_path):
    api = build(tmp_path, keying=ReadbackKeying.ORACLE_FINGERPRINT)
    api.start()
    try:
        with TestClient(create_app(api)) as client:
            yield client
    finally:
        api.stop()


def mutate(client, *, reference, body=None):
    response = client.post(
        f"/v1/endpoints/{ENDPOINT}/mutations",
        content=json.dumps(body or envelope()),
        headers={
            "content-type": "application/json",
            "x-aep-client-reference": reference,
        },
    )
    assert response.status_code == 200, response.text
    return response


def readback(client, *, reference=None, identity=None):
    return client.post(
        f"/v1/endpoints/{ENDPOINT}/readback",
        json={"client_reference": reference, "identity": identity},
    )


# ===========================================================================
# The configuration
# ===========================================================================


def test_the_default_keying_is_the_caller_reference(tmp_path):
    """Session 1's behaviour is the default; nothing changes silently."""
    api = build(tmp_path)

    assert api.config.readback_keying is ReadbackKeying.CALLER_REFERENCE


def test_the_keying_is_echoed_into_the_configuration(tmp_path):
    api = build(tmp_path, keying=ReadbackKeying.ORACLE_FINGERPRINT)

    assert api.config.echo()["readback_keying"] == "ORACLE_FINGERPRINT"


def test_the_two_keyings_have_different_configuration_digests(tmp_path):
    """A run collected under one keying must not be attributable to the other."""
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    caller = build(first, keying=ReadbackKeying.CALLER_REFERENCE)
    oracle = build(second, keying=ReadbackKeying.ORACLE_FINGERPRINT)

    assert caller.config.config_digest != oracle.config.config_digest


def test_an_unknown_keying_refuses_to_load(tmp_path):
    document = {**config_document(tmp_path), "readback_keying": "WHATEVER_WORKS"}
    path = tmp_path / "mock-api.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(ConfigError) as refused:
        load_config(path)

    assert "readback_keying" in str(refused.value)
    assert "CALLER_REFERENCE" in str(refused.value)


# ===========================================================================
# CALLER_REFERENCE: the primary model
# ===========================================================================


def test_caller_reference_finds_a_mutation_by_the_reference_it_carried(
    caller_reference_client,
):
    mutate(caller_reference_client, reference="ref-1")

    response = readback(caller_reference_client, reference="ref-1")

    assert response.status_code == 200
    assert response.json()["result"] == ReadbackResult.APPLIED.value
    assert response.json()["readback_keying"] == "CALLER_REFERENCE"


def test_caller_reference_denies_a_mutation_asked_about_under_a_fresh_reference(
    caller_reference_client,
):
    """This is exactly what a naive-retry baseline will experience."""
    mutate(caller_reference_client, reference="attempt-1")

    response = readback(caller_reference_client, reference="attempt-2")

    assert response.json()["result"] == ReadbackResult.NOT_APPLIED.value


def test_caller_reference_ignores_a_correct_identity_descriptor(
    caller_reference_client,
):
    """The keying is a property of the run, not of what the caller sends."""
    mutate(caller_reference_client, reference="attempt-1")

    response = readback(
        caller_reference_client, reference="attempt-2", identity=identity_of()
    )

    assert response.json()["result"] == ReadbackResult.NOT_APPLIED.value


def test_caller_reference_still_answers_the_original_get_route(
    caller_reference_client,
):
    """Session 1's route is unchanged for the keying it was written for."""
    mutate(caller_reference_client, reference="ref-1")

    response = caller_reference_client.get(
        f"/v1/endpoints/{ENDPOINT}/readback", params={"client_reference": "ref-1"}
    )

    assert response.status_code == 200
    assert response.json()["result"] == ReadbackResult.APPLIED.value


def test_caller_reference_refuses_a_readback_that_names_nothing(
    caller_reference_client,
):
    response = readback(caller_reference_client, identity=identity_of())

    assert response.status_code == 422
    assert "client_reference" in response.json()["detail"]


# ===========================================================================
# ORACLE_FINGERPRINT: the sensitivity variant
# ===========================================================================


def test_oracle_fingerprint_finds_a_mutation_under_a_completely_fresh_reference(
    oracle_fingerprint_client,
):
    """The whole point of the variant: best-case read-back for the baselines."""
    mutate(oracle_fingerprint_client, reference="attempt-1")

    response = readback(
        oracle_fingerprint_client, reference="attempt-2", identity=identity_of()
    )

    assert response.status_code == 200
    assert response.json()["result"] == ReadbackResult.APPLIED.value
    assert response.json()["readback_keying"] == "ORACLE_FINGERPRINT"


def test_oracle_fingerprint_ignores_the_client_reference_entirely(
    oracle_fingerprint_client,
):
    mutate(oracle_fingerprint_client, reference="ref-1")

    with_reference = readback(
        oracle_fingerprint_client, reference="ref-1", identity=identity_of()
    )
    without_reference = readback(oracle_fingerprint_client, identity=identity_of())

    assert with_reference.json()["result"] == without_reference.json()["result"]
    assert without_reference.json()["result"] == ReadbackResult.APPLIED.value


def test_oracle_fingerprint_denies_a_mutation_with_different_identity_content(
    oracle_fingerprint_client,
):
    mutate(oracle_fingerprint_client, reference="ref-1")

    response = readback(
        oracle_fingerprint_client, identity=identity_of(amount_minor=9999)
    )

    assert response.json()["result"] == ReadbackResult.NOT_APPLIED.value


def test_oracle_fingerprint_ignores_fields_outside_the_identity_projection(
    oracle_fingerprint_client,
):
    """A caller may change its free-text memo between attempts; F(r) may not."""
    mutate(oracle_fingerprint_client, reference="ref-1")

    response = readback(
        oracle_fingerprint_client, identity=identity_of(memo="a different memo")
    )

    assert response.json()["result"] == ReadbackResult.APPLIED.value


def test_oracle_fingerprint_conflates_two_distinct_executions_of_equal_content(
    oracle_fingerprint_client,
):
    """The declared hazard, evidenced.

    Two *intended* mutations with identical content share one fingerprint. The
    provider cannot tell them apart, so a caller asking about the second is
    told about the first. This is why ORACLE_FINGERPRINT is a sensitivity
    variant and not the primary model, and it belongs in the paper's threats
    to validity with this test as its citation.
    """
    mutate(oracle_fingerprint_client, reference="execution-1")
    mutate(oracle_fingerprint_client, reference="execution-2")

    response = readback(oracle_fingerprint_client, identity=identity_of())

    assert response.json()["result"] == ReadbackResult.CONFLICT.value


def test_oracle_fingerprint_refuses_a_readback_that_describes_nothing(
    oracle_fingerprint_client,
):
    response = readback(oracle_fingerprint_client, reference="ref-1")

    assert response.status_code == 422
    assert "identity" in response.json()["detail"]


def test_oracle_fingerprint_refuses_the_get_route_it_cannot_answer(
    oracle_fingerprint_client,
):
    """A 200 here would be an answer to a question the run is not asking."""
    response = oracle_fingerprint_client.get(
        f"/v1/endpoints/{ENDPOINT}/readback", params={"client_reference": "ref-1"}
    )

    assert response.status_code == 409
    assert "ORACLE_FINGERPRINT" in response.json()["detail"]


def test_an_unidentifiable_descriptor_is_refused_rather_than_guessed(
    oracle_fingerprint_client,
):
    response = readback(
        oracle_fingerprint_client, identity={"target": "account-redacted-17"}
    )

    assert response.status_code == 422


# ===========================================================================
# The capability contract outranks the keying
# ===========================================================================


@pytest.mark.parametrize("keying", list(ReadbackKeying))
def test_no_readback_refuses_under_either_keying(tmp_path, keying):
    api = build(
        tmp_path,
        keying=keying,
        capability=ReconciliationCapability.NO_READBACK,
    )
    api.start()
    try:
        with TestClient(create_app(api)) as client:
            response = client.post(
                f"/v1/endpoints/{ENDPOINT}/readback",
                json={"client_reference": "ref-1", "identity": identity_of()},
            )
    finally:
        api.stop()

    assert response.status_code == 409


@pytest.mark.parametrize("keying", list(ReadbackKeying))
def test_positive_only_never_asserts_absence_under_either_keying(tmp_path, keying):
    api = build(
        tmp_path,
        keying=keying,
        capability=ReconciliationCapability.POSITIVE_ONLY_READBACK,
    )
    api.start()
    try:
        with TestClient(create_app(api)) as client:
            response = client.post(
                f"/v1/endpoints/{ENDPOINT}/readback",
                json={"client_reference": "never-used", "identity": identity_of()},
            )
    finally:
        api.stop()

    assert response.status_code == 200
    assert response.json()["result"] == ReadbackResult.UNKNOWN.value
