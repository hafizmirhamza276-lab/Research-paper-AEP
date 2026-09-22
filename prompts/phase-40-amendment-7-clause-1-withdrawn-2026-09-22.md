# Amendment 7 — clause 1 cannot be met, and is withdrawn rather than passed

**Amends `prompts/phase-40-amendment-6-same-payment-redecision-2026-09-21.md`
§9.** Committed **before any further live call**.

**A criterion correction, not a structural amendment.** Amendment 6 §8's
closure of structural amendments is untouched and is not reopened by this:
nothing in the instrument changes — no turn semantics, no prompt, no loop, no
cap, no metric, no system descriptor. What changes is a stage criterion's
wording, which is exactly what amendment 5 changed when it replaced C4.

The precedent is close enough to name: **C4 asked for a measurement no healthy
stage could produce; clause 1 asks for an event no regime can produce.** Both
are errors inside a criterion rather than defects in what is being measured,
and §8's list of what would justify a structural amendment — a crash, a leak,
a malformed path — is not engaged by either.

---

## 1. What was asked

Amendment 6 §9 clause 1 requires stage 30 to show that

> *"every decision that was made and observed is replayed with no model call."*

## 2. It cannot be met in the pre-registered regime

A decision is observed only if it was **dispatched and the worker survived
it**. A `Stop` executes nothing and can never be observed; a dispatch that is
`SIGKILL`ed mid-flight never returns and can never be observed either.

`runner.resume_from_index` starts the replacement worker at
`from_index = last_started`, and `InteractiveDriver` walks only executions with
`execution_index >= from_index`. The crash suppression un-arms **exactly** the
execution at `from_index`, so at `p(crash)=1.0` the first armed execution the
worker reaches is the next one: it always dies strictly above where it started.
No decision at the index it died on can be observed, so every decision it did
observe lies strictly below where the next lifetime begins — and `from_index`
is non-decreasing thereafter.

**No later lifetime ever sees a made-and-observed decision, so none can replay
one.**

The conclusion does not depend on `p(crash)=1.0`. It follows from the resume
rule at any crash rate, and no agent behaviour reaches it: every branch —
dispatch again, decline, stop — either ends the run or advances `from_index`
past what was observed.

Checked against the amendment-6 stub run, the only collection that has produced
observations: four lifetimes at `from_index` 0, 0, 1, 2, with observations at
steps 0 and 2, and no later lifetime's scaffold containing either.
`reports/phase-report-40-clause1-and-stage-100-prep-2026-09-22.md` §1 carries
the derivation and the evidence, including a correction to a first probe of
mine that ignored ordering and reported false positives.

**Amendment 6 created the clause and made it unreachable in the same change.**
§3.2 stopped replaying the crashed decision — correctly, because replaying it
re-dispatched without asking the agent — which left "made and observed" as the
only replayable category, and the resume rule excludes it.

## 3. Clause 1 is NOT recorded as passed

**Stage 30's record stands as PARTIAL.** Clause 1 was not met, is not met, and
is not retroactively satisfied by this ruling. A criterion withdrawn because it
cannot be met is not a criterion passed, and any later summary of stage 30
carries it as *not exercised, subsequently withdrawn as unreachable*.

## 4. What replaces it: nothing

Clause 1 is **withdrawn**, not rewritten. The property it was reaching for —
that a respawn costs no model call for work already decided — is already
carried by §6's original wording, which stage 30 satisfied and which remains in
force:

> *"re-enters the loop reading the transcript, issuing no new model call for
> already-decided steps."*

Clauses 2 and 3 of amendment 6 §9 are unchanged and both passed at stage 30.

**No replacement clause is invented.** A clause written now, after seeing which
events this regime produces, would be a criterion fitted to the data — which is
what §9's whole discipline exists to prevent.

## 5. §9's counter

Clause 1 never failed; it was never reachable. **§9's "fails its criterion
twice" counter is not incremented by it**, and this ruling resets no other
counter. Amendment 5's ruling on C4 stands, and C4′'s counter remains at zero.

## 6. Stage 100 is opened, by author decision, and this is an override

**The author has ruled that stage 30's remaining clauses are sufficient to open
stage 100.** Those are:

| | verdict at stage 30 |
|---|---|
| §6 original — respawn, read the transcript, no new call for an already-decided step | passed |
| amendment 6 §9 clause 2 — exactly one new call about the crashed payment | passed |
| amendment 6 §9 clause 3 — that re-decision is the agent's | passed |
| void rate recorded | passed, 0 of 2 |
| C1, C2, C3, C4′ | passed |

**This is an override and is recorded as one.** §6 says *"Nothing advances
automatically"* and stage 30's own verdict is PARTIAL, not passed. Advancing
from a partial stage is a decision the author is making explicitly, with the
reason on the record: the one clause that did not pass is the one this
amendment has just established could never have passed, and holding stage 100
behind it would hold it behind a criterion that no collection can satisfy.

It is not a precedent for advancing from any other partial stage. A clause that
is *unreached* is different from a clause that is *unreachable*, and only the
second is overridden here.

## 7. Open, and to be resolved in writing before stage 300

**The stage-300 run count does not reach §1's design, and this amendment does
not fix it.**

§1 fixes 10 runs per system, 20 in total. §6 assigns the full design to stage
300, whose budget is 300 calls. With amendment 6 §7's per-run cap of 20 at one
worker, `20N ≤ 300` gives **N ≤ 15**, five runs short of 20.

That is a tension between §1's design and §6's staging, and it is **noted as
open, not resolved now**. Resolving it needs a written derivation — of the
per-run cap, the collection budget, the worker count, or the design's run
count — and that derivation must be committed **before stage 300 runs**, not
alongside its data.

Nothing about stage 100 depends on it: four runs at a 100-call budget is
settled separately and fits.

## 8. What is unchanged

§1's design, §1.1's harness-assigned target, §2's metric and its prohibition on
rates, §3's controls, §4's `PLANNER_FILTERED`, §5's transcript requirements,
§6's C1–C3 and C4′, §8's failure definitions, and §9's spend and date limbs.
Amendments 1–6 stand in full, **including amendment 6 §8's closure of
structural amendments**, which this ruling does not reopen.
