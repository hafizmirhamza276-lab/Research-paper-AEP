"""The connector side of read-back keying.

The connector must stay ignorant of which keying a run uses. It sends both
things it legitimately knows -- the reference it minted, and a description of
the mutation it made -- and the *service* decides which one is authoritative.
Any other arrangement would let the system under test behave differently
depending on the measurement configuration, which is the one thing an
apparatus must never cause.
"""

from __future__ import annotations

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

from aep_core.core.connector_contract import ReadbackResult, ReconciliationCapability
from aep_core.core.request_binding import ReconciliationContext
from experiments.mock_api.client import MockLegacyApiConnector
from experiments.mock_api.config import ReadbackKeying
from experiments.mock_api.service import MockLegacyAPI, create_app

from experiments.mock_api.tests.test_readback_keying import (
    ENDPOINT,
    build,
    identity_of,
    mutate,
)


def _context(fingerprint: str) -> ReconciliationContext:
    return ReconciliationContext(
        execution_id="00000000-0000-4000-8000-000000000001",
        step_id="charge-card",
        intent_id="00000000-0000-4000-8000-000000000002",
        correlation_id="00000000-0000-4000-8000-000000000003",
        connector_operation="mock.non-idempotent.v1/mutate",
        redacted_target="account-redacted-17",
        request_fingerprint=fingerprint,
        attempt_count=0,
    )


def _connector(app, *, resolver=None) -> MockLegacyApiConnector:
    return MockLegacyApiConnector(
        base_url="http://mock-api",
        endpoint=ENDPOINT,
        reconciliation_capability=ReconciliationCapability.AUTHORITATIVE_READBACK,
        connector_identity="mock-connector",
        connector_operation="mock.non-idempotent.v1/mutate",
        endpoint_profile_id="mock-endpoint",
        endpoint_profile_version="1",
        client=httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://mock-api"
        ),
        readback_identity_resolver=resolver,
    )


def _serve(tmp_path, keying):
    api = build(tmp_path, keying=keying)
    api.start()
    app = create_app(api)
    return api, app


REFERENCE = "a" * 64


@pytest.mark.asyncio
async def test_without_a_resolver_the_connector_uses_the_original_get_route(tmp_path):
    api, app = _serve(tmp_path, ReadbackKeying.CALLER_REFERENCE)
    try:
        with TestClient(app) as seeding_client:
            mutate(seeding_client, reference=REFERENCE)
        connector = _connector(app)
        try:
            observation = await connector.read_back(
                context=_context(REFERENCE), readback_timeout=5.0
            )
        finally:
            await connector.aclose()
    finally:
        api.stop()

    assert observation.result is ReadbackResult.APPLIED


@pytest.mark.asyncio
async def test_with_a_resolver_the_connector_describes_the_mutation(tmp_path):
    """The ORACLE_FINGERPRINT path, over a fresh reference the service ignores."""
    api, app = _serve(tmp_path, ReadbackKeying.ORACLE_FINGERPRINT)
    try:
        with TestClient(app) as seeding_client:
            mutate(seeding_client, reference="the-original-attempt")
        connector = _connector(app, resolver=lambda context: identity_of())
        try:
            observation = await connector.read_back(
                context=_context(REFERENCE), readback_timeout=5.0
            )
        finally:
            await connector.aclose()
    finally:
        api.stop()

    assert observation.result is ReadbackResult.APPLIED


@pytest.mark.asyncio
async def test_the_resolver_path_still_works_under_caller_reference_keying(tmp_path):
    """One connector configuration serves both runs; only the service differs."""
    api, app = _serve(tmp_path, ReadbackKeying.CALLER_REFERENCE)
    try:
        with TestClient(app) as seeding_client:
            mutate(seeding_client, reference=REFERENCE)
        connector = _connector(app, resolver=lambda context: identity_of())
        try:
            observation = await connector.read_back(
                context=_context(REFERENCE), readback_timeout=5.0
            )
        finally:
            await connector.aclose()
    finally:
        api.stop()

    assert observation.result is ReadbackResult.APPLIED


@pytest.mark.asyncio
async def test_an_unanswerable_readback_is_unknown_not_an_assertion(tmp_path):
    """A 422 is not evidence; it must not be read as NOT_APPLIED."""
    api, app = _serve(tmp_path, ReadbackKeying.ORACLE_FINGERPRINT)
    try:
        # No resolver, so the connector cannot describe the mutation and the
        # service refuses the GET route it would otherwise use.
        connector = _connector(app)
        try:
            observation = await connector.read_back(
                context=_context(REFERENCE), readback_timeout=5.0
            )
        finally:
            await connector.aclose()
    finally:
        api.stop()

    assert observation.result is ReadbackResult.UNKNOWN


def test_the_connector_source_never_names_a_keying(tmp_path):
    """Structural: the system under test must not branch on the measurement."""
    from pathlib import Path

    source = Path(
        MockLegacyApiConnector.__module__.replace(".", "/") + ".py"
    ).read_text(encoding="utf-8")

    for keying in ReadbackKeying:
        assert keying.value not in source, (
            f"the connector mentions {keying.value}; it must send what it knows "
            "and let the service decide which input is authoritative"
        )
