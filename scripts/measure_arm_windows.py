r"""How long is each arm exposed after the fault is armed? From existing logs.

The design question a synchronous fault cannot dodge
----------------------------------------------------
The kill point ``after_intent_before_barrier`` resolves to
``CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER``
(`experiments/harness/crash_points.py:113`), which is
`aep_core/core/intent_workflow.py:442` -- **immediately before**
``_confirm_dispatch_barrier``, the ``WAITAOF`` call, at line 446.

The obvious way to make the fault deterministic is to freeze Redis
*synchronously at that checkpoint*, so ``WAITAOF`` is issued into a frozen
server and can never return. **That does not work, and the reason matters.**

B3 reaches the same checkpoint -- it is the full ``WriteAheadRunner`` with the
barrier ablated (`experiments/baselines/crash_points.py:155-160`) -- and after
it, B3 still performs `authorize_dispatch` and `preflight`, both of which are
Redis calls (`intent_workflow.py:479, 494`). A server frozen *at* the checkpoint
blocks those too, so B3 would stop dispatching and its 28/30 ceiling would
collapse. The contrast would vanish, and it would vanish because the injector
disabled both arms rather than because the protocol did anything.

**The asymmetry the experiment measures IS a timing difference**: AEP-full has
one extra Redis-dependent step, ``WAITAOF``, that B3 does not, and it is slow
(0-1000 ms under ``appendfsync everysec``) where B3's remaining calls are fast.
So the fault must land in a window B3 has already left and AEP-full is still in.
That window can be *widened* and its boundary *measured*, but it cannot be
removed without removing the phenomenon.

This script measures both arms' post-arming exposure from the event logs of
collections that already exist, so the arming delay is chosen from data rather
than guessed.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

#: The event the injector emits when it arms, and the events that mark each
#: arm leaving its exposed window.
ARMED = "redis_kill_armed"
ISSUED = "redis_kill_issued"


def _events(run: Path) -> list[dict]:
    out: list[dict] = []
    for log in sorted(run.glob("events*.jsonl")):
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    out.sort(key=lambda r: r.get("monotonic_ns", 0))
    return out


def window_for(run: Path) -> dict | None:
    events = _events(run)
    armed = next((e for e in events if e.get("event") == ARMED), None)
    if armed is None or "monotonic_ns" not in armed:
        return None
    t0 = int(armed["monotonic_ns"])

    def first_after(*names: str) -> int | None:
        for event in events:
            if event.get("event") in names and int(event.get("monotonic_ns", 0)) >= t0:
                return int(event["monotonic_ns"])
        return None

    issued = next(
        (e for e in events if e.get("event") == ISSUED and "issue_to_return_ns" in e),
        None,
    )
    names = sorted({str(e.get("event")) for e in events})
    return {
        "run": run.name,
        "armed_monotonic_ns": t0,
        "event_names": names,
        "kill_command_ms": (
            round(int(issued["issue_to_return_ns"]) / 1e6, 1) if issued else None
        ),
        # Whatever the run's own vocabulary calls the moment the provider was
        # contacted; tried in order, so the script works across the schema
        # changes these collections span.
        "to_dispatch_ms": _delta(
            t0,
            first_after(
                "provider_request_sent",
                "dispatch_transmitted",
                "request_transmitted",
                "provider_request",
                "execution_dispatched",
            ),
        ),
        "to_resolved_ms": _delta(t0, first_after("execution_resolved")),
        "to_barrier_failure_ms": _delta(
            t0, first_after("durability_barrier_failed", "dispatch_barrier_failed")
        ),
    }


def _delta(t0: int, t1: int | None) -> float | None:
    return None if t1 is None else round((t1 - t0) / 1e6, 1)


def summarise(values: list[float]) -> dict:
    if not values:
        return {}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "min": round(ordered[0], 1),
        "p05": round(ordered[max(0, int(0.05 * (len(ordered) - 1)))], 1),
        "median": round(statistics.median(ordered), 1),
        "p95": round(ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))], 1),
        "max": round(ordered[-1], 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", action="append", default=[], required=True)
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    report: dict = {"systems": {}}
    per_system: dict[str, dict[str, list[float]]] = {}
    vocabulary: set[str] = set()

    for spec in arguments.root:
        base = Path(spec)
        if not base.is_dir():
            print(f"missing {spec}", file=sys.stderr)
            continue
        for run in sorted(d for d in base.iterdir() if d.is_dir() and d.name != "analysis"):
            result = window_for(run)
            if result is None:
                continue
            vocabulary.update(result["event_names"])
            system = run.name.split("-")[0]
            bucket = per_system.setdefault(system, {})
            for key in ("to_dispatch_ms", "to_resolved_ms", "to_barrier_failure_ms",
                        "kill_command_ms"):
                if result[key] is not None:
                    bucket.setdefault(key, []).append(result[key])

    print("Post-arming exposure, per system, in ms")
    print(f"{'system':28s} {'measure':22s} {'n':>4s} {'min':>8s} {'p05':>8s} "
          f"{'median':>8s} {'p95':>8s} {'max':>8s}")
    print("-" * 100)
    for system, measures in sorted(per_system.items()):
        for key, values in sorted(measures.items()):
            s = summarise(values)
            print(
                f"{system:28s} {key:22s} {s['n']:4d} {s['min']:8.1f} {s['p05']:8.1f} "
                f"{s['median']:8.1f} {s['p95']:8.1f} {s['max']:8.1f}"
            )
            report["systems"].setdefault(system, {})[key] = s
    report["event_vocabulary_seen"] = sorted(vocabulary)
    print()
    print("event names seen in these logs:")
    for name in sorted(vocabulary):
        print(f"  {name}")

    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
