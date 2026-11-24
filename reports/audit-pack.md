# Audit pack

**For a second independent auditor.** The first audit
(`reports/external-audit-2026-09-23.md`) found two blockers, ten should-fix
items and **nine untrue claims in this file**. This is a rewrite, not an
amendment: the state it described no longer exists.

**This is a map, not a defence.** It tells you what the paper claims, where each
claim's evidence lives, what machinery checks what, and what is open. §8 is the
list of places I expect a reviewer to push hardest — written by the same process
that produced the work, which is a limitation of §8 you should weight
accordingly.

**Nothing here is a substitute for reading `paper/main.pdf`.** Where this
document and the repository disagree, the repository wins — and last time it
did, in nine places.

**What the first audit caught this file doing, so you can check whether it still
does it.** The previous version asserted *"gates green"* **without running
them**; `check_prereg_order.py` was exiting 1 at the time. It also undercounted
its own macro-source table by a factor of eighteen, reproduced a provenance path
that resolved nowhere, misquoted what the PDF says about the archive DOI, and
asserted a review model the venue does not offer. **Every gate claim in §3 and
§9 below was executed for this rewrite and its real output is quoted.** Four
gates could not be run here; they are named in §3.2 with the reason, rather than
being asserted.

| | |
|---|---|
| state | **not submitted anywhere.** Builds green. Gates: 11 run and green, **1 failing by design** (§3.1), 4 not runnable here (§3.2) |
| target venue | IEEE Transactions on Software Engineering — **single-anonymous** (§4) |
| length | main **25 pages** against a **12-page** limit; **13 overlength pages ≈ $2,860** (§4) |
| main | 25 pages · main-anon 25 · supplementary **7 / 7** |
| suite | **not run for this rewrite** — see §3.2. Do not take a number from this file |
| submission blockers | the Zenodo deposit (§7.4) and the archive-coverage failure (§3.1) |
| verified | 2026-09-25 at commit `56ef203` |

---

## 1. What the paper claims

### 1.1 Title

> **AEP: Declared Ambiguity for Non-Idempotent APIs Without Idempotency Keys**

The protocol is named **AEP** and **the acronym is deliberately not expanded** —
§5.3.

### 1.2 Abstract

250 words, at IEEE's limit. Its three moves: the problem (non-idempotent,
keyless, non-queryable endpoints); the protocol (durably acknowledged
write-ahead intent, fenced state writes, fail-closed escalation); and the
central result, a separation.

**The third move was rescoped on 2026-09-24 and this is the single most
important change since the first audit.** It now reads:

> *"Because detection does not depend on the barrier **for record-preserving
> faults**, its cost is a deployment choice, not the protocol's price."*

The words *for record-preserving faults* were not there when the first auditor
read it. §2.2 is why.

### 1.3 Contributions C1–C4

| | claim | where |
|---|---|---|
| **C1** | The declared-ambiguity formulation: a three-way trade, not an engineering-quality problem | Section 3, `tab:trilemma` |
| **C2** | A protocol and an implementation | Sections 4, 5 |
| **C3** | An evaluation under real process kills. *"AEP records no undetected duplicate and no lost effect in any cell measured"* | Section 6 |
| **C4** | **A decomposition of the mechanism, by ablation, and the boundary at which it stops** | Section 6.3 |

**C4's wording changed.** It previously read *"a decomposition … that reassigns
our own headline result"*. The first audit's objection was that a
design-guaranteed null was being presented as a finding, and the phrase is
gone (`c8cedbc`). **Check C4 against §6.3.1's closing paragraph**, which now
states a boundary the paper has not measured.

**C3's scope condition — *"in any cell measured"* — is load-bearing**, and §6.3.1
now carries a second scope condition of its own.

### 1.4 The research questions

| RQ | answered in |
|---|---|
| RQ1 undetected duplicates and the residual's shape | Section 6.2 |
| RQ2 which durability mechanism produces which guarantee | Section 6.3 |
| RQ3 cost, and how much is optional | Section 6.4 |
| RQ4 recovery | Section 6.5 and the supplementary |

**New since the first audit:** Section 6.6 (`sec:eval-abd`), a re-collected
crash point reported as its own session — §2.1.

---

## 2. The two blockers, and what was done

### 2.1 B2 — the baseline crash point was not the position Table 3 named

**The finding.** `experiments/baselines/crash_points.py` mapped both
`after_barrier_before_dispatch` and `mid_dispatch` to one enum value, that value
was the whole of `DEFERRED_BASELINE_POINTS`, and the injector therefore killed
the five baselines with a watchdog **inside the socket wait** at both names. The
request had been sent. Table 3 said *"record durable; no effect"*. The module
docstring claimed the opposite of what the module did. Nothing in the manuscript
disclosed it.

**Verified independently** in `reports/audit-response-2026-09-23.md` §1,
including that all 84 tracked `run-config.json` files carry
`crash_style: None`, so the override existed and was never used.

**What was done, five things:**

1. **The docstring now describes the code.** `crash_points.py`:
   *"Serves both `after_barrier_before_dispatch` and `mid_dispatch`, and **both
   are delivered by the deferred watchdog**, so in a baseline the death lands
   inside the socket wait for either name."* It goes on to name this as the one
   place a baseline's delivered position differs from the roadmap position it is
   named for.
2. **The two mappings are pinned against each other** —
   `tests/test_crash_point_mapping.py`. A future edit that collapses AEP-full's
   two positions, or that silently changes a kill style, fails.
