# Changelog

All notable changes to this project are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Every test count in this file is a figure that was actually observed, with the
raw output recorded in the phase report named alongside it. Unverified numbers
do not belong in a changelog for an artifact-evaluation package.

## [1.0.0-rc1] — 2026-08-10

The research artifact, prepared for submission. Nothing has been published,
uploaded or submitted anywhere; this tag marks the state a reviewer would be
pointed at.

Full reports: `reports/phase-report-5a-2026-08-10.md` and
`reports/phase-report-5b-2026-08-10.md`. 1729 → 1734 tests, coverage 91.18%.

### Added

- **`ARTIFACT.md`** — the claims-to-evidence map. Every quantitative claim in
  the manuscript resolves to a macro in `paper/generated/numbers.tex`, whose
  provenance comment names the file, the filter and the arithmetic behind it;
  the 89 macros draw on eight files and nothing else. Includes requirements,
  runtimes, the frozen-archive layout and how to verify it.
- **`Makefile`** — `reproduce-figures` regenerates every table and macro from
  the frozen CSVs and byte-compares them against what is committed;
  `reproduce-smoke` provisions Redis, collects one tier-1 cell for each of the
  seven systems under real `SIGKILL`, analyses it and prints a row per system.
  Both write only under `.scratch/`; neither can touch the frozen results.
- **The numbers gate now runs in CI.** The analysis products
  `scripts/check_paper_numbers.py` reads are tracked by name — 13 files, at
  their frozen content, verified against `SHA256SUMS` — and a `paper-numbers`
  job builds the manuscript and runs the gate on every push. Phase 5A had
  recorded this as the one checklist item it could not discharge.

### Fixed

- **34 hand-typed measurements in the manuscript** became generated macros or
  pointers to the generated table that carries them. Phase 5A found one of
  them, `0.9500`, was wrong by a factor of 1.8; it had survived a green gate
  and a hostile-reviewer pass because the gate checks generated tables against
  the CSVs and says nothing about a numeral typed into prose. Of the 34, four
  were also wrong or unverifiable: a third barrier costed at "roughly a 50%
  latency increase" is 24.6% of the step (50% is the increase in the barrier
  bill alone); a `400`–`1 000` ms kill latency had no source and is 419–992 ms
  in the probe that measured it; `p < 10^{-100}` was true but ungenerated
  (2.1×10⁻¹⁸³); and "two executions in six hundred" was a measurement spelled
  out in words, which no digit-based check can see.
- **A generated caption its own table falsified.** `table-outcomes.tex` read
  "AEP-full is the only system with a nonzero declared-ambiguity column, and
  the only one whose other two columns are zero everywhere" while the B3 row
  above it showed 0.0000/0.3667/0.7167 and zeros elsewhere. Both halves were
  false, and of the paper's own central finding.
- **`paper_tables.py` emits B4 and B4b macros for all three capability
  classes.** The loop listed two, which is what left the prose with no macro to
  quote and `0.9500` in its place.

## [Unreleased]

### Phase 2B Session 3 — baselines, the matrix, and the analysis

Full report: `reports/phase-report-2b-session3-2026-08-06.md`. 1565 → 1624
tests.

#### Added

- **`experiments/baselines/`** — the six systems of `PAPER_ROADMAP.md` §3.3 as
  thin variants sharing one connector, one workload driver and one ground-truth
  oracle: **B0** naive retry, **B1** lease-only, **B2** CAS-only (fenced state,
  no write-ahead intent), **B3** the full protocol with `WAITAOF` ablated and
  nothing else ablated, **B4** a minimal event-sourced durable-workflow engine,
  and AEP-full. Each has failing-then-passing tests proving what its label
  claims, and a `SystemDescriptor` table whose every row is checked against the
  implementation by running it.
  - B4 is a **real implementation** rather than the qualitative comparison the
    roadmap permits as a fallback. It has a durable, `WAITAOF`-acknowledged
    write-ahead record and still duplicates, because its semantics for a
    scheduled-but-uncompleted activity are at-least-once. The write-ahead
    record is necessary and is not sufficient; the policy applied to it is what
    matters.
- **`experiments/run_matrix.py`** — the `{system × crash-point ×
  response-class × read-back-keying}` matrix as code. 216 cells, 198
  applicable, 594 runs. Emits its full plan, seeds and estimated wall time
  before running anything; resumable; refuses to execute on a platform without
  a real `SIGKILL`; halts if AEP-full ever records an undetected duplicate.
