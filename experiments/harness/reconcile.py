"""Cross-check the run log against the ground-truth ledger.

Amendment C4 calls ``events.jsonl`` "the second oracle", and amendment C5 says
a disagreement between it and the mock API's SQLite ledger is a bug, not
something to reconcile in prose. This module is where that check lives.

**How an effect is attributed to an execution.** By ``target``. The workload
gives every execution its own resource (``account-<execution_id>``), so an
applied mutation names the execution that caused it without any cooperation
from the protocol -- which matters, because the executions this harness cares
most about are the ones whose worker died before it could record anything. A
``client_reference`` would only attribute the effects of executions that lived
long enough to resolve.

**What "agreement" means.** Not equality of two numbers computed from the same
place. The run log knows what the protocol *decided*; the ledger knows what the
world *did*; neither can see the other. The checks below are the statements
that must hold between them:

1. Every applied mutation is attributable to a planned execution. An effect the
   experiment cannot account for invalidates the run.
2. An execution the protocol resolved ``FAILED_CONFIRMED`` applied nothing.
   This is the strongest single check in the harness: a definitive "no effect"
   contradicted by the ledger would be the protocol lying, which is the exact
   failure the fail-closed design exists to make impossible.
3. An execution the protocol resolved ``FIRED_CONFIRMED`` applied at least one
   effect.
4. Executions in an *ambiguous* terminal state (``PERMANENTLY_AMBIGUOUS``,
   ``FIRED_UNCONFIRMED``) may have applied zero or one effect. That freedom is
   the whole point: AEP converts a silent guess into a declared unknown, and
   the ledger is allowed to disagree with the protocol's uncertainty because
   the protocol never claimed to know.
5. The number of resources that changed lies between the count the protocol is
   certain about and the count it could not rule out.
6. Every duplicate the ledger reports is classified by cause, and the ones the
   caller caused are counted separately from the ones the provider caused
   internally. The roadmap's headline "undetected duplicate rate" counts both,
   because from the world's point of view both are extra effects nobody
   flagged; the decomposition is reported alongside it because only the first
   is something a caller-side protocol could ever have prevented.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from aep_core.core.intents import IntentStatus

from experiments.harness.config import run_config_from_mapping
from experiments.harness.events import events_of, read_events
from experiments.harness.workload import plan_workload
from experiments.mock_api.ledger import GroundTruthLedger

#: Terminal statuses in which the protocol asserts it knows what happened.
CONFIRMED_STATUSES = frozenset(
    {IntentStatus.FIRED_CONFIRMED.value, IntentStatus.FAILED_CONFIRMED.value}
)
#: Terminal statuses in which the protocol declares it does not know.
AMBIGUOUS_STATUSES = frozenset(
    {
        IntentStatus.PERMANENTLY_AMBIGUOUS.value,
        IntentStatus.FIRED_UNCONFIRMED.value,
        IntentStatus.ABOUT_TO_FIRE.value,
    }
)
#: Recorded when an execution never reached a durable intent at all.
NO_INTENT = "NO_INTENT"


@dataclass(frozen=True)
class ExecutionDisagreement:
    """One place where the two records cannot both be right."""

    execution_id: str
    classification: str
    applied_effects: int
    rule: str

    def echo(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "classification": self.classification,
            "applied_effects": self.applied_effects,
            "rule": self.rule,
        }


@dataclass(frozen=True)
class ReconciliationReport:
    """The whole comparison, in a form the run summary can carry verbatim."""

    run_id: str
    config_digest: str
    executions_planned: int
    classifications: Mapping[str, int]
    oracle_applied_rows: int
    oracle_effect_executions: int
    oracle_unattributed_rows: int
    expected_effect_executions_lower: int
    expected_effect_executions_upper: int
    oracle_duplicate_groups: int
    expected_duplicate_groups: int
    caller_redispatch_duplicate_applications: int
    provider_internal_duplicate_applications: int
    undetected_duplicate_applications: int
    disagreements: tuple[ExecutionDisagreement, ...] = field(default=())

    @property
    def agrees(self) -> bool:
        return (
            not self.disagreements
            and self.oracle_unattributed_rows == 0
            and self.oracle_duplicate_groups == self.expected_duplicate_groups
            and (
                self.expected_effect_executions_lower
                <= self.oracle_effect_executions
                <= self.expected_effect_executions_upper
            )
        )

    def echo(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "config_digest": self.config_digest,
            "agrees": self.agrees,
            "executions_planned": self.executions_planned,
            "classifications": dict(sorted(self.classifications.items())),
            "oracle_applied_rows": self.oracle_applied_rows,
            "oracle_effect_executions": self.oracle_effect_executions,
            "oracle_unattributed_rows": self.oracle_unattributed_rows,
            "expected_effect_executions_lower": self.expected_effect_executions_lower,
            "expected_effect_executions_upper": self.expected_effect_executions_upper,
            "oracle_duplicate_groups": self.oracle_duplicate_groups,
            "expected_duplicate_groups": self.expected_duplicate_groups,
            "caller_redispatch_duplicate_applications": (
                self.caller_redispatch_duplicate_applications
            ),
            "provider_internal_duplicate_applications": (
                self.provider_internal_duplicate_applications
            ),
            "undetected_duplicate_applications": (
                self.undetected_duplicate_applications
            ),
            "disagreements": [item.echo() for item in self.disagreements],
        }


def run_configuration_of(records: Sequence[Mapping[str, Any]]):
    """The run config echoed as the first ``run_started`` record."""
    started = events_of(records, "run_started")
    if not started:
        raise ValueError(
            "the run log has no run_started record, so it does not say what "
            "configuration produced it"
        )
    return run_config_from_mapping(dict(started[0]["run_config"]))


def mock_api_echo_of(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    started = events_of(records, "run_started")
    if not started or "mock_api_config" not in started[0]:
        raise ValueError("the run log does not carry the mock API configuration")
    return dict(started[0]["mock_api_config"])


def classifications_of(records: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """The final status of each execution, as the protocol recorded it."""
    return {
        record["execution_id"]: record["status"]
        for record in events_of(records, "final_classification")
    }


def _expected_duplicate_groups(mock_api_echo: Mapping[str, Any]) -> int:
    """What the experiment side predicts before looking at the ledger.

    AEP dispatches at most once per intent and recovery is read-only, so the
    caller contributes no duplicates. The provider contributes them only if a
    configured endpoint has a non-zero duplicate-delivery probability -- and
    with a non-zero probability the count is a random variable, so no exact
    prediction is possible and this returns ``-1`` to mean "not predictable".
    """
    endpoints = mock_api_echo.get("endpoints", {})
    probabilities = [
        endpoint.get("faults", {}).get("duplicate_response_probability", 0.0)
        for endpoint in endpoints.values()
    ]
    if any(probability > 0 for probability in probabilities):
        return -1
    return 0


def reconcile(
    events_path: Path | str, ledger_path: Path | str
) -> ReconciliationReport:
    """Compare one run's log with the ground truth it was collected against."""
    records = read_events(events_path)
    config = run_configuration_of(records)
    mock_api_echo = mock_api_echo_of(records)
    plan = plan_workload(config)
    execution_by_target = {item.target: item.execution_id for item in plan}
    classifications = classifications_of(records)

    ledger = GroundTruthLedger(ledger_path)
    ledger.initialise()
    try:
        applied = ledger.applied_mutations()
        duplicate_groups = ledger.duplicate_groups()
    finally:
        ledger.close()

    effects_by_execution: Counter[str] = Counter()
    first_deliveries: Counter[str] = Counter()
    unattributed = 0
    for row in applied:
        execution_id = execution_by_target.get(row.target)
        if execution_id is None:
            unattributed += 1
            continue
        effects_by_execution[execution_id] += 1
        if row.delivery_index == 1:
            first_deliveries[execution_id] += 1

    status_counts = Counter(
        classifications.get(item.execution_id, NO_INTENT) for item in plan
    )

    disagreements: list[ExecutionDisagreement] = []
    for item in plan:
        status = classifications.get(item.execution_id, NO_INTENT)
        effects = effects_by_execution.get(item.execution_id, 0)
        if status == IntentStatus.FAILED_CONFIRMED.value and effects > 0:
            disagreements.append(
                ExecutionDisagreement(
                    execution_id=item.execution_id,
                    classification=status,
                    applied_effects=effects,
                    rule=(
                        "the protocol resolved FAILED_CONFIRMED -- a definitive "
                        "no-effect -- and the ledger records an effect"
                    ),
                )
            )
        elif status == IntentStatus.FIRED_CONFIRMED.value and effects == 0:
            disagreements.append(
                ExecutionDisagreement(
                    execution_id=item.execution_id,
                    classification=status,
                    applied_effects=effects,
                    rule=(
                        "the protocol resolved FIRED_CONFIRMED and the ledger "
                        "records no effect"
                    ),
                )
            )
        elif status == NO_INTENT and effects > 0:
            disagreements.append(
                ExecutionDisagreement(
                    execution_id=item.execution_id,
                    classification=status,
                    applied_effects=effects,
                    rule=(
                        "an effect exists for an execution that never wrote a "
                        "durable intent; P2's write-ahead ordering was violated"
                    ),
                )
            )

    # Bounds the experiment side can state without reading the ledger.
    lower = status_counts.get(IntentStatus.FIRED_CONFIRMED.value, 0)
    certainly_no_effect = status_counts.get(
        IntentStatus.FAILED_CONFIRMED.value, 0
    ) + status_counts.get(NO_INTENT, 0)
    upper = len(plan) - certainly_no_effect

    caller_redispatch = sum(
        max(count - 1, 0) for count in first_deliveries.values()
    )
    total_duplicate_applications = sum(
        group.duplicate_applications for group in duplicate_groups
    )
    provider_internal = total_duplicate_applications - caller_redispatch

    # The roadmap's headline metric: duplicates the system did not flag. An
    # execution is "flagged" if it ended in a declared-ambiguous state, which
    # is AEP's way of saying "an operator must look at this".
    undetected = 0
    for execution_id, effects in effects_by_execution.items():
        if effects <= 1:
            continue
        status = classifications.get(execution_id, NO_INTENT)
        if status not in AMBIGUOUS_STATUSES:
            undetected += effects - 1

    return ReconciliationReport(
        run_id=config.run_id,
        config_digest=config.config_digest,
        executions_planned=len(plan),
        classifications=dict(status_counts),
        oracle_applied_rows=len(applied),
        oracle_effect_executions=len(effects_by_execution),
        oracle_unattributed_rows=unattributed,
        expected_effect_executions_lower=lower,
        expected_effect_executions_upper=upper,
        oracle_duplicate_groups=len(duplicate_groups),
        expected_duplicate_groups=_expected_duplicate_groups(mock_api_echo),
        caller_redispatch_duplicate_applications=caller_redispatch,
        provider_internal_duplicate_applications=provider_internal,
        undetected_duplicate_applications=undetected,
        disagreements=tuple(disagreements),
    )


