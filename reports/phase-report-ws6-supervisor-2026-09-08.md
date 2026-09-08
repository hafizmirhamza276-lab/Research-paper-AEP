# WS-6: the worker supervisor, and the last open questions

**No data collected**, no run directory written, `analyse_b5_agreement.py` not
written, and **the pre-registration not changed** — it did not need to be.

One uninterrupted run. Every remaining item closed with evidence.

---

## The supervisor

### Where the shape was read from

`experiments/harness/runner.py:201`, `run_worker_slot` — *"Run one worker slot to
completion, respawning it after each crash."* Three properties were carried
across deliberately, and one was deliberately left behind.

**Carried:**

1. **A bounded attempt loop.** B4 uses `MAX_ATTEMPTS_PER_WORKER = 64`
   (`runner.py:97`) and raises `RunAborted` on exhaustion. B5 uses
   `MAX_LIFETIMES = 6`, smaller because a B5 run injects exactly one fault, and
   exhaustion is a void rather than a result.
2. **The fault is armed on attempt 1 only.** `runner.py:244`: *"The kill fires
   once per run. A respawned worker must not carry it, or a system whose
   supervisor re-executes would kill Redis once per lifetime while a system that
   does not would kill it once."* **This is the reason to copy the shape rather
   than invent one.** A B5 that re-armed every lifetime would produce duplicates
   by a different mechanism than B4 — which is exactly the confound this baseline
   exists to remove.
3. **Every lifetime recorded**, spawn and exit, with its attempt number, on the
   same trace the gate reads.

**Deliberately not carried:** B4's supervisor computes `from_index` and tells the
respawned worker where to resume, because B4's harness owns the resume policy.
**B5 must not.** What to re-execute is the engine's decision and is the thing
under measurement; the B5 supervisor guarantees only that a worker exists.

### Rule 13, both directions — **satisfied**

```
A respawn ON    COMPLETED                        void=False  deaths=1  respawns=1  calls=2  settled=True
B respawn OFF   VOID_SUPERVISOR_NEVER_RESPAWNED  void=True   deaths>0  respawns=0  calls=0
    reason: the fault was delivered at 'ACTIVITY_ENTERED_BEFORE_CALL' and the
            worker died, but no worker was respawned: the engine's retry had no
            worker to poll, so this run measures the supervisor and not the
            engine. NOT a deadline result.
rule 13 supervisor  satisfied=True
```

**Branch A** is the whole point: the worker was killed, a new one came back, the
engine's retry ran on it, and `calls=2` — **the provider was called twice.** That
is the duplicate mechanism this baseline exists to measure, working for the first
time in WS-6.

**Branch B** is the branch that mattered most, and it behaves as required: a
missing respawn now **voids naming the supervisor**, where before it was
indistinguishable from a legitimate `PENDING_AT_DEADLINE`. The new verdict
`VOID_SUPERVISOR_NEVER_RESPAWNED` is that distinction.

---

## Q2b — the retry lands: **CLOSED, and H1 is testable**

Redone with the supervisor in place:

| Start-To-Close | verdict | elapsed | provider calls | deaths | respawns |
|---|---|---|---|---|---|
| 2500 ms | **COMPLETED** | 25.35 s | **2** | 1 | 1 |
| 4000 ms | **COMPLETED** | 23.94 s | 1 | 1 | 1 |
| 8000 ms | **COMPLETED** | 26.67 s | 1 | 1 | 1 |

Against the previous round's identical `PENDING_AT_DEADLINE` at 150 s with **zero**
provider calls at all three values. The difference is the supervisor and nothing
else.

**H1 is testable as pre-registered.** The retry lands, it lands within ~24–27 s,
and at 2500 ms the provider was called twice — a caller-caused duplicate, which
is precisely the quantity H1 predicts B5 will reproduce from B4. The hypothesis
was not adjusted and did not need to be.

**A timeout value can now be chosen on evidence.** It must clear the measured
provider p95 (~2.03 s this run, ~2.02 s in round 2), and all three candidates
above completed. The tightest, 2500 ms, is the one that produced the duplicate,
because it expires soonest after the crash. That is a collection-design choice
for the pre-registered cell and is recorded, not made here.

## Q3 — the 120 s recovery deadline: **CLOSED**

