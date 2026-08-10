# AEP → Top-Tier Journal Paper: Complete Roadmap

**Repository:** Research-paper-AEP
**Target venues (in order of fit):** IEEE TSE, ACM TOSEM, IEEE TPDS
**Recommended path:** arXiv preprint → conference/workshop (ICSE/FSE/EuroSys track) → extended journal version
**Hardware needed:** 1 local machine with Docker (no GPU required). Kaggle P100 optional for the LLM-agent workload in Phase 3C.

---

## CURRENT PHASE: Monday audit

The manuscript, the artifact and the submission package are prepared and **nothing has been submitted anywhere**. The next step is an independent adversarial audit by a different reviewer, per the prompt at the end of `WEEKEND_CODEX_PROMPTS.md`. The submit/hold decision is that audit's output, not this roadmap's.

**Phase status, each with the report that closed it:**

| Phase | Status | Report |
|---|---|---|
| 1A Formal model | ✅ complete | `reports/phase-report-1A-2026-08-05.md` |
| 1B Correctness fixes | ✅ complete | `reports/phase-report-1b-2026-08-05.md` |
| 2A CI / artifact hardening | ✅ complete | `docs/23-ci-hardening-report.md` |
| 2B-1 Mock provider + oracle | ✅ complete | `reports/phase-report-2b-session1-2026-08-05.md` |
| 2B-2 Crash-point harness | ✅ complete | `reports/phase-report-2b-session2-2026-08-05.md` |
| 2B-3 Baselines + matrix | ✅ complete | `reports/phase-report-2b-session3-2026-08-06.md` |
| 2B-3B Capability cells, Redis kill, RQ3 | ✅ complete | `reports/phase-report-2b-session3b-2026-08-07.md` |
| 4 Manuscript, first draft | ✅ complete | `reports/phase-report-4-session1-2026-08-07.md` |
| 4B Closeout + hostile pass (G3, G4) | ✅ complete | `reports/phase-report-4b-2026-08-07.md` |
| 5A Adjudicate the hostile pass | ✅ complete | `reports/phase-report-5a-2026-08-10.md` |
| P Numbers gate into CI | ✅ complete | `reports/phase-report-5b-2026-08-10.md` |
| 5B Reproducibility artifact package | ✅ complete | `reports/phase-report-5b-2026-08-10.md` |
| Q Portable byte guarantee (`.gitattributes`) | ✅ complete | `reports/phase-report-5c-2026-08-10.md` |
| 5C Submission-ready, not submitted | ✅ complete | `reports/phase-report-5c-2026-08-10.md` |
| 3A TLA+/property layer | ⬜ optional, not started | — |
| 3B Second workload | ⬜ optional, not started | — |
| 3C LLM-driven workload | ⬜ optional, not started | — |

Release tag `v1.0.0-rc1`. Artifact entry point: `ARTIFACT.md`. Open findings for the audit are in section G of the 5C report.

---


## 0. Where the project stands today (honest baseline)

**Strengths already in the repo:**
- Phase 1 fixed: true expected-version CAS + lock-token fencing, lease-loss cancellation, correct UUIDv4 validation, schema-version write gate.
- Phase 2 implemented: write-ahead intent ledger with exhaustive transition table, WAITAOF durability barrier (Redis 7.2, AOF), crash-recovery resolver, request vault/binding, **674 passing tests** (verified 2026-08-05 against real Redis 7.2.5 with AOF; the pre-Phase-1B baseline was 611. The figure previously stated here — "218" — was never verified and was wrong; see `reports/phase-report-1b-2026-08-05.md` §C.0 and §C.6 for the raw pytest output).
- 21 design/gate-review documents, Redis 7.2 compose config.

> **Phase 1B (correctness fixes) was inserted between Phase 1A and Phase 2A and is COMPLETE** — report: `reports/phase-report-1b-2026-08-05.md` (typed connector contract, recovery fault isolation, WAITAOF-ack-gated dispatch authorization, evaluation composition; 611 → 674 tests).