3. **Section 6.1 discloses it, in the body, not a footnote.** It states that the
   five baselines resolve the two names to one position delivered by a watchdog
   in the socket wait; that the request was therefore sent; and that *"what
   those cells measure is a kill during transmission rather than a kill before
   it."*
4. **The cells are excluded from every pooled baseline rate**, and the
   consequence is stated rather than hidden: *"AEP-full and B3 pool six, B4 and
   B4b pool five, and B0 to B2 pool four."* `tab:outcomes`'s caption carries the
   same statement. **This asymmetry is now open claims-entry 5** (§7.1).
5. **The position was re-collected** — phase 53.

**The macros that moved.** `\BaselineDupLow` and `\BaselineDupHigh` are now
**0.74** and **0.78**; they were 0.77 and 0.83. Every Table 7 baseline cell
moved with them (the per-cell deltas are tabulated in
`audit-response-2026-09-23.md` §1.6). The direction of every comparison
survives: AEP-full and B3 are at zero on both metrics either way.

**Phase 53, and its prediction was refuted.** Pre-registered at `ba1638c`
(`prompts/phase-53-abd-immediate-2026-09-24.md`), collected 2026-09-24 with
`AEP_HARNESS_CRASH_STYLE=SIGKILL_IMMEDIATE`: **15 cells, 45 runs, 450
executions**, five baselines × three capability classes.

> **The registered prediction was that applied effects, undetected duplicates,
> lost effects and dispatch attempts would all be zero across all 450
> executions. Four of the five systems recorded all four above zero.**

**Why it was wrong, in the paper's own words:** the prediction *"reasoned from
the killed attempt, which does send nothing, to the execution, which in this
regime outlives its first attempt: a supervisor re-executes"*. The kill is
correct; the prediction confused attempt with execution.

**The control that establishes the kill is now where its name says.**
`\AbdZeroDispatchApplied` is **0 of 450** — no execution recorded
`dispatch_attempts = 0` together with an applied effect. The matrix's deferred
cell had 82 of 90 for B4b alone. And B4b, which is Maximum-Attempts-1 and does
not re-execute, is **0 applied and 0 dispatch attempts** across its 90.

**It is reported separately and pooled with nothing.** Section 6.6 says so
explicitly: *"The matrix was collected in early August. A rate computed across
two sessions is in part a property of how many runs of each it contains."*
Eleven `\Abd*` macros carry it; none mixes the two sessions.

**What an auditor should check here.** That no rate anywhere pools the
2026-09-24 cell with the matrix; that `tab:outcomes`'s caption matches §6.1's
prose about who pools how many crash points; and that the refutation is stated
as a refutation rather than softened.

### 2.2 B1 — detection vs the barrier

**The finding.** *"Detection does not depend on the barrier"* was stated
unscoped in eight places, while the project's own TLA+ model expects
`NoLostEffect` to **fail** when the barrier is ablated and the store restarts
(`formal/configs/b3-no-barrier-restart.cfg`, `EXPECT: fail NoLostEffect`). No
collected cell ever restarted Redis after a record loss —
`coordinator_restarted_unexpectedly` is `False` in all 60 write-loss runs, and
`reports/b1-plan-2026-09-24.md` established that this is **by construction**:
`MECHANISM_WRITE_LOSS` is in `NON_KILLING_MECHANISMS`, the set that skips the
restart.

**The model contains its own control**, which the first audit did not note and
which Table 6 has always printed two rows apart:

| config | Barrier | TruthfulFsync | SingleTimeline | expectation |
|---|---|---|---|---|
| `b3-no-barrier` | FALSE | TRUE | TRUE | pass |
| **`b3-no-barrier-restart`** | **FALSE** | TRUE | **FALSE** | **fail `NoLostEffect`** |
| **`aof-rewind`** | **TRUE** | TRUE | **FALSE** | fail `P1` only — **`NoLostEffect` holds** |
| `write-loss` | TRUE | **FALSE** | FALSE | fail `NoLostEffect` |

**What was done, three things:**

1. **Rescoped in all eight places** (`08590fb`). The abstract, §6.3.1 twice,
   §6.3.2 twice, §9.2, the generated supp Table 4 caption, and supp §7's
   heading. **`Durability is neither necessary nor sufficient for detection` —
   the strongest sentence in the paper and the least defensible — is gone;
   `grep` returns 0.** It is replaced by *"What separates them is not durability
   but that the record is written before the call and that no path re-enters the
   dispatching state."*
2. **§6.3.1 now states the model's prediction as falsifiable**, citing Table 6's
   matched pair: *"the model predicts that under a fault which destroys the
   record the barrier is what separates them, and that detection without it
   fails. **We have not tested that prediction. It is falsifiable, the cell that
   would decide it is pre-registered, and it has not been collected.**"*
3. **Phase 54 is built, tested and pre-registered — and NOT collected.**
   `prompts/phase-54-record-loss-restart-2026-09-24.md`, committed at `8d485c0`
   before any of its code existed, blob pinned at `711dd40`.

**What phase 54 will and will not do, because the obvious design does not
work.** The first audit proposed running B3 and AEP-full under `drop_writes`
with a restart. **That cell would produce a null.** `drop_writes` is the lying
fsync, which with a restart is `write-loss.cfg` — and that config expects
`NoLostEffect` to fail *with the barrier enabled*. Both arms lose and nothing
separates. Phase 54 therefore uses `dm-flakey` **`error_writes`**, under which
the barrier's `WAITAOF` fails honestly and AEP-full withholds dispatch.

