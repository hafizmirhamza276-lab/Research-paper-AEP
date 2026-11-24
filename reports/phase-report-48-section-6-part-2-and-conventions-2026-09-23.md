# Phase 48 — §VI part 2, the heading convention, and the emphasis pass

**No live calls.** `origin/main == HEAD` at `a2a2f60` confirmed before any edit.
Four commits. **§VI is now fully drafted.**

| | |
|---|---|
| part 2 | em dashes **18 → 0** |
| §VI whole section | em dashes **66 → 0** |
| heading convention | **colon**, applied to all seven label-and-title headings |
| §VI emphasis | `\emph` **46 → 38**, `\textbf` **25 → 25** |
| `claims-to-review.md` | **nothing added** |
| pages | main **24**, main-anon **24**, supplementary **7 / 7** |

---

## 1. Step 1 — the ruling

> **Before:** That qualification is not modesty, and the paragraphs above are why:
>
> **After:** That qualification **carries the argument**, and the paragraphs
> above are why:

Positive form restored, flagged word gone. Committed on its own as `837744b`.

---

## 2. Part 2 — before and after

Lines 546–762: the barrier-durability subsubsection, the write-loss cell, and
RQ3. §VI-E was written earlier this session and was not touched.

| metric | before | after |
|---|---|---|
| words | 1835 | 1823 |
| sentences | 71 | 74 |
| **em dashes** | **18** | **0** |
| em dashes per page | 7.36 | **0.0** |
| mean sentence length | 25.8 | 24.6 |
| sd | 14.5 | 12.5 |
| shortest / longest | 4 / **83** | 4 / **59** |
| corrective constructions | 9 | 9 |
| flagged vocabulary | 3 | 3 |
| `\emph` | 11 | 11 |
| `\textbf` | 10 | 10 |

**The 83-word sentence was the no-`p`-value justification.** It carried two
separate arguments through an em-dashed aside. It is now three sentences: the
trial-level objection with its pairing reason, the replication-level floor, and
what the finding rests on instead. Every element survives in the same order,
including *"which is the design's floor rather than a statement about these
data"*.

**No number, interval, `p`-value or macro changed, and no caption was touched.**

## 3. §VI as a whole

Measured against the section as it stood at the start of the part-1 pass, which
already included the new §VI-E.

| metric | before | after |
|---|---|---|
| words | 6588 | 6535 |
| sentences | 265 | 277 |
| **em dashes** | **66** | **0** |
| em dashes per page | 7.51 | **0.0** |
| mean sentence length | 24.9 | 23.6 |
| sd | 13.3 | 11.9 |
| longest | 83 | **62** |
| corrective constructions | 45 | 44 |
| flagged vocabulary | 10 | **7** |
| `\emph` | 46 | **38** |
| `\textbf` | 25 | 25 |

---

## 4. Step 3(a) — the heading convention

**Chosen: a colon.** `P1: Fenced state`, `RQ1: undetected duplicates and the
shape of the residual`.

### The seven headings

| file | before | after |
|---|---|---|
| `04-protocol.tex:38` | `P1 --- Fenced state` | `P1: Fenced state` |
| `04-protocol.tex:70` | `P2 --- Detectable ambiguity` | `P2: Detectable ambiguity` |
| `04-protocol.tex:174` | `P3 --- Fail-closed liveness bound` | `P3: Fail-closed liveness bound` |
| `06-evaluation.tex:87` | `RQ1 --- undetected duplicates…` | `RQ1: undetected duplicates…` |
| `06-evaluation.tex:299` | `RQ2 --- which mechanism…` | `RQ2: which mechanism…` |
| `06-evaluation.tex:693` | `RQ3 --- cost, and how much…` | `RQ3: cost, and how much…` |
| `06-evaluation.tex:763` | `RQ4 --- recovery` | `RQ4: recovery` |

Plus one that is **not** a heading: the dash inside RQ2's question in the
opening list (`06-evaluation.tex:8`) was a second clause rather than a label
separator, and became a comma.

### Why a colon

1. **§II already uses it.** The four trace headings were converted during that
   section's pass — `Trace 1: the duplicate nobody sees (B0, naive retry)` —
   and nothing since has contradicted them. Choosing anything else would mean
   changing §II back.
2. **It is the ordinary label-title separator** in IEEE headings.
3. **They were the last systematic source of em dashes.** `docs/37` §1 targets
   about one per page; seven headings stood in the way of §IV and §VI reaching
   zero.

### The rendered numbers cannot move

The instruction requires that a labelled title's rendered number not change.
Two facts establish it:

