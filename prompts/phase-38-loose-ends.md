# Phase 38 — the three items phase 34 left, and the prediction-content gap

**Rule 4.** Committed with the pass. **Issued:** 2026-09-15.

## The prompt, as issued

> Three loose ends, all small, all close enough to deletion that earlier bounds
> excluded them. Doing them now keeps the submission package clean.
>
> 1. Commit this prompt.
> 2. `paper/.build-provenance.json` — rule one way or the other, and record
>    which, so the asymmetry stops being a thing a reader has to wonder about.
> 3. `.scratch/` and the session transcript — delete or keep, deliberately, and
>    say which.
> 4. Close the audit's content gap cheaply: record the blob hash of every
>    prediction at its first commit, tracked, so a later rewrite is detectable.
>    Wire the comparison into the existing check. Rule 13.
> 5. R15 scoped. Zero `.tex`.
>
> Out of scope: any `.tex`, any analysis, the deposit.

## Corrections and deviations, recorded rather than applied silently

**1. Item 2 was not tidying.** The ignore rule's stated reason is factually wrong
about what the file contains, and one gitignored source — `paper/.ai/track.md` —
meant **the three tracked stamps could not verify in a clean clone**. Fixed at
the cause; all four are now tracked and all four read FRESH against a simulated
clone.

**2. The content check found two edited pre-registrations on its first run.**
Phase 9's amendments predate its data by six days — a convention deviation, not
a violation. WS-6's edits postdate its data, were read rather than assumed, and
add self-labelled post-data material that alters no hypothesis, threshold or
margin. Both recorded with their rulings; no history rewritten.

**3. Phase 34 classified `.scratch/` wrongly** as purely transient. It holds
authored phase-11 probes. Kept, with the correction in `docs/36` §2.5.

**4. My own wiring had a defect.** `audit()` read the real repository's blob
record regardless of which repository it was auditing, which broke two existing
tests as soon as the check was added. The path is now repo-relative.