**Built for it:** `error_writes` in `experiments/flakey_write_loss.py`
(previously hard-coded `drop_writes`, and it now raises on an unknown mode
rather than falling back); `arm_error_writes` in `experiments/harness/write_loss.py`;
and `MECHANISM_WRITE_LOSS_RESTART`, deliberately **not** in
`NON_KILLING_MECHANISMS` so the restart happens. 17 tests, three known-positives
each verified by reintroducing the defect.

**The rehearsal found a defect before any collection**, recorded in
`reports/phase-54-build-and-rehearsal-2026-09-24.md`: `_reload_table` issued a
plain `dmsetup suspend`, which calls `freeze_bdev()` and **syncs the
filesystem**. Two arming paths disagreed and the unflagged one was the one a run
calls. Had the cell been collected against it, the arming step would have
flushed the record the cell exists to lose and **both arms would have read zero,
indistinguishable from the claim being vindicated.**

**What an auditor should check here.** That the eight rescoped statements agree
with each other and with C4; that §6.3.1's prediction paragraph matches what
`b3-no-barrier-restart.cfg` and `aof-rewind.cfg` actually say; and that nothing
in the paper implies the boundary has been measured.

---

## 3. The gates — run for this rewrite, with real output

### 3.1 Run, and what they said

Executed 2026-09-25 at `56ef203`. **Three were run under WSL** because they fail
on this Windows checkout for environmental reasons — §3.3.

| gate | exit | output |
|---|---|---|
| `check_prereg_order.py` | **0** | `cells: 36   ok: 31   exempt: 5   failing: 0` · `pre-registrations byte-identical to their first commit: yes` |
| `check_paper_numbers.py` | **0** | `44 passed, 0 failed` |
| `check_no_repo_paths.py` | **0** | `4 build(s) clean, 0 failed` |
| `check_american_spelling.py` | **0** | `4 build(s) clean, 0 failed` |
| `check_american_spelling.py --selftest` | **0** | `selftest: 6 of 6 confirmed — it fires, it does not over-fire, and it leaves cited titles alone` |
| `check_line_endings.py` | **0** | `OK: no file changed its dominant line ending` |
| `check_tla_transitions.py` | **0** | `OK: AEP.tla matches aep_core.core.intents -- 10 transitions, 6 statuses` |
| `check_planner_cost.py` (three phase-40 roots) | **0** | `7 ok, 0 failed` · `C4' PASSED` |
| `render_arxiv_abstract.py --check` | **0** | `3 ok, 0 failed` · abstract 1 649 characters, 271 under arXiv's limit |
| `check_archive_covers_macros.py --selftest` | **0** | `selftest: 2 of 2` |
| `scan_archive_for_leakage.py --selftest` | **0** | `selftest: 9 of 9` |
| `verify_published_archive.py --local` × 3 parts | **0** | `VERIFIED: every archive at this source is byte-for-byte the one this repository describes` — 26 300 / 18 494 / 12 147 files, 0 problems |
| **`check_archive_covers_macros.py`** | **1** | **`FAILING: 1` — `abd-immediate-2026-09-24: supplies 10 macro(s) and is in NO archive part`** |

**The one failure is expected and is a submission blocker, not a defect.**
Phase 53's collection supplies ten macros and its raw runs are in no archive
part, because the third archive part was built before phase 53 landed and has
deliberately not been rebuilt. The check exists precisely to make this visible:
it was written after five roots supplying eighteen macros sat outside both
archives for nine days while every other gate passed. **It will pass when the
part is rebuilt** — `reports/zenodo-deposit-plan-2026-09-24.md` §19 is the
checklist.

### 3.2 NOT run, and why — asserted nowhere in this file

| gate | why not |
|---|---|
| `python -m pytest` (the suite) | **Out of scope for this session by instruction.** The previous version of this file claimed *"2670 passed, 34 skipped"*; **this one claims no suite number at all.** Run it yourself |
| `check_pytest_gates.py` | Requires a fresh `--junit` from a suite run. The tracked `junit-local.xml` is from 2026-08-05 and is stale |
| `prove_anonymous_gate.sh` | **Appends to `paper/sections/08-threats.tex` and rebuilds the PDFs by design.** Both were out of scope here. `pdflatex` and `IEEEtran.cls` are present in WSL, so it *can* be run — and should be, before submission |
| `verify_refs.py` | Resolves every bibliography entry against DBLP and `doi.org`. Needs network; this session made no live calls |

**The four anonymity checks inside `check_paper_numbers.py` did run** and are
among its 44 — what was not run is the script that proves they can fail.

### 3.3 A portability note an auditor on Windows will hit

Three gates fail on this Windows checkout for reasons that are not defects:

- `check_american_spelling.py` — `extract()` runs `pdftotext` with
  `encoding="utf-8"` and no error handling. The mingw64 `pdftotext` emits a
  byte (`0xb7`) that is not valid UTF-8, `stdout` becomes `None`, and the
  script raises `TypeError`. **It passes under WSL.** A one-line
  `errors="replace"` would fix the portability; it has not been applied.
- `check_paper_numbers.py` and `check_tla_transitions.py` — both import
  `aep_core.core.intents`, which imports `redis.asyncio`. Not installed in the
  Windows interpreter. **Both pass under WSL.**

The measurement host is WSL2, so this affects auditors and not results.

### 3.4 The full gate list, and what each enforces

