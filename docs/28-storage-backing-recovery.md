# Storage backing, recovered retrospectively

**Phase 11, 2026-09-03.** Produced by `scripts/recover_storage_backing.py`;
raw output `reports/raw/phase11-storage-backing-recovery.{txt,json}`.

---

## What this document is, and what it is not

`docs/24-revision-backlog.md` B1's Phase-8.2 addendum requires B1 to read
`redis_storage_backing` from its own runs **and from the frozen ones**, confirm
they differ, and say how. Phase 10 established that this is not possible from
the repository: no tracked file records that field for any collection, and
`experiments/harness/provenance.py` — which records it — did not exist until
`e67efd1` (2026-08-27). Every collection before that carries no `environment`
block at all.

That is not the same as unrecoverable. It means the answer lives in this host's
live state rather than in a field, and Phase 10 also established that this host
is degrading. This document extracts what is still extractable.

**It establishes facts and does nothing else.** No manuscript file is edited, no
frozen cell is re-analysed, nothing is corrected. What the manuscript should say
about any of this is the next phase's decision.

---

## 1. The evidence classes, and why each is worth what it is worth

Four classes were used, in decreasing strength. The classification rule is the
one the phase prompt sets: **an inference is never promoted to a determination**,
including where the inference is, in this author's judgement, obviously right.

| # | evidence | what it can support |
|---|---|---|
| 1 | the run's own `environment` block | **DETERMINED.** The harness recorded it at run construction, from `docker inspect` and `/proc/mounts`. |
| 2 | an absolute path inside the collection's own artifacts | **DETERMINED** for the collection *path*. `results_root` is recorded relative to the process's working directory, so an absolute path to the harness source fixes that directory. |
| 3 | inode change time against modification time | **INFERRED.** Neither ext4 nor this host's 9p mount lets userspace set `ctime`; `cp -a` restores `mtime` and stamps `ctime` with the copy. `ctime == mtime` across a whole collection means it was written where it sits. |
| 4 | a phase report's own statement | **INFERRED at best.** A report is a claim, not a measurement. Used only where 1–3 are silent, and always attributed. |

### Class 3 was checked before it was relied on

Depending on an inode field across two filesystems — one of them a 9p mount onto
NTFS — without testing it would be the shape of defect `docs/24-revision-backlog.md`
B19 records. `scripts/recover_storage_backing.py --probe-ctime` writes a file,
back-dates its `mtime`, and re-reads both fields on each filesystem:

```
=== is ctime usable on each filesystem? ===
  /root/.aep-ctime-probe                                     ext4       usable=True
  /mnt/d/personal/AEP/Research-paper-AEP/.scratch/.ctime-probe 9p         usable=True
```

**Birth time is not available on 9p and this limits §3 below.** `statx` reports
`Birth:` on ext4 and `Birth: -` on the drvfs mount:

```
--- /root/.aep-btime-probe/a ---
Modify: 2026-09-03 10:53:08.760411449 +0500
Change: 2026-09-03 10:53:08.760411449 +0500
 Birth: 2026-09-03 10:53:08.760411449 +0500
--- .scratch/.btime-probe/a ---
Modify: 2026-09-03 10:53:08.771998400 +0500
Change: 2026-09-03 10:53:08.771998400 +0500
 Birth: -
```

A copy creates a new inode with a new birth time; a `chmod` does not. On ext4
that distinction is readable. On the drvfs mount it is not — which is exactly
where it was needed.

---

## 2. The mounts as they are today, for reference

```
/               ext4  on /dev/sdd
/mnt/d          9p    on D:\134   (drvfs)
/var/lib/docker ext4  on /dev/sdd  (mount point /var/lib/docker)
```

**`/dev/sdd` is not an identity.** The Phase-8 collections recorded the same
distro root as `/dev/sdf`. WSL2 assigns these dynamically, and a comparison keyed
on `device` would read two identical filesystems as different. Phase 10 recorded
this; it is repeated here because it is load-bearing for the table below.

---

## 3. Per root

Twenty collection roots, in the order `ARCHIVE-METADATA.json` lists them.

### 3.1 `matrix` — 432 runs — **every outcome rate in the manuscript**

* Source: `/root/aep/experiments/results/matrix`
* mtime window `2026-08-06T06:17:35Z .. 2026-08-10T06:41:41Z`
* ctime window **identical to the mtime window, to the second, across all 432**

