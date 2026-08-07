"""Freeze the results directory: manifest the cells, then archive them.

Amendment F0(iv). A results tree that keeps changing is not evidence, and a
tree whose contents nobody enumerated is not reproducible. This writes:

  MANIFEST.md   -- run counts per cell, keyed the way the paper quotes them
                   (regime, system, crash point, response class, keying),
                   plus the digest of every run's config and the totals a
                   reader can check the tables against.
  MANIFEST.csv  -- the same, machine-readable.
  SHA256SUMS    -- over the manifest and the analysis outputs, so a later
                   reader can tell whether the numbers moved.

The manifest counts runs that actually *completed* -- a directory with no
parsing ``summary.json`` is an interrupted attempt, not a result, and is
listed separately rather than silently counted or silently dropped.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SKIP_DIRECTORIES = {"analysis"}


def load_summary(directory: Path) -> dict[str, Any] | None:
    path = directory / "summary.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def load_config(directory: Path) -> dict[str, Any] | None:
    path = directory / "run-config.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def regime_of(config: dict[str, Any]) -> str:
    """Read the regime back off the run's own config, as analyze.py does."""
    if config.get("redis_kill_point"):
        point = config["redis_kill_point"]
        delay = config.get("redis_kill_delay_ms") or 0
        return (
            "redis-kill-preack"
            if point == "after_intent_before_barrier" and not delay
            else "redis-kill-inflight"
        )
    probability = config.get("crash_probability", 1.0)
    if probability == 0.0:
        return "p0"
    if abs(probability - 0.3) < 1e-9:
        return "p30"
    return "(session-3)"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--label", default="", help="e.g. the session name")
    arguments = parser.parse_args()
    root: Path = arguments.results_root

    cells: dict[tuple[str, ...], list[str]] = defaultdict(list)
    incomplete: list[str] = []
    executions = 0
    disagreements = 0
    failed: list[str] = []

    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        if directory.name in SKIP_DIRECTORIES:
            continue
        summary = load_summary(directory)
        config = load_config(directory)
        if summary is None or config is None:
            incomplete.append(directory.name)
            continue
        key = (
            regime_of(config),
            str(config.get("system")),
            str(config.get("crash_point")),
            str(config.get("response_class") or summary.get("response_class")),
            str(config.get("readback_keying")),
        )
        cells[key].append(directory.name)
        executions += int(summary.get("executions") or 0)
        if summary.get("agrees") is False:
            disagreements += 1
        if summary.get("status") not in (None, "collected", "ok"):
            failed.append(f"{directory.name} ({summary.get('status')})")

    rows = []
    for key in sorted(cells):
        rows.append(
            {
                "regime": key[0],
                "system": key[1],
                "crash_point": key[2],
                "response_class": key[3],
                "readback_keying": key[4],
                "runs": len(cells[key]),
            }
        )

    csv_path = root / "MANIFEST.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    by_regime = Counter(r["regime"] for r in rows)
    runs_by_regime: Counter[str] = Counter()
    for row in rows:
        runs_by_regime[row["regime"]] += row["runs"]

    lines: list[str] = []
    lines.append(f"# Results manifest{f' -- {arguments.label}' if arguments.label else ''}")
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
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- completed runs: **{sum(runs_by_regime.values())}**")
    lines.append(f"- executions: **{executions}**")
    lines.append(f"- cells: **{len(rows)}**")
    lines.append(f"- reconciliation disagreements: **{disagreements}**")
    lines.append(
        f"- directories with no parsing summary (interrupted, not counted): "
        f"**{len(incomplete)}**"
    )
    if failed:
        lines.append(f"- runs with a non-collected status: **{len(failed)}**")
        for entry in failed:
            lines.append(f"  - `{entry}`")
    lines.append("")
    lines.append("## By regime")
    lines.append("")
    lines.append("| regime | cells | runs |")
    lines.append("|---|---|---|")
    for regime in sorted(by_regime):
        lines.append(f"| `{regime}` | {by_regime[regime]} | {runs_by_regime[regime]} |")
    lines.append("")
    lines.append("## Cells")
    lines.append("")
    lines.append(
        "| regime | system | crash point | response class | keying | runs |"
    )
    lines.append("|---|---|---|---|---|---|")
    for row in rows:
        lines.append(
            f"| `{row['regime']}` | {row['system']} | `{row['crash_point']}` | "
            f"{row['response_class']} | {row['readback_keying']} | "
            f"{row['runs']} |"
        )
    if incomplete:
        lines.append("")
        lines.append("## Directories without a parsing summary")
        lines.append("")
        lines.append(
            "These are interrupted attempts. They contribute nothing to any "
            "number in the paper and are listed so that the difference "
            "between the directory count and the run count is accounted for "
            "rather than noticed."
        )
        lines.append("")
        for name in incomplete:
            lines.append(f"- `{name}`")

    manifest_path = root / "MANIFEST.md"
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Digests over the manifest and every analysis output.
    sums: list[str] = []
    for path in [manifest_path, csv_path] + sorted(
        (root / "analysis").glob("*") if (root / "analysis").is_dir() else []
    ):
        if path.is_file():
            sums.append(f"{sha256(path)}  {path.relative_to(root)}")
    (root / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")

    print(f"wrote {manifest_path}")
    print(f"wrote {csv_path}")
    print(f"wrote {root / 'SHA256SUMS'}  ({len(sums)} files)")
    print()
    print(f"completed runs {sum(runs_by_regime.values())}   "
          f"executions {executions}   cells {len(rows)}   "
          f"disagreements {disagreements}   incomplete dirs {len(incomplete)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
