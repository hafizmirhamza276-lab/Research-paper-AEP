r"""How fast, and how tightly, does each candidate fault mechanism land?

WS-3's problem, stated precisely. AEP-full dispatches **iff** ``WAITAOF``
returns before the fault lands, so the measured prevention effect is a draw from
the injector's landing-latency distribution rather than a property of the
protocol. `paper/sections/08-threats.tex` §A(e) concedes exactly this. The fix
is a fault whose landing time is small and tight *relative to a WAITAOF round
trip* -- under ``appendfsync everysec`` that round trip is 0-1000 ms, uniform-ish
in the phase of the fsync cycle.

Two different quantities, and conflating them is how this gets chosen wrong:

* **command latency** -- how long the injector's own command takes to return.
  This is what `experiments/harness/redis_kill.py:96-108` times as ``command_ms``
  and what Phase 10 reported (native ``docker kill`` median 317 ms). It is
  measured here the same way so the numbers are comparable.
* **landing latency** -- how long until the server can no longer answer a
  client. *This* is what races ``WAITAOF``. For ``docker kill`` the two are
  nearly the same. For ``docker pause`` they are not: the freeze takes effect
  well before the CLI returns, which is the whole reason the mechanism is a
  candidate.

Landing is measured directly rather than inferred: a probe socket holds an open
connection and issues ``PING`` in a tight loop with a short timeout, and the
landing time is the interval from issuing the fault command to the first PING
that does not come back.

Every mechanism is restored afterwards, and the script refuses to start unless
the stack is healthy, because a half-restored host would silently poison every
measurement after the first failure.
"""

from __future__ import annotations

import argparse
import json
import socket
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CONTAINER = "aep-phase2-redis72"
HOST, PORT = "127.0.0.1", 6381
COMPOSE = str(REPO / "compose.phase2.yml")

#: What a WAITAOF round trip costs under `appendfsync everysec`, which is the
#: yardstick every number below is judged against. Redis fsyncs once a second,
#: so a WAITAOF issued at a uniformly random phase returns in U(0, 1000) ms.
WAITAOF_WINDOW_MS = 1000.0


def run(*argv: str, timeout: float = 60.0) -> tuple[int, str, float]:
    started = time.monotonic()
    try:
        done = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout
        )
        return done.returncode, done.stderr.strip()[-200:], (
            time.monotonic() - started
        ) * 1000.0
    except subprocess.TimeoutExpired:
        return 124, "timeout", (time.monotonic() - started) * 1000.0


#: Probe timeout. This is the RESOLUTION of every landing number below, so it
#: is small: a healthy loopback PING round trip is under 0.2 ms, and a 50 ms
#: timeout (the first version of this script) quantised iptables' 3 ms landing
#: to 54 ms and would have made a partition look ten times slower than it is.
PROBE_TIMEOUT_SECONDS = 0.010


class Probe:
    """An open connection that reports when the server stops answering."""

    def __init__(self) -> None:
        self.sock = socket.create_connection((HOST, PORT), timeout=5.0)
        self.sock.settimeout(PROBE_TIMEOUT_SECONDS)

    def _ping(self) -> bool:
        try:
            self.sock.sendall(b"*1\r\n$4\r\nPING\r\n")
            return bool(self.sock.recv(64))
        except Exception:
            return False

    def responsive(self) -> bool:
        """One failure is confirmed by a second attempt.

        At a 10 ms timeout a single scheduling hiccup on a loaded host could
        read as a landed fault. Every mechanism here is monotone -- once it has
        landed the server never answers again -- so re-checking costs nothing
        when the fault is real and removes the false positives when it is not.
        """
        if self._ping():
            return True
        return self._ping()

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass


@dataclass
class Mechanism:
    key: str
    describe: str
    #: Instantiates which class of the paper's failure model.
    failure_class: str
    arm: Callable[[], tuple[int, str, float]]
    restore: Callable[[], None]
    #: True when the mechanism leaves the server dead and needs a restart.
    kills: bool