| gate | what it enforces |
|---|---|
| `check_paper_numbers.py` | 44 checks: every generated table re-derives from the CSVs; `table-1.csv` is never a source; a defined-and-unused macro is a failure; captions use macros not literals; main and supplementary cannot `\cref` each other's labels; every per-cell row names its regime; the state-machine figure is generated from the implementation; the anonymous PDF leaks no byline, path or DocInfo; the supplementary is not stale; bibliography entries exist; no undefined reference; no `\todoitem` survives |
| **`check_archive_covers_macros.py`** | **NEW.** Every macro's evidence is obtainable — its collection root is in some archive part, or the file is tracked. Required roots are derived from `numbers.tex`'s provenance comments, **not by hand**. Refuses to guess: an unattributable bare filename is a failure, and coverage matches by exact name or a declared alias, never by prefix. `--selftest` |
| `check_no_repo_paths.py` | No repository path reaches the **rendered** text of any of the four PDFs |
| `check_american_spelling.py` | No British spelling in rendered text; exempts the references section and a documented identifier list. `--selftest`, 6 of 6 |
| `scan_archive_for_leakage.py` | What a public deposit would expose, in 17 categories. **Five are new and blocking**: third-party e-mail, Azure principal fields, corporate domain, ARM subscription path, phone number — with an author allow-list so the author's own deliberate identifiers do not drown the signal. `--root` scans a directory tree, so the repository is in scope. `--selftest`, 9 of 9 |
| `check_prereg_order.py` | A pre-registration is committed before the collection it governs, **by date and by ancestry**; and each is byte-identical to its first commit, against `reports/prereg-blobs.json` |
| `prove_anonymous_gate.sh` | The four anonymity checks, **by inducing each failure and restoring**. Not run here (§3.2) |
| `check_line_endings.py` | Evidence files under SHA-256 manifests do not have their bytes moved |
| `check_tla_transitions.py` | The formal model's transitions match the implementation — 10 transitions, 6 statuses |
| `check_planner_cost.py` | Phase 40's spend cap, and that the budget files match an independent recomputation from the transcripts |
| `verify_refs.py` | Every bibliography entry resolved against DBLP, `doi.org`, or fetched on a recorded date. Needs network |
| `verify_raw_archive.py` / `verify_published_archive.py` | The deposit's manifests verify file-by-file; the record carries all nine files |
| `build_paper.sh` | Compiles in a scratch directory and **promotes only a clean build** |

**`prove_anonymous_gate.sh` has a hazard worth knowing.** Its staleness fixture
is `paper/sections/08-threats.tex`: it appends to that file and restores with
`git checkout --`. Running it with uncommitted edits to that file destroys them.
It happened once (`reports/phase-report-49` §7).

---

## 4. The venue, and the length problem

**Established from the web on 2026-09-24, not from the repository** —
`reports/tse-venue-2026-09-24.md` carries the quotations, URLs and retrieval
dates. The previous version of this file asserted *"double-anonymous"*, which is
wrong.

| | |
|---|---|
| review model | **single-anonymous.** IEEE Computer Society author guidance names TSE in the list of journals that *"do not offer this option"* |
| page limit | **12 formatted pages** for Transactions |
| beyond it | **$220 per page**, a Mandatory Overlength Page Charge assessed on the final formatted article after acceptance — **not a desk return**. Corroborated by the 2026 IEEE APC List, whose TSE row reads Hybrid, $2 800, overlength $220, Regular 12 |
| this paper | **25 pages** → **13 overlength pages ≈ $2 860** |

**The page count grew from 24 to 25** with the B1 rescope and the audit-item
corrections. Paying is a legitimate option and is cheaper in author-hours than a
half-rewrite; it is the author's call and has not been made.

**What could not be retrieved:** TSE's own CSDL pages are client-rendered and
returned only the site header. The facts above come from the publisher's
society-wide guidance, which names TSE explicitly, and the publisher's own
charge list. **Neither is TSE's own page.** One secondary source — IEEE Xplore's
journal boilerplate — could be read the other way; `tse-venue-2026-09-24.md` §3
explains why it is discounted, and an auditor who wants to overturn this should
start there.

**The anonymous build is kept, and is no longer a deliverable.** Under
single-anonymous review the submitted article is the named build. The anonymous
build is retained as a **leak check**: it is the only differential identity test
in the repository — it builds the same source twice and asserts the second lacks
what the first has — and its DocInfo and `/PTEX.FileName` checks cover channels
no text-based gate reads. `reports/single-anonymous-implications-2026-09-24.md`
inventories every site that serves it and what removal would cost.

---

## 5. Pre-registration, phase 40, and the acronym

### 5.1 Phase 40's nine amendments

`prompts/phase-40-agent-reachability.md` pre-registered an experiment testing
whether the protocol's failure modes are reachable with a real LLM caller. Nine
amendments, each a separate committed file; none a retroactive edit.

**Goalposts were moved twice, and openly.** Amendment 5: the stop rule fired
(criterion C4 failed twice) and the author overrode it, labelling the amendment
*"an override, not a clarification"* and keeping both failures on record.
Amendment 7 withdrew a stage-30 clause as unreachable and opened stage 100 with
stage 30 recorded as PARTIAL. The first audit examined both and found the
diagnoses credible.

### 5.2 The closure, and what the manuscript may say

Closed by author decision at stage 100's first failure with **none** of the
three stop conditions met — spend USD 0.00775720 against a USD 10 threshold.
No manuscript text mentions phase 40 in any form, and the closure rules that
none is owed.

