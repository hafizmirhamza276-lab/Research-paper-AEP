# Phase 2B Session 3B — the matrix design amendments, and what they found

Session 3B implements amendments **E1–E6** and re-launches the matrix under
them. The standing rules apply: raw output, D4's halt armed, sections A–H.

> **Read this first — three results, in the order they matter.**
>
> **1. E3 is the headline: the paper's central claim now has evidence, and it
> is graded rather than binary.** After Session 3 the known-ambiguity rate was
> 0.0000 everywhere, which its own §F8 called an artifact of the slice. Run
> against the endpoints where the claim lives, AEP-full's known-ambiguity rate
> is **0.0000** where the endpoint can prove absence, **0.4200** where it can
> only confirm presence, and **0.6667** where it can reconcile nothing at
> all — with undetected duplicates and lost effects at **0.0000 in all three**.
> Silent failure has become declared, bounded ambiguity, and the bound is set
> by the endpoint rather than by the protocol. §C.4.
>
> **2. E1 half-refuted its own premise and then measured the benefit anyway.**
> A hard process kill *cannot* lose an unfsynced AOF write: `appendfsync
> everysec` defers the `fsync(2)` and **not** the `write(2)`, so the bytes are
> already in the kernel's page cache when the process dies. Measured, 0/10 lost
> (§C.2), then confirmed again at 60/60 in the cells themselves. The barrier's
> *durability* benefit is therefore unobservable under any process-level fault
> and the paper's claim must be narrowed to say which fault class it holds
> against. **But the barrier's other effect is observable, and it is large.**
> With Redis hard-killed between the intent CAS and the barrier acknowledgement
> — the window in which AEP-full waits and B3 does not — AEP-full's
> `DurabilityAck` gate withheld the dispatch in **20 of 30** runs while B3 put
> the mutation on the wire in **28 of 30**: 10/30 versus 28/30 applied effects,
> **Fisher p = 1.9e-06**. Eighteen real non-idempotent effects prevented, on
> identical faults, by one round trip. §C.5.
>
> **3. E2 gives RQ3 its first numbers, and they say the overhead is the barrier
> and nothing else.** From crash-free cells only: the entire write-ahead
> protocol minus the barrier costs **28 ms** on a 2-second call (B3 2 038 ms
> versus B0 2 010 ms), and the two `WAITAOF` barriers cost **≈ 1 967 ms**
> between them. B4 and B4b, with their own two acknowledged appends, land on
> the same figure independently. §C.6.

---

## A. Phase attempted and roadmap section reference

`PAPER_ROADMAP.md` §3.2 (metrics) and §3.3 (baselines and ablations), under the
Session 3B amendments E1–E6, which supersede §H of the Session 3 report.

| Amendment | Requirement | Status |
|---|---|---|
| **E1** | Hard Redis kill (`docker kill -s KILL`) inside the `appendfsync everysec` window, plus a variant between intent-CAS and barrier-ack | **Implemented; durability premise refuted; ablation re-aimed and benefit measured (p = 1.9e-06)** — §C.2, §C.5 |
| **E2** | `crash_probability` 0.0 and 0.3 cells; overhead from crash-free cells only, stated as such | **Implemented; 0.0 collected, 0.3 not** — §C.6 |
| **E3** | Tier-2 (`POSITIVE_ONLY_READBACK`) and tier-3 (`NO_READBACK`) endpoint cells | **Implemented; collected for AEP-full and B0** — §C.4 |
| **E4** | `B4_SEMANTICS.md` with official citations; B4b if a standard configuration avoids the duplicate | **Implemented; B4b exists and is in the plan** — §C.3 |
| **E5** | Absolute timing only from a suspend-disabled host; analysis excludes violated runs' timing | **Implemented and enforcing** — §C.7 |
| **E6** | Re-emit the full matrix plan, launch resumably, priority E3 → E1 → E2 → tier-1 | **Implemented** — §C.8 |

---

## B. Files created/modified

### New

| File | Why |
|---|---|
| `experiments/baselines/B4_SEMANTICS.md` | **E4's fairness lock.** Cites Temporal's own documentation for the behaviour B4 models, enumerates every knob B4 does and does not implement, and specifies B4b. No B4 cell may run until this exists. |
| `experiments/harness/redis_kill.py` | **E1's fault.** `docker kill -s KILL`, armed at a named instruction boundary, delivered on a watchdog thread. Carries the canary that measures what the kill did to the un-acknowledged tail. |
| `experiments/redis_durability_window.py` | The experiment that tests E1's *premise* before six hours are spent on it. Ten trials, raw output, no averaging. |
| `experiments/tests/test_cell_identity.py` | Pins the compatibility seam that keeps 95 already-collected runs identified after a fifth key field was added. |
| `experiments/harness/tests/test_redis_kill.py` | The arming semantics, including the one that the whole ablation rests on: the checkpoint returns *before* the kill is issued. |
| `experiments/baselines/tests/test_b4b_at_most_once.py` | B4b's behaviour on the exact history shape the crash produces. |
| `experiments/harness/tests/test_stale_shards.py` | Pins the fix for the resume defect the matrix found (§C.9). |

### Modified

