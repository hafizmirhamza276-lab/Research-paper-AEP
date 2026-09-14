# The raw runs under *this* directory were deleted. They are not lost.

> **CORRECTION, 2026-09-14, phase 20.** This file previously said the runs were
> **"not recoverable"**. That was wrong, and it was wrong because the search
> behind it was narrower than the claim it supported. **Two verified copies
> survive.** The deletion happened; the data did not die with it. The original
> text is kept below the line so the chain stays visible.

## What is true

Six run directories (60 executions) — three `AEP_FULL` and three
`B3_INTENT_NO_BARRIER`, crash-free, payments, `appendfsync always` — were
deleted from **this checkout** on 2026-09-14 by
`scripts/fsync_always_benchmark.sh`, whose clean path was a recursive delete of
this hardcoded root with `AEP_FSYNC_CLEAN` defaulting to `1`. That part stands,
and so does the repair and `docs/25` R16.

**This checkout was not the canonical copy.** The cell was collected on
2026-08-07 into `/root/aep/experiments/results/fsync-always`, and that is the
tree the Phase-11 raw archive was built from. Both survive and both verify:

| copy | run dirs | files | vs `MANIFEST.sha256` |
|---|---|---|---|
| `/root/aep-raw-archive/aep-raw-evidence.tar` | 6 | 112 | 112 OK, 0 failed |
| `/root/aep/experiments/results/fsync-always` | 6 | 112 | 112 OK, 0 failed, 0 missing |

The manifest is the one `README.md` names: its own digest is
`87fa2d534d8751d1239bd31f858a916536c94e1549741d37704a1b083d03e2d7`. The archived
`analysis/latency-and-throughput.csv` and `analysis/per-execution.csv` are
**byte-identical** to the two tracked CSVs in this directory, so
`\BarrierCostAlways`, `\AepAlwaysMedian` and `\BthreeAlwaysMedian` are
recomputable from raw after all.

The archived runs carry **16 files each**, including `summary.json`,
`events.jsonl` and the per-worker attempt logs. What this checkout held is not
knowable now, but Phase 11 recorded that this clone's `matrix` runs lacked the
per-worker attempt logs the `/root/aep` runs carry — so the deleted copy was
most likely the *poorer* of the two. That is an inference, and it is flagged as
one.

## What is still true and still bad

The deletion was undetectable from inside this repository: the raw runs are
gitignored, so `git status` could report only the two derived CSVs. The recovery
came from an archive this checkout does not contain and does not reference by
path. **Nothing in this repository would have told you the data survived** — and
nothing told me, either, until I looked outside it.

Account: `reports/incident-fsync-always-raw-destroyed-2026-09-14.md` (with its
own correction) and `reports/phase-report-20-ws5-accounting-2026-09-14.md`.
Rule: `docs/25` R16.

---

*Superseded text, 2026-09-14, kept for the chain:*

> **The raw runs under this directory no longer exist.** … They were gitignored,
> never committed, and no archive or manifest held them. **They are not
> recoverable.**

The final sentence was false. An archive and a manifest held them both.
