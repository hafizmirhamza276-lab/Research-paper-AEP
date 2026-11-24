"""MockLegacyAPI: the response classes, the fault surface, and the oracle.

The service is the paper's stand-in for a non-idempotent legacy API. Two
properties matter beyond "it returns 200":

* its three response classes are the *production* contract
  (``aep_core.core.connector_contract``), not a private copy that could drift
  from the protocol it is used to evaluate (amendment B1); and
* nothing it applies is invisible to the ground-truth ledger, including the
  mutations it applies twice on purpose.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from aep_core.core.connector_contract import (
    PERMITTED_READBACK_RESULTS,
    ReadbackResult,
    ReconciliationCapability,
)
from experiments.mock_api.ledger import DuplicateClass, GroundTruthLedger
from experiments.mock_api.service import MockLegacyAPI, create_app

MODULE_DIRECTORY = Path(__file__).resolve().parent.parent


def envelope(
    *,
    target: str = "account-redacted-17",
    action: str = "capture",
    amount_minor: int = 1700,
    memo: str = "invoice 42",
) -> dict:
    return {
        "envelope_schema": "aep.mutation-request/1",
        "canonicalization_version": "aep.canonical-json/1",
        "descriptor_version": "aep.safe-request/1",
        "connector_identity": "mock-connector",
        "connector_operation": "mock.non-idempotent.v1/mutate",
        "operation_version": "1",
        "endpoint_profile_id": "mock-endpoint",
        "endpoint_profile_version": "1",
        "credential_binding_id": "mock-credential",
        "credential_binding_version": "1",
        "wire_codec_version": "mock-wire/1",
        "target": target,
        "public_fields": [
            {"name": "action", "value": action},
            {"name": "amount_minor", "value": amount_minor},
            {"name": "memo", "value": memo},
        ],
        "protected_fields": [
            {
                "name": "authorization",
                "classification": "SECRET_AUTH",
                "encoding": "utf8",
                "value": "Bearer aaaa",
            }
        ],
        "mutation_options": [{"name": "notify", "value": False}],
    }


def config_document(tmp_path, *, endpoints=None, **overrides) -> dict:
    document = {
        "config_version": "aep.mock-legacy-api.config/1",
        "seed": 20260805,
        "ledger_path": str(tmp_path / "ground_truth.sqlite3"),
        "endpoints": endpoints
        or {
            "payments": {
                "response_class": ReconciliationCapability.AUTHORITATIVE_READBACK.value,
                "identity_fields": ["action", "amount_minor"],
            }
        },
    }
    document.update(overrides)
    return document


def build(tmp_path, document=None) -> MockLegacyAPI:
    path = tmp_path / "mock-api.yaml"
    path.write_text(
        yaml.safe_dump(document or config_document(tmp_path)), encoding="utf-8"
    )
    return MockLegacyAPI.from_config_path(path)


@pytest.fixture
def api(tmp_path):
    service = build(tmp_path)
    service.start()
    try:
        yield service
    finally:
        service.stop()


@pytest.fixture
def client(api):
    with TestClient(create_app(api)) as test_client:
        yield test_client


def mutate(client, endpoint="payments", *, body=None, reference="client-ref-1"):
    return client.post(
        f"/v1/endpoints/{endpoint}/mutations",
        content=json.dumps(body or envelope()),
        headers={
            "content-type": "application/json",
            "x-aep-client-reference": reference,
        },
    )


# ===========================================================================
# The production contract is the only vocabulary (amendment B1)
# ===========================================================================


def test_the_service_source_never_writes_a_capability_name_as_a_literal():
    """The guard against a private copy of the response-class vocabulary.

    A string literal is how the drift starts: one module spells a capability
    itself, the contract later gains a member or renames one, and the mock API
    keeps evaluating against the old vocabulary while still importing the new
    module.
    """
    names = [member.value for member in ReconciliationCapability]
    offenders = []
    for source in sorted(MODULE_DIRECTORY.glob("*.py")):
        text = source.read_text(encoding="utf-8")
        offenders.extend(
            f"{source.name}:{name}" for name in names if name in text
        )

    assert offenders == [], (
        "capability names appear as string literals in the service source: "
        f"{offenders}. Import ReconciliationCapability instead."
    )


def test_the_advertised_capabilities_are_contract_members(api):
    for endpoint in api.config.endpoints.values():
        assert isinstance(endpoint.response_class, ReconciliationCapability)


def test_the_config_endpoint_echoes_the_loaded_configuration(client, api):
    body = client.get("/v1/config").json()

    assert body == api.config.echo()
    assert body["config_digest"] == api.config.config_digest


def test_health_reports_the_configuration_digest(client, api):
    body = client.get("/v1/health").json()

    assert body["status"] == "ok"
    assert body["config_digest"] == api.config.config_digest


# ===========================================================================
# Applying a mutation
# ===========================================================================


def test_a_mutation_is_applied_and_recorded(client, api):
    response = mutate(client)

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "APPLIED"
    assert body["external_reference"]

    (row,) = api.ledger.applied_mutations()
    assert row.call_id == body["call_id"]
    assert row.endpoint == "payments"
    assert row.target == "account-redacted-17"
    assert row.client_reference == "client-ref-1"
    assert row.delivery_index == 1
    assert api.ledger.consistency_report().is_consistent


def test_the_response_never_exposes_oracle_state(client):
    """The caller must not be able to read the ground truth it is measured on."""
    body = mutate(client).json()

    assert set(body) == {"call_id", "outcome", "external_reference"}


def test_two_calls_with_the_same_content_are_one_duplicate_group(client, api):
    mutate(client, reference="ref-1")
    mutate(client, reference="ref-2")

    (group,) = api.ledger.duplicate_groups()
    assert group.duplicate_class is DuplicateClass.EXACT_DUPLICATE
    assert group.applications == 2


def test_a_different_amount_is_not_a_duplicate(client, api):
    mutate(client, body=envelope(amount_minor=1700))
    mutate(client, body=envelope(amount_minor=1701))

    assert api.ledger.duplicate_groups() == ()
    assert len(api.ledger.applied_mutations()) == 2


def test_a_changed_non_identity_field_is_a_fingerprint_conflict(client, api):
    mutate(client, body=envelope(memo="invoice 42"))
    mutate(client, body=envelope(memo="invoice 43"))

    (group,) = api.ledger.duplicate_groups()
    assert group.duplicate_class is DuplicateClass.FINGERPRINT_CONFLICT


def test_an_unknown_endpoint_is_rejected(client, api):
    assert mutate(client, endpoint="absent").status_code == 404
    assert api.ledger.applied_mutations() == ()


def test_an_unidentifiable_request_is_rejected_without_being_applied(client, api):
    """No fingerprint, no ledger row, therefore no mutation."""
    incomplete = envelope()
    incomplete["public_fields"] = [
        field for field in incomplete["public_fields"] if field["name"] != "action"
    ]

    assert mutate(client, body=incomplete).status_code == 422
    assert api.ledger.applied_mutations() == ()


def test_a_body_that_is_not_json_is_rejected(client, api):
    response = client.post(
        "/v1/endpoints/payments/mutations",
        content=b"not json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert api.ledger.applied_mutations() == ()


def test_a_mutation_without_a_client_reference_is_still_recorded(client, api):
    response = client.post(
        "/v1/endpoints/payments/mutations",
        content=json.dumps(envelope()),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    assert api.ledger.applied_mutations()[0].client_reference is None


# ===========================================================================
# The fault surface
# ===========================================================================


def faulty(tmp_path, **faults):
    return config_document(
        tmp_path,
        endpoints={
            "payments": {
                "response_class": ReconciliationCapability.AUTHORITATIVE_READBACK.value,
                "identity_fields": ["action", "amount_minor"],
                "faults": faults,
            }
        },
    )


def test_a_certain_server_error_returns_5xx_and_applies_nothing(tmp_path):
    """A 5xx is modelled as a refusal *before* the mutation is applied.

    Together with the timeout fault -- which applies and then loses the
    response -- this gives the evaluation both truth values behind an
    ambiguous outcome, which is what recovery has to tell apart.
    """
    service = build(tmp_path, faulty(tmp_path, server_error_probability=1.0))
    service.start()
    try:
        with TestClient(create_app(service)) as client:
            response = mutate(client)

        assert response.status_code == 503
        assert service.ledger.applied_mutations() == ()
    finally:
        service.stop()


def test_a_certain_timeout_applies_the_mutation_and_withholds_the_response(
    tmp_path, monkeypatch
):
    """Applied, and the caller is told nothing it can act on.

    ``TestClient`` drives the app in-process and cannot honour a client-side
    timeout, so this test asserts the server half of the fault: the mutation
    lands, the response is withheld for the full hold, and what finally
    arrives is not a success. The client half -- a real socket raising
    ReadTimeout -- is asserted in test_service_crash_safety.py against a real
    uvicorn server.
    """
    import time

    monkeypatch.setattr("experiments.mock_api.service.TIMEOUT_HOLD_SECONDS", 0.3)
    service = build(tmp_path, faulty(tmp_path, timeout_probability=1.0))
    service.start()
    try:
        with TestClient(create_app(service)) as client:
            started = time.monotonic()
            response = mutate(client)
            elapsed = time.monotonic() - started

        assert response.status_code == 504
        assert elapsed >= 0.3
        # The caller learned nothing; the external world changed anyway.
        assert len(service.ledger.applied_mutations()) == 1
        assert service.ledger.consistency_report().is_consistent
    finally:
        service.stop()


def test_a_certain_duplicate_delivery_applies_the_mutation_twice(tmp_path):
    service = build(tmp_path, faulty(tmp_path, duplicate_response_probability=1.0))
    service.start()
    try:
        with TestClient(create_app(service)) as client:
            assert mutate(client).status_code == 200

        rows = service.ledger.applied_mutations()
        assert [row.delivery_index for row in rows] == [1, 2]

        (group,) = service.ledger.duplicate_groups()
        assert group.duplicate_class is DuplicateClass.EXACT_DUPLICATE
        assert group.applications == 2
        assert service.ledger.duplicate_application_count() == 1
        assert service.ledger.consistency_report().is_consistent
    finally:
        service.stop()


def test_a_configured_delay_is_applied(tmp_path):
    service = build(
        tmp_path,
        faulty(tmp_path, delay={"distribution": "constant", "seconds": 0.25}),
    )
    service.start()
    try:
        import time

        with TestClient(create_app(service)) as client:
            started = time.monotonic()
            assert mutate(client).status_code == 200
            elapsed = time.monotonic() - started

        assert elapsed >= 0.25
    finally:
        service.stop()


def test_fault_decisions_are_drawn_from_the_seeded_generator(tmp_path):
    """Two services on one seed make the same decisions in the same order."""

    def decisions(seed: int) -> list[tuple[bool, bool, bool]]:
        document = faulty(
            tmp_path,
            timeout_probability=0.5,
            server_error_probability=0.5,
            duplicate_response_probability=0.5,
        )
        document["seed"] = seed
        document["ledger_path"] = str(tmp_path / f"ledger-{seed}.sqlite3")
        service = build(tmp_path, document)
        service.start()
        try:
            return [service.draw_faults("payments") for _ in range(20)]
        finally:
            service.stop()

    assert decisions(4) == decisions(4)
    assert decisions(4) != decisions(5)


# ===========================================================================
# Read-back, driven by the contract's permitted-result table
# ===========================================================================


def readback_service(tmp_path, capability: ReconciliationCapability) -> MockLegacyAPI:
    return build(
        tmp_path,
        config_document(
            tmp_path,
            endpoints={
                "payments": {
                    "response_class": capability.value,
                    "identity_fields": ["action", "amount_minor"],
                }
            },
        ),
    )


@pytest.mark.parametrize(
    "capability",
    [
        ReconciliationCapability.AUTHORITATIVE_READBACK,
        ReconciliationCapability.POSITIVE_ONLY_READBACK,
    ],
)
def test_an_applied_mutation_reads_back_as_applied(tmp_path, capability):
    service = readback_service(tmp_path, capability)
    service.start()
    try:
        with TestClient(create_app(service)) as client:
            mutate(client, reference="ref-1")
            body = client.get(
                "/v1/endpoints/payments/readback",
                params={"client_reference": "ref-1"},
            ).json()

        assert body["result"] == ReadbackResult.APPLIED.value
    finally:
        service.stop()


def test_an_authoritative_endpoint_can_deny_an_absent_mutation(tmp_path):
    service = readback_service(
        tmp_path, ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    service.start()
    try:
        with TestClient(create_app(service)) as client:
            body = client.get(
                "/v1/endpoints/payments/readback",
                params={"client_reference": "never-sent"},
            ).json()

        assert body["result"] == ReadbackResult.NOT_APPLIED.value
    finally:
        service.stop()


def test_a_positive_only_endpoint_never_denies(tmp_path):
    """The property that makes POSITIVE_ONLY a distinct response class."""
    service = readback_service(
        tmp_path, ReconciliationCapability.POSITIVE_ONLY_READBACK
    )
    service.start()
    try:
        with TestClient(create_app(service)) as client:
            body = client.get(
                "/v1/endpoints/payments/readback",
                params={"client_reference": "never-sent"},
            ).json()

        assert body["result"] == ReadbackResult.UNKNOWN.value
        assert (
            ReadbackResult.NOT_APPLIED
            not in PERMITTED_READBACK_RESULTS[
                ReconciliationCapability.POSITIVE_ONLY_READBACK
            ]
        )
    finally:
        service.stop()


def test_a_no_readback_endpoint_refuses_to_be_queried(tmp_path):
    service = readback_service(tmp_path, ReconciliationCapability.NO_READBACK)
    service.start()
    try:
        with TestClient(create_app(service)) as client:
            response = client.get(
                "/v1/endpoints/payments/readback",
                params={"client_reference": "ref-1"},
            )

        assert response.status_code == 409
    finally:
        service.stop()


def test_two_applications_read_back_as_conflicting_evidence(tmp_path):
    service = readback_service(
        tmp_path, ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    service.start()
    try:
        with TestClient(create_app(service)) as client:
            mutate(client, reference="ref-1")
            mutate(client, reference="ref-1")
            body = client.get(
                "/v1/endpoints/payments/readback",
                params={"client_reference": "ref-1"},
            ).json()

        assert body["result"] == ReadbackResult.CONFLICT.value
    finally:
        service.stop()


@pytest.mark.parametrize(
    "capability",
    [
        ReconciliationCapability.AUTHORITATIVE_READBACK,
        ReconciliationCapability.POSITIVE_ONLY_READBACK,
    ],
)
def test_every_answer_is_one_the_capability_may_assert(tmp_path, capability):
    """Enforced at run time, from the contract's own table."""
    service = readback_service(tmp_path, capability)
    service.start()
    try:
        with TestClient(create_app(service)) as client:
            mutate(client, reference="ref-1")
            answers = {
                client.get(
                    "/v1/endpoints/payments/readback",
                    params={"client_reference": reference},
                ).json()["result"]
                for reference in ("ref-1", "absent-ref")
            }

        permitted = {
            result.value for result in PERMITTED_READBACK_RESULTS[capability]
        }
        assert answers <= permitted
    finally:
        service.stop()


