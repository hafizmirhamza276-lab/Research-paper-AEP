"""Authenticated create-once request-vault boundary for P2-004.

Only the interface and an explicitly acknowledged test-only in-memory backend
are implemented here.  Production composition must supply a separately
reviewed durable vault/KMS backend; this module never falls back to plaintext.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_LOCATOR = re.compile(r"^vault_[A-Za-z0-9_-]{24,96}$")
AAD_SCHEMA_VERSION = "aep.vault-aad/1"
ENCRYPTION_ALGORITHM = "AES-GCM"


class RequestVaultError(Exception):
    """Stable safe base error; messages contain reason codes only."""

    reason_code = "request-vault-error"

    def __init__(self) -> None:
        super().__init__(self.reason_code)


class VaultCollisionError(RequestVaultError):
    reason_code = "vault-locator-collision"


class VaultUpdateForbiddenError(RequestVaultError):
    reason_code = "vault-update-forbidden"


class VaultMissingError(RequestVaultError):
    reason_code = "vault-object-missing"


class VaultExpiredError(RequestVaultError):
    reason_code = "vault-object-expired"


class VaultAuthenticationError(RequestVaultError):
    reason_code = "vault-authentication-failed"


class VaultKeyError(RequestVaultError):
    reason_code = "vault-key-unavailable"


class VaultVersionError(RequestVaultError):
    reason_code = "vault-version-unsupported"


class VaultConfigurationError(RequestVaultError):
    reason_code = "vault-configuration-invalid"


class VaultObjectMetadata(BaseModel):
    """Safe authenticated metadata; it contains no nonce, tag, or request."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, hide_input_in_errors=True
    )

    aad_schema_version: str = AAD_SCHEMA_VERSION
    locator: str
    object_version: int = Field(strict=True, ge=1, le=1)
    request_material_version: int = Field(strict=True, ge=1, le=1)
    encryption_algorithm: str = ENCRYPTION_ALGORITHM
    encryption_key_id: str
    envelope_schema: str
    canonicalization_version: str
    descriptor_version: str
    connector_identity: str
    connector_operation: str
    operation_version: str
    endpoint_profile_id: str
    endpoint_profile_version: str
    credential_binding_id: str
    credential_binding_version: str
    wire_codec_version: str
    commitment_algorithm: str
    commitment_key_id: str
    execution_id: str
    step_id: str
    intent_id: str
    correlation_id: str
    created_at_ms: int = Field(strict=True, ge=0)
    intent_creation_not_after_ms: int = Field(strict=True, ge=0)
    dispatch_material_not_after_ms: int = Field(strict=True, ge=0)
    retention_not_after_ms: int = Field(strict=True, ge=0)
    material_length: int = Field(strict=True, ge=1, le=1_048_576)

    @field_validator(
        "aad_schema_version",
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
    )
    @classmethod
    def _safe_identifier(cls, value: str) -> str:
        if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
            raise ValueError("vault metadata contains an invalid safe identifier")
        return value

    @field_validator("locator")
    @classmethod
    def _opaque_locator(cls, value: str) -> str:
        if not isinstance(value, str) or _LOCATOR.fullmatch(value) is None:
            raise ValueError("vault locator must be opaque and non-semantic")
        return value

    @model_validator(mode="after")
    def _deadlines(self) -> "VaultObjectMetadata":
        if self.aad_schema_version != AAD_SCHEMA_VERSION:
            raise ValueError("unsupported vault AAD schema")
        if self.encryption_algorithm != ENCRYPTION_ALGORITHM:
            raise ValueError("unsupported vault encryption algorithm")
        if not (
            self.created_at_ms <= self.intent_creation_not_after_ms
            < self.dispatch_material_not_after_ms
            <= self.retention_not_after_ms
        ):
            raise ValueError("vault authenticated deadlines are inconsistent")
        return self

    def authenticated_bytes(self) -> bytes:
        # The lazy import avoids a module cycle while guaranteeing that vault
        # AAD uses the exact request-binding canonicalizer and its limits.
        from src.core.request_binding import canonical_json_bytes

        return canonical_json_bytes(self.model_dump(mode="json"))


@dataclass(frozen=True, repr=False)
class VaultReadResult:
    material: bytes
    metadata: VaultObjectMetadata

    def __repr__(self) -> str:
        return (
            "VaultReadResult(material=<protected>, "
            f"locator={self.metadata.locator!r}, version={self.metadata.object_version})"
        )


@runtime_checkable
class RequestVault(Protocol):
    test_only: bool
    active_key_id: str

    async def create_once(
        self, material: bytes, metadata: VaultObjectMetadata
    ) -> VaultObjectMetadata: ...

    async def read_exact(self, locator: str, *, now_ms: int) -> VaultReadResult: ...


