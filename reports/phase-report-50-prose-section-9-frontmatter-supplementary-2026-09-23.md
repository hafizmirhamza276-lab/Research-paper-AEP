# Phase 50 — §IX, the front matter and the supplementary rewritten

**No live calls.** `origin/main == HEAD` at `e091cee` confirmed before any edit.
Five commits, plus this report.

**The prose pass is complete.** Every prose em dash in the manuscript and the
supplementary is gone.

| | |
|---|---|
| §IX | em dashes **8 → 0** |
| `main.tex` front matter | em dashes **6 → 0** |
| supplementary | prose em dashes **38 → 0** (raw 42 → 4) |
| flagged vocabulary | **9 → 1** across the three files |
| pages | main **24**, main-anon **24**, supplementary **7 / 7** |
| suite | **2593 passed, 34 skipped** |

**One failure was real and is fixed:** the abstract edit broke
`tests/test_arxiv_abstract.py`, because the paste-ready abstract in
`paper/arxiv-metadata.md` is generated from `main.tex`. §6 below.

---

## 1. Scope, and what was not touched

| file | prose em dashes | done |
|---|---|---|
| `01-introduction` … `08-threats` | 0 | earlier passes |
| `09-artifact` | **0** | **this session** |
| `main.tex` | **0** | **this session** |
| `supplementary` | **0** | **this session** |

The four `---` that remain in `supplementary.tex` are `tab:related`'s
not-applicable cells at lines 168, 172, 176 and 178. `docs/37` §0 forbids
touching a table, and `prose_metrics.py`'s tabular-grid exclusion (§12a) exists
for exactly these four, which is why the prose count reads 0 and the raw count
reads 4.

Each rewrite is a script under `macro-scratch/` (`rewrite_s9.py`,
`rewrite_main.py`, `rewrite_supp.py`), every edit anchored on a unique exact
string that raises if the count is not 1. That is what made last session's
recovery from the anonymous gate possible, and it is why each file below could
be reverted and re-applied three times while the wording was tuned.

---

## 2. §IX — before and after

| metric | before | after |
|---|---|---|
| words | 825 | 820 |
| sentences | 27 | 30 |
| **em dashes** | **8** | **0** |
| em dashes per page | 7.27 | **0.0** |
| mean sentence length | 30.6 | **27.3** |
| sd | 12.7 | 10.6 |
| shortest / longest | 8 / 56 | 8 / **47** |
| corrective constructions | 3 | **2** |
| flagged vocabulary | 2 | **0** |
| `\emph` | 5 | 5 |
| `\textbf` | 0 | 0 |

**Invariants:** every LaTeX command token, 98 numbers, 5 `\cref` targets, 1
label, 9 `\texttt` contents, 5 `\emph` contents and 24 provenance comment lines
identical to `HEAD`.

§IX describes the deposit, and every figure in it is a property of an archive
rather than of a tracked CSV — which is why `docs/29` and `ARTIFACT.md` are its
sources and not `generated/`. None of them moved.

### Four dashes became parentheses, one became a sentence, three became stops

| site | before | after |
|---|---|---|
| the two manifest digests | `digest --- 87fa2d53… and 54d1ab0f… --- attests` | parentheses; the aside joins two items with "and" |
| the re-analysis counts | `re-analysed --- 114 … none differing --- and` | parentheses; the aside has internal commas |
| the vendor-documentation qualifier | `or --- for vendor documentation --- fetched` | parentheses; it sits inside an "or A, or B, or C" list where a comma-wrap reads as a fourth item |
| the archive total | `18\,494 files) --- 2\,790 run directories and` | *"That is 2 790 run directories and…"*, its own sentence |
| the write-loss probe | `not part of the test suite --- a test that skips` | full stop |

### The re-analysis sentence kept its shape on purpose

A draft split it so the disclosure stood alone:

> The 2026-09-03 archive was additionally re-analysed, with 114 … and none
> differing. *That re-analysis has not been repeated for the extension.*

That ends the paragraph on a short emphasised sentence, which is the punchline
shape `docs/37` §3 names. It was reverted to parentheses, keeping the original
structure. The disclosure is identical either way.

### Two flagged words, and one corrective of three

