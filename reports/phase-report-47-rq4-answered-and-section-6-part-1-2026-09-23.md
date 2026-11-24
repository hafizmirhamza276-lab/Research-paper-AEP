# Phase 47 — RQ4 answered as counts, and §VI part 1 rewritten

**No live calls.** `origin/main == HEAD` at `ab61e89` confirmed before any edit.
Four commits. **Stopped after §VI part 1.**

| | |
|---|---|
| RQ4 | **answered in §VI-E, as counts, no rate and no interval** |
| macros added | **9**, all generated, none hardcoded |
| `claims-to-review` entry 2 | **RESOLVED** |
| §VI part 1 | em dashes **47 → 3** (7.82 → **0.50** per page) |
| pages | main **24**, main-anon **24**, supplementary **7 / 7** |
| suite | **2593 passed, 34 skipped** |

---

## 1. The new §VI-E, in full

```latex
\subsection{RQ4 --- recovery}
\label{sec:eval-rq4}

Recovery is reported as counts. In the crashed regime, every interrupted
execution that had written an intent was resolved to a terminal
classification: \RecoveryAepResolved{} of \RecoveryAepAttempted{} for
AEP-full and \RecoveryBthreeResolved{} of \RecoveryBthreeAttempted{} for B3,
over \RecoveryCrashPoints{} crash points and \RecoveryClasses{} endpoint
capabilities. The classes those executions resolved to are the ones
\cref{tab:outcomes} already reports.

The sixth crash point is counted separately, and it is not a recovery
failure. At \path{before_intent_write} the worker dies before any intent
exists, so there is no record for recovery to act on
(\cref{tab:crashpoints}). The \RecoveryAepNoRecord{} executions there for
AEP-full and the \RecoveryBthreeNoRecord{} for B3 resolve to no terminal
classification at all. Pooling them with the rest would produce a figure that
reads as a failure rate for a component that was never given anything to do.

We report no rate and no interval for this. The runs behind each cell
resolved identically, so a bootstrap interval would be degenerate and would
claim a precision they cannot support; the counts are the stronger statement.
Absolute recovery latency is not reported either. Under the timing gate of
\cref{sec:eval-setup}, \RunsWithUsableTiming{} of \RunsCollected{} runs
contribute a duration, which leaves too few gated crashed runs for a
distribution, and \cref{sec:threats} records that as a cost of the gate. The
baselines declare no recovery service and are excluded from these counts
rather than scored; the supplementary material, under \emph{RQ4: recovery},
gives that argument in full and carries the one reconciliation disagreement
in \RunsCollected{} runs and what became of it.
```

Rendered, that reads *450 of 450 for AEP-full and 450 of 450 for B3, over 5
crash points and 3 endpoint capabilities*, with *90* and *90* at
`before_intent_write`, and *176 of 432* runs contributing a duration.

**Nine lines became twenty-eight**, which puts it between RQ3 (69 lines) and
the shortest RQ subsections. No number is hardcoded.

### Two drafting choices worth recording

**`NO_RECORD` is not named.** The manuscript never uses that identifier;
`tab:crashpoints` describes the same crash point as *"no record, no effect"*.
The subsection points at `tab:crashpoints` and uses that wording rather than
importing a new `\textsc{}` term from the analysis code.

**The supplementary is referenced in words, not by `\cref`.** See §3 below.

---

## 2. The nine macros, with provenance

Added to `scripts/paper_tables.py`; `paper/generated/numbers.tex` regenerated.
Every one reads `analysis/per-cell-metrics.csv` or `analysis/coverage.json`,
which the generator already loads — **no new input file**, because
`recovery_success_rate` is already one of the six metrics in
`per-cell-metrics.csv` and the existing `totals()` helper sums it.

| macro | value | provenance comment emitted |
|---|---|---|
| `\RecoveryAepResolved` | 450 | `per-cell-metrics.csv \| system=AEP_FULL regime=(session-3)` / `metric=recovery_success_rate \| sum(successes) over the five crash points at which an intent exists` |
| `\RecoveryAepAttempted` | 450 | same filter / `sum(total) over the same five crash points; the denominator is executions that crashed` |
| `\RecoveryAepNoRecord` | 90 | `… crash_point=before_intent_write` / `sum(total); every one classifies NO_RECORD, which is_terminal excludes, so successes is 0` |
| `\RecoveryBthreeResolved` | 450 | as above, `system=B3_INTENT_NO_BARRIER` |
| `\RecoveryBthreeAttempted` | 450 | as above |
| `\RecoveryBthreeNoRecord` | 90 | as above |
| `\RecoveryCrashPoints` | 5 | `distinct crash_point values excluding before_intent_write` |
| `\RecoveryClasses` | 3 | `distinct response_class values behind the same counts` |
| `\RunsWithUsableTiming` | 176 | `analysis/coverage.json \| runs_with_usable_timing` |

