# Phase 10 — WS-0: native Docker Engine inside WSL2, and the measurement host re-baselined

**Date:** 2026-09-02  **Branch:** `main`  **Host:** `KP248`
**Prompt:** `prompts/phase-10-wsl2-native-docker.md` (verbatim, with the four
decisions and three additions issued alongside it recorded in the same file)
**Direction:** `docs/26-journal-readiness-direction.md` §4 WS-0

---

## Asked

Test whether installing Docker Engine natively inside the WSL2 distribution puts
the loop device, the `dm-flakey` target, the ext4 filesystem and the Redis
container in one namespace, and so unblocks `docs/24-revision-backlog.md` B1
without new hardware. Collect no new paper claim except one: a replication of an
existing frozen cell under the new runtime, to find out whether the runtime
change is a confound for everything collected afterwards.

Plus, issued with the prompt: measure `docker kill` latency on both runtimes;
give the replication a falsifiable criterion and the power to have one; record
fault-landing latency per run from now on; and establish (not fix) the
storage-backing split across existing collections.

---

## Done

| # | | evidence |
|---|---|---|
| 0 | Prompt + direction doc committed **and pushed** before anything else | `a9bf559`, pushed 09:38:02Z |
| 1 | Environment recorded before the change | `reports/phase-report-10-env-before.md`, `reports/raw/phase10-env-before-docker-desktop.txt` |
| 2 | dm-flakey self-test passes on this kernel | `reports/raw/phase10-flakey-selftest.{txt,json}` |
| 3 | Native engine provisioned, pinned, canaries proven | `scripts/provision_wsl2_native_docker.sh`, `reports/raw/phase10-provision-native-docker.txt` |
| 4 | Host verifier written; JSON below | `scripts/verify_measurement_host.py` |
| 5 | Stack up on the native engine, semantics unchanged | `reports/raw/phase10-stack-up-native.txt` |
| 6 | Full gate set run — **two gates fail, both pre-existing** | `reports/raw/phase10-gates-native.txt` |
| 6b | `docker kill` latency measured on both runtimes | `reports/raw/phase10-kill-latency*.{txt,json}` |
| 7b | Per-run fault-landing latency established and added | `experiments/harness/provenance.py`, new test file |
| 7 | Replication pre-registered, committed **and pushed** before data | `9b1848b`, pushed 10:34:00Z |
| 8 | Both arms collected, one arm **voided and re-collected** | see *Replication* |
| 9 | Storage backing across existing collections established | `scripts/survey_storage_backing.py` |
| 10 | Host documented | `docs/27-measurement-host.md` |
| 11 | Roadmap row added | `PAPER_ROADMAP.md` |

---

## Environment before

Full record: `reports/phase-report-10-env-before.md`. The two lines the phase
exists because of, verbatim from `reports/raw/phase10-env-before-docker-desktop.txt`:

```
=== docker inspect aep-phase2-redis72 -- HostConfig.Binds VERBATIM ===
["D:\\personal\\AEP\\Research-paper-AEP\\redis\\phase2.conf:/usr/local/etc/redis/redis.conf:ro","aep-phase2_redis-data:/data:rw"]
```

```
=== df -T for /var/lib/docker ===
df: /var/lib/docker: No such file or directory
```

The daemon resolved the bind source as a **Windows** path although the harness
ran inside WSL; and Docker's data root **did not exist inside the distro at
all**. Two namespaces. `docker version` reported `OS/Arch: windows/amd64` for the
client, because `/usr/local/bin/docker` was a shim that `cd`s to `/mnt/d` and
`exec`s `docker.exe`.

Also recorded then: `dmsetup targets` did **not** list `flakey` (the module ships
with the kernel but is not loaded on a freshly started distro), `iptables` was
absent, `systemd` is PID 1, and `AEP_HARNESS_SUSPEND_DISABLED` was unset.

---

## Environment after

`scripts/verify_measurement_host.py`, exit 0:

Written to `reports/raw/phase10-measurement-host.json`. All gates pass; both
bind-mount canaries round-trip their token.