def poisoned_detection_latencies(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Wall-clock latency from poisoning an execution to detecting it.

    Retires ``reports/phase-report-1b-2026-08-05.md`` F7 by measuring the thing
    that report said nothing consumed: the ``scan_failure_alert`` stream.
    """
    poisoned = {
        record["execution_id"]: record["wall_ms"]
        for record in events_of(records, "execution_poisoned")
    }
    seen: set[str] = set()
    latencies: list[dict[str, Any]] = []
    for alert in events_of(records, "scan_failure_alert"):
        execution_id = alert["execution_id"]
        if execution_id not in poisoned or execution_id in seen:
            continue
        seen.add(execution_id)
        latencies.append(
            {
                "execution_id": execution_id,
                "poisoned_at_ms": poisoned[execution_id],
                "detected_at_ms": alert["wall_ms"],
                "detection_latency_ms": alert["wall_ms"] - poisoned[execution_id],
                "failure_class": alert["failure_class"],
                "phase": alert["phase"],
            }
        )
    return latencies


def write_summary(
    directory: Path | str, report: ReconciliationReport, **extra: Any
) -> Path:
    """Write ``summary.json`` beside the run log."""
    path = Path(directory) / "summary.json"
    path.write_text(
        json.dumps({**report.echo(), **extra}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path
