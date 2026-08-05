"""The ground-truth oracle's identity function for mutations.

PAPER METHODOLOGY -- this section is written to be quoted verbatim.

    **Definition 1 (mutation fingerprint).**  Let ``r`` be a mutation request
    received by MockLegacyAPI on endpoint ``e`` via HTTP method ``m``.  The
    *mutation fingerprint* of ``r`` is

        F(r) = SHA-256( C( {
            "v":                 V,
            "method":            uppercase(m),
            "endpoint":          e,
            "operation":         r.connector_operation,
            "operation_version": r.operation_version,
            "target":            r.target,
            "identity":          { f: r.public_fields[f]  for f in I(e) }
        } ) )

    where ``C`` is the canonical JSON encoding of :func:`canonical_bytes`
    (UTF-8; strings NFC-normalised; object keys sorted by Unicode code point;
    no insignificant whitespace; integers only -- floats are rejected, not
    rounded), ``V`` is :data:`FINGERPRINT_SCHEMA_VERSION`, and ``I(e)`` is the
    set of *identity fields* declared for endpoint ``e`` in the mock API's
    configuration.

    **Two requests denote the same mutation iff their fingerprints are
    equal.**  Every duplicate reported by the evaluation is a fingerprint
    collision between two *applied* mutations in the ground-truth ledger.

    **What is deliberately outside F, and why.**  Everything a legitimate
    retry of the same mutation is allowed to change:

    * per-attempt protocol identity -- intent id, correlation id, execution
      id, step id, idempotency keys, client reference;
    * credentials and any other protected field;
    * public fields not declared in ``I(e)`` (a free-text memo, a notify
      flag);
    * transport metadata -- timestamps, nonces, headers, connection identity.

    If any of these entered ``F``, every retry would fingerprint differently,
    no two applied mutations could ever collide, and the measured duplicate
    rate of *every* system under test -- including the naive-retry baseline --
    would be identically zero.  The oracle would report a perfect result for a
    protocol that duplicates on every attempt.

    **Independence from the system under test.**  ``F`` is computed from the
    request as received on the wire, using this module's own canonicaliser.
    It deliberately does not reuse ``aep_core``'s request fingerprint or its
    canonical-JSON implementation: an oracle that inherited the canonicaliser
    of the protocol it measures would also inherit any collision that
    canonicaliser has.  AEP's own fingerprint is carried alongside as an
    opaque *client reference* used only to answer read-back queries, and is
    never an input to duplicate detection.

    **Definition 2 (payload digest).**  ``D(r) = SHA-256( C( redact(r) ) )``
    over the *whole* envelope, with each protected field's value replaced by
    the SHA-256 digest of its wire bytes (:func:`redact_envelope`).  ``D``
    distinguishes requests that ``F`` merges, which is what makes the
    ``FINGERPRINT_CONFLICT`` class of Definition 3 detectable: two requests
    that claim to be the same mutation but do not carry the same bytes.  The
    redaction is what lets the ledger -- a published artifact -- record
    payload identity without recording payload secrets.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any, Iterable, Mapping

#: Bound into every digest. A change to the definition above is a change to
#: the meaning of every duplicate count in the paper, so it must not compare
#: equal to the previous definition.
FINGERPRINT_SCHEMA_VERSION = "aep.mock-legacy-api.mutation-fingerprint/1"

#: Envelope keys this module requires to be present before it will produce a
#: fingerprint. Absence means the request is not a mutation request at all.
_REQUIRED_ENVELOPE_KEYS = frozenset(
    {
        "connector_operation",
        "operation_version",
        "target",
        "public_fields",
    }
)


class FingerprintError(Exception):
    """A request could not be given a fingerprint, so it is not identified.

    Raised rather than returning a best-effort digest: an unidentifiable
    mutation must be visible as such, because a plausible-looking fingerprint
    would silently join or split ground-truth duplicate groups.
    """


def _canonical(value: Any) -> Any:
    """Recursively normalise a value for canonical encoding.

    ``bool`` is checked before ``int`` because ``bool`` is a subclass of
    ``int`` and ``True`` must not canonicalise to ``1``.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        return {
            unicodedata.normalize("NFC", str(key)): _canonical(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    raise FingerprintError(
        f"value of type {type(value).__name__} has no canonical form; the "
        "mutation schema admits only null, bool, int, str, list and object "
        "(floats are excluded: money is integer minor units)"
    )


def canonical_bytes(value: Any) -> bytes:
    """Deterministic UTF-8 JSON: NFC strings, sorted keys, no whitespace."""
    try:
        return json.dumps(
            _canonical(value),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", errors="strict")
    except FingerprintError:
        raise
    except (TypeError, ValueError, UnicodeError) as exc:
        raise FingerprintError(f"value is not canonically encodable: {exc}") from None


def _public_field_map(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Turn the wire's ordered field list into a name -> value mapping."""
    entries = envelope.get("public_fields")
    if not isinstance(entries, (list, tuple)):
        raise FingerprintError("envelope has no public_fields list")

    fields: dict[str, Any] = {}
    for entry in entries:
        if not isinstance(entry, Mapping) or "name" not in entry or "value" not in entry:
            raise FingerprintError(
                "each public field must be an object with name and value"
            )
        name = entry["name"]
        if not isinstance(name, str):
            raise FingerprintError("public field names must be strings")
        if name in fields:
            # Two values for one field name make the mutation ambiguous: the
            # oracle would have to pick one, and either pick is a guess.
            raise FingerprintError(f"duplicate public field name {name!r}")
        fields[name] = entry["value"]
    return fields


def _require_envelope(envelope: Any) -> Mapping[str, Any]:
    if not isinstance(envelope, Mapping):
        raise FingerprintError("request envelope must be a JSON object")
    missing = sorted(_REQUIRED_ENVELOPE_KEYS - set(envelope))
    if missing:
        raise FingerprintError(f"request envelope is missing {missing}")
    return envelope


def mutation_fingerprint(
    *,
    method: str,
    endpoint: str,
    envelope: Mapping[str, Any],
    identity_fields: Iterable[str],
) -> str:
    """Return ``F(r)`` from Definition 1 as a 64-character hex digest."""
    envelope = _require_envelope(envelope)

    declared = tuple(identity_fields)
    if not declared:
        # An endpoint with no identity field cannot distinguish one mutation
        # from another, so it cannot have an oracle.
        raise FingerprintError(
            "endpoint declares no identity field; every mutation on it would "
            "fingerprint identically"
        )

    fields = _public_field_map(envelope)
    identity: dict[str, Any] = {}
    for name in sorted(set(declared)):
        if name not in fields:
            raise FingerprintError(
                f"request omits declared identity field {name!r}; it cannot "
                "be identified and must not be given a fingerprint"
            )
        identity[name] = fields[name]

    return hashlib.sha256(
        canonical_bytes(
            {
                "v": FINGERPRINT_SCHEMA_VERSION,
                "method": str(method).upper(),
                "endpoint": endpoint,
                "operation": envelope["connector_operation"],
                "operation_version": envelope["operation_version"],
                "target": envelope["target"],
                "identity": identity,
            }
        )
    ).hexdigest()


def redact_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy whose protected values are replaced by their digests.

    The caller's envelope is not modified. The digest is over the wire bytes
    of the value exactly as received, so two different secrets differ and two
    equal secrets agree, without the secret itself being retained anywhere the
    ledger -- or the published artifact built from it -- can reach.
    """
    envelope = _require_envelope(envelope)
    redacted = {
        key: value for key, value in envelope.items() if key != "protected_fields"
    }

    protected_entries = envelope.get("protected_fields", [])
    if not isinstance(protected_entries, (list, tuple)):
        raise FingerprintError("protected_fields must be a list when present")

    protected: list[dict[str, Any]] = []
    for entry in protected_entries:
        if not isinstance(entry, Mapping):
            raise FingerprintError("each protected field must be an object")
        replacement = {
            key: value for key, value in entry.items() if key != "value"
        }
        raw = entry.get("value", "")
        if not isinstance(raw, (str, bytes)):
            raise FingerprintError("protected field values must be str or bytes")
        material = raw.encode("utf-8") if isinstance(raw, str) else raw
        replacement["value_digest"] = hashlib.sha256(material).hexdigest()
        protected.append(replacement)

    redacted["protected_fields"] = protected
    return redacted


def payload_digest(envelope: Mapping[str, Any]) -> str:
    """Return ``D(r)`` from Definition 2 as a 64-character hex digest.

    Field lists are sorted by name first, so that a provider re-ordering the
    wire representation is not mistaken for a different payload.
    """
    redacted = redact_envelope(envelope)
    for key in ("public_fields", "protected_fields", "mutation_options"):
        entries = redacted.get(key)
        if isinstance(entries, list):
            redacted[key] = sorted(
                entries, key=lambda entry: str(entry.get("name", ""))
            )
    return hashlib.sha256(canonical_bytes(redacted)).hexdigest()
