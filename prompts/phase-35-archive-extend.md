# Phase 35 — extend the archive to cover every cell the paper cites

**Rule 4.** Committed with the pass. **Issued:** 2026-09-15.

## The prompt, as issued

> The archive covers 20 roots from three trees, built 2026-09-03. Five
> referenced collection trees — 852 MB — are outside it. Two back claims the
> paper makes. The deposit cannot proceed until each is either inside the
> archive or explicitly declared outside it.
>
> 1. Commit this prompt.  2. Establish what each of the five is and whether the
> paper depends on it; rule on all five explicitly.  3. Verify each tree before
> archiving; forward-only caveat per tree.  4. Extend ADDITIVELY — 87fa2d53…
> must still verify.  5. Anything not archived is declared in docs/29 by name.
> 6. Make README, ARTIFACT.md §5, docs/29 and docs/36 agree.  7. State where the
> archive lives and how many copies exist.  8. R15 scoped.
>
> Out of scope: deleting anything, the upload itself, any .tex change.

## Corrections and deviations, recorded rather than applied silently

**1. Phase 34's 852 MB overstated the evidence gap.** It was right about what
sat outside the archive and wrong to imply all of it was evidence. `/root/aep-5b`
holds only transient smoke output the 2026-09-03 archive had **already excluded
by name**, and `/root/aep-stage3` has **zero run directories** — a source
checkout. The real gap was **408 MB**, now archived. docs/36 carries the
correction in place.

**2. Phase 13 turned out to back a published claim**, not only `docs/31`:
`numbers.tex:529-543` derives the replication interval §VIII calls "the only
session-clustered interval in this paper that excludes zero". Archived.

**3. The builder reports `0 runs` for the WS-4 and WS-6 roots** because its
detector looks for a `*-r<N>` suffix they do not use at top level. The data is
present — 1 332 run directories counted directly in the extracted tar. A
cosmetic defect in a summary line, recorded not fixed.

**4. The extension existed in one copy when built.** Mirrored to the second
filesystem and digest-verified. Both archives are still on one machine, which is
what the deposit fixes.
