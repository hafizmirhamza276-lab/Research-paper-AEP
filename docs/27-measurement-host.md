# The measurement host

What this project measures on, how to rebuild it, and which numbers in the
manuscript predate it. Written by Phase 10 (WS-0); the phase report is
`reports/phase-report-10-wsl2-native-docker-2026-09-02.md`, the record of the
host *before* the change is `reports/phase-report-10-env-before.md`.

**One sentence.** The measurement host is Ubuntu 24.04 inside WSL2 on Windows 11,
and as of 2026-09-02 the container runtime is **Docker Engine running natively
inside that distribution** rather than Docker Desktop — so the loop device, the
`dm-flakey` target, the ext4 filesystem and the Redis container are in one
namespace for the first time.

---

## 1. The host as it now stands

| property | value | how to re-read it |
|---|---|---|
| machine | `KP248`, single host, single author | `hostname` |
| OS | Windows 11 Enterprise 10.0.26200 | — |
| distro | Ubuntu 24.04.4 LTS (`noble`) under WSL2 | `cat /etc/os-release` |
| kernel | `6.6.114.1-microsoft-standard-WSL2` | `uname -r` |
| PID 1 | `systemd` (`systemctl is-system-running` → `running`) | `ps -p 1 -o comm=` |
| account | `root` inside the distro | `whoami` |
| repo tree | `/mnt/d/personal/AEP/Research-paper-AEP` | — |
| repo filesystem | **9p / drvfs**, `uid=1001;gid=1001` | `stat -f -c %T .` |
| distro root filesystem | `/dev/sdd` **ext4**, `rw,relatime,discard,errors=remount-ro,data=ordered`, 952 GB free | `df -T /` |
| container runtime | **Docker Engine 29.4.3, native**, context `aep-native` | `docker context show` |
| daemon endpoint | `unix:///var/run/docker.sock` | `docker context inspect` |
| docker client | `linux/amd64` (was `windows/amd64`) | `docker version` |
| Docker data root | `/var/lib/docker`, on `/dev/sdd` ext4 — **inside the distro** | `docker info` |
| storage driver | `overlayfs` | `docker info` |
| `dmsetup targets` | `flakey v1.5.0` present once `dm-flakey` is loaded | `dmsetup targets` |
| Redis image | `redis:7.2.5-alpine@sha256:6aaf3f5e…`, digest unchanged | `docker image inspect` |
| `docker kill` latency | median **317 ms** against the compose container (n=100) | `scripts/measure_kill_latency.py` |

Everything above is asserted and printed as JSON by
**`scripts/verify_measurement_host.py`**, which every phase from Phase 10 onward
calls and embeds in its report. It exits non-zero if the context does not name a
unix socket, if the pinned digest does not resolve, if `dmsetup targets` lacks
`flakey`, or if either bind-mount canary fails.

### The device that is not a stable identifier

WSL2 assigns virtual disk device names dynamically. The Phase-8 collections
recorded the distro root as `/dev/sdf`; today it is `/dev/sdd`. **`device` is
therefore not usable as a filesystem identity across boots** — the mount point
and type are. Recorded here because
`experiments/harness/provenance.py::_mount_entry_for` carries `device` for a
good reason (it distinguishes two ext4 filesystems *at one moment*) and a later
reader could otherwise treat a changed device name as a changed disk.

---

## 2. What changed on 2026-09-02, and why

`docs/24-revision-backlog.md` B1 could not be run because **Docker Desktop's
daemon resolved bind-mount sources in the Windows filesystem**. The verbatim
evidence, from `reports/phase-report-10-env-before.md` §1:

```
"Type":"bind","Source":"D:\\personal\\AEP\\Research-paper-AEP\\redis\\phase2.conf"
```

…even though the harness driving that container ran inside WSL with
`cwd=/mnt/d/personal/AEP/Research-paper-AEP`. A `dm-flakey` device assembled
inside the distro exists only at a WSL path and so could not be named as a bind
source.

The sharper form of the same fact, and the one that settles it:
**`/var/lib/docker` did not exist inside `Ubuntu-24.04` at all.** `docker info`
reported it because the answer came from Docker Desktop's own VM. Two
namespaces, and nothing in the distro could reach across.

