"""Can a phase-aligned `docker kill -s KILL` be made to land inside the
appendfsync-everysec window reliably? Six trials, reported as they come out."""
import asyncio, subprocess, threading, time, sys
from redis.asyncio import Redis

URL = "redis://127.0.0.1:6381/15"
CONTAINER = "aep-phase2-redis72"
TRIALS = 6

async def ready(timeout=60.0):
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        r = Redis.from_url(URL, decode_responses=True, socket_connect_timeout=0.4)
        try:
            if await r.ping():
                return time.monotonic() - started
        except Exception:
            pass
        finally:
            try: await r.aclose()
            except Exception: pass
        await asyncio.sleep(0.05)
    raise RuntimeError("redis never became ready")

async def trial(n):
    r = Redis.from_url(URL, decode_responses=True)
    async with r.client() as conn:
        # Phase-align: a write put through WAITAOF means an fsync has just
        # completed, so the next everysec fsync is ~1s away.
        await conn.set("aep:probe:align", str(n))
        t_align0 = time.monotonic()
        acked = await conn.execute_command("WAITAOF", 1, 0, 2000)
        t_align = time.monotonic()
        # The write under test. Deliberately NOT waited on.
        await conn.set("aep:probe:tail", f"trial-{n}", ex=600)
        t_write = time.monotonic()

    killed_at = {}
    def fire():
        t0 = time.monotonic()
        subprocess.run(["docker", "kill", "-s", "KILL", CONTAINER],
                       capture_output=True, text=True)
        killed_at["returned"] = time.monotonic() - t0
    thread = threading.Thread(target=fire); thread.start()

    # Observe when the server actually stops answering: that brackets delivery.
    death = None
    while time.monotonic() - t_write < 20:
        try:
            probe = Redis.from_url(URL, decode_responses=True, socket_connect_timeout=0.3)
            await probe.ping()
            await probe.aclose()
        except Exception:
            death = time.monotonic(); break
        await asyncio.sleep(0.02)
    thread.join()
    try: await r.aclose()
    except Exception: pass

    subprocess.run(["docker", "start", CONTAINER], capture_output=True, text=True)
    await ready()
    r2 = Redis.from_url(URL, decode_responses=True)
    survived = await r2.get("aep:probe:tail")
    uptime = int((await r2.info("server"))["uptime_in_seconds"])
    await r2.aclose()

    print(f"trial {n}: waitaof_ack={acked} align={1000*(t_align-t_align0):.0f}ms  "
          f"write->death={1000*(death-t_write):.0f}ms  "
          f"kill_cli={1000*killed_at['returned']:.0f}ms  uptime_after={uptime}s  "
          f"tail={'LOST' if survived is None else 'SURVIVED'}", flush=True)
    return survived is None

async def main():
    lost = 0
    for n in range(TRIALS):
        lost += await trial(n)
    print(f"\ntail lost in {lost}/{TRIALS} trials")
    return 0

sys.exit(asyncio.run(main()))
