"""What a *host-level write loss* costs, measured rather than named.

Amendment G2. ``experiments/redis_durability_window.py`` established a negative
result: a hard **process** kill loses nothing, because ``appendfsync everysec``
defers the ``fsync(2)`` and not the ``write(2)``, so the bytes are already in a
page cache belonging to a kernel that is still running. That probe reported
0/10 unacknowledged writes lost, and the paper's consequent claim is that the
``WAITAOF`` barrier's durability benefit holds only against *loss of the page
cache* -- host power failure, kernel panic, VM destruction.

That claim named a fault class and never exercised it. This module exercises
it, and the design is deliberately the *same probe with the fault swapped*, so
the two results are directly comparable:

* ``redis_durability_window`` -- two keys, one ``WAITAOF``-acknowledged and one
  not, then ``docker kill -s KILL``.
* this module -- two keys, one ``WAITAOF``-acknowledged and one not, then
  **the block device stops accepting writes**.

**How the fault is produced.** A loop-backed device carries a ``dm-flakey``
target. ``dm-flakey``'s ``drop_writes`` feature silently discards every write
bio while serving reads correctly, which is what a storage stack looks like to
a kernel whose writes will never reach the platter. The switch into that mode
is the moment of "power loss": everything ``fsync(2)``-ed before it is on the
device and survives, everything still sitting dirty in the page cache is not
and does not.

Three details make that switch honest, and each is a way the experiment could
have silently measured nothing:

1. ``dmsetup suspend`` calls ``freeze_bdev()``, which **syncs the filesystem**.
   That would push the unacknowledged write to the device before the drop takes
   effect and the probe would report that nothing is ever lost. ``--nolockfs``
   suppresses it.
2. ``dmsetup suspend`` also flushes outstanding I/O by default, for the same
   net effect. ``--noflush`` suppresses that.
3. The page cache still holds the dropped bytes after the switch, so reading
   the key back without discarding it would find data that is not on any disk.
   The filesystem is unmounted and ``drop_caches`` is written before Redis is
   restarted.

``--selftest`` validates the device stack on its own terms, without Redis in
the picture: a file written and ``fsync``-ed before the switch must survive,
and a file written and ``fsync``-ed after it must not. If that does not hold,
no Redis result from this harness means anything, and the harness says so
rather than producing numbers.

**What a trial reports.** ``acknowledged`` surviving is a *precondition*: the
barrier is supposed to make it survive, and a trial where it did not says
nothing about the other key and is reported VOID. ``unacknowledged`` surviving
or not is the finding.

    sudo python -m experiments.flakey_write_loss --selftest
    sudo python -m experiments.flakey_write_loss --trials 30

Root is required: the probe creates a loop device and a device-mapper target.
Every trial's raw line is printed as it happens. Nothing is averaged away and
no trial is dropped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from redis.asyncio import Redis

ACKNOWLEDGED_KEY = "aep:flakey-write-loss:acknowledged"
UNACKNOWLEDGED_KEY = "aep:flakey-write-loss:unacknowledged"

#: The device-mapper target name. Namespaced so a stray one is identifiable.
DM_NAME = "aep-g2-flakey"

#: Size of the backing file. The AOF for a handful of keys is bytes; this is
#: sized for the ext4 journal and metadata, not for the data.
BACKING_MEGABYTES = 256

#: ``dm-flakey``'s table takes intervals in seconds. "Always up" and "always
#: down" are expressed as a zero-length opposite interval; the kernel refuses
#: both being zero, which is why PASS carries up=1/down=0.
PASS_INTERVALS = (1, 0)
DROP_INTERVALS = (0, 1)


class ProbeError(RuntimeError):
    """The harness cannot honestly proceed."""


def run(argv: list[str], *, check: bool = True, timeout: float = 60.0) -> str:
    """Run a command, returning stdout. Raises ProbeError on failure."""
    completed = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout
    )
    if check and completed.returncode != 0:
        raise ProbeError(
            f"{' '.join(argv)} exited {completed.returncode}: "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed.stdout


@dataclass
class DeviceStack:
    """The loop device, the dm-flakey target and the filesystem over it."""

    root: Path
    backing: Path = field(init=False)
    mountpoint: Path = field(init=False)
    loop: str = field(init=False, default="")
    sectors: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self.backing = self.root / "backing.img"
        self.mountpoint = self.root / "mnt"

    @property
    def dm_path(self) -> str:
        return f"/dev/mapper/{DM_NAME}"

    @property
    def data_dir(self) -> Path:
        return self.mountpoint / "redisdata"

    def create(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.mountpoint.mkdir(parents=True, exist_ok=True)
        run(
            [
                "dd",
                "if=/dev/zero",
                f"of={self.backing}",
                "bs=1M",
                f"count={BACKING_MEGABYTES}",
                "status=none",
            ]
        )
        self.loop = run(["losetup", "--find", "--show", str(self.backing)]).strip()
        if not self.loop:
            raise ProbeError("losetup returned no device")
        size_bytes = int(run(["blockdev", "--getsize64", self.loop]).strip())
        self.sectors = size_bytes // 512
        self.set_mode("pass")

    def table(self, mode: str) -> str:
        up, down = PASS_INTERVALS if mode == "pass" else DROP_INTERVALS
        line = f"0 {self.sectors} flakey {self.loop} 0 {up} {down}"
        if mode == "drop":
            line += " 1 drop_writes"
        return line

    def set_mode(self, mode: str) -> None:
        """Create or reload the dm target.

        The reload path is ``suspend --noflush --nolockfs`` on purpose; see the
        module docstring. Without both flags the kernel syncs the filesystem
        on the way in and the fault under test never happens.
        """
        table = self.table(mode)
        exists = Path(self.dm_path).exists()
        if not exists:
            proc = subprocess.run(
                ["dmsetup", "create", DM_NAME, "--table", table],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                raise ProbeError(f"dmsetup create failed: {proc.stderr.strip()}")
            return
        run(["dmsetup", "suspend", "--noflush", "--nolockfs", DM_NAME])
        run(["dmsetup", "reload", DM_NAME, "--table", table])
        run(["dmsetup", "resume", DM_NAME])

    def current_table(self) -> str:
        return run(["dmsetup", "table", DM_NAME]).strip()

    def mkfs(self) -> None:
        run(["mkfs.ext4", "-q", "-F", self.dm_path])

    def mount(self) -> None:
        run(["mount", self.dm_path, str(self.mountpoint)])

    def unmount(self, *, lazy_ok: bool = True) -> None:
        if not self.is_mounted():
            return
        proc = subprocess.run(
            ["umount", str(self.mountpoint)], capture_output=True, text=True, timeout=60
        )
        if proc.returncode != 0:
            if not lazy_ok:
                raise ProbeError(f"umount failed: {proc.stderr.strip()}")
            run(["umount", "-l", str(self.mountpoint)])

    def is_mounted(self) -> bool:
        return (
            subprocess.run(
                ["mountpoint", "-q", str(self.mountpoint)], capture_output=True
            ).returncode
            == 0
        )

    def drop_caches(self) -> None:
        subprocess.run(["sync"], capture_output=True, timeout=60)
        Path("/proc/sys/vm/drop_caches").write_text("3\n", encoding="ascii")

    def mount_options(self) -> str:
        """The options the filesystem is actually mounted with.

        A reviewer's first question about an fsync result is whether the
        filesystem was honouring fsync. ``nobarrier`` or ``data=writeback``
        would change what an acknowledgement means, so the answer is recorded
        from ``/proc/mounts`` rather than assumed from the ``mount`` command
        that was issued.
        """
        target = str(self.mountpoint)
        for line in Path("/proc/mounts").read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) >= 4 and fields[1] == target:
                return f"{fields[2]} {fields[3]}"
        return "(not mounted)"

    def destroy(self) -> None:
        try:
            self.unmount()
        except Exception:
            pass
        for argv in (
            ["dmsetup", "remove", "--force", DM_NAME],
            ["losetup", "-d", self.loop] if self.loop else ["true"],
        ):
            subprocess.run(argv, capture_output=True, timeout=60)
        try:
            if self.backing.exists():
                self.backing.unlink()
        except OSError:
            pass


@dataclass
class RedisProcess:
    """A real redis-server, on the flakey filesystem, started per trial."""

    binary: str
    data_dir: Path
    port: int
    process: subprocess.Popen | None = field(default=None, init=False)

    @property
    def url(self) -> str:
        return f"redis://127.0.0.1:{self.port}/0"

    def start(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.process = subprocess.Popen(
            [
                self.binary,
                "--port",
                str(self.port),
                "--dir",
                str(self.data_dir),
                "--appendonly",
                "yes",
                "--appendfsync",
                "everysec",
                "--save",
                "",
                "--daemonize",
                "no",
                "--protected-mode",
                "no",
                "--logfile",
                "",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def kill(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.kill()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass
        self.process = None


async def wait_ready(url: str, *, timeout: float = 30.0) -> float:
    """Block until the server answers PING. Returns the wait in ms."""
    started = time.monotonic()
    deadline = started + timeout
    while time.monotonic() < deadline:
        client = Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        try:
            if await client.ping():
                return (time.monotonic() - started) * 1000.0
        except Exception:
            await asyncio.sleep(0.05)
        finally:
            await client.aclose()
    raise ProbeError(f"redis at {url} never became ready within {timeout}s")


@dataclass
class Trial:
    index: int
    waitaof_ack: list[int] | None = None
    align_ms: float = 0.0
    barrier_ms: float = 0.0
    write_to_drop_ms: float = 0.0
    kill_ms: float = 0.0
    restart_ms: float = 0.0
    readiness_ms: float = 0.0
    acknowledged_survived: bool | None = None
    unacknowledged_survived: bool | None = None
    error: str | None = None

    @property
    def verdict(self) -> str:
        if self.error:
            return f"ERROR: {self.error}"
        if not self.acknowledged_survived:
            return "VOID: the acknowledged write did not survive"
        return (
            "UNACKNOWLEDGED SURVIVED"
            if self.unacknowledged_survived
            else "UNACKNOWLEDGED LOST"
        )

    @property
    def counts(self) -> bool:
        return self.error is None and bool(self.acknowledged_survived)


async def one_trial(
    stack: DeviceStack, binary: str, port: int, index: int
) -> Trial:
    """One matched pair of writes, one write-loss event, one read-back."""
    trial = Trial(index=index)
    server = RedisProcess(binary=binary, data_dir=stack.data_dir, port=port)

    # A fresh filesystem per trial. A trial must not be able to read a key a
    # previous trial's AOF happens to still contain.
    stack.set_mode("pass")
    stack.unmount()
    stack.mkfs()
    stack.mount()

    try:
        server.start()
        await wait_ready(server.url)
        client = Redis.from_url(server.url, socket_timeout=30)
        try:
            await client.delete(ACKNOWLEDGED_KEY, UNACKNOWLEDGED_KEY)

            # (1) The acknowledged write. WAITAOF both exercises the barrier
            #     and phase-aligns the everysec timer: when it returns an fsync
            #     has just completed, so the next is a full second away and the
            #     unacknowledged write's exposure window is as wide as it gets.
            started = time.monotonic()
            await client.set(ACKNOWLEDGED_KEY, f"trial-{index}")
            barrier_started = time.monotonic()
            ack = await client.execute_command("WAITAOF", 1, 0, 5000)
            trial.barrier_ms = (time.monotonic() - barrier_started) * 1000.0
            trial.align_ms = (time.monotonic() - started) * 1000.0
            trial.waitaof_ack = list(ack) if isinstance(ack, (list, tuple)) else [ack]
            if not trial.waitaof_ack or int(trial.waitaof_ack[0]) < 1:
                raise ProbeError(f"WAITAOF did not acknowledge locally: {ack}")

            # (2) The unacknowledged write. Returns as soon as Redis has
            #     write(2)-ed the AOF buffer; no fsync is waited for.
            wrote_at = time.monotonic()
            await client.set(UNACKNOWLEDGED_KEY, f"trial-{index}")
        finally:
            await client.aclose()

        # (3) Power loss. Everything fsynced before this instant is on the
        #     device; everything still dirty in the page cache never will be.
        stack.set_mode("drop")
        trial.write_to_drop_ms = (time.monotonic() - wrote_at) * 1000.0

        # (4) Destroy the process, then the page cache that outlived it. The
        #     unmount's own writes go to a device that is dropping them, which
        #     is the point.
        kill_started = time.monotonic()
        server.kill()
        trial.kill_ms = (time.monotonic() - kill_started) * 1000.0
        stack.unmount()
        stack.drop_caches()

        # (5) The storage comes back. What is on it is what was fsynced.
        restart_started = time.monotonic()
        stack.set_mode("pass")
        stack.mount()
        server.start()
        trial.readiness_ms = await wait_ready(server.url)
        trial.restart_ms = (time.monotonic() - restart_started) * 1000.0

        client = Redis.from_url(server.url, socket_timeout=30)
        try:
            trial.acknowledged_survived = bool(await client.exists(ACKNOWLEDGED_KEY))
            trial.unacknowledged_survived = bool(
                await client.exists(UNACKNOWLEDGED_KEY)
            )
        finally:
            await client.aclose()
    except Exception as exc:  # recorded, never swallowed
        trial.error = f"{type(exc).__name__}: {exc}"
    finally:
        server.kill()

    return trial


async def describe_environment(
    stack: DeviceStack, binary: str, port: int
) -> dict[str, Any]:
    """Read back the settings the result depends on, from the live system.

    Every value here is one a reader would otherwise have to take on trust,
    and two of them (``appendfsync`` and the mount options) are settings under
    which this experiment would produce a confident wrong answer. They are
    read from the running server and from ``/proc/mounts``, never from the
    arguments that were meant to set them -- the same discipline that caught
    a benchmark labelled ``always`` running under ``everysec``.
    """
    stack.set_mode("pass")
    stack.unmount()
    stack.mkfs()
    stack.mount()
    described: dict[str, Any] = {
        "mount_options": stack.mount_options(),
        "ext4_features": "",
        "appendfsync": "",
        "appendonly": "",
        "redis_dir": "",
    }
    dump = subprocess.run(
        ["dumpe2fs", "-h", stack.dm_path], capture_output=True, text=True, timeout=60
    )
    for line in dump.stdout.splitlines():
        if line.startswith("Filesystem features:"):
            described["ext4_features"] = line.split(":", 1)[1].strip()

    server = RedisProcess(binary=binary, data_dir=stack.data_dir, port=port)
    try:
        server.start()
        await wait_ready(server.url)
        client = Redis.from_url(server.url, socket_timeout=30)
        try:
            for setting in ("appendfsync", "appendonly", "dir"):
                value = await client.config_get(setting)
                described[
                    "redis_dir" if setting == "dir" else setting
                ] = value.get(setting, "")
            info = await client.info("server")
            described["redis_version"] = info.get("redis_version", "")
        finally:
            await client.aclose()
    finally:
        server.kill()
        stack.unmount()
    return described


def selftest(stack: DeviceStack) -> dict[str, Any]:
    """Prove the device stack drops writes, with no Redis in the picture.

    Before the switch: write a file and ``fsync`` it -- it is on the device.
    After the switch: write a file and ``fsync`` it -- the fsync returns
    success, because ``drop_writes`` discards silently, and the bytes are gone.
    """
    stack.set_mode("pass")
    stack.unmount()
    stack.mkfs()
    stack.mount()

    before = stack.mountpoint / "before-the-cut"
    after = stack.mountpoint / "after-the-cut"

    with open(before, "wb") as handle:
        handle.write(b"fsynced while the device was accepting writes\n")
        handle.flush()
        os.fsync(handle.fileno())
    # The directory entry needs its own fsync or the file may be unreachable
    # after recovery even though its data blocks landed.
    dir_fd = os.open(stack.mountpoint, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)

    stack.set_mode("drop")

    after_fsync_raised = None
    try:
        with open(after, "wb") as handle:
            handle.write(b"fsynced after the device stopped accepting writes\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        after_fsync_raised = str(exc)

    stack.unmount()
    stack.drop_caches()
    stack.set_mode("pass")
    stack.mount()

    result = {
        "table_pass": stack.table("pass"),
        "table_drop": stack.table("drop"),
        "before_the_cut_survived": before.exists(),
        "after_the_cut_survived": after.exists(),
        "after_the_cut_fsync_error": after_fsync_raised,
    }
    result["valid"] = bool(
        result["before_the_cut_survived"] and not result["after_the_cut_survived"]
    )
    stack.unmount()
    return result


def summarise(trials: list[Trial]) -> dict[str, Any]:
    counted = [t for t in trials if t.counts]
    void = [t for t in trials if not t.counts]
    lost = [t for t in counted if not t.unacknowledged_survived]
    windows = [t.write_to_drop_ms for t in counted]
    return {
        "trials": len(trials),
        "counted": len(counted),
        "void": len(void),
        "acknowledged_survived": sum(
            1 for t in trials if t.acknowledged_survived
        ),
        "unacknowledged_lost": len(lost),
        "unacknowledged_survived": len(counted) - len(lost),
        "unacknowledged_loss_rate": (len(lost) / len(counted)) if counted else None,
        "write_to_drop_ms_min": min(windows) if windows else None,
        "write_to_drop_ms_max": max(windows) if windows else None,
        "barrier_ms_min": min((t.barrier_ms for t in counted), default=None),
        "barrier_ms_max": max((t.barrier_ms for t in counted), default=None),
    }


async def main_async(arguments: argparse.Namespace) -> int:
    if os.geteuid() != 0:
        print("REFUSING: this probe creates a loop device and a dm target; run as root.")
        return 2
    for tool in ("losetup", "dmsetup", "mkfs.ext4", "blockdev", "mountpoint"):
        if shutil.which(tool) is None:
            print(f"REFUSING: {tool} is not on PATH.")
            return 2
    if "flakey" not in run(["dmsetup", "targets"]):
        print("REFUSING: this kernel has no dm-flakey target.")
        return 2
    binary = arguments.redis_server
    if shutil.which(binary) is None and not Path(binary).exists():
        print(f"REFUSING: redis-server not found at {binary}.")
        return 2

    version = run([binary, "--version"]).strip()
    print("=" * 78)
    print("G2: host-level write loss (dm-flakey drop_writes)")
    print("=" * 78)
    print(f"  platform        {platform.platform()}")
    print(f"  kernel          {platform.release()}")
    print(f"  redis           {version}")
    print(f"  dm targets      {run(['dmsetup', 'targets']).strip().splitlines()[0]}")
    print()

    stack = DeviceStack(root=Path(arguments.root))
    payload: dict[str, Any] = {
        "platform": platform.platform(),
        "kernel": platform.release(),
        "redis_version": version,
        "backing_megabytes": BACKING_MEGABYTES,
    }
    try:
        stack.create()
        payload["dm_table_pass"] = stack.table("pass")
        payload["dm_table_drop"] = stack.table("drop")
        print(f"  loop            {stack.loop}")
        print(f"  dm table (pass) {stack.table('pass')}")
        print(f"  dm table (drop) {stack.table('drop')}")
        print()

        print("--- the environment the durability claim rests on ---")
        environment = await describe_environment(stack, binary, arguments.port)
        payload["environment"] = environment
        for key, value in environment.items():
            print(f"  {key:24s} {value}")
        print()
        if environment.get("appendfsync") != "everysec":
            print(
                "REFUSING TO MEASURE: appendfsync is "
                f"{environment.get('appendfsync')!r}, not 'everysec'. The "
                "comparison against the process-kill probe assumes the same "
                "policy, and under 'always' there is no unacknowledged write "
                "to lose."
            )
            return 1
        if "nobarrier" in environment.get("mount_options", ""):
            print(
                "REFUSING TO MEASURE: the filesystem is mounted nobarrier, so "
                "fsync does not mean what the barrier assumes it means and a "
                "surviving acknowledged write would prove nothing."
            )
            return 1

        print("--- selftest: does the device stack actually lose writes? ---")
        check = selftest(stack)
        payload["selftest"] = check
        for key, value in check.items():
            print(f"  {key:32s} {value}")
        print()
        if not check["valid"]:
            print(
                "REFUSING TO MEASURE: the selftest did not lose the write it was "
                "supposed to lose. Any Redis result from this stack would be "
                "about the harness, not about the barrier."
            )
            payload["trials"] = []
            payload["summary"] = None
            return 1
        if arguments.selftest:
            return 0

        print(f"--- {arguments.trials} trials ---")
        trials: list[Trial] = []
        for index in range(arguments.trials):
            trial = await one_trial(stack, binary, arguments.port, index)
            trials.append(trial)
            print(
                f"  trial {index:2d}  barrier={trial.barrier_ms:7.1f}ms  "
                f"write->drop={trial.write_to_drop_ms:6.1f}ms  "
                f"ack={trial.acknowledged_survived}  "
                f"unack={trial.unacknowledged_survived}  "
                f"{trial.verdict}"
            )
        payload["trials"] = [asdict(t) for t in trials]
        payload["summary"] = summarise(trials)

        print()
        print("--- summary ---")
        for key, value in payload["summary"].items():
            print(f"  {key:30s} {value}")
        return 0
    finally:
        stack.destroy()
        if arguments.output:
            Path(arguments.output).parent.mkdir(parents=True, exist_ok=True)
            Path(arguments.output).write_text(
                json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
            )
            print(f"\nwrote {arguments.output}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--port", type=int, default=6399)
    parser.add_argument("--redis-server", default="/root/redis-server")
    parser.add_argument("--root", default="/root/aep-g2")
    parser.add_argument(
        "--output", default="experiments/results/g2-flakey-write-loss.json"
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="validate the device stack and stop before any Redis trial",
    )
    arguments = parser.parse_args(argv)
    return asyncio.run(main_async(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