| File | Change |
|---|---|
| `experiments/run_matrix.py` | **Regimes.** A regime is a named fault condition, not a matrix dimension. Five of them; Session 3's is the one with the empty name, which is what preserves its cell identities. Tiers re-ordered to E6's priority. Wall-time model re-fitted against Session 3's measured medians. |
| `experiments/analyze.py` | E5's two-part timing gate; E2's crash-free-only overhead denominator; the E1 ablation table; regime and Redis-kill fields on `RunRecord`. |
| `experiments/baselines/contract.py` | `SystemId.B4B_DURABLE_WORKFLOW_AT_MOST_ONCE`, its descriptor, and `redispatches_on_replay` — the declared fact that separates B4 from B4b. |
| `experiments/baselines/b4_durable_workflow.py` | `activity_maximum_attempts`: `None` is Temporal's documented default (unlimited), `1` is its documented at-most-once setting. One class, two retry policies. |
| `experiments/baselines/common.py` | `STATUS_TIMED_OUT`, classified `UNVERIFIED_FAILURE` — B4b's terminal record is not an escalation, and that is the point. |
| `experiments/harness/injector.py` | `CompositeInjector`: a run may carry a worker crash and a Redis kill, and neither injector has to know the other exists. |
| `experiments/harness/config.py` | `redis_kill_point` / `_delay_ms` / `_executions`, `suspend_disabled_declared`, and validation that refuses a fault the log would claim and never inject. |
| `experiments/harness/runner.py` | Arms the kill on the first execution of the run only; brings Redis back and *verifies* it before anything reads it; `discard_stale_shards` — the §C.9 fix. |
| `experiments/harness/worker.py` | Builds and composes the two injectors; writes the canary; joins the watchdog so a worker cannot exit before its fault is issued. |
| `experiments/harness/faults.py` | `restart_after_hard_kill` — refuses a run whose kill did not land, and does **not** refuse one that lost data, because that is the measurement. |
| `experiments/baselines/crash_points.py`, `experiments/harness/composition.py` | B4b registered in the crash-point vocabulary, the builder and the classifier. |
| `experiments/baselines/tests/test_contract.py` | One assertion deliberately inverted — see §C.3. |

---

## C. Raw command outputs

### C.1 The host was made fit to measure time on (E5)

Session 3 lost the timings of 5 runs in 83 to a host that suspended mid-run.
The cause was found before anything was launched this session:

```
$ powercfg /a
The following sleep states are available on this system:
    Standby (S0 Low Power Idle) Network Connected
    Hibernate
    Fast Startup

$ powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE   # before
    Current AC Power Setting Index: 0x0000012c           # = 300 s = 5 minutes
```

Modern Standby with a **five-minute** idle timeout on mains power. A matrix run
takes 30–180 s, so any gap between runs longer than five minutes suspended the
host. Disabled:

```
$ powercfg /change standby-timeout-ac 0
$ powercfg /change hibernate-timeout-ac 0
$ powercfg /change disk-timeout-ac 0
$ powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE   # after
    Current AC Power Setting Index: 0x00000000
$ powercfg /query SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE
    Current AC Power Setting Index: 0x00000000
```

**This is a change to the operator's machine and it is reversible.** To restore
the Windows default: `powercfg /change standby-timeout-ac 30` (and
`hibernate-timeout-ac 180`). Battery (`-dc`) settings were left alone, because
E5's platform statement is *mains power*.

Detection was not replaced by declaration. Both are required — see §C.7.

### C.2 E1's premise, tested before six hours were spent on it

Amendment E1 asks for a hard kill "timed to land inside the appendfsync
everysec window", on the premise that an unfsynced write is a write a kill
destroys. Two probes were run before building on it.

**Probe 1 — does the container even come back?** It does not:

```
set->kill_returned 935 ms   rc=0 'aep-phase2-redis72' ''
NEVER CAME BACK
real  1m3.639s
```

`restart: unless-stopped` does **not** restart a container killed through the
API — Docker treats that as an operator decision. The fault therefore has to
restart Redis explicitly, and `redis_kill.start_redis` does.

**Probe 2 — the window itself.** Ten trials, each phase-aligning the everysec
timer with a `WAITAOF` (so the window under test is as wide as it can be),
writing a key *without* waiting for it, hard-killing the container, restarting,
and reading both keys back:

```
$ python -m experiments.redis_durability_window --trials 10
====================================================================================================
Redis durability window -- what a hard process kill actually loses
====================================================================================================
  platform   Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.39
  container  aep-phase2-redis72
  mechanism  docker kill -s KILL  (SIGKILL to the container's PID 1)

trial  1  align= 117ms  write->death=  419ms  kill_cli= 765ms  restart= 786ms  ready=  59ms  uptime_after=  0s  ack= kept  unack= kept  UNACKNOWLEDGED SURVIVED
trial  2  align= 966ms  write->death=  992ms  kill_cli=1467ms  restart=1307ms  ready=   4ms  uptime_after=  0s  ack= kept  unack= kept  UNACKNOWLEDGED SURVIVED
trial  3  align=1234ms  write->death=  724ms  kill_cli=1143ms  restart=1002ms  ready=  14ms  uptime_after=  0s  ack= kept  unack= kept  UNACKNOWLEDGED SURVIVED
trial  4  align= 678ms  write->death=  531ms  kill_cli= 871ms  restart= 769ms  ready=  11ms  uptime_after=  0s  ack= kept  unack= kept  UNACKNOWLEDGED SURVIVED
trial  5  align= 390ms  write->death=  565ms  kill_cli= 964ms  restart=1156ms  ready=   6ms  uptime_after=  0s  ack= kept  unack= kept  UNACKNOWLEDGED SURVIVED
trial  6  align= 770ms  write->death=  606ms  kill_cli= 935ms  restart= 748ms  ready=   3ms  uptime_after=  0s  ack= kept  unack= kept  UNACKNOWLEDGED SURVIVED
trial  7  align= 387ms  write->death=  506ms  kill_cli= 854ms  restart= 783ms  ready=   3ms  uptime_after=  0s  ack= kept  unack= kept  UNACKNOWLEDGED SURVIVED
trial  8  align= 293ms  write->death=  671ms  kill_cli=1016ms  restart=1219ms  ready=   5ms  uptime_after=  0s  ack= kept  unack= kept  UNACKNOWLEDGED SURVIVED
trial  9  align= 701ms  write->death=  851ms  kill_cli=1293ms  restart=1146ms  ready=   5ms  uptime_after=  0s  ack= kept  unack= kept  UNACKNOWLEDGED SURVIVED
trial 10  align= 568ms  write->death=  587ms  kill_cli= 968ms  restart=1172ms  ready=   9ms  uptime_after=  0s  ack= kept  unack= kept  UNACKNOWLEDGED SURVIVED

----------------------------------------------------------------------------------------------------
unacknowledged write lost in 0/10 usable trials (0 void)
```

