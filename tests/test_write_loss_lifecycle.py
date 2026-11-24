r"""The write-loss device lifecycle: arm, restore, and refusing to run armed.

Two defects with one cause — nothing owned restoring the flakey table:

* `provision_write_loss.py`'s self-test restored pass mode with three *unchecked*
  `dmsetup` calls, and its verdict never consulted them, so a reload that failed
  left the device dropping and the gate still returned `valid=True`;
* `write_loss.py` had `arm_drop_writes` and no inverse, so a run that armed left
  the device armed and every later run began with the fault already delivered.

A third defect fell out of proving the first: on a failed reload both functions
returned early **between suspend and resume**, leaving the device SUSPENDED. A
suspended dm device blocks every I/O against it, so the next mount hung forever
rather than erroring — a collection would have hung silently. That is why
`_reload_table` resumes in a `finally`, and why the test below asserts it.
"""

from __future__ import annotations

import pytest

from experiments.harness import write_loss
from experiments.harness.redis_kill import MECHANISM_WRITE_LOSS, drop_writes_on_device
from experiments.harness.write_loss import (
    arm_drop_writes,
    pass_mode_table,
    restore_pass_mode,
    table_declares_drop,
)

PASS = "0 1048576 flakey 7:0 0 1 0 2 error_reads error_writes"
DROP = "0 1048576 flakey 7:0 0 0 1 1 drop_writes"


class Result:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = stderr


# ===========================================================================
# The inverse
# ===========================================================================


def test_pass_mode_table_is_built_from_live_geometry():
    """Not from a remembered string: a restore must not reinstate a stale length."""
    assert pass_mode_table(DROP) == "0 1048576 flakey 7:0 0 1 0"
    assert pass_mode_table("0 99 flakey 7:9 512 0 1 1 drop_writes") == (
        "0 99 flakey 7:9 512 1 0"
    )


def test_pass_mode_table_refuses_a_non_flakey_target():
    assert pass_mode_table("0 1048576 linear 7:0 0") is None
    assert pass_mode_table("") is None


def test_restore_clears_the_armed_flag(monkeypatch):
    """`armed` means "the device is dropping", so a good restore clears it."""
    tables = iter([DROP, PASS])
    monkeypatch.setattr(write_loss, "read_table", lambda device, **kw: next(tables))
    monkeypatch.setattr(write_loss, "_dmsetup", lambda args, timeout: Result())

    record = restore_pass_mode("flakey0")

    assert record.armed is False
    assert record.error is None


def test_a_restore_that_did_not_take_effect_is_an_error(monkeypatch):
    """Every dmsetup call returns 0 and the table still declares drop."""
    monkeypatch.setattr(write_loss, "read_table", lambda device, **kw: DROP)
    monkeypatch.setattr(write_loss, "_dmsetup", lambda args, timeout: Result())

    record = restore_pass_mode("flakey0")

    assert record.armed is True
    assert "still declares drop_writes" in (record.error or "")


# ===========================================================================
# The suspension defect the proof found
# ===========================================================================


@pytest.mark.parametrize("operation", [arm_drop_writes, restore_pass_mode])
def test_a_failed_reload_still_resumes_the_device(monkeypatch, operation):
    """A device left SUSPENDED blocks all I/O and hangs the next mount.

    This is worse than an error: the collection makes no progress and reports
    nothing. The resume must happen whatever the reload did.
    """
    calls: list[str] = []

    def dmsetup(args, timeout):
        calls.append(args[0])
        if args[0] == "reload":
            return Result(returncode=1, stderr="forced")
        return Result()

    monkeypatch.setattr(write_loss, "read_table", lambda device, **kw: DROP)
    monkeypatch.setattr(write_loss, "_dmsetup", dmsetup)

    record = operation("flakey0")

    assert "resume" in calls, (
        f"{operation.__name__} returned without resuming: the device is left "
        "suspended and every later I/O against it blocks forever"
    )
    assert calls.index("resume") > calls.index("reload")
    assert record.error is not None


# ===========================================================================
# A run that begins armed must abort
# ===========================================================================


def test_a_run_whose_device_is_already_dropping_is_refused(monkeypatch):
    """Its pre-fault portion ran under write loss too, so it is not the
    experiment the regime declares."""
    monkeypatch.setenv("AEP_HARNESS_WRITE_LOSS_DEVICE", "flakey0")
    monkeypatch.setattr(write_loss, "read_table", lambda device, **kw: DROP)

    outcome = drop_writes_on_device("aep-phase2-redis72")

    assert outcome["issued"] is False
    assert outcome["mechanism"] == MECHANISM_WRITE_LOSS
    assert "already in drop_writes" in outcome["error"]
    assert "pre-fault portion" in outcome["error"]


def test_a_run_beginning_in_pass_mode_arms_normally(monkeypatch):
    monkeypatch.setenv("AEP_HARNESS_WRITE_LOSS_DEVICE", "flakey0")
    tables = iter([PASS, PASS, DROP])
    monkeypatch.setattr(write_loss, "read_table", lambda device, **kw: next(tables))
    monkeypatch.setattr(write_loss, "_dmsetup", lambda args, timeout: Result())

    outcome = drop_writes_on_device("aep-phase2-redis72")

    assert outcome["issued"] is True
    assert table_declares_drop(outcome["table_after"])


def test_the_abort_fires_before_any_dmsetup_write(monkeypatch):
    """An already-armed device must not be suspended or reloaded again."""
    calls: list[str] = []
    monkeypatch.setenv("AEP_HARNESS_WRITE_LOSS_DEVICE", "flakey0")
    monkeypatch.setattr(write_loss, "read_table", lambda device, **kw: DROP)
    monkeypatch.setattr(
        write_loss, "_dmsetup",
        lambda args, timeout: (calls.append(args[0]), Result())[1],
    )

    drop_writes_on_device("aep-phase2-redis72")

    assert "suspend" not in calls and "reload" not in calls
