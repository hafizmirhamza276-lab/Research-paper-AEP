"""The collection counter, under the conditions the harness actually creates.

**This counter is not bookkeeping. It is the budget control.** The
per-collection call cap and the USD ceiling in
``prompts/phase-40-agent-reachability.md`` §3 are both enforced from it, so a
counter that undercounts is a ceiling that does not exist. The stub stage found
it undercounting and `reports/phase-report-40-stub-stage-2026-09-17.md` §5
records the measurement: four writers, 800 increments, 202 counted.

The mechanism, established rather than assumed
(`reports/phase-report-40-counter-2026-09-18.md` §1):

* ``os.replace`` was never the problem. Every write landed whole; 1 200
  concurrent writes left a well-formed file and no temp files. The file was
  always valid and always wrong, which is why nothing caught it.
* ``add`` was an unserialised read-modify-write and nothing anywhere in
  ``planner.py`` took a lock of any kind.
* The loss does not scale with the read-write window, so it is not a narrow
  race. Four writers in a tight loop advance the counter by about one per
  round: the loss is systematically ``(writers - 1) / writers``. With the two
  workers the harness really uses, half of every collection's spend was
  invisible.

Four writers is not a stress test here. ``--workers 2`` is the collected
default and the runs are re-spawned after every crash, so two to four live
writers is the ordinary case, not the extreme.

`docs/25` R2: ``test_the_probe_detects_loss_when_it_is_injected`` is the
known-positive. A concurrency test that passed because it never actually
raced would be worth nothing.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from experiments.harness.planner import (
    CapExceeded,
    Caps,
    CumulativeCounter,
    Price,
)

ROOT = Path(__file__).resolve().parents[1]

#: What the harness really runs. ``experiments/run_matrix.py`` defaults to
#: ``--workers 2``; every collected run in ``experiments/results`` used 2, and
#: a crashed run has both the dying worker and its replacement briefly live.
HARNESS_WRITERS = 2

#: Enough to make a lost update near-certain if one is possible at all. The
#: original defect lost 598 of 800 at this width.
STRESS_WRITERS = 4


def _child(path: Path, count: int, *, tag: str, delay: float = 0.0,
           key_prefix: str = "") -> list[str]:
    """The command a writer process runs."""
    program = textwrap.dedent(
        f"""
        import sys, time
        sys.path.insert(0, {str(ROOT)!r})
        from pathlib import Path
        from experiments.harness.planner import CumulativeCounter
        counter = CumulativeCounter(Path({str(path)!r}))
        for index in range({count}):
            counter.add(1, 0.0, key=f"{key_prefix}{tag}-{{index}}")
            print(index, flush=True)
            time.sleep({delay})
        """
    )
    return [sys.executable, "-c", program]


def _run_writers(path: Path, writers: int, count: int) -> None:
    procs = [
        subprocess.Popen(_child(path, count, tag=f"w{n}"),
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for n in range(writers)
    ]
    for proc in procs:
        _, err = proc.communicate(timeout=180)
        assert proc.returncode == 0, err.decode()[-2000:]


# ---------------------------------------------------------------------------
# 1. Concurrent increments, at the width the harness really uses
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("writers", [HARNESS_WRITERS, STRESS_WRITERS, 8])
def test_no_increment_is_lost_under_concurrent_writers(tmp_path, writers):
    """The defect, stated as the property it violated."""
    path = tmp_path / "planner-cumulative.json"
    per_writer = 60
    _run_writers(path, writers, per_writer)

    counted = CumulativeCounter(path).read()["calls"]
    expected = writers * per_writer
    assert counted == expected, (
        f"{writers} writers x {per_writer} increments: expected {expected}, "
        f"counted {counted}, lost {expected - counted}. The collection cap and "
        f"the USD ceiling are read from this number."
    )


def test_the_probe_detects_loss_when_it_is_injected(tmp_path):
    """R2: the known-positive. Prove the test above can fail at all.

    A hand-rolled unserialised read-modify-write, run at the same width. If
    this does *not* lose increments, the harness is not really running the
    writers concurrently and the test above proves nothing.
    """
    path = tmp_path / "unserialised.json"
    CumulativeCounter(path).write(
        {"calls": 0, "usd": 0.0, "runs": 0, "voided": 0})
    program = textwrap.dedent(
        f"""
        import json, sys
        from pathlib import Path
        path = Path({str(path)!r})
        for _ in range(60):
            state = json.loads(path.read_text())
            state["calls"] += 1
            path.write_text(json.dumps(state))
        """
    )
    procs = [subprocess.Popen([sys.executable, "-c", program],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
             for _ in range(STRESS_WRITERS)]
    for proc in procs:
        proc.wait(timeout=180)
    counted = json.loads(path.read_text())["calls"]
    assert counted < STRESS_WRITERS * 60, (
        "the unserialised control did not lose a single increment, so this "
        "host is not actually running these writers concurrently and the "
        "concurrency tests above are vacuous"
    )


# ---------------------------------------------------------------------------
# 2 and 3. Crashes: a clean exception, and SIGKILL
# ---------------------------------------------------------------------------

def test_an_increment_survives_a_crash_immediately_after_it(tmp_path):
    """Durable when ``add`` returns, not when the process exits cleanly."""
    path = tmp_path / "planner-cumulative.json"
    program = textwrap.dedent(
        f"""
        import os, sys
        sys.path.insert(0, {str(ROOT)!r})
        from pathlib import Path
        from experiments.harness.planner import CumulativeCounter
        counter = CumulativeCounter(Path({str(path)!r}))
        counter.add(1, 0.25, key="survivor")
        os._exit(9)          # no flush, no atexit, no finally
        """
    )
    assert subprocess.run([sys.executable, "-c", program]).returncode == 9

    state = CumulativeCounter(path).read()
    assert state["calls"] == 1, (
        "an increment that had already returned was lost when the process "
        "died without unwinding"
    )
    assert state["usd"] == pytest.approx(0.25)


def test_sigkill_mid_flight_loses_nothing_and_double_counts_nothing(tmp_path):
    """What the harness actually injects.

    A writer is killed with SIGKILL while incrementing. Every increment whose
    ``add`` returned -- the child prints one line per completed call -- must be
    present exactly once. Nothing it had not yet reserved may appear.
    """
    path = tmp_path / "planner-cumulative.json"
    proc = subprocess.Popen(
        _child(path, 400, tag="killed", delay=0.002),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    # Let it get properly under way, then kill it without warning.
    time.sleep(1.2)
    os.kill(proc.pid, signal.SIGKILL)
    out, _ = proc.communicate(timeout=60)
    completed = len(out.decode().split())
    assert proc.returncode == -signal.SIGKILL
    assert completed > 5, "the child was killed before it did enough to prove anything"

    state = CumulativeCounter(path).read()
    assert state["calls"] >= completed, (
        f"{completed} increments returned, only {state['calls']} survived "
        f"SIGKILL"
    )
    assert state["calls"] <= completed + 1, (
        f"{completed} increments returned but {state['calls']} were counted; "
        f"an increment was double-counted"
    )


def test_sigkill_with_concurrent_writers_loses_nothing(tmp_path):
    """The two conditions together, which is how the harness runs."""
    path = tmp_path / "planner-cumulative.json"
    survivors = [
        subprocess.Popen(_child(path, 80, tag=f"s{n}", delay=0.004),
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        for n in range(HARNESS_WRITERS)
    ]
    victim = subprocess.Popen(
        _child(path, 400, tag="victim", delay=0.004),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)
    os.kill(victim.pid, signal.SIGKILL)
    victim_out, _ = victim.communicate(timeout=60)
    victim_done = len(victim_out.decode().split())

    survivor_done = 0
    for proc in survivors:
        out, _ = proc.communicate(timeout=180)
        assert proc.returncode == 0
        survivor_done += len(out.decode().split())

    assert survivor_done == HARNESS_WRITERS * 80
    counted = CumulativeCounter(path).read()["calls"]
    assert counted >= survivor_done + victim_done, (
        f"survivors completed {survivor_done} and the killed writer completed "
        f"{victim_done}, but only {counted} were counted"
    )
    assert counted <= survivor_done + victim_done + 1


# ---------------------------------------------------------------------------
# 4. The cap still fires at its boundary under concurrent load
# ---------------------------------------------------------------------------

def test_the_collection_cap_fires_at_its_boundary_under_load(tmp_path):
    """The property all of the above exists to protect.

    Writers race the counter up to one below the cap; the next attempt must be
    refused. Under the old implementation the counter never reached the cap at
    all, so the refusal never happened.
    """
    from experiments.harness.planner import CallWrapper

    path = tmp_path / "planner-cumulative.json"
    cap = 120
    writers = STRESS_WRITERS
    per_writer = (cap - 1) // writers
    _run_writers(path, writers, per_writer)

    counter = CumulativeCounter(path)
    reached = counter.read()["calls"]
    assert reached == writers * per_writer

    # Walk the remainder up to exactly the cap, then demand one more.
    wrapper = CallWrapper(
        run_id="boundary", run_dir=tmp_path / "run", cumulative=counter,
        caps=Caps(per_run_calls=10_000, per_collection_calls=cap),
    )

    def _noop(*, max_output_tokens):
        from experiments.harness.planner import Stop
        return Stop("noop")

    made = 0
    with pytest.raises(CapExceeded) as raised:
        for step in range(cap - reached + 5):
            wrapper.attempt(worker_index=0, step_index=step, attempt=1,
                            prompt="p", call=_noop)
            made += 1

    assert reached + made == cap, (
        f"the cap fired at {reached + made} rather than exactly {cap}"
    )
    assert "COLLECTION_CALL_CAP" in str(raised.value)


def test_the_usd_ceiling_is_read_from_the_same_number(tmp_path):
    """The ceiling is not a separate mechanism; it reads this counter."""
    path = tmp_path / "planner-cumulative.json"
    counter = CumulativeCounter(path)
    counter.add(1, 19.99, key="nearly-there")
    assert counter.read()["usd"] == pytest.approx(19.99)
    counter.add(1, 0.02, key="over")
    assert counter.read()["usd"] >= Caps().per_collection_usd


# ---------------------------------------------------------------------------
# Idempotency, which is what makes "none double-counted" mechanical
# ---------------------------------------------------------------------------

def test_the_same_key_counts_once_however_often_it_is_added(tmp_path):
    path = tmp_path / "planner-cumulative.json"
    counter = CumulativeCounter(path)
    for _ in range(5):
        counter.add(1, 1.5, key="one-call")
    state = counter.read()
    assert state["calls"] == 1
    assert state["usd"] == pytest.approx(1.5)


def test_a_torn_line_is_refused_rather_than_silently_dropped(tmp_path):
    """Consistent with the stance ``read`` already took: unreadable is not zero.

    A partial line can only come from a process killed mid-append. Dropping it
    would undercount and counting it would invent a number, so the counter
    refuses and the operator reconciles against the transcript.
    """
    path = tmp_path / "planner-cumulative.json"
    counter = CumulativeCounter(path)
    counter.add(1, 0.5, key="good")
    with counter.journal.open("a", encoding="utf-8") as handle:
        handle.write('{"key": "torn", "calls": 1, "us')
    with pytest.raises(CapExceeded, match="unreadable|malformed"):
        counter.read()


def test_an_unreadable_journal_is_not_read_as_zero(tmp_path):
    path = tmp_path / "planner-cumulative.json"
    counter = CumulativeCounter(path)
    counter.add(1, 0.5, key="good")
    counter.journal.write_bytes(b"\x00\x01 not json at all\n")
    with pytest.raises(CapExceeded):
        counter.read()


def test_an_absent_counter_is_zero(tmp_path):
    """The one case that legitimately reads as nothing spent."""
    state = CumulativeCounter(tmp_path / "planner-cumulative.json").read()
    assert state == {"calls": 0, "usd": 0.0, "runs": 0, "voided": 0}


# ---------------------------------------------------------------------------
# The line-size assumption the append rests on
# ---------------------------------------------------------------------------

def test_a_line_too_long_to_append_atomically_is_refused(tmp_path):
    """``O_APPEND`` is atomic up to a limit; past it the guarantee lapses.

    Measured on this host: 800 concurrent 201-byte appends arrived intact.
    Rather than trust that a key can never grow, the writer refuses a line it
    cannot promise to write in one piece.
    """
    counter = CumulativeCounter(tmp_path / "planner-cumulative.json")
    with pytest.raises(ValueError, match="too long"):
        counter.add(1, 0.0, key="k" * 4000)
