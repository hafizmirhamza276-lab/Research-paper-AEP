"""Coverage for AEP's fail-closed rejection branches.

The Fail-Closed Invariant says: on corruption, ambiguity, or a safety-cap hit,
stop, fence, escalate -- never guess. Most of that invariant lives in
rejection branches that the happy-path suite never reaches: a malformed
version string from Redis, a lock engine that throws mid-command, a
durability acknowledgement someone tried to copy.

An untested rejection branch is an assumption, not an enforcement. These
tests exercise the branches directly so the claim "the system fails closed"
is evidenced rather than asserted.
"""

from __future__ import annotations

import copy
import math

import pytest

from aep_core.core.connector_contract import (
    ConnectorContractError,
    ReadbackResult,
    ReconciliationCapability,
    classify_readback,
    parse_readback_result,
    result_is_permitted,
)
from aep_core.core.durability import (
    DurabilityAck,
    DurabilityBarrierError,
    DurabilityCapabilityError,
    DurabilityMode,
    FakeDurabilityBarrier,
    RealWaitAofDurabilityBarrier,
    confirm_durable_ack,
    consume_durability_ack,
    dispatch_scope,
)
from aep_core.core.exceptions import (
    LockAcquisitionError,
    StateCorruptionError,
    StateSerializationError,
)
from aep_core.core.locks import DistributedLockManager
from aep_core.core.state_codec import decode_state, encode_state
from aep_core.core.validation import validate_execution_id

VALID_UUID4 = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


# ===========================================================================
# validation.py -- the execution-id boundary
# ===========================================================================


@pytest.mark.parametrize(
    "value",
    [None, 42, b"3f2504e0-4f89-41d3-9a0c-0305e82c3301", ["x"], object()],
)
def test_non_string_execution_id_is_rejected(value):
    with pytest.raises(ValueError, match="canonical UUIDv4"):
        validate_execution_id(value)


@pytest.mark.parametrize(
    "value",
    ["", "not-a-uuid", "3f2504e0-4f89-41d3-9a0c", "zzzzzzzz-4f89-41d3-9a0c-0305e82c3301"],
)
def test_unparseable_execution_id_is_rejected(value):
    with pytest.raises(ValueError, match="canonical UUIDv4"):
        validate_execution_id(value)


def test_a_non_v4_uuid_is_rejected():
    """UUIDv1 embeds a MAC address and timestamp; AEP requires random v4."""
    uuid_v1 = "a8098c1a-f86e-11da-bd1a-00112444be1e"

    with pytest.raises(ValueError, match="canonical UUIDv4"):
        validate_execution_id(uuid_v1)


@pytest.mark.parametrize(
    "value",
    [
        VALID_UUID4.upper(),
        VALID_UUID4.replace("-", ""),
        f"urn:uuid:{VALID_UUID4}",
        f"{{{VALID_UUID4}}}",
    ],
)
def test_non_canonical_spellings_of_a_valid_uuid4_are_rejected(value):
    """uuid.UUID() accepts these; AEP does not, because they alias one key."""
    with pytest.raises(ValueError, match="canonical UUIDv4"):
        validate_execution_id(value)


def test_the_canonical_form_is_returned_unchanged():
    assert validate_execution_id(VALID_UUID4) == VALID_UUID4


# ===========================================================================
# connector_contract.py -- totality of the response-class contract
# ===========================================================================


class _Observation:
    def __init__(self, result):
        self.result = result


def test_an_unrecognised_readback_string_degrades_to_unknown():
    """A connector inventing its own vocabulary must not be believed."""
    assert parse_readback_result(_Observation("SORT_OF_MAYBE")) is ReadbackResult.UNKNOWN


@pytest.mark.parametrize("value", [None, 7, object(), b"CONFIRMED"])
def test_a_non_string_non_enum_readback_degrades_to_unknown(value):
    assert parse_readback_result(_Observation(value)) is ReadbackResult.UNKNOWN


def test_an_observation_without_a_result_attribute_degrades_to_unknown():
    assert parse_readback_result(object()) is ReadbackResult.UNKNOWN


def test_an_enum_readback_passes_through():
    observation = _Observation(ReadbackResult.APPLIED)

    assert parse_readback_result(observation) is ReadbackResult.APPLIED


@pytest.mark.parametrize("capability", ["AUTHORITATIVE_READBACK", None, 3, object()])
def test_classification_refuses_a_capability_outside_the_contract(capability):
    """A bare string is exactly the failure mode Phase 1B removed."""
    with pytest.raises(ConnectorContractError, match="declared contract member"):
        classify_readback(capability, ReadbackResult.APPLIED)


@pytest.mark.parametrize("result", ["CONFIRMED", None, 3, object()])
def test_classification_refuses_a_result_outside_the_contract(result):
    with pytest.raises(ConnectorContractError, match="declared contract member"):
        classify_readback(ReconciliationCapability.AUTHORITATIVE_READBACK, result)


