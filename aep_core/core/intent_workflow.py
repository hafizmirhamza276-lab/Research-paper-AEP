"""Phase 2 write-ahead execution workflow for one non-idempotent call."""

from __future__ import annotations

import asyncio
import math
import random
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from aep_core.core.durability import (
    DurabilityAck,
    DurabilityBarrier,
    confirm_durable_ack,
    dispatch_scope,
)
from aep_core.core.exceptions import LockAcquisitionError
from aep_core.core.intents import (
    IntentBindingError,
    IntentLedgerStore,
    IntentPreflightError,
    IntentRecord,
    IntentStateError,
    IntentStatus,
)
from aep_core.core.locks import DistributedLockManager
from aep_core.core.request_binding import (
    ExactMutationRequest,
    RequestBindingError,
    RequestBindingService,
    VerifiedDispatch,
    canonical_request_binding_bytes,
)
from aep_core.core.request_vault import RequestVaultError


class DispatchMode(str, Enum):
    """Which composition a runner is permitted to dispatch under.

    The default is ``PRODUCTION``: a runner never silently degrades to a test
    composition.  ``EVALUATION`` exists so an experiment states plainly what it
    measured; it differs from ``PRODUCTION`` in exactly one respect — the
    connector is a declared evaluation endpoint — and every other component
    must still be production-grade (see :meth:`WriteAheadRunner.validate_startup`).
    """

    PRODUCTION = "PRODUCTION"
    EVALUATION = "EVALUATION"
    TEST = "TEST"


class ExternalMutationConnector(Protocol):
    connector_identity: str
    connector_operation: str
    endpoint_profile_id: str
    endpoint_profile_version: str

    async def mutate(
        self, *, dispatch: VerifiedDispatch, client_timeout: float
    ) -> Any: ...


class CrashInjectorProtocol(Protocol):
    async def checkpoint(self, point: Any) -> None: ...


@dataclass(frozen=True)
class ConnectorPolicy:
    """Per-connector timing and bounded reconciliation policy."""

    client_timeout_seconds: float
    settlement_lag_seconds: float = 0.0
    buffer_margin_seconds: float = 15.0
    lock_ttl_seconds: int = 60
    durability_timeout_ms: int = 1_000
    max_reconciliation_attempts: int = 8
    max_reconciliation_duration_seconds: float = 24 * 60 * 60
    backoff_base_seconds: float = 5.0
    backoff_cap_seconds: float = 300.0
    lease_acquire_attempts: int = 3
    lease_backoff_cap_seconds: float = 1.0
    definitive_success_evidence: frozenset[str] = frozenset(
        {"DEFINITIVE_SUCCESS"}
    )
    definitive_failure_evidence: frozenset[str] = frozenset(
        {"DEFINITIVE_FAILURE"}
    )

    def __post_init__(self) -> None:
        if self.client_timeout_seconds <= 0:
            raise ValueError("client_timeout_seconds must be positive")
        if self.settlement_lag_seconds < 0:
            raise ValueError("settlement_lag_seconds cannot be negative")
        if self.buffer_margin_seconds < 15:
            raise ValueError("buffer_margin_seconds must be at least 15")
        if (
            self.client_timeout_seconds
            > self.lock_ttl_seconds - self.buffer_margin_seconds
        ):
            raise ValueError(
                "T_client must be <= T_lock - Buffer_Margin"
            )
        if self.durability_timeout_ms <= 0:
            raise ValueError("durability_timeout_ms must be positive")
        if self.max_reconciliation_attempts <= 0:
            raise ValueError("max_reconciliation_attempts must be positive")
        if self.max_reconciliation_duration_seconds <= 0:
            raise ValueError(
                "max_reconciliation_duration_seconds must be positive"
            )
        if self.backoff_base_seconds < 0 or self.backoff_cap_seconds < 0:
            raise ValueError("reconciliation backoff values cannot be negative")
        if self.lease_acquire_attempts <= 0:
            raise ValueError("lease_acquire_attempts must be positive")
        if self.lease_backoff_cap_seconds < 0:
            raise ValueError("lease_backoff_cap_seconds cannot be negative")
        if not self.definitive_success_evidence:
            raise ValueError("connector must declare definitive success evidence")
        if not self.definitive_failure_evidence:
            raise ValueError("connector must declare definitive failure evidence")
        if self.definitive_success_evidence & self.definitive_failure_evidence:
            raise ValueError("success and failure evidence declarations overlap")

    def backoff_ceiling(self, attempt_number: int) -> float:
        if attempt_number < 1:
            raise ValueError("attempt_number must be positive")
        return min(
            self.backoff_base_seconds * (2 ** (attempt_number - 1)),
            self.backoff_cap_seconds,
        )


