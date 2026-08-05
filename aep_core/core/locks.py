"""AEP Phase 1 distributed lock manager.

Provides:
  - _RELEASE_SCRIPT: token-checked atomic lock release Lua script.
  - _RENEW_SCRIPT: token-checked atomic TTL extension Lua script.
  - DistributedLockManager: acquire/release/renew primitives and an
    auto-renewing lease context manager with a hard cap.

Honest guarantee: corruption and contention are detectable, and the system
fails closed. This module does NOT claim absolute atomicity, split-brain
impossibility, or exactly-once delivery. The lock is a LEASE, not a
consensus primitive; concurrent overlap is possible if the lease expires and
is made detectable by the CAS versioning in storage.py.

Import-side-effect-free: no I/O, no network, no logging config at import time.
"""

import asyncio
import contextlib
import logging
import secrets
from typing import AsyncIterator, Optional

from redis.asyncio import Redis

from aep_core.core.exceptions import LockAcquisitionError
from aep_core.core.validation import validate_execution_id

logger = logging.getLogger("aep.locks")

# ---------------------------------------------------------------------------
# Lua scripts — registered via register_script in __init__
# ---------------------------------------------------------------------------

_RELEASE_SCRIPT: str = """\
-- _RELEASE_SCRIPT: Token-checked atomic lock release.
--
-- KEYS[1] = aep:lock:{execution_id}
-- ARGV[1] = ownership token (secrets value; not the fencing token)
--
-- Returns:
--   1  => lock was held by this token; deleted successfully.
--   0  => token mismatch or key does not exist (lock expired or
--          already held by another worker). The Python caller MUST
--          log a warning: this is a CRITICAL signal that the lease
--          may have expired and overlap may have occurred.
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

_RENEW_SCRIPT: str = """\
-- _RENEW_SCRIPT: Token-checked atomic TTL extension.
--
-- KEYS[1] = aep:lock:{execution_id}
-- ARGV[1] = ownership token
-- ARGV[2] = new TTL in milliseconds (PEXPIRE takes ms)
--
-- Returns:
--   1  => token matched; PEXPIRE applied (TTL extended).
--   0  => token mismatch or key expired. The caller MUST treat
--          itself as lock-less and fail-closed immediately.
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("PEXPIRE", KEYS[1], ARGV[2])
else
    return 0
