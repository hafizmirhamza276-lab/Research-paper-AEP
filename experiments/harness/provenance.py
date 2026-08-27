"""Environment facts a run cannot declare about itself, detected at construction.

Phase 8.2. Two independent findings motivate this module, and both are the same
shape: **a property that could move a measured number, that nobody chose, that
no field recorded, and that a configuration comparison therefore could not see.**

*The first.* Phase 9C compared the five collections of the ``redis-kill-preack``
cell and found "40 of 44 ``run-config.json`` keys identical", concluding the
sessions were interchangeable. They were not. The paper's cell was collected in
the WSL-native tree on ext4; the four replications ran through ``/mnt/d`` on
drvfs, where an event-log append costs about forty times more (5.4 us against
229.7 us median, measured in Phase 8.1). The key-by-key check could not have
caught it, because the filesystem under the results root is not a key.

*The second, and the reason there are two fields rather than one.* That first
difference turned out **not** to reach the mechanism under test, and only a
second field can show why. ``compose.phase2.yml:12`` mounts Redis's ``/data``
from a *named Docker volume*, not a bind mount, so the AOF that ``WAITAOF``
waits on lives on Docker's own storage -- neither drvfs nor the host's ext4.
The barrier's latency was therefore constant across both strata and the 40x
difference touched only the harness's event log. That narrows the confound
instead of widening it.

**But constancy that nobody chose is not a control.** Nothing holds that mount
type fixed, and backlog B1 breaks it deliberately: it bind-mounts Redis's data
directory onto a ``dm-flakey`` device, so B1's numbers will be collected with
Redis storage on a backing unlike every number currently in the paper -- in the
one experiment where the storage *is* the fault. Recording the backing is what
lets that phase state the difference rather than inherit it.

**Detected, never declared.** Every value here is read from the running system:
``stat -f`` for the filesystem under the results root, ``docker inspect`` for
the mount actually serving ``/data``. A declared field would be worth nothing,
because nobody declared drvfs either -- that is precisely how the confound
survived two audits.

**These values do not enter ``config_digest``.** The digest's contract is
everything that could change a number *and that the operator set*; two runs
differing only in where Docker happened to put a volume are the same
configuration observed twice. There is also a hard reason: the digest is
verified when a saved configuration is re-read
(``config.run_config_from_mapping``), so admitting these keys to the digested
body would make every one of the 432 frozen runs fail its own digest check the
next time anything parsed it. They are carried in the echo as derived keys.

Every probe is fail-soft. A run that cannot reach Docker must still produce a
result; it records why the field is missing instead of dying, because a
provenance probe that can abort a collection is a worse defect than the gap it
closes.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

#: Probes run once per run, at construction, before any worker starts. The
#: Docker CLI costs 0.44-0.52 s per invocation on this host
#: (``redis_kill.py`` measured it), so this is seconds per session against a
#: cell that takes tens of minutes -- and none of it is on the protocol path.
PROBE_TIMEOUT_SECONDS = 15.0


#: Why the last ``_run`` failed, for the caller to record. A field that says
#: only "error" is barely better than no field: the first probe failure this
#: module actually hit was git refusing a repository for "dubious ownership",
#: which a bare "git was not reachable" would have misreported as absence.
_LAST_ERROR: str | None = None


def _run(command: list[str]) -> str | None:
    global _LAST_ERROR
    _LAST_ERROR = None
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except Exception as error:  # noqa: BLE001 -- provenance must never fail a run
        _LAST_ERROR = f"{type(error).__name__}: {error}"
        return None
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        _LAST_ERROR = (
            f"exit {completed.returncode}: {detail[0]}" if detail
            else f"exit {completed.returncode}"
        )
        return None
    return completed.stdout.strip()


def _mount_entry_for(path: Path) -> dict[str, str] | None:
    """The ``/proc/mounts`` line governing ``path``: longest matching prefix.

    Read as a fallback for, and a cross-check on, ``stat -f``. ``stat`` names
    the filesystem *type*; ``/proc/mounts`` also names the device, which is what
    distinguishes two ext4 filesystems from each other.
    """
    try:
        resolved = path.resolve()
        entries = Path("/proc/mounts").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    best: dict[str, str] | None = None
    best_length = -1
    for line in entries:
        fields = line.split()
        if len(fields) < 3:
            continue
        device, mount_point, filesystem = fields[0], fields[1], fields[2]
        try:
            mount = Path(mount_point)
        except ValueError:
            continue
        if resolved == mount or mount in resolved.parents:
            if len(mount_point) > best_length:
                best_length = len(mount_point)
                best = {
                    "device": device,
                    "mount_point": mount_point,
                    "type": filesystem,
                }
    return best


def results_root_filesystem(results_root: Path) -> dict[str, Any]:
    """What kind of filesystem the run is about to write its evidence onto.

    ``stat -f -c %T`` is the value the reviewer asked for by name; the
    ``/proc/mounts`` entry is carried alongside it because a type alone cannot
    tell two mounts apart, and the distinction that mattered in Phase 8.1 was
    between two directories on the same machine.
    """
    record: dict[str, Any] = {"path": str(results_root)}
    stat_type = _run(["stat", "-f", "-c", "%T", str(results_root)])
    if stat_type:
        record["type"] = stat_type
    entry = _mount_entry_for(results_root)
    if entry:
        record["mount_point"] = entry["mount_point"]
        record["device"] = entry["device"]
        record.setdefault("type", entry["type"])
        # Named separately from `type` so a later reader does not have to know
        # which strings mean "this is the Windows drive seen from WSL".
        record["is_drvfs"] = entry["type"] in {"9p", "drvfs", "v9fs", "virtiofs"}
    if "type" not in record:
        record["error"] = "neither stat -f nor /proc/mounts could describe it"
    return record


def redis_storage_backing(container: str) -> dict[str, Any]:
    """What is actually serving the container's ``/data`` -- the AOF's home.

    This is the field that can move the barrier's latency, and therefore the
    race the ``redis-kill-preack`` regime measures. A named volume, a bind
    mount from the host, and a bind mount onto a fault-injection device are
    three different storage stacks, and today only the compose file records
    which one is in use.
    """
    record: dict[str, Any] = {"container": container}
    raw = _run(["docker", "inspect", container, "--format", "{{json .Mounts}}"])
    if not raw:
        record["error"] = _LAST_ERROR or "docker inspect returned nothing"
        return record
    try:
        mounts = json.loads(raw)
    except json.JSONDecodeError:
        record["error"] = "docker inspect returned unparseable JSON"
        return record
    for mount in mounts:
        if mount.get("Destination") != "/data":
            continue
        record["mount_type"] = mount.get("Type")
        record["source"] = mount.get("Source")
        record["name"] = mount.get("Name")
        record["read_only"] = not mount.get("RW", True)
        return record
    record["error"] = "no mount at /data; Redis is writing to the container layer"
    return record


def docker_identity() -> dict[str, Any]:
    """Client and server versions, and the container's start time.

    Phase 9C named the missing Docker daemon state as "the gap that matters
    most" because the audit attributed the effect size to ``docker kill``
    latency. That attribution is now measured directly (Phase 8.1), which makes
    this corroborating rather than load-bearing -- but a daemon that was
    restarted between sessions is still the first thing to check when a
    latency distribution moves.
    """
    record: dict[str, Any] = {}
    client = _run(["docker", "version", "--format", "{{.Client.Version}}"])
    server = _run(["docker", "version", "--format", "{{.Server.Version}}"])
    if client:
        record["client_version"] = client
    if server:
        record["server_version"] = server
    if not record:
        record["error"] = _LAST_ERROR or "docker version was not reachable"
    return record


def container_state(container: str) -> dict[str, Any]:
    record: dict[str, Any] = {}
    started = _run(
        ["docker", "inspect", container, "--format", "{{.State.StartedAt}}"]
    )
    restarts = _run(
        ["docker", "inspect", container, "--format", "{{.RestartCount}}"]
    )
    if started:
        record["started_at"] = started
    if restarts:
        record["restart_count"] = restarts
    return record


def harness_version() -> dict[str, Any]:
    """The commit the harness was at, and whether the tree was dirty.

    Phase 8.2 changes what the harness records, so runs collected before and
    after it are not byte-comparable in their configuration even when every
    knob matches. Phase 8.4's report is required to say so; this is the field
    that lets a reader check the claim instead of taking it.
    """
    record: dict[str, Any] = {}
    root = Path(__file__).resolve().parents[2]
    commit = _run(["git", "-C", str(root), "rev-parse", "HEAD"])
    if commit:
        record["commit"] = commit
        status = _run(["git", "-C", str(root), "status", "--porcelain"])
        # `is None` and `""` mean different things: the first is "git did not
        # answer", the second is "git answered, and the tree is clean".
        if status is not None:
            record["dirty"] = bool(status)
    else:
        record["error"] = _LAST_ERROR or "git did not answer"
    return record


def collect(results_root: Path, redis_container: str | None) -> dict[str, Any]:
    """Every environment fact this run can detect about itself."""
    record: dict[str, Any] = {
        "results_root_filesystem": results_root_filesystem(results_root),
        "harness_version": harness_version(),
        "docker": docker_identity(),
        "platform_release": os.uname().release if hasattr(os, "uname") else None,
    }
    if redis_container:
        record["redis_storage_backing"] = redis_storage_backing(redis_container)
        record["redis_container_state"] = container_state(redis_container)
    else:
        record["redis_storage_backing"] = {
            "error": "no Redis container name was supplied to the run"
        }
    return record