**What is missing for publication (the entire gap):**
1. No manuscript, no formal research question, no threat/failure model.
2. No experimental evaluation — unit tests are not research results.
3. No baselines or ablations.
4. No novelty positioning against prior work (Leases 1989, Sagas 1987, Beldi OSDI'20, ExoFlow OSDI'23, AIOS, ACRFence 2026, Temporal-style durable execution).
5. Incomplete reproducibility artifact (no CI, no lockfile, no artifact-evaluation package, no license/citation file).

Everything below closes these gaps in order.

---

## 1. The contribution statement (write this FIRST, before any more code)

Top-tier reviewers reject papers whose claims exceed their evidence. AEP's honest, defensible contribution is:

> **AEP is a fail-closed execution protocol for autonomous agents that call non-idempotent legacy APIs. Instead of falsely promising exactly-once semantics, AEP makes *ambiguity a first-class, durable, detectable state*: every external side effect is preceded by a durably-acknowledged write-ahead intent, every state write is fenced by lock ownership and exact expected-version CAS, and every unresolvable outcome halts and escalates rather than guessing. We show that under injected crashes, partitions, and Redis restarts, AEP achieves a zero *undetected*-duplicate rate and a bounded *known*-ambiguity rate, at modest latency/throughput overhead, whereas standard retry and lease-only baselines silently duplicate or lose effects.**

Three formal properties to state and evidence:
- **P1 (Fenced state):** No committed state write can be superseded-then-resurrected by a stale writer (expected-version + live-lock-token CAS, atomic in one Lua invocation).
- **P2 (Detectable ambiguity):** If a durably-acknowledged intent exists and the process crashes at any point around the external call, recovery always classifies the effect as CONFIRMED, REFUTED, or PERMANENTLY_AMBIGUOUS — never silently retried, never silently dropped. (Explicitly scoped: requires the WAITAOF ack; the residual pre-ack window is *declared*, not hidden.)
- **P3 (Fail-closed liveness bound):** Recovery terminates within a configurable attempt/duration budget and ejects to operator escalation.

**Non-claims (state these explicitly in the paper — reviewers reward this):** no exactly-once, no split-brain immunity, no HA/consensus, single-Redis trust domain.

### Claude Code prompt — Phase 1A
```
Read docs/01-hld.md, docs/02-tech-design.md, docs/06-phase2-design.md, and src/core/*.py.
Write docs/22-formal-model.md containing:
1. A precise system model: processes, single Redis 7.2 instance with AOF, network, clocks (no synchrony assumption beyond lease TTLs), the external legacy API with response classes AUTHORITATIVE_READBACK / POSITIVE_ONLY_READBACK / NO_READBACK.
2. A failure model: worker crash (SIGKILL) at any instruction boundary, network partition worker↔Redis, Redis restart with AOF replay, delayed/duplicated external responses, worker pause (GC/VM stall) past lease expiry.
3. Formal statements of properties P1, P2, P3 (as given in PAPER_ROADMAP.md §1), each mapped to the exact Lua script / code path that enforces it, and each with its explicitly declared residual window.
4. A table of non-claims with the reason each is out of scope.
Do not overstate. Every property must cite the enforcing file:line.
```

---
### Phase 1B — COMPLETE (Correctness fixes required before any evaluation — inserted between 1A and 2A; this block was its authoritative spec). Report: `reports/phase-report-1b-2026-08-05.md`

Scope: src/core/, tests/, and the phase report. Fix the four gaps escalated by phase-report-1A, in this order, each with a failing-then-passing regression test written BEFORE the fix:

1. Promote the response-class contract into production code. Move ReconciliationCapability (and any related connector-contract types) from tests/mock_connector.py into src/core (typed Enum or Protocol). Replace every string-literal comparison in src/core/intent_recovery.py with the typed contract. POSITIVE_ONLY_READBACK must have explicit, tested handling — no fall-through behaviour for any of the three classes. tests/mock_connector.py then imports the contract from src.

