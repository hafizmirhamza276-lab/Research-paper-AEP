r"""Bring the harness stack up with Redis's data directory on the flakey device.

WS-4 / backlog B1. The instrument (`experiments/harness/write_loss.py`, the
`write-loss-preack` regime) is inert unless Redis is actually writing through the
`dm-flakey` mapping. `compose.phase2.yml` backs `/data` with the named volume
`redis-data`, so a session started the ordinary way runs against a device that
**cannot** drop writes — and the regime would then report a clean AEP-full result
for the wrong reason. That is the exact contamination `docs/24` B1 describes:

    An instrument that intermittently fails to deliver the fault does not cost B1
    precision -- it silently removes the phenomenon while leaving runs that look
    successful.

So this script refuses rather than falls back. Every check below is a refusal,
not a warning, and each names what it would otherwise have let through.

Usage::

    sudo python scripts/up_write_loss.py --root /var/tmp/aep-ws4
    sudo python scripts/up_write_loss.py --root /var/tmp/aep-ws4 --check-only

`--check-only` runs every refusal check and the post-up verification against a
stack that is already running, without touching it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.harness.write_loss import read_table  # noqa: E402
from experiments.harness.redis_kill import (  # noqa: E402
    MECHANISM_WRITE_LOSS,
    REDIS_FAULT_MECHANISM_VARIABLE,
    WRITE_LOSS_DEVICE_VARIABLE,
)

#: The variable `compose.write-loss.yml` interpolates. Its `:?` guard is the
#: second line of defence; the refusals here are the first, because compose's
#: message cannot explain *why* the path was wrong.
COMPOSE_PATH_VARIABLE = "AEP_WS4_REDIS_DIR"

BASE_COMPOSE = "compose.phase2.yml"
OVERRIDE_COMPOSE = "compose.write-loss.yml"

CONTAINER = "aep-phase2-redis72"


class Refused(RuntimeError):
    """A precondition failed, so the session does not start."""


def run(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, check=check)


def backing_device(path: Path) -> str | None:
    """Which device backs ``path``? The anti-fallback check.

    A provisioned directory that is really on the root filesystem -- because the
    mount failed, or the record is stale, or someone passed the wrong root --
    looks identical to a correct one from Python. ``findmnt`` answers what is
    actually underneath it.
    """
    completed = run("findmnt", "-no", "SOURCE", "--target", str(path))
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def load_and_check(root: Path) -> dict:
    """Every refusal, in the order that gives the most useful message first."""
    record_path = root / "write-loss-provision.json"
    if not record_path.is_file():
        raise Refused(
            f"no provision record at {record_path}. Run "
            f"`scripts/provision_write_loss.py provision --root {root}` first. "
            "Starting without one would put Redis on the ordinary redis-data "
            "volume, which cannot drop writes."
        )

    record = json.loads(record_path.read_text(encoding="utf-8"))

    self_test = record.get("self_test") or {}
    if not self_test.get("valid"):
        raise Refused(
            "the provision record's self-test did not pass "
            f"({self_test.get('reason', 'no reason recorded')}). "
            "§4 of the pre-registration: if the self-test does not pass, the "
            "session does not run."
        )

    device = record.get("device")
    table = read_table(device) if device else None
    if table is None:
        raise Refused(
            f"the provisioned device {device!r} no longer exists. The record is "
            "stale -- re-provision rather than starting against whatever is "
            "mounted there now."
        )
    if "flakey" not in table.split():
        raise Refused(
            f"{device!r} is not a dm-flakey target (table: {table!r}). It cannot "
            "drop writes, so the fault could never be delivered."
        )

    redis_dir = Path(record["redis_dir"])
    if not redis_dir.is_dir():
        raise Refused(f"the provisioned redis dir {redis_dir} does not exist")

    backing = backing_device(redis_dir)
    expected = f"/dev/mapper/{device}"
    if backing != expected:
        raise Refused(
            f"{redis_dir} is backed by {backing!r}, not by the provisioned "
            f"device {expected!r}. This is the silent fallback the regime must "
            "never run under: the path exists, so nothing else would have "
            "complained, and Redis would have written to a device that cannot "
            "drop writes."
        )

    return record


def verify_running_stack(record: dict) -> list[str]:
    """After `up`: is Redis *really* writing through the flakey device?

    Two observations, because neither alone is enough. The container's mount
    table says what Docker was asked to do; a file appearing on the host path
    says what Redis actually did.
    """
    findings: list[str] = []
    redis_dir = record["redis_dir"]

    inspected = run(
        "docker", "inspect", "-f",
        "{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}}\n{{end}}",
        CONTAINER,
    )
    if inspected.returncode != 0:
        raise Refused(f"cannot inspect {CONTAINER}: {inspected.stderr.strip()[:200]}")
    mounts = inspected.stdout.strip()
    findings.append(f"container mounts:\n{mounts}")

    data_mount = [line for line in mounts.splitlines() if line.endswith("-> /data")]
    if not data_mount:
        raise Refused("the container has no /data mount at all")
    if not any(redis_dir in line for line in data_mount):
        raise Refused(
            f"/data is {data_mount[0]!r}, not the provisioned {redis_dir!r}. "
            "Redis is running against the wrong backing."
        )
    if any("volume" in line for line in data_mount):
        raise Refused(
            f"/data is still a named volume ({data_mount[0]!r}). The override "
            "did not take effect and writes cannot be dropped."
        )

    # What Redis itself did: force an append and look for it on the host.
    run("docker", "exec", CONTAINER, "redis-cli", "-n", "15", "SET",
        "aep:ws4:wiring-probe", "1")
    run("docker", "exec", CONTAINER, "redis-cli", "-n", "15", "WAITAOF", "1", "0", "2000")
    on_host = list(Path(redis_dir).rglob("*.aof")) + list(Path(redis_dir).rglob("*.manifest"))
    if not on_host:
        raise Refused(
            f"Redis acknowledged a write but no AOF file appeared under "
            f"{redis_dir}. Its data directory is not this device."
        )
    findings.append(
        "AOF files on the provisioned device: "
        + ", ".join(str(p.relative_to(redis_dir)) for p in sorted(on_host)[:4])
    )
    run("docker", "exec", CONTAINER, "redis-cli", "-n", "15", "UNLINK",
        "aep:ws4:wiring-probe")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("/var/tmp/aep-ws4"))
    parser.add_argument("--check-only", action="store_true")
    arguments = parser.parse_args(argv)

    try:
        record = load_and_check(arguments.root)
    except Refused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 1

    redis_dir = record["redis_dir"]
    print(f"provisioned device : {record['device']}")
    print(f"redis dir          : {redis_dir}")
    print(f"backed by          : {backing_device(Path(redis_dir))}")

    if not arguments.check_only:
        environment = {COMPOSE_PATH_VARIABLE: redis_dir}
        completed = subprocess.run(
            ["docker", "compose", "-f", BASE_COMPOSE, "-f", OVERRIDE_COMPOSE,
             "up", "-d", "--wait"],
            cwd=REPO_ROOT, capture_output=True, text=True,
            env={**os.environ, **environment},
        )
        if completed.returncode != 0:
            print(f"compose up failed: {completed.stderr.strip()[:400]}", file=sys.stderr)
            return 1
        print("stack up")

    try:
        for finding in verify_running_stack(record):
            print(finding)
    except Refused as refusal:
        print(f"REFUSED after start: {refusal}", file=sys.stderr)
        return 1

    print()
    print("Redis is writing through the flakey device. Export before collecting:")
    print(f"  {REDIS_FAULT_MECHANISM_VARIABLE}={MECHANISM_WRITE_LOSS}")
    print(f"  {WRITE_LOSS_DEVICE_VARIABLE}={record['device']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
