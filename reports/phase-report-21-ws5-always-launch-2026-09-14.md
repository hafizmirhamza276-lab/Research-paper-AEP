# Phase 21 — WS-5.1: the `always` arm, launched

## Asked / Done

Asked: commit the prompt, prove the R16 guard covers this script on its failing
branch, pre-flight verified, launch 45 runs, do not analyse, freeze with no
temporal gap, verified teardown, scoped R15.

Done: all eight. **45 runs, 3 cells × 15, zero incomplete, zero void.** The arm
is collected, frozen and bound. Nothing was analysed.

One thing was changed mid-pass and is not cosmetic: the guard's non-empty-root
refusal was **hoisted above every side effect**, because step 2 found it firing
correctly but late.

---

## 1. Guard evidence — the refusal, for this script

| case | invocation | exit | expected |
|---|---|---|---|
| A | bare — the command its own header used to document | **2** | 2 |
| B | `AEP_FSYNC_RESULTS_ROOT=` (explicitly empty) | **2** | 2 |
| C | pointed at the frozen `experiments/results/fsync-always` | **3** | 3 |
| D | `aep_guarded_rm_results` on an unmarked root | **4** | 4 |
| D′ | same root, marker present | **0** | 0 |
| E | `aep_guarded_rm_results` on the real frozen root | **4** | 4 |

Execution is legitimate here and the phase-20 R13/R16 conflict does **not**
apply: this script forks nothing detached (`grep -nE 'nohup|setsid|&$|disown'`
→ no match), so its refusing branches can be run without launching anything.
That was checked before running it, not assumed.

### What step 2 found, and the fix

Case C refused with exit 3 — **after** `docker run` had started a real Redis on
the fixed name and port, after the `CONFIG GET` gate had passed, and after the
disposability marker had been `SET`. The refusal was correct and late.

Late is not good enough for this one. A second invocation racing the first over
one container name is the shape that destroyed data in phase 19. The check now
sits immediately after the root is resolved:

```
RESULTS_ROOT="${AEP_FSYNC_RESULTS_ROOT}"
aep_refuse_nonempty_results_root "${AEP_FSYNC_RESULTS_ROOT}" || exit $?
```

Re-run of case C after the hoist: exit 3, **and `docker ps -a` shows no
container was created**. The frozen root is intact throughout — both CSVs and
`RAW-RUNS-DESTROYED.md` still present after all six cases.

---

## 2. Pre-flight, verified

| check | result |
|---|---|
| `verify_measurement_host.py` | **exit 0**, `gates.passed = true`, `failures = []` |
| Redis image digest | `sha256:6aaf3f5e…1f44` — script, `compose.phase2.yml` and the locally present image all agree |
| clock | `within_tolerance = true`, wall−monotonic −4 µs over 2 s |
| ports | 6383, 8098, 8099 free; 6381 busy = the matrix Redis, which must stay up |
| `phase2-always.conf` | differs from `phase2.conf` in exactly one line: `appendfsync everysec` → `always` |
| target directory | absent before launch |

**Two things the first pre-flight got wrong, fixed rather than worked around.**

*`verify_measurement_host.py` exited 1 on `dmsetup targets does not contain
flakey`.* `dm-flakey` was on disk and not loaded. This arm is crash-free `p0`
and does not use it — but the honest way to satisfy a gate is to make its
condition true, not to argue the gate does not apply to you, so `modprobe
dm_flakey` was run and the target appeared. Re-run: exit 0.

*It also exited 1 on `suspend.declared = false`.* That is E5 working as designed:
the declaration is only accepted from the collection command's own environment.
Re-run with `AEP_HARNESS_SUSPEND_DISABLED=1` exported: `declared = true`.

### E5 — the policy read before the declaration was made

```
$ powercfg.exe /query SCHEME_CURRENT SUB_SLEEP
  GUID Alias: STANDBYIDLE      AC = 0x00000000   DC = 0x00000000
  GUID Alias: HIBERNATEIDLE    AC = 0x00000000   DC = 0x00000000
```

