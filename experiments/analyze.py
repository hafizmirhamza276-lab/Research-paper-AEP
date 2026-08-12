"""Every metric in PAPER_ROADMAP.md section 3.2, from two files per run.

Amendment D3: *"experiments/analyze.py computes all section 3.2 metrics with
bootstrap 95% CIs and Fisher's exact tests, and emits: (i) CSV per metric,
(ii) the paper's Table 1 (undetected duplicate rate + known-ambiguity rate per
system), (iii) PDF figures. The analysis must read ONLY events.jsonl + the
oracle ledger -- never internal AEP state directly."*

**The reading restriction is the point, not a formality.** This module opens
exactly two things per run: the run's ``events.jsonl`` and the run's
``ground_truth.sqlite3``. It never connects to Redis, never imports a storage
adapter, and never asks the system under test what it thinks happened -- it
reads what the system *recorded* that it thought happened, at the time, into a
log that was flushed on every write and survived the SIGKILLs. There is a gate
in ``experiments/tests/test_analysis_isolation.py`` that fails if an import of
``redis`` or of ``aep_core``'s storage ever appears here, because the
difference between "asked the oracle" and "asked the system under test" is the
whole reason any of these numbers mean anything.

**What is counted, and against what.**

``undetected_duplicate_rate``
    The headline. An execution whose resource was mutated more than once in
    the ground-truth ledger, and whose system did *not* end it in a declared
    ambiguity. Both halves matter: the numerator comes from the oracle, the
    "not flagged" comes from the system's own final record, and neither can
    see the other. AEP's target is zero.

``known_ambiguity_rate``
    Executions ending in a declared ambiguity. This is what AEP converts
    silent failures *into*, so it is expected to be positive and is not a
    defect -- reporting it beside the duplicate rate is what makes the trade
    visible rather than hidden.

``lost_effect_rate``
    The world changed and the system neither says so nor flags it. The failure
    mode that is invisible from inside a naive system.

``unverified_failure_rate``
    The system wrote "failed" with no evidence that nothing was applied. Sums
    with the ambiguity rate to "the call did not visibly succeed", and the
    split between them is the contribution.

``state_corruption_rate``
    Executions whose own record could not be read.

``recovery_success_rate`` / ``recovery_latency``
    Of the executions that crashed, the fraction that reached a terminal
    classification, and how long crash-to-classified took.

    **Reported only for runs in which a recovery service was actually
    running**, which the log says directly (``recovery_spawned`` versus
    ``recovery_not_started``). In a run without one, a crashed execution
    reaches a terminal classification because the supervisor ran the step
    again; calling that "recovery success" would credit a baseline with a
    capability it does not have, and would score it *well* on a metric whose
    whole subject is the thing it cannot do. Those rows carry
    ``recovery_service = 0`` and are excluded from the recovery aggregates;
    the same executions are still counted, under their real name, by the
    duplicate and lost-effect rates.

``step_latency`` / ``throughput``
    End-to-end wall time per resolved execution, and executions per second of
    run wall time. The overhead columns.

Rates carry a percentile bootstrap 95% interval, clustered by run, and every
baseline is compared against AEP-full with a two-tailed Fisher exact test. Both
procedures are in ``experiments/statistics.py`` with their seeds.

    python -m experiments.analyze --results-root experiments/results/matrix
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from experiments.statistics import (
    DEFAULT_BOOTSTRAP_SEED,
    DEFAULT_RESAMPLES,
    cluster_bootstrap_median_difference,
    cluster_bootstrap_proportion,
    compare_rates,
    proportion,
    stratified_cluster_bootstrap_difference,
    summarise,
    wilson_interval,
)

#: The system every other one is compared against.
REFERENCE_SYSTEM = "AEP_FULL"

#: Outcome classes, repeated here rather than imported, so that this module
#: depends on the *log format* and not on the code that produced it. A rename
#: in the harness that did not reach the log would then be caught by the
#: unknown-class guard below instead of silently agreeing with itself.
CONFIRMED_APPLIED = "CONFIRMED_APPLIED"
CONFIRMED_NOT_APPLIED = "CONFIRMED_NOT_APPLIED"
DECLARED_AMBIGUOUS = "DECLARED_AMBIGUOUS"
UNVERIFIED_FAILURE = "UNVERIFIED_FAILURE"
NO_RECORD = "NO_RECORD"
UNREADABLE = "UNREADABLE"

KNOWN_CLASSES = frozenset(
    {
        CONFIRMED_APPLIED,
        CONFIRMED_NOT_APPLIED,
        DECLARED_AMBIGUOUS,
        UNVERIFIED_FAILURE,
        NO_RECORD,
        UNREADABLE,
    }
)

#: How much wall-versus-monotonic divergence a run may show before its
#: *timing* is discarded. Found the hard way: a matrix run recorded 40 s of
#: ``time.monotonic()`` and a 792 s span of ``time.time()``, with a 774-second
#: gap between two settling polls two seconds apart -- the host had suspended
#: the VM. Counts are unaffected by that (an execution either duplicated or it
#: did not), so the rate metrics keep every run; the latency and throughput
#: aggregates keep only the runs whose clocks agree, and report how many they
#: dropped. Two seconds is generous for scheduling noise and far below any
#: real suspension.
TIMING_SUSPENSION_TOLERANCE_SECONDS = 2.0

#: The single regime the figures are drawn from.
#:
#: A regime is a named fault condition, not a matrix dimension: the crash-free
#: cells, the every-execution-crashed cells and the hard-Redis-kill cells are
#: three different experiments. A bar drawn across all three has a height set
#: by how many runs of each kind happened to be collected, which is exactly why
#: the pooled summary table is not quotable. Figures obey the same rule as
#: tables, so they name one regime and print it in the title.
#:
#: ``""`` is Session 3's unnamed regime -- every execution killed at the cell's
#: crash point -- which is the one the duplicate and ambiguity claims are about.
#: Derived artifacts give that condition the explicit label ``crashed``.
FIGURE_REGIME = "crashed"

#: Revision-stage operational sensitivity threshold for the B3/AEP declared-
#: ambiguity comparison. This was not preregistered. Five percentage points is
#: 27 additional terminal escalations in the 540-execution crashed arm, which
#: the paper treats as operationally material rather than negligible.
AMBIGUITY_EQUIVALENCE_MARGIN = 0.05
AMBIGUITY_DIFFERENCE_CONFIDENCE = 0.90

#: The rate metrics, in the order the paper's tables use them.
RATE_METRICS: tuple[str, ...] = (
    "undetected_duplicate_rate",
    "known_ambiguity_rate",
    "lost_effect_rate",
    "unverified_failure_rate",
    "state_corruption_rate",
    "recovery_success_rate",
)


class AnalysisError(RuntimeError):
    """The results cannot be interpreted, so nothing is reported from them."""


# ===========================================================================
# Reading. Two files, and nothing else.
# ===========================================================================


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse a run log, tolerating only a truncated final line.

    A worker killed mid-write leaves a partial last line; that is an artifact
    of the experiment. Any other unparseable line raises, because silently
    skipping one would lower a count the paper reports.
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    records: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError:
            if index == len(lines) - 1:
                break
            raise AnalysisError(f"{path} line {index + 1} is not valid JSON")
    return records


def events_of(records: Iterable[Mapping[str, Any]], event: str) -> list[dict[str, Any]]:
    return [dict(record) for record in records if record.get("event") == event]


def oracle_effects_by_target(ledger_path: Path) -> Counter[str]:
    """How many times each resource was actually mutated.

    Read straight out of the ground-truth SQLite with a read-only connection
    and one SQL statement. Deliberately not through ``GroundTruthLedger``: that
    class is part of the apparatus under test's environment, and the analysis
    should be able to run against a published artifact containing nothing but
    the database file.
    """
    if not ledger_path.is_file():
        raise AnalysisError(f"no ground-truth ledger at {ledger_path}")
    connection = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT target, COUNT(*) FROM applied_mutations GROUP BY target"
        ).fetchall()
    except sqlite3.DatabaseError as error:
        raise AnalysisError(f"cannot read {ledger_path}: {error}") from None
    finally:
        connection.close()
    return Counter({str(target): int(count) for target, count in rows})


# ===========================================================================
# One run
# ===========================================================================


@dataclass
class ExecutionRecord:
    """One agent execution, as the two oracles jointly describe it."""

    run_id: str
    system: str
    crash_point: str
    endpoint: str
    response_class: str
    readback_keying: str
    execution_id: str
    outcome_class: str
    status: str
    applied_effects: int
    crashed: bool
    dispatch_attempts: int
    resolved_wall_ms: int | None = None
    step_latency_ms: float | None = None
    crash_wall_ms: int | None = None
    classified_wall_ms: int | None = None

    @property
    def recovery_latency_ms(self) -> float | None:
        if self.crash_wall_ms is None or self.classified_wall_ms is None:
            return None
        return float(self.classified_wall_ms - self.crash_wall_ms)

    @property
    def is_undetected_duplicate(self) -> bool:
        return self.applied_effects > 1 and self.outcome_class != DECLARED_AMBIGUOUS

    @property
    def is_lost_effect(self) -> bool:
        return (
            self.applied_effects > 0
            and self.outcome_class != CONFIRMED_APPLIED
            and self.outcome_class != DECLARED_AMBIGUOUS
        )

    @property
    def is_terminal(self) -> bool:
        """Did the system reach a decision it is willing to stand behind?"""
        return self.outcome_class in {
            CONFIRMED_APPLIED,
            CONFIRMED_NOT_APPLIED,
            DECLARED_AMBIGUOUS,
        }


@dataclass
class RunRecord:
    """One run, reduced to the executions it produced."""

    run_id: str
    system: str
    crash_point: str
    endpoint: str
    response_class: str
    readback_keying: str
    seed: int
    config_digest: str
    has_sigkill: bool
    wall_seconds: float
    dataset_version: str = "unversioned"
    experiment_plan_sha256: str = ""
    git_sha: str = ""
    redis_durability: str = "unknown"
    redis_version: str = "unknown"
    redis_image: str = "unknown"
    source_raw_directory_hash: str = ""
    #: Whether a recovery service was actually running during this run. Read
    #: from the log (``recovery_spawned`` versus ``recovery_not_started``)
    #: rather than from the system's name, so it describes what happened.
    #:
    #: It matters because "recovery success rate" means two different things
    #: either side of it. Where a recovery service ran, a crashed execution
    #: reaching a terminal classification was *recovered*. Where none ran, the
    #: same execution reached its classification because the supervisor ran the
    #: step again -- which is not recovery, it is the thing recovery exists to
    #: avoid, and reporting the two under one name would credit a baseline with
    #: a capability it does not have.
    had_recovery_service: bool = False
    #: Wall-clock span minus monotonic span, over the runner's own records.
    #: On a host that never suspends this is ~0. Where the host *did* suspend,
    #: CLOCK_MONOTONIC stopped and CLOCK_REALTIME was resynchronised on
    #: resume, so every wall-clock duration in the run silently includes the
    #: suspension. See ``TIMING_SUSPENSION_TOLERANCE_SECONDS``.
    suspension_seconds: float = 0.0
    #: Amendment E5: whether the operator declared, before the run, that this
    #: host cannot suspend. Read from the run's own config echo.
    suspend_disabled_declared: bool = False
    #: The named condition the cell was collected under. ``""`` is Session 3's
    #: -- every execution crashed, no infrastructure fault.
    regime: str = ""
    #: Probability an execution was selected for the worker crash. The
    #: denominator of every overhead number: a run with a nonzero value has no
    #: crash-free step latency to contribute.
    crash_probability: float = 1.0
    #: Amendment E1: whether a worker hard-killed Redis during this run, and
    #: what happened to the un-acknowledged write made just before it.
    redis_kill_point: str | None = None
    redis_kill_canary: str | None = None
    redis_kill_was_killed: bool = False
    redis_kill_start_ms: int | None = None
    redis_kill_readiness_ms: int | None = None
    redis_uptime_after_seconds: int | None = None
    executions: list[ExecutionRecord] = field(default_factory=list)
    crash_injections: int = 0

    @property
    def suspension_detected(self) -> bool:
        return self.suspension_seconds > TIMING_SUSPENSION_TOLERANCE_SECONDS

    @property
    def timing_is_usable(self) -> bool:
        """Amendment E5's gate: declared *and* not observed to have suspended.

        Both halves are necessary and neither is sufficient. The detection
        catches a host that suspended despite the declaration; the declaration
        catches a host that could have suspended and merely did not happen to
        during this run, which no measurement can distinguish from one that
        cannot suspend at all. A run failing either contributes its **counts**
        to every rate -- an execution either duplicated or it did not -- and
        contributes no duration to anything.
        """
        return self.suspend_disabled_declared and not self.suspension_detected

    @property
    def is_crash_free(self) -> bool:
        """Amendment E2: may this run contribute to an overhead number?

        Only a run in which **nothing was injected at all** measures what the
        protocol costs. Three conditions, and the third was learned the hard
        way: the first pass at this counted the ``redis-kill-preack`` runs as
        crash-free, because their ``crash_probability`` is 0 and no *worker*
        was killed -- and every one of them contains a Redis outage and a
        container restart. Overhead computed over those would have been the
        cost of a hard kill wearing the units of protocol overhead, which is
        precisely the error amendment E2 exists to stop.

        At ``crash_probability = 1.0``, separately, AEP-full and B3 never reach
        ``execution_resolved`` at all, and the step latencies that *do* appear
        belong to the baselines' re-executions -- a measurement of the lease
        wait in the same disguise.
        """
        return (
            self.crash_probability == 0.0
            and self.crash_injections == 0
            and self.redis_kill_point is None
        )

    @property
    def cell_key(self) -> str:
        parts = [self.system, self.crash_point, self.endpoint, self.readback_keying]
        if self.regime:
            parts.append(self.regime)
        return "|".join(parts)

    @property
    def regime_label(self) -> str:
        """The regime, with Session 3's unnamed one given a printable name.

        ``regime`` is ``""`` for the runs collected before regimes existed,
        which is what preserves their cell identity (see
        ``experiments/tests/test_cell_identity.py``). An empty string is the
        right *key* and the wrong *label*: in a CSV column it reads as a
        missing value rather than as the every-execution-crashed condition it
        denotes.
        """
        return self.regime or "crashed"


def load_run(directory: Path) -> RunRecord | None:
    """Reduce one results directory to a :class:`RunRecord`, or skip it.

    ``None`` for a directory with no merged log or no ledger: an interrupted
    run is not a result and must not be counted as an empty one.
    """
    events_path = directory / "events.jsonl"
    ledger_path = directory / "ground_truth.sqlite3"
    if not events_path.is_file() or not ledger_path.is_file():
        return None

    records = read_jsonl(events_path)
    started = events_of(records, "run_started")
    if not started:
        return None
    opening = started[0]
    config = dict(opening["run_config"])
    mock_config = dict(opening.get("mock_api_config", {}))
    environment = dict(opening.get("environment", {}))

    endpoint = str(config["endpoint"])
    response_class = str(
        mock_config.get("endpoints", {}).get(endpoint, {}).get("response_class", "")
    )

    effects = oracle_effects_by_target(ledger_path)

    # The workload plan is echoed into the log, so the execution -> target
    # mapping comes out of the log rather than being recomputed from the seed.
    # An analysis that re-derived it would agree with the harness by
    # construction even if the harness had run something else.
    plan = {
        str(item["execution_id"]): item
        for item in opening.get("workload", {}).get("items", [])
    }

    crash_wall: dict[str, int] = {}
    for record in events_of(records, "crash_injected"):
        execution_id = record.get("execution_id")
        if execution_id and execution_id not in crash_wall:
            crash_wall[str(execution_id)] = int(record["wall_ms"])

    resolved: dict[str, dict[str, Any]] = {}
    for record in events_of(records, "execution_resolved"):
        resolved[str(record["execution_id"])] = record

    classified_wall: dict[str, int] = {}
    final: dict[str, dict[str, Any]] = {}
    for record in events_of(records, "final_classification"):
        execution_id = str(record["execution_id"])
        final[execution_id] = record
        classified_wall[execution_id] = int(record["wall_ms"])

    # A settling poll that first reports an execution settled is a better
    # estimate of "when was it classified" than the end-of-run sweep, which
    # happens once and late. Where the run has them, use the earliest poll at
    # which nothing was pending.
    settled_at: int | None = None
    for record in events_of(records, "settling_poll"):
        if int(record.get("pending", 1)) == 0:
            settled_at = int(record["wall_ms"])
            break

    run_started_ms = int(opening["wall_ms"])
    finished = events_of(records, "run_finished")
    run_finished_ms = int(finished[-1]["wall_ms"]) if finished else run_started_ms

    # The runner is one process, so max-minus-min over its own records is a
    # valid monotonic span, and comparing it with the wall span detects a host
    # suspension that both clocks would otherwise hide.
    runner_records = [
        record
        for record in records
        if record.get("source") == "runner" and "monotonic_ns" in record
    ]
    if len(runner_records) >= 2:
        wall_span = (
            max(int(r["wall_ms"]) for r in runner_records)
            - min(int(r["wall_ms"]) for r in runner_records)
        ) / 1000.0
        monotonic_span = (
            max(int(r["monotonic_ns"]) for r in runner_records)
            - min(int(r["monotonic_ns"]) for r in runner_records)
        ) / 1e9
        suspension = max(0.0, wall_span - monotonic_span)
    else:
        suspension = 0.0

    executions: list[ExecutionRecord] = []
    for execution_id, item in plan.items():
        classification = final.get(execution_id)
        if classification is None:
            # No final classification means the run did not complete its
            # sweep. Counting the execution as anything would be inventing a
            # result for it.
            continue
        outcome_class = str(classification.get("outcome_class", ""))
        if outcome_class not in KNOWN_CLASSES:
            raise AnalysisError(
                f"{directory.name}: unknown outcome class {outcome_class!r}. The "
                "analysis reads the log format, not the harness's enum, so a "
                "class it has never seen is refused rather than bucketed."
            )
        target = str(item["target"])
        resolution = resolved.get(execution_id)
        crash_ms = crash_wall.get(execution_id)
        executions.append(
            ExecutionRecord(
                run_id=str(config["run_id"]),
                system=str(config["system"]),
                crash_point=str(config.get("crash_point") or "none"),
                endpoint=endpoint,
                response_class=response_class,
                readback_keying=str(config["readback_keying"]),
                execution_id=execution_id,
                outcome_class=outcome_class,
                status=str(classification.get("status", "")),
                applied_effects=int(effects.get(target, 0)),
                crashed=crash_ms is not None,
                dispatch_attempts=int(
                    (resolution or {}).get(
                        "dispatch_attempts", classification.get("dispatch_attempts", 0)
                    )
                ),
                resolved_wall_ms=(
                    int(resolution["wall_ms"]) if resolution is not None else None
                ),
                step_latency_ms=(
                    float(resolution["duration_ns"]) / 1e6
                    if resolution is not None and "duration_ns" in resolution
                    else None
                ),
                crash_wall_ms=crash_ms,
                classified_wall_ms=(
                    settled_at
                    if settled_at is not None
                    else classified_wall.get(execution_id)
                ),
            )
        )

    # The regime is not in the run config -- it is the matrix's word, not the
    # harness's -- so it is reconstructed from the two config fields that
    # define it. A run collected before regimes existed has crash_probability
    # 1.0 and no Redis kill, which is exactly Session 3's unnamed regime.
    crash_probability = float(config.get("crash_probability", 1.0))
    redis_kill_point = config.get("redis_kill_point") or None
    kill_records = events_of(records, "redis_hard_killed")
    kill_record = kill_records[-1] if kill_records else {}

    return RunRecord(
        run_id=str(config["run_id"]),
        system=str(config["system"]),
        crash_point=str(config.get("crash_point") or "none"),
        endpoint=endpoint,
        response_class=response_class,
        readback_keying=str(config["readback_keying"]),
        seed=int(config["seed"]),
        config_digest=str(config.get("config_digest", "")),
        has_sigkill=bool(environment.get("has_sigkill", False)),
        wall_seconds=max(0.0, (run_finished_ms - run_started_ms) / 1000.0),
        dataset_version=str(config.get("dataset_version") or "unversioned"),
        experiment_plan_sha256=str(config.get("experiment_plan_sha256") or ""),
        git_sha=str(config.get("git_sha") or ""),
        redis_durability=str(config.get("redis_durability") or "unknown"),
        redis_version=str(config.get("redis_version") or "unknown"),
        redis_image=str(config.get("redis_image") or "unknown"),
        source_raw_directory_hash=raw_directory_sha256(directory),
        had_recovery_service=bool(events_of(records, "recovery_spawned")),
        suspension_seconds=round(suspension, 3),
        suspend_disabled_declared=bool(
            config.get("suspend_disabled_declared", False)
        ),
        regime=_regime_of(crash_probability, redis_kill_point),
        crash_probability=crash_probability,
        redis_kill_point=redis_kill_point,
        redis_kill_canary=(
            str(kill_record.get("canary")) if kill_records else None
        ),
        redis_kill_was_killed=bool(kill_record.get("was_killed", False)),
        redis_kill_start_ms=(
            int(kill_record["start_ms"]) if "start_ms" in kill_record else None
        ),
        redis_kill_readiness_ms=(
            int(kill_record["readiness_ms"])
            if "readiness_ms" in kill_record
            else None
        ),
        redis_uptime_after_seconds=(
            int(kill_record["uptime_after_seconds"])
            if "uptime_after_seconds" in kill_record
            else None
        ),
        executions=executions,
        crash_injections=len(events_of(records, "crash_injected")),
    )


def _regime_of(crash_probability: float, redis_kill_point: str | None) -> str:
    """The matrix regime a run belongs to, read back from its own config.

    Deliberately derived rather than trusted from a field the matrix wrote:
    the analysis reads what the *run* did, and a mislabelled cell would then
    be a disagreement rather than a silently pooled result.
    """
    if redis_kill_point == "after_intent_before_barrier":
        return "redis-kill-preack"
    if redis_kill_point is not None:
        return "redis-kill-inflight"
    if crash_probability == 0.0:
        return "p0"
    if crash_probability == 1.0:
        return ""
    return f"p{int(round(crash_probability * 100))}"


def raw_directory_sha256(directory: Path) -> str:
    """Hash every raw file and its relative path without interpreting it."""
    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        relative = path.relative_to(directory).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        size = path.stat().st_size
        digest.update(size.to_bytes(8, "big"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def load_voided_attempts(results_root: Path) -> list[dict[str, Any]]:
    """Verify the append-only void archive and return its accounting rows."""
    voided = results_root / "voided"
    if not voided.exists():
        return []
    if not voided.is_dir():
        raise AnalysisError(f"voided evidence path is not a directory: {voided}")
    reasons = sorted(voided.glob("*.void.json"))
    preserved = sorted(
        path for path in voided.iterdir()
        if path.is_dir()
    )
    if len(reasons) != len(preserved):
        raise AnalysisError(
            "voided-run accounting mismatch: "
            f"{len(preserved)} preserved directories, {len(reasons)} reasons"
        )
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for reason_path in reasons:
        try:
            row = json.loads(reason_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise AnalysisError(f"cannot parse {reason_path}: {error}") from None
        target = voided / str(row.get("preserved_path") or "")
        if not target.is_dir():
            raise AnalysisError(f"void reason has no preserved target: {reason_path}")
        if target.name in seen:
            raise AnalysisError(f"duplicate void target {target.name}")
        seen.add(target.name)
        observed = raw_directory_sha256(target)
        if observed != row.get("source_raw_directory_hash"):
            raise AnalysisError(
                f"voided raw-directory hash mismatch for {target}: "
                f"{observed} != {row.get('source_raw_directory_hash')}"
            )
        rows.append(row)
    if seen != {path.name for path in preserved}:
        raise AnalysisError("a preserved void directory has no machine-readable reason")
    return rows


def load_runs(results_root: Path) -> list[RunRecord]:
    runs: list[RunRecord] = []
    incomplete: list[str] = []
    for directory in sorted(path for path in results_root.iterdir() if path.is_dir()):
        if directory.name in {"analysis", "voided"}:
            continue
        run = load_run(directory)
        if run is not None:
            runs.append(run)
        else:
            incomplete.append(directory.name)
    if incomplete:
        raise AnalysisError(
            "raw run directories without both analysis inputs must be moved "
            f"to results/voided with a reason: {', '.join(incomplete[:20])}"
        )
    run_ids = [run.run_id for run in runs]
    if len(run_ids) != len(set(run_ids)):
        duplicates = sorted(
            run_id for run_id, count in Counter(run_ids).items() if count > 1
        )
        raise AnalysisError(f"duplicate run IDs: {duplicates}")
    seed_keys = [(run.dataset_version, run.redis_durability, run.seed) for run in runs]
    if len(seed_keys) != len(set(seed_keys)):
        duplicates = sorted(
            key for key, count in Counter(seed_keys).items() if count > 1
        )
        raise AnalysisError(f"duplicate seeds within dataset/configuration: {duplicates}")
    return runs


# ===========================================================================
# Metrics
# ===========================================================================


def _numerator(metric: str, execution: ExecutionRecord) -> int:
    if metric == "undetected_duplicate_rate":
        return int(execution.is_undetected_duplicate)
    if metric == "known_ambiguity_rate":
        return int(execution.outcome_class == DECLARED_AMBIGUOUS)
    if metric == "lost_effect_rate":
        return int(execution.is_lost_effect)
    if metric == "unverified_failure_rate":
        return int(execution.outcome_class == UNVERIFIED_FAILURE)
    if metric == "state_corruption_rate":
        return int(execution.outcome_class == UNREADABLE)
    if metric == "recovery_success_rate":
        return int(execution.crashed and execution.is_terminal)
    raise AnalysisError(f"unknown metric {metric!r}")


def _denominator(metric: str, execution: ExecutionRecord) -> int:
    # Recovery success is conditional on having crashed. Every other rate is
    # per execution.
    if metric == "recovery_success_rate":
        return int(execution.crashed)
    return 1


@dataclass
class MetricResult:
    """One metric, for one group of runs."""

    metric: str
    group: dict[str, str]
    successes: int
    total: int
    interval: Any
    runs: int

    def echo(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            **self.group,
            "successes": self.successes,
            "total": self.total,
            "rate": proportion(self.successes, self.total),
            "runs": self.runs,
            **{
                key: value
                for key, value in self.interval.echo().items()
                if key != "point"
            },
        }


def compute_metric(
    metric: str,
    runs: Sequence[RunRecord],
    group: Mapping[str, str],
    *,
    resamples: int,
    seed: int,
) -> MetricResult:
    if metric == "recovery_success_rate":
        # A run with no recovery service contributes no observations to a
        # metric about recovery. Excluded rather than counted as zero *or* as
        # success: both would be statements about a component that was not
        # present.
        runs = [run for run in runs if run.had_recovery_service]
    clusters: list[tuple[int, int]] = []
    successes = total = 0
    for run in runs:
        run_successes = sum(_numerator(metric, item) for item in run.executions)
        run_total = sum(_denominator(metric, item) for item in run.executions)
        clusters.append((run_successes, run_total))
        successes += run_successes
        total += run_total
    return MetricResult(
        metric=metric,
        group=dict(group),
        successes=successes,
        total=total,
        interval=cluster_bootstrap_proportion(
            clusters, resamples=resamples, seed=seed
        ),
        runs=len(runs),
    )


def group_runs(
    runs: Sequence[RunRecord], keys: Sequence[str]
) -> dict[tuple[str, ...], list[RunRecord]]:
    grouped: dict[tuple[str, ...], list[RunRecord]] = defaultdict(list)
    for run in runs:
        grouped[tuple(getattr(run, key) for key in keys)].append(run)
    return dict(grouped)


# ===========================================================================
# Outputs
# ===========================================================================


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def build_table_one(
    runs: Sequence[RunRecord], *, resamples: int, seed: int
) -> list[dict[str, Any]]:
    """A within-dataset, within-durability, within-regime system summary."""
    selected = [run for run in runs if run.regime_label == FIGURE_REGIME]
    rows: list[dict[str, Any]] = []
    grouped = group_runs(
        selected, ["dataset_version", "redis_durability", "regime_label", "system"]
    )
    for values, system_runs in sorted(grouped.items()):
        dataset, durability, regime, system = values
        reference = grouped.get(
            (dataset, durability, regime, REFERENCE_SYSTEM), []
        )
        duplicate = compute_metric(
            "undetected_duplicate_rate",
            system_runs,
            {
                "dataset_version": dataset,
                "redis_durability": durability,
                "regime": regime,
                "system": system,
            },
            resamples=resamples,
            seed=seed,
        )
        ambiguity = compute_metric(
            "known_ambiguity_rate",
            system_runs,
            {"system": system},
            resamples=resamples,
            seed=seed,
        )
        lost = compute_metric(
            "lost_effect_rate",
            system_runs,
            {"system": system},
            resamples=resamples,
            seed=seed,
        )
        row: dict[str, Any] = {
            "dataset_version": dataset,
            "redis_durability": durability,
            "regime": regime,
            "system": system,
            "runs": len(system_runs),
            "executions": duplicate.total,
            "crash_points_covered": len({run.crash_point for run in system_runs}),
            "response_classes_covered": len({run.response_class for run in system_runs}),
            "undetected_duplicates": duplicate.successes,
            "undetected_duplicate_rate": proportion(
                duplicate.successes, duplicate.total
            ),
            "undetected_duplicate_ci_low": duplicate.interval.low,
            "undetected_duplicate_ci_high": duplicate.interval.high,
            "known_ambiguities": ambiguity.successes,
            "known_ambiguity_rate": proportion(ambiguity.successes, ambiguity.total),
            "known_ambiguity_ci_low": ambiguity.interval.low,
            "known_ambiguity_ci_high": ambiguity.interval.high,
            "lost_effects": lost.successes,
            "lost_effect_rate": proportion(lost.successes, lost.total),
        }
        if system != REFERENCE_SYSTEM and reference:
            reference_duplicate = compute_metric(
                "undetected_duplicate_rate",
                reference,
                {"system": REFERENCE_SYSTEM},
                resamples=resamples,
                seed=seed,
            )
            comparison = compare_rates(
                "undetected_duplicate_rate",
                system=system,
                reference=REFERENCE_SYSTEM,
                system_successes=duplicate.successes,
                system_total=duplicate.total,
                reference_successes=reference_duplicate.successes,
                reference_total=reference_duplicate.total,
            )
            row["fisher_p_vs_aep_full"] = comparison.p_value
        else:
            row["fisher_p_vs_aep_full"] = None
        rows.append(row)
    return rows


def build_comparisons(
    runs: Sequence[RunRecord], *, resamples: int, seed: int
) -> list[dict[str, Any]]:
    """Every baseline against AEP-full, separately within each fault regime."""

    def run_clusters_by_stratum(
        selected: Sequence[RunRecord], metric: str
    ) -> dict[str, list[tuple[int, int]]]:
        strata: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for run in selected:
            if metric == "recovery_success_rate" and not run.had_recovery_service:
                continue
            successes = sum(_numerator(metric, item) for item in run.executions)
            total = sum(_denominator(metric, item) for item in run.executions)
            if total:
                key = "|".join(
                    (run.crash_point, run.response_class, run.readback_keying)
                )
                strata[key].append((successes, total))
        return dict(strata)

    # ``regime_label`` is derived by ``load_run`` from crash probability and
    # Redis-kill fields in the run's own schema. It is not a row-position or
    # directory-name convention. Grouping it with system makes cross-regime
    # pooling structurally impossible here.
    grouped = group_runs(
        runs, ["dataset_version", "redis_durability", "regime_label", "system"]
    )
    rows: list[dict[str, Any]] = []
    experiments = sorted(
        {(dataset, durability, regime) for dataset, durability, regime, _ in grouped}
    )
    for dataset, durability, regime in experiments:
        reference_runs = grouped.get(
            (dataset, durability, regime, REFERENCE_SYSTEM), []
        )
        if not reference_runs:
            continue
        systems = sorted(
            system
            for grouped_dataset, grouped_durability, grouped_regime, system in grouped
            if grouped_dataset == dataset
            and grouped_durability == durability
            and grouped_regime == regime
            and system != REFERENCE_SYSTEM
        )
        for metric in RATE_METRICS:
            reference = compute_metric(
                metric,
                reference_runs,
                {
                    "dataset_version": dataset,
                    "redis_durability": durability,
                    "regime": regime,
                    "system": REFERENCE_SYSTEM,
                },
                resamples=resamples,
                seed=seed,
            )
            for system in systems:
                system_runs = grouped[(dataset, durability, regime, system)]
                result = compute_metric(
                    metric,
                    system_runs,
                    {
                        "dataset_version": dataset,
                        "redis_durability": durability,
                        "regime": regime,
                        "system": system,
                    },
                    resamples=resamples,
                    seed=seed,
                )
                comparison = compare_rates(
                    metric,
                    system=system,
                    reference=REFERENCE_SYSTEM,
                    system_successes=result.successes,
                    system_total=result.total,
                    reference_successes=reference.successes,
                    reference_total=reference.total,
                )
                row: dict[str, Any] = {
                    "dataset_version": dataset,
                    "redis_durability": durability,
                    "regime": regime,
                    **comparison.echo(),
                    "system_runs": result.runs,
                    "reference_runs": reference.runs,
                    "fisher_unit": "execution (cluster-unadjusted)",
                }
                if metric == "known_ambiguity_rate":
                    system_strata = run_clusters_by_stratum(system_runs, metric)
                    reference_strata = run_clusters_by_stratum(reference_runs, metric)
                    if system_strata and set(system_strata) == set(reference_strata):
                        interval = stratified_cluster_bootstrap_difference(
                            system_strata,
                            reference_strata,
                            resamples=resamples,
                            seed=seed,
                            confidence=AMBIGUITY_DIFFERENCE_CONFIDENCE,
                        )
                        row.update(
                            {
                                "difference_rate": interval.point,
                                "difference_ci_low": interval.low,
                                "difference_ci_high": interval.high,
                                "difference_confidence": interval.confidence,
                                "difference_method": (
                                    "stratified run-cluster percentile bootstrap"
                                ),
                                "difference_strata": interval.strata,
                                "system_clusters": interval.system_clusters,
                                "reference_clusters": interval.reference_clusters,
                                "equivalence_margin": AMBIGUITY_EQUIVALENCE_MARGIN,
                                "equivalent_within_margin": interval.within(
                                    AMBIGUITY_EQUIVALENCE_MARGIN
                                ),
                                "equivalence_margin_preregistered": False,
                            }
                        )
                rows.append(row)
    return rows


def build_latencies(runs: Sequence[RunRecord]) -> list[dict[str, Any]]:
    """Step latency, recovery latency and throughput, per system.

    Two gates apply and they are different gates, so both are reported.

    **Amendment E5 (timing validity).** A duration is used only from a run on
    a host declared unable to suspend *and* not observed to have suspended.

    **Amendment E2 (what overhead means).** Step latency and throughput are
    computed from **crash-free runs only**. RQ3 asks what the protocol costs,
    and an execution that was killed partway through did not pay that cost --
    it paid a different one. Session 3's overhead column was empty for
    AEP-full and B3 for exactly this reason and full of the baselines' lease
    waits for the same one. ``overhead_runs`` is the honest denominator and is
    printed beside every number computed from it.

    Recovery latency is *not* gated on crash-freedom: it has no meaning
    without a crash, so it is drawn from the crashed runs, which is stated
    rather than left to be inferred from the column being non-empty.
    """
    rows: list[dict[str, Any]] = []
    for values, system_runs in sorted(
        group_runs(runs, ["dataset_version", "redis_durability", "system"]).items()
    ):
        dataset, durability, system = values
        # Timing only from runs whose clocks are trustworthy. A host suspension
        # puts its whole duration into every wall-clock interval in the run,
        # and no amount of averaging removes it.
        timed_runs = [run for run in system_runs if run.timing_is_usable]
        overhead_runs = [run for run in timed_runs if run.is_crash_free]
        step = [
            execution.step_latency_ms
            for run in overhead_runs
            for execution in run.executions
            if execution.step_latency_ms is not None
        ]
        # Only from runs that actually had a recovery service. See the module
        # docstring: without one, crash-to-classified is the latency of a
        # re-execution, which is a different quantity wearing the same units.
        recovery = [
            execution.recovery_latency_ms
            for run in timed_runs
            if run.had_recovery_service
            for execution in run.executions
            if execution.recovery_latency_ms is not None and execution.crashed
        ]
        # Throughput is an overhead number too, so it shares the denominator.
        executions = sum(len(run.executions) for run in overhead_runs)
        wall = sum(run.wall_seconds for run in overhead_runs)
        row: dict[str, Any] = {
            "dataset_version": dataset,
            "redis_durability": durability,
            "system": system,
            "runs": len(system_runs),
            "runs_with_usable_timing": len(timed_runs),
            "runs_dropped_for_clock_suspension": sum(
                1 for run in system_runs if run.suspension_detected
            ),
            "runs_dropped_for_undeclared_suspend_policy": sum(
                1
                for run in system_runs
                if not run.suspend_disabled_declared and not run.suspension_detected
            ),
            # Amendment E2's denominator, printed so no reader has to guess
            # which runs an overhead number came from.
            "overhead_runs_crash_free": len(overhead_runs),
        }
        for prefix, values in (("step_latency_ms", step), ("recovery_latency_ms", recovery)):
            for key, value in summarise(values).items():
                row[f"{prefix}_{key}"] = value
        row["executions"] = executions
        row["recovery_service"] = int(
            all(run.had_recovery_service for run in system_runs)
        )
        row["run_wall_seconds"] = round(wall, 3)
        row["executions_per_second"] = round(executions / wall, 4) if wall else None
        rows.append(row)
    return rows


def build_redis_kill_evidence(runs: Sequence[RunRecord]) -> list[dict[str, Any]]:
    """Amendment E1: what each hard Redis kill did, per system and variant.

    Two quantities, and the paper needs both.

    ``applied_effects`` is the discriminator the ablation is *for*: under a
    kill placed between the intent CAS and the barrier acknowledgement,
    AEP-full's ``WAITAOF`` fails and its ``DurabilityAck`` is never issued, so
    it must not have dispatched. B3, which does not wait, must have.

    ``canary`` is the *durability* question, and it is reported because the
    answer is counter-intuitive and load-bearing: an un-acknowledged write made
    immediately before a hard kill is expected to survive, because
    ``appendfsync everysec`` defers the fsync and not the ``write(2)``. Every
    row that says ``SURVIVED`` is another instance of the finding that no
    process-level fault can separate B3 from AEP-full on record durability.
    """
    rows: list[dict[str, Any]] = []
    killed = [run for run in runs if run.redis_kill_point is not None]
    keys = [
        "dataset_version", "redis_durability", "regime",
        "system", "response_class",
    ]
    for values, group in sorted(group_runs(killed, keys).items()):
        executions = [
            execution for run in group for execution in run.executions
        ]
        canaries = Counter(run.redis_kill_canary or "UNRECORDED" for run in group)
        metric_predicates = {
            "unwanted_applied_effect": lambda item: item.applied_effects > 0,
            "dispatch_withheld": lambda item: item.dispatch_attempts == 0,
            "declared_ambiguous": lambda item: item.outcome_class == DECLARED_AMBIGUOUS,
            "undetected_duplicate": lambda item: item.is_undetected_duplicate,
            "lost_effect": lambda item: item.is_lost_effect,
        }
        metric_values: dict[str, dict[str, Any]] = {}
        for metric, predicate in metric_predicates.items():
            clusters = [
                (
                    sum(1 for item in run.executions if predicate(item)),
                    len(run.executions),
                )
                for run in group
            ]
            interval = cluster_bootstrap_proportion(clusters)
            successes = sum(pair[0] for pair in clusters)
            total = sum(pair[1] for pair in clusters)
            metric_values[metric] = {
                f"{metric}_numerator": successes,
                f"{metric}_denominator": total,
                f"{metric}_rate": proportion(successes, total),
                f"{metric}_ci_low": interval.low,
                f"{metric}_ci_high": interval.high,
                f"{metric}_clusters": interval.clusters,
                f"{metric}_interval_method": "run-cluster percentile bootstrap",
            }
        rows.append(
            {
                **dict(zip(keys, values)),
                "runs": len(group),
                "executions": len(executions),
                "executions_with_an_applied_effect": sum(
                    1 for execution in executions if execution.applied_effects > 0
                ),
                "applied_effects_total": sum(
                    execution.applied_effects for execution in executions
                ),
                "declared_ambiguous": sum(
                    1
                    for execution in executions
                    if execution.outcome_class == DECLARED_AMBIGUOUS
                ),
                "confirmed_not_applied": sum(
                    1
                    for execution in executions
                    if execution.outcome_class == CONFIRMED_NOT_APPLIED
                ),
                "undetected_duplicates": sum(
                    1
                    for execution in executions
                    if execution.is_undetected_duplicate
                ),
                "lost_effects": sum(
                    1 for execution in executions if execution.is_lost_effect
                ),
                "canary_survived": canaries.get("SURVIVED", 0),
                "canary_lost": canaries.get("LOST", 0),
                "redis_kill_confirmed": sum(
                    1 for run in group if run.redis_kill_was_killed
                ),
                "redis_restart_start_ms_median": summarise(
                    [
                        float(run.redis_kill_start_ms)
                        for run in group
                        if run.redis_kill_start_ms is not None
                    ]
                )["median"],
                "redis_restart_readiness_ms_median": summarise(
                    [
                        float(run.redis_kill_readiness_ms)
                        for run in group
                        if run.redis_kill_readiness_ms is not None
                    ]
                )["median"],
                "redis_uptime_after_seconds_max": max(
                    (
                        run.redis_uptime_after_seconds
                        for run in group
                        if run.redis_uptime_after_seconds is not None
                    ),
                    default=None,
                ),
                "barrier_behavior": (
                    "acknowledged_if_dispatched; refused_or_failed_if_withheld"
                    if values[keys.index("system")] == "AEP_FULL"
                    else "not_applicable_barrier_ablated"
                ),
                "independent_ledger_agreement_runs": len(group),
                **{
                    key: value
                    for payload in metric_values.values()
                    for key, value in payload.items()
                },
            }
        )
    return rows


def build_timing_comparisons(
    runs: Sequence[RunRecord], *, resamples: int, seed: int
) -> list[dict[str, Any]]:
    """Primary B3 estimand within each Redis durability configuration."""
    selected = [
        run
        for run in runs
        if run.regime_label == "p0"
        and run.timing_is_usable
        and run.system in {"AEP_FULL", "B3_INTENT_NO_BARRIER"}
    ]
    keys = ("dataset_version", "redis_durability")
    rows: list[dict[str, Any]] = []
    for values, group in sorted(group_runs(selected, keys).items()):
        by_system: dict[str, dict[str, list[float]]] = {}
        for system in ("AEP_FULL", "B3_INTENT_NO_BARRIER"):
            by_system[system] = {
                run.run_id: [
                    float(item.step_latency_ms)
                    for item in run.executions
                    if item.step_latency_ms is not None
                ]
                for run in group
                if run.system == system
            }
            by_system[system] = {
                run_id: samples
                for run_id, samples in by_system[system].items()
                if samples
            }
        if not all(by_system.values()):
            continue
        interval = cluster_bootstrap_median_difference(
            by_system["AEP_FULL"],
            by_system["B3_INTENT_NO_BARRIER"],
            resamples=resamples,
            seed=seed,
            confidence=0.95,
        )
        rows.append(
            {
                **dict(zip(keys, values)),
                "estimand": "median AEP-full step latency minus median B3 step latency",
                "aep_runs": interval.treatment_clusters,
                "b3_runs": interval.control_clusters,
                "aep_executions": interval.treatment_observations,
                "b3_executions": interval.control_observations,
                "aep_median_step_latency_ms": summarise(
                    [
                        value
                        for samples in by_system["AEP_FULL"].values()
                        for value in samples
                    ]
                )["median"],
                "b3_median_step_latency_ms": summarise(
                    [
                        value
                        for samples in by_system["B3_INTENT_NO_BARRIER"].values()
                        for value in samples
                    ]
                )["median"],
                "median_difference_ms": interval.point,
                "ci_low_ms": interval.low,
                "ci_high_ms": interval.high,
                "confidence": interval.confidence,
                "interval_method": "run-cluster percentile bootstrap",
                "bootstrap_resamples": interval.resamples,
                "bootstrap_seed": interval.seed,
            }
        )
    return rows


def build_redis_kill_comparisons(
    runs: Sequence[RunRecord], *, resamples: int, seed: int
) -> list[dict[str, Any]]:
    """AEP-full minus B3 within each Redis-kill capability cell."""
    killed = [run for run in runs if run.redis_kill_point is not None]
    group_keys = (
        "dataset_version", "redis_durability", "regime_label", "response_class"
    )
    rows: list[dict[str, Any]] = []
    predicates = {
        "unwanted_applied_effect_rate": lambda item: item.applied_effects > 0,
        "dispatch_withheld_rate": lambda item: item.dispatch_attempts == 0,
        "declared_ambiguity_rate": lambda item: item.outcome_class == DECLARED_AMBIGUOUS,
        "undetected_duplicate_rate": lambda item: item.is_undetected_duplicate,
        "lost_effect_rate": lambda item: item.is_lost_effect,
    }
    for values, group in sorted(group_runs(killed, group_keys).items()):
        arms = {
            system: [run for run in group if run.system == system]
            for system in ("AEP_FULL", "B3_INTENT_NO_BARRIER")
        }
        if not all(arms.values()):
            continue
        for metric, predicate in predicates.items():
            clusters: dict[str, list[tuple[int, int]]] = {}
            for system, arm_runs in arms.items():
                clusters[system] = [
                    (
                        sum(1 for item in run.executions if predicate(item)),
                        len(run.executions),
                    )
                    for run in arm_runs
                ]
            aep_success = sum(pair[0] for pair in clusters["AEP_FULL"])
            aep_total = sum(pair[1] for pair in clusters["AEP_FULL"])
            b3_success = sum(
                pair[0] for pair in clusters["B3_INTENT_NO_BARRIER"]
            )
            b3_total = sum(
                pair[1] for pair in clusters["B3_INTENT_NO_BARRIER"]
            )
            interval = stratified_cluster_bootstrap_difference(
                {"cell": clusters["AEP_FULL"]},
                {"cell": clusters["B3_INTENT_NO_BARRIER"]},
                resamples=resamples,
                seed=seed,
                confidence=0.95,
            )
            comparison = compare_rates(
                metric,
                system="AEP_FULL",
                reference="B3_INTENT_NO_BARRIER",
                system_successes=aep_success,
                system_total=aep_total,
                reference_successes=b3_success,
                reference_total=b3_total,
            )
            rows.append(
                {
                    **dict(zip(group_keys, values)),
                    "metric": metric,
                    "aep_numerator": aep_success,
                    "aep_denominator": aep_total,
                    "aep_rate": proportion(aep_success, aep_total),
                    "b3_numerator": b3_success,
                    "b3_denominator": b3_total,
                    "b3_rate": proportion(b3_success, b3_total),
                    "absolute_difference_aep_minus_b3": interval.point,
                    "difference_ci_low": interval.low,
                    "difference_ci_high": interval.high,
                    "difference_confidence": interval.confidence,
                    "difference_method": "run-cluster percentile bootstrap",
                    "aep_clusters": interval.system_clusters,
                    "b3_clusters": interval.reference_clusters,
                    "fisher_p_value": comparison.p_value,
                    "fisher_label": "execution-level descriptive test",
                }
            )
    return rows


#: What makes two runs the same cell, for the file the paper quotes.
#:
#: ``regime`` is here because Table 1 is banned as a source precisely for
#: pooling regimes (Session 3B §F2), and a per-cell file that pooled them too
#: would inherit the same defect one level down. It nearly did: the
#: ``redis-kill-preack`` runs carry ``crash_point = "none"`` because no *worker*
#: is killed in them, and so do the crash-free ``p0`` runs. Today the two are
#: told apart only by an accident of which endpoints each happened to be
#: collected against; collect ``p0`` on ``NO_READBACK`` -- it is in the plan --
#: and a crash-free cell would silently merge with a hard-Redis-kill cell into
#: one rate. The grouping attribute is ``regime_label`` and the column is
#: ``regime``: the key must print, and ``""`` does not.
PER_CELL_GROUP_ATTRIBUTES = (
    "dataset_version",
    "redis_durability",
    "regime_label",
    "system",
    "crash_point",
    "response_class",
    "readback_keying",
)
PER_CELL_GROUP_COLUMNS = (
    "dataset_version",
    "redis_durability",
    "regime",
    "system",
    "crash_point",
    "response_class",
    "readback_keying",
)


def build_per_cell(
    runs: Sequence[RunRecord], *, resamples: int, seed: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    grouped = group_runs(runs, PER_CELL_GROUP_ATTRIBUTES)
    for values, cell_runs in sorted(grouped.items()):
        group = dict(zip(PER_CELL_GROUP_COLUMNS, values))
        for metric in RATE_METRICS:
            rows.append(
                compute_metric(
                    metric, cell_runs, group, resamples=resamples, seed=seed
                ).echo()
            )
    return rows


def build_executions_csv(runs: Sequence[RunRecord]) -> list[dict[str, Any]]:
    """Every execution, so a reader can recompute every rate above."""
    return [
        {
            "run_id": execution.run_id,
            "dataset_version": run.dataset_version,
            "git_sha": run.git_sha,
            "experiment_plan_sha256": run.experiment_plan_sha256,
            "regime": run.regime_label,
            "system": execution.system,
            "crash_point": execution.crash_point,
            "endpoint": execution.endpoint,
            "response_class": execution.response_class,
            "readback_keying": execution.readback_keying,
            "redis_durability": run.redis_durability,
            "redis_version": run.redis_version,
            "redis_image": run.redis_image,
            "run_seed": run.seed,
            "run_execution_count": len(run.executions),
            "inclusion_status": "included",
            "source_raw_directory_hash": run.source_raw_directory_hash,
            "execution_id": execution.execution_id,
            "outcome_class": execution.outcome_class,
            "status": execution.status,
            "applied_effects": execution.applied_effects,
            "crashed": int(execution.crashed),
            "dispatch_attempts": execution.dispatch_attempts,
            "step_latency_ms": execution.step_latency_ms,
            "recovery_latency_ms": execution.recovery_latency_ms,
            "undetected_duplicate": int(execution.is_undetected_duplicate),
            "lost_effect": int(execution.is_lost_effect),
        }
        for run in runs
        for execution in run.executions
    ]


def build_run_provenance(runs: Sequence[RunRecord]) -> list[dict[str, Any]]:
    """One inclusion row per independent run."""
    return [
        {
            "dataset_version": run.dataset_version,
            "regime": run.regime_label,
            "system": run.system,
            "endpoint": run.endpoint,
            "response_class": run.response_class,
            "crash_point": run.crash_point,
            "readback_keying": run.readback_keying,
            "redis_durability": run.redis_durability,
            "redis_version": run.redis_version,
            "redis_image": run.redis_image,
            "run_id": run.run_id,
            "seed": run.seed,
            "execution_count": len(run.executions),
            "inclusion_status": "included",
            "git_sha": run.git_sha,
            "experiment_plan_sha256": run.experiment_plan_sha256,
            "source_raw_directory_hash": run.source_raw_directory_hash,
        }
        for run in runs
    ]


def validate_plan_manifest(
    results_root: Path,
    runs: Sequence[RunRecord],
    voided: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Require the finalized plan, included directories, and voids to agree."""
    plan_path = results_root / "matrix-plan.json"
    if not plan_path.is_file():
        raise AnalysisError(f"missing finalized machine plan at {plan_path}")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AnalysisError(f"cannot parse {plan_path}: {error}") from None
    planned = [str(row["run_id"]) for row in plan.get("runs", [])]
    if len(planned) != len(set(planned)):
        raise AnalysisError("matrix plan contains duplicate run IDs")
    included = {run.run_id for run in runs}
    missing = sorted(set(planned) - included)
    extra = sorted(included - set(planned))
    if missing or extra:
        raise AnalysisError(
            "manifest/count disagreement: "
            f"missing planned runs={missing[:20]}, unplanned included runs={extra[:20]}"
        )
    plan_dataset = str(plan.get("dataset_version") or "")
    if {run.dataset_version for run in runs} != {plan_dataset}:
        raise AnalysisError(
            "run dataset version disagrees with matrix plan: "
            f"plan={plan_dataset!r}, runs={sorted({run.dataset_version for run in runs})}"
        )
    for run in runs:
        missing_fields = [
            name
            for name in (
                "experiment_plan_sha256", "git_sha", "redis_durability",
                "redis_version", "redis_image", "source_raw_directory_hash",
            )
            if not getattr(run, name) or getattr(run, name) == "unknown"
        ]
        if missing_fields:
            raise AnalysisError(
                f"{run.run_id} lacks required provenance: {missing_fields}"
            )
    return {
        "matrix_plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "planned_runs": len(planned),
        "included_runs": len(runs),
        "voided_attempts": len(voided),
    }


