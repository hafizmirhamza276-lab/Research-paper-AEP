"""Phase 1B regression tests: measurement composition is explicit, not silent.

Before Phase 1B the only composition that could dispatch at all required
``allow_test_dispatch`` plus a ``test_only`` vault and a ``test_only``
connector, so any evaluation would have silently measured a test rig.

Phase 1B introduces an explicit :class:`DispatchMode`.  ``EVALUATION`` differs
from ``PRODUCTION`` in exactly one respect — the connector endpoint is a
declared evaluation endpoint — and that restriction is enforced in code:
the durability barrier and the request vault must both be production-grade.
"""

from __future__ import annotations

import os
import uuid

import pytest

from aep_core.core.durability import (
    FakeDurabilityBarrier,
    RealWaitAofDurabilityBarrier,
)
from aep_core.core.intent_workflow import (
    ConnectorPolicy,
    DispatchMode,
    WriteAheadRunner,
    WriteAheadWorkflowError,
)
from aep_core.core.intents import IntentLedgerStore
from aep_core.core.request_vault import (
    EvaluationRedisRequestVault,
    VaultAuthenticationError,
    VaultCollisionError,
    VaultConfigurationError,
    VaultExpiredError,
    VaultMissingError,
    VaultObjectMetadata,
)
from tests.mock_connector import MockConnectorHarness
from tests.request_binding_helpers import (
    DEFAULT_CONNECTOR,
    test_binding_service as _binding_service,
)

INTEGRATION = os.environ.get("AEP_PHASE2_REDIS_INTEGRATION") == "1"


class _EvaluationConnector:
    """A mock endpoint that is explicitly declared as an evaluation endpoint."""

    test_only = False
    evaluation_endpoint = True
    connector_identity = "mock-connector"
    connector_operation = DEFAULT_CONNECTOR
    endpoint_profile_id = "mock-endpoint"
    endpoint_profile_version = "1"

    async def mutate(self, *, dispatch, client_timeout):  # pragma: no cover
        raise AssertionError("not dispatched in this test")


class _UndeclaredConnector(_EvaluationConnector):
    evaluation_endpoint = False


def _policy():
    return ConnectorPolicy(
        client_timeout_seconds=0.01,
        settlement_lag_seconds=0,
        buffer_margin_seconds=15,
        lock_ttl_seconds=30,
        durability_timeout_ms=2_000,
        lease_acquire_attempts=1,
    )


def _runner(redis_client, lock_manager, *, mode, connector, barrier, vault, **kwargs):
    return WriteAheadRunner(
        store=IntentLedgerStore(redis_client),
        lock_manager=lock_manager,
        connector=connector,
        barrier=barrier,
        policy=_policy(),
        connector_name=DEFAULT_CONNECTOR,
        binding_service=_binding_service(vault=vault),
        mode=mode,
        **kwargs,
    )


def _evaluation_vault(redis_client):
    return EvaluationRedisRequestVault(
        redis_client=redis_client,
        encryption_keys={"eval-vault-key-1": b"e" * 32},
        active_key_id="eval-vault-key-1",
    )


# ---------------------------------------------------------------------------
# Mode gating
# ---------------------------------------------------------------------------


def test_dispatch_mode_default_is_production(redis_client, lock_manager):
    runner = _runner(
        redis_client,
        lock_manager,
        mode=DispatchMode.PRODUCTION,
        connector=_EvaluationConnector(),
        barrier=RealWaitAofDurabilityBarrier(),
        vault=_evaluation_vault(redis_client),
    )
    assert runner.mode is DispatchMode.PRODUCTION
    # And omitting mode entirely selects PRODUCTION, never TEST.
    other = WriteAheadRunner(
        store=IntentLedgerStore(redis_client),
        lock_manager=lock_manager,
        connector=_EvaluationConnector(),
        barrier=RealWaitAofDurabilityBarrier(),
        policy=_policy(),
        connector_name=DEFAULT_CONNECTOR,
        binding_service=_binding_service(vault=_evaluation_vault(redis_client)),
    )
    assert other.mode is DispatchMode.PRODUCTION


@pytest.mark.asyncio
async def test_production_mode_rejects_a_test_only_vault(
    redis_client, lock_manager
):
    from aep_core.core.request_vault import TestOnlyInMemoryRequestVault

    vault = TestOnlyInMemoryRequestVault(
        encryption_keys={"k": b"v" * 32},
        active_key_id="k",
        test_only_acknowledgement=True,
    )
    runner = _runner(
        redis_client,
        lock_manager,
        mode=DispatchMode.PRODUCTION,
        connector=_EvaluationConnector(),
        barrier=RealWaitAofDurabilityBarrier(),
        vault=vault,
    )
    with pytest.raises(WriteAheadWorkflowError, match="vault"):
        await runner.validate_startup()


