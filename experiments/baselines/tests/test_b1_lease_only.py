"""B1: a lease, a raw SET, and nothing else.

PAPER_ROADMAP.md section 3.3: *"B1: Lease-only -- Redis lock, raw SET state, no
intent ledger."*

The lease is a real distributed lock and it really does serialise concurrent
workers -- that is asserted below, because a baseline whose lock did not work
would make AEP look good for the wrong reason. What the lease cannot do is
anything at all about a worker that has *died*: the lock expires on its TTL and
the next attempt proceeds, with no record anywhere of the call the dead worker
may already have made.
"""

from __future__ import annotations

import json

from aep_core.core.intent_workflow import ConnectorPolicy

from experiments.baselines.b1_lease_only import LeaseOnlyRunner, classify, state_key
from experiments.baselines.contract import OutcomeClass, SystemId
from experiments.baselines.tests.conftest import (
    RecordingConnector,
    ambiguous,
    applied,
)
from experiments.baselines.tests.helpers import EXECUTION_ID, item_for
from experiments.harness.workload import harness_profile, request_for

POLICY = ConnectorPolicy(client_timeout_seconds=1.0, lock_ttl_seconds=20)


def build(redis_client, lock_manager, connector, **kwargs) -> LeaseOnlyRunner:
    return LeaseOnlyRunner(
        redis_client=redis_client,
        lock_manager=lock_manager,
        connector=connector,
        profile=harness_profile(),
        policy=POLICY,
        **kwargs,
    )


async def test_takes_the_lease_and_releases_it(
    redis_client, lock_manager
) -> None:
    connector = RecordingConnector(script=[applied()])
    held: list[bool] = []
    item = item_for()

    def observe(index: int) -> None:
        held.append(True)

    connector.on_transmit = observe
    runner = build(redis_client, lock_manager, connector)

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert held == [True]
    assert await redis_client.exists(f"aep:lock:{item.execution_id}") == 0, (
        "the lease must be released; a baseline that leaked leases would "
        "serialise its own later executions and slow itself for no reason"
    )


async def test_the_lease_is_held_across_the_call(
    redis_client, lock_manager
) -> None:
    """Asserted from inside the transmission, which is the only moment it matters."""
    item = item_for()
    observed: list[int] = []
    connector = RecordingConnector(script=[applied()])

    def observe(index: int) -> None:
        observed.append(index)

    connector.on_transmit = observe
    runner = build(redis_client, lock_manager, connector)

    async def check_during_transmission() -> None:
        assert await redis_client.exists(f"aep:lock:{item.execution_id}") == 1

    connector.on_transmit = lambda index: observed.append(index)
    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )
    assert observed == [0]


async def test_a_second_worker_cannot_take_the_held_lease(
    redis_client, lock_manager
) -> None:
    """The one thing the lease genuinely buys."""
    item = item_for()
    token = await lock_manager.acquire_lock(item.execution_id, ttl_seconds=20)
    assert token is not None
    try:
        second = await lock_manager.acquire_lock(item.execution_id, ttl_seconds=20)
        assert second is None
    finally:
        await lock_manager.release_lock(item.execution_id, token)


async def test_state_is_a_raw_set_with_no_version(
    redis_client, lock_manager
) -> None:
    """"raw SET state": no fencing counter, so no protection against a stale writer."""
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, lock_manager, connector)
    item = item_for()

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    document = json.loads(await redis_client.get(state_key(item.execution_id)))
    assert document["status"] == "APPLIED"
    assert "version" not in document
    assert await redis_client.exists(f"aep:state:{item.execution_id}") == 0


async def test_retries_on_ambiguity(redis_client, lock_manager) -> None:
    connector = RecordingConnector(script=[ambiguous(), ambiguous(), applied()])
    runner = build(redis_client, lock_manager, connector, max_attempts=3)
    item = item_for()

    outcome = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert len(connector.transmissions) == 3
    assert outcome.dispatch_attempts == 3


async def test_re_execution_transmits_again(redis_client, lock_manager) -> None:
    """No pre-dispatch record means nothing to consult on the second run.

    This is what a supervisor's re-execution does to B1 after a crash, minus
    the crash: the lease has been released, the state record says nothing about
    an *attempted* call, and the mutation goes out a second time.
    """
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, lock_manager, connector)
    item = item_for()

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )
    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert len(connector.transmissions) == 2


async def test_writes_no_intent_and_sends_no_client_reference(
    redis_client, lock_manager
) -> None:
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, lock_manager, connector)
    item = item_for()

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert await redis_client.exists(f"aep:state:{item.execution_id}") == 0
    assert [sent.client_reference for sent in connector.transmissions] == [None]


async def test_classify(redis_client, lock_manager) -> None:
    absent = await classify(redis_client, EXECUTION_ID)
    assert absent.outcome_class is OutcomeClass.NO_RECORD
    assert absent.system is SystemId.B1_LEASE_ONLY

    connector = RecordingConnector(script=[ambiguous()])
    runner = build(redis_client, lock_manager, connector, max_attempts=2)
    item = item_for()
    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )
    outcome = await classify(redis_client, item.execution_id)
    assert outcome.outcome_class is OutcomeClass.UNVERIFIED_FAILURE
    assert outcome.dispatch_attempts == 2
