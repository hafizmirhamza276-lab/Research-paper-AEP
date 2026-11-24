# Length plan: 24 pages against a 12-page budget — 2026-09-24

**Nothing is applied.** No manuscript text was changed, no build was run. Every
candidate below is a proposal with a location, a word count and a verdict.

**Repository state:** `179f0f7` plus this session's prereg-order fix. Counts are
from `paper/` at that state and from `paper/main.pdf` as currently built
(2026-09-24 09:57).

**Why this exists.** TSE's regular-paper limit is 12 formatted pages and the
charge beyond it is $220 per page, assessed on the final formatted article
(`reports/tse-venue-2026-09-24.md`). The main body is 24 pages. The external
audit's §5.1 named the length problem and §5.2 named the sentences; this puts
numbers on both.

---

## 1. How the numbers were produced

Two measurements, deliberately separate so a disagreement between them is
visible:

1. **Rendered.** `pdftotext -layout paper/main.pdf` → **24 pages, 24 028
   words**, i.e. **1 001 rendered words per page** as the document actually
   sets.
2. **Stripped source.** Each `.tex` with comments, environments, commands,
   optional arguments and LaTeX punctuation removed, then word-counted. Body
   total **22 445**. Ratio rendered/stripped = **1.071**, so **one source word
   ≈ 1.07 rendered words ≈ 0.00107 pages**, and **≈ 935 source words ≈ one
   page**.

Scripts used, both read-only and both under the ignored `.scratch/`:
`.scratch/length/budget.py` (per-section) and `.scratch/length/spans.py`
(per-span, with the `file:line-line` for each so any figure can be rechecked
with `sed`).

**The one caveat that matters, stated up front.** Word counts understate float
area. A text-only two-column compsoc page holds roughly 1 100–1 200 words; the
document averages 1 001, so **floats, headings and whitespace occupy about 2–4
of the 24 pages (9–17%)**. Two figures and nine tables sit in the body. Cutting
*words* therefore recovers pages at a slightly worse rate than the arithmetic
below implies, and cutting a *float* recovers more than its word count. Treat
every page figure here as **±0.5 pages**, and treat the tier totals as
estimates rather than promises — the only authoritative number is a build, which
this session did not run.

---

## 2. The budget as it stands

| section | source w | est. rendered w | page-equiv |
|---|---|---|---|
| **6 Evaluation** | 7 005 | 7 499 | **7.49** |
| **9 Threats to Validity** | 3 477 | 3 722 | **3.72** |
| **7 Related Work** | 3 305 | 3 538 | **3.53** |
| 4 The AEP Protocol | 2 642 | 2 828 | 2.83 |
| 1 Introduction | 1 129 | 1 209 | 1.21 |
| 3 System and Failure Model | 1 060 | 1 135 | 1.13 |
| generated tables (captions + cells) | 915 | 980 | 0.98 |
| 2 Motivating Traces | 913 | 977 | 0.98 |
| 8 Artifact Availability | 857 | 917 | 0.92 |
| front matter + acknowledgment | 689 | 738 | 0.74 |
| 5 Implementation | 453 | 485 | 0.48 |
| **TOTAL** | **22 445** | **24 028** | **24.00** |

Section 6 broken down, because it is where a third of the paper lives:

| subsection | source w | page-equiv |
|---|---|---|
| 6.3 RQ2 (all four sub-subsections) | 3 586 | 3.83 |
|  — 6.3.2 Prevention | 1 428 | 1.53 |
|  — 6.3.3 The barrier's durability under the fault | 948 | 1.01 |
|  — 6.3.1 Detection | 689 | 0.74 |
|  — 6.3.4 Write-loss refutation | 409 | 0.44 |
| 6.2 RQ1 (with 6.2.1–6.2.3) | 1 776 | 1.90 |
| 6.1 Setup | 812 | 0.87 |
| 6.4 RQ3 cost | 532 | 0.57 |
| 6.5 RQ4 recovery | 246 | 0.26 |

The supplementary is **4 588 source words over 7 rendered pages**. It has no
page limit, which is the single most important fact in this document: **moving
a word there costs nothing and cutting it costs the same nothing.** Only
main-body reductions count against the 12 pages.

---

## 3. What 12 pages would actually require — stated honestly

**It is not reachable by trimming. It requires moving results to the
supplementary.**

