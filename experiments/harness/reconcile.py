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
long enough to resolve, and three of the six systems never send one at all.

**What "agreement" means, and why it depends on the system.** The run log knows
what the system *decided*; the ledger knows what the world *did*; neither can
see the other. Some of the statements that must hold between them are true of
any system, and some are true only of a system that promised something:

1. Every applied mutation is attributable to a planned execution. An effect the
   experiment cannot account for invalidates the run, whichever system produced
   it.
2. A system that asserted ``CONFIRMED_NOT_APPLIED`` -- a definitive no-effect,
   on evidence -- applied nothing. The strongest single check here: a
   definitive claim contradicted by the ledger is the system lying.
3. A system that asserted ``CONFIRMED_APPLIED`` applied at least one effect.
4. **Only for a system that writes a durable record before dispatching:** no
   effect exists for an execution with no record at all. For AEP-full and B3
   that is P2's write-ahead ordering and a violation is a defect. For B0, B1,
   B2 it is not a violation of anything -- they never promised it -- it is a
   *lost effect*, and it is counted as one instead.
5. The number of resources that changed lies between the count the system is
   certain about and the count it could not rule out.
6. **Only for a system that dispatches at most once:** the ledger reports no
   more duplicate groups than the provider's own configuration predicts. A
   retrying baseline duplicates by design; reporting that as a reconciliation
   failure would make every baseline run look broken.

Executions in a *declared-ambiguous* state may have applied zero or one effect.
That freedom is the point: the protocol converts a silent guess into a declared
unknown, and the ledger is allowed to disagree with an uncertainty the system
never claimed to resolve.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.baselines.contract import (
    FLAGGED_CLASSES,
    OutcomeClass,
    SystemDescriptor,
    descriptor_for,
)
from experiments.baselines.intent_classifier import NO_INTENT  # noqa: F401
from experiments.harness.config import run_config_from_mapping
from experiments.harness.events import events_of, read_events
from experiments.harness.workload import plan_workload
from experiments.mock_api.ledger import GroundTruthLedger

