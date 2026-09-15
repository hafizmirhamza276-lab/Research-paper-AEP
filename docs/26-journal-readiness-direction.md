# AEP → Top-Tier Journal: Direction Document for LLM-Guided Completion

**Repository:** https://github.com/hafizmirhamza276-lab/Research-paper-AEP
**Paper:** *Declared Ambiguity: The Agent Execution Protocol (AEP) for Autonomous Agents Calling Non-Idempotent Legacy APIs*
**Primary target:** IEEE TSE (fallbacks: ACM TOSEM, IEEE TDSC, Middleware / DSN as conference-first path)
**Audit date:** 2026-09-02, against `main` @ commit "B21 item 4" (2026-09-01)
**Current verdict:** **NOT READY for a top-tier journal. Ready for arXiv. Estimated outcome if submitted to TSE today: Reject or Major Revision.** With the workstreams below (~5–7 focused weeks), the paper becomes competitive.

---

## 0. HOW TO USE THIS DOCUMENT (instructions to the LLM reading this)

You are being given this file so that you can act as the **research director** for a human who executes work through **Claude Code** inside the repository above. Your job:

1. Read this whole document first. Then read, in the repo, in this order: `README.md`, `ARTIFACT.md`, `PAPER_ROADMAP.md`, `reports/phase-report-6-audit-2026-08-21.md` (§S4.12 finding table), `docs/24-revision-backlog.md`, `paper/main.tex`, `paper/sections/06-evaluation.tex`, `paper/sections/08-threats.tex`.
2. Work through the **workstreams in §4 in priority order**. For each, produce **one Claude Code prompt at a time**, using the **prompt template in §6**. Do not batch many workstreams into one prompt — Claude Code performs best with bounded, verifiable tasks.
3. After the human pastes back Claude Code's report (`reports/phase-report-<N>-*.md`), **verify the acceptance criteria** of that workstream before issuing the next prompt. If criteria are not met, issue a corrective prompt, not the next task.
4. Enforce the **non-negotiable rules in §3** in every prompt you write. They are the reason this artifact is trustworthy; breaking them destroys the paper.
5. Track progress in the checklist in §7. The human's goal is to reach "Submission checklist: all green".

Language note: the human may communicate in Urdu/Roman Urdu/English. Prompts for Claude Code must be in **English**.

---

## 1. WHAT THE PROJECT IS (facts an LLM must not get wrong)

- **Contribution.** A fail-closed execution protocol for calling non-idempotent APIs that offer no idempotency key and may offer no read-back. Instead of promising exactly-once, it produces a third outcome class — *declared, durable, bounded ambiguity* — and fails closed. Three properties: P1 fenced state (lock-token + expected-version CAS in one Lua script), P2 detectable ambiguity (write-ahead intent + transition table with no re-entry into ABOUT-TO-FIRE), P3 fail-closed liveness bound.
- **Implementation.** Python 3.13, single Redis 7.2.5 (AOF, `appendfsync everysec`, `WAITAOF` barrier), `aep_core/`. 1734 tests, 91% coverage, CI against real Redis with 5 gates (zero skipped tests, zero xpassed, coverage ≥ 90%, citation-range validation of `docs/22-formal-model.md`, paper numbers vs frozen CSVs).
- **Baselines (all self-implemented).** B0 naive retry, B1 lease-only, B2 lease + CAS, B3 = AEP minus the WAITAOF barrier (ablation), B4 event-sourced durable-execution engine with unlimited retries (Temporal-default-like), B4b same with max attempts = 1.
- **Evaluation.** Fault-injection harness, real `SIGKILL` of a worker process at 6 named crash points × 3 endpoint reconciliation capabilities (AUTHORITATIVE_READBACK / POSITIVE_ONLY_READBACK / NO_READBACK) × 7 systems. 432 runs / 3 780 executions collected of a 1 068-run plan. Mock provider with an independent ground-truth ledger as oracle.
- **Headline results.** (a) AEP-full and B3: 0 undetected duplicates, 0 lost effects over 540 crashed executions each; B0/B1/B2/B4 duplicate in 53–83% of crashed executions; B4b loses effects in ~51–54%. (b) **Ablation:** detection is produced by the pre-dispatch record + no-re-entry, *not* by the fsync barrier. (c) **Prevention:** under a hard Redis kill before acknowledgement, on NO_READBACK, AEP-full applied 10/30 unwanted effects vs B3 28/30 (Fisher p = 1.9e-6), replicated 4× at 4–20/30 — magnitude is a race with `docker kill` latency. (d) **Durability premise:** process kill loses 0/10 unfsynced writes (page cache survives); dm-flakey block-level write loss destroys 90/90 unacknowledged vs 0/90 acknowledged. (e) **Cost:** barrier costs ~983 ms per round trip under `everysec` (two per step → ~2 s over a 2 s provider floor), ~15 ms under `always`; everything else costs 28 ms.
- **Paper state.** 21 pages IEEEtran, 9 sections, 34 references, single author, `paper/generated/*.tex` machine-written from frozen CSVs (never hand-edit), anonymous and public builds via `scripts/build_paper.sh`.
- **Platform every number was collected on:** Ubuntu inside **WSL2 on Windows 11 with Docker Desktop**. Single host, single author.

---

## 2. AUDIT: WHY IT IS NOT READY YET

Ordered by how a TSE reviewer would weight them. The project's own audits (Phase 6, `reports/phase-report-6-audit-2026-08-21.md`) already found most of these; the items marked **[NEW]** are additional findings from this external audit.

### Blockers (any one alone gets a reject or a desk-return)