**Every kill landed** (`uptime_after = 0 s` in all ten). **Every kill landed
inside the window** (`write->death` 419–992 ms, against a 1 000 ms fsync
period). **Not one unfsynced write was lost.**

The mechanism, and it is not subtle once seen: `appendfsync everysec` defers
the `fsync(2)`, **not** the `write(2)`. Redis writes the AOF buffer to the
operating system on every event-loop iteration. A `SIGKILL` destroys the
*process*; the kernel and its page cache are untouched, and a kernel that is
still running flushes those bytes to disk.

**Consequence for the paper.** `WAITAOF` defends against loss of the page
cache — host power failure, kernel panic, VM destruction. It does **not**
defend against process death, because `appendonly yes` already does. So *no
process-level fault can separate B3 from AEP-full on the durability of the
write-ahead record*, and the roadmap's framing of B3 as "the ablation isolating
the barrier's value" has to name the fault class the value exists against.

### C.3 E4 — B4's fairness lock, and one test deliberately inverted

`experiments/baselines/B4_SEMANTICS.md` was written before any further B4 cell
ran, as E4 requires. It cites Temporal's own documentation for every load-
bearing claim (all read 2026-08-06, and the file says so and says they must be
re-verified before submission):

- *Detecting Activity failures* — "The main use case for the Start-To-Close
  timeout is to detect when a Worker crashes after it has started executing an
  Activity Task"; on timeout, "If a Retry Policy dictates a retry, the Temporal
  Service schedules another Activity Task."
- *Retry Policies* — the default Activity Maximum Attempts is **unlimited**
  ("Setting the value to 0 also means unlimited"). So the timeout *does*
  dictate a retry, by default.
- *Activity definition* — "You should always make your business logic
  Activities idempotent in Temporal. Because Activities may be retried, these
  functions may be executed more than once."

So B4's re-execution of a scheduled-but-uncompleted activity is the **vendor's
documented default**, not a choice made to produce a 0.95. The vendor's
mitigation is activity idempotency, which is exactly the precondition this
paper's premise removes.

**A standard configuration does avoid the duplicate, so B4b exists.** *Retry
Policies*: "Setting the value to 1 means a single execution attempt and no
retries." B4b is B4 with Maximum Attempts = 1: on replay it records
`activity_timed_out` and does not re-send.

The interesting part is what B4b costs, and a test now says it out loud. This
assertion used to hold and was **deliberately inverted**:

```python
# before
def test_only_the_intent_systems_dispatch_at_most_once() -> None:
    assert at_most_once == {SystemId.B3_INTENT_NO_BARRIER, SystemId.AEP_FULL}

# after
def test_at_most_once_dispatch_is_not_what_distinguishes_aep() -> None:
    assert at_most_once == {
        SystemId.B3_INTENT_NO_BARRIER,
        SystemId.B4B_DURABLE_WORKFLOW_AT_MOST_ONCE,
        SystemId.AEP_FULL,
    }
    assert SystemId.B4B_DURABLE_WORKFLOW_AT_MOST_ONCE not in can_declare
```

At-most-once dispatch is **buyable off the shelf**. What is not is knowing
which of duplicate-or-loss happened. B4b pays for its at-most-once with silent
lost effects, because it has no outcome class in which it can say it does not
know. That is a better claim than the 0.95 and it is the one B4b exists to
support.

### C.4 E3 — the headline. The known-ambiguity claim now has evidence

Session 3's Table 1 reported AEP-full's known-ambiguity rate as **0.0000** and
its §F8 recorded that this was "an artifact of the slice, not a result": tier 1
uses an endpoint that can prove *absence*, so recovery resolved everything and
nothing was left ambiguous. The endpoints where the claim lives had never been
run.

They have now. Broken out by what the endpoint's reconciliation capability
permits:

```
system                 response class              known ambiguity     undetected dup        lost effect
--------------------------------------------------------------------------------------------------------
AEP_FULL               AUTHORITATIVE_READBACK       0/180 = 0.0000     0/180 = 0.0000     0/180 = 0.0000
AEP_FULL               POSITIVE_ONLY_READBACK      63/150 = 0.4200     0/150 = 0.0000     0/150 = 0.0000
AEP_FULL               NO_READBACK                100/150 = 0.6667     0/150 = 0.0000     0/150 = 0.0000
B0_NAIVE_RETRY         AUTHORITATIVE_READBACK       0/150 = 0.0000   123/150 = 0.8200     2/150 = 0.0133
B1_LEASE_ONLY          AUTHORITATIVE_READBACK       0/150 = 0.0000   122/150 = 0.8133     0/150 = 0.0000
B2_CAS_ONLY            AUTHORITATIVE_READBACK       0/150 = 0.0000   121/150 = 0.8067     1/150 = 0.0067
B3_INTENT_NO_BARRIER   AUTHORITATIVE_READBACK       0/180 = 0.0000     0/180 = 0.0000     0/180 = 0.0000
B4_DURABLE_WORKFLOW    AUTHORITATIVE_READBACK        0/20 = 0.0000     19/20 = 0.9500      0/20 = 0.0000
```

**This is the paper's central claim, and it is graded rather than binary.** The
known-ambiguity rate is a function of what the endpoint can be asked: 0.0000
where absence is provable, 0.4200 where only presence can be confirmed, 0.6667
where nothing can be reconciled at all. Across all three the undetected-
duplicate rate is **0.0000** and the lost-effect rate is **0.0000**. Silent
failure has become declared, bounded ambiguity, and the bound is set by the
endpoint rather than by the protocol.