**The S0 residual, restated rather than referenced.** `powercfg /a` reports
*"Standby (S0 Low Power Idle) Network Connected"* as available on this host.
Timeouts of 0 remove **scheduled** sleep. They do not remove modern-standby
entry triggered by lid close or user action, and no query can rule that out —
a host that merely did not happen to suspend is indistinguishable from one that
cannot. `suspend_disabled_declared` is `true` on all 45 runs, and a declaration
is not a guarantee. That is the residual, unchanged and not narrowed by this
pass.

---

## 3. The launch, and the isolation it depended on

```
=== phase 21 launch 2026-09-14T12:46:09Z ===
root    : experiments/results/fsync-always-2026-09-14
runs    : 15 per cell
systems : AEP_FULL B3_INTENT_NO_BARRIER B0_NAIVE_RETRY
suspend : AEP_HARNESS_SUSPEND_DISABLED=1 (exported by this command)

--- verifying the server is actually running the policy under test ---
$ redis-cli CONFIG GET appendfsync
appendfsync = always
$ redis-cli CONFIG GET appendonly
yes
redis_version:7.2.5
run_id:7d57f363ade41f5233d0fd3bebafcd5f3c87944f
gate passed.

=== EXIT=0 2026-09-14T13:42:46Z ===
```

**56 minutes 37 seconds.** Predicted ~0.9 h.

### A second Redis, on its own port and its own volume

| | `aep-phase2-redis72` (matrix) | `aep-fsync-always` (this arm) |
|---|---|---|
| host port | 6381 | **6383** |
| volume | `aep-phase2_redis-data` | anonymous `38befa3d…` |
| config | `phase2.conf` | `phase2-always.conf` |
| `run_id` | `972bee16…` | `7d57f363…` |
| `appendfsync` | `everysec` | **`always`** |
| restart policy | `unless-stopped` | **`no`** |

**No `CONFIG SET` was issued anywhere.** The policy comes from the config file
at container start and is read back before measuring. The matrix Redis still
reports `everysec` after teardown — checked, not assumed. All 45 run-configs
record `redis_url = redis://127.0.0.1:6383/15`.

---

## 4. Counts and statuses only

**Nothing here is an outcome.** No median, no interval, no mixture test;
`power_analysis.py` was not run and `per-execution.csv` was not opened. The
script's own `analyze` step ran as part of collection — that is ordinary output
that `freeze_results.py` expects — and its side-by-side comparison was not read.

```
run directories                       45
  aep_full-none-payments-e5e5c7dc              15
  b3_intent_no_barrier-none-payments-85b7630d  15
  b0_naive_retry-none-payments-5e60d107        15

summary.json missing                   0
run-config.json missing                0
incomplete run directories             0
matrix-progress statuses               {'collected': 45}
VOID / non-collected                   0

suspend_disabled_declared              {True: 45}
settled (per run)                      {True: 45}
crash (point, probability)             {(None, 0.0): 45}     -- p0, crash-free
readback_keying                        {'CALLER_REFERENCE': 45}
redis url in configs                   {'redis://127.0.0.1:6383/15': 45}

config digests                         45 distinct across 45 runs
  summary.json / run-config.json agree in 45 of 45

executions                             450 (0 crashed)
settled=false runs                     0
```

**`settled=false`: none.** Had there been any they would be an observation here
and nothing more; classification belongs to the analysis pass, under amendment
3's already-fixed rule, outcome-independently.

**The 45 distinct digests are per-run, not drift.** Asked rather than assumed:
of the fields in `run-config.json`, only `run_id`, `seed`, `mock_api_config_path`
(which contains the run id) and `system` vary. **69 fields are constant across
all 45**, including `crash_point`, `crash_probability`, `endpoint`,
`readback_keying`, `redis_url`, `suspend_disabled_declared`, both Docker
versions, and `harness_version.commit = 972f05c`. The environment did not move
under the collection.

