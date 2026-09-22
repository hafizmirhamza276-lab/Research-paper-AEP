# Phase 41 — the cover letter and the arXiv metadata, brought back to the body

**No live calls. `main.tex` and `supplementary.tex` are not edited.** §4 lists
the one internal contradiction found in `main.tex` for the author's decision; it
is reported, not fixed.

| | |
|---|---|
| files brought into line | `paper/cover-letter-tse.md`, `paper/arxiv-metadata.md` |
| claims checked against the body | **17** |
| claims found stale | **6** |
| abstract | was hand-transcribed and a generation behind; now **derived** from `main.tex` |
| new check | `scripts/render_arxiv_abstract.py --check`, in the suite |
| known-positives | **8**, one of which found a real defect before commit |
| `main.tex` contradictions found | **1** — reported, not fixed |
| page count | main **24 pp**, supplementary **7 pp** |

---

## 1. The cover letter, claim by claim

**The body wins.** Every row was checked against the current `main.tex` tree,
not against memory and not against `docs/`.

### 1.1 Claims that were stale — 6

| # | claim | was | now | body location |
|---|---|---|---|---|
| **1** | fault regimes, C3 | *"three collected fault regimes"* | *"five reported fault regimes"*, enumerated: every execution crashed, none crashed, Redis hard-killed before the acknowledgement, Redis killed after dispatch, storage discarding writes while reporting success | `sections/01-introduction.tex:88–94`. The body's own comment records the change: *"This said 'three collected fault regimes' until 2026-09-17"* |
| **2** | prevention scope, C4 | *"one no-readback capability class at one pre-acknowledgement Redis-kill point on one host"* | *"three sessions covering all three capability classes, at one pre-acknowledgement Redis-kill point on one host"* | `sections/06-evaluation.tex:417` — *"Over `\ArmASessions{}` sessions and all `\ArmAClasses{}` capability classes"*, resolving to **3** and **3**. The crash-point and host limits still hold (`06-evaluation.tex:506`) |
| **3** | artifact availability | *"does not yet contain the 432 raw run directories, `results/voided/`, or a complete raw-evidence SHA-256 manifest … explicit pre-submission blockers"* | the archive **exists, is built and verified in two parts**, each with its own SHA-256 manifest, each extracted and checked file-by-file; the remaining caveat is that the Zenodo DOI is **reserved, not resolving** | `sections/09-artifact.tex:9–28`; `main.tex:231–241`, where `\archiveavail` renders the RESERVED state from a single source |
| **4** | the `432` figure | *"the 432 raw run directories"* | **removed** | `432` is `\RunsCollected` — the evaluation's collected runs. It never described the archive, which §IX puts at 2 790 run directories over 44 794 files. Deleted rather than corrected: the letter does not need it |
| **5** | C4's detection half | *"The pre-dispatch record plus no re-entry produces detection, and it does so without the durability barrier."* | same, **plus** *"ablating the barrier produces no observed difference in the crashed-regime detection metrics"* | `sections/01-introduction.tex:114–122`; the result is `sections/06-evaluation.tex:297–330` |
| **6** | the write-loss disclosure | stopped at *"tests it directly with a block-level write-loss probe"* | adds that **the probe's protocol-level extension refuted its own pre-registered prediction** — `WAITAOF` acknowledged after the device stopped accepting writes, and the barrier dispatched on an input that was false | `sections/06-evaluation.tex:631–674`. The abstract now leads with this; a cover letter that omitted it was behind the paper's own disclosure |

### 1.2 Claims that were already accurate — 11

Checked and left alone, because the instruction is to bring the letter to what
the body supports, not to rewrite it.

