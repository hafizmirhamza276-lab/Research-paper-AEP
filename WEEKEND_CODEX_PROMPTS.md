# AEP Research Paper — BOUNDED EDITION

**Repo:** Research-paper-AEP
**State at handoff:** Phase 4B in progress — G0, G1, G2 complete; G3 (B4/B4b capability cells) mid-run; G4 pending.
**Completeness at handoff:** ~88%.

---

## How to use this file

1. Run prompts **in order, one at a time**. Every prompt = **PREAMBLE + that prompt's block**, pasted together as one message.
2. Each prompt has four fenced parts: **SCOPE BOUNDS** (the only things Codex may touch), **FORBIDDEN** (instant-stop violations), **TASKS**, and **EXPECTED RESULTS** (a checklist you personally verify before running the next prompt).
3. **Your gate as the human:** after each prompt, open GitHub and check (a) new commits on `origin/main`, (b) Actions green on head commit, (c) the EXPECTED RESULTS checklist against the report. If ANY item fails or Codex touched anything outside SCOPE BOUNDS → do not run the next prompt; instead run the **RECOVERY PROMPT** at the bottom of this file.
4. **Nothing gets submitted or uploaded anywhere this weekend.** Prompts 3–4 prepare materials only. The submit decision happens after Monday's independent audit by a different reviewer.
5. Prompt 5 is optional, only if time remains after Prompt 4 passes its checklist.

---

## PREAMBLE — paste at the top of EVERY prompt

```
You are continuing work in the AEP research repository. Read PAPER_ROADMAP.md and the two most recent files in reports/ before doing anything.

STANDING RULES (non-negotiable):
1. Execute ONLY the phase in this prompt, ONLY within its SCOPE BOUNDS. If the task seems to require touching anything outside the bounds, STOP, write the report with status BLOCKED-SCOPE explaining exactly what you wanted to change and why, and end the session. Do not improvise an expansion of scope. Do not "quickly fix" things you notice outside scope — record them in report section G instead.
2. Every technical claim in any doc needs a real file:line reference you verified by opening the file. Never cite from memory.
3. Never claim tests/commands pass in prose alone — run them and paste RAW terminal output with exit codes into the report. If something cannot run in this environment, say BLOCKED, never simulate output.
4. Do not overstate. This work gets independently re-audited against the code on Monday by a different reviewer who will re-run your commands. If the code does not enforce a property, write that it does not.
5. GIT HYGIENE: verify clean working tree at start (git status — if dirty, STOP and report what is uncommitted; do not proceed on a dirty tree). At end: commit all work with a descriptive message, push, and confirm a green GitHub Actions run for the head commit BEFORE writing the final report. Not pushed with green CI = not complete.
6. Fabricating a citation, a number, or a test result is a halt-level offense. Every bibliography entry must be verified to exist (DOI resolves or venue confirmed).
7. End every session with reports/phase-report-<id>-<date>.md containing exactly:
   A. Phase attempted and scope reference
   B. Files created/modified — the FULL list; this list will be diffed against SCOPE BOUNDS on Monday
   C. Raw command outputs (verbatim, with exit codes) for every command run
   D. The prompt's EXPECTED RESULTS checklist, each item DONE / PARTIAL / NOT DONE / BLOCKED, with evidence for every DONE
   E. Deviations from the instructions and why
   F. Honest hostile-reviewer weaknesses of this session's output (mandatory, non-empty, specific)
   G. Out-of-scope issues noticed but NOT touched (this is where scope temptations go)
   H. Recommended next step
8. Numbers in the paper come ONLY from per-cell-metrics.csv / the frozen results archive via the committed generator scripts. The pooled Table-1 is banned as a source. check_paper_numbers.py must pass after any paper edit; paste its output.
9. EXTERNAL ACTIONS BAN: do not publish, upload, submit, or transmit anything to any external service (arXiv, Zenodo, journal systems, package registries). Do not create accounts, API tokens, or drafts on external platforms. git push to origin and GitHub Actions runs are the ONLY permitted external interactions.
10. NO HISTORY REWRITING: no force-push, no rebase of pushed commits, no amending pushed commits, no deleting or moving existing reports/ files, no editing frozen results. Corrections are made forward, as new commits and new report sections, preserving the record of what was wrong.
11. If any instruction in this prompt conflicts with something you believe is better, you do NOT get to choose the better thing. Follow the instruction and record your objection in section G.
```

