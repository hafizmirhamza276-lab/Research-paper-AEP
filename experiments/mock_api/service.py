"""MockLegacyAPI: a standalone non-idempotent legacy endpoint with an oracle.

PAPER_ROADMAP.md section 3.1(1). The service simulates the class of system AEP
exists for: one that applies effects the caller cannot undo and cannot always
observe. Its distinguishing feature is that *it* always knows what it applied,
and records that in a durable ground-truth ledger the caller cannot read.

Routes
------

``POST /v1/endpoints/{endpoint}/mutations``
    Apply one mutation. The body is the exact request envelope produced by
    ``aep_core.core.request_binding.build_exact_request_bytes``. The optional
    ``X-AEP-Client-Reference`` header is stored opaquely so read-back can find
    the mutation later; it is never an input to duplicate detection.

``GET /v1/endpoints/{endpoint}/readback``
    Read-only reconciliation, permitted only where the endpoint's capability
    permits it. The answer is checked against
    ``connector_contract.PERMITTED_READBACK_RESULTS`` before it is returned,
    so the service cannot assert evidence its declared capability may not
    produce -- the exact defect ``classify_readback`` treats as a connector
    contract violation.

``GET /v1/config``, ``GET /v1/health``
    The loaded configuration and its digest.

``GET /v1/oracle/{mutations,duplicates,consistency}``
    The ground truth. Separated under ``/oracle`` because nothing the protocol
    under evaluation talks to may read it.

Fault model
-----------

Three faults are drawn per mutation, always in the same order and always all
three, so that enabling one does not shift the random stream of the others and
two configurations remain comparable under a shared seed:

1. ``server_error`` -- refuse **before** applying, with 503.
2. ``timeout`` -- apply, then never answer within any sane client timeout.
3. ``duplicate_response`` -- apply a second time before answering.

(1) and (2) are deliberately complementary: they are the two truths that can
hide behind one ambiguous outcome, and telling them apart is what recovery is
for. A configuration with both probabilities at zero injects nothing.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse

from aep_core.core.connector_contract import (
    PERMITTED_READBACK_RESULTS,
    ReadbackResult,
    ReconciliationCapability,
    result_is_permitted,
)

from experiments.mock_api.config import (
    EndpointConfig,
    MockApiConfig,
    ReadbackKeying,
    load_config,
)
from experiments.mock_api.fingerprint import (
    FingerprintError,
    mutation_fingerprint,
    payload_digest,
)
from experiments.mock_api.ledger import GroundTruthLedger

#: How long a "lost response" occupies a worker before it is abandoned. Not a
#: fault knob: the fault is that no response arrives within the caller's
#: timeout, and every client timeout in the evaluation is far below this. The
#: bound exists only so a killed client cannot leak a request task forever.
TIMEOUT_HOLD_SECONDS = 30.0

#: Header carrying the caller's own request identifier. Opaque to the oracle.
CLIENT_REFERENCE_HEADER = "X-AEP-Client-Reference"


def _now_ms() -> int:
    return int(time.time() * 1000)


class MockLegacyAPI:
    """Configuration, ledger, seeded generator, and run log for one service."""

    def __init__(self, config: MockApiConfig) -> None:
        self.config = config
        self._ledger: GroundTruthLedger | None = None
        self._owns_ledger = False
        self._random = random.Random(config.seed)
        self.run_log_path = Path(config.ledger_path).with_suffix(".run.jsonl")

    @classmethod
    def from_config_path(cls, path: str | Path) -> "MockLegacyAPI":
        return cls(load_config(path))

    # -- lifecycle ---------------------------------------------------------

    def start(self, *, ledger: GroundTruthLedger | None = None) -> None:
        """Open the ledger and write the run log's opening record."""
        if ledger is None:
            ledger = GroundTruthLedger(self.config.ledger_path)
            ledger.initialise()
            self._owns_ledger = True
        self._ledger = ledger
        self.run_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._append_event(
            {
                "event": "run_started",
                # The whole configuration, not a summary: a run whose log does
                # not say what the API was doing cannot be interpreted later.
                "config": self.config.echo(),
            }
        )

    def stop(self) -> None:
        if self._ledger is not None and self._owns_ledger:
            self._ledger.close()
        self._ledger = None
        self._owns_ledger = False

    @property
    def ledger(self) -> GroundTruthLedger:
        if self._ledger is None:
            raise RuntimeError("MockLegacyAPI.start() has not been called")
        return self._ledger

    # -- run log -----------------------------------------------------------

    def _append_event(self, event: dict[str, Any]) -> None:
        record = {
            "at_ms": _now_ms(),
            "config_digest": self.config.config_digest,
            **event,
        }
        with self.run_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    # -- fault decisions ---------------------------------------------------

    def draw_faults(self, endpoint_name: str) -> tuple[bool, bool, bool]:
        """Draw all three fault decisions, in a fixed order, unconditionally."""
        faults = self.config.endpoint(endpoint_name).faults
        server_error = self._random.random() < faults.server_error_probability
        timeout = self._random.random() < faults.timeout_probability
        duplicate = self._random.random() < faults.duplicate_response_probability
        return server_error, timeout, duplicate

    def draw_delay(self, endpoint_name: str) -> float:
        return self.config.endpoint(endpoint_name).faults.delay.sample(self._random)

    # -- applying ----------------------------------------------------------

    def _crash_hooks(self, endpoint: EndpointConfig):
        """Turn the endpoint's crash simulation into two plain callables."""
        simulation = endpoint.crash_simulation
        if not simulation.is_armed:
            return None, None

        def touch_marker(phase: str) -> None:
            if simulation.progress_marker_path:
                Path(simulation.progress_marker_path).write_text(
                    phase, encoding="utf-8"
                )

        # The marker is written only by the hold that is actually armed. A
        # marker written on both sides would let a waiting test observe
        # "in transaction" microseconds before the commit and kill just after
        # it, which is precisely the ambiguity the crash tests exist to
        # remove from their own setup.
        def before_commit() -> None:
            if simulation.hold_in_transaction_seconds:
                touch_marker("in-transaction")
                time.sleep(simulation.hold_in_transaction_seconds)

        def after_commit() -> None:
            if simulation.hold_after_commit_seconds:
                touch_marker("after-commit")
                time.sleep(simulation.hold_after_commit_seconds)

        return before_commit, after_commit

    def apply_mutation(
        self,
        *,
        endpoint: EndpointConfig,
        envelope: dict[str, Any],
        fingerprint: str,
        digest: str,
        client_reference: str | None,
        delivery_index: int,
    ):
        """Record one applied mutation. Blocking: run it off the event loop."""
        before_commit, after_commit = self._crash_hooks(endpoint)
        applied = self.ledger.record_applied_mutation(
            call_id=f"mock-call-{uuid.uuid4()}",
            endpoint=endpoint.name,
            target=str(envelope["target"]),
            fingerprint=fingerprint,
            payload_digest=digest,
            client_reference=client_reference,
            response_class=endpoint.response_class.value,
            delivery_index=delivery_index,
            applied_at_ms=_now_ms(),
            before_commit=before_commit,
            after_commit=after_commit,
        )
        self._append_event(
            {
                "event": "mutation_applied",
                "endpoint": endpoint.name,
                "call_id": applied.call_id,
                "fingerprint": applied.fingerprint,
                "payload_digest": applied.payload_digest,
                "client_reference": applied.client_reference,
                "delivery_index": applied.delivery_index,
            }
        )
        return applied

    def record_refusal(self, *, endpoint: str, reason: str, status: int) -> None:
        self._append_event(
            {
                "event": "mutation_refused",
                "endpoint": endpoint,
                "reason": reason,
                "status": status,
            }
        )