| claim | body location |
|---|---|
| C1 — the three-way trade; three properties, each mapped to its code path, each with its residual declared | `01-introduction.tex:72–78` |
| C2 — the dispatch guard: opaque, non-copyable, single-use, scope-bound; not a cryptographic capability | `01-introduction.tex:79–87` — wording tightened to the body's (*"a control-flow invariant of the supported API"*, and the guard *"consumed to write a Redis-visible authorization"*), not a claim change |
| C3 — six named crash points | `06-evaluation.tex:23–24`, `tab:crashpoints` |
| C3 — three endpoint reconciliation capabilities | `06-evaluation.tex:17`, `tab:outcomes` |
| C3 — five baseline designs, one in two configurations | `06-evaluation.tex:17` — *"The seven of `\cref{tab:trilemma}`"* = AEP-full + five baselines, B4 twice |
| C3 — *"no undetected duplicate and no lost effect in any cell measured"* | `06-evaluation.tex:80–92`, the paragraph headed *"AEP's two silent columns are empty, everywhere measured"* |
| C3 — *"the baselines without a pre-dispatch record duplicate in most crashed executions"* | `06-evaluation.tex:94–96`, that paragraph's heading verbatim |
| C4 — *"detection is nearly free, prevention is where the fsync cost lives"* | `01-introduction.tex:126–129`; the three measured points are `supplementary.tex:522` |
| non-claims: exactly-once, an already-accepted duplicate, HA/consensus/split-brain, durability beyond one local AOF fsync, single trust domain, single node | `03-model.tex:145–178`, `tab:nonclaims` |
| disclosure — the detection ablation is *internal by construction* | `08-threats.tex:186–198` |
| disclosure — no process-level fault can exercise the barrier's durability | `08-threats.tex:55–66` |
| CI rebuilds the manuscript and re-derives every number on every push | `09-artifact.tex:53–60`, `09-artifact.tex:84–100` |
| `make reproduce-smoke`, `make reproduce-figures` | `Makefile:58,77`; both targets exist |

**One non-claim was added**, because `tab:nonclaims` makes it and the letter did
not: *no verified implementation* — the properties are model-checked, the Python
is not, and refinement is neither proven nor claimed (`03-model.tex:172–175`).
That is a disclosure, not a claim.

### 1.3 Agents, phase 40, T6, LLM

| term | cover letter, before | after |
|---|---|---|
| *agent* | 3 occurrences — *"Autonomous agents are increasingly pointed at…"*, *"long before agents existed"*, *"When an agent crashes around such a call"* | kept as motivating context and **explicitly bounded**, matching §I: the problem belongs to the endpoint, any caller inherits it, and the evaluated caller is scripted. *"When an agent crashes"* → *"When a caller crashes"* |
| *phase 40*, *T6*, *LLM*, *language model*, *Agent Execution Protocol* | **0** | **0**, and now asserted by a test |

**Neither file claimed or implied an agent evaluation before this session, and
neither does now.** `tests/test_arxiv_abstract.py::test_neither_file_claims_an_agent_evaluation`
makes that a build-time property rather than a reviewer's recollection, citing
`docs/33` §0's third banner and the phase-40 closure §6.

`"Agent Execution Protocol"` is in the forbidden list for a specific reason: the
expansion **no longer appears anywhere in the manuscript** — the retitle dropped
it — and the old arXiv abstract still carried *"We present the Agent Execution
Protocol (AEP)"*. Deriving the abstract from `main.tex` removes it; the test
stops it coming back by hand.

### 1.4 Hardcoded numbers

**Before:** one evidence number, `432`, and six spelled-out counts, of which two
were wrong (rows 1 and 2 above).

**After:** every number in the letter either resolves to a generated macro or is
a design fact the body states in the same words. A *"Provenance of every number
above"* section below the signature — explicitly marked not part of the letter —
names the source for each, because this file is hand-pasted and so cannot be
covered by `scripts/check_paper_numbers.py`.

The two macro-backed ones are named: `\ArmASessions{}` = 3 and `\ArmAClasses{}`
= 3.

**The page count is the one number with neither source**, and it is labelled as
such: it is a property of the build (`pdfinfo paper/main.pdf`), not of a tracked
CSV. It was **not mentioned at all** before; it is now stated in the header —
*24 pages, plus a 7-page supplementary submitted separately* — because an
unstated length in a TSE cover letter reads as an omission rather than a
neutral silence.

---

## 2. The arXiv abstract — the diff, and why it is now derived

### 2.1 The drift, measured

| | committed (hand-transcribed) | derived from `main.tex` |
|---|---|---|
| characters | **3 252** | **1 646** |
| words | 495 | 253 |
| paragraphs | 3 | 3 |
| word-level similarity | — | **0.433** |

**Less than half the words survived.** This was not a number going stale; it was
an entire earlier generation of the abstract, while the file's own header
claimed *"Every number in the abstract below is the resolved value of a
generated macro in `paper/generated/numbers.tex`."*

### 2.2 What changed

