# Claims to review

**This file changes no manuscript text.** It collects places where a claim may
be factually wrong, or may sit awkwardly beside a claim made elsewhere in the
paper, so that the independent audit has them in one list. Entries are raised
during the prose passes, which are language-only and may not resolve them.

**A prose pass never resolves an entry here.** If a rewrite would settle a
question of fact by choosing different words, the wording stays as close to the
original as possible and the question is recorded below instead.

| status | meaning |
|---|---|
| **open** | raised, not investigated |
| **checked** | investigated and found not to be a problem, with the reason |
| **resolved** | the manuscript was changed by an author decision, with the commit |
| **reopened** | closed once, and the closure was wrong — with what it got right, what it missed, and what would close it properly |

**A closed entry is not a settled one.** Entry 3 was marked **checked** on
2026-09-23 and reopened on 2026-09-24 after an external audit found that the
check had tested one half of a two-part sentence. When reading a **checked**
entry here, read what was actually tested, not what the entry is about.

---

## 1. §I says the uncertainty is *never* in the accounts; the evidence for that is scoped to what was measured

**Status: RESOLVED 2026-09-23.** Raised 2026-09-22 during the §I prose pass,
under the author's ruling that the original absolute be restored rather than
softened by a language edit. Closed by the author taking the **empirical**
reading: §I now carries C3's scope condition. The resolution is at §
*How it was resolved* below.

### The absolute

`paper/sections/01-introduction.tex`, closing the trilemma discussion:

> What a designer can choose is where the uncertainty is allowed to surface.
> AEP places it in a durable state that an operator can see, and **never in the
> accounts**.

This was the original wording. A draft of the §I rewrite had weakened it to
*"and keeps it out of the accounts"*; the author ruled that a language pass must
not weaken a claim, so *never* is restored and the question is recorded here.

### The scoped statements it sits beside

**C3, in the same section**, states the same property with a scope condition:

> AEP records no undetected duplicate and no lost effect **in any cell
> measured**, and the baselines without a pre-dispatch record duplicate in most
> crashed executions.

**`paper/sections/08-threats.tex`**, *The detection finding has no referent
outside this artifact*:

> Nothing external to this artifact establishes that a pre-dispatch record
> without an fsync barrier suffices for detection: the proposition is supported
> by two systems we wrote, measured by a harness we wrote, against a provider we
> wrote.

**`paper/sections/06-evaluation.tex`**, `sec:eval-writeloss-cell`, on the
write-loss regime:

> `WAITAOF` returned success for every durability acknowledgement requested
> after the device had stopped accepting writes […] The barrier withholds
> dispatch on a *failed or absent* acknowledgement; it was handed a successful
> one and dispatched, behaving exactly as specified on an input that was false.

and, a little later, that the result *"bounds the guarantee to storage that
reports its own failures and says nothing about storage that does not."*

### The question for the audit

*Never* is a claim about the protocol. *In any cell measured* is a claim about
the collection. They are compatible if *never* is read as a statement of what
the protocol is designed to do, and in tension if a reader takes it as a
statement about what was observed to happen. The write-loss regime is the case
worth checking: there, AEP dispatched on an acknowledgement that was false, so
an effect was applied while the durability of its own record could not be
established.

Three things a reader might want settled, none of which a prose pass can decide:

1. Is *never* intended as a design property or as an empirical one?
2. Under the write-loss regime, could an applied effect have reached the
   accounts with no durable record accounting for it? `summary.json` reports
   `lost_effect` at zero throughout, so the answer may be no, in which case this
   entry closes as **checked**.
3. If *never* is meant empirically, should §I carry the same scope condition C3
   already carries?

**No text is changed by this entry.**

### Question 2 is now answered from the collected data, 2026-09-23

**No.** In the `write-loss-preack` regime both safety metrics are zero, on both
arms, with the interval collapsed:

| metric | system | successes / total | rate | CI | run clusters |
|---|---|---|---|---|---|
| `lost_effect_rate` | `AEP_FULL` | **0 / 300** | 0.0 | [0.0, 0.0] | 30 |
| `lost_effect_rate` | `B3_INTENT_NO_BARRIER` | **0 / 300** | 0.0 | [0.0, 0.0] | 30 |
| `undetected_duplicate_rate` | `AEP_FULL` | **0 / 300** | 0.0 | [0.0, 0.0] | 30 |
| `undetected_duplicate_rate` | `B3_INTENT_NO_BARRIER` | **0 / 300** | 0.0 | [0.0, 0.0] | 30 |

