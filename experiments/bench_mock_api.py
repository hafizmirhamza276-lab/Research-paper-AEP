"""D0(iii): does the provider sustain far more load than the matrix asks of it?

The amendment: *"mock API throughput benchmark: demonstrate the mock API
sustains at least 10x the request rate the busiest planned configuration
generates, else fix or document as an overhead-measurement bound."*

The question is not academic. ``reports/phase-report-2b-session1-2026-08-05.md``
F8 and ``...-session2-...`` F9 both flagged it and neither measured it: the
ground-truth ledger commits one transaction per applied mutation with
``synchronous=FULL``, so every mutation costs an fsync, and since Session 2 it
also holds one SQLite connection per thread. If that fsync were anywhere near
the rate the matrix generates, PAPER_ROADMAP.md section 3.2's throughput and
latency comparisons would be measuring SQLite rather than AEP -- and the
overhead column of the paper would be a measurement of the measuring
apparatus.

**What is measured.** Sustained mutations per second against a provider
configured with *no* injected delay and no faults, driven by ``--concurrency``
concurrent clients for ``--seconds`` seconds. The delay is removed on purpose:
a 2 s response delay is a property of the experiment's fault surface, not of
the provider's capacity, and leaving it in would measure the sleep.

**What it is compared against.** The matrix's own plan, not a guess. The
busiest configuration is ``workers`` concurrent executions, each issuing at
most ``max_dispatch_attempts`` mutations plus one read-back, spaced by the
per-execution wall time the plan model uses. That number is computed here from
the same constants ``run_matrix.py`` plans with, so the two cannot drift.

    python -m experiments.bench_mock_api --seconds 20 --concurrency 16
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import httpx

from aep_core.core.request_binding import build_exact_request_bytes

from experiments.harness.workload import harness_profile, request_for
from experiments.baselines.tests.helpers import item_for
from experiments.mock_api.ledger import GroundTruthLedger
from experiments.mock_api.service import CLIENT_REFERENCE_HEADER
from experiments.mock_api.supervisor import render_config, start_mock_api

DEFAULT_TEMPLATE = Path("experiments/configs/matrix.yaml")

#: The bar the amendment sets.
REQUIRED_HEADROOM = 10.0

#: Requests issued before the clock starts, to warm the connection pool and
#: the SQLite page cache. They reach the ledger like any other, so the
#: ledger-versus-client check has to know about them.
WARMUP_REQUESTS = 1


def planned_peak_request_rate(
    *, workers: int, max_dispatch_attempts: int, per_execution_seconds: float
) -> float:
    """The busiest planned configuration's request rate, in requests/second.

    Upper bound, deliberately: every worker is assumed to be issuing its
    maximum number of attempts plus a read-back, back to back, with no worker
    ever idle. The real matrix is slower than this in every cell.
    """
    requests_per_execution = max_dispatch_attempts + 1
    return workers * requests_per_execution / per_execution_seconds


async def _fire(
    client: httpx.AsyncClient,
    url: str,
    payload: bytes,
    reference: str,
    deadline: float,
    latencies: list[float],
    failures: list[int],
) -> int:
    sent = 0
    while time.monotonic() < deadline:
        started = time.monotonic()
        try:
            response = await client.post(
                url,
                content=payload,
                headers={
                    "content-type": "application/json",
                    CLIENT_REFERENCE_HEADER: reference,
                },
                timeout=30.0,
            )
        except httpx.HTTPError:
            failures.append(-1)
            continue
        latencies.append(time.monotonic() - started)
        if response.status_code != 200:
            failures.append(response.status_code)
        sent += 1
    return sent


async def main_async(arguments) -> int:
    results_dir = Path(arguments.results_root)
    results_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = results_dir / "throughput.sqlite3"
    for stale in (
        ledger_path,
        ledger_path.with_suffix(".sqlite3-wal"),
        ledger_path.with_suffix(".sqlite3-shm"),
        ledger_path.with_suffix(".run.jsonl"),
    ):
        stale.unlink(missing_ok=True)

    config_path = render_config(
        arguments.template,
        results_dir / "mock-api.yaml",
        ledger_path=ledger_path,
        seed=1,
        readback_keying="CALLER_REFERENCE",
        # No delay and no faults: this measures capacity, not the fault
        # surface. A 2 s sleep would otherwise dominate every sample.
        fault_overrides={
            "delay": {"distribution": "constant", "seconds": 0.0},
            "timeout_probability": 0.0,
            "server_error_probability": 0.0,
            "duplicate_response_probability": 0.0,
        },
    )
    provider = start_mock_api(
        config_path,
        port=arguments.port,
        log_path=results_dir / "mock-api.log",
    )

    profile = harness_profile()
    url = f"{provider.base_url}/v1/endpoints/{arguments.endpoint}/mutations"
    latencies: list[float] = []
    failures: list[int] = []

    try:
        # Each client sends a distinct mutation, as the workload does: every
        # execution owns its own resource. A single hot fingerprint would
        # measure a different thing (one row's contention) from the one the
        # matrix creates.
        payloads = [
            build_exact_request_bytes(profile, request_for(item_for(amount_minor=1000 + index)))
            for index in range(arguments.concurrency)
        ]

        async with httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=arguments.concurrency * 2,
                max_keepalive_connections=arguments.concurrency * 2,
            )
        ) as client:
            # Warm the connection pool and the SQLite page cache so the
            # measured window is steady state rather than first-touch.
            await client.post(
                url,
                content=payloads[0],
                headers={
                    "content-type": "application/json",
                    CLIENT_REFERENCE_HEADER: "warmup",
                },
                timeout=30.0,
            )

            started = time.monotonic()
            deadline = started + arguments.seconds
            sent = await asyncio.gather(
                *(
                    _fire(
                        client,
                        url,
                        payloads[index],
                        f"bench-{index}",
                        deadline,
                        latencies,
                        failures,
                    )
                    for index in range(arguments.concurrency)
                )
            )
            elapsed = time.monotonic() - started
    finally:
        provider.stop()

    ledger = GroundTruthLedger(ledger_path)
    ledger.initialise()
    try:
        applied_rows = len(ledger.applied_mutations())
    finally:
        ledger.close()

    total_sent = sum(sent)
    achieved = total_sent / elapsed
    planned = planned_peak_request_rate(
        workers=arguments.matrix_workers,
        max_dispatch_attempts=arguments.matrix_max_attempts,
        per_execution_seconds=arguments.matrix_per_execution_seconds,
    )
    headroom = achieved / planned if planned else float("inf")

    report = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "concurrency": arguments.concurrency,
        "duration_seconds": round(elapsed, 3),
        "requests_sent": total_sent,
        "warmup_requests": WARMUP_REQUESTS,
        "non_200_responses": len(failures),
        "ledger_applied_rows": applied_rows,
        "achieved_requests_per_second": round(achieved, 2),
        "latency_ms": {
            "mean": round(statistics.mean(latencies) * 1000, 3) if latencies else None,
            "median": round(statistics.median(latencies) * 1000, 3) if latencies else None,
            "p95": (
                round(sorted(latencies)[int(len(latencies) * 0.95)] * 1000, 3)
                if len(latencies) >= 20
                else None
            ),
            "p99": (
                round(sorted(latencies)[int(len(latencies) * 0.99)] * 1000, 3)
                if len(latencies) >= 100
                else None
            ),
            "max": round(max(latencies) * 1000, 3) if latencies else None,
        },
        "planned_peak_requests_per_second": round(planned, 3),
        "planned_peak_model": {
            "workers": arguments.matrix_workers,
            "max_dispatch_attempts": arguments.matrix_max_attempts,
            "per_execution_seconds": arguments.matrix_per_execution_seconds,
            "requests_per_execution": arguments.matrix_max_attempts + 1,
            "note": (
                "upper bound: every worker assumed to issue its maximum "
                "attempts plus one read-back, back to back, never idle"
            ),
        },
        "headroom_multiple": round(headroom, 2),
        "required_headroom_multiple": REQUIRED_HEADROOM,
        "passes": headroom >= REQUIRED_HEADROOM,
    }

    destination = results_dir / "throughput.json"
    destination.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(report, indent=2, sort_keys=True))
    print("")
    if applied_rows != total_sent + WARMUP_REQUESTS:
        # Not a pass/fail condition -- a 5xx is not applied, and the fault
        # probabilities are zero here so there should be none -- but a
        # divergence means the oracle and the client disagree about what
        # happened, and that is worth seeing immediately. The warmup request
        # is applied too, and is counted here rather than being subtracted
        # from the ledger, so the check stays a real check.
        print(
            f"NOTE: {total_sent} measured requests plus {WARMUP_REQUESTS} "
            f"warmup, but {applied_rows} rows in the ledger. With every fault "
            "probability at zero these should match."
        )
    if report["passes"]:
        print(
            f"D0(iii) PASS -- {report['achieved_requests_per_second']} req/s "
            f"sustained is {report['headroom_multiple']}x the busiest planned "
            f"configuration's {report['planned_peak_requests_per_second']} req/s "
            f"(bar: {REQUIRED_HEADROOM}x)."
        )
        return 0
    print(
        f"D0(iii) FAIL -- {report['achieved_requests_per_second']} req/s is only "
        f"{report['headroom_multiple']}x the planned peak. Per D0 this must be "
        "fixed, or documented as an overhead-measurement bound."
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure the MockLegacyAPI's sustained throughput (D0(iii))."
    )
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--results-root", default="experiments/results/throughput")
    parser.add_argument("--endpoint", default="payments")
    parser.add_argument("--port", type=int, default=8098)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--concurrency", type=int, default=16)
    # The busiest planned configuration, from run_matrix.py's own defaults.
    parser.add_argument("--matrix-workers", type=int, default=2)
    parser.add_argument("--matrix-max-attempts", type=int, default=3)
    parser.add_argument("--matrix-per-execution-seconds", type=float, default=3.2)
    return asyncio.run(main_async(parser.parse_args(argv)))


if __name__ == "__main__":  # pragma: no cover - process entry point
    sys.exit(main())
