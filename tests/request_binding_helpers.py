"""Explicit test-only request binding composition for Phase 2 tests."""

from __future__ import annotations

import uuid

from aep_core.core.request_binding import (
    CommitmentKeyring,
    EndpointProfile,
    ExactMutationRequest,
    ProtectedFieldClass,
    ReconciliationContext,
    RequestBindingService,
    SafeValueKind,
    SafeValueRule,
)
from aep_core.core.request_vault import TestOnlyInMemoryRequestVault


DEFAULT_CONNECTOR = "mock.non-idempotent.v1/mutate"


def test_profile(
    connector_operation: str = DEFAULT_CONNECTOR,
    *,
    endpoint_profile_version: str = "1",
) -> EndpointProfile:
    return EndpointProfile(
        connector_identity="mock-connector",
        connector_operation=connector_operation,
        operation_version="1",
        endpoint_profile_id="mock-endpoint",
        endpoint_profile_version=endpoint_profile_version,
        credential_binding_id="mock-credential",
        credential_binding_version="1",
        wire_codec_version="mock-wire/1",
        public_field_rules={
            "action": SafeValueRule(
                kind=SafeValueKind.STRING,
                allowed_strings=frozenset({"capture", "void"}),
            ),
            "amount_minor": SafeValueRule(
                kind=SafeValueKind.INTEGER,
                minimum_integer=0,
                maximum_integer=1_000_000,
            ),
        },
        protected_field_classes={
            "authorization": ProtectedFieldClass.SECRET_AUTH,
            "cookie": ProtectedFieldClass.COOKIE,
            "token": ProtectedFieldClass.TOKEN,
            "credential": ProtectedFieldClass.SECRET_AUTH,
            "payment_value": ProtectedFieldClass.PAYMENT,
            "personal_identifier": ProtectedFieldClass.PERSONAL_INFORMATION,
        },
        mutation_option_rules={
            "notify": SafeValueRule(kind=SafeValueKind.BOOLEAN),
        },
    )


def test_vault() -> TestOnlyInMemoryRequestVault:
    return TestOnlyInMemoryRequestVault(
        encryption_keys={"test-vault-key-1": b"v" * 32},
        active_key_id="test-vault-key-1",
        test_only_acknowledgement=True,
    )


def test_binding_service(
    connector_operation: str = DEFAULT_CONNECTOR,
    *,
    vault=None,
) -> RequestBindingService:
    return RequestBindingService(
        profile=test_profile(connector_operation),
        commitment_keys=CommitmentKeyring(
            keys={"test-commitment-key-1": b"c" * 32},
            active_key_id="test-commitment-key-1",
        ),
        vault=vault or test_vault(),
    )


def test_request(
    *,
    target: str = "account-redacted-17",
    protected_fields=None,
) -> ExactMutationRequest:
    return ExactMutationRequest(
        target=target,
        public_fields={"action": "capture", "amount_minor": 1700},
        protected_fields=protected_fields or {},
        mutation_options={"notify": False},
    )


async def prepared_binding(
    *,
    execution_id: str,
    step_id: str,
    connector_operation: str = DEFAULT_CONNECTOR,
    target: str = "account-redacted-17",
    created_at_ms: int = 1_800_000_000_000,
    retention_ms: int = 31 * 24 * 60 * 60 * 1000,
):
    service = test_binding_service(connector_operation)
    intent_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    prepared = await service.prepare(
        execution_id=execution_id,
        step_id=step_id,
        intent_id=intent_id,
        correlation_id=correlation_id,
        request=test_request(target=target),
        created_at_ms=created_at_ms,
        intent_creation_not_after_ms=created_at_ms + 10_000,
        dispatch_material_not_after_ms=created_at_ms + 30_000,
        retention_not_after_ms=created_at_ms + retention_ms + 60_000,
    )
    return prepared.binding, intent_id, correlation_id


async def verified_dispatch(intent_id: str):
    service = test_binding_service()
    created_at_ms = 1_800_000_000_000
    prepared = await service.prepare(
        execution_id="execution-test",
        step_id="step-test",
        intent_id=intent_id,
        correlation_id="correlation-test",
        request=test_request(),
        created_at_ms=created_at_ms,
        intent_creation_not_after_ms=created_at_ms + 10_000,
        dispatch_material_not_after_ms=created_at_ms + 30_000,
        retention_not_after_ms=created_at_ms + 31 * 24 * 60 * 60 * 1000,
    )
    return await service.verify(
        binding=prepared.binding,
        execution_id="execution-test",
        step_id="step-test",
        intent_id=intent_id,
        correlation_id="correlation-test",
        now_ms=created_at_ms + 1,
        minimum_retention_not_after_ms=created_at_ms,
    )


def reconciliation_context(intent_id: str) -> ReconciliationContext:
    return ReconciliationContext(
        execution_id="execution-test",
        step_id="step-test",
        intent_id=intent_id,
        correlation_id="correlation-test",
        connector_operation=DEFAULT_CONNECTOR,
        redacted_target="account-redacted-17",
        request_fingerprint="a" * 64,
        attempt_count=0,
    )
