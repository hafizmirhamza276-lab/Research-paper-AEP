"""One worker process: ``python -m experiments.harness.worker``.

A worker is an ordinary OS process that executes a slice of the workload
through the EVALUATION composition and, if the run selected it, stops existing
partway through. It is spawned by ``experiments/harness/runner.py`` and is not
meant to be run by hand except when debugging.

**Progress is recorded, not returned.** A SIGKILLed process returns nothing.
The runner therefore reads a dead worker's shard of ``events.jsonl`` to learn
which execution it had reached, and respawns from the next one -- which is what
a supervisor does with a crashed worker, and which is what makes the crashed
execution's fate a matter for the recovery service rather than for a retry
loop. Nothing here ever re-executes an execution it may already have
dispatched: that is the behaviour under test, not a behaviour to work around.

**One crash per process.** The injector fires once. A run that wants ten
crashed executions gets ten worker lifetimes, which is also what makes the
lease-expiry timing realistic: the lease of a crashed execution is held by a
process that no longer exists until Redis expires it.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

from redis.asyncio import Redis

from aep_core.core.intent_workflow import DispatchMode
from aep_core.core.locks import DistributedLockManager
from aep_core.core.storage import RedisStorageAdapter

from experiments.baselines.contract import SystemId
from experiments.baselines.crash_points import (
    DEFERRED_BASELINE_POINTS,
    resolve_for_system,
    uses_aep_crash_points,
)
from experiments.harness.composition import (
    build_connector,
    build_system,
    seed_execution_state,
)
from experiments.harness.crash_points import (
    DEFERRED_CRASH_POINTS,
    resolve_crash_point,
)
from experiments.harness.config import RunConfig, load_run_config
from experiments.harness.events import EventLog
from experiments.harness.injector import (
    DurabilityAckObserver,
    ProcessCrashInjector,
    TransmissionObserver,
    compose_injectors,
)
from experiments.harness.redis_kill import RedisKillInjector, canary_payload
from experiments.harness.workload import (
    index_by_execution_id,
    plan_workload,
    request_for,
    worker_items,
)

#: Exit status a worker uses when it failed for a reason the run did not
#: schedule. Distinguished from an injected crash, which leaves no exit status
#: of its own choosing at all.
UNEXPECTED_FAILURE_EXIT = 70


def shard_path(config: RunConfig, worker_index: int, attempt: int) -> Path:
    return config.results_dir / f"events-worker-{worker_index}-attempt-{attempt}.jsonl"


def source_name(worker_index: int, attempt: int) -> str:
    return f"worker-{worker_index}#{attempt}"


async def run_worker(
    config: RunConfig, *, worker_index: int, attempt: int, from_index: int
) -> int:
    log = EventLog(
        shard_path(config, worker_index, attempt),
        run_id=config.run_id,
        source=source_name(worker_index, attempt),
    )
    # Each system announces its own instruction boundaries, so the injector
    # is handed that system's resolver rather than being told which system is
    # running. See experiments/baselines/crash_points.py for why the roadmap's
    # six names do not all exist in all six systems.
    if uses_aep_crash_points(config.system):
        resolver, deferred = resolve_crash_point, DEFERRED_CRASH_POINTS
    else:
        def resolver(name, _system=config.system):
            return resolve_for_system(_system, name)

        deferred = DEFERRED_BASELINE_POINTS
    crash_injector = ProcessCrashInjector.from_environment(
        emit=log.emit, resolver=resolver, deferred_points=deferred
    )

    items = [
        item
        for item in worker_items(plan_workload(config), worker_index)
        if item.execution_index >= from_index
    ]

    redis_client = Redis.from_url(
        config.effective_worker_redis_url, decode_responses=True
    )

    async def write_canary(key: str) -> None:
        # Deliberately un-acknowledged: whether this write survives the kill is
        # the measurement. Putting it through WAITAOF would guarantee it does.
        await redis_client.set(key, canary_payload(config.run_id), ex=3600)

    # Amendment E1. Resolved in the same vocabulary the crash point uses, so a
    # kill can be aimed at any instruction boundary the running system
    # announces -- in particular at the window between the intent CAS and the
    # barrier's acknowledgement, which is the one the ablation is about.
    redis_killer = RedisKillInjector.from_environment(
        emit=log.emit,
        resolver=resolver,
        write_canary=write_canary,
        run_id=config.run_id,
    )
    # The Redis kill is listed first: a synchronous worker kill at the same
    # checkpoint never returns, and an injector after it would never fire.
    #
    # The acknowledgement observer sits between them for the same reason, and
    # the ordering is the whole point at one crash point in particular. When
    # the crash point is `after_barrier_before_dispatch`, the worker is killed
    # at the instant this observer reports on -- and the run in which the ack
    # was issued and the process then died before dispatching is precisely the
    # one the fail-closed invariant is about. Listed after the crash injector,
    # that run would record nothing and the invariant would look vacuous.
    #
    # **It is attached only where a fault injector already exists**, and that
    # restraint is deliberate. `compose_injectors` returns None when nothing is
    # selected, and a None injector makes `WriteAheadRunner._checkpoint` a
    # no-op: a crash-free `p0` run currently dispatches no checkpoints at all.
    # Attaching the observer unconditionally would switch that machinery on in
    # exactly the cells RQ3's latency numbers come from -- the only cells the
    # cost result may use -- changing their conditions relative to every
    # crash-free run already collected. It would also start resolving names
    # through `crash_point_enum`, which for a baseline system is
    # `BaselineCrashPoint` and need not contain the acknowledgement boundary at
    # all. The observer is worth having wherever the invariant can be exercised;
    # it is not worth perturbing the one regime that measures cost, where
    # nothing prevents a dispatch and the invariant is vacuous anyway.
    observer = (
        DurabilityAckObserver(emit=log.emit)
        if (redis_killer is not None or crash_injector is not None)
        else None
    )
    injector = compose_injectors(redis_killer, observer, crash_injector)

    log.emit(
        "worker_started",
        worker_index=worker_index,
        attempt=attempt,
        from_index=from_index,
        assigned=len(items),
        crash_plan=(
            crash_injector.plan.echo() if crash_injector is not None else None
        ),
        redis_kill_plan=(
            redis_killer.plan.echo() if redis_killer is not None else None
        ),
        redis_url=config.effective_worker_redis_url,
    )
    connector = build_connector(
        config, items=index_by_execution_id(plan_workload(config))
    )
    # Phase 13 prerequisite. Marks the instant provider bytes leave, so each
    # arm's post-arming exposure is measured rather than argued. Gated on the
    # same condition as the acknowledgement observer above and for the same
    # reason: it puts an EventLog.emit on the dispatch path, and the crash-free
    # p0 cells are the ones RQ3's cost numbers come from.
    if observer is not None:
        connector = TransmissionObserver(connector=connector, emit=log.emit)
    exit_status = 0
    try:
        lock_manager = DistributedLockManager(redis_client)
        storage_adapter = RedisStorageAdapter(redis_client)
        runner = build_system(
            config,
            redis_client=redis_client,
            lock_manager=lock_manager,
            connector=connector,
            crash_injector=injector,
        )

        await runner.validate_startup()
        log.emit(
            "composition_validated",
            system=config.system.value,
            resume_policy=config.effective_resume_policy.value,
            dispatch_mode=getattr(runner, "mode", DispatchMode.EVALUATION).value,
            barrier=type(getattr(runner, "barrier", None)).__name__,
            vault=type(
                getattr(getattr(runner, "binding_service", None), "vault", None)
            ).__name__,
            connector=type(connector).__name__,
            # Discovered from the object, not spelled out: any truthy
            # ``allow_*`` attribute the runner carries is named here, so the
            # run log is the evidence that no test affordance was granted --
            # and a future affordance would appear without this line changing.
            # (Naming them as literals would also trip the source gate in
            # ``tests/test_composition.py``, which is the point of that gate.)
            test_authorisations=sorted(
                name
                for name in vars(runner)
                if name.startswith("allow_") and getattr(runner, name)
            ),
        )

        for item in items:
            if injector is not None:
                injector.enter_execution(item.execution_id)
            log.emit(
                "execution_started",
                worker_index=worker_index,
                execution_index=item.execution_index,
                execution_id=item.execution_id,
                target=item.target,
                amount_minor=item.amount_minor,
                crash_selected=item.crash_selected,
            )
            started = time.monotonic_ns()
            try:
                if config.descriptor.uses_fenced_state_writes:
                    # The fenced write path requires the record to exist. The
                    # systems that do not use it must not have one seeded for
                    # them: a state key B0 never wrote would misreport what B0
                    # leaves behind.
                    await seed_execution_state(
                        storage_adapter=storage_adapter,
                        lock_manager=lock_manager,
                        execution_id=item.execution_id,
                    )
                resolved = await runner.execute(
                    execution_id=item.execution_id,
                    step_id=item.step_id,
                    request=request_for(item),
                )
            except BaseException as error:  # noqa: BLE001 -- recorded, then re-raised
                log.emit(
                    "execution_failed",
                    execution_id=item.execution_id,
                    execution_index=item.execution_index,
                    failure_class=type(error).__name__,
                    duration_ns=time.monotonic_ns() - started,
                )
                if isinstance(error, (KeyboardInterrupt, SystemExit)):
                    raise
                exit_status = UNEXPECTED_FAILURE_EXIT
                continue

            log.emit(
                "execution_resolved",
                execution_id=item.execution_id,
                execution_index=item.execution_index,
                intent_id=resolved.intent_id,
                status=resolved.status,
                outcome_class=resolved.outcome_class.value,
                dispatch_attempts=resolved.dispatch_attempts,
                request_fingerprint=resolved.request_fingerprint,
                duration_ns=time.monotonic_ns() - started,
            )
    finally:
        if redis_killer is not None:
            # The kill is issued on a thread. Leaving the process before it has
            # been issued would silently drop the run's only infrastructure
            # fault, and the run would look like a clean one.
            redis_killer.join_watchdog(timeout=60.0)
        log.emit("worker_finished", worker_index=worker_index, attempt=attempt)
        try:
            await connector.aclose()
        finally:
            try:
                await redis_client.aclose()
            except Exception:  # noqa: BLE001 -- the server may be the fault
                pass
            log.close()
    return exit_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one AEP harness worker.")
    parser.add_argument("--run-config", required=True, type=Path)
    parser.add_argument("--worker-index", required=True, type=int)
    parser.add_argument("--attempt", required=True, type=int)
    parser.add_argument("--from-index", default=0, type=int)
    arguments = parser.parse_args(argv)

    config = load_run_config(arguments.run_config)
    return asyncio.run(
        run_worker(
            config,
            worker_index=arguments.worker_index,
            attempt=arguments.attempt,
            from_index=arguments.from_index,
        )
    )


if __name__ == "__main__":  # pragma: no cover - process entry point
    sys.exit(main())