@dataclass(frozen=True)
class _StoredCiphertext:
    nonce: bytes
    ciphertext: bytes
    metadata: VaultObjectMetadata


class TestOnlyInMemoryRequestVault:
    """TEST-ONLY AES-GCM vault; not durable and never production-capable."""

    __test__ = False
    test_only = True

    def __init__(
        self,
        *,
        encryption_keys: Mapping[str, bytes],
        active_key_id: str,
        test_only_acknowledgement: bool,
    ) -> None:
        if test_only_acknowledgement is not True:
            raise VaultConfigurationError()
        copied: dict[str, bytes] = {}
        for key_id, key in encryption_keys.items():
            if _SAFE_ID.fullmatch(key_id) is None or not isinstance(key, bytes):
                raise VaultConfigurationError()
            if len(key) not in {16, 24, 32}:
                raise VaultConfigurationError()
            copied[key_id] = bytes(key)
        if active_key_id not in copied:
            raise VaultConfigurationError()
        self._keys = copied
        self.active_key_id = active_key_id
        self._objects: dict[str, _StoredCiphertext] = {}
        self._lock = asyncio.Lock()

    def __repr__(self) -> str:
        return "TestOnlyInMemoryRequestVault(objects=<protected>, keys=<redacted>)"

    async def create_once(
        self, material: bytes, metadata: VaultObjectMetadata
    ) -> VaultObjectMetadata:
        if not isinstance(material, bytes) or len(material) != metadata.material_length:
            raise VaultConfigurationError()
        if metadata.object_version != 1:
            raise VaultVersionError()
        if metadata.encryption_key_id != self.active_key_id:
            raise VaultKeyError()
        key = self._keys.get(metadata.encryption_key_id)
        if key is None:
            raise VaultKeyError()
        async with self._lock:
            if metadata.locator in self._objects:
                raise VaultCollisionError()
            nonce = os.urandom(12)
            ciphertext = AESGCM(key).encrypt(
                nonce, material, metadata.authenticated_bytes()
            )
            self._objects[metadata.locator] = _StoredCiphertext(
                nonce=nonce,
                ciphertext=ciphertext,
                metadata=metadata,
            )
        return metadata

    async def read_exact(self, locator: str, *, now_ms: int) -> VaultReadResult:
        if type(now_ms) is not int or now_ms < 0 or _LOCATOR.fullmatch(locator) is None:
            raise VaultConfigurationError()
        stored = self._objects.get(locator)
        if stored is None:
            raise VaultMissingError()
        metadata = stored.metadata
        if metadata.object_version != 1:
            raise VaultVersionError()
        if now_ms >= metadata.dispatch_material_not_after_ms:
            raise VaultExpiredError()
        key = self._keys.get(metadata.encryption_key_id)
        if key is None:
            raise VaultKeyError()
        try:
            material = AESGCM(key).decrypt(
                stored.nonce,
                stored.ciphertext,
                metadata.authenticated_bytes(),
            )
        except InvalidTag:
            raise VaultAuthenticationError() from None
        if len(material) != metadata.material_length:
            raise VaultAuthenticationError()
        return VaultReadResult(material=material, metadata=metadata)

    async def update(self, locator: str, material: bytes) -> None:
        """There is intentionally no update path, including in tests."""

        raise VaultUpdateForbiddenError()

    # Controlled altered-state hooks. They are deliberately named test-only
    # and exist solely to prove authenticated failure behavior.
    def test_only_corrupt_ciphertext(self, locator: str) -> None:
        stored = self._objects[locator]
        changed = bytearray(stored.ciphertext)
        changed[0] ^= 1
        self._objects[locator] = _StoredCiphertext(
            nonce=stored.nonce,
            ciphertext=bytes(changed),
            metadata=stored.metadata,
        )

    def test_only_replace_metadata(
        self, locator: str, metadata: VaultObjectMetadata
    ) -> None:
        stored = self._objects[locator]
        self._objects[locator] = _StoredCiphertext(
            nonce=stored.nonce,
            ciphertext=stored.ciphertext,
            metadata=metadata,
        )

    def test_only_drop_encryption_key(self, key_id: str) -> None:
        self._keys.pop(key_id, None)

    def test_only_backing_bytes(self) -> bytes:
        chunks: list[bytes] = []
        for locator in sorted(self._objects):
            stored = self._objects[locator]
            chunks.extend(
                [
                    stored.nonce,
                    stored.ciphertext,
                    stored.metadata.authenticated_bytes(),
                ]
            )
        return b"".join(chunks)


