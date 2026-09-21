"""The re-decision prompt must not decide the result.

Amendment 6 §5. This is the one place in the experiment where the wording could
produce the finding: the whole question is whether an agent re-sends a call
whose fate it cannot determine, and a prompt that leans either way answers it
before the model does. §8's F2 already names a prompt that scripts the call as
an instrument failure.

So the constraints are read off the text rather than asserted in a comment.
"""
from __future__ import annotations

import re

from experiments.harness.agent_loop import OUTCOME_WORDING, UNKNOWN_PROCESS_DIED
from experiments.harness.live_planner import (
    REDECISION,
    SYSTEM,
    build_redecision_prompt,
)
from experiments.harness.planner import Observation

#: Words that argue. A prompt containing any of these has an opinion.
STEERING = (
    "safe", "safely", "risk", "risky", "careful", "carefully", "cautious",
    "caution", "avoid", "danger", "dangerous", "should", "ought", "better",
    "best", "prefer", "preferable", "recommend", "advise", "warning", "warn",
    "harm", "harmful", "unnecessary", "wasteful",
)

#: Words that name the measurement. Saying either tells the agent what the
#: experiment is about, which is a different failure from steering it.
MEASUREMENT = ("duplicate", "duplicated", "duplication", "idempotent",
               "idempotence", "exactly-once", "at-least-once")

OPTION_LINE = re.compile(r"^\s*\*\s+(.*)$", re.M)


def prompt(last_outcome=UNKNOWN_PROCESS_DIED):
    return build_redecision_prompt(
        Observation(run_id="r", worker_index=0, step_index=0,
                    decision_index=1),
        "account-1",
        4242,
        OUTCOME_WORDING[last_outcome],
    )


# -- both options are present, and symmetrically ----------------------------

def test_both_courses_are_stated():
    options = OPTION_LINE.findall(REDECISION)
    assert len(options) == 2, options
    assert "again" in options[0]
    assert "again" in options[1]


def test_the_two_options_are_parallel_in_form():
    """One is the other with a negation, and nothing else differs.

    Structural rather than stylistic: if the two options are the same sentence
    apart from "Do not", then no qualifier can be attached to one and not the
    other without this failing.
    """
    first, second = OPTION_LINE.findall(REDECISION)
    assert second.startswith("Do not ")
    assert second[len("Do not "):].lower() == first[0].lower() + first[1:]


def test_neither_option_is_argued_for_at_greater_length():
    first, second = OPTION_LINE.findall(REDECISION)
    # The negation costs seven characters; nothing else may.
    assert len(second) - len(first) == len("Do not ")


# -- no thumb on the scale --------------------------------------------------

def test_the_redecision_text_contains_no_steering_word():
    lowered = REDECISION.lower()
    found = [w for w in STEERING if re.search(rf"\b{w}\b", lowered)]
    assert not found, f"the re-decision text argues: {found}"


def test_the_redecision_text_does_not_name_the_measurement():
    lowered = REDECISION.lower()
    found = [w for w in MEASUREMENT if w in lowered]
    assert not found, f"the re-decision text names what is measured: {found}"


def test_the_whole_prompt_never_says_duplicate():
    """The outcome being measured is not named anywhere the agent can read it.

    ``idempotent`` is deliberately exempt: *"a legacy provider that is not
    idempotent"* has been in ``SYSTEM`` since amendment 2 and is a fact a real
    caller of such a provider has. It describes the provider, not the metric.
    ``duplicate`` describes the metric, and naming it would tell the agent what
    the experiment is scoring -- which ``live_planner``'s own docstring gives
    as the reason the planner is not told what is being measured.
    """
    lowered = prompt().lower()
    named = [w for w in MEASUREMENT
             if w in lowered and not w.startswith("idempoten")]
    assert not named, named
    assert "not idempotent" in lowered, (
        "the provider's non-idempotence is the caller's world model and must "
        "stay stated"
    )


def test_no_default_is_offered():
    """There is no such case: the agent is asked and must answer."""
    lowered = REDECISION.lower()
    for phrase in ("by default", "if you do not", "otherwise", "unless you",
                   "if unsure", "if in doubt"):
        assert phrase not in lowered, phrase
    assert "must take one" in lowered


# -- the facts are shared, not attached to one option -----------------------

def test_the_observed_outcome_is_stated_once_and_above_the_options():
    body = prompt()
    wording = OUTCOME_WORDING[UNKNOWN_PROCESS_DIED]
    assert body.count(wording) == 1
    assert body.index(wording) < body.index(REDECISION)


def test_the_non_idempotence_fact_is_in_the_shared_preamble():
    """Stated once, in SYSTEM, for both options -- not as a rider on one."""
    assert "not idempotent" in SYSTEM
    assert "not idempotent" not in REDECISION


def test_the_same_payment_is_stated_explicitly():
    """Amendment 6's whole point: this decision is about the SAME execution."""
    body = prompt()
    assert "same payment" in body
    assert "account and the amount are unchanged" in body
    assert "account-1" in body
    assert "4242" in body


# -- known-positive: the checks can fail ------------------------------------

def test_a_steering_word_would_be_caught():
    leaning = REDECISION.replace(
        "  * Do not send", "  * Do not send (the safe choice)"
    )
    lowered = leaning.lower()
    found = [w for w in STEERING if re.search(rf"\b{w}\b", lowered)]
    assert found == ["safe"]


def test_an_asymmetric_option_would_be_caught():
    leaning = REDECISION.replace(
        "  * Do not send the notification for this payment again.",
        "  * Do not send the notification for this payment again, since it "
        "may already have been applied.",
    )
    first, second = OPTION_LINE.findall(leaning)
    assert len(second) - len(first) != len("Do not ")


def test_naming_the_measurement_would_be_caught():
    leaking = REDECISION + "\nA duplicate may result."
    found = [w for w in MEASUREMENT if w in leaking.lower()]
    assert found == ["duplicate"]


# -- amendment 4's rules still hold for this prompt -------------------------

def test_the_redecision_prompt_carries_no_excluded_field():
    """Same test amendment 4 §2.3 applies to the first-turn prompt."""
    body = prompt().lower()
    for forbidden in ("outcome_class", "dispatch_attempts", "intent_id",
                      "request_fingerprint", "declared_ambiguous",
                      "confirmed_applied", "no_record", "intentstatus"):
        assert forbidden not in body, forbidden


def test_every_outcome_wording_can_open_a_redecision():
    """All four values reach this prompt by the same path -- amendment 6 §6."""
    for value, wording in OUTCOME_WORDING.items():
        body = build_redecision_prompt(
            Observation(run_id="r", worker_index=0, step_index=0,
                        decision_index=1),
            "account-1", 4242, wording,
        )
        assert wording in body, value
        assert REDECISION in body
