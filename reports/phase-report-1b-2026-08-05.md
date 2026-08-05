# Phase report — 1B (Correctness fixes required before any evaluation)

**Date:** 2026-08-05
**Repository:** Research-paper-AEP (single upstream commit `91c8324`)
**Executed by:** Claude Code session, effort level "max"

---

## A. Phase attempted and roadmap section reference

**Phase 1B — "Correctness fixes required before any evaluation."**

- Roadmap section: `PAPER_ROADMAP.md:53-69`, the block headed
  `### CURRENT PHASE: Phase 1B (... NOT in PAPER_ROADMAP.md; this block is its
  authoritative spec)`. This block did not exist when Phase 1A ran; it was
  added to the roadmap after `reports/phase-report-1A-2026-08-05.md` escalated
  four gaps.
- Declared scope (`PAPER_ROADMAP.md:55`): `src/core/`, `tests/`, and the phase
  report — plus `docs/22-formal-model.md` updates where a fix changes an
  enforcement table, residual window, or gap section (`PAPER_ROADMAP.md:69`).
- Items executed, in the order the roadmap specifies:
  1. Promote the response-class contract into production code (`:57`).
  2. Fault-isolate the recovery loop (`:59`).
  3. Make the WAITAOF ack a checked precondition of dispatch authority (`:61`).
  4. Define the evaluation composition (`:63`).
  5. Convert the two Phase 1A "reasoned hypotheses" into executable probes
     (`:65`).
  6. Environment prerequisite, done first (`:67`).
  7. Update `docs/22-formal-model.md` (`:69`).

No later phase was started. No CI workflow, lockfile, package rename, LICENSE,
CITATION.cff, harness, baseline, or manuscript work was performed (Phases 2A,
2B, 3, 4).

---

## B. Files created/modified

### Created

| File | Purpose |
|---|---|
| `src/core/connector_contract.py` | The production connector contract: `ReconciliationCapability`, `ReadbackResult`, `ReconciliationOutcome`, the permitted-result table, fail-closed capability resolution, and the total `classify_readback`. |
| `tests/test_connector_contract.py` | Fix 1 regression tests, including a source-level guard that no capability/result string literal remains in `intent_recovery.py`. |
| `tests/test_recovery_fault_isolation.py` | Fix 2 regression tests: one corrupt execution plus N healthy ones; unregistered connector; `run_forever` survival; cancellation still propagates. |
| `tests/test_dispatch_authorization.py` | Fix 3 regression tests: ack unforgeable/single-use/scope-bound; preflight refuses an unauthorized dispatch; forged authorization rejected. |
| `tests/test_evaluation_composition.py` | Fix 4 regression tests: `DispatchMode` gating for all three modes, plus evaluation-vault round-trip, create-once, tamper and transplant detection. |
| `tests/test_residual_probes.py` | Executable probes for Phase 1A residuals R1-3 and R3-5, plus the failing-then-passing test for the R3-5 local fix. |
| `tests/recovery_helpers.py` | Shared seeding helpers for the new Phase 1B test modules (kept separate so the pre-existing suite is untouched). |
| `tests/aof_rewind_probe.py` | Real-crash AOF probe. Deliberately **not** named `test_*` so pytest does not collect a nondeterministic experiment. |
| `reports/phase-report-1b-2026-08-05.md` | This report. |

### Modified

| File | Change |
|---|---|
| `src/core/intents.py` | New `DispatchAuthorizationError`; new `_DISPATCH_AUTHORIZATION_SCRIPT` + `authorize_dispatch`; preflight now takes and verifies an `authorization`; retention floor extended to cover `PERMANENTLY_AMBIGUOUS`. |
| `src/core/intent_recovery.py` | Typed connector contract replaces string literals; per-execution fault isolation in `scan_once`; `return_exceptions=True`; `run_forever` survives a failed pass with backoff; `RecoveryScanPhase`/`RecoveryScanFailure`/`scan_failure_alert`. |
| `src/core/intent_workflow.py` | New `DispatchMode` and rewritten `validate_startup`; `_confirm_dispatch_barrier` mints the ack; `execute` converts the ack into a Redis authorization and passes it to preflight. |
| `src/core/durability.py` | New `dispatch_scope`, `DurabilityAck`, HMAC provenance boundary, `consume_durability_ack`, `confirm_durable_ack`. |
| `src/core/request_vault.py` | New `EvaluationRedisRequestVault` (durable, AES-GCM, create-once, `test_only=False`). |
| `tests/mock_connector.py` | Imports `ReconciliationCapability`/`ReadbackResult` from `src.core.connector_contract` instead of defining them. |
| `docs/22-formal-model.md` | Revised for all four fixes; every `file:line` citation re-derived against the post-fix tree (239 citations, all range-validated). |

### Environment artifacts (not repository content)

`.venv/` — Python 3.13.0 virtualenv. Already covered by `.gitignore`
(`.venv` entry under "Virtual environments"). Not committed.
`.ai/track.md` — written automatically by the installed SDLC plugin hook on
each Write/Edit; not an intentional deliverable.