2. Fault-isolate the recovery loop. In intent_recovery: wrap per-execution handling so StateCorruptionError or any single-execution exception quarantines/records that execution and continues the scan; use return_exceptions=True (or equivalent structured handling) for gathered tasks; run_forever must survive a scan_once failure with backoff. Regression test: a keyspace with one corrupt execution and N healthy ones — all N healthy executions must still be processed.

3. Make the WAITAOF ack a checked precondition of dispatch authority, not path discipline. Design choice is yours but must be conservative: e.g., the barrier ack mints a dispatch authorization recorded in Redis (or bound into the intent record) and the dispatch gate / preflight Lua verifies it before the connector call can be made. Document the exact mechanism and its residual window in docs/22-formal-model.md (update the P2 section; keep file:line citations current).

4. Define the evaluation composition. Either (a) implement a production-shaped composition (real vault path or a documented evaluation vault with identical semantics) such that validate_startup passes WITHOUT allow_test_dispatch/test_only flags for the harness, or (b) if (a) is not achievable this phase, add an explicit EVALUATION mode whose only difference from production is the connector endpoint, enforce that difference in code, and document it in docs/22. Silent test-only measurement is not acceptable.

Additionally: convert the two "reasoned hypotheses" from phase-report-1A section F (AOF rewind un-fencing a lease; escalated records expiring at TTL) into executable probe tests. If a probe confirms the problem, fix it if the fix is local, otherwise document it as a declared residual window in docs/22 with the probe as evidence.

Environment prerequisite (do this first): install/pin Python 3.13 and project dependencies so the test suite can actually run; verify the full suite passes against real Redis 7.2 via compose.phase2.yml (Docker is available). Paste raw output including the total pass count — this also verifies or corrects the roadmap's unverified "218 passing tests" figure. If the environment cannot be brought up, STOP and report BLOCKED; do not proceed with fixes you cannot test.

Update docs/22-formal-model.md wherever these fixes change an enforcement table, residual window, or gap section. Every fix must appear in the report with its before-failing and after-passing raw test output.


## 2. Phase 2A — COMPLETE. Make the artifact evaluation-grade

> Report: `docs/23-ci-hardening-report.md`. Its open question **G1**
> (deselection vs. compose-everywhere) was resolved in favour of
> compose-everywhere at the start of Phase 2B; both CI jobs now provision Redis
> from `compose.phase2.yml` and the workflow deselects nothing. Its finding
> **F3** ("no CI run has ever been observed") is retired: the first green run is
> [30998269749](https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/30998269749).

Before experiments, harden reproducibility. All local, no GPU.

Tasks:
1. **CI that cannot lie:** GitHub Actions workflow that starts Redis 7.2 (AOF on) in a service container, runs the full suite, and **fails if any test is skipped** (`pytest -q -ra --strict-markers` + a skip-count gate). The old "36 skipped = green" failure mode must be impossible.
2. **Lockfile + pinned environment:** `uv lock` or `pip-tools`; record exact Redis image digest.
3. **Safe test fixture:** replace `FLUSHALL` with namespaced key cleanup (`SCAN aep:* + UNLINK`) or a hard guard that refuses to run unless the Redis instance advertises a test marker key. (Check whether this was already fixed post-audit; if not, fix it.)
4. **Packaging hygiene:** rename top-level package from `src` to `aep_core`; remove committed `__pycache__`/egg-info; add LICENSE (Apache-2.0 or MIT), CITATION.cff, CHANGELOG, release tag `v0.2.0`.
5. **Coverage report** wired into CI (target ≥ 90% on `aep_core` — the package was named `src/core` when this line was written; renamed in Phase 2A).

