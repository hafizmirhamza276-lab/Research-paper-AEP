# Phase 43 — §I's rulings applied, and §II and §III rewritten

**No live calls.** Three commits: the §I rulings, the §II rewrite, the §III
rewrite. **Stopped after §III for review.**

| | |
|---|---|
| §I rulings | five reverts, one acceptance; the one open question logged, not resolved |
| `reports/claims-to-review.md` | **created**, one entry |
| §II | prose em dashes **15 → 0**; the four in `tab:trilemma` are cell content and stay |
| §III | em dashes **4 → 0** |
| tabular grids | **byte-identical** to `HEAD` in both sections |
| `check_paper_numbers` | **43 passed, 0 failed** |
| builds | supplementary **7**, supplementary-anon **7**, main **24**, main-anon **24** |
| cut candidates applied | **none** |

---

## 1. §I — the rulings

| # | ruling | applied |
|---|---|---|
| 1 | revert to *"and it is two"* | ✔ the hedge *"we find that"* is gone |
| 2 | restore the original precision | ✔ *"…which each fail to prevent it because none of them is a record written before the call"* |
| 3 | restore the comparison | ✔ *"quieter than a duplicate and no better"* |
| 4 | remove *"structural"* | ✔ back to *"This impossibility is not incidental."* |
| 5 | restore *"never in the accounts"* | ✔ and the tension logged, not resolved |
| 6 | accepted as rewritten | ✔ unchanged |

Invariants after the rulings: 3 macros, 9 `\cref` targets, 2 labels, 3 citation
keys, 17 numbers, 12 provenance comment lines, all identical to `HEAD`. Em
dashes stay at 0, `\emph` at 1, `\textbf` at 11.

### 1.1 `reports/claims-to-review.md` — one entry added

**Entry 1: §I says the uncertainty is *never* in the accounts; the evidence for
that is scoped to what was measured.** Status **open**. It quotes §I's restored
absolute alongside three scoped statements it sits beside: C3's *"in any cell
measured"*, §VIII's *"Nothing external to this artifact establishes…"*, and
§VI-C.4's finding that the barrier *"was handed a successful one and
dispatched, behaving exactly as specified on an input that was false"*.

The entry asks three questions and answers none: whether *never* is meant as a
design property or an empirical one; whether an applied effect could have
reached the accounts unaccounted for under the write-loss regime (`summary.json`
reports `lost_effect` at zero throughout, so this may close as **checked**); and
whether §I should carry C3's scope condition. **No text is changed by it.**

---

## 2. An instrument correction, found by §II

The em-dash count was measured on the whole file minus comments. `tab:trilemma`
uses `---` in four cells as a not-applicable marker. That is table content, and
the invariants forbid touching it, so four of §II's nineteen em dashes named
something that must not be fixed.

`prose_metrics.py` now counts em dashes on the source with comments **and
tabular grids** removed, and reports the unfiltered number beside it as
`emRaw`. Grids only, not the whole float: a `\caption` is prose, and stripping
the float wrapper would have hidden the two em dashes in `tab:trilemma`'s
caption, which are real and are now fixed.

**Only three files move**, and the `emRaw` column preserves comparability with
the baseline taken before the distinction existed:

| file | em (baseline, raw) | em (prose only) | difference |
|---|---|---|---|
| `02-motivating` | 19 | **15** | 4 cells in `tab:trilemma` |
| `04-protocol` | 28 | 28 | — |
| `supplementary` | 42 | **38** | 4 cells |
| all others | unchanged | unchanged | — |

The manuscript total moves from **243** to **235** prose em dashes.

---

## 3. §II — before and after

| metric | before | after |
|---|---|---|
| words | 731 | 734 |
| sentences | 40 | 43 |
| **em dashes, prose** | **15** | **0** |
| em dashes, raw | 19 | 4 (all `tab:trilemma` cells) |
| em dashes per page | 15.39 | **0.0** |
| mean sentence length | 18.3 | 17.1 |
| sd | 12.2 | 9.7 |
| longest | 48 | 43 |
| corrective constructions | 2 | **1** |
| flagged vocabulary | 1 (`critically`) | **0** |
| `\emph` | 14 | **6** (all six are in the tabular grid) |
| `\textbf` | 9 | 9 (all in the grid) |
| paragraph-final short sentences | 4 | 2 |

**Where the 15 went.** Four were subsection-title separators
(`Trace 1 --- the duplicate nobody sees`), now colons. Two were in
`tab:trilemma`'s caption. Nine were in body prose.

## 4. §III — before and after

