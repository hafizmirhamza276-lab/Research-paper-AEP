"""Contract tests for the Phase 2 durability abstraction."""

import asyncio

import pytest

from src.core.durability import (
    DurabilityBarrier,
    DurabilityBarrierError,
    DurabilityCapabilityError,
    DurabilityMode,
    FakeDurabilityBarrier,
    RealWaitAofDurabilityBarrier,
)


_DEFAULT_WAITAOF_RESPONSE = object()


class _ScriptedRedis:
    def __init__(
        self,
        *,
        version="7.2.0",
        appendonly="yes",
        aof_enabled=1,
        command_info=None,
        waitaof_response=_DEFAULT_WAITAOF_RESPONSE,
    ):
        self.version = version
        self.appendonly = appendonly
        self.aof_enabled = aof_enabled
        self.command_info = (
            {"waitaof": {"name": "waitaof", "arity": 4}}
            if command_info is None
            else command_info
        )
        self.waitaof_response = (
            [1, 0]
            if waitaof_response is _DEFAULT_WAITAOF_RESPONSE
            else waitaof_response
        )
        self.calls = []

    async def info(self, section):
        self.calls.append(("INFO", section))
        if section == "server":
            return {"redis_version": self.version}
        if section == "persistence":
            return {"aof_enabled": self.aof_enabled}
        raise AssertionError(section)

    async def config_get(self, *names):
        self.calls.append(("CONFIG GET", *names))
        return {"appendonly": self.appendonly}

    async def execute_command(self, *args):
        self.calls.append(args)
        if args == ("COMMAND", "INFO", "WAITAOF"):
            return self.command_info
        if args[:1] == ("WAITAOF",):
            if isinstance(self.waitaof_response, BaseException):
                raise self.waitaof_response
            return self.waitaof_response
        raise AssertionError(args)


@pytest.mark.asyncio
async def test_fake_durability_barrier_acknowledges_without_redis_command():
    barrier = FakeDurabilityBarrier()
    assert isinstance(barrier, DurabilityBarrier)
    assert barrier.test_only is True
    assert await barrier.confirm_durable(object(), 500) is True


@pytest.mark.asyncio
async def test_fake_durability_barrier_rejects_nonpositive_timeout():
    with pytest.raises(ValueError, match="positive"):
        await FakeDurabilityBarrier().confirm_durable(object(), 0)


@pytest.mark.asyncio
async def test_real_waitaof_barrier_requires_startup_validation():
    barrier = RealWaitAofDurabilityBarrier()
    assert isinstance(barrier, DurabilityBarrier)
    with pytest.raises(
        DurabilityCapabilityError, match="startup validation"
    ) as rejected:
        await barrier.confirm_durable(object(), 500)
    assert not isinstance(rejected.value, NotImplementedError)


@pytest.mark.asyncio
async def test_waitaof_startup_validation_accepts_redis_72_with_aof():
    client = _ScriptedRedis(version="7.2.5")
    barrier = RealWaitAofDurabilityBarrier(mode=DurabilityMode.WAITAOF)

    capabilities = await barrier.validate_startup(client)

    assert capabilities.redis_version == "7.2.5"
    assert capabilities.aof_enabled is True
    assert capabilities.mode is DurabilityMode.WAITAOF
    assert ("COMMAND", "INFO", "WAITAOF") in client.calls


@pytest.mark.parametrize(
    ("client", "mode", "message"),
    [
        (_ScriptedRedis(version="7.1.99"), DurabilityMode.WAITAOF, "7.2"),
        (_ScriptedRedis(appendonly="no"), DurabilityMode.WAITAOF, "AOF"),
        (_ScriptedRedis(aof_enabled=0), DurabilityMode.WAITAOF, "AOF"),
        (_ScriptedRedis(command_info={}), DurabilityMode.WAITAOF, "WAITAOF"),
        (_ScriptedRedis(), "unsupported-mode", "durability mode"),
    ],
)
@pytest.mark.asyncio
async def test_waitaof_startup_validation_rejects_unsupported_capability(
    client, mode, message
):
    barrier = RealWaitAofDurabilityBarrier(mode=mode)

    with pytest.raises(DurabilityCapabilityError, match=message):
        await barrier.validate_startup(client)


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ([1, 0], True),
        ((2, 0), True),
        ([0, 0], False),
    ],
)
@pytest.mark.asyncio
async def test_waitaof_scripted_acknowledgement(response, expected):
    client = _ScriptedRedis(waitaof_response=response)
    barrier = RealWaitAofDurabilityBarrier()
    await barrier.validate_startup(client)

    assert await barrier.confirm_durable(client, 753) is expected
    assert client.calls[-1] == ("WAITAOF", 1, 0, 753)


@pytest.mark.parametrize(
    "response",
    [None, [], [1], [1, 0, 0], ["1", 0], [True, 0], {"local": 1}],
)
@pytest.mark.asyncio
async def test_waitaof_malformed_response_fails_closed(response):
    client = _ScriptedRedis(waitaof_response=response)
    barrier = RealWaitAofDurabilityBarrier()
    await barrier.validate_startup(client)

    with pytest.raises(DurabilityBarrierError, match="malformed"):
        await barrier.confirm_durable(client, 500)


@pytest.mark.parametrize(
    "failure",
    [TimeoutError("timed out"), ConnectionError("lost"), RuntimeError("command")],
)
@pytest.mark.asyncio
async def test_waitaof_command_failure_fails_closed(failure):
    client = _ScriptedRedis(waitaof_response=failure)
    barrier = RealWaitAofDurabilityBarrier()
    await barrier.validate_startup(client)

    with pytest.raises(DurabilityBarrierError, match="WAITAOF command failed"):
        await barrier.confirm_durable(client, 500)


@pytest.mark.asyncio
async def test_waitaof_requires_successful_startup_validation():
    client = _ScriptedRedis()
    barrier = RealWaitAofDurabilityBarrier()

    with pytest.raises(DurabilityCapabilityError, match="startup validation"):
        await barrier.confirm_durable(client, 500)

    assert not any(call[:1] == ("WAITAOF",) for call in client.calls)


@pytest.mark.asyncio
async def test_waitaof_rejects_nonpositive_or_boolean_timeout():
    client = _ScriptedRedis()
    barrier = RealWaitAofDurabilityBarrier()
    await barrier.validate_startup(client)

    for invalid in (0, -1, True):
        with pytest.raises(ValueError, match="positive integer"):
            await barrier.confirm_durable(client, invalid)


@pytest.mark.asyncio
async def test_waitaof_asyncio_timeout_fails_closed():
    client = _ScriptedRedis(waitaof_response=asyncio.TimeoutError())
    barrier = RealWaitAofDurabilityBarrier()
    await barrier.validate_startup(client)

    with pytest.raises(DurabilityBarrierError, match="WAITAOF command failed"):
        await barrier.confirm_durable(client, 500)
