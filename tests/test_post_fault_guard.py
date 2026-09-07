r"""The post-fault restart is conditional on the fault class killing the server.

`runner.py` restarts Redis and then *verifies it died* — `uptime_in_seconds`
proves the server the run started with is gone. The comment above that call
states the premise: *a worker killed Redis and cannot have restarted it*.

That premise is false for a fault class that does not kill. Under `write-loss`
Redis keeps running by design — the device stops accepting writes while the
server keeps serving reads — so the verification can never pass, and before this
change it refused every run with *"the hard kill did not land"*.

The mechanism is read from the **environment**, exactly as `killer_for` reads it.
Not from `RunConfig`: `docs/31` §4 records that `RunConfig._body()` iterates every
field into `config_digest`, so a new field would move the digest of all 432 frozen
matrix runs against `docs/32`'s generation-aware check.

**Live proof, not only these tests.** Running the regimes showed the guard firing
for `kill` and `pause-then-kill` (2/2 collected each, `redis_hard_killed` present)
and silent for `write-loss` (3/3 collected, zero such events). These tests pin the
decision so it cannot regress without failing.
"""

from __future__ import annotations

import inspect

import pytest

from experiments.harness import runner
from experiments.harness.redis_kill import (
    MECHANISM_KILL,
    MECHANISM_PAUSE_THEN_KILL,
    MECHANISM_WRITE_LOSS,
    NON_KILLING_MECHANISMS,
    REDIS_FAULT_MECHANISM_VARIABLE,
    SERVER_KILLING_MECHANISMS,
    mechanism_kills_server,
)


@pytest.mark.parametrize(
    ("mechanism", "kills"),
    [
        (MECHANISM_KILL, True),
        (MECHANISM_PAUSE_THEN_KILL, True),
        (MECHANISM_WRITE_LOSS, False),
        ("", True),      # unset: the default mechanism is a kill
        (None, True),
    ],
)
def test_which_mechanisms_kill_the_server(mechanism, kills):
    assert mechanism_kills_server(mechanism) is kills


def test_an_unknown_mechanism_is_treated_as_killing():
    """The conservative direction: the guard fires and the run is refused.

    The first version returned `mechanism in SERVER_KILLING_MECHANISMS`, which
    sends an unrecognised mechanism down the NON-killing branch and silently
    skips a verification that should have run. `killer_for` raises on an unknown
    mechanism, so a run cannot reach here with one -- but a predicate whose
    unsafe default is prevented only by a caller elsewhere is one refactor away
    from being wrong.
    """
    assert mechanism_kills_server("wrtie-loss") is True
    assert mechanism_kills_server("something-new") is True


def test_the_mechanism_is_read_from_the_environment(monkeypatch):
    """The same source `killer_for` reads, so the two cannot disagree."""
    monkeypatch.setenv(REDIS_FAULT_MECHANISM_VARIABLE, MECHANISM_WRITE_LOSS)
    assert mechanism_kills_server() is False

    monkeypatch.setenv(REDIS_FAULT_MECHANISM_VARIABLE, MECHANISM_PAUSE_THEN_KILL)
    assert mechanism_kills_server() is True

    monkeypatch.delenv(REDIS_FAULT_MECHANISM_VARIABLE, raising=False)
    assert mechanism_kills_server() is True


def test_the_two_sets_do_not_overlap():
    assert not (SERVER_KILLING_MECHANISMS & NON_KILLING_MECHANISMS)


# ===========================================================================
# config_digest must not learn about any of this
# ===========================================================================


def test_the_mechanism_is_not_a_run_config_field():
    from experiments.harness.config import RunConfig

    fields = set(RunConfig.__dataclass_fields__)

    assert "redis_fault_mechanism" not in fields
    assert "write_loss_device" not in fields


# ===========================================================================
# The call site stays gated
# ===========================================================================


def test_the_restart_call_is_gated_on_the_fault_class():
    """Pins the condition itself: an ungated call refuses every write-loss run."""
    source = inspect.getsource(runner)
    index = source.find("restart_after_hard_kill(")
    assert index != -1

    # The `if` that guards the call is the line above it.
    preceding = source[:index]
    guard = preceding[preceding.rfind("if config.redis_kill_point"):]

    assert "mechanism_kills_server()" in guard, (
        "the restart is no longer conditional on the fault class killing the "
        "server; every write-loss run will be refused with 'the hard kill did "
        "not land'"
    )


def test_the_per_run_restore_is_present_and_gated():
    """The restore runs before the workers, only for write-loss."""
    source = inspect.getsource(runner)

    assert "write_loss_restored" in source
    restore_at = source.find("restore_pass_mode(")
    workers_at = source.find("asyncio.to_thread(run_worker_slot")
    assert restore_at != -1 and restore_at < workers_at, (
        "the restore must happen BEFORE the workers run, or the run's pre-fault "
        "portion executes on a device a previous run left dropping"
    )
