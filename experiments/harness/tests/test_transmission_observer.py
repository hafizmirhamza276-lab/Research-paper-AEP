"""The transmission observer marks the boundary and changes nothing else.

Phase 13's prerequisite instrumentation. The observer sits on the protocol's
dispatch path, so the thing that has to be tested is not mainly that it emits --
it is that it is **transparent**: a wrapper that altered a return value, or
converted one exception into another, would change an execution's outcome class
silently, because `intent_workflow.py:616-624` classifies connector exceptions
as ambiguous and a retyped exception is a different classification.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from experiments.harness.injector import TransmissionObserver


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def __call__(self, event: str, **fields) -> None:
        self.events.append((event, fields))

    def names(self) -> list[str]:
        return [name for name, _ in self.events]


def _dispatch(execution_id: str = "exec-1") -> SimpleNamespace:
    return SimpleNamespace(
        binding=SimpleNamespace(
            execution_id=execution_id, intent_id="intent-1", step_id="charge-card"
        )
    )


class _Connector:
    """Enough of a connector to be wrapped, and nothing more."""

    def __init__(self, *, result=None, error: BaseException | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict] = []
        self.closed = False

    async def mutate(self, *, dispatch, client_timeout):
        self.calls.append({"dispatch": dispatch, "client_timeout": client_timeout})
        if self.error is not None:
            raise self.error
        return self.result

    async def aclose(self) -> None:
        self.closed = True

    @property
    def reconciliation_capability(self) -> str:
        return "NO_READBACK"


def test_the_event_precedes_the_call_and_the_response_event_follows_it() -> None:
    order: list[str] = []
    recorder = _Recorder()

    class Ordered(_Connector):
        async def mutate(self, *, dispatch, client_timeout):
            order.append("connector.mutate")
            return "response"

    def emit(event: str, **fields) -> None:
        order.append(event)
        recorder(event, **fields)

    observer = TransmissionObserver(connector=Ordered(), emit=emit)
    result = asyncio.run(observer.mutate(dispatch=_dispatch(), client_timeout=5.0))

    assert result == "response"
    # The boundary claim: nothing reaches the provider before the event.
    assert order == [
        "provider_request_transmitted",
        "connector.mutate",
        "provider_response_received",
    ]
    transmitted = dict(recorder.events[0][1])
    assert transmitted["execution_id"] == "exec-1"
    assert transmitted["intent_id"] == "intent-1"
    assert "elapsed_ns" in recorder.events[1][1]


def test_the_return_value_is_passed_through_untouched() -> None:
    sentinel = object()
    connector = _Connector(result=sentinel)
    observer = TransmissionObserver(connector=connector, emit=_Recorder())
    returned = asyncio.run(observer.mutate(dispatch=_dispatch(), client_timeout=2.0))
    assert returned is sentinel
    assert connector.calls[0]["client_timeout"] == 2.0


def test_an_exception_is_re_raised_as_itself_not_wrapped() -> None:
    """A retyped exception would be a different outcome class, silently."""
    original = TimeoutError("provider timed out")
    recorder = _Recorder()
    observer = TransmissionObserver(
        connector=_Connector(error=original), emit=recorder
    )
    with pytest.raises(TimeoutError) as caught:
        asyncio.run(observer.mutate(dispatch=_dispatch(), client_timeout=1.0))
    assert caught.value is original
    assert recorder.names() == [
        "provider_request_transmitted",
        "provider_request_failed",
    ]


def test_a_base_exception_is_not_caught() -> None:
    """Simulated process death derives from BaseException and must pass through.

    `experiments/harness/injector.py` raises it to end the worker; a wrapper
    that caught it would turn a crash into an ordinary ambiguous dispatch and
    the run would look successful.
    """

    class SimulatedDeath(BaseException):
        pass

    death = SimulatedDeath()
    recorder = _Recorder()
    observer = TransmissionObserver(connector=_Connector(error=death), emit=recorder)
    with pytest.raises(SimulatedDeath) as caught:
        asyncio.run(observer.mutate(dispatch=_dispatch(), client_timeout=1.0))
    assert caught.value is death
    assert "provider_request_failed" in recorder.names()


def test_every_other_attribute_reaches_the_wrapped_connector() -> None:
    connector = _Connector()
    observer = TransmissionObserver(connector=connector, emit=_Recorder())
    assert observer.reconciliation_capability == "NO_READBACK"
    asyncio.run(observer.aclose())
    assert connector.closed is True


def test_a_dispatch_without_a_binding_still_emits_rather_than_raising() -> None:
    """Evidence must not be able to break the protocol path it observes."""
    recorder = _Recorder()
    observer = TransmissionObserver(connector=_Connector(result=None), emit=recorder)
    asyncio.run(observer.mutate(dispatch=SimpleNamespace(), client_timeout=1.0))
    assert recorder.names()[0] == "provider_request_transmitted"
    assert recorder.events[0][1]["execution_id"] is None
