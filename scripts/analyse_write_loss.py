r"""WS-4's verdict, applying only what `d8b2ca5` pre-registered.

**Written before any write-loss data exists**, so nothing in it can have been
chosen to fit an observed result. Phase 13's verdict script landed after its
first session; this one does not, and that is the point of the ordering.

`reports/phase-report-ws4-prediction-2026-09-04.md` fixes:

* **the prediction** — AEP-full withholds dispatch when the record it depends on
  was destroyed, at or near **0** applied effects of 300 executions; B3, having
  no barrier to withhold on, proceeds at or near **ceiling**;
* **two exact quantities** — `lost_effect_executions` **0** for AEP-full (it does
  not dispatch, so there is nothing to lose) and
  `undetected_duplicate_applications` **0** for both arms;
* **three plausible Redis behaviours** when its AOF device fails, of which the
  third *"would complicate the reading"*.

**Why the behaviour is reported and not just the numbers.** A verdict that can
only say *held* or *refuted* is scoring the pre-registration, not applying it.
The pre-registration named a behaviour that would make the prediction hold for a
reason it did not anticipate, so the script must be able to say exactly that.
:func:`classify_reading` is where the numbers and the behaviour are combined, and
it is the reason this file exists rather than a one-line comparison.

**Attribution.** By execution — which for this cell *is* by target, because the
workload gives every execution its own resource
(``target = f"account-{execution_id}"``, `experiments/harness/workload.py`), so
the target encodes the execution. **The WS-1a execution-id column does not
exist**: it was reverted in `74ea31f` when the framing decision moved to Option
A, and `analyze.py` attributes by target alone. That is sound here and would not
be under an agent workload that re-plans onto a used target.

**Unit of analysis: the run** (`docs/26` §3 rule 6). Per-run counts are reported
and the run is what the spread is taken over; executions are never pooled as
independent draws.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# --------------------------------------------------------------- the criteria
#
# The pre-registration says "at or near 0" and "at or near ceiling" without
# fixing numbers. These are fixed HERE, before any data exists, and the band
# edges are taken from project precedent rather than invented: Phase 13 used
# >= 27/30 = 0.90 for "at ceiling", and WS-4 §5 bounds tolerated non-delivery at
# 5%, which is the most AEP-full could apply without the fault having failed.

#: AEP-full applied rate at or below this is "at or near 0".
AEP_HELD_AT_OR_BELOW = 0.05
#: Above this, the prediction is refuted rather than merely unclear.
AEP_REFUTED_ABOVE = 0.20
#: B3 applied rate at or above this is "at or near ceiling" (Phase 13's 27/30).
B3_CEILING_AT_OR_ABOVE = 0.90
#: Below this, B3 did not proceed and the contrast is not the predicted one.
B3_REFUTED_BELOW = 0.70

#: A barrier that blocked rather than erroring is distinguished by how long it
#: waited. `appendfsync everysec` gives WAITAOF a ~1000 ms window, so a wait that
#: exceeds it did not simply get an error back.
BLOCKED_THRESHOLD_MS = 1000.0

AEP = "AEP_FULL"
B3 = "B3_INTENT_NO_BARRIER"


class Behaviour(str, Enum):
    """Which of `d8b2ca5` §2's three Redis behaviours was observed."""

    #: WAITAOF returned an error. Anticipated.
    WAITAOF_ERROR = "WAITAOF_ERROR"
    #: WAITAOF blocked until timeout. Anticipated.
    BLOCKED_UNTIL_TIMEOUT = "BLOCKED_UNTIL_TIMEOUT"
    #: Redis kept serving while the append failed silently -- WAITAOF
    #: ACKNOWLEDGED after the device stopped accepting writes. This is the third
    #: behaviour, the one the pre-registration flagged as complicating.
    SILENT_APPEND_FAILURE = "SILENT_APPEND_FAILURE"
    #: The events do not distinguish. Reported as such rather than guessed.
    UNDETERMINED = "UNDETERMINED"


class Verdict(str, Enum):
    HELD = "HELD"
    INCONCLUSIVE = "INCONCLUSIVE"
    REFUTED = "REFUTED"


@dataclass
class ArmCounts:
    applied: int = 0
    executions: int = 0
    lost_effects: int = 0
    undetected_duplicates: int = 0
    per_run_applied: list[int] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.applied / self.executions if self.executions else 0.0


# ----------------------------------------------------------------- extraction


def read_ablation(root: Path) -> dict[str, ArmCounts]:
    """The estimand, read exactly as ``\\UnwantedPrevented`` reads it."""
    path = root / "analysis" / "redis-kill-ablation.csv"
    if not path.is_file():
        raise SystemExit(f"no ablation CSV at {path}")
    arms: dict[str, ArmCounts] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            arm = arms.setdefault(row["system"], ArmCounts())
            arm.applied += int(row["executions_with_an_applied_effect"])
            arm.executions += int(row["executions"])
            arm.lost_effects += int(row["lost_effects"])
            arm.undetected_duplicates += int(row["undetected_duplicates"])
    return arms


