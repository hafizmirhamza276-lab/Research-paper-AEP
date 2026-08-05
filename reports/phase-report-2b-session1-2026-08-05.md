# Phase 2B Session 1 — MockLegacyAPI and the ground-truth ledger

**Date:** 2026-08-05
**Repository:** Research-paper-AEP @ `867910d`
**Roadmap section:** `PAPER_ROADMAP.md` §3.1(1), Session 1 prompt block
**Amendments applied:** B0–B5 as given in the session brief

---

## A. Phase attempted and roadmap section reference

Two things, in order.

**The entry gate (B0).** Resolve open question G1 of
`docs/23-ci-hardening-report.md` — "should the `test` job's deselection be
removed by giving CI a config-file Redis?" — by switching *both* Redis-dependent
CI jobs to compose-based provisioning and removing the by-name deselection,
then push and obtain an actual green GitHub Actions run. The brief was explicit
that the mock API must not be built on a workflow that has never run.

**The session proper.** `PAPER_ROADMAP.md` §3.1(1): build `experiments/mock_api/`
as a standalone FastAPI service implementing MockLegacyAPI, with a ground-truth
applied-mutation ledger in SQLite, configurable via YAML, plus a docker-compose
entry, with the ledger itself unit-tested. The amendments raise the bar on four
points: the response classes must come from the production contract (B1); the
ledger is the paper's oracle and gets the protocol's own rigor (B2); the fault
surface must be configurable and echoed into every run log (B3); and EVALUATION
mode must be shown to *work*, not merely to be admissible (B4).

Both parts were completed. Nothing is reported here as blocked.

---

## B. Files created/modified

### B0 — the entry gate

| File | Change |
|---|---|
| `.github/workflows/ci.yml` | `test` job: `services:` block removed, Redis started from `compose.phase2.yml`, `--deselect` removed, `verify_redis_semantics.py` now runs without `--apply`, post-suite AOF re-verification and teardown added. Header comment records why. `waitaof-durability` header rewritten: it no longer holds a test the main job cannot run. |
| `tests/test_artifact_reproducibility.py` | Replaced `test_the_deselected_restart_test_is_run_by_the_durability_job` with five gates: nothing is deselected anywhere; every Redis-dependent job provisions from compose; no job applies settings at runtime; the container name matches `compose.phase2.yml`; the restart test is collected by the full suite. |
| `pyproject.toml` | `pyyaml` added to the `dev` extra, so those gates parse `ci.yml` per job rather than by substring. |

### Session 1 — the service

| File | Lines | What it is |
|---|---:|---|
| `experiments/mock_api/fingerprint.py` | 264 | Definitions 1 and 2: the oracle's identity function and the payload digest. Written to be quoted verbatim in the paper. |
| `experiments/mock_api/ledger.py` | 564 | Definition 3 and the ground-truth ledger: one transaction per applied mutation, WAL + `synchronous=FULL`, duplicate classification, consistency invariant. |
| `experiments/mock_api/config.py` | 492 | The YAML fault surface, its validation, and the self-describing echo. |
| `experiments/mock_api/service.py` | 474 | The FastAPI app: mutation, read-back, config, health, oracle routes. |
| `experiments/mock_api/client.py` | 219 | The AEP-side connector. Declares `evaluation_endpoint = True`; ignorant of the oracle. |
| `experiments/mock_api/__main__.py` | 49 | `python -m experiments.mock_api`. |
| `experiments/mock_api/config.example.yaml` | 64 | Reference configuration, one endpoint per response class. |
| `experiments/mock_api/Dockerfile` | 30 | Image built from `uv.lock`. |
| `experiments/mock_api/compose.mock-api.yml` | 61 | The roadmap's compose entry. |
| `experiments/mock_api/README.md` | 112 | How to run it, and the two boundaries that make its numbers mean something. |

Tests (`experiments/mock_api/tests/`, 149 of the 164 new tests):

| File | Tests | Covers |
|---|---:|---|
| `test_fingerprint.py` | 28 | Definitions 1 and 2, including every near-miss the oracle must not merge. |
| `test_ledger.py` | 28 | Atomicity, WAL/`synchronous`, duplicate classification, the consistency invariant, input refusal. |
| `test_config.py` | 46 | All five fault dimensions, seeded sampling, inheritance, fail-closed parsing, the echo and its digest. |
| `test_service.py` | 35 | The contract-literal guard, the fault surface end-to-end, read-back per capability, the oracle routes, the run log, the privacy boundary. |
| `test_service_crash_safety.py` | 5 | SIGKILL on each side of the commit boundary; the real-socket client timeout. |
| `test_evaluation_dispatch.py` | 7 | B4: EVALUATION mode dispatching a real mutation to a real process. |
| `test_packaging.py` | 8 | Compose/Dockerfile cross-file agreement. |
| `server_harness.py` | — | Not collected: runs the service as a real OS process so it can really be killed. |
| `conftest.py` | — | Re-exports the guarded Redis fixtures from `tests/conftest.py`. |

