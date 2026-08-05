"""Redis fixtures for the harness tests.

Re-exported from ``tests/conftest.py`` rather than reimplemented, for the same
reason ``experiments/mock_api/tests/conftest.py`` does it: the
test-instance-marker guard that stops a mis-pointed ``REDIS_URL`` from deleting
production keys must have exactly one definition. Session 1's report closed
with a caution about precisely this, because the harness kills processes that
hold Redis leases.
"""

from __future__ import annotations

from tests.conftest import (  # noqa: F401 -- re-exported as fixtures
    cjson_available,
    lock_manager,
    redis_client,
    storage_adapter,
)