@pytest.mark.asyncio
async def test_production_mode_rejects_an_evaluation_connector(
    redis_client, lock_manager
):
    runner = _runner(
        redis_client,
        lock_manager,
        mode=DispatchMode.PRODUCTION,
        connector=_EvaluationConnector(),
        barrier=RealWaitAofDurabilityBarrier(),
        vault=_evaluation_vault(redis_client),
    )
    with pytest.raises(WriteAheadWorkflowError, match="evaluation"):
        await runner.validate_startup()


@pytest.mark.asyncio
async def test_evaluation_mode_rejects_a_test_only_vault(
    redis_client, lock_manager
):
    from aep_core.core.request_vault import TestOnlyInMemoryRequestVault

    vault = TestOnlyInMemoryRequestVault(
        encryption_keys={"k": b"v" * 32},
        active_key_id="k",
        test_only_acknowledgement=True,
    )
    runner = _runner(
        redis_client,
        lock_manager,
        mode=DispatchMode.EVALUATION,
        connector=_EvaluationConnector(),
        barrier=RealWaitAofDurabilityBarrier(),
        vault=vault,
    )
    with pytest.raises(WriteAheadWorkflowError, match="vault"):
        await runner.validate_startup()


@pytest.mark.asyncio
async def test_evaluation_mode_rejects_a_test_only_barrier(
    redis_client, lock_manager
):
    runner = _runner(
        redis_client,
        lock_manager,
        mode=DispatchMode.EVALUATION,
        connector=_EvaluationConnector(),
        barrier=FakeDurabilityBarrier(),
        vault=_evaluation_vault(redis_client),
        allow_test_barrier=True,
    )
    with pytest.raises(WriteAheadWorkflowError, match="barrier"):
        await runner.validate_startup()


@pytest.mark.asyncio
async def test_evaluation_mode_rejects_an_undeclared_connector(
    redis_client, lock_manager
):
    runner = _runner(
        redis_client,
        lock_manager,
        mode=DispatchMode.EVALUATION,
        connector=_UndeclaredConnector(),
        barrier=RealWaitAofDurabilityBarrier(),
        vault=_evaluation_vault(redis_client),
    )
    with pytest.raises(WriteAheadWorkflowError, match="evaluation endpoint"):
        await runner.validate_startup()


@pytest.mark.asyncio
async def test_evaluation_mode_rejects_a_test_only_connector(
    redis_client, lock_manager
):
    harness = MockConnectorHarness()
    runner = _runner(
        redis_client,
        lock_manager,
        mode=DispatchMode.EVALUATION,
        connector=harness.connector,
        barrier=RealWaitAofDurabilityBarrier(),
        vault=_evaluation_vault(redis_client),
    )
    with pytest.raises(WriteAheadWorkflowError):
        await runner.validate_startup()


@pytest.mark.skipif(
    not INTEGRATION,
    reason="set AEP_PHASE2_REDIS_INTEGRATION=1 and REDIS_URL to Redis 7.2+ AOF",
)
@pytest.mark.redis72_integration
@pytest.mark.asyncio
async def test_evaluation_mode_startup_passes_without_any_test_flag(
    redis_client, lock_manager
):
    """The Phase 1B acceptance condition for the harness composition."""

    runner = _runner(
        redis_client,
        lock_manager,
        mode=DispatchMode.EVALUATION,
        connector=_EvaluationConnector(),
        barrier=RealWaitAofDurabilityBarrier(),
        vault=_evaluation_vault(redis_client),
    )
    assert runner.allow_test_dispatch is False
    assert runner.allow_test_barrier is False
    await runner.validate_startup()


# ---------------------------------------------------------------------------
# The evaluation vault
# ---------------------------------------------------------------------------


def _metadata(locator: str, *, now_ms: int = 1_800_000_000_000, length: int = 11):
    return VaultObjectMetadata(
        locator=locator,
        object_version=1,
        request_material_version=1,
        encryption_key_id="eval-vault-key-1",
        envelope_schema="aep.mutation-request/1",
        canonicalization_version="aep.canonical-json/1",
        descriptor_version="aep.safe-request/1",
        connector_identity="mock-connector",
        connector_operation=DEFAULT_CONNECTOR,
        operation_version="1",
        endpoint_profile_id="mock-endpoint",
        endpoint_profile_version="1",
        credential_binding_id="mock-credential",
        credential_binding_version="1",
        wire_codec_version="mock-wire/1",
        commitment_algorithm="HMAC-SHA-256",
        commitment_key_id="eval-commitment-key-1",
        execution_id=str(uuid.uuid4()),
        step_id="step-a",
        intent_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        created_at_ms=now_ms,
        intent_creation_not_after_ms=now_ms + 10_000,
        dispatch_material_not_after_ms=now_ms + 30_000,
        retention_not_after_ms=now_ms + 3_600_000,
        material_length=length,
    )


