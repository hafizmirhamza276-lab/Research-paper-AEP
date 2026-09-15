# Phase 30 — WS-9: the migration attempted, and what blocks it

## Asked / Done

Asked: write the split down, migrate in verifiable increments starting with the
hard case, per-change page table, prove the macro multiset unchanged.

Done: the split written down, **`sec:eval-deployment` migrated end to end**, and
then **reverted** — because completing it requires a change to
`scripts/paper_tables.py`, which this pass's bounds exclude.

**Two findings came out of the attempt, and the second is a defect in the
manuscript as it stands today.** The tree is green and committed green; the only
manuscript-affecting change kept is a correction to the phase-28 verifier.

---

## 1. The split, as decided

§VI is 8 177 words in fourteen blocks. Load-bearing claims stay; decision aids
and explainers go. The criterion was the prompt's: *a reader of the main text
alone must be able to follow every claim.*

| block | words | floats | disposition |
|---|---|---|---|
| `sec:eval-setup` | 482 | 0 | stays — methods |
| `sec:eval-rq1` | 970 | 1 | **stays** — headline |
| "residual is set by the endpoint" | 518 | 0 | stays — carries H4 |
| `sec:eval-provable` | 238 | 1 | migrate (explainer) |
| "cost of the third corner" | 137 | 0 | migrate |
| `sec:eval-rq2` | 116 | 0 | stays |
| `sec:eval-detection` | 690 | 1 | **stays** — headline |
| `sec:eval-prevention` | 1 426 | 0 | **stays** — headline |
| `sec:eval-durability` | 949 | 0 | **stays** — headline |
| `sec:eval-writeloss-cell` | 413 | 0 | stays — phases 24/26 put it here on purpose |
| `sec:eval-rq3` | 413 | 1 | **stays** — the cost claim |
| `sec:eval-deployment` | 908 | 1 | **migrate — attempted first, per the prompt** |
| `sec:eval-rq4` | 418 | 0 | migrate |

Migratable total: ~1 700 words ≈ 1.8 pages. **Even executed in full, §VI cannot
reach the target**, because four blocks totalling 4 035 words are the evidence
the paper exists to present. The remaining distance is §VII's 3 655 words, which
is a compression problem rather than a migration one.

## 2. `sec:eval-deployment` — migrated, verified, reverted

Executed completely, in the order the prompt asked:

1. Block lifted from §VI (111 lines), replaced by a pointer paragraph that
   restates both barrier costs with their intervals, so RQ3's claim stands alone.
2. Placed in the supplementary as a `\section`, relabelled `supp:deployment`,
   every number and provenance comment carried across unchanged.
3. Four `\cref` sites converted to by-name references — `01:112`, `06:378`,
   `08:51`, `08:307`.
4. Gate run. **It failed, correctly**, on six more references the block carries
   *into* the main text: `sec:eval-detection`, `sec:eval-prevention`,
   `sec:eval-durability`, `sec:eval-writeloss-cell`, `tab:outcomes`,
   `tab:ablation`.
5. Those converted to by-name references too. Gate run again.

At that point the supplementary was **6 pages** (from 5) and §VI was 7 350 words
(from 8 177). The migration itself worked.

### What stopped it

`paper/generated/table-deployment-choice.tex:25` — the generated caption:

> The detection claim of `\cref{tab:outcomes}` shows no observed difference in
> any cell … (`\cref{sec:eval-detection}`) … and `\cref{tab:ablation}` is the
> ablation that shows it … and `\cref{sec:eval-prevention}` is what it is worth.

**Four `\cref`s into the main text, inside a generated file.** Move the table to
the supplementary and they dangle; LaTeX warns, the supplementary build fails
its own check and preserves the old PDF. They cannot be fixed where they are:
rule 1 forbids hand-editing `generated/`, and `scripts/paper_tables.py` is not in
this pass's scope.

So `tab:deployment` cannot leave the main text until the generator emits that
caption without cross-references — a small change, but one for a pass whose
bounds allow it. The prose depends on the table throughout, so the block does
not move without it.

