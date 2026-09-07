"""B5's Temporal worker: one workflow, one activity that calls the mock provider.

**Not a collection harness.** This module exists so WS-6's open questions can be
closed by measurement rather than by reading documentation, and so the crash
injector has a real SDK worker to be proven against. It deliberately does not
import anything from ``aep_core``: the protocol under measurement must not depend
on the thing measuring it, and B5 is not the protocol anyway.

**The crash points are the SDK's, not ``aep_core``'s.** There is no
``_checkpoint`` here to hook. A named point is reached inside an activity or
workflow callback, and the injector kills this process there --- which is why
``B5_SEMANTICS.md`` §7 question 5 said the delivery mechanism has to be rebuilt
and proven able to fail rather than assumed to carry over.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

with workflow.unsafe.imports_passed_through():
    import httpx


TASK_QUEUE = "b5-ws6"

#: The named points this worker announces it can be cut at. These are B5's own
#: vocabulary, exactly as ``BaselineCrashPoint`` is B0--B4's; the mapping from
#: the roadmap's six names lives in ``B5_SEMANTICS.md`` §2.1 and in
#: :data:`ROADMAP_TO_B5` below.
B5_POINTS = (
    "BEFORE_SCHEDULE_ACTIVITY",       # roadmap: before_intent_write (approx)
    "ACTIVITY_ENTERED_BEFORE_CALL",   # roadmap: after_barrier_before_dispatch
    "DURING_PROVIDER_CALL",           # roadmap: mid_dispatch (deferred)
    "AFTER_RESPONSE_BEFORE_RETURN",   # roadmap: after_response_before_resolution
    "DURING_COMPLETE_RPC",            # roadmap: after_resolution_before_barrier
)

#: The roadmap's six names -> B5's positions, or ``None`` where B5 has no such
#: moment. Same shape and same meaning as
#: ``experiments/baselines/crash_points.py``: ``None`` is *this system has no
#: such moment*, never *no crash*.
ROADMAP_TO_B5 = {
    "before_intent_write": "BEFORE_SCHEDULE_ACTIVITY",
    # The worker issues an RPC and the SERVER persists transactionally before
    # replying, so no worker-side instant exists at which the record is written
    # and unacknowledged. See B5_SEMANTICS.md 2.3.
    "after_intent_before_barrier": None,
    "after_barrier_before_dispatch": "ACTIVITY_ENTERED_BEFORE_CALL",
    "mid_dispatch": "DURING_PROVIDER_CALL",
    "after_response_before_resolution": "AFTER_RESPONSE_BEFORE_RETURN",
    "after_resolution_before_barrier": "DURING_COMPLETE_RPC",
}

DEFERRED_B5_POINTS = frozenset({"DURING_PROVIDER_CALL"})


class B5CrashPointNotApplicable(LookupError):
    """B5 has no moment answering to that roadmap crash point."""


def resolve_b5_point(name: str | None) -> str | None:
    """Roadmap or canonical name -> B5 point. Refuses anything else.

    Mirrors ``experiments.baselines.crash_points.resolve_for_system``: an absent
    moment raises rather than returning ``None``, because ``None`` already means
    "no crash injection" and a caller that confused the two would run a full
    cell whose fault was never delivered.
    """
    if not name:
        return None
    if name in ROADMAP_TO_B5:
        resolved = ROADMAP_TO_B5[name]
        if resolved is None:
            raise B5CrashPointNotApplicable(
                f"B5 has no position answering to {name!r}: the worker issues "
                f"an RPC and the server persists it transactionally, so there "
                f"is no worker-side window between the write and its "
                f"acknowledgement"
            )
        return resolved
    if name in B5_POINTS:
        return name
    raise KeyError(
        f"unknown crash point {name!r} for B5; roadmap names: "
        f"{sorted(ROADMAP_TO_B5)}; canonical names: {sorted(B5_POINTS)}"
    )


# ----------------------------------------------------------------- injection

#: Read ONCE, at module import, outside any workflow.
#:
#: The first version read these inside ``_maybe_die``, which is called from
#: workflow code, and Temporal's workflow sandbox refused:
#:
#:     RestrictedWorkflowAccessError: Cannot access os.environ.get from inside
#:     a workflow
#:
#: The sandbox is right to refuse -- a workflow must be deterministic on replay
#: and the environment is not. Reading at import makes the value a module
#: constant that replay cannot observe changing, which is both sandbox-legal and
#: the more correct thing regardless of the sandbox.
_ARMED_POINT = os.environ.get("B5_CRASH_POINT") or None
_TRACE_PATH = os.environ.get("B5_TRACE") or None
_INJECTOR_DISABLED = os.environ.get("B5_INJECTOR_DISABLED") == "1"
_DEFER_MS = int(os.environ.get("B5_DEFER_MS", "40"))
_COMPLETE_DEFER_MS = int(os.environ.get("B5_COMPLETE_DEFER_MS", "1"))
_PROVIDER_URL = os.environ.get("B5_PROVIDER_URL", "http://127.0.0.1:8099")


def _trace(event: str, **fields) -> None:
    """Append one JSON line to the trace the probe reads.

    Written and flushed synchronously: the process is about to be SIGKILLed, and
    a buffered line is a line that does not survive the thing it is recording.
    """
    path = _TRACE_PATH
    if not path:
        return
    record = {"event": event, "wall_ms": round(time.time() * 1000), **fields}
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _maybe_die(point: str) -> None:
    """Die here if this is the armed point. SIGKILL, not exit.

    ``os.kill(os.getpid(), SIGKILL)`` rather than ``sys.exit``: the fault under
    test is a worker that stops existing without unwinding, and an exit would
    let the SDK report a clean activity failure -- a different experiment.

    **Always records reaching the point, whether or not it fires.** That record
    is what the gate reads: a run whose armed point produced no
    ``b5_point_reached`` is a run the injector never got to, and it must void
    rather than be reported as an outcome.
    """
    if point == _ARMED_POINT:
        _trace("b5_point_reached", point=point, pid=os.getpid(),
               fires=not _INJECTOR_DISABLED)
    if point != _ARMED_POINT or _INJECTOR_DISABLED:
        return
    _trace("b5_crash_firing", point=point, pid=os.getpid())
    os.kill(os.getpid(), signal.SIGKILL)


def _arm_deferred(point: str, delay_ms: int) -> None:
    """Deferred delivery for the one point inside a socket wait.

    ``mid_dispatch`` names an instant the caller never executes, so it is armed
    at the last instruction before transmission and delivered by a watchdog
    thread -- the same technique, and for the same reason, as
    ``harness/crash_points.py``'s ``DEFERRED_CRASH_POINTS``.
    """
    if point != _ARMED_POINT:
        return
    _trace("b5_point_reached", point=point, pid=os.getpid(),
           fires=not _INJECTOR_DISABLED)
    if _INJECTOR_DISABLED:
        return
    import threading

    def fire() -> None:
        time.sleep(delay_ms / 1000.0)
        _trace("b5_crash_firing", point=point, pid=os.getpid(), deferred=True)
        os.kill(os.getpid(), signal.SIGKILL)

    _trace("b5_crash_armed", point=point, delay_ms=delay_ms)
    threading.Thread(target=fire, daemon=True).start()


# ------------------------------------------------------------------ workload

@dataclass
class MutateRequest:
    target: str
    action: str
    amount_minor: int
    client_reference: str
    endpoint: str = "ledger_postings"


@activity.defn(name="b5_mutate")
async def b5_mutate(request: dict) -> dict:
    """One non-idempotent provider mutation, with three crash points in it."""
    _trace("b5_activity_started", attempt=activity.info().attempt)

    _maybe_die("ACTIVITY_ENTERED_BEFORE_CALL")
    _arm_deferred("DURING_PROVIDER_CALL", _DEFER_MS)

    # The provider's real contract, read from experiments/mock_api/service.py:
    # POST /v1/endpoints/{name}/mutations, with the caller reference in a
    # header rather than the body. An earlier version of this file posted to
    # /{endpoint} with the reference inline; nothing rejected it loudly, which
    # is why it was checked against the service rather than assumed.
    base = _PROVIDER_URL
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base}/v1/endpoints/{request['endpoint']}/mutations",
            headers={"X-Aep-Client-Reference": request["client_reference"]},
            # The envelope the oracle can fingerprint. A flat body is refused
            # 422 "missing ['connector_operation', 'operation_version',
            # 'public_fields']" in under 2 ms -- fast enough to look like a
            # healthy provider to anything that only checks for a 5xx.
            json={
                "connector_operation": "post_ledger_entry",
                "target": request["target"],
                "operation_version": "1",
                "public_fields": [
                    {"name": "target", "value": request["target"]},
                    {"name": "action", "value": request["action"]},
                    {"name": "amount_minor", "value": request["amount_minor"]},
                ],
            },
        )
    elapsed_ms = (time.monotonic() - started) * 1000.0
    _trace("b5_provider_returned", status=response.status_code,
           elapsed_ms=round(elapsed_ms, 3), attempt=activity.info().attempt)

    _maybe_die("AFTER_RESPONSE_BEFORE_RETURN")

    # DURING_COMPLETE_RPC is armed here, not fired: the RPC that reports this
    # result starts after the activity function returns, so the only way to die
    # inside it is a watchdog armed on the last instruction before the return.
    _arm_deferred("DURING_COMPLETE_RPC", _COMPLETE_DEFER_MS)

    return {"status": response.status_code, "elapsed_ms": elapsed_ms}


@workflow.defn(name="B5Workflow")
class B5Workflow:
    @workflow.run
    async def run(self, request: dict) -> dict:
        if not workflow.unsafe.is_replaying():
            _maybe_die("BEFORE_SCHEDULE_ACTIVITY")
        attempts = int(request.get("maximum_attempts", 0))
        return await workflow.execute_activity(
            b5_mutate,
            request,
            start_to_close_timeout=timedelta(
                milliseconds=int(request.get("start_to_close_ms", 5000))
            ),
            retry_policy=RetryPolicy(
                maximum_attempts=attempts,          # 0 = unlimited (B5); 1 = B5b
                backoff_coefficient=1.0,
                initial_interval=timedelta(
                    milliseconds=int(request.get("retry_interval_ms", 200))
                ),
                maximum_interval=timedelta(
                    milliseconds=int(request.get("retry_interval_ms", 200))
                ),
            ),
        )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--address", default="127.0.0.1:7233")
    parser.add_argument("--task-queue", default=TASK_QUEUE)
    parser.add_argument("--ready-file", default=None)
    arguments = parser.parse_args()

    client = await Client.connect(arguments.address)
    _trace("b5_worker_connected", pid=os.getpid())
    if arguments.ready_file:
        Path(arguments.ready_file).write_text(str(os.getpid()), encoding="utf-8")

    async with Worker(
        client,
        task_queue=arguments.task_queue,
        workflows=[B5Workflow],
        activities=[b5_mutate],
        # The workflow sandbox is disabled DELIBERATELY, and the trade is
        # recorded rather than buried. The injector must write a trace line and
        # SIGKILL itself from inside workflow code, and both are I/O the sandbox
        # forbids for the same reason it forbade reading the environment.
        #
        # What is given up: the sandbox is what mechanically catches workflow
        # nondeterminism. B5Workflow is one activity call with no clocks, no
        # randomness and no I/O of its own except the injector, so there is
        # little for it to catch -- but little is not nothing, and B5's
        # workflow determinism is therefore argued rather than machine-checked.
        workflow_runner=UnsandboxedWorkflowRunner(),
    ):
        _trace("b5_worker_running", pid=os.getpid())
        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
