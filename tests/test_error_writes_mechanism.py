r"""Phase 54's fault, and the two ways it could silently become WS-4's.

`prompts/phase-54-record-loss-restart-2026-09-24.md` rests on a distinction
that is one careless edit away from vanishing, in either of two places:

* **the device mode.** `error_writes` fails writes visibly; `drop_writes`
  discards them silently. Under `drop_writes` the barrier's `WAITAOF` succeeds
  on a lie, AEP-full dispatches, and the restart loses the record for *both*
  arms -- the cell separates nothing. The whole phase depends on the table
  carrying `error_writes` and not falling back;
* **the restart.** `MECHANISM_WRITE_LOSS` is in `NON_KILLING_MECHANISMS`, the
  set whose members skip the restart. That membership is exactly why
  `coordinator_restarted_unexpectedly` is False in all 60 WS-4 runs. If phase
  54's mechanism ever joined that set, the cell would collect WS-4 again under
  a new name and read as a clean null.

Neither would fail loudly. Both are pinned here.

**WS-4's own behaviour is pinned too**, in both places, because
`reports/raw/ws4-writeloss-s1-2026-09-07` has to stay reproducible from this
code -- the refactor that added `error_writes` must not have moved it.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _flakey():
    """Import the probe module with `redis` stubbed.

    The module imports `redis.asyncio` at top level for the parts of the probe
    that talk to Redis; the table builder needs none of it, and the tests must
    run wherever the suite runs.
    """
    if "redis" not in sys.modules:
        stub = types.ModuleType("redis")
        aio = types.ModuleType("redis.asyncio")
        aio.Redis = object
        stub.asyncio = aio
        sys.modules["redis"] = stub
        sys.modules["redis.asyncio"] = aio
    from experiments import flakey_write_loss

    return flakey_write_loss


def _stack(module):
    stack = module.DeviceStack.__new__(module.DeviceStack)
    stack.sectors = 204800
    stack.loop = "/dev/loop9"
    return stack


# --------------------------------------------------------------------------
# The device mode.
# --------------------------------------------------------------------------


def test_error_mode_emits_error_writes_and_never_drop_writes():
    """The known-positive: a silent fallback to drop_writes must fail here."""
    module = _flakey()
    table = _stack(module).table("error")
    assert "error_writes" in table, table
    assert "drop_writes" not in table, (
        "the error mode fell back to drop_writes. Under drop_writes the "
        "barrier's WAITAOF succeeds on a lie and BOTH arms lose the record, "
        "so phase 54's cell would separate nothing and read as a null"
    )


def test_ws4s_drop_table_is_byte_identical_to_what_it_always_was():
    """WS-4's collected cell must stay reproducible from this code."""
    module = _flakey()
    assert (
        _stack(module).table("drop")
        == "0 204800 flakey /dev/loop9 0 0 1 1 drop_writes"
    )


def test_pass_mode_carries_no_feature_at_all():
    module = _flakey()
    table = _stack(module).table("pass")
    assert table == "0 204800 flakey /dev/loop9 0 1 0"
    assert "writes" not in table


def test_an_unknown_mode_raises_rather_than_defaulting():
    """A typo must not become drop_writes."""
    module = _flakey()
    with pytest.raises(module.ProbeError) as raised:
        _stack(module).table("eror")
    assert "drop_writes" in str(raised.value), (
        "the refusal should say what the dangerous fallback would have been"
    )


def test_the_three_modes_are_distinct_tables():
    module = _flakey()
    stack = _stack(module)
    tables = {stack.table(mode) for mode in ("pass", "drop", "error")}
    assert len(tables) == 3


# --------------------------------------------------------------------------
# The restart.
# --------------------------------------------------------------------------


def _redis_kill():
    from experiments.harness import redis_kill

    return redis_kill