- **`experiments/analyze.py`** and **`experiments/statistics.py`** — every §3.2
  metric with run-clustered percentile bootstrap intervals and exact two-tailed
  Fisher tests, emitting a CSV per metric, Table 1 and PDF figures. The
  analysis opens exactly two files per run — `events.jsonl` and the run's
  read-only `ground_truth.sqlite3` — and a source gate fails the suite if an
  import of `redis` or `aep_core` ever appears in it.
- **`experiments/bench_mock_api.py`** — the provider's sustained throughput,
  compared against the busiest planned configuration's rate computed from
  `run_matrix.py`'s own constants. **468.8 req/s against a 2.5 req/s planned
  peak: 187×.** This retires Session 1 §F8 and Session 2 §F9/§G3, which had
  carried the question unmeasured through two sessions.
- **`experiments/smoke_matrix.py`** — all six crash points, one run each, as a
  precondition of any matrix launch. It cost six short runs and caught two
  defects the unit suite had missed.
- **Inapplicable cells are recorded, never filled.**
  `after_intent_before_barrier` does not exist in B0, B1 or B2; those 18 cells
  carry `applicable: false` and a machine-readable reason rather than being
  aliased onto a neighbouring crash point.

#### Fixed

- **Runs shared one provider, one ground-truth ledger and one seeded fault
  generator.** Reconciliation failed at two of six crash points because each
  run was being asked to account for its predecessors' effects. The second
  consequence was worse and silent: `MockLegacyAPI` seeds one
  `random.Random(seed)` per *process*, so a shared provider made run *N*'s
  fault stream a function of how many requests runs *1..N−1* had made — the
  seed in a run's own log did not determine that run's faults. Every run now
  gets its own provider, ledger and freshly seeded generator
  (`experiments/mock_api/supervisor.py`, `experiments/harness/orchestrate.py`).
- **A re-executing supervisor abandoned the lease instead of waiting for it.**
  A worker killed mid-dispatch leaves its lease held until the TTL expires, so
  the respawned execution's `acquire_lock` returned `None` and the baseline
  raised — crediting the lease with *preventing* a duplicate it only delays.
  The lease-taking systems now wait, bounded by the lock TTL plus a margin, and
  record what they waited.
- **`seed_execution_state` was not idempotent**, so B2 — the only system that
  both uses the fenced write path and re-executes — failed every re-execution
  with `StaleWriteError` before transmitting anything.

#### Changed

- `experiments/harness/reconcile.py` works in a system-agnostic outcome
  vocabulary and gates each rule on what the system under test promised: an
  effect with no durable record is a P2 violation for AEP-full and B3, and a
  measured lost effect for B0, B1 and B2.
- `MockLegacyApiConnector.transmit()` split out of `mutate()` so the baselines
  share the connector without inheriting the request-binding machinery that is
  the thing under ablation.
- CI installs the new `analysis` extra; `MINIMUM_TESTS` 1500 → 1590.

### Phase 2B Session 2 — the crash injector and the multi-process runner

Full report: `reports/phase-report-2b-session2-2026-08-05.md`. 1387 → 1565
tests; `aep_core` coverage 90.31% → 91.18%.

### Added

- **`experiments/harness/`** — named crash points wired into
  `aep_core` through a hook that is absent when disabled, a runner that
  launches worker processes and kills them with a real `SIGKILL`, a recovery
  process, Redis restart with *verified* AOF replay, a toxiproxy worker↔Redis
  partition, and `results/<run_id>/events.jsonl` (`PAPER_ROADMAP.md`
  §3.1(2–3)).
- **Read-back keying** as an explicit per-run measurement decision with two
  values, `CALLER_REFERENCE` (primary) and `ORACLE_FINGERPRINT` (sensitivity),
  both implemented and both contributing to the mock API's configuration
  digest. Rationale: `docs/24-readback-keying.md`. This closes open question
  G1 of `reports/phase-report-2b-session1-2026-08-05.md`.
- **`toxiproxy`** in `compose.phase2.yml`, pinned by digest, with the proxy
  declared in `redis/toxiproxy.json` so a run cannot proceed against a proxy
  that was never created.
- **The `scan_failure_alert` stream is consumed and measured** — poisoned
  executions are injected at recorded instants and the detection latency is
  reported. This retires `reports/phase-report-1b-2026-08-05.md` §F7, which
  recorded that nothing in the repository consumed it.

### Fixed

