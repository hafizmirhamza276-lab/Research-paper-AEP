"""B3: the full protocol with the durability barrier ablated.

PAPER_ROADMAP.md section 3.3: *"B3: Intent w/o durability barrier -- Full
protocol minus WAITAOF (ablation isolating the barrier's value)."*

B3 is not a reimplementation. It is ``WriteAheadRunner`` -- the same class, the
same Lua scripts, the same preflight, the same recovery service -- built with
:class:`NoBarrierDurabilityBarrier` in place of
``RealWaitAofDurabilityBarrier``. Exactly one behaviour differs: dispatch no
longer waits for Redis to acknowledge that the ``ABOUT_TO_FIRE`` intent has
reached the append-only file.

Two decisions about the shape of the ablation, both of which change what the
result means.

**``validate_startup`` is not ablated.** The capability probe still runs, so B3
still refuses a server without AOF or without ``WAITAOF`` support. If it were
removed as well, B3 would differ from AEP-full in the durability *configuration*
as well as the barrier, and a difference in the results could not be attributed
to either. What is ablated is one round trip per dispatch, and only that.

**The acknowledgement is still minted.** ``confirm_durable_ack`` mints the
single-use :class:`DurabilityAck` that ``authorize_dispatch`` consumes, so B3
still records a Redis-visible dispatch authorisation and its preflight still
re-checks it. Removing that would ablate the authorisation mechanism too. B3's
authorisation is simply issued on the strength of a barrier that did not wait.

**What the ablation can and cannot show.** ``redis/phase2.conf`` sets
``appendfsync everysec``, so without ``WAITAOF`` an intent may sit in Redis's
AOF buffer for up to a second. A *graceful* restart (``docker compose restart``
sends SIGTERM, and Redis flushes on shutdown) will not lose it, so a run whose
only infrastructure fault is a graceful restart will show B3 and AEP-full
agreeing -- and that agreement is not evidence that the barrier is worthless.
Losing the buffered write needs Redis to die without flushing. The harness's
``redis_kill`` fault is what does that, and any B3-versus-AEP claim must say
which fault was in force.
"""

from __future__ import annotations

from typing import Any

from aep_core.core.durability import (
    DurabilityCapabilityError,
    RealWaitAofDurabilityBarrier,
    RedisDurabilityCapabilities,
)

from experiments.baselines.contract import SystemId

SYSTEM = SystemId.B3_INTENT_NO_BARRIER


class NoBarrierDurabilityBarrier:
    """Reports the preceding write durable without asking whether it is.

    Not a test double. ``test_only`` is ``False`` because this really is the
    barrier a real -- if ill-advised -- deployment would have if it decided the
    ``WAITAOF`` round trip was too expensive, and because ``EVALUATION`` mode
    must accept it or B3 could not be measured at all. It fails closed on the
    one thing it still checks: ``confirm_durable`` refuses to answer before
    ``validate_startup`` has succeeded, exactly as the real barrier does, so
    the ablation cannot accidentally also remove the startup gate.
    """

    test_only = False

    def __init__(self) -> None:
        self._delegate = RealWaitAofDurabilityBarrier()
        self._startup_validated = False

    async def validate_startup(
        self, redis_client: Any
    ) -> RedisDurabilityCapabilities:
        capabilities = await self._delegate.validate_startup(redis_client)
        self._startup_validated = True
        return capabilities

    async def confirm_durable(self, connection: Any, timeout_ms: int) -> bool:
        if type(timeout_ms) is not int or timeout_ms <= 0:
            raise ValueError("durability timeout_ms must be a positive integer")
        if not self._startup_validated:
            raise DurabilityCapabilityError(
                "durability startup validation has not succeeded"
            )
        # The ablation. No command is issued: the write is reported durable on
        # the strength of nothing at all.
        return True