**Collection path: DETERMINED — `/root/aep/experiments/results/matrix`.**

The collection's own orchestrator log records absolute paths. `matrix-progress.jsonl`
captured a Python traceback into a `traceback` field, verbatim:

```
"traceback": "Traceback (most recent call last):\n
  File \"/root/aep/experiments/run_matrix.py\", line 862, in execute_plan\n
    outcome = await run_once(\n              ^^^^^^^^^^^^^^^\n
    ...<33 lines>...\n    )\n    ^\n
  File \"/root/aep/experiments/harness/orchestrate.py\", line 96, in ru…
```

Fifteen distinct absolute paths appear in that one file, all under `/root/aep`:

```
/root/aep/.venv/lib/python3.13/site-packages/redis/_parsers/base.py
/root/aep/experiments/baselines/b4_durable_workflow.py
/root/aep/experiments/harness/composition.py
/root/aep/experiments/harness/config.py
/root/aep/experiments/harness/orchestrate.py
/root/aep/experiments/harness/reconcile.py
/root/aep/experiments/harness/runner.py
/root/aep/experiments/mock_api/supervisor.py
/root/aep/experiments/run_matrix.py
                                    … and 6 more
```

The run configs record `"results_root": "experiments/results/matrix"` — relative.
An absolute path to `run_matrix.py` fixes the working directory as `/root/aep`,
so the relative root resolves to `/root/aep/experiments/results/matrix`, which is
where the 432 directories are. Corroborated by class 3: `ctime == mtime` on every
one of the 432, so they were written here rather than copied here.

**Filesystem: INFERRED — ext4, the distro root.** This is the strongest inference
available and it is still an inference. Nothing the run wrote records the
filesystem. The chain is: the path is `/root/…`, which is under `/`; `/` is ext4
today; and the Phase-8 collections' own recorded `environment` block independently
attests `/` as `ext2/ext3` on 2026-08-28. No step of that is a field the harness
recorded on 2026-08-06.

> **This is an upgrade on Phase 10, which reported `matrix` as UNDETERMINED on
> both counts.** Phase 10's own words were that `provenance.py`'s docstring claim
> — "the paper's cell was collected in the WSL-native tree on ext4" — was "a claim
> in prose, not a recorded field", supported only by where the bytes sit now. The
> traceback and the inode evidence are better than that: they are measurements of
> the collection, made by the collection.

**`redis_storage_backing`: UNDETERMINED as a recorded field; the mount *type* is
DETERMINED and the physical location is INFERRED.** See §4.

### 3.2 `fsync-always` — 6 runs — every `always` latency and throughput number

* Source: `/root/aep/experiments/results/fsync-always`
* mtime `2026-08-07T09:38:47Z .. 2026-08-07T11:08:53Z`, ctime identical → written in place
* No absolute path anywhere in its artifacts (it has `matrix-plan.json` and
  `matrix-progress.jsonl`, and neither recorded a traceback)

**Collection path: INFERRED — `/root/aep/experiments/results/fsync-always`**, from
class 3 alone. **Filesystem: INFERRED — ext4, the distro root**, by the same chain
as §3.1 minus the traceback.

### 3.3 `voided` — 1 run — the excluded oracle-disagreement run

* Source: `/root/aep/experiments/results/voided`, with its `README.md`
* mtime = ctime = `2026-08-07T12:42:03Z` → written in place

**Path and filesystem: INFERRED**, same chain as §3.2.

### 3.4–3.7 `b2-2026-08-21`, `b2-s1`, `b2-s2`, `b2-s3` — 60 runs each — `\ReplicationPrevented*`

* Source: the working clone, `experiments/results/b2-*-2026-08-21`, on the 9p mount
* No `environment` block in any of the 240 runs
* No absolute path in any artifact
* **mtimes 2026-08-21; ctimes all at `2026-09-01T06:46:54Z .. 06:46:55Z`**

