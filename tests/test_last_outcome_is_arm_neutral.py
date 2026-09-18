"""What the agent is told must not reveal which arm it is in.

**The standing constraint, from amendment 4 §2.3:**

    An agent that can tell which system it is on is a second uncontrolled
    variable, and the comparison stops meaning anything.

The experiment runs one fixed caller against `AEP_FULL` and `B0_NAIVE_RETRY`
and attributes the difference in outcomes to the systems. An agent able to infer
"I am on the naive baseline" may reason about duplicates it was never told
about, or behave more cautiously under AEP because it has noticed the protocol.
Either way the caller stops being fixed, the arms stop being comparable, and the
result measures the agent's inference rather than the protocol's effect.

Three fields on `ExecutionOutcome` are arm labels rather than oracle leaks, and
that was not obvious — `dispatch_attempts` in particular looks like innocuous
transport metadata and is the cleanest arm label in the whole record:

* `status` — an `IntentStatus` under AEP, a baseline's own string under B0.
* `dispatch_attempts` — 1 under AEP by construction, higher under B0.
* `intent_id` — exists only under AEP; its presence is a one-bit label.

This file exists so that a future field added to `last_outcome` fails a test
rather than being noticed by a reader.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from experiments.harness.agent_loop import (
    ACKNOWLEDGED,
    OUTCOME_VALUES,
    OUTCOME_WORDING,
    SERVER_ERROR,
    TIMED_OUT,
    UNKNOWN_PROCESS_DIED,
    classify_outcome,
)

HARNESS = Path(__file__).resolve().parents[1] / "experiments" / "harness"

#: Everything on ExecutionOutcome that names or counts something arm-specific.
ARM_LABELLING_FIELDS = ("status", "dispatch_attempts", "intent_id")

#: The oracle's own vocabulary and identity function.
ORACLE_FIELDS = ("outcome_class", "request_fingerprint")


class _Resolved:
    """Stands in for an ExecutionOutcome from either arm."""

    def __init__(self, **kw):
        self.status = kw.get("status", "")
        self.outcome_class = kw.get("outcome_class", "")
        self.dispatch_attempts = kw.get("dispatch_attempts", 0)
        self.intent_id = kw.get("intent_id")
        self.request_fingerprint = kw.get("request_fingerprint")
        self.transport_result = kw.get("transport_result", "")
        self.provider_status = kw.get("provider_status", "")


#: The same transport reality, described the way each arm describes it.
AEP_FULL = [
    _Resolved(status="RESOLVED_APPLIED", outcome_class="CONFIRMED_APPLIED",
              dispatch_attempts=1, intent_id="i-1",
              request_fingerprint="fp-1", transport_result="ok"),
    _Resolved(status="DECLARED_AMBIGUOUS", outcome_class="DECLARED_AMBIGUOUS",
              dispatch_attempts=1, intent_id="i-2",
              request_fingerprint="fp-2", transport_result="timeout"),
    _Resolved(status="RESOLVED_NOT_APPLIED",
              outcome_class="CONFIRMED_NOT_APPLIED", dispatch_attempts=1,
              intent_id="i-3", request_fingerprint="fp-3",
              transport_result="503 server_error"),
]
B0_NAIVE_RETRY = [
    _Resolved(status="applied", outcome_class="CONFIRMED_APPLIED",
              dispatch_attempts=1, transport_result="ok"),
    _Resolved(status="failed", outcome_class="UNVERIFIED_FAILURE",
              dispatch_attempts=3, transport_result="timeout"),
    _Resolved(status="failed", outcome_class="CONFIRMED_NOT_APPLIED",
              dispatch_attempts=2, transport_result="503 server_error"),
]


def test_the_two_arms_yield_the_same_set_of_values():
    """The property. If a future field leaks the arm, these sets diverge."""
    aep = {classify_outcome(r, None) for r in AEP_FULL}
    b0 = {classify_outcome(r, None) for r in B0_NAIVE_RETRY}
    assert aep == b0, (
        f"AEP produced {sorted(aep)} and B0 produced {sorted(b0)}. A value "
        f"available on one arm and not the other tells the agent which arm it "
        f"is in, and the comparison stops meaning anything."
    )


def test_matched_outcomes_classify_identically_pair_by_pair():
    """Stronger than set equality: the same reality reads the same on both."""
    for aep, b0 in zip(AEP_FULL, B0_NAIVE_RETRY):
        assert classify_outcome(aep, None) == classify_outcome(b0, None), (
            f"same transport reality, different observation: "
            f"{aep.transport_result!r}"
        )


def test_the_classifier_reads_no_arm_labelling_field():
    """Structural, so it cannot drift back in.

    An outcome carrying wildly different arm labels but the same transport
    result must classify the same. If `classify_outcome` ever consults
    `dispatch_attempts`, this fails.
    """
    quiet = _Resolved(status="x", dispatch_attempts=1, intent_id=None,
                      transport_result="timeout")
    loud = _Resolved(status="COMPLETELY_DIFFERENT", dispatch_attempts=99,
                     intent_id="i-999", outcome_class="DECLARED_AMBIGUOUS",
                     request_fingerprint="fp-abc", transport_result="timeout")
    assert classify_outcome(quiet, None) == classify_outcome(loud, None)


def test_the_classifier_touches_no_forbidden_field_by_name():
    """Belt and braces: the forbidden names are not read anywhere in it.

    Checked as exact attribute names and exact string constants, not as
    substrings -- ``provider_status`` contains "status" and is not it, and a
    test that fails on that is a test that gets silenced rather than obeyed.
    """
    import ast

    tree = ast.parse((HARNESS / "agent_loop.py").read_text(encoding="utf-8"))
    function = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "classify_outcome"
    )
    forbidden = set(ARM_LABELLING_FIELDS) | set(ORACLE_FIELDS)

    touched = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Attribute):
            touched.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            touched.add(node.value)

    leaked = sorted(touched & forbidden)
    assert not leaked, (
        f"classify_outcome reads {leaked}. "
        f"{sorted(set(leaked) & set(ARM_LABELLING_FIELDS))} label which arm "
        f"the agent is in; "
        f"{sorted(set(leaked) & set(ORACLE_FIELDS))} are the oracle's."
    )


def test_that_check_would_catch_a_real_leak():
    """R2: prove the test above can fail.

    The same walk over a function that *does* read ``dispatch_attempts`` must
    find it, or the check is decorative.
    """
    import ast

    leaky = ast.parse(
        "def f(resolved, error):\n"
        "    return 'many' if resolved.dispatch_attempts > 1 else 'one'\n"
    )
    touched = {
        node.attr for node in ast.walk(leaky)
        if isinstance(node, ast.Attribute)
    }
    assert touched & set(ARM_LABELLING_FIELDS) == {"dispatch_attempts"}


def test_nothing_the_agent_is_shown_carries_an_oracle_verdict():
    """`DECLARED_AMBIGUOUS` is the answer the agent is asked to reach."""
    for value in OUTCOME_VALUES:
        for banned in ("ambiguous", "confirmed", "unverified", "no_record",
                       "unreadable"):
            assert banned not in value.lower()
    for wording in OUTCOME_WORDING.values():
        for banned in ("ambiguous", "duplicate", "oracle", "ledger",
                       "intent", "fingerprint", "dispatch"):
            assert banned not in wording.lower(), wording


def test_the_vocabulary_is_exactly_four_values():
    """`rejected` was approved and then withdrawn -- amendment 4 §2.2.

    There is no injected 4xx fault: the injected refusal is a 503, which in
    this harness already means refused before applying. The only 4xx reachable
    in normal operation are on the read-back routes, and B0 never calls them,
    so `rejected` would have been an AEP-only value -- the same leak class as
    `dispatch_attempts`.
    """
    assert set(OUTCOME_VALUES) == {
        TIMED_OUT, SERVER_ERROR, ACKNOWLEDGED, UNKNOWN_PROCESS_DIED
    }
    assert "rejected" not in OUTCOME_VALUES
    assert set(OUTCOME_WORDING) == set(OUTCOME_VALUES)


@pytest.mark.parametrize("arm", [AEP_FULL, B0_NAIVE_RETRY])
def test_a_transport_exception_classifies_the_same_on_both_arms(arm):
    import httpx

    assert classify_outcome(None, httpx.ReadTimeout("x")) == TIMED_OUT
    assert classify_outcome(None, RuntimeError("boom")) == SERVER_ERROR