Supporting changes: `pyproject.toml` (`experiments` extra; `testpaths` extended
to `experiments`), `.github/workflows/ci.yml` (`--extra experiments`,
`MINIMUM_TESTS` 1100 → 1350), `.gitignore` (experiment output),
`CHANGELOG.md`, `tests/test_artifact_reproducibility.py` (+1 gate: the
full-suite job installs every declared extra).

**`aep_core` is unchanged.** B5 permitted a change only if B1 exposed a genuine
contract gap. It did not: `ReconciliationCapability`, `PERMITTED_READBACK_RESULTS`
and `result_is_permitted` were sufficient to drive both the service's read-back
behaviour and the client's declaration. See §E for the one place where a
related vocabulary is *not* in the contract and why that is not this session's
gap to close.

---

## C. Raw command outputs

### C.0 Baseline, before anything was touched

```
$ REDIS_URL="redis://127.0.0.1:6381/15" AEP_PHASE2_REDIS_INTEGRATION=1 \
  AEP_PHASE2_REDIS_CONTAINER=aep-phase2-redis72 \
  uv run --frozen pytest -q -ra --strict-markers
........................................................................ [ 94%]
.......................................................................  [100%]
1223 passed in 29.61s
```

Matches the figure `docs/23-ci-hardening-report.md` reports.

### C.1 B0 — the new CI gates fail against the old workflow

Written before the workflow was changed:

```
$ uv run --frozen pytest -q -ra --strict-markers tests/test_artifact_reproducibility.py
...
E       AssertionError: job 'test' applies Redis settings at runtime instead of
        asserting that compose.phase2.yml already provides them
E       assert '--apply' not in '\n\nuv sync..._TESTS}"\n\n'
...
E       KeyError: 'AEP_PHASE2_REDIS_CONTAINER'
=========================== short test summary info ===========================
FAILED tests/test_artifact_reproducibility.py::test_the_workflow_deselects_nothing_anywhere
FAILED tests/test_artifact_reproducibility.py::test_every_redis_job_provisions_redis_from_compose[test]
FAILED tests/test_artifact_reproducibility.py::test_every_redis_job_verifies_semantics_without_applying_them[test]
FAILED tests/test_artifact_reproducibility.py::test_every_redis_job_names_the_container_the_restart_test_restarts[test]
4 failed, 30 passed in 0.81s
```

### C.2 B0 — and pass after it

```
$ uv run --frozen pytest -q -ra --strict-markers tests/test_artifact_reproducibility.py
..................................                                       [100%]
34 passed in 0.14s
```

### C.3 B0 — the semantics check CI now runs, without `--apply`

```
$ uv run --frozen python scripts/verify_redis_semantics.py --url "redis://127.0.0.1:6381/15"
  verified redis_version=7.2.5
  verified appendonly=yes
  verified appendfsync=everysec
  verified aof-use-rdb-preamble=yes
  verified aof_enabled=1
  verified waitaof=present
OK: live Redis matches phase2.conf semantics
EXIT=0
```

### C.4 B0 — the exact CI sequence, locally

```
$ pytest -q -ra --strict-markers --junitxml=junit-local.xml | tee pytest-local.txt
1230 passed in 33.90s
PYTEST_EXIT=0
$ python scripts/check_pytest_gates.py --junit junit-local.xml \
    --output pytest-local.txt --minimum-tests 1100
OK: 1230 tests, 0 skipped, 0 failed, 0 errors, 0 xpassed
GATE_EXIT=0
```

1223 → 1230: the five new CI gates, two of which are parametrised over both jobs.

### C.5 B0 — the actual GitHub Actions run

```
$ git push origin main
To https://github.com/hafizmirhamza276-lab/Research-paper-AEP.git
   91c8324..5f06ed1  main -> main
```

The remote had been six commits behind: Phases 1A, 1B and 2A had been committed
but never pushed, so **no CI run had ever existed for this repository**. F3 of
`docs/23-ci-hardening-report.md` was correct to call this the largest open risk
of that phase.

Run: **<https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/30998269749>**

