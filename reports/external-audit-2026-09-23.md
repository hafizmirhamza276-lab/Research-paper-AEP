# External audit — 2026-09-23

**Manuscript:** *AEP: Declared Ambiguity for Non-Idempotent APIs Without Idempotency Keys* (`paper/main.pdf`, 24 pp.; `paper/supplementary.pdf`, 7 pp.)
**Repository state audited:** commit `3b55fc5` ("reports: the suite is 2670 after the reorder, and the flake did not recur").
**Auditor:** no prior involvement. The audit pack (`reports/audit-pack.md`) was used as a map, not as evidence.
**Nothing in the repository was edited.** This file is the only addition. Running the build created ignored directories (`.venv/`, `.scratch/`, `__pycache__/`); `git status` shows no tracked file changed.

Page numbers refer to `paper/main.pdf` (named build) unless marked "supp". The anonymous build has the same 24 pages, with slightly different line breaks. Source locations are `file:line` under `paper/`.

Ranking:
- **Blocker:** must be resolved before submission.
- **Should-fix:** a competent reviewer will raise it, and it weakens the paper.
- **Minor:** polish.

---

## 0. Summary of blockers

**B1. The headline "detection does not depend on the barrier" is broader than the evidence, and the paper's own formal model contradicts it.**
- The claim appears in the abstract, §6.3.1, §9.2 and supp Table 4.
- The ablation was run only where no record can be lost, so its null result was guaranteed by the design.
- Configuration `b3-no-barrier-restart.cfg` (Table 6 row "The barrier, plus a restart") breaks *no lost effect*. That is one of the two properties the abstract defines as detection.

**B2. For the five baseline systems, the crash point `after_barrier_before_dispatch` is silently a second `mid_dispatch` cell.**
- The kill is delivered mid-transmission, not before dispatch.
- The paper's Table 3 says the opposite.
- This inflates the baseline rates in Table 7, Figure 2 and the "0.77–0.83" headline, and it drives the Temporal comparison.
- It is not disclosed anywhere in the manuscript.

**B3. The submission package rests on premises I could not confirm, and one is contradicted.**
- IEEE Computer Society author guidance lists TSE among the journals that do *not* offer double-anonymous review. The whole anonymized build may therefore be the wrong deliverable.
- The raw evidence is unreachable: the DOI is reserved and does not resolve.
- §9.2 states that a voided run "is in the published archive". That is false at submission.
- I could not establish TSE's page limit. At 24 pages, length is a live desk-reject risk.

---

## 1. Claims against evidence

### 1.1 What I recomputed from collected data

| Claim | Where | Recomputation | Result |
|---|---|---|---|
| Table 7, all 63 cells | p. 10 | `experiments/results/matrix/analysis/per-execution.csv`, regime `(session-3)` (relabelled "crashed" by `scripts/paper_tables.py:131`) | **Exact match** |
| AEP-full 0 undetected duplicates and 0 lost effects "in any cell measured" (C3) | `sections/01-introduction.tex:111` | Every `per-execution.csv` in the repository that contains AEP-full (28 files, regimes crashed/p0/p30/redis-kill-preack/redis-kill-inflight/write-loss-preack) | **True in every file** |
| Weakest baseline-vs-AEP Fisher p = 5.4×10⁻¹⁸² | p. 9 | B2 357/450 vs 0/540 → 5.39×10⁻¹⁸²; B0 1.15×10⁻¹⁸³; B1 1.6×10⁻¹⁹⁰ | **Match** |
| Controlled Redis kill: AEP 3/269, B3 264/270, spread ≤ 1 per class | p. 12 | `phase13-armA-s{1,2,3}-2026-09-03` | **Match** |
| Uncontrolled cell 10/30 vs 28/30, p = 1.9×10⁻⁶ | p. 12 | Fisher two-sided | **Match** |
| Session-level prevention 17.2 [6.1, 28.4] | p. 13, p. 20 | `b2-*/analysis/redis-kill-ablation.csv` differences 8, 16, 24, 21; t(3) interval | **Match** (6.12, 28.38) |
| Kill-latency attribution +105 [-91, +302] | p. 20 | +70, -4, +282, +74; t(3) | **Match** |
| Barrier cost 1,939.7 ms [1,855.8, 1,962.4] (15 runs) | p. 14 | `ws5-2026-09-10/t1-p0-everysec`, run-cluster bootstrap, seed 20260806 | **Match** (1,939.7; [1,854.9, 1,962.6]) |
| Barrier under `always` -9.2 ms | p. 15 | `fsync-always-2026-09-14` per-execution medians give 2,080.2 − 2,089.0 = **-8.8** | Small discrepancy, probably a different median source; immaterial |
| Write-loss cell AEP 285/300, B3 287/300 applied, 0 dup, 0 lost | p. 14 | `reports/raw/ws4-writeloss-s1-2026-09-07/analysis/redis-kill-ablation.csv` | **Match** |
| Wilson one-sided 95% bound 4.77% on 0/54; 20.1 pp for 6 bounds over 18 clusters | p. 11, p. 10 | z²/(n+z²) | **Match** |
| Supp Table 1 sums to 63/180 and 130/180 | supp p. 2 | arithmetic | **Match** |
| Temporal (B5) 93/590 dup, 84/590 lost, 0 ambiguity | p. 9 | `reports/raw/ws6-b5-s1-2026-09-08-attempt3/b5-runs.jsonl` | **Match** |
| `numbers.tex` and all generated tables re-derive from the CSVs | — | `python scripts/check_paper_numbers.py` | **39 passed, 2 failed**. Both failures are "main.bbl/main.log exists", because my LaTeX install lacks `IEEEtran.cls` and the build could not run. Not an author defect |