**Not modified:** `pyproject.toml`, `compose.phase2.yml`, `redis/phase2.conf`,
`docs/01`–`docs/21`, `tests/conftest.py`, and every pre-existing test module.

---

## C. Raw command outputs

All commands run from `D:/personal/AEP/Research-paper-AEP` in Git Bash on
Windows 11. Test commands use
`AEP_PHASE2_REDIS_INTEGRATION=1 REDIS_URL=redis://127.0.0.1:6381/15`.

### C.0 Environment prerequisite (`PAPER_ROADMAP.md:67`)

```
$ py -0p
 -V:3.13 *        D:\Python-3.13\python.exe
 -V:3.11          C:\Users\HamzaKhan\AppData\Local\Programs\Python\Python311\python.exe
 -V:Astral/CPython3.12.13 C:\Users\HamzaKhan\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe
exit=0
$ uv --version
uv 0.11.8 (0e961dd9a 2026-04-27 x86_64-pc-windows-msvc)
exit=0
$ docker compose version
Docker Compose version v5.1.3
exit=0
```

Docker CLI was present but the daemon was **not** running:

```
$ docker compose -f compose.phase2.yml up -d
unable to get image 'redis:7.2.5-alpine@sha256:6aaf...': failed to connect to the docker API at
npipe:////./pipe/dockerDesktopLinuxEngine; check if the path is correct and if the daemon is
running: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
exit=1
```

Docker Desktop was started and the daemon came up:

```
$ "/c/Program Files/Docker/Docker/Docker Desktop.exe" &
launch issued exit=0
[2026-08-05T07:42:35.079467400Z][Docker Desktop.exe] launching  C:\Program Files\Docker\Docker\resources\com.docker.backend.exe
daemon up after ~10s
$ docker info --format 'ServerVersion={{.ServerVersion}} OS={{.OSType}}'
ServerVersion=29.4.3 OS=linux
exit=0
```

Virtualenv and dependency install:

```
$ uv venv --python "D:/Python-3.13/python.exe" .venv
Using CPython 3.13.0 interpreter at: D:\Python-3.13\python.exe
Creating virtual environment at: .venv
exit=0
$ ./.venv/Scripts/python.exe --version
Python 3.13.0
exit=0
$ uv pip install --python ./.venv/Scripts/python.exe "redis>=5.0" "pydantic>=2.0" "cryptography>=46.0" "pytest>=8.0" "pytest-asyncio>=0.23" "fakeredis[lua]>=2.20"
Installed 19 packages in 1.35s
 + annotated-types==0.8.0
 + cffi==2.1.1
 + colorama==0.4.6
 + cryptography==50.0.0
 + fakeredis==2.37.0
 + iniconfig==2.3.0
 + lupa==2.8
 + packaging==26.3
 + pluggy==1.6.0
 + pycparser==3.0
 + pydantic==2.13.4
 + pydantic-core==2.46.4
 + pygments==2.20.0
 + pytest==9.1.1
 + pytest-asyncio==1.4.0
 + redis==8.1.0
 + sortedcontainers==2.4.0
 + typing-extensions==4.16.0
 + typing-inspection==0.4.2
exit=0
```

Redis 7.2 brought up from `compose.phase2.yml` and capability-verified:

```
$ docker compose -f compose.phase2.yml up -d
 Image redis:7.2.5-alpine@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44 Pulled
 Container aep-phase2-redis72 Started
exit=0
$ docker compose -f compose.phase2.yml ps
NAME                 IMAGE                                     ...  STATUS                   PORTS
aep-phase2-redis72   redis:7.2.5-alpine@sha256:6aaf3f5e...     ...  Up 7 seconds (healthy)   127.0.0.1:6381->6379/tcp
exit=0
$ docker exec aep-phase2-redis72 redis-cli INFO server | grep ^redis_version
redis_version:7.2.5
exit=0
$ docker exec aep-phase2-redis72 redis-cli CONFIG GET appendonly
appendonly
yes
exit=0
$ docker exec aep-phase2-redis72 redis-cli CONFIG GET appendfsync
appendfsync
everysec
exit=0
$ docker exec aep-phase2-redis72 redis-cli INFO persistence | grep ^aof_enabled
aof_enabled:1
exit=0
$ docker exec aep-phase2-redis72 redis-cli COMMAND INFO WAITAOF | head -3
waitaof
4
noscript
exit=0
$ ./.venv/Scripts/python.exe -c "import redis;r=redis.Redis.from_url('redis://127.0.0.1:6381/15',decode_responses=True);print('PING',r.ping())"
PING True
exit=0
```

**Baseline suite, before any Phase 1B change.** First without the integration
flag, then with it:

```
$ REDIS_URL=... pytest -q -ra
...................ssss..................
SKIPPED [1] tests\test_phase2_waitaof_integration.py:110: set AEP_PHASE2_REDIS_INTEGRATION=1 and REDIS_URL to the dedicated Redis 7.2+ AOF DB 15
SKIPPED [1] tests\test_phase2_waitaof_integration.py:156: ...
SKIPPED [1] tests\test_phase2_waitaof_integration.py:196: ...
SKIPPED [1] tests\test_phase2_waitaof_integration.py:223: ...
607 passed, 4 skipped in 25.63s
PYTEST_EXIT=0

$ AEP_PHASE2_REDIS_INTEGRATION=1 REDIS_URL=... pytest -q -ra
611 passed in 29.14s
PYTEST_EXIT=0
```