```
b2-2026-08-21     mtime 2026-08-21T15:11:43Z .. 15:51:35Z   ctime 2026-09-01T06:46:54Z .. 06:46:55Z
b2-s1-2026-08-21  mtime 2026-08-21T16:17:13Z .. 16:52:35Z   ctime 2026-09-01T06:46:55Z
b2-s2-2026-08-21  mtime 2026-08-21T16:55:54Z .. 17:30:52Z   ctime 2026-09-01T06:46:55Z
b2-s3-2026-08-21  mtime 2026-08-21T17:33:06Z .. 18:08:06Z   ctime 2026-09-01T06:46:55Z
```

**Filesystem: UNDETERMINED. Collection path: UNDETERMINED.**

Every one of the 240 inodes was changed at one instant ten days after the write.
Class 3 therefore says the opposite of what it says for §3.1–3.3: **where these
bytes sit now is not evidence of where they were written.**

What the operation was cannot be settled here, and this document will not guess:

* **It was not a copy that created new directory entries.** `b2-s1`, `b2-s2` and
  `b2-s3`'s parent directories have `mtime 2026-08-27T09:51:36Z` — *before* the
  ctime event. A copy that created 60 subdirectories on 2026-09-01 would have set
  the parent's mtime to 2026-09-01. It did not.
* **It could still have been an overwriting `cp -a` into directories that already
  existed**, which restores `mtime`, stamps `ctime`, and leaves the parent's
  `mtime` alone.
* **Birth time would separate the two, and 9p does not report it** (§1).

What is available is class 4. `reports/phase-report-8-1-0-2026-08-27.md:296-299`
states the filesystem for all four, in a table, verbatim:

```
| session                  | filesystem | AEP median kill latency | AEP applied |
| **2026-08-07** (paper's) | **ext4**   | **858.9 ms**            | **10**/30   |
| `b2-s2-2026-08-21`       | drvfs      | 880.6 ms                | 4/30        |
| `b2-s3-2026-08-21`       | drvfs      | 945.0 ms                | 7/30        |
| `b2-s1-2026-08-21`       | drvfs      | 1025.2 ms               | 12/30       |
| `b2-2026-08-21` (P9-B)   | drvfs      | 1215.7 ms               | 20/30       |
```

That table is a claim in a report. It is recorded here, attributed, and **not
used to raise the confidence above UNDETERMINED** — because the report gives no
source for the `filesystem` column, and the only evidence this phase can find
that would have supported it is the same "where the bytes sit" reasoning that the
2026-09-01 inode event invalidates.

> **This is the one place where Phase 11 makes the picture worse rather than
> better.** Phase 10 recorded these four roots as UNDETERMINED for lack of a
> field. Phase 11 finds an inode event that also removes the fallback, and finds
> a phase report asserting a value it does not source. Four roots, 240 runs,
> carrying `\ReplicationPrevented\*` — and §VI compares them against `matrix`,
> whose filesystem is now INFERRED as ext4.

### 3.8–3.13 `b2-paired-s1`, `b2-paired-v2-s1…s4`, `b2-paired-v2-s2-aborted` — Phase 8.4

* Source: `/root/aep-phase8/experiments/results/…`
* **All 120/120 (and 26/26) runs carry an `environment` block**
* ctime == mtime throughout → written in place, corroborating the recorded value

**Filesystem: DETERMINED**, verbatim from `run-config.json`:

```json
"results_root_filesystem": {
  "device": "/dev/sdf",
  "is_drvfs": false,
  "mount_point": "/",
  "path": "experiments/results/b2-paired-v2-s1-2026-08-28",
  "type": "ext2/ext3"
}
```

**`redis_storage_backing`: DETERMINED as a recorded field**, verbatim:

```json
"redis_storage_backing": {
  "container": "aep-phase2-redis72",
  "mount_type": "volume",
  "name": "aep-phase2_redis-data",
  "read_only": false,
  "source": "/var/lib/docker/volumes/aep-phase2_redis-data/_data"
}
```

**But see §4: that `source` string does not name a path in this distro.**

### 3.14 `b2-paired-v2-s2-operator-aborted-2026-08-28` — 16 runs

Same as §3.8–3.13 on every count: `environment` block present on all 16,
ctime == mtime, filesystem and backing **DETERMINED**. No tracked analysis
product derives from it and no manuscript number depends on it.

### 3.15–3.18 The four Phase 10 replication arms

**Filesystem and backing: DETERMINED**, and additionally corroborated three ways
that no earlier collection has — the `environment` block, `matrix-plan.json`
recording the results root as an **absolute** path, and each root's
`COLLECTION-PROVENANCE.json` carrying the full `verify_measurement_host.py`
output.

