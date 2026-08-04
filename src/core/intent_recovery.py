"""Phase 2 discovery, fenced claiming, and read-only reconciliation."""

from __future__ import annotations

import asyncio
import inspect
import math
import random
import time
from dataclasses import dataclass
from typing import Any, Mapping

from src.core.durability import DurabilityBarrier
from src.core.intent_workflow import (
    ConnectorPolicy,
    CrashInjectorProtocol,
    WriteAheadWorkflowError,
)
from src.core.intents import (
    IntentLedgerStore,
    IntentRecord,
    IntentStatus,
    ReconciliationProgress,
)
from src.core.locks import DistributedLockManager
from src.core.request_binding import ReconciliationContext


@dataclass(frozen=True)
class RecoveryConnectorConfig:
    connector: Any
    barrier: DurabilityBarrier
    policy: ConnectorPolicy


@dataclass(frozen=True)
class RecoveryResult:
    execution_id: str
    intent_id: str
    status: IntentStatus
    readback_performed: bool


class IntentRecoveryService:
    """Cursor-scan state keys and reconcile eligible intents read-only."""

    def __init__(
        self,
        *,
        store: IntentLedgerStore,
        lock_manager: DistributedLockManager,
        connectors: Mapping[str, RecoveryConnectorConfig],
        scan_count: int = 500,
        max_concurrency: int = 16,
        crash_injector: CrashInjectorProtocol | None = None,
        crash_point_enum: type[Any] | None = None,
        random_source: random.Random | None = None,
        recovery_lag_alert: Any | None = None,
    ) -> None:
        if scan_count <= 0 or max_concurrency <= 0:
            raise ValueError("scan_count and max_concurrency must be positive")
        self.store = store
        self.lock_manager = lock_manager
        self.connectors = dict(connectors)
        self.scan_count = scan_count
        self.max_concurrency = max_concurrency
        self.crash_injector = crash_injector
        self.crash_point_enum = crash_point_enum
        self.random = random_source or random.Random()
        self.recovery_lag_alert = recovery_lag_alert
        for name, config in self.connectors.items():
            required_retention = math.ceil(
                config.policy.max_reconciliation_duration_seconds
            ) + 7 * 24 * 60 * 60
            if store.unresolved_ttl_seconds < required_retention:
                raise ValueError(
                    f"intent TTL for connector {name!r} must cover maximum "
                    "reconciliation duration plus 7-day operator retention"
                )

    async def _checkpoint(self, name: str) -> None:
        if self.crash_injector is not None:
            if self.crash_point_enum is None:
                raise RuntimeError(
                    "crash_point_enum is required when a crash injector is supplied"
                )
            await self.crash_injector.checkpoint(self.crash_point_enum[name])

    @staticmethod
    def _eligible(intent: IntentRecord, now: float) -> bool:
        if intent.status is IntentStatus.ABOUT_TO_FIRE:
            return now >= intent.reconcile_after
        if intent.status is IntentStatus.FIRED_UNCONFIRMED:
            assert intent.reconciliation is not None
            return now >= intent.reconciliation.next_check_at
        return False

    async def scan_once(self) -> list[RecoveryResult]:
        """Perform one cursor-based SCAN pass with bounded concurrency."""

        now = await self.store.redis_time()
        candidates: list[tuple[str, str]] = []
        async for key in self.store.redis.scan_iter(
            match="aep:state:*", count=self.scan_count
        ):
            execution_id = key.removeprefix("aep:state:")
            state = await self.store.get_execution(execution_id)
            if state is None:
                continue
            for intent in state.intent_ledger.values():
                if self._eligible(intent, now):
                    candidates.append((execution_id, intent.intent_id))

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def bounded(execution_id: str, intent_id: str):
            async with semaphore:
                return await self.recover_intent(execution_id, intent_id)

        results = await asyncio.gather(
            *(bounded(execution_id, intent_id) for execution_id, intent_id in candidates)
        )
        return [result for result in results if result is not None]

    async def run_forever(
        self,
        stop: asyncio.Event,
        *,
        pass_interval_seconds: float = 30.0,
        pass_slo_seconds: float = 300.0,
    ) -> None:
        """Continuously scan, spacing passes 30s after cursor zero by default."""

        if pass_interval_seconds <= 0 or pass_slo_seconds <= 0:
            raise ValueError("recovery interval and SLO must be positive")
        while not stop.is_set():
            started = time.monotonic()
            await self.scan_once()
            elapsed = time.monotonic() - started
            if elapsed > pass_slo_seconds and self.recovery_lag_alert is not None:
                result = self.recovery_lag_alert(elapsed)
                if inspect.isawaitable(result):
                    await result
            try:
                await asyncio.wait_for(stop.wait(), timeout=pass_interval_seconds)
            except asyncio.TimeoutError:
                pass

    async def _acquire(self, execution_id: str, policy: ConnectorPolicy) -> str | None:
        for attempt in range(1, policy.lease_acquire_attempts + 1):
            token = await self.lock_manager.acquire_lock(
                execution_id, ttl_seconds=policy.lock_ttl_seconds
            )
            if token is not None:
                return token
            if attempt < policy.lease_acquire_attempts:
                ceiling = min(
                    0.05 * (2 ** (attempt - 1)), policy.lease_backoff_cap_seconds
                )
                await asyncio.sleep(self.random.uniform(0, ceiling))
        return None

    async def _durable(self, barrier, connection, timeout_ms: int) -> None:
        try:
            durable = await barrier.confirm_durable(connection, timeout_ms)
        except Exception as exc:
            raise WriteAheadWorkflowError(
                f"recovery durability barrier failed:{type(exc).__name__}"
            ) from None
        if not durable:
            raise WriteAheadWorkflowError(
                "recovery durability barrier did not acknowledge the write"
            )

    async def recover_intent(
        self, execution_id: str, intent_id: str
    ) -> RecoveryResult | None:
        """Claim one eligible intent, perform one read-back, persist evidence."""

        initial = await self.store.get_execution(execution_id)
        if initial is None or intent_id not in initial.intent_ledger:
            return None
        initial_intent = initial.intent_ledger[intent_id]
        config = self.connectors.get(initial_intent.connector)
        if config is None:
            raise WriteAheadWorkflowError(
                f"no recovery connector declaration for {initial_intent.connector!r}"
            )

        token = await self._acquire(execution_id, config.policy)
        if token is None:
            return None
        try:
            current = await self.store.get_execution(execution_id)
            now = await self.store.redis_time()
            if current is None or intent_id not in current.intent_ledger:
                return None
            intent = current.intent_ledger[intent_id]
            if not self._eligible(intent, now):
                return None
            if intent.status not in {
                IntentStatus.ABOUT_TO_FIRE,
                IntentStatus.FIRED_UNCONFIRMED,
            }:
                return None

            if intent.status is IntentStatus.ABOUT_TO_FIRE:
                await self._checkpoint("DURING_RECOVERY_BEFORE_CLAIM_CAS")
                async with self.store.pinned_connection() as connection:
                    intent = await self.store.transition_intent(
                        execution_id=execution_id,
                        intent_id=intent_id,
                        expected_version=current.version,
                        lock_token=token,
                        new_status=IntentStatus.FIRED_UNCONFIRMED,
                        actor="recovery",
                        reason="orphaned-about-to-fire",
                        evidence={"class": "ORPHANED_ABOUT_TO_FIRE"},
                        observation_class="AMBIGUOUS",
                        connection=connection,
                    )
                    await self._durable(
                        config.barrier,
                        connection,
                        config.policy.durability_timeout_ms,
                    )
                current_version = current.version + 1
            else:
                current_version = current.version

            capability = getattr(
                getattr(config.connector, "reconciliation_capability", None),
                "value",
                None,
            )
            if capability == "NO_READBACK":
                return await self._persist_recovery_resolution(
                    execution_id=execution_id,
                    intent=intent,
                    expected_version=current_version,
                    token=token,
                    config=config,
                    target=IntentStatus.PERMANENTLY_AMBIGUOUS,
                    reason="connector-has-no-readback",
                    evidence_class="NO_READBACK",
                    external_reference=None,
                    reconciliation=intent.reconciliation,
                    readback_performed=False,
                )

            try:
                context = ReconciliationContext(
                    execution_id=execution_id,
                    step_id=intent.step_id,
                    intent_id=intent.intent_id,
                    correlation_id=intent.correlation_id,
                    connector_operation=intent.connector,
                    redacted_target=intent.target,
                    request_fingerprint=intent.request_fingerprint,
                    external_reference=None,
                    attempt_count=(
                        intent.reconciliation.attempt_count
                        if intent.reconciliation is not None
                        else 0
                    ),
                )
                observation = await config.connector.read_back(
                    context=context,
                    readback_timeout=config.policy.client_timeout_seconds,
                )
            except Exception:
                observation = None
            except BaseException:
                # Process/coroutine death must remain observable to crash tests.
                raise
            result_value = getattr(
                getattr(observation, "result", None), "value", None
            )
            result = (
                result_value
                if type(result_value) is str
                and result_value in {"APPLIED", "NOT_APPLIED", "UNKNOWN", "CONFLICT"}
                else "UNKNOWN"
            )
            # No endpoint-profile rule exists for provider-returned opaque
            # identifiers, so they are not persisted or fed back to readback.
            external_reference = None

            if result == "APPLIED":
                target = IntentStatus.FIRED_CONFIRMED
                reason = "authoritative-or-positive-readback-applied"
                progress = intent.reconciliation
            elif result == "NOT_APPLIED" and capability == "AUTHORITATIVE_READBACK":
                target = IntentStatus.FAILED_CONFIRMED
                reason = "authoritative-readback-not-applied"
                progress = intent.reconciliation
            elif result == "CONFLICT" or result == "NOT_APPLIED":
                target = IntentStatus.PERMANENTLY_AMBIGUOUS
                reason = "conflicting-or-nonauthoritative-negative-evidence"
                progress = intent.reconciliation
            elif result == "UNKNOWN":
                previous = intent.reconciliation
                if previous is None:
                    raise WriteAheadWorkflowError(
                        "FIRED_UNCONFIRMED intent lacks reconciliation progress"
                    )
                attempts = previous.attempt_count + 1
                first_check = previous.first_check_at or now
                exhausted = (
                    attempts >= config.policy.max_reconciliation_attempts
                    or now
                    >= intent.reconcile_after
                    + config.policy.max_reconciliation_duration_seconds
                )
                if exhausted:
                    target = IntentStatus.PERMANENTLY_AMBIGUOUS
                    reason = "reconciliation-attempt-or-duration-limit"
                    next_check = now
                else:
                    target = IntentStatus.FIRED_UNCONFIRMED
                    reason = "reconciliation-unknown-scheduled-backoff"
                    delay = self.random.uniform(
                        0, config.policy.backoff_ceiling(attempts)
                    )
                    next_check = now + delay
                progress = ReconciliationProgress(
                    attempt_count=attempts,
                    first_check_at=first_check,
                    last_check_at=now,
                    next_check_at=next_check,
                    last_evidence_class="UNKNOWN",
                )
            else:
                target = IntentStatus.PERMANENTLY_AMBIGUOUS
                reason = "unclassified-readback-evidence"
                progress = intent.reconciliation

            return await self._persist_recovery_resolution(
                execution_id=execution_id,
                intent=intent,
                expected_version=current_version,
                token=token,
                config=config,
                target=target,
                reason=reason,
                evidence_class=result or "UNCLASSIFIED",
                external_reference=external_reference,
                reconciliation=progress,
                readback_performed=True,
            )
        finally:
            await self.lock_manager.release_lock(execution_id, token)

    async def _persist_recovery_resolution(
        self,
        *,
        execution_id: str,
        intent: IntentRecord,
        expected_version: int,
        token: str,
        config: RecoveryConnectorConfig,
        target: IntentStatus,
        reason: str,
        evidence_class: str,
        external_reference: str | None,
        reconciliation: ReconciliationProgress | None,
        readback_performed: bool,
    ) -> RecoveryResult:
        await self._checkpoint("DURING_RECOVERY_RESOLUTION_CAS")
        async with self.store.pinned_connection() as connection:
            updated = await self.store.transition_intent(
                execution_id=execution_id,
                intent_id=intent.intent_id,
                expected_version=expected_version,
                lock_token=token,
                new_status=target,
                actor="recovery",
                reason=reason,
                evidence={"class": evidence_class},
                observation_class=evidence_class,
                external_reference=external_reference,
                reconciliation=reconciliation,
                connection=connection,
            )
            await self._checkpoint(
                "AFTER_RECOVERY_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER"
            )
            await self._checkpoint(
                "DURING_RECOVERY_RESOLUTION_DURABILITY_BARRIER"
            )
            await self._durable(
                config.barrier,
                connection,
                config.policy.durability_timeout_ms,
            )
        return RecoveryResult(
            execution_id=execution_id,
            intent_id=intent.intent_id,
            status=updated.status,
            readback_performed=readback_performed,
        )
