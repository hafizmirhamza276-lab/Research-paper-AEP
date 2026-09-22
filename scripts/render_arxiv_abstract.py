#!/usr/bin/env python3
r"""Render arXiv's paste-ready abstract FROM ``paper/main.tex``, and check it.

Why this exists
---------------
``paper/arxiv-metadata.md`` carried a hand-transcribed abstract. It drifted: by
2026-09-22 the file held an entire earlier generation of the abstract --- a
different opening, a different framing, and five sentences of statistics the
manuscript no longer states there --- while claiming at the top that "every
number in the abstract below is the resolved value of a generated macro". The
manuscript had moved and nothing could notice.

Hand-transcription is the defect. This module makes the metadata file a
*derived* artifact: the abstract is extracted from ``main.tex``, its macros are
resolved from ``paper/generated/numbers.tex``, and the result is converted to
the plain text arXiv's abstract field accepts. ``--check`` fails when the
committed block differs from what the manuscript now says, which is the same
discipline ``scripts/check_paper_numbers.py`` applies to the body.

What "plain text" means here
----------------------------
arXiv's abstract field does not render LaTeX markup, so this emits none:
em-dashes become ``--``, ``\emph``/``\textbf``/``\texttt``/``\textsc`` lose
their wrappers, ``$\times$`` becomes ``x``, superscripts keep ``^``, and thin
spaces inside numbers close up. Paragraph breaks survive; line wrapping does
not, because arXiv reflows.

**Two failure modes this refuses to paper over.** An unknown macro is an error,
not a literal ``\Foo`` in the output --- that is exactly how a stale number
would reach a submission. And a backslash surviving conversion is an error,
because it means a construct appeared in the abstract that this converter does
not know about, and guessing at it would put LaTeX source in a plain-text
field.

Usage
-----
    python scripts/render_arxiv_abstract.py            # print the rendering
    python scripts/render_arxiv_abstract.py --check    # exit 1 if stale
    python scripts/render_arxiv_abstract.py --write    # update the metadata
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

MAIN_TEX = REPO / "paper" / "main.tex"
NUMBERS_TEX = REPO / "paper" / "generated" / "numbers.tex"
METADATA = REPO / "paper" / "arxiv-metadata.md"

#: The metadata file's generated region. Markers rather than "the first fenced
#: block after a heading": a heading can be renamed and a fence can be added
#: above, and either would silently retarget an in-place rewrite.
BEGIN_MARKER = "<!-- BEGIN GENERATED ABSTRACT -- render_arxiv_abstract.py -->"
END_MARKER = "<!-- END GENERATED ABSTRACT -->"

#: arXiv's limit, quoted on info.arxiv.org/help/prep.html: "abstracts longer
#: than 1920 characters will not be accepted". Read 2026-08-21.
ARXIV_ABSTRACT_LIMIT = 1920


class RenderError(RuntimeError):
    """The abstract contains something this converter will not guess at."""


# -- extraction -------------------------------------------------------------

def extract_abstract(main_tex: str) -> str:
    """The LaTeX between ``\\begin{abstract}`` and ``\\end{abstract}``."""
    match = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}", main_tex, re.DOTALL
    )
    if match is None:
        raise RenderError("no abstract environment in main.tex")
    return match.group(1)


def extract_title(main_tex: str) -> str:
    """``\\title{...}``, with its typesetting line break removed.

    The title is split across two lines with ``\\\\`` so IEEEtran breaks it
    where the author chose. arXiv's title field is one line.
    """
    match = re.search(r"\\title\{(.*?)\}\s*\n\n", main_tex, re.DOTALL)
    if match is None:
        raise RenderError("no title in main.tex")
    title = match.group(1).replace("\\\\", " ")
    return re.sub(r"\s+", " ", title).strip()


def extract_keywords(main_tex: str) -> list[str]:
    """The ``IEEEkeywords`` block, split on commas."""
    match = re.search(
        r"\\begin\{IEEEkeywords\}(.*?)\\end\{IEEEkeywords\}", main_tex, re.DOTALL
    )
    if match is None:
        raise RenderError("no IEEEkeywords block in main.tex")
    body = re.sub(r"\s+", " ", match.group(1)).strip().rstrip(".")
    return [k.strip() for k in body.split(",") if k.strip()]


def load_macros(numbers_tex: str) -> dict[str, str]:
    """``\\newcommand{\\Foo}{value}`` pairs, keyed without the backslash."""
    macros: dict[str, str] = {}
    for name, value in re.findall(
        r"\\newcommand\{\\([A-Za-z]+)\}\{([^{}]*)\}", numbers_tex
    ):
        macros[name] = value
    return macros


# -- conversion -------------------------------------------------------------

def expand_macros(text: str, macros: dict[str, str]) -> str:
    """Resolve every generated macro. An unknown one is an error.

    ``\\Foo{}`` and ``\\Foo`` are both accepted; the first is how a macro is
    written before a space that must survive.
    """
    known = "|".join(sorted(macros, key=len, reverse=True))
    if known:
        text = re.sub(
            rf"\\({known})(\{{\}})?", lambda m: macros[m.group(1)], text
        )
    # Anything left that looks like a generated macro -- CamelCase, no
    # arguments -- was meant to resolve and did not.
    stray = re.findall(r"\\([A-Z][A-Za-z]*)(?:\{\})?(?![A-Za-z{])", text)
    if stray:
        raise RenderError(
            "abstract uses macro(s) absent from generated/numbers.tex: "
            + ", ".join(sorted(set(stray)))
            + " -- run scripts/paper_tables.py"
        )
    return text


#: Wrappers whose braces are dropped and whose contents are kept verbatim.
_PLAIN_WRAPPERS = ("emph", "textbf", "textit", "texttt", "textsc", "text")

#: Math commands with a settled plain-text spelling. Matched as *commands*,
#: anywhere, not as the literal string ``$\times$`` -- a parametrised test
#: caught that narrower form failing on ``$1.9\times10^{-6}$``, which is the
#: shape a Fisher p-value actually takes in this manuscript.
#:
#: The flag is whether the command closes up against what follows.
#: ``1.9\times 10^{-6}`` is one number and reads ``1.9x10^-6``; ``p \le 0.05``
#: is two tokens and must keep its space.
_MATH_COMMANDS = {
    "times": ("x", True),
    "cdot": (".", True),
    "pm": ("+/-", False),
    "approx": ("~", False),
    "le": ("<=", False),
    "ge": (">=", False),
}

#: Escapes and quotes with a settled plain-text spelling.
_LITERALS = {
    r"\%": "%",
    r"\&": "&",
    r"\_": "_",
    r"\#": "#",
    r"\$": "$",
    "``": '"',
    "''": '"',
    "~": " ",
}


def to_plain_text(text: str) -> str:
    """LaTeX to the plain text arXiv's abstract field accepts."""
    # Comments first: a % to end of line is not content, and leaving it in
    # would smuggle a provenance note into a submission.
    text = re.sub(r"(?<!\\)%.*", "", text)

    text = re.sub(r"\\label\{[^}]*\}", "", text)

    for wrapper in _PLAIN_WRAPPERS:
        # Repeated: \emph{a \textbf{b} c} needs two passes.
        pattern = rf"\\{wrapper}\{{([^{{}}]*)\}}"
        while re.search(pattern, text):
            text = re.sub(pattern, r"\1", text)

    for command, (replacement, closes_up) in _MATH_COMMANDS.items():
        trailing = r"\s*" if closes_up else ""
        text = re.sub(rf"\\{command}(?![A-Za-z]){trailing}", replacement, text)

    for source, replacement in _LITERALS.items():
        text = text.replace(source, replacement)

    # Thin space: closes up inside a number (1\,000 -> 1000), otherwise a
    # space (5\,ms -> 5 ms).
    text = re.sub(r"(?<=\d)\\,(?=\d)", "", text)
    text = text.replace(r"\,", " ")

    # Em-dash. arXiv renders nothing, and "--" is the convention the file
    # already used.
    text = text.replace("---", "--")

    # Inline math that survived: keep the contents, which is where ^ lives.
    text = re.sub(r"\$([^$]*)\$", r"\1", text)

    if "\\" in text:
        leftover = sorted(set(re.findall(r"\\[A-Za-z]+|\\.", text)))
        raise RenderError(
            "unconverted LaTeX in the abstract: "
            + ", ".join(leftover)
            + " -- teach render_arxiv_abstract.py this construct rather than "
              "hand-editing arxiv-metadata.md"
        )

    # Reflow: collapse each paragraph, keep the blank lines between them.
    paragraphs = [
        re.sub(r"\s+", " ", block).strip()
        for block in re.split(r"\n\s*\n", text)
    ]
    return "\n\n".join(p for p in paragraphs if p)