# ===========================================================================
# Figures
# ===========================================================================


def write_figures(
    table_one: Sequence[Mapping[str, Any]],
    per_cell: Sequence[Mapping[str, Any]],
    destination: Path,
) -> list[Path]:
    """Two PDFs: the headline bars, and the crash-point breakdown.

    matplotlib is imported here rather than at module scope so that the CSVs
    and the tables can still be produced on a machine without it -- a partial
    result is worth more than an import error.

    **Both figures are built from ``per_cell``, filtered to one regime.** The
    first version of figure 1 was built from ``table_one``, which is the table
    Session 3B banned as a source for exactly this reason: it pools the
    crash-free, every-execution-crashed and hard-Redis-kill regimes into one
    bar, so the bar's height is a property of how many runs of each kind were
    collected. A banned table does not become quotable by being drawn.

    ``table_one`` is still accepted, and still used for the system ordering
    only, so that the figure lists systems in the same order as the CSV.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        # Embed scalable TrueType outlines in the paper PDFs.  Matplotlib's
        # default Type 3 output is readable but complicates print-quality and
        # accessibility checks once these figures are included by LaTeX.
        matplotlib.rcParams["pdf.fonttype"] = 42
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # -- Figure 1: the headline trade, per system, ONE regime ---------------
    #
    # Pooled over the six crash points within the crashed regime, weighted by
    # each cell's own denominator -- which is what a rate over executions
    # means. Averaging the per-cell rates instead would weight a 10-execution
    # cell equally with a 30-execution one.
    figure_regime = FIGURE_REGIME
    pooled: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(lambda: [0, 0])
    )
    for row in per_cell:
        if row.get("regime") != figure_regime:
            continue
        bucket = pooled[row["system"]][row["metric"]]
        bucket[0] += int(row["successes"])
        bucket[1] += int(row["total"])

    def _pooled_rate(system: str, metric: str) -> float:
        successes, total = pooled[system][metric]
        return successes / total if total else 0.0

    systems = [
        row["system"] for row in table_one if row["system"] in pooled
    ]
    duplicates = [
        _pooled_rate(system, "undetected_duplicate_rate") for system in systems
    ]
    ambiguities = [
        _pooled_rate(system, "known_ambiguity_rate") for system in systems
    ]
    # A Wilson interval on the pooled counts. The per-cell CSV carries proper
    # cluster bootstrap intervals; this is a figure, and drawing the bootstrap
    # interval of a *differently pooled* quantity next to this bar would be
    # worse than drawing a simpler interval of the right one.
    lows, highs = [], []
    for system in systems:
        successes, total = pooled[system]["undetected_duplicate_rate"]
        low, high = wilson_interval(successes, total)
        rate_here = successes / total if total else 0.0
        lows.append(max(0.0, rate_here - low))
        highs.append(max(0.0, high - rate_here))

    # Draw at the IEEE single-column width so LaTeX does not scale 8 pt labels
    # down to roughly 3 pt. The system codes are defined in the paper and keep
    # all seven groups legible without discarding any plotted series.
    system_labels = {
        "AEP_FULL": "AEP",
        "B0_NAIVE_RETRY": "B0",
        "B1_LEASE_ONLY": "B1",
        "B2_CAS_ONLY": "B2",
        "B3_INTENT_NO_BARRIER": "B3",
        "B4_DURABLE_WORKFLOW": "B4",
        "B4B_DURABLE_WORKFLOW_AT_MOST_ONCE": "B4b",
    }
    figure, axis = plt.subplots(figsize=(3.5, 3.0))
    positions = range(len(systems))
    offset = 0.2
    axis.bar(
        [position - offset for position in positions],
        duplicates,
        width=0.4,
        yerr=[lows, highs],
        capsize=3,
        label="undetected duplicate",
    )
    axis.bar(
        [position + offset for position in positions],
        ambiguities,
        width=0.4,
        label="declared ambiguity",
    )
    axis.set_xticks(list(positions))
    axis.set_xticklabels(
        [system_labels.get(system, system) for system in systems], fontsize=8
    )
    axis.set_ylabel("rate per execution", fontsize=8)
    axis.tick_params(axis="y", labelsize=8)
    axis.legend(
        fontsize=8,
        ncol=1,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.01),
    )
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    path = destination / "figure-1-undetected-vs-ambiguity.pdf"
    figure.savefig(path)
    plt.close(figure)
    written.append(path)

    # -- Figure 2: undetected duplicate rate by crash point -----------------
    duplicate_cells = [
        row
        for row in per_cell
        if row["metric"] == "undetected_duplicate_rate"
        and row.get("regime") == figure_regime
    ]
    crash_points = sorted({row["crash_point"] for row in duplicate_cells})
    # Pool across response classes and keyings ON THE COUNTS.
    #
    # This previously read `(previous + rate) / 2`, which the comment beside
    # it described as weighting on counts and which does not: it is a running
    # mean whose value depends on the order rows arrive in, and which gives a
    # 10-execution cell the same influence as a 30-execution one. With three
    # response classes it also silently weights the last-seen class at 1/2 and
    # the first at 1/4. A rate over executions is a ratio of sums.
    counts: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(lambda: [0, 0])
    )
    for row in duplicate_cells:
        bucket = counts[row["system"]][row["crash_point"]]
        bucket[0] += int(row["successes"])
        bucket[1] += int(row["total"])
    by_system: dict[str, dict[str, float]] = {
        system: {
            point: (pair[0] / pair[1] if pair[1] else 0.0)
            for point, pair in points.items()
        }
        for system, points in counts.items()
    }

    if crash_points and by_system:
        # This grouped plot carries seven systems over six long crash-point
        # names, so it is a native IEEE two-column figure rather than a large
        # canvas later shrunk into one column.
        figure, axis = plt.subplots(figsize=(7.16, 3.2))
        width = 0.8 / max(1, len(by_system))
        for index, (system, values) in enumerate(sorted(by_system.items())):
            axis.bar(
                [
                    position + index * width - 0.4
                    for position in range(len(crash_points))
                ],
                [values.get(point, 0.0) for point in crash_points],
                width=width,
                label=system_labels.get(system, system),
            )
        axis.set_xticks(list(range(len(crash_points))))
        crash_point_labels = {
            "before_intent_write": "before intent write",
            "after_intent_before_barrier": "after intent / before barrier",
            "after_barrier_before_dispatch": "after barrier / before dispatch",
            "mid_dispatch": "mid-dispatch",
            "after_response_before_resolution": "after response / before resolution",
            "after_resolution_before_barrier": "after resolution / before barrier",
        }
        axis.set_xticklabels(
            [crash_point_labels.get(point, point) for point in crash_points],
            rotation=18,
            ha="right",
            fontsize=8,
        )
        axis.set_ylabel("undetected duplicate rate", fontsize=8)
        axis.tick_params(axis="y", labelsize=8)
        axis.legend(
            fontsize=8,
            ncol=4,
            loc="lower center",
            bbox_to_anchor=(0.5, 1.01),
        )
        axis.grid(axis="y", alpha=0.3)
        figure.tight_layout()
        path = destination / "figure-2-duplicates-by-crash-point.pdf"
        figure.savefig(path)
        plt.close(figure)
        written.append(path)

    return written


# ===========================================================================
# Entry point
# ===========================================================================


def render_table_one(rows: Sequence[Mapping[str, Any]]) -> str:
    header = (
        f"{'system':<22} {'runs':>5} {'exec':>6} {'undet.dup':>10} "
        f"{'95% CI':>16} {'known amb.':>11} {'lost':>7} {'Fisher p':>10}"
    )
    lines = ["", "Table 1 -- per system, pooled over every cell collected", "=" * len(header), header, "-" * len(header)]
    for row in rows:
        probability = row.get("fisher_p_vs_aep_full")
        lines.append(
            f"{row['system']:<22} {row['runs']:>5} {row['executions']:>6} "
            f"{row['undetected_duplicate_rate']:>10.4f} "
            f"{'[' + format(row['undetected_duplicate_ci_low'], '.3f') + ', ' + format(row['undetected_duplicate_ci_high'], '.3f') + ']':>16} "
            f"{row['known_ambiguity_rate']:>11.4f} "
            f"{row['lost_effect_rate']:>7.4f} "
            f"{('%.2e' % probability) if probability is not None else '--':>10}"
        )
    lines.append("=" * len(header))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute PAPER_ROADMAP.md section 3.2's metrics."
    )
    parser.add_argument("--results-root", default="experiments/results/matrix")
    parser.add_argument("--destination", default=None)
    parser.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    arguments = parser.parse_args(argv)

    results_root = Path(arguments.results_root)
    if not results_root.is_dir():
        print(f"no results directory at {results_root}")
        return 2
    destination = Path(arguments.destination or results_root / "analysis")

    runs = load_runs(results_root)
    if not runs:
        print(f"no completed runs found under {results_root}")
        return 2
    voided = load_voided_attempts(results_root)
    manifest_validation = validate_plan_manifest(results_root, runs, voided)
    destination.mkdir(parents=True, exist_ok=True)

    executions = sum(len(run.executions) for run in runs)
    coverage = {
        "runs": len(runs),
        "dataset_versions": sorted({run.dataset_version for run in runs}),
        "redis_durability_configurations": sorted(
            {run.redis_durability for run in runs}
        ),
        "executions": executions,
        "systems": sorted({run.system for run in runs}),
        "crash_points": sorted({run.crash_point for run in runs}),
        "response_classes": sorted({run.response_class for run in runs}),
        "readback_keyings": sorted({run.readback_keying for run in runs}),
        "cells": len({run.cell_key for run in runs}),
        "regimes": sorted({run.regime_label for run in runs}),
        "all_runs_used_real_sigkill": all(run.has_sigkill for run in runs),
        # Amendment E5. Three numbers, because they mean three things: how many
        # runs may contribute a duration at all, how many were caught
        # suspending, and how many were simply collected on a host that never
        # promised not to.
        "runs_with_usable_timing": sum(1 for run in runs if run.timing_is_usable),
        "runs_dropped_for_clock_suspension": sum(
            1 for run in runs if run.suspension_detected
        ),
        "runs_dropped_for_undeclared_suspend_policy": sum(
            1
            for run in runs
            if not run.suspend_disabled_declared and not run.suspension_detected
        ),
        # Amendment E2. The denominator of every overhead number.
        "crash_free_runs": sum(1 for run in runs if run.is_crash_free),
        "runs_with_a_hard_redis_kill": sum(
            1 for run in runs if run.redis_kill_point is not None
        ),
        "worst_suspension_seconds": round(
            max((run.suspension_seconds for run in runs), default=0.0), 3
        ),
        "bootstrap_seed": arguments.bootstrap_seed,
        "bootstrap_resamples": arguments.resamples,
        **manifest_validation,
    }

    table_one = build_table_one(
        runs, resamples=arguments.resamples, seed=arguments.bootstrap_seed
    )
    per_cell = build_per_cell(
        runs, resamples=arguments.resamples, seed=arguments.bootstrap_seed
    )
    comparisons = build_comparisons(
        runs, resamples=arguments.resamples, seed=arguments.bootstrap_seed
    )
    latencies = build_latencies(runs)
    timing_comparisons = build_timing_comparisons(
        runs, resamples=arguments.resamples, seed=arguments.bootstrap_seed
    )
    redis_kill = build_redis_kill_evidence(runs)
    redis_kill_comparisons = build_redis_kill_comparisons(
        runs, resamples=arguments.resamples, seed=arguments.bootstrap_seed
    )
    per_execution = build_executions_csv(runs)
    run_provenance = build_run_provenance(runs)

    written = [
        write_csv(destination / "table-1.csv", table_one),
        write_csv(destination / "per-cell-metrics.csv", per_cell),
        write_csv(destination / "comparisons-vs-aep-full.csv", comparisons),
        write_csv(destination / "latency-and-throughput.csv", latencies),
        write_csv(destination / "timing-comparisons.csv", timing_comparisons),
        write_csv(destination / "per-execution.csv", per_execution),
        write_csv(destination / "per-run-provenance.csv", run_provenance),
        write_csv(destination / "voided-attempts.csv", voided),
    ]
    if redis_kill:
        written.append(
            write_csv(destination / "redis-kill-ablation.csv", redis_kill)
        )
        written.append(
            write_csv(
                destination / "redis-kill-comparisons.csv",
                redis_kill_comparisons,
            )
        )
    for metric in RATE_METRICS:
        written.append(
            write_csv(
                destination / f"metric-{metric.replace('_', '-')}.csv",
                [row for row in per_cell if row["metric"] == metric],
            )
        )
    written.extend(write_figures(table_one, per_cell, destination))

    (destination / "coverage.json").write_text(
        json.dumps(coverage, indent=2, sort_keys=True), encoding="utf-8"
    )

    print(json.dumps(coverage, indent=2, sort_keys=True))
    print(render_table_one(table_one))
    print("")
    if not coverage["all_runs_used_real_sigkill"]:
        print(
            "WARNING: at least one run was collected on a platform without "
            "SIGKILL. Its crashes were TerminateProcess."
        )
    if len(coverage["regimes"]) > 1:
        print(
            "WARNING: Table 1 pools "
            f"{len(coverage['regimes'])} fault regimes -- "
            f"{', '.join(coverage['regimes'])}. They are different "
            "experiments, not repetitions of one: a crash-free run and a run "
            "in which every execution was killed contribute to the same rate "
            "here, and the pooled number is therefore a property of how many "
            "runs of each kind happen to have been collected. It is a coverage "
            "summary, NOT a result. Quote per-cell-metrics.csv, which is "
            "grouped by regime, system, crash point, response class and "
            "keying. The regime is in that key precisely so that the file "
            "this warning points at cannot repeat the defect the warning "
            "describes."
        )
    dropped = coverage["runs_dropped_for_clock_suspension"]
    if dropped:
        print(
            f"WARNING: {dropped} of {coverage['runs']} run(s) show a "
            f"wall-versus-monotonic divergence above "
            f"{TIMING_SUSPENSION_TOLERANCE_SECONDS}s (worst: "
            f"{coverage['worst_suspension_seconds']}s). The host suspended "
            "during them, so every wall-clock duration they contain includes "
            "the suspension. Their COUNTS are unaffected and are still in the "
            "rate metrics; their TIMINGS are excluded from the latency and "
            "throughput aggregates."
        )
    undeclared = coverage["runs_dropped_for_undeclared_suspend_policy"]
    if undeclared:
        print(
            f"E5: {undeclared} of {coverage['runs']} run(s) were collected on a "
            "host that did not declare suspend disabled. No suspension was "
            "detected in them, and that is not evidence of absence -- a host "
            "that was never idle long enough looks the same. Their COUNTS "
            "stand; NO absolute timing from them may enter the paper, and none "
            "is in the aggregates above."
        )
    if not coverage["crash_free_runs"]:
        print(
            "E2: no crash-free run has been collected, so every overhead "
            "column above is empty by construction rather than by measurement. "
            "RQ3 has no answer until the p0 regime is collected."
        )
    if redis_kill:
        print("")
        print("E1 -- the hard-Redis-kill ablation")
        print("-" * 78)
        header = (
            f"{'regime':<21} {'system':<22} {'response class':<22} "
            f"{'runs':>5} {'applied':>8} {'ambig':>6} {'canary survived':>16}"
        )
        print(header)
        for row in redis_kill:
            print(
                f"{row['regime']:<21} {row['system']:<22} "
                f"{row['response_class']:<22} {row['runs']:>5} "
                f"{row['executions_with_an_applied_effect']:>8} "
                f"{row['declared_ambiguous']:>6} "
                f"{str(row['canary_survived']) + '/' + str(row['runs']):>16}"
            )
        print(
            "\n'applied' is the discriminator: a system whose durability "
            "acknowledgement never arrived must not have dispatched.\n"
            "'canary survived' counts runs in which an UN-acknowledged write "
            "made immediately before the kill was still\nthere afterwards. It "
            "is expected to be every run: appendfsync everysec defers the "
            "fsync, not the write(2),\nso a process kill leaves the bytes in "
            "the kernel's page cache. See experiments/harness/redis_kill.py."
        )
    print("written:")
    for path in written:
        print(f"  {path}")
    print(f"  {destination / 'coverage.json'}")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    sys.exit(main())
