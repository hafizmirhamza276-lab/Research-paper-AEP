"""Fixtures for the baseline tests.

Redis fixtures are re-exported from ``tests/conftest.py`` rather than
reimplemented, for the reason that conftest states at length: the
test-instance-marker guard that stops a mis-pointed ``REDIS_URL`` from deleting
production keys must have exactly one definition.

The connector double here is deliberately *not* a mock of the protocol's
connector interface. It implements ``transmit`` -- the one method the baselines
call -- and records what reached the wire, because every claim a baseline test
makes ("it retried", "it sent no client reference", "it dispatched once") is a
claim about the wire and not about the caller's internal state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pytest

from experiments.mock_api.client import (
    MockLegacyApiAmbiguity,
    MutationEvidence,
    MutationResponse,
)

from tests.conftest import (  # noqa: F401 -- re-exported as fixtures
    cjson_available,
    lock_manager,
    redis_client,
    storage_adapter,
)


@dataclass
class Transmission:
    """One thing that reached the provider."""

    exact_request_bytes: bytes
    client_reference: str | None
    client_timeout: float
    # WS-1a. Recorded so a test can assert every system sends it,
    # including the baselines that send no client_reference.
    execution_id: str | None = None


@dataclass
class RecordingConnector:
    """A connector that records transmissions and answers from a script.

    ``script`` is consumed one entry per transmission; when it runs out the
    last entry repeats. An entry is either a :class:`MutationResponse` to
    return or an exception instance to raise, which is how an ambiguous
    outcome is expressed -- the real connector raises
    :class:`MockLegacyApiAmbiguity` and never returns one.
    """

    script: list[Any] = field(default_factory=list)
    transmissions: list[Transmission] = field(default_factory=list)
    on_transmit: Callable[[int], None] | None = None
    closed: bool = False

    # The two attributes ``WriteAheadRunner`` and the baselines' startup
    # validation read. Neither is a test affordance: they are the connector's
    # own declaration about what kind of endpoint it is.
    test_only = False
    evaluation_endpoint = True

    async def transmit(
        self,
        *,
        exact_request_bytes: bytes,
        client_reference: str | None,
        client_timeout: float,
        execution_id: str | None = None,
    ) -> MutationResponse:
        index = len(self.transmissions)
        self.transmissions.append(
            Transmission(
                exact_request_bytes=exact_request_bytes,
                client_reference=client_reference,
                client_timeout=client_timeout,
                execution_id=execution_id,
            )
        )
        if self.on_transmit is not None:
            self.on_transmit(index)
        if not self.script:
            return MutationResponse(
                call_id=f"call-{index}", evidence=MutationEvidence.DEFINITIVE_SUCCESS
            )
        entry = self.script[min(index, len(self.script) - 1)]
        if isinstance(entry, BaseException):
            raise entry
        return entry

    async def aclose(self) -> None:
        self.closed = True


def ambiguous(message: str = "no usable response: ReadTimeout"):
    return MockLegacyApiAmbiguity(message)


def applied(call_id: str = "call-1") -> MutationResponse:
    return MutationResponse(
        call_id=call_id, evidence=MutationEvidence.DEFINITIVE_SUCCESS
    )


def refused() -> MutationResponse:
    return MutationResponse(
        call_id=None, evidence=MutationEvidence.DEFINITIVE_FAILURE
    )


@pytest.fixture
def connector() -> RecordingConnector:
    return RecordingConnector()
