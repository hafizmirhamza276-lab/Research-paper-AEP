# The collection counter — what was actually wrong, and what replaced it

The stub stage found `planner-cumulative.json` reading 23 where the six
transcripts held 24 (`phase-report-40-stub-stage-2026-09-17.md` §5). One call
in twenty-four is easy to read as a rounding nuisance. It is not. The
per-collection call cap and the USD 20 ceiling of
`prompts/phase-40-agent-reachability.md` §3 are both enforced from that number,
so an undercount is not a reporting error — it is a ceiling that does not
exist.

This report is §1: the mechanism, established rather than assumed. §2 is the
fix and why that mechanism and not another. §3 is what pins it.

---

## 1. The mechanism

Four candidates were named before any of them was tested: a lost update between
read and write, non-atomic file replacement, no locking across processes, or
something else. Three turned out to be wrong and the fourth was bigger than the
name suggested.

### 1.1 `os.replace` was never the problem

The first implementation's docstring was about crash-safety — a temp file and
`os.replace` "so a crash between writes leaves either the old state or the new
one, never a truncated file". That part worked, on both filesystems the harness
can land on:

```
  1 200 concurrent writes  ->  file parses: True
                               leftover temp files: 0
```

**The file was always well-formed and always wrong.** That is why nothing
caught it for as long as it lasted: every inspection of the artifact showed a
valid counter, and validity was the only thing anything checked.

### 1.2 The read-modify-write was unserialised, and nothing took a lock

`add` was `read()`, mutate, `write()`. Searching the module for every locking
primitive that could have made that safe:

| `fcntl` | `flock` | `lockf` | `msvcrt` | `LockFile` | `filelock` | `portalocker` | `O_EXCL` |
|---|---|---|---|---|---|---|---|
| absent | absent | absent | absent | absent | absent | absent | absent |

### 1.3 It is not a narrow race, and that is the part that matters

A lost update is usually described as a race you lose occasionally — a small
window, rarely hit. This is not that, and the difference decides which fix is
adequate.

Widening the window between the read and the write changes nothing:

```
  gap=0ms    4 writers x 50  ->  expected 200, counted 51
  gap=1ms    4 writers x 50  ->  expected 200, counted 50
  gap=5ms    4 writers x 50  ->  expected 200, counted 50
```

The loss does not scale with the window because the window is not the
mechanism. Writers in a loop advance the counter by roughly **one per round**
regardless of how many of them there are: each reads the same value and writes
that value plus one. So the loss is systematic, and it is a function of the
number of writers:

```
  2 writers x 60  ->  expected 120, counted  69, lost  51   (42%)
  4 writers x 60  ->  expected 240, counted  64, lost 176   (73%)
```

Two writers is not the stress case. `experiments/run_matrix.py` defaults to
`--workers 2`, every run under `experiments/results` used 2, and a crashed run
has the dying worker and its replacement both briefly live. **Something close
to half of every collection's spend would have been invisible**, and it gets
worse, not better, if the collection is ever widened.

### 1.4 A second defect the first one was hiding

`CallWrapper.attempt`'s docstring says:

> Count, cap, invoke, price, record. In that order.
> Capping *before* invoking is what makes the ceiling real: a cap checked
> afterwards has already paid for the call it refuses.

The code capped, invoked, and then counted in the `finally` — after the call
had returned. The docstring was right about the principle and the code did not
implement it. A worker `SIGKILL`ed between the request going out and the
increment landing had made a paid call that nothing recorded.

The harness injects `SIGKILL` by design. This was not a corner case; it was the
crashed regime, which is the entire experiment.

### 1.5 The two together make the cap fire late while appearing to work

This is the part that would have been hardest to catch afterwards. Walking the
counter to a cap of 120 with four writers and then demanding calls until
refused:

```
  writers reached      41   (they had actually made 116)
  wrapper then made    79   (it should have made 4)
  cap fired at        120   the boundary, exactly
  calls really made   195
```

A probe would report that the cap fired at precisely its boundary. The
collection would have spent 60% more than the ceiling it was reporting against.
An error that announces itself as correct is worse than one that crashes.

---

## 2. The fix

**One append-only journal line per increment. The total is the sum.**

A single `os.write` to a file opened `O_APPEND` is atomic, so two writers
cannot interleave within a line and neither can overwrite the other's.
Measured on this host rather than assumed from the standard, on both
filesystems a collection can write to:

```
  /mnt/d  (DrvFs)   800 concurrent appends of 201 bytes  ->  800 intact
  /var/tmp (ext4)   800 concurrent appends of 201 bytes  ->  800 intact
```

### 2.1 Why not a lock

