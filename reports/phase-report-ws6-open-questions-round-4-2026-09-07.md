# WS-6 open questions, round 4: one uninterrupted run; Q4 closed, Q2b blocked on a missing instrument

**No data collected**, no run directory written, `analyse_b5_agreement.py` not
written, and **the pre-registration not changed.**

The run completed end to end and tore itself down cleanly. Two items closed, one
open for a reason that was not previously visible.

---

## Q4 — point 6's race on loopback: **CLOSED, and it is observable**

```
point 6   trials=8  reached=8  fired=8  after_provider_call=8  voids=0
```

Eight of eight. The worker reached `DURING_COMPLETE_RPC`, the kill fired, and in
every trial the provider had already been called — which is the whole content of
the question: the kill lands *after* the provider answered and *during* the
completion RPC.

**`B5_SEMANTICS.md` §2.1 stays at `approximate`, which is now positive evidence
rather than an unexamined default.** The mapping is not downgraded to absent, so
the cost I recorded in advance — B5 crashable at only four of six points, missing
both `*_before_barrier` positions, reducing the comparison to agreement where
neither engine has a durability window to be cut in — **is not incurred.**

What stays true is the *other* half of §2.4: the window's width is set by the
server and the loopback, not by anything the harness controls, so a rate measured
at point 6 is still not like-for-like with B4's fsync-width window. That was
never in question here and is unchanged.

## Q5c — the crash points: **4 of 5**, up from 3

| point | reached | fired | provider called |
|---|---|---|---|
| `BEFORE_SCHEDULE_ACTIVITY` | yes | yes | 0 (expected — dies before the activity) |
| `ACTIVITY_ENTERED_BEFORE_CALL` | yes | yes | 0 (expected) |
| `DURING_PROVIDER_CALL` | yes | yes | 0 (expected — dies inside the call) |
| `AFTER_RESPONSE_BEFORE_RETURN` | **no** | no | **0** |
| `DURING_COMPLETE_RPC` | yes | yes | 1 |

`DURING_COMPLETE_RPC` is now demonstrated, and independently again in Q4's eight
trials.

**`AFTER_RESPONSE_BEFORE_RETURN` remains undemonstrated at n=1**, and its
`provider_calls=0` says why: no response arrived, so a point defined as *after
the response* was never reached. The provider injects a 15% timeout and a 5%
server error, so roughly one trial in five cannot reach this point by
construction. **That is a plausible explanation, not a demonstrated one** — one
trial is not enough to distinguish "unlucky draw" from "unreachable", and it is
not being claimed either way. It needs the same n=8 treatment Q4 got.

**The gate voided it rather than reporting it**, which is the third time this run
that the gate caught a run that would otherwise have been recorded as a
`PENDING_AT_DEADLINE` measurement.

## Q2b — the retry-lands measurement: **OPEN, and the blocker is now identified**

```
start_to_close=2500ms   PENDING_AT_DEADLINE  settled=False  elapsed_s=150.01  calls=0
start_to_close=4000ms   PENDING_AT_DEADLINE  settled=False  elapsed_s=150.01  calls=0
start_to_close=8000ms   PENDING_AT_DEADLINE  settled=False  elapsed_s=150.01  calls=0
```

Identical at all three timeouts, with **zero provider calls**, which is the
diagnostic: the retry never ran, so no timeout value was ever exercised.

**The cause is a missing instrument, not a property of Temporal.** `run_one`
starts one worker, the injector kills it, and **nothing respawns it**. Temporal
schedules the retry correctly; there is no worker left to poll for it. The
measurement is therefore of my harness, not of the engine.

### This does NOT establish that H1 is untestable

The instruction was to stop and report if q2b established that, and to leave the
hypothesis alone. **It did not establish it.** What it establishes is that the
B5 instrument lacks worker respawn — and the pre-registration is unchanged, as it
should be, because nothing was learned about H1 at all.