def test_no_readback_connectors_cannot_be_classified_at_all():
    with pytest.raises(ConnectorContractError):
        classify_readback(
            ReconciliationCapability.NO_READBACK, ReadbackResult.APPLIED
        )


def test_permission_table_is_total_over_the_contract():
    """Every capability/result pair must have an answer, not a KeyError."""
    for capability in ReconciliationCapability:
        for result in ReadbackResult:
            assert isinstance(result_is_permitted(capability, result), bool)


# ===========================================================================
# state_codec.py -- serialization refuses what it cannot round-trip
# ===========================================================================


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_refused_on_decode(literal):
    """A persisted NaN would compare unequal to itself and break CAS."""
    with pytest.raises((StateCorruptionError, StateSerializationError)):
        decode_state(f'{{"value": {literal}}}')


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_refused_on_encode(value):
    with pytest.raises(StateSerializationError):
        encode_state({"value": value})


@pytest.mark.parametrize("value", [None, 42, 3.5, object(), ["x"]])
def test_decode_refuses_input_that_is_neither_text_nor_bytes(value):
    """Anything that is not text or bytes is treated as corruption, not a bug."""
    with pytest.raises(StateCorruptionError):
        decode_state(value)


def test_decode_refuses_invalid_utf8_bytes():
    with pytest.raises(StateCorruptionError):
        decode_state(b'{"value": "\xff\xfe"}')


def test_decode_refuses_a_surrogate_bearing_string():
    with pytest.raises(StateCorruptionError):
        decode_state('{"value": "\ud800"}')


def test_a_finite_number_round_trips():
    assert decode_state(encode_state({"value": 1.5})) == {"value": 1.5}
    assert math.isfinite(decode_state('{"value": 1.5}')["value"])


# ===========================================================================
# locks.py -- engine faults surface as typed errors, never as silence
# ===========================================================================


class _ExplodingRedis:
    """A Redis whose every command raises, to drive the engine-fault paths."""

    def __init__(self, exception_type=ConnectionError):
        self.exception_type = exception_type

    async def set(self, *args, **kwargs):
        raise self.exception_type("engine down")

    def register_script(self, script):
        async def _call(keys=None, args=None):
            raise self.exception_type("engine down")

        return _call


@pytest.fixture
def exploding_lock_manager():
    return DistributedLockManager(_ExplodingRedis())


async def test_acquire_surfaces_an_engine_fault_as_a_typed_error(
    exploding_lock_manager,
):
    with pytest.raises(LockAcquisitionError, match="Lock engine fault on acquire"):
        await exploding_lock_manager.acquire_lock(VALID_UUID4, ttl_seconds=60)


async def test_release_surfaces_an_engine_fault_as_a_typed_error(
    exploding_lock_manager,
):
    with pytest.raises(LockAcquisitionError, match="Lock release fault"):
        await exploding_lock_manager.release_lock(VALID_UUID4, "some-token")


async def test_renew_surfaces_an_engine_fault_as_a_typed_error(
    exploding_lock_manager,
):
    with pytest.raises(LockAcquisitionError, match="Lock renew fault"):
        await exploding_lock_manager.renew_lock(
            VALID_UUID4, "some-token", extend_ms=30_000
        )


async def test_engine_fault_messages_do_not_leak_the_underlying_exception_text(
    exploding_lock_manager,
):
    """Only the failure class is disclosed -- exception text can carry secrets."""
    with pytest.raises(LockAcquisitionError) as excinfo:
        await exploding_lock_manager.acquire_lock(VALID_UUID4, ttl_seconds=60)

    assert "engine down" not in str(excinfo.value)
    assert "failure_class=ConnectionError" in str(excinfo.value)


# --- The Timeout Invariant: T_client <= T_lock - Buffer, Buffer >= 15s ------


@pytest.fixture
def lock_manager_for_guard(redis_client):
    return DistributedLockManager(redis_client)


async def test_a_buffer_below_fifteen_seconds_is_refused(lock_manager_for_guard):
    with pytest.raises(LockAcquisitionError, match="at least 15 seconds"):
        async with lock_manager_for_guard.lease(
            VALID_UUID4, ttl_seconds=60, buffer_margin_seconds=14
        ):
            pass


@pytest.mark.parametrize("ttl", [15, 10, 0, -1, True])
async def test_a_ttl_not_exceeding_the_buffer_is_refused(lock_manager_for_guard, ttl):
    with pytest.raises(LockAcquisitionError, match="greater than the buffer margin"):
        async with lock_manager_for_guard.lease(
            VALID_UUID4, ttl_seconds=ttl, buffer_margin_seconds=15
        ):
            pass


