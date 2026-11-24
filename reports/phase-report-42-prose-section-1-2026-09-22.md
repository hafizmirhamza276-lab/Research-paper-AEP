# Phase 42 — §VI-A's regime list, a prose style guide, and §I rewritten

**No live calls.** Three commits, split by concern: the factual fix to §VI-A,
the style guide and its metrics script, and the §I rewrite. **Stopped after §I
for review.**

| | |
|---|---|
| §VI-A | now enumerates all five fault regimes, each pointing at where it is reported |
| style guide | `docs/37-prose-style.md` |
| metrics | `scripts/prose_metrics.py`, non-gating |
| baseline | 243 em dashes over 31.5 page-equivalents, **7.71 per page** |
| §I after | **0 em dashes**, mean sentence length 24.0 → 19.3, `\emph` 8 → 1 |
| invariants | **held** — macros, refs, labels, cites, numbers and provenance comments all identical |
| spelling convention | **British `-ise`** |
| pages | main **24**, main-anon **24**, supplementary **7**, supplementary-anon **7** |

---

## 1. §VI-A — the regime list

`paper/sections/06-evaluation.tex:25–37`. C3 was not touched.

The list had three entries under a sentence reading *"we report each separately
because they are different experiments:"*. Two of the five regimes the body
reports were missing. Added with the descriptions the body already gives them,
and every entry now names the section that reports it.

```diff
 \emph{regime} is a named fault condition --- not a matrix dimension --- and we
-report each separately because they are different experiments:
+report each separately because they are different experiments. Five are
+reported, and each is named here with the section that reports it:

 \begin{itemize}
 \item \textbf{crashed}: every execution is killed at the cell's crash point.
-      This is the regime RQ1 is about.
+      This is the regime RQ1 is about (\cref{sec:eval-rq1}), and it is also
+      the regime of the detection ablation (\cref{sec:eval-detection}).
 \item \textbf{crash-free} (\texttt{p0}): nothing is injected. The only regime
-      RQ3 may use.
+      RQ3 may use (\cref{sec:eval-rq3}).
 \item \textbf{\texttt{redis-kill-preack}}: no worker crash; Redis is hard-killed
       with \texttt{docker kill -s KILL} at the instruction boundary between the
       intent CAS and the barrier acknowledgement, then restarted and verified.
-      This is RQ2's ablation.
+      This is RQ2's ablation (\cref{sec:eval-prevention}).
+\item \textbf{\texttt{redis-kill-inflight}}: the same fault armed at the last
+      instruction before transmission and delivered afterwards, so that it
+      lands once both arms have dispatched. It is the control for
+      \texttt{redis-kill-preack}: where the fault falls on the far side of the
+      branch point, the arms should tie, and they do
+      (\cref{sec:eval-prevention}, under \emph{Where the fault lands after the
+      branch point}).
+\item \textbf{\texttt{write-loss-preack}}: no worker crash and no Redis kill;
+      the block device under Redis's append-only file stops accepting writes
+      while reporting success, armed at the intent checkpoint. This is the
+      fault the durability claim is defined against, and the regime that
+      refuted our prediction (\cref{sec:eval-writeloss-cell}).
 \end{itemize}
+
+A sixth regime, a $30\%$ crash probability, was collected and is in the
+artifact; no table here quotes its rates, so it is not one of the five.
```

**No `\label` was added for the in-flight paragraph.** `main.tex:65–69` records
that with `secnumdepth` at 3, a label on an unnumbered `\paragraph` resolves
through the enclosing subsubsection's counter, so it would render the same
number as `sec:eval-prevention`. The entry cites that label and names the
paragraph heading instead.

**The sixth regime is mentioned** because C3 parenthesises it. Without that
sentence the two lists would disagree again, in the other direction.

`main-anon` went 23 → 24 pages. `main` stayed at 24. All four builds clean, gate
green.

---

## 2. Baseline metrics, whole manuscript

`python scripts/prose_metrics.py`, 2026-09-22, before any rewriting. Also
recorded in `docs/37` §13 so later runs have something to compare against.