**It is also a real and non-obvious finding for WS-6.** B4's harness respawns a
worker after `SIGKILL`; that is precisely what makes replay observable. B5 needs
the equivalent supervisor — kill, then bring a fresh worker back to the same task
queue — and until it has one, *no* B5 cell can measure a duplicate, because a
duplicate is by definition something the second attempt does. This is a
prerequisite for collection that none of the four previous rounds surfaced, and
it belongs in `B5_SEMANTICS.md` before any collection.

## Q3 — **OPEN**, blocked on Q2b, unchanged.

## Q2a — reproduced

`n=30 answered=22 timed_out=3 refused={503: 5} p50=2013.0 ms p95=2019.0 ms`,
against round 2's `p50=2015.0 / p95=2024.2`. Independent agreement to ~2 ms, and
still matching the configured 2.0 s / 15% / 5% profile.

## Q5b — the gate, reproduced

`rule 13 both branches satisfied=True` again, with branch A silent and branch B
voiding on the injector. Closed in round 3; re-confirmed here at no extra cost.

---

## R1 applied to my own scripts

`pkill -f experiments.mock_api` killed the live provider mid-run last round —
controlling a process by pattern, which **R1 forbids** and which R12 exists for
from the other direction.

Every pattern-based kill in the run path is gone. `b5_final_run.sh` records the
PID of everything it starts (`provider`, `sampler`, `events`) at start, in a file,
and kills **only those PIDs** at teardown, reporting `already gone` when one has
exited. There is no `pkill` and no "kill whatever holds the port" anywhere in it.

**This is the fourth time this session a rule has been broken inside its own
scope**, and the pattern is now consistent enough to name plainly:

| rule | broken by |
|---|---|
| R13 (a gate must be able to fail) | its own proof script, which asserted on a re-run rather than the output it showed |
| R14 (checkers report three outcomes) | the probe written to close WS-6, twice |
| R14 again | an inline teardown check that lost `$P` to the WSL bridge and printed three bare `HELD` lines |
| **R1 (never control a process by pattern)** | **the probe's own cleanup, which killed the live provider** |

The through-line is the same one R14 names: the supporting code — proofs,
cleanups, verification — is written to a lower standard than the code it
supports, and it is the supporting code that decides what gets believed.

## R12a: observers ran, and nothing happened

`docker events` streamed from **before** bring-up, plus a 10-second stack
sampler. Result: **5 lifecycle events, all from bring-up**, and both containers
reporting `Up 21 minutes (healthy)` at teardown. **No unexplained restart in this
run.**

That is not an explanation — R12a's four occurrences stand — but it is the first
run of this pass with no interference from me, and it is also the first with no
disappearance. Recorded as a correlation of one, not chased. The observers are
now part of the run script, so a fifth occurrence will be identifiable rather
than merely noticed.

---

## Teardown

R8a — evidence preserved first: `findings-final-run.json`, the observer
directory (docker events, stack samples, up/down logs), the Temporal server log.

R8 / R8b / R12 — verified **from the script file**, not inline:

```
ws6 containers left      : 0
port 7233 / 8233 / 8099  : free / free / free
redis-data volume present: 1
```

`compose down` without `-v`; the provider and both observers killed by recorded
PID.

---

## Status

| Item | Status |
|---|---|
| Q4 point 6 race | **CLOSED** — observable 8/8; mapping stays `approximate`, the second-absent-point cost is not incurred |
| Q5c crash points | **4 of 5** — `AFTER_RESPONSE_BEFORE_RETURN` undemonstrated at n=1, needs n=8 |
| Q2b retry lands | **OPEN** — blocked on a missing worker respawn; does **not** show H1 untestable |
| Q3 deadline | **OPEN** — blocked on Q2b |
| Q2a distribution | reproduced, p50 2013.0 ms |
| Q5b gate | reproduced, rule 13 satisfied |

**WS-6 remains not ready to collect**, and the remaining work is now smaller and
better specified than at any previous round: a worker supervisor that respawns
after the kill, then Q2b and Q3, then eight trials at
`AFTER_RESPONSE_BEFORE_RETURN`.