> **The roadmap's "218 passing tests" figure (`PAPER_ROADMAP.md:14`, repeated at
> `:154`) is wrong. The verified pre-Phase-1B baseline is 611 passed, 0
> skipped, against real Redis 7.2.5 with AOF.**

### C.1 Fix 1 — response-class contract in production code

**Before (failing):**

```
$ pytest -q -ra tests/test_connector_contract.py
ImportError while importing test module 'tests\test_connector_contract.py'.
tests\test_connector_contract.py:16: in <module>
    from src.core.connector_contract import (
E   ModuleNotFoundError: No module named 'src.core.connector_contract'
ERROR tests/test_connector_contract.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.23s
PYTEST_EXIT=2
```

**After (passing):**

```
$ pytest -q -ra tests/test_connector_contract.py
......................                                                   [100%]
22 passed in 0.15s
PYTEST_EXIT=0

$ pytest -q -ra          # full suite
633 passed in 27.53s
PYTEST_EXIT=0
```

### C.2 Fix 2 — recovery fault isolation

**Before (failing):**

```
$ pytest -q -ra tests/test_recovery_fault_isolation.py
ImportError while importing test module 'tests\test_recovery_fault_isolation.py'.
tests\test_recovery_fault_isolation.py:16: in <module>
    from src.core.intent_recovery import RecoveryScanPhase
E   ImportError: cannot import name 'RecoveryScanPhase' from 'src.core.intent_recovery'
ERROR tests/test_recovery_fault_isolation.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.18s
PYTEST_EXIT=2
```

**After (passing):**

```
$ pytest -q -ra tests/test_recovery_fault_isolation.py
.......                                                                  [100%]
7 passed in 0.35s
PYTEST_EXIT=0

$ pytest -q -ra          # full suite
640 passed in 28.54s
PYTEST_EXIT=0
```

### C.3 Fix 3 — WAITAOF ack as a checked dispatch precondition

**Before (failing):**

```
$ pytest -q -ra tests/test_dispatch_authorization.py
ImportError while importing test module 'tests\test_dispatch_authorization.py'.
tests\test_dispatch_authorization.py:16: in <module>
    from src.core.durability import (
E   ImportError: cannot import name 'DurabilityAck' from 'src.core.durability'
ERROR tests/test_dispatch_authorization.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.18s
PYTEST_EXIT=2
```

**After (passing):**

```
$ pytest -q -ra tests/test_dispatch_authorization.py
.............                                                            [100%]
13 passed in 0.29s
PYTEST_EXIT=0

$ pytest -q -ra          # full suite
653 passed in 27.88s
PYTEST_EXIT=0
```

### C.4 Fix 4 — evaluation composition

**Before (failing):**

```
$ pytest -q -ra tests/test_evaluation_composition.py
ImportError while importing test module 'tests\test_evaluation_composition.py'.
tests\test_evaluation_composition.py:24: in <module>
    from src.core.intent_workflow import (
E   ImportError: cannot import name 'DispatchMode' from 'src.core.intent_workflow'
ERROR tests/test_evaluation_composition.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.19s
PYTEST_EXIT=2
```

**After (passing):**

```
$ pytest -q -ra tests/test_evaluation_composition.py
.................                                                        [100%]
17 passed in 0.39s
PYTEST_EXIT=0

$ pytest -q -ra          # full suite
670 passed in 28.48s
PYTEST_EXIT=0
```

### C.5 Residual probes

**Before the R3-5 local fix — the probes confirm both hypotheses, and the
fix-test fails:**

```
$ pytest -q -ra tests/test_residual_probes.py
...F                                                                     [100%]
================================== FAILURES ===================================
__________ test_sub_retention_ttl_is_refused_for_an_escalated_record __________
    @pytest.mark.asyncio
    async def test_sub_retention_ttl_is_refused_for_an_escalated_record(
        redis_client, storage_adapter, lock_manager
    ):
>       with pytest.raises(IntentInvariantError):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE IntentInvariantError

tests\test_residual_probes.py:242: Failed
=========================== short test summary info ===========================
FAILED tests/test_residual_probes.py::test_sub_retention_ttl_is_refused_for_an_escalated_record
1 failed, 3 passed in 0.22s
PYTEST_EXIT=1
```

The three passing tests in that run are the probe assertions themselves:
R1-3 (simulated rewind un-fences a stale writer), the mechanism behind it
(no `WAITAOF` in `src/core/locks.py`), and R3-5 (escalated-record retention is
finite). **Both Phase 1A hypotheses are therefore confirmed, not refuted.**

**After the local fix:**

```
$ pytest -q -ra tests/test_residual_probes.py
....                                                                     [100%]
4 passed in 0.16s
PYTEST_EXIT=0
```

**Real-crash AOF probe (manual experiment, 3 rounds):**