**Reverted** rather than left half-done: `git checkout --` on the four `.tex`
files. The pass was designed so a half-migration cannot be committed green, and
that property did its job.

## 3. Finding: the paper currently states a retired number

The same caption ends:

> `Over floor' is the same median less the provider's 2 000 ms delay, and so
> includes the **28.0 ms** the protocol costs with the barrier already removed.

**28.0 ms is the figure phase 26 retired.** At fifteen runs per arm that
quantity is 33.9 ms with an interval of [−122.6, +120.1] that spans zero, and
§VI now says the decomposition "supports an ordering and not a partition". This
caption says the opposite, in the built PDF, today.

It survived because it is a **hardcoded string** in the generator
(`scripts/paper_tables.py:1033`), not a macro. Phase 26 removed
`\ProtocolMinusBarrier` from the macro set and from every `.tex`, and
`check_macros_are_used` verified no macro was orphaned — but a literal inside
generated caption text is invisible to every gate in the file. `table-latency`
also carries `28.0` as a column value, which is correct there: it is that
table's three-run cell, labelled as such.

**Recorded, not fixed** — the fix is in `paper_tables.py`. It should be the
first thing the next pass does, ahead of any further migration.

## 4. What was kept: a correction to the phase-28 verifier

Phase 28 read every `paper/generated/*.tex` as part of the main text, because at
the time main input all of them. The first migration moved a generated table
into the supplementary and the assumption stopped holding: the label was defined
in a file the supplementary inputs, so the supplementary's own reference to it
read as unresolved.

`check_cross_document_references` now attributes each generated file to whichever
document `\input`s it, with a comment recording why. A file inputted by neither
stays with main, so an orphaned generated file still has its labels checked
somewhere rather than dropping out of the census.

**Caught by running the gate after one block rather than at the end**, which is
what step 3's increments are for.

## 5. Per-change page table

| # | change | pages | kept? |
|---|---|---|---|
| 1 | `sec:eval-deployment` → supplementary, 10 reference sites | main −0, supp +1 | **reverted** |
| 2 | verifier attribution fix | 0 (no `.tex`) | kept |

Main: 25 before, 25 after. The migration reached supp 5 → 6 pages and §VI
8 177 → 7 350 words before being reverted; **main stayed at 25 throughout**,
which is itself worth knowing — 827 words out of §VI did not cross a page
boundary.

## 6. Proof the macro multiset is unchanged

```
06-evaluation    before 199 uses / 155 distinct   after 199 uses / 155 distinct
08-threats       before  51 uses /  43 distinct   after  51 uses /  43 distinct
macro multiset unchanged: YES
```

Zero numeric claims changed. The reverted files are byte-identical to `HEAD`.

## 7. Not done, and why

* **The migration.** §2. Blocked on a generator change the bounds exclude.
  `sec:eval-rq4` and `sec:eval-provable` — the two float-free candidates — were
  not attempted, because the pass's remaining room went into establishing why
  the first one stopped, and that finding is worth more than 1.8 pages.
* **§VII untouched**, third pass running. It is a compression job, not a
  migration: 3 655 words, no floats, and every one of the paper's 371 citations
  must survive.
* **≤ 16 pages not reached.** The floor is 25, and §1 shows why migration alone
  cannot close it: §VI's four headline blocks are 4 035 words of the evidence
  the paper is for.

## 8. Raw outputs

```
check_paper_numbers.py    42 passed, 0 failed
validate_citations.py     OK: 371 citations, 0 invalid
tests/test_cross_document_references.py   6 passed
pages                     main 25, supplementary 5
words (sections)          22 764 (unchanged; migration reverted)
numeric claims changed    0
generated/ hand-edited    none
tree state                paper/sections/*.tex and supplementary.tex identical to HEAD
```

**During the attempt**, before the revert: supplementary reached 6 pages, §VI
7 350 words, and the gate correctly reported
`FAIL every reference in the supplementary resolves inside the supplementary`
until all ten sites were converted. That failure is the pass's main evidence
that the verifier works on a real migration and not only on its tests.
