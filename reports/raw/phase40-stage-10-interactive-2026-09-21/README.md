# Raw evidence — stage 10 re-run on the interactive loop, 2026-09-21

Assessed in `reports/phase-report-40-stage-10-interactive-2026-09-21.md`.

The live collection itself lives outside the repository with every other
agent-mode collection, at
`AEP/stub-results/phase40-live-10call-interactive-2026-09-21/`. This is the
text evidence from it, copied verbatim and unedited.

**What is here and why.** `prompts/phase-40-agent-reachability.md` §5 makes the
transcript the only replay mechanism a model-backed run has — a call cannot be
recomputed from a seed — so `planner-transcript.jsonl` is the primary evidence
and everything else is what is needed to check it against the harness's own
records.

| file | what it carries |
|---|---|
| `planner-transcript.jsonl` | every prompt, completion, token count, timestamp and outcome. 4 entries, schema `aep.agent.transcript/3` |
| `planner-cumulative.jsonl` | the append-only counter: one reservation and one settle per call |
| `planner-cumulative.json` | the derived snapshot, `"_authoritative": false` |
| `planner-caps.json` | the ceilings in force, beside the pre-registered ones. Collection root and per run |
| `planner-budget.json` | per-run calls, tokens and cost |
| `summary.json` | the oracle's counts per run |
| `events.jsonl`, `events-worker-*`, `events-runner`, `events-recovery` | the harness's record, including the respawns |
| `ground_truth.run.jsonl` | the applied-mutation ledger, as text |
| `run-config.json`, `mock-api.yaml`, `matrix-plan.*`, `collection.log` | what was run |

**What is deliberately absent.** The SQLite ground-truth files
(`ground_truth.sqlite3`, `-shm`, `-wal`) are binary, 280 KB of the collection's
486 KB, and `ground_truth.run.jsonl` is the same ledger in text. Zero-length
files (`recovery.stop`, `recovery-stderr.log`, `recovery-stdout.log`) carry
nothing.

**No credential is in any of these files.** Checked before committing:
`scripts/scan_archive_for_leakage.py` over a tar of the collection reported
*"No blocking category present."*, and a search for the literal 84-character key
value found 0 occurrences here, 0 across 3 266 tracked repository files, and 0
anywhere under `stub-results/`.

**These numbers are not results.** §2 of the pre-registration forbids reporting
any of this as a rate, and the report's §3 gives counts only. One execution per
system establishes nothing about reachability in either direction.
