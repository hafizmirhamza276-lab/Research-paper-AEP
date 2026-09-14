# Phase 17 — WS-5 analysis of the 612 collected runs

**Status at the time this section was committed: no outcome has been computed.**
The `settled=false` ruling below is committed *before* the analysis runs, so the
git history establishes the ordering rather than the report asserting it.

---

## 1. Integrity: what could be proved, and what could not

### 1.1 The committed digests verify

```
t1-p0-everysec     MANIFEST.md: OK MANIFEST.csv: OK
t1-incomplete      MANIFEST.md: OK MANIFEST.csv: OK
t2-p30             MANIFEST.md: OK MANIFEST.csv: OK
t2-keying          MANIFEST.md: OK MANIFEST.csv: OK
```

8 of 8 OK.

### 1.2 They do not cover the raw tree, and the prompt's step 2 assumed they did

Each `SHA256SUMS` contains **two lines** — `MANIFEST.md` and `MANIFEST.csv`.
`scripts/freeze_results.py` documents exactly this (*"over the manifest and every
analysis output"*), and at freeze time there were no analysis outputs. **The
over-claim is in commit `729fbfa`, which is mine:** *"SHA256SUMS is what lets the
later pass prove it analysed what was collected."* It lets a later pass prove the
manifests are unchanged. That is strictly weaker and does not cover 331 MB of run
directories.

### 1.3 What was done instead

The manifests were regenerated from the present raw tree and compared
byte-for-byte:

```
t1-p0-everysec     MANIFEST.md=same  MANIFEST.csv=same
t1-incomplete      MANIFEST.md=same  MANIFEST.csv=same
t2-p30             MANIFEST.md=same  MANIFEST.csv=same
t2-keying          MANIFEST.md=same  MANIFEST.csv=same
```

and the digests still verify afterwards (8/8 OK). Because `freeze_results.py`
reads runs through `experiments.analyze.load_run` — the same loader the analysis
uses — this establishes that the tree still yields the same **612 runs, 44 cells
and per-cell execution counts**.

**What it does not establish:** a change to a run's *contents* that left every
count identical would pass this check. It is not a full-tree digest and is not
presented as one.

---

## 2. Ruling on the `settled=false` runs

**Committed before any outcome was computed.** 19 of 315 in `t2-p30` and 53 of
180 in `t2-keying` carry `settled=false`.

### 2.1 What the flag means

`runner.wait_until_settled` returns `False` when at least one execution is still
in a `PENDING_STATUS` after `recovery_deadline_seconds`. It is a statement about
how long recovery took relative to a deadline, not about whether the run
produced a measurement.

### 2.2 The ruling

> **An unsettled run is a measurement and is included, unweighted, exactly as a
> settled one.**

### 2.3 Where the rule comes from — four independent grounds, none of them new

1. **The pre-registration fixes it.** §2.3: rates are *"unchanged from the frozen
   analysis, so old and new cells are comparable."* Any exclusion rule invented
   now would not be unchanged from the frozen analysis.
2. **`experiments/analyze.py` has no run-level `settled` filter at all.** The
   only occurrences are `settled_at`, an execution-level timing field. The
   absence of a filter is the frozen analysis's treatment; including these runs
   *is* leaving the analysis unchanged.
3. **The harness treats it as a warning, not a void.** `runner.py:747` prints
   `WARNING: the run did not settle within the recovery deadline` and returns
   `0 if report.agrees else 1` — validity is `agrees`, not `settled`. The harness
   has a separate, explicit void vocabulary (`RunVerdict.VOID_*`), and it voided
   nothing: all 612 runs carry `status=collected`.
4. **§2.4's stopping rule forbids it.** Fixed *n*, no outcome-dependent
   decisions. `settled` correlates with crash regimes by construction — the
   crash-free step has 0 unsettled and the all-crash step has the most — so
   excluding on it would preferentially drop crashed runs, which is an
   outcome-adjacent exclusion made after collection.

### 2.4 The honest limitation of ground 1

The frozen `matrix-progress.jsonl` available in this clone holds 83 entries, all
`settled=true`, so the frozen analysis was **never actually confronted with an
unsettled run**. The precedent is therefore untested rather than established,
and ground 1 rests on the absence of a filter (ground 2) rather than on an
observed decision. Recorded because the difference matters: grounds 2–4 carry
the ruling on their own, and ground 1 alone would not.

### 2.5 What would have changed the ruling

A run whose recovery process *died* during settling is a different case:
`wait_until_settled` raises `RunAborted` and states that *"No recovery
measurement from this run is usable."* That did not happen in any of the 612 —
every run reached `status=collected`. Had it happened, those runs would be
excluded, and the rule for doing so is the harness's own, not a new one.

---

*Sections 3 onward — the analysis, H1–H5 verdicts, and what this means for
§VI-RQ3 and §VIII — are appended after this file is committed.*
