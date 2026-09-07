# WS-4: why did Redis restart during the 2026-09-07 collection?

**Diagnosis only. Nothing was changed, fixed or collected.**

**Headline: the previous report's causal claim was wrong.** The restart did not
happen at collection start, and the missing marker is not downstream of it. The
marker was already absent ~3 seconds after launch, before any restart occurred.

---

## 1. The timeline, from artefact mtimes and the container's own log

| time (UTC) | event | source |
|---|---|---|
| 07:58:53 | `verify_measurement_host.py` writes `host.json` | mtime |
| ~07:59 | provision + `up_write_loss.py`; **marker set and read back** | console |
| **08:00:07** | collection launched | driver log |
| ~08:00:10 | **run 1 aborts: marker not advertised** | progress file |
| 08:05:38 | collection ends, 60/60 failed | mtimes |
| **08:05:42.714** | *current* container starts | `docker logs` |
| 08:05:58.590 | `Received SIGTERM` → `User requested shutdown...` | `docker logs` |
| 08:06:05 / 08:06:20 | start / SIGTERM again | `docker logs` |
| 08:19:11 / 08:20:03 | start / SIGTERM (teardown) | `docker logs` |

**The 232-second uptime cited in the previous report was measured after the
collection ended.** Counting back from that measurement lands at ≈08:05:38 — the
collection's **end**, not its start. The restart it named was my own
kill-and-teardown activity, not a fault during the run.

## 2. Candidates ruled OUT, with the evidence

| candidate | evidence | verdict |
|---|---|---|
| **Docker's `restart: unless-stopped` policy** | `RestartCount = 0` | **ruled out** — the policy never fired |
| **OOM kill** | `OOMKilled = false` | **ruled out** |
| **A crash** | `ExitCode = 0`, `State.Error` empty | **ruled out** — every exit was clean |
| **Device full** | `df /var/tmp` → 949G free, 1% used | **ruled out** |
| **Device or filesystem fault** | `dmesg`: clean `EXT4-fs (dm-0)` mount/unmount pairs, **zero** I/O errors, ext4 errors or writeback failures | **ruled out** |

## 3. What the log positively shows

Every shutdown in the visible window is the same pair:

```
1:signal-handler (…) Received SIGTERM scheduling shutdown...
1:M … * User requested shutdown...
```

**SIGTERM, not a fault.** That is `docker stop` / compose lifecycle — a
deliberate stop, consistent with `RestartCount = 0` and `ExitCode = 0`. Nothing
in the record shows Redis dying of anything.

## 4. Whether this is the container `up_write_loss.py` created — it is not

The user's question separates two faults, and the evidence answers it:

* current container `Created = 2026-09-07T08:05:42Z`, **four seconds after the
  collection ended**;
* its `/data` is `volume …/aep-phase2_redis-data/_data`, whereas the collection
  ran with a **bind** to `/var/tmp/aep-ws4/mnt/redis`;
* its log opens by loading `appendonly.aof.2.base.rdb` with `RDB age 340408
  seconds` (≈3.9 days) and `keys loaded: 2` — the *old volume's* data, not a
  device provisioned minutes earlier.

**This is a recreated container, not the one the collection ran against.** The
collection's container was removed — by my own teardown — and its log went with
it. That log is what would have shown the state at 08:00:10.

## 5. The `/data` revert candidate — not decidable from what survives

`up_write_loss.py` refuses at bring-up and nothing re-checks at run time, so a
silent revert to `redis-data` would look exactly like what was observed: an
instance with no marker and an old AOF.

The current container **is** on the volume, and it was created 4 s after the
collection ended — but that creation is explained by the teardown, so it is not
evidence that a revert happened *during* the collection. I cannot separate the
two from surviving artefacts.

## 6. What this leaves undecided, and what would settle it

**Undecided:** why the marker was absent ~3 seconds after `up_write_loss.py` set
it and read it back. The container that held it no longer exists.

**What would settle it** — a re-run instrumented to survive its own teardown:

1. `docker events --format '{{.Time}} {{.Action}} {{.Actor.Attributes.name}}' > events.log &` **before** provisioning, left running across the whole window. This records every create/start/stop/die/destroy with a timestamp, and is the single missing piece.
2. `docker inspect` captured to a file **immediately before launch** and **immediately after run 1**, so the container id and `/data` mount at both instants are recorded rather than inferred.
3. `docker logs -f` on the container id, teed to a file, so the log survives the container.
4. **Do not tear down before inspecting.** This diagnosis is limited precisely because the teardown ran first.
5. `redis-cli -n 15 EXISTS aep:test-instance-marker` sampled every second between bring-up and run 1, which brackets the disappearance to a second.

## 7. Correction to `phase-report-14-write-loss-not-collected-2026-09-07.md`

That report's §3 states *"Redis restarted at collection start"* and builds the
finding on it. **The restart was at the collection's end.** The marker was
missing from run 1, ~3 seconds after launch and ~5 minutes before the restart, so
the restart cannot be its cause.

The report's other statements stand: the marker was set and confirmed; it was
absent at run 1; no run reached the fault; nothing there is a measurement. Only
the causal claim is withdrawn — and §3's own "what is NOT established" paragraph
already said the restart's cause was unidentified, which was right for a reason
weaker than it gave.

This file is the correction; the report is left as written, per the practice of
recording corrections alongside rather than editing claims.