`fcntl.flock` does work here — verified across processes on both filesystems,
`['held', 'blocked']` — and the kernel releases it when a holder dies, which is
the property a crash-injecting harness needs. It was still the wrong choice.

A lock serialises the read-modify-write; it does not remove it. A writer that
takes the lock, reads, and is then `SIGKILL`ed before writing still loses its
increment. Locking makes the counter correct under concurrency and leaves it
wrong under the exact fault this harness spends its whole time injecting.

**An append has no window to be killed in.** It is also the idiom this
repository already uses everywhere else for the same reason: every event log
here is a jsonl append.

### 2.2 What each line carries, and why

* **A `key`.** The total counts a key once however many times it is appended.
  That is what makes "none double-counted" mechanical rather than a promise
  about call sites — and it is load-bearing for replay, where a respawned
  worker re-walks steps that were already decided.
* **`run_id`.** `runs` and `voided` are derived from the distinct run ids in
  the journal rather than kept as separate integers, so they cannot drift from
  what happened. This is defect C's fix: those two fields were previously
  initialised, written, read, and never incremented.

### 2.3 Reserve before dispatch, settle after

The reservation is appended **before** the call goes out. The real cost is not
known until it returns, so the reservation is priced at the most §3 permits one
call to cost — 2 000 input and 1 024 output tokens, $0.0016288 — and the
difference is settled afterwards under a second key.

The error direction is chosen, not incidental. A worker killed between the
reservation and the settle leaves the collection **over**-counted, which ends it
early. The other order spends money nobody counted.

`Caps` gains `max_prompt_tokens = 2000` to express this. That is not new
policy: §3's ceiling is already calculated from "1 000 attempts × (≤2 000 input
+ ≤1 024 output)". It is named because the reservation has to price a call it
has not made yet. **Nothing the pre-registration fixed has changed** — it
requires the cumulative counter be "persisted to disk" and the per-run counter
be "written into the run directory", and both still are. No amendment.

### 2.4 A partial line is refused, not dropped

It can only come from a writer killed mid-append. Dropping it would undercount;
counting it would invent a number. `read` raises — the same stance the first
implementation already took for an unreadable file, kept for the same reason.

### 2.5 What happened to `planner-cumulative.json`

Still written, now **derived**: re-derived in full from the journal on every
append, so a clobbered one self-heals, and marked `"_authoritative": false`
because nothing reads it back.

This is a real change in what is protected, and it is asserted rather than left
implied. Corrupting that file used to have to be refused, because it was the
authority. It is now harmless, because it is not an input to any decision.
"We stopped checking that file" and "that file stopped mattering" look
identical in a diff, so there is a test for each.

### 2.6 Defect A, in the same file

`CallWrapper.__init__` constructed `RunBudget(calls=0)` and wrote it straight
over what the first attempt had recorded. Every run's `planner-budget.json`
read `calls: 0` beside a transcript holding four entries: last writer wins, and
the last writer — which replays and therefore calls nothing — always had
nothing to report.

The budget is now rebuilt from the transcript, which is already the durable
record of what was spent. The consequence was worse than the wrong number in a
file: **the per-run cap reads that same counter**, so a respawned run got a
fresh 36 calls per attempt. At `p(crash)=1.0` it bounded nothing.

---

## 3. What pins it

`tests/test_cumulative_counter.py`, 14 tests. The four the brief asked for:

| | |
|---|---|
| concurrent writers at the width the harness runs | 2, 4 and 8 writers, no loss |
| a crash between read and write | durable across `os._exit` with no unwinding |
| the same under `SIGKILL` | nothing lost, nothing double-counted, with other writers live |
| the cap at its boundary under load | writers race to `cap - 1`, the next is refused |

`test_the_probe_detects_loss_when_it_is_injected` is `docs/25` R2's
known-positive: a hand-rolled unserialised read-modify-write at the same width.
A concurrency test that passed because the writers never actually overlapped
would be worth nothing, and this is what stops that passing silently.

Each defect was then put back **with the signature kept**, so the tests fail on
the property rather than on a `TypeError` — a test that errors on a missing
keyword proves nothing about a race:

```
  baseline                                              68 green
  unserialised read-modify-write                        18 red
  run budget reset on respawn                            3 red
  runs / voided not derived                              1 red
  count after the call again                             6 red
  a repeated key counted twice                           2 red
  restored, byte-identical                              68 green
```

Full suite 2 263 passed, 34 skipped.

---

## 4. What this cost, and what it would have cost

Nothing. The stub stage runs at zero calls, and every measurement above was
made with no `.env`, no key and no network.

Had the stage not existed, the first evidence of any of this would have been
the invoice — and because §1.5 makes the cap appear to fire exactly on its
boundary, the run directories would have said the ceiling held.
