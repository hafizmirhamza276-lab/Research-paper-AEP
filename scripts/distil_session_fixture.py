r"""Distil a session root down to only what `render_session_results.py` reads.

`tests/test_session_results_rendering.py` pins the renderer against the committed
`reports/raw/phase13-armA-s*-results.txt` files. It cannot do that from the real
session roots: they live on the measurement host (`/root/aep-phase13/...`), run
to ~150 MB of raw run data that `.gitignore` excludes by policy, and CI has no
access to them. A test gated on their presence would skip, and
`scripts/check_pytest_gates.py` gate 1 is *zero skipped*.

So the test works from `tests/fixtures/session-results/*.json`, and this is what
produces them. It keeps the handful of fields the renderer consumes and nothing
else -- roughly 56 KB per session against ~50 MB of source.

**Why the fixtures are not circular evidence.** Sessions 1 and 2's committed
results files were assembled by hand, before the renderer existed. If this
distillation dropped or corrupted a field, or the renderer computed a number a
different way, the render would stop matching them. Agreement is evidence
precisely because the two were arrived at separately.

**This script is the reason the fixtures are reproducible at all.** Generating
them by hand on one machine would reintroduce, one level down, exactly the
hand-assembly problem the renderer was promoted to remove.

Usage::

    python scripts/distil_session_fixture.py --root /root/aep-phase13/armA-s3-2026-09-03 \
        --out tests/fixtures/session-results/armA-s3.json

    # regression form -- diff against an already-committed fixture
    python scripts/distil_session_fixture.py --root <session root> \
        --check tests/fixtures/session-results/armA-s1.json
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

#: The committed fixtures are written with these settings. Changing either
#: rewrites every fixture byte-for-byte without changing its meaning, so they
#: are pinned here rather than left to json.dumps' defaults.
JSON_INDENT = 1
JSON_SORT_KEYS = True


def _run_directories(root: Path) -> list[Path]:
    return [d for d in sorted(root.iterdir()) if d.is_dir() and d.name != "analysis"]


def distil_run(run: Path) -> dict:
    """The per-run fields the renderer reads, and no others."""
    config = run / "run-config.json"
    mechanism = None
    if config.exists():
        mechanism = (
            json.loads(config.read_text(encoding="utf-8"))
            .get("environment", {})
            .get("redis_fault_mechanism")
        )

    paused_true = paused_false = 0
    for log in sorted(run.glob("events*.jsonl")):
        for line in log.read_text(errors="replace").splitlines():
            if '"redis_kill_issued"' not in line:
                continue
            record = json.loads(line)
            if record.get("paused") is True:
                paused_true += 1
            elif "paused" in record:
                paused_false += 1

    # The renderer takes run start stamps as the FIRST wall_ms each
    # events-runner.jsonl records. docs/30-controlled-fault-mechanism.md fixes
    # that definition; mtimes and matrix-progress.jsonl's started_at both give
    # wrong answers and must not be substituted here.
    runner_wall_ms = None
    runner = run / "events-runner.jsonl"
    if runner.exists():
        for line in runner.read_text(errors="replace").splitlines():
            record = json.loads(line)
            if "wall_ms" in record:
                runner_wall_ms = record["wall_ms"]
                break

    return {
        "name": run.name,
        "has_run_config": config.exists(),
        "redis_fault_mechanism": mechanism,
        "kill_paused_true": paused_true,
        "kill_paused_false": paused_false,
        "runner_wall_ms": runner_wall_ms,
    }


def distil(root: Path) -> dict:
    progress = [
        {"system": record["system"], "started_at": record["started_at"]}
        for record in (
            json.loads(line)
            for line in (root / "matrix-progress.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    ]

    return {
        "source_root": root.name,
        "runs": [distil_run(run) for run in _run_directories(root)],
        "progress": progress,
        "coverage": json.loads(
            (root / "analysis" / "coverage.json").read_text(encoding="utf-8")
        ),
        "ablation_csv": (root / "analysis" / "redis-kill-ablation.csv").read_text(
            encoding="utf-8"
        ),
    }


def serialise(fixture: dict) -> str:
    return (
        json.dumps(fixture, indent=JSON_INDENT, sort_keys=JSON_SORT_KEYS) + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True, help="the session's results root")
    parser.add_argument("--out", default=None, help="write here instead of stdout")
    parser.add_argument(
        "--check", default=None, help="diff against an already-committed fixture"
    )
    arguments = parser.parse_args(argv)

    text = serialise(distil(Path(arguments.root)))

    if arguments.check:
        expected = Path(arguments.check).read_text(encoding="utf-8")
        if expected == text:
            print(f"MATCH  {arguments.check}")
            return 0
        print(f"DIFFERS  {arguments.check}")
        for line in difflib.unified_diff(
            expected.splitlines(),
            text.splitlines(),
            fromfile="committed",
            tofile="regenerated",
            lineterm="",
        ):
            print(line)
        return 1

    if arguments.out:
        Path(arguments.out).write_text(text, encoding="utf-8")
        print(f"wrote {arguments.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
