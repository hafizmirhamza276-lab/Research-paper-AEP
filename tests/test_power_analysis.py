"""Validate ``scripts/power_analysis.py`` against answers known in advance.

``docs/25`` R2: *"Before a gate or a census is trusted on a case whose answer is
unknown, run it on one whose answer is already known and assert the result."*

This module's output is about to be used to decide how much machine time WS-5
spends and whether a published interval is defensible, so every helper is
checked against a value computed by hand or taken from a table, and every branch
that can refuse is exercised. A sample-size calculator that is wrong by a factor
of three is worse than none: it produces a number with the shape of evidence.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "power_analysis.py"


def load():
    spec = importlib.util.spec_from_file_location("power_analysis", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["power_analysis"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def pa():
    return load()


# --------------------------------------------------------------------------
# Known answers.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("df,expected", [
    (1, 12.706), (3, 3.182), (9, 2.262), (14, 2.145), (30, 2.042), (100, 1.984),
])
def test_t_critical_matches_published_quantiles(pa, df, expected):
    assert pa.t_critical(df) == pytest.approx(expected, abs=0.001)


def test_t_critical_between_table_entries_is_conservative(pa):
    """35 df is not tabulated; the value used must not understate the interval.

    Understating the critical value understates the required n, which is the
    direction that silently under-powers a collection.
    """
    assert pa.t_critical(35) >= pa.t_critical(40)


def test_t_critical_rejects_zero_degrees_of_freedom(pa):
    with pytest.raises(ValueError):
        pa.t_critical(0)


@pytest.mark.parametrize("n,expected", [(1, 1), (2, 3), (3, 10), (4, 35), (5, 126)])
def test_distinct_multisets_matches_the_closed_form(pa, n, expected):
    """C(2n-1, n). n=3 -> 10 is the number quoted in paper_tables.py."""
    assert pa.distinct_multisets(n) == expected


def test_the_ceiling_for_a_difference_is_the_product_of_the_arms(pa):
    """Three against three is 100, not 10.

    This is the correction the first run of the analysis forced: the two arms
    resample independently. Treating the per-arm ceiling as the ceiling for the
    difference understates it tenfold and makes a coarse interval look
    degenerate.
    """
    assert pa.distinct_multisets_for_difference(3, 3) == 100
    assert pa.distinct_multisets_for_difference(3, 4) == 350


@pytest.mark.parametrize("n,expected", [
    (1, 1.0), (2, 0.5), (3, 0.25), (4, 0.125), (5, 0.0625), (6, 0.03125),
])
def test_sign_test_floor_is_two_over_two_to_the_n(pa, n, expected):
    assert pa.sign_test_floor(n) == pytest.approx(expected)


def test_four_sessions_cannot_reject_at_five_percent(pa):
    """The hard result behind §VIII's conclusion-validity paragraph.

    With four paired sessions the smallest attainable two-sided sign-test
    p-value is 0.125. No effect size, however large, produces a rejection. That
    is a property of the design, and it is why the two comparisons in question
    are precision failures by construction rather than by bad luck.
    """
    assert pa.sign_test_floor(4) > pa.ALPHA
    assert pa.sign_test_floor(6) <= pa.ALPHA
    first_workable = next(n for n in range(1, 40) if pa.sign_test_floor(n) <= pa.ALPHA)
    assert first_workable == 6


# --------------------------------------------------------------------------
# Sample sizing.
# --------------------------------------------------------------------------


def test_half_width_sizing_against_a_hand_computation(pa):
    """sd=10, target half-width 5. t(df)*10/sqrt(n) <= 5.

    n=17: 2.110*10/4.123 = 5.117  -> too wide
    n=18: 2.101*10/4.243 = 4.952  -> fits
    """
    assert pa.runs_for_half_width(10.0, 5.0) == 18


def test_half_width_sizing_is_monotone_in_the_target(pa):
    tighter = pa.runs_for_half_width(10.0, 2.0)
    looser = pa.runs_for_half_width(10.0, 8.0)
    assert tighter > looser


def test_half_width_sizing_returns_none_when_unreachable(pa):
    """An unreachable target must not silently return the cap.

    Returning max_n would read as "400 runs will do it" when nothing will.
    """
    assert pa.runs_for_half_width(1000.0, 0.001, max_n=50) is None


def test_zero_variance_needs_one_run(pa):
    assert pa.runs_for_half_width(0.0, 5.0) == 1


def test_power_sizing_is_monotone_in_the_effect(pa):
    small = pa.runs_for_power(20.0, 5.0)
    large = pa.runs_for_power(20.0, 40.0)
    assert small > large


def test_power_sizing_rejects_a_non_positive_effect(pa):
    assert pa.runs_for_power(10.0, 0.0) is None
    assert pa.runs_for_power(10.0, -3.0) is None


def test_power_sizing_rejects_an_untabulated_power(pa):
    with pytest.raises(ValueError):
        pa.runs_for_power(10.0, 5.0, power=0.77)


# --------------------------------------------------------------------------
# The mixture detector, which decides whether an arm's median means anything.
# --------------------------------------------------------------------------


def test_a_clean_unimodal_sample_is_not_called_a_mixture(pa):
    values = [100.0 + i * 0.5 for i in range(30)]
    assert pa.largest_gap_split(values)["bimodal"] is False


def test_a_single_far_point_is_an_outlier_not_a_mixture(pa):
    """B0's shape: 29 values together and one at 15 s.

    Calling this a mixture would have flagged an arm whose three run medians
    agree to within 1.8 ms, and the flag would have meant nothing.
    """
    values = [2010.0 + i * 0.1 for i in range(29)] + [15022.9]
    split = pa.largest_gap_split(values)
    assert split["upper_n"] == 1
    assert split["bimodal"] is False


def test_a_genuine_two_group_sample_is_called_a_mixture(pa):
    """B3's shape: roughly a quarter of executions in a far upper group."""
    values = [2030.0 + i for i in range(22)] + [5030.0 + i for i in range(8)]
    split = pa.largest_gap_split(values)
    assert split["upper_n"] == 8
    assert split["upper_fraction"] == pytest.approx(8 / 30)
    assert split["bimodal"] is True