```
id: 30998269749
name: CI
display_title: Phase 2B B0: compose-provisioned Redis in both CI jobs, no deselection
head_branch: main
head_sha: 5f06ed1552524dc48cc4367e23d10075529fe4c6
event: push
status: completed
conclusion: success
run_number: 1
run_attempt: 1
created_at: 2026-08-05T10:39:05Z
updated_at: 2026-08-05T10:39:53Z
```

Per-step, all three jobs:

```
WAITAOF durability (compose, phase2.conf) | completed | success
    5 Start Redis 7.2 from compose.phase2.yml -> completed success
    6 Verify redis/phase2.conf semantics -> completed success
    7 Run the WAITAOF integration suite -> completed success
    8 Gate -- zero skipped, zero xpassed -> completed success
    9 Confirm AOF survived the restart test -> completed success
Citation ranges (docs/22) | completed | success
    5 Validate docs/22-formal-model.md citations -> completed success
Suite (py3.13, Redis from compose) | completed | success
    5 Start Redis 7.2 from compose.phase2.yml -> completed success
    7 Verify redis/phase2.conf semantics -> completed success
    8 Run the suite -> completed success
    9 Gate -- zero skipped, zero xpassed, suite actually ran -> completed success
   10 Confirm AOF survived the restart test -> completed success
```

The gate step passing is the load-bearing line: it fails unless ≥ 1100 tests
ran with zero skips and zero xpasses. The restart test that used to be
deselected ran inside that count, on ubuntu-24.04, against compose-provisioned
Redis.

**Raw job logs are not included** because the `/actions/runs/{id}/logs`
endpoint returns HTTP 403 without an authenticated token, and no token is
available in this environment. What is above is the API's own structured
result for every job and step; I did not have access to the log text and have
not paraphrased it as if I had.

### C.6 Definitions 1 and 2 — red, then green

```
$ pytest -q experiments/mock_api/tests/test_fingerprint.py
E   ModuleNotFoundError: No module named 'experiments.mock_api.fingerprint'
1 error in 0.31s
```

```
$ pytest -q -ra --strict-markers experiments/mock_api/tests/test_fingerprint.py
............................                                             [100%]
28 passed in 0.05s
```

### C.7 The ledger — red, then green

```
$ pytest -q experiments/mock_api/tests/test_ledger.py
E   ModuleNotFoundError: No module named 'experiments.mock_api.ledger'
1 error in 0.26s
```

```
$ pytest -q -ra --strict-markers experiments/mock_api/tests/test_ledger.py
............................                                             [100%]
28 passed in 0.48s
```

### C.8 The fault surface — red, then green

```
$ pytest -q experiments/mock_api/tests/test_config.py
E   ModuleNotFoundError: No module named 'experiments.mock_api.config'
1 error in 0.24s
```

```
$ pytest -q -ra --strict-markers experiments/mock_api/tests/test_config.py
..............................................                           [100%]
46 passed in 1.10s
```

### C.9 The service — red, then green

```
$ pytest -q experiments/mock_api/tests/test_service.py
ERROR experiments/mock_api/tests/test_service.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 warning, 1 error in 3.99s
```

First implementation run — one genuine failure, not a collection error:

```
_____ test_a_certain_timeout_applies_the_mutation_and_loses_the_response ______
>               with pytest.raises(Exception):
E               Failed: DID NOT RAISE Exception
1 failed, 34 passed, 2 warnings in 33.35s
```

`TestClient` drives the app in-process and cannot honour a client-side timeout
(Starlette says so in a warning). The test was asserting something the harness
cannot observe. It was split: the in-process test now asserts the *server* half
(applied, response withheld for the full hold, and what finally arrives is a
504), and the client half — a real socket raising `ReadTimeout` — moved to the
real-server file. The 33s runtime was the test sleeping through the full
`TIMEOUT_HOLD_SECONDS`; it is now 2.6s.

```
$ pytest -q -ra --strict-markers experiments/mock_api/tests/test_service.py
...................................                                      [100%]
35 passed, 1 warning in 2.62s
```

### C.10 B2(iii) — SIGKILL mid-mutation

```
$ pytest -q -ra --strict-markers experiments/mock_api/tests/test_service_crash_safety.py \
    experiments/mock_api/tests/test_service.py
........................................                                 [100%]
40 passed, 1 warning in 11.82s
```

The first run of these five passed too, but the after-commit test was racy: the
service wrote its progress marker on *both* sides of the commit, so a waiting
test could observe "in transaction" microseconds before the commit and kill
just after it. The marker is now written only by the hold that is actually
armed, and the test asserts its content (`after-commit`) before killing. A
crash test whose own setup is ambiguous about where the crash landed is not
evidence.

### C.11 B4 — EVALUATION mode, end to end

