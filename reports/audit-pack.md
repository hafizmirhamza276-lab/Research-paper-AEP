# Audit pack

**For an independent auditor with no prior knowledge of this project.**

**This is a map, not a defence.** It tells you what the paper claims, where
each claim's evidence lives, what machinery checks what, and what is open. It
does not argue that the paper is correct, and §8 is a list of the places I
expect a reviewer to push hardest — written by the same process that produced
the work, which is a limitation of §8 you should weight accordingly.

**Nothing here is a substitute for reading `paper/main.pdf`.** Where this
document and the repository disagree, the repository wins.

**This pack was itself audited, and it lost.** An external auditor
(`reports/external-audit-2026-09-23.md` §7) found nine claims here untrue,
inaccurate or unconfirmed; `reports/audit-response-2026-09-23.md` §4 checked
them finding by finding and conceded every one that could be checked without a
network. Seven corrections were applied on 2026-09-24 and are recorded, with
their evidence and the commands to recheck them, in
`reports/audit-pack-corrections-2026-09-24.md`. Two of them needed work outside
this file and have their own reports:
`reports/prereg-order-phase40-2026-09-24.md` (the failing gate) and
`reports/tse-venue-2026-09-24.md` (the review model and the page limit). **One
correction could not be made here at all** — `\WriteLossAepApplied`'s provenance
path is wrong in the *generated* output, not in this pack, and the fix is in
`scripts/paper_tables.py`; see §2.1. Read this paragraph as the pack's own
answer to its own standard: the repository won, in seven places.

| | |
|---|---|
| state | builds green; **gates NOT all green** — `check_prereg_order.py` exits 1 with four failing cells (§3, and `reports/prereg-order-phase40-2026-09-24.md`); **not submitted anywhere** |
| target venue | IEEE Transactions on Software Engineering — **single-anonymous**. TSE does not offer double-anonymous review (`reports/tse-venue-2026-09-24.md`). The anonymous builds and `prove_anonymous_gate.sh` are built for a review model this journal does not run |
| length budget | TSE's regular-paper limit is **12 formatted pages**, with a mandatory overlength charge of **$220 per page** beyond it. The main body is 24 |
| main | **24 pages** · main-anon 24 · supplementary **7 / 7** |
| suite | **2670 passed, 34 skipped** |
| submission blocker | the Zenodo deposit — §7.4 |

---

## 1. What the paper claims

### 1.1 Title

> **AEP: Declared Ambiguity for Non-Idempotent APIs Without Idempotency Keys**

Adopted 2026-09-23 (`reports/phase-report-51`). The protocol is named **AEP**
and **the acronym is deliberately not expanded** — see §5.3, because the reason
is a constraint and not a stylistic choice.

### 1.2 Abstract

250 words, at IEEE's limit with no margin. Its three moves:

1. **The problem.** Many enterprise APIs are non-idempotent, accept no
   idempotency key, and cannot be asked afterwards whether a mutation was
   applied. A caller crashing around such a call has no safe option.
2. **The protocol.** A fail-closed protocol: a durably acknowledged write-ahead
   intent before every external side effect; every state write fenced by lock
   ownership and an expected-version CAS in one atomic script; every
   unresolvable outcome escalates. Evaluated against five baseline designs
   under `SIGKILL`.
3. **The central result, which is a separation.** *Detection* — no undetected
   duplicate and no lost effect, leaving a residual of declared ambiguity —
   comes from the pre-dispatch record and a transition table, **not** from the
   durability barrier. *Prevention* is what the barrier contributes, against a
   narrower fault than it appears. Because detection does not depend on the
   barrier, its cost is a deployment choice.

### 1.3 Contributions C1–C4

`paper/sections/01-introduction.tex`, `\subsection{Contributions}`.