The arithmetic: 12 pages ≈ 12 014 rendered words ≈ **11 218 source words**. The
body is 22 445. **You have to remove 11 227 source words — exactly half the
paper.**

For scale, the three largest sections together (6, 7 and 9) are 13 787 source
words. Reaching 12 pages by cutting them alone would mean deleting **81%** of
Evaluation, Related Work and Threats combined. Every sentence the audit flagged
as cuttable — all the revision history, all the meta-commentary, all the process
detail — comes to **410 source words in the body**, which is **0.44 pages**, or
**3.7% of what is needed.**

So the honest statement is:

> **Tiers 1 and 2 are worth doing and will not get the paper under 14 pages,
> let alone 12. Reaching 12 pages means Section 6 keeps its headline results
> and one table, and RQ2's mechanism detail, RQ3, RQ4 and most of Section 9
> move to the supplementary. That is a different paper's structure, not an
> edit.**

**Three options, and the third is the one nobody has costed.**

1. **Restructure to 12 pages** (Tier 3). Achievable on the arithmetic below.
   Costs the reviewer the ability to read the evaluation without opening a
   second document, and costs the author a rewrite of Section 6's connective
   tissue.
2. **Submit at ~22–23 pages and pay.** MOPC on 24 pages is 12 × $220 =
   **$2 640**; at 22 pages, 10 × $220 = **$2 200**. The charge is assessed on
   the *final formatted* article after acceptance, so the figure is an estimate
   on the current layout. **This is a legitimate option** and it is cheaper in
   author-hours than a half-rewrite. Whether it is cheaper in money is a
   question this document cannot answer. An editor may still ask for cuts
   regardless.
3. **Land the pending corrections first, then measure again.** See §8 — this is
   the recommendation.

---

## 4. Tier 1 — safe cuts

Safe means: the sentence addresses a reader who never saw a previous version,
or comments on the paper's own virtue, or describes process that belongs in the
artifact. Removing it loses no result, no limitation and no number.

### 4.1 Revision history

These address readers of an earlier draft. In a first submission they read as an
undisclosed resubmission or as an artifact of iterative AI-assisted drafting —
the audit's §5.2 makes both readings. **Every one is a pure cut: state the
current result and its limitation, drop the history.**

| # | text | location | src w | what is lost | verdict |
|---|---|---|---|---|---|
| RH1 | *"We introduce that margin in this revision; it was not preregistered…"* | `06-evaluation.tex:351-353` | 36 | Nothing, **if** "not pre-registered, stated as a stipulation" survives — that half is a real disclosure and must stay | **safe**, reword not delete |
| RH2 | *"…which the earlier version of this result was criticized for not reporting"* | `06-evaluation.tex:447-449` | 31 | Nothing. The between-session spread is still reported | **safe** |
| RH3 | *"B3 is not the negative control an earlier version of this paper reported it to be"* | `06-evaluation.tex:533-536` | 51 | Nothing — the finding *"its session-level interval is far too wide to have contradicted the mechanism"* stands on its own and is the part that matters | **safe**, reword |
| RH4 | *"An earlier draft of this paper stopped there, naming a fault it had not injected. We now inject it."* | `06-evaluation.tex:592-593` | 27 | Nothing. "We inject it" is the whole content | **safe** |
| RH5 | *"An earlier draft of this paper quoted that remainder as a point figure of about thirty milliseconds; it rested on three runs per arm, and twelve more did not confirm it."* | `06-evaluation.tex:750-752` | 39 | **Careful.** The *"twelve more did not confirm it"* clause is a negative result and the audit praises it. Cut the draft framing, keep the non-confirmation | **safe**, reword |
| RH6 | *"We now require both a pre-run declaration… and a per-run wall-versus-monotonic check"* | `08-threats.tex:378-384` | 72 | The timing-gate disclosure, which is load-bearing — it explains why recovery-latency distributions are absent | **judgement** → Tier 2 |
| RH7 | supp: *"uncollected in an earlier draft"* | `supplementary.tex:386-390` | 46 | Nothing | safe, **but supplementary — no page benefit** |
| RH8 | supp: *"the third is the one the earlier framing of this paper concealed"* | `supplementary.tex:533-534` | 15 | Nothing. The three points stand without the confession | safe, **supplementary — no page benefit** |

**Body total RH1–RH5: 184 source words.**

