# Phase 4 Session 1 — the matrix closeout and the manuscript

**Date:** 2026-08-07
**Roadmap section:** `PAPER_ROADMAP.md` §5 (Phase 4, the manuscript) and its
prompt block, preceded by the matrix closeout, under amendments **F0–F5**.
**Predecessor:** `reports/phase-report-2b-session3b-2026-08-07.md`

> **Read this first — what changed, in the order it matters.**
>
> **1. The paper exists and it compiles.** `paper/` is an IEEEtran (TSE)
> project with all nine sections drafted including the evaluation, PLACEHOLDER_PAGES
> pages, zero undefined references or citations, and 24 bibliography entries
> every one of which was verified to exist by DBLP lookup or DOI resolution.
>
> **2. Three defects were found in the *measurement and reporting* code while
> writing it, and none of them was visible in any output.** A per-cell grouping
> that could silently average a crash-free cell with a hard-Redis-kill cell; a
> headline figure drawn from the table Session 3B had explicitly banned; and a
> cross-class pooling formula that was an order-dependent running mean under a
> comment claiming it weighted on counts. All three are fixed with
> failing-then-passing tests. §C.3, §C.4.
>
> **3. Two of the paper's own safeguards caught themselves.** A DOI written
> from memory did not resolve (404 against nine real DOIs at 200), and the
> bibliography compiled completely blank — 24 empty `\bibitem` blocks, no
> undefined-citation warning, clean build — because BibTeX rejects `%` comments
> inside an entry and treats an at-sign in a comment as an entry start. Both
> are now checked mechanically. §C.5.
>
> **4. The barrier's cost is now stated as a function of the durability
> configuration** rather than as one large number. §C.7.

---

## A. Phase attempted and roadmap section reference

`PAPER_ROADMAP.md` §5, under this session's amendments:

| Amendment | Requirement | Status |
|---|---|---|
| **F0(i)** | Apply standing rule 8 — commit/push Session 3B, green CI | ✅ §C.1 |
| **F0(ii)** | Let the remaining B1/B2/B3 cells finish | PLACEHOLDER_F0II |
| **F0(iii)** | `appendfsync always` barrier-latency micro-benchmark | PLACEHOLDER_F0III |
| **F0(iv)** | Freeze results: final `analyze.py` pass, `per-cell-metrics.csv` the only quotable source, archive with a per-cell manifest | PLACEHOLDER_F0IV |
| **F1** | Claims match Session 3B exactly: dispatch withholding, **not** durability against process SIGKILL | ✅ §C.6 |
| **F2** | The trilemma is the frame; per-capability Table 1 as the anchor | ✅ §C.6 |
| **F3** | Every number carries a pointer; timings only from suspend-gated runs; 28 ms and barrier cost separate; test counts never cited as assurance | ✅ §C.2, §C.7 |
| **F4** | All sections drafted; `\todo` only where completion cells could move a value; IEEEtran; verified-real refs only | ✅ §C.2, §C.5 |
| **F5** | Threats must include the six named items | ✅ §C.8 |

---

## B. Files created/modified

### New — the manuscript

| File | What it is |
|---|---|
| `paper/main.tex` | IEEEtran journal-mode document. Its header states the numbers discipline and names the two permitted rate sources. |
| `paper/sections/01-introduction.tex` | The trilemma as the frame; contributions C1–C4; explicit non-claims. |
| `paper/sections/02-motivating.tex` | Four traces from the harness, cross-checked against the oracle ledger; the trilemma table. |
| `paper/sections/03-model.tex` | System, clocks, endpoint capability, failure model F1–F5, non-claims. Condensed from `docs/22-formal-model.md`. |
| `paper/sections/04-protocol.tex` | Ordering, P1/P2/P3 with their declared residuals, the ack-to-authorization chain, the state machine. |
| `paper/sections/05-implementation.tex` | LOC, Lua scripts, composition modes, and an explicit refusal to cite test counts as protocol assurance. |
| `paper/sections/06-evaluation.tex` | RQ1–RQ4. Every table `\input` from `generated/`. |
| `paper/sections/07-related.tex` | Leases/fencing, transactions/logging, impossibility, durable execution, agents. |
| `paper/sections/08-threats.tex` | Construct/internal/external, and where the protocol should *not* be used. |
| `paper/sections/09-artifact.tex` | What is pinned, what can be reproduced, how the numbers regenerate. |
| `paper/refs.bib` | 24 entries. Header records the two silent failures of §C.5. |
| `paper/figures/state-machine.tex` | **Generated** from the implementation's transition set. |

### New — the tooling that keeps the paper honest

| File | Why |
|---|---|
| `scripts/paper_tables.py` | Generates every evaluation table and headline scalar from the frozen CSVs, emitting the filter and arithmetic behind each value as a LaTeX comment. Never reads the banned pooled table. |
| `scripts/gen_state_machine.py` | Emits the state-machine figure from `LEGAL_INTENT_TRANSITIONS`; exits non-zero if the code has an edge the layout does not. |
| `scripts/check_paper_numbers.py` | Re-derives all of the above and fails on drift. Also greps `main.bbl` for empty entries and `main.blg` for parse errors — the two failures of §C.5. |
| `scripts/verify_refs.py` | DBLP lookup per bibliography entry; the non-indexed sources are listed for URL verification. |
| `scripts/freeze_results.py` | Per-cell manifest keyed the way the paper quotes, plus `SHA256SUMS`. |
| `scripts/fsync_always_benchmark.sh`, `scripts/fsync_compare.py` | F0(iii). Second Redis, config-verified before measuring. |
| `scripts/matrix_progress.py` | Remaining runs and wall time for a filtered invocation. |
| `experiments/tests/test_per_cell_regimes.py` | Pins §C.3. |
| `experiments/tests/test_figure_pooling.py` | Pins §C.4. |

