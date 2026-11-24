"""The analysis may read two things, and this is the gate that says so.

Amendment D3: *"The analysis must read ONLY events.jsonl + the oracle ledger --
never internal AEP state directly."*

That is not a style preference. Every number in the paper is a comparison
between what the system *recorded* and what the world *did*, and the whole
force of it comes from those two records being produced independently. An
analysis that reached into Redis to ask the system how it feels now would be
comparing the oracle against a third thing -- one that has had the benefit of
seeing the run finish -- and the reconciliation would stop being a check.

Enforced by parsing the source rather than by trusting the imports at run
time, for the same reason ``experiments/harness/tests/test_crash_points.py``
parses ``aep_core``: the gate should read what the file actually says.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ANALYSIS_MODULES = ("analyze.py", "statistics.py")

#: Anything that could reach the system under test's live state.
FORBIDDEN_ROOTS = frozenset({"redis", "fakeredis"})

#: ``aep_core`` as a whole is forbidden: there is no submodule of it the
#: analysis needs, and permitting one would make the next one an argument
#: rather than a test failure.
FORBIDDEN_PACKAGES = frozenset({"aep_core"})

#: The harness modules that open Redis or build the protocol. Importing any of
#: them would pull the live-state dependency in transitively.
FORBIDDEN_EXPERIMENT_MODULES = frozenset(
    {
        "experiments.harness.composition",
        "experiments.harness.runner",
        "experiments.harness.worker",
        "experiments.harness.recovery",
        "experiments.harness.orchestrate",
        "experiments.harness.reconcile",
        "experiments.mock_api.ledger",
        "experiments.mock_api.service",
        "experiments.mock_api.supervisor",
        "experiments.mock_api.client",
    }
)

ROOT = Path(__file__).resolve().parents[1]


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


@pytest.mark.parametrize("module", ANALYSIS_MODULES)
def test_the_analysis_cannot_reach_live_state(module: str) -> None:
    imported = imported_modules(ROOT / module)
    for name in sorted(imported):
        root = name.split(".")[0]
        assert root not in FORBIDDEN_ROOTS, (
            f"{module} imports {name!r}. The analysis reads events.jsonl and "
            "the ground-truth ledger; a Redis client here would let it ask the "
            "system under test what it thinks now, which is not what any "
            "number in the paper claims to compare."
        )
        assert root not in FORBIDDEN_PACKAGES, (
            f"{module} imports {name!r}. The analysis reads the *log format*, "
            "not the code that produced it: sharing an enum with the harness "
            "would make the two agree by construction."
        )
        assert name not in FORBIDDEN_EXPERIMENT_MODULES, (
            f"{module} imports {name!r}, which opens Redis or builds the "
            "protocol, and would pull live state in transitively."
        )


def test_the_ledger_is_opened_read_only() -> None:
    """A read-write handle on the oracle could alter the evidence."""
    source = (ROOT / "analyze.py").read_text(encoding="utf-8")
    assert "mode=ro" in source
    assert "uri=True" in source


def test_the_analysis_reads_exactly_two_files_per_run() -> None:
    """Named here so that adding a third input is a decision, not a drift."""
    source = (ROOT / "analyze.py").read_text(encoding="utf-8")
    assert '"events.jsonl"' in source
    assert '"ground_truth.sqlite3"' in source
    # summary.json is written by the harness from *its own* reconciliation. If
    # the analysis read it, the paper's numbers would be the harness's numbers
    # restated rather than recomputed.
    assert "summary.json" not in source


def test_the_outcome_vocabulary_is_declared_locally() -> None:
    """The class names are literals here, not an import from the harness.

    The point of the duplication: the analysis is pinned to the *log format*.
    If the harness renamed a class without changing the logs, this module would
    keep working; if it renamed one and changed the logs, the unknown-class
    guard fires. Sharing the enum would silently accept either.
    """
    from experiments import analyze
    from experiments.baselines.contract import OutcomeClass

    assert analyze.KNOWN_CLASSES == frozenset(
        member.value for member in OutcomeClass
    ), (
        "the analysis's declared vocabulary has drifted from the harness's. "
        "This test exists to make that a deliberate update in two places, not "
        "an import."
    )
