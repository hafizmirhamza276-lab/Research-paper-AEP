#!/usr/bin/env python3
"""B9 / handover provenance: reconstruct the run-position drift figures.

The 28 August handover and the 28 August prediction amendment quote a
Spearman correlation between run position and Redis-kill latency for the
paired sessions.  ``matrix-progress.jsonl`` is a run artefact and is not
tracked, so the true wall-clock execution order is not in the repository.
Position is instead reconstructed from ``per-execution.csv``: the cell a
row belongs to, plus the ``-rN`` repetition suffix on ``run_id``.

Two candidate reconstructions, one per collection design:

  cell-major   position = (cell index, repetition)   -- the superseded design
  interleaved  position = (repetition, cell index)   -- the amended design

The cell order is the collection order, NOT alphabetical: NO_READBACK was
collected before AUTHORITATIVE_READBACK, which sorts the other way.  That
detail is the whole reconstruction; getting it wrong reads as "does not
reproduce".

Validation before use: a reconstruction is only trusted here if it returns
the independently committed figures exactly.  Run with no arguments.
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

ROOTS = Path(__file__).resolve().parents[2] / "experiments" / "results"

# Collection order, not alphabetical order.
CELLS = [
    ("AEP_FULL", "NO_READBACK"),
    ("AEP_FULL", "AUTHORITATIVE_READBACK"),
    ("B3_INTENT_NO_BARRIER", "NO_READBACK"),
    ("B3_INTENT_NO_BARRIER", "AUTHORITATIVE_READBACK"),
]


def rep_index(run_id: str) -> int:
    """Repetition index from the ``-rN`` suffix of a run_id."""
    return int(run_id.rsplit("-r", 1)[1])


def spearman(xs: list[float], ys: list[float]) -> float:
    return statistics.correlation(rank(xs), rank(ys))


def rank(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def theil_sen(xs: list[float], ys: list[float]) -> float:
    slopes = [
        (ys[j] - ys[i]) / (xs[j] - xs[i])
        for i in range(len(xs))
        for j in range(i + 1, len(xs))
        if xs[j] != xs[i]
    ]
    return statistics.median(slopes)


def load(root: str) -> list[dict]:
    path = ROOTS / root / "analysis" / "per-execution.csv"
    with path.open(newline="") as fh:
        return [r for r in csv.DictReader(fh) if r["redis_kill_latency_ms"]]


def positions(rows: list[dict], design: str) -> list[tuple[float, float]]:
    """Return (position, latency) pairs under one reconstruction."""
    pairs = []
    for row in rows:
        cell = CELLS.index((row["system"], row["response_class"]))
        rep = rep_index(row["run_id"])
        key = (cell, rep) if design == "cell-major" else (rep, cell)
        pairs.append((key, float(row["redis_kill_latency_ms"])))
    pairs.sort(key=lambda p: p[0])
    return [(float(i), lat) for i, (_, lat) in enumerate(pairs)]


def report(label: str, root: str, design: str) -> None:
    rows = load(root)
    pts = positions(rows, design)
    xs = [p for p, _ in pts]
    ys = [lat for _, lat in pts]
    print(
        f"{label:28s} n={len(pts):4d}  design={design:11s} "
        f"rho={spearman(xs, ys):+.4f}  theil-sen={theil_sen(xs, ys):+.3f} ms/run"
    )


if __name__ == "__main__":
    targets = [
        ("b2-paired-s1  (superseded)", "b2-paired-s1-2026-08-28", "cell-major"),
        ("b2-paired-v2-s1", "b2-paired-v2-s1-2026-08-28", "interleaved"),
        ("b2-paired-v2-s2", "b2-paired-v2-s2-2026-08-28", "interleaved"),
        ("b2-paired-v2-s3", "b2-paired-v2-s3-2026-08-28", "interleaved"),
        ("b2-paired-v2-s4", "b2-paired-v2-s4-2026-08-28", "interleaved"),
    ]
    for label, root, design in targets:
        if (ROOTS / root).is_dir():
            report(label, root, design)
        else:
            print(f"{label:28s} ABSENT: {root}")
    print()
    print("cross-check, each root under the other reconstruction:")
    for label, root, design in targets:
        if (ROOTS / root).is_dir():
            other = "interleaved" if design == "cell-major" else "cell-major"
            report(label, root, other)