---

## PROMPT 1 — Phase 4B Closeout (G3 + G4)

```
CURRENT PHASE: Phase 4B closeout (G3 + G4).

SCOPE BOUNDS — you may create/modify ONLY:
- experiments/results/** (new run data from resuming/completing G3 cells only — never editing existing frozen data)
- paper/** (manuscript text, tables, figures — regenerated via committed generators only)
- reports/phase-report-4b-closeout-<date>.md
- NOTHING else. In particular: aep_core/** is READ-ONLY, experiments/harness/** and experiments/mock_api/** and experiments/baselines/** are READ-ONLY, all generator/gate scripts (paper_tables.py, check_paper_numbers.py, verify_refs.py, analyze.py, freeze_results.py, gen_state_machine.py) are READ-ONLY, CI workflows are READ-ONLY, PAPER_ROADMAP.md is READ-ONLY.

FORBIDDEN in this prompt:
- Changing any harness, baseline, protocol, or analysis code — even to "fix a bug you found". A bug found = section G entry + BLOCKED-SCOPE if it blocks the phase.
- Hand-editing any number, table, or figure in the paper. Everything quantitative flows through the committed generators.
- Re-running or modifying any already-completed matrix cell. Only the incomplete G3 cells may run.
- Softening, omitting, or reordering hostile-pass findings in G4 because they are uncomfortable.

TASKS, in order:
T1. Assess G3 state in experiments/results/ and the run logs. Resume incomplete B4/B4b POSITIVE_ONLY and NO_READBACK cells (30 reps each) via the harness's documented resume path. Verify the stale-shard discard safeguard engages on resume — show evidence in raw output. If resume is unsafe, restart ONLY the affected cells cleanly and say so.
T2. When all G3 cells are complete: regenerate the trilemma table and every affected figure using ONLY the committed generators. Update manuscript text where the new numbers change a statement. If the data contradicts the expected shape (B4 duplicates across capabilities; B4b trades duplicates for lost effects), that is a FINDING — report it prominently, do not smooth it.
T3. Run check_paper_numbers.py (paste output). Rebuild the PDF: zero undefined references, zero \todo markers.
T4. G4 hostile-TSE-reviewer pass against the full revised draft. Attack at minimum: (i) detection-vs-prevention framing — can any sentence still be read as the barrier contributing to detection? Is the B3-equivalence finding stated near the abstract? (ii) the dm-flakey result as written — does text exceed what the experiment showed? (iii) author-written baselines — is the fairness argument and B4_SEMANTICS.md citation load-bearing? (iv) small-n timing cells and the suspend-exclusion policy. (v) anything the new G3 cells changed or exposed.
    Output: a RANKED list. Each attack → either the existing defense (with section reference) or the single word UNDEFENDED. Omitting an uncomfortable attack is a rule-4 violation.

EXPECTED RESULTS (the human will verify each before Prompt 2):
[ ] All G3 cells complete: B4 and B4b each have 30-rep cells on POSITIVE_ONLY and NO_READBACK; run counts visible in the report with raw output.
[ ] Trilemma table in the paper is fully symmetric (all systems × all three capabilities) and was generator-produced (report shows the generator command + output).
[ ] check_paper_numbers.py passes — raw output in report section C.
[ ] PDF builds clean: zero undefined refs, zero \todo (raw build output shown).
[ ] G4 ranked list exists in the report with ≥8 attacks, each resolved to a section-referenced defense or UNDEFENDED.
[ ] Report section B lists ONLY files inside SCOPE BOUNDS.
[ ] Committed, pushed, Actions green on head (run URL in report).
```

---

## PROMPT 2 — Phase 5A (Respond to the Hostile Pass)

