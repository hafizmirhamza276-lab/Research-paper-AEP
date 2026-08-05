"""P2-004/P2-010 final transport and privacy boundary tests."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from enum import Enum

import pytest

from aep_core.core.intent_workflow import ConnectorPolicy, WriteAheadRunner, WriteAheadWorkflowError
from aep_core.core.intents import IntentBindingError, IntentLedgerStore, IntentStatus
from aep_core.core.request_binding import (
    ExactMutationRequest,
    VerifiedDispatch,
    consume_verified_dispatch,
)
from aep_core.core.request_vault import (
    VaultAuthenticationError,
    VaultExpiredError,
    VaultMissingError,
)
from aep_core.core.storage import AEPExecutionState, AEPStatus
from aep_core.core.exceptions import StateCorruptionError
from tests.request_binding_helpers import (
    test_binding_service as _binding_service,
    test_profile as _profile,
    test_request as _request,
    test_vault as _vault,
)


class _Evidence(str, Enum):
    DEFINITIVE_SUCCESS = "DEFINITIVE_SUCCESS"


@dataclass(frozen=True)
class _Response:
    evidence: _Evidence = _Evidence.DEFINITIVE_SUCCESS
    call_id: str = "safe-call-1"
    external_reference: str = "safe-effect-1"


class _RecordingConnector:
    test_only = True
    connector_identity = "mock-connector"
    connector_operation = "mock.non-idempotent.v1/mutate"
    endpoint_profile_id = "mock-endpoint"
    endpoint_profile_version = "1"

    def __init__(self, *, fail=False):
        self.calls: list[VerifiedDispatch] = []
        self.fail = fail

    async def mutate(self, *, dispatch: VerifiedDispatch, client_timeout: float):
        consume_verified_dispatch(
            dispatch,
            connector_identity=self.connector_identity,
            connector_operation=self.connector_operation,
            endpoint_profile_id=self.endpoint_profile_id,
            endpoint_profile_version=self.endpoint_profile_version,
            execution_id=dispatch.binding.execution_id,
            step_id=dispatch.binding.step_id,
            intent_id=dispatch.binding.intent_id,
            correlation_id=dispatch.binding.correlation_id,
        )
        self.calls.append(dispatch)
        if self.fail:
            raise RuntimeError("provider-canary-must-not-escape")
        return _Response()


class _UnsafeResultConnector(_RecordingConnector):
    async def mutate(self, *, dispatch: VerifiedDispatch, client_timeout: float):
        consume_verified_dispatch(
            dispatch,
            connector_identity=self.connector_identity,
            connector_operation=self.connector_operation,
            endpoint_profile_id=self.endpoint_profile_id,
            endpoint_profile_version=self.endpoint_profile_version,
            execution_id=dispatch.binding.execution_id,
            step_id=dispatch.binding.step_id,
            intent_id=dispatch.binding.intent_id,
            correlation_id=dispatch.binding.correlation_id,
        )
        self.calls.append(dispatch)
        return _Response(
            call_id="TOKEN-CANARY-PROVIDER-CALL",
            external_reference="PII-CANARY-PROVIDER-REFERENCE",
        )


class _CountingBarrier:
    test_only = True

    def __init__(self):
        self.acknowledgements = 0

    async def confirm_durable(self, connection, timeout_ms):
        self.acknowledgements += 1
        return True


class _MissingOnDispatchVault(type(_vault())):
    def __init__(self):
        super().__init__(
            encryption_keys={"test-vault-key-1": b"v" * 32},
            active_key_id="test-vault-key-1",
            test_only_acknowledgement=True,
        )
        self.reads = 0

    async def read_exact(self, locator, *, now_ms):
        self.reads += 1
        if self.reads >= 2:
            raise VaultMissingError()
        return await super().read_exact(locator, now_ms=now_ms)


class _ExpiredOnDispatchVault(_MissingOnDispatchVault):
    async def read_exact(self, locator, *, now_ms):
        self.reads += 1
        if self.reads >= 2:
            raise VaultExpiredError()
        return await super(_MissingOnDispatchVault, self).read_exact(
            locator, now_ms=now_ms
        )


class _AlteredCiphertextOnDispatchVault(_MissingOnDispatchVault):
    async def read_exact(self, locator, *, now_ms):
        self.reads += 1
        if self.reads >= 2:
            self.test_only_corrupt_ciphertext(locator)
            with pytest.raises(VaultAuthenticationError):
                await super(_MissingOnDispatchVault, self).read_exact(
                    locator, now_ms=now_ms
                )
            raise VaultAuthenticationError()
        return await super(_MissingOnDispatchVault, self).read_exact(
            locator, now_ms=now_ms
        )


class _AlteredMetadataOnDispatchVault(type(_vault())):
    def __init__(self, field):
        super().__init__(
            encryption_keys={"test-vault-key-1": b"v" * 32},
            active_key_id="test-vault-key-1",
            test_only_acknowledgement=True,
        )
        self.field = field
        self.reads = 0
        self.metadata = None

    async def read_exact(self, locator, *, now_ms):
        self.reads += 1
        if self.reads == 2:
            metadata = self.metadata
            value = getattr(metadata, self.field)
            if self.field == "locator":
                changed = "vault_zyxwvutsrqponmlkjihgfedc"
            elif self.field == "encryption_key_id":
                changed = "missing-vault-key"
            elif isinstance(value, str):
                changed = value + "-changed"
            else:
                changed = value + 1
            self.test_only_replace_metadata(
                locator, metadata.model_copy(update={self.field: changed})
            )
        result = await super().read_exact(locator, now_ms=now_ms)
        self.metadata = result.metadata
        return result


class _AlterBindingAfterFirstAck(_CountingBarrier):
    def __init__(self, execution_id):
        super().__init__()
        self.execution_id = execution_id
        self.raw_after_replacement = None

    async def confirm_durable(self, connection, timeout_ms):
        self.acknowledgements += 1
        if self.acknowledgements == 1:
            key = f"aep:state:{self.execution_id}"
            state = json.loads(await connection.get(key))
            record = next(iter(state["intent_ledger"].values()))
            binding = json.loads(record["canonical_request_binding"])
            safe_fields = binding["safe_descriptor"]["public_fields"]
            action = next(item for item in safe_fields if item["name"] == "action")
            action["canonical_value"] = '"void"'
            record["canonical_request_binding"] = json.dumps(
                binding,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            self.raw_after_replacement = json.dumps(
                state, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
            await connection.set(key, self.raw_after_replacement, keepttl=True)
        return True


class _ChangeProfileAfterFirstAck(_CountingBarrier):
    def __init__(self, service):
        super().__init__()
        self.service = service

    async def confirm_durable(self, connection, timeout_ms):
        self.acknowledgements += 1
        if self.acknowledgements == 1:
            self.service.profile = _profile(endpoint_profile_version="2")
        return True


class _AlterCanonicalEncodingAfterFirstAck(_CountingBarrier):
    def __init__(self, execution_id, alteration):
        super().__init__()
        self.execution_id = execution_id
        self.alteration = alteration
        self.raw_after_replacement = None
        self.ttl_before_rejection = None

    async def confirm_durable(self, connection, timeout_ms):
        self.acknowledgements += 1
        if self.acknowledgements == 1:
            key = f"aep:state:{self.execution_id}"
            state = json.loads(await connection.get(key))
            record = next(iter(state["intent_ledger"].values()))
            binding = record["canonical_request_binding"]
            if self.alteration == "numeric-lexeme":
                changed = binding.replace(
                    '"request_material_version":1',
                    '"request_material_version":1.0',
                )
            else:
                changed = binding.replace(
                    '"protected_commitments":[]',
                    '"protected_commitments":{}',
                )
            assert changed != binding
            record["canonical_request_binding"] = changed
            self.raw_after_replacement = json.dumps(
                state, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
            await connection.set(key, self.raw_after_replacement, keepttl=True)
            self.ttl_before_rejection = await connection.pttl(key)
        return True


async def _seed(storage_adapter, lock_manager):
    execution_id = str(uuid.uuid4())
    token = await lock_manager.acquire_lock(execution_id, ttl_seconds=60)
    assert token
    await storage_adapter.save_state(
        AEPExecutionState(execution_id=execution_id, status=AEPStatus.IDLE),
        expected_version=0,
        lock_token=token,
        ttl_seconds=3600,
    )
    assert await lock_manager.release_lock(execution_id, token)
    return execution_id


def _runner(redis_client, lock_manager, connector, barrier, *, service=None, allow=True):
    return WriteAheadRunner(
        store=IntentLedgerStore(redis_client),
        lock_manager=lock_manager,
        connector=connector,
        barrier=barrier,
        policy=ConnectorPolicy(
            client_timeout_seconds=0.01,
            settlement_lag_seconds=0,
            buffer_margin_seconds=15,
            lock_ttl_seconds=30,
            durability_timeout_ms=100,
            lease_acquire_attempts=1,
        ),
        connector_name="mock.non-idempotent.v1/mutate",
        binding_service=service or _binding_service(),
        allow_test_barrier=True,
        allow_test_dispatch=allow,
    )


@pytest.mark.asyncio
async def test_valid_binding_dispatches_exactly_once_as_verified_object(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    connector = _RecordingConnector()
    barrier = _CountingBarrier()
    result = await _runner(redis_client, lock_manager, connector, barrier).execute(
        execution_id=execution_id,
        step_id="step-a",
        request=_request(),
    )
    assert result.status is IntentStatus.FIRED_CONFIRMED
    assert len(connector.calls) == 1
    assert barrier.acknowledgements == 2
    assert connector.calls[0].binding.intent_id == result.intent_id


@pytest.mark.asyncio
async def test_caller_mutation_after_vault_create_cannot_change_transmitted_bytes(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    public = {"action": "capture", "amount_minor": 1700}
    protected = {"authorization": "Bearer ORIGINAL"}
    options = {"notify": False}
    request = ExactMutationRequest(
        target="account-redacted-17",
        public_fields=public,
        protected_fields=protected,
        mutation_options=options,
    )
    connector = _RecordingConnector()
    service = _binding_service()
    original_create = service.vault.create_once

    async def mutate_after_create(material, metadata):
        result = await original_create(material, metadata)
        public["action"] = "substituted"
        protected["authorization"] = "Bearer SUBSTITUTED"
        options["notify"] = True
        return result

    service.vault.create_once = mutate_after_create
    await _runner(
        redis_client, lock_manager, connector, _CountingBarrier(), service=service
    ).execute(execution_id=execution_id, step_id="step-a", request=request)
    sent = connector.calls[0].exact_request_bytes
    assert b"ORIGINAL" in sent
    assert b"SUBSTITUTED" not in sent
    assert b'"action":"substituted"' not in sent


@pytest.mark.asyncio
async def test_missing_vault_after_durable_intent_has_zero_calls_and_no_extra_ack(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    connector = _RecordingConnector()
    barrier = _CountingBarrier()
    service = _binding_service(vault=_MissingOnDispatchVault())
    runner = _runner(redis_client, lock_manager, connector, barrier, service=service)
    with pytest.raises(WriteAheadWorkflowError) as exc_info:
        await runner.execute(execution_id=execution_id, step_id="step-a", request=_request())
    assert str(exc_info.value) == "verified-dispatch-rejected:vault-object-missing"
    assert connector.calls == []
    assert barrier.acknowledgements == 1
    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state and len(state.intent_ledger) == 1
    assert next(iter(state.intent_ledger.values())).status is IntentStatus.ABOUT_TO_FIRE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "vault_factory,reason",
    [
        (_ExpiredOnDispatchVault, "vault-object-expired"),
        (_AlteredCiphertextOnDispatchVault, "vault-authentication-failed"),
    ],
)
async def test_expired_or_unauthenticated_vault_has_zero_calls_and_no_extra_ack(
    redis_client, storage_adapter, lock_manager, vault_factory, reason
):
    execution_id = await _seed(storage_adapter, lock_manager)
    connector = _RecordingConnector()
    barrier = _CountingBarrier()
    service = _binding_service(vault=vault_factory())
    with pytest.raises(WriteAheadWorkflowError) as exc_info:
        await _runner(
            redis_client, lock_manager, connector, barrier, service=service
        ).execute(execution_id=execution_id, step_id="step-a", request=_request())
    assert str(exc_info.value) == f"verified-dispatch-rejected:{reason}"
    assert connector.calls == []
    assert barrier.acknowledgements == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    [
        "aad_schema_version",
        "locator",
        "object_version",
        "request_material_version",
        "encryption_algorithm",
        "encryption_key_id",
        "canonicalization_version",
        "connector_identity",
        "operation_version",
        "endpoint_profile_id",
        "endpoint_profile_version",
        "execution_id",
        "step_id",
        "intent_id",
        "correlation_id",
        "created_at_ms",
        "intent_creation_not_after_ms",
        "dispatch_material_not_after_ms",
        "retention_not_after_ms",
    ],
)
async def test_altered_authenticated_metadata_has_zero_calls_and_one_historical_ack(
    redis_client, storage_adapter, lock_manager, field
):
    execution_id = await _seed(storage_adapter, lock_manager)
    connector = _RecordingConnector()
    barrier = _CountingBarrier()
    service = _binding_service(vault=_AlteredMetadataOnDispatchVault(field))
    with pytest.raises(WriteAheadWorkflowError):
        await _runner(
            redis_client, lock_manager, connector, barrier, service=service
        ).execute(execution_id=execution_id, step_id="step-a", request=_request())
    assert connector.calls == []
    assert barrier.acknowledgements == 1
    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state and state.version == 2
    intent = next(iter(state.intent_ledger.values()))
    assert intent.status is IntentStatus.ABOUT_TO_FIRE


@pytest.mark.asyncio
async def test_altered_redis_binding_is_rejected_without_post_rejection_write_or_call(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    connector = _RecordingConnector()
    barrier = _AlterBindingAfterFirstAck(execution_id)
    with pytest.raises(IntentBindingError):
        await _runner(redis_client, lock_manager, connector, barrier).execute(
            execution_id=execution_id, step_id="step-a", request=_request()
        )
    assert connector.calls == []
    assert barrier.acknowledgements == 1
    assert await redis_client.get(f"aep:state:{execution_id}") == barrier.raw_after_replacement


@pytest.mark.asyncio
@pytest.mark.parametrize("alteration", ["numeric-lexeme", "empty-array-object"])
async def test_noncanonical_binding_encoding_after_durable_creation_preserves_exact_state(
    redis_client, storage_adapter, lock_manager, alteration
):
    execution_id = await _seed(storage_adapter, lock_manager)
    connector = _RecordingConnector()
    barrier = _AlterCanonicalEncodingAfterFirstAck(execution_id, alteration)
    started = time.monotonic()
    with pytest.raises(IntentBindingError):
        await _runner(redis_client, lock_manager, connector, barrier).execute(
            execution_id=execution_id, step_id="step-a", request=_request()
        )
    elapsed_ms = (time.monotonic() - started) * 1000
    key = f"aep:state:{execution_id}"
    assert connector.calls == []
    assert barrier.acknowledgements == 1
    assert await redis_client.get(key) == barrier.raw_after_replacement
    ttl_after = await redis_client.pttl(key)
    assert ttl_after <= barrier.ttl_before_rejection
    assert ttl_after >= barrier.ttl_before_rejection - elapsed_ms - 1_000
    state = json.loads(barrier.raw_after_replacement)
    assert state["version"] == 2
    intent = next(iter(state["intent_ledger"].values()))
    assert intent["status"] == IntentStatus.ABOUT_TO_FIRE.value
    assert len(intent["transitions"]) == 1


@pytest.mark.asyncio
async def test_endpoint_profile_change_after_intent_is_rejected_without_provider_call(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    connector = _RecordingConnector()
    service = _binding_service()
    barrier = _ChangeProfileAfterFirstAck(service)
    with pytest.raises(WriteAheadWorkflowError) as exc_info:
        await _runner(
            redis_client, lock_manager, connector, barrier, service=service
        ).execute(execution_id=execution_id, step_id="step-a", request=_request())
    assert str(exc_info.value) == "verified-dispatch-rejected:request-binding-mismatch"
    assert connector.calls == []
    assert barrier.acknowledgements == 1


@pytest.mark.asyncio
async def test_connector_exception_is_single_call_and_safe_evidence(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    connector = _RecordingConnector(fail=True)
    barrier = _CountingBarrier()
    result = await _runner(
        redis_client, lock_manager, connector, barrier
    ).execute(execution_id=execution_id, step_id="step-a", request=_request())
    assert len(connector.calls) == 1
    assert barrier.acknowledgements == 2
    assert result.status is IntentStatus.FIRED_UNCONFIRMED
    assert "provider-canary-must-not-escape" not in repr(result)


@pytest.mark.asyncio
async def test_unsafe_provider_result_values_never_enter_evidence_state_or_logs(
    redis_client, storage_adapter, lock_manager, caplog
):
    execution_id = await _seed(storage_adapter, lock_manager)
    connector = _UnsafeResultConnector()
    with caplog.at_level(logging.DEBUG):
        result = await _runner(
            redis_client, lock_manager, connector, _CountingBarrier()
        ).execute(execution_id=execution_id, step_id="step-a", request=_request())
    raw = await redis_client.get(f"aep:state:{execution_id}")
    prohibited = "\n".join((raw, caplog.text, repr(result)))
    assert "TOKEN-CANARY-PROVIDER-CALL" not in prohibited
    assert "PII-CANARY-PROVIDER-REFERENCE" not in prohibited
    assert result.external_reference is None


@pytest.mark.asyncio
async def test_test_vault_cannot_authorize_production_configuration(
    redis_client, storage_adapter, lock_manager
):
    execution_id = await _seed(storage_adapter, lock_manager)
    connector = _RecordingConnector()
    barrier = _CountingBarrier()
    runner = _runner(redis_client, lock_manager, connector, barrier, allow=False)
    with pytest.raises(WriteAheadWorkflowError):
        await runner.execute(execution_id=execution_id, step_id="step-a", request=_request())
    assert connector.calls == []
    assert barrier.acknowledgements == 0


@pytest.mark.asyncio
async def test_unsafe_request_rejection_has_no_intent_call_ack_or_canary_output(
    redis_client, storage_adapter, lock_manager, caplog
):
    canary = "AUTH-CANARY-UNSAFE-PUBLIC-VALUE"
    execution_id = await _seed(storage_adapter, lock_manager)
    connector = _RecordingConnector()
    barrier = _CountingBarrier()
    request = ExactMutationRequest(
        target="account-redacted-17",
        public_fields={"action": canary, "amount_minor": 1700},
        protected_fields={},
        mutation_options={"notify": False},
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(WriteAheadWorkflowError) as exc_info:
            await _runner(redis_client, lock_manager, connector, barrier).execute(
                execution_id=execution_id, step_id="step-a", request=request
            )
    state = await redis_client.get(f"aep:state:{execution_id}")
    assert json.loads(state)["intent_ledger"] == {}
    assert connector.calls == []
    assert barrier.acknowledgements == 0
    assert canary not in state
    assert canary not in str(exc_info.value)
    assert canary not in caplog.text
    assert exc_info.value.__cause__ is None


@pytest.mark.asyncio
async def test_controlled_invalid_state_never_enters_exception_chain_log_or_quarantine(
    redis_client, storage_adapter, lock_manager, caplog
):
    canary = "PII CANARY INVALID TARGET 907"
    execution_id = await _seed(storage_adapter, lock_manager)
    await _runner(
        redis_client, lock_manager, _RecordingConnector(), _CountingBarrier()
    ).execute(execution_id=execution_id, step_id="step-a", request=_request())
    key = f"aep:state:{execution_id}"
    raw = json.loads(await redis_client.get(key))
    next(iter(raw["intent_ledger"].values()))["target"] = canary
    await redis_client.set(
        key,
        json.dumps(raw, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        keepttl=True,
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(StateCorruptionError) as exc_info:
            await IntentLedgerStore(redis_client).get_execution(execution_id)
    poison_keys = [
        item
        async for item in redis_client.scan_iter(
            match=f"aep:poison:{execution_id}:*", count=100
        )
    ]
    quarantine = "\n".join(await redis_client.mget(poison_keys))
    assert canary not in str(exc_info.value)
    assert canary not in repr(exc_info.value)
    assert canary not in caplog.text
    assert canary not in quarantine
    assert exc_info.value.__cause__ is None


@pytest.mark.asyncio
async def test_privacy_canaries_only_exist_in_authorized_vault_read(
    redis_client, storage_adapter, lock_manager, caplog
):
    canaries = {
        "authorization": "AUTH-CANARY-7ba",
        "cookie": "COOKIE-CANARY-8cb",
        "token": "TOKEN-CANARY-9dc",
        "credential": "CREDENTIAL-CANARY-aed",
        "payment_value": "PAYMENT-CANARY-bfe",
        "personal_identifier": "PII-CANARY-c0f",
    }
    execution_id = await _seed(storage_adapter, lock_manager)
    connector = _RecordingConnector()
    service = _binding_service()
    with caplog.at_level(logging.DEBUG):
        result = await _runner(
            redis_client, lock_manager, connector, _CountingBarrier(), service=service
        ).execute(
            execution_id=execution_id,
            step_id="step-a",
            request=_request(protected_fields=canaries),
        )
    raw_state = await redis_client.get(f"aep:state:{execution_id}")
    prohibited = "\n".join(
        [raw_state, caplog.text, repr(result), repr(connector.calls[0]),
         connector.calls[0].binding.model_dump_json()]
    )
    for canary in canaries.values():
        assert canary not in prohibited
        assert canary.encode() not in service.vault.test_only_backing_bytes()
    authorized = await service.vault.read_exact(
        result.request_binding.request_material_ref,
        now_ms=result.request_binding.created_at_ms + 1,
    )
    for canary in canaries.values():
        assert canary.encode() in authorized.material
