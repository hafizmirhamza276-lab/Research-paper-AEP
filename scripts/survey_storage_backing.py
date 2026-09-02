#!/usr/bin/env python3
"""Which collections know what filesystem and storage backing they ran on?

Phase 10, added scope. **This script establishes a fact. It changes nothing,
recommends nothing, and re-analyses nothing.**

`docs/24-revision-backlog.md` B1's Phase-8.2 addendum states the rule this
survey applies:

> a property that can move a measured quantity, that nobody chose to hold
> fixed, and that no field recorded [...] must be stated rather than assumed
> comparable.

`experiments/harness/provenance.py` was added in Phase 8.2 (commit `e67efd1`,
2026-08-27) to record two such properties per run: `results_root_filesystem`
and `redis_storage_backing`. Collections made *before* that commit carry
neither. This script says, per results root, which of them do.

**Two rules it follows, both of which matter for the answer to be worth
anything.**

1. **Nothing is inferred from a directory name.** A root called
   `b2-paired-v2-s2-aborted-2026-08-28` is not evidence that anything was
   aborted, and a root under `/mnt/d` is not evidence that a run wrote to
   drvfs -- trees get copied. Only `run-config.json`'s recorded `environment`
   block counts as determining the answer. Everything else is reported as
   *where the bytes sit today*, labelled as such.
2. **`UNDETERMINED` is a first-class answer** and is never quietly replaced by
   a plausible guess.

It also answers the second half of the question: **which comparisons in
`paper/sections/06-evaluation.tex` put numbers from different results roots
side by side.** Those are the comparisons that span a storage-backing
difference. The mapping is macro -> provenance comment in
`paper/generated/numbers.tex` (which `scripts/paper_tables.py` is required to
emit, and `tests/test_paper_tables.py` enforces) -> results root.

Usage::

    python scripts/survey_storage_backing.py
    python scripts/survey_storage_backing.py --json reports/raw/survey.json
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Trees that may hold run directories for the roots the manuscript quotes.
#: Named explicitly rather than discovered, so that a tree appearing or
#: disappearing is visible in a diff of this file.
DEFAULT_TREES = (
    "/root/aep",
    "/root/aep-phase8",
    "/root/aep-stage3",
    str(REPO_ROOT),
)

#: Provenance-comment prefix -> the results root it names. `paper_tables.py`
#: writes the analysis directory it was given, so the bare CSV names resolve to
#: whatever `--analysis` pointed at, which is `experiments/results/matrix`.
PROVENANCE_TO_ROOT = {
    "per-cell-metrics.csv": "matrix",
    "comparisons-vs-aep-full.csv": "matrix",
    "redis-kill-ablation.csv": "matrix",
    "latency-and-throughput.csv": "matrix",
    "analysis/per-execution.csv": "matrix",
    "analysis/coverage.json": "matrix",
    "b2-*/analysis/redis-kill-ablation.csv": "b2-*-2026-08-21",
    "experiments/results/b2-*/analysis/redis-kill-ablation.csv": "b2-*-2026-08-21",
    "experiments/results/b2-*/": "b2-*-2026-08-21",
    "b2-paired-v2-*/analysis/redis-kill-ablation.csv": "b2-paired-v2-*",
    "fsync-always/analysis/latency-and-throughput.csv": "fsync-always",
    "experiments/results/g2-flakey-write-loss*.json": "g2-flakey (no Docker in the path)",
    "reports/raw/e1-durability-window.txt": "e1-durability-window probe",
    "reports/raw/e1-kill-latency-by-run.csv": "e1-kill-latency (matrix + b2-*)",
}


# ---------------------------------------------------------------- the roots
def tracked_paths() -> set[str]:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "experiments/results"],
        capture_output=True, text=True, timeout=60,
    )
    return set(completed.stdout.split())


def survey_root(root: Path) -> dict[str, Any]:
    """What this directory's run-configs record about where they ran."""
    configs = sorted(root.glob("*/run-config.json"))
    record: dict[str, Any] = {
        "path": str(root),
        "run_directories": sum(
            1 for child in root.iterdir()
            if child.is_dir() and child.name != "analysis"
        ) if root.is_dir() else 0,
        "run_configs": len(configs),
        "with_environment": 0,
        "filesystem": "UNDETERMINED",
        "redis_storage_backing": "UNDETERMINED",
        "recorded_results_root": None,
    }
    seen_fs: collections.Counter[str] = collections.Counter()
    seen_backing: collections.Counter[str] = collections.Counter()
    seen_declared: collections.Counter[str] = collections.Counter()
    for config in configs:
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        environment = data.get("environment")
        if not environment:
            continue
        record["with_environment"] += 1
        fs = environment.get("results_root_filesystem") or {}
        backing = environment.get("redis_storage_backing") or {}
        seen_fs[
            f"type={fs.get('type')} device={fs.get('device')} "
            f"mount={fs.get('mount_point')} is_drvfs={fs.get('is_drvfs')}"
        ] += 1
        seen_backing[
            f"{backing.get('mount_type')} {backing.get('source')} "
            f"name={backing.get('name')}"
        ] += 1
        seen_declared[str(data.get("results_root"))] += 1
    if record["with_environment"]:
        record["filesystem"] = [
            {"value": value, "runs": n} for value, n in seen_fs.most_common()
        ]
        record["redis_storage_backing"] = [
            {"value": value, "runs": n} for value, n in seen_backing.most_common()
        ]
        record["recorded_results_root"] = [
            {"value": value, "runs": n} for value, n in seen_declared.most_common()
        ]
    return record


