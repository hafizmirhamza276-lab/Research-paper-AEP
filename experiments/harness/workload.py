"""The workload: N workers x M executions, derived from one seed.

Everything about an execution -- its identifier, its target, the amount it
moves, and whether it was selected to crash -- is a pure function of
``(run_id, seed, worker_index, execution_index)``. Nothing is drawn from a
global generator, so a worker respawned after a SIGKILL recomputes exactly the
plan the dead one was working through, and a run replayed from its recorded
seed reproduces the same executions in the same order.

**Distinct targets.** Each execution mutates its own resource. That is a
modelling decision with a measurement consequence: two executions can then
never share a fingerprint, so every duplicate group the oracle reports is a
*duplicated effect on one intended mutation* rather than two intended
mutations that happened to look alike. The headline metric measures what its
name says.

**No protected material.** The workload sends no credentials, so an identity
descriptor -- what a caller re-sends to describe a past mutation under
``ORACLE_FINGERPRINT`` read-back -- never has to carry one. The request
*binding* still goes through the evaluation vault, so the vault path is
exercised; there is simply nothing secret in the payload.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from aep_core.core.request_binding import (
    EndpointProfile,
    ExactMutationRequest,
    ProtectedFieldClass,
    SafeValueKind,
    SafeValueRule,
)

#: The connector operation the whole harness speaks. Must equal the
#: ``connector_name`` the runner is built with and the profile's operation.
CONNECTOR_OPERATION = "mock.non-idempotent.v1/mutate"

#: The public fields the mock API is configured to fingerprint on. Kept here
#: because the workload and the mock API configuration must agree, and a test
#: asserts the descriptor carries them.
IDENTITY_FIELDS: tuple[str, ...] = ("action", "amount_minor")

#: Smallest and largest amount an execution moves, in integer minor units.
#: Floats are excluded everywhere in this project; money is minor units.
_MIN_AMOUNT = 1
_MAX_AMOUNT = 999_999

STEP_ID = "charge-card"


def harness_profile() -> EndpointProfile:
    """The endpoint profile every harness worker binds requests against."""
    return EndpointProfile(
        connector_identity="mock-connector",
        connector_operation=CONNECTOR_OPERATION,
        operation_version="1",
        endpoint_profile_id="mock-endpoint",
        endpoint_profile_version="1",
        credential_binding_id="mock-credential",
        credential_binding_version="1",
        wire_codec_version="mock-wire/1",
        public_field_rules={
            "action": SafeValueRule(
                kind=SafeValueKind.STRING,
                allowed_strings=frozenset({"capture", "void"}),
            ),
            "amount_minor": SafeValueRule(
                kind=SafeValueKind.INTEGER,
                minimum_integer=0,
                maximum_integer=1_000_000,
            ),
        },
        protected_field_classes={
            "authorization": ProtectedFieldClass.SECRET_AUTH,
        },
        mutation_option_rules={
            "notify": SafeValueRule(kind=SafeValueKind.BOOLEAN),
        },
    )


@dataclass(frozen=True)
class WorkloadItem:
    """One agent execution: one non-idempotent call, one intended effect."""

    worker_index: int
    execution_index: int
    execution_id: str
    step_id: str
    target: str
    action: str
    amount_minor: int
    crash_selected: bool

    def echo(self) -> dict[str, Any]:
        return {
            "worker_index": self.worker_index,
            "execution_index": self.execution_index,
            "execution_id": self.execution_id,
            "step_id": self.step_id,
            "target": self.target,
            "action": self.action,
            "amount_minor": self.amount_minor,
            "crash_selected": self.crash_selected,
        }


def _stream(run_id: str, seed: int, *parts: Any) -> bytes:
    """One independent 32-byte pseudorandom stream per named purpose.

    Named streams rather than one sequential generator: adding a knob that
    consumes randomness must not shift the identifiers of a run collected
    before it existed.
    """
    material = "|".join([run_id, str(seed), *(str(part) for part in parts)])
    return hashlib.sha256(material.encode("utf-8")).digest()


def _execution_id(run_id: str, seed: int, worker: int, index: int) -> str:
    digest = _stream(run_id, seed, "execution-id", worker, index)
    # version=4 fixes the version and variant bits, so the result is a
    # canonical v4 string and passes aep_core.core.validation.
    return str(uuid.UUID(bytes=digest[:16], version=4))


def _amount(run_id: str, seed: int, worker: int, index: int) -> int:
    digest = _stream(run_id, seed, "amount", worker, index)
    span = _MAX_AMOUNT - _MIN_AMOUNT + 1
    return _MIN_AMOUNT + int.from_bytes(digest[:8], "big") % span


def _crash_selected(
    run_id: str, seed: int, worker: int, index: int, probability: float
) -> bool:
    if probability <= 0.0:
        return False
    if probability >= 1.0:
        return True
    digest = _stream(run_id, seed, "crash-selection", worker, index)
    draw = int.from_bytes(digest[:8], "big") / float(1 << 64)
    return draw < probability


def plan_workload(config) -> tuple[WorkloadItem, ...]:
    """Every execution the run will attempt, in worker-then-index order."""
    items: list[WorkloadItem] = []
    for worker in range(config.workers):
        for index in range(config.executions_per_worker):
            execution_id = _execution_id(config.run_id, config.seed, worker, index)
            items.append(
                WorkloadItem(
                    worker_index=worker,
                    execution_index=index,
                    execution_id=execution_id,
                    step_id=STEP_ID,
                    # Derived from the execution id, so the target is unique
                    # and reconstructible from the id alone.
                    target=f"account-{execution_id}",
                    action="capture",
                    amount_minor=_amount(config.run_id, config.seed, worker, index),
                    crash_selected=_crash_selected(
                        config.run_id,
                        config.seed,
                        worker,
                        index,
                        config.crash_probability,
                    ),
                )
            )
    return tuple(items)


def worker_items(
    items: Sequence[WorkloadItem], worker_index: int
) -> tuple[WorkloadItem, ...]:
    return tuple(item for item in items if item.worker_index == worker_index)


def request_for(item: WorkloadItem) -> ExactMutationRequest:
    """The exact request one execution dispatches."""
    return ExactMutationRequest(
        target=item.target,
        public_fields={"action": item.action, "amount_minor": item.amount_minor},
        protected_fields={},
        mutation_options={"notify": False},
    )


def identity_descriptor(item: WorkloadItem) -> dict[str, Any]:
    """What a caller sends to describe a past mutation it wants read back.

    Exactly the keys the oracle's Definition 1 reads, and no more: a read-back
    must not require re-transmitting anything the mutation carried beyond its
    identity.
    """
    return {
        "connector_operation": CONNECTOR_OPERATION,
        "operation_version": "1",
        "target": item.target,
        "public_fields": [
            {"name": "action", "value": item.action},
            {"name": "amount_minor", "value": item.amount_minor},
        ],
    }


def index_by_execution_id(
    items: Iterable[WorkloadItem],
) -> Mapping[str, WorkloadItem]:
    return {item.execution_id: item for item in items}
