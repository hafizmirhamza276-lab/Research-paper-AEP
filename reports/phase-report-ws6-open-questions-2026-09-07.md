# WS-6's five open questions: one closed, four still open

`1fecb1f` listed five questions that must close before any B5 data commit. This
pass closed **one** with evidence and left **four open**, with the blocker for
all four now established rather than suspected.

**No data was collected.** No run directory was written, no B5 rate exists, and
`scripts/analyse_b5_agreement.py` was not written.

**The pre-registration was not changed.** The blocker found is in the instrument,
not in the hypothesis, so there was nothing to adjust — and had there been, the
adjustment would not have been made in this pass.

---

## Q1 — image digests: **CLOSED**

Resolved 2026-09-07T12:36:38Z, pinned in `compose.temporal.yml` in the form
`compose.phase2.yml` uses for redis and toxiproxy:

| tag | digest |
|---|---|
| `postgres:16.3` | `sha256:d0f363f8366fbc3f52d172c6e76bc27151c3d643b870e1062b4e8bfe65baf609` |
| `temporalio/auto-setup:1.24.2` | `sha256:10e8c557ace5fa4aa99217637e7b9969316e89b929a3bfb117853a5417eef25c` |
| `temporalio/ui:2.26.2` | `sha256:bb9e9bc2ecb4962f43ef72b7f03a3d3f22f0df3eb5ec7c409bcae3d0135b88bc` |

**Evidence, and why it is this evidence.** A digest read back from the local
image store only proves what was pulled, not that the pinned reference *works*.
The proof is that the stack was brought up **from the pinned file** and the
running containers report the pinned digests:

```
aep-ws6-postgres   image ref: postgres:16.3@sha256:d0f363f8366f…baf609
                   running  : sha256:d0f363f8366f…baf609
aep-ws6-temporal   image ref: temporalio/auto-setup:1.24.2@sha256:10e8c557ace5…ef25c
                   running  : sha256:10e8c557ace5…ef25c
```

Both containers reached `healthy`. A digest that did not resolve could not have
started a container.

**One thing not established.** `docker manifest inspect` against the registry
hung and was abandoned, so these digests are confirmed *resolvable and running
on this host*, not confirmed to be what the registry serves that tag today. For
pinning purposes that is sufficient — the point of a pin is that this exact image
is used regardless of what the tag later points at — but it is not a check that
the tag was un-tampered at pull time.

---

## Q2 — Start-To-Close timeout: **OPEN**

This is the question the pre-registration says "can invalidate the
pre-registration rather than merely delay it", so it gets the plainest possible
statement: **it was not settled, and no number was chosen.**

**What was measured.** The provider's fault configuration was read from the WS-4
collection's own `mock-api.yaml` rather than invented: constant delay **2.0 s**,
`timeout_probability` **0.15**, `server_error_probability` **0.05**. So a timeout
must clear a 2 s floor on every call, and 15% of calls do not answer at all.
That much is now known and is a real input to the eventual choice.

**What was not measured.** The 40-sample latency distribution and the
retry-lands-inside-the-run test both require workflows that execute. They did
not (Q5). No timeout value was chosen, and **none will be chosen from
documentation** — the pre-registration says by measurement, and that stands.

---

## Q3 — the 120 s recovery deadline: **OPEN, blocked on Q2**

Cannot be answered before Q2. The arithmetic that will answer it is unchanged:
a run must fit the 2 s provider floor, the Start-To-Close timeout, the retry
backoff and the second attempt inside the deadline, or every run is
`PENDING_AT_DEADLINE` and the cell is uninformative by the pre-registration's own
20% rule.

---

## Q4 — is point 6's race observable on loopback: **OPEN**

`after_resolution_before_barrier` maps approximately to dying during the
`RespondActivityTaskCompleted` RPC. `worker.py` implements it as a watchdog armed
on the last instruction before the activity returns. **Whether the kill lands
inside that RPC is unknown**: no activity ever completed, so the race was never
run. If it turns out unhittable, `B5_SEMANTICS.md` §2.1 must be corrected to mark
point 6 absent rather than approximate.

---

## Q5 — the crash injector against an SDK worker: **OPEN, and this is the blocker**

### What was found

The injector decides whether to die by reading an environment variable. Inside
**activity** code that is ordinary Python. Inside **workflow** code it is not:

```
temporalio.worker.workflow_sandbox._restrictions.RestrictedWorkflowAccessError:
    Cannot access os.environ.get from inside a workflow.
  worker.py:210  _maybe_die("BEFORE_SCHEDULE_ACTIVITY")
  worker.py:128  if os.environ.get("B5_CRASH_POINT") != point:
```

