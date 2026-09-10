"""Exercise ``scripts/check_tla_transitions.py`` on the branches where it fails.

``docs/26`` §3 rule 13: *"Before a check is treated as evidence, exercise the
branch on which it fails and confirm it does. A check only ever run against
data that satisfies it establishes nothing, and reads exactly like one that
works."*

The gate this file tests is the only thing standing between ``formal/AEP.tla``
and silent drift from the implementation, and it has an unusually bad failure
mode: a model checker asked about the wrong state machine does not complain, it
reports success.  So every rejection path is exercised against a deliberately
mutated copy of the specification, and the passing path is exercised against
the real one.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_tla_transitions.py"
SPEC = ROOT / "formal" / "AEP.tla"


def load_gate():
    """Import the gate as a module so its internals can be pointed elsewhere."""
    spec = importlib.util.spec_from_file_location("check_tla_transitions", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_tla_transitions"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def gate():
    return load_gate()


@pytest.fixture
def mutated(tmp_path, gate, monkeypatch):
    """Point the gate at an edited copy of the real specification."""

    def _mutate(old: str, new: str, *, count: int = 1) -> Path:
        text = SPEC.read_text(encoding="utf-8")
        assert old in text, f"fixture is stale: {old!r} is not in {SPEC.name}"
        path = tmp_path / "AEP.tla"
        path.write_text(text.replace(old, new, count), encoding="utf-8")
        monkeypatch.setattr(gate, "SPEC", path)
        return path

    return _mutate


def run(gate, *argv: str) -> int:
    old = sys.argv
    sys.argv = ["check_tla_transitions.py", *argv]
    try:
        return gate.main()
    finally:
        sys.argv = old


# --------------------------------------------------------------------------
# The passing branch.
# --------------------------------------------------------------------------


def test_the_committed_specification_matches_the_implementation(gate, capsys):
    assert run(gate, "--all") == 0
    assert "OK:" in capsys.readouterr().out


def test_the_specification_names_every_status_the_code_has(gate):
    body = gate.strip_comments(SPEC.read_text(encoding="utf-8"))
    assert gate.check_statuses(gate.spec_status_names(body)) == []


def test_the_specification_has_exactly_the_code_s_ten_edges(gate):
    body = gate.strip_comments(SPEC.read_text(encoding="utf-8"))
    edges = gate.spec_transitions(body, gate.spec_status_names(body))
    assert len(edges) == 10
    # The two absences the paper's claims rest on, asserted rather than assumed.
    assert not any(new == "ABOUT_TO_FIRE" for old, new in edges if old != "NONE")
    assert ("ABOUT_TO_FIRE", "PERMANENTLY_AMBIGUOUS") not in edges


# --------------------------------------------------------------------------
# The failing branches.  Each mutation is a plausible edit, not a corruption.
# --------------------------------------------------------------------------


def test_an_edge_the_code_does_not_have_is_rejected(gate, mutated, capsys):
    """The dangerous drift: a model that permits more than the code does.

    ``ABOUT_TO_FIRE -> PERMANENTLY_AMBIGUOUS`` is the edge a reader would most
    plausibly add by hand, because the direction document's own sketch of the
    state machine implies it exists (see ``formal/README.md`` finding F1).  It
    does not.
    """
    mutated("      <<PA, FC>>, <<PA, FAC>> }", "      <<PA, FC>>, <<PA, FAC>>, <<ATF, PA>> }")
    assert run(gate, "--all") == 1
    out = capsys.readouterr().out
    assert "allows ABOUT_TO_FIRE -> PERMANENTLY_AMBIGUOUS" in out


def test_an_edge_dropped_from_the_model_is_rejected(gate, mutated, capsys):
    """The quiet drift: a model that permits less, and so proves too much.

    Removing the ``FIRED_UNCONFIRMED`` self-loop would make the reconciliation
    budget unreachable and P3 vacuously true.
    """
    mutated("      <<FU, FU>>, <<FU, FC>>", "      <<FU, FC>>")
    assert run(gate, "--all") == 1
    out = capsys.readouterr().out
    assert "FIRED_UNCONFIRMED -> FIRED_UNCONFIRMED" in out
    assert "which AEP.tla does not" in out


def test_a_status_renamed_in_the_model_is_rejected(gate, mutated, capsys):
    """Check 1 compares strings, so check 2 has to hold the strings honest."""
    mutated('ATF        == "ABOUT_TO_FIRE"', 'ATF        == "ABOUT_TO_DISPATCH"')
    assert run(gate, "--all") == 1
    out = capsys.readouterr().out
    assert "ABOUT_TO_DISPATCH" in out


def test_a_protocol_action_reading_the_oracle_is_rejected(gate, mutated, capsys):
    """The failure a formal artifact must not have.

    If a protocol guard could branch on whether the endpoint really applied the
    mutation, the model would verify a protocol strictly stronger than the one
    the paper describes -- and every property would still come back green.
    """
    mutated(
        "RunnerTarget(ev) ==\n    CASE ev = \"SUCCESS\" -> FC",
        "RunnerTarget(ev) ==\n    CASE effect[1] -> FC\n      [] ev = \"SUCCESS\" -> FC",
    )
    assert run(gate, "--all") == 1
    out = capsys.readouterr().out
    assert "RunnerTarget reads the oracle" in out


def test_the_oracle_check_is_off_unless_asked_for(gate, mutated, capsys):
    """The two checks are separable, so the default must not silently include it."""
    mutated(
        "RunnerTarget(ev) ==\n    CASE ev = \"SUCCESS\" -> FC",
        "RunnerTarget(ev) ==\n    CASE effect[1] -> FC\n      [] ev = \"SUCCESS\" -> FC",
    )
    assert run(gate) == 0
    assert run(gate, "--check-oracle") == 1


def test_an_unchanged_clause_is_not_read_as_reading_the_oracle(gate, capsys):
    """Nearly every protocol action names ``effect`` in UNCHANGED.

    If the oracle check counted those, it would fail on the committed
    specification and would have to be weakened or deleted -- which is how a
    real check turns into decoration.
    """
    body = gate.strip_comments(SPEC.read_text(encoding="utf-8"))
    assert "effect" in gate.definition(body, "AcquireLease")
    assert gate.check_oracle(body) == []


def test_a_missing_specification_is_an_error_not_a_pass(gate, tmp_path, monkeypatch):
    """A gate that reports success when its subject is absent is worse than none."""
    monkeypatch.setattr(gate, "SPEC", tmp_path / "does-not-exist.tla")
    with pytest.raises(SystemExit):
        run(gate, "--all")


def test_a_specification_without_the_transition_table_is_an_error(gate, mutated):
    mutated("LegalTransitions ==", "LegalTransitionsRenamed ==")
    with pytest.raises(SystemExit):
        run(gate, "--all")