| file | words | sent | pg | em | em/pg | en | len | sd | min | max | corr | flag | sign | hedge | we | emph | bold | para | punch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `01-introduction` | 1056 | 44 | 1.41 | 11 | 7.81 | 0 | 24.0 | 16.2 | 3 | 61 | 5 | 0 | 0 | 6 | 5 | 8 | 11 | 14 | 0 |
| `02-motivating` | 731 | 40 | 0.97 | 19 | **19.49** | 1 | 18.3 | 12.2 | 3 | 48 | 2 | 1 | 0 | 3 | 2 | 14 | 9 | 12 | 4 |
| `03-model` | 638 | 36 | 0.85 | 4 | 4.70 | 0 | 17.7 | 10.7 | 3 | 47 | 9 | 0 | 1 | 3 | 2 | 15 | 12 | 14 | 1 |
| `04-protocol` | 2291 | 92 | 3.05 | 28 | 9.17 | 1 | 24.9 | 14.0 | 5 | 57 | 16 | 5 | 1 | 5 | 1 | 22 | 7 | 26 | 0 |
| `05-implementation` | 440 | 13 | 0.59 | 4 | 6.82 | 0 | **33.8** | 17.3 | 13 | 74 | 3 | 1 | 0 | 0 | 1 | 2 | 0 | 5 | 0 |
| `06-evaluation` | 6389 | 255 | 8.52 | 68 | 7.98 | 7 | 25.1 | 13.3 | 4 | 83 | **43** | **10** | **5** | 7 | 34 | **46** | **25** | 70 | 5 |
| `07-related` | 3204 | 116 | 4.27 | 28 | 6.55 | 2 | 27.6 | 14.3 | 5 | 71 | 18 | 3 | 0 | 13 | 5 | 19 | 3 | 26 | 0 |
| `08-threats` | 3234 | 118 | 4.31 | 25 | 5.80 | 2 | 27.4 | 14.2 | 5 | 68 | **33** | 4 | 1 | 2 | 23 | 22 | 4 | 35 | 2 |
| `09-artifact` | 816 | 25 | 1.09 | 8 | 7.35 | 0 | **32.6** | 14.0 | 8 | 67 | 3 | 2 | 2 | 0 | 0 | 5 | 0 | 8 | 0 |
| `main.tex` | 688 | 20 | 0.92 | 6 | 6.54 | 1 | **34.4** | 18.5 | 6 | 85 | 6 | 0 | 0 | 0 | 4 | 6 | 0 | 7 | 0 |
| `supplementary` | 4165 | 151 | 5.55 | 42 | 7.56 | 2 | 27.6 | 14.3 | 4 | 84 | **40** | 7 | 3 | 6 | 31 | 26 | 21 | 46 | 2 |
| **TOTAL** | **23 652** | **910** | **31.5** | **243** | **7.71** | 16 | — | — | — | — | **178** | **33** | **13** | **45** | **108** | **185** | **92** | 263 | 14 |

Corrective constructions by kind, across the manuscript: `rather than` **103**,
`X, not Y` **54**, `is not A, it is B` **10**, `not X but Y` **8**,
`instead of` **3**.

**What stands out.** `02-motivating` is the worst section for em dashes by a
factor of two and is short enough to fix quickly. `06-evaluation` and
`08-threats` carry two-fifths of the corrective constructions between them.
`05-implementation`, `09-artifact` and `main.tex` have the longest mean
sentences and almost no short ones.

---

## 3. §I — before and after

| metric | before | after | note |
|---|---|---|---|
| words | 1056 | 1062 | +6 |
| sentences | 44 | 55 | long sentences split |
| **em dashes** | **11** | **0** | target was about 1 per 1.41 pages |
| em dashes per page | 7.81 | **0.0** | |
| mean sentence length | 24.0 | **19.3** | |
| sd of sentence length | 16.2 | 9.9 | see below |
| longest sentence | 61 | 48 | |
| shortest | 3 | 3 | |
| corrective constructions | 5 | 5 | all five are substantive; see below |
| flagged vocabulary | 0 | 0 | §I was already clean |
| signposts | 0 | 0 | |
| hedges | 6 | 6 | |
| `\emph` | 8 | **1** | |
| `\textbf` | 11 | 11 | all are run-in headings or defined-term first uses |
| paragraph-final short sentences | 0 | 0 | |

**The standard deviation fell, and that is worth stating rather than
presenting as an improvement.** `docs/37` §5 asks for varied sentence length.
Splitting the two longest sentences removed the outliers that were producing
most of the spread, so the distribution is tighter even though the writing is
more varied to read. Mean 19.3 is slightly below the "low twenties" the guide
suggests. Both are arguments for reading the section rather than the table.

