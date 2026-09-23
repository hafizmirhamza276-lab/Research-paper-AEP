"""The arXiv metadata is derived from the manuscript, and the check can fail.

`paper/arxiv-metadata.md` held a hand-transcribed abstract that fell an entire
generation behind `paper/main.tex` -- a different opening, a different framing,
and five sentences of statistics the manuscript no longer states there -- while
the file's own header claimed every number in it was a resolved macro. Nothing
could notice, because nothing compared them.

**The known-positives are the point of this file.** A checker that has only
ever been seen to pass is not evidence. Every check in
`render_arxiv_abstract.py` is exercised here against an input that must make it
fail: a changed abstract, a changed title, a dropped keyword, an unresolved
macro, an unconvertible construct, and an over-length abstract. If any of those
stops failing, the check has quietly stopped checking.
"""
from __future__ import annotations

import re

import pytest

from scripts.render_arxiv_abstract import (
    ARXIV_ABSTRACT_LIMIT,
    BEGIN_MARKER,
    END_MARKER,
    MAIN_TEX,
    METADATA,
    NUMBERS_TEX,
    RenderError,
    check,
    expand_macros,
    extract_abstract,
    extract_keywords,
    extract_title,
    load_macros,
    read_committed,
    render,
    replace_committed,
    to_plain_text,
)


@pytest.fixture(scope="module")
def main_tex() -> str:
    return MAIN_TEX.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def numbers_tex() -> str:
    return NUMBERS_TEX.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def metadata() -> str:
    return METADATA.read_text(encoding="utf-8")


# -- the committed state ----------------------------------------------------

def test_the_committed_metadata_matches_the_manuscript(
    main_tex, numbers_tex, metadata
):
    """The check that would have caught the drift, run on the real files."""
    assert check(main_tex, numbers_tex, metadata) == []


def test_the_rendered_abstract_fits_arxivs_limit(main_tex, numbers_tex):
    rendered = render(main_tex, numbers_tex)
    assert len(rendered) <= ARXIV_ABSTRACT_LIMIT, (
        f"{len(rendered)} characters, limit {ARXIV_ABSTRACT_LIMIT}"
    )


def test_the_rendered_abstract_carries_no_latex(main_tex, numbers_tex):
    rendered = render(main_tex, numbers_tex)
    assert "\\" not in rendered
    assert "---" not in rendered, "em-dash should render as --"
    for wrapper in ("\\emph", "\\texttt", "\\textbf", "\\textsc"):
        assert wrapper not in rendered


def test_the_metadata_carries_no_second_copy_of_the_abstract(metadata):
    """The deleted short form was a second hand-maintained copy, and it drifted.

    Anything long, prose-like and fenced that is *not* the generated block is
    the failure mode returning.
    """
    generated = read_committed(metadata)
    others = [
        block for block in re.findall(r"```\n(.*?)\n```", metadata, re.DOTALL)
        if block != generated and len(block) > 400
    ]
    assert others == [], (
        "a second long fenced block is in arxiv-metadata.md; if it is another "
        "copy of the abstract, delete it -- one derived copy is the design"
    )


# -- known-positives: each check, made to fail ------------------------------

def test_known_positive_a_changed_abstract_is_caught(
    main_tex, numbers_tex, metadata
):
    """The exact drift that happened: the committed block says something else."""
    committed = read_committed(metadata)
    tampered = replace_committed(
        metadata, committed.replace("Many enterprise APIs", "Autonomous agents")
    )
    failures = check(main_tex, numbers_tex, tampered)
    assert failures, "a rewritten abstract passed the check"
    assert "not what main.tex now says" in failures[0]
    assert "first differs at character" in failures[0]


