# The Phase 2B fault-injection harness

`PAPER_ROADMAP.md` §3.1(2–3). Crash points, real OS processes, real SIGKILL,
real Redis, a real HTTP provider with a ground-truth oracle, and one JSONL run
log that is cross-checked against that oracle before any number is believed.

```
python -m experiments.harness \
  --run-id my-run --seed 20260805 \
  --workers 3 --executions-per-worker 10 \
  --crash-point mid_dispatch --crash-probability 0.4 --crash-delay-ms 400 \
  --readback-keying CALLER_REFERENCE \
  --endpoint payments \
  --mock-api-config-path experiments/results/selfcheck/mock-api.yaml \
  --mock-api-base-url http://127.0.0.1:8099 \
  --redis-url redis://127.0.0.1:6381/15 \
  --results-root experiments/results \
  --poisoned-executions 3
```

Exit status is `0` only if the run log and the ground-truth ledger agree.

## Preconditions

1. `docker compose -f compose.phase2.yml up -d --wait` — Redis 7.2 with AOF,
   and toxiproxy for the partition fault.
2. A MockLegacyAPI running against the configuration you pass:
   `python -m experiments.mock_api --config <yaml> --host 127.0.0.1 --port 8099`.
3. The Redis instance must advertise `aep:test-instance-marker`. The harness
   kills processes holding leases on it and deletes the keys it created, so it
   refuses to run against an instance that has not asserted it is disposable:
   `redis-cli -n 15 SET aep:test-instance-marker 1`.

## The six crash points

The roadmap names positions in the protocol; `aep_core` names instruction
boundaries. `crash_points.py` holds both and the mapping, and a test asserts
the mapping against the `_checkpoint(...)` calls parsed out of the `aep_core`
sources — so a rename there fails a test rather than raising `KeyError` inside
a worker, mid-run, for one crash point.

| roadmap name | `aep_core` checkpoint | delivery |
|---|---|---|
| `before_intent_write` | `AFTER_LEASE_ACQUISITION_BEFORE_INTENT_CAS` | immediate |
| `after_intent_before_barrier` | `AFTER_INTENT_CAS_BEFORE_DURABILITY_BARRIER` | immediate |
| `after_barrier_before_dispatch` | `AFTER_DURABLE_ABOUT_TO_FIRE_BEFORE_PREFLIGHT` | immediate |
| `mid_dispatch` | `AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION` | **deferred** |
| `after_response_before_resolution` | `DURING_RESOLUTION_CAS` | immediate |
| `after_resolution_before_barrier` | `AFTER_RESOLUTION_CAS_BEFORE_DURABILITY_BARRIER` | immediate |

Five are positions the workflow executes, so the kill lands at the checkpoint.
`mid_dispatch` names an instant inside a socket wait, which the workflow never
executes: the injector arms a watchdog thread at the last pre-transmission
checkpoint, returns so the request really is sent, and the watchdog delivers
the kill while the connector is blocked. Whether the provider had already
applied the mutation is then **read from the ground-truth ledger**, not
assumed — `reconcile.py` reports the split.

Any canonical checkpoint name is also accepted. A name that is neither is a
`KeyError` at process start: a mistyped crash point that read as "no crash"
would produce a full, slow, entirely uninformative run whose own log claimed a
crash point was selected.

## Disabled means absent

No crash point selected ⇒ `ProcessCrashInjector.from_environment` returns
`None` ⇒ `WriteAheadRunner` receives `crash_injector=None` ⇒ the hot path is
one attribute load and one identity comparison per checkpoint. Measured at
**76 ns per checkpoint, 0.84 µs per execution** across eleven checkpoints —
three orders of magnitude below the millisecond-scale Redis round trips they
sit between. There is no "disabled injector" object that could grow behaviour
later. `tests/test_injector.py` asserts both the structure and a ceiling.

## EVALUATION mode only

`RunConfig` refuses to represent a run in `TEST` or `PRODUCTION` mode, and a
source gate fails if any harness module names a test authorisation. Every
worker records, in its own run log, which `allow_*` attributes its runner
carried — discovered from the object, so a future affordance would show up
without that line changing. **No harness path requires `TEST` mode.**

## What lands in `results/<run_id>/`

| file | what it is |
|---|---|
| `run-config.json` | the configuration workers were launched with |
| `events-runner.jsonl`, `events-worker-N-attempt-M.jsonl`, `events-recovery.jsonl` | per-process shards, flushed on every record so a SIGKILL loses nothing |
| `events.jsonl` | the merged, wall-ordered timeline |
| `summary.json` | the reconciliation against the ground-truth ledger |
| `recovery-stdout.log`, `recovery-stderr.log` | the recovery process's own output |

Every record carries `wall_ms` (comparable across processes, the merge order)
and `monotonic_ns` (cannot go backwards inside a process, what durations come
from). They are not comparable to each other, so each log opens with a
`clock_reference` record pairing them at a known instant.

`events.jsonl` opens with `run_started`, which carries the whole run
configuration, the whole mock API configuration including its digest, every
seed, the workload plan, and whether this platform delivers a real `SIGKILL`.

## The reconciliation

`reconcile.py` is the second half of amendment C4: the run log knows what the
protocol *decided*, the ledger knows what the world *did*, and neither can see
the other. Effects are attributed to executions by target — every execution
mutates its own resource — so an execution whose worker died before recording
anything is still attributable.

A run "agrees" only if all of:

* every applied mutation is attributable to a planned execution;
* no `FAILED_CONFIRMED` execution applied anything *(the strongest check: a
  definitive no-effect contradicted by the ledger would be the protocol
  lying)*;
* every `FIRED_CONFIRMED` execution applied at least one effect;
* no effect exists for an execution that never wrote a durable intent;
* the number of changed resources lies between what the protocol was certain
  of and what it could not rule out;
* the duplicate-group count matches what the configuration predicts.

Executions in a declared-ambiguous state may have applied zero or one effect.
That freedom is the point: the protocol converts a silent guess into a declared
unknown, and the ledger is allowed to disagree with an uncertainty the protocol
never claimed to resolve.

## Infrastructure faults

* **Redis restart** — `docker compose restart`, then *verified* AOF replay: a
  probe key is written through the same `WAITAOF` barrier the protocol uses,
  the container is restarted, and the key is read back. `INFO persistence` is
  checked too, but the probe is load-bearing: `aof_enabled` and `loading` both
  look healthy on a server that came back empty.
* **Worker↔Redis partition** — a toxiproxy `timeout` toxic with `timeout: 0`
  on the upstream stream: data stops and the connection is *not* closed, so the
  client is left waiting while its lease expires. The proxy is declared in
  `redis/toxiproxy.json` and created at container start, so a run cannot
  proceed against a proxy that was never made.

## Poisoned executions

`--poisoned-executions N` writes N corrupt state payloads at recorded instants.
The recovery service isolates each one and the harness consumes its
`scan_failure_alert` stream, turning the pair into a **detection latency** —
which retires `reports/phase-report-1b-2026-08-05.md` §F7 ("nothing in the
repository consumes any of those") by measuring it rather than asserting it is
small.

Note: a quarantined payload is never removed by the protocol, so a poisoned
execution is re-isolated on every subsequent scan pass. That is correct — an
operator is meant to find them — and the harness deletes the quarantine records
it caused at the end of a run.
