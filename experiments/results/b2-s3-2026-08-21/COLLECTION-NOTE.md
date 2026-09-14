# Collection note: this session is cell-major, and that is permanent.

**Read this before using these runs in any paired comparison.**

This session collects all 30 `AEP_FULL` runs first and then all 30
`B3_INTENT_NO_BARRIER` runs. It does **not** interleave the two arms.

## Why that matters

Run-level interleaving was introduced on 2026-08-28 in `5b601d0`,
*"Phase 8 pre-registration amendment 1: interleave at run level, because arm
and drift are collinear"*. Its comment in `experiments/run_matrix.py` states
the problem this session has:

> one arm of a paired comparison was always the earlier block and the other
> always the later one, so arm and drift were *perfectly collinear*: not a
> large confound to adjust for, but a **non-identifiable** one that no number
> of sessions separates.

These four sessions are dated **21 August** — a week before that commit.
They were collected under the design it replaced, and they were never
re-collected.

## What was decided, and what was not

Phase 22 launched two further sessions and stopped them at 19 of 60 runs on
finding they interleave while these four do not. Adding them would have put
two designs inside one paired sign test; matching them would have meant
reverting `5b601d0` so that new data resembled old data.

**The precedent for the other choice exists and was deliberately not
followed.** On 28 August the identical defect was met by re-collecting the
whole comparison as `b2-paired-v2-*` and retaining the v1 session unpooled.
The class sweep could have had a v2 the same way, at about six hours. It was
ruled against because amendment 1 §2 had already fixed this result as **a
bound rather than a test** — so the 2/2ⁿ floor the extra sessions would have
moved is not load-bearing, and §VIII's claim (that this design *could not*
have found an effect) is a cleaner theorem at four sessions than at six of
mixed design.

Full ruling: `reports/phase-report-ws5-prediction-amendment-4-2026-09-14.md`.
How it was found: `reports/phase-report-22-ws5-class-sweep-2026-09-14.md`.

## The other asymmetry, while you are here

All 60 runs record `suspend_disabled_declared = false`, so all 60 are already
excluded from every absolute-timing aggregate
(`runs_dropped_for_undeclared_suspend_policy = 30, 30`). Rates are
unaffected — a run failing that gate still contributes its counts. **Anything
computed from these sessions is a rate claim.**