| # | Finding | Evidence | Why it blocks |
|---|---|---|---|
| A1 | **Title/framing says "Autonomous Agents"; the evaluation contains no agent.** "agent" occurs 0 times in `03-model`, `04-protocol`, `05-implementation`, `06-evaluation`, `09-artifact`; no LLM anywhere in `experiments/`. | Roadmap item T6, audit S4.6 (MAJOR). | A reviewer's first note will be "the framing is decorative". Undermines the motivation, the related work positioning, and the title. **A decision the author must make (§4, WS-1).** |
| A2 | **Raw run archive, `results/voided/`, and SHA-256 manifest are not published; no immutable release/DOI.** `09-artifact.tex` availability sentence is currently false. | Cover letter §Artifact; `ARTIFACT.md` §5. | Any artifact-badging venue requires it; TSE reviewers will check. |
| A3 | **The prevention result (the barrier's only measured benefit, and the paper's most novel mechanism C2) is one cell, one crash point, one capability class, one host, and its magnitude is a fault-injector timing artifact** (4–20/30 across sessions; kill latency +194 ms in runs that applied an effect, p=0.00005). | §VI-C2, §VIII-A(e), `reports/phase-report-9c-result-2026-08-21.md`. | Reviewers will ask why the race was not controlled. It *can* be controlled (§4, WS-3). Leaving it as "a draw from a distribution" invites "then the result is not about the protocol". |
| A4 | **All measurements from WSL2 + Docker Desktop on Windows, one machine.** Timing numbers rest on 3 runs per arm; the `always` barrier-cost CI is [-1 474.6, 22.7] ms (contains zero). | §VIII-C(c),(e); Table XI footnotes. | For a systems/reliability paper this is a credibility problem independent of the numbers. Cheap to fix (cloud Linux VM). |

### Major (each costs a round of revision)

| # | Finding | Why it matters |
|---|---|---|
| M1 | **Every baseline was written by the author.** B4 "is not Temporal" (§VIII-A(i)). | Reviewers of TSE/TOSEM will ask: Temporal is open source and runs in Docker — why not run the real engine in both configurations? Running real Temporal (and ideally one more: e.g., Restate, Inngest, or Azure Durable Functions emulator) as B4/B4b converts the weakest external-validity point into a strong one. |
| M2 | **B1 — protocol outcomes under block-level write loss — was never run.** The paper calls it "the most worthwhile single extension" and did not do it because of a Docker Desktop bind-mount limitation. | Same fix as A4: a native Linux host removes the blocker. Turns the durability claim from "premise + argument" into a system-level result. |
| M3 | **Statistical precision is inadequate for several stated comparisons**: 3 crash-free runs per timing cell; the AUTH×redis-kill comparison's session-clustered interval is [-21.4, +46.4] pp; equivalence margin ±5 pp is post hoc. | These are all *sample size* problems, not design problems. More runs, on a quiet Linux host, fix them. Pre-register the run counts. |
| M4 | **Related work is thin: 34 references.** TSE regular papers typically carry 60–100. Missing literatures: idempotency-key practice (Stripe/AWS design notes), transactional outbox/inbox patterns, Kafka exactly-once semantics, saga/compensation literature beyond the 1987 paper, LLM-agent reliability and tool-use safety (e.g., ToolEmu, AgentBench-style evaluations, agent-failure taxonomies), agent frameworks' retry semantics (LangGraph, AutoGen, OpenAI Agents SDK, MCP), human-in-the-loop / escalation in autonomous systems, formal results on the two-generals / coordinated-attack problem in the applied setting. | Positioning is what wins or loses novelty arguments. |
| M5 | **Length and tone.** 17 000 words in sections (evaluation 6 374, threats 4 258), 21 pages. The prose repeatedly undercuts its own results ("worth nothing", "thinner than", "the uncomfortable reading", "we would rather say so"). | Honesty is an asset; *performative* self-doubt is not. Reviewers read "our most novel mechanism serves the claim with the narrowest evidence" and conclude "not yet". **Fix the evidence (WS-3, WS-4), then rewrite the threats section as a compact, neutral limitations section.** Target ≤ 16 pages main text + supplementary material. |

> **AMENDED 2026-09-15, phase 33. The 16-page target is withdrawn on
> evidence.**
>
> Three passes measured the same exchange rate: **~950 words per page**.
> Phases 27, 30, 31 and 32 removed or moved what could be removed or moved
> without deleting evidence, and the paper went 25 — 23 pages.
>
> What is protected, and why the remaining distance cannot be closed:
>
> * **§VI's four headline blocks, 4 035 words** — RQ1, detection,
>   prevention, durability. These are the measured guarantees the paper
>   exists to report.
> * **§VII's positioning, 1 498 words** — the durable-orchestration line,
>   what an idempotency-key contract requires of the *server*, why not
>   two-phase commit. WS-8 built these deliberately and a reviewer checks
>   them.
>
> Reaching 16 needs ~5 000 further words, and there is nowhere to take them
> from except those two sets. **That is a scope decision — which results
> are main text — not a compression problem, and the author declined it.**
> A 16-page version of this work exists; it is a different paper.
>
> **The revised target is 23 pages**, which is where the paper now stands.
> Tone, M5's other half, is complete: the four phrases M5 named are gone
> (phase 27), and the passage that undercut the paper's own novelty claim
> was rewritten once WS-5 made it inaccurate.

