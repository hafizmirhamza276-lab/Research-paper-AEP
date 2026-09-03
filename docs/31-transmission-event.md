# The transmission event, and the digest constraint it ran into

**Phase 13 prerequisite. 2026-09-03.** Both arms of Phase 13 need each arm's
post-arming exposure measured rather than argued, and neither could be collected
until the harness could witness the moment provider bytes leave.

---

## 1. What the event marks, precisely

`provider_request_transmitted` is emitted on **entry to
`MockLegacyApiConnector.mutate`**.

That call is the instruction **immediately after**
`await self._checkpoint("AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION")`
(`aep_core/core/intent_workflow.py:579`) and **before** the exact request bytes
are constructed, let alone sent — `mutate` calls `consume_verified_dispatch`
first and only then `transmit`.

The workflow states the same boundary from the other side, at
`intent_workflow.py:574-578`:

> a process cut before this line has provably not dispatched; a process cut
> *after* this line may have.

So the event is **the last observable point at which no provider byte can have
left** — an instruction boundary, not an approximation of one. A second event,
`provider_response_received`, closes the interval, and
`provider_request_failed` records the exception path with its elapsed time, so
the transmission is measurable rather than inferred from the ends of a run.

## 2. It changes no protocol behaviour

`TransmissionObserver` (`experiments/harness/injector.py`) is a passthrough:

* every attribute other than `mutate` is delegated untouched by `__getattr__`,
  so read-back, `aclose` and anything added later reach the real connector;
* `mutate` returns exactly what the wrapped connector returned;
* exceptions are **re-raised as themselves**, caught as `BaseException` so the
  simulated process death the crash injector raises passes through rather than
  being swallowed. This matters more than it looks: `intent_workflow.py:616-624`
  classifies a connector exception as `AMBIGUOUS`, so a wrapper that retyped one
  would silently change an execution's outcome class.

Six tests pin exactly these properties
(`experiments/harness/tests/test_transmission_observer.py`), including that the
event **precedes** the connector call in program order and that a `BaseException`
is not caught.

## 3. It changes no existing cell's comparability

Two independent reasons, and the first is the one that matters.

**It is attached only where a fault injector already exists**
(`experiments/harness/worker.py`), gated on the same condition as
`DurabilityAckObserver` and for the same documented reason: `EventLog.emit`
serialises and flushes — a real syscall, 5.4 µs median on ext4 — and it would
otherwise sit on the dispatch path of the crash-free `p0` cells, which are the
only cells RQ3's cost numbers may use. Fault-bearing cells already carry the
observer machinery, so nothing about their conditions moves.

**It adds no field to `RunConfig`, so no `config_digest` changes.** Verified
end to end rather than argued: `make reproduce-smoke` exits 0 across all seven
systems under real `SIGKILL`, and the event appears in exactly the runs that
reached transmission.

```
{"event": "provider_request_transmitted",
 "execution_id": "da459fa7-40e5-469b-9696-2232e8f97c20",
 "intent_id": "df6709ca-44da-4f90-a860-9e75a8ae1d3f",
 "monotonic_ns": 85400708728408, "pid": 2309,
 "run_id": "aep_full-mid_dispatch-notifications-ea8836a3-r0",
 "seq": 6, "source": "worker-0#1", "step_id": "charge-card",
 "wall_iso": "2026-09-03T09:17:36.237992+00:00"}
```

The five baseline runs at `mid_dispatch` carry **no** event, which is correct
and is the check working: those systems are killed before transmission, so there
is nothing to witness.

**`aep_core/` was not touched.** `git status aep_core/` is empty. The only
changed files are `experiments/harness/injector.py` and
`experiments/harness/worker.py`.

---

## 4. The constraint this ran into, and the pre-existing defect it exposed

The obvious way to select a fault mechanism per regime is a new `RunConfig`
field. **It cannot be done**, and the reason is measurable.

`RunConfig._body()` iterates `fields(self)`, and `config_digest` is a SHA-256
over that body. `run_config_from_mapping` rebuilds a config from a saved
document, recomputes the digest **over the current field set**, and raises if it
differs. So adding any field changes the digest of every run ever collected.

Checking the frozen collections directly:

```
matrix                             ok= 282 failed= 150
fsync-always                       ok=   6 failed=   0
b2-paired-v2-s1-2026-08-28         ok= 120 failed=   0
b2-2026-08-21                      ok=  60 failed=   0
ext4-2026-09-02                    ok=  18 failed=   0

distinct sets of absent fields among the failures:
   150 runs missing ['redis_kill_delay_ms', 'redis_kill_executions',
                     'redis_kill_point', 'suspend_disabled_declared']
```

> **150 of the 432 frozen `matrix` runs — 35% of the collection every outcome
> rate in the paper is computed from — cannot be re-read through
> `run_config_from_mapping`, because they fail their own digest check.**

**This is pre-existing and is not caused by this phase.** The absent fields are
`redis_kill_point`, `redis_kill_delay_ms`, `redis_kill_executions` (amendment
E1) and `suspend_disabled_declared` (amendment E5) — all of which were added to
`RunConfig` long before Phase 13, and all of which post-date those 150 runs.
This phase added **no** field: `experiments/harness/config.py` is unmodified,
and every root collected after E1/E5 verifies 100%.

**What it does and does not break.** `experiments/analyze.py` reads the run
config directly rather than through `run_config_from_mapping`, which is why the
matrix still analyses to 432 runs and why Phase 11's archive verification
reproduced every tracked product. What is broken is the **self-check**: the
digest exists to prove a run's configuration was not altered after collection,
and on 35% of the paper's core evaluation that proof cannot be run — not because
anything was altered, but because the digest is computed over the current field
set rather than the recorded one. The same defect is what produced the
`ValueError: the saved run configuration does not match its own digest` that
`matrix-progress.jsonl` recorded at collection time.

**Recorded, not fixed.** A fix — digesting over the recorded key set, or
versioning the body — would change the digest of runs that currently verify, and
that is a decision about the frozen artifact rather than a Phase 13 change.

### The consequence for Phase 13's two regimes

Neither arm may add a `RunConfig` field. The mechanism must be selected and
recorded the way Phase 8.2 and Phase 10 added `results_root_filesystem` and
`docker_kill_latency`: **in the `environment` block**, which `echo()` adds and
`config_digest` excludes, so it is recorded in every run and changes no digest.
