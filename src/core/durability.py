"""Durability barriers for Phase 2 write-ahead transitions.

The real barrier authorizes dispatch only after Redis 7.2+ acknowledges a
local AOF fsync for preceding writes on the exact same pinned connection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol, runtime_checkable


_MINIMUM_WAITAOF_REDIS_VERSION = (7, 2, 0)
_REDIS_VERSION_PREFIX = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?")


class DurabilityBarrierError(RuntimeError):
    """A local durability command could not safely authorize dispatch."""


class DurabilityCapabilityError(DurabilityBarrierError):
    """Redis cannot prove support for the selected durability mode."""


class DurabilityMode(str, Enum):
    """Approved production local-durability modes implemented by this module."""

    WAITAOF = "waitaof"


@dataclass(frozen=True)
class RedisDurabilityCapabilities:
    """Capabilities proved by production startup validation."""

    redis_version: str
    redis_version_tuple: tuple[int, int, int]
    aof_enabled: bool
    mode: DurabilityMode


@runtime_checkable
class DurabilityBarrier(Protocol):
    """Confirms that all prior writes on ``connection`` are durable."""

    async def confirm_durable(
        self, connection: Any, timeout_ms: int
    ) -> bool:
        """Return True only when the preceding same-connection write is durable."""


class FakeDurabilityBarrier:
    """TEST-ONLY barrier that never supplies production durability evidence."""

    test_only = True

    async def confirm_durable(
        self, connection: Any, timeout_ms: int
    ) -> bool:
        if timeout_ms <= 0:
            raise ValueError("durability timeout_ms must be positive")
        return True


class RealWaitAofDurabilityBarrier:
    """Redis 7.2+ AOF barrier using ``WAITAOF 1 0 <timeout-ms>``.

    ``validate_startup`` must succeed before ``confirm_durable`` can issue a
    command. The workflow invokes validation before every dispatch attempt, so
    an unsupported server or disabled AOF cannot silently reach the provider.
    """

    test_only = False

    def __init__(self, *, mode: DurabilityMode | str = DurabilityMode.WAITAOF):
        self.mode = mode
        self._startup_validated = False
        self._capabilities: RedisDurabilityCapabilities | None = None

    @staticmethod
    def _parse_version(version: Any) -> tuple[int, int, int]:
        if not isinstance(version, str):
            raise DurabilityCapabilityError(
                "Redis startup validation returned a malformed version"
            )
        match = _REDIS_VERSION_PREFIX.match(version)
        if match is None:
            raise DurabilityCapabilityError(
                "Redis startup validation returned a malformed version"
            )
        return tuple(int(part or 0) for part in match.groups())

    @staticmethod
    def _command_info_supports_waitaof(command_info: Any) -> bool:
        if not isinstance(command_info, Mapping):
            return False
        descriptor = command_info.get("waitaof")
        if descriptor is None:
            descriptor = command_info.get(b"waitaof")
        return isinstance(descriptor, Mapping) and bool(descriptor)

    async def validate_startup(
        self, redis_client: Any
    ) -> RedisDurabilityCapabilities:
        """Fail closed unless Redis proves WAITAOF and active local AOF."""

        self._startup_validated = False
        self._capabilities = None
        try:
            mode = DurabilityMode(self.mode)
        except (TypeError, ValueError):
            raise DurabilityCapabilityError(
                "unsupported durability mode"
            ) from None
        if mode is not DurabilityMode.WAITAOF:
            raise DurabilityCapabilityError(
                f"unsupported durability mode {mode.value!r}"
            )

        try:
            server_info = await redis_client.info("server")
            persistence_info = await redis_client.info("persistence")
            aof_config = await redis_client.config_get(
                "appendonly", "appendfsync"
            )
            command_info = await redis_client.execute_command(
                "COMMAND", "INFO", "WAITAOF"
            )
        except Exception as exc:
            raise DurabilityCapabilityError(
                "Redis durability startup validation command failed: "
                f"{type(exc).__name__}"
            ) from None

        if not isinstance(server_info, Mapping):
            raise DurabilityCapabilityError(
                "Redis startup validation returned malformed server INFO"
            )
        version = server_info.get("redis_version")
        version_tuple = self._parse_version(version)
        if version_tuple < _MINIMUM_WAITAOF_REDIS_VERSION:
            raise DurabilityCapabilityError(
                "WAITAOF durability mode requires Redis 7.2 or newer"
            )

        if not isinstance(aof_config, Mapping):
            raise DurabilityCapabilityError(
                "Redis startup validation returned malformed AOF configuration"
            )
        appendonly = aof_config.get("appendonly")
        if isinstance(appendonly, bytes):
            appendonly = appendonly.decode("ascii", errors="strict")
        if not isinstance(appendonly, str) or appendonly.lower() != "yes":
            raise DurabilityCapabilityError(
                "Redis AOF must be enabled for WAITAOF durability mode"
            )
        if (
            not isinstance(persistence_info, Mapping)
            or type(persistence_info.get("aof_enabled")) is not int
            or persistence_info.get("aof_enabled") != 1
        ):
            raise DurabilityCapabilityError(
                "Redis persistence INFO does not report AOF enabled"
            )
        if not self._command_info_supports_waitaof(command_info):
            raise DurabilityCapabilityError(
                "Redis does not report WAITAOF command support"
            )

        capabilities = RedisDurabilityCapabilities(
            redis_version=version,
            redis_version_tuple=version_tuple,
            aof_enabled=True,
            mode=mode,
        )
        self._capabilities = capabilities
        self._startup_validated = True
        return capabilities

    async def confirm_durable(
        self, connection: Any, timeout_ms: int
    ) -> bool:
        if type(timeout_ms) is not int or timeout_ms <= 0:
            raise ValueError("durability timeout_ms must be a positive integer")
        if not self._startup_validated or self._capabilities is None:
            raise DurabilityCapabilityError(
                "WAITAOF startup validation has not succeeded"
            )
        try:
            response = await connection.execute_command(
                "WAITAOF", 1, 0, timeout_ms
            )
        except Exception as exc:
            raise DurabilityBarrierError(
                f"WAITAOF command failed: {type(exc).__name__}"
            ) from None

        if (
            not isinstance(response, (list, tuple))
            or len(response) != 2
            or any(type(value) is not int or value < 0 for value in response)
        ):
            raise DurabilityBarrierError("malformed WAITAOF response")
        local_fsyncs, _replica_fsyncs = response
        return local_fsyncs >= 1