```
CURRENT PHASE: Phase 5A (adjudicate every UNDEFENDED item from G4).

SCOPE BOUNDS — you may create/modify ONLY:
- paper/** (text changes; any new quantitative content via committed generators only)
- docs/24-revision-backlog.md (create if absent)
- experiments/results/** ONLY IF option (a) below triggers a permitted small experiment (see FORBIDDEN for the limit)
- reports/phase-report-5a-<date>.md
- READ-ONLY everything else, same list as Prompt 1.

FORBIDDEN in this prompt:
- Any new experiment exceeding 1 hour total wall time, or requiring ANY code change to run. If an UNDEFENDED item needs more than that, it goes to (c) DEFER — no exceptions.
- Making an UNDEFENDED item disappear: every single one must land in the adjudication table.
- Weakening or deleting an existing Threats-to-Validity entry.
- Touching generator/gate scripts, harness code, aep_core, CI, or frozen data.

TASKS:
For EACH item marked UNDEFENDED in the G4 ranked list, do exactly one of:
(a) FIX — bounded change: manuscript text, a new analysis over EXISTING frozen data, or a code-change-free experiment under 1 hour wall time. New numbers flow through generators + check_paper_numbers.py.
(b) DISCLOSE — add to Threats to Validity with a specific, honest scope statement (no vague "future work" waves).
(c) DEFER — add to docs/24-revision-backlog.md with a one-paragraph experiment design.
Then re-run check_paper_numbers.py, rebuild the PDF, and re-read abstract + introduction once for consistency with the changes.

EXPECTED RESULTS:
[ ] Adjudication table in the report: every G4 UNDEFENDED item → (a)/(b)/(c) → exact pointer (file/section or backlog entry). Count of items matches the G4 list exactly.
[ ] Zero items resolved by silence.
[ ] check_paper_numbers.py passes (raw output).
[ ] PDF builds clean (raw output).
[ ] If (a) was used with an experiment: total added wall time stated and under 1 hour, no code changed.
[ ] Report section B lists only in-bounds files.
[ ] Committed, pushed, Actions green (run URL in report).
```

---

## PROMPT 3 — Phase 5B (Reproducibility Artifact Package)

```
CURRENT PHASE: Phase 5B (artifact package — prepared, NOT published).

SCOPE BOUNDS — you may create/modify ONLY:
- ARTIFACT.md (new, repo root)
- Makefile (adding reproduce-smoke and reproduce-figures targets; existing targets untouched)
- README.md, LICENSE, CITATION.cff, CHANGELOG.md (content refresh only)
- The git tag v1.0.0-rc1
- reports/phase-report-5b-<date>.md
- A temporary clean clone in a scratch directory for testing reproduce-smoke (deleted after; not committed)
- READ-ONLY everything else: paper/**, aep_core/**, experiments/** (including results), all scripts, CI workflows.

FORBIDDEN in this prompt:
- Uploading anything anywhere (rule 9): no Zenodo, no arXiv, no DOI minting, no release-asset uploads beyond the plain git tag.
- Editing the paper, the frozen results, or any experiment/analysis code. If reproduce-figures reveals a mismatch between regenerated and committed figures, that is a FINDING for the report and Monday — do NOT "fix" it by regenerating and committing new figures in this phase.
- Makefile targets that mutate frozen results or require manual steps.

TASKS:
T1. ARTIFACT.md: claims-to-evidence map (every quantitative claim in the paper → exact command + CSV/report path that reproduces it), hardware/software requirements (Linux/WSL2, Docker, Python 3.13, pinned Redis digest), estimated runtimes, frozen-archive layout + verification method.
T2. `make reproduce-smoke`: from a clean clone in the scratch directory — compose-provision Redis, run one representative tier-1 cell per system end-to-end, run analysis, print metric rows. Fully unattended. Run it; paste raw output.
T3. `make reproduce-figures`: regenerate every paper figure/table from the frozen archive; compare against committed outputs (byte-comparable or documented tolerance). Run it; paste raw output including the comparison verdict.
T4. Verify frozen-archive manifest hashes against the results directory; paste output.
T5. Refresh README (must describe the research artifact as it now exists — protocol + harness + frozen results + paper — not the old Phase-1 prototype text), review LICENSE/CITATION.cff/CHANGELOG.
T6. Tag v1.0.0-rc1 and push the tag.

EXPECTED RESULTS:
[ ] ARTIFACT.md exists; spot-checking any 3 claims in it leads to a command that a reader could run.
[ ] reproduce-smoke ran to completion unattended from a CLEAN CLONE — raw output in report, including the printed metric rows.
[ ] reproduce-figures ran; comparison verdict stated. A mismatch, if any, is reported as a finding, not silently fixed.
[ ] Archive manifest verification output in report.
[ ] README describes the current artifact; no Phase-1-era text remains.
[ ] Tag v1.0.0-rc1 visible on GitHub.
[ ] Nothing was uploaded to any external service.
[ ] Report section B lists only in-bounds files. Committed, pushed, Actions green (run URL).
```