class ReadbackInputError(Exception):
    """The caller did not supply what this run's keying needs to answer."""


def _readback_applications(
    api: MockLegacyAPI,
    endpoint: EndpointConfig,
    *,
    client_reference: str | None,
    identity: dict[str, Any] | None,
):
    """Find the past applications this run's keying says the caller may find.

    The keying is read from the *configuration*, never from the request: which
    input is authoritative is a property of the run (amendment C1), so the
    input the keying does not name is ignored even when it is present and
    correct. ``tests/test_readback_keying.py`` asserts both directions of that.
    """
    keying = api.config.readback_keying

    if keying is ReadbackKeying.CALLER_REFERENCE:
        if not client_reference:
            raise ReadbackInputError(
                "this run is keyed on CALLER_REFERENCE; supply client_reference"
            )
        rows = api.ledger.applications_for_client_reference(client_reference)
    else:
        if not identity:
            raise ReadbackInputError(
                "this run is keyed on ORACLE_FINGERPRINT; supply identity, an "
                "object carrying connector_operation, operation_version, "
                "target and public_fields for the mutation being asked about"
            )
        try:
            # The same method the mutation was made with: F(r) binds it, so a
            # read-back claiming a different method is asking about a
            # different mutation.
            fingerprint = mutation_fingerprint(
                method="POST",
                endpoint=endpoint.name,
                envelope=identity,
                identity_fields=endpoint.identity_fields,
            )
        except FingerprintError as error:
            raise ReadbackInputError(
                f"identity descriptor cannot be fingerprinted: {error}"
            ) from None
        rows = api.ledger.applications_for_fingerprint(fingerprint)

    return [row for row in rows if row.endpoint == endpoint.name]


