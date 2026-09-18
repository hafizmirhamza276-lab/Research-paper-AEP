"""The live transport, tested without touching the network.

**The question this file exists to answer is "can anything reach Azure without
being counted first".** Every other property here is secondary to that one,
because it is the only ceiling: there is no spending cap set on the Azure side,
so the code is it.

Three independent things have to hold, and each is asserted rather than
reasoned about:

1. There is exactly one place in the repository that makes an HTTP request to
   Azure — ``AzureCall.__call__``.
2. That method refuses unless its reservation is **already on disk** in the
   cumulative journal. Not in memory: on disk, re-read, because the guarantee
   is about what survives a `SIGKILL`.
3. The wrapper and the client agree on the attribute name the reservation
   travels under. They did not, at first — the wrapper set ``reservation_key``
   and the client read ``_reservation_key``, which would have refused every
   call in the collection. That is the safe direction, but a guard that always
   fires is not evidence that a guard works, so the agreement is pinned.

No test here performs real I/O. ``httpx.Client.post`` is replaced, and
``test_no_test_in_this_file_can_reach_the_network`` checks that the replacement
is what ran.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from experiments.harness import azure_client
from experiments.harness.azure_client import (
    ROUTE_DEPLOYMENT,
    ROUTE_FLAT,
    AzureCall,
    AzureConfig,
    MissingConfiguration,
    SnapshotMismatch,
)
from experiments.harness.planner import (
    CallWrapper,
    Caps,
    CumulativeCounter,
    PlannerAttemptFailed,
    PlannerOutcome,
    Stop,
    ToolCall,
    reservation_key,
)

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "experiments" / "harness"

CONFIG = AzureConfig(
    endpoint="https://example-resource.openai.azure.com",
    deployment="luna-dep",
    api_version="2026-08-01-preview",
    snapshot="gpt-5.6-luna-2026-07-09",
)


def _payload(text: str = None, **over):
    body = {
        "model": CONFIG.snapshot,
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [
                {"type": "output_text", "text": text if text is not None else
                 json.dumps({"decision": {
                     "kind": "call", "tool": "send_notification",
                     "action": "capture", "amount_minor": 250,
                     "reason": "first attempt"}})},
            ]},
        ],
        "usage": {
            "input_tokens": 812,
            "output_tokens": 240,
            "output_tokens_details": {"reasoning_tokens": 192},
        },
    }
    body.update(over)
    return body


class _Recorder:
    """Stands in for the network. Records what would have gone out."""

    def __init__(self, status=200, payload=None, text=None, raises=None):
        self.status = status
        self.payload = payload
        self.text = text
        self.raises = raises
        self.requests = []

    def __call__(self, url, *, headers=None, content=None, **kw):
        self.requests.append(
            {"url": url, "headers": dict(headers or {}), "content": content}
        )
        if self.raises:
            raise self.raises
        body = self.payload if self.payload is not None else _payload()
        return httpx.Response(
            self.status,
            content=self.text if self.text is not None else json.dumps(body),
            headers={"content-type": "application/json"},
            request=httpx.Request("POST", url),
        )


@pytest.fixture
def recorder(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(httpx.Client, "post", lambda self, url, **kw: rec(url, **kw))
    monkeypatch.setenv(azure_client.KEY_ENV, "test-key-not-real")
    return rec


def _counted(tmp_path, prompt="p"):
    """A call whose reservation really is on disk, the way the wrapper does it."""
    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    key = reservation_key("r0", 0, 0, 1)
    counter.add(1, 0.0, key=key, run_id="r0")
    call = AzureCall(CONFIG, prompt, counter=counter)
    call.reservation_key = key
    return call, counter


# ---------------------------------------------------------------------------
# 1. Nothing reaches Azure uncounted
# ---------------------------------------------------------------------------

def test_a_call_with_no_reservation_key_refuses_to_dispatch(tmp_path, recorder):
    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    call = AzureCall(CONFIG, "p", counter=counter)
    with pytest.raises(RuntimeError, match="no reservation key"):
        call(max_output_tokens=1024)
    assert recorder.requests == [], "a request went out uncounted"


def test_a_call_whose_reservation_is_not_on_disk_refuses(tmp_path, recorder):
    """In memory is not good enough; the guarantee is about surviving a crash."""
    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    call = AzureCall(CONFIG, "p", counter=counter)
    call.reservation_key = reservation_key("r0", 0, 0, 1)  # never appended
    with pytest.raises(RuntimeError, match="not in the cumulative journal"):
        call(max_output_tokens=1024)
    assert recorder.requests == []


def test_a_counted_call_does_dispatch(tmp_path, recorder):
    """R2's known-positive: prove the two refusals above are not vacuous."""
    call, _ = _counted(tmp_path)
    result = call(max_output_tokens=1024)
    assert isinstance(result, ToolCall)
    assert len(recorder.requests) == 1