Source: `reports/raw/ws4-writeloss-s1-2026-09-07/analysis/`
`metric-lost-effect-rate.csv` and `metric-undetected-duplicate-rate.csv`,
`crash_point=none`, `response_class=NO_READBACK`,
`readback_keying=CALLER_REFERENCE`, 10 000 resamples, seed 20260806.

The host-level probe behind the same cell agrees on its own terms:
`g2-flakey-write-loss{,-rep2,-rep3}.json` each report
`acknowledged_survived 30/30`, `unacknowledged_lost 30/30`, `void 0`.

**What this settles and what it does not.** It settles that no effect reached
the accounts without a record accounting for it, in the regime that looked most
likely to produce one. It does not settle question 1 or question 3, because
those are about what *never* was written to mean. The nuance worth having in
front of you when you rule: in this regime AEP dispatched on an acknowledgement
that was false, so the *durability of the record* was not established even
though the record existed at dispatch and nothing was lost. The empirical
reading of *never* survives here, and it survives contingently.

### How it was resolved

**The empirical reading, by author decision, 2026-09-23.** §I takes C3's scope
condition.

> **Before:** …AEP places it in a durable state that an operator can see, and
> **never in the accounts**.
>
> **After:** …AEP places the uncertainty in a durable state that an operator can
> see, and **in every cell we measured, none of it reached the accounts**.

(*"it"* became *"the uncertainty"* in the same pass that introduced the name;
the antecedent is now two sentences back.)

**The author's reason, recorded as given:** AEP dispatched on a false
acknowledgement in the write-loss cell, so the durability of the record was
never established, and an unscoped *never* would claim something about
conditions that were not tested.

**Note what this does and does not concede.** The data in the section above is
clean — `lost_effect_rate` and `undetected_duplicate_rate` are both 0/300 on
both arms in `write-loss-preack`. So the unscoped *never* was not contradicted
by anything collected. It is scoped because the **conditions** under which it
would have been tested were not reached: the barrier was handed a successful
acknowledgement that was false, so the regime that could have produced a
counterexample was one the instrument could not detect. The scope condition
records the limit of the instrument, not a failure in the result.

§I and C3 now make the same claim in the same terms, which is the consistency
the entry was raised about.

---

## 2. The supplementary says every crashed AEP-full and B3 execution reached a terminal classification; 180 of them did not

**Status: RESOLVED 2026-09-23.** Raised earlier the same day during the RQ4
fact-finding, and closed by the author's Option 1 decision. The fix is in
§10 below.

### The statement

`paper/supplementary.tex:654-657`, in *RQ4: recovery*:

> Within that scope: **every AEP-full and B3 execution in the crashed regime
> reached a terminal classification**, and across `\RunsCollected{}` runs
> exactly one recorded a reconciliation disagreement.

### What the collected data says

`is_terminal` is defined in `experiments/analyze.py:266-273` as an
`outcome_class` in `{CONFIRMED_APPLIED, CONFIRMED_NOT_APPLIED,
DECLARED_AMBIGUOUS}`. Counted from `analysis/per-execution.csv`, crashed
regime:

| system | crash point | terminal / crashed |
|---|---|---|
| `AEP_FULL` | the other five | **450 / 450** |
| `AEP_FULL` | `before_intent_write` | **0 / 90** |
| `B3_INTENT_NO_BARRIER` | the other five | **450 / 450** |
| `B3_INTENT_NO_BARRIER` | `before_intent_write` | **0 / 90** |

All 180 non-terminal executions carry `outcome_class = NO_RECORD`.
`analysis/metric-recovery-success-rate.csv` reports the same thing as a rate:
`1.0` with CI `[1.0, 1.0]` at five crash points for both systems, and `0.0` at
`before_intent_write` for both.

### The question for the audit

At `before_intent_write` the worker dies before any intent exists, so there is
nothing for recovery to resolve. Reading `NO_RECORD` as a recovery *failure*
would be wrong, and the metric's `0.0` should not be read that way either.

But the sentence as written says *every* execution reached a terminal
classification, and under the project's own definition 180 did not. Three
readings, none of which a prose pass can choose between:

1. *Terminal classification* is meant loosely, as "the execution was
   classified", in which case `NO_RECORD` qualifies and the sentence is true
   but uses a term the analysis code defines differently.
