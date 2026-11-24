"""``results/<run_id>/events.jsonl`` -- the run log, which is the second oracle.

Amendment C4 makes this file evidence rather than telemetry: the counts in the
paper are cross-checked between it and the mock API's SQLite ledger, and a
disagreement is a bug. Three properties follow from that.

*Every record must survive a SIGKILL of its writer.* Which means flushed on
write, not buffered until close.

*Every record must be placeable on a timeline.* Which means both clocks: wall
time, because it is the only one comparable across processes, and monotonic,
because it is the only one that cannot go backwards inside a process. A
``clock_reference`` record pairs them once per process so a reader can convert.

*Nothing may be silently overwritten.* A caller that passes ``event=`` or
``wall_ms=`` as a payload field is refused, because the alternative is a record
whose meaning depends on dictionary ordering.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from experiments.harness.events import (
    RESERVED_FIELDS,
    EventLog,
    merge_event_shards,
    read_events,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def log(tmp_path) -> EventLog:
    instance = EventLog(
        tmp_path / "events-worker-0.jsonl", run_id="run-test", source="worker-0"
    )
    try:
        yield instance
    finally:
        instance.close()


# ===========================================================================
# The record shape
# ===========================================================================


def test_the_first_record_is_a_clock_reference(log, tmp_path):
    records = read_events(log.path)

    assert records[0]["event"] == "clock_reference"
    assert records[0]["wall_ns"] > 0
    assert records[0]["monotonic_ns"] > 0
    assert records[0]["pid"] == os.getpid()


def test_every_record_carries_both_clocks_and_its_provenance(log):
    log.emit("execution_started", execution_id="exec-1")

    record = read_events(log.path)[-1]

    assert record["event"] == "execution_started"
    assert record["execution_id"] == "exec-1"
    assert record["run_id"] == "run-test"
    assert record["source"] == "worker-0"
    assert record["pid"] == os.getpid()
    assert isinstance(record["wall_ms"], int)
    assert isinstance(record["monotonic_ns"], int)
    assert record["wall_iso"].endswith("+00:00")


def test_the_sequence_number_is_dense_and_per_source(log):
    for index in range(5):
        log.emit("tick", index=index)

    sequences = [record["seq"] for record in read_events(log.path)]

    assert sequences == list(range(len(sequences)))


def test_monotonic_never_decreases_within_a_process(log):
    for _ in range(20):
        log.emit("tick")

    stamps = [record["monotonic_ns"] for record in read_events(log.path)]

    assert stamps == sorted(stamps)


@pytest.mark.parametrize("field", sorted(RESERVED_FIELDS))
def test_a_payload_field_may_not_shadow_a_reserved_one(log, field):
    with pytest.raises(ValueError) as refused:
        log.emit("tick", **{field: "hijacked"})

    assert field in str(refused.value)


def test_a_payload_that_cannot_be_serialised_is_refused_at_the_call_site(log):
    """Better to fail the emitting line than to write a broken JSONL file."""
    with pytest.raises(TypeError):
        log.emit("tick", value=object())

    # ...and the file is still parseable.
    assert read_events(log.path)


def test_records_are_written_one_per_line_sorted_within_the_object(log):
    log.emit("tick", zebra=1, alpha=2)

    lines = log.path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert lines[-1].index('"alpha"') < lines[-1].index('"zebra"')
    for line in lines:
        json.loads(line)


# ===========================================================================
# Durability against the crash the harness injects
# ===========================================================================


_CHILD = textwrap.dedent(
    """
    import os, signal, sys
    from pathlib import Path
    from experiments.harness.events import EventLog

    log = EventLog(Path(sys.argv[1]), run_id="run-child", source="worker-child")
    for index in range(50):
        log.emit("tick", index=index)
    # No close(), no flush of our own: exactly what a SIGKILLed worker gets.
    if hasattr(signal, "SIGKILL"):
        os.kill(os.getpid(), signal.SIGKILL)
    else:
        os.kill(os.getpid(), signal.SIGTERM)
    """
)


def test_every_record_survives_a_sigkill_of_the_writing_process(tmp_path):
    script = tmp_path / "child.py"
    script.write_text(_CHILD, encoding="utf-8")
    events = tmp_path / "events-child.jsonl"

    completed = subprocess.run(
        [sys.executable, str(script), str(events)],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        timeout=60,
    )

    assert completed.returncode != 0, "the child was supposed to be killed"
    records = read_events(events)
    ticks = [record for record in records if record["event"] == "tick"]
    assert len(ticks) == 50, (
        "records were lost to the process buffer; the run log would be missing "
        "exactly the executions the harness crashed"
    )


# ===========================================================================
# Merging the shards
# ===========================================================================


def test_shards_merge_into_one_wall_ordered_timeline(tmp_path):
    first = EventLog(tmp_path / "events-worker-0.jsonl", run_id="r", source="worker-0")
    second = EventLog(tmp_path / "events-worker-1.jsonl", run_id="r", source="worker-1")
    first.emit("a")
    second.emit("b")
    first.emit("c")
    first.close()
    second.close()

    merged = tmp_path / "events.jsonl"
    written = merge_event_shards(tmp_path, output=merged)

    records = read_events(merged)
    assert written == len(records) == 5  # two clock references, then a, b, c
    stamps = [(record["wall_ms"], record["source"], record["seq"]) for record in records]
    assert stamps == sorted(stamps)
    assert {record["source"] for record in records} == {"worker-0", "worker-1"}


def test_merging_refuses_to_read_its_own_output(tmp_path):
    """Re-running a merge must not double every record."""
    log = EventLog(tmp_path / "events-worker-0.jsonl", run_id="r", source="worker-0")
    log.emit("a")
    log.close()
    merged = tmp_path / "events.jsonl"

    merge_event_shards(tmp_path, output=merged)
    second = merge_event_shards(tmp_path, output=merged)

    assert second == 2
    assert len(read_events(merged)) == 2


def test_a_truncated_final_line_does_not_lose_the_whole_shard(tmp_path):
    """A worker killed mid-write leaves a partial line. The rest is evidence."""
    shard = tmp_path / "events-worker-0.jsonl"
    log = EventLog(shard, run_id="r", source="worker-0")
    log.emit("a")
    log.close()
    with shard.open("a", encoding="utf-8") as handle:
        handle.write('{"event": "truncated"')

    records = read_events(shard)

    assert [record["event"] for record in records] == ["clock_reference", "a"]


def test_read_events_reports_the_file_it_could_not_parse(tmp_path):
    broken = tmp_path / "events-worker-0.jsonl"
    broken.write_text('{"event": "a"}\nnot json at all\n', encoding="utf-8")

    with pytest.raises(ValueError) as failure:
        read_events(broken, tolerate_truncated_tail=False)

    assert "events-worker-0.jsonl" in str(failure.value)
