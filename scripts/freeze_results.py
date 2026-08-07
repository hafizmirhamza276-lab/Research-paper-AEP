"""Freeze the results directory: manifest the cells, then digest them.

Amendment F0(iv). A results tree that keeps changing is not evidence, and a
tree whose contents nobody enumerated is not reproducible. This writes:

  MANIFEST.md   -- run counts per cell, keyed the way the paper quotes them
                   (regime, system, crash point, response class, keying),
                   plus the totals a reader can check the tables against.
  MANIFEST.csv  -- the same, machine-readable.
  SHA256SUMS    -- over the manifest and every analysis output, so a later
                   reader can tell whether the numbers moved.

**It reads runs through ``experiments.analyze.load_run``, deliberately.** The
first version re-derived the regime, the response class and the execution
count from ``run-config.json`` and ``summary.json`` itself, and got all three
wrong: ``executions`` is spelled ``executions_planned``, ``response_class`` is
not in the run config at all (it is a property of the endpoint), and the
resulting manifest reported 0 executions across 37 cells where the analysis
saw 2 720 across 91. A manifest that disagrees with the analysis is worse than
no manifest -- it is a second, quieter set of numbers. Sharing the loader
makes agreement structural.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.analyze import load_run  # noqa: E402

SKIP_DIRECTORIES = {"analysis"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--label", default="")
    arguments = parser.parse_args()
    root: Path = arguments.results_root

    cells: dict[tuple[str, ...], list[str]] = defaultdict(list)
    incomplete: list[str] = []
    executions = 0
    crashed_executions = 0

    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        if directory.name in SKIP_DIRECTORIES:
            continue
        run = load_run(directory)
        if run is None:
            # No merged log or no ledger: an interrupted attempt, which is not
            # a result and must not be counted as an empty one.
            incomplete.append(directory.name)
            continue
        key = (
            run.regime_label,
            run.system,
            run.crash_point,
            run.response_class,
            run.readback_keying,
        )
        cells[key].append(run.run_id)
        executions += len(run.executions)
        crashed_executions += sum(1 for e in run.executions if e.crashed)

    rows = [
        {
            "regime": key[0],
            "system": key[1],
            "crash_point": key[2],
            "response_class": key[3],
            "readback_keying": key[4],
            "runs": len(cells[key]),
        }
        for key in sorted(cells)
    ]
    if not rows:
        raise SystemExit(f"no completed runs under {root}")

    csv_path = root / "MANIFEST.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    cells_by_regime = Counter(row["regime"] for row in rows)
    runs_by_regime: Counter[str] = Counter()
    for row in rows:
        runs_by_regime[row["regime"]] += row["runs"]

    lines: list[str] = []
    title = f" -- {arguments.label}" if arguments.label else ""
    lines.append(f"# Results manifest{title}")
    lines.append("")
    lines.append(
        "Run counts per cell, keyed the way the paper quotes them. A cell is "
        "`(regime, system, crash point, response class, read-back keying)`. "
        "The regime is part of the key because pooling regimes is what "
        "disqualified the summary table as a source: a crash-free run and a "
        "run in which every execution was killed are different experiments, "
        "not repetitions of one."
    )
    lines.append("")
    lines.append(
        "Produced by `scripts/freeze_results.py`, which loads each run "
        "through the same `experiments.analyze.load_run` the analysis uses, "
        "so these counts and the CSVs cannot disagree."
    )
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- completed runs: **{sum(runs_by_regime.values())}**")
    lines.append(f"- executions: **{executions}**")
    lines.append(f"- of which crashed: **{crashed_executions}**")
    lines.append(f"- cells: **{len(rows)}**")
    lines.append(
        f"- directories with no parsing log (interrupted, not counted): "
        f"**{len(incomplete)}**"
    )
    lines.append("")
    lines.append("## By regime")
    lines.append("")
    lines.append("| regime | cells | runs |")
    lines.append("|---|---|---|")
    for regime in sorted(cells_by_regime):
        lines.append(
            f"| `{regime}` | {cells_by_regime[regime]} | "
            f"{runs_by_regime[regime]} |"
        )
    lines.append("")
    lines.append("## Cells")
    lines.append("")
    lines.append(
        "| regime | system | crash point | response class | keying | runs |"
    )
    lines.append("|---|---|---|---|---|---|")
    for row in rows:
        lines.append(
            f"| `{row['regime']}` | {row['system']} | `{row['crash_point']}` "
            f"| {row['response_class']} | {row['readback_keying']} | "
            f"{row['runs']} |"
        )
    if incomplete:
        lines.append("")
        lines.append("## Directories without a parsing run log")
        lines.append("")
        lines.append(
            "Interrupted attempts. They contribute nothing to any number in "
            "the paper, and are listed so the difference between the "
            "directory count and the run count is accounted for rather than "
            "noticed."
        )
        lines.append("")
        for name in incomplete:
            lines.append(f"- `{name}`")

    manifest_path = root / "MANIFEST.md"
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    analysis = root / "analysis"
    digested = [manifest_path, csv_path]
    if analysis.is_dir():
        digested += sorted(p for p in analysis.glob("*") if p.is_file())
    sums = [f"{sha256(path)}  {path.relative_to(root)}" for path in digested]
    (root / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")

    print(f"wrote {manifest_path}")
    print(f"wrote {csv_path}")
    print(f"wrote {root / 'SHA256SUMS'}  ({len(sums)} files)")
    print()
    print(
        f"completed runs {sum(runs_by_regime.values())}   "
        f"executions {executions} ({crashed_executions} crashed)   "
        f"cells {len(rows)}   incomplete dirs {len(incomplete)}"
    )
    for name in incomplete:
        print(f"  incomplete: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
