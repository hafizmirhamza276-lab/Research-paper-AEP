# Raw evidence — stage 30, 2026-09-21

Assessed in `reports/phase-report-40-stage-30-2026-09-21.md`. The first
collection under amendment 6: the re-decision concerns the same payment, and
the agent owns it.

The live collection itself lives outside the repository with every other
agent-mode collection, at
`AEP/stub-results/phase40-live-30call-interactive-2026-09-21/`. This is its
text evidence, copied verbatim and unedited.

Six live calls, **USD 0.00130300**, 0 voided, `rc=0`.

| file | what it carries |
|---|---|
| `planner-transcript.jsonl` | every prompt, completion, token count, timestamp, `decision_index` and outcome. 3 entries per run, schema `aep.agent.transcript/4` |
| `planner-cumulative.jsonl` | one reservation and one settle per call. The `…:0:0:d1:1` keys are amendment 6's second decision for execution 0, counted separately |
| `planner-caps.json` | 20/run, 30/collection, USD 0.06; `planner: {mode: live, loop: interactive}` |
| `planner-budget.json` | per-run calls, tokens and cost |
| `summary.json` | the oracle's counts per run |
| `events.jsonl`, `events-worker-*`, `events-runner`, `events-recovery` | the harness's record, including `resume_for_agent_redecision` and `planner_declined_redispatch` |
| `ground_truth.run.jsonl` | the applied-mutation ledger, as text |
| `run-config.json`, `mock-api.yaml`, `matrix-plan.*`, `collection.log` | what was run |

**`planner-observations.jsonl` is absent, and that is correct.** It is written
on the first observation and this collection produced none: the one executed
decision per run was `SIGKILL`ed mid-dispatch before `observe()` could run, and
every later decision was a `Stop`, which executes nothing.

**What `events.jsonl` holds that the agent was not told.** The AEP run's event
log contains `recovery_resolution status=FIRED_CONFIRMED` and
`final_classification outcome_class=CONFIRMED_APPLIED` for execution 0 — the
crashed mutation did apply. The agent was told `unknown_process_died`. The
answer was on disk and the driver never read it, which is amendment 4 §3 and
amendment 6 §3.2 working as specified.

**No credential is in any of these files.** Checked before committing:
`scripts/scan_archive_for_leakage.py` over a tar of the collection reported
*"No blocking category present."*, and a search for the literal 84-character
key value found 0 occurrences here, 0 across 3 300 tracked repository files,
and 0 anywhere under `stub-results/`.

**These numbers are not results.** §2 forbids reporting any of this as a rate.
At one run per system the counts establish nothing about reachability in either
direction, and the report says so.
