# Changelog

All notable changes to this project are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Every test count in this file is a figure that was actually observed, with the
raw output recorded in the phase report named alongside it. Unverified numbers
do not belong in a changelog for an artifact-evaluation package.

## [Unreleased]

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
