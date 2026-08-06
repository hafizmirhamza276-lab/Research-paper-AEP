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

from experiments.baselines import (
    b0_naive_retry,
    b1_lease_only,
    b2_cas_only,
    b4_durable_workflow,
)
from experiments.baselines.b3_no_barrier import NoBarrierDurabilityBarrier
from experiments.baselines.contract import SystemId
from experiments.baselines.crash_points import BaselineCrashPoint
from experiments.baselines.intent_classifier import NO_INTENT, classify_intent_state
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


def build_barrier(config):
    """The durability barrier the run's system declares it has.

    B3 is the *only* system that gets a different one, and what it gets is the
    ablated barrier from ``experiments/baselines/b3_no_barrier.py`` -- same
    startup validation, no per-dispatch ``WAITAOF``. Selecting it from the
    descriptor rather than from a flag means "B3 has no barrier" is read from
    the same table the paper prints.
    """
    if not config.descriptor.uses_durability_barrier:
        return NoBarrierDurabilityBarrier()
    return RealWaitAofDurabilityBarrier()


def build_runner(
    config,
    *,
    redis_client,
    lock_manager: DistributedLockManager,
    connector,
    crash_injector=None,
) -> WriteAheadRunner:
    """The runner AEP-full and B3 execute with. No test authorisation exists."""
    return WriteAheadRunner(
        store=IntentLedgerStore(redis_client),
        lock_manager=lock_manager,
        connector=connector,
        barrier=build_barrier(config),
        policy=config.policy(),
        connector_name=CONNECTOR_OPERATION,
        binding_service=build_binding_service(config, redis_client),
        crash_injector=crash_injector,
        crash_point_enum=CrashPoint if crash_injector is not None else None,
        mode=DispatchMode.EVALUATION,
    )


class _IntentSystemAdapter:
    """Present ``WriteAheadRunner`` through the baselines' outcome vocabulary.

    AEP-full and B3 return an ``IntentRecord``; the baselines return an
    ``ExecutionOutcome``. The worker should not have to know which, so the two
    protocol systems are wrapped rather than the four baselines being made to
    imitate an intent ledger they do not have.
    """

    def __init__(self, runner: WriteAheadRunner, system: SystemId) -> None:
        self.runner = runner
        self.system = system

    @property
    def mode(self):
        return self.runner.mode

    @property
    def barrier(self):
        return self.runner.barrier

    @property
    def binding_service(self):
        return self.runner.binding_service

    async def validate_startup(self) -> None:
        await self.runner.validate_startup()

    async def execute(self, *, execution_id: str, step_id: str, request):
        resolved = await self.runner.execute(
            execution_id=execution_id, step_id=step_id, request=request
        )
        return classify_intent_state(
            resolved.status.value,
            system=self.system,
            execution_id=execution_id,
            # One transmission per intent, by construction. It is asserted by
            # the ledger cross-check rather than counted here: this number is
            # what the protocol *claims*, and the oracle is what checks it.
            dispatch_attempts=1,
            intent_id=resolved.intent_id,
        )


def build_system(
    config,
    *,
    redis_client,
    lock_manager: DistributedLockManager,
    connector,
    crash_injector=None,
):
    """The runner for whichever of the six systems this run measures."""
    system = config.system
    if system in (SystemId.AEP_FULL, SystemId.B3_INTENT_NO_BARRIER):
        return _IntentSystemAdapter(
            build_runner(
                config,
                redis_client=redis_client,
                lock_manager=lock_manager,
                connector=connector,
                crash_injector=crash_injector,
            ),
            system,
        )

    shared = {
        "redis_client": redis_client,
        "connector": connector,
        "profile": harness_profile(),
        "policy": config.policy(),
        "max_attempts": config.max_dispatch_attempts,
        "crash_injector": crash_injector,
        "crash_point_enum": (
            BaselineCrashPoint if crash_injector is not None else None
        ),
    }
    if system is SystemId.B0_NAIVE_RETRY:
        return b0_naive_retry.NaiveRetryRunner(**shared)
    if system is SystemId.B1_LEASE_ONLY:
        return b1_lease_only.LeaseOnlyRunner(lock_manager=lock_manager, **shared)
    if system is SystemId.B2_CAS_ONLY:
        return b2_cas_only.CasOnlyRunner(
            lock_manager=lock_manager,
            storage_adapter=RedisStorageAdapter(redis_client),
            **shared,
        )
    if system is SystemId.B4_DURABLE_WORKFLOW:
        return b4_durable_workflow.DurableWorkflowRunner(
            lock_manager=lock_manager,
            barrier=RealWaitAofDurabilityBarrier(),
            **shared,
        )
    raise KeyError(f"no runner is registered for {system}")


async def classify_execution(config, redis_client, execution_id: str):
    """What the run's system says about one execution, after everything.

    Read from whichever durable record that system keeps -- the intent ledger,
    a raw key, a fenced state, an event history -- and returned in the shared
    vocabulary the metrics use. This is the *only* place the harness looks at
    a system's internal state, and it never looks at the ground-truth ledger:
    keeping those two readers apart is what makes the reconciliation a check
    rather than a restatement.
    """
    system = config.system
    if system in (SystemId.AEP_FULL, SystemId.B3_INTENT_NO_BARRIER):
        store = IntentLedgerStore(redis_client)
        try:
            state = await store.get_execution(execution_id)
        except Exception as error:  # noqa: BLE001 -- a corrupt state is a result
            return classify_intent_state(
                f"UNREADABLE:{type(error).__name__}",
                system=system,
                execution_id=execution_id,
            )
        if state is None or not state.intent_ledger:
            return classify_intent_state(
                NO_INTENT, system=system, execution_id=execution_id
            )
        intent = sorted(
            state.intent_ledger.values(), key=lambda item: item.prepared_at
        )[-1]
        return classify_intent_state(
            intent.status.value,
            system=system,
            execution_id=execution_id,
            intent_id=intent.intent_id,
        )

    classifier = {
        SystemId.B0_NAIVE_RETRY: b0_naive_retry.classify,
        SystemId.B1_LEASE_ONLY: b1_lease_only.classify,
        SystemId.B2_CAS_ONLY: b2_cas_only.classify,
        SystemId.B4_DURABLE_WORKFLOW: b4_durable_workflow.classify,
    }[system]
    return await classifier(redis_client, execution_id)


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
        # The baselines keep their records outside the protocol's namespace,
        # so the run has to name them here or a matrix would accumulate one
        # key per execution per cell for the whole of its retention.
        keys.append(f"aep:b0:result:{execution_id}")
        keys.append(f"aep:b1:state:{execution_id}")
        keys.append(f"aep:b4:history:{execution_id}")
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
