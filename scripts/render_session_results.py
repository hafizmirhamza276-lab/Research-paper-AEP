r"""Render one collection session's raw results file, the shape `reports/raw/` holds.

Arm A's session 1 and session 2 files were assembled by hand from component
pieces. Nothing was wrong with them -- this script reproduces both byte-for-byte,
and `tests/test_session_results_rendering.py` asserts exactly that -- but a
hand-assembled artifact has no defence against the next session being assembled
slightly differently, and the sessions are only comparable if their diagnostics
are computed identically. Per-session differences must come from the data.

**The per-run cost definition is load-bearing and is not obvious.**
`docs/30-controlled-fault-mechanism.md` fixes it: consecutive run *start* stamps,
taken as the first `wall_ms` each `events-runner.jsonl` records, so each interval
is one whole run including provider start, fault, restart and settle. Directory
mtimes are **not** used -- they are touched after the fact, and the first attempt
at this measurement reported a nonsense rate because of it. `matrix-progress.jsonl`'s
`started_at` is a different clock and does not reproduce the committed numbers.

Usage:

    python scripts/render_session_results.py --root <session root> \
        --out reports/raw/phase13-armA-s3-results.txt

    # regression form -- diff against an already-committed file
    python scripts/render_session_results.py --root <session root> \
        --compare reports/raw/phase13-armA-s1-results.txt
"""

from __future__ import annotations

import argparse
import difflib
import json
import statistics
import sys
from pathlib import Path

#: The harness's fitted cost for this regime shape, from `experiments/run_matrix.py`.
#: Not edited here: it is shared by three regimes and back-solving it per regime
#: would be misleading. `docs/30-controlled-fault-mechanism.md` records why.
FITTED_SECONDS_PER_RUN = 36.0
CURRENT_REDIS_KILL_SECONDS = 5.0

#: How many arm letters the interleaving line prints.
#:
#: NOTE: the section header committed with sessions 1 and 2 reads "first 12 runs"
#: while all three files print 40 letters. The header is reproduced verbatim so
#: the three sessions stay byte-comparable; correcting it here would make s3
#: differ from its predecessors for a reason that has nothing to do with the data.
#: Carried as a known text defect rather than silently repaired.
INTERLEAVING_LETTERS = 40


def _run_directories(root: Path) -> list[Path]:
    return [d for d in sorted(root.iterdir()) if d.is_dir() and d.name != "analysis"]


def mechanism_section(root: Path) -> list[str]:
    """Did the injector fire, and did each run record which mechanism it used?"""
    mechanisms: dict[str, int] = {}
    paused = not_paused = no_kill = 0

    for run in _run_directories(root):
        config = run / "run-config.json"
        if config.exists():
            environment = json.loads(config.read_text(encoding="utf-8")).get(
                "environment", {}
            )
            name = environment.get("redis_fault_mechanism")
            mechanisms[name] = mechanisms.get(name, 0) + 1

        seen = False
        for log in sorted(run.glob("events*.jsonl")):
            for line in log.read_text(errors="replace").splitlines():
                if '"redis_kill_issued"' not in line:
                    continue
                seen = True
                record = json.loads(line)
                if record.get("paused") is True:
                    paused += 1
                elif "paused" in record:
                    not_paused += 1
        if not seen:
            # A run the harness refused: its own guard detected the kill had not
            # landed and aborted rather than scoring a trial with no fault in it.
            no_kill += 1

    return [
        "########## did the mechanism fire, and was it recorded? ##########",
        f"  runs: {len(_run_directories(root))}",
        f"  environment.redis_fault_mechanism: {mechanisms}",
        f"  kills with paused=true : {paused}",
        f"  kills with paused=false: {not_paused}",
        f"  runs with no kill event: {no_kill}",
    ]


def clock_section(root: Path) -> list[str]:
    """The E5 gate, read from the analyzer's own coverage rather than recomputed."""
    coverage = json.loads(
        (root / "analysis" / "coverage.json").read_text(encoding="utf-8")
    )
    return [
        "########## E5 clock gate for this session ##########",
        f"  runs {coverage['runs']} executions {coverage['executions']}",
        f"  dropped for clock suspension: {coverage['runs_dropped_for_clock_suspension']}",
        f"  worst suspension seconds  : {coverage['worst_suspension_seconds']}",
        f"  all real SIGKILL          : {coverage['all_runs_used_real_sigkill']}",
        f"  regimes                   : {coverage['regimes']}",
    ]