| change | old | new |
|---|---|---|
| **the opening, and the framing** | *"Autonomous software agents increasingly invoke legacy enterprise APIs…"* — agents as the subject | *"Many enterprise APIs are non-idempotent…"*, then *"A caller that crashes around such a call — an autonomous agent, a workflow engine —"*. The Option A position: the problem is the endpoint's, agents are one caller |
| **the protocol's name** | *"We present the Agent Execution Protocol (AEP)"* | *"We present a fail-closed protocol"*. The expansion is gone from the manuscript entirely |
| **the statistics** | five sentences of them: `540` executions per arm, a `0.50%` Wilson bound, `195/540` vs `193/540`, `0.3333` vs `0.9333` over `30` runs, `10/30` vs `28/30`, Fisher `1.9x10^-6`, write-loss `90/90` and `2.2x10^-53` | **none.** The current abstract carries no number at all; the results moved into §VI |
| **the prevention claim** | *"in one no-readback capability class, at one pre-acknowledgement Redis-kill point, on one host"* | *"against a narrower fault than it appears: it withholds dispatch when the store dies inside the acknowledgement window, not when storage discards writes while reporting success, which we injected and where it dispatched"* — the refutation is now in the abstract |
| **the baselines** | enumerated inline — naive retry, lease-only, CAS-only, ablation, engine in two settings | *"five baseline designs"* |
| **the short form** | a separately hand-written 1 906-character abridgement, needed because 3 252 > 1 920 | **deleted.** The derived abstract is 1 646 characters — **274 under arXiv's limit** — so no abridgement is needed, and a second hand-maintained copy is one more thing that drifts |

### 2.3 Title, keywords, categories

| field | checked against | result |
|---|---|---|
| **title** | `main.tex`'s `\title{}`, with the `\\` typesetting break removed | **matches**, and is now asserted by the check |
| **keywords** | `main.tex`'s `IEEEkeywords` block | **were absent from the file entirely.** Added as a section, all 8 present and checked |
| **categories** | — | `cs.SE` primary, `cs.DC` secondary. **No source exists in the manuscript**, so no check can derive them; recorded as an author decision and labelled as one |
| **figures and tables** | counted from source | **was "3 figures, 12 tables"; is 2 and 11.** Under the file's own stated scope — `main.tex`, `sections/`, `generated/` — there are 2 figures and 11 tables, 5 of them generator-produced. Including `supplementary.tex` it is 3 and 13. **The old pair matched neither scope** |
| **the `\archivedoi` line reference** | `main.tex` | said *"currently line 125"*; it is line **144**. The line number was removed rather than corrected — it is a pointer that goes stale on every edit above it, and the macro name locates it |

---

## 3. The new check, and its known-positives

### 3.1 `scripts/render_arxiv_abstract.py`

Both halves the instruction asked for, because either alone leaves a gap: a
renderer with no check drifts again the moment someone edits by hand, and a
check with no renderer tells you it is broken without fixing it.

```
python scripts/render_arxiv_abstract.py            # print the rendering
python scripts/render_arxiv_abstract.py --check    # exit 1 if stale
python scripts/render_arxiv_abstract.py --write    # regenerate the block
```

It extracts the `abstract` environment from `main.tex`, resolves generated
macros from `paper/generated/numbers.tex`, and converts to the plain text
arXiv's abstract field accepts. The generated region in `arxiv-metadata.md` is
delimited by explicit markers rather than located by heading, so renaming a
heading cannot silently retarget a rewrite.

**Two things it refuses to paper over**, because both are how a wrong number
reaches a submission:

* **An unknown macro is an error**, not a literal `\Foo` in the output.
* **A backslash surviving conversion is an error.** It means a construct
  appeared that the converter does not know, and guessing would put LaTeX
  source into a plain-text field.

Current state: `3 ok, 0 failed` — abstract matches (1 646 characters, 274 under
the limit), title matches, all 8 keywords present.

### 3.2 The known-positives — 8

`tests/test_arxiv_abstract.py`, 41 tests. Every check is exercised against an
input that must make it fail. A checker only ever seen to pass is not evidence.

| # | known-positive | what it proves can fail |
|---|---|---|
| 1 | the committed block is rewritten to open *"Autonomous agents"* | **the exact drift that happened** — content divergence, reported with the first differing character |
| 2 | the committed block is truncated to half | length-only divergence, where no character differs before the end |
| 3 | the title is changed | the title check |
| 4 | a keyword is deleted | the keyword check, naming the missing one |
| 5 | the marker block is removed | the file can't silently lose its generated region |
| 6 | `\NotAMacro` with an empty macro table | an unresolved macro raises instead of emitting a literal |
| 7 | `\cref{sec:evaluation}` in the abstract | an unconvertible construct raises instead of emitting LaTeX |
| 8 | a 2 100-character synthetic abstract | crossing arXiv's limit turns the build red |

### 3.3 A known-positive that earned its keep before commit