def test_the_wrapper_and_the_client_agree_on_the_attribute_name(tmp_path, recorder):
    """The bug that would have refused every call in the collection.

    The wrapper sets ``reservation_key``; the client read ``_reservation_key``.
    Checked end to end through the wrapper rather than by comparing strings.
    """
    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    wrapper = CallWrapper("r0", tmp_path / "run", counter)
    call = AzureCall(CONFIG, "p", counter=counter)
    assert call.reservation_key == ""
    wrapper.attempt(worker_index=0, step_index=0, attempt=1, prompt="p",
                    call=call)
    assert call.reservation_key == reservation_key("r0", 0, 0, 1)
    assert len(recorder.requests) == 1


def test_the_reservation_is_on_disk_before_the_request_goes_out(tmp_path,
                                                                recorder):
    """Ordering, observed from inside the dispatch rather than inferred."""
    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    wrapper = CallWrapper("r0", tmp_path / "run", counter)
    call = AzureCall(CONFIG, "p", counter=counter)

    seen = {}
    original = call._refuse_if_uncounted

    def watching():
        seen["calls_on_disk"] = counter.read()["calls"]
        return original()

    call._refuse_if_uncounted = watching
    wrapper.attempt(worker_index=0, step_index=0, attempt=1, prompt="p",
                    call=call)
    assert seen["calls_on_disk"] == 1


#: The one other module in the harness that opens an HTTP client. It drives
#: toxiproxy's control API on 127.0.0.1 to create and remove network faults;
#: it has no Azure configuration and cannot reach a model. Named explicitly so
#: that a *third* one has to be argued for rather than merely added.
NON_AZURE_HTTP = {"faults.py"}


def test_only_one_place_in_the_harness_can_reach_azure():
    """Structural. A second transport would be a second, uncounted door."""
    clients, azure_aware = [], []
    for path in sorted(HARNESS.rglob("*.py")):
        if "tests" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        if any(token in source for token in
               ("httpx.Client", "httpx.AsyncClient", "requests.post",
                "urllib.request", "http.client")):
            clients.append(path.name)
        if "openai.azure.com" in source or "AZURE_OPENAI" in source:
            azure_aware.append(path.name)

    assert set(clients) - NON_AZURE_HTTP == {"azure_client.py"}, clients
    # Knowing where Azure is, and being able to open a socket, meet in exactly
    # one file.
    assert set(clients) & set(azure_aware) == {"azure_client.py"}
    assert "AZURE_OPENAI" not in (
        HARNESS / "faults.py").read_text(encoding="utf-8")


def test_the_transport_does_not_retry():
    """§3: an SDK retry inside one call is an attempt that is not capped."""
    source = (HARNESS / "azure_client.py").read_text(encoding="utf-8")
    assert "httpx.HTTPTransport(retries=0)" in source


# ---------------------------------------------------------------------------
# 2. The key never lands anywhere
# ---------------------------------------------------------------------------

def test_the_key_is_sent_in_a_header_and_held_nowhere(tmp_path, recorder):
    call, _ = _counted(tmp_path)
    call(max_output_tokens=1024)
    assert recorder.requests[0]["headers"]["api-key"] == "test-key-not-real"
    # Not on the object, not in its repr.
    assert "test-key-not-real" not in repr(call)
    assert "test-key-not-real" not in json.dumps(
        {k: str(v) for k, v in vars(call).items()}
    )


def test_the_repr_carries_no_prompt_and_no_key(tmp_path, recorder):
    """A traceback prints arguments, and a traceback is a file."""
    call, _ = _counted(tmp_path, prompt="SENSITIVE-PROMPT-TEXT")
    assert "SENSITIVE-PROMPT-TEXT" not in repr(call)


# ---------------------------------------------------------------------------
# 3. The pinned snapshot
# ---------------------------------------------------------------------------

def test_a_different_served_model_is_a_finding_not_a_retry(tmp_path, recorder):
    recorder.payload = _payload(model="gpt-5.6-luna-2026-11-30")
    call, _ = _counted(tmp_path)
    with pytest.raises(SnapshotMismatch, match="2026-11-30"):
        call(max_output_tokens=1024)


def test_the_pinned_snapshot_passes(tmp_path, recorder):
    call, _ = _counted(tmp_path)
    call(max_output_tokens=1024)
    assert call.served_model == CONFIG.snapshot


