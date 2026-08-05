"""The ground-truth ledger: the paper's oracle, tested as such.

The ledger is not instrumentation. Every duplicate the evaluation reports is a
row in this database, so a defect here is indistinguishable from a result. It
therefore gets the same treatment as the protocol: an explicit atomicity
claim, an explicit durability claim, and a query whose classification is
pinned by test rather than inferred from a count.
"""

from __future__ import annotations

import sqlite3

import pytest

from experiments.mock_api.ledger import (
    DuplicateClass,
    GroundTruthLedger,
    LedgerError,
)

ENDPOINT = "payments"
FINGERPRINT_A = "a" * 64
FINGERPRINT_B = "b" * 64
PAYLOAD_1 = "1" * 64
PAYLOAD_2 = "2" * 64


@pytest.fixture
def ledger(tmp_path):
    instance = GroundTruthLedger(tmp_path / "ground_truth.sqlite3")
    instance.initialise()
    try:
        yield instance
    finally:
        instance.close()


def apply_mutation(
    ledger: GroundTruthLedger,
    *,
    call_id: str,
    fingerprint: str = FINGERPRINT_A,
    payload: str = PAYLOAD_1,
    target: str = "account-redacted-17",
    endpoint: str = ENDPOINT,
    delivery_index: int = 1,
    client_reference: str | None = "client-ref-1",
    **kwargs,
):
    return ledger.record_applied_mutation(
        call_id=call_id,
        endpoint=endpoint,
        target=target,
        fingerprint=fingerprint,
        payload_digest=payload,
        client_reference=client_reference,
        response_class="AUTHORITATIVE_READBACK",
        delivery_index=delivery_index,
        applied_at_ms=1_800_000_000_000,
        **kwargs,
    )


# ===========================================================================
# Durability of the ledger itself
# ===========================================================================


def test_the_database_is_in_wal_mode(ledger):
    """WAL survives a process kill without a rollback journal to replay."""
    assert ledger.journal_mode() == "wal"


def test_writes_are_fully_synchronous(ledger):
    """synchronous=FULL makes the durability claim unconditional.

    NORMAL would be enough for the crash model actually injected (SIGKILL of
    the service process leaves committed data with the OS). FULL also covers
    host loss, which costs one fsync per applied mutation and removes a
    caveat from the paper.
    """
    assert ledger.synchronous() == "FULL"


def test_the_schema_version_is_recorded(ledger):
    assert ledger.schema_version().startswith("aep.mock-legacy-api.ledger/")


def test_reopening_sees_previously_applied_mutations(tmp_path):
    path = tmp_path / "ground_truth.sqlite3"
    first = GroundTruthLedger(path)
    first.initialise()
    apply_mutation(first, call_id="call-1")
    first.close()

    second = GroundTruthLedger(path)
    second.initialise()
    try:
        assert [row.call_id for row in second.applied_mutations()] == ["call-1"]
    finally:
        second.close()


def test_initialise_is_idempotent(ledger):
    apply_mutation(ledger, call_id="call-1")
    ledger.initialise()

    assert len(ledger.applied_mutations()) == 1


# ===========================================================================
# Atomicity: the ledger row and the state change are one transaction
# ===========================================================================


def test_an_applied_mutation_changes_state_and_ledger_together(ledger):
    apply_mutation(ledger, call_id="call-1")

    (row,) = ledger.applied_mutations()
    (state,) = ledger.simulated_state()
    assert row.fingerprint == FINGERPRINT_A
    assert row.call_id == "call-1"
    assert state.effect_count == 1
    assert state.last_call_id == "call-1"


def test_a_failed_ledger_insert_rolls_back_the_state_change(ledger):
    """The UNIQUE constraint on call_id is a stand-in for any write failure.

    If the state increment and the ledger row were separate transactions,
    the simulated state would advance while the oracle stayed silent -- an
    applied effect with no ground truth, which is the one outcome that would
    invalidate every duplicate count in the paper.
    """
    apply_mutation(ledger, call_id="call-1")

    with pytest.raises(sqlite3.IntegrityError):
        apply_mutation(ledger, call_id="call-1")

    (state,) = ledger.simulated_state()
    assert state.effect_count == 1
    assert len(ledger.applied_mutations()) == 1


