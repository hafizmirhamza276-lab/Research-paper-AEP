#!/usr/bin/env python3
"""Claim-level sweep of the manuscript, for the pre-Phase-10 assessment.

`check_paper_numbers.py` verifies every number against its source, and the
orphan gate plus LaTeX make a withdrawn *number* impossible to leave behind.
Neither reaches a withdrawn *claim*: a sentence that states a conclusion,
cites a section rather than a macro, and carries no number is invisible to
every check in the repository.  F.0b named that mechanism and recorded the
enforcing lexicon check as unimplemented.  This is that check, widened from
equivalence vocabulary to strength vocabulary.

Two outputs:

  map     every macro site, file and line -- the sentences that CAN be
          audited against a source.
  sweep   every sentence carrying evidential force that cites NO macro --
          the sentences that cannot.  This is the audit list.

Generated captions are included.  B20 found two of its four defects inside
them, and no grep over `sections/*.tex` reaches a generated file.

Read-only.  Prints; writes nothing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"

MACRO = re.compile(r"\\([A-Z][A-Za-z]+)\{\}")

# Strength vocabulary.  Equivalence terms are F.0b's original list; the rest
# are the words a paper uses when it asserts that something is established,
# caused, or large.  Deliberately over-inclusive: a false positive costs one
# line of reading, a false negative is the defect this exists to find.
LEXICON = [
    # equivalence -- F.0b's list
    "indistinguishab", "equivalen", "no difference", "no observed difference",
    "no effect", "unaffected", "identical to", "the same as", "shows no",
    # strength and magnitude
    "large", "largely", "small", "nearly free", "substantial", "dramatic",
    "order of magnitude", "far more", "much more",
    # causation and mechanism -- where the paper explains rather than reports
    "because", "therefore", "is produced by", "produced by", "buys", "causes",
    "the reason", "explains", "is why", "which is why", "structural",
    "mechanism", "drives", "decided by", "a function of",
    # establishment
    "we show", "we demonstrate", "shows that", "establishes", "confirms",
    "proves", "guarantees", "prevents", "eliminates", "ensures",
    "is real", "now measured", "measured", "significant",
]
LEXICON_RE = re.compile("|".join(re.escape(t) for t in LEXICON), re.I)

# Lines that are structure, not prose.
SKIP = re.compile(
    r"^\s*(%|\\(begin|end|label|input|centering|toprule|midrule|bottomrule|"
    r"small|item\b|newcommand|documentclass|usepackage|section|subsection|"
    r"subsubsection|caption\*?\{?$))"
)


def files() -> list[Path]:
    out = sorted((PAPER / "sections").glob("*.tex"))
    out.append(PAPER / "main.tex")
    out += sorted((PAPER / "generated").glob("*.tex"))
    return [p for p in out if p.is_file() and p.name != "numbers.tex"]


def sentences(path: Path) -> list[tuple[int, str]]:
    """(line number of the sentence's first line, sentence text)."""
    raw = path.read_text(encoding="utf-8").splitlines()
    buf: list[str] = []
    start = 1
    out: list[tuple[int, str]] = []

    def flush() -> None:
        if buf:
            text = " ".join(buf).strip()
            if text:
                out.append((start, re.sub(r"\s+", " ", text)))
        buf.clear()

    for i, line in enumerate(raw, 1):
        stripped = line.strip()
        if not stripped or SKIP.match(line):
            flush()
            start = i + 1
            continue
        if not buf:
            start = i
        buf.append(stripped)
        # A sentence ends at . ! ? not preceded by a lowercase abbreviation
        # and not inside \cref{...}.
        while True:
            m = re.search(r"(?<![A-Z])[.!?](?:''|\")?(\s|$)", " ".join(buf))
            if not m:
                break
            joined = " ".join(buf)
            head, tail = joined[: m.end()].strip(), joined[m.end():].strip()
            out.append((start, re.sub(r"\s+", " ", head)))
            buf.clear()
            if tail:
                buf.append(tail)
            else:
                break
    flush()
    return out


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "sweep"
    n_sites = n_sent = n_hits = 0

    for path in files():
        rel = path.relative_to(ROOT).as_posix()
        if mode == "map":
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for name in MACRO.findall(line):
                    print(f"{rel}:{i}\t{name}")
                    n_sites += 1
            continue

        for lineno, text in sentences(path):
            n_sent += 1
            if MACRO.search(text):
                continue
            if not LEXICON_RE.search(text):
                continue
            n_hits += 1
            hit = sorted({m.group(0).lower() for m in LEXICON_RE.finditer(text)})
            print(f"\n{rel}:{lineno}  [{', '.join(hit)}]")
            print(f"  {text}")

    print(f"\n--- {'sites' if mode == 'map' else 'sentences'}: "
          f"{n_sites if mode == 'map' else n_sent}", end="")
    if mode != "map":
        print(f", evidential with no macro: {n_hits}", end="")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
