"""The AEP-side connector for MockLegacyAPI.

This is what a ``WriteAheadRunner`` in EVALUATION mode dispatches through. It
is an ordinary HTTP client and is deliberately ignorant: it never reads the
service's ``/v1/oracle`` routes, so no measurement can be contaminated by the
protocol knowing the ground truth it is being scored against.

**What the caller is allowed to conclude from a response.** The mapping below
is the whole of the connector's evidence policy, and it is conservative by
construction:

======================  =================================================
``200``                 definitive success -- the provider said it applied
``4xx``                 definitive failure -- refused before applying
``5xx``                 *ambiguous* -- raised, never treated as a failure
timeout / transport     *ambiguous* -- raised
======================  =================================================

The 5xx row is the one that matters. This repository's mock API happens to
implement its injected 5xx as a refusal *before* applying, but a real caller
cannot know that, and neither may this one: a connector that mapped 5xx to
"definitely not applied" would be reading the oracle through the response
code. Everything not definitively one thing or the other is ambiguous, which
is exactly what the protocol is designed to handle.

The declared ``reconciliation_capability`` is supplied by the caller as a
``ReconciliationCapability`` member from the production contract, so the
runner's ``declared_capability`` check and ``classify_readback`` see the same
vocabulary the service was configured with.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from aep_core.core.connector_contract import (
    ReadbackResult,
    ReconciliationCapability,
)
from aep_core.core.request_binding import (
    ReconciliationContext,
    VerifiedDispatch,
    consume_verified_dispatch,
)

from experiments.mock_api.service import CLIENT_REFERENCE_HEADER


class MutationEvidence(str, Enum):
    """What the caller was permitted to learn from one mutation call.

    These strings are the ones a ``ConnectorPolicy`` declares in
    ``definitive_success_evidence`` / ``definitive_failure_evidence``; the
    protocol treats that vocabulary as connector-supplied configuration rather
    than as a fixed contract, so it is declared here rather than imported.
    """

    DEFINITIVE_SUCCESS = "DEFINITIVE_SUCCESS"
    DEFINITIVE_FAILURE = "DEFINITIVE_FAILURE"


@dataclass(frozen=True)
class MutationResponse:
    """A definitive outcome. Ambiguity is raised, never returned."""

    call_id: str | None
    evidence: MutationEvidence
    external_reference: str | None = None


@dataclass(frozen=True)
class ReadbackObservation:
    """One read-only reconciliation answer, in the contract's vocabulary."""

    intent_id: str
    result: ReadbackResult


class MockLegacyApiAmbiguity(Exception):
    """The call may or may not have applied. The only honest conclusion."""


class MockLegacyApiConnector:
    """Dispatch one non-idempotent mutation to a running MockLegacyAPI."""

    #: Not a test double: this connector speaks to a real process over a real
    #: socket, which is what lets EVALUATION mode accept it.
    test_only = False
    #: The one respect in which EVALUATION differs from PRODUCTION.
    evaluation_endpoint = True

    def __init__(
        self,
        *,
        base_url: str,
        endpoint: str,
        reconciliation_capability: ReconciliationCapability,
        connector_identity: str,
        connector_operation: str,
        endpoint_profile_id: str,
        endpoint_profile_version: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not isinstance(reconciliation_capability, ReconciliationCapability):
            raise TypeError(
                "reconciliation_capability must be a declared contract member"
            )
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint
        self.reconciliation_capability = reconciliation_capability
        self.connector_identity = connector_identity
        self.connector_operation = connector_operation
        self.endpoint_profile_id = endpoint_profile_id
        self.endpoint_profile_version = endpoint_profile_version
        self._client = client
        self._owns_client = client is None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def mutate(
        self, *, dispatch: VerifiedDispatch, client_timeout: float
    ) -> MutationResponse:
        """Send exactly one mutation. No transport-level retry, ever."""
        binding = dispatch.binding
        # Carried so read-back can find this mutation later. Opaque to the
        # oracle: the service stores it and never uses it to decide whether
        # two applications are the same mutation.
        client_reference = binding.request_fingerprint

        exact_request_bytes = consume_verified_dispatch(
            dispatch,
            connector_identity=self.connector_identity,
            connector_operation=self.connector_operation,
            endpoint_profile_id=self.endpoint_profile_id,
            endpoint_profile_version=self.endpoint_profile_version,
            execution_id=binding.execution_id,
            step_id=binding.step_id,
            intent_id=binding.intent_id,
            correlation_id=binding.correlation_id,
        )

        http = await self._http()
        try:
            response = await http.post(
                f"{self.base_url}/v1/endpoints/{self.endpoint}/mutations",
                content=exact_request_bytes,
                headers={
                    "content-type": "application/json",
                    CLIENT_REFERENCE_HEADER: client_reference,
                },
                timeout=client_timeout,
            )
        except httpx.HTTPError as error:
            raise MockLegacyApiAmbiguity(
                f"no usable response: {type(error).__name__}"
            ) from None

        if response.status_code == 200:
            body = self._json_or_none(response)
            return MutationResponse(
                call_id=(body or {}).get("call_id"),
                evidence=MutationEvidence.DEFINITIVE_SUCCESS,
                external_reference=(body or {}).get("external_reference"),
            )
        if 400 <= response.status_code < 500:
            return MutationResponse(
                call_id=None, evidence=MutationEvidence.DEFINITIVE_FAILURE
            )
        raise MockLegacyApiAmbiguity(
            f"provider returned {response.status_code}; applied state unknown"
        )

    async def read_back(
        self, *, context: ReconciliationContext, readback_timeout: float
    ) -> ReadbackObservation:
        """Ask the provider what it knows, within what its class may assert."""
        if not isinstance(context, ReconciliationContext):
            raise TypeError("a safe reconciliation context is required")

        http = await self._http()
        response = await http.get(
            f"{self.base_url}/v1/endpoints/{self.endpoint}/readback",
            params={"client_reference": context.request_fingerprint},
            timeout=readback_timeout,
        )
        if response.status_code != 200:
            # Including 409 from an endpoint whose class permits no read-back:
            # an uninformative answer is not evidence, and UNKNOWN keeps the
            # intent inside the bounded reconciliation budget.
            return ReadbackObservation(
                intent_id=context.intent_id, result=ReadbackResult.UNKNOWN
            )

        body = self._json_or_none(response) or {}
        try:
            result = ReadbackResult(body.get("result"))
        except ValueError:
            result = ReadbackResult.UNKNOWN
        return ReadbackObservation(intent_id=context.intent_id, result=result)

    @staticmethod
    def _json_or_none(response: httpx.Response) -> dict[str, Any] | None:
        try:
            body = response.json()
        except ValueError:
            return None
        return body if isinstance(body, dict) else None