### 4.2 Meta-commentary

Sentences about the paper's own honesty. The audit: *"Reviewers read this as
defensive, and it spends words the paper cannot afford."*

| # | text | location | src w | what is lost | verdict |
|---|---|---|---|---|---|
| MC1 | *"Declared ambiguity is not free, and a paper that presented it as a pure win would be selling something."* | `06-evaluation.tex:302-303` | 27 | Nothing. The next sentence — each declared ambiguity stops an execution and needs a human — makes the point with evidence | **safe** |
| MC2 | Run-in heading *"The result fell below its own pre-registered bound, and we report that as a surprise rather than a success"* | `06-evaluation.tex:454-455` | 24 | A heading. The audit separately flags full-sentence run-in headings as hard to scan. *"Below the pre-registered bound"* does the job | **safe**, reword |
| MC3 | *"…and choosing between them after seeing them is the move this paper is arguing against."* | `06-evaluation.tex:738-740` | 31 | **Careful.** *"We report both because they were both pre-registered and they disagree"* is the substance and must stay; only the aphorism goes | **safe**, reword |

**Body total: 82 source words.**

### 4.3 Process detail belonging in the artifact

| # | text | location | src w | what is lost | verdict |
|---|---|---|---|---|---|
| PD1 | *"One results directory was destroyed during tooling work and recovered from the archive"* | `08-threats.tex:369-376` | 63 | An incident already recorded in `reports/incident-fsync-always-raw-destroyed-2026-09-14.md` and in the supplementary. **But** it is also evidence that the archive's manifest works, which is a claim Section 8 makes. Move to the artifact section as a clause, or drop | **safe** |
| PD2 | Citation-verification mechanics (DBLP API, `doi.org`, fetched-on-date, *"the raw lookup transcript is not present…"*) | `09-artifact.tex:108-114` | 81 | The last sentence is an honest disclosure of a gap in the evidence chain and should survive somewhere. The mechanics should not be in the paper | **safe**, keep one clause |
| PD3 | supp §6.3 *"The test suite is destructive to a running matrix"* | `supplementary.tex:487-522` | 290 | Nothing a reader of the paper needs | safe, **supplementary — no page benefit** |

**Body total: 144 source words.**

### Tier 1 running estimate

| | source w removed | rendered | pages |
|---|---|---|---|
| Revision history (body) | 184 | 197 | 0.20 |
| Meta-commentary | 82 | 88 | 0.09 |
| Process detail (body) | 144 | 154 | 0.15 |
| **Tier 1 total** | **410** | **439** | **0.44** |

**Pages after Tier 1: 24.0 → 23.6.**

Plus 533 source words removable from the supplementary (RH7, RH8, PD3, and the
supp §3/§9 merge below) at **zero** page benefit. Worth doing for quality; it
buys nothing against the limit.

---

## 5. Tier 2 — judgement calls

### 5.1 The 569 words already collected

`reports/phase-report-49-prose-sections-7-8-2026-09-23.md` §6 lists eight
candidates with word counts and, for each, an argument against cutting it.
**None was applied**, and the phase's own assessment was that none should be.
Reproduced with that assessment intact:

**Section 7 (Related Work), 268 words**

| # | candidate | w | against cutting | verdict |
|---|---|---|---|---|
| 1 | Stripe and Adyen contract details | 96 | They evidence that one header name carries different guarantees, which is the paragraph's claim | **load-bearing** — keep |
| 2 | *"Why not two-phase commit"*'s Spanner paragraph | 76 | Forestalls *"but Spanner does it"*, which a reviewer will raise | **judgement** |
| 3 | The workflow-management-systems sentence | 44 | Historical bridge; without it the durable-execution line starts in 2016 | **judgement** |
| 4 | *"Fault-injection lineage"*'s FATE / LDFI / Elle comparisons | 52 | Each names a method this work is not, which is what a related-work section does | **judgement** |

**Section 9 (Threats), 301 words** — these are the §6/§9 duplication the audit
named, item by item:

