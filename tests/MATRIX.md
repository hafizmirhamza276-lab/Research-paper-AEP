# AEP Adversarial Test Matrix

This document maps every required scenario from the AEP specification to a corresponding test function. Each row contains the scenario ID, area, scenario description, expected result, and the pytest function that verifies it.

## Test Coverage Summary

- **CAS write tests (C-01..C-04):** 4 scenarios in `test_cas_write.py`
- **Get/migration tests (G-01..G-07):** 7 scenarios in `test_get_migration.py`
- **Lock tests (L-01..L-05):** 5 scenarios in `test_locks.py`
- **Race/concurrency tests (R-01..R-02):** 2 scenarios in `test_races.py`
- **Lease cap tests (LE-01..LE-02):** 2 scenarios in `test_lease.py`

**Total: 20 required scenarios + additional adversarial coverage**

---

## Matrix

| ID  | Area              | Scenario                                                                   | Expected Result                                    | Test Function                                       |
|-----|-------------------|----------------------------------------------------------------------------|----------------------------------------------------|----------------------------------------------------|
| C-01 | CAS write         | First write to a fresh key                                                | Succeeds; version stored                           | `test_cas_write.TestCASFirstWrite.test_cas_first_write_no_key` |
| C-02 | CAS write         | Strictly increasing versions written in order                             | All succeed                                        | `test_cas_write.TestCASMonotonicIncrements.test_cas_strictly_increasing_versions` |
| C-03 | CAS write         | Write with equal or lower version                                        | `StaleWriteError`; stored value unchanged         | `test_cas_write.TestCASStaleWrite.test_cas_equal_version_rejected`, `test_cas_stale_write_rejected` |
| C-04 | CAS write         | Stored payload corrupt (non-JSON) at write time                           | `StateCorruptionError`; no overwrite              | `test_cas_write.TestCASCorruptPayload.test_cas_corrupt_at_write_no_overwrite` |
| G-01 | Get/migration     | Missing key                                                               | Returns `None`                                     | `test_get_migration.TestGetMissing.test_get_missing_key_returns_none` |
| G-02 | Get/migration     | Valid JSON, valid schema_version → round-trip                             | Parsed model returned                              | `test_get_migration.TestGetValidRoundTrip.test_get_valid_round_trip` |
| G-03 | Get/migration     | Non-JSON bytes stored                                                     | Quarantined; `StateCorruptionError`                | `test_get_migration.TestGetNonJSON.test_get_non_json_payload` |
| G-04 | Get/migration     | JSON that fails schema validation                                         | Quarantined; `StateCorruptionError`                | `test_get_migration.TestGetSchemaInvalid.test_get_schema_invalid_json` |
| G-05 | Get/migration     | Unknown `schema_version` with no migrator                                 | `StateCorruptionError`                             | `test_get_migration.TestGetUnknownSchema.test_get_unknown_schema_version_no_migrator` |
| G-06 | Get/migration     | Known older `schema_version` with registered migrator                    | Upgraded payload returned                          | `test_get_migration.TestGetKnownMigrator.test_get_schema_migrated_with_registered_migrator` |
| G-07 | Get/migration     | ID field inside payload != requested key                                  | `StorageOperationError`                            | `test_get_migration.TestGetKeyPayloadMismatch.test_get_key_payload_mismatch` |
| L-01 | Lock              | Double-acquire of a held lock                                             | Second acquire returns `None`                      | `test_locks.TestDoubleAcquire.test_lock_double_acquire_returns_none` |
| L-02 | Lock              | Release with correct token                                               | Succeeds; key gone                                 | `test_locks.TestReleaseCorrectToken.test_lock_release_correct_token_succeeds` |
| L-03 | Lock              | Release with wrong token                                                 | No-op; logged warning                              | `test_locks.TestReleaseWrongToken.test_lock_release_wrong_token_returns_false` |
| L-04 | Lock              | Renew with correct token                                                 | TTL extended                                       | `test_locks.TestRenewCorrectToken.test_lock_renew_correct_token_extends_ttl` |
| L-05 | Lock              | Renew with wrong token                                                   | No-op; caller treated as lock-less                 | `test_locks.TestRenewWrongToken.test_lock_renew_wrong_token_returns_false` |
| R-01 | Race              | Two workers race to acquire the same lock                                 | Exactly one wins                                   | `test_races.TestRaceLockAcquire.test_race_acquire_lock_one_wins` |
| R-02 | Race              | Worker A writes version N, lock expires, worker B advances to N+1, A attempts write at N | A is fenced (`StaleWriteError`)                    | `test_races.TestRaceStaleFence.test_race_stale_write_fenced` |
| LE-01 | Lease            | Long-running task with auto-renew under TTL                              | Lock stays held                                    | `test_lease.TestLeaseAutoRenewal.test_lease_auto_renew_stays_locked` |
| LE-02 | Lease            | Task runtime exceeds `max_total_lease` ceiling                            | Renewal stops; lock expires; caller fails closed  | `test_lease.TestLeaseHardCap.test_lease_hard_cap_stops_renewal` |