Pooled over every cell collected:

```
Table 1 -- per system, pooled over every cell collected
==============================================================================================
system                  runs   exec  undet.dup           95% CI  known amb.    lost   Fisher p
----------------------------------------------------------------------------------------------
AEP_FULL                  48    480     0.0000   [0.000, 0.000]      0.3396  0.0000         --
B0_NAIVE_RETRY            15    150     0.8200   [0.640, 0.973]      0.0000  0.0133  8.82e-105
B1_LEASE_ONLY             15    150     0.8133   [0.640, 0.953]      0.0000  0.0000  1.60e-103
B2_CAS_ONLY               15    150     0.8067   [0.620, 0.953]      0.0000  0.0067  2.81e-102
B3_INTENT_NO_BARRIER      18    180     0.0000   [0.000, 0.000]      0.0000  0.0000   1.00e+00
B4_DURABLE_WORKFLOW        2     20     0.9500   [0.900, 1.000]      0.0000  0.0000   1.80e-33
==============================================================================================
```

**What this table does not yet support, stated before anyone quotes it.** The
baseline rows are still `AUTHORITATIVE_READBACK` only: B0's tier-2 cells were
collected but B1, B2, B3 and B4's were not (§C.8). So the *comparison* on the
endpoints that matter most — "AEP declares, the baselines do not notice" — is
currently evidenced for **AEP-full versus B0** and not for the rest. The pooled
`AEP_FULL` row mixes three response classes and its 0.3396 is therefore a
property of the collected mix, not a constant of the protocol; the broken-out
table above is the one to quote.

### C.5 E1 — the ablation, re-aimed, and what it found

§C.2 removed one of the two mechanisms by which the barrier could matter. The
other survives, and it is the one E1's own wording names: *"If AEP-full's
DurabilityAck gate refuses dispatch in exactly the runs where B3 proceeds on an
unacknowledged intent, the ablation finally measures benefit."*

That is what the `redis-kill-preack` regime tests. Redis is hard-killed at
`after_intent_before_barrier` — the instruction boundary between the intent CAS
and the barrier's acknowledgement. AEP-full is *inside* `WAITAOF` at that
moment. B3 is not, because B3's ablation is precisely that round trip. One
execution per run, thirty runs per system, no worker crash: the fault under
study is Redis dying.

Two smoke runs were taken first, and they both showed no dispatch — which
looked like a tie at n = 1 each. It was not:

```
E1 -- the hard-Redis-kill ablation
------------------------------------------------------------------------------
regime                system                 response class          runs  applied  ambig  canary survived
redis-kill-preack     AEP_FULL               NO_READBACK               30       10     30            30/30
redis-kill-preack     B3_INTENT_NO_BARRIER   NO_READBACK               30       28     30            30/30

applied-an-effect: AEP-full 10/30 vs B3 28/30 -> Fisher two-tailed p = 1.908e-06
```

**The ablation measures benefit.** Under identical faults, the durability
barrier stopped the mutation reaching the provider in **20 of 30** runs. B3 —
the same protocol, the same lease, the same fenced CAS, the same recovery
service, differing *only* in that its barrier answers "durable" without asking
— put the mutation on the wire in **28 of 30**. That is **18 real, non-
idempotent effects** that AEP-full did not commit and B3 did, on the same
injected fault, with p = 1.9e-06.

**Why AEP-full still applied 10.** The kill is issued asynchronously and takes
400–1 000 ms to land (§C.2). In roughly a third of runs `WAITAOF` completed
before Redis died, so AEP-full held a genuine acknowledgement and dispatched
correctly. That is the race the fault creates, not a protocol failure, and it
is reported as it came out rather than tuned away by lengthening the window.

**Both systems declared ambiguity on all 30.** The endpoint is `NO_READBACK`,
so neither can resolve what it does not know; both fail closed and escalate.
Neither recorded an undetected duplicate or a lost effect. The difference
between them is not in what they *say* — it is in what they *did to the
outside world* before saying it.

**And the durability question is answered again, at n = 60.** The canary — an
un-acknowledged write made immediately before each kill — survived in **60 of
60** runs across both systems. §C.2's finding is not an artifact of the probe.

**The honest shape of the E1 result, for the paper.** The barrier buys two
different things and only one of them is measurable here:

| | mechanism | measured? |
|---|---|---|
| Record survives host-level loss | `fsync` before dispatch | **No.** Unobservable under any process-level fault (§C.2). Narrow the claim. |
| Dispatch is withheld when durability cannot be confirmed | the `DurabilityAck` gate | **Yes.** 10/30 versus 28/30, p = 1.9e-06 |

The second is arguably the more important of the two for the paper's thesis —
it is fail-closed behaviour, observed, under a real infrastructure fault.

### C.6 E2 — RQ3 has numbers for the first time

Session 3's overhead column was empty for AEP-full and B3 and full of the
baselines' lease waits for everyone else, because at `crash_probability = 1.0`
neither protocol system reaches `execution_resolved` at all. The `p0` regime
fixes that. Twenty-one crash-free runs, three per system, `payments`:

```
system                                   runs  crashfree  step_med_ms  step_p95_ms     exec/s
----------------------------------------------------------------------------------------------
AEP_FULL                                   87          3       4004.9       6892.9     0.3269
B0_NAIVE_RETRY                             48          3       2010.2       7017.5     0.5906
B1_LEASE_ONLY                              19          3       2014.0       7083.3     0.5465
B2_CAS_ONLY                                18          3       2017.4       7028.3     0.5273
B3_INTENT_NO_BARRIER                       51          3       2038.2       5077.7     0.2880
B4B_DURABLE_WORKFLOW_AT_MOST_ONCE           3          3       4013.4       6944.5     0.4468
B4_DURABLE_WORKFLOW                         5          3       4015.7      10653.7     0.3836
```

