# Phase 25 — WS-5 macros: unblock §VI-RQ3

**Rule 4.** Committed with the pass that executed it. **Issued:** 2026-09-15.

## The prompt, as issued

> Every WS-5 number exists in a tracked CSV. The generator path from those CSVs
> to `numbers.tex` does not, so §VI-RQ3 cannot be corrected without typing
> numbers, which rule 1 forbids. This pass builds the path. It changes no prose.
>
> 1. Commit this prompt.
> 2. Add the four inputs, no defaults pointing at a frozen root; make the gate
>    default to the same set so the two cannot disagree.
> 3. Emit the macros §VI-RQ3 needs, each traceable to one CSV cell. Both
>    readings of protocol−barrier; name 15-run macros so they cannot be
>    confused with 3-run ones.
> 4. Rule 14 + R17 on both scripts.
> 5. Prove the existing 197 are untouched. Any changed value is a stop
>    condition.
> 6. Regenerate, build all four in order, state the page delta.
>
> Out of scope: zero `.tex` hand-edits, no new analysis, existing 197 must not
> change value.

## Corrections and deviations, recorded rather than applied silently

**1. The gate had to gain a mechanism, and it is not a hole.**
`check_macros_are_used` fails on any macro defined and not used, so emitting 17
macros a pass ahead of their prose fails by construction. Writing the prose was
out of scope and not emitting them defeats the pass. `PENDING_MACROS` was added:
a name-to-reason map with **two checks that can fail** — a pending macro that no
longer exists is stale, a pending macro that is used is an entry nobody deleted
— plus a `NOTE` printed on every run. Phase 26 cannot finish without emptying
it, because using a macro trips the second check.

**2. `paper_tables.py` now imports `power_analysis.lower_mode_difference`**
rather than reimplementing amendment 3's pinned boundary, so the manuscript and
the pre-registered analysis cannot drift apart on where the lower mode ends.

**3. H2, H3 and H5 still have no macros**, and phase 25 report §6 separates the
three reasons. H5's is the only technical one: its interval needs a stratified
bootstrap the generator does not have, and adding an estimator is not a
plumbing change.