| | claim | where it is evidenced |
|---|---|---|
| **C1** | **The declared-ambiguity formulation.** The problem is a three-way trade, not an engineering-quality problem | Section 3 (model), `tab:trilemma` |
| **C2** | **A protocol and an implementation** | Sections 4 and 5 |
| **C3** | **An evaluation under real process kills** across six crash points, three capability classes and five baselines. *"AEP records no undetected duplicate and no lost effect **in any cell measured**"* | Section 6 |
| **C4** | **A decomposition of the mechanism, by ablation, that reassigns our own headline result.** The write-ahead pattern is two mechanisms, not one; ablating the barrier produces no observed difference in crashed-regime detection metrics | Section 6.3, `sec:eval-detection` |

**C4 is the claim to read first.** It says the paper's own earlier headline was
wrong about which mechanism delivered which guarantee.

**C3's scope condition — *"in any cell measured"* — is load-bearing**, and Section 1
now carries the same condition on the same claim (see §7.1, entry 1).

### 1.4 The four research questions, and where each is answered

| RQ | question | answered in | label |
|---|---|---|---|
| **RQ1** | Under crashes, does AEP eliminate *undetected* duplicates, and what is the shape of the residual? | Section 6.2 | `sec:eval-rq1` |
| **RQ2** | Which of the protocol's two durability mechanisms produces which guarantee? | Section 6.3 | `sec:eval-detection`, `sec:eval-prevention` |
| **RQ3** | What does the protocol cost, and how much of that cost is optional? | Section 6.4 | `sec:eval-rq3` |
| **RQ4** | How does recovery behave? | Section 6.5 **and** the supplementary's *RQ4: recovery* | `sec:eval-rq4`, `supp:rq4` |

**RQ4 was a stub forwarding to the supplementary until 2026-09-23** and is now
answered in the body as counts (`453a32b`). The supplementary carries the
argument in full. An auditor should check that the two agree.

---

## 2. The evidence chain

**The rule the project imposes on itself:** every numeric claim in the
manuscript carries a LaTeX comment naming the CSV cell or raw report section it
came from, and no number is typed by hand. `paper/main.tex:8-25` states it.

### 2.1 Macros → generated files

`paper/generated/` holds six files, all emitted by `scripts/paper_tables.py`,
none hand-edited:

| file | contents |
|---|---|
| `numbers.tex` | **221 macros** — every headline scalar |
| `table-outcomes.tex` | the trilemma table |
| `table-ablation.tex` | the barrier ablation |
| `table-latency.tex` | latency under both fsync policies |
| `table-ambiguity-by-crashpoint.tex` | declared ambiguity decomposed |
| `table-deployment-choice.tex` | the three deployment points |

**Each macro carries a generated provenance comment** naming the file, the
filter and the arithmetic. Example, from `numbers.tex`:

```
% ws4-writeloss-s1-2026-09-07/analysis/redis-kill-ablation.csv |
%   executions_with_an_applied_effect, AEP_FULL row
\newcommand{\WriteLossAepApplied}{285}
```

**Do not follow that path as written — it resolves nowhere, and this is a defect
in the generated provenance rather than in this pack.** Every other bare
directory prefix in `numbers.tex` (`ws5-2026-09-10`, `fsync-always`,
`fsync-always-2026-09-14`, `b2-paired-v2-*`, `phase13-armA-*`) resolves under
`experiments/results/`. This one does not: the tree exists **only** at
`reports/raw/ws4-writeloss-s1-2026-09-07`. Seven macros carry the truncated
prefix (`grep -c 'ws4-writeloss-s1-2026-09-07' paper/generated/numbers.tex`).
The cause is `writeloss_cell_macros()` at `scripts/paper_tables.py:625`, which
builds all seven comments from `root.name` — `Path.name` drops the parent,
though the full path is available (the `--writeloss-cell` default at
`scripts/paper_tables.py:3451`). The fix is `root.relative_to(ROOT).as_posix()`
plus a regeneration, and **it has not been applied**: it is a `paper/generated/`
rebuild. Details and the other emitters worth checking for the same bug:
`reports/audit-pack-corrections-2026-09-24.md` §3.

### 2.2 Generated files → collections

