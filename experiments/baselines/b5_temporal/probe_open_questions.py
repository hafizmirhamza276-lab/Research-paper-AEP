"""Close WS-6's open questions 2-5 by measurement on the real stack.

Not a collection. Nothing here writes a run directory, and no result from it may
appear as a B5 rate. It exists to answer questions the pre-registration says must
be closed before any data commit, each by running the real engine rather than by
reading documentation.

Run with the stack up and a mock provider listening.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from experiments.baselines.b5_temporal.gate import classify  # noqa: E402

HERE = Path(__file__).resolve().parent
ALL_POINTS = (
    "BEFORE_SCHEDULE_ACTIVITY",
    "ACTIVITY_ENTERED_BEFORE_CALL",
    "DURING_PROVIDER_CALL",
    "AFTER_RESPONSE_BEFORE_RETURN",
    "DURING_COMPLETE_RPC",
)


def emit(label: str, **fields) -> None:
    print(f"  {label:34s} " + "  ".join(f"{k}={v}" for k, v in fields.items()),
          flush=True)


async def provider_latency(url: str, endpoint: str, n: int) -> dict:
    ok, timed_out, errored = [], 0, 0
    refusals: dict[int, int] = {}
    async with httpx.AsyncClient(timeout=25.0) as client:
        for index in range(n):
            started = time.monotonic()
            try:
                response = await client.post(
                    f"{url}/v1/endpoints/{endpoint}/mutations",
                    headers={"X-Aep-Client-Reference": f"probe-{uuid.uuid4()}"},
                    json={
                        "connector_operation": "post_ledger_entry",
                        "target": f"probe-lat-{index}",
                        "operation_version": "1",
                        "public_fields": [
                            {"name": "target", "value": f"probe-lat-{index}"},
                            {"name": "action", "value": "post"},
                            {"name": "amount_minor", "value": 100},
                        ],
                    },
                )
                elapsed = (time.monotonic() - started) * 1000.0
                # 2xx ONLY. The first version accepted anything under 500, so a
                # 422 "unidentifiable envelope" returned in 1.8 ms counted as a
                # healthy sample and the measured p50 was the rejection path.
                if 200 <= response.status_code < 300:
                    ok.append(elapsed)
                else:
                    errored += 1
                    refusals[response.status_code] = refusals.get(
                        response.status_code, 0) + 1
            except httpx.TimeoutException:
                timed_out += 1
    return {"answered_ms": ok, "timed_out": timed_out, "errored": errored,
            "refusals": refusals, "n": n}


async def run_one(
    client: Client,
    *,
    crash_point: str | None,
    maximum_attempts: int,
    start_to_close_ms: int,
    provider_url: str,
    out: Path,
    deadline_s: float,
    injector_disabled: bool = False,
    retry_interval_ms: int = 200,
) -> dict:
    trace = out / "trace.jsonl"
    trace.write_text("", encoding="utf-8")
    ready = out / "ready"
    ready.unlink(missing_ok=True)

    env = dict(os.environ)
    env["B5_TRACE"] = str(trace)
    env["B5_PROVIDER_URL"] = provider_url
    env.pop("B5_CRASH_POINT", None)
    env.pop("B5_INJECTOR_DISABLED", None)
    if crash_point:
        env["B5_CRASH_POINT"] = crash_point
    if injector_disabled:
        env["B5_INJECTOR_DISABLED"] = "1"

    worker = subprocess.Popen(
        [sys.executable, str(HERE / "worker.py"), "--ready-file", str(ready)],
        env=env, stdout=subprocess.DEVNULL,
        stderr=open(out / "worker.err", "ab"),
    )
    worker_ready = False
    for _ in range(400):
        if ready.exists():
            worker_ready = True
            break
        await asyncio.sleep(0.05)

    settled, result, elapsed = False, None, 0.0
    if worker_ready:
        handle = await client.start_workflow(
            "B5Workflow",
            {"target": f"probe-{uuid.uuid4()}", "action": "post",
             "amount_minor": 100, "client_reference": f"probe-{uuid.uuid4()}",
             "endpoint": "ledger_postings",
             "maximum_attempts": maximum_attempts,
             "start_to_close_ms": start_to_close_ms,
             "retry_interval_ms": retry_interval_ms},
            id=f"b5-probe-{uuid.uuid4()}", task_queue="b5-ws6",
        )
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(handle.result(), timeout=deadline_s)
            settled = True
        except asyncio.TimeoutError:
            settled = False
        except Exception as exc:                              # noqa: BLE001
            settled, result = True, f"FAILED:{type(exc).__name__}"
        elapsed = time.monotonic() - started

    worker.kill()
    try:
        worker.wait(timeout=10)
    except Exception:                                          # noqa: BLE001
        pass

    events = []
    if trace.exists():
        for line in trace.read_text(errors="replace").splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    names = [e["event"] for e in events]
    verdict = classify(armed_point=crash_point, settled=settled,
                       worker_ready=worker_ready, events=names)
    return {
        "verdict": verdict.verdict.value,
        "reason": verdict.reason,
        "is_void": verdict.is_void,
        "settled": settled,
        "result": result,
        "elapsed_s": round(elapsed, 2),
        "provider_calls": sum(1 for n in names if n == "b5_provider_returned"),
        "reached": "b5_point_reached" in names,
        "fired": "b5_crash_firing" in names,
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--address", default="127.0.0.1:7233")
    parser.add_argument("--provider", default="http://127.0.0.1:8099")
    parser.add_argument("--out", default="/var/tmp/b5-probe")
    arguments = parser.parse_args()

    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    findings: dict = {}
    client = await Client.connect(arguments.address)
    print("connected\n", flush=True)

    # ------------------------------------------------------------------ Q2a
    print("=== Q2a: provider response-time distribution (n=30) ===", flush=True)
    dist = await provider_latency(arguments.provider, "ledger_postings", 30)
    answered = dist["answered_ms"]
    p50 = statistics.median(answered) if answered else None
    p95 = sorted(answered)[int(0.95 * (len(answered) - 1))] if answered else None
    emit("provider", n=dist["n"], answered=len(answered),
         timed_out=dist["timed_out"], refused=dist["refusals"],
         p50_ms=round(p50, 1) if p50 else None,
         p95_ms=round(p95, 1) if p95 else None,
         max_ms=round(max(answered), 1) if answered else None)
    findings["q2a_provider"] = {**dist, "p50": p50, "p95": p95}

    # ------------------------------------------------------------------ Q5
    print("\n=== Q5: does the injector reach each of the five points? ===",
          flush=True)
    reach = {}
    for point in ALL_POINTS:
        r = await run_one(client, crash_point=point, maximum_attempts=1,
                          start_to_close_ms=8000, provider_url=arguments.provider,
                          out=out, deadline_s=40)
        reach[point] = r
        emit(point, reached=r["reached"], fired=r["fired"],
             verdict=r["verdict"], calls=r["provider_calls"])
    findings["q5_reach"] = reach

    # ------------------------------------------- Q5 gate, both branches
    print("\n=== Q5 gate, rule 13: BOTH branches on the real stack ===",
          flush=True)
    silent = await run_one(client, crash_point="ACTIVITY_ENTERED_BEFORE_CALL",
                           maximum_attempts=1, start_to_close_ms=8000,
                           provider_url=arguments.provider, out=out, deadline_s=40)
    emit("reachable -> gate silent", verdict=silent["verdict"],
         void=silent["is_void"])
    voided = await run_one(client, crash_point="ACTIVITY_ENTERED_BEFORE_CALL",
                           maximum_attempts=1, start_to_close_ms=8000,
                           provider_url=arguments.provider, out=out, deadline_s=40,
                           injector_disabled=True)
    emit("unreachable -> gate voids", verdict=voided["verdict"],
         void=voided["is_void"])
    print(f"    reason: {voided['reason'][:150]}", flush=True)
    findings["q5_gate"] = {"silent": silent, "voided": voided}

    # ------------------------------------------------------------- Q2b / Q3
    print("\n=== Q2b/Q3: does the retry land, and inside what deadline? ===",
          flush=True)
    timing = {}
    for stc in (3000, 8000, 15000):
        r = await run_one(client, crash_point="ACTIVITY_ENTERED_BEFORE_CALL",
                          maximum_attempts=0, start_to_close_ms=stc,
                          provider_url=arguments.provider, out=out,
                          deadline_s=150)
        timing[stc] = r
        emit(f"start_to_close={stc}ms", verdict=r["verdict"],
             settled=r["settled"], elapsed_s=r["elapsed_s"])
    findings["q2b_timing"] = timing

    # ------------------------------------------------------------------ Q4
    print("\n=== Q4: is point 6's race observable on loopback? (n=8) ===",
          flush=True)
    hits = []
    for _ in range(8):
        r = await run_one(client, crash_point="DURING_COMPLETE_RPC",
                          maximum_attempts=1, start_to_close_ms=8000,
                          provider_url=arguments.provider, out=out, deadline_s=40)
        hits.append(r)
    landed = sum(1 for r in hits if r["fired"] and r["provider_calls"] >= 1)
    emit("point 6", trials=len(hits), fired=sum(1 for r in hits if r["fired"]),
         with_provider_call=landed,
         voids=sum(1 for r in hits if r["is_void"]))
    findings["q4_point6"] = hits

    (out / "findings.json").write_text(
        json.dumps(findings, indent=2, sort_keys=True, default=str),
        encoding="utf-8")
    print(f"\nwrote {out / 'findings.json'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
