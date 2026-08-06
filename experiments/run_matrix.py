"""The evaluation matrix, as code rather than as a paragraph.

Amendment D2: *"experiments/run_matrix.py executes {system x crash-point x
response-class x read-back-keying} with 30 repetitions per cell, resumable,
seeds recorded, every run in EVALUATION mode on Linux. Before launching, emit
the full matrix plan (cell list + estimated wall time) into the report and the
results directory."*

Four decisions in here are methodological and are stated up front, because
each of them determines what a number in the paper means.

**What a repetition is.** A *cell* needs at least 30 repetitions. The unit of
the metrics in PAPER_ROADMAP.md section 3.2 is one agent execution -- one
intended non-idempotent effect -- so a repetition is one execution, and a cell
is collected as ``runs_per_cell`` independent runs of ``executions_per_run``
executions (3 x 10 by default). Both numbers are recorded. Collecting all 30 in
a single run would make them share one provider, one lease namespace and one
worker-respawn history; collecting 30 separate runs of one execution would cost
thirty provider starts and thirty settling periods per cell and buy nothing but
a longer wall time. Splitting the difference means run-level effects are
sampled too, which is what lets ``analyze.py`` report a cluster-aware interval
rather than assuming thirty independent draws.

**Inapplicable cells are recorded, not filled.** ``after_intent_before_barrier``
does not exist in B0, B1 or B2: those systems write nothing before dispatching,
so there is no window between writing a record and acknowledging it durable.
The plan carries those cells with ``applicable: false`` and the reason, and
nothing is run for them. Aliasing them onto a neighbouring crash point would
have produced a full row of numbers for an experiment that was never performed.

**Every run is isolated.** One provider process, one ledger, one freshly seeded
fault generator per run -- see ``experiments/harness/orchestrate.py`` for the
D0(ii) failure that made this non-negotiable.

**Order is by informativeness, not by loop nesting.** A matrix this size will
not finish in one sitting, so the schedule is tiered: the cells that make up
the paper's Table 1 run first, the remaining response classes second, and the
read-back-keying sensitivity variant last. A partial matrix is then a *usable*
partial matrix, and ``--plan-only`` prints exactly which cells are in which
tier before anything is launched.

    python -m experiments.run_matrix --plan-only
    python -m experiments.run_matrix --redis-url redis://127.0.0.1:6381/15
    python -m experiments.run_matrix --resume        # skips completed runs
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from experiments.baselines.contract import SystemId, descriptor_for
from experiments.baselines.crash_points import (
    NOT_APPLICABLE_REASONS,
    CrashPointNotApplicable,
    resolve_for_system,
)
from experiments.harness.crash_points import ROADMAP_CRASH_POINTS
from experiments.harness.injector import HAS_SIGKILL
from experiments.harness.orchestrate import run_once
from experiments.mock_api.config import ReadbackKeying

#: The matrix's own version. Bumping it is a statement that cells collected
#: under the previous one are not comparable to new ones.
MATRIX_VERSION = "aep.matrix/1"

DEFAULT_TEMPLATE = Path("experiments/configs/matrix.yaml")
DEFAULT_RESULTS_ROOT = "experiments/results/matrix"

#: The response classes, named by the endpoint that declares each one in
#: ``experiments/configs/matrix.yaml``. The dimension is the *capability*; the
#: endpoint is how a run selects it.
ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("payments", "AUTHORITATIVE_READBACK"),
    ("notifications", "POSITIVE_ONLY_READBACK"),
    ("ledger_postings", "NO_READBACK"),
)

SYSTEM_ORDER: tuple[SystemId, ...] = (
    SystemId.AEP_FULL,
    SystemId.B0_NAIVE_RETRY,
    SystemId.B1_LEASE_ONLY,
    SystemId.B2_CAS_ONLY,
    SystemId.B3_INTENT_NO_BARRIER,
    SystemId.B4_DURABLE_WORKFLOW,
)

#: Wall-time model, in seconds, measured from the D0(ii) smoke matrix and the
#: Session 2 self-validation. Deliberately crude and deliberately recorded: a
#: plan that estimates its own cost must say where the estimate came from, and
#: the plan file carries the residual against the actual once a run completes.
PROVIDER_START_SECONDS = 2.5
PER_EXECUTION_SECONDS = 3.2
#: Systems with a recovery service wait for crashed executions to be
#: classified; lease TTL plus the reconciliation delay dominates it.
SETTLE_SECONDS_WITH_RECOVERY = 45.0
SETTLE_SECONDS_WITHOUT_RECOVERY = 1.0


@dataclass(frozen=True)
class Cell:
    """One point of the matrix, and whether it can be visited at all."""

    system: SystemId
    crash_point: str
    endpoint: str
    response_class: str
    readback_keying: ReadbackKeying
    tier: int
    applicable: bool
    reason: str | None = None

    @property
    def key(self) -> str:
        return "|".join(
            (
                self.system.value,
                self.crash_point,
                self.endpoint,
                self.readback_keying.value,
            )
        )

    @property
    def slug(self) -> str:
        """A short, stable, filesystem-safe identifier for the cell.

        Readable prefix plus a digest of the full key: the prefix is for a
        human scanning a directory listing, the digest is what guarantees two
        different cells never collide on one results directory.
        """
        digest = hashlib.sha256(self.key.encode("utf-8")).hexdigest()[:8]
        return f"{self.system.value.lower()}-{self.crash_point}-{self.endpoint}-{digest}"

    def echo(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "slug": self.slug,
            "system": self.system.value,
            "crash_point": self.crash_point,
            "endpoint": self.endpoint,
            "response_class": self.response_class,
            "readback_keying": self.readback_keying.value,
            "tier": self.tier,
            "applicable": self.applicable,
            "reason": self.reason,
        }


def _tier(endpoint: str, keying: ReadbackKeying) -> int:
    """Which pass a cell belongs to. Lower runs first.

    Tier 1 is the paper's Table 1: every system at every crash point against
    the authoritative-read-back endpoint under the primary keying. Tier 2 adds
    the other two response classes. Tier 3 is the ``ORACLE_FINGERPRINT``
    sensitivity variant, which ``docs/24-readback-keying.md`` argues is more
    generous than a real legacy endpoint and is therefore a robustness check
    rather than a headline.
    """
    if keying is ReadbackKeying.ORACLE_FINGERPRINT:
        return 3
    return 1 if endpoint == "payments" else 2


def build_cells(
    *,
    systems: Sequence[SystemId] = SYSTEM_ORDER,
    crash_points: Sequence[str] = tuple(ROADMAP_CRASH_POINTS),
    endpoints: Sequence[tuple[str, str]] = ENDPOINTS,
    keyings: Sequence[ReadbackKeying] = tuple(ReadbackKeying),
) -> tuple[Cell, ...]:
    """The complete cross product, including the cells that cannot be run."""
    cells: list[Cell] = []
    for system in systems:
        for crash_point in crash_points:
            try:
                resolve_for_system(system, crash_point)
                applicable, reason = True, None
            except CrashPointNotApplicable:
                applicable = False
                reason = NOT_APPLICABLE_REASONS.get(
                    crash_point, "this system has no such moment"
                )
            for endpoint, response_class in endpoints:
                for keying in keyings:
                    cells.append(
                        Cell(
                            system=system,
                            crash_point=crash_point,
                            endpoint=endpoint,
                            response_class=response_class,
                            readback_keying=keying,
                            tier=_tier(endpoint, keying),
                            applicable=applicable,
                            reason=reason,
                        )
                    )
    return tuple(cells)


def estimated_run_seconds(cell: Cell, executions_per_run: int, workers: int) -> float:
    """A crude, stated, checkable model of one run's wall time."""
    descriptor = descriptor_for(cell.system)
    per_worker = max(1, executions_per_run // max(1, workers))
    settle = (
        SETTLE_SECONDS_WITH_RECOVERY
        if descriptor.has_recovery_service
        else SETTLE_SECONDS_WITHOUT_RECOVERY
    )
    return PROVIDER_START_SECONDS + per_worker * PER_EXECUTION_SECONDS + settle


def cell_seed(matrix_seed: int, cell: Cell, repetition: int) -> int:
    """A reproducible seed per (matrix, cell, repetition).

    Derived rather than drawn: the plan can then state every seed it will use
    before any of them is used, and a re-run of one cell reproduces exactly the
    workload and fault stream the first collection saw.
    """
    material = f"{matrix_seed}|{MATRIX_VERSION}|{cell.key}|{repetition}"
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    # Kept inside 2**31 so it is representable everywhere a seed is echoed.
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


@dataclass
class MatrixPlan:
    """Everything the matrix will do, decided before any of it is done."""

    cells: tuple[Cell, ...]
    runs_per_cell: int
    executions_per_run: int
    workers: int
    matrix_seed: int
    results_root: str
    template: str
    redis_url: str
    runs: list[dict[str, Any]] = field(default_factory=list)

    @property
    def applicable_cells(self) -> list[Cell]:
        return [cell for cell in self.cells if cell.applicable]

    @property
    def estimated_seconds(self) -> float:
        return sum(entry["estimated_seconds"] for entry in self.runs)

    def echo(self) -> dict[str, Any]:
        by_tier: dict[str, dict[str, Any]] = {}
        for entry in self.runs:
            tier = str(entry["tier"])
            bucket = by_tier.setdefault(tier, {"runs": 0, "estimated_seconds": 0.0})
            bucket["runs"] += 1
            bucket["estimated_seconds"] += entry["estimated_seconds"]
        return {
            "matrix_version": MATRIX_VERSION,
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "has_sigkill": HAS_SIGKILL,
            "matrix_seed": self.matrix_seed,
            "runs_per_cell": self.runs_per_cell,
            "executions_per_run": self.executions_per_run,
            "repetitions_per_cell": self.runs_per_cell * self.executions_per_run,
            "workers": self.workers,
            "results_root": self.results_root,
            "template": self.template,
            "redis_url": self.redis_url,
            "cells_total": len(self.cells),
            "cells_applicable": len(self.applicable_cells),
            "cells_not_applicable": len(self.cells) - len(self.applicable_cells),
            "runs_total": len(self.runs),
            "estimated_seconds": round(self.estimated_seconds, 1),
            "estimated_hours": round(self.estimated_seconds / 3600.0, 2),
            "estimate_model": {
                "provider_start_seconds": PROVIDER_START_SECONDS,
                "per_execution_seconds": PER_EXECUTION_SECONDS,
                "settle_seconds_with_recovery": SETTLE_SECONDS_WITH_RECOVERY,
                "settle_seconds_without_recovery": SETTLE_SECONDS_WITHOUT_RECOVERY,
                "source": (
                    "measured from the D0(ii) smoke matrix (six runs, 6 "
                    "executions each) and the Session 2 self-validation"
                ),
            },
            "by_tier": by_tier,
            "cells": [cell.echo() for cell in self.cells],
            "runs": self.runs,
        }


def build_plan(arguments) -> MatrixPlan:
    cells = build_cells(
        systems=arguments.systems or SYSTEM_ORDER,
        crash_points=arguments.crash_points or tuple(ROADMAP_CRASH_POINTS),
        keyings=arguments.keyings or tuple(ReadbackKeying),
    )
    plan = MatrixPlan(
        cells=cells,
        runs_per_cell=arguments.runs_per_cell,
        executions_per_run=arguments.executions_per_run,
        workers=arguments.workers,
        matrix_seed=arguments.matrix_seed,
        results_root=arguments.results_root,
        template=str(arguments.template),
        redis_url=arguments.redis_url,
    )
    for cell in cells:
        if not cell.applicable:
            continue
        if cell.tier > arguments.max_tier:
            continue
        for repetition in range(arguments.runs_per_cell):
            plan.runs.append(
                {
                    "run_id": f"{cell.slug}-r{repetition}",
                    "cell_key": cell.key,
                    "cell_slug": cell.slug,
                    "tier": cell.tier,
                    "system": cell.system.value,
                    "crash_point": cell.crash_point,
                    "endpoint": cell.endpoint,
                    "response_class": cell.response_class,
                    "readback_keying": cell.readback_keying.value,
                    "repetition": repetition,
                    "seed": cell_seed(arguments.matrix_seed, cell, repetition),
                    "estimated_seconds": round(
                        estimated_run_seconds(
                            cell, arguments.executions_per_run, arguments.workers
                        ),
                        1,
                    ),
                }
            )
    plan.runs.sort(key=lambda entry: (entry["tier"], entry["cell_key"], entry["repetition"]))
    return plan


def render_plan(plan: MatrixPlan) -> str:
    """The human-readable plan. Written next to the machine-readable one."""
    echo = plan.echo()
    lines = [
        "=" * 78,
        f"AEP evaluation matrix plan ({MATRIX_VERSION})",
        "=" * 78,
        f"  platform             {echo['platform']}",
        f"  python               {echo['python']}",
        f"  real SIGKILL         {echo['has_sigkill']}",
        f"  matrix seed          {echo['matrix_seed']}",
        f"  repetitions/cell     {echo['repetitions_per_cell']} "
        f"({echo['runs_per_cell']} runs x {echo['executions_per_run']} executions)",
        f"  workers per run      {echo['workers']}",
        f"  cells (total)        {echo['cells_total']}",
        f"  cells (applicable)   {echo['cells_applicable']}",
        f"  cells (not applic.)  {echo['cells_not_applicable']}",
        f"  runs planned         {echo['runs_total']}",
        f"  estimated wall time  {echo['estimated_hours']} h "
        f"({echo['estimated_seconds']} s)",
        "",
        "  by tier:",
    ]
    for tier in sorted(echo["by_tier"]):
        bucket = echo["by_tier"][tier]
        label = {
            "1": "Table 1: all systems x all crash points, AUTHORITATIVE_READBACK, CALLER_REFERENCE",
            "2": "other response classes, CALLER_REFERENCE",
            "3": "ORACLE_FINGERPRINT sensitivity variant",
        }.get(tier, "")
        lines.append(
            f"    tier {tier}: {bucket['runs']:>4} runs, "
            f"{bucket['estimated_seconds'] / 3600.0:>5.2f} h   {label}"
        )

    inapplicable = [cell for cell in plan.cells if not cell.applicable]
    if inapplicable:
        lines += ["", "  not applicable (recorded, never run):"]
        seen: set[tuple[str, str]] = set()
        for cell in inapplicable:
            key = (cell.system.value, cell.crash_point)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"    {cell.system.value:<22} {cell.crash_point:<34} {cell.reason}")
        lines.append(
            f"    ({len(inapplicable)} cells in total, over "
            f"{len(seen)} system/crash-point pairs)"
        )

    lines += ["", "  cell list:", ""]
    lines.append(
        f"    {'tier':<5} {'system':<22} {'crash point':<34} "
        f"{'endpoint':<16} {'keying':<20} runs"
    )
    counts: dict[str, int] = {}
    for entry in plan.runs:
        counts[entry["cell_key"]] = counts.get(entry["cell_key"], 0) + 1
    for cell in sorted(plan.cells, key=lambda item: (item.tier, item.key)):
        if not cell.applicable:
            continue
        planned = counts.get(cell.key, 0)
        if planned == 0:
            continue
        lines.append(
            f"    {cell.tier:<5} {cell.system.value:<22} {cell.crash_point:<34} "
            f"{cell.endpoint:<16} {cell.readback_keying.value:<20} {planned}"
        )
    lines.append("")
    lines.append("=" * 78)
    return "\n".join(lines)


