"""Versioned immutable request binding and safe-value boundary.

The semantic fingerprint and the attempt-specific request-binding digest are
separate SHA-256 constructions. Protected values use dedicated keyed,
domain-separated HMAC commitments and appear in cleartext only in exact vault
material or an explicitly authorized verified-dispatch object.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
import unicodedata
import uuid
import weakref
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aep_core.core.request_vault import (
    RequestVault,
    VaultAuthenticationError,
    VaultObjectMetadata,
)


CANONICALIZATION_VERSION = "aep.canonical-json/1"
ENVELOPE_SCHEMA = "aep.mutation-request/1"
DESCRIPTOR_VERSION = "aep.safe-request/1"
BINDING_SCHEMA_VERSION = "aep.persisted-request-binding/1"
FINGERPRINT_DOMAIN = "AEP_REQUEST_FINGERPRINT_V1"
BINDING_DOMAIN = "AEP_ATTEMPT_REQUEST_BINDING_V1"
COMMITMENT_DOMAIN = b"AEP_SENSITIVE_FIELD_V1"
COMMITMENT_ALGORITHM = "HMAC-SHA-256"

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_SAFE_FIELD = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LOCATOR = re.compile(r"^vault_[A-Za-z0-9_-]{24,96}$")
_SENSITIVE_NAME_TOKENS = frozenset(
    {
        "authorization", "auth", "cookie", "credential", "password", "passwd",
        "secret", "token", "pan", "card", "cvv", "cvc", "payment", "email",
        "phone", "address", "name", "ssn", "personal", "pii", "header",
        "query", "metadata",
    }
)
_MAX_SAFE_INTEGER = (1 << 53) - 1
_MAX_CANONICAL_BYTES = 1_048_576
_MAX_CANONICAL_DEPTH = 128


class RequestBindingError(Exception):
    reason_code = "request-binding-error"

    def __init__(self) -> None:
        super().__init__(self.reason_code)


class CanonicalizationError(RequestBindingError):
    reason_code = "canonicalization-rejected"


class UnsafeRequestError(RequestBindingError):
    reason_code = "unsafe-request-rejected"


class CommitmentKeyError(RequestBindingError):
    reason_code = "commitment-key-unavailable"


class RequestBindingMismatchError(RequestBindingError):
    reason_code = "request-binding-mismatch"


class RequestBindingExpiredError(RequestBindingError):
    reason_code = "request-binding-expired"


class UnsupportedRequestVersionError(RequestBindingError):
    reason_code = "request-version-unsupported"


class ProtectedFieldClass(str, Enum):
    SENSITIVE_SEMANTIC = "SENSITIVE_SEMANTIC"
    SECRET_AUTH = "SECRET_AUTH"
    TOKEN = "TOKEN"
    COOKIE = "COOKIE"
    PAYMENT = "PAYMENT"
    PERSONAL_INFORMATION = "PERSONAL_INFORMATION"


class SafeValueKind(str, Enum):
    NULL = "null"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    STRING = "string"
    ARRAY = "array"
    OBJECT = "object"
    ONE_OF = "one_of"


@dataclass(frozen=True, repr=False)
class SafeValueRule:
    """Recursive, code-owned allowlist for one persisted semantic value."""

    kind: SafeValueKind
    allowed_strings: frozenset[str] = frozenset()
    minimum_integer: int | None = None
    maximum_integer: int | None = None
    array_item: "SafeValueRule | None" = None
    maximum_items: int = 64
    object_fields: Mapping[str, "SafeValueRule"] | None = None
    variants: tuple["SafeValueRule", ...] = ()

    def __post_init__(self) -> None:
        try:
            kind = SafeValueKind(self.kind)
        except (TypeError, ValueError):
            raise UnsafeRequestError() from None
        object.__setattr__(self, "kind", kind)
        strings = frozenset(self.allowed_strings)
        for value in strings:
            if type(value) is not str or _SAFE_ID.fullmatch(value) is None:
                raise UnsafeRequestError()
            _require_nfc(value)
        object.__setattr__(self, "allowed_strings", strings)
        if type(self.maximum_items) is not int or not 0 <= self.maximum_items <= 256:
            raise UnsafeRequestError()
        if self.minimum_integer is not None and type(self.minimum_integer) is not int:
            raise UnsafeRequestError()
        if self.maximum_integer is not None and type(self.maximum_integer) is not int:
            raise UnsafeRequestError()
        if (
            self.minimum_integer is not None
            and self.maximum_integer is not None
            and self.minimum_integer > self.maximum_integer
        ):
            raise UnsafeRequestError()

        supplied_object_fields = self.object_fields
        fields: dict[str, SafeValueRule] = {}
        if supplied_object_fields is not None:
            if type(supplied_object_fields) is not dict:
                raise UnsafeRequestError()
            for name, rule in supplied_object_fields.items():
                _validate_safe_field_name(name)
                if not isinstance(rule, SafeValueRule):
                    raise UnsafeRequestError()
                fields[name] = rule
        object.__setattr__(self, "object_fields", MappingProxyType(fields))
        variants = tuple(self.variants)
        if any(not isinstance(rule, SafeValueRule) for rule in variants):
            raise UnsafeRequestError()
        object.__setattr__(self, "variants", variants)

        if kind is SafeValueKind.STRING and not strings:
            raise UnsafeRequestError()
        if kind is SafeValueKind.ARRAY and not isinstance(self.array_item, SafeValueRule):
            raise UnsafeRequestError()
        if kind is SafeValueKind.OBJECT and supplied_object_fields is None:
            raise UnsafeRequestError()
        if kind is SafeValueKind.ONE_OF and not 2 <= len(variants) <= 8:
            raise UnsafeRequestError()

    def __repr__(self) -> str:
        return f"SafeValueRule(kind={self.kind.value!r}, values=<allowlisted>)"


def _validate_safe_value(value: Any, rule: SafeValueRule) -> None:
    if rule.kind is SafeValueKind.ONE_OF:
        matches = 0
        for variant in rule.variants:
            try:
                _validate_safe_value(value, variant)
            except (UnsafeRequestError, CanonicalizationError):
                continue
            matches += 1
        if matches != 1:
            raise UnsafeRequestError()
        return
    if rule.kind is SafeValueKind.NULL:
        if value is not None:
            raise UnsafeRequestError()
        return
    if rule.kind is SafeValueKind.BOOLEAN:
        if type(value) is not bool:
            raise UnsafeRequestError()
        return
    if rule.kind is SafeValueKind.INTEGER:
        if type(value) is not int:
            raise UnsafeRequestError()
        if rule.minimum_integer is not None and value < rule.minimum_integer:
            raise UnsafeRequestError()
        if rule.maximum_integer is not None and value > rule.maximum_integer:
            raise UnsafeRequestError()
        return
    if rule.kind is SafeValueKind.STRING:
        if type(value) is not str or value not in rule.allowed_strings:
            raise UnsafeRequestError()
        return
    if rule.kind is SafeValueKind.ARRAY:
        if type(value) is not list or len(value) > rule.maximum_items:
            raise UnsafeRequestError()
        assert rule.array_item is not None
        for item in value:
            _validate_safe_value(item, rule.array_item)
        return
    if rule.kind is SafeValueKind.OBJECT:
        if type(value) is not dict or set(value) != set(rule.object_fields):
            raise UnsafeRequestError()
        for name, member in value.items():
            _validate_safe_value(member, rule.object_fields[name])
        return
    raise UnsafeRequestError()


def _require_nfc(value: str) -> str:
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise CanonicalizationError() from None
    if unicodedata.normalize("NFC", value) != value or len(encoded) > 8_192:
        raise CanonicalizationError()
    return value


def _canonical_value(
    value: Any,
    *,
    path: str = "$",
    safe_names: bool = False,
    depth: int = 0,
) -> Any:
    if depth > _MAX_CANONICAL_DEPTH:
        raise CanonicalizationError()
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if abs(value) > _MAX_SAFE_INTEGER:
            raise CanonicalizationError()
        return value
    if type(value) is str:
        return _require_nfc(value)
    if type(value) in {list, tuple}:
        return [
            _canonical_value(
                item,
                path=f"{path}[{index}]",
                safe_names=safe_names,
                depth=depth + 1,
            )
            for index, item in enumerate(value)
        ]
    if type(value) is dict:
        result: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise CanonicalizationError()
            key = _require_nfc(key)
            if key in result:
                raise CanonicalizationError()
            if safe_names:
                _validate_safe_field_name(key)
            result[key] = _canonical_value(
                item,
                path=f"{path}.{key}",
                safe_names=safe_names,
                depth=depth + 1,
            )
        return result
    raise CanonicalizationError()


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic NFC UTF-8 JSON under canonicalization v1.

    Floats are intentionally unsupported. The request schema represents times
    as integer epoch milliseconds and monetary values as integer minor units.
    """

    canonical = _canonical_value(value)
    try:
        encoded = json.dumps(
            canonical,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", errors="strict")
        if len(encoded) > _MAX_CANONICAL_BYTES:
            raise CanonicalizationError()
        return encoded
    except (TypeError, ValueError, UnicodeError):
        raise CanonicalizationError() from None


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalizationError()
        result[key] = value
    return result


def _decode_canonical(raw: bytes) -> Any:
    if not isinstance(raw, bytes) or len(raw) > _MAX_CANONICAL_BYTES:
        raise CanonicalizationError()
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_pairs,
            parse_float=lambda _: (_ for _ in ()).throw(CanonicalizationError()),
            parse_constant=lambda _: (_ for _ in ()).throw(CanonicalizationError()),
        )
    except RequestBindingError:
        raise
    except (json.JSONDecodeError, UnicodeError, RecursionError, ValueError, TypeError):
        raise CanonicalizationError() from None
    if canonical_json_bytes(value) != raw:
        raise CanonicalizationError()
    return value


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _validate_safe_field_name(value: str) -> str:
    if _SAFE_FIELD.fullmatch(value) is None:
        raise UnsafeRequestError()
    components = frozenset(_normalized_name(value).split("_"))
    if components & _SENSITIVE_NAME_TOKENS:
        raise UnsafeRequestError()
    return value


