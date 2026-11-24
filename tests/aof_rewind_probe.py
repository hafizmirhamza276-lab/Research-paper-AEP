"""Real-crash probe for residual R1-3 (AOF rewind un-fencing a lease).

Deliberately NOT named ``test_*``: its outcome depends on where the
``appendfsync everysec`` boundary happens to fall, so it is an experiment, not
an assertion.  ``tests/test_residual_probes.py`` holds the deterministic
counterpart.

Run it explicitly:

    AEP_PROBE_REDIS_URL=redis://127.0.0.1:6381/15 \
    AEP_PROBE_CONTAINER=aep-phase2-redis72 \
    python tests/aof_rewind_probe.py

It SIGKILLs the Redis container immediately after a lease release plus a state
write, restarts it, and reports whether the AOF replay lost either write.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redis.asyncio import Redis  # noqa: E402

from aep_core.core.locks import DistributedLockManager  # noqa: E402
from aep_core.core.storage import (  # noqa: E402
    AEPExecutionState,
    AEPStatus,
    RedisStorageAdapter,
)

REDIS_URL = os.environ.get("AEP_PROBE_REDIS_URL", "redis://127.0.0.1:6381/15")
CONTAINER = os.environ.get("AEP_PROBE_CONTAINER", "aep-phase2-redis72")
ROUNDS = int(os.environ.get("AEP_PROBE_ROUNDS", "1"))


def _docker(*args: str) -> tuple[int, str]:
    completed = subprocess.run(
        ["docker", *args], capture_output=True, text=True
    )
    return completed.returncode, (completed.stdout + completed.stderr).strip()


async def _wait_ready(timeout_s: float = 60.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        client = Redis.from_url(REDIS_URL, decode_responses=True)
        try:
            if await client.ping():
                await client.aclose()
                return
        except Exception:
            pass
        finally:
            try:
                await client.aclose()
            except Exception:
                pass
        await asyncio.sleep(0.5)
    raise RuntimeError("redis did not come back up")


async def one_round(index: int) -> dict:
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    locks = DistributedLockManager(client)
    storage = RedisStorageAdapter(client)

    execution_id = str(uuid.uuid4())
    token = await locks.acquire_lock(execution_id, ttl_seconds=600)
    assert token
    await storage.save_state(
        AEPExecutionState(execution_id=execution_id, status=AEPStatus.IDLE),
        expected_version=0,
        lock_token=token,
        ttl_seconds=3600,
    )
    # Advance the version and drop the lease, then die immediately.  These are
    # exactly the two writes whose loss would un-fence the previous holder.
    await storage.save_state(
        AEPExecutionState(
            execution_id=execution_id, status=AEPStatus.PROCESSING, version=2
        ),
        expected_version=1,
        lock_token=token,
        ttl_seconds=3600,
    )
    released = await locks.release_lock(execution_id, token)
    await client.aclose()

    code, out = _docker("kill", "--signal", "SIGKILL", CONTAINER)
    kill_result = f"exit={code} {out}"
    code, out = _docker("start", CONTAINER)
    start_result = f"exit={code} {out}"
    await _wait_ready()

    client = Redis.from_url(REDIS_URL, decode_responses=True)
    storage = RedisStorageAdapter(client)
    after_state = await storage.get_state(execution_id)
    after_lock = await client.get(f"aep:lock:{execution_id}")
    await client.aclose()

    return {
        "round": index,
        "execution_id": execution_id,
        "released_before_kill": released,
        "kill": kill_result,
        "start": start_result,
        "version_after_replay": None if after_state is None else after_state.version,
        "state_lost_entirely": after_state is None,
        "version_rewound": after_state is not None and after_state.version < 2,
        "lease_resurrected": after_lock == token,
    }


async def main() -> int:
    print(f"probe: redis={REDIS_URL} container={CONTAINER} rounds={ROUNDS}")
    findings = []
    for index in range(1, ROUNDS + 1):
        result = await one_round(index)
        findings.append(result)
        for key, value in result.items():
            print(f"  {key}: {value}")
        print("  ---")
    rewound = [item for item in findings if item["version_rewound"]]
    resurrected = [item for item in findings if item["lease_resurrected"]]
    print(f"rounds={len(findings)} version_rewound={len(rewound)} "
          f"lease_resurrected={len(resurrected)}")
    print(
        "NOTE: a zero count does NOT refute R1-3; it means this run did not "
        "land inside the appendfsync everysec window."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