| word | decision |
|---|---|
| *deliberately \emph{not} a source for any number here* | → *by design*, matching §IV and §VIII |
| *it cannot silently disagree with the code* | → *cannot disagree with the code unnoticed*. Not the defined term *silent failure* |
| *a reader can see what was collected rather than inferring it from the tables* | → *without inferring it*. The reader does not arrive expecting to infer it |
| *build failures rather than warnings* | **kept** — LaTeX's default **is** a warning, so the correction is the point |
| *voided rather than counted* | **kept** — a voided trial looks like a countable one |

---

## 3. `main.tex` front matter — before and after

| metric | before | after |
|---|---|---|
| words | 693 | 687 |
| **em dashes** | **6** | **0** |
| mean sentence length | 34.6 | 34.4 |
| corrective constructions | 6 | **6** |
| `\emph` | 6 | 6 |

**Invariants:** 157 LaTeX command tokens, 34 numbers, 5 `\texttt` contents, 6
`\emph` contents, 143 comment lines — all identical to `HEAD`.

Three sites, all parentheses, because each aside carries an internal comma:

1. **The anonymous build's AI disclosure.** `(implementation, harness, analysis
   pipeline, documentation and manuscript prose)`. Which tools, over what scope,
   under whose direction and who is responsible are unchanged. The
   non-anonymous disclosure at line 203 has no em dash and is untouched.
2. **The abstract's `(an autonomous agent, a workflow engine)`**, which leaves
   the colon as the sentence's only strong break.
3. **The abstract's gloss on `\emph{Detection}`.**

### Every corrective in the abstract stays, and one of them is not a corrective

Four state a result against what a reader expects, which is what an abstract is
for: the trade is *not an engineering-quality problem*; detection comes *not
from the durability barrier*; the barrier guards *not* the fault it appears to;
the cost is *a deployment choice, not the protocol's price*.

The fifth is a false positive and is the reason to read the list rather than the
count:

> retrying risks a second real-world effect nobody observes, **not retrying** an
> effect no record accounts for

*"not retrying"* is the **subject** of the second clause, a parallel
construction, not an `X, not Y` correction. `prose_metrics.py` counts it as one.
Editing it would invert the sentence.

---

## 4. The supplementary — before and after

| metric | before | after |
|---|---|---|
| words | 4213 | 4185 |
| sentences | 153 | 161 |
| **em dashes (prose)** | **38** | **0** |
| em dashes (raw) | 42 | 4 |
| em dashes per page | 6.76 | **0.0** |
| mean sentence length | 27.5 | 26.0 |
| sd | 14.2 | 13.5 |
| corrective constructions | 44 | **43** |
| flagged vocabulary | 7 | **1** |
| signposts | 3 | **2** |
| `\emph` | 26 | 26 |
| `\textbf` | 21 | 21 |

**Invariants:** 334 LaTeX command tokens, 74 numbers, 11 labels, 14 citation
keys, 1 `\cref` target, 31 `\texttt` contents, 26 `\emph` contents, 113 comment
lines — all identical to `HEAD`.

**27 sites.** Fifteen asides carrying internal commas became parentheses: the
two cells that carry the RQ1 argument, the provably-empty result, the three
*"same X"* replication controls, the p30 run and execution counts, the five
baselines that declare no recovery service, the two medians under `everysec` and
`always`, the three shapes of Redis fault, the run's `inputs`, the
configuration-digest mismatch, and the general point about fault-injection
harnesses. Eight dashes standing before a conclusion or a reason became full
stops, one became a colon, three appositions became commas.

### No scope condition weakened

Every restructure was checked against the disclaimer it carries.

* **The provably-empty result** still says the cell is *"provably empty in the
  world and not resolvable from the store, so recovery fails closed"*.
* **The class-comparison finding** still reports *"a failure to reject at a
  precision inadequate to the question, not evidence that capability class
  leaves the applied-effect column alone"* — the corrective stays, only the dash
  goes.
* **The p30 exceptions** still sit in *"(a single observation, not a regime
  interaction)"*.
* **The keying refutation** still reports the delta and that it is *"nearly
  twice the margin"*, now as its own sentence so the number is not parenthesised.
* **The recovery scope sentence** resolved as entry 2 of `claims-to-review.md`
  on the author's Option 1 decision is **untouched**.

The two passages that state the same reasoning about an authorized, unresolved
intent — in `supp:provable` and again in `supp:provable-detail` — are punctuated
the same way, as they were before. See §7, entry 4.

### Five flagged words went, one stayed

| word | decision |
|---|---|
| *deliberately does not model* (×2), *deliberately destructive* | → *by design*, the substitution §IV and §VIII already made |
| *dropped silently* | → *dropped without record* |
| *discarding it quietly* | → *discarding it without saying so* |
| *Nothing in this section is load bearing* | → *No part of the paper's argument depends on this section* |
| *That one is worth stating precisely* | **kept** — the ordinary adverb on *stating*, not the intensifier `docs/37` §6 flags |

**`load bearing` is a check that was not firing.** `prose_metrics.py` never
flagged it because the source wraps *"load bearing"* across a newline and the
pattern carries a hyphen. §12a fixed the multi-word patterns by making the space
`\s+`; a hyphen inside a flagged word has the same problem and was not covered.
**Recommend extending §12a's fix to hyphens.** Found by eye, not by the script.

### One corrective of 34 went

> both at ceiling: the tie our analysis predicted, ~~measured rather than
> inferred~~.

`docs/37` §2 gives *"We report this rather than inferring it"* as its worked
example of contrast supplying shape, and the item's own lead already says the
variant *"is now collected"*. **The other 33 stay**, and that is the expected
result: in a document whose subject is what was and was not measured, the
corrective form is the content — *"supported by a bound rather than a test"*,
*"recorded as refuted rather than reinterpreted"*, *"we report it rather than
resolving it"*, *"the artifact enforces both rather than documenting them"*,
*"bootstrapped over runs rather than executions"*. All 34 were read
individually; the list is in `macro-scratch/corr_list.py`'s output.

### The punchline `docs/37` §3 names

> **Before:** …as a mis-timed injector rather than as a tie; **it is the
> boundary, not headroom.**
>
> **After:** …as a mis-timed injector rather than as a tie. **The result sits on
> that boundary, with no margin above it.**

Same claim: B3's lowest cell is at the floor, not above it.

---

## 5. Meaning-risk list — least sure first

### 5.1 "measured rather than inferred" was deleted, not rephrased — least sure

This is the only place in three files where a clause was removed rather than
re-punctuated. It asserted an epistemic status (measured, not inferred) that the
item's lead and the reported counts already carry. If the contrast with the
earlier analytical prediction is wanted explicitly, restore it; it is one edit
in `rewrite_supp.py`.

### 5.2 "Nothing in the mechanism is expensive." — left in place

It closes the `always`-with-the-barrier paragraph and is a punchline by
`docs/37` §3's description. **It was not touched**, because it generalises from
*the barrier* to *the mechanism*, and deleting it would remove a claim, which §0
forbids a language pass from doing. Flagged so the author can decide whether the
generalisation is wanted.

### 5.3 The §IX archive total became "That is…"

> **Before:** …18 494 files) --- 2 790 run directories and 44 794 files in all…
>
> **After:** …18 494 files). **That is** 2 790 run directories and 44 794 files
> in all…

*"That is"* reads as *i.e.*, which is the intended sense (the sum of the two
archives). Flagged only because the next sentence opens *"Between them they
carry…"* and the two are adjacent.

### 5.4 "by design" now appears five times across the manuscript

§IV, §VIII and now §IX and the supplementary (×3) all use it as the replacement
for *deliberately*. It is accurate in each, but it is becoming this manuscript's
next habit. Worth a look in the final read-through.

---

## 6. The abstract edit broke a generated file, and the suite caught it

**`tests/test_arxiv_abstract.py` failed on two tests.** `paper/arxiv-metadata.md`
carries a paste-ready abstract generated from `main.tex` by
`scripts/render_arxiv_abstract.py`, and the two parenthesis substitutions made
it stale. Regenerated with `--write`; only those two lines moved; 41 passed.

**The second failure was a cascade.**
`test_known_positive_a_truncated_abstract_is_caught` truncates the committed
abstract and asserts the checker reports *"identical for N characters"*. The
checker reports the **first differing character** when there is one, and there
was one at position 172. It passes again now.

**A correction to `9822ce2`'s commit message.** It says
`paper/arxiv-metadata.md` *"already differed from main.tex's"*, on the strength
of `SESSION-HANDOFF-2026-09-18` §4 item 3. **That is wrong.** The item was
closed by the submission-metadata pass on 2026-09-22, the two were in sync at
`HEAD`, and the test proves it — it had been passing. The handoff is stale on
that point; the repository wins, as its own header says. `e457bb5` records the
correction.

**This is the fourth instance of the generated-artifact staleness class** this
project has logged (§8, supplementary, introduction, `\HarnessLoc`). It is the
first one a gate caught before a human did.

---

## 7. `claims-to-review.md` — entry 4 added

**The supplementary points a reader at "the supplementary material", and two of
its sections answer the same question.**

`supp:provable-detail` closes with *"The supplementary material gives the probe
detail and prices the third barrier that would split the two cases"* — a
sentence that is itself in the supplementary. The comment above the section
records why: it was moved out of §VI in WS-9's length pass, and the pointer
moved with it.

It points at `supp:provable`, a sibling 500 lines earlier whose heading is the
same question plus *"and what closing it would cost"*. Both state that a
recovery process sees an authorized, unresolved intent, that this is what it
would see had the worker died during transmission, and that the two histories
are identical in everything durable. One prices the third barrier; the other
says the supplementary prices it.

Three options are set out in the entry, including whether the two sections
should merge. **No text was changed** — whether this is redundancy or
restatement at two depths is structural, not linguistic.

Entries **1, 3 and 4 are open**; entry 2 remains **RESOLVED**.

---

## 8. Two sentences `docs/37` §3 names by example are still in §VI

Reported, **not acted on**, because §VI is a closed pass.

| file:line | sentence |
|---|---|
| `06-evaluation.tex:473` | *…and only the second kind is visible without looking.* |
| `06-evaluation.tex:541` | *…it is the boundary, not headroom.* |

Both are quoted verbatim in `docs/37` §3's list of punchlines. They survived the
§VI rewrite in phases 47–48.

The second one matters slightly more: **it is the same sentence this session
changed in the supplementary**, so the same fact is now worded two ways across
the two documents. That is not a contradiction and papers restate results
routinely, which is why it was left alone rather than fixed by reopening a
committed section. **It is the author's call whether §VI gets the same
substitution.**

---

## 9. Where the manuscript stands

**§I–§IX, `main.tex` and the supplementary are done.** The prose pass has no
remaining sections.

What `docs/37` still lists as unfinished across the whole manuscript:

* **The mechanical British-spelling pass.** §VII's three `-ize` slips
  (`realized` l. 140, `formalizes` l. 226, `characterizes` l. 230) are still
  there by instruction. `analyze.py` and `authorization` are not exceptions and
  must not move.
* **`prose_metrics.py` misses hyphenated flagged words** (§4 above).
* **Emphasis.** `\emph` and `\textbf` were left at their existing counts in all
  three files this session, as in §VII and §VIII.

---

## 10. Verification

| | |
|---|---|
| live calls | **none** |
| `origin/main == HEAD` before starting | confirmed at `e091cee` |
| builds, supplementaries first | **7 / 7 / 24 / 24**, all clean |
| `check_paper_numbers.py` | **43 passed, 0 failed** |
| `check_no_repo_paths.py` | **4 builds clean, 0 failed** |
| `??` in the four PDFs | **0 / 0 / 0 / 0** |
| `prove_anonymous_gate.sh` | **green, tree restored clean** (run after the commits) |
| full suite | **2593 passed, 34 skipped** |
| invariants, all three files | **HELD** under a checker that compares every LaTeX command token, `\texttt` and `\emph` contents |
| lines over the 79-column wrap | supplementary **56 → 50**; none newly introduced in any file |
| pushed | **no** — five commits are local on `main` |

### Build order matters, and the first attempt failed on it

`build_paper.sh` fails the public main build if the anonymous one predates the
sources. The order that works is **supplementary, supplementary-anon,
main-anon, main**. The first public main build reported *"anonymous build is not
stale: 3 changed"* and correctly preserved the existing `main.pdf` rather than
promoting a build that had failed a check.

### The phase-49 gate hazard did not recur

`prove_anonymous_gate.sh` uses `paper/sections/08-threats.tex` as its staleness
fixture and runs `git checkout --` on it. §VIII was untouched this session and
every file was committed before the gate ran. `git status` after the gate was
empty.