* **`\cref` renders a counter, never a title.** Every reference to these
  sections resolves through `\label` and the section counter, neither of which
  is touched.
* **The manuscript defines no `\nameref` and no `\titleref`**, checked across
  `main.tex`, `sections/*.tex` and `supplementary.tex`. Nothing anywhere
  renders a section's title text.

All four builds are clean and `check_paper_numbers` passes at 43, including its
undefined-reference check.

### Where the manuscript now stands on em dashes

| file | em dashes |
|---|---|
| `01-introduction` | **0** |
| `02-motivating` | **0** (4 raw are `tab:trilemma` cells) |
| `03-model` | **0** |
| `04-protocol` | **0** |
| `05-implementation` | **0** |
| `06-evaluation` | **0** |
| `07-related` | 28 |
| `08-threats` | 25 |
| `09-artifact` | 8 |
| `main.tex` | 6 |
| `supplementary` | 38 (42 raw) |

§I–§VI are done. The remainder has not been through a prose pass.

---

## 5. Step 3(b) — emphasis in §VI

`\emph` **46 → 38**. `\textbf` **25 → 25**. **No mark inside a tabular grid was
touched**; §VI's tables are `\input` from `generated/` and none was opened.

### The eight removed

| mark | why it went |
|---|---|
| `\emph{zero}` ×2 | the word *zero* was already the claim |
| `\emph{below}` | *"the observed rate is below that bound"* — the word states it |
| `\emph{incomplete}` | the first of four bounds, when *conditional*, *asymmetric* and *sized by the server* carry no mark. Arbitrary rather than structural |
| `\emph{absence of an edge back into the dispatching state}` | the surrounding *"not durability but…"* already carries it |
| `\emph{the honest price of the information the endpoint withholds}` | same, inside *"not that this is cheap but that it is…"* |
| `\emph{The direction transfers; the magnitudes do not.}` | a whole sentence in italics, used as a paragraph lead |
| outer `\emph{…}` on the pos-only keying sentence | a whole sentence in italics |

**The keying sentence needed care.** Its outer `\emph` wrapped the sentence and
nested an `\emph{and}` inside, which LaTeX renders *upright*. Removing the outer
wrapper leaves `\emph{and}` italic — which is the point, because the claim is
that the rate is a property of the protocol **and** of how the question is
phrased, and that conjunction is the sentence's content.

### The thirty-eight kept, in four groups

**Defined-term first use.** `\emph{regime}`, `\emph{pre-dispatch record}`,
`\emph{barrier}`, `\emph{unwanted-applied-effect rate}`, `\emph{bound}`,
`\emph{actually}` applied, `\emph{undetected}` in RQ1, and the two
reporting-rule names `\emph{no pooled table}` and `\emph{no absolute timing
from an ungated host}`.

**Names of sections elsewhere.** *Where the fault lands after the branch
point*, *Why the provably-empty cell is not resolved*, *RQ4: recovery*.

**Ordering and contrast qualifiers where dropping the mark changes the
reading.** `\emph{before}` the call; `\emph{after}` dispatch; `\emph{during}`
transmission; `\emph{does}` typically exist, which contrasts with *no effect
can possibly exist* two sentences earlier; `\emph{say}` against what they did;
`\emph{process}` against the kernel; `\emph{dispatch}` against `\emph{applied
effect}`; `\emph{trial}` against replication; `\emph{silently}` discarding
writes, on which the whole bound depends; a property of a
`\emph{configuration}`; `\emph{controlled}` injector; `\emph{failed or
absent}` acknowledgement; `\emph{no effect can possibly exist}`; and
`\emph{the system could know that}`, which voices the reader's objection rather
than asserting it.

**One logical operator.** `\emph{and}` in the timing gate's two conditions,
which the next sentence calls out as *"Both halves are necessary"*.

### All 25 `\textbf` kept, and why — with one thing flagged

Every one is a run-in paragraph lead or a result stated against a reader's
expectation, which `docs/37` §7 permits: *"The prediction is refuted"*, *"Not
one unfsynced write was lost"*, *"We do not claim that AEP-full prevents the
unwanted effect"*, *"B4's rates are our model's, not the product's"*, *"The
overhead is the barrier, and the rest is not separable from zero"*.

**The density is a separate question and I have not decided it.** Twenty-five
bold leads is §VI's own convention for structuring a results section, and
changing it would alter how every result is presented rather than how it is
worded. That is a presentation decision, not a language one. **Flagged for you
rather than taken.**

---

## 6. Meaning-risk list — least sure first

### 6.1 The no-`p`-value paragraph was split three ways — least sure

