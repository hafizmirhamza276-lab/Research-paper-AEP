# Phase 45 — §IV and §V rewritten

**No live calls.** `origin/main == HEAD` at `ac0e683` was confirmed before any
edit. Two commits: the §IV rewrite, and the §V rewrite with this report.
**Stopped after §V for review.**

| | |
|---|---|
| §IV | em dashes **28 → 3** (9.17 → **0.99** per page) |
| §V | em dashes **4 → 0**; mean sentence length **34.2 → 27.5** |
| invariants | held in both; both tabular grids byte-identical |
| `check_no_repo_paths` | **clean on all four builds** |
| `claims-to-review.md` | **nothing added** |
| pages | main **24**, main-anon **24**, supplementary **7**, supplementary-anon **7** |

---

## 1. Metrics, before and after

Both columns are measured with the **corrected** script (§4 below), so the
comparison is like for like.

| metric | §IV before | §IV after | §V before | §V after |
|---|---|---|---|---|
| words | 2291 | 2278 | 444 | 440 |
| sentences | 92 | 99 | 13 | 16 |
| **em dashes** | **28** | **3** | **4** | **0** |
| em dashes per page | 9.17 | **0.99** | 6.76 | **0.0** |
| mean sentence length | 24.9 | 23.0 | **34.2** | **27.5** |
| sd | 14.0 | 12.8 | 17.4 | 16.5 |
| shortest / longest | 5 / 57 | 5 / 57 | 13 / 74 | 8 / 73 |
| corrective constructions | 16 | 15 | 4 | 4 |
| flagged vocabulary | 5 | **3** | 1 | **0** |
| signposts | 1 | 1 | 0 | 0 |
| `\emph` | 22 | 19 | 2 | **0** |
| `\textbf` | 7 | 7 | 0 | 0 |
| paragraph-final short sentences | 0 | 0 | 0 | 1 |

**§IV's three remaining em dashes are all subsection-title separators** —
`P1 --- Fenced state`, `P2 --- Detectable ambiguity`,
`P3 --- Fail-closed liveness bound`. They are left deliberately: §VI's headings
use the same device (`RQ1 --- undetected duplicates and the shape of the
residual`), and changing one set without the other would be inconsistent.
**A decision for when §VI comes up.** At 0.99 per page §IV is already on
`docs/37` §1's target with them.

**§V's one paragraph-final short sentence** is *"The build fails if any test is
skipped."* It is a plain factual sentence, and it duplicates the same clause
eight lines earlier — listed as cut candidate 5 below rather than dropped.

**§IV's three surviving flagged words are all `silently`**, and all three must
stay: *"never silently re-dispatched"* and *"never silently dropped"* are P2's
own words, quoted in the state-machine subsection and the figure caption.
`docs/37` §6 exempts the paper's defined terms.

---

## 2. What was treated as specification and left alone

The instruction is that clarity for an implementer outweighs smoothness. These
were not touched at all:

* the runner's **eight-step ordering** enumerate, including
  `\emph{before any intent exists}` and `\emph{same pinned connection}`, which
  mark ordering constraints rather than supplying emphasis;
* P2's **four links** enumerate, including `\emph{consumes}`;
* both `\begin{property}` statements, apart from one punctuation change noted
  in §3.2;
* both tabular grids, `tab:classification` and `tab:modelchecking`, byte-identical;
* every state, transition and property name: `\textsc{none}`,
  `\textsc{about-to-fire}`, `\textsc{fired-confirmed}`,
  `\textsc{failed-confirmed}`, `\textsc{permanently-ambiguous}`,
  `\textsc{no-readback}`, `\textsc{authoritative}`, `\textsc{positive-only}`,
  `\texttt{LOCAL\_NO\_DISPATCH}`, `\texttt{DurabilityAck}`,
  `\texttt{execution:intent:prepared\_version}`, P1–P3, F1–F5.

Invariants, checked mechanically against `HEAD`:

| | §IV | §V |
|---|---|---|
| `\cref` targets | 17, identical | 4, identical |
| `\label` | 8, identical | 1, identical |
| `\cite` keys | 1, identical | 0 |
| numbers and maths | 22, identical | 4, identical |
| provenance comments | 4 lines, identical | 2 lines, identical |
| tabular grids | 2, byte-identical | — |