@pytest.mark.parametrize("deadline", [0, -5, 46, True])
async def test_a_client_deadline_violating_the_timeout_invariant_is_refused(
    lock_manager_for_guard, deadline
):
    """ttl 60 - buffer 15 leaves 45s; anything above that breaks the invariant."""
    with pytest.raises(LockAcquisitionError, match="T_client <= "):
        async with lock_manager_for_guard.lease(
            VALID_UUID4,
            ttl_seconds=60,
            buffer_margin_seconds=15,
            client_deadline_seconds=deadline,
        ):
            pass


@pytest.mark.parametrize("cap", [0, -1, True])
async def test_a_non_positive_lease_cap_is_refused(lock_manager_for_guard, cap):
    with pytest.raises(LockAcquisitionError, match="max_total_lease_seconds"):
        async with lock_manager_for_guard.lease(
            VALID_UUID4,
            ttl_seconds=60,
            buffer_margin_seconds=15,
            max_total_lease_seconds=cap,
        ):
            pass


# ===========================================================================
# durability.py -- the supported guard is uncopyable, single-use, scope-bound
# ===========================================================================


SCOPE = dispatch_scope(VALID_UUID4, "intent-1", 3)


def test_a_durability_ack_cannot_be_constructed_through_its_public_type():
    with pytest.raises(DurabilityBarrierError, match="supported barrier API"):
        DurabilityAck()


def test_a_durability_ack_cannot_be_subclassed():
    with pytest.raises(TypeError, match="final"):

        class Forged(DurabilityAck):
            pass


async def test_a_durability_ack_cannot_be_shallow_copied():
    ack = await confirm_durable_ack(
        FakeDurabilityBarrier(), object(), 1000, scope=SCOPE
    )

    with pytest.raises(DurabilityBarrierError, match="not copyable"):
        copy.copy(ack)


async def test_a_durability_ack_cannot_be_deep_copied():
    ack = await confirm_durable_ack(
        FakeDurabilityBarrier(), object(), 1000, scope=SCOPE
    )

    with pytest.raises(DurabilityBarrierError, match="not copyable"):
        copy.deepcopy(ack)


async def test_a_durability_ack_repr_discloses_only_its_scope():
    ack = await confirm_durable_ack(
        FakeDurabilityBarrier(), object(), 1000, scope=SCOPE
    )

    rendered = repr(ack)

    assert rendered == f"DurabilityAck(scope={SCOPE!r})"
    assert "_provenance" not in rendered


async def test_an_ack_is_single_use():
    ack = await confirm_durable_ack(
        FakeDurabilityBarrier(), object(), 1000, scope=SCOPE
    )
    consume_durability_ack(ack, scope=SCOPE)

    with pytest.raises(DurabilityBarrierError, match="already consumed"):
        consume_durability_ack(ack, scope=SCOPE)


async def test_an_ack_cannot_authorise_a_different_scope():
    ack = await confirm_durable_ack(
        FakeDurabilityBarrier(), object(), 1000, scope=SCOPE
    )
    other_scope = dispatch_scope(VALID_UUID4, "intent-1", 4)

    with pytest.raises(DurabilityBarrierError, match="does not authorise"):
        consume_durability_ack(ack, scope=other_scope)

    # A failed scope check consumes the guard as well: it cannot later be
    # replayed with the correct scope.
    with pytest.raises(DurabilityBarrierError, match="already consumed"):
        consume_durability_ack(ack, scope=SCOPE)


@pytest.mark.parametrize("impostor", [None, "ack", object(), 42])
def test_only_a_real_ack_can_be_consumed(impostor):
    with pytest.raises(DurabilityBarrierError, match="valid in-process"):
        consume_durability_ack(impostor, scope=SCOPE)


@pytest.mark.parametrize("scope", ["", None, 42, b"scope"])
async def test_an_ack_requires_a_non_empty_string_scope(scope):
    with pytest.raises(DurabilityBarrierError, match="non-empty string"):
        await confirm_durable_ack(
            FakeDurabilityBarrier(), object(), 1000, scope=scope
        )


async def test_no_ack_is_issued_when_the_barrier_declines():
    class _DecliningBarrier:
        async def confirm_durable(self, connection, timeout_ms):
            return False

    with pytest.raises(DurabilityBarrierError, match="did not acknowledge"):
        await confirm_durable_ack(_DecliningBarrier(), object(), 1000, scope=SCOPE)


async def test_the_fake_barrier_refuses_a_non_positive_timeout():
    with pytest.raises(ValueError, match="positive"):
        await FakeDurabilityBarrier().confirm_durable(object(), 0)


# --- Startup validation refuses anything it cannot prove -------------------


#: Distinguishes "caller did not override this" from "caller passed None",
#: since None is itself one of the malformed responses under test.
_DEFAULT = object()