| M6 | **Properties P1–P3 are "argued from code paths, not model-checked"** (Table IV non-claim). | A TLA+ (or Alloy) model of the intent transition table + lease/CAS fencing is a few hundred lines and directly converts a non-claim into a contribution. Also strengthens C1. Optional in the roadmap (3A); this audit recommends doing it. |
| M7 | **Declared ambiguity is not evaluated as an operational outcome** (§VIII-A(j)); there is no escalation mechanism. | Full operator study is out of scope. But a *bounded* analysis is feasible: queue-growth model under measured ambiguity rates, plus a minimal escalation hook (webhook/log sink) so "escalates" is not "pauses silently". |
| M8 | **[NEW] AI-assistance disclosure.** The repository is transparent that Claude Code / Codex generated substantial code and prose (`AEP_CLAUDE_CODE_BUILD_PROMPT.md`, `CODEX_PROMPTS.md`, `prompts/`). IEEE and ACM now require disclosure of generative-AI use in manuscripts. | Add a disclosure paragraph (acknowledgements / methods) and make sure it matches venue policy. Not doing so is a policy violation, not a stylistic choice. |
| M9 | **[NEW] Uncollected-but-implemented cells**: 30%-crash regime, in-flight Redis kill, alternative read-back keying, one incomplete run. | Cheap (hours). Removes four "named gaps" from §VIII-C(f). |
| M10 | **[NEW] Single author, no affiliation.** | Not a scientific defect, but TSE reviewers weight independent replication. At minimum, get one external person to run `make reproduce-smoke` and `make reproduce-figures` on a different machine and record it (§VIII-A(f) says "we know of no way" — this is the way). |

### Minor

- `paper/arxiv-metadata.md` counts-only gate not in CI; `verify_refs.py --offline` not in CI (both noted in roadmap).
- Contribution list C1–C4 is long; C2 (dispatch guard) reads as over-engineered relative to its evidence. Consider demoting C2 to an implementation detail unless WS-3 strengthens prevention.
- Figures 1–3 exist; a **figure of the protocol sequence with the six crash points overlaid** would replace half a page of prose.
- Abstract is ~400 words and contains raw statistics; TSE abstracts should be ≤ 250 words, numbers minimal.
- Cover letter says "The authors" while the paper has one author.

---

## 3. NON-NEGOTIABLE RULES FOR EVERY CLAUDE CODE PROMPT

Include these verbatim (or by reference to this section) in every prompt. They are already the project's rules; breaking them silently invalidates the artifact.

1. **Never hand-edit `paper/generated/*.tex`.** Regenerate via `scripts/paper_tables.py` / `make reproduce-figures`.
2. **Frozen results are immutable.** Never modify anything under `experiments/results/**` from a previous collection. New collections go in new dated directories and are added to the manifest.
3. **Numbers discipline.** Every numeric claim in the manuscript carries a LaTeX comment naming its CSV cell; `scripts/check_paper_numbers.py` must pass. `analysis/table-1.csv` (pooled) is a banned source for rates.
4. **Prompt provenance.** Before a phase's first data commit, commit the issued prompt to `prompts/phase-<N>-<slug>.md`. Corrections to the prompt are recorded alongside it, never silently applied.
5. **Pre-register before collecting.** For any new experimental cell: commit a prediction file (`reports/phase-report-<N>-prediction-<date>.md`) with the hypothesis, run counts, unit of analysis, stopping rule, and the exact analysis to be run — *before* data exists.
6. **Unit of analysis is the run (or session), never the execution**, unless independence is demonstrated.
7. **No test may skip.** CI gates: zero skipped, zero xpassed, coverage ≥ 90%, citations valid, paper numbers match.
8. **Record environment.** Every new run records `redis_storage_backing`, kernel, filesystem, host identity, docker version, and the fault-injector latency where applicable.
9. **Test-instance safety.** Destructive cleanup requires `aep:test-instance-marker`. Never run the test suite against a Redis a matrix is collecting on.
10. **Every phase ends with a report** in `reports/phase-report-<N>-<slug>-<date>.md` stating: what was asked, what was done, what changed in the paper, what was *not* done and why, raw command outputs for headline numbers.
11. **Tone rule for prose edits.** Honest and precise, never apologetic. State the scope of a result once, in the place it belongs (limitations), not three times.
12. **One bounded task per prompt.** Claude Code should not "also fix" unrelated things. If it finds a defect outside scope, it records it in the report as a finding and stops.
13. **A gate that cannot fail is decoration.** Before a check is treated as evidence, exercise the branch on which it *fails* and confirm it does. A check only ever run against data that satisfies it establishes nothing, and reads exactly like one that works. Applies to test assertions, verification scripts, self-tests, and any "we confirmed X" in a report.
14. **A script whose output is load-bearing lives in `scripts/` with a test.** If a number reaches a report, a commit message, or the manuscript, the thing that produced it is committed and pinned. A number only one machine can reproduce is not evidence, and a one-off that is going to be re-run is a hand-assembly defect waiting to happen.

**Rules 13 and 14 came from practice, not from the original list**, and are recorded here because §3 says these rules go into every prompt verbatim or by reference — so a rule that is *not* here does not propagate, however consistently it is being followed. That gap has already had a visible consequence: a prompt cited "rule 13" as though it existed when §3 stopped at 12, because the practice was real and the text had never caught up.

*Where each was learned.*

- **13** — WS-1a §2.3. An attribution repair was about to ship with a proof that would have *passed* while never exercising the code it existed to validate: on the frozen data the fallback fires on every row, so the new path is never reached. The fix was a paired fixture in which the two attributions disagree. The same shape recurred three times afterwards — the WS-4 delivery gate (built by proving it *rejects* a drop that did not take effect), the `dm-flakey` self-test restore (proven by forcing the reload to fail), and the write-loss injector's malformed table, which returned exit 0 from every call while arming nothing. `docs/25` R3 states the collection-tooling form of this; rule 13 is the general one.
- **14** — Phase 13. The Arm A session-results files were assembled by hand, and `scripts/render_session_results.py` was promoted only afterwards, once it could be shown to reproduce them byte-for-byte. `distil_session_fixture.py` closed the same defect one level down, and `analyse_model_gap.py` closed it for a note whose every number had come from throwaway probes. Each promotion was prompted by the same observation: the artefact was already being relied on.

