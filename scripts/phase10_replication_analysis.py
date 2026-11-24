#!/usr/bin/env python3
"""Is the container runtime a confound? The replication's analysis, pinned.

Phase 10, step 8. This script is committed **before any Phase 10 run exists**,
because an analysis chosen after seeing the data is not an analysis. It is named
in `reports/phase-report-10-prediction-2026-09-02.md` and nothing about it
changes once data arrives.

**What it compares.** The frozen `matrix` cell -- AEP-full x NO_READBACK
(`ledger_postings`) x the `session-3` crash-always regime -- against the same
cell re-collected under the native Docker Engine, on two filesystems:

  * the **ext4 arm**, collected on the distro's own disk. This matches where the
    frozen cell was collected (`provenance.py`'s docstring: "the paper's cell was
    collected in the WSL-native tree on ext4"), so the *only* difference from the
    frozen cell is the container runtime. This is the primary test.
  * the **drvfs arm**, collected through `/mnt/d` on 9p. Phase 8.1 measured an
    event-log append costing about forty times more there. This arm separates
    the filesystem from the runtime instead of confounding them.

**Why a difference and not a containment.** The frozen cell's own run-clustered
interval on the one informative sub-cell is [0.0, 0.6]. Almost any outcome falls
inside it, so "the replication agrees if it lands in the frozen interval" is a
test that cannot fail. The criterion here is therefore the *difference* between
arm and frozen, with its own run-clustered interval, against a margin declared
in advance.

**The margin is a stipulation and is labelled as one.** +/-15 percentage points.
It is not derived from a power calculation; it is chosen, as Section VI-C1's
equivalence margin is chosen, and the reasoning is in the prediction file. A
margin tighter than the frozen cell's own resolution would be a margin the
design cannot support.

**The half-width rule exists because Phase 9C's failure was exactly this shape.**
An interval too wide to exclude anything is not agreement. If the half-width of
the difference interval exceeds the margin, the verdict is INCONCLUSIVE --
UNDERPOWERED, in those words, and never "agrees".

Usage::

    python scripts/phase10_replication_analysis.py \\
        --frozen experiments/results/matrix/analysis/per-execution.csv \\
        --arm ext4=<root>/analysis/per-execution.csv \\
        --arm drvfs=<root>/analysis/per-execution.csv \\
        --output reports/raw/phase10-replication-analysis.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.statistics import (  # noqa: E402
    DEFAULT_BOOTSTRAP_SEED,
    DEFAULT_RESAMPLES,
    cluster_bootstrap_proportion,
    proportion,
    stratified_cluster_bootstrap_difference,
)

# --------------------------------------------------------------------------
# The cell. Fixed here so that no invocation can quietly select a different one.
# --------------------------------------------------------------------------
SYSTEM = "AEP_FULL"
RESPONSE_CLASS = "NO_READBACK"
KEYING = "CALLER_REFERENCE"

#: The crash-always regime, under every label it has ever been written with.
#:
#: **Recorded as a post-data correction, not applied silently** (rule 4). This
#: script was committed before collection with a single literal `"(session-3)"`,
#: which is what the tracked `experiments/results/matrix/analysis/per-execution.csv`
#: (committed 2026-08-10, `831c796`) contains. A freshly generated
#: per-execution.csv writes `"crashed"` for the same regime, because
#: `analyze.py:406` maps the empty regime key to that display label. The two are
#: the same condition -- `analyze.py:601-616` derives the key as `""` when
#: `crash_probability == 1.0` and the run performs no Redis kill -- so joining
#: frozen and new rows on the label alone silently selects **zero** rows from
#: the new arm. That is what happened on the first run of this analysis.
#:
#: The correction is a label alias and nothing else. It does not touch the
#: estimand, the unit of analysis, the margin, the resamples, the seed or the
#: verdict rule, and it cannot move a verdict in either direction: before it,
#: the new arm contributed no rows at all.
REGIMES = frozenset({"(session-3)", "crashed", ""})

#: The six crash points of the matched arms.
CRASH_POINTS = (
    "before_intent_write",
    "after_intent_before_barrier",
    "mid_dispatch",
    "after_response_before_resolution",
    "after_resolution_before_barrier",
    "after_barrier_before_dispatch",
)

#: The one sub-cell with interior variance, and therefore the only one whose
#: agreement carries information. The frozen value is 10/30 across 3 runs; the
#: other five are 0/30 or 30/30 and would agree trivially.
INFORMATIVE_CRASH_POINT = "after_resolution_before_barrier"

#: Declared in advance. A STIPULATION, not a derivation. See the module
#: docstring and the prediction file.
CONFOUND_MARGIN = 0.15

#: The metrics compared. `known_ambiguity` is the primary; the rest are carried
#: because a runtime that changed a duplicate or lost-effect rate would be a
#: far more serious finding than one that moved an ambiguity rate.
METRICS = {
    "known_ambiguity_rate": lambda row: row["outcome_class"] == "DECLARED_AMBIGUOUS",
    "undetected_duplicate_rate": lambda row: row["undetected_duplicate"].strip().lower()
    in {"1", "true"},
    "lost_effect_rate": lambda row: row["lost_effect"].strip().lower() in {"1", "true"},
    "unverified_failure_rate": lambda row: row["outcome_class"] == "UNVERIFIED_FAILURE",
    "recovery_success_rate": lambda row: row["outcome_class"]
    in {"CONFIRMED_APPLIED", "CONFIRMED_NOT_APPLIED", "DECLARED_AMBIGUOUS"},
}


def load(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def select(rows: list[dict[str, str]], crash_points: tuple[str, ...]
           ) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("system") == SYSTEM
        and row.get("response_class") == RESPONSE_CLASS
        and row.get("regime") in REGIMES
        and row.get("readback_keying") == KEYING
        and row.get("crash_point") in crash_points
    ]


def clusters_by_stratum(
    rows: list[dict[str, str]], metric: str
) -> dict[str, list[tuple[int, int]]]:
    """One (successes, total) pair per run, grouped by crash point.

    The run is the unit of analysis. Grouping by crash point keeps the matched
    arms' fixed crash-point mix intact when the difference is bootstrapped, so
    a resample cannot silently reweight the cells.
    """
    predicate = METRICS[metric]
    per_run: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row in rows:
        per_run[(row["crash_point"], row["run_id"])].append(1 if predicate(row) else 0)
    strata: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for (crash_point, _run), flags in sorted(per_run.items()):
        strata[crash_point].append((sum(flags), len(flags)))
    return dict(strata)


def describe(rows: list[dict[str, str]], metric: str, *, resamples: int, seed: int
             ) -> dict[str, Any]:
    strata = clusters_by_stratum(rows, metric)
    flat = [pair for pairs in strata.values() for pair in pairs]
    successes = sum(pair[0] for pair in flat)
    total = sum(pair[1] for pair in flat)
    record: dict[str, Any] = {
        "successes": successes,
        "total": total,
        "rate": proportion(successes, total),
        "runs": len(flat),
        "crash_points": sorted(strata),
    }
    if flat:
        interval = cluster_bootstrap_proportion(
            flat, resamples=resamples, seed=seed, confidence=0.95
        )
        record["ci_low"] = interval.low
        record["ci_high"] = interval.high
    return record


def verdict_for(low: float, high: float, margin: float) -> str:
    """The rule, applied. Declared before data existed; not negotiable after."""
    half_width = (high - low) / 2.0
    if half_width > margin:
        return "INCONCLUSIVE -- UNDERPOWERED"
    if low > -margin and high < margin:
        return "NOT A CONFOUND at this margin"
    if low >= margin or high <= -margin:
        return "CONFOUND"
    return "INCONCLUSIVE -- INTERVAL STRADDLES THE MARGIN"


def compare(
    arm_rows: list[dict[str, str]],
    reference_rows: list[dict[str, str]],
    metric: str,
    *,
    resamples: int,
    seed: int,
    margin: float,
) -> dict[str, Any]:
    arm = clusters_by_stratum(arm_rows, metric)
    reference = clusters_by_stratum(reference_rows, metric)
    shared = sorted(set(arm) & set(reference))
    if not shared:
        return {"error": "no crash point is present in both arms"}
    dropped = sorted((set(arm) | set(reference)) - set(shared))
    difference = stratified_cluster_bootstrap_difference(
        {key: arm[key] for key in shared},
        {key: reference[key] for key in shared},
        resamples=resamples,
        seed=seed,
        confidence=0.95,
    )
    record: dict[str, Any] = {
        "point": difference.point,
        "ci_low": difference.low,
        "ci_high": difference.high,
        "half_width": (difference.high - difference.low) / 2.0,
        "confidence": difference.confidence,
        "margin": margin,
        "within_margin": difference.within(margin),
        "arm_clusters": difference.system_clusters,
        "reference_clusters": difference.reference_clusters,
        "strata": shared,
        "verdict": verdict_for(difference.low, difference.high, margin),
    }
    if dropped:
        # Never silently: a crash point present in one arm and not the other is
        # a coverage gap, and a comparison that quietly narrowed to the overlap
        # would read as complete.
        record["crash_points_dropped_not_in_both"] = dropped
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--frozen",
        type=Path,
        default=REPO_ROOT / "experiments/results/matrix/analysis/per-execution.csv",
    )
    parser.add_argument(
        "--arm",
        dest="arms",
        action="append",
        required=True,
        metavar="LABEL=path/to/per-execution.csv",
    )
    parser.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    parser.add_argument("--margin", type=float, default=CONFOUND_MARGIN)
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args(argv)

    frozen_rows = load(arguments.frozen)
    arms: dict[str, list[dict[str, str]]] = {}
    for specification in arguments.arms:
        label, separator, path = specification.partition("=")
        if not separator:
            print(f"REFUSING: --arm {specification!r} is not LABEL=PATH", file=sys.stderr)
            return 2
        arms[label.strip()] = load(Path(path.strip()))

    payload: dict[str, Any] = {
        "analysis": "phase10-replication/1",
        "cell": {
            "system": SYSTEM,
            "response_class": RESPONSE_CLASS,
            "regime_labels_accepted": sorted(REGIMES),
            "readback_keying": KEYING,
            "crash_points": list(CRASH_POINTS),
            "informative_crash_point": INFORMATIVE_CRASH_POINT,
        },
        "unit_of_analysis": "the run",
        "margin": arguments.margin,
        "margin_is": "a stipulation declared before collection, not a derivation",
        "resamples": arguments.resamples,
        "bootstrap_seed": arguments.bootstrap_seed,
        "frozen_source": str(arguments.frozen),
        "matched": {},
        "informative_cell": {},
        "arm_vs_arm": {},
    }

    # ---------------------------------------------------- the matched arms
    frozen_matched = select(frozen_rows, CRASH_POINTS)
    for metric in METRICS:
        entry: dict[str, Any] = {
            "frozen": describe(
                frozen_matched, metric,
                resamples=arguments.resamples, seed=arguments.bootstrap_seed,
            )
        }
        for label, rows in arms.items():
            selected = select(rows, CRASH_POINTS)
            entry[label] = describe(
                selected, metric,
                resamples=arguments.resamples, seed=arguments.bootstrap_seed,
            )
            entry[f"{label}_vs_frozen"] = compare(
                selected, frozen_matched, metric,
                resamples=arguments.resamples, seed=arguments.bootstrap_seed,
                margin=arguments.margin,
            )
        payload["matched"][metric] = entry

    # -------------------------------------- the powered, informative sub-cell
    only = (INFORMATIVE_CRASH_POINT,)
    frozen_informative = select(frozen_rows, only)
    for metric in METRICS:
        entry = {
            "frozen": describe(
                frozen_informative, metric,
                resamples=arguments.resamples, seed=arguments.bootstrap_seed,
            )
        }
        for label, rows in arms.items():
            selected = select(rows, only)
            entry[label] = describe(
                selected, metric,
                resamples=arguments.resamples, seed=arguments.bootstrap_seed,
            )
            entry[f"{label}_vs_frozen"] = compare(
                selected, frozen_informative, metric,
                resamples=arguments.resamples, seed=arguments.bootstrap_seed,
                margin=arguments.margin,
            )
        payload["informative_cell"][metric] = entry

    # ------------------------------------------- ext4 against drvfs, directly
    labels = sorted(arms)
    if len(labels) == 2:
        first, second = labels
        for scope, crash_points in (
            ("matched", CRASH_POINTS), ("informative_cell", only)
        ):
            payload["arm_vs_arm"][scope] = {
                metric: compare(
                    select(arms[first], crash_points),
                    select(arms[second], crash_points),
                    metric,
                    resamples=arguments.resamples,
                    seed=arguments.bootstrap_seed,
                    margin=arguments.margin,
                )
                for metric in METRICS
            }
            payload["arm_vs_arm"][f"{scope}_direction"] = f"{first} minus {second}"

    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(text + "\n", encoding="utf-8")

    # A summary a human reads, after the JSON a machine reads.
    print("\n" + "=" * 78, file=sys.stderr)
    print("PRIMARY: known_ambiguity_rate on "
          f"{INFORMATIVE_CRASH_POINT}, powered cell", file=sys.stderr)
    print("=" * 78, file=sys.stderr)
    informative = payload["informative_cell"]["known_ambiguity_rate"]
    frozen = informative["frozen"]
    print(f"  frozen        {frozen['successes']}/{frozen['total']} "
          f"= {frozen['rate']:.4f} over {frozen['runs']} run(s)", file=sys.stderr)
    for label in arms:
        arm = informative[label]
        comparison = informative[f"{label}_vs_frozen"]
        print(f"  {label:12s}  {arm['successes']}/{arm['total']} "
              f"= {arm['rate']:.4f} over {arm['runs']} run(s)", file=sys.stderr)
        if "error" not in comparison:
            print(f"                difference {comparison['point']:+.4f} "
                  f"95% CI [{comparison['ci_low']:+.4f}, {comparison['ci_high']:+.4f}] "
                  f"half-width {comparison['half_width']:.4f}", file=sys.stderr)
            print(f"                VERDICT: {comparison['verdict']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
