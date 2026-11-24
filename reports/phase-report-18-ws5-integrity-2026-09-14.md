# Phase 18 — WS-5.integrity: the four load-bearing claims that did not hold

## Asked

Close four defects before any WS-5 finding reaches the manuscript: the H2
hypothesis/instrument conflict, `SHA256SUMS`' scope, R14 instance 8, and
`make reproduce-figures`. Zero `.tex` changes.

## Done

All four. Zero `.tex` files changed. No existing report or commit message
edited. No new collection.

---

## H1 under both readings

Same estimator throughout — cluster bootstrap over runs, 10 000 resamples, seed
20260806.

| quantity | pooled median (governing) | lower-mode median |
|---|---|---|
| barrier cost, AEP-full − B3 | **1 939.7** [1 855.8, 1 962.4], half-width 53.3, excludes 0 | **1 959.0** [1 914.2, 1 970.2], half-width 28.0, excludes 0 |
| protocol − barrier, B3 − B0 | **33.9** [−122.6, +120.1], half-width **121.3**, **spans 0** | **16.3** [−54.1, +47.5], half-width **50.8**, **spans 0** |

**Clause 1** — the barrier's cost excludes zero — holds under both.

**Clause 2** — half-width below 100 ms — **fails** under the governing reading
(121.3 ms) and **passes** under the alternative (50.8 ms). So **H1 is refuted as
governed, and would be supported under the other reading.** That is the
disagreement, priced.

**What does not depend on the choice:** protocol-minus-barrier **spans zero
under both**. §VI-RQ3's 28.0 ms figure is not resolvable from zero at fifteen
runs per arm either way. The reading changes H1's label, not what the manuscript
may claim.

*A correction inside this pass.* The first lower-mode computation used a
midpoint threshold (`lower_median + gap/2`) and returned **[+7.1, +46.6] —
excluding zero**, which would have been the opposite headline. That threshold
sits below the top of a skewed lower group and dropped 8 of B3's 120 lower-mode
executions. The boundary is now the largest value still in the lower group, and
the kept counts match `largest_gap_split`'s groups exactly (149 / 120 / 145).

---

## What each of the four claims said versus what it did

### 1. H2 — the hypothesis and the instrument returned opposite answers

*Said:* phase 17 §4 ruled H2 **supported** at 0.20, recording that the flag
disagreed.
*Did:* amendment 1 §1's final paragraph fixes the rule — *"If no arm is flagged
at fifteen runs, the mixture reporting is omitted and the pooled median stands.
That outcome is H2 … being refuted."* No arm was flagged.

**Resolution: amendment 1 governs. H2 is REFUTED.** Recorded in
`reports/phase-report-ws5-prediction-amendment-2-2026-09-14.md`; amendment 1 and
the pre-registration are unedited. Phase 17's H2 verdict is **superseded**, and
its report is likewise unedited.

The resolution chosen is the one that is *worse* for the paper. Amendment 1
exists because choosing a summary after seeing the data *"would be a fitted
choice: the shape of the new data would decide which summary flatters it."*
Reading H2's prose over amendment 1's predicate, with both answers visible, is
that choice.

Recorded and **not fixed**: `gap / range > 0.5` is range-sensitive — the same
mixture fires at 3 runs and not at 15 because the denominator grows with the
sample. Changing the predicate now, knowing which answer each version yields, is
the same fitted choice. Amendment 2 §4 states what a better predicate looks like
for the next pre-registration to adopt *before* its data.

### 2. `SHA256SUMS` — claimed to bind the collection, binds two manifests

*Said:* `729fbfa` — *"SHA256SUMS is what lets the later pass prove it analysed
what was collected."*
*Did:* two lines per step, `MANIFEST.md` and `MANIFEST.csv`.

**(a) What already bound the runs, checked first.** Per-run `config_digest`,
written at collection time, present in both `run-config.json` and
`summary.json`: **612/612 agree, 612 distinct**. That is the only *retroactive*
binding available, and it covers what each run was **configured** to do, not
what it **produced** — a summary whose counts were edited afterwards would still
carry a matching digest.

**(b) What was added.** `scripts/digest_results_tree.py` → `RAW-SHA256SUMS` per
step: **10 024 files** (1 245 / 201 / 4 630 / 3 948), each verified by plain
`sha256sum -c`, plus a per-run and tree-level roll-up. SQLite `-wal`/`-shm` are
excluded and the exclusion is asserted by a test, because any open of the
database rewrites them and a gate that fails for a read-only reader is one
people learn to ignore.

**(c) The residual, stated in every file it writes.** Hashed **2026-09-14**,
three days after `COMPLETE` (2026-09-11T11:36:23Z) and after phase 17 ran. It
binds every pass from that date. **It does not retroactively bind phase 17, and
no digest taken now could.**

**(d)** `reports/correction-729fbfa-sha256sums-scope-2026-09-14.md`.

### 3. R14 instance 8 — an empty section that reads like a verdict

