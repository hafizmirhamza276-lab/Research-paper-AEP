"""Tests for the docs/22 citation gate (scripts/validate_citations.py).

A build gate that cannot fail is decoration. These tests pin the failure
modes the gate exists to catch -- a cited file deleted or renamed, a cited
line past the end of a shrunken file -- and pin the parsing rules that decide
what counts as a citation in the first place.
"""

from __future__ import annotations

import pytest

from scripts import validate_citations
from scripts.validate_citations import (
    Citation,
    extract_citations,
    line_count,
    main,
    validate,
)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway repository root the validator resolves paths against."""
    monkeypatch.setattr(validate_citations, "REPO_ROOT", tmp_path)
    return tmp_path


def write(repo, relative_path: str, content: str):
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def cited_document(repo, body: str):
    return write(repo, "docs/doc.md", body)


# ---------------------------------------------------------------------------
# The failures the gate exists to catch
# ---------------------------------------------------------------------------


def test_citation_to_a_missing_file_fails(repo):
    document = cited_document(repo, "See `aep_core/core/gone.py:12`.")

    citations, _ = extract_citations(document)
    failures = validate(citations)

    assert len(failures) == 1
    assert "cited file does not exist" in failures[0]


def test_citation_past_the_end_of_a_shrunken_file_fails(repo):
    write(repo, "aep_core/core/locks.py", "one\ntwo\nthree\n")
    document = cited_document(repo, "See `aep_core/core/locks.py:99`.")

    failures = validate(extract_citations(document)[0])

    assert len(failures) == 1
    assert "out of range" in failures[0]
    assert "has 3 lines" in failures[0]


def test_range_citation_fails_when_only_its_end_overruns(repo):
    write(repo, "aep_core/core/locks.py", "one\ntwo\nthree\n")
    document = cited_document(repo, "See `aep_core/core/locks.py:2-4`.")

    failures = validate(extract_citations(document)[0])

    assert len(failures) == 1
    assert "out of range" in failures[0]


def test_citation_inside_the_file_passes(repo):
    write(repo, "aep_core/core/locks.py", "one\ntwo\nthree\n")
    document = cited_document(repo, "See `aep_core/core/locks.py:1-3`.")

    assert validate(extract_citations(document)[0]) == []


def test_a_drifted_but_in_range_citation_is_not_caught(repo):
    """Documents the gate's declared limit: range validity, not semantics."""
    write(repo, "aep_core/core/locks.py", "one\ntwo\nthree\n")
    document = cited_document(repo, "See `aep_core/core/locks.py:1`.")

    assert validate(extract_citations(document)[0]) == []


# ---------------------------------------------------------------------------
# Continuation citations -- the form Phase 1B's ad-hoc validator did not check
# ---------------------------------------------------------------------------


def test_continuation_inherits_the_preceding_path_on_the_same_line(repo):
    write(repo, "aep_core/core/locks.py", "\n".join(str(n) for n in range(100)))
    document = cited_document(repo, "`aep_core/core/locks.py:10-12`, `:14-16`.")

    citations, _ = extract_citations(document)

    assert [c.path for c in citations] == [
        "aep_core/core/locks.py",
        "aep_core/core/locks.py",
    ]
    assert citations[1].is_continuation is True
    assert validate(citations) == []


def test_continuation_inherits_across_lines(repo):
    write(repo, "aep_core/core/locks.py", "\n".join(str(n) for n in range(100)))
    document = cited_document(
        repo, "`aep_core/core/locks.py:10`.\n\nAnd also `:20`.\n"
    )

    citations, _ = extract_citations(document)

    assert len(citations) == 2
    assert citations[1].path == "aep_core/core/locks.py"


def test_an_out_of_range_continuation_fails(repo):
    write(repo, "aep_core/core/locks.py", "one\ntwo\nthree\n")
    document = cited_document(repo, "`aep_core/core/locks.py:1`, `:900`.")

    failures = validate(extract_citations(document)[0])

    assert len(failures) == 1
    assert "continuation" in failures[0]
    assert "aep_core/core/locks.py:900" in failures[0]


