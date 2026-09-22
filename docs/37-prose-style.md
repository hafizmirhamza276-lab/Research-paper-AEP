# Prose style for the manuscript

**Scope: language only.** This document governs a rewrite that changes how the
paper reads and nothing about what it says. It has no authority over any claim,
number, scope condition, citation, table, figure or provenance comment. Where
following a rule here would change what a sentence asserts, the rule loses.

**Why it exists.** The manuscript's English reads as over-polished. It leans on
a small set of devices — the em dash, the corrective "not X but Y", the
three-item list, the short closing sentence — often enough that they stop
carrying meaning and start supplying rhythm. The effect is a text that sounds
edited rather than written, and that asks a reader to admire a sentence when it
should be asking them to follow an argument.

`scripts/prose_metrics.py` measures the habits named below. It is **non-gating**
and always will be: a threshold on any of these numbers would be met by the
next edit rather than earned. The numbers are for comparing a section with
itself before and after a rewrite.

---

## 0. The invariants, before anything else

A language rewrite may not change:

* any `\macro`, number, `\ref`, `\cref`, `\label`, `\cite`, table or figure;
* any claim, or the scope conditions attached to it;
* the substance of C1–C4;
* provenance comments (`%` lines naming a source, a filter or an arithmetic).

If a sentence cannot be made to read naturally without altering what it claims,
**leave it close to the original and flag it** in the rewrite's report. A
slightly stiff sentence that is true is better than a fluent one that is not.

---

## 1. Em dashes

The manuscript uses 243 across roughly 31 pages of prose, about 7.7 per page.
That is the single most visible habit.

**Target: about one per page.** Some sections will have none.

Every em dash is doing a job that ordinary punctuation does as well:

| the em dash is… | replace with |
|---|---|
| a parenthetical aside | commas, or parentheses if the aside is genuinely incidental |
| an apposition or gloss | a comma, or a colon if the second part defines the first |
| a pause before a conclusion | a full stop and a new sentence |
| an interruption for emphasis | nothing. Delete the interruption and let the sentence run |

Use a colon **sparingly**, and only where the second clause specifies the
first. A colon deployed as often as the em dash was is the same habit wearing a
different mark.

**En dashes (`--`) in number ranges are correct and stay.** `10--30`,
`2026--2027`, `[-1.11, 2.04]`. The metrics script counts them separately for
exactly this reason.

**Keep an em dash only where the sentence genuinely needs a strong break** —
typically where a comma would be misread because the sentence already has
commas doing other work. Expect one or two per section at most.

## 2. Corrective constructions

The manuscript reaches for contrast as a default sentence shape: `not X but Y`,
`X, not Y`, `rather than`, `instead of`, `it is not A, it is B`. There are 178
of these. §VIII alone has 33, §VI has 43.

Contrast is a legitimate move when the reader would otherwise assume X. It is
not a legitimate default. **State the positive claim first, and add the
contrast only when a reader would plausibly have expected the other thing.**

| instead of | write |
|---|---|
| "The finding is a property of the mechanism, not of the workload." | "The finding is a property of the mechanism. It holds across the three workloads we collected." |
| "We report this rather than inferring it." | "We collected this directly." |
| "Detection comes from the record, not from the barrier." | (keep — a reader *does* expect the barrier, and the correction is the result) |

The last row is the test: keep the correction when the thing being corrected is
a belief the reader arrives with. Delete it when it only exists to give the
sentence a shape.

`rather than` is the most overused single phrase, at 103 occurrences. Most can
become a plain positive statement.

## 3. No aphorisms, and no punchlines

**Do not end a paragraph on a short sentence written for effect.** The habit is
easy to see once named:

> …and only the second kind is visible without looking.

> The magnitude is not a constant of the protocol and this paper does not offer
> it as one.

> It is the boundary, not headroom.

Each of these is a good sentence and each is doing rhetorical work the
surrounding evidence should be doing on its own. Where the closing sentence
carries real content, **move it earlier in the paragraph** and let the paragraph
end on ordinary material. Where it carries none, delete it.

**No sentence fragments used for emphasis.** "It is two." "And it did." A
fragment is a stylistic signal, and this paper has no use for one.

No quotable one-liners. If a sentence would work as a pull quote, that is a
reason to rewrite it.

## 4. No habitual triplets

Three-item lists appear throughout: "opaque, non-copyable, single-use";
"a protocol, an implementation, and a fault-injection evaluation"; "fenced
state, detectable ambiguity, and a fail-closed liveness bound".

**Where the three items are real and enumerated elsewhere, keep them.** The
three properties and the three capability classes are facts about the work.

