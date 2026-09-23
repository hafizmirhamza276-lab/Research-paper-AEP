# Known flaky tests

**This file exists so that a green suite is not the only thing an auditor sees.**
A test that fails once in a hundred runs and is never written down is
indistinguishable, later, from a test that never failed. Each entry records
what was observed, what was ruled out, and what would be needed to diagnose it.

**No entry here is a fix, and none should be read as one.** A flake that has
not been diagnosed may be a real defect that is hard to reproduce.

| status | meaning |
|---|---|
| **open** | observed, not diagnosed |
| **diagnosed** | cause established, with the evidence |
| **fixed** | cause removed, with the commit |

---

## 1. `test_sigkill_with_concurrent_writers_loses_nothing`

**Status: open.** Observed once, 2026-09-23.

`tests/test_cumulative_counter.py::test_sigkill_with_concurrent_writers_loses_nothing`

### What was observed

One failure, in a full-suite run during the phase-52 spelling pass:

```
FAILED tests/test_cumulative_counter.py::test_sigkill_with_concurrent_writers_loses_nothing
1 failed, 2667 passed, 34 skipped, 1 warning in 964.58s (0:16:04)
```

### What is known

| | |
|---|---|
| reproduced? | **no** |
| in isolation | **5 consecutive passes**, plus one run of the whole file (14 passed) |
| on a full-suite re-run | **2668 passed, 34 skipped, 0 failed** |
| changed by the session that saw it? | **no** |

`git diff a8fb63b~5..a8fb63b -- experiments/ aep_core/ tests/test_cumulative_counter.py`
is **empty**. The phase-52 work touched the abstract, the eleven manuscript
files, `scripts/paper_tables.py`, `scripts/build_paper.sh` and two new files
under `scripts/` and `tests/`. It touched nothing this test imports.

### What is NOT known, and this is the important part

**The failing assertion was not captured.** The run was piped through `tail`,
so only the summary line survived; the traceback naming which of the test's
four assertions failed is gone. Without it the cause cannot be narrowed, and
everything below is a list of candidates rather than a diagnosis.

### What the test does

```python
# HARNESS_WRITERS is 2, the width the agent harness really runs at.
survivors = [Popen(_child(path, 80, tag=f"s{n}", delay=0.004)) for n in range(HARNESS_WRITERS)]
victim    =  Popen(_child(path, 400, tag="victim", delay=0.004))
time.sleep(1.0)
os.kill(victim.pid, signal.SIGKILL)
...
assert survivor_done == HARNESS_WRITERS * 80                    # (1)
assert counted >= survivor_done + victim_done                   # (2)
assert counted <= survivor_done + victim_done + 1               # (3)
```

Each child does `counter.add(...)` then `print(index, flush=True)`, so
`victim_done` is counted from the victim's flushed stdout and `counted` from
the journal on disk.

### Candidates, in the order worth checking

1. **Assertion (3), the over-count tolerance.** The journal design appends a
   reservation *before* dispatch, so a kill leaves an entry with no stdout
   line. The tolerance for that is exactly **one**. If a `SIGKILL` can leave
   *two* journal entries unaccounted for in stdout, (3) fails while the
   property the test is named for — that nothing is *lost* — still holds.
   **This is the candidate that would make the failure benign**, and it is a
   defect in the test's accounting rather than in `CumulativeCounter`.
2. **Assertion (1), under load.** `HARNESS_WRITERS` is **2**, so two survivors
   must each complete 80 writes within `communicate(timeout=180)`. A full-suite
   run is the only context in which this has ever failed, and it is the context
   with the most contention.
3. **Assertion (2), a genuinely lost increment.** This would be the defect the
   test exists to catch, and the one the handoff of 2026-09-18 records as
   having been real once: `CumulativeCounter.add` lost 598 of 800 increments
   under concurrency before the append-only journal replaced it. **It cannot
   be ruled out from the evidence available.**

**Stdout buffering was considered and ruled out**: the child passes
`flush=True` on every `print`, so a lost buffer is not the mechanism.

### What would be needed to diagnose it

1. **Run the full suite with `-rf --tb=long` and keep the whole output**, not a
   `tail`. One recurrence with the assertion named separates candidate 1 from
   candidate 3, and that is the whole question.
2. **Run the test in a loop under artificial load** — the suite's own duration
   suggests contention matters — with the journal preserved on failure.
3. **If it is candidate 1**, the fix is in the test: count the victim's
   completions from the journal rather than from its stdout, or widen the
   tolerance to the number of in-flight reservations a kill can strand, and say
   which in a comment.

### Why it is not being fixed now

Instructed not to attempt a fix. And the right first step is evidence, not a
patch: widening assertion (3) would silence candidate 1 **and** candidate 3
together, which is the wrong trade for the one test that stands between this
project and a repeat of the counter defect it was written for.

**It must stay visible.** `experiments/harness/planner.py`'s counter is what
bounds live spend in the agent experiment, and this is its only concurrency
test under a real kill.
