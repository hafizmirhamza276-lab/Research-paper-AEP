# Phase 31 — the 28.0 ms still in the PDF, and the class of defect it belongs to

**Rule 4.** Committed with the pass. **Issued:** 2026-09-15.

## The prompt, as issued

> The paper states 28.0 ms today, in the built PDF, in a caption that
> contradicts §VI's own "an ordering and not a partition". Phase 26 retired that
> figure and every gate stayed green, because the number is a hardcoded string
> in the generator rather than a macro — and rule 3's entire apparatus sees only
> macros. This pass fixes the number and closes the blind spot that hid it.
>
> 1. Commit this prompt.  2. Fix the caption at its source, both readings per
> amendment 2.  3. Sweep the generator for every other hardcoded number — this
> is the pass's real work.  4. Make the class detectable; rule 13, R17.
> 5. Record an R14 instance with the shape named.  6. Check the built PDF, not
> the source.  7. Regenerate, build four, gates green.

## Corrections and deviations, recorded rather than applied silently

**1. It was not a hardcoded string.** The source read `f"{tex(b3 - b0)}"` — a
value **computed inline** from the three-run medians. Same wrong number; a
broader class. The defect is *any number the generator prints that no macro
backs*, computed or typed, and the gate is built on that.

**2. One `28.0` remains in `main.pdf` and I left it.** It is a data cell in
`tab:latency`, in a row that prints `3` in a `runs` column — correctly derived
and correctly scoped, unlike the caption. Removing it means deleting a row
(forbidden) or repointing `--analysis` (which would move frozen macros, also
forbidden). The acceptance criterion "absent from all four PDFs" is **not met**;
report §4 says why and names the fix for a pass that can make it.

**3. The source-level sweep was mostly noise** — 261 literals, 106 computed
interpolations, almost all provenance comments, macro values, paths and seeds.
The surface that matters is the generated output, and there the answer is one
genuine offender across every caption in the paper.
