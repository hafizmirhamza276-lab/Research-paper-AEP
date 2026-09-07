"""Close WS-6's open questions 2-5 by measurement on the real stack.

Not a collection. Nothing here writes a run directory, and no result from it may
appear as a B5 rate. It exists to answer four questions the pre-registration says
must be closed before any data commit, each by running the real engine rather
than by reading documentation.

Run with the stack already up and a mock provider already listening.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from temporalio.client import Client

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def emit(section: str, **fields) -> None:
    print(f"  {section}: " + "  ".join(f"{k}={v}" for k, v in fields.items()))


# ---------------------------------------------------------------- Q2 part one

async def provider_latency(url: str, endpoint: str, n: int) -> list[float]:
    """The provider's response-time distribution -- what a timeout must clear."""
    samples: list[float] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for index in range(n):
            started = time.monotonic()
            await client.post(
                f"{url}/v1/endpoints/{endpoint}/mutations",
                headers={"X-Aep-Client-Reference": f"probe-lat-{uuid.uuid4()}"},
                json={
                    "target": f"probe-latency-{index}",
                    "action": "post",
                    "amount_minor": 100,
                },
            )
            samples.append((time.monotonic() - started) * 1000.0)
    return samples


# --------------------------------------------------------------------- runner

async def run_one(
    client: Client,
    *,
    crash_point: str | None,
    maximum_attempts: int,
    start_to_close_ms: int,
    provider_url: str,
    trace: Path,
    deadline_s: float,
    worker_env: dict | None = None,
) -> dict:
    """Start a worker, run one workflow, return what happened.

    The worker is a *child process* so it can be SIGKILLed from inside itself at
    a named point -- which is the fault under test.
    """
    trace.write_text("", encoding="utf-8")
    env = dict(os.environ)
    env["B5_TRACE"] = str(trace)
    env["B5_PROVIDER_URL"] = provider_url
    if crash_point:
        env["B5_CRASH_POINT"] = crash_point
    else:
        env.pop("B5_CRASH_POINT", None)
    env.update(worker_env or {})

    ready = trace.with_suffix(".ready")
    ready.unlink(missing_ok=True)
    worker = subprocess.Popen(
        [sys.executable, str(HERE / "worker.py"), "--ready-file", str(ready)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    for _ in range(200):
        if ready.exists():
            break
        await asyncio.sleep(0.05)
    else:
        worker.kill()
        return {"outcome": "WORKER_NEVER_READY"}

    reference = f"probe-{uuid.uuid4()}"
    handle = await client.start_workflow(
        "B5Workflow",
        {
            "target": f"probe-{uuid.uuid4()}",
            "action": "post",
            "amount_minor": 100,
            "client_reference": reference,
            "endpoint": "ledger_postings",
            "maximum_attempts": maximum_attempts,
            "start_to_close_ms": start_to_close_ms,
        },
        id=f"b5-probe-{uuid.uuid4()}",
        task_queue="b5-ws6",
    )

    started = time.monotonic()
    outcome = "PENDING_AT_DEADLINE"
    try:
        await asyncio.wait_for(handle.result(), timeout=deadline_s)
        outcome = "COMPLETED"
    except asyncio.TimeoutError:
        outcome = "PENDING_AT_DEADLINE"
    except Exception as exc:                              # noqa: BLE001
        outcome = f"FAILED:{type(exc).__name__}"
    elapsed = time.monotonic() - started

    worker.kill()
    worker.wait(timeout=10)

    events = []
    if trace.exists():
        for line in trace.read_text(errors="replace").splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    return {
        "outcome": outcome,
        "elapsed_s": round(elapsed, 3),
        "reference": reference,
        "events": [e["event"] for e in events],
        "provider_calls": sum(1 for e in events if e["event"] == "b5_provider_returned"),
        "died": any(e["event"] == "b5_crash_firing" for e in events),
        "worker_rc": worker.returncode,
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--address", default="127.0.0.1:7233")
    parser.add_argument("--provider", default="http://127.0.0.1:8099")
    parser.add_argument("--out", default="/var/tmp/b5-probe")
    arguments = parser.parse_args()

    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    trace = out / "trace.jsonl"
    findings: dict = {}

    client = await Client.connect(arguments.address)
    print("connected to Temporal\n")

    # ---------------------------------------------------------------- Q2
    print("=== Q2a: provider response-time distribution (n=40) ===")
    samples = await provider_latency(arguments.provider, "ledger_postings", 40)
    p50, p95 = statistics.median(samples), sorted(samples)[int(0.95 * len(samples))]
    worst = max(samples)
    emit("provider_ms", p50=round(p50, 2), p95=round(p95, 2), max=round(worst, 2))
    findings["provider_ms"] = {"p50": p50, "p95": p95, "max": worst}

    print("\n=== Q2b: does a healthy run complete, and how fast? ===")
    healthy = await run_one(
        client, crash_point=None, maximum_attempts=0, start_to_close_ms=5000,
        provider_url=arguments.provider, trace=trace, deadline_s=60,
    )
    emit("healthy", **{k: v for k, v in healthy.items() if k != "events"})
    findings["healthy"] = healthy

    print("\n=== Q2c: crash at ACTIVITY_ENTERED_BEFORE_CALL, does the retry land? ===")
    for stc in (2000, 5000):
        crashed = await run_one(
            client, crash_point="ACTIVITY_ENTERED_BEFORE_CALL",
            maximum_attempts=0, start_to_close_ms=stc,
            provider_url=arguments.provider, trace=trace, deadline_s=120,
        )
        emit(f"start_to_close={stc}ms",
             **{k: v for k, v in crashed.items() if k != "events"})
        findings[f"retry_stc_{stc}"] = crashed

    # ---------------------------------------------------------------- Q5
    print("\n=== Q5: injector reaches each named point ===")
    reach = {}
    for point in ("BEFORE_SCHEDULE_ACTIVITY", "ACTIVITY_ENTERED_BEFORE_CALL",
                  "DURING_PROVIDER_CALL", "AFTER_RESPONSE_BEFORE_RETURN",
                  "DURING_COMPLETE_RPC"):
        result = await run_one(
            client, crash_point=point, maximum_attempts=1,
            start_to_close_ms=3000, provider_url=arguments.provider,
            trace=trace, deadline_s=45,
        )
        reach[point] = result
        emit(point, died=result["died"], calls=result["provider_calls"],
             outcome=result["outcome"])
    findings["reach"] = reach

    (out / "findings.json").write_text(
        json.dumps(findings, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"\nwrote {out / 'findings.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
