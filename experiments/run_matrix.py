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
import os
import platform
import sys
import time
import traceback
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from experiments.baselines.contract import ResumePolicy, SystemId, descriptor_for
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

#: Amendment E5. Set to ``1`` by the operator on a host whose sleep, standby
#: and hibernation have been disabled, on mains power. Recorded into every run
#: config and therefore into every run log; ``analyze.py`` refuses to put a run
#: without it into any absolute-timing aggregate. It is not detected because it
#: cannot be: a host that simply was not idle long enough to suspend is
#: indistinguishable from one that cannot.
SUSPEND_DISABLED_VARIABLE = "AEP_HARNESS_SUSPEND_DISABLED"

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
    SystemId.B4B_DURABLE_WORKFLOW_AT_MOST_ONCE,
)

#: The two systems amendment E1's ablation is between. Running the Redis kill
#: against the other five would cost four hours to demonstrate that systems
#: with no durability barrier are unaffected by one.
ABLATION_SYSTEMS: tuple[SystemId, ...] = (
    SystemId.AEP_FULL,
    SystemId.B3_INTENT_NO_BARRIER,
)


@dataclass(frozen=True)
class Regime:
    """The fault condition a cell is collected under.

    Session 3's matrix had exactly one of these and never named it: every cell
    was ``crash_probability = 1.0`` with no infrastructure fault. Amendments E1
    and E2 add three more conditions, and a condition is not a *dimension* --
    the cells of different regimes are not a cross product, they are different
    experiments that happen to share a harness.

    **The unnamed regime is Session 3's, and that is load-bearing.** ``name``
    is the empty string for it, and :meth:`Cell.key` appends nothing when the
    name is empty, so every cell collected in Session 3 keeps the identity --
    and therefore the results directory -- it was collected under. Eighty-three
    runs are not re-run to accommodate a new field. Any *other* regime
    contributes its name to the key and cannot collide with them.
    """

    name: str
    label: str
    #: Probability that any one execution is selected for the worker crash.
    crash_probability: float
    #: Whether cells in this regime iterate the six crash points. A regime with
    #: no worker crash has one cell per system, not six identical ones.
    iterates_crash_points: bool = True
    #: Amendment E1: where a worker hard-kills Redis, and how long after.
    redis_kill_point: str | None = None
    redis_kill_delay_ms: int = 0
    redis_kill_executions: int = 0
    #: Per-regime shape overrides. The Redis-kill regimes use one execution per
    #: run so that the unit of the fault and the unit of the metric are the
    #: same thing: a second execution would run against a Redis the first one
    #: had just killed, and its outcome would be about the restart.
    runs_per_cell: int | None = None
    executions_per_run: int | None = None
    workers: int | None = None
    #: Restrict the regime to particular systems, or ``None`` for all of them.
    systems: tuple[SystemId, ...] | None = None
    #: And to particular endpoints, keyings and crash points. A regime is an
    #: experiment with a question, and a dimension that cannot change its
    #: answer is not worth an hour of wall time. Every restriction here is
    #: printed in the plan, so what was *not* collected is as visible as what
    #: was -- which is the only honest way to bound a matrix.
    endpoints: tuple[str, ...] | None = None
    keyings: tuple[ReadbackKeying, ...] | None = None
    crash_points: tuple[str, ...] | None = None

    def echo(self) -> dict[str, Any]:
        return {
            "name": self.name or "(session-3 baseline)",
            "label": self.label,
            "crash_probability": self.crash_probability,
            "iterates_crash_points": self.iterates_crash_points,
            "redis_kill_point": self.redis_kill_point,
            "redis_kill_delay_ms": self.redis_kill_delay_ms,
            "redis_kill_executions": self.redis_kill_executions,
            "runs_per_cell": self.runs_per_cell,
            "executions_per_run": self.executions_per_run,
            "workers": self.workers,
            "systems": (
                [system.value for system in self.systems] if self.systems else None
            ),
            "endpoints": list(self.endpoints) if self.endpoints else None,
            "keyings": (
                [keying.value for keying in self.keyings] if self.keyings else None
            ),
            "crash_points": list(self.crash_points) if self.crash_points else None,
        }