| # | candidate | w | restates | against cutting | verdict |
|---|---|---|---|---|---|
| 5 | Kill-latency attribution's interval detail | 88 | Section 6.4 | §6 reports the attempt; §9 reports that it failed *at this precision* | **judgement** |
| 6 | *"B4 is our model of a durable-execution engine, and the real one"* | 84 | Section 6.2's B5 paragraph | §6 states the result, §9 states the threat it leaves. Cutting leaves the threat unstated | **judgement** |
| 7 | The voided-run description | 71 | supplementary RQ4 | Two sentences make the oracle-independence claim checkable rather than asserted | **judgement** — and see the note below |
| 8 | *"Concurrency coverage is narrow"* | 58 | nothing | A reviewer will ask what concurrency was exercised | **load-bearing** — keep |

**Note on candidate 7.** It is the sentence `reports/claims-to-review.md` entry 3
was reopened on — it asserts the run is in the *published* archive, which is
false while `\archivedoistate` is `RESERVED`. **Do not cut it as a length
measure while that entry is open**, because deleting a false sentence to save
71 words would close a correctness question by accident rather than by decision.

**Cutting whole paragraphs rather than phase 49's narrower spans** would take
candidates 5–8 from 301 to **453** source words (measured: `08-threats.tex`
321-337 = 162, 114-122 = 99, 220-239 = 117, 255-262 = 75). The extra 152 words
are the surrounding sentences, and they are the ones carrying the threat
framing. Not recommended.

### 5.2 RH6, reworded

`08-threats.tex:378-384`, 72 source words. Cut *"We now require"* and keep the
requirement: the gate is real, it is strict, and it costs the paper its
recovery-latency distributions. **Saves roughly 40 words**; the rest must stay.

### 5.3 The supplementary §3 / §9 duplication

`supp:provable` (`supplementary.tex:189-220`, **294** words) and
`supp:provable-detail` (`:698-731`, **182** words) answer the same question,
500 lines apart. Merging saves **~182 source words in the supplementary** —
**zero pages in the body** — and closes the open half of
`reports/claims-to-review.md` entry 4. The author's 2026-09-23 decision was that
this belongs to the length pass; this is the length pass, and the answer is that
it is a quality fix rather than a length fix.

### Tier 2 running estimate

| | source w removed | pages |
|---|---|---|
| S7 candidates 2, 3, 4 | 172 | 0.18 |
| S9 candidates 5, 6 (not 7 while entry 3 is open; not 8) | 172 | 0.18 |
| RH6 reworded | 40 | 0.04 |
| **Tier 2 total (body)** | **384** | **0.41** |
| **Tier 1 + Tier 2** | **794** | **0.85** |

**Pages after Tier 2: 24.0 → 23.2.**

This is the finding worth sitting with. **Every sentence the audit named, plus
every cut candidate three rewrite passes collected, comes to 0.85 pages.** The
length problem is not made of bad sentences. It is made of Sections 6, 7 and 9
being 14.7 pages between them.

---

## 6. Tier 3 — structural

This is the only tier that reaches 12. Each line moves material to the
supplementary rather than deleting it, so no result is lost from the record —
only from the body.

| # | move | source w | pages | what a body-only reader loses | verdict |
|---|---|---|---|---|---|
| T3-1 | **Section 9 → supplementary**, keeping ~700 words of body threats (construct/internal/external in one paragraph each, plus the non-claims) | −2 775 | −2.97 | The threat framing at the point of reading. A reviewer expects threats *in* the paper; this is the least popular move on the list | **structural**, and the one most likely to draw a reviewer complaint |
| T3-2 | **Section 6.3.2 Prevention detail and 6.3.3 → supplementary**, keeping the result, one interval and a pointer | −1 900 | −2.03 | The mechanism argument for RQ2, which is the paper's central claim | **structural**, and see §8 |
| T3-3 | **Section 6.4 RQ3 + 6.5 RQ4 → supplementary**, keeping two sentences and a table reference | −600 | −0.64 | RQ3's ordering result and RQ4's counts. RQ4 is already thin (audit S8) and the supplementary already carries its argument in full | **structural**, lowest cost on the list |
| T3-4 | **Section 7 halved** — related work cannot move to the supplementary (reviewers read it to judge novelty) so this is a genuine cut | −1 700 | −1.82 | Depth of positioning. Candidate 1's Stripe/Adyen evidence must survive | **structural**, genuine loss |
| T3-5 | **Section 6.2's three sub-subsections → supplementary**, keeping 6.2's headline | −900 | −0.96 | The residual's shape, which is half of RQ1 | **structural** |
| T3-6 | **Section 4 trimmed** 2 642 → ~1 800 | −842 | −0.90 | Protocol detail; the TLA+ configs and the artifact carry it | **judgement** |
| T3-7 | **Move 3 of the 9 body tables to the supplementary** | n/a | −1.2 | Inline access to the ablation and deployment tables | **structural**, and the best pages-per-unit-of-loss on the list because float area exceeds word area |

