#!/usr/bin/env python3
r"""Fail if a repository path reaches the RENDERED manuscript.

A submitted paper does not cite the files of the repository that produced it.
Rendered references such as ``docs/22-formal-model.md``, ``scripts/…``,
``analyze.py`` or ``.claude/agents/`` are wrong for a journal, and under
double-anonymous review a path naming a personal layout is an anonymity risk as
well.

**This reads the PDFs, not the LaTeX.** A ``\texttt{}`` in a caption, a
footnote, a table cell and a generated file all reach the reader by different
routes, and only the extracted text sees all of them at once. It also means a
path added to `paper/generated/` by the table generator is caught even though
nobody edited a `.tex` file by hand.

**Provenance comments are unaffected**, because a ``%`` comment is not in the
PDF. That is the point of putting sources in comments: the evidence trail stays
in the source and never reaches the page.

What is allowed through
-----------------------
* **Vendor documentation URLs.** ``https://redis.io/docs/latest/commands/…``
  and ``https://cadenceworkflow.io/docs/concepts/workflows`` are citations, not
  repository paths. Anything inside an ``http(s)://`` run is skipped.
* **Prose that happens to contain a slash**, such as ``AEP-full/B3``: the
  pattern requires a known repository directory name before the slash, or a
  filename with a source-code extension.

Usage
-----
    python scripts/check_no_repo_paths.py                 # all four builds
    python scripts/check_no_repo_paths.py paper/main.pdf
    python scripts/check_no_repo_paths.py --text FILE     # check extracted text
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAPER = REPO / "paper"

BUILDS = ["main.pdf", "main-anon.pdf", "supplementary.pdf",
          "supplementary-anon.pdf"]

#: Top-level directories of this repository. A slash after one of these in
#: rendered text is a repository path.
REPO_DIRECTORIES = [
    "docs", "scripts", "reports", "prompts", "experiments", "tests",
    "aep_core", "results", "analysis", "paper", "figures", "generated",
    r"\.claude", r"\.github",
]

#: Extensions that make a bare word a source filename rather than prose.
SOURCE_EXTENSIONS = [
    "py", "sh", "md", "json", "jsonl", "csv", "yaml", "yml", "toml", "lock",
    "cls", "bib", "sqlite3", "cfg", "ini",
]

PATTERNS = [
    ("repository path",
     r"(?<![\w./-])(?:" + "|".join(REPO_DIRECTORIES) + r")/[\w./*-]*"),
    ("source filename",
     r"(?<![\w./-])[\w-]+\.(?:" + "|".join(SOURCE_EXTENSIONS) + r")\b"),
    ("manifest filename", r"(?<![\w./-])MANIFEST\.\w+"),
    ("artifact doc", r"(?<![\w./-])ARTIFACT\.md\b"),
]

#: Substrings that make an occurrence a citation rather than a path.
URL_MARKERS = ("http://", "https://", "doi.org", "github.com", "zenodo")


def extract_text(pdf: Path) -> str:
    """The PDF's text, via pdftotext."""
    if shutil.which("pdftotext") is None:
        raise RuntimeError(
            "pdftotext not found; it ships with poppler-utils and the paper "
            "build already requires a TeX installation"
        )
    result = subprocess.run(
        ["pdftotext", "-q", str(pdf), "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed on {pdf}: {result.stderr}")
    return result.stdout


def _url_spans(line: str) -> list[tuple[int, int]]:
    """Character ranges belonging to a URL, which are citations."""
    spans = []
    for match in re.finditer(r"(?:https?://|doi\.org/)\S*", line):
        spans.append(match.span())
    return spans


def findings(text: str) -> list[tuple[int, str, str, str]]:
    """(line number, kind, matched text, the line) for each hit."""
    out = []
    lines = text.splitlines()
    for number, line in enumerate(lines, 1):
        # A URL can wrap, so a bare continuation is judged by its neighbour.
        context = line
        if number > 1 and any(m in lines[number - 2] for m in URL_MARKERS):
            context = lines[number - 2] + " " + line
        if any(marker in context for marker in URL_MARKERS):
            spans = _url_spans(line)
        else:
            spans = []

        for kind, pattern in PATTERNS:
            for match in re.finditer(pattern, line):
                if any(s <= match.start() < e for s, e in spans):
                    continue
                # A wrapped URL: the previous line ended mid-address.
                if context is not line and not spans:
                    continue
                # The path pattern runs to the end of the run, so a sentence's
                # full stop is swallowed: `intents.py.` rather than
                # `intents.py`. Trailing punctuation is never part of a path,
                # and a trailing slash is (`.claude/agents/`).
                found = match.group(0).rstrip(".,;:)")
                if not found:
                    continue
                out.append((number, kind, found, line.strip()))
    return out


def check(pdf: Path) -> list[tuple[int, str, str, str]]:
    return findings(extract_text(pdf))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdfs", nargs="*", type=Path)
    parser.add_argument("--text", type=Path,
                        help="check an already-extracted text file")
    args = parser.parse_args(argv)

    total = 0
    if args.text:
        targets = [(args.text, findings(args.text.read_text(encoding="utf-8")))]
    else:
        pdfs = args.pdfs or [PAPER / name for name in BUILDS]
        targets = []
        for pdf in pdfs:
            if not pdf.is_file():
                print(f"  FAIL  {pdf} does not exist; build it first")
                total += 1
                continue
            targets.append((pdf, check(pdf)))

    for target, hits in targets:
        name = target.name
        if not hits:
            print(f"  PASS  {name} carries no repository path")
            continue
        total += len(hits)
        for number, kind, text, line in hits:
            print(f"  FAIL  {name} line {number}: {kind} {text!r}")
            print(f"        {line[:110]}")

    if total:
        print(f"---- {total} occurrence(s) of a repository path in rendered text")
        print("     Replace with a \\cref to the supplementary, a one-clause "
              "statement of the fact, or a generic artifact pointer.")
        return 1
    print(f"---- {len(targets)} build(s) clean, 0 failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
