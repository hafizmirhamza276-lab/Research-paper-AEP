# Phase 28 — WS-9: the structural migration, §VI and §VII to the supplementary

**Rule 4.** Committed with the pass. **Issued:** 2026-09-15.

## The prompt, as issued

> 25 pages, target 16, ~8 500 words. Phase 27 established this is a migration,
> not a trim, and that doing it partially splits `\cref` targets across
> documents while every gate still passes — a gate that cannot see the defect it
> should catch. That is the first thing to fix.
>
> 1. Commit this prompt.  2. **First: make a broken cross-document reference
> fail a gate** — build it before moving anything and watch it fail (rule 13,
> R17).  3. Decide the split before executing it.  4. Migrate; macro multiset
> identical, proven in Python.  5. Per-change page count.  6. Regenerate, build
> four, gate green.
>
> Also: execute the WS-0 ruling, blocker → declared limitation, with cross-host
> replication of one frozen cell as the named future-work item. Tick WS-1.
>
> Out of scope: any numeric claim, new analysis, new macro.

## Corrections and deviations, recorded rather than applied silently

**1. Step 2 is done; the migration is not started.** The check exists, is wired
into the gate (39 → 42), and was watched failing on all four branches from a
disposable tree. The move itself was not begun: `sec:eval-deployment` alone is
six reference sites across three files, and the full migration is ~8 500 words
and on the order of forty sites. The pass's own premise is that a partial
migration is the failure mode, and with the working room left, starting one
would have produced exactly that — now detectable, so committing it would mean
committing a red gate.

**2. WS-0's box in `docs/26` §7 is left unticked on purpose.** It describes work
that has not been done. What changed is that it no longer blocks submission,
and that is recorded beside the box rather than by ticking it.

**3. The full suite was not run before the report was written**, although
`check_paper_numbers.py` changed. Launched before committing rather than left as
a gap.