---

## PROMPT 4 — Phase 5C (Submission-Ready, NOT Submitted)

```
CURRENT PHASE: Phase 5C (final submission package — prepared, NOT transmitted).

SCOPE BOUNDS — you may create/modify ONLY:
- paper/** (proofreading-level text edits, cover letter, arXiv metadata, final PDF)
- PAPER_ROADMAP.md (marking completed phases with report paths; setting CURRENT PHASE to "Monday audit")
- reports/phase-report-5c-<date>.md
- READ-ONLY everything else.

FORBIDDEN in this prompt:
- Submitting or uploading anything anywhere (rule 9). Creating drafts/accounts on arXiv or journal systems counts as a violation.
- Any change that alters a quantitative claim, adds/removes a result, or changes the framing established in G1/5A. This phase is polish; substance is frozen. If proofreading reveals a substantive problem, it goes in section G for Monday, untouched.
- Removing bibliography entries that fail verification without replacement being verified too; keeping any unverified entry "on faith".
- Editing check_paper_numbers.py or verify_refs.py to make them pass.

TASKS:
T1. Full proofread: grammar; terminology consistency — exactly one name per concept globally (choose one of "declared ambiguity"/"known ambiguity"; likewise for "dispatch authority", "coordinator loss", crash-point names); number formatting (decimal places, units, CI notation); figure/table cross-reference integrity both directions; IEEEtran compliance and page budget.
T2. verify_refs.py full pass — every entry resolves (DOI 200 or venue verified). Paste raw output.
T3. paper/cover-letter-tse.md: venue fit, contribution list, no-prior-publication statement (noting the planned arXiv preprint), artifact availability pointing at ARTIFACT.md and the tag.
T4. paper/arxiv-metadata.md: final title, final abstract as plain text, categories cs.SE primary + cs.DC secondary — paste-ready for Monday.
T5. Build the final PDF, commit it. Update PAPER_ROADMAP.md as scoped above.
T6. Report section H must contain: your own completeness percentage with one-line justification, and your top 3 risks for the Monday audit.

EXPECTED RESULTS:
[ ] verify_refs.py passes with raw output; zero unverified bibliography entries.
[ ] check_paper_numbers.py still passes after all edits (raw output) — proving no number drifted during proofreading.
[ ] Terminology audit result stated: which term won for each concept, with a grep-style count showing zero occurrences of the losing terms.
[ ] cover-letter-tse.md and arxiv-metadata.md exist and are complete.
[ ] Final PDF committed; page count stated; zero undefined refs.
[ ] PAPER_ROADMAP.md updated exactly as scoped, nothing else in it changed.
[ ] Section H has the percentage + top-3 risks.
[ ] Nothing submitted/uploaded anywhere. Report section B lists only in-bounds files. Committed, pushed, Actions green (run URL).
```

---

## PROMPT 5 — OPTIONAL Strengthener (only if Prompts 1–4 all passed their checklists)

```
CURRENT PHASE: Optional Phase 3A-lite (formal check of the intent state machine).

SCOPE BOUNDS — you may create/modify ONLY:
- formal/** (new directory: the spec + any runner script for it)
- paper/** (AT MOST one new paragraph citing the spec + one ARTIFACT.md line — nothing else in the paper)
- reports/phase-report-3a-lite-<date>.md
- READ-ONLY everything else. aep_core/** must not change by even one character.

FORBIDDEN in this prompt:
- Any change to src/aep_core, harness, generators, gates, CI, results, or roadmap.
- Claiming the model "verifies AEP" — the paper paragraph may claim only what the checked model actually covers, stated precisely.
- Spending more than ~2 hours on tooling friction: if TLC/Hypothesis setup fights you past that, STOP, write the report as BLOCKED-TOOLING, leave the repo clean (no half-installed toolchains committed), and end.

TASKS:
Choose ONE: (a) a minimal TLA+ spec of the intent transition table + dispatch-authorization chain, model-checked with TLC for P1 and the DurabilityAck precondition; or (b) a Hypothesis stateful test driving the REAL committed Lua scripts against a real compose-provisioned Redis. Raw model-checking / test output goes in the report, including state counts or example counts.

EXPECTED RESULTS:
[ ] Spec/test exists under formal/ and its run output (raw) is in the report.
[ ] The paper gained at most one paragraph + one ARTIFACT.md line; a diff summary proves nothing else changed.
[ ] aep_core diff is empty (show git diff --stat aep_core/ output = nothing).
[ ] check_paper_numbers.py still passes.
[ ] Committed, pushed, Actions green — OR the report says BLOCKED-TOOLING and the tree is clean.
```