---

## 4. WORKSTREAMS (priority order)

Each workstream: goal → why → tasks → acceptance criteria → effort → dependencies. The LLM director turns each *task* into one Claude Code prompt using the §6 template.

### WS-0 · Environment: get off WSL2 (prerequisite for WS-3, WS-4, WS-5)

**Goal.** A native Linux host (bare metal or cloud VM: e.g., 4 vCPU / 8 GB, Ubuntu 24.04, native Docker Engine, NVMe/SSD) where loop devices, dm-flakey, and containers share one namespace.
**Why.** Unblocks B1 (M2), removes the WSL2 credibility issue (A4), and gives the quiet host needed for timing (M3).
**Tasks.**
- 0.1 Write `docs/26-measurement-host.md`: host spec, provisioning script (`scripts/provision_host.sh`) that installs pinned Docker Engine, `uv`, `dmsetup`, verifies `redis:7.2.5-alpine@sha256:6aaf3f5e...` digest, disables suspend, sets CPU governor to `performance`.
- 0.2 Run `make reproduce-smoke` and the full test suite there; record outputs in `reports/phase-report-10-host-2026-XX.md`.
- 0.3 Re-collect **one** already-frozen cell (e.g., AEP-full × NO_READBACK × crashed) as a cross-host replication and diff against the frozen CSV. This becomes a paragraph in §VIII (external validity) *in the paper's favour*.
**Acceptance.** Suite passes (1734+ tests, 0 skipped); smoke passes; cross-host replication reported with run-clustered interval; host recorded in every subsequent run's metadata.
**Effort.** 1 day + ~$20–40 of cloud time for the whole project.

### WS-1 · Framing decision (T6) — the author decides, the LLM helps cost it

**DECIDED 2026-09-04: Option B.** The agent workload goes ahead; design in
`docs/33-agent-workload.md` (numbered 33, not the 27 named below — 27 was taken
by `27-measurement-host.md`).

**Option B has since been split into two workstreams.** Designing it surfaced a
prerequisite that is not part of the workload and is much larger than "a metric
repair": the published duplicate metric attributes ledger rows to executions by
`target`, which is sound only because each execution owns its resource — and the
agent workload removes that property for all seven systems. Fixing it needs a
ledger schema change, four proofs and a §VIII threat statement.

* **WS-1a · Attribution** — the execution-id repair. `docs/33` §2. Blocks WS-1b
  entirely. Eleven acceptance items, four of them proofs, one of them a
  manuscript change.
* **WS-1b · The agent workload** — tools, planners, plan drift. `docs/33` §§1,
  3–5. Task list 1B.1–1B.5 below belongs here.

The two options below are retained as the record of the decision, not as an open
question.

Two options. **Pick one within the first week; every prose task downstream depends on it.**

**Option A — Retitle around the API problem (recommended if time < 6 weeks).**
New working title: *Declared Ambiguity: Fail-Closed Execution for Non-Idempotent Legacy APIs Without Idempotency Keys*. Agents become the *motivating deployment context* in §I and §II (one paragraph each, well cited), not the subject.
- Tasks: 1A.1 rewrite title/abstract/§I to make "callers that cannot be made idempotent" the subject and autonomous agents the leading example; 1A.2 sweep every "agent" in the manuscript and either justify or remove; 1A.3 update `CITATION.cff`, `arxiv-metadata.md`, cover letter, README.
- Acceptance: a grep for "agent" in the manuscript returns only §I/§II/§VII motivation uses; abstract ≤ 250 words; no claim about agents is made that the evaluation does not support.
- Effort: 1–2 days, 0 experiments.

**Option B — Make agents load-bearing (choose only if ≥ 6 weeks available and WS-0 done).**
Add a workload in which a small LLM (or a scripted nondeterministic planner as a control) chooses which of several non-idempotent tools to call and with what arguments, driving the same harness; measure the same three outcomes plus a new one: *plan drift* after recovery (does the agent re-plan a duplicate action once the intent is ambiguous?). This is Phase 3C in the roadmap.
- Tasks: 1B.1 design doc `docs/27-agent-workload.md` (tool schema, planner interface, determinism controls, seeds); 1B.2 implement `experiments/workloads/agent_planner.py` with a scripted planner *and* an LLM planner behind one interface; 1B.3 pre-register; 1B.4 collect AEP-full, B3, B0, B4 under the agent workload on NO_READBACK and POS_ONLY; 1B.5 add §VI-F "Under an agent workload" and rewrite §I/§II.
- Acceptance: agent-workload cells in `per-cell-metrics.csv`; paper's agent claims each cite a cell; LLM planner run is reproducible from recorded prompts/responses (log every call).
- Effort: 1.5–3 weeks.

### WS-2 · Publish the artifact properly (A2)