| arm | recorded filesystem | recorded backing |
|---|---|---|
| ext4 matched / powered | `ext2/ext3`, `/dev/sdd`, mount `/`, `is_drvfs=false` | volume `aep-phase2_redis-data` at `/var/lib/docker/volumes/…/_data` |
| drvfs matched / powered | `v9fs`, `D:\134`, mount `/mnt/d`, `is_drvfs=true` | the same volume |

### 3.19–3.20 The two Phase 10 VOIDED trees

**Filesystem and backing: DETERMINED** by the same three routes. Recorded because
a voided collection is evidence about the instrument; the Phase 10 report cites
them for its same-day Docker-Desktop-served clock-divergence comparison.

### 3.21 The two probes, which have no run directories

**`g2-flakey-write-loss*.json` — backing DETERMINED, and it is the only
collection whose backing is *deliberately different*.** The probe's own JSON
records the device-mapper table and the server, verbatim:

```json
"dm_table_drop":  "0 524288 flakey /dev/loop0 0 0 1 1 drop_writes",
"dm_table_pass":  "0 524288 flakey /dev/loop0 0 1 0",
"redis_version":  "Redis server v=7.2.5 sha=00000000:0 malloc=jemalloc-5.3.0 bits=64 build=5259b0772c1000e1"
```

A **native** `redis-server`, not the pinned container, on an ext4 built over a
`dm-flakey` target over `/dev/loop0`. No Docker in the path at all, so no volume
and no daemon.

**`reports/raw/e1-durability-window.txt` — backing INFERRED (§4).** Its header
records the container and the mechanism but not the volume:

```
  platform   Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.39
  container  aep-phase2-redis72
  url        redis://127.0.0.1:6381/15
  trials     10
  mechanism  docker kill -s KILL  (SIGKILL to the container's PID 1)
```

It used the compose container, so it used the compose volume.

---

## 4. The finding that the recorded field does not, by itself, support

**`redis_storage_backing.source` is byte-identical across the Phase 8 and the
Phase 10 collections and denotes two different filesystems on two different
machines.**

Both record:

```
/var/lib/docker/volumes/aep-phase2_redis-data/_data
```

For the Phase 10 collections that is a path in this distro, on `/dev/sdd` ext4,
proven by `verify_measurement_host.py`'s embedded output. For the Phase 8
collections it is a path **inside the `docker-desktop` virtual machine**, because
that is the daemon that answered `docker inspect`. Phase 10's pre-change capture
recorded both halves of that, verbatim, from
`reports/raw/phase10-env-before-docker-desktop.txt`:

```
=== docker info (fuller, for the record) ===
 Kernel Version: 6.6.114.1-microsoft-standard-WSL2
 Operating System: Docker Desktop
 Name: docker-desktop
 Docker Root Dir: /var/lib/docker
```

```
=== df -T for /var/lib/docker ===
df: /var/lib/docker: No such file or directory
```

The daemon reported its root as `/var/lib/docker` while that path **did not exist
in the distro at all**. `provenance.py` records what `docker inspect` returns; it
has no way to know whose filesystem the answer is about.

**Consequence, stated narrowly.** A later comparison keyed on
`redis_storage_backing` would read a Phase 8 collection and a Phase 10 collection
as sharing a backing. They do not. This is the same defect shape as the device
name in §2 — a recorded identifier that is not an identity — and it is exactly
what B1's Phase-8.2 addendum exists to prevent.

### What is DETERMINED about the backing of the seven roots with no `environment` block

The *mount type* is determined even where the recorded field is absent.
`compose.phase2.yml` has declared the AOF's directory as a **named Docker
volume** since `2fefe5e` (2026-08-05T18:00:31+05:00) — before the first run of
any collection, at `2026-08-06T06:17:35Z` — and the file has only two commits in
its whole history, both predating that run:

```yaml
    volumes:
      - ./redis/phase2.conf:/usr/local/etc/redis/redis.conf:ro
      - redis-data:/data
…
volumes:
  redis-data:
```

So for `matrix`, `fsync-always`, `voided`, the four `b2-*-2026-08-21` roots and
the `e1` probe:

* **mount type: DETERMINED** — a named Docker volume `aep-phase2_redis-data`
  mounted at `/data`, never a bind mount and never the container's writable layer.
* **physical location: INFERRED** — inside the `docker-desktop` VM's own
  filesystem. The inference is that the native Docker Engine did not exist on this
  host until Phase 10 installed it on 2026-09-02 (`scripts/provision_wsl2_native_docker.sh`,
  `/root/phase10/provision-record.json`), and `/usr/local/bin/docker` before that
  was the shim in `scripts/wsl_docker_shim.sh` that `exec`s `docker.exe`.

---

## 5. Summary table

`F` = `results_root_filesystem`. `B` = `redis_storage_backing` as a recorded field.

| root | runs | F | B | where written |
|---|---|---|---|---|
| `matrix` | 432 | **INFERRED** ext4 | UNDETERMINED | **DETERMINED** `/root/aep/…` (traceback) |
| `fsync-always` | 6 | **INFERRED** ext4 | UNDETERMINED | INFERRED `/root/aep/…` (ctime) |
| `voided` | 1 | **INFERRED** ext4 | UNDETERMINED | INFERRED `/root/aep/…` (ctime) |
| `b2-2026-08-21` | 60 | **UNDETERMINED** | UNDETERMINED | **UNDETERMINED** |
| `b2-s1-2026-08-21` | 60 | **UNDETERMINED** | UNDETERMINED | **UNDETERMINED** |
| `b2-s2-2026-08-21` | 60 | **UNDETERMINED** | UNDETERMINED | **UNDETERMINED** |
| `b2-s3-2026-08-21` | 60 | **UNDETERMINED** | UNDETERMINED | **UNDETERMINED** |
| `b2-paired-s1-2026-08-28` | 120 | DETERMINED ext4 `/dev/sdf` | DETERMINED | DETERMINED `/root/aep-phase8/…` |
| `b2-paired-v2-s1…s4-2026-08-28` | 120 each | DETERMINED ext4 `/dev/sdf` | DETERMINED | DETERMINED `/root/aep-phase8/…` |
| `b2-paired-v2-s2-aborted` | 26 | DETERMINED ext4 `/dev/sdf` | DETERMINED | DETERMINED |
| `b2-paired-v2-s2-operator-aborted` | 16 | DETERMINED ext4 `/dev/sdf` | DETERMINED | DETERMINED |
| Phase 10 ext4 arms | 18 + 30 | DETERMINED ext4 `/dev/sdd` | DETERMINED | DETERMINED |
| Phase 10 drvfs arms | 18 + 30 | DETERMINED v9fs `D:\134` | DETERMINED | DETERMINED |
| Phase 10 VOIDED trees | 18 + 23 | DETERMINED ext4 `/dev/sdd` | DETERMINED | DETERMINED |
| `g2-flakey-write-loss*` | — | n/a (no results root) | **DETERMINED** dm-flakey/loop0, native `redis-server` | n/a |
| `e1-durability-window` | — | n/a | UNDETERMINED (mount type determined) | n/a |

**Counts across the 20 archived roots:** filesystem **13 DETERMINED, 3 INFERRED,
4 UNDETERMINED**; recorded backing **13 DETERMINED, 7 UNDETERMINED**.

---

## 6. Phase 10's §VI finding, restated with the recovered information

Phase 10 listed **12 paragraphs of `paper/sections/06-evaluation.tex`** that put
numbers from two or more results roots side by side, and reported that in all but
one of them **both** sides were UNDETERMINED. Its macro-to-root mapping is reused
unchanged; only the confidences move.