After the change, the same inspect reads:

```
"Type":"bind","Source":"/mnt/d/personal/AEP/Research-paper-AEP/redis/phase2.conf"
```

and `/var/lib/docker` is a real directory on the distro's ext4.

### Docker Desktop was not removed

It is installed, startable, and its CLI shim is preserved at
`/usr/local/bin/docker-desktop-shim`. This is deliberate: every number in the
manuscript was collected through it, and Phase 10 needed to measure both
runtimes side by side. **Rollback is one command:**

```bash
mv /usr/local/bin/docker-desktop-shim /usr/local/bin/docker
```

After that, `docker` is the shim again (`cd /mnt/d/... && exec docker.exe`) and
Docker Desktop's `desktop-linux` context serves. To come back, remove
`/usr/local/bin/docker` and `docker context use aep-native`.

---

## 3. Reproducing the host from scratch

### 3.1 The distribution

A WSL2 Ubuntu 24.04 distro with `systemd` enabled (`/etc/wsl.conf` →
`[boot]\nsystemd=true`). Everything below runs as `root` inside it.

### 3.2 The runtime

```bash
sudo bash scripts/provision_wsl2_native_docker.sh --match-server-version 29.4.3
```

Idempotent and non-interactive. It:

1. installs Docker's apt keyring and the `noble` stable repository;
2. pins **exact** apt versions and `apt-mark hold`s them, so an unattended
   upgrade cannot move the engine between two runs of the same cell:

   | package | version installed 2026-09-02 |
   |---|---|
   | `docker-ce` | `5:29.4.3-1~ubuntu.24.04~noble` |
   | `docker-ce-cli` | `5:29.4.3-1~ubuntu.24.04~noble` |
   | `containerd.io` | `2.3.4-1~ubuntu.24.04~noble` |
   | `docker-buildx-plugin` | `0.36.1-1~ubuntu.24.04~noble` |
   | `docker-compose-plugin` | `5.5.0-1~ubuntu.24.04~noble` |

3. starts the daemon. **On this host the systemd path was taken** and the script
   prints `START PATH TAKEN: systemd`. It carries a `nohup dockerd` fallback for
   a distro without systemd; that branch is not exercised here and says so;
4. renames the Docker Desktop shim rather than deleting it (§2);
5. creates and selects the `aep-native` context on
   `unix:///var/run/docker.sock`, and refuses to continue if the context does
   not name that socket;
6. pulls the compose file's digest-pinned Redis and **refuses if the digest does
   not match** — it never substitutes a tag;
7. runs both bind-mount canaries (§3.4) and refuses if either fails;
8. writes `/root/phase10/provision-record.json`.

**The version match is exact.** Docker Desktop was serving engine `29.4.3`, git
commit `56be731`; the native engine is `29.4.3`, git commit `56be731` — the same
build. The runtime change is therefore *where the daemon lives*, not *which
daemon it is*. Two lower layers do differ and are recorded rather than elided:
`containerd` v2.3.4 against Docker Desktop's v2.2.3, and `runc` 1.4.3 against
1.3.5.

### 3.3 `dm-flakey`

The module ships with the WSL2 kernel but is **not loaded on a freshly started
distro**, so `dmsetup targets` will not list `flakey` until:

```bash
modprobe dm-flakey        # and `modprobe loop` if /dev/loop-control is absent
```

`experiments/flakey_write_loss.py:563` refuses to measure without it, which is
the correct behaviour and not a failure.

### 3.4 Proving it works

```bash
python scripts/verify_measurement_host.py          # JSON + gates, exit 0
sudo python -m experiments.flakey_write_loss --selftest \
     --root /root/phase10/aep-g2-selftest --redis-server /root/redis-server
```

The canary is the assertion the whole change turns on: write a unique token to a
file, bind-mount **that file** into a container from the pinned image, `cat` it
inside, and compare. The assertion is on the *content*, not the exit status,
because Docker Desktop's failure mode was a silently **empty** destination
rather than an error. Two canaries are run:

| canary | path | filesystem |
|---|---|---|
| `wsl_local` | `/root/aep-phase10-canary/canary.txt` | ext4 — the one B1 needs |
| `drvfs` | `<repo>/.scratch/phase10-canary/canary.txt` | 9p — the repo tree |

Both pass. Under Docker Desktop, `wsl_local` could not have.

### 3.5 The environment the harness needs

```bash
export REDIS_URL=redis://127.0.0.1:6381/15
export AEP_PHASE2_REDIS_INTEGRATION=1
export AEP_PHASE2_REDIS_CONTAINER=aep-phase2-redis72
uv sync --frozen --extra dev --extra cov --extra experiments --extra analysis
docker compose -f compose.phase2.yml up -d --wait
python scripts/verify_redis_semantics.py --url "$REDIS_URL"
```

`git` refuses a tree owned by another uid when run as `root`, which silently
breaks `provenance.harness_version()`. Fix once:

```bash
git config --global --add safe.directory /mnt/d/personal/AEP/Research-paper-AEP
```

---

## 4. Fault-injector timing, and why it is part of the host spec

Phase 8.1 established that in the `redis-kill-preack` regime AEP-full dispatches
**iff** `WAITAOF` returns before Redis dies, and that runs which applied an
effect had **+194.1 ms** higher kill latency (permutation p = 0.00005). The
width of that race is a property of the host's fault injector, so the host
description is incomplete without it.

Measured by `scripts/measure_kill_latency.py`, which calls the harness's own
`redis_kill.kill_redis` so the number is the same instrument the runs used, and
selects a runtime by putting a `docker` symlink at the front of `PATH` so the
code under measurement is byte-identical between arms.

**Interleaved, throwaway container, n = 100 per runtime** — isolates the runtime:

| runtime | min | median | p95 | max | median 95% CI |
|---|---|---|---|---|---|
| Docker Desktop shim | 378 | **423** | 485 | 514 | [418, 431] |
| `aep-native` | 179 | **223** | 257 | 287 | [220, 229] |

Difference of medians **+199.5 ms**, 95% CI **[192.0, 209.0]**, ratio **1.89×**,
and the native distribution is tighter (IQR 22 ms against 39 ms).

**Against the real compose container** — comparable in absolute terms to the
collected runs, because that is the container the runs killed:

| source | n | min | median | max |
|---|---|---|---|---|
| collected runs, Docker Desktop shim (`reports/raw/e1-kill-latency-by-run.csv`) | 300 | 681.8 | **961.8** | 1673.9 |
| `aep-native`, 2026-09-02 | 100 | 264 | **317** | 397 |

> **Fault delivery on the native runtime is about three times faster and far
> tighter.** The race window that decides `\UnwantedPrevented{}` is
> correspondingly narrower. **Nothing in the manuscript is re-analysed on this
> basis and no existing number is adjusted** — Phase 10 establishes the
> distribution only. What it implies for Table IX is WS-3's decision.

Two caveats, stated rather than left to be discovered:

- The historical figure was recorded *during live protocol runs*, with a worker
  mid-execution; the Phase-10 figure was measured on an otherwise idle stack.
  The comparison is like-for-like in target and instrument, not in host load.
- `\ProcessKillWindowMin`/`Max` (419–992 ms) is **not** this quantity. It is the
  write-to-death window of the durability probe
  (`reports/raw/e1-durability-window.txt`), which kill latency dominates but
  does not equal. Do not compare against it.

From Phase 10 onward, `experiments/harness/provenance.py` writes this
distribution into **every** run's `environment.docker_kill_latency`, including
the regimes that issue no `docker kill` at all — `session-3`'s fault is a worker
`SIGKILL` the process sends to itself (`injector.py:81-82`), which has no
cross-boundary landing latency, but the host it ran on still had one, and
whether two collections are comparable turns on that.

---

## 5. Which numbers in the paper predate this host

**All of them.** Every number in `paper/generated/*.tex` as of commit `cfb6dbe`
was collected under **Docker Desktop**, with Redis's `/data` on a named Docker
volume inside Docker Desktop's VM.