def _restore_stack() -> None:
    run("docker", "unpause", CONTAINER, timeout=30)
    run("docker", "start", CONTAINER, timeout=60)
    for _ in range(60):
        code, _, _ = run("docker", "exec", CONTAINER, "redis-cli", "-n", "15", "PING")
        if code == 0:
            return
        time.sleep(0.5)


def _drop_rule(action: str) -> tuple[int, str, float]:
    return run(
        "iptables", action, "OUTPUT", "-p", "tcp", "-d", HOST,
        "--dport", str(PORT), "-j", "DROP", timeout=30,
    )


def _netem(action: str) -> tuple[int, str, float]:
    if action == "add":
        return run(
            "tc", "qdisc", "add", "dev", "lo", "root", "netem",
            "delay", "5000ms", timeout=30,
        )
    return run("tc", "qdisc", "del", "dev", "lo", "root", timeout=30)


MECHANISMS: tuple[Mechanism, ...] = (
    Mechanism(
        "docker-kill",
        "docker kill -s KILL -- the mechanism the frozen cells used",
        "F3 crash-stop of the state store",
        lambda: run("docker", "kill", "-s", "KILL", CONTAINER),
        _restore_stack,
        kills=True,
    ),
    Mechanism(
        "docker-pause",
        "docker pause -- cgroup-v2 freezer; the server stops answering and is "
        "then killed, so the run's end state is identical to docker-kill",
        "F3 crash-stop of the state store",
        lambda: run("docker", "pause", CONTAINER),
        _restore_stack,
        kills=False,
    ),
    Mechanism(
        "iptables-drop",
        "iptables -I OUTPUT ... -j DROP on the published port -- the client's "
        "packets are discarded; the server is alive and unaware",
        "F2 network partition -- NOT a crash",
        lambda: _drop_rule("-I"),
        lambda: (_drop_rule("-D"), None)[1],
        kills=False,
    ),
    Mechanism(
        "tc-netem-delay",
        "tc qdisc netem delay 5000ms on lo -- every loopback packet is delayed, "
        "INCLUDING the mock provider's on 127.0.0.1:8099",
        "F2 network partition (asymmetric, delay-only) -- NOT a crash",
        lambda: _netem("add"),
        lambda: (_netem("del"), None)[1],
        kills=False,
    ),
)


