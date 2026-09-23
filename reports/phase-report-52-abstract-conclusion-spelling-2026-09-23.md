# Phase 52 — the abstract, the conclusion question, and the American spelling pass

**No live calls.** `origin/main == HEAD` at `bfbcae5` confirmed before any edit.

**§2 is a proposal. Nothing about a conclusion has been written into the
manuscript.**

| | |
|---|---|
| abstract | names AEP once; **250 words** |
| conclusion | **investigated, not written.** Recommendation at §2.5, draft at §2.6 |
| spelling | **73 words** converted across 11 files, plus 1 in a generator |
| new gate | `scripts/check_american_spelling.py`, wired into `build_paper.sh` |
| pages | main **24**, main-anon **24**, supplementary **7 / 7** |

---

## 1. The abstract

### 1.1 A correction first: it was 249 words, not 253

The instruction said 253 and over IEEE's 250. **It was 249 and under**, by
three independent counts taken before any edit:

| convention | words |
|---|---|
| raw LaTeX source, whitespace split | **249** |
| `to_plain_text`, the arXiv paste form | **249** |
| the rendered PDF's abstract | **249** |
| `to_plain_text`, hyphenated compounds split apart | 259 |

Only the last reading exceeds 250, and splitting *three-way* into two words is
not how IEEE counts. `docs/26` §9.3 sets the project's own target at **≤ 250**,
which it already met.

**So there was no overage to remove, and I did not invent one.** The only
change that adds a word is the one that was asked for.

### 1.2 Naming the protocol

> **Before:** We present a fail-closed protocol in which every external side
> effect is preceded by a durably acknowledged write-ahead intent…
>
> **After:** We present **AEP**, a fail-closed protocol in which every external
> side effect is preceded by a durably acknowledged write-ahead intent…

The second paragraph is where the protocol is first described, so it is where
the name belongs. Nothing is expanded, no claim is added, and nothing implies
an agent evaluation.

Also removed: a stray leading space on the following source line. LaTeX
collapses it, so no rendered word changed.

### 1.3 Final count: 250

**249 + 1 = 250.** That is at the limit rather than under it, and I want to be
plain about the consequence: **there is no margin left.** The next sentence
added to the abstract puts it over.

**I found no trim that did not cost something**, and record the three closest
so the choice is yours rather than mine:

| candidate | saves | what it costs |
|---|---|---|
| drop *"(an autonomous agent, a workflow engine)"* | 6 | the only place agents appear in the abstract, which the phase-40 closure §3.4 marks accurate and load-bearing |
| *"is what the barrier contributes"* → *"is the barrier's contribution"* | 1 | a plain verb becomes a nominalisation, against `docs/37` §6, and breaks the parallel with *"Detection … comes from"* |
| drop *"afterwards"* from *"cannot be asked afterwards"* | 1 | the temporal marker is the whole point of §III's capability axis: the endpoint cannot be asked **after the fact** |

### 1.4 arXiv metadata