### Modified

| File | Change |
|---|---|
| `experiments/analyze.py` | `regime` added to the per-cell grouping key and to `per-execution.csv`; `regime_label`; both figures re-pointed at `per_cell` within one named regime; figure 2's pooling corrected to a ratio of sums. |
| `experiments/statistics.py` | `wilson_interval`, for figure error bars only, with a docstring saying it is not interchangeable with the CSV's cluster bootstrap. |
| `.gitignore` | LaTeX build products. |

---

## C. Raw command outputs

### C.1 F0(i) — standing rule 8, discharged

Session 3B ended without committing, which is itself a rule-8 violation by that
session; F0(i) is the remediation and it is recorded rather than smoothed over.

```
PLACEHOLDER_C1
```

### C.2 The manuscript, and the discipline it is written under

PLACEHOLDER_C2

### C.3 A defect in the file the paper is told to quote

Session 3B §F2 banned `analysis/table-1.csv` because it pools three fault
regimes, and directed every reader to `per-cell-metrics.csv` instead. That
remedy is only sound if the per-cell file does not have the same defect.

**It did not have it yet, and it was one collected cell away from having it.**
`build_per_cell` grouped by
`(system, crash_point, response_class, readback_keying)` — no regime. Two of
the five regimes report `crash_point = "none"`, because no *worker* is killed
in either:

* `p0` — crash-free, the only cells RQ3 may use;
* `redis-kill-preack` — Redis hard-killed and restarted mid-run.

Today they are told apart only because `p0` happened to be collected against
`payments` and the Redis-kill cells against `NO_READBACK`. `p0` on
`NO_READBACK` is in the 1 068-run plan. Collect it, and a crash-free cell and a
hard-Redis-kill cell merge into one rate with nothing to say so.

```
PLACEHOLDER_C3
```

### C.4 Two figure-computation defects, neither visible in any output

**Figure 1 was drawn from the banned table.** `write_figures` took its bar
heights from `table_one` — the pooled table whose own warning text says it is a
coverage summary and not a result. A banned table does not become quotable by
being drawn. Figure 1 is now pooled from `per_cell` inside one named regime,
and the regime is printed in the figure's title so a reader cannot lose it.

**Figure 2 pooled response classes with a running mean.** The code read:

```python
current[row["crash_point"]] = (
    row["rate"] if previous is None else (previous + row["rate"]) / 2
)
```

under the comment `# Pool across response classes and keyings by weighting on
counts.` It does not weight on counts. It is order-dependent, and across three
response classes it weights the last-seen cell at 1/2, the one before at 1/4
and the first at 1/4. A rate over executions is a ratio of sums.

The test that pins it uses three cells where the two formulas visibly diverge —
1/10, 0/10 and 30/30 — for which the correct pooled rate is 31/50 = 0.62 and
the old formula returns 0.525:

```
PLACEHOLDER_C4
```

### C.5 Two silent failures in the citation apparatus

**A DOI written from memory did not exist.** `refs.bib`'s first draft carried
`10.1145/2181796.2229155` for Helland's *Idempotence Is Not a Medical
Condition*. It resolves to nothing. Every other DOI in the file resolves:

```
PLACEHOLDER_C5A
```

The real records are `10.1145/2160718.2160734` (CACM 55(5), used) and
`10.1145/2181796.2187821` (ACM Queue). **A DOI is exactly the kind of thing
that looks verified because it is well-formed**, and only resolution
distinguishes them. This is what F4 means by a D4-level halt, and the check is
the reason it did not become one.

**The bibliography compiled completely blank and nothing said so.** Provenance
comments were written *inside* each entry. BibTeX does not accept `%` comments
inside an entry; it emitted `You're missing a field name ... I'm skipping
whatever remains of this entry` for all 24 and produced 24 empty `\bibitem`
blocks. LaTeX then reported **no undefined citations** — the keys existed, the
entries were empty — so the build was clean and the bibliography was blank.

```
PLACEHOLDER_C5B
```

A second bite of the same apple followed: BibTeX's scanner treats an at-sign as
the start of an entry *even on a comment line*, so the header comment
explaining the first failure silently swallowed the two entries after it.

Both are now checked by `check_paper_numbers.py`, against the artifact rather
than the log: it greps `main.bbl` for empty `\bibitem` blocks and `main.blg`
for parse errors.

### C.6 F1 and F2 — what the paper claims

PLACEHOLDER_C6

### C.7 F0(iii) — the barrier's cost as a function of durability config

PLACEHOLDER_C7

### C.8 F5 — threats to validity

PLACEHOLDER_C8

### C.9 F0(iv) — the freeze

PLACEHOLDER_C9

### C.10 The suite

PLACEHOLDER_C10

---

## D. Requirement checklist

PLACEHOLDER_D

---

## E. Deviations from the amendments

PLACEHOLDER_E

---

## F. The draft read as a hostile TSE reviewer

PLACEHOLDER_F

---

## G. Open questions needing a human/architect decision

PLACEHOLDER_G

---

## H. Recommended next phase and its prerequisites

PLACEHOLDER_H