```
$ AEP_PROBE_ROUNDS=3 ./.venv/Scripts/python.exe tests/aof_rewind_probe.py
probe: redis=redis://127.0.0.1:6381/15 container=aep-phase2-redis72 rounds=3
  round: 1
  execution_id: 6d97b66b-dd4f-4e32-bd27-a8632a7e66d0
  released_before_kill: True
  kill: exit=0 aep-phase2-redis72
  start: exit=0 aep-phase2-redis72
  version_after_replay: 2
  state_lost_entirely: False
  version_rewound: False
  lease_resurrected: False
  ---
  round: 2
  execution_id: 72d44e1f-7ae9-49ef-9da5-341066ad6b39
  released_before_kill: True
  kill: exit=0 aep-phase2-redis72
  start: exit=0 aep-phase2-redis72
  version_after_replay: 2
  state_lost_entirely: False
  version_rewound: False
  lease_resurrected: False
  ---
  round: 3
  execution_id: 7e865512-b9b1-4a52-b8fa-bc775463a446
  released_before_kill: True
  kill: exit=0 aep-phase2-redis72
  start: exit=0 aep-phase2-redis72
  version_after_replay: 2
  state_lost_entirely: False
  version_rewound: False
  lease_resurrected: False
  ---
rounds=3 version_rewound=0 lease_resurrected=0
NOTE: a zero count does NOT refute R1-3; it means this run did not land inside the appendfsync everysec window.
PROBE_EXIT=0
```

**Reading this honestly:** in 3 SIGKILL rounds the AOF replay lost nothing, so
the *frequency* of a real rewind is unmeasured and is certainly low at this
write rate. The deterministic probe establishes the *consequence* if one
occurs. R1-3 is therefore stated in `docs/22-formal-model.md` as
consequence-confirmed, frequency-unmeasured.

### C.6 Final state

```
$ AEP_PHASE2_REDIS_INTEGRATION=1 REDIS_URL=... pytest -q -ra --strict-markers
........................................................................ [ 42%]
........................................................................ [ 53%]
........................................................................ [ 64%]
........................................................................ [ 74%]
........................................................................ [ 85%]
........................................................................ [ 96%]
..........................                                               [100%]
674 passed in 27.77s
PYTEST_EXIT=0

$ ./.venv/Scripts/python.exe --version
Python 3.13.0
exit=0

$ uv pip freeze --python ./.venv/Scripts/python.exe
annotated-types==0.8.0
cffi==2.1.1
colorama==0.4.6
cryptography==50.0.0
fakeredis==2.37.0
iniconfig==2.3.0
lupa==2.8
packaging==26.3
pluggy==1.6.0
pycparser==3.0
pydantic==2.13.4
pydantic-core==2.46.4
pygments==2.20.0
pytest==9.1.1
pytest-asyncio==1.4.0
redis==8.1.0
sortedcontainers==2.4.0
typing-extensions==4.16.0
typing-inspection==0.4.2
exit=0

$ git status --short
 M src/core/durability.py
 M src/core/intent_recovery.py
 M src/core/intent_workflow.py
 M src/core/intents.py
 M src/core/request_vault.py
 M tests/mock_connector.py
?? .ai/
?? PAPER_ROADMAP.md
?? docs/22-formal-model.md
?? reports/
?? src/core/connector_contract.py
?? tests/aof_rewind_probe.py
?? tests/recovery_helpers.py
?? tests/test_connector_contract.py
?? tests/test_dispatch_authorization.py
?? tests/test_evaluation_composition.py
?? tests/test_recovery_fault_isolation.py
?? tests/test_residual_probes.py
exit=0
```

### C.7 Citation validation for `docs/22-formal-model.md`

Script run via stdin (no file written to the repo); it extracts every
backticked `path:line` / `path:a-b` citation, checks the file exists and the
range is within its line count.

```
citations: 239 invalid: 0
exit=0
```

Semantic spot-check of the corrected anchors:

```
src/core/intent_recovery.py               202 |         now = await self.store.redis_time()
src/core/intent_recovery.py               367 |             now = await self.store.redis_time()
src/core/intent_recovery.py               124 |         self.scan_failure_alert = scan_failure_alert
src/core/intent_recovery.py               123 |         self.recovery_lag_alert = recovery_lag_alert
src/core/intent_recovery.py               379 |             if intent.status is IntentStatus.ABOUT_TO_FIRE:
src/core/intents.py                      1186 |         supplied_authorization = authorization if type(authorization) is str else ""
src/core/intents.py                       573 | local unresolved_by_step = {}
src/core/intent_workflow.py               162 |         if mode is None:
src/core/durability.py                    229 |     async def validate_startup(
tests/test_residual_probes.py             125 | async def test_probe_lock_keys_are_not_covered_by_the_durability_barrier(
tests/test_residual_probes.py             207 | async def test_probe_escalated_record_retention_is_finite(
tests/test_residual_probes.py             232 | async def test_sub_retention_ttl_is_refused_for_an_escalated_record(
```

**Range validation proves no citation points outside a file; it does not prove
semantic correctness.** Semantic correctness rests on the per-anchor grep and
spot-check output above plus the files read during the session.

