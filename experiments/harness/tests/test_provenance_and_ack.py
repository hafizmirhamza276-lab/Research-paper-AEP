"""Phase 8.2: the two things the harness could not previously say about a run.

Both additions exist because a property that could move a number was neither
recorded nor recoverable afterwards:

* **The durability acknowledgement.** Phase 8.1.0 established four independent
  ways that ``applied implies acknowledged`` could not be checked against runs
  already collected. :class:`DurabilityAckObserver` makes it checkable for new
  ones, without touching ``aep_core``.
* **The environment.** Phase 9C compared five collections key by key, found
  "40 of 44 identical", and concluded they were interchangeable. The filesystem
  under the results root was not a key, and it differed.

The tests that matter most here are the negative ones: an observer that fires
at the wrong checkpoint would fabricate acknowledgements, and a provenance
probe that raises would fail a collection it was only supposed to describe.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.harness import provenance
from experiments.harness.injector import DurabilityAckObserver


class _Point:
    """A stand-in for the protocol's crash-point enum member."""

    def __init__(self, name: str) -> None:
        self.name = name


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def __call__(self, event: str, /, **fields) -> None:
        self.events.append((event, fields))


# ------------------------------------------------------- the ack observer


async def test_the_observer_fires_only_at_the_post_acknowledgement_point() -> None:
    """Every other boundary must pass through it silently.

    The protocol announces a dozen instruction boundaries and only one of them
    means the acknowledgement was issued. An observer that fired at, say,
    ``DURING_INTENT_CAS`` would record an acknowledgement that had not
    happened -- and because the invariant it feeds predicts zero exceptions,
    a false positive here is invisible: it makes the check pass.
    """
    emit = _Recorder()
    observer = DurabilityAckObserver(emit=emit)
    observer.enter_execution("exec-1")
    for name in (
        "BEFORE_LEASE_ACQUISITION",
        "DURING_INTENT_CAS",
        "AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER",
        "AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION",
        "DURING_RESOLUTION_CAS",
    ):
        await observer.checkpoint(_Point(name))
    assert emit.events == []

    await observer.checkpoint(_Point("AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT"))
    assert len(emit.events) == 1
    event, fields = emit.events[0]
    assert event == "durability_ack_observed"
    assert fields["execution_id"] == "exec-1"


async def test_the_observer_attributes_each_ack_to_its_own_execution() -> None:
    """A run with several executions must not credit them all to the first."""
    emit = _Recorder()
    observer = DurabilityAckObserver(emit=emit)
    point = _Point("AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT")
    for execution_id in ("exec-a", "exec-b"):
        observer.enter_execution(execution_id)
        await observer.checkpoint(point)
    assert [fields["execution_id"] for _, fields in emit.events] == [
        "exec-a",
        "exec-b",
    ]


async def test_the_observer_injects_nothing() -> None:
    """It is on the protocol path; it must not be able to change control flow.

    ``checkpoint`` returning normally for every input is the whole safety
    argument for putting it there.
    """
    emit = _Recorder()
    observer = DurabilityAckObserver(emit=emit)
    observer.enter_execution("exec-1")
    assert await observer.checkpoint(_Point("mid_dispatch")) is None
    assert await observer.checkpoint(
        _Point("AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT")
    ) is None


# ----------------------------------------------------------- provenance


def test_the_filesystem_probe_describes_a_real_directory(tmp_path: Path) -> None:
    record = provenance.results_root_filesystem(tmp_path)
    assert record["path"] == str(tmp_path)
    # Either it identified the filesystem, or it said why it could not. A
    # silent gap is the failure mode this module exists to remove.
    assert "type" in record or "error" in record


def test_a_missing_container_is_recorded_rather_than_raised() -> None:
    """A provenance probe must never be able to fail a collection.

    The probe runs at run construction, before any worker starts. If it raised
    on a host without Docker, it would convert a describable gap into a lost
    run -- strictly worse than the gap it exists to close.
    """
    record = provenance.redis_storage_backing("aep-no-such-container-8f3a")
    assert "error" in record
    assert record["container"] == "aep-no-such-container-8f3a"
    assert "mount_type" not in record


def test_collect_is_json_serialisable_and_names_both_fields() -> None:
    """It is written into run-config.json, so it has to survive json.dumps.

    Both fields must be present even when they cannot be filled: a key that
    disappears when a probe fails would make "this run does not say" and "this
    run was not asked" indistinguishable to a later reader.
    """
    record = provenance.collect(Path("."), "aep-no-such-container-8f3a")
    assert "results_root_filesystem" in record
    assert "redis_storage_backing" in record
    json.dumps(record)


def test_no_container_still_yields_the_backing_key() -> None:
    record = provenance.collect(Path("."), None)
    assert "error" in record["redis_storage_backing"]


# ------------------------------------------- where the observer is attached


def test_a_run_with_no_fault_injector_still_gets_no_injector() -> None:
    """The crash-free cells must keep dispatching no checkpoints at all.

    ``compose_injectors`` returns ``None`` when nothing is selected, and a
    ``None`` injector makes ``WriteAheadRunner._checkpoint`` a no-op. That is
    the state every crash-free ``p0`` run was collected in -- and ``p0`` is the
    only regime RQ3's cost numbers may use.

    Attaching the acknowledgement observer unconditionally would switch the
    checkpoint machinery on in exactly those cells, changing their conditions
    relative to every crash-free run already collected, to record an invariant
    that is vacuous there: nothing prevents a dispatch in a run with no fault.
    It would also begin resolving names through ``crash_point_enum``, which for
    a baseline system is ``BaselineCrashPoint`` and need not contain the
    acknowledgement boundary at all.
    """
    from experiments.harness.injector import compose_injectors

    assert compose_injectors(None, None, None) is None


def test_the_observer_is_ordered_before_a_synchronous_worker_kill() -> None:
    """Ordering is load-bearing at ``after_barrier_before_dispatch``.

    A synchronous worker kill never returns, so anything listed after it never
    fires. The run in which the acknowledgement was issued and the process then
    died before dispatching is precisely the run the fail-closed invariant is
    about; recorded after the crash injector, it would report nothing.
    """
    from experiments.harness.injector import CompositeInjector, compose_injectors

    emit = _Recorder()
    observer = DurabilityAckObserver(emit=emit)
    crash = object()
    composed = compose_injectors(None, observer, crash)
    assert isinstance(composed, CompositeInjector)
    assert composed.injectors.index(observer) < composed.injectors.index(crash)
