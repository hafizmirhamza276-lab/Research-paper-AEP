"""What a hard Redis kill actually loses, measured rather than assumed.

Amendment E1 asked for a hard Redis kill "timed to land inside the appendfsync
everysec window", on the premise that a write not yet fsynced is a write that a
kill destroys. That premise is worth one experiment before six hours of cells
are collected on top of it, and this is the experiment.

**The claim under test.** ``redis/phase2.conf`` sets ``appendfsync everysec``.
The usual reading is "a write may be up to a second from durable, so a crash in
that second loses it". The reading is right about *power loss* and wrong about
*process death*, and the difference is the whole of amendment E1's outcome:

* Redis issues ``write(2)`` on the append-only file on every event loop
  iteration. Those bytes leave the process immediately and enter the kernel's
  page cache.
* ``appendfsync everysec`` defers only the ``fsync(2)`` that moves them from
  the page cache to the disk.
* ``docker kill -s KILL`` destroys the *process*. The kernel, and therefore the
  page cache, is untouched, and the bytes are flushed by a kernel that is still
  running.

So a hard process kill should lose **nothing**, and ``WAITAOF`` should make no
difference to what survives one. This module measures that directly.

**The design.** Each trial:

1. writes a key and puts it through ``WAITAOF``, which both proves the barrier
   works and *phase-aligns* the everysec timer -- when ``WAITAOF`` returns, an
   fsync has just completed, so the next one is a full second away and the
   window under test is as wide as it can be;
2. writes a second key and does **not** wait for it;
3. hard-kills the container and records when the server stopped answering;
4. restarts it, waits for readiness, and reports which of the two keys is
   still there.

``acknowledged`` surviving is a precondition: if it does not, the run says
nothing about the unacknowledged one, and the trial is reported as VOID rather
than as evidence. ``unacknowledged`` surviving is the finding.

    python -m experiments.redis_durability_window --trials 10

Every trial's raw line is printed as it happens. Nothing is averaged away and
no trial is dropped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from redis.asyncio import Redis

from experiments.harness.redis_kill import kill_redis, start_redis

ACKNOWLEDGED_KEY = "aep:durability-window:acknowledged"
UNACKNOWLEDGED_KEY = "aep:durability-window:unacknowledged"


@dataclass
class Trial:
    index: int
    waitaof_ack: list[int] | None = None
    align_ms: int = 0
    write_to_death_ms: int | None = None
    kill_cli_ms: int = 0
    restart_ms: int = 0
    readiness_ms: int = 0
    uptime_after_seconds: int = -1
    acknowledged_survived: bool | None = None
    unacknowledged_survived: bool | None = None
    error: str | None = None

    @property
    def verdict(self) -> str:
        if self.error:
            return "ERROR"
        if self.uptime_after_seconds > 60:
            return "VOID: the kill did not land"
        if not self.acknowledged_survived:
            return "VOID: the acknowledged write did not survive"
        return (
            "UNACKNOWLEDGED SURVIVED"
            if self.unacknowledged_survived
            else "UNACKNOWLEDGED LOST"
        )

    def echo(self) -> dict[str, Any]:
        return {
            "trial": self.index,
            "waitaof_ack": self.waitaof_ack,
            "align_ms": self.align_ms,
            "write_to_death_ms": self.write_to_death_ms,
            "kill_cli_ms": self.kill_cli_ms,
            "restart_ms": self.restart_ms,
            "readiness_ms": self.readiness_ms,
            "uptime_after_seconds": self.uptime_after_seconds,
            "acknowledged_survived": self.acknowledged_survived,
            "unacknowledged_survived": self.unacknowledged_survived,
            "verdict": self.verdict,
            "error": self.error,
        }

    def line(self) -> str:
        return (
            f"trial {self.index:>2}  align={self.align_ms:>4}ms  "
            f"write->death={self.write_to_death_ms if self.write_to_death_ms is not None else '   -':>5}ms  "
            f"kill_cli={self.kill_cli_ms:>4}ms  restart={self.restart_ms:>4}ms  "
            f"ready={self.readiness_ms:>4}ms  uptime_after={self.uptime_after_seconds:>3}s  "
            f"ack={_mark(self.acknowledged_survived)}  "
            f"unack={_mark(self.unacknowledged_survived)}  {self.verdict}"
        )


def _mark(value: bool | None) -> str:
    if value is None:
        return "  ?  "
    return " kept" if value else " lost"


async def _wait_ready(url: str, timeout: float = 90.0) -> int:
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        client = Redis.from_url(url, decode_responses=True, socket_connect_timeout=0.4)
        try:
            if await client.ping():
                return int((time.monotonic() - started) * 1000)
        except Exception:  # noqa: BLE001 -- it is restarting
            pass
        finally:
            try:
                await client.aclose()
            except Exception:  # noqa: BLE001
                pass
        await asyncio.sleep(0.05)
    raise RuntimeError(f"Redis did not become ready within {timeout}s")


async def _observe_death(url: str, deadline: float) -> float | None:
    """When the server stopped answering. Brackets the kill's delivery."""
    while time.monotonic() < deadline:
        client = Redis.from_url(url, decode_responses=True, socket_connect_timeout=0.3)
        try:
            await client.ping()
        except Exception:  # noqa: BLE001 -- this is the event being timed
            return time.monotonic()
        finally:
            try:
                await client.aclose()
            except Exception:  # noqa: BLE001
                pass
        await asyncio.sleep(0.02)
    return None


