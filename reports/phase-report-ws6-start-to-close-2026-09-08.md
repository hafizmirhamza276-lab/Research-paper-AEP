# WS-6: fixing the Start-To-Close timeout, before any B5 data exists

**The last free parameter in this cell.** A value chosen after seeing runs is a
fitted parameter however well argued, so it is fixed and committed here, before
collection, exactly as `d8b2ca5`'s ordering requires of the pre-registration
itself.

---

## The measurements it rests on

All from the probe passes, on the real stack, against the same provider
configuration the collection will use (2.0 s constant delay, 15% injected
timeout, 5% injected server error — read from the WS-4 collection's own
`mock-api.yaml`, not invented).

**Provider response time**, three independent samples of n=30:

| round | p50 | p95 | answered | timed out | 503 |
|---|---|---|---|---|---|
| 2 | 2015.0 ms | 2024.2 ms | 22 | 3 | 5 |
| 4 | 2013.0 ms | 2019.0 ms | 22 | 3 | 5 |
| 5 | 2034.1 ms | 2287.0 ms | 22 | 3 | 5 |

The floor is the configured 2.0 s delay. The spread above it is small and the
worst p95 observed is **2287 ms**.

**Retry-lands, with the supervisor in place**, one run per candidate:

| Start-To-Close | verdict | elapsed | provider calls |
|---|---|---|---|
| 2500 ms | COMPLETED | 25.35 s | **2** |
| 4000 ms | COMPLETED | 23.94 s | 1 |
| 8000 ms | COMPLETED | 26.67 s | 1 |

All three complete, all well inside the pre-registered 120 s recovery deadline.

## The choice: **4000 ms**

### Why not 2500 ms

It is the value that produced `calls=2` — the duplicate — and that is precisely
why it must not be chosen. 2500 ms sits **213 ms** above the worst observed p95
of 2287 ms. A timeout that close to the response distribution will fire on
*healthy* calls whenever the provider runs slightly slow, and every such firing
produces a retry, and every retry can produce a duplicate.

**A duplicate caused by an over-tight timeout is not the duplicate H1 predicts.**
H1 is about what an event-sourced engine does when a worker *crashes* mid-flight.
Choosing the timeout that maximises duplicates would be selecting the parameter
that most flatters the hypothesis — the fitted-parameter failure this document
exists to avoid, arrived at by a different route.

### Why not 8000 ms

Safe against spurious firing, but it lengthens every crashed run by the time the
engine waits before deciding the activity is lost. That directly inflates the
`PENDING_AT_DEADLINE` share, which the pre-registration makes the uninformative
trigger at 20% (§3.3). Paying observation-window risk for margin already
available at half the value buys nothing.

### Why 4000 ms

* **1713 ms above the worst observed p95**, ~1.75× the response floor — enough
  that a slow-but-healthy call does not trip it. Spurious firing is the failure
  mode that would corrupt the measurement, and this is the margin against it.
* **It completed in 23.94 s**, the fastest of the three, leaving ~96 s of the
  120 s deadline unused. Comfortable room for the `PENDING_AT_DEADLINE` bound.
* It sits between the two candidates on the only axis that trades off here —
  spurious-retry risk against pending risk — and is defensible from the measured
  distribution alone, without reference to which value produced a duplicate.

## What it costs the comparison with B4

**B4 has no Start-To-Close timeout at all.** It is our model: it re-runs a
scheduled-but-uncompleted activity on replay, immediately, with no timer
(`B4_SEMANTICS.md` §3 — *"Initial Interval / Backoff Coefficient / jitter: No —
retry timing is not under test; retry policy is"*). B5 cannot omit the timer,
because a real server needs one to decide the activity is lost.

Three consequences, all of which belong in `§VIII` alongside the result:

1. **B5's duplicate rate is conditioned on a value B4 does not have.** The
   comparison is *"does the vendor's engine reproduce our model's rate when the
   engine's own timer is set to 4000 ms"*, not *"…unconditionally"*. A different
   timeout is a different cell and would have to be collected and reported as
   one.
2. **B5's rate is a lower bound**, and 4000 ms makes it more conservative than
   2500 ms would. Heartbeating is off (`B5_SEMANTICS.md` §5), and a timeout with
   margin fires later than a tuned deployment's would. If B5 comes in *below*
   B4, part of that gap is this choice and must not be read as the engine
   disagreeing with the model.
3. **Latency from B5 is not Temporal's recovery latency**, and now doubly so:
   the timeout is ours. No B5 timing number may be quoted as a property of the
   engine.

## Fixed

```
B5_START_TO_CLOSE_MS = 4000
```

Fixed before any B5 run exists. If collection shows it was wrong — a pending
share above 20%, or spurious firing on healthy calls — the remedy the
pre-registration allows is a **re-registered** value and a fresh session, never a
re-reading of runs already collected.
