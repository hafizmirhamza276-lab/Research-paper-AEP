r"""Every number published in `reports/raw/phase13-armA-model-gap.md` is regenerable.

That note is the phase's central finding and is load-bearing for §VI-C2: it
establishes that the landing-latency model failed on two independent premises
rather than one miscalibration. Its figures were originally computed by one-off
probes, and a number that only one machine can reproduce is not evidence.

**These tests are deliberately written as literals transcribed from the note**,
not as assertions against a stored copy of the script's own output. A snapshot
test would pass if the analysis and the snapshot drifted together; this fails the
moment the analysis stops producing what the manuscript's source note claims. If
one of these fails, either the analysis changed or the note is wrong -- both need
a human before §VI-C2 is drafted.

The session roots (~50 MB uncontrolled, ~150 MB controlled) live on the
measurement host and CI has no access to them, and
`scripts/check_pytest_gates.py` gate 1 is *zero skipped*. So the analysis runs
from `tests/fixtures/model-gap/runs.json`, the per-run extraction the script
itself emits with `--emit-fixture`. The bench numbers are read from the
committed `reports/raw/phase13-fault-landing.json` rather than the fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analyse_model_gap import analyse

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "model-gap" / "runs.json"
NOTE = REPO_ROOT / "reports" / "raw" / "phase13-armA-model-gap.md"


@pytest.fixture(scope="module")
def report() -> dict:
    return analyse(json.loads(FIXTURE.read_text(encoding="utf-8")))


# ===========================================================================
# The note exists, and says it is not adjusting the model
# ===========================================================================


def test_the_note_is_present_and_declares_no_model_adjustment():
    text = NOTE.read_text(encoding="utf-8")

    assert "does not adjust the model" in text
    assert "It does not write §VI-C2." in text


# ===========================================================================
# §1 and §5 -- the headline rates
# ===========================================================================


def test_uncontrolled_dispatch_and_applied(report):
    side = report["uncontrolled"]

    assert side["aep_full_runs"] == 240
    assert side["acked"] == 143
    assert side["ack_rate"] == 0.5958
    assert (side["applied"], side["executions"]) == (131, 240)
    assert side["applied_rate"] == 0.5458


def test_controlled_dispatch_and_applied(report):
    side = report["controlled"]

    assert side["aep_full_runs"] == 269
    assert side["acked"] == 4
    assert side["ack_rate"] == 0.0149
    assert (side["applied"], side["executions"]) == (3, 269)
    assert side["applied_rate"] == 0.0112
    assert side["transmitted"] == 4


def test_applied_by_class_and_ack_by_endpoint(report):
    """Ack is flat across classes; applied is not. §5 of the note."""
    applied = report["uncontrolled"]["applied_by_class"]
    endpoints = report["uncontrolled"]["ack_by_endpoint"]

    assert applied["AUTHORITATIVE_READBACK"] == {"applied": 73, "executions": 120, "rate": 0.6083}
    assert applied["NO_READBACK"] == {"applied": 58, "executions": 120, "rate": 0.4833}
    assert endpoints["ledger_postings"]["ack_rate"] == 0.575
    assert endpoints["payments"]["ack_rate"] == 0.6167


# ===========================================================================
# §2 -- premise (b): the wait is not uniform
# ===========================================================================


def test_the_wait_distribution(report):
    assert report["uncontrolled"]["wait_ms"] == {
        "n": 143, "min": 29.3, "p25": 362.4, "median": 483.6, "p75": 622.8, "max": 1111.8
    }


def test_the_no_barrier_baseline(report):
    """B3 reaches the same checkpoint without a barrier: ~5 ms, not ~480 ms."""
    assert report["uncontrolled"]["b3_no_barrier_wait_ms"] == {
        "n": 240, "min": 2.1, "p25": 3.7, "median": 4.6, "p75": 5.3, "max": 16.4
    }


def test_the_wait_histogram(report):
    """Unimodal around 300-500 ms. Uniform would be flat."""
    assert report["uncontrolled"]["wait_histogram"] == {
        "0": 1, "100": 3, "200": 15, "300": 29, "400": 27, "500": 25,
        "600": 17, "700": 14, "800": 3, "900": 5, "1000": 3, "1100": 1,
    }


@pytest.mark.parametrize(
    ("x", "empirical", "uniform", "overstates"),
    [
        ("25", 0.0000, 0.0250, None),
        ("29", 0.0000, 0.0290, None),
        ("58", 0.0042, 0.0580, 13.9),
        ("100", 0.0042, 0.1000, 24.0),
        ("200", 0.0167, 0.2000, 12.0),
        ("368", 0.1542, 0.3680, 2.4),
    ],
)
def test_empirical_cdf_against_uniform(report, x, empirical, uniform, overstates):
    """The error grows as the window narrows -- the whole reason Arm A missed."""
    entry = report["uncontrolled"]["empirical_cdf"][x]

    assert entry["empirical"] == empirical
    assert entry["uniform"] == uniform
    assert entry["uniform_overstates_by"] == overstates


def test_the_cdf_is_reported_only_where_uncensored(report):
    side = report["uncontrolled"]

    assert side["uncensored_below_ms"] == 492.8
    assert all(int(x) <= 492.8 for x in side["empirical_cdf"])


# ===========================================================================
# §3 -- premise (a): the window is not the bench landing
# ===========================================================================


def test_acks_prove_redis_lived_past_the_bench_landing(report):
    """The model-free evidence: a WAITAOF ack requires a live server."""
    side = report["uncontrolled"]

    assert side["acks_after_bench_landing"] == 106
    assert side["acks_after_bench_landing_rate"] == 0.4417


@pytest.mark.parametrize(
    ("session", "n", "acked", "ack_rate", "after", "after_rate", "max_wait"),
    [
        ("b2-paired-v2-s1-2026-08-28", 60, 40, 0.667, 24, 0.4, 1111.8),
        ("b2-paired-v2-s2-2026-08-28", 60, 36, 0.6, 30, 0.5, 1086.6),
        ("b2-paired-v2-s3-2026-08-28", 60, 29, 0.483, 23, 0.383, 969.8),
        ("b2-paired-v2-s4-2026-08-28", 60, 38, 0.633, 29, 0.483, 726.7),
    ],
)
def test_per_session_table(report, session, n, acked, ack_rate, after, after_rate, max_wait):
    entry = report["uncontrolled"]["per_session"][session]

    assert entry["n"] == n
    assert entry["acked"] == acked
    assert entry["ack_rate"] == ack_rate
    assert entry["after_bench_landing"] == after
    assert entry["after_bench_landing_rate"] == after_rate
    assert entry["max_wait_ms"] == max_wait


def test_the_bench_kill_measurement_did_not_transport(report):
    bench = report["bench"]["docker-kill"]
    in_situ = report["uncontrolled"]["in_situ_kill_latency_ms"]

    assert (bench["command_ms_median"], bench["command_ms_min"], bench["command_ms_max"]) == (
        368.3, 294.1, 428.6
    )
    assert bench["landing_ms_median"] == 368.4
    assert in_situ == {
        "n": 480, "min": 731.7, "p25": 932.8, "median": 1038.5, "p75": 1177.6, "max": 8229.4
    }
    # The ranges do not overlap -- the sharpest form of the claim.
    assert bench["command_ms_max"] < in_situ["min"]
    assert report["ratios"]["bench_ranges_disjoint"] is True
    assert report["ratios"]["in_situ_kill_over_bench"] == 2.82


def test_the_bench_pause_measurement_did_transport(report):
    """Error (a) vanishes in Arm A, which is what leaves error (b) exposed."""
    bench = report["bench"]["docker-pause"]

    assert bench["command_ms_median"] == 37.9
    assert bench["landing_ms_median"] == 58.3
    assert report["bench"]["landing_measurement_floor_ms"] == 20.0
    assert report["controlled"]["in_situ_pause_ms"] == {
        "n": 539, "min": 21, "p25": 34, "median": 36, "p75": 46, "max": 242
    }
    assert report["controlled"]["abort_ms_non_acking"] == {
        "n": 265, "min": 42.7, "p25": 54.7, "median": 58.2, "p75": 78.3, "max": 201.6
    }


def test_uncontrolled_runs_abort_before_the_kill_call_returns(report):
    """§6: what closes the window there is not settled by these events."""
    assert report["uncontrolled"]["abort_ms_non_acking"] == {
        "n": 97, "min": 492.8, "p25": 586.3, "median": 668.1, "p75": 738.8, "max": 963.7
    }


# ===========================================================================
# §4 and §6 -- the sign flip, and the gap the note leaves open
# ===========================================================================


def test_the_ratios_the_note_quotes(report):
    ratios = report["ratios"]

    assert ratios["window_narrowed_by"] == 6.3
    assert ratios["uniform_overstates_at_58ms"] == 13.9
    assert ratios["uniform_overstates_at_368ms"] == 2.4
    assert ratios["model_vs_uncontrolled_dispatch"] == 1.62
    assert ratios["model_vs_no_readback_dispatch"] == 1.56
    assert ratios["dispatch_not_applied_loss_no_readback"] == 0.16
    assert ratios["model_over_dispatch_controlled"] == 3.9
    assert ratios["model_over_applied_controlled"] == 5.2


def test_the_controlled_acks_are_faster_than_the_uncontrolled_minimum():
    """§4's unreconciled gap, pinned so it cannot be quietly dropped.

    Three of Arm A's four acks are below the fastest of all 143 uncontrolled
    acks. The note declines to explain this; it must not stop being true
    without someone noticing.
    """
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    controlled = sorted(
        r["wait_ms"] for r in fixture["controlled"]["runs"]
        if r["system"] == "AEP_FULL" and r["wait_ms"] is not None
    )
    uncontrolled_min = min(
        r["wait_ms"] for r in fixture["uncontrolled"]["runs"]
        if r["system"] == "AEP_FULL" and r["wait_ms"] is not None
    )

    assert controlled == [3.5505, 4.5136, 7.4865, 102.7458]
    assert round(uncontrolled_min, 1) == 29.3
    assert sum(1 for w in controlled if w < 7.5) == 3
    assert sum(1 for w in controlled if w < uncontrolled_min) == 3


def test_the_model_constants_are_the_pre_registered_ones(report):
    """Not fitted. If these move, the note is comparing against something else."""
    assert report["model"] == {"uncontrolled": 0.368, "controlled": 0.058}


def test_the_fixture_covers_both_arms_completely():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert len(fixture["uncontrolled"]["runs"]) == 480
    assert len(fixture["controlled"]["runs"]) == 539
    assert len(fixture["uncontrolled"]["kill_latency_ms"]) == 480
    assert fixture["controlled"]["kill_latency_ms"] == []