---

## D. Requirement checklist

| # | Requirement (`PAPER_ROADMAP.md`) | Status | Evidence |
|---|---|---|---|
| E1 | "install/pin Python 3.13 and project dependencies so the test suite can actually run" (`:67`) | **DONE** | §C.0: `.venv` on CPython 3.13.0; 19 packages installed; exact versions in §C.6. |
| E2 | "verify the full suite passes against real Redis 7.2 via compose.phase2.yml" (`:67`) | **DONE** | §C.0: `redis_version:7.2.5`, `appendonly yes`, `appendfsync everysec`, `aof_enabled:1`, `COMMAND INFO WAITAOF` present; baseline `611 passed`, exit 0. |
| E3 | "Paste raw output including the total pass count — this also verifies or corrects the roadmap's unverified '218 passing tests' figure" (`:67`) | **DONE — figure CORRECTED** | §C.0. Baseline 611, final 674. The roadmap's 218 (`PAPER_ROADMAP.md:14`, `:154`) is wrong. |
| 1a | "Move ReconciliationCapability (and any related connector-contract types) from tests/mock_connector.py into src/core (typed Enum or Protocol)" (`:57`) | **DONE** | `src/core/connector_contract.py:36-45` (capability), `:47-54` (`ReadbackResult`), `:101` (`ReconciliationConnector` Protocol). `tests/mock_connector.py:24-27` imports them. Identity asserted by `tests/test_connector_contract.py:36-45`. |
| 1b | "Replace every string-literal comparison in src/core/intent_recovery.py with the typed contract" (`:57`) | **DONE** | `src/core/intent_recovery.py:404`, `:424`, `:469`. Mechanically guarded by `tests/test_connector_contract.py:318-330`, which fails if any capability/result literal reappears. |
| 1c | "POSITIVE_ONLY_READBACK must have explicit, tested handling — no fall-through behaviour for any of the three classes" (`:57`) | **DONE** | `classify_readback` is total (`src/core/connector_contract.py:171-240`); the positive-only negative case is a named violation (`:220`). Tests: totality over both querying classes (`tests/test_connector_contract.py:88-101`), named violation (`:126-135`), `NO_READBACK` rejected from classification (`:117-123`), undeclared capability fails closed (`:236-251`), end-to-end reason recorded (`:277-299`). |
| 1d | "tests/mock_connector.py then imports the contract from src" (`:57`) | **DONE** | `tests/mock_connector.py:24-27`. |
| 2a | "wrap per-execution handling so StateCorruptionError or any single-execution exception quarantines/records that execution and continues the scan" (`:59`) | **DONE** | `src/core/intent_recovery.py:213-221` (discovery isolation), `:245-259` (per-task isolation), recorded as `RecoveryScanFailure` (`:68-79`, `:153-190`). Quarantine already happens inside `get_execution`; asserted by `tests/test_recovery_fault_isolation.py:82-101`. |
| 2b | "use return_exceptions=True (or equivalent structured handling) for gathered tasks" (`:59`) | **DONE** | `src/core/intent_recovery.py:241`; guarded by `tests/test_recovery_fault_isolation.py:209-216`. |
| 2c | "run_forever must survive a scan_once failure with backoff" (`:59`) | **DONE** | `src/core/intent_recovery.py:291-311` (exponential backoff, reset on success), cancellation still propagates (`:289-290`). Tests: `tests/test_recovery_fault_isolation.py:157-185`, `:188-206`. |
| 2d | "Regression test: a keyspace with one corrupt execution and N healthy ones — all N healthy executions must still be processed" (`:59`) | **DONE** | `tests/test_recovery_fault_isolation.py:41-79` — 1 corrupt + 4 healthy; asserts the processed set equals the healthy set and each reached `FIRED_CONFIRMED`. Before/after raw output in §C.2. |
| 3a | "the barrier ack mints a dispatch authorization recorded in Redis ... and the dispatch gate / preflight Lua verifies it before the connector call can be made" (`:61`) | **DONE** | Mint: `src/core/durability.py:161-176`. Unforgeable/single-use/scope-bound: `:75-155`. Redis record: `src/core/intents.py:1081-1162` → `_DISPATCH_AUTHORIZATION_SCRIPT` `:649-675`. Preflight verification: `src/core/intents.py:639`, fail-closed default `:1186`. Wiring: `src/core/intent_workflow.py:481-490`, `:496-504`. |
| 3b | "Document the exact mechanism and its residual window in docs/22-formal-model.md (update the P2 section; keep file:line citations current)" (`:61`) | **DONE** | `docs/22-formal-model.md` §3.2 B (the four-step chain) and residuals R2-7, R2-8. All 239 citations re-derived and range-validated (§C.7). |
| 4 | "Either (a) production-shaped composition ... or (b) an explicit EVALUATION mode whose only difference from production is the connector endpoint, enforce that difference in code, and document it in docs/22. Silent test-only measurement is not acceptable." (`:63`) | **DONE via (b), with the vault upgraded toward (a)** | `DispatchMode` (`src/core/intent_workflow.py:39-52`), gate (`:226-309`). PRODUCTION and EVALUATION share one requirement block; only the connector-endpoint check differs (`:292-307`). A durable, non-test `EvaluationRedisRequestVault` (`src/core/request_vault.py:321-451`) means EVALUATION needs no `test_only` vault and no `allow_test_*` flag — asserted by `tests/test_evaluation_composition.py:225-245`. Documented in `docs/22-formal-model.md` §1.7 and NC-11. |
| 5a | Probe: "AOF rewind un-fencing a lease" (`:65`) | **DONE — confirmed, no local fix, documented as residual** | Deterministic probe `tests/test_residual_probes.py:46-121`; mechanism pin `:125-145`; real-crash experiment `tests/aof_rewind_probe.py` with raw output in §C.5. Documented as R1-3 in `docs/22-formal-model.md` §3.1. The fix is consensus/HA, an explicit non-claim (NC-3). |
| 5b | Probe: "escalated records expiring at TTL" (`:65`) | **DONE — confirmed, local fix applied, remainder documented** | Probe `tests/test_residual_probes.py:207-228`. Local fix: retention floor extended to `PERMANENTLY_AMBIGUOUS` (`src/core/intents.py:592-599`), failing-then-passing test `tests/test_residual_probes.py:232-245` with raw output in §C.5. Remaining finite-retention behaviour documented as R3-5. |
| 6 | "Update docs/22-formal-model.md wherever these fixes change an enforcement table, residual window, or gap section" (`:69`) | **DONE** | New §0.1 change table; §1.5(b), §1.6, §1.7 rewritten; §3.2 B added; assumption A2 promoted to enforced and A4 retired; R2-7 rewritten, R2-8 added; R1-2, R1-3, R3-1, R3-5 updated; §5 reduced from 6 gaps to 5 with two closed; §6 evidence index rebuilt. |
| 7 | "each with a failing-then-passing regression test written BEFORE the fix" (`:55`) | **DONE for all four fixes and for the R3-5 fix** | §C.1–§C.5 each show the failing run (exit 2 or 1) captured before the implementation and the passing run after. |

