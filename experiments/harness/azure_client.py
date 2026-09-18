"""The live Azure OpenAI transport. One HTTP request per counted attempt.

**Everything in this module exists to make one sentence true: no request
reaches Azure that the counter has not already recorded.**

``prompts/phase-40-agent-reachability.md`` §3 requires the wrapper to count at
the **HTTP transport layer, not the SDK method**, because an SDK's automatic
retries on 429 and timeout happen *inside* one ``responses.create()`` call and
are invisible above it: "a retry that is not counted is a retry that is not
capped."

This is written against ``httpx`` directly rather than the ``openai`` SDK, which
is not a dependency of this project and is not installed. That is the cheaper
way to satisfy §3 and the stronger one: there is no retry layer to hook,
because there is no layer. One ``POST``, retries explicitly zero, per call.

**The reservation check.** ``CallWrapper.attempt`` appends a reservation to the
cumulative journal before it invokes anything. This client re-reads that journal
from disk and refuses to dispatch unless its own reservation key is already
there. So the ordering is not a convention that a future edit could quietly
invert -- the request cannot physically go out ahead of the count, and
``tests/test_azure_client.py`` asserts the refusal rather than trusting it.

**The key is never written anywhere.** It is read from the environment into one
local, sent in one header, and never placed on the call object, in the
transcript, in an exception, or in a log line. ``__repr__`` is overridden
because a traceback prints arguments, and a traceback is a file.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from experiments.harness.planner import (
    PlannerOutcome,
    PlannerAttemptFailed,
    Stop,
    ToolCall,
    Usage,
)

#: Read from the environment, never from RunConfig -- docs/31 §4, the same
#: reason the planner mode is.
ENDPOINT_ENV = "AZURE_OPENAI_ENDPOINT"
KEY_ENV = "AZURE_OPENAI_API_KEY"
DEPLOYMENT_ENV = "AZURE_OPENAI_DEPLOYMENT"
API_VERSION_ENV = "AZURE_OPENAI_API_VERSION"
SNAPSHOT_ENV = "AEP_PLANNER_SNAPSHOT"

#: Pinned, not an alias. The author's fixed decision, recorded in the
#: pre-registration's preamble. Checked against what the response reports.
REASONING_EFFORT = "low"

#: The shape the planner must answer in. Structured output rather than free
#: text, because "zero malformed tool calls" is a stage criterion and a schema
#: is the only way to make it a property of the request instead of a hope.
RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision"],
    "properties": {
        "decision": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "tool", "action", "amount_minor", "reason"],
            "properties": {
                "kind": {"type": "string", "enum": ["call", "stop"]},
                "tool": {"type": "string"},
                "action": {"type": "string"},
                "amount_minor": {"type": "integer"},
                "reason": {"type": "string"},
            },
        }
    },
}


class MissingConfiguration(RuntimeError):
    """A live run was asked for and the environment does not describe one."""


class SnapshotMismatch(RuntimeError):
    """Azure served a model other than the pinned snapshot.

    Not retried and not tolerated. The pre-registration pins a snapshot rather
    than an alias precisely so that a silent server-side model change is a
    finding instead of a confound, and ``docs/33`` §3.2 is about exactly this:
    a hosted API is "a remote, versioned, silently-updated dependency".
    """


@dataclass(frozen=True)
class AzureConfig:
    endpoint: str
    deployment: str
    api_version: str
    snapshot: str
    reasoning_effort: str = REASONING_EFFORT

    @classmethod
    def from_environment(cls) -> "AzureConfig":
        missing = [
            name for name in (ENDPOINT_ENV, KEY_ENV, DEPLOYMENT_ENV,
                              API_VERSION_ENV, SNAPSHOT_ENV)
            if not (os.environ.get(name) or "").strip()
        ]
        if missing:
            raise MissingConfiguration(
                "a live planner run needs " + ", ".join(sorted(missing))
                + ". Nothing is guessed and nothing defaults: a live run that "
                "silently picked a deployment would spend money against a "
                "model the record does not name."
            )
        return cls(
            endpoint=os.environ[ENDPOINT_ENV].strip().rstrip("/"),
            deployment=os.environ[DEPLOYMENT_ENV].strip(),
            api_version=os.environ[API_VERSION_ENV].strip(),
            snapshot=os.environ[SNAPSHOT_ENV].strip(),
        )

    def url(self) -> str:
        return (
            f"{self.endpoint}/openai/deployments/{self.deployment}/responses"
            f"?api-version={self.api_version}"
        )


def api_key() -> str:
    """The one place the key is read. Returned, never stored on an object."""
    value = (os.environ.get(KEY_ENV) or "").strip()
    if not value:
        raise MissingConfiguration(f"{KEY_ENV} is not set")
    return value


class AzureCall:
    """One HTTP attempt, and the only thing in this repository that calls Azure.

    Invoked by ``CallWrapper.attempt`` and by nothing else. Carries the usage
    and identity fields back as attributes because that is the interface the
    wrapper reads them through after the call returns.
    """

    def __init__(
        self,
        config: AzureConfig,
        prompt: str,
        *,
        counter,
        reservation_key: str = "",
        timeout: float = 120.0,
    ):
        self.config = config
        self.prompt = prompt
        self._counter = counter
        self._timeout = timeout
        #: PUBLIC, and normally empty at construction. CallWrapper.attempt
        #: sets it immediately after appending the reservation and immediately
        #: before invoking. The name must match what the wrapper sets, and
        #: test_the_wrapper_and_the_client_agree_on_the_attribute_name pins
        #: that -- a private copy here would make the guard refuse every call,
        #: which is the safe direction but not a working experiment.
        self.reservation_key = reservation_key

        # What the wrapper reads back off the call object afterwards.
        self.usage = Usage()
        self.model = config.deployment
        self.snapshot = config.snapshot
        self.deployment = config.deployment
        self.api_version = config.api_version
        self.reasoning_effort = config.reasoning_effort
        self.sampling: dict[str, Any] = {
            "reasoning_effort": config.reasoning_effort,
        }
        #: What the response said it was, as distinct from what was asked for.
        self.served_model: str | None = None

    def __repr__(self) -> str:  # pragma: no cover - a safety property
        """No key, no prompt, no completion. A traceback is a file."""
        return (
            f"<AzureCall deployment={self.config.deployment!r} "
            f"snapshot={self.config.snapshot!r}>"
        )

    # -- the seam ----------------------------------------------------------
    def _refuse_if_uncounted(self) -> None:
        """The request may not go out ahead of its own reservation.

        Re-read from disk rather than trusted from memory: the point is that
        the count is durable before the money is spent, and a value held in
        this process proves nothing about what survives its death.
        """
        if not self.reservation_key:
            raise RuntimeError(
                "refusing to dispatch: this call carries no reservation key, "
                "so it was not created by CallWrapper.attempt. Every request "
                "must be counted before it is made "
                "(prompts/phase-40-agent-reachability.md §3)."
            )
        if not self._counter.has_key(self.reservation_key):
            raise RuntimeError(
                "refusing to dispatch: reservation "
                f"{self.reservation_key!r} is not in the cumulative journal. "
                "Every request must be counted before it is made "
                "(prompts/phase-40-agent-reachability.md §3)."
            )

    def __call__(self, *, max_output_tokens: int):
        self._refuse_if_uncounted()

        body = {
            "model": self.config.deployment,
            "input": [{"role": "user", "content": self.prompt}],
            "max_output_tokens": max_output_tokens,
            "reasoning": {"effort": self.config.reasoning_effort},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "planner_decision",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                }
            },
        }
        # retries=0 is the whole point of not using an SDK: one attempt per
        # counted attempt, so the count and the billed requests are the same
        # number.
        transport = httpx.HTTPTransport(retries=0)
        try:
            with httpx.Client(transport=transport,
                              timeout=self._timeout) as client:
                response = client.post(
                    self.config.url(),
                    headers={
                        "api-key": api_key(),
                        "content-type": "application/json",
                    },
                    content=json.dumps(body),
                )
        except httpx.HTTPError as exc:
            raise PlannerAttemptFailed(
                PlannerOutcome.RETRY, f"transport error: {type(exc).__name__}"
            ) from None

        return self._interpret(response)

    # -- reading the response ---------------------------------------------
    def _interpret(self, response: httpx.Response):
        if response.status_code == 429 or response.status_code >= 500:
            raise PlannerAttemptFailed(
                PlannerOutcome.RETRY,
                f"HTTP {response.status_code}",
            )
        if response.status_code != 200:
            detail = response.text[:300]
            if "content_filter" in detail or "ResponsibleAI" in detail:
                raise PlannerAttemptFailed(
                    PlannerOutcome.FILTERED, f"HTTP {response.status_code}"
                )
            raise PlannerAttemptFailed(
                PlannerOutcome.MALFORMED,
                f"HTTP {response.status_code}: {detail}",
            )

        payload = response.json()
        self._record_usage(payload)

        served = payload.get("model")
        self.served_model = served
        if served and served != self.config.snapshot:
            raise SnapshotMismatch(
                f"pinned snapshot is {self.config.snapshot!r} and Azure served "
                f"{served!r}. The pre-registration pins a snapshot rather than "
                f"an alias so that this is a finding, not a confound."
            )

        if payload.get("status") == "incomplete":
            reason = (payload.get("incomplete_details") or {}).get("reason")
            if reason == "content_filter":
                raise PlannerAttemptFailed(
                    PlannerOutcome.FILTERED, "incomplete: content_filter"
                )
            raise PlannerAttemptFailed(
                PlannerOutcome.MALFORMED, f"incomplete: {reason}"
            )

        return self._decision(payload)

    def _record_usage(self, payload: dict[str, Any]) -> None:
        usage = payload.get("usage") or {}
        details = usage.get("output_tokens_details") or {}
        reasoning = int(details.get("reasoning_tokens", 0))
        output = int(usage.get("output_tokens", 0))
        # The API reports reasoning tokens inside output_tokens. Usage keeps
        # them apart and bills both, so completion is the remainder.
        self.usage = Usage(
            prompt_tokens=int(usage.get("input_tokens", 0)),
            completion_tokens=max(output - reasoning, 0),
            reasoning_tokens=reasoning,
        )

    def _decision(self, payload: dict[str, Any]):
        text = _output_text(payload)
        if not text:
            raise PlannerAttemptFailed(
                PlannerOutcome.MALFORMED, "response carried no output text"
            )
        try:
            decision = json.loads(text)["decision"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise PlannerAttemptFailed(
                PlannerOutcome.MALFORMED, f"{type(exc).__name__}: {text[:200]}"
            ) from None

        if decision.get("kind") == "stop":
            return Stop(str(decision.get("reason", "stop")))
        try:
            return ToolCall(
                tool=str(decision["tool"]),
                action=str(decision["action"]),
                amount_minor=int(decision["amount_minor"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PlannerAttemptFailed(
                PlannerOutcome.MALFORMED, f"{type(exc).__name__}: {text[:200]}"
            ) from None


def _output_text(payload: dict[str, Any]) -> str:
    """Pull the assistant text out of a Responses payload.

    Tolerant of the shape, strict about the content: reasoning items carry no
    text and must be skipped rather than treated as an empty answer.
    """
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") in ("output_text", "text"):
                chunks.append(part.get("text", ""))
    return "".join(chunks)