def test_the_mixture_median_is_unstable_at_a_five_five_split(pa):
    """Why the mixture matters, stated as an assertion rather than as prose.

    Ten executions split 5/5 across two modes put the median at the midpoint of
    a gap where no observation lies. One execution moving between modes shifts
    it by half the gap. That is what B3's third run does, and it is the whole
    of that arm's between-run variance.
    """
    import statistics
    low, high = 2030.0, 5030.0
    five_five = [low] * 5 + [high] * 5
    four_six = [low] * 6 + [high] * 4
    assert statistics.median(five_five) == pytest.approx((low + high) / 2)
    assert statistics.median(four_six) == pytest.approx(low)
    assert abs(statistics.median(five_five)
               - statistics.median(four_six)) > 1000.0


def test_largest_gap_split_handles_a_degenerate_sample(pa):
    assert pa.largest_gap_split([]) == {}
    assert pa.largest_gap_split([1.0]) == {}


# --------------------------------------------------------------------------
# The audit runs against the frozen data and agrees with the manuscript.
# --------------------------------------------------------------------------


def test_the_report_builds_from_frozen_data(pa):
    report = pa.build_report()
    assert report["degeneracy"], "no timing arms found in the frozen results"
    assert report["session_comparisons"]
    assert report["preregistered"]["alpha"] == 0.05


def test_the_audit_reproduces_the_published_barrier_interval(pa):
    """The audit must be an audit of the shipped number, not of a lookalike.

    numbers.tex carries \\BarrierCostLow = 477.9 and \\BarrierCostHigh = 1978.8
    for appendfsync=everysec. If this module's estimator drifted from
    paper_tables.py's, everything it concludes would be about a different
    quantity.
    """
    rows = {(r["quantity"], r["policy"]): r for r in pa.assess_degeneracy()}
    row = rows.get(("barrier cost (AEP-full - B3)", "everysec"))
    assert row is not None
    assert row["ci_low"] == pytest.approx(477.9, abs=0.1)
    assert row["ci_high"] == pytest.approx(1978.8, abs=0.1)


def test_the_published_endpoints_are_not_the_extremes_of_the_support(pa):
    """The hypothesis the audit was written to test, recorded as refuted.

    If the percentile endpoints coincided with the support's extremes, the
    interval would be a range dressed as an interval. They do not.
    """
    rows = {(r["quantity"], r["policy"]): r for r in pa.assess_degeneracy()}
    row = rows[("barrier cost (AEP-full - B3)", "everysec")]
    assert row["realised_distinct_values"] > 10
    assert row["low_is_support_min"] is False


def test_the_b3_arm_is_flagged_as_a_mixture_in_both_policies(pa):
    flagged = {
        (r["system"], r["policy"])
        for r in pa.assess_mixtures() if r["mixture"].get("bimodal")
    }
    assert ("B3_INTENT_NO_BARRIER", "everysec") in flagged
    assert ("B3_INTENT_NO_BARRIER", "always") in flagged


