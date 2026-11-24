# WS-4: instrumented diagnostic re-run

**Diagnose only. Two runs, not sixty. Nothing collected, nothing fixed.**

Output went to `/var/tmp/ws4-diagnostic-2026-09-07`, deliberately **outside**
`/root/aep-phase14/`, so it cannot later be read as a collection.

**Headline: the abort did not reproduce.** Both runs collected. The evidence
nonetheless settles several candidates on the collection's own container, and
identifies one race directly observed in the sampling.

---

## 0. Correction to the previous diagnosis

The previous pass read `RestartCount`, `OOMKilled`, `ExitCode` and `State.Error`
from the container created at **08:05:42** — four seconds *after* the collection
ended, and a different container from the one the collection ran on. **Those rows
do not rule out what they were used to rule out.** They described a replacement.

`dmesg` and disk-free are host-level, not per-container, and **still stand**: no
I/O errors, no ext4 errors, 949G free.

This pass re-establishes the per-container facts on a container that actually ran
the workload.

## 1. What was captured

| file | contents |
|---|---|
| `docker-events.log` | streamed from **before** provisioning through the abort window |
| `redis-logs.log` | `docker logs -f` teed, keyed to the container **id** so it outlives the container |
| `inspect-after-up.json` | `docker inspect` immediately after bring-up |
| `inspect-after-run1.json` | `docker inspect` immediately after the runs |
| `marker-samples.log` | `EXISTS aep:test-instance-marker` on db 15, **1 Hz**, from before the marker is set through the runs |

## 2. The measurement: the marker over time

```
09:12:57  exists=1  container=b140c5d1643c     <- old container, marker durable in redis-data
09:12:58  exists=1  container=b140c5d1643c
09:12:59  exists=1  container=b140c5d1643c
09:13:00  Error: container b140c5d1643c... is not running   container=32222905e73f
09:13:01  exists=0  container=32222905e73f     <- NEW container, marker ABSENT
09:13:02  exists=0  container=32222905e73f
09:13:04  exists=1  container=32222905e73f     <- up_write_loss.py sets it
09:13:05 … 09:14:32  exists=1  (unbroken, through both runs)
```

**The marker was present for the entire run window.** It never dropped once set.

## 3. What `docker events` shows at 09:13:00

```
1788772380 container create  b140c5d1643c_aep-phase2-redis72
1788772380 container kill    aep-phase2-redis72
1788772380 container stop    aep-phase2-redis72
1788772380 container die     aep-phase2-redis72
1788772380 container destroy aep-phase2-redis72
1788772381 container start   aep-phase2-redis72
```

This is Compose's **recreate**, triggered by `up_write_loss.py`'s
`docker compose -f base -f override up -d --wait`, because `/data` changes from
the named volume to a bind. **The container is destroyed and replaced**, and the
replacement starts on a device whose AOF is empty — hence `exists=0` at 09:13:01.

## 4. Candidates, on the collection's own container this time

| candidate | evidence | verdict |
|---|---|---|
| **Silent `/data` revert to `redis-data`** | `/data` is `bind /var/tmp/aep-ws4/mnt/redis` in **both** captures, before and after the runs | **excluded** |
| **Container replaced between bring-up and run 1** | same id `32222905e73f` at both captures | **excluded for this run** |
| **A restart during the runs** | `FinishedAt: 0001-01-01T00:00:00Z` (never finished), `RestartCount 0`, `ExitCode 0`, `State.Error` empty | **excluded** |
| **Docker's restart policy** | `RestartCount 0` on the container that ran the workload | **excluded** |
| **Marker never set on the instance the runner reaches** | `exists=1` continuously from 09:13:04 through 09:14:32 | **excluded for this run** |
| **Marker set and then lost** | no `exists=0` sample after 09:13:02 | **excluded for this run** |

## 5. The race the sampling caught

At **09:13:00** the sampler's own `docker exec` failed:

```
Error response from daemon: container b140c5d1643c... is not running
```

It addressed the container by **name** and reached the *old* container mid-destroy.
`up_write_loss.py:224` sets the marker the same way — `docker exec CONTAINER
redis-cli`, by name, not by id.

**This is a real, observed race**, and it is the strongest surviving candidate
for the original failure: a `docker exec` by name issued while Compose is
replacing the container can land on the container about to be destroyed. The
marker would then be set on a container that ceases to exist seconds later, and
`up_write_loss.py` would still print `set (rule 9)` — because, as established
last pass, it checks only `redis-cli`'s exit code and never reads back.

In *this* run the race did not bite: `--wait` returned before the marker was set,
so the exec reached the replacement.

**It is a candidate, not a demonstration.** I did not reproduce the failure, so I
cannot show that this is what happened on 2026-09-07 at 08:00.

## 6. What would confirm it

Not run here:

* set the marker by **container id** captured after `--wait` returns, not by
  name, and read it back through the runner's own client
  (`Redis.from_url(redis_url)`), then re-check after a short delay — the
  read-back that `docs/26` rule 13 requires and that `up_write_loss.py` lacks;
* repeat bring-up several times with the sampler running, to see how often the
  exec lands on a dying container.

Both are fixes or repetitions, and this pass was diagnosis.

## 7. Teardown, verified per R8

Torn down **after** the evidence was captured and inspected, base compose alone,
never `-v`:

```
dmsetup ls   -> 0 mappings
losetup -a   -> 0 loops
dmsetup info -> device absent
/data        -> volume …/aep-phase2_redis-data/_data
```

## 8. Status

The write-loss cell is **still not collected**, and this pass did not attempt it.
Two runs collected in a diagnostic root that is deliberately outside the phase
tree; they are not data and are not committed.
