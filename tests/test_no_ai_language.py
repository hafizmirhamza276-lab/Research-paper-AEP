"""No AI-tool language may reach the rendered manuscript, and the check can fail.

The author's supervisor ruled on 2026-09-25 that the article carries no
acknowledgment section and no reference to AI tools or coding agents, and that
the disclosure is submitted as a separate report. The material that report
needs is preserved in `reports/ai-use-disclosure-source-2026-09-25.md`, so the
removal loses nothing; what it does not by itself prevent is the language
coming back in a caption, a table cell or a generated file that nobody
associates with the block that was removed.

`scripts/check_no_ai_language.py` reads the PDFs rather than the LaTeX, for the
reason `check_no_repo_paths.py` does: a string reaches the page by several
routes and only the extracted text sees all of them.

**The two halves are equally the point.** The check has to fire on the
disclosure that was removed, and it has to stay silent on this paper's ordinary
vocabulary. "Model" is one of the manuscript's most-used words -- the TLA+
model, model checking, the fault model, our model of a durable-execution engine
-- and "agent" is its motivating example, named in the abstract and the index
terms. A gate that caught those would be turned off within a week.
"""
from __future__ import annotations

import shutil

import pytest

from scripts.check_no_ai_language import (
    BUILDS,
    KNOWN_POSITIVES,
    LEGITIMATE_MODEL_SENSES,
    LEGITIMATE_OTHER,
    PAPER,
    check,
    findings,
    selftest,
)

pytestmark = pytest.mark.skipif(
    shutil.which("pdftotext") is None,
    reason="pdftotext (poppler-utils) is not installed",
)


# -- the committed state ----------------------------------------------------

@pytest.mark.parametrize("name", BUILDS)
def test_no_build_carries_ai_tool_language(name):
    pdf = PAPER / name
    if not pdf.is_file():
        pytest.skip(f"{name} has not been built")
    assert check(pdf) == []


# -- the known-positives ----------------------------------------------------

@pytest.mark.parametrize("sentence", KNOWN_POSITIVES)
def test_every_pattern_family_fires(sentence):
    assert findings(sentence), f"not caught: {sentence}"


def test_the_removed_disclosure_would_be_caught():
    """The exact first sentence of the named build's acknowledgment."""
    removed = (
        "The author used Anthropic's Claude (Claude Code, with Opus, Sonnet "
        "and Haiku models) and OpenAI's Codex as coding and drafting "
        "assistants throughout this work."
    )
    kinds = {kind for _, kind, _, _ in findings(removed)}
    assert "vendor or model name" in kinds
    assert "AI-tool collocation" in kinds


def test_the_anonymous_builds_wording_would_be_caught():
    removed = (
        "The author used generative-AI coding and drafting assistants "
        "throughout this work. No AI system is an author."
    )
    assert findings(removed)


def test_the_provenance_sentence_would_be_caught():
    """Trailers, configuration files and phase prompts, each on its own."""
    for clause in (
        "the commit trailers name the model that signed each commit",
        "the per-assistant configuration files committed beside them",
        "The phase prompts issued from Phase 8 onward are committed",
    ):
        assert findings(clause), f"not caught: {clause}"


# -- the exemptions ---------------------------------------------------------

@pytest.mark.parametrize(
    "sense,sentence", LEGITIMATE_MODEL_SENSES, ids=lambda v: None
)
def test_legitimate_model_senses_pass(sense, sentence):
    assert findings(sentence) == [], f"false positive on {sense}"


@pytest.mark.parametrize("sense,sentence", LEGITIMATE_OTHER, ids=lambda v: None)
def test_other_legitimate_uses_pass(sense, sentence):
    assert findings(sentence) == [], f"false positive on {sense}"


def test_cited_titles_are_exempt():
    """Altering a cited title would misquote its authors."""
    entry = (
        '[38] I. K. Mansoor, A. Phadke, and P. Rana, "Verified tool calls '
        'improve LLM agent reliability under non-atomic failures," CoRR, '
        'vol. abs/2608.02645, 2026.'
    )
    assert findings(entry) == []


def test_the_exemption_is_not_a_blanket_one():
    """A new AI sentence next to a cited title is still caught."""
    line = (
        '[38] "Verified tool calls improve LLM agent reliability under '
        'non-atomic failures." Drafted with Claude.'
    )
    hits = findings(line)
    assert hits, "the exemption swallowed a real occurrence"
    assert any(text.lower() == "claude" for _, _, text, _ in hits)


# -- the gate's own evidence ------------------------------------------------

def test_selftest_passes(capsys):
    assert selftest() == 0
    assert "confirmed" in capsys.readouterr().out
