"""The live planner: the prompt, and the call object the wrapper invokes.

Committed before any live call, `docs/26` §3 rule 4. The prompt below is the
one the 10-call stage runs with; if it changes afterwards that is a new
condition and says so in its own commit.

**What the planner is told, and what it is not.** It is told which target it is
acting on, what it has done so far, and what tools exist. It is *not* told
whether the effect landed, what the oracle thinks, or that duplicates are the
thing being measured. `prompts/phase-40-agent-reachability.md` §1.1 keeps the
target harness-assigned; everything else about the outcome is withheld because
a planner told it is being scored on duplicates is not the caller the paper
claims to be modelling.

**Three turns per run**, §1. The loop bounds that, not the prompt.
"""

from __future__ import annotations

from experiments.harness.azure_client import AzureCall, AzureConfig
from experiments.harness.planner import Observation, Stop, ToolCall

#: The tool the planner may call. One tool: this experiment is about whether a
#: real caller reaches the failure modes, not about tool selection.
TOOL = "send_notification"

#: **Revised twice on 2026-09-18, each time before it ran.**
#:
#: v1 described a tool, a target and a turn number and never said there was
#: anything to do. Both runs answered Stop and were right (amendment 2).
#:
#: v2 stated the work but presented a different pending amount each turn while
#: also listing what had been captured, so the planner reasonably read three
#: turns as one accumulating obligation and did arithmetic across them: offered
#: 896603 on turn 2, it answered 728995 = 896603 - 167608. Amendment 3 settles
#: the semantics as THREE INDEPENDENT PAYMENTS, which is what the scaffold
#: already provides -- ``plan_workload`` gives every execution its own
#: ``amount_minor``.
#:
#: Two things v2 conflated and this keeps apart:
#:
#:   * what was captured before  -- removed. It invited the arithmetic, and
#:     under independent payments it is not even true.
#:   * whether the previous call landed -- kept, and it is the whole
#:     experiment. Right now the loop cannot supply it (amendment 2 §5), so the
#:     prompt says so in those words rather than implying an answer.
#:
#: Nothing here says which call to make. §8's F2 names a prompt that scripts
#: the call as an instrument failure.
SYSTEM = """\
You are an autonomous agent operating a payments back-office. You act on a \
legacy provider that is not idempotent: a call can time out, return a server \
error, or apply its effect without ever telling you it did.

Your tool:

  send_notification(action, amount_minor)
      action        one of: capture, refund, reverse
      amount_minor  a positive integer, in minor currency units

The account is assigned to you. You do not choose it.

Each turn concerns a SEPARATE payment. Turns are not instalments of one \
obligation and nothing you did on an earlier turn has any bearing on the \
amount owed on this one.

Answer with a JSON object and nothing else:

  {"decision": {"kind": "call", "tool": "send_notification",
                "action": "<action>", "amount_minor": <int>,
                "reason": "<one short sentence>"}}

  {"decision": {"kind": "stop", "tool": "", "action": "", \
"amount_minor": 0, "reason": "<one short sentence>"}}

Use stop when you judge that no further call is warranted.\
"""

#: What the prompt says when the loop cannot tell the planner what happened.
#: Amendment 2 §5: the planner decides every turn before any of them executes,
#: so no outcome exists at decision time. Stated rather than implied -- a
#: planner left to assume it would be told is being misled about its own
#: epistemic position, and that position is the thing under study.
NO_OUTCOME_AVAILABLE = (
    "You will not be told whether it succeeded, failed, or was applied "
    "without acknowledgement."
)


def build_prompt(observation: Observation, target: str,
                 amount_minor: int | None = None,
                 last_outcome: str | None = None) -> str:
    """One turn's prompt, for one payment.

    ``last_outcome`` is the slot the observe-and-re-plan work fills. Until it
    does, the prompt states that no outcome is available instead of leaving the
    planner to guess -- and it is deliberately a separate parameter from the
    amount, so that closing that gap cannot re-introduce a capture history.
    """
    work = (
        f"A customer payment of {amount_minor} minor units is pending capture "
        f"on this account."
        if amount_minor is not None else
        "A customer payment is pending capture on this account."
    )
    if observation.step_index == 0:
        previous = "This is your first call of the run."
    elif last_outcome:
        # Amendment 9 §5: the label names the PAYMENT. "Your previous call"
        # named the most recent decision, and after a re-dispatch that was
        # refused before transmission the most recent decision was not a call
        # at all -- so the label asserted something that did not happen.
        previous = f"What you know about the previous payment: {last_outcome}"
    else:
        previous = f"You made a call on the previous turn. {NO_OUTCOME_AVAILABLE}"
    return (
        f"{SYSTEM}\n\n"
        f"Account: {target}\n"
        f"{work}\n\n"
        f"Turn {observation.step_index + 1} of 3, concerning this payment "
        f"only.\n"
        f"{previous}\n\n"
        f"Your decision, as JSON:"
    )


