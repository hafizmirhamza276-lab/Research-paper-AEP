r"""WS-6's verdict: does the vendor's engine agree with our model of it?

**Written before any B5 data exists**, so nothing in it can have been chosen to
fit an observed result. `reports/phase-report-ws6-prediction-2026-09-07.md` §5.1
registered exactly this, and gave the reason: B5 is a baseline whose configuration
this author chooses, so a favourable agreement result reported by the person who
predicted it is worth nothing without the ordering. WS-4's REFUTED verdict was
credible for the same reason and no other.

It applies `1fecb1f`'s pre-registration and nothing else.

---

**ONE CORRECTION WAS MADE AFTER DATA EXISTED, on 8 September 2026.** This is the
single edit the ordering above exists to prevent, so it is recorded here in full
rather than folded into a diff.

* **What it was.** ``build_report`` mapped the frozen ``undetected_duplicate_rate``
  onto B5's ``undetected_duplicate_applications``. The frozen numerator is
  ``int(execution.is_undetected_duplicate)`` (``experiments/analyze.py:664``) --
  a per-execution 0/1 indicator -- so H1 compared a count of *applications*
  against a count of *executions*. It now reads
  ``undetected_duplicate_executions``, the field the reconciler already computes
  for exactly this. **H2 was already units-consistent and is unchanged.**
* **What the script said before.** Against the 2026-09-08 session (`0c6bcf4`),
  H1 read `DISAGREES` at both response classes: B5 `0.4000 [0.4000,0.4000]` vs
  frozen `0.9333 [0.9000,1.0000]`, and B5 `0.4107 [0.4000,0.4214]` vs frozen
  `0.9667 [0.9000,1.0000]`. Recorded verbatim in
  ``reports/raw/ws6-b5-s1-2026-09-08/agreement.txt``, which is kept.
* **What it says after.** Not yet run against any data. The corrected mapping is
  committed *before* the collection it will read, and the session it would
  change was collected by a harness now known to be defective in a second,
  independent way, so re-reading it would answer nothing.
* **Why this is not fitting the script to the result.** The mismatch was found
  by reading ``analyze.py``'s numerator definitions against this file's mapping
  while establishing why three of four B5 intervals were zero-width -- a
  question about the *estimator*, not about the verdict. The correction moves
  H1's B5 numerator **down** (3 where applications were 4 in 55 of 120 runs), so
  it widens the gap that produced `DISAGREES` rather than narrowing it. It was
  not made because the result was unwelcome; it makes an unwelcome result
  slightly more unwelcome.
* **Recorded in** ``reports/phase-report-ws6-determinism-2026-09-08.md`` §6 and
  re-registered in ``reports/phase-report-ws6-prediction-corrected-2026-09-08.md``.

**The three hypotheses** (pre-registration §1):

* **H1** -- at the crash points B4 and B5 can *both* be cut at, B5 reproduces
  B4's undetected-duplicate rate, run-clustered intervals overlapping.
* **H2** -- the same for B5b against B4b's lost-effect rate.
* **H3** -- neither B5 nor B5b declares ambiguity in any run. Predicted at
  **exactly zero**, because it is structural: the fact required (did the provider
  apply the effect?) is not in the engine's history and cannot be put there. One
  declared ambiguity refutes the paper's characterisation of durable-execution
  engines and is a finding, not noise.

**Where the frozen rates are read from, rather than restated.**
``experiments/results/matrix/analysis/per-cell-metrics.csv``, the long-form file
keyed by ``(metric, regime, system, crash_point, response_class,
readback_keying)`` and already carrying ``rate``, ``ci_low``, ``ci_high``,
``runs`` and ``clusters`` -- the run-clustered intervals this comparison needs,
computed by the same estimator, not recomputed here from a number typed into a
docstring. The metrics used are ``undetected_duplicate_rate`` (H1),
``lost_effect_rate`` (H2) and ``known_ambiguity_rate`` (H3).
``analysis/table-1.csv`` is a **banned** source (Session 3B §F2) and is never
read.

**Why a cell can agree and still not be reportable.** Two conditions in the
pre-registration make an agreement mean less than it looks, and a verdict that
could only say AGREES/DISAGREES would hide both:

* ``PENDING_AT_DEADLINE`` above **20%** of a cell's runs makes that cell
  **uninformative** (§3.3). H1/H2 are not evaluated on it. The fix is a design
  change to the timeout, re-registered -- never a re-reading of data in hand.
* **B5 has no ``after_intent_before_barrier`` point at all** (`B5_SEMANTICS.md`
  §2.3): in Temporal the worker issues an RPC and the server persists it
  transactionally, so no worker-side pre-acknowledgement window exists to be cut
  in. B4 and B4b **have frozen cells there on all three response classes**, so
  this is a hole in B5 where B4 has numbers. Any summary must say the cell is
  ABSENT rather than print a complete-looking table with it missing.

:func:`classify_cell` is where the numbers and those conditions are combined, and
it is the reason this file exists rather than an interval-overlap one-liner.

**Voids are instrument failures, not measurements.** ``VOID_INJECTOR_*``,
``VOID_SUPERVISOR_NEVER_RESPAWNED`` and ``VOID_WORKER_NEVER_READY`` are excluded
from every rate and reported separately with counts. A void silently counted as
"no duplicate" would make B5 look better than B4 for an instrument reason, which
is the failure mode `experiments/baselines/b5_temporal/gate.py` was built to stop
and which this script must not reintroduce one layer up.

**Unit of analysis: the run** (`docs/26` §3 rule 6), via
``experiments.statistics.cluster_bootstrap_proportion`` -- the same estimator
that produced the frozen intervals.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.statistics import (  # noqa: E402
    DEFAULT_BOOTSTRAP_SEED,
    DEFAULT_RESAMPLES,
    cluster_bootstrap_proportion,
)

# ------------------------------------------------------------------ constants
#
# Fixed HERE, before any B5 data exists.

#: Above this fraction of a cell's non-void runs, the cell is uninformative
#: (pre-registration §3.3). Not a tuning knob: it is the line past which a
#: "no duplicate" result is an artefact of the observation window.
PENDING_UNINFORMATIVE_ABOVE = 0.20

#: H3 is predicted at exactly zero and is structural, so any non-zero count
#: refutes it. There is no tolerance band and inventing one later would be
#: fitting the threshold to the data.
AMBIGUITY_REFUTES_AT_OR_ABOVE = 1

#: The roadmap point B5 cannot be cut at. Read as a constant rather than
#: inferred from an empty cell: an absent point and an uncollected one must not
#: render the same.
ABSENT_IN_B5 = "after_intent_before_barrier"

#: Frozen source, and the banned one.
FROZEN_PER_CELL = Path("experiments/results/matrix/analysis/per-cell-metrics.csv")
BANNED_SOURCE = "table-1.csv"

B5, B5B = "B5_TEMPORAL", "B5B_TEMPORAL_AT_MOST_ONCE"
B4, B4B = "B4_DURABLE_WORKFLOW", "B4B_DURABLE_WORKFLOW_AT_MOST_ONCE"

#: hypothesis -> (B5 arm, frozen arm, metric in the frozen file)
HYPOTHESES = {
    "H1": (B5, B4, "undetected_duplicate_rate"),
    "H2": (B5B, B4B, "lost_effect_rate"),
}


class Reading(str, Enum):
    """What a cell says. Deliberately more than AGREES/DISAGREES."""

    AGREES = "AGREES"
    DISAGREES = "DISAGREES"
    #: Absent in B5 by construction. Not a failure, and not a gap in collection.
    NOT_TESTABLE_ABSENT_IN_B5 = "NOT_TESTABLE_ABSENT_IN_B5"
    #: Too many PENDING_AT_DEADLINE runs. The arms may or may not agree; this
    #: cell cannot say which.
    UNINFORMATIVE_PENDING = "UNINFORMATIVE_PENDING"
    #: Nothing left after voids were excluded.
    NO_DATA_AFTER_VOIDS = "NO_DATA_AFTER_VOIDS"
    #: The frozen file has no such cell to compare against.
    NO_FROZEN_COMPARATOR = "NO_FROZEN_COMPARATOR"


VOID_PREFIX = "VOID_"
PENDING = "PENDING_AT_DEADLINE"


@dataclass
class Interval:
    point: float
    low: float
    high: float

    def overlaps(self, other: "Interval") -> bool:
        return self.low <= other.high and other.low <= self.high

    def as_dict(self) -> dict:
        return {"rate": self.point, "ci_low": self.low, "ci_high": self.high}


@dataclass
class CellReading:
    hypothesis: str
    crash_point: str
    response_class: str
    reading: Reading
    reasons: list[str] = field(default_factory=list)
    b5: Interval | None = None
    frozen: Interval | None = None
    runs_total: int = 0
    runs_void: int = 0
    runs_pending: int = 0
    voids_by_verdict: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "hypothesis": self.hypothesis,
            "crash_point": self.crash_point,
            "response_class": self.response_class,
            "reading": self.reading.value,
            "reasons": self.reasons,
            "b5": self.b5.as_dict() if self.b5 else None,
            "frozen": self.frozen.as_dict() if self.frozen else None,
            "runs_total": self.runs_total,
            "runs_void": self.runs_void,
            "runs_pending": self.runs_pending,
            "voids_by_verdict": self.voids_by_verdict,
        }


# ----------------------------------------------------------------- extraction


def read_frozen(root: Path) -> dict[tuple[str, str, str, str], Interval]:
    """Frozen B4/B4b rates and their run-clustered intervals.

    Keyed ``(metric, system, crash_point, response_class)``. Read from the
    long-form per-cell file, which already carries the intervals; nothing is
    recomputed and no rate is restated in this module.
    """
    path = root / FROZEN_PER_CELL
    if not path.is_file():
        raise SystemExit(f"no frozen per-cell metrics at {path}")
    if BANNED_SOURCE in str(path):
        raise SystemExit(f"{BANNED_SOURCE} is a banned source (Session 3B F2)")
    out: dict[tuple[str, str, str, str], Interval] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (
                row["metric"], row["system"], row["crash_point"],
                row["response_class"],
            )
            try:
                out[key] = Interval(
                    float(row["rate"]), float(row["ci_low"]), float(row["ci_high"])
                )
            except (TypeError, ValueError):
                continue
    return out


def read_b5_runs(session: Path) -> list[dict]:
    """One record per B5 run, with its gate verdict.

    Expects ``b5-runs.jsonl``: the collection writes the gate's verdict beside
    each run precisely so this script never has to re-derive it.
    """
    path = session / "b5-runs.jsonl"
    if not path.is_file():
        raise SystemExit(f"no b5-runs.jsonl at {path}")
    runs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            runs.append(json.loads(line))
    return runs


def cell_interval(runs: list[dict], metric_field: str) -> Interval:
    """Run-clustered bootstrap over the non-void runs of one cell."""
    clusters = [
        (int(run.get(metric_field, 0)), int(run.get("executions", 0)))
        for run in runs
    ]
    result = cluster_bootstrap_proportion(
        clusters, resamples=DEFAULT_RESAMPLES, seed=DEFAULT_BOOTSTRAP_SEED
    )
    return Interval(result.point, result.low, result.high)


# ------------------------------------------------------------------- the rule


def classify_cell(
    *,
    hypothesis: str,
    crash_point: str,
    response_class: str,
    runs: list[dict],
    frozen: Interval | None,
    metric_field: str,
) -> CellReading:
    """Agreement AND the reasons, with the flagged conditions kept visible.

    Order matters. Absence is decided before anything is computed, voids are
    removed before any rate exists, and the uninformative test runs before
    overlap -- so a cell can never be reported as AGREES on a basis the
    pre-registration already said would not support one.
    """
    reading = CellReading(hypothesis, crash_point, response_class,
                          Reading.AGREES)
    reading.runs_total = len(runs)

    # 1. Absent by construction, before any arithmetic.
    if crash_point == ABSENT_IN_B5:
        reading.reading = Reading.NOT_TESTABLE_ABSENT_IN_B5
        reading.reasons.append(
            f"B5 has no {ABSENT_IN_B5!r} position: the worker issues an RPC and "
            f"the server persists it transactionally, so there is no worker-side "
            f"window between the write and its acknowledgement "
            f"(B5_SEMANTICS.md 2.3). B4 and B4b HAVE frozen cells here, so this "
            f"is a hole in B5 where B4 has numbers -- not a shared absence."
        )
        return reading

    # 2. Voids are instrument failures. Out of the rate, and counted.
    void_runs = [r for r in runs if str(r.get("verdict", "")).startswith(VOID_PREFIX)]
    live = [r for r in runs if not str(r.get("verdict", "")).startswith(VOID_PREFIX)]
    reading.runs_void = len(void_runs)
    for run in void_runs:
        verdict = str(run["verdict"])
        reading.voids_by_verdict[verdict] = (
            reading.voids_by_verdict.get(verdict, 0) + 1
        )
    if void_runs:
        reading.reasons.append(
            f"{len(void_runs)}/{len(runs)} runs voided as instrument failures "
            f"and excluded from the rate: {reading.voids_by_verdict}"
        )
    if not live:
        reading.reading = Reading.NO_DATA_AFTER_VOIDS
        reading.reasons.append("no runs survived void exclusion")
        return reading

    # 3. Pending share, over the runs that are measurements.
    pending = [r for r in live if str(r.get("verdict")) == PENDING]
    reading.runs_pending = len(pending)
    share = len(pending) / len(live)
    if share > PENDING_UNINFORMATIVE_ABOVE:
        reading.reading = Reading.UNINFORMATIVE_PENDING
        reading.reasons.append(
            f"{len(pending)}/{len(live)} = {share:.0%} of non-void runs ended "
            f"PENDING_AT_DEADLINE, above the pre-registered {PENDING_UNINFORMATIVE_ABOVE:.0%}. "
            f"The engine had not decided, so this cell cannot say whether the "
            f"arms agree. The fix is a timeout change, re-registered -- not a "
            f"re-reading of these runs."
        )
        return reading
    if pending:
        reading.reasons.append(
            f"{len(pending)}/{len(live)} = {share:.0%} PENDING_AT_DEADLINE, "
            f"within the {PENDING_UNINFORMATIVE_ABOVE:.0%} bound"
        )

    # 4. Now, and only now, the comparison.
    reading.b5 = cell_interval(live, metric_field)
    if frozen is None:
        reading.reading = Reading.NO_FROZEN_COMPARATOR
        reading.reasons.append(
            "the frozen per-cell file has no matching B4/B4b cell to compare "
            "against; B5's own rate is reported and nothing is concluded"
        )
        return reading
    reading.frozen = frozen
    if reading.b5.overlaps(frozen):
        reading.reading = Reading.AGREES
        reading.reasons.append(
            f"B5 {reading.b5.point:.4f} [{reading.b5.low:.4f},{reading.b5.high:.4f}] "
            f"overlaps frozen {frozen.point:.4f} [{frozen.low:.4f},{frozen.high:.4f}]"
        )
    else:
        reading.reading = Reading.DISAGREES
        reading.reasons.append(
            f"B5 {reading.b5.point:.4f} [{reading.b5.low:.4f},{reading.b5.high:.4f}] "
            f"does NOT overlap frozen {frozen.point:.4f} "
            f"[{frozen.low:.4f},{frozen.high:.4f}] -- B4 would then be an "
            f"artefact of our model rather than of event-sourced re-execution, "
            f"and every B4 claim must be re-scoped"
        )
    return reading


def classify_h3(runs: list[dict]) -> tuple[str, list[str]]:
    """H3: neither arm declares ambiguity. Predicted at exactly zero."""
    live = [r for r in runs if not str(r.get("verdict", "")).startswith(VOID_PREFIX)]
    declared = sum(int(r.get("declared_ambiguous", 0)) for r in live)
    if declared >= AMBIGUITY_REFUTES_AT_OR_ABOVE:
        return "REFUTED", [
            f"{declared} declared ambiguity/ambiguities across {len(live)} "
            f"non-void runs. H3 predicted exactly zero and is structural, so "
            f"this refutes the paper's characterisation of durable-execution "
            f"engines. It is the most important finding of WS-6 if it stands."
        ]
    return "HELD", [
        f"0 declared ambiguities across {len(live)} non-void runs, as predicted"
    ]


# ------------------------------------------------------------------ reporting


def build_report(session: Path, repo: Path) -> dict:
    frozen = read_frozen(repo)
    runs = read_b5_runs(session)

    by_cell: dict[tuple[str, str, str], list[dict]] = {}
    for run in runs:
        key = (str(run["system"]), str(run.get("crash_point", "none")),
               str(run.get("response_class", "")))
        by_cell.setdefault(key, []).append(run)

    readings: list[CellReading] = []
    for hypothesis, (b5_arm, frozen_arm, metric) in HYPOTHESES.items():
        # CORRECTED 2026-09-08, AFTER data existed. See the header note.
        #
        # The frozen numerators in analyze.py:664-670 are per-execution 0/1
        # indicators -- int(execution.is_undetected_duplicate) and
        # int(execution.is_lost_effect) -- so both sides must count EXECUTIONS.
        #
        #   H1 was wrong: it read undetected_duplicate_APPLICATIONS, a count of
        #      applications, against B4's count of executions that had any
        #      duplicate. An execution with three duplicate applications
        #      contributes 3 on one side and 1 on the other.
        #   H2 was already right and is UNCHANGED: lost_effect_executions is
        #      already the executions-based field.
        metric_field = {
            "undetected_duplicate_rate": "undetected_duplicate_executions",
            "lost_effect_rate": "lost_effect_executions",
        }[metric]
        for (system, crash_point, response_class), cell_runs in sorted(by_cell.items()):
            if system != b5_arm:
                continue
            readings.append(
                classify_cell(
                    hypothesis=hypothesis,
                    crash_point=crash_point,
                    response_class=response_class,
                    runs=cell_runs,
                    frozen=frozen.get(
                        (metric, frozen_arm, crash_point, response_class)
                    ),
                    metric_field=metric_field,
                )
            )

    # The absent point is reported even when the collection produced no rows
    # for it, so the table cannot look complete by omission.
    covered = {(r.hypothesis, r.crash_point, r.response_class) for r in readings}
    for hypothesis in HYPOTHESES:
        for response_class in sorted(
            {str(r.get("response_class", "")) for r in runs}
        ):
            key = (hypothesis, ABSENT_IN_B5, response_class)
            if key not in covered:
                readings.append(
                    classify_cell(
                        hypothesis=hypothesis, crash_point=ABSENT_IN_B5,
                        response_class=response_class, runs=[], frozen=None,
                        metric_field="",
                    )
                )

    h3_verdict, h3_reasons = classify_h3(runs)
    counts: dict[str, int] = {}
    for reading in readings:
        counts[reading.reading.value] = counts.get(reading.reading.value, 0) + 1
    voids: dict[str, int] = {}
    for run in runs:
        verdict = str(run.get("verdict", ""))
        if verdict.startswith(VOID_PREFIX):
            voids[verdict] = voids.get(verdict, 0) + 1

    return {
        "session": session.name,
        "cells": [r.as_dict() for r in readings],
        "cell_counts": counts,
        "h3": {"verdict": h3_verdict, "reasons": h3_reasons},
        "voids_by_verdict": voids,
        "voided_runs": sum(voids.values()),
        "total_runs": len(runs),
        "frozen_source": str(FROZEN_PER_CELL),
    }


def render(report: dict) -> str:
    lines = [f"=== WS-6 B5 agreement: {report['session']} ===", ""]
    lines.append(f"frozen comparator: {report['frozen_source']}")
    lines.append(
        f"runs: {report['total_runs']} total, {report['voided_runs']} voided "
        f"as instrument failures and excluded from every rate"
    )
    if report["voids_by_verdict"]:
        for verdict, count in sorted(report["voids_by_verdict"].items()):
            lines.append(f"    {count:4d}  {verdict}")
    lines.append("")
    lines.append("--- per cell ---")
    for cell in report["cells"]:
        lines.append(
            f"  {cell['hypothesis']}  {cell['crash_point']:32s} "
            f"{cell['response_class']:24s} {cell['reading']}"
        )
        for reason in cell["reasons"]:
            lines.append(f"        {reason}")
    lines.append("")
    lines.append("--- H3, non-escalation ---")
    lines.append(f"  {report['h3']['verdict']}")
    for reason in report["h3"]["reasons"]:
        lines.append(f"    - {reason}")
    lines.append("")
    lines.append("--- summary ---")
    for reading, count in sorted(report["cell_counts"].items()):
        lines.append(f"  {count:4d}  {reading}")
    absent = report["cell_counts"].get(Reading.NOT_TESTABLE_ABSENT_IN_B5.value, 0)
    if absent:
        lines.append("")
        lines.append(
            f"  {absent} cell(s) are ABSENT IN B5, not missing from the "
            f"collection. No agreement claim covers them, and the comparison "
            f"is not complete."
        )
    uninformative = report["cell_counts"].get(Reading.UNINFORMATIVE_PENDING.value, 0)
    if uninformative:
        lines.append(
            f"  {uninformative} cell(s) are UNINFORMATIVE on the pre-registered "
            f"pending bound and are NOT evidence of agreement."
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--repo", default=str(REPO))
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    report = build_report(Path(arguments.session), Path(arguments.repo))
    print(render(report), end="")
    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
