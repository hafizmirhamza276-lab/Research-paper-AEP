r"""The block-level write-loss fault, and the gate that says whether it landed.

WS-4 / backlog **B1**. The analogue of :mod:`experiments.harness.redis_kill`,
for a fault that stops the device accepting writes instead of killing the
server.

**Why this file has a gate at all, and why the gate is the hard part.**
``docs/24-revision-backlog.md`` B1:

    In Phase 8 the kill is a *side condition*: a run whose fault did not land is
    discarded and the estimand is measured on the runs where it did. **In B1 the
    fault *is* the measurement.** [...] An instrument that intermittently fails
    to deliver the fault does not cost B1 precision -- it silently removes the
    phenomenon while leaving runs that look successful.

A run whose writes were never dropped looks like a clean success for *both*
arms. It is not distinguishable, after the fact, from a genuine survival. So the
whole of the pre-registered abort rule
(``reports/phase-report-ws4-prediction-2026-09-04.md`` §5) rests on detecting
non-delivery *at the time*, and this module's job is to make that detectable
rather than assumed.

**Two independent checks, and one of them is behavioural.**

1. **Structural** -- read the ``dm-flakey`` table back and require it to say
   ``drop_writes``. Cheap, and catches a table that was never flipped.
2. **Behavioural** -- a canary written *after* arming and *not* acknowledged
   must **not** survive a restart. This is the one that matters: the table can
   read ``drop_writes`` while writes still reach the platter, if the table
   belongs to a device Redis is not actually writing through, or if the mapping
   was resumed against the wrong backing. The structural check cannot see that;
   the canary can, because it asks the question end to end.

Structural alone is exactly the silent failure B1 warns about, which is why
:func:`classify_delivery` refuses to return ``DELIVERED`` on it.

**It fails closed.** No canary result means ``NOT_DELIVERED``, not "probably
fine". A gate that passes when it did not look is not a gate.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

#: The device-mapper target this fault is built on.
FLAKEY_TARGET = "flakey"

#: ``drop_writes`` makes the device accept writes and discard them silently --
#: reads still work, so Redis keeps serving while nothing reaches the platter.
#: That is the fault under study: not an I/O error the application can see, but
#: a device that lies about having written.
DROP_FEATURE = "drop_writes"

#: ``error_writes`` makes the device FAIL writes visibly, with an I/O error.
#: Phase 54's fault, added 2026-09-24. It is not interchangeable with
#: ``drop_writes``: under a lying fsync the model expects ``NoLostEffect`` to
#: fail *with the barrier enabled*, so both arms lose and nothing separates
#: them. An honest failure makes the barrier's ``WAITAOF`` fail, which is what
#: lets AEP-full withhold dispatch and B3 not.
#: ``prompts/phase-54-record-loss-restart-2026-09-24.md`` §2.
ERROR_FEATURE = "error_writes"


class Delivery(str, Enum):
    """Did the write-loss fault actually take effect for this run?"""

    DELIVERED = "DELIVERED"
    NOT_DELIVERED = "NOT_DELIVERED"


class CanaryResult(str, Enum):
    """What happened to the unacknowledged key written after arming."""

    #: Gone after the restart. Writes were being dropped.
    LOST = "LOST"
    #: Still there. Writes were reaching the device: the fault did NOT land.
    SURVIVED = "SURVIVED"
    #: Not probed, or the probe itself failed. Treated as non-delivery.
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DeliveryVerdict:
    """The gate's answer, with the reason it reached it."""

    delivery: Delivery
    reason: str
    table_says_drop: bool
    canary: CanaryResult

    @property
    def delivered(self) -> bool:
        return self.delivery is Delivery.DELIVERED


def table_declares_drop(table: str | None) -> bool:
    """Does this ``dmsetup table`` line put the device in ``drop_writes``?

    Parsed rather than string-matched loosely: a table naming the feature in a
    comment, or a *different* target that happens to contain the word, must not
    pass. The flakey table is
    ``<start> <len> flakey <dev> <offset> <up> <down> [<n> <feature>...]``.
    """
    if not table:
        return False
    fields = table.split()
    if FLAKEY_TARGET not in fields:
        return False
    return table_declares_feature(table, DROP_FEATURE)