The generator carries a block comment explaining why the counts are emitted and
the rate is not, why `before_intent_write` is split out rather than pooled, and
that the two axis macros exist so the sentence cannot say *"five"* after a
sixth crash point is collected.

### `check_paper_numbers` covers them, without a new check

Two existing gates do it from both sides:

* **`check_generated_tables`** regenerates `numbers.tex` into a temp directory
  and byte-diffs it against what is committed, so all nine values are re-derived
  from the CSVs on every build.
* **`check_macros_are_used`** fails on any macro defined and never used.

**The second one earned its keep immediately.** The first draft wrote *"the
\RecoveryAepNoRecord{} executions per arm"*, using one macro for both systems.
The build refused it:

```
FAIL  every generated number is used in the manuscript
      1 orphaned: RecoveryBthreeNoRecord
```

Naming both counts is the more precise sentence anyway, and that is what
shipped.

---

## 3. The supplementary correction

`paper/supplementary.tex`, *RQ4: recovery*:

> **Before:** Within that scope: every AEP-full and B3 execution in the crashed
> regime reached a terminal classification, and across `\RunsCollected{}` runs
> exactly one recorded a reconciliation disagreement…
>
> **After:** Within that scope: every AEP-full and B3 execution in the crashed
> regime **that had written an intent** reached a terminal classification, and
> the main paper's RQ4 subsection gives the counts. **The executions crashed
> before an intent existed are outside that scope rather than failures within
> it, because no record exists for recovery to act on.** Across
> `\RunsCollected{}` runs exactly one recorded a reconciliation disagreement…

This is **reading 2** of the three that `claims-to-review` entry 2 set out: the
sentence scopes itself, and the exception is stated in a form that cannot be
read as a recovery failure.

**A gate caught my first attempt.** I wrote `\cref{sec:eval-rq4}` and the
supplementary build failed:

