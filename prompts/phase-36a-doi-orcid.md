# Phase 36a — record the reserved DOI and the ORCID, accurately

**Rule 4.** Committed with the pass. **Issued:** 2026-09-15.

## The prompt, as issued

> A Zenodo draft exists with a **reserved** DOI, `10.5281/zenodo.22766567`.
> Reserved is not registered: it resolves only once the record is published, and
> the files are not uploaded yet. This pass records the identifier and the ORCID
> in the repository, stating exactly what is true today.
>
> 1. Commit this prompt.  2. README — replace the pending language; a reader
> must be able to tell that clicking the DOI today will not work.  3.
> ARTIFACT.md §5 — each pending item edited to its current state, not deleted.
> 4. docs/29 — mark what the reservation closes, leave upload/verify/publish
> open.  5. ORCID in README and in the non-anonymous author block; rule 13 —
> grep the anonymous PDF.  6. State the copy count.  7. R15 scoped.
>
> **No sentence may imply the DOI resolves today.** It does not.

## Corrections and deviations, recorded rather than applied silently

**1. Setting `\archivedoi` alone would have made the paper lie.** The existing
toggle had two states, and anything other than PENDING selected "deposited at
https://doi.org/…". A third state, RESERVED, was added; the built PDF contains
"deposited at" zero times.

**2. The new anonymity check failed on its first run, correctly, on a
bibliography DOI** — `10.5555/1286831.1286846`, a cited reference present in
both builds by design. Matching every DOI was too broad; narrowed to the archive
DOI, read from `main.tex` so no identifying string is written into the checking
file itself.

**3. The check also fails if the public build contains no ORCID or DOI**, so it
cannot start passing because the strings stopped being emitted.
