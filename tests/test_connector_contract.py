"""Phase 1B regression tests: the connector contract lives in production code.

These tests encode the Phase 1B requirement that the three reconciliation
response classes are a *production* contract rather than a test-only construct,
that every class is handled explicitly, and that no class reaches a
fall-through branch.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

import pytest

from src.core.connector_contract import (
    PERMITTED_READBACK_RESULTS,
    ConnectorContractError,
    ReadbackResult,
    ReconciliationCapability,
    ReconciliationOutcome,
    classify_readback,
    declared_capability,
    parse_readback_result,
)
from src.core.intents import IntentLedgerStore, IntentStatus
from tests.test_phase2_recovery import (
    CONNECTOR_NAME,
    _policy,
    _seed_stale_about,
    _service,
)

import tests.mock_connector as mock_connector


# ---------------------------------------------------------------------------
# Contract location and shape
# ---------------------------------------------------------------------------


def test_contract_types_are_defined_in_src_core_not_tests():
    """tests/mock_connector.py must import the contract, not define it."""

    assert mock_connector.ReconciliationCapability is ReconciliationCapability
    assert mock_connector.ReadbackResult is ReadbackResult
    assert ReconciliationCapability.__module__ == "src.core.connector_contract"
    assert ReadbackResult.__module__ == "src.core.connector_contract"


def test_permitted_results_table_matches_design_section_8_3():
    """docs/06-phase2-design.md:351-353 permitted-conclusion table."""

    assert PERMITTED_READBACK_RESULTS[
        ReconciliationCapability.AUTHORITATIVE_READBACK
    ] == frozenset(
        {
            ReadbackResult.APPLIED,
            ReadbackResult.NOT_APPLIED,
            ReadbackResult.UNKNOWN,
            ReadbackResult.CONFLICT,
        }
    )
    # Absence never proves failure for a positive-only endpoint.
    assert PERMITTED_READBACK_RESULTS[
        ReconciliationCapability.POSITIVE_ONLY_READBACK
    ] == frozenset(
        {ReadbackResult.APPLIED, ReadbackResult.UNKNOWN, ReadbackResult.CONFLICT}
    )
    assert (
        PERMITTED_READBACK_RESULTS[ReconciliationCapability.NO_READBACK]
        == frozenset()
    )
    # Every declared class has an entry: no class can be silently absent.
    assert set(PERMITTED_READBACK_RESULTS) == set(ReconciliationCapability)


@pytest.mark.parametrize(
    "capability",
    [
        ReconciliationCapability.AUTHORITATIVE_READBACK,
        ReconciliationCapability.POSITIVE_ONLY_READBACK,
    ],
)
@pytest.mark.parametrize("result", list(ReadbackResult))
def test_classify_readback_is_total_over_queryable_classes(capability, result):
    """No (capability, result) pair may reach a fall-through branch."""

    decision = classify_readback(capability, result)
    assert isinstance(decision.outcome, ReconciliationOutcome)
    assert decision.reason
    assert decision.evidence_class


def test_classify_readback_rejects_no_readback_capability():
    """A NO_READBACK connector must never be queried, so classifying is a bug."""

    with pytest.raises(ConnectorContractError):
        classify_readback(
            ReconciliationCapability.NO_READBACK, ReadbackResult.APPLIED
        )


def test_positive_only_not_applied_is_a_named_contract_violation():
    """POSITIVE_ONLY_READBACK may not assert absence (design §8.3)."""

    decision = classify_readback(
        ReconciliationCapability.POSITIVE_ONLY_READBACK,
        ReadbackResult.NOT_APPLIED,
    )
    assert decision.outcome is ReconciliationOutcome.PERMANENTLY_AMBIGUOUS
    assert decision.reason == "positive-only-negative-evidence-contract-violation"


def test_authoritative_not_applied_refutes():
    decision = classify_readback(
        ReconciliationCapability.AUTHORITATIVE_READBACK,
        ReadbackResult.NOT_APPLIED,
    )
    assert decision.outcome is ReconciliationOutcome.REFUTED


@pytest.mark.parametrize(
    "capability",
    [
        ReconciliationCapability.AUTHORITATIVE_READBACK,
        ReconciliationCapability.POSITIVE_ONLY_READBACK,
    ],
)
def test_unknown_always_retries_within_budget(capability):
    decision = classify_readback(capability, ReadbackResult.UNKNOWN)
    assert decision.outcome is ReconciliationOutcome.RETRY


# ---------------------------------------------------------------------------
# Capability / result resolution
# ---------------------------------------------------------------------------


class _NoCapabilityConnector:
    """A connector that forgot to declare its reconciliation capability."""

    read_back_calls = 0

    async def read_back(self, *, context, readback_timeout):  # pragma: no cover
        type(self).read_back_calls += 1
        raise AssertionError("an undeclared connector must never be queried")


class _StringCapabilityConnector:
    reconciliation_capability = "AUTHORITATIVE_READBACK"

    def __init__(self, result: ReadbackResult) -> None:
        self._result = result
        self.read_back_calls = 0

    async def read_back(self, *, context, readback_timeout):
        self.read_back_calls += 1
        return _Observation(result=self._result)


class _ContractViolatingConnector:
    """Declares positive-only authority but reports absence anyway."""

    reconciliation_capability = ReconciliationCapability.POSITIVE_ONLY_READBACK

    def __init__(self) -> None:
        self.read_back_calls = 0

    async def read_back(self, *, context, readback_timeout):
        self.read_back_calls += 1
        return _Observation(result=ReadbackResult.NOT_APPLIED)


@dataclass(frozen=True)
class _Observation:
    result: ReadbackResult


def test_declared_capability_accepts_enum_and_exact_string():
    assert (
        declared_capability(_StringCapabilityConnector(ReadbackResult.APPLIED))
        is ReconciliationCapability.AUTHORITATIVE_READBACK
    )
    assert (
        declared_capability(_ContractViolatingConnector())
        is ReconciliationCapability.POSITIVE_ONLY_READBACK
    )


def test_declared_capability_rejects_missing_or_unknown_declaration():
    with pytest.raises(ConnectorContractError):
        declared_capability(_NoCapabilityConnector())

    class _Bogus:
        reconciliation_capability = "MAYBE_READBACK"

    with pytest.raises(ConnectorContractError):
        declared_capability(_Bogus())


def test_parse_readback_result_defaults_unparseable_evidence_to_unknown():
    assert parse_readback_result(None) is ReadbackResult.UNKNOWN
    assert parse_readback_result(_Observation(result=ReadbackResult.APPLIED)) is (
        ReadbackResult.APPLIED
    )

    class _Weird:
        result = "SOMETHING_ELSE"

    assert parse_readback_result(_Weird()) is ReadbackResult.UNKNOWN


# ---------------------------------------------------------------------------
# End-to-end recovery behaviour against real Redis
# ---------------------------------------------------------------------------


class _Harnessish:
    """Minimal stand-in exposing the attributes _service() needs."""

    def __init__(self, connector) -> None:
        self.connector = connector
        self.crashes = None


def _service_for(redis_client, lock_manager, connector, *, policy=None):
    from src.core.durability import FakeDurabilityBarrier
    from src.core.intent_recovery import (
        IntentRecoveryService,
        RecoveryConnectorConfig,
    )

    config = RecoveryConnectorConfig(
        connector=connector,
        barrier=FakeDurabilityBarrier(),
        policy=policy or _policy(),
    )
    return IntentRecoveryService(
        store=IntentLedgerStore(redis_client),
        lock_manager=lock_manager,
        connectors={CONNECTOR_NAME: config},
    )


@pytest.mark.asyncio
async def test_undeclared_capability_is_permanently_ambiguous_without_query(
    redis_client, storage_adapter, lock_manager
):
    connector = _NoCapabilityConnector()
    execution_id, intent_id, _ = await _seed_stale_about(
        storage_adapter, lock_manager, redis_client
    )
    result = await _service_for(
        redis_client, lock_manager, connector
    ).recover_intent(execution_id, intent_id)

    assert result is not None
    assert result.status is IntentStatus.PERMANENTLY_AMBIGUOUS
    assert result.readback_performed is False
    assert _NoCapabilityConnector.read_back_calls == 0

    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    intent = state.intent_ledger[intent_id]
    assert intent.transitions[-1].reason == "connector-capability-undeclared"


@pytest.mark.asyncio
async def test_positive_only_not_applied_records_the_violation_reason(
    redis_client, storage_adapter, lock_manager
):
    connector = _ContractViolatingConnector()
    execution_id, intent_id, _ = await _seed_stale_about(
        storage_adapter, lock_manager, redis_client
    )
    result = await _service_for(
        redis_client, lock_manager, connector
    ).recover_intent(execution_id, intent_id)

    assert result is not None
    assert result.status is IntentStatus.PERMANENTLY_AMBIGUOUS
    assert connector.read_back_calls == 1

    state = await IntentLedgerStore(redis_client).get_execution(execution_id)
    assert state is not None
    intent = state.intent_ledger[intent_id]
    assert intent.transitions[-1].reason == (
        "positive-only-negative-evidence-contract-violation"
    )
    assert intent.last_observation is not None
    assert intent.last_observation.evidence_class == ReadbackResult.NOT_APPLIED.value


@pytest.mark.asyncio
async def test_string_declared_capability_behaves_as_the_typed_member(
    redis_client, storage_adapter, lock_manager
):
    connector = _StringCapabilityConnector(ReadbackResult.NOT_APPLIED)
    execution_id, intent_id, _ = await _seed_stale_about(
        storage_adapter, lock_manager, redis_client
    )
    result = await _service_for(
        redis_client, lock_manager, connector
    ).recover_intent(execution_id, intent_id)

    assert result is not None
    # Authoritative absence refutes the effect.
    assert result.status is IntentStatus.FAILED_CONFIRMED
    assert connector.read_back_calls == 1


# ---------------------------------------------------------------------------
# Source-level guard for the Phase 1B requirement
# ---------------------------------------------------------------------------


def test_recovery_module_contains_no_capability_or_result_string_literals():
    """PAPER_ROADMAP.md Phase 1B item 1: replace every string-literal comparison."""

    source = pathlib.Path("src/core/intent_recovery.py").read_text(encoding="utf-8")
    forbidden = []
    for member in list(ReconciliationCapability) + list(ReadbackResult):
        for quoted in (f'"{member.value}"', f"'{member.value}'"):
            if quoted in source:
                forbidden.append(quoted)
    assert forbidden == [], (
        "intent_recovery.py must use the typed contract, not string literals: "
        f"{forbidden}"
    )
