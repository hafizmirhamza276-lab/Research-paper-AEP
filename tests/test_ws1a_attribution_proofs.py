r"""WS-1a's four proofs (`docs/33-agent-workload.md` §2.8).

The repair changes how an applied effect is attributed to an execution: by the
harness-supplied `execution_id` where the ledger carries it, by `target`
otherwise. Four things must hold, and each is stated as something to *falsify*
because the proof that was nearly shipped would have passed without exercising
the code it existed to validate (§2.3).

* **Proof 1** — frozen numbers do not move, **and the check is non-vacuous**. On
  every database collected before WS-1a the column is absent, so byte-identity
  there only shows the fallback is intact. It is therefore paired with a fixture
  where the two attributions genuinely *disagree*, proving the new path is
  reached and does something.
* **Proof 2** — `config_digest` is unaffected: the execution id travels on the
  wire and into the ledger, never through `RunConfig`.
* **Proof 3** — the schema bump does not reach the analysis.
* **Proof 4** — the execution id is inert: not in `F(r)`, no accessor keyed on
  it, and not an input to the provider's duplicate detection.
"""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

import pytest

from experiments.analyze import (
    EXECUTION_ID_COLUMN,
    applied_effects_for,
    oracle_effects_by_execution,
    oracle_effects_by_target,
)
from experiments.mock_api.ledger import GroundTruthLedger

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_ledger(path: Path, rows: list[tuple[str, str | None]], *, column: bool) -> Path:
    """A ledger of ``(target, execution_id)`` rows, with or without the column."""
    connection = sqlite3.connect(path)
    extra = ", execution_id TEXT" if column else ""
    connection.execute(
        "CREATE TABLE applied_mutations ("
        f"id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT NOT NULL{extra})"
    )
    for target, execution_id in rows:
        if column:
            connection.execute(
                "INSERT INTO applied_mutations (target, execution_id) VALUES (?, ?)",
                (target, execution_id),
            )
        else:
            connection.execute(
                "INSERT INTO applied_mutations (target) VALUES (?)", (target,)
            )
    connection.commit()
    connection.close()
    return path


# ===========================================================================
# Proof 1 -- frozen numbers do not move, and the check is not vacuous
# ===========================================================================


def test_proof_1_old_data_is_attributed_exactly_as_before(tmp_path):
    """A pre-WS-1a ledger: one execution per target, no column."""
    path = build_ledger(
        tmp_path / "frozen.sqlite3",
        [("account-a", None), ("account-a", None), ("account-b", None)],
        column=False,
    )

    by_target = oracle_effects_by_target(path)
    by_execution = oracle_effects_by_execution(path)

    assert by_execution is None, "no column means attribution must stay on target"
    assert applied_effects_for("exec-a", "account-a", by_execution, by_target) == 2
    assert applied_effects_for("exec-b", "account-b", by_execution, by_target) == 1


def test_proof_1_is_non_vacuous_the_two_attributions_disagree(tmp_path):
    """**The paired fixture.** Two executions share one target.

    This is the shape an agent workload produces and frozen data never does.
    Old attribution counts both rows against whichever execution asks, because
    it can only see the target. New attribution splits them correctly.

    If this test ever passes while asserting agreement, the byte-identity check
    above has stopped proving anything -- that is the §2.3 trap.
    """
    path = build_ledger(
        tmp_path / "agent.sqlite3",
        [("account-shared", "exec-a"), ("account-shared", "exec-b")],
        column=True,
    )

    by_target = oracle_effects_by_target(path)
    by_execution = oracle_effects_by_execution(path)
    assert by_execution is not None, "the column is present; the new path must engage"

    old_for_a = by_target["account-shared"]
    new_for_a = applied_effects_for("exec-a", "account-shared", by_execution, by_target)

    assert old_for_a == 2, "target attribution sees both rows"
    assert new_for_a == 1, "execution attribution sees only its own"
    assert old_for_a != new_for_a, (
        "the two attributions must genuinely disagree here, or Proof 1's "
        "byte-identity on frozen data proves nothing"
    )


def test_proof_1_the_disagreement_is_what_breaks_the_duplicate_metric(tmp_path):
    """Under old attribution both executions look like undetected duplicates."""
    path = build_ledger(
        tmp_path / "agent2.sqlite3",
        [("account-shared", "exec-a"), ("account-shared", "exec-b")],
        column=True,
    )
    by_target = oracle_effects_by_target(path)
    by_execution = oracle_effects_by_execution(path)

    # is_undetected_duplicate is `applied_effects > 1`.
    old = [by_target["account-shared"] > 1 for _ in ("exec-a", "exec-b")]
    new = [
        applied_effects_for(e, "account-shared", by_execution, by_target) > 1
        for e in ("exec-a", "exec-b")
    ]

    assert old == [True, True], "the metric would report two duplicates that are not"
    assert new == [False, False], "each execution applied exactly one effect"