```json
{
  "bind_mount_canary": {
    "drvfs": {
      "directory": "/mnt/d/personal/AEP/Research-paper-AEP/.scratch/phase10-canary",
      "filesystem": "v9fs",
      "name": "drvfs",
      "pass": true,
      "returncode": 0,
      "seen": "aep-host-verify-drvfs-3d786af7b8d0431f9d9c0bcdee7d59ac",
      "token": "aep-host-verify-drvfs-3d786af7b8d0431f9d9c0bcdee7d59ac"
    },
    "wsl_local": {
      "directory": "/root/aep-phase10-canary",
      "filesystem": "ext2/ext3",
      "name": "wsl_local",
      "pass": true,
      "returncode": 0,
      "seen": "aep-host-verify-wsl_local-f40c0dee01d8486a93b74d8fd89882ad",
      "token": "aep-host-verify-wsl_local-f40c0dee01d8486a93b74d8fd89882ad"
    }
  },
  "checked_at_utc": "2026-09-02T12:27:40Z",
  "clock": {
    "monotonic_span_seconds": 2.000052,
    "sample_seconds": 2.0,
    "source": "experiments/analyze.py TIMING_SUSPENSION_TOLERANCE_SECONDS",
    "tolerance_seconds": 2.0,
    "wall_minus_monotonic_seconds": -3e-06,
    "wall_span_seconds": 2.000049,
    "within_tolerance": true
  },
  "device_mapper": {
    "has_flakey": true,
    "module_on_disk": true,
    "module_path": "/usr/lib/modules/6.6.114.1-microsoft-standard-WSL2/kernel/drivers/md/dm-flakey.ko",
    "targets": [
      "flakey           v1.5.0",
      "verity           v1.9.0",
      "striped          v1.6.0",
      "linear           v1.4.0",
      "error            v1.6.0"
    ]
  },
  "docker": {
    "cli_path": "/usr/bin/docker",
    "client_os_arch": "linux/amd64",
    "client_version": "29.4.3",
    "compose_version": "5.5.0",
    "context": "aep-native",
    "daemon_name": "KP248",
    "daemon_os": "Ubuntu 24.04.4 LTS",
    "daemon_socket": "unix:///var/run/docker.sock",
    "data_root": "/var/lib/docker",
    "docker_host_env": null,
    "is_unix_socket": true,
    "is_windows_named_pipe": false,
    "server_git_commit": "56be731",
    "server_version": "29.4.3",
    "storage_driver": "overlayfs"
  },
  "docker_kill_latency": {
    "age_days": 0.1,
    "cache": "/mnt/d/personal/AEP/Research-paper-AEP/reports/raw/measurement-host-kill-latency.json",
    "comparable_historical_source": "reports/raw/e1-kill-latency-by-run.csv (issue_to_return_ns, n=300, median 961.6 ms, range 681.8-1673.9 ms, Docker Desktop shim). NOT comparable to \\ProcessKillWindowMin/Max 419-992 ms, which is the write-to-death window of the durability probe.",
    "instrument": "experiments.harness.redis_kill.kill_redis command_ms -- time.monotonic() around subprocess.run(['docker','kill','-s','KILL',container])",
    "measured_at_utc": "2026-09-02T10:00:45Z",
    "runtimes": {
      "aep-native": {
        "context": "aep-native",
        "endpoint": "unix:///var/run/docker.sock",
        "max": 397.0,
        "median": 317.0,
        "median_ci_high": 327.0,
        "median_ci_low": 312.5,
        "min": 264.0,
        "p95": 361.0,
        "server_version": "29.4.3",
        "trials_counted": 100,
        "unit": "milliseconds"
      }
    }
  },
  "euid": 0,
  "filesystem": {
    "docker_data_root": {
      "device": "/dev/sdd",
      "is_drvfs": false,
      "mount_options": "rw,relatime,discard,errors=remount-ro,data=ordered",
      "mount_point": "/var/lib/docker",
      "path": "/var/lib/docker",
      "type": "ext2/ext3"
    },
    "repo": {
      "device": "D:\\134",
      "is_drvfs": true,
      "mount_options": "rw,noatime,aname=drvfs;path=D:\\;uid=1001;gid=1001;symlinkroot=/mnt/,cache=5,access=client,msize=65536,trans=fd,rfd=6,wfd=6",
      "mount_point": "/mnt/d",
      "path": "/mnt/d/personal/AEP/Research-paper-AEP",
      "type": "v9fs"
    }
  },
  "gates": {
    "failures": [],
    "passed": true
  },
  "host": "KP248",
  "kernel": "6.6.114.1-microsoft-standard-WSL2",
  "os_release": {
    "BUG_REPORT_URL": "https://bugs.launchpad.net/ubuntu/",
    "HOME_URL": "https://www.ubuntu.com/",
    "ID": "ubuntu",
    "ID_LIKE": "debian",
    "LOGO": "ubuntu-logo",
    "NAME": "Ubuntu",
    "PRETTY_NAME": "Ubuntu 24.04.4 LTS",
    "PRIVACY_POLICY_URL": "https://www.ubuntu.com/legal/terms-and-policies/privacy-policy",
    "SUPPORT_URL": "https://help.ubuntu.com/",
    "UBUNTU_CODENAME": "noble",
    "VERSION": "24.04.4 LTS (Noble Numbat)",
    "VERSION_CODENAME": "noble",
    "VERSION_ID": "24.04"
  },
  "platform": "Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.39",
  "probe": "aep.measurement-host/1",
  "redis_endpoint": {
    "container": "aep-phase2-redis72",
    "container_status": "running",
    "published_ports": "{\"6379/tcp\":[{\"HostIp\":\"127.0.0.1\",\"HostPort\":\"6381\"}]}",
    "publishes_expected_port": true,
    "run_id_in_container": "61ec53bc51bb66bc18fa8163cc2ab7f0c29271f7",
    "run_id_on_port": "61ec53bc51bb66bc18fa8163cc2ab7f0c29271f7",
    "same_server": true,
    "url": "redis://127.0.0.1:6381"
  },
  "redis_image": {
    "compose_file": "/mnt/d/personal/AEP/Research-paper-AEP/compose.phase2.yml",
    "digest_matches": true,
    "image_id": "sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44",
    "pinned_digest": "sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44",
    "pinned_reference": "redis:7.2.5-alpine@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44",
    "resolved_repo_digests": [
      "redis@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44"
    ]
  },
  "repo_root": "/mnt/d/personal/AEP/Research-paper-AEP",
  "suspend": {
    "declared": false,
    "note": "amendment E5. Not detectable: a host that merely did not happen to suspend is indistinguishable from one that cannot. The declaration must be exported by the collection command itself.",
    "value": null,
    "variable": "AEP_HARNESS_SUSPEND_DISABLED"
  }
}
```


---

## Gate outputs (raw)

Full log: `reports/raw/phase10-gates-native.txt`.

| gate | exit | verdict |
|---|---|---|
| `uv sync --frozen --extra dev --extra cov --extra experiments --extra analysis` | 0 | pass |
| `verify_redis_semantics.py` (before suite) | 0 | pass |
| `pytest … --cov=aep_core --cov-fail-under=90` | 1 | **2 failed, 1792 passed** (a later re-run: 3 failed, 1791 passed, **coverage 91%** — the barrier flakiness picks different tests each run, see F2) |
| `check_pytest_gates.py` | 1 | fails as a consequence of the above |
| `verify_redis_semantics.py` (after the restart test) | 0 | pass |
| `validate_citations.py` | 0 | **371 citations, 0 invalid** — as expected |
| `check_paper_numbers.py` | 1 | 13 passed, 2 failed |
| `make reproduce-figures` | 2 | 3 files differ |
| `make reproduce-smoke` | 0 | **pass** |

> **The acceptance criterion "full suite passes with 0 skipped, 0 xpassed,
> coverage ≥ 90%; reproduce-figures byte-identical" is NOT met.** Stated plainly
> rather than buried. What follows is which failures this phase caused and which
> it did not, established by re-running the gates against a pristine
> `experiments/` tree.

### Suite

```
=========================== short test summary info ============================
FAILED tests/test_paper_tables.py::test_the_cross_fault_comparison_is_against_the_process_kill_probe
FAILED tests/test_recovery_durability_barrier.py::test_the_barrier_is_validated_once_not_per_resolution
2 failed, 1792 passed, 3 warnings in 193.31s (0:03:13)
```

**0 skipped, 0 xpassed. Coverage 91% (`TOTAL 2528 222 91%`), above the 90%
gate.** Both failures pre-date this phase; both are recorded under *Findings
outside scope* with the evidence for that claim.