**The five corrective constructions were kept deliberately.** Each is the
substance of a claim, which is the test `docs/37` §2 sets:

| line | construction | why it stays |
|---|---|---|
| 57 | *"declared and bounded rather than silent and unbounded"* | the paper's central distinction |
| 71 | *"rather than as a pursuit of exactly-once"* | C1's framing claim |
| 75 | *"declared rather than assumed away"* | C1's claim about residual windows |
| 78 | *"a checked precondition of dispatch authority, not a matter of call ordering"* | C2's claim |
| 80–83 | *"It is not a cryptographic capability, and it is not a boundary against…"* | C2's scope disclaimer, which must be stated |

### 3.1 Invariants, checked mechanically

Compared against `HEAD:paper/sections/01-introduction.tex`:

| | count | result |
|---|---|---|
| macros (`\undetdup{}`, `\lostfx{}`, `\declamb{}`) | 3 | **identical** |
| `\cref` targets | 9 | **identical** |
| `\label` | 2 | **identical** |
| `\cite` keys | 3 | **identical** |
| numbers and maths | 17 | **identical** |
| provenance comment lines | 12 | **identical, verbatim and in order** |

`check_paper_numbers.py`: **43 passed, 0 failed**. All four builds clean,
supplementaries first. Gate green.

---

## 4. Sentences where meaning might have shifted — for review

Six. Each is a place where I judged the rewrite to preserve the claim; each is
listed because a reasonable reader might disagree.

### 4.1 C4 — "It is two"

> **Before:** The write-ahead pattern is normally presented as one mechanism
> delivering one guarantee. It is two.
>
> **After:** The write-ahead pattern is normally presented as one mechanism
> delivering one guarantee, and we find that it is two.

`docs/37` §3 names the two-word fragment as the pattern to remove. Adding *"we
find"* converts an assertion into a reported finding, which §8 wants, but it is
a slightly weaker statement than the original. **The risk is understatement, not
overstatement.** Revert to a full-sentence assertion — *"and it is two"* — if
you would rather keep the force.

### 4.2 The trilemma's first item

> **Before:** This is what a naive retry produces, and, as we show in
> \cref{sec:evaluation}, it is also what a lease, a fenced compare-and-swap,
> and a durable event-sourced history each fail to prevent, because none of
> them is a record written \emph{before} the call.
>
> **After:** A naive retry produces this outcome. So do a lease, a fenced
> compare-and-swap and a durable event-sourced history, as
> \cref{sec:evaluation} shows, because none of them writes a record before the
> call.

Two changes to check. *"fail to prevent"* became *"So do"*, which says the three
designs **produce** the outcome rather than **fail to prevent** it — very close,
but not word-for-word identical in emphasis. And *"none of them is a record
written before the call"* became *"none of them writes a record before the
call"*; the original described the mechanisms as not *being* such a record,
which is the more precise statement about a lease.

### 4.3 The lost-effect item's second clause

> **Before:** It is quieter than a duplicate and it is not better; a refund
> that the ledger says did not happen is a reconciliation problem that surfaces
> weeks later, in the accounts.
>
> **After:** It is quieter than a duplicate and no less serious: a refund that
> the ledger says did not happen becomes a reconciliation problem that surfaces
> in the accounts weeks later.

*"it is not better"* became *"no less serious"*. These are equivalent in
ordinary use, but *"not better"* is a comparison to the duplicate and *"no less
serious"* asserts a severity. If the distinction matters, revert.

### 4.4 The impossibility paragraph's opening

> **Before:** The impossibility is not incidental.
>
> **After:** This impossibility is structural.

*"not incidental"* and *"structural"* are not synonyms. *Structural* is a
stronger positive claim than the original negation, and it is mine rather than
the paper's. This is the change I am least sure of.

### 4.5 AEP's answer

> **Before:** What is available is a choice about where the uncertainty is
> allowed to surface. AEP's answer is: in a durable state, visible to an
> operator, never in the accounts.
>
> **After:** What a designer can choose is where the uncertainty is allowed to
> surface. AEP places it in a durable state that an operator can see, and keeps
> it out of the accounts.

