# Phase 24 — WS-5 → manuscript: H1–H5 into §VI-RQ3 and §VIII

**Rule 4.** Committed with the pass that executed it.

**Issued:** 2026-09-15.

## The prompt, as issued

> Every WS-5 collection is closed. Five pre-registered hypotheses have verdicts
> and none has reached the manuscript. §VI-RQ3 still asserts a 28.0 ms
> decomposition that the project's own data no longer supports. This pass puts
> the findings in the paper, once, because §VI and §VIII have to agree with each
> other and with the tables.
>
> 1. Commit this prompt.
> 2. Regenerate `numbers.tex` so `\HarnessLoc` reads 27,127, rebuild, get
>    `check_paper_numbers.py` to 33/33 before any prose is touched.
> 3. Add the rule phase 23 earned, to `docs/25`.
> 4. §VI-RQ3 — retire the 28.0 ms figure.
> 5. The `always` arm — a near-zero or negative cost is the expected shape.
> 6. H2–H5 each get a sentence; H4's +9.33 pp belongs in §VI.
> 7. §VIII — three things, and no more.
> 8. Rule 3 on every number that moves.
> 9. Regenerate, build both ways, report the page count delta.
>
> In scope: `06-evaluation.tex`, `08-threats.tex`, regenerated files under
> `paper/generated/`, `reports/`, `prompts/`. Out of scope: hand-editing
> anything generated, any new collection, any re-analysis. **If a number you
> need does not exist in a tracked CSV, stop and say so.**

## Corrections and deviations, recorded rather than applied silently

**1. Steps 4, 5 and 6 were not done, and the bounds are why.** All 197 macros in
`numbers.tex` come from the three-run frozen cells; not one is derived from a
WS-5 root. `paper_tables.py`'s five input paths cannot be pointed at one, and
`check_paper_numbers.py` hardcodes them as defaults. The numbers exist in
tracked CSVs; the generator path from those CSVs to `numbers.tex` does not, and
rule 1 forbids typing them. The minimal unblocking change is listed in the phase
24 report §4.

**2. R17's placement.** The prompt said "beside R13 and R16a". It became a
top-level rule with cross-references to R3, R4, R13 and R16a, because the second
of its three occurrences was not about a results root and the principle
generalises past R16.

**3. The build order is not the obvious one.** Regenerating `numbers.tex` makes
all four documents stale, and `build_paper.sh` refuses to overwrite `main.pdf`
while any sibling is stale. Supplementaries must be built first.