def _safe_identifier(value: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise UnsafeRequestError()
    _require_nfc(value)
    return value


@dataclass(frozen=True)
class EndpointProfile:
    """One explicit versioned endpoint/request schema; not a connector registry."""

    connector_identity: str
    connector_operation: str
    operation_version: str
    endpoint_profile_id: str
    endpoint_profile_version: str
    credential_binding_id: str
    credential_binding_version: str
    wire_codec_version: str
    public_field_rules: Mapping[str, SafeValueRule]
    protected_field_classes: Mapping[str, ProtectedFieldClass]
    mutation_option_rules: Mapping[str, SafeValueRule]

    def __post_init__(self) -> None:
        for value in (
            self.connector_identity,
            self.connector_operation,
            self.operation_version,
            self.endpoint_profile_id,
            self.endpoint_profile_version,
            self.credential_binding_id,
            self.credential_binding_version,
            self.wire_codec_version,
        ):
            _safe_identifier(value)
        if type(self.public_field_rules) is not dict or type(self.mutation_option_rules) is not dict:
            raise UnsafeRequestError()
        public: dict[str, SafeValueRule] = {}
        for name, rule in self.public_field_rules.items():
            _validate_safe_field_name(name)
            if not isinstance(rule, SafeValueRule):
                raise UnsafeRequestError()
            public[name] = rule
        options: dict[str, SafeValueRule] = {}
        for name, rule in self.mutation_option_rules.items():
            _validate_safe_field_name(name)
            if not isinstance(rule, SafeValueRule):
                raise UnsafeRequestError()
            options[name] = rule
        protected: dict[str, ProtectedFieldClass] = {}
        for name, classification in self.protected_field_classes.items():
            if _SAFE_FIELD.fullmatch(name) is None:
                raise UnsafeRequestError()
            try:
                protected[name] = ProtectedFieldClass(classification)
            except (TypeError, ValueError):
                raise UnsafeRequestError() from None
        if (public.keys() & options.keys()) or (public.keys() & protected.keys()) or (options.keys() & protected.keys()):
            raise UnsafeRequestError()
        object.__setattr__(self, "public_field_rules", MappingProxyType(public))
        object.__setattr__(self, "mutation_option_rules", MappingProxyType(options))
        object.__setattr__(self, "protected_field_classes", MappingProxyType(protected))


class ExactMutationRequest:
    """Defensively copied request input with a constant safe representation."""

    __slots__ = ("_target", "_public", "_protected", "_options")

    def __init__(
        self,
        *,
        target: str,
        public_fields: Mapping[str, Any],
        protected_fields: Mapping[str, str | bytes],
        mutation_options: Mapping[str, Any],
    ) -> None:
        if not all(type(value) is dict for value in (public_fields, protected_fields, mutation_options)):
            raise UnsafeRequestError()
        if type(target) is not str:
            raise UnsafeRequestError()
        for mapping in (public_fields, protected_fields, mutation_options):
            if any(type(name) is not str for name in mapping):
                raise UnsafeRequestError()
        self._target = target
        self._public = tuple(
            (name, canonical_json_bytes(_canonical_value(value, safe_names=True)))
            for name, value in sorted(public_fields.items())
        )
        protected: list[tuple[str, str, bytes]] = []
        for name, value in sorted(protected_fields.items()):
            if type(value) is str:
                protected.append((name, "utf8", _require_nfc(value).encode("utf-8")))
            elif type(value) is bytes:
                protected.append((name, "bytes", bytes(value)))
            else:
                raise UnsafeRequestError()
        self._protected = tuple(protected)
        self._options = tuple(
            (name, canonical_json_bytes(_canonical_value(value, safe_names=True)))
            for name, value in sorted(mutation_options.items())
        )

    def __repr__(self) -> str:
        return "ExactMutationRequest(material=<protected>)"


def _validate_target(target: str) -> str:
    target = _require_nfc(target)
    if not target or len(target.encode("utf-8")) > 512:
        raise UnsafeRequestError()
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.username or parsed.password:
        raise UnsafeRequestError()
    if any(character in target for character in ("?", "#", "@", "\\")):
        raise UnsafeRequestError()
    if _SAFE_ID.fullmatch(target) is None:
        raise UnsafeRequestError()
    return target


def _field_entries(
    entries: Sequence[tuple[str, bytes]], rules: Mapping[str, SafeValueRule]
) -> list[dict[str, Any]]:
    names = {name for name, _ in entries}
    if names != set(rules):
        raise UnsafeRequestError()
    output: list[dict[str, Any]] = []
    for name, encoded in entries:
        value = _decode_canonical(encoded)
        _validate_safe_value(value, rules[name])
        output.append({"name": name, "value": value})
    return output


def build_exact_request_bytes(
    profile: EndpointProfile, request: ExactMutationRequest
) -> bytes:
    if not isinstance(profile, EndpointProfile) or not isinstance(request, ExactMutationRequest):
        raise UnsafeRequestError()
    protected_names = {name for name, _, _ in request._protected}
    if not protected_names.issubset(profile.protected_field_classes):
        raise UnsafeRequestError()
    protected_entries = []
    for name, encoding, value in request._protected:
        if encoding == "utf8":
            encoded_value = value.decode("utf-8", errors="strict")
        else:
            encoded_value = base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
        protected_entries.append(
            {
                "name": name,
                "classification": profile.protected_field_classes[name].value,
                "encoding": encoding,
                "value": encoded_value,
            }
        )
    envelope = {
        "envelope_schema": ENVELOPE_SCHEMA,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "descriptor_version": DESCRIPTOR_VERSION,
        "connector_identity": profile.connector_identity,
        "connector_operation": profile.connector_operation,
        "operation_version": profile.operation_version,
        "endpoint_profile_id": profile.endpoint_profile_id,
        "endpoint_profile_version": profile.endpoint_profile_version,
        "credential_binding_id": profile.credential_binding_id,
        "credential_binding_version": profile.credential_binding_version,
        "wire_codec_version": profile.wire_codec_version,
        "target": _validate_target(request._target),
        "public_fields": _field_entries(request._public, profile.public_field_rules),
        "protected_fields": protected_entries,
        "mutation_options": _field_entries(request._options, profile.mutation_option_rules),
    }
    exact = canonical_json_bytes(envelope)
    if len(exact) > 1_048_576:
        raise UnsafeRequestError()
    return exact


class CommitmentKeyring:
    """Dedicated commitment keys. No default key is generated or inferred."""

    def __init__(self, *, keys: Mapping[str, bytes], active_key_id: str) -> None:
        copied: dict[str, bytes] = {}
        for key_id, key in keys.items():
            if _SAFE_ID.fullmatch(key_id) is None or type(key) is not bytes or len(key) < 32:
                raise CommitmentKeyError()
            copied[key_id] = bytes(key)
        if active_key_id not in copied:
            raise CommitmentKeyError()
        self._keys = copied
        self.active_key_id = active_key_id

    def __repr__(self) -> str:
        return "CommitmentKeyring(keys=<redacted>)"

    def key_for(self, key_id: str) -> bytes:
        key = self._keys.get(key_id)
        if key is None:
            raise CommitmentKeyError()
        return key

    def drop_key_for_test(self, key_id: str) -> None:
        self._keys.pop(key_id, None)


class SafeField(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, hide_input_in_errors=True
    )
    name: str
    canonical_value: str = Field(max_length=8_192, repr=False)

    @field_validator("canonical_value")
    @classmethod
    def _canonical(cls, value: str) -> str:
        if type(value) is not str:
            raise ValueError("safe field canonical value is invalid")
        _decode_canonical(value.encode("utf-8", errors="strict"))
        return value

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _validate_safe_field_name(value)


class ProtectedCommitment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field_name: str
    classification: ProtectedFieldClass
    algorithm: str
    key_id: str
    commitment: str

    @field_validator("field_name")
    @classmethod
    def _field_name(cls, value: str) -> str:
        if _SAFE_FIELD.fullmatch(value) is None:
            raise ValueError("invalid protected field identifier")
        return value

    @field_validator("algorithm")
    @classmethod
    def _algorithm(cls, value: str) -> str:
        if value != COMMITMENT_ALGORITHM:
            raise ValueError("unsupported commitment algorithm")
        return value

    @field_validator("key_id")
    @classmethod
    def _key_id(cls, value: str) -> str:
        return _safe_identifier(value)

    @field_validator("commitment")
    @classmethod
    def _digest(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("invalid protected commitment")
        return value


class SafeSemanticDescriptor(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, hide_input_in_errors=True
    )

    descriptor_version: str = DESCRIPTOR_VERSION
    request_envelope_schema: str = ENVELOPE_SCHEMA
    canonicalization_version: str = CANONICALIZATION_VERSION
    fingerprint_domain: str = FINGERPRINT_DOMAIN
    connector_identity: str
    connector_operation: str
    operation_version: str
    endpoint_profile_id: str
    endpoint_profile_version: str
    credential_binding_id: str
    credential_binding_version: str
    wire_codec_version: str
    redactor_version: str = "aep.redactor/1"
    dynamic_transport_policy: str = "authentication-profile-only/1"
    redacted_target: str
    public_fields: tuple[SafeField, ...]
    mutation_options: tuple[SafeField, ...]
    protected_commitments: tuple[ProtectedCommitment, ...]

    @field_validator(
        "descriptor_version", "request_envelope_schema", "canonicalization_version", "fingerprint_domain",
        "connector_identity", "connector_operation", "operation_version", "endpoint_profile_id",
        "endpoint_profile_version", "credential_binding_id",
        "credential_binding_version", "wire_codec_version", "redactor_version",
        "dynamic_transport_policy",
    )
    @classmethod
    def _safe_ids(cls, value: str) -> str:
        return _safe_identifier(value)

    @field_validator("redacted_target")
    @classmethod
    def _target(cls, value: str) -> str:
        return _validate_target(value)

    @model_validator(mode="after")
    def _supported_versions(self) -> "SafeSemanticDescriptor":
        if (
            self.descriptor_version != DESCRIPTOR_VERSION
            or self.request_envelope_schema != ENVELOPE_SCHEMA
            or self.canonicalization_version != CANONICALIZATION_VERSION
            or self.fingerprint_domain != FINGERPRINT_DOMAIN
            or self.redactor_version != "aep.redactor/1"
            or self.dynamic_transport_policy != "authentication-profile-only/1"
        ):
            raise ValueError("unsupported safe descriptor version")
        return self


def _unpad_base64url(value: str) -> bytes:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]*", value) is None:
        raise CanonicalizationError()
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except ValueError:
        raise CanonicalizationError() from None


def _framed(parts: Sequence[bytes]) -> bytes:
    return b"".join(len(part).to_bytes(4, "big") + part for part in parts)


def _validate_envelope(envelope: Any, profile: EndpointProfile) -> dict[str, Any]:
    if type(envelope) is not dict:
        raise CanonicalizationError()
    fixed = {
        "envelope_schema": ENVELOPE_SCHEMA,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "descriptor_version": DESCRIPTOR_VERSION,
        "connector_identity": profile.connector_identity,
        "connector_operation": profile.connector_operation,
        "operation_version": profile.operation_version,
        "endpoint_profile_id": profile.endpoint_profile_id,
        "endpoint_profile_version": profile.endpoint_profile_version,
        "credential_binding_id": profile.credential_binding_id,
        "credential_binding_version": profile.credential_binding_version,
        "wire_codec_version": profile.wire_codec_version,
    }
    expected_keys = {*fixed, "target", "public_fields", "protected_fields", "mutation_options"}
    if set(envelope) != expected_keys:
        raise UnsupportedRequestVersionError()
    if any(envelope[name] != value for name, value in fixed.items()):
        raise UnsupportedRequestVersionError()
    _validate_target(envelope["target"])
    return envelope


def _safe_fields_from_envelope(
    entries: Any, rules: Mapping[str, SafeValueRule]
) -> tuple[SafeField, ...]:
    if type(entries) is not list:
        raise UnsafeRequestError()
    output: list[SafeField] = []
    seen: set[str] = set()
    for entry in entries:
        if type(entry) is not dict or set(entry) != {"name", "value"}:
            raise UnsafeRequestError()
        name = entry["name"]
        if name in seen or name not in rules:
            raise UnsafeRequestError()
        seen.add(name)
        _canonical_value(entry["value"], safe_names=True)
        _validate_safe_value(entry["value"], rules[name])
        output.append(
            SafeField(
                name=name,
                canonical_value=canonical_json_bytes(entry["value"]).decode("utf-8"),
            )
        )
    if seen != set(rules):
        raise UnsafeRequestError()
    return tuple(sorted(output, key=lambda item: item.name))


def build_safe_descriptor(
    exact_request_bytes: bytes,
    profile: EndpointProfile,
    keyring: CommitmentKeyring,
    *,
    commitment_key_id: str | None = None,
) -> SafeSemanticDescriptor:
    envelope = _validate_envelope(_decode_canonical(exact_request_bytes), profile)
    key_id = commitment_key_id or keyring.active_key_id
    key = keyring.key_for(key_id)
    protected = envelope["protected_fields"]
    if type(protected) is not list:
        raise UnsafeRequestError()
    commitments: list[ProtectedCommitment] = []
    seen: set[str] = set()
    operation_context = canonical_json_bytes(
        {
            "connector_operation": profile.connector_operation,
            "connector_identity": profile.connector_identity,
            "operation_version": profile.operation_version,
            "endpoint_profile_id": profile.endpoint_profile_id,
            "endpoint_profile_version": profile.endpoint_profile_version,
        }
    )
    for entry in protected:
        if type(entry) is not dict or set(entry) != {
            "name", "classification", "encoding", "value"
        }:
            raise UnsafeRequestError()
        name = entry["name"]
        if name in seen or name not in profile.protected_field_classes:
            raise UnsafeRequestError()
        seen.add(name)
        classification = profile.protected_field_classes[name]
        if entry["classification"] != classification.value or entry["encoding"] not in {"utf8", "bytes"}:
            raise UnsafeRequestError()
        if entry["encoding"] == "utf8":
            if type(entry["value"]) is not str:
                raise CanonicalizationError()
            decoded = _require_nfc(entry["value"])
            raw_value = decoded.encode("utf-8")
        else:
            raw_value = _unpad_base64url(entry["value"])
        canonical_protected = canonical_json_bytes(
            {"encoding": entry["encoding"], "value": entry["value"]}
        )
        message = _framed(
            [
                COMMITMENT_DOMAIN,
                DESCRIPTOR_VERSION.encode("utf-8"),
                operation_context,
                name.encode("utf-8"),
                canonical_protected,
            ]
        )
        commitments.append(
            ProtectedCommitment(
                field_name=name,
                classification=classification,
                algorithm=COMMITMENT_ALGORITHM,
                key_id=key_id,
                commitment=hmac.new(key, message, hashlib.sha256).hexdigest(),
            )
        )
    return SafeSemanticDescriptor(
        connector_identity=profile.connector_identity,
        connector_operation=profile.connector_operation,
        operation_version=profile.operation_version,
        endpoint_profile_id=profile.endpoint_profile_id,
        endpoint_profile_version=profile.endpoint_profile_version,
        credential_binding_id=profile.credential_binding_id,
        credential_binding_version=profile.credential_binding_version,
        wire_codec_version=profile.wire_codec_version,
        redacted_target=envelope["target"],
        public_fields=_safe_fields_from_envelope(
            envelope["public_fields"], profile.public_field_rules
        ),
        mutation_options=_safe_fields_from_envelope(
            envelope["mutation_options"], profile.mutation_option_rules
        ),
        protected_commitments=tuple(sorted(commitments, key=lambda item: item.field_name)),
    )


def semantic_request_fingerprint(descriptor: SafeSemanticDescriptor) -> str:
    if not isinstance(descriptor, SafeSemanticDescriptor):
        raise CanonicalizationError()
    return hashlib.sha256(
        canonical_json_bytes(descriptor.model_dump(mode="json"))
    ).hexdigest()


def compute_request_binding_digest(
    *,
    request_fingerprint: str,
    request_material_ref: str,
    request_material_version: int,
    execution_id: str,
    step_id: str,
    intent_id: str,
    correlation_id: str,
    descriptor_version: str,
    endpoint_profile_version: str,
    vault_object_version: int,
    created_at_ms: int,
    intent_creation_not_after_ms: int,
    dispatch_material_not_after_ms: int,
    retention_not_after_ms: int,
) -> str:
    manifest = {
        "domain": BINDING_DOMAIN,
        "request_fingerprint": request_fingerprint,
        "request_material_ref": request_material_ref,
        "request_material_version": request_material_version,
        "execution_id": execution_id,
        "step_id": step_id,
        "intent_id": intent_id,
        "correlation_id": correlation_id,
        "descriptor_version": descriptor_version,
        "endpoint_profile_version": endpoint_profile_version,
        "vault_object_version": vault_object_version,
        "created_at_ms": created_at_ms,
        "intent_creation_not_after_ms": intent_creation_not_after_ms,
        "dispatch_material_not_after_ms": dispatch_material_not_after_ms,
        "retention_not_after_ms": retention_not_after_ms,
    }
    return hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()


class PersistedRequestBinding(BaseModel):
    """The complete safe binding persisted under one intent."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, hide_input_in_errors=True
    )

    binding_schema_version: str = BINDING_SCHEMA_VERSION
    execution_id: str
    step_id: str
    intent_id: str
    correlation_id: str
    connector_identity: str
    connector_operation: str
    operation_version: str
    descriptor_version: str = DESCRIPTOR_VERSION
    canonicalization_version: str = CANONICALIZATION_VERSION
    endpoint_profile_id: str
    endpoint_profile_version: str
    credential_binding_id: str
    credential_binding_version: str
    wire_codec_version: str
    request_material_ref: str
    request_material_version: int = Field(strict=True, ge=1, le=1)
    vault_object_version: int = Field(strict=True, ge=1, le=1)
    vault_encryption_key_id: str
    commitment_algorithm: str
    commitment_key_id: str
    request_fingerprint: str
    request_binding_digest: str
    created_at_ms: int = Field(strict=True, ge=0)
    intent_creation_not_after_ms: int = Field(strict=True, ge=0)
    dispatch_material_not_after_ms: int = Field(strict=True, ge=0)
    retention_not_after_ms: int = Field(strict=True, ge=0)
    safe_descriptor: SafeSemanticDescriptor

    @field_validator("request_fingerprint", "request_binding_digest")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("binding digest must be lowercase SHA-256")
        return value

    @field_validator("request_material_ref")
    @classmethod
    def _locator(cls, value: str) -> str:
        if _LOCATOR.fullmatch(value) is None:
            raise ValueError("invalid opaque vault locator")
        return value

    @field_validator(
        "binding_schema_version", "execution_id", "step_id", "intent_id",
        "correlation_id", "connector_identity", "connector_operation", "operation_version",
        "descriptor_version", "canonicalization_version", "endpoint_profile_id",
        "endpoint_profile_version", "credential_binding_id",
        "credential_binding_version", "wire_codec_version",
        "vault_encryption_key_id", "commitment_algorithm", "commitment_key_id",
    )
    @classmethod
    def _safe_identifier(cls, value: str) -> str:
        return _safe_identifier(value)

    @model_validator(mode="after")
    def _consistent(self) -> "PersistedRequestBinding":
        if self.binding_schema_version != BINDING_SCHEMA_VERSION:
            raise ValueError("unsupported request-binding version")
        if self.descriptor_version != DESCRIPTOR_VERSION or self.canonicalization_version != CANONICALIZATION_VERSION:
            raise ValueError("unsupported descriptor/canonicalization version")
        if self.commitment_algorithm != COMMITMENT_ALGORITHM:
            raise ValueError("unsupported commitment algorithm")
        if not (
            self.created_at_ms <= self.intent_creation_not_after_ms
            < self.dispatch_material_not_after_ms
            <= self.retention_not_after_ms
        ):
            raise ValueError("request-binding deadlines are inconsistent")
        if self.safe_descriptor.descriptor_version != self.descriptor_version:
            raise ValueError("safe descriptor version mismatch")
        return self


def canonical_request_binding_bytes(
    binding: PersistedRequestBinding | Mapping[str, Any],
) -> bytes:
    """Return the sole canonical representation of the complete safe binding."""

    if isinstance(binding, PersistedRequestBinding):
        value: Any = binding.model_dump(mode="json")
    elif type(binding) is dict:
        value = dict(binding)
    else:
        raise CanonicalizationError()
    return canonical_json_bytes(value)


def parse_canonical_request_binding(value: str | bytes) -> PersistedRequestBinding:
    """Strictly decode and type the persisted canonical binding string."""

    try:
        raw = value.encode("utf-8", errors="strict") if type(value) is str else value
    except UnicodeError:
        raise CanonicalizationError() from None
    decoded = _decode_canonical(raw)
    if type(decoded) is not dict:
        raise CanonicalizationError()
    try:
        return PersistedRequestBinding.model_validate(decoded)
    except (ValueError, TypeError):
        raise CanonicalizationError() from None


def validate_persisted_binding_against_profile(
    binding: PersistedRequestBinding,
    profile: EndpointProfile,
) -> None:
    """Revalidate every persisted safe value and commitment against one profile."""

    if not isinstance(binding, PersistedRequestBinding) or not isinstance(
        profile, EndpointProfile
    ):
        raise RequestBindingMismatchError()
    descriptor = binding.safe_descriptor
    descriptor_context = (
        descriptor.connector_identity,
        descriptor.connector_operation,
        descriptor.operation_version,
        descriptor.endpoint_profile_id,
        descriptor.endpoint_profile_version,
        descriptor.credential_binding_id,
        descriptor.credential_binding_version,
        descriptor.wire_codec_version,
    )
    binding_context = (
        binding.connector_identity,
        binding.connector_operation,
        binding.operation_version,
        binding.endpoint_profile_id,
        binding.endpoint_profile_version,
        binding.credential_binding_id,
        binding.credential_binding_version,
        binding.wire_codec_version,
    )
    profile_context = (
        profile.connector_identity,
        profile.connector_operation,
        profile.operation_version,
        profile.endpoint_profile_id,
        profile.endpoint_profile_version,
        profile.credential_binding_id,
        profile.credential_binding_version,
        profile.wire_codec_version,
    )
    if descriptor_context != binding_context or binding_context != profile_context:
        raise RequestBindingMismatchError()

    def validate_fields(
        fields: tuple[SafeField, ...], rules: Mapping[str, SafeValueRule]
    ) -> None:
        seen: set[str] = set()
        for field in fields:
            if type(field) is not SafeField or field.name in seen or field.name not in rules:
                raise RequestBindingMismatchError()
            seen.add(field.name)
            try:
                decoded = _decode_canonical(
                    field.canonical_value.encode("utf-8", errors="strict")
                )
                _validate_safe_value(decoded, rules[field.name])
            except (RequestBindingError, UnicodeError):
                raise RequestBindingMismatchError() from None
        if seen != set(rules):
            raise RequestBindingMismatchError()

    validate_fields(descriptor.public_fields, profile.public_field_rules)
    validate_fields(descriptor.mutation_options, profile.mutation_option_rules)

    seen_protected: set[str] = set()
    for commitment in descriptor.protected_commitments:
        name = commitment.field_name
        expected_class = profile.protected_field_classes.get(name)
        if (
            type(commitment) is not ProtectedCommitment
            or name in seen_protected
            or expected_class is None
            or commitment.classification is not expected_class
            or commitment.algorithm != binding.commitment_algorithm
            or commitment.key_id != binding.commitment_key_id
        ):
            raise RequestBindingMismatchError()
        seen_protected.add(name)


def _profile_context(profile: EndpointProfile) -> tuple[str, ...]:
    return (
        profile.connector_identity,
        profile.connector_operation,
        profile.operation_version,
        profile.endpoint_profile_id,
        profile.endpoint_profile_version,
        profile.credential_binding_id,
        profile.credential_binding_version,
        profile.wire_codec_version,
    )


class ReconciliationContext(BaseModel):
    """Safe read-only context with no request material or dispatch authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: str
    step_id: str
    intent_id: str
    correlation_id: str
    connector_operation: str
    redacted_target: str
    request_fingerprint: str
    external_reference: str | None = None
    attempt_count: int = Field(strict=True, ge=0)

    @field_validator(
        "execution_id", "step_id", "intent_id", "correlation_id",
        "connector_operation", "redacted_target", "external_reference",
    )
    @classmethod
    def _safe_context_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_identifier(value)

    @field_validator("request_fingerprint")
    @classmethod
    def _fingerprint(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("invalid reconciliation fingerprint")
        return value


@dataclass(frozen=True, repr=False)
class PreparedMutation:
    binding: PersistedRequestBinding

    def __repr__(self) -> str:
        return (
            "PreparedMutation(material=<protected>, "
            f"intent_id={self.binding.intent_id!r})"
        )


@dataclass(frozen=True, repr=False, init=False, eq=False)
class VerifiedDispatch:
    exact_request_bytes: bytes
    binding: PersistedRequestBinding
    _provenance: bytes

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise RequestBindingMismatchError()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("VerifiedDispatch is final")

    def __copy__(self) -> "VerifiedDispatch":
        raise RequestBindingMismatchError()

    def __deepcopy__(self, memo: dict[int, Any]) -> "VerifiedDispatch":
        raise RequestBindingMismatchError()

    def __repr__(self) -> str:
        return (
            "VerifiedDispatch(material=<protected>, "
            f"intent_id={self.binding.intent_id!r})"
        )


@dataclass(frozen=True, repr=False)
class _DispatchProvenanceRecord:
    dispatch_ref: weakref.ReferenceType[VerifiedDispatch]
    material_digest: bytes
    canonical_binding: bytes
    provenance: bytes
    expires_monotonic: float


def _build_dispatch_boundary():
    secret = secrets.token_bytes(32)
    records: dict[int, _DispatchProvenanceRecord] = {}
    record_lock = threading.Lock()

    def issue(
        material: bytes,
        binding: PersistedRequestBinding,
        verified_at_ms: int,
    ) -> tuple[bytes, PersistedRequestBinding, int]:
        exact = bytes(material)
        canonical_binding = canonical_request_binding_bytes(binding)
        material_digest = hashlib.sha256(exact).digest()
        nonce = secrets.token_bytes(32)
        provenance = hmac.new(
            secret,
            _framed(
                [
                    b"AEP_VERIFIED_DISPATCH_CAPABILITY_V1",
                    nonce,
                    material_digest,
                    hashlib.sha256(canonical_binding).digest(),
                ]
            ),
            hashlib.sha256,
        ).digest()
        dispatch = object.__new__(VerifiedDispatch)
        object.__setattr__(dispatch, "exact_request_bytes", exact)
        object.__setattr__(dispatch, "binding", binding)
        object.__setattr__(dispatch, "_provenance", provenance)
        identity = id(dispatch)

        def discard(reference: weakref.ReferenceType[VerifiedDispatch]) -> None:
            with record_lock:
                current = records.get(identity)
                if current is not None and current.dispatch_ref is reference:
                    records.pop(identity, None)

        reference = weakref.ref(dispatch, discard)
        remaining_ms = max(
            1, binding.dispatch_material_not_after_ms - verified_at_ms
        )
        with record_lock:
            records[identity] = _DispatchProvenanceRecord(
                dispatch_ref=reference,
                material_digest=material_digest,
                canonical_binding=canonical_binding,
                provenance=provenance,
                expires_monotonic=time.monotonic() + remaining_ms / 1000,
            )
        return dispatch

    def consume(
        dispatch: VerifiedDispatch,
        *,
        connector_identity: str,
        connector_operation: str,
        endpoint_profile_id: str,
        endpoint_profile_version: str,
        execution_id: str,
        step_id: str,
        intent_id: str,
        correlation_id: str,
    ) -> bytes:
        if type(dispatch) is not VerifiedDispatch:
            raise RequestBindingMismatchError()
        with record_lock:
            record = records.pop(id(dispatch), None)
        if record is None or record.dispatch_ref() is not dispatch:
            raise RequestBindingMismatchError()
        try:
            binding = dispatch.binding
            exact = dispatch.exact_request_bytes
            provenance = dispatch._provenance
            canonical_binding = canonical_request_binding_bytes(binding)
        except (AttributeError, RequestBindingError, TypeError):
            raise RequestBindingMismatchError() from None
        expected = (
            connector_identity,
            connector_operation,
            endpoint_profile_id,
            endpoint_profile_version,
            execution_id,
            step_id,
            intent_id,
            correlation_id,
        )
        actual = (
            binding.connector_identity,
            binding.connector_operation,
            binding.endpoint_profile_id,
            binding.endpoint_profile_version,
            binding.execution_id,
            binding.step_id,
            binding.intent_id,
            binding.correlation_id,
        )
        if (
            time.monotonic() > record.expires_monotonic
            or expected != actual
            or type(exact) is not bytes
            or not hmac.compare_digest(
                hashlib.sha256(exact).digest(), record.material_digest
            )
            or not hmac.compare_digest(canonical_binding, record.canonical_binding)
            or not hmac.compare_digest(provenance, record.provenance)
        ):
            raise RequestBindingMismatchError()
        return bytes(exact)

    return issue, consume


_dispatch_issuer, consume_verified_dispatch = _build_dispatch_boundary()
del _build_dispatch_boundary


class RequestBindingService:
    """Prepare, vault, read back, and verify one versioned endpoint profile."""

    def __init__(
        self,
        *,
        profile: EndpointProfile,
        commitment_keys: CommitmentKeyring,
        vault: RequestVault,
    ) -> None:
        self.profile = profile
        self.commitment_keys = commitment_keys
        self.vault = vault

    async def prepare(
        self,
        *,
        execution_id: str,
        step_id: str,
        intent_id: str,
        correlation_id: str,
        request: ExactMutationRequest,
        created_at_ms: int,
        intent_creation_not_after_ms: int,
        dispatch_material_not_after_ms: int,
        retention_not_after_ms: int,
    ) -> PreparedMutation:
        for identifier in (execution_id, step_id, intent_id, correlation_id):
            _safe_identifier(identifier)
        exact = build_exact_request_bytes(self.profile, request)
        descriptor = build_safe_descriptor(exact, self.profile, self.commitment_keys)
        fingerprint = semantic_request_fingerprint(descriptor)
        locator = "vault_" + secrets.token_urlsafe(24)
        metadata = VaultObjectMetadata(
            locator=locator,
            object_version=1,
            request_material_version=1,
            encryption_key_id=self.vault.active_key_id,
            envelope_schema=ENVELOPE_SCHEMA,
            canonicalization_version=CANONICALIZATION_VERSION,
            connector_identity=self.profile.connector_identity,
            connector_operation=self.profile.connector_operation,
            operation_version=self.profile.operation_version,
            descriptor_version=DESCRIPTOR_VERSION,
            endpoint_profile_id=self.profile.endpoint_profile_id,
            endpoint_profile_version=self.profile.endpoint_profile_version,
            credential_binding_id=self.profile.credential_binding_id,
            credential_binding_version=self.profile.credential_binding_version,
            wire_codec_version=self.profile.wire_codec_version,
            commitment_algorithm=COMMITMENT_ALGORITHM,
            commitment_key_id=self.commitment_keys.active_key_id,
            execution_id=execution_id,
            step_id=step_id,
            intent_id=intent_id,
            correlation_id=correlation_id,
            created_at_ms=created_at_ms,
            intent_creation_not_after_ms=intent_creation_not_after_ms,
            dispatch_material_not_after_ms=dispatch_material_not_after_ms,
            retention_not_after_ms=retention_not_after_ms,
            material_length=len(exact),
        )
        await self.vault.create_once(exact, metadata)
        readback = await self.vault.read_exact(locator, now_ms=created_at_ms)
        if readback.metadata != metadata or not hmac.compare_digest(readback.material, exact):
            raise VaultAuthenticationError()
        digest = compute_request_binding_digest(
            request_fingerprint=fingerprint,
            request_material_ref=locator,
            request_material_version=1,
            execution_id=execution_id,
            step_id=step_id,
            intent_id=intent_id,
            correlation_id=correlation_id,
            descriptor_version=DESCRIPTOR_VERSION,
            endpoint_profile_version=self.profile.endpoint_profile_version,
            vault_object_version=1,
            created_at_ms=created_at_ms,
            intent_creation_not_after_ms=intent_creation_not_after_ms,
            dispatch_material_not_after_ms=dispatch_material_not_after_ms,
            retention_not_after_ms=retention_not_after_ms,
        )
        binding = PersistedRequestBinding(
            execution_id=execution_id,
            step_id=step_id,
            intent_id=intent_id,
            correlation_id=correlation_id,
            connector_identity=self.profile.connector_identity,
            connector_operation=self.profile.connector_operation,
            operation_version=self.profile.operation_version,
            endpoint_profile_id=self.profile.endpoint_profile_id,
            endpoint_profile_version=self.profile.endpoint_profile_version,
            credential_binding_id=self.profile.credential_binding_id,
            credential_binding_version=self.profile.credential_binding_version,
            wire_codec_version=self.profile.wire_codec_version,
            request_material_ref=locator,
            request_material_version=1,
            vault_object_version=1,
            vault_encryption_key_id=self.vault.active_key_id,
            commitment_algorithm=COMMITMENT_ALGORITHM,
            commitment_key_id=self.commitment_keys.active_key_id,
            request_fingerprint=fingerprint,
            request_binding_digest=digest,
            created_at_ms=created_at_ms,
            intent_creation_not_after_ms=intent_creation_not_after_ms,
            dispatch_material_not_after_ms=dispatch_material_not_after_ms,
            retention_not_after_ms=retention_not_after_ms,
            safe_descriptor=descriptor,
        )
        return PreparedMutation(binding=binding)

    async def verify(
        self,
        *,
        binding: PersistedRequestBinding,
        execution_id: str,
        step_id: str,
        intent_id: str,
        correlation_id: str,
        now_ms: int,
        minimum_retention_not_after_ms: int,
    ) -> VerifiedDispatch:
        expected_context = (execution_id, step_id, intent_id, correlation_id)
        actual_context = (
            binding.execution_id, binding.step_id, binding.intent_id,
            binding.correlation_id,
        )
        if expected_context != actual_context:
            raise RequestBindingMismatchError()
        if now_ms >= binding.dispatch_material_not_after_ms:
            raise RequestBindingExpiredError()
        if binding.retention_not_after_ms < minimum_retention_not_after_ms:
            raise RequestBindingMismatchError()
        profile = self.profile
        profile_values = (
            binding.connector_identity,
            binding.connector_operation,
            binding.operation_version,
            binding.endpoint_profile_id,
            binding.endpoint_profile_version,
            binding.credential_binding_id,
            binding.credential_binding_version,
            binding.wire_codec_version,
        )
        expected_profile_values = (
            profile.connector_identity,
            profile.connector_operation,
            profile.operation_version,
            profile.endpoint_profile_id,
            profile.endpoint_profile_version,
            profile.credential_binding_id,
            profile.credential_binding_version,
            profile.wire_codec_version,
        )
        if profile_values != expected_profile_values:
            raise RequestBindingMismatchError()
        readback = await self.vault.read_exact(
            binding.request_material_ref, now_ms=now_ms
        )
        metadata = readback.metadata
        if (
            metadata.locator != binding.request_material_ref
            or metadata.object_version != binding.vault_object_version
            or metadata.request_material_version != binding.request_material_version
            or metadata.encryption_key_id != binding.vault_encryption_key_id
            or metadata.envelope_schema != ENVELOPE_SCHEMA
            or metadata.canonicalization_version != binding.canonicalization_version
            or metadata.connector_identity != binding.connector_identity
            or metadata.intent_id != intent_id
            or metadata.execution_id != execution_id
            or metadata.step_id != step_id
            or metadata.correlation_id != correlation_id
            or metadata.connector_operation != binding.connector_operation
            or metadata.operation_version != binding.operation_version
            or metadata.descriptor_version != binding.descriptor_version
            or metadata.endpoint_profile_id != binding.endpoint_profile_id
            or metadata.endpoint_profile_version != binding.endpoint_profile_version
            or metadata.credential_binding_id != binding.credential_binding_id
            or metadata.credential_binding_version != binding.credential_binding_version
            or metadata.wire_codec_version != binding.wire_codec_version
            or metadata.commitment_algorithm != binding.commitment_algorithm
            or metadata.commitment_key_id != binding.commitment_key_id
            or metadata.created_at_ms != binding.created_at_ms
            or metadata.intent_creation_not_after_ms
            != binding.intent_creation_not_after_ms
            or metadata.dispatch_material_not_after_ms
            != binding.dispatch_material_not_after_ms
            or metadata.retention_not_after_ms != binding.retention_not_after_ms
            or metadata.material_length != len(readback.material)
        ):
            raise RequestBindingMismatchError()
        self.revalidate_persisted_binding(binding)
        descriptor = build_safe_descriptor(
            readback.material,
            profile,
            self.commitment_keys,
            commitment_key_id=binding.commitment_key_id,
        )
        fingerprint = semantic_request_fingerprint(descriptor)
        if not hmac.compare_digest(fingerprint, binding.request_fingerprint):
            raise RequestBindingMismatchError()
        if descriptor != binding.safe_descriptor:
            raise RequestBindingMismatchError()
        digest = compute_request_binding_digest(
            request_fingerprint=fingerprint,
            request_material_ref=binding.request_material_ref,
            request_material_version=binding.request_material_version,
            execution_id=execution_id,
            step_id=step_id,
            intent_id=intent_id,
            correlation_id=correlation_id,
            descriptor_version=binding.descriptor_version,
            endpoint_profile_version=binding.endpoint_profile_version,
            vault_object_version=binding.vault_object_version,
            created_at_ms=binding.created_at_ms,
            intent_creation_not_after_ms=binding.intent_creation_not_after_ms,
            dispatch_material_not_after_ms=binding.dispatch_material_not_after_ms,
            retention_not_after_ms=binding.retention_not_after_ms,
        )
        if not hmac.compare_digest(digest, binding.request_binding_digest):
            raise RequestBindingMismatchError()

        return bytes(readback.material), binding, now_ms

    def revalidate_persisted_binding(
        self, binding: PersistedRequestBinding
    ) -> None:
        validate_persisted_binding_against_profile(binding, self.profile)


def _install_verified_dispatch_issuer(
    service_type: type[RequestBindingService], issuer: Any
) -> None:
    authenticated_verify = service_type.verify

    async def verify(self: RequestBindingService, **kwargs: Any) -> VerifiedDispatch:
        material, binding, verified_at_ms = await authenticated_verify(
            self, **kwargs
        )
        return issuer(material, binding, verified_at_ms)

    service_type.verify = verify  # type: ignore[method-assign]


_install_verified_dispatch_issuer(RequestBindingService, _dispatch_issuer)
del _dispatch_issuer
del _install_verified_dispatch_issuer