def render(main_tex: str, numbers_tex: str) -> str:
    """The paste-ready abstract."""
    abstract = extract_abstract(main_tex)
    return to_plain_text(expand_macros(abstract, load_macros(numbers_tex)))


# -- the metadata file ------------------------------------------------------

def read_committed(metadata: str) -> str:
    """The abstract currently in ``arxiv-metadata.md``."""
    match = re.search(
        re.escape(BEGIN_MARKER) + r"\s*\n```\n(.*?)\n```\s*\n" + re.escape(END_MARKER),
        metadata,
        re.DOTALL,
    )
    if match is None:
        raise RenderError(
            "arxiv-metadata.md has no generated-abstract block; expected\n"
            f"  {BEGIN_MARKER}\n  ```\n  ...\n  ```\n  {END_MARKER}"
        )
    return match.group(1)


def replace_committed(metadata: str, rendered: str) -> str:
    """``arxiv-metadata.md`` with the block replaced."""
    read_committed(metadata)  # raises if the markers are absent
    return re.sub(
        re.escape(BEGIN_MARKER) + r"\s*\n```\n.*?\n```\s*\n" + re.escape(END_MARKER),
        lambda _: f"{BEGIN_MARKER}\n```\n{rendered}\n```\n{END_MARKER}",
        metadata,
        flags=re.DOTALL,
    )


