#!/usr/bin/env python3
"""Assert, and print as JSON, what this host is measuring with.

Phase 10 / WS-0. Every phase from here on calls this and embeds its output in
its report, so that a later reader can tell which runtime, which filesystem and
which fault-injection timing a number was collected under **without taking a
prose sentence's word for it**.

The design rule is `experiments/harness/provenance.py`'s and it is repeated
here because it is the whole point: *detected, never declared*. Every field
below is read from the running system. A declared field would be worth nothing
-- Phase 8.1 found a 40x filesystem difference between two collections that
nobody had declared, and Phase 9C's "40 of 44 config keys identical" conclusion
survived two audits precisely because the difference that mattered was not a
key anybody wrote down.

What it asserts, and therefore what a non-zero exit means:

  * the docker context in use names a **unix socket**, not a Windows named pipe
    (the condition `docs/24-revision-backlog.md` B1 was blocked by);
  * a container can bind-mount a **WSL-local** path and see the file (B1's
    actual requirement), and a **drvfs** path too (the repo tree lives there);
  * the Redis image the daemon resolves locally carries the digest pinned in
    `compose.phase2.yml` -- checked through the image reference, never through
    the `redis:7.2.5-alpine` tag, which does not exist on a host that pulled by
    digest;
  * `dmsetup targets` contains `flakey`.

What it records without asserting, because absence is informative rather than
fatal: the filesystem under the repo and under Docker's data root, the E5
suspend declaration and wall-versus-monotonic check, and the host's measured
`docker kill` latency distribution.

**The kill latency is read from a cache, not measured here.** Measuring it
costs a hundred container kills; this script is called at the top of every
phase. `scripts/measure_kill_latency.py --output` writes the cache and this
script reports it, with its age, so a stale one is visible rather than silently
authoritative.

Usage::

    python scripts/verify_measurement_host.py
    python scripts/verify_measurement_host.py --no-canary   # skip container runs
    python scripts/verify_measurement_host.py --output reports/raw/host.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.analyze import TIMING_SUSPENSION_TOLERANCE_SECONDS  # noqa: E402
from experiments.harness.provenance import (  # noqa: E402
    KILL_LATENCY_CACHE,
    _mount_entry_for,
    results_root_filesystem,
)
from experiments.run_matrix import (  # noqa: E402
    SUSPEND_DISABLED_VARIABLE,
    suspend_disabled_declared,
)

DEFAULT_COMPOSE = REPO_ROOT / "compose.phase2.yml"
DEFAULT_KILL_LATENCY_CACHE = REPO_ROOT / KILL_LATENCY_CACHE
DEFAULT_CANARY_WSL_DIR = Path("/root/aep-phase10-canary")

#: How long the clock check watches for. Long enough that a two-second
#: divergence would show, short enough to run at the top of every phase. The
#: gate this mirrors is `analyze.py`'s, which measures over a whole run; this
#: is a spot check that the two clocks are tracking each other *now*.
CLOCK_SAMPLE_SECONDS = 2.0

TIMEOUT = 60.0


def _run(argv: list[str], *, timeout: float = TIMEOUT) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout
        )
    except Exception as error:  # noqa: BLE001 -- a probe must describe its own failure
        return (-1, "", f"{type(error).__name__}: {error}")
    return (completed.returncode, completed.stdout.strip(), completed.stderr.strip())


def _docker(*args: str, timeout: float = TIMEOUT) -> str | None:
    code, out, _ = _run(["docker", *args], timeout=timeout)
    return out if code == 0 else None


def pinned_image(compose_file: Path) -> str | None:
    try:
        text = compose_file.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(
        r"^\s*image:\s*(redis:[^\s]+@sha256:[0-9a-f]{64})\s*$", text, re.MULTILINE
    )
    return match.group(1) if match else None


def docker_facts() -> dict[str, Any]:
    record: dict[str, Any] = {
        "cli_path": _run(["bash", "-lc", "command -v docker"])[1] or None,
        "context": _docker("context", "show"),
        "client_version": _docker("version", "--format", "{{.Client.Version}}"),
        "client_os_arch": _docker(
            "version", "--format", "{{.Client.Os}}/{{.Client.Arch}}"
        ),
        "server_version": _docker("version", "--format", "{{.Server.Version}}"),
        "server_git_commit": _docker(
            "version", "--format", "{{.Server.Components}}"
        ) and _docker("version", "--format", "{{(index .Server.Components 0).Details.GitCommit}}"),
        "data_root": _docker("info", "--format", "{{.DockerRootDir}}"),
        "storage_driver": _docker("info", "--format", "{{.Driver}}"),
        "daemon_os": _docker("info", "--format", "{{.OperatingSystem}}"),
        "daemon_name": _docker("info", "--format", "{{.Name}}"),
        "compose_version": (_run(["docker", "compose", "version", "--short"])[1] or None),
        "docker_host_env": os.environ.get("DOCKER_HOST"),
    }
    context = record["context"]
    if context:
        record["daemon_socket"] = _docker(
            "context", "inspect", context, "--format", "{{.Endpoints.docker.Host}}"
        )
    else:
        record["daemon_socket"] = None
    socket = record["daemon_socket"] or ""
    record["is_unix_socket"] = socket.startswith("unix://")
    # Named separately from `is_unix_socket` so a later reader does not have to
    # know that `npipe://` is what Docker Desktop looked like. This is the
    # condition backlog B1 was blocked by, stated as a field.
    record["is_windows_named_pipe"] = socket.startswith("npipe:")
    return record


def canary(name: str, directory: Path, image: str) -> dict[str, Any]:
    """Write a token, bind-mount the file, read it back from inside a container.

    The failure this detects is a daemon that resolves the *source* somewhere
    other than where the caller meant, whose symptom under Docker Desktop was
    an empty destination rather than an error. So the assertion is on the
    content, not on the exit status: a mount that silently produced nothing
    would otherwise pass.
    """
    record: dict[str, Any] = {"name": name, "directory": str(directory)}
    token = f"aep-host-verify-{name}-{uuid.uuid4().hex}"
    record["token"] = token
    try:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "canary.txt"
        target.write_text(token + "\n", encoding="ascii")
    except OSError as error:
        record["pass"] = False
        record["error"] = f"could not write the canary: {error}"
        return record
    record["filesystem"] = _run(["stat", "-f", "-c", "%T", str(directory)])[1] or None
    code, out, err = _run(
        [
            "docker", "run", "--rm",
            "-v", f"{target}:/canary.txt:ro",
            image, "cat", "/canary.txt",
        ],
        timeout=180.0,
    )
    seen = out.strip()
    record["seen"] = seen
    record["returncode"] = code
    record["pass"] = seen == token
    if not record["pass"] and err:
        record["stderr"] = err[-500:]
    return record


def redis_image_facts(compose_file: Path) -> dict[str, Any]:
    record: dict[str, Any] = {"compose_file": str(compose_file)}
    pinned = pinned_image(compose_file)
    record["pinned_reference"] = pinned
    if not pinned:
        record["error"] = "no digest-pinned redis image in the compose file"
        record["digest_matches"] = False
        return record
    record["pinned_digest"] = pinned.split("@", 1)[1]
    # Deliberately through the pinned reference and not through the bare tag:
    # `docker image inspect redis:7.2.5-alpine` fails with "No such image" on a
    # host that pulled by digest, which is every host this project uses.
    raw = _docker("image", "inspect", pinned, "--format", "{{json .RepoDigests}}")
    if raw is None:
        record["error"] = "the image is not present locally (pull it first)"
        record["digest_matches"] = False
        return record
    try:
        digests = json.loads(raw)
    except json.JSONDecodeError:
        record["error"] = "docker image inspect returned unparseable JSON"
        record["digest_matches"] = False
        return record
    record["resolved_repo_digests"] = digests
    record["digest_matches"] = any(record["pinned_digest"] in d for d in digests)
    record["image_id"] = _docker("image", "inspect", pinned, "--format", "{{.Id}}")
    return record


def device_mapper_facts() -> dict[str, Any]:
    code, out, err = _run(["dmsetup", "targets"])
    record: dict[str, Any] = {}
    if code != 0:
        record["error"] = err or "dmsetup targets failed"
        record["has_flakey"] = False
        return record
    record["targets"] = out.splitlines()
    record["has_flakey"] = any(
        line.split()[:1] == ["flakey"] for line in out.splitlines() if line.split()
    )
    # Recorded because "flakey is absent" and "the module exists but is not
    # loaded" are different situations and only one of them is a blocker.
    module = Path(
        f"/usr/lib/modules/{platform.release()}/kernel/drivers/md/dm-flakey.ko"
    )
    record["module_on_disk"] = module.exists()
    record["module_path"] = str(module)
    return record


def filesystem_facts(docker_data_root: str | None) -> dict[str, Any]:
    """Type, device and mount options under the repo and under Docker.

    Reuses `provenance.results_root_filesystem` and `provenance._mount_entry_for`
    rather than reimplementing them, so this script and every run's own
    `run-config.json` describe a filesystem the same way and can be compared
    field for field.
    """
    def describe(path: Path) -> dict[str, Any]:
        record = dict(results_root_filesystem(path))
        entry = _mount_entry_for(path)
        if entry:
            record["device"] = entry["device"]
        # `results_root_filesystem` does not carry the options, and the options
        # are what say whether an fsync means anything (`nobarrier`,
        # `data=writeback`). `flakey_write_loss.py` reads them for the same
        # reason.
        try:
            resolved = str(path.resolve())
            best_length = -1
            for line in Path("/proc/mounts").read_text(encoding="utf-8").splitlines():
                fields = line.split()
                if len(fields) < 4:
                    continue
                if resolved == fields[1] or resolved.startswith(
                    fields[1].rstrip("/") + "/"
                ):
                    if len(fields[1]) > best_length:
                        best_length = len(fields[1])
                        record["mount_options"] = fields[3]
        except OSError:
            pass
        return record

    record: dict[str, Any] = {"repo": describe(REPO_ROOT)}
    if docker_data_root:
        path = Path(docker_data_root)
        record["docker_data_root"] = (
            describe(path) if path.exists()
            else {
                "path": docker_data_root,
                "error": (
                    "the daemon reports this path but it does not exist in this "
                    "namespace -- the daemon is not in this distro"
                ),
            }
        )
    else:
        record["docker_data_root"] = {"error": "the daemon did not report a data root"}
    return record


def clock_facts() -> dict[str, Any]:
    """The E5 wall-versus-monotonic check, as a spot measurement.

    `analyze.py:493` computes `wall_span - monotonic_span` over a whole run and
    `analyze.py:348` calls a run suspended when it exceeds
    `TIMING_SUSPENSION_TOLERANCE_SECONDS`. The same arithmetic over a short
    window cannot prove a host will not suspend -- nothing can, which is why
    amendment E5 keeps a *declaration* as well -- but it does catch a host
    whose clocks are already disagreeing.
    """
    wall_start = time.time()
    monotonic_start = time.monotonic()
    time.sleep(CLOCK_SAMPLE_SECONDS)
    wall_span = time.time() - wall_start
    monotonic_span = time.monotonic() - monotonic_start
    divergence = wall_span - monotonic_span
    return {
        "sample_seconds": CLOCK_SAMPLE_SECONDS,
        "wall_span_seconds": round(wall_span, 6),
        "monotonic_span_seconds": round(monotonic_span, 6),
        "wall_minus_monotonic_seconds": round(divergence, 6),
        "tolerance_seconds": TIMING_SUSPENSION_TOLERANCE_SECONDS,
        "within_tolerance": abs(divergence) <= TIMING_SUSPENSION_TOLERANCE_SECONDS,
        "source": "experiments/analyze.py TIMING_SUSPENSION_TOLERANCE_SECONDS",
    }


def suspend_facts() -> dict[str, Any]:
    return {
        "variable": SUSPEND_DISABLED_VARIABLE,
        "value": os.environ.get(SUSPEND_DISABLED_VARIABLE),
        "declared": suspend_disabled_declared(),
        "note": (
            "amendment E5. Not detectable: a host that merely did not happen to "
            "suspend is indistinguishable from one that cannot. The declaration "
            "must be exported by the collection command itself."
        ),
    }


def kill_latency_facts(cache: Path) -> dict[str, Any]:
    """The host's measured `docker kill` latency, read from a cache.

    Not measured here: it costs a hundred container kills and this script runs
    at the top of every phase. Its age is reported so that a cache from a
    different runtime is visible rather than silently authoritative -- the
    number decides the width of the race the prevention result measures
    (Phase 8.1), so an out-of-date one is worse than none.
    """
    record: dict[str, Any] = {"cache": str(cache)}
    if not cache.is_file():
        record["error"] = (
            "no cached measurement; run scripts/measure_kill_latency.py --output "
            f"{cache}"
        )
        return record
    try:
        payload = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        record["error"] = f"cache unreadable: {error}"
        return record
    record["measured_at_utc"] = payload.get("measured_at_utc")
    record["age_days"] = None
    measured = payload.get("measured_at_utc")
    if measured:
        try:
            stamp = time.mktime(time.strptime(measured, "%Y-%m-%dT%H:%M:%SZ"))
            record["age_days"] = round(
                (time.mktime(time.gmtime()) - stamp) / 86400.0, 2
            )
        except ValueError:
            pass
    record["instrument"] = payload.get("instrument")
    record["comparable_historical_source"] = payload.get(
        "comparable_historical_source"
    )
    summaries = payload.get("summaries", {})
    record["runtimes"] = {
        label: {
            key: summary.get(key)
            for key in (
                "trials_counted", "min", "median", "p95", "max",
                "median_ci_low", "median_ci_high", "server_version",
                "context", "endpoint", "unit",
            )
        }
        for label, summary in summaries.items()
    }
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--compose-file", type=Path, default=DEFAULT_COMPOSE)
    parser.add_argument("--canary-wsl-dir", type=Path, default=DEFAULT_CANARY_WSL_DIR)
    parser.add_argument(
        "--canary-drvfs-dir",
        type=Path,
        default=REPO_ROOT / ".scratch" / "phase10-canary",
    )
    parser.add_argument(
        "--kill-latency-cache", type=Path, default=DEFAULT_KILL_LATENCY_CACHE
    )
    parser.add_argument(
        "--no-canary",
        action="store_true",
        help="skip the two container runs (they need a working daemon and the image)",
    )
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args(argv)

    docker = docker_facts()
    image = redis_image_facts(arguments.compose_file)

    canaries: dict[str, Any] = {}
    if arguments.no_canary:
        canaries = {"skipped": True, "reason": "--no-canary"}
    elif not image.get("pinned_reference"):
        canaries = {"skipped": True, "reason": "no pinned image to mount into"}
    else:
        reference = image["pinned_reference"]
        canaries = {
            "wsl_local": canary("wsl_local", arguments.canary_wsl_dir, reference),
            "drvfs": canary("drvfs", arguments.canary_drvfs_dir, reference),
        }

    payload: dict[str, Any] = {
        "probe": "aep.measurement-host/1",
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": platform.node(),
        "kernel": platform.release(),
        "platform": platform.platform(),
        "os_release": {
            key: value.strip('"')
            for key, _, value in (
                line.partition("=")
                for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines()
                if "=" in line
            )
        } if Path("/etc/os-release").is_file() else {},
        "repo_root": str(REPO_ROOT),
        "euid": os.geteuid() if hasattr(os, "geteuid") else None,
        "docker": docker,
        "bind_mount_canary": canaries,
        "redis_image": image,
        "device_mapper": device_mapper_facts(),
        "filesystem": filesystem_facts(docker.get("data_root")),
        "suspend": suspend_facts(),
        "clock": clock_facts(),
        "docker_kill_latency": kill_latency_facts(arguments.kill_latency_cache),
    }

    # ------------------------------------------------------------------ gates
    failures: list[str] = []
    if not docker.get("is_unix_socket"):
        failures.append(
            f"docker context {docker.get('context')!r} names "
            f"{docker.get('daemon_socket')!r}, not a unix socket"
        )
    if not image.get("digest_matches"):
        failures.append(
            "the locally resolved Redis image does not carry the digest pinned "
            f"in {arguments.compose_file.name}: {image.get('error') or image.get('resolved_repo_digests')}"
        )
    if not payload["device_mapper"].get("has_flakey"):
        failures.append(
            "dmsetup targets does not contain flakey"
            + ("" if payload["device_mapper"].get("module_on_disk")
               else " and dm-flakey.ko is not on disk either")
        )
    if not arguments.no_canary and "skipped" not in canaries:
        for name, result in canaries.items():
            if not result.get("pass"):
                failures.append(
                    f"bind-mount canary {name!r} failed: wrote "
                    f"{result.get('token')!r}, saw {result.get('seen')!r}"
                )
    payload["gates"] = {
        "passed": not failures,
        "failures": failures,
    }

    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(text + "\n", encoding="utf-8")

    if failures:
        print("", file=sys.stderr)
        for failure in failures:
            print(f"GATE FAILED: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
