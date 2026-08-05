"""P2-004/P2-010 canonical request and commitment regressions."""

from __future__ import annotations

import math
import subprocess
import sys
import uuid

import pytest

from aep_core.core.request_binding import (
    CanonicalizationError,
    CommitmentKeyError,
    CommitmentKeyring,
    EndpointProfile,
    ExactMutationRequest,
    ProtectedFieldClass,
    SafeValueKind,
    SafeValueRule,
    UnsafeRequestError,
    build_exact_request_bytes,
    build_safe_descriptor,
    canonical_json_bytes,
    compute_request_binding_digest,
    semantic_request_fingerprint,
)


def _profile(**changes) -> EndpointProfile:
    values = {
        "connector_identity": "mock-connector",
        "connector_operation": "mock.non-idempotent/mutate",
        "operation_version": "1",
        "endpoint_profile_id": "mock-endpoint",
        "endpoint_profile_version": "1",
        "credential_binding_id": "mock-credential",
        "credential_binding_version": "1",
        "wire_codec_version": "mock-wire/1",
        "public_field_rules": {
            "action": SafeValueRule(
                kind=SafeValueKind.STRING,
                allowed_strings=frozenset({"capture", "void"}),
            ),
            "amount_minor": SafeValueRule(
                kind=SafeValueKind.INTEGER,
                minimum_integer=0,
                maximum_integer=1_000_000,
            ),
            "nested": SafeValueRule(
                kind=SafeValueKind.OBJECT,
                object_fields={
                    "approved": SafeValueRule(kind=SafeValueKind.BOOLEAN),
                    "sequence": SafeValueRule(
                        kind=SafeValueKind.ARRAY,
                        array_item=SafeValueRule(
                            kind=SafeValueKind.ONE_OF,
                            variants=(
                                SafeValueRule(
                                    kind=SafeValueKind.INTEGER,
                                    minimum_integer=0,
                                    maximum_integer=10,
                                ),
                                SafeValueRule(
                                    kind=SafeValueKind.STRING,
                                    allowed_strings=frozenset({"1"}),
                                ),
                                SafeValueRule(kind=SafeValueKind.NULL),
                            ),
                        ),
                    ),
                },
            ),
        },
        "protected_field_classes": {
            "authorization": ProtectedFieldClass.SECRET_AUTH,
            "cookie": ProtectedFieldClass.SECRET_AUTH,
            "payment_value": ProtectedFieldClass.PAYMENT,
            "personal_identifier": ProtectedFieldClass.PERSONAL_INFORMATION,
            "token": ProtectedFieldClass.TOKEN,
        },
        "mutation_option_rules": {
            "notify": SafeValueRule(kind=SafeValueKind.BOOLEAN),
            "ordered_labels": SafeValueRule(
                kind=SafeValueKind.ARRAY,
                array_item=SafeValueRule(
                    kind=SafeValueKind.STRING,
                    allowed_strings=frozenset({"a", "b"}),
                ),
            ),
        },
    }
    values.update(changes)
    return EndpointProfile(**values)


def _keyring() -> CommitmentKeyring:
    return CommitmentKeyring(
        keys={"commit-2026-01": b"c" * 32},
        active_key_id="commit-2026-01",
    )


def _request(**changes) -> ExactMutationRequest:
    values = {
        "target": "account-redacted-17",
        "public_fields": {
            "action": "capture",
            "amount_minor": 1700,
            "nested": {"approved": True, "sequence": [1, "1", None]},
        },
        "protected_fields": {
            "authorization": "Bearer CANARY-AUTH",
            "payment_value": "4111111111111111",
        },
        "mutation_options": {"notify": False, "ordered_labels": ["a", "b"]},
    }
    values.update(changes)
    return ExactMutationRequest(**values)


def _descriptor(profile=None, request=None):
    profile = profile or _profile()
    request = request or _request()
    exact = build_exact_request_bytes(profile, request)
    return build_safe_descriptor(exact, profile, _keyring())


def test_canonical_bytes_ignore_mapping_insertion_order():
    left = {"z": 1, "a": {"second": False, "first": "x"}}
    right = {"a": {"first": "x", "second": False}, "z": 1}
    assert canonical_json_bytes(left) == canonical_json_bytes(right)