> **Before:** …and the reason is that no unit supports one: at the trial level
> the test would assume an independence the shared device stack violates and
> would ignore the pairing --- both records are written in the same trial and
> meet the same write-loss event --- while at the replication level, three
> against three, the two-sided minimum a perfectly separated result can reach
> is $0.1$, which is the design's floor rather than a statement about these
> data.
>
> **After:** …and the reason is that no unit supports one. At the trial level
> the test would assume an independence the shared device stack violates, and
> it would ignore the pairing, since both records are written in the same trial
> and meet the same write-loss event. At the replication level, three against
> three, the two-sided minimum a perfectly separated result can reach is $0.1$,
> which is the design's floor rather than a statement about these data.

An 83-word sentence became three. Two things to check: *"and would ignore the
pairing"* became *"and it would ignore the pairing, since…"*, which makes the
pairing an explicit reason rather than an apposition; and the *"while"* joining
the trial and replication levels became a full stop, so the two objections are
now parallel rather than contrasted. **Both read to me as the original's
meaning, but this is the largest single restructure in either part.**

### 6.2 "The comparison is incomplete" lost its italics

The emphasis marked the first of four bounds. The other three carry none, so
the mark was arbitrary. **But it was also the only visual signal that a list of
four was starting**, and the list runs for 210 words. If you want the signal
back, the consistent fix is to mark all four, not to restore one.

### 6.3 A named fault class became a list with "by"

> **Before:** That narrows the claim to a named fault class --- loss of the
> page cache: host power failure, kernel panic, VM destruction --- and an
> earlier draft of this paper stopped there…
>
> **After:** That narrows the claim to a named fault class: loss of the page
> cache, **by** host power failure, kernel panic or VM destruction. An earlier
> draft of this paper stopped there…

The three causes are unchanged. *"by"* makes them causes of page-cache loss
rather than an apposition, which I believe is what the original meant.

### 6.4 Three list introductions changed connective

The five non-barrier protocol components (*"meaning …"*), the three deployment
points (a comma), and the B0-versus-B3 aside (*"since"*). In each the members
and their order are unchanged.

---

## 7. Cut candidates for part 2 — **none applied**

| # | candidate | words | restates | against cutting |
|---|---|---|---|---|
| 1 | The exposure-window qualification closing the durability subsubsection | 118 | **§VIII** *The barrier's durability benefit is measured on an emulated fault* makes the phase-alignment point | It is the qualification on `\FlakeyUnackLost{}`, stated immediately after the number. §VIII is ten pages later |
| 2 | The `dmsetup suspend` / self-test paragraph | 92 | nothing | It is what makes the probe believable; a reviewer who does not read it has no reason to accept the separation |
| 3 | The lower-mode re-analysis in RQ3, *"B3's arm is a mixture of two modes…"* | 74 | nothing | Both readings were pre-registered and they disagree; reporting one is the move the paper argues against |
| 4 | *"The barrier is a deployment choice"* paragraph | 96 | the supplementary section of the same name | It is the sentence that stops *"≈2 seconds"* being carried away as AEP's overhead |
| 5 | The Redis-documentation reading, *"you may lose 1 second of data…"* | 78 | nothing | It corrects a widely repeated misreading, which is one of the section's more transferable contributions |

**Total 458 words.** My view: **none should be cut.** 1 and 3 least of all —
both are qualifications attached to a number stated immediately above them.

---

## 8. `claims-to-review.md`

**Nothing added.** Part 2 was checked against §III's failure model and the
analysis outputs: the fault classes (F3, page-cache loss, `drop_writes`), the
`appendfsync everysec` premise, the trial and replication counts, and the
`\ProcessKillUnackLost{}` / `\FlakeyUnackLost{}` contrast are all consistent
with §III and with §IV's `tab:modelchecking` row for a truthful `fsync`.

Entry 1 remains **open** (§I's *never in the accounts*). Entry 2 remains
**RESOLVED**, with its related observation about `\label{supp:rq4}` still open
as a tidying question.

---

## 9. Verification

| | |
|---|---|
| live calls | **none** |
| `origin/main == HEAD` before starting | confirmed at `a2a2f60` |
| §VI-E | untouched by parts 1 and 2 |
| tabular grids | byte-identical; none opened |
| spelling | British `-ise`, unchanged |
| `check_paper_numbers.py` | **43 passed, 0 failed** |
| `check_no_repo_paths.py` | **4 builds clean, 0 failed** |
| builds, supplementaries first | **7 / 7 / 24 / 24**, all clean |
| `prove_anonymous_gate.sh` | green |
| cut candidates applied | **none** |
