r"""Arm A's verdict, against the criterion pre-registered before the data existed.

`reports/phase-report-13-prediction-armA-2026-09-03.md`, pushed at
2026-09-03T10:02:00Z, fixed three things that this script only applies:

* the **prediction** -- AEP-full approaches **0.058**, the injector's landing
  latency as a fraction of the 1000 ms WAITAOF window, bounded by
  **[0.045, 0.081]** from the measured landing min and max. Zero was explicitly
  *not* predicted;
* the **spread criterion** -- between-session range in AEP-full's
  unwanted-applied count, per capability class: **<=3 succeeded, 4-5
  inconclusive, >=6 failed**, against a baseline spread of 8 under the
  uncontrolled fault;
* the **mechanism-failure signatures**, kept separate from protocol surprise,
  with B3 falling below 27/30 as the primary one.

Nothing here is chosen after seeing the data. The script's only job is to read
the estimand out of each session's `redis-kill-ablation.csv` exactly as
`\UnwantedPrevented` reads it, and apply the above.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from pathlib import Path

#: Pre-registered, all of it.
POINT_PREDICTION = 0.058
BOUND = (0.045, 0.081)
SPREAD_SUCCEEDED = 3
SPREAD_FAILED = 6
B3_CEILING = 27
UNCONTROLLED_BASELINE_SPREAD = 8
BOOTSTRAP_SEED = 20260806
RESAMPLES = 10000

CLASSES = ("AUTHORITATIVE_READBACK", "POSITIVE_ONLY_READBACK", "NO_READBACK")


def ablation_rows(root: Path) -> list[dict[str, str]]:
    path = root / "analysis" / "redis-kill-ablation.csv"
    if not path.is_file():
        raise SystemExit(f"no ablation CSV at {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def mechanism_checks(root: Path) -> dict:
    """The pre-registered signatures that would mean the INJECTOR failed."""
    mechanisms: dict[str, int] = {}
    paused = not_paused = no_kill = 0
    runs = [d for d in sorted(root.iterdir()) if d.is_dir() and d.name != "analysis"]
    for run in runs:
        config = run / "run-config.json"
        if config.exists():
            environment = json.loads(config.read_text(encoding="utf-8")).get(
                "environment", {}
            )
            name = environment.get("redis_fault_mechanism")
            mechanisms[name] = mechanisms.get(name, 0) + 1
        seen = False
        for log in run.glob("events*.jsonl"):
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
            no_kill += 1
    total = paused + not_paused
    return {
        "runs": len(runs),
        "mechanisms_recorded": mechanisms,
        "kill_events_paused_true": paused,
        "kill_events_paused_false": not_paused,
        "runs_with_no_kill_event": no_kill,
        "paused_false_fraction": (not_paused / total) if total else None,
    }


def cluster_bootstrap(per_session: list[tuple[int, int]]) -> tuple[float, float]:
    """Session-clustered percentile interval on a pooled rate.

    The unit is the session, not the run and not the execution: the estimand is
    a between-session quantity and resampling runs would assume the very
    independence the over-dispersion finding denies.
    """
    if len(per_session) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(BOOTSTRAP_SEED)
    rates = []
    for _ in range(RESAMPLES):
        drawn = [per_session[rng.randrange(len(per_session))] for _ in per_session]
        applied = sum(a for a, _ in drawn)
        total = sum(n for _, n in drawn)
        rates.append(applied / total if total else 0.0)
    rates.sort()
    return (
        rates[int(0.025 * (len(rates) - 1))],
        rates[int(0.975 * (len(rates) - 1))],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session", action="append", default=[], required=True)
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    roots = [Path(spec) for spec in arguments.session]
    report: dict = {
        "pre_registered": {
            "point_prediction": POINT_PREDICTION,
            "bound": list(BOUND),
            "spread_succeeded_at_or_below": SPREAD_SUCCEEDED,
            "spread_failed_at_or_above": SPREAD_FAILED,
            "b3_ceiling": B3_CEILING,
            "uncontrolled_baseline_spread": UNCONTROLLED_BASELINE_SPREAD,
        },
        "sessions": {},
        "by_class": {},
    }

    print("=== mechanism checks, per session (pre-registered signatures) ===")
    mechanism_failed: list[str] = []
    for root in roots:
        checks = mechanism_checks(root)
        report["sessions"][root.name] = checks
        bad_mech = set(checks["mechanisms_recorded"]) - {"pause-then-kill"}
        fraction = checks["paused_false_fraction"]
        print(
            f"  {root.name:32s} runs={checks['runs']:3d} "
            f"mechanisms={checks['mechanisms_recorded']} "
            f"paused_false={checks['kill_events_paused_false']} "
            f"no_kill={checks['runs_with_no_kill_event']}"
        )
        if bad_mech:
            mechanism_failed.append(f"{root.name}: mechanism recorded as {bad_mech}")
        if fraction is not None and fraction > 0.05:
            mechanism_failed.append(
                f"{root.name}: paused=false in {fraction:.1%} of kills (>5%)"
            )
        if checks["runs_with_no_kill_event"]:
            mechanism_failed.append(
                f"{root.name}: {checks['runs_with_no_kill_event']} runs had no kill"
            )

    counts: dict[str, dict[str, list[tuple[int, int]]]] = {}
    for root in roots:
        for row in ablation_rows(root):
            system = row["system"]
            klass = row["response_class"]
            applied = int(row["executions_with_an_applied_effect"])
            total = int(row["executions"])
            counts.setdefault(klass, {}).setdefault(system, []).append((applied, total))

    print()
    print("=== the estimand, per capability class ===")
    print(
        f"{'class':26s} {'system':22s} {'per session':>18s} {'pooled':>12s} "
        f"{'95% CI (session)':>22s}"
    )
    verdicts: dict[str, str] = {}
    for klass in CLASSES:
        for system in ("AEP_FULL", "B3_INTENT_NO_BARRIER"):
            series = counts.get(klass, {}).get(system, [])
            if not series:
                continue
            applied = sum(a for a, _ in series)
            total = sum(n for _, n in series)
            low, high = cluster_bootstrap(series)
            per = "/".join(str(a) for a, _ in series)
            print(
                f"{klass:26s} {system:22s} {per:>18s} "
                f"{applied}/{total} = {applied/total:.4f}  "
                f"[{low:.4f}, {high:.4f}]"
            )
            report["by_class"].setdefault(klass, {})[system] = {
                "per_session_applied": [a for a, _ in series],
                "per_session_total": [n for _, n in series],
                "pooled_applied": applied,
                "pooled_total": total,
                "pooled_rate": applied / total,
                "session_clustered_ci": [low, high],
            }

    print()
    print("=== B3 at ceiling? (primary mechanism-failure signature) ===")
    for klass in CLASSES:
        series = counts.get(klass, {}).get("B3_INTENT_NO_BARRIER", [])
        below = [a for a, _ in series if a < B3_CEILING]
        state = "OK" if not below else f"** BELOW {B3_CEILING}: {below} **"
        print(f"  {klass:26s} {[a for a, _ in series]}  {state}")
        if below:
            mechanism_failed.append(f"{klass}: B3 below ceiling in {len(below)} session(s)")

    print()
    print("=== spread, against the pre-registered criterion ===")
    print(f"  baseline under the uncontrolled fault: {UNCONTROLLED_BASELINE_SPREAD} counts")
    for klass in CLASSES:
        series = counts.get(klass, {}).get("AEP_FULL", [])
        values = [a for a, _ in series]
        if not values:
            continue
        spread = max(values) - min(values)
        if spread <= SPREAD_SUCCEEDED:
            verdict = "CONTROL SUCCEEDED"
        elif spread >= SPREAD_FAILED:
            verdict = "CONTROL FAILED"
        else:
            verdict = "INCONCLUSIVE"
        verdicts[klass] = verdict
        print(f"  {klass:26s} AEP-full {values}  spread={spread}  -> {verdict}")
        report["by_class"].setdefault(klass, {})["spread"] = spread
        report["by_class"][klass]["spread_verdict"] = verdict

    print()
    print("=== AEP-full against the pre-registered bound [0.045, 0.081] ===")
    for klass in CLASSES:
        entry = report["by_class"].get(klass, {}).get("AEP_FULL")
        if not entry:
            continue
        rate = entry["pooled_rate"]
        if rate < BOUND[0]:
            where = "BELOW the bound"
        elif rate > BOUND[1]:
            where = "ABOVE the bound"
        else:
            where = "inside the bound"
        entry["bound_verdict"] = where
        print(f"  {klass:26s} {rate:.4f}  {where}")

    print()
    if mechanism_failed:
        print("MECHANISM FAILURE SIGNATURES PRESENT:")
        for line in mechanism_failed:
            print(f"  - {line}")
    else:
        print(
            "No mechanism-failure signature present: the injector did what it "
            "was supposed to, so the rates are about the protocol."
        )
    report["mechanism_failures"] = mechanism_failed
    report["spread_verdicts"] = verdicts

    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
