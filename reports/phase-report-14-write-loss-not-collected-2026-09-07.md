# Phase 14 / WS-4 — the write-loss cell was not collected (second attempt)

**2026-09-07. No data.** The collection was launched as pre-registered, every run
refused before the fault was armed, and it is voided. This report is the finding.

Rule 12: *a defect found outside scope is recorded and the work stops.*

---

## 1. What was asked, and what was done first

Collect exactly what `d8b2ca5` pre-registers — 60 runs, 30 × 10, both arms,
`ledger_postings` only, under `REGIME_WRITE_LOSS_PREACK`, into a new dated
directory.

**Rule 4 was satisfied before any data commit.** `prompts/phase-14-write-loss.md`
gained prompts 7–11 verbatim, committed as `ed1c7ff`, with three corrections
recorded alongside rather than applied silently (a cited rule 13 that did not
exist, a false premise about WS-1a attribution, and a claim in the previous
phase-14 report that the evidence did not support).

**Preflight passed.** `verify_measurement_host.py` exit 0, pinned digest matches,
Docker 29.4.3, kernel 6.6.114.1. The device provisioned with its §4 self-test
passing and all three table lines recorded:

```
pass, before arming : 0 1048576 flakey 7:0 0 1 0 2 error_reads error_writes
drop, armed         : 0 1048576 flakey 7:0 0 0 1 1 drop_writes
pass, RESTORED      : 0 1048576 flakey 7:0 0 1 0 2 error_reads error_writes
```

Redis came up with `/data` bound to the flakey device, and
`up_write_loss.py` set `aep:test-instance-marker` and read it back.

## 2. What happened

Launched detached with `setsid nohup`. **All 60 runs failed**, every one with:

```
RunAborted: Redis at 'redis://127.0.0.1:6381/15' does not advertise
'aep:test-instance-marker'.
```

**No run directory exists in the tree.** The runs aborted at startup, before any
directory was created, so **the write-loss fault never fired** and nothing in the
tree is a measurement.

## 3. The finding: the marker does not survive to the first run

Measured immediately after stopping:

```
redis-cli -n 15 GET aep:test-instance-marker   -> (empty)
redis-cli -n 15 DBSIZE                         -> 0
redis-cli INFO server | uptime_in_seconds      -> 232
appendonly.aof.1.incr.aof on the device        -> 0 bytes
```

232 s is approximately the collection's own duration, so **Redis restarted at
collection start**. Its AOF lives on the freshly provisioned dm-flakey device,
where the incremental file is empty, so the restart brought the instance back
with nothing — and the marker, set seconds earlier and confirmed, was gone before
run 1.

**The shape of the problem.** Rule 9 requires a Redis to assert it is disposable
before the harness will run destructive cleanup against it. Under this regime the
instance is created fresh on a device that starts empty, so the assertion must be
made *after* provisioning — and it is — but nothing makes it survive a restart on
a device whose AOF is empty.

### What is NOT established

**Why Redis restarted.** The post-fault guard is conditional as of `4d0fc84` and
should not fire for `write-loss`; no run reached the fault; the device was in pass
mode throughout; and `dm-flakey` in pass mode drops nothing. The restart is real —
uptime and the container's own age agree — and its cause is **not identified**.

I am recording that as an open question rather than naming a cause I have not
demonstrated. Candidates not tested: the compose healthcheck plus
`restart: unless-stopped`, and some harness-side restart at collection start.

## 4. Per-run cost observed

```
runs recorded : 60
wall_seconds  : n=60  min=3.52  median=3.91  max=19.28
```

**This is the cost of aborting at the marker check, not the cost of a run.** No
run executed a workload, armed a fault, or settled. The matrix-plan estimator
predicted 3 870 s for 60 runs — **64.5 s/run** — and that prediction remains
untested by this attempt.

**No estimator constant was edited**, and none should be from this data: it
measures a refusal path.

## 5. R9 — not applicable, and why

R9's flake did not recur, because **the test suite was not run at all** during
this pass. Rule 9 forbids running it against a Redis a matrix is collecting on,
and the collection held the only Redis. So this attempt provides no evidence
about R9 either way, which is the correct outcome rather than a gap.

## 6. Teardown, verified per R8

Torn down with the base compose file alone, never `-v`, and the device checked
rather than the exit code trusted:

```
dmsetup ls    -> 0 mappings
losetup -a    -> 0 loops
dmsetup info  -> device absent
/data         -> volume .../aep-phase2_redis-data/_data -> /data
```

R8 exists because a previous teardown reported success while the mapping
survived. This one was verified on all three checks and needed no forcing.

## 7. A dating error in this workstream's earlier artifacts

**Today is 2026-09-07.** Several WS-4 artifacts are dated `2026-09-04`:
`reports/phase-report-ws4-prediction-2026-09-04.md`,
`reports/phase-report-14-write-loss-blocked-2026-09-04.md`,
`reports/raw/ws4-fault-delivery-assessment.md`, and the `docs/25` R9 entry.

I introduced those dates by carrying forward Phase 13's, and did not check the
host clock until this pass named a directory. The **content and commit order are
unaffected** — git's timestamps are authoritative and correct — but the filenames
and in-file dates are wrong by three days. Not corrected here: renaming
pre-registration and report files is not "collect WS-4, nothing else", and the
pre-registration in particular is cited by commit in several places.

## 8. What is not done

* **The cell is not collected.** No protocol outcome under write loss exists.
* **`analyse_write_loss.py` was not run**, as instructed. The run count and the
  abort reason were read; no applied-effect number was. That property is intact,
  so a decision to void this tree — already taken — is uncontaminated by
  outcomes, and so would be any future one.
* Nothing analysed, no verdict, paper untouched. §VIII-A(b)'s *"we have not done
  it"* stands and remains true.
* `d8b2ca5` stands unmodified and unused.

## 9. What would unblock it

Not attempted, recorded for the next prompt:

1. **Establish why Redis restarts at collection start.** Until that is known, any
   marker fix is a guess at a symptom.
2. **Make the marker survive.** Either seed it during provisioning so it is in the
   AOF base before the collection begins, or set it after whatever restarts
   Redis, or make the harness's guard accept an out-of-band assertion for a
   regime whose instance is provisioned per session.

Both are instrument work, and neither is this prompt.