#: Every crash point crashed, no infrastructure fault. Session 3's condition,
#: and the one the paper's Table 1 is built from.
REGIME_CRASH_ALWAYS = Regime(
    name="",
    label="every execution crashed, no infrastructure fault",
    crash_probability=1.0,
)

#: Amendment E2. At ``crash_probability = 1.0`` neither AEP-full nor B3
#: completes an execution, so neither emits a single ``execution_resolved``
#: record and RQ3 has no step-latency sample at all. These are the cells that
#: give it one, and the analysis computes overhead from them *only*.
REGIME_NO_CRASH = Regime(
    name="p0",
    label="no crash (RQ3 overhead: the only cells overhead is computed from)",
    crash_probability=0.0,
    iterates_crash_points=False,
    # Overhead is a property of the protocol's own work, and the read-back
    # keying only matters to a *reconciliation*, which a crash-free execution
    # never performs. Collecting the sensitivity variant here would double the
    # cost to reproduce the same number.
    keyings=(ReadbackKeying.CALLER_REFERENCE,),
)

REGIME_CRASH_SOMETIMES = Regime(
    name="p30",
    label="30% of executions crashed (RQ3 mid-point)",
    crash_probability=0.3,
    # One crash point, not six. This regime exists to put a second point on
    # the overhead curve between 0% and 100% crashed; which instruction the
    # crash lands on does not change what the crash-free executions in the
    # same run cost. ``mid_dispatch`` is the representative because it is the
    # one that leaves the provider's state genuinely unknown.
    crash_points=("mid_dispatch",),
    keyings=(ReadbackKeying.CALLER_REFERENCE,),
)

#: Amendment E1, the load-bearing variant. Redis is hard-killed in the window
#: between the intent CAS and the barrier's acknowledgement -- the exact moment
#: AEP-full waits and B3 does not. AEP-full's WAITAOF fails and its
#: DurabilityAck is never minted, so it refuses to dispatch; B3 has already
#: dispatched. No worker crash: the fault under study is Redis dying.
REGIME_REDIS_KILL_PREACK = Regime(
    name="redis-kill-preack",
    label="hard Redis kill between the intent CAS and the barrier ack (E1)",
    crash_probability=0.0,
    iterates_crash_points=False,
    redis_kill_point="after_intent_before_barrier",
    redis_kill_delay_ms=0,
    redis_kill_executions=1,
    runs_per_cell=30,
    executions_per_run=1,
    workers=1,
    systems=ABLATION_SYSTEMS,
    # Two endpoints, chosen because they are where the same mechanism has two
    # different consequences. Under AUTHORITATIVE_READBACK a read-back can
    # rescue a system that dispatched without an acknowledged intent, so the
    # difference shows only in what was applied. Under NO_READBACK nothing can,
    # so it shows in what the system is left able to say. Collecting the middle
    # endpoint as well would cost 60 runs to interpolate between them.
    endpoints=("payments", "ledger_postings"),
    keyings=(ReadbackKeying.CALLER_REFERENCE,),
)

#: Amendment E1's second variant. Armed at the last instruction before
#: transmission and delivered 200 ms later, so the kill lands while the request
#: is in flight -- inside the appendfsync-everysec window measured from B3's
#: intent write, and outside it for AEP-full, whose barrier moved the window's
#: start. This is the variant that would show a lost record if a process kill
#: could lose one; see experiments/harness/redis_kill.py for why it cannot.
REGIME_REDIS_KILL_INFLIGHT = Regime(
    name="redis-kill-inflight",
    label="hard Redis kill 200 ms after transmission, in flight (E1)",
    crash_probability=0.0,
    iterates_crash_points=False,
    redis_kill_point="mid_dispatch",
    redis_kill_delay_ms=200,
    redis_kill_executions=1,
    runs_per_cell=30,
    executions_per_run=1,
    workers=1,
    systems=ABLATION_SYSTEMS,
    # Two endpoints, chosen because they are where the same mechanism has two
    # different consequences. Under AUTHORITATIVE_READBACK a read-back can
    # rescue a system that dispatched without an acknowledged intent, so the
    # difference shows only in what was applied. Under NO_READBACK nothing can,
    # so it shows in what the system is left able to say. Collecting the middle
    # endpoint as well would cost 60 runs to interpolate between them.
    endpoints=("payments", "ledger_postings"),
    keyings=(ReadbackKeying.CALLER_REFERENCE,),
)

