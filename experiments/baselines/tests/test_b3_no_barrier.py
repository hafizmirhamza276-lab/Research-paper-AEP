"""B3: the complete protocol with WAITAOF removed, and nothing else removed.

PAPER_ROADMAP.md section 3.3: *"B3: Intent w/o durability barrier -- Full
protocol minus WAITAOF (ablation isolating the barrier's value)."*

An ablation is only an ablation if exactly one thing changed. The tests below
are mostly about what did *not* change: B3 still writes the intent, still
fences it, still mints a dispatch authorisation, still dispatches at most once,
and still runs a recovery service. The single difference is that
``confirm_durable`` returns ``True`` without asking Redis to fsync -- asserted
by watching the commands that reach the connection, because a barrier that
merely *claimed* not to wait would leave the ablation unperformed.

``validate_startup`` is deliberately **not** ablated. It runs the same
capability checks as the real barrier, so B3 still refuses a server without AOF
or without WAITAOF support. Removing those too would ablate the durability
*configuration* as well as the barrier, and the resulting difference could not
be attributed to either.
"""

from __future__ import annotations

import pytest

from aep_core.core.durability import (
    DurabilityCapabilityError,
    RealWaitAofDurabilityBarrier,
)
from aep_core.core.intents import IntentStatus

from experiments.baselines.b3_no_barrier import NoBarrierDurabilityBarrier
from experiments.baselines.contract import OutcomeClass, SystemId
from experiments.baselines.intent_classifier import classify_intent_state
from experiments.baselines.tests.helpers import EXECUTION_ID


class RecordingConnection:
    """Wraps a Redis connection and remembers every command issued."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.commands: list[tuple] = []

    async def execute_command(self, *args, **kwargs):
        self.commands.append(tuple(str(part).upper() for part in args[:1]))
        return await self.inner.execute_command(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.inner, name)


async def _validated_barrier(redis_client) -> NoBarrierDurabilityBarrier:
    """A validated ablated barrier, or a skip.

    ``validate_startup`` is deliberately *not* ablated (see the module
    docstring), so it needs a server that can prove ``WAITAOF`` support --
    which fakeredis cannot. CI runs the whole suite against the compose Redis,
    where nothing here skips and the zero-skip gate stays meaningful.
    """
    barrier = NoBarrierDurabilityBarrier()
    try:
        await barrier.validate_startup(redis_client)
    except DurabilityCapabilityError:
        pytest.skip("this Redis cannot prove WAITAOF support")
    return barrier


async def test_confirm_durable_issues_no_waitaof(redis_client) -> None:
    """The ablation itself, observed on the wire."""
    barrier = await _validated_barrier(redis_client)

    connection = RecordingConnection(redis_client)
    durable = await barrier.confirm_durable(connection, 2000)

    assert durable is True
    assert connection.commands == [], (
        "B3's barrier must issue no command at all: the ablation is the "
        "absence of the WAITAOF round trip, not a faster version of it"
    )


async def test_the_real_barrier_does_issue_waitaof(redis_client) -> None:
    """The control for the assertion above. Without it the test proves nothing."""
    barrier = RealWaitAofDurabilityBarrier()
    try:
        await barrier.validate_startup(redis_client)
    except DurabilityCapabilityError:
        pytest.skip("this Redis cannot prove WAITAOF support")

    connection = RecordingConnection(redis_client)
    async with redis_client.client() as pinned:
        connection = RecordingConnection(pinned)
        await barrier.confirm_durable(connection, 2000)

    assert ("WAITAOF",) in connection.commands


async def test_is_not_a_test_only_barrier(redis_client) -> None:
    """EVALUATION mode must accept it, or B3 could not be run at all.

    ``WriteAheadRunner.validate_startup`` refuses a barrier declaring
    ``test_only``. B3 is a research ablation running against real Redis with
    a real connector, not a test double, and it says so.
    """
    assert NoBarrierDurabilityBarrier.test_only is False
    assert hasattr(NoBarrierDurabilityBarrier(), "validate_startup")


async def test_validate_startup_is_not_ablated(redis_client) -> None:
    """The capability checks are the real ones; only the per-call wait is gone."""
    barrier = await _validated_barrier(redis_client)
    capabilities = await barrier.validate_startup(redis_client)
    assert capabilities.aof_enabled is True

    unvalidated = NoBarrierDurabilityBarrier()
    with pytest.raises(DurabilityCapabilityError):
        await unvalidated.confirm_durable(redis_client, 2000)


def test_intent_statuses_map_onto_the_shared_vocabulary() -> None:
    """The mapping the metrics depend on, stated once and asserted here.

    ``FIRED_UNCONFIRMED`` and ``ABOUT_TO_FIRE`` are declared ambiguities, not
    failures: an operator reading either knows the outcome is unresolved. That
    is the property no baseline outside B3/AEP-full can express.
    """
    assert (
        classify_intent_state(IntentStatus.FIRED_CONFIRMED.value).outcome_class
        is OutcomeClass.CONFIRMED_APPLIED
    )
    assert (
        classify_intent_state(IntentStatus.FAILED_CONFIRMED.value).outcome_class
        is OutcomeClass.CONFIRMED_NOT_APPLIED
    )
    for ambiguous_status in (
        IntentStatus.PERMANENTLY_AMBIGUOUS,
        IntentStatus.FIRED_UNCONFIRMED,
        IntentStatus.ABOUT_TO_FIRE,
    ):
        assert (
            classify_intent_state(ambiguous_status.value).outcome_class
            is OutcomeClass.DECLARED_AMBIGUOUS
        ), ambiguous_status

    assert (
        classify_intent_state("NO_INTENT").outcome_class is OutcomeClass.NO_RECORD
    )
    assert (
        classify_intent_state("UNREADABLE:StateCorruptionError").outcome_class
        is OutcomeClass.UNREADABLE
    )


def test_the_classifier_names_the_system_it_was_asked_about() -> None:
    outcome = classify_intent_state(
        IntentStatus.FIRED_CONFIRMED.value,
        system=SystemId.B3_INTENT_NO_BARRIER,
        execution_id=EXECUTION_ID,
    )
    assert outcome.system is SystemId.B3_INTENT_NO_BARRIER
    assert outcome.execution_id == EXECUTION_ID