Distinct sources cited across `numbers.tex`, by frequency. **An earlier version
of this table undercounted by an order of magnitude** — it said
`per-cell-metrics.csv` supplied 3 macros where it supplies 56 provenance lines —
because it was built from a regex for the literal string
`analysis/per-cell-metrics.csv`, and most provenance comments write the basename
bare. Rebuilt 2026-09-24 at `44cb5d1`.

**How to recheck column (a):** one command per row.

```
grep -c -- "per-cell-metrics.csv" paper/generated/numbers.tex     # -> 56
```

That counts every line of the file naming that basename. **Column (b)** counts
*macros*: walk the file, accumulate consecutive `%` lines into a block, and when
a `\newcommand` is reached attribute it to each distinct basename named in its
block.

| source | (a) provenance lines | (b) macros |
|---|---|---|
| `per-cell-metrics.csv` — the rate source | **56** | 55 |
| `redis-kill-ablation.csv` — the ablation | 41 | 40 |
| `comparisons-vs-aep-full.csv` | 20 | 19 |
| `e1-kill-latency-by-run.csv` | 19 | 19 |
| `per-execution.csv` | 11 | 11 |
| `phase13-model-gap.json` | 10 | 10 |
| `latency-and-throughput.csv` | 9 | 8 |
| `g2-flakey-write-loss*.json` | 9 | 8 |
| `coverage.json` | 7 | 7 |
| `phase13-fault-landing.json` | 5 | 5 |

**Three facts that reconcile the two columns**, and that an auditor should check
before trusting either:

1. `numbers.tex` defines **221** macros (`grep -c 'newcommand'`). **182** name a
   source in their comment block — the sum of column (b) — and **39** are
   derived from other macros and name no file.
2. **No comment block names two different sources** (checked; the count is 0),
   so column (b) double-counts nothing.
3. Column (a) exceeds column (b) by exactly **1** for five rows and by **0** for
   the other five. The five are precisely the files listed in `numbers.tex`'s own
   5-line header banner. That banner line is the entire discrepancy.

**Which collection each source belongs to** is a second axis this table
deliberately does not mix in, because mixing them is what produced the original
error. Attributing full paths rather than basenames gives, largest first:
`reports/raw/e1-kill-latency-by-run.csv` 19,
`b2-paired-v2-*/analysis/redis-kill-ablation.csv` 12,
`ws5-2026-09-10/t1-p0-everysec/analysis/per-execution.csv` 9,
`ws4-writeloss-s1-2026-09-07/analysis/redis-kill-ablation.csv` 5.

The main matrix is **432 runs / 3 780 executions / 126 cells**
(`\RunsCollected`, `\ExecutionsCollected`, `\CellsCollected`).

**Two bans the project enforces on itself:**

1. **`analysis/table-1.csv` is never read.** It pools fault regimes and
   response classes, so its rates are a property of the collected mix.
   `check_no_banned_source` enforces it.
2. **Regimes are never pooled.** Every rollup filters to one regime and names
   it in the emitted comment.

**An auditor should know that the second rule was violated once and caught by a
review conducted in a separate session against the tracked CSVs**, not by the
gates — see §8.2.

### 2.3 Raw evidence

Two archives under one DOI, **2 790 run directories / 44 794 files**, 848 MB
uncompressed. Every file carries a SHA-256 in its archive's manifest; the
manifest's own digest attests the archive. Section 8 describes it.

**The DOI is `RESERVED` and does not resolve.** §7.4.

### 2.4 How `check_paper_numbers.py` verifies it

It re-reads the CSVs and recomputes. **43 checks, 0 failing.** The twelve
check functions:

| function | what it enforces |
|---|---|
| `check_generated_tables` | every generated table matches a fresh derivation from the CSVs |
| `check_no_banned_source` | `table-1.csv` is not a source for any number |
| `check_macros_are_used` | **a generated number that is defined and never used is a failure** — the drift a framing revision produces, which LaTeX is silent about |
| `check_generated_captions_use_macros` | a caption's numbers come from macros, not literals |
| `check_cross_document_references` | main and supplementary are two documents; neither `\cref`s the other's labels, and a *copied* block cannot go stale silently |
| `check_per_cell_has_regime` | every per-cell row names its regime |
| `check_state_machine` | the figure is generated from the implementation's transition set |
| `check_anonymous_build` | the anonymous PDF leaks no byline, path or DocInfo |
| `check_supplementary` | the supplementary is not stale, and declares a bibliography if it cites |
| `check_bibliography` | entries exist, none empty, BibTeX reported no parse error |
| `check_undefined_references` | no undefined reference or citation — **treated as a build failure, not a warning** |
| `check_todos` | no `\todoitem` marker survives |