# ===========================================================================
# Proof 2 -- config_digest is unaffected
# ===========================================================================


def test_proof_2_execution_id_is_not_a_run_config_field():
    """It travels on the wire and into the ledger, never through RunConfig.

    `docs/31-transmission-event.md` §4: `RunConfig._body()` iterates every field
    into `config_digest`, so a new field would change the digest of every run
    ever collected.
    """
    from experiments.harness.config import RunConfig

    fields = set(RunConfig.__dataclass_fields__)

    # Fields whose names merely contain "execution" are fine and pre-existing
    # (executions_per_worker, poisoned_executions, redis_kill_executions). The
    # claim is narrower: no field carries the per-execution identifier.
    assert "execution_id" not in fields


def test_proof_2_the_digest_body_does_not_mention_it():
    from experiments.harness import config as config_module

    source = inspect.getsource(config_module)
    body = source[source.find("def _body"):]

    assert "execution_id" not in body.split("def ")[1]


# ===========================================================================
# Proof 3 -- the schema bump does not reach the analysis
# ===========================================================================


def test_proof_3_the_analysis_never_reads_a_schema_version():
    source = (REPO_ROOT / "experiments" / "analyze.py").read_text(encoding="utf-8")

    assert "ledger_meta" not in source
    assert "schema_version" not in source
    # The constant is named once, in prose explaining that it is NOT consulted.
    # What matters is that the module which owns it is never imported.
    assert "mock_api.ledger" not in source
    assert "from experiments.mock_api" not in source


def test_proof_3_a_frozen_ledger_is_read_without_naming_the_new_column(tmp_path):
    """The column is never selected from a database that does not have it."""
    path = build_ledger(
        tmp_path / "frozen.sqlite3", [("account-a", None)], column=False
    )
    statements: list[str] = []
    real_connect = sqlite3.connect

    def recording_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        # Connection.execute is read-only; the trace callback is the supported
        # way to observe every statement a connection actually issues.
        connection.set_trace_callback(
            lambda sql: statements.append(" ".join(str(sql).split()))
        )
        return connection

    sqlite3.connect = recording_connect  # type: ignore[assignment]
    try:
        oracle_effects_by_target(path)
        assert oracle_effects_by_execution(path) is None
    finally:
        sqlite3.connect = real_connect  # type: ignore[assignment]

    selects = [s for s in statements if s.upper().startswith("SELECT")]
    assert selects == ["SELECT target, COUNT(*) FROM applied_mutations GROUP BY target"]
    assert any(s.upper().startswith("PRAGMA TABLE_INFO") for s in statements)
    assert not any(EXECUTION_ID_COLUMN in s for s in selects)


# ===========================================================================
# Proof 4 -- the execution id is inert
# ===========================================================================


def test_proof_4_no_ledger_accessor_is_keyed_on_the_execution_id():
    """`client_reference` is a capability *because* it has an accessor.

    `applications_for_client_reference` exists and serves read-backs. The
    execution id gets no equivalent, and its absence is the thing that keeps it
    instrumentation rather than a capability (`docs/33` §2.6).
    """
    accessors = [name for name in dir(GroundTruthLedger) if name.startswith("applications_for")]

    assert "applications_for_client_reference" in accessors
    assert not any("execution" in name for name in accessors)


def test_proof_4_it_is_not_an_identity_field_of_the_fingerprint():
    """`F(r)` must not depend on it, or no two mutations ever match."""
    from experiments.mock_api import fingerprint as fingerprint_module

    source = inspect.getsource(fingerprint_module)

    assert "execution_id" not in source


def test_proof_4_it_is_not_an_input_to_duplicate_detection(tmp_path):
    """Two applications of one mutation under different execution ids are one
    duplicate group, exactly as they are under different client references."""
    ledger = GroundTruthLedger(tmp_path / "oracle.sqlite3")
    ledger.initialise()
    try:
        common = dict(
            endpoint="payments",
            target="account-1",
            fingerprint="f" * 64,
            payload_digest="d" * 64,
            client_reference="ref-1",
            response_class="AUTHORITATIVE_READBACK",
            applied_at_ms=1,
        )
        ledger.record_applied_mutation(
            call_id="call-1", execution_id="exec-a", delivery_index=1, **common
        )
        ledger.record_applied_mutation(
            call_id="call-2", execution_id="exec-b", delivery_index=2, **common
        )

        (group,) = ledger.duplicate_groups()

        assert group.applications == 2, (
            "the oracle must decide identity without trusting caller-supplied "
            "or harness-supplied fields"
        )
    finally:
        ledger.close()