The numbers are faithful to their sources. The problems below are about **what the sources measure** and **which source was chosen**, not about transcription.

### 1.2 Blocker B1 — detection vs. the barrier

**What the paper says:**
- Abstract, `main.tex:286-293` (p. 1): *"Detection (no undetected duplicate and no lost effect, …) comes from the pre-dispatch record and a transition table …, not from the durability barrier. … Because detection does not depend on the barrier, its cost is a deployment choice, not the protocol's price."*
- §6.3.1, `sections/06-evaluation.tex:393` (p. 12): *"Durability is neither necessary nor sufficient for detection."*
- §9.2, `sections/08-threats.tex:151` (p. 20): *"the ablation says which half delivers which, including that the expensive half is optional."*
- Supp Table 4 caption, `generated/table-deployment-choice.tex:13` (supp p. 5): *"All three rows run the same pre-dispatch intent ledger and therefore make the same detection claim."* This includes B3-mode.

**What the evidence covers.** The B3/AEP ablation on detection metrics ran only in the crashed regime. That regime is a worker SIGKILL with Redis alive. The paper itself says (p. 12) *"no worker-crash fault can exercise it [the barrier], which is why Section 6.3.1 returns a null."* The null is therefore a consequence of the design, not an empirical reassignment of the mechanism.

**What the authors' own model says.**
- `formal/configs/b3-no-barrier.cfg` (EXPECT: pass) carries the comment: *"the barrier does not defend the state machine -- it defends the record's existence, and nothing here destroys records."*
- `formal/configs/b3-no-barrier-restart.cfg` is `EXPECT: fail NoLostEffect`, with the comment *"This is the pairing that gives the barrier its purpose."*
- Table 6 (`sections/04-protocol.tex:276`, p. 7) prints this as *"The barrier, plus a restart | no lost effect | 8"*. The text discusses two other rows of Table 6 and never this one.

*No lost effect* is half of the abstract's own definition of detection. Under the fault class the paper identifies in §6.3.3 as the one that really loses unfsynced writes (host-level page-cache loss followed by a Redis restart), detection **does** depend on the barrier.

**The write-loss cell does not rescue the claim.** Redis was never restarted inside that cell. The README reports that no `coordinator_restarted_unexpectedly` fired. The in-memory record therefore served recovery, and the 0 lost / 0 dup there cannot test record loss. `write-loss-no-restart.cfg` says exactly this: *"the lie costs nothing until the moment it costs everything."*

**What would answer it:**
- Scope every detection-without-barrier statement to "faults that do not destroy the record (worker crash; Redis process kill with the page cache intact)".
- Discuss the Table 6 restart row in the text.
- Either run B3 under host-level loss *with* a restart, or state that detection under that fault is untested empirically and fails in the model.
- Remove "Durability is neither necessary nor sufficient for detection".

C4 as worded in §1.2 (`sections/01-introduction.tex`, "in the crashed-regime detection metrics") is correctly scoped. The abstract, §6.3.1, §9.2 and supp §7 drop that scope.

### 1.3 Blocker B2 — baseline crash points are not the positions Table 3 describes