**What it does not do:** it verifies that numbers match their sources. It does
not verify that the *source was the right one to use*, and §8.2 is an instance
where it was not.

---

## 3. The gates

| gate | what it enforces | how it proves it can fail |
|---|---|---|
| `check_paper_numbers.py` | §2.4 | 43 named checks, each reported |
| `check_no_repo_paths.py` | no repository path reaches the **rendered** text; reads the four PDFs | `tests/test_no_repo_paths.py` known-positives |
| `check_american_spelling.py` | no British spelling reaches rendered text; reads the PDFs; exempts the references section and a documented identifier list | `--selftest`, **6 of 6**, plus **77 tests** |
| `prove_anonymous_gate.sh` | the four anonymity checks **by inducing each failure and restoring** | it is itself the proof |
| `check_line_endings.py` | evidence files under SHA-256 manifests do not have their bytes moved |  |
| `check_prereg_order.py` | a pre-registration is committed before the collection it governs | **exits 1 at `44cb5d1`**: `cells: 35 ok: 27 exempt: 4 failing: 4`. The four are the phase-40 roots under `reports/raw/`, each *"tracked collection with no entry in EXPECTED"*. They **were** pre-registered — `prompts/phase-40-agent-reachability.md`, committed 2026-09-17, precedes all four — so this is a gate-table omission, not a missing pre-registration. Diagnosis and the exact entry each root needs: `reports/prereg-order-phase40-2026-09-24.md`. **Not fixed** |
| `check_pytest_gates.py` | no test in the suite is silently skipped |  |
| `check_tla_transitions.py` | the formal model's transitions match the implementation |  |
| `verify_refs.py` | every bibliography entry was resolved against DBLP, `doi.org`, or fetched on a recorded date |  |
| `verify_raw_archive.py` / `verify_published_archive.py` | the deposit's manifests verify file-by-file |  |
| `check_planner_cost.py` | the agent experiment's spend cap |  |
| `build_paper.sh` | compiles in a scratch directory and **promotes only a clean build**, so a failing check leaves the previous PDF byte-identical |  |

**`prove_anonymous_gate.sh` has a hazard worth knowing.** Its staleness fixture
is `paper/sections/08-threats.tex`: it appends to that file and restores with
`git checkout --`. Running it with uncommitted edits to that file destroys
them. It happened once (`reports/phase-report-49` §7).

---

## 4. The pre-registration and its amendments

`prompts/phase-40-agent-reachability.md` pre-registered an experiment testing
whether the protocol's failure modes are reachable with a **real LLM caller**.
Nine amendments, in order. Each is a separate committed file; none is a
retroactive edit of the original.

| # | title | what it changed, and why |
|---|---|---|
| **1** | the deployment reports an alias, not a snapshot | `response.model` returns an alias with no version, so `SnapshotMismatch` was unraisable. **The check was removed rather than made to pass**, and a test now asserts the ARM-read snapshot and the served model differ |
| **2** | the first prompt stated no task | The prompt described a tool, a target and a turn number but never a payment; the model correctly declined. **Kept in the record as a null stage** rather than rewritten |
| **3** | a turn is one independent payment | Turn semantics were ambiguous; an agent computed a difference and stopped early believing it had over-captured. Its two declared ambiguities are **not a result** (n=1, confounded) |
| **4** | the loop observes an outcome, and the cap is re-derived | `agent_worker_items` asked for all turns *then* executed, so no observation existed at decision time. Added a third branch; the scripted branch is unchanged by construction |
| **5** | C4 failed twice, the stop rule was armed, and the author overrode it | The cost criterion compared a measured mean against a ceiling written with `≤`, making the ±20 % band unreachable by a healthy stage. **Recorded as an override, not as a pass** |
| **6** | the re-decision concerns the same payment, and the agent owns it | Made the re-dispatch offer neutral and two-option |
| **7** | clause 1 cannot be met, and is withdrawn | **Withdrawn rather than weakened** |
| **8** | paired seeding, so both arms meet the same conditions | |
| **9** | a caller-visible outcome begins at transmission | |