def worker_events(run: Path) -> list[dict]:
    out = []
    for log in sorted(run.glob("events-worker-*.jsonl")):
        for line in log.read_text(errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def observe_behaviour(root: Path) -> tuple[Behaviour, dict]:
    """Which Redis behaviour did AEP-full actually meet?

    The discriminator is whether a **durability acknowledgement arrived after
    the device stopped accepting writes**. If it did, `WAITAOF` returned success
    while the append could not have reached the platter -- `d8b2ca5`'s third
    behaviour, and the one that changes what a held prediction means.
    """
    acks_after_fault = 0
    aep_runs = 0
    post_arm_waits: list[float] = []
    failures = 0

    for run in sorted(root.iterdir()):
        if not run.is_dir() or run.name == "analysis":
            continue
        if not run.name.startswith("aep_full"):
            continue
        aep_runs += 1
        events = worker_events(run)

        arm_at = None
        for record in events:
            if record.get("event") == "redis_kill_issued":
                returned = record.get("monotonic_ns")
                command_ms = record.get("command_ms") or 0
                if returned is not None:
                    arm_at = returned - int(command_ms) * 1_000_000
                break
        if arm_at is None:
            continue

        for record in events:
            name = record.get("event")
            when = record.get("monotonic_ns")
            if when is None or when < arm_at:
                continue
            if name == "durability_ack_observed":
                acks_after_fault += 1
            elif name == "execution_failed":
                failures += 1
                post_arm_waits.append((when - arm_at) / 1e6)

    detail = {
        "aep_full_runs_examined": aep_runs,
        "durability_acks_after_the_fault": acks_after_fault,
        "post_fault_failures": failures,
        "post_fault_wait_ms_median": (
            round(statistics.median(post_arm_waits), 1) if post_arm_waits else None
        ),
    }

    if acks_after_fault:
        return Behaviour.SILENT_APPEND_FAILURE, detail
    if not post_arm_waits:
        return Behaviour.UNDETERMINED, detail
    if statistics.median(post_arm_waits) >= BLOCKED_THRESHOLD_MS:
        return Behaviour.BLOCKED_UNTIL_TIMEOUT, detail
    return Behaviour.WAITAOF_ERROR, detail


def per_run_applied(root: Path) -> dict[str, list[int]]:
    """Applied effects per run. The run is the unit (rule 6)."""
    path = root / "matrix-progress.jsonl"
    if not path.is_file():
        return {}
    out: dict[str, list[int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("status") != "collected":
            continue
        out.setdefault(record["system"], []).append(
            int(record.get("applied_effects_total", 0))
        )
    return out


# ------------------------------------------------------------------- the verdict


def classify_numbers(arms: dict[str, ArmCounts]) -> tuple[Verdict, list[str]]:
    """The four pre-registered quantities, and nothing else."""
    reasons: list[str] = []
    aep, b3 = arms.get(AEP), arms.get(B3)
    if aep is None or b3 is None:
        return Verdict.INCONCLUSIVE, ["one or both arms are absent from the ablation CSV"]

    if aep.rate > AEP_REFUTED_ABOVE:
        reasons.append(
            f"AEP-full applied {aep.applied}/{aep.executions} = {aep.rate:.4f}, "
            f"above the refutation threshold {AEP_REFUTED_ABOVE}"
        )
        verdict = Verdict.REFUTED
    elif aep.rate > AEP_HELD_AT_OR_BELOW:
        reasons.append(
            f"AEP-full applied {aep.rate:.4f}, above 'at or near 0' "
            f"({AEP_HELD_AT_OR_BELOW}) but not refuting"
        )
        verdict = Verdict.INCONCLUSIVE
    else:
        reasons.append(f"AEP-full applied {aep.applied}/{aep.executions} = {aep.rate:.4f}: at or near 0")
        verdict = Verdict.HELD

    if b3.rate < B3_REFUTED_BELOW:
        reasons.append(
            f"B3 applied {b3.applied}/{b3.executions} = {b3.rate:.4f}, below "
            f"{B3_REFUTED_BELOW}: it did not proceed, so the contrast is not the "
            "predicted one"
        )
        verdict = Verdict.REFUTED
    elif b3.rate < B3_CEILING_AT_OR_ABOVE:
        reasons.append(f"B3 applied {b3.rate:.4f}, below ceiling ({B3_CEILING_AT_OR_ABOVE})")
        if verdict is Verdict.HELD:
            verdict = Verdict.INCONCLUSIVE
    else:
        reasons.append(f"B3 applied {b3.applied}/{b3.executions} = {b3.rate:.4f}: at ceiling")

    # The two exact quantities. Any non-zero refutes on its own.
    if aep.lost_effects:
        reasons.append(
            f"AEP-full has {aep.lost_effects} lost effects; the prediction is 0, "
            "because it does not dispatch and so has nothing to lose"
        )
        verdict = Verdict.REFUTED
    for name, arm in ((AEP, aep), (B3, b3)):
        if arm.undetected_duplicates:
            reasons.append(
                f"{name} has {arm.undetected_duplicates} undetected duplicates; "
                "the prediction is 0 for both arms"
            )
            verdict = Verdict.REFUTED

    return verdict, reasons


def classify_reading(verdict: Verdict, behaviour: Behaviour) -> str:
    """Combine the numbers with the behaviour that produced them.

    This is the function the pre-registration's §2 requires: it must be possible
    for the script to say *the prediction held, for a reason the
    pre-registration did not anticipate*. A verdict that cannot say that is
    scoring the pre-registration rather than applying it.
    """
    if behaviour is Behaviour.SILENT_APPEND_FAILURE:
        if verdict is Verdict.HELD:
            return (
                "HELD, BUT FOR A REASON THE PRE-REGISTRATION FLAGGED AS "
                "COMPLICATING. WAITAOF acknowledged after the device stopped "
                "accepting writes, so the record AEP-full withheld on was not "
                "destroyed in the way the prediction assumes. The direction is "
                "the predicted one; the mechanism is not. Report both."
            )
        return (
            f"{verdict.value}, and the third Redis behaviour was observed: "
            "WAITAOF acknowledged after the device stopped accepting writes. "
            "Whatever the numbers say, they were not produced by the mechanism "
            "the prediction describes."
        )
    if behaviour is Behaviour.UNDETERMINED:
        return (
            f"{verdict.value}, but the events do not establish which Redis "
            "behaviour produced it. The numbers stand; the mechanism is not "
            "evidenced by this collection."
        )
    return (
        f"{verdict.value}, under a behaviour the pre-registration anticipated "
        f"({behaviour.value}). The behaviour is one of the two it named as "
        "leaving the reading intact; the verdict above is the numbers' own."
    )


def analyse(root: Path) -> dict:
    arms = read_ablation(root)
    behaviour, detail = observe_behaviour(root)
    verdict, reasons = classify_numbers(arms)
    runs = per_run_applied(root)

    return {
        "session": root.name,
        "criteria": {
            "aep_held_at_or_below": AEP_HELD_AT_OR_BELOW,
            "aep_refuted_above": AEP_REFUTED_ABOVE,
            "b3_ceiling_at_or_above": B3_CEILING_AT_OR_ABOVE,
            "b3_refuted_below": B3_REFUTED_BELOW,
            "unit_of_analysis": "run",
        },
        "arms": {
            name: {
                "applied": arm.applied,
                "executions": arm.executions,
                "rate": round(arm.rate, 4),
                "lost_effects": arm.lost_effects,
                "undetected_duplicates": arm.undetected_duplicates,
            }
            for name, arm in sorted(arms.items())
        },
        "per_run_applied": runs,
        "behaviour": behaviour.value,
        "behaviour_detail": detail,
        "verdict": verdict.value,
        "reasons": reasons,
        "reading": classify_reading(verdict, behaviour),
    }


def render(report: dict) -> str:
    lines = [f"=== WS-4 write-loss verdict: {report['session']} ===", ""]
    lines.append("--- the estimand, per arm ---")
    for name, arm in report["arms"].items():
        lines.append(
            f"  {name:22s} applied {arm['applied']:4d}/{arm['executions']:<4d} "
            f"= {arm['rate']:.4f}  lost={arm['lost_effects']} "
            f"dupes={arm['undetected_duplicates']}"
        )
    lines.append("")
    lines.append("--- per-run applied effects (the run is the unit, rule 6) ---")
    for name, runs in sorted(report["per_run_applied"].items()):
        lines.append(f"  {name:22s} n={len(runs):3d} {runs[:12]}{' ...' if len(runs) > 12 else ''}")
    lines.append("")
    lines.append("--- which Redis behaviour was observed ---")
    lines.append(f"  {report['behaviour']}")
    for key, value in report["behaviour_detail"].items():
        lines.append(f"    {key}: {value}")
    lines.append("")
    lines.append("--- verdict ---")
    lines.append(f"  numbers : {report['verdict']}")
    for reason in report["reasons"]:
        lines.append(f"    - {reason}")
    lines.append("")
    lines.append(f"  READING : {report['reading']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session", required=True)
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    report = analyse(Path(arguments.session))
    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    sys.stdout.write(render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