REGIMES: tuple[Regime, ...] = (
    REGIME_CRASH_ALWAYS,
    REGIME_NO_CRASH,
    REGIME_CRASH_SOMETIMES,
    REGIME_REDIS_KILL_PREACK,
    REGIME_REDIS_KILL_INFLIGHT,
)

#: Wall-time model, in seconds. **Re-fitted for this session against the 83
#: runs Session 3 actually collected**, whose median wall times were AEP-full
#: 40.0 s, B0 41.1 s, B1 147.3 s, B2 147.2 s, B3 35.4 s and B4 176.3 s. The
#: previous model predicted 35.5 s for all of them and was wrong by a factor of
#: four on half the table, which is why Session 3's "5.86 h" estimate described
#: a matrix that would have taken far longer. A plan that estimates its own
#: cost has to say where the estimate came from and be corrected when the
#: measurements arrive.
PROVIDER_START_SECONDS = 2.5
PER_EXECUTION_SECONDS = 3.2
#: What a crashed execution costs a system that waits for a dead worker's lease
#: to expire. This is ``lock_ttl_seconds`` (25) plus a poll margin, and it is
#: most of B1, B2 and B4's wall time. Charged only to systems that both take a
#: lease and re-execute a crashed execution.
LEASE_WAIT_SECONDS = 26.0
#: What a crashed execution costs a system that re-sends on an ambiguous
#: answer: another provider round trip, sometimes several.
RETRY_SECONDS = 4.0
#: Systems with a recovery service wait for crashed executions to be
#: classified; lease TTL plus the reconciliation delay dominates it.
SETTLE_SECONDS_WITH_RECOVERY = 25.0
SETTLE_SECONDS_WITHOUT_RECOVERY = 1.0
#: One hard kill plus the explicit restart and the readiness wait. Measured:
#: kill 0.8-1.1 s, start 0.9 s, ready ~2 s.
REDIS_KILL_SECONDS = 5.0


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
    regime: Regime = REGIME_CRASH_ALWAYS

    @property
    def key(self) -> str:
        """The cell's identity, and therefore its results directory.

        The regime is appended only when it has a name, which is what keeps
        every Session 3 cell identified by exactly the string it was collected
        under. This is a deliberate compatibility seam, stated here rather than
        discovered later: it is asserted by ``test_cell_identity.py``, so a
        future edit that silently re-keys 83 collected runs fails a test
        instead of quietly re-running them.
        """
        parts = [
            self.system.value,
            self.crash_point,
            self.endpoint,
            self.readback_keying.value,
        ]
        if self.regime.name:
            parts.append(self.regime.name)
        return "|".join(parts)

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
            "regime": self.regime.echo(),
        }


#: What each tier is for, in the order amendment E6 sets. The order is not
#: loop nesting: it is "which unanswered question is worth the next hour".
TIER_LABELS: Mapping[int, str] = MappingProxyType(
    {
        1: (
            "E3: POSITIVE_ONLY_READBACK and NO_READBACK -- where the "
            "known-ambiguity claim lives, and had no evidence at all"
        ),
        2: "E1: the hard-Redis-kill ablation, AEP-full versus B3",
        3: "E2: crash-free and 30% cells -- the only cells RQ3 can use",
        4: "Table 1 completion: AUTHORITATIVE_READBACK, CALLER_REFERENCE",
        5: "ORACLE_FINGERPRINT sensitivity variant",
    }
)


