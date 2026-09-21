"""§5 requires a wall-clock timestamp on every transcript entry.

`reports/phase-report-40-stage-10-2026-09-21.md` §5.1 found that none carried
one, across the whole live archive and in the code that would write the next.

**Why it is not bookkeeping.** §5 makes the transcript "the only replay
mechanism", and amendment 1 records that deployment auto-upgrade is ON and that
"the pinned version can change with no trace in the data". A timestamp is what
lets a later reader bound a given call against a version change -- the one
question amendment 1 says the paper must be honest about. Without it the
archive cannot answer which side of an upgrade a call was on.
"""
from __future__ import annotations

import datetime as dt
import re

import pytest

from experiments.harness.planner import (
    TRANSCRIPT_FIELDS,
    TRANSCRIPT_SCHEMA_VERSION,
    CallWrapper,
    CumulativeCounter,
    TranscriptEntry,
    Usage,
    utc_now,
)

#: UTC, ISO-8601, milliseconds, explicit Z. Not a loose "parses as a date":
#: a local-time stamp would parse and would be wrong.
ISO_UTC_MS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class FakeCall:
    model = "stub"
    snapshot = "2026-07-09"
    deployment = "d"
    api_version = "v"
    reasoning_effort = "low"
    sampling = {"reasoning_effort": "low"}
    served_model = "stub"
    usage = Usage(prompt_tokens=10, completion_tokens=2, reasoning_tokens=1)

    def __call__(self, *, max_output_tokens):
        return "ok"


@pytest.fixture
def wrapper(tmp_path):
    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    return CallWrapper(run_id="r0", run_dir=tmp_path / "r0",
                       cumulative=counter)


def test_utc_now_is_iso8601_utc_with_milliseconds():
    assert ISO_UTC_MS.match(utc_now()), utc_now()


def test_utc_now_is_actually_utc_not_local():
    """A local-time stamp matches the same regex and is still wrong."""
    stamped = dt.datetime.strptime(utc_now(), "%Y-%m-%dT%H:%M:%S.%fZ")
    stamped = stamped.replace(tzinfo=dt.timezone.utc)
    now = dt.datetime.now(dt.timezone.utc)
    assert abs((now - stamped).total_seconds()) < 60


def test_every_written_entry_carries_a_timestamp(wrapper):
    wrapper.attempt(worker_index=0, step_index=0, attempt=1, prompt="p",
                    call=FakeCall())
    entry = wrapper.transcript.entries()[0]
    assert "timestamp" in entry, entry.keys()
    assert ISO_UTC_MS.match(entry["timestamp"]), entry["timestamp"]


def test_the_timestamp_is_a_declared_field_and_the_schema_was_bumped():
    """A field added without a version bump makes two shapes one name."""
    assert "timestamp" in TRANSCRIPT_FIELDS
    assert TRANSCRIPT_SCHEMA_VERSION == "aep.agent.transcript/3"


def test_it_cannot_be_forgotten_on_a_construction_path():
    """The default_factory is the point.

    The entry is built in a ``finally`` block reached from four different
    outcomes. A required parameter would be passed on the path someone tested
    and missed on the one they did not, which is how the field came to be
    absent in the first place.
    """
    entry = TranscriptEntry(
        run_id="r", worker_index=0, step_index=0, attempt=1, prompt="p",
        completion="c", model="m", snapshot="s", deployment="d",
        api_version="v", reasoning_effort="low", sampling={},
        usage=Usage(), outcome=__import__(
            "experiments.harness.planner", fromlist=["PlannerOutcome"]
        ).PlannerOutcome.OK,
    )
    assert ISO_UTC_MS.match(entry.timestamp)


def test_timestamps_are_non_decreasing_across_attempts(wrapper):
    """Millisecond resolution exists so two attempts can be ordered.

    Second resolution would tie on a retry, and a timestamp that cannot order
    two attempts on the same step is not much better than none.
    """
    for step in range(3):
        wrapper.attempt(worker_index=0, step_index=step, attempt=1,
                        prompt="p", call=FakeCall())
    stamps = [e["timestamp"] for e in wrapper.transcript.entries()]
    assert stamps == sorted(stamps)
    assert len(stamps) == 3


def test_replay_preserves_the_recorded_timestamp(wrapper, tmp_path):
    """A respawn must not restamp a decision it did not make.

    Replay reads the transcript rather than calling the model (§5), so the
    recorded time is when the ORIGINAL call happened. Re-stamping it would
    date a decision to the lifetime that merely re-read it.
    """
    wrapper.attempt(worker_index=0, step_index=0, attempt=1, prompt="p",
                    call=FakeCall())
    original = wrapper.transcript.entries()[0]["timestamp"]

    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    respawned = CallWrapper(run_id="r0", run_dir=tmp_path / "r0",
                            cumulative=counter)
    replayed = respawned.transcript.replay_index()[(0, 0)]
    assert replayed["timestamp"] == original