**A counting instrument that was wrong first.** The first pass looked for
`suspend_disabled_declared` in `summary.json` and reported **`{True: 0, false/absent: 45}`**
— which is exactly what a real E5 failure looks like. The key lives in
`run-config.json`. The guess was replaced by a search of both files before
anything was reported (`docs/25` R14). Same for `regime`, which reported `{}`
because there is no such key — the regime is `crash_point` / `crash_probability`.

---

## 5. Canonical tree location

```
/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/fsync-always-2026-09-14
filesystem: v9fs (drvfs), device D:\ 
```

**Inside this checkout.** Phase 20's third finding — that the `/root/aep*`
collection trees are unmonitored by anything in this repository — **does not
apply to this arm.** Its raw tree is in the repository's own working tree, its
`RAW-SHA256SUMS` is tracked, and `--check` runs against it from a clean clone.

That is a difference from the cell it extends: the frozen `fsync-always` was
collected into `/root/aep` in August, and this checkout has never held its raw
runs. The two cells are comparable in policy and seeds, and differ in custody.

---

## 6. Freeze, with no temporal gap

```
freeze_results.py  -> MANIFEST.md, MANIFEST.csv, SHA256SUMS (15 files)
                      completed runs 45, executions 450 (0 crashed), cells 3,
                      incomplete dirs 0
digest_results_tree.py -> RAW-SHA256SUMS   45 runs, 585 file lines
                      tree digest cb79054867ee05af8aa98d8cf85c26568443e4c01eb93e52cbdbae4c986cfd12
```

| event | time |
|---|---|
| last run finished | 2026-09-14T13:42:46Z |
| `RAW-SHA256SUMS` written | 2026-09-14T13:49:46Z |
| **gap** | **7 minutes** |

**This is the first collection in the project whose raw digest has no temporal
gap.** Every earlier one was digested days later (phase 20, nine roots), or
never — `fsync-always` had no raw manifest at all, which is why its deletion
looked total from inside the repository for several hours.

Both verify immediately: `sha256sum -c SHA256SUMS` all OK; `--check` reports
585 files, 0 missing, 0 added, 0 changed, tree digest matches.

The refusal path still works and was re-checked after the freeze: pointed at an
empty root the tool exits **3** rather than certifying `sha256(b"")`.

Tracked: `MANIFEST.md`, `MANIFEST.csv`, `SHA256SUMS`, `RAW-SHA256SUMS`, and five
analysis products. Not tracked: run directories, ledgers, logs, the figure PDF
and the seven `metric-*.csv`/`table-1.csv` files — matching what the WS-5 steps
track.

---

## 7. Teardown, verified

```
1. processes            none to kill; re-read after acting: clear
2. aep-fsync-always     already removed by the script's own EXIT trap
   its volume           38befa3d… removed BY NAME (see below)
3. ports                6383 free, 8098 free, 8099 free
   6381                 1 listener -- the matrix Redis, which must stay up
4. matrix stack         aep-phase2-redis72 + aep-phase2-toxiproxy, both healthy
   matrix appendfsync   everysec  -- unchanged, checked not assumed
5. dmsetup ls           No devices found
   losetup -a           only Docker Desktop's own iso loop
6. frozen tree          45 run dirs; SHA256SUMS 15/15 OK after teardown
```

**The volume was identified, not guessed.** During collection `docker inspect
aep-fsync-always` recorded its `/data` mount as
`/var/lib/docker/volumes/38befa3d…/_data`, and that volume's `CreatedAt` is
`2026-09-14T17:46:10+05:00` = `12:46:10Z`, matching the container's `StartedAt`
to the second. It was removed by name.

