# WS-6 — B5 Temporal baseline, primary stage, session 1

**Collected 8 September 2026, 09:06:38 – 11:11:52 UTC.** Attempt 2 of the 3 the
pre-registration allows. Attempt 1 is voided and kept at
`VOIDED-b5-s1-2026-09-08-attempt1`; see
`reports/phase-report-ws6-attempt1-voided-2026-09-08.md`.

**No analysis has been run on this data.** `analyse_b5_agreement.py` has not been
executed, no rate has been computed, and no hypothesis has been read. What is
recorded below is the run count, the verdict column and the environment —
nothing that could make a later void decision outcome-dependent. The verdict
column is instrument health, which is why it is here; the outcome fields are in
the data and were not looked at.

## What was collected

Exactly what `1fecb1f` §3.1 pre-registered, at the 4000 ms Start-To-Close fixed
in `06d51b0` before any B5 data existed:

| | |
|---|---|
| stage | primary |
| crash point | `after_barrier_before_dispatch` (one point, both endpoints) |
| arms | `B5_TEMPORAL` (`maximumAttempts` unlimited), `B5B_TEMPORAL_AT_MOST_ONCE` (`maximumAttempts = 1`) |
| endpoints | `ledger_postings` (NO_READBACK), `payments` (AUTHORITATIVE_READBACK) |
| runs | **120** — 4 cells × 30 |
| executions per run | 10 |
| Start-To-Close | 4000 ms |

Per-cell run counts, all exactly 30:

```
  30  B5B_TEMPORAL_AT_MOST_ONCE  after_barrier_before_dispatch  AUTHORITATIVE_READBACK
  30  B5B_TEMPORAL_AT_MOST_ONCE  after_barrier_before_dispatch  NO_READBACK
  30  B5_TEMPORAL                after_barrier_before_dispatch  AUTHORITATIVE_READBACK
  30  B5_TEMPORAL                after_barrier_before_dispatch  NO_READBACK
```

## Completeness, against the pre-registration §4

| §4 void condition | Observed |
|---|---|
| run count short | **no** — 120 of 120 recorded, 120 run directories |
| engine or provider restarted mid-collection | **no** — `RestartCount=0` on both containers, exit 0, no OOM, zero `container restart` events in the observer log, and 0 runs whose provider never became healthy |

`stage-primary-finished.json` records `{"runs": 120}`; the driver logged
`### primary rc=0`. **This is a complete session.**

## Verdicts — instrument health only

```
 118  COMPLETED
   2  VOID_WORKER_NEVER_READY
   0  PENDING_AT_DEADLINE
```

The two voids are at sequence positions 10 and 21 (`b5_temporal-…-r9` and
`…-r20`), both in the first cell, both with an empty `worker.err` — the worker
did not signal ready within the spawn window, and `collect.py` retries once
before voiding. They are **excluded from every rate** by
`analyse_b5_agreement.py`'s `VOID_` prefix rule rather than counted as zeros.
Attempt 1 produced none in its 39 runs, so this is a difference between the two
launches that is recorded here and not explained.

`VOID_ATTRIBUTION_UNAVAILABLE` did **not** appear. It was watched for: the
crash-point binding proof saw it at the two earliest crash points under a
2-execution configuration, and the standing instruction was to stop rather than
collect through it on this stage. It did not occur in any of the 120 runs.

## The crash-point binding

Each record carries both:

* `crash_point` — the **roadmap** name, `after_barrier_before_dispatch`, which is
  the vocabulary `analyse_b5_agreement.py` keys the frozen B4 comparison on;
* `armed_point` — B5's own `ACTIVITY_ENTERED_BEFORE_CALL`, what the injector was
  armed at.

Attempt 1 wrote the second into the first's place, so every cell would have found
no frozen counterpart. Fixed and proven at `593ea64`; the runner refuses any run
whose label and armed point disagree.

## What is here, and what is not

Committed: `b5-runs.jsonl`, `plan-primary.json`,
`stage-primary-finished.json`, `measurement-host.txt`, the compose file, the
provider template, `collected-at-commit.txt`, the observer logs
(`observers/`), and per run `events.jsonl`, `trace.jsonl`, `b5-run.json`,
`mock-api.yaml`, `worker.err`, `provider.err`.

The five observer logs are published as `*.log.txt`. `.gitignore` excludes
`*.log`, and these are the evidence for §4's "no engine restart" condition, so
they are renamed rather than forced past the ignore rule — the original name
stays legible in the new one, and the archive keeps the files under their
original names.

**Not committed:** the per-run `ground_truth.sqlite3*` ledgers and
`ground_truth.run.jsonl`. `.gitignore` excludes them and raw run directories are
published as an archive rather than committed — the same treatment
`252e2d3` gave WS-4. The complete tree including every ledger is mirrored at
`aep-raw-archive/ws6-b5-s1-2026-09-08` (1454 files, 62 MB).

`SHA256SUMS` digests all 974 committed files. Manifest digest:

```
aacab9a0c2acec13f5ab792b20d07739de8d1bd4964907203b3005403b76379c
```

`b5-runs.jsonl`: 120 lines,
`9c941dce724157fa06a89005790e0664532470a928bcbb13bae616366bceb736`.

## Provider configuration

Written explicitly by the collection script rather than inherited from whatever
was on disk, and verified **byte-identical** to the configuration all 40 runs of
the voided attempt 1 ran under: constant 2.0 s delay, 5% server errors, 15%
timeouts, 0% duplicate responses, seed 20260908, `CALLER_REFERENCE` readback
keying. No knob was tuned between attempts.

## Host

`measurement-host.txt` carries the machine-readable environment recorded before
any run. The collection ran detached (`setsid`+`nohup`, PID recorded per R1)
with the WSL keepalive held, which is what attempt 1 lacked.