**The first audit's should-fix here was not accepted, and you should weigh
that.** It argued that the closure's no-numbers rule, written to keep a
non-reproducible hosted-API rate out of the tables, was then used to forbid even
a threats sentence — while the paper opens with an agent scenario. The closure's
position is that stage 300 never passed, so the condition on which every
manuscript permission depends was never satisfied. **Nothing changed in response
to that finding.** `grep -ri "phase 40\|language model" paper/` still returns
only a bibliography title.

**The closure governs the manuscript, not the archive.** Its §9 names
`reports/raw/phase40-*/` as preserved evidence, and three of the four phase-40
roots are in the 2026-09-24 archive part. The fourth is withheld — §7.6.

### 5.3 Why the acronym is not expanded

The artifact is called *Agent Execution Protocol*; the manuscript does not use
that expansion, on three grounds: it would make agents the subject, it
contradicts §2's *"It is a scripted caller, not an agent"*, and **nothing
agent-shaped was evaluated**. The artifact's own metadata still carries the old
framing and is on the camera-ready checklist — §7.5.

---

## 6. The evidence chain

**The rule the project imposes on itself:** every numeric claim carries a LaTeX
comment naming the CSV cell or raw report section it came from, and no number is
typed by hand. `paper/main.tex:8-25` states it.

### 6.1 Macros → generated files

`paper/generated/` holds six files, all emitted by `scripts/paper_tables.py`,
none hand-edited. `numbers.tex` defines **228 macros** — 221 at the first audit;
the eleven `\Abd*` macros are new and some were removed.

**A provenance defect the first audit found is still open.** **Seven** macros —
`WriteLossRunsPerArm`, `WriteLossExecPerArm`, `WriteLossExecPerRun`,
`WriteLossAepApplied`, `WriteLossBthreeApplied`, `WriteLossAcksAfterFault`,
`WriteLossAckFailures` — carry the bare prefix
`ws4-writeloss-s1-2026-09-07`, which **resolves nowhere**: the tree exists only
under `reports/raw/`, while every other bare prefix in `numbers.tex` resolves
under `experiments/results/`. Recheck with
`grep -c 'ws4-writeloss-s1-2026-09-07' paper/generated/numbers.tex` → **7**
lines, of which 5 also carry `/analysis/`.

The cause is `root.name` in `writeloss_cell_macros()`
(`scripts/paper_tables.py:625`); the fix is `root.relative_to(ROOT).as_posix()`
plus a regeneration. **Not applied.** Do not follow that path as written.

### 6.2 Generated files → collections

Provenance comment lines naming each source, recheckable with
`grep -c -- "<basename>" paper/generated/numbers.tex`:

| source | lines |
|---|---|
| `per-cell-metrics.csv` | 57 |
| `redis-kill-ablation.csv` | 41 |
| `comparisons-vs-aep-full.csv` | 19 |
| `e1-kill-latency-by-run.csv` | 19 |
| `per-execution.csv` | 15 |
| **`abd-immediate-2026-09-24`** (phase 53, **new**) | **11** |
| `coverage.json` | 10 |
| `phase13-model-gap.json` | 10 |
| `b5-runs.jsonl` | 9 |
| `g2-flakey-write-loss*.json` | 9 |
| `latency-and-throughput.csv` | 8 |
| `phase13-fault-landing.json` | 5 |

The main matrix is **432 runs / 3 780 executions / 126 cells**. Phase 53 adds
**45 runs / 450 executions / 15 cells**, in a separate session pooled with
nothing.

**Two bans the project enforces on itself:** `analysis/table-1.csv` is never
read, enforced by `check_no_banned_source`; and regimes are never pooled, with
every rollup naming its regime in the emitted comment. **A third rule now
applies:** sessions are never pooled either — phase 53's cell and the matrix
share no macro.

**The second rule was violated once and was not caught by the gates.** §8.2.

### 6.3 Raw evidence

**Three archives under one DOI**, not two — the third was built 2026-09-24. All
three verify file-by-file: 26 300 / 18 494 / 12 147 files, 0 problems, quoted in
§3.1. **The DOI is `RESERVED` and does not resolve** — §7.4.

---

## 7. Every open item

### 7.1 `reports/claims-to-review.md`

| # | entry | status |
|---|---|---|
| 1 | §1 said the uncertainty is *never* in the accounts | **RESOLVED** — §1 took C3's scope condition |
| 2 | the supplementary said *every* crashed execution reached a terminal classification; 180 did not | **RESOLVED** — scoped to executions that wrote an intent |
| 3 | `voided/` renders in Section 9 as being in the *published* archive | **REOPENED 2026-09-24.** It closed on the directory existing — true, and verified — without testing the word *published*. `\archivedoistate` is `RESERVED`. **Closes with no text change the moment the deposit is published** |
| 4 | the supplementary's two sections answering the same question | **half RESOLVED.** The self-reference is fixed; whether they merge is open and belongs to the length pass |
| 5 | **Table 7's rows now pool different numbers of crash points, by family** | **open.** Raised 2026-09-24 by B2's exclusion. AEP-full and B3 pool six, B4/B4b five, B0–B2 four |
| 6 | **Phase 54 is pre-registered and not collected; §6.3.1's prediction waits on it** | **open, and a pointer rather than a doubt** |

### 7.2 Phase 54 — built, not collected

Everything it needs exists (§2.2). What stands in the way:
**root** (password sudo, for `losetup`/`dmsetup`/`mkfs.ext4`), **docker socket
access**, and **two unrehearsed halves** — that the write loss lands, and that
`WAITAOF` fails and the record is absent after the restart. Collection is ~1
hour for 60 runs on WS-4's precedent. `reports/phase-54-build-and-rehearsal-2026-09-24.md`
§5.