Temporal's workflow sandbox forbids environment access in workflow code, because
a workflow must be deterministic on replay and the environment is not. The
injector's own mechanism is therefore illegal at the one crash point that lives
in workflow code — `BEFORE_SCHEDULE_ACTIVITY`, which is B5's mapping for
`before_intent_write`.

### Why this is worse than a crash, and is the point of the exercise

**The failure is silent in the unsafe direction.** The workflow task failed, and
Temporal did what it is designed to do: retried it, indefinitely. From the
caller's side the workflow simply never finished. The server-side workflow list
showed nothing completed, the trace showed a worker connected and running, and
the run looked exactly like `PENDING_AT_DEADLINE` — **an outcome the
pre-registration defines as a legitimate measurement result.**

So a B5 session run today would have recorded a stream of `PENDING_AT_DEADLINE`
runs at that crash point and reported them as data. It would have taken the 20%
uninformative-cell rule to notice, and that rule would have blamed the timeout
rather than the injector.

**This is exactly the WS-4 self-test lesson, and it is why the question was asked
this way.** An injector exercised only where it works approves one that does not.
Here the injector was exercised at the *first* point in the list and failed, and
still produced no error visible to the caller.

### The gate does not yet exist

The pre-registration required showing that *"a worker it cannot reach refuses the
run rather than proceeding"*. **It does not refuse.** It hangs, and the hang is
indistinguishable from a legitimate outcome. There is no gate here to prove able
to fail, because there is no gate.

That is the first task of the next pass, and it is now a design constraint rather
than a checkbox: the injector must **prove it reached the named point** and the
run must be **voided when it did not**, distinguishable from a genuine
`PENDING_AT_DEADLINE`.

### The known fix, recorded and deliberately not applied

Read `B5_CRASH_POINT` **once at module import**, outside workflow code, into a
module constant; the workflow-side check then compares a constant rather than
touching the environment. Activity-side points are unaffected — activities are not
sandboxed.

**Not applied in this pass**, because applying it means re-running the probe to
find out whether the four activity-side points then work, and that is a second
cycle. One pass, as instructed.

### What is consequently unknown

The four activity-side points — `ACTIVITY_ENTERED_BEFORE_CALL`,
`DURING_PROVIDER_CALL`, `AFTER_RESPONSE_BEFORE_RETURN`, `DURING_COMPLETE_RPC` —
are **untested**. They are not blocked by the sandbox in principle, but nothing
here demonstrates any of them, and after this finding no such claim should be made
without a run.

---

## A defect in the probe, found the same way

The probe's readiness check and the worker's provider call both used routes that
do not exist: `POST /{endpoint}` and `GET /healthz`, where
`experiments/mock_api/service.py` serves
`POST /v1/endpoints/{name}/mutations` with the caller reference in an
`X-Aep-Client-Reference` header, and `GET /v1/health`.

The readiness check reported `provider up: 000` and the probe **proceeded
anyway** — a check that could only report "not ready" and never "I am asking the
wrong question". Corrected in both files against the service source. This is the
third instance this session of the checking code being weaker than the code it
checks (`856d78a` §3, `docs/25` R13).

---

## Environment change: a new `b5` extra

`temporalio` was not in the project. It is added as its **own** optional extra,
not appended to `experiments`:

```toml
b5 = ["temporalio>=1.7,<2"]
```

Every frozen cell was collected with the `experiments` extra as it resolves
today, and adding a dependency there would change the environment of collection
paths that produced results already in the manuscript, for a baseline none of
them use.

**Verified against the lock file**: 4 packages added (`temporalio`, `protobuf`,
`nexus-rpc`, `types-protobuf`), **0 changed, 0 removed**. No existing dependency
moved.

---

## Teardown

R8a — evidence preserved *before* teardown, under `/var/tmp/b5-evidence`: worker
stderr and stdout, both traces, the diagnostic transcript, the probe transcript,
and the Temporal server log.

R8 — verified, not asserted:

```
ws6 containers left      : 0
port 7233 / 8233 / 8099  : free / free / free
redis-data volume present: 1
```

R12 — all three ports this stack used were checked for orphaned listeners before
bring-up and after teardown; 8099 was found free at both ends. `docker compose
down` was run without `-v`.

---

## Status

| Question | Status |
|---|---|
| Q1 image digests | **CLOSED** — pinned, and the stack ran from the pins |
| Q2 Start-To-Close timeout | **OPEN** — provider fault profile known; no value chosen; blocked on Q5 |
| Q3 120 s recovery deadline | **OPEN** — blocked on Q2 |
| Q4 point 6 race on loopback | **OPEN** — never exercised |
| Q5 injector against an SDK worker | **OPEN** — sandbox forbids the mechanism at the workflow-side point, and the failure is silent |

**WS-6 remains not ready to collect**, and the pre-registration's requirement
that all five close before the first data commit stands unchanged.