def test_evaluation_vault_is_not_test_only(redis_client):
    vault = _evaluation_vault(redis_client)
    assert vault.test_only is False
    assert vault.evaluation_only is True


def test_evaluation_vault_requires_valid_keys(redis_client):
    with pytest.raises(VaultConfigurationError):
        EvaluationRedisRequestVault(
            redis_client=redis_client,
            encryption_keys={"short": b"too-short"},
            active_key_id="short",
        )
    with pytest.raises(VaultConfigurationError):
        EvaluationRedisRequestVault(
            redis_client=redis_client,
            encryption_keys={"k1": b"e" * 32},
            active_key_id="absent",
        )


@pytest.mark.asyncio
async def test_evaluation_vault_roundtrips_exactly(redis_client):
    vault = _evaluation_vault(redis_client)
    locator = "vault_" + "a" * 30
    material = b"hello world"
    metadata = _metadata(locator, length=len(material))
    await vault.create_once(material, metadata)

    read = await vault.read_exact(locator, now_ms=metadata.created_at_ms + 1)
    assert read.material == material
    assert read.metadata == metadata


@pytest.mark.asyncio
async def test_evaluation_vault_is_create_once(redis_client):
    vault = _evaluation_vault(redis_client)
    locator = "vault_" + "b" * 30
    material = b"hello world"
    metadata = _metadata(locator, length=len(material))
    await vault.create_once(material, metadata)
    with pytest.raises(VaultCollisionError):
        await vault.create_once(material, metadata)


@pytest.mark.asyncio
async def test_evaluation_vault_has_no_update_path(redis_client):
    from aep_core.core.request_vault import VaultUpdateForbiddenError

    vault = _evaluation_vault(redis_client)
    with pytest.raises(VaultUpdateForbiddenError):
        await vault.update("vault_" + "c" * 30, b"x")


@pytest.mark.asyncio
async def test_evaluation_vault_rejects_missing_and_expired(redis_client):
    vault = _evaluation_vault(redis_client)
    with pytest.raises(VaultMissingError):
        await vault.read_exact("vault_" + "d" * 30, now_ms=1)

    locator = "vault_" + "e" * 30
    material = b"hello world"
    metadata = _metadata(locator, length=len(material))
    await vault.create_once(material, metadata)
    with pytest.raises(VaultExpiredError):
        await vault.read_exact(
            locator, now_ms=metadata.dispatch_material_not_after_ms
        )


@pytest.mark.asyncio
async def test_evaluation_vault_detects_ciphertext_tampering(redis_client):
    vault = _evaluation_vault(redis_client)
    locator = "vault_" + "f" * 30
    material = b"hello world"
    metadata = _metadata(locator, length=len(material))
    await vault.create_once(material, metadata)

    import json

    key = vault.object_key(locator)
    stored = json.loads(await redis_client.get(key))
    ciphertext = bytearray(
        __import__("base64").urlsafe_b64decode(stored["ciphertext"])
    )
    ciphertext[0] ^= 1
    stored["ciphertext"] = (
        __import__("base64").urlsafe_b64encode(bytes(ciphertext)).decode("ascii")
    )
    await redis_client.set(key, json.dumps(stored), keepttl=True)

    with pytest.raises(VaultAuthenticationError):
        await vault.read_exact(locator, now_ms=metadata.created_at_ms + 1)


@pytest.mark.asyncio
async def test_evaluation_vault_detects_metadata_tampering(redis_client):
    vault = _evaluation_vault(redis_client)
    locator = "vault_" + "g" * 30
    material = b"hello world"
    metadata = _metadata(locator, length=len(material))
    await vault.create_once(material, metadata)

    import json

    key = vault.object_key(locator)
    stored = json.loads(await redis_client.get(key))
    tampered = dict(stored["metadata"])
    tampered["step_id"] = "step-b"
    stored["metadata"] = tampered
    await redis_client.set(key, json.dumps(stored), keepttl=True)

    with pytest.raises(VaultAuthenticationError):
        await vault.read_exact(locator, now_ms=metadata.created_at_ms + 1)


@pytest.mark.asyncio
async def test_evaluation_vault_rejects_a_transplanted_record(redis_client):
    vault = _evaluation_vault(redis_client)
    source = "vault_" + "h" * 30
    target = "vault_" + "i" * 30
    material = b"hello world"
    metadata = _metadata(source, length=len(material))
    await vault.create_once(material, metadata)

    raw = await redis_client.get(vault.object_key(source))
    await redis_client.set(vault.object_key(target), raw, ex=3600)

    with pytest.raises(VaultAuthenticationError):
        await vault.read_exact(target, now_ms=metadata.created_at_ms + 1)