def _tier(regime: Regime, endpoint: str, keying: ReadbackKeying) -> int:
    """Which pass a cell belongs to. Lower runs first.

    Amendment E6 fixes this order and it is a statement about evidence, not
    about convenience. Tier 1 is E3, because the paper's central claim -- that
    silent failure becomes measured, bounded known-ambiguity -- had *zero*
    evidence after Session 3, and the endpoints where it can appear had never
    been run. Tier 2 is E1, the ablation that could not previously show the
    barrier's benefit. Tier 3 is E2, without which RQ3 has no numbers. Tier 4
    is what Session 3 collected and is therefore mostly already done; tier 5 is
    the sensitivity variant, which ``docs/24-readback-keying.md`` argues is
    more generous than a real legacy endpoint and is a robustness check rather
    than a headline.
    """
    if regime.redis_kill_point is not None:
        return 2
    if regime.name in {"p0", "p30"}:
        return 3
    if keying is ReadbackKeying.ORACLE_FINGERPRINT:
        return 5
    return 4 if endpoint == "payments" else 1


def build_cells(
    *,
    systems: Sequence[SystemId] = SYSTEM_ORDER,
    crash_points: Sequence[str] = tuple(ROADMAP_CRASH_POINTS),
    endpoints: Sequence[tuple[str, str]] = ENDPOINTS,
    keyings: Sequence[ReadbackKeying] = tuple(ReadbackKeying),
    regimes: Sequence[Regime] = REGIMES,
) -> tuple[Cell, ...]:
    """Every cell of every regime, including the ones that cannot be run."""
    cells: list[Cell] = []
    for regime in regimes:
        regime_systems = [
            system
            for system in systems
            if regime.systems is None or system in regime.systems
        ]
        # A regime with no worker crash has one cell per system, not six
        # identical ones under six crash-point labels. "none" is what the run
        # config records and what the analysis groups on.
        regime_crash_points = (
            tuple(regime.crash_points or crash_points)
            if regime.iterates_crash_points
            else ("none",)
        )
        regime_endpoints = [
            entry
            for entry in endpoints
            if regime.endpoints is None or entry[0] in regime.endpoints
        ]
        regime_keyings = [
            keying
            for keying in keyings
            if regime.keyings is None or keying in regime.keyings
        ]
        for system in regime_systems:
            for crash_point in regime_crash_points:
                applicable, reason = True, None
                if crash_point != "none":
                    try:
                        resolve_for_system(system, crash_point)
                    except CrashPointNotApplicable:
                        applicable = False
                        reason = NOT_APPLICABLE_REASONS.get(
                            crash_point, "this system has no such moment"
                        )
                if applicable and regime.redis_kill_point is not None:
                    # The kill is aimed at an instruction boundary too, and a
                    # system without that boundary cannot host the experiment.
                    try:
                        resolve_for_system(system, regime.redis_kill_point)
                    except CrashPointNotApplicable:
                        applicable = False
                        reason = NOT_APPLICABLE_REASONS.get(
                            regime.redis_kill_point,
                            "this system has no such moment for the Redis kill",
                        )
                for endpoint, response_class in regime_endpoints:
                    for keying in regime_keyings:
                        cells.append(
                            Cell(
                                system=system,
                                crash_point=crash_point,
                                endpoint=endpoint,
                                response_class=response_class,
                                readback_keying=keying,
                                tier=_tier(regime, endpoint, keying),
                                applicable=applicable,
                                reason=reason,
                                regime=regime,
                            )
                        )
    return tuple(cells)