#: Outcome classes in which the system asserts something the ledger may
#: contradict.
ASSERTED_APPLIED = OutcomeClass.CONFIRMED_APPLIED
ASSERTED_NOT_APPLIED = OutcomeClass.CONFIRMED_NOT_APPLIED


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
    system: str
    executions_planned: int
    classifications: Mapping[str, int]
    outcome_classes: Mapping[str, int]
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
    undetected_duplicate_executions: int
    lost_effect_executions: int
    unverified_failure_executions: int
    declared_ambiguous_executions: int
    unreadable_executions: int
    duplicate_prediction_applies: bool
    disagreements: tuple[ExecutionDisagreement, ...] = field(default=())

    @property
    def agrees(self) -> bool:
        duplicates_agree = (
            not self.duplicate_prediction_applies
            or self.oracle_duplicate_groups == self.expected_duplicate_groups
        )
        return (
            not self.disagreements
            and self.oracle_unattributed_rows == 0
            and duplicates_agree
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
            "system": self.system,
            "agrees": self.agrees,
            "executions_planned": self.executions_planned,
            "classifications": dict(sorted(self.classifications.items())),
            "outcome_classes": dict(sorted(self.outcome_classes.items())),
            "oracle_applied_rows": self.oracle_applied_rows,
            "oracle_effect_executions": self.oracle_effect_executions,
            "oracle_unattributed_rows": self.oracle_unattributed_rows,
            "expected_effect_executions_lower": self.expected_effect_executions_lower,
            "expected_effect_executions_upper": self.expected_effect_executions_upper,
            "oracle_duplicate_groups": self.oracle_duplicate_groups,
            "expected_duplicate_groups": self.expected_duplicate_groups,
            "duplicate_prediction_applies": self.duplicate_prediction_applies,
            "caller_redispatch_duplicate_applications": (
                self.caller_redispatch_duplicate_applications
            ),
            "provider_internal_duplicate_applications": (
                self.provider_internal_duplicate_applications
            ),
            "undetected_duplicate_applications": (
                self.undetected_duplicate_applications
            ),
            "undetected_duplicate_executions": self.undetected_duplicate_executions,
            "lost_effect_executions": self.lost_effect_executions,
            "unverified_failure_executions": self.unverified_failure_executions,
            "declared_ambiguous_executions": self.declared_ambiguous_executions,
            "unreadable_executions": self.unreadable_executions,
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
    """The final status of each execution, in the system's own vocabulary."""
    return {
        record["execution_id"]: record["status"]
        for record in events_of(records, "final_classification")
    }


def outcome_classes_of(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, OutcomeClass]:
    """The final outcome class of each execution, in the shared vocabulary."""
    classes: dict[str, OutcomeClass] = {}
    for record in events_of(records, "final_classification"):
        raw = record.get("outcome_class")
        if raw is None:
            raise ValueError(
                "a final_classification record carries no outcome_class; the "
                "run log predates the multi-system harness and its numbers "
                "cannot be compared with runs that do"
            )
        classes[record["execution_id"]] = OutcomeClass(raw)
    return classes


def _expected_duplicate_groups(
    mock_api_echo: Mapping[str, Any], descriptor: SystemDescriptor
) -> tuple[int, bool]:
    """What the experiment side predicts before looking at the ledger.

    Returns ``(prediction, applies)``. The prediction is only meaningful for a
    system that dispatches at most once and therefore contributes no duplicate
    of its own; for a retrying system the caller's contribution is a random
    variable of the fault stream and no prediction is possible. Even for an
    at-most-once system the provider may duplicate internally, and with a
    non-zero probability that count is also random -- reported as ``-1``.
    """
    if not descriptor.dispatches_at_most_once:
        return -1, False
    endpoints = mock_api_echo.get("endpoints", {})
    probabilities = [
        endpoint.get("faults", {}).get("duplicate_response_probability", 0.0)
        for endpoint in endpoints.values()
    ]
    if any(probability > 0 for probability in probabilities):
        return -1, False
    return 0, True


def reconcile(
    events_path: Path | str, ledger_path: Path | str
) -> ReconciliationReport:
    """Compare one run's log with the ground truth it was collected against."""
    records = read_events(events_path)
    config = run_configuration_of(records)
    descriptor = descriptor_for(config.system)
    mock_api_echo = mock_api_echo_of(records)
    plan = plan_workload(config)
    execution_by_target = {item.target: item.execution_id for item in plan}
    statuses = classifications_of(records)
    classes = outcome_classes_of(records)

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
        statuses.get(item.execution_id, "NO_RECORD") for item in plan
    )
    class_counts: Counter[str] = Counter(
        classes.get(item.execution_id, OutcomeClass.NO_RECORD).value for item in plan
    )

    disagreements: list[ExecutionDisagreement] = []
    lost_effects = 0
    undetected_applications = 0
    undetected_executions = 0

    for item in plan:
        outcome = classes.get(item.execution_id, OutcomeClass.NO_RECORD)
        status = statuses.get(item.execution_id, "NO_RECORD")
        effects = effects_by_execution.get(item.execution_id, 0)

        if outcome is ASSERTED_NOT_APPLIED and effects > 0:
            disagreements.append(
                ExecutionDisagreement(
                    execution_id=item.execution_id,
                    classification=status,
                    applied_effects=effects,
                    rule=(
                        "the system asserted a definitive no-effect and the "
                        "ledger records an effect"
                    ),
                )
            )
        elif outcome is ASSERTED_APPLIED and effects == 0:
            disagreements.append(
                ExecutionDisagreement(
                    execution_id=item.execution_id,
                    classification=status,
                    applied_effects=effects,
                    rule=(
                        "the system asserted the effect was applied and the "
                        "ledger records none"
                    ),
                )
            )
        elif (
            outcome is OutcomeClass.NO_RECORD
            and effects > 0
            and descriptor.writes_pre_dispatch_record
        ):
            disagreements.append(
                ExecutionDisagreement(
                    execution_id=item.execution_id,
                    classification=status,
                    applied_effects=effects,
                    rule=(
                        "an effect exists for an execution that never wrote a "
                        "durable pre-dispatch record; P2's write-ahead "
                        "ordering was violated"
                    ),
                )
            )

        # The world changed and the system neither says so nor flags it. For a
        # system with no write-ahead record this is the expected outcome of a
        # crash, not a defect -- which is exactly why it is measured.
        if effects > 0 and outcome is not ASSERTED_APPLIED and outcome not in FLAGGED_CLASSES:
            lost_effects += 1

        if effects > 1 and outcome not in FLAGGED_CLASSES:
            undetected_applications += effects - 1
            undetected_executions += 1

    # Bounds the experiment side can state without reading the ledger.
    lower = class_counts.get(ASSERTED_APPLIED.value, 0)
    certainly_no_effect = class_counts.get(ASSERTED_NOT_APPLIED.value, 0)
    if descriptor.writes_pre_dispatch_record:
        # No record and a write-ahead promise together mean no bytes were sent.
        certainly_no_effect += class_counts.get(OutcomeClass.NO_RECORD.value, 0)
    upper = len(plan) - certainly_no_effect

    caller_redispatch = sum(max(count - 1, 0) for count in first_deliveries.values())
    total_duplicate_applications = sum(
        group.duplicate_applications for group in duplicate_groups
    )
    provider_internal = total_duplicate_applications - caller_redispatch

    predicted, prediction_applies = _expected_duplicate_groups(
        mock_api_echo, descriptor
    )

    return ReconciliationReport(
        run_id=config.run_id,
        config_digest=config.config_digest,
        system=config.system.value,
        executions_planned=len(plan),
        classifications=dict(status_counts),
        outcome_classes=dict(class_counts),
        oracle_applied_rows=len(applied),
        oracle_effect_executions=len(effects_by_execution),
        oracle_unattributed_rows=unattributed,
        expected_effect_executions_lower=lower,
        expected_effect_executions_upper=upper,
        oracle_duplicate_groups=len(duplicate_groups),
        expected_duplicate_groups=predicted,
        duplicate_prediction_applies=prediction_applies,
        caller_redispatch_duplicate_applications=caller_redispatch,
        provider_internal_duplicate_applications=provider_internal,
        undetected_duplicate_applications=undetected_applications,
        undetected_duplicate_executions=undetected_executions,
        lost_effect_executions=lost_effects,
        unverified_failure_executions=class_counts.get(
            OutcomeClass.UNVERIFIED_FAILURE.value, 0
        ),
        declared_ambiguous_executions=class_counts.get(
            OutcomeClass.DECLARED_AMBIGUOUS.value, 0
        ),
        unreadable_executions=class_counts.get(OutcomeClass.UNREADABLE.value, 0),
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
