"""B4b: the documented at-most-once configuration, and what it costs.

Amendment E4. ``B4_SEMANTICS.md`` cites Temporal's documentation for both ends
of the retry policy: Maximum Attempts defaults to unlimited, and setting it to
1 means "a single execution attempt and no retries". B4 is the first, B4b is
the second, and the pair is only an ablation of the retry policy if everything
else about them is identical.

What these tests pin is the *behaviour* the citation predicts, on the exact
history shape the crash under test produces: ``activity_scheduled`` recorded,
``activity_completed`` absent, worker gone. B4 sends the mutation again. B4b
does not, and records a timeout that no operator can distinguish from "nothing
happened" -- which is the whole reason running B4b makes the paper stronger
rather than weaker.
"""

from __future__ import annotations

import json

import pytest

from aep_core.core.intent_workflow import ConnectorPolicy

from experiments.baselines import b4_durable_workflow as b4
from experiments.baselines.common import STATUS_SCHEDULED, STATUS_TIMED_OUT
from experiments.baselines.contract import OutcomeClass, SystemId


class FakeRedis:
    """The three commands the history uses, and nothing else."""

    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}

    async def lrange(self, key, start, stop):
        return list(self.lists.get(key, []))

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    async def expire(self, key, seconds):
        return True

    def client(self):
        redis = self

        class _Pinned:
            async def __aenter__(self):
                return redis

            async def __aexit__(self, *_):
                return False

        return _Pinned()


def _scheduled_history(redis: FakeRedis, execution_id: str, attempts: int = 1) -> None:
    key = b4.history_key(execution_id)
    redis.lists[key] = [
        json.dumps(
            {"event": b4.ACTIVITY_SCHEDULED, "step_id": "s1", "attempt": n + 1},
            sort_keys=True,
        )
        for n in range(attempts)
    ]


@pytest.mark.asyncio
async def test_b4_classifies_a_scheduled_history_as_an_unverified_failure() -> None:
    redis = FakeRedis()
    _scheduled_history(redis, "e1")
    outcome = await b4.classify(redis, "e1")
    assert outcome.status == STATUS_SCHEDULED
    assert outcome.outcome_class is OutcomeClass.UNVERIFIED_FAILURE
    assert outcome.system is SystemId.B4_DURABLE_WORKFLOW


@pytest.mark.asyncio
async def test_b4b_results_are_never_attributed_to_b4() -> None:
    """The two share a history shape, so the system has to be passed in."""
    redis = FakeRedis()
    _scheduled_history(redis, "e1")
    outcome = await b4.classify(
        redis, "e1", system=SystemId.B4B_DURABLE_WORKFLOW_AT_MOST_ONCE
    )
    assert outcome.system is SystemId.B4B_DURABLE_WORKFLOW_AT_MOST_ONCE


@pytest.mark.asyncio
async def test_b4b_records_a_timeout_and_that_is_not_an_escalation() -> None:
    """The honest cost of at-most-once: a failure record over a live effect.

    ``UNVERIFIED_FAILURE``, not ``DECLARED_AMBIGUOUS``. An operator reading
    B4b's history sees an activity that timed out, which reads exactly like an
    activity that never applied anything. Nothing in B4b can say otherwise.
    """
    redis = FakeRedis()
    key = b4.history_key("e1")
    redis.lists[key] = [
        json.dumps(
            {
                "event": b4.ACTIVITY_TIMED_OUT,
                "status": STATUS_TIMED_OUT,
                "attempt": 1,
            },
            sort_keys=True,
        )
    ]
    outcome = await b4.classify(
        redis, "e1", system=SystemId.B4B_DURABLE_WORKFLOW_AT_MOST_ONCE
    )
    assert outcome.status == STATUS_TIMED_OUT
    assert outcome.outcome_class is OutcomeClass.UNVERIFIED_FAILURE
    assert outcome.outcome_class is not OutcomeClass.DECLARED_AMBIGUOUS


def test_the_attempt_budget_is_validated_not_silently_clamped() -> None:
    with pytest.raises(ValueError, match="activity_maximum_attempts"):
        b4.DurableWorkflowRunner(
            redis_client=FakeRedis(),
            lock_manager=None,
            connector=None,
            profile=None,
            policy=None,
            barrier=None,
            activity_maximum_attempts=0,
        )


def test_unlimited_is_the_documented_default() -> None:
    """Temporal's default is unlimited, so B4's default must be too.

    If this flipped, B4 would quietly become B4b and the paper's sharpest
    comparison would be between a system and itself.
    """
    assert b4.UNLIMITED_ACTIVITY_ATTEMPTS is None
    runner = b4.DurableWorkflowRunner(
        redis_client=FakeRedis(),
        lock_manager=None,
        connector=None,
        profile=None,
        policy=ConnectorPolicy(
            client_timeout_seconds=5.0,
            settlement_lag_seconds=0.0,
            buffer_margin_seconds=15.0,
            lock_ttl_seconds=25,
        ),
        barrier=None,
    )
    assert runner.activity_maximum_attempts is None
    assert runner.system is SystemId.B4_DURABLE_WORKFLOW
