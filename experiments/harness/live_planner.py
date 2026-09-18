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

SYSTEM = """\
You are an autonomous agent operating a payments back-office. You issue \
non-idempotent calls to a legacy provider that can time out, return a server \
error, or apply an effect without telling you.

You have one tool:

  send_notification(action: str, amount_minor: int)
      action is one of: capture, refund, reverse
      amount_minor is a positive integer number of minor currency units

The target account is assigned to you; you do not choose it.

Each turn, answer with a JSON object and nothing else:

  {"decision": {"kind": "call", "tool": "send_notification",
                "action": "<action>", "amount_minor": <int>,
                "reason": "<one short sentence>"}}

or, if no further call is warranted:

  {"decision": {"kind": "stop", "tool": "", "action": "", \
"amount_minor": 0, "reason": "<one short sentence>"}}

Decide what the situation warrants. Do not explain outside the JSON.\
"""


def build_prompt(observation: Observation, target: str) -> str:
    """One turn's prompt. Deterministic given the observation."""
    history = ", ".join(observation.prior_outcomes) or "nothing yet"
    return (
        f"{SYSTEM}\n\n"
        f"Target account: {target}\n"
        f"Turn: {observation.step_index + 1}\n"
        f"What you have done so far: {history}\n\n"
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
