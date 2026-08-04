"""P2-004 authenticated create-once request-vault regressions."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from src.core.request_vault import (
    TestOnlyInMemoryRequestVault,
    VaultAuthenticationError,
    VaultCollisionError,
    VaultExpiredError,
    VaultKeyError,
    VaultMissingError,
    VaultObjectMetadata,
    VaultUpdateForbiddenError,
)


NOW_MS = 1_800_000_000_000
MATERIAL = b'{"authorization":"Bearer VAULT-ONLY-CANARY","amount":17}'


def _metadata(**changes):
    values = {
        "locator": "vault_0123456789abcdefghijklmnop",
        "object_version": 1,
        "request_material_version": 1,
        "encryption_key_id": "vault-key-2026-01",
        "envelope_schema": "aep.mutation-request/1",
        "canonicalization_version": "aep.canonical-json/1",
        "connector_identity": "mock-connector",
        "connector_operation": "mock.non-idempotent/mutate",
        "operation_version": "1",
        "descriptor_version": "aep.safe-request/1",
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


@pytest.mark.asyncio
async def test_create_once_and_exact_readback_preserve_bytes():
    vault = _vault()
    metadata = _metadata()
    created = await vault.create_once(MATERIAL, metadata)
    read = await vault.read_exact(metadata.locator, now_ms=NOW_MS + 1)
    assert created == metadata
    assert read.material == MATERIAL
    assert read.metadata == metadata


@pytest.mark.asyncio
async def test_collision_and_update_are_rejected():
    vault = _vault()
    metadata = _metadata()
    await vault.create_once(MATERIAL, metadata)
    with pytest.raises(VaultCollisionError):
        await vault.create_once(b"replacement", metadata.model_copy(update={"material_length": 11}))
    with pytest.raises(VaultUpdateForbiddenError):
        await vault.update(metadata.locator, b"replacement")


@pytest.mark.asyncio
async def test_missing_and_expired_are_distinct_typed_failures():
    vault = _vault()
    with pytest.raises(VaultMissingError):
        await vault.read_exact("vault_zyxwvutsrqponmlkjihgfedc", now_ms=NOW_MS)
    metadata = _metadata()
    await vault.create_once(MATERIAL, metadata)
    with pytest.raises(VaultExpiredError):
        await vault.read_exact(
            metadata.locator,
            now_ms=metadata.dispatch_material_not_after_ms,
        )


@pytest.mark.asyncio
async def test_altered_ciphertext_or_authenticated_metadata_is_rejected():
    vault = _vault()
    metadata = _metadata()
    await vault.create_once(MATERIAL, metadata)
    vault.test_only_corrupt_ciphertext(metadata.locator)
    with pytest.raises(VaultAuthenticationError):
        await vault.read_exact(metadata.locator, now_ms=NOW_MS + 1)

    vault = _vault()
    await vault.create_once(MATERIAL, metadata)
    vault.test_only_replace_metadata(
        metadata.locator, metadata.model_copy(update={"intent_id": str(uuid.uuid4())})
    )
    with pytest.raises(VaultAuthenticationError):
        await vault.read_exact(metadata.locator, now_ms=NOW_MS + 1)


@pytest.mark.asyncio
async def test_wrong_or_unavailable_key_id_is_rejected():
    vault = _vault()
    metadata = _metadata()
    await vault.create_once(MATERIAL, metadata)
    vault.test_only_drop_encryption_key("vault-key-2026-01")
    with pytest.raises(VaultKeyError):
        await vault.read_exact(metadata.locator, now_ms=NOW_MS + 1)


@pytest.mark.asyncio
async def test_concurrent_create_allows_at_most_one_success():
    vault = _vault()
    metadata = _metadata()

    async def create(index):
        try:
            await vault.create_once(MATERIAL, metadata)
            return "created"
        except VaultCollisionError:
            return "collision"

    results = await asyncio.gather(*(create(index) for index in range(16)))
    assert results.count("created") == 1
    assert results.count("collision") == 15


@pytest.mark.asyncio
async def test_backing_representation_contains_no_plaintext():
    vault = _vault()
    metadata = _metadata()
    await vault.create_once(MATERIAL, metadata)
    backing = vault.test_only_backing_bytes()
    assert MATERIAL not in backing
    assert b"VAULT-ONLY-CANARY" not in backing
    assert "VAULT-ONLY-CANARY" not in repr(vault)
    assert "VAULT-ONLY-CANARY" not in repr(await vault.read_exact(
        metadata.locator, now_ms=NOW_MS + 1
    ))
