"""Deterministic non-idempotent connector harness for Phase 2 crash tests.

This module is test infrastructure only.  A test creates a
``MockConnectorHarness``, passes only ``harness.connector`` to the code under
test, and retains ``harness.oracle`` to inspect simulated external ground
truth afterward.  The connector-facing responses deliberately never expose
whether an ambiguous call actually mutated the simulated external system.

Crash points mirror the rows (and the independently crashable sub-points) in
``docs/06-phase2-design.md`` section 7.  The connector reaches network and
read-back checkpoints itself.  A future runner/recovery test calls
``harness.crashes.checkpoint(...)`` at the lease, Redis CAS, durability, and
lease-release checkpoints that live outside the connector.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque, Iterable

from aep_core.core.connector_contract import (
    ReadbackResult,
    ReconciliationCapability,
)
from aep_core.core.request_binding import (
    ReconciliationContext,
    VerifiedDispatch,
    consume_verified_dispatch,
)

# ``ReconciliationCapability`` and ``ReadbackResult`` are the production
# connector contract (src/core/connector_contract.py).  They are re-exported
# here so existing test imports keep working, but this module no longer owns
# them.


class ResponseMode(str, Enum):
    """One deterministic result for a non-idempotent mutation call."""

    DEFINITIVE_SUCCESS = "DEFINITIVE_SUCCESS"
    DEFINITIVE_FAILURE = "DEFINITIVE_FAILURE"
    TIMEOUT_NO_RESPONSE = "TIMEOUT_NO_RESPONSE"
    CONNECTION_DROP_MID_TRANSMISSION = "CONNECTION_DROP_MID_TRANSMISSION"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"


class CallerEvidence(str, Enum):
    """What the mutation caller was permitted to learn."""

    NONE = "NONE"
    DEFINITIVE_SUCCESS = "DEFINITIVE_SUCCESS"
    DEFINITIVE_FAILURE = "DEFINITIVE_FAILURE"
    AMBIGUOUS = "AMBIGUOUS"


class CrashPoint(str, Enum):
    """Individually armable crash points from design section 7.

    Combined cells in the section 7 crash matrix are split where a process
    can die on either side of a Redis command or durability barrier.  This
    lets adversarial tests target each boundary rather than treating a whole
    row as one coarse failure point.
    """

    BEFORE_LEASE_ACQUISITION = "BEFORE_LEASE_ACQUISITION"
    AFTER_LEASE_ACQUISITION_BEFORE_INTENT_CAS = (
        "AFTER_LEASE_ACQUISITION_BEFORE_INTENT_CAS"
    )
    DURING_INTENT_CAS = "DURING_INTENT_CAS"
    AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER = (
        "AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER"
    )
    AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT = (
        "AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT"
    )
    AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION = (
        "AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION"
    )
    DURING_REQUEST_TRANSMISSION = "DURING_REQUEST_TRANSMISSION"
    WHILE_WAITING_WITHOUT_RESPONSE = "WHILE_WAITING_WITHOUT_RESPONSE"
    AFTER_CONCLUSIVE_SUCCESS_BEFORE_RESOLUTION_CAS = (
        "AFTER_CONCLUSIVE_SUCCESS_BEFORE_RESOLUTION_CAS"
    )
    AFTER_CONCLUSIVE_FAILURE_BEFORE_RESOLUTION_CAS = (
        "AFTER_CONCLUSIVE_FAILURE_BEFORE_RESOLUTION_CAS"
    )
    AFTER_AMBIGUOUS_RESPONSE_BEFORE_RESOLUTION_CAS = (
        "AFTER_AMBIGUOUS_RESPONSE_BEFORE_RESOLUTION_CAS"
    )
    DURING_RESOLUTION_CAS = "DURING_RESOLUTION_CAS"
    AFTER_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER = (
        "AFTER_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER"
    )
    DURING_RESOLUTION_DURABILITY_BARRIER = (
        "DURING_RESOLUTION_DURABILITY_BARRIER"
    )
    AFTER_DURABLE_CONFIRMED_RESOLUTION_BEFORE_LEASE_RELEASE = (
        "AFTER_DURABLE_CONFIRMED_RESOLUTION_BEFORE_LEASE_RELEASE"
    )
    AFTER_DURABLE_FIRED_UNCONFIRMED_BEFORE_LEASE_RELEASE = (
        "AFTER_DURABLE_FIRED_UNCONFIRMED_BEFORE_LEASE_RELEASE"
    )
    DURING_RECOVERY_BEFORE_CLAIM_CAS = (
        "DURING_RECOVERY_BEFORE_CLAIM_CAS"
    )
    AFTER_RECOVERY_CLAIM_BEFORE_READBACK = (
        "AFTER_RECOVERY_CLAIM_BEFORE_READBACK"
    )
    AFTER_READBACK_BEFORE_RECOVERY_RESOLUTION_CAS = (
        "AFTER_READBACK_BEFORE_RECOVERY_RESOLUTION_CAS"
    )
    DURING_RECOVERY_RESOLUTION_CAS = "DURING_RECOVERY_RESOLUTION_CAS"
    AFTER_RECOVERY_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER = (
        "AFTER_RECOVERY_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER"
    )
    DURING_RECOVERY_RESOLUTION_DURABILITY_BARRIER = (
        "DURING_RECOVERY_RESOLUTION_DURABILITY_BARRIER"
    )


class CrashStyle(str, Enum):
    """How an armed checkpoint terminates its current control flow."""

    CANCEL_COROUTINE = "CANCEL_COROUTINE"
    PROCESS_EXIT = "PROCESS_EXIT"


class MockConnectorError(Exception):
    """Base class for ordinary mock connector failures."""


class MockAmbiguousOutcome(MockConnectorError):
    """Base class for outcomes that must become FIRED_UNCONFIRMED."""

    def __init__(self, message: str, *, call_id: str) -> None:
        super().__init__(message)
        self.call_id = call_id


class MockExternalTimeout(MockAmbiguousOutcome):
    """No response arrived within the caller-supplied timeout."""


class MockConnectionDropped(MockAmbiguousOutcome):
    """The connection failed after the request may have reached the server."""


class MockConflictingEvidence(MockAmbiguousOutcome):
    """The simulated provider returned mutually inconsistent evidence."""


class MockReadbackUnavailable(MockConnectorError):
    """Raised if code incorrectly queries a NO_READBACK connector."""


class SimulatedProcessCrash(BaseException):
    """Abrupt process-death signal, intentionally outside ``Exception``.

    A real process exit cannot be caught and inspected by the same pytest
    process.  This ``BaseException`` models that abrupt boundary while keeping
    the test runner alive.  ``CANCEL_COROUTINE`` is available when a test needs
    genuine task cancellation semantics instead.
    """

    def __init__(self, point: CrashPoint) -> None:
        super().__init__(f"simulated process crash at {point.value}")
        self.point = point


@dataclass(frozen=True)
class MutationResponse:
    """Caller-visible response for the two definitive modes only."""

    call_id: str
    evidence: CallerEvidence
    external_reference: str | None = None


@dataclass(frozen=True)
class ReadbackObservation:
    """Caller-visible result of a permitted read-only reconciliation query."""

    intent_id: str
    result: ReadbackResult
    external_reference: str | None = None


@dataclass(frozen=True)
class CallScenario:
    """One queued, deterministic mutation behavior.

    Ambiguous modes require an explicit hidden mutation truth.  Requiring the
    choice prevents a default or random branch from weakening crash tests.
    """

    mode: ResponseMode
    mutation_applied: bool | None = None

    def __post_init__(self) -> None:
        if self.mode is ResponseMode.DEFINITIVE_SUCCESS:
            if self.mutation_applied not in (None, True):
                raise ValueError("DEFINITIVE_SUCCESS must apply the mutation")
        elif self.mode is ResponseMode.DEFINITIVE_FAILURE:
            if self.mutation_applied not in (None, False):
                raise ValueError(
                    "DEFINITIVE_FAILURE must reject before mutation"
                )
        elif self.mutation_applied is None:
            raise ValueError(
                f"{self.mode.value} requires explicit mutation_applied=True "
                "or False so its hidden ground truth is deterministic"
            )

    @property
    def actual_mutation_applied(self) -> bool:
        if self.mode is ResponseMode.DEFINITIVE_SUCCESS:
            return True
        if self.mode is ResponseMode.DEFINITIVE_FAILURE:
            return False
        assert self.mutation_applied is not None
        return self.mutation_applied


@dataclass(frozen=True)
class GroundTruthCall:
    """Test-only snapshot of what actually happened in the external system."""

    call_id: str
    intent_id: str
    mode: ResponseMode
    transmission_started: bool
    request_may_have_reached_server: bool
    mutation_applied: bool
    response_received: bool
    caller_evidence: CallerEvidence
    call_finished: bool
    crashed_at: CrashPoint | None
    external_reference: str | None


@dataclass(frozen=True)
class GroundTruthReadback:
    """Test-only record of a reconciliation query and its evidence."""

    intent_id: str
    result: ReadbackResult
    scripted: bool
    crashed_at: CrashPoint | None


@dataclass
class _MutableGroundTruthCall:
    call_id: str
    intent_id: str
    mode: ResponseMode
    transmission_started: bool = False
    request_may_have_reached_server: bool = False
    mutation_applied: bool = False
    response_received: bool = False
    caller_evidence: CallerEvidence = CallerEvidence.NONE
    call_finished: bool = False
    crashed_at: CrashPoint | None = None
    external_reference: str | None = None

    def snapshot(self) -> GroundTruthCall:
        return GroundTruthCall(**vars(self))


@dataclass
class _MutableGroundTruthReadback:
    intent_id: str
    result: ReadbackResult
    scripted: bool
    crashed_at: CrashPoint | None = None

    def snapshot(self) -> GroundTruthReadback:
        return GroundTruthReadback(**vars(self))


class _GroundTruthStore:
    """Private mutable state shared by the connector and test-only oracle."""

    def __init__(self) -> None:
        self.calls: list[_MutableGroundTruthCall] = []
        self.readbacks: list[_MutableGroundTruthReadback] = []


class GroundTruthOracle:
    """Test-only inspection surface; never pass this object to caller code."""

    def __init__(self, store: _GroundTruthStore) -> None:
        self.__store = store

    @property
    def calls(self) -> tuple[GroundTruthCall, ...]:
        return tuple(item.snapshot() for item in self.__store.calls)

    @property
    def readbacks(self) -> tuple[GroundTruthReadback, ...]:
        return tuple(item.snapshot() for item in self.__store.readbacks)

    def calls_for_intent(self, intent_id: str) -> tuple[GroundTruthCall, ...]:
        return tuple(
            item.snapshot()
            for item in self.__store.calls
            if item.intent_id == intent_id
        )


class CrashInjector:
    """One-shot deterministic crash injection for runner and connector tests."""

    def __init__(self) -> None:
        self._armed: tuple[CrashPoint, CrashStyle] | None = None
        self._reached: list[CrashPoint] = []
        self._triggered: list[CrashPoint] = []

    @property
    def reached_points(self) -> tuple[CrashPoint, ...]:
        return tuple(self._reached)

    @property
    def triggered_points(self) -> tuple[CrashPoint, ...]:
        return tuple(self._triggered)

    @property
    def last_triggered_point(self) -> CrashPoint | None:
        return self._triggered[-1] if self._triggered else None

    def arm(
        self,
        point: CrashPoint,
        *,
        style: CrashStyle = CrashStyle.CANCEL_COROUTINE,
    ) -> None:
        if self._armed is not None:
            armed_point, _ = self._armed
            raise RuntimeError(
                f"crash point {armed_point.value} is already armed"
            )
        self._armed = (point, style)

    def disarm(self) -> None:
        self._armed = None

    async def checkpoint(self, point: CrashPoint) -> None:
        """Record a reached point and terminate if that point is armed."""

        self._reached.append(point)
        if self._armed is None or self._armed[0] is not point:
            return

        _, style = self._armed
        self._armed = None
        self._triggered.append(point)

        if style is CrashStyle.PROCESS_EXIT:
            raise SimulatedProcessCrash(point)

        task = asyncio.current_task()
        if task is None:  # pragma: no cover - asyncio always supplies one here
            raise RuntimeError("cannot cancel crash checkpoint outside a task")
        task.cancel(f"simulated crash at {point.value}")
        await asyncio.sleep(0)
        raise AssertionError("task cancellation did not interrupt checkpoint")


class MockExternalConnector:
    """Caller-facing non-idempotent connector with no ground-truth API."""

    test_only = True
    connector_identity = "mock-connector"
    connector_operation = "mock.non-idempotent.v1/mutate"
    endpoint_profile_id = "mock-endpoint"
    endpoint_profile_version = "1"

    def __init__(
        self,
        *,
        capability: ReconciliationCapability,
        call_scenarios: Deque[CallScenario],
        readback_scenarios: Deque[ReadbackResult],
        store: _GroundTruthStore,
        crashes: CrashInjector,
    ) -> None:
        self.reconciliation_capability = capability
        self.__call_scenarios = call_scenarios
        self.__readback_scenarios = readback_scenarios
        self.__store = store
        self.__crashes = crashes
        self.__call_sequence = 0

    async def mutate(
        self,
        *,
        dispatch: VerifiedDispatch,
        client_timeout: float,
    ) -> MutationResponse:
        """Make one scripted non-idempotent call with transport retries absent."""

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
        intent_id = dispatch.binding.intent_id
        if client_timeout <= 0:
            raise ValueError("client_timeout must be greater than zero")
        if not self.__call_scenarios:
            raise AssertionError(
                "no mock response queued; enqueue every expected call explicitly"
            )

        scenario = self.__call_scenarios.popleft()
        self.__call_sequence += 1
        call_id = f"mock-call-{self.__call_sequence}"
        record = _MutableGroundTruthCall(
            call_id=call_id,
            intent_id=intent_id,
            mode=scenario.mode,
        )
        self.__store.calls.append(record)
        trigger_count_before_call = len(self.__crashes.triggered_points)

        try:
            await self.__crashes.checkpoint(
                CrashPoint.AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION
            )

            record.transmission_started = True
            record.request_may_have_reached_server = True
            record.mutation_applied = scenario.actual_mutation_applied
            if record.mutation_applied:
                record.external_reference = f"mock-effect-{call_id}"

            await self.__crashes.checkpoint(
                CrashPoint.DURING_REQUEST_TRANSMISSION
            )

            if scenario.mode is ResponseMode.TIMEOUT_NO_RESPONSE:
                await self.__crashes.checkpoint(
                    CrashPoint.WHILE_WAITING_WITHOUT_RESPONSE
                )
                await asyncio.sleep(client_timeout)
                record.caller_evidence = CallerEvidence.AMBIGUOUS
                record.call_finished = True
                await self.__crashes.checkpoint(
                    CrashPoint.AFTER_AMBIGUOUS_RESPONSE_BEFORE_RESOLUTION_CAS
                )
                raise MockExternalTimeout(
                    "mock request timed out without a response",
                    call_id=call_id,
                )

            if scenario.mode is ResponseMode.CONNECTION_DROP_MID_TRANSMISSION:
                record.caller_evidence = CallerEvidence.AMBIGUOUS
                record.call_finished = True
                await self.__crashes.checkpoint(
                    CrashPoint.AFTER_AMBIGUOUS_RESPONSE_BEFORE_RESOLUTION_CAS
                )
                raise MockConnectionDropped(
                    "mock connection dropped after possible transmission",
                    call_id=call_id,
                )

            if scenario.mode is ResponseMode.CONFLICTING_EVIDENCE:
                record.response_received = True
                record.caller_evidence = CallerEvidence.AMBIGUOUS
                record.call_finished = True
                await self.__crashes.checkpoint(
                    CrashPoint.AFTER_AMBIGUOUS_RESPONSE_BEFORE_RESOLUTION_CAS
                )
                raise MockConflictingEvidence(
                    "mock provider returned conflicting evidence",
                    call_id=call_id,
                )

            if scenario.mode is ResponseMode.DEFINITIVE_FAILURE:
                record.response_received = True
                record.caller_evidence = CallerEvidence.DEFINITIVE_FAILURE
                record.call_finished = True
                await self.__crashes.checkpoint(
                    CrashPoint.AFTER_CONCLUSIVE_FAILURE_BEFORE_RESOLUTION_CAS
                )
                return MutationResponse(
                    call_id=call_id,
                    evidence=CallerEvidence.DEFINITIVE_FAILURE,
                )

            record.response_received = True
            record.caller_evidence = CallerEvidence.DEFINITIVE_SUCCESS
            record.call_finished = True
            await self.__crashes.checkpoint(
                CrashPoint.AFTER_CONCLUSIVE_SUCCESS_BEFORE_RESOLUTION_CAS
            )
            return MutationResponse(
                call_id=call_id,
                evidence=CallerEvidence.DEFINITIVE_SUCCESS,
                external_reference=record.external_reference,
            )
        except BaseException:
            if len(self.__crashes.triggered_points) > trigger_count_before_call:
                record.crashed_at = self.__crashes.last_triggered_point
            raise

    async def read_back(
        self,
        *,
        context: ReconciliationContext,
        readback_timeout: float,
    ) -> ReadbackObservation:
        """Perform one read-only reconciliation query allowed by capability."""

        if not isinstance(context, ReconciliationContext):
            raise TypeError("safe reconciliation context is required")
        if readback_timeout <= 0:
            raise ValueError("readback timeout must be positive")
        intent_id = context.intent_id

        if self.reconciliation_capability is ReconciliationCapability.NO_READBACK:
            raise MockReadbackUnavailable(
                "NO_READBACK connector must proceed to operator review"
            )

        await self.__crashes.checkpoint(
            CrashPoint.AFTER_RECOVERY_CLAIM_BEFORE_READBACK
        )

        scripted = bool(self.__readback_scenarios)
        if scripted:
            result = self.__readback_scenarios.popleft()
        else:
            result = self.__derive_readback(intent_id)

        if (
            self.reconciliation_capability
            is ReconciliationCapability.POSITIVE_ONLY_READBACK
            and result is ReadbackResult.NOT_APPLIED
        ):
            raise AssertionError(
                "POSITIVE_ONLY_READBACK cannot provide NOT_APPLIED evidence"
            )

        readback = _MutableGroundTruthReadback(
            intent_id=intent_id,
            result=result,
            scripted=scripted,
        )
        self.__store.readbacks.append(readback)

        try:
            await self.__crashes.checkpoint(
                CrashPoint.AFTER_READBACK_BEFORE_RECOVERY_RESOLUTION_CAS
            )
        except BaseException:
            readback.crashed_at = self.__crashes.last_triggered_point
            raise

        external_reference = None
        if result is ReadbackResult.APPLIED:
            matching = [
                item
                for item in self.__store.calls
                if item.intent_id == intent_id and item.mutation_applied
            ]
            if len(matching) == 1:
                external_reference = matching[0].external_reference

        return ReadbackObservation(
            intent_id=intent_id,
            result=result,
            external_reference=external_reference,
        )

    def __derive_readback(self, intent_id: str) -> ReadbackResult:
        matching = [
            item for item in self.__store.calls if item.intent_id == intent_id
        ]

        # More than one dispatch for one intent is itself conflicting evidence.
        if len(matching) > 1:
            return ReadbackResult.CONFLICT
        if matching and matching[0].mode is ResponseMode.CONFLICTING_EVIDENCE:
            return ReadbackResult.CONFLICT

        mutation_applied = bool(matching and matching[0].mutation_applied)
        if mutation_applied:
            return ReadbackResult.APPLIED
        if (
            self.reconciliation_capability
            is ReconciliationCapability.AUTHORITATIVE_READBACK
        ):
            return ReadbackResult.NOT_APPLIED
        return ReadbackResult.UNKNOWN


class MockConnectorHarness:
    """Test rig that separates caller access from the ground-truth oracle."""

    def __init__(
        self,
        *,
        capability: ReconciliationCapability = (
            ReconciliationCapability.AUTHORITATIVE_READBACK
        ),
    ) -> None:
        call_scenarios: Deque[CallScenario] = deque()
        readback_scenarios: Deque[ReadbackResult] = deque()
        store = _GroundTruthStore()

        self.crashes = CrashInjector()
        self.oracle = GroundTruthOracle(store)
        self.connector = MockExternalConnector(
            capability=capability,
            call_scenarios=call_scenarios,
            readback_scenarios=readback_scenarios,
            store=store,
            crashes=self.crashes,
        )
        self.__call_scenarios = call_scenarios
        self.__readback_scenarios = readback_scenarios

    def enqueue_call(
        self,
        mode: ResponseMode,
        *,
        mutation_applied: bool | None = None,
    ) -> None:
        self.__call_scenarios.append(
            CallScenario(mode=mode, mutation_applied=mutation_applied)
        )

    def enqueue_calls(self, scenarios: Iterable[CallScenario]) -> None:
        self.__call_scenarios.extend(scenarios)

    def enqueue_readback(self, result: ReadbackResult) -> None:
        if (
            self.connector.reconciliation_capability
            is ReconciliationCapability.NO_READBACK
        ):
            raise ValueError("cannot script a read-back for NO_READBACK")
        if (
            self.connector.reconciliation_capability
            is ReconciliationCapability.POSITIVE_ONLY_READBACK
            and result is ReadbackResult.NOT_APPLIED
        ):
            raise ValueError(
                "POSITIVE_ONLY_READBACK cannot be scripted as NOT_APPLIED"
            )
        self.__readback_scenarios.append(result)