**No requirement of this phase is NOT DONE or BLOCKED.**

---

## E. Deviations from the roadmap

1. **Fix 4 was executed as option (b), not option (a).** The roadmap permits
   this if (a) "is not achievable this phase". A real production vault requires
   a KMS-backed backend that `docs/15-production-vault-kms-design.md` designs
   but nobody has built; standing one up in this session would have meant
   shipping unreviewed key-management code. I took the middle path the roadmap
   allows under (a) — "a documented evaluation vault with identical semantics"
   — so that EVALUATION mode needs **no** `test_only` vault and **no**
   `allow_test_dispatch`/`allow_test_barrier` flag, and only the connector
   endpoint differs from PRODUCTION. Alternatives considered: (i) build a
   KMS-backed vault now — rejected as under-testable in one session; (ii)
   declare EVALUATION mode without a durable vault — rejected because the
   "only difference is the endpoint" claim would then be false.

2. **The dispatch authorization is verified but not consumed by the preflight.**
   Consuming it would make the preflight a writer, contradicting
   `docs/06-phase2-design.md:240-247`, which specifies a read-only preflight.
   Replay is already fenced by the existing status and version checks
   (`src/core/intents.py:624-626`). Recorded as residual R2-8 with the
   alternative stated.

3. **`DispatchAuthorizationError` is a sibling of `IntentPreflightError`, not a
   subclass.** Consequence: when the authorization check fails, `execute` does
   **not** take the "write FAILED_CONFIRMED" branch; it propagates and leaves
   the conservative `ABOUT_TO_FIRE` for recovery. Writing `FAILED_CONFIRMED`
   would also have been sound (no bytes were sent), but leaving the record for
   recovery is the strictly safer default and avoids widening a path I could
   not exercise end-to-end this phase.

4. **An undeclared connector capability resolves to `PERMANENTLY_AMBIGUOUS`
   without a read-back**, rather than raising or retrying forever
   (`src/core/intent_recovery.py:403-422`). Alternatives considered: (i) raise
   and skip — rejected because the intent would then never terminate,
   violating P3; (ii) attempt the read-back anyway — rejected because evidence
   whose authority is unknown cannot be interpreted. The chosen behaviour is
   operator-recoverable via the `PERMANENTLY_AMBIGUOUS → FAILED_CONFIRMED`
   edge.

5. **`declared_capability` accepts an exact-value string as well as an enum
   member** (`src/core/connector_contract.py:118-140`). Strict
   member-only acceptance was considered; exact-value strings are safe because
   any typo raises, and accepting them keeps third-party connectors workable.

6. **Unparseable read-back evidence still degrades to `UNKNOWN`** rather than
   escalating immediately (`src/core/connector_contract.py:142-169`). Both
   routes end at `PERMANENTLY_AMBIGUOUS`; `UNKNOWN` simply spends budget first.
   This preserves pre-existing tested behaviour.

