r"""Every number in `reports/raw/phase13-armA-model-gap.md`, regenerated from runs.

That note is load-bearing for §VI-C2: it establishes that the landing-latency
model failed on two independent premises rather than one miscalibration. It was
first computed by one-off probes, which is not a standard any of its numbers
should reach the manuscript under. This script is those probes, promoted.

**What it measures, and why each source is the one it is.**

* The `WAITAOF` wait is `redis_kill_armed` -> `durability_ack_observed`, both
  from the *worker's* own monotonic clock. The runner and recovery processes
  have separate clocks; mixing them would silently inject the offset between
  them into every wait.
* The exposure window's close, for a run that never acked, is
  `execution_failed`. Whether that abort is the lock lease, a barrier timeout or
  the fault landing is **not** decidable from the events -- see §6 of the note.
  This script measures when it happened and claims nothing about why.
* In-situ `docker kill` latency is `redis_kill_latency_ms` from
  `analysis/per-execution.csv` (`experiments/analyze.py:563` derives it from
  `issue_to_return_ns`), which is the same quantity the bench reported as
  `command_ms`. It times the *call*, not Redis's death.
* In-situ `docker pause` latency is `redis_kill_issued.pause_ms`, which exists
  only in the Arm A collections.
* Applied counts come from `analysis/redis-kill-ablation.csv`, column
  `executions_with_an_applied_effect`, read exactly as `\UnwantedPrevented`
  reads it.

Percentiles are index-based on the sorted sample (`p25 = s[n//4]`,
`p75 = s[3n//4]`), which is what the note's figures were computed with. They are
fixed here rather than left to a library default so the published numbers stay
reproducible.

Usage::

    # from the measurement host, where the session roots live
    python scripts/analyse_model_gap.py \
        --uncontrolled /root/aep-phase8/experiments/results/b2-paired-v2-s1-2026-08-28 \
        ... \
        --controlled /root/aep-phase13/armA-s1-2026-09-03 ... \
        --emit-fixture tests/fixtures/model-gap/runs.json

    # anywhere, from the committed fixture
    python scripts/analyse_model_gap.py --fixture tests/fixtures/model-gap/runs.json
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The bench landings the model was built on, from the committed measurement.
BENCH = REPO_ROOT / "reports" / "raw" / "phase13-fault-landing.json"

#: The model's own numbers, from the pre-registration. Constants, not fitted.
MODEL_UNCONTROLLED = 0.368
MODEL_CONTROLLED = 0.058

#: Histogram bin width for the wait distribution, in ms.
BIN_MS = 100


# ---------------------------------------------------------------- extraction


def _worker_events(run: Path) -> list[dict]:
    """Worker-process events only -- one process, one monotonic clock."""
    out = []
    for log in sorted(run.glob("events-worker-*.jsonl")):
        for line in log.read_text(errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _first(events: list[dict], name: str, key: str = "monotonic_ns"):
    for record in events:
        if record.get("event") == name:
            return record.get(key)
    return None


def extract_runs(root: Path) -> list[dict]:
    """One record per run that reached the fault checkpoint."""
    rows = []
    for run in sorted(root.iterdir()):
        if not run.is_dir() or run.name == "analysis":
            continue
        events = _worker_events(run)
        armed = _first(events, "redis_kill_armed")
        if armed is None:
            # A run the harness refused before arming: no race happened in it.
            continue
        ack = _first(events, "durability_ack_observed")
        failed = _first(events, "execution_failed")
        rows.append({
            "session": root.name,
            "run": run.name,
            "system": "AEP_FULL" if run.name.startswith("aep_full") else "B3",
            "endpoint": run.name.split("-")[2],
            "acked": ack is not None,
            "wait_ms": round((ack - armed) / 1e6, 4) if ack else None,
            "abort_ms": round((failed - armed) / 1e6, 4) if failed else None,
            "transmitted": _first(events, "provider_request_transmitted") is not None,
            "pause_ms": _first(events, "redis_kill_issued", "pause_ms"),
            "total_ms": _first(events, "redis_kill_issued", "total_ms"),
        })
    return rows


def extract_kill_latencies(root: Path) -> list[float]:
    """`redis_kill_latency_ms` -- recorded for the Phase-8.4 sessions only."""
    path = root / "analysis" / "per-execution.csv"
    if not path.is_file():
        return []
    values = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get("redis_kill_latency_ms") or "").strip()
            if raw:
                try:
                    values.append(float(raw))
                except ValueError:
                    continue
    return values


def extract_applied(root: Path) -> list[dict]:
    """AEP-full's applied effects per capability class."""
    path = root / "analysis" / "redis-kill-ablation.csv"
    if not path.is_file():
        return []
    out = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["system"] != "AEP_FULL":
                continue
            out.append({
                "session": root.name,
                "response_class": row["response_class"],
                "applied": int(row["executions_with_an_applied_effect"]),
                "executions": int(row["executions"]),
            })
    return out