*"never in the accounts"* became *"keeps it out of the accounts"*. The original
*never* is absolute; the rewrite is a statement about what the protocol does.
Given the paper elsewhere concedes a residual, the weaker form may be more
accurate, but it is a change and it is yours to decide.

### 4.6 Paragraph 2's closing clause

> **Before:** and --- the property that does the real damage --- many of them
> cannot be asked afterwards whether a mutation was applied.
>
> **After:** Many of them also cannot be asked afterwards whether a mutation
> was applied, and that third gap is the one that does the real damage.

The phrase *"does the real damage"* is preserved verbatim, but it now attributes
the damage to *"that third gap"* rather than sitting inside the sentence as an
aside. Same claim, slightly more explicit about which property is meant, which
I believe is what the original intended.

### 4.7 Two changes I judged safe and am noting anyway

* *"Temporal's own documentation"* → *"Temporal's documentation"*. `own`
  carried a faint "even they concede" tone; the citation makes the point.
* *"The first two are silent. The third is not."* → *"The first two outcomes are
  silent and the third is not."* Two fragments joined; no claim moves.

---

## 5. Cut candidates for §I — **none applied**

Listed for your decision. Word counts are of the material itself.

| # | candidate | words | why it is a candidate | argument against cutting |
|---|---|---|---|---|
| 1 | The Temporal quotation, *"You should always make your business logic Activities idempotent… executed more than once"* | 30 | It is quoted again in §VII's treatment of durable-execution engines. §I could cite `temporal-activity-definition` and state the precondition in half a line | It is the single most concrete piece of evidence that the precondition is stated by a vendor rather than inferred by us, and §I is where a reviewer decides whether the problem is real |
| 2 | The three examples of other callers, *"A workflow engine, a retrying batch job and a human operator with a script are all in the same position"* | 19 | The general claim in the preceding sentence already carries the scope. §II's opening makes the same point about the scripted caller | Without it the paper reads as being about agents, which is exactly the framing risk the Option A retitle exists to manage |
| 3 | C3's parenthesis about the sixth regime, `p30` | 27 | It is a disclosure about a collection no table quotes, and §VI-A now carries the same sentence | Removing it from §I would leave a reader who counts regimes in the artifact wondering why there are six |
| 4 | C2's final two sentences, the trusted-code scope disclaimer | 33 | §IV states the same limitation where the guard is specified, and §VIII revisits it | A capability-sounding mechanism described without its limit in §I is the kind of overclaim a reviewer marks on first reading. This is the weakest cut candidate of the five |
| 5 | The last sentence of *What this paper does not claim*, pointing at `\cref{sec:model}` and `\cref{sec:threats}` | 26 | Pure signposting, and `docs/37` §10 allows one per section | It is the only signpost in §I, and it tells a reader where the reasons are. Cheap at 26 words |
| 6 | C4's closing clause, *"and an operator can buy the first without the second (the supplementary material…)"* | 21 | The deployment consequence is developed at length in the supplementary section it names | It is the practical payoff of the contribution, and C4 without it is a claim about mechanism with no consequence attached |

**Total if all six were applied: 156 words**, about a fifth of a page. My view
is that 1 and 5 are the only ones worth considering, and that 4 should not be
cut under any circumstances.

---

## 6. Spelling convention

**British `-ise`**, and near-uniform already: `normalisation`, `serialisation`,
`anonymisation`, `formalise`, `generalisation`, `organised`, `analysed`,
`behaviour` (8), `favour` (2). `analysis` is unaffected by the convention.

Three genuine American spellings exist, all in §VII, each next to a cited
system's own terminology: `realized` (l. 140), `formalizes` (l. 226),
`characterizes` (l. 230). They are recorded in `docs/37` §11 for the §VII pass
to settle.

**Two that are not exceptions and must not be changed:** `analyze.py` is a
filename, and `authorization` is this protocol's term for the Redis-visible
record the dispatch guard is consumed to write. Both track identifiers in the
code.

---

## 7. Verification

| | |
|---|---|
| live calls | **none** |
| sections rewritten | **§I only** — stopped for review |
| `check_paper_numbers.py` | **43 passed, 0 failed** |
| builds, supplementaries first | supplementary **7**, supplementary-anon **7**, main **24**, main-anon **24** |
| gate | `prove_anonymous_gate.sh` green |
| suite | full |
| cut candidates applied | **none** |
