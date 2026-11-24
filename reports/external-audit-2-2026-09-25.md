# Second external audit — 2026-09-25

**Manuscript:** *AEP: Declared Ambiguity for Non-Idempotent APIs Without Idempotency Keys* (`paper/main.pdf`, 25 pp.; `paper/supplementary.pdf`, 7 pp.)
**Repository state audited:** `26d4d84`, HEAD of `origin/main` when cloned on 2026-09-25. The audit pack says it was verified at `56ef203` and extended at `b762290`; two commits (`b71ad7a`, `26d4d84`) landed after it.
**Auditor:** no involvement in the work or in the first audit. The repository was cloned fresh into a Linux sandbox, not onto the author's machine. The audit pack was read as the authors' account, not as evidence.
**Nothing tracked was edited.** `git status --short` is empty after every command run for this audit. This file is the only addition. Model-checking runs used a scratch copy of `formal/` outside the repository.

Page numbers refer to `paper/main.pdf` (named build) unless marked "supp". Source locations are `file:line` under `paper/` unless a path says otherwise.

Ranking:
- **Blocker:** must be resolved before submission.
- **Should-fix:** a competent reviewer will raise it, and it weakens the paper.
- **Minor:** polish.

---

## 0. Summary of blockers

**B1. Every run injects a provider fault the paper never discloses, and two claims added in this revision rest on it.**
- **The injection.** `experiments/run_matrix.py:1316-1324` sets `timeout_probability: 0.15` and `server_error_probability: 0.05`. Line 1197 applies them to every matrix run, crash-free runs and phase 53 included. They have been in place since `9154d85` (2026-08-06), before the matrix was collected.
- **What the paper says instead.** §6.1 (p. 8) says the crash-free regime is one where *"nothing is injected"*. No `.tex` file states the timeout or 5xx rates.
- **§6.6's duplicates are background.** The undetected-duplicate rates §6.6 attributes to post-crash re-execution are statistically indistinguishable from the same systems' rates in crash-free runs.
- **§6.2's engine comparison is background.** The comparison §6.2 now presents as *"closer"* matches the engine's rates against what are, in effect, the model's crash-free rates.

**B2. The detection claim is still unscoped outside the eight rescoped sentences, including in the abstract.**
- **What was fixed.** All eight rescoped sentences are present and true as worded.
- **What was not.** Seven other statements still say detection does not come from the barrier, without the scope. They sit in the abstract, the §6.3.1 heading, C4, Table 1, §6.4, §7.3 and supp §7.
- **One now contradicts the paper's own new paragraph.** §6.4 says the barrier's 1 939.7 ms buys prevention *"and nothing else"*. §6.3.1's new paragraph says the model predicts the barrier is what preserves detection under record loss. I ran the model and it agrees with §6.3.1.

**Nothing else rises to blocker.** The largest should-fix cluster is the Temporal comparison, which the paper now states three incompatible ways (§4, rows 4–5).

---

## 1. The first audit's findings: fixed, not fixed, and what the fixes broke

### 1.1 Status of each finding

| First-audit item | Status | Evidence |
|---|---|---|
| B2 docstring | **Fixed** | `experiments/baselines/crash_points.py:31-36`: *"both are delivered by the deferred watchdog, so in a baseline the death lands inside the socket wait for either name."* `tests/test_crash_point_mapping.py`: 20 passed |
| B2 disclosure in §6.1 | **Fixed** | p. 8: *"What those cells measure is a kill during transmission rather than a kill before it."* |
| B2 Table 3 | **Fixed by caption** | p. 4: *"For the five baseline systems the kill at after_barrier_before_dispatch was delivered later than the position named here"* |
| B2 exclusion from pooled rates | **Fixed in tables and prose; not in the figures** | Table 7 recomputed exactly (§2.1). Both data figures predate the exclusion (§1.2, F1) |
| B2 re-collection | Done (phase 53) | §3 |
| B1, the eight named places | **All eight present and true as worded** | `08590fb` touches the abstract, §6.3.1 twice, §6.3.2 twice, §9.2, the supp Table 4 caption and the supp §7 heading |
| B1, everything else | **Not fixed** | Blocker B2 |
| Item 4, Table 9 provenance | **Fixed** | Table 9 caption, p. 15 |
| Item 5, −9.2 vs 15.0 | **Partly** | Main text now explains the sign difference. Supp §7's text and its own Table 4 still disagree with no explanation in the supplementary (§4, row 13). Main's *"stated above with their intervals"* is false (§4, row 12) |
| Item 6, mixed sources | **Fixed** | supp p. 5: *"B3 is 2 075.2 ms under everysec and 2 089.0 ms under always, both from the fifteen-run cells"* |
| Item 7, Bonferroni | **Partly** | Captions say 80%; §6.3.1 itself still says 90% and applies it to two metrics (§4, row 7) |
| Item 8, sign-test "theorem" | **Main fixed; supplementary copy not** | `supplementary.tex:271-273`, supp p. 3 |
| Item 10, prevention under `always` | **Fixed** | supp Table 4: *"not measured"* |
| Item 9 / S1, Temporal comparison | **Rewritten in one place, now inconsistent in four** | §3.4, and §4 rows 4–5 |
| Item 12, supplementary order / duplicate section | **Not fixed** | `supplementary.tex:90`; supp §9 still repeats supp §3 |
| Item 13, uniqueness of the maximum | **Fixed in §6.2; survives in two places** | `sections/04-protocol.tex:171` (p. 6); supp Table 1 caption |
| Item 14, "top of this file" | **Not fixed** | `supplementary.tex:92`, supp p. 1 |
| S6, phase-40 omission | **Not accepted by the authors** | §6.3 |
| S7, AI systems unnamed in the anonymous build | **Fixed** | `main-anon.pdf` acknowledgment names Claude (Opus, Sonnet, Haiku) and Codex |
| S8, RQ4 thin | **Not addressed** | p. 15 still reports counts only |
| RQ3, "detection is nearly free" | **Not addressed** | `sections/01-introduction.tex:126`, p. 2 |
| §5.2, revision history in the prose | **Not addressed, and one instance added** | §7.2 |