`redis_storage_backing`, the field Phase 8.2 requires later phases to compare
against, in the two eras:

| | frozen collections | Phase 10 onward |
|---|---|---|
| mount type | `volume` | `volume` (unchanged) |
| name | `aep-phase2_redis-data` | `aep-phase2_redis-data` (unchanged) |
| source path | `/var/lib/docker/volumes/aep-phase2_redis-data/_data` | same path (unchanged) |
| **which kernel owns it** | **Docker Desktop's VM** | **`Ubuntu-24.04`** |
| **filesystem under it** | **not observable from the distro** | `/dev/sdd` ext4, `rw,relatime,discard,errors=remount-ro,data=ordered` |

The mount *type* is identical and the path string is identical. What changed is
the namespace — and before the change the filesystem under that path could not
be read from the distro at all, which is why no frozen run records it.

**A separate and larger gap, established by Phase 10 and not fixed by it:** no
*tracked* file in this repository records `results_root_filesystem` or
`redis_storage_backing` for any collection, and the 330 run directories present
in the working clone carry no `environment` block at all. See
`scripts/survey_storage_backing.py` and the phase report's section *"Storage
backing across existing collections"*. That section also lists the **12
paragraphs of `paper/sections/06-evaluation.tex` that put numbers from different
results roots side by side**. Phase 10 establishes this; what to do about it is
the next phase's decision.

---

## 6. The runtime-confound replication

See `reports/phase-report-10-wsl2-native-docker-2026-09-02.md`, section
*Replication*, and the pre-registration
`reports/phase-report-10-prediction-2026-09-02.md`, which was committed and
pushed before any Phase 10 run existed.

Summary, with the phase report authoritative for the detail:

- **96 runs, 960 executions**, two arms (ext4 and drvfs), 18 matched + 30 powered
  runs each.
- **Matched arms, 18 clusters a side:** `known_ambiguity_rate` differs from the
  frozen cell by **−0.0111 [−0.0778, +0.0556]** (ext4) and **+0.0000
  [−0.0667, +0.0667]** (drvfs) — both **conclusively inside the ±15 pp margin**.
  Undetected duplicates, lost effects and unverified failures are **0/180** in
  both arms exactly as in the frozen cell; recovery success is 150/180 in all
  three.
- **Powered cell against the frozen cell: INCONCLUSIVE — UNDERPOWERED**, exactly
  as pre-registered. The frozen side has three run-clusters (6/10, 4/10, 0/10)
  and floors the half-width at ≈ 0.29 whatever the new arm's size.
- **ext4 against drvfs, 30 clusters a side: +0.0000 [−0.0700, +0.0667]** — the
  one conclusive comparison of the phase. **The filesystem does not move this
  cell.**
- **Zero undetected duplicates and zero lost effects across all 960
  executions.**

**Read as a whole: no evidence that the container runtime is a confound for the
rates, and a conclusive result that the filesystem is not.** No timing claim is
made from these runs, and none can be — see §7.

---

## 7. What this host still is not

Recorded so that the platform threat in `paper/sections/08-threats.tex` §C(c)
can be updated honestly rather than optimistically.

- **Still one machine, still WSL2, still Windows underneath.** The native engine
  removes a *namespace* problem, not the single-host external-validity problem
  the audit raises as A4.
- **Still no verified suspend declaration.** `AEP_HARNESS_SUSPEND_DISABLED` is
  unset, and amendment E5 is explicit that a host that merely did not happen to
  suspend cannot be distinguished from one that cannot. Runs collected without
  it contribute counts, never durations.
- **Fault delivery reliability is not addressed by this change.**
  `docs/24-revision-backlog.md` B1's Phase-8.4 addendum requires a second host
  because the hard kill stopped landing in 2 of 120 runs after 360 consecutive
  successes. A native daemon in the *same* WSL2 kernel does nothing about that,
  and B1 must still report its own non-delivery count as a first-class number.
- **The repo tree is still on 9p/drvfs.** Collections that must match the frozen
  `matrix` cell's filesystem have to write outside the tree and be copied in;
  Phase 10 does exactly that and records both paths.