# ===========================================================================
# Execution
# ===========================================================================


def run_directory(results_root: str, entry: dict[str, Any]) -> Path:
    return Path(results_root) / entry["run_id"]


def already_collected(results_root: str, entry: dict[str, Any]) -> bool:
    """A run counts as collected when its own summary exists and parses.

    Deliberately not "the directory exists": a run killed halfway leaves a
    directory full of shards and no summary, and resuming must re-run it
    rather than treat a partial collection as a result.
    """
    summary = run_directory(results_root, entry) / "summary.json"
    if not summary.is_file():
        return False
    try:
        json.loads(summary.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return False
    return True


async def execute_plan(plan: MatrixPlan, arguments) -> int:
    results_root = plan.results_root
    Path(results_root).mkdir(parents=True, exist_ok=True)
    progress_path = Path(results_root) / "matrix-progress.jsonl"

    total = len(plan.runs)
    collected = 0
    skipped = 0
    failed: list[dict[str, Any]] = []
    started_at = time.monotonic()

    for index, entry in enumerate(plan.runs, start=1):
        if arguments.resume and already_collected(results_root, entry):
            skipped += 1
            continue
        if arguments.max_runs and collected >= arguments.max_runs:
            print(
                f"stopping after {collected} runs as instructed (--max-runs); "
                f"{total - index + 1} of {total} planned runs remain"
            )
            break

        label = (
            f"[{index}/{total}] tier {entry['tier']} {entry['system']} "
            f"{entry['crash_point']} {entry['endpoint']} "
            f"{entry['readback_keying']} rep{entry['repetition']}"
        )
        print(label, flush=True)
        started = time.monotonic()
        record: dict[str, Any] = {**entry, "started_at": started}
        try:
            outcome = await run_once(
                run_config_overrides={
                    "run_id": entry["run_id"],
                    "seed": entry["seed"],
                    "system": entry["system"],
                    "workers": plan.workers,
                    "executions_per_worker": max(
                        1, plan.executions_per_run // plan.workers
                    ),
                    "endpoint": entry["endpoint"],
                    "readback_keying": entry["readback_keying"],
                    "redis_url": plan.redis_url,
                    "results_root": results_root,
                    "crash_point": entry["crash_point"],
                    "crash_probability": arguments.crash_probability,
                    "crash_delay_ms": arguments.crash_delay_ms,
                    "max_dispatch_attempts": arguments.max_dispatch_attempts,
                    "poisoned_executions": arguments.poisoned_executions,
                    "recovery_deadline_seconds": arguments.recovery_deadline_seconds,
                },
                template_path=plan.template,
                port=arguments.port,
                fault_overrides=FAULTS,
                provider_seed=entry["seed"],
            )
            report = outcome["report"]
            record.update(
                {
                    "status": "collected",
                    "agrees": report.agrees,
                    "settled": outcome["settled"],
                    "undetected_duplicate_applications": (
                        report.undetected_duplicate_applications
                    ),
                    "declared_ambiguous_executions": (
                        report.declared_ambiguous_executions
                    ),
                    "lost_effect_executions": report.lost_effect_executions,
                    "summary": outcome["summary"],
                }
            )
            collected += 1
            if not report.agrees:
                failed.append(record)
            # D4: an undetected duplicate in AEP-full halts the matrix. It is
            # the session's primary result if it happens, and continuing would
            # only bury it under six hours of further runs.
            if (
                entry["system"] == SystemId.AEP_FULL.value
                and report.undetected_duplicate_applications > 0
                and not arguments.no_halt_on_undetected
            ):
                record["halted_matrix"] = True
                _append(progress_path, record)
                print("")
                print("!" * 78)
                print(
                    "HALTED: AEP-full recorded "
                    f"{report.undetected_duplicate_applications} undetected "
                    f"duplicate application(s) in {entry['run_id']}."
                )
                print(
                    "Amendment D4: this is a finding, not an embarrassment. The "
                    "matrix stops here so the reproduction can be minimised. Do "
                    "not re-run or filter to make the number zero."
                )
                print(f"  events:  {outcome['events']}")
                print(f"  summary: {outcome['summary']}")
                print("!" * 78)
                return 3
        except Exception as error:  # noqa: BLE001 -- one bad run must not end the matrix
            record.update(
                {
                    "status": "failed",
                    "error": f"{type(error).__name__}: {error}",
                    "traceback": traceback.format_exc()[-4000:],
                }
            )
            failed.append(record)
            print(f"  FAILED: {type(error).__name__}: {error}", flush=True)
        finally:
            record["wall_seconds"] = round(time.monotonic() - started, 2)
            _append(progress_path, record)

    elapsed = time.monotonic() - started_at
    print("")
    print("=" * 78)
    print(f"collected {collected} run(s), skipped {skipped} already-collected")
    print(f"wall time {elapsed / 3600.0:.2f} h")
    if failed:
        print(f"{len(failed)} run(s) did not agree or did not complete:")
        for record in failed[:20]:
            print(f"  {record['run_id']}: {record.get('error') or 'agrees=False'}")
    print(f"progress: {progress_path}")
    print(
        "resume with: python -m experiments.run_matrix --resume "
        f"--results-root {results_root}"
    )
    print("=" * 78)
    return 1 if failed else 0


def _append(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        handle.flush()


#: The fault surface every matrix run shares. Not a matrix dimension: the
#: dimensions are the four the amendment names, and a fifth would multiply the
#: cost without answering any of the four research questions. These values are
#: chosen so that the ambiguous outcomes the protocol exists for actually
#: occur -- a timeout that applies the effect and never answers is the exact
#: situation a naive retry turns into a duplicate.
FAULTS = {
    "timeout_probability": 0.15,
    "server_error_probability": 0.05,
    # Left at zero on purpose. Every duplicate the ledger reports is then
    # caller-caused, which keeps the attribution in reconcile.py exact and
    # keeps the at-most-once prediction checkable for AEP-full and B3.
    "duplicate_response_probability": 0.0,
    "delay": {"distribution": "constant", "seconds": 2.0},
}


def _systems(values: Iterable[str] | None) -> tuple[SystemId, ...] | None:
    if not values:
        return None
    return tuple(SystemId(value) for value in values)


def _keyings(values: Iterable[str] | None) -> tuple[ReadbackKeying, ...] | None:
    if not values:
        return None
    return tuple(ReadbackKeying(value) for value in values)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AEP evaluation matrix.")
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6381/15")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--results-root", default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--matrix-seed", type=int, default=20260806)
    parser.add_argument("--runs-per-cell", type=int, default=3)
    parser.add_argument("--executions-per-run", type=int, default=10)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--crash-probability", type=float, default=1.0)
    parser.add_argument("--crash-delay-ms", type=int, default=400)
    parser.add_argument("--max-dispatch-attempts", type=int, default=3)
    parser.add_argument("--poisoned-executions", type=int, default=0)
    parser.add_argument("--recovery-deadline-seconds", type=float, default=120.0)
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument(
        "--max-tier",
        type=int,
        default=3,
        help="run only tiers up to this number (1 = the paper's Table 1)",
    )
    parser.add_argument("--system", dest="systems", action="append")
    parser.add_argument("--crash-point", dest="crash_points", action="append")
    parser.add_argument("--keying", dest="keyings", action="append")
    parser.add_argument("--max-runs", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument(
        "--no-halt-on-undetected",
        action="store_true",
        help=(
            "do not stop when AEP-full records an undetected duplicate. "
            "Amendment D4 says to halt and minimise the reproduction; this "
            "exists only so the minimisation itself can be scripted."
        ),
    )
    arguments = parser.parse_args(argv)
    arguments.systems = _systems(arguments.systems)
    arguments.keyings = _keyings(arguments.keyings)
    arguments.crash_points = tuple(arguments.crash_points or ()) or None

    plan = build_plan(arguments)
    rendered = render_plan(plan)
    print(rendered)

    root = Path(arguments.results_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "matrix-plan.json").write_text(
        json.dumps(plan.echo(), indent=2, sort_keys=True), encoding="utf-8"
    )
    (root / "matrix-plan.txt").write_text(rendered + "\n", encoding="utf-8")
    print(f"plan written to {root / 'matrix-plan.json'} and matrix-plan.txt")

    if arguments.plan_only:
        return 0
    if not HAS_SIGKILL:
        print(
            "REFUSED: amendment D2 requires every run in EVALUATION mode on "
            "Linux. This platform has no SIGKILL, so its crashes would be "
            "TerminateProcess (Session 2 report F4)."
        )
        return 2
    return asyncio.run(execute_plan(plan, arguments))


if __name__ == "__main__":  # pragma: no cover - process entry point
    sys.exit(main())