```
$ REDIS_URL="redis://127.0.0.1:6381/15" AEP_PHASE2_REDIS_INTEGRATION=1 \
  pytest -q -ra --strict-markers experiments/mock_api/tests/test_evaluation_dispatch.py
.......                                                                  [100%]
7 passed in 20.21s
```

### C.12 The new gates have teeth — three controlled mutations, each reverted

These modules were implemented before their tests in three cases (see §F1), so
red-phase evidence was produced by breaking the property under test rather than
by the module not existing.

**B1 — reintroduce a capability string literal in `service.py`:**

```
E       AssertionError: capability names appear as string literals in the
        service source: ['service.py:AUTHORITATIVE_READBACK'].
        Import ReconciliationCapability instead.
FAILED experiments/mock_api/tests/test_service.py::test_the_service_source_never_writes_a_capability_name_as_a_literal
1 failed, 1 warning in 0.40s
--- reverted ---
1 passed, 1 warning in 0.27s
```

**B2(i) — split the write path into two transactions, so the state change can
commit without its ledger row:**

```
>       assert ledger.applied_mutations() == ()
E       AssertionError: assert (AppliedMutat...ect-call-1'),) == ()
E         Left contains one more item: AppliedMutation(id=1, call_id='call-1', ...)
FAILED experiments/mock_api/tests/test_ledger.py::test_a_crash_before_commit_persists_neither_side
1 failed, 27 passed in 0.51s
--- reverted ---
28 passed in 0.47s
```

**B4 — point the connector at a closed port, so no HTTP round trip happens:**

```
>       assert resolved.status is IntentStatus.FIRED_CONFIRMED
E       AssertionError: assert <IntentStatus.FIRED_UNCONFIRMED: 'FIRED_UNCONFIRMED'>
                       is <IntentStatus.FIRED_CONFIRMED: 'FIRED_CONFIRMED'>
FAILED .../test_evaluation_dispatch.py::test_evaluation_mode_dispatches_a_real_mutation_to_the_mock_api
1 failed in 4.45s
--- reverted ---
7 passed in 21.03s
```

The third is the important one: it shows the EVALUATION test's green depends on
a real socket reaching a real process whose ledger really recorded the effect,
and that the protocol correctly classifies the broken case as
`FIRED_UNCONFIRMED` rather than failing loudly.

### C.13 The compose entry, built and exercised

```
$ docker compose -f experiments/mock_api/compose.mock-api.yml up --build -d
 Image aep-mock-legacy-api-mock-legacy-api Built
 Container aep-mock-legacy-api Started
BUILD_EXIT=0

$ docker compose -f experiments/mock_api/compose.mock-api.yml ps
NAME                  STATUS                    PORTS
aep-mock-legacy-api   Up 14 seconds (healthy)   127.0.0.1:8099->8099/tcp

$ curl -s localhost:8099/v1/health
{"status":"ok","config_digest":"94cf018dc6f8bd1e2f68372bf72ca4e2494a54bf265a835d90d610f699f9cc22"}

$ curl -s localhost:8099/v1/config
{
  "config_version": "aep.mock-legacy-api.config/1",
  "seed": 20260805,
  "ledger_path": "experiments/results/mock_api/ground_truth.sqlite3",
  "source_path": "/app/config/mock-api.yaml",
  "config_digest": "94cf018dc6f8bd1e2f68372bf72ca4e2494a54bf265a835d90d610f699f9cc22"
}
endpoints: {'ledger_postings': 'NO_READBACK',
            'notifications': 'POSITIVE_ONLY_READBACK',
            'payments': 'AUTHORITATIVE_READBACK'}
```

Two mutations with identical content but *different* client references, then
read-back and the oracle:

```
$ curl -X POST .../v1/endpoints/payments/mutations -H "X-AEP-Client-Reference: demo-ref-1" ...
{"call_id":"mock-call-0ce8cd73-...","outcome":"APPLIED","external_reference":"mock-effect-mock-call-0ce8cd73-..."}
$ curl -X POST .../v1/endpoints/payments/mutations -H "X-AEP-Client-Reference: demo-ref-2" ...
{"call_id":"mock-call-c7d755fe-...","outcome":"APPLIED","external_reference":"mock-effect-mock-call-c7d755fe-..."}

$ curl "localhost:8099/v1/endpoints/payments/readback?client_reference=demo-ref-1"
{"result":"APPLIED","response_class":"AUTHORITATIVE_READBACK"}

$ curl -o /dev/null -w "%{http_code}" "localhost:8099/v1/endpoints/ledger_postings/readback?..."
409

$ curl localhost:8099/v1/oracle/duplicates
{
    "config_digest": "94cf018dc6f8bd1e2f68372bf72ca4e2494a54bf265a835d90d610f699f9cc22",
    "duplicate_application_count": 1,
    "groups": [
        {
            "fingerprint": "02ab7f87974ffc6abf449957151f76f05cbdf5b47051b338393ca8492780cb15",
            "endpoint": "payments",
            "duplicate_class": "EXACT_DUPLICATE",
            "applications": 2,
            "duplicate_applications": 1,
            "distinct_payloads": 1,
            "call_ids": ["mock-call-0ce8cd73-...", "mock-call-c7d755fe-..."]
        }
    ]
}

$ curl localhost:8099/v1/oracle/consistency
{"config_digest":"94cf...","is_consistent":true,"applied_rows":2,"total_effect_count":2,
 "disagreeing_resources":[]}
```