def table_declares_feature(table: str | None, feature: str) -> bool:
    """Does this ``dmsetup table`` line carry `feature`?

    The generalisation of :func:`table_declares_drop`, which now delegates
    here. Kept as a separate function rather than a parameter with a default
    so that every existing call site keeps asking the question it always
    asked -- WS-4's collected cell must stay reproducible from this code.
    """
    if not table:
        return False
    fields = table.split()
    if FLAKEY_TARGET not in fields:
        return False
    target_at = fields.index(FLAKEY_TARGET)
    # Features follow the up/down interval pair; anything before the target
    # name is geometry and cannot be a feature.
    return feature in fields[target_at:]


def classify_delivery(
    *,
    table_after: str | None,
    canary: CanaryResult,
) -> DeliveryVerdict:
    """**The gate.** Pure, so every path can be tested including the failures.

    ``DELIVERED`` requires *both* checks to agree. Either alone is insufficient:

    * table says ``drop_writes`` but the canary survived -> the mapping was not
      the one Redis writes through, and the run measured nothing;
    * canary lost but the table does not say ``drop_writes`` -> the key vanished
      for some other reason, and attributing it to this fault would be inventing
      a cause.
    """
    says_drop = table_declares_drop(table_after)

    if not says_drop and canary is CanaryResult.LOST:
        return DeliveryVerdict(
            Delivery.NOT_DELIVERED,
            "the canary was lost but the table was not in drop_writes: the loss "
            "has some other cause and must not be attributed to this fault",
            says_drop,
            canary,
        )
    if not says_drop:
        return DeliveryVerdict(
            Delivery.NOT_DELIVERED,
            "the dm-flakey table was not in drop_writes across the armed window",
            says_drop,
            canary,
        )
    if canary is CanaryResult.SURVIVED:
        return DeliveryVerdict(
            Delivery.NOT_DELIVERED,
            "the table declared drop_writes but an unacknowledged canary "
            "survived a restart: writes were still reaching the device, so the "
            "fault did not take effect on the path Redis actually uses",
            says_drop,
            canary,
        )
    if canary is CanaryResult.UNKNOWN:
        return DeliveryVerdict(
            Delivery.NOT_DELIVERED,
            "no canary result: delivery was not observed, and an unobserved "
            "fault is treated as undelivered rather than assumed",
            says_drop,
            canary,
        )
    return DeliveryVerdict(
        Delivery.DELIVERED,
        "table in drop_writes and an unacknowledged canary did not survive",
        says_drop,
        canary,
    )


# ------------------------------------------------------------------ the injector


@dataclass
class WriteLossRecord:
    """What one arming did, recorded for the run's artifacts."""

    device: str
    table_before: str | None
    table_after: str | None
    armed: bool
    arm_ms: int
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _dmsetup(args: list[str], *, timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["dmsetup", *args], capture_output=True, text=True, timeout=timeout
    )