def test_known_positive_a_truncated_abstract_is_caught(
    main_tex, numbers_tex, metadata
):
    """Length-only drift, with no differing character before the end."""
    committed = read_committed(metadata)
    tampered = replace_committed(metadata, committed[: len(committed) // 2])
    failures = check(main_tex, numbers_tex, tampered)
    assert failures
    assert "identical for" in failures[0]


def test_known_positive_a_changed_title_is_caught(
    main_tex, numbers_tex, metadata
):
    title = extract_title(main_tex)
    tampered = metadata.replace(title, "Declared Ambiguity: A Shorter Title")
    failures = check(main_tex, numbers_tex, tampered)
    assert any("title" in f for f in failures), failures


def test_known_positive_a_dropped_keyword_is_caught(
    main_tex, numbers_tex, metadata
):
    keyword = extract_keywords(main_tex)[-1]
    tampered = metadata.replace(keyword, "")
    failures = check(main_tex, numbers_tex, tampered)
    assert any("keyword" in f for f in failures), failures
    assert any(repr(keyword) in f for f in failures), failures


def test_known_positive_a_missing_marker_block_is_caught(
    main_tex, numbers_tex, metadata
):
    tampered = metadata.replace(BEGIN_MARKER, "<!-- moved -->")
    failures = check(main_tex, numbers_tex, tampered)
    assert failures
    assert "no generated-abstract block" in failures[0]


def test_known_positive_an_unknown_macro_is_an_error_not_a_literal():
    """The failure mode that would put a stale number in a submission."""
    with pytest.raises(RenderError) as error:
        expand_macros(r"the rate is \NotAMacro over \AlsoMissing runs", {})
    assert "absent from generated/numbers.tex" in str(error.value)
    assert "NotAMacro" in str(error.value)
    assert "AlsoMissing" in str(error.value)


def test_known_positive_an_unconvertible_construct_is_an_error():
    """Better a red build than LaTeX source pasted into a plain-text field."""
    with pytest.raises(RenderError) as error:
        to_plain_text(r"see \cref{sec:evaluation} for the rate")
    assert "unconverted LaTeX" in str(error.value)
    assert "\\cref" in str(error.value)


def test_known_positive_an_over_length_abstract_is_caught(
    numbers_tex, metadata
):
    """A manuscript edit that crosses arXiv's limit must turn the build red."""
    padding = "Padding sentence that adds length. " * 60
    fake_main = (
        "\\title{T}\n\n"
        "\\begin{abstract}\n" + padding + "\n\\end{abstract}\n"
        "\\begin{IEEEkeywords}\nk\n\\end{IEEEkeywords}\n"
    )
    rendered = render(fake_main, numbers_tex)
    assert len(rendered) > ARXIV_ABSTRACT_LIMIT, "the fixture is not long enough"
    tampered = replace_committed(metadata, rendered)
    failures = check(fake_main, numbers_tex, tampered)
    assert any("over arXiv's" in f for f in failures), failures


# -- the converter's rules --------------------------------------------------

@pytest.mark.parametrize("source,expected", [
    (r"a \emph{b} c", "a b c"),
    (r"a \textbf{b} c", "a b c"),
    (r"a \texttt{SIGKILL} c", "a SIGKILL c"),
    (r"a \textsc{pos-only} c", "a pos-only c"),
    ("a --- b", "a -- b"),
    (r"1\,000 runs", "1000 runs"),
    (r"5\,ms", "5 ms"),
    (r"$1.9\times10^{-6}$", "1.9x10^{-6}"),
    (r"50\% of", "50% of"),
    ("a~b", "a b"),
    (r"``quoted''", '"quoted"'),
    ("a % a comment\nb", "a b"),
    (r"\label{sec:x}text", "text"),
])
def test_plain_text_rules(source, expected):
    assert to_plain_text(source) == expected


def test_paragraph_breaks_survive_and_line_wrapping_does_not():
    assert to_plain_text("one\nline\n\ntwo\nline") == "one line\n\ntwo line"


def test_macros_resolve_with_and_without_empty_braces():
    macros = {"Rate": "0.0112", "N": "269"}
    assert expand_macros(r"\Rate{} over \N runs", macros) == "0.0112 over 269 runs"


def test_real_macros_load_from_numbers_tex(numbers_tex):
    macros = load_macros(numbers_tex)
    assert macros["ArmASessions"] == "3"
    assert macros["ArmAClasses"] == "3"
    assert macros["RunsCollected"] == "432"


# -- extraction -------------------------------------------------------------

def test_the_title_loses_its_typesetting_line_break(main_tex):
    title = extract_title(main_tex)
    assert "\\\\" not in title
    assert "\n" not in title
    # The startswith/endswith pair is the point of this test: it proves the
    # extraction spans BOTH authored lines, the first up to the ``\\`` and the
    # second after it. A retitle updates these two strings -- deleting either
    # would leave the test passing on a title that lost half of itself.
    assert title.startswith("AEP: Declared Ambiguity")
    assert title.endswith("Without Idempotency Keys")


def test_the_abstract_is_the_environments_contents(main_tex):
    abstract = extract_abstract(main_tex)
    assert "\\begin{abstract}" not in abstract
    assert "\\end{abstract}" not in abstract
    assert "enterprise APIs" in abstract


def test_keywords_are_split_and_stripped(main_tex):
    keywords = extract_keywords(main_tex)
    assert "Fault tolerance" in keywords
    assert "autonomous agents" in keywords
    assert all(k == k.strip() for k in keywords)
    assert not any(k.endswith(".") for k in keywords)


def test_a_missing_environment_is_an_error():
    with pytest.raises(RenderError):
        extract_abstract("no abstract here")
    with pytest.raises(RenderError):
        extract_title("no title here")
    with pytest.raises(RenderError):
        extract_keywords("no keywords here")


# -- round trip -------------------------------------------------------------

def test_write_then_check_is_a_fixed_point(main_tex, numbers_tex, metadata):
    rendered = render(main_tex, numbers_tex)
    rewritten = replace_committed(metadata, rendered)
    assert read_committed(rewritten) == rendered
    assert check(main_tex, numbers_tex, rewritten) == []


def test_the_markers_are_present_exactly_once(metadata):
    assert metadata.count(BEGIN_MARKER) == 1
    assert metadata.count(END_MARKER) == 1


# -- the closure constraint -------------------------------------------------

def test_neither_file_claims_an_agent_evaluation(metadata):
    """Phase 40 is closed; agents are motivating context only (Option A).

    `docs/33` §0's third banner and `prompts/phase-40-closure-2026-09-22.md` §6
    settle this: no manuscript-adjacent text may claim or imply that an agent
    or a language model was evaluated.
    """
    cover = (METADATA.parent / "cover-letter-tse.md").read_text(encoding="utf-8")
    for name, text in (("arxiv-metadata.md", metadata), ("cover-letter-tse.md", cover)):
        low = text.lower()
        for forbidden in ("phase 40", "phase-40", "llm", "language model",
                          "agent execution protocol"):
            assert forbidden not in low, f"{name} mentions {forbidden!r}"


@pytest.mark.parametrize("source,expected", [
    # Closes up: one number. This is the shape a Fisher p-value takes here.
    (r"$1.9\times10^{-6}$", "1.9x10^{-6}"),
    (r"$1.9 \times 10^{-6}$", "1.9 x10^{-6}"),
    (r"$2.2\times10^{-53}$", "2.2x10^{-53}"),
    # Keeps its space: two tokens.
    (r"$p \le 0.05$", "p <= 0.05"),
    (r"$n \ge 30$", "n >= 30"),
    (r"a $\pm$ b", "a +/- b"),
])
def test_math_commands_are_matched_as_commands_not_as_literals(source, expected):
    """A parametrised known-positive that already earned its keep.

    The first version of this converter replaced the literal string
    ``$\times$`` and left ``\times`` inside a longer math span untouched --
    which the over-length check would not have caught, because the renderer
    raises on the surviving backslash instead. This table is why it was found
    before the file was committed rather than after.
    """
    assert to_plain_text(source) == expected
