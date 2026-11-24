# AEP Correctness Fixes Report

**Date:** 2026-07-27  
**Real test backend for every async run:** `Redis server v=3.0.504`, isolated at `redis://127.0.0.1:6380/15`, persistence disabled.  
**Scope changed:** only `src/core/`, `tests/`, and this report.

The recurring `pytest-asyncio` warning printed by these runs is reproduced after the final run. It is unrelated to the six fixes.

## 1. True expected-version CAS and lock ownership

Regression tests added:

- `tests/test_cas_write.py::TestExpectedVersionAndLockFencing::test_stale_writer_cannot_jump_version`
- `tests/test_cas_write.py::TestExpectedVersionAndLockFencing::test_save_requires_matching_live_lock_token`

Implementation: `save_state` now requires `expected_version` and `lock_token`. One Lua script atomically verifies the live lock token, verifies that the stored version equals `expected_version`, requires the incoming version to be exactly `expected_version + 1`, and performs the write. A missing, expired, or mismatched token raises `LockAcquisitionError`; an expected-version or successor mismatch raises `StaleWriteError`.

### Before — actual failing output

```text
FF                                                                       [100%]
================================== FAILURES ===================================
___ TestExpectedVersionAndLockFencing.test_stale_writer_cannot_jump_version ___
tests\test_cas_write.py:70: in test_stale_writer_cannot_jump_version
    with pytest.raises(StaleWriteError, match="expected version"):
E   Failed: DID NOT RAISE <class 'src.core.exceptions.StaleWriteError'>
_ TestExpectedVersionAndLockFencing.test_save_requires_matching_live_lock_token _
tests\test_cas_write.py:94: in test_save_requires_matching_live_lock_token
    with pytest.raises(LockAcquisitionError, match="lock"):
E   Failed: DID NOT RAISE <class 'src.core.exceptions.LockAcquisitionError'>
=========================== short test summary info ===========================
FAILED tests/test_cas_write.py::TestExpectedVersionAndLockFencing::test_stale_writer_cannot_jump_version
FAILED tests/test_cas_write.py::TestExpectedVersionAndLockFencing::test_save_requires_matching_live_lock_token
2 failed in 0.45s
EXIT_CODE=1
```

### After — actual passing output

```text
..                                                                       [100%]
2 passed in 0.10s
EXIT_CODE=0
```

### Full suite after Fix 1 — actual output

```text
......................................                                   [100%]
38 passed in 12.24s
EXIT_CODE=0
```

## 2. Lease loss cancels protected work

Regression tests added:

- `tests/test_lease.py::TestLeaseLossCancellation::test_hard_cap_cancels_owner_before_rival_can_overlap`
- `tests/test_lease.py::TestLeaseLossCancellation::test_failed_renewal_cancels_protected_task`

Implementation: `lease` records the task running the protected context. A hard-cap hit, a `False` renewal, or a renewal exception calls `owner_task.cancel(...)`. The protected task receives `asyncio.CancelledError`; context cleanup then releases the token-checked lock. The rival-worker test confirms acquisition occurs only after the original worker's active flag is cleared.

### Before — actual failing output

