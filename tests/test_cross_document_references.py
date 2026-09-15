"""The cross-document reference check, watched failing on every branch.

``docs/26`` §3 rule 13. WS-9 moves sections out of the main text into the
supplementary, and phase 27 stopped before doing it because a partial migration
splits ``\\cref`` targets across two documents *while every gate stays green*.
This check is what makes that visible, so it is built and exercised before
anything moves.

``docs/25`` R17: nothing here executes the old code or touches the real paper
tree. Each case builds a two-document tree in ``tmp_path`` and runs the current
check over it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_paper_numbers import (  # noqa: E402
    Result,
    check_cross_document_references,
)


def build(tmp_path: Path, main_body: str, supp_body: str) -> Path:
    """A minimal paper/ tree: main.tex, one section, generated/, supplementary."""
    paper = tmp_path / "paper"
    (paper / "sections").mkdir(parents=True)
    (paper / "generated").mkdir(parents=True)
    (paper / "main.tex").write_text("\\documentclass{article}\n", encoding="utf-8")
    (paper / "sections" / "06-evaluation.tex").write_text(
        main_body, encoding="utf-8")
    (paper / "generated" / "table-latency.tex").write_text(
        "\\label{tab:latency}\n", encoding="utf-8")
    (paper / "supplementary.tex").write_text(supp_body, encoding="utf-8")
    return paper


def run(paper: Path) -> Result:
    result = Result()
    check_cross_document_references(result, paper)
    return result


def failed(result: Result, fragment: str) -> bool:
    return any(fragment in f for f in result.failures)


def test_a_clean_two_document_tree_passes(tmp_path):
    paper = build(
        tmp_path,
        "\\label{sec:eval}\nSee \\cref{sec:eval} and \\cref{tab:latency}.\n",
        "\\label{supp:extra}\nThe evaluation section of the paper gives it.\n",
    )
    result = run(paper)
    assert not result.failures, result.failures


def test_a_cref_in_main_to_a_label_only_in_the_supplementary_fails(tmp_path):
    """The migration half-done: the block moved, the pointer did not."""
    paper = build(
        tmp_path,
        "See \\cref{supp:moved} for the detail.\n",
        "\\label{supp:moved}\nThe moved block.\n",
    )
    result = run(paper)
    assert failed(result, "every reference in the main text resolves")


def test_a_label_defined_in_both_documents_fails(tmp_path):
    """The migration that copied instead of moving.

    This is the one no existing gate saw: LaTeX is silent in both documents,
    every other check passes, and a reader following the main text's pointer
    lands on whichever copy went stale.
    """
    paper = build(
        tmp_path,
        "\\label{sec:eval-deployment}\nSee \\cref{sec:eval-deployment}.\n",
        "\\label{sec:eval-deployment}\nThe same block, copied.\n",
    )
    result = run(paper)
    assert failed(result, "no label is defined in both documents")


def test_a_cref_in_the_supplementary_into_the_paper_fails(tmp_path):
    """The supplementary's own header says it cannot do this.

    A convention nothing enforces is a comment, so this asserts it.
    """
    paper = build(
        tmp_path,
        "\\label{sec:eval}\nThe evaluation.\n",
        "As shown in \\cref{sec:eval}, the rate holds.\n",
    )
    result = run(paper)
    assert failed(result, "every reference in the supplementary resolves")


def test_a_commented_out_reference_is_not_a_reference(tmp_path):
    """A migration that comments a block out rather than deleting it must not
    read as still-referencing, or the check reports a dangling ref forever."""
    paper = build(
        tmp_path,
        "\\label{sec:eval}\n% See \\cref{supp:gone} for the old version.\n",
        "\\label{supp:extra}\nDetail.\n",
    )
    result = run(paper)
    assert not result.failures, result.failures


def test_an_unreferenced_supplementary_label_is_a_note_not_a_failure(tmp_path):
    """The main text points at the supplementary by name, by design.

    So this must be visible and must not be a failure -- otherwise the check
    would force `\\cref`s that the two-document split makes impossible.
    """
    paper = build(
        tmp_path,
        "\\label{sec:eval}\nThe supplementary material gives the detail.\n",
        "\\label{supp:orphan}\nDetail.\n",
    )
    result = run(paper)
    assert not result.failures, result.failures
