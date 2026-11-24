"""Redis fixtures for the harness tests.

The guarded ``redis_client`` / ``storage_adapter`` / ``lock_manager`` fixtures
live in ``tests/conftest.py``, together with the test-instance-marker guard
that stops a mis-pointed ``REDIS_URL`` from deleting production keys. They are
re-exported rather than reimplemented: a second copy of that guard is a second
place for it to be weakened.
"""

from __future__ import annotations

from tests.conftest import (  # noqa: F401 -- re-exported as fixtures
    cjson_available,
    lock_manager,
    redis_client,
    storage_adapter,
)