@pytest.mark.parametrize(
    "value",
    [math.nan, math.inf, -math.inf, 1.5, {1: "ambiguous"}, {"x": object()}],
)
def test_canonical_bytes_reject_unsupported_or_ambiguous_values(value):
    with pytest.raises(CanonicalizationError):
        canonical_json_bytes(value)


def test_canonical_types_array_order_and_unicode_are_unambiguous():
    assert canonical_json_bytes(True) != canonical_json_bytes(1)
    assert canonical_json_bytes("1") != canonical_json_bytes(1)
    assert canonical_json_bytes(["a", "b"]) != canonical_json_bytes(["b", "a"])
    assert canonical_json_bytes("café") == b'"caf\xc3\xa9"'
    with pytest.raises(CanonicalizationError):
        canonical_json_bytes("cafe\u0301")


def test_semantically_identical_request_key_order_has_same_fingerprint():
    first = _request(public_fields={"action": "capture", "amount_minor": 1700,
                                    "nested": {"approved": True, "sequence": [1, "1", None]}})
    second = _request(public_fields={"nested": {"sequence": [1, "1", None], "approved": True},
                                     "amount_minor": 1700, "action": "capture"})
    assert semantic_request_fingerprint(_descriptor(request=first)) == semantic_request_fingerprint(
        _descriptor(request=second)
    )


@pytest.mark.parametrize(
    "profile_change,request_change",
    [
        ({"operation_version": "2"}, {}),
        ({"endpoint_profile_id": "mock-endpoint-two"}, {}),
        ({"endpoint_profile_version": "2"}, {}),
        ({}, {"target": "account-redacted-18"}),
        ({}, {"public_fields": {"action": "void", "amount_minor": 1700,
                                "nested": {"approved": True, "sequence": [1, "1", None]}}}),
        ({}, {"protected_fields": {"authorization": "Bearer DIFFERENT",
                                    "payment_value": "4111111111111111"}}),
        ({}, {"mutation_options": {"notify": True, "ordered_labels": ["a", "b"]}}),
        ({}, {"mutation_options": {"notify": False, "ordered_labels": ["b", "a"]}}),
    ],
)
def test_every_mutation_semantic_change_changes_fingerprint(profile_change, request_change):
    baseline = semantic_request_fingerprint(_descriptor())
    changed = semantic_request_fingerprint(
        _descriptor(profile=_profile(**profile_change), request=_request(**request_change))
    )
    assert changed != baseline


