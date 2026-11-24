"""Focused persisted safe-value and versioned-profile revalidation tests."""

from __future__ import annotations

import uuid

import pytest

from aep_core.core.request_binding import (
    CommitmentKeyring,
    EndpointProfile,
    ExactMutationRequest,
    PersistedRequestBinding,
    ProtectedFieldClass,
    RequestBindingError,
    RequestBindingService,
    SafeField,
    SafeValueKind,
    SafeValueRule,
)
from tests.request_binding_helpers import (
    test_binding_service as _binding_service,
    test_profile as _profile,
    test_request as _request,
    test_vault as _vault,
)


NOW_MS = 1_800_000_000_000


async def _prepare(service=None, request=None):
    selected = service or _binding_service()
    prepared = await selected.prepare(
        execution_id="execution-safe-profile",
        step_id="step-safe-profile",
        intent_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        request=request or _request(protected_fields={"authorization": "synthetic"}),
        created_at_ms=NOW_MS,
        intent_creation_not_after_ms=NOW_MS + 10_000,
        dispatch_material_not_after_ms=NOW_MS + 30_000,
        retention_not_after_ms=NOW_MS + 31 * 24 * 60 * 60 * 1000,
    )
    return selected, prepared.binding


def _with_descriptor(binding, descriptor):
    return binding.model_copy(update={"safe_descriptor": descriptor})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "unknown-field",
        "missing-field",
        "additional-field",
        "wrong-type",
        "wrong-classification",
        "wrong-profile-version",
        "noncanonical-value",
        "unexpected-array-object",
    ],
)
async def test_persisted_safe_fields_and_commitment_slots_are_revalidated(mutation):
    service, binding = await _prepare()
    descriptor = binding.safe_descriptor
    public = list(descriptor.public_fields)
    commitments = list(descriptor.protected_commitments)
    if mutation == "unknown-field":
        public[0] = SafeField(name="unexpected", canonical_value='"capture"')
    elif mutation == "missing-field":
        public.pop()
    elif mutation == "additional-field":
        public.append(SafeField(name="unexpected", canonical_value="null"))
    elif mutation == "wrong-type":
        public[0] = public[0].model_copy(update={"canonical_value": "17"})
    elif mutation == "wrong-classification":
        commitments[0] = commitments[0].model_copy(
            update={"classification": ProtectedFieldClass.PAYMENT}
        )
    elif mutation == "wrong-profile-version":
        descriptor = descriptor.model_copy(update={"endpoint_profile_version": "2"})
    elif mutation == "noncanonical-value":
        public[0] = public[0].model_copy(update={"canonical_value": ' "capture"'})
    elif mutation == "unexpected-array-object":
        public[0] = public[0].model_copy(update={"canonical_value": "[]"})
    descriptor = descriptor.model_copy(
        update={
            "public_fields": tuple(public),
            "protected_commitments": tuple(commitments),
        }
    )
    tampered = _with_descriptor(binding, descriptor)
    with pytest.raises(RequestBindingError):
        service.revalidate_persisted_binding(tampered)


def _nested_profile(*, endpoint_profile_version="1", connector_operation="nested.mutate"):
    return EndpointProfile(
        connector_identity="nested-test-connector",
        connector_operation=connector_operation,
        operation_version="1",
        endpoint_profile_id="nested-endpoint",
        endpoint_profile_version=endpoint_profile_version,
        credential_binding_id="nested-credential",
        credential_binding_version="1",
        wire_codec_version="nested-wire/1",
        public_field_rules={
            "routing": SafeValueRule(
                kind=SafeValueKind.OBJECT,
                object_fields={
                    "mode": SafeValueRule(
                        kind=SafeValueKind.STRING,
                        allowed_strings=frozenset({"direct", "queued"}),
                    ),
                    "hops": SafeValueRule(
                        kind=SafeValueKind.ARRAY,
                        array_item=SafeValueRule(
                            kind=SafeValueKind.INTEGER,
                            minimum_integer=1,
                            maximum_integer=9,
                        ),
                        maximum_items=3,
                    ),
                },
            )
        },
        protected_field_classes={},
        mutation_option_rules={
            "notify": SafeValueRule(kind=SafeValueKind.BOOLEAN),
        },
    )


def _nested_service(profile):
    return RequestBindingService(
        profile=profile,
        commitment_keys=CommitmentKeyring(
            keys={"nested-commitment-key": b"c" * 32},
            active_key_id="nested-commitment-key",
        ),
        vault=_vault(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "replacement",
    [
        '{"hops":[1,2,3,4],"mode":"direct"}',
        '{"hops":[1,{}],"mode":"direct"}',
        '{"hops":{"0":1},"mode":"direct"}',
        '{"extra":null,"hops":[1],"mode":"direct"}',
        '{"hops":[1]}',
    ],
)
async def test_nested_objects_and_arrays_are_recursively_revalidated(replacement):
    profile = _nested_profile()
    service = _nested_service(profile)
    request = ExactMutationRequest(
        target="nested-safe-target",
        public_fields={"routing": {"mode": "direct", "hops": [1, 2]}},
        protected_fields={},
        mutation_options={"notify": False},
    )
    service, binding = await _prepare(service, request)
    descriptor = binding.safe_descriptor
    field = descriptor.public_fields[0].model_copy(
        update={"canonical_value": replacement}
    )
    tampered = _with_descriptor(
        binding,
        descriptor.model_copy(update={"public_fields": (field,)}),
    )
    with pytest.raises(RequestBindingError):
        service.revalidate_persisted_binding(tampered)


@pytest.mark.asyncio
async def test_descriptor_valid_for_one_profile_is_rejected_by_another_version_or_operation():
    service, binding = await _prepare()
    wrong_version = _binding_service()
    wrong_version.profile = _profile(endpoint_profile_version="2")
    with pytest.raises(RequestBindingError):
        wrong_version.revalidate_persisted_binding(binding)

    other_operation = _binding_service("mock.other-operation/mutate")
    with pytest.raises(RequestBindingError):
        other_operation.revalidate_persisted_binding(binding)


@pytest.mark.asyncio
async def test_extra_binding_metadata_is_rejected_at_the_persisted_boundary():
    _, binding = await _prepare()
    values = binding.model_dump(mode="json")
    values["caller_metadata"] = "not-allowed"
    with pytest.raises(ValueError):
        PersistedRequestBinding.model_validate(values)


@pytest.mark.asyncio
async def test_nested_caller_mutation_after_vault_creation_cannot_change_verified_bytes():
    profile = _nested_profile()
    service = _nested_service(profile)
    caller_owned = {"mode": "direct", "hops": [1, 2]}
    request = ExactMutationRequest(
        target="nested-safe-target",
        public_fields={"routing": caller_owned},
        protected_fields={},
        mutation_options={"notify": False},
    )
    service, binding = await _prepare(service, request)
    caller_owned["mode"] = "queued"
    caller_owned["hops"].append(9)
    dispatch = await service.verify(
        binding=binding,
        execution_id=binding.execution_id,
        step_id=binding.step_id,
        intent_id=binding.intent_id,
        correlation_id=binding.correlation_id,
        now_ms=NOW_MS + 1,
        minimum_retention_not_after_ms=NOW_MS,
    )
    assert b'"hops":[1,2]' in dispatch.exact_request_bytes
    assert b'"hops":[1,2,9]' not in dispatch.exact_request_bytes
    assert b'"mode":"direct"' in dispatch.exact_request_bytes
    assert b'"mode":"queued"' not in dispatch.exact_request_bytes
