"""B0 must do what its label says, and nothing more.

PAPER_ROADMAP.md section 3.3: *"B0: Naive retry -- No lease, no CAS,
retry-on-timeout (what most agent frameworks do today)."* The Session 3
amendment D1 asks for a test proving exactly that, in those words: *"B0
demonstrably retries on timeout without any intent record."*

Every assertion below is about something observable outside the runner -- what
reached the wire, and what is in Redis afterwards -- because a baseline that
merely *reported* having retried would not have generated the duplicate the
evaluation exists to count.
"""

from __future__ import annotations

import json

import pytest

from aep_core.core.intent_workflow import ConnectorPolicy

from experiments.baselines.b0_naive_retry import NaiveRetryRunner, classify
from experiments.baselines.contract import OutcomeClass, SystemId
from experiments.baselines.tests.conftest import (
    RecordingConnector,
    ambiguous,
    applied,
    refused,
)
from experiments.harness.workload import harness_profile, request_for
from experiments.mock_api.fingerprint import mutation_fingerprint

from experiments.baselines.tests.helpers import EXECUTION_ID, item_for

POLICY = ConnectorPolicy(client_timeout_seconds=1.0, lock_ttl_seconds=20)


def build(redis_client, connector, **kwargs) -> NaiveRetryRunner:
    return NaiveRetryRunner(
        redis_client=redis_client,
        connector=connector,
        profile=harness_profile(),
        policy=POLICY,
        **kwargs,
    )


async def test_retries_on_timeout(redis_client) -> None:
    """The defining behaviour: an ambiguous answer is answered with a resend."""
    connector = RecordingConnector(script=[ambiguous(), ambiguous(), applied()])
    runner = build(redis_client, connector, max_attempts=3)
    item = item_for()

    outcome = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert len(connector.transmissions) == 3, (
        "B0 is the retry baseline: two ambiguous answers must produce two "
        "further transmissions, because that is the mechanism by which a "
        "naive caller duplicates a non-idempotent effect"
    )
    assert outcome.dispatch_attempts == 3
    assert outcome.outcome_class is OutcomeClass.CONFIRMED_APPLIED


async def test_every_retry_carries_the_identical_mutation(redis_client) -> None:
    """The resends are the *same mutation*, or the oracle would not count them.

    Definition 1 fingerprints the mutation, not the attempt. If B0's retries
    differed in an identity field the ground-truth ledger would see two
    distinct mutations and report a duplicate rate of zero for a system that
    duplicates on every attempt.
    """
    connector = RecordingConnector(script=[ambiguous(), ambiguous(), applied()])
    runner = build(redis_client, connector, max_attempts=3)
    item = item_for()

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    fingerprints = {
        mutation_fingerprint(
            method="POST",
            endpoint="payments",
            envelope=json.loads(sent.exact_request_bytes),
            identity_fields=("action", "amount_minor"),
        )
        for sent in connector.transmissions
    }
    assert len(fingerprints) == 1


async def test_writes_no_intent_record(redis_client) -> None:
    """"...without any intent record." Asserted against Redis, not the runner."""
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, connector)
    item = item_for()

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert await redis_client.exists(f"aep:state:{item.execution_id}") == 0
    assert (
        await redis_client.exists(f"aep:dispatch-auth:{item.execution_id}") == 0
    )


async def test_takes_no_lease(redis_client) -> None:
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, connector)
    item = item_for()

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert await redis_client.exists(f"aep:lock:{item.execution_id}") == 0


async def test_sends_no_client_reference(redis_client) -> None:
    """A caller with no pre-dispatch record has no stable identifier to send."""
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, connector)
    item = item_for()

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert [sent.client_reference for sent in connector.transmissions] == [None]


async def test_exhausted_retries_are_an_unverified_failure(redis_client) -> None:
    """The distinction the whole paper turns on.

    B0 gives up and writes "failed". It has no evidence that nothing was
    applied -- every attempt may have applied -- so the record is a guess. It
    must never be reported as a declared ambiguity, because B0 has no way to
    declare one and an operator reading its record cannot tell the difference.
    """
    connector = RecordingConnector(script=[ambiguous()])
    runner = build(redis_client, connector, max_attempts=3)
    item = item_for()

    outcome = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert len(connector.transmissions) == 3
    assert outcome.outcome_class is OutcomeClass.UNVERIFIED_FAILURE
    assert outcome.outcome_class is not OutcomeClass.DECLARED_AMBIGUOUS


async def test_a_refusal_is_definitive_and_is_not_retried(redis_client) -> None:
    """A 4xx is evidence of no effect. Retrying it would be a different bug."""
    connector = RecordingConnector(script=[refused()])
    runner = build(redis_client, connector, max_attempts=3)
    item = item_for()

    outcome = await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )

    assert len(connector.transmissions) == 1
    assert outcome.outcome_class is OutcomeClass.CONFIRMED_NOT_APPLIED


async def test_the_only_durable_record_is_written_after_the_call(
    redis_client,
) -> None:
    """Nothing exists before the call; the outcome record exists after it.

    This is the property that makes a crashed B0 execution unattributable from
    Redis alone -- and the reason the harness attributes effects by target
    instead.
    """
    seen: list[int] = []
    connector = RecordingConnector(script=[applied()])
    item = item_for()

    async def probe_before_transmission(index: int) -> None:  # pragma: no cover
        raise AssertionError

    def record(index: int) -> None:
        seen.append(index)

    connector.on_transmit = record
    runner = build(redis_client, connector)

    assert await redis_client.exists(f"aep:b0:result:{item.execution_id}") == 0
    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )
    assert seen == [0]
    assert await redis_client.exists(f"aep:b0:result:{item.execution_id}") == 1


async def test_classify_reads_the_systems_own_record(redis_client) -> None:
    connector = RecordingConnector(script=[applied()])
    runner = build(redis_client, connector)
    item = item_for()

    unknown = await classify(redis_client, EXECUTION_ID)
    assert unknown.outcome_class is OutcomeClass.NO_RECORD
    assert unknown.system is SystemId.B0_NAIVE_RETRY

    await runner.execute(
        execution_id=item.execution_id, step_id=item.step_id, request=request_for(item)
    )
    known = await classify(redis_client, item.execution_id)
    assert known.outcome_class is OutcomeClass.CONFIRMED_APPLIED
    assert known.dispatch_attempts == 1


async def test_a_corrupt_record_is_unreadable_not_absent(redis_client) -> None:
    await redis_client.set(f"aep:b0:result:{EXECUTION_ID}", "{not json")
    outcome = await classify(redis_client, EXECUTION_ID)
    assert outcome.outcome_class is OutcomeClass.UNREADABLE


async def test_max_attempts_must_be_positive(redis_client) -> None:
    with pytest.raises(ValueError):
        build(redis_client, RecordingConnector(), max_attempts=0)