- **`IntentRecoveryService` never satisfied its durability barrier's startup
  contract.** With the production `RealWaitAofDurabilityBarrier` every
  recovery resolution wrote its transition CAS and then failed to confirm it,
  leaving the state advanced but unacknowledged and reporting the resolution
  as an isolated failure. Invisible to the unit suite because every recovery
  test used the fake barrier. Regression:
  `tests/test_recovery_durability_barrier.py`.
- **The ground-truth ledger's read path was not thread-safe.** One SQLite
  connection was shared across the service's worker threads with only writes
  guarded, so a read-back issued during an open write transaction could report
  a committed row absent, report one application as a `CONFLICT`, or raise.
  Each corrupts a number the paper reports. Reads now use one connection per
  thread and the consistency report takes a snapshot. Regression:
  `experiments/mock_api/tests/test_ledger_concurrency.py`.

### Changed

- `aep_core/core/intent_workflow.py` gained one checkpoint,
  `AFTER_PREFLIGHT_BEFORE_REQUEST_TRANSMISSION`, immediately before the
  connector call — the last instruction at which a process is provably
  pre-dispatch, and the point a deferred `mid_dispatch` kill is armed from.

---

Phase 2B Session 1: MockLegacyAPI and the ground-truth ledger. Full report:
`reports/phase-report-2b-session1-2026-08-05.md`.

### Added

- **`experiments/mock_api/`** — a standalone FastAPI service simulating a
  non-idempotent legacy endpoint, with a durable ground-truth ledger the
  caller cannot read (`PAPER_ROADMAP.md` §3.1(1)).
- **The oracle's identity function**, stated precisely enough to be quoted in
  the paper: Definition 1 (mutation fingerprint), Definition 2 (payload
  digest) in `experiments/mock_api/fingerprint.py`, Definition 3 (duplicate
  classes) in `experiments/mock_api/ledger.py`. Computed by the service from
  the request as received on the wire, with its own canonicaliser: an oracle
  that reused the canonicaliser of the protocol it measures would inherit any
  collision that canonicaliser has.
- Ground-truth ledger in SQLite with `journal_mode=WAL` and
  `synchronous=FULL`. Each applied mutation writes the simulated state change
  and its ledger row in one `BEGIN IMMEDIATE … COMMIT`, so no interleaving
  exists in which the external world changed and the oracle does not know.
- Configurable fault surface via YAML — delay distribution, timeout
  probability, 5xx probability, duplicate-response probability, and
  per-endpoint response class — with the whole loaded configuration and a
  digest over it echoed into `GET /v1/config` and into the first record of
  every run log.
- `experiments/mock_api/Dockerfile` and `compose.mock-api.yml`, built and
  exercised end-to-end (build → mutation → read-back → oracle → teardown).

### Changed

- **Both CI jobs now provision Redis from `compose.phase2.yml`**, and the
  workflow deselects nothing. The `test` job previously took Redis from a
  GitHub `services:` container, which starts before checkout and so can
  neither mount `redis/phase2.conf` nor survive `docker restart` with AOF
  intact — forcing the crash-recovery test to be deselected by name. That
  deselection was the only construct in the workflow able to turn a gate
  green without the work being done (`docs/23-ci-hardening-report.md` G1).
  Five new gates in `tests/test_artifact_reproducibility.py` fail the suite
  if it returns.
- `pytest` `testpaths` now covers `experiments/` as well as `tests/`, so the
  zero-skip and zero-xpass gates apply to the harness suite too.
- `MINIMUM_TESTS` raised 1100 → 1350.

### Verified

- 1387 tests passing, 0 skipped, 0 xpassed, against Redis 7.2.5 with AOF on
  CPython 3.13.0. Suite grew 1223 → 1387.
- Coverage 90.31% on `aep_core` — unchanged, because no `aep_core` logic was
  changed in this session.
- EVALUATION mode dispatches a real mutation over a real socket to a real
  MockLegacyAPI process, with no `allow_test_dispatch` and no
  `allow_test_barrier`, and the ground-truth ledger records it. This retires
  the "admissible, not functional" finding (`phase-report-1b` §F4) at the
  scope of one dispatch; the crash-boundary matrix remains Session 2/3 work.

## [0.2.0] — 2026-08-05

Phase 2A: the artifact becomes evaluation-grade. Full report:
`docs/23-ci-hardening-report.md`.

### Added

- **CI that cannot lie** (`.github/workflows/ci.yml`). Runs the suite against
  real Redis 7.2.5 with AOF, never fakes it, and enforces four gates:
  zero skipped tests, zero xpassed tests, ≥ 90% line coverage on `aep_core`,
  and range-valid `file:line` citations in `docs/22-formal-model.md`.
  Each gate is itself tested, so a vacuous gate cannot produce a green build.
