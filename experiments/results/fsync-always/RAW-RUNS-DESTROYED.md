# The raw runs under this directory no longer exist.

**2026-09-14.** Six run directories (60 executions) — three `AEP_FULL` and three
`B3_INTENT_NO_BARRIER`, crash-free, payments, `appendfsync always` — together
with this root's `matrix-plan.json` and `matrix-progress.jsonl`, were destroyed
by `scripts/fsync_always_benchmark.sh`, whose clean path was a recursive delete
of this hardcoded root with `AEP_FSYNC_CLEAN` defaulting to `1`.

They were gitignored, never committed, and no archive or manifest held them.
**They are not recoverable.**

`analysis/latency-and-throughput.csv` and `analysis/per-execution.csv` are
tracked, were restored from git, and are unchanged. Every number the paper takes
from this cell — `\BarrierCostAlways`, `\AepAlwaysMedian`,
`\BthreeAlwaysMedian` — still verifies against them. What is gone is the ability
to recompute those CSVs from raw.

The script has been repaired: it refuses to write into a non-empty root, and the
root is now an input (`AEP_FSYNC_RESULTS_ROOT`).

Full account: `reports/incident-fsync-always-raw-destroyed-2026-09-14.md`.
Rule: `docs/25-collection-tooling-rules.md` R16.