| metric | before | after |
|---|---|---|
| words | 638 | 646 |
| sentences | 36 | 40 |
| **em dashes** | **4** | **0** |
| mean sentence length | 17.7 | 16.1 |
| sd | 10.7 | 9.2 |
| longest | 47 | 44 |
| corrective constructions | 9 | **9** |
| `\emph` | 15 | **9** (all nine are in tabular grids) |
| `\textbf` | 12 | 12 |
| signposts | 1 | 1 |

§III was already the best-written section in the manuscript by these measures.
The work was four em dashes, six emphasis marks and two over-packed sentences.

---

## 5. Corrective constructions kept, with the reason for each

`docs/37` §2's test is whether the reader arrives with the belief being
corrected. Ten kept across the two sections.

| § | line | construction | why it stays |
|---|---|---|---|
| II | 9 | *"It is a scripted caller, not an agent."* | §I has just spent a page on agents. A reader arrives expecting an agent, and this is the paper's central disclosure about its own workload |
| III | 8 | *"proves the citation ranges are valid, not that the semantics are right"* | a scope condition on what the CI check establishes. Removing the correction would overstate the check |
| III | 33 | *"a timing budget rather than a guarantee"* | the distinction is the claim. A lease budget that a reader took for a guarantee would be a misreading of the protocol |
| III | 45 | *"Ambiguity is the default here, not a special case."* | a reader assumes ambiguity is exceptional. This is exactly the belief being corrected |
| III | 53 | *"treated as the weakest, not as the strongest"* | fail-closed semantics; the alternative is the natural assumption and is wrong |
| III | 56 | *"resolves to ambiguity, not a fall-through to `it did not happen`"* | names the specific wrong behaviour the design avoids |
| III | 84 | *"The model is crash-and-delay, not Byzantine."* | the standard scope statement for a failure model |
| III | 93 | *"OS-level `SIGKILL` of a separate worker process, not in-process exceptions"* | a reader who assumed in-process exceptions would read the whole evaluation wrongly |
| III | 96 | *"forbids progress rather than permitting a guess"* | the fail-closed rule, stated as a contrast because permitting a guess is what the alternative designs do |
| III | 145 | *"several are structural rather than incidental"* | distinguishes limitations that cannot be engineered away from ones that were not |

**Dropped:** §II's *"which is the point"* twice, and *"Critically"*. Each
asserted significance without adding a claim.

---

## 6. Meaning-risk list — old next to new

Nine. None is a claim change in my judgement; each is listed because a
reasonable reader might disagree.

### §II

**6.1 An added qualifier on "green"**

> **Before:** Nothing in the system is in a state that a monitor could alert
> on: there is no error, no retry counter above its threshold, no ambiguous
> record. The execution is *green*.
>
> **After:** …there is no error, no retry counter above its threshold, and no
> ambiguous record. **By every signal the system exposes,** the execution is
> green.

The clause I added makes explicit what the list already implied, and it removes
the one-word-italic punchline. It could be read as a mild scoping of *green*.
**This is the §II change I am least sure of.**

**6.2 The thesis moved to the front of its paragraph**

> **Before:** Neither prevents the second effect. […] \Cref{sec:evaluation}
> shows B1 and B2 duplicating at substantially the same rate as B0, **which is
> the point: the mechanisms that protect the database do not protect the
> world.**
>
> **After:** Neither prevents the second effect, **because the mechanisms that
> protect the database do not protect the world.** […] \Cref{sec:evaluation}
> shows B1 and B2 duplicating at substantially the same rate as B0.

The sentence is preserved word for word and moved from the end to the start,
per `docs/37` §3. The paragraph now argues from claim to evidence instead of
ending on the claim.

**6.3 The duplicate reveal**

> **Before:** …writes a correctly versioned record --- of a duplicate.
>
> **After:** …and the correctly versioned record it writes is a record of a
> duplicate.

Same fact. The em-dash reveal is gone and the sentence is flatter.

**6.4 Subsection titles**

Four `---` separators became colons. One title also lost a word:

> **Before:** Trace 3b --- and the at-most-once configuration loses the effect
>
> **After:** Trace 3b: the at-most-once configuration loses the effect

The leading *"and"* did not survive the colon. No label points at any of these
four headings, so nothing references them.

**6.5 The caption's connective**

> **Before:** B3 --- AEP with the durability barrier removed and nothing
> else --- reaches the same corner, **which is the point:** the barrier is not
> what buys declared ambiguity…
>
> **After:** B3, which is AEP with the durability barrier removed and nothing
> else, reaches the same corner, **so** the barrier is not what buys declared
> ambiguity…

*"which is the point:"* became *"so"*. The assertion of significance became a
causal connective, which is what the argument already was.

### §III

**6.6 A scoping word added**

> **Before:** Ambiguity is the default, not a special case.
>
> **After:** Ambiguity is the default **here**, not a special case.

*Here* was added when the sentence moved to the head of its paragraph, where it
would otherwise read as a claim about ambiguity in general rather than about
this endpoint model. It is a scoping addition and could be read as a slight
weakening.