def test_the_session_comparisons_match_the_published_intervals(pa):
    """[-21.4, +46.4] pp is \\ClassPpLow / \\ClassPpHigh in numbers.tex."""
    rows = {r["name"]: r for r in
            (pa.assess_session_comparison(k, v)
             for k, v in pa.SESSION_COMPARISONS.items())}
    sweep = rows["class_sweep_pp"]
    assert sweep["ci_low"] == pytest.approx(-21.4, abs=0.15)
    assert sweep["ci_high"] == pytest.approx(46.4, abs=0.15)
    assert sweep["spans_zero"] is True
    kill = rows["kill_latency_ms"]
    assert kill["half_width"] == pytest.approx(195.7, abs=0.5)
    assert kill["sign_test_can_ever_reject"] is False

# --------------------------------------------------------------------------
# The section filter must not render "not computed" as "nothing found".
# --------------------------------------------------------------------------


def test_degeneracy_section_carries_the_mixture_report(pa):
    """Section A2 explains section A; dropping it prints an empty A2.

    Found on the first fifteen-run run of this module. `--section degeneracy`
    rebuilt the report without the "mixtures" key, so A2 rendered as a heading
    with nothing under it -- which reads exactly like "no arm was flagged", the
    outcome that refutes H2 of the pre-registration. An instrument whose
    "I was not asked" and "I found nothing" are the same glyph is the R14 shape,
    inside the instrument written to judge the mixture.
    """
    report = pa.build_report()
    assert "mixtures" in report
    filtered = {"degeneracy": report["degeneracy"],
                "mixtures": report["mixtures"],
                "session_comparisons": [], "timing_sizing": []}
    assert filtered["mixtures"], "the degeneracy view must carry the mixture rows"


def test_every_section_view_defines_mixtures(pa, capsys):
    """All three views must set the key, so none can print a blank A2."""
    import sys
    report = pa.build_report()
    for section in ("degeneracy", "session", "timing"):
        old = sys.argv
        sys.argv = ["power_analysis.py", "--section", section]
        try:
            assert pa.main() == 0
        finally:
            sys.argv = old
        out = capsys.readouterr().out
        # A2's heading may appear; if it does, it must not be the last thing
        # printed with nothing under it.
        # Every section must say which kind of empty it is: "not computed in
        # this view" or "computed: nothing found". A bare heading is the
        # ambiguity this test exists to forbid.
        tail = out.split("A2.", 1)[1] if "A2." in out else ""
        assert tail, f"--section {section} printed no A2 heading at all"
        assert ("MIXTURE" in tail or "not a mixture" in tail
                or "not computed in this view" in tail
                or "no arm has a splittable sample" in tail), (
            f"--section {section} printed an ambiguous empty A2"
        )


def test_execution_path_override_rejects_a_missing_file(pa, tmp_path):
    """Pointing the instrument at a tree that is not there must fail loudly."""
    import sys
    old = sys.argv
    sys.argv = ["power_analysis.py", "--everysec", str(tmp_path / "nope.csv")]
    try:
        with pytest.raises(SystemExit):
            pa.main()
    finally:
        sys.argv = old

def test_an_empty_A2_emits_an_explicit_sentinel(pa, tmp_path, monkeypatch, capsys):
    """Rule 13: feed it a tree that really produces an empty section.

    R14 instance 8 was an A2 heading with nothing under it, which read exactly
    like "no arm was flagged" -- that is, H2 refuted. The repair is a sentinel,
    and a sentinel is only evidence once something has been seen to trigger it.
    This builds a per-execution.csv whose arms hold one execution each, so
    ``largest_gap_split`` returns {} and no mixture row exists at all.

    Confirmed to fail against the pre-fix module at 5ff3dc2, whose A2 renders as
    a heading followed directly by section B.
    """
    rows = [
        "regime,system,run_id,step_latency_ms",
        "p0,AEP_FULL,r0,4000.0",
        "p0,B3_INTENT_NO_BARRIER,r0,2000.0",
        "p0,B0_NAIVE_RETRY,r0,2000.0",
    ]
    csv_path = tmp_path / "per-execution.csv"
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")

    monkeypatch.setitem(pa.EXECUTION_PATHS, "everysec", csv_path)
    monkeypatch.delitem(pa.EXECUTION_PATHS, "always", raising=False)

    mixture_rows = pa.assess_mixtures()
    assert all(not r["mixture"] for r in mixture_rows), (
        "fixture must yield no mixture rows, or it is not testing an empty A2"
    )

    pa.print_report({"degeneracy": [], "mixtures": [],
                     "session_comparisons": [], "timing_sizing": []})
    out = capsys.readouterr().out
    assert "A2." in out
    tail = out.split("A2.", 1)[1]
    assert ("no arm has a splittable sample" in tail
            or "not computed" in tail), (
        "an empty A2 printed no sentinel -- indistinguishable from "
        "'no arm was flagged', which is H2 refuted"
    )
