"""The multi-process runner: spawn, kill, supervise, settle, reconcile.

PAPER_ROADMAP.md 3.1(3). One run is:

1. a results directory holding the run configuration and, at the end, the
   merged ``events.jsonl`` and a ``summary.json``;
2. one recovery process, running for the whole run rather than as a tidy phase
   afterwards, because recovery latency measured against a quiesced system is
   not recovery latency;
3. ``workers`` worker processes, each executing its slice of the workload, each
   dying at the configured crash point if the run selected it, and each
   respawned by this supervisor to continue with the *next* execution -- never
   to retry the one it may already have dispatched;
4. optionally: poisoned executions, a Redis restart, a worker-to-Redis
   partition;
5. a settling phase, in which the runner waits for every execution to reach a
   terminal intent state or for the recovery deadline to pass;
6. the final classification of every execution, read from Redis and written
   into the run log, which is what ``reconcile.py`` compares against the
   ground-truth ledger.

**The Redis guard.** Session 1's report closed with a caution: the harness
kills processes holding Redis leases, and ``tests/conftest.py``'s
test-instance-marker is what stops a mis-pointed ``REDIS_URL`` from touching a
production keyspace. That guard is a pytest fixture and does not run here, so
the same precondition is checked directly, before anything is spawned.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Sequence

from redis.asyncio import Redis

from aep_core.core.intents import IntentLedgerStore, IntentStatus

from experiments.harness import recovery as recovery_module
from experiments.harness import worker as worker_module
from experiments.harness.composition import delete_run_keys
from experiments.harness.config import RunConfig, load_run_config
from experiments.harness.crash_points import roadmap_name_for
from experiments.harness.events import EventLog, merge_event_shards, read_events
from experiments.harness.faults import (
    ToxiproxyControl,
    restart_redis_and_verify_aof,
)
from experiments.harness.injector import (
    CRASH_DELAY_VARIABLE,
    CRASH_EXECUTIONS_VARIABLE,
    CRASH_POINT_VARIABLE,
    CRASH_STYLE_VARIABLE,
    HAS_SIGKILL,
    CrashStyle,
)
from experiments.harness.reconcile import (
    poisoned_detection_latencies,
    reconcile,
    write_summary,
)
from experiments.harness.workload import plan_workload, worker_items
from experiments.mock_api.config import load_config

#: The instance's own assertion that it is disposable. Same key, same meaning,
#: as ``tests/conftest.py``.
TEST_INSTANCE_MARKER_KEY = "aep:test-instance-marker"

#: Intent statuses that still need recovery to act.
PENDING_STATUSES = frozenset(
    {IntentStatus.ABOUT_TO_FIRE.value, IntentStatus.FIRED_UNCONFIRMED.value}
)

#: How many lifetimes one worker slot may burn before the runner gives up.
#: A crash costs one lifetime per selected execution, plus a margin.
MAX_ATTEMPTS_PER_WORKER = 64

REPO_ROOT = Path(__file__).resolve().parents[2]


class RunAborted(RuntimeError):
    """The run could not proceed safely, so it did not proceed at all."""


# ===========================================================================
# Preconditions
# ===========================================================================


async def assert_disposable_redis(redis_client, url: str) -> None:
    """Refuse to run against an instance that has not said it is disposable."""
    try:
        marked = await redis_client.exists(TEST_INSTANCE_MARKER_KEY)
    except Exception as error:  # noqa: BLE001 -- report the URL, not a traceback
        raise RunAborted(f"cannot reach Redis at {url!r}: {error!r}") from None
    if not marked:
        raise RunAborted(
            f"Redis at {url!r} does not advertise {TEST_INSTANCE_MARKER_KEY!r}. "
            "The harness kills processes that hold leases on this instance and "
            "deletes the keys it created, so it refuses to run against an "
            "instance that has not asserted it is disposable:\n"
            f"    redis-cli -n 15 SET {TEST_INSTANCE_MARKER_KEY} 1"
        )


# ===========================================================================
# Worker supervision
# ===========================================================================


def worker_environment(config: RunConfig, crash_execution_ids: Sequence[str]) -> dict:
    """The environment one worker process is launched with."""
    environment = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    point = config.resolved_crash_point
    if point is None or not crash_execution_ids:
        # Absent, not empty: the injector returns None and the workflow's
        # disabled path is `crash_injector is None`.
        environment.pop(CRASH_POINT_VARIABLE, None)
        return environment
    environment[CRASH_POINT_VARIABLE] = config.crash_point or point.value
    environment[CRASH_DELAY_VARIABLE] = str(config.crash_delay_ms)
    environment[CRASH_EXECUTIONS_VARIABLE] = ",".join(crash_execution_ids)
    if config.crash_style:
        environment[CRASH_STYLE_VARIABLE] = config.crash_style
    return environment


def worker_progress(config: RunConfig, worker_index: int) -> tuple[int | None, bool]:
    """Read a worker slot's shards: (last started index, finished cleanly).

    A process that was SIGKILLed cannot report anything, so its progress is
    read out of the run log it flushed on every record.
    """
    last_started: int | None = None
    finished = False
    for shard in sorted(
        config.results_dir.glob(f"events-worker-{worker_index}-attempt-*.jsonl")
    ):
        for record in read_events(shard):
            if record.get("event") == "execution_started":
                index = int(record["execution_index"])
                last_started = index if last_started is None else max(last_started, index)
            elif record.get("event") == "worker_finished":
                finished = True
    return last_started, finished


def run_worker_slot(config: RunConfig, worker_index: int, log: EventLog) -> None:
    """Run one worker slot to completion, respawning it after each crash."""
    items = worker_items(plan_workload(config), worker_index)
    from_index = 0
    for attempt in range(1, MAX_ATTEMPTS_PER_WORKER + 1):
        remaining_crashes = [
            item.execution_id
            for item in items
            if item.crash_selected and item.execution_index >= from_index
        ]
        command = [
            sys.executable,
            "-m",
            worker_module.__name__,
            "--run-config",
            str(config.results_dir / "run-config.json"),
            "--worker-index",
            str(worker_index),
            "--attempt",
            str(attempt),
            "--from-index",
            str(from_index),
        ]
        log.emit(
            "worker_spawned",
            worker_index=worker_index,
            attempt=attempt,
            from_index=from_index,
            crash_armed_for=len(remaining_crashes),
        )
        process = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            env=worker_environment(config, remaining_crashes),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, stderr = process.communicate()
        last_started, finished = worker_progress(config, worker_index)
        log.emit(
            "worker_exited",
            worker_index=worker_index,
            attempt=attempt,
            exit_status=process.returncode,
            finished_cleanly=finished,
            last_started_index=last_started,
            stderr_tail=stderr.decode(errors="replace")[-2000:] if stderr else "",
        )
        if finished:
            return
        if last_started is None:
            raise RunAborted(
                f"worker {worker_index} attempt {attempt} died before starting "
                f"any execution (exit {process.returncode}):\n"
                f"{stderr.decode(errors='replace')[-4000:]}"
            )
        from_index = last_started + 1
        if from_index >= config.executions_per_worker:
            # Killed during its last execution: nothing left to resume.
            return
    raise RunAborted(
        f"worker {worker_index} exhausted {MAX_ATTEMPTS_PER_WORKER} lifetimes"
    )


# ===========================================================================
# Settling and classification
# ===========================================================================


async def execution_status(store: IntentLedgerStore, execution_id: str) -> str:
    """The terminal status of one execution, as the protocol left it."""
    from experiments.harness.reconcile import NO_INTENT

    try:
        state = await store.get_execution(execution_id)
    except Exception as error:  # noqa: BLE001 -- a corrupt state is a result
        return f"UNREADABLE:{type(error).__name__}"
    if state is None or not state.intent_ledger:
        return NO_INTENT
    # One intent per execution in this workload; the newest wins if that ever
    # stops being true.
    intent = sorted(state.intent_ledger.values(), key=lambda item: item.prepared_at)[-1]
    return intent.status.value


async def wait_until_settled(
    config: RunConfig,
    store: IntentLedgerStore,
    execution_ids: Sequence[str],
    log: EventLog,
    recovery_process: subprocess.Popen | None = None,
) -> bool:
    """Wait for recovery to reach a terminal state for every execution.

    Watches the recovery process too. A run that kept polling for its full
    deadline against a recovery service that had already died would report
    "did not settle" -- true, but attributed to the protocol rather than to
    the harness, which is the worst kind of wrong number.
    """
    deadline = time.monotonic() + config.recovery_deadline_seconds
    poll = 0
    while time.monotonic() < deadline:
        if recovery_process is not None and recovery_process.poll() is not None:
            log.emit(
                "recovery_died_during_settling",
                exit_status=recovery_process.returncode,
                poll=poll,
            )
            raise RunAborted(
                "the recovery process exited during settling with status "
                f"{recovery_process.returncode}; see recovery-stderr.log. No "
                "recovery measurement from this run is usable."
            )
        statuses = [
            await execution_status(store, execution_id)
            for execution_id in execution_ids
        ]
        pending = [status for status in statuses if status in PENDING_STATUSES]
        poll += 1
        log.emit(
            "settling_poll",
            poll=poll,
            pending=len(pending),
            settled=len(statuses) - len(pending),
        )
        if not pending:
            return True
        await asyncio.sleep(min(config.recovery_pass_interval_seconds, 2.0))
    return False


# ===========================================================================
# The run
# ===========================================================================


async def execute_run(config: RunConfig) -> dict[str, Any]:
    config.results_dir.mkdir(parents=True, exist_ok=True)
    config_path = config.results_dir / "run-config.json"
    config_path.write_text(json.dumps(config.echo(), indent=2), encoding="utf-8")

    mock_api_config = load_config(config.mock_api_config_path)
    plan = plan_workload(config)
    execution_ids = [item.execution_id for item in plan]

    log = EventLog(
        config.results_dir / "events-runner.jsonl",
        run_id=config.run_id,
        source="runner",
    )
    stop_path = recovery_module.stop_file(config)
    stop_path.unlink(missing_ok=True)

    redis_client = Redis.from_url(config.redis_url, decode_responses=True)
    store = IntentLedgerStore(redis_client)
    toxiproxy: ToxiproxyControl | None = None
    recovery_process: subprocess.Popen | None = None
    recovery_out = recovery_err = None
    poisoned_ids: list[str] = []
    settled = False
    removed = 0

    try:
        await assert_disposable_redis(redis_client, config.redis_url)

        if config.partition_seconds > 0:
            toxiproxy = ToxiproxyControl(
                api_url=config.toxiproxy_api_url,
                proxy_name=config.toxiproxy_proxy_name,
            )
            toxiproxy.describe()  # raises if compose never declared it
            toxiproxy.heal()

        log.emit(
            "run_started",
            run_config=config.echo(),
            mock_api_config=mock_api_config.echo(),
            seeds={
                "run_seed": config.seed,
                "mock_api_seed": mock_api_config.seed,
                "workload_derivation": "sha256(run_id|seed|purpose|worker|index)",
            },
            workload={
                "total_executions": len(plan),
                "crash_selected": sum(1 for item in plan if item.crash_selected),
                "items": [item.echo() for item in plan],
            },
            environment={
                "platform": platform.platform(),
                "python": sys.version.split()[0],
                "has_sigkill": HAS_SIGKILL,
                "kill_mechanism": "SIGKILL" if HAS_SIGKILL else "TerminateProcess",
            },
            crash_point_roadmap_name=(
                roadmap_name_for(config.resolved_crash_point)
                if config.resolved_crash_point
                else None
            ),
        )

        # To files, never to a pipe. The recovery service logs a WARNING for
        # every execution it isolates, on every pass; an unread pipe fills its
        # OS buffer within a few passes and the child blocks forever on write.
        # That is not hypothetical -- it is what the first self-validation run
        # of this harness did, and it froze recovery 14 seconds in while the
        # run went on collecting numbers as though recovery were working.
        recovery_out = (config.results_dir / "recovery-stdout.log").open("wb")
        recovery_err = (config.results_dir / "recovery-stderr.log").open("wb")
        recovery_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                recovery_module.__name__,
                "--run-config",
                str(config_path),
            ],
            cwd=str(REPO_ROOT),
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
            stdout=recovery_out,
            stderr=recovery_err,
        )
        log.emit("recovery_spawned", recovery_pid=recovery_process.pid)

        poisoned_ids = await poison_executions(config, redis_client, log)

        # Worker slots run concurrently; each is a serial chain of lifetimes,
        # so a thread per slot is the whole of the concurrency needed here.
        await asyncio.gather(
            *(
                asyncio.to_thread(run_worker_slot, config, index, log)
                for index in range(config.workers)
            )
        )
        log.emit("all_workers_finished")

        if config.redis_restarts:
            for restart in range(config.redis_restarts):
                record = await restart_redis_and_verify_aof(
                    config, redis_client=redis_client
                )
                log.emit("redis_restarted", restart_number=restart + 1, **record.echo())

        if toxiproxy is not None and config.partition_seconds > 0:
            toxiproxy.partition()
            log.emit("partition_started", seconds=config.partition_seconds)
            await asyncio.sleep(config.partition_seconds)
            toxiproxy.heal()
            log.emit("partition_healed")

        settled = await wait_until_settled(
            config, store, execution_ids, log, recovery_process
        )
        log.emit("settled", settled=settled)

        for execution_id in execution_ids:
            log.emit(
                "final_classification",
                execution_id=execution_id,
                status=await execution_status(store, execution_id),
            )
        for execution_id in poisoned_ids:
            log.emit(
                "poisoned_final_state",
                execution_id=execution_id,
                present=bool(await redis_client.exists(f"aep:state:{execution_id}")),
            )
    finally:
        stop_path.touch()
        if recovery_process is not None:
            try:
                recovery_process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                recovery_process.kill()
                recovery_process.wait(timeout=10)
            log.emit("recovery_exited", exit_status=recovery_process.returncode)
        for handle in (recovery_out, recovery_err):
            if handle is not None:
                handle.close()
        if toxiproxy is not None:
            try:
                toxiproxy.heal()
            finally:
                toxiproxy.close()
        log.emit("run_finished", settled=settled)
        log.close()
        try:
            removed = await delete_run_keys(
                redis_client, [*execution_ids, *poisoned_ids]
            )
        finally:
            await redis_client.aclose()

    merged = config.results_dir / "events.jsonl"
    merge_event_shards(config.results_dir, output=merged)
    records = read_events(merged)
    report = reconcile(merged, mock_api_config.ledger_path)
    summary_path = write_summary(
        config.results_dir,
        report,
        settled=settled,
        keys_removed=removed,
        poisoned_detection=poisoned_detection_latencies(records),
        crash_injections=len(
            [record for record in records if record.get("event") == "crash_injected"]
        ),
    )
    return {
        "events": str(merged),
        "summary": str(summary_path),
        "report": report,
        "settled": settled,
    }


async def poison_executions(
    config: RunConfig, redis_client, log: EventLog
) -> list[str]:
    """Write corrupt state payloads so recovery has something to isolate.

    Retires ``phase-report-1b`` F7 by giving the ``scan_failure_alert`` stream
    something to report and recording the instant each poisoning happened, so
    the detection latency is a measured quantity.
    """
    poisoned: list[str] = []
    for index in range(config.poisoned_executions):
        execution_id = str(uuid.uuid4())
        await redis_client.set(
            f"aep:state:{execution_id}",
            "{not valid state json for AEP at all",
            ex=3600,
        )
        poisoned.append(execution_id)
        log.emit("execution_poisoned", execution_id=execution_id, index=index)
    return poisoned


def default_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


def build_config_from_arguments(arguments) -> RunConfig:
    overrides = {
        key: value
        for key, value in vars(arguments).items()
        if value is not None and key not in {"run_config"}
    }
    overrides.setdefault("run_id", default_run_id())
    return RunConfig(**overrides)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the AEP Phase 2B fault-injection harness."
    )
    parser.add_argument("--run-config", type=Path, help="a saved run-config.json")
    parser.add_argument("--run-id")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--executions-per-worker", type=int)
    parser.add_argument("--crash-point")
    parser.add_argument("--crash-probability", type=float)
    parser.add_argument("--crash-delay-ms", type=int)
    parser.add_argument("--readback-keying")
    parser.add_argument("--endpoint")
    parser.add_argument("--mock-api-config-path")
    parser.add_argument("--mock-api-base-url")
    parser.add_argument("--redis-url")
    parser.add_argument("--worker-redis-url")
    parser.add_argument("--results-root")
    parser.add_argument("--poisoned-executions", type=int)
    parser.add_argument("--redis-restarts", type=int)
    parser.add_argument("--partition-seconds", type=float)
    parser.add_argument("--recovery-deadline-seconds", type=float)
    arguments = parser.parse_args(argv)

    if arguments.run_config is not None:
        config = load_run_config(arguments.run_config)
    else:
        config = build_config_from_arguments(arguments)

    outcome = asyncio.run(execute_run(config))
    report = outcome["report"]
    print(json.dumps(report.echo(), indent=2, sort_keys=True))
    print(f"events:  {outcome['events']}")
    print(f"summary: {outcome['summary']}")
    if not outcome["settled"]:
        print("WARNING: the run did not settle within the recovery deadline")
    return 0 if report.agrees else 1


if __name__ == "__main__":  # pragma: no cover - process entry point
    sys.exit(main())