```text
FF                                                                       [100%]
================================== FAILURES ===================================
_ TestLeaseLossCancellation.test_hard_cap_cancels_owner_before_rival_can_overlap _
tests\test_lease.py:201: in test_hard_cap_cancels_owner_before_rival_can_overlap
    assert isinstance(owner_result, asyncio.CancelledError)
E   AssertionError: assert False
E    +  where False = isinstance('continued-after-cap', <class 'asyncio.exceptions.CancelledError'>)
E    +    where <class 'asyncio.exceptions.CancelledError'> = asyncio.CancelledError
------------------------------ Captured log call ------------------------------
WARNING  aep.locks:locks.py:295 AEP lease hard cap (0.4s) hit for execution_id=b4ec5e1d-2c53-4588-aa66-5f9bd79588db; stopping renewal. Lock will expire (fail-closed per Fail-Closed Invariant).
WARNING  aep.locks:locks.py:181 AEP lock release returned 0 for execution_id=b4ec5e1d-2c53-4588-aa66-5f9bd79588db: lease expired or re-acquired by another worker. Possible overlap occurred. Review logs for concurrent activity.
____ TestLeaseLossCancellation.test_failed_renewal_cancels_protected_task _____
tests\test_lease.py:226: in test_failed_renewal_cancels_protected_task
    assert isinstance(result, asyncio.CancelledError)
E   AssertionError: assert False
E    +  where False = isinstance('continued-after-renewal-loss', <class 'asyncio.exceptions.CancelledError'>)
E    +    where <class 'asyncio.exceptions.CancelledError'> = asyncio.CancelledError
------------------------------ Captured log call ------------------------------
WARNING  aep.locks:locks.py:309 AEP lease renewal returned False for execution_id=10571bc2-11b3-4cfe-87da-0c7102ab9071; lock no longer owned. Stopping heartbeat. Worker should cease work.
WARNING  aep.locks:locks.py:181 AEP lock release returned 0 for execution_id=10571bc2-11b3-4cfe-87da-0c7102ab9071: lease expired or re-acquired by another worker. Possible overlap occurred. Review logs for concurrent activity.
=========================== short test summary info ===========================
FAILED tests/test_lease.py::TestLeaseLossCancellation::test_hard_cap_cancels_owner_before_rival_can_overlap
FAILED tests/test_lease.py::TestLeaseLossCancellation::test_failed_renewal_cancels_protected_task
2 failed in 3.04s
EXIT_CODE=1
```

### After — actual passing output

```text
..                                                                       [100%]
2 passed in 1.21s
EXIT_CODE=0
```

### Full suite after Fix 2 — actual output

```text
........................................                                 [100%]
40 passed in 12.84s
EXIT_CODE=0
```

## 3. Executable timeout invariant

Regression tests added:

- `tests/test_lease.py::TestTimeoutInvariantEnforcement::test_lease_cancels_block_at_configured_client_deadline`
- `tests/test_lease.py::TestTimeoutInvariantEnforcement::test_lease_rejects_invalid_timeout_invariant`

Implementation choice: enforce the entire protected block's duration. `lease` now accepts `client_deadline_seconds` and `buffer_margin_seconds`. It rejects buffers below 15 seconds and rejects deadlines that do not satisfy `T_client <= T_lock - Buffer`. A watchdog cancels the protected task when its configured deadline expires.

### Before — actual failing output

```text
FF                                                                       [100%]
================================== FAILURES ===================================
_ TestTimeoutInvariantEnforcement.test_lease_cancels_block_at_configured_client_deadline _
tests\test_lease.py:64: in test_lease_cancels_block_at_configured_client_deadline
    assert isinstance(result, asyncio.CancelledError)
E   AssertionError: assert False
E    +  where False = isinstance('continued-after-client-deadline', <class 'asyncio.exceptions.CancelledError'>)
E    +    where <class 'asyncio.exceptions.CancelledError'> = asyncio.CancelledError
_ TestTimeoutInvariantEnforcement.test_lease_rejects_invalid_timeout_invariant _
tests\test_lease.py:70: in test_lease_rejects_invalid_timeout_invariant
    with pytest.raises(LockAcquisitionError, match="Buffer|buffer"):
E   Failed: DID NOT RAISE <class 'src.core.exceptions.LockAcquisitionError'>
=========================== short test summary info ===========================
FAILED tests/test_lease.py::TestTimeoutInvariantEnforcement::test_lease_cancels_block_at_configured_client_deadline
FAILED tests/test_lease.py::TestTimeoutInvariantEnforcement::test_lease_rejects_invalid_timeout_invariant
2 failed in 1.00s
EXIT_CODE=1
```

### After — actual passing output

```text
..                                                                       [100%]
2 passed in 0.32s
EXIT_CODE=0
```

### Full suite after Fix 3 — actual output

```text
..........................................                               [100%]
42 passed in 12.54s
EXIT_CODE=0
```

## 4. Strict canonical UUIDv4 validation

Regression tests added in `tests/test_uuid_validation.py`:

