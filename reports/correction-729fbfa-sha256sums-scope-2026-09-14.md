# Correction: `729fbfa` claims a scope for SHA256SUMS that it does not have

**The commit message is history and is not rewritten.** This file is the
correction, in the place corrections live.

---

## The sentence

Commit `729fbfa` ("WS-5 tiers 1 and 2: 612 runs collected, frozen and
manifested"), in the block headed *WHAT IS COMMITTED, and why not the data
itself*:

> SHA256SUMS is what lets the later pass prove it analysed what was collected.

## Why it is false

Each of the four `SHA256SUMS` files contains **two lines**:

```
<digest>  MANIFEST.md
<digest>  MANIFEST.csv
```

`scripts/freeze_results.py` says so in its own docstring — *"SHA256SUMS — over
the manifest and every analysis output, so a later reader can tell whether the
numbers moved"* — and at freeze time there were no analysis outputs, so only the
two manifests were digested. **The tool did exactly what it documents. The claim
about it was mine and was wrong.** Two manifest lines do not bind 331 MB of run
directories across 612 runs.

## What it cost

Phase 17 could not perform its own step 2 as written. It fell back to
regenerating the manifests from the present tree and comparing byte-for-byte,
which — because `freeze_results.py` reads runs through the same
`experiments.analyze.load_run` the analysis uses — establishes that the tree
still yields the same **612 runs, 44 cells and per-cell execution counts**, and
establishes nothing about run *contents*. A change to a run that left every
count identical would have passed.

## What binds the collection, precisely

Three things now, with different reach:

1. **Per-run `config_digest`, written at collection time.** Present in both
   `run-config.json` and `summary.json` for all 612 runs; the two agree in
   **612 of 612** cases, and all 612 digests are **distinct**. This is the only
   *retroactive* binding available: it was computed while the runs were being
   collected. It covers **what each run was configured to do**, and that no two
   runs share a configuration. It does **not** cover the event logs, the
   ground-truth ledger, or the outcome fields of `summary.json` — a summary
   whose counts were edited afterwards would still carry a matching digest.
2. **`SHA256SUMS`** — the two manifests per step. Verifies 8/8.
3. **`RAW-SHA256SUMS`**, added by this phase — every file in every run
   directory, 10 024 files across the four steps, plus a tree-level digest,
   written by `scripts/digest_results_tree.py` and verifiable with plain
   `sha256sum -c`.

## The residual, which no later digest can remove

`RAW-SHA256SUMS` was written on **2026-09-14**, three days after the collection
completed (`COMPLETE` = 2026-09-11T11:36:23Z) and after phase 17's analysis had
already run.

**It binds every pass from 14 September onward. It does not retroactively bind
phase 17, and nothing taken now could.** The strongest statement available about
phase 17 is the one in its own report: the manifests regenerate byte-identically,
which fixes the run counts and the cell shape, not the run contents.

## What changes because of this

- `scripts/digest_results_tree.py` exists, with
  `tests/test_digest_results_tree.py` exercising every branch on which it fails
  to detect a change (rule 13/14).
- The limitation above is stated **inside every `RAW-SHA256SUMS` file**, not only
  here, so a reader who finds the digest without finding this report still learns
  what it cannot do.
- Future collections should write `RAW-SHA256SUMS` **at freeze time**, in the
  same pass as the manifests. That is the only way the digest and the data share
  a date.
