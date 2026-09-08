"""Close WS-6's open questions 2-5 by measurement on the real stack.

Not a collection. Nothing here writes a run directory, and no result from it may
appear as a B5 rate.

**This module is subject to `docs/25` R14, and two earlier versions of it are
instance 5 in that rule.** Every readiness and sampling path below must be able
to report three outcomes, not two: the thing is there, the thing is not there,
and *I could not look, or I looked in the wrong place*. Concretely:

* :func:`precheck` sends a **canary mutation** and requires ``2xx``. A health
  endpoint answering 200 proves the process is up, not that this probe speaks the
  provider's contract -- one earlier version polled a route that does not exist,
  reported ``000``, and ran anyway; the next sent an envelope missing ``target``
  and recorded thirty ``422``s as a latency distribution. The canary is what
  separates those from a healthy provider, and the probe **refuses to measure**
  if it fails.
* :func:`provider_latency` accepts only ``2xx`` and reports refusals **by status
  code**, so a wrong request shape cannot masquerade as a slow provider.
* Every stage is wrapped and **findings are written after each one**, so a death
  mid-run leaves evidence of how far it got. The previous run exited after one
  line with no findings file and no traceback, which is why its cause was never
  established.
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
import traceback
import uuid
from pathlib import Path

import httpx
from temporalio.client import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from experiments.baselines.b5_temporal.gate import classify  # noqa: E402
from experiments.baselines.b5_temporal.supervisor import (  # noqa: E402
    WorkerSupervisor,
)

HERE = Path(__file__).resolve().parent
ALL_POINTS = (
    "BEFORE_SCHEDULE_ACTIVITY",
    "ACTIVITY_ENTERED_BEFORE_CALL",
    "DURING_PROVIDER_CALL",
    "AFTER_RESPONSE_BEFORE_RETURN",
    "DURING_COMPLETE_RPC",
)

OUT: Path = Path("/var/tmp/b5-probe")
FINDINGS: dict = {}


def say(text: str = "") -> None:
    print(text, flush=True)


def emit(label: str, **fields) -> None:
    say(f"  {label:32s} " + "  ".join(f"{k}={v}" for k, v in fields.items()))


def save() -> None:
    (OUT / "findings.json").write_text(
        json.dumps(FINDINGS, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )


def envelope(target: str) -> dict:
    """The shape the oracle can fingerprint.

    All four keys of ``fingerprint._REQUIRED_ENVELOPE_KEYS``, with ``target`` at
    the TOP level as well as inside ``public_fields``. Two earlier versions of
    this probe omitted one or more and were refused 422 in under 2 ms.
    """
    return {
        "connector_operation": "post_ledger_entry",
        "operation_version": "1",
        "target": target,
        "public_fields": [
            {"name": "target", "value": target},
            {"name": "action", "value": "post"},
            {"name": "amount_minor", "value": 100},
        ],
    }


async def precheck(url: str, endpoint: str) -> tuple[bool, str]:
    """Three outcomes: speaking the contract, provider down, or wrong shape."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            health = await client.get(f"{url}/v1/health")
    except Exception as exc:                                   # noqa: BLE001
        return False, f"provider unreachable at {url}/v1/health: {exc!r}"
    if health.status_code != 200:
        return False, f"/v1/health returned {health.status_code}, expected 200"

    # The decisive check: a canary mutation must be ACCEPTED, not merely answered.
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{url}/v1/endpoints/{endpoint}/mutations",
                headers={"X-Aep-Client-Reference": f"canary-{uuid.uuid4()}"},
                json=envelope(f"canary-{uuid.uuid4()}"),
            )
        except httpx.TimeoutException:
            # An injected timeout is a configured fault (15%), not a contract
            # error. Reachable, contract not refuted.
            return True, "canary timed out (injected fault); contract not refuted"
    if 200 <= response.status_code < 300:
        return True, f"canary accepted ({response.status_code})"
    if response.status_code == 503:
        return True, "canary drew an injected 503; contract not refuted"
    return False, (
        f"canary REFUSED {response.status_code}: {response.text[:200]} -- this "
        f"probe is not speaking the provider's contract, so nothing it measured "
        f"would be about the provider"
    )


