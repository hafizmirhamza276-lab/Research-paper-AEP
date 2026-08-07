"""The G2 write-loss probe's logic, pinned where it can be pinned.

The probe itself needs root, a loop device and a ``dm-flakey`` target, so the
part of it that talks to the kernel cannot be exercised in a unit test. What
*can* be exercised is everything that decides what a trial means, and that is
where the probe could lie without failing:

* the two device-mapper tables -- a ``drop`` table that does not actually carry
  ``drop_writes`` would produce a probe in which nothing is ever lost, and it
  would look exactly like a real negative result;
* the VOID rule -- a trial whose *acknowledged* write did not survive says
  nothing about the unacknowledged one, and must not be counted as evidence
  either way;
* the summary arithmetic -- a loss rate computed over all trials rather than
  over countable ones would be diluted by every void trial.

No test here requires root, a device or a network, so none of them can skip.
The repository's CI gate treats a skip as an unmet environment assumption
rather than a legitimate outcome, and a probe of this kind is exactly the sort
of thing that would otherwise arrive with a permanently-skipped test attached.
"""

from __future__ import annotations

from pathlib import Path

from experiments.flakey_write_loss import (
    DROP_INTERVALS,
    PASS_INTERVALS,
    DeviceStack,
    Trial,
    summarise,
)


def _stack() -> DeviceStack:
    stack = DeviceStack(root=Path("/nonexistent-probe-root"))
    stack.loop = "/dev/loop9"
    stack.sectors = 524288
    return stack


def test_the_drop_table_actually_requests_drop_writes() -> None:
    """Without this feature flag the probe measures nothing and looks fine."""
    table = _stack().table("drop")
    assert table.endswith("1 drop_writes")
    assert "flakey /dev/loop9" in table


def test_the_pass_table_carries_no_features() -> None:
    """Pass-through must not drop anything, or the control is not a control."""
    table = _stack().table("pass")
    assert "drop_writes" not in table
    assert table == f"0 524288 flakey /dev/loop9 0 {PASS_INTERVALS[0]} {PASS_INTERVALS[1]}"


def test_the_two_tables_differ_only_in_the_fault() -> None:
    stack = _stack()
    passing = stack.table("pass").split()
    dropping = stack.table("drop").split()
    # Same target, same backing device, same offset, same extent.
    assert passing[:5] == dropping[:5]
    # dm-flakey refuses a table whose up and down intervals are both zero.
    assert PASS_INTERVALS != (0, 0) and DROP_INTERVALS != (0, 0)
    assert PASS_INTERVALS[1] == 0, "pass mode must never enter a down interval"
    assert DROP_INTERVALS[0] == 0, "drop mode must never leave the down interval"


def test_a_trial_whose_acknowledged_write_vanished_is_void_not_evidence() -> None:
    trial = Trial(index=0, acknowledged_survived=False, unacknowledged_survived=False)
    assert trial.counts is False
    assert trial.verdict.startswith("VOID")


def test_an_errored_trial_is_void_and_names_the_error() -> None:
    trial = Trial(index=0, error="ProbeError: dmsetup went away")
    assert trial.counts is False
    assert "dmsetup went away" in trial.verdict


def test_the_finding_is_the_unacknowledged_write() -> None:
    lost = Trial(index=0, acknowledged_survived=True, unacknowledged_survived=False)
    kept = Trial(index=1, acknowledged_survived=True, unacknowledged_survived=True)
    assert lost.counts and kept.counts
    assert lost.verdict == "UNACKNOWLEDGED LOST"
    assert kept.verdict == "UNACKNOWLEDGED SURVIVED"


def test_the_loss_rate_is_over_countable_trials_not_all_trials() -> None:
    """A void trial must not dilute the rate toward zero."""
    trials = [
        Trial(index=0, acknowledged_survived=True, unacknowledged_survived=False),
        Trial(index=1, acknowledged_survived=True, unacknowledged_survived=False),
        Trial(index=2, acknowledged_survived=False, unacknowledged_survived=False),
        Trial(index=3, error="ProbeError: boom"),
    ]
    summary = summarise(trials)
    assert summary["trials"] == 4
    assert summary["counted"] == 2
    assert summary["void"] == 2
    assert summary["unacknowledged_lost"] == 2
    assert summary["unacknowledged_loss_rate"] == 1.0


def test_a_run_with_no_countable_trial_reports_no_rate_rather_than_zero() -> None:
    summary = summarise([Trial(index=0, acknowledged_survived=False)])
    assert summary["counted"] == 0
    assert summary["unacknowledged_loss_rate"] is None


def test_the_exposure_window_is_reported_from_countable_trials_only() -> None:
    trials = [
        Trial(
            index=0,
            acknowledged_survived=True,
            unacknowledged_survived=False,
            write_to_drop_ms=11.0,
        ),
        Trial(
            index=1,
            acknowledged_survived=False,
            unacknowledged_survived=False,
            write_to_drop_ms=9999.0,
        ),
    ]
    summary = summarise(trials)
    assert summary["write_to_drop_ms_min"] == 11.0
    assert summary["write_to_drop_ms_max"] == 11.0