def test_a_continuation_with_no_antecedent_warns_and_is_skipped(repo):
    document = cited_document(repo, "Orphan `:42` with nothing before it.")

    citations, warnings = extract_citations(document)

    assert citations == []
    assert len(warnings) == 1
    assert "no preceding explicit citation" in warnings[0]


# ---------------------------------------------------------------------------
# What is and is not a citation
# ---------------------------------------------------------------------------


def test_redis_key_templates_are_not_mistaken_for_citations(repo):
    document = cited_document(
        repo, "Key `aep:dispatch-auth:{execution_id}:{intent_id}` is written."
    )

    assert extract_citations(document)[0] == []


def test_fenced_blocks_are_ignored(repo):
    """Fenced blocks hold raw evidence output, not maintained anchors."""
    document = cited_document(
        repo,
        "Real `aep_core/core/locks.py:1`.\n"
        "```\n"
        "`aep_core/core/deleted.py:9999`\n"
        "```\n",
    )
    write(repo, "aep_core/core/locks.py", "one\n")

    citations, _ = extract_citations(document)

    assert len(citations) == 1
    assert citations[0].path == "aep_core/core/locks.py"


def test_unbackticked_paths_are_ignored(repo):
    document = cited_document(repo, "Plain aep_core/core/locks.py:9999 prose.")

    assert extract_citations(document)[0] == []


def test_an_inverted_range_warns(repo):
    write(repo, "aep_core/core/locks.py", "\n".join(str(n) for n in range(100)))
    document = cited_document(repo, "`aep_core/core/locks.py:50-10`.")

    _, warnings = extract_citations(document)

    assert len(warnings) == 1
    assert "inverted range" in warnings[0]


@pytest.mark.parametrize("suffix", ["py", "md", "yml", "conf", "toml", "cff"])
def test_every_declared_suffix_is_recognised(repo, suffix):
    write(repo, f"thing.{suffix}", "one\ntwo\n")
    document = cited_document(repo, f"See `thing.{suffix}:2`.")

    citations, _ = extract_citations(document)

    assert len(citations) == 1
    assert validate(citations) == []


# ---------------------------------------------------------------------------
# Line counting
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("", 0),
        ("one", 1),
        ("one\n", 1),
        ("one\ntwo", 2),
        ("one\ntwo\n", 2),
        ("one\n\n", 2),
    ],
)
def test_line_count_matches_editor_semantics(repo, content, expected):
    target = write(repo, "thing.py", content)

    assert line_count(target) == expected


# ---------------------------------------------------------------------------
# Exit status -- what CI actually keys on
# ---------------------------------------------------------------------------


def test_main_returns_nonzero_when_a_citation_is_invalid(repo, capsys):
    cited_document(repo, "See `aep_core/core/gone.py:1`.")

    assert main(["docs/doc.md"]) == 1


def test_main_returns_zero_when_every_citation_is_valid(repo, capsys):
    write(repo, "aep_core/core/locks.py", "one\ntwo\n")
    cited_document(repo, "See `aep_core/core/locks.py:2`.")

    assert main(["docs/doc.md"]) == 0
    assert "0 invalid" in capsys.readouterr().out


def test_main_returns_nonzero_when_the_target_document_is_missing(repo):
    assert main(["docs/nonexistent.md"]) == 2


def test_the_real_formal_model_validates():
    """The gate, run against the document it exists to protect."""
    assert main(["docs/22-formal-model.md"]) == 0


def test_citation_rendering_distinguishes_single_lines_from_ranges():
    single = Citation("d.md", 1, "a.py", 5, 5, False)
    span = Citation("d.md", 1, "a.py", 5, 9, False)
    inherited = Citation("d.md", 1, "a.py", 5, 5, True)

    assert single.rendered == "a.py:5"
    assert span.rendered == "a.py:5-9"
    assert inherited.rendered == "a.py:5 (continuation)"