**Mechanism, verified in code:**
- `experiments/baselines/crash_points.py` maps both `after_barrier_before_dispatch` and `mid_dispatch` to `BaselineCrashPoint.BEFORE_REQUEST_TRANSMISSION`. This applies to both B0–B2 and B4/B4b.
- `DEFERRED_BASELINE_POINTS = {BEFORE_REQUEST_TRANSMISSION}`.
- `experiments/harness/injector.py` (`from_environment`) selects `SIGKILL_DEFERRED` for any point in the deferred set unless `AEP_HARNESS_CRASH_STYLE` is set. That is a watchdog kill during the socket wait, 0.4 s after arming.
- `run_matrix.py` and the matrix config never set a crash style (grep finds no setter).
- The module docstring claims the opposite: *"Serves both `after_barrier_before_dispatch` (delivered immediately: the mutation provably was not sent) and `mid_dispatch`."*

**Data, crashed regime, `after_barrier_before_dispatch`:**

| System | undetected dup | mean applied effects | note |
|---|---|---|---|
| AEP-full | 0.000 | **0.000** | kill lands before dispatch, as Table 3 says |
| B0 | 0.933 | 2.14 | |
| B4 | 0.967 | 2.22 | |
| B4b | 0.000 (lost 0.911) | 0.91 | `dispatch_attempts = 0` in 90/90, yet an applied effect in 82/90 |

For every baseline, this cell is statistically indistinguishable from its `mid_dispatch` cell. Table 3 (`sections/03-model.tex:133`, p. 4) says of this crash point: *"record durable; **no effect**"*.

**Effect on reported numbers** (my recomputation, dropping the mis-mapped cell):
- B0 AUTH duplicates go from 0.8200 to 0.7833.
- B4 duplicates go from 0.53–0.59 to about 0.45 (AUTH 0.4467).
- B4b lost effects go from 0.51–0.54 to about 0.43 (POS-ONLY 0.4267).

The direction of every comparison survives. The magnitudes in Table 7 (p. 10), Figure 2 (p. 11), the "0.77–0.83" statement (`sections/02-motivating.tex:29`, p. 2; `sections/06-evaluation.tex:112`, p. 9) and Table 7's caption (*"Every execution in every cell was killed at one of the six crash points of Table 3"*) are not like-for-like across systems.

**What would answer it:**
- Either re-collect the baseline `after_barrier_before_dispatch` cells with `SIGKILL_IMMEDIATE`, or drop them from the pooled baseline rates.
- In either case, state the mapping in §6.1 and correct the docstring.

### 1.4 Contribution by contribution

**C1 (formulation).** Conceptual. It is supported as an argument. The "each mapped to the code path" claim rests on a citation-range check that, as §3 of the paper itself says, proves ranges exist, not semantics. Not independently verified.

**C2 (protocol and implementation).** Honestly bounded: the guard is "not a cryptographic capability" (p. 2). I did not audit the guard code.

**C3 (evaluation):**
- The zero-duplicate / zero-lost claim is verified across every AEP collection (§1.1).
- Two scope problems:
  - (a) The baseline comparison is affected by B2.
  - (b) The write-loss and redis-kill cells contribute zeros that cannot fail by construction, because Redis never restarts after losing a record. "In any cell measured" is true, but a reader will take it as broader evidence than it is. The pack's §7.1 entry 1 concedes this. I agree with the pack that the manuscript does not convey it.

**C4 (decomposition).** See B1. The "reassigns our own headline result" framing (`sections/01-introduction.tex`, p. 2; p. 11) presents a design-guaranteed null as a finding.

### 1.5 Research question by research question

**RQ1.** Answered, subject to B2.
- **Should-fix:** "At `after_barrier_before_dispatch` it is at its maximum, and that is the crash point at which *no effect can possibly exist*" (`sections/06-evaluation.tex:245-246`, p. 10).
  - Supp Table 1 shows `after_intent_before_barrier` equal (30/30 on POS-ONLY and NONE).
  - Table 3 also marks that point "no effect".
  - `mid_dispatch` on NONE is 30/30 as well.
  - "Its maximum … exactly where" overstates uniqueness.

**RQ2.** Detection: see B1. Prevention: the controlled cell is sound as reported. The residual 3/269 and the one-host scope are stated.

**RQ3:**
- The ordering claim (barrier dominates) is supported by the 15-run data I recomputed.
- "Detection is nearly free" (`sections/01-introduction.tex:126`) rests on an interval of [-122.6, 120.1] ms. "Not distinguishable from zero; at most ~120 ms on a 2-s call" is the accurate form.
- See S3 and S4 for presentation errors in this RQ.

**RQ4.**
- "450 of 450 … resolved to a terminal classification" (p. 15) is close to tautological given P3's bounded budget, and no recovery latency is reported: 176 of 432 runs pass the timing gate, which is too few gated crashed runs for a distribution.
- A reviewer will say RQ4 is not answered in any sense beyond "the implementation terminates". **Should-fix:** either report the gated recovery-latency distribution with its n, or fold RQ4 into RQ1 and drop it as a question.

