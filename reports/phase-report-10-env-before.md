# Phase 10, step 2 — the measurement host as the paper currently describes it

**Captured** 2026-09-02T09:42:26Z, at commit `a9bf5598e6dcc31b5979c88fbb395f3700a1ae90`,
**before any change to the environment.** Nothing in this file is a claim; it is the record
that `paper/sections/08-threats.tex:303-314` §C(c) refers to, preserved before it is replaced.

**Full raw capture:** `reports/raw/phase10-env-before-docker-desktop.txt` (412 lines, 30
sections, `EXIT=0`). Everything quoted below is copied from it verbatim. The capture script
is `.scratch/phase10-capture-env-before.sh` (untracked scratch; its content is reproduced in
`docs/27-measurement-host.md`).

---

## 1. The one line this whole phase exists because of

```
=== docker inspect aep-phase2-redis72 -- HostConfig.Binds VERBATIM ===
["D:\\personal\\AEP\\Research-paper-AEP\\redis\\phase2.conf:/usr/local/etc/redis/redis.conf:ro","aep-phase2_redis-data:/data:rw"]
```

```
=== docker inspect aep-phase2-redis72 -- Mounts VERBATIM ===
[{"Type":"volume","Name":"aep-phase2_redis-data","Source":"/var/lib/docker/volumes/aep-phase2_redis-data/_data","Destination":"/data","Driver":"local","Mode":"rw","RW":true,"Propagation":""},{"Type":"bind","Source":"D:\\personal\\AEP\\Research-paper-AEP\\redis\\phase2.conf","Destination":"/usr/local/etc/redis/redis.conf","Mode":"ro","RW":false,"Propagation":"rprivate"}]
```

The harness that drives this container runs **inside WSL**, as `root`, with
`cwd=/mnt/d/personal/AEP/Research-paper-AEP`. The daemon nevertheless records the bind source
as `D:\personal\AEP\Research-paper-AEP\redis\phase2.conf` — a **Windows** path. This is
`docs/24-revision-backlog.md` B1's "What blocked it here, exactly", reproduced exactly as
that entry states it, and it is why a `dm-flakey` device assembled inside WSL cannot be named
as a bind source today.

**And the field Phase 8.2 requires later phases to compare against:**

| field | value under Docker Desktop |
|---|---|
| `redis_storage_backing.mount_type` | `volume` |
| `redis_storage_backing.name` | `aep-phase2_redis-data` |
| `redis_storage_backing.source` | `/var/lib/docker/volumes/aep-phase2_redis-data/_data` |
| filesystem of that source | **not observable from this distro** — see §5 |

---

## 2. Docker

```
=== docker version ===
Client:
 Version:           29.4.3
 API version:       1.54
 Go version:        go1.26.2
 Git commit:        055a478
 Built:             Wed May  6 17:10:36 2026
 OS/Arch:           windows/amd64
 Context:           desktop-linux

Server: Docker Desktop 4.74.0 (227015)
 Engine:
  Version:          29.4.3
  API version:      1.54 (minimum version 1.40)
  Go version:       go1.26.2
  Git commit:       56be731
  Built:            Wed May  6 17:07:37 2026
  OS/Arch:          linux/amd64
  Experimental:     false
 containerd:
  Version:          v2.2.3
  GitCommit:        77c84241c7cbdd9b4eca2591793e3d4f4317c590
 runc:
  Version:          1.3.5
  GitCommit:        v1.3.5-0-g488fc13e
 docker-init:
  Version:          0.19.0
  GitCommit:        de40ad0
```

**`OS/Arch: windows/amd64` on the client is the whole story in one field.** The `docker` the
harness invokes from inside Linux is a Windows executable.

```
=== docker context ls ===
NAME              DESCRIPTION                               DOCKER ENDPOINT                             ERROR
default           Current DOCKER_HOST based configuration   npipe:////./pipe/docker_engine
desktop-linux *   Docker Desktop                            npipe:////./pipe/dockerDesktopLinuxEngine

=== docker context show ===
desktop-linux
```

```
=== docker info | grep -i 'root dir|storage driver|server version' ===
 Server Version: 29.4.3
 Storage Driver: overlayfs
 Docker Root Dir: /var/lib/docker
```

```
=== docker info (fuller, for the record) ===
 Cgroup Driver: cgroupfs
 Cgroup Version: 2
  cgroupns
 Kernel Version: 6.6.114.1-microsoft-standard-WSL2
 Operating System: Docker Desktop
 Architecture: x86_64
 Total Memory: 15.35GiB
 Name: docker-desktop
 Docker Root Dir: /var/lib/docker
```

