# Phase 14 / WS-4 — the write-loss cell was not collected

**2026-09-04. No data. The collection was attempted and stopped, and this report
is the finding.**

Rule 12: *"If it finds a defect outside scope, it records it in the report as a
finding and stops."* That is what happened.

---

## 1. What was asked

Collect the write-loss cell exactly as pre-registered at `d8b2ca5` — 60 runs,
30 × 10, both arms, `ledger_postings` only, under `REGIME_WRITE_LOSS_PREACK`,
into a new dated directory. Rule 4 first. Nothing else.

## 2. What was done

**Rule 4 was satisfied before anything else.** `prompts/phase-14-write-loss.md`
records all six issued prompts verbatim, committed as `a207dc4` before any data
commit. The pre-registration at `d8b2ca5` satisfies rule 5 and is not a
substitute for rule 4.

**Preflight passed.** `scripts/verify_measurement_host.py` exits 0 and the pinned
Redis digest matches. The device provisioned and its §4 self-test passed, with
both table lines recorded:

```
pass: 0 1048576 flakey 7:0 0 1 0 2 error_reads error_writes
drop: 0 1048576 flakey 7:0 0 0 1 1 drop_writes
```

Redis came up with `/data` bound to `/var/tmp/aep-ws4/mnt/redis`, backed by
`/dev/mapper/aep-ws4-flakey`.

**Four launches, none producing a measurement.** All are voided under
`/root/aep-phase14/VOIDED/` with reason files. Three failed for environmental or
operator reasons that were fixed; the fourth found the blocker.

## 3. The blocker — two gaps in the instrument

### 3.1 The post-fault path cannot accept a fault that does not kill Redis

`experiments/harness/runner.py:541` calls `restart_after_hard_kill`
unconditionally whenever `config.redis_kill_point` is set. That function reads
`uptime_in_seconds` and refuses any run in which the server did not die.

Under write loss Redis is **deliberately not killed** — the device stops
accepting writes while the server keeps running and keeps serving reads. So the
check can never pass, and every run aborted:

```
FaultInjectionError: the hard kill did not land: Redis reports
uptime_in_seconds=311, so it is the same server process the run started with
and no infrastructure fault was injected
```

**The guard is correct and the instrument is incomplete.** The guard exists
because a kill that silently fails to land is the exact contamination Phase 8.4
found; it simply encodes an assumption — *the fault kills Redis* — that this
fault class breaks.

**The injector itself works.** From the first run's own event log:

```
event: redis_kill_issued   mechanism: write-loss   issued: True   armed: True
device: aep-ws4-flakey     command_ms: 25
table_after: 0 1048576 flakey 7:0 0 0 1 1 drop_writes
```

So the fault armed, on the right device, in 25 ms. Only what happens *after* it
is wrong.

### 3.2 Nothing restores the device between runs

Visible in the same evidence: `table_before` on the **first** run already reads
`drop_writes`, and the device was still dropping when the collection stopped.
`arm_drop_writes` has no counterpart that returns the table to pass mode, and
the harness calls nothing equivalent to `start_redis`.

Consequence: every run after the first would begin with the fault **already
delivered**, so its pre-fault portion would also run under write loss. The fault
is pre-registered to land at the intent CAS, not before the run begins. Even
with §3.1 fixed, the cell would measure something other than what it declares.

**This is the more dangerous of the two**, because it would not abort. It would
produce runs that complete and look like data.

## 4. Why this was not fixed

The fix to §3.1 changes `runner.py`'s shared post-fault path, which every one of
the six frozen regimes runs through. That is a change to the instrument all
existing results were collected with, and it is not "collect WS-4, nothing else."
§3.2 needs a restore step and a decision about where it belongs.

Both are recorded here rather than attempted.

## 5. Per-run cost actually observed

Recorded as asked, rather than back-solved from the estimator — and bounded,
because no run completed:

```
runs that reached the fault: 5
wall_seconds: n=5  min=30.1  median=47.9  max=56.0
```