**Tasks.**
- 2.1 Build `scripts/build_raw_archive.py`: collect the 432 run directories + `results/voided/` into a deterministic tarball; emit `MANIFEST.sha256` (per file) and a top-level digest; verify against the tracked CSVs by re-running `analyze.py` on the archive and byte-comparing.
- 2.2 Upload to Zenodo (or Figshare); record the DOI; tag `v1.0.0` on the exact commit; add the DOI to `ARTIFACT.md`, `09-artifact.tex`, `CITATION.cff`, README.
- 2.3 Add a CI job that downloads the archive by DOI (or checks its digest from a cached copy) and re-derives `per-cell-metrics.csv`.
- 2.4 Ask one external person to run `make reproduce-figures` and `make reproduce-smoke` on their machine; record their output and host in `reports/external-replication-1.md` (M10).
**Acceptance.** `09-artifact.tex` availability sentence is true; DOI resolves; CI reproduces derived CSVs from the archive; one external replication recorded.
**Effort.** 1–2 days (plus waiting on the external person).

### WS-3 · Make the prevention result a property of the protocol (A3)

**Goal.** Replace "one draw from a docker-kill latency distribution" with a controlled fault.
**Why.** The race is: AEP-full dispatches iff `WAITAOF` returns before Redis dies. Controlling *when* Redis dies relative to `WAITAOF` makes the result deterministic and separable.
**Tasks.**
- 3.1 Design `docs/28-controlled-redis-fault.md`. Candidate mechanisms, choose after measurement: (a) `docker pause` (SIGSTOP the container) at the instrumented point *before* the `WAITAOF` call is issued, then `docker kill`; latency of `pause` is ~ms and it is synchronous; (b) `iptables`/`nftables` DROP on the Redis port after the intent CAS returns, so `WAITAOF` cannot return, then kill; (c) `tc netem` to add deterministic delay to the Redis socket so the kill always lands first. Measure the landing latency of each mechanism 100× and pick the one with the smallest, tightest distribution. Record the distribution in the paper.
- 3.2 Add the mechanism as a new regime (`REGIME_REDIS_KILL_PREACK_CONTROLLED`) without touching the existing regime; extend the harness to record fault-landing latency per run.
- 3.3 **Pre-register**: prediction that AEP-full unwanted-applied → ~0/30, B3 → ~30/30 under the controlled fault, across **all three** capability classes, k = 3 sessions each, interleaved; unit = run; report run-clustered intervals.
- 3.4 Collect on the WS-0 host. Also collect the **in-flight** Redis-kill variant (predicted tie) — M9.
- 3.5 Rewrite §VI-C2: lead with the controlled result; keep the original `docker kill` cell as the "uncontrolled fault" replication that agrees in direction; delete the language that presents the magnitude as unknowable.
**Acceptance.** Controlled-fault cells for AEP-full and B3 on AUTH/POS_ONLY/NONE with ≥ 3 sessions each; fault-landing latency reported with a distribution; the paper's prevention paragraph no longer depends on host docker latency; Table IX has a controlled row.
**Effort.** 3–4 days.

### WS-4 · Run the protocol under write loss (M2 / backlog B1)

**Tasks.**
- 4.1 On the WS-0 host, put the harness's Redis `dir` on the dm-flakey-backed ext4 (design already in `docs/24-revision-backlog.md` B1). Verify `redis_storage_backing` is recorded and differs from frozen runs; state this in the report.
- 4.2 Pre-register: AEP-full withholds dispatch when its record is destroyed; B3 proceeds. 30 runs × 10 executions per arm, NO_READBACK first, then AUTH if time allows.
  - **STATUS 2026-09-11: COLLECTED AND REFUTED, not open.** Pre-registered
    `d8b2ca5`, collected `252e2d3`, 60 runs in
    `reports/raw/ws4-writeloss-s1-2026-09-07/` (30 per arm, NO_READBACK).
    Verdict `REFUTED`: AEP-full applied 285/300 = 0.9500 against a refutation
    threshold of 0.2; B3 287/300 = 0.9567, at ceiling. Both arms zero on lost
    effects and duplicates. The prediction is false as written — AEP-full did
    not withhold — because `WAITAOF` returned success after the device stopped
    accepting writes, so the barrier never met the failed acknowledgement its
    guarantee is defined over. Reported in §VIII construct validity. The AUTH
    half was not collected.
- 4.3 Collect; analyse with the existing unwanted-applied-effect metric + duplicates/lost effects.
- 4.4 Add to §VI-C3 as the system-level result the paper currently says it lacks; update Table XI's "prevents" column semantics.
**Acceptance.** Protocol-level outcomes measured under write loss; §VIII-A(b) "we have not done it" sentence removed; storage backing difference explicitly stated.
**Effort.** 2–3 days.

### WS-5 · Statistical power and remaining cells (M3, M9)

**Tasks.**
- 5.1 Pre-register run counts for timing: ≥ 15 crash-free runs per arm for AEP-full/B3/B0 under both `everysec` and `always` (the intervals in Table XI must exclude zero where the point estimate is > 0, or the claim is dropped).
- 5.2 Collect the 30%-crash regime for all 7 systems on the three capability classes (fills the "nothing in between" gap).
- 5.3 Collect the alternative read-back keying sensitivity variant.
- 5.4 Re-collect the one incomplete run.
- 5.5 Replace the post-hoc ±5 pp equivalence margin with a pre-registered TOST (two one-sided tests) at the run level, or drop the equivalence language and report only the bound.
**Acceptance.** Every interval quoted in Tables X–XI has ≥ 15 clusters; §VIII-C(f) gap list shrinks to at most the AUTH×controlled-kill items not yet collected; no post-hoc margin remains.
**Effort.** 2–3 days of mostly unattended collection.

### WS-6 · Real durable-execution engine as baseline (M1)