### 7.3 The archive-coverage failure

`check_archive_covers_macros.py` exits 1 on `abd-immediate-2026-09-24` (§3.1).
Fixed by rebuilding the third archive part with phase 53 included —
`reports/zenodo-deposit-plan-2026-09-24.md` §19, steps D1–D7, about forty
minutes and no decisions. **Deliberately not done**: the other session was still
changing §6 and `numbers.tex`, and rebuilding against a manuscript in motion is
the defect this check exists to catch, in a new form.

### 7.4 The Zenodo deposit — still the submission blocker

`main.tex` carries `\archivedoistate{RESERVED}`. Rendered, Section 8:

> *"those are carried by a separate archive, prepared and verified, with the
> Zenodo record reserved under DOI 10.5281/zenodo.22766567; the identifier is
> fixed and begins resolving when the record is published."*

(The previous version of this file said `\archiveavail` renders *"not yet
deposited"*. It does not; that is the PENDING branch and appears in none of the
four PDFs.)

**What blocks it, in order:** phase 53 must be in the archive (§7.3); the
description in `docs/29` §3 must stay corrected — it previously claimed contents
the extension did not have; **the sandbox rehearsal has never been run**, and it
is the only exercise of the fetch-by-DOI path; then upload into the **existing
draft** and publish. Publishing is irreversible. Full sequence:
`reports/zenodo-deposit-plan-2026-09-24.md` §17.

### 7.5 `reports/camera-ready-checklist.md`

The artifact's *"for agents"* description and *Agent Execution Protocol*
heading; the author name, affiliation, ORCID and artifact URLs; the stale-title
records in `docs/`; and the deposit. **Its framing was wrong and is corrected:**
these were deferred as *"invisible to a double-anonymous reviewer"*, and under
single-anonymous review they are visible from the first day.

### 7.6 One withheld root, and a disclosure that is public

`reports/raw/phase40-deployment-2026-09-18/deployment-show.json` carried a
**third party's** corporate e-mail address in `createdBy` and
`lastModifiedBy` — Azure records who created a deployment. Committed
2026-09-18 and **public on `origin/main` for six days**.

**Redacted in the working tree; history deliberately not rewritten**, because
this project pins commit SHAs in `prereg-blobs.json` and in phase reports.
**The address remains reachable in `08f6e4d` and always will be.** The root is
withheld from the archive. A full sweep of the repository and all three archive
parts found nothing else. `reports/disclosure-phase40-deployment-email-2026-09-24.md`.

### 7.7 The length backlog

`PAPER_ROADMAP.md`'s *DEFERRED TO THE LENGTH PASS*: **L1** the conclusion
(declined, ~215-word draft kept), **L2** entry 4's merge question, **L3** 569
words of cut candidates with the assessment that none should be cut, **L4** §6
at ~6 500 words and §9 at ~3 200.

`reports/length-plan-2026-09-24.md` prices the whole problem: **every sentence
the first audit flagged, plus all 569 collected cut candidates, comes to 0.85
pages** against a 13-page overshoot. Twelve pages is not reachable by trimming.

**`PAPER_ROADMAP.md` still says "24 pages" and is stale by one.**

### 7.8 `reports/known-flakes.md` — one open flake

`test_sigkill_with_concurrent_writers_loses_nothing` failed once in a full suite
run on 2026-09-23. Not reproduced: 5/5 in isolation, and a full re-run passed.
**The failing assertion was not captured**, so the cause is not narrowed — and
one of the three candidates is a genuinely lost increment, which is the defect
the test exists to catch. Not fixed, on instruction.

---

## 8. Known weak points — rewritten from scratch

**Written by the process that produced the work.** Nothing here is carried
forward from the previous version unless it is still true; four of that
version's nine points are gone because they were fixed, and five below are new.

### 8.1 The central claim's boundary is predicted, not measured

§6.3.1 now says the model predicts detection fails without the barrier under
record loss, that the claim is falsifiable, and that the cell is
pre-registered and uncollected. **That is honest and it is not the same as
knowing.** A reviewer is entitled to ask why the boundary of the paper's central
decomposition was not measured when the fault was already provisioned for WS-4
and the restart already existed in the harness. The answer is that the
discriminating design took analysis to get right — the obvious cell produces a
null — and there was no room before submission. **That is a scheduling answer,
not a scientific one.**

### 8.2 An own-rule violation was found by a review, not by the gates

`reports/paper-review-2026-08-11.md` found that the headline significance test
pooled fault regimes — the exact practice §6.2(e) bans. Recomputed on
crashed-only counts the conclusion survived. The gates did not catch it, because
`check_paper_numbers` verifies a number against its source and not the choice of
source.

**And the previous version of this file called that review "an external
reviewer", which it should not have.** Nothing establishes who or what wrote it;
its own environment note describes a container with *"Python 3.12 + uv 0.11.7,
no Docker, and outbound network limited to package registries and web search"* —
consistent with an agent sandbox. What is documented is that it was written in a
separate session, stage 1 blind to `reports/`, against the tracked CSVs. That is
all this file now claims for it.

### 8.3 The same class of gap recurred, and the second one is still open

Five collection roots supplying eighteen macros — including
`\BarrierCostFifteen`, RQ3's headline — were in **neither** archive for nine
days, while `verify_published_archive.py` passed both archives. The cause was
one shared exclusion list written into every archive's metadata, so each part
declared the *other's* omissions. A check now exists
(`check_archive_covers_macros.py`) and **it is currently failing on phase 53**,
which is the same gap recurring within a day of the first being closed. The
check works; the discipline of rebuilding the archive when the manuscript gains
a source does not yet.

