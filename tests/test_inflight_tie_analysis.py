r"""Phase 13 Step 4's verdict is regenerable, and says what the write-up says.

`reports/raw/phase13-inflight-verdict.md` reports a TIE in all four
class-sessions. Three of its claims are load-bearing in a way the counts alone
are not, and each is pinned here:

1. **session 2 is a deterministic replay** -- all 120 seeds shared and every
   per-run outcome tuple identical, so the effective run count is 120, not 240;
2. **the absence of between-session variation is evidence**, because Arm A ran
   on the same shared-seed design and varied anyway;
3. **B3 NO_READBACK sits exactly on the 27 threshold**, which the analysis marks
   `AT THRESHOLD` rather than `OK` so it cannot be reported as headroom.

As with the other analyses in this repo, the assertions are literals transcribed
from the write-up rather than a snapshot of the script's own output: a snapshot
passes when the analysis and the snapshot drift together.

The session roots live on the measurement host and CI has no access to them, and
`scripts/check_pytest_gates.py` gate 1 is *zero skipped*, so the analysis runs
from `tests/fixtures/inflight/runs.json` -- the extraction the script itself
emits with `--emit-fixture`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analyse_inflight_tie import analyse

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "inflight" / "runs.json"
PRE_REGISTRATION = (
    REPO_ROOT / "reports" / "phase-report-13-prediction-inflight-2026-09-04.md"
)
VERDICT_NOTE = REPO_ROOT / "reports" / "raw" / "phase13-inflight-verdict.md"

SESSIONS = ("inflight-s1-2026-09-04", "inflight-s2-2026-09-04")


@pytest.fixture(scope="module")
def report() -> dict:
    return analyse(json.loads(FIXTURE.read_text(encoding="utf-8")))


# ===========================================================================
# The criterion is the pre-registered one, not one chosen after the data
# ===========================================================================


def test_the_criterion_matches_the_pre_registration(report):
    assert report["pre_registered"] == {
        "tie_at_or_below": 2,
        "not_a_tie_at_or_above": 6,
        "ceiling": 27,
        "mechanism": "kill",
        "kill_point": "mid_dispatch",
        "delay_ms": 200,
    }


def test_the_pre_registration_is_committed_and_says_what_it_fixed():
    text = PRE_REGISTRATION.read_text(encoding="utf-8")

    assert "<= 2" in text or "≤ 2" in text
    assert "mid_dispatch" in text
    assert "does not use the landing-latency model" in text


# ===========================================================================
# The verdict
# ===========================================================================


@pytest.mark.parametrize("session", SESSIONS)
@pytest.mark.parametrize(
    ("klass", "aep", "b3"),
    [("AUTHORITATIVE_READBACK", 29, 30), ("NO_READBACK", 28, 27)],
)
def test_tie_in_every_class_session(report, session, klass, aep, b3):
    entry = report["tie"][session][klass]

    assert (entry["AEP_FULL"], entry["B3_INTENT_NO_BARRIER"]) == (aep, b3)
    assert entry["difference"] == 1
    assert entry["verdict"] == "TIE"


def test_all_four_class_sessions_tie(report):
    assert report["verdicts"] == {"TIE": 4}


def test_nothing_larger_than_the_tie_occurred(report):
    """lost effects or undetected duplicates would outrank the tie entirely."""
    assert report["larger_than_the_tie"] == {}


def test_no_mechanism_failure_signature(report):
    assert report["mechanism_failures"] == []


@pytest.mark.parametrize("session", SESSIONS)
def test_the_injector_delivered_the_pre_registered_fault(report, session):
    checks = report["sessions"][session]["mechanism"]

    assert checks["runs"] == 120
    assert checks["mechanisms"] == {"kill": 120}
    assert checks["kill_points"] == {"mid_dispatch": 120}
    assert checks["delays"] == {"200": 120}
    assert checks["runs_with_no_kill_event"] == 0


@pytest.mark.parametrize("session", SESSIONS)
def test_clock_gate_and_no_dropped_runs(report, session):
    entry = report["sessions"][session]

    assert entry["coverage"]["runs"] == 120
    assert entry["coverage"]["runs_dropped_for_clock_suspension"] == 0
    assert entry["coverage"]["worst_suspension_seconds"] == 0.195
    assert entry["coverage"]["all_runs_used_real_sigkill"] is True
    assert entry["statuses"] == {"collected": 120}


@pytest.mark.parametrize("session", SESSIONS)
def test_interleaving_is_run_level(report, session):
    """Reported from the collected runs, not assumed -- B9 exists because of that."""
    weave = report["sessions"][session]["interleaving"]

    assert weave["longest_same_arm_streak"] == 2
    assert weave["mean_position"] == {"A": 58.5, "B": 60.5}
    assert weave["midpoint"] == 60.0
    assert (weave["adjacent_same_arm_pairs"], weave["adjacent_pairs"]) == (60, 119)


# ===========================================================================
# Claim 1 -- session 2 is a replay, so the effective n is 120
# ===========================================================================


def test_session_two_is_a_deterministic_replay(report):
    replay = report["replay"]

    assert replay["seeds_shared"] == 120
    assert replay["distinct_seeds_per_session"] == [120, 120]
    assert replay["same_seed"] == 120
    assert replay["same_outcome"] == 120
    assert replay["runs_compared"] == 120
    assert replay["is_deterministic_replay"] is True


def test_the_effective_run_count_is_half_the_nominal(report):
    """The write-up must not claim 240 runs of evidence for the counts."""
    replay = report["replay"]

    assert (replay["effective_runs"], replay["nominal_runs"]) == (120, 240)


# ===========================================================================
# Claim 2 -- Arm A shares seeds too, and varied anyway
# ===========================================================================


def test_arm_a_shares_a_seed_set_with_itself(report):
    """So the shared-seed design is the harness's, not something this run did."""
    compare = report["comparison"]

    assert compare["shares_a_seed_set"] is True
    assert compare["seeds_shared_by_all"] == 180
    assert compare["distinct_seeds_per_session"] == [180, 180, 180]