**6.7 The F3 restructure — the largest change in §III**

> **Before:** …two probes that sharpen this considerably: the set of *faults*
> that can actually realise that loss is narrower than the documentation's
> wording suggests --- a process kill is not in it --- and a host-level write
> loss, which is, realises it every time.
>
> **After:** …two probes that sharpen this considerably. The set of faults that
> can actually realise that loss is narrower than the documentation's wording
> suggests, and a process kill is not among them; a host-level write loss is,
> and realises the loss every time.

Three claims to check: the fault set is narrower than the documentation
suggests; a process kill is not in it; a host-level write loss is in it and
realises the loss every time. All three are preserved. The original's
*"which is, realises it every time"* was the hardest clause in the section to
parse and is the reason this one was restructured rather than lightly edited.

**6.8 An out-of-model item made more explicit**

> **Before:** loss of the Redis host *after* fsync acknowledgement
>
> **After:** loss of the Redis host once the fsync acknowledgement has been
> returned

*Returned* says to whom the acknowledgement went, which the original left
implicit. Slightly more specific and, I believe, what was meant.

**6.9 A fragment made a sentence**

> **Before:** Crash-and-delay, not Byzantine.
>
> **After:** The model is crash-and-delay, not Byzantine.

`docs/37` §3 bans fragments. The correction is preserved.

---

## 7. Cut candidates — **none applied**

### §II, 96 words

| # | candidate | words | why | against |
|---|---|---|---|---|
| 1 | Trace 3's closing paragraph, *"The mitigation the vendor recommends… precondition this paper's premise removes."* | 24 | §I already quotes `temporal-activity-definition` making the same point, and §VII returns to it | It is the sentence that connects the trace to the paper's premise. Without it Trace 3 ends on a mechanism with no consequence |
| 2 | Trace 2's second sentence, *"Both are the patterns an experienced engineer reaches for, and both are doing their job…"* | 31 | The point that the mechanisms work correctly could be compressed to a clause | It is what makes the trace persuasive: the reader has to believe B1 and B2 are competently built before the failure means anything |
| 3 | `tab:trilemma`'s caption after *"decline to decide"* | 13 | Forward references to §VI-C.1 and §VI-C.2 in a caption | A caption that says B3 reaches the same corner without saying where that is measured invites the objection it is answering |
| 4 | The final paragraph's last sentence | 28 | Signposts §VI-B.1, which the reader reaches shortly | It is the sentence that turns the trilemma from a taxonomy into a claim about endpoints |

### §III, 119 words

| # | candidate | words | why | against |
|---|---|---|---|---|
| 5 | The opening paragraph about `docs/22-formal-model.md` and the CI citation check | 58 | It is an artifact claim, and §IX is the artifact section | It is what licenses the whole section to be a condensation, and a reader who does not know that will read §III as unsupported assertion |
| 6 | *"Redis executes a Lua script without interleaving… every invariant below is expressed inside one."* | 32 | §IV restates the atomic-Lua mechanism at `04-protocol.tex:43` and `:108` | §IV describes one script; §III states the general property the whole model rests on. Removing it moves a premise into a later section |
| 7 | The non-claims introduction, *"We state these because reviewers are right to look for them…"* | 20 | The table has its own *Why* column and does not need an introduction | Two lines of framing for a table a reviewer will go straight to |
| 8 | `tab:capabilities`' caption after *"can conclude"* | 9 | Forward reference to §VI-B.1 | Cheap, and it tells the reader the table is going to be tested rather than asserted |

**Total across both sections: 215 words**, about a third of a page. My view is
that 7 is the only one worth taking, and that 5 and 6 should not be cut.

---

## 8. Additions to `reports/claims-to-review.md`

**One, from §I's ruling 5.** Nothing in §II or §III raised a factual question.
Both sections' claims check out against the sections they point at: §II's
`\BaselineDupLow{}--\BaselineDupHigh{}` range, its crash-point name, and its
statements about B4's and B4b's configurations all match §VI and the cited
vendor documentation; §III's six crash points match `tab:crashpoints` and §VI-A,
and its five fault classes are the ones §VI-A now enumerates as regimes.

---

## 9. Verification

| | |
|---|---|
| live calls | **none** |
| sections rewritten | **§II and §III**; stopped for review |
| tabular grids | byte-identical to `HEAD` — 1 grid in §II, 3 in §III |
| macros, refs, labels, cites, numbers, provenance comments | identical in both |
| spelling convention | British `-ise`, unchanged, as instructed |
| `check_paper_numbers.py` | **43 passed, 0 failed** |
| builds, supplementaries first | **7 / 7 / 24 / 24**, all clean |
| gate | green |
| cut candidates applied | **none** |
