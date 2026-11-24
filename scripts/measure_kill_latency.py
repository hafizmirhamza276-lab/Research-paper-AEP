#!/usr/bin/env python3
"""How long ``docker kill -s KILL`` takes, per container runtime.

Phase 10, addition 1. Phase 8.1 established that in the ``redis-kill-preack``
regime AEP-full dispatches **iff** ``WAITAOF`` returns before Redis dies, so the
width of that race -- and therefore ``\\UnwantedPrevented{}`` -- is partly a
property of the fault injector's timing rather than of the protocol. Phase 10
replaces the container runtime. Every prevention number collected afterwards
inherits the *new* runtime's timing, so it has to be measured before anything is
collected, on both runtimes, rather than assumed to carry over.

**The measurement is the harness's own.** This module does not re-implement the
timing: it calls :func:`experiments.harness.redis_kill.kill_redis` and reads its
``command_ms``, which is ``time.monotonic()`` around
``subprocess.run(["docker", "kill", "-s", "KILL", container])``
(``redis_kill.py:99-108``). A separate stopwatch here would measure a slightly
different thing and the comparison against the collected runs would be a
comparison of two instruments.

**Selecting a runtime without editing the harness.** ``kill_redis`` invokes the
bare name ``docker``, which is the point -- it is what a run does. The runtime is
therefore selected by putting a directory holding a ``docker`` symlink at the
front of ``PATH`` for the duration of the call, so the code under measurement is
byte-identical between arms and only resolution differs.

**Interleaving.** With two or more ``--runtime`` arguments the trials are
round-robined rather than run in blocks, so a drift in the host during the
measurement lands on both arms instead of on whichever ran second. Phase 8.4
found within-session drift whose *sign* reverses between sessions on this host;
blocked arms would be indistinguishable from it.

**What is comparable, and what is not.** The directly comparable historical
figure is ``reports/raw/e1-kill-latency-by-run.csv``: 300 runs' ``issue_to_return_ns``
through the Docker Desktop shim, median 961.6 ms, range 681.8-1673.9 ms. The
paper's ``\\ProcessKillWindowMin/Max`` (419-992 ms) is **not** this quantity --
it is the write-to-death window of the durability-window probe
(``reports/raw/e1-durability-window.txt``), which the kill latency dominates but
does not equal. Do not compare against it.

Usage::

    python scripts/measure_kill_latency.py \\
        --runtime docker-desktop=/usr/local/bin/docker-desktop-shim \\
        --runtime aep-native=/usr/bin/docker \\
        --trials 100 \\
        --output reports/raw/phase10-kill-latency.json

Each ``--trials`` is *per runtime*. Nothing is averaged away: every trial is in
the output, and the container is recreated if a trial leaves it unusable.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import re
import shutil
import statistics as _stdlib_statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.harness.redis_kill import kill_redis, start_redis  # noqa: E402
from experiments.statistics import (  # noqa: E402
    DEFAULT_BOOTSTRAP_SEED,
    DEFAULT_RESAMPLES,
    quantile,
    summarise,
)

DEFAULT_COMPOSE = REPO_ROOT / "compose.phase2.yml"

#: The throwaway container. Namespaced away from ``aep-phase2-redis72`` on
#: purpose: this probe kills its target a hundred times, and pointing it at the
#: compose container by accident would destroy a stack a collection was using.
DEFAULT_CONTAINER_PREFIX = "aep-phase10-killtarget"

#: How long to wait for a killed container to come back before declaring the
#: trial unusable. ``start_redis`` returns as soon as the daemon accepts the
#: request; the container still has to reach ``running``.
RESTART_DEADLINE_SECONDS = 60.0


class MeasurementError(RuntimeError):
    """The probe cannot honestly proceed."""


def pinned_image(compose_file: Path) -> str:
    """The image reference from the compose file, digest included.

    Read rather than hardcoded so this probe cannot drift from
    ``compose.phase2.yml``. Phase 10's bounds forbid changing that pin, and a
    probe carrying its own copy of it would make a silent divergence possible.
    """
    text = compose_file.read_text(encoding="utf-8")
    match = re.search(r"^\s*image:\s*(redis:[^\s]+@sha256:[0-9a-f]{64})\s*$",
                      text, re.MULTILINE)
    if not match:
        raise MeasurementError(
            f"no digest-pinned redis image found in {compose_file}"
        )
    return match.group(1)


class RuntimeSelector:
    """Make ``docker`` resolve to one specific binary, for the harness's call.

    A directory containing a single ``docker`` entry is prepended to ``PATH``.
    A symlink is used where the platform allows it and a two-line exec wrapper
    otherwise, because the Docker Desktop shim is itself a script and symlinking
    a script is fine while copying it would duplicate a thing that may change.
    """

    def __init__(self, label: str, binary: Path) -> None:
        self.label = label
        self.binary = binary
        if not binary.exists():
            raise MeasurementError(f"runtime {label!r}: {binary} does not exist")
        self._directory = Path(tempfile.mkdtemp(prefix=f"aep-runtime-{label}-"))
        link = self._directory / "docker"
        try:
            link.symlink_to(binary)
        except OSError:
            link.write_text(
                f'#!/usr/bin/env bash\nexec "{binary}" "$@"\n', encoding="ascii"
            )
            link.chmod(0o755)

    def __enter__(self) -> RuntimeSelector:
        self._saved_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{self._directory}{os.pathsep}{self._saved_path}"
        return self

    def __exit__(self, *_: object) -> None:
        os.environ["PATH"] = self._saved_path

    def cleanup(self) -> None:
        shutil.rmtree(self._directory, ignore_errors=True)

    def describe(self) -> dict[str, Any]:
        """What this runtime says about itself, recorded once per arm."""
        with self:
            def ask(*format_args: str) -> str | None:
                completed = subprocess.run(
                    ["docker", *format_args],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if completed.returncode != 0:
                    return None
                return completed.stdout.strip()

            return {
                "label": self.label,
                "binary": str(self.binary),
                "client_version": ask("version", "--format", "{{.Client.Version}}"),
                "client_os_arch": ask(
                    "version", "--format", "{{.Client.Os}}/{{.Client.Arch}}"
                ),
                "server_version": ask("version", "--format", "{{.Server.Version}}"),
                "context": ask("context", "show"),
                "endpoint": ask(
                    "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"
                ),
                "data_root": ask("info", "--format", "{{.DockerRootDir}}"),
            }


def _docker(selector: RuntimeSelector, argv: list[str], *, timeout: float = 120.0
            ) -> subprocess.CompletedProcess[str]:
    with selector:
        return subprocess.run(
            ["docker", *argv], capture_output=True, text=True, timeout=timeout
        )


def ensure_container(selector: RuntimeSelector, container: str, image: str) -> None:
    """Create the throwaway target if it is not there, and make it running."""
    inspect = _docker(selector, ["inspect", container, "--format", "{{.State.Status}}"])
    if inspect.returncode != 0:
        created = _docker(
            selector,
            [
                "run", "-d", "--name", container,
                # No published port: nothing connects to it. The probe measures
                # how long the daemon takes to kill a container, and a port
                # binding would add teardown work that a collected run's Redis
                # does have -- but the compose container's binding is on the
                # loopback of a different namespace under Docker Desktop, so
                # including it would make the two arms differ in a second way.
                image,
                "redis-server", "--save", "", "--appendonly", "no",
            ],
        )
        if created.returncode != 0:
            raise MeasurementError(
                f"could not create {container} on {selector.label}: "
                f"{created.stderr.strip()}"
            )
        return
    if inspect.stdout.strip() != "running":
        start_container(selector, container)


def start_container(selector: RuntimeSelector, container: str) -> float:
    """Bring it back and wait until the daemon reports it running."""
    started = time.monotonic()
    with selector:
        start_redis(container)
    deadline = started + RESTART_DEADLINE_SECONDS
    while time.monotonic() < deadline:
        status = _docker(
            selector, ["inspect", container, "--format", "{{.State.Status}}"]
        )
        if status.returncode == 0 and status.stdout.strip() == "running":
            return (time.monotonic() - started) * 1000.0
        time.sleep(0.05)
    raise MeasurementError(
        f"{container} did not return to running within "
        f"{RESTART_DEADLINE_SECONDS}s on {selector.label}"
    )


def remove_container(selector: RuntimeSelector, container: str) -> None:
    _docker(selector, ["rm", "-f", container])


def median_interval(
    values: list[float], *, resamples: int, seed: int
) -> tuple[float | None, float | None]:
    """Percentile bootstrap on the median.

    A bootstrap rather than a normal approximation because the kill latency is
    visibly not symmetric on this host -- the collected distribution's max is
    1.7x its median -- and a symmetric interval would understate the upper tail
    that decides the race.
    """
    if len(values) < 2:
        return (None, None)
    rng = random.Random(seed)
    medians: list[float] = []
    size = len(values)
    for _ in range(resamples):
        sample = [values[rng.randrange(size)] for _ in range(size)]
        medians.append(_stdlib_statistics.median(sample))
    medians.sort()
    low = medians[max(0, int(0.025 * resamples) - 1)]
    high = medians[min(resamples - 1, int(0.975 * resamples))]
    return (round(low, 1), round(high, 1))


def measure(
    selectors: list[RuntimeSelector],
    *,
    trials: int,
    image: str,
    container_prefix: str,
    resamples: int,
    seed: int,
    existing_container: str | None = None,
) -> dict[str, Any]:
    # Two target modes, because they answer two different questions.
    #
    # A throwaway container isolates the *runtime*: identical spec on both
    # arms, interleaved, so the difference is the daemon and nothing else. It
    # is not comparable in absolute terms to the collected runs, whose target
    # was a Redis serving an active protocol with a published port and an AOF.
    #
    # `--existing-container` points the same instrument at that real target, so
    # the number can be put beside `reports/raw/e1-kill-latency-by-run.csv`.
    # It cannot be interleaved across runtimes -- only one daemon can hold
    # 127.0.0.1:6381 -- so it takes one runtime at a time.
    if existing_container is not None and len(selectors) != 1:
        raise MeasurementError(
            "--existing-container measures one runtime at a time (only one "
            "daemon can own the compose stack's ports); pass a single --runtime"
        )
    containers = {
        s.label: (existing_container or f"{container_prefix}-{s.label}")
        for s in selectors
    }
    per_trial: list[dict[str, Any]] = []
    samples: dict[str, list[float]] = {s.label: [] for s in selectors}

    for selector in selectors:
        if existing_container is not None:
            status = _docker(
                selector,
                ["inspect", existing_container, "--format", "{{.State.Status}}"],
            )
            if status.returncode != 0:
                raise MeasurementError(
                    f"--existing-container {existing_container} not found on "
                    f"{selector.label}: {status.stderr.strip()}"
                )
            if status.stdout.strip() != "running":
                start_container(selector, existing_container)
            print(f"  [{selector.label}] target {existing_container} "
                  f"(pre-existing, not created by this probe)", flush=True)
            continue
        remove_container(selector, containers[selector.label])
        ensure_container(selector, containers[selector.label], image)
        print(f"  [{selector.label}] target {containers[selector.label]} ready",
              flush=True)

    # Round-robin, not blocked: see the module docstring on drift.
    for index in range(trials):
        for selector in selectors:
            container = containers[selector.label]
            record: dict[str, Any] = {
                "trial": index,
                "runtime": selector.label,
                "container": container,
            }
            try:
                with selector:
                    outcome = kill_redis(container)
                record.update(outcome)
                if outcome.get("issued") and outcome.get("returncode") == 0:
                    latency = float(outcome["command_ms"])
                    samples[selector.label].append(latency)
                    record["counted"] = True
                else:
                    record["counted"] = False
                record["restart_ms"] = round(
                    start_container(selector, container), 1
                )
            except Exception as error:  # noqa: BLE001 -- recorded, never swallowed
                record["counted"] = False
                record["error"] = f"{type(error).__name__}: {error}"
                if existing_container is not None:
                    # Never recreate a container this probe did not create: the
                    # compose stack's Redis owns a named volume holding the AOF,
                    # and `docker rm -f` plus a fresh `run` would silently give
                    # the next trial a different server.
                    raise MeasurementError(
                        f"{selector.label}: pre-existing target {container} "
                        f"unusable after trial {index} and this probe will not "
                        f"recreate it: {error}"
                    ) from None
                try:
                    remove_container(selector, container)
                    ensure_container(selector, container, image)
                    record["target_recreated"] = True
                except Exception as inner:  # noqa: BLE001
                    raise MeasurementError(
                        f"{selector.label}: target unrecoverable after trial "
                        f"{index}: {inner}"
                    ) from None
            per_trial.append(record)
            print(
                f"  trial {index:3d} [{selector.label:14s}] "
                f"command_ms={record.get('command_ms', '-'):>6} "
                f"counted={record.get('counted')}"
                + (f" error={record['error']}" if "error" in record else ""),
                flush=True,
            )

    summaries: dict[str, Any] = {}
    for selector in selectors:
        values = samples[selector.label]
        low, high = median_interval(values, resamples=resamples, seed=seed)
        summaries[selector.label] = {
            **selector.describe(),
            "trials_attempted": trials,
            "trials_counted": len(values),
            "trials_not_counted": trials - len(values),
            **summarise(values),
            "p50": quantile(values, 0.5),
            "median_ci_low": low,
            "median_ci_high": high,
            "unit": "milliseconds",
        }

    if existing_container is None:
        for selector in selectors:
            remove_container(selector, containers[selector.label])

    return {
        "summaries": summaries,
        "trials": per_trial,
        "target": {
            "mode": "pre-existing" if existing_container else "throwaway",
            "containers": containers,
            "comparable_to_collected_runs": bool(existing_container),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--runtime",
        dest="runtimes",
        action="append",
        required=True,
        metavar="LABEL=/path/to/docker",
        help="a runtime to measure; repeat to interleave two or more",
    )
    parser.add_argument("--trials", type=int, default=100,
                        help="per runtime (default 100)")
    parser.add_argument("--compose-file", type=Path, default=DEFAULT_COMPOSE)
    parser.add_argument("--container-prefix", default=DEFAULT_CONTAINER_PREFIX)
    parser.add_argument(
        "--existing-container",
        default=None,
        help=(
            "measure against an already-running container (e.g. "
            "aep-phase2-redis72) instead of a throwaway one. Makes the number "
            "comparable in absolute terms to the collected runs; requires a "
            "single --runtime, and this probe will never recreate the target."
        ),
    )
    parser.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args(argv)

    selectors: list[RuntimeSelector] = []
    try:
        for specification in arguments.runtimes:
            label, separator, path = specification.partition("=")
            if not separator:
                print(f"REFUSING: --runtime {specification!r} is not LABEL=PATH",
                      file=sys.stderr)
                return 2
            selectors.append(RuntimeSelector(label.strip(), Path(path.strip())))

        image = pinned_image(arguments.compose_file)

        print("=" * 78)
        print("Phase 10: docker kill -s KILL latency, per runtime")
        print("=" * 78)
        print(f"  image           {image}")
        print(f"  trials          {arguments.trials} per runtime, round-robined")
        print(f"  kernel          {platform.release()}")
        for selector in selectors:
            print(f"  runtime         {selector.label} -> {selector.binary}")
        print()

        payload: dict[str, Any] = {
            "probe": "phase10-kill-latency",
            "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kernel": platform.release(),
            "platform": platform.platform(),
            "image": image,
            "instrument": (
                "experiments.harness.redis_kill.kill_redis command_ms -- "
                "time.monotonic() around subprocess.run(['docker','kill','-s',"
                "'KILL',container])"
            ),
            "comparable_historical_source": (
                "reports/raw/e1-kill-latency-by-run.csv (issue_to_return_ns, "
                "n=300, median 961.6 ms, range 681.8-1673.9 ms, Docker Desktop "
                "shim). NOT comparable to \\ProcessKillWindowMin/Max 419-992 ms, "
                "which is the write-to-death window of the durability probe."
            ),
            "resamples": arguments.resamples,
            "bootstrap_seed": arguments.bootstrap_seed,
        }
        payload.update(
            measure(
                selectors,
                trials=arguments.trials,
                image=image,
                container_prefix=arguments.container_prefix,
                resamples=arguments.resamples,
                seed=arguments.bootstrap_seed,
                existing_container=arguments.existing_container,
            )
        )

        print()
        print("--- summary ---")
        for label, summary in payload["summaries"].items():
            print(
                f"  {label:16s} n={summary['trials_counted']:3d}  "
                f"min={summary['min']}  median={summary['median']}  "
                f"p95={summary['p95']}  max={summary['max']}  "
                f"median 95% CI [{summary['median_ci_low']}, "
                f"{summary['median_ci_high']}]"
            )

        if arguments.output:
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(
                json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
            )
            print(f"\nwrote {arguments.output}")
        return 0
    except MeasurementError as failure:
        print(f"REFUSING: {failure}", file=sys.stderr)
        return 1
    finally:
        for selector in selectors:
            selector.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