- `test_state_model_rejects_non_v4_or_noncanonical_uuid` (three parameter cases)
- `test_get_state_rejects_invalid_execution_id`
- `test_save_state_revalidates_mutated_execution_id`
- `test_all_lock_entry_points_reject_invalid_execution_id`

Implementation: `src/core/validation.py::validate_execution_id` parses without coercing the version, explicitly requires `parsed.version == 4`, and requires exact equality with `str(parsed)` so only canonical lowercase hyphenated UUIDv4 strings pass. The model validator, `save_state`, `get_state`, `acquire_lock`, `release_lock`, `renew_lock`, and `lease` all call it. Storage boundaries raise `StorageOperationError`; lock boundaries raise `LockAcquisitionError`.

### Before — actual failing output

```text
FFFFFF                                                                   [100%]
================================== FAILURES ===================================
_ test_state_model_rejects_non_v4_or_noncanonical_uuid[9a7aca92-89ec-11f1-b825-74d83e331296] _
tests\test_uuid_validation.py:21: in test_state_model_rejects_non_v4_or_noncanonical_uuid
    with pytest.raises(ValidationError, match="canonical UUIDv4"):
E   Failed: DID NOT RAISE <class 'pydantic_core._pydantic_core.ValidationError'>
_ test_state_model_rejects_non_v4_or_noncanonical_uuid[A16E100A-7FAE-451A-95EB-0C19ECD4615F] _
tests\test_uuid_validation.py:21: in test_state_model_rejects_non_v4_or_noncanonical_uuid
    with pytest.raises(ValidationError, match="canonical UUIDv4"):
E   Failed: DID NOT RAISE <class 'pydantic_core._pydantic_core.ValidationError'>
_ test_state_model_rejects_non_v4_or_noncanonical_uuid[ee590037ed4843f6b65bcb5adad97a8f] _
tests\test_uuid_validation.py:21: in test_state_model_rejects_non_v4_or_noncanonical_uuid
    with pytest.raises(ValidationError, match="canonical UUIDv4"):
E   Failed: DID NOT RAISE <class 'pydantic_core._pydantic_core.ValidationError'>
_________________ test_get_state_rejects_invalid_execution_id _________________
tests\test_uuid_validation.py:27: in test_get_state_rejects_invalid_execution_id
    with pytest.raises(StorageOperationError, match="canonical UUIDv4"):
E   Failed: DID NOT RAISE <class 'src.core.exceptions.StorageOperationError'>
______________ test_save_state_revalidates_mutated_execution_id _______________
tests\test_uuid_validation.py:42: in test_save_state_revalidates_mutated_execution_id
    with pytest.raises(StorageOperationError, match="canonical UUIDv4"):
E   Failed: DID NOT RAISE <class 'src.core.exceptions.StorageOperationError'>
___________ test_all_lock_entry_points_reject_invalid_execution_id ____________
tests\test_uuid_validation.py:55: in test_all_lock_entry_points_reject_invalid_execution_id
    with pytest.raises(LockAcquisitionError, match="canonical UUIDv4"):
E   Failed: DID NOT RAISE <class 'src.core.exceptions.LockAcquisitionError'>
=========================== short test summary info ===========================
FAILED tests/test_uuid_validation.py::test_state_model_rejects_non_v4_or_noncanonical_uuid[9a7aca92-89ec-11f1-b825-74d83e331296]
FAILED tests/test_uuid_validation.py::test_state_model_rejects_non_v4_or_noncanonical_uuid[A16E100A-7FAE-451A-95EB-0C19ECD4615F]
FAILED tests/test_uuid_validation.py::test_state_model_rejects_non_v4_or_noncanonical_uuid[ee590037ed4843f6b65bcb5adad97a8f]
FAILED tests/test_uuid_validation.py::test_get_state_rejects_invalid_execution_id
FAILED tests/test_uuid_validation.py::test_save_state_revalidates_mutated_execution_id
FAILED tests/test_uuid_validation.py::test_all_lock_entry_points_reject_invalid_execution_id
6 failed in 0.28s
EXIT_CODE=1
```

### After — actual passing output