Regenerated twice, because the spelling pass later touched the abstract too
(*acknowledgement* → *acknowledgment*). Final:
`render_arxiv_abstract.py --check` → **3 ok, 0 failed** (abstract 1642
characters, 278 under arXiv's limit; title matches; all 8 keywords present).

---

## 2. The conclusion — investigated, not written

### 2.1 Does TSE expect one? The repository does not say so

Searched `docs/`, `reports/` and the manuscript for IEEE or TSE guidance on a
conclusion section. **There is none.** What the repository does contain:

* `docs/26` §9.3 governs the abstract (≤ 250 words, ≤ 3 numbers) and says
  nothing about a conclusion.
* `paper/supplementary.tex:7` quotes IEEE Computer Society guidance, but on
  **supplemental material**, not structure.
* `main.tex:316` quotes the **IEEE Editorial Style Manual** on where the
  acknowledgment goes and how it is spelled. It is the only IEEE structural
  rule the repository quotes, and it is silent on conclusions.
* `scripts/build_paper.sh:16` quotes IEEE CS guidance on appendices.

**No gate, no test and no document requires one.** The one prior mention is
`reports/phase-report-46-rq4-status-2026-09-23.md` §4, which records the
absence as a fact — *"There is no conclusion section. `main.tex:301–309` inputs
sections 01–09 and stops at Artifact Availability"* — without calling it a
defect.

**What TSE practice actually is**, stated as my reading and not as a repository
fact: a concluding section is conventional in TSE and most reviewers expect
one, but it is not mandated, and papers ending on threats or on a
lessons-learned section do appear. The convention is strong enough that its
absence is noticed.

### 2.2 Where the paper currently ends

| | |
|---|---|
| last numbered section | **§IX, *Artifact Availability*** — 820 words, ~1.1 pages |
| then | `\section*{Acknowledgment}`, unnumbered, carrying the AI disclosure |
| then | references |

So the last thing a reader is told is where the code and the archive live.

**§VIII does more closing work than §IX does.** Its final subsection is
***Where the protocol should not be used***, which states the precondition
under which a durable-execution engine is strictly better, names the cost as
two fsync barriers, declines to put a ratio on it because the denominator is
not distinguishable from zero, and ends: *"AEP is for the case where the
precondition those systems require cannot be obtained, and its value is a
declared residual rather than a better guarantee."*

**That is a conclusion's final sentence, sitting two sections early.**

### 2.3 What a conclusion would contain that is not already elsewhere

Almost nothing, and that is the finding.

| a conclusion would normally… | already done, where |
|---|---|
| restate the contributions | §I's **C1–C4**, itemised |
| restate the central result | the abstract ¶3, and §VI's detection/prevention subsections |
| state what the result does not cover | §VIII, four validity subsections plus *Where the protocol should not be used* |
| say when to use the work | §VIII's last subsection, in full |
| name future work | **nowhere** — and this is the one real gap |

**The one thing genuinely absent is a forward-looking paragraph**, and it is
absent for a reason that must not be undone: the obvious future-work sentence
is *"place a real LLM in the caller position"*, and
`reports/phase-report-40-closure-2026-09-22.md` §3.2 rules that form
**permitted in principle but inaccurate in practice** —

> phase 40 **did** place a real LLM in the caller position, and a sentence
> implying the question is untouched would be false by omission. The only
> accurate version states the result, which form 1 forbids. **The two
> constraints have no overlap.**

So the single paragraph a conclusion would add that is not already in the paper
is the one paragraph the pre-registration will not let the paper write.

**Everything else would repeat.** A conclusion assembled from what is
available would be §I's contributions and §VIII's scope, in shorter words, one
page later.

### 2.4 Two options

**Option A — add a short conclusion, ~180–220 words, ~0.3 pages.**

Placed as a new §X after *Artifact Availability*, or better as a new §IX with
*Artifact Availability* moved last. It would: state the trilemma result in one
sentence; state the detection/prevention decomposition and that the barrier's
cost is therefore a deployment choice; state the boundary condition from
§VIII's last subsection in one clause; and close on the unresolved question
that is safe to name — that the detection finding has no referent outside this
artifact (§VIII), so the open problem is whether it transfers to systems the
authors did not write. Draft at §2.6.

**Cost:** ~0.3 pages onto a 24-page paper that is already over TSE's 12-page
charge point, and roughly 150 of those words restate §I and §VIII.

**Option B — leave the structure as it is.**

The paper ends on §VIII's *Where the protocol should not be used* as its
argumentative close and §IX as an availability appendix. The reason is that
§VIII already performs every function a conclusion would, and the only
non-repeating content a conclusion could add is barred by the phase-40 closure.

**Cost:** a reviewer who expects a *Conclusion* heading will notice its
absence, and "the paper has no conclusion" is a cheap review comment to write
even when the content is all present.

### 2.5 Recommendation: **Option A, in its reordered form**

Add a short conclusion **and move *Artifact Availability* after it**, so the
paper's last argumentative word is an argument rather than a URL.

Three reasons:

1. **The cost is the smallest version of a real risk.** ~0.3 pages against a
   reviewer comment that is easy to make, hard to argue with, and lands in the
   summary rather than the detail.
2. **The ordering defect is real independently of the conclusion.** Ending a
   TSE paper on *Artifact Availability* reads as the paper stopping rather than
   finishing, and that is true today, with or without §X.
3. **The repetition objection is answerable.** A conclusion that restates C1–C4
   would be waste; one that states the *decomposition* — detection is from the
   record, prevention is from the barrier, so the barrier is a deployment
   choice — states the thing the paper is actually for, which §I's contribution
   list gives as four items rather than as one argument.

**Against my own recommendation, and it is the strongest objection:** this
paper's discipline is not to say things twice, and §8 of the length problem in
`SESSION-HANDOFF-2026-09-18` §4 item 4 already notes that *"several results
appear in full in both §6 and §8"*. Adding a third statement of the central
result cuts against that. If the length pass is going to attack duplication,
**this section should be written after it, not before.**

### 2.6 Draft — for the report only, not applied

> ## X. Conclusion
>
> Non-idempotent endpoints that accept no idempotency key and cannot be asked
> afterwards what happened leave a caller three options, and only three: risk a
> duplicate, risk a lost effect, or make the uncertainty explicit. We built the
> third and measured it. AEP records an intent before every external call,
> fences every state write by lock ownership and an expected-version CAS, and
> escalates rather than guessing when recovery cannot resolve an outcome.
>
> The result we did not expect is that the mechanism separates. Detection — no
> undetected duplicate and no lost effect in any cell we measured, with a
> residual of declared ambiguity — comes from the pre-dispatch record and the
> transition table that forbids re-entry into dispatch. It does not come from
> the durability barrier, which is what withholds an effect when the store dies
> inside the acknowledgment window. Because the two are separable, the
> barrier's cost is a deployment choice rather than the protocol's price, and a
> deployment that does not fear losing its store can decline it.
>
> The boundary is the one §VIII states: where the endpoint can be enrolled in a
> transaction, given an idempotency key, or made idempotent, a durable-execution
> engine gives a stronger guarantee more cheaply, and this protocol is the wrong
> tool. What we cannot yet say is whether the detection result holds outside
> this artifact. It rests on two systems we wrote, measured by a harness we
> wrote, against a provider we wrote, and the obvious next work is to find out
> what it costs somebody else.

**~215 words.** Every claim in it is stated and evidenced elsewhere in the
paper; it makes no new one. It names no agent and no LLM. If it is adopted,
`check_paper_numbers.py` will require the two scope conditions (*"in any cell
we measured"*, *"two systems we wrote"*) to keep matching C3 and §VIII.

---

## 3. The spelling pass

### 3.1 What changed: 73 words in 11 files

Applied by `macro-scratch/spell_us.py`, one mechanical pass, every edit
anchored to a word boundary.

| British | American | count |
|---|---|---|
| acknowledgement(s) | acknowledgment(s) | **29** |
| behaviour | behavior | 6 |
| modelled / modelling | modeled / modeling | 5 |
| honour | honor | 3 |
| enrolment | enrollment | 3 |
| favour | favor | 2 |
| serialisation | serialization | 2 |
| analysed | analyzed | 2 |
| organised | organized | 2 |
| analogue | analog | 2 |
| unrecognised | unrecognized | 2 |
| realise / realises | realize / realizes | 2 |
| formalise / formalised | formalize / formalized | 2 |
| generalisation | generalization | 1 |
| generalises | generalizes | 1 |
| normalisations | normalizations | 1 |
| authorise | authorize | 1 |
| neutralised | neutralized | 1 |
| maximised | maximized | 1 |
| criticised | criticized | 1 |
| memoised | memoized | 1 |
| labelled | labeled | 1 |
| cancelled | canceled | 1 |
| judgement | judgment | 1 |
| **total** | | **73** |

Per file: `main.tex` 1, `01-introduction` 2, `02-motivating` 2, `03-model` 7,
`04-protocol` 10, `05-implementation` 3, `06-evaluation` 16, `07-related` 14,
`08-threats` 3, `09-artifact` 3, `supplementary` 12.

**`authorise` → `authorize` fixes an inconsistency rather than creating one.**
`authorization` was already American, because it is the protocol's term for the
Redis-visible record; the verb beside it was British.

**§VII's three `-ize` slips need no change.** `docs/37` §11 recorded
`realized`, `formalizes` and `characterizes` as exceptions to be settled by
this pass. They were already correct American; what the pass fixed was the
*British* forms sitting beside them in the same section.

### 3.2 What was protected, and proved to be

Verified by `macro-scratch/spell_guards.py`, which compares every file against
`HEAD`:

| protected | result |
|---|---|
| full-line and inline `%` comments | **byte-identical in all 11 files** |
| `\texttt{}` contents | **identical** |
| every LaTeX command token | **identical** |
| `\usepackage` / `\documentclass` lines | **identical** |
| `\cite` / `\ref` / `\cref` / `\label` / `\input` arguments | masked before substitution |

**`capitalise` is not a word here.** It is a `cleveref` package option in
`main.tex:64` and `supplementary.tex:34`. Converting it would break the build.
It is masked by the `\usepackage` rule and listed in the check's exemptions.

**No macro was touched, and none needed to be.** Every generated macro name was
checked against the convertible stems; the only near-miss is the `\Model*`
family, which contains *model* and not *modelled*. `check_paper_numbers.py`
stayed at **43 passed, 0 failed** throughout.

**Tabular cells were NOT protected**, deliberately: their prose is rendered
prose. `04-protocol.tex:154`'s *"capability undeclared / unrecognised"* is a
table cell and was converted. Identifiers inside cells are already inside
`\texttt` and were protected by that rule.

### 3.3 The one the `.tex` pass missed, and how it was caught

**`organised` in `paper/generated/table-outcomes.tex`.** Its caption is a
string literal at `scripts/paper_tables.py:204`, so no `.tex` scan would ever
see it and a hand edit would be overwritten on the next regeneration.

The fix went into the generator. Then, rather than trust it, the whole of
`paper/generated/` was regenerated into a scratch directory with the full
argument set and diffed against the tracked files: **five of six byte-identical,
and `table-outcomes.tex` differing by exactly one word.** That both proves the
invocation is the right one and proves the change is the only one.

```
256c256
< organised
---
> organized
```

**This is the argument for a PDF-based check in one example.**

### 3.4 One judgement call, flagged for reversal

**`analogue` → `analog`, twice** (`06-evaluation.tex:171`,
`07-related.tex:211`), both in the sense *counterpart*: *"a timeout that B4 has
no analogue for"*.

*analogue* is the British spelling and this was an American-spelling pass, so
it was converted. But **`analog` in an IEEE paper reads electronics-first**,
and *analogue* meaning *counterpart* is unremarkable in American academic
prose. If you would rather have it back, it is two edits and an `EXEMPT` entry.
**I converted rather than exempted because the instruction was mechanical and
the word is unambiguously British; the risk is a momentary misparse, not a
wrong claim.**

### 3.5 What the pass did NOT change

* **`analyze.py`** — a filename, and already American.
* **`authorization`** — the protocol's term.
* **`observe_behaviour`** and the other Python identifiers in
  `scripts/paper_tables.py` — code, referenced by provenance comments. Five
  occurrences, none rendered.
* **The bibliography.** `paper/refs.bib` contains no British spelling today, so
  nothing needed doing; the check exempts it anyway, because correcting a cited
  title is a misquotation.
* **Comments throughout.** They still read `normalisation` in places. That is
  deliberate: the instruction was to leave provenance comments alone, and a
  comment is not rendered.

---

## 4. The new check

`scripts/check_american_spelling.py`, modelled on `check_no_repo_paths.py` and
**wired into `scripts/build_paper.sh`** so it gates every build of every
variant, on the staged PDF, before promotion.

**It reads the PDFs, not the LaTeX** — which is not a stylistic preference
here. It is the only reason `organised` was found at all.

### 4.1 What it knows

* **43 explicit British→American pairs** (`-our`, `-re`, `-ce`, doubled and
  single `l`, and the miscellany: `judgement`, `artefact`, `whilst`,
  `analogue`, `programme`, `grey`…), so the failure message can name the
  replacement.
* **Generative `-ise`/`-isation`/`-yse` families**, for words the table does
  not know, filtered by a closed list of bases that are `-ise` in American
  English too (`exercise`, `comprise`, `promise`, `supervise`, `premise`…).
* **Prefix handling**, which the first run forced. *imprecise* is *precise*
  with a negation and is American; *unrecognised* is *recognised* with one and
  is not. The prefix is stripped and the remainder decides — in both
  directions, so *remodelled* is still caught.

### 4.2 The exemptions, each with its reason

`analyze.py`, `authorization`, `authorize`, `authorized`, `capitalise`,
`Idempotency-Key`, and the `-sis` nouns (`analysis`, `basis`, `emphasis`,
`hypothesis`, `synthesis`, `parenthesis`, `crisis`, `thesis`, `diagnosis`).

**Everything from the `REFERENCES` heading onward is skipped**, so a cited
title keeps its own spelling.

A test asserts **every exemption carries a stated reason**, because an
exemption nobody can re-audit is an exemption nobody will question.

### 4.3 The known-positive

`python scripts/check_american_spelling.py --selftest` — **6 of 6 confirmed**:

```
  PASS  known-positive: 'modelled' is caught
  PASS  known-positive: 'behaviour' is caught
  PASS  known-positive: 'analysed' is caught
  PASS  known-negative: -ise words common to both Englishes, their prefixed
        forms, and the exempt identifiers, are not flagged
  PASS  prefixed British form 'unrecognised' is still caught
  PASS  prefixed British form 'disorganised' is still caught
  PASS  prefixed British form 'remodelled' is still caught
  PASS  the references section is exempt, so a cited title keeps its own
        spelling
```

`tests/test_american_spelling.py` adds **75 tests**: the four builds; one
known-positive per family; one known-negative per both-Englishes word; one per
exemption; the references-boundary pair in both directions; and the
suggested-replacement strings.

**The check was written wrong twice and the tests are why that is visible.** It
first over-fired on `imprecise`, and the prefix fix then under-fired on
`remodelled`. Both are now cases in the selftest.

---

## 5. Verification

| | |
|---|---|
| live calls | **none** |
| `origin/main == HEAD` before starting | confirmed at `bfbcae5` |
| builds, supplementaries first | **7 / 7 / 24 / 24**, all clean |
| `check_paper_numbers.py` | **43 passed, 0 failed** |
| `check_no_repo_paths.py` | **4 builds clean, 0 failed** |
| `check_american_spelling.py` | **4 builds clean, 0 failed** |
| `--selftest` | **6 of 6 confirmed** |
| `render_arxiv_abstract.py --check` | **3 ok, 0 failed** |
| `??` in the four PDFs | **0** |
| abstract | **250 words** |
| pages | **unchanged**: main 24, main-anon 24, supplementary 7 / 7 |

**`main.tex` invalidates all four builds**, including both supplementaries,
because `build_paper.sh` treats it as a source for their staleness check. Both
the abstract edit and the spelling pass touched it, so the full four-build
sequence was run each time.
