# Phase 34 — reconcile the working tree with origin, nothing unaccounted for

**Rule 4.** Committed with the pass. **Issued:** 2026-09-15.

## The prompt, as issued

> Before the deposit, nothing may exist only on this machine by accident. The
> goal is **not** to push everything: raw run trees, sqlite ledgers and logs are
> excluded deliberately and belong in the Zenodo archive. The goal is that every
> untracked or ignored path is either pushed or has a recorded reason it is not.
>
> 1. Commit this prompt.  2. Inventory before touching anything.  3. Classify
> each row into exactly one of four classes; empty the fourth.  4. Check the
> ignore rules are not hiding authored work.  5. Check the other direction —
> what the repo references but does not contain.  6. Push.  7. Prove nothing was
> lost.  8. Write docs/36.  9. R15 scoped.
>
> Out of scope: **deleting anything.** This pass classifies; a later one may
> remove.

## Corrections and deviations, recorded rather than applied silently

**1. 26 378 ignored paths were classified by rule, not listed as rows.** The
prompt asked for a row per path. A 26 000-row document is not read, so the
equivalent-but-stronger form is used: every path is classified, and `docs/36`
§2.7 is the residue check showing nothing falls through.

**2. The finding is in step 5's direction, not step 3's.** The unexplained class
emptied to zero and no authored file is ignored. But **five referenced
collection trees totalling 852 MB are not in the archive WS-2 is about to
deposit**, and two of them — `/root/aep-phase14` and `/root/aep-ws6` — back
claims §VI-C and §VI-A make.

**3. Two things reported rather than changed**, because both are close to
deletion: `paper/.build-provenance.json` is ignored while its three siblings are
tracked, and `.scratch/` plus the session transcript remain on disk.
