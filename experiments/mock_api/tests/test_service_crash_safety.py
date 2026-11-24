"""SIGKILL the mock API mid-mutation; the oracle must still be believable.

Amendment B2(iii). The ground-truth ledger is the paper's oracle, so its own
crash behaviour is a result, not an implementation detail. If a killed service
could leave a simulated effect with no ledger row -- or a ledger row with no
effect -- then every duplicate count derived from it would be a count of an
unknown quantity.

Two kills, one on each side of the commit boundary:

* **before commit** -- neither the effect nor its record survives; the
  external world never changed.
* **after commit** -- both survive, and the caller received nothing. This is
  the case the whole protocol exists for: an effect that happened, with no
  evidence at the caller.

In both, recovery means nothing more than reopening the database, because WAL
plus ``synchronous=FULL`` leaves nothing to replay by hand.
"""

from __future__ import annotations

import threading
from pathlib import Path

import httpx
import pytest

from aep_core.core.connector_contract import ReconciliationCapability
from experiments.mock_api.ledger import GroundTruthLedger
from experiments.mock_api.tests.server_harness import (
    HAS_SIGKILL,
    MockApiProcess,
    wait_for_marker,
    write_config,
)

#: Far longer than the test needs; the point is that the process is definitely
#: still inside the hold when the kill lands.
HOLD_SECONDS = 60.0


def envelope(*, amount_minor: int = 1700) -> dict:
    return {
        "envelope_schema": "aep.mutation-request/1",
        "canonicalization_version": "aep.canonical-json/1",
        "descriptor_version": "aep.safe-request/1",
        "connector_identity": "mock-connector",
        "connector_operation": "mock.non-idempotent.v1/mutate",
        "operation_version": "1",
        "endpoint_profile_id": "mock-endpoint",
        "endpoint_profile_version": "1",
        "credential_binding_id": "mock-credential",
        "credential_binding_version": "1",
        "wire_codec_version": "mock-wire/1",
        "target": "account-redacted-17",
        "public_fields": [
            {"name": "action", "value": "capture"},
            {"name": "amount_minor", "value": amount_minor},
        ],
        "protected_fields": [],
        "mutation_options": [],
    }


def crash_config(tmp_path: Path, *, marker: Path, **crash) -> dict:
    return {
        "config_version": "aep.mock-legacy-api.config/1",
        "seed": 20260805,
        "ledger_path": str(tmp_path / "ground_truth.sqlite3"),
        "endpoints": {
            "payments": {
                "response_class": (
                    ReconciliationCapability.AUTHORITATIVE_READBACK.value
                ),
                "identity_fields": ["action", "amount_minor"],
                "crash_simulation": {
                    "progress_marker_path": str(marker),
                    **crash,
                },
            }
        },
    }


def reopen(tmp_path: Path) -> GroundTruthLedger:
    """Recovery, in full: open the database the killed process left behind."""
    ledger = GroundTruthLedger(tmp_path / "ground_truth.sqlite3")
    ledger.initialise()
    return ledger


def post_in_background(base_url: str) -> threading.Thread:
    """Fire the mutation that will be interrupted; ignore its fate."""

    def call() -> None:
        try:
            httpx.post(
                f"{base_url}/v1/endpoints/payments/mutations",
                json=envelope(),
                timeout=HOLD_SECONDS,
            )
        except Exception:
            # The server is about to be killed under this request. That the
            # call fails is the premise, not a finding.
            pass

    thread = threading.Thread(target=call, daemon=True)
    thread.start()
    return thread


@pytest.fixture
def marker(tmp_path) -> Path:
    return tmp_path / "in-transaction.marker"


def test_the_platform_supports_an_uncatchable_kill():
    """Names the mechanism, so a report can say which one produced the run.

    ``HAS_SIGKILL`` is True on the ubuntu-24.04 runner that gates the
    artifact; on Windows the test still runs, via TerminateProcess, which is
    equally uncatchable.
    """
    assert HAS_SIGKILL or __import__("sys").platform == "win32"


def test_a_kill_before_commit_leaves_no_effect_and_no_record(tmp_path, marker):
    config = write_config(
        tmp_path / "mock-api.yaml",
        crash_config(tmp_path, marker=marker, hold_in_transaction_seconds=HOLD_SECONDS),
    )
    server = MockApiProcess(config, log_directory=tmp_path)
    try:
        server.start()
        post_in_background(server.base_url)
        assert wait_for_marker(marker), (
            f"service never entered the transaction\n{server.logs()}"
        )
        server.sigkill()
        assert not server.is_running()
    finally:
        server.close()

    ledger = reopen(tmp_path)
    try:
        report = ledger.consistency_report()
        assert ledger.applied_mutations() == ()
        assert ledger.simulated_state() == ()
        assert report.is_consistent
        assert report.applied_rows == 0
        assert report.total_effect_count == 0
    finally:
        ledger.close()


