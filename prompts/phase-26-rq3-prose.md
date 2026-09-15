# Phase 26 — §VI-RQ3: the prose, over macros that now exist

**Rule 4.** Committed with the pass. **Issued:** 2026-09-15.

## The prompt, as issued

> Prose only. Every number needed is a macro. `PENDING_MACROS` must be empty
> when this pass ends — that is the gate's design and it is the completion
> criterion.
>
> 1. Commit this prompt.  2. Retire 28.0 ms, both readings, intervals
> in-sentence.  3. The `always` result is the headline; `\BarrierCostAlways`
> comes out of the manuscript, not replaced or contrasted.  4. H4 into §VI.
> 5. `08-threats.tex:303`'s "needs more crash-free runs" comes out.  6. Rule 3
> on every changed claim.  7. Empty `PENDING_MACROS`.  8. Rule 11 / M5; report
> the page delta.  9. Regenerate, build four, gate 39, citations 371/0.

## Corrections and deviations, recorded rather than applied silently

**1. Replacing the prose orphaned 15 macros, and the gate fails on orphans.**
They are superseded three-run estimates, not "pending" — `PENDING_MACROS` means
prose-not-written-yet and asserts the macro is not in use. So they are no longer
emitted: `SUPERSEDED_MACROS` in `paper_tables.py`, with the reason attached.
That file was not in this pass's listed scope; the alternative was a red gate or
a corrupted mechanism. Report §5.

**2. `\BarrierCostEach` was suppressed in error** and broke both supplementary
builds — `paper/supplementary.tex:202` quotes it, which is why the orphan check
had correctly not listed it. Un-suppressed. A three-run derived figure therefore
survives in the supplementary while §VI quotes fifteen-run ones; recorded as a
follow-up since `supplementary.tex` was out of scope.

**3. Four tests failed and were rewritten, not deleted**, to assert that the
superseded macros are *not* emitted. Report §10.

**4. The page count did not fall.** The pass was asked to remove more than it
adds; §VI grew 59 lines net. Stated in §8 rather than presented as neutral.