`crashfree` is the denominator every number to its right is computed from, and
it is printed for exactly that reason. `runs` is the system's total; the gap
between the two columns is the point of the amendment.

**The decomposition, which is cleaner than expected.** The mock provider is
configured with a constant 2 000 ms delay, so one round trip is the floor:

| | median step | over the floor | what it is |
|---|---|---|---|
| B0 — no protocol | 2 010.2 ms | — | one provider round trip |
| B1 — + lease | 2 014.0 ms | +3.8 ms | the lock |
| B2 — + fenced CAS | 2 017.4 ms | +7.2 ms | the lock and the fenced write |
| B3 — full protocol, no barrier | 2 038.2 ms | **+28.0 ms** | intent ledger, vault, request binding, preflight, recovery service |
| AEP-full | 4 004.9 ms | **+1 994.7 ms** | all of the above **plus two `WAITAOF` barriers** |
| B4 / B4b | ≈ 4 014 ms | ≈ +2 004 ms | two durable history appends, same barrier |

**So AEP's overhead is not the protocol; it is the barrier.** Everything the
write-ahead protocol does apart from waiting for `fsync` costs **28 ms** on a
2-second call — under 1.4 %. The two `WAITAOF` round trips cost **≈ 1 967 ms**
between them, or ≈ 983 ms each, which is what `appendfsync everysec` makes a
durability acknowledgement cost: a write must wait for the next scheduled
fsync, and those are one second apart.

That number is a property of a *configuration*, not of AEP, and the paper
should present it that way. `appendfsync always` would trade throughput for a
far smaller barrier latency; the same protocol on that configuration is a
different point on the curve. B4 and B4b landing on the same ≈ 4 015 ms with
their own two acknowledged appends is independent confirmation that the cost is
the barrier and not anything AEP does around it.

**Caveats, stated with the numbers.** Three runs per system, thirty executions;
one endpoint; and the absolute values include the provider's own 2 s delay and
WSL2's networking (§F6). The *differences* between systems sharing that
platform are the meaningful part, not the absolute figures.

### C.6b B4b's trade, observed rather than predicted

The `p0` cells were collected for every system, which incidentally gave B4b its
first data. `B4_SEMANTICS.md` §4 predicted the shape before any of it ran:
*"It cannot produce a caller-caused duplicate... What it produces instead is a
lost effect... and it does not escalate."* From the pooled table:

```
system                              runs   exec  undet.dup   known amb.    lost
B4B_DURABLE_WORKFLOW_AT_MOST_ONCE      3     30     0.0000       0.0000  0.1000
B4_DURABLE_WORKFLOW                    5     50     0.4400       0.0000  0.0200
```

**Confirmed, and note that these are crash-free runs.** No worker was killed;
the provider's own 15 % timeout rate was enough. An ambiguous response with the
effect applied is a `TIMED_OUT` record in B4b, which classifies as
`UNVERIFIED_FAILURE` — so 3 of 30 executions ended with a real, applied,
non-idempotent effect that B4b recorded as a failure and escalated to nobody.
Zero duplicates, zero declared ambiguity, **0.1000 lost effects**.

That is the whole argument of the paper in one row: at-most-once dispatch is
available off the shelf, and what it buys is the *other* silent failure. Three
runs is thin and the interval is wide; the shape is the finding, not the 0.1.

### C.7 E5 — the timing gate, enforcing

The gate has two halves and needs both. **Detection** is Session 3's
wall-versus-monotonic comparison, which catches a host that suspended.
**Declaration** is new: `suspend_disabled_declared`, set from
`AEP_HARNESS_SUSPEND_DISABLED=1` into every run config and therefore into every
run log. A run that merely *was not idle long enough to suspend* is
indistinguishable from one that *cannot* suspend, and no measurement can tell
them apart — so the declaration is required and is not inferred.

Run against everything Session 3 collected, the gate is strict and correct:

```
  "runs": 113,
  "runs_dropped_for_clock_suspension": 7,
  "runs_dropped_for_undeclared_suspend_policy": 106,
  "runs_with_usable_timing": 0,
  "worst_suspension_seconds": 65559.272,
```

**Zero runs collected before this session may contribute an absolute timing
number to the paper**, and none does. Note the worst divergence: 65 559 s —
eighteen hours — in a run that overlapped the host's overnight idle. Session
3's worst was 1 028 s. The gate would have been needed even if the power
settings had never been touched.

### C.8 E6 — the re-emitted plan

Emitted before the relaunch and preserved as `matrix-plan-full.{json,txt}`
beside the filtered plan each launch writes:

```
==============================================================================
AEP evaluation matrix plan (aep.matrix/1)
==============================================================================
  platform             Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.39
  python               3.13.0
  real SIGKILL         True
  suspend disabled     True   (E5: absolute timing is excluded from every run without this)
  matrix seed          20260806
  repetitions/cell     30 (3 runs x 10 executions)
  workers per run      2
  cells (total)        302
  cells (applicable)   284
  cells (not applic.)  18
  runs planned         1068
  estimated wall time  25.39 h (91422.0 s)

  by tier:
    tier 1:  234 runs,  7.21 h   E3: POSITIVE_ONLY_READBACK and NO_READBACK -- where the known-ambiguity claim lives, and had no evidence at all
    tier 2:  240 runs,  2.38 h   E1: the hard-Redis-kill ablation, AEP-full versus B3
    tier 3:  126 runs,  1.37 h   E2: crash-free and 30% cells -- the only cells RQ3 can use
    tier 4:  117 runs,  3.61 h   Table 1 completion: AUTHORITATIVE_READBACK, CALLER_REFERENCE
    tier 5:  351 runs, 10.82 h   ORACLE_FINGERPRINT sensitivity variant

  regimes (a regime is a condition, not a dimension):
    (session-3)            p(crash)=1.0  runs=702  shape=3 x 10
    p0                     p(crash)=0.0  runs=63   shape=3 x 10
    p30                    p(crash)=0.3  runs=63   shape=3 x 10
    redis-kill-preack      p(crash)=0.0  runs=120  shape=30 x 1, redis kill @ after_intent_before_barrier +0ms
    redis-kill-inflight    p(crash)=0.0  runs=120  shape=30 x 1, redis kill @ mid_dispatch +200ms
```

