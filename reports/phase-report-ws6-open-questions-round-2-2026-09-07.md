# WS-6 open questions, round 2: the sandbox fix works; two questions closed, three not

Second pass. **No data was collected**, no run directory was written, and
`analyse_b5_agreement.py` was not written. **The pre-registration was not
changed.**

The headline is honest rather than tidy: the sandbox fix works and is proven, the
gate is built, and the provider distribution is finally measured correctly — but
the probe did not run to completion, so the gate's two branches and three of the
five crash points are **still not demonstrated**, and I am not claiming them.

---

## Q5a — the sandbox fix: **CLOSED**

`worker.py` now reads the injector's variables **once at module import**, outside
any workflow, into module constants. The workflow sandbox is additionally
disabled via `UnsandboxedWorkflowRunner`, because the injector must also write a
trace line and `SIGKILL` itself from inside workflow code and both are I/O the
sandbox forbids for the same reason.

**Evidence.** `BEFORE_SCHEDULE_ACTIVITY` is the workflow-side point that
previously raised `RestrictedWorkflowAccessError` and hung forever. In two
independent probe runs it now reports:

```
BEFORE_SCHEDULE_ACTIVITY   reached=True  fired=True
```

**The trade, recorded not buried.** The sandbox is what mechanically catches
workflow nondeterminism. `B5Workflow` is one activity call with no clocks, no
randomness and no I/O of its own except the injector — so there is little for it
to catch, but "little" is not "nothing", and **B5's workflow determinism is now
argued rather than machine-checked.** That belongs in `B5_SEMANTICS.md` §6 before
any collection.

## Q5b — the gate: **BUILT, NOT PROVEN**

`experiments/baselines/b5_temporal/gate.py` exists and is a pure function over
the trace, so it is testable without a Temporal server. It distinguishes exactly
what the previous pass could not:

| verdict | measurement? |
|---|---|
| `COMPLETED` | yes |
| `PENDING_AT_DEADLINE` | yes — the pre-registered third outcome |
| `VOID_INJECTOR_NEVER_REACHED` | **no** — instrument failure |
| `VOID_INJECTOR_DID_NOT_FIRE` | **no** |
| `VOID_WORKER_NEVER_READY` | **no** |

The mechanism is positive evidence: `_maybe_die` records `b5_point_reached`
*whether or not it fires*, and a run armed at a point with no such record voids
with a reason **naming the injector and explicitly not the deadline**.

**But rule 13 is not satisfied.** The probe died before reaching the both-branch
proof, so I have **not** shown a run where the injector reaches and the gate is
silent alongside a run where it cannot reach and the gate voids. The failing
branch is implemented (`B5_INJECTOR_DISABLED=1`) and wired into the probe, and it
has not been executed. **By this project's own standard that gate is unproven
and must not be trusted yet.**

## Q5c — the five crash points: **3 of 5 demonstrated**

| point | reached | fired |
|---|---|---|
| `BEFORE_SCHEDULE_ACTIVITY` | **yes** | yes |
| `ACTIVITY_ENTERED_BEFORE_CALL` | **yes** | yes |
| `DURING_PROVIDER_CALL` | **yes** | yes |
| `AFTER_RESPONSE_BEFORE_RETURN` | **not demonstrated** | — |
| `DURING_COMPLETE_RPC` | **not demonstrated** | — |

The first three are from the run whose provider envelope was still invalid — which
does not affect them, since reaching a crash point does not depend on the
provider answering. The last two sit *after* the provider call, so that run could
not speak to them, and the corrected run stopped before printing them.

## Q2 — the Start-To-Close timeout: **HALF CLOSED**

**The provider distribution is now measured correctly**, and it took two wrong
measurements to get there:

```
n=30  answered=22  timed_out=3  refused={503: 5}
p50=2015.0 ms   p95=2024.2 ms   max=2059.0 ms
```

This matches the configured profile exactly — 2.0 s constant delay, 15% timeout,
5% server error — which is the check that the number is of the provider rather
than of some rejection path.

