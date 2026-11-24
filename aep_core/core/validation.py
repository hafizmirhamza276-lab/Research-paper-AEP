"""Shared validation helpers for AEP public boundaries."""

import uuid


def validate_execution_id(execution_id: str) -> str:
    """Return a lowercase hyphenated UUIDv4 string or raise ValueError."""
    if not isinstance(execution_id, str):
        raise ValueError("execution_id must be a canonical UUIDv4 string")
    try:
        parsed = uuid.UUID(execution_id)
    except (ValueError, AttributeError, TypeError):
        raise ValueError(
            "execution_id must be a canonical UUIDv4 string"
        ) from None
    if parsed.version != 4 or str(parsed) != execution_id:
        raise ValueError("execution_id must be a canonical UUIDv4 string")
    return execution_id