*Said:* nothing — it printed a heading and no rows.
*Did:* `--section degeneracy` rebuilt the report without the `mixtures` key, and
`print_report` emitted every heading unconditionally, so "not computed" and
"found nothing" rendered identically. A blank A2 is exactly what *"no arm was
flagged"* looks like — which amendment 1 defines as **H2 refuted**.

*Repair:* every section, in every view, now names which kind of empty it is.
*Rule 13, discharged:* a new test builds a per-execution.csv whose arms hold one
execution each, so no mixture row can exist, and asserts the sentinel fires. The
same assertion was **run against the pre-fix module at `5ff3dc2`** and fails
there — its A2 renders as a heading followed directly by section B.
Added to `docs/25` as instance 8; the header now reads eight.

### 4. `make reproduce-figures` — the guard tested presence, not sufficiency

*Said:* *"a plotted value moved. This is a finding, not a build error."*
*Did:* `compgen -G "$(ARCHIVE)/*-r0"` asks only whether **any** run directory
exists. This machine holds **84** of the archive's **432**, so the branch ran
`analyze.py` over a quarter of the data and compared the result against figures
built from all of it.

**It passes from a fresh clone, and always did.** No run directory is tracked,
so the guard is false, the figures are skipped with a message, and the target
succeeds. The failure needed a machine with a *partial* tree.

*Repair:* the guard now compares the run-directory count against the archive's
own `MANIFEST.md` and skips — naming both numbers — when they differ. Not
repointed at the 84-run snapshot, which would produce different numbers under
the same command name. Exercised on this machine: `rc=0`, with

```
  SKIPPED: experiments/results/matrix holds 84 run directories, but its MANIFEST.md
           records 432. …
```

README and `ARTIFACT.md` were **already accurate** — both promise tables and
macros, which do reproduce from tracked inputs. Each gains one paragraph naming
what the command does *not* cover, so a reader cannot infer the two analysis
figures are among them.

---

## Not done, and why

- **The `always` arm of task 5.1** and **the class sweep 4 → 6** — out of scope,
  still outstanding.
- **Applying H1–H5 to §VI-RQ3 and §VIII** — out of scope by instruction. H4's
  +9.33 pp on POS-ONLY remains the finding with the most paper-level
  consequence, and waits for the two outstanding collections so §VI is rewritten
  once.
- **Amendment 1's predicate is not changed** — §4 of amendment 2 explains why
  changing it now would be a fitted choice.
- **Phase 17's report is not edited**, per the bounds; amendment 2 supersedes its
  H2 verdict and says so.

## Raw outputs

```
barrier cost (AEP-full - B3)
  POOLED      point    1939.7  [   1855.8,    1962.4]  half    53.3  spans0=False
  LOWER-MODE  point    1959.0  [   1914.2,    1970.2]  half    28.0  spans0=False
     cuts: treat<=7091.5 (149 kept)  ctrl<=3302.3 (120 kept)
protocol - barrier (B3 - B0)
  POOLED      point      33.9  [   -122.6,     120.1]  half   121.3  spans0=True
  LOWER-MODE  point      16.3  [    -54.1,      47.5]  half    50.8  spans0=True
     cuts: treat<=3302.3 (120 kept)  ctrl<=7796.5 (145 kept)

run-config vs summary config_digest: agree=612 disagree=0 missing=0
distinct config digests: 612

RAW-SHA256SUMS, verified by sha256sum -c:
  t1-p0-everysec 1245    t1-incomplete 201    t2-p30 4630    t2-keying 3948

PRE-FIX code emits a sentinel for an empty A2 : False
PRE-FIX A2 renders as: ' Why those intervals are wide: the arms are mixtures --\n\n-- B. The two'
```

## Findings outside scope

1. **`uv sync` inside `make reproduce-figures` removes the dev extras.** The
   target syncs `--extra experiments --extra analysis`, which uninstalls
   `pytest`; the next `uv run … pytest` in the same shell fails to spawn. Cost a
   confusing failure mid-pass. The Makefile comment already anticipates the
   neighbouring problem (*"syncing twice in one target uninstalls 31 packages"*).
   Not changed: the target is in scope but its sync behaviour is a dependency
   question, not an integrity one.
2. **The suite needs `--extra b5`, and omitting it fails three tests on import,
   not on logic.** `temporalio` sits in its own `b5` extra — deliberately, so
   the `experiments` environment that produced every frozen cell is unchanged.
   A `uv sync` without it uninstalls `temporalio`, and
   `tests/test_b5_collect_contract.py` then reports three failures that look
   like contract breakage. Confirmed by re-running those 24 tests with the
   extra: all pass. The full invocation this pass used is in Environment below.
3. **Future collections should write `RAW-SHA256SUMS` at freeze time**, in the
   same pass as the manifests — the only way the digest and the data share a
   date. `scripts/freeze_results.py` is the place; not changed here because it
   would alter the artefacts of every previous collection's tooling path.

## Environment

`uv run --frozen --extra dev --extra cov --extra experiments --extra analysis`,
CPython 3.13.0, Redis 7.2.5-alpine by digest, WSL2 6.6.114.1, GNU coreutils 9.4.
