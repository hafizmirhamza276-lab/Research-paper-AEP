# AEP paper — handover, 31 August 2026

**Supersedes `AEP-HANDOVER-2026-08-28.md`**, which is now actively misleading:
it lists sessions 3 and 4 as pending/running, the backlog at B12, and its
findings 1 and 2 are both **contradicted by the data collected since**. Anyone
resuming from it starts wrong. The old file is marked superseded, not deleted.

**This one is in the repository**, which is what the 28 Aug handover asked for
and did not get — it lived at `D:\personal\AEP\`, untracked, on one machine, for
the three days its accuracy mattered most.

Written at the end of the session that ran Phase 8 from analysis through report
and the paper edits. Everything needed to resume is here.

---

## 1. Where the project stands

**The paper is not unfinished. The evidence is.** Sections `01`–`09` are fully
drafted, every number comes from a generator, CI builds the PDF on every commit.

**Changed since 28 Aug: the manuscript now has a submission-blocking defect of
its own** (B20), so "submittable at all" is no longer true without one edit.

| | State |
|---|---|
| Protocol implementation | Complete |
| Test suite | 1,754 passing, 34 skipped, ~91% coverage, CI green |
| Evaluation | 432 runs frozen + Phase 8's k = 4 set, **complete** |
| Manuscript | Full draft, all macros generator-produced. **`paper/main.pdf` is stale — see §3.7** |
| Artifact | `ARTIFACT.md` maps every claim to a command |
| Audit | Phase 6 adversarial audit: verdict FIX FIRST. Blocker closed in Phase 7 |

**Rough completion**, depending on the target:

- Submittable at all — **~90%**, down from 95%. B20 is one paragraph's worth of
  work but it is a *defect in the manuscript as it stands*, reachable by a
  reviewer who reads two sentences in one document.
- arXiv + a systems conference (DSN/Middleware) — **~75%**
- Top-tier journal (TSE/TOSEM) — **~40%**, because B4 remains

---

## 2. Phase history

| Phase | What it did |
|---|---|
| 1A–5C | Implementation, evaluation, artifact, reproducibility |
| 6 | Independent adversarial audit — 14 findings, 1 blocker, verdict FIX FIRST |
| 7 | Fixed the blocker (false fault-coverage claim in the abstract) — found in 3 more files than the audit had seen |
| 9 (pre-B2) | Pre-registered B2, ran the control first, **control failed** |
| 9C | Found the headline prevention result is over-dispersed: AEP-full 10, 20, 12, 4, 7 out of 30 across five identical sessions |
| **8** | **Complete: 8.0 → 8.6, plus the paper edits 8.6 licensed** |

Numbering is out of order: Phase 9 ran before Phase 8.

---

## 3. What Phase 8 did

8.0–8.3 are unchanged from the 28 Aug handover (provenance rescue; the
`\UnwantedPrevented` interval fix; the invariant question; instrumentation; the
pre-registration and its four amendments). What follows is everything after.

### 3.1 — 8.4 collection: **complete, frozen, committed, pushed**

Sessions 3 and 4 completed 120/120 each with zero refills, were frozen, and are
tracked at commit **`828a3fb`** — "Phase 8.4: sessions 3 and 4, the last two of
the pre-registered k=4 set". **19 files tracked per root** (3 top-level + 16
analysis products), strict 8.0 policy: no run directories, no ledgers, no logs.

**The pre-registered set is complete at k = 4 and is not extended.**

| | s1 | s2 | s3 | s4 |
|---|---|---|---|---|
| AEP-full AUTH applied | 18/30 | 15/30 | **17/30** | **23/30** |
| AEP-full NO_READBACK applied | 18/30 | 18/30 | **10/30** | **12/30** |
| **class difference (pp)** | **0.0** | **−10.0** | **+23.3** | **+36.7** |
| B3 AUTH / NO_READBACK | 30/30, 28/30 | 30/30, 28/30 | 30/30, 28/30 | 30/30, 28/30 |
| balance (AEP-full, ms) | +13.0 | −97.7 | **+73.6** | **+41.3** |
| drift (Spearman) | −0.478 | **−0.547** | **−0.112** | **−0.665** |
| non-landing kills | 0 | 2 (rep0, rep6) | **0** | **0** |

> **Correction, 31 Aug.** The s2 figure read **−0.595** in the first version of
> this document. **That number is wrong and I put it there**, carried forward
> from the superseded 28 Aug handover without deriving it — the failure mode
> this project keeps filing, committed inside the document written to replace a
> misleading one.
>
> All four are now derived from the tracked `per-execution.csv` of each root:
> Spearman(run position in execution order, `redis_kill_latency_ms`), position
> reconstructed as `(repetition, cell)` for the interleaved sort key. **One cell
> ordering reproduces `+0.703` for the superseded `b2-paired-s1` and `−0.478`,
> `−0.112` and `−0.665` for s1, s3 and s4 exactly**, which is what licenses
> reading `−0.547` off the same construction. **No ordering, and no combination
> of the s2 root with its aborted predecessor, produces `−0.595`.**
>
> **Provenance of `−0.595`, closed 31 Aug: an isolated slip.** `−0.595` shares
> its source with six other committed figures, so the question is whether they
> are wrong too. Re-derived by `reports/raw/b9_drift_reconstruction.py`, all six
> reproduce **exactly**, including two Theil–Sen slopes a Spearman-only check
> would not have touched:
>
> | figure | committed | derived | source |
> |---|---|---|---|
> | `b2-paired-s1` Spearman | +0.703 | **+0.7034** | amendment 3 §1 |
> | `b2-paired-s1` Theil–Sen | +9.06 ms/run | **+9.060** | amendment 3 §1 |
> | `v2-s1` Spearman | −0.478 | **−0.4780** | amendment 3 §1, 28 Aug handover |
> | `v2-s1` Theil–Sen | −1.81 ms/run | **−1.812** | amendment 3 §1 |
> | `v2-s3` Spearman | −0.112 | **−0.1116** | this document |
> | `v2-s4` Spearman | −0.665 | **−0.6648** | this document |
> | **`v2-s2` Spearman** | **−0.595** | **−0.5467** | 28 Aug handover |
>
> Ten further subsets of s2 — per system, per response class, under both
> reconstructions — were swept for anything near `−0.595`. The closest is
> `−0.5517`; none is within 0.045. **So it is not a real computation with a
> different denominator, which would have been the more serious answer.** It is
> a transcription slip, isolated, and the 28 Aug handover's other quantitative
> content is not impeached by it.
>
> Each root is reconstructed under **its own declared collection design** —
> cell-major for the superseded root, interleaved for the four v2 roots — which
> is a fact of the record, not a fitted parameter. The script prints the
> cross-check: under the other design the same roots give +0.247, −0.153,
> −0.244, +0.006, −0.149, matching nothing. **The reconstruction was validated
> against six known answers before `−0.547` was read off it.**

**All four sessions are interleaved, and k = 4 stands — established from two
independent sources that agree.** This corrected a claim I had asserted from
memory in the 8.5 plan (that s1 was cell-major, which would have dropped k to 3).
It was false; it came from conflating two roots whose names differ by three
characters, `b2-paired-s1` and `b2-paired-**v2**-s1`.

- **Evidence A** — execution order from each root's own `matrix-progress.jsonl`:
  `cell_key` changes per session. Interleaved gives ~119 of 119; cell-major gives
  3. All four v2 sessions: **119, 121, 119, 119**. The superseded `b2-paired-s1`:
  **3**, longest same-cell run 30.
- **Evidence B** — `run-config.json`'s recorded harness commit, then the sort key
  at that commit. All four v2 roots: `(tier, repetition, cell_key)`. The
  superseded root: `(tier, cell_key, repetition)`.

Two orders of magnitude apart, so no threshold needed tuning.

### 3.2 — 8.5 analysis

**Amendment 3 §2 is settled, and it went the way that keeps the registered
primary.** The Δ median log-latency values reproduce the plan's numbers exactly
(+0.012398, −0.085097, +0.069105, +0.041653 against +0.0124, −0.0851, +0.0691,
+0.0417). `|Δ| < 0.02` holds in **1 of 4** sessions. The registered rule is a
*majority*. **No majority → the covariate is not degenerate**, so plan §3.1's
covariate-adjusted model is the primary result and §3.2 is a robustness check,
not a fallback. Sessions 1 and 2 had split 1–1; s3 and s4 decided it, and they
did not exist when the threshold was set.

The covariate is present for 30/30 in all eight arm-sessions. No separation in
any arm of any session. No missing-data handling needed or applied.

**One correction carried forward:** the plan change said "60 runs per arm per
session". It is **30 per arm per session**; 60 is AEP-full's per-session total
across both arms.

### 3.3 — the primary result, and the binding it carries

**The primary estimand returned CONFIRMS.** It may not be stated anywhere, in any
form, without its realised precision beside it. This is **F.0**, and it binds the
*claim*, not any particular word — "a null", "no effect", "statistically
indistinguishable", "the interval contains zero" and any paraphrase all trigger
it. There is no form of words that reports this result and escapes it.

> The registered rule returned CONFIRMS **at a realised precision inadequate to
> the question**. The interval contains zero at a width that would also have
> contained most effects worth detecting.

| | |
|---|---|
| registered minimum detectable effect | 17.3 pp |
| projected §3.2 half-width at k = 4 | 19.6 pp |
| **realised §3.2 half-width** | **33.9 pp** |
| **observed mean effect** | **+12.5 pp** |

The first two rows are **themselves defective** (F.5 / B19) — both computed with
no between-session variance component — so they are deliberately *not* quoted in
the manuscript. The self-contained comparison the paper makes is the half-width
against the observed mean.

**The four session coefficients:**

| session | β class | se | β/se | pp difference |
|---|---|---|---|---|
| s1 | −0.0477 | 0.538 | −0.09 | 0.0 |
| s2 | −0.0268 | 0.610 | −0.04 | −10.0 |
| s3 | **+0.8698** | 0.594 | **+1.46** | +23.3 |
| s4 | **+1.5382** | 0.585 | **+2.63** | +36.7 |

**Heterogeneity is the result, not a caveat on it.** Mean β class **+0.5834**,
t(3) interval **[−0.6368, +1.8035]**; between-session sd **0.7669** against a
typical within-session se of **0.5815**. More of the interval's width comes from
the sessions disagreeing with each other than from sampling error inside them.
The interval contains zero **because the sessions disagree, not because the
effect is absent.** Robustness: the unadjusted paired difference reaches the same
verdict on a different quantity (+12.5 pp, [−21.4, +46.4] pp), and adding run
position moves the mean by +0.003 log-odds.

**This is the sentence to protect:** *an effect of +12.5 pp was observed by an
instrument too blunt to resolve it, and by the registered rule that counts as
failure to reject* — **not** "no class effect was detected".

### 3.4 — the estimator disclosure

**The estimator was chosen after collection, and it determined the verdict.**
Plan §3.1 registered a 95% CI and did not name a variance estimator. That gap was
filled after collection, and the choice decided the outcome: the t(3) interval
contains zero (**CONFIRMS**) while the pooled fixed-effect Wald interval
**[+0.0173, +1.1291]** excludes it.

Graded **"weaker than blind, stronger than post-hoc"** — Amendment 3's own label,
reused so the paper grades its decisions on one scale. **And weaker than
Amendment 3's original position**: when the 0.02 threshold was set, s3 and s4 did
not exist in any form; when this estimator was chosen, **all four sessions'
outcome counts were visible** (18/18, 15/18, 17/10, 23/12), which give the
direction and approximate magnitude.

**What protects the choice is not blindness but the absence of a free
parameter.** Session as the unit, mean, t(k−1), half-width `t·sd/√k` — that
construction predates collection (`paper_tables.py:1899-1901`, which produced
`[6.1, 28.4]`) and plan §3.2 registers it. There was no knob to turn.

**The dual result is reported, not resolved.** Point estimates barely differ
(+0.583 vs +0.573); the disagreement is entirely about the standard error. The
pooled exclusion is marginal — lower bound **+0.017**, and a **3.11%** change in
one standard error flips it. That se was cross-checked against a numerically
differentiated Hessian (agreement 5e-08 to 1.5e-06 relative), so the disagreement
is a property of the two constructions, not of the arithmetic.

### 3.5 — a registered halt fired and was overridden by changing the guard

**Stated plainly because the sequence was *halt → change the instrument →
proceed*, and a reader is entitled to see that without reading a diff.**

The first fit halted on session 2 with "separation or implausible standard
error". **The halt was wrong**: the guard tested coefficient magnitude on the
**intercept**, which is not a quantity of interest. `log(latency)` sits near 7.0
with slopes of 2.4–6.7, so the intercept must land near −7×slope simply to place
the curve.

None of the three registered halt conditions was met: all four sessions converged
in 6–7 iterations, no predictor perfectly orders the outcome, every
class-coefficient se is near 0.6. The guard was narrowed to exclude the
intercept. **The model was untouched, no penalty or prior applied, and the fitted
coefficients are identical either way.**

**The narrowed guard was then positive-controlled**, because a guard that stops
firing is never caught. Against B3's genuinely separated 30/30 arms it **halts in
all four sessions**, by non-convergence before any threshold is consulted.

### 3.6 — 8.6 report

`reports/phase-report-8-6-section-F-2026-08-31.md`, §F.0 through §F.11. It
re-runs nothing, adjusts no estimate, drops no session, and modifies no
pre-registration or amendment.

### 3.7 — the paper edits (the only `paper/` changes this phase)

Two sites, both approved verbatim before editing, both verified **in the built
PDF** rather than in the source:

- **`sections/08-threats.tex`** — the capability-class result: four
  pre-registered sessions, the spread `\ClassPpMin` to `\ClassPpMax`, the
  interval, and the explicit statement that it contains zero *because the
  sessions disagree*, with the half-width wider than the mean it brackets.
- **`sections/06-evaluation.tex`** — the prevention-result scope paragraph now
  says the class comparison "did not reach a precision adequate to the question
  and does not extend the prevention result".

Twelve `\Class*` macros added to `generated/numbers.tex` (122 → 134). Two of them
carry an F.0 binding in their description comment, because `\ClassPpLow` and
`\ClassPpHigh` straddle zero and quoting the pair *is* a statement of the result.

**`paper/main.pdf` is STALE.** It is from 2026-08-21 (`97c44ff`), 19 pages; the
sources build to 20. It was not regenerated because `build_paper.sh` correctly
refuses to promote while a check fails, and one does on this host (missing
`pydantic` in the state-machine figure check, **B6**). Forcing it would be F.4's
move. Marked in `ARTIFACT.md`; the real fix is **B21**.

---

## 4. Findings that outlive Phase 8

**The 28 Aug handover's findings 1 and 2 are CONTRADICTED.** Both were registered
predictions, both failed, **neither was re-run** — the rule inherited from 9C.

1. ~~**Drift reverses sign between sessions.**~~ **CONTRADICTED (F.3b).** Session
   1's −0.478 against the earlier +0.703 was read as a reversal that would recur.
   **All four v2 sessions are negative.** No reversal in the pre-registered set.
   *Replaced by:* the interleaving argument survives on its own merits — it
   removed the perfect arm/drift collinearity that killed the first attempt — but
   it no longer rests on an unpredictable sign.

2. ~~**Fault delivery has started failing.**~~ **CONTRADICTED (F.3a).** Sessions 3
   and 4 returned **0 and 0**. Across 480 runs there are **2** non-landing kills,
   both in one session, both in the first seven repetitions. **Clustered, not a
   rate, and not a trend.** *Replaced by:* nothing — the phenomenon did not
   recur. **B1's backlog entry still argues from the 0→2 reading and must be
   annotated.** That is a Phase 12 edit, named and not made.

3. **Host degradation now has one surface, not three.** With 1 and 2 gone, what
   remains is the kill-latency envelope and the balance figures — real
   instability (+13.0, −97.7, +73.6, +41.3 ms; covariate imbalance signs +, −, +,
   +) but not a directional trend.

4. **Foreign Docker load is confirmed *inside* sessions, and s1/s2 are unmeasured
   rather than clean (F.7).** Three `komserv-pg-race` containers during s3, two
   during s4, despite the precondition clearing the VM at t = 0 — exactly the gap
   B12 names. **The two sessions with confirmed load are the +23.3 and +36.7 pp
   sessions.** No causal claim, no adjustment, no exclusion: the comparison
   available is **"load observed versus load not looked for"**, which is
   consistent with load mattering and equally consistent with coincidence. At 60 s
   sampling both observed containers vanished within four minutes, so counts are
   lower bounds.

5. **"A check that structurally cannot detect what it names"** — the class that
   has now recurred in every part of this project. The 28 Aug handover listed four
   instances in one day. Phase 8 added: B18's guard firing on the intercept, B19's
   sensitivity sweep varying the one parameter that did not matter, B15's
   `SHA256SUMS` attesting 1% of a root, and **F.0's own binding evaded on its
   first use** by a paraphrase that never triggered the word it was written
   around.

6. **NEW — three constructions in one session that were correct only for a reason
   nothing enforces (F.0c).** F.0 binding a word rather than a claim;
   `\ClassPpTwo`/`\ClassPpFour` quoted as a min and max because those sessions
   happen to be the extremes today; claim-bearing macros with no binding
   attached. In each, every macro still resolves and `check_paper_numbers.py`
   still passes while the sentence states something false. **Two of the three were
   found by human review, not by any tool.** The population is unknown and the
   sampling method is manual.

7. **The four sessions are not uniformly instrumented (F.8)** and must not be
   presented as though they were: `SHA256SUMS` entries 15/17/18/18; container
   precondition ✗/✓/✓/✓; fault census ✗/✓/✓/✓; foreign-load series ✗/✗/✓/✓.
   Instrumentation was added *during* the phase, touched no registered gate and
   changed no collection condition. **Uniform where it matters for pooling:** all
   four report `mount_type = volume`, `is_drvfs = false`, ext4, `/dev/sdf`,
   harness clean, interleaved sort key. **k = 4 stands.**

8. **B3 controls for the barrier, not for the host (F.9).** 30/30 AUTH and 28/30
   NO_READBACK in all four sessions, zero variance across 480 runs — a
   **structural** consequence: `b3_no_barrier.py:79-88` returns `True` and issues
   no command, so **B3 has no acknowledgement to race**. *Licensed:* B3 flat while
   AEP-full moves locates the movement in the arm the barrier governs. *Not
   licensed:* any claim that the host was stable. **B3 would read 30/30 and 28/30
   on a host that was on fire.**

9. **The fail-closed invariant held, confirmatorily (F.10).** 131 applied AEP-full
   executions, 131 with the checkpoint traversed, zero exceptions — but along a
   single code path where `dispatched ⇒ traversed` holds by construction. Its
   value is that the claim rests on 131 recorded executions rather than on reading
   the source. `ack ⇒ applied` is not claimed and is not testable here.

10. **The evidence is in the WALs, and the files named after it are empty
    (survey a).** **1093 of 1093 ledgers across both trees are bare 4096-byte
    pages with non-empty uncheckpointed WALs. 100%, without a single exception.**
    For `matrix`: 1.77 MB of `.sqlite3` against **184.59 MB** of WAL — the
    evidence is 104× the size of the files named after it. See §6.

---

## 5. Backlog — now at **B21**, plus **R1–R5**. None fixed.

| ID | Item | Due |
|---|---|---|
| **B20** | **The paper holds a careful and a careless version of one equivalence claim, and ships both** | **SUBMISSION-BLOCKING** |
| **B5** | `freeze_results.py` not portable — `as_posix()` and `newline="\n"`, two lines. `SHA256SUMS` is the integrity mechanism for exactly the reviewers who will run it on Windows | Before Phase 10 |
| **B9** | 8.1's run-level permutation test assumes exchangeability, but kill latency drifts within session. Condition on run index or permute within blocks | Before Phase 10 — the number is already in the manuscript |
| **B6** | Local TeX Live typesets only 24 of 29 bibitems; also the missing `pydantic` that blocks PDF promotion today | Before Phase 14 |
| **B7** | Two-step inference: `04-protocol.tex:78` + `02-motivating.tex:107` lets a reader derive "B3 has no DurabilityAck". Both true, conjunction false | Phase 11 |
| **B8** | `harness_version()` computes `dirty` from porcelain including untracked files. Also move `CLAUDE.md` out of the tree | Phase 12 |
| **B10** | `paper_tables.py` writes incomplete output and exits 0 when under-invoked | Phase 12 |
| **B11** | Gates that look live and cannot act: failing-branch testing **and** validation against a known answer, plus a dry-run seam | Phase 12 |
| **B12** | Nothing samples foreign VM load *during* a session — now confirmed to matter, F.7 | Phase 12 |
| **B13** | `slice_load.py` writes into frozen roots, and its output depends on when it ran | Phase 12 |
| **B14** | `finish_session.sh` counts its own output — the second file to do so | Phase 12 |
| **B15** | `SHA256SUMS` attests ~1% of a root; the gate record is in the other 99%. **B15a**: three artefacts exist twice, hashed in one place and not the other | Before Phase 10 |
| **B16** | A frozen root is an ordinary writable directory — the freeze produces a digest and no enforcement | Phase 12 |
| **B17** | Amendment 4's exclusion criterion compares wall-clock uptime against a suspension-blind threshold | Phase 12 |
| **B18** | Shell substitution silently rewrote the tooling's own inputs, including a commit message | Phase 12 |
| **B19** | The §3.2 half-width column assumed zero between-session variance and said so nowhere | Phase 12 |
| **B21** | The paper build compiles in scratch and then reads three-week-old state back in; `paper/main.pdf` is stale | Phase 12 |
| **R1–R5** | `docs/25-collection-tooling-rules.md`. R1: PIDs, never patterns. R2: validate against a known answer. R3: test the failing branch. R4: dry-run seam. R5: mid-collection observation is disclosed in the artefact | Phase 12 |

**R6 was never filed.** The 28 Aug handover listed it as "to file" — every session
writes a sentinel on exit, the chain advances by reading it, never by polling for
a process. It still does not exist. **The rules file stops at R5.**

**B1 extended** (unchanged, but see finding 2): the second host is required for
*reliability*, not merely by the dm-flakey bind-mount constraint. In Phase 8 a
non-landing kill is visible and discarded; in B1 the fault *is* the measurement,
so intermittent non-delivery silently removes the phenomenon while leaving runs
that look successful. B1 must report its own non-delivery count as a first-class
number. **Its entry still argues from the contradicted 0→2 reading.**

---

## 6. The four things due before submission

### (a) B20 — SUBMISSION-BLOCKING, and the cheapest of the four

**Three places in one build contradict each other.**

- `06-evaluation.tex:618-621` asserts that every rate in that table, on every
  capability class, is *"statistically indistinguishable from AEP-full's"* —
  **carrying no precision at all.**
- `06-evaluation.tex:283-301` says the careful version: a test between two zero
  counts has no power, failing to distinguish is not evidence of sameness, and
  the Fisher values **"are not evidence of equivalence"**.
- `generated/table-ablation.tex:6` says those p-values **"are not used as
  equivalence evidence"**.

**Two of the three disclaim the use the third makes.** And the abstract's
narrower version of the same claim carries `\AblationZeroUpper{}`, a one-sided
95% Wilson bound — so the paper holds a bounded version and an unbounded version
of one claim and ships both. The careless one also *adds* "on every capability
class", which nothing supports: every interval in the section is pooled, and the
only per-class statistics are the Fisher values all three locations refuse to
rest on.

**`check_paper_numbers.py` cannot see it** — the sentence contains no number.

**This is older and easier to reach than anything in 8.5.** A reviewer needs to
read two sentences in one document. It is filed with all locations and exact
wording; it is deliberately **not edited**, because it is a different quantity
and needs its own analysis.

**F.0b states the general principle**, quantity-free, so the next instance is
caught by the rule rather than by a sweep: *a failure to reject may not be
reported as indistinguishability, equivalence, sameness, or absence of an effect
— in any wording — unless the precision that licenses that reading is stated in
the same place.* Two instances now exist in this manuscript, found five days
apart by different means, **neither by a tool**. The three enforcement mechanisms
F.0b names are recorded as unimplemented.

### (b) B9 — the re-analysis obligation

The number is already in the manuscript. Not started.

### (c) B5 — freeze portability

Two lines. Not started. Blocks Phase 10 because the archive's integrity
mechanism is the thing that does not work on the reviewers' platform.

### (d) Phase 10 — **now a design task, not an upload**

**This is the biggest change in scope since 28 Aug.** The old handover budgeted
"~1 h + your manual step". That is no longer true.

**1093 of 1093 ledgers are bare 4096-byte pages with the ground truth in
uncheckpointed WALs.** Consequences for whoever builds the archive:

- **The obvious glob is catastrophic and silent.** `cp **/*.sqlite3` — the
  filename a reader would look for — publishes **432 empty pages** for `matrix`
  under a permanent DOI while appearing complete.
- **"Verifying" or "compacting" before archiving is worse.** A tool that opens
  each ledger to check it can checkpoint and truncate the WALs, destroying the
  originals rather than merely omitting them.
- **The triple must travel together**: `.sqlite3`, `-wal`, `-shm`, per run.
- **`ARTIFACT.md` specifies the archive's contents and nowhere says any of
  this.** There is still **no archive script**; `Makefile:38`'s `ARCHIVE ?=` is
  an input path, not a builder.

**Standing rule that produced this finding, and that stays in force: do not
checkpoint any WAL in place — that writes to the ledger.** If checkpointing is
ever needed it happens on a copy.

---

## 7. Where the raw data actually is — **not off-host**

**State this plainly to anyone who asks whether the evidence is safe. It is
not.**

- The **240 raw run directories** for s3 and s4 exist in the WSL distro, on one
  machine.
- A tar copy exists at `D:\personal\AEP\phase8-raw-archive\` — one gzip per root,
  each verified to contain **120 `ground_truth.sqlite3` + 120 `-wal` + 120
  `-shm`**, 1949 entries, with a **full** SHA-256 manifest covering every file in
  the tar (not just derived products — the gap B15 names) and before/after ledger
  mtimes proving nothing was opened.
- **`D:` is off the WSL ext4 VHDX but on the same physical machine.** This
  removes the "one filesystem" risk. **It does not remove the "one machine"
  risk.** There is no off-host copy of any raw run, for any phase.
- What *is* off-host is the tracked derived products, via `origin`. Those are
  ~1% of each root.

---

## 8. What happens next

### Immediately on return

Nothing is mid-flight. No session is running, no sampler is alive, the working
tree is clean and pushed. The natural next step is **Phase 9 (B3)** or **B20**,
and B20 is one paragraph.

### Then, in order

| Phase | Work | Time |
|---|---|---|
| — | **B20** — the equivalence claim. Do this first; it is cheap and it is blocking | ~1 h |
| **9** | B3 — 9 runs per arm, tighten the `appendfsync always` interval | ~1 h |
| **10** | Raw archive + Zenodo DOI. **B5, B9 and B15 due first.** **Re-budget: this is now a design task** (§6d) | ~half a day + your manual step |
| **11** | T6 retitle + B7 | ~1 day |
| **12** | Housekeeping: B8, B10–B19, B21, R1–R5, file R6, annotate B1 for the contradicted finding, test-count reconciliation | ~1 day |
| **14** | arXiv package. **B6 due first** | ~1 h |
| **13** | B1 — write loss. Needs a Linux host with native Docker | ~2.5 h + VM |
| **15** | Venue decision, taken with evidence in hand | — |

---

## 9. Decisions already taken, and why

Unchanged from 28 Aug, and none of them was disturbed by the new data:

**Retitle rather than run 3C.** The audit ranks 3C #7 of 9 and says retitling is
cheaper. "agent" appears 0 times in sections `03`–`09`. Reversible.

**Conference first, journal second.** arXiv is not a venue. Route: finish the
evidence → arXiv → DSN or Middleware → extended TSE/TOSEM. Going straight at TSE
means B4 — 12–16 practitioners, pre-registered, plus an escalation surface that
does not exist, plus recruitment and probably ethics approval.

**POS_ONLY deferred, via a new regime.** `notifications` is not in
`REGIME_REDIS_KILL_PREACK.endpoints`, so `--endpoint notifications` yields zero
runs silently. When done it gets a **new** `REGIME_REDIS_KILL_PREACK_POSONLY`,
leaving the original byte-for-byte intact.

**k = 4 is not extended.** The plan states that if realised precision is worse it
is reported worse. Adding sessions after seeing results is optional stopping.
Descriptively — post hoc, and **not** a power claim — at the realised sd of
21.3 pp a 17.3 pp half-width needs **k ≈ 9**. Recorded because a reviewer will
ask and Phase 12 planning needs a figure grounded in observation.

**Session 2 is not dropped.** No registered stop condition fired. Discovering an
unrecorded difference in a session's conditions after the fact is licence to
report it, not to remove it.

---

## 10. Open decisions

1. **B4** — going to your supervisor. If you decide to do it, **file the ethics
   application immediately**: its clock starts on submission and runs in parallel.
2. **Venue** — Phase 15, deliberately, once the evidence is in.
3. **Zenodo** — create the account and enable the GitHub integration now. It is
   the one part of Phase 10 that cannot be delegated. **And read §6d before
   assembling anything.**
4. **NEW — off-host raw storage.** §7 is an open exposure with no plan attached.
   It needs a decision (institutional storage? Zenodo restricted deposit? a
   second machine?) that has not been made.

---

## 11. How to work with Claude Code on this

The method that has worked, and it has caught real defects every single round:

**Plan mode for anything that writes new code or pre-registers anything.** Direct
execution only for mechanical steps.

The cycle: ask for a plan → review the plan → amend → approve execution, scoped
to specific steps → report → repeat. **Scope execution narrowly.**

**Two additions from this session, both earned:**

- **Refusing to reconstruct approved text from memory is correct.** When a
  transcript read was denied mid-task, the right move was to stop and ask for the
  text verbatim rather than reproduce it. Four claims in this phase were wrong
  because they were asserted from memory rather than derived — including one in
  the 8.5 plan that would have dropped k to 3.
- **Commit each unit as it completes, with its own message. Never batch unrelated
  work.** Push once at the end. Commit ordering is this project's verifiable
  provenance; batching destroys it.

**What review should look for**, based on what it actually found:

- Claims sourced from prose rather than data
- Numbers asserted rather than derived
- Estimands that are near-tautological by construction
- Verification steps that structurally cannot detect the thing they check
- Conditions set honestly but with no record of their own provenance
- The same misreading in more than one file — it has been three, twice
- **NEW: constructions that are correct only because of an unstated, unowned
  fact** — a session ordering, a word choice, a quotation context. Nothing
  degrades when the assumption stops holding; the sentence still reads fluently
  and every check still passes. **Two of the three found this session were found
  by the reviewer, not by the tooling.**