**Tasks.**
- 6.1 `experiments/baselines/b5_temporal/`: Temporal server (docker compose, pinned image), a worker whose activity calls the mock provider, two configurations: `maximumAttempts` unlimited (default) and `= 1`. Crash injection via `SIGKILL` of the worker process at the same six crash points (map Temporal's activity lifecycle to them; document the mapping in `B5_SEMANTICS.md`).
- 6.2 Optional second engine if cheap (Restate or Inngest dev server).
- 6.3 Pre-register: B5 reproduces B4's duplicate rates and B5b reproduces B4b's lost-effect rates within run-clustered intervals.
- 6.4 Collect on NO_READBACK and AUTH; add rows to Table VI; rewrite §II-C/D and §VIII-A(i) ("B4 is not Temporal" becomes "B4 is our model; B5 is the vendor's engine and behaves the same").
**Acceptance.** Real-engine rows in Table VI; "self-implemented baselines" threat reduced to B0–B3 which are trivial.
**Effort.** 3–5 days.

### WS-7 · Formal model in TLA+ (M6)

**Tasks.**
- 7.1 `formal/AEP.tla` + `AEP.cfg`: model the intent state machine (NONE → ABOUT-TO-FIRE → FIRED-UNCONFIRMED → {FIRED-CONFIRMED, FAILED-CONFIRMED, PERMANENTLY-AMBIGUOUS}), lease acquire/expire/renew, CAS with expected version + token, worker crash at each of the six points, recovery. Check invariants: P1 (no stale writer commits), P2 (no re-entry into ABOUT-TO-FIRE; every durable intent reaches exactly one terminal state), and the *trilemma invariant* (no history contains an undetected duplicate or a lost effect). Deliberately include the model without the barrier to show P2 holds without it — matching the ablation.
- 7.2 Add a CI job running TLC on the model (bounded: 2 workers, 3 versions).
- 7.3 New §IV-D "Model checking" (½ page) and remove the "Machine-checked proofs" row from Table IV.
**Acceptance.** TLC passes in CI; the paper states the bounds checked; the AOF-rewind residual is shown as a counterexample when the "single timeline" assumption is removed (this is a strong, honest figure).

**DEFECTS IN THIS ENTRY, found while executing it (2026-09-10). Recorded, not
fixed -- 7.1 and 7.2 above are left as written, because this file is a record of
what was directed as well as a direction, and a brief that is silently corrected
afterwards cannot be audited against what was built.**

*(a) The state-machine sketch in 7.1 is missing four of the code's ten edges.*
`LEGAL_INTENT_TRANSITIONS` (`aep_core/core/intents.py:65-96`, re-implemented in
Lua at `:449-461`) has ten. The sketch omits `ABOUT_TO_FIRE -> FIRED_CONFIRMED`
and `ABOUT_TO_FIRE -> FAILED_CONFIRMED` -- **the ordinary path every non-crashed
dispatch takes** -- the `FIRED_UNCONFIRMED` self-loop that the P3 reconciliation
budget counts on, and the two operator edges out of `PERMANENTLY_AMBIGUOUS`.
Read literally it also implies a direct `ABOUT_TO_FIRE -> PERMANENTLY_AMBIGUOUS`
edge, which does not exist: escalation must pass through `FIRED_UNCONFIRMED` via
the recovery claim, and that claim is what advances the version and consumes the
lease, which is in turn what stops a late original worker from persisting its
own resolution. A model built from the sketch would have been a model of a
different protocol, and would have verified cleanly.

The manuscript is unaffected -- section IV defers to
`scripts/gen_state_machine.py`, which imports the edge set from the code.
`formal/AEP.tla` was transcribed from the code for the same reason, and
`scripts/check_tla_transitions.py` now fails if the two ever disagree.

*(b) "2 workers, 3 versions" in 7.2 is too shallow to be the CI bound.* At
`MaxVersion=3` the `operator` configuration cannot reach `PERMANENTLY_AMBIGUOUS`
at all, so the operator edge out of it is unreachable, its counterexample does
not exist, and the configuration **passes** -- turning one of the nine
must-fail configurations into a check that cannot fail, with no outward sign.
CI therefore runs the committed bound of 5 versions, which costs 137s for all
fifteen configurations against 58s for three. `formal/README.md` section 4.3 has
the measurements. The defect was caught only because `scripts/run_tlc.sh` holds
each configuration to a declared expectation instead of reporting a green tick.

*Also worth recording: 7.3 budgets half a page for section IV-D and it came out
at one.* The overrun is the nine failing configurations and the scoping
paragraph, both directed explicitly, and both the section's substance.

**Effort.** 3–4 days.

### WS-8 · Related work and positioning (M4)

**Tasks.**
- 8.1 Literature sweep (use web search) for the missing literatures listed in M4; target 65–85 references; every added reference must be cited in prose, not dumped.
- 8.2 Rewrite §VII around three questions: (i) what does each prior system *require of the endpoint*; (ii) can it *report unknown*; (iii) what is its *residual when the assumption fails*. Table XII already has this shape — extend it.
- 8.3 Add a short §VII-F on agent-framework retry semantics (only if WS-1 Option A: as motivation; if Option B: as direct comparison).
- 8.4 Run `scripts/verify_refs.py --offline` and wire it into CI.
**Acceptance.** ≥ 65 references, all resolvable (DOI/URL verified), `verify_refs` in CI, Table XII ≥ 12 rows.
**Effort.** 2–3 days.

### WS-9 · Manuscript rewrite for length, tone, structure (M5, minors)

Do this **after** WS-3/4/5 land, because the tone problem is downstream of the evidence problem.
**Tasks.**
- 9.1 Restructure to ≤ 16 pages main text: move §VI-C3 probe details, §VIII-B(a–c) incident narratives, and the per-session tables to a supplementary PDF (`paper/supplementary.tex`), leaving one paragraph each in the main text.
- 9.2 Rewrite §VIII as a conventional *Threats to Validity* of ≤ 1.5 pages: construct / internal / external / conclusion validity, each threat stated once, neutrally, with its mitigation. Remove self-referential commentary about earlier drafts ("an earlier draft of this paper…") — it belongs in the changelog, not the manuscript.
- 9.3 Abstract ≤ 250 words, ≤ 3 numbers.
- 9.4 Contributions: reduce to 3 (formulation + protocol/implementation, evaluation, ablation decomposition); fold the dispatch guard into §IV/§V.
- 9.5 Add the protocol-sequence figure with crash points overlaid (TikZ), and a figure for the controlled prevention result from WS-3.
- 9.6 Add AI-assistance disclosure (M8) in Acknowledgements per IEEE policy; add author affiliation; fix "The authors" in the cover letter.
- 9.7 Full copy-edit pass; run a reading-level check; ensure every table caption is ≤ 3 sentences.
**Acceptance.** `main.pdf` ≤ 16 pages + supplementary; `check_paper_numbers.py` passes; grep for "earlier draft", "we would rather", "worth nothing", "uncomfortable" returns 0; anonymous build leaks nothing (`scripts/check_anonymity.sh` or equivalent).
**Effort.** 4–5 days.

### WS-10 · Submission package

- 10.1 Final pre-registration audit: for every cell added in WS-3/4/5/6, the prediction file's commit predates the first data commit (script it: `scripts/check_prereg_order.py`).
- 10.2 One more **independent adversarial audit pass** by a *different* LLM than the one that wrote the prose (the project's Phase 6 pattern), against the §7 checklist. Verdict must be SUBMIT.
- 10.3 arXiv preprint (cs.SE primary, cs.DC secondary) with the DOI'd artifact.
- 10.4 TSE submission: anonymous PDF, supplementary, cover letter (updated), artifact DOI, AI-disclosure form.

---

## 5. RECOMMENDED SEQUENCE AND CALENDAR

| Week | Workstreams | Output |
|---|---|---|
| 1 | WS-0, WS-1 decision, WS-2.1–2.3 | Linux host live; framing decided; archive + DOI |
| 1+ | **WS-1a (attribution)** — blocks WS-1b | Execution-id attribution; four proofs; §VIII threat stated |
| 2+ | **WS-1b (agent workload)** — only after WS-1a | Agent cells; plan-drift metric; §VI-F |
| 2 | WS-3 (controlled prevention), WS-5 collection running unattended | Controlled prevention cells; timing intervals |
| 3 | WS-4 (write loss), WS-6 (real Temporal) | System-level durability result; real-engine baseline |
| 4 | WS-7 (TLA+), WS-8 (related work) | Model checked in CI; 65+ refs |
| 5 | WS-9 (rewrite), WS-2.4 external replication | ≤ 16-page manuscript, supplementary |
| 6 | WS-10 | Audit → arXiv → TSE |

If only **3 weeks** are available: WS-0, WS-1 Option A, WS-2, WS-3, WS-5, WS-9 (tone only), WS-10. Skip WS-4/6/7 and keep them as honest, *briefly* stated limitations. This yields a solid TOSEM/TDSC submission and a plausible TSE one.

---

## 6. PROMPT TEMPLATE FOR CLAUDE CODE (the LLM director fills this in per task)

```
# Phase <N> — <workstream id>.<task id>: <one-line task name>

## Read first (do not skip)
- AEP_JOURNAL_READINESS_DIRECTION.md §3 (rules) and §4 <WS-id>
- <list of 3–6 specific repo files relevant to this task, with line ranges if known>
- The most recent report in reports/ for this workstream, if any

## Context
<2–4 sentences: what this task is, why it matters to the paper, what the acceptance criteria are. Quote the exact claim in the paper it affects, with the .tex file and line.>

## Bounds
- In scope: <exact files/dirs that may change>
- Out of scope: <explicit list — especially experiments/results/** (frozen), paper/generated/** (regenerate only), unrelated tests>
- If you find a defect outside scope: record it in the report under "Findings outside scope" and do not fix it.

## Steps
1. Commit the issued prompt as prompts/phase-<N>-<slug>.md before anything else.
2. <If experimental:> Write and commit reports/phase-report-<N>-prediction-<date>.md with hypothesis, run counts, unit of analysis, stopping rule, exact analysis command — BEFORE collecting any data.
3. <numbered concrete steps>
4. Run: uv run --frozen pytest -q -ra --strict-markers --cov=aep_core --cov-fail-under=90 ; uv run --frozen python scripts/validate_citations.py ; uv run --frozen python scripts/check_paper_numbers.py ; make reproduce-figures
5. Rebuild the paper both ways: bash scripts/build_paper.sh && bash scripts/build_paper.sh --anonymous

## Acceptance criteria (all must be true)
- <copy from §4, made concrete>
- All CI gates green; 0 skipped tests
- Every new number in the manuscript has a provenance comment naming its CSV cell

## Report
Write reports/phase-report-<N>-<slug>-<date>.md with sections: Asked / Done / Paper changes (file:line) / Not done and why / Raw outputs for every headline number / Findings outside scope / Environment (host, kernel, docker, redis digest, storage backing).
Do not summarise the report in chat beyond a 5-line pointer to the file.
```

**Director's checklist before sending a prompt:** one task only; read-first list present; bounds explicit; pre-registration step present if data is collected; acceptance criteria copied from §4 and made testable; report file named.

---

## 7. SUBMISSION READINESS CHECKLIST (the LLM director maintains this)

Mark each item `[x]` only after verifying the phase report and, where possible, the CI run.

**Evidence**
- [ ] Measurements exist from a native Linux host; cross-host replication of ≥ 1 frozen cell reported (WS-0)
      **Converted from blocker to declared limitation, phase 28.** Left
      unticked deliberately: the box describes work that has not been done,
      and ticking it would say otherwise. What changed is that it no longer
      blocks submission. WS-3, WS-4 and WS-5 are all complete on the WSL2
      host and moving now means re-collecting every one of them;
      `08-threats.tex` discloses the platform, the port forwarding and the
      development/measurement split, and now names the concrete future-work
      item: re-collect **one** frozen cell on bare metal --- the crash-free
      `everysec` AEP-full/B3 cell, thirty runs, about an hour --- rather
      than leaving "future work" open-ended beside absolute medians.
- [ ] Prevention result collected under a controlled Redis fault on all 3 capability classes, ≥ 3 sessions each (WS-3)
- [ ] Protocol outcomes measured under block-level write loss (WS-4)
- [x] Every timing interval rests on ≥ 15 runs; no CI containing zero is presented as a positive cost (WS-5)
- [x] 30%-crash regime, in-flight kill, read-back keying variant collected; zero "implemented but not collected" items remain (WS-5)
- [x] **WS-5 is closed to further collection** (amendment 4). The `always`
      arm is collected (45 runs, phase 21). The capability-class sweep
      **stays at four sessions by ruling**, reported as a bound with its
      0.125 sign-test floor stated, not as a test: the four sessions are
      cell-major and pre-date `5b601d0`'s interleaving, so a fifth and
      sixth would have mixed two designs. Nothing in WS-5 is now
      "implemented but not collected"; the class sweep is "collected and
      deliberately not extended", which is a different statement and is
      the one the paper must make.
- [ ] Real durable-execution engine run as baseline in both configurations (WS-6) — *or* explicitly deferred with one sentence
- [ ] TLA+ model of P1/P2 checked in CI (WS-7) — *or* explicitly deferred with one sentence
- [x] Every new cell has a pre-registration commit that predates its first data commit (`scripts/check_prereg_order.py`)
      **Audited across the whole history, phase 37: 31 cells, 27 ok, 4
      exempt, 0 failing.** Both orderings checked -- commit date and
      ancestry. The four exempt predate rule 5 (adopted 2026-08-27) or are
      not collections; they are printed as EXEMPT, not filtered out. In CI
      as the `prereg-order` job with `fetch-depth: 0`. The check's blind
      spots are printed on every run and listed in the phase 37 report §6 --
      the largest is that it reads commit ORDER, never the prediction's
      CONTENT, so early-committed-then-rewritten would pass.

**Artifact**
- [ ] Raw run archive + voided runs + SHA-256 manifest on Zenodo with DOI; tag `v1.0.0` (WS-2)
- [ ] CI re-derives `per-cell-metrics.csv` from the archive
- [ ] ≥ 1 external replication of `make reproduce-figures` / `reproduce-smoke` recorded
- [ ] `09-artifact.tex` availability statements are true

**Manuscript**
- [x] Framing decision executed (title, abstract, §I, §II consistent with evaluation) (WS-1)
      Verified phase 27: the title carries no "Autonomous Agents", §VI uses
      "agent" zero times, §I:7 scopes it as the motivating example, and §II:9
      states outright "It is a scripted caller, not an agent".
- [x] Main text at its measured floor; supplementary PDF exists (WS-9)
      **Target amended from ≤ 16 to 23 pages, phase 33** (see M5). The
      paper is 23 pages and the supplementary 6. Ticked against the amended
      target, not the original one: 16 was withdrawn on evidence rather than
      met.
- [x] **WS-9 closed.** Tone complete (phase 27). Compression complete
      (phases 27, 31, 32). Migration complete to the floor (phases 30, 33):
      the deployment table, RQ4 and the provably-empty-cell detail are in
      the supplementary; the four headline blocks and §VII's positioning
      stayed. 25 → 23 pages.
- [ ] Abstract ≤ 250 words
- [ ] ≥ 65 references, all verified, `verify_refs --offline` in CI (WS-8)
- [ ] Threats section ≤ 1.5 pages, neutral tone, no references to earlier drafts
- [ ] Protocol-sequence figure with crash points; controlled-prevention figure
- [ ] AI-assistance disclosure present and matches IEEE policy; affiliation present
- [ ] Anonymous build leaks no identity (text, URLs, PDF metadata)
- [ ] `check_paper_numbers.py`, `validate_citations.py`, `reproduce-figures` all green on the submission commit

**Process**
- [ ] Independent adversarial audit by a different LLM returns SUBMIT
- [ ] arXiv preprint posted
- [ ] Cover letter updated (single author, DOI, framing)

When every box is checked, the paper is ready for TSE. If WS-4/6/7 are deferred, it is ready for TOSEM/TDSC and *submittable* to TSE with a higher revision risk.

---

## 8. THINGS THE LLM DIRECTOR MUST NOT DO

- Do not let Claude Code "improve" frozen numbers, re-analyse old runs with a new unit of analysis without recording both, or delete voided runs.
- Do not accept a report that says "collected" without raw command output and the run-count per cell.
- Do not let the manuscript regain marketing language ("robust", "guarantees exactly-once", "solves") — the paper's credibility is its precision. Equally, do not let it keep self-undermining language once the evidence is fixed.
- Do not skip pre-registration to save time. A single un-pre-registered cell reintroduces the Phase 9C problem.
- Do not merge WS-1 Option A and Option B halfway (a title about agents with one token-count-based "agent" experiment is worse than either).
- Do not issue a prompt whose scope you cannot verify from the resulting report.
