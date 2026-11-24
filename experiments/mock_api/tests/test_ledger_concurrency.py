"""The oracle must answer correctly while it is being written to.

Found by the Phase 2B Session 2 self-validation run (amendment C5), which is
exactly what that amendment exists for. The run's reconciliation reported one
execution the protocol had resolved ``FAILED_CONFIRMED`` -- a definitive
no-effect -- for which the ledger held an effect. The protocol was not wrong:
the *oracle* had told it ``NOT_APPLIED`` for a row committed 27.8 seconds
earlier.

``GroundTruthLedger`` shared one ``sqlite3.Connection`` across the service's
worker threads and guarded only the write path. A ``SELECT`` issued from one
thread while another thread was inside ``BEGIN IMMEDIATE ... COMMIT`` on the
*same connection* interleaves with that transaction, and the reproduction below
observed all three of its failure modes: a committed row reported absent, a
single application reported as a ``CONFLICT``, and outright ``sqlite3`` errors.

Every one of those corrupts a number the paper reports -- a missed row inflates
the lost-effect rate, a fabricated conflict inflates the duplicate rate -- and
none of them is a property of the system under test. Reads now use one
connection per thread, which is what WAL is for: concurrent readers take a
consistent snapshot and never observe a writer's open transaction.
"""

from __future__ import annotations

import threading

import pytest

from experiments.mock_api.ledger import GroundTruthLedger

WRITERS = 40
READERS = 3

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


@pytest.fixture
def ledger(tmp_path) -> GroundTruthLedger:
    instance = GroundTruthLedger(tmp_path / "ground_truth.sqlite3")
    instance.initialise()
    try:
        yield instance
    finally:
        instance.close()


def record(ledger: GroundTruthLedger, index: int) -> str:
    reference = f"{index:064d}"
    ledger.record_applied_mutation(
        call_id=f"call-{index}",
        endpoint="payments",
        target=f"account-{index}",
        fingerprint=f"{index:064x}",
        payload_digest=DIGEST_A,
        client_reference=reference,
        response_class="AUTHORITATIVE_READBACK",
        delivery_index=1,
        applied_at_ms=1_700_000_000_000 + index,
    )
    return reference


def test_a_committed_row_is_never_invisible_to_a_concurrent_reader(ledger):
    """The exact failure that produced the C5 run's single disagreement."""
    committed: list[str] = []
    guard = threading.Lock()
    misses: list[tuple[str, int]] = []
    errors: list[BaseException] = []
    stop = threading.Event()

    def write(index: int) -> None:
        try:
            reference = record(ledger, index)
        except BaseException as error:  # noqa: BLE001 -- recorded, then asserted
            errors.append(error)
            return
        with guard:
            committed.append(reference)

    def read() -> None:
        while not stop.is_set():
            with guard:
                snapshot = list(committed)
            for reference in snapshot:
                try:
                    rows = ledger.applications_for_client_reference(reference)
                except BaseException as error:  # noqa: BLE001
                    errors.append(error)
                    continue
                if len(rows) != 1:
                    misses.append((reference, len(rows)))

    readers = [threading.Thread(target=read) for _ in range(READERS)]
    for reader in readers:
        reader.start()
    writers = [threading.Thread(target=write, args=(index,)) for index in range(WRITERS)]
    for writer in writers:
        writer.start()
    for writer in writers:
        writer.join()
    stop.set()
    for reader in readers:
        reader.join()

    assert errors == [], f"the ledger raised under concurrency: {errors[:3]}"
    assert misses == [], (
        "a committed row was reported absent or duplicated while writes were "
        f"in flight: {misses[:5]}"
    )
    assert len(committed) == WRITERS


def test_duplicate_detection_is_not_fabricated_by_a_concurrent_write(ledger):
    """A spurious CONFLICT would inflate the paper's headline duplicate rate."""
    reference = record(ledger, 0)
    observed: list[int] = []
    stop = threading.Event()

    def read() -> None:
        while not stop.is_set():
            observed.append(len(ledger.applications_for_client_reference(reference)))

    reader = threading.Thread(target=read)
    reader.start()
    try:
        for index in range(1, WRITERS):
            record(ledger, index)
    finally:
        stop.set()
        reader.join()

    assert set(observed) == {1}, (
        f"one applied row was observed with counts {sorted(set(observed))}; a "
        "count above 1 is a fabricated duplicate"
    )


def test_the_consistency_report_is_stable_under_concurrent_writes(ledger):
    """The invariant the SIGKILL test asserts must not be racy either."""
    inconsistent: list[tuple[int, int]] = []
    stop = threading.Event()

    def read() -> None:
        while not stop.is_set():
            report = ledger.consistency_report()
            if not report.is_consistent:
                inconsistent.append(
                    (report.applied_rows, report.total_effect_count)
                )

    reader = threading.Thread(target=read)
    reader.start()
    try:
        for index in range(WRITERS):
            record(ledger, index)
    finally:
        stop.set()
        reader.join()

    assert inconsistent == [], (
        "the ledger reported itself inconsistent while a write was in "
        f"flight: {inconsistent[:3]}"
    )


def test_every_thread_gets_the_declared_durability_settings(ledger):
    """``synchronous`` is per connection, so a per-thread pool must set it."""
    observed: dict[str, tuple[str, str]] = {}

    def inspect(name: str) -> None:
        observed[name] = (ledger.journal_mode(), ledger.synchronous())

    threads = [
        threading.Thread(target=inspect, args=(f"thread-{index}",))
        for index in range(4)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert set(observed.values()) == {("wal", "FULL")}, observed


def test_closing_releases_every_thread_connection(tmp_path):
    """Otherwise a run leaks a file handle per worker thread."""
    instance = GroundTruthLedger(tmp_path / "ground_truth.sqlite3")
    instance.initialise()

    def touch() -> None:
        instance.applied_mutations()

    threads = [threading.Thread(target=touch) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert instance.open_connection_count() == 5  # four threads plus this one
    instance.close()
    assert instance.open_connection_count() == 0
