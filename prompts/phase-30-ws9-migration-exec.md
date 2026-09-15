# Phase 30 — WS-9: the migration, executed

**Rule 4.** Committed with the pass. **Issued:** 2026-09-15.

## The prompt, as issued

> ~8 500 words, on the order of forty reference sites. The verifier now exists
> and a half-migrated tree commits a red gate, which is the safety property this
> pass depends on.
>
> 1. Commit this prompt.  2. Write the split down before moving anything — the
> criterion is that a reader of the main text alone can follow every claim.
> 3. Migrate in verifiable increments; run the gate after each block;
> `sec:eval-deployment` is the known-hard one, do it early.  4. Numbers travel
> with their comments.  5. Per-change page table.  6. 42/42, citations 371/0.
>
> Out of scope: any numeric claim, rule 1 on `generated/`, no new macro, no
> analysis, no new gate. Anything cut is moved, not dropped.

## Corrections and deviations, recorded rather than applied silently

**1. `sec:eval-deployment` was migrated end to end and then reverted.** It
works: supplementary 5 → 6 pages, §VI 8 177 → 7 350 words, ten reference sites
converted. It cannot be completed in scope because
`generated/table-deployment-choice.tex` carries four `\cref`s into the main text
inside its caption — rule 1 forbids editing that file and `paper_tables.py` is
not in scope. Reverted rather than committed half-done; the gate is what stopped
it, which is the property the pass was built on.

**2. A defect found, not fixed: the paper currently states 28.0 ms**, the figure
phase 26 retired, as a hardcoded string in the same generated caption
(`paper_tables.py:1033`). It is invisible to every gate because it is a literal
and not a macro. Report §3. It should be the next pass's first action.

**3. The verifier was corrected and kept.** Phase 28 attributed every generated
file to the main text; the first migration broke that assumption. It now
attributes each by whichever document `\input`s it.

**4. ≤ 16 pages not reached.** §1 shows migration alone cannot close it: §VI's
four headline blocks are 4 035 words of the evidence the paper exists to present.
