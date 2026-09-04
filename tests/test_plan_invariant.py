r"""The §2.9 repeat invariant, and the attribution fallback it protects.

Two things are pinned here, both from `docs/33-agent-workload.md`:

* **§2.9** — a planner may repeat a fingerprint only in response to a step
  declared `PERMANENTLY_AMBIGUOUS`. A violation means a published duplicate
  number has changed population, not that a planner behaved oddly.
* **§2.4** — `oracle_effects_by_execution` must return `None` for a ledger that
  cannot answer, so the caller falls back to `target`. The dangerous case is a
  ledger that *carries* the column with nothing in it: returning an empty
  mapping there would attribute zero applied effects to every execution and
  silently zero every duplicate, lost-effect and applied-effect number in the
  paper.
"""

from __future__ import annotations

import sqlite3

import pytest

from experiments.analyze import oracle_effects_by_execution
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


# ===========================================================================
# §2.4 -- the fallback, including the state that would zero every number
# ===========================================================================


def _ledger(path, *, column: bool, values: list[str | None] | None = None):
    connection = sqlite3.connect(path)
    extra = ", execution_id TEXT" if column else ""
    connection.execute(
        f"CREATE TABLE applied_mutations (id INTEGER PRIMARY KEY, target TEXT{extra})"
    )
    for index, value in enumerate(values or []):
        if column:
            connection.execute(
                "INSERT INTO applied_mutations (target, execution_id) VALUES (?, ?)",
                (f"account-{index}", value),
            )
        else:
            connection.execute(
                "INSERT INTO applied_mutations (target) VALUES (?)", (f"account-{index}",)
            )
    connection.commit()
    connection.close()
    return path


def test_a_ledger_without_the_column_returns_none(tmp_path):
    """Every database collected before WS-1a. Attribution stays on target."""
    path = _ledger(tmp_path / "old.sqlite3", column=False, values=[None, None])

    assert oracle_effects_by_execution(path) is None


def test_a_ledger_with_the_column_but_no_values_returns_none(tmp_path):
    """The hazard: column added, provider not yet plumbed.

    Returning an empty mapping here would make the caller take the
    by-execution path and attribute zero applied effects to everything.
    """
    path = _ledger(tmp_path / "empty.sqlite3", column=True, values=[None, None])

    assert oracle_effects_by_execution(path) is None


def test_a_populated_ledger_counts_by_execution(tmp_path):
    path = _ledger(
        tmp_path / "new.sqlite3", column=True, values=["exec-a", "exec-a", "exec-b"]
    )

    counts = oracle_effects_by_execution(path)

    assert counts is not None
    assert counts["exec-a"] == 2
    assert counts["exec-b"] == 1


def test_partially_populated_counts_only_what_it_can_attribute(tmp_path):
    """A NULL row is not attributable; it must not be counted against anyone."""
    path = _ledger(
        tmp_path / "mixed.sqlite3", column=True, values=["exec-a", None, "exec-a"]
    )

    counts = oracle_effects_by_execution(path)

    assert counts is not None
    assert counts["exec-a"] == 2
    assert sum(counts.values()) == 2
