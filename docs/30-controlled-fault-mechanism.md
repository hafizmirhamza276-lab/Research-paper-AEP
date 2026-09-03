# Choosing the controlled fault mechanism — measurement, and a design finding

**Phase 13, step 1. 2026-09-03.** Instruments:
`scripts/measure_fault_landing.py`, `scripts/measure_arm_windows.py`. Raw:
`reports/raw/phase13-fault-landing.json`, `reports/raw/phase13-arm-windows.json`,
`reports/raw/phase13-landing.txt`.

---

## 1. What was measured, and what "landing" means

Two quantities, kept apart because conflating them chooses the mechanism wrong:

* **command latency** — how long the injector's own command takes to return.
  This is what `experiments/harness/redis_kill.py:96-108` times as `command_ms`
  and what Phase 10 reported (native `docker kill` median 317 ms).
* **landing latency** — how long until the server can no longer answer a client.
  **This** is the quantity that races `WAITAOF`. It is measured directly: an
  open probe socket issues `PING` in a tight loop, and landing is the interval
  from *issuing* the fault command to the first PING that does not return.

The yardstick throughout is the `WAITAOF` round trip under `appendfsync
everysec`: Redis fsyncs once a second, so a `WAITAOF` issued at a uniformly
random phase returns in **U(0, 1000) ms**.

**Measurement floor, disclosed rather than chased.** `Probe.responsive()`
confirms a failure with a second attempt at a 10 ms timeout, so declaring the
fault landed costs two timeouts. Every landing number below has a floor of
**~20 ms**; a reported 22 ms landing means "at or below 22 ms". Against a
1000 ms window that is immaterial to the choice. The first version of this
script used a 50 ms timeout and reported iptables' ~2 ms landing as 54 ms — a
27× overstatement, and the reason the floor is now printed with the result.

## 2. All four candidates, 100 trials each, native runtime

| mechanism | failure class | command median | **landing median** | landing spread (max−min) | landing / WAITAOF window | failures |
|---|---|---|---|---|---|---|
| `docker kill -s KILL` *(the mechanism the frozen cells used)* | **F3 crash-stop** | 368.3 ms | **368.4 ms** | 134.6 ms | **0.368** | 0/100 |
| `docker pause` *(cgroup-v2 freezer)* | **F3 crash-stop** | 37.9 ms | **58.3 ms** | 36.0 ms | **0.058** | 0/100 |
| `iptables -I OUTPUT … -j DROP` | **F2 partition** | 1.6 ms | **22.0 ms** *(at the floor)* | 2.5 ms | **0.022** | 2/100 |
| `tc qdisc netem delay 5000ms dev lo` | **F2 partition** | 1.9 ms | **22.3 ms** *(at the floor)* | 20.8 ms | **0.022** | 2/100 |

Full detail (min/p95/max) in `reports/raw/phase13-landing.txt`.

Two preconditions were verified before any of this, because the mechanism is
worthless if either fails:

* **`docker kill` works on a paused container** — status `exited`, exit code
  **137** (SIGKILL), auto-unpaused. So pause-then-kill leaves the same end state
  as kill alone.
* **A paused Redis blocks a client command** — a `PING` on an established
  connection **timed out after 2002 ms**. So a `WAITAOF` issued into a frozen
  server cannot return, which is the entire premise.

## 3. The criterion, and the choice

> **Criterion: the smallest and tightest landing latency among mechanisms that
> do not change the class of fault being injected.**

The second clause does the work. `iptables` and `tc netem` are faster — about
2 ms against 58 ms — but they are **F2 network partitions, not F3 crashes**.
Using either would change the claim from *"AEP-full withholds an unwanted effect
when Redis crashes"* to *"…when the network partitions"*: a different result,
requiring a new row in §III's failure model, and **not comparable to the frozen
`docker kill` cell** it is supposed to replicate under control. `tc netem` is
additionally disqualified on its own terms — it delays **every** loopback packet
on the host, including the mock provider's on `127.0.0.1:8099`, so it perturbs
the thing being measured as well as the thing being faulted.

**Chosen: `docker pause` followed by `docker kill`.** Against the existing
mechanism it is **6.3× faster** (58.3 ms against 368.4 ms) and **3.7× tighter**
(spread 36.0 ms against 134.6 ms), and it cuts the residual race from **37% of
the WAITAOF window to 5.8%**.

### Failure-model classification

`docker pause` uses the cgroup-v2 freezer; the kill that follows delivers
SIGKILL to PID 1 exactly as before. The run's end state — no shutdown hook, no
buffer flush, written bytes still in the kernel page cache — is **identical** to
the existing fault. The mechanism therefore instantiates **F3, crash-stop of the
state store**, the same class as the frozen cells.

**§III's failure model does not need a new row.** It needs, at most, one clause
noting that the crash may be preceded by a bounded freeze. The freeze is not a
separate fault the protocol can observe: from the client's side a frozen server
and a slow server are indistinguishable, and the protocol's response to both is
the barrier timeout it already has.