A second full run of the same tree (`reports/raw/phase10-gates-final-suite.txt`)
gave **3 failed, 1791 passed** — the same stale-macro failure plus **two
different** barrier tests. F2 explains why the identity of the failing tests
moves between runs.

Note the count: **1794 collected**, not the 1734 the prompt expected. 1788 of
those pre-date this phase; 6 are the new
`experiments/harness/tests/test_kill_latency_provenance.py`. The prompt's 1734
was already stale.

### Citations

```
docs/22-formal-model.md: 371 citations (240 explicit, 131 continuation)
OK: 371 citations, 0 invalid
```

### `reproduce-figures` — three differences, one of them mine

```
  DIFFERS   numbers.tex
-% 90 files; regenerated on every run of this script
-\newcommand{\HarnessLoc}{23\,022}
+% 91 files; regenerated on every run of this script
+\newcommand{\HarnessLoc}{23\,243}
  IDENTICAL table-ablation.tex
  IDENTICAL table-ambiguity-by-crashpoint.tex
  IDENTICAL table-deployment-choice.tex
  IDENTICAL table-latency.tex
  IDENTICAL table-outcomes.tex
  DIFFERS   figure-1-undetected-vs-ambiguity.pdf: 11726 bytes differ, and not only in the timestamp.
  DIFFERS   figure-2-duplicates-by-crash-point.pdf: 12551 bytes differ, and not only in the timestamp.
```

**Attribution, established rather than assumed.** `experiments/` was reverted to
`HEAD`, `make reproduce-figures` re-run, and the result was:

```
  IDENTICAL numbers.tex          <- so the numbers.tex diff IS this phase's
  ...
  DIFFERS   figure-1-undetected-vs-ambiguity.pdf: 11726 bytes differ
  DIFFERS   figure-2-duplicates-by-crash-point.pdf: 12551 bytes differ
```

- **`numbers.tex` is this phase's**, and it is a **line count, not a result**.
  `\HarnessLoc` counts lines of Python under `experiments/`, which grew by 221
  across 1 new file because **ADDITION 3 required a harness change**. Every
  table is byte-identical; no measured number moved. Regenerating it is one
  command — `make reproduce-figures` writes it — but `paper/generated/**` is
  **out of this phase's scope**, so it has not been regenerated. **This is the
  one acceptance criterion that ADDITION 3 and the stated bounds cannot both
  satisfy, and it needs one line of the next phase.**
- **The two figure PDFs differ on a pristine tree**, so they pre-date this
  phase entirely. Recorded under *Findings outside scope*.

### `check_paper_numbers.py`

`13 passed, 2 failed`. `numbers.tex matches the CSVs` — the same `\HarnessLoc`
line as above. `build artifacts match current sources` — *"no
`.build-provenance.json` in `paper/`"*; pre-existing and unrelated (the PDFs in
`paper/` were not produced by `scripts/build_paper.sh` in a recorded run).

### `make reproduce-smoke`

```
reproduce-smoke: OK. New data is under .scratch/reproduce/smoke; the frozen tree was not touched.
```

Seven systems, real `SIGKILL`, on the native engine, tearing its own stack down
with `down -v` on exit.

---

## Fault delivery latency, both runtimes

ADDITION 1. Measured **before** the replication was collected, and recorded in
the pre-registration so it could not be introduced afterwards as an explanation.

**Instrument.** `scripts/measure_kill_latency.py` calls the harness's own
`experiments.harness.redis_kill.kill_redis` and reads its `command_ms` —
`time.monotonic()` around `subprocess.run(["docker","kill","-s","KILL",…])`
(`redis_kill.py:99-108`). The runtime is selected by putting a `docker` symlink
at the front of `PATH`, so the code under measurement is byte-identical between
arms and only resolution differs.

**First: what the paper's 419–992 ms actually is.** It is
`\ProcessKillWindowMin`/`Max`, the **write-to-death window** of the
durability-window probe (`reports/raw/e1-durability-window.txt`), which kill
latency dominates but does not equal. The directly comparable historical
quantity is `reports/raw/e1-kill-latency-by-run.csv` — 300 collected runs'
`issue_to_return_ns` through the Docker Desktop shim. Everything below is
compared against **that**.

### Interleaved, throwaway container, n = 100 per runtime — isolates the runtime

Round-robined rather than blocked, so host drift during the measurement lands on
both arms. Raw: `reports/raw/phase10-kill-latency.{txt,json}`.

| runtime | n | min | median | p95 | max | median 95% CI |
|---|---|---|---|---|---|---|
| Docker Desktop shim | 100 | 378 | **423** | 485 | 514 | [418, 431] |
| `aep-native` | 100 | 179 | **223** | 257 | 287 | [220, 229] |

**Difference of medians +199.5 ms, 95% CI [192.0, 209.0]** (10 000 resamples,
seed 20260806). Ratio **1.89×**. The native distribution is also **tighter**:
IQR 22 ms against 39 ms; range 108 ms against 136 ms.

### Against the real compose container — comparable in absolute terms

The throwaway container isolates the runtime but is not what the collected runs
killed. `--existing-container aep-phase2-redis72` points the same instrument at
the real target. Only one daemon can hold `127.0.0.1:6381`, so this arm cannot
be interleaved and was run on the native runtime only; the Docker Desktop side
of this comparison is the 300 collected runs. Raw:
`reports/raw/phase10-kill-latency-compose-native.{txt,json}`.

| source | runtime | n | min | median | max |
|---|---|---|---|---|---|
| `reports/raw/e1-kill-latency-by-run.csv` (collected runs) | Docker Desktop shim | 300 | 681.8 | **961.8** | 1673.9 |
| this phase | `aep-native` | 100 | 264 | **317** | 397 |

> **Fault delivery on the native runtime is about three times faster and far
> tighter — median 317 ms against 961.8 ms, range 133 ms against 992 ms.**

**Why this matters, stated once.** Phase 8.1 established that in the
`redis-kill-preack` regime AEP-full dispatches **iff** `WAITAOF` returns before
Redis dies, and that runs which applied an effect had **+194.1 ms** higher kill
latency (permutation p = 0.00005). The runtime change alone moves the median by
**199.5 ms** — the same order as the effect Phase 8.1 attributed to the race.
The window that decides `\UnwantedPrevented{}` is materially narrower on this
runtime.