def _readback_result(
    api: MockLegacyAPI,
    endpoint: EndpointConfig,
    *,
    client_reference: str | None = None,
    identity: dict[str, Any] | None = None,
) -> ReadbackResult:
    """Decide what this endpoint's capability permits it to say.

    The capability's permitted-result set comes from the production contract,
    so an endpoint that cannot prove absence never says NOT_APPLIED and the
    difference between the response classes is enforced here rather than
    described in prose.
    """
    permitted = PERMITTED_READBACK_RESULTS[endpoint.response_class]
    applications = _readback_applications(
        api, endpoint, client_reference=client_reference, identity=identity
    )

    if len(applications) > 1:
        return ReadbackResult.CONFLICT
    if applications:
        return ReadbackResult.APPLIED
    # Absence is only assertable by a capability permitted to assert it.
    if ReadbackResult.NOT_APPLIED in permitted:
        return ReadbackResult.NOT_APPLIED
    return ReadbackResult.UNKNOWN


def create_app(api: MockLegacyAPI) -> FastAPI:
    """Build the ASGI application around an already-started service."""

    app = FastAPI(
        title="MockLegacyAPI",
        summary="Non-idempotent legacy endpoint with a ground-truth oracle",
        version=api.config.config_version,
    )
    app.state.api = api

    @app.get("/v1/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "config_digest": api.config.config_digest}

    @app.get("/v1/config")
    async def configuration() -> dict[str, Any]:
        return api.config.echo()

    @app.post("/v1/endpoints/{endpoint_name}/mutations")
    async def mutate(
        endpoint_name: str,
        request: Request,
        x_aep_client_reference: str | None = Header(default=None),
    ) -> Response:
        try:
            endpoint = api.config.endpoint(endpoint_name)
        except Exception:
            api.record_refusal(
                endpoint=endpoint_name, reason="unknown-endpoint", status=404
            )
            return JSONResponse(
                {"detail": f"no endpoint named {endpoint_name!r}"}, status_code=404
            )

        raw = await request.body()
        try:
            envelope = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            api.record_refusal(
                endpoint=endpoint_name, reason="unparseable-body", status=400
            )
            return JSONResponse({"detail": "body is not JSON"}, status_code=400)

        try:
            fingerprint = mutation_fingerprint(
                method="POST",
                endpoint=endpoint.name,
                envelope=envelope,
                identity_fields=endpoint.identity_fields,
            )
            digest = payload_digest(envelope)
        except FingerprintError as error:
            # An unidentifiable request is refused rather than applied: the
            # oracle could not attribute its effect to any mutation.
            api.record_refusal(
                endpoint=endpoint_name, reason=f"unidentifiable:{error}", status=422
            )
            return JSONResponse({"detail": str(error)}, status_code=422)

        server_error, timeout, duplicate = api.draw_faults(endpoint.name)
        delay = api.draw_delay(endpoint.name)

        if server_error:
            api.record_refusal(
                endpoint=endpoint_name, reason="injected-server-error", status=503
            )
            if delay:
                await asyncio.sleep(delay)
            return JSONResponse(
                {"detail": "upstream unavailable"}, status_code=503
            )

        applied = await asyncio.to_thread(
            api.apply_mutation,
            endpoint=endpoint,
            envelope=envelope,
            fingerprint=fingerprint,
            digest=digest,
            client_reference=x_aep_client_reference,
            delivery_index=1,
        )
        if duplicate:
            # The provider handled the same request twice. The caller will
            # never learn this; the ledger records both applications.
            await asyncio.to_thread(
                api.apply_mutation,
                endpoint=endpoint,
                envelope=envelope,
                fingerprint=fingerprint,
                digest=digest,
                client_reference=x_aep_client_reference,
                delivery_index=2,
            )

        if delay:
            await asyncio.sleep(delay)
        if timeout:
            # Applied, and the caller will never hear so.
            await asyncio.sleep(TIMEOUT_HOLD_SECONDS)
            return JSONResponse({"detail": "no response"}, status_code=504)

        return JSONResponse(
            {
                "call_id": applied.call_id,
                "outcome": "APPLIED",
                "external_reference": applied.external_reference,
            }
        )

    async def _answer_readback(
        endpoint_name: str,
        *,
        client_reference: str | None,
        identity: dict[str, Any] | None,
    ) -> Response:
        """The one read-back implementation both routes share."""
        try:
            endpoint = api.config.endpoint(endpoint_name)
        except Exception:
            return JSONResponse(
                {"detail": f"no endpoint named {endpoint_name!r}"}, status_code=404
            )

        if not PERMITTED_READBACK_RESULTS[endpoint.response_class]:
            # The capability permits no evidence at all, so the endpoint has
            # no read-back to offer and must not invent one. Checked before
            # the keying: what a capability may assert outranks how a run
            # chose to index it.
            return JSONResponse(
                {
                    "detail": "this endpoint's capability permits no read-back "
                    "evidence; the caller must escalate instead of querying"
                },
                status_code=409,
            )

        try:
            result = await asyncio.to_thread(
                _readback_result,
                api,
                endpoint,
                client_reference=client_reference,
                identity=identity,
            )
        except ReadbackInputError as error:
            return JSONResponse({"detail": str(error)}, status_code=422)

        if not result_is_permitted(endpoint.response_class, result):
            # Unreachable by construction; asserted because a service that
            # asserts evidence its capability may not produce would silently
            # corrupt every reconciliation decision made from it.
            return JSONResponse(
                {"detail": "internal contract violation"}, status_code=500
            )
        return JSONResponse(
            {
                "result": result.value,
                "response_class": endpoint.response_class.value,
                "readback_keying": api.config.readback_keying.value,
            }
        )

    @app.get("/v1/endpoints/{endpoint_name}/readback")
    async def readback(endpoint_name: str, client_reference: str) -> Response:
        """Read-back by caller reference. Cannot serve ORACLE_FINGERPRINT.

        A GET carries no room for a mutation description, so under
        ORACLE_FINGERPRINT keying this route refuses rather than quietly
        falling back to the caller reference -- which would answer a question
        the run is not asking, under a keying it is not configured for.
        """
        if api.config.readback_keying is not ReadbackKeying.CALLER_REFERENCE:
            return JSONResponse(
                {
                    "detail": "this run is keyed on "
                    f"{api.config.readback_keying.value}; the GET route can "
                    "only answer CALLER_REFERENCE read-backs. POST an identity "
                    "descriptor instead."
                },
                status_code=409,
            )
        return await _answer_readback(
            endpoint_name, client_reference=client_reference, identity=None
        )

    @app.post("/v1/endpoints/{endpoint_name}/readback")
    async def readback_described(endpoint_name: str, request: Request) -> Response:
        """Read-back under either keying.

        The caller sends both what it knows: the reference it used, and a
        description of the mutation. The *service* decides which one is
        authoritative, from its own configuration.
        """
        try:
            body = json.loads(await request.body() or b"{}")
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"detail": "body is not JSON"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"detail": "body must be an object"}, status_code=400)

        identity = body.get("identity")
        if identity is not None and not isinstance(identity, dict):
            return JSONResponse(
                {"detail": "identity must be an object"}, status_code=400
            )
        client_reference = body.get("client_reference")
        if client_reference is not None and not isinstance(client_reference, str):
            return JSONResponse(
                {"detail": "client_reference must be a string"}, status_code=400
            )

        return await _answer_readback(
            endpoint_name, client_reference=client_reference, identity=identity
        )

    # -- the oracle. Never reachable by the protocol under evaluation. -----

    @app.get("/v1/oracle/mutations")
    async def oracle_mutations() -> dict[str, Any]:
        rows = await asyncio.to_thread(api.ledger.applied_mutations)
        return {
            "config_digest": api.config.config_digest,
            "applied_mutations": [vars(row) for row in rows],
        }

    @app.get("/v1/oracle/duplicates")
    async def oracle_duplicates() -> dict[str, Any]:
        groups = await asyncio.to_thread(api.ledger.duplicate_groups)
        return {
            "config_digest": api.config.config_digest,
            "duplicate_application_count": sum(
                group.duplicate_applications for group in groups
            ),
            "groups": [
                {
                    "fingerprint": group.fingerprint,
                    "endpoint": group.endpoint,
                    "duplicate_class": group.duplicate_class.value,
                    "applications": group.applications,
                    "duplicate_applications": group.duplicate_applications,
                    "distinct_payloads": group.distinct_payloads,
                    "call_ids": list(group.call_ids),
                }
                for group in groups
            ],
        }

    @app.get("/v1/oracle/consistency")
    async def oracle_consistency() -> dict[str, Any]:
        report = await asyncio.to_thread(api.ledger.consistency_report)
        return {
            "config_digest": api.config.config_digest,
            "is_consistent": report.is_consistent,
            "applied_rows": report.applied_rows,
            "total_effect_count": report.total_effect_count,
            "disagreeing_resources": [
                list(entry) for entry in report.disagreeing_resources
            ],
        }

    return app


def build_app(config_path: str | Path) -> FastAPI:
    """Load, start, and wrap a service in one call (uvicorn entry point)."""
    api = MockLegacyAPI.from_config_path(config_path)
    api.start()
    return create_app(api)