# -------------------------------------------------- the manuscript's numbers
def macro_provenance() -> dict[str, str]:
    numbers = REPO_ROOT / "paper/generated/numbers.tex"
    provenance: dict[str, str] = {}
    pending: list[str] = []
    for line in numbers.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("%"):
            pending.append(stripped.lstrip("% ").strip())
        elif stripped.startswith("\\newcommand{"):
            match = re.match(r"\\newcommand\{\\([A-Za-z]+)\}", stripped)
            if match:
                provenance[match.group(1)] = pending[0] if pending else "(none)"
            pending = []
        elif stripped:
            pending = []
    return provenance


def cross_root_paragraphs(section: Path) -> list[dict[str, Any]]:
    """Paragraphs whose numbers come from two or more results roots."""
    provenance = macro_provenance()
    root_of = {
        macro: PROVENANCE_TO_ROOT.get(
            prov.split("|")[0].strip(), f"DERIVED ({prov.split('|')[0].strip()[:48]})"
        )
        for macro, prov in provenance.items()
    }
    lines = section.read_text(encoding="utf-8").splitlines()
    blocks: list[tuple[int, list[tuple[int, str]]]] = []
    buffer: list[tuple[int, str]] = []
    for number, line in enumerate(lines, 1):
        if line.strip():
            buffer.append((number, line))
        elif buffer:
            blocks.append((buffer[0][0], buffer))
            buffer = []
    if buffer:
        blocks.append((buffer[0][0], buffer))

    pattern = re.compile(r"\\([A-Za-z]+)(?![A-Za-z])")
    found: list[dict[str, Any]] = []
    for start, block in blocks:
        body = "\n".join(text for _, text in block)
        macros = [m for m in pattern.findall(body) if m in root_of]
        if not macros:
            continue
        by_root: dict[str, list[str]] = collections.defaultdict(list)
        for macro in macros:
            by_root[root_of[macro]].append(macro)
        concrete = {r for r in by_root if not r.startswith("DERIVED")}
        if len(concrete) < 2:
            continue
        found.append({
            "file": "paper/sections/06-evaluation.tex",
            "lines": f"{start}-{block[-1][0]}",
            "roots": {
                root: sorted(set(names)) for root, names in sorted(by_root.items())
            },
            "distinct_results_roots": sorted(concrete),
        })
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", dest="trees", action="append", default=None)
    parser.add_argument("--json", type=Path, default=None)
    arguments = parser.parse_args(argv)
    trees = arguments.trees or list(DEFAULT_TREES)

    tracked = tracked_paths()
    tracked_roots = sorted({
        path.split("/")[2] for path in tracked
        if path.startswith("experiments/results/") and len(path.split("/")) > 3
    })

    payload: dict[str, Any] = {
        "survey": "phase10-storage-backing/1",
        "rule": (
            "Only run-config.json's recorded environment block determines the "
            "answer. Directory names and current file locations do not."
        ),
        "instrumentation_added": (
            "experiments/harness/provenance.py, Phase 8.2, commit e67efd1, "
            "2026-08-27. Collections before it carry no environment block."
        ),
        "tracked_results_roots": tracked_roots,
        "tracked_file_count": len(tracked),
        "note_on_tracking": (
            "Raw run directories are gitignored by design (.gitignore:134-151); "
            "only analysis products and manifests are tracked. No TRACKED file "
            "carries results_root_filesystem or redis_storage_backing."
        ),
        "trees": {},
    }

    print("=" * 78)
    print("Storage backing across existing collections")
    print("=" * 78)
    print(f"\n{len(tracked_roots)} results roots are represented in git:")
    for root in tracked_roots:
        print(f"  {root}")
    print(f"\n{payload['note_on_tracking']}\n")

    for tree in trees:
        results = Path(tree) / "experiments" / "results"
        entry: dict[str, Any] = {}
        print("=" * 78)
        print(f"TREE {tree}")
        print("=" * 78)
        if not results.is_dir():
            print("  (no experiments/results)")
            payload["trees"][tree] = {"error": "no experiments/results"}
            continue
        for root in sorted(p for p in results.iterdir() if p.is_dir()):
            record = survey_root(root)
            entry[root.name] = record
            determined = record["with_environment"] > 0
            print(f"\n  {root.name}")
            print(f"    run directories        {record['run_directories']}")
            print(f"    run-configs            {record['run_configs']}"
                  f"  (with environment: {record['with_environment']})")
            if not determined:
                print("    filesystem             UNDETERMINED from recorded metadata")
                print("    redis_storage_backing  UNDETERMINED from recorded metadata")
            else:
                for item in record["filesystem"]:
                    print(f"    filesystem             {item['value']}  [{item['runs']} run(s)]")
                for item in record["redis_storage_backing"]:
                    print(f"    redis_storage_backing  {item['value']}  [{item['runs']} run(s)]")
                for item in record["recorded_results_root"]:
                    print(f"    recorded results_root  {item['value']}  [{item['runs']} run(s)]")
        payload["trees"][tree] = entry

    section = REPO_ROOT / "paper/sections/06-evaluation.tex"
    crossing = cross_root_paragraphs(section)
    payload["cross_root_comparisons"] = crossing
    print("\n" + "=" * 78)
    print("Comparisons in section VI that span two or more results roots")
    print("=" * 78)
    for item in crossing:
        print(f"\n  {item['file']}:{item['lines']}  "
              f"-> {', '.join(item['distinct_results_roots'])}")
        for root, macros in item["roots"].items():
            print(f"      [{root}] {', '.join('\\' + m for m in macros[:8])}")
    print(f"\n  TOTAL: {len(crossing)} paragraph(s)")

    if arguments.json:
        arguments.json.parent.mkdir(parents=True, exist_ok=True)
        arguments.json.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(f"\nwrote {arguments.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