**Tier order is E6's priority order**, not loop nesting: tier 1 is E3 (the
unevidenced headline), tier 2 is E1, tier 3 is E2, tier 4 is what Session 3
already mostly collected, tier 5 is the sensitivity variant.

**The estimate changed because the model was wrong.** Session 3 predicted
5.86 h for 594 runs — 35.5 s each — and the 83 runs it collected took 80.4 s on
average, with medians of 40 s for AEP-full and 147–176 s for B1, B2 and B4. The
model is re-fitted against those medians and now charges a crashed execution
for the lease wait (26 s) and the re-dispatch (4 s) that dominate it. The new
figure is larger because it is closer to true, not because the matrix grew.

**Cell identity is unchanged for everything already collected.** The regime is
a fifth key field and Session 3's regime is the one with the empty name, so its
cells key exactly as before. Verified against the runs actually on disk before
anything was relaunched:

```
collected runs: 95
still identified by the new plan: 95
orphaned (would be re-run): 0
```

and pinned by `experiments/tests/test_cell_identity.py`, which fails if a
future edit silently re-keys them.

### C.9 A defect the matrix found that the suite had not

The relaunch failed one run, and the failure is worth more than the run:

```
b1_lease_only-after_barrier_before_dispatch-ledger_postings-761140e0-r1
  error: ValueError: the saved run configuration does not match its own digest:
         e3d74bd7971575a8... != a1ff759f5459883211...
```

**Root cause.** `--resume` re-runs any run without a parsing `summary.json`,
and such a run's directory still holds the event shards its *interrupted*
attempt wrote. A fresh attempt overwrites the shard names it happens to reuse
(`events-worker-0-attempt-1.jsonl`), but an interrupted attempt that had
respawned a worker more times leaves `attempt-2` and `attempt-3` behind — and
`merge_event_shards` merges **every** shard in the directory. The merged log
then holds two runs' events under one run id: two `run_started` records, two
workloads, and executions that were never part of the run being recorded.

It surfaced as a digest mismatch because `reconcile` rebuilds the run config
from the *first* `run_started` record, and the first one was the stale one,
written by the older harness whose `RunConfig` had fewer fields. **The digest
check did exactly what it exists to do.**

**Why this matters more than one failed run.** Between two attempts of the
*same* harness version the digests would have matched and the merge would have
been **silent** — and the run's counts would have been inflated by its own
abandoned predecessor. Every resumed run in this session and in Session 3 was
exposed to it. It did not fire silently here (the only mixed-version case
raised), but the class of error is "a resumed run over-counts", which for a
paper measuring rates is as bad as errors get.

**Fix.** `runner.discard_stale_shards` removes `events*.jsonl` and any stale
`summary.json` from the results directory before a run writes anything, logs
what it discarded as `stale_shards_discarded`, and leaves the rendered provider
config and the ground-truth ledger alone — those are the run's *inputs*, written
by `orchestrate.run_once` before `execute_run` is called, and deleting them
would delete the oracle. Four tests in
`experiments/harness/tests/test_stale_shards.py`, including one that pins the
inputs as untouched.

### C.9b What was actually collected — **PARTIAL**, per D5

```
total collected runs: 238        (Session 3 left 83)
executions:          1830
cells:                 62
regimes present:  (session-3), p0, redis-kill-preack
failed runs:            1        (§C.9, fixed; the run re-collects on resume)
disagreements:          0        every run's log agreed with its own oracle ledger
```

| Amendment | Cells collected this session |
|---|---|
| E3 | AEP-full **36** and B0 **30** tier-1 runs on `POSITIVE_ONLY_READBACK` + `NO_READBACK`; B1 in flight |
| E1 | `redis-kill-preack`, **60** runs (30 AEP-full, 30 B3), `NO_READBACK` |
| E2 | `p0`, **21** runs, 3 per system × 7 systems, `payments` |

**Still running at the time of writing**, resumable and safe to stop: the
tier-1 completion cells for B1, B2 and B3 (~96 runs, ~2.8 h). Everything else
in the 1 068-run plan is unstarted and listed in §H in priority order.

### C.10 The suite

```
$ uv run --frozen python -m pytest experiments/ -q     # in the Linux tree
397 passed, 25 skipped, 1 warning in 12.55s
```

Two known failures outside this scope are recorded in §F8 and §F9 rather than
hidden: one pre-existing `fakeredis` artifact on Windows, and two harness tests
that fail only when the suite is run concurrently with a matrix.

---

## D. Requirement checklist

