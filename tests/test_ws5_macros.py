"""The WS-5 generator path, and the property that makes the gate worth anything.

``docs/26`` §3 rule 14: a load-bearing script is committed with a test. Both
scripts changed in phase 25 are load-bearing --- one produces every number in
the manuscript, the other is what proves the manuscript still matches it.

``docs/25`` R17 governs how these are written. **Nothing here executes an older
version of either script.** The refusal-shaped assertions read source text; the
behavioural ones run the *current* generator into a ``tmp_path``, which writes
nowhere else. R17 exists because three passes in one week damaged real data
while demonstrating that old code was unsafe.
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "paper_tables.py"
GATE = ROOT / "scripts" / "check_paper_numbers.py"
RESULTS = ROOT / "experiments" / "results"
WS5 = RESULTS / "ws5-2026-09-10"

WS5_FLAGS = ("--ws5-everysec", "--ws5-p30", "--ws5-keying", "--fsync-always-45")


# --------------------------------------------------------------------- 1
# R16: no input may default to a results root.
# --------------------------------------------------------------------- 1

def test_the_four_ws5_inputs_have_no_results_root_default():
    """Source assertion, deliberately (R17).

    ``run_matrix.py`` defaulted to the frozen 432-run root and wrote into it
    twice before anyone noticed. These four are new inputs of the same kind.
    """
    source = GENERATOR.read_text(encoding="utf-8")
    for flag in WS5_FLAGS:
        block = re.search(
            r'parser\.add_argument\(\s*"' + re.escape(flag) + r'"(.*?)\)\n',
            source, re.S)
        assert block, f"{flag} is not declared in {GENERATOR.name}"
        body = block.group(1)
        assert "default=None" in body, f"{flag} must default to None"
        assert "experiments/results" not in body, (
            f"{flag} must not default to a results root"
        )


# --------------------------------------------------------------------- 2
# The property the gate exists for: it regenerates with the same inputs.
# --------------------------------------------------------------------- 2

def test_the_gate_passes_every_ws5_input_to_the_generator():
    """If the gate regenerates with different inputs than the documented
    invocation, it certifies a numbers.tex nobody can reproduce."""
    gate = GATE.read_text(encoding="utf-8")
    for flag in WS5_FLAGS:
        assert f'"{flag}"' in gate, (
            f"{flag} is not passed to paper_tables.py by the gate"
        )
    for name in ("ws5_everysec", "ws5_p30", "ws5_keying", "fsync_always_45"):
        assert f"arguments.{name}" in gate, f"{name} never reaches the check"


def test_the_gate_treats_a_missing_ws5_input_as_a_failure():
    """Absence must fail, not silently check less than yesterday."""
    gate = GATE.read_text(encoding="utf-8")
    for label in ("WS-5 everysec 15-run cell", "WS-5 30%-crash regime",
                  "WS-5 read-back keying variant",
                  "appendfsync=always 45-run arm"):
        assert label in gate, f"no presence check for {label}"


# --------------------------------------------------------------------- 3
# The pending list must be able to fail in both directions.
# --------------------------------------------------------------------- 3

def test_pending_macros_fails_on_a_stale_entry_and_on_a_landed_one():
    gate = GATE.read_text(encoding="utf-8")
    assert "every pending macro still exists" in gate
    assert "no pending macro is already in use" in gate


def test_every_pending_macro_actually_exists():
    """The stale-entry direction, checked here too so the list cannot rot
    between full gate runs."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_paper_numbers

    numbers = (ROOT / "paper" / "generated" / "numbers.tex").read_text(
        encoding="utf-8")
    defined = set(re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", numbers))
    missing = sorted(n for n in check_paper_numbers.PENDING_MACROS
                     if n not in defined)
    assert not missing, f"PENDING_MACROS names macros that do not exist: {missing}"


# --------------------------------------------------------------------- 4
# The macros equal their CSV cells. Run the CURRENT generator into tmp_path.
# --------------------------------------------------------------------- 4

@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    out = tmp_path_factory.mktemp("generated")
    completed = subprocess.run(
        [sys.executable, str(GENERATOR),
         "--analysis", str(RESULTS / "matrix" / "analysis"),
         "--fsync-analysis", str(RESULTS / "fsync-always" / "analysis"),
         "--flakey", str(RESULTS),
         "--b5-session", str(ROOT / "reports" / "raw"
                             / "ws6-b5-s1-2026-09-08-attempt3"),
         "--writeloss-cell", str(ROOT / "reports" / "raw"
                                 / "ws4-writeloss-s1-2026-09-07"),
         "--ws5-everysec", str(WS5 / "t1-p0-everysec" / "analysis"),
         "--ws5-p30", str(WS5 / "t2-p30" / "analysis"),
         "--ws5-keying", str(WS5 / "t2-keying" / "analysis"),
         "--fsync-always-45", str(RESULTS / "fsync-always-2026-09-14"
                                  / "analysis"),
         "--out", str(out)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert completed.returncode == 0, completed.stderr
    text = (out / "numbers.tex").read_text(encoding="utf-8")
    return dict(re.findall(r"\\newcommand\{\\([A-Za-z]+)\}\{([^}]*)\}", text))


def _number(raw: str) -> float:
    return float(raw.replace("\\,", "").replace(",", ""))


def test_the_always_barrier_cost_is_the_difference_of_two_csv_medians(generated):
    """The headline of the 45-run arm, checked against the CSV it came from.

    It is NEGATIVE, and that is the pre-registered expectation for this arm,
    not a defect: under ``always`` there is no fsync boundary to wait for.
    """
    rows = list(csv.DictReader(
        (RESULTS / "fsync-always-2026-09-14" / "analysis"
         / "latency-and-throughput.csv").open(encoding="utf-8")))
    medians = {r["system"]: float(r["step_latency_ms_median"]) for r in rows}
    expected = medians["AEP_FULL"] - medians["B3_INTENT_NO_BARRIER"]

    assert _number(generated["BarrierCostAlwaysFortyFive"]) == pytest.approx(
        expected, abs=0.05)
    assert expected < 0


def test_h4s_keying_delta_is_the_two_pooled_rates(generated):
    """H4 was pre-registered as a sensitivity check predicted null."""
    def pooled(path, response_class):
        s = n = 0
        for row in csv.DictReader(path.open(encoding="utf-8")):
            if (row["metric"] == "known_ambiguity_rate"
                    and row["system"] == "AEP_FULL"
                    and row["response_class"] == response_class):
                s += int(row["successes"])
                n += int(row["total"])
        return s / n * 100.0

    oracle = pooled(WS5 / "t2-keying" / "analysis" / "per-cell-metrics.csv",
                    "POSITIVE_ONLY_READBACK")
    caller = pooled(RESULTS / "matrix" / "analysis" / "per-cell-metrics.csv",
                    "POSITIVE_ONLY_READBACK")

    assert _number(generated["KeyingAmbiguityOracle"]) == pytest.approx(oracle, abs=0.01)
    assert _number(generated["KeyingAmbiguityCaller"]) == pytest.approx(caller, abs=0.01)
    assert _number(generated["KeyingAmbiguityDelta"]) == pytest.approx(
        oracle - caller, abs=0.01)
    assert abs(oracle - caller) > 5.0, "H4's whole point is that it exceeds the margin"


def test_both_readings_of_protocol_minus_barrier_are_emitted(generated):
    """Amendment 2: both are reported, neither is chosen silently.

    They disagree, and it would be trivial to quote whichever flatters the
    claim. Emitting only one is the failure this asserts against.
    """
    for name in ("ProtocolMinusBarrierFifteen", "ProtocolMinusBarrierLowerMode"):
        for suffix in ("", "Low", "High"):
            assert name + suffix in generated, f"{name}{suffix} missing"

    for name in ("ProtocolMinusBarrierFifteen", "ProtocolMinusBarrierLowerMode"):
        low = _number(generated[name + "Low"])
        high = _number(generated[name + "High"])
        assert low <= 0.0 <= high, (
            f"{name}'s interval no longer spans zero; the manuscript claim "
            "that the decomposition is not separable at this precision "
            "depends on it"
        )


def test_the_fifteen_run_macros_are_distinguishable_from_the_three_run_ones(generated):
    """Both exist on purpose; section VIII argues from the three-run figures.

    So the names must say which is which at the point of use.
    """
    assert "BarrierCost" in generated and "BarrierCostFifteen" in generated
    assert _number(generated["BarrierCost"]) != _number(
        generated["BarrierCostFifteen"])
    assert "BarrierCostAlways" in generated
    assert "BarrierCostAlwaysFortyFive" in generated


def test_no_ws5_input_means_no_ws5_macro(tmp_path):
    """An absent input emits nothing, never a zero.

    A zero is indistinguishable from a measurement; an absent macro makes
    LaTeX fail loudly at the point of use.
    """
    out = tmp_path / "out"
    completed = subprocess.run(
        [sys.executable, str(GENERATOR),
         "--analysis", str(RESULTS / "matrix" / "analysis"),
         "--out", str(out)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert completed.returncode == 0, completed.stderr
    text = (out / "numbers.tex").read_text(encoding="utf-8")
    for name in ("BarrierCostFifteen", "BarrierCostAlwaysFortyFive",
                 "KeyingAmbiguityDelta"):
        assert name not in text, f"{name} was emitted without its input"