class _StubRedis:
    """Serves canned INFO/CONFIG/COMMAND responses to startup validation."""

    def __init__(
        self, *, server=_DEFAULT, persistence=_DEFAULT, aof=_DEFAULT, command=_DEFAULT
    ):
        self._server = {"redis_version": "7.2.5"} if server is _DEFAULT else server
        self._persistence = (
            {"aof_enabled": 1} if persistence is _DEFAULT else persistence
        )
        self._aof = (
            {"appendonly": "yes", "appendfsync": "everysec"} if aof is _DEFAULT else aof
        )
        self._command = (
            {"waitaof": {"name": "waitaof"}} if command is _DEFAULT else command
        )

    async def info(self, section):
        return self._server if section == "server" else self._persistence

    async def config_get(self, *names):
        return self._aof

    async def execute_command(self, *args):
        return self._command


@pytest.mark.parametrize("mode", ["rdb", "none", 42, None])
async def test_startup_refuses_an_unsupported_durability_mode(mode):
    barrier = RealWaitAofDurabilityBarrier.__new__(RealWaitAofDurabilityBarrier)
    barrier.mode = mode
    barrier._startup_validated = False
    barrier._capabilities = None

    with pytest.raises(DurabilityCapabilityError, match="unsupported durability mode"):
        await barrier.validate_startup(_StubRedis())


async def test_startup_refuses_when_a_probe_command_raises():
    class _BrokenRedis(_StubRedis):
        async def info(self, section):
            raise ConnectionError("gone")

    with pytest.raises(DurabilityCapabilityError, match="startup validation command failed"):
        await RealWaitAofDurabilityBarrier().validate_startup(_BrokenRedis())


@pytest.mark.parametrize("server", [None, "not-a-mapping", 42, []])
async def test_startup_refuses_malformed_server_info(server):
    with pytest.raises(DurabilityCapabilityError, match="malformed server INFO"):
        await RealWaitAofDurabilityBarrier().validate_startup(
            _StubRedis(server=server)
        )


@pytest.mark.parametrize("version", [None, 42, "", "seven.two", b"7.2.5"])
async def test_startup_refuses_a_malformed_version_string(version):
    with pytest.raises(DurabilityCapabilityError, match="malformed version"):
        await RealWaitAofDurabilityBarrier().validate_startup(
            _StubRedis(server={"redis_version": version})
        )


@pytest.mark.parametrize("version", ["7.1.0", "7.0.15", "6.2", "5.0.0"])
async def test_startup_refuses_a_redis_older_than_7_2(version):
    with pytest.raises(DurabilityCapabilityError, match="7.2 or newer"):
        await RealWaitAofDurabilityBarrier().validate_startup(
            _StubRedis(server={"redis_version": version})
        )


@pytest.mark.parametrize("aof", [None, "nope", 42, []])
async def test_startup_refuses_malformed_aof_configuration(aof):
    with pytest.raises(DurabilityCapabilityError, match="malformed AOF configuration"):
        await RealWaitAofDurabilityBarrier().validate_startup(_StubRedis(aof=aof))


@pytest.mark.parametrize(
    "appendonly", ["no", "", None, 42, b"no"]
)
async def test_startup_refuses_a_disabled_aof(appendonly):
    with pytest.raises(DurabilityCapabilityError, match="AOF must be enabled"):
        await RealWaitAofDurabilityBarrier().validate_startup(
            _StubRedis(aof={"appendonly": appendonly, "appendfsync": "everysec"})
        )


async def test_startup_accepts_a_bytes_encoded_appendonly_yes():
    """redis-py may or may not decode responses; both spellings must work."""
    capabilities = await RealWaitAofDurabilityBarrier().validate_startup(
        _StubRedis(aof={"appendonly": b"yes", "appendfsync": b"everysec"})
    )

    assert capabilities.aof_enabled is True
    assert capabilities.mode is DurabilityMode.WAITAOF


async def test_startup_succeeds_against_a_conforming_server():
    capabilities = await RealWaitAofDurabilityBarrier().validate_startup(_StubRedis())

    assert capabilities.redis_version == "7.2.5"
    assert capabilities.redis_version_tuple == (7, 2, 5)
    assert capabilities.aof_enabled is True


@pytest.mark.parametrize(
    "command_info", [None, {}, {"waitaof": None}, {"waitaof": {}}, "nope", 42]
)
async def test_startup_refuses_a_server_that_cannot_prove_waitaof(command_info):
    with pytest.raises(DurabilityCapabilityError):
        await RealWaitAofDurabilityBarrier().validate_startup(
            _StubRedis(command=command_info)
        )


async def test_startup_accepts_a_bytes_keyed_waitaof_descriptor():
    capabilities = await RealWaitAofDurabilityBarrier().validate_startup(
        _StubRedis(command={b"waitaof": {"name": "waitaof"}})
    )

    assert capabilities.mode is DurabilityMode.WAITAOF