2. The sentence means to scope itself to executions that wrote an intent, in
   which case it should say so, and the number is 450 of 450 per system.
3. The sentence is simply too strong and should carry the `before_intent_write`
   exception.

### How it was resolved

**Reading 2**, by author decision, in the same commit that answers RQ4. The
sentence now scopes itself to executions that wrote an intent, and says where
the counts are:

> Within that scope: every AEP-full and B3 execution in the crashed regime
> **that had written an intent** reached a terminal classification, and the
> main paper's RQ4 subsection gives the counts. **The executions crashed before
> an intent existed are outside that scope rather than failures within it,
> because no record exists for recovery to act on.**

The exception is stated rather than implied, and in a form that cannot be read
as a recovery failure. The counts it points at are §VI-E's: 450 of 450 per arm
at the five crash points where an intent exists, with `before_intent_write`
reported separately.

**Related, and still open, but not a correctness problem.**
`\label{supp:rq4}` at `paper/supplementary.tex:641` is defined and never
referenced. Both places that point at that section name it in words rather than
by `\cref` — and they must: `supplementary.tex` states in its own header that
it cannot `\cref` labels defined in `main.tex`, and
`check_paper_numbers.py::check_cross_document_references` enforces that the two
are separate documents. **The label is therefore unusable by design, not merely
unused.** Deleting it is tidying, not a fix. This session tried a `\cref` to
`sec:eval-rq4` from the supplementary and the build correctly refused it.

---

## 3. `voided/` still renders in Section 9, after the same path was removed from the supplementary

**Status: REOPENED 2026-09-24.** Was CHECKED on 2026-09-23. **The check tested
the wrong half of the sentence.** It established that `voided/` is a real
directory — which is true, and is kept below as the record of what it did settle
— and never tested the word *published*. The archive is not published. The
external audit caught this (`reports/external-audit-2026-09-23.md`, blocker B3
and consistency item 3) and `reports/audit-response-2026-09-23.md` §7 conceded
it. The correct finding is at *§ What the 2026-09-23 closure missed* below.

**Two corrections to the entry's own framing**, both made 2026-09-24:

1. **The section number is stale.** This entry says §VIII throughout. The
   sentence is in `paper/sections/08-threats.tex`, and Artifact Availability and
   Threats to Validity were swapped on 2026-09-23 — the file keeps its name and
   now renders as **Section 9**. The headings below are corrected; quoted text
   from the earlier closure is left as written.
2. **"the published archive" is quoted below as if it were settled.** It is the
   thing at issue.

**No text under `paper/` is changed by this entry, then or now.**

### The two treatments

`paper/sections/08-threats.tex` (renders as Section 9), *The oracle is
independent, not infallible*:

> …the voided run's raw directory (its event log, its ledger and a `README`
> giving the reason) is in the published archive under **`\texttt{voided/}`**,
> so the disagreement can be read rather than taken on trust.

`paper/supplementary.tex`, *RQ4: recovery*, **was** the same path and is no
longer:

> the voided attempt must ship in the external raw archive, **in a directory
> reserved for voided runs**, with this explanation beside it

The supplementary said `\texttt{results/voided/}` until the path-removal pass
on 2026-09-22, which replaced it with prose. Section 9's `\texttt{voided/}`
survived that pass.

### Why it survived, and why that is not obviously wrong

`scripts/check_no_repo_paths.py` fires on a slash preceded by a known
repository directory name. `results/` is in that list and `voided/` is not, so
the supplementary's form was caught and Section 9's was not. **The check is
behaving as written.**

Whether it *should* fire is a different question, and it turns on what the
string denotes. `voided/` here is a directory **inside the evidence archive**,
not inside the Git repository, and Section 8 describes the archive's contents by
name elsewhere. A reader following the pointer needs to know where in the
deposit to look. (This passage read *"the published evidence archive"* when it
was written on 2026-09-23. That assumption is the one now reopened.)

### The question for the audit

1. Is `voided/` an archive location the paper should name, in which case
   Section 9 is right and the supplementary's replacement lost useful
   information?
2. Or should both read as prose, in which case Section 9 needs the same
   treatment the supplementary got?
3. If (1), should `check_no_repo_paths.py` gain an allow-list entry so the
   distinction is enforced rather than accidental?

**No text is changed by this entry.** A prose pass cannot decide what the
deposit's public contract is.

### It is (1), and the deposit says so, 2026-09-23

