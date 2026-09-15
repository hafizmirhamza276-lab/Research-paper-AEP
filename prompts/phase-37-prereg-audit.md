# Phase 37 — WS-10: the pre-registration order audit

**Rule 4.** Committed with the pass. **Issued:** 2026-09-15.

## The prompt, as issued

> Rule 5 requires that for every experimental cell, the prediction file's commit
> predates the first data commit. Rule 4 requires the issued prompt be committed
> before a phase's first data commit. Nothing has ever verified them **across
> the whole history at once**, which is what a reviewer or an artifact evaluator
> would do.
>
> 1. Commit this prompt.  2. Enumerate the cells FROM THE DATA, not from the
> reports.  3. Check both orderings -- timestamp and ancestry.  4. Rule 13,
> under R17.  5. Report every cell, including the passes; amendments get their
> own rows.  6. State the domain and the blind spots.  7. Wire into CI if green.
> 8. R15 scoped.
>
> Out of scope: **rewriting history.** A violation is recorded, never fixed by
> amending commits.

## Corrections and deviations, recorded rather than applied silently

**1. No violation exists.** 31 cells: 27 ok, 4 exempt, 0 failing. Nothing was
fixed by rewriting history because there was nothing to fix.

**2. The audit caught a mistyped path in its own table on the first run** --
`phase-21-ws9-...` for `ws5` -- because it refuses to skip a path that names
nothing. A lenient version would have reported that cell passing on a prompt
that does not exist. There is now a test citing this incident.

**3. The audit caught a defect in itself.** `git log -- <path>` searches only the
current branch, so a prediction on an unmerged branch was reported "not in the
history" rather than "not an ancestor". Both are failures, so the verdict was
right, but the message was wrong and would have made a reviewer distrust the
tool. `first_commit` now searches `--all`.

**4. `fetch-depth: 0` in CI is load-bearing**, not hygiene: the audit reads
commit dates and runs `merge-base`, and a shallow clone would make it pass by
being unable to look.