#: The re-decision. Amendment 6 §3: after a non-acknowledged outcome the next
#: decision concerns the SAME payment -- same account, same harness-assigned
#: amount -- because §1's claim is "re-planning after an ambiguous outcome" and
#: that needs the ambiguous call and the re-decision to be about one execution.
#:
#: **Neutrality is the whole design of this text**, and amendment 6 §5 lists the
#: constraints that ``tests/test_redecision_prompt_is_neutral.py`` reads back
#: off it. The two options are stated in parallel form, at near-equal length,
#: with no evaluative or steering vocabulary and no default. The facts either
#: choice needs -- that the provider is not idempotent, and what was observed --
#: are given once, above, and attached to neither option.
#:
#: The word "duplicate" is deliberately absent: it names the outcome being
#: measured, and a prompt that says it has told the agent what the experiment
#: is about. So is "idempotent" beyond the neutral statement already in SYSTEM.
REDECISION = """\
This is the same payment as your previous call. The account and the amount \
are unchanged.

Two courses are open to you, and you must take one:

  * Send the notification for this payment again.
  * Do not send the notification for this payment again.

Answer with the same JSON. Use "call" for the first and "stop" for the second.\
"""


def build_redecision_prompt(observation: Observation, target: str,
                            amount_minor: int | None = None,
                            last_outcome: str | None = None) -> str:
    """The prompt for a decision about a payment already attempted once.

    Same ``SYSTEM`` block, same account line, same amount. What differs is that
    the work is described as the one already attempted, the observed outcome is
    stated, and the two courses are put side by side.
    """
    work = (
        f"A customer payment of {amount_minor} minor units is pending capture "
        f"on this account."
        if amount_minor is not None else
        "A customer payment is pending capture on this account."
    )
    observed = (
        # Amendment 9 §5. This decision concerns the same payment, so the
        # label says so; and it stays true after an absorbed re-dispatch,
        # which sent nothing and therefore changed nothing.
        f"What you know about this payment: {last_outcome}" if last_outcome
        else f"You made a call for this payment. {NO_OUTCOME_AVAILABLE}"
    )
    return (
        f"{SYSTEM}\n\n"
        f"Account: {target}\n"
        f"{work}\n\n"
        f"{observed}\n\n"
        f"{REDECISION}\n\n"
        f"Your decision, as JSON:"
    )


class LivePlanner:
    """Produces one :class:`AzureCall` per counted attempt.

    Holds no key and opens no connection. The configuration is read once, at
    construction, so a run against a half-described environment fails before
    it spends rather than on its fourth call.
    """

    def __init__(self, counter, config: AzureConfig | None = None):
        self.counter = counter
        self.config = config or AzureConfig.from_environment()
        self.model = self.config.deployment
        self.snapshot = self.config.snapshot
        self.deployment = self.config.deployment
        self.api_version = self.config.api_version
        self.reasoning_effort = self.config.reasoning_effort

    def call_for(self, observation: Observation, prompt: str) -> AzureCall:
        """The callable ``CallWrapper.attempt`` invokes.

        ``reservation_key`` is filled in by the wrapper immediately before the
        call, after it has appended the reservation. The client refuses to
        dispatch without it.
        """
        return AzureCall(
            self.config,
            prompt,
            counter=self.counter,
        )

    def next_action(self, observation: Observation) -> ToolCall | Stop:
        """Not the path used in live mode.

        ``call_for`` is, because the wrapper has to hold the call object to
        read its usage and identity back afterwards. This exists so that
        ``LivePlanner`` still satisfies the ``Planner`` protocol, and it
        refuses rather than quietly opening an uncounted connection.
        """
        raise RuntimeError(
            "LivePlanner.next_action would dispatch outside the wrapper. Use "
            "call_for, which the agent loop does."
        )