---

## 3. Meaning-risk list — least sure first

### 3.1 The model-checking table's role — *least sure*

> **Before:** \Cref{tab:modelchecking} is where the section's content actually
> is. Two rows are worth reading twice.
>
> **After:** \Cref{tab:modelchecking} is where the section's content actually
> is, and two of its rows bear on results reported elsewhere.

*"Two rows are worth reading twice"* is an instruction to the reader;
*"two of its rows bear on results reported elsewhere"* is a statement about the
rows. The two rows named are the AOF-rewind residual (§IV-B) and the
truthful-`fsync` row (§VI-C.3), and both do bear on results reported elsewhere,
so I believe the replacement is true. **But it asserts something the original
did not**, and if you would rather keep the reader-instruction form, revert the
clause.

I kept *"is where the section's content actually is"* verbatim, because
replacing it was the larger change and it is a claim about the section.

### 3.2 P2's property statement — punctuation inside a formal property

> **Before:** …reaches exactly one \emph{terminal automated} state ---
> \textsc{fired-confirmed}, \textsc{failed-confirmed} or
> \textsc{permanently-ambiguous} --- and no automated transition moves it
> afterwards
>
> **After:** …reaches exactly one \emph{terminal automated} state
> (\textsc{fired-confirmed}, \textsc{failed-confirmed} or
> \textsc{permanently-ambiguous}) and no automated transition moves it
> afterwards

The three states, their order and the scope of the apposition are unchanged.
Flagged only because this is a formal property statement and §VI and the
supplementary quote P2.

### 3.3 The barrier paragraph — only the em dashes moved

> **Before:** The two are not quite the same system --- the ablated barrier
> cannot report failure, where the real one still fails when the server does
> not answer --- so write loss removes the barrier's ability to inform while
> leaving its ability to fail.
>
> **After:** The two are not quite the same system. The ablated barrier cannot
> report failure, where the real one still fails when the server does not
> answer, so write loss removes the barrier's ability to inform while leaving
> its ability to fail.

One sentence became two; the three clauses keep their order.

**Two things in this paragraph were deliberately not changed**, against
`docs/37`: the clause *"which is the sharpest available statement of what the
mechanism is worth"*, which §6 would flag as a flourish, and the `\textbf` on
*"the barrier is not a durability guarantee but a question about durability"*,
which §7 would normally cut. The clause asserts something about the statement's
status and the bold marks the section's central claim, which §7 permits for
exactly that case. Recorded because both are visible departures from the guide.

### 3.4 "deliberately" removed in three places

| before | after |
|---|---|
| lock keys are \emph{deliberately} \emph{not} barriered | lock keys are **by design** not barriered |
| transcribed from the implementation … and \emph{deliberately} not from this section | transcribed from the implementation … and **not** from this section |
| We \emph{deliberately} do \emph{not} offer the test count (§V) | We **do not** offer the test count |

`docs/37` §6 flags *deliberately*. In the first two the replacement carries the
same content. **In the third it does not quite**: *"we deliberately do not
offer"* says the omission is a choice, and *"we do not offer"* only says it is
not offered. The following sentences still explain why, so the reasoning
survives; the marker of intent does not.

### 3.5 The AOF-rewind residual, restructured

> **Before:** And --- confirmed by a probe rather than argued --- an AOF rewind
> can un-fence: P1 is a statement about one monotonic Redis timeline, and
> because lock keys are deliberately \emph{not} barriered, a lease whose
> release was lost can reappear alongside a rewound version, so a previously
> fenced writer satisfies both conjuncts.
>
> **After:** An AOF rewind can also un-fence, and that is confirmed by a probe
> rather than argued. P1 is a statement about one monotonic Redis timeline, and
> lock keys are by design not barriered, so a lease whose release was lost can
> reappear alongside a rewound version and a previously fenced writer then
> satisfies both conjuncts.

One sentence became two and the causal chain is now serial rather than nested.
The four elements — single-timeline premise, unbarriered lock keys, reappearing
lease alongside a rewound version, both conjuncts satisfied — are in the same
order.