def test_phase54s_mechanism_is_not_in_non_killing_mechanisms():
    """The known-positive: adding it to that set must fail here.

    Membership means the restart is skipped. A phase-54 run without a restart
    is WS-4 with a different device mode, and its null would be meaningless.
    """
    module = _redis_kill()
    assert module.MECHANISM_WRITE_LOSS_RESTART not in module.NON_KILLING_MECHANISMS, (
        "write-loss-restart was added to NON_KILLING_MECHANISMS, so the "
        "restart is skipped. The restart IS the experiment: without it the "
        "record stays in memory, recovery reads it, and both arms report "
        "zero lost effects for a reason that has nothing to do with the "
        "barrier"
    )
    assert module.mechanism_kills_server(module.MECHANISM_WRITE_LOSS_RESTART) is True


def test_ws4s_mechanism_still_skips_the_restart():
    """The inverse, pinned: WS-4 must keep NOT restarting."""
    module = _redis_kill()
    assert module.MECHANISM_WRITE_LOSS in module.NON_KILLING_MECHANISMS
    assert module.mechanism_kills_server(module.MECHANISM_WRITE_LOSS) is False


def test_each_mechanism_routes_to_its_own_fault():
    module = _redis_kill()
    assert (
        module.killer_for(module.MECHANISM_WRITE_LOSS).__name__
        == "drop_writes_on_device"
    )
    assert (
        module.killer_for(module.MECHANISM_WRITE_LOSS_RESTART).__name__
        == "error_writes_on_device"
    )


def test_a_misspelled_mechanism_is_refused_and_named_in_the_message():
    module = _redis_kill()
    with pytest.raises(ValueError) as raised:
        module.killer_for("write-loss-restrt")
    assert "write-loss-restart" in str(raised.value)


def test_an_unset_device_is_a_recorded_non_delivery_not_an_exception(monkeypatch):
    """A failure to arm becomes evidence, not a lost run."""
    module = _redis_kill()
    monkeypatch.delenv(module.WRITE_LOSS_DEVICE_VARIABLE, raising=False)
    result = module.error_writes_on_device("any-container")
    assert result["issued"] is False
    assert result["mechanism"] == module.MECHANISM_WRITE_LOSS_RESTART
    assert module.WRITE_LOSS_DEVICE_VARIABLE in result["error"]


def test_an_already_armed_device_is_refused(monkeypatch):
    """A run whose pre-fault portion ran under the fault is a different run."""
    module = _redis_kill()
    from experiments.harness import write_loss

    monkeypatch.setenv(module.WRITE_LOSS_DEVICE_VARIABLE, "aep-flakey")
    armed = "0 204800 flakey /dev/loop9 0 0 1 1 error_writes"
    monkeypatch.setattr(write_loss, "read_table", lambda _d, **_k: armed)

    def _must_not_arm(*_a, **_k):  # pragma: no cover - the point is it is unused
        raise AssertionError("armed a device that was already armed")

    monkeypatch.setattr(write_loss, "arm_error_writes", _must_not_arm)
    result = module.error_writes_on_device("any-container")
    assert result["issued"] is False
    assert "already failing or dropping" in result["error"]


# --------------------------------------------------------------------------
# The table predicate the delivery gate reads.
# --------------------------------------------------------------------------


def test_table_declares_feature_distinguishes_the_two_faults():
    from experiments.harness import write_loss

    drop = "0 204800 flakey /dev/loop9 0 0 1 1 drop_writes"
    error = "0 204800 flakey /dev/loop9 0 0 1 1 error_writes"
    assert write_loss.table_declares_feature(drop, write_loss.DROP_FEATURE)
    assert not write_loss.table_declares_feature(drop, write_loss.ERROR_FEATURE)
    assert write_loss.table_declares_feature(error, write_loss.ERROR_FEATURE)
    assert not write_loss.table_declares_feature(error, write_loss.DROP_FEATURE)
    # And the original predicate still answers its original question.
    assert write_loss.table_declares_drop(drop)
    assert not write_loss.table_declares_drop(error)


def test_a_non_flakey_target_declares_nothing():
    from experiments.harness import write_loss

    linear = "0 204800 linear /dev/loop9 0"
    assert not write_loss.table_declares_feature(linear, write_loss.ERROR_FEATURE)
    assert not write_loss.table_declares_drop(linear)


