# WS-6 — B5 Temporal baseline, primary stage, CORRECTED cell

**Collected 8 September 2026, 12:55:04 – 14:43:57 UTC.** Attempt 3, and the
first attempt against the **corrected** harness. Registered in advance by
`reports/phase-report-ws6-prediction-corrected-2026-09-08.md`, committed at
`4f31c42` before this session existed.

**No analysis has been run on this data.** `analyse_b5_agreement.py` has not been
executed. Only the run count, the verdict column, the environment and
`provider_seed` were inspected during collection — the last being configuration
the runner echoes back, not an outcome, which is what keeps a void decision
outcome-independent. **Per-run duplicate and lost-effect counts were
deliberately not read**; the identical-runs check belongs to the analysis pass.

## Why this session exists

The 2026-09-08 session at `0c6bcf4` ran all 120 runs on one fixed provider seed,
so every run replayed a single fault stream and three of four cells produced one
distinct outcome across thirty runs. That session is kept, unamended, at
`reports/raw/ws6-b5-s1-2026-09-08`, and read in
`reports/phase-report-ws6-determinism-2026-09-08.md`. It is not superseded — it
is the record of a harness that was too deterministic.

## The repair, visible in this data

Each run's provider is seeded from that run's own `RunConfig.seed` via
`mock_api.supervisor.render_config`. Every record carries `seed` and
`provider_seed`, the latter read back from the config the provider was actually
handed.

| cell | runs | distinct `provider_seed` | range |
|---|---|---|---|
| `B5_TEMPORAL` AUTHORITATIVE | 30 | **30** | 20260908–20260937 |
| `B5_TEMPORAL` NO_READBACK | 30 | **30** | 20260908–20260937 |
| `B5B` AUTHORITATIVE | 30 | **30** | 20260908–20260937 |
| `B5B` NO_READBACK | 30 | **30** | 20260908–20260937 |

One seed per run, distinct within every cell. The same thirty values recur
across cells **by design**: repetition *r* uses `base + r` in each, which makes
the arms a paired comparison under matched fault streams. Distinctness is
required *within* a cell, which is where the bootstrap clusters.

The records also carry **both** duplicate counts —
`undetected_duplicate_applications` and `undetected_duplicate_executions` — so
the record says which is which. H1's comparison uses the executions-based field,
matching the frozen B4 numerator; H2 was already units-consistent and is
unchanged.

## What was collected

Exactly what the corrected re-registration specifies, unchanged from `1fecb1f`
§3.1:

| | |
|---|---|
| stage | primary |
| crash point | `after_barrier_before_dispatch`, both endpoints |
| arms | `B5_TEMPORAL` (unlimited attempts), `B5B_TEMPORAL_AT_MOST_ONCE` (1) |
| runs | **120** — 4 cells × 30 |
| executions per run | 10 |
| Start-To-Close | 4000 ms, the value fixed in `06d51b0` |

## Completeness, against the pre-registration §5

| void condition | observed |
|---|---|
| run count short | **no** — 120 of 120, 120 run directories |
| engine or provider restarted mid-collection | **no** — `RestartCount=0` on both containers, exit 0, no OOM, zero restart events, 0 runs whose provider never became healthy |

`stage-primary-finished.json` records `{"runs": 120}`; driver logged
`### primary rc=0`. **This is a complete session.**

## Verdicts — instrument health only

```
 118  COMPLETED
   2  VOID_WORKER_NEVER_READY
   0  PENDING_AT_DEADLINE
```

Neither named stop condition occurred: **`VOID_ATTRIBUTION_UNAVAILABLE` = 0** and
**`VOID_CRASH_POINT_MISMATCH` = 0**.

### The two voids, recorded and not chased

Handoff §7 carries these as an open question from attempt 2. They recurred at the
same count:

| position | run |
|---|---|
| 10 | `b5_temporal-…-ledger_postings-r9` |
| 40 | `b5b_temporal_at_most_once-…-ledger_postings-r9` |

Both are **repetition r9**. Attempt 2's two were r9 and r20. That r9 appears in
both attempts is recorded as a fact about positions and **deliberately not
investigated** — the open question stands, now with a third and fourth
occurrence and a coincidence worth a later look. Both are excluded from every
rate by the `VOID_` prefix rule rather than counted as zeros.

## What is here, and what is not

Committed: `b5-runs.jsonl`, `plan-primary.json`,
`stage-primary-finished.json`, `measurement-host.txt`, the compose file, the
provider template, `collected-at-commit.txt`, `observers/`, and per run
`events.jsonl`, `trace.jsonl`, `b5-run.json`, `mock-api.yaml`, `worker.err`,
`provider.err`.

**Not committed:** per-run `ground_truth.sqlite3*` and `ground_truth.run.jsonl`.
`.gitignore` excludes them and raw run directories are published as an archive —
the treatment `252e2d3` gave WS-4. The complete tree including every ledger is
at `aep-raw-archive/ws6-b5-s1-2026-09-08-attempt3` (1454 files, 56 MB, 120
ledgers). The five observer logs are published as `*.log.txt` rather than forced
past `.gitignore`'s `*.log` rule.

`SHA256SUMS` digests all 974 committed files. Manifest digest:

```
76d24a546cac9e2227cdb6ffbb637d7fb3580a0fc51c64b5f6ba2e80902914a4
```

`b5-runs.jsonl`: 120 lines,
`ddb994c64087a968b65d61727dbe26052a81c62d901df7e1d85a4ec3fd40e906`.

## Host

`measurement-host.txt` records the environment before any run. The collection
ran detached (`setsid`+`nohup`, PID recorded per R1) with the WSL keepalive held.
Teardown verified rather than asserted: 0 containers left, ports 7233/8233/8099
free.

## Attempt budget

Under the corrected re-registration §7 this is **attempt 1 of 3 against the
corrected cell**. Attempts 1 and 2 of the original registration are not charged
to it, for the reasons and under the three conditions recorded there. Host
reliability evidence does not reset.