```
LaTeX Warning: Reference `sec:eval-rq4' on page 1 undefined on input line 656.
```

`supplementary.tex` states in its own header that it cannot `\cref` labels
defined in `main.tex`, and
`check_paper_numbers.py::check_cross_document_references` enforces it. The
reference is now in words.

---

## 4. `claims-to-review.md`

**Entry 2 → RESOLVED**, with the wording and the reasoning recorded.

**One observation upgraded and left open.** `\label{supp:rq4}` is not merely
unreferenced — it is **unusable by design**, because the two documents cannot
`\cref` each other at all. Deleting it is tidying rather than a fix. This
session's failed `\cref` attempt is recorded as the demonstration.

**Nothing new was added from the §VI part-1 pass.** Every number, interval,
p-value and scope qualifier in part 1 was left exactly as written, and nothing
in it contradicted §III or the analysis outputs.

---

## 5. §VI part 1 — before and after

Lines 1–545: the RQ list, Setup, all of RQ1, and RQ2 through the end of the
prevention subsubsection.

| metric | before | after |
|---|---|---|
| words | 4505 | 4465 |
| sentences | 182 | 191 |
| **em dashes** | **47** | **3** |
| em dashes per page | 7.82 | **0.50** |
| mean sentence length | 24.8 | 23.4 |
| sd | 12.8 | 11.6 |
| shortest / longest | 4 / 64 | 4 / 62 |
| corrective constructions | 35 | 34 |
| flagged vocabulary | **7** | **4** |
| signposts | 1 | 1 |
| `\emph` | 34 | 34 |
| `\textbf` | 15 | 15 |

**The three remaining em dashes are the RQ identity lines**, held pending your
decision after part 2: the RQ2 item in the question list (line 8) and the RQ1
and RQ2 subsection headings (lines 87, 299).

**Emphasis was left alone, deliberately.** §VI carries 46 `\emph` and 25
`\textbf` across the whole file, the most in the manuscript, and `docs/37` §7
would cut most of them. Here most mark a defined term or a scope qualifier —
`\emph{undetected}`, `\emph{no effect can possibly exist}`, `\emph{say}`,
`\emph{does}` — and cutting them is a judgement better made once part 2 is
drafted and the section reads whole. Recorded as a deferral, not an oversight.

### Flagged vocabulary: three removed, four kept

| word | line | decision |
|---|---|---|
| *which is the point* | 130 | **removed** — asserted significance, carried no claim |
| *the whole point of this subsection* | 410 | **removed** → *"what this subsection is for"* |
| *precisely that round trip* | 414 | **removed** → *"exactly that round trip"* |
| *genuinely one-sided bound* | 360 | **kept** — distinguishes a one-sided bound from the upper endpoint of a two-sided interval. A statistical qualifier, and the instruction forbids altering scope qualifiers |
| *the honest answer is "I do not know"* | 203 | **kept** — a stated position about what the protocol says |
| *the honest price of the information the endpoint withholds* | 293 | **kept** — the paper's claim about what declared ambiguity costs |
| *rather than silently skipped* | 21 | **kept** — the contrast with *"marked inapplicable and never run"* is the claim |

---

## 6. Meaning-risk list — least sure first

### 6.1 *"load-bearing rather than modest"* — least sure

> **Before:** That is the sharpest form of the argument the paper can make
> \emph{against our model of a durable-execution engine} --- and that
> qualification is load-bearing rather than modest, and the paragraphs above
> are why:
>
> **After:** That is the sharpest form of the argument the paper can make
> \emph{against our model of a durable-execution engine}. **That qualification
> is not modesty**, and the paragraphs above are why:

`docs/37` §6 flags *load-bearing*. *"Not modesty"* keeps the assertion that the
qualification does real work, but it states it by negation where the original
stated it positively. If you want the positive form back, *"that qualification
carries the argument"* would do it without the flagged word.

### 6.2 The B5 ambiguity sentence changed grammatical subject

> **Before:** …(\BfiveAmb{} and \BfivebAmb{} declarations) --- the third corner
> of \cref{sec:trilemma} going unreached by the engine itself and not merely by
> our model of it.
>
> **After:** …(\BfiveAmb{} and \BfivebAmb{} declarations), **so** the third
> corner of \cref{sec:trilemma} **goes** unreached by the engine itself and not
> merely by our model of it.

An appositive became a consequence clause. The claim is the same; *"so"*
asserts that the declarations are the reason, which the original implied.

### 6.3 The pre-registration sentence gained "namely"

> **Before:** …fixed in advance what a rate outside the bound would mean ---
> the protocol behaving unexpectedly, not the mechanism succeeding --- and we
> honour that here…
>
> **After:** …fixed in advance what a rate outside the bound would mean,
> **namely** the protocol behaving unexpectedly **and** not the mechanism
> succeeding, and we honour that here…

*"namely"* makes the apposition explicit, and the *"not the mechanism
succeeding"* correction is preserved intact.

### 6.4 Three appositions became sentences

*"What the controlled fault buys…"* (line 483), *"…is not in what they
\emph{say}…"* (502), and *"The second session is a deterministic replay…"*
(535) each split one em-dashed sentence into two. In each the clause order is
unchanged. Listed because splitting can subtly change what a subordinate clause
attaches to, and these three are the ones worth re-reading.

### 6.5 One restructure for readability

> **Before:** The per-session tables carrying both --- the uncontrolled counts,
> the four session-level kill-latency differences with their intervals, and the
> same analysis for B3 --- are in the supplementary material.
>
> **After:** The supplementary material carries the per-session tables for
> both: the uncontrolled counts, the four session-level kill-latency
> differences with their intervals, and the same analysis for B3.

Active rather than a 30-word subject with an embedded list. Same three items,
same destination.

---

## 7. Cut candidates for part 1 — **none applied**

| # | candidate | words | restates | against cutting |
|---|---|---|---|---|
| 1 | The four bounds on the B5 comparison, from *"Four things bound this…"* to *"…not like-for-like with B4's."* | 210 | the incompleteness and timeout bounds are restated in **§VIII** *B4 is not Temporal* and *B4 is our model of a durable-execution engine* | It is the paragraph that stops a reader treating B4's rates as a product's, immediately after the rates are given. §VIII is 15 pages later |
| 2 | *"The cost of the third corner"* subsubsection | 130 | **§VIII** *Declared ambiguity is not evaluated as an operational outcome* makes the same concession | §VI is where the ambiguity rates are stated, and the cost belongs beside them. §VIII revisits rather than duplicates |
| 3 | The keying-sensitivity paragraph's last two sentences | 62 | nothing | They are the scope limit on the `pos-only` figure; cutting them would leave the number unqualified |
| 4 | *"Why the provably-empty cell is not resolved"* subsubsection | 120 | the supplementary section of the same name has the probe detail | The main text keeps only the result and the reason; the detail is already out |
| 5 | The unit-of-analysis paragraph, *"Treating the executions as independent would give…"* | 95 | nothing | It is the justification for the conservative bound and a reviewer will ask for it |

**Total 617 words**, about four fifths of a page. My view: **none of these
should be cut**, and 1 and 5 least of all — both exist to stop a specific
misreading of a number stated immediately above them. They are listed because
you asked for the list, not because I think part 1 is padded.

---

## 8. Verification

| | |
|---|---|
| live calls | **none** |
| `origin/main == HEAD` before starting | confirmed at `ab61e89` |
| part 2 of §VI | **untouched** |
| spelling | British `-ise`, unchanged |
| `check_paper_numbers.py` | **43 passed, 0 failed** |
| `check_no_repo_paths.py` | **4 builds clean, 0 failed** |
| builds, supplementaries first | **7 / 7 / 24 / 24**, all clean |
| `prove_anonymous_gate.sh` | green |
| full suite | **2593 passed, 34 skipped** |
| cut candidates applied | **none** |
