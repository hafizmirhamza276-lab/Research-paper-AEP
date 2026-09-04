r"""The WS-4 write-loss delivery gate, tested for the failures it must catch.

`docs/24-revision-backlog.md` B1: under write loss the fault *is* the
measurement, so a non-delivery does not add noise — it removes the phenomenon
and leaves a run that looks like a clean success for both arms. Everything in
§5 of `reports/phase-report-ws4-prediction-2026-09-04.md` — the abort rule, the
void thresholds, the inconclusive verdict — rests on this gate noticing.

**So most of this file is about making it say NOT_DELIVERED.** A gate only
tested on the happy path is not a gate; it is a formality that will pass when
the instrument is broken, which is the precise failure B1 describes.

The gate is a pure function over two observations — what the `dm-flakey` table
said, and what happened to an unacknowledged canary — so every path, including
the ones that need a broken device to reach in reality, is reachable here.
"""

from __future__ import annotations

import pytest

from experiments.harness.write_loss import (
    CanaryResult,
    Delivery,
    arm_drop_writes,
    classify_delivery,
    table_declares_drop,
)

DROP = "0 524288 flakey /dev/loop0 0 0 1 1 drop_writes"
PASS = "0 524288 flakey /dev/loop0 0 1 0"


# ===========================================================================
# The gate says DELIVERED only when both checks agree
# ===========================================================================


def test_delivered_requires_both_checks():
    verdict = classify_delivery(table_after=DROP, canary=CanaryResult.LOST)

    assert verdict.delivery is Delivery.DELIVERED
    assert verdict.delivered is True


# ===========================================================================
# The failures. These are the point of the file.
# ===========================================================================


def test_the_silent_failure_b1_warns_about_is_caught():
    """Table says drop_writes, but writes still reached the device.

    This is the case that motivates the whole gate: a mapping that is not the
    one Redis writes through. The structural check passes and the run looks
    successful. Only the canary sees it.
    """
    verdict = classify_delivery(table_after=DROP, canary=CanaryResult.SURVIVED)

    assert verdict.delivery is Delivery.NOT_DELIVERED
    assert "survived" in verdict.reason
    assert verdict.table_says_drop is True, (
        "the structural check passed -- which is exactly why it cannot be "
        "the only check"
    )


def test_a_table_that_was_never_flipped_is_not_delivery():
    verdict = classify_delivery(table_after=PASS, canary=CanaryResult.UNKNOWN)

    assert verdict.delivery is Delivery.NOT_DELIVERED
    assert verdict.table_says_drop is False


def test_no_canary_result_fails_closed():
    """An unobserved fault is undelivered, not assumed delivered."""
    verdict = classify_delivery(table_after=DROP, canary=CanaryResult.UNKNOWN)

    assert verdict.delivery is Delivery.NOT_DELIVERED
    assert "not observed" in verdict.reason


def test_a_lost_canary_without_a_dropping_table_is_refused():
    """The key vanished for some other reason; do not credit this fault."""
    verdict = classify_delivery(table_after=PASS, canary=CanaryResult.LOST)

    assert verdict.delivery is Delivery.NOT_DELIVERED
    assert "some other cause" in verdict.reason


def test_an_unreadable_table_is_not_delivery():
    verdict = classify_delivery(table_after=None, canary=CanaryResult.LOST)

    assert verdict.delivery is Delivery.NOT_DELIVERED


@pytest.mark.parametrize("canary", list(CanaryResult))
def test_only_one_of_the_eight_combinations_is_delivery(canary):
    """Exhaustive over (table, canary): exactly one pair may pass."""
    for table in (DROP, PASS, None):
        verdict = classify_delivery(table_after=table, canary=canary)
        should_pass = table == DROP and canary is CanaryResult.LOST
        assert verdict.delivered is should_pass, (table, canary)


# ===========================================================================
# The structural check is parsed, not string-matched
# ===========================================================================


def test_the_feature_must_belong_to_a_flakey_target():
    """A different target naming the feature must not pass."""
    assert table_declares_drop("0 524288 linear /dev/loop0 0 drop_writes") is False


def test_a_device_path_containing_the_word_does_not_pass():
    assert table_declares_drop("0 524288 flakey /dev/drop_writes 0 1 0") is False


def test_pass_mode_and_empty_do_not_declare_drop():
    assert table_declares_drop(PASS) is False
    assert table_declares_drop("") is False
    assert table_declares_drop(None) is False


def test_drop_mode_declares_drop():
    assert table_declares_drop(DROP) is True


# ===========================================================================
# The injector refuses rather than raising, and "armed" means the table agrees
# ===========================================================================


def test_arming_a_missing_device_is_a_record_not_an_exception(monkeypatch):
    """A failure to arm must become a recorded non-delivery, not a crash that
    ends the run and loses the evidence."""
    monkeypatch.setattr(
        "experiments.harness.write_loss.read_table", lambda device, **kw: None
    )

    record = arm_drop_writes("nope")

    assert record.armed is False
    assert "cannot read" in (record.error or "")


def test_arming_refuses_a_non_flakey_target(monkeypatch):
    monkeypatch.setattr(
        "experiments.harness.write_loss.read_table",
        lambda device, **kw: "0 524288 linear /dev/loop0 0",
    )

    record = arm_drop_writes("linear0")

    assert record.armed is False
    assert "not a flakey target" in (record.error or "")


def test_armed_means_the_table_read_back_agrees(monkeypatch):
    """Not that dmsetup returned 0. Issuing the change and the change taking
    effect are different events, and only the second one is the fault."""
    calls = []

    class OK:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(
        "experiments.harness.write_loss._dmsetup",
        lambda args, timeout: (calls.append(args[0]), OK())[1],
    )
    # Every dmsetup command succeeds, but the table never changes.
    monkeypatch.setattr(
        "experiments.harness.write_loss.read_table", lambda device, **kw: PASS
    )

    record = arm_drop_writes("flakey0")

    assert calls == ["table", "suspend", "reload", "resume"] or "suspend" in calls
    assert record.armed is False, (
        "all three dmsetup calls returned 0 and the table still says pass mode; "
        "arming must follow the device, not the exit codes"
    )


def test_the_armed_table_is_well_formed(monkeypatch):
    """Regression: the built table must carry a feature COUNT.

    The first version emitted "... <up> <down> drop_writes" with no count.
    dmsetup parses the field after <down> as the number of features, found a
    word, and refused the reload -- so nothing was ever armed. The unit tests
    could not see it because they mock dmsetup; only a real device could, and
    did. This pins the shape so it cannot regress silently.
    """
    built = {}

    class OK:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake(args, timeout):
        if args[0] == "reload":
            built["table"] = args[args.index("--table") + 1]
        return OK()

    monkeypatch.setattr("experiments.harness.write_loss._dmsetup", fake)
    monkeypatch.setattr(
        "experiments.harness.write_loss.read_table",
        lambda device, **kw: "0 262144 flakey 7:0 0 1 0 2 error_reads error_writes",
    )

    arm_drop_writes("flakey0")
    fields = built["table"].split()

    # <start> <len> flakey <dev> <offset> <up> <down> <n_features> <feature>
    assert len(fields) == 9, built["table"]
    assert fields[2] == "flakey"
    assert fields[4] == "0", "the live table's offset must be preserved"
    assert fields[5:8] == ["0", "1", "1"], "up=0 down=1 n_features=1"
    assert fields[8] == "drop_writes"
    assert table_declares_drop(built["table"]) is True
