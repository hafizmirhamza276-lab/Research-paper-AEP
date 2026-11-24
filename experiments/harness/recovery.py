"""The recovery process: ``python -m experiments.harness.recovery``.

Runs ``IntentRecoveryService`` in its own OS process for the duration of a run,
so that reconciliation happens concurrently with the workload rather than as a
tidy phase afterwards -- which is the only arrangement in which recovery
latency means anything.

**The scan-failure stream is a measurement, not a log line.** Amendment C4
requires it: ``reports/phase-report-1b-2026-08-05.md`` F7 recorded that fault
isolation had turned a loud failure (a corrupt execution crashing the recovery
loop) into a quiet one, and that *nothing in the repository consumed*
``scan_failure_alert``. Here it is consumed. Every isolated failure is written
to the run log at the instant it is detected, and the runner -- which knows
when it poisoned an execution -- turns the pair into a detection latency. The
gap is closed by measuring it rather than by asserting it is small.

**Stopping.** The runner signals shutdown by creating a file, which the loop
checks between passes. A signal would be neater on POSIX and is not portable:
``Popen.terminate`` on Windows is ``TerminateProcess``, which would kill the
recovery process mid-pass and lose exactly the records this run is collecting.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from redis.asyncio import Redis

from aep_core.core.intent_recovery import RecoveryScanFailure
from aep_core.core.locks import DistributedLockManager

from experiments.harness.composition import build_connector, build_recovery_service
from experiments.harness.config import RunConfig, load_run_config
from experiments.harness.events import EventLog
from experiments.harness.workload import index_by_execution_id, plan_workload

STOP_FILE_NAME = "recovery.stop"
SOURCE = "recovery"


def stop_file(config: RunConfig) -> Path:
    return config.results_dir / STOP_FILE_NAME


def shard_path(config: RunConfig) -> Path:
    return config.results_dir / f"events-{SOURCE}.jsonl"


async def run_recovery(config: RunConfig) -> int:
    log = EventLog(shard_path(config), run_id=config.run_id, source=SOURCE)
    redis_client = Redis.from_url(
        config.effective_worker_redis_url, decode_responses=True
    )
    connector = build_connector(
        config, items=index_by_execution_id(plan_workload(config))
    )
    stop = stop_file(config)

    def on_scan_failure(failure: RecoveryScanFailure) -> None:
        """Fired the instant one execution is isolated out of a scan pass."""
        log.emit(
            "scan_failure_alert",
            execution_id=failure.execution_id,
            intent_id=failure.intent_id,
            failure_class=failure.failure_class,
            phase=failure.phase.value,
        )

    def on_recovery_lag(elapsed_seconds: float) -> None:
        log.emit("recovery_lag_alert", elapsed_seconds=elapsed_seconds)

    log.emit(
        "recovery_started",
        pass_interval_seconds=config.recovery_pass_interval_seconds,
        redis_url=config.effective_worker_redis_url,
    )
    passes = 0
    try:
        service = build_recovery_service(
            config,
            redis_client=redis_client,
            lock_manager=DistributedLockManager(redis_client),
            connector=connector,
            scan_failure_alert=on_scan_failure,
            recovery_lag_alert=on_recovery_lag,
        )

        while not stop.exists():
            started = time.monotonic_ns()
            try:
                results = await service.scan_once()
            except Exception as error:  # noqa: BLE001 -- the loop must survive
                log.emit(
                    "recovery_pass_failed",
                    failure_class=type(error).__name__,
                    duration_ns=time.monotonic_ns() - started,
                )
                await asyncio.sleep(config.recovery_pass_interval_seconds)
                continue

            duration_ns = time.monotonic_ns() - started
            for result in results:
                log.emit(
                    "recovery_resolution",
                    execution_id=result.execution_id,
                    intent_id=result.intent_id,
                    status=result.status.value,
                    readback_performed=result.readback_performed,
                )
            passes += 1
            log.emit(
                "recovery_pass",
                pass_number=passes,
                resolutions=len(results),
                isolated_failures=len(service.last_scan_failures),
                duration_ns=duration_ns,
            )
            await asyncio.sleep(config.recovery_pass_interval_seconds)
    finally:
        log.emit("recovery_finished", passes=passes)
        try:
            await connector.aclose()
        finally:
            await redis_client.aclose()
            log.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AEP recovery service.")
    parser.add_argument("--run-config", required=True, type=Path)
    arguments = parser.parse_args(argv)

    config = load_run_config(arguments.run_config)
    return asyncio.run(run_recovery(config))


if __name__ == "__main__":  # pragma: no cover - process entry point
    sys.exit(main())