`voided/` is a real directory in the archive, holding exactly the run Section 9
describes. From the archive's own `MANIFEST.sha256`, 24 entries under a
path segment that is exactly `voided`:

```
voided/README.md
voided/b4b_durable_workflow_at_most_once-before_intent_write-notifications-
       6451e4c7-r1.attempt-1/events.jsonl
voided/…/ground_truth.sqlite3          (the oracle ledger)
voided/…/run-config.json, summary.json, mock-api.{log,yaml}, recovery.stop
voided/…/events-worker-{0,1}-attempt-{1..6}.jsonl
```

That is Section 9's *"its event log, its ledger and a `README` giving the
reason"*, item for item, and it is a **B4b** run at `before_intent_write` — the
cell Section 9's oracle-disagreement passage is about.

**So the path is right and `check_no_repo_paths.py` is right.** `voided/`
denotes a location inside the deposit, not inside the Git repository, which is
why the checker's repository-directory list does not contain it and why it did
not fire. Nothing was missed *on that question*.

**Two follow-ups, neither blocking, both the author's call:**

1. **The supplementary lost information it need not have.** It now reads *"in a
   directory reserved for voided runs"*, where it used to name the path. The
   name is accurate and a reader following the pointer needs it. Restoring it
   would mean the path-removal pass's replacement was too broad in this one
   place.
2. **The distinction is accidental rather than enforced.** `voided/` passes
   because `voided` happens not to be a repository directory name. If a
   repository directory is ever created with that name, Section 9 starts failing
   a check it should never fail. An allow-list of deposit-internal paths would
   make the distinction deliberate.

**That closure said "CHECKED. The claim in Section 9 is accurate."** It is not.
See below.

### What the 2026-09-23 closure missed, 2026-09-24

**The entry was raised about a path and closed about a path.** The sentence makes
two assertions and only one was tested.

`paper/sections/08-threats.tex:223-227`, in full:

> One voided run demonstrates that this oracle can fail: its event log and
> ledger disagreed while sibling and repeated runs agreed. The repository
> retains the aggregate record of that exclusion, and the voided run's raw
> directory (its event log, its ledger and a `README` giving the reason) **is in
> the published archive** under `\texttt{voided/}`, so the disagreement can be
> read rather than taken on trust.

| assertion | tested on 2026-09-23? | verdict |
|---|---|---|
| there is a directory named `voided/` holding that run | **yes** | **true**, 24 manifest entries, item for item |
| the archive containing it **is published** | **no** | **false at submission** |

**The evidence that it is false.** `paper/main.tex:145` is
`\archivedoistate{RESERVED}`. A reserved Zenodo DOI is minted and does not
resolve until the record is published. The manuscript says so itself, two
sections earlier — rendered, Section 8:

> "with the Zenodo record reserved under DOI 10.5281/zenodo.22766567; the
> identifier is fixed and begins resolving when the record is published."

So the paper states in Section 8 that the archive is not yet published and
asserts in Section 9 that a run is in the published archive. That is the
external audit's consistency item 3, and it is a contradiction internal to the
manuscript, not a judgement call about wording.

**Why the earlier closure reached the wrong place.** It read the deposit — the
local archive tree and its `MANIFEST.sha256` — and found the directory. The
deposit *exists*; it is built, verified, and its manifests check file by file
(`scripts/verify_raw_archive.py`). None of that makes it *published*. "Published"
is a property of the Zenodo record, not of the bytes on disk, and the only thing
that establishes it is a resolving DOI. The closure checked the bytes.

**What would close this entry.** Exactly two things, and they are mutually
exclusive in practice:

1. **Publish the Zenodo deposit.** `\archivedoistate` moves from `RESERVED` to
   the published state, the DOI resolves, and the Section 9 sentence becomes true
   **with no text change at all**. Procedure is `docs/29-archive-deposit.md` —
   one record, six files, manual web upload — and it is already this project's
   named submission blocker (`reports/audit-pack.md` §7.4). This is the
   preferred close: it makes the sentence true rather than weaker, and it fixes
   the audit's blocker B3 in the same act.
2. **Reword so the sentence does not assert publication.** Two forms would do
   it: drop *published* (the archive is named and described in Section 8
   regardless), or make the availability conditional on the deposit in the same
   way `\archiveavail` already is. This is the fallback if the paper is
   submitted before the deposit is live, and it is strictly worse, because the
   sentence exists to let a reviewer read the disagreement rather than take it
   on trust — and a reviewer still cannot.