def read_table(device: str, *, timeout: float = 10.0) -> str | None:
    """The device's current table line, or ``None`` if it cannot be read."""
    try:
        completed = _dmsetup(["table", device], timeout=timeout)
    except Exception:  # noqa: BLE001 -- an unreadable table is a None, not a raise
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _reload_table(
    device: str, table: str, *, timeout: float, flush: bool = True
) -> str | None:
    """suspend -> reload -> resume, resuming even if the reload fails.

    Returns an error string, or ``None`` on success.

    ``flush`` defaults to ``True``, which is a plain ``dmsetup suspend`` and is
    **exactly what WS-4 issued**: its collected cell must stay reproducible
    from this code, so the default reproduces the old argv byte for byte.

    ``flush=False`` adds ``--noflush --nolockfs``, which phase 54 requires.
    A plain suspend calls ``freeze_bdev()`` and **syncs the filesystem** --
    `experiments/flakey_write_loss.py`'s module docstring says so, and its own
    `set_mode` has always passed both flags for that reason. For phase 54 the
    sync is the instrument hazard named in
    ``prompts/phase-54-record-loss-restart-2026-09-24.md`` §6: it would flush
    the very record the cell is trying to lose, and BOTH ARMS would read zero,
    which looks exactly like the claim being vindicated.

    Found by rehearsing the arming path against a simulated ``dmsetup`` before
    any collection -- the two arming paths in this repository disagreed, and
    the one a run actually calls was the unflagged one.

    **The resume is in a `finally` on purpose.** An earlier version returned
    early when the reload failed and left the device SUSPENDED; a suspended dm
    device blocks every I/O against it, so the next mount hung forever rather
    than erroring. A collection would have hung the same way -- silently, with no
    progress and no failure. Found by the proof that forces a reload to fail.
    """
    suspend_args = ["suspend", device] if flush else [
        "suspend", "--noflush", "--nolockfs", device
    ]
    suspended = _dmsetup(suspend_args, timeout=timeout)
    if suspended.returncode != 0:
        return f"dmsetup suspend failed: {suspended.stderr.strip()[:200]}"
    try:
        reloaded = _dmsetup(["reload", device, "--table", table], timeout=timeout)
        if reloaded.returncode != 0:
            return f"dmsetup reload failed: {reloaded.stderr.strip()[:200]}"
    finally:
        resumed = _dmsetup(["resume", device], timeout=timeout)
        if resumed.returncode != 0:
            # Nothing can be done about it here, but it must not be silent: the
            # device is unusable and every later step will block.
            print(
                f"WARNING: dmsetup resume failed for {device}; the device is "
                f"left SUSPENDED and will block I/O: {resumed.stderr.strip()[:200]}"
            )
    return None


def arm_drop_writes(device: str, *, timeout: float = 30.0) -> WriteLossRecord:
    """Flip ``device`` into ``drop_writes``: WS-4's fault, at the checkpoint.

    Delegates to :func:`_arm_feature`. **Its behaviour is unchanged** --
    ``reports/raw/ws4-writeloss-s1-2026-09-07`` must stay reproducible from
    this code, so the split is a refactor and not a revision.
    """
    return _arm_feature(device, DROP_FEATURE, timeout=timeout)


def arm_error_writes(device: str, *, timeout: float = 30.0) -> WriteLossRecord:
    """Flip ``device`` into ``error_writes``: phase 54's fault.

    Writes FAIL visibly rather than being discarded silently, so the
    barrier's ``WAITAOF`` fails and AEP-full withholds dispatch. That is
    the whole difference from :func:`arm_drop_writes`, and it is why the
    two arms can separate at all.
    """
    # flush=False: a plain suspend would sync the filesystem and flush the
    # record this cell exists to lose. Section 6 of the pre-registration.
    return _arm_feature(device, ERROR_FEATURE, timeout=timeout, flush=False)