def test_fingerprint_is_stable_in_a_fresh_process():
    expected = semantic_request_fingerprint(_descriptor())
    script = """
from tests.test_request_canonicalization import _descriptor
from aep_core.core.request_binding import semantic_request_fingerprint
print(semantic_request_fingerprint(_descriptor()))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == expected


def test_commitments_are_keyed_domain_separated_and_secret_free():
    descriptor = _descriptor()
    rendered = descriptor.model_dump_json()
    assert "CANARY-AUTH" not in rendered
    assert "4111111111111111" not in rendered
    assert {item.field_name for item in descriptor.protected_commitments} == {
        "authorization", "payment_value"
    }
    assert all(item.algorithm == "HMAC-SHA-256" for item in descriptor.protected_commitments)
    assert all(item.key_id == "commit-2026-01" for item in descriptor.protected_commitments)
    assert len({item.commitment for item in descriptor.protected_commitments}) == 2


def test_missing_or_invalid_commitment_key_fails_closed():
    profile = _profile()
    exact = build_exact_request_bytes(profile, _request())
    with pytest.raises(CommitmentKeyError):
        build_safe_descriptor(
            exact,
            profile,
            CommitmentKeyring(keys={}, active_key_id="missing"),
        )
    with pytest.raises(CommitmentKeyError):
        CommitmentKeyring(keys={"short": b"tiny"}, active_key_id="short")


@pytest.mark.parametrize(
    "request_factory",
    [
        lambda: _request(public_fields={
            "action": "AUTH-CANARY-IN-SAFE-FIELD",
            "amount_minor": 1700,
            "nested": {"approved": True, "sequence": [1, "1", None]},
        }),
        lambda: _request(public_fields={
            "action": "capture",
            "amount_minor": 1700,
            "nested": {
                "approved": True,
                "sequence": [1, "1", None],
                "arbitrary_metadata": "PII-CANARY-NESTED",
            },
        }),
        lambda: _request(mutation_options={
            "notify": False,
            "ordered_labels": ["a", "TOKEN-CANARY-NESTED"],
        }),
    ],
)
def test_recursive_typed_value_rules_reject_arbitrary_or_protected_safe_values(request_factory):
    with pytest.raises(UnsafeRequestError):
        build_exact_request_bytes(_profile(), request_factory())


@pytest.mark.parametrize(
    "target",
    [
        "https://user:password@example.invalid/path",
        "account-redacted-17?token=CANARY",
        "account-redacted-17#fragment",
    ],
)
def test_target_rejects_url_user_information_query_and_fragments(target):
    with pytest.raises(UnsafeRequestError):
        build_exact_request_bytes(_profile(), _request(target=target))


def test_exact_request_rejects_ambiguous_non_string_names_and_target():
    with pytest.raises(UnsafeRequestError):
        ExactMutationRequest(
            target=17,
            public_fields={"action": "capture"},
            protected_fields={},
            mutation_options={},
        )
    with pytest.raises(UnsafeRequestError):
        ExactMutationRequest(
            target="account-redacted-17",
            public_fields={1: "capture"},
            protected_fields={},
            mutation_options={},
        )


@pytest.mark.parametrize(
    "public_fields,protected_fields",
    [
        (
            {
                "action": "capture",
                "amount_minor": 1700,
                "nested": {
                    "approved": True,
                    "sequence": [1, "1", None],
                    "Authorization": "AUTH-CANARY-CASE",
                },
            },
            {},
        ),
        (
            {
                "action": "capture",
                "amount_minor": 1700,
                "nested": {"approved": True, "sequence": [1, "1", None]},
            },
            {"aUtHoRiZaTiOn": "AUTH-CANARY-MIXED-CASE"},
        ),
    ],
)
def test_case_variations_and_nested_protected_placement_fail_closed(
    public_fields, protected_fields
):
    with pytest.raises(UnsafeRequestError):
        request = ExactMutationRequest(
            target="account-redacted-17",
            public_fields=public_fields,
            protected_fields=protected_fields,
            mutation_options={"notify": False, "ordered_labels": ["a", "b"]},
        )
        build_exact_request_bytes(_profile(), request)


def test_attempt_binding_digest_changes_for_every_attempt_specific_field():
    base = {
        "request_fingerprint": "a" * 64,
        "request_material_ref": "vault_0123456789abcdefghijklmnop",
        "request_material_version": 1,
        "execution_id": str(uuid.uuid4()),
        "step_id": "step-a",
        "intent_id": str(uuid.uuid4()),
        "correlation_id": str(uuid.uuid4()),
        "descriptor_version": "aep.safe-request/1",
        "endpoint_profile_version": "1",
        "vault_object_version": 1,
        "created_at_ms": 1_800_000_000_000,
        "intent_creation_not_after_ms": 1_800_000_010_000,
        "dispatch_material_not_after_ms": 1_800_000_030_000,
        "retention_not_after_ms": 1_802_678_400_000,
    }
    baseline = compute_request_binding_digest(**base)
    replacements = {
        "execution_id": str(uuid.uuid4()),
        "intent_id": str(uuid.uuid4()),
        "correlation_id": str(uuid.uuid4()),
        "request_fingerprint": "b" * 64,
        "request_material_ref": "vault_zyxwvutsrqponmlkjihgfedc",
        "request_material_version": 2,
        "descriptor_version": "aep.safe-request/2",
        "endpoint_profile_version": "2",
        "vault_object_version": 2,
        "created_at_ms": base["created_at_ms"] + 1,
        "intent_creation_not_after_ms": base["intent_creation_not_after_ms"] + 1,
        "dispatch_material_not_after_ms": base["dispatch_material_not_after_ms"] + 1,
        "retention_not_after_ms": base["retention_not_after_ms"] + 1,
    }
    for field, replacement in replacements.items():
        changed = dict(base)
        changed[field] = replacement
        assert compute_request_binding_digest(**changed) != baseline, field
