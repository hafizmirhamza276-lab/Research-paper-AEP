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

## 3. `voided/` still renders in §VIII, after the same path was removed from the supplementary

**Status: CHECKED 2026-09-23.** Raised earlier the same day during the §VIII
prose pass. Closed by reading the deposit rather than by an editorial decision:
`voided/` is a directory in the published archive, §VIII names it correctly, and
it is not a repository path. **No text changed.**

### The two treatments

`paper/sections/08-threats.tex`, *The oracle is independent, not infallible*:

> …the voided run's raw directory (its event log, its ledger and a `README`
> giving the reason) is in the published archive under **`\texttt{voided/}`**,
> so the disagreement can be read rather than taken on trust.

`paper/supplementary.tex`, *RQ4: recovery*, **was** the same path and is no
longer:

> the voided attempt must ship in the external raw archive, **in a directory
> reserved for voided runs**, with this explanation beside it

The supplementary said `\texttt{results/voided/}` until the path-removal pass
on 2026-09-22, which replaced it with prose. §VIII's `\texttt{voided/}`
survived that pass.

### Why it survived, and why that is not obviously wrong

`scripts/check_no_repo_paths.py` fires on a slash preceded by a known
repository directory name. `results/` is in that list and `voided/` is not, so
the supplementary's form was caught and §VIII's was not. **The check is
behaving as written.**

Whether it *should* fire is a different question, and it turns on what the
string denotes. `voided/` here is a directory **inside the published evidence
archive**, not inside the Git repository, and §IX describes the archive's
contents by name elsewhere. A reader following the pointer needs to know where
in the deposit to look.

### The question for the audit

1. Is `voided/` an archive location the paper should name, in which case §VIII
   is right and the supplementary's replacement lost useful information?
2. Or should both read as prose, in which case §VIII needs the same treatment
   the supplementary got?
3. If (1), should `check_no_repo_paths.py` gain an allow-list entry so the
   distinction is enforced rather than accidental?

**No text is changed by this entry.** A prose pass cannot decide what the
deposit's public contract is.

### It is (1), and the deposit says so, 2026-09-23

`voided/` is a real directory in the published archive, holding exactly the run
§VIII describes. From the archive's own `MANIFEST.sha256`, 24 entries under a
path segment that is exactly `voided`:

```
voided/README.md
voided/b4b_durable_workflow_at_most_once-before_intent_write-notifications-
       6451e4c7-r1.attempt-1/events.jsonl
voided/…/ground_truth.sqlite3          (the oracle ledger)
voided/…/run-config.json, summary.json, mock-api.{log,yaml}, recovery.stop
voided/…/events-worker-{0,1}-attempt-{1..6}.jsonl
```

That is §VIII's *"its event log, its ledger and a `README` giving the reason"*,
item for item, and it is a **B4b** run at `before_intent_write` — the cell
§VIII's oracle-disagreement passage is about.

**So §VIII is right and `check_no_repo_paths.py` is right.** `voided/` denotes a
location inside the deposit, not inside the Git repository, which is why the
checker's repository-directory list does not contain it and why it did not
fire. Nothing was missed.

**Two follow-ups, neither blocking, both the author's call:**

1. **The supplementary lost information it need not have.** It now reads *"in a
   directory reserved for voided runs"*, where it used to name the path. The
   name is accurate and a reader following the pointer needs it. Restoring it
   would mean the path-removal pass's replacement was too broad in this one
   place.
2. **The distinction is accidental rather than enforced.** `voided/` passes
   because `voided` happens not to be a repository directory name. If a
   repository directory is ever created with that name, §VIII starts failing a
   check it should never fail. An allow-list of deposit-internal paths would
   make the distinction deliberate.

**Status: CHECKED.** The claim in §VIII is accurate and no text changed.

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