def test_arm_a_varied_despite_sharing_seeds(report):
    """Which is what makes the in-flight cell's zero variation informative."""
    applied = report["comparison"]["aep_full_applied"]

    assert applied["NO_READBACK"]["per_session"] == [1, 0, 1]
    assert applied["NO_READBACK"]["varied"] is True
    assert applied["POSITIVE_ONLY_READBACK"]["per_session"] == [0, 0, 1]
    assert applied["POSITIVE_ONLY_READBACK"]["varied"] is True
    assert applied["AUTHORITATIVE_READBACK"]["per_session"] == [0, 0, 0]
    assert report["comparison"]["any_class_varied"] is True


# ===========================================================================
# Claim 3 -- 27/30 is the floor, not headroom
# ===========================================================================


@pytest.mark.parametrize("session", SESSIONS)
def test_b3_no_readback_sits_exactly_on_the_threshold(report, session):
    entry = report["ceiling"][session]["NO_READBACK"]["B3_INTENT_NO_BARRIER"]

    assert entry["applied"] == 27
    assert entry["state"] == "AT THRESHOLD"


def test_at_threshold_is_reported_separately_from_ok(report):
    """A cell one run from failing must not render as OK."""
    assert sorted(report["at_threshold"]) == [
        "inflight-s1-2026-09-04/NO_READBACK/B3_INTENT_NO_BARRIER",
        "inflight-s2-2026-09-04/NO_READBACK/B3_INTENT_NO_BARRIER",
    ]


def test_the_write_up_states_all_three_claims():
    """The three the report was asked to state plainly."""
    text = VERDICT_NOTE.read_text(encoding="utf-8")

    assert "deterministic replay" in text
    assert "does not hold as written" in text
    assert "not headroom" in text.lower()
