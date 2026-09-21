#!/usr/bin/env python3
"""C4' -- the replacement cost criterion, as something that runs.

``prompts/phase-40-amendment-5-cost-criterion-2026-09-21.md`` §4 replaces the
pre-registration's C4 ("measured cost within 20% of §3's model") after it failed
twice for a reason no healthy stage could have avoided: it compared a measured
mean against a ceiling written with ``<=`` signs.

The replacement is three limbs, and this file is them. A criterion that lives
only in prose is assessed by whoever is reading the prose; this one is assessed
by running it.

    python scripts/check_planner_cost.py <collection-root> [...]

Exit status is 0 if every limb passes for every collection given, 1 otherwise.

**The recomputation is deliberately not ``Price.usd``.** Amendment 5 §4.2: a
checker that calls the same function the writer called compares the code with
itself and would survive any drift in it. The formula below is written out from
the documented rule -- prompt tokens at the input rate, *completion plus
reasoning* tokens at the output rate -- so that a change to ``Usage.output``
(the term most easily dropped; reasoning tokens ran 4x the visible completion on
one recorded call) fails this check instead of quietly understating every bill.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.harness.planner import (  # noqa: E402
    CAPS_FILENAME,
    PRICE_SOURCE,
    Caps,
    Price,
)

#: Tolerance per run. ``RunBudget.echo`` rounds USD to 8 decimal places, so an
#: exact comparison would fail on rounding alone.
EPSILON_PER_RUN = 1e-8


class Findings:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []
        self.failed = 0

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        self.rows.append(("PASS" if ok else "FAIL", label, detail))
        if not ok:
            self.failed += 1
        return ok

    def note(self, label: str, detail: str = "") -> None:
        self.rows.append(("NOTE", label, detail))

    def render(self) -> None:
        for status, label, detail in self.rows:
            print(f"  {status}  {label}")
            if detail and status != "PASS":
                for line in str(detail).splitlines():
                    print(f"          {line}")


def recompute_usd(entry: dict, input_per_million: float,
                  output_per_million: float) -> float:
    """The documented formula, written out rather than imported."""
    usage = entry.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0))
    output_tokens = (
        int(usage.get("completion_tokens", 0))
        + int(usage.get("reasoning_tokens", 0))
    )
    return (
        prompt_tokens * input_per_million + output_tokens * output_per_million
    ) / 1_000_000


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


class Limits:
    """What bounded this collection: prices, token caps, per-call ceiling."""

    def __init__(self, input_per_million, output_per_million,
                 max_prompt_tokens, max_output_tokens, per_call_ceiling):
        self.input_per_million = input_per_million
        self.output_per_million = output_per_million
        self.max_prompt_tokens = max_prompt_tokens
        self.max_output_tokens = max_output_tokens
        self.per_call_ceiling = per_call_ceiling


def resolve_limits(root: Path, findings: Findings) -> Limits:
    """What this collection actually ran under.

    Preferred source is the collection's own ``planner-caps.json``, because
    what matters is what was in force when the calls were made and not the
    constant in the working tree today. A collection recorded before that file
    existed falls back to the module defaults, and says so.
    """
    caps_path = root / CAPS_FILENAME
    if caps_path.is_file():
        body = json.loads(caps_path.read_text(encoding="utf-8"))
        price = body.get("price") or {}
        source = body.get("price_source") or {}
        in_force = body.get("in_force") or {}
        findings.check(
            bool(source.get("url")) and bool(source.get("retrieved")),
            "C4'(b) the price in the caps record cites a source and a date",
            f"price_source={source!r}",
        )
        return Limits(
            float(price.get("input_per_million", Price().input_per_million)),
            float(price.get("output_per_million", Price().output_per_million)),
            int(in_force.get("max_prompt_tokens", Caps().max_prompt_tokens)),
            int(in_force.get("max_output_tokens", Caps().max_output_tokens)),
            float(body.get("per_call_ceiling_usd", 0.0)),
        )

    findings.note(
        f"no {CAPS_FILENAME} in this collection",
        "Recorded before amendment 5's caps record existed. Falling back to "
        "the module's documented price. The caps that were in force cannot "
        "be established from this archive -- which is the gap the caps "
        "record was added to close.",
    )
    price = Price()
    caps = Caps()
    return Limits(
        price.input_per_million,
        price.output_per_million,
        caps.max_prompt_tokens,
        caps.max_output_tokens,
        price.usd(caps.max_prompt_tokens, caps.max_output_tokens),
    )


def check_collection(root: Path) -> Findings:
    findings = Findings()

    findings.check(
        bool(PRICE_SOURCE.get("url")) and bool(PRICE_SOURCE.get("retrieved")),
        "C4'(b) PRICE_SOURCE in the repository carries a URL and a date",
        f"PRICE_SOURCE={PRICE_SOURCE!r}",
    )

    limits = resolve_limits(root, findings)
    if limits.per_call_ceiling <= 0:
        findings.check(False, "a per-call ceiling is available", "got 0")
        return findings

    run_dirs = sorted(d for d in root.iterdir() if d.is_dir())

    # ---- C4'(a) the per-call cost bound, and the token bounds under it ----
    #
    # Both, and the second is not decoration. The ceiling is 0.0004 of input
    # and 0.0012288 of output, so OUTPUT DOMINATES IT: a prompt overrun alone
    # does not breach the cost bound until about 8 144 tokens, four times the
    # cap it has already broken. Checking only the cost would let a prompt run
    # at 3 000 tokens indefinitely while section 3's model -- which is derived
    # from "<=2 000 input" -- was quietly false.
    #
    # The first draft of this checker had exactly that hole, and the
    # known-positive in tests/test_planner_cost_criterion.py is what found it.
    over_cost = []
    over_tokens = []
    entries = 0
    recomputed_total = 0.0
    for run in run_dirs:
        for entry in read_jsonl(run / "planner-transcript.jsonl"):
            entries += 1
            usd = recompute_usd(entry, limits.input_per_million,
                                limits.output_per_million)
            recomputed_total += usd
            where = (f"{run.name} step {entry.get('step_index')} "
                     f"attempt {entry.get('attempt')}")
            if usd > limits.per_call_ceiling:
                over_cost.append(
                    f"{where}: {usd:.8f} > {limits.per_call_ceiling:.8f}"
                )
            usage = entry.get("usage") or {}
            prompt_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = (
                int(usage.get("completion_tokens", 0))
                + int(usage.get("reasoning_tokens", 0))
            )
            if prompt_tokens > limits.max_prompt_tokens:
                over_tokens.append(
                    f"{where}: prompt {prompt_tokens} > "
                    f"{limits.max_prompt_tokens}"
                )
            if output_tokens > limits.max_output_tokens:
                over_tokens.append(
                    f"{where}: output {output_tokens} > "
                    f"{limits.max_output_tokens}"
                )
    findings.check(
        not over_cost,
        f"C4'(a) all {entries} call(s) at or under the per-call ceiling "
        f"{limits.per_call_ceiling:.8f} USD",
        "\n".join(over_cost),
    )
    findings.check(
        not over_tokens,
        f"C4'(a) all {entries} call(s) within section 3's token bounds "
        f"(<={limits.max_prompt_tokens} in, <={limits.max_output_tokens} out)",
        "\n".join(over_tokens)
        + ("\n\nmax_prompt_tokens is never enforced on the outbound request "
           "(amendment 5 §4.1); it only prices the reservation. A prompt over "
           "it makes section 3's ceiling arithmetic false."
           if over_tokens else ""),
    )

    # ---- C4'(b) recorded USD is reproducible from the transcripts --------
    budget_total = 0.0
    budget_runs = 0
    for run in run_dirs:
        path = run / "planner-budget.json"
        if path.is_file():
            budget_total += float(
                json.loads(path.read_text(encoding="utf-8")).get("usd", 0.0)
            )
            budget_runs += 1
    tolerance = EPSILON_PER_RUN * max(1, budget_runs) + 1e-12
    findings.check(
        abs(budget_total - recomputed_total) <= tolerance,
        "C4'(b) planner-budget.json totals match an independent "
        "recomputation from the transcripts",
        f"recorded {budget_total:.10f} vs recomputed {recomputed_total:.10f} "
        f"(tolerance {tolerance:.2e})",
    )

    journal = read_jsonl(root / "planner-cumulative.jsonl")
    journal_net = sum(float(e.get("usd", 0.0)) for e in journal)
    findings.check(
        abs(journal_net - recomputed_total) <= tolerance,
        "C4'(b) the cumulative journal's net matches the same recomputation",
        f"journal {journal_net:.10f} vs recomputed {recomputed_total:.10f} "
        f"(tolerance {tolerance:.2e})",
    )

    # ---- C4'(c) no call cost more than its reservation -------------------
    positive = [
        f"{e['key']}: settle {e.get('usd', 0.0):+.8f}"
        for e in journal
        if e.get("key", "").endswith(":settle") and float(e.get("usd", 0.0)) > 0
    ]
    settles = sum(1 for e in journal if e.get("key", "").endswith(":settle"))
    findings.check(
        not positive,
        f"C4'(c) all {settles} settle(s) at or below zero -- every call "
        f"cost no more than its reservation",
        "\n".join(positive)
        + ("\n\nA positive settle means the reservation was not an upper "
           "bound, so the cumulative counter under-counts and the USD "
           "ceiling can be crossed without the cap firing."
           if positive else ""),
    )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", type=Path, nargs="+",
                        help="collection roots to assess")
    arguments = parser.parse_args()

    failed = 0
    for root in arguments.roots:
        print("=" * 70)
        print(f"C4' -- {root}")
        print("=" * 70)
        if not root.is_dir():
            print(f"  FAIL  no such collection: {root}")
            failed += 1
            continue
        findings = check_collection(root)
        findings.render()
        print(f"  ---- {len(findings.rows) - findings.failed} ok, "
              f"{findings.failed} failed")
        failed += findings.failed
        print()

    print("C4' PASSED" if not failed else f"C4' FAILED ({failed} check(s))")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