7. **Two new test-support files were added** (`tests/recovery_helpers.py`,
   `tests/aof_rewind_probe.py`) beyond the fixes themselves, to avoid editing
   the 611 pre-existing passing tests. `tests/aof_rewind_probe.py` is
   deliberately not collected by pytest so a nondeterministic experiment cannot
   make the suite flaky.

8. **No lockfile was committed.** "pin ... project dependencies" was satisfied
   by pinning the interpreter and recording exact installed versions in §C.6; a
   committed lockfile is Phase 2A task 2 (`PAPER_ROADMAP.md:78`) and Rule 1
   forbids starting it.

9. **Docker Desktop was started.** The roadmap asserts "Docker is available";
   the CLI was, but the daemon was not running. Starting it was necessary to
   satisfy the environment gate and is recorded verbatim in §C.0.

---

## F. Known weaknesses, shortcuts, and what a hostile reviewer would attack

**F1. The dispatch authorization cannot prove that Redis fsynced — and I want
to be blunt about how much Fix 3 actually buys.** Redis exposes no way for a
Lua script to verify that a prior `WAITAOF` on some connection succeeded. What
Fix 3 changes is that the ordering is now *checked* rather than merely
*followed*: the authorization key is written by exactly one script, that script
is reachable only through `authorize_dispatch`, and `authorize_dispatch` first
consumes an unforgeable, single-use, scope-bound `DurabilityAck` that only a
`True` barrier can mint. But (i) anyone with direct Redis access can write the
authorization key themselves, and (ii) code inside this process can still
compose `RequestBindingService.verify` with a connector and bypass the runner
entirely. A reviewer who reads `PAPER_ROADMAP.md:32`'s contribution statement
as "the protocol makes it impossible to dispatch without a durable intent" will
find that overstated. R2-7 states the limits.

**F2. The real AOF-rewind probe did not reproduce a rewind.** Three SIGKILL
rounds, zero rewinds (§C.5). I am claiming only that the *consequence* of a
rewind is confirmed (by a simulated restore of the exact prior key bytes), not
that rewinds occur at any measured rate. A reviewer could fairly say the
deterministic probe assumes its own premise: it restores the state and lock
keys by hand and then shows the CAS accepts the old writer. That is a valid
criticism of the probe's strength; it is not a criticism of the conclusion,
which follows from the CAS predicate itself. Measuring the real rate needs the
Phase 2B harness with a write-rate high enough to sit inside the `everysec`
window.

**F3. The evaluation vault stores request material in the same Redis as
execution state.** That is a security downgrade relative to
`docs/15-production-vault-kms-design.md`, which specifies a separate KMS
boundary. It is declared in `src/core/request_vault.py:325-339` and in
`docs/22-formal-model.md` §1.7, but a reviewer is entitled to say that an
"evaluation composition" that co-locates secrets with state is not
production-shaped in the way that matters most for a security argument. Keys
are also operator-supplied with no rotation or attestation.

**F4. EVALUATION mode is enforced but never exercised end-to-end.**
`tests/test_evaluation_composition.py:225-245` asserts that `validate_startup`
passes with no test flags, and the vault has its own round-trip and tamper
tests — but **no test dispatches a real mutation in EVALUATION mode.** The 22
crash-boundary runner tests all still run in TEST mode. So the composition is
proven *admissible*, not proven *functional*. Phase 2B must build an evaluation
connector and re-run the crash matrix under EVALUATION, or the paper's
evaluation section will still describe a TEST-mode measurement.

**F5. `PRODUCTION` mode is unreachable and therefore untested in the positive
direction.** Every PRODUCTION test asserts a rejection. There is no evidence
that PRODUCTION would work if a production vault and connector existed; the
mode is a declaration plus a set of refusals.

**F6. The retention fix narrows R3-5 but does not close it.** Escalated records
now get at least 31 days instead of possibly one second, but Redis still
deletes them when the floor elapses. A protocol that promises "fail closed and
escalate" and then silently garbage-collects the escalation after a month is
still, in the limit, fail-forgotten. The real fix is exporting escalations to a
store outside the TTL regime, which is out of scope here.

**F7. Fault isolation converts a loud failure into a quiet one.** Before Fix 2,
a corrupt execution crashed the recovery loop — catastrophic, but impossible to
miss. Now it is recorded in `last_scan_failures`, logged at WARNING, and
optionally passed to `scan_failure_alert`. Since **nothing in the repository
consumes any of those** (§5.2 of docs/22), a deployment that ignores logs will
now silently never reconcile a poisoned execution. I judged this the right
trade — one bad key must not stop the other N — but it does move the failure
from "obvious" to "needs monitoring", and there is still no alerting component.

**F8. `MAX_RETAINED_SCAN_FAILURES` bounds the failure list but the candidate
list is still unbounded.** `scan_once` accumulates every eligible
`(execution_id, intent_id)` pair before acting
(`src/core/intent_recovery.py:202-236`). The memory-bound gap raised in
`docs/07-phase2-gap-audit.md:33` is still open (R3-6). I did not fix it because
it was not in the Phase 1B list.