**A Start-To-Close timeout must therefore clear ~2.06 s** to avoid firing on a
healthy call, and the 15% of calls that never answer will hit it by design.

**Still open: no timeout value is chosen**, because choosing one requires the
Q2b measurement — does the retry actually land inside the run — and that did not
execute. Per the instruction, no value is being inferred from the distribution
alone.

**H1's testability is therefore still unestablished, and the pre-registration
stands unchanged.** Nothing here is evidence that H1 is untestable; it is
evidence that the question is not yet answered.

## Q3 — the 120 s recovery deadline: **OPEN**

Blocked on Q2b. The arithmetic is now partly grounded — a ~2.06 s provider floor
and a timeout above it — but the retry-completion time was not measured.

## Q4 — point 6's race on loopback: **OPEN**

Not exercised. `B5_SEMANTICS.md` §2.1 still marks `after_resolution_before_barrier`
**approximate**, and that mapping is **unchanged** because nothing was learned
that would justify changing it. If it later proves unhittable it becomes a second
**absent** point, which would change what the comparison can claim — so it is
left as an open question rather than quietly downgraded.

## Q1 — residual, as instructed

The three digests are pinned and **confirmed running on this host** — both
containers report the pinned digest as their running image and reach `healthy`,
twice. They are **not confirmed against the registry**: `docker manifest inspect`
hung and was abandoned, and was **not retried in this pass**. Recorded as a
residual on the pin, not as a defect in it.

---

## The fourth and fifth instances of the same pattern — now `docs/25` R14

The instruction said to note the fourth instance and make it a rule. Writing it
up surfaced a fifth, in the same probe:

* The readiness check polled `/healthz`, which does not exist. It reported `000`
  and **the probe proceeded anyway** — it could say *"not ready"* but never *"I am
  asking the wrong question"*.
* The latency sampler counted any non-5xx as a healthy sample. Thirty consecutive
  `422 unidentifiable envelope` refusals, returned in **1.8 ms**, were recorded as
  a provider p50 of **8.6 ms** — against a provider configured with a **2 s**
  delay. Then, after adding three of the four required envelope keys, it produced
  `refused={422: 30}` again, because `target` is required at the top level too.

Both were caught the same way every previous instance was: a number looked wrong
against something already known by hand. Neither was caught by the instrument.

**`docs/25` R14** now records all five instances and states the rule: a checking
instrument must be able to report *three* outcomes — the thing is there, the
thing is not there, and **I could not look, or I looked in the wrong place** —
because one that can only express the first two will express the second when the
third is true, and the second is the answer that lets work proceed.

R14's concrete clauses are each one of the five: never let *not found* and *could
not ask* render the same; assert on the output you showed, not a fresh
invocation; compare like with like; check the success shape (`2xx`), not the
absence of an error shape (`< 500`); and readiness checks fail closed and say
which.

---

## Environment and teardown

`temporalio` remains its own `b5` extra — 4 packages added to the lock, **0
changed, 0 removed**, so the frozen collection environment is untouched.

R8a — evidence preserved before teardown under `/var/tmp/b5-evidence`: worker
stderr, traces, all four probe transcripts, the Temporal server log.
R8 — verified, not asserted: `ws6 containers left 0`, ports 7233/8233/8099 all
free, `redis-data` volume intact. R8b/R12 — `compose down` without `-v`, and all
three ports checked for orphaned listeners at both ends of the pass.

---

## Status

| Question | Status |
|---|---|
| Q1 digests | **CLOSED**, with a recorded residual (registry unverified) |
| Q5a sandbox fix | **CLOSED** — proven on the workflow-side point |
| Q5b the gate | **BUILT, NOT PROVEN** — rule 13's both-branch proof did not run |
| Q5c five points | **3 of 5** demonstrated |
| Q2 timeout | **HALF** — distribution measured; no value chosen |
| Q3 deadline | **OPEN** — blocked on Q2b |
| Q4 point 6 | **OPEN** — mapping unchanged |

**WS-6 remains not ready to collect.** The next pass needs one probe run to
completion: the gate's two branches, the two remaining crash points, the
retry-lands measurement, and point 6's race.