### 8.4 Two pre-registered predictions have now been refuted

Phase 53's prediction was refuted (§2.1) and the capability-class sweep
contradicted a registered prediction earlier. Both are reported as refutations,
which is to the paper's credit. **But the pattern is worth a reviewer's
attention**: the project's predictions about its own instrument have a mixed
record, and phase 54's prediction — which the paper now prints — comes from the
same process.

### 8.5 Prevention is measured far more narrowly than detection, and one cell of it was never measured at all

The earlier review put prevention at **1/126th** of detection's breadth.
Separately, supp Table 4's `always` row claimed *"prevents: yes"* when both
`always` collections contain **no crashed executions at all**. That is now
corrected to **"not measured"** (`f3d0ddb`), which is honest and also means the
three-point deployment table has a hole in it where a reader would most want a
number.

### 8.6 The detection finding still has no referent outside this artifact

Section 9 says it plainly: *"the proposition is supported by two systems we
wrote, measured by a harness we wrote, against a provider we wrote."* The only
external system (Temporal) is compared in a cell the first audit showed is not
like-for-like: one kill per ten executions, synchronous before the call, against
a B4 cell where every execution is killed mid-transmission. **The paper
discloses the kill-style difference now; the comparison has not been
re-collected.** The *"roughly six times"* framing rests on it.

### 8.7 Everything was measured on one host, under WSL2

`docs/27-measurement-host.md`. Section 9 proposes re-collecting one frozen cell
on bare metal to price the platform term. **Not done.** Every effect size's
dependence on host timing is measured *on* that host rather than established
*across* hosts. Phase 53 added a second session on the same host, which
addresses session variance and not platform variance.

### 8.8 The length problem is now priced, and nobody has paid it

25 pages against 12. **13 overlength pages ≈ $2 860**, and
`reports/length-plan-2026-09-24.md` establishes that trimming cannot close it:
all the prose the first audit objected to is 0.85 pages. The choice is a
structural rewrite moving results to the supplementary, or the invoice. **That
choice has not been made**, and the paper grew by a page while the audit items
were being fixed.

### 8.9 Statistical practice: one inconsistency fixed, the standard still mixed

The sign-test *"theorem"* is now scoped to the sign test (`c1b46b9`), and
Bonferroni coverage is stated as **80%** where the claim spans four bounds
(`d48d70e`, `be72a83`). What remains: bootstrap intervals are cluster-aware over
runs while Wilson intervals appear on pooled counts; the ±5 pp equivalence margin
is post hoc and disclosed; execution-level Fisher tests are used on clustered
data and disclosed; and *n* = 3 runs per stratum in the matrix.

### 8.10 The generated provenance still points somewhere that does not exist

Seven write-loss macros name a path that resolves nowhere (§6.1). It is a
one-line fix in the generator plus a regeneration, it was found by the first
audit, and it is still there. **A provenance chain with a broken link in it is
the kind of thing this project claims not to have.**

### 8.11 A generated caption escaped a manuscript-wide pass, once

The American-spelling pass over the `.tex` files missed *organised* in
`paper/generated/table-outcomes.tex`, whose caption is a string literal in
`scripts/paper_tables.py`. The PDF-based check found it. **Assume other
manuscript-wide passes have the same blind spot** unless they read the PDFs —
and note that the supp Table 4 caption fixed under B1 was a generated caption
too.

---

## 8a. What you can and cannot verify from a clone

**Read this before you start, so you do not spend time discovering it.** Audited
2026-09-25 at `b762290`; the evidence is in
`reports/clone-completeness-2026-09-25.md`.

### The remote is complete, with two exceptions

`origin/main == HEAD`, one branch, no stashes, one worktree, and **nothing
reachable from any local ref that is not on `origin/main`**
(`git log --all --not origin/main` → 0). The remote carries only `refs/heads/main`.

**Two things exist on the author's machine and nowhere else**, and neither is
evidence for any number:

1. **Two commits in a second clone** (`audit-clone`), on branches the remote
   does not have. They add `docs/25-rebuttal-notes.md` and
   `docs/26-rebuttal-notes.md` — prepared rebuttal paragraphs written
   2026-08-13 against the Stage-2 manuscript. **Those files have never existed
   on `main`** (`git log --all -- <path>` → 0 commits). Not pushed: they are
   submission strategy, and the repository is public.
2. **An aborted collection**, `experiments/results/b2-s4-2026-09-14-ABORTED-order-mismatch`
   — 19 run directories, 286 files, 3.8 MB — **untracked and in no archive
   part.** It is not a session and its own `ABORTED.md` says so; phase report 22
   gives the full account and deliberately left it untracked. But the precedent
   it cites (`b2-paired-v2-s2-aborted-2026-08-28`) *is* archived, and this one
   is not. **Now recorded in `build_raw_archive.py`'s part-3 exclusion list to
   be added on the next rebuild.** Nothing in the paper derives from it.

### What a clone can do