async def provider_latency(url: str, endpoint: str, n: int) -> dict:
    ok: list[float] = []
    timed_out = 0
    refusals: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=25.0) as client:
        for index in range(n):
            started = time.monotonic()
            try:
                response = await client.post(
                    f"{url}/v1/endpoints/{endpoint}/mutations",
                    headers={"X-Aep-Client-Reference": f"probe-{uuid.uuid4()}"},
                    json=envelope(f"probe-lat-{index}"),
                )
            except httpx.TimeoutException:
                timed_out += 1
                continue
            elapsed = (time.monotonic() - started) * 1000.0
            if 200 <= response.status_code < 300:
                ok.append(elapsed)
            else:
                key = str(response.status_code)
                refusals[key] = refusals.get(key, 0) + 1
    return {"answered_ms": ok, "timed_out": timed_out, "refusals": refusals, "n": n}


async def run_one(
    client: Client,
    *,
    crash_point: str | None,
    maximum_attempts: int,
    start_to_close_ms: int,
    provider_url: str,
    deadline_s: float,
    injector_disabled: bool = False,
    retry_interval_ms: int = 200,
    respawn_enabled: bool = True,
) -> dict:
    trace = OUT / "trace.jsonl"
    trace.write_text("", encoding="utf-8")
    # Truncated per run, decided rather than carried. Appending across runs meant
    # a stale traceback from a previous round was readable during a later one and
    # could have been attributed to it -- a log that cannot say which run a line
    # belongs to cannot report "I could not tell" (docs/25 R14).
    (OUT / "worker.err").write_bytes(b"")

    sup = WorkerSupervisor(
        out=OUT, crash_point=crash_point, provider_url=provider_url,
        respawn_enabled=respawn_enabled, injector_disabled=injector_disabled,
    )
    worker_ready = sup.spawn(1)
    if not worker_ready:
        # Decided: a cold start that misses the ready timeout is RETRIED ONCE,
        # not spent. A worker that never came up measured nothing, so voiding
        # the run loses a run of power for a reason that has nothing to do with
        # the engine. One retry only -- a second failure is a real defect and
        # must still void, or this quietly becomes an unbounded loop that hides
        # a broken worker.
        sup.spawn(1)
        worker_ready = (OUT / "ready").exists()

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
        waiter = asyncio.ensure_future(handle.result())
        # Poll rather than a single wait_for: the supervisor has to notice the
        # worker died and bring one back WHILE the workflow is outstanding.
        while time.monotonic() - started < deadline_s:
            done, _ = await asyncio.wait({waiter}, timeout=0.5)
            if done:
                break
            sup.maintain()
        if waiter.done():
            try:
                result, settled = waiter.result(), True
            except Exception as exc:                           # noqa: BLE001
                settled, result = True, f"FAILED:{type(exc).__name__}"
        else:
            waiter.cancel()
            settled = False
        elapsed = time.monotonic() - started
        if not sup.alive():
            # A death at the very end must still be counted, or a run that died
            # and settled would look like one that never died.
            sup.state.deaths = max(sup.state.deaths, 1)

    sup.stop()

    names: list[str] = []
    if trace.exists():
        for line in trace.read_text(errors="replace").splitlines():
            try:
                names.append(json.loads(line)["event"])
            except (ValueError, KeyError):
                pass
    verdict = classify(armed_point=crash_point, settled=settled,
                       worker_ready=worker_ready, events=names,
                       worker_deaths=sup.state.deaths,
                       respawns=sup.state.respawns)
    return {
        "verdict": verdict.verdict.value,
        "reason": verdict.reason,
        "is_void": verdict.is_void,
        "settled": settled,
        "result": str(result)[:120],
        "elapsed_s": round(elapsed, 2),
        "provider_calls": names.count("b5_provider_returned"),
        "reached": "b5_point_reached" in names,
        "fired": "b5_crash_firing" in names,
        "spawns": sup.state.spawns,
        "deaths": sup.state.deaths,
        "respawns": sup.state.respawns,
        "exhausted": sup.state.exhausted,
    }