def estimand_section(root: Path) -> list[str]:
    """`redis-kill-ablation.csv` verbatim -- the estimand, read as \\UnwantedPrevented reads it."""
    text = (root / "analysis" / "redis-kill-ablation.csv").read_text(encoding="utf-8")
    return [
        "########## THE ESTIMAND -- unwanted applied effects, per capability class ##########",
        *text.strip().splitlines(),
    ]


def progress_records(root: Path) -> list[dict]:
    records = [
        json.loads(line)
        for line in (root / "matrix-progress.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    return sorted(records, key=lambda record: record["started_at"])


def interleaving_section(records: list[dict]) -> list[str]:
    """The realised ordering, reported from the collected runs rather than assumed.

    The pre-registration requires this: Phase 8.4's `b2-paired-s1` was cell-major
    and B9 exists because of it.
    """
    letters = ["A" if r["system"] == "AEP_FULL" else "B" for r in records]
    adjacent = sum(1 for a, b in zip(letters, letters[1:]) if a == b)
    return [
        "########## interleaving actually realised (first 12 runs, by start time) ##########",
        "  " + " ".join(letters[:INTERLEAVING_LETTERS]),
        f"  adjacent same-arm pairs: {adjacent} of {len(letters) - 1}",
    ]


def runner_start_stamps(root: Path) -> list[float]:
    """Run start stamps: the first `wall_ms` each `events-runner.jsonl` records.

    See the module docstring -- mtimes and `started_at` both give wrong answers.
    """
    stamps: list[float] = []
    for run in _run_directories(root):
        log = run / "events-runner.jsonl"
        if not log.exists():
            continue
        for line in log.read_text(errors="replace").splitlines():
            record = json.loads(line)
            if "wall_ms" in record:
                stamps.append(record["wall_ms"] / 1000.0)
                break
    return sorted(stamps)


def percentile95(values: list[float]) -> float:
    """Linear interpolation on the sorted sample."""
    ordered = sorted(values)
    position = 0.95 * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def cost_section(stamps: list[float]) -> list[str]:
    intervals = [b - a for a, b in zip(stamps, stamps[1:])]
    median = statistics.median(intervals)
    implied = CURRENT_REDIS_KILL_SECONDS + (median - FITTED_SECONDS_PER_RUN)
    return [
        "########## final per-run cost, full n ##########",
        f"runs observed          : {len(stamps)}",
        f"inter-run intervals (n): {len(intervals)}",
        f"  min      {min(intervals):5.1f} s",
        f"  median   {median:5.1f} s",
        f"  mean     {statistics.fmean(intervals):5.1f} s",
        f"  p95      {percentile95(intervals):5.1f} s",
        f"  max      {max(intervals):5.1f} s",
        "",
        f"harness fitted estimate for this regime: {FITTED_SECONDS_PER_RUN:.1f} s/run",
        f"observed / fitted                      : {median / FITTED_SECONDS_PER_RUN:.2f}x",
        "implied REDIS_KILL_SECONDS if the rest of the model holds: "
        f"{implied:.1f} s (currently {CURRENT_REDIS_KILL_SECONDS:.1f})",
    ]


def render(root: Path) -> str:
    """The whole file, exactly as `reports/raw/phase13-armA-s*-results.txt` holds it."""
    records = progress_records(root)
    sections = [
        mechanism_section(root),
        clock_section(root),
        estimand_section(root),
        interleaving_section(records),
        cost_section(runner_start_stamps(root)),
    ]
    body = "\n\n\n".join("\n".join(section) for section in sections)
    return "\n\n" + body + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True, help="the session's results root")
    parser.add_argument("--out", default=None, help="write here instead of stdout")
    parser.add_argument(
        "--compare", default=None, help="diff against an already-committed file"
    )
    arguments = parser.parse_args(argv)

    text = render(Path(arguments.root))

    if arguments.compare:
        expected = Path(arguments.compare).read_text(encoding="utf-8")
        if expected == text:
            print(f"MATCH  {arguments.compare}")
            return 0
        print(f"DIFFERS  {arguments.compare}")
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
