#!/usr/bin/env python3
"""Prove the live Redis matches redis/phase2.conf, or fail the build.

CI cannot mount `redis/phase2.conf` into a GitHub Actions service container:
service containers start before the repository is checked out and their
command line cannot be extended. The honest response is not to quietly run
the suite against a default Redis -- AOF would be off and every WAITAOF
durability claim in docs/22-formal-model.md would be evidenced by a server
that cannot provide it.

Instead this script derives the required settings *from phase2.conf itself*,
applies the runtime-settable ones with CONFIG SET, and then asserts the live
server reports them. Deriving rather than hardcoding means the CI
environment cannot drift from the compose environment: change phase2.conf and
CI follows, or fails.

It additionally asserts the two capabilities the protocol depends on and
which no config file can promise:

  * ``redis_version >= 7.2`` -- WAITAOF does not exist before it;
  * ``COMMAND INFO WAITAOF`` returns a descriptor -- the command is really
    there, not merely implied by a version string.

Usage::

    python scripts/verify_redis_semantics.py --url redis://127.0.0.1:6379/15 --apply
    python scripts/verify_redis_semantics.py --url redis://127.0.0.1:6379/15
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONF = REPO_ROOT / "redis" / "phase2.conf"

MINIMUM_REDIS_VERSION = (7, 2)

#: Directives that CONFIG SET can change on a running server and that carry
#: protocol meaning. Anything else in phase2.conf is startup-only (bind,
#: port, databases, appenddirname) or environment-specific.
RUNTIME_SETTABLE = ("appendonly", "appendfsync", "aof-use-rdb-preamble", "save")

#: Directives whose value must match phase2.conf exactly after apply.
MUST_MATCH = ("appendonly", "appendfsync", "aof-use-rdb-preamble")


class SemanticsFailure(Exception):
    """The live server does not provide phase2.conf semantics."""


def parse_conf(path: Path) -> dict[str, str]:
    """Parse a redis.conf into {directive: value}. Last occurrence wins."""
    if not path.is_file():
        raise SemanticsFailure(f"Redis config not found: {path}")

    directives: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, value = line.partition(" ")
        # `save ""` means "no RDB snapshots"; redis expects an empty string.
        directives[name.strip().lower()] = value.strip().strip('"')
    return directives


def parse_version(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in version.split("."):
        digits = ""
        for character in chunk:
            if not character.isdigit():
                break
            digits += character
        if not digits:
            break
        parts.append(int(digits))
    if not parts:
        raise SemanticsFailure(f"unparseable redis_version: {version!r}")
    return tuple(parts)


def apply_settings(client, wanted: dict[str, str]) -> list[str]:
    """CONFIG SET every runtime-settable directive present in the config."""
    applied = []
    for directive in RUNTIME_SETTABLE:
        if directive not in wanted:
            continue
        value = wanted[directive]
        try:
            client.config_set(directive, value)
        except Exception as exc:
            raise SemanticsFailure(
                f"CONFIG SET {directive} {value!r} failed: "
                f"{type(exc).__name__}: {exc}"
            ) from None
        applied.append(f"{directive}={value!r}")
    return applied


def verify(client, wanted: dict[str, str]) -> list[str]:
    """Assert the live server matches phase2.conf and supports WAITAOF."""
    checks: list[str] = []

    server_info = client.info("server")
    version = server_info.get("redis_version", "")
    version_tuple = parse_version(version)
    if version_tuple[:2] < MINIMUM_REDIS_VERSION:
        raise SemanticsFailure(
            f"redis_version {version} is below the required "
            f"{'.'.join(map(str, MINIMUM_REDIS_VERSION))} -- WAITAOF does not "
            "exist on this server, so the durability barrier cannot be evidenced"
        )
    checks.append(f"redis_version={version}")

    for directive in MUST_MATCH:
        if directive not in wanted:
            continue
        expected = wanted[directive]
        live = client.config_get(directive).get(directive)
        if isinstance(live, bytes):
            live = live.decode("ascii", errors="replace")
        if str(live).lower() != expected.lower():
            raise SemanticsFailure(
                f"{directive}: live server reports {live!r}, "
                f"redis/phase2.conf requires {expected!r}"
            )
        checks.append(f"{directive}={live}")

    persistence = client.info("persistence")
    aof_enabled = persistence.get("aof_enabled")
    if int(aof_enabled or 0) != 1:
        raise SemanticsFailure(
            f"aof_enabled={aof_enabled!r}; AOF is not actually active. "
            "appendonly may be set while the rewrite has not completed."
        )
    checks.append("aof_enabled=1")

    command_info = client.execute_command("COMMAND", "INFO", "WAITAOF")
    descriptor = None
    if isinstance(command_info, dict):
        descriptor = command_info.get("waitaof") or command_info.get(b"waitaof")
    elif isinstance(command_info, (list, tuple)) and command_info:
        descriptor = command_info[0]
    if not descriptor:
        raise SemanticsFailure(
            "COMMAND INFO WAITAOF returned no descriptor -- the server does "
            "not implement WAITAOF despite reporting a 7.2+ version"
        )
    checks.append("waitaof=present")

    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a live Redis provides redis/phase2.conf semantics."
    )
    parser.add_argument("--url", required=True, help="redis:// URL to check")
    parser.add_argument("--conf", type=Path, default=DEFAULT_CONF)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="CONFIG SET the runtime-settable directives before verifying",
    )
    arguments = parser.parse_args(argv)

    try:
        import redis
    except ImportError:
        print("GATE FAILED: redis-py is not installed", file=sys.stderr)
        return 1

    try:
        wanted = parse_conf(arguments.conf)
        client = redis.Redis.from_url(arguments.url, decode_responses=True)
        client.ping()

        if arguments.apply:
            for applied in apply_settings(client, wanted):
                print(f"  applied {applied}")

        for check in verify(client, wanted):
            print(f"  verified {check}")
    except SemanticsFailure as failure:
        print(f"GATE FAILED: {failure}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 -- any fault here must fail closed
        print(
            f"GATE FAILED: could not verify {arguments.url}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    print(f"OK: live Redis matches {arguments.conf.name} semantics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
