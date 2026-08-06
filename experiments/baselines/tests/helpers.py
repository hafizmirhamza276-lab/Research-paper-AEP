"""Shared workload fixtures for the baseline tests.

The baselines are compared on *one* workload, so their tests use the workload
driver rather than an invented request: a baseline tested against a different
mutation from the one the matrix sends would be a baseline whose unit tests
prove nothing about the numbers it produces.
"""

from __future__ import annotations

import uuid

from experiments.harness.workload import STEP_ID, WorkloadItem

#: A fixed identifier for tests about *absence* -- "classify finds no record"
#: -- where no execution has been run.
EXECUTION_ID = "3f1c2f8a-6f5f-4d2f-8f3a-6c1d0e9b7a45"


def item_for(
    *,
    execution_id: str | None = None,
    amount_minor: int = 4_242,
    action: str = "capture",
    worker_index: int = 0,
    execution_index: int = 0,
    crash_selected: bool = False,
) -> WorkloadItem:
    """One workload item, with the same shape ``plan_workload`` produces."""
    execution_id = execution_id or str(uuid.uuid4())
    return WorkloadItem(
        worker_index=worker_index,
        execution_index=execution_index,
        execution_id=execution_id,
        step_id=STEP_ID,
        target=f"account-{execution_id}",
        action=action,
        amount_minor=amount_minor,
        crash_selected=crash_selected,
    )