---

## 4. The design finding: the race can be narrowed, not removed

This is the part that changes what Phase 13 can claim, and it was found by
reading the ordering rather than by assuming it.

`after_intent_before_barrier` resolves to
`CrashPoint.AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER`
(`experiments/harness/crash_points.py:113`), which is
`aep_core/core/intent_workflow.py:442` — **immediately before**
`_confirm_dispatch_barrier`, the `WAITAOF` call, at line 446.

So the obvious deterministic design is: **freeze Redis synchronously at that
checkpoint**, so `WAITAOF` is issued into a frozen server and can never return.
Ordering guaranteed by program order rather than by a latency comparison.

**It does not work, and the reason is structural.**

B3 reaches the same checkpoint — it is the full `WriteAheadRunner` with the
barrier ablated, and `experiments/baselines/crash_points.py:155-160` states that
it "reaches every `_checkpoint` AEP-full reaches and uses the same vocabulary".
After that checkpoint B3 still performs `authorize_dispatch`
(`intent_workflow.py:479`) and `preflight` (`:494`), **both Redis calls**. A
server frozen *at* the checkpoint blocks those too. B3 would stop dispatching,
its 28/30 ceiling would collapse, and it would collapse **because the injector
disabled both arms**, not because either protocol did anything.

The generalisation is the finding:

> **The asymmetry this experiment measures *is* a timing difference.** AEP-full
> has exactly one extra Redis-dependent step that B3 does not — `WAITAOF`, slow
> and phase-dependent at 0–1000 ms — where B3's remaining calls are fast. The
> fault must therefore land in a window B3 has already left and AEP-full is
> still inside. That window can be widened, and its boundary measured, but it
> cannot be closed without removing the phenomenon being measured.

`experiments/harness/redis_kill.py:15-22` already recorded half of this, as the
reason the kill fires asynchronously: firing synchronously *"would suspend it
equally for every system, which would destroy the very difference the ablation
exists to measure."* What is new here is that the same objection defeats the
**synchronous-freeze** design too, and therefore defeats the strong form of
WS-3's goal.

### What this means for the phase as specified

The Phase 13 prompt's framing — *"replaces the race with a controlled fault, so
the result becomes deterministic and attributable"* — is achievable in a
**weakened** form only:

* **Achievable:** narrow the race from 37% to ~6–8% of the WAITAOF window, make
  the injector's contribution measured rather than unknown, and report the
  residual explicitly. AEP-full's unwanted-applied rate should fall from
  10–18/30 toward a small number, and *the remaining variance is bounded by a
  distribution this document measures* rather than being unknown.
* **Not achievable by this mechanism:** a genuinely deterministic 0/30 against
  30/30. Any fault that guarantees `WAITAOF` cannot return also blocks B3's
  post-checkpoint Redis calls, unless the fault is targeted specifically at the
  fsync rather than at the server — which is a different fault class again and
  is *not* a crash.

### The one mechanism that would be deterministic, and its cost

Disabling the fsync rather than the server — `CONFIG SET appendfsync no` at the
checkpoint — would make `WAITAOF` unsatisfiable while leaving every other Redis
call working, so B3 would be untouched and AEP-full would deterministically time
out. It is the only candidate that separates the two arms by construction.

**It is not a crash, and it is arguably not a fault at all** — it is a
configuration change that makes durability unattainable. It would instantiate a
class the paper's failure model does not currently have, it could not be
described as a Redis-kill result, and the comparison to the frozen cell would be
to a different experiment. **It is recorded here as the honest alternative and
is not adopted without an explicit decision**, because adopting it silently
would answer a different question from the one §VI-C2 asks.

---

## 5. What the arming delay must be, and why it is not yet fixed

Under the chosen mechanism the injector arms at the checkpoint and the fault
lands 58 ms later. B3 needs its `authorize_dispatch` + `preflight` round trips to
complete inside those 58 ms; AEP-full needs its `WAITAOF` to still be
outstanding.

`scripts/measure_arm_windows.py` was written to take that boundary from existing
collections rather than guess it. **It does not yet yield the number**, and this
is stated rather than papered over: the event vocabulary of the Phase-8.4 logs
carries `redis_kill_armed`, `redis_kill_issued`, `durability_ack_observed`,
`execution_resolved` and `redis_hard_killed`, but **no event marking the moment
provider bytes were transmitted**, which is where B3's exposure ends. The
measured `kill_command_ms` in those logs (median 1045 ms for both arms) is the
old shim-era `docker kill`, not a post-arming exposure.

Determining B3's window therefore needs one of:

1. an added event at transmission — a harness change, in scope, and the
   cleanest option; or
2. a direct micro-measurement of `authorize_dispatch` + `preflight` against a
   live Redis, which bounds it without touching the harness.

Until it is measured the arming delay cannot be chosen by measurement, and
choosing it by argument is the thing this step exists to avoid.