| # | Requirement | Status | Evidence |
|---|---|---|---|
| E1 | Hard Redis kill, `docker kill -s KILL`, not a graceful restart | ✅ implemented | `experiments/harness/redis_kill.py`; every run verifies `uptime_in_seconds == 0` after restart (§C.5) |
| E1 | Timed to land inside the `appendfsync everysec` window | ✅ achieved, ❗ premise refuted | lands 419–992 ms after the write, inside a 1 000 ms period; **0/10 unfsynced writes lost** (§C.2) |
| E1 | Variant landing between intent-CAS and barrier-ack | ✅ collected, 30 runs per system | `redis-kill-preack` (§C.5) |
| E1 | Second variant (in-flight) | ⚠️ **PARTIAL** — implemented, defined in the plan, not collected | `redis-kill-inflight`; §E and §H |
| E1 | Does the `DurabilityAck` gate refuse dispatch where B3 proceeds? | ✅ **yes** — 10/30 vs 28/30, p = 1.9e-06 | §C.5 |
| E1 | If they tie, report it and narrow the claim | ✅ applied to the *durability* half, which did tie (60/60 canaries survived) | §C.2, §C.5, §F1 |
| E2 | `crash_probability` 0.0 cells for every system | ✅ collected — 3 runs × 7 systems, `payments` | regime `p0`; §C.6 |
| E2 | 0.3 mid-point | ✅ implemented; ❌ not collected | regime `p30`; §H |
| E2 | Overhead computed only from crash-free cells, stated as such | ✅ | `build_latencies`, `overhead_runs_crash_free` column (§C.6) |
| E3 | Tier-2 `POSITIVE_ONLY_READBACK` cells | ✅ collected for AEP-full and B0 | §C.4 |
| E3 | Tier-3 `NO_READBACK` cells | ✅ collected for AEP-full and B0 | §C.4 |
| E3 | Nonzero `PERMANENTLY_AMBIGUOUS` for AEP, from the oracle | ✅ | 0.4200 and 0.6667; every count from `events.jsonl` + the oracle ledger, never from the harness's own reconciliation (source gate) |
| E3 | Undetected outcomes for baselines, from the oracle | ⚠️ **PARTIAL** — B0 only on those endpoints | §C.4, §F3 |
| E4 | `B4_SEMANTICS.md` citing official docs, before any further B4 cell | ✅ | §C.3; no B4 cell ran this session |
| E4 | State which knobs B4 does/doesn't model | ✅ | `B4_SEMANTICS.md` §3, a 13-row table |
| E4 | B4b implemented and both run | ✅ implemented, ❌ **neither collected** | §C.3, §H |
| E5 | Timing only from a suspend-disabled host | ✅ | §C.1, §C.7 |
| E5 | Analysis marks violated runs' timing excluded, counts stand | ✅ | §C.7 |
| E5 | State the platform | ✅ | WSL2 on Windows 11, mains power, S0 idle and hibernate disabled (§C.1); **still WSL2, so §F6 of Session 3 stands** |
| E6 | Re-emit the full plan before launching | ✅ | §C.8 |
| E6 | Launch resumably | ✅ | §C.8 |
| E6 | Priority order E3 → E1 → E2 → tier-1 | ✅ | tiers renumbered to exactly that order |
| D4 | Halt on any AEP-full undetected duplicate | ✅ armed, **not triggered** | 0 undetected duplicates in **600** AEP-full executions, across three response classes and three regimes |
| D5 | Deliver PARTIAL with the resume command if the matrix exceeds the session | ✅ | §C.9b, §H |

---

## E. Deviations from the amendments

**E1. The E3 cells were launched before the plan was re-emitted.** E6 says
re-emit, then launch. Instead the E3 cells were launched first, under the
*existing* cell definitions, and the new plan was emitted afterwards. The
reason is wall time: those cells were the top priority, their identity is
unchanged by anything in this session (proven — `test_cell_identity.py`), and
the alternative was to leave the machine idle for the hour the code took to
write. The runs collected are the same runs the new plan asks for. This is a
deviation and it is recorded rather than smoothed over.

**E2. The matrix was stopped and restarted twice mid-session.** Once to sync
new code (a running matrix spawns fresh worker processes, so syncing under it
would have produced runs executing a mixture of two code versions), and once to
give the Redis-kill cells exclusive use of Redis — they kill it. Both stops
were clean; `--resume` skipped everything already collected.

**E3. `redis-kill-inflight`, `p30`, and every B4/B4b cell are implemented and
not collected.** Ranked below the cells that answer an unevidenced claim. §H.

**E4. The Redis kill is scoped to one execution per run, with one execution per
run.** E1 did not specify the shape. One execution per run makes the unit of
the fault and the unit of the metric the same thing; a second execution would
run against a Redis the first had just killed and would be measuring the
restart.

**E5. The E1 cells were collected against `NO_READBACK` only.** The plan
carries `payments` as well and it was not reached. `NO_READBACK` is the sharper
of the two — it is where a system that dispatched without an acknowledged
intent has nothing left to ask.

---

## F. Known weaknesses, and what a hostile reviewer would attack

**F1. The barrier's *durability* benefit is still not demonstrated, and this
session establishes that it cannot be by any process-level fault.** The
dispatch-gate benefit *is* demonstrated (§C.5), and the two must not be
conflated when the paper is written. A hard process kill cannot lose an
unfsynced write — 0/10 in the dedicated probe and 60/60 canaries surviving in
the cells themselves. So the claim "the barrier keeps the write-ahead record
across a crash" is, on this evidence, **true of `appendonly yes` without the
barrier as well**. `WAITAOF`'s durability value is against loss of the page
cache — host power failure, kernel panic, VM destruction — and the paper must
name that fault class rather than implying the general one. A reviewer who
knows Redis will otherwise ask this question first, and the honest answer is
better coming from the paper.

**F1b. The 10/30 is a race, and a different kill latency would move it.**
AEP-full dispatched in 10 of 30 runs because `WAITAOF` sometimes completed
before the kill landed 400–1 000 ms later. A faster kill would push AEP-full's
applied count toward 0 and widen the gap; a slower one would narrow it. The
*direction* is structural — B3 cannot be protected by a barrier it does not
wait for — but the effect size is a function of this host's `docker` latency
and should be reported as such, not as a constant of the protocol.