async def run_trial(index: int, *, url: str, container: str) -> Trial:
    trial = Trial(index=index)
    client = Redis.from_url(url, decode_responses=True)
    try:
        async with client.client() as connection:
            # (1) An acknowledged write. Proves the barrier works, and aligns
            # the everysec phase so the window under test is at its widest.
            await connection.set(ACKNOWLEDGED_KEY, f"trial-{index}", ex=3600)
            align_started = time.monotonic()
            trial.waitaof_ack = list(
                await connection.execute_command("WAITAOF", 1, 0, 5000)
            )
            trial.align_ms = int((time.monotonic() - align_started) * 1000)

            # (2) The write under test. Deliberately not waited on.
            await connection.set(UNACKNOWLEDGED_KEY, f"trial-{index}", ex=3600)
            wrote_at = time.monotonic()

        # (3) The kill, on a thread so the observer can time the death.
        loop = asyncio.get_running_loop()
        killing = loop.run_in_executor(None, kill_redis, container)
        death = await _observe_death(url, deadline=wrote_at + 30.0)
        outcome = await killing
        trial.kill_cli_ms = int(outcome.get("command_ms", 0))
        if death is not None:
            trial.write_to_death_ms = int((death - wrote_at) * 1000)
    except Exception as error:  # noqa: BLE001 -- a failed trial is reported
        trial.error = f"{type(error).__name__}: {error}"
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass

    # (4) Back up, and read the two keys.
    started = start_redis(container)
    trial.restart_ms = int(started.get("start_ms", 0))
    if started.get("returncode") != 0:
        trial.error = f"docker start failed: {started.get('stderr')}"
        return trial
    trial.readiness_ms = await _wait_ready(url)

    client = Redis.from_url(url, decode_responses=True)
    try:
        trial.uptime_after_seconds = int(
            (await client.info("server")).get("uptime_in_seconds", -1)
        )
        trial.acknowledged_survived = await client.get(ACKNOWLEDGED_KEY) is not None
        trial.unacknowledged_survived = (
            await client.get(UNACKNOWLEDGED_KEY) is not None
        )
        await client.unlink(ACKNOWLEDGED_KEY, UNACKNOWLEDGED_KEY)
    finally:
        await client.aclose()
    return trial


async def run(trials: int, *, url: str, container: str) -> dict[str, Any]:
    print("=" * 100)
    print("Redis durability window -- what a hard process kill actually loses")
    print("=" * 100)
    print(f"  platform   {platform.platform()}")
    print(f"  container  {container}")
    print(f"  url        {url}")
    print(f"  trials     {trials}")
    print(f"  mechanism  docker kill -s KILL  (SIGKILL to the container's PID 1)")
    print("")

    results: list[Trial] = []
    for index in range(1, trials + 1):
        trial = await run_trial(index, url=url, container=container)
        results.append(trial)
        print(trial.line(), flush=True)

    usable = [t for t in results if t.verdict.startswith("UNACKNOWLEDGED")]
    lost = [t for t in usable if not t.unacknowledged_survived]
    summary = {
        "platform": platform.platform(),
        "container": container,
        "mechanism": "docker kill -s KILL",
        "appendfsync": "everysec",
        "trials": trials,
        "usable_trials": len(usable),
        "void_trials": len(results) - len(usable),
        "unacknowledged_lost": len(lost),
        "unacknowledged_survived": len(usable) - len(lost),
        "results": [t.echo() for t in results],
    }
    print("")
    print("-" * 100)
    print(
        f"unacknowledged write lost in {len(lost)}/{len(usable)} usable trials "
        f"({summary['void_trials']} void)"
    )
    if usable and not lost:
        print(
            "\nFINDING. Not one un-acknowledged write was lost. With "
            "appendfsync everysec Redis still write(2)s the AOF on every event\n"
            "loop iteration; everysec defers the fsync, not the write. A "
            "SIGKILL removes the process and leaves those bytes in the\n"
            "kernel's page cache, which a still-running kernel flushes. So "
            "appendonly yes already survives a process death, and WAITAOF\n"
            "adds nothing against this fault class. Separating AEP-full from "
            "B3 on record DURABILITY requires a fault that loses the page\n"
            "cache -- host power loss, kernel panic, or VM destruction -- and no "
            "process-level fault can stand in for one.\n\n"
            "The barrier's other effect is untouched by this and is what the "
            "redis-kill-preack cells measure: AEP-full WAITS where B3 does\n"
            "not, so a Redis that dies inside that wait stops AEP-full "
            "dispatching and does not stop B3."
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure what a hard Redis kill loses under appendfsync everysec."
    )
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6381/15")
    parser.add_argument("--container", default="aep-phase2-redis72")
    parser.add_argument("--destination", default=None)
    arguments = parser.parse_args(argv)

    summary = asyncio.run(
        run(arguments.trials, url=arguments.redis_url, container=arguments.container)
    )
    if arguments.destination:
        path = Path(arguments.destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\nwritten: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    sys.exit(main())