**These are runs that aborted at the post-fault guard**, so this is the cost of
reaching the fault, not the cost of a completed run. A completed run also carries
the remaining executions, the settle and the recovery pass. The matrix-plan
estimator predicts 35.7 s/run for this shape; the observed 47.9 s median to reach
the fault alone already exceeds it, which is consistent with the under-prediction
seen for `pause-then-kill` and with this regime running ten executions per run
rather than one. **No estimator constant was edited.**

## 6. The three earlier voids

Recorded because they are operator error, and because a reader of the VOIDED
tree should not mistake them for instrument defects.

1. **No `aep:test-instance-marker`.** `up_write_loss.py` brings Redis up on a
   freshly provisioned device, which is empty, so the marker that lived in the
   `redis-data` volume was absent. The harness refused every run — correctly. It
   is now set as part of the reset, but **`up_write_loss.py` should set it** and
   does not.
2. **A stale mock-API provider.** Recovering from (1) with `kill -9` orphaned the
   provider on port 8099; every later run refused on a digest mismatch.
3. **A void that did not happen.** The command intended to move the failed tree
   used an inline shell variable, and the `wsl.exe` bridge strips `$`, so the
   `mv` silently did nothing and a further attempt appended to the same progress
   file. This is why one voided tree holds more rows than the regime plans runs.

## 7. Host state

Restored and verified, not assumed:

* the flakey device was returned to pass mode, torn down, and no dm mappings or
  loop devices remain;
* the stack is back up on `compose.phase2.yml` **alone** — never with `-v` —
  and `/data` is the named volume again;
* `aep-phase2_redis-data` is the same volume (`created 2026-09-03T14:28:18`) and
  its tree checksum is **unchanged at `5f2e374ee78a43dbc9a4753907d20358`**,
  before and after.

No frozen result was modified. The test suite was not run against the Redis being
collected on.

## 8. What is not done

* **The cell is not collected.** No protocol outcome under write loss exists.
* **Nothing was analysed**, no verdict written, and the paper is untouched.
* §VIII-A(b)'s *"we have not done it"* sentence stands, and remains true.
* The pre-registration at `d8b2ca5` stands unmodified and unused. It is still the
  prediction for this cell whenever the instrument can deliver it.

---

## 9. Correction (added 2026-09-04, after §3.2 was written)

**§3.2 above is left exactly as written.** This section is added beside it
rather than editing it, so the record shows both what was claimed and what the
evidence supports.

### What §3.2 says

> `table_before` on the **first** run already reads `drop_writes` […]
> `arm_drop_writes` has no counterpart that returns the table to pass mode

### What the evidence actually shows

The attribution — **defect 2, the missing inverse** — is correct. The
description of the evidence was loose in two ways.

All twelve arming events across the voided trees were examined in `wall_ms`
order. **The first arming ever recorded saw `table_before` in PASS mode:**

```
arming #1  (VOID-marker-and-stale-provider)  ...-r19
    table_before: 0 1048576 flakey 7:0 0 1 0 2 error_reads error_writes
    table_after : 0 1048576 flakey 7:0 0 0 1 1 drop_writes
arming #2  (same tree)                       ...-r0
    table_before: 0 1048576 flakey 7:0 0 0 1 1 drop_writes
```

So:

1. **Provisioning restored correctly.** The device was handed over in pass mode,
   and the first run to arm found it that way. §3.2's phrasing invited the
   reading that provisioning left it dropping; it did not.
2. **"The first run" was not the first run.** The `r0` §3.2 cites is the first
   run of the *last* voided tree. That tree's device arrived already dropping
   from the tree before it. The genuinely first arming, in an earlier tree, was
   clean.

### What it means for contamination

**In the voided trees, run 1 is contaminated too — not only the runs after it.**
The device was already dropping before `r0` began, so `r0`'s pre-fault portion
also ran under write loss. §3.2 did not say this either way and it should have.

**In a clean single collection the picture differs**: provisioning hands over a
device in pass mode, run 1 begins clean and only runs 2..N inherit the previous
run's arming. The observed pattern is worse than the general case because
several collections ran back-to-back against one device.

Both cases are now prevented: the per-run restore returns the device to pass
mode before each run arms, and the abort in `drop_writes_on_device` refuses any
run that still finds it dropping.