**Also withdrawn during implementation:** the `rejected` value of
`last_outcome`, because it was reachable on only one arm — the mock provider's
refusal fault is a 503, and the only 4xx are on read-back routes `B0_NAIVE_RETRY`
never calls. It would have let the agent tell which arm it was in.

**The standing constraint the auditor should check amendments against:**
nothing in `last_outcome` may reveal which arm the agent is in, because an
agent that can tell AEP from B0 stops being a fixed caller and becomes a second
uncontrolled variable.

---

## 5. The phase-40 closure

`prompts/phase-40-closure-2026-09-22.md` and
`reports/phase-report-40-closure-2026-09-22.md`.

### 5.1 What happened

**Closed by author decision at stage 100's first failure, with none of the
three stop conditions met** — spend USD 0.00775720 against a USD 10 threshold,
one criterion failure against a two-failure rule, and 23 days left on the date.
The closure says so explicitly, because *"a workstream abandoned because a rule
fired and one abandoned because the author chose to stop are different facts
about a project."*

**The result that did not vary:** across stages 30 and 100, on both arms, the
agent was offered the re-dispatch **12 times and declined 12 times**.

### 5.2 What the manuscript may and may not say

The closure report §3.2 rules on four forms of mention. **This is the section
an auditor should hold the manuscript against.**

| form | permitted? |
|---|---|
| **A result** — any count from the collection, in prose, a table or a macro | **FORBIDDEN**, three independent grounds |
| **A threats note about phase 40** | **FORBIDDEN** — it would depend on the collection |
| **A threats note about the caller being scripted**, not referencing phase 40 | **PERMITTED, and already present twice** — `02-motivating.tex:9`, `08-threats.tex:284` |
| **A future-work sentence** | **Permitted in principle, NOT RECOMMENDED, and not written.** Phase 40 *did* place a real LLM in the caller position, so a sentence implying the question is untouched would be false by omission — and the only accurate version states a result the first row forbids. **The two constraints have no overlap** |
| **An artifact pointer to the raw phase-40 data** | **FORBIDDEN as a manuscript sentence, and unnecessary** — `reports/raw/phase40-*` is in the repository |

**Net: no manuscript text mentions phase 40 in any form, and none is owed.**
The prose was gated on stage 300 passing; stage 300 never passed; so there is
nothing to retract.

**Verify this yourself, and note the one hit you will get.**

* `grep -ri "phase 40\|phase-40\|language model" paper/` — **nothing.**
* `grep -ri "LLM" paper/` — **three hits, all the same cited title**:
  *"Verified Tool Calls Improve LLM Agent Reliability Under…"* in `refs.bib`
  and the two generated `.bbl` files. **It is somebody else's paper's name in
  the bibliography, not the manuscript's own prose.**
* `grep -ric "agent" paper/*.tex paper/sections/*.tex` — 10 lines across
  `main.tex` (2), `01-introduction` (2), `02-motivating` (2) and `07-related`
  (4). Each is audited individually in the closure report §3.4 and each is a
  *motivating context*, a *scenario*, an *index term* or a description of
  somebody else's system — not a result. `supplementary.tex` has none, and so
  does every file under `paper/generated/`, which is the tree the
  pre-registration names first.

### 5.3 Why the acronym is not expanded

The artifact is called *Agent Execution Protocol* (`README.md:1`,
`pyproject.toml:8`). **The manuscript does not use that expansion**, and
reinstating it was declined 2026-09-23 on three grounds:

1. It makes agents the *subject*, which `docs/33` §0's 2026-09-04 banner says
   they are not — they are the motivating deployment context.