### Claude Code prompt — Phase 2A
```
Harden this repo to artifact-evaluation grade:
1. Add .github/workflows/ci.yml: matrix over Python 3.13, Redis 7.2 service container with AOF enabled via redis/phase2.conf, run pytest with -ra, then fail the job if the pytest summary contains any skipped tests. Add a separate job that runs the WAITAOF integration suite.
2. Introduce a lockfile (uv preferred) pinning all deps; pin the Redis image by digest in compose.phase2.yml.
3. Audit tests/conftest.py: if FLUSHALL is still used, replace with SCAN-based deletion of aep:* keys only, plus a guard requiring key aep:test-instance-marker to exist before any destructive operation.
4. Rename the package from src to aep_core (update pyproject, imports, tests). Remove any committed bytecode or egg-info; extend .gitignore.
5. Add LICENSE (MIT), CITATION.cff, CHANGELOG.md.
6. Add pytest-cov to CI with a 90% line-coverage gate on aep_core.
Run the full suite against real Redis 7.2 in Docker and paste the raw output into docs/23-ci-hardening-report.md.
```

---

## 3. Phase 2B — COMPLETE. The evaluation harness (this is the heart of the paper)

> **Session 1 is COMPLETE** — report:
> `reports/phase-report-2b-session1-2026-08-05.md`. `experiments/mock_api/`
> ships the standalone service, the SQLite ground-truth ledger (WAL,
> `synchronous=FULL`, one transaction per applied mutation), the YAML fault
> surface with a config echo in every run log, a docker-compose entry, and one
> end-to-end EVALUATION-mode dispatch that retires the "admissible, not
> functional" finding of `reports/phase-report-1b-2026-08-05.md` §F4 at the
> scope of a single dispatch. 1223 → 1387 tests. Sessions 2 and 3 below are
> unchanged. Read §F5 and §G1 of the Session 1 report before writing the
> baselines: the read-back key is a modelling decision that will affect B0's
> numbers.
>
> **Session 2 is COMPLETE** — report:
> `reports/phase-report-2b-session2-2026-08-05.md`. `experiments/harness/`
> ships the six named crash points (mapped onto `aep_core`'s checkpoints by a
> test, not a comment), the environment-selected process crash injector with
> real `SIGKILL`, the multi-process runner and recovery process, Redis restart
> with *verified* AOF replay, a toxiproxy worker↔Redis partition declared in
> `compose.phase2.yml`, and `results/<run_id>/events.jsonl` cross-checked
> against the ground-truth ledger. Session 1's open question G1 is settled by
> `docs/24-readback-keying.md`: read-back keying is a per-run configuration
> with `CALLER_REFERENCE` primary and `ORACLE_FINGERPRINT` as the sensitivity
> variant, both implemented. Every harness path runs in EVALUATION mode with
> no test flags. 1387 → 1565 tests; coverage 90.31% → 91.18%.
>
> The self-validation run found **two defects that the unit suite had missed**
> — `IntentRecoveryService` never satisfied its durability barrier's startup
> contract, and the ground-truth ledger's read path was not thread-safe. Both
> are fixed with regressions. Read §F1, §F2, §F6 and §F7 of the Session 2
> report before Session 3: only one of the six crash points has actually been
> run, and only once.
>
> **Session 3 is COMPLETE for D0–D3; the matrix is PARTIAL** — report:
> `reports/phase-report-2b-session3-2026-08-06.md`. `experiments/baselines/`
> ships all six systems of §3.3 behind one connector, one workload driver and
> one oracle, each with failing-then-passing tests and a machine-readable
> descriptor that tests check against the implementation. **B4 is a real
> event-sourced engine, not the qualitative fallback** — it has a durable,
> `WAITAOF`-acknowledged write-ahead record and still duplicates, which is the
> sharpest statement of the contribution available: the record is necessary and
> is not sufficient. `experiments/run_matrix.py` emits its plan, seeds and cost
> estimate before running (216 cells, 198 applicable, 594 runs, ≈5.9 h) and is
> resumable; `experiments/analyze.py` computes every §3.2 metric from
> `events.jsonl` and the oracle ledger *only*, enforced by a source gate.
> 1565 → 1624 tests.
>
> Three things a reader of the results must know. **(1)** The entry gate
> D0(ii) failed on its first attempt: six runs shared one provider, so each
> reconciled against its predecessors' effects *and* drew faults from a
> generator they had already advanced — which would have made the seed in every
> run log a fiction. Every run now owns its provider, ledger and seed.
> **(2)** The matrix then found two more defects the 1 600-test suite had not:
> a re-executing supervisor abandoned the lease instead of waiting for it, and
> `seed_execution_state` was not idempotent. Both made a baseline look *better*
> than it is. **(3)** B3's ablation cannot yet show the barrier's *benefit*:
> `appendfsync everysec` plus a graceful `docker restart` does not lose a
> buffered write, so a hard Redis kill is needed before any B3-versus-AEP claim
> is made. That is §F3 and the first prerequisite in §H of the Session 3
> report.
>
> **Session 3B is COMPLETE for E1–E6; the matrix is PARTIAL** — report:
> `reports/phase-report-2b-session3b-2026-08-07.md`. Three results change what
> the paper can say.
>
> **(1) The central claim has evidence, and it is graded.** Session 3's
> known-ambiguity rate of 0.0000 was an artifact of running only the endpoint
> that can prove absence. Against the endpoints where the claim lives,
> AEP-full's known-ambiguity rate is **0.0000 / 0.4200 / 0.6667** for
> `AUTHORITATIVE_READBACK` / `POSITIVE_ONLY_READBACK` / `NO_READBACK`, with
> undetected duplicates and lost effects at **0.0000 in all three**. The bound
> on ambiguity is set by what the endpoint can be asked, not by the protocol.
>
> **(2) The hard Redis kill exists, and it refuted half its own premise.** A
> process `SIGKILL` **cannot** lose an unfsynced AOF write — `appendfsync
> everysec` defers the `fsync(2)`, not the `write(2)`, so the bytes are already
> in the kernel's page cache (0/10 lost in a dedicated probe, 60/60 canaries
> surviving in the cells). **The barrier's durability benefit is unobservable
> under any process-level fault and the paper's claim must name the fault class
> it holds against — host power loss, kernel panic, VM destruction.** The
> barrier's *other* benefit is measured and large: with Redis killed between
> the intent CAS and the barrier acknowledgement, AEP-full's `DurabilityAck`
> gate withheld the dispatch in **20 of 30** runs while B3 put the mutation on
> the wire in **28 of 30** (10/30 vs 28/30 applied, Fisher **p = 1.9e-06**).
>
> **(3) RQ3 has numbers, and the overhead is the barrier.** From crash-free
> cells only: the entire write-ahead protocol minus the barrier costs **28 ms**
> on a 2-second call; the two `WAITAOF` round trips cost **≈ 1 967 ms**. That
> is a property of `appendfsync everysec`, not of AEP.
>
> Also: `experiments/baselines/B4_SEMANTICS.md` is the B4 fairness lock, citing
> Temporal's own documentation (default Maximum Attempts = *unlimited*), and
> **B4b** — the documented at-most-once configuration — is implemented and
> shows the trade it predicts: 0.0000 duplicates, 0.0000 declared ambiguity,
> **0.1000 lost effects**. Read §F1, §F2 and §C.9 before Session 4: Table 1 now
> pools three fault regimes and is a coverage summary rather than a result, and
> a resume defect that could silently inflate a resumed run's counts was found
> by the matrix and fixed.