def build_fixture(uncontrolled: list[Path], controlled: list[Path]) -> dict:
    return {
        "uncontrolled": {
            "runs": [r for root in uncontrolled for r in extract_runs(root)],
            "kill_latency_ms": [
                v for root in uncontrolled for v in extract_kill_latencies(root)
            ],
            "applied": [r for root in uncontrolled for r in extract_applied(root)],
        },
        "controlled": {
            "runs": [r for root in controlled for r in extract_runs(root)],
            "kill_latency_ms": [],
            "applied": [r for root in controlled for r in extract_applied(root)],
        },
    }


# ------------------------------------------------------------------ analysis


def summarise(values) -> dict | None:
    s = sorted(v for v in values if v is not None)
    if not s:
        return None
    return {
        "n": len(s),
        "min": round(s[0], 1),
        "p25": round(s[len(s) // 4], 1),
        "median": round(statistics.median(s), 1),
        "p75": round(s[3 * len(s) // 4], 1),
        "max": round(s[-1], 1),
    }


def arm_side(group: dict, bench_landing: float) -> dict:
    runs = group["runs"]
    aep = [r for r in runs if r["system"] == "AEP_FULL"]
    b3 = [r for r in runs if r["system"] == "B3"]
    acked = [r for r in aep if r["acked"]]
    waits = [r["wait_ms"] for r in acked if r["wait_ms"] is not None]
    aborts = [r["abort_ms"] for r in aep if not r["acked"] and r["abort_ms"] is not None]

    # Empirical F(x): the fraction of ALL AEP-full runs whose wait was below x.
    # Only valid below the earliest abort; past that a non-acking run might have
    # acked later and the sample is censored.
    censor = min(aborts) if aborts else None
    cdf = {}
    for x in (25, 29, 58, 100, 200, 368, 500, 668):
        if censor is not None and x > censor:
            continue
        empirical = sum(1 for w in waits if w < x) / len(aep)
        cdf[str(x)] = {
            "empirical": round(empirical, 4),
            "uniform": round(x / 1000, 4),
            "uniform_overstates_by": (
                round((x / 1000) / empirical, 1) if empirical else None
            ),
        }

    histogram = {}
    for w in waits:
        edge = int(w // BIN_MS) * BIN_MS
        histogram[str(edge)] = histogram.get(str(edge), 0) + 1

    per_session = {}
    for record in aep:
        entry = per_session.setdefault(
            record["session"], {"n": 0, "acked": 0, "after_bench_landing": 0, "waits": []}
        )
        entry["n"] += 1
        if record["acked"]:
            entry["acked"] += 1
            entry["waits"].append(record["wait_ms"])
            if record["wait_ms"] > bench_landing:
                entry["after_bench_landing"] += 1
    for entry in per_session.values():
        entry["ack_rate"] = round(entry["acked"] / entry["n"], 3)
        entry["after_bench_landing_rate"] = round(entry["after_bench_landing"] / entry["n"], 3)
        entry["max_wait_ms"] = round(max(entry["waits"]), 1) if entry["waits"] else None
        del entry["waits"]

    applied_total = sum(a["applied"] for a in group["applied"])
    executions_total = sum(a["executions"] for a in group["applied"])
    by_class: dict[str, dict] = {}
    for record in group["applied"]:
        entry = by_class.setdefault(record["response_class"], {"applied": 0, "executions": 0})
        entry["applied"] += record["applied"]
        entry["executions"] += record["executions"]
    for entry in by_class.values():
        entry["rate"] = round(entry["applied"] / entry["executions"], 4)

    by_endpoint: dict[str, dict] = {}
    for record in aep:
        entry = by_endpoint.setdefault(record["endpoint"], {"n": 0, "acked": 0})
        entry["n"] += 1
        entry["acked"] += bool(record["acked"])
    for entry in by_endpoint.values():
        entry["ack_rate"] = round(entry["acked"] / entry["n"], 4)

    return {
        "aep_full_runs": len(aep),
        "acked": len(acked),
        "ack_rate": round(len(acked) / len(aep), 4),
        "transmitted": sum(1 for r in aep if r["transmitted"]),
        "applied": applied_total,
        "executions": executions_total,
        "applied_rate": round(applied_total / executions_total, 4) if executions_total else None,
        "applied_by_class": by_class,
        "ack_by_endpoint": by_endpoint,
        "wait_ms": summarise(waits),
        "b3_no_barrier_wait_ms": summarise(
            [r["wait_ms"] for r in b3 if r["wait_ms"] is not None]
        ),
        "abort_ms_non_acking": summarise(aborts),
        "uncensored_below_ms": round(censor, 1) if censor is not None else None,
        "acks_after_bench_landing": sum(1 for w in waits if w > bench_landing),
        "acks_after_bench_landing_rate": round(
            sum(1 for w in waits if w > bench_landing) / len(aep), 4
        ),
        "empirical_cdf": cdf,
        "wait_histogram": dict(sorted(histogram.items(), key=lambda kv: int(kv[0]))),
        "per_session": per_session,
        "in_situ_kill_latency_ms": summarise(group["kill_latency_ms"]),
        "in_situ_pause_ms": summarise([r["pause_ms"] for r in runs]),
        "in_situ_total_ms": summarise([r["total_ms"] for r in runs]),
    }


def bench_numbers() -> dict:
    data = json.loads(BENCH.read_text(encoding="utf-8"))
    out = {}
    for entry in data["results"]:
        out[entry["mechanism"]] = {
            "command_ms_median": entry["command_ms"]["median"],
            "command_ms_min": entry["command_ms"]["min"],
            "command_ms_max": entry["command_ms"]["max"],
            "landing_ms_median": entry["landing_ms"]["median"],
            "landing_ms_min": entry["landing_ms"]["min"],
            "landing_ms_max": entry["landing_ms"]["max"],
        }
    out["landing_measurement_floor_ms"] = data["results"][0].get(
        "landing_measurement_floor_ms"
    )
    return out


def analyse(fixture: dict) -> dict:
    bench = bench_numbers()
    kill_landing = bench["docker-kill"]["landing_ms_median"]
    pause_landing = bench["docker-pause"]["landing_ms_median"]

    uncontrolled = arm_side(fixture["uncontrolled"], kill_landing)
    controlled = arm_side(fixture["controlled"], pause_landing)

    no_readback = uncontrolled["applied_by_class"].get("NO_READBACK", {})
    ledger = uncontrolled["ack_by_endpoint"].get("ledger_postings", {})

    ratios = {
        # premise (a): the bench call against the same call, in situ
        "in_situ_kill_over_bench": round(
            uncontrolled["in_situ_kill_latency_ms"]["median"]
            / bench["docker-kill"]["command_ms_median"], 2
        ),
        "bench_ranges_disjoint": (
            bench["docker-kill"]["command_ms_max"]
            < uncontrolled["in_situ_kill_latency_ms"]["min"]
        ),
        # how far Arm A narrowed the window
        "window_narrowed_by": round(kill_landing / pause_landing, 1),
        # premise (b) at each arm's scale
        "uniform_overstates_at_58ms": uncontrolled["empirical_cdf"]["58"][
            "uniform_overstates_by"
        ],
        "uniform_overstates_at_368ms": uncontrolled["empirical_cdf"]["368"][
            "uniform_overstates_by"
        ],
        # the calibration, against the quantity the model predicts
        "model_vs_uncontrolled_dispatch": round(
            uncontrolled["ack_rate"] / MODEL_UNCONTROLLED, 2
        ),
        "model_vs_no_readback_dispatch": round(
            ledger.get("ack_rate", 0) / MODEL_UNCONTROLLED, 2
        ) if ledger else None,
        "dispatch_not_applied_loss_no_readback": round(
            1 - no_readback.get("rate", 0) / ledger["ack_rate"], 2
        ) if ledger and no_readback else None,
        # the controlled arm's realised over-prediction
        "model_over_dispatch_controlled": round(
            MODEL_CONTROLLED / controlled["ack_rate"], 1
        ) if controlled["ack_rate"] else None,
        "model_over_applied_controlled": round(
            MODEL_CONTROLLED / controlled["applied_rate"], 1
        ) if controlled["applied_rate"] else None,
    }

    return {
        "bench": bench,
        "model": {
            "uncontrolled": MODEL_UNCONTROLLED,
            "controlled": MODEL_CONTROLLED,
        },
        "uncontrolled": uncontrolled,
        "controlled": controlled,
        "ratios": ratios,
    }


def render(report: dict) -> str:
    lines = []
    for arm in ("uncontrolled", "controlled"):
        side = report[arm]
        lines.append(f"########## {arm.upper()} ##########")
        lines.append(f"  AEP-full runs {side['aep_full_runs']}  acked {side['acked']} "
                     f"= {side['ack_rate']}  transmitted {side['transmitted']}")
        lines.append(f"  applied {side['applied']}/{side['executions']} = {side['applied_rate']}")
        lines.append(f"  wait_ms            {side['wait_ms']}")
        lines.append(f"  b3 no-barrier      {side['b3_no_barrier_wait_ms']}")
        lines.append(f"  abort (non-acking) {side['abort_ms_non_acking']}")
        lines.append(f"  uncensored below   {side['uncensored_below_ms']} ms")
        lines.append(f"  acks after bench landing: {side['acks_after_bench_landing']} "
                     f"({side['acks_after_bench_landing_rate']} of runs)")
        lines.append(f"  in-situ kill latency {side['in_situ_kill_latency_ms']}")
        lines.append(f"  in-situ pause_ms     {side['in_situ_pause_ms']}")
        lines.append("  empirical F(x) vs uniform:")
        for x, entry in side["empirical_cdf"].items():
            lines.append(f"    {x:>5} ms  empirical={entry['empirical']:.4f}  "
                         f"uniform={entry['uniform']:.4f}  "
                         f"overstates={entry['uniform_overstates_by']}x")
        lines.append("  wait histogram (100 ms bins):")
        for edge, count in side["wait_histogram"].items():
            lines.append(f"    {int(edge):5d}-{int(edge)+99:5d} ms  {'#' * count} ({count})")
        lines.append("  per session:")
        for name, entry in side["per_session"].items():
            lines.append(f"    {name:34s} n={entry['n']:3d} acked={entry['acked']:3d} "
                         f"({entry['ack_rate']}) after-landing={entry['after_bench_landing']:3d} "
                         f"({entry['after_bench_landing_rate']}) max_wait={entry['max_wait_ms']}")
        lines.append("  applied by class:")
        for name, entry in sorted(side["applied_by_class"].items()):
            lines.append(f"    {name:26s} {entry['applied']:3d}/{entry['executions']:3d} = {entry['rate']}")
        lines.append("  ack by endpoint:")
        for name, entry in sorted(side["ack_by_endpoint"].items()):
            lines.append(f"    {name:26s} {entry['acked']:3d}/{entry['n']:3d} = {entry['ack_rate']}")
        lines.append("")
    lines.append("########## RATIOS THE NOTE QUOTES ##########")
    for name, value in report["ratios"].items():
        lines.append(f"  {name:36s} {value}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--uncontrolled", action="append", default=[])
    parser.add_argument("--controlled", action="append", default=[])
    parser.add_argument("--fixture", default=None, help="read runs from here instead")
    parser.add_argument("--emit-fixture", default=None)
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    if arguments.fixture:
        fixture = json.loads(Path(arguments.fixture).read_text(encoding="utf-8"))
    else:
        if not arguments.uncontrolled or not arguments.controlled:
            parser.error("give --fixture, or both --uncontrolled and --controlled")
        fixture = build_fixture(
            [Path(p) for p in arguments.uncontrolled],
            [Path(p) for p in arguments.controlled],
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