def test_a_crash_before_commit_persists_neither_side(ledger):
    """The in-process half of the SIGKILL test in test_service_crash_safety."""

    class Killed(BaseException):
        pass

    def die() -> None:
        raise Killed()

    with pytest.raises(Killed):
        apply_mutation(ledger, call_id="call-1", before_commit=die)

    assert ledger.applied_mutations() == ()
    assert ledger.simulated_state() == ()
    assert ledger.consistency_report().is_consistent


def test_a_crash_after_commit_persists_both_sides(ledger):
    """The ambiguous case the protocol exists for: applied, never acknowledged."""

    class Killed(BaseException):
        pass

    def die() -> None:
        raise Killed()

    with pytest.raises(Killed):
        apply_mutation(ledger, call_id="call-1", after_commit=die)

    assert len(ledger.applied_mutations()) == 1
    assert ledger.simulated_state()[0].effect_count == 1
    assert ledger.consistency_report().is_consistent


def test_repeated_applications_accumulate_on_one_resource(ledger):
    apply_mutation(ledger, call_id="call-1")
    apply_mutation(ledger, call_id="call-2", delivery_index=2)

    (state,) = ledger.simulated_state()
    assert state.effect_count == 2
    assert state.last_call_id == "call-2"


def test_distinct_targets_are_distinct_resources(ledger):
    apply_mutation(ledger, call_id="call-1", target="account-redacted-17")
    apply_mutation(ledger, call_id="call-2", target="account-redacted-18")

    assert sorted(row.effect_count for row in ledger.simulated_state()) == [1, 1]
    assert len(ledger.simulated_state()) == 2


# ===========================================================================
# The consistency invariant the crash test asserts on recovery
# ===========================================================================


def test_consistency_holds_over_many_applications(ledger):
    for index in range(1, 26):
        apply_mutation(
            ledger,
            call_id=f"call-{index}",
            target=f"account-redacted-{index % 4}",
            fingerprint=FINGERPRINT_A if index % 2 else FINGERPRINT_B,
        )

    report = ledger.consistency_report()
    assert report.is_consistent
    assert report.applied_rows == 25
    assert report.total_effect_count == 25
    assert report.disagreeing_resources == ()


def test_consistency_detects_a_state_row_the_ledger_cannot_explain(ledger):
    """Proves the invariant can fail, so passing it elsewhere means something."""
    apply_mutation(ledger, call_id="call-1")
    ledger._require_connection().execute(  # noqa: SLF001 -- deliberate corruption
        "UPDATE simulated_state SET effect_count = effect_count + 1"
    )
    ledger._require_connection().commit()  # noqa: SLF001

    report = ledger.consistency_report()
    assert not report.is_consistent
    assert len(report.disagreeing_resources) == 1


# ===========================================================================
# Duplicate detection (Definition 3)
# ===========================================================================


def test_two_identical_applications_are_an_exact_duplicate(ledger):
    apply_mutation(ledger, call_id="call-1")
    apply_mutation(ledger, call_id="call-2", delivery_index=2)

    (group,) = ledger.duplicate_groups()
    assert group.fingerprint == FINGERPRINT_A
    assert group.duplicate_class is DuplicateClass.EXACT_DUPLICATE
    assert group.applications == 2
    assert group.duplicate_applications == 1
    assert group.distinct_payloads == 1
    assert sorted(group.call_ids) == ["call-1", "call-2"]


def test_the_same_mutation_with_different_bytes_is_a_conflict(ledger):
    """Same fingerprint, different payload digest: a caller that thinks it is
    retrying but is not sending the same request."""
    apply_mutation(ledger, call_id="call-1", payload=PAYLOAD_1)
    apply_mutation(ledger, call_id="call-2", payload=PAYLOAD_2, delivery_index=2)

    (group,) = ledger.duplicate_groups()
    assert group.duplicate_class is DuplicateClass.FINGERPRINT_CONFLICT
    assert group.applications == 2
    assert group.distinct_payloads == 2