def estimated_run_seconds(cell: Cell, executions_per_run: int, workers: int) -> float:
    """A crude, stated, checkable model of one run's wall time.

    Fitted against Session 3's measured medians (see the constants above). The
    two terms that dominate are both consequences of a *crashed* execution, so
    both are scaled by the regime's crash probability -- which is why the
    crash-free cells of amendment E2 are cheap and the tier-4 cells are not.
    """
    descriptor = descriptor_for(cell.system)
    per_worker = max(1, executions_per_run // max(1, workers))
    settle = (
        SETTLE_SECONDS_WITH_RECOVERY
        if descriptor.has_recovery_service
        else SETTLE_SECONDS_WITHOUT_RECOVERY
    )
    crash_probability = cell.regime.crash_probability
    per_execution = PER_EXECUTION_SECONDS
    if descriptor.resume_policy is ResumePolicy.REEXECUTE_CRASHED:
        if descriptor.uses_lease:
            per_execution += LEASE_WAIT_SECONDS * crash_probability
        if descriptor.retries_on_ambiguity:
            per_execution += RETRY_SECONDS * crash_probability
    total = PROVIDER_START_SECONDS + per_worker * per_execution + settle
    if cell.regime.redis_kill_point is not None:
        total += REDIS_KILL_SECONDS
    return total


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
            "suspend_disabled_declared": suspend_disabled_declared(),
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


def _regimes(values: Iterable[str] | None) -> tuple[Regime, ...]:
    """Select regimes by name; ``session-3`` names the unnamed one."""
    if not values:
        return REGIMES
    wanted = {"" if value == "session-3" else value for value in values}
    unknown = wanted - {regime.name for regime in REGIMES}
    if unknown:
        raise SystemExit(
            f"unknown regime(s) {sorted(unknown)}; known: "
            f"{sorted(regime.name or 'session-3' for regime in REGIMES)}"
        )
    return tuple(regime for regime in REGIMES if regime.name in wanted)


def build_plan(arguments) -> MatrixPlan:
    regimes = _regimes(arguments.regimes)
    if arguments.crash_probability is not None:
        # An explicit override applies to every selected regime and is recorded
        # in the plan, so a run collected under it can never be mistaken for
        # one collected under the regime's own probability.
        regimes = tuple(
            replace(
                regime,
                crash_probability=arguments.crash_probability,
                name=f"{regime.name or 'session-3'}-p"
                f"{int(round(arguments.crash_probability * 100))}",
            )
            for regime in regimes
        )
    endpoints = (
        tuple(
            entry for entry in ENDPOINTS if entry[0] in set(arguments.endpoints)
        )
        if arguments.endpoints
        else ENDPOINTS
    )
    if arguments.endpoints and not endpoints:
        raise SystemExit(
            f"unknown endpoint(s) {sorted(set(arguments.endpoints))}; known: "
            f"{[name for name, _ in ENDPOINTS]}"
        )
    cells = build_cells(
        systems=arguments.systems or SYSTEM_ORDER,
        crash_points=arguments.crash_points or tuple(ROADMAP_CRASH_POINTS),
        endpoints=endpoints,
        keyings=arguments.keyings or tuple(ReadbackKeying),
        regimes=regimes,
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
        # A regime may override the shape of its runs. The Redis-kill regimes
        # do: one execution per run, so that the unit of the fault and the unit
        # of the metric are the same execution.
        runs_per_cell = cell.regime.runs_per_cell or arguments.runs_per_cell
        executions_per_run = (
            cell.regime.executions_per_run or arguments.executions_per_run
        )
        workers = cell.regime.workers or arguments.workers
        for repetition in range(runs_per_cell):
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
                    "regime": cell.regime.name or "",
                    "crash_probability": cell.regime.crash_probability,
                    "redis_kill_point": cell.regime.redis_kill_point,
                    "redis_kill_delay_ms": cell.regime.redis_kill_delay_ms,
                    "redis_kill_executions": cell.regime.redis_kill_executions,
                    "executions_per_run": executions_per_run,
                    "workers": workers,
                    "repetition": repetition,
                    "seed": cell_seed(arguments.matrix_seed, cell, repetition),
                    "estimated_seconds": round(
                        estimated_run_seconds(cell, executions_per_run, workers),
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
        f"  suspend disabled     {echo['suspend_disabled_declared']}   "
        f"(E5: absolute timing is excluded from every run without this)",
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
    for tier in sorted(echo["by_tier"], key=int):
        bucket = echo["by_tier"][tier]
        label = TIER_LABELS.get(int(tier), "")
        lines.append(
            f"    tier {tier}: {bucket['runs']:>4} runs, "
            f"{bucket['estimated_seconds'] / 3600.0:>5.2f} h   {label}"
        )

    lines += ["", "  regimes (a regime is a condition, not a dimension):"]
    for regime in REGIMES:
        planned = sum(
            1 for entry in plan.runs if entry["regime"] == regime.name
        )
        if not planned:
            continue
        shape = (
            f"{regime.runs_per_cell or plan.runs_per_cell} x "
            f"{regime.executions_per_run or plan.executions_per_run}"
        )
        kill = (
            f", redis kill @ {regime.redis_kill_point} +{regime.redis_kill_delay_ms}ms"
            if regime.redis_kill_point
            else ""
        )
        lines.append(
            f"    {(regime.name or '(session-3)'):<22} p(crash)="
            f"{regime.crash_probability:<4} runs={planned:<4} shape={shape}{kill}"
        )
        lines.append(f"      {regime.label}")

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
        f"    {'tier':<5} {'regime':<20} {'system':<36} {'crash point':<34} "
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
            f"    {cell.tier:<5} {(cell.regime.name or '(session-3)'):<20} "
            f"{cell.system.value:<36} {cell.crash_point:<34} "
            f"{cell.endpoint:<16} {cell.readback_keying.value:<20} {planned}"
        )
    lines.append("")
    lines.append("=" * 78)
    return "\n".join(lines)


# ===========================================================================
# Execution
# ===========================================================================


def suspend_disabled_declared() -> bool:
    """Whether the operator declared this host cannot suspend (amendment E5)."""
    return os.environ.get(SUSPEND_DISABLED_VARIABLE, "").strip() in {
        "1",
        "true",
        "TRUE",
        "yes",
    }


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
            workers = int(entry.get("workers") or plan.workers)
            executions_per_run = int(
                entry.get("executions_per_run") or plan.executions_per_run
            )
            outcome = await run_once(
                run_config_overrides={
                    "run_id": entry["run_id"],
                    "seed": entry["seed"],
                    "system": entry["system"],
                    "workers": workers,
                    "executions_per_worker": max(
                        1, executions_per_run // workers
                    ),
                    "endpoint": entry["endpoint"],
                    "readback_keying": entry["readback_keying"],
                    "redis_url": plan.redis_url,
                    "results_root": results_root,
                    # "none" is the plan's word for a regime that schedules no
                    # worker crash; the run config's word is None.
                    "crash_point": (
                        None
                        if entry["crash_point"] == "none"
                        else entry["crash_point"]
                    ),
                    "crash_probability": entry["crash_probability"],
                    "crash_delay_ms": arguments.crash_delay_ms,
                    "redis_kill_point": entry["redis_kill_point"],
                    "redis_kill_delay_ms": entry["redis_kill_delay_ms"],
                    "redis_kill_executions": entry["redis_kill_executions"],
                    "max_dispatch_attempts": arguments.max_dispatch_attempts,
                    "poisoned_executions": arguments.poisoned_executions,
                    "recovery_deadline_seconds": arguments.recovery_deadline_seconds,
                    "suspend_disabled_declared": suspend_disabled_declared(),
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
    parser.add_argument(
        "--crash-probability",
        type=float,
        default=None,
        help=(
            "override every selected regime's crash probability. The regimes "
            "carry their own; this exists for debugging and renames the regime "
            "so an overridden run cannot be pooled with a normal one."
        ),
    )
    parser.add_argument(
        "--regime",
        dest="regimes",
        action="append",
        help=(
            "collect only these regimes: session-3, p0, p30, "
            "redis-kill-preack, redis-kill-inflight"
        ),
    )
    parser.add_argument("--crash-delay-ms", type=int, default=400)
    parser.add_argument("--max-dispatch-attempts", type=int, default=3)
    parser.add_argument("--poisoned-executions", type=int, default=0)
    parser.add_argument("--recovery-deadline-seconds", type=float, default=120.0)
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument(
        "--max-tier",
        type=int,
        default=5,
        help=(
            "run only tiers up to this number. Amendment E6's order: "
            "1 = E3 known-ambiguity endpoints, 2 = E1 Redis-kill ablation, "
            "3 = E2 overhead cells, 4 = Table 1 completion, "
            "5 = ORACLE_FINGERPRINT sensitivity"
        ),
    )
    parser.add_argument("--system", dest="systems", action="append")
    parser.add_argument(
        "--endpoint",
        dest="endpoints",
        action="append",
        help="collect only these endpoints (payments, notifications, ledger_postings)",
    )
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