Two different client references, one duplicate group: the oracle's independence
from the caller's own notion of request identity, demonstrated rather than
asserted. `NO_READBACK` refuses with 409.

### C.14 Full suite, and the CI gate

```
$ REDIS_URL="redis://127.0.0.1:6381/15" AEP_PHASE2_REDIS_INTEGRATION=1 \
  AEP_PHASE2_REDIS_CONTAINER=aep-phase2-redis72 \
  uv run --frozen pytest -q -ra --strict-markers --junitxml=junit-local.xml \
    --cov=aep_core --cov-fail-under=90
...
aep_core\core\connector_contract.py      72      1    99%
aep_core\core\intent_recovery.py        237     31    87%
aep_core\core\intent_workflow.py        258     42    84%
aep_core\core\intents.py                383     47    88%
aep_core\core\locks.py                  110      4    96%
aep_core\core\request_binding.py        788     78    90%
aep_core\core\request_vault.py          251     22    91%
aep_core\core\state_codec.py             61      3    95%
aep_core\core\storage.py                181     15    92%
-------------------------------------------------------------------
TOTAL                                  2518    244    90%
Required test coverage of 90% reached. Total coverage: 90.31%
1387 passed, 2 warnings in 78.82s (0:01:18)

$ uv run --frozen python scripts/check_pytest_gates.py \
    --junit junit-local.xml --output pytest-local.txt --minimum-tests 1350
OK: 1387 tests, 0 skipped, 0 failed, 0 errors, 0 xpassed
GATE_EXIT=0
```

1223 → 1387. Coverage on `aep_core` is unchanged at 90.31%, which is the
expected result: no `aep_core` logic was touched, and `--cov` is scoped to
`aep_core`, so the 164 new tests neither raise nor dilute it.

### C.15 The Actions run for the session's work

```
$ git push origin main
   5f06ed1..867910d  main -> main
```

Run: **<https://github.com/hafizmirhamza276-lab/Research-paper-AEP/actions/runs/31000865024>**

```
31000865024  867910d8  completed  success  2026-08-05T11:17:29Z -> 2026-08-05T11:18:36Z
```

```
Suite (py3.13, Redis from compose) | success | 11:17:32Z -> 11:18:35Z
     4 Sync locked environment -> success
     5 Start Redis 7.2 from compose.phase2.yml -> success
     7 Verify redis/phase2.conf semantics -> success
     8 Run the suite -> success
     9 Gate -- zero skipped, zero xpassed, suite actually ran -> success
    10 Confirm AOF survived the restart test -> success
WAITAOF durability (compose, phase2.conf) | success | 11:17:32Z -> 11:17:51Z
     7 Run the WAITAOF integration suite -> success
     8 Gate -- zero skipped, zero xpassed -> success
Citation ranges (docs/22) | success | 11:17:39Z -> 11:17:51Z
     5 Validate docs/22-formal-model.md citations -> success
```

The gate step ran with `MINIMUM_TESTS=1350`, so this is independent
confirmation on Linux that the suite really collected the new tests. Note this
also retires F10 of `phase-report-1b` ("the suite is verified on one platform"):
every run before today was Windows.

---

## D. Requirement checklist