**Where the third item exists for cadence, cut it to two or expand to a
sentence each.** The test: remove the third item and see whether anything is
lost. If not, it was rhythm.

The same applies to tricolon at the sentence level — three parallel clauses in
a row. Two is usually enough; four is fine if all four are needed.

## 5. Sentence length and paragraph shape

Mean sentence length runs 24–34 words across the manuscript, with standard
deviations of 12–18. The variation is there, but it comes from occasional very
long sentences rather than from deliberately short ones.

**Vary length on purpose.** A 12-word sentence after a 35-word one does more for
readability than any punctuation choice. Aim for a mean in the low twenties and
a range that includes genuinely short sentences carrying ordinary content, not
punchlines (§3).

**Write ordinary academic paragraphs: claim, evidence, implication.** Most
paragraphs here open with a bolded thesis and then argue toward it. That is a
fine shape used occasionally and a monotonous one used throughout. A paragraph
may simply state what was done, give the number, and say what follows.

Split any paragraph running past about 150 words unless it is a single
argument that genuinely cannot be divided.

## 6. Plain verbs and plain words

**Avoid** these, which appear as verbal tics rather than as descriptions:

`load-bearing`, `honest`/`honestly`/`honesty`, `discipline`/`disciplined`,
`crucially`, `crucial`, `notably`, `importantly`, `critically`,
`fundamentally`, `essentially`, `it is worth noting`, `worth noting`,
`the point is`, `the whole point`, `precisely` (when it means "exactly"),
`deliberately`, `quietly`, `silently` (except in `silent failure`, which is
this paper's defined term), `genuinely`, `tellingly`, `strikingly`,
`in other words`, `simply put`.

Most of these assert significance instead of demonstrating it. If a fact is
important, the surrounding argument should make that visible without an adverb.

**Prefer the plain verb.** "shows" over "establishes" where it merely shows;
"we measured" over "we characterise"; "we did not test" over "the design does
not contain a manipulation that would distinguish".

**Exception, and it matters:** `silent failure`, `declared ambiguity`,
`undetected duplicate`, `lost effect`, `fail-closed`, `fenced`, `authorization`
and the other defined terms are technical vocabulary. They are never
substituted for variety.

## 7. Emphasis

`\emph` and `\textbf` are used 185 and 92 times respectively. That is far past
the point where either signals anything.

* **`\textbf` for emphasis inside a paragraph: stop.** Keep it only for
  `\paragraph{}` run-in headings, table headers, and the handful of places
  where a result is being stated against a reader's expectation and the whole
  sentence would otherwise be missed.
* **`\emph` for first use of a defined term: keep.** For emphasis: delete. If a
  clause needs emphasis to land, the sentence is built wrong.
* Never both.

## 8. Hedging

Hedge where hedging is accurate, and not as a politeness. The manuscript is
generally good at this and should stay so.

* `we observe`, `this suggests`, `in our setting`, `consistent with`,
  `we did not test`, `we have no evidence about` — all correct where they fit.
* Do not hedge a measured fact. A count that was observed is not "appears to
  be".
* Do not use a hedge to soften a refutation. The write-loss result refuted a
  prediction, and the paper says so.

## 9. First person, and process narration

**Use "we".** It is already the manuscript's voice and it is right for a paper
with an empirical method.

**Do not narrate the process.** The paper carries a good deal of "the earlier
version of this result", "the third time we collected it", "we were wrong
about", "an earlier version of this paper reported". Most of this belongs in
`reports/`, not in the manuscript.

**The exception, and it is a real one:** where a correction is a *disclosure the
paper must make* — a refuted pre-registration, a defect the matrix found in our
own measurement, a result that moved when re-collected — it stays. The test is
whether a reviewer would be entitled to feel misled by its absence. If yes, keep
it and state it plainly. If it is only there to show the work was done
carefully, cut it.

## 10. Signposting

**At most once per section**, and only where the structure is not obvious from
the headings. "In this section we…" is rarely needed in a paper with
subsections.

Never signpost a paragraph. "Three readings, in the order they matter" and
"Two qualifications belong with that number" are the pattern; write the
readings and the qualifications instead.

## 11. Spelling

**The convention is British `-ise`, and it is already near-uniform.**
`normalisation`, `serialisation`, `anonymisation`, `formalise`, `generalisation`,
`organised`, `behaviour`, `favour`.

Three genuine exceptions exist, all in §VII, and a rewrite of that section
should settle them: `realized` (l. 140), `formalizes` (l. 226), `characterizes`
(l. 230). Each sits next to a cited system's own name for a thing, so the choice
is between matching the source and matching the manuscript.

**Not exceptions, and not to be changed:** `analyze.py` is a filename, and
`authorization` is this protocol's term for the Redis-visible record that the
dispatch guard is consumed to write. Both track identifiers in the code.

`-yse` for the verb: `analysed`, `analyses`. `analysis` is unaffected.

---

## 12. What the metrics script measures, and what it does not

`python scripts/prose_metrics.py` reports per file: words, sentences,
page-equivalents, em dashes (count and per page), en dashes, sentence length
(mean, standard deviation, min, max, median), corrective constructions by kind,
flagged vocabulary, signposts, hedges, first-person `we`, `\emph` and `\textbf`
counts, paragraphs, and paragraphs ending in a sentence of nine words or fewer.

**It cannot see §3, §4 or §5.** A punchline, a rhythmic triplet and a monotonous
paragraph shape are judgements. The `punch` column is a weak proxy, and a short
final sentence is often just a short sentence. Read the section.

**It measures prose only.** LaTeX comments are stripped first, so provenance
comments are never counted; environments holding tables, figures, code and
mathematics are removed; `\cref` and `\cite` become single tokens so a sentence
built around one still parses as a sentence; and each `\item` is treated as its
own unit, because consecutive items that do not end in terminal punctuation
otherwise fuse into one implausible sentence.

## 13a. Word counts after the path-removal pass, 2026-09-22

`scripts/check_no_repo_paths.py` replaced twenty-three rendered repository
paths with prose. The wording around each changed, so the word counts in §13
no longer describe the current text. Recorded here rather than by editing §13,
which is the pre-rewrite baseline and should stay that way.

| file | words, §13 | words now | em (prose) now |
|---|---|---|---|
| `01-introduction` | 1056 | 1065 | 0 |
| `02-motivating` | 731 | 728 | 0 |
| `03-model` | 638 | 652 | 0 |
| `04-protocol` | 2291 | 2291 | 28 |
| `05-implementation` | 440 | 444 | 4 |
| `06-evaluation` | 6389 | 6392 | 68 |
| `07-related` | 3204 | 3204 | 28 |
| `08-threats` | 3234 | 3234 | 25 |
| `09-artifact` | 816 | 825 | 8 |
| `main.tex` | 688 | 693 | 6 |
| `supplementary` | 4165 | 4175 | 38 |

§I, §II and §III are also rewritten; the others moved only where a path was
removed. The em-dash column is the prose-only count introduced with the
tabular-grid exclusion, so §II's four remaining and the supplementary's four
are table cells and not prose.

## 13. Baseline, 2026-09-22

Recorded before any rewriting, so that later runs have something to be compared
against.

| file | words | em | em/pg | len | sd | corr | flag | sign | emph | bold |
|---|---|---|---|---|---|---|---|---|---|---|
| `01-introduction` | 1056 | 11 | 7.81 | 24.0 | 16.2 | 5 | 0 | 0 | 8 | 11 |
| `02-motivating` | 731 | 19 | **19.49** | 18.3 | 12.2 | 2 | 1 | 0 | 14 | 9 |
| `03-model` | 638 | 4 | 4.70 | 17.7 | 10.7 | 9 | 0 | 1 | 15 | 12 |
| `04-protocol` | 2291 | 28 | 9.17 | 24.9 | 14.0 | 16 | 5 | 1 | 22 | 7 |
| `05-implementation` | 440 | 4 | 6.82 | 33.8 | 17.3 | 3 | 1 | 0 | 2 | 0 |
| `06-evaluation` | 6389 | 68 | 7.98 | 25.1 | 13.3 | **43** | **10** | **5** | **46** | **25** |
| `07-related` | 3204 | 28 | 6.55 | 27.6 | 14.3 | 18 | 3 | 0 | 19 | 3 |
| `08-threats` | 3234 | 25 | 5.80 | 27.4 | 14.2 | **33** | 4 | 1 | 22 | 4 |
| `09-artifact` | 816 | 8 | 7.35 | 32.6 | 14.0 | 3 | 2 | 2 | 5 | 0 |
| `main.tex` | 688 | 6 | 6.54 | 34.4 | 18.5 | 6 | 0 | 0 | 6 | 0 |
| `supplementary` | 4165 | 42 | 7.56 | 27.6 | 14.3 | **40** | 7 | 3 | 26 | 21 |
| **total** | **23 652** | **243** | **7.71** | — | — | **178** | **33** | **13** | **185** | **92** |

`02-motivating` is the worst section for em dashes by a factor of two and is
short enough to fix quickly. `06-evaluation` and `08-threats` carry most of the
corrective constructions. `05-implementation`, `09-artifact` and `main.tex` have
the longest mean sentences and almost no short ones.

## 14. Order of work

One section per pass, each reviewed before the next. §I first, because it sets
the voice a reader carries into the rest.