The pre-registered deadline is 120 s. The retry completes in **23.94–26.67 s**,
about a fifth of it. The deadline accommodates the timeout comfortably, it does
not need to move for B5's cells, and B5's runs therefore stay directly comparable
to B4's frozen ones — the concern recorded as open question 3 is answered in the
favourable direction.

## Q5c — all five crash points: **CLOSED**

`AFTER_RESPONSE_BEFORE_RETURN` given the n=8 treatment Q4 got:

```
trials=8  reached=6  fired=6  with_provider_call=6  voids=2
```

**6 of 8, and the 2 are explained rather than excused.** The provider injects 15%
timeouts and 5% server errors, so ~20% of trials cannot reach a point defined as
*after the response* — no response arrives. Expected reachable ≈ 6.4 of 8;
observed 6. The two unreachable trials were **voided by the gate**, not reported
as deadline results.

At n=1 this point told nothing either way. At n=8 it is demonstrated.

Final tally, all five demonstrated:

| point | status |
|---|---|
| `BEFORE_SCHEDULE_ACTIVITY` | demonstrated |
| `ACTIVITY_ENTERED_BEFORE_CALL` | demonstrated |
| `DURING_PROVIDER_CALL` | demonstrated |
| `AFTER_RESPONSE_BEFORE_RETURN` | **demonstrated, 6/8** |
| `DURING_COMPLETE_RPC` | demonstrated, and 8/8 again in Q4 this run |

Q4 re-ran and reproduced: `trials=8 reached=8 fired=8 after_provider_call=8
voids=0`.

---

## Two defects in the instrument, found and recorded

**1. `worker.err` is appended across runs and never truncated.** A stale
`httpx.ConnectError` from a previous round was visible in it during this run and
could have been attributed to this one. It was not, only because the provider's
liveness was checked directly (`/v1/health` → 200) instead of inferred from the
log. **R14's shape again**: a log that cannot say which run a line belongs to
cannot report "I could not tell". Should be truncated per run.

**2. `deaths` is over-counted when respawn is disabled.** Branch B reported
`deaths=232` because `maintain()` increments on every poll while the worker stays
dead, rather than counting distinct deaths. It does not affect any verdict — the
gate tests `deaths > 0` — but the number as printed is wrong and should not be
quoted as a count of anything.

Both are recorded here rather than fixed, per rule 12.

**Also observed:** two runs early in the sequence reported
`VOID_WORKER_NEVER_READY` on a cold start. The gate voided them correctly rather
than reporting a result. Worker start-up time against the 20 s ready timeout is
worth raising before collection, since a cell that voids 2 runs in 30 for
start-up reasons is losing power for an avoidable reason.

## R12a — observers ran, nothing happened, again

`docker events` streamed from before bring-up plus a 10 s stack sampler:
**5 lifecycle events, all bring-up**, both containers `Up 16 minutes (healthy)` at
teardown. **No unexplained restart.**

That is now two consecutive clean runs, both of which were also runs I did not
interfere with. **Still a correlation, not an explanation** — R12a's four
occurrences stand and are not withdrawn.

## R1 — teardown by recorded PID

Every process this run started was killed by a PID recorded at start:

```
killed provider pid 1517
killed sampler  pid 786
killed events   pid 766
```

No `pkill`, no pattern matching, no "kill whatever holds the port" anywhere in
the run path.

## Teardown

R8a — evidence preserved first: `findings-final-run.json`, the observer directory,
the Temporal server log. R8 / R8b / R12 — **verified from the script file**:

```
ws6 containers left      : 0
port 7233 / 8233 / 8099  : free / free / free
redis-data volume present: 1
```

`compose down` without `-v`.

---

## Status

| Item | Status |
|---|---|
| Worker supervisor | **BUILT**, B4's shape, and **rule 13 satisfied both directions** |
| Q2b retry lands | **CLOSED** — 24–27 s, all three timeouts; **H1 is testable** |
| Q3 120 s deadline | **CLOSED** — accommodates it with ~4× margin |
| Q5c five crash points | **CLOSED** — all five demonstrated; the last at 6/8 |
| Q4 point 6 race | reproduced 8/8 |
| Q1, Q5a, Q5b | closed previously, unchanged |

**All five of the pre-registration's open questions are now closed.** WS-6's
remaining prerequisites before collection are the two instrument defects above
and the timeout choice — none of which is an open question about the engine.