class WriteAheadWorkflowError(IntentStateError):
    """The workflow stopped safely before producing a durable resolution."""


class WriteAheadRunner:
    """Lease, write intent, confirm durability, preflight, dispatch once."""

    def __init__(
        self,
        *,
        store: IntentLedgerStore,
        lock_manager: DistributedLockManager,
        connector: ExternalMutationConnector,
        barrier: DurabilityBarrier,
        policy: ConnectorPolicy,
        connector_name: str,
        binding_service: RequestBindingService,
        crash_injector: CrashInjectorProtocol | None = None,
        crash_point_enum: type[Any] | None = None,
        random_source: random.Random | None = None,
        mode: DispatchMode | None = None,
        allow_test_barrier: bool = False,
        allow_test_dispatch: bool = False,
    ) -> None:
        # An unspecified mode is PRODUCTION.  A caller that opted into
        # test dispatch without naming a mode is in TEST mode by that act;
        # no composition ever silently degrades.
        if mode is None:
            mode = (
                DispatchMode.TEST if allow_test_dispatch else DispatchMode.PRODUCTION
            )
        self.mode = DispatchMode(mode)
        self.store = store
        self.lock_manager = lock_manager
        self.connector = connector
        self.barrier = barrier
        self.policy = policy
        self.connector_name = connector_name
        self.binding_service = binding_service
        self.crash_injector = crash_injector
        self.crash_point_enum = crash_point_enum
        self.random = random_source or random.Random()
        self.allow_test_barrier = allow_test_barrier
        self.allow_test_dispatch = allow_test_dispatch
        if binding_service.profile.connector_operation != connector_name:
            raise ValueError("request profile connector operation must match runner")
        connector_profile = (
            getattr(connector, "connector_identity", None),
            getattr(connector, "connector_operation", None),
            getattr(connector, "endpoint_profile_id", None),
            getattr(connector, "endpoint_profile_version", None),
        )
        expected_connector_profile = (
            binding_service.profile.connector_identity,
            binding_service.profile.connector_operation,
            binding_service.profile.endpoint_profile_id,
            binding_service.profile.endpoint_profile_version,
        )
        if connector_profile != expected_connector_profile:
            raise ValueError("connector identity/profile must match request profile")
        required_retention = math.ceil(
            policy.max_reconciliation_duration_seconds
        ) + 7 * 24 * 60 * 60
        if store.unresolved_ttl_seconds < required_retention:
            raise ValueError(
                "intent TTL must cover max reconciliation duration plus "
                "the 7-day operator retention period"
            )

    async def _checkpoint(self, name: str) -> None:
        if self.crash_injector is not None:
            if self.crash_point_enum is None:
                raise RuntimeError(
                    "crash_point_enum is required when a crash injector is supplied"
                )
            await self.crash_injector.checkpoint(self.crash_point_enum[name])

    async def _validate_real_barrier(self) -> None:
        validator = getattr(self.barrier, "validate_startup", None)
        if not callable(validator):
            raise WriteAheadWorkflowError(
                "production durability barrier lacks startup validation"
            )
        try:
            await validator(self.store.redis)
        except Exception as exc:
            raise WriteAheadWorkflowError(
                "durability startup validation failed: "
                f"{type(exc).__name__}"
            ) from None

    async def validate_startup(self) -> None:
        """Validate the composition and durability before non-idempotent work.

        The three modes are mutually exclusive and each is checked explicitly:

        * ``TEST`` — the historical composition.  Requires the explicit
          ``allow_test_dispatch`` opt-in plus a test-only vault and connector.
        * ``EVALUATION`` — production-grade durability barrier and a durable,
          non-test request vault; the *only* permitted difference from
          production is that the connector declares itself an evaluation
          endpoint.
        * ``PRODUCTION`` — as EVALUATION, but the connector must not be an
          evaluation endpoint and the vault must not be the evaluation vault.
          This repository ships no production vault or connector, so this mode
          fails closed until one exists.
        """

        vault = self.binding_service.vault
        vault_is_test = bool(getattr(vault, "test_only", False))
        vault_is_evaluation = bool(getattr(vault, "evaluation_only", False))
        connector_is_test = bool(getattr(self.connector, "test_only", False))
        connector_is_evaluation = bool(
            getattr(self.connector, "evaluation_endpoint", False)
        )
        barrier_is_test = bool(getattr(self.barrier, "test_only", False))
        mode_name = self.mode.value.lower()

        if self.mode is DispatchMode.TEST:
            if not self.allow_test_dispatch:
                raise WriteAheadWorkflowError(
                    "test dispatch requires the explicit test authorization"
                )
            if not vault_is_test:
                raise WriteAheadWorkflowError(
                    "test dispatch requires the explicit test-only request vault"
                )
            if not connector_is_test:
                raise WriteAheadWorkflowError(
                    "test dispatch requires an explicit test-only connector"
                )
            if barrier_is_test:
                if not self.allow_test_barrier:
                    raise WriteAheadWorkflowError(
                        "test-only durability barrier requires explicit test "
                        "authorization"
                    )
                return
            await self._validate_real_barrier()
            return

        # PRODUCTION and EVALUATION share every requirement below.  Keeping
        # them in one block is what makes "differs only in the connector
        # endpoint" a property of the code rather than a claim in prose.
        if vault_is_test:
            raise WriteAheadWorkflowError(
                f"{mode_name} dispatch requires a non-test request vault"
            )
        if barrier_is_test:
            raise WriteAheadWorkflowError(
                f"{mode_name} dispatch requires the production durability barrier"
            )
        if connector_is_test:
            raise WriteAheadWorkflowError(
                f"{mode_name} dispatch refuses a test-only connector"
            )

        if self.mode is DispatchMode.PRODUCTION:
            if connector_is_evaluation:
                raise WriteAheadWorkflowError(
                    "production dispatch refuses an evaluation-endpoint connector"
                )
            if vault_is_evaluation:
                raise WriteAheadWorkflowError(
                    "production dispatch requires a production request vault, "
                    "not the evaluation vault"
                )
        else:
            if not connector_is_evaluation:
                raise WriteAheadWorkflowError(
                    "evaluation dispatch requires a connector that declares an "
                    "evaluation endpoint"
                )

        await self._validate_real_barrier()

    async def _acquire_with_jitter(self, execution_id: str) -> str:
        for attempt in range(1, self.policy.lease_acquire_attempts + 1):
            token = await self.lock_manager.acquire_lock(
                execution_id, ttl_seconds=self.policy.lock_ttl_seconds
            )
            if token is not None:
                return token
            if attempt < self.policy.lease_acquire_attempts:
                ceiling = min(
                    0.05 * (2 ** (attempt - 1)),
                    self.policy.lease_backoff_cap_seconds,
                )
                await asyncio.sleep(self.random.uniform(0, ceiling))
        raise LockAcquisitionError(
            f"execution lease remained unavailable for {execution_id}"
        )

    async def _confirm_barrier(self, connection: Any) -> None:
        try:
            durable = await self.barrier.confirm_durable(
                connection, self.policy.durability_timeout_ms
            )
        except NotImplementedError:
            raise
        except Exception as exc:
            raise WriteAheadWorkflowError(
                f"durability barrier failed: {type(exc).__name__}"
            ) from None
        if not durable:
            raise WriteAheadWorkflowError(
                "durability barrier did not acknowledge the preceding write"
            )

    async def _confirm_dispatch_barrier(
        self, connection: Any, *, scope: str
    ) -> DurabilityAck:
        """Barrier the write-ahead intent and mint the dispatch-authorising ack."""

        try:
            return await confirm_durable_ack(
                self.barrier,
                connection,
                self.policy.durability_timeout_ms,
                scope=scope,
            )
        except NotImplementedError:
            raise
        except Exception as exc:
            raise WriteAheadWorkflowError(
                f"durability barrier failed: {type(exc).__name__}"
            ) from None

    async def execute(
        self,
        *,
        execution_id: str,
        step_id: str,
        request: ExactMutationRequest,
        actor: str = "runner",
    ) -> IntentRecord:
        """Perform exactly one dispatch and return its durably written outcome."""

        await self.validate_startup()
        await self._checkpoint("BEFORE_LEASE_ACQUISITION")
        token = await self._acquire_with_jitter(execution_id)
        intent: IntentRecord | None = None
        try:
            await self._checkpoint(
                "AFTER_LEASE_ACQUISITION_BEFORE_INTENT_CAS"
            )
            current = await self.store.get_execution(execution_id)
            if current is None:
                raise WriteAheadWorkflowError(
                    "execution state must exist before non-idempotent dispatch"
                )

            intent_id = str(uuid.uuid4())
            correlation_id = str(uuid.uuid4())
            created_at_ms = int((await self.store.redis_time()) * 1000)
            dispatch_window_ms = int(
                (
                    self.policy.client_timeout_seconds
                    + self.policy.buffer_margin_seconds
                )
                * 1000
            )
            # The lease TTL floor the preflight enforces, and the lifetime of
            # the dispatch authorization: both are exactly one dispatch window.
            required_ttl_ms = dispatch_window_ms
            try:
                prepared = await self.binding_service.prepare(
                    execution_id=execution_id,
                    step_id=step_id,
                    intent_id=intent_id,
                    correlation_id=correlation_id,
                    request=request,
                    created_at_ms=created_at_ms,
                    intent_creation_not_after_ms=created_at_ms + 5_000,
                    dispatch_material_not_after_ms=(
                        created_at_ms + max(dispatch_window_ms, 5_001)
                    ),
                    retention_not_after_ms=(
                        created_at_ms
                        + self.store.unresolved_ttl_seconds * 1000
                        + 60_000
                    ),
                )
            except (RequestBindingError, RequestVaultError) as exc:
                raise WriteAheadWorkflowError(
                    f"request-preparation-rejected:{exc}"
                ) from None

            await self._checkpoint("DURING_INTENT_CAS")
            async with self.store.pinned_connection() as connection:
                intent = await self.store.create_intent(
                    execution_id=execution_id,
                    expected_version=current.version,
                    lock_token=token,
                    step_id=step_id,
                    connector=self.connector_name,
                    target=prepared.binding.safe_descriptor.redacted_target,
                    request_fingerprint=prepared.binding.request_fingerprint,
                    request_binding=prepared.binding,
                    client_timeout_seconds=self.policy.client_timeout_seconds,
                    settlement_lag_seconds=self.policy.settlement_lag_seconds,
                    buffer_margin_seconds=self.policy.buffer_margin_seconds,
                    actor=actor,
                    intent_id=intent_id,
                    correlation_id=correlation_id,
                    connection=connection,
                )
                await self._checkpoint(
                    "AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER"
                )
                try:
                    ack = await self._confirm_dispatch_barrier(
                        connection,
                        scope=dispatch_scope(
                            execution_id,
                            intent.intent_id,
                            intent.prepared_state_version,
                        ),
                    )
                except WriteAheadWorkflowError as barrier_error:
                    # No provider bytes have been sent.  If ownership remains,
                    # make one fenced attempt to persist the definitive local
                    # no-dispatch result and confirm that second write.
                    if await connection.get(f"aep:lock:{execution_id}") == token:
                        try:
                            await self.store.transition_intent(
                                execution_id=execution_id,
                                intent_id=intent.intent_id,
                                expected_version=intent.prepared_state_version,
                                lock_token=token,
                                new_status=IntentStatus.FAILED_CONFIRMED,
                                actor=actor,
                                reason="pre-dispatch-durability-failure",
                                evidence={"class": "LOCAL_NO_DISPATCH"},
                                observation_class="DEFINITIVE_FAILURE",
                                connection=connection,
                            )
                            await self._confirm_barrier(connection)
                        except Exception:
                            # The conservative ABOUT_TO_FIRE or unconfirmed
                            # resolution is left for recovery.
                            pass
                    raise barrier_error

                # The acknowledgement is spent here, converting it into a
                # Redis-visible authorization the preflight must re-check.
                dispatch_authorization = await self.store.authorize_dispatch(
                    execution_id=execution_id,
                    intent_id=intent.intent_id,
                    prepared_state_version=intent.prepared_state_version,
                    lock_token=token,
                    request_binding=prepared.binding,
                    ack=ack,
                    authorization_ttl_ms=required_ttl_ms,
                    connection=connection,
                )

            await self._checkpoint(
                "AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT"
            )
            try:
                await self.store.preflight(
                    execution_id=execution_id,
                    intent_id=intent.intent_id,
                    prepared_state_version=intent.prepared_state_version,
                    lock_token=token,
                    required_ttl_ms=required_ttl_ms,
                    request_binding=prepared.binding,
                    authorization=dispatch_authorization,
                )
            except IntentPreflightError:
                # A failed preflight is definitive only if this worker still
                # owns the lease and can persist the no-dispatch resolution.
                if await self.store.redis.get(
                    f"aep:lock:{execution_id}"
                ) == token:
                    async with self.store.pinned_connection() as connection:
                        failed = await self.store.transition_intent(
                            execution_id=execution_id,
                            intent_id=intent.intent_id,
                            expected_version=intent.prepared_state_version,
                            lock_token=token,
                            new_status=IntentStatus.FAILED_CONFIRMED,
                            actor=actor,
                            reason="pre-dispatch-preflight-failure",
                            observation_class="DEFINITIVE_FAILURE",
                            connection=connection,
                        )
                        await self._confirm_barrier(connection)
                    return failed
                raise WriteAheadWorkflowError(
                    "preflight failed after lease ownership was lost"
                ) from None

            try:
                authoritative_state = await self.store.get_execution(
                    execution_id
                )
                if (
                    authoritative_state is None
                    or authoritative_state.version
                    != intent.prepared_state_version
                    or intent.intent_id not in authoritative_state.intent_ledger
                ):
                    raise IntentBindingError(
                        "authoritative request binding is unavailable"
                    )
                authoritative_intent = authoritative_state.intent_ledger[
                    intent.intent_id
                ]
                if (
                    authoritative_intent.request_binding is None
                    or authoritative_intent.canonical_request_binding
                    != canonical_request_binding_bytes(
                        prepared.binding
                    ).decode("utf-8")
                ):
                    raise IntentBindingError(
                        "authoritative canonical request binding changed"
                    )
                verify_now_ms = int((await self.store.redis_time()) * 1000)
                verified_dispatch = await self.binding_service.verify(
                    binding=authoritative_intent.request_binding,
                    execution_id=execution_id,
                    step_id=step_id,
                    intent_id=intent.intent_id,
                    correlation_id=intent.correlation_id,
                    now_ms=verify_now_ms,
                    minimum_retention_not_after_ms=(
                        prepared.binding.created_at_ms
                        + self.store.unresolved_ttl_seconds * 1000
                    ),
                )
            except (RequestBindingError, RequestVaultError) as exc:
                raise WriteAheadWorkflowError(
                    f"verified-dispatch-rejected:{exc}"
                ) from None

            # The last instruction before any provider bytes can exist. A
            # process cut here has a durable, authorised ABOUT_TO_FIRE intent
            # and has provably not dispatched; a process cut *after* this line
            # may have. It is also the point an out-of-process injector arms a
            # deferred kill from, to land inside the socket wait
            # (experiments/harness/crash_points.py, ``mid_dispatch``).
            await self._checkpoint("AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION")

            try:
                response = await self.connector.mutate(
                    dispatch=verified_dispatch,
                    client_timeout=self.policy.client_timeout_seconds,
                )
                evidence_value = getattr(
                    getattr(response, "evidence", None), "value", None
                )
                declared_evidence = (
                    self.policy.definitive_success_evidence
                    | self.policy.definitive_failure_evidence
                )
                evidence = (
                    evidence_value
                    if type(evidence_value) is str
                    and evidence_value in declared_evidence
                    else None
                )
                if evidence in self.policy.definitive_success_evidence:
                    target_status = IntentStatus.FIRED_CONFIRMED
                    reason = "connector-definitive-success"
                elif evidence in self.policy.definitive_failure_evidence:
                    target_status = IntentStatus.FAILED_CONFIRMED
                    reason = "connector-definitive-no-effect-failure"
                else:
                    target_status = IntentStatus.FIRED_UNCONFIRMED
                    reason = "connector-unclassified-response"
                # Provider-returned identifiers have no repository-defined,
                # profile-specific safe-value schema yet. Persist none.
                external_reference = None
                observation_class = evidence or "AMBIGUOUS"
                evidence_payload = {
                    "class": observation_class,
                }
            except Exception:
                # Connector exceptions are ambiguous by default.  Simulated
                # process death derives from BaseException and is not caught.
                target_status = IntentStatus.FIRED_UNCONFIRMED
                reason = "connector-ambiguous-exception"
                external_reference = None
                observation_class = "AMBIGUOUS"
                evidence_payload = {
                    "class": "AMBIGUOUS",
                }

            await self._checkpoint("DURING_RESOLUTION_CAS")
            async with self.store.pinned_connection() as connection:
                resolved = await self.store.transition_intent(
                    execution_id=execution_id,
                    intent_id=intent.intent_id,
                    expected_version=intent.prepared_state_version,
                    lock_token=token,
                    new_status=target_status,
                    actor=actor,
                    reason=reason,
                    evidence=evidence_payload,
                    observation_class=observation_class,
                    external_reference=external_reference,
                    connection=connection,
                )
                await self._checkpoint(
                    "AFTER_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER"
                )
                await self._checkpoint(
                    "DURING_RESOLUTION_DURABILITY_BARRIER"
                )
                await self._confirm_barrier(connection)

            if target_status is IntentStatus.FIRED_UNCONFIRMED:
                await self._checkpoint(
                    "AFTER_DURABLE_FIRED_UNCONFIRMED_BEFORE_LEASE_RELEASE"
                )
            else:
                await self._checkpoint(
                    "AFTER_DURABLE_CONFIRMED_RESOLUTION_BEFORE_LEASE_RELEASE"
                )
            return resolved
        finally:
            await self.lock_manager.release_lock(execution_id, token)
