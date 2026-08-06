"""B4: durable-workflow style, and why a write-ahead record is not enough.

PAPER_ROADMAP.md section 3.3: *"B4: Durable-workflow style -- A minimal
Temporal-like event-sourced re-execution baseline."*

B4 is the strongest baseline and the most instructive one. It has everything
AEP's critics assume is sufficient: an append-only history, durably
acknowledged by the same WAITAOF barrier AEP-full uses, replayed from the
beginning after a crash, with completed activities memoised so they are not
re-run. Its state is never corrupted and its bookkeeping is never lost.

It still duplicates, and the tests below pin exactly where. When replay finds
an activity *scheduled and not completed* -- the state a crash between
transmission and response leaves -- a durable-execution engine's semantics are
at-least-once for activities: it runs the activity again. The record exists;
the policy applied to it is "retry", not "this outcome is unknown, stop and
escalate". That single difference is the paper's contribution, and B4 is what
makes it visible rather than asserted.
"""

from __future__ import annotations

from aep_core.core.intent_workflow import ConnectorPolicy

from experiments.baselines.b4_durable_workflow import (
    ACTIVITY_COMPLETED,
    ACTIVITY_SCHEDULED,
    DurableWorkflowRunner,
    classify,
    history_key,
    read_history,
)
from experiments.baselines.contract import OutcomeClass, SystemId
from experiments.baselines.tests.conftest import (
    RecordingConnector,
    ambiguous,
    applied,
)
from experiments.baselines.tests.helpers import EXECUTION_ID, item_for
from experiments.harness.workload import harness_profile, request_for

POLICY = ConnectorPolicy(client_timeout_seconds=1.0, lock_ttl_seconds=20)


class CountingBarrier:
    """A barrier that records how many times it acknowledged."""

    test_only = False

    def __init__(self) -> None:
        self.acknowledgements = 0

    async def validate_startup(self, redis_client):
        return None

    async def confirm_durable(self, connection, timeout_ms: int) -> bool:
        self.acknowledgements += 1
        return True


def build(redis_client, lock_manager, connector, barrier=None, **kwargs):
    return DurableWorkflowRunner(
        redis_client=redis_client,
        lock_manager=lock_manager,
        connector=connector,
        profile=harness_profile(),
        policy=POLICY,
        barrier=barrier or CountingBarrier(),
        **kwargs,
    )


async def test_history_records_the_activity_before_it_is_run(
    redis_client, lock_manager
) -> None:
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, lock_manager, connector)
    item = item_for()

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    events = [entry["event"] for entry in await read_history(redis_client, item.execution_id)]
    assert events == [ACTIVITY_SCHEDULED, ACTIVITY_COMPLETED]


async def test_the_history_is_acknowledged_durable(
    redis_client, lock_manager
) -> None:
    """B4 is not ablated on durability. Its ledger is as durable as AEP's."""
    barrier = CountingBarrier()
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, lock_manager, connector, barrier=barrier)
    item = item_for()

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert barrier.acknowledgements == 2, (
        "both the scheduled and the completed event must be acknowledged; a "
        "durable-execution engine that lost its history would be a different, "
        "weaker baseline"
    )


async def test_replay_after_completion_does_not_re_run_the_activity(
    redis_client, lock_manager
) -> None:
    """Memoisation works. This is what durable execution is *for*."""
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, lock_manager, connector)
    item = item_for()

    first = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )
    second = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert len(connector.transmissions) == 1
    assert first.outcome_class is OutcomeClass.CONFIRMED_APPLIED
    assert second.outcome_class is OutcomeClass.CONFIRMED_APPLIED
    assert second.dispatch_attempts == 0, "the replay transmitted nothing"


async def test_replay_of_a_scheduled_but_uncompleted_activity_re_runs_it(
    redis_client, lock_manager
) -> None:
    """The defining defect, reproduced deterministically.

    The history is left exactly as a crash between transmission and response
    leaves it: the activity is scheduled and not completed. Replay re-runs it.
    The provider has already applied the mutation once; it now applies it
    again, and B4's own record will end up saying COMPLETED with no indication
    that anything happened twice.
    """
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, lock_manager, connector)
    item = item_for()

    await runner._append(
        item.execution_id,
        {"event": ACTIVITY_SCHEDULED, "step_id": item.step_id, "attempt": 1},
    )

    outcome = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert len(connector.transmissions) == 1, (
        "a scheduled-but-uncompleted activity is re-run: that is at-least-once "
        "activity semantics and it is where the duplicate comes from"
    )
    assert outcome.outcome_class is OutcomeClass.CONFIRMED_APPLIED
    assert outcome.outcome_class is not OutcomeClass.DECLARED_AMBIGUOUS


async def test_b4_never_declares_ambiguity(redis_client, lock_manager) -> None:
    """Exhausted retries end as an unverified failure, exactly as B0's do."""
    connector = RecordingConnector(script=[ambiguous()])
    runner = build(redis_client, lock_manager, connector, max_attempts=2)
    item = item_for()

    outcome = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert len(connector.transmissions) == 2
    assert outcome.outcome_class is OutcomeClass.UNVERIFIED_FAILURE


async def test_classify_reads_the_history(redis_client, lock_manager) -> None:
    absent = await classify(redis_client, EXECUTION_ID)
    assert absent.outcome_class is OutcomeClass.NO_RECORD
    assert absent.system is SystemId.B4_DURABLE_WORKFLOW

    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, lock_manager, connector)
    item = item_for()
    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    outcome = await classify(redis_client, item.execution_id)
    assert outcome.outcome_class is OutcomeClass.CONFIRMED_APPLIED


async def test_a_scheduled_only_history_classifies_as_unverified(
    redis_client, lock_manager
) -> None:
    """What a crashed B4 execution leaves behind, if nobody replays it."""
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, lock_manager, connector)
    await runner._append(
        EXECUTION_ID, {"event": ACTIVITY_SCHEDULED, "step_id": "charge-card"}
    )

    outcome = await classify(redis_client, EXECUTION_ID)
    assert outcome.outcome_class is OutcomeClass.UNVERIFIED_FAILURE
    assert outcome.status == "SCHEDULED"


async def test_history_key_is_namespaced(redis_client) -> None:
    assert history_key(EXECUTION_ID).startswith("aep:b4:history:")