**Tier 3 running estimate**

| after | pages |
|---|---|
| Tier 1 + 2 | 23.2 |
| + T3-3 (RQ3/RQ4) | 22.5 |
| + T3-7 (three tables out) | 21.3 |
| + T3-1 (threats out) | 18.4 |
| + T3-5 (RQ1 detail out) | 17.4 |
| + T3-2 (RQ2 detail out) | 15.4 |
| + T3-4 (related work halved) | 13.6 |
| + T3-6 (protocol trimmed) | **12.7** |

**And 12.7 is where honest arithmetic lands, not 12.0.** Closing the last 0.7
pages means either a ninth move not on this list, or accepting one overlength
page at $220, or discovering on an actual build that float repacking helps.
**±0.5 pages of uncertainty sits on every line above**, so 12.7 could be 12.2 or
13.2; only a build settles it, and no build was run.

---

## 7. What is explicitly **not** a cut candidate

Recorded so that a later pass does not rediscover them as savings:

- **The negative results.** The write-loss refutation, the keying-sensitivity
  miss, the prevention bound missed from below, B3 no longer being a negative
  control, the unconfirmed ~30 ms. The audit singles these out as *"better than
  typical"*. Cutting them to save pages would trade the paper's best property
  for about 1.5 pages.
- **The post-hoc ±5 pp margin disclosure** (`06-evaluation.tex:351-353`, the
  non-history half of RH1).
- **Candidate 7**, while `claims-to-review` entry 3 is open — §5.1.
- **The Bonferroni coverage passage**, which needs *correcting* (audit item 7,
  ≥80% not ≥90%) before anyone considers its length.
- **The abstract**, at 250 words and IEEE's limit with no margin.

---

## 8. The recommendation: do not start yet

Three pending changes will move Section 6, and doing the length work first means
doing it twice.

1. **B1 (the detection/barrier scope) makes §6.3 longer, not shorter.** The fix
   is to scope four statements, discuss Table 6's restart row, and state that
   detection under record-destroying faults is untested and fails in the model
   (`reports/audit-response-2026-09-23.md` §2.6). That is new text in exactly
   the subsection T3-2 proposes to move.
2. **B2's re-collection is in flight.** Phase 53
   (`prompts/phase-53-abd-immediate-2026-09-24.md`) re-collects
   `after_barrier_before_dispatch` with an immediate kill, and its result is to
   be reported **separately with its own macros and its own n**, not pooled.
   That adds a cell, a disclosure in §6.1 and probably a table.
3. **The AI disclosure rewording** adds roughly 45 words across the two branches
   (`reports/ai-disclosure-2026-09-24.md` §6.3).

**Sequence:** land B1's rescoping and B2's cell, rebuild, re-measure, then apply
Tier 1 whole (it is safe regardless and costs nothing to redo), then decide
between Tier 3 and paying the MOPC with the real page count in front of you.

**One thing to do now, cheaply:** Tier 1's 410 body words and the 533
supplementary words are safe under every scenario above. They do not depend on
B1, B2 or the disclosure, and applying them early removes the flagged sentences
from anything a reviewer sees. They will not change the page count meaningfully
and should not be sold as length work.

---

## 9. Summary

| tier | what | body source w | pages saved | running total |
|---|---|---|---|---|
| — | as it stands | — | — | **24.0** |
| 1 | revision history, meta-commentary, process detail | 410 | 0.44 | **23.6** |
| 2 | phase-49 candidates, RH6 reworded | 384 | 0.41 | **23.2** |
| 3 | move RQ2 detail, RQ3, RQ4, threats and three tables to the supplementary; halve related work; trim the protocol | ~9 900 | ~10.5 | **~12.7** |

**Twelve pages is not achievable without moving results to the supplementary.**
Tiers 1 and 2 together are 0.85 pages — 7% of the gap. The audit is right that
the prose problems are real, and they are a quality argument, not a length one.

**Nothing in this session changed the manuscript, the code, the data or the
gates.**