### 1.2 Problems the fixes introduced

**F1. The two data figures were not regenerated after the exclusion.** Should-fix.
- `paper/figures/figure-1-undetected-vs-ambiguity.pdf` and `figure-2-duplicates-by-crash-point.pdf` were last changed in `c2fffa6` (2026-08-12). The exclusion is dated 2026-09-24.
- **Supp Figure 1** (supp p. 1), inspected visually, shows B0 ≈ 0.80, B1 ≈ 0.82, B2 ≈ 0.79 and B4 ≈ 0.56. Those are the pooled rates *with* the excluded cell (0.7978, 0.8156, 0.7933, 0.5593; `audit-response-2026-09-23.md` §1.6).
- The main text says the opposite. p. 9: *"the supplementary material shows the same executions pooled to one bar pair per system"*. p. 10: *"The figure adds no number this section does not state."*
- **Main Figure 2** (p. 11) still plots the five baselines at 0.92–0.97 under the label *"after barrier / before dispatch"*. That is the mis-delivered cell; phase 53 measured the position at 0.07–0.27 per cell. The caption does not disclose it: *"The baselines' rate is not concentrated at one crash point: any interruption after the request is on the wire is enough"*.

**F2. The supplementary still says B0–B2 pool five crash points.** Should-fix.
- Main §6.1 (p. 8) and the Table 7 caption (p. 10) say four.
- `supplementary.tex:327` (supp p. 2) says: *"Every other cell in the outcomes table spans all the crash points that apply to its system: six for the systems that run aep_core's workflow, and five for B0–B2"*.
- The data say four: n = 120 per class for B0–B2 (§2.1).
- The same wrong figure appears in `audit-response-2026-09-23.md:148-149` (*"leaves five crash points for B0–B2"*) and in the phase-53 pre-registration §5.1 (*"over the five crash points"*).

**F3. C4 points to a supplementary section that no longer exists.** Minor.
- `sections/01-introduction.tex:128-129` refers to *"(the supplementary material, The barrier is a deployment choice)"*.
- `08590fb` renamed that section to *"What the barrier costs, at three measured points"*.

**F4. The Bonferroni fix updated the captions but not the source they cite.** Should-fix; §4, row 7.

**F5. The Temporal comparison was rewritten in one paragraph and left in the others.** Should-fix; §3.4.

**F6. The unequal crash-point pooling (claims entry 5) now matters for one comparison.** Should-fix.
- `sections/06-evaluation.tex:433` (p. 12) says B4 *"duplicates at the highest rate in the study"*.
- **Pooled, it does not:** B4 is 0.45–0.51 against B0–B2's 0.74–0.78 (Table 7).
- **Per crash point, it does not:** B4's maximum is 0.989 against 1.000 for B0–B2 at `after_resolution_before_barrier`.
- **On a like-for-like mixture, it does not:** over B0's four crash points, B4 averages 0.575 and B0 0.764.
- The sentence was true only while the mis-delivered cell (B4 0.967) was in the pool.

---

## 2. Claims against evidence

### 2.1 What I recomputed