> **Nothing in the manuscript has been re-analysed or adjusted on this basis.**
> Phase 10 establishes the distribution only. What it implies for Table IX is
> WS-3's decision.

Two caveats, stated rather than left to be found:

- The historical figure was recorded **during live protocol runs**, with a
  worker mid-execution; this phase's was measured on an otherwise idle stack.
  Target and instrument are like-for-like; host load is not.
- The `session-3` regime the replication uses **performs no `docker kill`** —
  its fault is a worker `SIGKILL` the process sends to itself
  (`injector.py:81-82`). So this does not reach the replication. It will reach
  WS-3.

---

## Replication

### Provenance of the pre-registration, and the ordering it proves

| | commit | commit time | pushed to `origin/main` |
|---|---|---|---|
| prompt + direction doc | `a9bf5598e6dcc31b5979c88fbb395f3700a1ae90` | 2026-09-02T09:37:33Z | **09:38:02Z** |
| **pre-registration + analysis script** | `9b1848b53903c8fc285e781e0d6e19a37c236364` | 2026-09-02T10:33:31Z | **10:34:00Z** |
| first Phase 10 data written | — | **11:30:32Z** (`events-recovery.jsonl`, ext4 matched, first record) | — |

**The pre-registration was pushed 56 minutes before the first byte of data
existed**, and the analysis it names — `scripts/phase10_replication_analysis.py`,
including the ±15 pp margin and the half-width rule — is in that same commit.

### The cell, and the arms

`aep_full` × `ledger_postings` (= `NO_READBACK`) × `session-3` (crash-always) ×
`CALLER_REFERENCE`, matching the frozen `matrix` cell exactly.

| arm | collected at | filesystem recorded by the runs | committed at |
|---|---|---|---|
| **ext4** | `/root/aep-phase10/…` | `ext2/ext3`, `/dev/sdd`, `is_drvfs=False` | `experiments/results/phase10-replication-ext4-*-2026-09-02` |
| **drvfs** | repo tree | `v9fs`, `D:\134`, `is_drvfs=True` | `experiments/results/phase10-replication-drvfs-*-2026-09-02` |

Each arm: **18 matched runs** (3 × 6 crash points) + **30 powered runs** at
`after_resolution_before_barrier`. **96 runs, 960 executions total.** Each
directory carries a `COLLECTION-PROVENANCE.json` recording the collection path,
its filesystem, the committed path, and the full `verify_measurement_host.py`
output — so the ext4 arm's collected-vs-committed path difference is explicit.

**The two arms are genuinely separate collections**, checked rather than
assumed: of 70 event logs compared, **0 are byte-identical**; their wall clocks
are ~53 minutes apart; and their recorded filesystems differ as above.

### Result 1 — matched arms, 18 runs each, against the frozen cell

| metric | frozen | ext4 | ext4 − frozen (95% CI) | verdict |
|---|---|---|---|---|
| `known_ambiguity_rate` | 130/180 = 0.7222 | 128/180 = 0.7111 | **−0.0111 [−0.0778, +0.0556]**, hw 0.067 | **NOT A CONFOUND** |
| `undetected_duplicate_rate` | 0/180 | **0/180** | +0.0000 [0, 0] | NOT A CONFOUND |
| `lost_effect_rate` | 0/180 | **0/180** | +0.0000 [0, 0] | NOT A CONFOUND |
| `unverified_failure_rate` | 0/180 | **0/180** | +0.0000 [0, 0] | NOT A CONFOUND |
| `recovery_success_rate` | 150/180 = 0.8333 | **150/180 = 0.8333** | +0.0000 [0, 0] | NOT A CONFOUND |

| metric | drvfs | drvfs − frozen (95% CI) | verdict |
|---|---|---|---|
| `known_ambiguity_rate` | 130/180 = 0.7222 | **+0.0000 [−0.0667, +0.0667]**, hw 0.067 | **NOT A CONFOUND** |
| the other four | identical to frozen | +0.0000 [0, 0] | NOT A CONFOUND |

**ext4 vs drvfs, matched:** `known_ambiguity_rate` **+0.0111 [−0.0556, +0.0778]**,
half-width 0.0667 → **NOT A CONFOUND at ±15 pp.** All four other metrics
identical.

> **P1 is confirmed exactly.** Four of the five metrics reproduce to the
> execution — 0/180 undetected duplicates, 0/180 lost effects, 0/180 unverified
> failures, 150/180 recovery successes — under a different container runtime and
> on both filesystems.
>
> And the matched comparison turned out to be **conclusive**, which the
> pre-registration did not predict: half-width 0.067, well inside the margin.
> The §3 power calculation was about the single 3-run sub-cell; pooling the six
> crash points gives 18 matched clusters per side and a much tighter interval.
> That is a bonus, not a deviation — the strata are matched exactly and the
> bootstrap is stratified over them.

### Result 2 — the powered cell, 30 runs per arm

`after_resolution_before_barrier`, the only sub-cell with interior variance.

| | runs | `known_ambiguity_rate` | 95% CI |
|---|---|---|---|
| frozen | 3 | 10/30 = **0.3333** | [0.0000, 0.6000] |
| ext4 | 30 | 58/300 = **0.1933** | [0.1467, 0.2433] |
| drvfs | 30 | 58/300 = **0.1933** | [0.1467, 0.2433] |

| comparison | difference | 95% CI | half-width | verdict |
|---|---|---|---|---|
| ext4 − frozen | −0.1400 | [−0.3967, +0.1833] | **0.2900** | **INCONCLUSIVE — UNDERPOWERED** |
| drvfs − frozen | −0.1400 | [−0.3967, +0.1833] | **0.2900** | **INCONCLUSIVE — UNDERPOWERED** |
| **drvfs − ext4** | **+0.0000** | **[−0.0700, +0.0667]** | **0.0683** | **NOT A CONFOUND** |

`undetected_duplicate_rate`, `lost_effect_rate` and `unverified_failure_rate`
are **0/300 in both arms**; `recovery_success_rate` is **300/300 in both**.

> **P2 and P3 came out exactly as pre-registered, including the verdict.** The
> half-width is 0.290 against a predicted ≈ 0.29. The comparison against the
> frozen cell **cannot** be made conclusive at ±15 pp by collecting more,
> because the frozen side has three run-clusters whose per-run values are
> **6/10, 4/10, 0/10**. This was stated in advance precisely so that an
> inconclusive result could not be presented afterwards as agreement.
>
> **P4 is confirmed and is the one conclusive comparison of the phase:** ext4
> against drvfs, 30 clusters a side, difference exactly 0.0000 with a
> half-width of 0.068. **The filesystem does not move this cell.**
>
> **P5 is confirmed:** across all 960 executions of both arms, **zero undetected
> duplicates and zero lost effects.**