### 1.6 Places where the choice of source does the work

1. **The Temporal comparison (S1).** It puts a cell with one kill per 10-execution run against a cell in which every execution is killed mid-transmission.
2. **The statistical standard (S2).** A t-interval is used for the favorable 4-session result. A sign-test floor is used to declare the two unfavorable 4-session results "incapable" of rejecting.
3. **Latency (S3).** Three-run medians are used in Table 9 and supp Table 4, and 15-run figures in the prose. The table value falls outside the prose interval.

---

## 2. Internal consistency

| # | Location A | Location B | Contradiction | Rank |
|---|---|---|---|---|
| 1 | Abstract `main.tex:292`: "detection does not depend on the barrier" | Table 6 row "The barrier, plus a restart \| no lost effect" `sections/04-protocol.tex:276` | Own model breaks detection without the barrier (B1) | Blocker |
| 2 | Table 3 `sections/03-model.tex:133`: `after_barrier_before_dispatch` = "no effect" | Baseline data at that cell: effects applied, B4b applies with 0 recorded dispatches | B2 | Blocker |
| 3 | §8 p. 18: archive DOI "reserved … begins resolving when the record is published" | §9.2 `sections/08-threats.tex:227` p. 20: voided run "is in the published archive under voided/" | Archive is not published | Blocker (as part of B3) |
| 4 | §6.4 p. 14: barrier 1,939.7 ms [1,855.8, 1,962.4] | Table 9 p. 14: AEP 4,004.9 − B3 2,038.2 = **1,966.7**, outside that interval; supp Table 4 prints 1,966.7 | 3-run vs 15-run cells; Table 9 is not labelled as the earlier cells. §9.4 (`sections/08-threats.tex:333`) discloses this only for the supp table | Should-fix |
| 5 | §6.4 `sections/06-evaluation.tex:760` p. 15: supplementary gives "the three measured points … with the table they are read from", then quotes -9.2 ms | Supp Table 4 prints 15.0 ms for the barrier under `always` | Opposite sign; the quoted figure is not in the table it points to | Should-fix |
| 6 | Supp §7 `supplementary.tex:575-576`: "(B3 is 2,038.2 ms under everysec and 2,089.0 ms under always)" | First figure is a 3-run cell, second a 15-run cell (15-run everysec B3 is 2,075.2) | Mixed sources in one comparison | Should-fix |
| 7 | Table 7 caption, §7.2 `sections/07-related.tex:220`, supp p. 5: "both zero-event rates … joint coverage of at least 90%" | §6.3.1 `sections/06-evaluation.tex:364` derives ≥ 90% for **two** bounds (two systems, one metric) | Two metrics × two systems = four bounds → Bonferroni ≥ 80% | Should-fix |
| 8 | §9.4 `sections/08-threats.tex:339-350` p. 22: with four sessions "No effect size, however large, could have produced a rejection at α = 0.05" — "a theorem" | §6.3.2 p. 13 / §9.2 p. 20: [6.1, 28.4] from four sessions excludes zero; one-sample t p = 0.016 (my computation) | True only for the sign test; false for the t-analysis the paper actually reports | Should-fix |
| 9 | §6.2 `sections/06-evaluation.tex:161-162` p. 9: B4 "roughly six times the engine's rates. B4's rates are our model's, not the product's"; repeated `sections/07-related.tex:208` | Temporal cell: one kill per 10-execution run, synchronous before the call; B4 cell: every execution killed, mid-transmission | Not the same experiment (S1) | Should-fix |
| 10 | Supp Table 4 row "AEP-full, `always` … prevents: yes" | `fsync-always-2026-09-14` contains regime `p0` only | Prevention under `always` never measured (S4) | Should-fix |
| 11 | §1.2 C3 p. 2 and §6.1 `sections/06-evaluation.tex:54`: 30% regime "rates are not in these tables" / "no table here quotes its rates" | Supp §5 p. 4 quotes 30% rates in prose (B0 0.0044, B4 0.0044) | Literally consistent ("tables"), but the paper does report 30% rates | Minor |
| 12 | Supp §1 p. 1: "Sections appear in the order the main paper reaches them" | Supp §9 repeats supp §3's topic (the provably-empty cell) after RQ4 | Ordering claim false; duplicated section (the pack's open entry 4) | Minor |
| 13 | §6.2 p. 10: ambiguity at its maximum "exactly where no effect can possibly exist" | Supp Table 1: `after_intent_before_barrier` also 30/30 and also "no effect" (Table 3) | Uniqueness overstated | Minor |
| 14 | Supp §1 `supplementary.tex:92`: "for the reason recorded at the top of this file" | The reason is a LaTeX comment, invisible to readers | Leaked source reference | Minor |