**Neither is done, and nothing under `paper/` was touched.** The choice is the
author's, and it is really a scheduling question: if the deposit is published
before submission, option 1 costs nothing.

**One thing this reopening does not disturb.** Everything the 2026-09-23 closure
established about the *path* stands: `voided/` is a real deposit directory, it
holds exactly the run Section 9 describes, it is not a repository path, and
`check_no_repo_paths.py` behaved correctly in not firing. Only the word
*published* is at issue.

**Status: REOPENED.**

---

## 4. The supplementary points a reader at "the supplementary material", and two of its sections answer the same question

**Status: half RESOLVED, half open, 2026-09-23.** The self-reference was a
wording error and is fixed. Whether the two sections should merge is structural
and stays open.

### The self-reference

`paper/supplementary.tex`, closing `\label{supp:provable-detail}`:

> Closing it is possible and we did not do it. **The supplementary material
> gives the probe detail and prices the third barrier** that would split the two
> cases.

That sentence is itself in the supplementary material. The comment above the
section records why:

> Moved out of the evaluation section in WS-9's length pass. Section VI keeps
> the result […] and this carries the reasoning and the third-barrier trade.

When the text sat in §VI the pointer was correct. It moved, and the pointer
moved with it, so it now names the document it is in.

### The section it points at is a sibling, 500 lines earlier

| label | heading |
|---|---|
| `supp:provable` | Why the provably-empty cell is not resolved, **and what closing it would cost** |
| `supp:provable-detail` | Why the provably-empty cell is not resolved |

Both answer the same question, and the material overlaps closely. Each states
that a recovery process reading the store afterwards sees an authorized,
unresolved intent, that this is what it would see had the worker died during
transmission, and that the two histories are identical in everything durable.
`supp:provable` then prices the third barrier at `\ThirdBarrierStepPct{}\%`;
`supp:provable-detail` says that the supplementary prices it.

Both passages were re-punctuated identically by this pass, so the duplication
is no more and no less visible than it was.

### The question for the audit

1. Should `supp:provable-detail` be merged into `supp:provable`? They answer
   one question and the later one adds the framing sentence and little else.
2. If both stay, the self-reference needs different words: it should name the
   sibling section. A `\cref` is available here, unlike the case in entry 2
   above, because both labels are defined in `supplementary.tex` and the
   restriction is only on reaching labels defined in `main.tex`.
3. Is any of this load-bearing for §VI's pointer? §VI points at "the
   supplementary material" for the probe detail, and a reader following that
   pointer arrives at two sections with nearly the same heading.

### How it was resolved, in part

**The self-reference is fixed.** It was a wording error with one correct
answer: the sentence has to name the sibling section, and both labels are
defined in `supplementary.tex`, so `\Cref` reaches it. The header's rule is
about labels defined in `main.tex` only, and `cleveref` is already loaded —
`\Cref{tab:deployment}` was in the file before this.

> **Before:** Closing it is possible and we did not do it. **The supplementary
> material** gives the probe detail and prices the third barrier…
>
> **After:** Closing it is possible and we did not do it.
> **`\Cref{supp:provable}`** gives the probe detail and prices the third
> barrier…

The only invariant that moved is the one intended to: `\cref` targets 1 → 2,
adding `supp:provable`. Every label, citation, number, `\texttt` and `\emph`
content is unchanged.

**The structural question stays open, and it has a home.** Whether
`supp:provable-detail` should merge into `supp:provable` — two sections
answering the same question, one pricing the third barrier and the other now
pointing at it — is not a wording call. Option 1 above is still for the author.
Option 3 (does §VI's pointer land a reader on two near-identically-headed
sections?) is unaffected by the `\Cref` fix.

**Author decision, 2026-09-23: this belongs with the length work, after the
supervisor's review, and is not to be taken before then.** Merging two sections
changes what the supplementary contains, and the length pass is where that
trade is decided with word counts in front of it rather than in isolation. The
supplementary has no page limit, so nothing forces the question early.

**Carry this into the length pass as a named item**, alongside the 569 words of
§VII and §VIII cut candidates from phase 49 and the 24-page main body.

---

## 5. Table 7's rows now pool different numbers of crash points, by family

**Status: open.** Raised 2026-09-24 when phase 53's exclusion was applied.

### What changed

