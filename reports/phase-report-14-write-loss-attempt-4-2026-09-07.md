# Phase 14 / WS-4 — attempt 4: not collected, voided under R10

**2026-09-07. No data.** 47 runs, all failed, voided on the run count and the
abort reason alone. No outcome was read.

---

## 1. Obligations discharged before any data commit

* **Rule 4** — prompts 12–17 appended verbatim to
  `prompts/phase-14-write-loss.md`, with four corrections recorded alongside
  (commit `e392ea0`).
* **The cut condition** — §10 of
  `phase-report-14-write-loss-blocked-2026-09-04.md`, written in the same commit,
  while no write-loss data existed.

## 2. Preflight

Host verified (exit 0, digest matches). Device provisioned, self-test **PASS**
with all three table lines. Redis up with `/data` bound to the flakey device, and
the marker **set by container id and read back through
`Redis.from_url(redis://127.0.0.1:6381/15)`** — the runner's own path.

Container: `d71327c1b70a`.

## 3. What happened

All runs aborted:

```
RunAborted: Redis ... does not advertise 'aep:test-instance-marker'
```

47 runs recorded before the collection was stopped. Per the instruction, this was
voided **on the run count and abort reason alone**, before any outcome was
looked at.

## 4. The cause: R10, on the record

R8a captures were taken **before** anything was torn down. From
`inspect-at-failure.json` and `logs-at-failure.log`, on container
`d71327c1b70a` — the same container the marker was read back from:

```
Created    : 09:31:07.725Z
FinishedAt : 09:31:29.219Z      <- it STOPPED
StartedAt  : 09:31:54.867Z      <- started again, SAME id
RestartCount : 0    ExitCode : 0    OOMKilled : false
/data      : bind /var/tmp/aep-ws4/mnt/redis      (no revert)

09:31:08.444  Ready to accept connections tcp
09:31:29      Received SIGTERM ... / User requested shutdown...
09:31:55.157  Ready to accept connections tcp
```

**This is R10 exactly.** The marker lived only in RAM because this regime's Redis
runs on a freshly provisioned device with an empty AOF. The container stopped and
started; it came back without the marker; every run then aborted.

**`cf12884`'s read-back is not the problem and did its job.** The marker was
genuinely present and genuinely visible to the runner's own client at bring-up.
The failure is downstream of that, in a restart — which is what R10 predicted in
writing before this attempt ran.

**The class the read-back closes is now excluded as the cause**, which is the
outcome that prompt 15 said would be worth more than another reproduction
attempt. It was.

## 5. What is not established

**What sent the SIGTERM at 09:31:29.** `RestartCount 0` excludes Docker's restart
policy. `ExitCode 0` and `OOMKilled false` exclude a crash and OOM. The stop was
deliberate and its origin is unidentified. My 5-second sampler began at 09:31:56,
*after* the restart, so it recorded `exists=0` from its first sample — it
confirms the marker was absent throughout, but does not bracket the loss.

**That is a defect in my instrumentation, not in the evidence.** The sampler
should have been started before `up_write_loss.py`, as it was in the 2026-09-07
diagnostic. Started late, it could not see the transition it existed to catch.

## 6. Per-run cost observed

```
runs : 47
wall_seconds : n=47  min=4.93  median=5.37  max=18.54
```

**The cost of aborting at the marker check, not of a run.** No run executed a
workload or armed a fault. The estimator's 64.5 s/run for this shape remains
untested. **No estimator constant was edited**; this measures a refusal path.

## 7. R9

Not applicable. The test suite was not run — rule 9 forbids running it against
the Redis a matrix is collecting on. No evidence either way.

## 8. Teardown

Per R8b: base compose file **first** to release the bind, then the device.
Verified per R8 rather than trusting the exit code:

```
dmsetup ls -> 0    losetup -a -> 0    /data -> volume …/aep-phase2_redis-data/_data
```

R8a captures are preserved inside the voided tree at `R8a-capture/`.

## 9. Against the cut condition

§10 fixes the cut at **attempts 5 and 6 also failing**. This is attempt 4 and the
first failure after the instrument was completed. **WS-4 is not cut**, and two
attempts remain — but the next one must be aimed at R10, because a fifth attempt
that does not address the marker's durability would be spending one of two
remaining attempts on a failure mode already understood and written down.

## 10. What is not done

The cell is not collected. Nothing analysed, `analyse_write_loss.py` not run, no
verdict, paper untouched. §VIII-A(b) stands and remains true. `d8b2ca5` stands
unmodified and unused.