# ---------------------------------------------------------------------------
# 4. What the request asks for
# ---------------------------------------------------------------------------

def test_the_request_pins_effort_and_bounds_the_output(tmp_path, recorder):
    call, _ = _counted(tmp_path)
    call(max_output_tokens=1024)
    body = json.loads(recorder.requests[0]["content"])
    assert body["reasoning"] == {"effort": "low"}
    assert body["max_output_tokens"] == 1024
    assert body["model"] == CONFIG.deployment
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True


def test_reasoning_tokens_are_counted_as_output(tmp_path, recorder):
    """They bill as output. Counting them apart would understate the spend."""
    call, _ = _counted(tmp_path)
    call(max_output_tokens=1024)
    assert call.usage.prompt_tokens == 812
    assert call.usage.reasoning_tokens == 192
    assert call.usage.completion_tokens == 48
    assert call.usage.output == 240


# ---------------------------------------------------------------------------
# 5. Failure classes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", [429, 500, 503])
def test_throttling_and_server_errors_are_retryable(tmp_path, recorder, status):
    recorder.status = status
    call, _ = _counted(tmp_path)
    with pytest.raises(PlannerAttemptFailed) as raised:
        call(max_output_tokens=1024)
    assert raised.value.outcome is PlannerOutcome.RETRY


def test_a_content_filter_is_its_own_class(tmp_path, recorder):
    recorder.status = 400
    recorder.text = '{"error": {"code": "content_filter"}}'
    call, _ = _counted(tmp_path)
    with pytest.raises(PlannerAttemptFailed) as raised:
        call(max_output_tokens=1024)
    assert raised.value.outcome is PlannerOutcome.FILTERED


def test_an_incomplete_response_from_the_filter_is_also_filtered(tmp_path,
                                                                 recorder):
    recorder.payload = _payload(
        status="incomplete", incomplete_details={"reason": "content_filter"})
    call, _ = _counted(tmp_path)
    with pytest.raises(PlannerAttemptFailed) as raised:
        call(max_output_tokens=1024)
    assert raised.value.outcome is PlannerOutcome.FILTERED


def test_unparseable_output_is_malformed(tmp_path, recorder):
    recorder.payload = _payload(text="I'm afraid I can't do that")
    call, _ = _counted(tmp_path)
    with pytest.raises(PlannerAttemptFailed) as raised:
        call(max_output_tokens=1024)
    assert raised.value.outcome is PlannerOutcome.MALFORMED


def test_a_stop_decision_is_understood(tmp_path, recorder):
    recorder.payload = _payload(text=json.dumps({"decision": {
        "kind": "stop", "tool": "", "action": "", "amount_minor": 0,
        "reason": "nothing further warranted"}}))
    call, _ = _counted(tmp_path)
    assert isinstance(call(max_output_tokens=1024), Stop)


def test_a_transport_error_does_not_leak_the_url_or_the_key(tmp_path, recorder):
    recorder.raises = httpx.ConnectError("boom")
    call, _ = _counted(tmp_path)
    with pytest.raises(PlannerAttemptFailed) as raised:
        call(max_output_tokens=1024)
    assert raised.value.outcome is PlannerOutcome.RETRY
    assert "test-key-not-real" not in str(raised.value)


# ---------------------------------------------------------------------------
# 6. Configuration
# ---------------------------------------------------------------------------

def test_nothing_is_guessed_when_the_environment_is_incomplete(monkeypatch):
    for name in (azure_client.ENDPOINT_ENV, azure_client.KEY_ENV,
                 azure_client.DEPLOYMENT_ENV, azure_client.API_VERSION_ENV,
                 azure_client.SNAPSHOT_ENV):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(MissingConfiguration) as raised:
        AzureConfig.from_environment()
    for name in (azure_client.ENDPOINT_ENV, azure_client.DEPLOYMENT_ENV,
                 azure_client.SNAPSHOT_ENV):
        assert name in str(raised.value)


def test_the_url_names_the_deployment_and_the_api_version():
    url = CONFIG.url()
    assert url.startswith("https://example-resource.openai.azure.com/openai/")
    assert "/deployments/luna-dep/responses" in url
    assert "api-version=2026-08-01-preview" in url


def test_no_test_in_this_file_can_reach_the_network(tmp_path, recorder):
    """The fixture is what ran, not the real client."""
    call, _ = _counted(tmp_path)
    call(max_output_tokens=1024)
    assert len(recorder.requests) == 1
    assert recorder.requests[0]["url"] == CONFIG.url()


