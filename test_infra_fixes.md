# Test infrastructure fixes

No production code under `src/` was changed.

## What changed

1. Fail-closed backend selection

   `tests/conftest.py` now aborts pytest configuration with a clear
   `pytest.UsageError` when `REDIS_URL` is unset and `fakeredis` cannot be
   imported. The error tells the developer to set `REDIS_URL` or install
   `fakeredis[lua]`; Redis-backed tests are no longer silently skipped in this
   situation.

2. Destructive cleanup safety

   Real Redis is accepted by default only when the connected client reports
   database 15. Other database indexes are refused before cleanup unless
   `AEP_TEST_ALLOW_FLUSHALL=1` is explicitly set.

   `FLUSHALL` was removed completely. Per-test setup and teardown now use
   incremental `SCAN` plus batched `DELETE` for `aep:*` keys only. This combined
   approach is more robust than either protection alone: the DB allowlist
   prevents accidental use of the usual/shared DBs, while namespace-scoped
   cleanup limits collateral damage even when the override is deliberately
   used. The historical override name is retained as requested, but the code
   does not execute `FLUSHALL` under any condition.

3. Non-vacuous assertions

   - `test_cas_corrupted_json_field_in_table` now requires a typed rejection
     and verifies that the corrupt stored payload was not overwritten.
   - `test_cas_quarantine_called_on_corrupt` now requires
     `StateCorruptionError`, requires at least one poison key, and validates its
     reason and raw forensic payload.
   - `test_lease_hard_cap_stops_renewal` prevents normal context cleanup from
     deleting the lock, then verifies renewal calls stop and the real Redis TTL
     counts down.
   - `test_lease_cap_prevents_zombie_renewal` uses a short real Redis TTL,
     prevents normal release, and verifies the lock actually expires and is not
     recreated by a zombie heartbeat.

## Full suite before changes: no backend configured

Command:

```powershell
Remove-Item Env:REDIS_URL -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE='1'
py -3 -m pytest -p no:cacheprovider
```

Actual output:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.1, pytest-8.3.3, pluggy-1.6.0
rootdir: C:\Users\DELL\Desktop\personal\Research-paper-20260727T182111Z-1-001\Research-paper
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.13.0, langsmith-0.7.9, asyncio-1.3.0, cov-7.0.0, mock-3.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 51 items

tests\test_cas_write.py sssssssssss                                      [ 21%]
tests\test_get_migration.py sssssssss                                    [ 39%]
tests\test_lease.py ssssssssss                                           [ 58%]
tests\test_locks.py sssssssss                                            [ 76%]
tests\test_races.py ssss                                                 [ 84%]
tests\test_uuid_validation.py ...sss                                     [ 96%]
tests\test_version_range.py .s                                           [100%]

======================== 4 passed, 47 skipped in 0.54s ========================
FULL_SUITE_EXIT_CODE=0
C:\Users\DELL\AppData\Roaming\Python\Python313\site-packages\pytest_asyncio\plugin.py:247: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
```

## Full suite after changes: no backend configured

Command:

```powershell
Remove-Item Env:REDIS_URL -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE='1'
py -3 -m pytest -p no:cacheprovider
```

Actual output:

```text
FULL_SUITE_EXIT_CODE=4
ERROR: Redis test backend unavailable: set REDIS_URL to a dedicated test Redis database (DB 15 is allowed by default), or install fakeredis[lua]. Refusing to skip Redis-backed tests.
```

## Full suite after changes: dedicated Redis configured

Command:

```powershell
$env:REDIS_URL='redis://127.0.0.1:6380/15'
$env:PYTHONDONTWRITEBYTECODE='1'
py -3 -m pytest tests -p no:cacheprovider
```

Actual output:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.1, pytest-8.3.3, pluggy-1.6.0
rootdir: C:\Users\DELL\Desktop\personal\Research-paper-20260727T182111Z-1-001\Research-paper
configfile: pyproject.toml
plugins: anyio-4.13.0, langsmith-0.7.9, asyncio-1.3.0, cov-7.0.0, mock-3.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 51 items

tests\test_cas_write.py ...........                                      [ 21%]
tests\test_get_migration.py .........                                    [ 39%]
tests\test_lease.py ..........                                           [ 58%]
tests\test_locks.py .........                                            [ 76%]
tests\test_races.py ....                                                 [ 84%]
tests\test_uuid_validation.py ......                                     [ 96%]
tests\test_version_range.py ..                                           [100%]

============================= 51 passed in 11.62s =============================
FULL_SUITE_EXIT_CODE=0
C:\Users\DELL\AppData\Roaming\Python\Python313\site-packages\pytest_asyncio\plugin.py:247: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
```

## Additional safety verification

DB 0 was refused before cleanup:

```text
RuntimeError: Refusing Redis test cleanup on DB 0. Allowed dedicated test DB(s): 15. Point REDIS_URL at DB 15, or explicitly set AEP_TEST_ALLOW_FLUSHALL=1 to override. Even with the override, cleanup remains limited to aep:* keys.
SAFETY_GUARD_EXIT_CODE=1
```

Namespace-scoped cleanup was checked with temporary sentinel keys:

```text
sentinels_created
.                                                                        [100%]
1 passed in 0.05s
unrelated_after= preserve-me
aep_after= None
SCOPED_CLEANUP_CHECK_EXIT_CODE=0
```

The temporary unrelated sentinel was deleted explicitly after this check.
