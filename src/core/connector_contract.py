"""Production connector contract for non-idempotent external mutations.

The three reconciliation response classes are normative protocol vocabulary
(``docs/06-phase2-design.md`` section 8.3), not test scaffolding.  This module
is their single definition; ``tests/mock_connector.py`` imports from here.

The classification in :func:`classify_readback` is *total* over the declared
contract: every (capability, result) pair that can legally reach it produces an
explicit decision, and anything outside the contract raises
:class:`ConnectorContractError` rather than falling through to a default.

Import-side-effect-free: no I/O, no network, no logging config at import time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol, runtime_checkable

from src.core.exceptions import AEPException


class ConnectorContractError(AEPException):
    """A connector declaration or read-back response violated the contract.

    Raised for an absent or unrecognised capability declaration and for any
    attempt to classify evidence that the declaring capability may not
    produce.  It is never raised for a merely uninformative read-back: an
    unparseable or absent observation degrades to
    :attr:`ReadbackResult.UNKNOWN`, which consumes reconciliation budget
    instead of asserting anything about the external system.
    """


class ReconciliationCapability(str, Enum):
    """The capability a non-idempotent connector MUST declare.

    ``docs/06-phase2-design.md:347-353``.
    """

    AUTHORITATIVE_READBACK = "AUTHORITATIVE_READBACK"
    POSITIVE_ONLY_READBACK = "POSITIVE_ONLY_READBACK"
    NO_READBACK = "NO_READBACK"


class ReadbackResult(str, Enum):
    """Evidence a read-only reconciliation query may return."""

    APPLIED = "APPLIED"
    NOT_APPLIED = "NOT_APPLIED"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


class ReconciliationOutcome(str, Enum):
    """Protocol-level meaning of one classified read-back.

    These are the three terminal classes named in ``PAPER_ROADMAP.md`` §1 (P2)
    plus the non-terminal ``RETRY``, which is only reachable while the
    reconciliation budget of P3 remains.
    """

    CONFIRMED = "CONFIRMED"
    REFUTED = "REFUTED"
    PERMANENTLY_AMBIGUOUS = "PERMANENTLY_AMBIGUOUS"
    RETRY = "RETRY"


#: Evidence class persisted when a connector declares no usable capability.
UNDECLARED_CAPABILITY_EVIDENCE_CLASS = "UNDECLARED_CAPABILITY"

#: Reason persisted when a connector declares no usable capability.
UNDECLARED_CAPABILITY_REASON = "connector-capability-undeclared"

#: Exactly which results each capability is permitted to assert.
#: ``NO_READBACK`` is never queried, hence the empty set.
PERMITTED_READBACK_RESULTS: Mapping[
    ReconciliationCapability, frozenset[ReadbackResult]
] = {
    ReconciliationCapability.AUTHORITATIVE_READBACK: frozenset(
        {
            ReadbackResult.APPLIED,
            ReadbackResult.NOT_APPLIED,
            ReadbackResult.UNKNOWN,
            ReadbackResult.CONFLICT,
        }
    ),
    ReconciliationCapability.POSITIVE_ONLY_READBACK: frozenset(
        {
            ReadbackResult.APPLIED,
            ReadbackResult.UNKNOWN,
            ReadbackResult.CONFLICT,
        }
    ),
    ReconciliationCapability.NO_READBACK: frozenset(),
}


@runtime_checkable
class ReconciliationConnector(Protocol):
    """A connector that can be reconciled read-only after an ambiguous call."""

    reconciliation_capability: ReconciliationCapability

    async def read_back(self, *, context: Any, readback_timeout: float) -> Any: ...


@dataclass(frozen=True)
class ReconciliationDecision:
    """One fully explicit classification of read-back evidence."""

    outcome: ReconciliationOutcome
    reason: str
    evidence_class: str


def declared_capability(connector: Any) -> ReconciliationCapability:
    """Return the connector's declared capability or fail closed.

    Accepts either a :class:`ReconciliationCapability` member or a string
    exactly equal to one of its values.  Anything else — a missing attribute,
    ``None``, a typo, or a foreign type — raises, because the protocol cannot
    interpret read-back evidence whose authority is unknown.
    """

    declared = getattr(connector, "reconciliation_capability", None)
    if isinstance(declared, ReconciliationCapability):
        return declared
    if type(declared) is str:
        try:
            return ReconciliationCapability(declared)
        except ValueError:
            raise ConnectorContractError(
                "connector declared an unrecognised reconciliation capability"
            ) from None
    raise ConnectorContractError(
        "connector did not declare a reconciliation capability"
    )


def parse_readback_result(observation: Any) -> ReadbackResult:
    """Coerce a connector observation to a declared result, defaulting UNKNOWN.

    Unparseable evidence is deliberately *not* an error: it is simply not
    evidence.  Returning ``UNKNOWN`` keeps the intent inside the bounded
    reconciliation budget of P3 rather than asserting a conclusion the
    connector never supported.
    """

    attribute = getattr(observation, "result", None)
    value = getattr(attribute, "value", attribute)
    if isinstance(value, ReadbackResult):
        return value
    if type(value) is str:
        try:
            return ReadbackResult(value)
        except ValueError:
            return ReadbackResult.UNKNOWN
    return ReadbackResult.UNKNOWN


def result_is_permitted(
    capability: ReconciliationCapability, result: ReadbackResult
) -> bool:
    """True iff ``capability`` is allowed to assert ``result``."""

    return result in PERMITTED_READBACK_RESULTS[capability]


def classify_readback(
    capability: ReconciliationCapability, result: ReadbackResult
) -> ReconciliationDecision:
    """Classify one read-back result under one declared capability.

    Total over the contract.  Every branch is explicit; there is no
    fall-through default, which is what makes ``POSITIVE_ONLY_READBACK``
    handling auditable rather than emergent.
    """

    if not isinstance(capability, ReconciliationCapability):
        raise ConnectorContractError(
            "reconciliation capability must be a declared contract member"
        )
    if not isinstance(result, ReadbackResult):
        raise ConnectorContractError(
            "read-back result must be a declared contract member"
        )
    if capability is ReconciliationCapability.NO_READBACK:
        raise ConnectorContractError(
            "a NO_READBACK connector must never be queried or classified"
        )

    if result is ReadbackResult.APPLIED:
        # Positive evidence is trusted for both querying classes: absence is
        # what positive-only endpoints cannot prove, not presence.
        reason = (
            "authoritative-readback-applied"
            if capability is ReconciliationCapability.AUTHORITATIVE_READBACK
            else "positive-only-readback-applied"
        )
        return ReconciliationDecision(
            outcome=ReconciliationOutcome.CONFIRMED,
            reason=reason,
            evidence_class=result.value,
        )

    if result is ReadbackResult.NOT_APPLIED:
        if capability is ReconciliationCapability.AUTHORITATIVE_READBACK:
            return ReconciliationDecision(
                outcome=ReconciliationOutcome.REFUTED,
                reason="authoritative-readback-not-applied",
                evidence_class=result.value,
            )
        # A positive-only endpoint is not permitted to assert absence
        # (docs/06-phase2-design.md:352).  Receiving it is a connector defect,
        # so the intent is escalated rather than refuted.
        return ReconciliationDecision(
            outcome=ReconciliationOutcome.PERMANENTLY_AMBIGUOUS,
            reason="positive-only-negative-evidence-contract-violation",
            evidence_class=result.value,
        )

    if result is ReadbackResult.CONFLICT:
        return ReconciliationDecision(
            outcome=ReconciliationOutcome.PERMANENTLY_AMBIGUOUS,
            reason="conflicting-readback-evidence",
            evidence_class=result.value,
        )

    if result is ReadbackResult.UNKNOWN:
        return ReconciliationDecision(
            outcome=ReconciliationOutcome.RETRY,
            reason="reconciliation-unknown-scheduled-backoff",
            evidence_class=result.value,
        )

    raise ConnectorContractError(  # pragma: no cover - enum is exhaustive above
        "unhandled read-back result"
    )
