"""Fresh runtime-marker checks for repository safe representations and errors."""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.core.intents import IntentInvariantError, evidence_hash
from src.core.request_binding import (
    ExactMutationRequest,
    RequestBindingError,
    SafeField,
)
from tests.request_binding_helpers import (
    test_binding_service as _binding_service,
    test_request as _request,
)


def _marker() -> str:
    return "synthetic-" + secrets.token_hex(24)


def test_safe_field_repr_and_str_never_render_persisted_canonical_value():
    marker = _marker()
    field = SafeField(name="action", canonical_value=f'"{marker}"')
    assert marker not in repr(field)
    assert marker not in str(field)


def test_model_validation_errors_hide_case_varied_nested_caller_values():
    marker = _marker()
    with pytest.raises((ValidationError, RequestBindingError)) as exc_info:
        SafeField(name="Authorization", canonical_value=f'"{marker}"')
    rendered = str(exc_info.value)
    assert marker not in rendered
    assert "Authorization" not in rendered


@pytest.mark.asyncio
async def test_profile_rejection_exception_and_cause_do_not_expose_runtime_marker():
    marker = _marker()
    service = _binding_service()
    with pytest.raises(RequestBindingError) as exc_info:
        request = ExactMutationRequest(
            target="account-redacted-17",
            public_fields={
                "action": "capture",
                "amount_minor": 1700,
                "routing": {"Authorization": marker},
            },
            protected_fields={},
            mutation_options={"notify": False},
        )
        await service.prepare(
            execution_id="execution-privacy",
            step_id="step-privacy",
            intent_id="11111111-1111-4111-8111-111111111111",
            correlation_id="22222222-2222-4222-8222-222222222222",
            request=request,
            created_at_ms=1_800_000_000_000,
            intent_creation_not_after_ms=1_800_000_010_000,
            dispatch_material_not_after_ms=1_800_000_030_000,
            retention_not_after_ms=1_802_678_400_000,
        )
    assert marker not in str(exc_info.value)
    assert marker not in repr(exc_info.value)
    assert exc_info.value.__cause__ is None


def test_unknown_evidence_is_rejected_without_rendering_runtime_marker():
    marker = _marker()
    with pytest.raises(IntentInvariantError) as exc_info:
        evidence_hash({"provider_payload": marker})
    assert marker not in str(exc_info.value)
    assert marker not in repr(exc_info.value)
    assert exc_info.value.__cause__ is None


def test_request_repr_never_renders_nested_or_case_varied_runtime_markers():
    marker = _marker()
    request = _request(
        protected_fields={
            "authorization": marker,
            "cookie": marker[::-1],
        }
    )
    assert marker not in repr(request)
    assert marker[::-1] not in repr(request)


def test_runtime_marker_absent_from_reports_cache_and_captured_test_output(capsys):
    marker = _marker()
    root = Path(__file__).resolve().parents[1]
    scanned = [root / "phase2_implementation_report.md"]
    scanned.extend(sorted((root / "docs").glob("*.md")))
    cache = root / ".pytest_cache"
    if cache.exists():
        scanned.extend(path for path in cache.rglob("*") if path.is_file())
    occurrences = 0
    for path in scanned:
        occurrences += path.read_bytes().count(marker.encode("utf-8"))
    captured = capsys.readouterr()
    assert marker not in captured.out
    assert marker not in captured.err
    assert occurrences == 0