def test_a_throttled_attempt_raises_rather_than_returning_none(tmp_path,
                                                               recorder):
    """The bug this file found before any money was spent.

    RETRY fell through to ``return result``, which is None. The loop would have
    treated that as a decision and died on ``None.action``; ``_ask``'s retry
    never ran, because nothing was raised. Nothing in stub mode produces RETRY,
    so nothing had exercised it -- and the live client produces it for every
    429 and every 5xx.
    """
    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    wrapper = CallWrapper("r0", tmp_path / "run", counter)
    recorder.status = 429
    call = AzureCall(CONFIG, "p", counter=counter)
    with pytest.raises(PlannerAttemptFailed) as raised:
        wrapper.attempt(worker_index=0, step_index=0, attempt=1, prompt="p",
                        call=call)
    assert raised.value.outcome is PlannerOutcome.RETRY
    # Counted even though it produced nothing: §3, a retry that is not counted
    # is a retry that is not capped.
    assert counter.read()["calls"] == 1
    entries = wrapper.transcript.entries()
    assert len(entries) == 1
    assert entries[0]["outcome"] == PlannerOutcome.RETRY.value


# ---------------------------------------------------------------------------
# 7. The route. Established by two 404s against the real resource, 2026-09-18.
# ---------------------------------------------------------------------------

def test_the_flat_route_is_the_one_that_resolves_on_foundry():
    """What the probes found, kept so nobody has to spend to find it again.

    ``https://kps-rnd-foundry.cognitiveservices.azure.com``:

      /openai/deployments/gpt-5.6-luna/responses?api-version=2025-01-01-preview
          404 Resource not found
      /openai/deployments/gpt-5.6-luna/responses?api-version=2025-04-01-preview
          404 Resource not found   <- so it is the route, not the version
      /openai/responses?api-version=2025-04-01-preview
          200, model=gpt-5.6-luna, 93 in / 123 out / 71 reasoning

    An AI Foundry resource serves the flat route with the deployment in the
    body; the per-deployment path is an Azure OpenAI resource shape and is not
    present here at any api-version tried.
    """
    flat = AzureConfig(endpoint="https://x.cognitiveservices.azure.com",
                       deployment="dep", api_version="2025-04-01-preview",
                       snapshot="s", route=ROUTE_FLAT)
    assert flat.url() == (
        "https://x.cognitiveservices.azure.com/openai/responses"
        "?api-version=2025-04-01-preview"
    )
    assert "/deployments/" not in flat.url()


def test_the_deployment_travels_in_the_body_on_both_routes(tmp_path, recorder):
    """Which is why switching routes needs no other change."""
    for route in (ROUTE_DEPLOYMENT, ROUTE_FLAT):
        counter = CumulativeCounter(tmp_path / f"c-{route}.json")
        key = reservation_key("r0", 0, 0, 1)
        counter.add(1, 0.0, key=key, run_id="r0")
        config = AzureConfig(endpoint=CONFIG.endpoint,
                             deployment=CONFIG.deployment,
                             api_version=CONFIG.api_version,
                             snapshot=CONFIG.snapshot, route=route)
        call = AzureCall(config, "p", counter=counter)
        call.reservation_key = key
        call(max_output_tokens=1024)
        body = json.loads(recorder.requests[-1]["content"])
        assert body["model"] == CONFIG.deployment


def test_the_default_route_is_the_per_deployment_one():
    """Unchanged for an ordinary Azure OpenAI resource."""
    assert AzureConfig("https://e", "d", "v", "s").route == ROUTE_DEPLOYMENT
    assert "/deployments/d/responses" in AzureConfig("https://e", "d", "v",
                                                     "s").url()


def test_an_unknown_route_refuses_rather_than_guessing():
    config = AzureConfig("https://e", "d", "v", "s", route="sideways")
    with pytest.raises(MissingConfiguration, match="sideways"):
        config.url()


def test_the_route_can_be_set_from_the_environment(monkeypatch):
    for name, value in ((azure_client.ENDPOINT_ENV, "https://e"),
                        (azure_client.KEY_ENV, "k"),
                        (azure_client.DEPLOYMENT_ENV, "d"),
                        (azure_client.API_VERSION_ENV, "v"),
                        (azure_client.SNAPSHOT_ENV, "s")):
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(azure_client.ROUTE_ENV, raising=False)
    assert AzureConfig.from_environment().route == ROUTE_DEPLOYMENT
    monkeypatch.setenv(azure_client.ROUTE_ENV, ROUTE_FLAT)
    assert AzureConfig.from_environment().route == ROUTE_FLAT