The five baselines' `after_barrier_before_dispatch` cells are excluded from
every pooled baseline rate, because the harness delivered that kill inside the
socket wait (`reports/audit-response-2026-09-23.md` §1). AEP-full and B3 keep
the cell: their kill there was always immediate.

So `\cref{tab:outcomes}` now pools, per row:

| systems | crash points pooled | why |
|---|---|---|
| AEP-full, B3 | **6** | nothing excluded |
| B4, B4b | **5** | `after_barrier_before_dispatch` excluded |
| B0, B1, B2 | **4** | that, and `after_intent_before_barrier` does not exist for them |

This is stated in §6.1 and in the table's own caption, so it is disclosed
rather than hidden. It is recorded here because disclosure is not the same as
being a good idea.

### The question for the audit

A reviewer comparing an AEP-full row against a B0 row is comparing a rate over
six crash points against a rate over four. The exclusion was made to remove one
non-comparability and it introduces another, smaller one.

Three options, none of which this pass can choose between:

1. **Leave it.** The excluded cell measured a different fault, so including it
   would be worse; the caption says which rows pool what.
2. **Exclude `after_barrier_before_dispatch` from AEP-full and B3 as well**, so
   every row pools the same crash points it can. This discards two cells of
   correct data to buy symmetry, and it would lower AEP-full's denominator
   without changing its numerator, which is zero.
3. **Report the table per crash point** rather than pooled, which is what the
   supplementary's decomposition already does for AEP-full.

**The direction of every comparison is unaffected**: AEP-full and B3 record
zero undetected duplicates and zero lost effects under all three options.

### Related, and deliberately not merged with this entry

The re-collected cell (`\cref{sec:eval-abd}`) is a **separate session** and is
not pooled with the matrix under any of the three options. Whether a future
pass should pool it with a re-collected matrix is a different question and
needs a different pre-registration.

---

## 6. Phase 54 is pre-registered and not collected; §6.3.1's prediction is waiting on it

**Status: open, and it is a pointer rather than a doubt.** Raised 2026-09-24
when blocker B1 was rescoped.

### What the manuscript now says

`paper/sections/06-evaluation.tex`, at the end of `sec:eval-detection`:

> …the model predicts that under a fault which destroys the record the barrier
> is what separates them, and that detection without it fails. We have not
> tested that prediction. It is falsifiable, the cell that would decide it is
> pre-registered, and it has not been collected.

That is the only place the paper makes a prediction about a cell it has not
run, and it is deliberate: the author chose option (ii) of
`reports/b1-plan-2026-09-24.md`, rescope first and collect afterwards, with
option (iii)'s addition that the prediction is stated as falsifiable.

### What this entry exists to catch

**The pre-registration is `prompts/phase-54-record-loss-restart-2026-09-24.md`.**
When that cell is collected, four things in the manuscript become stale at once
and must be revisited together:

1. **The sentence above**, which says the cell has not been collected. If the
   result arrives and this is not updated, the paper states something false
   about its own evidence.
2. **The scope marker itself.** Eight locations now carry *for
   record-preserving faults*, *under these faults*, or *under the faults
   measured here*. A confirming result narrows none of them; a refuting result
   (AEP-full also losing effects) narrows all of them further.
3. **C4's wording**, now *"A decomposition of the mechanism, by ablation, and
   the boundary at which it stops."* If the cell measures the boundary, the
   phrase *"the boundary at which it stops"* becomes an understatement and C4
   can claim the two-sided decomposition the plan's §5 describes.
4. **§9.2**, which now says the ablation says which half delivers which *under
   the faults it covers*.

### The outcome that would need the most care

`reports/b1-plan-2026-09-24.md` §3.4 records that **both arms recording zero is
an instrument failure, not evidence** — most likely the `freeze_bdev` sync that
WS-4 had to defeat with `--noflush --nolockfs`. The pre-registration names that
condition in advance. **A null from this cell must not be read into the
manuscript as support for the unscoped claim**, which is the reading the
rescope exists to prevent.

### No text is changed by this entry

It records where to look, not what to conclude.

---

## 7. Declared ambiguity has no crash-free control outside `AUTHORITATIVE_READBACK`

**Status: OPEN.** Raised 2026-09-25 during the B1 fix, which disclosed the
provider fault surface in §6.1 and re-attributed §6.6's duplicates to it.

### What the B1 sweep settled, and by what evidence

