"""Map an intent status onto the vocabulary the metrics share.

B3 and AEP-full both keep their record in the intent ledger, so both classify
the same way, and both do it here. The mapping is short and every line of it is
a claim the paper makes:

``FIRED_CONFIRMED`` / ``FAILED_CONFIRMED``
    The protocol has evidence and asserts an outcome. Reconciliation is
    entitled to contradict either, and does -- a ``FAILED_CONFIRMED`` execution
    that applied an effect is the protocol lying, which is the single strongest
    check in the harness.

``PERMANENTLY_AMBIGUOUS`` / ``FIRED_UNCONFIRMED`` / ``ABOUT_TO_FIRE``
    The protocol declares that it does not know. This is the class no baseline
    outside B3 and AEP-full can produce, and the one the headline duplicate
    metric treats as "flagged": an operator reading any of the three knows the
    outcome is unresolved and knows to look.

``NO_INTENT``
    Nothing was ever written. For a system that promises a write-ahead record
    this also means no provider bytes can exist, which ``reconcile.py`` checks.

``UNREADABLE:*``
    The record exists and could not be read. Deliberately distinct from
    absence: merging the two would move counts between the lost-effect and
    state-corruption metrics.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from aep_core.core.intents import IntentStatus

from experiments.baselines.contract import (
    ExecutionOutcome,
    OutcomeClass,
    SystemId,
)

#: Recorded by the runner when an execution never reached a durable intent.
#: Same literal ``experiments/harness/reconcile.py`` uses.
NO_INTENT = "NO_INTENT"

#: Prefix the runner writes when reading an execution's state raised.
UNREADABLE_PREFIX = "UNREADABLE:"

INTENT_STATUS_CLASSES: Mapping[str, OutcomeClass] = MappingProxyType(
    {
        IntentStatus.FIRED_CONFIRMED.value: OutcomeClass.CONFIRMED_APPLIED,
        IntentStatus.FAILED_CONFIRMED.value: OutcomeClass.CONFIRMED_NOT_APPLIED,
        IntentStatus.PERMANENTLY_AMBIGUOUS.value: OutcomeClass.DECLARED_AMBIGUOUS,
        IntentStatus.FIRED_UNCONFIRMED.value: OutcomeClass.DECLARED_AMBIGUOUS,
        IntentStatus.ABOUT_TO_FIRE.value: OutcomeClass.DECLARED_AMBIGUOUS,
        NO_INTENT: OutcomeClass.NO_RECORD,
    }
)


def classify_intent_state(
    status: str,
    *,
    system: SystemId = SystemId.AEP_FULL,
    execution_id: str = "",
    dispatch_attempts: int = 0,
    intent_id: str | None = None,
) -> ExecutionOutcome:
    """Turn one recorded intent status into a shared-vocabulary outcome.

    An unrecognised status is ``UNREADABLE`` rather than anything friendlier:
    a status this module has never heard of is a status whose guarantees it
    cannot vouch for, and silently treating it as ambiguous would credit the
    protocol with a declaration it may not have made.
    """
    if status.startswith(UNREADABLE_PREFIX):
        return ExecutionOutcome(
            system=system,
            execution_id=execution_id,
            status=status,
            outcome_class=OutcomeClass.UNREADABLE,
            dispatch_attempts=dispatch_attempts,
            intent_id=intent_id,
        )
    return ExecutionOutcome(
        system=system,
        execution_id=execution_id,
        status=status,
        outcome_class=INTENT_STATUS_CLASSES.get(status, OutcomeClass.UNREADABLE),
        dispatch_attempts=dispatch_attempts,
        intent_id=intent_id,
    )
