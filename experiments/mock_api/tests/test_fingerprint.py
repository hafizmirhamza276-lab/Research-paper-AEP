"""The oracle's identity function: when are two requests the same mutation?

These tests pin the definition that appears verbatim in the paper's
methodology (``experiments/mock_api/fingerprint.py`` module docstring). Every
number the evaluation reports about *duplicates* is a count of fingerprint
collisions, so a change here silently changes the headline metric. That is why
the schema version is part of the hash and is asserted below.
"""

from __future__ import annotations

import copy

import pytest

from experiments.mock_api.fingerprint import (
    FINGERPRINT_SCHEMA_VERSION,
    FingerprintError,
    canonical_bytes,
    mutation_fingerprint,
    payload_digest,
    redact_envelope,
)

IDENTITY_FIELDS = ("action", "amount_minor")


def envelope(
    *,
    target: str = "account-redacted-17",
    action: str = "capture",
    amount_minor: int = 1700,
    memo: str = "invoice 42",
    secret: str = "Bearer aaaa",
    operation: str = "mock.non-idempotent.v1/mutate",
    operation_version: str = "1",
) -> dict:
    """An envelope shaped like aep_core's build_exact_request_bytes output."""
    return {
        "envelope_schema": "aep.mutation-request/1",
        "canonicalization_version": "aep.canonical-json/1",
        "descriptor_version": "aep.safe-request/1",
        "connector_identity": "mock-connector",
        "connector_operation": operation,
        "operation_version": operation_version,
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
                "value": secret,
            }
        ],
        "mutation_options": [{"name": "notify", "value": False}],
    }


def fingerprint(env: dict, *, endpoint: str = "payments", method: str = "POST") -> str:
    return mutation_fingerprint(
        method=method,
        endpoint=endpoint,
        envelope=env,
        identity_fields=IDENTITY_FIELDS,
    )


# ===========================================================================
# The same mutation
# ===========================================================================


def test_identical_requests_are_the_same_mutation():
    assert fingerprint(envelope()) == fingerprint(envelope())


def test_the_fingerprint_is_a_sha256_hex_digest():
    value = fingerprint(envelope())

    assert len(value) == 64
    assert set(value) <= set("0123456789abcdef")


def test_public_field_order_on_the_wire_does_not_change_identity():
    """A list is ordered; the mutation it denotes is not."""
    reordered = envelope()
    reordered["public_fields"] = list(reversed(reordered["public_fields"]))

    assert fingerprint(reordered) == fingerprint(envelope())


def test_a_retry_carrying_different_protected_material_is_the_same_mutation():
    """Rotating a bearer token between attempts does not create a new mutation.

    This is the property that makes duplicate counting possible at all: the
    things a retry legitimately changes must be outside the fingerprint.
    """
    assert fingerprint(envelope(secret="Bearer bbbb")) == fingerprint(envelope())


def test_a_non_identity_field_does_not_change_identity():
    """`memo` is not declared an identity field for this endpoint."""
    assert fingerprint(envelope(memo="invoice 43")) == fingerprint(envelope())


def test_unicode_is_compared_after_nfc_normalisation():
    """U+00E9 and "e" + U+0301 are the same text and must hash the same."""
    composed = envelope(memo="café", target="cafeé-account")
    decomposed = envelope(memo="café", target="cafeé-account")
    assert composed["target"] != decomposed["target"]

    # The target is inside the fingerprint ...
    assert fingerprint(composed) == fingerprint(decomposed)
    # ... and the memo is inside the payload digest.
    assert payload_digest(composed) == payload_digest(decomposed)


# ===========================================================================
# Different mutations (the near-miss cases the oracle must not merge)
# ===========================================================================


@pytest.mark.parametrize(
    ("kwargs", "what"),
    [
        ({"amount_minor": 1701}, "one minor unit more"),
        ({"amount_minor": 0}, "zero amount"),
        ({"action": "void"}, "a different action"),
        ({"target": "account-redacted-18"}, "a different target"),
        ({"operation": "mock.non-idempotent.v2/mutate"}, "a different operation"),
        ({"operation_version": "2"}, "a different operation version"),
    ],
)
def test_a_near_miss_is_a_different_mutation(kwargs, what):
    assert fingerprint(envelope(**kwargs)) != fingerprint(envelope()), what