def _arm_feature(
    device: str, feature: str, *, timeout: float = 30.0, flush: bool = True
) -> WriteLossRecord:
    """Reload ``device``'s table with ``feature`` set, always-down.

    Mirrors :mod:`redis_kill`'s shape -- it reports what happened rather than
    raising, so a failure to arm becomes a recorded non-delivery rather than an
    exception that ends the run and loses the evidence.

    The reload/resume pair is how device-mapper changes a live table; the table
    is read back afterwards because *issuing* the change and the change *taking
    effect* are different events, and only the second one is the fault.
    """
    started = time.monotonic()
    before = read_table(device)
    if before is None:
        return WriteLossRecord(
            device=device, table_before=None, table_after=None, armed=False,
            arm_ms=int((time.monotonic() - started) * 1000),
            error=f"cannot read the current table for {device}",
        )

    fields = before.split()
    if FLAKEY_TARGET not in fields:
        return WriteLossRecord(
            device=device, table_before=before, table_after=before, armed=False,
            arm_ms=int((time.monotonic() - started) * 1000),
            error=f"{device} is not a {FLAKEY_TARGET} target; refusing to reload it",
        )

    target_at = fields.index(FLAKEY_TARGET)
    # <start> <len> flakey <dev> <offset> <up> <down> <n_features> <features...>
    #
    # The offset is preserved from the live table rather than assumed zero, and
    # the feature COUNT is emitted: a table reading "... 1 1 drop_writes" is
    # malformed, because dmsetup parses the field after <down> as the number of
    # features and finds a word. That bug shipped once and was caught only by
    # running against a real device -- the unit tests mock dmsetup, so they
    # cannot see a table the kernel would reject.
    #
    # up=0, down=1 is "always down", matching the table
    # experiments/flakey_write_loss.py has already proven on this host.
    head = fields[: target_at + 2]
    offset = fields[target_at + 2] if len(fields) > target_at + 2 else "0"
    armed_table = " ".join([*head, offset, "0", "1", "1", feature])

    try:
        failure = _reload_table(device, armed_table, timeout=timeout, flush=flush)
    except Exception as error:  # noqa: BLE001
        failure = f"{type(error).__name__}: {error}"
    if failure is not None:
        return WriteLossRecord(
            device=device, table_before=before, table_after=read_table(device),
            armed=False, arm_ms=int((time.monotonic() - started) * 1000),
            error=failure,
        )

    after = read_table(device)
    return WriteLossRecord(
        device=device,
        table_before=before,
        table_after=after,
        # Armed means the table READ BACK carries the feature, not that
        # the commands returned 0.
        armed=table_declares_feature(after, feature),
        arm_ms=int((time.monotonic() - started) * 1000),
    )

def pass_mode_table(table: str) -> str | None:
    """The pass-through table for whatever ``table`` currently describes.

    ``up=1, down=0`` with no features: the device passes every read and write
    through untouched. Built from the live geometry rather than from a
    remembered string, so a restore cannot reinstate a stale length or offset.
    """
    if not table:
        return None
    fields = table.split()
    if FLAKEY_TARGET not in fields:
        return None
    target_at = fields.index(FLAKEY_TARGET)
    head = fields[: target_at + 2]
    offset = fields[target_at + 2] if len(fields) > target_at + 2 else "0"
    return " ".join([*head, offset, "1", "0"])


def restore_pass_mode(device: str, *, timeout: float = 30.0) -> WriteLossRecord:
    """The inverse of :func:`arm_drop_writes`. Checked, and read back.

    ``arm_drop_writes`` had no counterpart, so a run that armed left the device
    armed and every later run began with the fault already delivered. That is
    not a run that measures the fault late -- it is a run whose *pre-fault*
    portion also ran under write loss, which is a different experiment from the
    one the regime declares.

    ``armed`` is ``False`` on success here: the field means "the device is
    dropping writes", so a successful restore clears it. Every dmsetup step is
    checked and the table is re-read, because issuing a reload and the reload
    taking effect are different events -- the same distinction ``arm_drop_writes``
    makes, and the one an unchecked restore silently loses.
    """
    started = time.monotonic()
    before = read_table(device)
    target = pass_mode_table(before or "")
    if target is None:
        return WriteLossRecord(
            device=device, table_before=before, table_after=before, armed=False,
            arm_ms=int((time.monotonic() - started) * 1000),
            error=f"cannot build a pass-mode table for {device!r} from {before!r}",
        )

    try:
        failure = _reload_table(device, target, timeout=timeout)
    except Exception as error:  # noqa: BLE001
        failure = f"{type(error).__name__}: {error}"
    if failure is not None:
        after = read_table(device)
        return WriteLossRecord(
            device=device, table_before=before, table_after=after,
            armed=table_declares_drop(after),
            arm_ms=int((time.monotonic() - started) * 1000),
            error=failure,
        )

    after = read_table(device)
    still_dropping = table_declares_drop(after)
    return WriteLossRecord(
        device=device,
        table_before=before,
        table_after=after,
        armed=still_dropping,
        arm_ms=int((time.monotonic() - started) * 1000),
        error=(
            f"restore reported success but the table still declares drop_writes: {after!r}"
            if still_dropping else None
        ),
    )
