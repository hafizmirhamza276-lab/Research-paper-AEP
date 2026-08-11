"""Rebuild regime-labelled comparison rows from tracked analysis products.

The full raw-run archive is intentionally not tracked. This module therefore
provides a reproducible correction path for the derived comparison artifact:
aggregate counts come from ``per-cell-metrics.csv`` and the declared-ambiguity
run clusters come from ``per-execution.csv``. It never edits either input.

Usage::

    python -m experiments.rebuild_comparisons \
        --analysis experiments/results/matrix/analysis \
        --output experiments/results/matrix/analysis/comparisons-vs-aep-full.csv \
        --update-manifest experiments/results/matrix/SHA256SUMS
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from experiments.analyze import (
    AMBIGUITY_DIFFERENCE_CONFIDENCE,
    AMBIGUITY_EQUIVALENCE_MARGIN,
    RATE_METRICS,
    REFERENCE_SYSTEM,
)
from experiments.statistics import (
    compare_rates,
    stratified_cluster_bootstrap_difference,
)

DEFAULT_RESAMPLES = 10_000
DEFAULT_SEED = 20260806
LEGACY_CRASHED_REGIME = "(session-3)"
CRASHED_REGIME = "crashed"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _normalize_legacy_regimes(
    per_cell: Sequence[Mapping[str, str]],
    per_execution: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Name the legacy Session-3 regime from execution-level evidence.

    The old tracked derivatives called the every-execution-crashed regime
    ``(session-3)``. We do not infer it from row position: every execution
    carrying that legacy label must declare ``crashed=1``. The normalized
    copies feed the new artifact; the frozen inputs remain byte-identical.
    """
    legacy_executions = [
        row for row in per_execution if row.get("regime") == LEGACY_CRASHED_REGIME
    ]
    legacy_cells = [
        row for row in per_cell if row.get("regime") == LEGACY_CRASHED_REGIME
    ]
    if legacy_cells and not legacy_executions:
        raise ValueError("legacy Session-3 cells lack execution-level regime evidence")
    if any(row.get("crashed") != "1" for row in legacy_executions):
        raise ValueError("legacy Session-3 regime contains a non-crashed execution")

    def normalized(rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
        copies = [dict(row) for row in rows]
        for row in copies:
            if row.get("regime") == LEGACY_CRASHED_REGIME:
                row["regime"] = CRASHED_REGIME
        return copies

    return normalized(per_cell), normalized(per_execution)


def _aggregate_cells(
    rows: Iterable[Mapping[str, str]],
) -> dict[tuple[str, str, str], dict[str, int]]:
    aggregates: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {"successes": 0, "total": 0, "runs": 0}
    )
    for row in rows:
        metric = row["metric"]
        if metric not in RATE_METRICS:
            continue
        regime = row.get("regime", "")
        if not regime:
            raise ValueError("per-cell comparison source has an empty regime label")
        bucket = aggregates[(regime, row["system"], metric)]
        bucket["successes"] += int(row["successes"])
        bucket["total"] += int(row["total"])
        bucket["runs"] += int(row["runs"])
    return dict(aggregates)


def _ambiguity_clusters(
    rows: Iterable[Mapping[str, str]],
) -> dict[tuple[str, str], dict[str, list[tuple[int, int]]]]:
    by_run: dict[tuple[str, str, str, str], list[int]] = defaultdict(
        lambda: [0, 0]
    )
    for row in rows:
        regime = row.get("regime", "")
        if not regime:
            raise ValueError("per-execution comparison source has an empty regime label")
        stratum = "|".join(
            (
                row["crash_point"],
                row["response_class"],
                row["readback_keying"],
            )
        )
        bucket = by_run[(regime, row["system"], stratum, row["run_id"])]
        bucket[0] += int(row["outcome_class"] == "DECLARED_AMBIGUOUS")
        bucket[1] += 1

    clusters: dict[
        tuple[str, str], dict[str, list[tuple[int, int]]]
    ] = defaultdict(lambda: defaultdict(list))
    for (regime, system, stratum, _run_id), (successes, total) in by_run.items():
        clusters[(regime, system)][stratum].append((successes, total))
    return {key: dict(value) for key, value in clusters.items()}


def build_rows(
    per_cell: Sequence[Mapping[str, str]],
    per_execution: Sequence[Mapping[str, str]],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> list[dict[str, Any]]:
    per_cell, per_execution = _normalize_legacy_regimes(per_cell, per_execution)
    aggregates = _aggregate_cells(per_cell)
    ambiguity_clusters = _ambiguity_clusters(per_execution)
    rows: list[dict[str, Any]] = []
    regimes = sorted({regime for regime, _system, _metric in aggregates})
    for regime in regimes:
        systems = sorted(
            {
                system
                for aggregate_regime, system, _metric in aggregates
                if aggregate_regime == regime and system != REFERENCE_SYSTEM
            }
        )
        for metric in RATE_METRICS:
            reference = aggregates.get((regime, REFERENCE_SYSTEM, metric))
            if reference is None:
                continue
            for system in systems:
                result = aggregates.get((regime, system, metric))
                if result is None:
                    continue
                comparison = compare_rates(
                    metric,
                    system=system,
                    reference=REFERENCE_SYSTEM,
                    system_successes=result["successes"],
                    system_total=result["total"],
                    reference_successes=reference["successes"],
                    reference_total=reference["total"],
                )
                row: dict[str, Any] = {
                    "regime": regime,
                    **comparison.echo(),
                    "system_runs": result["runs"],
                    "reference_runs": reference["runs"],
                    "fisher_unit": "execution (cluster-unadjusted)",
                }
                if metric == "known_ambiguity_rate":
                    system_strata = ambiguity_clusters.get((regime, system), {})
                    reference_strata = ambiguity_clusters.get(
                        (regime, REFERENCE_SYSTEM), {}
                    )
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


def write_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def update_manifest(manifest: Path, output: Path) -> None:
    relative = output.relative_to(manifest.parent).as_posix()
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    lines = manifest.read_text(encoding="utf-8").splitlines()
    replacement = f"{digest}  {relative}"
    matches = [index for index, line in enumerate(lines) if line.endswith(f"  {relative}")]
    if len(matches) != 1:
        raise ValueError(
            f"manifest must contain exactly one entry for {relative}; found {len(matches)}"
        )
    lines[matches[0]] = replacement
    # Keep the checksum file byte-stable across Windows and POSIX hosts.
    with manifest.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--update-manifest", type=Path)
    parser.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    arguments = parser.parse_args()

    rows = build_rows(
        read_rows(arguments.analysis / "per-cell-metrics.csv"),
        read_rows(arguments.analysis / "per-execution.csv"),
        resamples=arguments.resamples,
        seed=arguments.seed,
    )
    write_rows(arguments.output, rows)
    if arguments.update_manifest:
        update_manifest(arguments.update_manifest, arguments.output)
    print(f"wrote {len(rows)} regime-labelled comparisons to {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