| file:line | roots spanned | filesystem status after recovery | AOF backing after recovery |
|---|---|---|---|
| `06-evaluation.tex:340-349` | `matrix` + `b2-paired-v2-*` | INFERRED ext4 vs **DETERMINED** ext4 | both: named volume, docker-desktop VM (INFERRED) |
| `06-evaluation.tex:385-397` | `matrix` + e1-durability-window | INFERRED ext4 vs n/a | both: named volume, docker-desktop VM (INFERRED) |
| **`06-evaluation.tex:406-419`** | `matrix` + `b2-*-2026-08-21` | INFERRED ext4 vs **UNDETERMINED** | both: named volume, docker-desktop VM (INFERRED) |
| **`06-evaluation.tex:421-438`** | `b2-*-2026-08-21` + e1-kill-latency | **UNDETERMINED** vs n/a | both: named volume, docker-desktop VM (INFERRED) |
| **`06-evaluation.tex:440-447`** | `b2-*-2026-08-21` + e1-kill-latency | **UNDETERMINED** vs n/a | both: named volume, docker-desktop VM (INFERRED) |
| **`06-evaluation.tex:462-468`** | `matrix` + `b2-*-2026-08-21` | INFERRED ext4 vs **UNDETERMINED** | both: named volume, docker-desktop VM (INFERRED) |
| `06-evaluation.tex:525-534` | g2-flakey + e1-durability-window | n/a | **DETERMINED and DELIBERATELY DIFFERENT** — dm-flakey/native server vs named volume |
| `06-evaluation.tex:558-568` | g2-flakey + e1-durability-window | n/a | **DETERMINED and DELIBERATELY DIFFERENT** — as above |
| `06-evaluation.tex:623-631` | `matrix` + `fsync-always` | INFERRED ext4 vs INFERRED ext4 | both: named volume, docker-desktop VM (INFERRED) |
| `06-evaluation.tex:633-640` | `matrix` + `fsync-always` | INFERRED ext4 vs INFERRED ext4 | both: named volume, docker-desktop VM (INFERRED) |
| `06-evaluation.tex:648-658` | `matrix` + `fsync-always` | INFERRED ext4 vs INFERRED ext4 | both: named volume, docker-desktop VM (INFERRED) |
| `06-evaluation.tex:704-715` | `matrix` + `fsync-always` | INFERRED ext4 vs INFERRED ext4 | both: named volume, docker-desktop VM (INFERRED) |

### The three numbers the next phase needs

1. **Paragraphs still spanning an UNDETERMINED *filesystem*: four —
   `406-419`, `421-438`, `440-447`, `462-468`.** All four are the ones that draw
   on `b2-*-2026-08-21`. Phase 10 counted eleven; the difference is entirely the
   recovery of `matrix` and `fsync-always` in §3.1–3.2.

   `462-468` is the paragraph carrying `\UnwantedPrevented{}` and the
   `\ReplicationAepMin`–`Max` range — the paper's prevention result.

2. **Paragraphs spanning an UNDETERMINED *AOF backing*: zero.** Not because it is
   recorded — it is recorded for none of them — but because §4 determines the
   *mount type* for every root the manuscript quotes, from the pinned compose file,
   and infers one common physical location for all of them. **Every collection the
   manuscript compares was served by the same named Docker volume inside the same
   `docker-desktop` VM.** That is a uniformity, not a difference, and it is the
   opposite of what Phase 10 had to assume.

3. **The two paragraphs whose backing difference is deliberate — `525-534` and
   `558-568` — now have it DETERMINED on both sides.** The write-loss probe ran a
   native `redis-server` on a `dm-flakey` device with no Docker in the path; the
   process-kill probe ran the pinned container on the named volume. The manuscript
   compares them precisely because the fault differs, and the storage difference
   is part of that fault. It is now evidenced rather than assumed.

**No claim is made here that any of these comparisons is wrong.** The claim is
the narrow one B1's addendum requires: the property that could move them is now
stated, per root, with its confidence, instead of being assumed comparable.

---

## 7. What is still not recoverable, and what would have prevented it

* **The four `b2-*-2026-08-21` roots' filesystem.** Nothing on this host settles
  it. The 2026-09-01 inode event removed the only fallback, and 9p does not
  report birth time. Only a record made at collection time would have done it —
  which is what `provenance.py` now is, six days too late for these.
* **The physical location of the `docker-desktop` VM's volume directory.** The
  daemon is no longer the selected one; the VHDX is a Windows-side artifact this
  phase did not touch.
* **`redis_storage_backing` for the seven pre-8.2 roots, as a *recorded* field.**
  It will never exist. §4 substitutes an argument for it and labels it as one.

**The general lesson, which is already B1's:** *detected, never declared*. Every
determination in §3 that holds rests on a field the harness wrote at run
construction, or on an absolute path a crash happened to leave behind. The
collections that recorded nothing are recoverable only by accident, and one of
the four accidents that could have saved `b2-*-2026-08-21` was destroyed by a
routine file operation ten days later.