**Abstract vs body.** Apart from B1, the abstract's prevention sentence ("not when storage discards writes while reporting success, which we injected and where it dispatched") is accurate and matches §6.3.4.

**§1 vs §6.** C3 matches §6.2. C4 matches §6.3.1 in wording but not in the scope §6.3.2 concedes.

**Main vs supplementary.** Items 4–7, 10 and 12 above.

**Captions.**
- Table 7's caption is accurate except for item 7 and its "every execution … killed at one of the six crash points of Table 3" (B2).
- Table 9's caption omits that its runs are the earlier 3-run cells.
- Supp Table 4's caption asserts the same detection claim for B3-mode (B1).

---

## 3. What a TSE reviewer would attack, by severity

1. **"Your central structural result is guaranteed by the experiment design."** (B1) The barrier cannot matter when nothing destroys the record, and the only fault that does destroy it was not combined with a restart. Your own Table 6 shows detection failing without the barrier.
   *Answer:* rescope, or run the missing cell (B3 and AEP-full under drop_writes plus a Redis restart after dispatch).

2. **"The baseline comparison is not like-for-like."** (B2) Once found in the artifact, this also undermines trust in Table 3.
   *Answer:* re-collect or exclude, and disclose.

3. **"Is the premise real?"** The paper offers no evidence that non-idempotent, keyless, non-queryable endpoints are common in agent deployments. §9.3 says "we have none". Combined with an agent-led introduction and an index term for agents, and nothing agent-shaped evaluated, a reviewer may read the framing as motivational only.
   *Answer:* a small field or documentation survey of real endpoints and their capability class, or de-emphasize agents.

4. **"Everything is self-built."** Protocol, five baselines, harness, mock provider and oracle are all by one author (§9.2 says so). The only external system (Temporal) is compared in a non-comparable cell (S1).
   *Answer:* fix S1, and run at least one baseline against a third-party endpoint or a second provider implementation.

5. **"Novelty."** §7 concedes write-ahead intent is Olive's and that the composition is not new. What remains is the capability-typed recovery table and the evaluation.
   *Answer:* sharpen the contribution statement around the capability classification and the declared-ambiguity outcome.

6. **Statistics.**
   - Post hoc ±5 pp equivalence margin (disclosed, p. 11).
   - The sign-test "theorem" (S2).
   - Bonferroni coverage (item 7).
   - Execution-level Fisher tests on clustered data (disclosed).
   - n = 3 runs per stratum.
   *Answer:* one consistent inferential standard across favorable and unfavorable results.

7. **Length and duplication.** At 24 pages, with §6 and §9 restating the same results, length could trigger a desk return. I could not confirm TSE's current limit.

8. **Single host under WSL2 with Docker Desktop** (§9.3). Every timing and race result is platform-bound. The re-collection the paper itself proposes (one frozen cell on bare metal, about an hour) was not done.

9. **Declared ambiguity is not evaluated as an operational outcome, and there is no alerting mechanism.** The paper states both (p. 11, p. 20). A reviewer will still ask why an unalerted pause is "operator-actionable".

**Desk-reject risks:**
- B3: review-model mismatch, unresolvable artifact, length.
- Submitting the anonymous build to a journal that runs single-anonymous review without the AI systems named (S7).

---

## 4. Honesty and disclosure

### 4.1 Limitations and negative results

To the paper's credit, these are reported as negative or refuting:
- the write-loss refutation (§6.3.4);
- the keying sensitivity miss, 9.33 pp against a 5 pp margin (p. 10);
- the prevention bound missed from below, reported "as a surprise rather than a success" (p. 12);
- B3 no longer being a negative control (p. 13);
- the unconfirmed ~30 ms protocol cost (p. 14);
- the capability-class sweep contradicting a registered prediction (supp p. 3);
- the post hoc ±5 pp margin (p. 11).

This is better than typical.

Softening that remains:
- **B1:** the barrier's detection role under record loss is absent from the discussion even though the model shows it.
- **S2:** the two unfavorable 4-session nulls are declared uninformative by "theorem", while the favorable 4-session result from the same design is kept and called "the only session-clustered interval in this paper that excludes zero" (p. 20). That sentence is true, but it is true because of the test chosen for the other two.
- **C3's "in any cell measured":** it counts zeros from cells that could not produce a loss.

