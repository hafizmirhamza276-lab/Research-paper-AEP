"""What every system under test shares, so that only the differences differ.

A comparison is only worth reporting if the systems being compared are the same
everywhere the comparison does not intend them to differ. This module holds the
"everywhere else": the wire format, the evidence policy, the crash-checkpoint
mechanism, and the shape of a durable outcome record.

**The wire format is built once, here.** Every system sends the bytes
``aep_core.core.request_binding.build_exact_request_bytes`` produces, so the
oracle's Definition 1 fingerprints them identically and a duplicate is a
duplicate regardless of who caused it. What the baselines do *not* inherit is
the vault, the commitment keyring and the two-phase prepare/verify around those
bytes -- that machinery is the thing under ablation, and a baseline paying for
it would make the section 3.2 overhead comparison meaningless.

**The evidence policy is the connector's, not the caller's.** A ``200`` is
definitive success, a ``4xx`` is a definitive refusal before applying, and
everything else -- 5xx, timeout, transport error -- is ambiguous. That mapping
lives in ``experiments/mock_api/client.py`` and every system reads it from
there. A baseline that treated 5xx as "definitely not applied" would be reading
the oracle through the response code and would score better than it deserves.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Mapping, Protocol

from aep_core.core.request_binding import (
    EndpointProfile,
    ExactMutationRequest,
    build_exact_request_bytes,
)

from experiments.baselines.contract import (
    ExecutionOutcome,
    OutcomeClass,
    SystemId,
)
from experiments.mock_api.client import (
    MockLegacyApiAmbiguity,
    MutationEvidence,
    MutationResponse,
)

#: How long a baseline's outcome record lives. Matches the intent ledger's
#: unresolved retention so that a comparison of "what is still readable a day
#: later" is not an artefact of two different TTLs.
DEFAULT_RECORD_TTL_SECONDS = 7 * 24 * 60 * 60

#: The status words the baselines write into their own records. Deliberately
#: their own vocabulary -- a baseline borrowing ``IntentStatus`` would imply it
#: had the state machine that gives those words meaning.
STATUS_APPLIED = "APPLIED"
STATUS_REFUSED = "REFUSED"
STATUS_FAILED = "FAILED"
STATUS_SCHEDULED = "SCHEDULED"

#: How a baseline's own status maps onto the shared vocabulary the metrics use.
#: ``STATUS_FAILED`` is the load-bearing row: a baseline that has exhausted its
#: retries writes "failed" without any evidence that nothing was applied.
STATUS_TO_CLASS: Mapping[str, OutcomeClass] = {
    STATUS_APPLIED: OutcomeClass.CONFIRMED_APPLIED,
    STATUS_REFUSED: OutcomeClass.CONFIRMED_NOT_APPLIED,
    STATUS_FAILED: OutcomeClass.UNVERIFIED_FAILURE,
    # A record that says only "I was about to call" is not a claim about the
    # outcome at all. It is *not* a declared ambiguity either: B4 writes it and
    # then re-runs the activity rather than escalating.
    STATUS_SCHEDULED: OutcomeClass.UNVERIFIED_FAILURE,
}


class Transmitter(Protocol):
    """The one connector method every system in section 3.3 calls."""

    async def transmit(
        self,
        *,
        exact_request_bytes: bytes,
        client_reference: str | None,
        client_timeout: float,
    ) -> MutationResponse: ...


class Verdict(str, Enum):
    """What one transmission established."""

    APPLIED = "APPLIED"
    REFUSED = "REFUSED"
    AMBIGUOUS = "AMBIGUOUS"


def exact_bytes(profile: EndpointProfile, request: ExactMutationRequest) -> bytes:
    """The wire bytes, identical for every system under test."""
    return build_exact_request_bytes(profile, request)


async def transmit_once(
    connector: Transmitter,
    *,
    exact_request_bytes: bytes,
    client_reference: str | None,
    client_timeout: float,
) -> Verdict:
    """Send once and classify the answer conservatively.

    Note what is *not* here: no retry, no read-back, no interpretation of the
    status code beyond the connector's declared evidence policy. Each system
    decides what to do with a :attr:`Verdict.AMBIGUOUS`, and that decision is
    what the evaluation is measuring.
    """
    try:
        response = await connector.transmit(
            exact_request_bytes=exact_request_bytes,
            client_reference=client_reference,
            client_timeout=client_timeout,
        )
    except MockLegacyApiAmbiguity:
        return Verdict.AMBIGUOUS
    except Exception:
        # Any other connector failure is ambiguous too. Simulated process
        # death derives from BaseException and is deliberately not caught.
        return Verdict.AMBIGUOUS

    if response.evidence is MutationEvidence.DEFINITIVE_SUCCESS:
        return Verdict.APPLIED
    if response.evidence is MutationEvidence.DEFINITIVE_FAILURE:
        return Verdict.REFUSED
    return Verdict.AMBIGUOUS


class CheckpointMixin:
    """The crash-injection hook, on the same terms ``aep_core`` offers it.

    ``crash_injector is None`` is the disabled path -- one attribute load and
    one identity comparison -- so a baseline measured without crash injection
    is not paying for the ability to be crashed. The same property is asserted
    for ``aep_core`` in ``experiments/harness/tests/test_injector.py``.
    """

    crash_injector: Any = None
    crash_point_enum: type[Enum] | None = None

    async def _checkpoint(self, name: str) -> None:
        if self.crash_injector is not None:
            if self.crash_point_enum is None:
                raise RuntimeError(
                    "crash_point_enum is required when a crash injector is supplied"
                )
            await self.crash_injector.checkpoint(self.crash_point_enum[name])


async def write_outcome_record(
    redis_client,
    key: str,
    *,
    status: str,
    dispatch_attempts: int,
    ttl_seconds: int = DEFAULT_RECORD_TTL_SECONDS,
    extra: Mapping[str, Any] | None = None,
) -> None:
    """Write a baseline's own record of what happened.

    Plain ``SET``: unfenced, unversioned, unacknowledged. That is the point --
    only B2 fences its state writes, and only AEP-full and B4 wait for an
    acknowledgement.
    """
    payload = {
        "status": status,
        "dispatch_attempts": dispatch_attempts,
        **dict(extra or {}),
    }
    await redis_client.set(key, json.dumps(payload, sort_keys=True), ex=ttl_seconds)


async def read_outcome_record(
    redis_client, key: str, *, system: SystemId, execution_id: str
) -> ExecutionOutcome:
    """Read one back, distinguishing "absent" from "unreadable"."""
    raw = await redis_client.get(key)
    if raw is None:
        return ExecutionOutcome(
            system=system,
            execution_id=execution_id,
            status="NO_RECORD",
            outcome_class=OutcomeClass.NO_RECORD,
        )
    try:
        document = json.loads(raw)
        status = str(document["status"])
        outcome_class = STATUS_TO_CLASS[status]
    except (ValueError, TypeError, KeyError):
        # A record that exists and cannot be interpreted is a different
        # failure from one that was never written, and merging the two would
        # move counts between the lost-effect and corruption metrics.
        return ExecutionOutcome(
            system=system,
            execution_id=execution_id,
            status="UNREADABLE",
            outcome_class=OutcomeClass.UNREADABLE,
        )
    return ExecutionOutcome(
        system=system,
        execution_id=execution_id,
        status=status,
        outcome_class=outcome_class,
        dispatch_attempts=int(document.get("dispatch_attempts", 0)),
    )