**F9. The source-literal guard test is a proxy, not a proof.** 
`tests/test_connector_contract.py:318-330` greps `intent_recovery.py` for
capability/result string literals. It would not catch a literal reintroduced in
a different module, or a comparison written with `.value`. It encodes the
roadmap's wording rather than the underlying property.

**F10. Test-module cross-imports.** `tests/test_connector_contract.py` and
`tests/test_dispatch_authorization.py` import private helpers (`_seed`,
`_create_bound`, `_policy`, `_seed_stale_about`, `_service`) from other test
modules. That is brittle: renaming a helper in one module breaks unrelated
files. I chose it over duplicating ~60 lines of fixture three times, but it is
a maintenance smell.

**F11. No coverage measurement was run.** The suite grew from 611 to 674 tests,
but I have not measured line coverage of the new code, and `pytest-cov` is not
installed. Some branches of the new code — notably the
`scan_failure_alert` exception-suppression path
(`src/core/intent_recovery.py:184-190`) and several
`EvaluationRedisRequestVault` error branches — may be unexercised. Coverage
gating is Phase 2A task 6.

**F12. Everything ran on one machine, one Redis, one Python.** No matrix, no
CI, no second platform. `fakeredis` is installed but every run in this report
used real Redis via `REDIS_URL`; the fakeredis path is now untested by me and
could have rotted with the new Lua scripts.

---

## G. Open questions needing a human/architect decision

1. **Does EVALUATION mode need an end-to-end dispatch test before Phase 2B, or
   is that Phase 2B's first task?** (F4.) My recommendation: make "port the
   crash-boundary matrix to EVALUATION mode" the first item of Phase 2B, so
   the harness cannot silently keep measuring TEST mode.

2. **Is the evaluation vault's shared-trust-domain compromise acceptable for
   the paper's threat story?** (F3.) If not, a KMS-backed vault becomes a
   prerequisite for Phase 2B rather than a later nicety.

3. **Should escalations be exported outside Redis?** (F6.) Options: a durable
   incident sink, a non-expiring `aep:escalation:*` namespace, or accepting the
   31-day bound and documenting it as a deployment requirement.

4. **Should an alerting component be built now?** (F7, §5.2 of docs/22.) The
   fault-isolation change makes monitoring load-bearing for the first time.
   `scan_failure_alert` and `recovery_lag_alert` are hooks with no
   implementation behind them.

5. **How hard should the paper lean on Fix 3?** (F1.) The honest claim is
   "checked precondition with two declared bypasses", not "impossible to
   dispatch without a durable intent". This wording choice belongs in the
   contribution statement at `PAPER_ROADMAP.md:32`, which currently overstates
   it.

6. **The roadmap's test-count figures need correcting.** `PAPER_ROADMAP.md:14`
   and `:154` both say 218; the verified numbers are 611 (pre-1B) and 674
   (post-1B). I did not edit the roadmap because it is outside the declared
   Phase 1B scope (`:55`).

7. **Is `tests/aof_rewind_probe.py` worth extending into a rate measurement?**
   (F2.) It would need a sustained write load to sit inside the `everysec`
   window. That is arguably Phase 2B harness work.

---

## H. Recommended next phase and its prerequisites

**Recommended next phase: 2A — "Make the artifact evaluation-grade"**
(`PAPER_ROADMAP.md:72-93`).

Rationale: Phase 1B removed the correctness blockers and, for the first time,
produced a reproducible environment and a verified test count. Phase 2A turns
that from "worked on this machine today" into "cannot lie in CI", which is the
precondition for every number Phase 2B will produce.

**Prerequisites, all now satisfied or newly known:**

1. **Python 3.13 toolchain** — satisfied (§C.0); the exact versions to pin into
   Phase 2A's lockfile are in §C.6.
2. **Redis 7.2 with AOF via Docker** — satisfied and digest-pinned
   (`compose.phase2.yml:5`).
3. **A true baseline test count** — 674 passed, 0 skipped, exit 0 (§C.6).
   Phase 2A's skip-count gate should treat any skip as a failure; note that
   4 tests skip unless `AEP_PHASE2_REDIS_INTEGRATION=1` is set
   (`tests/test_phase2_waitaof_integration.py:24-32`), so CI must set it.
4. **A decision on G.1** before Phase 2B, since the CI matrix should exercise
   whichever composition the evaluation will measure.

**Specific Phase 2A carry-overs identified by this phase:**

- `pytest-cov` is not installed; no coverage number exists for the new code
  (F11).
- The `fakeredis` fallback path is untested against the new Lua scripts (F12);
  Phase 2A's CI should either exercise it or the fallback should be removed.
- `tests/conftest.py` already uses namespaced `SCAN`-based cleanup rather than
  `FLUSHALL` (`tests/conftest.py:129-139`), so Phase 2A task 3 is largely
  already done — it needs verification, not a rewrite.

**Explicitly deferred to 2B:** separate-process `SIGKILL`, `docker
pause`/`restart`, toxiproxy partitions, the mock legacy API with a ground-truth
ledger, and an EVALUATION-mode connector — i.e. the work that would turn R1-3's
frequency, R2-1, and R2-3 from reasoned or simulated claims into measurements.
