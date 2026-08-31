"""Generate the manuscript's evaluation tables and numbers from the frozen CSVs.

Amendment F3: *"Every number in the paper carries a pointer (in a LaTeX
comment) to its CSV cell or raw report section."* The strongest form of that is
not to write the numbers by hand at all. Everything this script emits carries a
generated comment naming the file, the filter and the arithmetic that produced
it, so a reviewer can recompute any cell without reading Python.

Two rules are enforced here rather than remembered:

1. **``analysis/table-1.csv`` is never read.** Session 3B §F2 banned it: it
   pools fault regimes and response classes, so its rates are a property of the
   collected mix. The only rate source is ``per-cell-metrics.csv``.

2. **Regimes are never pooled.** Every rollup below filters to one regime and
   says which in the emitted comment. The default is the crashed regime, which
   is the one the duplicate/ambiguity claims are about; the crash-free ``p0``
   regime and the ``redis-kill-preack`` regime are reported separately because
   they are different experiments.

Amendment G1 adds a third rule, because the manuscript's framing now turns on
it:

3. **Detection and prevention are separate claims with separate numbers.** The
   pre-dispatch intent ledger is what makes an outcome detectable; the
   ``WAITAOF`` barrier is what withholds an effect when the coordinator is
   lost. They are measured by different metrics, on different regimes, against
   different baselines, and this script emits them as different macros so that
   no sentence can borrow one's evidence for the other. ``\\BthreeVsAep*``
   exists precisely so the ablation's *null* result is quotable rather than
   paraphrased.

Usage:
    python scripts/paper_tables.py --analysis experiments/results/matrix/analysis \\
                                   --fsync-analysis experiments/results/fsync-always/analysis \\
                                   --flakey experiments/results \\
                                   --out paper/generated
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

# check_paper_numbers.py runs this file as a script, so sys.path[0] is
# scripts/ and `experiments` is not importable without help. Reusing the
# repository's exact Fisher implementation rather than reimplementing it is
# the point: a second implementation is a second thing to keep correct.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.statistics import (  # noqa: E402
    fisher_exact_two_tailed,
    wilson_upper_bound,
)

#: The explicit fault-regime label whose runs answer RQ1.
CRASHED_REGIME = "crashed"
CRASH_FREE_REGIME = "p0"
REDIS_KILL_REGIME = "redis-kill-preack"

RESPONSE_ORDER = [
    "AUTHORITATIVE_READBACK",
    "POSITIVE_ONLY_READBACK",
    "NO_READBACK",
]
RESPONSE_SHORT = {
    "AUTHORITATIVE_READBACK": r"\textsc{auth}",
    "POSITIVE_ONLY_READBACK": r"\textsc{pos-only}",
    "NO_READBACK": r"\textsc{none}",
}
SYSTEM_ORDER = [
    "B0_NAIVE_RETRY",
    "B1_LEASE_ONLY",
    "B2_CAS_ONLY",
    "B4_DURABLE_WORKFLOW",
    "B4B_DURABLE_WORKFLOW_AT_MOST_ONCE",
    "B3_INTENT_NO_BARRIER",
    "AEP_FULL",
]
SYSTEM_LABEL = {
    "B0_NAIVE_RETRY": "B0 naive retry",
    "B1_LEASE_ONLY": "B1 lease-only",
    "B2_CAS_ONLY": "B2 CAS-only",
    "B3_INTENT_NO_BARRIER": "B3 intent, no barrier",
    "B4_DURABLE_WORKFLOW": r"B4 durable, $\infty$ attempts",
    "B4B_DURABLE_WORKFLOW_AT_MOST_ONCE": "B4b durable, 1 attempt",
    "AEP_FULL": r"\textbf{AEP-full}",
}
CRASH_POINT_LABEL = {
    "before_intent_write": r"\texttt{before\_intent\_write}",
    "after_intent_before_barrier": (
        r"\shortstack[l]{\texttt{after\_intent\_}\\\texttt{before\_barrier}}"
    ),
    "after_barrier_before_dispatch": (
        r"\shortstack[l]{\texttt{after\_barrier\_}\\\texttt{before\_dispatch}}"
    ),
    "mid_dispatch": r"\texttt{mid\_dispatch}",
    "after_response_before_resolution": (
        r"\shortstack[l]{\texttt{after\_response\_}\\\texttt{before\_resolution}}"
    ),
    "after_resolution_before_barrier": (
        r"\shortstack[l]{\texttt{after\_resolution\_}\\\texttt{before\_barrier}}"
    ),
}
CRASH_POINT_ORDER = list(CRASH_POINT_LABEL)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    # The frozen Session-3 derivative predates explicit regime names. Normalize
    # its legacy label in memory; the frozen source is never rewritten. Fresh
    # analysis output already uses ``crashed``.
    for row in rows:
        if row.get("regime") == "(session-3)":
            row["regime"] = CRASHED_REGIME
    return rows


def totals(
    rows: Iterable[dict[str, str]], metric: str
) -> tuple[int, int]:
    successes = total = 0
    for row in rows:
        if row["metric"] != metric:
            continue
        successes += int(row["successes"])
        total += int(row["total"])
    return successes, total


def rate(successes: int, total: int) -> str:
    return f"{successes / total:.4f}" if total else "---"


def fraction(successes: int, total: int) -> str:
    return f"{successes}/{total}" if total else "---"


def emit_outcomes_table(rows: list[dict[str, str]], out: Path) -> None:
    """The anchor table: the trilemma, per system and endpoint capability."""
    crashed = [r for r in rows if r["regime"] == CRASHED_REGIME]
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in crashed:
        grouped[(row["system"], row["response_class"])].append(row)

    lines: list[str] = []
    lines.append(
        "% GENERATED by scripts/paper_tables.py -- do not edit by hand."
    )
    lines.append("% Source: analysis/per-cell-metrics.csv")
    lines.append(f"% Filter: regime == {CRASHED_REGIME!r} ONLY.")
    lines.append(
        "%   Every execution in these cells was killed at the cell's crash"
    )
    lines.append(
        "%   point. The crash-free (p0) and hard-Redis-kill (redis-kill-preack)"
    )
    lines.append(
        "%   regimes are DIFFERENT EXPERIMENTS and are reported separately;"
    )
    lines.append("%   pooling them is what got analysis/table-1.csv banned.")
    lines.append(
        "% Each cell = sum(successes)/sum(total) over the six crash points."
    )
    lines.append(r"\begin{table*}[t]")
    lines.append(r"\centering")
    lines.append(
        r"\caption{The trilemma, measured. Every execution in every cell was "
        r"killed at one of the six crash points of \cref{tab:crashpoints}; "
        r"rates are over executions, pooled across crash points within one "
        r"endpoint capability. B0--B2 pool over five of those six rather than "
        r"all of them --- \texttt{after\_intent\_before\_barrier} cannot occur "
        r"in a system that writes no intent, so for those three there is no "
        r"such cell to pool --- and the per-crash-point rates behind every "
        r"cell here are in \texttt{per-cell-metrics.csv}. "
        r"\textsc{auth}/\textsc{pos-only}/\textsc{none} "
        r"are the reconciliation capabilities of \cref{tab:capabilities}. "
        r"AEP-full and B3 --- the same protocol with and without the "
        r"durability barrier --- are the only systems that record any "
        r"declared ambiguity, and the only two whose undetected-duplicate "
        r"and lost-effect columns are zero throughout. Their equality in "
        r"every cell shown is this paper's ablation result rather than an "
        r"accident of this table, but the evidence for it is a bound obtained "
        r"by pooling these columns, not by testing the cells individually: "
        r"\cref{sec:eval-detection} puts both zero-event rates in "
        r"$[0,\AblationZeroUpperRun{}\%]$ at joint coverage of at least "
        r"90\%. The per-class cells this table is organised by are not "
        r"separately bounded --- at that scope the width would be "
        r"\AblationZeroUpperPerClass{} percentage points --- so what the "
        r"table shows per class is no observed difference, and "
        r"\cref{sec:eval-detection} is where the claim is quantified. "
        r"Source: \texttt{per-cell-metrics.csv}, crashed regime only.}"
    )
    lines.append(r"\label{tab:outcomes}")
    lines.append(r"\small")
    lines.append(r"\begin{tabular}{@{}l" + "ccc" * 3 + r"@{}}")
    lines.append(r"\toprule")
    lines.append(
        r"& \multicolumn{3}{c}{undetected duplicate}"
        r"& \multicolumn{3}{c}{lost effect}"
        r"& \multicolumn{3}{c}{declared ambiguity}\\"
    )
    lines.append(r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}\cmidrule(lr){8-10}")
    header = " & ".join(RESPONSE_SHORT[c] for c in RESPONSE_ORDER)
    lines.append(f"system & {header} & {header} & {header}\\\\")
    lines.append(r"\midrule")

    for system in SYSTEM_ORDER:
        cells: list[str] = []
        present = False
        for metric in (
            "undetected_duplicate_rate",
            "lost_effect_rate",
            "known_ambiguity_rate",
        ):
            for response in RESPONSE_ORDER:
                successes, total = totals(
                    grouped.get((system, response), []), metric
                )
                if total:
                    present = True
                cells.append(rate(successes, total))
        if not present:
            continue
        lines.append(
            f"{SYSTEM_LABEL[system]} & " + " & ".join(cells) + r"\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table*}")

    # The denominators, as a comment, so no reader has to trust the rates.
    lines.append("")
    lines.append("% Denominators (executions) per (system, response class):")
    for system in SYSTEM_ORDER:
        for response in RESPONSE_ORDER:
            group = grouped.get((system, response), [])
            successes, total = totals(group, "undetected_duplicate_rate")
            if not total:
                continue
            # Runs are counted on ONE metric's rows. Summing over all of them
            # would multiply by the metric count, and recovery_success_rate
            # reports 0 runs for a system with no recovery service, which
            # would drag a min() to zero.
            runs = sum(
                int(r["runs"])
                for r in group
                if r["metric"] == "undetected_duplicate_rate"
            )
            points = sorted(
                {
                    r["crash_point"]
                    for r in group
                    if r["metric"] == "undetected_duplicate_rate"
                }
            )
            lines.append(
                f"%   {system:<34} {response:<24} "
                f"executions={total:<5} runs={runs:<4} "
                f"crash_points={len(points)}"
            )
    (out / "table-outcomes.tex").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def emit_ambiguity_by_crashpoint(rows: list[dict[str, str]], out: Path) -> None:
    """Where AEP's declared ambiguity comes from, and where it does not."""
    crashed = [
        r
        for r in rows
        if r["regime"] == CRASHED_REGIME
        and r["system"] == "AEP_FULL"
        and r["metric"] == "known_ambiguity_rate"
    ]
    table: dict[tuple[str, str], tuple[int, int]] = {}
    for row in crashed:
        table[(row["crash_point"], row["response_class"])] = (
            int(row["successes"]),
            int(row["total"]),
        )

    lines: list[str] = []
    lines.append(
        "% GENERATED by scripts/paper_tables.py -- do not edit by hand."
    )
    lines.append(
        "% Source: analysis/per-cell-metrics.csv, "
        "metric=known_ambiguity_rate,"
    )
    lines.append(f"%         system=AEP_FULL, regime={CRASHED_REGIME!r}.")
    lines.append("% Cells are successes/total straight from the CSV row.")
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(
        r"\caption{AEP-full's declared-ambiguity rate, by crash point and "
        r"endpoint capability. The rate is not a constant of the protocol: it "
        r"is zero where the crash precedes the intent write (nothing was "
        r"promised), zero throughout \textsc{auth} (absence is provable), and "
        r"highest exactly where no effect can exist but the endpoint cannot "
        r"say so. Undetected duplicates and lost effects are $0$ in every cell "
        r"of this table.}"
    )
    lines.append(r"\label{tab:ambiguity-by-crashpoint}")
    lines.append(r"\small")
    lines.append(r"\renewcommand{\arraystretch}{1.08}")
    lines.append(r"\begin{tabular}{@{}lccc@{}}")
    lines.append(r"\toprule")
    lines.append(
        "crash point & "
        + " & ".join(RESPONSE_SHORT[c] for c in RESPONSE_ORDER)
        + r"\\"
    )
    lines.append(r"\midrule")
    for point in CRASH_POINT_ORDER:
        cells = []
        for response in RESPONSE_ORDER:
            successes, total = table.get((point, response), (0, 0))
            cells.append(fraction(successes, total))
        if all(c == "---" for c in cells):
            continue
        lines.append(
            f"{CRASH_POINT_LABEL[point]} & " + " & ".join(cells) + r"\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    (out / "table-ambiguity-by-crashpoint.tex").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


#: The provider's configured delay. One round trip is the floor no protocol can
#: go under, so the reported increment is median minus this.
PROVIDER_DELAY_MS = 2000.0

LATENCY_ORDER = [
    ("B0_NAIVE_RETRY", "B0 no protocol"),
    ("B1_LEASE_ONLY", r"B1 $+$ lease"),
    ("B2_CAS_ONLY", r"B2 $+$ fenced CAS"),
    ("B3_INTENT_NO_BARRIER", "B3 full protocol, no barrier"),
    ("AEP_FULL", r"\textbf{AEP-full}"),
    ("B4B_DURABLE_WORKFLOW_AT_MOST_ONCE", "B4b durable, 1 attempt"),
    ("B4_DURABLE_WORKFLOW", r"B4 durable, $\infty$ attempts"),
]


def tex_number(value: float) -> str:
    """A LaTeX thousands separator, applied to the number and nothing else.

    The first version called ``.replace(",", r"\\,")`` on the whole assembled
    row, which turned "B3 full protocol, no barrier" into "B3 full protocol\\,
    no barrier". Formatting belongs to the number.
    """
    return f"{value:,.1f}".replace(",", r"\,")


def tex_sigfigs(value: float, digits: int = 2) -> str:
    """A magnitude, rounded to significant figures rather than to decimals.

    ``tex_number`` fixes one decimal place, which is right for a millisecond
    measurement and wrong for a ratio of two of them: printing ``70.1`` for a
    quotient whose denominator is a three-run median difference claims a
    precision the interval underneath it does not support. Significant figures
    round to the scale of the number instead.

    Formatted plainly rather than with ``%g``, which renders 100 as ``1e+02``
    and would put an exponent in the middle of an English sentence.
    """
    if value == 0:
        return "0"
    # Negative for values of 100 and up, and it has to stay negative for the
    # rounding: `round(1966.7, -2)` is 2000, while clamping to zero first gives
    # 1967 -- four significant figures wearing the label of two. Only the
    # *format* precision clamps.
    decimals = digits - 1 - math.floor(math.log10(abs(value)))
    return f"{round(value, decimals):,.{max(0, decimals)}f}".replace(",", r"\,")


def emit_latency_table(rows: list[dict[str, str]], out: Path) -> None:
    """RQ3. Every increment is computed from the CSV, never typed.

    The reference column is **B0**, not the provider's nominal delay. B0 is
    the no-protocol system, so B0's own median already contains the provider
    round trip *and* the harness's per-step cost; subtracting the nominal
    2\\,000\\,ms instead would charge every protocol row for a floor that is
    not the protocol's. B0 measures 10.2 ms above nominal, and that 10.2 ms
    belongs to the harness.
    """
    by_system = {r["system"]: r for r in rows}
    baseline_row = by_system.get("B0_NAIVE_RETRY")
    baseline = (
        float(baseline_row["step_latency_ms_median"])
        if baseline_row and int(baseline_row["overhead_runs_crash_free"] or 0)
        else None
    )

    lines: list[str] = []
    lines.append("% GENERATED by scripts/paper_tables.py -- do not edit.")
    lines.append("% Source: analysis/latency-and-throughput.csv")
    lines.append(
        "% 'median' is step_latency_ms_median over crash-free runs only"
    )
    lines.append("% (denominator = overhead_runs_crash_free, printed).")
    lines.append(
        f"% 'over B0' subtracts B0's median ({baseline if baseline else '?'}"
        " ms), which is"
    )
    lines.append(
        f"% the no-protocol system on the same host and the same provider"
    )
    lines.append(
        f"% (configured delay {PROVIDER_DELAY_MS:.0f} ms; B0 sits above it by"
    )
    lines.append(
        f"% {baseline - PROVIDER_DELAY_MS:.1f} ms, which is harness cost, not"
        " protocol cost)."
        if baseline
        else "% (B0 unavailable)"
    )
    lines.append(
        "% E5 gate: a run contributes a duration only if the host was declared"
    )
    lines.append(
        "% non-suspending BEFORE the run and no wall-versus-monotonic"
    )
    lines.append("% divergence was observed in it. Counts are unaffected.")
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(
        r"\caption{Median step latency, crash-free runs only, E5-gated. "
        r"Increments are over B0, the no-protocol system on the same host "
        r"and provider. The whole write-ahead protocol minus the barrier is "
        r"the B3 row; the barrier is the difference between B3 and AEP-full.}"
    )
    lines.append(r"\label{tab:latency}")
    lines.append(r"\small")
    lines.append(
        r"\begin{tabularx}{\columnwidth}"
        r"{@{}>{\raggedright\arraybackslash}Xrrr@{}}"
    )
    lines.append(r"\toprule")
    lines.append(
        r"system & runs & \shortstack{median step\\(ms)} & "
        r"\shortstack{over B0\\(ms)}\\"
    )
    lines.append(r"\midrule")
    for system, label in LATENCY_ORDER:
        row = by_system.get(system)
        if not row:
            continue
        crash_free = int(row["overhead_runs_crash_free"] or 0)
        if not crash_free:
            continue
        median = float(row["step_latency_ms_median"])
        if baseline is None:
            over = "---"
        elif system == "B0_NAIVE_RETRY":
            over = "---"
        else:
            over = tex_number(median - baseline)
        lines.append(
            f"{label} & {crash_free} & {tex_number(median)} & {over}" + r"\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabularx}")
    lines.append(r"\end{table}")
    (out / "table-latency.tex").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def cluster_bootstrap_median_difference(
    treatment: dict[str, list[float]],
    control: dict[str, list[float]],
    *,
    resamples: int = 10_000,
    seed: int = 20260806,
) -> tuple[float, float, float]:
    """95% interval for (median treatment - median control), clustered by run.

    The unit of independence is the *run*, not the execution: thirty step
    latencies from three runs are not thirty independent draws, because a run
    shares one provider process, one lease namespace and one worker-respawn
    history. So the resample is over runs, and every execution of a resampled
    run comes with it.

    With three runs per arm this interval is coarse by construction -- there
    are only ten distinct multisets of three runs -- and that coarseness is
    the honest content of the number. It is reported rather than smoothed,
    because the alternative on offer is a point estimate with no interval at
    all, which is what this replaces.
    """
    rng = random.Random(seed)
    treatment_runs = sorted(treatment)
    control_runs = sorted(control)
    if not treatment_runs or not control_runs:
        return (0.0, 0.0, 0.0)

    def draw(runs: list[str], data: dict[str, list[float]]) -> list[float]:
        picked: list[float] = []
        for _ in runs:
            picked.extend(data[rng.choice(runs)])
        return picked

    point = statistics.median(
        [v for run in treatment_runs for v in treatment[run]]
    ) - statistics.median([v for run in control_runs for v in control[run]])

    differences: list[float] = []
    for _ in range(resamples):
        differences.append(
            statistics.median(draw(treatment_runs, treatment))
            - statistics.median(draw(control_runs, control))
        )
    differences.sort()
    low = differences[int(0.025 * len(differences))]
    high = differences[min(len(differences) - 1, int(0.975 * len(differences)))]
    return (point, low, high)


def crash_free_latencies(path: Path, system: str) -> dict[str, list[float]]:
    """Per-run step latencies for one system's crash-free executions."""
    grouped: dict[str, list[float]] = defaultdict(list)
    if not path.is_file():
        return {}
    for row in read_rows(path):
        if row.get("regime") != CRASH_FREE_REGIME:
            continue
        if row.get("system") != system:
            continue
        value = row.get("step_latency_ms")
        if value:
            grouped[row["run_id"]].append(float(value))
    return dict(grouped)


def tex_p_value(value: float) -> str:
    """A p-value as LaTeX maths, in the form a reviewer can check.

    Below 1e-4 the exact mantissa is noise from the bootstrap-free exact
    computation's floating point, but the exponent is not, so the number is
    rendered in scientific form rather than rounded to ``0.0000``. At the
    other end, ``p = 1.0`` is a real and important value here -- it is what an
    ablation that changes nothing looks like -- and must not print as
    ``1.0\\times10^{0}``.
    """
    if value >= 0.01:
        return f"{value:.2f}"
    mantissa, exponent = f"{value:.1e}".split("e")
    return f"{mantissa}\\times10^{{{int(exponent)}}}"


def mann_whitney_two_tailed(first: list[float], second: list[float]) -> float:
    """Two-tailed Mann-Whitney U, normal approximation with tie correction.

    Deterministic on purpose. The obvious alternative, a permutation test, needs
    a seed, and a seeded resampling test in a file whose whole contract is that
    it regenerates byte-identically is one more thing that can silently stop
    doing so. The samples here are n=120 and n=30, well inside the range where
    the normal approximation is the standard choice.

    Used for a location shift in `docker kill` latency between the runs that
    applied an effect and those that did not, which is not a proportion and so
    has no Fisher form.
    """
    n_first, n_second = len(first), len(second)
    if not n_first or not n_second:
        return 1.0
    combined = sorted((value, group) for group, sample in
                      ((0, first), (1, second)) for value in sample)
    # Midranks, so ties do not bias the statistic toward whichever group the
    # sort happened to place first.
    ranks: list[float] = [0.0] * len(combined)
    index = 0
    tie_correction = 0.0
    while index < len(combined):
        stop = index
        while stop + 1 < len(combined) and combined[stop + 1][0] == combined[index][0]:
            stop += 1
        midrank = (index + stop) / 2.0 + 1.0
        for position in range(index, stop + 1):
            ranks[position] = midrank
        run = stop - index + 1
        if run > 1:
            tie_correction += run**3 - run
        index = stop + 1

    rank_sum_first = sum(
        rank for rank, (_, group) in zip(ranks, combined) if group == 0
    )
    u_first = rank_sum_first - n_first * (n_first + 1) / 2.0
    total = n_first * n_second
    mean = total / 2.0
    span = n_first + n_second
    variance = total * (span + 1) / 12.0
    if tie_correction:
        variance -= total * tie_correction / (12.0 * span * (span - 1))
    if variance <= 0:
        return 1.0
    # Continuity correction, then the two-tailed normal tail.
    z = (abs(u_first - mean) - 0.5) / math.sqrt(variance)
    if z <= 0:
        return 1.0
    return math.erfc(z / math.sqrt(2.0))


def flakey_macros(payloads: list[dict[str, Any]]) -> list[tuple[str, ...]]:
    """The G2 write-loss probe's numbers, pooled over its replications.

    Pooling here is legitimate and elsewhere is not, because every
    replication is the same probe against the same fault on the same host;
    there is no regime mixing of the kind Session 3B banned. The replication
    count is emitted so a reader can see what is being pooled.
    """
    counted = ack_survived = unack_lost = 0
    windows: list[float] = []
    barriers: list[float] = []
    for payload in payloads:
        summary = payload.get("summary") or {}
        counted += int(summary.get("counted", 0))
        ack_survived += int(summary.get("acknowledged_survived", 0))
        unack_lost += int(summary.get("unacknowledged_lost", 0))
        for trial in payload.get("trials", []):
            if trial.get("error") or not trial.get("acknowledged_survived"):
                continue
            windows.append(float(trial["write_to_drop_ms"]))
            barriers.append(float(trial["barrier_ms"]))
    if not counted:
        return []

    source = (
        "experiments/results/g2-flakey-write-loss*.json | "
        f"{len(payloads)} replication(s) of "
        "experiments/flakey_write_loss.py"
    )
    emitted: list[tuple[str, ...]] = [
        (
            "FlakeyReplications",
            str(len(payloads)),
            source,
            "independent runs of the probe, each rebuilding the device stack "
            "and the filesystem from scratch",
        ),
        (
            "FlakeyN",
            str(counted),
            source,
            "countable trials: the acknowledged write survived, so the "
            "trial says something about the unacknowledged one",
        ),
        (
            "FlakeyAckSurvived",
            f"{ack_survived}/{counted}",
            source,
            "WAITAOF-acknowledged writes still present after the device "
            "stopped accepting writes",
        ),
        (
            "FlakeyUnackLost",
            f"{unack_lost}/{counted}",
            source,
            "un-acknowledged writes destroyed by the same event",
        ),
        (
            "FlakeyWindowMin",
            f"{min(windows):.1f}",
            source,
            "narrowest write-to-write-loss exposure window, ms",
        ),
        (
            "FlakeyWindowMax",
            f"{max(windows):.1f}",
            source,
            "widest write-to-write-loss exposure window, ms; the "
            "appendfsync everysec period it sits inside is 1000 ms",
        ),
        (
            "FlakeyBarrierP",
            tex_p_value(
                fisher_exact_two_tailed(
                    counted - ack_survived,
                    ack_survived,
                    unack_lost,
                    counted - unack_lost,
                )
            ),
            source,
            "Fisher exact two-tailed, acknowledged vs un-acknowledged "
            f"loss over the same {counted} trials",
        ),
    ]
    # The cross-fault comparison is the point of the probe: the same two keys
    # under a process kill lost nothing.
    emitted.append(
        (
            "FlakeyVsProcessKillP",
            tex_p_value(fisher_exact_two_tailed(0, 10, unack_lost, 0)),
            "reports/raw/e1-durability-window.txt (0/10 lost under "
            "docker kill -s KILL) vs " + source,
            "Fisher exact two-tailed across the two fault classes",
        )
    )
    return emitted


def emit_ablation_table(
    per_cell: list[dict[str, str]],
    comparisons: list[dict[str, str]],
    out: Path,
) -> None:
    """AEP-full against its own barrier-ablation, on the detection metrics.

    This table exists to make a *null* result quotable. A sentence saying the
    ablation ``performed similarly'' is unfalsifiable; a table with both
    numerators, both denominators and the exact p-value is not. It is also the
    table that licenses the B3-mode row of \\cref{tab:deployment}, so it has
    to be visibly complete rather than a selected pair of columns.
    """
    crashed = [r for r in per_cell if r["regime"] == CRASHED_REGIME]
    metrics = (
        ("undetected_duplicate_rate", "undetected duplicate"),
        ("lost_effect_rate", "lost effect"),
        ("known_ambiguity_rate", "declared ambiguity"),
    )

    fragment = [
        "% GENERATED by scripts/paper_tables.py -- do not edit.",
        "% Source: analysis/per-cell-metrics.csv (rates, "
        f"regime={CRASHED_REGIME})",
        "%         analysis/comparisons-vs-aep-full.csv (regime-labelled p-values).",
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{The barrier ablation on the detection metrics. B3 is "
        r"AEP-full with the \texttt{WAITAOF} barrier removed and nothing else "
        r"removed. Crashed regime; rates are over executions, pooled across "
        r"crash points within one capability class. The p-values are "
        r"execution-level Fisher tests over all capability classes; they do "
        r"not account for run clustering and are not used as equivalence "
        r"evidence.}",
        r"\label{tab:ablation}",
        r"\small",
        r"\begin{tabular}{@{}llccc@{}}",
        r"\toprule",
        r"metric & capability & AEP-full & B3 & $p$\\",
        r"\midrule",
    ]
    for metric, label in metrics:
        comparison = next(
            (
                r
                for r in comparisons
                if r["regime"] == CRASHED_REGIME
                and r["system"] == "B3_INTENT_NO_BARRIER"
                and r["metric"] == metric
            ),
            None,
        )
        p_cell = (
            f"\\multirow{{3}}{{*}}{{${tex_p_value(float(comparison['fisher_p_value']))}$}}"
            if comparison
            else ""
        )
        for index, response in enumerate(RESPONSE_ORDER):
            aep = [
                r
                for r in crashed
                if r["system"] == "AEP_FULL" and r["response_class"] == response
            ]
            b3 = [
                r
                for r in crashed
                if r["system"] == "B3_INTENT_NO_BARRIER"
                and r["response_class"] == response
            ]
            aep_s, aep_t = totals(aep, metric)
            b3_s, b3_t = totals(b3, metric)
            if not aep_t and not b3_t:
                continue
            first = f"\\multirow{{3}}{{*}}{{{label}}}" if index == 0 else ""
            fragment.append(
                f"{first} & {RESPONSE_SHORT[response]} & "
                f"{rate(aep_s, aep_t)} & {rate(b3_s, b3_t)} & "
                f"{p_cell if index == 0 else ''}\\\\"
            )
        fragment.append(r"\midrule" if metric != metrics[-1][0] else "")
    fragment = [line for line in fragment if line != ""]
    fragment += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    (out / "table-ablation.tex").write_text(
        "\n".join(fragment) + "\n", encoding="utf-8"
    )


def emit_deployment_choice(
    latency: list[dict[str, str]], always: list[dict[str, str]], out: Path
) -> None:
    """The three configurations an operator actually chooses between.

    The manuscript previously reported the barrier's cost as one number and
    then, separately, that ``appendfsync always`` changes it by a factor of
    31. Read in sequence those invite the conclusion that AEP costs two
    seconds. They are better read as one decision with three settled points,
    and the third point -- running with no barrier at all, which is exactly
    what B3 is -- has to be on the table for the other two to mean anything.
    """
    def crash_free_medians(rows: list[dict[str, str]]) -> dict[str, float]:
        return {
            row["system"]: float(row["step_latency_ms_median"])
            for row in rows
            if int(row["overhead_runs_crash_free"] or 0)
        }

    everysec = crash_free_medians(latency)
    always_medians = crash_free_medians(always)
    b0 = everysec.get("B0_NAIVE_RETRY")
    b3 = everysec.get("B3_INTENT_NO_BARRIER")
    aep = everysec.get("AEP_FULL")
    aep_always = always_medians.get("AEP_FULL")
    b3_always = always_medians.get("B3_INTENT_NO_BARRIER")
    if not (b0 and b3 and aep and aep_always and b3_always):
        return

    def tex(value: float) -> str:
        return f"{value:,.1f}".replace(",", r"\,")

    # The barrier's cost is the ablation difference *within one fsync policy*.
    # Subtracting the everysec B3 median from the always AEP median would
    # assume the ablated protocol's own writes cost the same under both
    # policies. They nearly do -- b3_always - b3 is small -- but "nearly"
    # is a measurement, so the table takes each row's own B3.
    rows = [
        (
            r"AEP-full, \texttt{everysec}",
            aep,
            aep - b3,
            "yes",
            "detection + prevention",
        ),
        (
            r"AEP-full, \texttt{always}",
            aep_always,
            aep_always - b3_always,
            "yes",
            "detection + prevention",
        ),
        (
            r"B3-mode, \texttt{everysec}",
            b3,
            0.0,
            "no",
            "detection only",
        ),
    ]

    fragment = [
        "% GENERATED by scripts/paper_tables.py -- do not edit.",
        "% Sources: analysis/latency-and-throughput.csv (everysec rows),",
        "%          fsync-always/analysis/latency-and-throughput.csv (always).",
        "% step_latency_ms_median over crash-free, E5-gated runs only.",
        "% Barrier column = row median - the B3 median collected under the",
        f"% SAME fsync policy (everysec {tex(b3)} ms, always {tex(b3_always)} "
        "ms),",
        "% i.e. the same protocol with the barrier ablated and nothing else",
        "% changed. Never across policies: that would assume the ablated",
        "% protocol's own writes cost the same under both, which is exactly",
        "% what the two B3 numbers are here to establish rather than assume.",
        r"\begin{table*}[t]",
        r"\centering",
        r"\caption{The barrier is a deployment choice, not a fixed cost. All "
        r"three rows run the same pre-dispatch intent ledger and therefore "
        r"make the same detection claim; they differ in what they pay to "
        r"also withhold dispatch when durability cannot be confirmed. The "
        r"barrier column is each row's own median minus a B3 median "
        r"collected under the same \texttt{appendfsync} policy. Crash-free "
        r"runs only, E5-gated, 2\,000\,ms provider floor.}",
        r"\label{tab:deployment}",
        r"\small",
        r"\renewcommand{\arraystretch}{1.08}",
        r"\begin{tabularx}{\textwidth}{@{}>{\raggedright\arraybackslash}Xrrrc>{\raggedright\arraybackslash}p{0.20\textwidth}@{}}",
        r"\toprule",
        r"configuration & \shortstack{median\\(ms)} & \shortstack{over\\floor} & \shortstack{barrier\\(ms)} & prevents & claim\\",
        r"\midrule",
    ]
    for label, median, barrier, prevents, claim in rows:
        fragment.append(
            f"{label} & {tex(median)} & {tex(median - 2000.0)} & "
            f"{tex(barrier)} & {prevents} & {claim}\\\\"
        )
    fragment += [
        r"\midrule",
        r"\multicolumn{6}{@{}p{0.96\textwidth}@{}}{\footnotesize "
        r"The detection claim of \cref{tab:outcomes} shows no observed "
        r"difference in any cell, bounded by pooling the capability classes "
        r"rather than per class (\cref{sec:eval-detection}): it is produced "
        r"by the pre-dispatch record plus no re-entry, "
        r"which all three rows have, and \cref{tab:ablation} is the "
        r"ablation that shows it. What the barrier buys is the last "
        r"column's second word, and \cref{tab:killablation} is what it is "
        r"worth. `Over floor' is the same median less the provider's "
        r"2\,000\,ms delay, and so includes the "
        f"{tex(b3 - b0)}"
        r"\,ms the protocol costs with the barrier already removed.}\\",
        r"\bottomrule",
        r"\end{tabularx}",
        r"\end{table*}",
    ]
    (out / "table-deployment-choice.tex").write_text(
        "\n".join(fragment) + "\n", encoding="utf-8"
    )


def emit_numbers(
    per_cell: list[dict[str, str]],
    latency: list[dict[str, str]],
    kill: list[dict[str, str]],
    comparisons: list[dict[str, str]],
    flakey: list[dict[str, Any]],
    always: list[dict[str, str]],
    coverage: dict[str, Any],
    execution_paths: dict[str, Path],
    out: Path,
) -> None:
    """Headline scalars as macros, each with its provenance in a comment."""
    lines: list[str] = []
    lines.append("% GENERATED by scripts/paper_tables.py -- do not edit.")
    lines.append(
        "% Sources: analysis/per-cell-metrics.csv, "
        "analysis/latency-and-throughput.csv,"
    )
    lines.append(
        "%          analysis/redis-kill-ablation.csv, "
        "analysis/comparisons-vs-aep-full.csv,"
    )
    lines.append("%          experiments/results/g2-flakey-write-loss*.json")
    lines.append(
        "% Each macro carries the file, filter and arithmetic behind it."
    )
    lines.append("")

    def macro(name: str, value: str, *provenance: str) -> None:
        for line in provenance:
            lines.append(f"% {line}")
        lines.append(f"\\newcommand{{\\{name}}}{{{value}}}")
        lines.append("")

    crashed = [r for r in per_cell if r["regime"] == CRASHED_REGIME]
    denominators: dict[str, int] = {}

    # --- RQ1: AEP's three columns, per capability -----------------------
    for response in RESPONSE_ORDER:
        subset = [
            r
            for r in crashed
            if r["system"] == "AEP_FULL" and r["response_class"] == response
        ]
        suffix = {
            "AUTHORITATIVE_READBACK": "Auth",
            "POSITIVE_ONLY_READBACK": "PosOnly",
            "NO_READBACK": "NoReadback",
        }[response]
        for metric, tag in (
            ("known_ambiguity_rate", "Amb"),
            ("undetected_duplicate_rate", "Dup"),
            ("lost_effect_rate", "Lost"),
        ):
            successes, total = totals(subset, metric)
            macro(
                f"Aep{tag}{suffix}",
                rate(successes, total),
                f"per-cell-metrics.csv | system=AEP_FULL "
                f"regime={CRASHED_REGIME} response_class={response}",
                f"metric={metric} | sum(successes)/sum(total) "
                f"= {successes}/{total}",
            )
            denominators[suffix] = total
    # One denominator per capability class, not one per metric: the three
    # metrics are counted over the same executions, so three macros holding
    # the same number is three chances for a stale one to survive an edit.
    for suffix, total in denominators.items():
        macro(
            f"AepExec{suffix}",
            str(total),
            f"per-cell-metrics.csv | executions behind every AEP-full rate "
            f"on this capability class (regime={CRASHED_REGIME})",
        )

    # --- RQ1: the range the no-pre-dispatch-record baselines occupy -----
    # Typed as a literal once, it drifted the moment another cell landed.
    baseline_rates: list[float] = []
    for system in ("B0_NAIVE_RETRY", "B1_LEASE_ONLY", "B2_CAS_ONLY"):
        for response in RESPONSE_ORDER:
            subset = [
                r
                for r in crashed
                if r["system"] == system and r["response_class"] == response
            ]
            successes, total = totals(subset, "undetected_duplicate_rate")
            if total:
                baseline_rates.append(successes / total)
    if baseline_rates:
        macro(
            "BaselineDupLow",
            f"{min(baseline_rates):.2f}",
            "per-cell-metrics.csv | min undetected-duplicate rate over "
            "{B0,B1,B2} x {all collected response classes}",
            f"regime={CRASHED_REGIME} | {len(baseline_rates)} cells",
        )
        macro(
            "BaselineDupHigh",
            f"{max(baseline_rates):.2f}",
            "per-cell-metrics.csv | max undetected-duplicate rate over "
            "{B0,B1,B2} x {all collected response classes}",
            f"regime={CRASHED_REGIME} | {len(baseline_rates)} cells",
        )
        # The same two numbers as percentages. The equivalence argument in
        # section 6 compares them against \AblationZeroUpperRun, which is a
        # percentage, and the comparison was written with the rates converted
        # by hand -- "77--83%" typed beside the macros that hold 0.77 and 0.83.
        # Two representations of one measurement, only one of them generated,
        # is how the two drift apart.
        macro(
            "BaselineDupLowPct",
            f"{min(baseline_rates) * 100:.0f}",
            "\\BaselineDupLow as a percentage, for comparison against "
            "\\AblationZeroUpperRun",
        )
        macro(
            "BaselineDupHighPct",
            f"{max(baseline_rates) * 100:.0f}",
            "\\BaselineDupHigh as a percentage, for comparison against "
            "\\AblationZeroUpperRun",
        )
    # The significance of that gap. The manuscript asserted a bound --
    # "p < 10^{-100}" -- which is true but is a number nothing generated and
    # nobody can check without recomputing it. The weakest of the three
    # comparisons is the honest figure to quote: if the least significant one
    # is this small, all three are.
    baseline_dup_p = [
        float(row["fisher_p_value"])
        for row in comparisons
        if row["metric"] == "undetected_duplicate_rate"
        and row["regime"] == CRASHED_REGIME
        and row["system"] in ("B0_NAIVE_RETRY", "B1_LEASE_ONLY", "B2_CAS_ONLY")
        and row["reference"] == "AEP_FULL"
    ]
    if baseline_dup_p:
        macro(
            "BaselineDupMaxP",
            tex_p_value(max(baseline_dup_p)),
            "comparisons-vs-aep-full.csv | metric=undetected_duplicate_rate, "
            f"regime={CRASHED_REGIME}, largest (weakest) Fisher p over "
            "{B0,B1,B2} vs AEP_FULL",
            f"{len(baseline_dup_p)} comparisons; the other "
            f"{len(baseline_dup_p) - 1} are smaller",
        )

    # --- RQ3: latency, E5-gated only ------------------------------------
    # Only the three systems the cost decomposition is built from get a
    # macro. Every system's median is in \cref{tab:latency}, which is
    # generated from the same file; a macro for a median no sentence quotes
    # is a number with no reader, and the manuscript gate now says so.
    for row in latency:
        crash_free = int(row["overhead_runs_crash_free"] or 0)
        if not crash_free:
            continue
        key = {
            "AEP_FULL": "Aep",  # the protocol with the barrier
            "B0_NAIVE_RETRY": "Bzero",  # no protocol at all
            "B3_INTENT_NO_BARRIER": "Bthree",  # the protocol without it
        }.get(row["system"])
        if not key:
            continue
        median = float(row["step_latency_ms_median"])
        macro(
            f"{key}StepMedian",
            tex_number(median),
            f"latency-and-throughput.csv | system={row['system']}",
            f"step_latency_ms_median over crash-free runs only "
            f"(overhead_runs_crash_free={crash_free})",
            "E5 gate: runs without a declared suspend-disabled host "
            "contribute NO timing",
        )

    # --- RQ3: the decomposition, which is the quotable part -------------
    # "the protocol costs 28 ms and the barrier costs the rest" is the
    # sentence a reader will carry away, so neither half is typed by hand.
    medians: dict[str, float] = {}
    for row in latency:
        if int(row["overhead_runs_crash_free"] or 0):
            medians[row["system"]] = float(row["step_latency_ms_median"])
    b0 = medians.get("B0_NAIVE_RETRY")
    b3 = medians.get("B3_INTENT_NO_BARRIER")
    aep = medians.get("AEP_FULL")
    if b0 and b3:
        macro(
            "ProtocolMinusBarrier",
            tex_number(b3 - b0),
            "latency-and-throughput.csv | B3 median - B0 median",
            f"= {b3:.1f} - {b0:.1f}; the whole write-ahead protocol except "
            "the barrier",
        )
        macro(
            "ProtocolMinusBarrierPct",
            f"{(b3 - b0) / b0 * 100:.1f}",
            f"= ({b3:.1f} - {b0:.1f}) / {b0:.1f} x 100",
        )
    if b3 and aep:
        macro(
            "BarrierCost",
            tex_number(aep - b3),
            "latency-and-throughput.csv | AEP-full median - B3 median, both "
            "under appendfsync=everysec",
            f"= {aep:.1f} - {b3:.1f}; the two WAITAOF round trips together",
        )
        macro(
            "BarrierCostEach",
            tex_number((aep - b3) / 2),
            "half of \\BarrierCost -- the protocol runs exactly two barriers "
            "per step",
        )
        # What a *third* barrier would cost, as a share of the step a reader
        # is timing. Section 6 costed the unresolved-crash-point fix at
        # "roughly a 50% latency increase", which is what one more barrier
        # does to the barrier bill (983.3 on top of 1966.7) and not what it
        # does to the step: against AEP-full's own median the increase is half
        # that. Both readings are arithmetic on the same two macros, which is
        # exactly why the sentence should quote a generated one.
        macro(
            "ThirdBarrierStepPct",
            f"{(aep - b3) / 2 / aep * 100:.1f}",
            "= \\BarrierCostEach / \\AepStepMedian x 100",
            f"= {(aep - b3) / 2:.1f} / {aep:.1f} x 100; the end-to-end cost of "
            "adding one more barrier to the step, not the increase in the "
            "barrier bill alone",
        )

    # --- D6: the factor the threats section was estimating in words ------
    # `08-threats.tex` said the barriers "dominate the protocol's latency by
    # two orders of magnitude". The two macros above put it at 70x, which is
    # nearer one and a half orders; the Monday audit recorded the gap as D6.
    # The sentence now quotes this macro, so the phrase and the measurement
    # cannot drift apart again.
    #
    # This is a ratio of two median differences, which is the construction
    # the `always` arm below refuses -- but the reason it refuses does not
    # apply here. There, the denominator's cluster bootstrap spans zero, and a
    # ratio through a denominator indistinguishable from zero is not a
    # measurement. Here it does not: the same bootstrap over (B3 - B0) under
    # everysec gives [27.1, 1524.6] ms, entirely positive, so the quotient is
    # defined across the interval. It is still a point estimate of a wide one,
    # which is why it is rounded to two significant figures and why the
    # sentence quoting it says "roughly".
    if b0 and b3 and aep:
        macro(
            "BarrierToProtocolRatio",
            tex_sigfigs((aep - b3) / (b3 - b0)),
            "latency-and-throughput.csv | \\BarrierCost / "
            "\\ProtocolMinusBarrier, both under appendfsync=everysec",
            f"= ({aep:.1f} - {b3:.1f}) / ({b3:.1f} - {b0:.1f}) "
            f"= {aep - b3:.1f} / {b3 - b0:.1f} = {(aep - b3) / (b3 - b0):.2f}, "
            "to two significant figures",
            "how much more the two fsync barriers cost than everything else "
            "the protocol does",
        )

    # The same subtraction under the other durability policy. Both arms are
    # collected under that policy; see emit_deployment_choice.
    if always:
        always_medians = {
            row["system"]: float(row["step_latency_ms_median"])
            for row in always
            if int(row["overhead_runs_crash_free"] or 0)
        }
        aep_always = always_medians.get("AEP_FULL")
        b3_always = always_medians.get("B3_INTENT_NO_BARRIER")
        if aep_always and b3_always and b3 and aep:
            macro(
                "BarrierCostAlways",
                tex_number(aep_always - b3_always),
                "fsync-always/analysis/latency-and-throughput.csv | "
                "AEP-full median - B3 median, both under appendfsync=always",
                f"= {aep_always:.1f} - {b3_always:.1f}",
            )
            # No ratio macro. The obvious one -- \BarrierCost divided by
            # \BarrierCostAlways -- was emitted and quoted until the cluster
            # bootstrap showed the denominator's interval spans zero. A ratio
            # whose denominator is not distinguishable from zero is not a
            # measurement, and generating it would only invite it back into
            # the prose.
            macro(
                "BthreeAlwaysMedian",
                tex_number(b3_always),
                "fsync-always/analysis/latency-and-throughput.csv | "
                "system=B3_INTENT_NO_BARRIER, appendfsync=always",
                f"against {b3:.1f} ms under everysec: the ablated protocol's "
                "own cost is nearly policy-independent, which is what makes "
                "the two barrier figures comparable",
            )
            macro(
                "AepAlwaysMedian",
                tex_number(aep_always),
                "fsync-always/analysis/latency-and-throughput.csv | "
                "system=AEP_FULL, appendfsync=always",
                "step_latency_ms_median; quoted in the threats section "
                "against the p95 below, to show the tail the three-run "
                "interval is drawn from",
            )

        # The tail and the throughput of the `always` arm. Threats-to-validity
        # quotes both to argue the interval is wide because the distribution
        # is skewed rather than because the estimate is unstable, and section 6
        # quotes the throughput pair. All four were typed by hand.
        # `.get` rather than indexing: these two columns arrived with the
        # throughput reporting and a caller holding an older row shape should
        # lose a macro, not crash the generator. The "every generated number
        # is used" gate catches the loss from the other side.
        always_rows = {row["system"]: row for row in always}
        aep_always_row = always_rows.get("AEP_FULL", {})
        aep_everysec_row = next(
            (row for row in latency if row["system"] == "AEP_FULL"), {}
        )
        if aep_always_row.get("step_latency_ms_p95"):
            macro(
                "AepAlwaysPninetyfive",
                tex_number(float(aep_always_row["step_latency_ms_p95"])),
                "fsync-always/analysis/latency-and-throughput.csv | "
                "system=AEP_FULL, appendfsync=always",
                "step_latency_ms_p95",
            )
        if aep_always_row.get("executions_per_second"):
            macro(
                "AepThroughputAlways",
                f"{float(aep_always_row['executions_per_second']):.2f}",
                "fsync-always/analysis/latency-and-throughput.csv | "
                "system=AEP_FULL, appendfsync=always",
                "executions_per_second",
            )
        if aep_everysec_row.get("executions_per_second"):
            macro(
                "AepThroughputEverysec",
                f"{float(aep_everysec_row['executions_per_second']):.2f}",
                "latency-and-throughput.csv | system=AEP_FULL, "
                "appendfsync=everysec",
                "executions_per_second; the everysec matrix collected more "
                "runs per cell, so wall time per execution is not comparable "
                "as a benchmark -- it is quoted only against the always arm",
            )

    # --- G3: the durable-execution engine's two corners ------------------
    # B4 and B4b are one design in two configurations, and the argument is
    # that they land on *different* corners of the trilemma rather than on a
    # better one. That only reads as a finding if both corners are quoted, so
    # both are emitted for every capability class.
    #
    # This loop listed two classes until Phase P. AUTHORITATIVE_READBACK was
    # left out while those cells were still partial, and the omission outlived
    # the reason for it: Phase 5A completed both cells to 180 executions, and
    # the prose that wanted to quote them had no macro to quote, so it quoted
    # a hand-written 0.9500 that the completed cell then contradicted
    # (reports/phase-report-5a-2026-08-10.md sections E.5 and G.1). A
    # capability class missing from this tuple is a number the manuscript will
    # end up typing by hand.
    for system, key, metric in (
        ("B4_DURABLE_WORKFLOW", "Bfour", "undetected_duplicate_rate"),
        ("B4B_DURABLE_WORKFLOW_AT_MOST_ONCE", "Bfourb", "lost_effect_rate"),
    ):
        for response, suffix in (
            ("AUTHORITATIVE_READBACK", "Auth"),
            ("POSITIVE_ONLY_READBACK", "PosOnly"),
            ("NO_READBACK", "NoReadback"),
        ):
            subset = [
                r
                for r in crashed
                if r["system"] == system and r["response_class"] == response
            ]
            successes, total = totals(subset, metric)
            if not total:
                continue
            tag = "Dup" if metric == "undetected_duplicate_rate" else "Lost"
            macro(
                f"{key}{tag}{suffix}",
                rate(successes, total),
                f"per-cell-metrics.csv | system={system} "
                f"regime={CRASHED_REGIME} response_class={response}",
                f"metric={metric} | sum(successes)/sum(total) "
                f"= {successes}/{total}",
            )
            macro(
                f"{key}Exec{suffix}",
                str(total),
                f"per-cell-metrics.csv | executions behind \\{key}{tag}{suffix}",
            )

    # The third corner is the one neither configuration reaches, and the
    # manuscript needs to say so without typing a zero. A ceiling over every
    # B4/B4b cell says it in the one form that stays true if a cell ever moves:
    # the claim is "never above this", not "exactly zero everywhere", so a
    # future nonzero cell changes the number instead of silently falsifying a
    # sentence.
    family_amb: list[float] = []
    for row in crashed:
        if row["system"] not in (
            "B4_DURABLE_WORKFLOW",
            "B4B_DURABLE_WORKFLOW_AT_MOST_ONCE",
        ):
            continue
        if row["metric"] != "known_ambiguity_rate":
            continue
        total = int(row["total"])
        if total:
            family_amb.append(int(row["successes"]) / total)
    if family_amb:
        macro(
            "BfourFamilyAmbMax",
            f"{max(family_amb):.4f}",
            "per-cell-metrics.csv | max known_ambiguity_rate over "
            "{B4,B4b} x {all capability classes} x {all crash points}",
            f"regime={CRASHED_REGIME} | {len(family_amb)} cells",
            "the durable-execution engine never declares ambiguity; that is "
            "the corner of the trilemma it cannot reach",
        )
        macro(
            "BfourFamilyAmbCells",
            str(len(family_amb)),
            "per-cell-metrics.csv | cells behind \\BfourFamilyAmbMax",
        )

    # --- G1: the ablation's NULL result, on detection --------------------
    # The barrier is an ablation of AEP-full and it changes nothing that RQ1
    # measures. That is a finding, so it is generated rather than asserted:
    # every macro below is a number a reader can check, including the
    # p-values that say the two systems are indistinguishable.
    for response in RESPONSE_ORDER:
        subset = [
            r
            for r in crashed
            if r["system"] == "B3_INTENT_NO_BARRIER"
            and r["response_class"] == response
        ]
        suffix = {
            "AUTHORITATIVE_READBACK": "Auth",
            "POSITIVE_ONLY_READBACK": "PosOnly",
            "NO_READBACK": "NoReadback",
        }[response]
        # Only ambiguity varies by capability class and only ambiguity is
        # quoted per class in prose. The duplicate and lost-effect rates are
        # uniformly zero for both systems and are read off \cref{tab:ablation},
        # which prints all nine cells; a macro per cell would be nine more
        # numbers with no reader.
        successes, total = totals(subset, "known_ambiguity_rate")
        macro(
            f"BthreeAmb{suffix}",
            rate(successes, total),
            f"per-cell-metrics.csv | system=B3_INTENT_NO_BARRIER "
            f"regime={CRASHED_REGIME} response_class={response}",
            f"metric=known_ambiguity_rate | sum(successes)/sum(total) "
            f"= {successes}/{total}",
        )

    arms: set[str] = set()
    # The run counts behind those execution counts. The zero-event bound was
    # computed on executions only, which treats 540 executions as 540
    # independent trials when they are 54 runs of 10. That is the same
    # execution-level independence \cref{tab:ablation}'s own caption disclaims
    # for the Fisher values, and nothing disclaimed it here. Collected so the
    # bound can be emitted at both units rather than at the narrower one alone.
    arm_runs: set[str] = set()
    for metric, tag in (
        ("undetected_duplicate_rate", "Dup"),
        ("lost_effect_rate", "Lost"),
        ("known_ambiguity_rate", "Amb"),
    ):
        row = next(
            (
                r
                for r in comparisons
                if r["regime"] == CRASHED_REGIME
                and r["system"] == "B3_INTENT_NO_BARRIER"
                and r["metric"] == metric
            ),
            None,
        )
        if not row:
            continue
        arms.add(row["system_total"])
        arms.add(row["reference_total"])
        arm_runs.add(row["system_runs"])
        arm_runs.add(row["reference_runs"])
        macro(
            f"BthreeVsAep{tag}P",
            tex_p_value(float(row["fisher_p_value"])),
            f"comparisons-vs-aep-full.csv | metric={metric} "
            f"regime={CRASHED_REGIME} system=B3_INTENT_NO_BARRIER "
            "reference=AEP_FULL",
            f"B3 {row['system_successes']}/{row['system_total']} vs "
            f"AEP-full {row['reference_successes']}/{row['reference_total']}",
            (
                "execution-level Fisher value is descriptive only; the "
                "run-cluster difference interval is the ambiguity evidence"
                if metric == "known_ambiguity_rate"
                else "execution-level Fisher value is descriptive only; the "
                "one-sided zero-event bound is the reported evidence"
            ),
        )
    if len(arms) == 1:
        per_arm = arms.pop()
        macro(
            "BthreeVsAepN",
            per_arm,
            "comparisons-vs-aep-full.csv | executions per arm, identical "
            "across all three metrics",
        )
        # A Fisher test on two zero counts returns p = 1.00 and means
        # nothing: it has no power, and "we could not distinguish them" is
        # not "they are the same". What IS defensible from two zero counts is
        # a bound. This call deliberately uses Phi^-1(0.95), not the 1.96
        # quantile of a two-sided 95% interval. For two simultaneous bounds,
        # the joint coverage is at least 90% by Bonferroni.
        upper = wilson_upper_bound(0, int(per_arm), confidence=0.95)
        # The same bound at the two units, each named in the macro rather than
        # left to the prose. Which one is defensible is not a presentational
        # choice: 10 executions share a run, a crash point and a system, so the
        # execution-level denominator is false by construction and the bound
        # built on it is too narrow. With zero events the within-run
        # correlation cannot be estimated from the data, so the run is taken as
        # the unit -- the conservative reading, and the one this file already
        # applies to the declared-ambiguity difference.
        macro(
            "AblationZeroUpperExec",
            f"{upper * 100:.2f}",
            f"one-sided Wilson 95% upper bound on 0/{per_arm} EXECUTIONS",
            "assumes the executions are independent trials; they are not, and "
            "this is the value that assumption buys",
            "uses z=Phi^-1(0.95), not the two-sided 97.5th quantile",
        )
        if len(arm_runs) == 1:
            per_arm_runs = arm_runs.pop()
            upper_run = wilson_upper_bound(0, int(per_arm_runs), confidence=0.95)
            macro(
                "BthreeVsAepRuns",
                per_arm_runs,
                "comparisons-vs-aep-full.csv | run clusters per arm, identical "
                "across all three metrics",
                f"{per_arm} executions over {per_arm_runs} runs "
                f"= {int(per_arm) // int(per_arm_runs)} executions per run",
            )
            macro(
                "AblationZeroUpperRun",
                f"{upper_run * 100:.2f}",
                "comparisons-vs-aep-full.csv | one-sided Wilson 95% upper "
                f"bound on 0/{per_arm_runs} RUN CLUSTERS",
                f"{per_arm} executions over {per_arm_runs} runs; the run is "
                "the independent unit, so this is the reported bound",
                "uses z=Phi^-1(0.95), not the two-sided 97.5th quantile",
                "the unit was not chosen for the result: the baselines it is "
                "contrasted against are \\BaselineDupLowPct-\\BaselineDupHighPct"
                "%, so the contrast is unaffected either way",
            )
            # The same construction at per-class scope, which is what
            # \cref{tab:outcomes}'s columns actually are. Three capability
            # classes x two systems is six simultaneous bounds, so Bonferroni
            # needs each at 1 - 0.10/6 to hold the same joint 90%. This exists
            # so the paper can say WHY it declines to claim equivalence per
            # class, rather than dropping the scope silently.
            #
            # Derived from the per-class run counts, not by dividing the pooled
            # one by three. The six arm-classes happen to be balanced at 18 and
            # nothing enforces that, so this refuses to emit if they ever stop
            # being equal rather than quietly averaging them.
            per_class_runs: dict[tuple[str, str], int] = {}
            for row in crashed:
                if (
                    row["system"] in ("AEP_FULL", "B3_INTENT_NO_BARRIER")
                    and row["metric"] == "undetected_duplicate_rate"
                ):
                    key = (row["system"], row["response_class"])
                    per_class_runs[key] = per_class_runs.get(key, 0) + int(
                        row["runs"]
                    )
            distinct = set(per_class_runs.values())
            if per_class_runs and len(distinct) == 1:
                class_runs = distinct.pop()
                simultaneous = len(per_class_runs)
                joint = 1.0 - (1.0 - 0.90) / simultaneous
                upper_class = wilson_upper_bound(0, class_runs, confidence=joint)
                macro(
                    "AblationZeroUpperPerClass",
                    f"{upper_class * 100:.1f}",
                    "per-cell-metrics.csv | one-sided Wilson upper bound on "
                    f"0/{class_runs} run clusters, per arm per capability class",
                    f"{simultaneous} simultaneous bounds (3 capability classes "
                    f"x 2 systems), so Bonferroni sets each at "
                    f"{joint * 100:.3f}% to hold joint coverage at 90%",
                    "this is the width the phrase 'on every capability class' "
                    "would have to carry, and it is why the paper declines to "
                    "make that claim rather than omitting it silently",
                )
        # The numerators themselves. "a rate of 0" was written as a bare
        # numeral in four places, which made the paper's most load-bearing
        # zero the one number no gate looked at. Emitted as the larger of the
        # two arms so the sentence built on it -- "neither system records more
        # than this" -- cannot become false without this number moving.
        for metric, tag in (
            ("undetected_duplicate_rate", "Dup"),
            ("lost_effect_rate", "Lost"),
        ):
            row = next(
                (
                    r
                    for r in comparisons
                    if r["regime"] == CRASHED_REGIME
                    and r["system"] == "B3_INTENT_NO_BARRIER"
                    and r["metric"] == metric
                ),
                None,
            )
            if not row:
                continue
            worst = max(
                int(row["system_successes"]), int(row["reference_successes"])
            )
            macro(
                f"BthreeVsAep{tag}Count",
                str(worst),
                f"comparisons-vs-aep-full.csv | metric={metric}, the larger "
                "of the two arms' numerators",
                f"B3 {row['system_successes']}/{row['system_total']} vs "
                f"AEP-full {row['reference_successes']}/"
                f"{row['reference_total']}",
            )
        # The one metric on which the two systems are not identical, as a
        # count. Both the abstract and section 6 described it in words -- "two
        # executions in six hundred" -- which is a measurement spelled out,
        # and a spelled-out measurement is invisible to every check that looks
        # for digits. It is a difference of counts, so it is emitted as one.
        amb = next(
            (
                r
                for r in comparisons
                if r["regime"] == CRASHED_REGIME
                and r["system"] == "B3_INTENT_NO_BARRIER"
                and r["metric"] == "known_ambiguity_rate"
            ),
            None,
        )
        if amb:
            macro(
                "BthreeAmbCount",
                amb["system_successes"],
                "comparisons-vs-aep-full.csv | crashed known_ambiguity_rate, "
                "B3 numerator",
            )
            macro(
                "AepAmbCount",
                amb["reference_successes"],
                "comparisons-vs-aep-full.csv | crashed known_ambiguity_rate, "
                "AEP-full numerator",
            )
            macro(
                "BthreeVsAepAmbDelta",
                str(
                    abs(
                        int(amb["system_successes"])
                        - int(amb["reference_successes"])
                    )
                ),
                "comparisons-vs-aep-full.csv | metric=known_ambiguity_rate, "
                "|B3 successes - AEP-full successes|",
                f"|{amb['system_successes']} - {amb['reference_successes']}| "
                f"over {amb['system_total']} executions per arm",
            )
            macro(
                "BthreeVsAepAmbDiffPP",
                f"{float(amb['difference_rate']) * 100:.2f}",
                "comparisons-vs-aep-full.csv | crashed known_ambiguity_rate, "
                "100 * (B3 rate - AEP-full rate)",
            )
            macro(
                "BthreeVsAepAmbDiffLow",
                f"{float(amb['difference_ci_low']) * 100:.2f}",
                "comparisons-vs-aep-full.csv | lower endpoint of stratified "
                "run-cluster bootstrap difference interval, percentage points",
            )
            macro(
                "BthreeVsAepAmbDiffHigh",
                f"{float(amb['difference_ci_high']) * 100:.2f}",
                "comparisons-vs-aep-full.csv | upper endpoint of stratified "
                "run-cluster bootstrap difference interval, percentage points",
            )
            macro(
                "BthreeVsAepAmbDiffConfidence",
                f"{float(amb['difference_confidence']) * 100:.0f}",
                "comparisons-vs-aep-full.csv | confidence level of declared-"
                "ambiguity difference interval",
            )
            macro(
                "BthreeVsAepAmbMargin",
                f"{float(amb['equivalence_margin']) * 100:.0f}",
                "comparisons-vs-aep-full.csv | revision-stage operational "
                "equivalence margin, percentage points; not preregistered",
            )
            macro(
                "BthreeVsAepAmbClusters",
                amb["system_clusters"],
                "comparisons-vs-aep-full.csv | run clusters per arm in the "
                "declared-ambiguity interval",
            )
            macro(
                "BthreeVsAepAmbStrata",
                amb["difference_strata"],
                "comparisons-vs-aep-full.csv | matched crash-point x "
                "capability x keying strata",
            )

    def emit_kill_macros(macro, key: str, row: dict[str, str], rate) -> None:
        """The four per-arm kill macros for one (system, response_class) row.

        Extracted so the headline class and any additional class emit through
        exactly one code path; the emitted text is unchanged from before the
        (system, response_class) keying was introduced.
        """
        applied = int(row["executions_with_an_applied_effect"])
        executions = int(row["executions"])
        macro(
            f"{key}KillApplied",
            row["executions_with_an_applied_effect"],
            f"redis-kill-ablation.csv | regime={row['regime']} "
            f"system={row['system']} response_class={row['response_class']}",
            "executions_with_an_applied_effect",
        )
        macro(
            f"{key}UnwantedRate",
            rate(applied, executions),
            f"redis-kill-ablation.csv | regime={row['regime']} "
            f"system={row['system']} response_class={row['response_class']}",
            f"unwanted-applied-effect rate = "
            f"executions_with_an_applied_effect/executions = "
            f"{applied}/{executions}",
            "an effect put on the wire while the durability of its own "
            "intent record could no longer be confirmed",
        )
        macro(
            f"{key}KillRuns",
            row["runs"],
            f"redis-kill-ablation.csv | runs for {row['system']}",
        )
        macro(
            f"{key}KillCanary",
            f"{row['canary_survived']}/{int(row['canary_survived']) + int(row['canary_lost'])}",
            f"redis-kill-ablation.csv | canary_survived/(survived+lost) "
            f"for {row['system']}",
            "the un-acknowledged write made immediately before the hard kill",
        )

    # --- G1/RQ2: the hard-Redis-kill ablation ---------------------------
    # The barrier's own metric. Named `Unwanted` rather than `Applied`
    # because "applied an effect" is not by itself a failure -- a dispatch
    # that the coordinator authorised is supposed to apply one. What this
    # counts is effects applied when durability could no longer be
    # confirmed, which is the thing the barrier exists to prevent.
    #
    # Keyed by (system, response_class), NOT by system. `analyze.py` groups this
    # evidence by ["regime", "system", "response_class"], so a second capability
    # class makes this file 2N rows. Keying by system alone let the last row win
    # and silently re-bound \AepKillApplied and friends to whichever class sorted
    # last, while section 6.2.2's prose named `no-readback` -- and because the
    # macros still regenerated byte-identically from the new CSV, the numbers
    # gate would have passed over it. The headline macros therefore name their
    # class explicitly, and any further class gets its own suffixed names rather
    # than overwriting them.
    KILL_SYSTEM_KEYS = (("AEP_FULL", "Aep"), ("B3_INTENT_NO_BARRIER", "Bthree"))
    #: The class the manuscript's prevention prose describes. Headline macros
    #: bind to this row and to no other.
    HEADLINE_KILL_CLASS = "NO_READBACK"
    #: Suffixes for any additional class, matching the crashed-regime naming
    #: already used by \AepAmbAuth / \AepAmbPosOnly.
    KILL_CLASS_SUFFIX = {
        "AUTHORITATIVE_READBACK": "Auth",
        "POSITIVE_ONLY_READBACK": "PosOnly",
    }

    kill_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in kill:
        system_key = dict(KILL_SYSTEM_KEYS).get(row["system"])
        if not system_key:
            continue
        pair = (system_key, row["response_class"])
        if pair in kill_by_key:
            raise SystemExit(
                "redis-kill-ablation.csv has two rows for "
                f"{row['system']} x {row['response_class']}. A (system, "
                "response_class) pair must be unique; re-run analyze.py."
            )
        kill_by_key[pair] = row

    present_classes = sorted({cls for _, cls in kill_by_key})
    if kill_by_key and HEADLINE_KILL_CLASS not in present_classes:
        raise SystemExit(
            f"redis-kill-ablation.csv has no {HEADLINE_KILL_CLASS} rows "
            f"(found {present_classes}). The manuscript's prevention result is "
            f"stated for {HEADLINE_KILL_CLASS}; refusing to bind its macros to "
            "a different class."
        )
    for cls in present_classes:
        if cls != HEADLINE_KILL_CLASS and cls not in KILL_CLASS_SUFFIX:
            raise SystemExit(
                f"redis-kill-ablation.csv contains response class {cls!r}, "
                "which has no macro suffix. Add one to KILL_CLASS_SUFFIX "
                "rather than letting it collide with the headline macros."
            )

    # Headline class first, in a fixed system order, so the emitted file does not
    # depend on CSV row order; then any additional class, suffixed.
    ordered = [(HEADLINE_KILL_CLASS, "")] + [
        (cls, KILL_CLASS_SUFFIX[cls])
        for cls in present_classes
        if cls != HEADLINE_KILL_CLASS
    ]
    for response_class, suffix in ordered:
        for _, key in KILL_SYSTEM_KEYS:
            row = kill_by_key.get((key, response_class))
            if row is None:
                continue
            key = f"{key}{suffix}" if suffix else key
            emit_kill_macros(macro, key, row, rate)

    kill_by_system = {
        key: kill_by_key[(key, HEADLINE_KILL_CLASS)]
        for _, key in KILL_SYSTEM_KEYS
        if (key, HEADLINE_KILL_CLASS) in kill_by_key
    }
    if {"Aep", "Bthree"} <= kill_by_system.keys():
        aep_row = kill_by_system["Aep"]
        b3_row = kill_by_system["Bthree"]
        aep_applied = int(aep_row["executions_with_an_applied_effect"])
        b3_applied = int(b3_row["executions_with_an_applied_effect"])
        aep_n = int(aep_row["executions"])
        b3_n = int(b3_row["executions"])
        macro(
            "UnwantedPrevented",
            str(b3_applied - aep_applied),
            "redis-kill-ablation.csv | B3 applied - AEP-full applied",
            f"= {b3_applied} - {aep_applied}; real non-idempotent effects "
            "that the barrier withheld under an identical injected fault",
        )
        macro(
            "UnwantedP",
            tex_p_value(
                fisher_exact_two_tailed(
                    aep_applied,
                    aep_n - aep_applied,
                    b3_applied,
                    b3_n - b3_applied,
                )
            ),
            "redis-kill-ablation.csv | Fisher exact two-tailed on "
            f"[[{aep_applied}, {aep_n - aep_applied}], "
            f"[{b3_applied}, {b3_n - b3_applied}]]",
            "AEP-full vs B3 on the unwanted-applied-effect rate",
        )
        # The canary total across both arms. Sections 6 and 8 both cite it as
        # "n=60" -- the second, independent replication of the process-kill
        # result -- and both typed it, which is one addition nobody re-checked
        # after the cells were recollected.
        canaries = sum(
            int(row["canary_survived"]) + int(row["canary_lost"])
            for row in (aep_row, b3_row)
        )
        macro(
            "KillCanaryN",
            str(canaries),
            "redis-kill-ablation.csv | canary_survived + canary_lost, summed "
            "over AEP_FULL and B3_INTENT_NO_BARRIER",
            "un-acknowledged writes made immediately before a hard Redis "
            "kill, inside the ablation cells",
        )

    # --- G2: the fault class the barrier's durability claim names --------
    if flakey:
        for name, value, *why in flakey_macros(flakey):
            macro(name, value, *why)

    # --- The barrier's cost, with an interval rather than a point --------
    # A difference of two medians from three runs each. Reported with a
    # cluster bootstrap over runs, because the hostile read's sharpest
    # surviving objection was that the headline cost figure carried no
    # uncertainty at all.
    for policy, tag in (("everysec", ""), ("always", "Always")):
        path = execution_paths.get(policy)
        if not path:
            continue
        treated = crash_free_latencies(path, "AEP_FULL")
        ablated = crash_free_latencies(path, "B3_INTENT_NO_BARRIER")
        if not treated or not ablated:
            continue
        point, low, high = cluster_bootstrap_median_difference(treated, ablated)
        macro(
            f"BarrierCost{tag}Low",
            tex_number(low),
            f"{path.parent.name}/per-execution.csv | cluster bootstrap over "
            f"runs, 10000 resamples, seed 20260806, appendfsync={policy}",
            f"2.5th percentile of (median AEP-full - median B3); "
            f"point estimate {point:.1f} ms from "
            f"{len(treated)} and {len(ablated)} runs",
        )
        macro(
            f"BarrierCost{tag}High",
            tex_number(high),
            f"{path.parent.name}/per-execution.csv | 97.5th percentile of the "
            f"same bootstrap, appendfsync={policy}",
        )

    # --- The same interval for the OTHER half of the decomposition -------
    # \BarrierToProtocolRatio divides one median difference by another, and
    # until now only the numerator carried an interval. The denominator is the
    # weaker of the two: three runs per arm, and a spread wide enough that the
    # ratio is pinned to about one order of magnitude rather than to a figure.
    # Threats-to-validity quotes both endpoints so the ratio is read as a
    # median-based estimate rather than as a measurement of "70".
    #
    # everysec only, deliberately. The `always` arm has no sentence quoting
    # it, and the "every generated number is used" gate turns an unquoted
    # macro into a build failure rather than into clutter.
    everysec_path = execution_paths.get("everysec")
    if everysec_path:
        protocol = crash_free_latencies(everysec_path, "B3_INTENT_NO_BARRIER")
        no_protocol = crash_free_latencies(everysec_path, "B0_NAIVE_RETRY")
        if protocol and no_protocol:
            point, low, high = cluster_bootstrap_median_difference(
                protocol, no_protocol
            )
            macro(
                "ProtocolMinusBarrierLow",
                tex_number(low),
                "analysis/per-execution.csv | cluster bootstrap over runs, "
                "10000 resamples, seed 20260806, appendfsync=everysec",
                f"2.5th percentile of (median B3 - median B0); point estimate "
                f"{point:.1f} ms from {len(protocol)} and "
                f"{len(no_protocol)} runs",
            )
            macro(
                "ProtocolMinusBarrierHigh",
                tex_number(high),
                "analysis/per-execution.csv | 97.5th percentile of the same "
                "bootstrap, appendfsync=everysec",
                "the denominator of \\BarrierToProtocolRatio; its width is "
                "why that factor is quoted as an estimate",
            )

    # --- Coverage, from the analysis tool's own census -------------------
    if coverage:
        for name, key in (
            ("RunsCollected", "runs"),
            ("ExecutionsCollected", "executions"),
            ("CellsCollected", "cells"),
            # Not a measurement -- a parameter of the method. It is generated
            # anyway because analyze.py records it, which means it can change
            # without the sentence that states it changing: every interval in
            # the paper would move and "10,000 resamples" would still read
            # true. A constant that lives in the results is a constant that
            # can drift.
            ("BootstrapResamples", "bootstrap_resamples"),
        ):
            if key in coverage:
                macro(
                    name,
                    f"{int(coverage[key]):,}".replace(",", r"\,"),
                    f"analysis/coverage.json | {key}",
                )

    # --- E1: what a hard process kill actually loses ---------------------
    # The probe that found the barrier does nothing against a SIGKILL. Its
    # numbers -- ten trials, zero unacknowledged writes lost, and the window
    # each kill landed inside -- were typed into three sections by hand,
    # because the probe writes a raw report rather than a CSV and nothing here
    # read it. It is tracked, so it can be read: a number quoted in three
    # places and generated in none is three chances to update two of them.
    probe = ROOT / "reports" / "raw" / "e1-durability-window.txt"
    if probe.is_file():
        text = probe.read_text(encoding="utf-8", errors="replace")
        windows = [int(m) for m in re.findall(r"write->death=\s*(\d+)ms", text)]
        lost = re.search(
            r"unacknowledged write lost in (\d+)/(\d+) usable trials", text
        )
        if windows and lost:
            macro(
                "ProcessKillUnackLost",
                f"{lost.group(1)}/{lost.group(2)}",
                f"reports/raw/{probe.name} | un-acknowledged writes lost to "
                "`docker kill -s KILL` under appendfsync=everysec",
                "everysec defers the fsync, not the write; a still-running "
                "kernel flushes the page cache",
            )
            macro(
                "ProcessKillTrials",
                lost.group(2),
                f"reports/raw/{probe.name} | usable trials",
            )
            macro(
                "ProcessKillWindowMin",
                str(min(windows)),
                f"reports/raw/{probe.name} | min write->death over "
                f"{len(windows)} trials, ms",
            )
            macro(
                "ProcessKillWindowMax",
                str(max(windows)),
                f"reports/raw/{probe.name} | max write->death over "
                f"{len(windows)} trials, ms",
                "every kill landed inside the 1000 ms fsync period, which is "
                "what makes the zero above a measurement rather than a miss",
            )

    # --- Phase 8.1: the kill cell replicated, and why its magnitude moves --
    #
    # The ablation cell above was collected once. It has since been collected
    # four more times under an identical configuration, and AEP-full's applied
    # count moved 4 -> 20 out of 30 while B3 recorded 28/30 in every session.
    # \UnwantedPrevented is therefore a point estimate of a quantity that is not
    # a point: these macros are what let the manuscript say so with numbers
    # rather than with an apology.
    #
    # The four replication sessions are read, and the original cell is NOT
    # pooled with them. They differ in a way no run-config key records: the
    # original was collected in the WSL-native tree on ext4, the four
    # replications through /mnt/d on drvfs, where an event-log append costs
    # ~40x more. Pooling a heterogeneous five to widen an interval would trade
    # a stated limitation for an unstated confound.
    REPLICATION_ROOTS = (
        ("P9-B", "b2-2026-08-21"),
        ("s1", "b2-s1-2026-08-21"),
        ("s2", "b2-s2-2026-08-21"),
        ("s3", "b2-s3-2026-08-21"),
    )
    replication: list[dict[str, int]] = []
    for _, directory in REPLICATION_ROOTS:
        path = (
            ROOT / "experiments" / "results" / directory
            / "analysis" / "redis-kill-ablation.csv"
        )
        if not path.is_file():
            replication = []
            break
        by_system = {row["system"]: row for row in read_rows(path)}
        aep_row = by_system.get("AEP_FULL")
        b3_row = by_system.get("B3_INTENT_NO_BARRIER")
        if not aep_row or not b3_row:
            replication = []
            break
        replication.append(
            {
                "aep": int(aep_row["executions_with_an_applied_effect"]),
                "b3": int(b3_row["executions_with_an_applied_effect"]),
                "n": int(aep_row["executions"]),
            }
        )

    if len(replication) == len(REPLICATION_ROOTS):
        prevented = [row["b3"] - row["aep"] for row in replication]
        aep_applied = [row["aep"] for row in replication]
        b3_applied = [row["b3"] for row in replication]
        sessions = len(replication)
        per_arm = sum(row["n"] for row in replication)
        mean_prevented = statistics.mean(prevented)
        # Session as the unit, not the execution. Pooling the 120 executions
        # would treat them as independent draws when they share a session's
        # host-timing state; session 3B's no-pooling rule and the run-cluster
        # bootstrap used elsewhere in this file are the same argument.
        stdev_prevented = statistics.stdev(prevented)
        # t(0.975, 3). Spelled out because scipy is not a dependency and a
        # hard-coded critical value must be checkable against a table.
        t_critical = 3.182
        half_width = t_critical * stdev_prevented / math.sqrt(sessions)
        macro(
            "ReplicationSessions",
            str(sessions),
            "experiments/results/b2-*/analysis/redis-kill-ablation.csv | "
            "independent re-collections of the redis-kill-preack cell",
            "each an identical configuration, same seed, same pinned image",
        )
        macro(
            "ReplicationRuns",
            str(per_arm),
            f"experiments/results/b2-*/ | executions per arm over "
            f"{sessions} sessions",
        )
        macro(
            "ReplicationPreventedMean",
            f"{mean_prevented:.1f}",
            "b2-*/analysis/redis-kill-ablation.csv | mean over sessions of "
            "(B3 applied - AEP-full applied)",
            f"= mean{tuple(prevented)}",
        )
        macro(
            "ReplicationPreventedLow",
            f"{mean_prevented - half_width:.1f}",
            "b2-*/analysis/redis-kill-ablation.csv | session-clustered 95% "
            f"interval, t({sessions - 1}) = {t_critical}, session as the unit",
        )
        macro(
            "ReplicationPreventedHigh",
            f"{mean_prevented + half_width:.1f}",
            "b2-*/analysis/redis-kill-ablation.csv | upper end of the same "
            "interval",
            "wide because the quantity moves between sessions, not because "
            "the sessions are few",
        )
        macro(
            "ReplicationAepMin",
            str(min(aep_applied)),
            "b2-*/analysis/redis-kill-ablation.csv | fewest AEP-full "
            "executions with an applied effect, over sessions",
        )
        macro(
            "ReplicationAepMax",
            str(max(aep_applied)),
            "b2-*/analysis/redis-kill-ablation.csv | most, over sessions",
            "a five-fold spread on a cell whose configuration did not change",
        )
        macro(
            "ReplicationBthreeApplied",
            str(b3_applied[0]) if len(set(b3_applied)) == 1 else "varies",
            "b2-*/analysis/redis-kill-ablation.csv | B3 executions with an "
            "applied effect, identical in every session",
        )
        macro(
            "ReplicationBthreeRange",
            str(max(b3_applied) - min(b3_applied)),
            "b2-*/analysis/redis-kill-ablation.csv | max - min of the same "
            "column over sessions",
            "zero: the arm that never waits for the barrier does not move",
        )

    # --- Phase 8.4/8.5: the capability-class comparison ------------------
    # The four pre-registered sessions that settle whether capability class
    # moves the applied-effect column. Read from the same hashed artefact as
    # the replication block above, and reported on the SAME construction:
    # session as the unit, mean, t(k-1), half-width t*sd/sqrt(k). One
    # inferential standard in this file, not two.
    #
    # Percentage points, not log-odds. The estimand is fitted per session as a
    # logistic regression, but no fitter exists in this generator or in
    # experiments.statistics, and adding one to emit two decimal places would
    # be a far larger change than the claim needs. The paragraph these macros
    # serve argues from the applied-effect rate, which is what the surrounding
    # text already uses. The log-odds coefficients live in
    # reports/phase-report-8-5-step-4-primary-estimand-2026-08-31.md.
    #
    # The registered MDE is deliberately NOT emitted. It was computed as a
    # pooled binomial across all k sessions with no between-session variance
    # component (backlog B19), which is the same omission the realised spread
    # exposed, so quoting it as the standard would propagate the defect. The
    # comparison the text makes instead is self-contained: the half-width
    # against the observed mean.
    CLASS_ROOTS = (
        "b2-paired-v2-s1-2026-08-28",
        "b2-paired-v2-s2-2026-08-28",
        "b2-paired-v2-s3-2026-08-28",
        "b2-paired-v2-s4-2026-08-28",
    )
    class_pp: list[float] = []
    class_arm_n: set[int] = set()
    for directory in CLASS_ROOTS:
        path = (
            ROOT / "experiments" / "results" / directory
            / "analysis" / "redis-kill-ablation.csv"
        )
        if not path.is_file():
            class_pp = []
            break
        by_class = {
            row["response_class"]: row
            for row in read_rows(path)
            if row["system"] == "AEP_FULL"
        }
        auth = by_class.get("AUTHORITATIVE_READBACK")
        norb = by_class.get("NO_READBACK")
        if not auth or not norb:
            class_pp = []
            break
        class_arm_n.update(
            {int(auth["executions"]), int(norb["executions"])}
        )
        class_pp.append(
            100.0
            * (
                int(auth["executions_with_an_applied_effect"])
                / int(auth["executions"])
                - int(norb["executions_with_an_applied_effect"])
                / int(norb["executions"])
            )
        )

    if len(class_pp) == len(CLASS_ROOTS):
        k_class = len(class_pp)
        class_mean = statistics.mean(class_pp)
        class_sd = statistics.stdev(class_pp)
        # t(0.975, 3), identical to the replication interval above.
        class_half = 3.182 * class_sd / math.sqrt(k_class)
        macro(
            "ClassSessions",
            str(k_class),
            "b2-paired-v2-*/analysis/redis-kill-ablation.csv | pre-registered "
            "sessions of the capability-class comparison",
            "all four run-level interleaved; k fixed in advance and not extended",
        )
        macro(
            "ClassRunsPerArm",
            str(sorted(class_arm_n)[0]) if len(class_arm_n) == 1 else "varies",
            "b2-paired-v2-*/analysis/redis-kill-ablation.csv | executions per "
            "arm per session",
        )
        for label, value in zip(("One", "Two", "Three", "Four"), class_pp):
            macro(
                f"ClassPp{label}",
                f"{value:+.1f}",
                "b2-paired-v2-*/analysis/redis-kill-ablation.csv | AEP-full "
                "AUTHORITATIVE_READBACK minus NO_READBACK applied rate, "
                "percentage points",
            )
        # The prose states the spread as a range. Emitting min and max derived
        # here, rather than letting the sentence name \ClassPpTwo and
        # \ClassPpFour, keeps the range correct if the sessions are ever
        # reordered, regenerated, or extended: those macros are session-indexed
        # and only happen to be the extremes today.
        macro(
            "ClassPpMin",
            f"{min(class_pp):+.1f}",
            "b2-paired-v2-*/analysis/redis-kill-ablation.csv | smallest of the "
            "per-session applied-rate differences",
            "derived as min over sessions, not a fixed session index",
        )
        macro(
            "ClassPpMax",
            f"{max(class_pp):+.1f}",
            "b2-paired-v2-*/analysis/redis-kill-ablation.csv | largest of the "
            "per-session applied-rate differences",
            "derived as max over sessions, not a fixed session index",
        )
        macro(
            "ClassPpMean",
            f"{class_mean:+.1f}",
            "b2-paired-v2-*/analysis/redis-kill-ablation.csv | mean over "
            "sessions of the applied-rate difference",
            f"= mean{tuple(round(v, 1) for v in class_pp)}",
        )
        macro(
            "ClassPpHalfWidth",
            f"{class_half:.1f}",
            "b2-paired-v2-*/analysis/redis-kill-ablation.csv | session-"
            f"clustered 95% half-width, t({k_class - 1}) = 3.182, session as "
            "the unit",
            "wider than the mean it brackets: the sessions disagree",
        )
        # \ClassPpLow and \ClassPpHigh straddle zero, so quoting the pair is
        # already a statement of the primary estimand's result -- the claim F.0
        # binds -- and a macro's whole purpose is to be quoted away from the
        # prose that currently carries the precision beside it. The note travels
        # with the value so the binding does not depend on the next author
        # having read section VIII.
        _INTERVAL_BINDING = (
            "F.0: this endpoint states the primary estimand's result. It may "
            "not be quoted without \\ClassPpHalfWidth (" + f"{class_half:.1f}"
            + " pp, wider than the "
            + f"{class_mean:+.1f}"
            + " pp mean) in the same sentence: the interval contains zero "
            "because the sessions disagree, not because the effect is absent"
        )
        macro(
            "ClassPpLow",
            f"{class_mean - class_half:+.1f}",
            "b2-paired-v2-*/analysis/redis-kill-ablation.csv | lower end of "
            "that interval",
            _INTERVAL_BINDING,
        )
        macro(
            "ClassPpHigh",
            f"{class_mean + class_half:+.1f}",
            "b2-paired-v2-*/analysis/redis-kill-ablation.csv | upper end",
            _INTERVAL_BINDING,
        )
        # \ClassPpMoved (sessions moving >= 20 pp: 2 of 4) is deliberately not
        # emitted. The prose states the spread and its direction instead, which
        # a count of sessions past an unregistered threshold understates. The
        # figure itself is not dropped -- it is stated in
        # reports/phase-report-8-5-step-4-primary-estimand-2026-08-31.md.

    # The mechanism. The harness has always recorded the `docker kill` latency
    # and nothing surfaced it; reports/raw/extract_kill_latency.py bridges the
    # raw runs to this file. AEP-full dispatches only if WAITAOF returns before
    # Redis dies, so that latency is the width of the race -- and B3, which
    # never waits, is a negative control the same data provides for free.
    latency_path = ROOT / "reports" / "raw" / "e1-kill-latency-by-run.csv"
    if latency_path.is_file():
        latency_rows = read_rows(latency_path)

        def _median_split(stratum: str, system: str) -> tuple[float, float, float, int]:
            subset = [
                r for r in latency_rows
                if r["filesystem"] == stratum and r["system"] == system
            ]
            applied = [int(r["issue_to_return_ns"]) / 1e6
                       for r in subset if r["applied"] == "1"]
            not_applied = [int(r["issue_to_return_ns"]) / 1e6
                           for r in subset if r["applied"] != "1"]
            if not applied or not_applied == []:
                return 0.0, 0.0, 1.0, len(subset)
            return (
                statistics.median(applied),
                statistics.median(not_applied),
                mann_whitney_two_tailed(applied, not_applied),
                len(subset),
            )

        for stratum, suffix, why in (
            ("drvfs", "", "the four replication sessions, one filesystem"),
            ("ext4", "Orig", "the paper's own cell, reported separately "
                             "because it differs in filesystem"),
        ):
            for system, system_suffix in (
                ("AEP_FULL", ""),
                ("B3_INTENT_NO_BARRIER", "Bthree"),
            ):
                hit, miss, p_value, count = _median_split(stratum, system)
                if not count:
                    continue
                name = f"KillLatency{system_suffix}{suffix}"
                macro(
                    f"{name}Diff",
                    f"{hit - miss:.0f}",
                    f"reports/raw/{latency_path.name} | {stratum} | {system} | "
                    "median issue_to_return_ns of runs that applied an effect "
                    "minus those that did not, ms",
                    f"= {hit:.1f} - {miss:.1f}; {why}",
                )
                macro(
                    f"{name}P",
                    tex_p_value(p_value),
                    f"reports/raw/{latency_path.name} | {stratum} | {system} | "
                    "Mann-Whitney two-tailed on the same two groups",
                )
                macro(
                    f"{name}N",
                    str(count),
                    f"reports/raw/{latency_path.name} | {stratum} | {system} | "
                    "runs",
                )

    # --- Implementation size, counted rather than remembered -------------
    # These were hand-written with a shell command in a comment beside them,
    # and the harness figure had drifted by 1,359 lines by the time anyone
    # re-ran it. A number in the paper that is not regenerated is a number
    # that is eventually wrong.
    for label, tree in (("Core", "aep_core"), ("Harness", "experiments")):
        directory = ROOT / tree
        if not directory.is_dir():
            continue
        total = 0
        files = 0
        for path in sorted(directory.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            total += len(path.read_text(encoding="utf-8", errors="replace").splitlines())
            files += 1
        macro(
            f"{label}Loc",
            f"{total:,}".replace(",", r"\,"),
            f"lines of Python under {tree}/, excluding __pycache__",
            f"{files} files; regenerated on every run of this script",
        )

    (out / "numbers.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument(
        "--fsync-analysis",
        type=Path,
        default=None,
        help="analysis dir of the appendfsync=always re-run; enables "
        "table-deployment-choice.tex",
    )
    parser.add_argument(
        "--flakey",
        type=Path,
        default=None,
        help="directory holding g2-flakey-write-loss*.json; enables the "
        "host-level write-loss macros",
    )
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.out.mkdir(parents=True, exist_ok=True)

    per_cell = read_rows(arguments.analysis / "per-cell-metrics.csv")
    if "regime" not in per_cell[0]:
        raise SystemExit(
            "per-cell-metrics.csv has no `regime` column. Re-run analyze.py: "
            "without it, a crash-free cell and a hard-Redis-kill cell can be "
            "averaged into one rate."
        )
    latency = read_rows(arguments.analysis / "latency-and-throughput.csv")
    kill = read_rows(arguments.analysis / "redis-kill-ablation.csv")
    comparisons = read_rows(arguments.analysis / "comparisons-vs-aep-full.csv")
    if not comparisons or "regime" not in comparisons[0]:
        raise SystemExit(
            "comparisons-vs-aep-full.csv has no `regime` column. Re-run "
            "experiments.rebuild_comparisons; pooled comparisons are not a "
            "valid paper source."
        )

    flakey: list[dict[str, Any]] = []
    if arguments.flakey:
        for path in sorted(arguments.flakey.glob("g2-flakey-write-loss*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("summary"):
                flakey.append(payload)

    always: list[dict[str, str]] = []
    if arguments.fsync_analysis:
        always = read_rows(
            arguments.fsync_analysis / "latency-and-throughput.csv"
        )

    emit_outcomes_table(per_cell, arguments.out)
    emit_ambiguity_by_crashpoint(per_cell, arguments.out)
    emit_ablation_table(per_cell, comparisons, arguments.out)
    emit_latency_table(latency, arguments.out)
    if always:
        emit_deployment_choice(latency, always, arguments.out)
    coverage_path = arguments.analysis / "coverage.json"
    coverage = (
        json.loads(coverage_path.read_text(encoding="utf-8"))
        if coverage_path.is_file()
        else {}
    )
    execution_paths = {"everysec": arguments.analysis / "per-execution.csv"}
    if arguments.fsync_analysis:
        execution_paths["always"] = (
            arguments.fsync_analysis / "per-execution.csv"
        )
    emit_numbers(
        per_cell, latency, kill, comparisons, flakey, always, coverage,
        execution_paths, arguments.out,
    )
    for name in sorted(p.name for p in arguments.out.glob("*.tex")):
        print(f"wrote {arguments.out / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
