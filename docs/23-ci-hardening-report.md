# Phase report — 2A (CI / artifact hardening)

**Date:** 2026-08-05
**Roadmap section:** `PAPER_ROADMAP.md` §2 ("Phase 2A — Make the artifact
evaluation-grade"), as amended by the five session amendments A1–A5, which
override the roadmap text where they conflict.
**Repository state at report time:** commit `9ded06e`, clean tree, on `main`.

---

## A. Phase attempted and roadmap section reference

Phase 2A: harden the repository to artifact-evaluation grade before any
experimental work begins. Five roadmap tasks (`PAPER_ROADMAP.md:79-85`) plus
five amendments:

| Amendment | Requirement |
|---|---|
| A1 | Correct the stale "218 passing tests" figure in the roadmap; record that Phase 1B was inserted between 1A and 2A, with its report path |
| A2 | CI against real Redis 7.2 (AOF on, `phase2.conf` semantics) in a service container, with four gates: zero skips, zero xpass surprises, the coverage gate, and citation range-validation for `docs/22-formal-model.md` |
| A3 | Audit the `FLUSHALL` state and **report findings before changing anything** |
| A4 | Do not touch `src/core` logic except where the package rename mechanically requires import changes; if the rename risks destabilising the suite, do it in a single commit with the full suite raw output immediately before and immediately after |
| A5 | Lockfile pinning the exact dependency set the 674-pass run used; record Python 3.13.0 and the Redis image digest |

No experimental harness, baseline, mock-API, or manuscript work was performed.
Those are Phases 2B and 4.

**Headline outcome:** all four gates are implemented, wired into CI, and
demonstrated to fail when they should. The suite grew 674 → **1223 passing,
0 skipped**; coverage on `aep_core` rose 88% → **90.35%**. Not one line of
protocol logic was changed: the entire package diff for this phase is 26
inserted and 26 deleted lines, all of them import statements.

---

## B. Files created/modified

### Created

| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | Three jobs (`citations`, `test`, `waitaof-durability`) enforcing the four gates against real Redis 7.2.5 |
| `scripts/validate_citations.py` | Gate (iv). Range-validates `file:line` citations in `docs/22-formal-model.md` |
| `scripts/check_pytest_gates.py` | Gates (i) and (ii). Zero-skip, zero-xpass, suite-actually-ran, from JUnit XML + the `-ra` summary |
| `scripts/verify_redis_semantics.py` | Derives required Redis settings from `redis/phase2.conf` and asserts the live server reports them |
| `scripts/__init__.py` | Makes the gate scripts importable by their tests |
| `tests/test_conftest_safety.py` | 21 tests pinning the destructive-cleanup guards |
| `tests/test_citation_validator.py` | 30 tests for gate (iv), both directions |
| `tests/test_ci_gates.py` | 27 tests for gates (i)/(ii), both directions |
| `tests/test_failclosed_branches.py` | 116 tests for fail-closed rejection branches |
| `tests/test_safe_value_allowlist.py` | 111 tests for the request-binding allowlist and canonicalization |
| `tests/test_vault_metadata_validation.py` | 217 tests for the vault AAD validators |
| `tests/test_artifact_reproducibility.py` | 27 tests cross-checking the artifact's environment declarations |
| `uv.lock` | Exact dependency pins (A5) |
| `.python-version` | `3.13.0` |
| `LICENSE` | MIT |
| `CITATION.cff` | Citation metadata, v0.2.0 |
| `CHANGELOG.md` | 0.1.0 and 0.2.0 |

### Modified

| File | Change |
|---|---|
| `PAPER_ROADMAP.md` | A1: 218 → 674 at `:14` and `:156`; Phase 1B recorded as complete with its report path; "CURRENT PHASE" moved from 1B to 2A; two forward-looking `src/core` references re-pointed |
| `tests/conftest.py` | A3: test-instance-marker guard, `UNLINK` instead of `DEL`, env var renamed |
| `pyproject.toml` | version 0.2.0, `aep_core*` discovery, `requires-python` upper bound, `cov` extra, `xfail_strict`, coverage config, MIT licence metadata |
| `docs/22-formal-model.md` | 161 citation paths re-pointed to `aep_core/core/...`; new §0.05 recording the rename; §0 notes the CI citation gate |
| `README.md` | Rewritten — it still described "Phase 1" and the `src/` layout |
| `.gitignore` | Ignore `.ai/` agent session logs |
| `src/` → `aep_core/` | 14 files moved; 131 import sites and 8 string-literal references rewritten |

### Package rename diff, with rename detection

```
$ git diff --stat -M50% f4bb7a0..HEAD -- aep_core src
 {src => aep_core}/__init__.py                |  0
 {src => aep_core}/core/__init__.py           |  0
 {src => aep_core}/core/connector_contract.py |  2 +-
 {src => aep_core}/core/durability.py         |  0
 {src => aep_core}/core/exceptions.py         |  0
 {src => aep_core}/core/intent_recovery.py    | 12 ++++++------
 {src => aep_core}/core/intent_workflow.py    | 12 ++++++------
 {src => aep_core}/core/intents.py            | 10 +++++-----
 {src => aep_core}/core/locks.py              |  4 ++--
 {src => aep_core}/core/request_binding.py    |  2 +-
 {src => aep_core}/core/request_vault.py      |  2 +-
 {src => aep_core}/core/state_codec.py        |  2 +-
 {src => aep_core}/core/storage.py            |  6 +++---
 {src => aep_core}/core/validation.py         |  0
 14 files changed, 26 insertions(+), 26 deletions(-)
```

26 lines changed in the whole package, every one an import.

---

## C. Raw command outputs

All commands run from `D:/personal/AEP/Research-paper-AEP` in Git Bash on
Windows 11. Test commands use
`AEP_PHASE2_REDIS_INTEGRATION=1 REDIS_URL=redis://127.0.0.1:6381/15`.

### C.0 Environment

```
$ ./.venv/Scripts/python.exe -VV
Python 3.13.0 (tags/v3.13.0:60403a5, Oct  7 2024, 09:38:07) [MSC v.1941 64 bit (AMD64)]

$ uv --version
uv 0.11.8 (0e961dd9a 2026-04-27 x86_64-pc-windows-msvc)

$ docker info --format 'ServerVersion={{.ServerVersion}} OS={{.OSType}}'
ServerVersion=29.4.3 OS=linux

$ docker compose -f compose.phase2.yml ps --format '{{.Name}} {{.Image}} {{.Status}}'
aep-phase2-redis72 redis:7.2.5-alpine@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44 Up About a minute (healthy)

$ docker exec aep-phase2-redis72 redis-cli INFO server | grep -E "^redis_version"
redis_version:7.2.5

$ docker exec aep-phase2-redis72 redis-cli CONFIG GET appendonly appendfsync
appendfsync
everysec
appendonly
yes

$ docker exec aep-phase2-redis72 redis-cli INFO persistence | grep -E "^aof_enabled"
aof_enabled:1
```

### C.1 A3 — FLUSHALL audit, findings BEFORE any change

Per amendment A3, the audit ran first and its findings are recorded here
before the change that followed.

```
$ grep -rn -i "flushall\|flushdb" --include="*.py" . | grep -v .venv | grep -v __pycache__
./tests/conftest.py:18:    explicitly opts in with AEP_TEST_ALLOW_FLUSHALL=1. Cleanup never calls
./tests/conftest.py:19:    FLUSHALL; it incrementally deletes only keys in the ``aep:*`` namespace.
./tests/conftest.py:118:    explicitly_allowed = os.environ.get("AEP_TEST_ALLOW_FLUSHALL") == "1"

$ grep -rn -i "test-instance-marker" . | grep -v .venv
./PAPER_ROADMAP.md:88:3. Audit tests/conftest.py: if FLUSHALL is still used, replace with SCAN-based ...
```

| Roadmap ask (`PAPER_ROADMAP.md:81`, `:90`) | Verified state before changing anything |
|---|---|
| Replace `FLUSHALL` with namespaced cleanup | **Already done.** No executable `FLUSHALL` call exists anywhere. `_delete_aep_test_keys` used `scan_iter(match="aep:*", count=500)` plus batched `delete`. The only surviving occurrences were a docstring and an env-var name. |
| Guard requiring `aep:test-instance-marker` | **Not implemented.** Zero occurrences repo-wide outside the roadmap text itself. |
| Existing guard | Database-based, not marker-based: refused a real Redis unless the selected DB was 15. |

**The hole the audit found.** `AEP_TEST_ALLOW_FLUSHALL=1` let destructive
cleanup run against *any* real Redis database. Cleanup remained scoped to
`aep:*` — but `aep:*` is precisely the namespace AEP uses in production, so
the override's blast radius was exactly the production keyspace the scoping
was meant to protect. Namespace scoping is not self-sufficient here. The env
var name was also misleading, naming a command that no longer existed in the
codebase.

**Change made after reporting:** cleanup now requires the instance to
advertise `aep:test-instance-marker`, auto-provisioned only on an allowed and
completely empty database. The override widens *which database* is
acceptable; it no longer licenses writing to an unmarked instance. Cleanup
switched to `UNLINK` and preserves the marker. Env var renamed to
`AEP_TEST_ALLOW_NONSTANDARD_DB`, legacy name still honoured.

**Negative control — the guard refusing a populated, unmarked database:**

```
$ docker exec aep-phase2-redis72 redis-cli -n 14 SET aep:execution:pretend-production "MUST SURVIVE"
OK
$ AEP_TEST_ALLOW_NONSTANDARD_DB=1 REDIS_URL=redis://127.0.0.1:6381/14 pytest -q tests/test_locks.py -x
E       RuntimeError: Refusing Redis test cleanup: DB 14 at 'redis://127.0.0.1:6381/14' does not
        advertise the test marker key 'aep:test-instance-marker'. The marker is auto-created only
        on an allowed, completely empty database; this one is non-empty or outside the allowed set,
        so it cannot be assumed disposable. If this instance really is a throwaway test instance,
        mark it explicitly:
            redis-cli -n 14 SET aep:test-instance-marker 1
tests\conftest.py:163: RuntimeError
1 error in 0.35s
PYTEST_EXIT=1

$ docker exec aep-phase2-redis72 redis-cli -n 14 GET aep:execution:pretend-production
MUST SURVIVE
```

The override was set, and the pretend-production key still survived.

### C.2 A4 — the rename, with the full suite immediately before and after

Amendment A4 required this. 131 import sites across 43 files is a real
destabilisation risk, so the rename is a single commit (`23e4ae5`) with these
two runs bracketing it.

**Immediately before (`f19687a`):**

```
$ AEP_PHASE2_REDIS_INTEGRATION=1 REDIS_URL=... pytest -q -ra --strict-markers
........................................................................ [ 10%]
........................................................................ [ 20%]
........................................................................ [ 31%]
........................................................................ [ 41%]
........................................................................ [ 51%]
........................................................................ [ 62%]
........................................................................ [ 72%]
........................................................................ [ 82%]
........................................................................ [ 93%]
...............................................                          [100%]
695 passed in 34.81s
PYTEST_EXIT=0
```

**Immediately after:**

```
$ AEP_PHASE2_REDIS_INTEGRATION=1 REDIS_URL=... pytest -q -ra --strict-markers
........................................................................ [ 10%]
........................................................................ [ 20%]
........................................................................ [ 31%]
........................................................................ [ 41%]
........................................................................ [ 51%]
........................................................................ [ 62%]
........................................................................ [ 72%]
........................................................................ [ 82%]
........................................................................ [ 93%]
...............................................                          [100%]
695 passed in 36.54s
PYTEST_EXIT=0
```

**Mechanical-only proof.** Each old blob diffed against its new counterpart,
excluding import lines:

```
$ for new in $(find aep_core -name "*.py" | sort); do
    old="src/${new#aep_core/}"
    git show "HEAD:$old" | diff - "$new" | grep "^[<>]" \
      | grep -vE "^[<>] (from|import) (src|aep_core)\.core" || echo "    [import-only]"
  done
--- src/core/__init__.py -> aep_core/core/__init__.py
    [import-only]
--- src/core/connector_contract.py -> aep_core/core/connector_contract.py
    [import-only]
--- src/core/durability.py -> aep_core/core/durability.py
    [import-only]
--- src/core/exceptions.py -> aep_core/core/exceptions.py
    [import-only]
--- src/core/intent_recovery.py -> aep_core/core/intent_recovery.py
    [import-only]
--- src/core/intent_workflow.py -> aep_core/core/intent_workflow.py
    [import-only]
--- src/core/intents.py -> aep_core/core/intents.py
    [import-only]
--- src/core/locks.py -> aep_core/core/locks.py
    [import-only]
--- src/core/request_binding.py -> aep_core/core/request_binding.py
    [import-only]
--- src/core/request_vault.py -> aep_core/core/request_vault.py
<         from src.core.request_binding import canonical_json_bytes
>         from aep_core.core.request_binding import canonical_json_bytes
--- src/core/state_codec.py -> aep_core/core/state_codec.py
    [import-only]
--- src/core/storage.py -> aep_core/core/storage.py
    [import-only]
--- src/core/validation.py -> aep_core/core/validation.py
    [import-only]
```

The single `request_vault.py` hit is a function-local import; the filter
missed it only because of its leading indentation. No non-import line changed
anywhere in the package.

### C.3 A5 — lockfile pins the exact 674-pass dependency set

Comparison against the 19 packages recorded in
`reports/phase-report-1b-2026-08-05.md` §C.6:

```
locked packages: 21   674-run packages: 19

  OK   annotated-types        run=0.8.0      lock=0.8.0
  OK   cffi                   run=2.1.1      lock=2.1.1
  OK   colorama               run=0.4.6      lock=0.4.6
  OK   cryptography           run=50.0.0     lock=50.0.0
  OK   fakeredis              run=2.37.0     lock=2.37.0
  OK   iniconfig              run=2.3.0      lock=2.3.0
  OK   lupa                   run=2.8        lock=2.8
  OK   packaging              run=26.3       lock=26.3
  OK   pluggy                 run=1.6.0      lock=1.6.0
  OK   pycparser              run=3.0        lock=3.0
  OK   pydantic               run=2.13.4     lock=2.13.4
  OK   pydantic-core          run=2.46.4     lock=2.46.4
  OK   pygments               run=2.20.0     lock=2.20.0
  OK   pytest                 run=9.1.1      lock=9.1.1
  OK   pytest-asyncio         run=1.4.0      lock=1.4.0
  OK   redis                  run=8.1.0      lock=8.1.0
  OK   sortedcontainers       run=2.4.0      lock=2.4.0
  OK   typing-extensions      run=4.16.0     lock=4.16.0
  OK   typing-inspection      run=0.4.2      lock=0.4.2

added by the coverage extra (not in the 674 run):
        coverage               lock=7.15.3
        pytest-cov             lock=7.1.0

MISMATCHES: none
```

19 of 19 exact, zero mismatches. The two additions are the coverage gate's
own dependencies, which the 674-pass run predates.

**Clean sync from the lock reproduces the environment and the suite:**

```
$ uv sync --frozen --extra dev --extra cov
 + aep-core==0.2.0 (from file:///D:/personal/AEP/Research-paper-AEP)
SYNC_EXIT=0

$ ./.venv/Scripts/python.exe --version
Python 3.13.0

$ AEP_PHASE2_REDIS_INTEGRATION=1 REDIS_URL=... pytest -q -ra --strict-markers \
      --cov=aep_core --cov-fail-under=90
Required test coverage of 90% reached. Total coverage: 90.31%
1169 passed in 47.99s
PYTEST_EXIT=0
```

Python 3.13.0 is recorded in `.python-version` and bounded in
`requires-python = ">=3.13,<3.14"`. The Redis image digest
`sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44` is
pinned in both `compose.phase2.yml` and `.github/workflows/ci.yml`, and
`tests/test_artifact_reproducibility.py` fails if the two ever disagree.

### C.4 Gate (i) — zero skipped, demonstrated failing

The suite skips tests when `AEP_PHASE2_REDIS_INTEGRATION` is unset. This is
the "36 skipped = green" failure mode in miniature: **pytest itself exits 0.**

```
$ REDIS_URL=... pytest -q -ra --strict-markers --junitxml=junit-skip.xml
SKIPPED [1] tests\test_phase2_waitaof_integration.py:156: set AEP_PHASE2_REDIS_INTEGRATION=1 ...
SKIPPED [1] tests\test_phase2_waitaof_integration.py:196: set AEP_PHASE2_REDIS_INTEGRATION=1 ...
SKIPPED [1] tests\test_phase2_waitaof_integration.py:223: set AEP_PHASE2_REDIS_INTEGRATION=1 ...
1164 passed, 5 skipped in 23.52s
PYTEST_EXIT=0          <-- pytest reports SUCCESS

$ python scripts/check_pytest_gates.py --junit junit-skip.xml --output pytest-skip.txt --minimum-tests 1100
GATE FAILED: 5 test(s) were SKIPPED. In CI every precondition is provisioned, so a skip is an
unmet environment assumption, not a legitimate outcome. Re-run with -ra to see which, and either
fix the environment or delete the test.
GATES_EXIT=1
```

### C.5 Redis semantics gate, demonstrated failing and then satisfied

A GitHub Actions service container starts before checkout and cannot mount
`redis/phase2.conf`. A default Redis therefore has AOF **off**, which would
make every WAITAOF durability claim in `docs/22-formal-model.md` evidenced by
a server that cannot provide it. The gate refuses that:

```
$ docker run -d --rm --name aep-ci-sim -p 127.0.0.1:6399:6379 redis:7.2.5-alpine@sha256:6aaf...
$ python scripts/verify_redis_semantics.py --url redis://127.0.0.1:6399/15
GATE FAILED: appendonly: live server reports 'no', redis/phase2.conf requires 'yes'
EXIT=1

$ python scripts/verify_redis_semantics.py --url redis://127.0.0.1:6399/15 --apply
  applied appendonly='yes'
  applied appendfsync='everysec'
  applied aof-use-rdb-preamble='yes'
  applied save=''
  verified redis_version=7.2.5
  verified appendonly=yes
  verified appendfsync=everysec
  verified aof-use-rdb-preamble=yes
  verified aof_enabled=1
  verified waitaof=present
OK: live Redis matches phase2.conf semantics
EXIT=0
```

Values are read from `redis/phase2.conf`, not hardcoded, so CI cannot drift
from the compose environment.

### C.6 Why the CI Redis is split across two jobs — the measurement that forced it

`CONFIG SET` does not survive `docker restart`, so the one test that restarts
Redis cannot run against a service container. Measured directly rather than
assumed:

```
$ docker run -d --rm --name aep-restart-probe -p 127.0.0.1:6398:6379 redis:7.2.5-alpine@sha256:6aaf...
$ docker exec aep-restart-probe redis-cli CONFIG SET appendonly yes
OK
$ docker exec aep-restart-probe redis-cli -n 15 SET probe:key "SURVIVES?"
OK
$ docker exec aep-restart-probe redis-cli INFO persistence | grep ^aof_enabled
aof_enabled:1

$ docker restart aep-restart-probe

$ docker exec aep-restart-probe redis-cli CONFIG GET appendonly
appendonly
no
$ docker exec aep-restart-probe redis-cli INFO persistence | grep ^aof_enabled
aof_enabled:0
$ docker exec aep-restart-probe redis-cli -n 15 GET probe:key
                       <-- empty: the data is gone
```

Hence the arrangement: the `test` job (service container) deselects
`test_intent_and_resolution_survive_controlled_redis_restart` **by name and
loudly**, and the `waitaof-durability` job runs the whole integration file
against a compose-started Redis whose config *is* `phase2.conf`. Coverage of
that test moves between jobs; it is not dropped.
`tests/test_artifact_reproducibility.py::test_the_deselected_restart_test_is_run_by_the_durability_job`
fails if that arrangement is ever broken.

### C.7 Both CI jobs simulated locally, end to end

**`test` job** — against a default Redis container, exactly as a service
container would present:

```
$ python scripts/verify_redis_semantics.py --url redis://127.0.0.1:6399/15 --apply
OK: live Redis matches phase2.conf semantics

$ pytest -q -ra --strict-markers \
    --deselect "tests/test_phase2_waitaof_integration.py::test_intent_and_resolution_survive_controlled_redis_restart" \
    --junitxml=ci-junit.xml --cov=aep_core --cov-fail-under=90
Required test coverage of 90% reached. Total coverage: 90.31%
1195 passed, 1 deselected in 33.57s
PYTEST_EXIT=0

$ python scripts/check_pytest_gates.py --junit ci-junit.xml --output ci-out.txt --minimum-tests 1100
OK: 1195 tests, 0 skipped, 0 failed, 0 errors, 0 xpassed
GATES_EXIT=0

$ python scripts/validate_citations.py
docs/22-formal-model.md: 374 citations (240 explicit, 134 continuation)
OK: 374 citations, 0 invalid
CITATIONS_EXIT=0
```

**`waitaof-durability` job** — against compose, including the restart test:

```
$ python scripts/verify_redis_semantics.py --url redis://127.0.0.1:6381/15
OK: live Redis matches phase2.conf semantics

$ pytest -q -ra --strict-markers tests/test_phase2_waitaof_integration.py --junitxml=wa-junit.xml
....                                                                     [100%]
4 passed in 6.74s
PYTEST_EXIT=0

$ python scripts/check_pytest_gates.py --junit wa-junit.xml --output wa-out.txt --minimum-tests 1
OK: 4 tests, 0 skipped, 0 failed, 0 errors, 0 xpassed
GATES_EXIT=0

$ python scripts/verify_redis_semantics.py --url redis://127.0.0.1:6381/15   # after the restart test
  verified aof_enabled=1
  verified waitaof=present
OK: live Redis matches phase2.conf semantics
EXIT=0
```

AOF survived the restart in the compose job, which is precisely what the
service-container job could not offer.

### C.8 Final state

```
$ AEP_PHASE2_REDIS_INTEGRATION=1 REDIS_URL=... pytest -q -ra --strict-markers \
      --junitxml=final-junit.xml --cov=aep_core --cov-report=term --cov-fail-under=90

Name                                  Stmts   Miss  Cover
---------------------------------------------------------
aep_core\__init__.py                      0      0   100%
aep_core\core\__init__.py                 0      0   100%
aep_core\core\connector_contract.py      72      1    99%
aep_core\core\durability.py             158      1    99%
aep_core\core\exceptions.py               8      0   100%
aep_core\core\intent_recovery.py        237     31    87%
aep_core\core\intent_workflow.py        258     42    84%
aep_core\core\intents.py                383     46    88%
aep_core\core\locks.py                  110      4    96%
aep_core\core\request_binding.py        788     78    90%
aep_core\core\request_vault.py          251     22    91%
aep_core\core\state_codec.py             61      3    95%
aep_core\core\storage.py                181     15    92%
aep_core\core\validation.py              11      0   100%
---------------------------------------------------------
TOTAL                                  2518    243    90%
Required test coverage of 90% reached. Total coverage: 90.35%
1223 passed in 35.99s
PYTEST_EXIT=0

$ python scripts/check_pytest_gates.py --junit final-junit.xml --output final-out.txt --minimum-tests 1100
OK: 1223 tests, 0 skipped, 0 failed, 0 errors, 0 xpassed
EXIT=0

$ python scripts/validate_citations.py
docs/22-formal-model.md: 374 citations (240 explicit, 134 continuation)
OK: 374 citations, 0 invalid
EXIT=0

$ python scripts/verify_redis_semantics.py --url redis://127.0.0.1:6381/15
OK: live Redis matches phase2.conf semantics
EXIT=0

$ git log --oneline -5
9ded06e Phase 2A: CI with four gates, pinned environment, packaging hygiene
7c60337 Phase 2A: citation gate and coverage for the fail-closed branches
23e4ae5 Phase 2A: rename top-level package src -> aep_core
f19687a Phase 2A: correct roadmap figures and harden the test-cleanup guard
f4bb7a0 Phase 1A + 1B: formal model and correctness fixes

$ git status --short
                       <-- clean
```

---

## D. Requirement checklist

| # | Requirement | Status | Evidence |
|---|---|---|---|
| A1a | Replace the stale "218 passing tests" with the verified count | **DONE** | `PAPER_ROADMAP.md:14` and `:156` now read 674 with a pointer to the raw output. The third occurrence at `:69` is deliberately left: it sits inside the Phase 1B spec block and is an accurate record of the instruction as issued. Rewriting it would falsify history. |
| A1b | One-line note that Phase 1B was inserted between 1A and 2A, with its report path | **DONE** | `PAPER_ROADMAP.md:17`. Additionally `:55` re-labelled from "CURRENT PHASE: Phase 1B" to "Phase 1B — COMPLETE", and `:74` marked as the current phase, so the roadmap does not contradict reality. |
| A2-container | Suite runs against real Redis 7.2, AOF on, `phase2.conf` semantics, in a service container | **DONE** | `.github/workflows/ci.yml` `test` job, `services.redis`, digest-pinned. Semantics applied from `phase2.conf` and asserted (§C.5, §C.7). |
| A2-i | Gate: zero skipped tests | **DONE, demonstrated failing** | `scripts/check_pytest_gates.py`; §C.4 shows pytest exiting 0 with 5 skips and the gate refusing it. |
| A2-ii | Gate: zero xfail-turned-passing surprises, using `-ra` and grepping the summary | **DONE** | Same script parses the `-ra` short summary for `XPASS` lines and the `N xpassed` count; `xfail_strict = true` in `pyproject.toml` makes it a hard failure independently. Both directions tested in `tests/test_ci_gates.py`. |
| A2-iii | Gate: the roadmap's coverage gate | **DONE** | `--cov-fail-under=90` in CI plus `fail_under = 90` in `pyproject.toml`. Measured 90.35%. |
| A2-iv | Gate: citation range-validation for `docs/22-formal-model.md`, committed or equivalent | **DONE, and strengthened** | `scripts/validate_citations.py`, run by the `citations` CI job. Resolves 374 citations vs the 239 the Phase 1B ad-hoc validator resolved — the 134 bare `:NNN` continuation citations had never been checked. |
| A3 | Verify FLUSHALL state first and report findings before changing anything | **DONE** | §C.1 records the audit and its findings before the change. `FLUSHALL` was already gone; the real hole was the override's blast radius. |
| A4-scope | No `src/core` logic changes except mechanical import changes | **DONE** | §B and §C.2: 26 inserted, 26 deleted lines across the package, all imports; per-file blob diff confirms no non-import line changed. |
| A4-commit | Rename in a single commit with the full suite immediately before and after | **DONE** | Commit `23e4ae5`; 695 passed before, 695 passed after (§C.2). |
| A5 | Lockfile pins the exact dependency set the 674-pass run used | **DONE** | §C.3: 19/19 exact, zero mismatches. |
| A5b | Record Python 3.13.0 and the Redis image digest | **DONE** | `.python-version`, `requires-python`, `compose.phase2.yml`, `ci.yml`; agreement enforced by `tests/test_artifact_reproducibility.py`. |
| R2 | Lockfile (`uv lock`) + Redis image pinned by digest in compose | **DONE** | `uv.lock`; the digest pin already existed in `compose.phase2.yml` and is now asserted by test. |
| R3 | Safe test fixture: SCAN-based deletion + marker guard | **DONE** | §C.1. Cleanup uses `UNLINK` (the roadmap's own suggestion at `:81`) rather than `DEL`. |
| R4a | Rename `src` → `aep_core` | **DONE** | §C.2. |
| R4b | Remove committed `__pycache__` / egg-info; extend `.gitignore` | **DONE — nothing to remove** | `git ls-files | grep -cE "__pycache__|\.pyc$|egg-info"` returned `0`; `.gitignore` already covered both. Extended for `.ai/` session logs. |
| R4c | LICENSE, CITATION.cff, CHANGELOG | **DONE** | MIT `LICENSE`, `CITATION.cff` v0.2.0, `CHANGELOG.md`. |
| R4d | Release tag `v0.2.0` | **DONE** | Annotated tag on the report commit (see §H). |
| R5 | Coverage report wired into CI, target ≥ 90% on the package | **DONE** | 88% → 90.35%, achieved entirely by adding tests. |
| R1b | Separate CI job for the WAITAOF integration suite | **DONE** | `waitaof-durability` job, which additionally makes the restart test runnable (§C.6). |

**No requirement of this phase is NOT DONE or BLOCKED.**

---

## E. Deviations from the roadmap

1. **The `test` job deselects one test.** `PAPER_ROADMAP.md:79` asks for a
   service container and zero skips. `test_intent_and_resolution_survive_controlled_redis_restart`
   cannot run there, because `CONFIG SET` does not survive `docker restart`
   (measured, §C.6). It is deselected by name in that job and run in full by
   `waitaof-durability`. A deselection is not a skip — it does not appear in
   the JUnit counts — so this is a place where the gate could have been
   satisfied dishonestly. It is called out in the workflow, echoed at job
   runtime, recorded here, and asserted by a test.

2. **Roadmap `:69` still says "218".** A1 asked for the stale figure to be
   replaced. Two of the three occurrences were live claims and were corrected.
   The third is inside the Phase 1B spec block, quoting the instruction that
   was actually issued at the time; changing it would make the roadmap a less
   accurate record, not a more accurate one.

3. **Historical reports were not re-pointed after the rename.**
   `docs/22-formal-model.md` is a living document and its 161 `src/core`
   citations were updated. `reports/phase-report-1A`, `phase-report-1b`, and
   `docs/07`–`docs/21` still cite `src/core/...` deliberately: they describe a
   tree that existed. `docs/22` §0.05 records this explicitly. Only `docs/22`
   is under the CI citation gate.

4. **`fakeredis` remains a dependency.** The roadmap does not ask for its
   removal and CI never uses it (both jobs set `REDIS_URL`), but it is still
   the local fallback when `REDIS_URL` is unset. See §F3.

5. **Coverage was raised by adding tests, not by changing code.** A4 forbade
   touching package logic. Every one of the 549 tests added this phase targets
   an existing rejection branch; none required a source change.

---

## F. Known weaknesses, shortcuts, and what a hostile reviewer would attack

**F1. The coverage margin is thin, and the number is not perfectly stable.**
90.35% against a 90% gate is 9 statements of headroom. Two consecutive full
runs reported 243 and 244 missed statements — a ~0.04pp wobble, so at least
one covered line is timing- or ordering-dependent. A reviewer would rightly
say the gate is one unlucky refactor away from flapping. The honest reading:
the gate is met, the margin is small, and the wobble's source has not been
identified. Raising `intent_workflow.py` (84%) and `intent_recovery.py` (87%)
is the cheapest way to buy real headroom.

**F2. The citation gate proves range validity, not semantic correctness.** A
citation that drifts from line 400 to 402 inside the same file still passes.
This limit is stated in the script's own docstring, in `docs/22` §0, and is
pinned by a test named `test_a_drifted_but_in_range_citation_is_not_caught`.
It catches deletions, renames, and truncations — nothing more.

**F3. CI has never actually run.** Everything here was verified by simulating
both jobs locally against real containers (§C.7), which is strong evidence but
not the same as a green GitHub Actions run. The workflow has not executed on
GitHub's runners: `ubuntu-24.04` runner behaviour, `astral-sh/setup-uv@v5`
caching, and `services.redis` port mapping are all unexercised in situ. This
is the single largest untested claim in the phase.

**F4. Action versions are pinned by tag, not by commit SHA.**
`actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/upload-artifact@v4`
are mutable references. For an artifact-evaluation package that pins its Redis
by digest and its dependencies by lock, pinning actions by tag is
inconsistent. SHAs were not fabricated here because they could not be verified
offline; this is a deliberate, disclosed gap.

**F5. The marker guard can be satisfied by an attacker who can write to
Redis.** `aep:test-instance-marker` is a plain key. Anyone able to set it can
mark a production instance disposable. The guard defends against *mistake*
(a mis-pointed `REDIS_URL`), not against an adversary who already has write
access — at which point the marker is the least of the problems. Worth stating
plainly rather than letting "guard" imply more than it delivers.

**F6. Marker auto-provisioning weakens the guard on an empty DB 15.** The
marker is created automatically when the database is in the allowed set and
`DBSIZE == 0`. A production Redis that happens to be empty on DB 15 would
therefore be marked and cleaned. The trade was deliberate — requiring manual
marking everywhere would make local development hostile — but a reviewer
should know the guard is strongest exactly where it matters (populated
databases, overridden databases) and weakest on an empty allowed database.

**F7. The gate scripts are new and lightly exercised.** They have 57 tests
between them and both directions are covered, but they have run against
exactly one real repository state. Bugs in a gate are invisible by
construction: they surface as builds that pass when they should not.

**F8. `1223 passed` overstates the growth in *protocol* assurance.** 549 tests
were added, but they cover rejection branches, gate scripts, and artifact
metadata — not new protocol behaviour. The number of tests exercising the
write-ahead intent path is essentially unchanged since Phase 1B. A reviewer
who reads "674 → 1223" as "the protocol is twice as tested" would be wrong,
and the paper must not imply it.

**F9. Two vault behaviours were documented rather than changed.** Pydantic lax
mode coerces ASCII bytes to `str` in vault metadata, and the locator charset
is case-insensitive. Both are benign — the coerced value still has to satisfy
the safe-identifier pattern — and both are now pinned by tests so a future
change is deliberate. But "we wrote a test asserting the current behaviour" is
a weaker position than "we decided this is right", and I did not have grounds
to change AAD semantics under A4.

**F10. The suite is verified on one platform.** Every run in this report is
Windows 11 with a Linux Docker backend. CI targets `ubuntu-24.04`. Path
handling in `tests/test_connector_contract.py` and friends uses
`pathlib.Path("aep_core/core/...")` relative to the working directory, which
is portable, but no run on Linux has confirmed it.

**F11. `requires-python <3.14` is a claim about untested versions, inverted.**
Bounding it is the honest move, but it also means the artifact will refuse to
install on 3.14 even if it would work. That is a deliberate choice of
false-negative over false-positive.

---

## G. Open questions needing a human/architect decision

1. **Should the `test` job's deselection be removed by giving CI a
   config-file Redis?** The alternative is dropping the GitHub `services:`
   block in favour of `docker compose` in both jobs, which would let the
   restart test run everywhere and remove the deselection entirely — at the
   cost of no longer using a literal service container, which A2 specified.
   My recommendation is to switch: the deselection is the only place in this
   design where a gate could be satisfied without the work being done.

2. **Should the coverage gate be raised to ratchet?** A fixed 90% permits
   coverage to decay to 90.0%. A ratcheting gate (fail if coverage drops below
   the previous run) would prevent slow erosion but needs somewhere to store
   the previous value.

3. **Should `fakeredis` stay?** It exists so the suite runs without Docker,
   but it means a local `pytest` can pass against a backend that lacks
   `cjson`, skipping CAS tests. CI is unaffected. Removing it would make the
   Docker requirement hard and eliminate a class of local false confidence.

4. **Is MIT the right licence?** The roadmap offers "Apache-2.0 or MIT"
   (`PAPER_ROADMAP.md:82`) and the prompt said MIT (`:92`), so MIT was chosen.
   Apache-2.0's patent grant is the usual preference for artifacts that may be
   built on commercially. Trivial to change now, awkward after a Zenodo DOI.

5. **Should actions be SHA-pinned before artifact submission?** See F4. This
   needs network access to resolve the SHAs.

---

## H. Recommended next phase and its prerequisites

**Next phase: 2B — the evaluation harness** (`PAPER_ROADMAP.md` §3). This is
the heart of the paper and nothing in 2A blocks it.

**Before starting 2B, close these:**

1. **Push and observe one green CI run.** F3 is the largest open risk in this
   phase and it costs one push to retire. Everything else here is evidenced;
   this is not. `git push origin main` plus the `v0.2.0` tag, then read the
   Actions log.
2. **Decide question G1** (deselection vs. compose-everywhere) before the
   harness adds more Redis-restart-dependent tests, because the same
   constraint will bite again and harder.
3. **Buy coverage headroom** in `intent_workflow.py` and `intent_recovery.py`
   (F1). 2B will add code to both paths and a gate sitting on 9 statements of
   margin will start failing for reasons unrelated to the change under test.

**What 2B can rely on from this phase:**

- A reproducible environment: `uv sync --frozen` plus the digest-pinned Redis
  gives byte-identical dependencies and a server proven to support WAITAOF.
- A citation gate, so the formal model cannot silently drift as the harness
  changes `aep_core`.
- `scripts/verify_redis_semantics.py`, which the harness should call at the
  start of every experimental run so no result is ever collected against a
  Redis without AOF. That is worth wiring in from the first experiment, not
  retrofitting after a matrix has run.

**One caution for 2B.** The harness will want to kill workers with `SIGKILL`,
restart Redis, and inject partitions — all of which are exactly the operations
the test-instance marker guard makes deliberate. Expect to set
`aep:test-instance-marker` explicitly in harness setup, and do not weaken the
guard to make the harness convenient.

---

*Every figure in this report is from raw output pasted above. The suite count
is 1223, verified; the roadmap's long-standing 218 is corrected, and the
correction is itself recorded rather than quietly applied.*