def test_the_same_payload_on_a_different_endpoint_is_a_different_mutation():
    assert fingerprint(envelope(), endpoint="refunds") != fingerprint(envelope())


def test_the_same_payload_under_a_different_method_is_a_different_mutation():
    assert fingerprint(envelope(), method="PUT") != fingerprint(envelope())


def test_the_method_is_compared_case_insensitively():
    assert fingerprint(envelope(), method="post") == fingerprint(envelope())


def test_declaring_more_identity_fields_changes_the_fingerprint():
    """The projection is part of the definition, not an implementation detail."""
    wider = mutation_fingerprint(
        method="POST",
        endpoint="payments",
        envelope=envelope(),
        identity_fields=("action", "amount_minor", "memo"),
    )

    assert wider != fingerprint(envelope())


def test_identity_field_order_does_not_matter():
    swapped = mutation_fingerprint(
        method="POST",
        endpoint="payments",
        envelope=envelope(),
        identity_fields=("amount_minor", "action"),
    )

    assert swapped == fingerprint(envelope())


# ===========================================================================
# Fail closed
# ===========================================================================


def test_a_missing_identity_field_is_refused():
    """An unidentifiable mutation must not be given a plausible fingerprint."""
    incomplete = envelope()
    incomplete["public_fields"] = [
        entry for entry in incomplete["public_fields"] if entry["name"] != "action"
    ]

    with pytest.raises(FingerprintError, match="action"):
        fingerprint(incomplete)


def test_declaring_no_identity_fields_is_refused():
    with pytest.raises(FingerprintError, match="identity field"):
        mutation_fingerprint(
            method="POST", endpoint="payments", envelope=envelope(), identity_fields=()
        )


def test_a_duplicated_public_field_name_is_refused():
    ambiguous = envelope()
    ambiguous["public_fields"].append({"name": "action", "value": "void"})

    with pytest.raises(FingerprintError, match="duplicate"):
        fingerprint(ambiguous)


def test_a_malformed_envelope_is_refused():
    with pytest.raises(FingerprintError):
        fingerprint({"target": "t"})


def test_floats_are_refused_by_the_canonicaliser():
    """Money is integer minor units. A float would hash non-deterministically."""
    with pytest.raises(FingerprintError):
        canonical_bytes({"amount": 17.0})


def test_the_schema_version_is_bound_into_the_digest():
    """A future v2 definition must not silently compare equal to a v1 one."""
    assert FINGERPRINT_SCHEMA_VERSION.startswith("aep.mock-legacy-api.")
    assert FINGERPRINT_SCHEMA_VERSION.encode() in canonical_bytes(
        {"v": FINGERPRINT_SCHEMA_VERSION}
    )


# ===========================================================================
# The payload digest, and the privacy boundary it has to respect
# ===========================================================================


def test_the_payload_digest_separates_requests_the_fingerprint_merges():
    """Same mutation, different bytes -- the conflict the ledger must surface."""
    other = envelope(memo="invoice 43")

    assert fingerprint(other) == fingerprint(envelope())
    assert payload_digest(other) != payload_digest(envelope())


def test_the_payload_digest_notices_changed_protected_material():
    assert payload_digest(envelope(secret="Bearer bbbb")) != payload_digest(envelope())


def test_redaction_removes_protected_values_but_keeps_their_identity():
    redacted = redact_envelope(envelope(secret="Bearer aaaa"))
    (protected,) = redacted["protected_fields"]

    assert "value" not in protected
    assert protected["name"] == "authorization"
    assert protected["classification"] == "SECRET_AUTH"
    assert len(protected["value_digest"]) == 64
    assert "aaaa" not in canonical_bytes(redacted).decode("utf-8")


def test_redaction_does_not_mutate_the_caller_s_envelope():
    original = envelope()
    snapshot = copy.deepcopy(original)
    redact_envelope(original)

    assert original == snapshot


def test_the_payload_digest_ignores_wire_field_order():
    reordered = envelope()
    reordered["public_fields"] = list(reversed(reordered["public_fields"]))

    assert payload_digest(reordered) == payload_digest(envelope())
