# Phase 8.4 — commit `38ad8cd` claims more than its timestamp supports

**Nothing is amended.** The commit stands, the report it introduced stands, and
the 0.02 threshold is untouched. What is recorded here is that the commit's
**subject line is false as written**, discovered by checking it against the
mechanism that commit itself nominates as authoritative.

The substantive claim survives intact. The overclaim is in the framing, and the
framing is what a reader meets first.

---

## 1. The claim

    38ad8cd  Phase 8: the 0.02 threshold's provenance, computed before sessions 3-4 exist

and, in the body of
`reports/phase-report-8-amendment-3-threshold-provenance-2026-08-28.md`:

> **Committed while sessions 3 and 4 are still collecting**, so that what was
> computable at the time the threshold was set is on the record before the data
> it will judge exists.

## 2. The timestamps

All from `git show -s`, and from the frozen artefacts of the sessions
themselves — not from any narrative account.

| event | timestamp (+0500) | source |
|---|---|---|
| `850f221` — amendment 3 fixes the threshold | **2026-08-28 13:58:41** | `git show -s --format=%ci` |
| session 3 collection starts | **2026-08-28 16:48:39** | s3 `analysis/container-precondition.json` `captured_at`; s3 `analysis/foreign-load-sample.json` `window_start` |
| **`38ad8cd` — provenance report committed** | **2026-08-28 17:01:17** | `git show -s --format=%ci`, author and committer date identical |
| session 3 collection completes | 2026-08-28 18:07:15 | session log `complete at` |
| session 4 collection starts | **2026-08-28 18:07:19** | s4 `analysis/container-precondition.json` `captured_at` |

**`38ad8cd` landed 12 minutes 38 seconds after session 3's collection began.**

## 3. How far into session 3, exactly

Counted from `matrix-progress.jsonl` — the structured record R2 names as
authoritative — rather than estimated from the mean run time.

`started_at` in that file is a **monotonic** clock reading, not a wall-clock
timestamp, so it was anchored to the session's known start. The anchor checks
out: the monotonic span of the 120 runs is 4725.6 s against a wall span of
4716 s from collection start to completion, a 9.6 s disagreement against a mean
run of 39 s. The count below is therefore good to well under one run.

At `17:01:17`, 758 s into session 3:

- **19 of 120 runs had finished**
- **a 20th was in flight**

So roughly one sixth of session 3 existed, on disk, when the commit that says
sessions 3 and 4 do not yet exist was written.

## 4. What is and is not damaged

**Not damaged — the substantive claim.** Three separate facts carry it:

1. The threshold was **fixed at `850f221`, 13:58:41**, two hours and fifty
   minutes before session 3 started. Nothing about session 3 could have informed
   the number itself.
2. The provenance computation in `38ad8cd` used **only sessions 1 and 2**. Its
   own table lists two rows. Sessions 3 and 4 contribute nothing to it.
3. `covariate_check.py` reads `analysis/per-execution.csv` from a **frozen**
   root. Session 3 had not been frozen at 17:01:17 and had no `analysis/`
   directory to read. The computation could not have touched it even by
   accident.

**Damaged — the framing, in two places.**

- The **subject line**, "computed before sessions 3-4 exist", is false for
  session 3. It is true for session 4, which started an hour later.
- The **body's** "before the data it will judge exists" is false in the same
  way. Session 3's data had begun to exist. The body's "while sessions 3 and 4
  are still collecting" is separately imprecise in the other direction: session 3
  was collecting, session 4 had not started.

**Why this matters more than its size suggests.** The report's own §2 says
commit timestamps are "the only account that cannot be reconstructed favourably
afterwards", and then rests its case on them. That mechanism works — it is
exactly what caught this. But a reader who checks the subject line against the
timestamp finds a mismatch in the one document whose entire subject is the
integrity of a claim about ordering. The credibility cost of an inaccurate
sentence is highest in the document arguing that sentences like it should be
checked.

## 5. The class this belongs to

**A claim asserted from memory of the plan rather than derived from the record.**
The commit's author knew the *intent* — publish the provenance before sessions 3
and 4 land — and wrote the subject from the intent instead of from the clock.
The intent was met for session 4 and missed for session 3 by twelve minutes.

This is the same substitution as two others in the same phase's work, and the
repetition is the finding rather than any one instance:

- a `.gitignore` block asserted to need 21 files per root when the freeze names
  19 — the count taken from a remembered "18 OK" that was 18 *entries*, not 18
  analysis files;
- an unhashed-file list asserted as four top-level-only files when the listing
  gives five.

In all three, a number or an ordering was recalled where it should have been
recomputed, and in all three the recomputation was cheap. The remedy is R2's
already-stated rule applied to prose: **a claim about the record is derived from
the record at the moment it is written.**

## 6. What 8.5 and 8.6 must carry

- Cite `850f221` (13:58:41), not `38ad8cd`, as the commit that fixes the
  threshold before the data. That is the claim that is actually true, and it is
  the stronger one.
- Do not repeat "computed before sessions 3-4 exist". The accurate form is:
  **computed from sessions 1 and 2 only, and committed before either session 3 or
  session 4 was frozen or analysed.**
- Carry §3's disclosure from the original provenance report verbatim, unchanged:
  the threshold was set with one session visible, and that session's value fell
  below it at 0.62× the threshold.

## 7. Not done

The commit is **not** amended, the report is **not** edited, and no history is
rewritten. `38ad8cd` is published and three commits deep; rewriting it would
destroy the ordering evidence that this finding depends on and that the original
report correctly identified as the only unfalsifiable account. The wrong subject
line stays, with this document beside it.