2. It contradicts `02-motivating.tex:9`: *"It is a scripted caller, not an
   agent."*
3. **Nothing agent-shaped was evaluated**, so the name would be the strongest
   agent claim in the paper and the only unevidenced one.

**The artifact's own metadata still carries the old framing** and is on the
camera-ready checklist, not fixed — §7.5.

---

## 6. Structure, and one thing that changed today

Section order, as rendered:

I Introduction · II Motivating Traces · III System and Failure Model ·
IV The AEP Protocol · V Implementation · VI Evaluation · VII Related Work ·
**VIII Artifact Availability** · **IX Threats to Validity** · Acknowledgment ·
References

**Artifact Availability and Threats to Validity were swapped on 2026-09-23** so
the last numbered section ends on an argument rather than a URL. The file names
keep their original numbers — `08-threats.tex` renders as **Section 9**, and
Artifact Availability renders as **Section 8**. Section references in this pack
were Roman numerals until 2026-09-24 and are now the Arabic numerals the
compsoc build actually prints; each was resolved against what the sentence is
about, because both numerals had been used for both sections.

**There is no conclusion section.** That is a decision, not an oversight —
§7.6.

---

## 7. Every open item

### 7.1 `reports/claims-to-review.md`

| # | entry | status |
|---|---|---|
| 1 | Section 1 said the uncertainty is *never* in the accounts; C3 scopes the same claim | **RESOLVED** — empirical reading taken, Section 1 now carries C3's scope condition |
| 2 | the supplementary said *every* crashed execution reached a terminal classification; 180 did not | **RESOLVED** — scoped to executions that wrote an intent |
| 3 | `voided/` renders in Section 9 after the path was removed from the supplementary | **REOPENED 2026-09-24.** It was closed on the directory's existence — `voided/` is a real directory with 24 manifest entries, and that half is verified. But the sentence says the run is in the **published** archive, and `\archivedoistate` is `RESERVED`, so it is false at submission. Closes when the deposit is published, or by rewording |
| 4 | the supplementary points a reader at "the supplementary material", and two of its sections answer the same question | **HALF RESOLVED.** The self-reference is fixed (`\Cref{supp:provable}`). **Whether the two sections merge is open** |

**Entry 1 is worth your attention even though it is closed.** The data was
clean — `lost_effect_rate` and `undetected_duplicate_rate` are both 0/300 in
the write-loss regime. It was scoped because in that regime AEP dispatched on
an acknowledgement that was false, so the durability of the record was never
established. **The scope condition records a limit of the instrument, not a
failure in the result** — and you may disagree that the distinction is
adequately conveyed to a reader.

### 7.2 Deferred to the length pass

`PAPER_ROADMAP.md`, the *DEFERRED TO THE LENGTH PASS* section: **L1** the
conclusion (draft exists, §7.6), **L2** entry 4's merge question, **L3** 569
words of Section 7 / Section 9 cut candidates with the assessment that none
should be cut,
**L4** Section 6 at ~6 500 words and Section 9 at ~3 200.

### 7.3 Cut candidates — 569 words, none applied

`reports/phase-report-49` §6 lists eight with word counts. **Three of them (5,
6, 7) are the threat-side counterparts of results stated in Section 6** — which is
simultaneously the argument against cutting them and the evidence that Section 6
and Section 9 duplicate.

### 7.4 The Zenodo deposit — the submission blocker

`main.tex:145` is `\archivedoistate{RESERVED}`. A reserved DOI is minted but
does not resolve until published.

**What the PDF actually says**, verbatim from `pdftotext -layout paper/main.pdf`,
Section 8:

> "those are carried by a separate archive, prepared and verified, with the
> Zenodo record reserved under DOI 10.5281/zenodo.22766567; the identifier is
> fixed and begins resolving when the record is published."

An earlier version of this pack said `\archiveavail` renders *"not yet
deposited"*. **It does not.** That text is the **PENDING** branch
(`main.tex:232`); `RESERVED` selects the branch at `:238`. The string "not yet
deposited" appears in **none** of the four built PDFs. The anonymous build
renders a third sentence again, from `main.tex:158`: *"those are carried by a
separate archive, available via the submission system."*