# ===========================================================================
# The oracle surface and the run log
# ===========================================================================


def test_the_oracle_endpoints_report_the_ledger(client):
    mutate(client, reference="ref-1")
    mutate(client, reference="ref-2")

    mutations = client.get("/v1/oracle/mutations").json()
    duplicates = client.get("/v1/oracle/duplicates").json()
    consistency = client.get("/v1/oracle/consistency").json()

    assert len(mutations["applied_mutations"]) == 2
    assert duplicates["duplicate_application_count"] == 1
    assert duplicates["groups"][0]["duplicate_class"] == "EXACT_DUPLICATE"
    assert consistency["is_consistent"] is True


def test_the_run_log_opens_with_the_full_configuration_echo(api):
    """No experiment can be ambiguous about what the API was doing."""
    first = json.loads(api.run_log_path.read_text(encoding="utf-8").splitlines()[0])

    assert first["event"] == "run_started"
    assert first["config"] == api.config.echo()
    assert first["config"]["config_digest"] == api.config.config_digest


def test_every_applied_mutation_appends_to_the_run_log(client, api):
    mutate(client, reference="ref-1")

    events = [
        json.loads(line)
        for line in api.run_log_path.read_text(encoding="utf-8").splitlines()
    ]
    applied = [event for event in events if event["event"] == "mutation_applied"]

    assert len(applied) == 1
    assert applied[0]["endpoint"] == "payments"
    assert applied[0]["config_digest"] == api.config.config_digest
    assert applied[0]["delivery_index"] == 1