`Docker Root Dir: /var/lib/docker` and `Name: docker-desktop` are reported **from inside
Docker Desktop's own VM**, not from `Ubuntu-24.04`. §5 shows that path does not exist in the
distro the harness runs in. That is the namespace split this phase closes.

### How `docker` is reached from the distro

Docker Desktop's WSL integration was **never enabled** for `Ubuntu-24.04`. A hand-written
shim supplies `docker` instead, and it shadows everything else on `PATH`:

```
=== which -a docker ===
/usr/local/bin/docker
/mnt/c/Program Files/Docker/Docker/resources/bin/docker

=== cat /usr/local/bin/docker  (the Docker Desktop shim being replaced) ===
#!/usr/bin/env bash
# Forward to Docker Desktop, from the Windows-side tree.
cd /mnt/d/personal/AEP/Research-paper-AEP 2>/dev/null || true
exec docker.exe "$@"
```

Installed by `scripts/wsl_docker_shim.sh`. It is recorded here because it is part of the
environment being replaced, and because **every `docker kill` the paper timed went through
it** — a `cd` into `/mnt/d` followed by an `exec` of a Windows binary across the WSL/Windows
boundary. That is the instrument behind the 419–992 ms figure, and step 6b measures what it
costs.

### The pinned image, as actually resolved

```
=== docker inspect aep-phase2-redis72 -- Image + digest ===
Config.Image      : redis:7.2.5-alpine@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44
Image (resolved)  : sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44
RepoDigests       : ["redis@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44"]
RepoTags          : ["redis@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44"]

=== docker images --digests (redis, toxiproxy) ===
REPOSITORY                                      TAG                       DIGEST                                                                    IMAGE ID       CREATED         SIZE
ghcr.io/shopify/toxiproxy                       2.12.0                    sha256:9378ed52a28bc50edc1350f936f518f31fa95f0d15917d6eb40b8e376d1a214e   9378ed52a28b   17 months ago   26.3MB
redis                                           7.2.5                     sha256:3aaec283e6e593bde528077d60280ac1589887067a39273348860837c9346d7e   3aaec283e6e5   2 years ago     175MB
redis                                           <none>                    sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44   6aaf3f5e6bc8   2 years ago     60MB
```

The digest matches `compose.phase2.yml:5` exactly. **Note for the native-engine comparison:**
the image carries **no `redis:7.2.5-alpine` tag** on this host — compose pulled it by digest,
so `docker image inspect redis:7.2.5-alpine` fails with *"No such image"*. Any digest check
must resolve through the container's `.Image`, not through the tag. `verify_measurement_host.py`
is written that way.

### The container

`Created: 2026-08-13T07:19:04.157654294Z`, `StartedAt: 2026-09-02T09:39:16.745840673Z`
(restarted when Docker Desktop was started for this capture),
`Id: 4c30a5546934beb80f4cd07060734fe95acee02ea318cf2fbf9eee44b550d7be`.
`docker compose -f compose.phase2.yml up -d --wait` reported both services `Healthy`.

---

## 3. Kernel and distribution

```
=== uname -a ===
Linux KP248 6.6.114.1-microsoft-standard-WSL2 #1 SMP PREEMPT_DYNAMIC Mon Dec  1 20:46:23 UTC 2025 x86_64 x86_64 x86_64 GNU/Linux

=== WSL kernel version (from uname -r) ===
6.6.114.1-microsoft-standard-WSL2
```

```
=== cat /etc/os-release ===
PRETTY_NAME="Ubuntu 24.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04.4 LTS (Noble Numbat)"
VERSION_CODENAME=noble
ID=ubuntu
ID_LIKE=debian
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
UBUNTU_CODENAME=noble
LOGO=ubuntu-logo
```

```
=== systemd? ===
systemd
running
```

**PID 1 is `systemd` and `systemctl is-system-running` reports `running`.** The prompt asks
for a non-systemd start path to be configured "if systemd is unavailable in this distro". It
is available; step 4 records that the systemd path was taken and still ships the fallback
branch.

---

## 4. Device mapper — the premise B1 rests on

```
=== dmsetup targets ===
verity           v1.9.0
striped          v1.6.0
linear           v1.4.0
error            v1.6.0

=== lsmod | grep -i 'dm_|loop' ===
(no matching modules loaded)

=== dm-flakey module present on disk? ===
-rw-rw-r-- 1 root root 26864 Dec  2  2025 /usr/lib/modules/6.6.114.1-microsoft-standard-WSL2/kernel/drivers/md/dm-flakey.ko
```