The substantive point is unchanged and is the reason this is the blocker: **a
reviewer cannot verify the evidence.** Procedure: `docs/29-archive-deposit.md`,
one record, six files, manual web upload. Inserting the real DOI is a one-line
edit.

**One consequence worth carrying to Section 9.** While the deposit is
`RESERVED`, `sections/08-threats.tex:223-227` — the voided run *"is in the
**published** archive under `voided/`"* — is false as printed. Publishing the
deposit makes it true with no text change. `reports/claims-to-review.md` entry 3
is reopened on exactly this.

### 7.5 `reports/camera-ready-checklist.md`

Things that must be fixed before camera-ready: the artifact's *"for agents"*
description and its *Agent Execution Protocol* heading; the author identity,
ORCID and artifact URLs; the stale-title records in `docs/`; and the deposit.

**That list was assembled under the heading "things invisible to a
double-anonymous reviewer", and that framing is wrong.** TSE runs
single-anonymous review (`reports/tse-venue-2026-09-24.md`), so the submitted
article is the **named** build and the author identity, ORCID and artifact URLs
are visible to reviewers from the first day. The items still need fixing; the
reason they were safe to defer does not hold, and the artifact URL in particular
is now something a reviewer can and will follow.

### 7.6 The conclusion — declined, with the draft kept

Investigated 2026-09-23. **No IEEE or TSE guidance in the repository requires
one.** The recommendation was to add ~200 words; **the author declined**, on
the objection raised against that recommendation: the paper already states
results in full in both Section 6 and Section 9, and a conclusion would be a third
statement. A ~215-word draft is at `reports/phase-report-52` §2.6. The ordering
half was applied separately (§6).

### 7.7 `reports/known-flakes.md` — one open flake

`test_sigkill_with_concurrent_writers_loses_nothing` failed once in a full
suite run on 2026-09-23. Not reproduced: 5/5 in isolation, and a full re-run
passed. Nothing in that session touched its code path. **The failing assertion
was not captured**, so the cause is not narrowed — and one of the three
candidates is a genuinely lost increment, which is the defect the test exists
to catch. Not fixed, on instruction.

---

## 8. Known weak points

**Written by the process that produced the work.** Treat it as a starting list,
not a complete one.

### 8.1 The detection finding has no referent outside this artifact

Section 9 says it plainly: *"the proposition is supported by two systems we wrote,
measured by a harness we wrote, against a provider we wrote."* The central
result — that detection comes from the record and not the barrier — rests
entirely on an artifact built by the author. **Nothing external corroborates
it.**

### 8.2 An own-rule violation was found by a review, not by the gates

`reports/paper-review-2026-08-11.md` found that the headline significance test
pooled fault regimes — *the exact practice Section 6.2(e) bans*. Recomputed on
crashed-only counts the conclusion survived (p = 1.15 × 10⁻¹⁸³). The same
review found the one-sided/two-sided Wilson bound mislabelled.

**Both were corrected. The point for an auditor is that the gates did not catch
either**, because `check_paper_numbers` verifies a number against its source
and not the choice of source.

**An earlier version of this pack called that review "an external reviewer". It
should not have, and the claim is withdrawn.** Nothing in the repository
establishes who or what wrote it. The review names no person and no affiliation,
and its own environment note (`reports/paper-review-2026-08-11.md:9`) describes
*"a container … Python 3.12 + `uv 0.11.7`, no Docker, and outbound network
limited to package registries and web search"* — a description consistent with
an agent sandbox. What **is** documented, in the review's own *Review protocol*
section, is the property the finding actually rests on: it was written in a
separate session, stage 1 blind to everything under `reports/`, from
`paper/main.pdf`, `ARTIFACT.md` and the public tree, with every computation run
against the tracked CSVs in its own clone. That is what this pack now claims for
it, and no more. Raised by the external audit; see
`reports/audit-pack-corrections-2026-09-24.md` §6.