def test_the_run_log_records_refusals_too(client, api):
    mutate(client, endpoint="absent")

    events = [
        json.loads(line)
        for line in api.run_log_path.read_text(encoding="utf-8").splitlines()
    ]

    assert any(event["event"] == "mutation_refused" for event in events)


def test_the_run_log_never_contains_protected_material(client, api):
    mutate(client, reference="ref-1")

    assert "Bearer aaaa" not in api.run_log_path.read_text(encoding="utf-8")


def test_the_ledger_never_contains_protected_material(client, api):
    mutate(client, reference="ref-1")

    raw = Path(api.config.ledger_path).read_bytes()
    assert b"Bearer aaaa" not in raw


# ===========================================================================
# Wiring
# ===========================================================================


def test_the_service_refuses_to_serve_before_it_is_started(tmp_path):
    service = build(tmp_path)

    with pytest.raises(RuntimeError, match="start"):
        _ = service.ledger


def test_the_example_configuration_in_the_repository_loads():
    """A broken example is a broken quick-start."""
    from experiments.mock_api.config import load_config

    config = load_config(MODULE_DIRECTORY / "config.example.yaml")

    assert config.endpoints
    assert set(
        endpoint.response_class for endpoint in config.endpoints.values()
    ) == set(ReconciliationCapability)


def test_a_prepared_ledger_can_be_supplied_for_inspection(tmp_path):
    """The harness owns the ledger's lifetime when it needs to."""
    ledger = GroundTruthLedger(tmp_path / "supplied.sqlite3")
    ledger.initialise()
    service = build(tmp_path)
    service.start(ledger=ledger)
    try:
        with TestClient(create_app(service)) as client:
            mutate(client)
        assert len(ledger.applied_mutations()) == 1
    finally:
        service.stop()
