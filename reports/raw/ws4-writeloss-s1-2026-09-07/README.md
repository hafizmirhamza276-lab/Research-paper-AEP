# WS-4 write-loss cell, session 1, collected 2026-09-07 (attempt 5)

Collected exactly as `d8b2ca5` pre-registers. **No outcome has been looked at**
and `scripts/analyse_write_loss.py` has not been run against this data.

## Provenance

- launched 10:00:54 UTC, `run_matrix rc=0` at 11:02:21 UTC — 3687 s for 60 runs,
  **61.4 s/run**. The pre-registration's 64.5 s/run estimate was untested; it
  came out 4.8 % high and **no constant was edited**.
- `nohup setsid`, detached, `< /dev/null`.
- mechanism selected by the environment, not by `RunConfig`, so no collected
  run's `config_digest` changes:
  `AEP_HARNESS_REDIS_FAULT_MECHANISM=write-loss`,
  `AEP_HARNESS_WRITE_LOSS_DEVICE=aep-ws4-flakey`, `AEP_HARNESS_SUSPEND_DISABLED=1`.
- host record in `collection-logs/measurement-host.txt`.

## Run count and completion

| | |
|---|---|
| run directories | **60** |
| `AEP_FULL` / `B3_INTENT_NO_BARRIER` | 30 / 30 |
| `matrix-progress.jsonl` rows | 60, `status=collected` for all 60 |
| `summary.json` present | 60 / 60 |
| rows with an error / abort / failure field | **0** |
| `FAILED` lines in the collection log | **0** |
| R9 known-flake matches | 0 |

Every run matches the pre-registration on the parameters that define the cell:
`regime=write-loss-preack` (60), `endpoint=ledger_postings` (60),
`redis_kill_point=after_intent_before_barrier` (60), `executions_per_run=10`
(60), `workers=1` (60).

**No void condition fired.** In particular `coordinator_restarted_unexpectedly`
is `False` in all 60 runs — R10's abort condition, which ended attempt 4.

## R10 is closed by construction, and the evidence is here

The test-instance marker is seeded durably into the device AOF (`a994023`). The
2 s sampler in `collection-logs/marker-samples.log` ran from **before**
provisioning to the end of collection: **0 samples with `exists=0`**, and a
single container id (`92ca02374fc4`) throughout. The container reported healthy
for the whole hour.

## One thing observed after the collection, recorded rather than glossed

At teardown both containers read `Up 14 seconds`, so **something restarted them
after the collection had ended**. Its origin is not established — it is the same
unexplained-SIGTERM class that `reports/raw/ws4-sigterm-bound-2026-09-07.md`
bounds but does not solve.

It did not touch this data. The newest file anywhere under the results root is
`matrix-progress.jsonl` at 11:02:21 UTC, which is the instant `run_matrix`
returned 0; nothing was written afterwards. The marker sampler and
`coordinator_restarted_unexpectedly` independently show no restart *during* the
60 runs.

## What is here, and what is not

Committed: `matrix-plan.*`, `matrix-progress.jsonl`, and per run
`summary.json`, `run-config.json` (which carries `config_digest`),
`events-worker-*.jsonl` (what the verdict script reads), `events-runner.jsonl`,
`ground_truth.run.jsonl`.

Not committed: `ground_truth.sqlite3*` (24 MB) — the oracle's working store, not
an input to the verdict, with the same rows already in `ground_truth.run.jsonl`.

## Known display artifact, recorded not fixed

The plan header prints `workers per run 2` and `repetitions/cell 30 (3 runs x 10
executions)`. Both echo CLI defaults. The plan itself resolves per cell at
`experiments/run_matrix.py:744` (`cell.regime.workers or arguments.workers`), and
the collected rows confirm `workers=1` and 30 runs per arm. A header mislabel of
the same family as the "first 12 runs" header in the Arm A session files, and
left alone for the same reason.
