"""Complete versioned canonical vault-AAD coverage tests."""

from __future__ import annotations

import json
import uuid

import pytest

from src.core.request_binding import canonical_json_bytes
from src.core.request_vault import (
    RequestVaultError,
    TestOnlyInMemoryRequestVault,
    VaultObjectMetadata,
)


NOW_MS = 1_800_000_000_000
MATERIAL = b'{"safe":"exact-bytes"}'


def _metadata(**changes):
    values = {
        "aad_schema_version": "aep.vault-aad/1",
        "locator": "vault_0123456789abcdefghijklmnop",
        "object_version": 1,
        "request_material_version": 1,
        "encryption_algorithm": "AES-GCM",
        "encryption_key_id": "vault-key-2026-01",
        "envelope_schema": "aep.mutation-request/1",
        "canonicalization_version": "aep.canonical-json/1",
        "descriptor_version": "aep.safe-request/1",
        "connector_identity": "mock-connector",
        "connector_operation": "mock.non-idempotent/mutate",
        "operation_version": "1",
        "endpoint_profile_id": "mock-endpoint",
        "endpoint_profile_version": "1",
        "credential_binding_id": "mock-credential",
        "credential_binding_version": "1",
        "wire_codec_version": "mock-wire/1",
        "commitment_algorithm": "HMAC-SHA-256",
        "commitment_key_id": "commitment-key-2026-01",
        "execution_id": "execution-a",
        "step_id": "step-a",
        "intent_id": str(uuid.uuid4()),
        "correlation_id": str(uuid.uuid4()),
        "created_at_ms": NOW_MS,
        "intent_creation_not_after_ms": NOW_MS + 10_000,
        "dispatch_material_not_after_ms": NOW_MS + 30_000,
        "retention_not_after_ms": NOW_MS + 2_678_400_000,
        "material_length": len(MATERIAL),
    }
    values.update(changes)
    return VaultObjectMetadata(**values)


def _vault(**changes):
    values = {
        "encryption_keys": {"vault-key-2026-01": b"v" * 32},
        "active_key_id": "vault-key-2026-01",
        "test_only_acknowledgement": True,
    }
    values.update(changes)
    return TestOnlyInMemoryRequestVault(**values)


def _changed_value(metadata, field):
    value = getattr(metadata, field)
    if isinstance(value, str):
        if field == "locator":
            return "vault_zyxwvutsrqponmlkjihgfedc"
        if field == "encryption_key_id":
            return "missing-vault-key"
        return value + "-changed"
    if field == "object_version":
        return 2
    if field == "request_material_version":
        return 2
    if field == "material_length":
        return value + 1
    return value + 1


def test_aad_schema_covers_every_security_relevant_metadata_field():
    metadata = _metadata()
    required = {
        "aad_schema_version",
        "locator",
        "object_version",
        "request_material_version",
        "encryption_algorithm",
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
        "created_at_ms",
        "intent_creation_not_after_ms",
        "dispatch_material_not_after_ms",
        "retention_not_after_ms",
        "material_length",
    }
    assert set(metadata.model_dump(mode="json")) == required
    assert metadata.authenticated_bytes() == canonical_json_bytes(
        metadata.model_dump(mode="json")
    )
    assert json.loads(metadata.authenticated_bytes())["aad_schema_version"] == "aep.vault-aad/1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    [
        "aad_schema_version",
        "locator",
        "object_version",
        "request_material_version",
        "encryption_algorithm",
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
        "created_at_ms",
        "intent_creation_not_after_ms",
        "dispatch_material_not_after_ms",
        "retention_not_after_ms",
        "material_length",
    ],
)
async def test_changing_any_authenticated_metadata_field_is_rejected(field):
    vault = _vault()
    metadata = _metadata()
    await vault.create_once(MATERIAL, metadata)
    replacement = metadata.model_copy(
        update={field: _changed_value(metadata, field)}
    )
    vault.test_only_replace_metadata(metadata.locator, replacement)
    with pytest.raises(RequestVaultError):
        await vault.read_exact(metadata.locator, now_ms=NOW_MS + 1)


@pytest.mark.asyncio
async def test_authenticated_readback_preserves_exact_bytes_and_backing_has_no_plaintext():
    vault = _vault()
    metadata = _metadata()
    await vault.create_once(MATERIAL, metadata)
    readback = await vault.read_exact(metadata.locator, now_ms=NOW_MS + 1)
    assert readback.material == MATERIAL
    assert readback.metadata == metadata
    assert MATERIAL not in vault.test_only_backing_bytes()
    assert MATERIAL.decode("utf-8") not in repr(vault)
