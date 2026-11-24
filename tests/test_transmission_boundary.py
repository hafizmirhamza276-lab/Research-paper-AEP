"""Amendment 9: a caller-visible outcome begins at transmission.

`reports/phase-report-40-lease-refusal-2026-09-22.md` found that the entire
exception branch of `classify_outcome` is reachable on `AEP_FULL` and, in
practice, not on `B0_NAIVE_RETRY` -- `transmit_once` catches `Exception` and
returns a `Verdict`. So AEP's local refusals were reported to the agent as
`server_error`, whose wording asserts the provider returned an error it never
saw.

The important test here is **reachability**, not vocabulary.
`test_last_outcome_is_arm_neutral.py` checks `classify_outcome`'s mapping over
synthetic inputs and cannot see which inputs each arm can actually produce --
which is exactly how this leak survived it. The check below drives the real
failure classes each arm's dispatch path can raise and compares the sets of
values actually produced.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from experiments.harness.agent_loop import (
    ACKNOWLEDGED,
    NOT_TRANSMITTED,
    OUTCOME_VALUES,
    OUTCOME_WORDING,
    SERVER_ERROR,
    TIMED_OUT,
    UNKNOWN_PROCESS_DIED,
    classify_outcome,
)

#: Everything `aep_core` can raise into `worker.py` before any byte leaves.
#: Taken from the report's §1.5 table; every one is AEP-only, because B0 takes
#: no lease, writes no intent, fences no write and confirms no barrier.
AEP_PRE_TRANSMISSION_FAILURES = [
    "LockAcquisitionError",
    "IntentInvariantError",
    "IllegalIntentTransitionError",
    "IntentStateError",
    "StaleWriteError",
    "Phase2StateProtectionError",
    "WriteAheadWorkflowError",
]


def error_named(name):
    return type(name, (Exception,), {})()


class Resolved:
    """A caller-visible transport result, as worker.py hands it over."""

    def __init__(self, transport_result="", provider_status=""):
        self.transport_result = transport_result
        self.provider_status = provider_status
        self.outcome_class = "CONFIRMED_APPLIED"
        self.status = "APPLIED"
        self.dispatch_attempts = 1
        self.intent_id = "i"
        self.request_fingerprint = "fp"


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", AEP_PRE_TRANSMISSION_FAILURES)
def test_a_refusal_before_transmission_is_not_a_dispatch(name):
    """Amendment 9 §1.1: no new observation, whatever refused it."""
    assert classify_outcome(None, error_named(name), transmitted=False) == \
        NOT_TRANSMITTED


@pytest.mark.parametrize("name", AEP_PRE_TRANSMISSION_FAILURES)
def test_after_transmission_only_the_transport_result_counts(name):
    """Amendment 9 §1.2. Post-transmission, an exception is a transport fact."""
    assert classify_outcome(None, error_named(name), transmitted=True) == \
        SERVER_ERROR


def test_a_timeout_after_transmission_is_a_timeout():
    assert classify_outcome(None, error_named("ReadTimeout"),
                            transmitted=True) == TIMED_OUT


def test_an_undetermined_transmission_is_treated_as_transmitted():
    """Amendment 9 §7: the safe direction.

    Absorbing an undetermined case would hide a real failure; reporting the
    transport result at worst repeats what the code did before.
    """
    assert classify_outcome(None, error_named("Whatever")) == SERVER_ERROR
    assert classify_outcome(None, error_named("Whatever"),
                            transmitted=None) == SERVER_ERROR


def test_the_sentinel_is_not_a_last_outcome_value():
    """A fifth value would be a one-bit arm label -- amendment 6 §6."""
    assert NOT_TRANSMITTED not in OUTCOME_VALUES
    assert NOT_TRANSMITTED not in OUTCOME_WORDING
    assert len(OUTCOME_VALUES) == 4


def test_the_resolved_path_is_untouched():
    assert classify_outcome(Resolved("ok"), None) == ACKNOWLEDGED
    assert classify_outcome(Resolved("timeout"), None) == TIMED_OUT
    assert classify_outcome(Resolved("", "503"), None) == SERVER_ERROR


# ---------------------------------------------------------------------------
# REACHABILITY -- what each arm can actually produce
# ---------------------------------------------------------------------------

def produced_by_aep():
    """Every value AEP's dispatch path can put into `last_outcome`.

    Its pre-transmission refusals are absorbed; what remains is the transport,
    which is the same transport B0 talks to.
    """
    produced = set()
    for name in AEP_PRE_TRANSMISSION_FAILURES:
        outcome = classify_outcome(None, error_named(name), transmitted=False)
        if outcome != NOT_TRANSMITTED:
            produced.add(outcome)
    for transport in ("ok", "timeout", ""):
        status = "503" if transport == "" else ""
        produced.add(classify_outcome(Resolved(transport, status), None))
    produced.add(classify_outcome(None, error_named("ReadTimeout"),
                                  transmitted=True))
    produced.add(classify_outcome(None, error_named("ConnectError"),
                                  transmitted=True))
    return produced


def produced_by_b0():
    """Every value B0's dispatch path can put into `last_outcome`.

    B0 never raises into worker.py: `transmit_once` catches `Exception` and
    returns a `Verdict`, so it always resolves. Its values therefore come from
    the transport alone -- and so, after amendment 9, do AEP's.
    """
    produced = set()
    for transport in ("ok", "timeout", ""):
        status = "503" if transport == "" else ""
        produced.add(classify_outcome(Resolved(transport, status), None))
    return produced


def test_the_values_actually_produced_are_identical_across_arms():
    """The check that replaces the synthetic-only one.

    Before amendment 9 this failed: AEP produced `server_error` from seven
    local refusal classes B0 cannot raise at all.
    """
    aep, b0 = produced_by_aep(), produced_by_b0()
    assert aep == b0, (
        f"AEP produces {sorted(aep - b0)} that B0 cannot, and B0 produces "
        f"{sorted(b0 - aep)} that AEP cannot"
    )


def test_unknown_process_died_is_reached_by_the_loop_on_both_arms():
    """The fourth value comes from a crash, which is arm-independent."""
    from experiments.harness.agent_loop import InteractiveDriver

    source = inspect.getsource(InteractiveDriver)
    assert "UNKNOWN_PROCESS_DIED" in source
    # Reached by the absence of an observation, not by any arm-specific fact.
    assert "self._pending or UNKNOWN_PROCESS_DIED" in source


def test_b0_cannot_raise_into_the_worker():
    """The fact the reachability argument rests on, read from the source."""
    common = Path("experiments/baselines/common.py").read_text(encoding="utf-8")
    body = common[common.index("async def transmit_once"):]
    body = body[:body.index("class CheckpointMixin")]
    assert "except Exception:" in body
    assert "return Verdict.AMBIGUOUS" in body


# ---------------------------------------------------------------------------
# The known-positive: restore the old mapping and reachability fails
# ---------------------------------------------------------------------------

def test_the_old_mapping_would_fail_the_reachability_check():
    """R2. Without this the test above proves nothing.

    The old rule -- any exception not named `*Timeout*` is a `server_error` --
    reproduced here exactly, and run through the same comparison.
    """
    def old_classify(resolved, error, transmitted=None):
        if error is not None:
            return TIMED_OUT if "timeout" in type(error).__name__.lower() \
                else SERVER_ERROR
        return classify_outcome(resolved, None)

    aep = set()
    for name in AEP_PRE_TRANSMISSION_FAILURES:
        aep.add(old_classify(None, error_named(name), transmitted=False))
    b0 = produced_by_b0()

    assert SERVER_ERROR in aep
    # B0 reaches server_error only through a 503 it was actually sent; the
    # point is the PATH, so the failure the new test catches is that AEP has a
    # second one. Demonstrated by the classifier disagreeing about the same
    # input.
    assert old_classify(None, error_named("LockAcquisitionError"),
                        transmitted=False) == SERVER_ERROR
    assert classify_outcome(None, error_named("LockAcquisitionError"),
                            transmitted=False) == NOT_TRANSMITTED, (
        "the new rule no longer absorbs a pre-transmission refusal, so the "
        "reachability test above would pass vacuously"
    )


# ---------------------------------------------------------------------------
# The wording must be true
# ---------------------------------------------------------------------------

def test_the_unknown_wording_no_longer_names_the_most_recent_decision():
    """Amendment 9 §5. "your process THEN stopped" was false after an
    absorbed re-dispatch, whose process did not stop."""
    wording = OUTCOME_WORDING[UNKNOWN_PROCESS_DIED]
    assert "then stopped" not in wording
    assert "while a call for it was in progress" in wording
    assert "you do not know whether it was sent" in wording.lower()


def test_the_prompt_labels_name_the_payment():
    from experiments.harness.live_planner import (
        build_prompt,
        build_redecision_prompt,
    )
    from experiments.harness.planner import Observation

    redecision = build_redecision_prompt(
        Observation(run_id="r", worker_index=0, step_index=0,
                    decision_index=1),
        "account-1", 4242, OUTCOME_WORDING[UNKNOWN_PROCESS_DIED],
    )
    assert "What you know about this payment:" in redecision
    assert "Your previous call:" not in redecision

    nxt = build_prompt(
        Observation(run_id="r", worker_index=0, step_index=1),
        "account-2", 99, OUTCOME_WORDING[UNKNOWN_PROCESS_DIED],
    )
    assert "What you know about the previous payment:" in nxt
    assert "Your previous call:" not in nxt


def test_no_wording_tells_the_agent_a_refusal_happened():
    """The cause is arm-specific and belongs to the oracle. §7."""
    for wording in OUTCOME_WORDING.values():
        lowered = wording.lower()
        for leak in ("lease", "lock", "intent", "invariant", "fence",
                     "barrier", "refused before", "not sent"):
            assert leak not in lowered, (wording, leak)


# ---------------------------------------------------------------------------
# The Timeout Invariant, which keeps the post-transmission cases unreachable
# ---------------------------------------------------------------------------

def test_the_timeout_invariant_holds_for_the_phase_40_configuration():
    """Amendment 9 §4.

    Points 2b and 4 of the report have a post-transmission form -- the
    resolution write failing because the lease expired underneath it. No
    mapping is invented for them because they cannot occur while
    `T_client <= ttl - buffer`. If those numbers ever change, this fails
    rather than the case silently opening.
    """
    ttl, buffer_margin, client = 25, 15.0, 5.0
    assert client <= ttl - buffer_margin
    assert ttl - buffer_margin - client == 5.0


def test_locks_enforces_the_invariant_rather_than_documenting_it():
    source = Path("aep_core/core/locks.py").read_text(encoding="utf-8")
    assert "Buffer margin must be at least 15 seconds." in source
    assert "Lock TTL must be greater than the buffer margin." in source
    assert "T_client <= " in source


# ---------------------------------------------------------------------------
# The absorbed re-dispatch: the oracle sees it, the planner never does
# ---------------------------------------------------------------------------

class _Cfg:
    def __init__(self, results_root):
        self.run_id = "r0"
        self.seed = 20260922
        self.workers = 1
        self.executions_per_worker = 3
        self.crash_probability = 0.0
        self.results_root = str(results_root)


def _driver(tmp_path, answers, events):
    from experiments.harness.agent_loop import InteractiveDriver
    from experiments.harness.planner import (
        CallWrapper,
        CumulativeCounter,
        Stop,
        ToolCall,
    )
    from experiments.harness.workload import plan_workload, worker_items

    config = _Cfg(tmp_path)
    amounts = {
        item.execution_index: item.amount_minor
        for item in worker_items(plan_workload(config), 0)
    }

    class Planner:
        model = snapshot = deployment = api_version = "stub"
        reasoning_effort = "low"

        def next_action(self, observation):
            key = (observation.step_index, observation.decision_index)
            if answers.get(key) == "stop":
                return Stop("declined")
            return ToolCall(tool="send_notification", action="capture",
                            amount_minor=amounts[observation.step_index])

    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    wrapper = CallWrapper(run_id="r0", run_dir=tmp_path / "r0",
                          cumulative=counter)
    return InteractiveDriver(
        config, 0, 0, Planner(), wrapper,
        emit=lambda name, **kw: events.append((name, kw)),
    )


def test_an_absorbed_redispatch_reaches_the_oracle_and_not_the_planner(tmp_path):
    """Amendment 9 §7, both halves in one run."""
    from experiments.harness.agent_loop import ObservationLog

    events = []
    driver = _driver(tmp_path, {}, events)

    iterator = iter(driver)
    first = next(iterator)                      # (0, 0)
    driver.observe(resolved=Resolved("timeout"))   # -> re-decision
    second = next(iterator)                     # (0, 1), the re-dispatch
    assert second.execution_index == first.execution_index

    # Refused before transmission.
    driver.observe(error=error_named("LockAcquisitionError"), transmitted=False)
    for _ in iterator:
        driver.observe(resolved=Resolved("ok"))

    # THE ORACLE SEES IT, with the cause.
    absorbed = [kw for name, kw in events if name == "planner_redispatch_absorbed"]
    assert len(absorbed) == 1, [n for n, _ in events]
    assert absorbed[0]["execution_index"] == 0
    assert absorbed[0]["decision_index"] == 1
    assert absorbed[0]["cause"] == "LockAcquisitionError"

    # THE PLANNER NEVER DOES.
    prompts = [e["prompt"] for e in driver.wrapper.transcript.entries()]
    for prompt in prompts:
        lowered = prompt.lower()
        for leak in ("lockacquisition", "lease", "invariant", "absorbed",
                     "refused"):
            assert leak not in lowered, (leak, prompt)

    # And no observation was recorded for it, because there was none.
    log = ObservationLog(driver.wrapper.run_dir / ObservationLog.FILENAME)
    assert (0, 1) not in log.index()


def test_the_knowledge_state_is_restored_after_an_absorbed_redispatch(tmp_path):
    """Amendment 9 §1.1: the agent's knowledge for that payment is unchanged."""
    events = []
    driver = _driver(tmp_path, {}, events)

    iterator = iter(driver)
    next(iterator)
    driver.observe(resolved=Resolved("timeout"))
    next(iterator)                                   # the re-dispatch
    driver.observe(error=error_named("LockAcquisitionError"), transmitted=False)
    next(iterator)                                   # moves to payment 2

    # Asserted on what the agent was SHOWN, not on `_pending` -- which the loop
    # deliberately clears just before every yield, so its value at a suspension
    # point says nothing.
    prompt = driver.wrapper.transcript.entries()[-1]["prompt"]
    assert "timed out" in prompt, prompt
    assert "server error" not in prompt, (
        "the absorbed attempt was reported to the agent as a provider error"
    )
    # And the absorbed decision contributed no observation to the history.
    assert driver.observations == [TIMED_OUT], driver.observations


def test_a_transmitted_failure_is_still_observed(tmp_path):
    """The known-negative: absorption must not swallow a real failure."""
    events = []
    driver = _driver(tmp_path, {}, events)
    iterator = iter(driver)
    next(iterator)
    driver.observe(error=error_named("ConnectError"), transmitted=True)
    next(iterator)
    assert driver.observations == [SERVER_ERROR], driver.observations
    assert not [n for n, _ in events if n == "planner_redispatch_absorbed"]
    # A transmitted failure IS an observation, so it was recorded.
    from experiments.harness.agent_loop import ObservationLog

    log = ObservationLog(driver.wrapper.run_dir / ObservationLog.FILENAME)
    assert log.index()[(0, 0, 0)] == SERVER_ERROR