### 4.2 Pre-registration and the nine phase-40 amendments

I read in full the pre-registration (`prompts/phase-40-agent-reachability.md`), amendments 2, 5 and 7, and the closure report (`reports/phase-report-40-closure-2026-09-22.md`). Amendments 1, 3, 4, 6, 8 and 9 I know only from the audit pack's summary and the closure report.

**Were goalposts moved? Yes, twice, and openly.**

- **Amendment 5.**
  - The pre-registered stop rule (§9: *"Any stage fails its criterion **twice**"*) fired: criterion C4 failed in both stage-10 collections.
  - The author overrode it and replaced C4 with bounds that a healthy stage passes.
  - The diagnosis is credible: C4 asked for ±20% of a cost *ceiling*, which no healthy stage could meet.
  - The amendment labels itself "an **override**, not a clarification" and keeps both failures on record.

- **Amendment 7.**
  - Withdrew a stage-30 criterion (clause 1) as unreachable.
  - Then, by author decision, opened stage 100 with stage 30 recorded as PARTIAL.
  - It too is labelled an override and does not score the clause as passed.

- **Amendment 2** changed the prompt after the first live stage.
  - The pre-registration's F1 clause forbids retrying "with a different prompt … until the result appears".
  - F1 is defined over 20 runs, and the first prompt produced zero executions. I read this as an instrument fix, not a violation.

**Net for the manuscript.** None of these moves produced a manuscript claim. Stage 100 failed and the workstream was closed, and `grep -ri "phase 40\|language model\|LLM" paper/` finds only a bibliography title (verified). So the amendments did not move the paper's goalposts.

**But the closure then ruled every form of mention forbidden (should-fix, honesty).** The closure report records:
- 0 undetected duplicates for B0 with a real LLM caller;
- 12 of 12 re-dispatch offers declined by the agent;
- stage 100 FAILED on "both failure modes observed at least once".

It then uses the pre-registration's no-numbers rule, written to keep a non-reproducible hosted-API rate out of the tables, to forbid even a threats sentence. Meanwhile the paper opens with an agent scenario and says *"we use them throughout as the motivating example"* (`sections/01-introduction.tex:8`), and §2 says the traces show *"the property an agent deployment would inherit"* (p. 2).

The pre-registration's own §8 says *"Both failures are reportable results. Neither is a reason to leave the experiment out of the record."* The "record" there is `reports/`, so the rule is technically met. But a reader of the paper is left believing the agent question is untouched, when an attempt was made and the observed caller behaved unlike B0.

*Answer:* one threats sentence, e.g. *"An exploratory, non-reproducible trial with one hosted model as caller, closed early, observed no naive re-dispatch; we report no rate from it."* Alternatively, remove agents from the motivation and the index terms.

### 4.3 Generative-AI disclosure

IEEE policy requires disclosure in the acknowledgments that identifies the AI system, the sections containing AI-generated content, and the level of use (IEEE Author Center, submission and peer-review policies).

- **Named build (p. 22):** compliant in substance. It names Claude (Claude Code, Opus and Sonnet) and OpenAI Codex, and states that implementation, harness, analysis, gates, documentation and prose were all produced with assistance.

- **Anonymous build (`main.tex:168`), the version prepared for reviewers:** *"The author used generative AI coding and drafting assistants …"*. It **does not identify the AI systems**. Naming a vendor does not de-anonymize anyone, so there is no reason for the omission. **Should-fix.**

- **"Exact model identifiers … are recorded in the artifact repository's commit trailers" (p. 22): only partly true.**
  - `git log --format='%(trailers)'` shows one identifier, `Co-Authored-By: Claude Opus 5 (1M context)`, on 396 of 488 commits.
  - There is no trailer for any Sonnet model or for Codex.
  - Codex use is evidenced only by `CODEX_PROMPTS.md` and `WEEKEND_CODEX_PROMPTS.md`.
  - The claimed "authoritative record" is incomplete. **Minor.**

- **The "external reviewer" (should-fix for the audit pack; minor for the paper).**
  - The audit pack (§2.2, §8.2) credits "an external reviewer" (`reports/paper-review-2026-08-11.md`) with catching the pooling violation.
  - That review's own environment note describes a sandbox with "Python 3.12 + uv 0.11.7, no Docker, and outbound network limited to package registries and web search". That is an AI-agent environment, not a human reviewer's.
  - If it was an AI session, "external" overstates its independence. I could not confirm who or what wrote it.

### 4.4 Gates