| | |
|---|---|
| **Regenerate all six files in `paper/generated/`, byte-identically** | **Yes** — verified 2026-09-25: 6 of 6 `IDENTICAL`, from tracked inputs only. Every path `numbers.tex` names resolves to a tracked file, and **no collection root has an untracked `analysis/` directory** |
| Rebuild all four PDFs | **Yes, if you have `pdflatex`, `bibtex` and `IEEEtran.cls`.** All 20 `.tex` files, `refs.bib` and all 3 figures are tracked. The four built PDFs are tracked too, so you can diff rather than trust |
| Run 11 of the gates | **Yes** — §3.1 |
| Read every phase report, pre-registration and amendment | **Yes.** `reports/` and `prompts/` are fully tracked |
| Check pre-registration ordering by ancestry | **Yes** — it is a property of the git history you just cloned |

**One thing that was broken until 2026-09-25 and is worth knowing, because it
tells you what the project's own reproduction target does not cover.**
`make reproduce-figures` omitted `--abd-immediate`, so it regenerated a
`numbers.tex` missing all **eleven** `\Abd*` macros and reported `DIFFERS` —
while every gate passed, because `check_paper_numbers.py` builds its own
invocation. **This is the second occurrence**: the Makefile's own comment
records the same drift in phase 25, costing seventeen macros over four passes.
Fixed, and the two argument lists now agree — but **there is still no check that
they agree**, and `comm -23` over the two `--flag` sets is the whole of the
procedure.

### What a clone cannot do

| | why |
|---|---|
| **See any raw run directory** | 1 315 paths under `experiments/results/` and 86 under `reports/raw/` are ignored as bulk data. Only the derived `analysis/` products are tracked — which is deliberate, and is why the archive exists |
| **Obtain the raw evidence at all** | **The DOI is `RESERVED` and does not resolve.** The three archive parts — 147 MB, 20 MB, 375 MB — exist on one machine and are unpublished. Until the deposit is published, **no raw run directory is reachable by anyone but the author** |
| Re-derive the analysis products from raw | Needs an unpacked archive part. `make reproduce-figures` documents pointing `FIG_ROOT` at one |
| Run the evaluation, or `make reproduce-smoke` | Needs **Docker** and **Redis** (pinned by digest to `redis:7.2.5-alpine@sha256:6aaf3f5e…`) |
| Run phase 54, or reproduce the WS-4 write-loss cell | Needs **root**, a **loop device** and **`dm-flakey`**. On the audit machine `sudo -n` required a password and the docker socket was permission-denied to the ordinary user |
| Run the full suite | Needs Docker and Redis. **This file quotes no suite number** — §3.2 |
| Run `prove_anonymous_gate.sh` | It appends to `paper/sections/08-threats.tex` and rebuilds the PDFs. Commit that file first |
| Run `verify_refs.py` | Network access to DBLP and `doi.org` |
| Run the TLC model checks | TLA+ tooling. The 15 `.cfg` files are tracked; only the *runs* are not |
| See the phase-40 live collections | They are at `AEP/stub-results/phase40-*`, **outside the repository by design** (the closure's §9). 18 MB, one machine. `reports/raw/phase40-*` is the committed text evidence |

**Three gates fail on a Windows checkout** for reasons that are not defects, and
pass under WSL — §3.3. Run on Linux or WSL.

**A clone is missing no input that any generator, gate or test reads.** That was
checked explicitly rather than assumed, because five roots supplying eighteen
macros were once outside both archive parts: every provenance path in
`numbers.tex` was resolved against `git ls-files`, and every collection root was
checked for an untracked `analysis/`. **None was found.** The gap that existed
was in the *archive*, not in the repository, and it is tracked as such (§7.3).

### If this machine were lost today

Everything the paper's numbers are computed **from** would be gone, and
everything they are computed **to** would survive. The repository carries the
analysis products, the manuscript, the reports and the pre-registrations. It does
not carry: 2 790 run directories / 44 794 files / 848 MB of raw evidence in the
three unpublished archive parts; 18 MB of phase-40 live collections; the two
rebuttal-note commits; and the 3.8 MB aborted collection. **Publishing the
deposit is the only step that changes this**, and it is §7.4.

---

## 9. How to verify the state yourself

```
bash scripts/build_paper.sh --supplementary
bash scripts/build_paper.sh --supplementary --anonymous
bash scripts/build_paper.sh --anonymous
bash scripts/build_paper.sh
python scripts/check_paper_numbers.py
python scripts/check_archive_covers_macros.py
python scripts/check_archive_covers_macros.py --selftest
python scripts/check_no_repo_paths.py
python scripts/check_american_spelling.py
python scripts/check_american_spelling.py --selftest
python scripts/scan_archive_for_leakage.py --selftest
python scripts/check_prereg_order.py
python scripts/check_line_endings.py
python scripts/check_tla_transitions.py
python scripts/render_arxiv_abstract.py --check
bash scripts/prove_anonymous_gate.sh
python -m pytest -q
```

**Build the supplementaries first.** `build_paper.sh` treats `main.tex` as a
source for the supplementary staleness check, so touching it invalidates all
four builds.

**Commit `paper/sections/08-threats.tex` before running the anonymity gate**, or
run the gate first (§3.4).

**Run on Linux or WSL, not on a Windows checkout** — §3.3.

**Expected, as of 2026-09-25 at `56ef203`:** `25 / 25 / 7 / 7` pages;
`44 passed, 0 failed`; `4 build(s) clean` twice; `3 ok, 0 failed`;
`cells: 36 ok: 31 exempt: 5 failing: 0`; the three selftests at 6/6, 2/2 and
9/9; and **`check_archive_covers_macros.py` exiting 1 on
`abd-immediate-2026-09-24`** until the archive part is rebuilt.

**The suite count is deliberately absent from this file.** The previous version
asserted one without running it, in the same breath as asserting gates green
that were not. If you want a number, run the suite.
