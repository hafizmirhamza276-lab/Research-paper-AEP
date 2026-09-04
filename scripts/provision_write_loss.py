r"""Provision the dm-flakey device WS-4 collects on, and run the §4 self-test.

`reports/phase-report-ws4-prediction-2026-09-04.md` §4:

    Per session, before the first run, recorded as a first-class artifact. […]
    **If the self-test does not pass, the session does not run.**

That is enforced here rather than remembered: `provision` exits non-zero and
tears the device down if the self-test fails, so a session cannot begin on a
device that is not actually dropping writes.

**Why a self-test at all.** `docs/24-revision-backlog.md` B1: under write loss
the fault *is* the measurement, so a mapping that silently fails to drop leaves
runs that look like clean successes for both arms. The two-key probe
(`experiments/flakey_write_loss.py`) self-tests for exactly this reason, and its
90/90 result is only trustworthy because it did. This carries that discipline
into the harness configuration, which is the part the probe evidence does *not*
cover.

Usage::

    sudo python scripts/provision_write_loss.py provision --root /var/tmp/ws4
    sudo python scripts/provision_write_loss.py teardown  --root /var/tmp/ws4

`provision` prints the two `dmsetup` table lines and writes a JSON record beside
the device, which the session root should carry.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.harness.write_loss import (  # noqa: E402
    arm_drop_writes,
    read_table,
    table_declares_drop,
)

#: Size of the backing file. Large enough for an AOF across a session, small
#: enough to create in a second.
BACKING_MEGABYTES = 512

DEVICE_NAME = "aep-ws4-flakey"


def run(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, check=check)


@dataclass
class SelfTest:
    """§4's three steps, and whether the device may be collected on."""

    pass_mode_survived: bool | None = None
    drop_mode_survived: bool | None = None
    table_pass: str | None = None
    table_drop: str | None = None
    valid: bool = False
    reason: str = "not run"


def _write_probe(mount: Path, name: str, content: str) -> None:
    (mount / name).write_text(content, encoding="utf-8")


def self_test(device: str, mount: Path) -> SelfTest:
    """Write before the cut and after it, and require different fates.

    Step 1 -- in **pass** mode, a synced write must survive a remount.
    Step 2 -- in **drop_writes**, an unsynced write must **not**.

    A device that fails step 1 is broken; one that fails step 2 is not dropping,
    which is the silent failure the gate exists for. Either way the session does
    not run.
    """
    result = SelfTest()
    result.table_pass = read_table(device)

    # Step 1: pass mode, synced, must survive.
    _write_probe(mount, "selftest-before", "written in pass mode\n")
    run("sync")
    run("umount", str(mount))
    if run("mount", f"/dev/mapper/{device}", str(mount)).returncode != 0:
        result.reason = "could not remount after the pass-mode write"
        return result
    result.pass_mode_survived = (mount / "selftest-before").exists()

    # Step 2: drop mode, unsynced, must not survive.
    record = arm_drop_writes(device)
    result.table_drop = record.table_after
    if not record.armed:
        result.reason = f"could not arm drop_writes: {record.error}"
        return result

    _write_probe(mount, "selftest-after", "written after the cut\n")
    run("umount", str(mount))
    run("dmsetup", "suspend", device)
    run("dmsetup", "reload", device, "--table", result.table_pass or "")
    run("dmsetup", "resume", device)
    if run("mount", f"/dev/mapper/{device}", str(mount)).returncode != 0:
        result.reason = "could not remount after the drop-mode write"
        return result
    result.drop_mode_survived = (mount / "selftest-after").exists()

    if not result.pass_mode_survived:
        result.reason = "a synced write in pass mode did not survive: device is broken"
    elif result.drop_mode_survived:
        result.reason = (
            "an unsynced write in drop_writes SURVIVED: the device is not "
            "dropping, and a session on it would measure nothing"
        )
    elif not table_declares_drop(result.table_drop):
        result.reason = "the drop table did not read back as drop_writes"
    else:
        result.valid = True
        result.reason = "pass-mode write survived, drop-mode write did not"
    return result


def provision(root: Path) -> int:
    root.mkdir(parents=True, exist_ok=True)
    backing = root / "backing.img"
    mount = root / "mnt"
    mount.mkdir(exist_ok=True)

    run("truncate", "-s", f"{BACKING_MEGABYTES}M", str(backing), check=True)
    loop = run("losetup", "--find", "--show", str(backing), check=True).stdout.strip()
    sectors = run("blockdev", "--getsz", loop, check=True).stdout.strip()
    run("dmsetup", "create", DEVICE_NAME, "--table",
        f"0 {sectors} flakey {loop} 0 1 0", check=True)
    run("mkfs.ext4", "-q", "-F", f"/dev/mapper/{DEVICE_NAME}", check=True)
    run("mount", f"/dev/mapper/{DEVICE_NAME}", str(mount), check=True)

    outcome = self_test(DEVICE_NAME, mount)
    record = {
        "device": DEVICE_NAME,
        "loop": loop,
        "backing": str(backing),
        "mount": str(mount),
        "redis_dir": str(mount / "redis"),
        "at_ms": int(time.time() * 1000),
        "self_test": asdict(outcome),
    }
    (root / "write-loss-provision.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(json.dumps(record, indent=2, sort_keys=True))
    print()
    print(f"table (pass): {outcome.table_pass}")
    print(f"table (drop): {outcome.table_drop}")
    print(f"self-test   : {'PASS' if outcome.valid else 'FAIL'} -- {outcome.reason}")

    if not outcome.valid:
        print()
        print("THE SESSION DOES NOT RUN. Tearing the device down.")
        teardown(root)
        return 1

    (mount / "redis").mkdir(exist_ok=True)
    for name in ("selftest-before", "selftest-after"):
        (mount / name).unlink(missing_ok=True)
    print()
    print("Provisioned. Export before collecting:")
    print("  AEP_HARNESS_REDIS_FAULT_MECHANISM=write-loss")
    print(f"  AEP_HARNESS_WRITE_LOSS_DEVICE={DEVICE_NAME}")
    print(f"  redis dir: {mount / 'redis'}")
    return 0


def teardown(root: Path) -> int:
    mount = root / "mnt"
    run("umount", str(mount))
    run("dmsetup", "remove", DEVICE_NAME)
    record_path = root / "write-loss-provision.json"
    if record_path.is_file():
        loop = json.loads(record_path.read_text(encoding="utf-8")).get("loop")
        if loop:
            run("losetup", "-d", loop)
    run("rm", "-f", str(root / "backing.img"))
    print("torn down")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("provision", "teardown"))
    parser.add_argument("--root", type=Path, default=Path("/var/tmp/aep-ws4"))
    arguments = parser.parse_args(argv)
    return (provision if arguments.action == "provision" else teardown)(arguments.root)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
