"""Does `docker kill -s KILL` lose the appendfsync-everysec tail, and does the
container come back? Both are premises of the E1 fault; neither is assumed."""
import asyncio, subprocess, time, sys
from redis.asyncio import Redis

URL = "redis://127.0.0.1:6381/15"
CONTAINER = "aep-phase2-redis72"

async def main():
    r = Redis.from_url(URL, decode_responses=True)
    await r.ping()
    # A key written and NOT waited on: everysec means it sits in the AOF buffer.
    t0 = time.monotonic()
    await r.set("aep:probe:tail", "written-then-killed", ex=600)
    t_set = time.monotonic()
    proc = subprocess.run(["docker", "kill", "-s", "KILL", CONTAINER],
                          capture_output=True, text=True)
    t_kill = time.monotonic()
    print(f"set->kill_returned {1000*(t_kill-t_set):.0f} ms   rc={proc.returncode} "
          f"{proc.stdout.strip()!r} {proc.stderr.strip()!r}")
    try:
        await r.aclose()
    except Exception:
        pass

    # Wait for the restart policy to bring it back.
    back = None
    for _ in range(600):
        try:
            r2 = Redis.from_url(URL, decode_responses=True, socket_connect_timeout=0.5)
            if await r2.ping():
                back = time.monotonic()
                break
        except Exception:
            pass
        finally:
            try:
                await r2.aclose()
            except Exception:
                pass
        await asyncio.sleep(0.1)
    if back is None:
        print("NEVER CAME BACK"); return 1
    print(f"restart->ready {1000*(back-t_kill):.0f} ms after kill returned")

    r3 = Redis.from_url(URL, decode_responses=True)
    value = await r3.get("aep:probe:tail")
    info = await r3.info("persistence")
    print(f"probe after restart: {value!r}  (None == the tail was lost)")
    print(f"aof_enabled={info.get('aof_enabled')} loading={info.get('loading')} "
          f"aof_last_write_status={info.get('aof_last_write_status')}")
    uptime = (await r3.info("server")).get("uptime_in_seconds")
    print(f"uptime_in_seconds={uptime} (small == really restarted)")
    await r3.aclose()
    return 0

sys.exit(asyncio.run(main()))