Build a **crash-point fault-injection harness** + **mock legacy API** + **multi-process workload driver**. Everything runs on one machine with Docker.

### 3.1 Components
1. **MockLegacyAPI** (extend tests/mock_connector.py into a standalone HTTP service):
   - Configurable: response delay distribution, timeout probability, 5xx probability, duplicate-response probability, and per-endpoint response class (AUTHORITATIVE_READBACK / POSITIVE_ONLY / NO_READBACK).
   - **Ground-truth ledger:** records every *actually applied* mutation with request fingerprint → this is the oracle for counting real duplicates.
2. **Crash injector:** named crash points inside the workflow (`before_intent_write`, `after_intent_before_barrier`, `after_barrier_before_dispatch`, `mid_dispatch`, `after_response_before_resolution`, `after_resolution_before_barrier`). Workers are separate OS processes killed with SIGKILL at the chosen point (env-var controlled). Also: `docker pause`/`unpause` for lease-expiry stalls, `docker restart redis` for AOF-replay recovery, and `tc netem` or proxy-based partition between worker and Redis.
3. **Workload driver:** N worker processes × M agent executions × K steps; seeds recorded; every run emits a machine-readable JSONL result log.

### 3.2 Metrics (per configuration, ≥ 30 repetitions each)
- **Undetected duplicate rate** = duplicates in ground-truth ledger NOT flagged ambiguous/duplicate by the system (headline metric; AEP target: 0).
- **Known-ambiguity rate** = executions ending PERMANENTLY_AMBIGUOUS (AEP converts silent failures into this).
- **Lost-effect rate**, **state-corruption/quarantine rate**.
- **Recovery success rate** and **recovery latency** (crash → classified), with median/p95/p99.
- **Overhead:** end-to-end step latency and throughput vs. the no-protocol baseline; Redis memory footprint; WAITAOF stall time.
- **Statistics:** report mean + 95% CI (bootstrap), and for rate comparisons use Fisher's exact test; state seeds and repetition counts.