| # | Requirement | Status | Evidence |
|---|---|---|---|
| B0 | Both CI jobs compose-provisioned | Done | §C.2, `ci.yml` |
| B0 | By-name deselection removed | Done | §C.1 red → §C.2 green; gate forbids its return |
| B0 | Actual green Actions run | Done | §C.5, run 30998269749; §C.15, run 31000865024 |
| B1 | Three response classes via the production contract | Done | `config.py` parses into `ReconciliationCapability`; §C.12 literal guard |
| B1 | No capability name string-compared anywhere | Done | `test_the_service_source_never_writes_a_capability_name_as_a_literal` |
| B2(i) | Mutation + fingerprint recorded atomically with the state change | Done | one `BEGIN IMMEDIATE … COMMIT`; §C.12 mutation |
| B2(ii) | Documented fingerprint definition, paper-ready | Done | Definition 1, `fingerprint.py` module docstring |
| B2(iii) | WAL + SIGKILL-mid-mutation recovery test | Done | §C.10; `test_service_crash_safety.py` (both sides of commit) |
| B2(iv) | Duplicate query: exact / conflict / near-miss | Done | Definition 3; `test_ledger.py`, 3 named tests + service-level equivalents |
| B3 | Delay, timeout, 5xx, duplicate, per-endpoint class, via YAML | Done | `config.py`, 46 tests |
| B3 | Loaded config echoed into every run's result log | Done | run log record 1 + `config_digest` on every subsequent record |
| B4 | One EVALUATION-mode integration test, real dispatch, ledger records it | Done | §C.11; §C.12 mutation proves it is end-to-end |
| B5 | New code under `experiments/mock_api/` + tests | Done | §B; `aep_core` unchanged |
| Roadmap | Standalone FastAPI service | Done | `service.py`, `__main__.py` |
| Roadmap | Ground-truth ledger in SQLite | Done | `ledger.py` |
| Roadmap | docker-compose entry | Done | §C.13, built and exercised |
| Roadmap | Unit-test the ledger itself | Done | 28 tests |
| Standing | Failing-then-passing for every new gate | Partial | §C.6–C.9 for three modules; §C.12 mutation evidence for the rest. See §F1. |
| Standing | Raw output in a dated report | Done | §C |

---

## E. Deviations from the roadmap

**E1. `duplicate_response_probability` is implemented as duplicated delivery of
the *request*.** The roadmap names the knob "duplicate-response probability".
A single HTTP exchange cannot deliver two responses to one request, so a
literal implementation would be unobservable. The implemented fault is the
provider handling the same request twice before answering — an at-least-once
internal retry, which is a real and common legacy-system behaviour. The caller
receives one response; the ledger records two applications sharing one
fingerprint. This is an interpretation, flagged as one in `config.py`, in the
README, and here.

**E2. The 5xx and timeout faults were given complementary ground truths.** The
roadmap lists both as probabilities and says nothing about whether the mutation
was applied. That silence is load-bearing: if both faults applied the mutation,
every ambiguous outcome would resolve to "actually applied" and recovery would
never be tested against a negative. So `server_error_probability` refuses
*before* applying, and `timeout_probability` applies and then loses the
response. Together they give the evaluation both truths behind an ambiguous
outcome. The connector is not told which is which (§E3).

**E3. The connector treats 5xx as ambiguous, not as failure.** This service
implements its injected 5xx as a refusal before applying, but `client.py` maps
5xx to ambiguity anyway, because a real caller cannot know that. Only `4xx` is
read as definitive failure. Without this the connector would be reading the
oracle through the response code and every recovery measurement would be
contaminated.

**E4. The oracle does not reuse `aep_core`'s canonicaliser or fingerprint.**
`fingerprint.py` implements its own canonical JSON. Reusing
`request_binding.canonical_json_bytes` would have been less code, but an oracle
that inherits the canonicaliser of the protocol it measures inherits any
collision that canonicaliser has, and the paper's central claim is a count
produced by that oracle. AEP's own fingerprint is carried as an opaque client
reference for read-back and is never an input to duplicate detection —
demonstrated in §C.13, where two different references still produce one
duplicate group.