### 3.6 Two `\emph` markers dropped from ordering statements

`\emph{before}` in *"both refusals happen before any provider bytes exist"*
(§IV-A) and in *"a crash after a durable intent but before transmission"*
(§IV-C). In both the word keeps its position and the sentence its meaning; only
the italics go. Flagged because both mark a temporal ordering that the protocol
turns on.

---

## 4. A measurement correction, found while measuring §V

§V's corrective count came out as 3 before and 4 after, which did not match the
text: both versions contain four `rather than`.

**The cause is LaTeX line wrapping.** The source wraps at column 79, so a
two-word phrase splits across a newline wherever the line happens to end. §V's
*"are declared rather\nthan hidden"* was invisible to a pattern written with a
literal space.

Every multi-word pattern now uses `\s+`, in `CORRECTIVE` and in the
`FLAGGED_WORDS`, `SIGNPOSTS` and `HEDGES` tables that `count_phrases`
normalises. **It moves four other sections' counts**, all upward:

| file | corr, was | corr, now |
|---|---|---|
| `06-evaluation` | 43 | **44** |
| `07-related` | 18 | **21** |
| `08-threats` (hedges) | 2 | **3** |
| `supplementary` | 40 | **43** |

`docs/37` §12a records this alongside the earlier tabular-grid correction, and
notes that §13's baseline `corr` column should be read as a lower bound. **Both
defects made the script report fewer faults than the text contains**, which is
the direction that matters: no section was ever reported worse than it was.

The before-figures in §1 above are measured with the corrected script.

---

## 5. Corrective constructions kept — 19, with reasons

`docs/37` §2's test is whether the reader arrives with the belief being
corrected. All nineteen pass it; most are scope disclaimers.

### §IV, 15

| line | construction | why it stays |
|---|---|---|
| 31 | *"a reason naming the preflight rather than the barrier"* | which of two refusal paths fired is the distinction the sentence exists to draw |
| 35 | *"keys on the resulting status rather than on which of the two refused"* | how the classifier counts, which is what makes the two paths comparable |
| 61 | *"Expiry, not deletion, ends the guarantee"* | a reader assumes deletion ends it; the correction is the residual |
| 64 | *"confirmed by a probe rather than argued"* | the evidential status of the claim |
| 84 | *"exact rather than cautious"* | says the term is meant literally, against the natural reading |
| 113 | *"mutation/reuse checks, not a cryptographic security boundary"* | a required scope disclaimer on an attacker model |
| 132 | *"a precondition of P2's soundness rather than a courtesy about late responses"* | the claim about what the delay is for |
| 146 | *"produced by design rather than by failure"* (caption) | what the two bold rows mean |
| 192 | *"not a gap in practice, but it is not a global watchdog either"* | two-sided, and both sides are scope |
| 199 | *"confirmed by executable probes in the artifact, not asserted"* | evidential status |
| 222 | *"enforced inside the atomic script rather than by the caller"* (caption) | where enforcement lives, which is P2's substance |
| 241 | *"chosen adversarially rather than derived from anything the caller did"* | the modelling decision the result rests on |
| 263 | *"rather than letting it pass while meaning nothing"* (caption) | the non-vacuity claim |
| 287 | *"out of the model rather than modelled badly"* | why the exclusion is principled |
| 290 | *"is \emph{assumed}, not checked"* | the boundary of what TLC establishes |

Two more are inside quoted property text or a `%` comment and are not counted
as prose: *"not termination in an unbounded run"* (§IV, a scope disclaimer that
stays) and the `Depths are used rather than state counts` provenance line.

The paragraph heading *"The barrier is a query about durability, not a
guarantee"* and its body sentence *"the barrier is not a durability guarantee
but a question about durability"* are the section's central claim and stay in
corrective form, because the belief being corrected is exactly the one a reader
brings.

### §V, 4

| line | construction | why it stays |
|---|---|---|
| 18 | *"rejects a malformed document rather than trusting the client that sent it"* | where validation happens, which is the claim |
| 25 | *"a property of the code rather than of this sentence"* | the point of the composition gate |
| 30 | *"declared rather than hidden"* | a disclosure claim about the two weaknesses |
| 32 | *"operator-supplied rather than KMS-wrapped"* | names the weakness by contrast with the production design |