The parametrised converter table included `$1.9\times10^{-6}$` — the shape a
Fisher p-value takes in this manuscript. **It failed.** The first version
replaced the literal string `$\times$` and left `\times` inside a longer math
span untouched, so the renderer raised *"unconverted LaTeX"* on a construct it
was supposed to handle.

Fixed by matching math as *commands* rather than as literals, with a flag for
whether each closes up against what follows — `1.9\times10^{-6}` is one number
and renders `1.9x10^{-6}`, while `p \le 0.05` is two tokens and keeps its space.
Both directions are now in the table.

**The current abstract contains no math**, so this defect could not have been
found by running the tool on the real input. It was found only because the test
table covered a construct the manuscript might plausibly acquire, which is the
argument for known-positives stated concretely.

---

## 4. `main.tex` contradicts itself in one place — reported, not fixed

**One, and it is the same shape as the C3 defect the instruction cites.**

### 4.1 The regime count: §I promises five, §VI enumerates three

| | location | text |
|---|---|---|
| **§I, C3** | `paper/sections/01-introduction.tex:88–94` | *"An evaluation under real process kills across six named crash points, three endpoint reconciliation capabilities and **five reported fault regimes** — every execution crashed, none crashed, Redis hard-killed before the acknowledgement, Redis killed after dispatch, and storage discarding writes while reporting success"* |
| **§VI-A, *Faults*** | `paper/sections/06-evaluation.tex:25–37` | *"A regime is a named fault condition — not a matrix dimension — and **we report each separately because they are different experiments:**"* followed by an `itemize` of **three**: `crashed`, `crash-free (p0)`, `redis-kill-preack` |

**The two regimes §I names fourth and fifth are absent from §VI-A's list**, even
though the body does report both:

* `redis-kill-inflight` — `06-evaluation.tex:511–527`, *"Where the fault lands
  after the branch point, the arms tie"*, over `\InflightSessions{}` = 2
  sessions.
* `write-loss-preack` — `06-evaluation.tex:631–674`,
  `\label{sec:eval-writeloss-cell}`, the cell that refuted its own prediction.

**Why it is a contradiction and not merely an omission.** §VI-A's sentence ends
in a colon and says *"we report each separately"*. It presents itself as the
enumeration of what the paper reports. A reader who counts regimes from the
Setup gets three; §I promised five. One of the two missing is the fault the
abstract's prevention sentence turns on.

**This is the residue of a real correction**, which is why it is worth the
author's attention rather than a silent edit: §I's own provenance comment
(`01-introduction.tex:105–109`) records that C3 *"said 'three collected fault
regimes' until 2026-09-17, which was the matrix root's three and excluded the two
regimes 6.3.2.5 and 6.3.4 report"*. **C3 was fixed and §VI-A's list was not.**

**Not fixed here, per the instruction.** The remedy is a §VI-A decision — two
more bullets, or a sentence saying the list is the matrix root's three and the
other two are introduced where they are used — and either changes body text.

### 4.2 One apparent conflict that is not one, checked and cleared

`06-evaluation.tex:506` says *"The scope of the cell is one pre-acknowledgement
crash point and one host, and the **authoritative-readback** class was
subsequently collected over `\ClassSessions{}` sessions at a precision
inadequate to the question"*, which sits oddly beside `06-evaluation.tex:417`'s
*"Over `\ArmASessions{}` sessions and all `\ArmAClasses{}` capability classes"*.

**They are about different collections and do not conflict.** The macro
provenance settles it: `\ClassSessions` is from `b2-paired-v2-*`, the
*uncontrolled* cell's class comparison; `\ArmAClasses`'s own comment in
`numbers.tex` reads *"all three, **which the uncontrolled cell deliberately does
not reach**"*, sourced from `phase13-armA-*`. Line 506 is inside the paragraph
headed *"The direction replicates; the magnitude moves"*, within the
subsubsection *"The uncontrolled cell replicates the direction"*.

Recorded because it is the kind of thing that looks like a contradiction on a
fast read, and a later reviewer should not have to re-derive that it is not.

---

## 5. Verification

| | |
|---|---|
| live calls | **none** |
| `main.tex` / `supplementary.tex` edited | **no** |
| new tests | `tests/test_arxiv_abstract.py`, **41 passed** |
| `render_arxiv_abstract.py --check` | **3 ok, 0 failed** |
| builds, supplementaries first | supplementary **7**, supplementary-anon **7**, main **24**, main-anon **23** |
| gate | `prove_anonymous_gate.sh` |
| suite | full |