**E5. The fingerprint is a projection, not a whole-payload hash.** Definition 1
hashes the endpoint, method, operation, target and a configured set of
*identity fields*. Hashing the whole payload would make
`FINGERPRINT_CONFLICT` (B2(iv)'s "same-fingerprint-different-payload")
unreachable except by SHA-256 collision, and would also mean a caller changing
a free-text memo between retries produced a "different mutation". The
projection is per-endpoint configuration, so it is part of the run's recorded
description.

**E6. Tests live in `experiments/mock_api/tests/`, and `testpaths` was widened
to collect them.** The alternative — putting them in `tests/` — would have kept
one directory but split the harness from its tests. Widening `testpaths` means
one `pytest` invocation, so the zero-skip and zero-xpass gates apply to the
harness suite without a second gate configuration.

**E7. The compose entry is a separate file, not a service in
`compose.phase2.yml`.** Both CI jobs bring `compose.phase2.yml` up; folding an
image build into it would put a Python build on the critical path of every
suite run. The tests do not use the compose entry at all — a test that SIGKILLs
the API needs the process, not the container.

**E8. `pyyaml` was added to the `dev` extra during B0.** Needed so the CI gates
could parse `ci.yml` per job rather than by substring. Small, pure-Python, and
required by the service later regardless.

---

## F. Known weaknesses, shortcuts, and what a hostile reviewer would attack

**F1. Three modules were implemented before their tests.** `service.py` (in
part), `client.py`, `Dockerfile`/`compose.mock-api.yml` and `test_packaging.py`
were written implementation-first, so §C.6–C.9's clean red phase does not cover
them. I compensated with the three controlled mutations in §C.12 — which are
arguably stronger evidence than a `ModuleNotFoundError`, since they show the
tests detect the specific property being claimed rather than merely the
module's existence — but the discipline was not uniform and I am not going to
present it as if it were. `test_packaging.py` in particular has no red-phase
evidence of any kind; it is a cross-file agreement check written after the
files it checks.

**F2. The crash tests kill the service, not the database.** SIGKILL of the
process proves the *application* cannot leave a half-applied mutation. It does
not prove behaviour under host power loss or a full disk. `synchronous=FULL`
makes the durability claim unconditional in principle, but no test injects a
storage fault, and none can without hardware or a fault-injecting filesystem.

**F3. On Windows the "SIGKILL" is `TerminateProcess`.** Every local run in this
report is Windows 11 with a Linux Docker backend. `server_harness.HAS_SIGKILL`
is False there and `Popen.kill()` is used, which is equally uncatchable but is
not the same system call. The CI run in §C.15 executed these tests on
ubuntu-24.04 with the real `SIGKILL`, so the artifact's claim rests on the
Linux path — but the two paths have not been compared, only both observed to
pass.

**F4. B4 is one dispatch on the happy path.** The EVALUATION test dispatches a
successful mutation and asserts the ledger recorded it. That retires "proven
admissible, not proven functional" for the composition, which is exactly what
the amendment asked for at the smallest scope. It does **not** show EVALUATION
mode surviving a crash, a partition, or an ambiguous response. The 22
crash-boundary runner tests still run in TEST mode with `allow_test_dispatch`.
A reviewer reading "EVALUATION mode works" as "the crash matrix now runs in
EVALUATION mode" would be wrong, and the paper must not imply it.

**F5. The read-back path is keyed on the client reference, which is AEP's own
fingerprint.** This is realistic — legacy APIs do echo client references — but
it means read-back correctness depends on the caller supplying a stable
reference across attempts. A baseline that mints a fresh reference per attempt
(B0, naive retry) will read back `NOT_APPLIED` for a mutation that *was*
applied. That is arguably the correct model of a system with no idempotency
discipline, but it is a modelling decision inside the measurement apparatus and
it will affect B0's numbers. It needs to be stated in the paper's threats to
validity, and Session 2 should check whether a second, content-derived
read-back key is needed for a fair baseline comparison.

**F6. The duplicate-detection query is `GROUP BY fingerprint` over the whole
table.** Correct and indexed, but O(rows) per call, and the matrix will produce
30 repetitions × several systems × several crash points. It has not been run
at that scale. Nothing here is designed for a ledger with millions of rows.

**F7. `TIMEOUT_HOLD_SECONDS` is a module constant, not configuration.** 30
seconds, chosen so that any experimental client timeout expires first. It is
not in the config echo, so a run log does not record it. If a future experiment
uses a client timeout above 30s the fault will silently stop being a timeout
and start being a slow success. This should become a config key with a
validation rule tying it to the client timeout.

**F8. The service serialises all ledger writes behind one lock.** One SQLite
connection shared across worker threads, guarded by a `threading.Lock`, with
each write dispatched through `asyncio.to_thread`. Correct, and SQLite
serialises writes regardless — but it means the mock API's throughput is a
floor on the throughput of any overhead measurement made through it. The
roadmap's §3.2 asks for throughput vs. a no-protocol baseline; if the mock API
is the bottleneck, that comparison measures the mock API. Session 3 must check
this before reporting any throughput number.

**F9. No test asserts that the protocol never calls `/v1/oracle/*`.** The
separation is by convention and by the connector not containing the URL. A
guard — grep the connector for `oracle`, or have the service refuse oracle
requests carrying a client reference header — would make it a property. I did
not add one.

**F10. Coverage of `experiments/` is not measured.** `--cov=aep_core` is
unchanged, so the 164 new tests contribute nothing to the gate and the new
2,100 lines of harness code have no coverage floor at all. That is defensible
— the gate exists to protect the protocol — but "90.31% coverage" now describes
a smaller fraction of the repository than it did yesterday.

**F11. The coverage gate still sits on 9 statements of margin.** 90.31% against
a 90% floor. `docs/23-ci-hardening-report.md` H.3 asked for headroom in
`intent_workflow.py` and `intent_recovery.py` before 2B; that was not done, and
Session 2 adds code to both. It will start failing for reasons unrelated to the
change under test.

**F12. A Starlette deprecation warning is emitted on every run.**
`Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2'`.
Harmless today, and warnings are not gated, but it is a pin that will move.

**F13. The fingerprint's identity-field projection is only as good as the
configuration.** An endpoint configured with too narrow a projection will
report distinct mutations as duplicates. The service refuses an *empty*
projection and refuses a request missing a declared identity field, but it
cannot tell that `["action"]` is too narrow for an endpoint where the amount
matters. This is inherent to the design and must be stated: the oracle's
notion of identity is declared, not discovered.

---

## G. Open questions needing a human/architect decision

1. **Does the read-back key need to be content-derived for the baselines?**
   (F5.) Today read-back is keyed on the caller's own reference. B0 (naive
   retry) will not supply a stable one, so its read-backs will deny mutations
   that happened. If that is the intended model of a system with no idempotency
   discipline, nothing changes; if it would unfairly flatter B0's *known*
   ambiguity rate, the service needs a second read-back key computed from the
   request content. My recommendation: add the content-derived key in Session
   2, before the baselines exist, because retrofitting it after a matrix has
   run means re-running the matrix.

