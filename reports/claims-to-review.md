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

**Status: open.** Raised 2026-09-22 during the §I prose pass, under the author's
ruling that the original absolute be restored rather than softened by a language
edit.

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

**Status: open.** Raised 2026-09-23 during the §VIII prose pass, which changed
no text.

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