class EvaluationRedisRequestVault:
    """Durable AES-GCM create-once vault for the EVALUATION composition.

    Semantics are identical to the production contract: create-once, no update
    path, authenticated metadata as AAD, exact-length verification, and
    dispatch-window expiry.  Two properties are deliberately weaker than the
    production vault/KMS design in ``docs/15-production-vault-kms-design.md``
    and are declared, not hidden:

    1. **Shared trust domain.** Ciphertext lives in the same Redis instance as
       execution state, so it inherits that instance's access boundary rather
       than a separate KMS boundary.
    2. **Locally supplied keys.** Encryption keys are passed in by the operator
       instead of being wrapped by a KMS, so there is no key rotation,
       attestation, or hardware protection.

    It is therefore ``evaluation_only``.  It is *not* ``test_only``: it is
    durable and is the composition an evaluation harness measures.
    """

    test_only = False
    evaluation_only = True

    KEY_PREFIX = "aep:vault:"

    def __init__(
        self,
        *,
        redis_client,
        encryption_keys: Mapping[str, bytes],
        active_key_id: str,
    ) -> None:
        copied: dict[str, bytes] = {}
        for key_id, key in encryption_keys.items():
            if _SAFE_ID.fullmatch(key_id) is None or not isinstance(key, bytes):
                raise VaultConfigurationError()
            if len(key) not in {16, 24, 32}:
                raise VaultConfigurationError()
            copied[key_id] = bytes(key)
        if active_key_id not in copied:
            raise VaultConfigurationError()
        self.redis = redis_client
        self._keys = copied
        self.active_key_id = active_key_id

    def __repr__(self) -> str:
        return "EvaluationRedisRequestVault(objects=<protected>, keys=<redacted>)"

    def object_key(self, locator: str) -> str:
        return f"{self.KEY_PREFIX}{locator}"

    async def create_once(
        self, material: bytes, metadata: VaultObjectMetadata
    ) -> VaultObjectMetadata:
        if not isinstance(material, bytes) or len(material) != metadata.material_length:
            raise VaultConfigurationError()
        if metadata.object_version != 1:
            raise VaultVersionError()
        if metadata.encryption_key_id != self.active_key_id:
            raise VaultKeyError()
        key = self._keys.get(metadata.encryption_key_id)
        if key is None:
            raise VaultKeyError()
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(
            nonce, material, metadata.authenticated_bytes()
        )
        record = json.dumps(
            {
                "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
                "ciphertext": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
                "metadata": metadata.model_dump(mode="json"),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        # Retention is bounded by the authenticated retention deadline; a
        # 1-second floor keeps Redis from rejecting a non-positive TTL.
        ttl_ms = max(
            1_000, metadata.retention_not_after_ms - metadata.created_at_ms
        )
        created = await self.redis.set(
            self.object_key(metadata.locator),
            record,
            nx=True,
            px=ttl_ms,
        )
        if not created:
            raise VaultCollisionError()
        return metadata

    async def read_exact(self, locator: str, *, now_ms: int) -> VaultReadResult:
        if type(now_ms) is not int or now_ms < 0 or _LOCATOR.fullmatch(locator) is None:
            raise VaultConfigurationError()
        raw = await self.redis.get(self.object_key(locator))
        if raw is None:
            raise VaultMissingError()
        try:
            record = json.loads(
                raw.decode("utf-8") if isinstance(raw, bytes) else raw
            )
            metadata = VaultObjectMetadata.model_validate(record["metadata"])
            nonce = base64.urlsafe_b64decode(record["nonce"])
            ciphertext = base64.urlsafe_b64decode(record["ciphertext"])
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise VaultAuthenticationError() from None
        # A record moved to another locator is not authentic for that locator.
        if metadata.locator != locator:
            raise VaultAuthenticationError()
        if metadata.object_version != 1:
            raise VaultVersionError()
        if now_ms >= metadata.dispatch_material_not_after_ms:
            raise VaultExpiredError()
        key = self._keys.get(metadata.encryption_key_id)
        if key is None:
            raise VaultKeyError()
        try:
            material = AESGCM(key).decrypt(
                nonce, ciphertext, metadata.authenticated_bytes()
            )
        except InvalidTag:
            raise VaultAuthenticationError() from None
        if len(material) != metadata.material_length:
            raise VaultAuthenticationError()
        return VaultReadResult(material=material, metadata=metadata)

    async def update(self, locator: str, material: bytes) -> None:
        """There is intentionally no update path in any composition."""

        raise VaultUpdateForbiddenError()