**47 dangling volumes remain and were deliberately left.** Two of them
(`17:41:55+05`, `17:42:20+05`) line up with the two containers my step-2 guard
probe started before the refusal was hoisted — I can infer that, not prove it,
because their containers are gone and nothing recorded the mapping. The other 45
predate this pass. **No `docker volume prune` was run**: it would take all 47,
including volumes whose purpose I cannot establish.

---

## 8. R15, scoped

```
test files referencing the changed script (found, not assumed):
    tests/test_results_root_guard.py
test_results_root_guard.py + test_digest_results_tree.py   33 passed
check_paper_numbers.py                                     33 passed, 0 failed
validate_citations.py                                      OK: 371 citations, 0 invalid
this arm: --check                       585 files, 0 missing, 0 added, 0 changed
this arm: sha256sum -c SHA256SUMS        15 OK
phase 20's nine pre-WS-5 digests         0 failing
zero .tex changed                        0
frozen roots touched (rule 2)            none
```

Scoped rather than full, as instructed. The full suite was **not** re-run; the
only behavioural change is the hoist in `fsync_always_benchmark.sh`, and the
module covering it was located by search rather than assumed. The paper was not
rebuilt: `build_paper.sh` pins no `SOURCE_DATE_EPOCH`, so byte-identity is not a
meaningful check — zero `.tex` is, and it holds.

---

## 9. Findings outside scope

1. **The run-configs name the wrong Redis container, and this is pre-existing.**
   Every one of the 45 records `redis_container = aep-phase2-redis72` and
   `environment.redis_storage_backing.name = aep-phase2_redis-data` — the
   **matrix** Redis and its volume — while `redis_url` correctly says 6383. A
   reader of these artefacts would conclude the runs used the matrix instance.
   The frozen 2026-08-07 `fsync-always` cell has the same `redis_container`
   value, so this is not new; what *is* new is that `redis_storage_backing` is
   now **populated** (it was `None` in August), so the artefact is more specific
   and more wrong. `redis_url` is the authoritative field. The harness captures
   the compose service's container regardless of where `--redis-url` points.
   Recorded, not fixed: fixing it means re-collecting.

2. **The Docker daemon restarted at least three times today** — 12:46:05,
   13:51:55 and 13:53:15 UTC — each time taking both `unless-stopped` containers
   down and back up together with `RestartCount = 0` and a clean exit. `dockerd`'s
   PID moved 276 → 240, which is a whole-distro restart rather than a service
   restart. It then held stable across three 60-second samples.

   **None of the three fell inside the collection window** (12:46:10–13:42:46Z),
   and that is demonstrable rather than hoped: `aep-fsync-always` was created
   with `RestartPolicy = no`, so a bounce would have left it dead and every
   remaining run would have failed — and 45/45 collected with zero failures.
   The fail-loud property is what makes the argument available at all. A
   long-running collection on this host is exposed to this; the WS-5 tier-1/2
   collection ran 13 hours through it and survived.

   This is *not* offered as an explanation for R12a's three earlier unexplained
   restarts. R12a's attribution was withdrawn once already. What is established
   is that on these three occasions the signature was a daemon bounce.

3. **`.gitignore` now carries 18 more lines for one collection.** The
   re-open/re-close-with-`*`/name-each-file pattern costs ~13 lines per results
   root and there are 22 roots. It works and nothing is broken; it is also how
   `scripts/lib/` got silently swallowed in phase 20. Recorded as a maintenance
   observation, not acted on.

---

## 10. Environment

`uv run --frozen --extra dev --extra cov --extra experiments --extra analysis
--extra b5`, CPython 3.13.0, WSL2 6.6.114.1, Ubuntu 24.04.4, Docker 29.4.3
(context `aep-native`, unix socket). Redis
`redis:7.2.5-alpine@sha256:6aaf3f5e…1f44` for both instances. Harness commit at
collection time: `972f05c`. `dm_flakey` loaded during pre-flight and left
loaded. Collection root on v9fs (`/mnt/d`); Docker data root on ext4.
