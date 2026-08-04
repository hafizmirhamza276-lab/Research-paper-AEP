PROBE A (stale-write fencing)
STALE_HIGH_VERSION_WRITE_ACCEPTED=False
REJECTION_TYPE=StaleWriteError
REJECTION=Stale write blocked for execution_id=ff32f69b-1f31-406f-a0f0-3bd3a4846fa9: expected version 1 did not match the stored version, or incoming version 999 was not exactly expected version + 1.
FINAL_VERSION=2
FINAL_STATUS=COMPLETED

PROBE B (lease-loss halt)
PROTECTED_BLOCK_COMPLETED=False
PROTECTED_BLOCK_RAISED=True
RAISED_TYPE=CancelledError
RAISED=CancelledError('')
RIVAL_ACQUIRED=True
ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False

PROBE C (oversized version / Lua precision)
ATTEMPTED_INCREMENT=9007199254740992 -> 9007199254740993
HANDLED_SAFELY=True
REJECTION_TYPE=StorageOperationError
REJECTION=version must be an integer between 1 and the Redis Lua safe maximum 9007199254740991.
FINAL_STORED_VERSION=9007199254740992

LOCK TOKEN CHECK (wrong / expired)
WRONG_TOKEN_WRITE_ACCEPTED=False
WRONG_TOKEN_REJECTION_TYPE=LockAcquisitionError
WRONG_TOKEN_REJECTION=State write rejected for execution_id=f180d5bf-1a39-4cd3-97cc-b401c7f866e8: lock token is missing, expired, or not the current owner.
EXPIRED_TOKEN_WRITE_ACCEPTED=False
EXPIRED_TOKEN_REJECTION_TYPE=LockAcquisitionError
EXPIRED_TOKEN_REJECTION=State write rejected for execution_id=a1dc6f46-511a-438b-a878-83f3e9606aba: lock token is missing, expired, or not the current owner.

STRESS-REPEAT PROBE B (25 iterations, randomized 0-200ms rival jitter)
ITERATION=01 JITTER_MS=61.626 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=02 JITTER_MS=56.487 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=03 JITTER_MS=134.332 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=04 JITTER_MS=161.002 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=05 JITTER_MS=63.713 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=06 JITTER_MS=127.996 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=07 JITTER_MS=44.207 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=08 JITTER_MS=94.783 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=09 JITTER_MS=175.962 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=10 JITTER_MS=142.734 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=11 JITTER_MS=21.148 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=12 JITTER_MS=105.298 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=13 JITTER_MS=30.386 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=14 JITTER_MS=75.374 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=15 JITTER_MS=177.323 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=16 JITTER_MS=111.810 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=17 JITTER_MS=38.099 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=18 JITTER_MS=33.041 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=19 JITTER_MS=172.077 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=20 JITTER_MS=180.640 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=21 JITTER_MS=35.151 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=22 JITTER_MS=19.449 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=23 JITTER_MS=95.503 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=24 JITTER_MS=106.935 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ITERATION=25 JITTER_MS=184.671 PROTECTED_BLOCK_RAISED=True RIVAL_ACQUIRED=True ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED=False
ORIGINAL_BLOCK_EXECUTING_WHEN_RIVAL_ACQUIRED_TRUE_COUNT=0
PROTECTED_BLOCK_RAISED_FALSE_COUNT=0
RIVAL_ACQUIRED_FALSE_COUNT=0
STRESS_PROBE_EXIT_CODE=0

FULL SUITE RE-RUN (real local Redis at redis://127.0.0.1:6380/15)
POST-SIX-FIX_SOURCE_CHANGES_FOR_ADVERSARIAL_PROBES=No
No code changes were made to src/core/storage.py, src/core/locks.py, or src/core/validation.py after the six fixes reported in fixes_report.md in order to make the four adversarial probes pass.
Exact completed pytest output:
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

============================= 51 passed in 12.66s =============================
FULL_SUITE_EXIT_CODE=0
C:\Users\DELL\AppData\Roaming\Python\Python313\site-packages\pytest_asyncio\plugin.py:247: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
