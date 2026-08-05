"""The EVALUATION composition every harness process builds.

Amendment C2: *"Every harness-driven run -- including every crash point --
executes the workflow in EVALUATION mode with no test flags."* Session 1's
report named ``experiments/mock_api/tests/test_evaluation_dispatch.py``
``_evaluation_runner`` as the composition the crash matrix should be ported to.
This is that composition, moved out of a test module so that worker processes,
the recovery process, and the tests all build the same one.

What "no test flags" means concretely, and what a test here asserts:

* ``mode=DispatchMode.EVALUATION`` -- so ``validate_startup`` takes the branch
  that shares every requirement with ``PRODUCTION``;
* neither of the two test-authorisation keywords ``WriteAheadRunner`` accepts
  is passed anywhere in this package, so both keep their ``False`` defaults --
  a property enforced by a source gate in ``tests/test_composition.py`` rather
  than by discipline, which is why they are not spelled out here;
* the barrier is ``RealWaitAofDurabilityBarrier`` -- real ``WAITAOF`` against
  real Redis 7.2 with AOF;
* the vault is ``EvaluationRedisRequestVault`` -- durable, ``test_only=False``,
  with its two declared weaknesses (shared trust domain, operator-supplied
  keys) recorded in ``docs/22-formal-model.md``;
* the connector is a real HTTP client to a MockLegacyAPI in another process.

The only respect in which this differs from ``PRODUCTION`` is the connector
endpoint, and that is enforced by ``WriteAheadRunner.validate_startup`` rather
than promised here.

**Key material.** The evaluation vault and the commitment keyring take
operator-supplied keys. They are derived deterministically from the run id so
that a run is reproducible, and they are *never* written to the run log -- only
their key ids are. They protect nothing of value: the workload carries no real
secret. That is a property of the workload, not a licence to treat this as a
production key path.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable, Mapping

from aep_core.core.connector_contract import ReconciliationCapability
from aep_core.core.durability import RealWaitAofDurabilityBarrier
from aep_core.core.intent_recovery import (
    IntentRecoveryService,
    RecoveryConnectorConfig,
)
from aep_core.core.intent_workflow import DispatchMode, WriteAheadRunner
from aep_core.core.intents import IntentLedgerStore
from aep_core.core.locks import DistributedLockManager
from aep_core.core.request_binding import CommitmentKeyring, RequestBindingService
from aep_core.core.request_vault import EvaluationRedisRequestVault
from aep_core.core.storage import AEPExecutionState, AEPStatus, RedisStorageAdapter

from experiments.harness.crash_points import CrashPoint
from experiments.harness.workload import (
    CONNECTOR_OPERATION,
    WorkloadItem,
    harness_profile,
    identity_descriptor,
    index_by_execution_id,
)
from experiments.mock_api.client import MockLegacyApiConnector
from experiments.mock_api.config import load_config

VAULT_KEY_ID = "eval-vault-key-1"
COMMITMENT_KEY_ID = "eval-commitment-key-1"

#: Every Redis key prefix this harness is responsible for creating. Used by
#: the run's own cleanup, which is scoped to the executions it created rather
#: than to the namespace -- ``aep:*`` is the namespace AEP uses in production.
RUN_KEY_PREFIXES = ("aep:state:", "aep:lock:", "aep:dispatch-auth:")


def derive_key(run_id: str, purpose: str) -> bytes:
    """32 bytes of deterministic key material for one run and one purpose."""
    return hashlib.sha256(f"aep-harness|{run_id}|{purpose}".encode("utf-8")).digest()


def endpoint_capability(config) -> ReconciliationCapability:
    """The endpoint's *declared* reconciliation capability.

    Read from the mock API's configuration file, which is where the endpoint
    declares it. This is not oracle knowledge: a real connector is likewise
    told what class of endpoint it is talking to, and ``declared_capability``
    in ``aep_core`` requires it to say so. Nothing else from that file reaches
    the connector -- in particular not ``ledger_path``.
    """
    return load_config(config.mock_api_config_path).endpoint(config.endpoint).response_class


def build_connector(
    config,
    *,
    items: Mapping[str, WorkloadItem] | None = None,
    client: Any = None,
) -> MockLegacyApiConnector:
    """The evaluation connector, optionally able to describe past mutations.

    When ``items`` is supplied the connector can answer an
    ``ORACLE_FINGERPRINT`` read-back, because it can reconstruct the identity
    of the mutation an execution made from the execution id alone. It sends
    that description on every read-back regardless of the run's keying; the
    service decides which input it consults.
    """
    resolver: Callable[[Any], Mapping[str, Any]] | None = None
    if items:
        lookup = dict(items)

        def resolve(context) -> Mapping[str, Any]:
            item = lookup.get(context.execution_id)
            if item is None:
                raise KeyError(
                    f"no workload item for execution {context.execution_id!r}; "
                    "the connector cannot describe a mutation it never made"
                )
            return identity_descriptor(item)

        resolver = resolve

    profile = harness_profile()
    return MockLegacyApiConnector(
        base_url=config.mock_api_base_url,
        endpoint=config.endpoint,
        reconciliation_capability=endpoint_capability(config),
        connector_identity=profile.connector_identity,
        connector_operation=profile.connector_operation,
        endpoint_profile_id=profile.endpoint_profile_id,
        endpoint_profile_version=profile.endpoint_profile_version,
        client=client,
        readback_identity_resolver=resolver,
    )


def build_binding_service(config, redis_client) -> RequestBindingService:
    """Durable evaluation vault plus a dedicated commitment keyring."""
    return RequestBindingService(
        profile=harness_profile(),
        commitment_keys=CommitmentKeyring(
            keys={COMMITMENT_KEY_ID: derive_key(config.run_id, "commitment")},
            active_key_id=COMMITMENT_KEY_ID,
        ),
        vault=EvaluationRedisRequestVault(
            redis_client=redis_client,
            encryption_keys={VAULT_KEY_ID: derive_key(config.run_id, "vault")},
            active_key_id=VAULT_KEY_ID,
        ),
    )


def build_runner(
    config,
    *,
    redis_client,
    lock_manager: DistributedLockManager,
    connector,
    crash_injector=None,
) -> WriteAheadRunner:
    """The runner every worker executes with. No test authorisation exists."""
    return WriteAheadRunner(
        store=IntentLedgerStore(redis_client),
        lock_manager=lock_manager,
        connector=connector,
        barrier=RealWaitAofDurabilityBarrier(),
        policy=config.policy(),
        connector_name=CONNECTOR_OPERATION,
        binding_service=build_binding_service(config, redis_client),
        crash_injector=crash_injector,
        crash_point_enum=CrashPoint if crash_injector is not None else None,
        mode=DispatchMode.EVALUATION,
    )


def build_recovery_service(
    config,
    *,
    redis_client,
    lock_manager: DistributedLockManager,
    connector,
    scan_failure_alert=None,
    recovery_lag_alert=None,
    crash_injector=None,
) -> IntentRecoveryService:
    """The recovery loop, with its scan-failure stream wired to the run log.

    ``scan_failure_alert`` is the component ``reports/phase-report-1b`` F7
    said nothing in the repository consumed. Amendment C4 makes consuming it a
    requirement, and the runner measures the latency between poisoning an
    execution and this callback firing.
    """
    return IntentRecoveryService(
        store=IntentLedgerStore(redis_client),
        lock_manager=lock_manager,
        connectors={
            CONNECTOR_OPERATION: RecoveryConnectorConfig(
                connector=connector,
                barrier=RealWaitAofDurabilityBarrier(),
                policy=config.policy(),
            )
        },
        crash_injector=crash_injector,
        crash_point_enum=CrashPoint if crash_injector is not None else None,
        scan_failure_alert=scan_failure_alert,
        recovery_lag_alert=recovery_lag_alert,
    )


async def seed_execution_state(
    *, storage_adapter: RedisStorageAdapter, lock_manager, execution_id: str
) -> None:
    """Create the execution state the write-ahead workflow requires to exist."""
    token = await lock_manager.acquire_lock(execution_id, ttl_seconds=60)
    if token is None:
        raise RuntimeError(f"could not seed execution {execution_id}: lease unavailable")
    try:
        await storage_adapter.save_state(
            AEPExecutionState(execution_id=execution_id, status=AEPStatus.IDLE),
            expected_version=0,
            lock_token=token,
            ttl_seconds=3600,
        )
    finally:
        await lock_manager.release_lock(execution_id, token)


async def delete_run_keys(redis_client, execution_ids) -> int:
    """Remove the keys one run created, and only those.

    Scoped to this run's execution identifiers rather than to ``aep:*``:
    ``aep:*`` is precisely the namespace AEP uses in production, so a
    namespace-wide sweep in a harness that a mis-pointed ``REDIS_URL`` could
    reach is the failure ``tests/conftest.py``'s marker guard exists to
    prevent. Vault objects are keyed by an opaque locator and are left to
    their own expiry.
    """
    keys: list[str] = []
    for execution_id in execution_ids:
        keys.append(f"aep:state:{execution_id}")
        keys.append(f"aep:lock:{execution_id}")
        for pattern in (
            f"aep:dispatch-auth:{execution_id}:*",
            # A quarantined payload is never removed by the protocol, so a
            # poisoned execution is re-isolated on every subsequent scan pass
            # and leaves one quarantine record per pass. Correct behaviour --
            # an operator is meant to find them -- but the harness created
            # them, so the harness removes them.
            f"aep:poison:{execution_id}:*",
        ):
            async for key in redis_client.scan_iter(match=pattern, count=100):
                keys.append(key if isinstance(key, str) else key.decode())
    removed = 0
    for start in range(0, len(keys), 500):
        batch = keys[start : start + 500]
        if batch:
            removed += int(await redis_client.unlink(*batch))
    return removed
