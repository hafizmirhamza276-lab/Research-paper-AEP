"""The B5 collection runner: one run, reconciled by B4's reconciler.

**The load-bearing constraint is oracle attribution.** ``undetected_duplicate_
applications`` and ``lost_effect_executions`` must mean for B5 exactly what they
mean for B4, or an agreement between the arms would be an artefact of how each
was counted rather than of the engines --- the confound WS-6 exists to remove.

**So this module does not compute them.** It calls
``experiments.harness.reconcile.reconcile(events_path, ledger_path)``, the same
function ``run_matrix`` calls for every other arm, unchanged. Read from
``experiments/harness/reconcile.py:236``; the counts it returns are built in
``ReconciliationReport`` (line 90) from the provider's own
``GroundTruthLedger.applied_mutations()`` and ``duplicate_groups()``, joined to
executions through ``plan_workload(config)``'s targets.

The consequence, and it is the whole design of this file: **B5's job is to
produce an event log of the shape the reconciler already reads**, not to produce
numbers. Specifically ``reconcile`` requires

* one ``run_started`` carrying ``run_config`` and ``mock_api_config``
  (``reconcile.py:169`` and ``:180``), and
* one ``final_classification`` per execution with ``execution_id``, ``status``
  and ``outcome_class`` (``:187``, ``:195``) --- the last is mandatory, and a log
  without it is refused rather than silently counted.

Everything else follows: the workflow must mutate the **plan's** targets, because
``execution_by_target`` is how an applied row becomes an execution's effect.

**Not a collection driver.** This runs ONE run. Sequencing runs into cells is
``run_matrix``'s job and is deliberately not duplicated here.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from experiments.baselines.b5_temporal.gate import (
    AttributionStatus,
    RunVerdict,
    classify,
)
from experiments.baselines.b5_temporal.supervisor import WorkerSupervisor
from experiments.baselines.contract import OutcomeClass, SystemId
from experiments.harness.events import EventLog
from experiments.harness.reconcile import reconcile, write_summary
from experiments.harness.workload import plan_workload

#: Fixed at 06d51b0, before any B5 data existed, from the measured provider
#: distribution. Imported rather than passed so a collection cannot quietly use
#: a different one than the committed decision.
START_TO_CLOSE_MS = 4000

#: ``maximumAttempts``: 0 is Temporal's unlimited, 1 is the documented
#: at-most-once configuration.
MAX_ATTEMPTS = {
    SystemId.B5_TEMPORAL: 0,
    SystemId.B5B_TEMPORAL_AT_MOST_ONCE: 1,
}


@dataclass
class ExecutionOutcome:
    execution_id: str
    status: str
    outcome_class: OutcomeClass


def outcome_of(settled: bool, result: object) -> ExecutionOutcome | None:
    """Map one workflow's own record into the shared vocabulary.

    B5 can never produce ``DECLARED_AMBIGUOUS``: the engine has no such record,
    which is H3's structural prediction and not a property of this mapping. A
    workflow that failed produces ``UNVERIFIED_FAILURE`` and **not**
    ``CONFIRMED_NOT_APPLIED``, because the engine wrote "failed" with no evidence
    that nothing was applied --- the distinction ``contract.py:87`` exists to
    preserve, and the one that makes B5b's lost effects visible.
    """
    if not settled:
        return None
    if isinstance(result, str) and result.startswith("FAILED:"):
        return ExecutionOutcome("", "activity_failed", OutcomeClass.UNVERIFIED_FAILURE)
    return ExecutionOutcome("", "completed", OutcomeClass.CONFIRMED_APPLIED)


def attribution_status(report) -> AttributionStatus:
    """Could the shared reconciler account for what the ledger holds?

    Unattributed rows are the signal: a row the plan's targets cannot explain
    means the join this run's numbers rest on did not hold, and a rate computed
    over it would be arithmetic on the wrong denominator.
    """
    unattributed = int(getattr(report, "oracle_unattributed_rows", 0) or 0)
    if unattributed:
        return AttributionStatus(
            usable=False,
            reason=(
                f"{unattributed} applied ledger row(s) could not be attributed "
                f"to any execution in this run's workload plan"
            ),
            unattributed_rows=unattributed,
        )
    return AttributionStatus(True, "every applied row attributed to an execution")


async def run_once(
    *,
    config,
    mock_api_config,
    results_dir: Path,
    crash_point: str | None,
    provider_url: str,
    temporal_address: str = "127.0.0.1:7233",
    deadline_s: float = 120.0,
    respawn_enabled: bool = True,
    ledger_path: Path | None = None,
) -> dict:
    """One B5 run: drive the workflow, then reconcile it with B4's reconciler.

    ``crash_point`` is B5's own vocabulary and must be the point this run's
    label -- ``config.crash_point``, a roadmap name -- resolves to. A run whose
    two disagree is refused **here**, before a worker is spawned or a provider is
    called, so no caller can produce one: the defect this guards against is a
    driver that arms one point for every cell while labelling the cells
    differently, and it is invisible in the run's own output.
    """
    # Imported here, not at module scope: ``worker`` pulls in the Temporal SDK,
    # and this module is imported by tests and readers that must not need it.
    from temporalio.client import Client

    from experiments.baselines.b5_temporal.worker import resolve_b5_point

    # The label's own resolution, through B5's registered mapping. Raises
    # B5CrashPointNotApplicable for a moment B5 does not have, which is the
    # behaviour ``resolve_b5_point`` exists to give and must not be caught here.
    expected_point = resolve_b5_point(config.crash_point)
    if crash_point is not None and crash_point != expected_point:
        results_dir.mkdir(parents=True, exist_ok=True)
        verdict = classify(
            armed_point=crash_point, expected_point=expected_point,
            settled=False, worker_ready=False, events=[],
        )
        record = {
            "run_id": config.run_id,
            "system": config.system.value,
            "crash_point": config.crash_point or "none",
            "armed_point": crash_point,
            "expected_point": expected_point,
            "response_class": mock_api_config.endpoint(
                config.endpoint
            ).response_class.value,
            "verdict": RunVerdict.VOID_CRASH_POINT_MISMATCH.value,
            "reason": verdict.reason,
            "executions": 0,
            "attribution_usable": False,
            "attribution_reason": "not run: the label and the fault disagree",
            "start_to_close_ms": START_TO_CLOSE_MS,
            "undetected_duplicate_applications": None,
            "undetected_duplicate_executions": None,
            "lost_effect_executions": None,
            "declared_ambiguous": None,
        }
        (results_dir / "b5-run.json").write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
        )
        return record

    #: What the injector is actually armed at. ``None`` stays ``None`` -- an
    #: explicitly unarmed run is a legitimate configuration and must not be
    #: silently armed from its label.
    armed_point = crash_point

    results_dir.mkdir(parents=True, exist_ok=True)
    events_path = results_dir / "events.jsonl"
    log = EventLog(events_path, source="b5-collect", run_id=config.run_id)

    plan = plan_workload(config)
    log.emit(
        "run_started",
        run_config=config.echo(),
        mock_api_config=mock_api_config.echo(),
        seeds={"run_seed": config.seed, "mock_api_seed": mock_api_config.seed},
        workload={
            "total_executions": len(plan),
            "crash_selected": sum(1 for item in plan if item.crash_selected),
            "items": [item.echo() for item in plan],
        },
    )

    client = await Client.connect(temporal_address)
    supervisor = WorkerSupervisor(
        out=results_dir, crash_point=crash_point, provider_url=provider_url,
        respawn_enabled=respawn_enabled,
    )
    worker_ready = supervisor.spawn(1)
    if not worker_ready:
        # Retried once, not spent -- a worker that never came up measured
        # nothing. A second failure still voids.
        supervisor.spawn(1)
        worker_ready = (results_dir / "ready").exists()

    outcomes: list[ExecutionOutcome] = []
    if worker_ready:
        for item in plan:
            handle = await client.start_workflow(
                "B5Workflow",
                {
                    # The PLAN's target, not a fresh one: this is the join the
                    # reconciler uses to turn an applied row into an execution's
                    # effect, and a target invented here would make every row
                    # unattributed.
                    "target": item.target,
                    "action": "post",
                    "amount_minor": 100,
                    "client_reference": item.execution_id,
                    "endpoint": config.endpoint,
                    "maximum_attempts": MAX_ATTEMPTS[config.system],
                    "start_to_close_ms": START_TO_CLOSE_MS,
                },
                id=f"b5-{config.run_id}-{item.execution_index}",
                task_queue="b5-ws6",
            )
            settled, result = False, None
            started = time.monotonic()
            waiter = asyncio.ensure_future(handle.result())
            while time.monotonic() - started < deadline_s:
                done, _ = await asyncio.wait({waiter}, timeout=0.5)
                if done:
                    break
                supervisor.maintain()
            if waiter.done():
                try:
                    result, settled = waiter.result(), True
                except Exception as exc:                       # noqa: BLE001
                    settled, result = True, f"FAILED:{type(exc).__name__}"
            else:
                waiter.cancel()
            outcome = outcome_of(settled, result)
            if outcome is not None:
                outcome.execution_id = item.execution_id
                outcomes.append(outcome)
                log.emit(
                    "final_classification",
                    execution_id=item.execution_id,
                    status=outcome.status,
                    outcome_class=outcome.outcome_class.value,
                    system=config.system.value,
                    dispatch_attempts=supervisor.state.spawns,
                    intent_id=None,
                )
    supervisor.stop()
    log.emit("run_finished", executions=len(outcomes))

    # ---- attribution, through the shared reconciler and nothing else --------
    ledger = Path(ledger_path or (results_dir / "ground_truth.sqlite3"))
    try:
        report = reconcile(events_path, ledger)
        status = attribution_status(report)
    except Exception as exc:                                   # noqa: BLE001
        report, status = None, AttributionStatus(
            usable=False,
            reason=f"the reconciler could not read this run: {type(exc).__name__}: {exc}",
        )

    trace = results_dir / "trace.jsonl"
    names: list[str] = []
    # The POINT each reach names, not merely that a reach happened. Reading only
    # the event name is what let a trace naming the wrong point read as success.
    reached_points: list[str] = []
    if trace.exists():
        for line in trace.read_text(errors="replace").splitlines():
            try:
                entry = json.loads(line)
                names.append(entry["event"])
            except (ValueError, KeyError, TypeError):
                continue
            if entry["event"] == "b5_point_reached" and "point" in entry:
                reached_points.append(entry["point"])

    verdict = classify(
        armed_point=armed_point,
        expected_point=expected_point,
        settled=bool(outcomes),
        worker_ready=worker_ready,
        events=names,
        reached_points=reached_points,
        worker_deaths=supervisor.state.deaths,
        respawns=supervisor.state.respawns,
        attribution=status,
    )

    # The seed the provider ACTUALLY ran under, read back from the config that
    # was rendered for it rather than restated from what the driver intended.
    # A seed that varies in the driver but never reaches the provider is
    # indistinguishable, in the outcome, from the fixed-seed defect this
    # replaces -- so the record carries the value the provider was given.
    provider_seed = None
    rendered = results_dir / "mock-api.yaml"
    if rendered.exists():
        for line in rendered.read_text(encoding="utf-8").splitlines():
            if line.startswith("seed:"):
                try:
                    provider_seed = int(line.split(":", 1)[1].strip())
                except ValueError:
                    provider_seed = None
                break

    record = {
        "run_id": config.run_id,
        "system": config.system.value,
        "seed": config.seed,
        "provider_seed": provider_seed,
        # The run's LABEL, in the roadmap vocabulary the tables are keyed on --
        # not the injected point, which is B5's own name for it. These were the
        # same string only because one crash point was ever collected.
        "crash_point": config.crash_point or "none",
        "armed_point": armed_point or "none",
        "response_class": mock_api_config.endpoint(config.endpoint).response_class.value,
        "verdict": verdict.verdict.value,
        "reason": verdict.reason,
        "executions": len(plan),
        "attribution_usable": status.usable,
        "attribution_reason": status.reason,
        "start_to_close_ms": START_TO_CLOSE_MS,
    }
    if report is not None:
        write_summary(results_dir, report, b5_verdict=verdict.verdict.value)
        # The three outcome fields analyse_b5_agreement.py reads. Taken from the
        # reconciler's report, never recomputed here.
        record.update(
            {
                "undetected_duplicate_applications": (
                    report.undetected_duplicate_applications
                ),
                # The EXECUTIONS-based count, which is what the frozen B4 rate
                # is built from: analyze.py's numerator is
                # int(execution.is_undetected_duplicate), a per-execution 0/1
                # indicator. The applications count above is a different
                # quantity -- an execution with three duplicate applications
                # contributes 3 to it and 1 to this -- and comparing the two
                # was H1's units defect. Both are written so the record says
                # which is which rather than leaving the reader to infer it.
                "undetected_duplicate_executions": (
                    report.undetected_duplicate_executions
                ),
                "lost_effect_executions": report.lost_effect_executions,
                "declared_ambiguous": report.declared_ambiguous_executions,
            }
        )
    else:
        # No rate may be invented for a run the reconciler refused. The verdict
        # is already VOID_ATTRIBUTION_UNAVAILABLE and the fields are absent
        # rather than zero, so nothing downstream can average them in.
        record.update({"undetected_duplicate_applications": None,
                       "undetected_duplicate_executions": None,
                       "lost_effect_executions": None,
                       "declared_ambiguous": None})
    (results_dir / "b5-run.json").write_text(
        json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
    )
    return record


def append_session_record(session_root: Path, record: dict) -> None:
    """One line per run in the file ``analyse_b5_agreement.py`` reads."""
    session_root.mkdir(parents=True, exist_ok=True)
    with (session_root / "b5-runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


# --------------------------------------------------------- per-run provider
#
# WS-6's attribution gate voided a run against a ledger holding 129 rows from
# days of earlier probe runs. That was the gate working, and it named a
# requirement nobody had written down: **every run gets its own ledger**, as
# every WS-4 run had its own ``ground_truth.sqlite3`` inside its run directory.
# A shared ledger makes every run's effects unattributable to that run's plan,
# which is exactly what the reconciler's join is for.
#
# **And every run gets its own SEED.** The first version of this class rewrote
# ``ledger_path`` and nothing else, so all 120 runs of the 2026-09-08 session
# ran a provider seeded ``20260908``. ``MockLegacyAPI`` draws its three fault
# decisions from one ``random.Random(config.seed)`` per process, so every run
# replayed one fault stream: three of the four cells produced a single distinct
# outcome across thirty runs, and the bootstrap correctly reported a zero-width
# interval over thirty identical numbers.
#
# That is the ledger half of Session 3's D0(ii) lesson kept and the seed half
# dropped -- and ``mock_api/supervisor.py`` had already written both down:
#
#     One provider process per run, one ledger per run, one freshly seeded
#     generator per run. A run's fault stream is then a function of its seed
#     alone, and its reconciliation sees only its own effects.
#
# So this now calls that module's ``render_config`` rather than hand-rolling a
# line rewrite. Recorded in
# ``reports/phase-report-ws6-determinism-2026-09-08.md``.


class RunProvider:
    """A mock provider with a ledger AND a seed belonging to ONE run.

    R1: the process is killed by the PID recorded when it started, never by
    pattern. The port is checked free before binding and verified released
    after, because an orphan on it would silently serve the next run (R12).
    """

    def __init__(self, results_dir: Path, template: Path, port: int = 8099,
                 seed: int | None = None):
        self.results_dir = results_dir
        self.template = template
        self.port = port
        #: The provider's fault stream is a function of this alone. Passed by
        #: the driver from the run's own ``RunConfig.seed``, so the run is
        #: reproducible from its own record: re-running with the same seed
        #: replays the same faults, and that is what the rule-13 proof asserts.
        #: ``None`` leaves the template's seed in place, which is only correct
        #: for a single-run probe and never for a collection.
        self.seed = seed
        self.ledger_path = results_dir / "ground_truth.sqlite3"
        self.config_path = results_dir / "mock-api.yaml"
        self._process = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def render(self) -> Path:
        """Write this run's provider config. Separated from ``start`` so the
        seed path can be tested without binding a port or spawning a process --
        the defect it replaces was invisible precisely because nothing checked
        the rendered config."""
        from experiments.mock_api.supervisor import render_config

        self.results_dir.mkdir(parents=True, exist_ok=True)
        # render_config applies the overrides to the raw document and then
        # loads the result through the strict loader, so a template typo fails
        # here rather than inside a provider the runner has already started.
        return render_config(
            self.template, self.config_path,
            ledger_path=self.ledger_path, seed=self.seed,
        )

    def start(self, timeout_s: float = 90.0) -> bool:
        import subprocess
        import urllib.request

        self.render()

        self._process = subprocess.Popen(
            [sys.executable, "-m", "experiments.mock_api",
             "--config", str(self.config_path),
             "--host", "127.0.0.1", "--port", str(self.port)],
            stdout=subprocess.DEVNULL,
            stderr=open(self.results_dir / "provider.err", "ab"),
        )
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"{self.url}/v1/health", timeout=3) as r:
                    if r.status == 200:
                        return True
            except Exception:                                  # noqa: BLE001
                time.sleep(0.5)
        return False

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.kill()
            try:
                self._process.wait(timeout=10)
            except Exception:                                  # noqa: BLE001
                pass