```text
......                                                                   [100%]
6 passed in 0.10s
EXIT_CODE=0
```

### Full suite after Fix 4 — actual output

```text
................................................                         [100%]
48 passed in 12.62s
EXIT_CODE=0
```

## 5. Schema-version guard on write

Regression test added:

- `tests/test_cas_write.py::TestSchemaVersionWriteGuard::test_save_rejects_unsupported_schema_version_before_write`

Implementation choice: only `CURRENT_SCHEMA_VERSION` may be written. Registered older versions remain a read/migration concern; a new write cannot label current state as an old or unknown version. Rejection occurs before Redis I/O and raises `StorageOperationError`.

### Before — actual failing output

```text
F                                                                        [100%]
================================== FAILURES ===================================
_ TestSchemaVersionWriteGuard.test_save_rejects_unsupported_schema_version_before_write _
tests\test_cas_write.py:121: in test_save_rejects_unsupported_schema_version_before_write
    with pytest.raises(StorageOperationError, match="schema_version"):
E   Failed: DID NOT RAISE <class 'src.core.exceptions.StorageOperationError'>
=========================== short test summary info ===========================
FAILED tests/test_cas_write.py::TestSchemaVersionWriteGuard::test_save_rejects_unsupported_schema_version_before_write
1 failed in 0.39s
EXIT_CODE=1
```

### After — actual passing output

```text
.                                                                        [100%]
1 passed in 0.05s
EXIT_CODE=0
```

### Full suite after Fix 5 — actual output

```text
.................................................                        [100%]
49 passed in 12.64s
EXIT_CODE=0
```

## 6. Redis Lua safe version range

Regression tests added in `tests/test_version_range.py`:

- `test_state_model_rejects_version_above_lua_safe_integer`
- `test_save_rejects_increment_beyond_lua_safe_integer`

Implementation choice: enforce a maximum version of `2^53 - 1` (`9007199254740991`). Redis Lua represents numbers as IEEE-754 doubles, and every integer through that value is exact. `AEPExecutionState` uses a strict bounded integer field; `save_state` revalidates mutated models and expected versions; Lua independently rejects out-of-range/fractional incoming values and treats an out-of-range stored version as corruption. The maximum version is terminal because it cannot be incremented safely.

### Before — actual failing output

```text
FF                                                                       [100%]
================================== FAILURES ===================================
___________ test_state_model_rejects_version_above_lua_safe_integer ___________
tests\test_version_range.py:17: in test_state_model_rejects_version_above_lua_safe_integer
    with pytest.raises(ValidationError, match="less than or equal"):
E   Failed: DID NOT RAISE <class 'pydantic_core._pydantic_core.ValidationError'>
_____________ test_save_rejects_increment_beyond_lua_safe_integer _____________
tests\test_version_range.py:50: in test_save_rejects_increment_beyond_lua_safe_integer
    with pytest.raises(StorageOperationError, match="maximum|safe"):
E   Failed: DID NOT RAISE <class 'src.core.exceptions.StorageOperationError'>
=========================== short test summary info ===========================
FAILED tests/test_version_range.py::test_state_model_rejects_version_above_lua_safe_integer
FAILED tests/test_version_range.py::test_save_rejects_increment_beyond_lua_safe_integer
2 failed in 0.40s
EXIT_CODE=1
```

### After — actual passing output

```text
..                                                                       [100%]
2 passed in 0.06s
EXIT_CODE=0
```

### Full suite after Fix 6 — actual output

```text
...................................................                      [100%]
51 passed in 12.61s
EXIT_CODE=0
```

## Final verification — actual full output

```text
PY_COMPILE_EXIT_CODE=0
Redis server v=3.0.504 sha=00000000:0 malloc=jemalloc-3.6.0 bits=64 build=a4f7a6e86f2d60b3
...................................................                      [100%]
51 passed in 12.71s
FINAL_PYTEST_EXIT_CODE=0
C:\Users\DELL\AppData\Roaming\Python\Python313\site-packages\pytest_asyncio\plugin.py:247: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
```

The final exit code was 0. The warning is pre-existing pytest configuration debt; it does not indicate a failed test.