### Result 3 — why the frozen 0.3333 and the new 0.1933 are consistent

Descriptive, and **post hoc** — not pre-registered.

The 30-run ext4 sample, ambiguous executions per run:

```
0 0 0 1 1 1 1 1 1 1 1 1 1 1 2 2 2 2 2 2 2 3 3 3 3 3 4 4 4 6
mean 1.93/10   median 2/10   range 0–6
pooled 0.1933; binomial variance 1.560, observed 1.926 -> over-dispersion 1.24x
```

The frozen cell's three runs were **0/10, 4/10 and 6/10**. **All three of those
values occur in the 30-run sample** (0 three times, 4 three times, 6 once). A
three-run draw from this distribution that happened to take 0, 4 and 6 gives
0.3333; the 30-run estimate of 0.1933 is simply a better estimate of the same
quantity. Nothing here is evidence that the runtime moved the rate — and nothing
here licenses replacing the frozen number, which is not this phase's business.

It does, however, show the shape Phase 9C found: **three runs cannot resolve
this cell.** The matched arm's own 3-run ARBB draw returned 10/30 = 0.3333,
identical to the frozen value, while the 30-run draw on the same host the same
hour returned 0.1933.

### Result 4 — a paired, execution-level view

Also **post hoc and descriptive.** The harness derives `run_id` and
`execution_id` deterministically from the cell identity and matrix seed, so the
frozen collection and both new arms carry **the same 180 execution identifiers**.
That permits a one-to-one comparison stronger than a rate difference:

| pair | executions with identical `outcome_class` | where they differ |
|---|---|---|
| frozen vs ext4 | **172/180 (95.6%)** | `after_resolution_before_barrier` 6, `mid_dispatch` 2 |
| frozen vs drvfs | **168/180 (93.3%)** | `after_resolution_before_barrier` 12 |
| ext4 vs drvfs | **168/180 (93.3%)** | `after_resolution_before_barrier` 10, `mid_dispatch` 2 |

In the powered cell, 225/300 (75%) of executions match between arms — **yet all
30 runs have identical ambiguous counts and the pooled rate is identical at
58/300.** The 75 disagreements are almost perfectly balanced in direction
(33 `DECLARED_AMBIGUOUS`→`CONFIRMED_APPLIED` against 32 the other way), so they
cancel within each run. Read plainly: **how many executions a run declares
ambiguous is reproducible; which executions they are is not.** Every
disagreement is between `DECLARED_APPLIED`/`CONFIRMED_APPLIED`-class outcomes and
`DECLARED_AMBIGUOUS` — **none of them is an undetected duplicate or a lost
effect**, which are 0 everywhere.

### Deviations from the pre-registration, recorded not applied silently

1. **`AEP_HARNESS_SUSPEND_DISABLED` was not exported**, though §4's command
   shows it. Reason and evidence under *Not done and why* item 4. It makes the
   arms *more* like the frozen cell, not less, and cannot affect a rate.
2. **`--system aep_full` in §4 is not a valid `SystemId`**; the enum value is
   `AEP_FULL`. The first attempt exited 2 having written nothing. A typo in the
   pre-registered command, corrected in the invocation.
