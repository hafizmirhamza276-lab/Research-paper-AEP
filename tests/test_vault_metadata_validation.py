"""Coverage for the vault's authenticated-metadata validators.

`VaultObjectMetadata` is the AAD for the vault's AEAD: every field in it is
authenticated, so a value that should never have been accepted becomes a
value that is cryptographically bound to the ciphertext. Validation has to
refuse at construction, not at read time.

Three classes of rejection are pinned here:

  * identifier fields must be safe identifiers, so metadata cannot smuggle
    arbitrary bytes into the AAD;
  * the locator must be opaque, so it cannot leak request semantics into a
    key name that appears in logs and keyspace scans;
  * the four deadlines must be strictly ordered, so material cannot outlive
    the intent that authorised it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aep_core.core.request_vault import (
    AAD_SCHEMA_VERSION,
    ENCRYPTION_ALGORITHM,
    VaultObjectMetadata,
)
from tests.test_request_vault import NOW_MS, _metadata

IDENTIFIER_FIELDS = [
    "encryption_key_id",
    "envelope_schema",
    "canonicalization_version",
    "descriptor_version",
    "connector_identity",
    "connector_operation",
    "operation_version",
    "endpoint_profile_id",
    "endpoint_profile_version",
    "credential_binding_id",
    "credential_binding_version",
    "wire_codec_version",
    "commitment_algorithm",
    "commitment_key_id",
    "execution_id",
    "step_id",
    "intent_id",
    "correlation_id",
]


def test_the_baseline_metadata_is_valid():
    """Guards the rest of this file: every case below changes one thing."""
    assert _metadata().locator == "vault_0123456789abcdefghijklmnop"


# ===========================================================================
# Identifier fields
# ===========================================================================


@pytest.mark.parametrize("field", IDENTIFIER_FIELDS)
@pytest.mark.parametrize("value", ["has space", "-leading", "", "x" * 200])
def test_identifier_fields_refuse_unsafe_values(field, value):
    with pytest.raises(ValidationError):
        _metadata(**{field: value})


@pytest.mark.parametrize("field", IDENTIFIER_FIELDS)
@pytest.mark.parametrize("value", [None, 42])
def test_identifier_fields_refuse_non_strings(field, value):
    with pytest.raises(ValidationError):
        _metadata(**{field: value})


@pytest.mark.parametrize("field", IDENTIFIER_FIELDS)
def test_identifier_fields_accept_bytes_by_pydantic_coercion(field):
    """Documented behaviour, not an oversight.

    The model runs in pydantic's default (lax) mode, so ASCII bytes are
    decoded to str before the safe-identifier validator sees them. The
    authenticated value is therefore the decoded text. This is benign --
    the decoded value still has to satisfy the safe-identifier pattern --
    but it is pinned so a future switch to strict mode is a deliberate,
    visible change rather than a silent one.
    """
    metadata = _metadata(**{field: b"coerced-value"})

    assert getattr(metadata, field) == "coerced-value"


@pytest.mark.parametrize("field", IDENTIFIER_FIELDS)
def test_bytes_that_do_not_decode_to_a_safe_identifier_are_still_refused(field):
    with pytest.raises(ValidationError):
        _metadata(**{field: b"has space"})


@pytest.mark.parametrize("value", ["newline\nid", "tab\tid", "null\x00id"])
def test_identifier_fields_refuse_control_characters(value):
    """Control bytes in AAD would be authenticated and then logged verbatim."""
    with pytest.raises(ValidationError):
        _metadata(execution_id=value)


# ===========================================================================
# Locator opacity
# ===========================================================================


@pytest.mark.parametrize(
    "value",
    [
        "customer-4471-invoice",           # semantic, and no vault_ prefix
        "vault_tooshort",                  # below the 24-char body minimum
        "vault_" + "a" * 97,               # above the 96-char body maximum
        "vault_has space0123456789abcdef",  # space outside the charset
        "vault_dots.0123456789abcdefghij",  # '.' outside the charset
        "",
        None,
        42,
    ],
)
def test_a_non_opaque_locator_is_refused(value):
    with pytest.raises(ValidationError):
        _metadata(locator=value)


@pytest.mark.parametrize(
    "value",
    [
        "vault_" + "a" * 24,               # minimum body length
        "vault_" + "a" * 96,               # maximum body length
        "vault_MiXeDcAsE0123456789_-abc",  # the charset is case-insensitive
    ],
)
def test_an_opaque_locator_within_the_pattern_is_accepted(value):
    assert _metadata(locator=value).locator == value


# ===========================================================================
# Schema and algorithm pinning
# ===========================================================================


@pytest.mark.parametrize("value", ["aep.vault-aad/0", "aep.vault-aad/2", "other"])
def test_an_unsupported_aad_schema_is_refused(value):
    with pytest.raises(ValidationError, match="unsupported vault AAD schema"):
        _metadata(aad_schema_version=value)


@pytest.mark.parametrize("value", ["AES-128-GCM", "ChaCha20", "none"])
def test_an_unsupported_encryption_algorithm_is_refused(value):
    with pytest.raises(ValidationError, match="unsupported vault encryption algorithm"):
        _metadata(encryption_algorithm=value)


def test_the_pinned_defaults_are_the_supported_ones():
    metadata = _metadata()

    assert metadata.aad_schema_version == AAD_SCHEMA_VERSION
    assert metadata.encryption_algorithm == ENCRYPTION_ALGORITHM


# ===========================================================================
# Deadline ordering: created <= intent < dispatch <= retention
# ===========================================================================


def test_deadlines_in_the_correct_order_are_accepted():
    assert _metadata().created_at_ms == NOW_MS


@pytest.mark.parametrize(
    "changes",
    [
        # intent creation before the object was created
        {"intent_creation_not_after_ms": NOW_MS - 1},
        # dispatch material outliving nothing -- must be strictly after intent
        {"dispatch_material_not_after_ms": NOW_MS + 10_000},
        {"dispatch_material_not_after_ms": NOW_MS + 5_000},
        # retention shorter than the dispatch window
        {"retention_not_after_ms": NOW_MS + 20_000},
    ],
)
def test_inconsistent_deadlines_are_refused(changes):
    with pytest.raises(ValidationError, match="deadlines are inconsistent"):
        _metadata(**changes)


def test_touching_boundaries_are_permitted_where_the_order_is_non_strict():
    """created == intent and dispatch == retention are both allowed."""
    _metadata(intent_creation_not_after_ms=NOW_MS)
    _metadata(
        dispatch_material_not_after_ms=NOW_MS + 30_000,
        retention_not_after_ms=NOW_MS + 30_000,
    )


@pytest.mark.parametrize("field", [
    "created_at_ms",
    "intent_creation_not_after_ms",
    "dispatch_material_not_after_ms",
    "retention_not_after_ms",
])
@pytest.mark.parametrize("value", [-1, 1.5, "0", True, None])
def test_deadlines_must_be_non_negative_integers(field, value):
    with pytest.raises(ValidationError):
        _metadata(**{field: value})


# ===========================================================================
# Bounded integers
# ===========================================================================


@pytest.mark.parametrize("value", [0, -1, 1_048_577, 1.5, "10", True, None])
def test_material_length_is_bounded(value):
    with pytest.raises(ValidationError):
        _metadata(material_length=value)


@pytest.mark.parametrize("field", ["object_version", "request_material_version"])
@pytest.mark.parametrize("value", [0, 2, -1, 1.5, "1", True, None])
def test_versions_are_pinned_to_exactly_one(field, value):
    """Widening a version is a schema change, not a runtime input."""
    with pytest.raises(ValidationError):
        _metadata(**{field: value})


# ===========================================================================
# Model hygiene
# ===========================================================================


def test_unknown_fields_are_refused():
    with pytest.raises(ValidationError):
        _metadata(smuggled_field="value")


def test_metadata_is_frozen():
    metadata = _metadata()

    with pytest.raises(ValidationError):
        metadata.execution_id = "other"


def test_authenticated_bytes_are_deterministic():
    """Pin the ids: the shared _metadata() helper randomises them per call."""
    fixed = {
        "intent_id": "11111111-1111-4111-8111-111111111111",
        "correlation_id": "22222222-2222-4222-8222-222222222222",
    }

    assert _metadata(**fixed).authenticated_bytes() == _metadata(
        **fixed
    ).authenticated_bytes()


def test_authenticated_bytes_change_with_any_authenticated_field():
    fixed = {
        "intent_id": "11111111-1111-4111-8111-111111111111",
        "correlation_id": "22222222-2222-4222-8222-222222222222",
    }
    baseline = _metadata(**fixed).authenticated_bytes()

    assert _metadata(**fixed, step_id="step-b").authenticated_bytes() != baseline
