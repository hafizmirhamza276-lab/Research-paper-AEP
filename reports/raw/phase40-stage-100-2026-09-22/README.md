# Raw evidence — stage 100, 2026-09-22

Assessed in `reports/phase-report-40-stage-100-2026-09-22.md`. The first
collection under **paired seeding** (amendment 8) and under the **transmission
boundary** (amendment 9): two repetitions per arm, drawn from one pair identity,
so the two arms face the same payments and the same fault schedule.

The live collection itself lives outside the repository with every other
agent-mode collection, at
`AEP/stub-results/phase40-live-100call-interactive-2026-09-22/`. This is its
text evidence, copied verbatim and unedited.

**21 live calls, USD 0.004167, 0 voided, `rc=0`**, 4 runs, wall time 0.13 h.

| file | what it carries |
|---|---|
| `planner-transcript.jsonl` | every prompt, completion, token count, timestamp, `decision_index` and outcome. Schema `aep.agent.transcript/4` |
| `planner-cumulative.jsonl` | one reservation and one settle per call, keyed by `(step, decision)` |
| `planner-caps.json` | 20/run, 100/collection, USD 0.20; `planner: {mode: live, loop: interactive}`; `price_source` with URL and retrieval date |
| `planner-budget.json` | per-run calls, tokens and cost |
| `summary.json` | the oracle's counts per run, including `declared_ambiguous_executions` and `undetected_duplicate_executions` |
| `events.jsonl`, `events-worker-*`, `events-runner`, `events-recovery` | the harness's record, including `planner_declined_redispatch` and `provider_request_transmitted` |
| `run-config.json`, `mock-api.yaml`, `matrix-plan.*` | what was run |

**Three kinds of file are deliberately not here**, because `.gitignore` excludes
them repository-wide (`*.log` at line 88, `*.run.jsonl` at line 85) and every
earlier phase-40 raw directory follows the same rule: `ground_truth.run.jsonl`
(the applied-mutation ledger), `mock-api.log`, and `collection.log`. They are
preserved unedited in the external collection at the path above. The report
quotes the ledger for `AEP_FULL` repetition 1 — `applied, applied,
refused(injected-server-error)` — and that is where to check it.

**The pairing is visible in the agent's own completions.** Repetition 0 shows
amounts `986162`, `419764`, `434899` on both arms, in that order; repetition 0
of `AEP_FULL` and of `B0_NAIVE_RETRY` drew the same accounts. Repetition 1 shows
`975014` on both arms before `B0_NAIVE_RETRY` stopped. Nothing had to be
asserted about the seeding: it is in `planner-transcript.jsonl`.

**`planner-observations.jsonl` is absent from every run, and that is correct.**
It is written on the first observation and this collection produced none:
`crash_probability = 1.0` at `mid_dispatch`, so every dispatch was `SIGKILL`ed
before `observe()` could run, and every later decision was a `Stop`, which
executes nothing. The consequence matters for reading the transcripts — the only
`last_outcome` the agent was ever handed, on either arm, is
`unknown_process_died`.

**What `events.jsonl` holds that the agent was not told.** The AEP runs' event
logs carry `provider_request_transmitted` and the final classifications for the
crashed executions. The agent was told only that its process stopped while a
call for it was in progress. The answer was on disk and the driver never read
it — amendment 4 §3 and amendment 6 §3.2 working as specified.

**No credential is in any of these files.** Checked before committing:
`scripts/scan_archive_for_leakage.py` over a tar of the **full** collection —
all 83 files, including the three kinds excluded above — reported *"No blocking
category present."* with `credential`, `env_dump`, `account_name` and
`email_address` all at zero; and a search for the literal 84-character key value
found **0 occurrences** here, 0 across 23 256 repository files, and 0 across
1 216 files under `stub-results/`.

**These numbers are not results.** §2 forbids reporting any of this as a rate.
At two runs per system the counts establish one existence claim and refute
nothing, and the report says so.