3. **The analysis script's regime literal was widened to a set of aliases**
   after data existed. `"(session-3)"` (the tracked frozen CSV, 2026-08-10)
   and `"crashed"` (today's `analyze.py`) are the same regime; joining on the
   label alone selected **zero** rows from the new arms. The change is a label
   alias and touches neither the estimand, the unit, the margin, the seed nor
   the verdict rule — before it, the new arms contributed nothing at all. Full
   reasoning is in the script's own comment, and the underlying defect is
   recorded as F5.

### The voided arm

**The first ext4 collection was discarded. It was collected against the wrong
runtime.**

What happened: the barrier-flake comparison (F2) brought Docker Desktop's stack
up to measure it, and its restore step ran the native `compose up` with output
suppressed. That `up` failed —
`failed to bind host port 127.0.0.1:6381/tcp: address already in use` — because
Docker Desktop still held the port. The collect script then ran `compose up`
piped into `tail`, **losing its exit status**, and `verify_redis_semantics.py`
passed: it interrogates the *server*, and a Redis started from the same compose
file by another daemon satisfies every one of its checks. Forty runs went to
Docker Desktop's Redis while the native container sat in state `created`.

**What exposed it** was a provenance field: `redis_container_state.started_at`
read `0001-01-01T00:00:00Z` in the run configs — `docker inspect` reporting a
container that had never started. The environment record was describing a
container that was not serving the runs.

Action taken:

- the collection was stopped and moved to
  `/root/aep-phase10/VOIDED/…-VOID-wrong-runtime`, **never committed**; its log
  is kept at `reports/raw/phase10-collect-ext4-VOIDED-wrong-runtime.txt`;
- the stack was reset and **proved** native by comparing `INFO server`'s `run_id`
  seen from the socket against the same field through `docker exec`;
- the collect script now fails loudly on `compose up`, asserts the container is
  `running` and publishes 6381, asserts the two `run_id`s match, and asserts
  Docker Desktop has no `aep-phase2` container running;
- **`scripts/verify_measurement_host.py` now performs the same `run_id` check**
  and fails the gate on mismatch, so every later phase inherits it;
- the arm was re-collected in full on the verified native stack.

The voided runs were not wasted entirely: they supply the same-day
Docker-Desktop-served comparison in the clock-divergence table under *What this
unblocks*. They are used for that and for nothing else.

---

## Storage backing across existing collections

Added scope. **This section establishes a fact and does nothing else.** No
manuscript file is edited, no frozen cell is re-analysed, nothing is corrected.

Method: `scripts/survey_storage_backing.py`. Raw:
`reports/raw/phase10-storage-backing-survey.{txt,json}`. Two rules it follows,
because otherwise the answer is worthless: **nothing is inferred from a
directory name**, and **`UNDETERMINED` is a first-class answer**. Only a run's
own recorded `environment` block counts as determining it.

### 1. What is tracked, and what a tracked file can tell you

Raw run directories are **gitignored by design** (`.gitignore:134-151`); only
`analysis/` products and manifests are tracked — 149 files of the 5 006 on disk.

> **No tracked file in this repository records `results_root_filesystem` or
> `redis_storage_backing` for any collection.** `git grep` over
> `experiments/results/` returns nothing for either field, and neither
> `coverage.json` nor `MANIFEST.csv` carries an environment column.

So from the repository alone, the storage backing of **every** collection the
manuscript quotes is `UNDETERMINED`.

### 2. Per root, from the run directories that exist

`experiments/harness/provenance.py` was added in Phase 8.2 (`e67efd1`,
2026-08-27). Collections before it carry no `environment` block at all.

| results root | where its runs live | runs | environment recorded | filesystem | `redis_storage_backing` |
|---|---|---|---|---|---|
| **`matrix`** (432 runs — the cell **every rate in the paper** comes from) | `/root/aep` | 433 dirs / 432 configs | **0** | **UNDETERMINED** | **UNDETERMINED** |
| `matrix` (working clone subset) | `/mnt/d` repo tree | 84 | **0** | **UNDETERMINED** | **UNDETERMINED** |
| `fsync-always` | `/root/aep` | 6 | **0** | **UNDETERMINED** | **UNDETERMINED** |
| `b2-2026-08-21`, `b2-s1/s2/s3-2026-08-21` (240 runs, carry `\ReplicationPrevented*`) | `/mnt/d` repo tree | 60 each | **0** | **UNDETERMINED** | **UNDETERMINED** |
| `smoke`, `selfcheck`, `selfcheck-c5`, `throughput` | mixed | 0–6 | **0** | **UNDETERMINED** | **UNDETERMINED** |
| `b2-paired-s1-2026-08-28` | `/root/aep-phase8` | 120 | **120** | ext4, `/dev/sdf`, mount `/`, `is_drvfs=False` | `volume /var/lib/docker/volumes/aep-phase2_redis-data/_data` |
| `b2-paired-v2-s1…s4-2026-08-28` | `/root/aep-phase8` | 120 each | **120 each** | ext4, `/dev/sdf`, mount `/`, `is_drvfs=False` | same |
| `b2-paired-v2-s2-aborted-…`, `…-operator-aborted-…` | `/root/aep-phase8` | 26, 16 | all | ext4, `/dev/sdf`, mount `/` | same |
| **Phase 10 ext4 arm** | `/root/aep-phase10` | 48 | all | ext4, `/dev/sdd`, mount `/`, `is_drvfs=False` | `volume …/_data`, on `/dev/sdd` ext4 **in the distro** |
| **Phase 10 drvfs arm** | repo tree | 48 | all | **v9fs**, `/mnt/d`, `is_drvfs=True` | same volume |

### 3. Three findings a reader should not have to derive

**(a) The frozen `matrix` collection's storage backing is UNDETERMINED from
recorded metadata.** `provenance.py`'s own docstring states that "the paper's
cell was collected in the WSL-native tree on ext4". That is a **claim in prose,
not a recorded field.** Its support is that the 432 run directories physically
sit at `/root/aep/experiments/results/matrix`, which is today on `/dev/sdd`
ext4 — an inference from where bytes sit *now*, not from what the run wrote. It
is very probably correct. It is not evidenced in the way Phase 8.2 requires.

**(b) The device name is not a stable identity.** The Phase-8 collections
recorded the distro root as `/dev/sdf`; today it is `/dev/sdd`. WSL2 assigns
these dynamically. A later comparison keyed on `device` would read two
identical filesystems as different.

**(c) Two roots record a `results_root` that is not where they now sit.**
`b2-paired-v2-s2-aborted-2026-08-28` and
`b2-paired-v2-s2-operator-aborted-2026-08-28` both record
`results_root: experiments/results/b2-paired-v2-s2-2026-08-28`. They were
renamed after collection. The recorded field is the truthful one; the directory
name is not.

### 4. Which comparisons in §VI span a storage-backing difference

Determined, not estimated. Each `\macro` used in
`paper/sections/06-evaluation.tex` was mapped through the provenance comment
`scripts/paper_tables.py` emits above it in `paper/generated/numbers.tex` to its
source root; paragraphs drawing on two or more roots are listed below.

**12 paragraphs of `paper/sections/06-evaluation.tex` put numbers from different
results roots side by side:**

| file:line | roots spanned |
|---|---|
| `06-evaluation.tex:340-349` | `matrix` + `b2-paired-v2-*` |
| `06-evaluation.tex:385-397` | `matrix` + e1-durability-window probe |
| `06-evaluation.tex:406-419` | `matrix` + `b2-*-2026-08-21` |
| `06-evaluation.tex:421-438` | `b2-*-2026-08-21` + e1-kill-latency |
| `06-evaluation.tex:440-447` | `b2-*-2026-08-21` + e1-kill-latency |
| `06-evaluation.tex:462-468` | `matrix` + `b2-*-2026-08-21` |
| `06-evaluation.tex:525-534` | g2-flakey (no Docker) + e1-durability-window |
| `06-evaluation.tex:558-568` | g2-flakey (no Docker) + e1-durability-window |
| `06-evaluation.tex:623-631` | `matrix` + `fsync-always` |
| `06-evaluation.tex:633-640` | `matrix` + `fsync-always` |
| `06-evaluation.tex:648-658` | `matrix` + `fsync-always` |
| `06-evaluation.tex:704-715` | `matrix` + `fsync-always` |

Of these, the ones where **both** sides are `UNDETERMINED` are all of them
except `340-349`, whose `b2-paired-v2-*` side *is* determined
(ext4, `/dev/sdf`) while its `matrix` side is not.

`06-evaluation.tex:462-468` is the paragraph carrying `\UnwantedPrevented{}` and
the `\ReplicationAepMin`–`Max` range; `623-658` and `704-715` are the barrier
cost and throughput comparisons between `everysec` (`matrix`) and `always`
(`fsync-always`).

**No claim is made here that any of these comparisons is wrong.** The claim is
narrower and it is exactly B1's Phase-8.2 rule: the property that could move
them was not held fixed by anyone and is not recorded, so it must be *stated*
rather than assumed comparable. What to do about it is the next phase's
decision.

---

## What this unblocks

**B1 has two recorded blockers. This phase removes one of them and does not
touch the other.**

### Blocker 1 — the bind-mount resolution failure. **REMOVED.**

`docs/24-revision-backlog.md` B1, "What blocked it here, exactly":

> This Docker daemon resolves bind-mount *sources* in the Windows filesystem,
> not in the WSL distro's […] A `dm-flakey` device assembled inside WSL exists
> only at a WSL path, so it cannot be named as a bind source for the container.

Four things are now true that were not, each with raw evidence:

| requirement | evidence |
|---|---|
| the daemon is in the distro | `docker info` → `Name: KP248`, `Operating System: Ubuntu 24.04.4 LTS`, `Docker Root Dir: /var/lib/docker` **which now exists**, on `/dev/sdd` ext4 |
| bind sources resolve as Linux paths | `"Source":"/mnt/d/personal/AEP/Research-paper-AEP/redis/phase2.conf"` (was `D:\personal\…`) |
| a **WSL-local** path can be bind-mounted and read inside a container | canary `wsl_local` round-trips its token, `/root/aep-phase10-canary`, fs `ext4` |
| `dm-flakey` works on this kernel | self-test `valid=true`: `before_the_cut_survived=True`, `after_the_cut_survived=False` |

B1's second sub-argument is also now partly obsolete and is recorded so nobody
re-derives it: B1 says *"`which redis-server` in Ubuntu-24.04 returns nothing"*.
A native `redis-server 7.2.5` binary does exist at `/root/redis-server` and the
self-test ran against it. It is still **not** the digest-pinned container image,
so the argument's conclusion stands; only its premise has moved.

### Blocker 2 — fault-delivery reliability. **NOT REMOVED.**

B1's Phase-8.4 addendum, which the phase prompt required be treated separately:

> **the second host is now required for *reliability*, not only for the
> bind-mount** […] In B1 the fault **is** the measurement. […] An instrument
> that intermittently fails to deliver the fault does not cost B1 precision — it
> silently removes the phenomenon while leaving runs that look successful.

The count that motivates it — 0 non-landing kills in 360 runs, then 2 in the
first 26 of Phase 8.4 session 2 — is about **this WSL2 kernel and this host**. A
native daemon in the *same* kernel does nothing about it. Phase 10 did not
re-measure it, and could not have: the `session-3` regime issues no `docker
kill`.

**And this phase found a fourth independent surface of the same host
degradation.** The E5 wall-versus-monotonic gate:

| collection | runs | dropped for clock suspension | worst |
|---|---|---|---|
| frozen `matrix` | 432 | **7 (1.6%)** | 65 559 s (the known 18-hour incident) |
| Phase 10 ext4 matched | 18 | **18 (100%)** | 16.6 s |
| Phase 10 ext4 powered | 30 | **29 (97%)** | 10.9 s |
| the voided Docker-Desktop-served runs, same day | 18 | **16 (89%)** | 6.4 s |

The divergences are small in magnitude but **near-universal in frequency, under
both runtimes on the same day**. It is therefore a property of the host today,
not of the runtime change — a fourth surface alongside the within-session drift,
the kill-latency envelope and the kill non-delivery that B1's addendum already
lists. **No timing number can be collected on this host in its current state.**
Rates are unaffected (counts stand; `analyze.py:352-362`), which is why the
replication remains valid.

### Verdict

> **B1 is now *runnable* — the bind-mount blocker that stopped it is gone and
> proven gone. It is not yet *trustworthy* on this host: its own addendum
> requires reliable fault delivery, this host is showing degradation on four
> independent surfaces, and in B1 the fault is the measurement rather than a
> side condition.**
>
> B1 can be attempted here, and it must report its own non-delivery count as a
> first-class number, as its addendum already requires. A second host remains
> required for the result to be worth anything.

WS-3 (controlled Redis fault) and WS-5 (timing power) additionally inherit the
finding in *Fault delivery latency*: the race window is ~3× narrower on this
runtime than in every collected run.

---

## Not done and why

1. **`paper/generated/numbers.tex` was not regenerated**, so
   `make reproduce-figures` is not byte-identical and `check_paper_numbers.py`
   does not pass. The only difference is `\HarnessLoc` 23 022 → 23 243
   (90 → 91 files), a line count of `experiments/`, which changed because
   ADDITION 3 required a harness change. `paper/generated/**` is explicitly out
   of this phase's bounds. **This is the one place where an addition to the
   prompt and the prompt's own bounds cannot both be satisfied**, and it needs a
   single `make reproduce-figures` in the next phase.

2. **The two pre-existing test failures were not fixed** (F1, F2), nor the two
   pre-existing figure-PDF differences (F3) or the missing build provenance
   (F4). All are outside scope and recorded above.

3. **`.github/workflows/ci.yml` was not touched.** The prompt allows it "only if
   a new environment assertion is needed". None is: CI runs on
   `ubuntu-24.04` GitHub runners with a native Docker daemon already, so the
   bind-source pathology this phase fixes cannot occur there, and asserting a
   `dm-flakey` target or an `aep-native` context in CI would assert something
   about a host CI does not have.

4. **`AEP_HARNESS_SUSPEND_DISABLED` was not set for the collection**, deviating
   from the pre-registration's §4 command. Recorded in
   `.scratch/phase10-collect.sh` and here rather than applied silently. Reason:
   all 84 frozen `matrix` run-configs carry **no** `suspend_disabled_declared`
   key, so `analyze.py` defaults them to `False` and every frozen run already
   contributes counts and no durations. Setting it on the new runs would assert
   something about this Windows host's sleep settings that was **not verified**
   — exactly what E5 exists to prevent — and would make the new runs differ from
   the frozen ones in a recorded field, for no benefit to a rate comparison.
   Matching the frozen cell is the more like-for-like choice and is the one
   taken.

5. **B1 itself was not run.** Out of scope for this phase, and its second
   blocker is not removed (see *What this unblocks*).

6. **The final data commit `c63aea0` is committed locally but NOT pushed.**
   `git push` hangs with no output; `git-credential-manager.exe` is resident and
   is presumably holding an interactive authentication dialog that cannot be
   answered from this session. Two attempts were stopped after ~10 and ~7
   minutes. The repository is intact — no `index.lock`, no
   `refs/remotes/origin/main.lock`, `git fsck --connectivity-only` clean,
   `main` ahead of `origin/main` by exactly one commit.

   **The pre-registration ordering requirement is unaffected and already
   satisfied**: decision A2 requires the prompt commit and the pre-registration
   commit to be pushed *before data exists*, and both were —
   `a9bf559` at 09:38:02Z and `9b1848b` at 10:34:00Z, against a first data byte
   at 11:30:32Z, all verifiable on `origin/main`. What remains unpushed is only
   the commit that *carries* the data, whose ordering claim is already witnessed
   externally. **`git push origin main` needs to be run interactively.**

7. **The Windows host's sleep/hibernation configuration was not established.**
   `powercfg` could not be queried non-interactively from this shell. It does
   not affect anything this phase reports, because no timing number is claimed
   and the E5 gate excluded every duration anyway.

---

## Findings outside scope

Recorded, **not fixed**, per the prompt's bounds.

### F1 — `tests/test_paper_tables.py` asserts a macro that was deliberately withdrawn

`test_the_cross_fault_comparison_is_against_the_process_kill_probe` fails with
`KeyError: 'FlakeyVsProcessKillP'`. `scripts/paper_tables.py:708` says:

```
# \FlakeyBarrierP and \FlakeyVsProcessKillP are deliberately NOT emitted.
# Both were Fisher exact two-tailed, and Fisher assumes two independent
# samples. These are not two samples: one_trial() writes an acknowledged
# and an un-acknowledged record in the SAME trial …
```

Dated: the macro was withdrawn **2026-08-31** (`9545ccb`, *"Withdraw the flakey
probe's two p-values"*); the test asserting it was last touched **2026-08-07**
(`b2fc057`). **The suite has been red on this test for two days before this
phase began.** The test, not the implementation, is the stale one — the
withdrawal was deliberate and reasoned.

### F2 — the real `WAITAOF` barrier intermittently exceeds its timeout on this host

**This is not one flaky test.** Two suite runs on the same tree produced
*different* failing tests, all with the same root cause:

| run | failing tests | cause |
|---|---|---|
| gate run | `test_the_barrier_is_validated_once_not_per_resolution` | `WriteAheadWorkflowError: recovery durability barrier did not acknowledge the write` |
| final run | `test_acknowledged_real_waitaof_barrier_permits_dispatch`, `test_one_execution_produces_exactly_one_applied_mutation` | `WriteAheadWorkflowError: durability barrier failed: DurabilityBarrierError` (`intent_workflow.py:359`) |

So the defect is in the **host**, not in any one test: under
`appendfsync everysec` a `WAITAOF` occasionally does not return inside the
configured `durability_timeout_ms`, and whichever test happens to hit it fails.
**AEP-full's dispatch depends on that same barrier**, and it fails *closed* when
the barrier does not acknowledge — which is the protocol behaving correctly, but
it means barrier timeouts were a live condition during this phase's collection.
Offered as a candidate contributor to the `after_resolution_before_barrier`
cell's variability, **not** as a claim: it was not measured per run.

The most-studied instance,
`test_the_barrier_is_validated_once_not_per_resolution`, measured 20× per
runtime:

| runtime | failures / 20 | Wilson 95% |
|---|---|---|
| `aep-native` | **5/20 (0.25)** | [0.112, 0.469] |
| Docker Desktop | **2/20 (0.10)** | [0.028, 0.301] |

Fisher exact two-tailed **p = 0.41** — the runtimes are **not** distinguishable
at n = 20. Raw: `reports/raw/phase10-barrier-flake-{native,desktop}.txt`.

Mechanism: the test performs **three consecutive** recoveries, each running a
real `WAITAOF` with `durability_timeout_ms=2000` under `appendfsync everysec`.
A 2 s timeout against a 1 s fsync period, three times over, leaves little
headroom. It is a test-design fragility, not a protocol defect — and it is worth
noting that **AEP-full uses the same barrier**, so if the runtime had moved
barrier latency materially this is where it would have shown. At n = 20 per
runtime it does not.

### F3 — the two analysis-figure PDFs differ from what is committed, on a pristine tree

`figure-1-undetected-vs-ambiguity.pdf` (11 726 bytes) and
`figure-2-duplicates-by-crash-point.pdf` (12 551 bytes) differ under
`make reproduce-figures` **with `experiments/` reverted to `HEAD`**, so this
pre-dates the phase. The Makefile itself distinguishes a timestamp-only
difference from a real one and reports *"A plotted value moved. This is a
finding, not a build error."* Not investigated further — out of scope.

### F4 — `check_paper_numbers.py`: no `.build-provenance.json` in `paper/`

*"the artifacts there were not recorded as produced from any source tree"*. Two
further checks (bibliography, undefined references) are consequently skipped.
Pre-existing and unrelated to this phase.

### F5 — the same regime has two different labels in two generated CSVs

The tracked `experiments/results/matrix/analysis/per-execution.csv` (committed
2026-08-10, `831c796`) labels the crash-always regime **`(session-3)`**. A
per-execution.csv generated by today's `analyze.py` labels it **`crashed`**
(`analyze.py:406` maps the empty regime key to that display string). Both are
the same condition — `analyze.py:601-616` derives the key as `""` when
`crash_probability == 1.0` and no Redis kill occurs.

**Consequence:** any script joining a frozen analysis CSV to a fresh one on
`regime` silently selects **zero** rows and reports a clean, empty, plausible
result. That happened to this phase's own analysis on its first run and was
caught only because a rate of `0/0` is obviously wrong. A less obvious metric
would have passed. Recorded as a defect in the analysis output's stability, not
fixed.

### F6 — `provenance.redis_container_state` can silently describe a container that never ran

`docker inspect --format '{{.State.StartedAt}}'` on a container in state
`created` returns `0001-01-01T00:00:00Z`, and `provenance.py:209-221` records it
without comment. During this phase that zero timestamp was the **only** visible
symptom of a far larger problem (see *Replication → the voided arm*): the
provenance block described a container that was not serving the runs. The field
is doing its job by recording what it saw; what is missing is that nothing
treats a zero `StartedAt`, or a non-`running` status, as worth flagging.

Related, and closed *inside* this phase rather than left: neither
`verify_redis_semantics.py` (which interrogates the **server**) nor
`docker version` (which interrogates the **daemon**) can tell you whether the
Redis on the harness's port is the one the selected daemon owns.
`scripts/verify_measurement_host.py` now checks exactly that, by comparing
`INFO server`'s `run_id` seen from the socket against the same field seen
through `docker exec`.