---

## Additional Adversarial Scenarios (Beyond Required 20)

| ID  | Area              | Scenario                                                                   | Expected Result                                    | Test Function                                       |
|-----|-------------------|----------------------------------------------------------------------------|----------------------------------------------------|----------------------------------------------------|
| C-03a | CAS write       | Write with lower version (stale)                                         | `StaleWriteError`; stored value unchanged         | `test_cas_write.TestCASStaleWrite.test_cas_lower_version_rejected` |
| C-04a | CAS write       | Stored payload valid JSON but missing version field                       | `StateCorruptionError`; no overwrite              | `test_cas_write.TestCASCorruptPayload.test_cas_corrupt_unversioned_payload` |
| C-04b | CAS write       | Stored payload valid JSON with non-numeric version field                  | `StateCorruptionError` or `StaleWriteError`        | `test_cas_write.TestCASCorruptPayload.test_cas_corrupted_json_field_in_table` |
| C-04c | CAS write       | Quarantine key written on corrupt at write                                | Quarantine key has reason and safe size/encoding metadata; raw omitted | `test_cas_write.TestCASCorruptPayload.test_cas_quarantine_called_on_corrupt` |
| G-04a | Get/migration   | Valid JSON with invalid status enum value                                | `StateCorruptionError`                             | `test_get_migration.TestGetSchemaInvalid.test_get_invalid_status_enum` |
| G-04b | Get/migration   | Valid JSON with invalid execution_id type (not string)                   | `StateCorruptionError`                             | `test_get_migration.TestGetSchemaInvalid.test_get_invalid_execution_id_type` |
| L-01a | Lock            | Tokens generated for different executions are unique                      | Each token is unique                               | `test_locks.TestDoubleAcquire.test_lock_tokens_are_unique` |
| L-03a | Lock            | Release with expired token (key deleted)                                 | Returns `False` and logs warning                   | `test_locks.TestReleaseWrongToken.test_lock_release_expired_token_returns_false` |
| L-04a | Lock            | Renew multiple times maintains lock                                      | All renewals succeed; key persists                 | `test_locks.TestRenewCorrectToken.test_lock_renew_multiple_times` |
| L-05a | Lock            | Renew with expired token (key deleted)                                   | Returns `False`                                    | `test_locks.TestRenewWrongToken.test_lock_renew_expired_token_returns_false` |
| R-01a | Race            | Three-way race for lock acquisition                                      | Exactly one gets token; two get None               | `test_races.TestRaceLockAcquire.test_race_acquire_lock_three_way` |
| R-02a | Race            | Two concurrent CAS writers without lock; one is fenced                   | Exactly one succeeds; other gets `StaleWriteError` | `test_races.TestRaceStaleFence.test_race_concurrent_writers_one_fenced` |
| LE-01a | Lease          | Lease unavailable when lock is held                                      | Yields `None`; no heartbeat started                | `test_lease.TestLeaseAutoRenewal.test_lease_yields_none_when_unavailable` |
| LE-01b | Lease          | Lease cleanup on exception during task                                   | Lock released despite exception                   | `test_lease.TestLeaseAutoRenewal.test_lease_cleanup_on_exception` |
| LE-02a | Lease          | Lease cap prevents zombie-lock renewal                                   | Lock expires after cap even with hung task        | `test_lease.TestLeaseHardCap.test_lease_cap_prevents_zombie_renewal` |
| LE-02b | Lease          | Very high cap allows indefinite renewal under normal operation            | Lock renewed as long as task runs                 | `test_lease.TestLeaseHardCap.test_lease_no_cap_allows_indefinite_renewal` |

---

## Test Execution

## P2-004/P2-010 Request-Binding Addendum