# --------------------------------------------------------------------------
# The suspend flags. Found by rehearsing the arming path before collecting.
#
# `dmsetup suspend` calls freeze_bdev(), which SYNCS THE FILESYSTEM. For phase
# 54 that is the instrument hazard named in the pre-registration section 6: a
# sync at arming time flushes the record the cell exists to lose, and both arms
# read zero -- indistinguishable from the claim being vindicated.
#
# Two arming paths existed and disagreed. `flakey_write_loss.set_mode` has
# always passed `--noflush --nolockfs`; `harness/write_loss._reload_table`,
# which is what a RUN calls at the fault point, did not.
#
# WS-4's argv must stay exactly as it was, so the flags are opt-in.
# --------------------------------------------------------------------------


def _drive(arm):
    """Run one arming call against a simulated dmsetup; return the argv issued."""
    import types as _t

    from experiments.harness import write_loss

    issued: list[list[str]] = []
    live = {"table": "0 204800 flakey /dev/loop9 0 1 0"}

    def fake(args, *, timeout):
        issued.append(list(args))
        if args[0] == "table":
            return _t.SimpleNamespace(returncode=0, stdout=live["table"], stderr="")
        if args[0] == "reload":
            live["table"] = args[args.index("--table") + 1]
        return _t.SimpleNamespace(returncode=0, stdout="", stderr="")

    original = write_loss._dmsetup
    write_loss._dmsetup = fake
    try:
        record = arm("aep-flakey")
    finally:
        write_loss._dmsetup = original
    return issued, record


def test_phase54_suspends_without_flushing_the_filesystem():
    """The known-positive: dropping the flags must fail here.

    Without them the arming step syncs the record to the platter and the cell
    measures nothing, while looking like a clean result.
    """
    from experiments.harness import write_loss

    issued, record = _drive(write_loss.arm_error_writes)
    suspend = [a for a in issued if a[0] == "suspend"][0]
    assert suspend == ["suspend", "--noflush", "--nolockfs", "aep-flakey"], (
        "phase 54 armed the device with a plain suspend, which calls "
        "freeze_bdev() and syncs the filesystem. That flushes the record the "
        "cell is trying to lose, and both arms would read zero -- the "
        "instrument failure the pre-registration section 6 exists to catch"
    )
    assert "error_writes" in record.table_after


def test_ws4s_suspend_argv_is_unchanged():
    """WS-4's collected cell must stay reproducible from this code."""
    from experiments.harness import write_loss

    issued, record = _drive(write_loss.arm_drop_writes)
    suspend = [a for a in issued if a[0] == "suspend"][0]
    assert suspend == ["suspend", "aep-flakey"], (
        "WS-4's dmsetup argv changed; reports/raw/ws4-writeloss-s1-2026-09-07 "
        "is no longer reproducible from this code"
    )
    assert "drop_writes" in record.table_after


def test_the_armed_table_is_well_formed_for_the_kernel():
    """A malformed table shipped once and only a real device caught it.

    <start> <len> flakey <dev> <offset> <up> <down> <n_features> <features...>
    """
    from experiments.harness import write_loss

    _issued, record = _drive(write_loss.arm_error_writes)
    fields = record.table_after.split()
    assert len(fields) == 9, fields
    assert fields[2] == "flakey"
    assert fields[0].isdigit() and fields[1].isdigit()
    assert fields[4].isdigit()
    assert fields[5].isdigit() and fields[6].isdigit()
    assert not (fields[5] == "0" and fields[6] == "0"), "the kernel refuses both zero"
    assert fields[7] == "1", "the feature COUNT must precede the feature"
    assert fields[8] == "error_writes"


def test_the_device_is_resumed_even_though_the_reload_succeeded():
    from experiments.harness import write_loss

    issued, _record = _drive(write_loss.arm_error_writes)
    assert any(a[0] == "resume" for a in issued), (
        "a suspended dm device blocks every I/O against it"
    )