def measure(mechanism: Mechanism, trials: int) -> dict:
    command_ms: list[float] = []
    landing_ms: list[float] = []
    failures = 0

    for index in range(trials):
        # Only the killing mechanism needs the container restarted; for the
        # others a responsiveness check is enough, and doing the full restore
        # anyway would have made this run four times longer for nothing.
        if mechanism.kills or index == 0:
            _restore_stack()
        try:
            probe = Probe()
        except OSError:
            failures += 1
            _restore_stack()
            continue
        if not probe.responsive():
            probe.close()
            failures += 1
            continue

        started = time.monotonic()
        code, stderr, elapsed = mechanism.arm()
        # Landing: poll from the moment the command was ISSUED, not from when
        # it returned -- for a freeze the effect precedes the return, and
        # measuring from the return would report a negative interval as zero.
        landed = None
        deadline = started + 10.0
        while time.monotonic() < deadline:
            if not probe.responsive():
                landed = (time.monotonic() - started) * 1000.0
                break
        probe.close()

        if code != 0:
            failures += 1
        command_ms.append(elapsed)
        if landed is not None:
            landing_ms.append(landed)
        else:
            failures += 1

        try:
            mechanism.restore()
        except Exception:
            pass
        if index % 20 == 19:
            print(f"    {index + 1}/{trials}", flush=True)

    _restore_stack()

    def summarise(values: list[float]) -> dict:
        if not values:
            return {}
        ordered = sorted(values)
        return {
            "n": len(ordered),
            "min": round(ordered[0], 1),
            "median": round(statistics.median(ordered), 1),
            "p95": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 1),
            "max": round(ordered[-1], 1),
            "spread_max_minus_min": round(ordered[-1] - ordered[0], 1),
            "iqr": round(
                ordered[int(0.75 * (len(ordered) - 1))]
                - ordered[int(0.25 * (len(ordered) - 1))],
                1,
            ),
        }

    landing = summarise(landing_ms)
    return {
        "mechanism": mechanism.key,
        "describes": mechanism.describe,
        "failure_class": mechanism.failure_class,
        "command_ms": summarise(command_ms),
        "landing_ms": landing,
        "failures": failures,
        # The decision number: what fraction of the WAITAOF window is still
        # available to the protocol after the fault has landed. Small is good;
        # it is the residual race.
        "landing_as_fraction_of_waitaof_window": (
            round(landing["median"] / WAITAOF_WINDOW_MS, 4) if landing else None
        ),
        # Disclosed rather than chased. `responsive()` confirms a failure with a
        # second attempt, so declaring the fault landed costs two timeouts:
        # every landing number below has a floor of ~20 ms regardless of how
        # fast the mechanism really is. Against a 1000 ms WAITAOF window that is
        # immaterial to the choice, but it means a reported 24 ms landing is
        # "at or below 24 ms", not "24 ms".
        "landing_measurement_floor_ms": round(PROBE_TIMEOUT_SECONDS * 2000, 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument(
        "--only", action="append", default=[], help="mechanism key; repeat"
    )
    parser.add_argument("--json", default=None)
    arguments = parser.parse_args(argv)

    print(f"target {CONTAINER} at {HOST}:{PORT}; {arguments.trials} trials each")
    print(f"WAITAOF window under appendfsync everysec: {WAITAOF_WINDOW_MS:.0f} ms")
    _restore_stack()

    results = []
    try:
        results = _measure_all(MECHANISMS, arguments)
    finally:
        # tc netem on `lo` delays EVERY loopback packet on this host. If this
        # script dies mid-trial and the qdisc survives, the mock provider, the
        # Redis client and anything else on 127.0.0.1 are all degraded, and the
        # next collection would be silently poisoned. Removed unconditionally.
        run("tc", "qdisc", "del", "dev", "lo", "root", timeout=15)
        _drop_rule("-D")
        _restore_stack()

    print("\n" + "=" * 78)
    print(f"{'mechanism':18s} {'class':42s} {'landing median':>15s}")
    for result in results:
        land = result["landing_ms"]
        print(
            f"{result['mechanism']:18s} {result['failure_class']:42s} "
            f"{(str(land.get('median')) + ' ms') if land else 'n/a':>15s}"
        )

    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(
                {"waitaof_window_ms": WAITAOF_WINDOW_MS,
                 "probe_timeout_ms": PROBE_TIMEOUT_SECONDS * 1000,
                 "results": results},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0


def _measure_all(mechanisms, arguments) -> list[dict]:
    results = []
    for mechanism in mechanisms:
        if arguments.only and mechanism.key not in arguments.only:
            continue
        print(f"\n=== {mechanism.key} -- {mechanism.failure_class} ===")
        print(f"    {mechanism.describe}")
        result = measure(mechanism, arguments.trials)
        results.append(result)
        cmd, land = result["command_ms"], result["landing_ms"]
        if cmd:
            print(
                f"  command  n={cmd['n']:3d} min={cmd['min']:8.1f} "
                f"median={cmd['median']:8.1f} p95={cmd['p95']:8.1f} "
                f"max={cmd['max']:8.1f} spread={cmd['spread_max_minus_min']:8.1f}"
            )
        if land:
            print(
                f"  LANDING  n={land['n']:3d} min={land['min']:8.1f} "
                f"median={land['median']:8.1f} p95={land['p95']:8.1f} "
                f"max={land['max']:8.1f} spread={land['spread_max_minus_min']:8.1f}"
            )
            print(
                f"  landing / WAITAOF window = "
                f"{result['landing_as_fraction_of_waitaof_window']}"
            )
        print(f"  failures {result['failures']}")
    return results


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