def test_a_near_miss_is_not_reported_as_a_duplicate(ledger):
    """Different mutations, however similar, are not duplicates."""
    apply_mutation(ledger, call_id="call-1", fingerprint=FINGERPRINT_A)
    apply_mutation(ledger, call_id="call-2", fingerprint=FINGERPRINT_B)

    assert ledger.duplicate_groups() == ()


def test_one_application_is_never_a_duplicate(ledger):
    apply_mutation(ledger, call_id="call-1")

    assert ledger.duplicate_groups() == ()


def test_an_empty_ledger_reports_no_duplicates(ledger):
    assert ledger.duplicate_groups() == ()
    assert ledger.consistency_report().is_consistent


def test_duplicates_and_near_misses_are_separated_in_one_query(ledger):
    apply_mutation(ledger, call_id="call-1", fingerprint=FINGERPRINT_A)
    apply_mutation(ledger, call_id="call-2", fingerprint=FINGERPRINT_A, delivery_index=2)
    apply_mutation(ledger, call_id="call-3", fingerprint=FINGERPRINT_B)

    (group,) = ledger.duplicate_groups()
    assert group.fingerprint == FINGERPRINT_A
    assert ledger.duplicate_application_count() == 1


def test_three_applications_count_two_duplicates(ledger):
    """The headline metric counts extra applications, not affected groups."""
    for index in (1, 2, 3):
        apply_mutation(ledger, call_id=f"call-{index}", delivery_index=index)

    (group,) = ledger.duplicate_groups()
    assert group.applications == 3
    assert group.duplicate_applications == 2
    assert ledger.duplicate_application_count() == 2


def test_a_client_reference_is_never_an_input_to_duplicate_detection(ledger):
    """Oracle independence: AEP's own fingerprint must not decide the result.

    Two applications of the same mutation carrying *different* client
    references are still one duplicate -- otherwise a protocol could hide its
    duplicates simply by minting a fresh reference per attempt.
    """
    apply_mutation(ledger, call_id="call-1", client_reference="ref-1")
    apply_mutation(
        ledger, call_id="call-2", client_reference="ref-2", delivery_index=2
    )

    (group,) = ledger.duplicate_groups()
    assert group.duplicate_class is DuplicateClass.EXACT_DUPLICATE
    assert group.applications == 2


# ===========================================================================
# Read-back support and input validation
# ===========================================================================


def test_applications_are_findable_by_client_reference(ledger):
    apply_mutation(ledger, call_id="call-1", client_reference="ref-1")

    assert len(ledger.applications_for_client_reference("ref-1")) == 1
    assert ledger.applications_for_client_reference("ref-2") == ()


def test_applications_are_findable_by_fingerprint(ledger):
    apply_mutation(ledger, call_id="call-1")

    assert len(ledger.applications_for_fingerprint(FINGERPRINT_A)) == 1
    assert ledger.applications_for_fingerprint(FINGERPRINT_B) == ()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fingerprint", "not-a-digest"),
        ("fingerprint", "A" * 64),
        ("payload_digest", ""),
        ("call_id", ""),
    ],
)
def test_malformed_oracle_input_is_refused(ledger, field, value):
    """A row the oracle cannot interpret must never reach the database."""
    arguments = {"call_id": "call-1"}
    if field == "fingerprint":
        arguments["fingerprint"] = value
    elif field == "payload_digest":
        arguments["payload"] = value
    else:
        arguments["call_id"] = value

    with pytest.raises(LedgerError):
        apply_mutation(ledger, **arguments)

    assert ledger.applied_mutations() == ()


def test_a_non_positive_delivery_index_is_refused(ledger):
    with pytest.raises(LedgerError):
        apply_mutation(ledger, call_id="call-1", delivery_index=0)