| ID | Area | Scenario | Expected Result | Test Module |
|---|---|---|---|---|
| RB-01 | Canonical request | Key order, type, Unicode, array ordering, unsupported values, and cross-process stability | Deterministic canonical bytes and semantic fingerprint; ambiguous values rejected | `test_request_canonicalization.py` |
| RB-02 | Protected commitments | Dedicated keyed, domain-separated commitments and missing-key behavior | Protected values absent from descriptors; missing/invalid key fails closed | `test_request_canonicalization.py` |
| RB-03 | Attempt binding | Every execution, intent, locator, profile, version, and deadline field | Any change alters or invalidates the attempt digest; transplant rejected | `test_request_canonicalization.py`, `test_request_binding_intents.py` |
| RV-01 | Request vault | Create/read, collision, overwrite, expiry, integrity, key version, concurrency, plaintext canary | Exact readback only; all altered or duplicate cases fail with typed errors | `test_request_vault.py` |
| RI-01 | Redis immutability | Creation, transition, legacy addition, locator replacement, transplant, and retention shortening | Atomic Lua rejection; exact bytes preserved; TTL changes only with elapsed time | `test_request_binding_intents.py` |
| VD-01 | Verified dispatch | Caller mutation, missing/expired/altered vault, altered Redis binding, profile mismatch, unsafe request, and connector exception | Verified immutable object only; precise zero/one provider and durability counters; no retry | `test_verified_dispatch.py` |
| SV-01 | Privacy boundary | Nested/case-varying protected values, URL user information/query, provider evidence, exceptions, logs, quarantine, fingerprints, and Redis | Typed allowlists reject or redact; protected canaries remain only in authorized vault plaintext | `test_request_canonicalization.py`, `test_verified_dispatch.py` |
| RB-04 | Canonical persisted binding | Every immutable field, context transplant, missing/null, array order, alternate numeric encoding, empty array/object, missing/additional/modified members, and explicit depth limit | One deterministic canonical UTF-8 representation; every Lua mutation/preflight rejects nonidentical bytes and preserves exact state/TTL | `test_canonical_request_binding_closure.py` |
| RI-02 | Legacy canonical migration boundary | Unbound legacy record inspection and attempted preflight/binding addition | Record remains readable; no silent binding acquisition or provider transport | `test_canonical_request_binding_closure.py`, `test_request_binding_intents.py` |
| VD-02 | Dispatch provenance | Direct construction, old token, object-new, copy, look-alike, subclass, stale/reused capability, context/profile/version/key/deadline/material replacement | Only successful verification issues a connector-consumable one-use process-local capability | `test_verified_dispatch_provenance.py` |
| EP-01 | Endpoint profile revalidation | Unknown/missing/additional/wrong-type/wrong-classification/wrong-version fields and recursive object/array violations | Persisted descriptor and commitment slots are revalidated against the exact selected profile before capability issuance | `test_endpoint_profile_revalidation.py` |
| VA-02 | Complete vault AAD | Every identity, schema/profile/material/key/version/deadline field is individually altered | Versioned canonical AAD authentication rejects every alteration before provider transport; exact readback/create-once remain | `test_vault_aad_closure.py`, `test_verified_dispatch.py` |
| SV-02 | Fresh privacy boundary | Runtime-generated nested/case-varied markers in safe models, request rejection, evidence, exceptions, and representations | No marker in prohibited representations/errors/causes; typed validation remains authoritative | `test_privacy_boundary_closure.py` |

The Redis-backed runs select dedicated DB 15 and delete only test-owned
`aep:*` keys. No test invokes `FLUSHALL`.

Run all tests with:

```bash
pytest tests/ -v
```

Run a specific area:

```bash
pytest tests/test_cas_write.py -v
pytest tests/test_get_migration.py -v
pytest tests/test_locks.py -v
pytest tests/test_races.py -v
pytest tests/test_lease.py -v
```

Run a specific test:

```bash
pytest tests/test_cas_write.py::TestCASFirstWrite::test_cas_first_write_no_key -v
```

## Notes

- All tests use `fakeredis[lua]` with `decode_responses=True` for consistency.
- The `conftest.py` provides fresh Redis clients and adapters per test.
- CAS tests (`C-*`) require `cjson` support in fakeredis; if unavailable, tests are skipped.
- Lease tests use short TTLs (1-3 seconds) to keep execution fast.
- Race tests use `asyncio.gather` for true concurrent execution.
- All tests check for expected log output (e.g., warnings on lock release failure).
