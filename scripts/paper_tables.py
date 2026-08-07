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
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

# check_paper_numbers.py runs this file as a script, so sys.path[0] is
# scripts/ and `experiments` is not importable without help. Reusing the
# repository's exact Fisher implementation rather than reimplementing it is
# the point: a second implementation is a second thing to keep correct.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.statistics import fisher_exact_two_tailed  # noqa: E402

#: The regime whose runs answer RQ1. A regime is a named fault condition, not
#: a matrix dimension; ``(session-3)`` is the one in which every execution is
#: killed at the cell's crash point.
CRASHED_REGIME = "(session-3)"
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
    "after_intent_before_barrier": r"\texttt{after\_intent\_before\_barrier}",
    "after_barrier_before_dispatch": r"\texttt{after\_barrier\_before\_dispatch}",
    "mid_dispatch": r"\texttt{mid\_dispatch}",
    "after_response_before_resolution": r"\texttt{after\_response\_before\_res.}",
    "after_resolution_before_barrier": r"\texttt{after\_resolution\_before\_bar.}",
}
CRASH_POINT_ORDER = list(CRASH_POINT_LABEL)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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
        r"endpoint capability. \textsc{auth}/\textsc{pos-only}/\textsc{none} "
        r"are the reconciliation capabilities of \cref{tab:capabilities}. "
        r"AEP-full is the only system with a nonzero declared-ambiguity "
        r"column, and the only one whose other two columns are zero "
        r"everywhere. Source: \texttt{per-cell-metrics.csv}, crashed regime "
        r"only.}"
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
    lines.append(r"\begin{tabular}{@{}lrrr@{}}")
    lines.append(r"\toprule")
    lines.append(r"system & runs & median step (ms) & over B0 (ms)\\")
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
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    (out / "table-latency.tex").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


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
        "%         analysis/comparisons-vs-aep-full.csv (p-values).",
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{The barrier ablation on the detection metrics. B3 is "
        r"AEP-full with the \texttt{WAITAOF} barrier removed and nothing else "
        r"removed. Crashed regime; rates are over executions, pooled across "
        r"crash points within one capability class. The p-values are Fisher's "
        r"exact, two-tailed, over all capability classes together.}",
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
                if r["system"] == "B3_INTENT_NO_BARRIER" and r["metric"] == metric
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
        r"\begin{table}[t]",
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
        r"\begin{tabular}{@{}lrrrcl@{}}",
        r"\toprule",
        r"configuration & median & over & barrier & prev- & claim\\",
        r" & (ms) & floor & (ms) & ents & \\",
        r"\midrule",
    ]
    for label, median, barrier, prevents, claim in rows:
        fragment.append(
            f"{label} & {tex(median)} & {tex(median - 2000.0)} & "
            f"{tex(barrier)} & {prevents} & {claim}\\\\"
        )
    fragment += [
        r"\midrule",
        r"\multicolumn{6}{@{}p{0.94\columnwidth}@{}}{\footnotesize "
        r"The detection claim of \cref{tab:outcomes} is unchanged down the "
        r"whole table: it is produced by the durable pre-dispatch record, "
        r"which all three rows have, and \cref{tab:ablation} is the "
        r"ablation that shows it. What the barrier buys is the last "
        r"column's second word, and \cref{tab:killablation} is what it is "
        r"worth. `Over floor' is the same median less the provider's "
        r"2\,000\,ms delay, and so includes the "
        f"{tex(b3 - b0)}"
        r"\,ms the protocol costs with the barrier already removed.}\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
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
            macro(
                "BarrierCostRatio",
                f"{(aep - b3) / (aep_always - b3_always):.0f}",
                "\\BarrierCost / \\BarrierCostAlways -- what one line of "
                "durability configuration is worth on this workload",
            )
            macro(
                "BthreeAlwaysMedian",
                tex_number(b3_always),
                "fsync-always/analysis/latency-and-throughput.csv | "
                "system=B3_INTENT_NO_BARRIER, appendfsync=always",
                f"against {b3:.1f} ms under everysec: the ablated protocol's "
                "own cost is nearly policy-independent, which is what makes "
                "the two barrier figures comparable",
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
    for metric, tag in (
        ("undetected_duplicate_rate", "Dup"),
        ("lost_effect_rate", "Lost"),
        ("known_ambiguity_rate", "Amb"),
    ):
        row = next(
            (
                r
                for r in comparisons
                if r["system"] == "B3_INTENT_NO_BARRIER" and r["metric"] == metric
            ),
            None,
        )
        if not row:
            continue
        arms.add(row["system_total"])
        macro(
            f"BthreeVsAep{tag}P",
            tex_p_value(float(row["fisher_p_value"])),
            f"comparisons-vs-aep-full.csv | metric={metric} "
            "system=B3_INTENT_NO_BARRIER reference=AEP_FULL",
            f"B3 {row['system_successes']}/{row['system_total']} vs "
            f"AEP-full {row['reference_successes']}/{row['reference_total']}",
            "the ablation is indistinguishable from the full protocol here; "
            "that is the finding, not a caveat",
        )
    if len(arms) == 1:
        macro(
            "BthreeVsAepN",
            arms.pop(),
            "comparisons-vs-aep-full.csv | executions per arm, identical "
            "across all three metrics",
        )

    # --- G1/RQ2: the hard-Redis-kill ablation ---------------------------
    # The barrier's own metric. Named `Unwanted` rather than `Applied`
    # because "applied an effect" is not by itself a failure -- a dispatch
    # that the coordinator authorised is supposed to apply one. What this
    # counts is effects applied when durability could no longer be
    # confirmed, which is the thing the barrier exists to prevent.
    kill_by_system: dict[str, dict[str, str]] = {}
    for row in kill:
        key = {
            "AEP_FULL": "Aep",
            "B3_INTENT_NO_BARRIER": "Bthree",
        }.get(row["system"])
        if not key:
            continue
        kill_by_system[key] = row
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

    # --- G2: the fault class the barrier's durability claim names --------
    if flakey:
        for name, value, *why in flakey_macros(flakey):
            macro(name, value, *why)

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
    emit_numbers(
        per_cell, latency, kill, comparisons, flakey, always, arguments.out
    )
    for name in sorted(p.name for p in arguments.out.glob("*.tex")):
        print(f"wrote {arguments.out / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
