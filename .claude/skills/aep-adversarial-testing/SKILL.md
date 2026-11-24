---
name: aep-adversarial-testing
description: How to author and execute the AEP adversarial test suite (pytest-asyncio) covering CAS, get/migration, locks, concurrency races, and lease cap.
---

# AEP adversarial test suite

The AEP build must be validated by an **adversarial** test suite — tests that try to break the invariants, not just confirm the happy path. Use `pytest-asyncio` and a real Redis instance (Docker) for any test that exercises the CAS Lua, because `fakeredis` may lack `cjson`.

## Authoring rules

- Tests must never be edited to force a pass. If a test reveals a real bug, fix the code.
- Every scenario in the matrix below must have at least one corresponding test.
- Failures must produce actionable output (the offending key, the version seen vs. expected, the raw bytes for corruption tests).
- Concurrency tests must use `asyncio.gather` against a real Redis; sleeping is not a substitute for a true race.

## Scenario matrix (minimum required)

| id   | area               | scenario                                                                                       | expected result                                  |
|------|--------------------|------------------------------------------------------------------------------------------------|--------------------------------------------------|
| C-01 | CAS write          | first write to a fresh key                                                                     | succeeds; version stored                         |
| C-02 | CAS write          | strictly increasing versions written in order                                                  | all succeed                                      |
| C-03 | CAS write          | write with equal or lower version                                                              | `StaleWriteError`; stored value unchanged        |
| C-04 | CAS write          | stored payload corrupt (non-JSON) at write time                                                | `StateCorruptionError`; no overwrite             |
| G-01 | get / migration    | missing key                                                                                    | returns `None`                                   |
| G-02 | get / migration    | valid JSON, valid schema_version → round-trip                                                  | parsed model returned                            |
| G-03 | get / migration    | non-JSON bytes stored                                                                          | quarantined; `StateCorruptionError`              |
| G-04 | get / migration    | JSON that fails schema validation                                                              | quarantined; `StateCorruptionError`              |
| G-05 | get / migration    | unknown `schema_version` with no migrator                                                      | `StateCorruptionError`                           |
| G-06 | get / migration    | known older `schema_version` with registered migrator                                          | upgraded payload returned                        |
| G-07 | get / migration    | id field inside payload != requested key                                                       | `StorageOperationError`                          |
| L-01 | lock               | double-acquire of a held lock                                                                  | second acquire returns `None`                    |
| L-02 | lock               | release with correct token                                                                     | succeeds; key gone                               |
| L-03 | lock               | release with wrong token                                                                       | no-op; logged warning                            |
| L-04 | lock               | renew with correct token                                                                       | TTL extended                                     |
| L-05 | lock               | renew with wrong token                                                                         | no-op; caller treated as lock-less               |
| R-01 | race               | two workers race to acquire the same lock                                                      | exactly one wins                                 |
| R-02 | race               | worker A writes version N, lock expires, worker B advances to N+1, A attempts write at N      | A is fenced (`StaleWriteError`)                  |
| LE-01 | lease              | long-running task with auto-renew under TTL                                                   | lock stays held                                  |
| LE-02 | lease              | task runtime exceeds `max_total_lease` ceiling                                                | renewal stops; lock expires; caller fails closed |

## Execution rules

- Use a real Redis (Docker) for any test in areas **C**, **R**, **G-03/G-04** (cjson involvement), and **LE**.
- Run with `pytest -q --tb=short`; the runner reports the exact command and exit code.
- The runner must NOT modify tests to silence failures. The runner's job is honest reporting; the orchestrator decides next steps.
