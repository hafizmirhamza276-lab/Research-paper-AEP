#!/usr/bin/env python3
"""Range-validate the ``file:line`` citations in AEP's living documents.

`docs/22-formal-model.md` grounds every behavioural claim in a `file:line`
citation. Those anchors rot silently: a refactor moves a function, the
citation keeps pointing at a line number that now holds something else, and
the document quietly starts lying. This script is the CI gate against the
detectable half of that rot.

What it proves
--------------
Every cited path exists, and every cited line (or line range) falls inside
that file. That is *range validity* only.

What it does NOT prove
----------------------
That a citation points at the *right* code. A citation that drifts from line
400 to line 402 within the same file still validates. Semantic correctness
rests on the per-anchor evidence recorded in the phase reports. This gate
catches deletions, renames, and truncations -- the failures that turn a
citation into a dangling pointer.

Citation forms recognised
-------------------------
Explicit, inside backticks::

    `aep_core/core/intents.py:1186`
    `aep_core/core/intents.py:1081-1162`

Continuation, inside backticks, inheriting the most recently named path in
document order::

    `aep_core/core/locks.py:149-152`, `:35-52`, `:54-70`

The continuation form carries real risk -- it is only as correct as its
antecedent -- so it is validated rather than ignored, and the resolved path
is shown for every failure.

Usage::

    python scripts/validate_citations.py                    # default targets
    python scripts/validate_citations.py docs/22-formal-model.md
    python scripts/validate_citations.py --verbose docs/22-formal-model.md

Exit status is 0 only when every citation in every target is in range.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Documents that must stay citation-valid. Adding a living document here is
#: what puts it under the CI gate.
DEFAULT_TARGETS = ("docs/22-formal-model.md",)

#: File suffixes a citation may point at. Requiring a known suffix keeps the
#: pattern from swallowing Redis key templates such as
#: ``aep:dispatch-auth:{execution_id}:{intent_id}``.
CITED_SUFFIXES = ("py", "md", "yml", "yaml", "conf", "toml", "cff", "lua", "txt")

_SUFFIX_ALTERNATION = "|".join(CITED_SUFFIXES)

#: `path/to/file.ext:123` or `path/to/file.ext:123-456`
EXPLICIT_CITATION = re.compile(
    rf"`(?P<path>[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:{_SUFFIX_ALTERNATION}))"
    r":(?P<start>\d+)(?:-(?P<end>\d+))?`"
)

#: `:123` or `:123-456` -- inherits the last explicit path seen.
CONTINUATION_CITATION = re.compile(r"`:(?P<start>\d+)(?:-(?P<end>\d+))?`")

#: Fenced code blocks hold raw command output, which is evidence rather than
#: citation. Anchors there are not maintained and must not gate the build.
FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class Citation:
    """One `file:line` anchor found in a document."""

    document: str
    document_line: int
    path: str
    start: int
    end: int
    is_continuation: bool

    @property
    def rendered(self) -> str:
        span = f"{self.start}" if self.start == self.end else f"{self.start}-{self.end}"
        form = " (continuation)" if self.is_continuation else ""
        return f"{self.path}:{span}{form}"


def extract_citations(document: Path) -> tuple[list[Citation], list[str]]:
    """Return every citation in ``document``, plus warnings about odd ones."""
    citations: list[Citation] = []
    warnings: list[str] = []
    relative_document = document.relative_to(REPO_ROOT).as_posix()
    last_explicit_path: str | None = None
    in_fence = False

    for line_number, raw_line in enumerate(
        document.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if FENCE.match(raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        # Walk both patterns in a single left-to-right pass so that a
        # continuation always resolves against the path that textually
        # precedes it, including one earlier on the same line.
        matches = sorted(
            [(m, False) for m in EXPLICIT_CITATION.finditer(raw_line)]
            + [(m, True) for m in CONTINUATION_CITATION.finditer(raw_line)],
            key=lambda pair: pair[0].start(),
        )

        for match, is_continuation in matches:
            start = int(match.group("start"))
            end = int(match.group("end") or start)

            if is_continuation:
                if last_explicit_path is None:
                    warnings.append(
                        f"{relative_document}:{line_number}: continuation "
                        f"`:{start}` has no preceding explicit citation; skipped"
                    )
                    continue
                path = last_explicit_path
            else:
                path = match.group("path")
                last_explicit_path = path

            if end < start:
                warnings.append(
                    f"{relative_document}:{line_number}: inverted range "
                    f"{path}:{start}-{end}"
                )

            citations.append(
                Citation(
                    document=relative_document,
                    document_line=line_number,
                    path=path,
                    start=start,
                    end=end,
                    is_continuation=is_continuation,
                )
            )

    return citations, warnings


def line_count(path: Path) -> int:
    """Count lines the way an editor does: a trailing newline ends the last line."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text:
        return 0
    return len(text.splitlines())


def validate(citations: list[Citation]) -> list[str]:
    """Return one failure string per out-of-range or dangling citation."""
    failures: list[str] = []
    known_line_counts: dict[str, int] = {}

    for citation in citations:
        target = REPO_ROOT / citation.path
        if citation.path not in known_line_counts:
            if not target.is_file():
                failures.append(
                    f"{citation.document}:{citation.document_line}: "
                    f"{citation.rendered} -> cited file does not exist"
                )
                known_line_counts[citation.path] = -1
                continue
            known_line_counts[citation.path] = line_count(target)

        total = known_line_counts[citation.path]
        if total == -1:
            failures.append(
                f"{citation.document}:{citation.document_line}: "
                f"{citation.rendered} -> cited file does not exist"
            )
            continue

        if citation.start < 1 or citation.end > total:
            failures.append(
                f"{citation.document}:{citation.document_line}: "
                f"{citation.rendered} -> out of range, {citation.path} has "
                f"{total} lines"
            )

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Range-validate file:line citations in AEP documents.",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        default=list(DEFAULT_TARGETS),
        help=f"documents to validate (default: {' '.join(DEFAULT_TARGETS)})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="list every citation that was checked",
    )
    arguments = parser.parse_args(argv)

    targets = arguments.targets or list(DEFAULT_TARGETS)

    all_citations: list[Citation] = []
    all_warnings: list[str] = []
    exit_code = 0

    for target in targets:
        document = (REPO_ROOT / target).resolve()
        if not document.is_file():
            print(f"ERROR: target document not found: {target}", file=sys.stderr)
            exit_code = 2
            continue

        citations, warnings = extract_citations(document)
        all_citations.extend(citations)
        all_warnings.extend(warnings)

        explicit = sum(1 for c in citations if not c.is_continuation)
        continuation = len(citations) - explicit
        print(
            f"{target}: {len(citations)} citations "
            f"({explicit} explicit, {continuation} continuation)"
        )

    if arguments.verbose:
        for citation in all_citations:
            print(f"  {citation.document}:{citation.document_line}  {citation.rendered}")

    for warning in all_warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    failures = validate(all_citations)
    if failures:
        print(f"\nINVALID CITATIONS: {len(failures)}", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    if exit_code == 0:
        print(f"OK: {len(all_citations)} citations, 0 invalid")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
