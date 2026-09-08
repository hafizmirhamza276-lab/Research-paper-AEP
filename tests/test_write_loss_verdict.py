r"""WS-4's verdict script, proven non-vacuously on three constructed sessions.

`scripts/analyse_write_loss.py` was written from `d8b2ca5` alone, before any
write-loss data existed. These fixtures are the proof that it discriminates:

1. **the predicted outcome** — AEP-full at 0, B3 at ceiling, under an
   anticipated Redis behaviour;
2. **its negation** — AEP-full applies as freely as B3, so the barrier withheld
   nothing;
3. **the complicating behaviour** — the numbers hold, but `WAITAOF`
   acknowledged *after* the device stopped accepting writes, which is the third
   behaviour `d8b2ca5` §2 named as complicating the reading.

**Each must produce a different reading.** A script that answers the same way for
all three is decoration, and the third is the one that matters: a verdict which
can only say *held* or *refuted* is scoring the pre-registration rather than
applying it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analyse_write_loss import (
    Behaviour,
    Verdict,
    analyse,
    classify_reading,
)

ABLATION_HEADER = (
    "regime,system,response_class,runs,executions,"
    "executions_with_an_applied_effect,applied_effects_total,declared_ambiguous,"
    "confirmed_not_applied,undetected_duplicates,lost_effects,canary_survived,"
    "canary_lost"
)

ARM_ORDER = ("AEP_FULL", "B3_INTENT_NO_BARRIER")


def build_session(
    tmp_path: Path,
    *,
    aep_applied: int,
    b3_applied: int,
    aep_lost: int = 0,
    dupes: int = 0,
    ack_after_fault: bool = False,
    post_fault_wait_ms: float = 60.0,
    executions: int = 300,
    runs: int = 30,
) -> Path:
    """A session root with just enough for the verdict script to read."""
    root = tmp_path / "writeloss-session"
    (root / "analysis").mkdir(parents=True)

    rows = [ABLATION_HEADER]
    for system, applied in zip(ARM_ORDER, (aep_applied, b3_applied)):
        lost = aep_lost if system == "AEP_FULL" else 0
        rows.append(
            f"write-loss-preack,{system},NO_READBACK,{runs},{executions},"
            f"{applied},{applied},{executions},0,{dupes},{lost},{runs},0"
        )
    (root / "analysis" / "redis-kill-ablation.csv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )

    progress = []
    for system, applied in zip(ARM_ORDER, (aep_applied, b3_applied)):
        per_run = applied // runs
        for index in range(runs):
            progress.append({
                "run_id": f"{system.lower()}-r{index}",
                "system": system,
                "endpoint": "ledger_postings",
                "status": "collected",
                "applied_effects_total": per_run,
                "started_at": 1000.0 + index,
            })
    (root / "matrix-progress.jsonl").write_text(
        "\n".join(json.dumps(r) for r in progress) + "\n", encoding="utf-8"
    )

    # Per-run summary.json, because that is where the per-run counts actually
    # live and where analyse_write_loss.py has read them from since 856d78a.
    # This fixture previously carried only matrix-progress.jsonl -- the file the
    # OLD per_run_applied read a non-existent key from, which is the defect that
    # commit repaired. A fixture still describing the old shape was asserting
    # against a world the script no longer reads, and it went unnoticed because
    # that pass ran check_paper_numbers.py rather than the suite.
    for record in progress:
        run_dir = root / record["run_id"]
        run_dir.mkdir(exist_ok=True)
        (run_dir / "summary.json").write_text(
            json.dumps(
                {
                    "run_id": record["run_id"],
                    "system": record["system"],
                    "oracle_effect_executions": record["applied_effects_total"],
                }
            ),
            encoding="utf-8",
        )

    # One AEP-full run's worker log, carrying the fault and what followed it.
    run = root / "aep_full-none-ledger_postings-abcd1234-r0"
    run.mkdir()
    arm_return_ns = 5_000_000_000
    command_ms = 25
    arm_at = arm_return_ns - command_ms * 1_000_000
    events = [
        {"event": "redis_kill_armed", "monotonic_ns": arm_at - 1_000_000},
        {
            "event": "redis_kill_issued",
            "mechanism": "write-loss",
            "monotonic_ns": arm_return_ns,
            "command_ms": command_ms,
        },
    ]
    if ack_after_fault:
        events.append({
            "event": "durability_ack_observed",
            "monotonic_ns": arm_at + 30_000_000,
            "checkpoint": "AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT",
        })
    events.append({
        "event": "execution_failed",
        "monotonic_ns": arm_at + int(post_fault_wait_ms * 1_000_000),
        "failure_class": "DurabilityBarrierError",
    })
    (run / "events-worker-0-attempt-1.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    return root


# ===========================================================================
# The three fixtures, and the requirement that they differ
# ===========================================================================


def test_fixture_1_the_predicted_outcome(tmp_path):
    """AEP-full withholds, B3 proceeds, under an anticipated behaviour."""
    report = analyse(build_session(tmp_path, aep_applied=0, b3_applied=300))

    assert report["verdict"] == Verdict.HELD.value
    assert report["behaviour"] == Behaviour.WAITAOF_ERROR.value
    assert "a behaviour the pre-registration anticipated" in report["reading"]


def test_fixture_2_the_negation(tmp_path):
    """The barrier withheld nothing: AEP-full applies as freely as B3."""
    report = analyse(build_session(tmp_path, aep_applied=294, b3_applied=300))

    assert report["verdict"] == Verdict.REFUTED.value
    assert "above the refutation threshold" in " ".join(report["reasons"])


def test_fixture_3_the_complicating_behaviour(tmp_path):
    """The numbers hold, but WAITAOF acked after the device stopped writing.

    `d8b2ca5` §2 named this as the behaviour that *"would complicate the
    reading"*. The prediction's direction survives; the mechanism it describes
    does not.
    """
    report = analyse(
        build_session(tmp_path, aep_applied=0, b3_applied=300, ack_after_fault=True)
    )

    assert report["verdict"] == Verdict.HELD.value
    assert report["behaviour"] == Behaviour.SILENT_APPEND_FAILURE.value
    assert "COMPLICATING" in report["reading"]
    assert "the mechanism is not" in report["reading"]


def test_the_three_fixtures_produce_three_different_readings(tmp_path):
    """The non-vacuity requirement, asserted directly."""
    readings = {
        "predicted": analyse(
            build_session(tmp_path / "a", aep_applied=0, b3_applied=300)
        )["reading"],
        "negation": analyse(
            build_session(tmp_path / "b", aep_applied=294, b3_applied=300)
        )["reading"],
        "complicating": analyse(
            build_session(
                tmp_path / "c", aep_applied=0, b3_applied=300, ack_after_fault=True
            )
        )["reading"],
    }

    assert len(set(readings.values())) == 3, readings


# ===========================================================================
# The behaviour discriminator
# ===========================================================================


def test_a_long_post_fault_wait_reads_as_blocking(tmp_path):
    report = analyse(
        build_session(tmp_path, aep_applied=0, b3_applied=300, post_fault_wait_ms=4000)
    )

    assert report["behaviour"] == Behaviour.BLOCKED_UNTIL_TIMEOUT.value
    assert "anticipated" in report["reading"]


def test_an_ack_after_the_fault_outranks_the_wait(tmp_path):
    """A silent append failure is the finding even if the wait was long."""
    report = analyse(
        build_session(
            tmp_path, aep_applied=0, b3_applied=300,
            post_fault_wait_ms=4000, ack_after_fault=True,
        )
    )

    assert report["behaviour"] == Behaviour.SILENT_APPEND_FAILURE.value


def test_a_held_prediction_under_a_silent_failure_is_not_a_clean_hold():
    """The distinction the pre-registration requires, at the function level."""
    clean = classify_reading(Verdict.HELD, Behaviour.WAITAOF_ERROR)
    complicated = classify_reading(Verdict.HELD, Behaviour.SILENT_APPEND_FAILURE)

    assert clean != complicated
    assert "COMPLICATING" in complicated and "COMPLICATING" not in clean


# ===========================================================================
# The two exact quantities refute on their own
# ===========================================================================


def test_a_lost_effect_for_aep_full_refutes(tmp_path):
    report = analyse(
        build_session(tmp_path, aep_applied=0, b3_applied=300, aep_lost=1)
    )

    assert report["verdict"] == Verdict.REFUTED.value
    assert any("lost effects" in r for r in report["reasons"])


def test_an_undetected_duplicate_refutes(tmp_path):
    report = analyse(build_session(tmp_path, aep_applied=0, b3_applied=300, dupes=1))

    assert report["verdict"] == Verdict.REFUTED.value
    assert any("undetected duplicates" in r for r in report["reasons"])


def test_b3_below_ceiling_is_not_the_predicted_contrast(tmp_path):
    """If B3 did not proceed, the separation is not the one predicted."""
    report = analyse(build_session(tmp_path, aep_applied=0, b3_applied=120))

    assert report["verdict"] == Verdict.REFUTED.value


def test_the_unit_of_analysis_is_the_run(tmp_path):
    """Rule 6. Per-run counts are reported, not only pooled executions."""
    report = analyse(build_session(tmp_path, aep_applied=0, b3_applied=300))

    assert report["criteria"]["unit_of_analysis"] == "run"
    assert len(report["per_run_applied"]["AEP_FULL"]) == 30
    assert len(report["per_run_applied"]["B3_INTENT_NO_BARRIER"]) == 30