### 8.3 Prevention is measured far more narrowly than detection

The external review put it at **1/126th** of detection's breadth. Section 9
carries the scope; the abstract and Section 1 are where a reader is most likely
to take the
two as equally supported.

### 8.4 Two comparisons fail to exclude zero for reasons of precision

The kill-latency attribution (half-width wider than the mean it brackets) and
the capability-class sweep, where **the applied-effect column moved,
contradicting the authors' own registered prediction**, while the interval
still contains zero because the sessions disagree with one another. Section 9 says
the weaker reading is not available. **A reviewer may reasonably read these as
underpowered rather than as informative nulls.**

### 8.5 Everything was measured on one host, under WSL2

`docs/27-measurement-host.md`. Section 9.3 proposes re-collecting one frozen
cell on bare metal to price the platform term. **Not done.** Every effect
size's dependence on host timing is measured *on* that host rather than
established *across* hosts.

### 8.6 The write-loss result refuted the paper's own prediction

`WAITAOF` returned success for every durability acknowledgement requested after
the device stopped accepting writes. The barrier was handed a successful
acknowledgement that was false, and dispatched. The paper reports this as a
refutation rather than a caveat — **and it bounds the durability guarantee to
storage that reports its own failures**, which is a narrower claim than the
abstract's *prevention* sentence may suggest on first reading.

### 8.7 The length problem is not cosmetic

24 pages against TSE's 12-page charge point, with acknowledged duplication
between Section 6 and Section 9. A reviewer who asks for cuts will be asking
the authors to choose between two statements of the same result, and that
choice has not been made.

**The charge point is now confirmed and priced.** IEEE Computer Society's author
guidance sets the regular-paper limit at 12 formatted pages and charges $220 for
each page beyond it; the 2026 IEEE APC list's TSE row says the same
(`reports/tse-venue-2026-09-24.md` §2). The charge is a Mandatory Overlength
Page Charge assessed on the **final formatted** article after acceptance, not a
desk return — so the length problem is not a rejection risk so much as a bill of
roughly $2,640 on the current page count, and an editor's discretion on top of
it. That makes §7.2's deferred length pass the most expensive open item in this
pack.

### 8.8 One statistical practice worth checking independently

Bootstrap intervals are cluster-aware over runs; Wilson intervals appear on
pooled counts; Bonferroni is applied for two simultaneous bounds at ≥ 90 %
joint coverage. The supplementary's `tab:trilemma` caption notes that the
per-class cells are **not** separately bounded, and that at that scope the
width would be `\AblationZeroUpperPerClass` points. **The distinction between
"no observed difference per class" and "bounded per class" is carried in a
caption**, and a reader who skips captions may miss it.

### 8.9 A generated caption escaped a manuscript-wide pass, once

The American-spelling pass over the `.tex` files missed *organised* in
`paper/generated/table-outcomes.tex`, whose caption is a string literal in
`scripts/paper_tables.py`. The PDF-based check found it. **Assume other
manuscript-wide passes have the same blind spot** unless they read the PDFs.

---

## 9. How to verify the state yourself

```
bash scripts/build_paper.sh --supplementary
bash scripts/build_paper.sh --supplementary --anonymous
bash scripts/build_paper.sh --anonymous
bash scripts/build_paper.sh
python scripts/check_paper_numbers.py
python scripts/check_no_repo_paths.py
python scripts/check_american_spelling.py
python scripts/check_american_spelling.py --selftest
python scripts/render_arxiv_abstract.py --check
bash scripts/prove_anonymous_gate.sh
python -m pytest -q
```

**Build the supplementaries first.** `build_paper.sh` treats `main.tex` as a
source for the supplementary staleness check, so touching it invalidates all
four builds.

**Commit `paper/sections/08-threats.tex` before running the anonymity gate**,
or run the gate first (§3).

Expected: **7 / 7 / 24 / 24** pages, `43 passed / 0 failed`, `4 builds clean`
three times, `3 ok / 0 failed`, gate green with the tree restored clean, and
**2670 passed, 34 skipped**.