Every outcome the manuscript attributes to a crash was checked against the
crash-free cells, which carry the same injected faults and no worker kill.

| claim | crashed | crash-free | reading |
|---|---|---|---|
| baselines' undetected duplicates, pooled | 0.74–0.78 | 0.1333–0.1800 | holds; the background is a floor under it, and §6.1 now says so |
| B4b loses the effect where B4 duplicates | 0.4267–0.4600 per class | 0.1467 | holds, Fisher $p \le 4.2\times10^{-9}$ per class. The crashed number contains the background but is not produced by it |
| AEP-full and B3 record zero duplicates and zero lost effects | 0/450 each | 0/150 each | unaffected; zero in both |
| prevention, `redis-kill-preack` | AEP-full 10/30 applied, B3 28/30 | not applicable | unaffected. Every execution in that cell applied 0 or 1 effect, so no timeout retry is inside those counts |
| declared ambiguity, AEP-full and B3 | 193/540 and 195/540 | **0/150 each** | holds on `AUTHORITATIVE_READBACK`; see below |

### The gap

The crash-free cells are `payments` only, which is
`AUTHORITATIVE_READBACK`. On that class a read-back settles a timed-out call,
so AEP-full declares no ambiguity there without a crash, and the crashed
ambiguity rate is the crash's.

**On `POSITIVE_ONLY_READBACK` and `NO_READBACK` there is no crash-free cell,
and on those classes a read-back cannot settle a timed-out call.** A provider
timeout with no crash should therefore produce a declared ambiguity on its own.
No collected cell separates that from the crash-driven ambiguity, and §6.2's
residual-by-capability result is the place it would matter: the residual is
attributed to endpoint capability, and part of it may be the timeout rate
rather than the crash.

### What would close it

A crash-free (`p0`) cell for AEP-full and B3 on `notifications` and
`ledger_postings`, three runs each. It is the same regime, the same systems and
two more endpoints, and it is machine time only. Until it exists, §6.2's
residual claim should be read as *ambiguity under crashes and timeouts
together*, which is what was collected.

### Not changed by this entry

No manuscript text. The B1 fix left §6.2's residual subsection alone because
the direction of the result does not depend on the split, and inventing a
qualifier for a number nobody has measured would be worse than recording the
gap here.

---

## 8. Figure 2 and supplementary Figure 1 predate the exclusion (audit 2, F1)

**Status: OPEN, and out of the B1 fix's scope by instruction.** Raised
2026-09-25.

Both figures were last regenerated in `c2fffa6` (2026-08-12); the
`after_barrier_before_dispatch` exclusion is from `18f44ac` (2026-09-24).

- **Supplementary Figure 1** plots B0 0.7978, B1 0.8156, B2 0.7933, B4 0.5593,
  which are the pooled rates **with** the excluded cell. Table 7 reports
  0.7417–0.7833 and 0.4467–0.5067 without it. Three sentences in §6.2 are false
  against the figure as plotted: *"the same executions"*, *"The figure adds no
  number this section does not state"*, and *"the three systems on the right
  have an empty left bar"*, the rightmost being B4 at ≈0.56.
- **Figure 2** still plots the excluded cell as its first group, at 0.92–0.97,
  inside the section that says the cell is excluded from every pooled rate.

The B1 fix corrected Figure 2's **caption**, which claimed that *"any
interruption after the request is on the wire is enough"* while the figure's own
`before_intent_write` bars show 0.122–0.244 from an interruption before
anything was sent. That sentence was the B1 misreading in a caption. The
staleness itself is untouched: the figures are generated by
`experiments/analyze.py write_figures()` from tracked CSVs, so regenerating them
is re-analysis and not collection, and the exclusion rule has to be taught to
the generator first.

---

## 9. Three prose sites still spell the provider delay as "two-second"

**Status: OPEN, minor.** Raised 2026-09-25 during the B1 fix.

§6.1 now states the timeout and 5xx rates from
`\ProviderTimeoutPct`, `\ProviderErrorPct` and `\ProviderDuplicatePct`, all
generated from `experiments/run_matrix.py`'s `FAULTS`. The constant delay in
the same dict is still written as prose in three places
(`06-evaluation.tex`, `08-threats.tex`, `supplementary.tex`, each *"a
two-second call"*). It is correct today and it is the one part of the fault
surface that can drift from its setting without a gate noticing, which is the
reason `\BootstrapResamples` is generated. A fourth macro and three word
substitutions would close it.