The audit pack's header says "gates green". **`python scripts/check_prereg_order.py` exits 1 at `3b55fc5`:** "cells: 35 ok: 27 exempt: 4 **failing: 4**". The four failures are the phase-40 collections (`reports/raw/phase40-*`), "tracked collection with no entry in EXPECTED". The collections were pre-registered in `prompts/`, so this is a gate-table omission, not missing pre-registrations. The pack's claim is nonetheless untrue.

Other gates:
- `check_american_spelling.py`: 4 builds clean.
- `check_no_repo_paths.py`: 4 builds clean.
- `check_paper_numbers.py`: see §1.1.

---

## 5. Presentation

### 5.1 Structure against TSE expectations

- **Section order:** Introduction, Motivating Traces, Model, Protocol, Implementation, Evaluation, Related Work, Artifact, Threats, Acknowledgment. This is conventional except for the missing conclusion.
- **No conclusion (should-fix).** I found no TSE rule requiring one. Readers and reviewers expect a short one, though, and the paper currently ends on §9.5 "Where the protocol should not be used". The author's objection that it would be "a third statement" of the results is really an argument for cutting §9's restatements, not for omitting the conclusion.
  - Recommendation: a ~150-word conclusion stating the scoped claim (after B1 is fixed), the negative results, and the open question.
- **Length:** 24 pages. About 3,700 words of Threats (`wc -w sections/08-threats.tex`) restate §6. Supp §3 and §9 duplicate each other.

### 5.2 Language, and what reads as machine-written or over-polished

The prose is careful and precise at the sentence level. The problems are at the level of register and repetition:

- **Constant antithesis.** "rather than" occurs 70 times in about 24,000 rendered words. Aphoristic contrast lines recur: *"The barrier is a query about durability, not a guarantee"* (p. 7); *"It is evidence about storage, not about the protocol"* (p. 14); *"the lie costs nothing until the moment it costs everything"* (model config).
- **Meta-commentary about the paper's own honesty.** For example:
  - *"we report that as a surprise rather than a success"* (p. 12);
  - *"a paper that presented it as a pure win would be selling something"* (p. 10);
  - *"choosing between them after seeing them is the move this paper is arguing against"* (p. 14);
  - *"the third is the one the earlier framing of this paper concealed"* (supp p. 5).
  Reviewers read this as defensive, and it spends words the paper cannot afford.
- **Revision history addressed to readers who never saw the earlier versions.** *"We introduce that margin in this revision"* (`sections/06-evaluation.tex:337`), *"An earlier draft of this paper stopped there"* (p. 13), *"B3 is not the negative control an earlier version of this paper reported it to be"* (p. 13), *"which the earlier version of this result was criticized for not reporting"* (p. 12), and supp p. 3 and p. 4. In a first submission this reads as a resubmission with undisclosed history, or as an artifact of AI-assisted iterative drafting. **Should-fix:** state each current result and its limitation, and drop the history.
- **Run-in paragraph headings written as full-sentence claims.** *"The result fell below its own pre-registered bound, and we report that as a surprise rather than a success:"* (p. 12). This style is unusual for TSE and hard to scan.
- **Process detail that belongs in the artifact.** The destroyed-results-directory incident (p. 22), the test-suite-destroys-matrix incident (supp §6.3), and citation-verification mechanics (p. 19).

### 5.3 Minor presentation items

- The index term "autonomous agents" remains while nothing agent-shaped is evaluated.
- The anonymous build says "The author" (singular). This matters only if the review is double-anonymous.
- Numbers.tex comment on `\ReplicationPreventedHigh`: *"wide because the quantity moves between sessions, not because the sessions are few"*. This is not true: t(3) = 3.182 alone widens the interval about 1.6× relative to a normal quantile. The comment is not rendered, but it is the reasoning the prose inherits.

---

## 6. Should-fix findings referenced above

**S1. The Temporal comparison is not like-for-like.**
- The B5 cell kills the worker once per 10-execution run. Every record in `b5-runs.jsonl` says "worker deaths=1", and one run trace shows 1 `b5_crash_firing`, 15 `b5_activity_started` and 10 `final_classification` events.
- The kill is synchronous, before the call (`experiments/baselines/b5_temporal/worker.py`, `_maybe_die("ACTIVITY_ENTERED_BEFORE_CALL")`).
- The B4 comparison cell kills every execution, mid-transmission (B2).
- The "roughly six times" gap is therefore plausibly exposure and timing, not modelling error. The paper's explanation, "B4's rates are our model's, not the product's", and its pre-registered obligation to re-scope every B4 claim may both have been triggered by an artifact.
- The paper also omits that the Temporal cell took three attempts:
  - Attempt 1 was voided.
  - Attempt 2 was replaced because every run shared one fault seed, with B5b losing 180/600.
  - The replacement was re-registered before collection (`reports/raw/ws6-b5-s1-2026-09-08-attempt3/README.md`). I found no goalpost-moving there, but a sentence is owed.