end
"""


# ---------------------------------------------------------------------------
# Lock manager
# ---------------------------------------------------------------------------

class DistributedLockManager:
    """Distributed lease lock backed by a single Redis instance.

    Provides acquire/release/renew primitives and an auto-renewing lease
    context manager with a hard cap.

    The lock provides an OWNERSHIP signal (who holds the lease), not a
    FENCING guarantee. Concurrent overlap is still possible if the lease
    expires mid-operation. Overlap is made detectable by the monotonic
    version CAS in storage.py (the CAS Fencing Invariant), not by this
    lock alone.

    The honest guarantee: corruption and contention are detectable, and
    the system fails closed.
    """

    def __init__(self, redis_client: Redis) -> None:
        """Initialize the lock manager.

        Args:
            redis_client: A pre-built redis.asyncio.Redis instance
                constructed with decode_responses=True and a shared
                connection pool. Shared with RedisStorageAdapter — do not
                create a separate client.

        Post-condition:
            self._release and self._renew are bound to the compiled Lua
            script callables via register_script. No network I/O in __init__.
        """
        self.redis: Redis = redis_client
        self._release = self.redis.register_script(_RELEASE_SCRIPT)
        self._renew = self.redis.register_script(_RENEW_SCRIPT)

    @staticmethod
    def _validate_execution_id(execution_id: str) -> None:
        try:
            validate_execution_id(execution_id)
        except ValueError:
            raise LockAcquisitionError(
                "execution_id must be a canonical UUIDv4 string"
            ) from None

    async def acquire_lock(
        self,
        execution_id: str,
        ttl_seconds: int = 60,
    ) -> Optional[str]:
        """Attempt to acquire the lock for the given execution_id.

        Uses SET NX EX for an atomic acquire. The returned token is a
        random ownership token (secrets.token_urlsafe(32)) — it is NOT the
        monotonic fencing token. Do not use it for CAS versioning.

        Args:
            execution_id: The UUIDv4 of the execution to lock.
            ttl_seconds: Lock TTL in seconds. Default 60. Must be sized
                so that T_client <= ttl_seconds - 15 (Timeout Invariant).

        Returns:
            A random token string on successful acquisition.
            None if the lock is already held by another worker. None is
            NOT an error; the orchestrator owns backoff/retry policy.

        Raises:
            LockAcquisitionError: on Redis transport failure (network,
                auth, timeout). Not raised for "lock unavailable."

        Post-condition (on return of a token):
            aep:lock:{execution_id} exists in Redis with TTL = ttl_seconds
            and value = token.
        """
        self._validate_execution_id(execution_id)
        key = f"aep:lock:{execution_id}"
        token = secrets.token_urlsafe(32)
        try:
            acquired = await self.redis.set(key, token, nx=True, ex=ttl_seconds)
        except Exception as exc:
            raise LockAcquisitionError(
                f"Lock engine fault on acquire for execution_id={execution_id}; "
                f"failure_class={type(exc).__name__}"
            ) from None
        return token if acquired else None

    async def release_lock(
        self,
        execution_id: str,
        lock_token: str,
    ) -> bool:
        """Release the lock only if the token still matches.

        Uses _RELEASE_SCRIPT for an atomic token check + DEL.

        Args:
            execution_id: The UUIDv4 of the execution to unlock.
            lock_token: The ownership token returned by acquire_lock.

        Returns:
            True if the lock was held by this token and was deleted.
            False if the token did not match (lock expired or re-acquired
            by another worker). False is a CRITICAL signal: potential
            overlap has occurred. A warning is logged via logger.warning.

        Raises:
            LockAcquisitionError: on Redis transport failure.

        Post-condition (on return True):
            aep:lock:{execution_id} does not exist in Redis.
        """
        self._validate_execution_id(execution_id)
        key = f"aep:lock:{execution_id}"
        try:
            result = await self._release(keys=[key], args=[lock_token])
        except Exception as exc:
            raise LockAcquisitionError(
                f"Lock release fault for execution_id={execution_id}; "
                f"failure_class={type(exc).__name__}"
            ) from None
        if int(result) == 0:
            logger.warning(
                "AEP lock release returned 0 for execution_id=%s: lease "
                "expired or re-acquired by another worker. Possible overlap "
                "occurred. Review logs for concurrent activity.",
                execution_id,
            )
            return False
        return True

    async def renew_lock(
        self,
        execution_id: str,
        lock_token: str,
        extend_ms: int = 30000,
    ) -> bool:
        """Extend the lock TTL atomically only if the token still matches.

        Uses _RENEW_SCRIPT for an atomic token check + PEXPIRE. PEXPIRE
        takes milliseconds; use extend_ms for sub-second precision.

        Args:
            execution_id: The UUIDv4 of the execution whose lock to extend.
            lock_token: The ownership token from acquire_lock.
            extend_ms: New TTL in milliseconds. Default 30000 (30s).

        Returns:
            True if the token matched and TTL was extended.
            False if the token no longer matches (lock expired or
            re-acquired). The caller MUST stop all work immediately on
            False — it no longer owns the lock (Fail-Closed Invariant).

        Raises:
            LockAcquisitionError: on Redis transport failure.
        """
        self._validate_execution_id(execution_id)
        key = f"aep:lock:{execution_id}"
        try:
            result = await self._renew(
                keys=[key], args=[lock_token, str(extend_ms)]
            )
        except Exception as exc:
            raise LockAcquisitionError(
                f"Lock renew fault for execution_id={execution_id}; "
                f"failure_class={type(exc).__name__}"
            ) from None
        return int(result) == 1

    # ---- OPTIONAL helper: capped auto-renewing lease ----------------------

    @contextlib.asynccontextmanager
    async def lease(
        self,
        execution_id: str,
        ttl_seconds: int = 60,
        max_total_lease_seconds: int = 600,
        client_deadline_seconds: Optional[float] = None,
        buffer_margin_seconds: float = 15.0,
    ) -> AsyncIterator[Optional[str]]:
        """Acquire a lock and auto-renew it in the background up to a hard cap.

        Heartbeat interval is ttl_seconds / 3 (minimum 1s). Each heartbeat
        calls renew_lock with extend_ms = ttl_seconds * 1000.

        Hard cap behavior (Fail-Closed Invariant):
            When elapsed renewal time reaches max_total_lease_seconds, the
            heartbeat cancels the task running the protected context. That
            task receives asyncio.CancelledError at its next suspension point,
            then the context cleanup releases the lock.

        Heartbeat False behavior:
            If renew_lock returns False during a heartbeat, the task stops
            renewing, logs a warning, and cancels the protected task. The
            caller cannot continue silently after ownership is lost.

        Args:
            execution_id: The UUIDv4 of the execution to lock.
            ttl_seconds: Per-renewal TTL in seconds. Default 60.
                Must satisfy Timeout Invariant: T_client <= ttl_seconds - 15.
            max_total_lease_seconds: Hard ceiling on total auto-renewal
                duration. Default 600 (10 minutes). Once elapsed, the
                protected task is cancelled and cleanup releases the lock.
            client_deadline_seconds: Maximum duration of the protected block.
                Defaults to ttl_seconds - buffer_margin_seconds. Exceeding the
                deadline cancels the protected task.
            buffer_margin_seconds: Safety margin between the protected-block
                deadline and lock TTL. Must be at least 15 seconds.

        Yields:
            The ownership token (str) on successful acquisition.
            None if the lock could not be acquired. The caller MUST check
            for None — if None, no heartbeat task is started.

        Note: this method never claims "exactly-once" or "split-brain
        impossible." The honest guarantee is: corruption and contention are
        detectable, and the system fails closed.
        """
        self._validate_execution_id(execution_id)
        numeric_types = (int, float)
        if (
            isinstance(buffer_margin_seconds, bool)
            or not isinstance(buffer_margin_seconds, numeric_types)
            or buffer_margin_seconds < 15
        ):
            raise LockAcquisitionError(
                "Buffer margin must be at least 15 seconds."
            )
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, numeric_types)
            or ttl_seconds <= buffer_margin_seconds
        ):
            raise LockAcquisitionError(
                "Lock TTL must be greater than the buffer margin."
            )
        maximum_deadline = ttl_seconds - buffer_margin_seconds
        if client_deadline_seconds is None:
            client_deadline_seconds = maximum_deadline
        if (
            isinstance(client_deadline_seconds, bool)
            or not isinstance(client_deadline_seconds, numeric_types)
            or client_deadline_seconds <= 0
            or client_deadline_seconds > maximum_deadline
        ):
            raise LockAcquisitionError(
                "Client deadline must be positive and satisfy T_client <= "
                "T_lock - Buffer."
            )
        if (
            isinstance(max_total_lease_seconds, bool)
            or not isinstance(max_total_lease_seconds, numeric_types)
            or max_total_lease_seconds <= 0
        ):
            raise LockAcquisitionError(
                "max_total_lease_seconds must be positive."
            )

        token = await self.acquire_lock(execution_id, ttl_seconds)
        if token is None:
            yield None
            return

        stop = asyncio.Event()
        owner_task = asyncio.current_task()
        if owner_task is None:  # pragma: no cover - asyncio always has one here
            raise RuntimeError("lease() must run inside an asyncio Task")

        async def _heartbeat() -> None:
            elapsed = 0.0
            # Renewal interval = ttl/3 with a small floor (50ms) to avoid
            # busy-looping at sub-millisecond TTLs while still keeping the
            # interval comfortably below TTL even for short TTLs (e.g.
            # ttl_seconds=1 -> interval=0.33s, well under expiry). A 1.0s
            # floor would equal or exceed the TTL for short-TTL tests,
            # causing the first renewal to race with or fire after expiry
            # (renew_lock returns False, cap never reached).
            interval = max(
                min(
                    ttl_seconds / 3.0,
                    max_total_lease_seconds / 3.0,
                    client_deadline_seconds / 3.0,
                ),
                0.05,
            )
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=interval)
                    return  # Normal exit: stop was set by the finally block.
                except asyncio.TimeoutError:
                    elapsed += interval
                    if elapsed >= max_total_lease_seconds:
                        logger.warning(
                            "AEP lease hard cap (%ss) hit for "
                            "execution_id=%s; cancelling protected work "
                            "(fail-closed per Fail-Closed Invariant).",
                            max_total_lease_seconds,
                            execution_id,
                        )
                        owner_task.cancel(
                            f"AEP lease hard cap reached for {execution_id}"
                        )
                        return
                    try:
                        renewed = await self.renew_lock(
                            execution_id,
                            token,
                            extend_ms=ttl_seconds * 1000,
                        )
                    except Exception as exc:
                        logger.warning(
                            "AEP lease renewal failed for execution_id=%s; "
                            "failure_class=%s. "
                            "Cancelling protected work.",
                            execution_id,
                            type(exc).__name__,
                        )
                        owner_task.cancel(
                            f"AEP lease renewal failed for {execution_id}"
                        )
                        return
                    if not renewed:
                        logger.warning(
                            "AEP lease renewal returned False for "
                            "execution_id=%s; lock no longer owned. "
                            "Stopping heartbeat. Worker should cease work.",
                            execution_id,
                        )
                        owner_task.cancel(
                            f"AEP lease ownership lost for {execution_id}"
                        )
                        return

        async def _deadline_watchdog() -> None:
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=client_deadline_seconds
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "AEP client deadline (%ss) exceeded for execution_id=%s; "
                    "cancelling protected work before the lock TTL.",
                    client_deadline_seconds,
                    execution_id,
                )
                owner_task.cancel(
                    f"AEP client deadline exceeded for {execution_id}"
                )

        hb = asyncio.create_task(_heartbeat())
        deadline_watchdog = asyncio.create_task(_deadline_watchdog())
        try:
            yield token
        finally:
            stop.set()
            with contextlib.suppress(Exception):
                await hb
            with contextlib.suppress(Exception):
                await deadline_watchdog
            await self.release_lock(execution_id, token)
