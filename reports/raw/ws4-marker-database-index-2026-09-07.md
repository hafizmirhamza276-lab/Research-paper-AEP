# WS-4: is the missing marker a database-index mismatch?

**Static diagnosis, read-only. No re-run, no collection, no fix.**

**Answer: no. The two routes address the same database (15). A mismatch is ruled
out, and the static route is exhausted.**

---

## 1. Which database each side uses, with the lines

**The write** — `scripts/up_write_loss.py:224`:

```python
marked = run("docker", "exec", CONTAINER, "redis-cli", "-n", "15",
             "SET", TEST_INSTANCE_MARKER, "1")
```

→ **db 15**, via `redis-cli -n 15` inside the container.

**The check** — `experiments/harness/runner.py:445`, then `:454`:

```python
redis_client = Redis.from_url(config.redis_url, decode_responses=True)
...
await assert_disposable_redis(redis_client, config.redis_url)
```

`Redis.from_url` takes the database from the URL path. The URL is passed through
unchanged: `run_matrix.py:1201` defaults to `redis://127.0.0.1:6381/15`,
`run_matrix.py:730` sets `redis_url=arguments.redis_url` on the plan, and the
launch script passed that same URL explicitly.

→ **db 15**.

The abort text at `runner.py:123` instructs `redis-cli -n 15`, which agrees with
both.

## 2. Demonstrated on a live instance, not inferred

One uniquely-named probe key, written by the *write* route and read by the
*check* route. The harness's own marker was not touched.

```
ROUTE A writes:  docker exec redis-cli -n 15 SET aep:ws4:db-index-probe 1  -> OK

ROUTE B reads:   Redis.from_url("redis://127.0.0.1:6381/15")
                 connection kwargs db : 15
                 EXISTS -> 1

contrast, db 0:  Redis.from_url("redis://127.0.0.1:6381/0")
                 connection kwargs db : 0
                 EXISTS -> 0

probe removed;   EXISTS now -> 0
```

A key written by route A is visible to route B and absent from db 0. **The two
routes are the same database. A database-index mismatch is ruled out.**

## 3. A correction to the question's premise

The question says *"`up_write_loss.py` did a read-back and the read-back
passed."* **It does not read back at all.** `up_write_loss.py:224-230`:

```python
marked = run("docker", "exec", CONTAINER, "redis-cli", "-n", "15",
             "SET", TEST_INSTANCE_MARKER, "1")
if marked.returncode != 0:
    ...
    return 1
print(f"{TEST_INSTANCE_MARKER}: set (rule 9)")
```

It checks the **exit code of `redis-cli`** and prints `set (rule 9)` on the
strength of it. No `GET`, no `EXISTS`.

The point in the question stands and is sharper than stated. A read-back against
the same endpoint as the write would confirm the write and not the agreement.
What is here is weaker again: it confirms that the command **ran**, not that a
key **exists**. `redis-cli` exits 0 for a SET it successfully delivered, which
says nothing about what a *different* client at a *different* address will
observe a moment later.

**That is a gate that cannot fail** in the sense of `docs/26` rule 13: the only
branch it can take is the one where `docker exec` itself failed.

## 4. An observation that bears on the next step

The probe run showed the marker **currently present** on db 15:

```
marker on db15 : 1
marker on db0  : 0
```

That is the `redis-data` volume's copy, durable in its AOF from an earlier set.
It explains why the frozen regimes never meet this problem: their Redis loads an
AOF that already contains the marker.

Under `write-loss` the instance runs on a **freshly provisioned device whose AOF
is empty**, so a marker set there exists in memory only. Any restart — for any
reason — loses it, and the instance comes back without it. That is a structural
difference between this regime and the six frozen ones, and it is worth carrying
into the next step whatever the eventual cause turns out to be.

It is **not** by itself the explanation: the previous diagnosis established the
marker was already absent at t+3 s, and no restart is visible in that window. But
the container that would have shown it was removed by the teardown.

## 5. The static route is exhausted

Both indices are 15, demonstrated. Nothing further can be settled by reading.

**The instrumented re-run is the next step**, and it must carry the measurement
that would have decided this either way:

> `redis-cli -n 15 EXISTS aep:test-instance-marker` sampled **every second**
> between bring-up and run 1, written to a file.

That brackets the disappearance to a second and distinguishes *never set on the
instance the runner reaches* from *set and then lost*. With `docker events`
streaming across the same window (§6 of the previous diagnosis), the pair is
decisive.

Neither is run here. This pass was read-only.
