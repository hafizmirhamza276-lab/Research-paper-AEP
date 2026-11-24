"""D0(ii): every one of the six roadmap crash points, one run each, on Linux.

The gate is stated in the Session 3 amendments: *"smoke matrix: every one of
the six crash points x 1 run on Linux, EVALUATION mode, reconciliation must
agree for all six -- any disagreement stops the phase."*

``reports/phase-report-2b-session2-2026-08-05.md`` F6 is the reason it exists:
the harness had been run at exactly one of its six crash points, once, so five
sixths of the crash matrix was code that had never executed. Finding a defect
there costs six short runs; finding it during the 30-repetition matrix costs a
matrix.

Each run gets its own provider, its own ledger and its own seeded fault
generator -- see ``experiments/harness/orchestrate.py`` for why that is not
optional.

    python -m experiments.smoke_matrix --redis-url redis://127.0.0.1:6381/15
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import time
from pathlib import Path

from experiments.harness.crash_points import ROADMAP_CRASH_POINTS
from experiments.harness.injector import HAS_SIGKILL
from experiments.harness.orchestrate import run_once

DEFAULT_TEMPLATE = Path("experiments/configs/smoke.yaml")


async def main_async(arguments) -> int:
    points = list(ROADMAP_CRASH_POINTS)
    print("=" * 70)
    print(f"D0(ii) smoke matrix -- {len(points)} crash points x 1 run")
    print(f"  platform:      {platform.platform()}")
    print(f"  python:        {sys.version.split()[0]}")
    print(f"  has_sigkill:   {HAS_SIGKILL}")
    print(f"  kill:          {'SIGKILL' if HAS_SIGKILL else 'TerminateProcess'}")
    print(f"  redis:         {arguments.redis_url}")
    print(f"  template:      {arguments.template}")
    print(f"  results root:  {arguments.results_root}")
    print("=" * 70)

    if not HAS_SIGKILL:
        print(
            "REFUSED: this gate exists to retire the Windows TerminateProcess "
            "caveat (Session 2 report F4). Run it on Linux."
        )
        return 2

    outcomes: list[dict] = []
    failed: list[str] = []
    for index, point in enumerate(points):
        run_id = f"smoke-{point}"
        print("")
        print("-" * 70)
        print(f"[{index + 1}/{len(points)}] crash point: {point}")
        print("-" * 70)
        started = time.monotonic()
        outcome = await run_once(
            run_config_overrides={
                "run_id": run_id,
                "seed": arguments.seed,
                "workers": arguments.workers,
                "executions_per_worker": arguments.executions_per_worker,
                "endpoint": arguments.endpoint,
                "redis_url": arguments.redis_url,
                "results_root": arguments.results_root,
                "crash_point": point,
                "crash_probability": 1.0,
                "crash_delay_ms": arguments.crash_delay_ms,
                "poisoned_executions": arguments.poisoned_executions,
            },
            template_path=arguments.template,
            port=arguments.port,
        )
        elapsed = time.monotonic() - started
        report = outcome["report"]
        print(json.dumps(report.echo(), indent=2, sort_keys=True))
        print(f"settled: {outcome['settled']}   wall: {elapsed:.1f}s")
        print(f"agrees:  {report.agrees}")
        outcomes.append(
            {
                "crash_point": point,
                "run_id": run_id,
                "agrees": report.agrees,
                "settled": outcome["settled"],
                "wall_seconds": round(elapsed, 3),
                "summary": outcome["summary"],
            }
        )
        if not report.agrees:
            failed.append(point)

    manifest = Path(arguments.results_root) / "smoke-matrix.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "platform": platform.platform(),
                "python": sys.version.split()[0],
                "has_sigkill": HAS_SIGKILL,
                "seed": arguments.seed,
                "runs": outcomes,
                "passed": not failed,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print("")
    print("=" * 70)
    for entry in outcomes:
        mark = "PASS" if entry["agrees"] else "FAIL"
        print(
            f"  {mark}  {entry['crash_point']:<34} "
            f"settled={str(entry['settled']):<5} {entry['wall_seconds']:>7.1f}s"
        )
    print("=" * 70)
    if failed:
        print(f"D0(ii) FAIL -- reconciliation disagreed at: {', '.join(failed)}")
        print("Per D0, any disagreement stops the phase.")
        return 1
    print(f"D0(ii) PASS -- reconciliation agreed at all {len(points)} crash points")
    print(f"manifest: {manifest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the D0(ii) smoke matrix.")
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6381/15")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--results-root", default="experiments/results/smoke")
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--executions-per-worker", type=int, default=3)
    parser.add_argument("--endpoint", default="payments")
    parser.add_argument("--crash-delay-ms", type=int, default=400)
    parser.add_argument("--poisoned-executions", type=int, default=1)
    parser.add_argument("--port", type=int, default=8099)
    return asyncio.run(main_async(parser.parse_args(argv)))


if __name__ == "__main__":  # pragma: no cover - process entry point
    sys.exit(main())
