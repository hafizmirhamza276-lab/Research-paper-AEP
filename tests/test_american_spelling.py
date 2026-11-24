r"""No British spelling may reach the rendered manuscript, and the check can fail.

IEEE house style is American English; the manuscript was written in British
``-ise`` throughout, which `docs/37` §11 recorded as the convention until the
mechanical pass at the end. Seventy-three words were converted across
``main.tex``, the nine section files and ``supplementary.tex``.

`scripts/check_american_spelling.py` reads the PDFs rather than the LaTeX, for
the reason `check_no_repo_paths.py` gives: a word reaches the page from a
caption, a footnote, a table cell, a run-in heading and a generated file by
five different routes, and only the extracted text sees all of them. That is
not hypothetical here -- the pass over the ``.tex`` files missed *organised* in
``paper/generated/table-outcomes.tex``, whose caption is a string literal in
``scripts/paper_tables.py``, and the PDF check is what found it.

**The known-positives are the point.** Every way the check can fire is
exercised against text that must make it fire, and every exemption against text
that must not.
"""
from __future__ import annotations

import shutil

import pytest

from scripts.check_american_spelling import (
    BUILDS,
    EXEMPT,
    PAPER,
    americanise,
    explicit_form,
    is_allowed_ise,
    scan,
    selftest,
)

pytestmark = pytest.mark.skipif(
    shutil.which("pdftotext") is None,
    reason="pdftotext (poppler-utils) is not installed",
)


# -- the committed state ----------------------------------------------------

@pytest.mark.parametrize("name", BUILDS)
def test_no_build_carries_a_british_spelling(name):
    from scripts.check_american_spelling import extract

    pdf = PAPER / name
    if not pdf.is_file():
        pytest.skip(f"{name} has not been built")
    hits = scan(extract(pdf))
    assert hits == [], [f"{w} -> {s}" for _, w, s, _ in hits]


# -- known-positives: every family the check knows about --------------------

@pytest.mark.parametrize("word", [
    "behaviour", "favour", "honour", "colour",          # -our
    "modelled", "labelled", "cancelled",                # doubled l
    "enrolment", "fulfil",                              # single l
    "judgement", "artefact", "whilst",                  # miscellaneous
    "centre", "defence", "licence",                     # -re, -ce
    "organised", "realise", "serialisation",            # -ise, -isation
    "analysed", "analysing",                            # -yse
])
def test_a_british_spelling_is_caught(word):
    hits = scan(f"The sentence contains {word} in it.\n")
    assert [w.lower() for _, w, _, _ in hits] == [word]


def test_a_prefix_does_not_launder_a_british_spelling():
    """"remodelled" is "modelled" with a prefix and is just as British."""
    hits = scan("It was remodelled, disorganised and unrecognised.\n")
    found = {w.lower() for _, w, _, _ in hits}
    assert found == {"remodelled", "disorganised", "unrecognised"}


# -- known-negatives: everything that must NOT fire -------------------------

@pytest.mark.parametrize("word", [
    "exercise", "exercised", "exercising", "comprise", "comprising",
    "promise", "promised", "premise", "premises", "supervise", "surprise",
    "revise", "advise", "enterprise", "expertise", "precise", "concise",
    "raise", "arise", "noise", "otherwise", "likewise",
])
def test_an_ise_word_common_to_both_englishes_is_not_flagged(word):
    assert scan(f"We {word} the endpoint.\n") == []


def test_a_prefixed_both_englishes_word_is_not_flagged():
    """The check fired on "imprecise" the first time it was run."""
    assert scan("The bound is imprecise rather than wrong, and unwise.\n") == []


@pytest.mark.parametrize("term", sorted(EXEMPT))
def test_every_exempt_identifier_is_not_flagged(term):
    assert scan(f"See {term} for the detail.\n") == []


def test_analogue_is_exempt_by_author_decision():
    """Reverted 2026-09-23 after the mechanical pass converted it.

    It is the British spelling, so the pass was right to convert it and the
    check was right to know it. The revert is a judgement about the reader:
    "analog" in an IEEE paper reads electronics-first, and both uses here mean
    "counterpart". Removing the EXEMPT entry converts them again.
    """
    assert scan("a Start-To-Close timeout that B4 has no analogue for\n") == []
    assert "analogue" in EXEMPT


def test_every_exemption_carries_a_reason():
    """An exemption without a stated reason is one nobody can re-audit."""
    for term, reason in EXEMPT.items():
        assert reason and len(reason) > 10, term


def test_the_references_section_keeps_its_own_spelling():
    """Correcting a cited title is a misquotation."""
    text = ("Our behavior is American.\n"
            "REFERENCES\n"
            '[1] A. Author, "Analysing behaviour," 2026.\n')
    assert scan(text) == []


def test_text_before_the_references_heading_is_still_checked():
    text = ("Our behaviour is British.\n"
            "REFERENCES\n"
            '[1] A. Author, "Analysing behaviour," 2026.\n')
    assert [w.lower() for _, w, _, _ in scan(text)] == ["behaviour"]


# -- the suggestion the failure message prints ------------------------------

@pytest.mark.parametrize("brit,amer", [
    ("behaviour", "behavior"),
    ("organised", "organized"),
    ("serialisation", "serialization"),
    ("analysed", "analyzed"),
    ("remodelled", "remodeled"),
])
def test_the_suggested_replacement_is_the_american_form(brit, amer):
    assert americanise(brit) == amer


def test_helpers_agree_with_each_other():
    assert explicit_form("behaviour") == "behavior"
    assert explicit_form("exercise") is None
    assert is_allowed_ise("imprecise")
    assert not is_allowed_ise("organised")


# -- the script's own selftest ----------------------------------------------

def test_the_scripts_selftest_passes(capsys):
    assert selftest() == 0
    assert "6 of 6 confirmed" in capsys.readouterr().out