# -- checks -----------------------------------------------------------------

def check(main_tex: str, numbers_tex: str, metadata: str) -> list[str]:
    """Every way the metadata can disagree with the manuscript."""
    failures: list[str] = []

    rendered = render(main_tex, numbers_tex)

    try:
        committed = read_committed(metadata)
    except RenderError as error:
        return [str(error)]

    if committed != rendered:
        failures.append(
            "the abstract in arxiv-metadata.md is not what main.tex now says.\n"
            + _first_difference(committed, rendered)
            + "\n    fix: python scripts/render_arxiv_abstract.py --write"
        )

    length = len(rendered)
    if length > ARXIV_ABSTRACT_LIMIT:
        failures.append(
            f"the rendered abstract is {length} characters, over arXiv's "
            f"{ARXIV_ABSTRACT_LIMIT}-character limit by "
            f"{length - ARXIV_ABSTRACT_LIMIT}"
        )

    title = extract_title(main_tex)
    if title not in metadata:
        failures.append(
            f"the title in arxiv-metadata.md is not main.tex's:\n    {title!r}"
        )

    keywords = extract_keywords(main_tex)
    missing = [k for k in keywords if k not in metadata]
    if missing:
        failures.append(
            "keyword(s) in main.tex's IEEEkeywords block are absent from "
            "arxiv-metadata.md: " + ", ".join(repr(k) for k in missing)
        )

    return failures


def _first_difference(committed: str, rendered: str) -> str:
    """Where they part, so the failure names a place and not just a fact."""
    for index, (left, right) in enumerate(zip(committed, rendered)):
        if left != right:
            start = max(0, index - 40)
            return (
                f"    first differs at character {index}:\n"
                f"      committed: ...{committed[start:index + 40]!r}\n"
                f"      main.tex : ...{rendered[start:index + 40]!r}"
            )
    shorter, longer = sorted((committed, rendered), key=len)
    return (
        f"    identical for {len(shorter)} characters, then "
        f"{'main.tex' if longer is rendered else 'the committed block'} "
        f"continues: {longer[len(shorter):len(shorter) + 80]!r}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if arxiv-metadata.md is stale")
    parser.add_argument("--write", action="store_true",
                        help="rewrite the generated block in arxiv-metadata.md")
    args = parser.parse_args(argv)

    main_tex = MAIN_TEX.read_text(encoding="utf-8")
    numbers_tex = NUMBERS_TEX.read_text(encoding="utf-8")

    if args.write:
        rendered = render(main_tex, numbers_tex)
        metadata = METADATA.read_text(encoding="utf-8")
        METADATA.write_text(
            replace_committed(metadata, rendered), encoding="utf-8", newline="\n"
        )
        print(f"wrote {len(rendered)} characters to {METADATA.name}")
        return 0

    if args.check:
        metadata = METADATA.read_text(encoding="utf-8")
        failures = check(main_tex, numbers_tex, metadata)
        for failure in failures:
            print(f"  FAIL  {failure}")
        if failures:
            print(f"---- {len(failures)} failed")
            return 1
        rendered = render(main_tex, numbers_tex)
        print(f"  PASS  abstract matches main.tex ({len(rendered)} characters, "
              f"{ARXIV_ABSTRACT_LIMIT - len(rendered)} under arXiv's limit)")
        print(f"  PASS  title matches main.tex")
        print(f"  PASS  all {len(extract_keywords(main_tex))} keyword(s) present")
        print("---- 3 ok, 0 failed")
        return 0

    print(render(main_tex, numbers_tex))
    return 0


if __name__ == "__main__":
    sys.exit(main())
