# WS-4 attempt 5, Part 2: bounding the SIGTERM

One cycle, as instructed. This bounds the SIGTERM; it does not establish its
origin, and the section below says plainly what remains open.

## What was run

Observers started **before** provisioning, so the whole bring-up is bracketed —
this is the ordering defect that made attempt 4's sampler useless (it started
after `up_write_loss.py` and recorded `exists=0` from its first sample,
confirming absence without ever witnessing the loss).

- `docker events` on the redis container, full lifecycle
- a 2 s marker sampler through `docker exec ... redis-cli -n 15 EXISTS`, also
  recording the container id so a recreate is visible as an id change
- container log, read afterwards for `SIGTERM` / shutdown / ready lines

Timeline of the deliberate actions: `T_provision=09:50:08`, `T_up=09:50:13`,
`T_restart=09:50:20` (mine), `T_done=09:50:31`.

## What the observers show

Lifecycle events, filtered to the redis container (healthcheck and sampler
`exec_*` events removed):

```
09:50:15  create    f0c7003affa5_aep-phase2-redis72
09:50:15  kill      aep-phase2-redis72
09:50:15  stop      aep-phase2-redis72
09:50:15  die       aep-phase2-redis72
09:50:15  destroy   aep-phase2-redis72
09:50:15  rename    aep-phase2-redis72
09:50:15  start     aep-phase2-redis72
09:50:20  kill      aep-phase2-redis72
09:50:20  stop      aep-phase2-redis72
09:50:21  die       aep-phase2-redis72
09:50:21  start     aep-phase2-redis72
09:50:21  restart   aep-phase2-redis72
```

Container log over the same window:

```
09:50:15.900 * Ready to accept connections tcp
1:signal-handler Received SIGTERM scheduling shutdown...
09:50:20.315 * User requested shutdown...
09:50:21.055 * Ready to accept connections tcp
```

## The bound

**Two lifecycle disruptions in the cycle, and both are accounted for.**

1. **09:50:15 — Compose's own recreate.** The `create`(temp name) → `kill` →
   `stop` → `die` → `destroy` → `rename` → `start` sequence is Compose's
   recreate signature: it is replacing the container because the override file
   changes `/data` from the named volume to a bind. It happens *inside*
   `up_write_loss.py`'s compose invocation (`T_up=09:50:13`), before the script
   returns. This is expected and is why bring-up reads the marker back at all.
2. **09:50:20 — my own `docker restart`.** `T_restart=09:50:20` is the
   verification step. The one SIGTERM in the log lands at the same second and is
   followed by `User requested shutdown`.

**There was no unexplained SIGTERM.** Attempt 4's SIGTERM is therefore *not* a
deterministic consequence of bring-up: an identical provision-and-up on the same
host, with observers watching, did not reproduce it.

The marker sampler shows no `1 → 0` transition across either disruption. The
container id changes once, at the 09:50:15 recreate, as expected.

## What remains unestablished

- **The origin of attempt 4's SIGTERM at 09:31:29.** It did not recur, so it is
  either intermittent or was caused by something not present in this cycle.
  Candidates the evidence does *not* rule out: an external agent on the host
  (Docker Desktop / WSL housekeeping), or a second Compose invocation racing the
  first. Nothing in this cycle distinguishes them.
- This is a **bound, not a diagnosis**, and per the instruction no second cycle
  was spent on it.

## Why the collection can proceed anyway

The reason this stops being a blocker is not that the SIGTERM was explained — it
was not. It is that `a994023` made the test-instance marker **durable**: it is
seeded into a real `appendonlydir` that the collection's server loads at start.
Re-verified immediately before this collection, on a freshly provisioned device,
through the runner's own `Redis.from_url` client: `EXISTS=1 db15=1` before a
`docker restart` and `EXISTS=1 db15=1` after it.

So a restart mid-collection — whatever sends it — no longer destroys the marker,
and R10's abort-every-remaining-run failure mode is closed by construction
rather than by having eliminated the restart.