**`flakey` is not in `dmsetup targets` right now**, and no `dm_*` or `loop` module is loaded.
This is not a regression and not a blocker: the module ships with the kernel and is simply
not loaded on a freshly started distro. `experiments/flakey_write_loss.py:563` refuses to
measure when `"flakey" not in dmsetup targets`, so the module must be loaded before the
self-test. Step 3 does that and reports the result.

Recorded here because it would otherwise look, to a later reader of this file, as though the
capability had gone away between the 90-trial collection and this phase.

```
=== iptables present? ===
(neither iptables nor nft on PATH)
```

`nft_compat`, `ip_tables`, `xt_nat`, `xt_MASQUERADE` and `br_netfilter` are all **loaded**
(Docker Desktop's networking uses them from its own VM); only the *userspace* tools are
absent from this distro. `docker-ce` depends on `iptables`, so apt will install it in step 4.

---

## 5. Filesystems

```
=== df -T for the repo ===
Filesystem     Type 1K-blocks     Used Available Use% Mounted on
D:\            9p   409598972 26342952 383256020   7% /mnt/d

=== df -T for /var/lib/docker ===
df: /var/lib/docker: No such file or directory
(/var/lib/docker does not exist on this distro -- Docker Desktop keeps its data root in its own VM)
```

> **`/var/lib/docker` does not exist inside `Ubuntu-24.04`.** `docker info` reports it because
> the answer comes from Docker Desktop's VM. The loop device, the `dm-flakey` target and the
> ext4 filesystem B1 needs all live in *this* distro; Redis's `/data` lives in *that* one.
> Two namespaces, and nothing in the distro can reach across. That is the finding, stated as
> an absence rather than as an argument.

```
=== /proc/mounts entry governing the repo ===
/dev/sdd / ext4 rw,relatime,discard,errors=remount-ro,data=ordered 0 0
D:\134 /mnt/d 9p rw,noatime,aname=drvfs;path=D:\;uid=1001;gid=1001;symlinkroot=/mnt/,cache=5,access=client,msize=65536,trans=fd,rfd=6,wfd=6 0 0
```

Two things worth naming for later phases:

- **The repo working tree is on 9p/drvfs**, not ext4. This is the stratum Phase 8.1 measured
  at ~40× the event-log append cost of the WSL-native tree, and it is why this phase collects
  the replication on **both** filesystems rather than one.
- **`uid=1001;gid=1001`** — `/mnt/d` is owned by `hamzakhan`, not by `root`, even though the
  harness runs as `root`. Any bind-mount canary from `/mnt/d` must account for that.

```
=== df -T (all) ===
/dev/sdd       ext4    1055762868   4821900 997237496   1% /
```

952 GB free on the distro's own ext4 root — ample for a native `/var/lib/docker`.

---

## 6. Timing declaration

```
=== AEP_HARNESS_SUSPEND_DISABLED ===
value=<unset>
```

Amendment E5's declaration is **not set in this shell**. `run_matrix.py:823` reads it per
invocation, so it must be exported by the collection command itself; `analyze.py:352` will
otherwise exclude every duration collected. Recorded so the collection commands in step 8
can be checked against it.

---

## 7. One environment change was made during this capture, and it is declared

`git` refused the tree with *"detected dubious ownership in repository at
'/mnt/d/personal/AEP/Research-paper-AEP'"* when run as `root`, which made
`experiments/harness/provenance.py::harness_version` unable to record the commit — the exact
failure mode that function's comment at `provenance.py:68-71` was written about. Fixed with:

```
git config --global --add safe.directory /mnt/d/personal/AEP/Research-paper-AEP
```

This is a change to root's git config inside WSL, not to the repository, and it affects only
whether provenance can be *recorded*. It is declared here rather than left for a reader to
notice that the first capture attempt carried a `fatal:` line the second did not.

---

## 8. Summary of what the native engine must reproduce or change

| property | under Docker Desktop | required after |
|---|---|---|
| docker client OS/Arch | `windows/amd64` | `linux/amd64` |
| context | `desktop-linux` → `npipe://` | `aep-native` → `unix:///var/run/docker.sock` |
| bind source resolution | `D:\personal\AEP\...` (Windows) | a Linux path |
| server version | `29.4.3` | pin to `29.4.3` if the noble repo has it |
| `/var/lib/docker` in the distro | **absent** | present, on `/dev/sdd` ext4 |
| pinned Redis digest | `sha256:6aaf3f5e…` | **identical** |
| `dmsetup targets` | no `flakey` (module unloaded) | `flakey` present |
| repo filesystem | 9p/drvfs, `uid=1001` | unchanged (9p is a property of where the tree lives) |