def test_a_kill_after_commit_keeps_both_and_tells_the_caller_nothing(
    tmp_path, marker
):
    config = write_config(
        tmp_path / "mock-api.yaml",
        crash_config(tmp_path, marker=marker, hold_after_commit_seconds=HOLD_SECONDS),
    )
    server = MockApiProcess(config, log_directory=tmp_path)
    try:
        server.start()
        thread = post_in_background(server.base_url)
        assert wait_for_marker(marker), (
            f"service never reached the post-commit hold\n{server.logs()}"
        )
        # Only the armed hold writes the marker, so its content proves the
        # commit has already happened rather than being about to.
        assert marker.read_text(encoding="utf-8") == "after-commit"
        server.sigkill()
        assert not server.is_running()
        thread.join(timeout=30)
    finally:
        server.close()

    ledger = reopen(tmp_path)
    try:
        (row,) = ledger.applied_mutations()
        (state,) = ledger.simulated_state()
        report = ledger.consistency_report()

        assert row.target == "account-redacted-17"
        assert row.delivery_index == 1
        assert state.effect_count == 1
        assert state.last_call_id == row.call_id
        assert report.is_consistent
        assert report.applied_rows == 1
        assert report.total_effect_count == 1
    finally:
        ledger.close()


def test_the_ledger_survives_a_kill_with_earlier_mutations_intact(tmp_path, marker):
    """A kill must not cost the mutations that committed before it."""
    config = write_config(
        tmp_path / "mock-api.yaml",
        crash_config(tmp_path, marker=marker, hold_in_transaction_seconds=HOLD_SECONDS),
    )
    # The hold is armed for every mutation on this endpoint, so the two
    # settled calls are made against a server whose crash simulation is
    # disarmed, and only the third run arms it.
    settled_config = write_config(
        tmp_path / "mock-api-settled.yaml",
        crash_config(tmp_path, marker=tmp_path / "unused.marker"),
    )
    with MockApiProcess(settled_config, log_directory=tmp_path) as server:
        for amount in (1700, 1800):
            response = httpx.post(
                f"{server.base_url}/v1/endpoints/payments/mutations",
                json=envelope(amount_minor=amount),
                timeout=10,
            )
            assert response.status_code == 200

    server = MockApiProcess(config, log_directory=tmp_path)
    try:
        server.start()
        post_in_background(server.base_url)
        assert wait_for_marker(marker), server.logs()
        server.sigkill()
    finally:
        server.close()

    ledger = reopen(tmp_path)
    try:
        assert len(ledger.applied_mutations()) == 2
        assert ledger.consistency_report().is_consistent
        assert ledger.duplicate_groups() == ()
    finally:
        ledger.close()


def test_a_real_client_times_out_when_the_response_is_withheld(tmp_path):
    """The client half of the timeout fault, over a real socket.

    ``TestClient`` runs the app in-process and cannot honour a client-side
    timeout, so the in-process test in test_service.py asserts only that the
    server withholds the response. This asserts what the caller actually
    experiences, which is the input to the protocol's ambiguity handling.
    """
    document = {
        "config_version": "aep.mock-legacy-api.config/1",
        "seed": 20260805,
        "ledger_path": str(tmp_path / "ground_truth.sqlite3"),
        "endpoints": {
            "payments": {
                "response_class": (
                    ReconciliationCapability.AUTHORITATIVE_READBACK.value
                ),
                "identity_fields": ["action", "amount_minor"],
                "faults": {"timeout_probability": 1.0},
            }
        },
    }
    config = write_config(tmp_path / "mock-api.yaml", document)

    with MockApiProcess(config, log_directory=tmp_path) as server:
        with pytest.raises(httpx.ReadTimeout):
            httpx.post(
                f"{server.base_url}/v1/endpoints/payments/mutations",
                json=envelope(),
                timeout=1.0,
            )

    ledger = reopen(tmp_path)
    try:
        # Applied. The caller has no evidence either way.
        assert len(ledger.applied_mutations()) == 1
        assert ledger.consistency_report().is_consistent
    finally:
        ledger.close()