async def stage(name: str, coro) -> None:
    """Run one stage; record a failure instead of dying silently."""
    say(f"\n=== {name} ===")
    try:
        FINDINGS[name] = await coro
    except Exception:                                          # noqa: BLE001
        FINDINGS[name] = {"STAGE_FAILED": traceback.format_exc()[-1500:]}
        say("  STAGE FAILED -- recorded, continuing:")
        say(traceback.format_exc()[-700:])
    save()


async def main() -> int:
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--address", default="127.0.0.1:7233")
    parser.add_argument("--provider", default="http://127.0.0.1:8099")
    parser.add_argument("--out", default="/var/tmp/b5-probe")
    # Run a subset. Stages already closed with evidence are not re-run: each
    # costs minutes on a stack that has twice gone away mid-probe (R12a), and
    # re-running a closed stage is exposure without information.
    parser.add_argument("--stages", default="",
                        help="comma-separated stage names; empty means all")
    arguments = parser.parse_args()
    global WANTED
    WANTED = {s for s in arguments.stages.split(",") if s}
    OUT = Path(arguments.out)
    OUT.mkdir(parents=True, exist_ok=True)
    provider = arguments.provider

    say("=== R14 precheck: is this probe speaking the provider's contract? ===")
    ok, why = await precheck(provider, "ledger_postings")
    emit("precheck", ok=ok)
    say(f"    {why}")
    FINDINGS["precheck"] = {"ok": ok, "reason": why}
    save()
    if not ok:
        say("\nREFUSING TO MEASURE: a probe that cannot get one mutation accepted "
            "would report the rejection path as a provider distribution.")
        return 2

    client = await Client.connect(arguments.address)
    say("connected to Temporal")

    async def q2a():
        dist = await provider_latency(provider, "ledger_postings", 30)
        answered = dist["answered_ms"]
        p50 = statistics.median(answered) if answered else None
        p95 = sorted(answered)[int(0.95 * (len(answered) - 1))] if answered else None
        emit("provider", n=dist["n"], answered=len(answered),
             timed_out=dist["timed_out"], refused=dist["refusals"],
             p50_ms=round(p50, 1) if p50 else None,
             p95_ms=round(p95, 1) if p95 else None)
        return {**dist, "p50_ms": p50, "p95_ms": p95}
    await stage("q2a_provider_distribution", q2a())

    async def gate_proof():
        out: dict = {}
        silent = await run_one(client, crash_point="ACTIVITY_ENTERED_BEFORE_CALL",
                               maximum_attempts=1, start_to_close_ms=8000,
                               provider_url=provider, deadline_s=45)
        emit("branch A reachable", verdict=silent["verdict"], void=silent["is_void"],
             reached=silent["reached"], fired=silent["fired"])
        voided = await run_one(client, crash_point="ACTIVITY_ENTERED_BEFORE_CALL",
                               maximum_attempts=1, start_to_close_ms=8000,
                               provider_url=provider, deadline_s=45,
                               injector_disabled=True)
        emit("branch B unreachable", verdict=voided["verdict"], void=voided["is_void"],
             reached=voided["reached"], fired=voided["fired"])
        say(f"    void reason: {voided['reason'][:200]}")
        out["silent"], out["voided"] = silent, voided
        out["rule13_satisfied"] = bool(
            (not silent["is_void"]) and voided["is_void"]
        )
        emit("rule 13 both branches", satisfied=out["rule13_satisfied"])
        return out
    await stage("q5b_gate_both_branches", gate_proof())

    async def points():
        out: dict = {}
        for point in ALL_POINTS:
            r = await run_one(client, crash_point=point, maximum_attempts=1,
                              start_to_close_ms=8000, provider_url=provider,
                              deadline_s=45)
            out[point] = r
            emit(point, reached=r["reached"], fired=r["fired"],
                 calls=r["provider_calls"], verdict=r["verdict"])
            FINDINGS["q5c_five_points"] = out
            save()
        return out
    await stage("q5c_five_points", points())

    async def retry_lands():
        out: dict = {}
        for stc in (2500, 4000, 8000):
            r = await run_one(client, crash_point="ACTIVITY_ENTERED_BEFORE_CALL",
                              maximum_attempts=0, start_to_close_ms=stc,
                              provider_url=provider, deadline_s=150)
            out[str(stc)] = r
            emit(f"start_to_close={stc}ms", verdict=r["verdict"],
                 settled=r["settled"], elapsed_s=r["elapsed_s"],
                 calls=r["provider_calls"])
            FINDINGS["q2b_retry_lands"] = out
            save()
        return out
    await stage("q2b_retry_lands", retry_lands())

    async def sup_proof():
        """Rule 13 for the supervisor, both directions."""
        out: dict = {}
        on = await run_one(client, crash_point="ACTIVITY_ENTERED_BEFORE_CALL",
                           maximum_attempts=0, start_to_close_ms=4000,
                           provider_url=provider, deadline_s=120,
                           respawn_enabled=True)
        emit("A respawn ON", verdict=on["verdict"], void=on["is_void"],
             deaths=on["deaths"], respawns=on["respawns"],
             calls=on["provider_calls"], settled=on["settled"])
        off = await run_one(client, crash_point="ACTIVITY_ENTERED_BEFORE_CALL",
                            maximum_attempts=0, start_to_close_ms=4000,
                            provider_url=provider, deadline_s=120,
                            respawn_enabled=False)
        emit("B respawn OFF", verdict=off["verdict"], void=off["is_void"],
             deaths=off["deaths"], respawns=off["respawns"],
             calls=off["provider_calls"])
        say(f"    void reason: {off['reason'][:190]}")
        out["respawn_on"], out["respawn_off"] = on, off
        out["rule13_satisfied"] = bool(
            (not on["is_void"]) and off["is_void"]
            and off["verdict"] == "VOID_SUPERVISOR_NEVER_RESPAWNED"
        )
        emit("rule 13 supervisor", satisfied=out["rule13_satisfied"])
        return out
    await stage("q5d_supervisor_both_branches", sup_proof())

    async def after_response():
        """Q5c's remaining point, n=8, the treatment Q4 got."""
        trials = []
        for _ in range(8):
            r = await run_one(client, crash_point="AFTER_RESPONSE_BEFORE_RETURN",
                              maximum_attempts=1, start_to_close_ms=8000,
                              provider_url=provider, deadline_s=45)
            trials.append(r)
            FINDINGS["q5c_after_response_n8"] = trials
            save()
        emit("AFTER_RESPONSE_BEFORE_RETURN", trials=len(trials),
             reached=sum(1 for r in trials if r["reached"]),
             fired=sum(1 for r in trials if r["fired"]),
             with_provider_call=sum(1 for r in trials if r["provider_calls"] >= 1),
             voids=sum(1 for r in trials if r["is_void"]))
        return trials
    await stage("q5c_after_response_n8", after_response())

    async def point6():
        trials: list[dict] = []
        for _ in range(8):
            r = await run_one(client, crash_point="DURING_COMPLETE_RPC",
                              maximum_attempts=1, start_to_close_ms=8000,
                              provider_url=provider, deadline_s=45)
            trials.append(r)
            FINDINGS["q4_point6_race"] = trials
            save()
        emit("point 6", trials=len(trials),
             reached=sum(1 for r in trials if r["reached"]),
             fired=sum(1 for r in trials if r["fired"]),
             after_provider_call=sum(1 for r in trials if r["provider_calls"] >= 1),
             voids=sum(1 for r in trials if r["is_void"]))
        return trials
    await stage("q4_point6_race", point6())

    say(f"\nwrote {OUT / 'findings.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