| Claim | Where | Recomputation | Result |
|---|---|---|---|
| Table 7, all 63 cells, with the exclusion | p. 10 | `experiments/results/matrix/analysis/per-execution.csv`, regime `(session-3)`, dropping the five baselines' `after_barrier_before_dispatch` rows | **Exact match** |
| Crash points pooled: six / five / four | p. 8, p. 10 | n per class: AEP-full and B3 180, B4 and B4b 150, B0–B2 120 | **Match** (the supplementary's "five" is wrong, F2) |
| `\BaselineDupLow` / `\BaselineDupHigh` = 0.74 / 0.78 | p. 2, p. 9 | min 0.7417, max 0.7833 | **Match** |
| Phase-53 totals 420 / 55 / 4 / 448 and the per-cell table | `phase-report-53` §1 | `abd-immediate-2026-09-24/analysis/per-execution.csv` | **Match** |
| `\AbdZeroDispatchApplied` 0 of 450; B4b 0 applied over 0 dispatches; `\AbdDupRange` 0.0667–0.2667; `\AbdBfourDupAuth` 0.1333 | p. 16 | same file | **Match** |
| No macro mixes phase 53 with the matrix | pack §2.1 | all 11 `\Abd*` provenance comments in `generated/numbers.tex` name only `abd-immediate-2026-09-24`; Table 7 recomputes from the matrix alone | **True** |
| C3: AEP-full records 0 undetected duplicates and 0 lost effects in every cell measured | p. 2 | every tracked `per-execution.csv` containing AEP-full: 27 files, regimes crashed, p0, p30, redis-kill-preack, redis-kill-inflight, write-loss-preack | **True in every file** |
| Engine: 93/590 duplicates, 84/590 lost | p. 9 | `reports/raw/ws6-b5-s1-2026-09-08-attempt3/b5-runs.jsonl` | **Match** |
| Table 6: barrier-off restart breaks *no lost effect* in 8 steps; single-timeline removal breaks P1 in 4 | p. 7 | TLC 2026.09.25 on `b3-no-barrier-restart.cfg` and `aof-rewind.cfg` as committed | **Match** (8 and 4) |
| §6.3.1: *"with the barrier enabled under the same restart, only version monotonicity breaks and no lost effect holds"* | p. 12 | `aof-rewind.cfg` with its PROPERTIES block removed; it differs from `b3-no-barrier-restart.cfg` only in `BarrierEnabled` | **True**: complete state space, 52 940 distinct states, depth 28, no invariant violated. **But no committed configuration checks this** (§2.5) |
| `numbers.tex` and the five generated tables re-derive from the CSVs | — | `check_paper_numbers.py` | 40 passed, 2 failed. Both failures are "main.bbl / main.log exists", because the sandbox lacks `IEEEtran.cls` |

### 2.2 Contribution by contribution

**C1 (formulation).** Conceptual; not re-audited. The first audit's reading still applies.

**C2 (protocol and implementation).** The guard code was not audited. The paper's bounding of it (*"not a cryptographic capability"*, p. 2) is honest.

**C3 (evaluation).**
- The zeros are verified across all 27 AEP-full collections (§2.1).
- The scope condition *"in any cell measured"* is in place.
- The new problem is B1: the paper does not state the fault surface the evaluation runs under. So C3's *"the baselines without a pre-dispatch record duplicate in most crashed executions"* cannot be read correctly. Part of every baseline rate is the provider's 15% timeout.

**C4 (decomposition).**
- The unscoped residue is blocker B2.
- A framing problem survives even once the scope is fixed. §6.3.2 (p. 12) states that *"no worker-crash fault can exercise it, which is why Section 6.3.1 returns a null."*
- Yet the same section calls that null *"the paper's central structural result"* (`06-evaluation.tex:352`), *"not the one we expected"* (same line), and something reported *"as a finding rather than as a limitation, because it reassigns our own headline claim"* (`06-evaluation.tex:423-424`).
- Scoped to record-preserving faults, the detection half of C4 says: when nothing destroys the record, the mechanism that protects the record is not needed. That is close to definitional.
- The empirical content of C4 is the prevention half, plus the observation that the missing re-entry edge (not durability) is what separates B3 from B4.
- Phase 54 is the cell that would give the detection half empirical bite.

### 2.3 Research question by research question

**RQ1.**
- Table 7 is exact (§2.1).
- The baselines' rates carry an undisclosed background (B1).
- Figure 2 still shows the mis-delivered cell (F1).
- *"B4 … duplicates at the highest rate in the study"* is false (F6).

**RQ2, detection.**
- The model statement in §6.3.1 is true (§2.1).
- The unscoped residue elsewhere is blocker B2.

**RQ2, prevention.**
- Not recomputed; the first audit matched the controlled and uncontrolled cells, and nothing in them changed.
- The residual 3/269 and the one-host scope are stated.

**RQ3.**
- *"The 1 939.7 ms buys the prevention guarantee of Section 6.3.2 and nothing else"* (`06-evaluation.tex:797-799`, p. 15) contradicts §6.3.1's prediction (B2).
- *"Detection is nearly free"* (`01-introduction.tex:126`) still rests on an interval of [−122.6, 120.1] ms. The accurate form is "not distinguishable from zero at this precision".
- The raw evidence for RQ3's two headline figures is in an archive part the paper does not describe (§4, row 15).

**RQ4.**
- Unchanged since the first audit: counts only. *"450 of 450 … resolved to a terminal classification"* (p. 15) is close to guaranteed by P3's bounded budget.
- The recovery-latency distribution is still absent.
- The first audit's should-fix (report the gated latency distribution with its n, or fold RQ4 into RQ1) was not acted on.

### 2.4 Numbers whose source does not measure what the sentence says

1. **Phase-53 duplicates** (p. 16). Presented as re-execution reaching the provider *"from a position where nothing had been sent"*. In fact they are the provider-timeout background (§3.2).
2. **The engine comparison** (p. 9). Presented as model versus engine *"at the same crash point, measured at the intended instant"*. In fact it compares two measurements of the same 15% timeout (§3.4).
3. **Supp Figure 1.** Described as *"the same executions"* as Table 7; it contains 90 more per baseline (F1).
4. **Figure 2's "after barrier / before dispatch" bars.** They measure a kill during transmission (F1).
5. **§9.3, `08-threats.tex:279` (p. 22).** It says the crash-free everysec cell *"is the cell both barrier figures come from"*. If "both barrier figures" means 1 939.7 ms and −9.2 ms, as supp §7 uses the phrase, the second comes from `fsync-always-2026-09-14`, not that cell. Minor.

### 2.5 A model claim that is true but that the artifact never checks (minor)

- **What the paper relies on.** §6.3.1 (p. 12) needs *"no lost effect holds"* with the barrier enabled under a restart.
- **What the committed check does.** `aof-rewind.cfg` lists `NoLostEffect` as an invariant, but `scripts/run_tlc.sh` runs TLC without `-continue`. P1 is an action property (`formal/AEP.tla:637`), so the run halts at P1's 4-step counterexample: *"30 distinct states found, 20 states left on queue. The depth of the complete state graph search is 4."*
- **Why that matters.** The barrier-off `NoLostEffect` counterexample is 8 steps deep. So the committed run never explores the states where the paper's claim could fail.
- **The claim itself is true.** I checked the invariants alone and they hold (§2.1).
- **What would answer it.** Commit an invariants-only configuration, so the claim the paper prints is one the build checks.

---

## 3. Phase 53

### 3.1 Is the refutation reported as a refutation? — **Yes**

- p. 16: *"We registered a prediction and it was refuted. … Four of the five systems recorded all four quantities above zero."* Nothing is softened, and the phase was not re-run.
- The pre-registration (`prompts/phase-53-abd-immediate-2026-09-24.md:84-92`) fixed in advance what an applied effect would mean: *"either the immediate kill is not landing where the code says it does, or a baseline sends before the checkpoint the injector fires at."*
- The phase report (§3) tests both readings against the data and rejects them, correctly. B4b's 0 of 90 rules out both.
- The paper does not mention that the pre-registration named readings. One clause would close that. Minor.

### 3.2 Is the explanation supported by the data? — **Half of it**

**The explanation, p. 16:** *"It reasoned from the killed attempt, which does send nothing, to the execution, which in this regime outlives its first attempt: a supervisor re-executes, and a system holding no durable record of the first attempt calls again."*

**Supported for applied effects and dispatch attempts.**
- 0 of 450 executions record an applied effect with no dispatch attempt.
- B4b, which never retries, records 0 applied over 0 dispatches in 90 of 90.
- Every applied effect has at least one recorded dispatch behind it.
- That establishes the kill position, and that the effects come from re-execution.

**Not supported for undetected duplicates or lost effects.**
- One re-execution after a kill that sent nothing yields one effect.
- A duplicate needs two. 74 executions record 2–3 dispatches, and 55 record 2–3 applied effects (phase report §2.1 cross-tabulation, recomputed here).
- Those extra dispatches are the provider's injected timeouts turning into retries. The same systems duplicate at the same rate when nothing is killed:

| system | phase 53, immediate kill | crash-free, `ws5-2026-09-10/t1-p0-everysec` | Fisher two-sided |
|---|---|---|---|
| B0 | 14/90 = 0.156 | 22/150 = 0.147 | p = 0.85 |
| B1 | 13/90 = 0.144 | 27/150 = 0.180 | p = 0.59 |
| B2 | 12/90 = 0.133 | 20/150 = 0.133 | p = 1.00 |
| B4 | 16/90 = 0.178 | 24/150 = 0.160 | p = 0.72 |

- The matrix's own p0 cells point the same way on smaller n: B0 3/30, B1 5/30, B2 5/30, B4 3/30.
- The phase-53 plan labels its regime *"every execution crashed, no infrastructure fault"* (`matrix-plan.txt`). The provider fault was on regardless (`run_matrix.py:1197`).

**The explanation's wording is also wrong for B4.**
- B4 holds a durable pre-dispatch record. Trace 3 (p. 3): *"its history is on disk before the call"*.
- B4 still calls again, because its retry policy says so, not because it lacks a record.

### 3.3 Is the separate cell kept separate? — **From the pooled rates, yes. From comparisons, no**

**Pooled rates.** No rate pools the two sessions (§2.1). The pack's claim is true as stated.

**Comparison with AEP-full and B3.**
- p. 16: *"The systems that hold a pre-dispatch record, or that decline to retry, reach it at none. That is the same separation Section 6.3.1 reports, measured here"*.
- AEP-full and B3 were not in this collection (pre-registration §2); their zeros come from the matrix. The separation was not "measured here".
- The first sentence is false for B4: it holds a pre-dispatch record and duplicates at 0.2000 in the same paragraph.

**Comparison with the engine.**
- §6.2 (p. 9) compares this cell with the engine's session.
- That comparison is not in the pre-registration's *"Analysis, fixed in advance"* (lines 126–141), and the paper does not label it as unregistered.

**The paper's own rationale cuts against these comparisons.** It says *"A rate computed across two sessions is in part a property of how many runs of each it contains"* (p. 16). These are not pooled rates, but they are cross-session contrasts drawn as findings.

### 3.4 What phase 53 did to the Temporal comparison

**The paper now says four things about it:**
- §6.2, p. 9 (`06-evaluation.tex:181`): *"The direction transfers, and the magnitudes are closer than an earlier comparison of ours suggested."*
- §6.2, p. 10 (`06-evaluation.tex:212`): *"The separation should therefore be read from the point estimates, which differ by roughly 0.8"*. That is the old deferred-kill comparison (0.9167 against 0.1424).
- §7.2, p. 18 (`07-related.tex:208`): *"The rates were several times below B4's and B4b's at the same crash point"*.
- §9.1, p. 21 (`08-threats.tex:119`): *"the direction of the result transfers and the magnitude does not"*.

**None of the new figures measures the crash point.**
- The engine cell kills one worker per ten-execution run. Every record in `b5-runs.jsonl` reads *"worker deaths=1, respawns=1"*.
- Yet 30 of 59 B5 runs record 2–3 duplicate executions, and 21 of 59 B5b runs record 2–4 lost executions. At least 42 of B5's 93 events and 35 of B5b's 84 cannot be the killed execution.
- The engine's rates match the model's crash-free rates: B5 93/590 against B4 24/150 (Fisher p = 1.0); B5b 84/590 against B4b 22/150 (p = 0.90). Both sit on the provider's `timeout_probability: 0.15`, which the engine cell's tracked `mock-api.yaml` confirms.
- B4b's *"loses nothing at all"* is because no B4b execution in phase 53 dispatched at all, while nine in ten engine executions ran normally. The paper discloses the exposure difference (p. 9) but not what it does here.

**The phase report overreaches too.** `reports/phase-report-53-abd-immediate-2026-09-24.md:220-223` calls the B4-versus-B5 match *"a stronger statement about the model's fidelity"*. It shows that both systems retry on a provider timeout at about the timeout rate. That is fidelity for retry-on-timeout, not for crash recovery.

**What would answer it.**
- State the comparison once, in one place.
- Compare the engine against the model's crash-free cell, and say that is what it is.
- Or drop the comparison and keep §9.1's disclaimer.

---

## 4. Internal consistency

| # | Location A | Location B | Contradiction | Rank |
|---|---|---|---|---|
| 1 | §6.1 p. 8, `06-evaluation.tex:57`: p0 is *"nothing is injected"* | `experiments/run_matrix.py:1197, 1316-1324`: 15% timeout, 5% 5xx on every run | Undisclosed fault surface | **Blocker (B1)** |
| 2 | Abstract p. 1, `main.tex:294`: detection *"comes from the pre-dispatch record … not from the durability barrier"* | §6.3.1 p. 12 prediction paragraph; Table 6 row *"The barrier, plus a restart"* p. 7 | Unscoped claim against own model | **Blocker (B2)** |
| 3 | §6.4 p. 15, `06-evaluation.tex:797-799`: *"B3 is the system that already has that guarantee in full"*; 1 939.7 ms buys prevention *"and nothing else"* | §6.3.1 p. 12: *"the model predicts that under a fault which destroys the record the barrier is what separates them"* | Direct contradiction | **Blocker (B2)** |
| 4 | §6.2 p. 9: magnitudes *"closer"* | §6.2 p. 10: *"differ by roughly 0.8"*; §7.2 p. 18: *"several times below"*; §9.1 p. 21: *"the magnitude does not"* | Four statements of one comparison | Should-fix |
| 5 | §6.6 p. 16, `06-evaluation.tex:898`: *"The systems that hold a pre-dispatch record … reach it at none"* | Same paragraph: B4 *"0.2000 … under NONE"*; Trace 3 p. 3: B4's *"history is on disk before the call"* | Self-contradiction | Should-fix |
| 6 | §6.3.1 p. 12, `06-evaluation.tex:433`: B4 *"duplicates at the highest rate in the study"* | Table 7 p. 10: B4 0.45–0.51, B0–B2 0.74–0.78 | False (F6) | Should-fix |
| 7 | Table 7 caption p. 10; §7.2 p. 18; supp p. 5: *"at least 80% … Section 6.3.1"* | §6.3.1 p. 12, `06-evaluation.tex:405-409`: *"at least 90%"*, then applied to *"the two zero-event metrics"* | Captions cite a figure the section does not state; the section keeps the error item 7 identified | Should-fix |
| 8 | §6.1 p. 8 and Table 7 caption: B0–B2 pool four | `supplementary.tex:327`, supp p. 2: *"five for B0–B2"* | Stale supplementary (F2) | Should-fix |
| 9 | §6.1 p. 8: excluded from *"every pooled baseline rate"*; p. 9 *"the same executions"*; p. 10 *"adds no number"* | Supp Figure 1 (supp p. 1) plots the pre-exclusion rates | Stale figure (F1) | Should-fix |
| 10 | Table 3 caption p. 4 discloses the mis-delivered kill | Figure 2 p. 11 plots that cell at 0.92–0.97 with no disclosure | Stale figure (F1) | Should-fix |
| 11 | C4 p. 2, `01-introduction.tex:128-129`: supp section *"The barrier is a deployment choice"* | Supp §7 is now *"What the barrier costs, at three measured points"* | Dangling name (F3) | Minor |
| 12 | §6.4 p. 15, `06-evaluation.tex:818-820`: −9.2 ms *"stated above with [its] interval"* | No interval for −9.2 appears in the main text | False sentence | Minor |
| 13 | Supp §7 text, supp p. 5: 1 939.7 ms and −9.2 ms *"over fifteen runs per arm"* | Supp Table 4, same section, supp p. 6: barrier 1 966.7 and 15.0; the caption does not say these are the three-run cells | Unexplained inside the supplementary (item 5 remainder) | Should-fix |
| 14 | §9.4 p. 23: the sign-test floor, correctly scoped | `supplementary.tex:271-273`, supp p. 3: *"no outcome this design admits could have reached significance"* | Unscoped copy (item 8 remainder) | Should-fix |
| 15 | §8 p. 19: *"Two archives … Between them they carry … the appendfsync=always arm, the deployment sweep of Section 6.4"* | `scripts/build_raw_archive.py` `PART3_ROOTS` (line 408 ff.) holds `ws5-2026-09-10-t1-p0-everysec` (the 1 939.7 ms), `fsync-always-2026-09-14` (the −9.2 ms), `t2-p30`, `t2-keying` and `abd-immediate-2026-09-24` | The paper describes two parts; RQ3's evidence and §6.6's data are in a third it never mentions | Should-fix |
| 16 | §4.3 p. 6, `04-protocol.tex:171`: *"ambiguity is highest at exactly the crash point where no effect can possibly exist"* | §6.2.1 p. 11: *"equally at that maximum at after_intent_before_barrier"* | Uniqueness (item 13 remainder) | Minor |
| 17 | §6.2 p. 10, `06-evaluation.tex:268`: *"the three systems on the right have an empty left bar"* | Supp Figure 1 order is AEP, B0, B1, B2, B3, B4b, B4; the rightmost, B4, is ≈ 0.56 | Caption does not match the figure | Minor |
| 18 | §9.2 p. 22: the voided run *"is in the published archive under voided/"* | Supp §8, supp p. 6: it *"must ship in the external raw archive … it is not present in the current Git repository"*; the DOI is `RESERVED` | False until the deposit is published (claims entry 3) | Should-fix, closes with the deposit |
| 19 | Supp §1, `supplementary.tex:90-93`: *"Sections appear in the order the main paper reaches them … for the reason recorded at the top of this file"* | Supp §9 repeats supp §3 out of order; the "reason" is a LaTeX comment | Items 12 and 14, unfixed | Minor |

---

## 5. What a TSE reviewer would attack, by severity

1. **"Your baseline rates, your only third-party comparison and your newest section all ride on a provider fault you never mention."** (B1)
   *Answer:* disclose the fault surface in §6.1. Re-attribute §6.6's duplicates to the background. Rebuild or drop the engine comparison. All of this is wording and re-analysis of tracked data; no new collection is needed.

2. **"Your central structural result is a null the design guaranteed, and you still call it a finding."** (B2 and §2.2 C4)
   *Answer:* finish the rescope. Replace *"finding rather than a limitation"* and *"not the one we expected"*. Either collect phase 54, or present the detection half as a design argument with a confirming null, and lead with prevention as the empirical result.

3. **"The Temporal comparison says four different things, and none of them is about the crash point."** (§3.4)
   *Answer:* one statement, in one place, labelled for what it compares.

4. **Length.** See below.

5. **"Is the premise real?"** Unchanged since the first audit. §9.3 (p. 22) on field frequency: *"we have none"*. The agent-led framing and the silence about phase 40 make this sharper (§6.3).

6. **"Everything is self-built."** Unchanged. §9.2 (p. 21): *"the proposition is supported by two systems we wrote, measured by a harness we wrote, against a provider we wrote."* The one external system is the one whose comparison is now incoherent.

7. **Statistics.** Much improved. Remaining:
   - §6.3.1's 90%;
   - the supplementary's unscoped sign test;
   - n = 3 runs per stratum;
   - the post hoc ±5 pp margin (disclosed);
   - execution-level Fisher tests on clustered data (disclosed).

8. **Single host under WSL2.** Unchanged. The proposed one-hour bare-metal re-collection of one frozen cell was not done.

9. **RQ4 answers "the implementation terminates" and little more.** Unchanged.

10. **Novelty.** Unchanged: §7 concedes that write-ahead intent is Olive's. The contribution is the capability-typed recovery semantics and the evaluation.

### 5.1 The length problem, and what 25 pages against 12 means

**The rule.** IEEE Computer Society guidance (computer.org/publications/author-resources, retrieved 2026-09-25) sets the regular-paper limit at 12 formatted pages for Transactions, **including references and author biographies**. Each page or fraction beyond it is charged $220, assessed after acceptance and final layout. The same page warns that submission page limits may differ from overlength limits.

**What I could not verify.** TSE's own submission-guidelines page is client-rendered and could not be read. **Whether TSE applies a stricter limit at submission is unverified.** The pack's single-anonymous finding rests on the same Computer Society source; I did not independently re-establish it.

**What the number means.**
- 25 pages is at least 13 overlength pages, or at least $2 860.
- That is before author biographies, which TSE prints and which count toward the limit. Expect one more page.
- The fixes for B1 and B2 add text rather than remove it.

**Where the words are.** Measured from `main.pdf`:

| section | words |
|---|---|
| §6 Evaluation | 8 338 (about 7.5 pages on its own) |
| §9 Threats | 3 623 |
| §7 Related work | 3 282 |
| §4 Protocol | 2 891 |
| References | 1 647 |

**Trimming cannot close the gap.** `reports/length-plan-2026-09-24.md:92-93` reaches the same conclusion: twelve pages means removing about half the body.

**Beyond the fee, length costs something else.** A reviewer reading 25 pages of restatement meets the same result three times: §6, §9, and the supplementary. The Temporal comparison contradiction (§3.4) is a direct product of that restatement: one copy was updated, three were not.

**The structural option.** Keep §§1–6.3 and a compressed §7 in the body. Move §4.6's configuration detail, §6.3.3–6.3.4's probe mechanics, the engine comparison, and most of §9's restatements into the supplementary. Cut the revision-history and meta-commentary sentences (§7). Each page removed saves $220 and shortens a review.

**Paying is legitimate** under the policy. It does not fix the restatement problem.

---

## 6. Honesty and disclosure

### 6.1 Limitations and negative results

**Better than typical, and better than at the first audit.** Refutations are reported as refutations:
- phase 53 (p. 16);
- the write-loss cell (p. 14);
- the keying sensitivity (p. 10);
- the prevention bound missed from below (p. 12);
- the capability-class sweep (supp p. 3);
- prevention under `always`, now *"not measured"*;
- the non-barrier cost that did not replicate (p. 15).

**Softening that remains:**
- the "finding rather than limitation" framing (§2.2);
- supp §7's *"when we ran both arms under exactly that fault"* (`supplementary.tex:613`). The write-loss cell never restarted Redis, so it was not that fault. The sentence steers the reader away from the inference the model supports;
- the phase report's fidelity claim (§3.4).

### 6.2 Pre-registration and amendments

**Phase 53.**
- `check_prereg_order.py`: *"cells: 36 ok: 31 exempt: 5 failing: 0"*, *"byte-identical to their first commit: yes"*.
- The prediction preceded the data by date and by ancestry.
- The five exemptions are `matrix` and `fsync-always` (data from 2026-08-10, before phase 8), `stage3-replication-2026-08-13`, an incident root, and the phase-40 deployment record. None governs a claim made after phase 8.
- The paper's use of phase 53 goes beyond the registered analysis plan without saying so (§3.3).

**Phase 40.** I read the closure report §3. I did not re-read amendments 1–9; the first audit read 2, 5 and 7 and found the overrides disclosed and credible.

### 6.3 The phase-40 ruling: is forbidding any mention defensible? — **Not as the paper now stands**

**R1 is sound.** The closure's rule R1 keeps a non-reproducible hosted-API rate out of the tables: *"No number that reaches the manuscript may come from it."*

**Extending R3 to all prose is not, for four reasons.**

1. **The closure concedes the conflict itself.** Its permission table, row 3 (`reports/phase-report-40-closure-2026-09-22.md:99`), says a future-work sentence *"would now be inaccurate"* because *"phase 40 did place a real LLM in the caller position, and a sentence implying the question is untouched would be false by omission"*. The same reasoning applies to the paper's framing as a whole.

2. **The paper uses agents as its motivation.**
   - Abstract, `main.tex:277`: *"(an autonomous agent, a workflow engine)"*.
   - `01-introduction.tex:4-8` opens with an agent and says *"we use them throughout as the motivating example"*.
   - Index term *"autonomous agents"* (`main.tex:306`).
   - A reader concludes no agent-shaped test was attempted. One was, and the observed caller did not behave like B0.

3. **The review is single-anonymous.**
   - The repository URL is on p. 1, and `reports/raw/phase40-*` and the closure report are public there.
   - A reviewer who opens the artifact will find an unmentioned agent experiment. That reads worse discovered than disclosed.

4. **The pre-registration's own §8 frames both outcomes as results.** *"Both failures are reportable results. Neither is a reason to leave the experiment out of the record."* The closure satisfies this with `reports/`; it is a narrow reading.

**Two defensible exits, both wording-only:**
- one threats sentence that reports no rate (the first audit's draft works); or
- remove the agent framing: the abstract parenthetical, the introduction's opening, and the index term.

**Keeping both the framing and the silence is the one position I would not defend to an editor.**

### 6.4 Generative-AI disclosure

**Both builds now name the systems.** Named build p. 23; anonymous build acknowledgment: *"Anthropic's Claude (Claude Code, with Opus, Sonnet and Haiku models) and OpenAI's Codex"*.

**The model identifiers the disclosure points to exist.** `.claude/agents/*.md` name `opus-4-7` and `sonnet-4-6`, and `.claude/agents/hld-designer.md` names `haiku-4-5-20251001`.

**The trailer claim is overstated.** Minor.
- Named build, p. 23: *"the commit trailers name the model that signed each commit"*.
- 444 of 536 commits carry a `Co-Authored-By` trailer; 92 carry none.
- The untrailered commits are spread from 2026-08-04 to 2026-09-18, including the phase-40 amendment commits.
- Say *"commits that carry one"*.

**Codex is honestly described.** The disclosure says no Codex identifier was recorded.

**Reproducibility is overstated until the deposit is published.** p. 23: *"Every measurement … is reproducible from the archived raw runs"*. The archive DOI is `RESERVED`, so this is true only after publication (claims entry 3).

---

## 7. Presentation and structure

### 7.1 No conclusion

The main text ends on §9.5, *"Where the protocol should not be used"* (p. 23). No TSE rule requires a conclusion, but reviewers expect one. The case for one is stronger now than at the first audit:

- **The scoped claim needs one authoritative statement.** The B1/B2 problems exist because the claim is stated in many places and each copy drifts. A conclusion of about 150 words gives the scoped claim a home — detection under record-preserving faults, prevention under a Redis crash-stop, the prediction phase 54 would test.
- **It lets the restatements go.** The abstract, C4 and §9.2 could then stop restating the claim.
- **It pays for itself.** The author's objection (a third statement of the results) is an argument for cutting the restatements, and those cuts save more words than a conclusion adds.

### 7.2 Revision history addressed to readers who never saw earlier versions (should-fix; not addressed, and grown)

- p. 9: *"closer than an earlier comparison of ours suggested"* — **new in this revision**
- p. 12: *"We introduce that margin in this revision"*
- p. 12: *"which the earlier version of this result was criticized for not reporting"*
- p. 13: *"B3 is not the negative control an earlier version of this paper reported it to be"*
- p. 14: *"An earlier draft of this paper stopped there"*
- p. 15: *"An earlier draft of this paper quoted that remainder"*
- supp p. 3: *"In an earlier draft B4's AUTH cell held twenty executions"*
- supp p. 3: *"B3 is not the negative control this paper previously reported"*
- supp p. 5: *"the third is the one the earlier framing of this paper concealed"*

In a first submission these read as an undisclosed resubmission history. State each current result and its limitation, and drop the history.

### 7.3 Meta-commentary about the paper's own honesty (should-fix; unchanged)

- p. 11: *"a paper that presented it as a pure win would be selling something"*
- p. 12: *"we report that as a surprise rather than a success"*, used as a run-in heading
- p. 15: *"choosing between them after seeing them is the move this paper is arguing against"*

These cost words the paper cannot afford and read as defensive.

### 7.4 Other presentation findings

- **Stale figures (F1).** A reader comparing Figure 2 with Table 3's caption will find the mis-delivered cell the text says was excluded.
- **Supplementary order and duplication.** Supp §9 duplicates §3, and supp §1 claims an order the document does not follow.
- **Full-sentence claims as run-in headings.** Still the dominant heading style in §6 and §9, and hard to scan.

---

## 8. Audit-pack claims found untrue or inaccurate

| Pack claim | Finding | Evidence |
|---|---|---|
| Lines 5 and 16: the first audit found *"nine untrue claims in this file"*, and *"the repository wins … in nine places"* | **Untrue** | The first audit's §7 table has nine rows. It marked two of them **True** (`external-audit-2026-09-23.md:393-394`). At most seven were found untrue or inaccurate |
| Line 77: *"the phrase is gone (`c8cedbc`)"* | **Untrue in substance** | Gone from C4. It survives at `06-evaluation.tex:423-424` (p. 12): *"because it reassigns our own headline claim"* |
| §8a, line 719: *"Run 11 of the gates — Yes"* | **Untrue** | From a clone, `check_archive_covers_macros.py` and its `--selftest` both exit 2 (*"manifest not on disk"*): the manifests live beside the repository (`check_archive_covers_macros.py:59-65`). `verify_published_archive.py --local` needs an archive directory. `check_paper_numbers.py` gives 40 passed, 2 failed without a LaTeX build. Nine ran clean: prereg order, repository paths, spelling and its selftest, line endings, TLA transitions, planner cost (on the tracked `reports/raw/phase40-*` roots), arXiv abstract, leakage selftest |
| §8a, line 752: *"A clone is missing no input that any generator, gate or test reads"* | **Untrue** | Same evidence as the row above |
| Header line 35; §3.1 line 262; §7.3; §7.4; §8.3; §8a lines 705–711; §9 line 805 — the coverage gate fails, phase 53 and the aborted session are in no archive part | **Stale at HEAD** | `26d4d84` states that part 3 was rebuilt with both roots and the gate exits 0. The pack was not updated. **I could not verify the rebuild either way**: the manifests are not in the clone |
| §8a, lines 764–765: *"2 790 run directories / 44 794 files / 848 MB … in the three unpublished archive parts"* | **Inaccurate** | Those are the two-part totals. The paper (p. 19) gives 1 458 + 1 332 = 2 790 and 26 300 + 18 494 = 44 794 for the 2026-09-03 and 2026-09-15 parts. `26d4d84` gives part 3 another 729 run directories |
| §2.1, line 161: phase 53 *"is reported separately and pooled with nothing"* | **True as stated, incomplete** | No rate pools it (§2.1). It is contrasted across sessions in §6.2 and §6.6 (§3.3) |

**And two claims in `audit-response-2026-09-23.md`:**

| Claim | Finding | Evidence |
|---|---|---|
| Line 77: *"all 84 tracked `run-config.json` files under `experiments/results/matrix/`"* | **Not verifiable from a clone** | `git ls-files` finds none there; `.gitignore:154` ignores `experiments/results/matrix/*`. The B2 conclusion stands on the data and on phase 53, but that supporting fact exists only on the author's machine |
| Lines 148–149: dropping the cell *"leaves five crash points for B0–B2"* | **Untrue** | Four; n = 120 per class. Propagated to supp §5 (F2) and the phase-53 pre-registration §5.1 |

---

## 9. What I verified and what I could not

**Verified:**
- Everything in §2.1.
- Every quotation in this file, against `pdftotext` of the four tracked PDFs and against the `.tex` sources at the lines given.
- The provider fault configuration (`run_matrix.py:1197, 1316-1324`, introduced `9154d85`), confirmed in two tracked `mock-api.yaml` files, and its absence from the manuscript (grep).
- The phase-53 pre-registration and report in full; the rates in §3.2; the per-run engine counts in §3.4.
- The eight rescoped sentences (`08590fb`) and the seven that were not rescoped.
- Figure staleness: git history, plus visual inspection of both rasterised figures.
- The TLA+ question: TLC run on three configurations, one of them derived.
- The archive-part contents as declared in `scripts/build_raw_archive.py`.
- The AI disclosure in both builds; the model identifiers in `.claude/`; trailer counts.
- The phase-40 closure's permission table.
- Gate outputs, as listed in §8.
- `tests/test_crash_point_mapping.py`: 20 passed.
- The Computer Society page-limit policy, from computer.org.

**Could not check, and why:**
- **The pytest suite.** Needs Docker and Redis.
- **Rebuilding the PDFs, and `prove_anonymous_gate.sh`.** `IEEEtran.cls` is not installed in the sandbox. I audited the tracked PDFs; `check_paper_numbers.py` reports them not stale against current sources.
- **The raw archive, the part-3 rebuild, and `check_archive_covers_macros.py`.** The DOI is `RESERVED` and the manifests live outside the repository.
- **The engine's per-execution attribution.** Only per-run counts are tracked. §3.4's lower bounds (42 of 93 and 35 of 84 events not in the killed execution) follow from those counts; the full attribution needs the raw event logs.
- **TSE's own submission-guidelines page.** Client-rendered; returned nothing usable. Whether TSE has a stricter submission limit, and its current review model, rest on Computer Society guidance only.
- **Phase-40 amendments 1–9 in full.**
- **Not re-examined:** the C2 guard implementation, and the controlled and uncontrolled Redis-kill recomputations (the first audit matched them, and the underlying data did not change).
- **Not re-checked:** the `WriteLoss*` provenance path (the pack's §6.1 already concedes it is open).
- **`verify_refs.py`.** Not run.
