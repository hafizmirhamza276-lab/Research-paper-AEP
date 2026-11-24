"""The run log: ``results/<run_id>/events.jsonl``.

Amendment C4 promotes this file from telemetry to evidence. The paper's counts
are cross-checked between it and the mock API's SQLite ledger
(``experiments/harness/reconcile.py``), and a disagreement between the two is a
bug rather than something to reconcile in prose. Three consequences.

**Flushed on write.** The harness exists to SIGKILL the processes writing this
file. A record still sitting in a Python buffer when the process stops existing
is a record about the very execution the run was collected to study. Every
:meth:`EventLog.emit` therefore flushes.

    ``fsync`` is deliberately *not* called. The failure model injected here is
    process death, and a ``write`` that has reached the kernel survives that
    without an ``fsync``; only host power loss needs one. The mock API's ledger
    does call ``fsync`` (``synchronous=FULL``) because it is the ground truth
    and pays for the stronger claim. This file matches its threat model instead
    of overpaying, and says so.

**Both clocks, and a way to relate them.** ``wall_ms`` is the only stamp
comparable across processes, and is what the merged timeline is ordered by;
``monotonic_ns`` is the only stamp that cannot jump backwards inside a process,
and is what durations are computed from. They are not comparable to each other,
so every log opens with a ``clock_reference`` record pairing the two at a known
instant -- which is what lets a reader convert one worker's monotonic interval
onto the shared wall timeline without pretending the conversion was free.

**Shards, then a merge.** Processes write their own file
(``events-<source>.jsonl``); the runner merges them into ``events.jsonl`` at
the end. Appending from many processes to one file would be atomic only below
``PIPE_BUF`` on POSIX and is not guaranteed at all on Windows, and a harness
that corrupted its own evidence under load would be worse than useless.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

#: Written by :class:`EventLog` itself. A payload field may not shadow one:
#: the record would then mean different things depending on dict ordering.
RESERVED_FIELDS = frozenset(
    {
        "event",
        "run_id",
        "source",
        "pid",
        "seq",
        "wall_ms",
        "wall_iso",
        "monotonic_ns",
    }
)

#: Shard files the merge collects. ``events.jsonl`` itself is excluded.
SHARD_GLOB = "events-*.jsonl"
MERGED_NAME = "events.jsonl"


def _wall_iso(wall_ns: int) -> str:
    return datetime.fromtimestamp(wall_ns / 1e9, tz=timezone.utc).isoformat()


class EventLog:
    """One process's append-only shard of a run's timeline."""

    def __init__(self, path: Path | str, *, run_id: str, source: str) -> None:
        self.path = Path(path)
        self.run_id = run_id
        self.source = source
        self._seq = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")
        self._emit_clock_reference()

    # -- writing -----------------------------------------------------------

    def _emit_clock_reference(self) -> None:
        """Pin this process's monotonic clock to the shared wall clock."""
        self.emit(
            "clock_reference",
            wall_ns=time.time_ns(),
            monotonic_ns_at_reference=time.monotonic_ns(),
            platform=os.name,
        )

    def emit(self, event: str, /, **fields: Any) -> dict[str, Any]:
        """Append one record and flush it. Returns the record as written.

        ``event`` is positional-only so that ``emit("tick", event="x")`` lands
        in ``fields`` and is refused by the shadowing guard below, rather than
        raising a bare ``TypeError`` about duplicate arguments.
        """
        shadowed = sorted(RESERVED_FIELDS & set(fields))
        if shadowed:
            raise ValueError(
                f"payload field(s) {shadowed} would shadow a reserved record "
                "field; rename them"
            )

        record = {
            "event": event,
            "run_id": self.run_id,
            "source": self.source,
            "pid": os.getpid(),
            "seq": self._seq,
            "wall_ms": time.time_ns() // 1_000_000,
            "wall_iso": _wall_iso(time.time_ns()),
            "monotonic_ns": time.monotonic_ns(),
            **fields,
        }
        # Serialise before touching the file: a payload that cannot be encoded
        # must fail at the call site, not leave a half-written line behind.
        line = json.dumps(record, sort_keys=True)
        self._handle.write(line + "\n")
        self._handle.flush()
        self._seq += 1
        return record

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.flush()
            self._handle.close()

    def __enter__(self) -> "EventLog":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# ===========================================================================
# Reading and merging
# ===========================================================================


def read_events(
    path: Path | str, *, tolerate_truncated_tail: bool = True
) -> list[dict[str, Any]]:
    """Parse one JSONL file.

    A worker killed mid-``write`` can leave a partial final line. That is an
    expected artifact of the experiment, not corruption, so by default the
    trailing partial line is dropped and everything before it is kept. Any
    *other* unparseable line raises, naming the file: silently skipping it
    would quietly lower a count the paper reports.
    """
    source = Path(path)
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    records: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError as error:
            is_final = index == len(lines) - 1
            if is_final and tolerate_truncated_tail:
                break
            raise ValueError(
                f"{source.name} line {index + 1} is not valid JSON: {error}"
            ) from None
    return records


def _ordering_key(record: dict[str, Any]) -> tuple[int, str, int]:
    return (
        int(record.get("wall_ms", 0)),
        str(record.get("source", "")),
        int(record.get("seq", 0)),
    )


def merge_event_shards(
    directory: Path | str, *, output: Path | str | None = None
) -> int:
    """Merge every ``events-*.jsonl`` shard into one wall-ordered timeline.

    Returns the number of records written. The output file is excluded from
    the input glob, so re-running a merge is idempotent rather than doubling.
    """
    root = Path(directory)
    destination = Path(output) if output is not None else root / MERGED_NAME

    records: list[dict[str, Any]] = []
    for shard in sorted(root.glob(SHARD_GLOB)):
        if shard.resolve() == destination.resolve():
            continue
        records.extend(read_events(shard))

    records.sort(key=_ordering_key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
    return len(records)


def events_of(records: Iterable[dict[str, Any]], event: str) -> list[dict[str, Any]]:
    """Every record of one type, in timeline order."""
    return [record for record in records if record.get("event") == event]