- `scripts/validate_citations.py` — range-validates every citation in
  `docs/22-formal-model.md`. Resolves 374 citations, including the 134
  bare `:NNN` continuation forms that the earlier ad-hoc validator never
  checked.
- `scripts/check_pytest_gates.py` — enforces the zero-skip / zero-xpass /
  suite-actually-ran gates from JUnit XML plus the `-ra` summary.
- `scripts/verify_redis_semantics.py` — derives the required Redis settings
  from `redis/phase2.conf` and asserts the live server reports them, so the
  CI environment cannot drift from the compose environment.
- `uv.lock` pinning the exact dependency set the verified runs used, plus
  `.python-version` recording CPython 3.13.0.
- `LICENSE` (MIT), `CITATION.cff`, and this changelog.
- Test-instance marker guard: destructive test cleanup now requires the
  Redis instance to advertise `aep:test-instance-marker`.
- Coverage on `aep_core` raised 88% → 90.31%, entirely by adding tests for
  fail-closed rejection branches. No package logic was changed to reach it.

### Changed

- **Package renamed `src` → `aep_core`.** Mechanical: file moves plus import
  rewrites, verified import-only by diffing each old blob against its new
  counterpart. The suite reported 695 passed immediately before and 695
  passed immediately after, both against real Redis 7.2.5.
- `docs/22-formal-model.md` citation paths re-pointed to `aep_core/core/...`
  (161 references). Line numbers are unchanged because no statement inside
  any function moved.
- Test cleanup uses `UNLINK` instead of `DEL`, so a large test keyspace
  cannot stall the server.
- `AEP_TEST_ALLOW_FLUSHALL` renamed to `AEP_TEST_ALLOW_NONSTANDARD_DB`; the
  legacy name is still accepted. Nothing has called `FLUSHALL` since the
  post-audit cleanup rewrite, so the old name described a command that no
  longer existed in the codebase.
- `requires-python` upper-bounded to `>=3.13,<3.14`: the artifact is
  evidenced on CPython 3.13 only.
- `xfail_strict = true`, so an xfail that starts passing is a hard failure
  rather than a summary note.
- `PAPER_ROADMAP.md` corrected: the "218 passing tests" figure was never
  verified and was wrong.

### Fixed

- The `AEP_TEST_ALLOW_FLUSHALL=1` override let destructive test cleanup run
  against any real Redis database. Cleanup was namespace-scoped to `aep:*`,
  but `aep:*` is precisely the namespace AEP uses in production, so the
  override's blast radius was exactly the production keyspace the scoping
  was meant to protect. The marker guard closes this: widening which
  database is acceptable no longer licenses writing to an unmarked instance.

### Verified

- 1223 tests passing, 0 skipped, against Redis 7.2.5 (AOF on, `appendfsync
  everysec`) on CPython 3.13.0. The suite grew 674 → 1223 in this phase;
  every addition is a test, none is a change to protocol logic.
- Coverage 90.31% on `aep_core`.
- 374 citations in `docs/22-formal-model.md`, 0 out of range.

## [0.1.0] — 2026-08-05 (pre-release baseline)

The state imported at the start of the paper work, plus Phases 1A and 1B.
Reports: `reports/phase-report-1A-2026-08-05.md`,
`reports/phase-report-1b-2026-08-05.md`.

### Added

- Phase 1: expected-version CAS with lock-token fencing, lease-loss
  cancellation, UUIDv4 validation, schema-version write gate.
- Phase 2: write-ahead intent ledger with an exhaustive transition table,
  WAITAOF durability barrier (Redis 7.2, AOF), crash-recovery resolver,
  request vault and request binding.
- Phase 1A: `docs/22-formal-model.md` — system model, failure model,
  properties P1–P3 with per-property enforcement maps and declared residual
  windows, and a non-claims table.
- Phase 1B: typed connector response-class contract in production code,
  fault-isolated recovery loop, WAITAOF-ack-gated dispatch authorization,
  and an explicit `EVALUATION` dispatch mode.

### Verified

- 611 tests passing before Phase 1B, 674 after, 0 skipped, against real
  Redis 7.2.5 with AOF.

[0.2.0]: https://github.com/hafizmirhamza276-lab/Research-paper-AEP/releases/tag/v0.2.0
[0.1.0]: https://github.com/hafizmirhamza276-lab/Research-paper-AEP/releases/tag/v0.1.0
