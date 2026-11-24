"""Connector-verifiable, one-use verified-dispatch provenance tests."""

from __future__ import annotations

import copy
import uuid

import pytest

import aep_core.core.request_binding as request_binding_module
from aep_core.core.request_binding import RequestBindingMismatchError, VerifiedDispatch
from tests.request_binding_helpers import verified_dispatch


def _consume(dispatch, **changes):
    binding = dispatch.binding
    values = {
        "connector_identity": binding.connector_identity,
        "connector_operation": binding.connector_operation,
        "endpoint_profile_id": binding.endpoint_profile_id,
        "endpoint_profile_version": binding.endpoint_profile_version,
        "execution_id": binding.execution_id,
        "step_id": binding.step_id,
        "intent_id": binding.intent_id,
        "correlation_id": binding.correlation_id,
    }
    values.update(changes)
    return request_binding_module.consume_verified_dispatch(dispatch, **values)


@pytest.mark.asyncio
async def test_only_successful_verification_can_issue_connector_acceptable_dispatch():
    dispatch = await verified_dispatch(str(uuid.uuid4()))
    material = _consume(dispatch)
    assert material == dispatch.exact_request_bytes
    with pytest.raises(RequestBindingMismatchError):
        _consume(dispatch)


@pytest.mark.asyncio
async def test_direct_construction_and_object_new_forgery_are_rejected():
    issued = await verified_dispatch(str(uuid.uuid4()))
    with pytest.raises((TypeError, RequestBindingMismatchError)):
        VerifiedDispatch(issued.exact_request_bytes, issued.binding)

    forged = object.__new__(VerifiedDispatch)
    object.__setattr__(forged, "exact_request_bytes", issued.exact_request_bytes)
    object.__setattr__(forged, "binding", issued.binding)
    with pytest.raises(RequestBindingMismatchError):
        _consume(forged)


@pytest.mark.asyncio
async def test_legacy_module_token_cannot_forge_provenance():
    issued = await verified_dispatch(str(uuid.uuid4()))
    token = getattr(request_binding_module, "_VERIFIED_DISPATCH_TOKEN", None)
    if token is None:
        return
    forged = VerifiedDispatch(
        issued.exact_request_bytes, issued.binding, _token=token
    )
    with pytest.raises(RequestBindingMismatchError):
        _consume(forged)


@pytest.mark.asyncio
async def test_copied_lookalike_and_subclassed_dispatches_are_rejected():
    issued = await verified_dispatch(str(uuid.uuid4()))
    try:
        copied = copy.copy(issued)
    except RequestBindingMismatchError:
        copied = None
    if copied is not None:
        with pytest.raises(RequestBindingMismatchError):
            _consume(copied)

    class Lookalike:
        exact_request_bytes = issued.exact_request_bytes
        binding = issued.binding

    with pytest.raises(RequestBindingMismatchError):
        _consume(Lookalike())

    try:
        class Subclass(VerifiedDispatch):
            pass
    except TypeError:
        return
    subclassed = object.__new__(Subclass)
    object.__setattr__(subclassed, "exact_request_bytes", issued.exact_request_bytes)
    object.__setattr__(subclassed, "binding", issued.binding)
    with pytest.raises(RequestBindingMismatchError):
        _consume(subclassed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,replacement",
    [
        ("execution_id", "other-execution"),
        ("step_id", "other-step"),
        ("intent_id", str(uuid.uuid4())),
        ("correlation_id", str(uuid.uuid4())),
        ("connector_identity", "other-connector"),
        ("connector_operation", "other.operation/mutate"),
        ("endpoint_profile_id", "other-endpoint"),
        ("endpoint_profile_version", "2"),
    ],
)
async def test_provenance_cannot_be_transplanted_to_another_context(field, replacement):
    dispatch = await verified_dispatch(str(uuid.uuid4()))
    with pytest.raises(RequestBindingMismatchError):
        _consume(dispatch, **{field: replacement})


@pytest.mark.asyncio
async def test_replacement_material_or_binding_invalidates_provenance():
    material_dispatch = await verified_dispatch(str(uuid.uuid4()))
    object.__setattr__(
        material_dispatch,
        "exact_request_bytes",
        material_dispatch.exact_request_bytes + b" ",
    )
    with pytest.raises(RequestBindingMismatchError):
        _consume(material_dispatch)

    binding_dispatch = await verified_dispatch(str(uuid.uuid4()))
    object.__setattr__(
        binding_dispatch,
        "binding",
        binding_dispatch.binding.model_copy(update={"step_id": "replacement-step"}),
    )
    with pytest.raises(RequestBindingMismatchError):
        _consume(binding_dispatch)


@pytest.mark.asyncio
async def test_stale_unconsumed_capability_is_rejected(monkeypatch):
    dispatch = await verified_dispatch(str(uuid.uuid4()))
    current = request_binding_module.time.monotonic()
    monkeypatch.setattr(
        request_binding_module.time, "monotonic", lambda: current + 3_600
    )
    with pytest.raises(RequestBindingMismatchError):
        _consume(dispatch)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,replacement",
    [
        ("request_material_ref", "vault_zyxwvutsrqponmlkjihgfedc"),
        ("request_material_version", 2),
        ("vault_object_version", 2),
        ("descriptor_version", "aep.safe-request/2"),
        ("canonicalization_version", "aep.canonical-json/2"),
        ("credential_binding_id", "other-credential"),
        ("credential_binding_version", "2"),
        ("wire_codec_version", "other-wire/2"),
        ("vault_encryption_key_id", "other-vault-key"),
        ("commitment_key_id", "other-commitment-key"),
        ("request_fingerprint", "b" * 64),
        ("request_binding_digest", "c" * 64),
        ("created_at_ms", 1_800_000_000_001),
        ("intent_creation_not_after_ms", 1_800_000_010_001),
        ("dispatch_material_not_after_ms", 1_800_000_030_001),
        ("retention_not_after_ms", 1_802_678_400_001),
    ],
)
async def test_material_descriptor_version_key_digest_and_deadline_replacement_is_rejected(
    field, replacement
):
    dispatch = await verified_dispatch(str(uuid.uuid4()))
    object.__setattr__(
        dispatch,
        "binding",
        dispatch.binding.model_copy(update={field: replacement}),
    )
    with pytest.raises(RequestBindingMismatchError):
        _consume(dispatch)