---

## RECOVERY PROMPT — use ONLY if a prompt violated its bounds or failed its checklist

```
STOP all forward work. The previous session violated its scope bounds or failed its expected-results checklist. Your ONLY tasks:
1. git status and git log --oneline -15 — paste raw output.
2. Diff the previous session's report section B against its prompt's SCOPE BOUNDS. List every out-of-bounds file touched.
3. For each out-of-bounds change: revert it with a forward commit (git revert or a targeted forward fix — NO history rewriting, rule 10), UNLESS reverting would break a green CI run; in that case leave it and flag it.
4. For each failed checklist item: state precisely why it failed. Do NOT attempt to complete it.
5. Write reports/recovery-report-<date>.md with the full accounting. Commit, push, confirm CI, and END. Do not proceed to any other phase; the human decides what happens next.
```

---

## MONDAY — the prompt to give Claude for the independent audit

Paste this to Claude on Monday (this is for Claude, not Codex):

```
Monday audit. Repo: https://github.com/hafizmirhamza276-lab/Research-paper-AEP.git — clone it and perform a fresh, adversarial audit of the weekend's work (every reports/ file after the 4B handoff), executed by a different model (Codex) under bounded prompts stored in WEEKEND_CODEX_PROMPTS.md.

(1) BOUNDS AUDIT first: for each weekend report, diff its section B file list against its prompt's SCOPE BOUNDS in WEEKEND_CODEX_PROMPTS.md, and independently verify via git log/diff that no out-of-bounds file changed. Check rule 10: no force-pushes, no amended/rewritten history, no deleted reports, no edits to frozen results (verify archive hashes). Check rule 9: no evidence of external uploads.

(2) CLAIMS AUDIT: spot-verify each report's claims against code and results. Specifically: do the G3 B4/B4b numbers in the paper match the frozen archive when regenerated via committed generators (run make reproduce-figures yourself); do check_paper_numbers.py and verify_refs.py actually pass (run them); did any G4 UNDEFENDED item vanish instead of landing in the 5A adjudication table; is CI genuinely green on head with gates intact (zero-skip, citation ranges, digest pin); does any report contain a prose claim with no raw output behind it; did reproduce-smoke really run from a clean clone.

(3) MANUSCRIPT READ: judge abstract, introduction, evaluation, and threats-to-validity as a hostile TSE reviewer — is the detection-vs-prevention framing clean, is the B3-equivalence finding honestly placed, is any claim ahead of its evidence, did the 5C proofread stay within polish (no substantive drift)?

(4) VERDICT: deliver a final completeness percentage; a defect list from the weekend work (if any); and ONE clear verdict — SUBMIT NOW (arXiv + TSE), FIX FIRST (exact ordered fix list), or MAJOR GAP (what is missing). Be conservative: submission is irreversible and a week's delay costs nothing against a desk reject.
```

---

## Quick reference — expected completeness after each prompt

| After | Approx. completeness | Your go/no-go check |
|---|---|---|
| Handoff (now) | ~88% | — |
| Prompt 1 (4B closeout) | ~90% | Symmetric trilemma table + G4 list with ≥8 attacks |
| Prompt 2 (5A) | ~92% | Adjudication table covers 100% of UNDEFENDED items |
| Prompt 3 (5B) | ~94% | reproduce-smoke ran from clean clone; nothing uploaded |
| Prompt 4 (5C) | ~96–97% | verify_refs + numbers gates pass; nothing submitted |
| Prompt 5 (optional) | +1% | aep_core diff empty |
| Monday audit | decision point | Claude's verdict |
| arXiv + TSE submitted | 100% of submission milestone | journal review cycle begins |