---

## 6. Cut candidates — **none applied**

### §IV, 181 words

| # | candidate | words | restates | against cutting |
|---|---|---|---|---|
| 1 | *"The irreducible gap, stated"*'s last three sentences, from *"A principal with direct Redis access…"* to *"…which this implementation does not have."* | 62 | **§VIII's *The dispatch guard assumes trusted same-process code*** (`08-threats.tex:92`) covers the same attacker model | §IV is where the guard is specified, and a reader who meets the four links without the limit in the same subsection may carry an overclaim into §VI |
| 2 | *"What this establishes, and what it does not"*'s Redis-assumed sentence | 38 | **§III's F3** and **§VI-C.3** both state that `WAITAOF` semantics are a premise that can be false | It is one of the four bounds in a deliberately parallel list; removing one leaves three and an unexplained "four" |
| 3 | The second half of *"A fifth link, and it is a clock"*, from *"Remove that delay…"* to *"…in ten steps."* | 48 | **`tab:modelchecking`'s reconciliation-delay row** gives the same counterexample at 10 steps | The prose says what the counterexample *is*; the table only says a property breaks in 10 steps |
| 4 | *"False-positive ambiguity is the price"*'s last sentence | 33 | **§VI-B.1** states the same asymmetry with the data | It is the forward pointer that makes §VI-B.1's shape predictable |

### §V, 96 words

| # | candidate | words | restates | against cutting |
|---|---|---|---|---|
| 5 | *"The build fails if any test is skipped."* (Reproducibility) | 8 | **the same clause eight lines earlier**, *"CI that fails if any test is skipped"* (On test counts) | Genuine duplication and the cheapest cut in either section. **My view: this is the one worth taking** |
| 6 | *"On test counts"*'s middle sentence about the prior internal audit | 45 | **§VIII's *Test counts are not protocol assurance*** (`08-threats.tex:132`) makes the claim without the audit detail | The audit is the evidence for the claim; §VIII asserts it and §V supports it |
| 7 | *"What the protocol rests on"*'s second sentence about the three off-path scripts | 34 | nothing | It is the statement that bounds which scripts the properties depend on, which a reader checking §IV needs |
| 8 | The Lua UTF-8 / duplicate-member sentence | 33 | nothing | Small and load-bearing for the "store rejects rather than trusts" claim |

**Total 277 words**, about a third of a page. Only 5 is clearly worth taking.
1 and 2 restate §VIII and are the most defensible larger cuts, but both remove a
limitation from the section that states the mechanism.

---

## 7. `claims-to-review.md`

**Nothing added.** Both sections were checked against §III's model and §VI's
results:

* §IV's six crash points, F1–F5 references and the `\textsc{}` capability names
  match `tab:crashpoints` and `tab:capabilities` in §III.
* §IV's counterexample depths (4, 8, 8, 9, 16, 10, 12) and the
  six/nine/seven/two configuration counts are internally consistent: seven rows
  shown of nine that must fail, plus two non-vacuity witnesses, plus six that
  check the properties hold.
* §IV's claim that the truthful-`fsync` row is §VI-C.3's write-loss result in
  the model matches what §VI-C.4 reports.
* §IV's *"ambiguity is highest at exactly the crash point where no effect can
  possibly exist"* is consistent with `tab:crashpoints`' `after_barrier_before_dispatch`
  row (*record durable; no effect*) and with §VI-B.
* §V's `\CoreLoc{}` and `\HarnessLoc{}` are generated macros and unchanged.

---

## 8. Verification

| | |
|---|---|
| live calls | **none** |
| `origin/main == HEAD` before editing | confirmed at `ac0e683` |
| spelling | British `-ise`, unchanged |
| `check_paper_numbers.py` | **43 passed, 0 failed** |
| `check_no_repo_paths.py` | **4 builds clean, 0 failed** |
| builds, supplementaries first | **7 / 7 / 24 / 24**, all clean |
| `prove_anonymous_gate.sh` | green |
| cut candidates applied | **none** |