**S2. Asymmetric statistical standard.** See consistency item 8.

**S3. Latency cells.** See consistency items 4–6. Additionally, `\BarrierCostEach` = 983.3 ms (supp §3's "24.6% increase") is half of the 3-run figure.

**S4. Prevention under `always` is asserted, not measured.**
- Supp Table 4 says "prevents: yes" for `always`.
- Supp §7 says *"`always` makes it nearly free"* (`supplementary.tex:620`).
- The `always` data is crash-free only.
- Under `always`, B3's own writes are synced before the reply, so whether the barrier still separates the arms is an open question.

**S5. Bonferroni coverage.** See consistency item 7.

**S6. Phase-40 omission.** See §4.2.

**S7. AI disclosure in the anonymous build.** See §4.3.

**S8. RQ4 is thin.** See §1.5.

**S9. Scope of the zeros in non-restarting fault cells.** See §1.4 C3.

**S10. Audit-pack gate claim.** See §4.4.

---

## 7. Audit pack claims found untrue or inaccurate

| Pack claim | Finding | Evidence |
|---|---|---|
| Header: "builds green, gates green" | **Untrue** for `check_prereg_order.py` | Exit 1, 4 failing (§4.4) |
| §2.2 table: `per-cell-metrics.csv` supplies "3" macros; `redis-kill-ablation.csv` 25; and so on | **Inaccurate** | Provenance comment lines in `paper/generated/numbers.tex`: `per-cell-metrics.csv` 52, `comparisons-vs-aep-full.csv` 19, `reports/raw/e1-kill-latency-by-run.csv` 19; several sources in the pack's table appear in different proportions |
| §2.1: `\WriteLossAepApplied` provenance under `ws4-writeloss-s1-2026-09-07/` | Path exists only under `reports/raw/`, not the results directories | `find` |
| §7.4: `\archiveavail` renders the "not yet deposited" sentence | **Inaccurate** | The named PDF p. 18 says "prepared and verified, with the Zenodo record reserved under DOI … begins resolving when the record is published" |
| Target venue "TSE, double-anonymous" | **Not confirmed; likely wrong** | IEEE Computer Society author guidance: *"IEEE Transactions on Software Engineering … do not offer this option"* (computer.org/publications/author-resources, snapshot April 2024). Check current TSE instructions |
| §8.2 and §2.2: the pooling violation was caught "by an external reviewer" | **Unconfirmed; doubtful** | The review's environment note describes an agent sandbox (§4.3) |
| Section references in Roman numerals (§VI-B, §VIII) | Mismatch | The compsoc PDF renders Arabic numerals (Section 6.3.1, Section 9) |
| §1.3 C3 "in any cell measured" | **True** | §1.1 |
| §5.2: no manuscript text mentions phase 40 | **True** | grep |

---

## 8. What I verified and what I could not

**Verified:**
- Everything in §1.1.
- The crash-point mapping and deferral logic (B2) in code and data.
- The Temporal kill count and timing (S1) in code and traces.
- The TLA+ configurations cited in B1.
- The anonymous-vs-named PDF differences (text diff).
- The phase-40 pre-registration, amendments 2, 5 and 7, and the closure report.
- Commit trailers.
- Abstract length: 250 words.
- Gate outputs for numbers, spelling, repository paths and pre-registration order.

**Could not check, and why:**
- **Building the PDFs and the anonymity gate:** `IEEEtran.cls` is not installed in my environment. `build_paper.sh` stopped at pdflatex. It promotes only clean builds, so no PDF changed.
- **The pytest suite (2,670 tests):** it needs Docker and Redis, which were not available.
- **The raw evidence archive:** not in the repository, and the DOI is unresolved.
- **The dm-flakey 90/90 probe:** needs root, a loop device and a device-mapper target.
- **TSE's current page limit and review model:** only the Computer Society guidance cited above was found. Confirm with the TSE submission site.
- **Amendments 1, 3, 4, 6, 8, 9:** not read in full.
- **The C2 guard implementation and the TLA+ runs themselves:** TLC was not executed.
- **The -9.2 ms figure:** reproduced as -8.8 ms from per-execution data. The paper's source is `latency-and-throughput.csv`, and I did not trace the difference.
