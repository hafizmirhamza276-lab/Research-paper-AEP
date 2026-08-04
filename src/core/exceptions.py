"""AEP Phase 1 exception hierarchy.

Provides distinct exception classes so the orchestrator can branch on
root cause (retry vs. fence vs. quarantine vs. alert) without inspecting
message strings.

This module is import-side-effect-free: no I/O, no network, no logging
configuration, no global state mutations at import time.
"""


class AEPException(Exception):
    """Baseline for all AEP core errors.

    Catch this to handle any AEP failure generically. Do not raise this
    directly — raise a specific subclass so the orchestrator can branch
    on root cause.
    """


class StorageOperationError(AEPException):
    """Transport/driver failure or an integrity violation that is NOT
    corruption and NOT a stale write.

    Examples:
        - Redis network fault or authentication failure.
        - execution_id key/payload mismatch (key is aep:state:X, payload
          claims execution_id Y).

    Retry semantics: retryable ONLY if the root cause is a transient
    transport error. The orchestrator must inspect the message to
    determine whether the cause is transient before scheduling a retry.
    An execution_id mismatch is not retryable; escalate to operator.
    """


class StaleWriteError(StorageOperationError):
    """The expected stored version did not match, or the incoming version
    was not exactly expected_version + 1.

    This is EXPECTED under contention (two workers race to save; the
    slower one is fenced). It is NOT a bug.

    Retry semantics: NOT retryable as-is. The worker must re-read current
    state, rebase its local changes, and retry with that exact version as
    expected_version and the next consecutive version as the incoming value.

    Raised by: RedisStorageAdapter.save_state when _CAS_SCRIPT returns -1.
    """


class StateCorruptionError(StorageOperationError):
    """Stored payload is unparseable, fails Pydantic validation, has no
    usable version field, or the schema migration chain cannot reach the
    current schema version.

    Retry semantics: NOT retryable. This is a data integrity failure.
    The adapter's _quarantine() is called before this exception is raised;
    the orchestrator must then mark the execution FAILED and eject it from
    active scheduling (Phase 2 concern).

    Per the Fail-Closed Invariant: corrupt payloads are quarantined, not
    silently overwritten or healed. Never catch this to continue silently.

    Raised by:
        - RedisStorageAdapter.save_state when _CAS_SCRIPT returns -2
          (after _quarantine is called).
        - RedisStorageAdapter.get_state when JSON decode fails, Pydantic
          validation fails, or schema migration fails (after _quarantine
          is called).
        - RedisStorageAdapter._migrate_schema when no migration path exists
          or the migration chain does not converge within 50 steps.
    """


class AmbiguousStateError(StateCorruptionError):
    """Persisted JSON contains duplicate object member names.

    Duplicate names are rejected before an ordinary mapping is built and
    before any Redis Lua mutation interprets the state.  Equal and conflicting
    duplicate values have identical fail-closed handling.  This error never
    means that repeating an external provider mutation is safe.
    """


class StateSerializationError(StorageOperationError):
    """Application state could not be represented as deterministic JSON."""


class Phase2StateProtectionError(StorageOperationError):
    """The Phase 1 writer was asked to create or replace Phase 2 state.

    This is a stable, fail-closed domain rejection.  It is not a Redis
    transport error and must not be retried through ``save_state``.  Marked
    executions and legacy executions with a non-empty intent ledger may be
    changed only by the invariant-aware Phase 2 Lua operations.
    """


class LockAcquisitionError(AEPException):
    """Lock engine communication fault or an invalid lease operation.

    Note: the plain "lock not available" case is NOT this exception.
    acquire_lock() returns None (not an error) when the lock is held by
    another worker. This exception signals an inability to communicate
    with the lock engine, or a programming error such as calling release
    with an invalid token type.

    Raised by: DistributedLockManager.acquire_lock, release_lock,
    renew_lock on Redis transport failure.
    """