### 3.3 Baselines and ablations (minimum viable set)
| System | Description |
|---|---|
| B0: Naive retry | No lease, no CAS, retry-on-timeout (what most agent frameworks do today) |
| B1: Lease-only | Redis lock, raw SET state, no intent ledger |
| B2: CAS-only | Fenced writes, no write-ahead intent |
| B3: Intent w/o durability barrier | Full protocol minus WAITAOF (ablation isolating the barrier's value) |
| B4: Durable-workflow style | A minimal Temporal-like event-sourced re-execution baseline (or, if too costly, a carefully argued qualitative comparison + micro-benchmark of its logging overhead) |
| AEP-full | The complete protocol |

### Claude Code prompt — Phase 2B (split into 3 sessions)
```
Session 1: Build experiments/mock_api/ as a standalone FastAPI service implementing MockLegacyAPI per PAPER_ROADMAP.md §3.1(1), including the ground-truth applied-mutation ledger persisted to SQLite, configurable via YAML. Add docker-compose entry. Unit-test the ground-truth ledger itself.

Session 2: Build experiments/harness/ implementing the crash injector (§3.1(2)): environment-variable-selected named crash points wired into intent_workflow.py via a zero-overhead-when-disabled hook; a runner that launches N worker subprocesses, kills them with SIGKILL at chosen points, restarts Redis via docker, injects worker↔Redis partitions using a TCP proxy (toxiproxy), and runs the intent_recovery loop. Every run writes results/<run_id>/events.jsonl with full config + seed.

Session 3: Build experiments/baselines/ implementing B0, B1, B2, B3 per PAPER_ROADMAP.md §3.3 as thin variants sharing the same connector interface, and experiments/analyze.py computing all §3.2 metrics with bootstrap 95% CIs and Fisher's exact tests, emitting CSV + matplotlib figures (PDF) for the paper. Then add experiments/run_matrix.py that executes the full {system × crash-point × response-class} matrix, 30 reps each, resumable.
```

**Expected result shape (what the paper's Table 1 should show):** B0 has a high *undetected* duplicate rate; B1/B2 reduce state corruption but still silently duplicate external effects; B3 shows the pre-durability window leaking; AEP-full shows 0 undetected duplicates with all residual cases surfaced as known ambiguity, at X% latency overhead. If AEP-full does *not* achieve this, that is a bug to fix before writing — the harness is also your strongest verification tool.

---

## 4. Phase 3 — Optional strengtheners (do after core results exist)

- **3A. Property-based/model-checking layer:** encode the intent transition table in TLA+ or use Hypothesis stateful testing against the Lua scripts. Even a small TLA+ spec of P1/P2 dramatically strengthens a TSE/TOSEM submission.
- **3B. Second workload:** a realistic multi-step agent scenario (e.g., invoice-processing pipeline hitting 3 mock legacy endpoints with mixed response classes).
- **3C. (Optional, uses Kaggle P100):** drive the workload with a real small LLM planning steps, to show the protocol under genuine agent nondeterminism. Nice-to-have, not required — reviewers care about the fault-injection matrix far more.

---

## 5. Phase 4 — The manuscript

Structure (TSE/TOSEM style, ~14–18 pages double column):
1. **Introduction** — the agent + non-idempotent legacy API problem; why "exactly-once" claims are false; the fail-closed alternative; contributions C1–C4.
2. **Motivating study** — 3 concrete failure traces from B0 (naive retry) reproduced by your harness.
3. **System & failure model** — from docs/22-formal-model.md.
4. **The AEP protocol** — state machine figure, the three Lua invariants, WAITAOF barrier, recovery classification; explicit residual windows.
5. **Implementation** — ~5.8k LOC Python 3.13 + Redis 7.2, 674 tests (verified; see `reports/phase-report-1b-2026-08-05.md` §C.6).
6. **Evaluation** — RQ1: Does AEP eliminate undetected duplicates under crashes? RQ2: What does each mechanism contribute (ablations)? RQ3: What is the overhead? RQ4: How fast/robust is recovery?
7. **Related work** — Leases (Gray & Cheriton '89), Chubby, Redis locking pattern, optimistic CC, WAL, Sagas ('87), Beldi (OSDI'20), ExoFlow (OSDI'23), Temporal/durable execution, AIOS, ACRFence (2026). One paragraph each on why AEP differs (the differentiator: *declared-ambiguity semantics for non-cooperative legacy endpoints*, not exactly-once for cooperative ones).
8. **Threats to validity** — single-node, mock API realism, Python overhead, single-Redis trust domain.
9. **Artifact availability** — repo tag + Zenodo DOI, CI badge, one-command reproduction (`make reproduce`).

### Claude Code prompt — Phase 4
```
Create paper/ with a LaTeX project using the IEEEtran (TSE) template. Draft sections 1–5 and 7–9 per PAPER_ROADMAP.md §5, drawing every technical statement from docs/22-formal-model.md and aep_core/core with file:line grounding, and leaving \todo markers where experiment numbers from experiments/results will be inserted. Generate the protocol state-machine figure with TikZ from the transition table in aep_core/core/intents.py. Write related work with real citations in refs.bib (verify each BibTeX entry exists; do not fabricate).
```

---

## 6. Order of operations & realistic effort

| Step | Output | Effort with Claude Code |
|---|---|---|
| 1A Formal model | docs/22 | 2–3 days |
| 2A CI/artifact hardening | green non-lying CI | 3–5 days |
| 2B Harness + baselines + matrix | results CSVs + figures | 2–4 weeks (matrix runtime included) |
| 4 Manuscript | full draft | 1–2 weeks |
| 3A TLA+/property layer | spec + report | 1 week (optional but high value) |
| Polish + arXiv + submit | preprint | 1 week |

**Rule for every Claude Code session:** end each session by demanding raw command output pasted into a dated report file — never accept "tests pass" as prose. The repo's own audit history shows why: earlier internal reports claimed properties the code did not have.

---

## 7. Venue decision cheat-sheet

- **IEEE TSE / ACM TOSEM:** best fit — reliability engineering for AI agents, strong artifact culture, no page-count panic. Expect 6–12 month review cycles; no deadline pressure suits you.
- **IEEE TPDS:** fits if the fault-injection + distributed-coordination results are the centerpiece.
- **Fast-feedback path first:** submit a 4-page version to an ICSE/FSE workshop or the SANER/ISSRE track to collect reviews cheaply, then extend ≥30% for the journal (standard practice; disclose the prior version).
- Post the preprint to **arXiv (cs.SE + cs.DC)** as soon as the evaluation is done — it timestamps your contribution against fast-moving agent-reliability work like ACRFence.

8. GIT HYGIENE (mandatory): At the START of every session, verify the working tree is clean (git status); if it is not, stop and report what is uncommitted before doing anything else. At the END of every session, commit all work with a descriptive message, push, and confirm CI is green BEFORE writing the final report. A session whose work is not committed and pushed is not complete. Never leave staged work across sessions.