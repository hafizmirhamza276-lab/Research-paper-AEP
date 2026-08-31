#!/usr/bin/env python3
"""Phase 8.4 per-session registered gates.

Reads only the frozen analysis products, so it cannot disagree with what was
committed.

WHAT HALTS (plan section 3.4, and section 3.3's integrity check). These are the
pre-registered HALT set and they exit non-zero:

  * any undetected_duplicates > 0
  * any lost_effects > 0
  * executions != runs x 1 in any cell
  * a (system, response_class) pair appearing twice
  * canary_survived + canary_lost != 30 in any arm
  * an invariant exception: an AEP-full execution with an applied effect whose
    run does not show the durability ack (section 3.3)
  * the unfalsifiability check (P9-A section 4.4): AUTH declared ambiguity that
    does not drop below 30/30 means the read-back is not being exercised, and
    the output is a defect report about the cell rather than a finding

WHAT IS REPORTED BUT DOES NOT HALT. The balance check and the kill-latency
envelope are reported, never fatal. Section 3.4 says failing sessions are
reported individually and NO SESSION IS DROPPED; making the balance check fatal
here would quietly convert that into a drop rule. The drift slope is likewise
reported for its own sake -- the sign reversed between the first two sessions,
so the per-session slope is worth having whatever it does.

Usage: gates.py <absolute run root>
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from statistics import median

APPLIED = "executions_with_an_applied_effect"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def spearman(xs: list[float], ys: list[float]) -> float:
    """Pearson on ranks. Ties get average ranks."""

    def rank(vs: list[float]) -> list[float]:
        order = sorted(range(len(vs)), key=lambda i: vs[i])
        out = [0.0] * len(vs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vs[order[j + 1]] == vs[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = rank(xs), rank(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def theil_sen(xs: list[float], ys: list[float]) -> float:
    """Median of pairwise slopes."""
    slopes = [
        (ys[j] - ys[i]) / (xs[j] - xs[i])
        for i in range(len(xs))
        for j in range(i + 1, len(xs))
        if xs[j] != xs[i]
    ]
    return median(slopes) if slopes else float("nan")


def main(root: Path) -> int:
    analysis = root / "analysis"
    ablation = read_csv(analysis / "redis-kill-ablation.csv")
    per_exec = read_csv(analysis / "per-execution.csv")

    halts: list[str] = []
    notes: list[str] = []

    # ---- HALT set over the cell table ------------------------------------
    seen: set[tuple[str, str]] = set()
    for row in ablation:
        cell = f"{row['system']}/{row['response_class']}"
        key = (row["system"], row["response_class"])
        if key in seen:
            halts.append(f"{cell}: (system, response_class) appears twice")
        seen.add(key)

        runs = int(row["runs"])
        execs = int(row["executions"])
        if execs != runs:
            halts.append(f"{cell}: executions {execs} != runs {runs}")
        if int(row["undetected_duplicates"]) > 0:
            halts.append(
                f"{cell}: undetected_duplicates = {row['undetected_duplicates']}"
            )
        if int(row["lost_effects"]) > 0:
            halts.append(f"{cell}: lost_effects = {row['lost_effects']}")

        canary = int(row["canary_survived"]) + int(row["canary_lost"])
        if canary != 30:
            halts.append(
                f"{cell}: canary_survived + canary_lost = {canary}, expected 30"
            )

    # ---- Unfalsifiability check (P9-A section 4.4) -----------------------
    for row in ablation:
        if row["system"] != "AEP_FULL":
            continue
        if row["response_class"] != "AUTHORITATIVE_READBACK":
            continue
        declared = int(row["declared_ambiguous"])
        if declared >= int(row["runs"]):
            halts.append(
                f"unfalsifiability: AUTH declared ambiguity {declared}/"
                f"{row['runs']} did not drop; the read-back is not being "
                "exercised and the cell measures something other than it claims"
            )
        else:
            notes.append(f"unfalsifiability check PASSES: AUTH declared ambiguity {declared}/{row['runs']}")

    # ---- Gate 1: B3 acknowledged in both cells ---------------------------
    for row in ablation:
        if row["system"] == "B3_INTENT_NO_BARRIER":
            notes.append(
                f"Gate 1 B3 {row['response_class']}: "
                f"{row[APPLIED]}/{row['runs']} applied"
            )

    # ---- Integrity check 3.3: applied implies durability ack -------------
    exceptions = []
    ack_counts: dict[str, int] = {}
    for row in per_exec:
        if row["system"] != "AEP_FULL":
            continue
        cls = row["response_class"]
        ack = row.get("durability_ack_observed", "").strip().lower()
        is_ack = ack in ("true", "1", "yes")
        ack_counts[cls] = ack_counts.get(cls, 0) + (1 if is_ack else 0)
        applied = float(row.get("applied_effects") or 0)
        if applied > 0 and not is_ack:
            exceptions.append(row["execution_id"])

    if exceptions:
        halts.append(
            f"INVARIANT EXCEPTION (section 3.3): {len(exceptions)} AEP-full "
            f"execution(s) applied without a durability ack: "
            f"{exceptions[:5]}{'...' if len(exceptions) > 5 else ''}"
        )
    else:
        for row in ablation:
            if row["system"] == "AEP_FULL":
                cls = row["response_class"]
                notes.append(
                    f"invariant {cls}: {ack_counts.get(cls, 0)} acks against "
                    f"{row[APPLIED]} applied, 0 exceptions"
                )

    # ---- Reported, never fatal: balance check and drift -------------------
    # Chronological position comes from the run directory's mtime, which is the
    # real collection order. The interleaved sort key means the arms alternate
    # run by run, so a per-arm median is drawn from the whole session rather
    # than from one block of it -- which is the entire point of amendment 1.
    order: dict[str, float] = {}
    for d in root.iterdir():
        if d.is_dir() and d.name != "analysis":
            order[d.name] = d.stat().st_mtime

    points: list[tuple[float, float, str, str]] = []
    for row in per_exec:
        lat = row.get("redis_kill_latency_ms", "").strip()
        if not lat:
            continue
        rid = row["run_id"]
        if rid not in order:
            continue
        points.append((order[rid], float(lat), row["system"], row["response_class"]))

    points.sort(key=lambda p: p[0])

    if points:
        xs = list(range(len(points)))
        ys = [p[1] for p in points]
        rho = spearman([float(x) for x in xs], ys)
        slope = theil_sen([float(x) for x in xs], ys)
        notes.append(
            f"DRIFT: Spearman(position, kill latency) = {rho:+.3f}, "
            f"Theil-Sen = {slope:+.2f} ms/run over {len(points)} runs"
        )

        for system in ("AEP_FULL", "B3_INTENT_NO_BARRIER"):
            auth = [p[1] for p in points if p[2] == system and p[3] == "AUTHORITATIVE_READBACK"]
            noro = [p[1] for p in points if p[2] == system and p[3] == "NO_READBACK"]
            if auth and noro:
                diff = median(auth) - median(noro)
                flag = "" if abs(diff) <= 100 else "  ** outside the registered 100 ms threshold **"
                band = ""
                if system == "AEP_FULL":
                    band = (
                        "  (inside amendment 2's registered +9 to +14 ms band)"
                        if 9.0 <= diff <= 14.0
                        else "  (outside amendment 2's registered +9 to +14 ms band)"
                    )
                notes.append(
                    f"BALANCE {system}: AUTH {median(auth):.1f} - "
                    f"NO_READBACK {median(noro):.1f} = {diff:+.1f} ms{flag}{band}"
                )

        overall = median(ys)
        env = "" if 859.0 <= overall <= 1216.0 else "  ** outside the 859-1216 ms envelope; recorded, collection continues **"
        notes.append(f"kill-latency session median: {overall:.1f} ms{env}")

    # ---- Report -----------------------------------------------------------
    print(f"\n--- registered gates for {root.name} ---")
    for n in notes:
        print(f"  {n}")

    summary = {
        "root": root.name,
        "halts": halts,
        "notes": notes,
    }
    (root / "gates.json").write_text(
        json.dumps(summary, indent=2) + "\n", newline="\n"
    )

    if halts:
        print("\n  *** HALT ***")
        for h in halts:
            print(f"    {h}")
        return 1

    print("\n  all registered HALT conditions clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]).resolve()))