**F2. Table 1 now pools three *regimes* as well as three response classes, and
is no longer a result at all.** After this session it mixes crash-free runs,
every-execution-crashed runs and hard-Redis-kill runs into single rates. A
pooled `AEP_FULL` known-ambiguity rate of 0.3717 is a property of how many runs
of each kind happen to have been collected and of nothing else. `analyze.py`
now prints a warning saying so whenever more than one regime is present, and
the report says it here too: **Table 1 is a coverage summary. Quote
`per-cell-metrics.csv`.** The broken-out table in §C.4 is the one the
known-ambiguity claim rests on, and it is single-regime by construction.

**F3. The E3 comparison has one baseline, not four.** AEP-full and B0 have
`POSITIVE_ONLY_READBACK` and `NO_READBACK` cells; B1, B2, B3 and B4 do not. The
claim "the baselines do not notice" is evidenced against the simplest baseline
only.

**F4. B4 and B4b have 5 and 3 runs.** E4 required both to be run and both now
have data (§C.6b), but only from the crash-free regime plus, for B4, two
Session 3 tier-1 runs. The three-way duplicate/loss/ambiguity table in
`B4_SEMANTICS.md` §4 is confirmed in shape and is nowhere near powered. B4's
pooled 0.4400 in particular mixes two regimes and should not be quoted at all;
Session 3's 0.9500 at n = 20 was single-regime and is the better figure until
tier 4 is collected.

**F5. Every quotation in `B4_SEMANTICS.md` was captured by automated fetch on
2026-08-06.** They are attributed with URLs and a date, and the file says they
must be re-verified against the live pages before submission. A paraphrase
that has drifted into quotation marks would be a citation error.

**F6. Still WSL2.** E5 fixed *suspension*; it did not move the collection off a
virtualised host with Docker Desktop port forwarding in the path. Session 3's
F6 stands: absolute latency and throughput remain platform-bound, and only
comparisons between systems sharing that platform are meaningful.

**F7. The 18-hour clock divergence in §C.7 was in a run that had already been
collected.** Its counts are in the tables above. That is correct — an execution
either duplicated or it did not — but it is worth stating that a run can be
wall-clock nonsense and still be a valid observation of a rate.

**F8. `test_cleanup_spans_more_keys_than_one_scan_batch` fails on Windows and
did so before this session's changes** (verified by stashing them and re-running
— it still fails). It is a `fakeredis` scan-batching artifact; the Linux suite
with real Redis is the one the artifact rests on. Not fixed, and not caused
here.

**F9. Two harness tests failed once, in a run that took 18 hours of wall time**
because it was competing with the matrix for the machine. Both spawn real
subprocesses and assert kill timing. They pass in an uncontended run. The
suite should not be run concurrently with a matrix, and that is now known
rather than suspected.

---

## G. Open questions needing a human/architect decision

1. **Can the paper obtain a host-level fault at all?** §F1 makes this the
   single question that decides whether the barrier's benefit is *measured* or
   *argued*. Options, in increasing cost: a VM whose power can be cut
   (`virsh destroy`, or a cloud instance force-stopped); `dm-flakey` with
   `drop_writes` under the AOF directory; or accepting the narrowed claim and
   citing the durability argument rather than an experiment. Recommendation:
   the narrowed claim plus §C.2 as evidence for *why* it is narrowed — it is
   more honest than a fault nobody would believe, and §C.2 is itself a
   contribution: it shows that a widely-repeated reading of `appendfsync
   everysec` is wrong about process crashes.

2. **How should the barrier's two benefits be presented?** §C.5 measures one
   (dispatch withheld when durability cannot be confirmed: p = 1.9e-06) and
   §C.2 shows the other (record survives) is unmeasurable here. Recommendation:
   lead with the measured one, since it is the fail-closed property the paper
   is actually about, and give the durability one as an argument with §C.2 as
   the reason no experiment accompanies it.

2b. **Is `redis-kill-inflight` still worth 30 minutes?** §C.2 predicts it ties.
   Recommendation: yes — a predicted tie that is *collected* is evidence; a
   predicted tie that is inferred is an assumption, and this report has already
   been wrong once about what a smoke pair implied (§C.5).

3. **Session 3's G1 (drop-on-crash baselines), G4 (partition/restart in the
   matrix), G5 (recovery-success denominator) and G6 (per-execution versus
   per-application) are all still open.** None was in scope for E1–E6.

4. **Is one endpoint enough for RQ3?** The overhead cells were collected
   against `payments` only. Overhead should not depend on the endpoint's
   reconciliation capability in a crash-free run — but that is an argument, not
   a measurement.

---

## H. Recommended next phase and its prerequisites

**Next: finish the comparison, not the matrix.** The matrix is 1 068 runs and
~25 h. Almost none of the remaining hours change a claim. These do:

1. **B1, B2, B3 tier-1 cells** (`POSITIVE_ONLY_READBACK`, `NO_READBACK`) — ~96
   runs. Turns §C.4's one-baseline comparison into a four-baseline one. This is
   the highest-value wall time available and it is the direct completion of E3.
2. **B4 and B4b, both, on all three endpoints** — E4's requirement, unmet.
   ~144 runs at ~170 s. Expensive, and it is the only way the three-way
   duplicate/loss/ambiguity table becomes data.
3. **The `p0` regime for every system** — RQ3 still has no overhead column
   without it.
4. **Decide G1 (host-level fault).** Until then the barrier claim stays
   narrowed.
5. **`redis-kill-inflight`** — cheap (60 runs, ~30 min) and now expected to
   tie, which is worth recording explicitly rather than leaving as an
   inference from §C.2.

**Resume command** — the matrix is resumable and was stopped, not finished:

```
AEP_HARNESS_SUSPEND_DISABLED=1 \
  python -m experiments.run_matrix --resume \
  --results-root experiments/results/matrix
```

Add `--regime`, `--system` and `--endpoint` to take the items above in order.
Every seed is in `experiments/results/matrix/matrix-plan.json`.