2. **Should `TIMEOUT_HOLD_SECONDS` become configuration with a validated
   relationship to the client timeout?** (F7.) It is a silent correctness
   dependency between the harness and the experiment configuration.

3. **Should the oracle boundary be enforced rather than observed?** (F9.) A
   test that fails if the connector can reach `/v1/oracle/*` would convert a
   convention into a property. Cheap; I left it out because it was not asked
   for.

4. **Is the mock API fast enough to measure AEP's overhead through?** (F8.)
   This needs a measurement, not an opinion, and it should happen before the
   matrix rather than after.

5. **Coverage: raise `aep_core` headroom, or extend the gate to
   `experiments/`?** (F10, F11.) These pull in opposite directions — extending
   the gate makes the margin problem worse. My recommendation: buy headroom in
   `aep_core` first (it is a prerequisite for Session 2 regardless), and give
   `experiments/` its own, lower floor rather than folding it into the same
   number.

---

## H. Recommended next phase and its prerequisites

**Next: Phase 2B Session 2 — the crash injector and workload driver**
(`PAPER_ROADMAP.md` §3.1(2–3)). Nothing in this session blocks it, and the two
pieces it depends on — a service that can be killed, and an oracle that
survives being killed — are now evidenced.

**Before starting Session 2, close these:**

1. **Buy coverage headroom in `intent_workflow.py` (84%) and
   `intent_recovery.py` (87%).** (F11.) Session 2 wires crash points into both.
   Nine statements of margin will not survive it, and a coverage failure
   unrelated to the change under test is exactly the kind of noise that gets a
   gate lowered.
2. **Decide question G1** — the read-back key — before the baselines are
   written against the current one.
3. **Measure the mock API's throughput ceiling** (G4) so §3.2's overhead
   numbers are known not to be measuring the harness.

**What Session 2 can rely on from this session:**

- A service it can `SIGKILL` at will, whose ledger is proven to agree with its
  simulated state on both sides of the commit boundary.
- A seeded, fully-declared fault surface, with the configuration and its digest
  in every run log — so a Session 2 `events.jsonl` can be joined to the API's
  behaviour by `config_digest` rather than by hope.
- A working EVALUATION composition: `experiments/mock_api/tests/test_evaluation_dispatch.py`
  `_evaluation_runner` is the composition the crash matrix should be ported to,
  and it needs no test flags.
- `server_harness.py`, which already starts the service as a subprocess on a
  free port and kills it uncatchably.

**One caution for Session 2.** The crash injector will want to SIGKILL AEP
*workers*, and those workers hold Redis leases. The test-instance-marker guard
in `tests/conftest.py` is what stops a mis-pointed `REDIS_URL` from deleting a
production keyspace; `docs/23-ci-hardening-report.md` already warned not to
weaken it for harness convenience, and that warning now applies to a second
process type. Set `aep:test-instance-marker` explicitly in harness setup.

---

*Every figure in this report is from raw output pasted above. Where evidence
was unavailable — the Actions job logs, which require an authenticated token —
that is stated rather than worked around. §F1 records where the
failing-then-passing discipline was not uniform.*
