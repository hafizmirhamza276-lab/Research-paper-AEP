"""The deployment table must be placeable in either document.

WS-9's migration stopped in phase 30 because
``generated/table-deployment-choice.tex`` carried four ``\\cref``s into the main
text. A ``\\cref`` cannot cross documents --- ``supplementary.tex`` says so in
its own header --- so the table was pinned to the paper by its own caption, and
moving it made the supplementary build fail with undefined references.

``docs/26`` §3 rule 13: the fix is known to be the fix because the pre-fix
caption is watched failing the very gate the post-fix caption passes.
``docs/25`` R17: nothing here executes an older generator. The failing-branch
evidence is the real pre-fix caption text, kept verbatim as a fixture.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_paper_numbers import (  # noqa: E402
    Result,
    check_cross_document_references,
)

GENERATED = ROOT / "paper" / "generated" / "table-deployment-choice.tex"

#: The caption exactly as it stood before this fix, trimmed to the clause that
#: carried the cross-document references.
PRE_FIX = (
    r"\multicolumn{6}{@{}p{0.96\textwidth}@{}}{\footnotesize "
    r"The detection claim of \cref{tab:outcomes} shows no observed "
    r"difference in any cell, bounded by pooling the capability classes "
    r"rather than per class (\cref{sec:eval-detection}): it is produced "
    r"by the pre-dispatch record plus no re-entry, "
    r"which all three rows have, and \cref{tab:ablation} is the "
    r"ablation that shows it. What the barrier buys is the last "
    r"column's second word, and \cref{sec:eval-prevention} is what it is "
    r"worth.}\\"
)


def build(tmp_path: Path, table_body: str, inputter: str) -> Path:
    """A two-document tree where `inputter` is 'main' or 'supp'."""
    paper = tmp_path / "paper"
    (paper / "sections").mkdir(parents=True)
    (paper / "generated").mkdir(parents=True)
    (paper / "main.tex").write_text("\\documentclass{article}\n", encoding="utf-8")

    main_body = (
        "\\label{sec:eval-detection}\\label{sec:eval-prevention}\n"
        "\\label{tab:outcomes}\\label{tab:ablation}\n"
    )
    supp_body = "\\label{supp:extra}\nDetail.\n"
    line = "\\input{generated/table-deployment-choice}\n"
    if inputter == "main":
        main_body += line
    else:
        supp_body += line

    (paper / "sections" / "06-evaluation.tex").write_text(
        main_body, encoding="utf-8")
    (paper / "supplementary.tex").write_text(supp_body, encoding="utf-8")
    (paper / "generated" / "table-deployment-choice.tex").write_text(
        table_body + "\n", encoding="utf-8")
    return paper


def run(paper: Path) -> Result:
    result = Result()
    check_cross_document_references(result, paper)
    return result


def failed(result: Result, fragment: str) -> bool:
    return any(fragment in f for f in result.failures)


def test_the_pre_fix_caption_pins_the_table_to_the_main_text(tmp_path):
    """In main it is fine -- which is why nobody noticed for nine passes."""
    result = run(build(tmp_path, PRE_FIX, "main"))
    assert not result.failures, result.failures


def test_the_pre_fix_caption_fails_the_gate_in_the_supplementary(tmp_path):
    """Rule 13. This is exactly what stopped phase 30."""
    result = run(build(tmp_path, PRE_FIX, "supp"))
    assert failed(result, "every reference in the supplementary resolves"), (
        result.failures
    )


def test_the_real_caption_is_portable(tmp_path):
    """The post-fix caption, read from the generated file rather than retyped.

    Reading the real artifact means this test fails if a later regeneration
    reintroduces a \\cref, which is the property worth holding.
    """
    body = GENERATED.read_text(encoding="utf-8")
    for where in ("main", "supp"):
        result = run(build(tmp_path / where, body, where))
        assert not result.failures, (where, result.failures)


def test_the_generated_caption_contains_no_cref_at_all():
    """The direct statement of the invariant, so a reader of this file sees it."""
    body = GENERATED.read_text(encoding="utf-8")
    assert not re.search(r"\\[cC]ref\{", body), (
        "the deployment table carries a \\cref again; it is then pinned to "
        "whichever document defines that label"
    )
