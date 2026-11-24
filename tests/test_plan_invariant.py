r"""The §2.9 repeat invariant from `docs/33-agent-workload.md`.

A planner may repeat a fingerprint only in response to a step declared
`PERMANENTLY_AMBIGUOUS`. A violation does not mean a planner behaved oddly; it
means a published duplicate number has quietly changed population.

**This file once had a second half**, pinning the WS-1a execution-id attribution
fallback. That machinery — the ledger column, its reader and its four proofs —
was reverted when the framing decision moved from Option B to Option A, since it
served an agent workload nothing collects. The invariant is kept because it is a
statement about a *plan*, independent of whether a planner exists to produce
one, and because §2.9 remains the reasoning record either way.
"""

from __future__ import annotations

import pytest

from experiments.harness.plan_invariant import (
    PERMANENTLY_AMBIGUOUS,
    PlannedStep,
    Violation,
    assert_holds,
    find_violations,
)


def step(index: int, fingerprint: str, outcome: str | None = None) -> PlannedStep:
    return PlannedStep(index=index, fingerprint=fingerprint, outcome=outcome)


# ===========================================================================
# §2.9 -- the repeat invariant
# ===========================================================================


def test_distinct_fingerprints_never_violate():
    """The current workload's shape: every execution its own mutation."""
    plan = [step(0, "aaa"), step(1, "bbb"), step(2, "ccc")]

    assert find_violations(plan) == ()


def test_a_repeat_after_declared_ambiguity_is_licensed():
    """This is plan drift, and it is the phenomenon being measured."""
    plan = [step(0, "aaa", PERMANENTLY_AMBIGUOUS), step(1, "aaa")]

    assert find_violations(plan) == ()


def test_a_repeat_without_ambiguity_is_a_violation():
    plan = [step(0, "aaa", "CONFIRMED"), step(1, "aaa")]
    violations = find_violations(plan)

    assert len(violations) == 1
    assert violations[0].index == 1
    assert violations[0].first_index == 0
    assert violations[0].fingerprint == "aaa"


def test_ambiguity_on_a_different_mutation_licenses_nothing():
    """The planner may re-plan what it cannot determine, not something else."""
    plan = [step(0, "aaa", PERMANENTLY_AMBIGUOUS), step(1, "bbb"), step(2, "bbb")]
    violations = find_violations(plan)

    assert [v.fingerprint for v in violations] == ["bbb"]


def test_a_repeat_may_itself_license_a_further_repeat():
    plan = [
        step(0, "aaa", "CONFIRMED"),
        step(1, "aaa", PERMANENTLY_AMBIGUOUS),  # violation: 0 was not ambiguous
        step(2, "aaa"),                          # licensed by step 1
    ]
    violations = find_violations(plan)

    assert [v.index for v in violations] == [1]


def test_an_unresolved_step_licenses_nothing():
    """`outcome=None` is 'not known yet', which is not a declared ambiguity."""
    plan = [step(0, "aaa", None), step(1, "aaa")]

    assert len(find_violations(plan)) == 1


def test_assert_holds_raises_with_the_offending_steps_named():
    plan = [step(0, "aaa"), step(1, "aaa")]

    with pytest.raises(AssertionError) as caught:
        assert_holds(plan)

    message = str(caught.value)
    assert "2.9" in message
    assert "step 1" in message


def test_assert_holds_is_silent_on_a_valid_plan():
    assert_holds([step(0, "aaa", PERMANENTLY_AMBIGUOUS), step(1, "aaa")])
