r"""Phase 13 Step 4's verdict, applying only what was pre-registered in 77afd9a.

`reports/phase-report-13-prediction-inflight-2026-09-04.md` fixed, before any
`redis-kill-inflight` data existed:

* **the tie criterion** — |AEP_FULL − B3| on
  `executions_with_an_applied_effect`, per capability class per session:
  **≤ 2 TIE, 3–5 INCONCLUSIVE, ≥ 6 NOT A TIE**;
* **both arms at ceiling**, ≥ 27/30, with either arm below it the *primary*
  mechanism-failure signature — two arms equally broken by a mis-timed injector
  is not a tie;
* **the four mechanism-failure signatures**, kept separate from protocol
  surprise, and the two results that would be larger than the tie
  (`lost_effect_executions` or `undetected_duplicate_applications` above zero).

Nothing here is chosen after seeing the data.

**Two things this script reports that the pre-registration did not anticipate**,
both load-bearing for how the result may be described:

* **Session independence.** The harness assigns seeds deterministically per
  (system, endpoint, repetition), so two sessions share a seed set and vary only
  through the timing race. Where there is no race, a second session is a
  deterministic *replay*. This script measures seed overlap and per-run outcome
  agreement rather than assuming either, and reports the **effective** run count.
* **Ceiling proximity.** A cell sitting exactly on 27/30 passes the
  pre-registered threshold while being one run from failing it. The script marks
  that as `AT THRESHOLD` rather than `OK`, so it cannot be read as headroom.

Usage::

    python scripts/analyse_inflight_tie.py \
        --session /root/aep-phase13/inflight-s1-2026-09-04 \
        --session /root/aep-phase13/inflight-s2-2026-09-04 \
        --compare /root/aep-phase13/armA-s1-2026-09-03 ... \
        --emit-fixture tests/fixtures/inflight/runs.json

    python scripts/analyse_inflight_tie.py --fixture tests/fixtures/inflight/runs.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

#: Pre-registered, all of it.
TIE_AT_OR_BELOW = 2
NOT_A_TIE_AT_OR_ABOVE = 6
CEILING = 27
RUNS_PER_CELL = 30
EXPECTED_MECHANISM = "kill"
EXPECTED_KILL_POINT = "mid_dispatch"
EXPECTED_DELAY_MS = 200
NO_KILL_TOLERANCE = 0.05

CLASSES = ("AUTHORITATIVE_READBACK", "NO_READBACK")
SYSTEMS = ("AEP_FULL", "B3_INTENT_NO_BARRIER")


# ---------------------------------------------------------------- extraction


def extract_session(root: Path) -> dict:
    runs = []
    for run in sorted(root.iterdir()):
        if not run.is_dir() or run.name == "analysis":
            continue
        config = run / "run-config.json"
        mechanism = kill_point = delay = None
        if config.exists():
            data = json.loads(config.read_text(encoding="utf-8"))
            mechanism = data.get("environment", {}).get("redis_fault_mechanism")
            body = data.get("run_config", data)
            kill_point = body.get("redis_kill_point")
            delay = body.get("redis_kill_delay_ms")
        has_kill = any(
            '"redis_kill_issued"' in log.read_text(errors="replace")
            for log in sorted(run.glob("events-worker-*.jsonl"))
        )
        runs.append({
            "run": run.name,
            "redis_fault_mechanism": mechanism,
            "redis_kill_point": kill_point,
            "redis_kill_delay_ms": delay,
            "has_kill_event": has_kill,
        })

    progress = []
    for line in (root / "matrix-progress.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        progress.append({
            "run_id": record["run_id"],
            "system": record["system"],
            "endpoint": record["endpoint"],
            "repetition": record["repetition"],
            "seed": record["seed"],
            "started_at": record["started_at"],
            "status": record.get("status"),
            # The per-run outcome, for the replay check.
            "outcome": [
                record.get("declared_ambiguous_executions"),
                record.get("undetected_duplicate_applications"),
                record.get("lost_effect_executions"),
                record.get("agrees"),
            ],
        })

    with (root / "analysis" / "redis-kill-ablation.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        ablation = list(csv.DictReader(handle))

    return {
        "name": root.name,
        "runs": runs,
        "progress": progress,
        "ablation": ablation,
        "coverage": json.loads(
            (root / "analysis" / "coverage.json").read_text(encoding="utf-8")
        ),
    }


def extract_comparison(root: Path) -> dict:
    """Just enough of another collection to test the shared-seed claim against it."""
    seeds, applied = [], {}
    for line in (root / "matrix-progress.jsonl").read_text(encoding="utf-8").splitlines():
        seeds.append(json.loads(line)["seed"])
    with (root / "analysis" / "redis-kill-ablation.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        for row in csv.DictReader(handle):
            if row["system"] == "AEP_FULL":
                applied[row["response_class"]] = int(
                    row["executions_with_an_applied_effect"]
                )
    return {"name": root.name, "seeds": seeds, "aep_full_applied": applied}


def build_fixture(sessions: list[Path], comparison: list[Path]) -> dict:
    return {
        "sessions": [extract_session(root) for root in sessions],
        "comparison": [extract_comparison(root) for root in comparison],
    }


# ------------------------------------------------------------------ analysis


def mechanism_checks(session: dict) -> dict:
    mechanisms = Counter(r["redis_fault_mechanism"] for r in session["runs"])
    points = Counter(str(r["redis_kill_point"]) for r in session["runs"])
    delays = Counter(str(r["redis_kill_delay_ms"]) for r in session["runs"])
    no_kill = sum(1 for r in session["runs"] if not r["has_kill_event"])
    total = len(session["runs"])

    failures = []
    if set(mechanisms) - {EXPECTED_MECHANISM}:
        failures.append(f"mechanism {sorted(set(mechanisms))}")
    if set(points) - {EXPECTED_KILL_POINT}:
        failures.append(f"kill point {sorted(set(points))}")
    if set(delays) - {str(EXPECTED_DELAY_MS)}:
        failures.append(f"delay {sorted(set(delays))}")
    if total and no_kill / total > NO_KILL_TOLERANCE:
        failures.append(f"{no_kill}/{total} runs had no kill event")

    return {
        "runs": total,
        "mechanisms": dict(mechanisms),
        "kill_points": dict(points),
        "delays": dict(delays),
        "runs_with_no_kill_event": no_kill,
        "failures": failures,
    }


def replay_check(sessions: list[dict]) -> dict:
    """Are these independent sessions, or one collection run twice?"""
    if len(sessions) < 2:
        return {"comparable": False}
    first, second = sessions[0], sessions[1]
    seeds_a = {r["seed"] for r in first["progress"]}
    seeds_b = {r["seed"] for r in second["progress"]}

    keyed_a = {(r["system"], r["endpoint"], r["repetition"]): r for r in first["progress"]}
    keyed_b = {(r["system"], r["endpoint"], r["repetition"]): r for r in second["progress"]}
    shared_keys = sorted(set(keyed_a) & set(keyed_b))
    same_seed = sum(1 for k in shared_keys if keyed_a[k]["seed"] == keyed_b[k]["seed"])
    same_outcome = sum(
        1 for k in shared_keys if keyed_a[k]["outcome"] == keyed_b[k]["outcome"]
    )

    is_replay = same_seed == len(shared_keys) and same_outcome == len(shared_keys)
    return {
        "comparable": True,
        "distinct_seeds_per_session": [len(seeds_a), len(seeds_b)],
        "seeds_shared": len(seeds_a & seeds_b),
        "runs_compared": len(shared_keys),
        "same_seed": same_seed,
        "same_outcome": same_outcome,
        "is_deterministic_replay": is_replay,
        # If session 2 reproduces session 1 exactly, it carries no independent
        # information about the counts. Saying so is the point of this block.
        "effective_runs": (
            len(first["progress"]) if is_replay
            else sum(len(s["progress"]) for s in sessions)
        ),
        "nominal_runs": sum(len(s["progress"]) for s in sessions),
    }


def comparison_check(comparison: list[dict]) -> dict:
    """Does another collection share seeds too -- and did it vary anyway?"""
    if len(comparison) < 2:
        return {"comparable": False}
    sets = [set(entry["seeds"]) for entry in comparison]
    shared = set.intersection(*sets)
    varied = {}
    for klass in set().union(*(e["aep_full_applied"] for e in comparison)):
        values = [e["aep_full_applied"].get(klass) for e in comparison]
        varied[klass] = {"per_session": values, "varied": len(set(values)) > 1}
    return {
        "comparable": True,
        "sessions": [entry["name"] for entry in comparison],
        "distinct_seeds_per_session": [len(s) for s in sets],
        "seeds_shared_by_all": len(shared),
        "shares_a_seed_set": all(len(shared) == len(s) for s in sets),
        "aep_full_applied": varied,
        "any_class_varied": any(v["varied"] for v in varied.values()),
    }


def interleaving(session: dict) -> dict:
    records = sorted(session["progress"], key=lambda r: r["started_at"])
    letters = ["A" if r["system"] == "AEP_FULL" else "B" for r in records]
    longest = current = 1
    for previous, this in zip(letters, letters[1:]):
        if this == previous:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    positions: dict[str, list[int]] = {"A": [], "B": []}
    for index, letter in enumerate(letters):
        positions[letter].append(index)
    return {
        "first_24": " ".join(letters[:24]),
        "longest_same_arm_streak": longest,
        "adjacent_same_arm_pairs": sum(
            1 for a, b in zip(letters, letters[1:]) if a == b
        ),
        "adjacent_pairs": len(letters) - 1,
        "mean_position": {
            key: round(sum(value) / len(value), 1) for key, value in positions.items()
        },
        "midpoint": len(letters) / 2,
    }


def applied_counts(session: dict) -> dict:
    out: dict[str, dict[str, int]] = {}
    for row in session["ablation"]:
        out.setdefault(row["response_class"], {})[row["system"]] = int(
            row["executions_with_an_applied_effect"]
        )
    return out


def analyse(fixture: dict) -> dict:
    sessions = fixture["sessions"]
    report: dict = {
        "pre_registered": {
            "tie_at_or_below": TIE_AT_OR_BELOW,
            "not_a_tie_at_or_above": NOT_A_TIE_AT_OR_ABOVE,
            "ceiling": CEILING,
            "mechanism": EXPECTED_MECHANISM,
            "kill_point": EXPECTED_KILL_POINT,
            "delay_ms": EXPECTED_DELAY_MS,
        },
        "sessions": {},
        "tie": {},
        "ceiling": {},
        "larger_than_the_tie": {},
    }

    mechanism_failures: list[str] = []
    for session in sessions:
        checks = mechanism_checks(session)
        report["sessions"][session["name"]] = {
            "mechanism": checks,
            "coverage": session["coverage"],
            "statuses": dict(Counter(r["status"] for r in session["progress"])),
            "interleaving": interleaving(session),
        }
        mechanism_failures.extend(f"{session['name']}: {f}" for f in checks["failures"])

    report["replay"] = replay_check(sessions)
    report["comparison"] = comparison_check(fixture.get("comparison", []))

    for session in sessions:
        counts = applied_counts(session)
        for klass in CLASSES:
            pair = counts.get(klass)
            if not pair:
                continue
            aep, b3 = pair["AEP_FULL"], pair["B3_INTENT_NO_BARRIER"]
            difference = abs(aep - b3)
            if difference <= TIE_AT_OR_BELOW:
                verdict = "TIE"
            elif difference >= NOT_A_TIE_AT_OR_ABOVE:
                verdict = "NOT A TIE"
            else:
                verdict = "INCONCLUSIVE"
            report["tie"].setdefault(session["name"], {})[klass] = {
                "AEP_FULL": aep,
                "B3_INTENT_NO_BARRIER": b3,
                "difference": difference,
                "verdict": verdict,
            }
            for system in SYSTEMS:
                value = pair[system]
                state = (
                    "BELOW" if value < CEILING
                    else "AT THRESHOLD" if value == CEILING
                    else "OK"
                )
                report["ceiling"].setdefault(session["name"], {}).setdefault(
                    klass, {}
                )[system] = {"applied": value, "of": RUNS_PER_CELL, "state": state}
                if value < CEILING:
                    mechanism_failures.append(
                        f"{session['name']}/{klass}/{system}: {value} < {CEILING}"
                    )

    for session in sessions:
        for row in session["ablation"]:
            lost = int(row["lost_effects"])
            duplicates = int(row["undetected_duplicates"])
            if lost or duplicates:
                report["larger_than_the_tie"].setdefault(session["name"], []).append(
                    {
                        "response_class": row["response_class"],
                        "system": row["system"],
                        "lost_effects": lost,
                        "undetected_duplicates": duplicates,
                    }
                )

    report["mechanism_failures"] = mechanism_failures
    report["verdicts"] = dict(
        Counter(
            entry["verdict"]
            for classes in report["tie"].values()
            for entry in classes.values()
        )
    )
    report["at_threshold"] = [
        f"{name}/{klass}/{system}"
        for name, classes in report["ceiling"].items()
        for klass, systems in classes.items()
        for system, entry in systems.items()
        if entry["state"] == "AT THRESHOLD"
    ]
    return report


def render(report: dict) -> str:
    lines = ["########## mechanism checks (pre-registered signatures) ##########"]
    for name, entry in report["sessions"].items():
        checks = entry["mechanism"]
        lines.append(
            f"  {name:28s} runs={checks['runs']:3d} mechanism={checks['mechanisms']} "
            f"point={checks['kill_points']} delay={checks['delays']} "
            f"no_kill={checks['runs_with_no_kill_event']}"
        )
        coverage = entry["coverage"]
        lines.append(
            f"    E5: runs {coverage['runs']} executions {coverage['executions']} "
            f"clock_drops={coverage['runs_dropped_for_clock_suspension']} "
            f"worst_suspension={coverage['worst_suspension_seconds']} "
            f"sigkill={coverage['all_runs_used_real_sigkill']} "
            f"statuses={entry['statuses']}"
        )
        weave = entry["interleaving"]
        lines.append(
            f"    interleaving: {weave['first_24']} ... streak={weave['longest_same_arm_streak']} "
            f"adjacent={weave['adjacent_same_arm_pairs']}/{weave['adjacent_pairs']} "
            f"meanpos A={weave['mean_position']['A']} B={weave['mean_position']['B']} "
            f"(midpoint {weave['midpoint']})"
        )

    replay = report["replay"]
    lines.append("")
    lines.append("########## are the sessions independent? ##########")
    if replay.get("comparable"):
        lines.append(
            f"  seeds shared between sessions: {replay['seeds_shared']} of "
            f"{replay['distinct_seeds_per_session'][0]}"
        )
        lines.append(
            f"  same seed per (system, endpoint, repetition): "
            f"{replay['same_seed']}/{replay['runs_compared']}"
        )
        lines.append(
            f"  identical per-run outcome tuple: "
            f"{replay['same_outcome']}/{replay['runs_compared']}"
        )
        lines.append(
            f"  -> {'DETERMINISTIC REPLAY' if replay['is_deterministic_replay'] else 'independent'}; "
            f"effective runs {replay['effective_runs']} of {replay['nominal_runs']} nominal"
        )

    compare = report["comparison"]
    if compare.get("comparable"):
        lines.append("")
        lines.append("########## the same shared-seed design elsewhere ##########")
        lines.append(f"  sessions: {compare['sessions']}")
        lines.append(
            f"  shares a seed set: {compare['shares_a_seed_set']} "
            f"({compare['seeds_shared_by_all']} shared)"
        )
        for klass, entry in sorted(compare["aep_full_applied"].items()):
            lines.append(
                f"    AEP_FULL {klass:26s} per session {entry['per_session']}  "
                f"varied={entry['varied']}"
            )
        lines.append(f"  any class varied: {compare['any_class_varied']}")

    lines.append("")
    lines.append("########## THE TIE CRITERION ##########")
    for name, classes in report["tie"].items():
        for klass, entry in classes.items():
            lines.append(
                f"  {name:28s} {klass:26s} AEP={entry['AEP_FULL']:2d}/30 "
                f"B3={entry['B3_INTENT_NO_BARRIER']:2d}/30 "
                f"|diff|={entry['difference']} -> {entry['verdict']}"
            )

    lines.append("")
    lines.append("########## ceiling ##########")
    for name, classes in report["ceiling"].items():
        for klass, systems in classes.items():
            for system, entry in systems.items():
                lines.append(
                    f"  {name:28s} {klass:26s} {system:22s} "
                    f"{entry['applied']:2d}/{entry['of']}  {entry['state']}"
                )
    if report["at_threshold"]:
        lines.append(
            "  NOTE: cells marked AT THRESHOLD sit exactly on the pre-registered "
            "floor and are one run from tripping it. Not headroom."
        )

    lines.append("")
    lines.append("########## results that would be larger than the tie ##########")
    if report["larger_than_the_tie"]:
        for name, entries in report["larger_than_the_tie"].items():
            for entry in entries:
                lines.append(f"  ** {name} {entry} **")
    else:
        lines.append(
            "  lost_effect_executions and undetected_duplicate_applications: "
            "zero in every cell, as predicted"
        )

    lines.append("")
    if report["mechanism_failures"]:
        lines.append("MECHANISM FAILURE SIGNATURES PRESENT:")
        lines.extend(f"  - {line}" for line in report["mechanism_failures"])
    else:
        lines.append(
            "No mechanism-failure signature present: the injector delivered the "
            "pre-registered fault, so the counts are about the protocol."
        )
    lines.append(f"OVERALL: {report['verdicts']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session", action="append", default=[])
    parser.add_argument("--compare", action="append", default=[])
    parser.add_argument("--fixture", default=None)
    parser.add_argument("--emit-fixture", default=None)
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    if arguments.fixture:
        fixture = json.loads(Path(arguments.fixture).read_text(encoding="utf-8"))
    else:
        if not arguments.session:
            parser.error("give --fixture, or at least one --session")
        fixture = build_fixture(
            [Path(p) for p in arguments.session],
            [Path(p) for p in arguments.compare],
        )

    if arguments.emit_fixture:
        Path(arguments.emit_fixture).write_text(
            json.dumps(fixture, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"wrote {arguments.emit_fixture}")

    report = analyse(fixture)
    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    sys.stdout.write(render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
